"""K3：Worker 领取唯一性、租约回收、旧代次禁发、失败退避（真实 MySQL）。"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from sqlalchemy import text

from _knowledge_helpers import (
    count_rows,
    knowledge_storage,  # noqa: F401
    run_worker_once,
    txt_bytes,
    unfreeze_corpus,  # noqa: F401
    upload,
    worker_drain,
)


async def _task_rows(db, *, kind: str | None = None):
    from app.adapters.db.models import BackgroundTask

    async with db() as session:
        statement = __import__("sqlalchemy").select(BackgroundTask)
        if kind:
            statement = statement.where(BackgroundTask.kind == kind)
        return list((await session.execute(statement)).scalars().all())


async def test_claim_is_unique_under_concurrency(client, seeded):
    from app.modules.knowledge.tasks import claim_next

    await upload(client, seeded["admin_headers"], [("并发.txt", txt_bytes("并发领取测试内容。"))])
    results = await asyncio.gather(claim_next("owner-a"), claim_next("owner-b"))
    claimed = [item for item in results if item is not None]
    # publish 任务 1h 后才到期，因此只有一个 doc_persist 可领取
    assert len(claimed) == 1
    assert claimed[0].kind == "doc_persist"

    from app.adapters.db.engine import session_scope

    async with session_scope() as session:
        running = int(
            (
                await session.execute(
                    text("SELECT COUNT(*) FROM background_tasks WHERE state='running'")
                )
            ).scalar_one()
        )
    assert running == 1


async def test_expired_lease_is_recovered_and_old_fence_cannot_commit(client, seeded, db):
    from app.adapters.db.models import DocumentBatch
    from app.adapters.db.uow import uow
    from app.modules.knowledge.tasks import (
        LeaseLost,
        TaskLease,
        claim_next,
        execute_claimed,
        finish_success,
        recover_expired_leases,
    )

    response = await upload(
        client, seeded["admin_headers"], [("租约.txt", txt_bytes("租约过期回收测试。"))]
    )
    batch_id = response.json()["data"]["batch_id"]

    old = await claim_next("worker-old")
    assert old is not None and old.kind == "doc_persist"
    async with db() as session:
        await session.execute(
            text(
                "UPDATE background_tasks SET lease_until = "
                "UTC_TIMESTAMP(6) - INTERVAL 5 SECOND WHERE id=:id"
            ),
            {"id": old.id},
        )
        await session.commit()

    assert await recover_expired_leases() == 1
    new = await claim_next("worker-new")
    assert new is not None
    assert new.id == old.id
    assert new.fence == old.fence + 1
    assert new.attempt == old.attempt + 1

    # 旧代次提交必须失败（owner/fence/lease 三重校验）
    async with uow() as tx:
        try:
            await finish_success(tx.session, TaskLease(claimed=old, owner="worker-old"))
            raise AssertionError("旧代次不应提交成功")
        except LeaseLost:
            await tx.rollback()

    # 新代次可以正常完成发布
    assert await execute_claimed(new, "worker-new") in ("succeeded",)
    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
    assert batch.state == "published"


async def test_lost_lease_execution_cannot_publish(client, seeded, db):
    from app.adapters.db.models import DocumentBatch
    from app.modules.knowledge.tasks import (
        TaskLease,
        claim_next,
        handle_doc_persist,
        recover_expired_leases,
    )

    response = await upload(
        client, seeded["admin_headers"], [("迟到.txt", txt_bytes("丢失租约不得发布。"))]
    )
    batch_id = response.json()["data"]["batch_id"]

    old = await claim_next("worker-old")
    assert old is not None
    async with db() as session:
        await session.execute(
            text(
                "UPDATE background_tasks SET lease_until = "
                "UTC_TIMESTAMP(6) - INTERVAL 5 SECOND WHERE id=:id"
            ),
            {"id": old.id},
        )
        await session.commit()
    await recover_expired_leases()
    new = await claim_next("worker-new")
    assert new is not None and new.id == old.id

    # 旧执行者继续跑完解析/入库，但发布事务中的任务 CAS 必须失败并回滚发布
    from app.modules.knowledge.tasks import LeaseLost

    try:
        await handle_doc_persist(TaskLease(claimed=old, owner="worker-old"))
    except LeaseLost:
        pass
    else:  # pragma: no cover - 不允许成功
        raise AssertionError("旧代次不得完成发布")

    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        visibility = (
            await session.execute(text("SELECT visibility FROM documents LIMIT 1"))
        ).scalar_one()
    assert batch.state == "processing"
    assert visibility == "unpublished"

    # 新代次重试后完成发布
    from app.modules.knowledge.tasks import execute_claimed

    assert await execute_claimed(new, "worker-new") == "succeeded"
    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
    assert batch.state == "published"


async def test_retry_backoff_then_failure_triggers_compensation(client, seeded, db):
    from app.adapters.filestore.local import FileStore
    from app.modules.knowledge.adapters import document_key

    response = await upload(
        client, seeded["admin_headers"], [("缺失.txt", txt_bytes("原件会被删除。"))]
    )
    batch_id = response.json()["data"]["batch_id"]
    document_id = response.json()["data"]["documents"][0]["id"]
    FileStore().delete(document_key(document_id))

    for attempt in range(1, 6):
        if attempt > 1:
            async with db() as session:
                await session.execute(
                    text(
                        "UPDATE background_tasks SET next_run_at = UTC_TIMESTAMP(6) "
                        "WHERE kind='doc_persist' AND state IN ('retry_wait','pending')"
                    )
                )
                await session.commit()
        await run_worker_once()
        async with db() as session:
            task = (
                await session.execute(
                    text(
                        "SELECT state, attempt, error_code, "
                        "TIMESTAMPDIFF(MICROSECOND, UTC_TIMESTAMP(6), next_run_at)/1000000.0 "
                        "AS delay FROM background_tasks WHERE kind='doc_persist'"
                    )
                )
            ).one()
        assert task.error_code == "STORAGE_UNAVAILABLE"
        if attempt < 5:
            assert task.state == "retry_wait", (attempt, task)
            expected = (2, 4, 8, 16)[attempt - 1]
            assert expected * 0.5 <= float(task.delay) <= expected * 1.5 + 0.5, (
                attempt,
                task,
            )
        else:
            assert task.state == "failed"

    await worker_drain(rounds=4)
    async with db() as session:
        batch_state = (
            await session.execute(
                text("SELECT state, error_code FROM document_batches WHERE id=:id"),
                {"id": batch_id},
            )
        ).one()
        doc_state = (
            await session.execute(
                text(
                    "SELECT visibility, processing_state FROM documents WHERE id=:id"
                ),
                {"id": document_id},
            )
        ).one()
    assert batch_state.state == "failed"
    assert batch_state.error_code == "STORAGE_UNAVAILABLE"
    assert doc_state.visibility == "unpublished"
    assert doc_state.processing_state == "failed"
    await count_rows(__import__("app.adapters.db.models", fromlist=["Chunk"]).Chunk) == 0
