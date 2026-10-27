"""请求级审计耗时拾取（FR-OPS-001「记录……耗时」）。

设计依据：FR-OPS-001 要求管理变更、计划写入、工具执行都记录耗时。此前只有内网工具
审计填了 ``duration_ms``，计划/课表/学生/文档审计为 NULL。

做法：请求进入时由中间件打点，``append_audit`` 在调用方没显式给 ``duration_ms`` 时
自动取用；worker / CLI 路径没有请求上下文，保持 NULL（不臆造耗时）。
"""

from __future__ import annotations

import time
from contextvars import ContextVar

_started_at: ContextVar[float | None] = ContextVar("cca_request_started_at", default=None)


def mark_request_start() -> None:
    _started_at.set(time.perf_counter())


def reset_request_timing() -> None:
    _started_at.set(None)


def current_duration_ms() -> int | None:
    """当前请求已耗时毫秒；无请求上下文时返回 None。"""
    started = _started_at.get()
    if started is None:
        return None
    return max(0, int((time.perf_counter() - started) * 1000))


__all__ = ["current_duration_ms", "mark_request_start", "reset_request_timing"]
