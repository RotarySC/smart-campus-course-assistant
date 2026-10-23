"""课程与课表服务（设计 §6.2 / FR-COURSE / FR-SCH）。

排课算法（顺序固定）：锁操作者与学生 → 验证目标为启用学生 → 锁课程并验证可用 →
检查精确重复 → 检查时间重叠（半开区间）→ 未确认返回 409 + 重叠摘要 → 确认要求非空原因
并重查 → 插入或条件更新 → 写审计并提交。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.adapters.db.models import Course, Schedule, User
from app.adapters.db.uow import UoW, uow
from app.config import get_settings
from app.modules.academics.schemas import (
    CourseCreate,
    CoursePatch,
    ScheduleCreate,
    SchedulePatch,
    course_view,
    schedule_view,
)
from app.modules.operations.service import append_audit
from app.shared.clock import now_utc, parse_time, school_date, to_db
from app.shared.errors import ApiError, map_integrity_error, validation_error
from app.shared.ids import PREFIX_COURSE, PREFIX_SCHEDULE, new_id

MAX_COURSE_NORM_BYTES = 384


def normalize_course_code(code: str) -> tuple[str, bytes]:
    trimmed = code.strip()
    normalized = trimmed.casefold().encode("utf-8")
    if len(normalized) > MAX_COURSE_NORM_BYTES:
        raise validation_error(("code", "课程代码规范化后过长"))
    return trimmed, normalized


def resolve_date_range(
    from_date: date | None, to_date: date | None
) -> tuple[date, date]:
    """只传一端视为单日；两端不传为今天；跨度受配置上限约束（设计 §6.2）。"""
    settings = get_settings()
    if from_date is None and to_date is None:
        today = school_date()
        return today, today
    start = from_date or to_date
    end = to_date or from_date
    assert start is not None and end is not None
    if start > end:
        raise validation_error(("from_date", "开始日期不得晚于结束日期"))
    if (end - start).days > settings.schedule_max_days:
        raise validation_error(
            ("to_date", f"单次查询跨度不得超过 {settings.schedule_max_days} 天")
        )
    return start, end


# --------------------------------------------------------------------------- #
# 课程
# --------------------------------------------------------------------------- #
async def list_courses(
    actor: Any,
    *,
    page: int,
    page_size: int,
    query: str | None,
    enabled: bool | None,
) -> dict[str, Any]:
    conditions = []
    if query:
        conditions.append(
            or_(
                Course.code.contains(query, autoescape=True),
                Course.name.contains(query, autoescape=True),
            )
        )
    if enabled is not None:
        conditions.append(Course.enabled == enabled)
    async with uow() as tx:
        total = await tx.session.scalar(
            select(func.count()).select_from(Course).where(*conditions)
        )
        result = await tx.session.execute(
            select(Course)
            .where(*conditions)
            .order_by(Course.created_at, Course.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list(result.scalars().all())
    return {
        "items": [course_view(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": int(total or 0),
    }


async def create_course(
    actor: Any, command: CourseCreate, request_id: str
) -> dict[str, Any]:
    trimmed, norm = normalize_course_code(command.code)
    now = to_db(now_utc())
    course = Course(
        id=new_id(PREFIX_COURSE),
        code=trimmed,
        code_norm=norm,
        name=command.name,
        description=command.description,
        enabled=bool(command.enabled),
        version=1,
        created_at=now,
        updated_at=now,
    )
    try:
        async with uow() as tx:
            await tx.lock_and_validate_actor(actor)
            tx.session.add(course)
            await tx.session.flush()
            append_audit(
                tx,
                action="course.create",
                object_type="course",
                object_id=course.id,
                result="success",
                request_id=request_id,
                actor_id=actor.user_id,
            )
            await tx.commit()
    except IntegrityError as exc:
        mapped = map_integrity_error(exc)
        raise mapped or ApiError("INTERNAL_ERROR") from None
    return course_view(course)


async def patch_course(
    actor: Any, course_id: str, command: CoursePatch, request_id: str
) -> dict[str, Any]:
    now = to_db(now_utc())
    async with uow() as tx:
        await tx.lock_and_validate_actor(actor)
        course = await tx.lock_course(course_id)
        if course is None:
            raise ApiError("RESOURCE_NOT_FOUND")
        if int(course.version) != command.expected_version:
            raise ApiError("VERSION_CONFLICT")
        provided = command.model_fields_set
        if "name" in provided and command.name is not None:
            course.name = command.name
        if "description" in provided:
            course.description = command.description
        if "enabled" in provided and command.enabled is not None:
            course.enabled = bool(command.enabled)
        course.version = int(course.version) + 1
        course.updated_at = now
        await tx.session.flush()
        append_audit(
            tx,
            action="course.patch",
            object_type="course",
            object_id=course.id,
            result="success",
            request_id=request_id,
            actor_id=actor.user_id,
            metadata={"fields": sorted(provided.intersection({"name", "description", "enabled"}))},
        )
        await tx.commit()
    return course_view(course)


# --------------------------------------------------------------------------- #
# 课表查询
# --------------------------------------------------------------------------- #
def _page_payload(
    rows: Sequence[tuple[Schedule, str]], page: int, page_size: int, total: int,
    start: date, end: date,
) -> dict[str, Any]:
    return {
        "items": [schedule_view(schedule, course_name) for schedule, course_name in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "school_timezone": get_settings().school_timezone,
    }


async def _query_schedules(
    tx: UoW,
    *,
    user_id: str,
    start: date,
    end: date,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    base = (
        select(Schedule, Course.name)
        .join(Course, Course.id == Schedule.course_id)
        .where(
            Schedule.user_id == user_id,
            Schedule.class_date >= start,
            Schedule.class_date <= end,
        )
    )
    total = await tx.session.scalar(
        select(func.count())
        .select_from(Schedule)
        .where(
            Schedule.user_id == user_id,
            Schedule.class_date >= start,
            Schedule.class_date <= end,
        )
    )
    result = await tx.session.execute(
        base.order_by(Schedule.class_date, Schedule.start_time, Schedule.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = [(row[0], row[1]) for row in result.all()]
    return _page_payload(rows, page, page_size, int(total or 0), start, end)


async def list_my_schedules(
    actor: Any,
    *,
    page: int,
    page_size: int,
    from_date: date | None,
    to_date: date | None,
) -> dict[str, Any]:
    start, end = resolve_date_range(from_date, to_date)
    async with uow() as tx:
        return await _query_schedules(
            tx,
            user_id=actor.user_id,
            start=start,
            end=end,
            page=page,
            page_size=page_size,
        )


async def list_admin_schedules(
    actor: Any,
    *,
    student_id: str,
    page: int,
    page_size: int,
    from_date: date | None,
    to_date: date | None,
) -> dict[str, Any]:
    start, end = resolve_date_range(from_date, to_date)
    async with uow() as tx:
        student = await tx.session.get(User, student_id)
        if student is None or student.role != "student":
            raise ApiError("RESOURCE_NOT_FOUND")
        return await _query_schedules(
            tx,
            user_id=student_id,
            start=start,
            end=end,
            page=page,
            page_size=page_size,
        )


# --------------------------------------------------------------------------- #
# 课表写入
# --------------------------------------------------------------------------- #
async def _find_exact_duplicate(
    tx: UoW,
    *,
    user_id: str,
    course_id: str,
    class_date: date,
    start_time,
    end_time,
    exclude_id: str | None,
) -> Schedule | None:
    stmt = select(Schedule).where(
        Schedule.user_id == user_id,
        Schedule.course_id == course_id,
        Schedule.class_date == class_date,
        Schedule.start_time == start_time,
        Schedule.end_time == end_time,
    )
    if exclude_id is not None:
        stmt = stmt.where(Schedule.id != exclude_id)
    result = await tx.session.execute(stmt)
    return result.scalar_one_or_none()


async def _find_overlaps(
    tx: UoW,
    *,
    user_id: str,
    class_date: date,
    start_time,
    end_time,
    exclude_id: str | None,
) -> list[tuple[Schedule, str]]:
    """半开区间 [start, end)：首尾相接不算重叠。"""
    stmt = (
        select(Schedule, Course.name)
        .join(Course, Course.id == Schedule.course_id)
        .where(
            Schedule.user_id == user_id,
            Schedule.class_date == class_date,
            Schedule.start_time < end_time,
            Schedule.end_time > start_time,
        )
        .order_by(Schedule.start_time, Schedule.id)
    )
    if exclude_id is not None:
        stmt = stmt.where(Schedule.id != exclude_id)
    result = await tx.session.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


def _overlap_details(overlaps: Sequence[tuple[Schedule, str]]) -> dict[str, Any]:
    return {"overlaps": [schedule_view(schedule, name) for schedule, name in overlaps]}


async def _check_conflicts(
    tx: UoW,
    *,
    user_id: str,
    course_id: str,
    class_date: date,
    start_time,
    end_time,
    acknowledged: bool | None,
    reason: str | None,
    exclude_id: str | None,
) -> list[tuple[Schedule, str]]:
    duplicate = await _find_exact_duplicate(
        tx,
        user_id=user_id,
        course_id=course_id,
        class_date=class_date,
        start_time=start_time,
        end_time=end_time,
        exclude_id=exclude_id,
    )
    if duplicate is not None:
        # 精确重复始终拒绝，不能以重叠确认放行（FR-SCH-004）。
        raise ApiError("DUPLICATE_SCHEDULE")

    overlaps = await _find_overlaps(
        tx,
        user_id=user_id,
        class_date=class_date,
        start_time=start_time,
        end_time=end_time,
        exclude_id=exclude_id,
    )
    if overlaps:
        if not acknowledged:
            raise ApiError("SCHEDULE_OVERLAP", details=_overlap_details(overlaps))
        if not reason or not reason.strip():
            raise validation_error(("reason", "确认时间重叠时必须填写原因"))
        # 已持有目标学生行锁，重查结果即为提交时视图。
        overlaps = await _find_overlaps(
            tx,
            user_id=user_id,
            class_date=class_date,
            start_time=start_time,
            end_time=end_time,
            exclude_id=exclude_id,
        )
    return overlaps


async def create_schedule(
    actor: Any, command: ScheduleCreate, request_id: str
) -> dict[str, Any]:
    start_time = parse_time(command.start_time)
    end_time = parse_time(command.end_time)
    now = to_db(now_utc())
    async with uow() as tx:
        users = await tx.lock_users_and_validate_actor(actor, [command.student_id])
        student = users.get(command.student_id)
        if student is None or student.role != "student" or not student.enabled:
            raise ApiError("RESOURCE_NOT_FOUND")
        course = await tx.lock_course(command.course_id)
        if course is None:
            raise ApiError("RESOURCE_NOT_FOUND")
        if not course.enabled:
            raise validation_error(("course_id", "课程已停用，不能用于新增课表"))

        overlaps = await _check_conflicts(
            tx,
            user_id=command.student_id,
            course_id=command.course_id,
            class_date=command.class_date,
            start_time=start_time,
            end_time=end_time,
            acknowledged=command.overlap_acknowledged,
            reason=command.reason,
            exclude_id=None,
        )
        schedule = Schedule(
            id=new_id(PREFIX_SCHEDULE),
            user_id=command.student_id,
            course_id=command.course_id,
            class_date=command.class_date,
            start_time=start_time,
            end_time=end_time,
            location=command.location,
            overlap_reason=command.reason if overlaps else None,
            version=1,
            created_at=now,
            updated_at=now,
        )
        tx.session.add(schedule)
        try:
            await tx.session.flush()
        except IntegrityError as exc:
            mapped = map_integrity_error(exc)
            raise mapped or ApiError("INTERNAL_ERROR") from None
        append_audit(
            tx,
            action="schedule.create",
            object_type="schedule",
            object_id=schedule.id,
            result="success",
            request_id=request_id,
            actor_id=actor.user_id,
            metadata={"student_id": command.student_id, "course_id": command.course_id},
        )
        await tx.commit()
    return schedule_view(schedule, course.name)


async def patch_schedule(
    actor: Any, schedule_id: str, command: SchedulePatch, request_id: str
) -> dict[str, Any]:
    now = to_db(now_utc())
    async with uow() as tx:
        current = await tx.session.get(Schedule, schedule_id)
        if current is None:
            raise ApiError("RESOURCE_NOT_FOUND")
        await tx.lock_users_and_validate_actor(actor, [current.user_id])
        schedule = await tx.lock_schedule(schedule_id)
        if schedule is None:
            raise ApiError("RESOURCE_NOT_FOUND")
        if int(schedule.version) != command.expected_version:
            raise ApiError("VERSION_CONFLICT")

        provided = command.model_fields_set
        course_id = (
            command.course_id if "course_id" in provided and command.course_id else schedule.course_id
        )
        if course_id != schedule.course_id:
            course = await tx.lock_course(course_id)
            if course is None:
                raise ApiError("RESOURCE_NOT_FOUND")
            if not course.enabled:
                raise validation_error(("course_id", "课程已停用，不能用于课表变更"))
        else:
            course = await tx.session.get(Course, course_id)
            if course is None:
                raise ApiError("RESOURCE_NOT_FOUND")

        class_date = command.class_date if "class_date" in provided else schedule.class_date
        start_time = (
            parse_time(command.start_time)
            if "start_time" in provided and command.start_time
            else schedule.start_time
        )
        end_time = (
            parse_time(command.end_time)
            if "end_time" in provided and command.end_time
            else schedule.end_time
        )
        if start_time >= end_time:
            raise validation_error(("end_time", "结束时间必须晚于开始时间，且不支持跨日记录"))

        # 仅排课字段变化时才重查冲突；只改地点不应要求重新确认既有重叠。
        time_changed = bool(
            provided.intersection({"course_id", "class_date", "start_time", "end_time"})
        )
        overlaps = (
            await _check_conflicts(
                tx,
                user_id=schedule.user_id,
                course_id=course_id,
                class_date=class_date,
                start_time=start_time,
                end_time=end_time,
                acknowledged=command.overlap_acknowledged,
                reason=command.reason,
                exclude_id=schedule_id,
            )
            if time_changed
            else []
        )

        schedule.course_id = course_id
        schedule.class_date = class_date
        schedule.start_time = start_time
        schedule.end_time = end_time
        if "location" in provided:
            schedule.location = command.location
        if overlaps:
            schedule.overlap_reason = command.reason
        schedule.version = int(schedule.version) + 1
        schedule.updated_at = now
        await tx.session.flush()
        append_audit(
            tx,
            action="schedule.patch",
            object_type="schedule",
            object_id=schedule.id,
            result="success",
            request_id=request_id,
            actor_id=actor.user_id,
            metadata={"fields": sorted(provided.intersection({"course_id", "class_date", "start_time", "end_time", "location"}))},
        )
        await tx.commit()
    return schedule_view(schedule, course.name)


async def delete_schedule(
    actor: Any, schedule_id: str, expected_version: int, request_id: str
) -> dict[str, Any]:
    async with uow() as tx:
        current = await tx.session.get(Schedule, schedule_id)
        if current is None:
            raise ApiError("RESOURCE_NOT_FOUND")
        await tx.lock_users_and_validate_actor(actor, [current.user_id])
        schedule = await tx.lock_schedule(schedule_id)
        if schedule is None:
            raise ApiError("RESOURCE_NOT_FOUND")
        if int(schedule.version) != expected_version:
            raise ApiError("VERSION_CONFLICT")
        await tx.session.delete(schedule)
        audit_id = append_audit(
            tx,
            action="schedule.delete",
            object_type="schedule",
            object_id=schedule_id,
            result="success",
            request_id=request_id,
            actor_id=actor.user_id,
        )
        await tx.commit()
    return {"deleted": True, "schedule_id": schedule_id, "audit_id": audit_id}
