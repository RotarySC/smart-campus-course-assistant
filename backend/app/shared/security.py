"""口令摘要与不透明令牌（设计 §6.1、NFR-SEC-002）。

- Argon2id（argon2-cffi 默认参数，TBD-03 未冻结，开发默认值）在受限线程池执行。
- 会话令牌 32 字节随机、base64url；仅持久化 SHA-256 摘要。
- 账号不存在时执行等效成本的虚拟校验，避免明显时间差。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# argon2-cffi 默认即 Argon2id（m=65536 KiB, t=3, p=4）。参数属 TBD-03。
_hasher = PasswordHasher()

# 虚拟校验用摘要（非真实账号口令；仅用于时间等价）
_VIRTUAL_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$gyoSo8ZPSA+MP3RbhVKXYg$"
    "WF7D1gdySp4nb/uq17JkXLldLtyG3vCQ1rhGhtgiwgI"
)

TOKEN_BYTES = 32


def _hash_sync(password: str) -> str:
    return _hasher.hash(password)


def _verify_sync(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


async def hash_password(password: str) -> str:
    """Argon2id 摘要（不阻塞事件循环）。"""
    return await asyncio.to_thread(_hash_sync, password)


async def verify_password(password_hash: str, password: str) -> bool:
    return await asyncio.to_thread(_verify_sync, password_hash, password)


async def burn_virtual_verify(password: str) -> None:
    """账号不存在时也走一次同成本校验，避免账号枚举时间差。"""
    await asyncio.to_thread(_verify_sync, _VIRTUAL_HASH, password)


def new_session_token() -> str:
    """32 字节随机令牌（base64url，无填充）。"""
    return base64.urlsafe_b64encode(secrets.token_bytes(TOKEN_BYTES)).rstrip(b"=").decode("ascii")


def token_digest(token: str) -> bytes:
    """令牌摘要（SHA-256，存 BINARY(32)）。"""
    return hashlib.sha256(token.encode("utf-8")).digest()


def constant_time_equals(left: bytes, right: bytes) -> bool:
    return hmac.compare_digest(left, right)


@lru_cache(maxsize=1)
def virtual_password_hash() -> str:
    return _VIRTUAL_HASH
