"""A5/A7 车道测试：接受/去重/单活动轮/容量 + SSE 六类事件 + 状态/取消。

真实 MySQL + httpx ASGI 流式客户端；工具执行注入 StubToolExecutor（不依赖网络），
MCP 的真实双跳链路已由 ``test_mcp_server.py`` 覆盖。
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, text

from app.adapters.db.models import AICapacitySlot, ChatRequest
from app.modules.assistant.runtime import Runtime, get_runtime, set_runtime
from app.modules.assistant.settings import get_assistant_settings
from tests.assistant_support import (
    GatedProvider,
    StubToolExecutor,
    assert_sse_invariants,
    assistant_isolation,  # noqa: F401 - autouse fixture
    make_chat_request,
    parse_sse,
    serve_app,  # noqa: F401 - re-exported for parity
    session_id_for_token,
    validate_sse_events,
    wait_for_request_state,
)

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731 - 测试简写


async def read_stream(
    client,
    token: str,
    payload: dict[str, Any],
    *,
    timeout: float = 25.0,
) -> tuple[int, list[dict[str, Any]], str]:
    """跑完 POST /chat/stream，返回 (HTTP 状态, 解析后事件, 原始文本)。"""

    async def _inner() -> tuple[int, list[dict[str, Any]], str]:
        async with client.stream(
            "POST", "/api/v1/chat/stream", json=payload, headers=AUTH(token)
        ) as response:
            raw = (await response.aread()).decode("utf-8")
            return response.status_code, parse_sse(raw), raw

    return await asyncio.wait_for(_inner(), timeout=timeout)


async def post_chat(client, token: str, payload: dict[str, Any]):
    return await client.post("/api/v1/chat/stream", json=payload, headers=AUTH(token))


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def runtime_fixture():
    executor = StubToolExecutor()
    runtime = Runtime(
        provider=GatedProvider(),
        executor=executor,
        settings=get_assistant_settings(),
    )
    set_runtime(runtime)
    yield runtime, executor
    set_runtime(None)


# --------------------------------------------------------------------------- #
# A7：SSE 六类事件 + schema + 终态唯一
# --------------------------------------------------------------------------- #
async def test_stream_schedule_turn_emits_schema_valid_events(client, seeded, runtime_fixture):
    runtime, executor = runtime_fixture
    runtime.provider.gate.set()

    status, events, _raw = await read_stream(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_stream_001", "message": "明天有课吗"},
    )
    assert status == 200, events
    validate_sse_events(events)
    assert_sse_invariants(events)

    names = [event["event"] for event in events]
    assert names[0] == "status"
    assert "tool_start" in names and "tool_end" in names
    assert names.count("done") == 1
    assert names[-1] == "done"
    assert "token" in names

    tool_start = next(event for event in events if event["event"] == "tool_start")
    assert tool_start["data"]["tool_name"] == "get_my_schedule"
    tool_end = next(event for event in events if event["event"] == "tool_end")
    assert tool_end["data"]["success"] is True
    assert tool_end["data"]["result_status"] == "ok"

    done = events[-1]["data"]
    assert done["state"] == "succeeded"
    assert done["citations"] == []
    request_id = done["request_id"]

    # 状态接口：本人可见、终态一致
    state_response = await client.get(
        f"/api/v1/chat/requests/{request_id}", headers=AUTH(seeded["student_token"])
    )
    assert state_response.status_code == 200
    state = state_response.json()["data"]
    assert state["state"] == "succeeded"
    assert state["model_calls"] >= 1
    assert state["tool_calls"] == 1
    assert state["finished_at"]
    assert state["request_id"] == request_id

    # 容量槽已释放、活动会话已清空
    from app.adapters.db.engine import get_session_factory

    async with get_session_factory()() as session:
        slot = await session.scalar(
            select(AICapacitySlot).where(AICapacitySlot.request_id == request_id)
        )
        row = await session.get(ChatRequest, request_id)
        active = await session.scalar(
            text("SELECT active_request_id FROM conversation_states WHERE id = :cid"),
            {"cid": row.conversation_id},
        )
    assert slot is None, "终态后必须释放 AI 容量槽"
    assert active in (None, "")


async def test_natural_schedule_phrase_emits_tool_start_with_date_anchor(
    client, seeded, runtime_fixture
):
    """冒烟回归：'明天有什么课？' 必须触发 get_my_schedule，日期锚点为明天。"""
    runtime, executor = runtime_fixture
    runtime.provider.gate.set()

    status, events, _ = await read_stream(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_schedule_natural", "message": "明天有什么课？"},
    )
    assert status == 200
    validate_sse_events(events)
    assert_sse_invariants(events)
    starts = [
        event
        for event in events
        if event["event"] == "tool_start"
        and event["data"]["tool_name"] == "get_my_schedule"
    ]
    assert len(starts) == 1, [event["event"] for event in events]
    ends = [
        event
        for event in events
        if event["event"] == "tool_end"
        and event["data"]["tool_call_id"] == starts[0]["data"]["tool_call_id"]
    ]
    assert len(ends) == 1 and ends[0]["data"]["success"] is True

    schedule_calls = [
        call for call in executor.calls if call.tool_name == "get_my_schedule"
    ]
    assert len(schedule_calls) == 1
    from app.shared.clock import school_date

    tomorrow = (school_date() + timedelta(days=1)).isoformat()
    assert schedule_calls[0].arguments == {
        "from_date": tomorrow,
        "to_date": tomorrow,
    }


async def test_stream_docs_turn_returns_citations(client, seeded, runtime_fixture):
    runtime, _ = runtime_fixture
    runtime.provider.gate.set()
    status, events, _ = await read_stream(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_docs_001", "message": "课件对实验报告有什么要求"},
    )
    assert status == 200
    validate_sse_events(events)
    assert_sse_invariants(events)
    done = events[-1]["data"]
    assert done["state"] == "succeeded"
    assert len(done["citations"]) == 1
    citation = done["citations"][0]
    assert citation["reference_id"] == "cit_fixture_1"
    assert citation["file_name"] == "课程大纲.txt"
    token_text = "".join(
        event["data"]["text_delta"] for event in events if event["event"] == "token"
    )
    assert "课程大纲.txt" in token_text


# --------------------------------------------------------------------------- #
# A5：去重 / 单活动轮 / 容量
# --------------------------------------------------------------------------- #
async def test_duplicate_client_request_id_returns_409_with_original(client, seeded, runtime_fixture):
    runtime, _ = runtime_fixture
    runtime.provider.gate.set()
    first_status, first_events, _ = await read_stream(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_dup_001", "message": "明天有课吗"},
    )
    assert first_status == 200
    original_request_id = first_events[-1]["data"]["request_id"]

    response = await post_chat(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_dup_001", "message": "换一个问题"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "REQUEST_ALREADY_EXISTS"
    assert body["error"]["details"]["request_id"] == original_request_id
    assert body["error"]["details"]["status_endpoint"].endswith(original_request_id)


async def test_second_turn_while_running_returns_chat_in_progress(client, seeded, runtime_fixture):
    runtime, _ = runtime_fixture
    student = seeded["student"]
    gate = runtime.provider.gate  # 未放行 → 第一轮保持 running

    stream_task = asyncio.create_task(
        read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_active_001", "message": "明天有课吗"},
        )
    )
    running = await wait_for_request_state(student["id"], ("accepted", "running"))

    response = await post_chat(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_active_002", "message": "再来一轮"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "CHAT_IN_PROGRESS"
    assert body["error"]["details"]["request_id"] == running["request_id"]

    gate.set()
    status, events, _ = await asyncio.wait_for(stream_task, timeout=25)
    assert status == 200
    assert events[-1]["event"] == "done"


async def test_capacity_limit_and_release(client, seeded, runtime_fixture, login):
    runtime, _ = runtime_fixture
    runtime.provider.gate.set()
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])

    # 直接占满 5 个容量槽（每个绑定一条运行中的 ChatRequest）
    from app.adapters.db.engine import get_session_factory

    async with get_session_factory()() as session:
        slots = (
            await session.execute(select(AICapacitySlot).order_by(AICapacitySlot.slot_no))
        ).scalars().all()
    assert len(slots) == 5
    from app.shared.clock import now_utc, to_db

    from tests.conftest import create_user_row

    # 用 5 个不同用户的运行中请求占满容量槽（避免与“同会话单活动轮”混淆）
    for slot in slots:
        holder = await create_user_row(account=f"capacity_{slot.slot_no}", role="student")
        holder_token = await login(holder["account"], holder["password"])
        holder_session = await session_id_for_token(holder_token)
        chat = await make_chat_request(
            user_id=holder["id"], session_id=holder_session, state="running"
        )
        async with get_session_factory()() as session:
            row = await session.get(AICapacitySlot, slot.slot_no)
            row.request_id = chat["request_id"]
            row.fence = 1
            row.lease_until = to_db(now_utc() + timedelta(seconds=30))
            await session.commit()

    response = await post_chat(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_capacity_1", "message": "明天有课吗"},
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "CAPACITY_LIMITED"

    # 释放一个槽（模拟前一轮终态回收）后可再次接受
    async with get_session_factory()() as session:
        row = await session.get(AICapacitySlot, 1)
        row.request_id = None
        row.lease_until = None
        await session.commit()

    status, events, _ = await read_stream(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_capacity_2", "message": "明天有课吗"},
    )
    assert status == 200
    assert events[-1]["event"] == "done"


# --------------------------------------------------------------------------- #
# 状态 / 取消
# --------------------------------------------------------------------------- #
async def test_state_is_owner_scoped(client, seeded, runtime_fixture):
    runtime, _ = runtime_fixture
    runtime.provider.gate.set()
    _, events, _ = await read_stream(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_state_001", "message": "明天有课吗"},
    )
    request_id = events[-1]["data"]["request_id"]

    other_token = seeded["other_headers"]["Authorization"].split(" ", 1)[1]
    other = await client.get(
        f"/api/v1/chat/requests/{request_id}", headers=AUTH(other_token)
    )
    assert other.status_code == 404

    unknown = await client.get(
        "/api/v1/chat/requests/req_unknown_x", headers=AUTH(seeded["student_token"])
    )
    assert unknown.status_code == 404


async def test_cancel_after_completion_is_noop(client, seeded, runtime_fixture):
    runtime, _ = runtime_fixture
    runtime.provider.gate.set()
    _, events, _ = await read_stream(
        client,
        seeded["student_token"],
        {"client_request_id": "creq_cancel_done", "message": "明天有课吗"},
    )
    request_id = events[-1]["data"]["request_id"]

    for _ in range(2):  # 幂等
        response = await client.post(
            f"/api/v1/chat/requests/{request_id}/cancel",
            headers=AUTH(seeded["student_token"]),
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["accepted"] is False
        assert data["request"]["state"] == "succeeded"


async def test_cancel_during_run_ends_once_with_cancelled(client, seeded, runtime_fixture):
    runtime, _ = runtime_fixture
    student = seeded["student"]
    gate = runtime.provider.gate

    stream_task = asyncio.create_task(
        read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_cancel_run", "message": "明天有课吗"},
        )
    )
    running = await wait_for_request_state(student["id"], ("accepted", "running"))

    cancel_response = await client.post(
        f"/api/v1/chat/requests/{running['request_id']}/cancel",
        headers=AUTH(seeded["student_token"]),
    )
    assert cancel_response.status_code == 200
    cancel_data = cancel_response.json()["data"]
    assert cancel_data["accepted"] is True
    assert cancel_data["request"]["cancel_requested"] is True

    gate.set()
    status, events, _ = await asyncio.wait_for(stream_task, timeout=25)
    assert status == 200
    validate_sse_events(events)
    assert_sse_invariants(events)
    done = events[-1]["data"]
    assert done["state"] == "cancelled"
    assert done["reason"] == "USER_CANCELLED"

    state_response = await client.get(
        f"/api/v1/chat/requests/{running['request_id']}",
        headers=AUTH(seeded["student_token"]),
    )
    state = state_response.json()["data"]
    assert state["state"] == "cancelled"
    assert state["cancel_requested"] is True


# --------------------------------------------------------------------------- #
# 校验
# --------------------------------------------------------------------------- #
async def test_stream_rejects_extra_field_and_unknown_query(client, seeded):
    response = await client.post(
        "/api/v1/chat/stream",
        json={"client_request_id": "creq_x", "message": "hi", "history": [], "evil": 1},
        headers=AUTH(seeded["student_token"]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"

    unknown_query = await client.post(
        "/api/v1/chat/stream?page=1",
        json={"client_request_id": "creq_y", "message": "hi"},
        headers=AUTH(seeded["student_token"]),
    )
    assert unknown_query.status_code == 422


async def test_stream_requires_authentication(client):
    response = await client.post(
        "/api/v1/chat/stream", json={"client_request_id": "creq_anon", "message": "hi"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"

async def test_capacity_slot_retries_transient_skip_locked(monkeypatch):
    """SKIP LOCKED 瞬时空闲槽被行锁占住时，不能直接判 429（AT-30 PERF-005）。"""
    from app.modules.assistant.accept import _lock_free_capacity_slot

    class _Result:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class _Session:
        def __init__(self):
            self.calls = 0

        async def execute(self, stmt):
            self.calls += 1
            return _Result(object() if self.calls >= 3 else None)

    class _Tx:
        def __init__(self):
            self.session = _Session()

    tx = _Tx()
    slot = await _lock_free_capacity_slot(tx)

    assert slot is not None
    assert tx.session.calls == 3


async def test_capacity_slot_429_is_bounded_when_really_full():
    """真满容量：重试次数有界、耗时有界，不能无限排队（NFR-PERF-004）。"""
    import time

    from app.modules.assistant import accept as accept_module

    class _Result:
        def scalar_one_or_none(self):
            return None

    class _Session:
        def __init__(self):
            self.calls = 0

        async def execute(self, stmt):
            self.calls += 1
            return _Result()

    class _Tx:
        def __init__(self):
            self.session = _Session()

    tx = _Tx()
    started = time.perf_counter()
    slot = await accept_module._lock_free_capacity_slot(tx)
    elapsed = time.perf_counter() - started

    assert slot is None
    assert tx.session.calls == accept_module._CAPACITY_SLOT_ATTEMPTS
    assert elapsed < 0.2
