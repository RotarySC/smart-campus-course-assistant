"""MCP / 内部服务适配层（Phase 3）。

- ``delegation``：应用签发的短期委派凭据（pyjwt HS256，双跳 audience）；
- ``client``：API 侧 MCP 客户端（SDK streamable HTTP）与 MCP 侧内部 API 客户端。
"""

from __future__ import annotations

from app.adapters.mcp.client import InternalToolClient, McpToolClient
from app.adapters.mcp.delegation import (
    ALL_SCOPES,
    AUD_INTERNAL,
    AUD_MCP,
    ISSUER,
    SCOPE_DOCS_SEARCH,
    SCOPE_PLAN_SAVE,
    SCOPE_SCHEDULE_READ,
    DelegationClaims,
    JtiRegistry,
    consume_jti,
    mint_delegation,
    reset_jti_registry,
    verify_delegation,
)

__all__ = [
    "ALL_SCOPES",
    "AUD_INTERNAL",
    "AUD_MCP",
    "ISSUER",
    "SCOPE_DOCS_SEARCH",
    "SCOPE_PLAN_SAVE",
    "SCOPE_SCHEDULE_READ",
    "DelegationClaims",
    "InternalToolClient",
    "JtiRegistry",
    "McpToolClient",
    "consume_jti",
    "mint_delegation",
    "reset_jti_registry",
    "verify_delegation",
]
