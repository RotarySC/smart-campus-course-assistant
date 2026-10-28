"""TBD-04 骨架：模型配置键、Provider 装配与「配置了就显式失败」的约定。

约定（与 ``backend/.env.example`` 的助手模型小节一一对应）：
- 默认 ``deterministic``：离线、可复现，不是生产 AI；
- ``openai-compatible``：必须同时给出 BASE_URL / API_KEY / NAME，缺一项启动期就报错；
- 配置了真实供应商后**不得**静默回退到确定性 Provider；上游不可用时以
  ``MODEL_UNAVAILABLE`` 显式失败（真实调用见 ``test_model_real_provider.py``）。

用例全部用 ``Settings(_env_file=None)``，不依赖开发者本机 ``backend/.env``。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from pydantic import ValidationError

from app.adapters.model.deterministic import DeterministicProvider
from app.adapters.model.factory import build_model_provider
from app.adapters.model.gateway import Answer, ModelBudget, ModelContext
from app.adapters.model.real import RealProviderAdapter
from app.config import Settings, reset_settings_cache
from app.modules.assistant.runtime import Runtime
from app.shared.errors import ApiError

MODEL_KEYS = (
    "CCA_MODEL_PROVIDER",
    "CCA_MODEL_BASE_URL",
    "CCA_MODEL_API_KEY",
    "CCA_MODEL_NAME",
    "CCA_MODEL_TEMPERATURE",
    "CCA_MODEL_MAX_TOKENS",
    "CCA_MODEL_TIMEOUT_SECONDS",
    "CCA_MODEL_MAX_RETRIES",
)

REAL_ENV = {
    "CCA_MODEL_PROVIDER": "openai-compatible",
    "CCA_MODEL_BASE_URL": "https://api.example.com/v1",
    "CCA_MODEL_API_KEY": "sk-test-not-a-real-key",
    "CCA_MODEL_NAME": "deepseek-chat",
}


@pytest.fixture(autouse=True)
def fresh_settings(monkeypatch):
    """每个用例都从干净的模型配置起步（清缓存 + 清掉外部残留的 CCA_MODEL_*）。

    同时屏蔽开发者本机 ``backend/.env``：接真实供应商时该文件会写入
    ``CCA_MODEL_PROVIDER=openai-compatible`` 等真实配置，本文件只验证「配置 → 装配 →
    错误映射」，不能随本机 .env 漂移（与文件头"不依赖开发者本机 backend/.env"一致）。
    """
    for key in MODEL_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    reset_settings_cache()
    yield
    reset_settings_cache()


def _context() -> ModelContext:
    return ModelContext(
        request_id="req_model_cfg",
        conversation_id="cnv_model_cfg",
        message="明天有什么课",
        history=(),
        accepted_at=datetime(2026, 10, 23, 15, 30, tzinfo=timezone.utc),
        school_timezone="Asia/Shanghai",
        today=date(2026, 10, 23),
        tomorrow=date(2026, 10, 24),
    )


def _budget() -> ModelBudget:
    # 相对当下给 60s：真实 Provider 会先查预算，固定的历史时刻会被判 EXECUTION_TIMEOUT，
    # 而本组用例只验证「配置/装配/错误映射」，不验证预算语义（预算用例在
    # test_model_real_provider.py）。
    return ModelBudget(
        remaining_decisions=6,
        remaining_tools=10,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=60),
    )


# --------------------------------------------------------------------------- #
# 默认值
# --------------------------------------------------------------------------- #
def test_defaults_are_deterministic_and_offline():
    cfg = Settings(_env_file=None)

    assert cfg.model_provider == "deterministic"
    assert cfg.model_configured is False
    assert cfg.model_base_url == ""
    assert cfg.model_api_key == ""
    assert cfg.model_name == ""
    # 默认采样/预算参数（与 .env.example 注释一致）
    assert cfg.model_temperature == 0.3
    assert cfg.model_max_tokens == 2048
    assert cfg.model_timeout_seconds == 30.0
    assert cfg.model_max_retries == 1

    assert isinstance(build_model_provider(cfg), DeterministicProvider)


# --------------------------------------------------------------------------- #
# 环境变量 → Settings → Provider
# --------------------------------------------------------------------------- #
def test_env_selects_openai_compatible(monkeypatch):
    for key, value in REAL_ENV.items():
        monkeypatch.setenv(key, value)

    cfg = Settings(_env_file=None)
    assert cfg.model_configured is True

    provider = build_model_provider(cfg)
    assert isinstance(provider, RealProviderAdapter)
    assert provider.configured is True

    desc = provider.describe()
    assert desc["endpoint"] == "https://api.example.com/v1"
    assert desc["model"] == "deepseek-chat"
    assert desc["api_key_configured"] is True
    assert desc["implemented"] is True


def test_runtime_uses_configured_provider(monkeypatch):
    """装配点：Runtime 默认 provider 由 CCA_MODEL_* 决定（配置了就是真实适配位）。"""
    for key, value in REAL_ENV.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    provider = Runtime().provider
    assert isinstance(provider, RealProviderAdapter)
    assert provider.model == "deepseek-chat"


def test_runtime_defaults_to_deterministic():
    assert isinstance(Runtime().provider, DeterministicProvider)


# --------------------------------------------------------------------------- #
# 配置错误在启动期就失败
# --------------------------------------------------------------------------- #
def test_missing_keys_fail_fast(monkeypatch):
    monkeypatch.setenv("CCA_MODEL_PROVIDER", "openai-compatible")

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)

    message = str(exc.value)
    for key in ("CCA_MODEL_BASE_URL", "CCA_MODEL_API_KEY", "CCA_MODEL_NAME"):
        assert key in message


def test_base_url_must_be_http(monkeypatch):
    monkeypatch.setenv("CCA_MODEL_PROVIDER", "openai-compatible")
    monkeypatch.setenv("CCA_MODEL_BASE_URL", "api.example.com/v1")
    monkeypatch.setenv("CCA_MODEL_API_KEY", "sk-test")
    monkeypatch.setenv("CCA_MODEL_NAME", "deepseek-chat")

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)

    assert "http" in str(exc.value)


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setenv("CCA_MODEL_PROVIDER", "openai")  # 少了 -compatible

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)

    assert "CCA_MODEL_PROVIDER" in str(exc.value)


def test_temperature_out_of_range(monkeypatch):
    monkeypatch.setenv("CCA_MODEL_TEMPERATURE", "3")

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)

    assert "CCA_MODEL_TEMPERATURE" in str(exc.value)


# --------------------------------------------------------------------------- #
# 已配置但上游拒绝/不可用：显式 MODEL_UNAVAILABLE（不静默回退）
# --------------------------------------------------------------------------- #
def _upstream_unauthorized(calls: dict[str, int] | None = None):
    """伪装上游 401：断言适配器真的发起了 HTTP 调用，并把它映射成稳定错误码。"""

    async def handle(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls["n"] += 1
        return httpx.Response(401, json={"error": "invalid api key"})

    return handle


async def test_configured_provider_raises_model_unavailable():
    calls = {"n": 0}
    provider = RealProviderAdapter(
        endpoint="https://api.example.com/v1",
        api_key="sk-test-not-a-real-key",
        model="deepseek-chat",
        transport=httpx.MockTransport(_upstream_unauthorized(calls)),
    )

    with pytest.raises(ApiError) as action_error:
        await provider.next_action(_context(), _budget())
    assert action_error.value.code == "MODEL_UNAVAILABLE"
    assert action_error.value.status_code == 503
    assert action_error.value.message == "模型服务暂不可用"
    assert calls["n"] == 1, "4xx 不重试：应恰好一次上游调用"

    emitted: list[str] = []

    async def _emit(delta: str) -> None:  # pragma: no cover - 401 不应输出正文
        emitted.append(delta)

    with pytest.raises(ApiError) as stream_error:
        await provider.stream_answer(Answer(text="x"), _emit)
    assert stream_error.value.code == "MODEL_UNAVAILABLE"
    assert emitted == []


def test_describe_never_leaks_api_key():
    provider = RealProviderAdapter(
        endpoint="https://api.example.com/v1",
        api_key="sk-secret-value",
        model="deepseek-chat",
    )

    desc = provider.describe()
    assert "sk-secret-value" not in repr(desc)
    assert desc["api_key_configured"] is True


# --------------------------------------------------------------------------- #
# 端到端：配置了真实供应商，SSE 终态必须是 MODEL_UNAVAILABLE（不静默回退）
# --------------------------------------------------------------------------- #
async def test_configured_model_fails_loudly_through_sse(client, seeded):
    from app.modules.assistant.runtime import set_runtime
    from tests.assistant_support import (  # noqa: F401 - autouse 隔离夹具
        StubToolExecutor,
        assistant_isolation,
        parse_sse,
        validate_sse_events,
    )

    provider = RealProviderAdapter(
        endpoint="https://api.example.com/v1",
        api_key="sk-test-not-a-real-key",
        model="deepseek-chat",
        transport=httpx.MockTransport(_upstream_unauthorized()),
    )
    set_runtime(Runtime(provider=provider, executor=StubToolExecutor()))
    try:
        async with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"client_request_id": "creq_model_unavailable", "message": "明天有什么课"},
            headers={"Authorization": f"Bearer {seeded['student_token']}"},
        ) as response:
            assert response.status_code == 200
            raw = (await response.aread()).decode("utf-8")
    finally:
        set_runtime(None)

    events = parse_sse(raw)
    validate_sse_events(events)
    terminal = events[-1]
    assert terminal["event"] == "error"
    assert terminal["data"]["state"] == "failed"
    assert terminal["data"]["code"] == "MODEL_UNAVAILABLE"
    # 静默回退的反证：正文一个字都没流出去
    assert [event for event in events if event["event"] == "token"] == []
