"""身份与认证定向测试（真实 MySQL + 真实 HTTP 应用）。"""

from __future__ import annotations

import pytest


async def test_login_success_shape(client, seeded):
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": "student_seed", "password": "demo1234"},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"request_id", "data"}
    data = body["data"]
    assert set(data) == {"access_token", "token_type", "expires_at", "user"}
    assert data["token_type"] == "Bearer"
    assert data["access_token"] not in response.text.replace('"access_token":', "")[:0]
    assert set(data["user"]) == {
        "id",
        "account",
        "display_name",
        "role",
        "enabled",
        "version",
    }
    assert data["user"]["role"] == "student"
    assert "password" not in response.text.lower()
    assert "argon2" not in response.text


async def test_login_wrong_password_unified(client, seeded):
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": "student_seed", "password": "wrong-pass"},
    )
    assert response.status_code == 401
    error = response.json()["error"]
    assert error["code"] == "AUTH_REQUIRED"
    assert error["message"] == "账号或密码不正确"


async def test_login_unknown_account_same_message(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": "nobody_here", "password": "whatever"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "账号或密码不正确"


async def test_login_disabled_account_unified(client, seeded):
    from tests.conftest import create_user_row

    await create_user_row(account="disabled_user", enabled=False)
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": "disabled_user", "password": "demo1234"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "账号或密码不正确"


async def test_login_extra_field_rejected(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": "student_seed", "password": "demo1234", "role": "admin"},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_FAILED"
    assert any(item["field"] == "role" for item in error["field_errors"])


async def test_auth_required_and_bad_token(client):
    response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"

    response = await client.get(
        "/api/v1/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


async def test_me_shape(client, seeded):
    response = await client.get("/api/v1/me", headers=seeded["student_headers"])
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {
        "user",
        "session_expires_at",
        "school_timezone",
        "capabilities",
    }
    assert data["school_timezone"] == "Asia/Shanghai"
    assert data["capabilities"] == ["chat", "plans", "schedules"]
    assert data["session_expires_at"].endswith("Z")


async def test_logout_revokes_session(client, seeded):
    headers = seeded["student_headers"]
    response = await client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == {"revoked": True}

    response = await client.get("/api/v1/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"


async def test_student_cannot_use_admin_endpoints(client, seeded):
    for method, path in [
        ("get", "/api/v1/admin/students"),
        ("post", "/api/v1/admin/students"),
        ("get", "/api/v1/admin/courses"),
        ("get", "/api/v1/admin/schedules?student_id=x"),
    ]:
        response = await getattr(client, method)(
            path, headers=seeded["student_headers"]
        )
        assert response.status_code == 403, (method, path, response.text)
        assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_list_students(client, seeded):
    response = await client.get(
        "/api/v1/admin/students", headers=seeded["admin_headers"]
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {"items", "page", "page_size", "total"}
    assert data["page"] == 1 and data["page_size"] == 20
    accounts = {item["account"] for item in data["items"]}
    assert {"student_seed", "student_other"} <= accounts
    assert "admin_seed" not in accounts
    assert data["total"] == 2

    response = await client.get(
        "/api/v1/admin/students?enabled=false", headers=seeded["admin_headers"]
    )
    assert response.status_code == 200
    assert response.json()["data"]["items"] == []

    response = await client.get(
        "/api/v1/admin/students?enabled=1", headers=seeded["admin_headers"]
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_admin_create_student(client, seeded):
    response = await client.post(
        "/api/v1/admin/students",
        json={
            "account": "new_student",
            "display_name": "新学生",
            "initial_password": "password123",
        },
        headers=seeded["admin_headers"],
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["role"] == "student"
    assert data["enabled"] is True
    assert data["version"] == 1
    assert data["account"] == "new_student"

    # 规范值唯一（大小写不敏感）
    duplicate = await client.post(
        "/api/v1/admin/students",
        json={
            "account": "NEW_STUDENT",
            "display_name": "重复",
            "initial_password": "password123",
        },
        headers=seeded["admin_headers"],
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_ACCOUNT"

    weak = await client.post(
        "/api/v1/admin/students",
        json={"account": "weak_pass", "display_name": "弱口令", "initial_password": "123"},
        headers=seeded["admin_headers"],
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_admin_patch_student(client, seeded):
    target = seeded["other"]
    response = await client.patch(
        f"/api/v1/admin/students/{target['id']}",
        json={"display_name": "改名后", "expected_version": 1},
        headers=seeded["admin_headers"],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["display_name"] == "改名后"
    assert data["version"] == 2

    stale = await client.patch(
        f"/api/v1/admin/students/{target['id']}",
        json={"display_name": "再次", "expected_version": 1},
        headers=seeded["admin_headers"],
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"

    missing = await client.patch(
        "/api/v1/admin/students/usr_missing",
        json={"display_name": "x", "expected_version": 1},
        headers=seeded["admin_headers"],
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_disable_student_revokes_all_sessions(client, seeded):
    target = seeded["other"]
    response = await client.patch(
        f"/api/v1/admin/students/{target['id']}",
        json={"enabled": False, "expected_version": 1},
        headers=seeded["admin_headers"],
    )
    assert response.status_code == 200
    assert response.json()["data"]["enabled"] is False

    # 既有会话立即失效（auth_version 递增 + 会话撤销）
    me = await client.get("/api/v1/me", headers=seeded["other_headers"])
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "SESSION_EXPIRED"

    login = await client.post(
        "/api/v1/auth/login",
        json={"account": target["account"], "password": target["password"]},
    )
    assert login.status_code == 401


async def test_patch_student_requires_at_least_one_field(client, seeded):
    target = seeded["other"]
    response = await client.patch(
        f"/api/v1/admin/students/{target['id']}",
        json={"expected_version": 1},
        headers=seeded["admin_headers"],
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"

    # 显式 null 不允许（OpenAPI 字段非 nullable）
    response = await client.patch(
        f"/api/v1/admin/students/{target['id']}",
        json={"display_name": None, "expected_version": 1},
        headers=seeded["admin_headers"],
    )
    assert response.status_code == 422


# ===================== 自助注册（桌面自适应追加包 §15.4） =====================


async def test_register_creates_student_and_logs_in(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"account": "new_student", "display_name": "新同学", "password": "demo1234"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert set(data) == {"access_token", "token_type", "expires_at", "user"}
    assert data["user"]["role"] == "student"
    assert data["user"]["enabled"] is True
    assert data["user"]["account"] == "new_student"

    # 注册即自动登录：同一令牌可直接访问 /me
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me = await client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["user"]["account"] == "new_student"
    assert "admin" not in me.json()["data"]["capabilities"]

    # 退出后可用刚注册的账号再次登录
    assert (
        await client.post("/api/v1/auth/logout", headers=headers)
    ).status_code == 200
    again = await client.post(
        "/api/v1/auth/login",
        json={"account": "new_student", "password": "demo1234"},
    )
    assert again.status_code == 200


async def test_register_duplicate_account_conflicts(client):
    payload = {"account": "dup_student", "display_name": "重复同学", "password": "demo1234"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_ACCOUNT"


async def test_register_duplicate_is_case_and_space_insensitive(client):
    assert (
        await client.post(
            "/api/v1/auth/register",
            json={"account": "CaseUser", "display_name": "大小写", "password": "demo1234"},
        )
    ).status_code == 201
    # 账号规范化按 casefold：大小写不同、首尾带空白都算同一个账号
    response = await client.post(
        "/api/v1/auth/register",
        json={"account": "  caseuser  ", "display_name": "大小写二", "password": "demo1234"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_ACCOUNT"


@pytest.mark.parametrize(
    "payload",
    [
        {"account": "ab", "display_name": "短账号", "password": "demo1234"},
        {"account": "   ", "display_name": "空白账号", "password": "demo1234"},
        {"account": "ok_account", "display_name": "   ", "password": "demo1234"},
        {"account": "ok_account2", "display_name": "短密码", "password": "short"},
    ],
)
async def test_register_validation_failed(client, payload):
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


async def test_register_rejects_role_field(client):
    """请求体里没有 role：额外字段一律 422，管理员账号不能自助注册。"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "account": "sneaky_admin",
            "display_name": "想变管理员",
            "password": "demo1234",
            "role": "admin",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
