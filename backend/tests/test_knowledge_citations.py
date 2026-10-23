"""K9：引用端点（有效可展开、失效 410、不泄漏内部键）。"""

from __future__ import annotations

from _knowledge_helpers import (
    API,
    knowledge_storage,  # noqa: F401
    publish_batch,
    search_evidence,
    txt_bytes,
    unfreeze_corpus,  # noqa: F401
    upload,
    worker_drain,
)


async def test_citation_expand_contract(client, seeded):
    await publish_batch(
        client,
        seeded["admin_headers"],
        [
            ("引用资料.txt", txt_bytes("引用端点验证：课程评分规则与考核方式。")),
            ("另一份.md", txt_bytes("另一份资料的内容。")),
        ],
    )
    evidence = await search_evidence(seeded, "评分规则")
    reference = evidence.references[0]

    response = await client.get(
        f"{API}/citations/{reference.reference_id}", headers=seeded["student_headers"]
    )
    assert response.status_code == 200, response.text
    payload = response.json()["data"]
    assert set(payload) == {"reference", "text"}
    assert set(payload["reference"]) <= {
        "reference_id",
        "document_id",
        "version_id",
        "file_name",
        "location_label",
        "page_number",
    }
    assert payload["reference"]["reference_id"] == reference.reference_id
    assert payload["reference"]["file_name"] == reference.file_name
    assert payload["text"].strip()
    assert "documents/" not in response.text
    assert "attempts/" not in response.text
    assert "original_storage_key" not in response.text

    # 学生与管理员都可以展开（当前模型资料全共享）
    admin_response = await client.get(
        f"{API}/citations/{reference.reference_id}", headers=seeded["admin_headers"]
    )
    assert admin_response.status_code == 200


async def test_citation_requires_auth_and_handles_unknown(client, seeded):
    unauthenticated = await client.get(f"{API}/citations/cit_unknown")
    assert unauthenticated.status_code == 401

    unknown = await client.get(
        f"{API}/citations/cit_unknown", headers=seeded["student_headers"]
    )
    assert unknown.status_code == 410
    assert unknown.json()["error"]["code"] == "CITATION_UNAVAILABLE"

    # 格式不合法的路径参数 → 422
    malformed = await client.get(
        f"{API}/citations/bad id!", headers=seeded["student_headers"]
    )
    assert malformed.status_code == 422


async def test_citation_invalid_after_delete(client, seeded, db):
    from app.adapters.db.models import Document

    await publish_batch(
        client, seeded["admin_headers"], [("删除引用.txt", txt_bytes("删除后引用应失效。"))]
    )
    evidence = await search_evidence(seeded, "引用")
    reference = evidence.references[0]
    async with db() as session:
        document = await session.get(Document, reference.document_id)
        version = int(document.version)

    deleted = await client.delete(
        f"{API}/admin/documents/{reference.document_id}?expected_version={version}",
        headers=seeded["admin_headers"],
    )
    assert deleted.status_code == 202

    response = await client.get(
        f"{API}/citations/{reference.reference_id}", headers=seeded["student_headers"]
    )
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "CITATION_UNAVAILABLE"
