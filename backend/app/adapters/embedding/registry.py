"""Embedding Adapter 装配：按 ``CCA_EMBEDDING_PROVIDER`` 选择确定性或远端实现。

为什么不放进 ``Settings``：这些键与 ``CCA_VECTOR_SPACE`` / ``CCA_RETRIEVAL_MIN_SCORE``
一样属于"进程级装配参数"，worker 与 API 各自读环境即可；``Settings`` 的缓存会让人误以为
改环境就能热切换。切换 Provider 会改变向量空间与 ``parser_config_digest``，
已发布的旧版本必须重建（这是刻意的：不同源的向量不能混用）。
"""

from __future__ import annotations

import os

from app.adapters.embedding import remote as remote_mod
from app.adapters.embedding.deterministic import (
    PROVIDER_NAME as DETERMINISTIC_PROVIDER,
)
from app.adapters.embedding.deterministic import (
    DeterministicEmbedding,
    embedding_dim as deterministic_dim,
)

REMOTE_KIND: str = "openai-compatible"
DETERMINISTIC_KIND: str = "deterministic"


def provider_kind() -> str:
    """``deterministic`` | ``openai-compatible``；写错按确定性处理并在日志提示。"""
    raw = os.environ.get("CCA_EMBEDDING_PROVIDER", "").strip().lower()
    if raw in ("", DETERMINISTIC_KIND):
        return DETERMINISTIC_KIND
    if raw in (REMOTE_KIND, "remote", "http", "openai"):
        return REMOTE_KIND
    return DETERMINISTIC_KIND


def is_remote() -> bool:
    return provider_kind() == REMOTE_KIND


def provider_name() -> str:
    """写进 ``parser_config_digest`` 的提供者标识（换实现即换摘要）。"""
    if is_remote():
        return f"{REMOTE_KIND}:{remote_mod.model_name().lower()}"
    return DETERMINISTIC_PROVIDER


def current_dim() -> int:
    if is_remote():
        return remote_mod.embedding_dim()
    return deterministic_dim()


def build_embedding():
    """构造当前配置下的 Embedding Gateway（异步接口：``embed`` / ``embed_batch``）。"""
    if is_remote():
        return remote_mod.RemoteEmbedding()
    return DeterministicEmbedding()


__all__ = [
    "DETERMINISTIC_KIND",
    "REMOTE_KIND",
    "build_embedding",
    "current_dim",
    "is_remote",
    "provider_kind",
    "provider_name",
]
