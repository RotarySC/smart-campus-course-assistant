"""模型 Provider 装配（TBD-04 骨架）。

按 ``CCA_MODEL_PROVIDER`` 选择 Provider：

- ``deterministic``（默认）：``DeterministicProvider`` —— 关键词规则，可复现，
  **非生产 AI 能力**；
- ``openai-compatible``：``RealProviderAdapter`` —— 兼容 chat/completions 的供应商
  适配位，真实的网络调用尚未实现，任何请求都以 ``MODEL_UNAVAILABLE``（503）显式失败。

刻意**不做**静默回退：一旦配置了真实供应商，就绝不会悄悄落到确定性 Provider 上，
否则规则匹配的行为会被当成大模型能力对外呈现（设计 TBD-04 / ``real.py`` 注释同此约定）。
"""

from __future__ import annotations

from app.adapters.model.deterministic import DeterministicProvider
from app.adapters.model.gateway import ModelGateway
from app.adapters.model.real import RealProviderAdapter
from app.config import Settings, get_settings


def build_model_provider(settings: Settings | None = None) -> ModelGateway:
    """按配置装配 Provider（默认确定性；配置错误由 ``Settings`` 校验拦在启动期）。"""
    cfg = settings or get_settings()
    if cfg.model_provider == "deterministic":
        return DeterministicProvider()
    return RealProviderAdapter(
        endpoint=cfg.model_base_url,
        api_key=cfg.model_api_key,
        model=cfg.model_name,
        temperature=cfg.model_temperature,
        max_tokens=cfg.model_max_tokens,
        timeout_seconds=cfg.model_timeout_seconds,
        max_retries=cfg.model_max_retries,
    )


__all__ = ["build_model_provider"]
