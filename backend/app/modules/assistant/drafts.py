"""草稿形成与「直接指令」判定（设计 §7.1 / FR-PLAN-003；PHASE-03 A8）。

两件事：

1. ``classify_direct_instruction``：对**当前用户消息**做保守的保存意图判定
   ``none / explicit / ambiguous / denied``。模型只能给候选（``DraftIntent.save_candidate``），
   是否签发许可由本函数 + 服务端规则决定；否定、疑问、引用/历史转述一律不授权。
2. ``create_turn_draft``：把 provider 的草稿意图落成 ``plan_drafts`` + 不可变
   ``plan_draft_versions``（预分配 ``operation_id``）。**每轮最多一份来源草稿**。
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.adapters.db.models import PlanDraft, PlanDraftVersion
from app.adapters.db.uow import uow
from app.adapters.model.gateway import DraftIntent, DraftRecord
from app.config import get_settings
from app.modules.planning.schemas import validate_plan_payload
from app.shared.clock import now_utc, to_db
from app.shared.context import ExecutionContext
from app.shared.errors import ApiError
from app.shared.ids import PREFIX_DRAFT, PREFIX_DRAFT_OPERATION, new_id
from app.shared.payload import normalize_plan_payload, plan_payload_digest

logger = logging.getLogger("cca.assistant.drafts")

DirectInstruction = Literal["none", "explicit", "ambiguous", "denied"]

SAVE_MARKERS: tuple[str, ...] = (
    "保存",
    "存下来",
    "存到",
    "记录下来",
    "记到我的计划",
    "帮我存",
    "加入计划",
)

# 否定：出现即不授权（且不得用“否定+肯定”混合话术绕过）
DENIED_MARKERS: tuple[str, ...] = (
    "不保存",
    "不要保存",
    "不用保存",
    "不必保存",
    "不需要保存",
    "先不要保存",
    "先别保存",
    "先不保存",
    "暂时不保存",
    "别保存",
    "不想保存",
    "不需要存",
    "不用存",
    "别存",
    "不要存",
)

# 疑问 / 条件 / 引用 / 历史转述：只能形成草稿，不能据此自动保存
AMBIGUOUS_MARKERS: tuple[str, ...] = (
    "吗",
    "是否",
    "要不要",
    "需不需要",
    "可以不",
    "能不能",
    "能否",
    "如果",
    "假如",
    "要是",
    "他说",
    "她说",
    "之前提到",
    "之前说过",
    "历史",
    "引用",
    "材料里",
    "文档里",
    "老师说",
    "?",
    "？",
)

PLAN_MARKERS: tuple[str, ...] = ("计划", "制定", "规划", "复习", "安排")


def classify_direct_instruction(message: str, *, draft_ready: bool) -> DirectInstruction:
    """保守判定当前消息是否构成可确定的“生成并保存”直接指令。"""
    text = (message or "").strip()
    if not text or not any(marker in text for marker in SAVE_MARKERS):
        return "none"
    if any(marker in text for marker in DENIED_MARKERS):
        return "denied"
    if any(marker in text for marker in AMBIGUOUS_MARKERS):
        return "ambiguous"
    if draft_ready or any(marker in text for marker in PLAN_MARKERS):
        return "explicit"
    return "none"


async def get_turn_draft(actor: Any, request_id: str) -> PlanDraft | None:
    """本轮已有的来源草稿（每轮最多一份）。"""
    async with uow() as tx:
        result = await tx.session.execute(
            select(PlanDraft).where(
                PlanDraft.user_id == actor.user_id,
                PlanDraft.origin_chat_request_id == request_id,
            )
        )
        return result.scalar_one_or_none()


async def create_turn_draft(
    context: ExecutionContext,
    intent: DraftIntent,
    *,
    references: list[dict[str, Any]] | None = None,
) -> DraftRecord:
    """把草稿意图落库（独立短事务，不等模型/工具）。"""
    actor = context.actor
    existing = await get_turn_draft(actor, context.chat_request_id)
    if existing is not None:
        async with uow() as tx:
            version = await tx.session.get(
                PlanDraftVersion, (existing.id, int(existing.current_version))
            )
        if version is None:
            raise ApiError("INTERNAL_ERROR")
        return DraftRecord(
            draft_id=existing.id,
            draft_version=int(version.draft_version),
            operation_id=version.operation_id,
        )

    payload = normalize_plan_payload(
        {
            "title": intent.title.strip()[:100],
            "goal": (intent.goal or None),
            "start_date": intent.start_date.isoformat() if intent.start_date else None,
            "end_date": intent.end_date.isoformat() if intent.end_date else None,
            "content": intent.content,
            "basis_types": list(intent.basis_types),
            "references": references or [],
        }
    )
    validate_plan_payload(payload)
    digest = plan_payload_digest(payload)
    now = now_utc()
    draft_id = new_id(PREFIX_DRAFT)
    operation_id = new_id(PREFIX_DRAFT_OPERATION)

    async with uow() as tx:
        await tx.lock_user(actor.user_id)
        draft = PlanDraft(
            id=draft_id,
            user_id=actor.user_id,
            session_id=actor.session_id,
            conversation_id=context.conversation_id,
            origin_chat_request_id=context.chat_request_id,
            current_version=1,
            expires_at=to_db(now + timedelta(seconds=get_settings().draft_ttl_seconds)),
            created_at=to_db(now),
            updated_at=to_db(now),
        )
        version = PlanDraftVersion(
            draft_id=draft_id,
            draft_version=1,
            operation_id=operation_id,
            schema_version=1,
            payload=payload,
            content_digest=digest,
            created_at=to_db(now),
            payload_cleared_at=None,
        )
        tx.session.add(draft)
        tx.session.add(version)
        try:
            await tx.session.flush()
            await tx.commit()
        except IntegrityError as exc:
            await tx.rollback()
            logger.warning("draft insert conflicted request_id=%s", context.chat_request_id)
            existing = await get_turn_draft(actor, context.chat_request_id)
            if existing is None:
                raise ApiError("INTERNAL_ERROR") from exc
            draft_id = existing.id
            operation_id = version.operation_id if version is not None else ""
            async with uow() as tx2:
                row = await tx2.session.get(
                    PlanDraftVersion, (draft_id, int(existing.current_version))
                )
            if row is None:
                raise ApiError("INTERNAL_ERROR") from exc
            return DraftRecord(
                draft_id=draft_id,
                draft_version=int(row.draft_version),
                operation_id=row.operation_id,
            )
    return DraftRecord(draft_id=draft_id, draft_version=1, operation_id=operation_id)


async def attach_plan_to_requests(
    tx: Any,
    request_ids: list[str],
    *,
    plan_id: str,
    operation_id: str,
) -> None:
    """把已确认计划写回来源轮/授权轮的 chat_requests 元数据（供状态查询）。"""
    from app.adapters.db.models import ChatRequest

    if not request_ids:
        return
    for request_id in sorted(set(request_ids)):
        row = await tx.session.get(ChatRequest, request_id)
        if row is None:
            continue
        row.plan_id = plan_id
        row.operation_id = operation_id[:64]


__all__ = [
    "AMBIGUOUS_MARKERS",
    "DENIED_MARKERS",
    "DirectInstruction",
    "SAVE_MARKERS",
    "attach_plan_to_requests",
    "classify_direct_instruction",
    "create_turn_draft",
    "get_turn_draft",
]
