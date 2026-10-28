"""远端 Embedding Adapter（OpenAI 兼容）单元测试。

全部用 ``httpx.MockTransport`` 在进程内伪造服务端，**不依赖外网/隧道**；
真实链路的内容级比对由 ``scripts/verify_embedding.py`` 负责（不是 pytest 的职责）。
"""

from __future__ import annotations

import hashlib
import json

import httpx
import numpy as np
import pytest

from app.adapters.embedding.deterministic import EmbeddingError
from app.adapters.embedding.remote import RemoteEmbedding

DIM = 8


def _vector(seed: str, dim: int = DIM) -> list[float]:
    """确定性伪随机向量（非归一化，交给 Adapter 归一化）。"""
    raw = hashlib.sha256(seed.encode("utf-8")).digest()
    values = [((raw[i % len(raw)] / 255.0) * 2 - 1) for i in range(dim)]
    return values


def _handler(requests: list[dict], *, status: int = 200, fail_first: int = 0):
    state = {"calls": 0}

    async def handle(request: httpx.Request) -> httpx.Response:
        state["calls"] += 1
        payload = json.loads(request.content)
        requests.append(payload)
        if state["calls"] <= fail_first:
            return httpx.Response(status, json={"error": "temporary"})
        data = [
            {"object": "embedding", "index": index, "embedding": _vector(text)}
            for index, text in enumerate(payload["input"])
        ]
        return httpx.Response(200, json={"object": "list", "data": data, "model": "m"})

    return handle


def _remote(**kwargs) -> RemoteEmbedding:
    defaults = dict(
        base_url_="http://127.0.0.1:8892/v1",
        model="Qwen3-Embedding-0.6B",
        api_key_="",
        dim=DIM,
        batch_size_=2,
        timeout=5.0,
        retries=0,
    )
    defaults.update(kwargs)
    return RemoteEmbedding(**defaults)


async def test_batches_requests_and_keeps_order_and_normalizes():
    requests: list[dict] = []
    transport = httpx.MockTransport(_handler(requests))
    embedding = _remote(transport=transport)

    texts = ["第一段", "第二段", "第三段", "第四段", "第五段"]
    matrix = await embedding.embed_batch(texts)

    assert matrix.shape == (5, DIM)
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-5)
    # batch_size=2 → 3 次请求，且每次 input 顺序不变
    assert [len(item["input"]) for item in requests] == [2, 2, 1]
    assert [item["input"][0] for item in requests] == ["第一段", "第三段", "第五段"]
    assert requests[0]["model"] == "Qwen3-Embedding-0.6B"
    assert requests[0]["dimensions"] == DIM


async def test_single_embed_uses_same_path():
    requests: list[dict] = []
    embedding = _remote(transport=httpx.MockTransport(_handler(requests)))
    vector = await embedding.embed("你好")
    assert vector.shape == (DIM,)
    assert requests[0]["input"] == ["你好"]


async def test_dimension_mismatch_fails_before_writing_vectors():
    async def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1] * (DIM + 3)}]},
        )

    embedding = _remote(transport=httpx.MockTransport(handle))
    with pytest.raises(EmbeddingError, match="维度与配置不一致"):
        await embedding.embed("x")


async def test_5xx_is_retried_then_succeeds():
    requests: list[dict] = []
    embedding = _remote(
        transport=httpx.MockTransport(_handler(requests, status=503, fail_first=1)),
        retries=1,
    )
    matrix = await embedding.embed_batch(["a", "b"])
    assert matrix.shape == (2, DIM)
    assert len(requests) == 2


async def test_4xx_is_not_retried():
    calls = {"n": 0}

    async def handle(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(422, json={"error": "bad input"})

    embedding = _remote(transport=httpx.MockTransport(handle), retries=3)
    with pytest.raises(EmbeddingError, match="HTTP 422"):
        await embedding.embed("x")
    assert calls["n"] == 1


async def test_transport_error_is_bounded():
    calls = {"n": 0}

    async def handle(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("tunnel down")

    embedding = _remote(transport=httpx.MockTransport(handle), retries=2)
    with pytest.raises(EmbeddingError, match="不可达"):
        await embedding.embed("x")
    assert calls["n"] == 3


async def test_count_mismatch_is_rejected():
    async def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    embedding = _remote(transport=httpx.MockTransport(handle))
    with pytest.raises(EmbeddingError, match="条数不符"):
        await embedding.embed_batch(["a", "b"])


async def test_empty_inputs():
    embedding = _remote(transport=httpx.MockTransport(_handler([])))
    empty = await embedding.embed_batch([])
    assert empty.shape == (0, DIM)
    with pytest.raises(EmbeddingError, match="空文本"):
        await embedding.embed_batch(["  "])


def test_missing_base_url_fails_fast(monkeypatch):
    monkeypatch.delenv("CCA_EMBEDDING_BASE_URL", raising=False)
    with pytest.raises(EmbeddingError, match="必须配置 CCA_EMBEDDING_BASE_URL"):
        RemoteEmbedding()


def test_registry_switches_provider_and_digest(monkeypatch):
    from app.adapters.embedding.registry import current_dim, provider_name
    from app.adapters.parser.document_parser import parser_config_digest

    monkeypatch.delenv("CCA_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("CCA_EMBEDDING_DIM", raising=False)
    deterministic_digest = parser_config_digest()
    assert provider_name() == "deterministic-sha256"
    assert current_dim() == 64

    monkeypatch.setenv("CCA_EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("CCA_EMBEDDING_MODEL", "Qwen3-Embedding-0.6B")
    monkeypatch.setenv("CCA_EMBEDDING_DIM", "1024")
    assert provider_name() == "openai-compatible:qwen3-embedding-0.6b"
    assert current_dim() == 1024
    assert parser_config_digest() != deterministic_digest


async def test_query_prefix_default_off_keeps_input_unchanged(monkeypatch):
    """默认不设 CCA_EMBEDDING_QUERY_PREFIX 时，query 输入与旧行为逐字相同。"""
    monkeypatch.delenv("CCA_EMBEDDING_QUERY_PREFIX", raising=False)
    requests: list[dict] = []
    embedding = _remote(transport=httpx.MockTransport(_handler(requests)))
    await embedding.embed("课程目标是什么？")
    assert requests[0]["input"] == ["课程目标是什么？"]


async def test_query_prefix_applies_only_to_single_embed_not_docs(monkeypatch):
    """A/AT-32：指令前缀只加在 query 侧（embed），doc 侧（embed_batch）不加。"""
    prefix = "Instruct: 给定校园课程问题，检索课程资料\nQuery: "
    monkeypatch.setenv("CCA_EMBEDDING_QUERY_PREFIX", prefix)
    requests: list[dict] = []
    embedding = _remote(transport=httpx.MockTransport(_handler(requests)))

    await embedding.embed("数据库默认隔离级别？")
    await embedding.embed_batch(["数据库默认可重复读。", "另一段资料。"])

    assert requests[0]["input"] == [prefix + "数据库默认隔离级别？"]
    assert requests[1]["input"] == ["数据库默认可重复读。", "另一段资料。"]


def test_query_prefix_helper_reads_env(monkeypatch):
    from app.adapters.embedding.remote import query_prefix

    monkeypatch.delenv("CCA_EMBEDDING_QUERY_PREFIX", raising=False)
    assert query_prefix() == ""
    monkeypatch.setenv("CCA_EMBEDDING_QUERY_PREFIX", "Instruct: x\nQuery: ")
    assert query_prefix() == "Instruct: x\nQuery: "


# ---------------------------------------------------------------------------
# 批量内容级自检（2026-10-28 服务端左填充池化缺陷的客户端防线）
# ---------------------------------------------------------------------------
def _misaligned_handler(requests: list[dict]):
    """模拟缺陷：除最长那条外，返回的是**别的文本**的向量（长度/范数/条数全正常）。"""

    async def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        texts = payload["input"]
        data = []
        for index, text in enumerate(texts):
            # 最短的那条被"污染"：返回批内最长那条的向量
            source = max(texts, key=len) if len(texts) > 1 and text != max(texts, key=len) else text
            data.append({"object": "embedding", "index": index, "embedding": _vector(source)})
        return httpx.Response(200, json={"object": "list", "data": data, "model": "m"})

    return handle


def test_verify_batch_defaults_off(monkeypatch):
    from app.adapters.embedding.remote import verify_batch_enabled

    monkeypatch.delenv("CCA_EMBEDDING_VERIFY_BATCH", raising=False)
    assert verify_batch_enabled() is False
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("CCA_EMBEDDING_VERIFY_BATCH", value)
        assert verify_batch_enabled() is True
    for value in ("0", "false", "off", ""):
        monkeypatch.setenv("CCA_EMBEDDING_VERIFY_BATCH", value)
        assert verify_batch_enabled() is False


async def test_verify_batch_off_by_default_adds_no_request():
    requests: list[dict] = []
    embedding = _remote(transport=httpx.MockTransport(_handler(requests)))
    await embedding.embed_batch(["第一段", "第二段"])
    assert [item["input"] for item in requests] == [["第一段", "第二段"]]


async def test_verify_batch_accepts_aligned_server():
    requests: list[dict] = []
    embedding = _remote(
        transport=httpx.MockTransport(_handler(requests)), verify_batch_=True
    )
    matrix = await embedding.embed_batch(["数据库默认隔离级别？是", "短"])
    assert matrix.shape == (2, DIM)
    # 校验请求 = 每个 >=2 条的批次额外 1 条单条请求，且比的是**最短**那条
    assert [item["input"] for item in requests] == [["数据库默认隔离级别？是", "短"], ["短"]]


async def test_verify_batch_rejects_misaligned_server():
    """缺陷重演：批内最短那条拿到别人的向量 → 必须在写库前失败。"""
    requests: list[dict] = []
    embedding = _remote(
        transport=httpx.MockTransport(_misaligned_handler(requests)), verify_batch_=True
    )
    with pytest.raises(EmbeddingError, match="批量结果与单条不一致"):
        await embedding.embed_batch(["短", "很长很长很长很长的一段课程资料"])


async def test_verify_batch_picks_shortest_not_longest():
    """只比最短那条：最长那条在历史缺陷下必然正确，比它等于没比。"""
    requests: list[dict] = []
    embedding = _remote(
        transport=httpx.MockTransport(_handler(requests)), verify_batch_=True
    )
    await embedding.embed_batch(["中等长度的文本", "长" * 40, "短"])
    assert requests[-1]["input"] == ["短"]
