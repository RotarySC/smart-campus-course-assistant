"""FR-QA-004 / AT-23：同名课程先补问（歧义与冲突）。

覆盖四层：
1. 纯函数判定（课程目录 + 问题文本 → 候选）：同名、唯一、已报代码、最长匹配、单字名；
2. 服务端查库判定（``lookup_ambiguous_courses``）走真实课程目录；
3. 确定性 Provider：拿到候选就**先补问**，不发起注定混淆的检索；
4. 端到端 SSE：同名课程提问 → 无 tool_start、回答是补问、无引用。
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.adapters.model.deterministic import DeterministicProvider
from app.adapters.model.gateway import (
    AmbiguousCourse,
    Answer,
    ModelBudget,
    ModelContext,
    ToolCall,
)
from app.modules.assistant.clarify import ambiguous_candidates, lookup_ambiguous_courses
from app.modules.assistant.runtime import Runtime, set_runtime
from tests.assistant_support import (
    StubToolExecutor,
    assistant_isolation,  # noqa: F401 - autouse fixture
    parse_sse,
    validate_sse_events,
)

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731 - 测试简写

DEFAULT_ACCEPTED_AT = "2026-10-23T15:30:00+00:00"


def _accepted_at():
    from datetime import datetime

    return datetime.fromisoformat(DEFAULT_ACCEPTED_AT)


def make_context(message: str, *, ambiguous: tuple[AmbiguousCourse, ...] = ()) -> ModelContext:
    from datetime import date

    return ModelContext(
        request_id="req_clarify_1",
        conversation_id="cnv_clarify_1",
        message=message,
        history=(),
        accepted_at=_accepted_at(),
        school_timezone="Asia/Shanghai",
        today=date(2026, 10, 23),
        tomorrow=date(2026, 10, 24),
        ambiguous_courses=ambiguous,
    )


def budget() -> ModelBudget:
    from datetime import datetime, timedelta

    return ModelBudget(
        remaining_decisions=6,
        remaining_tools=10,
        deadline_at=_accepted_at() + timedelta(minutes=1),
    )


# --------------------------------------------------------------------------- #
# 1) 纯函数判定
# --------------------------------------------------------------------------- #
CATALOG = [
    ("MATH101", "高等数学"),
    ("MATH102", "高等数学"),
    ("CS101", "数据结构"),
    ("XX1", "数学"),
    ("Y1", "数"),
    ("Y2", "数"),
]


def test_two_courses_share_name_need_clarification():
    candidates = ambiguous_candidates("高等数学的评分要求是什么？", CATALOG)
    assert [(item.code, item.name) for item in candidates] == [
        ("MATH101", "高等数学"),
        ("MATH102", "高等数学"),
    ]


def test_unique_course_name_needs_no_clarification():
    assert ambiguous_candidates("数据结构的评分要求是什么？", CATALOG) == ()


def test_explicit_course_code_counts_as_resolved():
    assert ambiguous_candidates("MATH102 的评分要求是什么？", CATALOG) == ()
    assert ambiguous_candidates("math102 的评分要求是什么？", CATALOG) == ()


def test_longest_course_name_wins():
    # 「数学」也是课程名，但问题里的「高等数学」更长，更具体
    candidates = ambiguous_candidates("高等数学难吗", CATALOG)
    assert {item.name for item in candidates} == {"高等数学"}


def test_single_character_name_is_not_a_course_hit():
    assert ambiguous_candidates("数的要求是什么？", CATALOG) == ()


def test_unrelated_question_has_no_candidates():
    assert ambiguous_candidates("帮我制定一个复习计划", CATALOG) == ()
    assert ambiguous_candidates("", CATALOG) == ()


# --------------------------------------------------------------------------- #
# 2) 服务端查库（真实课程目录）
# --------------------------------------------------------------------------- #
async def _add_same_name_course(client, seeded, *, code: str, name: str) -> None:
    response = await client.post(
        "/api/v1/admin/courses",
        json={"code": code, "name": name},
        headers=seeded["admin_headers"],
    )
    assert response.status_code == 201, response.text


async def test_lookup_finds_candidates_from_real_catalog(client, seeded):
    # seeded 已有一门 CS101「数据结构」；再加一门同名的 CS102
    await _add_same_name_course(client, seeded, code="CS102", name="数据结构")

    candidates = await lookup_ambiguous_courses("数据结构的评分要求是什么？")
    assert {item.code for item in candidates} == {"CS101", "CS102"}
    assert {item.name for item in candidates} == {"数据结构"}

    # 用户直接报了代码 → 不再补问
    assert await lookup_ambiguous_courses("CS102 的评分要求是什么？") == ()
    # 唯一课程名 → 不补问
    assert await lookup_ambiguous_courses("线性代数的评分要求是什么？") == ()


# --------------------------------------------------------------------------- #
# 3) 确定性 Provider：先补问、不检索
# --------------------------------------------------------------------------- #
async def test_provider_asks_before_searching_when_course_name_is_ambiguous():
    provider = DeterministicProvider()
    ambiguous = (
        AmbiguousCourse(code="MATH101", name="高等数学"),
        AmbiguousCourse(code="MATH102", name="高等数学"),
    )
    action = await provider.next_action(
        make_context("高等数学的评分要求是什么？", ambiguous=ambiguous), budget()
    )

    assert isinstance(action, Answer), "同名课程必须先补问，不能直接检索后混答"
    assert "高等数学" in action.text
    assert "MATH101" in action.text and "MATH102" in action.text
    assert "请先告诉我要看哪一门" in action.text
    # 没有检索就不可能给出资料依据
    assert "根据已发布的课程资料" not in action.text
    assert "general" in action.basis_types and "documents" not in action.basis_types


async def test_provider_still_searches_when_no_ambiguity():
    provider = DeterministicProvider()
    action = await provider.next_action(
        make_context("数据结构的评分要求是什么？"), budget()
    )
    assert isinstance(action, ToolCall)
    assert action.tool_name == "search_course_docs"


# --------------------------------------------------------------------------- #
# 4) 端到端 SSE
# --------------------------------------------------------------------------- #
async def read_stream(client, token: str, payload: dict[str, Any], *, timeout: float = 40.0):
    async def _inner():
        async with client.stream(
            "POST", "/api/v1/chat/stream", json=payload, headers=AUTH(token)
        ) as response:
            raw = (await response.aread()).decode("utf-8")
            return response.status_code, parse_sse(raw)

    return await asyncio.wait_for(_inner(), timeout=timeout)


async def test_e2e_same_name_course_asks_and_has_no_citations(client, seeded):
    await _add_same_name_course(client, seeded, code="CS102", name="数据结构")

    runtime = Runtime(provider=DeterministicProvider(), executor=StubToolExecutor())
    set_runtime(runtime)
    try:
        status, events = await read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_clarify_001", "message": "数据结构的评分要求是什么？"},
        )
    finally:
        set_runtime(None)

    assert status == 200, events
    validate_sse_events(events)

    # 先补问：不发起检索，也就没有伪依据
    assert not [event for event in events if event["event"] == "tool_start"]
    text = "".join(
        event["data"]["text_delta"] for event in events if event["event"] == "token"
    )
    assert "请先告诉我要看哪一门" in text
    assert "CS101" in text and "CS102" in text

    done = events[-1]
    assert done["event"] == "done"
    assert done["data"]["state"] == "succeeded"
    assert done["data"]["citations"] == []


async def test_e2e_empty_corpus_points_to_admin(client, seeded):
    """FR-QA-004 第三句：全库为空时要提示管理员尚未提供材料。"""
    runtime = Runtime(provider=DeterministicProvider(), executor=StubToolExecutor())
    # StubToolExecutor 默认返回有依据；改成「检索成功但库为空」
    runtime.executor.corpus_empty = True
    set_runtime(runtime)
    try:
        status, events = await read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_empty_001", "message": "评分要求是什么？"},
        )
    finally:
        set_runtime(None)

    assert status == 200, events
    validate_sse_events(events)
    text = "".join(
        event["data"]["text_delta"] for event in events if event["event"] == "token"
    )
    assert "还没有已发布的课程资料" in text
    assert "管理员" in text
