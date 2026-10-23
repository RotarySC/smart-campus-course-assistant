"""MCP server 入口桩（Phase 3 实现私有 Streamable HTTP，端口 8102）。

本阶段只保证模块可导入、可启动（打印未启用后正常退出），不开放任何工具。
"""

from __future__ import annotations

import logging

logger = logging.getLogger("cca.mcp")

MCP_ENABLED = False
MCP_PATH = "/mcp"


def create_mcp_app():  # pragma: no cover - Phase 3
    raise NotImplementedError("MCP server 在 Phase 3 实现（mcp 2.3.0 streamable_http_app）")


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    logger.warning("MCP server 尚未启用（Phase 3 交付）；本进程空转退出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
