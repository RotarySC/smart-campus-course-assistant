"""确定性 Embedding Provider（非生产 AI；TBD-04 未冻结时的可替换实现）。

SHA-256 派生特征 → 固定维度单位向量：同一文本永远得到同一向量，便于端到端可重复测试。
维度由 ``CCA_EMBEDDING_DIM`` 配置（默认 64）。生产替换为真实 EmbeddingGateway 实现。
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Final

import numpy as np

from app.config import env_int

PROVIDER_NAME: Final = "deterministic-sha256"
_DEFAULT_DIM: Final = 64
_TOKEN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+")
_CJK = re.compile(r"[\u4e00-\u9fff]+")


class EmbeddingError(Exception):
    """向量化失败（对外映射 EMBEDDING_FAILED，可有限重试）。"""


def embedding_dim() -> int:
    value = env_int("CCA_EMBEDDING_DIM", _DEFAULT_DIM)
    return max(8, min(value, 1024))


def tokens_of(text: str) -> list[str]:
    lowered = text.casefold()
    tokens: list[str] = []
    for match in _TOKEN.finditer(lowered):
        token = match.group(0)
        tokens.append(token)
        if _CJK.fullmatch(token or ""):
            # 中文补充 2-gram，避免单字特征过稀；纯 ASCII 词保持整词。
            tokens.extend(token[i : i + 2] for i in range(len(token) - 1))
    return tokens


def embed_text(text: str, dim: int | None = None) -> np.ndarray:
    dimension = dim or embedding_dim()
    if not text or not text.strip():
        raise EmbeddingError("空文本不能向量化")
    counts = Counter(tokens_of(text))
    vector = np.zeros(dimension, dtype=np.float64)
    for token, count in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % dimension
        sign = 1.0 if digest[8] & 1 else -1.0
        # 次线性词频饱和，避免重复词完全主导。
        vector[index] += sign * (1.0 + math.log(count))
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:  # pragma: no cover - tokens 非空时不会发生
        raise EmbeddingError("向量归一化失败")
    return (vector / norm).astype(np.float32)


class DeterministicEmbedding:
    """EmbeddingGateway 的本地确定性实现（标注：非生产模型）。"""

    provider = PROVIDER_NAME

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim or embedding_dim()

    async def embed(self, text: str) -> np.ndarray:
        return embed_text(text, self.dim)

    async def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack([embed_text(text, self.dim) for text in texts])

    def describe(self) -> dict:
        return {"provider": self.provider, "dim": self.dim, "production": False}


__all__ = [
    "PROVIDER_NAME",
    "DeterministicEmbedding",
    "EmbeddingError",
    "embed_text",
    "embedding_dim",
    "tokens_of",
]
