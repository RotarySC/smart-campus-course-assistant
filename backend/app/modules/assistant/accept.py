"""请求接受 / 状态查询 / 取消（设计 §8.1、§8.3；PHASE-03 A5/A7）。

接受事务顺序（§8.1）：
认证用户与会话（依赖注入已完成）→ 获取/创建 ConversationState 并核实绑定 →
``client_request_id`` 唯一 + 请求摘要 → 同会话活动轮检查 → 锁定一个未占用 AI 容量槽 →
插入 accepted ``ChatRequest`` → 绑定槽与会话 → 提交。

- 重复 ID：409 ``REQUEST_ALREADY_EXISTS`` + 原请求状态入口（details）。
- 同会话运行：409 ``CHAT_IN_PROGRESS``。
- 无容量：事务回滚 + 429 ``CAPACITY_LIMITED``。
- 容量槽租约按**数据库时间**判定（``lease_until <= NOW(6)``），进程崩溃后可回收。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, text

from app.adapters.db.models import AICapacitySlot, ChatRequest, ConversationState
from app.adapters.db.uow import uow
from app.config import get_settings
from app.modules.assistant.contracts import ChatInput, ChatState
from app.modules.assistant.drafts import classify_direct_instruction
from app.modules.assistant.settings import get_assistant_settings
from app.modules.operations.service import append_outbox
from app.shared.clock import isoformat, now_utc, to_db
from app.shared.context import ActorContext
from app.shared.errors import ApiError
from app.shared.ids import PREFIX_CONVERSATION, PREFIX_REQUEST, new_id

logger = logging.getLogger("cca.assistant.accept")

ACTIVE_STATES = ("accepted", "running")
TERMINAL_STATES = ("succeeded", "failed", "cancelled")
MAX_HISTORY_CHARS = 30_000
# 容量槽选槽的有界重试：SKIP LOCKED 把"瞬时被行锁占着"的空闲槽也跳过，
# 单次查询为空不等于容量耗尽（AT-30 PERF-005 实测 9/120 误拒）。
_CAPACITY_SLOT_ATTEMPTS = 4
_CAPACITY_SLOT_RETRY_DELAY = 0.003


@dataclass
class AcceptResult:
    request_id: str
    conversation_id: str
    accepted_at: datetime
    deadline_at: datetime
    fence: int
    message: str
    history: list[tuple[str, str]] = field(default_factory=list)
    context_truncated: bool = False


def request_digest(command: ChatInput) -> bytes:
    """请求摘要：只覆盖客户端可见的请求体（用于重复键审计与冲突核实）。"""
    document = {
        "client_request_id": command.client_request_id,
        "conversation_id": command.conversation_id,
        "message": command.message,
        "history": (
            [{"role": item.role, "content": item.content} for item in command.history]
            if command.history
            else []
        ),
    }
    canonical = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).digest()


def trim_history(
    history: list[Any] | None,
) -> tuple[list[tuple[str, str]], bool]:
    """保留最近的**完整**问答对；超预算截断并告知（FR-CHAT-002 / §8.2）。"""
    if not history:
        return [], False
    pairs: list[tuple[str, str]] = []
    truncated = False
    # 从尾部按「user→assistant」完整对收集
    index = len(history) - 1
    total = 0
    while index >= 1:
        assistant = history[index]
        user = history[index - 1]
        if getattr(assistant, "role", "") != "assistant" or getattr(user, "role", "") != "user":
            truncated = True
            index -= 1
            continue
        length = len(user.content) + len(assistant.content)
        if total + length > MAX_HISTORY_CHARS:
            truncated = True
            break
        pairs.append((user.content, assistant.content))
        total += length
        index -= 2
    if index >= 0:
        truncated = True
    pairs.reverse()
    return pairs, truncated


async def accept_request(
    actor: ActorContext,
    command: ChatInput,
    *,
    request_trace_id: str,
) -> AcceptResult:
    settings = get_assistant_settings()
    now = now_utc()
    deadline_at = now + timedelta(seconds=settings.deadline_seconds)
    digest = request_digest(command)
    history, history_truncated = trim_history(command.history)

    async with uow() as tx:
        # 锁当前用户：同一用户的接受事务串行化（锁顺序第 1 位），避免重复键/活动轮竞态
        user = await tx.lock_user(actor.user_id)
        if user is None or not bool(user.enabled):
            raise ApiError("SESSION_EXPIRED")
        if int(user.auth_version) != int(actor.auth_version):
            raise ApiError("SESSION_EXPIRED")

        conversation: ConversationState | None = None
        if command.conversation_id:
            conversation = await tx.session.get(ConversationState, command.conversation_id)
            if (
                conversation is None
                or conversation.user_id != actor.user_id
                or conversation.session_id != actor.session_id
            ):
                # 跨用户/跨会话不可见：不泄露存在性
                raise ApiError("RESOURCE_NOT_FOUND")
            await tx.lock_conversation(conversation.id)

        existing = await _find_by_client_id(tx, actor.user_id, command.client_request_id)
        if existing is not None:
            raise ApiError(
                "REQUEST_ALREADY_EXISTS",
                details={
                    "request_id": existing.id,
                    "conversation_id": existing.conversation_id,
                    "state": existing.state,
                    "status_endpoint": f"/api/v1/chat/requests/{existing.id}",
                },
            )

        active = await _find_active(tx, actor.user_id, actor.session_id)
        if active is not None:
            raise ApiError(
                "CHAT_IN_PROGRESS",
                details={
                    "request_id": active.id,
                    "conversation_id": active.conversation_id,
                    "state": active.state,
                },
            )

        if conversation is None:
            conversation = ConversationState(
                id=new_id(PREFIX_CONVERSATION),
                user_id=actor.user_id,
                session_id=actor.session_id,
                active_request_id=None,
                created_at=to_db(now),
                updated_at=to_db(now),
            )
            tx.session.add(conversation)
            await tx.session.flush()

        slot = await _lock_free_capacity_slot(tx)
        if slot is None:
            raise ApiError("CAPACITY_LIMITED")

        request_id = new_id(PREFIX_REQUEST)
        chat_request = ChatRequest(
            id=request_id,
            client_request_id=command.client_request_id,
            user_id=actor.user_id,
            session_id=actor.session_id,
            conversation_id=conversation.id,
            request_digest=digest,
            state="accepted",
            cancel_requested=False,
            accepted_at=to_db(now),
            deadline_at=to_db(deadline_at),
            finished_at=None,
            school_timezone=get_settings().school_timezone,
            model_calls=0,
            tool_calls=0,
            owner_instance=settings.instance_id,
            fence=1,
            lease_until=to_db(now + timedelta(seconds=settings.lease_seconds)),
            terminal_reason=None,
            # 服务端对用户原文的保存意图分类（模型意见只作候选，不能写这一列）
            instruction_class=classify_direct_instruction(command.message, draft_ready=False),
            plan_id=None,
            operation_id=None,
        )
        tx.session.add(chat_request)
        await tx.session.flush()

        slot.request_id = request_id
        slot.owner_instance = settings.instance_id
        slot.fence = 1
        slot.lease_until = to_db(now + timedelta(seconds=settings.lease_seconds))

        conversation.active_request_id = request_id
        conversation.updated_at = to_db(now)

        append_outbox(
            tx,
            event_type="chat_requested",
            aggregate_id=request_id,
            request_id=request_trace_id,
            metadata={
                "request_id": request_id,
                "conversation_id": conversation.id,
                "slot_no": int(slot.slot_no),
            },
        )
        await tx.commit()

    return AcceptResult(
        request_id=request_id,
        conversation_id=conversation.id,
        accepted_at=now,
        deadline_at=deadline_at,
        fence=1,
        message=command.message,
        history=history,
        context_truncated=history_truncated,
    )


async def _find_by_client_id(tx: Any, user_id: str, client_request_id: str) -> ChatRequest | None:
    result = await tx.session.execute(
        select(ChatRequest).where(
            ChatRequest.user_id == user_id,
            ChatRequest.client_request_id == client_request_id,
        )
    )
    return result.scalar_one_or_none()


async def _find_active(tx: Any, user_id: str, session_id: str) -> ChatRequest | None:
    result = await tx.session.execute(
        select(ChatRequest)
        .where(
            ChatRequest.user_id == user_id,
            ChatRequest.session_id == session_id,
            ChatRequest.state.in_(ACTIVE_STATES),
        )
        .order_by(ChatRequest.accepted_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _lock_free_capacity_slot(tx: Any) -> AICapacitySlot | None:
    """选一个空闲容量槽；对 SKIP LOCKED 造成的瞬时假满做有界重试。

    ``SKIP LOCKED`` 会跳过"被其它 accept 事务瞬时行锁占着"的空闲槽，单次查询
    返回空并不代表容量耗尽——直接判 429 会把额定容量内的请求拒掉（AT-30
    实测 120 轮里 9 次 429，同时仍有 2–3 个空闲槽）。这里只在毫秒级窗口内重试，
    真实满容量时仍然快速返回 None（NFR-PERF-004：不得无限排队）。
    """
    for attempt in range(_CAPACITY_SLOT_ATTEMPTS):
        result = await tx.session.execute(
            select(AICapacitySlot)
            .where(
                (AICapacitySlot.request_id.is_(None))
                | text(
                    "ai_capacity_slots.lease_until IS NOT NULL "
                    "AND ai_capacity_slots.lease_until <= NOW(6)"
                )
            )
            .order_by(AICapacitySlot.slot_no)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        slot = result.scalar_one_or_none()
        if slot is not None:
            return slot
        if attempt + 1 < _CAPACITY_SLOT_ATTEMPTS:
            await asyncio.sleep(_CAPACITY_SLOT_RETRY_DELAY * (attempt + 1))
    return None


# --------------------------------------------------------------------------- #
# 状态查询 / 取消
# --------------------------------------------------------------------------- #
def chat_state(request: ChatRequest) -> ChatState:
    data: dict[str, Any] = {
        "request_id": request.id,
        "conversation_id": request.conversation_id,
        "state": request.state,
        "cancel_requested": bool(request.cancel_requested),
        "accepted_at": isoformat(request.accepted_at) or "",
        "finished_at": isoformat(request.finished_at),
        "model_calls": int(request.model_calls),
        "tool_calls": int(request.tool_calls),
    }
    # 设计包中以下字段为“可选非 nullable”：缺省时省略键，不输出 null
    if request.terminal_reason:
        data["terminal_reason"] = request.terminal_reason
    if request.plan_id:
        data["plan_id"] = request.plan_id
    if request.operation_id:
        data["operation_id"] = request.operation_id
    return ChatState(**data)


async def get_request_state(actor: ActorContext, request_id: str) -> ChatState:
    async with uow() as tx:
        result = await tx.session.execute(
            select(ChatRequest).where(
                ChatRequest.id == request_id,
                ChatRequest.user_id == actor.user_id,
            )
        )
        request = result.scalar_one_or_none()
    if request is None:
        raise ApiError("RESOURCE_NOT_FOUND")
    return chat_state(request)


async def cancel_request(
    actor: ActorContext, request_id: str
) -> tuple[bool, ChatState]:
    """幂等提出停止；返回是否已接受取消及当前状态。"""
    async with uow() as tx:
        await tx.lock_user(actor.user_id)
        result = await tx.session.execute(
            select(ChatRequest)
            .where(ChatRequest.id == request_id, ChatRequest.user_id == actor.user_id)
            .with_for_update()
        )
        request = result.scalar_one_or_none()
        if request is None:
            raise ApiError("RESOURCE_NOT_FOUND")
        if request.state in ACTIVE_STATES:
            request.cancel_requested = True
            accepted = True
        else:
            accepted = False
        state = chat_state(request)
        await tx.commit()
    return accepted, state


async def recover_stale_requests(*, limit: int = 100) -> int:
    """启动扫描：租约过期且仍在 accepted/running 的请求标 failed/SERVICE_RESTARTED。

    不重跑模型；递增 fence 防旧 runner 继续提交；释放活动会话槽与 AI 槽。
    """
    recovered = 0
    async with uow() as tx:
        result = await tx.session.execute(
            select(ChatRequest)
            .where(
                ChatRequest.state.in_(ACTIVE_STATES),
                text("chat_requests.lease_until IS NOT NULL AND chat_requests.lease_until <= NOW(6)"),
            )
            .order_by(ChatRequest.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = list(result.scalars().all())
        now = to_db(now_utc())
        for request in rows:
            request.state = "failed"
            request.finished_at = now
            request.terminal_reason = "SERVICE_RESTARTED"
            request.fence = int(request.fence) + 1
            request.lease_until = None
            await tx.session.execute(
                text(
                    "UPDATE ai_capacity_slots SET request_id = NULL, owner_instance = NULL, "
                    "lease_until = NULL WHERE request_id = :rid"
                ),
                {"rid": request.id},
            )
            await tx.session.execute(
                text(
                    "UPDATE conversation_states SET active_request_id = NULL, updated_at = :now "
                    "WHERE id = :cid AND active_request_id = :rid"
                ),
                {"cid": request.conversation_id, "rid": request.id, "now": now},
            )
            append_outbox(
                tx,
                event_type="chat_failed",
                aggregate_id=request.id,
                request_id=request.id,
                metadata={"reason": "SERVICE_RESTARTED"},
            )
            recovered += 1
        if recovered:
            await tx.commit()
    if recovered:
        logger.warning("recovered stale chat requests count=%s", recovered)
    # 写入操作恢复（§7.3）：确认没有创建结果的 pending 意图收敛为可重试失败，
    # 已有计划的补齐 succeeded。失败不影响请求恢复本身。
    try:
        from app.modules.planning.recovery import recover_pending_write_operations

        counters = await recover_pending_write_operations()
        if counters["recovered_succeeded"] or counters["recovered_failed"]:
            logger.warning("recovered write operations %s", counters)
    except Exception:  # noqa: BLE001 - 恢复失败不应阻断新请求
        logger.exception("write operation recovery failed")
    return recovered


__all__ = [
    "ACTIVE_STATES",
    "AcceptResult",
    "TERMINAL_STATES",
    "accept_request",
    "cancel_request",
    "chat_state",
    "get_request_state",
    "recover_stale_requests",
    "request_digest",
    "trim_history",
]
