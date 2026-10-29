"""确定性 Reranker（测试/离线用；非生产精排能力）。

为什么需要它：精排层的接入代码（阈值标定、fail-open、top_n 语义）必须能在**没有 GPU
服务**的环境里可复现地跑通。这里用"查询词与文档的词重叠率"给出一个稳定分数：

- 分词复用 ``app.adapters.embedding.deterministic.tokens_of``（中文按 2-gram、英文按整词、
  casefold），因此与确定性 Embedding 用同一套词表，不额外引入分词依赖；
- 分数 = ``|查询词集合 ∩ 文档词集合| / |查询词集合|``，落在 ``[0,1]``：文档覆盖的查询词
  越全分越高，与词序、出现次数无关（稳定、可复现，适合断言）；
- ``top_n`` 语义与远端一致：只保留分数最高的 ``top_n`` 条，其余记 ``0.0``（并列时按输入
  下标稳定排序）；
- **不做截断**：截断是为了控制服务端 token 预算，本地实现没有这个成本，截断只会让
  分数变得依赖配置（``CCA_RERANK_MAX_DOC_CHARS``），不利于测试复现。

本实现**不是**语义精排：同义改写（"打分规则" vs "成绩构成"）会得 0 分。生产必须用
``remote`` 实现；默认关闭时检索链路根本不会调用到这里。
"""

from __future__ import annotations

from typing import Sequence

from app.adapters.embedding.deterministic import tokens_of
from app.adapters.rerank._text import normalize_documents


class DeterministicReranker:
    """按词重叠率打分的确定性精排器（``name="deterministic"``）。"""

    name = "deterministic"

    @staticmethod
    def _score(query_tokens: set[str], document: str) -> float:
        if not query_tokens:
            return 0.0
        document_tokens = set(tokens_of(document))
        if not document_tokens:
            return 0.0
        return len(query_tokens & document_tokens) / len(query_tokens)

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int | None = None,
    ) -> list[float]:
        """返回与 ``documents`` 等长、同序的 ``[0,1]`` 分数。"""
        cleaned = normalize_documents(documents)
        if not cleaned:
            return []
        query_tokens = set(tokens_of(query or ""))
        scores = [self._score(query_tokens, text) for text in cleaned]

        limit = top_n
        if limit is not None:
            limit = max(0, min(int(limit), len(scores)))
            # 并列时按下标稳定排序：同一输入永远得到同一结果，便于断言。
            keep = {
                index
                for index, _score in sorted(
                    enumerate(scores), key=lambda item: (-item[1], item[0])
                )[:limit]
            }
            scores = [score if index in keep else 0.0 for index, score in enumerate(scores)]
        return scores


__all__ = ["DeterministicReranker"]
