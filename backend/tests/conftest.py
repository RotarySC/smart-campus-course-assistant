"""测试夹具（Phase 1 车道，库名由 DATABASE_URL 覆盖；默认 cca_test_core）。

约定（供 Phase 2/3 复用，勿改名）：
- ``client``      : httpx.AsyncClient（ASGI 直连，真实应用 + 真实 MySQL）
- ``db``          : async_sessionmaker，测试直接造数据/断言
- ``seeded``      : admin/student/course 已就绪的字典（含 Authorization 头）
- ``make_draft``  : 造一条草稿（含 conversation/chat_request/version），供保存路径测试
- ``login``       : 登录辅助函数
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Awaitable

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parent.parent

# 必须在导入 app 之前固定环境变量（设置模块缓存）。
os.environ.setdefault(
    "DATABASE_URL",
    "mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_core?charset=utf8mb4",
)
os.environ.setdefault("CCA_ENV", "test")

_db_name = os.environ["DATABASE_URL"].rsplit("/", 1)[-1].split("?", 1)[0]
if "_test_" not in _db_name:
    raise RuntimeError(
        f"拒绝在非测试库上跑测试：{_db_name}（必须形如 cca_test_core）"
    )

TABLES = [
    "assistant_save_slots",
    "save_grants",
    "study_plans",
    "write_operations",
    "plan_draft_versions",
    "plan_drafts",
    "ai_capacity_slots",
    "chat_requests",
    "conversation_states",
    "schedules",
    "courses",
    "auth_sessions",
    "users",
    "citation_references",
    "chunks",
    "document_versions",
    "documents",
    "document_batches",
    "storage_attempts",
    "background_tasks",
    "outbox_events",
    "audit_events",
    "corpus_control",
]


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Any:
    """会话级：空库执行 alembic upgrade head（真实 MySQL）。"""
    env = dict(os.environ)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade 失败:\n{result.stdout}\n{result.stderr}")
    yield
    from app.adapters.db.engine import dispose_engine

    import asyncio

    asyncio.run(dispose_engine())


@pytest_asyncio.fixture(autouse=True)
async def clean_database(migrated_database: Any):
    """每个用例前清表并恢复控制记录（23 表，FK 检查关闭）。"""
    from app.adapters.db.engine import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in TABLES:
            await conn.execute(text(f"TRUNCATE TABLE `{table}`"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        await conn.execute(
            text(
                "INSERT INTO corpus_control (singleton_id, revision, publish_frozen, updated_at) "
                "VALUES (1, 0, TRUE, UTC_TIMESTAMP(6))"
            )
        )
        await conn.execute(
            text("INSERT INTO ai_capacity_slots (slot_no) VALUES (1),(2),(3),(4),(5)")
        )
    yield


@pytest_asyncio.fixture
async def client() -> Any:
    from app.main import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest_asyncio.fixture
async def db() -> Any:
    from app.adapters.db.engine import get_session_factory

    yield get_session_factory()


# --------------------------------------------------------------------------- #
# 数据构造辅助
# --------------------------------------------------------------------------- #
async def create_user_row(
    *,
    account: str,
    password: str = "demo1234",
    role: str = "student",
    display_name: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    from app.adapters.db.models import User
    from app.adapters.db.uow import uow
    from app.shared.clock import now_utc, to_db
    from app.shared.ids import PREFIX_USER, new_id
    from app.shared.security import hash_password

    norm = account.strip().casefold().encode("utf-8")
    now = to_db(now_utc())
    user_id = new_id(PREFIX_USER)
    async with uow() as tx:
        tx.session.add(
            User(
                id=user_id,
                account=account,
                account_norm=norm,
                display_name=display_name or account,
                password_hash=await hash_password(password),
                role=role,
                enabled=enabled,
                auth_version=1,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        await tx.commit()
    return {
        "id": user_id,
        "account": account,
        "password": password,
        "role": role,
        "enabled": enabled,
    }


@pytest_asyncio.fixture
async def login(client: httpx.AsyncClient) -> Callable[[str, str], Awaitable[str]]:
    async def _login(account: str, password: str = "demo1234") -> str:
        response = await client.post(
            "/api/v1/auth/login", json={"account": account, "password": password}
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]["access_token"]

    return _login


@pytest_asyncio.fixture
async def seeded(client: httpx.AsyncClient, login: Any) -> dict[str, Any]:
    """管理员 + 学生 + 一门课程，均已登录。"""
    admin = await create_user_row(account="admin_seed", role="admin", display_name="管理员")
    student = await create_user_row(account="student_seed", role="student", display_name="学生甲")
    other = await create_user_row(account="student_other", role="student", display_name="学生乙")
    admin_token = await login(admin["account"], admin["password"])
    student_token = await login(student["account"], student["password"])
    other_token = await login(other["account"], other["password"])

    course_resp = await client.post(
        "/api/v1/admin/courses",
        json={"code": "CS101", "name": "数据结构", "description": "数组与链表"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert course_resp.status_code == 201, course_resp.text
    course = course_resp.json()["data"]

    return {
        "admin": admin,
        "student": student,
        "other": other,
        "course": course,
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "student_headers": {"Authorization": f"Bearer {student_token}"},
        "other_headers": {"Authorization": f"Bearer {other_token}"},
        "admin_token": admin_token,
        "student_token": student_token,
    }


async def _session_id_for_token(token: str) -> str:
    from sqlalchemy import select

    from app.adapters.db.engine import get_session_factory
    from app.adapters.db.models import AuthSession
    from app.shared.security import token_digest

    async with get_session_factory()() as session:
        result = await session.execute(
            select(AuthSession).where(AuthSession.token_digest == token_digest(token))
        )
        return result.scalar_one().id


@pytest_asyncio.fixture
async def make_draft(seeded: dict[str, Any]) -> Callable[..., Awaitable[dict[str, Any]]]:
    """造草稿：conversation_states + chat_requests + plan_drafts + version。"""
    from app.adapters.db.models import (
        ChatRequest,
        ConversationState,
        PlanDraft,
        PlanDraftVersion,
    )
    from app.adapters.db.uow import uow
    from app.shared.clock import now_utc, to_db
    from app.shared.ids import (
        PREFIX_CONVERSATION,
        PREFIX_DRAFT,
        PREFIX_DRAFT_OPERATION,
        PREFIX_REQUEST,
        new_id,
    )
    from app.shared.payload import normalize_plan_payload, plan_payload_digest

    async def _make(
        *,
        title: str = "生成的学习计划",
        content: str = "周一复习数据结构，周三做习题。",
        goal: str | None = "掌握基础",
        basis_types: list[str] | None = None,
        references: list[dict[str, Any]] | None = None,
        expires_in_seconds: int = 1800,
        token: str | None = None,
    ) -> dict[str, Any]:
        token = token or seeded["student_token"]
        session_id = await _session_id_for_token(token)
        now = now_utc()
        conversation_id = new_id(PREFIX_CONVERSATION)
        request_id = new_id(PREFIX_REQUEST)
        draft_id = new_id(PREFIX_DRAFT)
        operation_id = new_id(PREFIX_DRAFT_OPERATION)
        payload = normalize_plan_payload(
            {
                "title": title,
                "goal": goal,
                "start_date": None,
                "end_date": None,
                "content": content,
                "basis_types": basis_types or ["general"],
                "references": references or [],
            }
        )
        digest = plan_payload_digest(payload)
        async with uow() as tx:
            tx.session.add(
                ConversationState(
                    id=conversation_id,
                    user_id=seeded["student"]["id"],
                    session_id=session_id,
                    active_request_id=None,
                    created_at=to_db(now),
                    updated_at=to_db(now),
                )
            )
            tx.session.add(
                ChatRequest(
                    id=request_id,
                    client_request_id=new_id(PREFIX_REQUEST),
                    user_id=seeded["student"]["id"],
                    session_id=session_id,
                    conversation_id=conversation_id,
                    request_digest=digest,
                    state="succeeded",
                    cancel_requested=False,
                    accepted_at=to_db(now),
                    deadline_at=to_db(now + __import__("datetime").timedelta(seconds=60)),
                    finished_at=to_db(now),
                    school_timezone="Asia/Shanghai",
                    model_calls=1,
                    tool_calls=0,
                    fence=1,
                )
            )
            tx.session.add(
                PlanDraft(
                    id=draft_id,
                    user_id=seeded["student"]["id"],
                    session_id=session_id,
                    conversation_id=conversation_id,
                    origin_chat_request_id=request_id,
                    current_version=1,
                    expires_at=to_db(
                        now + __import__("datetime").timedelta(seconds=expires_in_seconds)
                    ),
                    created_at=to_db(now),
                    updated_at=to_db(now),
                )
            )
            tx.session.add(
                PlanDraftVersion(
                    draft_id=draft_id,
                    draft_version=1,
                    operation_id=operation_id,
                    schema_version=1,
                    payload=payload,
                    content_digest=digest,
                    created_at=to_db(now),
                )
            )
            await tx.commit()
        return {
            "draft_id": draft_id,
            "draft_version": 1,
            "operation_id": operation_id,
            "payload": payload,
            "request_id": request_id,
            "session_id": session_id,
        }

    return _make


@pytest.fixture
def api() -> Callable[[str], str]:
    return lambda path: f"/api/v1{path}"
