"""Phase 3 端到端补充：真实 EvidenceSet → SSE 引用 → ``GET /citations/{id}`` 展开。

链路（全真实）：
admin 上传 txt → worker 解析/入库/发布 → 学生提问 → DeterministicProvider 触发
``search_course_docs`` → 内部 API 调真实 ``knowledge.search`` → MCP 回传 →
SSE ``tool_end``/``done.citations`` 带权威 reference → ``GET /api/v1/citations/{reference_id}``
返回可展开片段。

依赖 Phase 2 的测试夹具（只 import，不改 knowledge 模块）。
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from app.adapters.model.deterministic import DeterministicProvider
from app.config import get_settings
from app.main import create_internal_app
from app.modules.assistant.runtime import Runtime, set_runtime
from app.modules.assistant.settings import reset_assistant_settings
from tests._knowledge_helpers import (  # noqa: F401 - autouse fixtures
    publish_batch,
    txt_bytes,
    unfreeze_corpus,
)
from tests.assistant_support import (
    InternalToolExecutor,
    assistant_isolation,  # noqa: F401 - autouse fixture
    parse_sse,
    serve_app,
    validate_sse_events,
)

AUTH = lambda token: {"Authorization": f"Bearer {token}"}  # noqa: E731

DOC_NAME = "实验课预习与评分说明.txt"
DOC_CONTENT = (
    "实验课预习要求：每次实验前必须完成预习报告，写明实验目的、步骤与预期结果。\n"
    "预习报告需在实验开始前通过课程平台提交，未提交者不得进入实验室。\n"
    "实验成绩占课程总评的百分之二十，缺勤一次扣五分。\n"
)


@pytest.fixture(autouse=True)
def short_knowledge_storage(monkeypatch):
    """Windows 路径长度：用系统临时目录（短路径）承载 FileStore/VectorStore。

    ``tmp_path`` 位于深工作树下，任务目录 + 版本目录会触发 WinError 206。
    """
    base = Path(tempfile.mkdtemp(prefix="cca_p3_"))
    monkeypatch.setenv("CCA_FILESTORE_ROOT", str(base / "u"))
    monkeypatch.setenv("CCA_VECTOR_ROOT", str(base / "v"))
    monkeypatch.setenv("CCA_CHUNK_SIZE", "120")
    monkeypatch.setenv("CCA_CHUNK_OVERLAP", "20")
    yield base
    shutil.rmtree(base, ignore_errors=True)


async def read_stream(client, token, payload, *, timeout: float = 40.0):
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


@pytest.fixture
async def mcp_url(internal_url):
    """真实回环 MCP server（依赖已启动的内部 API）。"""
    from app.entrypoints import mcp_server

    async with serve_app(mcp_server.create_mcp_app()) as base:
        yield f"{base}/mcp"


DOC_TWO_NAME = "实验课评分补充说明.txt"
DOC_TWO_CONTENT = (
    "实验课评分与预习补充说明：补做实验同样需要提前提交预习报告，否则不得进入实验室。\n"
    "实验课预习要求包括写明实验目的、步骤与预期结果，并在实验开始前完成提交。\n"
)


async def test_real_evidence_over_mcp_transport_into_citations(
    client, seeded, internal_url, mcp_url
):
    """回归（Phase 5 缺陷）：真实 MCP 传输 + 多文档/多 chunk → tool_end ok + citations 可用。"""
    from app.adapters.mcp.client import McpToolClient

    await publish_batch(
        client,
        seeded["admin_headers"],
        [
            (DOC_NAME, txt_bytes(DOC_CONTENT)),
            (DOC_TWO_NAME, txt_bytes(DOC_TWO_CONTENT)),
        ],
    )
    runtime = Runtime(
        provider=DeterministicProvider(),
        executor=McpToolClient(url=mcp_url),
    )
    set_runtime(runtime)
    try:
        status, events = await read_stream(
            client,
            seeded["student_token"],
            {
                "client_request_id": "creq_e2e_mcp_multi",
                "message": "实验课预习要求是什么？",
            },
        )
        assert status == 200, events
        validate_sse_events(events)

        start = [
            event
            for event in events
            if event["event"] == "tool_start"
            and event["data"]["tool_name"] == "search_course_docs"
        ]
        assert len(start) == 1
        tool_end = next(
            event
            for event in events
            if event["event"] == "tool_end"
            and event["data"]["tool_call_id"] == start[0]["data"]["tool_call_id"]
        )
        assert tool_end["data"]["success"] is True, tool_end
        assert tool_end["data"]["result_status"] == "ok"
        assert tool_end["data"].get("code") is None

        done = events[-1]["data"]
        assert done["state"] == "succeeded"
        assert done["citations"], "真实 MCP 检索必须产生 citations（不得 MCP_UNAVAILABLE）"
        assert {item["file_name"] for item in done["citations"]} <= {
            DOC_NAME,
            DOC_TWO_NAME,
        }

        citation = done["citations"][0]
        expand = await client.get(
            f"/api/v1/citations/{citation['reference_id']}",
            headers=AUTH(seeded["student_token"]),
        )
        assert expand.status_code == 200
        assert expand.json()["data"]["reference"]["reference_id"] == citation["reference_id"]
    finally:
        set_runtime(None)


async def test_real_evidence_flows_into_sse_citations_and_expands(
    client, seeded, internal_url
):
    # 1) 真实发布：admin 上传 txt → worker --once 建库/发布
    batch_id = await publish_batch(
        client,
        seeded["admin_headers"],
        [(DOC_NAME, txt_bytes(DOC_CONTENT))],
    )
    assert batch_id

    # 2) 学生提问：真实检索 + SSE
    runtime = Runtime(
        provider=DeterministicProvider(),
        executor=InternalToolExecutor(internal_url, get_settings().service_token),
    )
    set_runtime(runtime)
    try:
        status, events = await read_stream(
            client,
            seeded["student_token"],
            {
                "client_request_id": "creq_e2e_knowledge",
                "message": "实验课预习要求是什么？",
            },
        )
        assert status == 200, events
        validate_sse_events(events)

        start = [
            event
            for event in events
            if event["event"] == "tool_start"
            and event["data"]["tool_name"] == "search_course_docs"
        ]
        assert len(start) == 1
        tool_end = [
            event
            for event in events
            if event["event"] == "tool_end"
            and event["data"]["tool_call_id"] == start[0]["data"]["tool_call_id"]
        ]
        assert len(tool_end) == 1
        assert tool_end[0]["data"]["success"] is True
        assert tool_end[0]["data"]["result_status"] == "ok"

        done = events[-1]["data"]
        assert done["state"] == "succeeded"
        assert done["citations"], "真实检索必须产生权威引用"
        citation = done["citations"][0]
        assert citation["reference_id"].startswith("cit_")
        assert citation["reference_id"] != "cit_stub_syllabus_0001", "不得再返回固定 stub"
        assert citation["file_name"] == DOC_NAME
        assert citation["document_id"] != "doc_stub_syllabus"

        # 3) 引用展开：GET /citations/{reference_id}
        expand = await client.get(
            f"/api/v1/citations/{citation['reference_id']}",
            headers=AUTH(seeded["student_token"]),
        )
        assert expand.status_code == 200, expand.text
        payload = expand.json()["data"]
        assert payload["reference"]["reference_id"] == citation["reference_id"]
        assert payload["reference"]["document_id"] == citation["document_id"]
        assert payload["reference"]["file_name"] == DOC_NAME
        assert "预习报告" in payload["text"]
        assert payload["reference"]["location_label"]

        # 4) 回答正文引用了真实文件（而不是 stub）
        answer_text = "".join(
            event["data"]["text_delta"]
            for event in events
            if event["event"] == "token"
        )
        assert DOC_NAME in answer_text
        assert "预习报告" in answer_text
    finally:
        set_runtime(None)


async def test_citation_requires_owner_session(client, seeded, internal_url):
    """引用展开只对登录用户开放；未知/失效引用返回 CITATION_UNAVAILABLE。"""
    response = await client.get(
        "/api/v1/citations/cit_unknown_x", headers=AUTH(seeded["student_token"])
    )
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "CITATION_UNAVAILABLE"

    anonymous = await client.get("/api/v1/citations/cit_unknown_x")
    assert anonymous.status_code == 401
