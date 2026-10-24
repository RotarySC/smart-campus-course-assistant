"""身份模块 Interface（供路由与其它模块复用的认证依赖）。

签名冻结（Phase 2/3 直接复用）：
- ``get_actor(request) -> ActorContext``：Bearer 认证，每次查询 User + AuthSession 当前状态。
- ``get_admin(actor) -> ActorContext``：管理员校验，学生 403。
"""

from __future__ import annotations

from fastapi import Depends, Request

from app.modules.identity.service import authenticate_token
from app.shared.context import ActorContext
from app.shared.errors import ApiError
from app.shared.http import request_id_of


async def get_actor(request: Request) -> ActorContext:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if not header or scheme.lower() != "bearer" or not token.strip():
        raise ApiError("AUTH_REQUIRED")
    return await authenticate_token(token.strip(), request_id_of(request))


async def get_admin(actor: ActorContext = Depends(get_actor)) -> ActorContext:
    if not actor.is_admin:
        raise ApiError("FORBIDDEN")
    return actor


__all__ = ["get_actor", "get_admin"]
