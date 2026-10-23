"""身份路由：/auth/login、/auth/logout、/me、/admin/students。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Request

from app.modules.identity import service
from app.modules.identity.interface import get_actor, get_admin
from app.modules.identity.schemas import LoginInput, StudentCreate, StudentPatch
from app.shared.context import ActorContext
from app.shared.http import envelope, page_query, parse_optional_bool, request_id_of

router = APIRouter(tags=["identity"])

ID_PATH = Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


@router.post("/auth/login", operation_id="login")
async def login(request: Request, body: LoginInput):
    data = await service.login(body, request_id_of(request))
    return envelope(request, data, status_code=200)


@router.post("/auth/logout", operation_id="logout")
async def logout(
    request: Request, actor: ActorContext = Depends(get_actor)
):
    data = await service.logout(actor, request_id_of(request))
    return envelope(request, data, status_code=200)


@router.get("/me", operation_id="getMe")
async def get_me(request: Request, actor: ActorContext = Depends(get_actor)):
    data = await service.get_me(actor)
    return envelope(request, data, status_code=200)


@router.get("/admin/students", operation_id="listStudents")
async def list_students(
    request: Request,
    pagination: tuple[int, int] = Depends(page_query),
    query: str | None = Query(default=None, min_length=0, max_length=100),
    enabled: str | None = Query(default=None),
    actor: ActorContext = Depends(get_admin),
):
    page, page_size = pagination
    data = await service.list_students(
        actor,
        page=page,
        page_size=page_size,
        query=query,
        enabled=parse_optional_bool("enabled", enabled),
    )
    return envelope(request, data, status_code=200)


@router.post("/admin/students", operation_id="createStudent")
async def create_student(
    request: Request,
    body: StudentCreate,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.create_student(actor, body, request_id_of(request))
    return envelope(request, data, status_code=201)


@router.patch("/admin/students/{id}", operation_id="patchStudent")
async def patch_student(
    request: Request,
    body: StudentPatch,
    id: str = ID_PATH,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.patch_student(actor, id, body, request_id_of(request))
    return envelope(request, data, status_code=200)
