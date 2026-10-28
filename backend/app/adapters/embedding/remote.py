"""远端 Embedding Adapter（OpenAI 兼容 ``POST /v1/embeddings``）。

用途：接真实语义向量（如 Qwen3-Embedding-0.6B，1024 维），替代确定性 Hash Embedding。
确定性实现只用于可重复测试；真实检索质量必须由本 Adapter 提供（TBD-04 的落地形态）。

配置（进程环境变量优先，其次 ``backend/.env``，P1-5 起写进 ``.env`` 即生效）：
- ``CCA_EMBEDDING_PROVIDER=openai-compatible`` 切换到远端；默认 ``deterministic``
- ``CCA_EMBEDDING_BASE_URL`` 例如 ``http://127.0.0.1:8892/v1``（经 SSH 隧道的外网入口）
- ``CCA_EMBEDDING_MODEL`` 例如 ``Qwen3-Embedding-0.6B``（服务端不校验，但用于摘要与日志）
- ``CCA_EMBEDDING_API_KEY`` 服务不校验鉴权时可留空（发了也只用非空时才带 Authorization）
- ``CCA_EMBEDDING_DIM`` 向量维度（默认 1024；Qwen3 支持 Matryoshka 降维，传该参数给服务端）
- ``CCA_EMBEDDING_BATCH_SIZE`` 单次 HTTP 请求最多几条（默认 16；服务端上限 256）
- ``CCA_EMBEDDING_TIMEOUT_SECONDS`` 单次请求超时（默认 30）
- ``CCA_EMBEDDING_MAX_RETRIES`` 连接/5xx 的有界重试次数（默认 2）
- ``CCA_EMBEDDING_QUERY_PREFIX`` query 侧指令前缀（默认空串 = 行为不变）。

  Qwen3-Embedding 是 instruction-aware 模型：检索时 query 应带 ``Instruct: …\\nQuery: …``
  前缀，doc 侧不加。只作用于单条 ``embed()``（query 侧），``embed_batch()``（doc 侧）
  不受影响。默认空串保证不设变量时行为与旧版完全一致。
- ``CCA_EMBEDDING_VERIFY_BATCH`` 批量内容级自检（默认 0=关；入库任务建议开 1）。
  开启后每个 >=2 条的批次额外发 1 条单条请求，比对**最短那条**的批量向量与单条向量
  余弦，>0.999 才接受。理由：2026-10-28 服务端左填充、池化却按下标取
  时，条数/维度/范数三项校验**全部正常**，只有内容级比对能发现。

设计取舍：
- **异步**：调用发生在 async 的检索与入库任务里，网络往返不能阻塞事件循环；
- **有界重试**：只对超时/连接错误/5xx 重试；4xx 是配置或输入问题，立即失败；
- **维度校验**：返回维度与配置不一致直接 ``EmbeddingError``（宁可失败，也不写进不同源的向量库）；
- **归一化**：服务端已归一化，这里再做一次防御性归一（零向量才报错），保证余弦=点积。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import numpy as np

from app.adapters.embedding.deterministic import EmbeddingError
from app.config import env_flag, env_float, env_int, env_str

logger = logging.getLogger("cca.embedding.remote")

DEFAULT_DIM: int = 1024
DEFAULT_BATCH_SIZE: int = 16
# 服务端 MAX_INPUTS 上限：257 条以上返回 400，256 条整可以通过
MAX_INPUTS: int = 256
DEFAULT_TIMEOUT_SECONDS: float = 30.0
DEFAULT_MAX_RETRIES: int = 2
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def base_url() -> str:
    return env_str("CCA_EMBEDDING_BASE_URL", "").strip().rstrip("/")


def api_key() -> str:
    return env_str("CCA_EMBEDDING_API_KEY", "").strip()


def model_name() -> str:
    return env_str("CCA_EMBEDDING_MODEL", "").strip() or "Qwen3-Embedding-0.6B"


def query_prefix() -> str:
    """query 侧指令前缀（默认空串；doc 侧不使用）。"""
    return env_str("CCA_EMBEDDING_QUERY_PREFIX", "")


def embedding_dim() -> int:
    return max(8, min(env_int("CCA_EMBEDDING_DIM", DEFAULT_DIM), MAX_INPUTS * 8))


def batch_size() -> int:
    return max(1, min(env_int("CCA_EMBEDDING_BATCH_SIZE", DEFAULT_BATCH_SIZE), MAX_INPUTS))


# 批量 vs 单条的最小余弦：服务端两种路径在数学上应等价（fp16 差异 <1e-5）
VERIFY_MIN_COS: float = 0.999


def verify_batch_enabled() -> bool:
    """批量内容级自检开关（默认关；``CCA_EMBEDDING_VERIFY_BATCH=1`` 开启）。"""
    return env_flag("CCA_EMBEDDING_VERIFY_BATCH", False)


def timeout_seconds() -> float:
    return max(
        1.0, min(env_float("CCA_EMBEDDING_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS), 600.0)
    )


def max_retries() -> int:
    return max(0, min(env_int("CCA_EMBEDDING_MAX_RETRIES", DEFAULT_MAX_RETRIES), 5))


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
        verify_batch_: bool | None = None,
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
        self.verify_batch = (
            verify_batch_ if verify_batch_ is not None else verify_batch_enabled()
        )
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
        """单条 = query 侧：按 ``CCA_EMBEDDING_QUERY_PREFIX`` 加指令前缀（默认不加）。"""
        return (await self.embed_batch([f"{query_prefix()}{text}"]))[0]

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
            if self.verify_batch and len(batch) > 1:
                await self._verify_batch_alignment(batch, rows[-len(batch) :])
        return np.vstack(rows)

    async def _verify_batch_alignment(
        self, batch: list[str], vectors: list[np.ndarray]
    ) -> None:
        """内容级自检：批量里**最短那条**的向量必须与单条请求一致。

        只比最短的那条不是偷懒：服务端 2026-10-28 的缺陷（左填充却按右填充取池化下标）
        恰好让批内最长那条免于 padding 污染，其余全错——所以"最短 + 最长"里只能选最短。
        条数、维度、范数三项校验在那种缺陷下**全部通过**，只有这个判据有效。
        """
        index = min(range(len(batch)), key=lambda i: len(batch[i]))
        solo = await self._post([batch[index]])
        reference = self._normalize(np.asarray(solo[0], dtype=np.float32))
        similarity = float(np.dot(vectors[index], reference))
        if similarity <= VERIFY_MIN_COS:
            raise EmbeddingError(
                "Embedding 批量结果与单条不一致（疑似服务端批量错位/池化缺陷）："
                f"第 {index}/{len(batch)} 条余弦 {similarity:.4f} <= {VERIFY_MIN_COS}；"
                "可用 scripts/verify_embedding.py 复现（同一批量 vs 单条比对）"
            )

    def describe(self) -> dict:
        return {
            "provider": self.provider,
            "dim": self.dim,
            "production": True,
            "endpoint": self.endpoint,
            "batch_size": self.batch_size,
            "verify_batch": self.verify_batch,
        }


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_DIM",
    "MAX_INPUTS",
    "VERIFY_MIN_COS",
    "RemoteEmbedding",
    "batch_size",
    "base_url",
    "embedding_dim",
    "max_retries",
    "model_name",
    "query_prefix",
    "timeout_seconds",
    "verify_batch_enabled",
]
