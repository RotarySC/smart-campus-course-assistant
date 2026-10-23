"""助手链路路由桩：chat 三端点返回 501 统一错误信封（Phase 3 实现）。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.shared.api_models import ERROR_RESPONSES
from app.shared.http import not_implemented

router = APIRouter(tags=["assistant"])

PHASE = "Phase 3（助手执行链路）"


@router.post("/chat/stream", operation_id="streamChat", responses=ERROR_RESPONSES)
async def stream_chat(request: Request):
    return not_implemented(request, f"对话流式接口（{PHASE}）")


@router.get("/chat/requests/{request_id}", operation_id="getChatState", responses=ERROR_RESPONSES)
async def get_chat_state(request: Request, request_id: str):
    return not_implemented(request, f"对话状态查询（{PHASE}）")


@router.post("/chat/requests/{request_id}/cancel", operation_id="cancelChat", responses=ERROR_RESPONSES)
async def cancel_chat(request: Request, request_id: str):
    return not_implemented(request, f"对话取消（{PHASE}）")
