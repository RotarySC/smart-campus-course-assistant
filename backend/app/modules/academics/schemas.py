"""课程与课表 Schema / 视图（字段以 OpenAPI 为权威）。"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.adapters.db.models import Course, Schedule
from app.shared.clock import time_str
from app.shared.validation import ExpectedVersion, RequestModel, StrictBool

TIME_PATTERN = r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"
ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class CourseCreate(RequestModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    enabled: StrictBool = True

    @field_validator("code")
    @classmethod
    def _code_trimmed(cls, value: str) -> str:
        trimmed = value.strip()
        if not (1 <= len(trimmed) <= 32):
            raise ValueError("课程代码去首尾空白后长度必须为 1–32")
        return trimmed

    @field_validator("name")
    @classmethod
    def _name_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("课程名称不能为空白")
        return value


class CoursePatch(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    enabled: StrictBool | None = None
    expected_version: ExpectedVersion

    @model_validator(mode="after")
    def _patch_shape(self) -> "CoursePatch":
        provided = self.model_fields_set
        if not provided.intersection({"name", "description", "enabled"}):
            raise ValueError("至少提供 name、description、enabled 之一")
        for name in ("name", "enabled"):
            if name in provided and getattr(self, name) is None:
                raise ValueError(f"{name} 不允许为 null")
        if "name" in provided and not (self.name or "").strip():
            raise ValueError("课程名称不能为空白")
        return self


class ScheduleCreate(RequestModel):
    student_id: str = Field(min_length=1, max_length=64, pattern=ID_PATTERN)
    course_id: str = Field(min_length=1, max_length=64, pattern=ID_PATTERN)
    class_date: date
    start_time: str = Field(pattern=TIME_PATTERN)
    end_time: str = Field(pattern=TIME_PATTERN)
    location: str | None = Field(default=None, max_length=200)
    overlap_acknowledged: StrictBool | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def _times_ordered(self) -> "ScheduleCreate":
        if self.start_time >= self.end_time:
            raise ValueError("结束时间必须晚于开始时间，且不支持跨日记录")
        return self


class SchedulePatch(RequestModel):
    course_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=ID_PATTERN)
    class_date: date | None = None
    start_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    end_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    location: str | None = Field(default=None, max_length=200)
    overlap_acknowledged: StrictBool | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=500)
    expected_version: ExpectedVersion

    @model_validator(mode="after")
    def _patch_shape(self) -> "SchedulePatch":
        provided = self.model_fields_set
        mutable = {"course_id", "class_date", "start_time", "end_time", "location"}
        if not provided.intersection(mutable):
            raise ValueError("至少提供一个可修改字段")
        for name in ("course_id", "class_date", "start_time", "end_time"):
            if name in provided and getattr(self, name) is None:
                raise ValueError(f"{name} 不允许为 null")
        return self


def course_view(course: Course) -> dict[str, Any]:
    return {
        "id": course.id,
        "code": course.code,
        "name": course.name,
        "description": course.description,
        "enabled": bool(course.enabled),
        "version": int(course.version),
    }


def schedule_view(schedule: Schedule, course_name: str) -> dict[str, Any]:
    return {
        "id": schedule.id,
        "student_id": schedule.user_id,
        "course_id": schedule.course_id,
        "course_name": course_name,
        "class_date": schedule.class_date.isoformat(),
        "start_time": time_str(schedule.start_time),
        "end_time": time_str(schedule.end_time),
        "location": schedule.location,
        "version": int(schedule.version),
    }
