"""课程与课表路由：/admin/courses、/me/schedules、/admin/schedules。"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Request

from app.modules.academics import service
from app.modules.academics.schemas import (
    CourseCreate,
    CoursePatch,
    ScheduleCreate,
    SchedulePatch,
)
from app.modules.identity.interface import get_actor, get_admin
from app.shared.context import ActorContext
from app.shared.api_models import (
    ERROR_RESPONSES,
    Course,
    CoursePage,
    Envelope,
    Schedule,
    ScheduleDelete,
    SchedulePage,
)
from app.shared.http import envelope, page_query, parse_optional_bool, request_id_of
from app.shared.validation import ExpectedVersion

router = APIRouter(tags=["academics"])

def id_path():
    """每次返回新的 Path 实例：FastAPI 会按参数名回填 alias，复用同一实例会串名。"""
    return Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
def student_id_query():
    return Query(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


# ---- 课程 ----
@router.get("/admin/courses", operation_id="listCourses", response_model=Envelope[CoursePage], responses=ERROR_RESPONSES)
async def list_courses(
    request: Request,
    pagination: tuple[int, int] = Depends(page_query),
    query: str | None = Query(default=None, min_length=0, max_length=100),
    enabled: str | None = Query(default=None),
    actor: ActorContext = Depends(get_admin),
):
    page, page_size = pagination
    data = await service.list_courses(
        actor,
        page=page,
        page_size=page_size,
        query=query,
        enabled=parse_optional_bool("enabled", enabled),
    )
    return envelope(request, data)


@router.post("/admin/courses", operation_id="createCourse", status_code=201, response_model=Envelope[Course], responses=ERROR_RESPONSES)
async def create_course(
    request: Request,
    body: CourseCreate,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.create_course(actor, body, request_id_of(request))
    return envelope(request, data, status_code=201)


@router.patch("/admin/courses/{id}", operation_id="patchCourse", response_model=Envelope[Course], responses=ERROR_RESPONSES)
async def patch_course(
    request: Request,
    body: CoursePatch,
    id: str = id_path(),
    actor: ActorContext = Depends(get_admin),
):
    data = await service.patch_course(actor, id, body, request_id_of(request))
    return envelope(request, data)


# ---- 课表 ----
@router.get("/me/schedules", operation_id="mySchedules", response_model=Envelope[SchedulePage], responses=ERROR_RESPONSES)
async def my_schedules(
    request: Request,
    pagination: tuple[int, int] = Depends(page_query),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    actor: ActorContext = Depends(get_actor),
):
    page, page_size = pagination
    data = await service.list_my_schedules(
        actor,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
    )
    return envelope(request, data)


@router.get("/admin/schedules", operation_id="adminSchedules", response_model=Envelope[SchedulePage], responses=ERROR_RESPONSES)
async def admin_schedules(
    request: Request,
    pagination: tuple[int, int] = Depends(page_query),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    student_id: str = student_id_query(),
    actor: ActorContext = Depends(get_admin),
):
    page, page_size = pagination
    data = await service.list_admin_schedules(
        actor,
        student_id=student_id,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date,
    )
    return envelope(request, data)


@router.post("/admin/schedules", operation_id="createSchedule", status_code=201, response_model=Envelope[Schedule], responses=ERROR_RESPONSES)
async def create_schedule(
    request: Request,
    body: ScheduleCreate,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.create_schedule(actor, body, request_id_of(request))
    return envelope(request, data, status_code=201)


@router.patch("/admin/schedules/{id}", operation_id="patchSchedule", response_model=Envelope[Schedule], responses=ERROR_RESPONSES)
async def patch_schedule(
    request: Request,
    body: SchedulePatch,
    id: str = id_path(),
    actor: ActorContext = Depends(get_admin),
):
    data = await service.patch_schedule(actor, id, body, request_id_of(request))
    return envelope(request, data)


@router.delete("/admin/schedules/{id}", operation_id="deleteSchedule", response_model=Envelope[ScheduleDelete], responses=ERROR_RESPONSES)
async def delete_schedule(
    request: Request,
    expected_version: ExpectedVersion = Query(...),
    id: str = id_path(),
    actor: ActorContext = Depends(get_admin),
):
    data = await service.delete_schedule(
        actor, id, expected_version, request_id_of(request)
    )
    return envelope(request, data)
