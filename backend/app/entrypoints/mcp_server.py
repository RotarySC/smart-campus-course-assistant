"""MCP Server 入口（私有 Streamable HTTP，``127.0.0.1:8102/mcp``；PHASE-03 A4）。

技术决定 D4：``mcp==2.3.0``，使用 ``from mcp.server.mcpserver import MCPServer``
（不是 1.x 的 ``FastMCP``）；HTTP 用 ``streamable_http_app()`` / ``run_streamable_http_async``。

边界：
- 只发布固定三工具，schema 与 ``contracts/mcp_tools_v0.1.json`` 对应；
  不开放动态发现/管理工具/远程 URL 工具。
- 工具实现只做参数校验 + 委派兑换 + 调用内部端点，**不直接读库**。
- 身份来源是传输头里的 ``aud=cca-mcp`` 短委派；用户 Bearer 不进入 MCP。
- 业务失败返回 ``isError=true`` + 统一 code/message/request_id；技术故障不返回 empty。
- 仅回环监听 + Host/Origin 校验。
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS, CallToolResult, TextContent
from pydantic import Field

from app.adapters.mcp.client import (
    DELEGATION_HEADER,
    InternalServiceError,
    InternalServiceUnavailable,
    InternalToolClient,
)
from app.adapters.mcp.delegation import (
    AUD_MCP,
    SCOPE_DOCS_SEARCH,
    SCOPE_PLAN_SAVE,
    SCOPE_SCHEDULE_READ,
    verify_delegation,
)
from app.modules.assistant.contracts import (
    SaveToolOutput,
    ScheduleToolOutput,
    SearchToolOutput,
    contract_dump,
    validate_tool_call,
)
from app.modules.assistant.settings import get_assistant_settings
from app.shared.errors import ApiError

logger = logging.getLogger("cca.mcp")

MCP_PATH = "/mcp"
SERVER_NAME = "cca-assistant-tools"

QueryText = Annotated[str, Field(min_length=1, max_length=2000, description="检索内容")]
DraftId = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]
DraftVersion = Annotated[int, Field(ge=1)]

TOOL_SCOPES = {
    "get_my_schedule": SCOPE_SCHEDULE_READ,
    "search_course_docs": SCOPE_DOCS_SEARCH,
    "save_study_plan": SCOPE_PLAN_SAVE,
}

TOOL_PATHS = {
    "get_my_schedule": "/internal/v1/tools/get-my-schedule",
    "search_course_docs": "/internal/v1/tools/search-course-docs",
    "save_study_plan": "/internal/v1/tools/save-study-plan",
}


class StrictToolArguments:
    """``tools/call`` 参数严格校验（未知字段/类型不符 → JSON-RPC invalid params）。

    工具业务失败与协议结构错误分开：这里只处理后者（设计 §9.3）。
    """

    async def __call__(self, ctx: Any, call_next: Any) -> Any:
        if getattr(ctx, "method", "") == "tools/call":
            params = getattr(ctx, "params", None) or {}
            name = str(params.get("name") or "")
            arguments = params.get("arguments") or {}
            try:
                validate_tool_call(name, arguments)
            except ApiError as exc:
                raise MCPError(INVALID_PARAMS, exc.message) from exc
        return await call_next(ctx)



def _tool_error(code: str, message: str, request_id: str = "") -> CallToolResult:
    payload: dict[str, Any] = {"code": code, "message": message}
    if request_id:
        payload["request_id"] = request_id
    return CallToolResult(
        content=[TextContent(type="text", text=message)],
        structuredContent=payload,
        isError=True,
    )


def _client() -> InternalToolClient:
    return InternalToolClient(get_assistant_settings().internal_api_url)


def _delegation_of(ctx: Context) -> str:
    headers = ctx.headers or {}
    token = headers.get(DELEGATION_HEADER) or headers.get(DELEGATION_HEADER.lower())
    if not token:
        raise ApiError("AUTH_REQUIRED", message="缺少委派凭据")
    return str(token)


async def _call_internal(
    tool_name: str,
    arguments: dict[str, Any],
    ctx: Context,
    output_model: Any,
) -> Any:
    """兑换 + 调用内部端点；业务失败/技术故障都映射成 MCP 工具错误。"""
    client = _client()
    try:
        delegation = _delegation_of(ctx)
        claims = verify_delegation(
            delegation, expected_audience=AUD_MCP, required_scope=TOOL_SCOPES[tool_name]
        )
        logger.info(
            "mcp tool call tool=%s request_id=%s fence=%s",
            tool_name,
            claims.request_id,
            claims.fence,
        )
        exchanged = await client.exchange(delegation)
        internal_token = str(exchanged.get("delegation") or "")
        if not internal_token:
            raise InternalServiceUnavailable("兑换响应缺少 delegation")
        result = await client.call_tool(
            TOOL_PATHS[tool_name], arguments, execution_context=internal_token
        )
    except ApiError as exc:
        return _tool_error(exc.code, exc.message)
    except InternalServiceError as exc:
        return _tool_error(exc.code, exc.message, exc.request_id)
    except InternalServiceUnavailable:
        logger.warning("internal api unavailable tool=%s", tool_name)
        return _tool_error("MCP_UNAVAILABLE", "工具服务暂不可用")
    except Exception:  # noqa: BLE001 - 不把内部细节暴露给模型
        logger.exception("mcp tool crashed tool=%s", tool_name)
        return _tool_error("MCP_UNAVAILABLE", "工具服务暂不可用")
    return _tool_success(output_model(**result.data))


def _tool_success(output: Any) -> CallToolResult:
    """成功结果：``structuredContent`` 必须能通过已发布的 outputSchema 校验。

    MCP 客户端（mcp 2.3.0 ``ClientSession.call_tool`` → ``validate_tool_result``）会用
    ``list_tools`` 公布的 outputSchema 对 structuredContent 做 jsonschema 校验。设计包中
    ``page_number`` 等字段是“可选非 nullable”，但 SDK 默认 ``model_dump`` 会把缺省字段
    序列化成 ``null`` → 校验失败（Invalid structured content）。因此显式按
    ``exclude_none=True`` 序列化：缺省键省略，与 outputSchema/设计包一致。
    """
    payload = contract_dump(output)
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structuredContent=payload,
        isError=False,
    )


def create_server() -> MCPServer:
    server = MCPServer(
        name=SERVER_NAME,
        version="0.1.0",
        instructions="校园课程智能助手私有工具服务：只读本人课表、检索共享资料、保存有许可的计划草稿。",
        middleware=[StrictToolArguments()],
    )

    @server.tool(
        name="get_my_schedule",
        description="读取当前身份本人课表，不允许指定目标用户。",
    )
    async def get_my_schedule(
        ctx: Context,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> ScheduleToolOutput:
        arguments: dict[str, Any] = {}
        if from_date is not None:
            arguments["from_date"] = from_date.isoformat()
        if to_date is not None:
            arguments["to_date"] = to_date.isoformat()
        return await _call_internal(
            "get_my_schedule", arguments, ctx, ScheduleToolOutput
        )

    @server.tool(
        name="search_course_docs",
        description="检索有效共享资料，空结果与依赖失败分开。",
    )
    async def search_course_docs(ctx: Context, query: QueryText) -> SearchToolOutput:
        return await _call_internal(
            "search_course_docs", {"query": query}, ctx, SearchToolOutput
        )

    @server.tool(
        name="save_study_plan",
        description="仅保存已有有效许可的指定草稿版本；许可与 operation_id 来自可信执行上下文。",
    )
    async def save_study_plan(
        ctx: Context, draft_id: DraftId, draft_version: DraftVersion
    ) -> SaveToolOutput:
        return await _call_internal(
            "save_study_plan",
            {"draft_id": draft_id, "draft_version": draft_version},
            ctx,
            SaveToolOutput,
        )

    _tighten_schemas(server)
    return server


def _strip_titles(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_titles(item)
            for key, item in value.items()
            if key not in ("title", "default")
        }
    if isinstance(value, list):
        return [_strip_titles(item) for item in value]
    return value


def _tighten_schemas(server: MCPServer) -> None:
    """把 SDK 自动生成的 input schema 收紧到契约形状（additionalProperties=false）。"""
    manager = getattr(server, "_tool_manager", None)
    tools = getattr(manager, "_tools", {}) if manager is not None else {}
    for tool in tools.values():
        schema = getattr(tool, "parameters", None)
        if not schema:
            continue
        tightened = _strip_titles(dict(schema))
        tightened["additionalProperties"] = False
        tightened.setdefault("required", [])
        tool.parameters = tightened


_server: MCPServer | None = None


def get_server() -> MCPServer:
    global _server
    if _server is None:
        _server = create_server()
    return _server


def release_server() -> None:
    """测试用：释放全局 server（其 session manager 绑定事件循环）。"""
    global _server
    _server = None


def transport_security() -> TransportSecuritySettings:
    settings = get_assistant_settings()
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[f"{settings.mcp_host}:*", "127.0.0.1:*", "localhost:*"],
        allowed_origins=[],
    )


def create_mcp_app():  # noqa: ANN201 - Starlette app
    settings = get_assistant_settings()
    return get_server().streamable_http_app(
        streamable_http_path=settings.mcp_path,
        transport_security=transport_security(),
        stateless_http=False,
    )


async def run_async() -> None:
    settings = get_assistant_settings()
    await get_server().run_streamable_http_async(
        host=settings.mcp_host,
        port=settings.mcp_port,
        streamable_http_path=settings.mcp_path,
        transport_security=transport_security(),
    )


def main() -> int:
    import asyncio

    logging.basicConfig(level=logging.INFO)
    settings = get_assistant_settings()
    logging.getLogger("cca.mcp").info(
        "MCP server listening on http://%s:%s%s",
        settings.mcp_host,
        settings.mcp_port,
        settings.mcp_path,
    )
    asyncio.run(run_async())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "MCP_PATH",
    "SERVER_NAME",
    "TOOL_PATHS",
    "TOOL_SCOPES",
    "create_mcp_app",
    "create_server",
    "get_server",
    "main",
    "release_server",
    "run_async",
    "transport_security",
]
