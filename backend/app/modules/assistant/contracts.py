"""助手模块契约模型（字段以 ``contracts/openapi_v0.1.json``、
``sse_events_v0.1.schema.json``、``mcp_tools_v0.1.json`` 为权威）。

集中三处共用：
1. 公共端点请求/响应（``ChatInput`` / ``ChatState`` / ``Cancel``）；
2. 内部 API 请求/响应（兑换与三工具）；
3. SSE 六类事件 data。

另含 runner 侧的**工具白名单参数校验**（不依赖模型输出做可信判断）。
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.errors import ApiError, validation_error

ID_PATTERN = r"^[A-Za-z0-9_-]+$"
OPERATION_PATTERN = r"^[A-Za-z0-9._:-]+$"
TIME_PATTERN = r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"
TOOL_NAME_PATTERN = r"^[A-Za-z0-9_-]+$"

ID = Annotated[str, Field(min_length=1, max_length=64, pattern=ID_PATTERN)]
OPERATION_ID = Annotated[str, Field(min_length=1, max_length=96, pattern=OPERATION_PATTERN)]
TIME_TEXT = Annotated[str, Field(pattern=TIME_PATTERN)]

TOOL_NAMES: tuple[str, ...] = ("get_my_schedule", "search_course_docs", "save_study_plan")

TOOL_DISPLAY_NAMES: dict[str, str] = {
    "get_my_schedule": "查询我的课表",
    "search_course_docs": "检索课程资料",
    "save_study_plan": "保存学习计划",
}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# 1. 公共端点
# --------------------------------------------------------------------------- #
class HistoryMessageIn(_Model):
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=20_000)]


class ChatInput(_Model):
    client_request_id: Annotated[str, Field(min_length=1, max_length=64, pattern=ID_PATTERN)]
    # 设计包为可选非 nullable；显式 null 不再接受
    conversation_id: Annotated[
        str, Field(min_length=1, max_length=64, pattern=ID_PATTERN)
    ] = None  # type: ignore[assignment]
    message: Annotated[str, Field(min_length=1, max_length=2000)]
    history: Annotated[list[HistoryMessageIn], Field(max_length=40)] = None  # type: ignore[assignment]

    @field_validator("message")
    @classmethod
    def _reject_blank_after_strip(cls, value: str) -> str:
        """SRS FR-CHAT-001：问题去空白后非空才接受（全角空格同样算空白）。"""
        stripped = value.strip()
        if not stripped:
            raise ValueError("消息不能为空白")
        return stripped


class ChatState(_Model):
    request_id: ID
    conversation_id: ID
    state: Literal["accepted", "running", "succeeded", "failed", "cancelled"]
    cancel_requested: bool
    accepted_at: str
    finished_at: str | None
    model_calls: Annotated[int, Field(ge=0)]
    tool_calls: Annotated[int, Field(ge=0)]
    terminal_reason: Annotated[str, Field(min_length=1, max_length=64)] = None  # type: ignore[assignment]
    plan_id: ID = None  # type: ignore[assignment]
    operation_id: Annotated[str, Field(min_length=1, max_length=96)] = None  # type: ignore[assignment]


class CancelOutput(_Model):
    accepted: bool
    request: ChatState


# --------------------------------------------------------------------------- #
# 2. 内部 API
# --------------------------------------------------------------------------- #
class DelegationExchangeInput(_Model):
    delegation: Annotated[str, Field(min_length=1, max_length=8192)]


class DelegationExchangeOutput(_Model):
    delegation: Annotated[str, Field(min_length=1, max_length=8192)]
    audience: Literal["cca-internal"]
    expires_at: str


class ScheduleToolInput(_Model):
    # 设计包为可选非 nullable；显式 null 不再接受
    from_date: date = None  # type: ignore[assignment]
    to_date: date = None  # type: ignore[assignment]


class ScheduleItem(_Model):
    id: ID
    student_id: ID
    course_id: ID
    course_name: Annotated[str, Field(min_length=1, max_length=100)]
    class_date: str
    start_time: TIME_TEXT
    end_time: TIME_TEXT
    location: Annotated[str, Field(min_length=0, max_length=200)] | None
    version: Annotated[int, Field(ge=1)]


class ScheduleToolOutput(_Model):
    status: Literal["ok", "empty"]
    from_date: str
    to_date: str
    school_timezone: Annotated[str, Field(min_length=1, max_length=64)]
    items: list[ScheduleItem]


class SearchToolInput(_Model):
    query: Annotated[str, Field(min_length=1, max_length=2000)]


class EvidenceChunkOut(_Model):
    chunk_id: ID
    reference_id: ID
    document_id: ID
    version_id: ID
    text: Annotated[str, Field(min_length=1, max_length=20_000)]
    location_label: Annotated[str, Field(min_length=1, max_length=100)]
    page_number: Annotated[int, Field(ge=1)] = None  # type: ignore[assignment]


class ReferenceOut(_Model):
    reference_id: ID
    document_id: ID
    version_id: ID
    file_name: Annotated[str, Field(min_length=1, max_length=255)]
    location_label: Annotated[str, Field(min_length=1, max_length=100)]
    page_number: Annotated[int, Field(ge=1)] = None  # type: ignore[assignment]


class SearchToolOutput(_Model):
    status: Literal["ok", "empty"]
    corpus_empty: bool
    revision: Annotated[int, Field(ge=0)]
    chunks: list[EvidenceChunkOut]
    references: list[ReferenceOut]


class SaveToolInput(_Model):
    draft_id: ID
    draft_version: Annotated[int, Field(ge=1)]


class SaveToolOutput(_Model):
    # deleted：计划已被删除，重放保存必须回报墓碑（§7.3），不能伪装成 existing
    status: Literal["created", "existing", "deleted"]
    operation_id: OPERATION_ID
    plan_id: ID


class WriteOperationOut(_Model):
    operation_id: OPERATION_ID
    state: Literal["pending", "succeeded", "failed", "deleted"]
    resolution: Literal["confirmed", "recovering"]
    plan_id: ID = None  # type: ignore[assignment]
    error_code: Annotated[str, Field(min_length=1, max_length=64)] = None  # type: ignore[assignment]
    retryable: bool


# --------------------------------------------------------------------------- #
# 3. SSE 六类事件 data（seq 由统一写出器分配）
# --------------------------------------------------------------------------- #
class StatusData(_Model):
    request_id: ID
    seq: Annotated[int, Field(ge=1)]
    timestamp: str
    code: Annotated[str, Field(min_length=1, max_length=64)]
    message: Annotated[str, Field(min_length=1, max_length=500)]
    conversation_id: ID | None = None
    draft_id: ID | None = None
    draft_version: Annotated[int, Field(ge=1)] | None = None


class ToolStartData(_Model):
    request_id: ID
    seq: Annotated[int, Field(ge=1)]
    timestamp: str
    tool_call_id: Annotated[str, Field(min_length=1, max_length=64, pattern=TOOL_NAME_PATTERN)]
    tool_name: Literal["get_my_schedule", "search_course_docs", "save_study_plan"]
    display_name: Annotated[str, Field(min_length=1, max_length=500)]


class ToolEndData(_Model):
    request_id: ID
    seq: Annotated[int, Field(ge=1)]
    timestamp: str
    tool_call_id: Annotated[str, Field(min_length=1, max_length=64, pattern=TOOL_NAME_PATTERN)]
    success: bool
    result_status: Literal["ok", "empty", "created", "existing", "failed"]
    code: Annotated[str | None, Field(max_length=64)] = None
    plan_id: ID | None = None
    operation_id: OPERATION_ID | None = None
    # 仅 search_course_docs 成功时出现：true = 全库尚无已发布资料（S05 第 3 态「全库为空」），
    # 与「库里有资料但本次没检索到」（S05 第 2 态「依据不足」）是两个不同的产品状态。
    corpus_empty: bool | None = None


class TokenData(_Model):
    request_id: ID
    seq: Annotated[int, Field(ge=1)]
    timestamp: str
    text_delta: Annotated[str, Field(min_length=1, max_length=4096)]
    answer_block_id: ID


class DoneData(_Model):
    request_id: ID
    seq: Annotated[int, Field(ge=1)]
    timestamp: str
    state: Literal["succeeded", "cancelled"]
    reason: Annotated[str | None, Field(max_length=64)] = None
    citations: list[ReferenceOut]
    plan_id: ID | None = None
    operation_id: OPERATION_ID | None = None


class ErrorData(_Model):
    request_id: ID
    seq: Annotated[int, Field(ge=1)]
    timestamp: str
    state: Literal["failed"]
    code: Annotated[str, Field(min_length=1, max_length=64)]
    message: Annotated[str, Field(min_length=1, max_length=500)]
    plan_id: ID | None = None
    operation_id: OPERATION_ID | None = None


# --------------------------------------------------------------------------- #
# 4. runner 侧工具参数白名单校验（先检查后执行）
# --------------------------------------------------------------------------- #
_ARGUMENT_KEYS: dict[str, frozenset[str]] = {
    "get_my_schedule": frozenset({"from_date", "to_date"}),
    "search_course_docs": frozenset({"query"}),
    "save_study_plan": frozenset({"draft_id", "draft_version"}),
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID_RE = re.compile(ID_PATTERN)


def validate_tool_call(tool_name: str, arguments: Any) -> dict[str, Any]:
    """严格的工具名 + 参数白名单校验；不合法一律 422，不进入执行。"""
    if tool_name not in TOOL_NAMES:
        raise ApiError("FORBIDDEN", message="工具不在白名单内")
    if not isinstance(arguments, dict):
        raise validation_error(("arguments", "工具参数必须是对象"))
    allowed = _ARGUMENT_KEYS[tool_name]
    unknown = sorted(set(arguments) - set(allowed))
    if unknown:
        raise validation_error(*[(key, "不允许的工具参数") for key in unknown])

    if tool_name == "get_my_schedule":
        parsed: dict[str, Any] = {}
        for key in ("from_date", "to_date"):
            raw = arguments.get(key)
            if raw is None:
                continue
            if not isinstance(raw, str) or not _DATE_RE.match(raw):
                raise validation_error((key, "日期格式必须是 YYYY-MM-DD"))
            try:
                parsed[key] = date.fromisoformat(raw)
            except ValueError:
                raise validation_error((key, "日期不合法")) from None
        start = parsed.get("from_date")
        end = parsed.get("to_date")
        if start and end and start > end:
            raise validation_error(("to_date", "结束日期不能早于开始日期"))
        if start and end and (end - start).days > 31:
            raise validation_error(("to_date", "查询跨度不能超过 31 天"))
        return {key: value.isoformat() for key, value in parsed.items()}

    if tool_name == "search_course_docs":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise validation_error(("query", "检索内容不能为空"))
        if len(query) > 2000:
            raise validation_error(("query", "检索内容过长"))
        return {"query": query}

    # save_study_plan
    draft_id = arguments.get("draft_id")
    draft_version = arguments.get("draft_version")
    if not isinstance(draft_id, str) or not _ID_RE.match(draft_id) or len(draft_id) > 64:
        raise validation_error(("draft_id", "草稿标识不合法"))
    if isinstance(draft_version, bool) or not isinstance(draft_version, int) or draft_version < 1:
        raise validation_error(("draft_version", "草稿版本必须是正整数"))
    return {"draft_id": draft_id, "draft_version": draft_version}


def sse_dump(model: BaseModel) -> dict[str, Any]:
    """SSE data 序列化：去掉 None（schema ``additionalProperties:false``）。"""
    return model.model_dump(mode="json", exclude_none=True)


def contract_dump(model: BaseModel) -> dict[str, Any]:
    """按 ``contracts/mcp_tools_v0.1.json`` 序列化工具输入输出。

    ``exclude_none`` 会连"**必填但可空**"的字段一起抹掉，而契约只把"可选非 nullable"
    的字段从 ``required`` 里去掉。两者混用就会出现下面这种事故（2026-10-29 实测）：

    - ``ScheduleItem.location`` 在契约里是 ``required: true`` + ``anyOf [string, null]``；
    - 内部端点 ``exclude_none=True`` 抹掉 ``location`` → MCP 侧 pydantic 报
      ``items.N.location Field required`` → 兜底成 ``MCP_UNAVAILABLE``；
    - 结果是**只要某天有一节课没填地点，整个课表工具就 100% 不可用**。

    所以判据必须是 pydantic 的 ``field.is_required()``（它与输出 schema 的 required
    列表同源）：必填且值为 None 的字段补回 null，可选字段继续省略。
    """
    payload = model.model_dump(mode="json", exclude_none=True)
    _restore_required_nones(model, payload)
    return payload


def _restore_required_nones(model: Any, payload: Any) -> None:
    """递归把"必填但值为 None"的字段补回 payload（见 :func:`contract_dump`）。"""
    if not isinstance(payload, dict) or model is None:
        return
    fields = getattr(type(model), "model_fields", {})
    for name, field in fields.items():
        if name not in payload:
            if field.is_required():
                payload[name] = None
            continue
        value = getattr(model, name, None)
        if isinstance(value, list) and isinstance(payload.get(name), list):
            for item, dumped in zip(value, payload[name]):
                _restore_required_nones(item, dumped)
        elif isinstance(value, BaseModel):
            _restore_required_nones(value, payload[name])


__all__ = [
    "contract_dump",
    "CancelOutput",
    "ChatInput",
    "ChatState",
    "DelegationExchangeInput",
    "DelegationExchangeOutput",
    "DoneData",
    "ErrorData",
    "EvidenceChunkOut",
    "HistoryMessageIn",
    "ReferenceOut",
    "SaveToolInput",
    "SaveToolOutput",
    "ScheduleItem",
    "ScheduleToolInput",
    "ScheduleToolOutput",
    "SearchToolInput",
    "SearchToolOutput",
    "StatusData",
    "TOOL_DISPLAY_NAMES",
    "TOOL_NAMES",
    "TokenData",
    "ToolEndData",
    "ToolStartData",
    "WriteOperationOut",
    "sse_dump",
    "validate_tool_call",
]
