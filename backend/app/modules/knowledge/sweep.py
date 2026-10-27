"""孤立文件巡检（设计 §10.1）：按内部引用清理无主对象，绝不碰在途写入。

背景：`fs.copy` 与建行之间崩溃、终态失败的 attempt 产物、上传失败残留的暂存
原件，都会留下没有任何行指向的文件。设计 §10.1 要求"由基于内部引用的巡检清理"。

保守策略：
- 只删「没有任何数据库行引用」的文件；
- 只删「最后修改时间早于 ``min_age_seconds``」的文件 —— 在途上传/写入的文件
  刚写完，不会被误删；
- 向量命名空间不在这里枚举（本地向量库没有公开的命名空间清单接口），
  由"终态失败即时回收"与批次/文档清理负责。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import select

from app.adapters.db.engine import session_scope
from app.adapters.db.models import Document, StorageAttempt
from app.adapters.db.uow import uow
from app.adapters.filestore.local import StorageError
from app.modules.knowledge.adapters import file_store
from app.modules.operations.service import append_audit

logger = logging.getLogger("cca.knowledge.sweep")

# 默认一小时：既覆盖残留回收，又不会碰到「刚写完还没建行」的在途文件。
ORPHAN_MIN_AGE_SECONDS = 3600


async def sweep_orphan_objects(
    *, min_age_seconds: float = ORPHAN_MIN_AGE_SECONDS
) -> dict[str, Any]:
    """巡检并删除无主文件，返回各类计数；写一条 ``storage.orphan_sweep`` 审计。"""
    fs = file_store()
    cutoff = time.time() - max(0.0, float(min_age_seconds))

    async with session_scope() as session:
        document_keys = set(
            (
                await session.execute(
                    select(Document.original_storage_key).where(
                        Document.original_storage_key.is_not(None)
                    )
                )
            )
            .scalars()
            .all()
        )
        # 只有「未清理」的 attempt 才算引用：已 cleaned 的 attempt 其产物就该被回收，
        # 这正是终态失败残留能被巡检兜底的原因。
        attempt_prefixes = tuple(
            (
                await session.execute(
                    select(StorageAttempt.file_prefix).where(
                        StorageAttempt.io_state != "cleaned"
                    )
                )
            )
            .scalars()
            .all()
        )

    result: dict[str, Any] = {
        "scanned": 0,
        "documents": 0,
        "attempts": 0,
        "uploads": 0,
        "kept_recent": 0,
        "errors": 0,
        "min_age_seconds": int(min_age_seconds),
    }

    def _old_enough(key: str) -> bool:
        try:
            return fs.path_of(key).stat().st_mtime <= cutoff
        except OSError:
            return False

    def _delete(group: str, key: str) -> None:
        result[group] += 1
        try:
            fs.delete(key)
        except StorageError as exc:  # 单键失败不拖垮整轮巡检
            logger.warning("orphan sweep delete failed key=%s err=%s", key, exc)
            result["errors"] += 1

    for key in fs.list_keys("documents"):
        result["scanned"] += 1
        if key in document_keys:
            continue
        if not _old_enough(key):
            result["kept_recent"] += 1
            continue
        _delete("documents", key)

    for key in fs.list_keys("attempts"):
        result["scanned"] += 1
        if any(key.startswith(prefix) for prefix in attempt_prefixes):
            continue
        if not _old_enough(key):
            result["kept_recent"] += 1
            continue
        _delete("attempts", key)

    for key in fs.list_keys("uploads"):
        result["scanned"] += 1
        if not _old_enough(key):
            result["kept_recent"] += 1
            continue
        _delete("uploads", key)

    async with uow() as tx:
        append_audit(
            tx,
            action="storage.orphan_sweep",
            object_type="storage",
            object_id="filestore",
            result="success",
            request_id="worker",
            metadata=dict(result),
        )
        await tx.commit()

    logger.info("orphan sweep finished: %s", result)
    return result


__all__ = ["ORPHAN_MIN_AGE_SECONDS", "sweep_orphan_objects"]
