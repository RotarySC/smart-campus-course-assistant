"""Unit of Work 与行锁助手（设计 §5.1 / §5.2 全局锁顺序）。

- 一个应用方法管理一个或少量显式短事务；每个短事务独立 ``AsyncSession``。
- 锁顺序：users（多用户按 ID 升序）→ auth_sessions → courses/conversation_states/
  chat_requests/ai_capacity_slots → plan_drafts → plan_draft_versions → write_operations →
  save_grants → assistant_save_slots → study_plans →（Phase 2 表）→ audit/outbox 插入。
- 事务内不等待模型、Embedding、MCP、文件解析或向量网络请求。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.engine import get_session_factory
from app.adapters.db.models import (
    AuthSession,
    ConversationState,
    Course,
    PlanDraft,
    PlanDraftVersion,
    SaveGrant,
    Schedule,
    StudyPlan,
    User,
    WriteOperation,
)
from app.shared.clock import now_utc, to_db
from app.shared.context import ActorContext
from app.shared.errors import ApiError
from app.shared.ids import PREFIX_SESSION


class UoW:
    """短事务边界 + 行锁助手。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- 事务 ----
    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def flush(self) -> None:
        await self.session.flush()

    # ---- 锁：users ----
    async def lock_user(self, user_id: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def lock_users(self, user_ids: Sequence[str]) -> dict[str, User]:
        """按 ID 升序锁定多用户，返回 id → User。"""
        ordered = sorted({uid for uid in user_ids if uid})
        if not ordered:
            return {}
        result = await self.session.execute(
            select(User).where(User.id.in_(ordered)).order_by(User.id).with_for_update()
        )
        rows = list(result.scalars().all())
        return {row.id: row for row in rows}

    # ---- 提交前二次校验（§5.1：敏感写入锁内复核启用状态）----
    @staticmethod
    def _validate_actor_row(actor: ActorContext, user: User | None) -> User:
        """锁内复核：enabled / auth_version / role 必须与认证上下文一致。

        认证依赖只在请求进入时检查一次；禁用、口令重置或角色变化可能发生在其后，
        因此所有敏感写入在提交前必须复核，避免“认证后、提交前被禁用”的写入穿透。
        """
        if (
            user is None
            or not user.enabled
            or int(user.auth_version) != int(actor.auth_version)
            or user.role != actor.role
        ):
            raise ApiError("SESSION_EXPIRED")
        return user

    async def lock_and_validate_actor(self, actor: ActorContext) -> User:
        """锁定当前操作者 User 并复核当前状态（全局锁顺序第 1 位）。"""
        return self._validate_actor_row(actor, await self.lock_user(actor.user_id))

    async def lock_users_and_validate_actor(
        self, actor: ActorContext, extra_ids: Sequence[str] = ()
    ) -> dict[str, User]:
        """按 ID 升序锁定操作者与目标用户，并复核操作者状态（顺序不变）。"""
        users = await self.lock_users([actor.user_id, *extra_ids])
        self._validate_actor_row(actor, users.get(actor.user_id))
        return users

    # ---- 锁：auth_sessions ----
    async def lock_session(self, session_id: str) -> AuthSession | None:
        result = await self.session.execute(
            select(AuthSession)
            .where(AuthSession.id == session_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def lock_user_sessions(self, user_id: str) -> list[AuthSession]:
        result = await self.session.execute(
            select(AuthSession)
            .where(AuthSession.user_id == user_id)
            .order_by(AuthSession.id)
            .with_for_update()
        )
        return list(result.scalars().all())

    # ---- 锁：courses ----
    async def lock_course(self, course_id: str) -> Course | None:
        result = await self.session.execute(
            select(Course).where(Course.id == course_id).with_for_update()
        )
        return result.scalar_one_or_none()

    # ---- 锁：schedules ----
    async def lock_schedule(self, schedule_id: str) -> Schedule | None:
        result = await self.session.execute(
            select(Schedule).where(Schedule.id == schedule_id).with_for_update()
        )
        return result.scalar_one_or_none()

    # ---- 锁：conversation / chat_requests（Phase 3 复用）----
    async def lock_conversation(self, conversation_id: str) -> ConversationState | None:
        result = await self.session.execute(
            select(ConversationState)
            .where(ConversationState.id == conversation_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def lock_chat_requests(self, request_ids: Sequence[str]) -> dict[str, object]:
        ordered = sorted({rid for rid in request_ids if rid})
        if not ordered:
            return {}
        from app.adapters.db.models import ChatRequest

        result = await self.session.execute(
            select(ChatRequest)
            .where(ChatRequest.id.in_(ordered))
            .order_by(ChatRequest.id)
            .with_for_update()
        )
        return {row.id: row for row in result.scalars().all()}

    # ---- 锁：草稿 → 版本 ----
    async def lock_draft(self, draft_id: str) -> PlanDraft | None:
        result = await self.session.execute(
            select(PlanDraft).where(PlanDraft.id == draft_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def lock_draft_version(
        self, draft_id: str, draft_version: int
    ) -> PlanDraftVersion | None:
        result = await self.session.execute(
            select(PlanDraftVersion)
            .where(
                PlanDraftVersion.draft_id == draft_id,
                PlanDraftVersion.draft_version == draft_version,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    # ---- 锁：write_operations → save_grants → assistant_save_slots ----
    async def lock_operation(
        self, user_id: str, operation_id: str
    ) -> WriteOperation | None:
        result = await self.session.execute(
            select(WriteOperation)
            .where(
                WriteOperation.user_id == user_id,
                WriteOperation.operation_id == operation_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def lock_grants_for_operation(
        self, user_id: str, operation_id: str
    ) -> list[SaveGrant]:
        result = await self.session.execute(
            select(SaveGrant)
            .where(
                SaveGrant.user_id == user_id,
                SaveGrant.operation_id == operation_id,
            )
            .order_by(SaveGrant.id)
            .with_for_update()
        )
        return list(result.scalars().all())

    # ---- 锁：study_plans ----
    async def lock_plan(self, plan_id: str, user_id: str) -> StudyPlan | None:
        result = await self.session.execute(
            select(StudyPlan)
            .where(StudyPlan.id == plan_id, StudyPlan.user_id == user_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    # ---- 便捷读取（非锁定）----
    async def get_user(self, user_id: str) -> User | None:
        return await self.session.get(User, user_id)


@asynccontextmanager
async def uow() -> AsyncIterator[UoW]:
    """打开一个短事务；退出时未 commit 则 rollback。"""
    factory = get_session_factory()
    session = factory()
    wrapper = UoW(session)
    try:
        yield wrapper
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def new_session_id() -> str:
    from app.shared.ids import new_id

    return new_id(PREFIX_SESSION)


def utcnow_db():
    return to_db(now_utc())
