"""内部 API 路由（``/internal/v1``，只回环 8101；PHASE-03 A3）。

四个端点：
- ``POST /delegations/exchange``：MCP 服务身份 + ``aud=cca-mcp`` 委派 → 复核当前会话、
  enabled、auth_version、fence、scope 后签发 ``aud=cca-internal`` 受限凭据（jti 一次性）。
- ``POST /tools/get-my-schedule``：身份固定为委派用户，**不接受** student_id；完整日期范围。
- ``POST /tools/search-course-docs``：调用检索（Phase 2 合并前为固定 EvidenceSet stub）。
- ``POST /tools/save-study-plan``：服务端签发 ``direct_instruction`` 许可后按 Phase 1 统一事务保存。

不接收浏览器 Bearer；``X-Service-Credential`` 与 ``X-Execution-Context`` 缺一不可。
"""

from __future__ import annotations

import hmac
import logging
import time
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.adapters.db.models import AuthSession, ChatRequest, User
from app.adapters.db.uow import uow
from app.adapters.mcp.delegation import (
    AUD_INTERNAL,
    AUD_MCP,
    DelegationClaims,
    consume_jti,
    mint_delegation,
    verify_delegation,
)
from app.adapters.mcp.client import EXECUTION_HEADER, SERVICE_HEADER
from app.config import get_settings
from app.modules.assistant.contracts import (
    DelegationExchangeInput,
    DelegationExchangeOutput,
    ReferenceOut,
    SaveToolInput,
    SaveToolOutput,
    ScheduleItem,
    ScheduleToolInput,
    ScheduleToolOutput,
    SearchToolInput,
    SearchToolOutput,
    EvidenceChunkOut,
)
from app.modules.assistant.retrieval import search_course_docs
from app.modules.assistant.save import save_study_plan
from app.modules.assistant.schedule_tool import get_my_schedule
from app.modules.operations.service import append_audit
from app.shared.clock import isoformat, now_utc, to_db
from app.shared.api_models import ERROR_RESPONSES, Envelope, WriteOperation
from app.shared.context import ActorContext
from app.shared.errors import ApiError
from app.shared.http import envelope, request_id_of

logger = logging.getLogger("cca.assistant.internal")

router = APIRouter(tags=["internal"])

ACTIVE_STATES = ("accepted", "running")


def _require_service(request: Request) -> None:
    provided = request.headers.get(SERVICE_HEADER, "")
    expected = get_settings().service_token
    if not provided:
        raise ApiError("AUTH_REQUIRED", message="缺少服务凭据")
    if not hmac.compare_digest(provided, expected):
        raise ApiError("FORBIDDEN", message="服务凭据无效")


async def _validate_execution(
    claims: DelegationClaims, *, required_scope: str | None = None
) -> tuple[User, ChatRequest]:
    """每次调用都复核当前会话 / enabled / auth_version / fence / scope。"""
    if required_scope is not None and not claims.has_scope(required_scope):
        raise ApiError("FORBIDDEN", message="委派范围不足")
    now = to_db(now_utc())
    async with uow() as tx:
        user = await tx.session.get(User, claims.sub)
        session = await tx.session.get(AuthSession, claims.session_id)
        chat = await tx.session.get(ChatRequest, claims.request_id)
    if user is None or not bool(user.enabled):
        raise ApiError("SESSION_EXPIRED")
    if int(user.auth_version) != int(claims.auth_version):
        raise ApiError("SESSION_EXPIRED")
    if (
        session is None
        or session.user_id != claims.sub
        or session.revoked_at is not None
        or session.expires_at <= now
        or int(session.auth_version) != int(claims.auth_version)
    ):
        raise ApiError("SESSION_EXPIRED")
    if (
        chat is None
        or chat.user_id != claims.sub
        or chat.session_id != claims.session_id
        or chat.conversation_id != claims.conversation_id
    ):
        raise ApiError("FORBIDDEN")
    if int(chat.fence) != int(claims.fence):
        raise ApiError("FORBIDDEN", message="执行代次已失效")
    if chat.cancel_requested:
        # 用已登记码（IF-010 同码同义）：本轮已取消 → 工具调用无权继续。
        # 原实现抛的 "CANCELLED" 不在 ERROR_STATUS / 契约 enum，message 会回落
        # 成「服务内部错误」，且经 MCP 直通出去（审计 P1）。
        raise ApiError("FORBIDDEN", message="本轮已取消")
    if chat.state not in ACTIVE_STATES:
        raise ApiError("FORBIDDEN", message="本轮已结束")
    if chat.deadline_at is not None and chat.deadline_at <= now:
        raise ApiError("EXECUTION_TIMEOUT")
    return user, chat


def _actor(claims: DelegationClaims, user: User) -> ActorContext:
    return ActorContext(
        user_id=user.id,
        session_id=claims.session_id,
        auth_version=int(user.auth_version),
        role=user.role,  # type: ignore[arg-type]
        trace_request_id=claims.request_id,
        account=user.account,
        display_name=user.display_name,
        user_version=int(user.version),
        enabled=bool(user.enabled),
    )


async def _audit_tool(
    *,
    claims: DelegationClaims,
    action: str,
    object_id: str | None,
    result: str,
    request_id: str,
    duration_ms: int,
) -> None:
    try:
        async with uow() as tx:
            append_audit(
                tx,
                action=action,
                object_type="chat_request",
                object_id=object_id,
                result=result,
                request_id=request_id,
                actor_id=claims.sub,
                duration_ms=duration_ms,
                metadata={"tool": action, "scope": list(claims.scope)},
            )
            await tx.commit()
    except Exception:  # noqa: BLE001 - 审计失败不改变业务结果
        logger.exception("tool audit failed action=%s", action)


# --------------------------------------------------------------------------- #
# 1. 委派兑换
# --------------------------------------------------------------------------- #
@router.post(
    "/delegations/exchange",
    operation_id="exchangeDelegation",
    responses=ERROR_RESPONSES,
    response_model=Envelope[DelegationExchangeOutput],
)
async def exchange_delegation(request: Request, body: DelegationExchangeInput):
    _require_service(request)
    claims = verify_delegation(body.delegation, expected_audience=AUD_MCP)
    if not await consume_jti(claims.jti, expires_at=float(claims.exp)):
        raise ApiError("AUTH_REQUIRED", message="委派凭据已被使用")
    _user, chat = await _validate_execution(claims)
    deadline_at = min(
        claims.expires_at,
        chat.deadline_at.replace(tzinfo=now_utc().tzinfo)
        if chat.deadline_at is not None
        else claims.expires_at,
    )
    internal_token = mint_delegation(
        audience=AUD_INTERNAL,
        user_id=claims.sub,
        session_id=claims.session_id,
        auth_version=claims.auth_version,
        request_id=claims.request_id,
        conversation_id=claims.conversation_id,
        scope=list(claims.scope),
        fence=claims.fence,
        deadline_at=deadline_at,
    )
    internal_claims = verify_delegation(internal_token, expected_audience=AUD_INTERNAL)
    output = DelegationExchangeOutput(
        delegation=internal_token,
        audience="cca-internal",
        expires_at=isoformat(internal_claims.expires_at) or "",
    )
    return envelope(request, output.model_dump(mode="json", exclude_none=True))


# --------------------------------------------------------------------------- #
# 2. 三工具
# --------------------------------------------------------------------------- #
@router.post(
    "/tools/get-my-schedule",
    operation_id="internalSchedule",
    responses=ERROR_RESPONSES,
    response_model=Envelope[ScheduleToolOutput],
)
async def internal_schedule(request: Request, body: ScheduleToolInput):
    _require_service(request)
    claims = verify_delegation(
        request.headers.get(EXECUTION_HEADER, ""),
        expected_audience=AUD_INTERNAL,
        required_scope="schedule:read",
    )
    if not await consume_jti(claims.jti, expires_at=float(claims.exp)):
        raise ApiError("AUTH_REQUIRED", message="执行凭据已被使用")
    user, _chat = await _validate_execution(claims, required_scope="schedule:read")
    started = time.perf_counter()
    try:
        data = await get_my_schedule(_actor(claims, user), body.from_date, body.to_date)
    except ApiError as exc:
        await _audit_tool(
            claims=claims,
            action="tool.get_my_schedule",
            object_id=claims.request_id,
            result=exc.code,
            request_id=request_id_of(request),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        raise
    output = ScheduleToolOutput(
        status=data["status"],
        from_date=data["from_date"],
        to_date=data["to_date"],
        school_timezone=data["school_timezone"],
        items=[ScheduleItem(**item) for item in data["items"]],
    )
    await _audit_tool(
        claims=claims,
        action="tool.get_my_schedule",
        object_id=claims.request_id,
        result=output.status,
        request_id=request_id_of(request),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return envelope(request, output.model_dump(mode="json", exclude_none=True))


@router.post(
    "/tools/search-course-docs",
    operation_id="internalSearch",
    responses=ERROR_RESPONSES,
    response_model=Envelope[SearchToolOutput],
)
async def internal_search(request: Request, body: SearchToolInput):
    _require_service(request)
    claims = verify_delegation(
        request.headers.get(EXECUTION_HEADER, ""),
        expected_audience=AUD_INTERNAL,
        required_scope="docs:search",
    )
    if not await consume_jti(claims.jti, expires_at=float(claims.exp)):
        raise ApiError("AUTH_REQUIRED", message="执行凭据已被使用")
    user, _chat = await _validate_execution(claims, required_scope="docs:search")
    started = time.perf_counter()
    try:
        evidence = await search_course_docs(_actor(claims, user), body.query)
    except ApiError as exc:
        await _audit_tool(
            claims=claims,
            action="tool.search_course_docs",
            object_id=claims.request_id,
            result=exc.code,
            request_id=request_id_of(request),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        raise
    output = SearchToolOutput(
        status=evidence.status,
        corpus_empty=evidence.corpus_empty,
        revision=evidence.revision,
        chunks=[
            EvidenceChunkOut(
                chunk_id=chunk.chunk_id,
                reference_id=chunk.reference_id,
                document_id=chunk.document_id,
                version_id=chunk.version_id,
                text=chunk.text[:20_000],
                location_label=chunk.location_label,
                **({"page_number": chunk.page_number} if chunk.page_number is not None else {}),
            )
            for chunk in evidence.chunks
        ],
        references=[
            ReferenceOut(
                reference_id=reference.reference_id,
                document_id=reference.document_id,
                version_id=reference.version_id,
                file_name=reference.file_name,
                location_label=reference.location_label,
                **(
                    {"page_number": reference.page_number}
                    if reference.page_number is not None
                    else {}
                ),
            )
            for reference in evidence.references
        ],
    )
    await _audit_tool(
        claims=claims,
        action="tool.search_course_docs",
        object_id=claims.request_id,
        result=output.status,
        request_id=request_id_of(request),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return envelope(request, output.model_dump(mode="json", exclude_none=True))


@router.post(
    "/tools/save-study-plan",
    operation_id="internalSave",
    responses={
        **ERROR_RESPONSES,
        202: {
            "model": Envelope[WriteOperation],
            "description": "提交结果待核实，不能解释为创建成功",
        },
    },
    response_model=Envelope[SaveToolOutput],
)
async def internal_save(request: Request, body: SaveToolInput):
    _require_service(request)
    claims = verify_delegation(
        request.headers.get(EXECUTION_HEADER, ""),
        expected_audience=AUD_INTERNAL,
        required_scope="plan:save",
    )
    if not await consume_jti(claims.jti, expires_at=float(claims.exp)):
        raise ApiError("AUTH_REQUIRED", message="执行凭据已被使用")
    await _validate_execution(claims, required_scope="plan:save")
    started = time.perf_counter()
    try:
        data = await save_study_plan(
            claims,
            draft_id=body.draft_id,
            draft_version=body.draft_version,
            request_id=request_id_of(request),
        )
    except ApiError as exc:
        await _audit_tool(
            claims=claims,
            action="tool.save_study_plan",
            object_id=body.draft_id,
            result=exc.code,
            request_id=request_id_of(request),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        raise
    output = SaveToolOutput(
        status=data["status"],
        operation_id=data["operation_id"],
        plan_id=data["plan_id"],
    )
    await _audit_tool(
        claims=claims,
        action="tool.save_study_plan",
        object_id=body.draft_id,
        result=output.status,
        request_id=request_id_of(request),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return envelope(request, output.model_dump(mode="json", exclude_none=True))


__all__ = ["router"]
