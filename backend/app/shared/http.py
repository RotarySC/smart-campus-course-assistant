"""HTTP 通用层：request_id、统一信封、异常处理器、严格查询参数校验。

契约依据：后端详细设计 §3.1、§3.2、§3.3；SRS IF-001 / IF-010。
"""

from __future__ import annotations

import logging
import re
import time
from contextlib import suppress
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute, APIRouter as FastAPIRouter
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.routing import Match
from starlette.types import ASGIApp

from app.config import get_settings
from app.shared import ids
from app.shared.audit_timing import mark_request_start, reset_request_timing
from app.shared.errors import ApiError, field_error, validation_error

logger = logging.getLogger("cca.http")

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# 常见 Pydantic 校验错误 → 面向用户的安全说明
_VALIDATION_REASONS = {
    "missing": "该字段必填",
    "extra_forbidden": "不允许的字段",
    "string_too_short": "长度不足",
    "string_too_long": "长度超出上限",
    "string_pattern_mismatch": "格式不正确",
    "string_type": "必须是字符串",
    "int_type": "必须是整数",
    "int_parsing": "必须是整数",
    "bool_type": "必须是布尔值",
    "bool_parsing": "必须是布尔值",
    "greater_than_equal": "数值过小",
    "less_than_equal": "数值过大",
    "greater_than": "数值过小",
    "less_than": "数值过大",
    "date_from_datetime_parsing": "日期格式不正确",
    "date_parsing": "日期格式不正确",
    "date_type": "日期格式不正确",
    "time_parsing": "时间格式不正确",
    "list_type": "必须是数组",
    "dict_type": "必须是对象",
    "model_type": "必须是对象",
    "json_invalid": "请求体不是合法 JSON",
    "value_error": "取值不合法",
    "enum": "取值不在允许范围",
    "literal_error": "取值不在允许范围",
}


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "") or ids.new_id(ids.PREFIX_REQUEST)


def envelope(request: Request, data: Any, *, status_code: int = 200) -> JSONResponse:
    """成功信封：``{request_id, data}``。"""
    return JSONResponse(
        {"request_id": request_id_of(request), "data": data},
        status_code=status_code,
    )


def not_implemented(request: Request, feature: str) -> JSONResponse:
    """未实现端点（Phase 2/3 桩）：501 + 统一错误信封。"""
    error = ApiError(
        "INTERNAL_ERROR",
        message=f"{feature} 尚未实现",
        status_code=501,
    )
    return JSONResponse(
        error_body(request_id_of(request), error),
        status_code=501,
    )


def error_body(request_id: str, error: ApiError) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.field_errors:
        payload["field_errors"] = error.field_errors[:100]
    if error.details:
        payload["details"] = error.details
    return {"request_id": request_id, "error": payload}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """注入 request_id、记录结构化访问日志（不记录正文/Authorization）。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if REQUEST_ID_PATTERN.match(incoming) else ids.new_id(ids.PREFIX_REQUEST)
        request.state.request_id = rid
        started = time.perf_counter()
        mark_request_start()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            reset_request_timing()
            duration_ms = int((time.perf_counter() - started) * 1000)
            status_code = response.status_code if response is not None else 500
            logger.info(
                "request %s %s status=%s ms=%s request_id=%s",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                rid,
            )
            if response is not None:
                response.headers["X-Request-ID"] = rid


def _collect_query_names(dependant: Any, acc: set[str]) -> None:
    for model_field in getattr(dependant, "query_params", []) or []:
        acc.add(model_field.alias)
    for sub in getattr(dependant, "dependencies", []) or []:
        _collect_query_names(sub, acc)


async def enforce_strict_query(request: Request) -> None:
    """拒绝未声明的查询参数（设计 §3.1：未知查询参数同样拒绝）。"""
    route = request.scope.get("route")
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return
    allowed: set[str] = set()
    _collect_query_names(dependant, allowed)
    unknown = sorted({key for key in request.query_params.keys() if key not in allowed})
    if unknown:
        raise validation_error(*[(key, "不支持的查询参数") for key in unknown])


class StrictAPIRoute(APIRoute):
    """在路由匹配时记录 route（供严格查询参数校验读取）。"""


def strict_router(*, prefix: str = "", tags: list[str] | None = None) -> APIRouter:
    return APIRouter(
        prefix=prefix,
        tags=tags or None,
        route_class=StrictAPIRoute,
    )


# --------------------------------------------------------------------------- #
# 分页与查询参数工具
# --------------------------------------------------------------------------- #
def page_query(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int | None = Query(default=None, ge=1, le=100, description="每页条数"),
) -> tuple[int, int]:
    settings = get_settings()
    size = page_size or settings.page_default_size
    return page, min(size, settings.page_max_size)


def parse_optional_bool(name: str, raw: str | None) -> bool | None:
    """布尔查询参数不做宽松强转：只接受 ``true`` / ``false``。"""
    if raw is None:
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise validation_error((name, "只接受 true/false"))


# --------------------------------------------------------------------------- #
# 异常处理器
# --------------------------------------------------------------------------- #
def _field_name(location: tuple[Any, ...]) -> str:
    parts = [str(item) for item in location if item not in ("body", "query", "path", "header")]
    return ".".join(parts) or "request"


async def _record_access_denied(request: Request, *, code: str, status_code: int) -> None:
    """FR-OPS-001：权限拒绝/越权访问必须可追踪；审计写失败不得改变响应。"""
    try:
        from app.adapters.db.uow import uow
        from app.modules.operations.service import append_audit

        async with uow() as tx:
            append_audit(
                tx,
                action="access.denied",
                object_type="endpoint",
                object_id=f"{request.method} {request.url.path}"[:64],
                result=code,
                request_id=request_id_of(request),
                actor_id=getattr(request.state, "actor_id", None),
                metadata={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status_code,
                    "code": code,
                },
            )
            await tx.commit()
    except Exception:  # noqa: BLE001 - 审计失败不能影响拒绝响应
        logger.warning("access.denied 审计写入失败 request_id=%s", request_id_of(request))


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        if exc.status_code in (403, 404):
            await _record_access_denied(
                request, code=exc.code, status_code=exc.status_code
            )
        return JSONResponse(
            error_body(request_id_of(request), exc),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors: list[dict[str, str]] = []
        for item in exc.errors():
            kind = str(item.get("type", ""))
            field = _field_name(tuple(item.get("loc", ())))
            reason = _VALIDATION_REASONS.get(kind, "取值不合法")
            field_errors.append(field_error(field, reason))
        if not field_errors:
            field_errors = [field_error("request", "请求参数不合法")]
        error = ApiError(
            "VALIDATION_FAILED",
            message="请检查输入内容",
            field_errors=field_errors,
        )
        return JSONResponse(error_body(request_id_of(request), error), status_code=422)

    @app.exception_handler(ValidationError)
    async def _pydantic_validation(request: Request, exc: ValidationError) -> JSONResponse:
        field_errors = [
            field_error(
                _field_name(tuple(item.get("loc", ()))),
                _VALIDATION_REASONS.get(str(item.get("type", "")), "取值不合法"),
            )
            for item in exc.errors()
        ] or [field_error("request", "请求参数不合法")]
        error = ApiError("VALIDATION_FAILED", field_errors=field_errors)
        return JSONResponse(error_body(request_id_of(request), error), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        if exc.status_code == 401:
            code, message = "AUTH_REQUIRED", None
        elif exc.status_code == 403:
            code, message = "FORBIDDEN", None
        elif exc.status_code == 404:
            code, message = "RESOURCE_NOT_FOUND", None
        elif exc.status_code == 405:
            code, message = "VALIDATION_FAILED", "请求方法不被支持"
        else:
            code, message = "INTERNAL_ERROR", None
        error = ApiError(code, message=message)
        error.status_code = exc.status_code
        if exc.status_code in (403, 404):
            await _record_access_denied(
                request, code=code, status_code=exc.status_code
            )
        return JSONResponse(
            error_body(request_id_of(request), error),
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = request_id_of(request)
        # 不把 SQL/驱动原文返回客户端；日志同样不记录正文与参数。
        if get_settings().env == "dev":
            logger.exception("unhandled error request_id=%s", rid)
        else:
            logger.error(
                "unhandled error request_id=%s type=%s", rid, type(exc).__name__
            )
        error = ApiError("INTERNAL_ERROR")
        return JSONResponse(error_body(rid, error), status_code=500)
