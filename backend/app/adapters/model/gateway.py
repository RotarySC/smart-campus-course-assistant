"""模型网关契约（设计 §8.2；Phase 3 A1）。

不变量（PHASE-03 §3）：
- 模型永远不接收、也不能伪造用户身份与许可：``ModelContext`` 里没有 user_id / session_id，
  只有本轮 request/conversation 标识、用户问题、受控历史与工具证据。
- 工具 arguments 只来自白名单 schema（runner 侧校验，见 ``modules.assistant.contracts``）。
- 保存许可只由服务端签发；provider 只能给出 ``DraftIntent.save_candidate`` 候选。

动作类型（同一轮里按需返回其一）：
- ``ToolCall``    请求执行一个白名单工具；
- ``DraftIntent`` 请求形成一份服务端草稿快照（可带保存候选）；
- ``Answer``      产出最终正文（基于已获证据）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Awaitable, Callable, Literal, Protocol, Union

ToolName = Literal["get_my_schedule", "search_course_docs", "save_study_plan"]

SUPPORTED_TOOL_NAMES: tuple[str, ...] = (
    "get_my_schedule",
    "search_course_docs",
    "save_study_plan",
)

# 工具结果的依赖状态（设计 §8.2：satisfied/empty/failed/ambiguous）
DependencyState = Literal["satisfied", "empty", "failed", "ambiguous"]

MAX_HISTORY_MESSAGES = 40
MAX_HISTORY_CONTENT = 20_000


@dataclass(frozen=True)
class HistoryMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class EvidenceReference:
    """权威引用（只由检索结果构造；模型输出不得成为来源）。"""

    reference_id: str
    document_id: str
    version_id: str
    file_name: str
    location_label: str
    page_number: int | None = None

    def as_public_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "reference_id": self.reference_id,
            "document_id": self.document_id,
            "version_id": self.version_id,
            "file_name": self.file_name,
            "location_label": self.location_label,
        }
        if self.page_number is not None:
            data["page_number"] = int(self.page_number)
        return data


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    reference_id: str
    document_id: str
    version_id: str
    text: str
    location_label: str
    page_number: int | None = None


@dataclass(frozen=True)
class EvidenceSet:
    """``search_course_docs`` 的可信结果。"""

    status: Literal["ok", "empty"]
    corpus_empty: bool
    revision: int
    chunks: tuple[EvidenceChunk, ...] = ()
    references: tuple[EvidenceReference, ...] = ()

    @property
    def reference_ids(self) -> set[str]:
        return {item.reference_id for item in self.references}


@dataclass(frozen=True)
class ToolCall:
    tool_name: ToolName
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DraftIntent:
    """草稿意图：正文由 provider 起草，服务端补身份/会话/版本/操作键。"""

    title: str
    content: str
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    basis_types: tuple[str, ...] = ("general",)
    # 模型对“用户是否明确要求保存”的**候选判断**，不授权任何写入（§7.1 / FR-PLAN-003）。
    save_candidate: bool = False


@dataclass(frozen=True)
class Answer:
    text: str
    basis_types: tuple[str, ...] = ("general",)


ModelAction = Union[ToolCall, DraftIntent, Answer]


@dataclass
class ToolExecutionRecord:
    """runner 实际执行过的工具结果（回灌给 provider 做下一步决策）。"""

    tool_name: str
    arguments: dict[str, Any]
    success: bool
    result_status: str
    dependency_state: DependencyState
    code: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class DraftRecord:
    draft_id: str
    draft_version: int
    operation_id: str


@dataclass
class SaveRecord:
    plan_id: str
    operation_id: str
    status: Literal["created", "existing"]


@dataclass(frozen=True)
class AmbiguousCourse:
    """无法仅凭课程名区分的候选（FR-QA-004：先补问，不擅自挑一门）。

    ``code`` 是用户可见的课程代码；``name`` 是同名课程名，用于把候选分组补问。
    """

    code: str
    name: str


@dataclass
class ModelContext:
    """provider 可见的上下文（无身份字段）。"""

    request_id: str
    conversation_id: str
    message: str
    history: tuple[HistoryMessage, ...]
    accepted_at: datetime
    school_timezone: str
    today: date
    tomorrow: date
    tool_results: list[ToolExecutionRecord] = field(default_factory=list)
    draft: DraftRecord | None = None
    save: SaveRecord | None = None
    # FR-QA-004：本轮问题里的同名课程候选（由服务端按课程目录判定，provider 只决定是否先补问）
    ambiguous_courses: tuple[AmbiguousCourse, ...] = ()

    def result_of(self, tool_name: str) -> ToolExecutionRecord | None:
        for record in reversed(self.tool_results):
            if record.tool_name == tool_name:
                return record
        return None


@dataclass(frozen=True)
class ModelBudget:
    """先检查后分配（设计 §8.2）：剩余决策/工具次数与本轮截止时刻。"""

    remaining_decisions: int
    remaining_tools: int
    deadline_at: datetime


EmitToken = Callable[[str], Awaitable[None]]


class ModelGateway(Protocol):
    async def next_action(self, context: ModelContext, budget: ModelBudget) -> ModelAction: ...

    async def stream_answer(self, answer: Answer, emit: EmitToken) -> None: ...


__all__ = [
    "AmbiguousCourse",
    "Answer",
    "DraftIntent",
    "DraftRecord",
    "DependencyState",
    "EmitToken",
    "EvidenceChunk",
    "EvidenceReference",
    "EvidenceSet",
    "HistoryMessage",
    "MAX_HISTORY_CONTENT",
    "MAX_HISTORY_MESSAGES",
    "ModelAction",
    "ModelBudget",
    "ModelContext",
    "ModelGateway",
    "SUPPORTED_TOOL_NAMES",
    "SaveRecord",
    "ToolCall",
    "ToolExecutionRecord",
    "ToolName",
]
