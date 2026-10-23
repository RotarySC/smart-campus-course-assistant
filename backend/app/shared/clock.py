"""可注入 Clock（设计 §4.1 / T02）。

- 存储层统一 UTC（``DATETIME(6)`` 无时区，写库前转 naive UTC）。
- 业务日期（今天/明天/下周一）按 ``Asia/Shanghai`` 解析，锚点为请求 accepted_at。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol
from datetime import tzinfo

from app.config import get_settings

UTC = timezone.utc


class Clock(Protocol):
    def now(self) -> datetime:
        """当前时刻（aware UTC）。"""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """冻结时间（测试 / 可复现用例）。"""

    def __init__(self, instant: datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FixedClock 需要带时区的时刻")
        self._instant = instant.astimezone(UTC)

    def now(self) -> datetime:
        return self._instant

    def advance(self, seconds: float) -> None:
        self._instant = self._instant + timedelta(seconds=seconds)


_clock: Clock = SystemClock()


def get_clock() -> Clock:
    return _clock


def set_clock(clock: Clock | None) -> None:
    """测试用：替换全局时钟。"""
    global _clock
    _clock = clock or SystemClock()


def reset_clock() -> None:
    set_clock(None)


def now_utc() -> datetime:
    """当前 aware UTC 时刻。"""
    return _clock.now().astimezone(UTC)


def school_tz() -> tzinfo:
    return get_settings().tz


def to_db(value: datetime) -> datetime:
    """aware/naive → 存储用 naive UTC。"""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def from_db(value: datetime | None) -> datetime | None:
    """存储 naive UTC → aware UTC。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def isoformat(value: datetime | None) -> str | None:
    """API 输出：带时区的 ISO 8601（UTC，``Z`` 后缀）。"""
    aware = from_db(value)
    if aware is None:
        return None
    return aware.isoformat().replace("+00:00", "Z")


def school_date(instant: datetime | None = None) -> date:
    """按学校时区取日期。"""
    moment = instant or now_utc()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(school_tz()).date()


def parse_business_date(raw: date) -> date:
    """业务日期为纯日期值，不做浏览器时区移动（DR-002）。"""
    return raw


def date_to_db(value: date) -> date:
    return value


def time_str(value: time) -> str:
    """分钟精度时间 → ``HH:mm``。"""
    return f"{value.hour:02d}:{value.minute:02d}"


def parse_time(raw: str) -> time:
    """``HH:mm`` → ``time``（秒恒为 0）。"""
    hour, minute = raw.split(":")
    return time(int(hour), int(minute), 0)
