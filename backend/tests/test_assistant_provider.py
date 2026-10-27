"""A1 车道测试：ModelGateway 契约、确定性 Provider 行为、工具参数白名单。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

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


async def test_natural_schedule_phrases_trigger_tool():
    """冒烟回归：口语化“明天有什么课/今天有什么课”必须触发 get_my_schedule。"""
    provider = DeterministicProvider()
    tomorrow = await provider.next_action(make_context("明天有什么课？"), budget())
    assert isinstance(tomorrow, ToolCall)
    assert tomorrow.tool_name == "get_my_schedule"
    assert tomorrow.arguments == {"from_date": "2026-10-24", "to_date": "2026-10-24"}

    today = await provider.next_action(make_context("今天有什么课"), budget())
    assert isinstance(today, ToolCall)
    assert today.arguments == {"from_date": "2026-10-23", "to_date": "2026-10-23"}

    for phrase in ("明天有课吗", "帮我看看课表", "这周课程安排", "下周一上什么课"):
        action = await provider.next_action(make_context(phrase), budget())
        assert isinstance(action, ToolCall) and action.tool_name == "get_my_schedule", phrase


async def test_docs_question_with_kejian_is_not_schedule():
    """“课件”类资料问题不得被口语课表关键词误触发。"""
    provider = DeterministicProvider()
    action = await provider.next_action(
        make_context("课件对实验课预习要求是什么？"), budget()
    )
    assert isinstance(action, ToolCall)
    assert action.tool_name == "search_course_docs"


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


async def test_retrieval_failure_is_not_reported_as_empty_result():
    """FR-QA-003：检索失败 ≠ 检索过但没找到，文案必须区分。"""
    from app.adapters.model.gateway import EvidenceSet, ToolExecutionRecord

    provider = DeterministicProvider()
    record = ToolExecutionRecord(
        tool_name="search_course_docs",
        arguments={"query": "期末成绩怎么算？"},
        success=False,
        result_status="failed",
        dependency_state="failed",
        code="MCP_UNAVAILABLE",
        payload={
            "status": "failed",
            "corpus_empty": False,
            "_evidence": EvidenceSet(status="ok", corpus_empty=False, revision=0),
        },
    )
    context = make_context("期末成绩怎么算？", tool_results=[record])
    action = await provider.next_action(context, budget())
    assert isinstance(action, Answer)
    assert "检索服务暂时不可用" in action.text
    assert "没有检索到可用的课程资料依据" not in action.text
    assert "还没有已发布的课程资料" not in action.text


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


async def test_conflicting_documents_are_listed_with_caveat():
    """FR-QA-004：多来源 + 判定类问法时要并列依据并提示可能不一致。"""
    from app.adapters.model.deterministic import DeterministicProvider
    from app.adapters.model.gateway import (
        EvidenceChunk,
        EvidenceReference,
        EvidenceSet,
        ToolExecutionRecord,
    )

    def _chunk(doc_id: str, ref_id: str, text: str) -> EvidenceChunk:
        return EvidenceChunk(
            chunk_id=f"chk_{ref_id}",
            reference_id=ref_id,
            document_id=doc_id,
            version_id=f"dvs_{doc_id}",
            text=text,
            location_label="第 1 段",
        )

    evidence = EvidenceSet(
        status="ok",
        corpus_empty=False,
        revision=3,
        chunks=(
            _chunk("doc_math_a", "cit_a", "考试范围包含级数；考试时长 90 分钟。"),
            _chunk("doc_math_b", "cit_b", "考试范围不包含级数：级数章节不考。"),
        ),
        references=(
            EvidenceReference(
                reference_id="cit_a",
                document_id="doc_math_a",
                version_id="dvs_doc_math_a",
                file_name="高等数学-期中考试说明.md",
                location_label="第 1 段",
            ),
            EvidenceReference(
                reference_id="cit_b",
                document_id="doc_math_b",
                version_id="dvs_doc_math_b",
                file_name="eval-conflict-math.txt",
                location_label="第 1 段",
            ),
        ),
    )
    record = ToolExecutionRecord(
        tool_name="search_course_docs",
        arguments={"query": "高数期中是否含级数"},
        success=True,
        result_status="ok",
        dependency_state="available",
        code=None,
        payload={
            "status": "ok",
            "corpus_empty": False,
            "_evidence": evidence,
        },
    )
    context = make_context("高数期中是否含级数", tool_results=[record])
    action = await DeterministicProvider().next_action(context, budget())

    assert isinstance(action, Answer)
    assert "可能不一致" in action.text
    # 两份来源都列出来（并列依据，不替用户挑一个）
    assert "高等数学-期中考试说明.md" in action.text
    assert "eval-conflict-math.txt" in action.text
    assert "没有检索到" not in action.text


# --------------------------------------------------------------------------- #
# AT-07：时区午夜边界 / 周日锚点 / 答案展示完整日期
# --------------------------------------------------------------------------- #
def test_school_date_midnight_boundary_in_school_timezone():
    """学校时区午夜切换：UTC 15:59:59 vs 16:00:00 必须落到不同业务日。"""
    from app.shared.clock import school_date

    assert school_date(datetime(2026, 10, 25, 15, 59, 59, tzinfo=timezone.utc)) == date(2026, 10, 25)
    assert school_date(datetime(2026, 10, 25, 16, 0, 0, tzinfo=timezone.utc)) == date(2026, 10, 26)


@pytest.mark.parametrize(
    ("today", "message", "expected"),
    [
        # 2026-10-25 是周日
        (date(2026, 10, 25), "明天有什么课", ("2026-10-26", "2026-10-26")),
        (date(2026, 10, 25), "下周一上什么课", ("2026-10-26", "2026-11-01")),
        (date(2026, 10, 25), "本周课程安排", ("2026-10-19", "2026-10-25")),
        # 2026-10-26 是周一：下周一必须是 11-02
        (date(2026, 10, 26), "下周一上什么课", ("2026-11-02", "2026-11-08")),
    ],
)
def test_schedule_range_sunday_and_weekday_anchors(today, message, expected):
    context = make_context(message, today=today, tomorrow=today + timedelta(days=1))
    assert schedule_range(context) == expected


async def test_schedule_answer_shows_full_dates():
    """AT-07：答案要展示完整日期（不是「今天/明天」这种相对说法）。"""
    from app.adapters.model.gateway import ToolExecutionRecord

    record = ToolExecutionRecord(
        tool_name="get_my_schedule",
        arguments={"from_date": "2026-10-26", "to_date": "2026-10-26"},
        success=True,
        result_status="ok",
        dependency_state="available",
        code=None,
        payload={
            "status": "ok",
            "from_date": "2026-10-26",
            "to_date": "2026-10-26",
            "items": [
                {
                    "class_date": "2026-10-26",
                    "start_time": "08:00",
                    "end_time": "09:40",
                    "course_name": "数据结构",
                    "location": "A-201",
                }
            ],
        },
    )
    action = await DeterministicProvider().next_action(
        make_context("明天有什么课", tool_results=[record]), budget()
    )
    assert isinstance(action, Answer)
    assert "2026-10-26" in action.text
    assert "数据结构" in action.text and "08:00-09:40" in action.text


# --------------------------------------------------------------------------- #
# AT-21：多步任务缺课表/缺资料时要说明缺口，且草稿不虚称已引用
# --------------------------------------------------------------------------- #
async def test_draft_states_missing_dependencies_without_claiming_citations():
    from app.adapters.model.gateway import EvidenceSet, ToolExecutionRecord

    def _record(tool_name: str, status: str, **payload) -> ToolExecutionRecord:
        return ToolExecutionRecord(
            tool_name=tool_name,
            arguments={},
            success=True,
            result_status=status,
            dependency_state="empty" if status == "empty" else "available",
            code=None,
            payload={"status": status, "_evidence": EvidenceSet(status="empty", corpus_empty=False, revision=0), **payload},
        )

    context = make_context(
        "先看看明天课表和课件要求，再帮我制定复习计划",
        tool_results=[
            _record("get_my_schedule", "empty", items=[], from_date="2026-10-24", to_date="2026-10-24"),
            _record("search_course_docs", "empty"),
        ],
    )
    action = await DeterministicProvider().next_action(context, budget())
    assert isinstance(action, DraftIntent)
    # 两处缺口都要明说
    assert "没有查到课程安排" in action.content
    assert "未检索到课程资料依据" in action.content
    # 不虚称已引用：没有任何「依据《…》」或「根据已发布的课程资料」
    assert "依据《" not in action.content
    assert "根据已发布的课程资料" not in action.content
    # 依据类型只有一般建议，不声称 documents/schedule
    assert action.basis_types == ("general",)
