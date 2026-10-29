"""检索精排（Reranker）Adapter 包。

跨编码器精排：给定「问题 + 候选文档」，用一次模型调用重新打分，弥补向量检索
"主题相近但答非所问"的缺陷。本层**不接入** ``knowledge/service.py``——由检索侧
在阈值标定后按 ``CCA_RERANK_ENABLED`` 决定是否调用。

两种实现：
- ``remote``：局域网 GPU 机的 ``POST {CCA_RERANK_BASE_URL}{CCA_RERANK_PATH}``
  （如 bge-reranker-v2-m3），真实精排；
- ``deterministic``：查询词与文档的词重叠率，稳定可复现，只用于测试/离线。

分数约定（两个实现一致，调用方可以放心使用）：
- 返回值**与输入 ``documents`` 等长、下标一一对齐**；
- 分数落在 ``[0, 1]``，越高越相关；未进入 ``top_n`` 或未被服务端返回的文档给 ``0.0``
  （可以理解为"不提供依据"），而**不是**让列表变短——调用方不需要再做下标映射；
- 失败抛 :class:`RerankUnavailable`，不静默返回空列表：静默空会让"精排故障"
  看起来像"检索没命中"，是两件不同的事。

配置见 ``backend/.env.example`` 的「检索精排 Reranker」分组；默认关闭。
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from app.config import rerank_enabled


class RerankError(Exception):
    """精排层错误基类（配置错误/契约不符都收敛到这里）。"""


class RerankUnavailable(RerankError):
    """精排服务不可用或返回不可用（连接/超时/5xx/契约不符）。

    调用方应结合 ``CCA_RERANK_FAIL_OPEN`` 决定：放行（保留检索分数）或判空。
    """


@runtime_checkable
class Reranker(Protocol):
    """精排器协议：``rerank`` 返回与 ``documents`` 等长、同序的分数。"""

    name: str

    async def rerank(
        self,
        query: str,
        documents: Sequence[str],
        top_n: int | None = None,
    ) -> list[float]:
        ...


def build_reranker() -> Reranker | None:
    """按 ``CCA_RERANK_ENABLED`` 装配精排器；关闭时返回 None（调用方完全跳过）。

    关闭是默认值，也是"行为与未引入精排时一致"的保证。开启但地址非法/缺依赖时
    直接抛 :class:`RerankUnavailable`，不做静默降级（由调用方按 fail-open 处理）。
    """
    if not rerank_enabled():
        return None
    from app.adapters.rerank.remote import RemoteReranker

    return RemoteReranker()


# 具体实现放在异常/协议定义之后导入：remote 需要 ``from app.adapters.rerank import
# RerankUnavailable``，先定义再导入可避免循环导入时拿到半初始化模块。
from app.adapters.rerank.deterministic import DeterministicReranker  # noqa: E402
from app.adapters.rerank.remote import RemoteReranker  # noqa: E402

__all__ = [
    "DeterministicReranker",
    "RemoteReranker",
    "RerankError",
    "RerankUnavailable",
    "Reranker",
    "build_reranker",
]
