"""测试环境数据库连接重试：只抑制连接层瞬时噪声，不掩盖断言失败。

背景：测试库跑在 Docker Desktop 端口映射（``127.0.0.1:33061``）后面。全量用例
（200+ 例、每例多次短连接，测试环境用 ``NullPool`` 即每次新建 TCP 连接）偶发 1 例
在 fixture 建立连接时拿到 ``pymysql.err.OperationalError(2003, "Can't connect to
MySQL server")`` 或 2013/1040。容器本身健康（``Up``，``Restarts 0``），重试一次即消失；
若不处理，全量结果会带上 1 例与用例语义无关的假失败。

约束（判定口径写死在测试里，见 ``test_db_retry.py``）：
- 只对连接层 / 服务端暂不可用错误（2002/2003/2005/2006/2013/1040/1203/1053）重试；
- 语法错误、约束冲突、业务错误码、断言失败一律**不重试**，照常抛出；
- 重试次数与退避可由环境变量配置；每次重试都以 WARNING 记录，不静默吞掉。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger("tests.db_retry")

# MySQL 客户端/服务端"连不上/连上被掐/连接数满/正在关闭"类错误码。
RETRYABLE_ERRNOS = frozenset({2002, 2003, 2005, 2006, 2013, 1040, 1203, 1053})

DEFAULT_ATTEMPTS = 4
DEFAULT_BASE_DELAY = 0.5

T = TypeVar("T")


def retry_attempts() -> int:
    """总尝试次数（含首次），默认 4；``CCA_TEST_DB_RETRY_ATTEMPTS=1`` 可关闭重试。"""
    try:
        value = int(os.environ.get("CCA_TEST_DB_RETRY_ATTEMPTS", str(DEFAULT_ATTEMPTS)))
    except ValueError:
        return DEFAULT_ATTEMPTS
    return max(1, value)


def retry_base_delay() -> float:
    """首次退避秒数，之后翻倍（默认 0.5 → 1.0 → 2.0），上限 8s。"""
    try:
        value = float(os.environ.get("CCA_TEST_DB_RETRY_BASE_DELAY", str(DEFAULT_BASE_DELAY)))
    except ValueError:
        return DEFAULT_BASE_DELAY
    return max(0.0, min(value, 8.0))


def driver_errno(exc: BaseException) -> int | None:
    """取底层驱动的错误码（``pymysql.err.*`` 的 ``args[0]``）。"""
    orig = getattr(exc, "orig", exc)
    args = getattr(orig, "args", ())
    if args and isinstance(args[0], int):
        return args[0]
    return None


def is_retryable(exc: BaseException) -> bool:
    """仅 SQLAlchemy 包装且底层错误码属连接层时才算可重试。"""
    from sqlalchemy.exc import DBAPIError

    if not isinstance(exc, DBAPIError):
        return False
    return driver_errno(exc) in RETRYABLE_ERRNOS


async def run_with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    what: str,
    attempts: int | None = None,
    base_delay: float | None = None,
) -> T:
    """执行 ``operation``，连接层错误时按指数退避重试；其它异常立即抛出。"""
    total = attempts if attempts is not None else retry_attempts()
    delay = base_delay if base_delay is not None else retry_base_delay()
    for attempt in range(1, total + 1):
        try:
            return await operation()
        except Exception as exc:  # noqa: BLE001 - 分类后决定重试或抛出
            if attempt >= total or not is_retryable(exc):
                raise
            logger.warning(
                "数据库连接失败，%s 第 %d/%d 次重试（errno=%s，%.1fs 后）：%s",
                what,
                attempt,
                total,
                driver_errno(exc),
                delay,
                exc.__class__.__name__,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 8.0)
    raise AssertionError("unreachable")  # pragma: no cover


async def wait_for_database(*, what: str = "等待测试库就绪") -> None:
    """会话开始时确认测试库可连接（容器/端口映射刚起来时的等待窗口）。"""
    from sqlalchemy import text

    from app.adapters.db.engine import get_engine

    async def _ping() -> None:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))

    await run_with_retry(_ping, what=what)


def subprocess_error_is_retryable(stderr: str) -> bool:
    """``alembic upgrade`` 子进程失败是否属连接层噪声（无异常对象可用，按文本判）。"""
    markers = (
        "Can't connect to MySQL server",
        "Lost connection to MySQL server",
        "Too many connections",
        "MySQL server has gone away",
        "Connection reset by peer",
    )
    if any(marker in stderr for marker in markers):
        return True
    return any(str(code) in stderr for code in (2002, 2003, 2006, 2013, 1040, 1203))


__all__ = [
    "RETRYABLE_ERRNOS",
    "driver_errno",
    "is_retryable",
    "run_with_retry",
    "wait_for_database",
    "subprocess_error_is_retryable",
]
