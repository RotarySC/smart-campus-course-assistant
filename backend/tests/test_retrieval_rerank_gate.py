"""精排门禁（rerank gate）裁决逻辑用例：只验行为，不联网、不依赖 GPU 服务。

被验对象是 ``KnowledgeService._decide`` 的两条路径（精排开启 / 精排关闭）：

- 精排开启：余弦硬门让位 → 余弦 top-N 送精排 → 按「精排分 + 余弦复核」两个信号裁决：
  ``>= HIGH`` 放行；``< 噪声底`` 判空；``[噪声底, LOW)`` 需要余弦替它作证，作证则由判官
  读正文决定、不作证才判空；中段 ``[LOW, HIGH)`` 里余弦没依据时直接放行（B01 实测：
  判官会随机否决弱证据）。精排不可用时按 ``CCA_RERANK_FAIL_OPEN`` 退回余弦路径或判空。
- 精排关闭：保持 2026-10-28 的「余弦硬门 + 判官带」行为。

全部用 Fake 替换装配点（``service.retrieval_reranker`` / ``service.retrieval_judge`` /
``service.rerank_thresholds`` / ``service.judge_band``），不启动真实精排/判官服务。
"""

from __future__ import annotations

import pytest

from _knowledge_helpers import (
    knowledge_storage,  # noqa: F401 - pytest fixture（隔离 filestore/vector 根）
    publish_batch,
    search_evidence,
    txt_bytes,
    unfreeze_corpus,  # noqa: F401 - pytest fixture（解除发布冻结）
)
from app.adapters.rerank import RerankUnavailable
from app.modules.knowledge import service as service_mod

LOW = 0.40
HIGH = 0.80

DOC_A = ("甲档资料.txt", "甲档案：数组与链表的基本操作。")
DOC_B = ("乙档资料.txt", "乙档案：树与图的遍历方式。")
DOC_C = ("丙档资料.txt", "丙档案：哈希表冲突处理。")


class FakeReranker:
    """按文档正文里的标记给分；记录调用次数与送进来的文本（证明门禁确实走到精排）。"""

    name = "fake"

    def __init__(self, scores: dict[str, float], *, error: Exception | None = None) -> None:
        self._scores = scores
        self._error = error
        self.calls = 0
        self.seen: list[list[str]] = []

    def _score(self, text: str) -> float:
        for marker, score in self._scores.items():
            if marker in text:
                return score
        return 0.0

    async def rerank(self, query: str, documents, top_n: int | None = None) -> list[float]:
        self.calls += 1
        self.seen.append(list(documents))
        if self._error is not None:
            raise self._error
        return [self._score(text) for text in documents]


class FakeJudge:
    """固定裁决的判官；记录调用次数（用于断言"该不该问判官"）。"""

    def __init__(self, verdict: bool | None) -> None:
        self._verdict = verdict
        self.calls = 0
        self.seen: list[str] = []

    async def decide(self, question: str, snippets: list[str]) -> bool | None:
        self.calls += 1
        self.seen = list(snippets)
        return self._verdict


def _install(
    monkeypatch,
    *,
    reranker,
    judge,
    thresholds: tuple[float, float] = (LOW, HIGH),
) -> None:
    """替换 service 模块里的装配点（实现未接入依赖注入，只能按导入名替换）。"""
    monkeypatch.setattr(service_mod, "retrieval_reranker", lambda: reranker)
    monkeypatch.setattr(service_mod, "retrieval_judge", lambda: judge)
    monkeypatch.setattr(service_mod, "rerank_thresholds", lambda: thresholds)
    monkeypatch.setattr(service_mod, "rerank_limit", lambda: 8)


def _force_legacy_judge_band(monkeypatch) -> None:
    """旧路径的判官带固定成 (0,1)，保证"中间带"必然轮到判官裁决。

    真实 ``judge_band()`` 默认 (0.45,0.58)；确定性 Embedding 的余弦常低于 0.45，
    不固定的话旧路径会直接判空、根本不调用判官，测不到"退回余弦路径并仍走判官"。
    """
    monkeypatch.setattr(service_mod, "judge_band", lambda: (0.0, 1.0))


def _force_cos_floor(monkeypatch, floor: float) -> None:
    """固定"余弦侧明确无依据"的下界（精排路径的余弦复核线）。

    下界取 ``judge_band()[0]``（与 legacy 路径同一常量），所以这里改 ``judge_band``
    就能控制"余弦这侧会不会替精排的低分作证"，无需真去凑余弦分数。
    """
    monkeypatch.setattr(service_mod, "judge_band", lambda: (floor, 1.0))


async def _seed_three_docs(client, seeded) -> None:
    await publish_batch(
        client,
        seeded["admin_headers"],
        [DOC_A, DOC_B, DOC_C],
    )


async def _search(seeded, question: str):
    return await search_evidence(seeded, question, top_k=5)


# --------------------------------------------------------------------------- #
# 1) 精排关闭 → 不调用精排，行为同旧路径
# --------------------------------------------------------------------------- #
async def test_rerank_disabled_never_calls_reranker(client, seeded, monkeypatch):
    await _seed_three_docs(client, seeded)
    fake_reranker = FakeReranker({"甲": 0.9})
    monkeypatch.setattr(service_mod, "retrieval_reranker", lambda: None)
    monkeypatch.setattr(service_mod, "retrieval_judge", lambda: None)
    monkeypatch.delenv("CCA_RETRIEVAL_MIN_SCORE", raising=False)

    evidence = await _search(seeded, "资料")

    assert evidence.status == "ok"
    assert evidence.chunks
    assert fake_reranker.calls == 0  # 精排完全没被碰


# --------------------------------------------------------------------------- #
# 2) 精排分低于噪声底，或低于 LOW 且余弦也说无依据 → 判空，且不调用判官
# --------------------------------------------------------------------------- #
async def test_top_below_low_returns_empty_without_judge(client, seeded, monkeypatch):
    await _seed_three_docs(client, seeded)
    fake_reranker = FakeReranker({"甲": 0.10, "乙": 0.20, "丙": 0.05})
    fake_judge = FakeJudge(True)
    _install(monkeypatch, reranker=fake_reranker, judge=fake_judge)
    # 余弦侧也"明确无依据"（下界拉到 0.999）→ 两个信号一致，不必问判官
    _force_cos_floor(monkeypatch, 0.999)

    evidence = await _search(seeded, "资料")

    assert evidence.status == "empty"
    assert evidence.chunks == [] and evidence.references == []
    assert evidence.corpus_empty is False  # 检索过但没命中，不是空库
    assert fake_reranker.calls == 1
    assert fake_judge.calls == 0  # 低分不该再花一次 LLM 调用


# --------------------------------------------------------------------------- #
# 3) 精排分 >= HIGH → 放行，且不调用判官
# --------------------------------------------------------------------------- #
async def test_top_at_or_above_high_returns_ok_without_judge(client, seeded, monkeypatch):
    await _seed_three_docs(client, seeded)
    fake_reranker = FakeReranker({"甲": 0.91, "乙": 0.10, "丙": 0.05})
    fake_judge = FakeJudge(False)  # 即使判官会否决，也不该被问
    _install(monkeypatch, reranker=fake_reranker, judge=fake_judge)

    evidence = await _search(seeded, "资料")

    assert evidence.status == "ok"
    assert evidence.chunks and evidence.references
    assert fake_judge.calls == 0


# --------------------------------------------------------------------------- #
# 4) 中间带 → 由判官裁决（False 判空 / True 放行）
# --------------------------------------------------------------------------- #
async def test_mid_band_judge_denies_then_allows(client, seeded, monkeypatch):
    await _seed_three_docs(client, seeded)
    fake_reranker = FakeReranker({"甲": 0.60, "乙": 0.30, "丙": 0.20})
    fake_judge = FakeJudge(False)
    _install(monkeypatch, reranker=fake_reranker, judge=fake_judge)

    denied = await _search(seeded, "资料")
    assert denied.status == "empty"
    assert denied.chunks == []
    assert fake_judge.calls == 1

    fake_judge_ok = FakeJudge(True)
    monkeypatch.setattr(service_mod, "retrieval_judge", lambda: fake_judge_ok)
    allowed = await _search(seeded, "资料")
    assert allowed.status == "ok"
    assert allowed.chunks
    assert fake_judge_ok.calls == 1


# --------------------------------------------------------------------------- #
# 5) 中间带 + 判官无法判断 → 按 CCA_RETRIEVAL_JUDGE_FAIL_OPEN
# --------------------------------------------------------------------------- #
async def test_mid_band_judge_unknown_honours_judge_fail_open(client, seeded, monkeypatch):
    await _seed_three_docs(client, seeded)
    fake_reranker = FakeReranker({"甲": 0.60})
    _install(monkeypatch, reranker=fake_reranker, judge=FakeJudge(None))

    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_FAIL_OPEN", "1")
    opened = await _search(seeded, "资料")
    assert opened.status == "ok"
    assert opened.chunks

    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_FAIL_OPEN", "0")
    closed = await _search(seeded, "资料")
    assert closed.status == "empty"
    assert closed.chunks == []


# --------------------------------------------------------------------------- #
# 6) 精排不可用 + FAIL_OPEN=1 → 退回余弦路径，仍然问判官
# --------------------------------------------------------------------------- #
async def test_rerank_unavailable_fail_open_falls_back_to_cosine_and_judge(
    client, seeded, monkeypatch
):
    await _seed_three_docs(client, seeded)
    fake_reranker = FakeReranker({}, error=RerankUnavailable("service down"))
    fake_judge = FakeJudge(True)
    _install(monkeypatch, reranker=fake_reranker, judge=fake_judge)
    _force_legacy_judge_band(monkeypatch)
    monkeypatch.setenv("CCA_RERANK_FAIL_OPEN", "1")
    monkeypatch.delenv("CCA_RETRIEVAL_MIN_SCORE", raising=False)

    evidence = await _search(seeded, "资料")

    assert evidence.status == "ok"
    assert evidence.chunks
    assert fake_reranker.calls == 1  # 尝试过精排
    assert fake_judge.calls == 1  # 退回余弦路径后判官仍生效


# --------------------------------------------------------------------------- #
# 7) 精排不可用 + FAIL_OPEN=0 → 直接判空，不带引用
# --------------------------------------------------------------------------- #
async def test_rerank_unavailable_strict_returns_empty(client, seeded, monkeypatch):
    await _seed_three_docs(client, seeded)
    fake_reranker = FakeReranker({}, error=RerankUnavailable("service down"))
    fake_judge = FakeJudge(True)  # 判官即便会放行也不该被问
    _install(monkeypatch, reranker=fake_reranker, judge=fake_judge)
    monkeypatch.setenv("CCA_RERANK_FAIL_OPEN", "0")

    evidence = await _search(seeded, "资料")

    assert evidence.status == "empty"
    assert evidence.chunks == [] and evidence.references == []
    assert fake_judge.calls == 0


# --------------------------------------------------------------------------- #
# 8) 精排开启时余弦硬门让位：低余弦候选仍能成为依据
# --------------------------------------------------------------------------- #
async def test_rerank_enabled_bypasses_cosine_hard_gate(client, seeded, monkeypatch):
    await _seed_three_docs(client, seeded)
    # 余弦硬门设到 0.99：旧路径下所有候选都会被挡掉
    monkeypatch.setenv("CCA_RETRIEVAL_MIN_SCORE", "0.99")

    # 对照：精排关闭 → 余弦门生效 → empty
    monkeypatch.setattr(service_mod, "retrieval_reranker", lambda: None)
    monkeypatch.setattr(service_mod, "retrieval_judge", lambda: None)
    legacy = await _search(seeded, "资料")
    assert legacy.status == "empty"

    # 精排开启 → 余弦门不生效，精排分 > HIGH 直接放行
    fake_reranker = FakeReranker({"甲": 0.95})
    _install(monkeypatch, reranker=fake_reranker, judge=FakeJudge(False))
    reranked = await _search(seeded, "资料")

    assert reranked.status == "ok"
    assert reranked.chunks
    assert fake_reranker.calls == 1


# --------------------------------------------------------------------------- #
# 9) 精排路径下 chunks / references 顺序 = 精排分降序
# --------------------------------------------------------------------------- #
async def test_rerank_path_orders_chunks_by_rerank_score(client, seeded, monkeypatch):
    await _seed_three_docs(client, seeded)
    # 甲的余弦可能最高，但精排认为 乙 > 丙 > 甲
    fake_reranker = FakeReranker({"甲": 0.10, "乙": 0.90, "丙": 0.50})
    _install(monkeypatch, reranker=fake_reranker, judge=FakeJudge(True))

    evidence = await _search(seeded, "资料")

    assert evidence.status == "ok"
    chunk_markers = [chunk.text[0] for chunk in evidence.chunks]
    assert chunk_markers[:3] == ["乙", "丙", "甲"]
    reference_markers = [reference.file_name[0] for reference in evidence.references]
    assert reference_markers == chunk_markers
    # 精排送进去的是"余弦 top-N 的正文"，顺序可以不同，但条数应与候选一致（<=8）
    assert 1 <= fake_reranker.calls == 1
    assert len(fake_reranker.seen[0]) == 3


# --------------------------------------------------------------------------- #
# 10) 精排低（>= 噪声底）+ 余弦有候选 → 判官复核，判 True 就放行（H-B09 形态）
# --------------------------------------------------------------------------- #
async def test_low_rerank_with_cosine_support_asks_judge(client, seeded, monkeypatch):
    await _seed_three_docs(client, seeded)
    # 精排把有答案的片段压到 0.04（实测 bge-reranker 对问句改写极敏感），余弦仍高于复核线
    fake_reranker = FakeReranker({"甲": 0.04, "乙": 0.01, "丙": 0.00})
    fake_judge = FakeJudge(True)
    _install(monkeypatch, reranker=fake_reranker, judge=fake_judge)
    _force_cos_floor(monkeypatch, 0.0)  # 余弦侧确认"有候选"

    evidence = await _search(seeded, "资料")

    assert evidence.status == "ok"
    assert evidence.chunks
    assert fake_judge.calls == 1  # 精排低分不再一票否决，必须让判官读正文
    assert "甲档案" in fake_judge.seen[0]


# --------------------------------------------------------------------------- #
# 11) 同一形态但判官否认 → 仍然判空（不是"低分一律放行"）
# --------------------------------------------------------------------------- #
async def test_low_rerank_with_cosine_support_still_denied_by_judge(
    client, seeded, monkeypatch
):
    await _seed_three_docs(client, seeded)
    fake_reranker = FakeReranker({"甲": 0.04, "乙": 0.01, "丙": 0.00})
    fake_judge = FakeJudge(False)
    _install(monkeypatch, reranker=fake_reranker, judge=fake_judge)
    _force_cos_floor(monkeypatch, 0.0)

    evidence = await _search(seeded, "资料")

    assert evidence.status == "empty"
    assert evidence.chunks == []
    assert fake_judge.calls == 1


# --------------------------------------------------------------------------- #
# 12) 精排分落在噪声底以下 → 直接判空，不问判官，也不放行
# --------------------------------------------------------------------------- #
async def test_rerank_below_noise_floor_returns_empty_without_judge(
    client, seeded, monkeypatch
):
    await _seed_three_docs(client, seeded)
    # 实测噪声底以下（无关片段 1e-4~1e-3）；余弦侧即便"有候选"也不该救
    fake_reranker = FakeReranker({"甲": 0.0004, "乙": 0.0002, "丙": 0.0001})
    fake_judge = FakeJudge(True)
    _install(monkeypatch, reranker=fake_reranker, judge=fake_judge)
    _force_cos_floor(monkeypatch, 0.0)

    evidence = await _search(seeded, "资料")

    assert evidence.status == "empty"
    assert evidence.chunks == []
    assert fake_judge.calls == 0


# --------------------------------------------------------------------------- #
# 13) 中段精排 + 余弦没到向量置信门 → 放行且不问判官（B01 实测：判官会随机否决）
# --------------------------------------------------------------------------- #
async def test_mid_band_without_cosine_support_passes_without_judge(
    client, seeded, monkeypatch
):
    await _seed_three_docs(client, seeded)
    # 余弦没到向量置信门（硬门 0.99；精排开启时该门只当"余弦够不够强"的尺子用）
    monkeypatch.setenv("CCA_RETRIEVAL_MIN_SCORE", "0.99")
    fake_reranker = FakeReranker({"甲": 0.60, "乙": 0.40, "丙": 0.30})
    fake_judge = FakeJudge(False)  # 判官若被问到会否决
    _install(monkeypatch, reranker=fake_reranker, judge=fake_judge)

    evidence = await _search(seeded, "资料")

    assert evidence.status == "ok"
    assert evidence.chunks
    assert fake_judge.calls == 0
