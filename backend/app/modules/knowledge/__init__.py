"""知识链路模块（Phase 2）：上传/Worker/发布/检索/引用/清理。

对外稳定入口（Phase 3 复用）：

- ``knowledge.search(ctx, SearchQuery(...)) -> EvidenceSet``
- ``knowledge.accept_batch / get_batch / list_documents / preview_document /
  mutate_document / get_citation``

确定性声明：Embedding 为 SHA-256 派生的本地确定性 Provider，VectorStore 为本地
JSON 适配器，均**非生产实现**（TBD-04 / TBD-07 未冻结，见 PHASE-02-REPORT）。
"""

from app.modules.knowledge.schemas import (
    BatchOptions,
    DocumentCommand,
    EvidenceChunk,
    EvidenceReference,
    EvidenceSet,
    ListDocumentsQuery,
    SearchQuery,
)
from app.modules.knowledge.service import KnowledgeService, knowledge

__all__ = [
    "BatchOptions",
    "DocumentCommand",
    "EvidenceChunk",
    "EvidenceReference",
    "EvidenceSet",
    "KnowledgeService",
    "ListDocumentsQuery",
    "SearchQuery",
    "knowledge",
]
