"""真实模型 Provider（OpenAI 兼容 chat/completions）单元测试。

全部用 ``httpx.MockTransport`` 在进程内伪造供应商，**不联网**；真实链路验证属于
``verification/`` 的职责，不在 pytest。覆盖：意图→工具暴露、工具映射与白名单、正文、
SSE 流式与退化、重试/不重试、预算、错误映射、密钥与身份不外泄、describe 与契约一致性，
以及 AT-32 首跑修复的两条模型侧行为：**课表答案可核验化（ISO 日期/空课句式）** 与
**计划草稿/保存语义（DraftIntent）**。
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, AsyncIterator

import httpx
import pytest

from app.adapters.model import real as real_module
from app.adapters.model.gateway import (
    Answer,
    DraftIntent,
    DraftRecord,
    HistoryMessage,
    ModelBudget,
    ModelContext,
    SaveRecord,
    ToolCall,
    ToolExecutionRecord,
)
from app.adapters.model.real import (
    DRAFT_TOOL_DEFINITION,
    DRAFT_TOOL_NAME,
    MODEL_CALLABLE_TOOLS,
    TOOL_DEFINITIONS,
    RealProviderAdapter,
)
from app.shared.errors import ApiError

API_KEY = "sk-test-very-secret"
MODEL = "deepseek-chat"
BASE_URL = "http://model.invalid/v1"
SECRET_MESSAGE = "秘密问题标记-不得泄漏"
NEUTRAL_MESSAGE = "请介绍一下你自己"

SCHEDULE_QUESTION = "明天有什么课？"
DOCS_QUESTION = "课程资料里对实验报告有什么要求？"
PLAN_QUESTION = "帮我制定期末复习计划并保存"

ITEM_A = {
    "id": "sch_eval_1",
    "student_id": "usr_eval",
    "course_id": "crs_1",
    "course_name": "数据结构",
    "class_date": "2026-10-29",
    "start_time": "08:00",
    "end_time": "09:40",
    "location": "教学楼 A101",
    "version": 1,
}
ITEM_B = {
    "id": "sch_eval_2",
    "student_id": "usr_eval",
    "course_id": "crs_2",
    "course_name": "操作系统",
    "class_date": "2026-10-29",
    "start_time": "10:00",
    "end_time": "11:40",
    "location": "实验楼 B203",
    "version": 1,
}


# --------------------------------------------------------------------------- #
# 构造辅助
# --------------------------------------------------------------------------- #
def _context(
    *,
    message: str = DOCS_QUESTION,
    history: Any = (),
    tool_results: list[ToolExecutionRecord] | None = None,
    draft: DraftRecord | None = None,
    save: SaveRecord | None = None,
) -> ModelContext:
    return ModelContext(
        request_id="req_real_provider",
        conversation_id="cnv_real_provider",
        message=message,
        history=history,
        accepted_at=datetime(2026, 10, 28, 1, 0, tzinfo=timezone.utc),
        school_timezone="Asia/Shanghai",
        today=date(2026, 10, 28),
        tomorrow=date(2026, 10, 29),
        tool_results=list(tool_results or []),
        draft=draft,
        save=save,
    )


def _budget(*, decisions: int = 6, deadline_in: float = 60.0) -> ModelBudget:
    return ModelBudget(
        remaining_decisions=decisions,
        remaining_tools=10,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=deadline_in),
    )


def _adapter(handler: Any, **overrides: Any) -> RealProviderAdapter:
    params: dict[str, Any] = {
        "endpoint": BASE_URL,
        "api_key": API_KEY,
        "model": MODEL,
        "timeout_seconds": 5.0,
        "max_retries": 0,
        "transport": httpx.MockTransport(handler),
    }
    params.update(overrides)
    return RealProviderAdapter(**params)


def _text_handler(
    text: str, *, captured: list[dict[str, Any]] | None = None
):
    async def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(json.loads(request.content))
        return httpx.Response(200, json=_text_payload(text))

    return handler


def _tool_handler(
    name: str,
    arguments: Any,
    *,
    captured: list[dict[str, Any]] | None = None,
):
    async def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(json.loads(request.content))
        return httpx.Response(200, json=_tool_payload(name, arguments))

    return handler


def _tool_payload(name: str, arguments: Any) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": name, "arguments": arguments},
                        }
                    ],
                }
            }
        ]
    }


def _text_payload(text: str) -> dict[str, Any]:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def _sse_body(chunks: list[str]) -> bytes:
    lines: list[str] = []
    for chunk in chunks:
        event = {"choices": [{"delta": {"content": chunk}}]}
        lines.append("data: " + json.dumps(event, ensure_ascii=False) + "\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode("utf-8")


async def _emitted(provider: RealProviderAdapter, text: str) -> list[str]:
    deltas: list[str] = []

    async def emit(delta: str) -> None:
        deltas.append(delta)

    await provider.stream_answer(Answer(text=text), emit)
    return deltas


def _schedule_record(
    items: list[dict[str, Any]],
    *,
    from_date: str = "2026-10-28",
    to_date: str = "2026-10-28",
) -> ToolExecutionRecord:
    status = "ok" if items else "empty"
    return ToolExecutionRecord(
        tool_name="get_my_schedule",
        arguments={"from_date": from_date, "to_date": to_date},
        success=True,
        result_status=status,
        dependency_state="satisfied" if items else "empty",
        payload={
            "status": status,
            "from_date": from_date,
            "to_date": to_date,
            "school_timezone": "Asia/Shanghai",
            "items": items,
        },
    )


def _draft_record() -> DraftRecord:
    return DraftRecord(draft_id="dft_test_1", draft_version=1, operation_id="dop_test_1")


def _save_record() -> SaveRecord:
    return SaveRecord(plan_id="plan_test_1", operation_id="dop_test_1", status="created")


class _BrokenSse(httpx.AsyncByteStream):
    """先给一块正文，再抛读超时（模拟流中断）。"""

    def __init__(self, first_chunk: str) -> None:
        self._first_chunk = first_chunk

    async def __aiter__(self) -> AsyncIterator[bytes]:
        event = {"choices": [{"delta": {"content": self._first_chunk}}]}
        yield ("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode("utf-8")
        raise httpx.ReadTimeout("upstream stream broke")


# --------------------------------------------------------------------------- #
# 意图 → 工具暴露
# --------------------------------------------------------------------------- #
async def test_tools_are_exposed_by_intent():
    cases = [
        (SCHEDULE_QUESTION, ["get_my_schedule"], None),
        (DOCS_QUESTION, ["search_course_docs"], None),
        (PLAN_QUESTION, [DRAFT_TOOL_NAME], None),
        (NEUTRAL_MESSAGE, [], None),
        (PLAN_QUESTION, [], _draft_record()),  # 草稿已出：不再暴露工具
    ]
    for message, expected, draft in cases:
        captured: list[dict[str, Any]] = []
        context = _context(message=message, draft=draft)
        provider = _adapter(_text_handler("嗯，我了解了。", captured=captured))
        await provider.next_action(context, _budget())
        tools = captured[0].get("tools") or []
        names = [tool["function"]["name"] for tool in tools]
        assert names == expected, (message, names)


async def test_plan_and_schedule_intents_are_disjoint():
    """S09「课程安排」不是计划请求；P07「规划…安排」是计划请求。"""
    s09 = _context(message="明天的课程安排是怎样的？")
    p07 = _context(message="帮我规划下周的复习安排")
    provider = _adapter(_text_handler("好的。"))
    assert [
        tool["function"]["name"] for tool in provider._tools_for(s09)
    ] == ["get_my_schedule"]
    assert [
        tool["function"]["name"] for tool in provider._tools_for(p07)
    ] == [DRAFT_TOOL_NAME]


# --------------------------------------------------------------------------- #
# 工具映射与白名单
# --------------------------------------------------------------------------- #
async def test_tool_call_is_mapped_to_whitelisted_action():
    captured: list[dict[str, Any]] = []
    provider = _adapter(
        _tool_handler(
            "search_course_docs",
            json.dumps({"query": "期末成绩"}, ensure_ascii=False),
            captured=captured,
        )
    )
    action = await provider.next_action(_context(message=DOCS_QUESTION), _budget())

    assert isinstance(action, ToolCall)
    assert action.tool_name == "search_course_docs"
    assert action.arguments == {"query": "期末成绩"}

    payload = captured[0]
    assert payload["model"] == MODEL
    assert {"temperature", "max_tokens", "messages", "tools"} <= set(payload)
    tools = payload["tools"]
    assert [tool["function"]["name"] for tool in tools] == ["search_course_docs"]
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][-1] == {"role": "user", "content": DOCS_QUESTION}


async def test_tool_arguments_are_passed_through_without_defaults():
    provider = _adapter(
        _tool_handler("get_my_schedule", {"from_date": "2026-10-29"})
    )
    action = await provider.next_action(_context(message=SCHEDULE_QUESTION), _budget())

    assert isinstance(action, ToolCall)
    # 不补 to_date 等默认值：参数原样交给 runner 的二次校验。
    assert action.arguments == {"from_date": "2026-10-29"}


@pytest.mark.parametrize(
    "name",
    [
        "save_study_plan",
        "delete_everything",
        "get_my_schedules",
        "",
        "get_my_schedule",  # 本轮只暴露 search：未暴露的合法工具同样拒绝
    ],
)
async def test_non_exposed_tool_is_rejected(name: str):
    provider = _adapter(_tool_handler(name, "{}"))
    with pytest.raises(ApiError) as excinfo:
        await provider.next_action(_context(message=DOCS_QUESTION), _budget())

    assert excinfo.value.code == "MODEL_UNAVAILABLE"
    assert excinfo.value.status_code == 503


async def test_invalid_tool_arguments_json_is_rejected():
    provider = _adapter(_tool_handler("search_course_docs", "{not json"))
    with pytest.raises(ApiError) as excinfo:
        await provider.next_action(_context(message=DOCS_QUESTION), _budget())

    assert excinfo.value.code == "MODEL_UNAVAILABLE"


# --------------------------------------------------------------------------- #
# 正文回答 / 历史 / 工具结果回灌 / 身份隔离
# --------------------------------------------------------------------------- #
async def test_plain_text_answer_when_no_tool_calls():
    provider = _adapter(
        _text_handler("  你好，我是校园课程智能助手。  ")
    )
    action = await provider.next_action(_context(message=NEUTRAL_MESSAGE), _budget())

    assert isinstance(action, Answer)
    assert action.text == "你好，我是校园课程智能助手。"


async def test_history_pairs_and_tool_results_are_fed_back():
    captured: list[dict[str, Any]] = []
    record = ToolExecutionRecord(
        tool_name="search_course_docs",
        arguments={"query": "实验预习要求"},
        success=True,
        result_status="ok",
        dependency_state="satisfied",
        payload={"status": "ok", "corpus_empty": False, "_evidence": object()},
    )
    context = _context(
        history=(
            HistoryMessage(role="user", content="上轮问题"),
            HistoryMessage(role="assistant", content="上轮回答"),
            ("旧问题", "旧回答"),
        ),
        tool_results=[record],
    )
    provider = _adapter(
        _text_handler("依据资料：预习报告需提前提交。", captured=captured)
    )
    action = await provider.next_action(context, _budget())

    assert isinstance(action, Answer)
    messages = captured[0]["messages"]
    assert [message["role"] for message in messages[:2]] == ["system", "user"]
    contents = [message.get("content") for message in messages]
    assert "上轮问题" in contents and "上轮回答" in contents
    assert "旧问题" in contents and "旧回答" in contents

    tool_messages = [message for message in messages if message["role"] == "tool"]
    assert len(tool_messages) == 1
    assert "_evidence" not in tool_messages[0]["content"]
    assert "corpus_empty" in tool_messages[0]["content"]
    call_message = next(
        message
        for message in messages
        if message["role"] == "assistant" and message.get("tool_calls")
    )
    assert call_message["tool_calls"][0]["function"]["name"] == "search_course_docs"


async def test_identity_fields_are_never_sent_to_model():
    captured: list[dict[str, Any]] = []
    provider = _adapter(_text_handler("好的", captured=captured))
    context = _context(message=NEUTRAL_MESSAGE)
    # ModelContext 没有身份字段；即便调用方塞进来，适配器也不应读取/发送。
    context.user_id = "usr_should_not_leak"  # type: ignore[attr-defined]
    context.session_id = "ses_should_not_leak"  # type: ignore[attr-defined]
    context.auth_token = "tok_should_not_leak"  # type: ignore[attr-defined]

    await provider.next_action(context, _budget())

    serialized = json.dumps(captured[0], ensure_ascii=False)
    for secret in (
        "usr_should_not_leak",
        "ses_should_not_leak",
        "tok_should_not_leak",
        API_KEY,
        "req_real_provider",
        "cnv_real_provider",
    ):
        assert secret not in serialized
    allowed_keys = {"role", "content", "tool_calls", "tool_call_id"}
    for message in captured[0]["messages"]:
        assert set(message) <= allowed_keys


async def test_system_prompt_has_iso_date_anchors():
    captured: list[dict[str, Any]] = []
    provider = _adapter(_text_handler("好的", captured=captured))
    await provider.next_action(_context(message=NEUTRAL_MESSAGE), _budget())

    system = captured[0]["messages"][0]["content"]
    assert "2026-10-28" in system and "2026-10-29" in system
    assert "YYYY-MM-DD" in system


# --------------------------------------------------------------------------- #
# 错误映射与重试
# --------------------------------------------------------------------------- #
async def test_invalid_json_body_maps_to_model_unavailable():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"{not json", headers={"content-type": "application/json"}
        )

    provider = _adapter(handler)
    with pytest.raises(ApiError) as excinfo:
        await provider.next_action(_context(message=NEUTRAL_MESSAGE), _budget())

    assert excinfo.value.code == "MODEL_UNAVAILABLE"


async def test_response_without_choices_maps_to_model_unavailable():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"object": "chat.completion", "choices": []})

    provider = _adapter(handler)
    with pytest.raises(ApiError) as excinfo:
        await provider.next_action(_context(message=NEUTRAL_MESSAGE), _budget())

    assert excinfo.value.code == "MODEL_UNAVAILABLE"


async def test_5xx_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(real_module, "RETRY_BACKOFF_SECONDS", 0.0)
    calls = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json=_text_payload("重试后成功"))

    provider = _adapter(handler, max_retries=1)
    action = await provider.next_action(_context(message=NEUTRAL_MESSAGE), _budget())

    assert isinstance(action, Answer)
    assert action.text == "重试后成功"
    assert calls["n"] == 2


async def test_4xx_is_not_retried(monkeypatch):
    monkeypatch.setattr(real_module, "RETRY_BACKOFF_SECONDS", 0.0)
    calls = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = _adapter(handler, max_retries=3)
    with pytest.raises(ApiError) as excinfo:
        await provider.next_action(_context(message=NEUTRAL_MESSAGE), _budget())

    assert excinfo.value.code == "MODEL_UNAVAILABLE"
    assert excinfo.value.status_code == 503
    assert calls["n"] == 1, "4xx（含 401/429）不得重试"


async def test_timeout_is_retried_per_max_retries(monkeypatch):
    monkeypatch.setattr(real_module, "RETRY_BACKOFF_SECONDS", 0.0)
    calls = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("slow upstream", request=request)

    provider = _adapter(handler, max_retries=1)
    with pytest.raises(ApiError) as excinfo:
        await provider.next_action(_context(message=NEUTRAL_MESSAGE), _budget())

    assert excinfo.value.code == "MODEL_UNAVAILABLE"
    assert calls["n"] == 2, "超时按 max_retries 语义重试一次后失败"


# --------------------------------------------------------------------------- #
# 预算
# --------------------------------------------------------------------------- #
async def test_exhausted_decisions_fail_before_any_network_call():
    calls = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        calls["n"] += 1
        return httpx.Response(200, json=_text_payload("x"))

    with pytest.raises(ApiError) as excinfo:
        await _adapter(handler).next_action(
            _context(message=NEUTRAL_MESSAGE), _budget(decisions=0)
        )

    assert excinfo.value.code == "CALL_LIMIT_REACHED"
    assert calls["n"] == 0


async def test_passed_deadline_raises_execution_timeout():
    async def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, json=_text_payload("x"))

    with pytest.raises(ApiError) as excinfo:
        await _adapter(handler).next_action(
            _context(message=NEUTRAL_MESSAGE), _budget(deadline_in=-1.0)
        )

    assert excinfo.value.code == "EXECUTION_TIMEOUT"
    assert excinfo.value.status_code == 504


# --------------------------------------------------------------------------- #
# 流式
# --------------------------------------------------------------------------- #
async def test_stream_answer_emits_sse_chunks_in_order():
    seen: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            content=_sse_body(["第一段", "第二段"]),
            headers={"content-type": "text/event-stream"},
        )

    provider = _adapter(handler)
    deltas = await _emitted(provider, "第一段第二段")

    assert seen[0]["stream"] is True
    assert deltas == ["第一段", "第二段"]
    assert "".join(deltas) == "第一段第二段"


async def test_stream_chunks_are_split_by_token_chunk_limit(monkeypatch):
    monkeypatch.setattr(RealProviderAdapter, "_chunk_limit", staticmethod(lambda: 5))
    text = "一二三四五六七八九十"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_sse_body([text]),
            headers={"content-type": "text/event-stream"},
        )

    deltas = await _emitted(_adapter(handler), text)

    assert "".join(deltas) == text
    assert len(deltas) >= 2
    assert all(0 < len(delta) <= 5 for delta in deltas)


async def test_stream_falls_back_to_local_chunks_when_server_returns_json():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_text_payload("完整正文"),
            headers={"content-type": "application/json"},
        )

    deltas = await _emitted(_adapter(handler), "完整正文")

    assert "".join(deltas) == "完整正文"


async def test_stream_falls_back_when_server_rejects_stream():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "stream not supported"})

    deltas = await _emitted(_adapter(handler), "不支持流式也能输出")

    assert deltas == ["不支持流式也能输出"]


async def test_stream_interruption_maps_to_model_unavailable_but_keeps_emitted():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_BrokenSse("前半"),
        )

    provider = _adapter(handler)
    deltas: list[str] = []

    async def emit(delta: str) -> None:
        deltas.append(delta)

    with pytest.raises(ApiError) as excinfo:
        await provider.stream_answer(Answer(text="前半后半"), emit)

    assert excinfo.value.code == "MODEL_UNAVAILABLE"
    assert deltas == ["前半"], "已 emit 的部分不撤回（与 runner 终态语义一致）"


# --------------------------------------------------------------------------- #
# 密钥与请求体保护 / describe / 契约一致性
# --------------------------------------------------------------------------- #
async def test_api_key_and_request_body_are_never_logged(caplog):
    caplog.set_level(logging.DEBUG)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = _adapter(handler, max_retries=1)
    with pytest.raises(ApiError):
        await provider.next_action(_context(message=SECRET_MESSAGE), _budget())

    assert API_KEY not in caplog.text
    assert SECRET_MESSAGE not in caplog.text


def test_describe_reports_implemented_and_hides_api_key():
    provider = RealProviderAdapter(endpoint=BASE_URL, api_key=API_KEY, model=MODEL)

    desc = provider.describe()

    assert desc["implemented"] is True
    assert desc["api_key_configured"] is True
    assert "api_key" not in desc
    assert API_KEY not in repr(desc)


async def test_unconfigured_provider_fails_loudly_without_network():
    provider = RealProviderAdapter(endpoint=BASE_URL, api_key="", model=MODEL)

    with pytest.raises(ApiError) as excinfo:
        await provider.next_action(_context(message=NEUTRAL_MESSAGE), _budget())

    assert excinfo.value.code == "MODEL_UNAVAILABLE"


def test_tool_definitions_match_contract_inputs():
    from app.modules.assistant import contracts

    functions = {
        definition["function"]["name"]: definition["function"]
        for definition in TOOL_DEFINITIONS
    }
    assert set(functions) == {"get_my_schedule", "search_course_docs"}
    assert set(functions) <= set(contracts.TOOL_NAMES)
    assert "save_study_plan" not in functions
    assert "save_study_plan" not in MODEL_CALLABLE_TOOLS

    for name, function in functions.items():
        parameters = function["parameters"]
        assert parameters["type"] == "object"
        assert parameters["additionalProperties"] is False
        assert set(parameters["properties"]) == set(contracts._ARGUMENT_KEYS[name])  # noqa: SLF001

    schedule = functions["get_my_schedule"]["parameters"]["properties"]
    assert schedule["from_date"]["format"] == "date"
    assert "required" not in functions["get_my_schedule"]["parameters"]
    assert functions["search_course_docs"]["parameters"]["required"] == ["query"]

    # Provider 内部的草稿通道：不属于 MCP 工具契约，也不产生 tool 事件。
    draft = DRAFT_TOOL_DEFINITION["function"]
    assert draft["name"] == DRAFT_TOOL_NAME
    assert draft["parameters"]["additionalProperties"] is False
    assert set(draft["parameters"]["required"]) == {"title", "content"}


# --------------------------------------------------------------------------- #
# AT-32 修复 A：课表答案可核验化（ISO 日期 / 空课固定句式 / 不重复追加）
# --------------------------------------------------------------------------- #
async def test_schedule_grounding_appends_iso_items():
    record = _schedule_record([ITEM_A, ITEM_B], from_date="2026-10-29", to_date="2026-10-29")
    provider = _adapter(
        _text_handler("明天（2026年10月29日）你有数据结构与操作系统两门课，请注意别迟到。")
    )
    action = await provider.next_action(
        _context(message=SCHEDULE_QUESTION, tool_results=[record]), _budget()
    )

    assert isinstance(action, Answer)
    text = action.text
    assert "2026年10月29日）" in text, "模型原文保留"
    assert "【课表核对】" in text
    for item in (ITEM_A, ITEM_B):
        assert item["course_name"] in text
        assert item["class_date"] in text
        assert item["start_time"] in text
        assert item["end_time"] in text
        assert item["location"] in text


async def test_schedule_empty_adds_fixed_no_class_phrase():
    record = _schedule_record([])
    provider = _adapter(
        _text_handler("今天（2026年10月28日）你没有需要上的课程。")
    )
    action = await provider.next_action(
        _context(message="今天的课表是什么？", tool_results=[record]), _budget()
    )

    assert isinstance(action, Answer)
    assert "没有课" in action.text
    assert "2026-10-28" in action.text


async def test_schedule_compliant_answer_is_not_duplicated():
    record = _schedule_record([ITEM_A], from_date="2026-10-29", to_date="2026-10-29")
    compliant = (
        "2026-10-29 08:00-09:40 数据结构，地点 教学楼 A101。"
    )
    provider = _adapter(_text_handler(compliant))
    action = await provider.next_action(
        _context(message=SCHEDULE_QUESTION, tool_results=[record]), _budget()
    )

    assert isinstance(action, Answer)
    assert "【课表核对】" not in action.text
    assert action.text == compliant


async def test_schedule_question_without_tool_call_gets_fallback_tool():
    provider = _adapter(_text_handler("明天你有两节课。"))
    action = await provider.next_action(_context(message=SCHEDULE_QUESTION), _budget())

    assert isinstance(action, ToolCall)
    assert action.tool_name == "get_my_schedule"
    assert action.arguments == {"from_date": "2026-10-29", "to_date": "2026-10-29"}


async def test_docs_question_without_tool_call_gets_fallback_search():
    provider = _adapter(_text_handler("我记得资料里好像是……"))
    action = await provider.next_action(_context(message=DOCS_QUESTION), _budget())

    assert isinstance(action, ToolCall)
    assert action.tool_name == "search_course_docs"
    assert action.arguments == {"query": DOCS_QUESTION}


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        # AT-32 S05：deterministic 的 SCHEDULE_WORDS 不含「哪里上」。
        ("明天的课在哪里上？", ["get_my_schedule"]),
        ("明天在哪上课？", ["get_my_schedule"]),
        # U05：办公室在哪里是资料问题，不得被地点问法误判成课表。
        ("课件里说数据结构老师的办公室在哪里？", ["search_course_docs"]),
    ],
)
async def test_location_question_intent_routing(message: str, expected: list[str]):
    captured: list[dict[str, Any]] = []
    provider = _adapter(_text_handler("好的。", captured=captured))
    await provider.next_action(_context(message=message), _budget())

    tools = captured[0].get("tools") or []
    assert [tool["function"]["name"] for tool in tools] == expected


async def test_location_question_falls_back_to_schedule_tool():
    provider = _adapter(_text_handler("明天下午有一节课。"))
    action = await provider.next_action(_context(message="明天的课在哪里上？"), _budget())

    assert isinstance(action, ToolCall)
    assert action.tool_name == "get_my_schedule"
    assert action.arguments == {"from_date": "2026-10-29", "to_date": "2026-10-29"}


async def test_citation_ids_are_stripped_from_answer():
    provider = _adapter(
        _text_handler("依据见 cit_injected_evil 与 cit_other_1，请以原文为准。")
    )
    action = await provider.next_action(_context(message=NEUTRAL_MESSAGE), _budget())

    assert isinstance(action, Answer)
    assert "cit_" not in action.text
    assert "请以原文为准" in action.text


# --------------------------------------------------------------------------- #
# AT-32 修复 B：计划草稿 / 保存语义（DraftIntent）
# --------------------------------------------------------------------------- #
async def test_draft_tool_maps_to_draft_intent():
    payload = {
        "title": "数据结构期末复习计划",
        "goal": "两周内覆盖全部考点",
        "start_date": "2026-11-01",
        "end_date": "2026-11-14",
        "content": "1. 每天一个专题；2. 周末自测。",
    }
    provider = _adapter(_tool_handler(DRAFT_TOOL_NAME, json.dumps(payload, ensure_ascii=False)))
    action = await provider.next_action(_context(message=PLAN_QUESTION), _budget())

    assert isinstance(action, DraftIntent)
    assert action.title == payload["title"]
    assert action.goal == payload["goal"]
    assert action.content == payload["content"]
    assert action.start_date == date(2026, 11, 1)
    assert action.end_date == date(2026, 11, 14)
    assert action.save_candidate is True, "本轮明确要求保存 → 候选置真（授权仍由服务端判）"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("帮我制定期末复习计划并保存", True),
        ("能不能帮我制定计划并保存？", False),
        ("不要保存，只帮我制定计划", False),
        ("先别保存这个计划", False),
        ("他说要保存这个计划", False),
        ("帮我制定一份复习计划", False),
    ],
)
async def test_draft_save_candidate_uses_server_classifier(message: str, expected: bool):
    payload = {"title": "复习计划", "content": "第 1 周复习。"}
    provider = _adapter(_tool_handler(DRAFT_TOOL_NAME, json.dumps(payload, ensure_ascii=False)))
    action = await provider.next_action(_context(message=message), _budget())

    assert isinstance(action, DraftIntent)
    assert action.save_candidate is expected


async def test_plan_text_answer_falls_back_to_draft():
    draft_text = "目标：两周覆盖数据结构。\n1. 每天一个专题。"
    provider = _adapter(_text_handler(draft_text))
    action = await provider.next_action(_context(message=PLAN_QUESTION), _budget())

    assert isinstance(action, DraftIntent)
    assert action.content == draft_text
    assert action.title
    assert action.save_candidate is True


async def test_draft_round_answers_with_unsaved_wording():
    captured: list[dict[str, Any]] = []
    provider = _adapter(
        _text_handler("这是给你的复习安排。", captured=captured)
    )
    action = await provider.next_action(
        _context(message=PLAN_QUESTION, draft=_draft_record()), _budget()
    )

    assert isinstance(action, Answer)
    assert "尚未保存" in action.text
    assert "已按你的明确要求保存" not in action.text
    assert "tools" not in captured[0], "草稿已出：不再暴露/调度工具"


async def test_draft_round_ignores_repeated_draft_tool_call():
    provider = _adapter(
        _tool_handler(DRAFT_TOOL_NAME, json.dumps({"title": "重复", "content": "重复"}))
    )
    action = await provider.next_action(
        _context(message=PLAN_QUESTION, draft=_draft_record()), _budget()
    )

    assert isinstance(action, Answer)
    assert "尚未保存" in action.text


async def test_saved_round_finalizes_confirmation_phrase():
    provider = _adapter(_text_handler("好的，已经处理完了。"))
    action = await provider.next_action(
        _context(message=PLAN_QUESTION, save=_save_record()), _budget()
    )

    assert isinstance(action, Answer)
    assert "已按你的明确要求保存" in action.text
    assert "plan_test_1" in action.text
    assert "尚未保存" not in action.text


async def test_saved_round_removes_contradictory_unsaved_wording():
    provider = _adapter(_text_handler("草稿尚未保存，你可以稍后保存。"))
    action = await provider.next_action(
        _context(message=PLAN_QUESTION, save=_save_record()), _budget()
    )

    assert isinstance(action, Answer)
    assert "尚未保存" not in action.text
    assert "已按你的明确要求保存" in action.text


async def test_plan_round_never_claims_saved_without_server_save():
    provider = _adapter(_text_handler("已按你的明确要求保存学习计划。"))
    action = await provider.next_action(
        _context(message=PLAN_QUESTION, draft=_draft_record()), _budget()
    )

    assert isinstance(action, Answer)
    assert "已按你的明确要求保存" not in action.text
    assert "尚未保存" in action.text
