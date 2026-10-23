"""计划 / 草稿 / 保存 / 写入状态定向测试（真实 MySQL，含 10 并发幂等用例）。"""

from __future__ import annotations

import asyncio

import pytest


PLAN_BODY = {
    "title": "第一周学习计划",
    "goal": "掌握基础",
    "content": "周一复习，周三做题。",
}


# --------------------------------------------------------------------------- #
# 手动计划
# --------------------------------------------------------------------------- #
async def test_manual_plan_lifecycle(client, seeded):
    headers = seeded["student_headers"]
    response = await client.post(
        "/api/v1/me/plans",
        json=PLAN_BODY,
        headers={**headers, "Idempotency-Key": "op-manual-0001"},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["status"] == "created"
    assert data["operation_id"] == "op-manual-0001"
    plan_id = data["plan_id"]

    detail = await client.get(f"/api/v1/me/plans/{plan_id}", headers=headers)
    assert detail.status_code == 200
    plan = detail.json()["data"]
    assert set(plan) == {
        "id",
        "title",
        "goal",
        "start_date",
        "end_date",
        "content",
        "source",
        "basis_types",
        "references",
        "version",
        "created_at",
        "updated_at",
    }
    assert plan["source"] == "manual"
    assert plan["basis_types"] == ["general"]
    assert plan["references"] == []
    assert plan["version"] == 1

    listing = await client.get("/api/v1/me/plans", headers=headers)
    assert listing.status_code == 200
    page = listing.json()["data"]
    assert page["total"] == 1 and page["page_size"] == 20

    filtered = await client.get("/api/v1/me/plans?title=第一周", headers=headers)
    assert filtered.json()["data"]["total"] == 1
    filtered = await client.get("/api/v1/me/plans?title=不存在", headers=headers)
    assert filtered.json()["data"]["total"] == 0

    # 幂等：同键同内容 → 200 existing，不新建
    again = await client.post(
        "/api/v1/me/plans",
        json=PLAN_BODY,
        headers={**headers, "Idempotency-Key": "op-manual-0001"},
    )
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "existing"
    assert again.json()["data"]["plan_id"] == plan_id

    # 同键异内容 → 409
    conflict = await client.post(
        "/api/v1/me/plans",
        json={**PLAN_BODY, "title": "另一份计划"},
        headers={**headers, "Idempotency-Key": "op-manual-0001"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    # 写入状态
    operation = await client.get(
        "/api/v1/me/write-operations/op-manual-0001", headers=headers
    )
    assert operation.status_code == 200
    op_data = operation.json()["data"]
    assert op_data["state"] == "succeeded"
    assert op_data["resolution"] == "confirmed"
    assert op_data["plan_id"] == plan_id

    # 未知提交 → pending(recovering)，不解释为确定未保存
    unknown = await client.get(
        "/api/v1/me/write-operations/op-unknown-9999", headers=headers
    )
    assert unknown.status_code == 200
    assert unknown.json()["data"] == {
        "operation_id": "op-unknown-9999",
        "state": "pending",
        "resolution": "recovering",
        "retryable": False,
    }

    # 更新
    patched = await client.patch(
        f"/api/v1/me/plans/{plan_id}",
        json={"title": "改名计划", "expected_version": 1},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["version"] == 2

    stale = await client.patch(
        f"/api/v1/me/plans/{plan_id}",
        json={"title": "再次", "expected_version": 1},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"

    # 删除 → 墓碑
    deleted = await client.delete(
        f"/api/v1/me/plans/{plan_id}?expected_version=2", headers=headers
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True
    assert deleted.json()["data"]["plan_id"] == plan_id

    gone = await client.get(f"/api/v1/me/plans/{plan_id}", headers=headers)
    assert gone.status_code == 404

    tombstone = await client.get(
        "/api/v1/me/write-operations/op-manual-0001", headers=headers
    )
    assert tombstone.json()["data"]["state"] == "deleted"
    assert tombstone.json()["data"]["plan_id"] == plan_id

    # 删除后原键返回 deleted，不重建
    reuse = await client.post(
        "/api/v1/me/plans",
        json=PLAN_BODY,
        headers={**headers, "Idempotency-Key": "op-manual-0001"},
    )
    assert reuse.status_code == 200
    assert reuse.json()["data"]["status"] == "deleted"


async def test_plan_date_and_blank_validation(client, seeded):
    headers = seeded["student_headers"]
    cases = [
        {"title": "x", "content": "y", "start_date": "2026-11-02"},  # 只有开始日期
        {
            "title": "x",
            "content": "y",
            "start_date": "2026-11-05",
            "end_date": "2026-11-02",
        },  # 倒置
        {"title": "   ", "content": "y"},
        {"title": "x", "content": "   "},
    ]
    for index, body in enumerate(cases):
        response = await client.post(
            "/api/v1/me/plans",
            json=body,
            headers={**headers, "Idempotency-Key": f"op-bad-{index}"},
        )
        assert response.status_code == 422, (index, response.text)
        assert response.json()["error"]["code"] == "VALIDATION_FAILED"

    # 合法日期
    ok = await client.post(
        "/api/v1/me/plans",
        json={
            "title": "带日期",
            "content": "正文",
            "start_date": "2026-11-02",
            "end_date": "2026-11-08",
        },
        headers={**headers, "Idempotency-Key": "op-good-dates"},
    )
    assert ok.status_code == 201
    assert ok.json()["data"]["status"] == "created"


async def test_plan_isolation(client, seeded):
    headers = seeded["student_headers"]
    created = await client.post(
        "/api/v1/me/plans",
        json=PLAN_BODY,
        headers={**headers, "Idempotency-Key": "op-iso-0001"},
    )
    plan_id = created.json()["data"]["plan_id"]

    other = await client.get(
        f"/api/v1/me/plans/{plan_id}", headers=seeded["other_headers"]
    )
    assert other.status_code == 404
    assert other.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    other_patch = await client.patch(
        f"/api/v1/me/plans/{plan_id}",
        json={"title": "偷改", "expected_version": 1},
        headers=seeded["other_headers"],
    )
    assert other_patch.status_code == 404

    other_list = await client.get("/api/v1/me/plans", headers=seeded["other_headers"])
    assert other_list.json()["data"]["total"] == 0


# --------------------------------------------------------------------------- #
# 草稿与保存
# --------------------------------------------------------------------------- #
async def test_draft_get_and_revise(client, seeded, make_draft):
    draft = await make_draft()
    headers = seeded["student_headers"]

    response = await client.get(
        f"/api/v1/me/drafts/{draft['draft_id']}", headers=headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {
        "draft_id",
        "draft_version",
        "operation_id",
        "title",
        "goal",
        "start_date",
        "end_date",
        "content",
        "basis_types",
        "references",
        "expires_at",
    }
    assert data["draft_version"] == 1
    assert data["operation_id"] == draft["operation_id"]

    revised = await client.patch(
        f"/api/v1/me/drafts/{draft['draft_id']}",
        json={"title": "改后的草稿", "expected_draft_version": 1},
        headers=headers,
    )
    assert revised.status_code == 200
    revised_data = revised.json()["data"]
    assert revised_data["draft_version"] == 2
    assert revised_data["title"] == "改后的草稿"
    assert revised_data["operation_id"] != draft["operation_id"]

    stale = await client.patch(
        f"/api/v1/me/drafts/{draft['draft_id']}",
        json={"title": "再次", "expected_draft_version": 1},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"


async def test_save_draft_button_path(client, seeded, make_draft):
    draft = await make_draft()
    headers = seeded["student_headers"]

    response = await client.post(
        f"/api/v1/me/drafts/{draft['draft_id']}/save",
        json={"draft_version": 1},
        headers={**headers, "Idempotency-Key": draft["operation_id"]},
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["status"] == "created"
    assert data["operation_id"] == draft["operation_id"]
    plan_id = data["plan_id"]

    plan = await client.get(f"/api/v1/me/plans/{plan_id}", headers=headers)
    assert plan.status_code == 200
    assert plan.json()["data"]["source"] == "assistant"

    # 重复保存同键 → 200 existing，不新建
    again = await client.post(
        f"/api/v1/me/drafts/{draft['draft_id']}/save",
        json={"draft_version": 1},
        headers={**headers, "Idempotency-Key": draft["operation_id"]},
    )
    assert again.status_code == 200
    assert again.json()["data"]["status"] == "existing"
    assert again.json()["data"]["plan_id"] == plan_id

    listing = await client.get("/api/v1/me/plans", headers=headers)
    assert listing.json()["data"]["total"] == 1

    operation = await client.get(
        f"/api/v1/me/write-operations/{draft['operation_id']}", headers=headers
    )
    assert operation.json()["data"]["state"] == "succeeded"
    assert operation.json()["data"]["plan_id"] == plan_id


async def test_save_requires_matching_key_and_current_version(
    client, seeded, make_draft
):
    draft = await make_draft()
    headers = seeded["student_headers"]

    wrong_key = await client.post(
        f"/api/v1/me/drafts/{draft['draft_id']}/save",
        json={"draft_version": 1},
        headers={**headers, "Idempotency-Key": "op-not-the-bound-one"},
    )
    assert wrong_key.status_code == 422
    assert wrong_key.json()["error"]["code"] == "SAVE_NOT_AUTHORIZED"

    # 旧版本首次保存：先改出新版本
    revised = await client.patch(
        f"/api/v1/me/drafts/{draft['draft_id']}",
        json={"content": "新正文", "expected_draft_version": 1},
        headers=headers,
    )
    assert revised.status_code == 200
    old_version = await client.post(
        f"/api/v1/me/drafts/{draft['draft_id']}/save",
        json={"draft_version": 1},
        headers={**headers, "Idempotency-Key": draft["operation_id"]},
    )
    assert old_version.status_code == 422
    assert old_version.json()["error"]["code"] == "SAVE_NOT_AUTHORIZED"

    # 新版本可用其预分配 operation_id 保存
    new_op = revised.json()["data"]["operation_id"]
    saved = await client.post(
        f"/api/v1/me/drafts/{draft['draft_id']}/save",
        json={"draft_version": 2},
        headers={**headers, "Idempotency-Key": new_op},
    )
    assert saved.status_code == 201, saved.text


async def test_draft_expired_and_isolation(client, seeded, make_draft):
    expired = await make_draft(expires_in_seconds=-10)
    headers = seeded["student_headers"]
    response = await client.get(
        f"/api/v1/me/drafts/{expired['draft_id']}", headers=headers
    )
    assert response.status_code == 410
    assert response.json()["error"]["code"] == "DRAFT_EXPIRED"

    save_expired = await client.post(
        f"/api/v1/me/drafts/{expired['draft_id']}/save",
        json={"draft_version": 1},
        headers={**headers, "Idempotency-Key": expired["operation_id"]},
    )
    assert save_expired.status_code == 410

    draft = await make_draft()
    other_get = await client.get(
        f"/api/v1/me/drafts/{draft['draft_id']}", headers=seeded["other_headers"]
    )
    assert other_get.status_code == 404

    other_save = await client.post(
        f"/api/v1/me/drafts/{draft['draft_id']}/save",
        json={"draft_version": 1},
        headers={
            **seeded["other_headers"],
            "Idempotency-Key": draft["operation_id"],
        },
    )
    assert other_save.status_code == 404


async def test_save_concurrent_same_key_creates_one_plan(client, seeded, make_draft):
    """真 MySQL 并发：同键同内容 10 次并发只产生 1 份计划。"""
    draft = await make_draft()
    headers = {**seeded["student_headers"], "Idempotency-Key": draft["operation_id"]}

    async def save_once():
        return await client.post(
            f"/api/v1/me/drafts/{draft['draft_id']}/save",
            json={"draft_version": 1},
            headers=headers,
        )

    responses = await asyncio.gather(*[save_once() for _ in range(10)])
    codes = [response.status_code for response in responses]
    assert set(codes) <= {200, 201}, codes
    assert codes.count(201) == 1, codes

    plan_ids = {response.json()["data"]["plan_id"] for response in responses}
    assert len(plan_ids) == 1

    listing = await client.get("/api/v1/me/plans", headers=seeded["student_headers"])
    assert listing.json()["data"]["total"] == 1
