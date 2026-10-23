"""知识链路路由桩：路由已挂载，未实现端点返回 501 统一错误信封。

Phase 2 只需实现本模块的 service 并替换 501 返回；**不要改** public_api.py。
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.shared.api_models import ERROR_RESPONSES
from app.shared.http import not_implemented

router = APIRouter(tags=["knowledge"])

PHASE = "Phase 2（资料与知识链路）"


@router.post("/admin/document-batches", operation_id="uploadBatch", responses=ERROR_RESPONSES)
async def upload_batch(request: Request):
    return not_implemented(request, f"批量上传（{PHASE}）")


@router.get("/admin/document-batches/{id}", operation_id="getBatch", responses=ERROR_RESPONSES)
async def get_batch(request: Request, id: str):
    return not_implemented(request, f"批次详情（{PHASE}）")


@router.get("/admin/documents", operation_id="listDocuments", responses=ERROR_RESPONSES)
async def list_documents(request: Request):
    return not_implemented(request, f"文档列表（{PHASE}）")


@router.get("/admin/documents/{id}/text", operation_id="previewDocument", responses=ERROR_RESPONSES)
async def preview_document(request: Request, id: str):
    return not_implemented(request, f"文本预览（{PHASE}）")


@router.post("/admin/documents/{id}/rebuild", operation_id="rebuildDocument", responses=ERROR_RESPONSES)
async def rebuild_document(request: Request, id: str):
    return not_implemented(request, f"文档重建（{PHASE}）")


@router.delete("/admin/documents/{id}", operation_id="deleteDocument", responses=ERROR_RESPONSES)
async def delete_document(request: Request, id: str):
    return not_implemented(request, f"文档删除（{PHASE}）")


@router.post("/admin/documents/{id}/cleanup-retry", operation_id="retryCleanup", responses=ERROR_RESPONSES)
async def retry_cleanup(request: Request, id: str):
    return not_implemented(request, f"清理重试（{PHASE}）")


@router.get("/citations/{reference_id}", operation_id="getCitation", responses=ERROR_RESPONSES)
async def get_citation(request: Request, reference_id: str):
    return not_implemented(request, f"引用展开（{PHASE}）")
