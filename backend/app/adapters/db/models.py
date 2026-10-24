"""SQLAlchemy 2.0 异步模型：与 ``contracts/cca_schema_v0.1.sql`` 的 23 张表一一对应。

说明：
- 迁移以原始 DDL 为权威（``migrations/versions/0001_initial_schema.py``），本文件只服务
  查询/写入；索引、CHECK、生成列、级联约束均由 DDL 保证，不在 ORM 层重复声明。
- 不使用 ORM ``relationship``：跨模块存取统一走显式 SQL 与 Interface，避免异步懒加载。
- 时间列统一按 UTC ``datetime``（naive 存库，见 ``shared.clock.to_db/from_db``）。
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.dialects.mysql import TIME as MySQLTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# 1. 身份
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    account = Column(String(64), nullable=False)
    account_norm = Column(LargeBinary(768), nullable=False)
    display_name = Column(String(50), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    auth_version = Column(BigInteger, nullable=False, default=1)
    version = Column(BigInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False)
    token_digest = Column(LargeBinary(32), nullable=False)
    auth_version = Column(BigInteger, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)


# --------------------------------------------------------------------------- #
# 2. 课程与课表
# --------------------------------------------------------------------------- #
class Course(Base):
    __tablename__ = "courses"

    id = Column(String(64), primary_key=True)
    code = Column(String(32), nullable=False)
    code_norm = Column(LargeBinary(384), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    version = Column(BigInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False)
    course_id = Column(String(64), nullable=False)
    class_date = Column(Date, nullable=False)
    start_time = Column(MySQLTime(fsp=0), nullable=False)
    end_time = Column(MySQLTime(fsp=0), nullable=False)
    location = Column(String(200), nullable=True)
    overlap_reason = Column(String(500), nullable=True)
    version = Column(BigInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


# --------------------------------------------------------------------------- #
# 3. 对话与容量（Phase 3 使用；本阶段建表冻结）
# --------------------------------------------------------------------------- #
class ConversationState(Base):
    __tablename__ = "conversation_states"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False)
    session_id = Column(String(64), nullable=False)
    active_request_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class ChatRequest(Base):
    __tablename__ = "chat_requests"

    id = Column(String(64), primary_key=True)
    client_request_id = Column(String(64), nullable=False)
    user_id = Column(String(64), nullable=False)
    session_id = Column(String(64), nullable=False)
    conversation_id = Column(String(64), nullable=False)
    request_digest = Column(LargeBinary(32), nullable=False)
    state = Column(String(16), nullable=False)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    accepted_at = Column(DateTime, nullable=False)
    deadline_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    school_timezone = Column(String(64), nullable=False)
    model_calls = Column(Integer, nullable=False, default=0)
    tool_calls = Column(Integer, nullable=False, default=0)
    owner_instance = Column(String(64), nullable=True)
    fence = Column(BigInteger, nullable=False, default=1)
    lease_until = Column(DateTime, nullable=True)
    terminal_reason = Column(String(64), nullable=True)
    plan_id = Column(String(64), nullable=True)
    operation_id = Column(String(64), nullable=True)


class AICapacitySlot(Base):
    __tablename__ = "ai_capacity_slots"

    slot_no = Column(Integer, primary_key=True)
    request_id = Column(String(64), nullable=True)
    owner_instance = Column(String(64), nullable=True)
    fence = Column(BigInteger, nullable=False, default=0)
    lease_until = Column(DateTime, nullable=True)


# --------------------------------------------------------------------------- #
# 4. 草稿、许可、操作与计划
# --------------------------------------------------------------------------- #
class PlanDraft(Base):
    __tablename__ = "plan_drafts"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False)
    session_id = Column(String(64), nullable=False)
    conversation_id = Column(String(64), nullable=False)
    origin_chat_request_id = Column(String(64), nullable=False)
    current_version = Column(BigInteger, nullable=False, default=1)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class PlanDraftVersion(Base):
    __tablename__ = "plan_draft_versions"

    draft_id = Column(String(64), primary_key=True)
    draft_version = Column(BigInteger, primary_key=True)
    operation_id = Column(String(64), nullable=False)
    schema_version = Column(Integer, nullable=False, default=1)
    payload = Column(JSON(none_as_null=True), nullable=True)
    content_digest = Column(LargeBinary(32), nullable=False)
    created_at = Column(DateTime, nullable=False)
    payload_cleared_at = Column(DateTime, nullable=True)


class WriteOperation(Base):
    __tablename__ = "write_operations"

    user_id = Column(String(64), primary_key=True)
    operation_id = Column(String(96), primary_key=True)
    source = Column(String(16), nullable=False)
    origin_chat_request_id = Column(String(64), nullable=True)
    authorization_chat_request_id = Column(String(64), nullable=True)
    draft_id = Column(String(64), nullable=True)
    draft_version = Column(BigInteger, nullable=True)
    content_digest = Column(LargeBinary(32), nullable=False)
    state = Column(String(16), nullable=False)
    resolution = Column(String(16), nullable=False, default="confirmed")
    plan_id = Column(String(64), nullable=True)
    error_code = Column(String(64), nullable=True)
    retryable = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class SaveGrant(Base):
    __tablename__ = "save_grants"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False)
    session_id = Column(String(64), nullable=False)
    trace_request_id = Column(String(64), nullable=False)
    authorization_kind = Column(String(32), nullable=False)
    authorization_chat_request_id = Column(String(64), nullable=True)
    draft_id = Column(String(64), nullable=True)
    draft_version = Column(BigInteger, nullable=True)
    operation_id = Column(String(96), nullable=False)
    content_digest = Column(LargeBinary(32), nullable=False)
    state = Column(String(16), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False)
    operation_id = Column(String(96), nullable=False)
    title = Column(String(100), nullable=True)
    goal = Column(String(500), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    content = Column(MEDIUMTEXT, nullable=True)
    source = Column(String(16), nullable=False)
    basis_snapshot = Column(JSON(none_as_null=True), nullable=True)
    version = Column(BigInteger, nullable=False, default=1)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class AssistantSaveSlot(Base):
    __tablename__ = "assistant_save_slots"

    user_id = Column(String(64), primary_key=True)
    request_id = Column(String(64), primary_key=True)
    operation_id = Column(String(96), nullable=False)
    plan_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)


# --------------------------------------------------------------------------- #
# 5. 知识链路（Phase 2 使用；本阶段建表冻结）
# --------------------------------------------------------------------------- #
class CorpusControl(Base):
    __tablename__ = "corpus_control"

    singleton_id = Column(Integer, primary_key=True)
    revision = Column(BigInteger, nullable=False, default=0)
    active_vector_space = Column(String(128), nullable=True)
    publish_frozen = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, nullable=False)


class DocumentBatch(Base):
    __tablename__ = "document_batches"

    id = Column(String(64), primary_key=True)
    uploaded_by = Column(String(64), nullable=False)
    state = Column(String(16), nullable=False)
    expected_files = Column(Integer, nullable=False)
    total_bytes = Column(BigInteger, nullable=False)
    error_code = Column(String(64), nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True)
    batch_id = Column(String(64), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_type = Column(String(8), nullable=False)
    byte_size = Column(BigInteger, nullable=False)
    original_storage_key = Column(String(512), nullable=True)
    visibility = Column(String(16), nullable=False, default="unpublished")
    processing_state = Column(String(32), nullable=False)
    active_version_id = Column(String(64), nullable=True)
    mutation_task_id = Column(String(64), nullable=True)
    error_code = Column(String(64), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    cleanup_state = Column(String(16), nullable=False, default="not_required")
    version = Column(BigInteger, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(String(64), primary_key=True)
    document_id = Column(String(64), nullable=False)
    version_no = Column(BigInteger, nullable=False)
    state = Column(String(16), nullable=False)
    content_digest = Column(LargeBinary(32), nullable=True)
    parser_config_digest = Column(LargeBinary(32), nullable=False)
    vector_space = Column(String(128), nullable=False)
    selected_attempt_id = Column(String(64), nullable=True)
    extracted_text_key = Column(String(512), nullable=True)
    error_code = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False)


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(64), primary_key=True)
    document_id = Column(String(64), nullable=False)
    version_id = Column(String(64), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text_content = Column(MEDIUMTEXT, nullable=False)
    page_number = Column(Integer, nullable=True)
    location_label = Column(String(100), nullable=False)
    content_digest = Column(LargeBinary(32), nullable=False)


class CitationReference(Base):
    __tablename__ = "citation_references"

    id = Column(String(64), primary_key=True)
    document_id = Column(String(64), nullable=False)
    version_id = Column(String(64), nullable=False)
    chunk_id = Column(String(64), nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)


# --------------------------------------------------------------------------- #
# 6. 任务、审计与 Outbox
# --------------------------------------------------------------------------- #
class BackgroundTask(Base):
    __tablename__ = "background_tasks"

    id = Column(String(64), primary_key=True)
    kind = Column(String(32), nullable=False)
    object_id = Column(String(64), nullable=False)
    dedupe_key = Column(String(96), nullable=False)
    state = Column(String(16), nullable=False)
    priority = Column(Integer, nullable=False, default=0)
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    fence = Column(BigInteger, nullable=False, default=0)
    owner_instance = Column(String(64), nullable=True)
    lease_until = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=False)
    error_code = Column(String(64), nullable=True)
    error_summary = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class StorageAttempt(Base):
    __tablename__ = "storage_attempts"

    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), nullable=False)
    task_fence = Column(BigInteger, nullable=False)
    version_id = Column(String(64), nullable=False)
    file_prefix = Column(String(512), nullable=False)
    vector_namespace = Column(String(512), nullable=False)
    io_state = Column(String(16), nullable=False)
    inflight_writes = Column(Integer, nullable=False, default=0)
    barrier_confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True)
    actor_id = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False)
    object_type = Column(String(32), nullable=False)
    object_id = Column(String(64), nullable=True)
    result = Column(String(32), nullable=False)
    request_id = Column(String(64), nullable=False)
    duration_ms = Column(BigInteger, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(String(64), primary_key=True)
    event_type = Column(String(64), nullable=False)
    aggregate_id = Column(String(64), nullable=True)
    request_id = Column(String(64), nullable=False)
    metadata_json = Column("metadata", JSON, nullable=False)
    state = Column(String(16), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_run_at = Column(DateTime, nullable=False)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)


# 表数自检用（应为 23）
TABLE_COUNT = len(Base.metadata.tables)
