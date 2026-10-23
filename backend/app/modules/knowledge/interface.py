"""知识链路 Interface（Phase 1 冻结；Phase 2 只填本模块目录，不改公共文件）。

签名与后端详细设计 §2.2 对应：
- accept_batch(ctx, files, options) -> BatchView
- search(ctx, query) -> EvidenceSet
- mutate_document(ctx, command) -> TaskView
- get_citation / preview / list 等查询由 router 直接调用本模块 service。
"""

from __future__ import annotations

from typing import Any, Protocol

from app.shared.context import ActorContext


class KnowledgeInterface(Protocol):
    async def accept_batch(self, ctx: ActorContext, files: Any, options: Any) -> Any: ...

    async def get_batch(self, ctx: ActorContext, batch_id: str) -> Any: ...

    async def list_documents(self, ctx: ActorContext, query: Any) -> Any: ...

    async def preview_document(
        self, ctx: ActorContext, document_id: str, offset: int, limit: int
    ) -> Any: ...

    async def mutate_document(self, ctx: ActorContext, command: Any) -> Any: ...

    async def search(self, ctx: ActorContext, query: Any) -> Any: ...

    async def get_citation(self, ctx: ActorContext, reference_id: str) -> Any: ...


__all__ = ["KnowledgeInterface"]
