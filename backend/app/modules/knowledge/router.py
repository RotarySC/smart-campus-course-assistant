"""知识链路路由：8 个文档/引用端点（OpenAPI v0.1 契约）。

- 上传用 multipart；其余变更用 JSON（设计 §3.2）。
- 未声明查询/表单字段一律 422；错误统一信封由全局异常处理器渲染。
- 响应模型声明沿用 Phase 1 约定：返回 ``JSONResponse``（信封由 shared.http.envelope
  组装），``responses=ERROR_RESPONSES`` 供运行态 OpenAPI 与设计包对齐。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Path, Query, Request
from starlette.datastructures import UploadFile

from app.modules.identity.interface import get_actor, get_admin
from app.modules.knowledge.schemas import (
    BatchOptions,
    DocumentCommand,
    ListDocumentsQuery,
)
from app.modules.knowledge.service import knowledge
from app.modules.knowledge.api_models import (
    Batch,
    Citation,
    DocumentMutation,
    DocumentPage,
    DocumentText,
)
from app.shared.api_models import ERROR_RESPONSES, Envelope
from app.shared.context import ActorContext
from app.shared.errors import validation_error
from app.shared.http import envelope, page_query
from app.shared.validation import ExpectedVersion, RequestModel

router = APIRouter(tags=["knowledge"])

ID_PATH = Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
IDEMPOTENCY_KEY = Header(
    ...,
    alias="Idempotency-Key",
    min_length=1,
    max_length=96,
    pattern=r"^[A-Za-z0-9._:-]+$",
)
PREVIEW_LIMIT = Query(default=20000, ge=1, le=20000)
PREVIEW_OFFSET = Query(default=0, ge=0)

UPLOAD_OPENAPI_EXTRA = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 10,
                            "items": {"type": "string", "format": "binary"},
                        },
                        "allow_duplicate_names": {"type": "boolean"},
                    },
                    "required": ["files"],
                    "additionalProperties": False,
                }
            }
        },
    }
}


class Rebuild(RequestModel):
    expected_version: ExpectedVersion


@router.post(
    "/admin/document-batches",
    operation_id="uploadBatch",
    status_code=202,
    response_model=Envelope[Batch],
    responses=ERROR_RESPONSES,
    openapi_extra=UPLOAD_OPENAPI_EXTRA,
)
async def upload_batch(request: Request, actor: ActorContext = Depends(get_admin)):
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        raise validation_error(("files", "必须使用 multipart/form-data"))
    try:
        form = await request.form()
    except Exception as exc:  # noqa: BLE001 - multipart 解析失败统一 422
        raise validation_error(("files", "multipart 请求解析失败")) from exc
    unknown = sorted(set(form.keys()) - {"files", "allow_duplicate_names"})
    if unknown:
        raise validation_error(*[(name, "不允许的字段") for name in unknown])
    raw_files = form.getlist("files")
    uploads = [item for item in raw_files if isinstance(item, UploadFile)]
    if len(uploads) != len(raw_files):
        raise validation_error(("files", "文件字段格式不正确"))
    raw_allow = form.get("allow_duplicate_names")
    allow = False
    if raw_allow is not None:
        if not isinstance(raw_allow, str) or raw_allow not in ("true", "false"):
            raise validation_error(("allow_duplicate_names", "只接受 true/false"))
        allow = raw_allow == "true"
    data = await knowledge.accept_batch(
        actor, uploads, BatchOptions(allow_duplicate_names=allow)
    )
    return envelope(request, data, status_code=202)


@router.get(
    "/admin/document-batches/{id}",
    operation_id="getBatch",
    response_model=Envelope[Batch],
    responses=ERROR_RESPONSES,
)
async def get_batch(
    request: Request,
    id: str = ID_PATH,
    actor: ActorContext = Depends(get_admin),
):
    data = await knowledge.get_batch(actor, id)
    return envelope(request, data)


@router.get(
    "/admin/documents",
    operation_id="listDocuments",
    response_model=Envelope[DocumentPage],
    responses=ERROR_RESPONSES,
)
async def list_documents(
    request: Request,
    pagination: tuple[int, int] = Depends(page_query),
    name: str | None = Query(default=None, min_length=0, max_length=255),
    state: str | None = Query(default=None, min_length=1, max_length=32),
    actor: ActorContext = Depends(get_admin),
):
    page, page_size = pagination
    data = await knowledge.list_documents(
        actor,
        ListDocumentsQuery(page=page, page_size=page_size, name=name, state=state),
    )
    return envelope(request, data)


@router.get(
    "/admin/documents/{id}/text",
    operation_id="previewDocument",
    response_model=Envelope[DocumentText],
    responses=ERROR_RESPONSES,
)
async def preview_document(
    request: Request,
    id: str = ID_PATH,
    offset: int = PREVIEW_OFFSET,
    limit: int = PREVIEW_LIMIT,
    actor: ActorContext = Depends(get_admin),
):
    data = await knowledge.preview_document(actor, id, offset, limit)
    return envelope(request, data)


@router.post(
    "/admin/documents/{id}/rebuild",
    operation_id="rebuildDocument",
    status_code=202,
    response_model=Envelope[DocumentMutation],
    responses=ERROR_RESPONSES,
)
async def rebuild_document(
    request: Request,
    body: Rebuild,
    id: str = ID_PATH,
    idempotency_key: str = IDEMPOTENCY_KEY,
    actor: ActorContext = Depends(get_admin),
):
    data = await knowledge.mutate_document(
        actor,
        DocumentCommand(
            action="rebuild",
            document_id=id,
            expected_version=body.expected_version,
            idempotency_key=idempotency_key,
        ),
    )
    return envelope(request, data, status_code=202)


@router.delete(
    "/admin/documents/{id}",
    operation_id="deleteDocument",
    status_code=202,
    response_model=Envelope[DocumentMutation],
    responses=ERROR_RESPONSES,
)
async def delete_document(
    request: Request,
    id: str = ID_PATH,
    expected_version: ExpectedVersion = Query(...),
    actor: ActorContext = Depends(get_admin),
):
    data = await knowledge.mutate_document(
        actor,
        DocumentCommand(
            action="delete",
            document_id=id,
            expected_version=expected_version,
        ),
    )
    return envelope(request, data, status_code=202)


@router.post(
    "/admin/documents/{id}/cleanup-retry",
    operation_id="retryCleanup",
    status_code=202,
    response_model=Envelope[DocumentMutation],
    responses=ERROR_RESPONSES,
)
async def retry_cleanup(
    request: Request,
    id: str = ID_PATH,
    idempotency_key: str = IDEMPOTENCY_KEY,
    actor: ActorContext = Depends(get_admin),
):
    data = await knowledge.mutate_document(
        actor,
        DocumentCommand(
            action="cleanup_retry",
            document_id=id,
            idempotency_key=idempotency_key,
        ),
    )
    return envelope(request, data, status_code=202)


@router.get(
    "/citations/{reference_id}",
    operation_id="getCitation",
    response_model=Envelope[Citation],
    responses=ERROR_RESPONSES,
)
async def get_citation(
    request: Request,
    reference_id: str = Path(
        ..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"
    ),
    actor: ActorContext = Depends(get_actor),
):
    data = await knowledge.get_citation(actor, reference_id)
    return envelope(request, data)


