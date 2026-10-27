"""运维面：审计、Outbox、后台任务骨架（设计 §5.2 顺序 6 / §13.3）。

- 审计与业务结果同事务写入，只记元数据（无正文、口令、令牌、完整工具参数）。
- Outbox 消费骨架：按 event_id 去重、no-op 派发；Phase 2/3 接真实消费者。
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update

from app.adapters.db.models import AuditEvent, OutboxEvent
from app.adapters.db.uow import UoW
from app.shared.clock import now_utc, to_db
from app.shared.ids import PREFIX_AUDIT, PREFIX_OUTBOX, new_id

logger = logging.getLogger("cca.operations")

AUDIT_RETENTION_DAYS = 180


def append_audit(
    tx: UoW,
    *,
    action: str,
    object_type: str,
    object_id: str | None,
    result: str,
    request_id: str,
    actor_id: str | None = None,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """插入审计事件（与业务同事务）。metadata 只放白名单元数据。

    ``duration_ms`` 未显式给出时取请求级耗时（FR-OPS-001）；worker/CLI 无请求上下文
    时保持 NULL，不臆造数字。
    """
    from app.shared.audit_timing import current_duration_ms

    measured = duration_ms if duration_ms is not None else current_duration_ms()
    event = AuditEvent(
        id=new_id(PREFIX_AUDIT),
        actor_id=actor_id,
        action=action[:64],
        object_type=object_type[:32],
        object_id=object_id,
        result=result[:32],
        request_id=request_id[:64],
        duration_ms=measured,
        metadata_json=metadata,
        created_at=to_db(now_utc()),
    )
    tx.session.add(event)
    return event.id


def append_outbox(
    tx: UoW,
    *,
    event_type: str,
    aggregate_id: str | None,
    request_id: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    now = to_db(now_utc())
    event = OutboxEvent(
        id=new_id(PREFIX_OUTBOX),
        event_type=event_type[:64],
        aggregate_id=aggregate_id,
        request_id=request_id[:64],
        metadata_json=metadata or {},
        state="pending",
        attempts=0,
        next_run_at=now,
        created_at=now,
    )
    tx.session.add(event)
    return event.id


async def dispatch_outbox_once(limit: int = 50) -> int:
    """Outbox 骨架消费：去重 + no-op 派发（Phase 2/3 接真实消费者）。

    只把到期的 pending 事件标记为 published；发送失败不回滚已提交业务。
    """
    from app.adapters.db.engine import get_session_factory

    factory = get_session_factory()
    now = to_db(now_utc())
    dispatched = 0
    async with factory() as session:
        result = await session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.state == "pending", OutboxEvent.next_run_at <= now)
            .order_by(OutboxEvent.next_run_at, OutboxEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        events = list(result.scalars().all())
        for event in events:
            event.state = "published"
            event.attempts = (event.attempts or 0) + 1
            event.published_at = now
            dispatched += 1
        await session.commit()
    if dispatched:
        logger.info("outbox noop dispatch: %s events", dispatched)
    return dispatched


async def claim_background_tasks(owner: str, limit: int = 10) -> int:  # pragma: no cover
    """任务领取骨架（Phase 2 实现真实领取；本阶段仅保留入口）。"""
    logger.info("background task claim placeholder owner=%s limit=%s", owner, limit)
    return 0


async def expire_old_audits(days: int = AUDIT_RETENTION_DAYS) -> int:  # pragma: no cover
    """审计保留期清理骨架（保留期属 TBD-06，本阶段不自动执行）。"""
    cutoff = to_db(now_utc() - timedelta(days=days))
    from app.adapters.db.engine import get_session_factory

    async with get_session_factory()() as session:
        result = await session.execute(
            update(AuditEvent).where(AuditEvent.created_at < cutoff).values()
        )
        await session.commit()
        return result.rowcount or 0
