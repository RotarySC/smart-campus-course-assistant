"""响应模型（OpenAPI 运行态契约）。

说明：
- 类名与 ``docs/backend/openapi_v0.1.json`` 的 components.schemas 名称逐字一致，
  便于前端 ``openapi-typescript`` 生成与漂移门禁比对。
- 路由实际返回 ``JSONResponse``（信封由 ``shared.http.envelope`` 组装），响应模型只用于
  OpenAPI 文档与契约测试；字段名/可空性/枚举仍以设计包为权威。
- ``Envelope[T]`` 对应设计包中每个响应内联的 ``{request_id, data}`` 结构。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    request_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    data: T


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- 错误 ----
class FieldError(_Strict):
    field: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)


class ErrorDetails(_Strict):
    existing_request_id: str | None = None
    operation_id: str | None = None
    plan_id: str | None = None
    state: Literal["pending", "succeeded", "failed", "deleted"] | None = None
    overlaps: list["Schedule"] | None = None
    retryable: bool | None = None


class ErrorObject(_Strict):
    code: str
    message: str = Field(min_length=1, max_length=500)
    field_errors: list[FieldError] | None = None
    details: ErrorDetails | None = None


class Error(_Strict):
    request_id: str
    error: ErrorObject


# ---- 身份 ----
class User(_Strict):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    account: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=50)
    role: Literal["student", "admin"]
    enabled: bool
    version: int = Field(ge=1)


class Login(_Strict):
    access_token: str = Field(min_length=1, max_length=256)
    token_type: Literal["Bearer"]
    expires_at: datetime
    user: User


class Logout(_Strict):
    revoked: Literal[True]


class Me(_Strict):
    user: User
    session_expires_at: datetime
    school_timezone: str = Field(min_length=1, max_length=64)
    capabilities: list[str]


class StudentPage(_Strict):
    items: list[User]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


# ---- 课程与课表 ----
class Course(_Strict):
    id: str
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    # 设计包 required（可空但键必须存在）
    description: str | None = Field(max_length=2000)
    enabled: bool
    version: int = Field(ge=1)


class CoursePage(_Strict):
    items: list[Course]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class Schedule(_Strict):
    id: str
    student_id: str
    course_id: str
    course_name: str = Field(min_length=1, max_length=100)
    class_date: date
    start_time: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    end_time: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    # 设计包 required（可空但键必须存在）
    location: str | None = Field(max_length=200)
    version: int = Field(ge=1)


class SchedulePage(_Strict):
    items: list[Schedule]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    from_date: date
    to_date: date
    school_timezone: str


class ScheduleDelete(_Strict):
    deleted: Literal[True]
    schedule_id: str
    audit_id: str


# ---- 计划 / 草稿 / 保存 ----
class Reference(_Strict):
    reference_id: str
    document_id: str
    version_id: str
    file_name: str = Field(min_length=1, max_length=255)
    location_label: str = Field(min_length=1, max_length=100)
    page_number: int | None = Field(default=None, ge=1)


class Plan(_Strict):
    id: str
    title: str = Field(min_length=1, max_length=100)
    goal: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    content: str = Field(min_length=1, max_length=10000)
    source: Literal["manual", "assistant"]
    basis_types: list[Literal["schedule", "documents", "general"]]
    references: list[Reference]
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class PlanPage(_Strict):
    items: list[Plan]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class Draft(_Strict):
    draft_id: str
    draft_version: int = Field(ge=1)
    operation_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=100)
    goal: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    content: str = Field(min_length=1, max_length=10000)
    basis_types: list[Literal["schedule", "documents", "general"]]
    references: list[Reference]
    expires_at: datetime


class SaveCreatedResult(_Strict):
    status: Literal["created"]
    operation_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9._:-]+$")
    plan_id: str


class SaveReusedResult(_Strict):
    status: Literal["existing", "deleted"]
    operation_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9._:-]+$")
    plan_id: str


class WriteOperation(_Strict):
    operation_id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9._:-]+$")
    state: Literal["pending", "succeeded", "failed", "deleted"]
    resolution: Literal["confirmed", "recovering"]
    # 可选但非 nullable（设计包类型为 string，缺省时键不出现）
    plan_id: str = Field(default=None)  # type: ignore[assignment]
    error_code: str = Field(default=None)  # type: ignore[assignment]
    retryable: bool


class PlanDelete(_Strict):
    deleted: Literal[True]
    plan_id: str
    version: int = Field(ge=1)


class Health(_Strict):
    status: Literal["ok", "degraded"]
    checks: dict[str, Any]


# 标准错误响应（与设计包每个 operation 的 400–504 声明一致）
_ERROR_DESCRIPTIONS = {
    400: "请求不合法",
    401: "未认证或会话失效",
    403: "角色无权操作",
    404: "资源不存在或不属于当前用户",
    409: "唯一键/版本/重叠/幂等冲突",
    410: "临时内容或引用失效",
    413: "上传超过限额",
    415: "不支持的文件类型",
    422: "字段校验失败或许可不成立",
    429: "达到并发保护上限",
    500: "未预期系统错误",
    503: "依赖服务暂不可用",
    504: "执行预算耗尽",
}
ERROR_RESPONSES = {
    code: {"model": Error, "description": description}
    for code, description in _ERROR_DESCRIPTIONS.items()
}

# 前向引用（ErrorDetails.overlaps → Schedule）
ErrorDetails.model_rebuild()

__all__ = [
    "ERROR_RESPONSES",
    "Course",
    "CoursePage",
    "Draft",
    "Envelope",
    "Error",
    "ErrorDetails",
    "ErrorObject",
    "FieldError",
    "Health",
    "Login",
    "Logout",
    "Me",
    "Plan",
    "PlanDelete",
    "PlanPage",
    "Reference",
    "SaveCreatedResult",
    "SaveReusedResult",
    "Schedule",
    "ScheduleDelete",
    "SchedulePage",
    "StudentPage",
    "User",
    "WriteOperation",
]
