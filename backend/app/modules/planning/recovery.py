"""写入操作恢复（详细设计 §7.3 / §5.3；审计 P1 的最后一块）。

背景：`write_operations` 过去只会被写成 `pending(recovering)` 或 `succeeded`，
`failed` / `retryable=true` 从来没有写入点 —— 一次确认回滚的保存会永久停在
pending，客户端既拿不到确定失败、也无法用原键重试（§7.3 明列该状态）。

恢复规则（严格按 §7.3）：
- 只有拿到**操作行锁**才说明前一事务已结束（锁等待超时不能下"未提交"结论）；
- 若同键已有成功计划（`study_plans` 存在）→ 补齐 `succeeded` + `plan_id`，**不新建**；
- 确认没有创建结果 → `failed` + `retryable=true`；同键同内容的重试会复用该操作键，
  重新走授权与保存（不复活已删计划：`deleted` 状态不动）。
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from app.adapters.db.models import StudyPlan, WriteOperation
from app.adapters.db.uow import uow
from app.shared.clock import now_utc, to_db

logger = logging.getLogger("cca.planning.recovery")

# 超过该时长仍停在 pending(recovering) 才允许收敛（避免抢走正在进行的事务）
RECOVER_AFTER_SECONDS = 60
RECOVER_BATCH = 100


async def recover_pending_write_operations(
    *, limit: int = RECOVER_BATCH, older_than_seconds: int = RECOVER_AFTER_SECONDS
) -> dict[str, int]:
    """收敛卡住的写入操作；返回 {recovered_succeeded, recovered_failed, skipped}。"""
    now = now_utc()
    cutoff = to_db(now - timedelta(seconds=older_than_seconds))
    counters = {"recovered_succeeded": 0, "recovered_failed": 0, "skipped": 0}

    async with uow() as tx:
        rows = (
            await tx.session.execute(
                select(WriteOperation)
                .where(
                    WriteOperation.state == "pending",
                    WriteOperation.resolution == "recovering",
                    WriteOperation.updated_at <= cutoff,
                )
                .order_by(WriteOperation.updated_at)
                .limit(limit)
            )
        ).scalars().all()
    candidates = [(row.user_id, row.operation_id) for row in rows]
    if not candidates:
        return counters

    for user_id, operation_id in candidates:
        async with uow() as tx:
            # 行锁 + 重查：拿不到锁说明事务仍在，直接跳过（不臆断未提交）
            operation = await tx.lock_operation(user_id, operation_id)
            if operation is None:
                counters["skipped"] += 1
                await tx.commit()
                continue
            if operation.state != "pending" or operation.resolution != "recovering":
                counters["skipped"] += 1
                await tx.commit()
                continue
            plan = (
                await tx.session.execute(
                    select(StudyPlan).where(
                        StudyPlan.user_id == user_id,
                        StudyPlan.operation_id == operation_id,
                    )
                )
            ).scalar_one_or_none()
            if plan is not None:
                operation.state = "succeeded"
                operation.plan_id = plan.id
                operation.resolution = "confirmed"
                operation.retryable = False
                operation.error_code = None
                counters["recovered_succeeded"] += 1
            else:
                operation.state = "failed"
                operation.resolution = "confirmed"
                operation.retryable = True
                operation.error_code = "INTERNAL_ERROR"
                counters["recovered_failed"] += 1
            operation.updated_at = to_db(now)
            await tx.commit()
            logger.warning(
                "write operation recovered user=%s operation=%s state=%s",
                user_id,
                operation_id,
                operation.state,
            )
    return counters


__all__ = ["recover_pending_write_operations", "RECOVER_AFTER_SECONDS"]
