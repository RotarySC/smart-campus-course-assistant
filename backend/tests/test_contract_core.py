"""契约测试：Phase 1 的 23 个公共端点逐项断言字段名/状态码/错误码（OpenAPI 为权威）。

不引入完整 JSON Schema 校验器，聚焦「字段名集合 + 状态码 + 错误码 + 信封形状」；
额外覆盖严格对象、PATCH 缺失 vs null、分页边界、31 天跨度、501 桩与错误码表。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.shared.errors import ERROR_STATUS

REQUEST_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
OP_PATTERN = r"^[A-Za-z0-9._:-]{1,96}$"

USER_KEYS = {"id", "account", "display_name", "role", "enabled", "version"}
PAGE_KEYS = {"items", "page", "page_size", "total"}
SCHEDULE_KEYS = {
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
PLAN_KEYS = {
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
DRAFT_KEYS = {
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


def assert_envelope(response, expected_status: int) -> dict:
    assert response.status_code == expected_status, response.text
    body = response.json()
    assert set(body) == {"request_id", "data"}, body
    import re

    assert re.match(REQUEST_ID_PATTERN, body["request_id"]), body["request_id"]
    return body["data"]


def assert_error(response, expected_status: int, expected_code: str) -> dict:
    assert response.status_code == expected_status, response.text
    body = response.json()
    assert set(body) == {"request_id", "error"}, body
    error = body["error"]
    assert set(error) <= {"code", "message", "field_errors", "details"}, error
    assert {"code", "message"} <= set(error)
    assert error["code"] == expected_code
    assert 1 <= len(error["message"]) <= 500
    if "field_errors" in error:
        for item in error["field_errors"]:
            assert set(item) == {"field", "reason"}
            assert 1 <= len(item["field"]) <= 100
            assert 1 <= len(item["reason"]) <= 500
    return body


async def test_all_23_endpoints_contract(client, seeded, make_draft):
    """按 OpenAPI 顺序覆盖 23 个端点，断言状态码与响应 data 字段名集合。"""
    admin = seeded["admin_headers"]
    student = seeded["student_headers"]
    student_id = seeded["student"]["id"]

    # 1) POST /auth/login
    data = assert_envelope(
        await client.post(
            "/api/v1/auth/login",
            json={"account": "student_seed", "password": "demo1234"},
        ),
        200,
    )
    assert set(data) == {"access_token", "token_type", "expires_at", "user"}
    assert set(data["user"]) == USER_KEYS
    token = data["access_token"]
    fresh_headers = {"Authorization": f"Bearer {token}"}

    # 2) POST /auth/logout（用独立会话，避免影响后续）
    logout = assert_envelope(
        await client.post("/api/v1/auth/logout", headers=fresh_headers), 200
    )
    assert set(logout) == {"revoked"} and logout["revoked"] is True

    # 3) GET /me
    me = assert_envelope(await client.get("/api/v1/me", headers=student), 200)
    assert set(me) == {"user", "session_expires_at", "school_timezone", "capabilities"}
    assert set(me["user"]) == USER_KEYS

    # 4) GET /admin/students
    students = assert_envelope(
        await client.get("/api/v1/admin/students", headers=admin), 200
    )
    assert set(students) == PAGE_KEYS
    assert set(students["items"][0]) == USER_KEYS

    # 5) POST /admin/students
    created_student = assert_envelope(
        await client.post(
            "/api/v1/admin/students",
            json={
                "account": "contract_student",
                "display_name": "契约学生",
                "initial_password": "password123",
            },
            headers=admin,
        ),
        201,
    )
    assert set(created_student) == USER_KEYS
    target_student_id = created_student["id"]

    # 6) PATCH /admin/students/{id}
    patched_student = assert_envelope(
        await client.patch(
            f"/api/v1/admin/students/{target_student_id}",
            json={"display_name": "契约学生改", "expected_version": 1},
            headers=admin,
        ),
        200,
    )
    assert set(patched_student) == USER_KEYS
    assert patched_student["version"] == 2

    # 7) GET /admin/courses
    courses = assert_envelope(await client.get("/api/v1/admin/courses", headers=admin), 200)
    assert set(courses) == PAGE_KEYS
    course = courses["items"][0]
    assert set(course) == {"id", "code", "name", "description", "enabled", "version"}

    # 8) POST /admin/courses
    new_course = assert_envelope(
        await client.post(
            "/api/v1/admin/courses",
            json={"code": "PH101", "name": "物理"},
            headers=admin,
        ),
        201,
    )
    assert set(new_course) == {"id", "code", "name", "description", "enabled", "version"}

    # 9) PATCH /admin/courses/{id}
    patched_course = assert_envelope(
        await client.patch(
            f"/api/v1/admin/courses/{new_course['id']}",
            json={"description": "力学", "expected_version": 1},
            headers=admin,
        ),
        200,
    )
    assert set(patched_course) == {"id", "code", "name", "description", "enabled", "version"}

    # 10) GET /me/schedules
    my_schedules = assert_envelope(
        await client.get("/api/v1/me/schedules?from_date=2026-11-02&to_date=2026-11-02", headers=student),
        200,
    )
    assert set(my_schedules) == PAGE_KEYS | {"from_date", "to_date", "school_timezone"}

    # 11) GET /admin/schedules
    admin_schedules = assert_envelope(
        await client.get(
            f"/api/v1/admin/schedules?student_id={student_id}&from_date=2026-11-02&to_date=2026-11-02",
            headers=admin,
        ),
        200,
    )
    assert set(admin_schedules) == PAGE_KEYS | {
        "from_date",
        "to_date",
        "school_timezone",
    }

    # 12) POST /admin/schedules
    schedule = assert_envelope(
        await client.post(
            "/api/v1/admin/schedules",
            json={
                "student_id": student_id,
                "course_id": course["id"],
                "class_date": "2026-11-02",
                "start_time": "08:00",
                "end_time": "09:40",
                "location": "A-201",
            },
            headers=admin,
        ),
        201,
    )
    assert set(schedule) == SCHEDULE_KEYS
    schedule_id = schedule["id"]

    # 13) PATCH /admin/schedules/{id}
    patched_schedule = assert_envelope(
        await client.patch(
            f"/api/v1/admin/schedules/{schedule_id}",
            json={"location": "B-302", "expected_version": 1},
            headers=admin,
        ),
        200,
    )
    assert set(patched_schedule) == SCHEDULE_KEYS
    assert patched_schedule["version"] == 2

    # 14) DELETE /admin/schedules/{id}
    deleted_schedule = assert_envelope(
        await client.delete(
            f"/api/v1/admin/schedules/{schedule_id}?expected_version=2", headers=admin
        ),
        200,
    )
    assert set(deleted_schedule) == {"deleted", "schedule_id", "audit_id"}

    # 15) GET /me/plans
    plans = assert_envelope(await client.get("/api/v1/me/plans", headers=student), 200)
    assert set(plans) == PAGE_KEYS

    # 16) POST /me/plans
    plan = assert_envelope(
        await client.post(
            "/api/v1/me/plans",
            json={"title": "契约计划", "content": "正文"},
            headers={**student, "Idempotency-Key": "op-contract-0001"},
        ),
        201,
    )
    assert set(plan) == {"status", "operation_id", "plan_id"}
    plan_id = plan["plan_id"]

    # 17) GET /me/plans/{id}
    plan_detail = assert_envelope(
        await client.get(f"/api/v1/me/plans/{plan_id}", headers=student), 200
    )
    assert set(plan_detail) == PLAN_KEYS
    assert plan_detail["source"] == "manual"

    # 18) PATCH /me/plans/{id}
    patched_plan = assert_envelope(
        await client.patch(
            f"/api/v1/me/plans/{plan_id}",
            json={"goal": "新目标", "expected_version": 1},
            headers=student,
        ),
        200,
    )
    assert set(patched_plan) == PLAN_KEYS
    assert patched_plan["version"] == 2

    # 19) DELETE /me/plans/{id}
    deleted_plan = assert_envelope(
        await client.delete(
            f"/api/v1/me/plans/{plan_id}?expected_version=2", headers=student
        ),
        200,
    )
    assert set(deleted_plan) == {"deleted", "plan_id", "version"}

    # 20) GET /me/drafts/{draft_id}
    draft = await make_draft()
    draft_detail = assert_envelope(
        await client.get(f"/api/v1/me/drafts/{draft['draft_id']}", headers=student), 200
    )
    assert set(draft_detail) == DRAFT_KEYS

    # 21) PATCH /me/drafts/{draft_id}
    revised = assert_envelope(
        await client.patch(
            f"/api/v1/me/drafts/{draft['draft_id']}",
            json={"title": "契约草稿", "expected_draft_version": 1},
            headers=student,
        ),
        200,
    )
    assert set(revised) == DRAFT_KEYS
    assert revised["draft_version"] == 2

    # 22) POST /me/drafts/{draft_id}/save（用新版本预分配 operation_id）
    saved = assert_envelope(
        await client.post(
            f"/api/v1/me/drafts/{draft['draft_id']}/save",
            json={"draft_version": 2},
            headers={**student, "Idempotency-Key": revised["operation_id"]},
        ),
        201,
    )
    assert set(saved) == {"status", "operation_id", "plan_id"}

    # 23) GET /me/write-operations/{operation_id}
    operation = assert_envelope(
        await client.get(
            f"/api/v1/me/write-operations/{revised['operation_id']}", headers=student
        ),
        200,
    )
    assert set(operation) <= {
        "operation_id",
        "state",
        "resolution",
        "plan_id",
        "error_code",
        "retryable",
    }
    assert operation["state"] == "succeeded"


async def test_extra_fields_rejected_on_json_bodies(client, seeded):
    cases = [
        ("/api/v1/auth/login", {"account": "student_seed", "password": "demo1234", "x": 1}),
        (
            "/api/v1/admin/students",
            {
                "account": "extra_user",
                "display_name": "x",
                "initial_password": "password123",
                "role": "admin",
            },
        ),
        ("/api/v1/admin/courses", {"code": "EX1", "name": "x", "user_id": "usr_x"}),
        (
            "/api/v1/admin/schedules",
            {
                "student_id": "usr_x",
                "course_id": "crs_x",
                "class_date": "2026-11-02",
                "start_time": "08:00",
                "end_time": "09:00",
                "save_grant": "x",
            },
        ),
        ("/api/v1/me/plans", {"title": "x", "content": "y", "source": "assistant"}),
    ]
    for path, body in cases:
        headers = seeded["student_headers"]
        if path.startswith("/api/v1/admin"):
            headers = seeded["admin_headers"]
        if path == "/api/v1/me/plans":
            headers = {**headers, "Idempotency-Key": "op-extra-0001"}
        response = await client.post(path, json=body, headers=headers)
        assert_error(response, 422, "VALIDATION_FAILED")
        fields = {item["field"] for item in response.json()["error"]["field_errors"]}
        assert fields & {"x", "role", "user_id", "save_grant", "source"}, (path, fields)


async def test_patch_missing_vs_null_semantics(client, seeded):
    student = seeded["student_headers"]
    plan = assert_envelope(
        await client.post(
            "/api/v1/me/plans",
            json={
                "title": "PATCH 语义",
                "goal": "初始目标",
                "content": "正文",
            },
            headers={**student, "Idempotency-Key": "op-patch-null-0001"},
        ),
        201,
    )
    plan_id = plan["plan_id"]

    # 缺失字段 = 不改
    missing = assert_envelope(
        await client.patch(
            f"/api/v1/me/plans/{plan_id}",
            json={"title": "只改标题", "expected_version": 1},
            headers=student,
        ),
        200,
    )
    assert missing["goal"] == "初始目标"
    assert missing["title"] == "只改标题"

    # 显式 null = 清空可空字段
    cleared = assert_envelope(
        await client.patch(
            f"/api/v1/me/plans/{plan_id}",
            json={"goal": None, "expected_version": 2},
            headers=student,
        ),
        200,
    )
    assert cleared["goal"] is None

    # 不可空字段显式 null → 422
    response = await client.patch(
        f"/api/v1/me/plans/{plan_id}",
        json={"title": None, "expected_version": 3},
        headers=student,
    )
    assert_error(response, 422, "VALIDATION_FAILED")


async def test_pagination_boundaries(client, seeded):
    student = seeded["student_headers"]
    for query in ("page=0", "page_size=0", "page_size=101", "page=abc"):
        response = await client.get(f"/api/v1/me/plans?{query}", headers=student)
        assert_error(response, 422, "VALIDATION_FAILED")

    response = await client.get("/api/v1/me/plans?page=2&page_size=1", headers=student)
    data = assert_envelope(response, 200)
    assert data["page"] == 2
    assert data["page_size"] == 1


async def test_schedule_range_limit(client, seeded):
    student = seeded["student_headers"]
    start = date(2026, 11, 1)
    ok_end = start + timedelta(days=31)
    too_far = start + timedelta(days=32)

    response = await client.get(
        f"/api/v1/me/schedules?from_date={start}&to_date={ok_end}", headers=student
    )
    assert response.status_code == 200
    response = await client.get(
        f"/api/v1/me/schedules?from_date={start}&to_date={too_far}", headers=student
    )
    assert_error(response, 422, "VALIDATION_FAILED")


async def test_error_codes_for_phase1(client, seeded):
    admin = seeded["admin_headers"]
    student = seeded["student_headers"]

    # 401
    assert_error(await client.get("/api/v1/me"), 401, "AUTH_REQUIRED")
    # 403
    assert_error(await client.get("/api/v1/admin/students", headers=student), 403, "FORBIDDEN")
    # 404 未知路径
    assert_error(await client.get("/api/v1/unknown-path"), 404, "RESOURCE_NOT_FOUND")
    # 404 跨用户
    assert_error(
        await client.get("/api/v1/me/plans/plan_missing", headers=student),
        404,
        "RESOURCE_NOT_FOUND",
    )
    # 409 各冲突码
    duplicate_course = await client.post(
        "/api/v1/admin/courses", json={"code": "CS101", "name": "重复"}, headers=admin
    )
    assert_error(duplicate_course, 409, "DUPLICATE_COURSE")
    duplicate_student = await client.post(
        "/api/v1/admin/students",
        json={"account": "student_seed", "display_name": "重复", "initial_password": "password123"},
        headers=admin,
    )
    assert_error(duplicate_student, 409, "DUPLICATE_ACCOUNT")
    # 410 草稿过期由 planning 测试覆盖，这里断言错误码表映射
    assert ERROR_STATUS["DRAFT_EXPIRED"] == 410
    assert ERROR_STATUS["SCHEDULE_OVERLAP"] == 409
    assert ERROR_STATUS["SAVE_NOT_AUTHORIZED"] == 422
    assert ERROR_STATUS["CAPACITY_LIMITED"] == 429
    assert ERROR_STATUS["STORAGE_UNAVAILABLE"] == 503
    assert ERROR_STATUS["EXECUTION_TIMEOUT"] == 504
    assert ERROR_STATUS["INTERNAL_ERROR"] == 500


async def test_error_body_never_leaks_sql(client, seeded):
    admin = seeded["admin_headers"]
    response = await client.post(
        "/api/v1/admin/courses", json={"code": "CS101", "name": "重复"}, headers=admin
    )
    text = response.text
    for forbidden in ("Duplicate entry", "pymysql", "INSERT", "SELECT", "uq_courses_code", "Traceback"):
        assert forbidden not in text


async def test_unimplemented_endpoints_return_501_envelope(client, seeded):
    student = seeded["student_headers"]
    cases = [
        ("post", "/api/v1/admin/document-batches", {}),
        ("get", "/api/v1/admin/document-batches/bat_x", None),
        ("get", "/api/v1/admin/documents", None),
        ("get", "/api/v1/admin/documents/doc_x/text", None),
        ("post", "/api/v1/admin/documents/doc_x/rebuild", {}),
        ("delete", "/api/v1/admin/documents/doc_x", None),
        ("post", "/api/v1/admin/documents/doc_x/cleanup-retry", {}),
        ("get", "/api/v1/citations/cit_x", None),
        ("post", "/api/v1/chat/stream", {}),
        ("get", "/api/v1/chat/requests/req_x", None),
        ("post", "/api/v1/chat/requests/req_x/cancel", {}),
    ]
    for method, path, body in cases:
        response = await getattr(client, method)(
            path, headers=student, **({"json": body} if body is not None else {})
        )
        assert response.status_code == 501, (method, path, response.text)
        payload = response.json()
        assert set(payload) == {"request_id", "error"}
        assert payload["error"]["code"] == "INTERNAL_ERROR"
        assert "尚未实现" in payload["error"]["message"]


async def test_runtime_openapi_exposes_contract(client):
    response = await client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["openapi"].startswith("3.1")
    paths = spec["paths"]
    for path in [
        "/api/v1/auth/login",
        "/api/v1/me/plans",
        "/api/v1/me/drafts/{draft_id}/save",
        "/api/v1/chat/stream",
        "/api/v1/admin/documents",
    ]:
        assert path in paths, path
    assert "User" in spec["components"]["schemas"]
