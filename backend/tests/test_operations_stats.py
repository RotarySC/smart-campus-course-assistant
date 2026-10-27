"""运行统计查询面（FR-OPS-002 / NFR-OBS-001）。

覆盖的是"能不能回答 emptY/failed/cancelled/timeout 各多少"这个验收条件：
- 分类口径：successed / empty / failed / cancelled / timeout / limit_reached / auth_expired；
- 窗口：学校时区自然日、含起止、上限 31 天、窗外数据不计入；
- 写入与工具计数：计划新建/删除/可重试失败、工具失败、批次、草稿形成、引用展开；
- 权限：仅管理员；严格查询（未知参数 422）。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import update

from app.adapters.db.models import (
    AuditEvent,
    ChatRequest,
    DocumentBatch,
    OutboxEvent,
    StudyPlan,
    WriteOperation,
)
from app.adapters.db.uow import uow
from app.shared.clock import now_utc, school_date, to_db
from app.shared.ids import (
    PREFIX_AUDIT,
    PREFIX_BATCH,
    PREFIX_OUTBOX,
    PREFIX_PLAN,
    new_id,
)
from tests.assistant_support import make_chat_request, session_id_for_token

API = "/api/v1/admin/stats/overview"


async def _seed_request(seeded, *, state: str, reason: str | None, days_ago: int = 0) -> str:
    """造一条指定终态的轮次：先按 running 插入（满足状态机约束），再改终态字段。"""
    session_id = await session_id_for_token(seeded["student_token"])
    chat = await make_chat_request(
        user_id=seeded["student"]["id"], session_id=session_id, state="running"
    )
    accepted_at = to_db(now_utc() - timedelta(days=days_ago))
    async with uow() as tx:
        await tx.session.execute(
            update(ChatRequest)
            .where(ChatRequest.id == chat["request_id"])
            .values(
                state=state,
                terminal_reason=reason,
                accepted_at=accepted_at,
                finished_at=accepted_at if reason else None,
                lease_until=None,
            )
        )
        await tx.commit()
    return chat["request_id"]


async def _seed_events(seeded, *, empty_answers: int, drafts: int, citations: int) -> None:
    async with uow() as tx:
        for _ in range(empty_answers):
            tx.session.add(
                OutboxEvent(
                    id=new_id(PREFIX_OUTBOX),
                    event_type="chat_finished",
                    aggregate_id=None,
                    request_id="req_stats",
                    metadata_json={"state": "succeeded", "corpus_empty": True},
                    state="pending",
                    attempts=0,
                    next_run_at=to_db(now_utc()),
                    created_at=to_db(now_utc()),
                )
            )
        for event_type, amount in (("draft.formed", drafts), ("citation.expanded", citations)):
            for _ in range(amount):
                tx.session.add(
                    OutboxEvent(
                        id=new_id(PREFIX_OUTBOX),
                        event_type=event_type,
                        aggregate_id=None,
                        request_id="req_stats",
                        metadata_json={},
                        state="pending",
                        attempts=0,
                        next_run_at=to_db(now_utc()),
                        created_at=to_db(now_utc()),
                    )
                )
        await tx.commit()


async def _seed_tool_audits(*, ok: int, failed: int) -> None:
    async with uow() as tx:
        for result, amount in (("ok", ok), ("INTERNAL_ERROR", failed)):
            for _ in range(amount):
                tx.session.add(
                    AuditEvent(
                        id=new_id(PREFIX_AUDIT),
                        actor_id=None,
                        action="tool.search_course_docs",
                        object_type="chat_request",
                        object_id=None,
                        result=result,
                        request_id="req_stats",
                        duration_ms=12,
                        metadata_json=None,
                        created_at=to_db(now_utc()),
                    )
                )
        await tx.commit()


async def _seed_operations(seeded, *, created: int, deleted: int, retryable_failed: int) -> None:
    """按真实保存顺序造数据：pending 操作 → 计划（引用操作）→ 操作落终态。

    ``study_plans.operation_id`` 与 ``write_operations.plan_id`` 互为外键，必须分三步写。
    """
    async with uow() as tx:
        now = to_db(now_utc())
        index = 0
        for state, retryable, amount in (
            ("succeeded", False, created),
            ("deleted", False, deleted),
            ("failed", True, retryable_failed),
        ):
            for _ in range(amount):
                index += 1
                operation_id = f"op_stats_{index}"
                operation = WriteOperation(
                    user_id=seeded["student"]["id"],
                    operation_id=operation_id,
                    source="assistant",
                    origin_chat_request_id=None,
                    authorization_chat_request_id=None,
                    draft_id=None,
                    draft_version=None,
                    content_digest=b"\x01" * 32,
                    state="pending",
                    resolution="confirmed",
                    plan_id=None,
                    error_code=None,
                    retryable=False,
                    created_at=now,
                    updated_at=now,
                )
                tx.session.add(operation)
                await tx.session.flush()
                plan_id = None
                if state != "failed":
                    plan_id = new_id(PREFIX_PLAN)
                    tx.session.add(
                        StudyPlan(
                            id=plan_id,
                            user_id=seeded["student"]["id"],
                            operation_id=operation_id,
                            # ck_plan_body：删除态必须清空标题与正文
                            title=None if state == "deleted" else "统计用例计划",
                            goal=None,
                            start_date=None,
                            end_date=None,
                            content=None if state == "deleted" else "统计用例正文",
                            source="assistant",
                            basis_snapshot=None
                            if state == "deleted"
                            else {"types": ["general"], "references": []},
                            version=1,
                            deleted_at=now if state == "deleted" else None,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    await tx.session.flush()
                operation.state = state
                operation.plan_id = plan_id
                operation.error_code = "INTERNAL_ERROR" if state == "failed" else None
                operation.retryable = retryable
                await tx.session.flush()
        await tx.commit()


async def _seed_batches(seeded, *, published: int, failed: int) -> None:
    async with uow() as tx:
        now = to_db(now_utc())
        for state, amount in (("published", published), ("failed", failed)):
            for _ in range(amount):
                tx.session.add(
                    DocumentBatch(
                        id=new_id(PREFIX_BATCH),
                        uploaded_by=seeded["admin"]["id"],
                        state=state,
                        expected_files=1,
                        total_bytes=1024,
                        error_code=None,
                        published_at=now if state == "published" else None,
                        created_at=now,
                        updated_at=now,
                    )
                )
        await tx.commit()


async def test_stats_requires_admin(client, seeded):
    anonymous = await client.get(API)
    assert anonymous.status_code == 401
    student = await client.get(API, headers=seeded["student_headers"])
    assert student.status_code == 403
    assert student.json()["error"]["code"] == "FORBIDDEN"


async def test_stats_default_window_covers_recent_week(client, seeded):
    response = await client.get(API, headers=seeded["admin_headers"])
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    window = data["window"]
    assert window["to_date"] == school_date().isoformat()
    assert window["school_timezone"] == "Asia/Shanghai"
    assert data["requests"]["total"] == 0
    assert data["operations"]["plans_created"] == 0


async def test_stats_classifies_answer_termination(client, seeded):
    await _seed_request(seeded, state="succeeded", reason="OK")
    await _seed_request(seeded, state="failed", reason="EXECUTION_TIMEOUT")
    await _seed_request(seeded, state="failed", reason="CALL_LIMIT_REACHED")
    await _seed_request(seeded, state="failed", reason="SESSION_EXPIRED")
    await _seed_request(seeded, state="failed", reason="RETRIEVAL_UNAVAILABLE")
    await _seed_request(seeded, state="cancelled", reason="USER_CANCELLED")
    await _seed_request(seeded, state="running", reason=None)
    await _seed_events(seeded, empty_answers=1, drafts=0, citations=0)

    response = await client.get(API, headers=seeded["admin_headers"])
    assert response.status_code == 200, response.text
    requests = response.json()["data"]["requests"]

    assert requests["total"] == 7
    assert requests["succeeded"] == 1
    # succeeded 里 1 条被 chat_finished 的 corpus_empty 标成"空结果"
    assert requests["empty"] == 1
    assert requests["succeeded_with_evidence"] == 0
    assert requests["cancelled"] == 1
    assert requests["timeout"] == 1
    assert requests["limit_reached"] == 1
    assert requests["auth_expired"] == 1
    # RETRIEVAL_UNAVAILABLE 不归入 empty（检索失败≠没找到）
    assert requests["failed"] == 1
    assert requests["pending"] == 1


async def test_stats_counts_operations_and_tools(client, seeded):
    await _seed_operations(seeded, created=2, deleted=1, retryable_failed=1)
    await _seed_tool_audits(ok=3, failed=1)
    await _seed_events(seeded, empty_answers=0, drafts=2, citations=5)
    await _seed_batches(seeded, published=1, failed=2)

    response = await client.get(API, headers=seeded["admin_headers"])
    assert response.status_code == 200, response.text
    operations = response.json()["data"]["operations"]

    assert operations["plans_created"] == 2
    assert operations["plans_deleted"] == 1
    assert operations["plans_retryable_failed"] == 1
    assert operations["drafts_formed"] == 2
    assert operations["citations_expanded"] == 5
    assert operations["tool_calls"] == 4
    assert operations["tool_failures"] == 1
    assert operations["batches_published"] == 1
    assert operations["batches_failed"] == 2


async def test_stats_window_excludes_older_requests(client, seeded):
    await _seed_request(seeded, state="succeeded", reason="OK")
    await _seed_request(seeded, state="succeeded", reason="OK", days_ago=10)

    today = school_date()
    in_window = await client.get(
        API,
        params={
            "from_date": (today - timedelta(days=1)).isoformat(),
            "to_date": today.isoformat(),
        },
        headers=seeded["admin_headers"],
    )
    assert in_window.status_code == 200, in_window.text
    assert in_window.json()["data"]["requests"]["total"] == 1

    wide = await client.get(
        API,
        params={
            "from_date": (today - timedelta(days=10)).isoformat(),
            "to_date": today.isoformat(),
        },
        headers=seeded["admin_headers"],
    )
    assert wide.json()["data"]["requests"]["total"] == 2


@pytest.mark.parametrize(
    "params",
    [
        {"from_date": "2026-10-27", "to_date": "2026-10-26"},
        {"from_date": "2026-09-01", "to_date": "2026-10-27"},
        {"from_date": "not-a-date"},
        {"unknown_param": "1"},
    ],
)
async def test_stats_rejects_bad_window(client, seeded, params):
    response = await client.get(API, params=params, headers=seeded["admin_headers"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
