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
from app.shared.http import envelope, page_query, parse_optional_bool, request_id_of
from app.shared.validation import ExpectedVersion

router = APIRouter(tags=["academics"])

ID_PATH = Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
STUDENT_ID_QUERY = Query(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


# ---- 课程 ----
@router.get("/admin/courses", operation_id="listCourses")
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


@router.post("/admin/courses", operation_id="createCourse")
async def create_course(
    request: Request,
    body: CourseCreate,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.create_course(actor, body, request_id_of(request))
    return envelope(request, data, status_code=201)


@router.patch("/admin/courses/{id}", operation_id="patchCourse")
async def patch_course(
    request: Request,
    body: CoursePatch,
    id: str = ID_PATH,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.patch_course(actor, id, body, request_id_of(request))
    return envelope(request, data)


# ---- 课表 ----
@router.get("/me/schedules", operation_id="mySchedules")
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


@router.get("/admin/schedules", operation_id="adminSchedules")
async def admin_schedules(
    request: Request,
    pagination: tuple[int, int] = Depends(page_query),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    student_id: str = STUDENT_ID_QUERY,
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


@router.post("/admin/schedules", operation_id="createSchedule")
async def create_schedule(
    request: Request,
    body: ScheduleCreate,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.create_schedule(actor, body, request_id_of(request))
    return envelope(request, data, status_code=201)


@router.patch("/admin/schedules/{id}", operation_id="patchSchedule")
async def patch_schedule(
    request: Request,
    body: SchedulePatch,
    id: str = ID_PATH,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.patch_schedule(actor, id, body, request_id_of(request))
    return envelope(request, data)


@router.delete("/admin/schedules/{id}", operation_id="deleteSchedule")
async def delete_schedule(
    request: Request,
    expected_version: ExpectedVersion = Query(...),
    id: str = ID_PATH,
    actor: ActorContext = Depends(get_admin),
):
    data = await service.delete_schedule(
        actor, id, expected_version, request_id_of(request)
    )
    return envelope(request, data)
