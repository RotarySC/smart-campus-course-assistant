"""模型适配层（Phase 3）。

- ``gateway``：``ModelGateway`` 契约与动作/上下文数据结构；
- ``deterministic``：默认的确定性 Provider（测试/演示，非生产）；
- ``real``：真实供应商 Adapter 占位（TBD-04 未冻结，未配置时返回 ``MODEL_UNAVAILABLE``）。
"""

from __future__ import annotations

from app.adapters.model.deterministic import DeterministicProvider
from app.adapters.model.gateway import (
    Answer,
    DraftIntent,
    EvidenceChunk,
    EvidenceReference,
    EvidenceSet,
    HistoryMessage,
    ModelAction,
    ModelBudget,
    ModelContext,
    ModelGateway,
    ToolCall,
    ToolExecutionRecord,
)
from app.adapters.model.real import RealProviderAdapter

__all__ = [
    "Answer",
    "DeterministicProvider",
    "DraftIntent",
    "EvidenceChunk",
    "EvidenceReference",
    "EvidenceSet",
    "HistoryMessage",
    "ModelAction",
    "ModelBudget",
    "ModelContext",
    "ModelGateway",
    "RealProviderAdapter",
    "ToolCall",
    "ToolExecutionRecord",
]
