"""应用工厂：组装中间件、异常处理器与模块路由。

T01 验收：``uvicorn app.entrypoints.public_api:app --port 8100`` 可启动；
``GET /api/v1/health`` 200；未知路径 404 信封化；多余字段 422 且错误码符合契约。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.db.engine import check_database, dispose_engine
from app.config import get_settings
from app.modules.academics.router import router as academics_router
from app.modules.assistant.router import router as assistant_router
from app.modules.identity.router import router as identity_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.operations.router import router as operations_router
from app.modules.planning.router import router as planning_router
from app.shared.api_models import Envelope, Health
from app.shared.http import (
    RequestContextMiddleware,
    enforce_strict_query,
    envelope,
    setup_exception_handlers,
)
from app.shared.log_redaction import install_redaction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

API_PREFIX = "/api/v1"


def build_api_router() -> APIRouter:
    router = APIRouter(
        prefix=API_PREFIX,
        dependencies=[Depends(enforce_strict_query)],
    )

    @router.get("/health", tags=["ops"], operation_id="health", response_model=Envelope[Health])
    async def health(request: Request):
        database_ok = await check_database()
        return envelope(
            request,
            {
                "status": "ok" if database_ok else "degraded",
                "checks": {
                    "process": "ok",
                    "database": "ok" if database_ok else "unavailable",
                },
            },
        )

    @router.get("/openapi.json", include_in_schema=False)
    async def runtime_openapi(request: Request):
        """运行态 OpenAPI（供前端 openapi-typescript 生成与漂移门禁）。"""
        return request.app.openapi()

    router.include_router(identity_router)
    router.include_router(academics_router)
    router.include_router(planning_router)
    # Phase 2 / Phase 3：路由在 Phase 1 冻结并挂载，未实现端点返回 501 信封。
    router.include_router(knowledge_router)
    router.include_router(assistant_router)
    router.include_router(operations_router)
    return router


def _configure_app(app: FastAPI, *, cors: bool) -> FastAPI:
    settings = get_settings()
    setup_exception_handlers(app)
    # NFR-PRIV-001：日志默认不落正文/凭据（含 logger.exception 的 SQLAlchemy 参数块）
    install_redaction()

    # 注意顺序：后添加的中间件在最外层；CORS 需包住 request_id 中间件。
    app.add_middleware(RequestContextMiddleware)
    if cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    return app


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await dispose_engine()

    app = FastAPI(
        title="校园课程智能助手 API",
        version="0.1.0",
        description="Phase 1：身份 / 课程 / 课表 / 计划 / 草稿 / 保存 / 写入状态",
        lifespan=lifespan,
    )
    _configure_app(app, cors=True)
    app.include_router(build_api_router())
    return app


def create_internal_app() -> FastAPI:
    """内部 API（Phase 3 实现；本阶段只冻结路由与信封）。"""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await dispose_engine()

    app = FastAPI(title="校园课程智能助手内部 API", version="0.1.0", lifespan=lifespan)
    _configure_app(app, cors=False)
    app.include_router(build_internal_router())
    return app


def build_internal_router() -> APIRouter:
    from app.modules.assistant.internal_router import router as internal_router

    router = APIRouter(prefix="/internal/v1")
    router.include_router(internal_router)
    return router


__all__ = [
    "API_PREFIX",
    "build_api_router",
    "build_internal_router",
    "create_app",
    "create_internal_app",
]
