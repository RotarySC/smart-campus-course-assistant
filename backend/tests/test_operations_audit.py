"""FR-OPS-001 的两个缺口：审计「耗时」与「权限拒绝」可追踪。

- 耗时：请求级打点后，计划/课表/学生/文档等审计不再为 NULL；
- 权限拒绝：403（角色不符）与 404（跨用户/不存在）都要留审计行，便于事后追溯。
"""

from __future__ import annotations

from sqlalchemy import select

from app.adapters.db.engine import get_session_factory
from app.adapters.db.models import AuditEvent


async def _latest_audit(action: str) -> AuditEvent | None:
    async with get_session_factory()() as session:
        result = await session.execute(
            select(AuditEvent)
            .where(AuditEvent.action == action)
            .order_by(AuditEvent.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def test_schedule_create_audit_records_duration(client, seeded):
    """请求级打点后，课表等业务审计的 duration_ms 不再是 NULL。"""
    created = await client.post(
        "/api/v1/admin/schedules",
        json={
            "student_id": seeded["student"]["id"],
            "course_id": seeded["course"]["id"],
            "class_date": "2026-11-03",
            "start_time": "08:00",
            "end_time": "09:40",
        },
        headers=seeded["admin_headers"],
    )
    assert created.status_code == 201, created.text

    audit = await _latest_audit("schedule.create")
    assert audit is not None
    assert audit.duration_ms is not None
    assert audit.duration_ms >= 0


async def test_forbidden_access_is_audited(client, seeded):
    response = await client.get(
        "/api/v1/admin/students", headers=seeded["student_headers"]
    )
    assert response.status_code == 403

    audit = await _latest_audit("access.denied")
    assert audit is not None
    assert audit.result == "FORBIDDEN"
    assert audit.actor_id == seeded["student"]["id"]
    assert audit.request_id
    assert audit.metadata_json["path"] == "/api/v1/admin/students"


async def test_cross_user_not_found_is_audited(client, seeded):
    response = await client.get(
        "/api/v1/me/plans/plan_does_not_exist", headers=seeded["student_headers"]
    )
    assert response.status_code == 404

    audit = await _latest_audit("access.denied")
    assert audit is not None
    assert audit.result == "RESOURCE_NOT_FOUND"
    assert audit.actor_id == seeded["student"]["id"]


async def test_worker_audit_without_request_has_no_duration(seeded):
    """没有请求上下文时不臆造耗时（worker/CLI 路径保持 NULL）。"""
    from app.adapters.db.uow import uow
    from app.modules.operations.service import append_audit

    async with uow() as tx:
        audit_id = append_audit(
            tx,
            action="worker.test",
            object_type="document",
            object_id="doc_demo",
            result="ok",
            request_id="req_worker_test",
        )
        await tx.commit()

    async with get_session_factory()() as session:
        row = await session.get(AuditEvent, audit_id)
    assert row is not None
    assert row.duration_ms is None
