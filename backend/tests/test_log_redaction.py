"""日志脱敏（NFR-PRIV-001）：正文与凭据不得默认进日志。

审计发现的现实风险是 ``logger.exception`` 把 SQLAlchemy 的 ``[parameters: ...]``
（计划正文、口令摘要入参）整段写进日志。这里锁住三层：
1. 纯函数 ``redact`` 的替换规则；
2. ``RedactFilter`` 对 **异常 traceback** 也生效（在 formatter 之前格式化再脱敏）；
3. ``install_redaction`` 幂等，重复调用不会重复挂过滤器。
"""

from __future__ import annotations

import io
import logging

import pytest
from sqlalchemy.exc import OperationalError

from app.shared.log_redaction import RedactFilter, install_redaction, redact


def test_redact_strips_sqlalchemy_parameter_block() -> None:
    text = (
        "(pymysql.err.OperationalError) (3819, 'boom') "
        "[SQL: INSERT INTO study_plans (content) VALUES (%s)] "
        "[parameters: ('这是一份计划的正文，不应出现在日志里',)]"
    )
    cleaned = redact(text)

    assert "计划的正文" not in cleaned
    assert "[parameters: <redacted>]" in cleaned
    assert "[SQL: <redacted>]" in cleaned


@pytest.mark.parametrize(
    "secret_text",
    [
        "login password='hunter2'",
        'body={"token": "abc.def.ghi"}',
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
        "api_key=sk-live-123456",
        "Set-Cookie: cca_session=xyz",
    ],
)
def test_redact_masks_credentials(secret_text: str) -> None:
    cleaned = redact(secret_text)
    for fragment in ("hunter2", "abc.def.ghi", "eyJhbGciOiJIUzI1NiJ9", "sk-live-123456", "xyz"):
        assert fragment not in cleaned
    assert "<redacted>" in cleaned


def test_redact_keeps_non_secret_text_untouched() -> None:
    assert redact("计划已保存 plan_id=plan_abc") == "计划已保存 plan_id=plan_abc"


def test_filter_redacts_exception_traceback() -> None:
    try:
        raise OperationalError(
            "INSERT INTO study_plans",
            {},
            Exception("(3819) boom"),
            None,
        )
    except OperationalError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="cca.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="写入失败 password='hunter2'",
        args=(),
        exc_info=exc_info,
    )
    assert RedactFilter().filter(record) is True
    assert record.exc_info is None
    assert record.exc_text is not None
    assert "hunter2" not in record.msg
    assert "hunter2" not in record.exc_text
    assert "<redacted>" in record.msg


def test_install_redaction_is_idempotent_and_effective() -> None:
    logger = logging.getLogger("cca.test.redaction")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers = [handler]

    install_redaction(logger)
    install_redaction(logger)
    filters = [item for item in handler.filters if isinstance(item, RedactFilter)]
    assert len(filters) == 1

    try:
        raise OperationalError(
            "INSERT INTO study_plans", {}, Exception("(3819) boom"), None
        )
    except OperationalError:
        import sys

        logger.exception("创建计划失败 password='hunter2'", exc_info=sys.exc_info())

    written = stream.getvalue()
    assert "hunter2" not in written
    assert "<redacted>" in written
    assert "创建计划失败" in written
