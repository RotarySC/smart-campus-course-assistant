"""AT-15 重启恢复（等价重启：租约过期 + 新 owner 接管；不需要真 kill 进程）。

覆盖两条"整链路"结论：
- 入库中途崩溃 → 重启后重跑一次并只发布一次（无半批、无重复版本）；
- 删除清理中途崩溃 → 重启后清理完成、已删文档不复活、旧引用仍是 410。
"""

from __future__ import annotations

from sqlalchemy import select, text

from _knowledge_helpers import (
    API,
    knowledge_storage,  # noqa: F401
    search_evidence,
    txt_bytes,
    unfreeze_corpus,  # noqa: F401
    upload,
    worker_drain,
)


async def _simulate_crash(task_kind: str, object_id: str) -> None:
    """把一个任务停在"某个进程正在跑、租约已过期"的状态（等价于进程被杀）。"""
    from app.adapters.db.engine import session_scope

    async with session_scope() as session:
        await session.execute(
            text(
                "UPDATE background_tasks SET state='running', owner_instance='crashed-worker', "
                "lease_until = UTC_TIMESTAMP(6) - INTERVAL 5 MINUTE, "
                "next_run_at = UTC_TIMESTAMP(6) - INTERVAL 5 MINUTE, attempt = 1, fence = 1, "
                "updated_at = UTC_TIMESTAMP(6) "
                "WHERE kind=:kind AND object_id=:oid"
            ),
            {"kind": task_kind, "oid": object_id},
        )
        await session.commit()


async def test_restart_reprocesses_orphaned_persist_and_publishes_once(client, seeded, db):
    from app.adapters.db.models import Document, DocumentBatch, DocumentVersion

    response = await upload(
        client, seeded["admin_headers"], [("重启入库.txt", txt_bytes("重启入库内容：数组与链表。"))]
    )
    assert response.status_code == 202, response.text
    batch_id = response.json()["data"]["batch_id"]
    document_id = response.json()["data"]["documents"][0]["id"]

    async with db() as session:
        version_id = (
            await session.execute(
                text("SELECT id FROM document_versions WHERE document_id=:did"),
                {"did": document_id},
            )
        ).scalar_one()
    # doc_persist 任务的 object_id 是版本 ID，不是文档 ID
    await _simulate_crash("doc_persist", version_id)

    # 新进程接管：先回收过期租约，再重跑任务直到排空
    result = await worker_drain(rounds=8)
    assert result["processed"] >= 1

    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        document = await session.get(Document, document_id)
        versions = list(
            (
                await session.execute(
                    select(DocumentVersion).where(DocumentVersion.document_id == document_id)
                )
            )
            .scalars()
            .all()
        )
        revision = (
            await session.execute(
                text("SELECT revision FROM corpus_control WHERE singleton_id = 1")
            )
        ).scalar_one()
        task_row = (
            await session.execute(
                text(
                    "SELECT state, attempt, error_code FROM background_tasks "
                    "WHERE kind='doc_persist' AND object_id=:oid"
                ),
                {"oid": version_id},
            )
        ).first()

    # 只发布一次、只有一个 active 版本、没有半批
    assert batch.state == "published"
    assert int(revision) == 1
    assert document.visibility == "shared"
    assert len(versions) == 1
    assert versions[0].state == "active"
    assert task_row.state == "succeeded"
    assert task_row.attempt >= 2  # 崩溃那次 + 重启后重跑

    evidence = await search_evidence(seeded, "重启入库内容")
    assert evidence.status == "ok"
    assert all(ref.document_id == document_id for ref in evidence.references)


async def test_restart_completes_orphaned_cleanup_and_never_resurrects(client, seeded, db):
    from app.adapters.db.models import Document

    response = await upload(
        client, seeded["admin_headers"], [("重启删除.txt", txt_bytes("重启删除内容。"))]
    )
    assert response.status_code == 202, response.text
    document_id = response.json()["data"]["documents"][0]["id"]
    await worker_drain()

    document = await client.get(
        f"{API}/admin/documents", headers=seeded["admin_headers"]
    )
    assert document.status_code == 200
    row = next(item for item in document.json()["data"]["items"] if item["id"] == document_id)

    old_evidence = await search_evidence(seeded, "重启删除内容")
    old_ref = next(ref for ref in old_evidence.references if ref.document_id == document_id)

    deleted = await client.delete(
        f"{API}/admin/documents/{document_id}?expected_version={row['version']}",
        headers=seeded["admin_headers"],
    )
    assert deleted.status_code == 202, deleted.text

    # 清理任务被"杀掉"：running + 过期租约
    await _simulate_crash("doc_cleanup", document_id)

    await worker_drain(rounds=6)

    async with db() as session:
        document_row = await session.get(Document, document_id)
    assert document_row.visibility == "removed"
    assert document_row.processing_state == "deleted"
    assert document_row.cleanup_state == "succeeded"

    # 不复活：检索不再命中、旧引用仍是 410
    evidence = await search_evidence(seeded, "重启删除内容")
    assert all(ref.document_id != document_id for ref in evidence.references)
    old_citation = await client.get(
        f"{API}/citations/{old_ref.reference_id}", headers=seeded["student_headers"]
    )
    assert old_citation.status_code == 410
