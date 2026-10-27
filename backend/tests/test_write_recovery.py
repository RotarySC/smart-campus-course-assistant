"""写入操作恢复（§7.3）：`failed/retryable` 过去没有写入点，pending 会永久卡住。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.adapters.db.models import StudyPlan, WriteOperation
from app.adapters.db.uow import uow
from app.modules.planning.recovery import recover_pending_write_operations
from app.shared.clock import now_utc, to_db
from app.shared.ids import PREFIX_PLAN, new_id


async def _make_pending_operation(user_id: str, operation_id: str, *, age_seconds: int = 600) -> None:
    now = now_utc()
    async with uow() as tx:
        tx.session.add(
            WriteOperation(
                user_id=user_id,
                operation_id=operation_id,
                source="assistant",
                origin_chat_request_id=None,
                authorization_chat_request_id=None,
                draft_id=None,
                draft_version=None,
                content_digest=b"\x01" * 32,
                state="pending",
                resolution="recovering",
                plan_id=None,
                error_code=None,
                retryable=False,
                created_at=to_db(now - timedelta(seconds=age_seconds)),
                updated_at=to_db(now - timedelta(seconds=age_seconds)),
            )
        )
        await tx.commit()


async def _read_operation(user_id: str, operation_id: str) -> WriteOperation:
    async with uow() as tx:
        return await tx.session.get(WriteOperation, (user_id, operation_id))


async def test_pending_without_plan_becomes_retryable_failure(seeded):
    user_id = seeded["student"]["id"]
    operation_id = "op_recover_no_plan"
    await _make_pending_operation(user_id, operation_id)

    counters = await recover_pending_write_operations()

    assert counters["recovered_failed"] >= 1
    operation = await _read_operation(user_id, operation_id)
    assert operation.state == "failed"
    assert operation.retryable is True
    assert operation.resolution == "confirmed"
    assert operation.plan_id is None


async def test_pending_with_plan_is_marked_succeeded(seeded):
    user_id = seeded["student"]["id"]
    operation_id = "op_recover_with_plan"
    await _make_pending_operation(user_id, operation_id)

    now = now_utc()
    plan_id = new_id(PREFIX_PLAN)
    async with uow() as tx:
        tx.session.add(
            StudyPlan(
                id=plan_id,
                user_id=user_id,
                operation_id=operation_id,
                title="恢复用例计划",
                goal=None,
                start_date=None,
                end_date=None,
                content="恢复用例正文",
                source="assistant",
                basis_snapshot=None,
                version=1,
                deleted_at=None,
                created_at=to_db(now),
                updated_at=to_db(now),
            )
        )
        await tx.commit()

    counters = await recover_pending_write_operations()

    assert counters["recovered_succeeded"] >= 1
    operation = await _read_operation(user_id, operation_id)
    assert operation.state == "succeeded"
    assert operation.plan_id == plan_id
    assert operation.retryable is False
    # 核实结果要留事件（FR-OPS-001/002：写入 unknown 已核实可见）
    from app.adapters.db.models import OutboxEvent

    async with uow() as tx:
        events = (
            await tx.session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.event_type == "write_operation.recovered"
                )
            )
        ).scalars().all()
    assert events
    assert events[-1].metadata_json["state"] in ("succeeded", "failed")



async def test_fresh_pending_operation_is_not_touched(seeded):
    """刚建立、可能仍在外层事务里的 pending 不收敛（避免抢跑）。"""
    user_id = seeded["student"]["id"]
    operation_id = "op_recover_fresh"
    await _make_pending_operation(user_id, operation_id, age_seconds=0)

    await recover_pending_write_operations()

    operation = await _read_operation(user_id, operation_id)
    assert operation.state == "pending"
    assert operation.resolution == "recovering"
