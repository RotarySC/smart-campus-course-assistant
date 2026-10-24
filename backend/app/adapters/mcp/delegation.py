"""双跳委派凭据（设计 §9.2；PHASE-03 A2）。

链路：

```
浏览器 Bearer → 公共 API 认证 → 签发 aud=cca-mcp 的短期委派（≤30s）
API → MCP：X-Service-Credential + X-CCA-Delegation（不进入工具 arguments）
MCP 校验 → POST /internal/v1/delegations/exchange（服务身份 + 已验委派）
内部 API 复核会话/enabled/auth_version/fence/scope → 签发 aud=cca-internal
MCP → 内部三工具：X-Service-Credential + X-Execution-Context(aud=cca-internal)
```

硬约束：
- 固定算法 HS256 与固定 audience；开发密钥来自 ``settings.delegation_signing_key``（TBD-03 未冻结）。
- 有效期 = min(30s, 本轮剩余时限)，不得被中间服务延长；中间服务不得放大 scope。
- jti 一次性消费（兑换端点），跨请求重放拒绝；过期即拒绝。
- 用户原始 Bearer 不进入 MCP，也不进入工具参数。
"""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Sequence

import jwt

from app.config import get_settings
from app.shared.clock import now_utc
from app.shared.errors import ApiError

ISSUER = "cca-api"
AUD_MCP = "cca-mcp"
AUD_INTERNAL = "cca-internal"

SCOPE_SCHEDULE_READ = "schedule:read"
SCOPE_DOCS_SEARCH = "docs:search"
SCOPE_PLAN_SAVE = "plan:save"
ALL_SCOPES: tuple[str, ...] = (SCOPE_SCHEDULE_READ, SCOPE_DOCS_SEARCH, SCOPE_PLAN_SAVE)

ALGORITHM = "HS256"
MAX_TTL_SECONDS = 30

REQUIRED_CLAIMS = (
    "iss",
    "aud",
    "sub",
    "session_id",
    "auth_version",
    "request_id",
    "conversation_id",
    "scope",
    "fence",
    "iat",
    "exp",
    "jti",
)


@dataclass(frozen=True)
class DelegationClaims:
    iss: str
    aud: str
    sub: str
    session_id: str
    auth_version: int
    request_id: str
    conversation_id: str
    scope: tuple[str, ...]
    fence: int
    iat: int
    exp: int
    jti: str

    @property
    def expires_at(self) -> datetime:
        return datetime.fromtimestamp(self.exp, tz=now_utc().tzinfo)

    def has_scope(self, scope: str) -> bool:
        return scope in self.scope

    def as_dict(self) -> dict[str, Any]:
        return {
            "iss": self.iss,
            "aud": self.aud,
            "sub": self.sub,
            "session_id": self.session_id,
            "auth_version": self.auth_version,
            "request_id": self.request_id,
            "conversation_id": self.conversation_id,
            "scope": list(self.scope),
            "fence": self.fence,
            "iat": self.iat,
            "exp": self.exp,
            "jti": self.jti,
        }


def _signing_key() -> str:
    return get_settings().delegation_signing_key


def _normalize_scope(scope: Iterable[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for item in scope:
        text = str(item).strip()
        if text not in ALL_SCOPES:
            raise ApiError("FORBIDDEN", message="委派范围不合法")
        if text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        raise ApiError("FORBIDDEN", message="委派范围不能为空")
    return tuple(cleaned)


def mint_delegation(
    *,
    audience: str,
    user_id: str,
    session_id: str,
    auth_version: int,
    request_id: str,
    conversation_id: str,
    scope: Sequence[str],
    fence: int,
    deadline_at: datetime | None = None,
    ttl_seconds: int = MAX_TTL_SECONDS,
) -> str:
    """签发短期委派；exp ≤ min(now+30s, 本轮剩余时限)。"""
    if audience not in (AUD_MCP, AUD_INTERNAL):
        raise ValueError("audience 必须是 cca-mcp 或 cca-internal")
    if not user_id or not session_id or not request_id or not conversation_id:
        raise ValueError("委派缺少必要绑定标识")
    scopes = _normalize_scope(scope)
    now = now_utc()
    expires = now + timedelta(seconds=min(max(int(ttl_seconds), 1), MAX_TTL_SECONDS))
    if deadline_at is not None:
        expires = min(expires, deadline_at)
    if expires <= now:
        raise ApiError("EXECUTION_TIMEOUT", message="本轮剩余时限不足，无法签发委派")
    claims = DelegationClaims(
        iss=ISSUER,
        aud=audience,
        sub=user_id,
        session_id=session_id,
        auth_version=int(auth_version),
        request_id=request_id,
        conversation_id=conversation_id,
        scope=scopes,
        fence=int(fence),
        iat=int(now.timestamp()),
        exp=int(expires.timestamp()),
        jti=secrets.token_urlsafe(18),
    )
    token = jwt.encode(claims.as_dict(), _signing_key(), algorithm=ALGORITHM)
    return str(token)


def _to_claims(payload: dict[str, Any], expected_audience: str) -> DelegationClaims:
    try:
        scope = tuple(payload.get("scope") or ())
        claims = DelegationClaims(
            iss=str(payload["iss"]),
            aud=str(payload["aud"]),
            sub=str(payload["sub"]),
            session_id=str(payload["session_id"]),
            auth_version=int(payload["auth_version"]),
            request_id=str(payload["request_id"]),
            conversation_id=str(payload["conversation_id"]),
            scope=scope,
            fence=int(payload["fence"]),
            iat=int(payload["iat"]),
            exp=int(payload["exp"]),
            jti=str(payload["jti"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError("AUTH_REQUIRED", message="委派凭据结构不合法") from exc
    if claims.iss != ISSUER:
        raise ApiError("AUTH_REQUIRED", message="委派签发方不合法")
    if claims.aud != expected_audience:
        raise ApiError("FORBIDDEN", message="委派受众不匹配")
    if not claims.sub or not claims.session_id or not claims.jti:
        raise ApiError("AUTH_REQUIRED", message="委派缺少身份绑定")
    if any(item not in ALL_SCOPES for item in claims.scope):
        raise ApiError("FORBIDDEN", message="委派范围不合法")
    if claims.exp - claims.iat > MAX_TTL_SECONDS + 1:
        # 中间服务不得延长有效期
        raise ApiError("FORBIDDEN", message="委派有效期超出上限")
    return claims


def verify_delegation(
    token: str,
    *,
    expected_audience: str,
    required_scope: str | None = None,
) -> DelegationClaims:
    """校验签名/受众/时效，并（可选）校验 scope。"""
    if not token or not token.strip():
        raise ApiError("AUTH_REQUIRED", message="缺少委派凭据")
    try:
        payload = jwt.decode(
            token,
            _signing_key(),
            algorithms=[ALGORITHM],
            audience=expected_audience,
            issuer=ISSUER,
            options={"require": list(REQUIRED_CLAIMS)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ApiError("AUTH_REQUIRED", message="委派已过期") from exc
    except jwt.InvalidAudienceError as exc:
        raise ApiError("FORBIDDEN", message="委派受众不匹配") from exc
    except jwt.InvalidIssuerError as exc:
        raise ApiError("AUTH_REQUIRED", message="委派签发方不合法") from exc
    except jwt.MissingRequiredClaimError as exc:
        raise ApiError("AUTH_REQUIRED", message="委派缺少必要声明") from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError("AUTH_REQUIRED", message="委派凭据无效") from exc
    if not isinstance(payload, dict):
        raise ApiError("AUTH_REQUIRED", message="委派凭据无效")
    claims = _to_claims(payload, expected_audience)
    if required_scope is not None and not claims.has_scope(required_scope):
        raise ApiError("FORBIDDEN", message="委派范围不足")
    return claims


class JtiRegistry:
    """jti 一次性消费（进程内；多进程部署需换共享存储，登记为未验证项）。"""

    def __init__(self) -> None:
        self._seen: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def consume(self, jti: str, *, expires_at: float) -> bool:
        async with self._lock:
            now = now_utc().timestamp()
            # 清理过期项，避免无界增长
            for key, exp in list(self._seen.items()):
                if exp <= now:
                    self._seen.pop(key, None)
            if jti in self._seen:
                return False
            self._seen[jti] = expires_at
            return True

    def reset(self) -> None:
        self._seen.clear()


_registry = JtiRegistry()


async def consume_jti(jti: str, *, expires_at: float) -> bool:
    return await _registry.consume(jti, expires_at=expires_at)


def reset_jti_registry() -> None:
    _registry.reset()


__all__ = [
    "ALL_SCOPES",
    "ALGORITHM",
    "AUD_INTERNAL",
    "AUD_MCP",
    "DelegationClaims",
    "ISSUER",
    "JtiRegistry",
    "MAX_TTL_SECONDS",
    "SCOPE_DOCS_SEARCH",
    "SCOPE_PLAN_SAVE",
    "SCOPE_SCHEDULE_READ",
    "consume_jti",
    "mint_delegation",
    "reset_jti_registry",
    "verify_delegation",
]
