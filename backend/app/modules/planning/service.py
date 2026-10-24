"""计划、草稿、保存与写入状态（设计 §7）。

核心约束：
- 幂等：``(user_id, operation_id)`` 唯一；同键同摘要 → 200 existing/deleted，同键异摘要 → 409。
- 保存事务顺序：锁用户 → 锁对话/请求 → 锁草稿头与版本 → 锁操作 → 校验许可/当前版/过期 →
  槽位唯一 → 插入计划 → 消费许可 → 操作成功 → 审计/Outbox 同事务。
- 权限：所有查询先限定归属再取记录；跨用户一律 404 不泄露存在性。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.adapters.db.models import (
    AssistantSaveSlot,
    PlanDraft,
    PlanDraftVersion,
    SaveGrant,
    StudyPlan,
    WriteOperation,
)
from app.adapters.db.uow import UoW, uow
from app.config import get_settings
from app.modules.operations.service import append_audit, append_outbox
from app.modules.planning.schemas import (
    DraftPatch,
    PlanCreate,
    PlanPatch,
    draft_view,
    plan_view,
    validate_plan_payload,
)
from app.shared.clock import isoformat, now_utc, to_db
from app.shared.errors import ApiError, map_integrity_error, validation_error
from app.shared.ids import (
    PREFIX_DRAFT_OPERATION,
    PREFIX_GRANT,
    PREFIX_PLAN,
    new_id,
)
from app.shared.payload import (
    basis_snapshot_from_payload,
    normalize_plan_payload,
    payload_from_row,
    plan_payload_digest,
)


# --------------------------------------------------------------------------- #
# 通用工具
# --------------------------------------------------------------------------- #
def _now_db():
    return to_db(now_utc())


def _operation_final_result(operation: WriteOperation) -> dict[str, Any] | None:
    if operation.state == "succeeded":
        return {
            "status": "existing",
            "operation_id": operation.operation_id,
            "plan_id": operation.plan_id,
        }
    if operation.state == "deleted":
        return {
            "status": "deleted",
            "operation_id": operation.operation_id,
            "plan_id": operation.plan_id,
        }
    return None


async def _ensure_pending_intent(
    actor: Any,
    *,
    operation_id: str,
    digest: bytes,
    source: str,
    draft_id: str | None = None,
    draft_version: int | None = None,
    origin_chat_request_id: str | None = None,
) -> WriteOperation | None:
    """建立 pending 意图（独立短事务，唯一键收敛并发）；已终结则返回原操作。"""
    now = _now_db()
    async with uow() as tx:
        await tx.lock_and_validate_actor(actor)
        operation = await tx.lock_operation(actor.user_id, operation_id)
        if operation is not None:
            if operation.content_digest != digest:
                raise ApiError("IDEMPOTENCY_CONFLICT")
            return operation if _operation_final_result(operation) else None
        operation = WriteOperation(
            user_id=actor.user_id,
            operation_id=operation_id,
            source=source,
            origin_chat_request_id=origin_chat_request_id,
            authorization_chat_request_id=None,
            draft_id=draft_id,
            draft_version=draft_version,
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
        except IntegrityError:
            await tx.rollback()
            async with uow() as tx2:
                existing = await tx2.session.get(
                    WriteOperation, (actor.user_id, operation_id)
                )
            if existing is None:
                raise ApiError("INTERNAL_ERROR") from None
            if existing.content_digest != digest:
                raise ApiError("IDEMPOTENCY_CONFLICT") from None
            return existing if _operation_final_result(existing) else None
    return None


def _insert_plan(
    tx: UoW,
    actor: Any,
    *,
    operation_id: str,
    payload: Mapping[str, Any],
    source: str,
) -> StudyPlan:
    now = _now_db()
    normalized = normalize_plan_payload(payload)
    plan = StudyPlan(
        id=new_id(PREFIX_PLAN),
        user_id=actor.user_id,
        operation_id=operation_id,
        title=normalized["title"].strip(),
        goal=normalized["goal"],
        start_date=(
            date.fromisoformat(normalized["start_date"])
            if normalized["start_date"]
            else None
        ),
        end_date=(
            date.fromisoformat(normalized["end_date"]) if normalized["end_date"] else None
        ),
        content=normalized["content"],
        source=source,
        basis_snapshot=basis_snapshot_from_payload(normalized),
        version=1,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    tx.session.add(plan)
    return plan


def _result_payload(operation: WriteOperation) -> dict[str, Any]:
    return {
        "status": "existing" if operation.state == "succeeded" else "deleted",
        "operation_id": operation.operation_id,
        "plan_id": operation.plan_id,
    }


# --------------------------------------------------------------------------- #
# 计划：手动创建 / 查询 / 更新 / 删除
# --------------------------------------------------------------------------- #
async def list_plans(
    actor: Any, *, page: int, page_size: int, title: str | None
) -> dict[str, Any]:
    conditions = [
        StudyPlan.user_id == actor.user_id,
        StudyPlan.deleted_at.is_(None),
    ]
    if title:
        conditions.append(StudyPlan.title.contains(title, autoescape=True))
    async with uow() as tx:
        total = await tx.session.scalar(
            select(func.count()).select_from(StudyPlan).where(*conditions)
        )
        result = await tx.session.execute(
            select(StudyPlan)
            .where(*conditions)
            .order_by(StudyPlan.updated_at.desc(), StudyPlan.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list(result.scalars().all())
    return {
        "items": [plan_view(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": int(total or 0),
    }


async def get_plan(actor: Any, plan_id: str) -> dict[str, Any]:
    async with uow() as tx:
        result = await tx.session.execute(
            select(StudyPlan).where(
                StudyPlan.id == plan_id,
                StudyPlan.user_id == actor.user_id,
                StudyPlan.deleted_at.is_(None),
            )
        )
        plan = result.scalar_one_or_none()
    if plan is None:
        raise ApiError("RESOURCE_NOT_FOUND")
    return plan_view(plan)


async def create_plan_manual(
    actor: Any, body: PlanCreate, idempotency_key: str, request_id: str
) -> tuple[int, dict[str, Any]]:
    payload = normalize_plan_payload(
        {
            "title": body.title.strip(),
            "goal": body.goal,
            "start_date": body.start_date,
            "end_date": body.end_date,
            "content": body.content,
            "basis_types": ["general"],
            "references": [],
        }
    )
    validate_plan_payload(payload)
    digest = plan_payload_digest(payload)

    final = await _ensure_pending_intent(
        actor, operation_id=idempotency_key, digest=digest, source="manual"
    )
    if final is not None:
        return 200, _result_payload(final)

    try:
        async with uow() as tx:
            await tx.lock_and_validate_actor(actor)
            operation = await tx.lock_operation(actor.user_id, idempotency_key)
            if operation is None:
                raise ApiError("INTERNAL_ERROR")
            if _operation_final_result(operation) is not None:
                return 200, _result_payload(operation)
            if operation.content_digest != digest:
                raise ApiError("IDEMPOTENCY_CONFLICT")
            plan = _insert_plan(
                tx,
                actor,
                operation_id=idempotency_key,
                payload=payload,
                source="manual",
            )
            await tx.session.flush()
            now = _now_db()
            operation.state = "succeeded"
            operation.plan_id = plan.id
            operation.resolution = "confirmed"
            operation.retryable = False
            operation.updated_at = now
            append_audit(
                tx,
                action="plan_saved",
                object_type="study_plan",
                object_id=plan.id,
                result="success",
                request_id=request_id,
                actor_id=actor.user_id,
                metadata={"source": "manual"},
            )
            append_outbox(
                tx,
                event_type="plan_saved",
                aggregate_id=plan.id,
                request_id=request_id,
                metadata={"plan_id": plan.id, "operation_id": idempotency_key},
            )
            await tx.commit()
    except IntegrityError as exc:
        mapped = map_integrity_error(exc)
        if mapped is not None and mapped.code in ("IDEMPOTENCY_CONFLICT", "INTERNAL_ERROR"):
            async with uow() as tx2:
                operation = await tx2.session.get(
                    WriteOperation, (actor.user_id, idempotency_key)
                )
            if operation is not None and _operation_final_result(operation):
                return 200, _result_payload(operation)
        raise (mapped or ApiError("INTERNAL_ERROR")) from None

    return 201, {
        "status": "created",
        "operation_id": idempotency_key,
        "plan_id": plan.id,
    }


async def patch_plan(
    actor: Any, plan_id: str, body: PlanPatch, request_id: str
) -> dict[str, Any]:
    now = _now_db()
    async with uow() as tx:
        await tx.lock_and_validate_actor(actor)
        plan = await tx.lock_plan(plan_id, actor.user_id)
        if plan is None or plan.deleted_at is not None:
            raise ApiError("RESOURCE_NOT_FOUND")
        if int(plan.version) != body.expected_version:
            raise ApiError("VERSION_CONFLICT")

        payload = payload_from_row(
            title=plan.title,
            goal=plan.goal,
            start_date=plan.start_date,
            end_date=plan.end_date,
            content=plan.content,
            basis_snapshot=plan.basis_snapshot,
        )
        provided = body.model_fields_set
        if "title" in provided and body.title is not None:
            payload["title"] = body.title.strip()
        if "goal" in provided:
            payload["goal"] = body.goal
        if "start_date" in provided:
            payload["start_date"] = body.start_date.isoformat() if body.start_date else None
        if "end_date" in provided:
            payload["end_date"] = body.end_date.isoformat() if body.end_date else None
        if "content" in provided and body.content is not None:
            payload["content"] = body.content
        validate_plan_payload(payload)

        normalized = normalize_plan_payload(payload)
        plan.title = normalized["title"].strip()
        plan.goal = normalized["goal"]
        plan.start_date = (
            date.fromisoformat(normalized["start_date"]) if normalized["start_date"] else None
        )
        plan.end_date = (
            date.fromisoformat(normalized["end_date"]) if normalized["end_date"] else None
        )
        plan.content = normalized["content"]
        plan.basis_snapshot = basis_snapshot_from_payload(normalized)
        plan.version = int(plan.version) + 1
        plan.updated_at = now
        await tx.session.flush()
        append_audit(
            tx,
            action="plan.patch",
            object_type="study_plan",
            object_id=plan.id,
            result="success",
            request_id=request_id,
            actor_id=actor.user_id,
            metadata={"fields": sorted(provided.intersection({"title", "goal", "start_date", "end_date", "content"}))},
        )
        await tx.commit()
    return plan_view(plan)


async def delete_plan(
    actor: Any, plan_id: str, expected_version: int, request_id: str
) -> dict[str, Any]:
    now = _now_db()
    async with uow() as tx:
        await tx.lock_and_validate_actor(actor)
        plan = await tx.lock_plan(plan_id, actor.user_id)
        if plan is None or plan.deleted_at is not None:
            raise ApiError("RESOURCE_NOT_FOUND")
        if int(plan.version) != expected_version:
            raise ApiError("VERSION_CONFLICT")
        operation = await tx.lock_operation(actor.user_id, plan.operation_id)
        # 清空正文与依据快照，保留墓碑与操作记录（FR-PLAN-005 / 设计 §7.4）
        plan.title = None
        plan.goal = None
        plan.start_date = None
        plan.end_date = None
        plan.content = None
        plan.basis_snapshot = None
        plan.deleted_at = now
        plan.version = int(plan.version) + 1
        plan.updated_at = now
        if operation is not None:
            operation.state = "deleted"
            operation.resolution = "confirmed"
            operation.updated_at = now
        await tx.session.flush()
        append_audit(
            tx,
            action="plan.delete",
            object_type="study_plan",
            object_id=plan_id,
            result="success",
            request_id=request_id,
            actor_id=actor.user_id,
        )
        await tx.commit()
        new_version = int(plan.version)
    return {"deleted": True, "plan_id": plan_id, "version": new_version}


# --------------------------------------------------------------------------- #
# 草稿
# --------------------------------------------------------------------------- #
async def get_draft(actor: Any, draft_id: str) -> dict[str, Any]:
    now = _now_db()
    async with uow() as tx:
        draft = await tx.session.get(PlanDraft, draft_id)
        if (
            draft is None
            or draft.user_id != actor.user_id
            or draft.session_id != actor.session_id
        ):
            raise ApiError("RESOURCE_NOT_FOUND")
        if draft.expires_at <= now:
            raise ApiError("DRAFT_EXPIRED")
        version = await tx.session.get(
            PlanDraftVersion, (draft_id, int(draft.current_version))
        )
    if version is None or version.payload is None:
        raise ApiError("DRAFT_EXPIRED")
    return draft_view(draft, version, version.payload)


async def revise_draft(
    actor: Any, draft_id: str, body: DraftPatch, request_id: str
) -> dict[str, Any]:
    now = _now_db()
    async with uow() as tx:
        await tx.lock_and_validate_actor(actor)
        draft = await tx.lock_draft(draft_id)
        if (
            draft is None
            or draft.user_id != actor.user_id
            or draft.session_id != actor.session_id
        ):
            raise ApiError("RESOURCE_NOT_FOUND")
        if draft.expires_at <= now:
            raise ApiError("DRAFT_EXPIRED")
        current = await tx.lock_draft_version(draft_id, int(draft.current_version))
        if current is None or current.payload is None:
            raise ApiError("DRAFT_EXPIRED")
        if int(draft.current_version) != body.expected_draft_version:
            raise ApiError("VERSION_CONFLICT")

        payload = normalize_plan_payload(current.payload)
        provided = body.model_fields_set
        if "title" in provided and body.title is not None:
            payload["title"] = body.title.strip()
        if "goal" in provided:
            payload["goal"] = body.goal
        if "start_date" in provided:
            payload["start_date"] = body.start_date.isoformat() if body.start_date else None
        if "end_date" in provided:
            payload["end_date"] = body.end_date.isoformat() if body.end_date else None
        if "content" in provided and body.content is not None:
            payload["content"] = body.content
        validate_plan_payload(payload)
        payload = normalize_plan_payload(payload)

        new_version_no = int(draft.current_version) + 1
        version = PlanDraftVersion(
            draft_id=draft_id,
            draft_version=new_version_no,
            operation_id=new_id(PREFIX_DRAFT_OPERATION),
            schema_version=1,
            payload=payload,
            content_digest=plan_payload_digest(payload),
            created_at=now,
            payload_cleared_at=None,
        )
        tx.session.add(version)
        # 新版本撤销旧版未消费许可
        from sqlalchemy import update as sa_update

        await tx.session.execute(
            sa_update(SaveGrant)
            .where(
                SaveGrant.user_id == actor.user_id,
                SaveGrant.draft_id == draft_id,
                SaveGrant.state == "issued",
            )
            .values(state="revoked")
        )
        draft.current_version = new_version_no
        draft.updated_at = now
        await tx.session.flush()
        append_audit(
            tx,
            action="draft.revise",
            object_type="plan_draft",
            object_id=draft_id,
            result="success",
            request_id=request_id,
            actor_id=actor.user_id,
            metadata={"draft_version": new_version_no},
        )
        await tx.commit()
    return draft_view(draft, version, payload)


async def _resolve_save_binding(
    actor: Any, draft_id: str, draft_version: int
) -> tuple[PlanDraft, PlanDraftVersion]:
    async with uow() as tx:
        draft = await tx.session.get(PlanDraft, draft_id)
        if draft is None or draft.user_id != actor.user_id:
            raise ApiError("RESOURCE_NOT_FOUND")
        version = await tx.session.get(PlanDraftVersion, (draft_id, draft_version))
    if version is None:
        raise ApiError("DRAFT_EXPIRED")
    return draft, version


async def save_draft(
    actor: Any,
    draft_id: str,
    draft_version: int,
    idempotency_key: str,
    request_id: str,
) -> tuple[int, dict[str, Any]]:
    """按设计 §7.2 顺序执行保存（本阶段授权来源：draft_button）。"""
    draft_read, version_read = await _resolve_save_binding(actor, draft_id, draft_version)
    now = _now_db()

    if draft_read.session_id != actor.session_id:
        raise ApiError("SAVE_NOT_AUTHORIZED")
    if draft_read.expires_at <= now:
        raise ApiError("DRAFT_EXPIRED")
    if version_read.payload is None:
        raise ApiError("DRAFT_EXPIRED")
    if int(draft_read.current_version) != draft_version:
        # 旧版本不得首次保存（设计 §7.3）
        raise ApiError("SAVE_NOT_AUTHORIZED")
    if idempotency_key != version_read.operation_id:
        # 草稿保存必须匹配服务端版本绑定
        raise ApiError("SAVE_NOT_AUTHORIZED")

    digest = version_read.content_digest
    origin_request_id = draft_read.origin_chat_request_id

    final = await _ensure_pending_intent(
        actor,
        operation_id=idempotency_key,
        digest=digest,
        source="assistant",
        draft_id=draft_id,
        draft_version=draft_version,
        origin_chat_request_id=origin_request_id,
    )
    if final is not None:
        return 200, _result_payload(final)

    try:
        async with uow() as tx:
            await tx.lock_and_validate_actor(actor)
            await tx.lock_chat_requests([origin_request_id])
            draft = await tx.lock_draft(draft_id)
            version_row = await tx.lock_draft_version(draft_id, draft_version)
            operation = await tx.lock_operation(actor.user_id, idempotency_key)
            if operation is None:
                raise ApiError("INTERNAL_ERROR")
            if _operation_final_result(operation) is not None:
                return 200, _result_payload(operation)
            if operation.content_digest != digest:
                raise ApiError("IDEMPOTENCY_CONFLICT")
            if draft is None or draft.user_id != actor.user_id:
                raise ApiError("RESOURCE_NOT_FOUND")
            if draft.session_id != actor.session_id:
                raise ApiError("SAVE_NOT_AUTHORIZED")
            if draft.expires_at <= _now_db():
                raise ApiError("DRAFT_EXPIRED")
            if version_row is None or version_row.payload is None:
                raise ApiError("DRAFT_EXPIRED")
            if int(draft.current_version) != draft_version:
                raise ApiError("SAVE_NOT_AUTHORIZED")

            slot = await tx.session.get(
                AssistantSaveSlot, (actor.user_id, origin_request_id)
            )
            if slot is not None and slot.operation_id != idempotency_key:
                raise ApiError("SAVE_LIMIT_REACHED")

            grants = await tx.lock_grants_for_operation(actor.user_id, idempotency_key)
            grant = next(
                (
                    item
                    for item in grants
                    if item.content_digest == digest and item.state in ("issued", "consumed")
                ),
                None,
            )
            if grant is not None and grant.state == "consumed":
                raise ApiError("SAVE_NOT_AUTHORIZED")
            if grant is not None:
                if grant.expires_at <= _now_db():
                    raise ApiError("SAVE_NOT_AUTHORIZED")
                if grant.session_id != actor.session_id:
                    raise ApiError("SAVE_NOT_AUTHORIZED")
            else:
                grant = SaveGrant(
                    id=new_id(PREFIX_GRANT),
                    user_id=actor.user_id,
                    session_id=actor.session_id,
                    trace_request_id=request_id,
                    authorization_kind="draft_button",
                    authorization_chat_request_id=None,
                    draft_id=draft_id,
                    draft_version=draft_version,
                    operation_id=idempotency_key,
                    content_digest=digest,
                    state="issued",
                    expires_at=to_db(
                        now_utc()
                        + timedelta(seconds=get_settings().draft_ttl_seconds)
                    ),
                    created_at=_now_db(),
                    consumed_at=None,
                )
                tx.session.add(grant)

            payload = version_row.payload
            validate_plan_payload(payload)
            plan = _insert_plan(
                tx,
                actor,
                operation_id=idempotency_key,
                payload=payload,
                source="assistant",
            )
            await tx.session.flush()
            if slot is None:
                tx.session.add(
                    AssistantSaveSlot(
                        user_id=actor.user_id,
                        request_id=origin_request_id,
                        operation_id=idempotency_key,
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
            append_audit(
                tx,
                action="plan_saved",
                object_type="study_plan",
                object_id=plan.id,
                result="success",
                request_id=request_id,
                actor_id=actor.user_id,
                metadata={"source": "assistant", "draft_id": draft_id},
            )
            append_outbox(
                tx,
                event_type="plan_saved",
                aggregate_id=plan.id,
                request_id=request_id,
                metadata={
                    "plan_id": plan.id,
                    "operation_id": idempotency_key,
                    "draft_id": draft_id,
                    "draft_version": draft_version,
                },
            )
            await tx.commit()
    except IntegrityError as exc:
        mapped = map_integrity_error(exc)
        async with uow() as tx2:
            operation = await tx2.session.get(
                WriteOperation, (actor.user_id, idempotency_key)
            )
        if operation is not None and _operation_final_result(operation):
            return 200, _result_payload(operation)
        raise (mapped or ApiError("INTERNAL_ERROR")) from None

    return 201, {
        "status": "created",
        "operation_id": idempotency_key,
        "plan_id": plan.id,
    }


# --------------------------------------------------------------------------- #
# 写入状态
# --------------------------------------------------------------------------- #
async def get_write_operation(actor: Any, operation_id: str) -> dict[str, Any]:
    async with uow() as tx:
        operation = await tx.session.get(
            WriteOperation, (actor.user_id, operation_id)
        )
    if operation is None:
        # 未知提交：不解释为“确定未保存”，返回 pending(recovering)（设计 §7.3）
        return {
            "operation_id": operation_id,
            "state": "pending",
            "resolution": "recovering",
            "retryable": False,
        }
    data: dict[str, Any] = {
        "operation_id": operation.operation_id,
        "state": operation.state,
        "resolution": operation.resolution,
        "retryable": bool(operation.retryable),
    }
    if operation.state in ("succeeded", "deleted") and operation.plan_id:
        data["plan_id"] = operation.plan_id
    if operation.state == "failed" and operation.error_code:
        data["error_code"] = operation.error_code
    return data


def operation_created_at(operation: WriteOperation) -> str | None:  # pragma: no cover
    return isoformat(operation.created_at)


__all__ = [
    "create_plan_manual",
    "delete_plan",
    "get_draft",
    "get_plan",
    "get_write_operation",
    "list_plans",
    "patch_plan",
    "revise_draft",
    "save_draft",
]


# 供 Phase 3 复用的服务端校验基建（direct_instruction 由对话来源写入时调用）
async def validate_direct_authorization(  # pragma: no cover - Phase 3 接入
    tx: UoW, *, operation_id: str, digest: bytes
) -> SaveGrant | None:
    grants = await tx.lock_grants_for_operation(tx.session.info.get("actor_id", ""), operation_id)
    return next((g for g in grants if g.content_digest == digest), None)
