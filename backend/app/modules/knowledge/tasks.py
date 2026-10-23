"""文档 Worker：持久任务领取 / 租约 / 心跳 / 重试 / 入库发布 / 清理。

设计依据：后端详细设计 §10（全文）、§5.2 锁顺序 / §7.2 状态模型。

核心不变量：
- 写作用域（发布/删除/清理）在事务内先校验任务代次（owner+fence+lease_until），
  **丢失租约的执行代次不得发布**；迟到的旧代次写入由 VectorStore 屏障拒绝。
- 整批发布：所有文件版本 ready 且索引可检索后，一次事务切换可见性；半批不可见。
- 失败分类：解析类确定性失败不自动重试；存储/向量/临时故障有限重试（2/4/8/16s + 抖动）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import case, delete, func, select, text, update

from app.adapters.db.engine import get_session_factory, session_scope
from app.adapters.db.models import (
    BackgroundTask,
    Chunk,
    CitationReference,
    CorpusControl,
    Document,
    DocumentBatch,
    DocumentVersion,
    StorageAttempt,
)
from app.adapters.db.uow import UoW, uow
from app.adapters.embedding.deterministic import EmbeddingError
from app.adapters.filestore.local import StorageError
from app.adapters.parser.document_parser import ParserError
from app.adapters.vector.local import LateWriteRejected, VectorStoreError
from app.modules.knowledge.adapters import (
    BACKOFF_SECONDS,
    HEARTBEAT_SECONDS,
    LEASE_SECONDS,
    MAX_ATTEMPTS,
    NON_RETRYABLE_CODES,
    POLL_SECONDS,
    TASK_KIND_BATCH_CLEANUP,
    TASK_KIND_DOC_CLEANUP,
    TASK_KIND_PERSIST,
    TASK_KIND_PUBLISH,
    attempt_file_prefix,
    attempt_manifest_key,
    attempt_namespace,
    attempt_text_key,
    build_chunks,
    corpus_vector_space,
    document_key,
    embedding,
    file_store,
    manifest_payload,
    parse_bytes,
    parser_config_digest,
    vector_store,
)
from app.modules.operations.service import append_audit, append_outbox
from app.shared.clock import now_utc, to_db
from app.shared.ids import (
    PREFIX_ATTEMPT,
    PREFIX_CITATION,
    PREFIX_TASK,
    new_id,
)

logger = logging.getLogger("cca.worker")

# 任务内部错误码（不进入 HTTP 错误映射，只用于任务视图/查询）
RETRYABLE_CODES = frozenset(
    {"EMBEDDING_FAILED", "STORAGE_UNAVAILABLE", "RETRIEVAL_UNAVAILABLE", "PROCESSING_FAILED"}
)


# --------------------------------------------------------------------------- #
# 租约与异常
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ClaimedTask:
    id: str
    kind: str
    object_id: str
    dedupe_key: str
    attempt: int
    max_attempts: int
    fence: int


@dataclass(frozen=True)
class TaskLease:
    claimed: ClaimedTask
    owner: str

    @property
    def task_id(self) -> str:
        return self.claimed.id

    @property
    def fence(self) -> int:
        return self.claimed.fence


class LeaseLost(Exception):
    """执行代次已失效（租约过期/被回收）：不得提交任何业务结果。"""


class TaskFailure(Exception):
    def __init__(self, code: str, *, retryable: bool | None = None, summary: str = "") -> None:
        self.code = code
        self.retryable = (code not in NON_RETRYABLE_CODES) if retryable is None else retryable
        self.summary = (summary or code)[:500]
        super().__init__(self.summary)


def instance_id() -> str:
    return f"{socket.gethostname()[:24]}:{os.getpid()}:{uuid.uuid4().hex[:8]}"[:64]


def _backoff_seconds(attempt: int) -> float:
    index = max(0, min(attempt - 1, len(BACKOFF_SECONDS) - 1))
    base = BACKOFF_SECONDS[index]
    return base * random.uniform(0.75, 1.25)  # 抖动


# --------------------------------------------------------------------------- #
# 领取 / 回收 / 心跳
# --------------------------------------------------------------------------- #
async def claim_next(owner: str) -> ClaimedTask | None:
    """独立短事务领取一条到期任务（FOR UPDATE SKIP LOCKED）。"""
    factory = get_session_factory()
    now = to_db(now_utc())
    lease_until = to_db(now_utc() + timedelta(seconds=LEASE_SECONDS))
    async with factory() as session:
        async with session.begin():
            row = (
                await session.execute(
                    text(
                        "SELECT id FROM background_tasks "
                        "WHERE state IN ('pending','retry_wait') AND next_run_at <= :now "
                        "ORDER BY priority DESC, next_run_at, id LIMIT 1 FOR UPDATE SKIP LOCKED"
                    ),
                    {"now": now},
                )
            ).first()
            if row is None:
                return None
            task_id = row[0]
            await session.execute(
                text(
                    "UPDATE background_tasks SET state='running', owner_instance=:owner, "
                    "lease_until=:lease_until, attempt=attempt+1, fence=fence+1, "
                    "error_code=NULL, error_summary=NULL, updated_at=:now WHERE id=:id"
                ),
                {
                    "owner": owner,
                    "lease_until": lease_until,
                    "now": now,
                    "id": task_id,
                },
            )
            task = (
                await session.execute(
                    select(BackgroundTask).where(BackgroundTask.id == task_id)
                )
            ).scalar_one()
            return ClaimedTask(
                id=task.id,
                kind=task.kind,
                object_id=task.object_id,
                dedupe_key=task.dedupe_key,
                attempt=int(task.attempt),
                max_attempts=int(task.max_attempts),
                fence=int(task.fence),
            )


async def recover_expired_leases() -> int:
    """启动/轮询扫描过期租约：回收为 retry_wait，旧代次由 fence 隔离。"""
    now = to_db(now_utc())
    async with uow() as tx:
        result = await tx.session.execute(
            update(BackgroundTask)
            .where(
                BackgroundTask.state == "running",
                BackgroundTask.lease_until.is_not(None),
                BackgroundTask.lease_until < now,
            )
            .values(
                state="retry_wait",
                owner_instance=None,
                lease_until=None,
                next_run_at=now,
                error_code="SERVICE_RESTARTED",
                error_summary="执行租约过期，任务被回收",
                updated_at=now,
            )
        )
        await tx.commit()
        return int(result.rowcount or 0)


class Heartbeat:
    """10s 续租；续租失败标记 lost，任务提交前会再次校验收敛。"""

    def __init__(self, lease: TaskLease) -> None:
        self.lease = lease
        self.lost = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_SECONDS)
                now = to_db(now_utc())
                lease_until = to_db(now_utc() + timedelta(seconds=LEASE_SECONDS))
                async with uow() as tx:
                    result = await tx.session.execute(
                        update(BackgroundTask)
                        .where(
                            BackgroundTask.id == self.lease.task_id,
                            BackgroundTask.state == "running",
                            BackgroundTask.owner_instance == self.lease.owner,
                            BackgroundTask.fence == self.lease.claimed.fence,
                        )
                        .values(lease_until=lease_until, updated_at=now)
                    )
                    await tx.commit()
                    if int(result.rowcount or 0) == 0:
                        self.lost = True
                        logger.warning("lease lost during heartbeat task=%s", self.lease.task_id)
                        return
        except asyncio.CancelledError:  # pragma: no cover - 正常停止
            raise

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


async def _assert_lease_alive(session: Any, lease: TaskLease) -> None:
    """在同一事务内校验任务代次；失败抛 :class:`LeaseLost`。"""
    now = to_db(now_utc())
    row = (
        await session.execute(
            select(BackgroundTask.id).where(
                BackgroundTask.id == lease.task_id,
                BackgroundTask.state == "running",
                BackgroundTask.owner_instance == lease.owner,
                BackgroundTask.fence == lease.claimed.fence,
                BackgroundTask.lease_until >= now,
            )
        )
    ).first()
    if row is None:
        raise LeaseLost()


async def finish_success(session: Any, lease: TaskLease, *, error_code: str | None = None) -> None:
    """任务成功收尾（可与业务事务同事务提交；在事务末尾调用）。"""
    now = to_db(now_utc())
    result = await session.execute(
        update(BackgroundTask)
        .where(
            BackgroundTask.id == lease.task_id,
            BackgroundTask.state == "running",
            BackgroundTask.owner_instance == lease.owner,
            BackgroundTask.fence == lease.claimed.fence,
            BackgroundTask.lease_until >= now,
        )
        .values(
            state="succeeded",
            owner_instance=None,
            lease_until=None,
            next_run_at=now,
            error_code=error_code,
            error_summary=None,
            updated_at=now,
        )
    )
    if int(result.rowcount or 0) != 1:
        raise LeaseLost()


async def _requeue(session: Any, lease: TaskLease, delay_seconds: float) -> None:
    """不消耗自动重试次数的等待（发布冻结/批次尚未全部就绪）。"""
    now = to_db(now_utc())
    result = await session.execute(
        update(BackgroundTask)
        .where(
            BackgroundTask.id == lease.task_id,
            BackgroundTask.state == "running",
            BackgroundTask.owner_instance == lease.owner,
            BackgroundTask.fence == lease.claimed.fence,
        )
        .values(
            state="retry_wait",
            owner_instance=None,
            lease_until=None,
            attempt=func.greatest(BackgroundTask.attempt - 1, 0),
            next_run_at=to_db(now_utc() + timedelta(seconds=delay_seconds)),
            error_code=None,
            error_summary=None,
            updated_at=now,
        )
    )
    if int(result.rowcount or 0) != 1:
        raise LeaseLost()


# --------------------------------------------------------------------------- #
# 任务登记（供 service 在业务事务内调用）
# --------------------------------------------------------------------------- #
def new_task(
    *,
    kind: str,
    object_id: str,
    dedupe_key: str,
    priority: int = 0,
    delay_seconds: float = 0.0,
    max_attempts: int = MAX_ATTEMPTS,
) -> BackgroundTask:
    now = to_db(now_utc())
    return BackgroundTask(
        id=new_id(PREFIX_TASK),
        kind=kind[:32],
        object_id=object_id,
        dedupe_key=dedupe_key[:96],
        state="pending",
        priority=priority,
        attempt=0,
        max_attempts=max_attempts,
        fence=0,
        owner_instance=None,
        lease_until=None,
        next_run_at=to_db(now_utc() + timedelta(seconds=delay_seconds)),
        error_code=None,
        error_summary=None,
        created_at=now,
        updated_at=now,
    )


async def record_attempt(
    tx: UoW,
    *,
    task_id: str,
    fence: int,
    version_id: str,
    file_prefix: str,
    namespace: str,
    io_state: str = "settled",
) -> str:
    now = to_db(now_utc())
    attempt_id = new_id(PREFIX_ATTEMPT)
    tx.session.add(
        StorageAttempt(
            id=attempt_id,
            task_id=task_id,
            task_fence=int(fence),
            version_id=version_id,
            file_prefix=file_prefix,
            vector_namespace=namespace,
            io_state=io_state,
            inflight_writes=0,
            barrier_confirmed_at=now if io_state == "settled" else None,
            created_at=now,
            updated_at=now,
        )
    )
    return attempt_id


# --------------------------------------------------------------------------- #
# 失败收尾 / 批次补偿
# --------------------------------------------------------------------------- #
async def schedule_failure(
    claimed: ClaimedTask, owner: str, *, code: str, retryable: bool, summary: str = ""
) -> str:
    """失败分类：可重试 → retry_wait + 退避；否则 failed，并触发批次补偿/解除重建互斥。"""
    retry = retryable and claimed.attempt < claimed.max_attempts
    now = to_db(now_utc())
    next_run = to_db(
        now_utc() + timedelta(seconds=_backoff_seconds(claimed.attempt) if retry else 0)
    )
    async with uow() as tx:
        result = await tx.session.execute(
            update(BackgroundTask)
            .where(
                BackgroundTask.id == claimed.id,
                BackgroundTask.state == "running",
                BackgroundTask.owner_instance == owner,
                BackgroundTask.fence == claimed.fence,
            )
            .values(
                state="retry_wait" if retry else "failed",
                owner_instance=None,
                lease_until=None,
                next_run_at=next_run,
                error_code=code[:64],
                error_summary=(summary or code)[:500],
                updated_at=now,
            )
        )
        if int(result.rowcount or 0) != 1:
            await tx.rollback()
            return "lease_lost"
        if claimed.kind in (TASK_KIND_PERSIST, TASK_KIND_DOC_CLEANUP):
            await _apply_failure_scope(tx, claimed, code=code, terminal=not retry, request_id="")
        if claimed.kind == TASK_KIND_BATCH_CLEANUP and not retry:
            batch = await tx.session.get(DocumentBatch, claimed.object_id)
            if batch is not None and batch.state == "compensating":
                batch.error_code = code[:64]
                batch.updated_at = now
        await tx.commit()
    return "retry_wait" if retry else "failed"


async def _apply_failure_scope(
    tx: UoW, claimed: ClaimedTask, *, code: str, terminal: bool, request_id: str
) -> None:
    if claimed.kind == TASK_KIND_DOC_CLEANUP:
        document = await tx.session.get(Document, claimed.object_id)
        if document is not None and terminal:
            document.cleanup_state = "failed"
            document.processing_state = "delete_failed"
            document.mutation_task_id = None
            document.error_code = code[:64]
            document.version = int(document.version) + 1
            document.updated_at = to_db(now_utc())
        return

    version = await tx.session.get(DocumentVersion, claimed.object_id)
    if version is None:
        return
    document = await tx.session.get(Document, version.document_id)
    if document is None:
        return
    batch = (
        await tx.session.execute(
            select(DocumentBatch)
            .where(DocumentBatch.id == document.batch_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    document = (
        await tx.session.execute(
            select(Document).where(Document.id == document.id).with_for_update()
        )
    ).scalar_one_or_none()
    version = (
        await tx.session.execute(
            select(DocumentVersion)
            .where(DocumentVersion.id == version.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if document is None or version is None:
        return
    now = to_db(now_utc())
    initial_upload = int(version.version_no) == 1 and batch is not None
    if initial_upload:
        if terminal:
            version.state = "failed"
            version.error_code = code[:64]
            document.processing_state = "failed"
            document.error_code = code[:64]
            document.version = int(document.version) + 1
            document.updated_at = now
            await start_compensation(
                tx, batch, code=code, request_id=request_id or "worker"
            )
        return
    # 重建失败：保留旧 active，解除文档互斥并登记错误（详细设计 §10.4）
    if terminal:
        version.state = "failed"
        version.error_code = code[:64]
        document.processing_state = "available"
        document.mutation_task_id = None
        document.error_code = code[:64]
        document.version = int(document.version) + 1
        document.updated_at = now


async def start_compensation(
    tx: UoW, batch: DocumentBatch, *, code: str, request_id: str
) -> None:
    """批次进入 compensating：阻止发布、取消发布任务、登记清理任务（幂等）。"""
    if batch.state in ("compensating", "failed"):
        return
    now = to_db(now_utc())
    batch.state = "compensating"
    batch.error_code = code[:64]
    batch.updated_at = now
    await tx.session.execute(
        update(BackgroundTask)
        .where(
            BackgroundTask.kind == TASK_KIND_PUBLISH,
            BackgroundTask.object_id == batch.id,
            BackgroundTask.state.in_(("pending", "retry_wait")),
        )
        .values(state="failed", error_code="COMPENSATED", owner_instance=None, updated_at=now)
    )
    existing = (
        await tx.session.execute(
            select(BackgroundTask.id).where(
                BackgroundTask.kind == TASK_KIND_BATCH_CLEANUP,
                BackgroundTask.object_id == batch.id,
            )
        )
    ).first()
    if existing is None:
        tx.session.add(
            new_task(
                kind=TASK_KIND_BATCH_CLEANUP,
                object_id=batch.id,
                dedupe_key=batch.id,
                priority=20,
            )
        )
    append_audit(
        tx,
        action="document.batch.compensating",
        object_type="document_batch",
        object_id=batch.id,
        result="failure",
        request_id=request_id or "worker",
        metadata={"error_code": code[:64]},
    )


# --------------------------------------------------------------------------- #
# 批次就绪 / 索引可检索预检（事务外，只读）
# --------------------------------------------------------------------------- #
@dataclass
class Precheck:
    all_ready: bool
    failed_code: str | None
    index_ok: bool
    detail: str = ""


async def batch_precheck(batch_id: str) -> Precheck:
    vs = vector_store()
    fs = file_store()
    async with session_scope() as session:
        batch = await session.get(DocumentBatch, batch_id)
        if batch is None:
            return Precheck(False, "RESOURCE_NOT_FOUND", False)
        docs = list(
            (
                await session.execute(
                    select(Document).where(Document.batch_id == batch_id).order_by(Document.id)
                )
            )
            .scalars()
            .all()
        )
        if len(docs) != int(batch.expected_files):
            return Precheck(False, None, False, "文档数与批次期望不一致")
        versions = list(
            (
                await session.execute(
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id.in_([d.id for d in docs]))
                    .order_by(DocumentVersion.id)
                )
            )
            .scalars()
            .all()
        )
        if len(versions) != len(docs):
            return Precheck(False, None, False, "版本与文档数不一致")
        for version in versions:
            if version.state == "failed":
                return Precheck(False, version.error_code or "PARSE_FAILED", False, "版本失败")
            if version.state not in ("ready", "active"):
                return Precheck(False, None, False, "版本尚未就绪")
        version_ids = [v.id for v in versions]
        attempts = list(
            (
                await session.execute(
                    select(StorageAttempt).where(
                        StorageAttempt.version_id.in_(version_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        by_version: dict[str, StorageAttempt] = {}
        for attempt in attempts:
            if attempt.io_state in ("active", "quiescing", "unknown"):
                return Precheck(False, None, False, "存在未知/进行中的外部写入")
        for version in versions:
            # 以选中代次为准（重试会留下多个历史代次，历史代次已标记 cleaned）
            chosen = next(
                (a for a in attempts if a.id == version.selected_attempt_id), None
            ) or next(
                (
                    a
                    for a in attempts
                    if a.version_id == version.id and a.io_state == "settled"
                ),
                None,
            )
            if chosen is None or chosen.io_state != "settled":
                return Precheck(False, None, False, "缺少已收敛的写入代次")
            attempt = chosen
            chunk_ids = set(
                (
                    await session.execute(
                        select(Chunk.id).where(Chunk.version_id == version.id)
                    )
                )
                .scalars()
                .all()
            )
            if not chunk_ids:
                return Precheck(False, None, False, "版本没有片段")
            stored_ids = set(await vs.list_chunk_ids(attempt.vector_namespace))
            if not chunk_ids.issubset(stored_ids):
                return Precheck(False, None, False, "向量索引缺少片段")
            if not attempt.file_prefix or not fs.exists(
                f"{attempt.file_prefix}/extracted-text"
            ):
                return Precheck(False, None, False, "抽取文本缺失")
    return Precheck(True, None, True)


# --------------------------------------------------------------------------- #
# 发布事务
# --------------------------------------------------------------------------- #
async def _close_publish_task(session: Any, batch_id: str, now: Any) -> None:
    """发布成功后收尾旁路登记的发布任务（正常由最后持久任务直接完成发布）。"""
    await session.execute(
        update(BackgroundTask)
        .where(
            BackgroundTask.kind == TASK_KIND_PUBLISH,
            BackgroundTask.object_id == batch_id,
            BackgroundTask.state.in_(("pending", "retry_wait")),
        )
        .values(
            state="succeeded",
            owner_instance=None,
            lease_until=None,
            next_run_at=now,
            error_code=None,
            error_summary=None,
            updated_at=now,
        )
    )


async def publish_batch(lease: TaskLease, batch_id: str, *, complete: bool = True) -> str:
    """整批发布事务：全部就绪/索引可检索才一次切换可见性。

    ``complete=False`` 供 `batch_publish` 任务调用（任务收尾由调用方处理）。
    """
    pre = await batch_precheck(batch_id)
    if pre.failed_code:
        raise TaskFailure(pre.failed_code, retryable=False, summary=pre.detail)
    if not pre.all_ready:
        if complete:
            await _complete_quietly(lease, batch_id)
        return "not_ready"
    if not pre.index_ok:
        raise TaskFailure("RETRIEVAL_UNAVAILABLE", retryable=True, summary=pre.detail)

    now_dt = now_utc()
    now = to_db(now_dt)
    async with uow() as tx:
        corpus = (
            await tx.session.execute(
                select(CorpusControl).where(CorpusControl.singleton_id == 1).with_for_update()
            )
        ).scalar_one()
        batch = (
            await tx.session.execute(
                select(DocumentBatch)
                .where(DocumentBatch.id == batch_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if batch is None:
            raise TaskFailure("RESOURCE_NOT_FOUND", retryable=False)
        if batch.state == "published":
            if complete:
                await _close_publish_task(tx.session, batch_id, now)
                await finish_success(tx.session, lease)
            await tx.commit()
            return "published"
        if batch.state in ("compensating", "failed"):
            if complete:
                await finish_success(tx.session, lease)
            await tx.commit()
            return "blocked"
        documents = list(
            (
                await tx.session.execute(
                    select(Document)
                    .where(Document.batch_id == batch_id)
                    .order_by(Document.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        versions = list(
            (
                await tx.session.execute(
                    select(DocumentVersion)
                    .where(
                        DocumentVersion.document_id.in_([d.id for d in documents])
                    )
                    .order_by(DocumentVersion.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if len(documents) != int(batch.expected_files) or len(versions) != len(documents):
            if complete:
                await finish_success(tx.session, lease)
            await tx.commit()
            return "not_ready"
        if any(v.state == "failed" for v in versions):
            await start_compensation(
                tx, batch, code="BATCH_FAILED", request_id="worker"
            )
            if complete:
                await finish_success(tx.session, lease)
            await tx.commit()
            return "blocked"
        if any(v.state != "ready" for v in versions):
            if complete:
                await finish_success(tx.session, lease)
            await tx.commit()
            return "not_ready"
        if corpus.publish_frozen:
            # 发布冻结（向量空间迁移窗口）：不发布、不失败，稍后重试
            if complete:
                await tx.session.execute(
                    update(BackgroundTask)
                    .where(
                        BackgroundTask.kind == TASK_KIND_PUBLISH,
                        BackgroundTask.object_id == batch_id,
                        BackgroundTask.state.in_(("pending", "retry_wait")),
                    )
                    .values(
                        state="retry_wait",
                        next_run_at=to_db(now_dt + timedelta(seconds=10)),
                        updated_at=now,
                    )
                )
                await finish_success(tx.session, lease)
            await tx.commit()
            return "deferred"

        if not complete:
            await _assert_lease_alive(tx.session, lease)

        vector_space = versions[0].vector_space
        if any(v.vector_space != vector_space for v in versions):
            raise TaskFailure("VECTOR_SPACE_MISMATCH", retryable=False)
        if corpus.active_vector_space is None:
            corpus.active_vector_space = vector_space
        elif corpus.active_vector_space != vector_space:
            raise TaskFailure("VECTOR_SPACE_MISMATCH", retryable=False)

        # 写入收敛证明：选中代次必须已 settled 且登记了屏障时间
        attempt_ids = [v.selected_attempt_id for v in versions if v.selected_attempt_id]
        attempts = list(
            (
                await tx.session.execute(
                    select(StorageAttempt).where(StorageAttempt.id.in_(attempt_ids))
                )
            )
            .scalars()
            .all()
        )
        if len(attempts) != len(versions):
            raise TaskFailure("RETRIEVAL_UNAVAILABLE", retryable=True)
        for attempt in attempts:
            if attempt.io_state != "settled" or attempt.barrier_confirmed_at is None:
                raise TaskFailure("RETRIEVAL_UNAVAILABLE", retryable=True)

        by_document = {v.document_id: v for v in versions}
        for document in documents:
            version = by_document[document.id]
            document.visibility = "shared"
            document.processing_state = "available"
            document.active_version_id = version.id
            document.error_code = None
            document.version = int(document.version) + 1
            document.updated_at = now
            version.state = "active"
            version.error_code = None
        batch.state = "published"
        batch.published_at = now
        batch.updated_at = now
        corpus.revision = int(corpus.revision) + 1
        corpus.updated_at = now
        await _close_publish_task(tx.session, batch_id, now)
        if complete:
            await finish_success(tx.session, lease)
        append_audit(
            tx,
            action="document.batch.publish",
            object_type="document_batch",
            object_id=batch_id,
            result="success",
            request_id="worker",
            metadata={
                "documents": len(documents),
                "revision": int(corpus.revision),
                "vector_space": vector_space,
            },
        )
        append_outbox(
            tx,
            event_type="document.batch.published",
            aggregate_id=batch_id,
            request_id="worker",
            metadata={"revision": int(corpus.revision)},
        )
        await tx.commit()
    return "published"


async def _complete_quietly(lease: TaskLease, object_id: str) -> None:
    async with uow() as tx:
        await finish_success(tx.session, lease)
        await tx.commit()


# --------------------------------------------------------------------------- #
# 版本切换（重建完成）
# --------------------------------------------------------------------------- #
async def switch_version(lease: TaskLease, document_id: str, new_version_id: str) -> str:
    vs = vector_store()
    async with session_scope() as session:
        document = await session.get(Document, document_id)
        version = await session.get(DocumentVersion, new_version_id)
        if document is None or version is None:
            raise TaskFailure("RESOURCE_NOT_FOUND", retryable=False)
        if version.state == "failed":
            raise TaskFailure(version.error_code or "PARSE_FAILED", retryable=False)
        if version.state != "ready":
            await _complete_quietly(lease, document_id)
            return "not_ready"
        attempt = (
            await session.execute(
                select(StorageAttempt).where(StorageAttempt.version_id == version.id)
            )
        ).scalars().first()
        if attempt is None or attempt.io_state != "settled":
            raise TaskFailure("RETRIEVAL_UNAVAILABLE", retryable=True)
        chunk_ids = set(
            (
                await session.execute(select(Chunk.id).where(Chunk.version_id == version.id))
            )
            .scalars()
            .all()
        )
        if not chunk_ids or not chunk_ids.issubset(
            set(await vs.list_chunk_ids(attempt.vector_namespace))
        ):
            raise TaskFailure("RETRIEVAL_UNAVAILABLE", retryable=True)

    now_dt = now_utc()
    now = to_db(now_dt)
    async with uow() as tx:
        corpus = (
            await tx.session.execute(
                select(CorpusControl).where(CorpusControl.singleton_id == 1).with_for_update()
            )
        ).scalar_one()
        document = (
            await tx.session.execute(
                select(Document).where(Document.id == document_id).with_for_update()
            )
        ).scalar_one_or_none()
        if document is None:
            raise TaskFailure("RESOURCE_NOT_FOUND", retryable=False)
        if document.active_version_id == new_version_id:
            await finish_success(tx.session, lease)
            await tx.commit()
            return "published"
        if document.visibility != "shared":
            raise TaskFailure("DOCUMENT_BUSY", retryable=False)
        versions = list(
            (
                await tx.session.execute(
                    select(DocumentVersion)
                    .where(DocumentVersion.document_id == document_id)
                    .order_by(DocumentVersion.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        new_version = next((v for v in versions if v.id == new_version_id), None)
        if new_version is None or new_version.state != "ready":
            raise TaskFailure("RETRIEVAL_UNAVAILABLE", retryable=True)
        if corpus.active_vector_space is None:
            corpus.active_vector_space = new_version.vector_space
        elif corpus.active_vector_space != new_version.vector_space:
            raise TaskFailure("VECTOR_SPACE_MISMATCH", retryable=False)
        old_version = next(
            (v for v in versions if v.id == document.active_version_id), None
        )
        if old_version is not None:
            old_version.state = "retired"
        new_version.state = "active"
        document.active_version_id = new_version.id
        document.processing_state = "available"
        document.mutation_task_id = None
        document.error_code = None
        document.version = int(document.version) + 1
        document.updated_at = now
        corpus.revision = int(corpus.revision) + 1
        corpus.updated_at = now
        if old_version is not None:
            await tx.session.execute(
                update(CitationReference)
                .where(
                    CitationReference.version_id == old_version.id,
                    CitationReference.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            await tx.session.execute(
                delete(Chunk).where(Chunk.version_id == old_version.id)
            )
        await finish_success(tx.session, lease)
        append_audit(
            tx,
            action="document.version.switch",
            object_type="document",
            object_id=document_id,
            result="success",
            request_id="worker",
            metadata={"version_id": new_version_id, "revision": int(corpus.revision)},
        )
        append_outbox(
            tx,
            event_type="document.version.switched",
            aggregate_id=document_id,
            request_id="worker",
            metadata={"version_id": new_version_id},
        )
        await tx.commit()

    if old_version is not None:
        old_attempts = await _attempts_of([old_version.id])
        await _cleanup_version_artifacts(
            version_id=old_version.id,
            attempt_prefixes=[
                f"attempts/{a.task_id}/{a.task_fence}/{a.version_id}" for a in old_attempts
            ],
            namespaces=[a.vector_namespace for a in old_attempts],
        )
    return "published"


async def _attempts_of(version_ids: list[str]) -> list[StorageAttempt]:
    async with session_scope() as session:
        return list(
            (
                await session.execute(
                    select(StorageAttempt).where(
                        StorageAttempt.version_id.in_(version_ids)
                    )
                )
            )
            .scalars()
            .all()
        )


async def _cleanup_version_artifacts(
    *,
    version_id: str,
    attempt_prefixes: list[str],
    namespaces: list[str],
) -> None:
    fs = file_store()
    vs = vector_store()
    for prefix in attempt_prefixes:
        try:
            fs.delete_prefix(prefix)
        except StorageError:
            logger.warning("cleanup attempt prefix failed prefix=%s", prefix)
    for namespace in namespaces:
        try:
            await vs.delete_namespace(namespace)
        except VectorStoreError:
            logger.warning("cleanup vector namespace failed namespace=%s", namespace)
    async with uow() as tx:
        await tx.session.execute(
            update(StorageAttempt)
            .where(StorageAttempt.version_id == version_id)
            .values(io_state="cleaned", updated_at=to_db(now_utc()))
        )
        await tx.commit()


# --------------------------------------------------------------------------- #
# 任务处理器
# --------------------------------------------------------------------------- #
async def handle_doc_persist(lease: TaskLease) -> None:
    claimed = lease.claimed
    version_id = claimed.object_id
    # 读取任务上下文（短事务）
    async with session_scope() as session:
        version = await session.get(DocumentVersion, version_id)
        if version is None:
            raise TaskFailure("RESOURCE_NOT_FOUND", retryable=False)
        document = await session.get(Document, version.document_id)
        if document is None:
            raise TaskFailure("RESOURCE_NOT_FOUND", retryable=False)
        batch = await session.get(DocumentBatch, document.batch_id)
        if batch is None:
            raise TaskFailure("RESOURCE_NOT_FOUND", retryable=False)
        document_batch_state = batch.state
        document_visibility = document.visibility
        original_key = document.original_storage_key
        file_type = document.file_type
        version_state = version.state
        version_no = int(version.version_no)
        vector_space = version.vector_space

    if document_batch_state in ("compensating", "failed"):
        await _complete_quietly(lease, claimed.object_id)
        return
    if document_visibility == "removed":
        await _complete_quietly(lease, claimed.object_id)
        return

    if document_batch_state == "accepted":
        async with uow() as tx:
            batch_row = (
                await tx.session.execute(
                    select(DocumentBatch)
                    .where(DocumentBatch.id == batch.id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if batch_row is not None and batch_row.state == "accepted":
                batch_row.state = "processing"
                batch_row.updated_at = to_db(now_utc())
            await tx.commit()

    if version_state not in ("ready", "active"):
        await _run_staging(
            lease,
            version_id=version_id,
            document_id=document.id,
            file_type=file_type,
            original_key=original_key,
            vector_space=vector_space,
        )

    if version_no == 1:
        await publish_batch(lease, batch.id)
    else:
        await switch_version(lease, document.id, version_id)


async def _run_staging(
    lease: TaskLease,
    *,
    version_id: str,
    document_id: str,
    file_type: str,
    original_key: str | None,
    vector_space: str,
) -> None:
    fs = file_store()
    vs = vector_store()
    emb = embedding()
    if not original_key:
        raise TaskFailure("STORAGE_UNAVAILABLE", retryable=True, summary="原件键缺失")
    if not fs.exists(original_key):
        raise TaskFailure("STORAGE_UNAVAILABLE", retryable=True, summary="原件不存在")
    data = fs.read_bytes(original_key)
    parsed = parse_bytes(data, file_type)
    chunks = build_chunks(parsed)

    fence = lease.fence
    task_id = lease.task_id
    file_prefix = attempt_file_prefix(task_id, fence, version_id)
    text_key = attempt_text_key(task_id, fence, version_id)
    manifest_key = attempt_manifest_key(task_id, fence, version_id)
    namespace = attempt_namespace(task_id, fence, document_id, version_id)

    # 收敛屏障：拒绝旧代次迟到写入，并清理旧产物（同一任务此前失败重试的代次）。
    version_prefix = f"{vector_space}/{document_id}/{version_id}"
    try:
        if fence > 0:
            await vs.barrier(version_prefix, fence - 1)
        fs.delete_prefix(f"attempts/{task_id}")
    except (StorageError, VectorStoreError) as exc:
        raise TaskFailure("STORAGE_UNAVAILABLE", retryable=True, summary=str(exc)[:200])

    vectors = emb.embed_batch([chunk.text for chunk in chunks])

    # 先登记 active 代次（含 inflight 计数），外部写完成后在业务事务内收敛为 settled。
    attempt_id = new_id(PREFIX_ATTEMPT)
    attempt_now = to_db(now_utc())
    async with uow() as tx:
        await tx.session.execute(
            update(StorageAttempt)
            .where(
                StorageAttempt.version_id == version_id,
                StorageAttempt.task_fence != fence,
                StorageAttempt.io_state != "cleaned",
            )
            .values(io_state="cleaned", updated_at=attempt_now)
        )
        tx.session.add(
            StorageAttempt(
                id=attempt_id,
                task_id=task_id,
                task_fence=fence,
                version_id=version_id,
                file_prefix=file_prefix,
                vector_namespace=namespace,
                io_state="active",
                inflight_writes=len(chunks),
                barrier_confirmed_at=None,
                created_at=attempt_now,
                updated_at=attempt_now,
            )
        )
        await tx.commit()

    try:
        fs.write_bytes(text_key, parsed.text.encode("utf-8"))
        fs.write_bytes(
            manifest_key,
            json.dumps(manifest_payload(parsed, chunks), ensure_ascii=False).encode("utf-8"),
        )
        await vs.upsert(
            namespace,
            [(chunk.chunk_id, vector) for chunk, vector in zip(chunks, vectors)],
            fence=fence,
        )
        stored = await vs.namespace_chunk_ids(namespace)
        if len(stored) != len(chunks):
            raise TaskFailure("RETRIEVAL_UNAVAILABLE", retryable=True, summary="索引写入不完整")
    except (StorageError, VectorStoreError) as exc:
        raise TaskFailure("STORAGE_UNAVAILABLE", retryable=True, summary=str(exc)[:200]) from exc

    now = to_db(now_utc())
    async with uow() as tx:
        document = (
            await tx.session.execute(
                select(Document).where(Document.id == document_id).with_for_update()
            )
        ).scalar_one_or_none()
        version = (
            await tx.session.execute(
                select(DocumentVersion)
                .where(DocumentVersion.id == version_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if document is None or version is None:
            raise TaskFailure("RESOURCE_NOT_FOUND", retryable=False)
        await tx.session.execute(
            update(StorageAttempt)
            .where(StorageAttempt.id == attempt_id)
            .values(
                io_state="settled",
                inflight_writes=0,
                barrier_confirmed_at=now,
                updated_at=now,
            )
        )
        for chunk in chunks:
            tx.session.add(
                Chunk(
                    id=chunk.chunk_id,
                    document_id=document_id,
                    version_id=version_id,
                    chunk_index=chunk.chunk_index,
                    text_content=chunk.text,
                    page_number=chunk.page_number,
                    location_label=chunk.location_label,
                    content_digest=chunk.content_digest,
                )
            )
            tx.session.add(
                CitationReference(
                    id=new_id(PREFIX_CITATION),
                    document_id=document_id,
                    version_id=version_id,
                    chunk_id=chunk.chunk_id,
                    revoked_at=None,
                    created_at=now,
                )
            )
        version.state = "ready"
        version.selected_attempt_id = attempt_id
        version.extracted_text_key = text_key
        version.content_digest = __import__("hashlib").sha256(
            parsed.text.encode("utf-8")
        ).digest()
        version.error_code = None
        document.processing_state = (
            "processing" if int(version.version_no) == 1 else "rebuilding"
        )
        document.error_code = None
        document.updated_at = now
        await tx.commit()


async def handle_batch_publish(lease: TaskLease) -> None:
    batch_id = lease.claimed.object_id
    async with session_scope() as session:
        batch = await session.get(DocumentBatch, batch_id)
        if batch is None:
            raise TaskFailure("RESOURCE_NOT_FOUND", retryable=False)
        state = batch.state
    if state in ("compensating", "failed"):
        await _complete_quietly(lease, batch_id)
        return
    result = await publish_batch(lease, batch_id, complete=False)
    async with uow() as tx:
        if result in ("not_ready", "deferred"):
            # 不消耗自动重试次数地稍后重试
            await _requeue(tx.session, lease, 5.0 if result == "not_ready" else 10.0)
        else:
            await finish_success(tx.session, lease)
        await tx.commit()


async def handle_doc_cleanup(lease: TaskLease) -> None:
    document_id = lease.claimed.object_id
    fs = file_store()
    vs = vector_store()
    async with session_scope() as session:
        document = await session.get(Document, document_id)
        if document is None:
            await _complete_quietly(lease, document_id)
            return
        if document.visibility != "removed":
            await _complete_quietly(lease, document_id)
            return
        versions = list(
            (
                await session.execute(
                    select(DocumentVersion).where(DocumentVersion.document_id == document_id)
                )
            )
            .scalars()
            .all()
        )
        attempts = list(
            (
                await session.execute(
                    select(StorageAttempt).where(
                        StorageAttempt.version_id.in_([v.id for v in versions])
                    )
                )
            )
            .scalars()
            .all()
        )
        version_ids = [v.id for v in versions]
        original_key = document.original_storage_key

    # 先撤销引用并删除外部产物，再清空正文；失败则保留 cleanup 未完成并可重试。
    now = to_db(now_utc())
    async with uow() as tx:
        await tx.session.execute(
            update(CitationReference)
            .where(
                CitationReference.document_id == document_id,
                CitationReference.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await tx.session.execute(delete(Chunk).where(Chunk.document_id == document_id))
        await tx.session.execute(
            update(StorageAttempt)
            .where(StorageAttempt.version_id.in_(version_ids))
            .values(io_state="cleaned", updated_at=now)
        )
        await tx.session.execute(
            update(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .values(
                extracted_text_key=None,
                selected_attempt_id=None,
                state=case(
                    (DocumentVersion.state == "active", "retired"),
                    else_=DocumentVersion.state,
                ),
            )
        )
        doc_row = (
            await tx.session.execute(
                select(Document).where(Document.id == document_id).with_for_update()
            )
        ).scalar_one_or_none()
        if doc_row is None:
            await tx.commit()
            return
        doc_row.active_version_id = None
        doc_row.original_storage_key = None
        doc_row.processing_state = "deleted"
        doc_row.cleanup_state = "succeeded"
        doc_row.mutation_task_id = None
        doc_row.error_code = None
        doc_row.version = int(doc_row.version) + 1
        doc_row.updated_at = now
        await finish_success(tx.session, lease)
        append_audit(
            tx,
            action="document.cleanup",
            object_type="document",
            object_id=document_id,
            result="success",
            request_id="worker",
        )
        await tx.commit()

    for attempt in attempts:
        try:
            fs.delete_prefix(attempt.file_prefix)
        except StorageError:
            logger.warning("cleanup file prefix failed prefix=%s", attempt.file_prefix)
        try:
            await vs.barrier(attempt.vector_namespace, 2**31 - 1)
            await vs.delete_namespace(attempt.vector_namespace)
        except VectorStoreError:
            logger.warning("cleanup vector namespace failed namespace=%s", attempt.vector_namespace)
    if original_key:
        try:
            fs.delete(original_key)
        except StorageError:
            logger.warning("cleanup original failed key=%s", original_key)


async def handle_batch_cleanup(lease: TaskLease) -> None:
    batch_id = lease.claimed.object_id
    fs = file_store()
    vs = vector_store()
    async with session_scope() as session:
        batch = await session.get(DocumentBatch, batch_id)
        if batch is None:
            await _complete_quietly(lease, batch_id)
            return
        documents = list(
            (
                await session.execute(
                    select(Document).where(Document.batch_id == batch_id)
                )
            )
            .scalars()
            .all()
        )
        document_ids = [d.id for d in documents]
        versions = list(
            (
                await session.execute(
                    select(DocumentVersion).where(
                        DocumentVersion.document_id.in_(document_ids)
                    )
                )
            )
            .scalars()
            .all()
        ) if document_ids else []
        attempts = list(
            (
                await session.execute(
                    select(StorageAttempt).where(
                        StorageAttempt.version_id.in_([v.id for v in versions])
                    )
                )
            )
            .scalars()
            .all()
        ) if versions else []

    now = to_db(now_utc())
    async with uow() as tx:
        if document_ids:
            await tx.session.execute(
                update(CitationReference)
                .where(
                    CitationReference.document_id.in_(document_ids),
                    CitationReference.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            await tx.session.execute(
                delete(Chunk).where(Chunk.document_id.in_(document_ids))
            )
            await tx.session.execute(
                update(Document)
                .where(Document.id.in_(document_ids))
                .values(
                    processing_state="failed",
                    visibility="unpublished",
                    active_version_id=None,
                    original_storage_key=None,
                    mutation_task_id=None,
                    error_code=batch.error_code if batch else None,
                    updated_at=now,
                )
            )
            await tx.session.execute(
                update(DocumentVersion)
                .where(DocumentVersion.document_id.in_(document_ids))
                .values(state="failed", extracted_text_key=None, selected_attempt_id=None)
            )
            await tx.session.execute(
                update(StorageAttempt)
                .where(StorageAttempt.version_id.in_([v.id for v in versions]))
                .values(io_state="cleaned", updated_at=now)
            )
        batch_row = (
            await tx.session.execute(
                select(DocumentBatch).where(DocumentBatch.id == batch_id).with_for_update()
            )
        ).scalar_one_or_none()
        if batch_row is not None:
            batch_row.state = "failed"
            batch_row.published_at = None
            batch_row.updated_at = now
        await finish_success(tx.session, lease)
        append_audit(
            tx,
            action="document.batch.compensated",
            object_type="document_batch",
            object_id=batch_id,
            result="success",
            request_id="worker",
        )
        await tx.commit()

    if batch is not None:
        for attempt in attempts:
            try:
                fs.delete_prefix(attempt.file_prefix)
            except StorageError:
                logger.warning("batch cleanup file prefix failed prefix=%s", attempt.file_prefix)
            try:
                await vs.barrier(attempt.vector_namespace, 2**31 - 1)
                await vs.delete_namespace(attempt.vector_namespace)
            except VectorStoreError:
                logger.warning(
                    "batch cleanup vector namespace failed namespace=%s",
                    attempt.vector_namespace,
                )
        for document in documents:
            try:
                fs.delete(document_key(document.id))
            except StorageError:
                logger.warning("batch cleanup original failed document=%s", document.id)


HANDLERS = {
    TASK_KIND_PERSIST: handle_doc_persist,
    TASK_KIND_PUBLISH: handle_batch_publish,
    TASK_KIND_DOC_CLEANUP: handle_doc_cleanup,
    TASK_KIND_BATCH_CLEANUP: handle_batch_cleanup,
}


# --------------------------------------------------------------------------- #
# 循环入口
# --------------------------------------------------------------------------- #
async def execute_claimed(claimed: ClaimedTask, owner: str) -> str:
    lease = TaskLease(claimed=claimed, owner=owner)
    handler = HANDLERS.get(claimed.kind)
    heartbeat = Heartbeat(lease)
    await heartbeat.start()
    try:
        if handler is None:
            raise TaskFailure("UNSUPPORTED_TASK", retryable=False)
        await handler(lease)
        return "succeeded"
    except LeaseLost:
        logger.warning("lease lost, abandon task=%s fence=%s", claimed.id, claimed.fence)
        return "lease_lost"
    except (TaskFailure, ParserError) as exc:
        code = getattr(exc, "code", "PROCESSING_FAILED")
        retryable = getattr(exc, "retryable", code not in NON_RETRYABLE_CODES)
        summary = getattr(exc, "summary", None) or getattr(exc, "message", "") or str(exc)
        result = await schedule_failure(
            claimed, owner, code=code, retryable=retryable, summary=summary
        )
        return result
    except (StorageError, VectorStoreError, EmbeddingError, LateWriteRejected) as exc:
        result = await schedule_failure(
            claimed,
            owner,
            code="STORAGE_UNAVAILABLE",
            retryable=True,
            summary=str(exc)[:500],
        )
        return result
    except Exception as exc:  # noqa: BLE001 - Worker 必须记录并分类，不得静默重启
        logger.exception("task failed unexpectedly task=%s", claimed.id)
        result = await schedule_failure(
            claimed,
            owner,
            code="PROCESSING_FAILED",
            retryable=True,
            summary=f"{type(exc).__name__}: {exc}"[:500],
        )
        return result
    finally:
        await heartbeat.stop()


async def run_once(owner: str | None = None, *, max_tasks: int = 100) -> dict[str, Any]:
    """单轮执行：先回收过期租约，再按队列顺序处理至多 max_tasks 条到期任务。"""
    worker = owner or instance_id()
    recovered = await recover_expired_leases()
    processed = 0
    counters: dict[str, int] = {}
    while processed < max_tasks:
        claimed = await claim_next(worker)
        if claimed is None:
            break
        outcome = await execute_claimed(claimed, worker)
        processed += 1
        counters[outcome] = counters.get(outcome, 0) + 1
        counters[f"kind:{claimed.kind}"] = counters.get(f"kind:{claimed.kind}", 0) + 1
    return {
        "owner": worker,
        "processed": processed,
        "recovered_leases": recovered,
        "counters": counters,
    }


async def run_forever(owner: str | None = None, *, poll_seconds: float = POLL_SECONDS) -> None:
    worker = owner or instance_id()
    await recover_expired_leases()
    logger.info("worker started owner=%s", worker)
    while True:
        result = await run_once(worker)
        if result["processed"] == 0:
            await asyncio.sleep(poll_seconds)


__all__ = [
    "ClaimedTask",
    "HANDLERS",
    "Heartbeat",
    "LeaseLost",
    "TaskFailure",
    "TaskLease",
    "claim_next",
    "execute_claimed",
    "finish_success",
    "handle_batch_cleanup",
    "handle_batch_publish",
    "handle_doc_cleanup",
    "handle_doc_persist",
    "instance_id",
    "new_task",
    "publish_batch",
    "record_attempt",
    "recover_expired_leases",
    "run_forever",
    "run_once",
    "schedule_failure",
    "start_compensation",
    "switch_version",
]
