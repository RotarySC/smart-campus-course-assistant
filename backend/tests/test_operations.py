"""运维面定向测试：审计 / Outbox / 种子（真实 MySQL）。"""

from __future__ import annotations

from sqlalchemy import func, select


async def test_seed_demo_idempotent(db):
    from app.cli.seed import seed_demo
    from app.adapters.db.models import Course, Schedule, StudyPlan, User

    first = await seed_demo()
    assert first["users"]["student_demo"]["created"] is True
    assert first["users"]["admin_demo"]["created"] is True
    assert first["courses"]["CS101"]["created"] is True
    assert first["schedules_created"] == 3
    assert first["demo_plan_created"] == 1

    second = await seed_demo()
    assert second["users"]["student_demo"]["created"] is False
    assert second["users"]["admin_demo"]["created"] is False
    assert second["courses"]["CS101"]["created"] is False
    assert second["schedules_created"] == 0
    assert second["demo_plan_created"] == 0

    async with db() as session:
        assert await session.scalar(select(func.count()).select_from(User)) == 2
        assert await session.scalar(select(func.count()).select_from(Course)) == 2
        assert await session.scalar(select(func.count()).select_from(Schedule)) == 3
        assert await session.scalar(select(func.count()).select_from(StudyPlan)) == 1


async def test_seed_accounts_can_login(client):
    from app.cli.seed import seed_demo

    await seed_demo()
    for account in ("student_demo", "admin_demo"):
        response = await client.post(
            "/api/v1/auth/login",
            json={"account": account, "password": "demo1234"},
        )
        assert response.status_code == 200, (account, response.text)


async def test_audit_and_outbox_written_in_same_transaction(client, seeded, db):
    from app.adapters.db.models import AuditEvent, OutboxEvent

    headers = seeded["student_headers"]
    response = await client.post(
        "/api/v1/me/plans",
        json={"title": "审计计划", "content": "正文内容不应进入审计"},
        headers={**headers, "Idempotency-Key": "op-audit-0001"},
    )
    assert response.status_code == 201
    plan_id = response.json()["data"]["plan_id"]

    async with db() as session:
        audits = list(
            (
                await session.execute(
                    select(AuditEvent).where(AuditEvent.action == "plan_saved")
                )
            )
            .scalars()
            .all()
        )
        outbox = list(
            (
                await session.execute(
                    select(OutboxEvent).where(OutboxEvent.event_type == "plan_saved")
                )
            )
            .scalars()
            .all()
        )
    assert len(audits) == 1
    assert audits[0].object_id == plan_id
    assert audits[0].actor_id == seeded["student"]["id"]
    assert audits[0].request_id.startswith("req_")
    # 审计 metadata 不含正文
    assert "正文内容不应进入审计" not in str(audits[0].metadata_json)
    assert len(outbox) == 1
    assert outbox[0].aggregate_id == plan_id
    assert outbox[0].state == "pending"
    assert outbox[0].metadata_json["operation_id"] == "op-audit-0001"


async def test_schedule_mutation_writes_audit(client, seeded, db):
    from app.adapters.db.models import AuditEvent

    headers = seeded["admin_headers"]
    created = await client.post(
        "/api/v1/admin/schedules",
        json={
            "student_id": seeded["student"]["id"],
            "course_id": seeded["course"]["id"],
            "class_date": "2026-11-02",
            "start_time": "08:00",
            "end_time": "09:40",
        },
        headers=headers,
    )
    assert created.status_code == 201

    async with db() as session:
        audits = list(
            (
                await session.execute(
                    select(AuditEvent).where(AuditEvent.action == "schedule.create")
                )
            )
            .scalars()
            .all()
        )
    assert len(audits) == 1
    assert audits[0].object_id == created.json()["data"]["id"]
    assert audits[0].actor_id == seeded["admin"]["id"]


async def test_outbox_noop_dispatch(db):
    from app.adapters.db.models import OutboxEvent
    from app.modules.operations.service import dispatch_outbox_once
    from app.shared.clock import now_utc, to_db
    from app.shared.ids import PREFIX_OUTBOX, new_id

    now = to_db(now_utc())
    async with db() as session:
        for index in range(2):
            session.add(
                OutboxEvent(
                    id=new_id(PREFIX_OUTBOX),
                    event_type="plan_saved",
                    aggregate_id=f"plan_{index}",
                    request_id="req_test",
                    metadata_json={"index": index},
                    state="pending",
                    attempts=0,
                    next_run_at=now,
                    created_at=now,
                )
            )
        await session.commit()

    assert await dispatch_outbox_once() == 2
    assert await dispatch_outbox_once() == 0

    async with db() as session:
        events = list((await session.execute(select(OutboxEvent))).scalars().all())
    assert all(event.state == "published" for event in events)
    assert all(event.published_at is not None for event in events)


async def test_worker_run_once_importable(db):
    from app.entrypoints.worker import run_once

    # 空转一轮：Phase 2 起 run_once 返回结构化回执（processed/counters/recovered_leases），
    # 不再返回整数；空队列时 processed == 0 且无成功计数。
    result = await run_once(owner="test-worker")
    assert isinstance(result, dict)
    assert result["processed"] == 0
    assert result["counters"] == {}
    assert result["recovered_leases"] == 0
