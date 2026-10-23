"""时区解析（环境兼容层）。

Windows 的 Python 3.12 默认不带 IANA 时区库（``tzdata`` 未安装，且本阶段不新增第三方依赖）。
``Asia/Shanghai`` 自 1991 年起无夏令时，等价于固定 UTC+08:00；因此用固定偏移实现，
保证业务日期解析正确。若配置其它时区且系统缺少 tzdata，则启动校验失败（不静默降级）。
"""

from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FIXED_OFFSETS: dict[str, timedelta] = {
    "Asia/Shanghai": timedelta(hours=8),
    "UTC": timedelta(0),
}


def resolve_timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        offset = FIXED_OFFSETS.get(name)
        if offset is None:
            raise ValueError(
                f"未知时区或系统缺少 tzdata: {name}（仅支持 {', '.join(FIXED_OFFSETS)} 的固定偏移回退）"
            ) from None
        return timezone(offset, name)
