"""检索充分性判官（LLM）单元测试。

用 ``httpx.MockTransport`` 在进程内伪造 chat/completions，不依赖外网。
真实判官的语义质量由 ``verification/evidence/at32-retrieval/judge_calibration.py``
在 30 条标定 query 上验证（不是 pytest 的职责）。
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.adapters.judge import (
    RetrievalJudge,
    build_judge,
    judge_band,
    judge_enabled,
    judge_fail_open,
    parse_verdict,
)


def _completion(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def _handler(requests: list[dict], *, content: str = "ANSWERABLE", status: int = 200):
    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if status != 200:
            return httpx.Response(status, json={"error": "boom"})
        return httpx.Response(200, json=_completion(content))

    return handle


def _judge(transport, **kwargs) -> RetrievalJudge:
    defaults = dict(
        endpoint="http://127.0.0.1:9999/v1",
        api_key="k",
        model="judge-model",
        timeout_seconds=2.0,
        max_tokens=64,
    )
    defaults.update(kwargs)
    return RetrievalJudge(transport=transport, **defaults)


# ---------------------------------------------------------------- 配置读取
def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CCA_RETRIEVAL_JUDGE", raising=False)
    assert judge_enabled() is False
    assert build_judge() is None  # 关闭时完全不装配，检索路径零开销


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_enabled_flags(monkeypatch, value):
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE", value)
    assert judge_enabled() is True
    assert build_judge() is not None


def test_fail_open_defaults_true(monkeypatch):
    monkeypatch.delenv("CCA_RETRIEVAL_JUDGE_FAIL_OPEN", raising=False)
    assert judge_fail_open() is True
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_FAIL_OPEN", "0")
    assert judge_fail_open() is False


def test_band_defaults_and_clamping(monkeypatch):
    monkeypatch.delenv("CCA_RETRIEVAL_JUDGE_LOW", raising=False)
    monkeypatch.delenv("CCA_RETRIEVAL_JUDGE_HIGH", raising=False)
    assert judge_band() == (0.45, 0.58)
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_LOW", "0.5")
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_HIGH", "0.7")
    assert judge_band() == (0.5, 0.7)
    # 配反了不允许整段检索随机变空：退化成"没有中间带"
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_LOW", "0.8")
    monkeypatch.setenv("CCA_RETRIEVAL_JUDGE_HIGH", "0.3")
    low, high = judge_band()
    assert low == high == 0.8


# ---------------------------------------------------------------- 响应解析
def test_parse_verdict_sentinels():
    assert parse_verdict(_completion("ANSWERABLE")) is True
    assert parse_verdict(_completion("NOT_ANSWERABLE")) is False
    assert parse_verdict(_completion("not answerable")) is False
    assert parse_verdict(_completion("NOT ANSWERABLE")) is False


def test_parse_verdict_tolerates_explanation():
    """模型偶尔会带一句解释：首行含答案就取，别因为多话就当无法判断。"""
    assert parse_verdict(_completion("ANSWERABLE\n片段 1 有定义")) is True
    assert parse_verdict(_completion("NOT_ANSWERABLE\n只是提到了名词")) is False


def test_parse_verdict_ambiguous_or_empty_is_none():
    assert parse_verdict(_completion("")) is None
    assert parse_verdict(_completion("ANSWERABLE 或 NOT_ANSWERABLE")) is None
    assert parse_verdict(_completion("我不确定")) is None
    assert parse_verdict({}) is None
    assert parse_verdict({"choices": []}) is None


# ---------------------------------------------------------------- 调用行为
async def test_decide_true_and_prompt_contents():
    requests: list[dict] = []
    judge = _judge(httpx.MockTransport(_handler(requests)))
    verdict = await judge.decide("为什么需要索引？", ["B+ 树把数据放在叶子节点。", "无关片段。"])
    assert verdict is True
    payload = requests[0]
    assert payload["temperature"] == 0
    assert payload["max_tokens"] == 64
    user = payload["messages"][1]["content"]
    assert "为什么需要索引？" in user
    assert "B+ 树把数据放在叶子节点。" in user


async def test_decide_false():
    judge = _judge(httpx.MockTransport(_handler([], content="NOT_ANSWERABLE")))
    assert await judge.decide("问题", ["只是同主题的片段"]) is False


async def test_decide_empty_snippets_short_circuits():
    requests: list[dict] = []
    judge = _judge(httpx.MockTransport(_handler(requests)))
    assert await judge.decide("问题", []) is False
    assert requests == []  # 没有片段就不必花一次模型调用


async def test_decide_http_error_is_unknown():
    judge = _judge(httpx.MockTransport(_handler([], status=503)))
    assert await judge.decide("问题", ["片段"]) is None


async def test_decide_timeout_is_unknown():
    async def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    judge = _judge(httpx.MockTransport(boom))
    assert await judge.decide("问题", ["片段"]) is None


async def test_decide_unparseable_is_unknown():
    judge = _judge(httpx.MockTransport(_handler([], content="我觉得差不多")))
    assert await judge.decide("问题", ["片段"]) is None


def test_snippet_truncation_and_limit():
    from app.adapters.judge.llm import SNIPPET_CHARS, SNIPPET_LIMIT

    snippet = "字" * (SNIPPET_CHARS + 50)
    rendered = RetrievalJudge._payload_snippets([snippet] * (SNIPPET_LIMIT + 3))
    assert "[片段 1]" in rendered
    assert f"[片段 {SNIPPET_LIMIT}]" in rendered
    assert f"[片段 {SNIPPET_LIMIT + 1}]" not in rendered  # 只喂前 N 条
    assert "字" * (SNIPPET_CHARS + 1) not in rendered  # 单条截断


# ---------------------------------------------------------------- 两维结构化判定
def test_parse_judgement_plain_json():
    from app.adapters.judge import parse_judgement

    assert parse_judgement('{"same_subject": true, "has_specific_info": true}') == {
        "same_subject": True,
        "has_specific_info": True,
    }
    assert parse_judgement('{"same_subject": false, "has_specific_info": true}') == {
        "same_subject": False,
        "has_specific_info": True,
    }


def test_parse_judgement_json_inside_prose():
    """推理模型常带一句前后文：JSON 在中间也要能取到。"""
    from app.adapters.judge import parse_judgement

    content = '判断如下：\n{"same_subject": true, "has_specific_info": false}\n以上。'
    assert parse_judgement(content) == {"same_subject": True, "has_specific_info": False}


def test_parse_judgement_string_booleans():
    from app.adapters.judge import parse_judgement

    assert parse_judgement('{"same_subject": "yes", "has_specific_info": "no"}') == {
        "same_subject": True,
        "has_specific_info": False,
    }


def test_parse_judgement_incomplete_json_is_none():
    from app.adapters.judge import parse_judgement

    assert parse_judgement('{"same_subject": true}') is None
    assert parse_judgement('{"same_subject": true, "has_specific_info": "maybe"}') is None
    assert parse_judgement("完全不是 JSON") is None


def test_parse_judgement_sentinel_fallback():
    """兼容回退成一句哨兵的供应商输出。"""
    from app.adapters.judge import parse_judgement

    assert parse_judgement("ANSWERABLE") == {"same_subject": True, "has_specific_info": True}
    assert parse_judgement("NOT_ANSWERABLE") == {
        "same_subject": False,
        "has_specific_info": False,
    }


async def test_decide_detailed_returns_dimensions():
    requests: list[dict] = []
    judge = _judge(
        httpx.MockTransport(
            _handler(requests, content='{"same_subject": true, "has_specific_info": false}')
        )
    )
    verdict, detail = await judge.decide_detailed("问题", ["片段"])
    assert verdict is False
    assert detail == {"same_subject": True, "has_specific_info": False}
    assert "same_subject" in requests[0]["messages"][0]["content"]


async def test_decide_detailed_failure_returns_no_detail():
    judge = _judge(httpx.MockTransport(_handler([], status=500)))
    verdict, detail = await judge.decide_detailed("问题", ["片段"])
    assert verdict is None
    assert detail is None
