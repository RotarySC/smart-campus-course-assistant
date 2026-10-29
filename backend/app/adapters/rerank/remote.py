"""远端 Reranker Adapter（局域网 GPU 机的 ``POST {BASE_URL}{PATH}``）。

服务端契约（不可更改，服务端由 Lead 实现）：

请求::

    {"query": str, "documents": [str, ...], "top_n": int | null, "return_documents": false}

响应 200::

    {"model": str,
     "results": [{"index": int, "relevance_score": float}, ...],
     "usage": {"prompt_tokens": int},
     "truncated": [bool, ...]}

- ``results`` 按 ``relevance_score`` 降序，**可能只含 top_n 条**；
- ``relevance_score`` 落在 ``[0,1]``，越高越相关；
- 服务端 503 = 模型未加载；408/5xx = 暂时不可用。

设计取舍（为什么这样做）：

- **对齐优先于省事**：``rerank()`` 一定返回与输入 ``documents`` 等长的列表，用响应的
  ``index`` 映射回输入顺序。未返回（被 top_n 截断或服务端省略）的文档记 ``0.0``——
  调用方拿到的仍是"一一对应"的分数，不必自己再补位；``0.0`` 也让"不提供依据"在
  阈值语义下自然落空，而不是被误当成相关。
- **截断在客户端做**：超长文档先在本地截到 ``CCA_RERANK_MAX_DOC_CHARS``，条数越过
  ``CCA_RERANK_MAX_DOCS`` 的文档直接不送、记 ``0.0``。这样 token 预算与服务端排队
  时间可控，也不会因为一次请求过大把整批精排拖垮。
- **只重试"暂时性"错误**：连接错误/超时/408/5xx 重试 1 次（退避后）；4xx 是请求或
  配置问题，立即失败。重试次数与超时由 ``CCA_RERANK_TIMEOUT_S`` 控制。
- **失败不静默**：任何不可用都抛 :class:`RerankUnavailable`。把故障伪装成"没命中"
  会误导下游（空结果与依赖故障必须分开），是否放行由调用方按
  ``CCA_RERANK_FAIL_OPEN`` 决定。
- **不发送 model 字段**：契约里请求体只有四个键；``CCA_RERANK_MODEL`` 只进日志与
  ``name``，避免与"服务端已加载模型"这一事实分叉。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Sequence

import httpx

from app.adapters.rerank import RerankUnavailable
from app.config import (
    rerank_base_url,
    rerank_max_doc_chars,
    rerank_max_docs,
    rerank_model,
    rerank_path,
    rerank_timeout_s,
)

logger = logging.getLogger("cca.rerank.remote")

DEFAULT_RETRIES: int = 1
# 连接错误与这些状态码视为"暂时不可用"：408/425/429 与 5xx（含 503 模型未加载）。
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_SCORE_MIN = 0.0
_SCORE_MAX = 1.0


def endpoint_path() -> str:
    """拼出端点路径；``BASE_URL`` 去尾斜杠、``PATH`` 补前导斜杠（配置侧已处理）。"""
    return f"{rerank_base_url()}{rerank_path()}"


class RemoteReranker:
    """跨编码器精排的远端实现（httpx.AsyncClient，可注入 transport 供测试）。"""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        path: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        retries: int = DEFAULT_RETRIES,
        max_doc_chars: int | None = None,
        max_docs: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        base = (base_url if base_url is not None else rerank_base_url()).strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise RerankUnavailable(
                "CCA_RERANK_BASE_URL 必须以 http:// 或 https:// 开头"
                f"（当前 {base or '空'}）"
            )
        path_value = path if path is not None else rerank_path()
        path_value = path_value.strip()
        if not path_value:
            raise RerankUnavailable("CCA_RERANK_PATH 不能为空")
        if not path_value.startswith("/"):
            path_value = f"/{path_value}"
        self._base_url = base
        self._path = path_value
        self.model = model or rerank_model()
        self.timeout = timeout if timeout is not None else rerank_timeout_s()
        self.retries = max(0, min(int(retries), 3))
        self.max_doc_chars = (
            max_doc_chars if max_doc_chars is not None else rerank_max_doc_chars()
        )
        self.max_docs = max_docs if max_docs is not None else rerank_max_docs()
        self._transport = transport
        self.name = f"remote:{self.model}"

    # ------------------------------------------------------------------ 内部
    @property
    def endpoint(self) -> str:
        return f"{self._base_url}{self._path}"

    def _payload(self, query: str, documents: list[str], top_n: int | None) -> dict[str, Any]:
        """按契约拼请求体：四个键，不夹带 model/其它字段。"""
        return {
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "return_documents": False,
        }

    def _trim(self, documents: list[str]) -> tuple[list[str], int]:
        """返回 (要发送的文档, 实际发送条数)；超长截断、超量截断（后者记 0.0）。"""
        trimmed = [text[: self.max_doc_chars] for text in documents[: self.max_docs]]
        if len(documents) > self.max_docs:
            logger.debug(
                "rerank 文档数 %d 超过上限 %d，其余按 0.0 处理",
                len(documents),
                self.max_docs,
            )
        return trimmed, len(trimmed)

    async def _post(self, query: str, documents: list[str], top_n: int | None) -> dict[str, Any]:
        """发一次（含重试）请求并返回响应 JSON；失败统一收敛为 RerankUnavailable。"""
        payload = self._payload(query, documents, top_n)
        delay = 0.2
        last_error = ""
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, transport=self._transport
                ) as client:
                    response = await client.post(self.endpoint, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt >= self.retries:
                    raise RerankUnavailable(f"精排服务不可达：{last_error}") from exc
                logger.warning(
                    "rerank 请求失败，第 %d/%d 次重试（%.1fs 后）：%s",
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
                        "rerank 服务返回 %d，第 %d/%d 次重试（%.1fs 后）",
                        response.status_code,
                        attempt + 1,
                        self.retries,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 5.0)
                    continue
                raise RerankUnavailable(
                    f"精排服务返回 HTTP {response.status_code}：{body}"
                )
            try:
                data = response.json()
            except ValueError as exc:  # noqa: TRY700 - 明确收敛为 RerankUnavailable
                raise RerankUnavailable("精排服务返回非 JSON 响应") from exc
            if not isinstance(data, dict):
                raise RerankUnavailable("精排服务返回结构不合法：顶层不是对象")
            return data
        raise RerankUnavailable(f"精排服务不可达：{last_error}")

    def _scores_from_results(
        self, data: dict[str, Any], total: int, sent: int
    ) -> list[float]:
        """把 ``results`` 映射回输入顺序；缺失/越界一律 0.0（不改变长度）。"""
        results = data.get("results")
        if not isinstance(results, list):
            raise RerankUnavailable("精排服务返回结构不合法：缺少 results 数组")
        scores = [0.0] * total
        for item in results:
            if not isinstance(item, dict):
                raise RerankUnavailable("精排服务返回结构不合法：results 项不是对象")
            try:
                index = int(item.get("index", -1))
            except (TypeError, ValueError) as exc:
                raise RerankUnavailable("精排服务返回结构不合法：index 不是整数") from exc
            try:
                score = float(item.get("relevance_score", 0.0))
            except (TypeError, ValueError) as exc:
                raise RerankUnavailable(
                    "精排服务返回结构不合法：relevance_score 不是数字"
                ) from exc
            if index < 0 or index >= sent:
                # 越界下标说明服务端契约被破坏：不猜、不静默吞掉，直接报错。
                raise RerankUnavailable(
                    f"精排服务返回越界 index={index}（本次发送 {sent} 条，总输入 {total} 条）"
                )
            scores[index] = max(_SCORE_MIN, min(score, _SCORE_MAX))
        return scores

    # ------------------------------------------------------------------ 网关
    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int | None = None,
    ) -> list[float]:
        """对 ``documents`` 打分，返回与输入等长、同序的 ``[0,1]`` 分数。"""
        cleaned = ["" if text is None else str(text) for text in documents]
        if not cleaned:
            return []
        trimmed, sent = self._trim(cleaned)
        if sent == 0:  # pragma: no cover - max_docs 被配置为 0 时才会发生
            return [0.0] * len(cleaned)
        data = await self._post(query, trimmed, top_n)
        return self._scores_from_results(data, len(cleaned), sent)

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "provider": "http-rerank",
            "endpoint": self.endpoint,
            "timeout_s": self.timeout,
            "retries": self.retries,
            "max_docs": self.max_docs,
            "max_doc_chars": self.max_doc_chars,
        }


__all__ = [
    "DEFAULT_RETRIES",
    "RemoteReranker",
    "endpoint_path",
]
