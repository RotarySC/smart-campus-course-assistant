"""计划 / 草稿 / 保存 / 写入状态路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Path, Query, Request

from app.modules.identity.interface import get_actor
from app.modules.planning import service
from app.modules.planning.schemas import DraftPatch, DraftSave, PlanCreate, PlanPatch
from app.shared.context import ActorContext
from app.shared.http import envelope, page_query, request_id_of
from app.shared.validation import ExpectedVersion

router = APIRouter(tags=["planning"])

ID_PATH = Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
OPERATION_PATH = Path(..., min_length=1, max_length=96, pattern=r"^[A-Za-z0-9._:-]+$")
IDEMPOTENCY_KEY = Header(
    ...,
    alias="Idempotency-Key",
    min_length=1,
    max_length=96,
    pattern=r"^[A-Za-z0-9._:-]+$",
    description="同一逻辑写入必须复用；草稿保存必须匹配服务端版本绑定。",
)


@router.get("/me/plans", operation_id="listPlans")
async def list_plans(
    request: Request,
    pagination: tuple[int, int] = Depends(page_query),
    title: str | None = Query(default=None, min_length=0, max_length=100),
    actor: ActorContext = Depends(get_actor),
):
    page, page_size = pagination
    data = await service.list_plans(
        actor, page=page, page_size=page_size, title=title
    )
    return envelope(request, data)


@router.post("/me/plans", operation_id="createPlan")
async def create_plan(
    request: Request,
    body: PlanCreate,
    idempotency_key: str = IDEMPOTENCY_KEY,
    actor: ActorContext = Depends(get_actor),
):
    status_code, data = await service.create_plan_manual(
        actor, body, idempotency_key, request_id_of(request)
    )
    return envelope(request, data, status_code=status_code)


@router.get("/me/plans/{id}", operation_id="getPlan")
async def get_plan(
    request: Request,
    id: str = ID_PATH,
    actor: ActorContext = Depends(get_actor),
):
    data = await service.get_plan(actor, id)
    return envelope(request, data)


@router.patch("/me/plans/{id}", operation_id="patchPlan")
async def patch_plan(
    request: Request,
    body: PlanPatch,
    id: str = ID_PATH,
    actor: ActorContext = Depends(get_actor),
):
    data = await service.patch_plan(actor, id, body, request_id_of(request))
    return envelope(request, data)


@router.delete("/me/plans/{id}", operation_id="deletePlan")
async def delete_plan(
    request: Request,
    expected_version: ExpectedVersion = Query(...),
    id: str = ID_PATH,
    actor: ActorContext = Depends(get_actor),
):
    data = await service.delete_plan(
        actor, id, expected_version, request_id_of(request)
    )
    return envelope(request, data)


@router.get("/me/drafts/{draft_id}", operation_id="getDraft")
async def get_draft(
    request: Request,
    draft_id: str = ID_PATH,
    actor: ActorContext = Depends(get_actor),
):
    data = await service.get_draft(actor, draft_id)
    return envelope(request, data)


@router.patch("/me/drafts/{draft_id}", operation_id="reviseDraft")
async def revise_draft(
    request: Request,
    body: DraftPatch,
    draft_id: str = ID_PATH,
    actor: ActorContext = Depends(get_actor),
):
    data = await service.revise_draft(actor, draft_id, body, request_id_of(request))
    return envelope(request, data)


@router.post("/me/drafts/{draft_id}/save", operation_id="saveDraft")
async def save_draft(
    request: Request,
    body: DraftSave,
    idempotency_key: str = IDEMPOTENCY_KEY,
    draft_id: str = ID_PATH,
    actor: ActorContext = Depends(get_actor),
):
    status_code, data = await service.save_draft(
        actor,
        draft_id,
        body.draft_version,
        idempotency_key,
        request_id_of(request),
    )
    return envelope(request, data, status_code=status_code)


@router.get("/me/write-operations/{operation_id}", operation_id="getWriteOperation")
async def get_write_operation(
    request: Request,
    operation_id: str = OPERATION_PATH,
    actor: ActorContext = Depends(get_actor),
):
    data = await service.get_write_operation(actor, operation_id)
    return envelope(request, data)
