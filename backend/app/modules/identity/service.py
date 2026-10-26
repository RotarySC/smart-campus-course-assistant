"""身份模块服务：登录、登出、当前身份、学生账号维护（设计 §6.1）。

事务与锁：
- 登录：先按规范值查询并做口令校验（受限线程池），再在短事务中锁 User 复核
  enabled / password_hash / auth_version，建立 2h 会话（令牌仅返回一次）。
- 敏感写入先锁当前操作者 User；涉及目标学生时按 ID 升序一并锁定。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.adapters.db.models import AuthSession, SaveGrant, User
from app.adapters.db.uow import UoW, uow
from app.config import get_settings
from app.modules.identity.schemas import (
    LoginInput,
    RegisterInput,
    StudentCreate,
    StudentPatch,
    capabilities_for,
    user_view,
)
from app.modules.operations.service import append_audit
from app.shared.clock import from_db, isoformat, now_utc, to_db
from app.shared.errors import ApiError, map_integrity_error, validation_error
from app.shared.ids import PREFIX_SESSION, PREFIX_USER, new_id
from app.shared.security import (
    burn_virtual_verify,
    hash_password,
    new_session_token,
    token_digest,
    verify_password,
)

UNIFIED_LOGIN_FAILURE = "账号或密码不正确"


def normalize_account(account: str) -> tuple[str, bytes]:
    """账号先 trim，再按 Unicode casefold 产生唯一规范值（设计 §3.1）。"""
    trimmed = account.strip()
    normalized = trimmed.casefold().encode("utf-8")
    if len(normalized) > 768:
        raise validation_error(("account", "账号规范化后过长"))
    return trimmed, normalized


async def authenticate_token(raw_token: str, request_id: str) -> "ActorContextLike":
    """校验 Bearer 令牌当前状态（每次查询 User + AuthSession，不用进程缓存）。"""
    from app.shared.context import ActorContext

    if not raw_token:
        raise ApiError("AUTH_REQUIRED")
    digest = token_digest(raw_token)
    async with uow() as tx:
        result = await tx.session.execute(
            select(AuthSession).where(AuthSession.token_digest == digest)
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise ApiError("AUTH_REQUIRED")
        user = await tx.session.get(User, session.user_id)
    if user is None:
        raise ApiError("AUTH_REQUIRED")
    now = to_db(now_utc())
    if (
        session.revoked_at is not None
        or session.expires_at <= now
        or not user.enabled
        or int(session.auth_version) != int(user.auth_version)
    ):
        raise ApiError("SESSION_EXPIRED")
    return ActorContext(
        user_id=user.id,
        session_id=session.id,
        auth_version=int(user.auth_version),
        role=user.role,  # type: ignore[arg-type]
        trace_request_id=request_id,
        account=user.account,
        display_name=user.display_name,
        user_version=int(user.version),
        enabled=bool(user.enabled),
        session_expires_at=from_db(session.expires_at),
    )


ActorContextLike = Any


async def login(command: LoginInput, request_id: str) -> dict[str, Any]:
    settings = get_settings()
    trimmed, norm = normalize_account(command.account)

    async with uow() as tx:
        result = await tx.session.execute(select(User).where(User.account_norm == norm))
        candidate = result.scalar_one_or_none()

    if candidate is None:
        # 账号不存在也执行等效成本校验，避免时间差暴露账号是否存在。
        await burn_virtual_verify(command.password)
        raise ApiError("AUTH_REQUIRED", message=UNIFIED_LOGIN_FAILURE)

    if not await verify_password(candidate.password_hash, command.password):
        raise ApiError("AUTH_REQUIRED", message=UNIFIED_LOGIN_FAILURE)
    if not candidate.enabled:
        # 对外统一认证失败文案（FR-AUTH-001），不区分“禁用/不存在/口令错误”。
        raise ApiError("AUTH_REQUIRED", message=UNIFIED_LOGIN_FAILURE)

    now = now_utc()
    expires_at = now + timedelta(seconds=settings.session_ttl_seconds)
    raw_token = new_session_token()
    session_id = new_id(PREFIX_SESSION)

    async with uow() as tx:
        locked = await tx.lock_user(candidate.id)
        if (
            locked is None
            or not locked.enabled
            or locked.password_hash != candidate.password_hash
        ):
            raise ApiError("AUTH_REQUIRED", message=UNIFIED_LOGIN_FAILURE)
        session = AuthSession(
            id=session_id,
            user_id=locked.id,
            token_digest=token_digest(raw_token),
            auth_version=int(locked.auth_version),
            expires_at=to_db(expires_at),
            revoked_at=None,
            created_at=to_db(now),
        )
        tx.session.add(session)
        append_audit(
            tx,
            action="auth.login",
            object_type="user",
            object_id=locked.id,
            result="success",
            request_id=request_id,
            actor_id=locked.id,
        )
        await tx.commit()

    return {
        "access_token": raw_token,
        "token_type": "Bearer",
        "expires_at": isoformat(expires_at),
        "user": user_view(locked),
    }


async def register(command: RegisterInput, request_id: str) -> dict[str, Any]:
    """自助注册（桌面自适应追加包 §15.4）：建 student 账号并**在同一事务里**建 2h 会话。

    并发：不先查后写（避免 TOCTOU），直接依赖 `uq_users_account` 的唯一约束，
    把 `IntegrityError` 映射成 `DUPLICATE_ACCOUNT`（409）。
    """
    settings = get_settings()
    trimmed, norm = normalize_account(command.account)
    password_hash = await hash_password(command.password)
    now = now_utc()
    expires_at = now + timedelta(seconds=settings.session_ttl_seconds)
    raw_token = new_session_token()

    user = User(
        id=new_id(PREFIX_USER),
        account=trimmed,
        account_norm=norm,
        display_name=command.display_name.strip(),
        password_hash=password_hash,
        role="student",
        enabled=True,
        auth_version=1,
        version=1,
        created_at=to_db(now),
        updated_at=to_db(now),
    )
    try:
        async with uow() as tx:
            tx.session.add(user)
            await tx.session.flush()
            tx.session.add(
                AuthSession(
                    id=new_id(PREFIX_SESSION),
                    user_id=user.id,
                    token_digest=token_digest(raw_token),
                    auth_version=1,
                    expires_at=to_db(expires_at),
                    revoked_at=None,
                    created_at=to_db(now),
                )
            )
            append_audit(
                tx,
                action="auth.register",
                object_type="user",
                object_id=user.id,
                result="success",
                request_id=request_id,
                actor_id=user.id,
            )
            await tx.commit()
    except IntegrityError as exc:
        mapped = map_integrity_error(exc)
        raise mapped or ApiError("INTERNAL_ERROR") from None

    return {
        "access_token": raw_token,
        "token_type": "Bearer",
        "expires_at": isoformat(expires_at),
        "user": user_view(user),
    }


async def logout(actor: Any, request_id: str) -> dict[str, bool]:
    async with uow() as tx:
        await tx.lock_and_validate_actor(actor)
        session = await tx.lock_session(actor.session_id)
        if session is None or session.user_id != actor.user_id:
            raise ApiError("AUTH_REQUIRED")
        if session.revoked_at is None:
            session.revoked_at = to_db(now_utc())
        append_audit(
            tx,
            action="auth.logout",
            object_type="auth_session",
            object_id=session.id,
            result="success",
            request_id=request_id,
            actor_id=actor.user_id,
        )
        await tx.commit()
    return {"revoked": True}


async def get_me(actor: Any) -> dict[str, Any]:
    async with uow() as tx:
        user = await tx.session.get(User, actor.user_id)
    if user is None or not user.enabled:
        raise ApiError("SESSION_EXPIRED")
    return {
        "user": user_view(user),
        "session_expires_at": isoformat(actor.session_expires_at),
        "school_timezone": get_settings().school_timezone,
        "capabilities": capabilities_for(user.role),
    }


async def list_students(
    actor: Any,
    *,
    page: int,
    page_size: int,
    query: str | None,
    enabled: bool | None,
) -> dict[str, Any]:
    conditions = [User.role == "student"]
    if query:
        conditions.append(
            or_(
                User.account.contains(query, autoescape=True),
                User.display_name.contains(query, autoescape=True),
            )
        )
    if enabled is not None:
        conditions.append(User.enabled == enabled)

    async with uow() as tx:
        total = await tx.session.scalar(
            select(func.count()).select_from(User).where(*conditions)
        )
        result = await tx.session.execute(
            select(User)
            .where(*conditions)
            .order_by(User.created_at, User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list(result.scalars().all())
    return {
        "items": [user_view(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": int(total or 0),
    }


async def create_student(
    actor: Any, command: StudentCreate, request_id: str
) -> dict[str, Any]:
    trimmed, norm = normalize_account(command.account)
    password_hash = await hash_password(command.initial_password)
    now = to_db(now_utc())
    user = User(
        id=new_id(PREFIX_USER),
        account=trimmed,
        account_norm=norm,
        display_name=command.display_name,
        password_hash=password_hash,
        role="student",
        enabled=True,
        auth_version=1,
        version=1,
        created_at=now,
        updated_at=now,
    )
    try:
        async with uow() as tx:
            await tx.lock_and_validate_actor(actor)
            tx.session.add(user)
            await tx.session.flush()
            append_audit(
                tx,
                action="student.create",
                object_type="user",
                object_id=user.id,
                result="success",
                request_id=request_id,
                actor_id=actor.user_id,
            )
            await tx.commit()
    except IntegrityError as exc:
        mapped = map_integrity_error(exc)
        raise mapped or ApiError("INTERNAL_ERROR") from None
    return user_view(user)


async def patch_student(
    actor: Any, student_id: str, command: StudentPatch, request_id: str
) -> dict[str, Any]:
    now = to_db(now_utc())
    async with uow() as tx:
        locked_users = await tx.lock_users_and_validate_actor(actor, [student_id])
        target = locked_users.get(student_id)
        if target is None or target.role != "student":
            raise ApiError("RESOURCE_NOT_FOUND")
        if int(target.version) != command.expected_version:
            raise ApiError("VERSION_CONFLICT")

        provided = command.model_fields_set
        if "display_name" in provided and command.display_name is not None:
            target.display_name = command.display_name
        if "enabled" in provided and command.enabled is not None:
            target.enabled = bool(command.enabled)
            if not target.enabled:
                # 禁用 = 递增 auth_version + 撤销全部会话 + 撤销未消费许可（同事务）
                target.auth_version = int(target.auth_version) + 1
                await tx.session.execute(
                    update(AuthSession)
                    .where(
                        AuthSession.user_id == target.id,
                        AuthSession.revoked_at.is_(None),
                    )
                    .values(revoked_at=now)
                )
                await tx.session.execute(
                    update(SaveGrant)
                    .where(SaveGrant.user_id == target.id, SaveGrant.state == "issued")
                    .values(state="revoked")
                )
        target.version = int(target.version) + 1
        target.updated_at = now
        await tx.session.flush()
        append_audit(
            tx,
            action="student.patch",
            object_type="user",
            object_id=target.id,
            result="success",
            request_id=request_id,
            actor_id=actor.user_id,
            metadata={"fields": sorted(provided.intersection({"display_name", "enabled"}))},
        )
        await tx.commit()
        await tx.session.refresh(target)
    return user_view(target)
