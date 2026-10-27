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
    parser.add_argument(
        "--sweep-orphans",
        action="store_true",
        help="只跑一次孤立文件巡检（设计 §10.1）后退出，不处理任务队列",
    )
    parser.add_argument(
        "--no-startup-sweep",
        action="store_true",
        help="常驻模式启动时不跑孤立文件巡检（默认启动即扫，FR-DOC-007）",
    )
    parser.add_argument(
        "--sweep-min-age",
        type=float,
        default=0.0,
        help="巡检只清理「早于 N 秒未修改」的文件（0 = 用默认 3600 秒）",
    )
    return parser


async def _main(args: argparse.Namespace) -> int:
    owner = args.owner or instance_id()
    try:
        if args.sweep_orphans:
            from app.modules.knowledge.sweep import (
                ORPHAN_MIN_AGE_SECONDS,
                sweep_orphan_objects,
            )

            min_age = args.sweep_min_age or ORPHAN_MIN_AGE_SECONDS
            result = await sweep_orphan_objects(min_age_seconds=min_age)
            logger.info("orphan sweep finished: %s", result)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.once:
            result = await run_once(owner, max_tasks=max(1, args.max_tasks))
            logger.info("worker round finished: %s", result)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        # FR-DOC-007 / 设计 §10.1：常驻 worker 启动时先做一次孤立文件巡检。
        # 阈值 1 小时，不会碰到正在上传/写入的文件。
        if not args.no_startup_sweep:
            from app.modules.knowledge.sweep import sweep_orphan_objects

            try:
                swept = await sweep_orphan_objects()
                logger.info("startup orphan sweep: %s", swept)
            except Exception:  # noqa: BLE001 - 巡检失败不得阻止 worker 启动
                logger.exception("startup orphan sweep failed")
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
