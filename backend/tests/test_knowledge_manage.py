"""K8/K9：文档列表/文本预览、重建切版、删除立即不可见、清理与重试、引用 410。"""

from __future__ import annotations

from sqlalchemy import func, select, text

from _knowledge_helpers import (
    API,
    count_rows,
    get_document_row,
    knowledge_storage,  # noqa: F401
    publish_batch,
    search_evidence,
    txt_bytes,
    unfreeze_corpus,  # noqa: F401
    upload,
    worker_drain,
)


async def _publish_document(client, seeded, name: str, content: str) -> tuple[str, dict]:
    response = await upload(client, seeded["admin_headers"], [(name, txt_bytes(content))])
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    await worker_drain()
    document_id = data["documents"][0]["id"]
    return document_id, data


# --------------------------------------------------------------------------- #
# 列表 / 文本预览
# --------------------------------------------------------------------------- #
async def test_list_documents_pagination_and_filters(client, seeded):
    await publish_batch(
        client,
        seeded["admin_headers"],
        [
            ("课程A.txt", txt_bytes("课程A的内容甲。")),
            ("课程B.md", txt_bytes("课程B的内容乙。")),
            ("规则.txt", txt_bytes("规则内容丙。")),
        ],
    )

    first = await client.get(
        f"{API}/admin/documents?page=1&page_size=2", headers=seeded["admin_headers"]
    )
    assert first.status_code == 200
    payload = first.json()["data"]
    assert payload["total"] == 3
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert len(payload["items"]) == 2

    second = await client.get(
        f"{API}/admin/documents?page=2&page_size=2", headers=seeded["admin_headers"]
    )
    assert len(second.json()["data"]["items"]) == 1

    filtered = await client.get(
        f"{API}/admin/documents?name=课程", headers=seeded["admin_headers"]
    )
    assert filtered.json()["data"]["total"] == 2

    by_state = await client.get(
        f"{API}/admin/documents?state=available", headers=seeded["admin_headers"]
    )
    assert by_state.json()["data"]["total"] == 3
    empty_state = await client.get(
        f"{API}/admin/documents?state=failed", headers=seeded["admin_headers"]
    )
    assert empty_state.json()["data"]["total"] == 0

    forbidden = await client.get(f"{API}/admin/documents", headers=seeded["student_headers"])
    assert forbidden.status_code == 403
    unknown_param = await client.get(
        f"{API}/admin/documents?foo=1", headers=seeded["admin_headers"]
    )
    assert unknown_param.status_code == 422


async def test_preview_document_offset_and_errors(client, seeded):
    document_id, data = await _publish_document(
        client, seeded, "长文本.txt", "第一段内容。" * 20
    )
    preview = await client.get(
        f"{API}/admin/documents/{document_id}/text?offset=0&limit=12",
        headers=seeded["admin_headers"],
    )
    assert preview.status_code == 200
    payload = preview.json()["data"]
    assert len(payload["text"]) <= 12
    assert payload["offset"] == 0
    assert payload["next_offset"] is not None

    tail = await client.get(
        f"{API}/admin/documents/{document_id}/text?offset=995&limit=100",
        headers=seeded["admin_headers"],
    )
    assert tail.status_code == 200
    assert tail.json()["data"]["next_offset"] is None

    missing = await client.get(
        f"{API}/admin/documents/doc_missing/text", headers=seeded["admin_headers"]
    )
    assert missing.status_code == 404
    bad_limit = await client.get(
        f"{API}/admin/documents/{document_id}/text?limit=0",
        headers=seeded["admin_headers"],
    )
    assert bad_limit.status_code == 422


# --------------------------------------------------------------------------- #
# 重建
# --------------------------------------------------------------------------- #
async def test_rebuild_switches_version_and_invalidates_old_citation(client, seeded, db):
    from app.adapters.db.models import DocumentVersion

    document_id, _ = await _publish_document(
        client, seeded, "重建.txt", "旧版本内容：数组与链表。"
    )
    document = await get_document_row(document_id)
    old_version_id = document.active_version_id
    old_evidence = await search_evidence(seeded, "数组")
    old_ref = next(ref for ref in old_evidence.references if ref.document_id == document_id)

    rebuilt = await client.post(
        f"{API}/admin/documents/{document_id}/rebuild",
        json={"expected_version": int(document.version)},
        headers={**seeded["admin_headers"], "Idempotency-Key": "rebuild-key-1"},
    )
    assert rebuilt.status_code == 202, rebuilt.text
    mutation = rebuilt.json()["data"]
    assert set(mutation) == {"document_id", "visibility", "task", "version"}
    assert mutation["visibility"] == "shared"
    assert mutation["task"]["state"] == "pending"
    task_id = mutation["task"]["task_id"]

    # 重建进行中：旧版仍可检索，旧引用仍有效
    mid = await search_evidence(seeded, "数组")
    assert mid.status == "ok"
    assert all(ref.version_id == old_version_id for ref in mid.references)
    old_citation = await client.get(
        f"{API}/citations/{old_ref.reference_id}", headers=seeded["student_headers"]
    )
    assert old_citation.status_code == 200

    # 完成切换：新版本 active、旧版 retired、revision 递增
    await worker_drain()
    document = await get_document_row(document_id)
    assert document.active_version_id != old_version_id
    async with db() as session:
        old_version = await session.get(DocumentVersion, old_version_id)
        new_version = await session.get(DocumentVersion, document.active_version_id)
        revision = int(
            (
                await session.execute(
                    text("SELECT revision FROM corpus_control WHERE singleton_id=1")
                )
            ).scalar_one()
        )
    assert old_version.state == "retired"
    assert new_version.state == "active"
    assert revision == 2

    new_evidence = await search_evidence(seeded, "数组")
    assert new_evidence.status == "ok"
    assert all(ref.version_id == new_version.id for ref in new_evidence.references)
    new_ref = next(ref for ref in new_evidence.references if ref.document_id == document_id)
    assert new_ref.reference_id != old_ref.reference_id
    new_citation = await client.get(
        f"{API}/citations/{new_ref.reference_id}", headers=seeded["student_headers"]
    )
    assert new_citation.status_code == 200

    # 旧引用 410（切版失效）
    invalid = await client.get(
        f"{API}/citations/{old_ref.reference_id}", headers=seeded["student_headers"]
    )
    assert invalid.status_code == 410
    assert invalid.json()["error"]["code"] == "CITATION_UNAVAILABLE"

    # 幂等重放：同一 Idempotency-Key 返回原任务，不再建新版本
    replay = await client.post(
        f"{API}/admin/documents/{document_id}/rebuild",
        json={"expected_version": int(document.version)},
        headers={**seeded["admin_headers"], "Idempotency-Key": "rebuild-key-1"},
    )
    assert replay.status_code == 202
    assert replay.json()["data"]["task"]["task_id"] == task_id
    async with db() as session:
        version_count = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(DocumentVersion)
                    .where(DocumentVersion.document_id == document_id)
                )
            ).scalar_one()
        )
    assert version_count == 2


async def test_rebuild_busy_conflict_and_validation(client, seeded):
    document_id, _ = await _publish_document(
        client, seeded, "并发重建.txt", "并发重建测试内容。"
    )
    document = await get_document_row(document_id)
    first = await client.post(
        f"{API}/admin/documents/{document_id}/rebuild",
        json={"expected_version": int(document.version)},
        headers={**seeded["admin_headers"], "Idempotency-Key": "busy-1"},
    )
    assert first.status_code == 202
    second = await client.post(
        f"{API}/admin/documents/{document_id}/rebuild",
        json={"expected_version": int(document.version) + 1},
        headers={**seeded["admin_headers"], "Idempotency-Key": "busy-2"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DOCUMENT_BUSY"

    # 重建进行中删除也返回 DOCUMENT_BUSY
    blocked_delete = await client.delete(
        f"{API}/admin/documents/{document_id}?expected_version={int(document.version) + 1}",
        headers=seeded["admin_headers"],
    )
    assert blocked_delete.status_code == 409
    assert blocked_delete.json()["error"]["code"] == "DOCUMENT_BUSY"

    # 缺少 Idempotency-Key / 版本不匹配
    missing_key = await client.post(
        f"{API}/admin/documents/{document_id}/rebuild",
        json={"expected_version": 3},
        headers=seeded["admin_headers"],
    )
    assert missing_key.status_code == 422

    await worker_drain(rounds=4)
    document = await get_document_row(document_id)
    stale = await client.post(
        f"{API}/admin/documents/{document_id}/rebuild",
        json={"expected_version": 1},
        headers={**seeded["admin_headers"], "Idempotency-Key": "stale-1"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"


# --------------------------------------------------------------------------- #
# 删除 / 清理
# --------------------------------------------------------------------------- #
async def test_delete_immediately_invisible_then_cleanup(client, seeded, db):
    from app.adapters.db.models import Chunk, CitationReference, Document
    from app.adapters.filestore.local import FileStore
    from app.modules.knowledge.adapters import document_key

    document_id, _ = await _publish_document(
        client, seeded, "待删除.txt", "待删除的资料内容。"
    )
    document = await get_document_row(document_id)
    evidence = await search_evidence(seeded, "待删除")
    reference = next(ref for ref in evidence.references if ref.document_id == document_id)
    original_key = document_key(document_id)
    assert FileStore().exists(original_key)

    deleted = await client.delete(
        f"{API}/admin/documents/{document_id}?expected_version={int(document.version)}",
        headers=seeded["admin_headers"],
    )
    assert deleted.status_code == 202, deleted.text
    payload = deleted.json()["data"]
    assert payload["visibility"] == "removed"
    assert payload["task"]["state"] == "pending"
    cleanup_task_id = payload["task"]["task_id"]

    # 立即不可见 + 引用 410
    after = await search_evidence(seeded, "待删除")
    assert after.status == "empty"
    assert after.corpus_empty is True
    invalid = await client.get(
        f"{API}/citations/{reference.reference_id}", headers=seeded["student_headers"]
    )
    assert invalid.status_code == 410

    # 幂等重放删除（带新版本号）返回同一清理任务
    replay = await client.delete(
        f"{API}/admin/documents/{document_id}?expected_version={payload['version']}",
        headers=seeded["admin_headers"],
    )
    assert replay.status_code == 202
    assert replay.json()["data"]["task"]["task_id"] == cleanup_task_id

    # 错误版本号 → VERSION_CONFLICT
    stale = await client.delete(
        f"{API}/admin/documents/{document_id}?expected_version=1",
        headers=seeded["admin_headers"],
    )
    assert stale.status_code == 409

    await worker_drain()
    document = await get_document_row(document_id)
    assert document.visibility == "removed"
    assert document.processing_state == "deleted"
    assert document.cleanup_state == "succeeded"
    assert document.active_version_id is None
    assert document.original_storage_key is None
    assert not FileStore().exists(original_key)
    async with db() as session:
        chunks = int(
            (
                await session.execute(
                    select(func.count()).select_from(Chunk).where(Chunk.document_id == document_id)
                )
            ).scalar_one()
        )
        active_refs = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(CitationReference)
                    .where(
                        CitationReference.document_id == document_id,
                        CitationReference.revoked_at.is_(None),
                    )
                )
            ).scalar_one()
        )
    assert chunks == 0
    assert active_refs == 0

    # 清理成功后再重试：不恢复可见性，返回既有任务
    retry = await client.post(
        f"{API}/admin/documents/{document_id}/cleanup-retry",
        headers={**seeded["admin_headers"], "Idempotency-Key": "cleanup-after-done"},
    )
    assert retry.status_code == 202
    assert retry.json()["data"]["visibility"] == "removed"
    document = await get_document_row(document_id)
    assert document.visibility == "removed"


async def test_cleanup_retry_only_advances_removal(client, seeded, db):
    document_id, _ = await _publish_document(
        client, seeded, "清理重试.txt", "清理重试的资料。"
    )
    document = await get_document_row(document_id)
    deleted = await client.delete(
        f"{API}/admin/documents/{document_id}?expected_version={int(document.version)}",
        headers=seeded["admin_headers"],
    )
    assert deleted.status_code == 202
    await worker_drain()
    document = await get_document_row(document_id)
    assert document.cleanup_state == "succeeded"

    # 模拟一次失败：清理状态 failed，但可见性仍 removed
    async with db() as session:
        await session.execute(
            text(
                "UPDATE documents SET cleanup_state='failed', "
                "processing_state='delete_failed', mutation_task_id=NULL, "
                "version=version+1 WHERE id=:id"
            ),
            {"id": document_id},
        )
        await session.commit()

    retry = await client.post(
        f"{API}/admin/documents/{document_id}/cleanup-retry",
        headers={**seeded["admin_headers"], "Idempotency-Key": "cleanup-retry-1"},
    )
    assert retry.status_code == 202, retry.text
    payload = retry.json()["data"]
    assert payload["visibility"] == "removed"
    assert payload["task"]["state"] == "pending"

    await worker_drain()
    document = await get_document_row(document_id)
    assert document.visibility == "removed"
    assert document.cleanup_state == "succeeded"
    assert document.processing_state == "deleted"

    # 对未删除文档重试清理 → DOCUMENT_BUSY
    other_id, _ = await _publish_document(client, seeded, "未删除.txt", "未删除内容。")
    bad_retry = await client.post(
        f"{API}/admin/documents/{other_id}/cleanup-retry",
        headers={**seeded["admin_headers"], "Idempotency-Key": "not-removed"},
    )
    assert bad_retry.status_code == 409
    assert bad_retry.json()["error"]["code"] == "DOCUMENT_BUSY"
    other = await get_document_row(other_id)
    assert other.visibility == "shared"


async def test_delete_validation(client, seeded):
    document_id, _ = await _publish_document(client, seeded, "删除校验.txt", "内容。")
    document = await get_document_row(document_id)
    missing_version = await client.delete(
        f"{API}/admin/documents/{document_id}", headers=seeded["admin_headers"]
    )
    assert missing_version.status_code == 422
    forbidden = await client.delete(
        f"{API}/admin/documents/{document_id}?expected_version={int(document.version)}",
        headers=seeded["student_headers"],
    )
    assert forbidden.status_code == 403
    missing = await client.delete(
        f"{API}/admin/documents/doc_missing?expected_version=1",
        headers=seeded["admin_headers"],
    )
    assert missing.status_code == 404


# --------------------------------------------------------------------------- #
# 清理失败不得先报成功（FR-DOC-006 / SRS §7.2「清理成功才报告完成」）
# --------------------------------------------------------------------------- #
async def test_cleanup_failure_is_not_reported_as_success(client, seeded, db, monkeypatch):
    from app.adapters.filestore.local import FileStore, StorageError
    from app.modules.knowledge.adapters import document_key

    document_id, _ = await _publish_document(
        client, seeded, "清理失败.txt", "清理失败的资料内容。"
    )
    document = await get_document_row(document_id)
    original_key = document_key(document_id)
    assert FileStore().exists(original_key)

    deleted = await client.delete(
        f"{API}/admin/documents/{document_id}?expected_version={int(document.version)}",
        headers=seeded["admin_headers"],
    )
    assert deleted.status_code == 202

    # 故障注入：外部产物删不掉（原文件 = 最后一步，前缀删除成功也会被它挡住）
    def boom(self, prefix: str) -> int:
        raise StorageError("injected cleanup failure")

    monkeypatch.setattr(FileStore, "delete_prefix", boom)
    await worker_drain()

    document = await get_document_row(document_id)
    assert document.visibility == "removed"  # 已不可见（不可见标记先行，不受清理失败影响）
    assert document.cleanup_state != "succeeded"  # 核心：不得先报成功
    assert document.processing_state != "deleted"
    assert FileStore().exists(original_key)  # 产物确实还在，状态与事实一致

    # 依赖恢复 + 退避到期 → 才允许报 succeeded
    async with db() as session:
        await session.execute(
            text(
                "UPDATE background_tasks SET next_run_at = UTC_TIMESTAMP(6) "
                "WHERE object_id = :id AND state = 'retry_wait'"
            ),
            {"id": document_id},
        )
        await session.commit()
    monkeypatch.undo()
    await worker_drain()

    document = await get_document_row(document_id)
    assert document.cleanup_state == "succeeded"
    assert document.processing_state == "deleted"
    assert not FileStore().exists(original_key)


async def test_rebuild_failure_keeps_old_version_active(client, seeded, db, monkeypatch):
    """AT-13 失败半边：重建失败 → 旧版仍 active、旧引用仍 200、失败产物被回收。"""
    from app.adapters.db.models import DocumentVersion, StorageAttempt
    from app.adapters.vector.local import VectorStoreError
    from app.modules.knowledge import tasks as tasks_mod
    from app.modules.knowledge.adapters import file_store, vector_store

    document_id, _ = await _publish_document(
        client, seeded, "重建失败.txt", "旧内容：数组与链表。"
    )
    document = await get_document_row(document_id)
    old_version_id = document.active_version_id
    old_evidence = await search_evidence(seeded, "数组")
    old_ref = next(ref for ref in old_evidence.references if ref.document_id == document_id)

    rebuilt = await client.post(
        f"{API}/admin/documents/{document_id}/rebuild",
        json={"expected_version": int(document.version)},
        headers={**seeded["admin_headers"], "Idempotency-Key": "rebuild-fail-1"},
    )
    assert rebuilt.status_code == 202, rebuilt.text

    # 把重试预算降到 1 次，让"登记 attempt 之后的失败"一次就走到终态（免去退避等待）
    async with db() as session:
        await session.execute(
            text(
                "UPDATE background_tasks SET max_attempts = 1 WHERE kind='doc_persist' "
                "AND object_id IN (SELECT id FROM document_versions WHERE document_id=:did)"
            ),
            {"did": document_id},
        )
        await session.commit()

    real_vs = vector_store()

    class _BrokenUpsert:
        async def upsert(self, namespace, items, *, fence):
            raise VectorStoreError("模拟重建向量写入失败")

        def __getattr__(self, name):
            return getattr(real_vs, name)

    monkeypatch.setattr(tasks_mod, "vector_store", lambda: _BrokenUpsert())
    await worker_drain(rounds=6)

    document = await get_document_row(document_id)
    async with db() as session:
        versions = list(
            (
                await session.execute(
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id == document_id)
                    .order_by(DocumentVersion.id)
                )
            )
            .scalars()
            .all()
        )
        task_row = (
            await session.execute(
                text(
                    "SELECT state, error_code FROM background_tasks "
                    "WHERE kind='doc_persist' AND object_id IN "
                    "(SELECT id FROM document_versions WHERE document_id=:did) "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"did": document_id},
            )
        ).first()

    # 旧版不动、文档恢复可改、互斥解除
    assert document.active_version_id == old_version_id
    assert document.processing_state == "available"
    assert document.mutation_task_id is None
    new_versions = [v for v in versions if v.id != old_version_id]
    assert new_versions and all(v.state == "failed" for v in new_versions)
    assert new_versions[-1].error_code == "STORAGE_UNAVAILABLE"
    assert task_row.state == "failed"
    assert task_row.error_code == "STORAGE_UNAVAILABLE"

    # 旧版仍可检索、旧引用仍可展开（失败不产生半切版）
    mid = await search_evidence(seeded, "数组")
    assert mid.status == "ok"
    assert all(ref.version_id == old_version_id for ref in mid.references)
    old_citation = await client.get(
        f"{API}/citations/{old_ref.reference_id}", headers=seeded["student_headers"]
    )
    assert old_citation.status_code == 200

    # 失败版本的 attempt 产物必须回收（FR-DOC-007 / 设计 §10.1）
    failed_version_ids = [v.id for v in new_versions]
    async with db() as session:
        failed_attempts = list(
            (
                await session.execute(
                    select(StorageAttempt).where(
                        StorageAttempt.version_id.in_(failed_version_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
    assert failed_attempts
    assert all(attempt.io_state == "cleaned" for attempt in failed_attempts)
    store = file_store()
    vs = vector_store()
    for attempt in failed_attempts:
        assert store.list_keys(attempt.file_prefix) == []
        assert await vs.namespace_chunk_ids(attempt.vector_namespace) == []


async def test_preview_reports_unavailable_reason(client, seeded):
    """FR-DOC-004：预览不可用要给原因（处理中 / 解析失败），不是一律 404。"""
    # 1) 已接受但还没跑 worker → 处理中
    pending = await upload(
        client, seeded["admin_headers"], [("待处理.txt", txt_bytes("待处理内容。"))]
    )
    assert pending.status_code == 202, pending.text
    pending_id = pending.json()["data"]["documents"][0]["id"]

    first = await client.get(
        f"{API}/admin/documents/{pending_id}/text", headers=seeded["admin_headers"]
    )
    assert first.status_code == 200, first.text
    payload = first.json()["data"]
    assert payload["state"] == "processing"
    assert payload["text"] == ""
    assert payload["next_offset"] is None

    # 2) 整批补偿（空白文本 → NO_TEXT_EXTRACTED）→ 解析失败
    failed = await upload(
        client, seeded["admin_headers"], [("空白.txt", txt_bytes("   \n\t\n  "))]
    )
    assert failed.status_code == 202, failed.text
    failed_id = failed.json()["data"]["documents"][0]["id"]
    await worker_drain(rounds=8)

    second = await client.get(
        f"{API}/admin/documents/{failed_id}/text", headers=seeded["admin_headers"]
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["state"] == "parse_failed"
    assert second.json()["data"]["text"] == ""

    # 3) 已发布 → available（对照组）
    published_id, _ = await _publish_document(client, seeded, "可预览.txt", "可预览内容。")
    third = await client.get(
        f"{API}/admin/documents/{published_id}/text", headers=seeded["admin_headers"]
    )
    assert third.status_code == 200
    assert third.json()["data"]["state"] == "available"
    assert third.json()["data"]["text"].strip()
