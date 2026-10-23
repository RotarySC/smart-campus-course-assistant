"""助手运行时配置（Phase 3 自有；不改 ``app/config.py`` 单写者文件）。

默认值来自设计（§8.2/§8.4 / PHASE-03 §4）；可用环境变量覆盖，便于部署与测试：

- ``CCA_INTERNAL_API_URL``（默认 http://127.0.0.1:8101）
- ``CCA_MCP_URL``（默认 http://127.0.0.1:8102/mcp）
- ``CCA_MCP_HOST`` / ``CCA_MCP_PORT`` / ``CCA_MCP_PATH``（默认 127.0.0.1 / 8102 / /mcp）
- ``CCA_ASSISTANT_CAPACITY_SLOTS``（默认 5，仅接受时预置 5 行，运行期不改变）
- ``CCA_ASSISTANT_DEADLINE_SECONDS``（默认 60）
- ``CCA_ASSISTANT_MODEL_DECISIONS``（默认 6）
- ``CCA_ASSISTANT_TOOL_CALLS``（默认 10）
- ``CCA_ASSISTANT_LEASE_SECONDS``（默认 30）/ ``CCA_ASSISTANT_LEASE_RENEW_SECONDS``（默认 10）
- ``CCA_ASSISTANT_HEARTBEAT_SECONDS``（默认 15）
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from functools import lru_cache


def _int_env(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def _float_env(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


@dataclass(frozen=True)
class AssistantSettings:
    internal_api_url: str = "http://127.0.0.1:8101"
    mcp_url: str = "http://127.0.0.1:8102/mcp"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8102
    mcp_path: str = "/mcp"

    capacity_slots: int = 5
    deadline_seconds: int = 60
    model_decision_limit: int = 6
    tool_call_limit: int = 10
    lease_seconds: int = 30
    lease_renew_seconds: int = 10

    event_queue_blocks: int = 64
    backpressure_seconds: float = 2.0
    max_buffer_events: int = 2048
    heartbeat_seconds: float = 15.0

    token_chunk_limit: int = 4096
    max_text_length: int = 20_000

    instance_id: str = field(default_factory=lambda: f"ins_{uuid.uuid4().hex[:16]}")

    @property
    def mcp_origin(self) -> str:
        return f"http://{self.mcp_host}:{self.mcp_port}"


def load_assistant_settings() -> AssistantSettings:
    return AssistantSettings(
        internal_api_url=os.environ.get("CCA_INTERNAL_API_URL", "").strip()
        or "http://127.0.0.1:8101",
        mcp_url=os.environ.get("CCA_MCP_URL", "").strip() or "http://127.0.0.1:8102/mcp",
        mcp_host=os.environ.get("CCA_MCP_HOST", "").strip() or "127.0.0.1",
        mcp_port=_int_env("CCA_MCP_PORT", 8102, minimum=1),
        mcp_path=os.environ.get("CCA_MCP_PATH", "").strip() or "/mcp",
        capacity_slots=_int_env("CCA_ASSISTANT_CAPACITY_SLOTS", 5, minimum=1),
        deadline_seconds=_int_env("CCA_ASSISTANT_DEADLINE_SECONDS", 60, minimum=1),
        model_decision_limit=_int_env("CCA_ASSISTANT_MODEL_DECISIONS", 6, minimum=1),
        tool_call_limit=_int_env("CCA_ASSISTANT_TOOL_CALLS", 10, minimum=1),
        lease_seconds=_int_env("CCA_ASSISTANT_LEASE_SECONDS", 30, minimum=1),
        lease_renew_seconds=_int_env("CCA_ASSISTANT_LEASE_RENEW_SECONDS", 10, minimum=1),
        event_queue_blocks=_int_env("CCA_ASSISTANT_QUEUE_BLOCKS", 64, minimum=1),
        backpressure_seconds=_float_env("CCA_ASSISTANT_BACKPRESSURE_SECONDS", 2.0),
        max_buffer_events=_int_env("CCA_ASSISTANT_MAX_BUFFER_EVENTS", 2048, minimum=64),
        heartbeat_seconds=_float_env("CCA_ASSISTANT_HEARTBEAT_SECONDS", 15.0),
        token_chunk_limit=_int_env("CCA_ASSISTANT_TOKEN_CHUNK_LIMIT", 4096, minimum=1),
        max_text_length=_int_env("CCA_ASSISTANT_MAX_TEXT_LENGTH", 20_000, minimum=1),
    )


@lru_cache(maxsize=1)
def get_assistant_settings() -> AssistantSettings:
    return load_assistant_settings()


def reset_assistant_settings() -> None:
    get_assistant_settings.cache_clear()


__all__ = [
    "AssistantSettings",
    "get_assistant_settings",
    "load_assistant_settings",
    "reset_assistant_settings",
]
