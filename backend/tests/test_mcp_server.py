"""MCP Server 车道测试（PHASE-03 D3）：真实回环 HTTP + 真实 MySQL + SDK 客户端。

覆盖：
- 初始化 + ``list_tools``（三工具、schema 与 ``mcp_tools_v0.1.json`` 对齐）；
- 三次工具调用（课表 / 检索 / 保存）经真实**双跳委派**（API → MCP → 内部 API）；
- 错误拒绝：无凭据、错 audience、过期、重放（jti）、阻止浏览器 Origin。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest

from app.adapters.mcp.client import DELEGATION_HEADER, SERVICE_HEADER, McpToolClient
from app.adapters.mcp.delegation import (
    ALGORITHM,
    AUD_INTERNAL,
    AUD_MCP,
    ISSUER,
    SCOPE_DOCS_SEARCH,
    SCOPE_PLAN_SAVE,
    SCOPE_SCHEDULE_READ,
    mint_delegation,
)
from app.config import get_settings
from app.entrypoints import mcp_server
from app.main import create_internal_app
from app.modules.assistant.contracts import (
    EvidenceChunkOut,
    ReferenceOut,
    SearchToolOutput,
)
from tests._knowledge_helpers import (  # noqa: F401 - autouse fixtures
    publish_batch,
    txt_bytes,
    unfreeze_corpus,
)
from tests.assistant_support import (
    call_mcp_tool,
    contract_tools,
    make_chat_request,
    make_draft_row,
    open_mcp_session,
    seed_course_and_schedule,
    serve_app,
    session_id_for_token,
)

# Windows 路径长度：知识链路落盘用系统临时短目录（任务/版本目录会超 260）
_DOC_PARA = (
    "第{n}段：实验课预习要求包括完成预习报告、写明实验目的与步骤、提前提交。"
    "预习报告需在实验开始前通过课程平台提交，未提交者不得进入实验室。"
)
DOC_ONE = "实验课预习与评分说明.txt"
DOC_ONE_TEXT = "实验课预习与评分说明\n" + "\n".join(
    _DOC_PARA.format(n=i) for i in range(1, 8)
)
DOC_TWO = "实验课评分补充说明.txt"
DOC_TWO_TEXT = "实验课评分与预习补充说明\n" + "\n".join(
    _DOC_PARA.format(n=i) + "实验课预习要求同样适用于补做实验。" for i in range(8, 15)
)


@pytest.fixture(autouse=True)
def short_knowledge_storage(monkeypatch):
    base = Path(tempfile.mkdtemp(prefix="cca_mcp_"))
    monkeypatch.setenv("CCA_FILESTORE_ROOT", str(base / "u"))
    monkeypatch.setenv("CCA_VECTOR_ROOT", str(base / "v"))
    monkeypatch.setenv("CCA_CHUNK_SIZE", "120")
    monkeypatch.setenv("CCA_CHUNK_OVERLAP", "20")
    yield base
    shutil.rmtree(base, ignore_errors=True)


def _delegation(chat: dict, scope: str, *, ttl: int = 30) -> str:
    return mint_delegation(
        audience=AUD_MCP,
        user_id=chat["user_id"],
        session_id=chat["session_id"],
        auth_version=1,
        request_id=chat["request_id"],
        conversation_id=chat["conversation_id"],
        scope=[scope],
        fence=chat["fence"],
        ttl_seconds=ttl,
    )


def _headers(delegation: str) -> dict[str, str]:
    return {
        SERVICE_HEADER: get_settings().service_token,
        DELEGATION_HEADER: delegation,
    }


@pytest.fixture
async def mcp_env(seeded, monkeypatch):
    """起真实内部 API + MCP 服务（随机回环端口）。"""
    internal = create_internal_app()
    async with serve_app(internal) as internal_url:
        monkeypatch.setenv("CCA_INTERNAL_API_URL", internal_url)
        from app.modules.assistant.settings import reset_assistant_settings

        reset_assistant_settings()
        async with serve_app(mcp_server.create_mcp_app()) as mcp_url:
            yield {"internal_url": internal_url, "mcp_url": f"{mcp_url}/mcp"}


async def test_list_tools_matches_contract(mcp_env):
    tool_session_headers = _headers("placeholder")
    async with open_mcp_session(mcp_env["mcp_url"], tool_session_headers) as session:
        listing = await session.list_tools()
    tools = listing.tools
    by_name = {tool.name: tool for tool in tools}
    contract = contract_tools()
    assert set(by_name) == set(contract) == {
        "get_my_schedule",
        "search_course_docs",
        "save_study_plan",
    }
    for name, contract_tool in contract.items():
        schema = by_name[name].input_schema
        expected = contract_tool["inputSchema"]
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == set(expected["properties"])
        assert sorted(schema.get("required") or []) == sorted(expected.get("required") or [])
        output = by_name[name].output_schema
        assert output is not None
        assert set(output["properties"]) == set(contract_tool["outputSchema"]["properties"])
        assert sorted(output.get("required") or []) == sorted(
            contract_tool["outputSchema"]["required"]
        )


async def test_three_tools_over_real_delegation(seeded, mcp_env):
    student = seeded["student"]
    token = seeded["student_token"]
    session_id = await session_id_for_token(token)
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    await seed_course_and_schedule(user_id=student["id"])

    # 1) get_my_schedule：完整范围 + 身份固定
    schedule_result = await call_mcp_tool(
        mcp_env["mcp_url"],
        _headers(_delegation(chat, SCOPE_SCHEDULE_READ)),
        "get_my_schedule",
        {},
    )
    assert schedule_result.is_error is False, schedule_result
    schedule = schedule_result.structured_content
    assert schedule["status"] == "ok"
    assert schedule["school_timezone"] == "Asia/Shanghai"
    assert schedule["items"] and schedule["items"][0]["student_id"] == student["id"]

    # 2) search_course_docs：Phase 2 已合并 → 真实 knowledge.search；
    #    本用例库没有已发布资料，因此按契约返回 empty（不是失败，也不是 stub 假数据）
    search_result = await call_mcp_tool(
        mcp_env["mcp_url"],
        _headers(_delegation(chat, SCOPE_DOCS_SEARCH)),
        "search_course_docs",
        {"query": "期末成绩怎么算"},
    )
    assert search_result.is_error is False, search_result
    search = search_result.structured_content
    assert search["status"] == "empty"
    assert search["corpus_empty"] is True
    assert search["chunks"] == [] and search["references"] == []
    # 真实 EvidenceSet（ok 路径）→ SSE citations → /citations/{id} 展开见
    # tests/test_assistant_e2e_knowledge.py

    # 3) save_study_plan：服务端签发 direct_instruction 许可并真实落库
    draft = await make_draft_row(
        user_id=student["id"],
        session_id=session_id,
        conversation_id=chat["conversation_id"],
        origin_request_id=chat["request_id"],
    )
    save_result = await call_mcp_tool(
        mcp_env["mcp_url"],
        _headers(_delegation(chat, SCOPE_PLAN_SAVE)),
        "save_study_plan",
        {"draft_id": draft["draft_id"], "draft_version": 1},
    )
    assert save_result.is_error is False, save_result
    saved = save_result.structured_content
    assert saved["status"] == "created"
    assert saved["operation_id"] == draft["operation_id"]
    assert saved["plan_id"]

    # 重复调用同草稿版本（新 jti）：幂等返回 existing，不新增
    again = await call_mcp_tool(
        mcp_env["mcp_url"],
        _headers(_delegation(chat, SCOPE_PLAN_SAVE)),
        "save_study_plan",
        {"draft_id": draft["draft_id"], "draft_version": 1},
    )
    assert again.is_error is False
    assert again.structured_content["status"] == "existing"
    assert again.structured_content["plan_id"] == saved["plan_id"]

    from sqlalchemy import func, select

    from app.adapters.db.engine import get_session_factory
    from app.adapters.db.models import AssistantSaveSlot, StudyPlan, WriteOperation

    async with get_session_factory()() as db_session:
        plan_count = await db_session.scalar(
            select(func.count()).select_from(StudyPlan).where(StudyPlan.user_id == student["id"])
        )
        slot_count = await db_session.scalar(
            select(func.count())
            .select_from(AssistantSaveSlot)
            .where(AssistantSaveSlot.user_id == student["id"])
        )
        operation = await db_session.get(
            WriteOperation, (student["id"], draft["operation_id"])
        )
    assert plan_count == 1
    assert slot_count == 1
    assert operation is not None and operation.state == "succeeded"


async def test_missing_delegation_is_auth_error(seeded, mcp_env):
    result = await call_mcp_tool(
        mcp_env["mcp_url"],
        {SERVICE_HEADER: get_settings().service_token},
        "search_course_docs",
        {"query": "x"},
    )
    assert result.is_error is True
    assert result.structured_content["code"] == "AUTH_REQUIRED"


async def test_wrong_audience_is_rejected(seeded, mcp_env):
    student = seeded["student"]
    token = seeded["student_token"]
    session_id = await session_id_for_token(token)
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    internal_token = mint_delegation(
        audience=AUD_INTERNAL,
        user_id=chat["user_id"],
        session_id=chat["session_id"],
        auth_version=1,
        request_id=chat["request_id"],
        conversation_id=chat["conversation_id"],
        scope=[SCOPE_SCHEDULE_READ],
        fence=chat["fence"],
    )
    result = await call_mcp_tool(
        mcp_env["mcp_url"], _headers(internal_token), "get_my_schedule", {}
    )
    assert result.is_error is True
    assert result.structured_content["code"] == "FORBIDDEN"


async def test_expired_delegation_is_rejected(seeded, mcp_env):
    student = seeded["student"]
    token = seeded["student_token"]
    session_id = await session_id_for_token(token)
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    now = datetime.now(timezone.utc)
    claims = {
        "iss": ISSUER,
        "aud": AUD_MCP,
        "sub": chat["user_id"],
        "session_id": chat["session_id"],
        "auth_version": 1,
        "request_id": chat["request_id"],
        "conversation_id": chat["conversation_id"],
        "scope": [SCOPE_SCHEDULE_READ],
        "fence": chat["fence"],
        "iat": int((now - timedelta(seconds=120)).timestamp()),
        "exp": int((now - timedelta(seconds=60)).timestamp()),
        "jti": "expired-jti-0001",
    }
    expired = jwt.encode(claims, get_settings().delegation_signing_key, algorithm=ALGORITHM)
    result = await call_mcp_tool(
        mcp_env["mcp_url"], _headers(expired), "get_my_schedule", {}
    )
    assert result.is_error is True
    assert result.structured_content["code"] == "AUTH_REQUIRED"


async def test_replayed_delegation_is_rejected(seeded, mcp_env):
    student = seeded["student"]
    token = seeded["student_token"]
    session_id = await session_id_for_token(token)
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    delegation = _delegation(chat, SCOPE_SCHEDULE_READ)
    headers = _headers(delegation)
    first = await call_mcp_tool(mcp_env["mcp_url"], headers, "get_my_schedule", {})
    assert first.is_error is False
    second = await call_mcp_tool(mcp_env["mcp_url"], headers, "get_my_schedule", {})
    assert second.is_error is True
    assert second.structured_content["code"] == "AUTH_REQUIRED"


def _error_text(exc: BaseException) -> str:
    """展开 ExceptionGroup，收集全部子异常文本与 JSON-RPC code。"""
    parts = [str(exc), f"code={getattr(exc, 'code', '')}"]
    for inner in getattr(exc, "exceptions", ()) or ():
        parts.append(_error_text(inner))
    if exc.__cause__ is not None:
        parts.append(_error_text(exc.__cause__))
    return "\n".join(parts)


async def test_unknown_argument_is_protocol_error(seeded, mcp_env):
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    headers = _headers(_delegation(chat, SCOPE_SCHEDULE_READ))
    # 额外字段（例如伪造 student_id）必须在协议层被拒绝（-32602 invalid params），
    # 而不是被静默忽略
    with pytest.raises(Exception) as excinfo:
        await call_mcp_tool(
            mcp_env["mcp_url"], headers, "get_my_schedule", {"student_id": "usr_other"}
        )
    assert "-32602" in _error_text(excinfo.value)


async def test_browser_origin_is_rejected(seeded, mcp_env):
    import httpx

    async with httpx.AsyncClient(trust_env=False) as client:
        response = await client.post(
            mcp_env["mcp_url"],
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            headers={
                "Origin": "https://evil.example",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
    assert response.status_code != 200


async def test_internal_api_requires_service_credential(seeded, mcp_env):
    """内部 API 不接受浏览器 Bearer / 无凭据调用（D6 契约）。"""
    import httpx

    async with httpx.AsyncClient(base_url=mcp_env["internal_url"], trust_env=False) as client:
        missing = await client.post(
            "/internal/v1/tools/get-my-schedule", json={}
        )
        assert missing.status_code == 401
        assert missing.json()["error"]["code"] == "AUTH_REQUIRED"

        browser_only = await client.post(
            "/internal/v1/tools/get-my-schedule",
            json={},
            headers={
                "X-Service-Credential": get_settings().service_token,
                "Authorization": f"Bearer {seeded['student_token']}",
            },
        )
        assert browser_only.status_code == 401
        assert browser_only.json()["error"]["code"] == "AUTH_REQUIRED"

        wrong_service = await client.post(
            "/internal/v1/tools/get-my-schedule",
            json={},
            headers={"X-Service-Credential": "wrong-token"},
        )
        assert wrong_service.status_code == 403
        assert wrong_service.json()["error"]["code"] == "FORBIDDEN"


async def test_exchange_rejects_wrong_audience(seeded, mcp_env):
    """兑换端点只接受 aud=cca-mcp；aud=cca-internal 的凭据不得再次兑换。"""
    import httpx

    from app.adapters.mcp.delegation import AUD_INTERNAL

    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)
    internal_token = mint_delegation(
        audience=AUD_INTERNAL,
        user_id=chat["user_id"],
        session_id=chat["session_id"],
        auth_version=1,
        request_id=chat["request_id"],
        conversation_id=chat["conversation_id"],
        scope=[SCOPE_SCHEDULE_READ],
        fence=chat["fence"],
    )
    async with httpx.AsyncClient(base_url=mcp_env["internal_url"], trust_env=False) as client:
        response = await client.post(
            "/internal/v1/delegations/exchange",
            json={"delegation": internal_token},
            headers={"X-Service-Credential": get_settings().service_token},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


# --------------------------------------------------------------------------- #
# 回归（Phase 5 缺陷）：structuredContent 必须与已发布 outputSchema 一致
# --------------------------------------------------------------------------- #
async def test_success_payload_omits_none_and_passes_advertised_output_schema():
    """缺省的可选字段不得序列化成 null（否则 MCP 客户端校验失败 → MCP_UNAVAILABLE）。"""
    import jsonschema

    output = SearchToolOutput(
        status="ok",
        corpus_empty=False,
        revision=0,
        chunks=[
            EvidenceChunkOut(
                chunk_id="chk_regress_1",
                reference_id="cit_regress_1",
                document_id="doc_regress_1",
                version_id="dvs_regress_1",
                text="实验课预习要求：提前提交预习报告。",
                location_label="第 1 段",  # 无页码（txt）
            )
        ],
        references=[
            ReferenceOut(
                reference_id="cit_regress_1",
                document_id="doc_regress_1",
                version_id="dvs_regress_1",
                file_name="实验课预习.txt",
                location_label="第 1 段",
            )
        ],
    )
    result = mcp_server._tool_success(output)
    assert result.is_error is False
    payload = result.structured_content or {}
    assert "page_number" not in payload["chunks"][0]
    assert "page_number" not in payload["references"][0]

    tools = await mcp_server.get_server().list_tools()
    schema = next(tool.output_schema for tool in tools if tool.name == "search_course_docs")
    jsonschema.validate(instance=payload, schema=schema)


async def test_search_multi_document_multi_chunk_via_api_client(
    client, seeded, mcp_env
):
    """真实回环 MCP + 多文档/多 chunk：必须成功映射 references（不得 MCP_UNAVAILABLE）。"""
    from datetime import timedelta

    from app.adapters.model.gateway import ToolCall
    from app.shared.clock import now_utc
    from app.shared.context import ActorContext, ExecutionContext

    await publish_batch(
        client,
        seeded["admin_headers"],
        [(DOC_ONE, txt_bytes(DOC_ONE_TEXT)), (DOC_TWO, txt_bytes(DOC_TWO_TEXT))],
    )
    student = seeded["student"]
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(user_id=student["id"], session_id=session_id)

    api_client = McpToolClient(url=mcp_env["mcp_url"])
    actor = ActorContext(
        user_id=student["id"],
        session_id=session_id,
        auth_version=1,
        role="student",
        trace_request_id="req_regress_mcp",
    )
    context = ExecutionContext(
        actor=actor,
        chat_request_id=chat["request_id"],
        conversation_id=chat["conversation_id"],
        accepted_at=now_utc(),
        school_timezone="Asia/Shanghai",
        deadline_at=now_utc() + timedelta(seconds=60),
        execution_fence=1,
    )
    record = await api_client.execute(
        ToolCall(
            tool_name="search_course_docs",
            arguments={"query": "实验课预习要求是什么？"},
        ),
        context,
    )
    assert record.success is True, record.payload
    assert record.result_status == "ok"
    evidence = record.payload.get("_evidence")
    assert evidence is not None and evidence.status == "ok"
    assert len(evidence.chunks) >= 1
    assert len(evidence.references) >= 1
    assert all(item.reference_id.startswith("cit_") for item in evidence.references)
    published = {DOC_ONE, DOC_TWO}
    assert {item.file_name for item in evidence.references} <= published

    # 原始 structuredContent 中不得出现 null 的可选字段（根因回归断言）
    raw = await api_client._call_tool(
        "search_course_docs",
        {"query": "实验课预习要求是什么？"},
        _delegation(chat, SCOPE_DOCS_SEARCH),
    )
    structured = raw.structured_content or {}
    for item in (structured.get("chunks") or []) + (structured.get("references") or []):
        assert item.get("page_number") is not None or "page_number" not in item
