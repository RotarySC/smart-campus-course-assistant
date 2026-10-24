"""应用配置：环境变量驱动，启动时校验。

设计依据：后端详细设计 §13.1（配置分层）。开发期只读环境变量 / backend/.env，
不硬编码秘密；数据库连接串必须由 DATABASE_URL 提供。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from app.shared.timezones import resolve_timezone

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 基础设施 ----
    database_url: str = Field(
        default="mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_core?charset=utf8mb4",
        alias="DATABASE_URL",
    )
    env: Literal["dev", "test", "prod"] = Field(default="dev", alias="CCA_ENV")

    # ---- 学校与业务 ----
    school_timezone: str = Field(default="Asia/Shanghai", alias="CCA_SCHOOL_TIMEZONE")
    page_default_size: int = Field(default=20, ge=1, le=100, alias="CCA_PAGE_DEFAULT_SIZE")
    page_max_size: int = Field(default=100, ge=1, le=100, alias="CCA_PAGE_MAX_SIZE")
    schedule_max_days: int = Field(default=31, ge=1, le=31, alias="CCA_SCHEDULE_MAX_DAYS")

    # ---- 会话与草稿 ----
    session_ttl_seconds: int = Field(default=7200, ge=60, alias="CCA_SESSION_TTL_SECONDS")
    draft_ttl_seconds: int = Field(default=1800, ge=60, alias="CCA_DRAFT_TTL_SECONDS")

    # ---- 上传（Phase 2 使用；本阶段只校验配置存在）----
    upload_max_files: int = Field(default=10, ge=1, alias="CCA_UPLOAD_MAX_FILES")
    upload_max_file_bytes: int = Field(
        default=20 * 1024 * 1024, ge=1, alias="CCA_UPLOAD_MAX_FILE_BYTES"
    )
    upload_max_total_bytes: int = Field(
        default=50 * 1024 * 1024, ge=1, alias="CCA_UPLOAD_MAX_TOTAL_BYTES"
    )

    # ---- 前端来源 ----
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        alias="CCA_CORS_ORIGINS",
    )

    # ---- 服务认证（Phase 3）----
    service_token: str = Field(default="dev-internal-token", alias="CCA_SERVICE_TOKEN")
    delegation_signing_key: str = Field(
        default="dev-delegation-key-not-for-production", alias="CCA_DELEGATION_SIGNING_KEY"
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("school_timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            resolve_timezone(value)
        except ValueError as exc:  # pragma: no cover - 配置错误
            raise ValueError(str(exc)) from exc
        return value

    @field_validator("database_url")
    @classmethod
    def _validate_mysql(cls, value: str) -> str:
        # 设计 D1：只使用 MySQL；不允许 SQLite 替代（锁/唯一键验证必须真 MySQL）。
        if not value.startswith(("mysql+aiomysql://", "mysql+asyncmy://", "mysql+pymysql://")):
            raise ValueError("DATABASE_URL 必须是 MySQL 连接串（mysql+aiomysql://…）")
        return value

    @property
    def database_name(self) -> str:
        tail = self.database_url.rsplit("/", 1)[-1]
        return tail.split("?", 1)[0]

    @property
    def tz(self):
        return resolve_timezone(self.school_timezone)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """测试中切换环境变量后调用。"""
    get_settings.cache_clear()
