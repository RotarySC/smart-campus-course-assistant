"""AT-06：页面与助手查同一有课日/无课日，结果必须一致。

链路（真实）：学生页面 `GET /me/schedules` ↔ 助手 `get_my_schedule`（走 MCP 双跳 →
内部 API → 与页面同一个 ``resolve_range``/查询实现）。断言两边的**业务日语义**与
**内容**（课名、起止时间、有课/无课）一致，而不是各说各话。
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from app.adapters.model.deterministic import DeterministicProvider
from app.main import create_internal_app
from app.modules.assistant.runtime import Runtime, set_runtime
from app.modules.assistant.settings import reset_assistant_settings
from app.shared.clock import school_date
from tests.assistant_support import (
    assistant_isolation,  # noqa: F401 - autouse fixture
    parse_sse,
    serve_app,
    validate_sse_events,
)

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731


@pytest.fixture
async def internal_url(monkeypatch):
    async with serve_app(create_internal_app()) as url:
        monkeypatch.setenv("CCA_INTERNAL_API_URL", url)
        reset_assistant_settings()
        yield url


@pytest.fixture
async def mcp_url(internal_url):
    from app.entrypoints import mcp_server

    async with serve_app(mcp_server.create_mcp_app()) as base:
        yield f"{base}/mcp"


async def read_stream(client, token: str, payload: dict, *, timeout: float = 40.0):
    async def _inner():
        async with client.stream(
            "POST", "/api/v1/chat/stream", json=payload, headers=AUTH(token)
        ) as response:
            raw = (await response.aread()).decode("utf-8")
            return response.status_code, parse_sse(raw)

    return await asyncio.wait_for(_inner(), timeout=timeout)


async def _my_schedules(client, token: str, day) -> dict:
    response = await client.get(
        f"/api/v1/me/schedules?from_date={day}&to_date={day}", headers=AUTH(token)
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _answer_text(events) -> str:
    return "".join(
        event["data"]["text_delta"] for event in events if event["event"] == "token"
    )


async def test_page_and_assistant_agree_on_class_day_and_empty_day(
    client, seeded, internal_url, mcp_url
):
    from app.adapters.mcp.client import McpToolClient

    today = school_date()
    tomorrow = today + timedelta(days=1)

    # 造一门「今天」的课（明天故意不排）
    created = await client.post(
        "/api/v1/admin/schedules",
        json={
            "student_id": seeded["student"]["id"],
            "course_id": seeded["course"]["id"],
            "class_date": today.isoformat(),
            "start_time": "08:00",
            "end_time": "09:40",
            "location": "A-201",
        },
        headers=seeded["admin_headers"],
    )
    assert created.status_code == 201, created.text

    runtime = Runtime(provider=DeterministicProvider(), executor=McpToolClient(url=mcp_url))
    set_runtime(runtime)
    try:
        # ---- 有课日：页面 ----
        page_today = await _my_schedules(client, seeded["student_token"], today)
        assert page_today["total"] == 1
        item = page_today["items"][0]
        assert item["course_name"] == "数据结构"
        assert item["start_time"] == "08:00" and item["end_time"] == "09:40"

        # ---- 有课日：助手 ----
        status, events = await read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_at06_today", "message": "今天有什么课？"},
        )
        assert status == 200, events
        validate_sse_events(events)
        tool_end = next(e for e in events if e["event"] == "tool_end")
        assert tool_end["data"]["success"] is True
        assert tool_end["data"]["result_status"] == "ok"
        text = _answer_text(events)
        assert "数据结构" in text
        assert "08:00-09:40" in text
        assert today.isoformat() in text  # 完整日期，不是「今天」

        # ---- 无课日：页面与助手都是 empty，且助手不说成错误 ----
        page_tomorrow = await _my_schedules(client, seeded["student_token"], tomorrow)
        assert page_tomorrow["total"] == 0

        status, events = await read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_at06_tomorrow", "message": "明天有课吗"},
        )
        assert status == 200, events
        validate_sse_events(events)
        tool_end = next(e for e in events if e["event"] == "tool_end")
        assert tool_end["data"]["success"] is True
        assert tool_end["data"]["result_status"] == "empty"
        assert tool_end["data"].get("code") is None
        text = _answer_text(events)
        assert "没有查询到课程安排" in text
        assert "暂时不可用" not in text
    finally:
        set_runtime(None)
