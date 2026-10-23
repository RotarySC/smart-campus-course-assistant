"""助手车道测试支撑（fixture 约定沿用 ``conftest.py``，不改该文件）。

提供：
- 真实回环 HTTP 服务（uvicorn in-process，随机端口）与端口探测；
- 直接造 ``chat_requests`` / 草稿行（供内部 API / MCP 车道级测试）；
- SSE 解析 + 逐事件 jsonschema 校验；
- 注入式 Fake ToolExecutor（验证 SSE 全序列而不依赖网络）。
"""

from __future__ import annotations

import asyncio
import json
import socket
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from pathlib import Path
from typing import Any, AsyncIterator

import pytest_asyncio
import uvicorn
from sqlalchemy import select

from app.adapters.db.models import (
    ChatRequest,
    ConversationState,
    Course,
    PlanDraft,
    PlanDraftVersion,
    Schedule,
    User,
)
from app.adapters.db.uow import uow
from app.adapters.model.gateway import (
    EvidenceChunk,
    EvidenceReference,
    EvidenceSet,
    ToolCall,
    ToolExecutionRecord,
)
from app.shared.clock import now_utc, to_db
from app.shared.ids import (
    PREFIX_CONVERSATION,
    PREFIX_DRAFT,
    PREFIX_DRAFT_OPERATION,
    PREFIX_REQUEST,
    PREFIX_SCHEDULE,
    new_id,
)
from app.shared.payload import normalize_plan_payload, plan_payload_digest

BACKEND_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BACKEND_DIR.parent / "docs"
SSE_SCHEMA_PATH = DOCS_DIR / "backend" / "sse_events_v0.1.schema.json"
MCP_TOOLS_PATH = DOCS_DIR / "backend" / "mcp_tools_v0.1.json"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@asynccontextmanager
async def serve_app(app: Any, *, port: int | None = None) -> AsyncIterator[str]:
    """在独立 uvicorn 任务里跑真实 HTTP 服务（仅回环）。"""
    chosen = port or free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=chosen,
        log_level="warning",
        lifespan="on",
        access_log=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(300):
        if server.started:
            break
        await asyncio.sleep(0.02)
    else:  # pragma: no cover - 启动失败
        server.should_exit = True
        raise RuntimeError("uvicorn 启动超时")
    try:
        yield f"http://127.0.0.1:{chosen}"
    finally:
        server.should_exit = True
        with suppress(Exception):
            await asyncio.wait_for(task, timeout=10)


async def session_id_for_token(token: str) -> str:
    from app.adapters.db.engine import get_session_factory
    from app.adapters.db.models import AuthSession
    from app.shared.security import token_digest

    async with get_session_factory()() as session:
        result = await session.execute(
            select(AuthSession).where(AuthSession.token_digest == token_digest(token))
        )
        return result.scalar_one().id


async def make_chat_request(
    *,
    user_id: str,
    session_id: str,
    state: str = "running",
    fence: int = 1,
    conversation_id: str | None = None,
    deadline_seconds: int = 60,
    lease_seconds: int = 30,
    cancel_requested: bool = False,
    message: str = "明天有课吗",
) -> dict[str, Any]:
    """直接造一条 ChatRequest（模拟已被 accept 的轮次）。"""
    now = now_utc()
    conversation_id = conversation_id or new_id(PREFIX_CONVERSATION)
    request_id = new_id(PREFIX_REQUEST)
    async with uow() as tx:
        if await tx.session.get(ConversationState, conversation_id) is None:
            tx.session.add(
                ConversationState(
                    id=conversation_id,
                    user_id=user_id,
                    session_id=session_id,
                    active_request_id=None,
                    created_at=to_db(now),
                    updated_at=to_db(now),
                )
            )
        tx.session.add(
            ChatRequest(
                id=request_id,
                client_request_id=new_id(PREFIX_REQUEST),
                user_id=user_id,
                session_id=session_id,
                conversation_id=conversation_id,
                request_digest=b"\x00" * 32,
                state=state,
                cancel_requested=cancel_requested,
                accepted_at=to_db(now),
                deadline_at=to_db(now + timedelta(seconds=deadline_seconds)),
                finished_at=None,
                school_timezone="Asia/Shanghai",
                model_calls=0,
                tool_calls=0,
                owner_instance="test",
                fence=fence,
                lease_until=to_db(now + timedelta(seconds=lease_seconds)),
                terminal_reason=None,
                plan_id=None,
                operation_id=None,
            )
        )
        await tx.commit()
    return {
        "request_id": request_id,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "user_id": user_id,
        "fence": fence,
        "message": message,
    }


async def make_draft_row(
    *,
    user_id: str,
    session_id: str,
    conversation_id: str,
    origin_request_id: str,
    title: str = "本周复习计划",
    content: str = "周一复习数据结构；周三完成实验报告。",
    goal: str | None = "掌握树与图",
    expires_seconds: int = 1800,
) -> dict[str, Any]:
    now = now_utc()
    draft_id = new_id(PREFIX_DRAFT)
    operation_id = new_id(PREFIX_DRAFT_OPERATION)
    payload = normalize_plan_payload(
        {
            "title": title,
            "goal": goal,
            "start_date": None,
            "end_date": None,
            "content": content,
            "basis_types": ["schedule"],
            "references": [],
        }
    )
    digest = plan_payload_digest(payload)
    async with uow() as tx:
        tx.session.add(
            PlanDraft(
                id=draft_id,
                user_id=user_id,
                session_id=session_id,
                conversation_id=conversation_id,
                origin_chat_request_id=origin_request_id,
                current_version=1,
                expires_at=to_db(now + timedelta(seconds=expires_seconds)),
                created_at=to_db(now),
                updated_at=to_db(now),
            )
        )
        tx.session.add(
            PlanDraftVersion(
                draft_id=draft_id,
                draft_version=1,
                operation_id=operation_id,
                schema_version=1,
                payload=payload,
                content_digest=digest,
                created_at=to_db(now),
                payload_cleared_at=None,
            )
        )
        await tx.commit()
    return {
        "draft_id": draft_id,
        "draft_version": 1,
        "operation_id": operation_id,
        "payload": payload,
    }


async def seed_course_and_schedule(
    *,
    user_id: str,
    course_name: str = "数据结构",
    class_date=None,
) -> dict[str, Any]:
    from datetime import date, time

    now = now_utc()
    course_id = new_id("crs")
    schedule_id = new_id(PREFIX_SCHEDULE)
    day = class_date or (now.date() + timedelta(days=1))
    async with uow() as tx:
        tx.session.add(
            Course(
                id=course_id,
                code=f"CS{new_id('crs')[-4:]}",
                code_norm=b"seed",
                name=course_name,
                description=None,
                enabled=True,
                version=1,
                created_at=to_db(now),
                updated_at=to_db(now),
            )
        )
        tx.session.add(
            Schedule(
                id=schedule_id,
                user_id=user_id,
                course_id=course_id,
                class_date=day,
                start_time=time(8, 0),
                end_time=time(9, 40),
                location="教学楼 A101",
                overlap_reason=None,
                version=1,
                created_at=to_db(now),
                updated_at=to_db(now),
            )
        )
        await tx.commit()
    return {"course_id": course_id, "schedule_id": schedule_id, "date": day}


# --------------------------------------------------------------------------- #
# SSE 解析与 schema 校验
# --------------------------------------------------------------------------- #
class SseParseError(Exception):
    pass


def parse_sse(raw: str) -> list[dict[str, Any]]:
    """把 SSE 文本解析为 [{id,event,data}]（忽略注释心跳）。"""
    events: list[dict[str, Any]] = []
    for block in raw.split("\n\n"):
        block = block.strip("\n")
        if not block or block.startswith(":"):
            continue
        event_name = None
        event_id = None
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("id:"):
                event_id = line[3:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if event_name is None:
            continue
        payload = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append({"id": event_id, "event": event_name, "data": payload})
    return events


_SCHEMA_CACHE: dict[str, Any] | None = None


def sse_schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = json.loads(SSE_SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE


def validate_sse_events(events: list[dict[str, Any]]) -> None:
    import jsonschema

    schema = sse_schema()
    for event in events:
        jsonschema.validate(instance=event, schema=schema)


def assert_sse_invariants(events: list[dict[str, Any]]) -> None:
    """流级应用约束：seq 连续、终态唯一且最后、工具配对、首个 status 含会话。"""
    assert events, "至少应有一个事件"
    seqs = [event["data"]["seq"] for event in events]
    assert seqs == list(range(1, len(events) + 1)), f"seq 必须从 1 连续递增: {seqs}"
    terminals = [event for event in events if event["event"] in ("done", "error")]
    assert len(terminals) == 1, f"终态必须恰好一次: {terminals}"
    assert events[-1]["event"] in ("done", "error"), "终态必须是最后一个事件"
    first = events[0]
    assert first["event"] == "status"
    assert first["data"]["code"] == "ACCEPTED"
    assert first["data"].get("conversation_id"), "首个 status 必须含 conversation_id"
    starts = {
        event["data"]["tool_call_id"]
        for event in events
        if event["event"] == "tool_start"
    }
    ends = {
        event["data"]["tool_call_id"]
        for event in events
        if event["event"] == "tool_end"
    }
    assert starts == ends, f"tool_start/tool_end 必须按 tool_call_id 一一配对: {starts} / {ends}"
    for event in events:
        assert str(event["data"]["seq"]) == str(event["id"]), "id 必须等于 data.seq"


# --------------------------------------------------------------------------- #
# 注入式 Fake ToolExecutor
# --------------------------------------------------------------------------- #
class StubToolExecutor:
    """确定性工具执行器：不经过网络，用于验证 SSE/预算/取消等执行语义。"""

    def __init__(self) -> None:
        self.calls: list[ToolCall] = []
        self.fail_schedule = False
        self.fail_docs = False
        self.fail_save_codes: list[str] = []
        self.saved_plans: list[dict[str, str]] = []

    async def execute(self, call: ToolCall, context: Any) -> ToolExecutionRecord:
        self.calls.append(call)
        if call.tool_name == "get_my_schedule":
            if self.fail_schedule:
                return ToolExecutionRecord(
                    tool_name=call.tool_name,
                    arguments=call.arguments,
                    success=False,
                    result_status="failed",
                    dependency_state="failed",
                    code="MCP_UNAVAILABLE",
                    payload={"code": "MCP_UNAVAILABLE"},
                )
            from_date = call.arguments.get("from_date", "")
            to_date = call.arguments.get("to_date", "")
            return ToolExecutionRecord(
                tool_name=call.tool_name,
                arguments=call.arguments,
                success=True,
                result_status="ok",
                dependency_state="satisfied",
                payload={
                    "status": "ok",
                    "from_date": from_date,
                    "to_date": to_date,
                    "school_timezone": "Asia/Shanghai",
                    "items": [
                        {
                            "id": "sch_fixture_1",
                            "student_id": context.actor.user_id,
                            "course_id": "crs_fixture_1",
                            "course_name": "数据结构",
                            "class_date": from_date,
                            "start_time": "08:00",
                            "end_time": "09:40",
                            "location": "教学楼 A101",
                            "version": 1,
                        }
                    ],
                },
            )
        if call.tool_name == "search_course_docs":
            if self.fail_docs:
                return ToolExecutionRecord(
                    tool_name=call.tool_name,
                    arguments=call.arguments,
                    success=False,
                    result_status="failed",
                    dependency_state="failed",
                    code="RETRIEVAL_UNAVAILABLE",
                    payload={"code": "RETRIEVAL_UNAVAILABLE"},
                )
            reference = EvidenceReference(
                reference_id="cit_fixture_1",
                document_id="doc_fixture_1",
                version_id="dvs_fixture_1",
                file_name="课程大纲.txt",
                location_label="第 1 页",
                page_number=1,
            )
            chunk = EvidenceChunk(
                chunk_id="chk_fixture_1",
                reference_id=reference.reference_id,
                document_id=reference.document_id,
                version_id=reference.version_id,
                text="期末成绩由平时作业与期末考试组成。",
                location_label=reference.location_label,
                page_number=1,
            )
            evidence = EvidenceSet(
                status="ok",
                corpus_empty=False,
                revision=0,
                chunks=(chunk,),
                references=(reference,),
            )
            payload = {
                "status": "ok",
                "corpus_empty": False,
                "revision": 0,
                "chunks": [],
                "references": [],
                "_evidence": evidence,
            }
            return ToolExecutionRecord(
                tool_name=call.tool_name,
                arguments=call.arguments,
                success=True,
                result_status="ok",
                dependency_state="satisfied",
                payload=payload,
            )
        # save_study_plan（runner 服务端编排）
        if self.fail_save_codes:
            code = self.fail_save_codes.pop(0)
            return ToolExecutionRecord(
                tool_name=call.tool_name,
                arguments=call.arguments,
                success=False,
                result_status="failed",
                dependency_state="failed",
                code=code,
                payload={"code": code},
            )
        plan_id = new_id("plan")
        operation_id = f"dop_{plan_id[-16:]}"
        record = {
            "status": "created",
            "operation_id": operation_id,
            "plan_id": plan_id,
        }
        self.saved_plans.append(record)
        return ToolExecutionRecord(
            tool_name=call.tool_name,
            arguments=call.arguments,
            success=True,
            result_status="created",
            dependency_state="satisfied",
            payload=record,
        )


@pytest_asyncio.fixture(autouse=True)
async def assistant_isolation() -> AsyncIterator[None]:
    """每个用例恢复：运行时、助手配置、全局时钟、jti、检索 stub、MCP 全局 server。"""
    from app.adapters.mcp.delegation import reset_jti_registry
    from app.entrypoints import mcp_server
    from app.modules.assistant import retrieval, runtime
    from app.modules.assistant.settings import reset_assistant_settings
    from app.shared.clock import reset_clock

    await runtime.reset_runtime()
    reset_assistant_settings()
    reset_clock()
    reset_jti_registry()
    retrieval.reset_stub_evidence()
    mcp_server.release_server()
    yield
    await runtime.reset_runtime()
    reset_assistant_settings()
    reset_clock()
    reset_jti_registry()
    retrieval.reset_stub_evidence()
    mcp_server.release_server()


async def user_row(user_id: str) -> User | None:
    from app.adapters.db.engine import get_session_factory

    async with get_session_factory()() as session:
        return await session.get(User, user_id)


@asynccontextmanager
async def open_mcp_session(url: str, headers: dict[str, str]) -> AsyncIterator[Any]:
    """真实 SDK 客户端：初始化 MCP 会话（回环 Streamable HTTP）。"""
    from mcp import ClientSession
    from mcp.client.streamable_http import (
        create_mcp_http_client,
        streamable_http_client,
    )

    http_client = create_mcp_http_client(headers=headers)
    async with http_client:
        async with streamable_http_client(url, http_client=http_client) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(
                read_stream, write_stream, read_timeout_seconds=30
            ) as session:
                await session.initialize()
                yield session


async def call_mcp_tool(
    url: str,
    headers: dict[str, str],
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> Any:
    async with open_mcp_session(url, headers) as session:
        return await session.call_tool(tool_name, arguments or {})


def contract_tools() -> dict[str, dict[str, Any]]:
    payload = json.loads(MCP_TOOLS_PATH.read_text(encoding="utf-8"))
    return {tool["name"]: tool for tool in payload["tools"]}

