"""精排包内的共享小工具（两个实现都用，避免同一段归一化各写一遍）。"""

from __future__ import annotations

from typing import Sequence


def normalize_documents(documents: Sequence[object]) -> list[str]:
    """把任意外部输入归一成 ``list[str]``（``None`` → 空串，其余 ``str()``）。

    为什么统一在这里：远端实现要按字符数截断、本地实现要分词，两者都需要
    "``documents`` 里不会有 None/非字符串"这一前提；各写一份就会出现一处改了、
    另一处忘改的不一致（分数下标对齐是契约的核心，不能靠运气）。
    """
    return ["" if text is None else str(text) for text in documents]


__all__ = ["normalize_documents"]
