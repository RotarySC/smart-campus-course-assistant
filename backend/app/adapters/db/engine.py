"""数据库适配层：异步引擎、会话工厂、UoW 与行锁助手。

设计依据：后端详细设计 §1.2、§5（事务与锁协议）。约束：
- 每个短事务独立 ``AsyncSession``（禁止在并发任务间共享会话）。
- 使用真实 MySQL（aiomysql）；测试禁止 SQLite 替代锁/唯一键验证。
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_engine_url: str | None = None


def _build_engine(url: str) -> AsyncEngine:
    # 测试环境用 NullPool：pytest-asyncio 每个用例一个事件循环，
    # 连接池跨循环复用会触发 "Event loop is closed"。
    if get_settings().env == "test":
        return create_async_engine(url, poolclass=NullPool, echo=False, future=True)
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        echo=False,
        future=True,
    )


def get_engine() -> AsyncEngine:
    global _engine, _session_factory, _engine_url
    if _engine is None:
        url = os.environ.get("DATABASE_URL") or get_settings().database_url
        _engine = _build_engine(url)
        _engine_url = url
        _session_factory = async_sessionmaker(
            _engine, expire_on_commit=False, autoflush=False
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def dispose_engine() -> None:
    global _engine, _session_factory, _engine_url
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    _engine_url = None


def current_database_name() -> str:
    url = _engine_url or os.environ.get("DATABASE_URL") or get_settings().database_url
    return url.rsplit("/", 1)[-1].split("?", 1)[0]


async def check_database() -> bool:
    """健康检查：轻量 SELECT 1。"""
    from sqlalchemy import text

    engine = get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - 健康检查只关心可用性
        return False


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """只读/简单查询用短会话（不自动 commit）。"""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        await session.close()
