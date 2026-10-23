"""内部 API 路由桩（/internal/v1）：Phase 3 实现，本阶段返回 501。

路由在 Phase 1 冻结；P3 只改本文件与 assistant 模块，不改 entrypoints/internal_api.py。
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.shared.http import not_implemented

router = APIRouter(tags=["internal"])

PHASE = "Phase 3（内部委派与工具）"


@router.post("/delegations/exchange", operation_id="exchangeDelegation")
async def exchange_delegation(request: Request):
    return not_implemented(request, f"委派兑换（{PHASE}）")


@router.post("/tools/get-my-schedule", operation_id="internalSchedule")
async def internal_schedule(request: Request):
    return not_implemented(request, f"课表工具（{PHASE}）")


@router.post("/tools/search-course-docs", operation_id="internalSearch")
async def internal_search(request: Request):
    return not_implemented(request, f"检索工具（{PHASE}）")


@router.post("/tools/save-study-plan", operation_id="internalSave")
async def internal_save(request: Request):
    return not_implemented(request, f"保存工具（{PHASE}）")
