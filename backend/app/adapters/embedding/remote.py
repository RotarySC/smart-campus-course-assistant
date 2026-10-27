"""远端 Embedding Adapter（OpenAI 兼容 ``POST /v1/embeddings``）。

用途：接真实语义向量（如 Qwen3-Embedding-0.6B，1024 维），替代确定性 Hash Embedding。
确定性实现只用于可重复测试；真实检索质量必须由本 Adapter 提供（TBD-04 的落地形态）。

配置（环境变量，按 ``CCA_VECTOR_SPACE`` 同样走进程环境，便于 worker/API 各自读到）：
- ``CCA_EMBEDDING_PROVIDER=openai-compatible`` 切换到远端；默认 ``deterministic``
- ``CCA_EMBEDDING_BASE_URL`` 例如 ``http://127.0.0.1:8892/v1``（经 SSH 隧道的外网入口）
- ``CCA_EMBEDDING_MODEL`` 例如 ``Qwen3-Embedding-0.6B``（服务端不校验，但用于摘要与日志）
- ``CCA_EMBEDDING_API_KEY`` 服务不校验鉴权时可留空（发了也只用非空时才带 Authorization）
- ``CCA_EMBEDDING_DIM`` 向量维度（默认 1024；Qwen3 支持 Matryoshka 降维，传该参数给服务端）
- ``CCA_EMBEDDING_BATCH_SIZE`` 单次 HTTP 请求最多几条（默认 16；服务端上限 256）
- ``CCA_EMBEDDING_TIMEOUT_SECONDS`` 单次请求超时（默认 30）
- ``CCA_EMBEDDING_MAX_RETRIES`` 连接/5xx 的有界重试次数（默认 2）

设计取舍：
- **异步**：调用发生在 async 的检索与入库任务里，网络往返不能阻塞事件循环；
- **有界重试**：只对超时/连接错误/5xx 重试；4xx 是配置或输入问题，立即失败；
- **维度校验**：返回维度与配置不一致直接 ``EmbeddingError``（宁可失败，也不写进不同源的向量库）；
- **归一化**：服务端已归一化，这里再做一次防御性归一（零向量才报错），保证余弦=点积。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
import numpy as np

from app.adapters.embedding.deterministic import EmbeddingError

logger = logging.getLogger("cca.embedding.remote")

DEFAULT_DIM: int = 1024
DEFAULT_BATCH_SIZE: int = 16
# 服务端 MAX_INPUTS 上限（手册 §6：257 条以上 400，256 条整可以通过）
MAX_INPUTS: int = 256
DEFAULT_TIMEOUT_SECONDS: float = 30.0
DEFAULT_MAX_RETRIES: int = 2
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _env_int(name: str, default: int, *, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, "").strip() or default)
    except ValueError:
        value = default
    return max(low, min(value, high))


def base_url() -> str:
    return os.environ.get("CCA_EMBEDDING_BASE_URL", "").strip().rstrip("/")


def api_key() -> str:
    return os.environ.get("CCA_EMBEDDING_API_KEY", "").strip()


def model_name() -> str:
    return os.environ.get("CCA_EMBEDDING_MODEL", "").strip() or "Qwen3-Embedding-0.6B"


def embedding_dim() -> int:
    return _env_int("CCA_EMBEDDING_DIM", DEFAULT_DIM, low=8, high=MAX_INPUTS * 8)


def batch_size() -> int:
    return _env_int("CCA_EMBEDDING_BATCH_SIZE", DEFAULT_BATCH_SIZE, low=1, high=MAX_INPUTS)


def timeout_seconds() -> float:
    return max(1.0, min(_env_float("CCA_EMBEDDING_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS), 600.0))


def max_retries() -> int:
    return _env_int("CCA_EMBEDDING_MAX_RETRIES", DEFAULT_MAX_RETRIES, low=0, high=5)


class RemoteEmbedding:
    """OpenAI 兼容 Embedding（``POST {base_url}/embeddings``）。"""

    production = True

    def __init__(
        self,
        *,
        base_url_: str | None = None,
        model: str | None = None,
        api_key_: str | None = None,
        dim: int | None = None,
        batch_size_: int | None = None,
        timeout: float | None = None,
        retries: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = (base_url_ if base_url_ is not None else base_url()).rstrip("/")
        if not self._url:
            raise EmbeddingError(
                "CCA_EMBEDDING_PROVIDER=openai-compatible 时必须配置 CCA_EMBEDDING_BASE_URL"
            )
        if not self._url.startswith(("http://", "https://")):
            raise EmbeddingError("CCA_EMBEDDING_BASE_URL 必须以 http:// 或 https:// 开头")
        self.model = model or model_name()
        self._api_key = api_key_ if api_key_ is not None else api_key()
        self.dim = dim if dim is not None else embedding_dim()
        self.batch_size = batch_size_ if batch_size_ is not None else batch_size()
        self.timeout = timeout if timeout is not None else timeout_seconds()
        self.retries = retries if retries is not None else max_retries()
        self._transport = transport
        self.provider = f"openai-compatible:{self.model.lower()}"

    # ------------------------------------------------------------------ 内部
    @property
    def endpoint(self) -> str:
        return f"{self._url}/embeddings"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _post(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, Any] = {"input": texts, "model": self.model}
        if self.dim:
            payload["dimensions"] = self.dim
        delay = 0.2
        last_error: str = ""
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, transport=self._transport
                ) as client:
                    response = await client.post(
                        self.endpoint, json=payload, headers=self._headers()
                    )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt >= self.retries:
                    raise EmbeddingError(f"Embedding 服务不可达：{last_error}") from exc
                logger.warning(
                    "embedding 请求失败，第 %d/%d 次重试（%.1fs 后）：%s",
                    attempt + 1,
                    self.retries,
                    delay,
                    last_error,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 5.0)
                continue

            if response.status_code != 200:
                body = response.text[:300]
                if response.status_code in _RETRYABLE_STATUS and attempt < self.retries:
                    last_error = f"HTTP {response.status_code}: {body}"
                    logger.warning(
                        "embedding 服务返回 %d，第 %d/%d 次重试（%.1fs 后）",
                        response.status_code,
                        attempt + 1,
                        self.retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 5.0)
                    continue
                raise EmbeddingError(
                    f"Embedding 服务返回 HTTP {response.status_code}：{body}"
                )

            try:
                data = response.json()
            except ValueError as exc:  # noqa: TRY700 - 明确收敛为 EmbeddingError
                raise EmbeddingError("Embedding 服务返回非 JSON 响应") from exc
            entries = data.get("data")
            if not isinstance(entries, list) or len(entries) != len(texts):
                raise EmbeddingError(
                    f"Embedding 服务返回条数不符：期望 {len(texts)}，实际 "
                    f"{len(entries) if isinstance(entries, list) else '非数组'}"
                )
            ordered = sorted(entries, key=lambda item: int(item.get("index", 0)))
            return [list(item.get("embedding") or []) for item in ordered]
        raise EmbeddingError(f"Embedding 服务不可达：{last_error}")

    @staticmethod
    def _normalize(vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))
        if norm == 0.0:
            raise EmbeddingError("Embedding 返回零向量")
        return (vector / norm).astype(np.float32)

    # ------------------------------------------------------------------ 网关
    async def embed(self, text: str) -> np.ndarray:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        cleaned = ["" if text is None else str(text) for text in texts]
        if any(not text.strip() for text in cleaned):
            raise EmbeddingError("空文本不能向量化")

        rows: list[np.ndarray] = []
        for start in range(0, len(cleaned), self.batch_size):
            batch = cleaned[start : start + self.batch_size]
            vectors = await self._post(batch)
            matrix = np.asarray(vectors, dtype=np.float32)
            if matrix.ndim != 2 or matrix.shape[0] != len(batch):
                raise EmbeddingError("Embedding 返回形状不合法")
            if matrix.shape[1] != self.dim:
                raise EmbeddingError(
                    "Embedding 维度与配置不一致："
                    f"配置 {self.dim}，实际 {matrix.shape[1]}"
                    "（检查 CCA_EMBEDDING_DIM 与服务端 /health 的 dim）"
                )
            rows.extend(self._normalize(row) for row in matrix)
        return np.vstack(rows)

    def describe(self) -> dict:
        return {
            "provider": self.provider,
            "dim": self.dim,
            "production": True,
            "endpoint": self.endpoint,
            "batch_size": self.batch_size,
        }


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_DIM",
    "MAX_INPUTS",
    "RemoteEmbedding",
    "batch_size",
    "base_url",
    "embedding_dim",
    "max_retries",
    "model_name",
    "timeout_seconds",
]
