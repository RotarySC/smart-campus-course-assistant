"""日志脱敏（NFR-PRIV-001 / FR-OPS-001 末句）。

默认不把问答、课表、计划、资料正文与凭据写进日志。审计发现的现实风险是
``logger.exception`` 会把 SQLAlchemy 的 ``[parameters: ...]``（含计划正文、口令哈希入参）
整段带进日志，因此这里在 **formatter 之前** 做两层脱敏：

1. SQLAlchemy 的 ``[parameters: ...]`` / ``[SQL: ...]`` 块整段替换为 ``<redacted>``；
2. ``password=...`` / ``token: ...`` / ``Authorization: Bearer ...`` 等键值脱敏。

过滤发生在 Formatter 里格式化 traceback 之前：先把异常格式化成文本、脱敏，再赋给
``record.exc_text`` 并清空 ``exc_info``，这样 traceback 里的参数块也会被覆盖。
"""

from __future__ import annotations

import logging
import re
import traceback

_SQL_PARAMS = re.compile(r"\[parameters:.*?\]", re.DOTALL)
_SQL_STATEMENT = re.compile(r"\[SQL:.*?\]", re.DOTALL)
_SECRET_PAIR = re.compile(
    r"(?i)([\"']?)\b(password|passwd|pwd|secret|token|access_token|refresh_token|"
    r"api[_-]?key|authorization|set-cookie)\b\1\s*[:=]\s*"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;)\]]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")


def redact(text: str) -> str:
    """把正文参数块与凭据形态的片段替换成占位符（纯函数，便于单测）。"""
    if not text:
        return text
    cleaned = _SQL_PARAMS.sub("[parameters: <redacted>]", text)
    cleaned = _SQL_STATEMENT.sub("[SQL: <redacted>]", cleaned)
    # 先处理 Bearer，避免 "Authorization: Bearer xxx" 只脱掉 scheme 留下令牌
    cleaned = _BEARER.sub("Bearer <redacted>", cleaned)
    cleaned = _SECRET_PAIR.sub(lambda m: f"{m.group(2)}=<redacted>", cleaned)
    return cleaned


class RedactFilter(logging.Filter):
    """把日志消息与异常 traceback 里的正文/凭据脱敏。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            text = "".join(traceback.format_exception(*record.exc_info))
            record.exc_text = redact(text)
            record.exc_info = None
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - 格式化失败也不能把日志吞掉
            message = str(record.msg)
        record.msg = redact(message)
        record.args = ()
        return True


def install_redaction(target: logging.Logger | None = None) -> None:
    """给目标 logger 的处理器挂上脱敏过滤器（幂等）。"""
    root = target or logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(item, RedactFilter) for item in handler.filters):
            handler.addFilter(RedactFilter())


__all__ = ["RedactFilter", "install_redaction", "redact"]
