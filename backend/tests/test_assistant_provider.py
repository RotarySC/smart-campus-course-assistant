"""A1 车道测试：ModelGateway 契约、确定性 Provider 行为、工具参数白名单。"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.adapters.model.deterministic import (
    DeterministicProvider,
    mentions_save,
    schedule_range,
)
from app.adapters.model.gateway import (
    Answer,
    DraftIntent,
    ModelBudget,
    ModelContext,
    ToolCall,
)
from app.modules.assistant.contracts import validate_tool_call
from app.shared.errors import ApiError

ACCEPTED_AT = datetime(2026, 10, 23, 15, 30, tzinfo=timezone.utc)  # 北京时间 2026-10-23 23:30


def make_context(message: str, **overrides) -> ModelContext:
    today = date(2026, 10, 23)
    values = dict(
        request_id="req_test_1",
        conversation_id="cnv_test_1",
        message=message,
        history=(),
        accepted_at=ACCEPTED_AT,
        school_timezone="Asia/Shanghai",
        today=today,
        tomorrow=date(2026, 10, 24),
    )
    values.update(overrides)
    return ModelContext(**values)


def budget() -> ModelBudget:
    return ModelBudget(
        remaining_decisions=6,
        remaining_tools=10,
        deadline_at=datetime(2026, 10, 23, 15, 31, tzinfo=timezone.utc),
    )


async def test_schedule_intent_anchors_to_school_date():
    provider = DeterministicProvider()
    context = make_context("明天有课吗")
    action = await provider.next_action(context, budget())
    assert isinstance(action, ToolCall)
    assert action.tool_name == "get_my_schedule"
    assert action.arguments == {"from_date": "2026-10-24", "to_date": "2026-10-24"}

    today_context = make_context("今天课表")
    today_action = await provider.next_action(today_context, budget())
    assert isinstance(today_action, ToolCall)
    assert today_action.arguments == {"from_date": "2026-10-23", "to_date": "2026-10-23"}


def test_schedule_range_week_windows():
    context = make_context("下周的课表")
    start, end = schedule_range(context)
    assert start == "2026-10-26"  # 2026-10-23 是周五，下周一是 26 日
    assert end == "2026-11-01"
    start_this, end_this = schedule_range(make_context("本周课表"))
    assert start_this == "2026-10-19"
    assert end_this == "2026-10-25"


async def test_docs_intent_uses_current_message_only():
    provider = DeterministicProvider()
    context = make_context("课件里对实验报告有什么要求？")
    action = await provider.next_action(context, budget())
    assert isinstance(action, ToolCall)
    assert action.tool_name == "search_course_docs"
    assert action.arguments == {"query": "课件里对实验报告有什么要求？"}


async def test_plan_intent_is_draft_with_save_candidate_flag():
    provider = DeterministicProvider()
    plan_context = make_context("帮我制定一份期末复习计划")
    action = await provider.next_action(plan_context, budget())
    assert isinstance(action, DraftIntent)
    assert "学习计划" in action.title
    assert action.save_candidate is False

    save_context = make_context("帮我制定期末复习计划并保存")
    save_action = await provider.next_action(save_context, budget())
    assert isinstance(save_action, DraftIntent)
    assert save_action.save_candidate is True


async def test_regulation_question_without_retrieval_refuses_claim():
    """规定类问题无任何证据时明确“依据不足”，不编造规定。"""
    provider = DeterministicProvider()
    context = make_context("考勤怎么算？")
    action = await provider.next_action(context, budget())
    assert isinstance(action, Answer)
    assert "依据不足" in action.text


async def test_docs_question_retrieves_before_claiming():
    provider = DeterministicProvider()
    context = make_context("期末成绩怎么算？")
    action = await provider.next_action(context, budget())
    assert isinstance(action, ToolCall)
    assert action.tool_name == "search_course_docs"


async def test_empty_corpus_is_reported_not_claimed_as_no_rule():
    from app.adapters.model.gateway import EvidenceSet, ToolExecutionRecord

    provider = DeterministicProvider()
    record = ToolExecutionRecord(
        tool_name="search_course_docs",
        arguments={"query": "期末成绩怎么算？"},
        success=True,
        result_status="empty",
        dependency_state="empty",
        payload={
            "status": "empty",
            "corpus_empty": True,
            "_evidence": EvidenceSet(status="empty", corpus_empty=True, revision=0),
        },
    )
    context = make_context("期末成绩怎么算？", tool_results=[record])
    action = await provider.next_action(context, budget())
    assert isinstance(action, Answer)
    assert "还没有已发布的课程资料" in action.text


async def test_general_advice_is_labelled_as_advice():
    provider = DeterministicProvider()
    context = make_context("怎么安排时间比较好")
    action = await provider.next_action(context, budget())
    assert isinstance(action, Answer)
    assert "一般学习建议" in action.text


async def test_stream_answer_chunks_are_bounded_and_lossless():
    provider = DeterministicProvider()
    text = "依据不足：目前没有取得课程资料或课表证据，不能确认这项规定。" * 5
    chunks: list[str] = []

    async def emit(delta: str) -> None:
        chunks.append(delta)

    await provider.stream_answer(Answer(text=text), emit)
    assert "".join(chunks) == text
    assert all(0 < len(chunk) <= 4096 for chunk in chunks)


async def test_determinism_same_input_same_action():
    provider = DeterministicProvider()
    first = await provider.next_action(make_context("明天有课吗"), budget())
    second = await provider.next_action(make_context("明天有课吗"), budget())
    assert isinstance(first, ToolCall) and isinstance(second, ToolCall)
    assert (first.tool_name, first.arguments) == (second.tool_name, second.arguments)


def test_save_marker_detection():
    assert mentions_save("帮我保存到我的计划")
    assert not mentions_save("这个计划怎么样")


@pytest.mark.parametrize(
    "tool, arguments",
    [
        ("delete_everything", {}),
        ("get_my_schedule", {"student_id": "usr_other"}),
        ("search_course_docs", {"query": ""}),
        ("search_course_docs", {"query": "x" * 2001}),
        ("save_study_plan", {"draft_id": "bad id", "draft_version": 1}),
        ("save_study_plan", {"draft_id": "dft_ok", "draft_version": 0}),
    ],
)
def test_tool_whitelist_rejects(tool: str, arguments: dict):
    with pytest.raises(ApiError):
        validate_tool_call(tool, arguments)


def test_tool_whitelist_normalizes_dates():
    normalized = validate_tool_call(
        "get_my_schedule", {"from_date": "2026-10-23", "to_date": "2026-10-24"}
    )
    assert normalized == {"from_date": "2026-10-23", "to_date": "2026-10-24"}
