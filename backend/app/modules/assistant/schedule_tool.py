"""``get_my_schedule`` 的服务侧实现（PHASE-03 A3）。

要求（设计 §9.3）：
- 身份固定为委派用户，**不接受** student_id 参数；
- 读取整个查询日期范围（不复用页面的默认 20 条后声称完整）；
- 日期只传一端视为单日，两端皆无视为今天（学校时区）。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from app.adapters.db.models import Course, Schedule
from app.adapters.db.uow import uow
from app.config import get_settings
from app.shared.clock import parse_business_date, school_date
from app.shared.context import ActorContext
from app.shared.errors import validation_error

MAX_SPAN_DAYS = 31


def resolve_range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    """单端视为单日；未传按今天；跨度 ≤31 天。"""
    if from_date is None and to_date is None:
        today = school_date()
        return today, today
    if from_date is None:
        assert to_date is not None
        return parse_business_date(to_date), parse_business_date(to_date)
    if to_date is None:
        return parse_business_date(from_date), parse_business_date(from_date)
    start = parse_business_date(from_date)
    end = parse_business_date(to_date)
    if end < start:
        raise validation_error(("to_date", "结束日期不能早于开始日期"))
    if (end - start).days > MAX_SPAN_DAYS:
        raise validation_error(("to_date", f"查询跨度不能超过 {MAX_SPAN_DAYS} 天"))
    return start, end


async def get_my_schedule(
    actor: ActorContext, from_date: date | None, to_date: date | None
) -> dict[str, Any]:
    start, end = resolve_range(from_date, to_date)
    # 完整范围查询：不分页、不截断（items 由 MCP 侧按模型预算另行处理）
    async with uow() as tx:
        result = await tx.session.execute(
            select(Schedule, Course.name)
            .join(Course, Course.id == Schedule.course_id)
            .where(
                Schedule.user_id == actor.user_id,
                Schedule.class_date >= start,
                Schedule.class_date <= end,
            )
            .order_by(Schedule.class_date, Schedule.start_time, Schedule.id)
        )
        rows = list(result.all())

    from app.modules.academics.schemas import schedule_view

    items = [schedule_view(schedule, course_name) for schedule, course_name in rows]
    return {
        "status": "ok" if items else "empty",
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "school_timezone": get_settings().school_timezone,
        "items": items,
    }


__all__ = ["MAX_SPAN_DAYS", "get_my_schedule", "resolve_range"]
