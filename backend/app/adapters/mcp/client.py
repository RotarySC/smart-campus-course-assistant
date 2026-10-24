"""MCP 客户端（API 侧）与内部 API 客户端（MCP 侧）。

- :class:`McpToolClient` 由 runner 使用：每次工具调用签发新的 ``aud=cca-mcp`` 短委派，
  经 SDK Streamable HTTP 调用 MCP server（``127.0.0.1:8102/mcp``）。
- :class:`InternalToolClient` 由 MCP server 使用：先兑换 ``aud=cca-internal`` 受限凭据，
  再调用内部三工具端点。用户 Bearer 不进入 MCP，也不进入工具参数。
- 技术故障（不可达/超时/非契约响应）与业务失败严格分开：前者 ``MCP_UNAVAILABLE``，
  后者携带统一 code/message/request_id。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.adapters.mcp.delegation import (
    AUD_INTERNAL,
    AUD_MCP,
    SCOPE_DOCS_SEARCH,
    SCOPE_PLAN_SAVE,
    SCOPE_SCHEDULE_READ,
    mint_delegation,
)
from app.adapters.model.gateway import (
    EvidenceChunk,
    EvidenceReference,
    EvidenceSet,
    ToolCall,
    ToolExecutionRecord,
)
from app.config import get_settings
from app.shared.context import ExecutionContext
from app.shared.errors import ERROR_MESSAGE, ApiError

logger = logging.getLogger("cca.mcp.client")

TOOL_SCOPE: dict[str, str] = {
    "get_my_schedule": SCOPE_SCHEDULE_READ,
    "search_course_docs": SCOPE_DOCS_SEARCH,
    "save_study_plan": SCOPE_PLAN_SAVE,
}

DELEGATION_HEADER = "X-CCA-Delegation"
EXECUTION_HEADER = "X-Execution-Context"
SERVICE_HEADER = "X-Service-Credential"

DEFAULT_INTERNAL_URL = "http://127.0.0.1:8101"
DEFAULT_MCP_URL = "http://127.0.0.1:8102/mcp"

MCP_CALL_TIMEOUT_SECONDS = 20.0
INTERNAL_CALL_TIMEOUT_SECONDS = 10.0


class ToolExecutor(Protocol):
    """runner 依赖的工具执行端口（测试可注入）。"""

    async def execute(self, call: ToolCall, context: ExecutionContext) -> ToolExecutionRecord: ...


class InternalServiceError(Exception):
    """内部 API 的业务错误（带稳定 code/message/request_id）。"""

    def __init__(self, code: str, message: str, *, request_id: str = "", status_code: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id
        self.status_code = status_code


class InternalServiceUnavailable(Exception):
    """内部 API 技术故障（不可达/超时/响应不合法）。"""


# --------------------------------------------------------------------------- #
# API 侧：MCP 工具客户端
# --------------------------------------------------------------------------- #
class McpToolClient:
    """通过 MCP SDK 调用三工具；每次调用一个新委派（jti 不重复）。"""

    def __init__(
        self,
        url: str | None = None,
        *,
        service_token: str | None = None,
        timeout: float = MCP_CALL_TIMEOUT_SECONDS,
    ) -> None:
        self.url = url or _env_or("CCA_MCP_URL", DEFAULT_MCP_URL)
        self.service_token = service_token or get_settings().service_token
        self.timeout = timeout

    def _mint(self, tool_name: str, context: ExecutionContext) -> str:
        return mint_delegation(
            audience=AUD_MCP,
            user_id=context.actor.user_id,
            session_id=context.actor.session_id,
            auth_version=context.actor.auth_version,
            request_id=context.chat_request_id,
            conversation_id=context.conversation_id,
            scope=[TOOL_SCOPE[tool_name]],
            fence=context.execution_fence,
            deadline_at=context.deadline_at,
        )

    async def execute(self, call: ToolCall, context: ExecutionContext) -> ToolExecutionRecord:
        if call.tool_name not in TOOL_SCOPE:
            return _failure(call, "FORBIDDEN", "工具不在白名单内")
        delegation = self._mint(call.tool_name, context)
        try:
            result = await self._call_tool(call.tool_name, call.arguments, delegation)
        except ApiError as exc:
            return _failure(call, exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001 - 技术故障统一映射
            # 技术失败保留分类（不伪装 empty/成功），同时记录异常类型与栈便于定位。
            # 注意：不记录工具返回正文/令牌。
            logger.exception(
                "mcp tool call failed tool=%s request_id=%s",
                call.tool_name,
                context.chat_request_id,
            )
            return _failure(
                call,
                "MCP_UNAVAILABLE",
                ERROR_MESSAGE["MCP_UNAVAILABLE"],
                detail=type(exc).__name__,
            )
        return _record_from_result(call, result)

    async def _call_tool(
        self, tool_name: str, arguments: dict[str, Any], delegation: str
    ) -> Any:
        # 延迟导入：只有真正走 MCP 时才需要 SDK；也让导入期错误集中在入口层。
        from mcp import ClientSession
        from mcp.client.streamable_http import (
            create_mcp_http_client,
            streamable_http_client,
        )

        headers = {
            SERVICE_HEADER: self.service_token,
            DELEGATION_HEADER: delegation,
        }
        http_client = create_mcp_http_client(headers=headers, timeout=self.timeout)
        async with http_client:
            async with streamable_http_client(self.url, http_client=http_client) as (
                read_stream,
                write_stream,
            ):
                async with ClientSession(
                    read_stream, write_stream, read_timeout_seconds=self.timeout
                ) as session:
                    await session.initialize()
                    return await session.call_tool(tool_name, arguments)


def _env_or(name: str, default: str) -> str:
    import os

    value = os.environ.get(name, "").strip()
    return value or default


def _failure(
    call: ToolCall,
    code: str,
    message: str,
    *,
    detail: str | None = None,
) -> ToolExecutionRecord:
    payload: dict[str, Any] = {"code": code, "message": message}
    if detail:
        payload["error_type"] = detail
    return ToolExecutionRecord(
        tool_name=call.tool_name,
        arguments=call.arguments,
        success=False,
        result_status="failed",
        dependency_state="failed",
        code=code,
        payload=payload,
    )


def _record_from_result(call: ToolCall, result: Any) -> ToolExecutionRecord:
    """把 MCP ``CallToolResult`` 映射为 runner 的记录（业务失败不伪装成功）。"""
    is_error = bool(getattr(result, "is_error", False))
    structured = getattr(result, "structured_content", None) or {}
    if not isinstance(structured, dict):
        structured = {}
    if is_error:
        code = str(structured.get("code") or "MCP_UNAVAILABLE")
        message = str(structured.get("message") or ERROR_MESSAGE.get(code, "工具执行失败"))
        return _failure(call, code, message)

    status = str(structured.get("status") or "")
    if call.tool_name == "get_my_schedule":
        dependency = "satisfied" if status == "ok" else "empty"
        return ToolExecutionRecord(
            tool_name=call.tool_name,
            arguments=call.arguments,
            success=True,
            result_status=status or "empty",
            dependency_state=dependency,  # type: ignore[arg-type]
            payload=structured,
        )
    if call.tool_name == "search_course_docs":
        evidence = _evidence_from_payload(structured)
        dependency = "satisfied" if evidence.status == "ok" else "empty"
        payload = dict(structured)
        payload["_evidence"] = evidence
        return ToolExecutionRecord(
            tool_name=call.tool_name,
            arguments=call.arguments,
            success=True,
            result_status=evidence.status,
            dependency_state=dependency,  # type: ignore[arg-type]
            payload=payload,
        )
    # save_study_plan：created/existing 都算已满足依赖
    save_status = status if status in ("created", "existing") else "failed"
    return ToolExecutionRecord(
        tool_name=call.tool_name,
        arguments=call.arguments,
        success=save_status != "failed",
        result_status=save_status,
        dependency_state="satisfied" if save_status != "failed" else "failed",
        payload=structured,
    )


def _evidence_from_payload(payload: dict[str, Any]) -> EvidenceSet:
    chunks: list[EvidenceChunk] = []
    for item in payload.get("chunks") or []:
        if not isinstance(item, dict):
            continue
        chunks.append(
            EvidenceChunk(
                chunk_id=str(item.get("chunk_id") or ""),
                reference_id=str(item.get("reference_id") or ""),
                document_id=str(item.get("document_id") or ""),
                version_id=str(item.get("version_id") or ""),
                text=str(item.get("text") or ""),
                location_label=str(item.get("location_label") or ""),
                page_number=(
                    int(item["page_number"]) if item.get("page_number") is not None else None
                ),
            )
        )
    references: list[EvidenceReference] = []
    for item in payload.get("references") or []:
        if not isinstance(item, dict):
            continue
        references.append(
            EvidenceReference(
                reference_id=str(item.get("reference_id") or ""),
                document_id=str(item.get("document_id") or ""),
                version_id=str(item.get("version_id") or ""),
                file_name=str(item.get("file_name") or ""),
                location_label=str(item.get("location_label") or ""),
                page_number=(
                    int(item["page_number"]) if item.get("page_number") is not None else None
                ),
            )
        )
    status = "ok" if payload.get("status") == "ok" and chunks else "empty"
    return EvidenceSet(
        status=status,  # type: ignore[arg-type]
        corpus_empty=bool(payload.get("corpus_empty")),
        revision=int(payload.get("revision") or 0),
        chunks=tuple(chunks),
        references=tuple(references),
    )


# --------------------------------------------------------------------------- #
# MCP 侧：内部 API 客户端
# --------------------------------------------------------------------------- #
@dataclass
class InternalToolResult:
    data: dict[str, Any]
    request_id: str = ""


class InternalToolClient:
    """MCP server 侧访问内部 API（服务身份 + 双跳凭据）。"""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        service_token: str | None = None,
        timeout: float = INTERNAL_CALL_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = (base_url or _env_or("CCA_INTERNAL_API_URL", DEFAULT_INTERNAL_URL)).rstrip(
            "/"
        )
        self.service_token = service_token or get_settings().service_token
        self.timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            trust_env=False,
            headers={"X-Service-Credential": self.service_token},
        )

    async def exchange(self, delegation: str) -> dict[str, Any]:
        async with self._client() as client:
            try:
                response = await client.post(
                    "/internal/v1/delegations/exchange",
                    json={"delegation": delegation},
                )
            except httpx.HTTPError as exc:
                raise InternalServiceUnavailable(type(exc).__name__) from exc
        return _unwrap(response)

    async def call_tool(
        self,
        path: str,
        body: dict[str, Any],
        *,
        execution_context: str,
    ) -> InternalToolResult:
        async with self._client() as client:
            try:
                response = await client.post(
                    path,
                    json=body,
                    headers={EXECUTION_HEADER: execution_context},
                )
            except httpx.HTTPError as exc:
                raise InternalServiceUnavailable(type(exc).__name__) from exc
        data = _unwrap(response)
        return InternalToolResult(data=data, request_id=str(data.pop("_request_id", "")))


def _unwrap(response: httpx.Response) -> dict[str, Any]:
    """解包内部 API 信封；业务错误抛 InternalServiceError，技术故障抛 Unavailable。"""
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise InternalServiceUnavailable("响应不是合法 JSON") from exc
    if not isinstance(body, dict):
        raise InternalServiceUnavailable("响应结构不合法")
    request_id = str(body.get("request_id") or "")
    if response.status_code >= 400 or "error" in body:
        error = body.get("error") or {}
        if not isinstance(error, dict) or not error.get("code"):
            raise InternalServiceUnavailable(f"内部服务错误响应不合法 status={response.status_code}")
        raise InternalServiceError(
            str(error.get("code")),
            str(error.get("message") or ERROR_MESSAGE.get(str(error.get("code")), "内部服务错误")),
            request_id=request_id,
            status_code=response.status_code,
        )
    data = body.get("data")
    if not isinstance(data, dict):
        raise InternalServiceUnavailable("内部服务响应缺少 data")
    return dict(data, _request_id=request_id)


__all__ = [
    "AUD_INTERNAL",
    "AUD_MCP",
    "DELEGATION_HEADER",
    "EXECUTION_HEADER",
    "InternalServiceError",
    "InternalServiceUnavailable",
    "InternalToolClient",
    "InternalToolResult",
    "McpToolClient",
    "SERVICE_HEADER",
    "TOOL_SCOPE",
    "ToolExecutor",
]
