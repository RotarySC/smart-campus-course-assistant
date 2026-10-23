"""Worker 入口（Phase 1 骨架）：空转一轮 Outbox no-op 派发后退出。

用法：``python -m app.entrypoints.worker``（Phase 2 接入真实任务领取）。
"""

from __future__ import annotations

import asyncio
import logging

from app.adapters.db.engine import dispose_engine
from app.modules.operations.service import dispatch_outbox_once

logger = logging.getLogger("cca.worker")


async def run_once() -> int:
    """执行一轮轮询：本阶段只做 Outbox 去重与 no-op 派发。"""
    dispatched = await dispatch_outbox_once()
    logger.info("worker round finished: outbox_dispatched=%s", dispatched)
    return dispatched


async def _main() -> None:
    try:
        await run_once()
    finally:
        await dispose_engine()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())


if __name__ == "__main__":
    main()
