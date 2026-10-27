"""Embedding Adapter 包。

两种实现：
- ``deterministic``：SHA-256 派生特征，可重复、离线；测试与非生产默认；
- ``openai-compatible``：远端真实语义向量（如 Qwen3-Embedding-0.6B，1024 维），
  经 ``POST /v1/embeddings`` 调用；用 ``CCA_EMBEDDING_*`` 配置。

用 ``build_embedding()`` 取当前配置下的实现；``provider_name()/current_dim()``
供 ``parser_config_digest`` 使用（换实现即换冻结参数）。
"""

from app.adapters.embedding.deterministic import (
    PROVIDER_NAME,
    DeterministicEmbedding,
    EmbeddingError,
    embed_text,
    embedding_dim,
)
from app.adapters.embedding.registry import (
    build_embedding,
    current_dim,
    is_remote,
    provider_kind,
    provider_name,
)
from app.adapters.embedding.remote import RemoteEmbedding

__all__ = [
    "PROVIDER_NAME",
    "DeterministicEmbedding",
    "EmbeddingError",
    "RemoteEmbedding",
    "build_embedding",
    "current_dim",
    "embed_text",
    "embedding_dim",
    "is_remote",
    "provider_kind",
    "provider_name",
]
