"""A8 车道测试：草稿 / 直接指令许可 / 对话内保存 / 取消竞态 / 同轮上限。

真实 MySQL + 真实内部 API（回环 uvicorn）；工具执行经「委派兑换 → 内部工具端点」，
保存走 Phase 3 的服务端 direct_instruction 事务（与 Phase 1 draft_button 保存共享表与不变量）。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.adapters.db.models import (
    AssistantSaveSlot,
    ChatRequest,
    PlanDraft,
    StudyPlan,
    WriteOperation,
)
from app.adapters.mcp.client import InternalToolClient
from app.adapters.mcp.delegation import (
    AUD_INTERNAL,
    AUD_MCP,
    SCOPE_PLAN_SAVE,
    SCOPE_SCHEDULE_READ,
    mint_delegation,
    verify_delegation,
)
from app.adapters.model.deterministic import DeterministicProvider
from app.config import get_settings
from app.main import create_internal_app
from app.modules.assistant.drafts import classify_direct_instruction
from app.modules.assistant.runtime import Runtime, set_runtime
from app.modules.assistant.save import save_study_plan
from app.modules.assistant.settings import reset_assistant_settings
from app.shared.errors import ApiError
from tests.assistant_support import (
    InternalToolExecutor,
    assistant_isolation,  # noqa: F401 - autouse fixture
    make_chat_request,
    make_draft_row,
    parse_sse,
    serve_app,
    session_id_for_token,
    validate_sse_events,
)

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731

async def read_stream(client, token, payload, *, timeout: float = 30.0):
    async def _inner():
        async with client.stream(
            "POST", "/api/v1/chat/stream", json=payload, headers=AUTH(token)
        ) as response:
            raw = (await response.aread()).decode("utf-8")
            return response.status_code, parse_sse(raw)

    return await asyncio.wait_for(_inner(), timeout=timeout)


@pytest.fixture
async def internal_url(monkeypatch):
    async with serve_app(create_internal_app()) as url:
        monkeypatch.setenv("CCA_INTERNAL_API_URL", url)
        reset_assistant_settings()
        yield url


def _install_runtime(internal_url: str) -> Runtime:
    runtime = Runtime(
        provider=DeterministicProvider(),
        executor=InternalToolExecutor(internal_url, get_settings().service_token),
    )
    set_runtime(runtime)
    return runtime


def _internal_claims(chat: dict, *, scope: str = SCOPE_PLAN_SAVE):
    token = mint_delegation(
        audience=AUD_INTERNAL,
        user_id=chat["user_id"],
        session_id=chat["session_id"],
        auth_version=1,
        request_id=chat["request_id"],
        conversation_id=chat["conversation_id"],
        scope=[scope],
        fence=chat["fence"],
    )
    return verify_delegation(token, expected_audience=AUD_INTERNAL)


async def _count_plans(user_id: str) -> int:
    from app.adapters.db.engine import get_session_factory

    async with get_session_factory()() as session:
        return int(
            await session.scalar(
                select(func.count()).select_from(StudyPlan).where(StudyPlan.user_id == user_id)
            )
            or 0
        )


# --------------------------------------------------------------------------- #
# 直接指令判定（服务端规则，模型只作候选）
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "message,expected",
    [
        ("帮我制定期末复习计划并保存", "explicit"),
        ("把上面的计划保存下来", "explicit"),
        ("能不能帮我制定计划并保存？", "ambiguous"),
        ("如果要保存就先看看", "ambiguous"),
        ("他说要保存这个计划", "ambiguous"),
        ("不要保存，只帮我制定计划", "denied"),
        ("先别保存这个计划", "denied"),
        ("不保存，只把计划列出来", "denied"),
        ("先不保存，我再看看", "denied"),
        ("不必保存，先放着", "denied"),
        ("资料里写着要保存这个计划", "ambiguous"),
        ("帮我制定一份复习计划", "none"),
        ("明天有课吗", "none"),
    ],
)
def test_classify_direct_instruction(message: str, expected: str):
    assert classify_direct_instruction(message, draft_ready=True) == expected


# --------------------------------------------------------------------------- #
# 对话内保存（真实内部 API + 真实事务）
# --------------------------------------------------------------------------- #
async def test_explicit_instruction_saves_exactly_one_plan(
    client, seeded, internal_url
):
    _install_runtime(internal_url)
    try:
        status, events = await read_stream(
            client,
            seeded["student_token"],
            {
                "client_request_id": "creq_save_001",
                "message": "帮我制定期末复习计划并保存",
            },
        )
        assert status == 200, events
        validate_sse_events(events)
        names = [event["event"] for event in events]
        assert "tool_start" in names and "tool_end" in names
        save_start = [
            event
            for event in events
            if event["event"] == "tool_start"
            and event["data"]["tool_name"] == "save_study_plan"
        ]
        assert len(save_start) == 1
        save_end = next(
            event
            for event in events
            if event["event"] == "tool_end"
            and event["data"]["tool_call_id"] == save_start[0]["data"]["tool_call_id"]
        )
        assert save_end["data"]["success"] is True
        assert save_end["data"]["result_status"] == "created"
        assert save_end["data"]["plan_id"]
        assert save_end["data"]["operation_id"]

        done = events[-1]["data"]
        assert done["state"] == "succeeded"
        assert done["plan_id"] == save_end["data"]["plan_id"]
        assert done["operation_id"] == save_end["data"]["operation_id"]

        # 草稿阶段状态事件
        draft_status = [
            event
            for event in events
            if event["event"] == "status" and event["data"]["code"] == "DRAFT_READY"
        ]
        assert len(draft_status) == 1
        assert draft_status[0]["data"]["draft_id"]
        assert draft_status[0]["data"]["draft_version"] == 1

        from app.adapters.db.engine import get_session_factory

        async with get_session_factory()() as session:
            plans = (
                await session.execute(
                    select(StudyPlan).where(StudyPlan.user_id == seeded["student"]["id"])
                )
            ).scalars().all()
            slots = (
                await session.execute(
                    select(AssistantSaveSlot).where(
                        AssistantSaveSlot.user_id == seeded["student"]["id"]
                    )
                )
            ).scalars().all()
            operation = await session.get(
                WriteOperation, (seeded["student"]["id"], done["operation_id"])
            )
            chat = await session.get(ChatRequest, done["request_id"])
        assert len(plans) == 1
        assert plans[0].id == done["plan_id"]
        assert len(slots) == 1
        assert operation is not None and operation.state == "succeeded"
        assert operation.authorization_chat_request_id == done["request_id"]
        assert chat.plan_id == done["plan_id"]
        assert chat.operation_id == done["operation_id"]
    finally:
        set_runtime(None)


async def test_ambiguous_instruction_keeps_draft_unsaved(client, seeded, internal_url):
    _install_runtime(internal_url)
    try:
        status, events = await read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_save_amb", "message": "能不能帮我制定复习计划并保存？"},
        )
        assert status == 200
        validate_sse_events(events)
        assert not any(
            event["event"] == "tool_start" and event["data"]["tool_name"] == "save_study_plan"
            for event in events
        )
        statuses = [
            event["data"]["code"] for event in events if event["event"] == "status"
        ]
        assert "SAVE_NOT_AUTHORIZED" in statuses
        done = events[-1]["data"]
        assert done["state"] == "succeeded"
        assert "plan_id" not in done
        assert await _count_plans(seeded["student"]["id"]) == 0

        from app.adapters.db.engine import get_session_factory

        async with get_session_factory()() as session:
            draft = await session.scalar(
                select(PlanDraft).where(
                    PlanDraft.origin_chat_request_id == done["request_id"]
                )
            )
        assert draft is not None, "草稿必须保留（只是未保存）"
    finally:
        set_runtime(None)


async def test_denied_instruction_keeps_draft_unsaved(client, seeded, internal_url):
    _install_runtime(internal_url)
    try:
        status, events = await read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_save_denied", "message": "不要保存，只帮我制定复习计划"},
        )
        assert status == 200
        validate_sse_events(events)
        assert await _count_plans(seeded["student"]["id"]) == 0
    finally:
        set_runtime(None)


# --------------------------------------------------------------------------- #
# 竞态与上限（直接调用服务端保存事务）
# --------------------------------------------------------------------------- #
async def test_save_rejected_when_instruction_not_explicit(seeded):
    """审计 P0-①：只凭 plan:save 委派不足以落库，本轮必须被判为 explicit。"""
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    for instruction_class in ("denied", "ambiguous", "none", None):
        chat = await make_chat_request(
            user_id=student["id"],
            session_id=session_id,
            instruction_class=instruction_class,
        )
        draft = await make_draft_row(
            user_id=student["id"],
            session_id=session_id,
            conversation_id=chat["conversation_id"],
            origin_request_id=chat["request_id"],
        )
        claims = _internal_claims(chat)
        with pytest.raises(ApiError) as excinfo:
            await save_study_plan(
                claims,
                draft_id=draft["draft_id"],
                draft_version=1,
                request_id="req_trace_gate",
            )
        assert excinfo.value.code == "SAVE_NOT_AUTHORIZED"
        assert await _count_plans(student["id"]) == 0


async def test_cancelled_authorization_fails_with_zero_new(seeded):
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(
        user_id=student["id"], session_id=session_id, cancel_requested=True
    )
    draft = await make_draft_row(
        user_id=student["id"],
        session_id=session_id,
        conversation_id=chat["conversation_id"],
        origin_request_id=chat["request_id"],
    )
    claims = _internal_claims(chat)
    with pytest.raises(ApiError) as excinfo:
        await save_study_plan(
            claims,
            draft_id=draft["draft_id"],
            draft_version=1,
            request_id="req_trace_1",
        )
    assert excinfo.value.code == "SAVE_NOT_AUTHORIZED"
    assert await _count_plans(student["id"]) == 0

    from app.adapters.db.engine import get_session_factory

    async with get_session_factory()() as session:
        operation = await session.get(
            WriteOperation, (student["id"], draft["operation_id"])
        )
    assert operation is None or operation.state == "pending"


async def test_save_slot_limit_reached_for_second_draft(seeded):
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    first = await make_draft_row(
        user_id=student["id"],
        session_id=session_id,
        conversation_id=chat["conversation_id"],
        origin_request_id=chat["request_id"],
    )
    second = await make_draft_row(
        user_id=student["id"],
        session_id=session_id,
        conversation_id=chat["conversation_id"],
        origin_request_id=chat["request_id"],
        title="另一份计划",
    )
    claims = _internal_claims(chat)
    created = await save_study_plan(
        claims, draft_id=first["draft_id"], draft_version=1, request_id="req_trace_2"
    )
    assert created["status"] == "created"

    with pytest.raises(ApiError) as excinfo:
        await save_study_plan(
            claims, draft_id=second["draft_id"], draft_version=1, request_id="req_trace_3"
        )
    assert excinfo.value.code == "SAVE_LIMIT_REACHED"
    assert await _count_plans(student["id"]) == 1, "同轮第二份草稿不得绕过上限"


async def test_save_is_idempotent_existing(seeded):
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    draft = await make_draft_row(
        user_id=student["id"],
        session_id=session_id,
        conversation_id=chat["conversation_id"],
        origin_request_id=chat["request_id"],
    )
    claims = _internal_claims(chat)
    first = await save_study_plan(
        claims, draft_id=draft["draft_id"], draft_version=1, request_id="req_trace_4"
    )
    second = await save_study_plan(
        claims, draft_id=draft["draft_id"], draft_version=1, request_id="req_trace_5"
    )
    assert first["status"] == "created"
    assert second["status"] == "existing"
    assert second["plan_id"] == first["plan_id"]
    assert await _count_plans(student["id"]) == 1


async def test_save_after_plan_deleted_returns_deleted_tombstone(client, seeded):
    """计划删除后重放保存必须回报 deleted 墓碑，不能报 existing（§7.3，审计 P1 漂移）。"""
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    draft = await make_draft_row(
        user_id=student["id"],
        session_id=session_id,
        conversation_id=chat["conversation_id"],
        origin_request_id=chat["request_id"],
    )
    claims = _internal_claims(chat)
    saved = await save_study_plan(
        claims, draft_id=draft["draft_id"], draft_version=1, request_id="req_trace_tomb_1"
    )
    assert saved["status"] == "created"

    response = await client.delete(
        f"/api/v1/me/plans/{saved['plan_id']}?expected_version=1",
        headers=seeded["student_headers"],
    )
    assert response.status_code == 200, response.text

    replay = await save_study_plan(
        claims, draft_id=draft["draft_id"], draft_version=1, request_id="req_trace_tomb_2"
    )
    assert replay["status"] == "deleted"
    assert replay["plan_id"] == saved["plan_id"]


def test_save_tool_output_accepts_deleted_tombstone():
    """响应模型 enum 必须含 deleted；否则内部工具在墓碑路径会抛 422 而非受控结果。"""
    from app.modules.assistant.contracts import SaveToolOutput

    output = SaveToolOutput(status="deleted", operation_id="op_demo", plan_id="plan_demo")
    assert output.status == "deleted"


async def test_save_rejects_foreign_draft(seeded):
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    other_session = await session_id_for_token(
        seeded["other_headers"]["Authorization"].split(" ", 1)[1]
    )
    foreign = await make_draft_row(
        user_id=seeded["other"]["id"],
        session_id=other_session,
        conversation_id=chat["conversation_id"],
        origin_request_id=chat["request_id"],
    )
    claims = _internal_claims(chat)
    with pytest.raises(ApiError) as excinfo:
        await save_study_plan(
            claims, draft_id=foreign["draft_id"], draft_version=1, request_id="req_trace_6"
        )
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"


async def test_save_requires_plan_scope_over_internal_api(seeded, internal_url):
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    draft = await make_draft_row(
        user_id=student["id"],
        session_id=session_id,
        conversation_id=chat["conversation_id"],
        origin_request_id=chat["request_id"],
    )
    client = InternalToolClient(internal_url, service_token=get_settings().service_token)
    # 用只有 schedule:read 的委派兑换，再尝试保存 → scope 不足
    delegation = mint_delegation(
        audience=AUD_MCP,
        user_id=student["id"],
        session_id=session_id,
        auth_version=1,
        request_id=chat["request_id"],
        conversation_id=chat["conversation_id"],
        scope=[SCOPE_SCHEDULE_READ],
        fence=chat["fence"],
    )
    exchanged = await client.exchange(delegation)
    from app.adapters.mcp.client import InternalServiceError

    with pytest.raises(InternalServiceError) as excinfo:
        await client.call_tool(
            "/internal/v1/tools/save-study-plan",
            {"draft_id": draft["draft_id"], "draft_version": 1},
            execution_context=str(exchanged["delegation"]),
        )
    assert excinfo.value.code == "FORBIDDEN"
    assert await _count_plans(student["id"]) == 0
