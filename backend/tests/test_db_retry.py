"""``tests/db_retry.py`` 的判定口径测试（不连库，纯分类与退避逻辑）。

这些用例存在的原因：重试机制最大的风险是"把真失败也重试掉"，因此必须把
「哪些错误重试、哪些立刻抛」和「退避有界」写成可断言的契约。
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError

from db_retry import (
    RETRYABLE_ERRNOS,
    driver_errno,
    is_retryable,
    run_with_retry,
    subprocess_error_is_retryable,
)


class _FakeDriverError(Exception):
    """替身：pymysql 的 ``OperationalError(2003, "Can't connect ...")`` 形态。"""


def _dbapi(error_cls, *args):
    return error_cls("SELECT 1", {}, _FakeDriverError(*args))


def test_driver_errno_comes_from_driver_args() -> None:
    assert driver_errno(_dbapi(OperationalError, 2003, "Can't connect")) == 2003
    assert driver_errno(ValueError("boom")) is None


@pytest.mark.parametrize("errno", sorted(RETRYABLE_ERRNOS))
def test_connection_errors_are_retryable(errno: int) -> None:
    assert is_retryable(_dbapi(OperationalError, errno, "transient"))


def test_constraint_and_business_errors_are_not_retryable() -> None:
    # 唯一键冲突 / 语法错误 / 非 SQLAlchemy 异常都不得重试
    assert not is_retryable(_dbapi(IntegrityError, 1062, "Duplicate entry"))
    assert not is_retryable(_dbapi(OperationalError, 1064, "You have an error in your SQL syntax"))
    assert not is_retryable(AssertionError("用例自己的断言失败"))


@pytest.mark.asyncio
async def test_retry_recovers_from_transient_failure() -> None:
    calls: list[int] = []

    async def operation() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise _dbapi(OperationalError, 2003, "Can't connect to MySQL server")
        return "ok"

    result = await run_with_retry(operation, what="unit", attempts=4, base_delay=0.0)

    assert result == "ok"
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_retry_gives_up_and_reraises_last_error() -> None:
    calls: list[int] = []

    async def operation() -> None:
        calls.append(1)
        raise _dbapi(OperationalError, 2013, "Lost connection to MySQL server")

    with pytest.raises(OperationalError) as excinfo:
        await run_with_retry(operation, what="unit", attempts=3, base_delay=0.0)

    assert len(calls) == 3
    assert driver_errno(excinfo.value) == 2013


@pytest.mark.asyncio
async def test_non_retryable_error_is_raised_on_first_attempt() -> None:
    calls: list[int] = []

    async def operation() -> None:
        calls.append(1)
        raise _dbapi(IntegrityError, 1062, "Duplicate entry")

    with pytest.raises(IntegrityError):
        await run_with_retry(operation, what="unit", attempts=4, base_delay=0.0)

    assert len(calls) == 1


def test_alembic_subprocess_noise_detection() -> None:
    stderr = "sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (2003, \"Can't connect to MySQL server on '127.0.0.1'\")"
    assert subprocess_error_is_retryable(stderr)
    # 真正的迁移错误不能被当成噪声重试
    assert not subprocess_error_is_retryable(
        "alembic.util.exc.CommandError: Can't locate revision identified by '0003'"
    )
