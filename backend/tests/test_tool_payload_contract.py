"""工具输入输出与 HTTP 响应必须与已发布契约逐键对齐。

两份契约：``contracts/mcp_tools_v0.1.json``（工具）与 ``contracts/openapi_v0.1.json``（HTTP）。

为什么单独有一组用例：``exclude_none=True`` 与"必填但可空"的字段天生冲突，
2026-10-29 就踩了这个坑 —— ``ScheduleItem.location`` 在契约里是
``required: true`` + ``anyOf [string, null]``，内部端点把它按 None 抹掉后，
MCP 侧 pydantic 报 ``location Field required``，兜底成 ``MCP_UNAVAILABLE``；
后果是"只要某天有一节课没填地点，课表工具就 100% 不可用"，而这条链路在
schedule 用例里连坐 7 条。同类字段还有 ``ChatState.finished_at``（运行中的请求
就该是 null），HTTP 端点漏了同样的修复会把 ``/chat/requests/{id}`` 的响应弄成缺键。

这里不去硬编码字段名，而是**直接读契约**：``contract_dump`` 的输出键集合必须
覆盖契约里该 schema 的 ``required`` 列表，可选字段允许出现也允许省略。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.assistant.contracts import (
    CancelOutput,
    ChatState,
    EvidenceChunkOut,
    ReferenceOut,
    ScheduleItem,
    ScheduleToolOutput,
    SearchToolOutput,
    contract_dump,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "contracts" / "mcp_tools_v0.1.json"
OPENAPI = REPO_ROOT / "contracts" / "openapi_v0.1.json"


def _tool_output_schema(tool_name: str) -> dict:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    for tool in payload["tools"]:
        if tool.get("name") == tool_name:
            return tool["outputSchema"]
    raise AssertionError(f"契约里没有工具 {tool_name}")


def _openapi_schema(name: str) -> dict:
    payload = json.loads(OPENAPI.read_text(encoding="utf-8"))
    return payload["components"]["schemas"][name]


def _sample_schedule_item(location: str | None) -> ScheduleItem:
    return ScheduleItem(
        id="sch_test",
        student_id="usr_test",
        course_id="crs_test",
        course_name="数据结构",
        class_date="2026-10-30",
        start_time="08:00",
        end_time="09:40",
        location=location,
        version=1,
    )


def _sample_schedule_output(location: str | None) -> ScheduleToolOutput:
    return ScheduleToolOutput(
        status="ok",
        from_date="2026-10-30",
        to_date="2026-10-30",
        school_timezone="Asia/Shanghai",
        items=[_sample_schedule_item(location)],
    )


def test_schedule_item_keeps_required_nullable_location():
    """无地点课表：location 必须作为 null 出现，不能被 exclude_none 抹掉。"""
    payload = contract_dump(_sample_schedule_output(None))
    item = payload["items"][0]
    assert "location" in item, "location 是必填可空字段，省略键会让 MCP 侧校验失败"
    assert item["location"] is None


def test_schedule_output_has_every_required_key_from_contract():
    """输出键集合覆盖契约 required（多出的键是 optional，允许）。"""
    schema = _tool_output_schema("get_my_schedule")
    required_top = set(schema.get("required", []))
    item_schema = schema["properties"]["items"]["items"]
    required_item = set(item_schema.get("required", []))

    payload = contract_dump(_sample_schedule_output(None))
    assert required_top <= set(payload), f"缺顶层必填键：{required_top - set(payload)}"
    assert required_item <= set(payload["items"][0]), (
        f"缺条目必填键：{required_item - set(payload['items'][0])}"
    )


def test_schedule_item_with_location_still_serialises_string():
    payload = contract_dump(_sample_schedule_output("教学楼 A-201"))
    assert payload["items"][0]["location"] == "教学楼 A-201"


def test_search_output_omits_optional_null_page_number():
    """可选非 nullable（page_number）仍应被省略，别把 null 塞进契约之外的形态。"""
    output = SearchToolOutput(
        status="ok",
        corpus_empty=False,
        revision=1,
        chunks=[
            EvidenceChunkOut(
                chunk_id="chk_1",
                reference_id="cit_1",
                document_id="doc_1",
                version_id="dvs_1",
                text="正文",
                location_label="第 1 节",
                # page_number 是"可选非 nullable"：这里刻意不给值（给 None 会被拒），
                # 序列化后也不应出现 null 键。
            )
        ],
        references=[
            ReferenceOut(
                reference_id="cit_1",
                document_id="doc_1",
                version_id="dvs_1",
                file_name="资料.md",
                location_label="第 1 节",
            )
        ],
    )
    payload = contract_dump(output)
    assert "page_number" not in payload["chunks"][0]
    schema = _tool_output_schema("search_course_docs")
    chunk_schema = schema["properties"]["chunks"]["items"]
    required = set(chunk_schema.get("required", []))
    assert required <= set(payload["chunks"][0])
    assert "page_number" not in required


def test_contract_file_declares_location_required():
    """守住前提：若有人把契约改成"location 可选"，上面的用例就该跟着改，而不是默默失效。"""
    schema = _tool_output_schema("get_my_schedule")
    item_schema = schema["properties"]["items"]["items"]
    assert "location" in item_schema.get("required", [])
    assert item_schema["properties"]["location"]["anyOf"] == [
        {"type": "string", "minLength": 0, "maxLength": 200},
        {"type": "null"},
    ]


# --------------------------------------------------------------------------- #
# HTTP 响应侧：同一类"必填但可空"缺陷（ChatState.finished_at）
# --------------------------------------------------------------------------- #
def _running_state() -> ChatState:
    return ChatState(
        request_id="req_running",
        conversation_id="cnv_running",
        state="running",
        cancel_requested=False,
        accepted_at="2026-10-29T10:00:00+08:00",
        finished_at=None,
        model_calls=0,
        tool_calls=0,
    )


def test_chat_state_keeps_required_nullable_finished_at():
    """运行中的请求 finished_at 就是 null：省略键会让响应缺 required 字段。"""
    payload = contract_dump(_running_state())
    assert "finished_at" in payload, "finished_at 是必填可空字段，省略键即违反契约"
    assert payload["finished_at"] is None
    required = set(_openapi_schema("ChatState").get("required", []))
    assert required <= set(payload), f"缺必填键：{required - set(payload)}"
    assert "finished_at" in required


def test_cancel_output_keeps_contract_required_keys():
    """取消响应内嵌 ChatState：外层与内层都要按契约补齐必填键。"""
    payload = contract_dump(CancelOutput(accepted=True, request=_running_state()))
    required = set(_openapi_schema("Cancel").get("required", []))
    assert required <= set(payload), f"缺必填键：{required - set(payload)}"
    inner_required = set(_openapi_schema("ChatState").get("required", []))
    assert inner_required <= set(payload["request"]), (
        f"取消响应内层缺必填键：{inner_required - set(payload['request'])}"
    )


def test_contract_dump_omits_optional_none_fields():
    """可选非 nullable 字段（如 ChatState.plan_id 默认 None）仍应省略。"""
    payload = contract_dump(_running_state())
    assert "plan_id" not in payload
    assert "plan_id" not in set(_openapi_schema("ChatState").get("required", []))
