"""运维面路由：运行统计查询（FR-OPS-002 / NFR-OBS-001）。

只读聚合，不写库；窗口按学校时区自然日，默认最近 7 天，上限 31 天。
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import Depends, Query, Request

from app.modules.identity.interface import get_admin
from app.modules.operations import stats
from app.shared.api_models import ERROR_RESPONSES, Envelope, StatsOverview
from app.shared.clock import school_date
from app.shared.context import ActorContext
from app.shared.errors import validation_error
from app.shared.http import envelope, strict_router

router = strict_router()


@router.get(
    "/admin/stats/overview",
    operation_id="getStatsOverview",
    response_model=Envelope[StatsOverview],
    responses=ERROR_RESPONSES,
)
async def stats_overview(
    request: Request,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    actor: ActorContext = Depends(get_admin),
):
    """回答终止、工具、计划、批次与草稿/引用计数（管理员）。"""
    end = to_date or school_date()
    start = from_date or (end - timedelta(days=6))
    if start > end:
        raise validation_error(("from_date", "起始日期不能晚于结束日期"))
    if (end - start).days + 1 > stats.MAX_WINDOW_DAYS:
        raise validation_error(
            ("from_date", f"查询跨度不能超过 {stats.MAX_WINDOW_DAYS} 天")
        )
    data = await stats.overview(from_date=start, to_date=end)
    return envelope(request, data)


__all__ = ["router"]
