"""A6 车道测试：预算（6 决策/10 工具）、60s 截止、租约回收、fence 防旧 runner 提交。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.adapters.db.models import AICapacitySlot, ChatRequest
from app.adapters.model.deterministic import DeterministicProvider
from app.adapters.model.gateway import ToolCall
from app.modules.assistant.accept import recover_stale_requests
from app.modules.assistant.runtime import Runtime, set_runtime
from app.modules.assistant.settings import reset_assistant_settings
from app.shared.clock import FixedClock, set_clock
from tests.assistant_support import (
    StubToolExecutor,
    assert_sse_invariants,
    assistant_isolation,  # noqa: F401 - autouse fixture
    make_chat_request,
    parse_sse,
    validate_sse_events,
    wait_for_request_state,
)

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731


class AlwaysScheduleProvider:
    """永远请求课表工具：用于把决策/工具预算打满。"""

    name = "always-schedule"

    async def next_action(self, context, budget):
        return ToolCall(tool_name="get_my_schedule", arguments={})

    async def stream_answer(self, answer, emit):  # pragma: no cover - 不会走到
        await emit(answer.text)


async def read_stream(client, token, payload, *, timeout: float = 25.0):
    async def _inner():
        async with client.stream(
            "POST", "/api/v1/chat/stream", json=payload, headers=AUTH(token)
        ) as response:
            raw = (await response.aread()).decode("utf-8")
            return response.status_code, parse_sse(raw)

    return await asyncio.wait_for(_inner(), timeout=timeout)


def _runtime(provider, *, env: dict[str, str] | None = None) -> Runtime:
    reset_assistant_settings()
    runtime = Runtime(provider=provider, executor=StubToolExecutor())
    return runtime


@pytest.fixture
def decision_limited(monkeypatch):
    monkeypatch.setenv("CCA_ASSISTANT_MODEL_DECISIONS", "2")
    runtime = _runtime(AlwaysScheduleProvider())
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


@pytest.fixture
def tool_limited(monkeypatch):
    monkeypatch.setenv("CCA_ASSISTANT_MODEL_DECISIONS", "50")
    monkeypatch.setenv("CCA_ASSISTANT_TOOL_CALLS", "2")
    runtime = _runtime(AlwaysScheduleProvider())
    set_runtime(runtime)
    yield runtime
    set_runtime(None)


async def test_decision_budget_stops_with_call_limit(client, seeded, decision_limited):
    status, events = await read_stream(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_budget_dec", "message": "复习计划"},
    )
    assert status == 200
    validate_sse_events(events)
    assert_sse_invariants(events)
    terminal = events[-1]
    assert terminal["event"] == "error"
    assert terminal["data"]["state"] == "failed"
    assert terminal["data"]["code"] == "CALL_LIMIT_REACHED"

    from app.adapters.db.engine import get_session_factory

    async with get_session_factory()() as session:
        row = await session.get(ChatRequest, terminal["data"]["request_id"])
    assert row.model_calls == 2
    assert row.state == "failed"
    assert row.terminal_reason == "CALL_LIMIT_REACHED"


async def test_tool_budget_stops_with_call_limit(client, seeded, tool_limited):
    status, events = await read_stream(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_budget_tool", "message": "明天课表"},
    )
    assert status == 200
    validate_sse_events(events)
    terminal = events[-1]
    assert terminal["event"] == "error"
    assert terminal["data"]["code"] == "CALL_LIMIT_REACHED"
    tool_ends = [event for event in events if event["event"] == "tool_end"]
    assert len(tool_ends) == 2
    from app.adapters.db.engine import get_session_factory

    async with get_session_factory()() as session:
        row = await session.get(ChatRequest, terminal["data"]["request_id"])
    assert row.tool_calls == 2


class AdvancingProvider:
    """第一次决策后把可注入时钟推进 61 秒，触发 60s 截止。"""

    def __init__(self, clock: FixedClock) -> None:
        self._inner = DeterministicProvider()
        self._clock = clock
        self._advanced = False

    async def next_action(self, context, budget):
        if not self._advanced:
            self._advanced = True
            self._clock.advance(61)
        return await self._inner.next_action(context, budget)

    async def stream_answer(self, answer, emit):
        await self._inner.stream_answer(answer, emit)


async def test_deadline_produces_execution_timeout(client, seeded, monkeypatch):
    clock = FixedClock(datetime.now(timezone.utc))
    set_clock(clock)
    runtime = _runtime(AdvancingProvider(clock))
    set_runtime(runtime)
    try:
        status, events = await read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_deadline", "message": "明天有课吗"},
        )
        assert status == 200
        validate_sse_events(events)
        terminal = events[-1]
        assert terminal["event"] == "error"
        assert terminal["data"]["code"] == "EXECUTION_TIMEOUT"
        from app.adapters.db.engine import get_session_factory

        async with get_session_factory()() as session:
            row = await session.get(ChatRequest, terminal["data"]["request_id"])
        assert row.state == "failed"
        assert row.terminal_reason == "EXECUTION_TIMEOUT"
    finally:
        set_runtime(None)


async def test_recovery_marks_stale_request_and_frees_slot(seeded):
    student = seeded["student"]
    session_id = None

    from tests.assistant_support import session_id_for_token

    session_id = await session_id_for_token(seeded["student_token"])
    stale = await make_chat_request(
        user_id=student["id"],
        session_id=session_id,
        state="running",
        lease_seconds=-5,  # 已过期租约
    )

    from app.adapters.db.engine import get_session_factory
    from app.shared.clock import now_utc, to_db

    async with get_session_factory()() as session:
        slot = await session.get(AICapacitySlot, 1)
        slot.request_id = stale["request_id"]
        slot.fence = 1
        slot.lease_until = to_db(now_utc() - timedelta(seconds=30))
        await session.commit()

    recovered = await recover_stale_requests()
    assert recovered == 1

    async with get_session_factory()() as session:
        row = await session.get(ChatRequest, stale["request_id"])
        slot = await session.get(AICapacitySlot, 1)
    assert row.state == "failed"
    assert row.terminal_reason == "SERVICE_RESTARTED"
    assert int(row.fence) == stale["fence"] + 1
    assert slot.request_id is None, "回收后必须释放 AI 容量槽"


async def test_fence_loss_prevents_stale_runner_commit(client, seeded):
    from tests.assistant_support import GatedProvider

    provider = GatedProvider()
    runtime = Runtime(provider=provider, executor=StubToolExecutor())
    set_runtime(runtime)
    try:
        stream_task = asyncio.create_task(
            read_stream(
                client,
                seeded["student_token"],
                {"client_request_id": "creq_fence", "message": "明天有课吗"},
            )
        )
        running = await wait_for_request_state(seeded["student"]["id"], ("running",))

        # 模拟恢复器接管：递增 fence + 终结该请求（旧 runner 必须停止提交）
        from app.adapters.db.engine import get_session_factory
        from app.shared.clock import now_utc, to_db

        async with get_session_factory()() as session:
            row = await session.get(ChatRequest, running["request_id"])
            row.fence = int(row.fence) + 1
            row.state = "failed"
            row.terminal_reason = "SERVICE_RESTARTED"
            row.finished_at = to_db(now_utc())
            await session.commit()

        provider.gate.set()
        status, events = await asyncio.wait_for(stream_task, timeout=25)
        assert status == 200
        terminal = [event for event in events if event["event"] in ("done", "error")]
        assert terminal == [], "丢失 fence 的旧 runner 不得发终态"

        async with get_session_factory()() as session:
            row = await session.get(ChatRequest, running["request_id"])
        assert row.state == "failed"
        assert row.terminal_reason == "SERVICE_RESTARTED"
    finally:
        set_runtime(None)
