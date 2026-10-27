"""FR-DOC-007 / 设计 §10.1：孤立文件巡检与清理超时告警。"""

from __future__ import annotations

import os
import time

from sqlalchemy import select, text

from _knowledge_helpers import (
    API,
    knowledge_storage,  # noqa: F401
    txt_bytes,
    upload,
    worker_drain,
)


async def _publish_one(client, seeded, name: str = "巡检.txt", content: str = "巡检内容。"):
    response = await upload(client, seeded["admin_headers"], [(name, txt_bytes(content))])
    assert response.status_code == 202, response.text
    document_id = response.json()["data"]["documents"][0]["id"]
    await worker_drain()
    return document_id


def _backdate(path, *, seconds: int = 7200) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


async def test_sweep_removes_only_old_unreferenced_files(client, seeded, db):
    """只删「无引用 + 够久」的文件；已被行引用的原件与 attempt 产物必须保留。"""
    from app.adapters.filestore.local import FileStore
    from app.modules.knowledge.adapters import document_key, file_store
    from app.modules.knowledge.sweep import sweep_orphan_objects

    document_id = await _publish_one(client, seeded)
    store: FileStore = file_store()

    referenced_original = document_key(document_id)
    assert store.exists(referenced_original)

    async with db() as session:
        attempt_prefix = (
            await session.execute(
                text(
                    "SELECT file_prefix FROM storage_attempts WHERE version_id IN "
                    "(SELECT id FROM document_versions WHERE document_id=:did)"
                ),
                {"did": document_id},
            )
        ).scalar_one()

    # 造三类孤儿：文档原件、attempt 产物、暂存原件（都没有行指向它们）
    orphans = {
        "documents": "documents/doc_orphan_for_sweep/original",
        "attempts": "attempts/task_orphan/0/dvs_orphan/extracted-text",
        "uploads": "uploads/upl_orphan_for_sweep/sealed-original",
    }
    for key in orphans.values():
        store.write_bytes(key, b"orphan")
        _backdate(store.path_of(key))

    # 一个"太新"的孤儿：必须保留（在途写入保护）
    recent_key = "documents/doc_recent_orphan/original"
    store.write_bytes(recent_key, b"recent")

    result = await sweep_orphan_objects()

    assert result["documents"] == 1
    assert result["attempts"] == 1
    assert result["uploads"] == 1
    assert result["kept_recent"] >= 1
    assert result["errors"] == 0

    for group, key in orphans.items():
        assert not store.exists(key), f"{group} 孤儿未被清理：{key}"
    assert store.exists(recent_key)
    assert store.exists(referenced_original)
    assert store.list_keys(attempt_prefix)

    # 巡检自身留审计
    from app.adapters.db.models import AuditEvent

    async with db() as session:
        audit = (
            await session.execute(
                select(AuditEvent)
                .where(AuditEvent.action == "storage.orphan_sweep")
                .order_by(AuditEvent.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
    assert audit.metadata_json["documents"] == 1


async def test_cleanup_over_target_is_recorded(client, seeded, db):
    """清理超过 5 分钟目标时要留记录（FR-DOC-007 / NFR-REL-002）。"""
    from app.adapters.db.models import AuditEvent

    document_id = await _publish_one(client, seeded, "超时清理.txt", "超时清理内容。")

    deleted = await client.delete(
        f"{API}/admin/documents/{document_id}?expected_version=1",
        headers=seeded["admin_headers"],
    )
    assert deleted.status_code == 202, deleted.text

    # 把清理任务入队时间往前挪 10 分钟，模拟排空延迟
    async with db() as session:
        await session.execute(
            text(
                "UPDATE background_tasks SET created_at = created_at - INTERVAL 10 MINUTE "
                "WHERE kind='doc_cleanup' AND object_id=:did"
            ),
            {"did": document_id},
        )
        await session.commit()

    await worker_drain(rounds=6)

    async with db() as session:
        audit = (
            await session.execute(
                select(AuditEvent)
                .where(
                    AuditEvent.action == "document.cleanup",
                    AuditEvent.object_id == document_id,
                )
                .order_by(AuditEvent.created_at.desc())
                .limit(1)
            )
        ).scalar_one()

    assert audit.result == "success"
    assert audit.metadata_json["slow_cleanup"] is True
    assert audit.metadata_json["cleanup_seconds"] >= 600
