"""助手链路 Interface（Phase 1 冻结；Phase 3 只填本模块目录与自己的 adapters）。

- accept(ctx, ChatCommand) -> RunHandle
- cancel(ctx, request_id) -> RequestState
- status(ctx, request_id) -> ChatState
- stream：SSE 写出器在 Phase 3 实现（本阶段路由返回 501）。
"""

from __future__ import annotations

from typing import Any, Protocol

from app.shared.context import ActorContext


class AssistantInterface(Protocol):
    async def accept(self, ctx: ActorContext, command: Any) -> Any: ...

    async def cancel(self, ctx: ActorContext, request_id: str) -> Any: ...

    async def status(self, ctx: ActorContext, request_id: str) -> Any: ...


__all__ = ["AssistantInterface"]
