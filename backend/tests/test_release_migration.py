"""迁移生命周期与数据库反注入测试（Phase 5 前置）。

- 空库 ``upgrade head`` = 23 表；``downgrade base`` = 0；二次 upgrade 幂等；
- CHECK / 唯一键 / 外键 / 长度约束对坏数据必须拒绝（数据库层反注入，不依赖应用校验）；
- 每项断言记录耗时，便于 Phase 5 报告直接引用。

真实 MySQL ``cca_test_core``；本文件会临时 downgrade，结束时强制恢复 ``head``。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

BACKEND_DIR = Path(__file__).resolve().parent.parent

EXPECTED_TABLES = {
    "users",
    "auth_sessions",
    "courses",
    "schedules",
    "conversation_states",
    "chat_requests",
    "ai_capacity_slots",
    "plan_drafts",
    "plan_draft_versions",
    "write_operations",
    "save_grants",
    "study_plans",
    "assistant_save_slots",
    "corpus_control",
    "document_batches",
    "documents",
    "document_versions",
    "chunks",
    "citation_references",
    "background_tasks",
    "storage_attempts",
    "audit_events",
    "outbox_events",
}
assert len(EXPECTED_TABLES) == 23


def _run_alembic(*args: str) -> tuple[int, str, float]:
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=dict(os.environ),
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - started
    return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), elapsed


async def _table_names() -> set[str]:
    from app.adapters.db.engine import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = DATABASE()"
                )
            )
        ).all()
    return {row[0] for row in rows}


async def test_migration_upgrade_downgrade_upgrade_idempotent(db):
    timings: list[tuple[str, float]] = []
    try:
        code, output, elapsed = _run_alembic("downgrade", "base")
        timings.append(("downgrade base", elapsed))
        assert code == 0, output
        names = await _table_names()
        assert names <= {"alembic_version"}, f"downgrade 后仍有业务表: {sorted(names - {'alembic_version'})}"

        code, output, elapsed = _run_alembic("upgrade", "head")
        timings.append(("upgrade head (empty)", elapsed))
        assert code == 0, output
        names = await _table_names()
        tables = names - {"alembic_version"}
        assert tables == EXPECTED_TABLES, (
            f"表集合不符：多 {sorted(tables - EXPECTED_TABLES)} 少 {sorted(EXPECTED_TABLES - tables)}"
        )
        assert len(tables) == 23

        code, output, elapsed = _run_alembic("upgrade", "head")
        timings.append(("upgrade head (idempotent)", elapsed))
        assert code == 0, output
        assert (await _table_names()) - {"alembic_version"} == EXPECTED_TABLES
    finally:
        code, output, elapsed = _run_alembic("upgrade", "head")
        timings.append(("restore head", elapsed))
        assert code == 0, output
    for label, elapsed in timings:
        print(f"[migration] {label}: {elapsed:.2f}s")


async def _expect_db_reject(sql: str, params: dict, marker: str | tuple[str, ...]) -> float:
    """执行坏数据插入，断言数据库拒绝且错误含指定约束/错误标记。"""
    from app.adapters.db.engine import get_engine

    engine = get_engine()
    started = time.perf_counter()
    async with engine.connect() as conn:
        with pytest.raises(DBAPIError) as excinfo:
            await conn.execute(text(sql), params)
            await conn.commit()
        await conn.rollback()
    elapsed = time.perf_counter() - started
    message = str(excinfo.value)
    markers = (marker,) if isinstance(marker, str) else marker
    assert any(item in message for item in markers), (
        f"期望错误含 {markers!r}，实际：{message[:300]}"
    )
    return elapsed


async def test_database_rejects_invalid_data(db):
    """CHECK / 唯一键 / FK / 长度：数据库层必须拒绝（不依赖应用层校验）。"""
    from app.adapters.db.engine import get_engine

    engine = get_engine()
    now = "UTC_TIMESTAMP(6)"

    async with engine.begin() as conn:
        # 合法前置数据
        await conn.execute(
            text(
                "INSERT INTO users (id, account, account_norm, display_name, password_hash, "
                "role, enabled, auth_version, version, created_at, updated_at) "
                f"VALUES ('usr_valid', 'valid_user', :norm, '有效用户', 'x', 'student', 1, 1, 1, {now}, {now})"
            ),
            {"norm": b"valid_user"},
        )
        await conn.execute(
            text(
                "INSERT INTO courses (id, code, code_norm, name, enabled, version, created_at, updated_at) "
                f"VALUES ('crs_valid', 'CS101', :norm, '数据结构', 1, 1, {now}, {now})"
            ),
            {"norm": b"cs101"},
        )
        await conn.execute(
            text(
                "INSERT INTO schedules (id, user_id, course_id, class_date, start_time, end_time, "
                f"version, created_at, updated_at) VALUES ('sch_valid', 'usr_valid', 'crs_valid', "
                f"'2026-11-02', '08:00:00', '09:00:00', 1, {now}, {now})"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO write_operations (user_id, operation_id, source, content_digest, state, "
                f"resolution, retryable, created_at, updated_at) VALUES ('usr_valid', 'op_valid', "
                f"'manual', :digest, 'pending', 'confirmed', 0, {now}, {now})"
            ),
            {"digest": b"\x00" * 32},
        )

    results: list[tuple[str, float]] = []

    results.append(
        (
            "users.role CHECK",
            await _expect_db_reject(
                "INSERT INTO users (id, account, account_norm, display_name, password_hash, role, "
                f"enabled, auth_version, version, created_at, updated_at) VALUES "
                f"('usr_bad_role', 'bad_role', :norm, 'x', 'x', 'teacher', 1, 1, 1, {now}, {now})",
                {"norm": b"bad_role"},
                "ck_users_role",
            ),
        )
    )
    results.append(
        (
            "users.account_norm UNIQUE",
            await _expect_db_reject(
                "INSERT INTO users (id, account, account_norm, display_name, password_hash, role, "
                f"enabled, auth_version, version, created_at, updated_at) VALUES "
                f"('usr_dup', 'dup_user', :norm, 'x', 'x', 'student', 1, 1, 1, {now}, {now})",
                {"norm": b"valid_user"},
                "uq_users_account",
            ),
        )
    )
    results.append(
        (
            "users.account 长度下界 CHECK",
            await _expect_db_reject(
                "INSERT INTO users (id, account, account_norm, display_name, password_hash, role, "
                f"enabled, auth_version, version, created_at, updated_at) VALUES "
                f"('usr_short', 'ab', :norm, 'x', 'x', 'student', 1, 1, 1, {now}, {now})",
                {"norm": b"ab"},
                "ck_users_names",
            ),
        )
    )
    results.append(
        (
            "users.account 越界长度",
            await _expect_db_reject(
                "INSERT INTO users (id, account, account_norm, display_name, password_hash, role, "
                f"enabled, auth_version, version, created_at, updated_at) VALUES "
                f"('usr_long', :acct, :norm, 'x', 'x', 'student', 1, 1, 1, {now}, {now})",
                {"acct": "x" * 65, "norm": b"x" * 65},
                "Data too long",
            ),
        )
    )
    results.append(
        (
            "schedules.start<end CHECK",
            await _expect_db_reject(
                "INSERT INTO schedules (id, user_id, course_id, class_date, start_time, end_time, "
                f"version, created_at, updated_at) VALUES ('sch_bad_time', 'usr_valid', 'crs_valid', "
                f"'2026-11-02', '10:00:00', '09:00:00', 1, {now}, {now})",
                {},
                "ck_schedule_times",
            ),
        )
    )
    results.append(
        (
            "schedules 分钟精度 CHECK",
            await _expect_db_reject(
                "INSERT INTO schedules (id, user_id, course_id, class_date, start_time, end_time, "
                f"version, created_at, updated_at) VALUES ('sch_bad_sec', 'usr_valid', 'crs_valid', "
                f"'2026-11-02', '08:00:30', '09:00:00', 1, {now}, {now})",
                {},
                "ck_schedule_times",
            ),
        )
    )
    results.append(
        (
            "schedules 精确重复 UNIQUE",
            await _expect_db_reject(
                "INSERT INTO schedules (id, user_id, course_id, class_date, start_time, end_time, "
                f"version, created_at, updated_at) VALUES ('sch_dup', 'usr_valid', 'crs_valid', "
                f"'2026-11-02', '08:00:00', '09:00:00', 1, {now}, {now})",
                {},
                "uq_schedule_exact",
            ),
        )
    )
    results.append(
        (
            "schedules.user_id 外键",
            await _expect_db_reject(
                "INSERT INTO schedules (id, user_id, course_id, class_date, start_time, end_time, "
                f"version, created_at, updated_at) VALUES ('sch_fk', 'usr_missing', 'crs_valid', "
                f"'2026-11-02', '11:00:00', '12:00:00', 1, {now}, {now})",
                {},
                "fk_schedule_user",
            ),
        )
    )
    results.append(
        (
            "study_plans 日期成对 CHECK",
            await _expect_db_reject(
                "INSERT INTO study_plans (id, user_id, operation_id, title, goal, start_date, end_date, "
                f"content, source, basis_snapshot, version, created_at, updated_at) VALUES "
                f"('plan_bad_dates', 'usr_valid', 'op_valid', 'x', NULL, '2026-11-02', NULL, '正文', "
                f"'manual', NULL, 1, {now}, {now})",
                {},
                "ck_plan_dates",
            ),
        )
    )
    results.append(
        (
            "write_operations.state CHECK",
            await _expect_db_reject(
                "INSERT INTO write_operations (user_id, operation_id, source, content_digest, state, "
                f"resolution, retryable, created_at, updated_at) VALUES ('usr_valid', 'op_bad_state', "
                f"'manual', :digest, 'weird', 'confirmed', 0, {now}, {now})",
                {"digest": b"\x00" * 32},
                # 坏 state 同时违反 ck_operations_result（MySQL 可能先报后者）
                ("ck_operations_state", "ck_operations_result"),
            ),
        )
    )
    results.append(
        (
            "auth_sessions.expires_at CHECK",
            await _expect_db_reject(
                "INSERT INTO auth_sessions (id, user_id, token_digest, auth_version, expires_at, "
                f"revoked_at, created_at) VALUES ('ses_bad_exp', 'usr_valid', :digest, 1, {now}, NULL, {now})",
                {"digest": b"\x01" * 32},
                "ck_sessions_expiry",
            ),
        )
    )
    results.append(
        (
            "outbox_events.state CHECK",
            await _expect_db_reject(
                "INSERT INTO outbox_events (id, event_type, aggregate_id, request_id, metadata, state, "
                f"attempts, next_run_at, created_at) VALUES ('evt_bad', 'x', NULL, 'req_x', JSON_OBJECT(), "
                f"'weird', 0, {now}, {now})",
                {},
                "ck_outbox_state",
            ),
        )
    )

    for label, elapsed in results:
        print(f"[db-reject] {label}: {elapsed * 1000:.1f}ms")
    assert len(results) == 12
