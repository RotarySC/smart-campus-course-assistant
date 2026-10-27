"""AT-29：工具成功/空结果/失败的审计与统计可区分；正文与密钥不落日志。

两条口径（SRS AT-29 / FR-OPS-001/002 / NFR-PRIV-001）：
1. **可区分**：同一轮对话的终态事件必须能分出「有依据成功」「检索成功但无依据（空）」
   「依赖失败」，且统计口径按 ``corpus_empty`` 区分 empty 与 failed；
2. **不入日志**：真实日志路径（含 ``logger.exception`` 的 SQL 参数块）里不得出现
   计划正文与口令，脱敏占位符必须出现。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from app.adapters.model.deterministic import DeterministicProvider
from app.adapters.model.gateway import ToolCall, ToolExecutionRecord
from app.modules.assistant.runtime import Runtime, set_runtime
from app.shared.errors import ApiError
from tests.assistant_support import (
    StubToolExecutor,
    assistant_isolation,  # noqa: F401 - autouse fixture
    parse_sse,
    validate_sse_events,
)

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731


async def _read_stream(client, token: str, payload: dict, *, timeout: float = 40.0):
    async def _inner():
        async with client.stream(
            "POST", "/api/v1/chat/stream", json=payload, headers=AUTH(token)
        ) as response:
            raw = (await response.aread()).decode("utf-8")
            return response.status_code, parse_sse(raw)

    return await asyncio.wait_for(_inner(), timeout=timeout)


async def _outbox_of(db, request_id: str):
    from app.adapters.db.models import OutboxEvent

    async with db() as session:
        return list(
            (
                await session.execute(
                    select(OutboxEvent).where(OutboxEvent.aggregate_id == request_id)
                )
            )
            .scalars()
            .all()
        )


async def test_terminal_events_distinguish_success_empty_and_failure(client, seeded, db):
    executor = StubToolExecutor()
    runtime = Runtime(provider=DeterministicProvider(), executor=executor)
    set_runtime(runtime)
    try:
        # 1) 有依据成功
        status, events = await _read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_at29_ok", "message": "评分要求是什么？"},
        )
        assert status == 200, events
        validate_sse_events(events)
        done_ok = events[-1]["data"]
        assert done_ok["state"] == "succeeded"
        assert len(done_ok["citations"]) >= 1

        # 2) 检索成功但全库为空（不是失败）
        executor.corpus_empty = True
        status, events = await _read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_at29_empty", "message": "评分要求是什么？"},
        )
        assert status == 200, events
        validate_sse_events(events)
        done_empty = events[-1]["data"]
        assert done_empty["state"] == "succeeded"
        assert done_empty["citations"] == []

        # 3) 工具失败（内部 503 映射回 failed 记录）→ 回答明说暂不可用，且统计不把它算成空结果
        class _FailedToolExecutor:
            async def execute(self, call: ToolCall, context: Any) -> ToolExecutionRecord:
                return ToolExecutionRecord(
                    tool_name=call.tool_name,
                    arguments=call.arguments,
                    success=False,
                    result_status="failed",
                    dependency_state="failed",
                    code="RETRIEVAL_UNAVAILABLE",
                    payload={},
                )

        set_runtime(Runtime(provider=DeterministicProvider(), executor=_FailedToolExecutor()))
        status, events = await _read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_at29_fail", "message": "评分要求是什么？"},
        )
        assert status == 200, events
        validate_sse_events(events)
        done_fail = events[-1]["data"]
        # 工具失败不伪装成「没找到」：回答明说暂不可用，本轮仍正常收敛
        assert done_fail["state"] == "succeeded"
        fail_text = "".join(
            event["data"]["text_delta"] for event in events if event["event"] == "token"
        )
        assert "检索服务暂时不可用" in fail_text
        assert "没有检索到可用的课程资料依据" not in fail_text
        tool_end = next(event for event in events if event["event"] == "tool_end")
        assert tool_end["data"]["success"] is False
        assert tool_end["data"]["code"] == "RETRIEVAL_UNAVAILABLE"

        # 4) 执行器直接抛错（崩溃路径）→ 终态失败，不伪装成功
        class _RaisingExecutor:
            async def execute(self, call: ToolCall, context: Any) -> ToolExecutionRecord:
                raise ApiError("RETRIEVAL_UNAVAILABLE")

        set_runtime(Runtime(provider=DeterministicProvider(), executor=_RaisingExecutor()))
        status, events = await _read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_at29_crash", "message": "评分要求是什么？"},
        )
        assert status == 200, events
        validate_sse_events(events)
        events_are_error = [event for event in events if event["event"] == "error"]
        assert events_are_error, "执行器崩溃必须给 error 事件"
        crashed_request_id = events_are_error[-1]["data"]["request_id"]
    finally:
        set_runtime(None)

    # 统计口径：outbox 终态事件可区分（成功 / 空结果 / 工具失败 / 崩溃）
    async def _terminal_event(request_id: str):
        rows = await _outbox_of(db, request_id)
        return next(
            row
            for row in rows
            if row.event_type in ("chat_finished", "chat_failed")
        )

    ok_event = await _terminal_event(done_ok["request_id"])
    empty_event = await _terminal_event(done_empty["request_id"])
    fail_event = await _terminal_event(done_fail["request_id"])
    crash_event = await _terminal_event(crashed_request_id)

    assert ok_event.event_type == "chat_finished"
    assert ok_event.metadata_json["corpus_empty"] is False
    assert ok_event.metadata_json["citations"] >= 1

    assert empty_event.event_type == "chat_finished"
    assert empty_event.metadata_json["corpus_empty"] is True
    assert empty_event.metadata_json["citations"] == 0

    assert fail_event.event_type == "chat_finished"
    # 工具失败不等于空结果：corpus_empty 必须保持 None（不是 True）
    assert fail_event.metadata_json["corpus_empty"] is None
    assert fail_event.metadata_json["citations"] == 0

    assert crash_event.event_type == "chat_failed"
    assert crash_event.metadata_json["state"] == "failed"


async def test_logs_redact_plan_body_and_secrets_on_real_path(
    client, seeded, monkeypatch, caplog
):
    """真实 ``logger.exception`` 路径：SQL 参数块（含正文）必须被脱敏。"""
    from sqlalchemy.exc import OperationalError

    from app.modules.assistant import runner as runner_mod

    marker = "秘密计划正文ABC123"
    secret = "demo1234"

    def _broken_append_outbox(*args: Any, **kwargs: Any):
        raise OperationalError(
            "INSERT INTO plan_drafts (content) VALUES (%s)",
            (marker, secret),
            Exception("simulated failure"),
        )

    monkeypatch.setattr(runner_mod, "append_outbox", _broken_append_outbox)

    caplog.set_level(logging.WARNING, logger="cca.assistant.runner")
    runtime = Runtime(provider=DeterministicProvider(), executor=StubToolExecutor())
    set_runtime(runtime)
    try:
        status, events = await _read_stream(
            client,
            seeded["student_token"],
            {"client_request_id": "creq_at29_log", "message": "评分要求是什么？"},
        )
    finally:
        set_runtime(None)

    assert status == 200, events
    validate_sse_events(events)
    # 终态写失败不能伪装成功：没有 done；连接直接关闭（前端按 A7「流关闭而无终态 ⇒ unknown」
    # 进入核实路径，不得显示已成功）
    assert not [event for event in events if event["event"] == "done"]

    log_text = caplog.text
    assert marker not in log_text, "计划正文不得落日志"
    assert secret not in log_text, "口令不得落日志"
    assert "<redacted>" in log_text, "应看到脱敏占位符，证明过滤器在真实路径上生效"
