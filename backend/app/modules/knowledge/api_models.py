"""知识链路响应模型（仅用于运行态 OpenAPI 文档与契约比对）。

类名/字段与 ``docs/backend/openapi_v0.1.json`` 的 components.schemas 一致；
路由实际返回 ``JSONResponse``（信封由 ``shared.http.envelope`` 组装），因此这些
模型不会在运行时改写响应，只声明契约。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.shared.api_models import Reference


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Task(_Strict):
    task_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    state: Literal["pending", "running", "retry_wait", "succeeded", "failed"]
    error_code: str | None = Field(default=None, min_length=1, max_length=64)
    retryable: bool


class Document(_Strict):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    batch_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    original_name: str = Field(min_length=1, max_length=255)
    file_type: Literal["txt", "md", "pdf", "docx"]
    byte_size: int = Field(ge=0, le=20 * 1024 * 1024)
    visibility: Literal["unpublished", "shared", "removed"]
    processing_state: Literal[
        "processing",
        "available",
        "failed",
        "rebuilding",
        "deleting",
        "delete_failed",
        "deleted",
    ]
    version: int = Field(ge=1)
    uploaded_at: datetime
    error_code: str | None = Field(default=None, min_length=1, max_length=64)
    cleanup_state: Literal["not_required", "pending", "running", "succeeded", "failed"]


class Batch(_Strict):
    batch_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    state: Literal["accepted", "processing", "published", "compensating", "failed"]
    published: bool
    documents: list[Document] = Field(max_length=10)
    tasks: list[Task]
    error_code: str | None = Field(default=None, min_length=1, max_length=64)


class DocumentPage(_Strict):
    items: list[Document]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class DocumentText(_Strict):
    document_id: str
    version_id: str
    offset: int = Field(ge=0)
    next_offset: int | None = Field(ge=0)
    text: str = Field(max_length=20000)


class DocumentMutation(_Strict):
    document_id: str
    visibility: Literal["unpublished", "shared", "removed"]
    task: Task
    version: int = Field(ge=1)


class Citation(_Strict):
    reference: Reference
    text: str = Field(min_length=1, max_length=20000)


__all__ = [
    "Batch",
    "Citation",
    "Document",
    "DocumentMutation",
    "DocumentPage",
    "DocumentText",
    "Task",
]
