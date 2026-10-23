"""K1/K2：上传校验 + 批次/文档/版本/任务建立（真实 MySQL + 真实文件）。"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from _knowledge_helpers import (
    API,
    count_rows,
    docx_bytes,
    knowledge_storage,  # noqa: F401 - pytest fixture
    pdf_bytes,
    txt_bytes,
    unfreeze_corpus,  # noqa: F401 - pytest fixture
    upload,
)


async def test_upload_accepts_batch_and_persists_files(client, seeded, db):
    from app.adapters.db.models import BackgroundTask, Document, DocumentVersion
    from app.adapters.filestore.local import FileStore
    from app.modules.knowledge.adapters import document_key
    from app.shared.ids import PREFIX_BATCH

    response = await upload(
        client,
        seeded["admin_headers"],
        [
            ("课程大纲.txt", txt_bytes("第一周：绪论。\n第二周：数组。")),
            ("说明.md", txt_bytes("# 课程资料\n\n评分规则见附录。")),
        ],
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert set(data) == {"batch_id", "state", "published", "documents", "tasks"}
    assert data["batch_id"].startswith(PREFIX_BATCH)
    assert data["state"] == "accepted"
    assert data["published"] is False
    assert len(data["documents"]) == 2
    assert {document["original_name"] for document in data["documents"]} == {
        "课程大纲.txt",
        "说明.md",
    }
    for document in data["documents"]:
        assert set(document) == {
            "id",
            "batch_id",
            "original_name",
            "file_type",
            "byte_size",
            "visibility",
            "processing_state",
            "version",
            "uploaded_at",
            "cleanup_state",
        }
        assert document["visibility"] == "unpublished"
        assert document["processing_state"] == "processing"
        assert document["version"] == 1
        assert document["cleanup_state"] == "not_required"
    assert len(data["tasks"]) == 3  # 2 persist + 1 publish
    assert {task["state"] for task in data["tasks"]} == {"pending"}
    assert {task["retryable"] for task in data["tasks"]} == {False}

    # 数据库行数与文件数一致
    assert await count_rows(Document) == 2
    assert await count_rows(DocumentVersion) == 2
    assert await count_rows(BackgroundTask) == 3
    from app.adapters.db.models import AuditEvent
    from sqlalchemy import func, select

    async with db() as session:
        accepted_audits = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(AuditEvent.action == "document.batch.accept")
                )
            ).scalar_one()
        )
    assert accepted_audits == 1

    # 文件真实落盘：原件存在、隔离区已清理
    store = FileStore()
    for document in data["documents"]:
        key = document_key(document["id"])
        assert store.exists(key)
        assert store.size_of(key) == document["byte_size"]
    sealed = store.list_keys("uploads")
    assert sealed == []


async def test_upload_requires_admin(client, seeded):
    response = await upload(
        client, seeded["student_headers"], [("a.txt", txt_bytes("hi"))]
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_upload_requires_auth(client, seeded):
    response = await client.post(
        f"{API}/admin/document-batches",
        files=[("files", ("a.txt", b"hello", "text/plain"))],
    )
    assert response.status_code == 401


async def test_upload_file_count_limits(client, seeded):
    too_many = [(f"f{index}.txt", txt_bytes("x")) for index in range(11)]
    response = await upload(client, seeded["admin_headers"], too_many)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"

    empty = await client.post(
        f"{API}/admin/document-batches", files=[], headers=seeded["admin_headers"]
    )
    assert empty.status_code == 422


async def test_upload_rejects_unsupported_and_fake_signature(client, seeded):
    bad_ext = await upload(client, seeded["admin_headers"], [("notes.exe", b"MZ")])
    assert bad_ext.status_code == 415
    assert bad_ext.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    fake_pdf = await upload(
        client, seeded["admin_headers"], [("fake.pdf", b"not a pdf at all")]
    )
    assert fake_pdf.status_code == 415

    fake_docx = await upload(
        client, seeded["admin_headers"], [("fake.docx", b"plain text")]
    )
    assert fake_docx.status_code == 415

    fake_txt = await upload(
        client, seeded["admin_headers"], [("fake.txt", b"abc\x00def")]
    )
    assert fake_txt.status_code == 415


async def test_upload_rejects_empty_and_oversize(client, seeded, db, monkeypatch):
    empty = await upload(client, seeded["admin_headers"], [("empty.txt", b"")])
    assert empty.status_code == 422

    from app.config import reset_settings_cache

    monkeypatch.setenv("CCA_UPLOAD_MAX_FILE_BYTES", "1024")
    reset_settings_cache()
    try:
        oversized = await upload(
            client, seeded["admin_headers"], [("big.txt", b"a" * 2048)]
        )
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "UPLOAD_TOO_LARGE"

        monkeypatch.setenv("CCA_UPLOAD_MAX_TOTAL_BYTES", "1500")
        reset_settings_cache()
        too_total = await upload(
            client,
            seeded["admin_headers"],
            [("a.txt", b"a" * 900), ("b.txt", b"b" * 900)],
        )
        assert too_total.status_code == 413
    finally:
        monkeypatch.delenv("CCA_UPLOAD_MAX_FILE_BYTES", raising=False)
        monkeypatch.delenv("CCA_UPLOAD_MAX_TOTAL_BYTES", raising=False)
        reset_settings_cache()

    # 失败请求不留下数据库行 / 暂存文件
    assert await count_rows(__import__("app.adapters.db.models", fromlist=["Document"]).Document) == 0
    from app.adapters.filestore.local import FileStore

    assert FileStore().list_keys("uploads") == []


async def test_upload_rejects_path_injection_and_extra_form(client, seeded):
    from app.adapters.filestore.local import FileStore

    injection = await upload(
        client, seeded["admin_headers"], [("../../evil.txt", txt_bytes("x"))]
    )
    assert injection.status_code == 422
    windows = await upload(
        client, seeded["admin_headers"], [("..\\evil.txt", txt_bytes("x"))]
    )
    assert windows.status_code == 422
    assert FileStore().list_keys("uploads") == []

    extra = await upload(
        client,
        seeded["admin_headers"],
        [("ok.txt", txt_bytes("ok"))],
        form_extra={"role": "admin"},
    )
    assert extra.status_code == 422
    assert extra.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_upload_duplicate_names_policy(client, seeded):
    content = [("同名.txt", txt_bytes("one")), ("同名.txt", txt_bytes("two"))]
    duplicate = await upload(client, seeded["admin_headers"], content)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_FILENAME"

    allowed = await upload(
        client, seeded["admin_headers"], content, allow_duplicate=True
    )
    assert allowed.status_code == 202
    assert len(allowed.json()["data"]["documents"]) == 2

    # 已存在同名文档：未显式允许时拒绝，允许时作为独立文档继续
    existing = await upload(
        client, seeded["admin_headers"], [("同名.txt", txt_bytes("three"))]
    )
    assert existing.status_code == 409
    again = await upload(
        client,
        seeded["admin_headers"],
        [("同名.txt", txt_bytes("three"))],
        allow_duplicate=True,
    )
    assert again.status_code == 202


async def test_get_batch_contract_and_permissions(client, seeded):
    response = await upload(
        client, seeded["admin_headers"], [("a.txt", txt_bytes("hello"))]
    )
    batch_id = response.json()["data"]["batch_id"]

    detail = await client.get(
        f"{API}/admin/document-batches/{batch_id}", headers=seeded["admin_headers"]
    )
    assert detail.status_code == 200
    payload = detail.json()["data"]
    assert payload["batch_id"] == batch_id
    assert payload["state"] == "accepted"
    assert payload["published"] is False
    assert len(payload["tasks"]) == 2

    missing = await client.get(
        f"{API}/admin/document-batches/bat_missing", headers=seeded["admin_headers"]
    )
    assert missing.status_code == 404

    forbidden = await client.get(
        f"{API}/admin/document-batches/{batch_id}", headers=seeded["student_headers"]
    )
    assert forbidden.status_code == 403

    # 上传后批次不可见（未发布）
    from app.modules.knowledge import SearchQuery, knowledge
    from app.shared.context import ActorContext

    actor = ActorContext(
        user_id=seeded["student"]["id"],
        session_id="ses_test",
        auth_version=1,
        role="student",
        trace_request_id="req_test",
    )
    evidence = await knowledge.search(actor, SearchQuery(query="课程"))
    assert evidence.status == "empty"
    assert evidence.corpus_empty is True
    assert evidence.chunks == []


async def test_upload_docx_and_pdf_samples_stage_ok(client, seeded):
    response = await upload(
        client,
        seeded["admin_headers"],
        [
            ("资料.pdf", pdf_bytes(["Page one about arrays.", "Page two about lists."])),
            ("资料.docx", docx_bytes(["第一段：课程简介", "第二段：考核方式"])),
        ],
    )
    assert response.status_code == 202, response.text
    types = {document["file_type"] for document in response.json()["data"]["documents"]}
    assert types == {"pdf", "docx"}


async def test_upload_unknown_query_param_rejected(client, seeded):
    response = await client.post(
        f"{API}/admin/document-batches?foo=1",
        files=[("files", ("a.txt", b"hello", "text/plain"))],
        headers=seeded["admin_headers"],
    )
    assert response.status_code == 422
