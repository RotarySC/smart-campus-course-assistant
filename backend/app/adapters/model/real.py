"""真实模型供应商 Adapter 占位（TBD-04 未冻结）。

本阶段不接外部模型：没有凭据、供应商与数据出境约束未定。
保留 ``ModelGateway`` 形状的类与配置位，任何调用都以 ``MODEL_UNAVAILABLE`` 明确失败，
**不得**悄悄回退到确定性 Provider 上桌（避免把非生产行为冒充真实 AI）。

配置位全部来自 ``app.config.Settings`` 的 ``CCA_MODEL_*`` 键（见 ``backend/.env.example``）：

- ``provider``   ``CCA_MODEL_PROVIDER`` → 只有 ``openai-compatible`` 才会构造本类；
- ``endpoint``   ``CCA_MODEL_BASE_URL``，如 ``https://api.example.com/v1``；
- ``api_key``    ``CCA_MODEL_API_KEY``，只从环境变量 / ``.env`` 读取，不入库不落日志；
- ``model``      ``CCA_MODEL_NAME``，如 ``deepseek-chat``；
- ``temperature`` / ``max_tokens`` / ``timeout_seconds`` / ``max_retries`` 采样与重试参数。

实现 ``next_action`` / ``stream_answer`` 时需遵守（见 ``gateway.py`` 顶部不变量）：
模型上下文里没有身份字段、工具参数只能取白名单 schema、保存许可只能服务端签发。
"""

from __future__ import annotations

from typing import Any

from app.adapters.model.gateway import (
    Answer,
    EmitToken,
    ModelAction,
    ModelBudget,
    ModelContext,
)
from app.shared.errors import ApiError

DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 1


class RealProviderAdapter:
    """外部供应商适配位（TBD-04）。未实现前只做显式失败。"""

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.name = f"openai-compatible:{model or 'unset'}"

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.model)

    def describe(self) -> dict[str, Any]:
        """可安全外发的描述：只报密钥是否已配，不回显密钥原文。"""
        return {
            "provider": "openai-compatible",
            "name": self.name,
            "endpoint": self.endpoint or None,
            "model": self.model or None,
            "api_key_configured": bool(self.api_key),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "implemented": False,
        }

    async def next_action(self, context: ModelContext, budget: ModelBudget) -> ModelAction:
        raise ApiError("MODEL_UNAVAILABLE")

    async def stream_answer(self, answer: Answer, emit: EmitToken) -> None:
        raise ApiError("MODEL_UNAVAILABLE")


__all__ = ["RealProviderAdapter"]
