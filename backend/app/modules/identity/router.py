"""身份路由：/auth/login、/auth/logout、/me、/admin/students。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Request

from app.modules.identity import service
from app.modules.identity.interface import get_actor, get_admin
from app.modules.identity.schemas import LoginInput, StudentCreate, StudentPatch
from app.shared.context import ActorContext
from app.shared.api_models import ERROR_RESPONSES, Envelope, Login, Logout, Me, StudentPage, User
from app.shared.http import envelope, page_query, parse_optional_bool, request_id_of

router = APIRouter(tags=["identity"])

def id_path():
    """每次返回新的 Path 实例：FastAPI 会按参数名回填 alias，复用同一实例会串名。"""
    return Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


@router.post("/auth/login", operation_id="login", response_model=Envelope[Login], responses=ERROR_RESPONSES)
async def login(request: Request, body: LoginInput):
    data = await service.login(body, request_id_of(request))
    return envelope(request, data, status_code=200)


@router.post("/auth/logout", operation_id="logout", response_model=Envelope[Logout], responses=ERROR_RESPONSES)
async def logout(
    request: Request, actor: ActorContext = Depends(get_actor)
):
    data = await service.logout(actor, request_id_of(request))
    return envelope(request, data, status_code=200)


@router.get("/me", operation_id="getMe", response_model=Envelope[Me], responses=ERROR_RESPONSES)
async def get_me(request: Request, actor: ActorContext = Depends(get_actor)):
    data = await service.get_me(actor)
    return envelope(request, data, status_code=200)


@router.get("/admin/students", operation_id="listStudents", response_model=Envelope[StudentPage], responses=ERROR_RESPONSES)
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


@router.post("/admin/students", operation_id="createStudent", status_code=201, response_model=Envelope[User], responses=ERROR_RESPONSES)
async def create_student(
    request: Request,
    body: StudentCreate,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.create_student(actor, body, request_id_of(request))
    return envelope(request, data, status_code=201)


@router.patch("/admin/students/{id}", operation_id="patchStudent", response_model=Envelope[User], responses=ERROR_RESPONSES)
async def patch_student(
    request: Request,
    body: StudentPatch,
    id: str = id_path(),
    actor: ActorContext = Depends(get_admin),
):
    data = await service.patch_student(actor, id, body, request_id_of(request))
    return envelope(request, data, status_code=200)
