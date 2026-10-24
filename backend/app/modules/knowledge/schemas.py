"""知识链路视图与命令数据结构（返回形状以 OpenAPI v0.1 为准）。

Router 只做参数解析与信封包装；返回 dict 的字段集合由本文件集中构造，
避免把 ORM 行或内部存储键泄漏给客户端。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.adapters.db.models import (
    BackgroundTask,
    CitationReference,
    Chunk,
    Document,
    DocumentBatch,
    DocumentVersion,
)
from app.shared.clock import isoformat

MutationAction = Literal["rebuild", "delete", "cleanup_retry"]

RETRYABLE_ERROR_CODES = frozenset(
    {
        "EMBEDDING_FAILED",
        "STORAGE_UNAVAILABLE",
        "RETRIEVAL_UNAVAILABLE",
        "SERVICE_RESTARTED",
    }
)


# --------------------------------------------------------------------------- #
# 命令对象（Interface 入参）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BatchOptions:
    allow_duplicate_names: bool = False


@dataclass(frozen=True)
class DocumentCommand:
    action: MutationAction
    document_id: str = ""
    expected_version: int | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ListDocumentsQuery:
    page: int = 1
    page_size: int = 20
    name: str | None = None
    state: str | None = None


@dataclass(frozen=True)
class SearchQuery:
    query: str
    top_k: int = 5


@dataclass(frozen=True)
class UploadItem:
    """已通过接收层流式落盘的单份文件（service 只读取该临时对象）。"""

    original_name: str
    file_type: str
    byte_size: int
    sealed_key: str


# --------------------------------------------------------------------------- #
# 证据集（EvidenceSet；形状与 MCP search_course_docs 输出一致）
# --------------------------------------------------------------------------- #
@dataclass
class EvidenceChunk:
    chunk_id: str
    reference_id: str
    document_id: str
    version_id: str
    text: str
    location_label: str
    page_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "chunk_id": self.chunk_id,
            "reference_id": self.reference_id,
            "document_id": self.document_id,
            "version_id": self.version_id,
            "text": self.text,
            "location_label": self.location_label,
        }
        if self.page_number is not None:
            data["page_number"] = self.page_number
        return data


@dataclass
class EvidenceReference:
    reference_id: str
    document_id: str
    version_id: str
    file_name: str
    location_label: str
    page_number: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "reference_id": self.reference_id,
            "document_id": self.document_id,
            "version_id": self.version_id,
            "file_name": self.file_name,
            "location_label": self.location_label,
        }
        if self.page_number is not None:
            data["page_number"] = self.page_number
        return data


@dataclass
class EvidenceSet:
    status: str
    corpus_empty: bool
    revision: int
    chunks: list[EvidenceChunk] = field(default_factory=list)
    references: list[EvidenceReference] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "corpus_empty": self.corpus_empty,
            "revision": self.revision,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "references": [ref.to_dict() for ref in self.references],
        }

    @classmethod
    def empty(cls, *, corpus_empty: bool, revision: int) -> "EvidenceSet":
        return cls(
            status="empty",
            corpus_empty=corpus_empty,
            revision=revision,
            chunks=[],
            references=[],
        )


# --------------------------------------------------------------------------- #
# 视图
# --------------------------------------------------------------------------- #
def task_view(task: BackgroundTask) -> dict[str, Any]:
    data: dict[str, Any] = {
        "task_id": task.id,
        "state": task.state,
        "retryable": bool(
            task.state == "retry_wait"
            or (task.state == "failed" and (task.error_code or "") in RETRYABLE_ERROR_CODES)
        ),
    }
    if task.error_code:
        data["error_code"] = task.error_code
    return data


def document_view(document: Document) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": document.id,
        "batch_id": document.batch_id,
        "original_name": document.original_name,
        "file_type": document.file_type,
        "byte_size": int(document.byte_size),
        "visibility": document.visibility,
        "processing_state": document.processing_state,
        "version": int(document.version),
        "uploaded_at": isoformat(document.created_at),
        "cleanup_state": document.cleanup_state,
    }
    if document.error_code:
        data["error_code"] = document.error_code
    return data


def batch_view(
    batch: DocumentBatch,
    documents: list[Document],
    tasks: list[BackgroundTask],
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "batch_id": batch.id,
        "state": batch.state,
        "published": batch.state == "published",
        "documents": [document_view(document) for document in documents],
        "tasks": [task_view(task) for task in tasks],
    }
    if batch.error_code:
        data["error_code"] = batch.error_code
    return data


def document_mutation_view(
    document: Document,
    task: BackgroundTask,
) -> dict[str, Any]:
    return {
        "document_id": document.id,
        "visibility": document.visibility,
        "task": task_view(task),
        "version": int(document.version),
    }


def document_page_view(
    documents: list[Document], *, page: int, page_size: int, total: int
) -> dict[str, Any]:
    return {
        "items": [document_view(document) for document in documents],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def reference_view(
    reference: CitationReference,
    chunk: Chunk,
    document: Document,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "reference_id": reference.id,
        "document_id": reference.document_id,
        "version_id": reference.version_id,
        "file_name": document.original_name,
        "location_label": chunk.location_label,
    }
    if chunk.page_number is not None:
        data["page_number"] = int(chunk.page_number)
    return data


def citation_view(
    reference: CitationReference,
    chunk: Chunk,
    document: Document,
) -> dict[str, Any]:
    return {
        "reference": reference_view(reference, chunk, document),
        "text": chunk.text_content,
    }


__all__ = [
    "BatchOptions",
    "DocumentCommand",
    "EvidenceChunk",
    "EvidenceReference",
    "EvidenceSet",
    "ListDocumentsQuery",
    "MutationAction",
    "SearchQuery",
    "UploadItem",
    "batch_view",
    "citation_view",
    "document_mutation_view",
    "document_page_view",
    "document_view",
    "reference_view",
    "task_view",
]
