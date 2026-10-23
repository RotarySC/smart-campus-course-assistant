"""课程与课表定向测试（真实 MySQL，含并发重叠用例）。"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest


async def _create_schedule(
    client,
    headers,
    *,
    student_id: str,
    course_id: str,
    class_date: str = "2026-11-02",
    start_time: str = "08:00",
    end_time: str = "09:40",
    location: str | None = "A-201",
    **extra,
):
    body = {
        "student_id": student_id,
        "course_id": course_id,
        "class_date": class_date,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
    }
    body.update(extra)
    return await client.post("/api/v1/admin/schedules", json=body, headers=headers)


# --------------------------------------------------------------------------- #
# 课程
# --------------------------------------------------------------------------- #
async def test_course_crud_and_rules(client, seeded):
    headers = seeded["admin_headers"]
    response = await client.get("/api/v1/admin/courses", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    course = data["items"][0]
    assert set(course) == {"id", "code", "name", "description", "enabled", "version"}

    duplicate = await client.post(
        "/api/v1/admin/courses",
        json={"code": " cs101 ", "name": "重复课程"},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_COURSE"

    patched = await client.patch(
        f"/api/v1/admin/courses/{course['id']}",
        json={"name": "数据结构（改）", "expected_version": 1},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["version"] == 2
    assert patched.json()["data"]["code"] == "CS101"  # code 不可改

    stale = await client.patch(
        f"/api/v1/admin/courses/{course['id']}",
        json={"name": "x", "expected_version": 1},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"

    # code 不可通过 PATCH 修改（额外字段 422）
    extra = await client.patch(
        f"/api/v1/admin/courses/{course['id']}",
        json={"code": "NEW", "expected_version": 2},
        headers=headers,
    )
    assert extra.status_code == 422


async def test_disabled_course_cannot_be_used(client, seeded):
    headers = seeded["admin_headers"]
    course = seeded["course"]
    response = await client.patch(
        f"/api/v1/admin/courses/{course['id']}",
        json={"enabled": False, "expected_version": 1},
        headers=headers,
    )
    assert response.status_code == 200

    created = await _create_schedule(
        client,
        headers,
        student_id=seeded["student"]["id"],
        course_id=course["id"],
    )
    assert created.status_code == 422
    assert created.json()["error"]["code"] == "VALIDATION_FAILED"


# --------------------------------------------------------------------------- #
# 课表查询
# --------------------------------------------------------------------------- #
async def test_my_schedules_date_rules(client, seeded):
    headers = seeded["student_headers"]
    # 无参数 = 今天（Asia/Shanghai）
    response = await client.get("/api/v1/me/schedules", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {
        "items",
        "page",
        "page_size",
        "total",
        "from_date",
        "to_date",
        "school_timezone",
    }
    assert data["from_date"] == data["to_date"]
    assert data["school_timezone"] == "Asia/Shanghai"
    assert data["items"] == []

    # 只传一端 = 单日
    response = await client.get(
        "/api/v1/me/schedules?from_date=2026-11-02", headers=headers
    )
    assert response.json()["data"]["to_date"] == "2026-11-02"

    # 起止倒置 422
    response = await client.get(
        "/api/v1/me/schedules?from_date=2026-11-03&to_date=2026-11-02",
        headers=headers,
    )
    assert response.status_code == 422

    # 跨度超 31 天 422
    response = await client.get(
        "/api/v1/me/schedules?from_date=2026-11-01&to_date=2026-12-10",
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"

    # 31 天内 200
    response = await client.get(
        "/api/v1/me/schedules?from_date=2026-11-01&to_date=2026-12-01",
        headers=headers,
    )
    assert response.status_code == 200


async def test_admin_schedules_requires_student(client, seeded):
    headers = seeded["admin_headers"]
    response = await client.get(
        "/api/v1/admin/schedules?student_id=usr_missing", headers=headers
    )
    assert response.status_code == 404

    response = await client.get(
        f"/api/v1/admin/schedules?student_id={seeded['student']['id']}", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["items"] == []


# --------------------------------------------------------------------------- #
# 课表写入
# --------------------------------------------------------------------------- #
async def test_create_list_patch_delete_schedule(client, seeded):
    headers = seeded["admin_headers"]
    student_id = seeded["student"]["id"]
    course_id = seeded["course"]["id"]

    created = await _create_schedule(
        client, headers, student_id=student_id, course_id=course_id
    )
    assert created.status_code == 201, created.text
    schedule = created.json()["data"]
    assert set(schedule) == {
        "id",
        "student_id",
        "course_id",
        "course_name",
        "class_date",
        "start_time",
        "end_time",
        "location",
        "version",
    }
    assert schedule["class_date"] == "2026-11-02"
    assert schedule["start_time"] == "08:00"
    assert schedule["version"] == 1

    # 学生本人可见
    mine = await client.get(
        "/api/v1/me/schedules?from_date=2026-11-02&to_date=2026-11-02",
        headers=seeded["student_headers"],
    )
    assert mine.json()["data"]["total"] == 1
    assert mine.json()["data"]["items"][0]["id"] == schedule["id"]

    # 精确重复 → DUPLICATE_SCHEDULE（即使带确认原因）
    duplicate = await _create_schedule(
        client,
        headers,
        student_id=student_id,
        course_id=course_id,
        overlap_acknowledged=True,
        reason="确认重复",
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_SCHEDULE"

    # 重叠未确认 → 409 SCHEDULE_OVERLAP + details.overlaps
    overlap = await _create_schedule(
        client,
        headers,
        student_id=student_id,
        course_id=course_id,
        start_time="09:00",
        end_time="10:00",
    )
    assert overlap.status_code == 409
    error = overlap.json()["error"]
    assert error["code"] == "SCHEDULE_OVERLAP"
    assert error["details"]["overlaps"][0]["id"] == schedule["id"]

    # 确认但无原因 → 422
    no_reason = await _create_schedule(
        client,
        headers,
        student_id=student_id,
        course_id=course_id,
        start_time="09:00",
        end_time="10:00",
        overlap_acknowledged=True,
    )
    assert no_reason.status_code == 422

    # 确认 + 原因 → 201
    acknowledged = await _create_schedule(
        client,
        headers,
        student_id=student_id,
        course_id=course_id,
        start_time="09:00",
        end_time="10:00",
        overlap_acknowledged=True,
        reason="调课，允许重叠",
    )
    assert acknowledged.status_code == 201, acknowledged.text

    # 首尾相接不算重叠（半开区间）
    adjacent = await _create_schedule(
        client,
        headers,
        student_id=student_id,
        course_id=course_id,
        start_time="10:00",
        end_time="11:00",
    )
    assert adjacent.status_code == 201, adjacent.text

    # 更新：不能改归属学生（字段不存在 → 422）
    changed = await client.patch(
        f"/api/v1/admin/schedules/{schedule['id']}",
        json={"location": "B-302", "expected_version": 1},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["data"]["location"] == "B-302"
    assert changed.json()["data"]["version"] == 2

    change_owner = await client.patch(
        f"/api/v1/admin/schedules/{schedule['id']}",
        json={"student_id": seeded["other"]["id"], "expected_version": 2},
        headers=headers,
    )
    assert change_owner.status_code == 422

    stale = await client.patch(
        f"/api/v1/admin/schedules/{schedule['id']}",
        json={"location": "C-1", "expected_version": 1},
        headers=headers,
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"

    deleted = await client.delete(
        f"/api/v1/admin/schedules/{schedule['id']}?expected_version=2", headers=headers
    )
    assert deleted.status_code == 200
    assert set(deleted.json()["data"]) == {"deleted", "schedule_id", "audit_id"}

    after = await client.get(
        "/api/v1/me/schedules?from_date=2026-11-02&to_date=2026-11-02",
        headers=seeded["student_headers"],
    )
    ids = {item["id"] for item in after.json()["data"]["items"]}
    assert schedule["id"] not in ids

    missing = await client.delete(
        f"/api/v1/admin/schedules/{schedule['id']}?expected_version=3", headers=headers
    )
    assert missing.status_code == 404


async def test_schedule_time_validation(client, seeded):
    headers = seeded["admin_headers"]
    for start, end in [("10:00", "10:00"), ("11:00", "10:00")]:
        response = await _create_schedule(
            client,
            headers,
            student_id=seeded["student"]["id"],
            course_id=seeded["course"]["id"],
            start_time=start,
            end_time=end,
        )
        assert response.status_code == 422, (start, end)

    # 非分钟精度 / 非 HH:mm
    response = await _create_schedule(
        client,
        headers,
        student_id=seeded["student"]["id"],
        course_id=seeded["course"]["id"],
        start_time="8:00",
    )
    assert response.status_code == 422


async def test_disabled_student_cannot_get_schedule(client, seeded):
    headers = seeded["admin_headers"]
    target = seeded["other"]
    await client.patch(
        f"/api/v1/admin/students/{target['id']}",
        json={"enabled": False, "expected_version": 1},
        headers=headers,
    )
    response = await _create_schedule(
        client,
        headers,
        student_id=target["id"],
        course_id=seeded["course"]["id"],
    )
    assert response.status_code == 404


async def test_concurrent_overlap_only_acknowledged_succeeds(client, seeded):
    """预置一条重叠基准；并发提交“确认/未确认”两条重叠课表，只有确认者成功。"""
    headers = seeded["admin_headers"]
    student_id = seeded["student"]["id"]
    course_id = seeded["course"]["id"]

    base = await _create_schedule(
        client,
        headers,
        student_id=student_id,
        course_id=course_id,
        start_time="08:00",
        end_time="10:00",
    )
    assert base.status_code == 201

    async def create_ack():
        return await _create_schedule(
            client,
            headers,
            student_id=student_id,
            course_id=course_id,
            start_time="09:00",
            end_time="11:00",
            overlap_acknowledged=True,
            reason="并发确认重叠",
        )

    async def create_unack():
        return await _create_schedule(
            client,
            headers,
            student_id=student_id,
            course_id=course_id,
            start_time="09:30",
            end_time="11:30",
        )

    ack_resp, unack_resp = await asyncio.gather(create_ack(), create_unack())
    statuses = sorted([ack_resp.status_code, unack_resp.status_code])
    assert statuses == [201, 409], (ack_resp.text, unack_resp.text)
    conflict = unack_resp if unack_resp.status_code == 409 else ack_resp
    assert conflict.json()["error"]["code"] == "SCHEDULE_OVERLAP"

    listing = await client.get(
        "/api/v1/me/schedules?from_date=2026-11-02&to_date=2026-11-02",
        headers=seeded["student_headers"],
    )
    assert listing.json()["data"]["total"] == 2  # 基准 + 确认者
