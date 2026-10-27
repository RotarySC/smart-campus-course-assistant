"""知识链路服务：上传接受、批次/文档查询、重建/删除、检索与引用。

Interface 冻结（Phase 1）：``accept_batch / get_batch / list_documents /
preview_document / mutate_document / search / get_citation``。
路由只做 HTTP 解析与信封包装；本模块集中事务、锁顺序与授权校验。
"""

from __future__ import annotations

import codecs
import logging
from datetime import timedelta
from typing import Any, Iterable

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.adapters.db.engine import session_scope
from app.adapters.db.models import (
    BackgroundTask,
    CitationReference,
    Chunk,
    CorpusControl,
    Document,
    DocumentBatch,
    DocumentVersion,
)
from app.adapters.db.uow import UoW, uow
from app.adapters.filestore.local import StorageError
from app.adapters.vector.local import VectorStoreError
from app.modules.knowledge.adapters import (
    TASK_KIND_DOC_CLEANUP,
    TASK_KIND_PERSIST,
    TASK_KIND_PUBLISH,
    corpus_vector_space,
    detect_file_type,
    document_key,
    embedding,
    file_store,
    parser_config_digest,
    retrieval_min_score,
    sealed_key,
    upload_max_file_bytes,
    upload_max_files,
    upload_max_total_bytes,
    vector_store,
)
from app.modules.knowledge.schemas import (
    BatchOptions,
    DocumentCommand,
    EvidenceChunk,
    EvidenceReference,
    EvidenceSet,
    ListDocumentsQuery,
    SearchQuery,
    batch_view,
    citation_view,
    document_mutation_view,
    document_page_view,
    document_view,
    task_view,
)
from app.modules.knowledge.tasks import new_task, start_compensation
from app.modules.operations.service import append_audit, append_outbox
from app.shared.clock import now_utc, to_db
from app.shared.context import ActorContext
from app.shared.errors import ApiError, field_error, map_integrity_error, validation_error
from app.shared.ids import (
    PREFIX_BATCH,
    PREFIX_DOCUMENT,
    PREFIX_VERSION,
    new_id,
)

logger = logging.getLogger("cca.knowledge")

UPLOAD_ID_PREFIX = "upl"
MAX_FILENAME_LENGTH = 255
PREVIEW_DEFAULT_LIMIT = 20000
PREVIEW_MAX_LIMIT = 20000
SEARCH_MAX_TOP_K = 20


def _ensure_admin(ctx: ActorContext) -> None:
    if not ctx.is_admin:
        raise ApiError("FORBIDDEN")


def _safe_display_name(raw: str) -> str:
    if not isinstance(raw, str):
        raise validation_error(("files", "文件名缺失"))
    name = raw.strip()
    if not name:
        raise validation_error(("files", "文件名不能为空"))
    if "/" in name or "\\" in name:
        raise validation_error(("files", "文件名不能包含路径分隔符"))
    if any(ord(ch) < 32 for ch in name):
        raise validation_error(("files", "文件名包含控制字符"))
    if len(name) > MAX_FILENAME_LENGTH:
        raise validation_error(("files", "文件名过长"))
    return name


def _plain_text_validator() -> Any:
    """txt/md 流式校验：必须是 UTF-8 文本且不含 NUL。"""
    decoder = codecs.getincrementaldecoder("utf-8-sig")()

    def validate(block: bytes) -> None:
        if b"\x00" in block:
            raise ApiError(
                "UNSUPPORTED_FILE_TYPE",
                field_errors=[field_error("files", "文件内容与后缀不一致")],
            )
        try:
            decoder.decode(block)
        except UnicodeDecodeError as exc:
            raise ApiError(
                "UNSUPPORTED_FILE_TYPE",
                field_errors=[field_error("files", "文本文件不是合法 UTF-8")],
            ) from exc

    return validate


def _signature_ok(file_type: str, head: bytes) -> bool:
    if file_type == "pdf":
        return head.startswith(b"%PDF-")
    if file_type == "docx":
        return head[:2] == b"PK"
    return b"\x00" not in head


async def _ensure_corpus_control(tx: UoW) -> CorpusControl:
    corpus = (
        await tx.session.execute(
            select(CorpusControl).where(CorpusControl.singleton_id == 1).with_for_update()
        )
    ).scalar_one_or_none()
    if corpus is None:
        corpus = CorpusControl(
            singleton_id=1,
            revision=0,
            active_vector_space=None,
            publish_frozen=False,
            updated_at=to_db(now_utc()),
        )
        tx.session.add(corpus)
        await tx.session.flush()
    return corpus


def _preview_unavailable_reason(document: Document, version: DocumentVersion) -> str:
    """预览不可用的原因（FR-DOC-004）：解析失败 / 仍处理中。

    "已清理"的文档在 `preview_document` 入口就按 removed 返回 404，不会走到这里；
    "在排队"与"正在处理"对用户是同一种等待，合并为 processing。
    """
    if document.processing_state == "failed" or version.state == "failed":
        return "parse_failed"
    return "processing"


class KnowledgeService:
    # ------------------------------------------------------------------ 上传接受
    async def accept_batch(
        self, ctx: ActorContext, files: Iterable[Any], options: BatchOptions | None = None
    ) -> dict[str, Any]:
        _ensure_admin(ctx)
        options = options or BatchOptions()
        file_list = [item for item in files if item is not None]

        if not file_list:
            raise validation_error(("files", "至少上传 1 个文件"))
        if len(file_list) > upload_max_files():
            raise validation_error(("files", f"一次最多上传 {upload_max_files()} 个文件"))

        metas: list[dict[str, Any]] = []
        for upload in file_list:
            raw_name = getattr(upload, "filename", None)
            if raw_name is None:
                raise validation_error(("files", "文件字段缺失"))
            name = _safe_display_name(raw_name)
            file_type = detect_file_type(name)
            if file_type is None:
                raise ApiError(
                    "UNSUPPORTED_FILE_TYPE",
                    field_errors=[field_error("files", f"不支持的文件类型：{name}")],
                )
            metas.append({"upload": upload, "name": name, "file_type": file_type})

        names = [meta["name"] for meta in metas]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates and not options.allow_duplicate_names:
            raise ApiError(
                "DUPLICATE_FILENAME",
                details={"duplicate_names": duplicates},
            )

        async with session_scope() as session:
            existing = set(
                (
                    await session.execute(
                        select(Document.original_name).where(
                            Document.original_name.in_(names),
                            Document.visibility != "removed",
                        )
                    )
                )
                .scalars()
                .all()
            )
        conflicts = sorted(set(names) & existing)
        if conflicts and not options.allow_duplicate_names:
            raise ApiError("DUPLICATE_FILENAME", details={"duplicate_names": conflicts})

        fs = file_store()
        staged: list[dict[str, Any]] = []
        total_bytes = 0
        per_file_max = upload_max_file_bytes()
        total_max = upload_max_total_bytes()
        try:
            for meta in metas:
                upload = meta["upload"]
                upload_id = new_id(UPLOAD_ID_PREFIX)
                key = sealed_key(upload_id)
                validator = (
                    _plain_text_validator() if meta["file_type"] in ("txt", "md") else None
                )
                try:
                    size = await fs.write_async_stream(
                        key,
                        upload,
                        max_bytes=per_file_max,
                        validator=validator,
                    )
                    if size <= 0:
                        raise validation_error(("files", f"{meta['name']} 为空文件"))
                    if not _signature_ok(meta["file_type"], fs.read_first_bytes(key, 8)):
                        raise ApiError(
                            "UNSUPPORTED_FILE_TYPE",
                            field_errors=[
                                field_error("files", f"{meta['name']} 内容与后缀不一致")
                            ],
                        )
                    total_bytes += size
                    if total_bytes > total_max:
                        raise ApiError(
                            "UPLOAD_TOO_LARGE",
                            field_errors=[field_error("files", "整批文件超过总量限额")],
                        )
                except StorageError as exc:
                    try:
                        fs.delete(key)
                    except StorageError:  # pragma: no cover
                        pass
                    raise ApiError(
                        "UPLOAD_TOO_LARGE",
                        field_errors=[
                            field_error("files", f"{meta['name']} 超出单文件限额")
                        ],
                    ) from exc
                except BaseException:
                    try:
                        fs.delete(key)
                    except StorageError:  # pragma: no cover
                        pass
                    raise
                staged.append(
                    {
                        "upload_id": upload_id,
                        "sealed_key": key,
                        "name": meta["name"],
                        "file_type": meta["file_type"],
                        "byte_size": size,
                    }
                )
        except BaseException:
            for item in staged:
                try:
                    fs.delete(item["sealed_key"])
                except StorageError:  # pragma: no cover - 清理尽力而为
                    pass
            raise

        batch_id = new_id(PREFIX_BATCH)
        records: list[dict[str, Any]] = []
        try:
            for item in staged:
                document_id = new_id(PREFIX_DOCUMENT)
                version_id = new_id(PREFIX_VERSION)
                fs.copy(item["sealed_key"], document_key(document_id))
                records.append({**item, "document_id": document_id, "version_id": version_id})
        except BaseException:
            for item in staged:
                try:
                    fs.delete(item["sealed_key"])
                except StorageError:  # pragma: no cover
                    pass
            for record in records:
                try:
                    fs.delete(document_key(record["document_id"]))
                except StorageError:  # pragma: no cover
                    pass
            raise

        now = to_db(now_utc())
        batch = DocumentBatch(
            id=batch_id,
            uploaded_by=ctx.user_id,
            state="accepted",
            expected_files=len(records),
            total_bytes=total_bytes,
            error_code=None,
            published_at=None,
            created_at=now,
            updated_at=now,
        )
        documents: list[Document] = []
        versions: list[DocumentVersion] = []
        persist_tasks: list[BackgroundTask] = []
        for record in records:
            documents.append(
                Document(
                    id=record["document_id"],
                    batch_id=batch_id,
                    original_name=record["name"],
                    file_type=record["file_type"],
                    byte_size=record["byte_size"],
                    original_storage_key=document_key(record["document_id"]),
                    visibility="unpublished",
                    processing_state="processing",
                    active_version_id=None,
                    mutation_task_id=None,
                    error_code=None,
                    deleted_at=None,
                    cleanup_state="not_required",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
            versions.append(
                DocumentVersion(
                    id=record["version_id"],
                    document_id=record["document_id"],
                    version_no=1,
                    state="staging",
                    content_digest=None,
                    parser_config_digest=parser_config_digest(),
                    vector_space=corpus_vector_space(),
                    selected_attempt_id=None,
                    extracted_text_key=None,
                    error_code=None,
                    created_at=now,
                )
            )
            persist_tasks.append(
                new_task(
                    kind=TASK_KIND_PERSIST,
                    object_id=record["version_id"],
                    dedupe_key=batch_id,
                    priority=10,
                )
            )
        publish_task = new_task(
            kind=TASK_KIND_PUBLISH,
            object_id=batch_id,
            dedupe_key=batch_id,
            priority=0,
            delay_seconds=3600,  # 正常情况下由最后一个持久任务在发布事务中直接收尾
        )

        try:
            async with uow() as tx:
                await _ensure_corpus_control(tx)
                tx.session.add(batch)
                await tx.session.flush()
                tx.session.add_all(documents)
                await tx.session.flush()
                tx.session.add_all(versions)
                await tx.session.flush()
                tx.session.add_all(persist_tasks)
                tx.session.add(publish_task)
                await tx.session.flush()
                append_audit(
                    tx,
                    action="document.batch.accept",
                    object_type="document_batch",
                    object_id=batch_id,
                    result="success",
                    request_id=ctx.trace_request_id,
                    actor_id=ctx.user_id,
                    metadata={"files": len(records), "total_bytes": total_bytes},
                )
                append_outbox(
                    tx,
                    event_type="document.batch.accepted",
                    aggregate_id=batch_id,
                    request_id=ctx.trace_request_id,
                    metadata={"files": len(records)},
                )
                await tx.commit()
        except IntegrityError as exc:
            for record in records:
                try:
                    fs.delete(document_key(record["document_id"]))
                except StorageError:  # pragma: no cover
                    pass
            raise map_integrity_error(exc) or ApiError("INTERNAL_ERROR") from None
        finally:
            for item in staged:
                try:
                    fs.delete(item["sealed_key"])
                except StorageError:  # pragma: no cover
                    pass

        return batch_view(batch, documents, persist_tasks + [publish_task])

    # ------------------------------------------------------------------ 批次详情
    async def get_batch(self, ctx: ActorContext, batch_id: str) -> dict[str, Any]:
        _ensure_admin(ctx)
        async with session_scope() as session:
            batch = await session.get(DocumentBatch, batch_id)
            if batch is None:
                raise ApiError("RESOURCE_NOT_FOUND")
            documents = list(
                (
                    await session.execute(
                        select(Document)
                        .where(Document.batch_id == batch_id)
                        .order_by(Document.created_at, Document.id)
                    )
                )
                .scalars()
                .all()
            )
            version_ids = [
                row.id
                for row in (
                    await session.execute(
                        select(DocumentVersion).where(
                            DocumentVersion.document_id.in_([d.id for d in documents])
                        )
                    )
                )
                .scalars()
                .all()
            ]
            tasks = list(
                (
                    await session.execute(
                        select(BackgroundTask)
                        .where(
                            (BackgroundTask.kind == TASK_KIND_PERSIST)
                            & (BackgroundTask.object_id.in_(version_ids or [""]))
                            | (
                                (BackgroundTask.kind == TASK_KIND_PUBLISH)
                                & (BackgroundTask.object_id == batch_id)
                            )
                        )
                        .order_by(BackgroundTask.created_at, BackgroundTask.id)
                    )
                )
                .scalars()
                .all()
            )
        return batch_view(batch, documents, tasks)

    # ------------------------------------------------------------------ 文档列表
    async def list_documents(
        self, ctx: ActorContext, query: ListDocumentsQuery
    ) -> dict[str, Any]:
        _ensure_admin(ctx)
        conditions = []
        if query.name:
            conditions.append(Document.original_name.contains(query.name, autoescape=True))
        if query.state:
            conditions.append(Document.processing_state == query.state)
        page = max(1, int(query.page))
        page_size = min(max(1, int(query.page_size)), 100)
        async with session_scope() as session:
            total = int(
                (
                    await session.execute(
                        select(func.count()).select_from(Document).where(*conditions)
                    )
                ).scalar_one()
                or 0
            )
            rows = list(
                (
                    await session.execute(
                        select(Document)
                        .where(*conditions)
                        .order_by(Document.created_at.desc(), Document.id.desc())
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                    )
                )
                .scalars()
                .all()
            )
        return document_page_view(rows, page=page, page_size=page_size, total=total)

    # ------------------------------------------------------------------ 文本预览
    async def preview_document(
        self, ctx: ActorContext, document_id: str, offset: int, limit: int
    ) -> dict[str, Any]:
        _ensure_admin(ctx)
        offset = max(0, int(offset or 0))
        limit = min(max(1, int(limit or PREVIEW_DEFAULT_LIMIT)), PREVIEW_MAX_LIMIT)
        async with session_scope() as session:
            document = await session.get(Document, document_id)
            if document is None or document.visibility == "removed":
                raise ApiError("RESOURCE_NOT_FOUND")
            version = None
            if document.active_version_id:
                version = await session.get(DocumentVersion, document.active_version_id)
            if version is None:
                version = (
                    await session.execute(
                        select(DocumentVersion)
                        .where(DocumentVersion.document_id == document_id)
                        .order_by(DocumentVersion.version_no.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
        if version is None:
            raise ApiError("RESOURCE_NOT_FOUND")
        key = version.extracted_text_key
        fs = file_store()
        if not key or not fs.exists(key):
            # FR-DOC-004：预览不可用必须给原因，不能只说"资源不存在"。
            # 已删除文档仍走 404（删除后本就不该再被预览）。
            reason = _preview_unavailable_reason(document, version)
            return {
                "document_id": document_id,
                "version_id": version.id,
                "offset": offset,
                "next_offset": None,
                "text": "",
                "state": reason,
            }
        text = fs.read_text(key)
        piece = text[offset : offset + limit]
        next_offset = offset + len(piece) if offset + len(piece) < len(text) else None
        return {
            "document_id": document_id,
            "version_id": version.id,
            "offset": offset,
            "next_offset": next_offset,
            "text": piece,
            "state": "available",
        }

    # ------------------------------------------------------------------ 重建 / 删除 / 清理重试
    async def mutate_document(
        self, ctx: ActorContext, command: DocumentCommand
    ) -> dict[str, Any]:
        _ensure_admin(ctx)
        if command.action == "rebuild":
            return await self._rebuild(ctx, command)
        if command.action == "delete":
            return await self._delete(ctx, command)
        if command.action == "cleanup_retry":
            return await self._cleanup_retry(ctx, command)
        raise ApiError("VALIDATION_FAILED", field_errors=[field_error("action", "不支持的操作")])

    async def _find_rebuild_task(
        self, document_id: str, idempotency_key: str
    ) -> tuple[BackgroundTask, DocumentVersion] | None:
        async with session_scope() as session:
            row = (
                await session.execute(
                    select(BackgroundTask, DocumentVersion)
                    .join(DocumentVersion, DocumentVersion.id == BackgroundTask.object_id)
                    .where(
                        BackgroundTask.kind == TASK_KIND_PERSIST,
                        BackgroundTask.dedupe_key == f"rebuild:{idempotency_key}",
                        DocumentVersion.document_id == document_id,
                    )
                    .order_by(BackgroundTask.created_at.desc())
                    .limit(1)
                )
            ).first()
            if row is None:
                return None
            return row[0], row[1]

    async def _rebuild(self, ctx: ActorContext, command: DocumentCommand) -> dict[str, Any]:
        assert command.idempotency_key is not None
        assert command.expected_version is not None
        document_id = command.document_id
        # 相同 Idempotency-Key 返回原任务，不重复创建版本
        existing = await self._find_rebuild_task(document_id, command.idempotency_key)
        if existing is not None:
            task, _version = existing
            async with session_scope() as session:
                document = await session.get(Document, document_id)
                if document is None:
                    raise ApiError("RESOURCE_NOT_FOUND")
                return document_mutation_view(document, task)

        now = to_db(now_utc())
        try:
            async with uow() as tx:
                document = (
                    await tx.session.execute(
                        select(Document).where(Document.id == document_id).with_for_update()
                    )
                ).scalar_one_or_none()
                if document is None or document.visibility == "removed":
                    raise ApiError("RESOURCE_NOT_FOUND")
                if document.mutation_task_id:
                    current = await tx.session.get(
                        BackgroundTask, document.mutation_task_id
                    )
                    if current is not None and current.dedupe_key == (
                        f"rebuild:{command.idempotency_key}"
                    ):
                        await tx.commit()
                        return document_mutation_view(document, current)
                    raise ApiError("DOCUMENT_BUSY")
                if int(document.version) != int(command.expected_version):
                    raise ApiError("VERSION_CONFLICT")
                if document.active_version_id is None:
                    raise ApiError("DOCUMENT_BUSY", message="文档当前不可重建")
                max_no = (
                    await tx.session.execute(
                        select(func.max(DocumentVersion.version_no)).where(
                            DocumentVersion.document_id == document_id
                        )
                    )
                ).scalar_one() or 0
                version = DocumentVersion(
                    id=new_id(PREFIX_VERSION),
                    document_id=document_id,
                    version_no=int(max_no) + 1,
                    state="staging",
                    content_digest=None,
                    parser_config_digest=parser_config_digest(),
                    vector_space=corpus_vector_space(),
                    selected_attempt_id=None,
                    extracted_text_key=None,
                    error_code=None,
                    created_at=now,
                )
                tx.session.add(version)
                task = new_task(
                    kind=TASK_KIND_PERSIST,
                    object_id=version.id,
                    dedupe_key=f"rebuild:{command.idempotency_key}",
                    priority=10,
                )
                tx.session.add(task)
                await tx.session.flush()
                document.mutation_task_id = task.id
                document.processing_state = "rebuilding"
                document.error_code = None
                document.version = int(document.version) + 1
                document.updated_at = now
                append_audit(
                    tx,
                    action="document.rebuild",
                    object_type="document",
                    object_id=document_id,
                    result="accepted",
                    request_id=ctx.trace_request_id,
                    actor_id=ctx.user_id,
                    metadata={"version_no": int(max_no) + 1},
                )
                await tx.commit()
        except IntegrityError as exc:
            raise map_integrity_error(exc) or ApiError("INTERNAL_ERROR") from None
        return document_mutation_view(document, task)

    async def _delete(self, ctx: ActorContext, command: DocumentCommand) -> dict[str, Any]:
        assert command.expected_version is not None
        now = to_db(now_utc())
        async with uow() as tx:
            corpus = await _ensure_corpus_control(tx)
            batch_id = (
                await tx.session.execute(
                    select(Document.batch_id).where(Document.id == command.document_id)
                )
            ).scalar_one_or_none()
            if batch_id is None:
                raise ApiError("RESOURCE_NOT_FOUND")
            # 加锁顺序与发布事务保持一致（corpus→batch→document），避免与 batch_publish 互锁。
            batch = (
                await tx.session.execute(
                    select(DocumentBatch)
                    .where(DocumentBatch.id == batch_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            document = (
                await tx.session.execute(
                    select(Document).where(Document.id == command.document_id).with_for_update()
                )
            ).scalar_one_or_none()
            if document is None:
                raise ApiError("RESOURCE_NOT_FOUND")
            if int(document.version) != int(command.expected_version):
                raise ApiError("VERSION_CONFLICT")
            if document.visibility == "removed":
                task = None
                if document.mutation_task_id:
                    task = await tx.session.get(BackgroundTask, document.mutation_task_id)
                if task is None:
                    task = (
                        await tx.session.execute(
                            select(BackgroundTask)
                            .where(
                                BackgroundTask.kind == TASK_KIND_DOC_CLEANUP,
                                BackgroundTask.object_id == document.id,
                            )
                            .order_by(BackgroundTask.created_at.desc())
                            .limit(1)
                        )
                    ).scalar_one_or_none()
                await tx.commit()
                if task is None:
                    raise ApiError("RESOURCE_NOT_FOUND")
                return document_mutation_view(document, task)
            if document.mutation_task_id:
                raise ApiError("DOCUMENT_BUSY")
            task = new_task(
                kind=TASK_KIND_DOC_CLEANUP,
                object_id=document.id,
                dedupe_key="delete",
                priority=20,
            )
            tx.session.add(task)
            await tx.session.flush()
            document.visibility = "removed"
            document.deleted_at = now
            document.processing_state = "deleting"
            document.cleanup_state = "pending"
            document.mutation_task_id = task.id
            document.error_code = None
            document.version = int(document.version) + 1
            document.updated_at = now
            if batch is not None and batch.state != "published":
                # SRS FR-DOC-003：批次内任一文件失败/消失则整批不发布并进入补偿。
                # 未发布批次删掉其中一份文档后，该批次不可再发布，必须当场转补偿；
                # 否则发布任务会永远 not_ready 重排或复活已删文档。
                await start_compensation(
                    tx, batch, code="BATCH_FAILED", request_id=ctx.trace_request_id
                )
            corpus.revision = int(corpus.revision) + 1
            corpus.updated_at = now
            await tx.session.execute(
                update(CitationReference)
                .where(
                    CitationReference.document_id == document.id,
                    CitationReference.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            append_audit(
                tx,
                action="document.delete",
                object_type="document",
                object_id=document.id,
                result="accepted",
                request_id=ctx.trace_request_id,
                actor_id=ctx.user_id,
                metadata={"revision": int(corpus.revision)},
            )
            append_outbox(
                tx,
                event_type="document.removed",
                aggregate_id=document.id,
                request_id=ctx.trace_request_id,
                metadata={"revision": int(corpus.revision)},
            )
            await tx.commit()
        return document_mutation_view(document, task)

    async def _cleanup_retry(
        self, ctx: ActorContext, command: DocumentCommand
    ) -> dict[str, Any]:
        assert command.idempotency_key is not None
        now = to_db(now_utc())
        async with uow() as tx:
            document = (
                await tx.session.execute(
                    select(Document).where(Document.id == command.document_id).with_for_update()
                )
            ).scalar_one_or_none()
            if document is None:
                raise ApiError("RESOURCE_NOT_FOUND")
            if document.visibility != "removed":
                raise ApiError("DOCUMENT_BUSY", message="仅已删除文档可重试清理")
            if document.mutation_task_id:
                current = await tx.session.get(BackgroundTask, document.mutation_task_id)
                if current is not None and (
                    current.dedupe_key == f"retry:{command.idempotency_key}"
                    or current.state in ("pending", "running", "retry_wait")
                ):
                    await tx.commit()
                    return document_mutation_view(document, current)
            if document.cleanup_state == "succeeded":
                latest = (
                    await tx.session.execute(
                        select(BackgroundTask)
                        .where(
                            BackgroundTask.kind == TASK_KIND_DOC_CLEANUP,
                            BackgroundTask.object_id == document.id,
                        )
                        .order_by(BackgroundTask.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                await tx.commit()
                if latest is None:
                    raise ApiError("RESOURCE_NOT_FOUND")
                return document_mutation_view(document, latest)
            task = new_task(
                kind=TASK_KIND_DOC_CLEANUP,
                object_id=document.id,
                dedupe_key=f"retry:{command.idempotency_key}",
                priority=20,
            )
            tx.session.add(task)
            await tx.session.flush()
            document.mutation_task_id = task.id
            document.cleanup_state = "pending"
            document.processing_state = "deleting"
            document.version = int(document.version) + 1
            document.updated_at = now
            append_audit(
                tx,
                action="document.cleanup.retry",
                object_type="document",
                object_id=document.id,
                result="accepted",
                request_id=ctx.trace_request_id,
                actor_id=ctx.user_id,
            )
            await tx.commit()
        return document_mutation_view(document, task)

    # ------------------------------------------------------------------ 检索
    async def search(self, ctx: ActorContext, query: SearchQuery | str) -> EvidenceSet:
        """语义候选 + 关系库权威复核 → EvidenceSet（空库=empty，不是失败）。"""
        if isinstance(query, str):
            query = SearchQuery(query=query)
        text = (query.query or "").strip()
        if not text:
            raise validation_error(("query", "问题不能为空"))
        top_k = min(max(1, int(query.top_k or 5)), SEARCH_MAX_TOP_K)
        emb = embedding()
        vs = vector_store()

        for _attempt in range(2):
            async with session_scope() as session:
                corpus = await session.get(CorpusControl, 1)
                revision = int(corpus.revision) if corpus else 0
                vector_space = (
                    corpus.active_vector_space
                    if corpus and corpus.active_vector_space
                    else corpus_vector_space()
                )
                has_visible = (
                    await session.execute(
                        select(Document.id)
                        .join(DocumentBatch, DocumentBatch.id == Document.batch_id)
                        .join(
                            DocumentVersion,
                            DocumentVersion.id == Document.active_version_id,
                        )
                        .where(
                            Document.visibility == "shared",
                            Document.deleted_at.is_(None),
                            DocumentBatch.state == "published",
                            DocumentVersion.state == "active",
                        )
                        .limit(1)
                    )
                ).first()
            if has_visible is None:
                return EvidenceSet.empty(corpus_empty=True, revision=revision)

            candidates = await vs.search(
                vector_space, emb.embed(text), limit=top_k * 8
            )
            min_score = retrieval_min_score()
            if min_score > 0 and candidates:
                # FR-QA-003：低于相关性阈值的候选不算依据，"检索过但没命中"要说没找到。
                candidates = [
                    item
                    for item in candidates
                    if float(item.get("score", 0.0)) >= min_score
                ]
            if not candidates:
                return EvidenceSet.empty(corpus_empty=False, revision=revision)
            score_of = {item["chunk_id"]: item["score"] for item in candidates}
            chunk_ids = list(score_of)
            async with session_scope() as session:
                rows = list(
                    (
                        await session.execute(
                            select(
                                Chunk,
                                Document,
                                DocumentVersion,
                                CitationReference,
                            )
                            .join(Document, Document.id == Chunk.document_id)
                            .join(DocumentVersion, DocumentVersion.id == Chunk.version_id)
                            .join(DocumentBatch, DocumentBatch.id == Document.batch_id)
                            .join(CitationReference, CitationReference.chunk_id == Chunk.id)
                            .where(
                                Chunk.id.in_(chunk_ids),
                                Document.visibility == "shared",
                                Document.deleted_at.is_(None),
                                Document.active_version_id == DocumentVersion.id,
                                DocumentVersion.state == "active",
                                DocumentBatch.state == "published",
                                DocumentVersion.vector_space == vector_space,
                                CitationReference.revoked_at.is_(None),
                            )
                        )
                    ).all()
                )
                corpus_after = await session.get(CorpusControl, 1)
                revision_after = int(corpus_after.revision) if corpus_after else 0
            if revision_after != revision:
                continue  # 检索期间语料变更：重新核实（设计 §11.1）
            rows.sort(key=lambda row: (-score_of.get(row[0].id, 0.0), row[0].id))
            selected = rows[:top_k]
            if not selected:
                return EvidenceSet.empty(corpus_empty=False, revision=revision)
            chunks: list[EvidenceChunk] = []
            references: list[EvidenceReference] = []
            seen_documents: set[str] = set()
            for chunk, document, version, reference in selected:
                if document.id in seen_documents:
                    continue  # 每文档固定一个版本
                seen_documents.add(document.id)
                chunks.append(
                    EvidenceChunk(
                        chunk_id=chunk.id,
                        reference_id=reference.id,
                        document_id=document.id,
                        version_id=version.id,
                        text=chunk.text_content,
                        location_label=chunk.location_label,
                        page_number=chunk.page_number,
                    )
                )
                references.append(
                    EvidenceReference(
                        reference_id=reference.id,
                        document_id=document.id,
                        version_id=version.id,
                        file_name=document.original_name,
                        location_label=chunk.location_label,
                        page_number=chunk.page_number,
                    )
                )
            return EvidenceSet(
                status="ok",
                corpus_empty=False,
                revision=revision,
                chunks=chunks,
                references=references,
            )
        return EvidenceSet.empty(corpus_empty=False, revision=0)

    # ------------------------------------------------------------------ 引用
    async def get_citation(self, ctx: ActorContext, reference_id: str) -> dict[str, Any]:
        async with session_scope() as session:
            reference = await session.get(CitationReference, reference_id)
            chunk = await session.get(Chunk, reference.chunk_id) if reference else None
            document = await session.get(Document, reference.document_id) if reference else None
            version = await session.get(DocumentVersion, reference.version_id) if reference else None
            batch = await session.get(DocumentBatch, document.batch_id) if document else None
        valid = (
            reference is not None
            and reference.revoked_at is None
            and chunk is not None
            and document is not None
            and version is not None
            and batch is not None
            and chunk.version_id == reference.version_id
            and chunk.document_id == reference.document_id
            and document.deleted_at is None
            and document.visibility == "shared"
            and document.active_version_id == reference.version_id
            and version.state == "active"
            and batch.state == "published"
        )
        if not valid:
            raise ApiError("CITATION_UNAVAILABLE")
        await self._record_citation_expanded(ctx, reference_id, reference)
        return citation_view(reference, chunk, document)

    async def _record_citation_expanded(
        self, ctx: ActorContext, reference_id: str, reference: CitationReference
    ) -> None:
        """FR-OPS-002「引用展开」事件：读路径上的统计事件，写失败不影响展开本身。"""
        try:
            async with uow() as tx:
                append_outbox(
                    tx,
                    event_type="citation.expanded",
                    aggregate_id=reference_id,
                    request_id=ctx.trace_request_id,
                    metadata={
                        "reference_id": reference_id,
                        "document_id": reference.document_id,
                        "version_id": reference.version_id,
                    },
                )
                await tx.commit()
        except Exception:  # noqa: BLE001 - 统计事件不得让引用展开失败
            logger.warning("citation.expanded 事件写入失败 reference_id=%s", reference_id)


knowledge = KnowledgeService()


__all__ = ["KnowledgeService", "knowledge"]
