"""请求上下文与命令数据结构（设计 §2.3）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

Role = Literal["student", "admin"]
Source = Literal["manual", "assistant"]
AuthorizationKind = Literal["manual_form", "draft_button", "direct_instruction"]


@dataclass(frozen=True)
class ActorContext:
    """认证依赖构造；调用方不得自行拼接 user_id/role。"""

    user_id: str
    session_id: str
    auth_version: int
    role: Role
    trace_request_id: str
    account: str = ""
    display_name: str = ""
    user_version: int = 0
    enabled: bool = True
    session_expires_at: datetime | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass(frozen=True)
class ExecutionContext:
    """助手执行上下文（Phase 3 使用；本阶段只冻结结构）。"""

    actor: ActorContext
    chat_request_id: str
    conversation_id: str
    accepted_at: datetime
    school_timezone: str
    deadline_at: datetime
    execution_fence: int


@dataclass
class SaveCommand:
    """保存命令（服务端映射 source/用户/许可；本阶段公开入口为 draft_button）。"""

    source: Source
    operation_id: str
    draft_id: str | None = None
    draft_version: int | None = None
    authorization_kind: AuthorizationKind = "draft_button"
    authorization_chat_request_id: str | None = None
    origin_chat_request_id: str | None = None
    manual_fields: dict[str, Any] = field(default_factory=dict)
