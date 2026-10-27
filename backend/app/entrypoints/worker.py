"""Worker 入口：持久任务轮询 / 租约 / 心跳 / 重试 / 发布与清理。

用法：
    python -m app.entrypoints.worker            # 常驻轮询（1s）
    python -m app.entrypoints.worker --once     # 跑一轮（测试/运维单次排空）

``--once`` 在单次进程内按队列顺序处理到期任务直到队列为空或达到上限，
因此上传后一次调用即可完成“解析→入库→发布”。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from app.adapters.db.engine import dispose_engine
from app.modules.knowledge.adapters import POLL_SECONDS
from app.modules.knowledge.tasks import instance_id, run_forever, run_once

logger = logging.getLogger("cca.worker")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校园课程智能助手 · 文档 Worker")
    parser.add_argument("--once", action="store_true", help="单轮执行后排空退出")
    parser.add_argument(
        "--max-tasks", type=int, default=100, help="单轮最多处理任务数（默认 100）"
    )
    parser.add_argument("--owner", default="", help="实例标识（默认自动生成）")
    parser.add_argument(
        "--poll-seconds", type=float, default=POLL_SECONDS, help="空队列轮询间隔（秒）"
    )
    return parser


async def _main(args: argparse.Namespace) -> int:
    owner = args.owner or instance_id()
    try:
        if args.once:
            result = await run_once(owner, max_tasks=max(1, args.max_tasks))
            logger.info("worker round finished: %s", result)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        await run_forever(owner, poll_seconds=args.poll_seconds)
        return 0
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    # NFR-PRIV-001：worker 日志同样不落正文/凭据（含异常里的 SQLAlchemy 参数块）
    from app.shared.log_redaction import install_redaction

    install_redaction()
    args = build_parser().parse_args(argv)
    return asyncio.run(_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
