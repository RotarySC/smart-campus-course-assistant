"""身份模块请求/响应 Schema 与视图序列化（字段以 OpenAPI 为权威）。"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator

from app.adapters.db.models import User
from app.shared.validation import ExpectedVersion, RequestModel, StrictBool

# 口令策略属 TBD-03：开发默认值（创建时 8–1024），登录只校验非空。
INITIAL_PASSWORD_MIN = 8
INITIAL_PASSWORD_MAX = 1024


class LoginInput(RequestModel):
    account: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


class RegisterInput(RequestModel):
    """自助注册（桌面自适应追加包 §15.4）：请求里**没有** role，落地固定 student。"""

    account: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=INITIAL_PASSWORD_MIN, max_length=INITIAL_PASSWORD_MAX)

    @field_validator("account")
    @classmethod
    def _account_trimmed(cls, value: str) -> str:
        trimmed = value.strip()
        if not (3 <= len(trimmed) <= 64):
            raise ValueError("账号去首尾空白后长度必须为 3–64")
        return trimmed

    @field_validator("display_name")
    @classmethod
    def _display_name_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("显示名不能为空白")
        return value


class StudentCreate(RequestModel):
    account: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=50)
    initial_password: str = Field(min_length=1, max_length=INITIAL_PASSWORD_MAX)

    @field_validator("initial_password")
    @classmethod
    def _password_policy(cls, value: str) -> str:
        if len(value) < INITIAL_PASSWORD_MIN:
            raise ValueError(f"初始口令至少 {INITIAL_PASSWORD_MIN} 个字符")
        return value

    @field_validator("account")
    @classmethod
    def _account_trimmed(cls, value: str) -> str:
        trimmed = value.strip()
        if not (3 <= len(trimmed) <= 64):
            raise ValueError("账号去首尾空白后长度必须为 3–64")
        return trimmed

    @field_validator("display_name")
    @classmethod
    def _display_name_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("显示名不能为空白")
        return value


class StudentPatch(RequestModel):
    # 可选但非 nullable：缺省不出现；显式 null 由类型校验拒绝（与设计包一致）
    display_name: str = Field(default=None, min_length=1, max_length=50)  # type: ignore[assignment]
    enabled: StrictBool = Field(default=None)  # type: ignore[assignment]
    expected_version: ExpectedVersion

    @model_validator(mode="after")
    def _patch_shape(self) -> "StudentPatch":
        provided = self.model_fields_set
        if not provided.intersection({"display_name", "enabled"}):
            raise ValueError("至少提供 display_name 或 enabled 之一")
        # 显式 null 不允许（OpenAPI 中两字段均非 nullable）
        for name in ("display_name", "enabled"):
            if name in provided and getattr(self, name) is None:
                raise ValueError(f"{name} 不允许为 null")
        if "display_name" in provided and not (self.display_name or "").strip():
            raise ValueError("显示名不能为空白")
        return self


def user_view(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "account": user.account,
        "display_name": user.display_name,
        "role": user.role,
        "enabled": bool(user.enabled),
        "version": int(user.version),
    }


def capabilities_for(role: str) -> list[str]:
    """前端已消费的能力集合（mock 同源：chat/plans/schedules，管理员另有 admin）。"""
    caps = ["chat", "plans", "schedules"]
    if role == "admin":
        caps.append("admin")
    return caps
