"""对话内保存（``save_study_plan``）的服务端实现（设计 §7.2–§7.3；PHASE-03 A8）。

要点：
- **许可只由服务端签发**：``direct_instruction`` 许可绑定用户 / 会话 / 授权轮 /
  来源轮 / 草稿版本 / 内容摘要；工具与模型不能创建或修改许可。
- 事务与锁顺序（§5.2）：users → chat_requests（按 ID）→ plan_drafts →
  plan_draft_versions → write_operations → save_grants → assistant_save_slots → study_plans。
- 同轮创建上限：来源轮与授权轮（若是另一轮）各最多一份 ``assistant_save_slots``；
  同一 ID 只占一次；换 operation 键不能绕过。
- 取消竞态：锁内看到本授权轮 ``cancel_requested`` 或已非运行态 → 保存失败、零新增。
- 幂等：``(user_id, operation_id)`` 唯一；同键同摘要 → ``existing``；同键异摘要 → 409。
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.adapters.db.models import (
    AssistantSaveSlot,
    ChatRequest,
    PlanDraft,
    PlanDraftVersion,
    SaveGrant,
    StudyPlan,
    WriteOperation,
)
from app.adapters.db.uow import uow
from app.adapters.mcp.delegation import DelegationClaims
from app.config import get_settings
from app.modules.operations.service import append_audit, append_outbox
from app.modules.planning.schemas import validate_plan_payload
from app.shared.clock import from_db, now_utc, to_db
from app.shared.errors import ApiError, map_integrity_error
from app.shared.ids import PREFIX_GRANT, PREFIX_PLAN, new_id
from app.shared.payload import (
    basis_snapshot_from_payload,
    normalize_plan_payload,
    plan_payload_digest,
)

logger = logging.getLogger("cca.assistant.save")

SAVE_SOURCE = "assistant"
SAVE_KIND = "direct_instruction"


def _now_db():
    return to_db(now_utc())


def _final_result(operation: WriteOperation) -> dict[str, Any] | None:
    if operation.state in ("succeeded", "deleted"):
        return {
            "status": "existing",
            "operation_id": operation.operation_id,
            "plan_id": operation.plan_id,
        }
    return None


def _validate_user_row(user: Any, claims: DelegationClaims) -> Any:
    """锁内复核 enabled / auth_version（与 Phase 1 F-01 同一不变量，§5.1）。"""
    if (
        user is None
        or not bool(user.enabled)
        or int(user.auth_version) != int(claims.auth_version)
    ):
        raise ApiError("SESSION_EXPIRED")
    return user


def _insert_plan(tx: Any, *, user_id: str, operation_id: str, payload: dict[str, Any]) -> StudyPlan:
    from datetime import date

    normalized = normalize_plan_payload(payload)
    plan = StudyPlan(
        id=new_id(PREFIX_PLAN),
        user_id=user_id,
        operation_id=operation_id,
        title=normalized["title"].strip(),
        goal=normalized["goal"],
        start_date=(
            date.fromisoformat(normalized["start_date"]) if normalized["start_date"] else None
        ),
        end_date=date.fromisoformat(normalized["end_date"]) if normalized["end_date"] else None,
        content=normalized["content"],
        source=SAVE_SOURCE,
        basis_snapshot=basis_snapshot_from_payload(normalized),
        version=1,
        deleted_at=None,
        created_at=_now_db(),
        updated_at=_now_db(),
    )
    tx.session.add(plan)
    return plan


async def save_study_plan(
    claims: DelegationClaims,
    *,
    draft_id: str,
    draft_version: int,
    request_id: str,
) -> dict[str, Any]:
    """以 ``direct_instruction`` 许可保存指定草稿版本；返回 created/existing。"""
    # ---- 1) 非锁定读取绑定（归属 + 预分配操作键 + 摘要）----
    async with uow() as tx:
        draft = await tx.session.get(PlanDraft, draft_id)
        if draft is None or draft.user_id != claims.sub:
            raise ApiError("RESOURCE_NOT_FOUND")
        version = await tx.session.get(PlanDraftVersion, (draft_id, int(draft_version)))
    if draft.session_id != claims.session_id:
        raise ApiError("SAVE_NOT_AUTHORIZED")
    if version is None or version.payload is None:
        raise ApiError("DRAFT_EXPIRED")
    operation_id = version.operation_id
    digest = version.content_digest
    origin_request_id = draft.origin_chat_request_id
    if claims.request_id not in (origin_request_id,):
        # 授权轮就是当前执行轮；本阶段的保存只发生在对话执行轮内部
        auth_request_id = claims.request_id
    else:
        auth_request_id = claims.request_id
    request_ids = sorted({origin_request_id, auth_request_id})

    now = _now_db()
    if draft.expires_at <= now:
        raise ApiError("DRAFT_EXPIRED")
    if int(draft.current_version) != int(draft_version):
        raise ApiError("SAVE_NOT_AUTHORIZED")

    # ---- 2) pending 意图（唯一键收敛并发；独立短事务）----
    existing = await _ensure_pending_intent(
        claims,
        operation_id=operation_id,
        digest=digest,
        draft_id=draft_id,
        draft_version=int(draft_version),
        origin_request_id=origin_request_id,
        authorization_request_id=auth_request_id,
    )
    if existing is not None:
        return existing

    # ---- 3) 最终事务（锁顺序严格按 §5.2）----
    plan_id: str | None = None
    try:
        async with uow() as tx:
            _validate_user_row(await tx.lock_user(claims.sub), claims)
            requests = await tx.lock_chat_requests(request_ids)
            await _validate_execution_requests(requests, claims, request_ids)

            draft_row = await tx.lock_draft(draft_id)
            version_row = await tx.lock_draft_version(draft_id, int(draft_version))
            operation = await tx.lock_operation(claims.sub, operation_id)
            if operation is None:
                raise ApiError("INTERNAL_ERROR")
            final = _final_result(operation)
            if final is not None:
                return final
            if operation.content_digest != digest:
                raise ApiError("IDEMPOTENCY_CONFLICT")
            if operation.source != SAVE_SOURCE:
                raise ApiError("IDEMPOTENCY_CONFLICT")

            if draft_row is None or draft_row.user_id != claims.sub:
                raise ApiError("RESOURCE_NOT_FOUND")
            if draft_row.session_id != claims.session_id:
                raise ApiError("SAVE_NOT_AUTHORIZED")
            if draft_row.expires_at <= _now_db():
                raise ApiError("DRAFT_EXPIRED")
            if version_row is None or version_row.payload is None:
                raise ApiError("DRAFT_EXPIRED")
            if int(draft_row.current_version) != int(draft_version):
                raise ApiError("SAVE_NOT_AUTHORIZED")

            # 同轮保存槽：来源轮 + 授权轮各最多一份，且绑定同一操作
            slots = await _lock_save_slots(tx, claims.sub, request_ids)
            for slot in slots:
                if slot.operation_id != operation_id:
                    raise ApiError("SAVE_LIMIT_REACHED")

            grant = await _issue_or_lock_grant(
                tx,
                claims,
                operation_id=operation_id,
                digest=digest,
                draft_id=draft_id,
                draft_version=int(draft_version),
                authorization_request_id=auth_request_id,
                trace_request_id=request_id,
                now=now,
            )

            payload = dict(version_row.payload)
            validate_plan_payload(payload)
            plan = _insert_plan(tx, user_id=claims.sub, operation_id=operation_id, payload=payload)
            await tx.session.flush()
            plan_id = plan.id

            for request_id_value in request_ids:
                if any(slot.request_id == request_id_value for slot in slots):
                    continue
                tx.session.add(
                    AssistantSaveSlot(
                        user_id=claims.sub,
                        request_id=request_id_value,
                        operation_id=operation_id,
                        plan_id=plan.id,
                        created_at=_now_db(),
                    )
                )

            grant.state = "consumed"
            grant.consumed_at = _now_db()
            operation.state = "succeeded"
            operation.plan_id = plan.id
            operation.resolution = "confirmed"
            operation.retryable = False
            operation.updated_at = _now_db()

            from app.modules.assistant.drafts import attach_plan_to_requests

            await attach_plan_to_requests(
                tx, request_ids, plan_id=plan.id, operation_id=operation_id
            )
            append_audit(
                tx,
                action="assistant.plan_saved",
                object_type="study_plan",
                object_id=plan.id,
                result="success",
                request_id=request_id,
                actor_id=claims.sub,
                metadata={
                    "source": SAVE_SOURCE,
                    "authorization_kind": SAVE_KIND,
                    "draft_id": draft_id,
                    "draft_version": int(draft_version),
                },
            )
            append_outbox(
                tx,
                event_type="plan_saved",
                aggregate_id=plan.id,
                request_id=request_id,
                metadata={
                    "plan_id": plan.id,
                    "operation_id": operation_id,
                    "draft_id": draft_id,
                    "draft_version": int(draft_version),
                    "source": SAVE_SOURCE,
                },
            )
            await tx.commit()
    except IntegrityError as exc:
        mapped = map_integrity_error(exc)
        async with uow() as tx2:
            operation = await tx2.session.get(WriteOperation, (claims.sub, operation_id))
        if operation is not None:
            final = _final_result(operation)
            if final is not None:
                return final
        raise (mapped or ApiError("INTERNAL_ERROR")) from None

    return {"status": "created", "operation_id": operation_id, "plan_id": plan_id}


async def _ensure_pending_intent(
    claims: DelegationClaims,
    *,
    operation_id: str,
    digest: bytes,
    draft_id: str,
    draft_version: int,
    origin_request_id: str,
    authorization_request_id: str,
) -> dict[str, Any] | None:
    """建立 pending 意图（唯一键收敛并发）；已终结返回既有结果。"""
    now = _now_db()
    async with uow() as tx:
        _validate_user_row(await tx.lock_user(claims.sub), claims)
        operation = await tx.lock_operation(claims.sub, operation_id)
        if operation is not None:
            if operation.content_digest != digest:
                raise ApiError("IDEMPOTENCY_CONFLICT")
            return _final_result(operation)
        operation = WriteOperation(
            user_id=claims.sub,
            operation_id=operation_id,
            source=SAVE_SOURCE,
            origin_chat_request_id=origin_request_id,
            authorization_chat_request_id=authorization_request_id,
            draft_id=draft_id,
            draft_version=int(draft_version),
            content_digest=digest,
            state="pending",
            resolution="recovering",
            plan_id=None,
            error_code=None,
            retryable=False,
            created_at=now,
            updated_at=now,
        )
        tx.session.add(operation)
        try:
            await tx.session.flush()
            await tx.commit()
        except IntegrityError as exc:
            await tx.rollback()
            async with uow() as tx2:
                row = await tx2.session.get(WriteOperation, (claims.sub, operation_id))
            if row is None:
                raise ApiError("INTERNAL_ERROR") from exc
            if row.content_digest != digest:
                raise ApiError("IDEMPOTENCY_CONFLICT") from exc
            return _final_result(row)
    return None


async def _validate_execution_requests(
    requests: dict[str, Any],
    claims: DelegationClaims,
    request_ids: list[str],
) -> None:
    """锁内复核：归属 / 运行态 / fence / 取消 / 截止（取消先提交则保存失败）。"""
    now = _now_db()
    for request_id in request_ids:
        row = requests.get(request_id)
        if row is None or row.user_id != claims.sub:
            raise ApiError("RESOURCE_NOT_FOUND")
    current = requests.get(claims.request_id)
    if current is None:
        raise ApiError("RESOURCE_NOT_FOUND")
    if current.session_id != claims.session_id:
        raise ApiError("SAVE_NOT_AUTHORIZED")
    if int(current.fence) != int(claims.fence):
        raise ApiError("SAVE_NOT_AUTHORIZED")
    if bool(current.cancel_requested):
        raise ApiError("SAVE_NOT_AUTHORIZED")
    if current.state not in ("accepted", "running"):
        raise ApiError("SAVE_NOT_AUTHORIZED")
    if current.deadline_at is not None and current.deadline_at <= now:
        raise ApiError("EXECUTION_TIMEOUT")
    # 保存许可的语义前置（SRS FR-PLAN-003 / 详细设计 §7.1）：
    # 只有服务端对本轮用户原文明确定为 explicit 才允许写入；模型/调用方都不能声明。
    if str(getattr(current, "instruction_class", "") or "") != "explicit":
        raise ApiError("SAVE_NOT_AUTHORIZED", message="保存许可不成立：缺少本轮明确保存指令")


async def _lock_save_slots(
    tx: Any, user_id: str, request_ids: list[str]
) -> list[AssistantSaveSlot]:
    result = await tx.session.execute(
        select(AssistantSaveSlot)
        .where(
            AssistantSaveSlot.user_id == user_id,
            AssistantSaveSlot.request_id.in_(request_ids),
        )
        .order_by(AssistantSaveSlot.request_id)
        .with_for_update()
    )
    return list(result.scalars().all())


async def _issue_or_lock_grant(
    tx: Any,
    claims: DelegationClaims,
    *,
    operation_id: str,
    digest: bytes,
    draft_id: str,
    draft_version: int,
    authorization_request_id: str,
    trace_request_id: str,
    now: Any,
) -> SaveGrant:
    grants = await tx.lock_grants_for_operation(claims.sub, operation_id)
    grant = next((item for item in grants if item.content_digest == digest), None)
    if grant is not None:
        if grant.state == "consumed":
            raise ApiError("SAVE_NOT_AUTHORIZED")
        if grant.state != "issued":
            raise ApiError("SAVE_NOT_AUTHORIZED")
        if grant.expires_at <= _now_db():
            raise ApiError("SAVE_NOT_AUTHORIZED")
        if grant.session_id != claims.session_id:
            raise ApiError("SAVE_NOT_AUTHORIZED")
        if grant.authorization_kind != SAVE_KIND:
            raise ApiError("SAVE_NOT_AUTHORIZED")
        return grant
    grant = SaveGrant(
        id=new_id(PREFIX_GRANT),
        user_id=claims.sub,
        session_id=claims.session_id,
        trace_request_id=trace_request_id,
        authorization_kind=SAVE_KIND,
        authorization_chat_request_id=authorization_request_id,
        draft_id=draft_id,
        draft_version=int(draft_version),
        operation_id=operation_id,
        content_digest=digest,
        state="issued",
        expires_at=to_db(
            from_db(now) + timedelta(seconds=get_settings().draft_ttl_seconds)
        ),
        created_at=_now_db(),
        consumed_at=None,
    )
    tx.session.add(grant)
    return grant


__all__ = ["save_study_plan"]
