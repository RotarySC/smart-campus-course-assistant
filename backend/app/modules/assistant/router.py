"""公共助手端点（``/api/v1/chat/*``；PHASE-03 A7）。

- ``POST /chat/stream``：接受事务成功后才建立 SSE（认证/参数/冲突/容量错误在流之前以普通
  HTTP 错误返回）；runner 在独立任务中执行，连接断开不影响收尾。
- ``GET /chat/requests/{request_id}``：返回本人执行元数据（不含正文）。
- ``POST /chat/requests/{request_id}/cancel``：幂等提出停止；终态后返回当前状态。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Path, Request
from starlette.responses import StreamingResponse

from app.modules.assistant.accept import (
    accept_request,
    cancel_request,
    get_request_state,
)
from app.modules.assistant.contracts import CancelOutput, ChatInput, ChatState
from app.modules.assistant.runtime import get_runtime
from app.modules.assistant.sse import iter_sse
from app.modules.identity.interface import get_actor
from app.shared.api_models import ERROR_RESPONSES, Envelope
from app.shared.context import ActorContext
from app.shared.http import envelope, request_id_of

logger = logging.getLogger("cca.assistant.router")

router = APIRouter(tags=["assistant"])

ID_PATH = Path(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/chat/stream", operation_id="streamChat", responses=ERROR_RESPONSES)
async def stream_chat(
    request: Request,
    body: ChatInput,
    actor: ActorContext = Depends(get_actor),
):
    runtime = get_runtime()
    await runtime.ensure_recovered()
    accepted = await accept_request(
        actor, body, request_trace_id=request_id_of(request)
    )
    channel = runtime.start(actor, accepted)
    return StreamingResponse(
        iter_sse(channel),
        media_type="text/event-stream",
        headers=dict(SSE_HEADERS, **{"X-Request-Id": request_id_of(request)}),
    )


@router.get(
    "/chat/requests/{request_id}",
    operation_id="getChatState",
    responses=ERROR_RESPONSES,
    response_model=Envelope[ChatState],
)
async def get_chat_state(
    request: Request,
    request_id: str = ID_PATH,
    actor: ActorContext = Depends(get_actor),
):
    state = await get_request_state(actor, request_id)
    return envelope(request, state.model_dump(mode="json", exclude_none=True))


@router.post(
    "/chat/requests/{request_id}/cancel",
    operation_id="cancelChat",
    responses=ERROR_RESPONSES,
    response_model=Envelope[CancelOutput],
)
async def cancel_chat(
    request: Request,
    request_id: str = ID_PATH,
    actor: ActorContext = Depends(get_actor),
):
    accepted, state = await cancel_request(actor, request_id)
    output = CancelOutput(accepted=accepted, request=state)
    return envelope(request, output.model_dump(mode="json", exclude_none=True))


__all__ = ["router"]
