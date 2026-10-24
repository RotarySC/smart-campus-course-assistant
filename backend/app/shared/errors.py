"""统一错误语义（SRS IF-010 / 后端详细设计 §3.3）。

- 所有对外错误使用稳定业务 code，HTTP 状态只由本表决定。
- 禁止把 SQL / 驱动原文、口令摘要、令牌写入 message 或 details。
"""

from __future__ import annotations

from typing import Any, Final

# ---- 错误码 → HTTP 状态（SRS §8 错误码表）----
ERROR_STATUS: Final[dict[str, int]] = {
    "AUTH_REQUIRED": 401,
    "SESSION_EXPIRED": 401,
    "FORBIDDEN": 403,
    "RESOURCE_NOT_FOUND": 404,
    "DUPLICATE_ACCOUNT": 409,
    "DUPLICATE_COURSE": 409,
    "DUPLICATE_SCHEDULE": 409,
    "VERSION_CONFLICT": 409,
    "SCHEDULE_OVERLAP": 409,
    "CHAT_IN_PROGRESS": 409,
    "REQUEST_ALREADY_EXISTS": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "SAVE_LIMIT_REACHED": 409,
    "DOCUMENT_BUSY": 409,
    "DUPLICATE_FILENAME": 409,
    "DRAFT_EXPIRED": 410,
    "CITATION_UNAVAILABLE": 410,
    "UPLOAD_TOO_LARGE": 413,
    "UNSUPPORTED_FILE_TYPE": 415,
    "VALIDATION_FAILED": 422,
    "SAVE_NOT_AUTHORIZED": 422,
    "CAPACITY_LIMITED": 429,
    "MODEL_UNAVAILABLE": 503,
    "RETRIEVAL_UNAVAILABLE": 503,
    "MCP_UNAVAILABLE": 503,
    "STORAGE_UNAVAILABLE": 503,
    "EXECUTION_TIMEOUT": 504,
    "CALL_LIMIT_REACHED": 504,
    "INTERNAL_ERROR": 500,
}

# ---- 面向用户的安全文案（不含内部细节）----
ERROR_MESSAGE: Final[dict[str, str]] = {
    "AUTH_REQUIRED": "请先登录",
    "SESSION_EXPIRED": "会话已失效，请重新登录",
    "FORBIDDEN": "无权执行该操作",
    "RESOURCE_NOT_FOUND": "请求的资源不存在",
    "DUPLICATE_ACCOUNT": "账号已存在",
    "DUPLICATE_COURSE": "课程代码已存在",
    "DUPLICATE_SCHEDULE": "该课表记录已存在",
    "VERSION_CONFLICT": "数据已被其他操作更新，请重新加载后再提交",
    "SCHEDULE_OVERLAP": "课表时间存在重叠",
    "CHAT_IN_PROGRESS": "当前会话已有执行中的请求",
    "REQUEST_ALREADY_EXISTS": "该请求标识已存在",
    "IDEMPOTENCY_CONFLICT": "同一操作标识对应了不同内容",
    "SAVE_LIMIT_REACHED": "该请求已创建过一份计划",
    "DOCUMENT_BUSY": "该文档正在被其他操作处理",
    "DUPLICATE_FILENAME": "存在同名文件待处理",
    "DRAFT_EXPIRED": "草稿已过期，请重新生成",
    "CITATION_UNAVAILABLE": "引用已失效",
    "UPLOAD_TOO_LARGE": "上传文件超过大小限制",
    "UNSUPPORTED_FILE_TYPE": "不支持该文件类型",
    "VALIDATION_FAILED": "请检查输入内容",
    "SAVE_NOT_AUTHORIZED": "保存许可不成立，请重新生成或使用保存按钮",
    "CAPACITY_LIMITED": "当前请求过多，请稍后重试",
    "MODEL_UNAVAILABLE": "模型服务暂不可用",
    "RETRIEVAL_UNAVAILABLE": "检索服务暂不可用",
    "MCP_UNAVAILABLE": "工具服务暂不可用",
    "STORAGE_UNAVAILABLE": "数据服务暂不可用",
    "EXECUTION_TIMEOUT": "执行超时",
    "CALL_LIMIT_REACHED": "执行预算已耗尽",
    "INTERNAL_ERROR": "服务内部错误",
}


class ApiError(Exception):
    """业务错误：由全局异常处理器渲染为统一错误信封。"""

    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        field_errors: list[dict[str, str]] | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        self.code = code
        self.message = message or ERROR_MESSAGE.get(code, ERROR_MESSAGE["INTERNAL_ERROR"])
        self.field_errors = field_errors
        self.details = details
        self.status_code = status_code or ERROR_STATUS.get(code, 500)
        super().__init__(self.message)


def field_error(field: str, reason: str) -> dict[str, str]:
    return {"field": field[:100], "reason": reason[:500]}


def validation_error(*errors: tuple[str, str]) -> ApiError:
    return ApiError(
        "VALIDATION_FAILED",
        field_errors=[field_error(field, reason) for field, reason in errors],
    )


# ---- DB 唯一键 → 业务错误码映射（只看约束名，不透出驱动原文）----
UNIQUE_KEY_ERRORS: Final[dict[str, str]] = {
    "uq_users_account": "DUPLICATE_ACCOUNT",
    "uq_courses_code": "DUPLICATE_COURSE",
    "uq_schedule_exact": "DUPLICATE_SCHEDULE",
    "uq_sessions_token": "INTERNAL_ERROR",
    "uq_chat_client": "REQUEST_ALREADY_EXISTS",
    "uq_plan_operation": "IDEMPOTENCY_CONFLICT",
    "uq_draft_operation": "INTERNAL_ERROR",
    "uq_capacity_request": "CAPACITY_LIMITED",
    "uq_task_action": "DOCUMENT_BUSY",
    "uq_document_version": "DOCUMENT_BUSY",
}


def map_integrity_error(exc: BaseException) -> ApiError | None:
    """把 SQLAlchemy IntegrityError 映射为业务错误；无法识别返回 None。

    注意：只读取约束名，绝不拼接驱动原文进 message。
    """
    raw = str(getattr(exc, "orig", exc))
    for key, code in UNIQUE_KEY_ERRORS.items():
        if key in raw:
            return ApiError(code)
    if "Duplicate entry" in raw or "1062" in raw:
        return ApiError("INTERNAL_ERROR")
    return None
