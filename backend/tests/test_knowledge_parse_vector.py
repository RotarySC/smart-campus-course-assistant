"""K4/K5：解析分块与确定性 Embedding/本地 VectorStore。"""

from __future__ import annotations

import io
import json

import numpy as np
import pytest

from _knowledge_helpers import (
    count_rows,
    docx_bytes,
    knowledge_storage,  # noqa: F401
    pdf_bytes,
    run_worker_once,
    txt_bytes,
    unfreeze_corpus,  # noqa: F401
    upload,
    worker_drain,
)


# --------------------------------------------------------------------------- #
# Parser Adapter
# --------------------------------------------------------------------------- #
def test_parse_txt_and_md_with_bom_and_newlines(monkeypatch):
    from app.adapters.parser.document_parser import parse_bytes

    monkeypatch.setenv("CCA_CHUNK_SIZE", "80")
    monkeypatch.setenv("CCA_CHUNK_OVERLAP", "10")
    parsed = parse_bytes("第一行\r\n第二行\r\n".encode("utf-8-sig"), "txt")
    assert parsed.text == "第一行\n第二行"
    assert parsed.file_type == "txt"

    parsed_md = parse_bytes("# 标题\n\n正文".encode("utf-8"), "md")
    assert parsed_md.text == "# 标题\n\n正文"


def test_parse_rejects_invalid_text_and_empty():
    from app.adapters.parser.document_parser import ParserError, parse_bytes

    with pytest.raises(ParserError) as invalid:
        parse_bytes(b"\xff\xfe\x00binary", "txt")
    assert invalid.value.code == "PARSE_FAILED"

    with pytest.raises(ParserError) as empty:
        parse_bytes(b"   \n\t ", "md")
    assert empty.value.code == "NO_TEXT_EXTRACTED"


def test_parse_pdf_page_mapping_and_no_text():
    from app.adapters.parser.document_parser import ParserError, parse_bytes

    data = pdf_bytes(["Page one: arrays.", "Page two: linked lists."])
    parsed = parse_bytes(data, "pdf")
    assert [segment.page_number for segment in parsed.segments] == [1, 2]
    assert "arrays" in parsed.segments[0].text
    assert "linked lists" in parsed.segments[1].text

    # 空白 PDF（无文本层）必须明确失败，而不是空片段成功入库
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(ParserError) as no_text:
        parse_bytes(buffer.getvalue(), "pdf")
    assert no_text.value.code == "NO_TEXT_EXTRACTED"

    with pytest.raises(ParserError) as corrupt:
        parse_bytes(b"%PDF-1.4\nthis is broken", "pdf")
    assert corrupt.value.code == "PARSE_FAILED"


def test_parse_encrypted_pdf_rejected():
    from pypdf import PdfWriter

    from app.adapters.parser.document_parser import ParserError, parse_bytes

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret-pass")
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(ParserError) as encrypted:
        parse_bytes(buffer.getvalue(), "pdf")
    assert encrypted.value.code == "DOCUMENT_ENCRYPTED"


def test_parse_docx_paragraphs_and_empty():
    from app.adapters.parser.document_parser import ParserError, parse_bytes

    parsed = parse_bytes(docx_bytes(["第一段：课程简介", "第二段：考核方式"]), "docx")
    assert [segment.paragraph_index for segment in parsed.segments] == [1, 2]
    assert "考核方式" in parsed.text

    with pytest.raises(ParserError) as empty:
        parse_bytes(docx_bytes([]), "docx")
    assert empty.value.code == "NO_TEXT_EXTRACTED"


def test_chunking_respects_window_overlap_and_codepoints(monkeypatch):
    from app.adapters.parser.document_parser import (
        build_chunks,
        parse_bytes,
    )

    monkeypatch.setenv("CCA_CHUNK_SIZE", "100")
    monkeypatch.setenv("CCA_CHUNK_OVERLAP", "20")
    text = "".join(chr(0x4E00 + (index % 200)) for index in range(320))
    parsed = parse_bytes(text.encode("utf-8"), "txt")
    chunks = build_chunks(parsed)
    assert len(chunks) > 1
    assert all(len(chunk.text) <= 100 for chunk in chunks)
    assert all(chunk.text.strip() for chunk in chunks)
    # 相邻块按固定窗口重叠，正文不丢码点
    assert chunks[1].text[:20] == chunks[0].text[-20:]
    assert "".join([chunks[0].text] + [chunk.text[20:] for chunk in chunks[1:]]) == text


async def test_four_formats_end_to_end_publish(client, seeded, db):
    from app.adapters.db.models import Chunk, Document

    files = [
        ("中文.txt", txt_bytes("中文文本样本：换行\n与码点边界。")),
        ("说明.md", txt_bytes("# Markdown\n\n- 列表项")),
        ("英文.pdf", pdf_bytes(["PDF page one content.", "PDF page two content."])),
        ("段落.docx", docx_bytes(["第一段内容", "第二段内容"])),
    ]
    response = await upload(client, seeded["admin_headers"], files)
    assert response.status_code == 202, response.text
    batch_id = response.json()["data"]["batch_id"]
    await worker_drain()

    async with db() as session:
        from sqlalchemy import select

        from app.adapters.db.models import DocumentBatch

        batch = await session.get(DocumentBatch, batch_id)
        documents = list(
            (await session.execute(select(Document).where(Document.batch_id == batch_id)))
            .scalars()
            .all()
        )
        chunks = list((await session.execute(select(Chunk))).scalars().all())
    assert batch.state == "published"
    assert {document.file_type for document in documents} == {"txt", "md", "pdf", "docx"}
    by_document = {document.id: document for document in documents}
    pdf_doc = next(document for document in documents if document.file_type == "pdf")
    pdf_chunks = [chunk for chunk in chunks if chunk.document_id == pdf_doc.id]
    assert {chunk.page_number for chunk in pdf_chunks} == {1, 2}
    assert all(chunk.page_number and chunk.location_label == f"第 {chunk.page_number} 页" for chunk in pdf_chunks)
    docx_doc = next(document for document in documents if document.file_type == "docx")
    docx_chunks = [chunk for chunk in chunks if chunk.document_id == docx_doc.id]
    assert all(chunk.page_number is None for chunk in docx_chunks)
    assert all(chunk.location_label.startswith("段落") for chunk in docx_chunks)

    # 抽取文本/manifest 真实落盘且与 DB 一致
    from app.adapters.filestore.local import FileStore
    from app.adapters.db.models import DocumentVersion

    store = FileStore()
    async with db() as session:
        versions = list(
            (
                await session.execute(
                    select(DocumentVersion).where(
                        DocumentVersion.document_id.in_(list(by_document))
                    )
                )
            )
            .scalars()
            .all()
        )
    for version in versions:
        assert version.extracted_text_key and store.exists(version.extracted_text_key)
        text = store.read_text(version.extracted_text_key)
        document_chunks = [chunk for chunk in chunks if chunk.version_id == version.id]
        assert document_chunks and text.strip()
        prefix = version.extracted_text_key.rsplit("/", 1)[0]
        manifest = json.loads(store.read_text(f"{prefix}/chunk-manifest"))
        assert manifest["chunk_count"] == len(document_chunks)
        assert {item["chunk_id"] for item in manifest["chunks"]} == {
            chunk.id for chunk in document_chunks
        }


# --------------------------------------------------------------------------- #
# Embedding / VectorStore
# --------------------------------------------------------------------------- #
async def test_deterministic_embedding_is_stable_and_normalized(monkeypatch):
    from app.adapters.embedding.deterministic import DeterministicEmbedding

    monkeypatch.setenv("CCA_EMBEDDING_DIM", "32")
    provider = DeterministicEmbedding(dim=32)
    first = await provider.embed("数据结构 与 算法")
    second = await provider.embed("数据结构 与 算法")
    other = await provider.embed("完全不同的一段英文")
    assert first.shape == (32,)
    assert np.allclose(first, second)
    assert float(np.linalg.norm(first)) == pytest.approx(1.0, abs=1e-5)
    assert not np.allclose(first, other)
    batch = await provider.embed_batch(["a", "b"])
    assert batch.shape == (2, 32)


async def test_vector_store_idempotent_upsert_namespace_and_barrier(tmp_path):
    from app.adapters.vector.local import LateWriteRejected, LocalVectorStore

    store = LocalVectorStore(tmp_path / "vector")
    vector_a = [1.0, 0.0, 0.0]
    vector_b = [0.0, 1.0, 0.0]
    namespace = "corpus_v1/doc_1/dvs_1/tsk_1/1"
    assert await store.upsert(namespace, [("chk_1", vector_a)], fence=1) == 1
    # 幂等：同 chunk 重复写不产生重复
    assert await store.upsert(namespace, [("chk_1", vector_a), ("chk_2", vector_b)], fence=1) == 2
    assert sorted(await store.list_chunk_ids("corpus_v1")) == ["chk_1", "chk_2"]

    hits = await store.search("corpus_v1", vector_a, limit=5)
    assert hits[0]["chunk_id"] == "chk_1"
    assert hits[0]["score"] == pytest.approx(1.0, abs=1e-5)

    # 收敛屏障：旧 fence 写入被拒绝，旧记录被清除
    assert await store.barrier("corpus_v1/doc_1/dvs_1/tsk_1", 1) == 2
    with pytest.raises(LateWriteRejected):
        await store.upsert(namespace, [("chk_3", vector_a)], fence=1)
    assert await store.list_chunk_ids("corpus_v1") == []
    # 新代次（fence 更大）允许写入
    new_namespace = "corpus_v1/doc_1/dvs_1/tsk_1/2"
    assert await store.upsert(new_namespace, [("chk_4", vector_a)], fence=2) == 1

    assert await store.delete_namespace(new_namespace) == 1
    assert await store.list_chunk_ids("corpus_v1") == []
    assert await store.delete_prefix("corpus_v1") == 0


async def test_vector_store_isolates_namespaces(tmp_path):
    from app.adapters.vector.local import LocalVectorStore

    store = LocalVectorStore(tmp_path / "vector")
    await store.upsert("corpus_v1/doc_a/v1/t1/1", [("chk_a", [1.0, 0.0])], fence=1)
    await store.upsert("corpus_v1/doc_b/v1/t1/1", [("chk_b", [0.0, 1.0])], fence=1)
    hits = await store.search("corpus_v1/doc_a", [1.0, 0.0], limit=10)
    assert [hit["chunk_id"] for hit in hits] == ["chk_a"]
    assert await store.delete_namespace("corpus_v1/doc_a/v1/t1/1") == 1
    assert await store.list_chunk_ids("corpus_v1/doc_a") == []
    assert await store.list_chunk_ids("corpus_v1/doc_b") == ["chk_b"]


async def test_embedding_failure_maps_to_embedding_failed(client, seeded, db, monkeypatch):
    """SRS FR-DOC-002：Embedding 故障必须与存储故障分开（EMBEDDING_FAILED，可有限重试）。"""
    from sqlalchemy import select

    from app.adapters.embedding.deterministic import EmbeddingError
    from app.modules.knowledge import tasks as tasks_mod

    response = await upload(
        client, seeded["admin_headers"], [("向量失败.txt", txt_bytes("向量失败内容。"))]
    )
    assert response.status_code == 202, response.text
    batch_id = response.json()["data"]["batch_id"]

    class _BrokenEmbedding:
        def embed_batch(self, texts):
            raise EmbeddingError("模拟向量化失败")

    monkeypatch.setattr(tasks_mod, "embedding", lambda: _BrokenEmbedding())

    await run_worker_once()

    from app.adapters.db.models import BackgroundTask, DocumentBatch

    async with db() as session:
        tasks = list(
            (
                await session.execute(
                    select(BackgroundTask).where(BackgroundTask.kind == "doc_persist")
                )
            )
            .scalars()
            .all()
        )
        batch = await session.get(DocumentBatch, batch_id)

    assert tasks and all(task.error_code == "EMBEDDING_FAILED" for task in tasks)
    # 可重试：停在 retry_wait，不直接判死
    assert all(task.state == "retry_wait" for task in tasks)
    assert batch.state in ("accepted", "processing")
