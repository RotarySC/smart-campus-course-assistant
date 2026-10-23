"""真实模型供应商 Adapter 占位（TBD-04 未冻结）。

本阶段不接外部模型：没有凭据、供应商与数据出境约束未定。
保留 ``ModelGateway`` 形状的类与配置位，任何调用都以 ``MODEL_UNAVAILABLE`` 明确失败，
**不得**悄悄回退到确定性 Provider 上桌（避免把非生产行为冒充真实 AI）。
"""

from __future__ import annotations

from app.adapters.model.gateway import (
    Answer,
    EmitToken,
    ModelAction,
    ModelBudget,
    ModelContext,
)
from app.shared.errors import ApiError


class RealProviderAdapter:
    """外部供应商适配位（TBD-04）。未实现前只做显式失败。"""

    name = "real-unconfigured"

    def __init__(self, *, endpoint: str | None = None, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.api_key)

    async def next_action(self, context: ModelContext, budget: ModelBudget) -> ModelAction:
        raise ApiError("MODEL_UNAVAILABLE")

    async def stream_answer(self, answer: Answer, emit: EmitToken) -> None:
        raise ApiError("MODEL_UNAVAILABLE")


__all__ = ["RealProviderAdapter"]
