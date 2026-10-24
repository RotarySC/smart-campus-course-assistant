"""助手运行时：runner 注册表、事件通道与生命周期（PHASE-03 A5/A6）。

runner 在应用生命周期的独立任务里跑，**不绑定 HTTP 生成器**：连接断开后仍在预算内收尾，
最终状态通过 ``GET /chat/requests/{id}`` 查询。

测试可注入 provider / executor：``set_runtime(Runtime(...))``，用例结束 ``reset_runtime()``。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.adapters.mcp.client import McpToolClient, ToolExecutor
from app.adapters.model.deterministic import DeterministicProvider
from app.adapters.model.gateway import ModelGateway
from app.modules.assistant.accept import AcceptResult, recover_stale_requests
from app.modules.assistant.runner import Runner, RunnerDeps
from app.modules.assistant.settings import AssistantSettings, get_assistant_settings
from app.modules.assistant.sse import EventChannel
from app.shared.context import ActorContext

logger = logging.getLogger("cca.assistant.runtime")


@dataclass
class Runtime:
    settings: AssistantSettings = field(default_factory=get_assistant_settings)
    provider: ModelGateway = field(default_factory=DeterministicProvider)
    executor: ToolExecutor | None = None

    def __post_init__(self) -> None:
        if self.executor is None:
            self.executor = McpToolClient(url=self.settings.mcp_url)
        self._runners: dict[str, Runner] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._channels: dict[str, EventChannel] = {}
        self._recovery_lock = asyncio.Lock()
        self._recovered = False

    # ---- 生命周期 ----
    async def ensure_recovered(self) -> None:
        """首次使用时扫描过期请求（等价于进程启动扫描；不重跑模型）。"""
        async with self._recovery_lock:
            if self._recovered:
                return
            self._recovered = True
            try:
                await recover_stale_requests()
            except Exception:  # noqa: BLE001 - 恢复失败不应阻断新请求
                logger.exception("assistant recovery scan failed")

    # ---- 启动 runner ----
    def start(self, actor: ActorContext, accept: AcceptResult) -> EventChannel:
        channel = EventChannel(accept.request_id, settings=self.settings)
        deps = RunnerDeps(
            provider=self.provider,
            executor=self.executor,  # type: ignore[arg-type]
            settings=self.settings,
        )
        runner = Runner(accept=accept, actor=actor, channel=channel, deps=deps)
        self._runners[accept.request_id] = runner
        self._channels[accept.request_id] = channel
        task = asyncio.create_task(self._run(runner))
        self._tasks[accept.request_id] = task
        task.add_done_callback(lambda _: self._cleanup(accept.request_id))
        return channel

    async def _run(self, runner: Runner) -> None:
        try:
            await runner.run()
        except asyncio.CancelledError:  # pragma: no cover - 关闭路径
            raise
        except Exception:  # noqa: BLE001 - Runner.run 已兜底，这里只记录
            logger.exception("runner task failed request_id=%s", runner.request_id)

    def _cleanup(self, request_id: str) -> None:
        self._tasks.pop(request_id, None)
        # 保留 channel/runners 供订阅方取事件；shutdown/reset 时统一清理
        if len(self._channels) > 256:
            for key in list(self._channels)[:-128]:
                self._channels.pop(key, None)
                self._runners.pop(key, None)

    def channel_of(self, request_id: str) -> EventChannel | None:
        return self._channels.get(request_id)

    def runner_of(self, request_id: str) -> Runner | None:
        return self._runners.get(request_id)

    # ---- 关闭 ----
    async def shutdown(self) -> None:
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    def reset_local_state(self) -> None:
        self._runners.clear()
        self._channels.clear()


_runtime: Runtime | None = None


def get_runtime() -> Runtime:
    global _runtime
    if _runtime is None:
        _runtime = Runtime()
    return _runtime


def set_runtime(runtime: Runtime | None) -> None:
    global _runtime
    _runtime = runtime


async def reset_runtime(*, shutdown: bool = True) -> None:
    global _runtime
    if _runtime is not None:
        if shutdown:
            await _runtime.shutdown()
        _runtime.reset_local_state()
    _runtime = None


__all__ = [
    "Runtime",
    "get_runtime",
    "reset_runtime",
    "set_runtime",
]
