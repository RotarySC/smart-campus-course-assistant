"""应用配置：环境变量驱动，启动时校验。

设计依据：后端详细设计 §13.1（配置分层）。开发期只读环境变量 / backend/.env，
不硬编码秘密；数据库连接串必须由 DATABASE_URL 提供。

P1-5（2026-10-28）：``backend/.env`` 现在对**所有** ``CCA_*`` 键生效，不再只有 pydantic
``Settings`` 声明的字段。理由：``registry/remote/judge/vector/knowledge`` 等装配键历史上
直接读 ``os.environ``，写进 ``.env`` 无效、必须启动前手工 export，造成"同一份配置两个入口"。

读取优先级（``env_str/env_flag/env_float/env_int`` 统一遵守）：

1. **进程环境变量**（键存在即采用，显式空串也算显式值 —— 用于覆盖 ``.env``）；
2. ``CCA_ENV_FILE`` 指向的文件（默认 ``backend/.env``）的快照；
3. 代码里的默认值。

``.env`` 快照按进程缓存（``dotenv_snapshot``），运行中改文件需重启；测试用
``CCA_ENV_FILE`` 指向自己的临时文件并调用 ``reset_env_snapshot()``。
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from app.shared.timezones import resolve_timezone

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE_OVERRIDE = "CCA_ENV_FILE"


def env_file_path() -> str:
    """唯一的 ``.env`` 入口：``CCA_ENV_FILE`` 优先，否则 ``backend/.env``。"""
    return os.environ.get(_ENV_FILE_OVERRIDE) or str(BACKEND_DIR / ".env")


@lru_cache(maxsize=1)
def dotenv_snapshot() -> dict[str, str]:
    """``.env`` 的只读快照（文件不存在 → 空字典）。

    只给"不进 pydantic Settings 的进程级装配键"使用；进程环境变量优先的规则见
    :func:`env_str`。运行期改文件不会热更新（与 ``Settings`` 的缓存语义一致）。
    """
    from dotenv import dotenv_values  # pydantic-settings 的传递依赖

    path = Path(env_file_path())
    if not path.is_file():
        return {}
    return {
        str(key): str(value)
        for key, value in dotenv_values(path).items()
        if value is not None
    }


def reset_env_snapshot() -> None:
    """清 ``.env`` 快照（测试切换 ``CCA_ENV_FILE`` 后调用）。"""
    dotenv_snapshot.cache_clear()


def env_str(name: str, default: str = "") -> str:
    """进程环境变量 > .env > default；显式空串同样视为显式值。"""
    if name in os.environ:
        return os.environ[name]
    return dotenv_snapshot().get(name, default)


def env_flag(name: str, default: bool) -> bool:
    """布尔开关；空值/无法识别回落 default。"""
    raw = env_str(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def env_float(name: str, default: float) -> float:
    """浮点配置；空值或解析失败回落 default（不抛）。"""
    raw = env_str(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    """整数配置；空值或解析失败回落 default（不抛）。"""
    raw = env_str(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ---- 检索精排 Reranker（跨编码器；默认关闭，接入点在 knowledge/service.py:_decide）----
# 这些键只描述"怎么连服务端 + 检索侧用什么口径"：
# ``CCA_RERANK_ENABLED=0``（默认）时 ``build_reranker()`` 返回 None，检索走 2026-10-28 的
# "余弦分数门 + 判官"路径，行为不变；开启后余弦硬门（``CCA_RETRIEVAL_MIN_SCORE``）不再生效，
# 由精排分决定放行/判空（否则会把答案片段一起挡掉，实测 main 集 B01）。
# 服务端契约（POST {BASE_URL}{PATH}）与分数语义见 ``app/adapters/rerank/remote.py``。
RERANK_DEFAULT_BASE_URL = "http://127.0.0.1:8892"
RERANK_DEFAULT_PATH = "/rerank"
RERANK_DEFAULT_MODEL = "bge-reranker-v2-m3"
RERANK_DEFAULT_TIMEOUT_S = 20.0
RERANK_DEFAULT_TOP_K = 8
# 精排分数门（2026-10-29 用评测主集 30 条标定；明细见 verification/ai-eval/rerank-probe/）：
#   LOW  = 0.30  跨编码器认为"连主题相近都算不上" → 直接判空，不花一次 LLM 判官；
#   HIGH = 0.90  接近满分 → 单次判官否定不足以推翻，直接放行。实测判官对"检索到的
#                是主题相近片段"很敏感，会对本该通过的用例误判（B09/B20），需要这道上限。
# 达标区是成片的（LOW 0.10–0.40 × HIGH 0.80–0.95 在 main 上全部 based 20/20、uncovered 10/10），
# 不是单点巧合；改这两个值前请先重跑 rerank_probe.py + rerank_thresholds.py。
RERANK_DEFAULT_LOW = 0.30
RERANK_DEFAULT_HIGH = 0.90
# 精排输出的“噪声底”：低于它的分数等于模型完全没找到对应关系，不是“分数偏低”。
# 0.01 来自 main 集实测——无关片段集中在 1e-4~1e-3（同一批候选里最低 0.0001），
# 而“问句改写导致被低估”的相关片段仍有 0.03~0.05，两者差一个量级以上。
# 低于噪声底直接判空（省一次 LLM 判官）；高于噪声底但低于 LOW 的，交由判官读正文。
RERANK_DEFAULT_NOISE_FLOOR = 0.01
RERANK_DEFAULT_MAX_DOC_CHARS = 1200
RERANK_DEFAULT_MAX_DOCS = 32


def rerank_enabled() -> bool:
    """是否启用精排层；默认关（行为与未引入时一致）。"""
    return env_flag("CCA_RERANK_ENABLED", False)


def rerank_base_url() -> str:
    """服务根地址（不含 path）；去掉尾部斜杠，避免拼出 ``//rerank``。"""
    raw = env_str("CCA_RERANK_BASE_URL", RERANK_DEFAULT_BASE_URL).strip().rstrip("/")
    return raw or RERANK_DEFAULT_BASE_URL


def rerank_path() -> str:
    """端点路径；空值回落 ``/rerank``，缺前导斜杠时补上。"""
    raw = env_str("CCA_RERANK_PATH", RERANK_DEFAULT_PATH).strip()
    if not raw:
        return RERANK_DEFAULT_PATH
    return raw if raw.startswith("/") else f"/{raw}"


def rerank_model() -> str:
    """模型标识；只用于日志/``name``，不作为请求字段（契约里没有 model）。"""
    return env_str("CCA_RERANK_MODEL", RERANK_DEFAULT_MODEL).strip() or RERANK_DEFAULT_MODEL


def rerank_timeout_s() -> float:
    return max(1.0, min(env_float("CCA_RERANK_TIMEOUT_S", RERANK_DEFAULT_TIMEOUT_S), 600.0))


def rerank_top_k() -> int:
    """检索侧送入精排的候选上限（截断数），不是服务端 top_n。"""
    return max(1, min(env_int("CCA_RERANK_TOP_K", RERANK_DEFAULT_TOP_K), 256))


def rerank_low() -> float:
    return max(0.0, min(env_float("CCA_RERANK_LOW", RERANK_DEFAULT_LOW), 1.0))


def rerank_high() -> float:
    return max(0.0, min(env_float("CCA_RERANK_HIGH", RERANK_DEFAULT_HIGH), 1.0))


def rerank_band() -> tuple[float, float]:
    """``(LOW, HIGH)`` 分数门：低于 LOW 直接判空，高于等于 HIGH 直接放行，中间问判官。

    与判官一致：配反（HIGH < LOW）时把 HIGH 抬到 LOW，避免把整段检索随机判空。
    """
    low = rerank_low()
    high = rerank_high()
    return low, max(low, high)


def rerank_noise_floor() -> float:
    """精排分低于此值视为“模型没找到对应关系”（而不是“分数偏低”）。

    与 ``LOW`` 的区别：``LOW`` 是“连主题相近都算不上”的判空线，但实测跨编码器对
    问句改写极敏感（同一片段「题型和分值」0.83 / 「题型和分值是怎么分布的」0.05），
    落在 ``[noise_floor, LOW)`` 的分数往往是有答案被问句形式压低了，不该单凭它判空。
    """
    return max(0.0, min(env_float("CCA_RERANK_NOISE_FLOOR", RERANK_DEFAULT_NOISE_FLOOR), 1.0))


def rerank_fail_open() -> bool:
    """精排不可用时是否放行（保留检索分数）；默认 1=放行。"""
    return env_flag("CCA_RERANK_FAIL_OPEN", True)


def rerank_max_doc_chars() -> int:
    """单条文档送精排前的最大字符数（超出截断，控制服务端 token 预算）。"""
    return max(1, min(env_int("CCA_RERANK_MAX_DOC_CHARS", RERANK_DEFAULT_MAX_DOC_CHARS), 100_000))


def rerank_max_docs() -> int:
    """单次请求最多送几条文档（超出部分不送、分数按 0.0 对齐）。"""
    return max(1, min(env_int("CCA_RERANK_MAX_DOCS", RERANK_DEFAULT_MAX_DOCS), 256))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_file_path(),
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

    # ---- 助手模型（TBD-04 骨架：真实供应商尚未冻结，默认走确定性 Provider）----
    # 供应商协议名，不是厂商名：openai-compatible 覆盖一切兼容 chat/completions 的服务。
    model_provider: Literal["deterministic", "openai-compatible"] = Field(
        default="deterministic", alias="CCA_MODEL_PROVIDER"
    )
    model_base_url: str = Field(default="", alias="CCA_MODEL_BASE_URL")
    model_api_key: str = Field(default="", alias="CCA_MODEL_API_KEY")
    model_name: str = Field(default="", alias="CCA_MODEL_NAME")
    model_temperature: float = Field(
        default=0.3, ge=0.0, le=2.0, alias="CCA_MODEL_TEMPERATURE"
    )
    model_max_tokens: int = Field(default=2048, ge=1, le=32768, alias="CCA_MODEL_MAX_TOKENS")
    model_timeout_seconds: float = Field(
        default=30.0, ge=1.0, le=600.0, alias="CCA_MODEL_TIMEOUT_SECONDS"
    )
    model_max_retries: int = Field(default=1, ge=0, le=3, alias="CCA_MODEL_MAX_RETRIES")

    # ---- 助手检索兜底（默认关闭）----
    # 真实检索不可用时是否允许回落到**固定假证据**（演示/测试专用）。
    # 生产必须为 false：伪造的文件名/页码会被当成权威引用（INV-04/05）。
    assistant_allow_stub_evidence: bool = Field(
        default=False, alias="CCA_ASSISTANT_ALLOW_STUB_EVIDENCE"
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

    @model_validator(mode="after")
    def _validate_model_config(self) -> "Settings":
        """真实供应商必须三件套齐全，且地址是 http(s)；缺一项就启动失败。"""
        if self.model_provider == "deterministic":
            return self
        missing = [
            key
            for key, value in (
                ("CCA_MODEL_BASE_URL", self.model_base_url),
                ("CCA_MODEL_API_KEY", self.model_api_key),
                ("CCA_MODEL_NAME", self.model_name),
            )
            if not value.strip()
        ]
        if missing:
            raise ValueError(
                f"CCA_MODEL_PROVIDER={self.model_provider} 时必须同时配置："
                + "、".join(missing)
            )
        if not self.model_base_url.startswith(("http://", "https://")):
            raise ValueError("CCA_MODEL_BASE_URL 必须是 http:// 或 https:// 开头的地址")
        return self

    @property
    def model_configured(self) -> bool:
        """是否配置了真实供应商（deterministic 恒为 False）。"""
        return self.model_provider != "deterministic"

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


__all__ = [
    "BACKEND_DIR",
    "Settings",
    "dotenv_snapshot",
    "env_file_path",
    "env_flag",
    "env_float",
    "env_int",
    "env_str",
    "get_settings",
    "reset_env_snapshot",
    "reset_settings_cache",
    "RERANK_DEFAULT_BASE_URL",
    "RERANK_DEFAULT_HIGH",
    "RERANK_DEFAULT_LOW",
    "RERANK_DEFAULT_MAX_DOC_CHARS",
    "RERANK_DEFAULT_MAX_DOCS",
    "RERANK_DEFAULT_MODEL",
    "RERANK_DEFAULT_NOISE_FLOOR",
    "RERANK_DEFAULT_PATH",
    "RERANK_DEFAULT_TIMEOUT_S",
    "RERANK_DEFAULT_TOP_K",
    "rerank_band",
    "rerank_base_url",
    "rerank_enabled",
    "rerank_fail_open",
    "rerank_high",
    "rerank_low",
    "rerank_max_doc_chars",
    "rerank_max_docs",
    "rerank_model",
    "rerank_noise_floor",
    "rerank_path",
    "rerank_timeout_s",
    "rerank_top_k",
]
