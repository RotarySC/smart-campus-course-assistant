"""运行统计查询（FR-OPS-002 / NFR-OBS-001）。

口径（写死在这里，便于审计与回归）：
- 窗口按**学校时区自然日**，含起止；上限 31 天（与课表跨度同量级，防止一次扫全表）。
- 回答终止分类来自 ``chat_requests.state`` + ``terminal_reason``：
  ``succeeded`` / ``cancelled`` / ``failed``；失败再按原因拆
  ``EXECUTION_TIMEOUT``=timeout、``CALL_LIMIT_REACHED``=limit_reached、
  ``SESSION_EXPIRED``=auth_expired，其余计入 failed。
- ``empty``（主体正确结束但无依据）只在检索**成功且全库/本次无片段**时计：来自
  ``chat_finished`` 事件的 ``metadata.corpus_empty``。检索失败计 failed，不计 empty。
- 计划写入来自 ``write_operations``：幂等重放不新增行，因此不会把重放计成新建。
- 工具调用/失败来自 ``audit_events`` 的 ``tool.*`` 行：``ok/created/existing/deleted``
  视为成功，其余（错误码）视为失败。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select

from app.adapters.db.engine import session_scope
from app.adapters.db.models import (
    AuditEvent,
    BackgroundTask,
    ChatRequest,
    DocumentBatch,
    OutboxEvent,
    WriteOperation,
)
from app.shared.clock import school_tz, to_db

MAX_WINDOW_DAYS = 31

TOOL_SUCCESS_RESULTS = frozenset({"ok", "created", "existing", "deleted"})

_FAILURE_BUCKETS = {
    "EXECUTION_TIMEOUT": "timeout",
    "CALL_LIMIT_REACHED": "limit_reached",
    "SESSION_EXPIRED": "auth_expired",
}

_PENDING_STATES = ("accepted", "running")


def window_bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    """学校时区自然日 → UTC 半开区间 ``[start, end)``（供查询与测试共用）。"""
    tz = school_tz()
    start = datetime.combine(from_date, time.min, tzinfo=tz)
    end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=tz)
    return to_db(start), to_db(end)


def school_timezone_name() -> str:
    from app.config import get_settings

    return str(get_settings().school_timezone)


async def overview(*, from_date: date, to_date: date) -> dict[str, object]:
    """聚合窗口内的回答终止与写入/工具/批次计数。"""
    start, end = window_bounds(from_date, to_date)
    requests = {
        "total": 0,
        "succeeded": 0,
        "succeeded_with_evidence": 0,
        "empty": 0,
        "failed": 0,
        "cancelled": 0,
        "timeout": 0,
        "limit_reached": 0,
        "auth_expired": 0,
        "pending": 0,
    }
    async with session_scope() as session:
        rows = await session.execute(
            select(ChatRequest.state, ChatRequest.terminal_reason, func.count())
            .where(ChatRequest.accepted_at >= start, ChatRequest.accepted_at < end)
            .group_by(ChatRequest.state, ChatRequest.terminal_reason)
        )
        for state, reason, count in rows.all():
            amount = int(count)
            requests["total"] += amount
            if state in _PENDING_STATES:
                requests["pending"] += amount
            elif state == "cancelled":
                requests["cancelled"] += amount
            elif state == "succeeded":
                requests["succeeded"] += amount
            else:
                bucket = _FAILURE_BUCKETS.get(str(reason or ""))
                requests[bucket or "failed"] += amount

        empty = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.created_at >= start,
                OutboxEvent.created_at < end,
                OutboxEvent.event_type == "chat_finished",
                OutboxEvent.metadata_json["corpus_empty"].as_boolean().is_(True),
            )
        )
        requests["empty"] = int(empty or 0)
        requests["succeeded_with_evidence"] = max(
            0, requests["succeeded"] - requests["empty"]
        )

        operation_rows = await session.execute(
            select(WriteOperation.state, func.count())
            .where(
                WriteOperation.created_at >= start,
                WriteOperation.created_at < end,
            )
            .group_by(WriteOperation.state)
        )
        plan_states = {str(state): int(count) for state, count in operation_rows.all()}
        retryable_failed = await session.scalar(
            select(func.count())
            .select_from(WriteOperation)
            .where(
                WriteOperation.created_at >= start,
                WriteOperation.created_at < end,
                WriteOperation.state == "failed",
                WriteOperation.retryable.is_(True),
            )
        )

        event_rows = await session.execute(
            select(OutboxEvent.event_type, func.count())
            .where(
                OutboxEvent.created_at >= start,
                OutboxEvent.created_at < end,
                OutboxEvent.event_type.in_(("draft.formed", "citation.expanded")),
            )
            .group_by(OutboxEvent.event_type)
        )
        events = {str(kind): int(count) for kind, count in event_rows.all()}

        tool_rows = await session.execute(
            select(AuditEvent.result, func.count())
            .where(
                AuditEvent.created_at >= start,
                AuditEvent.created_at < end,
                AuditEvent.action.startswith("tool."),
            )
            .group_by(AuditEvent.result)
        )
        tool_calls = 0
        tool_failures = 0
        for result, count in tool_rows.all():
            amount = int(count)
            tool_calls += amount
            if str(result or "") not in TOOL_SUCCESS_RESULTS:
                tool_failures += amount

        batch_rows = await session.execute(
            select(DocumentBatch.state, func.count())
            .where(
                DocumentBatch.created_at >= start,
                DocumentBatch.created_at < end,
                DocumentBatch.state.in_(("published", "failed")),
            )
            .group_by(DocumentBatch.state)
        )
        batches = {str(state): int(count) for state, count in batch_rows.all()}

        idempotent_hits = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.created_at >= start,
                OutboxEvent.created_at < end,
                OutboxEvent.event_type == "write_operation.idempotent_hit",
            )
        )
        writes_recovered = await session.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(
                OutboxEvent.created_at >= start,
                OutboxEvent.created_at < end,
                OutboxEvent.event_type == "write_operation.recovered",
            )
        )

        # 任务积压是快照：反映查询时刻队列里的任务，不随窗口过滤。
        task_rows = await session.execute(
            select(BackgroundTask.state, func.count()).group_by(BackgroundTask.state)
        )
        task_states = {str(state): int(count) for state, count in task_rows.all()}

        cleanup_rows = await session.execute(
            select(AuditEvent.action, AuditEvent.result, func.count())
            .where(
                AuditEvent.created_at >= start,
                AuditEvent.created_at < end,
                AuditEvent.action.in_(
                    ("document.cleanup", "document.batch.compensated")
                ),
            )
            .group_by(AuditEvent.action, AuditEvent.result)
        )
        cleanup_succeeded = 0
        cleanup_failed = 0
        for _action, result, count in cleanup_rows.all():
            amount = int(count)
            if str(result or "") == "success":
                cleanup_succeeded += amount
            else:
                cleanup_failed += amount
        slow_cleanups = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.created_at >= start,
                AuditEvent.created_at < end,
                AuditEvent.action.in_(
                    ("document.cleanup", "document.batch.compensated")
                ),
                AuditEvent.metadata_json["slow_cleanup"].as_boolean().is_(True),
            )
        )

    return {
        "window": {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "school_timezone": school_timezone_name(),
        },
        "requests": requests,
        "operations": {
            "plans_created": plan_states.get("succeeded", 0),
            "plans_deleted": plan_states.get("deleted", 0),
            "plans_retryable_failed": int(retryable_failed or 0),
            "drafts_formed": events.get("draft.formed", 0),
            "citations_expanded": events.get("citation.expanded", 0),
            "tool_calls": tool_calls,
            "tool_failures": tool_failures,
            "batches_published": batches.get("published", 0),
            "batches_failed": batches.get("failed", 0),
            "idempotent_hits": int(idempotent_hits or 0),
            "writes_recovered": int(writes_recovered or 0),
        },
        "tasks": {
            "pending": task_states.get("pending", 0),
            "running": task_states.get("running", 0),
            "retry_wait": task_states.get("retry_wait", 0),
            "failed": task_states.get("failed", 0),
        },
        "cleanup": {
            "succeeded": cleanup_succeeded,
            "failed": cleanup_failed,
            "slow": int(slow_cleanups or 0),
        },
    }


__all__ = ["MAX_WINDOW_DAYS", "overview", "school_timezone_name", "window_bounds"]
