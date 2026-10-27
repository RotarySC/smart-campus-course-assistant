"""K6：入库/整批发布事务、失败补偿、发布冻结语义（真实 MySQL + 真实文件）。"""

from __future__ import annotations

from sqlalchemy import func, select, text

from _knowledge_helpers import (
    API,
    count_rows,
    knowledge_storage,  # noqa: F401
    publish_batch,
    run_worker_once,
    txt_bytes,
    unfreeze_corpus,  # noqa: F401
    upload,
    worker_drain,
)


async def _batch_state(batch_id: str):
    from app.adapters.db.engine import session_scope
    from app.adapters.db.models import CorpusControl, DocumentBatch

    async with session_scope() as session:
        batch = await session.get(DocumentBatch, batch_id)
        corpus = await session.get(CorpusControl, 1)
        return batch, int(corpus.revision)


async def test_worker_publishes_batch_and_chunks_are_searchable(client, seeded, db):
    from app.adapters.db.models import (
        BackgroundTask,
        Chunk,
        CitationReference,
        Document,
        DocumentBatch,
        DocumentVersion,
    )

    files = [
        ("数据结构.md", txt_bytes("第一章 数组与链表。链表适合频繁插入删除。")),
        ("评分规则.txt", txt_bytes("平时成绩占百分之四十，期末占百分之六十。")),
    ]
    response = await upload(client, seeded["admin_headers"], files)
    assert response.status_code == 202, response.text
    batch_id = response.json()["data"]["batch_id"]
    document_ids = [item["id"] for item in response.json()["data"]["documents"]]

    # 发布前：整批不可见
    batch, revision = await _batch_state(batch_id)
    assert batch.state == "accepted"
    assert revision == 0

    result = await worker_drain()
    assert result["processed"] >= 2  # 两个持久任务；最后一个在发布事务中收尾发布任务

    batch, revision = await _batch_state(batch_id)
    assert batch.state == "published"
    assert batch.published_at is not None
    assert revision == 1

    async with db() as session:
        docs = list(
            (
                await session.execute(select(Document).where(Document.id.in_(document_ids)))
            )
            .scalars()
            .all()
        )
        versions = list(
            (
                await session.execute(
                    select(DocumentVersion).where(
                        DocumentVersion.document_id.in_(document_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        tasks = list((await session.execute(select(BackgroundTask))).scalars().all())
    assert all(doc.visibility == "shared" for doc in docs)
    assert all(doc.processing_state == "available" for doc in docs)
    assert all(doc.active_version_id is not None for doc in docs)
    assert all(version.state == "active" for version in versions)
    assert {task.state for task in tasks} == {"succeeded"}

    assert await count_rows(Chunk) >= 2
    citation_count = await count_rows(CitationReference)
    assert citation_count >= 2

    # 检索：按语义候选 + 关系库复核返回可引用的片段
    from app.modules.knowledge import SearchQuery, knowledge
    from app.shared.context import ActorContext

    actor = ActorContext(
        user_id=seeded["student"]["id"],
        session_id="ses_search",
        auth_version=1,
        role="student",
        trace_request_id="req_search",
    )
    evidence = await knowledge.search(actor, SearchQuery(query="评分规则 平时成绩"))
    assert evidence.status == "ok"
    assert evidence.corpus_empty is False
    assert evidence.revision == 1
    assert evidence.chunks
    assert evidence.references
    chunk = evidence.chunks[0]
    reference = evidence.references[0]
    assert chunk.reference_id == reference.reference_id
    assert reference.file_name in {"数据结构.md", "评分规则.txt"}
    assert reference.location_label
    assert "storage" not in reference.to_dict()
    assert set(reference.to_dict()) <= {
        "reference_id",
        "document_id",
        "version_id",
        "file_name",
        "location_label",
        "page_number",
    }

    # 引用展开：返回片段文本，且不含内部存储键
    citation = await client.get(
        f"{API}/citations/{reference.reference_id}",
        headers=seeded["student_headers"],
    )
    assert citation.status_code == 200, citation.text
    payload = citation.json()["data"]
    assert set(payload) == {"reference", "text"}
    assert payload["text"].strip()
    assert "original_storage_key" not in citation.text
    assert "documents/" not in citation.text

    # 管理员文档列表 + 文本预览（真实落盘文本）
    listing = await client.get(f"{API}/admin/documents", headers=seeded["admin_headers"])
    assert listing.status_code == 200
    page = listing.json()["data"]
    assert set(page) == {"items", "page", "page_size", "total"}
    assert page["total"] == 2
    assert all(item["visibility"] == "shared" for item in page["items"])

    preview = await client.get(
        f"{API}/admin/documents/{document_ids[0]}/text?offset=0&limit=10",
        headers=seeded["admin_headers"],
    )
    assert preview.status_code == 200, preview.text
    text_payload = preview.json()["data"]
    assert set(text_payload) == {
        "document_id",
        "version_id",
        "offset",
        "next_offset",
        "text",
        "state",
    }
    assert text_payload["state"] == "available"
    assert len(text_payload["text"]) <= 10


async def test_batch_compensates_when_one_file_has_no_text(client, seeded, db):
    from app.adapters.db.models import (
        Chunk,
        CitationReference,
        Document,
        DocumentBatch,
        DocumentVersion,
    )
    from app.adapters.filestore.local import FileStore
    from app.modules.knowledge.adapters import document_key

    files = [
        ("正常.txt", txt_bytes("这是正常内容，应该被解析。")),
        ("空白.txt", txt_bytes("   \n\t\n  ")),
    ]
    response = await upload(client, seeded["admin_headers"], files)
    assert response.status_code == 202
    batch_id = response.json()["data"]["batch_id"]
    document_ids = [item["id"] for item in response.json()["data"]["documents"]]

    await worker_drain(rounds=8)

    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        docs = list(
            (
                await session.execute(
                    select(Document).where(Document.batch_id == batch_id)
                )
            )
            .scalars()
            .all()
        )
        versions = list(
            (
                await session.execute(
                    select(DocumentVersion).where(
                        DocumentVersion.document_id.in_(document_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
    assert batch.state == "failed"
    assert batch.error_code == "NO_TEXT_EXTRACTED"
    assert all(doc.visibility == "unpublished" for doc in docs)
    assert all(doc.processing_state == "failed" for doc in docs)
    assert all(version.state == "failed" for version in versions)
    assert await count_rows(Chunk) == 0
    # 引用可保留"不含正文的失效墓碑"，但不得有仍有效的引用
    async with db() as session:
        active_citations = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(CitationReference)
                    .where(CitationReference.revoked_at.is_(None))
                )
            ).scalar_one()
        )
    assert active_citations == 0

    # 补偿清理：原件与暂存区已删除（其他批次不受影响）
    store = FileStore()
    for document_id in document_ids:
        assert not store.exists(document_key(document_id))
    assert store.list_keys("uploads") == []

    # 检索不可见
    from app.modules.knowledge import SearchQuery, knowledge
    from app.shared.context import ActorContext

    actor = ActorContext(
        user_id=seeded["student"]["id"],
        session_id="ses_search",
        auth_version=1,
        role="student",
        trace_request_id="req_search",
    )
    evidence = await knowledge.search(actor, SearchQuery(query="正常内容"))
    assert evidence.status == "empty"
    assert evidence.corpus_empty is True


async def test_publish_frozen_defers_without_failing(client, seeded, db):
    from app.adapters.db.models import Document, DocumentBatch, DocumentVersion

    async with db() as session:
        await session.execute(
            text("UPDATE corpus_control SET publish_frozen = TRUE WHERE singleton_id = 1")
        )
        await session.commit()

    response = await upload(
        client, seeded["admin_headers"], [("资料.txt", txt_bytes("冻结期间的资料。"))]
    )
    assert response.status_code == 202
    batch_id = response.json()["data"]["batch_id"]

    await worker_drain(rounds=3)

    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        document = (
            await session.execute(
                select(Document).where(Document.batch_id == batch_id)
            )
        ).scalar_one()
        version = (
            await session.execute(
                select(DocumentVersion).where(DocumentVersion.document_id == document.id)
            )
        ).scalar_one()
        publish_task_state = (
            await session.execute(
                text(
                    "SELECT state FROM background_tasks WHERE kind='batch_publish' "
                    "AND object_id=:bid"
                ),
                {"bid": batch_id},
            )
        ).scalar_one()
    assert batch.state == "processing"
    assert document.visibility == "unpublished"
    assert version.state == "ready"
    assert publish_task_state == "retry_wait"

    await worker_drain(rounds=3)
    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        document = await session.get(Document, document.id)
    assert batch.state == "processing"  # 仍冻结，不失败也不半发布
    assert document.visibility == "unpublished"

    async with db() as session:
        await session.execute(
            text("UPDATE corpus_control SET publish_frozen = FALSE WHERE singleton_id = 1")
        )
        # 冻结期间发布任务被排到 10s 后；测试推进到期时间，避免真实 sleep。
        await session.execute(
            text(
                "UPDATE background_tasks SET next_run_at = UTC_TIMESTAMP(6) "
                "WHERE kind='batch_publish' AND object_id=:bid"
            ),
            {"bid": batch_id},
        )
        await session.commit()
    await worker_drain(rounds=4)
    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        document = await session.get(Document, document.id)
    assert batch.state == "published"
    assert document.visibility == "shared"


async def test_publish_terminal_failure_compensates_batch(client, seeded, db):
    """发布任务终态失败（不可重试）必须让批次进入补偿，不能永久停在 processing。"""
    from app.adapters.db.models import (
        Chunk,
        Document,
        DocumentBatch,
        DocumentVersion,
    )

    async with db() as session:
        await session.execute(
            text("UPDATE corpus_control SET publish_frozen = TRUE WHERE singleton_id = 1")
        )
        await session.commit()

    response = await upload(
        client, seeded["admin_headers"], [("终态失败.txt", txt_bytes("终态失败补偿内容。"))]
    )
    assert response.status_code == 202, response.text
    batch_id = response.json()["data"]["batch_id"]
    document_id = response.json()["data"]["documents"][0]["id"]

    # 冻结期间：持久完成、发布停在 retry_wait
    await worker_drain(rounds=3)
    async with db() as session:
        version_space = (
            await session.execute(
                text(
                    "SELECT vector_space FROM document_versions WHERE document_id=:did"
                ),
                {"did": document_id},
            )
        ).scalar_one()

    # 解开冻结，同时制造向量空间冲突 → 发布不可重试失败（VECTOR_SPACE_MISMATCH）
    async with db() as session:
        await session.execute(
            text(
                "UPDATE corpus_control SET publish_frozen = FALSE, "
                "active_vector_space = :space WHERE singleton_id = 1"
            ),
            {"space": f"{version_space}_conflict"},
        )
        await session.execute(
            text(
                "UPDATE background_tasks SET next_run_at = UTC_TIMESTAMP(6) "
                "WHERE kind='batch_publish' AND object_id=:bid"
            ),
            {"bid": batch_id},
        )
        await session.commit()

    await worker_drain(rounds=8)

    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        document = await session.get(Document, document_id)
        version = (
            await session.execute(
                select(DocumentVersion).where(DocumentVersion.document_id == document_id)
            )
        ).scalar_one()
        publish_state = (
            await session.execute(
                text(
                    "SELECT state, error_code FROM background_tasks "
                    "WHERE kind='batch_publish' AND object_id=:bid"
                ),
                {"bid": batch_id},
            )
        ).one()
        revision = (
            await session.execute(
                text("SELECT revision FROM corpus_control WHERE singleton_id = 1")
            )
        ).scalar_one()
        chunks = int(
            (await session.execute(select(func.count()).select_from(Chunk))).scalar_one()
        )

    # 批次进入终态，发布任务失败并留下错误码，绝不半发布
    assert batch.state == "failed"
    assert batch.error_code == "VECTOR_SPACE_MISMATCH"
    assert batch.published_at is None
    assert publish_state.state == "failed"
    assert publish_state.error_code == "VECTOR_SPACE_MISMATCH"
    assert int(revision) == 0
    assert document.visibility == "unpublished"
    assert document.processing_state == "failed"
    assert version.state == "failed"
    assert chunks == 0


async def test_delete_unpublished_document_compensates_batch(client, seeded, db):
    """未发布批次删掉其中一份文档 → 整批转补偿，已删文档走自己的清理终态。"""
    from app.adapters.db.models import Document, DocumentBatch
    from app.adapters.filestore.local import FileStore
    from app.modules.knowledge.adapters import document_key

    from _knowledge_helpers import get_document_row

    async with db() as session:
        await session.execute(
            text("UPDATE corpus_control SET publish_frozen = TRUE WHERE singleton_id = 1")
        )
        await session.commit()

    response = await upload(
        client,
        seeded["admin_headers"],
        [("先删的.txt", txt_bytes("这份会被删掉。")), ("留下的.txt", txt_bytes("这份随批次补偿。"))],
    )
    assert response.status_code == 202, response.text
    batch_id = response.json()["data"]["batch_id"]
    first_id = response.json()["data"]["documents"][0]["id"]
    second_id = response.json()["data"]["documents"][1]["id"]

    await worker_drain(rounds=3)
    first = await get_document_row(first_id)
    deleted = await client.delete(
        f"{API}/admin/documents/{first_id}?expected_version={int(first.version)}",
        headers=seeded["admin_headers"],
    )
    assert deleted.status_code == 202, deleted.text

    # 删除请求当场就把批次推进补偿（不留给发布事务）
    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
    assert batch.state == "compensating"
    assert batch.error_code == "BATCH_FAILED"

    async with db() as session:
        await session.execute(
            text("UPDATE corpus_control SET publish_frozen = FALSE WHERE singleton_id = 1")
        )
        await session.commit()
    await worker_drain(rounds=10)

    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        first_doc = await session.get(Document, first_id)
        second_doc = await session.get(Document, second_id)
        revision = (
            await session.execute(
                text("SELECT revision FROM corpus_control WHERE singleton_id = 1")
            )
        ).scalar_one()

    # 整批未发布：revision 只因删除而 +1（发布不递增）
    assert batch.state == "failed"
    assert int(revision) == 1
    # 被删文档：自己的清理任务赢下终态，批次补偿不得覆盖
    assert first_doc.visibility == "removed"
    assert first_doc.deleted_at is not None
    assert first_doc.processing_state == "deleted"
    assert first_doc.cleanup_state == "succeeded"
    # 同批其他文档：整批补偿为失败、不可见
    assert second_doc.visibility == "unpublished"
    assert second_doc.processing_state == "failed"
    assert second_doc.active_version_id is None

    store = FileStore()
    for document_id in (first_id, second_id):
        assert not store.exists(document_key(document_id))


async def test_publish_refuses_document_removed_concurrently(client, seeded, db, monkeypatch):
    """发布事务内发现 removed 文档：不复活、不撞 ck_document_removed，整批转补偿。

    预检与发布事务之间管理员删除了批次内文档的情况无法用 HTTP 请求直接构造，
    这里直接改行模拟并发提交，并把预检短路为"全部就绪"以进入发布事务。
    """
    from app.modules.knowledge import tasks as tasks_mod

    response = await upload(
        client, seeded["admin_headers"], [("并发移除.txt", txt_bytes("并发移除内容。"))]
    )
    assert response.status_code == 202, response.text
    batch_id = response.json()["data"]["batch_id"]
    document_id = response.json()["data"]["documents"][0]["id"]

    async with db() as session:
        await session.execute(
            text("UPDATE corpus_control SET publish_frozen = TRUE WHERE singleton_id = 1")
        )
        await session.commit()
    await worker_drain(rounds=3)

    # 模拟"预检通过之后、发布事务之前"管理员提交了删除
    async with db() as session:
        await session.execute(
            text(
                "UPDATE documents SET visibility='removed', deleted_at=UTC_TIMESTAMP(6), "
                "processing_state='deleting', cleanup_state='pending', version=version+1 "
                "WHERE id=:id"
            ),
            {"id": document_id},
        )
        await session.execute(
            text("UPDATE corpus_control SET publish_frozen = FALSE WHERE singleton_id = 1")
        )
        await session.execute(
            text(
                "UPDATE background_tasks SET next_run_at = UTC_TIMESTAMP(6) "
                "WHERE kind='batch_publish' AND object_id=:bid"
            ),
            {"bid": batch_id},
        )
        await session.commit()

    async def _always_ready(batch_id: str):
        return tasks_mod.Precheck(True, None, True)

    monkeypatch.setattr(tasks_mod, "batch_precheck", _always_ready)
    await worker_drain(rounds=6)

    from app.adapters.db.models import Document, DocumentBatch

    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        document = await session.get(Document, document_id)
        revision = (
            await session.execute(
                text("SELECT revision FROM corpus_control WHERE singleton_id = 1")
            )
        ).scalar_one()

    assert batch.state == "failed"
    assert batch.error_code == "BATCH_FAILED"
    assert int(revision) == 0
    # 已删文档保持 removed + deleted_at（未被改回 shared，也未触发 CHECK 违约）
    assert document.visibility == "removed"
    assert document.deleted_at is not None
    assert document.processing_state != "available"


async def test_publish_does_not_mix_partial_batches(client, seeded, db):
    from app.adapters.db.models import DocumentBatch

    # 先发布一个批次
    first = await publish_batch(
        client, seeded["admin_headers"], [("第一批.txt", txt_bytes("第一批的内容。"))]
    )
    # 第二批只上传不跑 worker：仍不可见，不影响第一批
    second_response = await upload(
        client, seeded["admin_headers"], [("第二批.txt", txt_bytes("第二批内容。"))]
    )
    assert second_response.status_code == 202
    second_id = second_response.json()["data"]["batch_id"]

    async with db() as session:
        first_batch = await session.get(DocumentBatch, first)
        second_batch = await session.get(DocumentBatch, second_id)
    assert first_batch.state == "published"
    assert second_batch.state == "accepted"

    from app.modules.knowledge import SearchQuery, knowledge
    from app.shared.context import ActorContext

    actor = ActorContext(
        user_id=seeded["student"]["id"],
        session_id="ses_search",
        auth_version=1,
        role="student",
        trace_request_id="req_search",
    )
    evidence = await knowledge.search(actor, SearchQuery(query="内容"))
    assert evidence.status == "ok"
    assert all("第二批" not in ref.file_name for ref in evidence.references)


async def test_publish_rejects_stale_parser_config_digest(client, seeded, db):
    """冻结参数变更后，旧参数构建的版本不得发布（设计 §10.5/§11.3）。"""
    from app.adapters.db.models import Document, DocumentBatch, DocumentVersion

    async with db() as session:
        await session.execute(
            text("UPDATE corpus_control SET publish_frozen = TRUE WHERE singleton_id = 1")
        )
        await session.commit()

    response = await upload(
        client, seeded["admin_headers"], [("参数变更.txt", txt_bytes("冻结参数内容。"))]
    )
    assert response.status_code == 202, response.text
    batch_id = response.json()["data"]["batch_id"]
    document_id = response.json()["data"]["documents"][0]["id"]

    # staging 完成（版本 ready、发布停在 retry_wait）
    await worker_drain(rounds=3)

    # 模拟"入库后解析/向量参数变更"：把版本行的摘要改成与当前配置不一致
    async with db() as session:
        await session.execute(
            text(
                "UPDATE document_versions SET parser_config_digest = UNHEX(SHA2('stale', 256)) "
                "WHERE document_id = :did"
            ),
            {"did": document_id},
        )
        await session.execute(
            text("UPDATE corpus_control SET publish_frozen = FALSE WHERE singleton_id = 1")
        )
        await session.execute(
            text(
                "UPDATE background_tasks SET next_run_at = UTC_TIMESTAMP(6) "
                "WHERE kind='batch_publish' AND object_id=:bid"
            ),
            {"bid": batch_id},
        )
        await session.commit()

    await worker_drain(rounds=8)

    async with db() as session:
        batch = await session.get(DocumentBatch, batch_id)
        document = await session.get(Document, document_id)
        version = (
            await session.execute(
                select(DocumentVersion).where(DocumentVersion.document_id == document_id)
            )
        ).scalar_one()
        revision = (
            await session.execute(
                text("SELECT revision FROM corpus_control WHERE singleton_id = 1")
            )
        ).scalar_one()

    assert batch.state == "failed"
    assert batch.error_code == "PROCESSING_FAILED"
    assert int(revision) == 0
    assert document.visibility == "unpublished"
    assert document.processing_state == "failed"
    assert version.state == "failed"


async def test_staging_namespace_uses_frozen_vector_space(client, seeded, db, monkeypatch):
    """CCA_VECTOR_SPACE 在"接受→staging"之间变化时，向量仍写进版本行冻结的空间。"""
    from app.adapters.db.models import DocumentVersion, StorageAttempt

    response = await upload(
        client, seeded["admin_headers"], [("空间冻结.txt", txt_bytes("空间冻结内容。"))]
    )
    assert response.status_code == 202, response.text
    document_id = response.json()["data"]["documents"][0]["id"]

    async with db() as session:
        frozen_space = (
            await session.execute(
                text(
                    "SELECT vector_space FROM document_versions WHERE document_id = :did"
                ),
                {"did": document_id},
            )
        ).scalar_one()

    # 在接受之后、worker 之前改环境变量（等价于运维中途切空间）
    monkeypatch.setenv("CCA_VECTOR_SPACE", "corpus_switched")

    await worker_drain(rounds=6)

    async with db() as session:
        attempt = (
            await session.execute(
                select(StorageAttempt)
                .join(DocumentVersion, DocumentVersion.id == StorageAttempt.version_id)
                .where(DocumentVersion.document_id == document_id)
            )
        ).scalars().first()
        revision = (
            await session.execute(
                text("SELECT revision FROM corpus_control WHERE singleton_id = 1")
            )
        ).scalar_one()
        active_space = (
            await session.execute(
                text("SELECT active_vector_space FROM corpus_control WHERE singleton_id = 1")
            )
        ).scalar_one()

    # 向量命名空间必须落在冻结空间下，不能跟着环境变量漂移
    assert attempt is not None
    assert attempt.vector_namespace.startswith(f"{frozen_space}/")
    assert not attempt.vector_namespace.startswith("corpus_switched/")
    # 发布成功且语料空间仍是冻结值（不是环境变量值）
    assert int(revision) == 1
    assert active_space == frozen_space

    # 检索可命中（不是"已发布但检索不到"）
    from app.modules.knowledge import SearchQuery, knowledge
    from app.shared.context import ActorContext

    actor = ActorContext(
        user_id=seeded["student"]["id"],
        session_id="ses_search",
        auth_version=1,
        role="student",
        trace_request_id="req_search",
    )
    evidence = await knowledge.search(actor, SearchQuery(query="空间冻结内容"))
    assert evidence.status == "ok"
    assert evidence.revision == 1


async def test_staging_rejects_digest_change_midflight(client, seeded, db, monkeypatch):
    """staging 与当前参数不同源时立即失败，不写入注定检索不到的向量。"""
    from app.modules.knowledge import tasks as tasks_mod

    response = await upload(
        client, seeded["admin_headers"], [("中途变更.txt", txt_bytes("中途变更内容。"))]
    )
    assert response.status_code == 202, response.text
    batch_id = response.json()["data"]["batch_id"]
    document_id = response.json()["data"]["documents"][0]["id"]

    monkeypatch.setattr(tasks_mod, "parser_config_digest", lambda: b"changed-midflight")

    await worker_drain(rounds=6)

    from app.adapters.db.models import Document, DocumentBatch, DocumentVersion

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

    assert batch.state == "failed"
    assert batch.error_code == "PROCESSING_FAILED"
    assert document.visibility == "unpublished"
    assert all(v.state == "failed" for v in versions)
    assert await count_rows(DocumentVersion) >= 1
