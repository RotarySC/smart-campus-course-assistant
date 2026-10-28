"""P1-5：``backend/.env`` 对所有 ``CCA_*`` 键生效（进程环境变量仍然优先）。

这些用例是 hermetic 的：不读开发者本机 ``backend/.env``，每个用例自己写一份临时
``.env`` 并 monkeypatch ``CCA_ENV_FILE``，再调用 ``app.config.reset_env_snapshot()``
清快照（快照是进程级缓存，等价于"重启后生效"）。
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app import config as app_config


@pytest.fixture(autouse=True)
def isolated_env_file(monkeypatch):
    """默认指向一个不存在的 .env；用例内可覆盖，结束后清缓存防串味。"""
    absent = Path(__file__).resolve().parent / "no-such-env-file.env"
    monkeypatch.setenv("CCA_ENV_FILE", str(absent))
    app_config.reset_env_snapshot()
    yield
    app_config.reset_env_snapshot()


def _write_env(tmp_path: Path, content: str) -> str:
    path = tmp_path / "case.env"
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
    return str(path)


def _use_env(monkeypatch, tmp_path: Path, content: str) -> str:
    path = _write_env(tmp_path, content)
    monkeypatch.setenv("CCA_ENV_FILE", path)
    app_config.reset_env_snapshot()
    return path


# --------------------------------------------------------------------------- #
# 基础语义：.env 生效、环境变量优先、空串覆盖、回落默认
# --------------------------------------------------------------------------- #
def test_dotenv_values_are_read_when_env_missing(monkeypatch, tmp_path):
    _use_env(
        monkeypatch,
        tmp_path,
        """
        CCA_DEMO_TEXT=from-file
        CCA_DEMO_INT=7
        CCA_DEMO_FLOAT=0.25
        CCA_DEMO_FLAG=1
        """,
    )
    monkeypatch.delenv("CCA_DEMO_TEXT", raising=False)
    monkeypatch.delenv("CCA_DEMO_INT", raising=False)
    monkeypatch.delenv("CCA_DEMO_FLOAT", raising=False)
    monkeypatch.delenv("CCA_DEMO_FLAG", raising=False)

    assert app_config.env_str("CCA_DEMO_TEXT") == "from-file"
    assert app_config.env_int("CCA_DEMO_INT", 0) == 7
    assert app_config.env_float("CCA_DEMO_FLOAT", 0.0) == 0.25
    assert app_config.env_flag("CCA_DEMO_FLAG", False) is True


def test_process_env_overrides_dotenv(monkeypatch, tmp_path):
    _use_env(monkeypatch, tmp_path, "CCA_DEMO_TEXT=from-file\nCCA_DEMO_INT=7\n")
    monkeypatch.setenv("CCA_DEMO_TEXT", "from-process")
    monkeypatch.setenv("CCA_DEMO_INT", "9")

    assert app_config.env_str("CCA_DEMO_TEXT") == "from-process"
    assert app_config.env_int("CCA_DEMO_INT", 0) == 9


def test_explicit_empty_env_overrides_dotenv(monkeypatch, tmp_path):
    """显式空串是"显式值"：env_str 返回空串（而不是 .env 里的值）。"""
    _use_env(monkeypatch, tmp_path, "CCA_DEMO_TEXT=from-file\nCCA_DEMO_INT=7\n")
    monkeypatch.setenv("CCA_DEMO_TEXT", "")

    assert app_config.env_str("CCA_DEMO_TEXT") == ""
    # 空串对数值工具等于"未设置"，回落 default（不是 .env 的 7）
    monkeypatch.setenv("CCA_DEMO_INT", "")
    assert app_config.env_int("CCA_DEMO_INT", 3) == 3


def test_missing_key_and_missing_file_fall_back_to_default(monkeypatch, tmp_path):
    _use_env(monkeypatch, tmp_path, "CCA_DEMO_TEXT=from-file\n")
    assert app_config.env_str("CCA_ABSENT_KEY", "fallback") == "fallback"
    assert app_config.env_int("CCA_ABSENT_INT", 5) == 5
    assert app_config.env_float("CCA_ABSENT_FLOAT", 1.5) == 1.5
    assert app_config.env_flag("CCA_ABSENT_FLAG", True) is True

    monkeypatch.setenv("CCA_ENV_FILE", str(tmp_path / "does-not-exist.env"))
    app_config.reset_env_snapshot()
    assert app_config.dotenv_snapshot() == {}
    assert app_config.env_str("CCA_DEMO_TEXT", "fallback") == "fallback"


def test_unparsable_values_fall_back_to_default(monkeypatch, tmp_path):
    _use_env(
        monkeypatch,
        tmp_path,
        """
        CCA_DEMO_INT=not-an-int
        CCA_DEMO_FLOAT=not-a-float
        CCA_DEMO_FLAG=maybe
        """,
    )
    assert app_config.env_int("CCA_DEMO_INT", 7) == 7
    assert app_config.env_float("CCA_DEMO_FLOAT", 0.5) == 0.5
    assert app_config.env_flag("CCA_DEMO_FLAG", False) is False


def test_flag_accepts_common_truthy_spellings(monkeypatch, tmp_path):
    for value, expected in (
        ("1", True),
        ("true", True),
        ("YES", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("", False),
    ):
        _use_env(monkeypatch, tmp_path, f"CCA_DEMO_FLAG={value}\n")
        assert app_config.env_flag("CCA_DEMO_FLAG", False) is expected, value


def test_snapshot_is_cached_until_reset(monkeypatch, tmp_path):
    path = _use_env(monkeypatch, tmp_path, "CCA_DEMO_TEXT=first\n")
    assert app_config.env_str("CCA_DEMO_TEXT") == "first"
    Path(path).write_text("CCA_DEMO_TEXT=second\n", encoding="utf-8")
    assert app_config.env_str("CCA_DEMO_TEXT") == "first"  # 进程内缓存，重启才变
    app_config.reset_env_snapshot()
    assert app_config.env_str("CCA_DEMO_TEXT") == "second"


def test_env_file_path_override(monkeypatch, tmp_path):
    target = str(tmp_path / "custom.env")
    monkeypatch.setenv("CCA_ENV_FILE", target)
    assert app_config.env_file_path() == target


# --------------------------------------------------------------------------- #
# 业务装配键：写进 .env 即生效（P1-5 的核心回归）
# --------------------------------------------------------------------------- #
def test_judge_settings_read_from_dotenv(monkeypatch, tmp_path):
    from app.adapters.judge.llm import (
        judge_band,
        judge_enabled,
        judge_fail_open,
        RetrievalJudge,
    )

    _use_env(
        monkeypatch,
        tmp_path,
        """
        CCA_RETRIEVAL_JUDGE=1
        CCA_RETRIEVAL_JUDGE_LOW=0.30
        CCA_RETRIEVAL_JUDGE_HIGH=0.60
        CCA_RETRIEVAL_JUDGE_FAIL_OPEN=0
        CCA_RETRIEVAL_JUDGE_TIMEOUT_SECONDS=5
        CCA_RETRIEVAL_JUDGE_MAX_TOKENS=256
        CCA_RETRIEVAL_JUDGE_MODEL=judge-from-env
        """,
    )
    for key in (
        "CCA_RETRIEVAL_JUDGE",
        "CCA_RETRIEVAL_JUDGE_LOW",
        "CCA_RETRIEVAL_JUDGE_HIGH",
        "CCA_RETRIEVAL_JUDGE_FAIL_OPEN",
        "CCA_RETRIEVAL_JUDGE_TIMEOUT_SECONDS",
        "CCA_RETRIEVAL_JUDGE_MAX_TOKENS",
        "CCA_RETRIEVAL_JUDGE_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)

    assert judge_enabled() is True
    assert judge_fail_open() is False
    assert judge_band() == (0.30, 0.60)

    judge = RetrievalJudge()
    assert judge.model == "judge-from-env"
    assert judge.timeout_seconds == 5
    assert judge.max_tokens == 256


def test_judge_defaults_when_dotenv_absent(monkeypatch):
    from app.adapters.judge.llm import judge_band, judge_enabled, judge_fail_open

    for key in ("CCA_RETRIEVAL_JUDGE", "CCA_RETRIEVAL_JUDGE_LOW", "CCA_RETRIEVAL_JUDGE_HIGH"):
        monkeypatch.delenv(key, raising=False)
    assert judge_enabled() is False
    assert judge_fail_open() is True
    assert judge_band() == (0.45, 0.58)


def test_judge_band_clamps_inverted_values_from_dotenv(monkeypatch, tmp_path):
    from app.adapters.judge.llm import judge_band

    _use_env(monkeypatch, tmp_path, "CCA_RETRIEVAL_JUDGE_LOW=0.70\nCCA_RETRIEVAL_JUDGE_HIGH=0.20\n")
    monkeypatch.delenv("CCA_RETRIEVAL_JUDGE_LOW", raising=False)
    monkeypatch.delenv("CCA_RETRIEVAL_JUDGE_HIGH", raising=False)
    # 配反 → high 抬到 low（"关闭中间带"），不是随机变空
    assert judge_band() == (0.70, 0.70)


def test_embedding_provider_read_from_dotenv(monkeypatch, tmp_path):
    from app.adapters.embedding import registry, remote

    _use_env(
        monkeypatch,
        tmp_path,
        """
        CCA_EMBEDDING_PROVIDER=openai-compatible
        CCA_EMBEDDING_BASE_URL=http://127.0.0.1:8892/v1
        CCA_EMBEDDING_MODEL=Qwen3-Embedding-0.6B
        CCA_EMBEDDING_DIM=1024
        """,
    )
    for key in (
        "CCA_EMBEDDING_PROVIDER",
        "CCA_EMBEDDING_BASE_URL",
        "CCA_EMBEDDING_MODEL",
        "CCA_EMBEDDING_DIM",
    ):
        monkeypatch.delenv(key, raising=False)

    assert registry.provider_kind() == "openai-compatible"
    assert registry.is_remote() is True
    assert registry.current_dim() == 1024
    assert registry.provider_name() == "openai-compatible:qwen3-embedding-0.6b"
    assert remote.base_url() == "http://127.0.0.1:8892/v1"
    assert remote.model_name() == "Qwen3-Embedding-0.6B"


def test_embedding_defaults_stay_deterministic_64(monkeypatch):
    from app.adapters.embedding import registry
    from app.adapters.embedding.deterministic import embedding_dim

    for key in ("CCA_EMBEDDING_PROVIDER", "CCA_EMBEDDING_DIM"):
        monkeypatch.delenv(key, raising=False)
    assert registry.provider_kind() == "deterministic"
    assert registry.current_dim() == 64
    assert embedding_dim() == 64


def test_storage_and_retrieval_keys_read_from_dotenv(monkeypatch, tmp_path):
    from app.adapters.filestore import local as filestore
    from app.adapters.parser import document_parser
    from app.adapters.vector import local as vector_store
    from app.modules.knowledge import adapters as knowledge_adapters

    _use_env(
        monkeypatch,
        tmp_path,
        """
        CCA_VECTOR_SPACE=corpus_dotenv_v2
        CCA_RETRIEVAL_MIN_SCORE=0.55
        CCA_VECTOR_ROOT=D:/dotenv/vector
        CCA_FILESTORE_ROOT=D:/dotenv/files
        CCA_CHUNK_SIZE=200
        CCA_CHUNK_OVERLAP=40
        """,
    )
    for key in (
        "CCA_VECTOR_SPACE",
        "CCA_RETRIEVAL_MIN_SCORE",
        "CCA_VECTOR_ROOT",
        "CCA_FILESTORE_ROOT",
        "CCA_CHUNK_SIZE",
        "CCA_CHUNK_OVERLAP",
    ):
        monkeypatch.delenv(key, raising=False)

    assert knowledge_adapters.corpus_vector_space() == "corpus_dotenv_v2"
    assert knowledge_adapters.retrieval_min_score() == 0.55
    assert document_parser.chunk_size() == 200
    assert document_parser.chunk_overlap() == 40
    assert vector_store.default_root() == Path("D:/dotenv/vector")
    assert filestore.default_root() == Path("D:/dotenv/files")
    # parser_config_digest 覆盖分块参数 + provider/dim，换空间/参数即换摘要
    assert len(document_parser.parser_config_digest()) == 32


def test_settings_uses_same_env_file_entry(monkeypatch, tmp_path):
    """pydantic Settings 与 env_* 共用同一个 .env 入口（CCA_ENV_FILE）。"""
    from app.config import Settings

    path = _use_env(monkeypatch, tmp_path, "CCA_ENV=prod\n")
    # conftest 会显式设置 CCA_ENV=test；这里临时摘掉，验证 Settings 也走同一个 .env 入口
    monkeypatch.delenv("CCA_ENV", raising=False)
    assert app_config.env_file_path() == path
    settings = Settings(_env_file=app_config.env_file_path())
    assert settings.env == "prod"
