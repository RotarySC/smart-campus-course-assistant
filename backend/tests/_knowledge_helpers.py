"""知识车道测试共享夹具与样本构造（由各 test_knowledge*.py 显式导入）。

不改 ``conftest.py``（Phase 1 单写者文件）：本模块只定义可被 import 的 fixture
与工具函数；导入到测试模块后 pytest 可正常发现。

隔离约定：
- FileStore / VectorStore 根目录每个用例切到 ``tmp_path``（真实落盘，非内存）。
- 每个用例把 ``corpus_control.publish_frozen`` 置 FALSE（迁移默认 TRUE，理由见报告）。
"""

from __future__ import annotations

import io
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text

MIME = {
    "txt": "text/plain",
    "md": "text/markdown",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

API = "/api/v1"


@pytest.fixture(autouse=True)
def knowledge_storage(tmp_path, monkeypatch):
    """每个用例独立的文件/向量存储根目录 + 较小分块便于覆盖多片段。"""
    monkeypatch.setenv("CCA_FILESTORE_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("CCA_VECTOR_ROOT", str(tmp_path / "vector"))
    monkeypatch.setenv("CCA_CHUNK_SIZE", "120")
    monkeypatch.setenv("CCA_CHUNK_OVERLAP", "20")
    return tmp_path


@pytest_asyncio.fixture(autouse=True)
async def unfreeze_corpus(db: Any, clean_database: Any):
    """conftest 每个用例把 publish_frozen 复位为 TRUE；知识车道用例显式解冻。"""
    async with db() as session:
        await session.execute(text("UPDATE corpus_control SET publish_frozen = FALSE"))
        await session.commit()
    yield


# --------------------------------------------------------------------------- #
# 样本文件
# --------------------------------------------------------------------------- #
def txt_bytes(text_: str) -> bytes:
    return text_.encode("utf-8")


def md_bytes(text_: str) -> bytes:
    return text_.encode("utf-8")


def docx_bytes(paragraphs: list[str]) -> bytes:
    from docx import Document

    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_bytes(pages: list[str]) -> bytes:
    """构造带文本层的多页 PDF（Helvetica ASCII），供 pypdf 抽取交叉验证。"""
    count = len(pages)
    font_id = 3 + 2 * count
    kids = " ".join(f"{3 + 2 * index} 0 R" for index in range(count))
    objects: list[str] = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>",
    ]
    for index, text_ in enumerate(pages):
        page_id = 3 + 2 * index
        content_id = page_id + 1
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({_pdf_escape(text_)}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    header = b"%PDF-1.4\n"
    body = b""
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(header) + len(body))
        body += f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref_offset = len(header) + len(body)
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n" + "".join(
        f"{offset:010d} 00000 n \n" for offset in offsets
    )
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    return header + body + xref.encode("ascii") + trailer.encode("ascii")


# --------------------------------------------------------------------------- #
# HTTP / Worker 工具
# --------------------------------------------------------------------------- #
def sample(name: str, content: bytes) -> tuple[str, tuple[str, bytes, str]]:
    ext = name.rsplit(".", 1)[-1].lower()
    return ("files", (name, content, MIME.get(ext, "application/octet-stream")))


async def upload(
    client: AsyncClient,
    headers: dict[str, str],
    files: list[tuple[str, bytes]],
    *,
    allow_duplicate: bool | None = None,
    form_extra: dict[str, str] | None = None,
):
    multipart = [sample(name, content) for name, content in files]
    data = {}
    if allow_duplicate is not None:
        data["allow_duplicate_names"] = "true" if allow_duplicate else "false"
    if form_extra:
        data.update(form_extra)
    return await client.post(
        f"{API}/admin/document-batches",
        files=multipart,
        data=data,
        headers=headers,
    )


async def run_worker_once(*, max_tasks: int = 100) -> dict[str, Any]:
    from app.modules.knowledge.tasks import run_once

    return await run_once("test-worker", max_tasks=max_tasks)


async def worker_drain(rounds: int = 5) -> dict[str, Any]:
    """多次 ``--once``（用于发布任务重排等场景），返回累计处理结果。"""
    total: dict[str, Any] = {"processed": 0, "rounds": 0, "counters": {}}
    for _ in range(rounds):
        result = await run_worker_once()
        total["rounds"] += 1
        total["processed"] += result.get("processed", 0)
        for key, value in (result.get("counters") or {}).items():
            total["counters"][key] = total["counters"].get(key, 0) + value
        if result.get("processed", 0) == 0:
            break
    return total


async def publish_batch(client: AsyncClient, headers: dict[str, str], files, **kwargs):
    response = await upload(client, headers, files, **kwargs)
    assert response.status_code == 202, response.text
    await worker_drain()
    return response.json()["data"]["batch_id"]


def batch_id_of(response) -> str:
    return response.json()["data"]["batch_id"]


async def get_document_row(document_id: str):
    from app.adapters.db.engine import session_scope
    from app.adapters.db.models import Document

    async with session_scope() as session:
        return await session.get(Document, document_id)


async def count_rows(model) -> int:
    from sqlalchemy import func, select

    from app.adapters.db.engine import session_scope

    async with session_scope() as session:
        return int(
            (
                await session.execute(select(func.count()).select_from(model))
            ).scalar_one()
            or 0
        )


__all__ = [
    "API",
    "MIME",
    "batch_id_of",
    "count_rows",
    "docx_bytes",
    "get_document_row",
    "knowledge_storage",
    "md_bytes",
    "pdf_bytes",
    "publish_batch",
    "run_worker_once",
    "sample",
    "txt_bytes",
    "unfreeze_corpus",
    "upload",
    "worker_drain",
]
