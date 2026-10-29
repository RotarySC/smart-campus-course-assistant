"""远端 Reranker Adapter / 确定性实现 / 配置键 单元测试。

全部用 ``httpx.MockTransport`` 在进程内伪造服务端，**不联网、不依赖 GPU 机**；
真实链路（LAN GPU 的 ``POST /rerank``）由运维脚本负责，不是 pytest 的职责。
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.adapters.rerank import (
    DeterministicReranker,
    RerankError,
    Reranker,
    RerankUnavailable,
    RemoteReranker,
    build_reranker,
)

DOCS = ["数据结构：线性表与树", "操作系统：进程调度", "数据库：B+ 树索引与回表"]


def _make_handler(
    requests: list[dict],
    *,
    results: list[dict] | None = None,
    status: int = 200,
    fail_first: int = 0,
):
    """按契约伪造 ``POST /rerank``：记录请求体，可注入失败次数/固定 results。"""
    state = {"calls": 0}

    async def handle(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        payload = json.loads(request.content)
        requests.append(payload)
        if state["calls"] <= fail_first:
            return httpx.Response(status, json={"error": "temporary"})
        if results is None:
            data = [
                {"index": index, "relevance_score": round(0.9 - 0.1 * index, 3)}
                for index in range(len(payload["documents"]))
            ]
        else:
            data = results
        return httpx.Response(
            200,
            json={
                "model": "bge-reranker-v2-m3",
                "results": data,
                "usage": {"prompt_tokens": 42},
                "truncated": [False] * len(data),
            },
        )

    return handle


def _remote(**kwargs) -> RemoteReranker:
    defaults = dict(
        base_url="http://127.0.0.1:8892",
        path="/rerank",
        model="bge-reranker-v2-m3",
        timeout=5.0,
        retries=0,
        max_doc_chars=1200,
        max_docs=32,
    )
    defaults.update(kwargs)
    transport = defaults.pop("transport", None)
    remote = RemoteReranker(**defaults, transport=transport)
    return remote


# --------------------------------------------------------------------------- #
# 远程实现：请求/响应契约、对齐、截断
# --------------------------------------------------------------------------- #
async def test_request_contract_and_aligned_scores():
    requests: list[dict] = []
    reranker = _remote(transport=httpx.MockTransport(_make_handler(requests)))

    scores = await reranker.rerank("索引 回表", DOCS, top_n=2)

    assert scores == [0.9, 0.8, 0.7]
    assert len(requests) == 1
    payload = requests[0]
    assert set(payload) == {"query", "documents", "top_n", "return_documents"}
    assert payload["query"] == "索引 回表"
    assert payload["documents"] == DOCS
    assert payload["top_n"] == 2
    assert payload["return_documents"] is False


async def test_index_shuffled_maps_back_to_input_order():
    """服务端按分数降序返回，index 乱序；输出必须回到输入顺序。"""
    requests: list[dict] = []
    results = [
        {"index": 2, "relevance_score": 0.91},
        {"index": 0, "relevance_score": 0.42},
        {"index": 1, "relevance_score": 0.13},
    ]
    reranker = _remote(
        transport=httpx.MockTransport(_make_handler(requests, results=results))
    )

    assert await reranker.rerank("q", DOCS) == [0.42, 0.13, 0.91]


async def test_only_top_n_returned_unreturned_docs_get_zero():
    requests: list[dict] = []
    results = [{"index": 1, "relevance_score": 0.88}]
    reranker = _remote(
        transport=httpx.MockTransport(_make_handler(requests, results=results))
    )

    scores = await reranker.rerank("q", DOCS, top_n=1)

    assert scores == [0.0, 0.88, 0.0]
    assert requests[0]["top_n"] == 1


async def test_scores_are_clamped_to_unit_interval():
    results = [
        {"index": 0, "relevance_score": 1.7},
        {"index": 1, "relevance_score": -0.2},
        {"index": 2, "relevance_score": 0.5},
    ]
    reranker = _remote(transport=httpx.MockTransport(_make_handler([], results=results)))

    assert await reranker.rerank("q", DOCS) == [1.0, 0.0, 0.5]


async def test_documents_truncated_by_chars():
    requests: list[dict] = []
    reranker = _remote(
        max_doc_chars=10,
        transport=httpx.MockTransport(_make_handler(requests)),
    )

    scores = await reranker.rerank("q", ["x" * 50, "y" * 3])

    assert requests[0]["documents"] == ["x" * 10, "y" * 3]
    assert len(scores) == 2


async def test_documents_truncated_by_count_and_rest_zeroed():
    requests: list[dict] = []
    reranker = _remote(
        max_docs=2,
        transport=httpx.MockTransport(_make_handler(requests)),
    )

    scores = await reranker.rerank("q", DOCS)

    assert len(requests[0]["documents"]) == 2  # 只送前 2 条
    assert len(scores) == len(DOCS)  # 输出仍与输入等长
    assert scores[2] == 0.0  # 未送服务端的文档给 0.0


async def test_empty_documents_short_circuits_without_request():
    requests: list[dict] = []
    reranker = _remote(transport=httpx.MockTransport(_make_handler(requests)))

    assert await reranker.rerank("q", []) == []
    assert requests == []


# --------------------------------------------------------------------------- #
# 远程实现：失败与重试（503 / 超时 / 4xx / 契约破坏）
# --------------------------------------------------------------------------- #
async def test_503_is_retried_then_succeeds():
    requests: list[dict] = []
    handler = _make_handler(requests, status=503, fail_first=1)
    reranker = _remote(retries=1, transport=httpx.MockTransport(handler))

    scores = await reranker.rerank("q", DOCS)

    assert len(requests) == 2  # 首次 503 + 重试成功
    assert len(scores) == len(DOCS)


async def test_503_exhausts_retry_and_raises():
    requests: list[dict] = []
    handler = _make_handler(requests, status=503, fail_first=2)
    reranker = _remote(retries=1, transport=httpx.MockTransport(handler))

    with pytest.raises(RerankUnavailable, match="HTTP 503"):
        await reranker.rerank("q", DOCS)
    assert len(requests) == 2


async def test_timeout_is_retried_then_raises():
    calls = {"n": 0}

    async def handle(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectTimeout("tunnel down")

    reranker = _remote(retries=1, transport=httpx.MockTransport(handle))

    with pytest.raises(RerankUnavailable, match="不可达"):
        await reranker.rerank("q", DOCS)
    assert calls["n"] == 2  # 重试 1 次


async def test_4xx_is_not_retried():
    calls = {"n": 0}

    async def handle(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": "bad request"})

    reranker = _remote(retries=1, transport=httpx.MockTransport(handle))

    with pytest.raises(RerankUnavailable, match="HTTP 400"):
        await reranker.rerank("q", DOCS)
    assert calls["n"] == 1


async def test_non_json_response_raises():
    async def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    reranker = _remote(transport=httpx.MockTransport(handle))

    with pytest.raises(RerankUnavailable, match="非 JSON"):
        await reranker.rerank("q", DOCS)


async def test_missing_results_raises():
    async def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "m"})

    reranker = _remote(transport=httpx.MockTransport(handle))

    with pytest.raises(RerankUnavailable, match="缺少 results"):
        await reranker.rerank("q", DOCS)


async def test_out_of_range_index_raises_instead_of_guessing():
    results = [{"index": 9, "relevance_score": 0.5}]
    reranker = _remote(transport=httpx.MockTransport(_make_handler([], results=results)))

    with pytest.raises(RerankUnavailable, match="越界 index=9"):
        await reranker.rerank("q", DOCS)


def test_invalid_base_url_fails_fast():
    with pytest.raises(RerankUnavailable, match="http:// 或 https://"):
        RemoteReranker(base_url="ftp://example.com")


def test_describe_reports_effective_settings():
    reranker = _remote()

    described = reranker.describe()

    assert described["endpoint"] == "http://127.0.0.1:8892/rerank"
    assert described["max_docs"] == 32
    assert described["max_doc_chars"] == 1200
    assert described["name"] == "remote:bge-reranker-v2-m3"


# --------------------------------------------------------------------------- #
# 确定性实现
# --------------------------------------------------------------------------- #
async def test_deterministic_is_stable_and_keyword_aligned():
    reranker = DeterministicReranker()
    query = "数据库 索引 回表"

    first = await reranker.rerank(query, DOCS)
    second = await reranker.rerank(query, DOCS)

    assert first == second
    assert len(first) == len(DOCS)
    assert all(0.0 <= score <= 1.0 for score in first)
    # 与查询词重叠最多的"数据库：B+ 树索引与回表"必须最高
    assert max(range(len(first)), key=lambda index: first[index]) == 2
    assert first[0] < first[2]


async def test_deterministic_top_n_zeroes_the_rest():
    reranker = DeterministicReranker()
    scores = await reranker.rerank("数据库 索引 回表", DOCS, top_n=1)

    assert scores[2] > 0.0
    assert scores[0] == 0.0 and scores[1] == 0.0


async def test_deterministic_empty_inputs():
    reranker = DeterministicReranker()

    assert await reranker.rerank("q", []) == []
    assert await reranker.rerank("", DOCS) == [0.0, 0.0, 0.0]
    assert reranker.name == "deterministic"


# --------------------------------------------------------------------------- #
# 工厂与配置键
# --------------------------------------------------------------------------- #
def test_build_reranker_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CCA_RERANK_ENABLED", raising=False)

    assert build_reranker() is None


def test_build_reranker_enabled_returns_remote(monkeypatch):
    monkeypatch.setenv("CCA_RERANK_ENABLED", "1")
    monkeypatch.setenv("CCA_RERANK_BASE_URL", "http://127.0.0.1:8892")
    monkeypatch.setenv("CCA_RERANK_PATH", "/rerank")
    monkeypatch.setenv("CCA_RERANK_MODEL", "bge-reranker-v2-m3")

    reranker = build_reranker()

    assert isinstance(reranker, RemoteReranker)
    assert isinstance(reranker, Reranker)  # Protocol 运行时可判定
    assert reranker.endpoint == "http://127.0.0.1:8892/rerank"
    assert reranker.name == "remote:bge-reranker-v2-m3"


def test_build_reranker_enabled_with_bad_url_raises(monkeypatch):
    monkeypatch.setenv("CCA_RERANK_ENABLED", "1")
    monkeypatch.setenv("CCA_RERANK_BASE_URL", "ftp://example.com")

    with pytest.raises(RerankUnavailable):
        build_reranker()


def test_rerank_config_defaults(monkeypatch):
    from app import config

    for key in (
        "CCA_RERANK_ENABLED",
        "CCA_RERANK_BASE_URL",
        "CCA_RERANK_PATH",
        "CCA_RERANK_MODEL",
        "CCA_RERANK_TIMEOUT_S",
        "CCA_RERANK_TOP_K",
        "CCA_RERANK_LOW",
        "CCA_RERANK_HIGH",
        "CCA_RERANK_NOISE_FLOOR",
        "CCA_RERANK_FAIL_OPEN",
        "CCA_RERANK_MAX_DOC_CHARS",
        "CCA_RERANK_MAX_DOCS",
        "CCA_RETRIEVAL_BUDGET_S",
        "CCA_RETRIEVAL_JUDGE_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    assert config.rerank_enabled() is False
    assert config.rerank_base_url() == "http://127.0.0.1:8892"
    assert config.rerank_path() == "/rerank"
    assert config.rerank_model() == "bge-reranker-v2-m3"
    # 8 s × (1+1 次重试) = 16 s ≤ 检索预算 18 s ≤ 内层调用预算 20 s
    assert config.rerank_timeout_s() == 8.0
    assert config.retrieval_budget_s() == 18.0
    assert config.judge_timeout_s() == 12.0
    assert config.rerank_timeout_s() * 2 <= config.retrieval_budget_s()
    assert config.retrieval_budget_s() < 20.0
    assert config.rerank_noise_floor() == 0.01
    assert config.rerank_top_k() == 8
    # 2026-10-29 用评测主集标定后的默认值（占位 0.5/0.5 已废弃）
    assert config.rerank_low() == 0.30
    assert config.rerank_high() == 0.90
    assert config.rerank_band() == (0.30, 0.90)
    assert config.rerank_fail_open() is True
    assert config.rerank_max_doc_chars() == 1200
    assert config.rerank_max_docs() == 32


def test_rerank_config_reads_env_and_clamps(monkeypatch):
    from app import config

    monkeypatch.setenv("CCA_RERANK_BASE_URL", "http://host:9000/")
    monkeypatch.setenv("CCA_RERANK_PATH", "rerank")
    monkeypatch.setenv("CCA_RERANK_TOP_K", "999")
    monkeypatch.setenv("CCA_RERANK_LOW", "0.8")
    monkeypatch.setenv("CCA_RERANK_HIGH", "0.2")
    monkeypatch.setenv("CCA_RERANK_FAIL_OPEN", "0")
    monkeypatch.setenv("CCA_RERANK_MAX_DOCS", "999")

    assert config.rerank_base_url() == "http://host:9000"
    assert config.rerank_path() == "/rerank"  # 补前导斜杠
    assert config.rerank_top_k() == 256  # 上限钳制
    assert config.rerank_band() == (0.8, 0.8)  # HIGH < LOW 时抬到 LOW
    assert config.rerank_fail_open() is False
    assert config.rerank_max_docs() == 256


# --------------------------------------------------------------------------- #
# fail-open 语义（配置层；调用方据此决定故障时放行还是判空）
# --------------------------------------------------------------------------- #
def test_fail_open_semantics(monkeypatch):
    from app import config

    monkeypatch.delenv("CCA_RERANK_FAIL_OPEN", raising=False)
    assert config.rerank_fail_open() is True  # 默认放行：故障不把"有答案"变"没找到"

    monkeypatch.setenv("CCA_RERANK_FAIL_OPEN", "0")
    assert config.rerank_fail_open() is False

    # 异常类型是同一个基类：调用方 catch RerankError 即可统一处理
    assert issubclass(RerankUnavailable, RerankError)
