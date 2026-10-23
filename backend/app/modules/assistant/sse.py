"""SSE 统一写出器（设计 §8.4；PHASE-03 A7）。

约束：
- **只有本模块分配 seq 并写 socket**；任何业务模块都通过 ``EventChannel.publish`` 提交事件。
- 六类事件 ``status / tool_start / tool_end / token / done / error``；
  data 由 ``contracts`` 中的模型构造，序列化去掉 None（``additionalProperties:false``）。
- 同一连接最多一个终态；runner **先提交持久终态**再 publish ``done/error``。
- 心跳是 SSE 注释（``: ping``），不是业务事件，不占 seq。
- 慢连接：积压超过 ``event_queue_blocks`` 时最多等待 ``backpressure_seconds``；
  仍积压则标记 ``slow``，写出器关闭 HTTP 连接，runner 继续在预算内收尾。
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable

from app.modules.assistant.contracts import sse_dump
from app.modules.assistant.settings import AssistantSettings, get_assistant_settings
from app.shared.clock import isoformat, now_utc

logger = logging.getLogger("cca.assistant.sse")

TERMINAL_EVENTS = frozenset({"done", "error"})
EVENT_NAMES = frozenset({"status", "tool_start", "tool_end", "token", "done", "error"})


@dataclass(frozen=True)
class SseEvent:
    seq: int
    event: str
    data: dict

    def encode(self) -> bytes:
        payload = json.dumps(self.data, ensure_ascii=False, separators=(",", ":"))
        return f"id: {self.seq}\nevent: {self.event}\ndata: {payload}\n\n".encode("utf-8")


def sse_comment(text: str = "ping") -> bytes:
    return f": {text}\n\n".encode("utf-8")


class EventChannel:
    """单个请求的事件缓冲 + 订阅（runner 生产、SSE 写出器消费）。"""

    def __init__(
        self,
        request_id: str,
        *,
        settings: AssistantSettings | None = None,
    ) -> None:
        self.request_id = request_id
        self.settings = settings or get_assistant_settings()
        self._events: list[SseEvent] = []
        self._condition = asyncio.Condition()
        self._seq = 0
        self._cursor = 0
        self._finished = False
        self._terminal_published = False
        self._slow = False

    # ---- 生产侧 ----
    @property
    def seq(self) -> int:
        return self._seq

    @property
    def slow(self) -> bool:
        return self._slow

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def terminal_published(self) -> bool:
        return self._terminal_published

    async def publish(
        self,
        event: str,
        build: Callable[[int, str], object],
    ) -> SseEvent | None:
        """分配 seq 并广播；返回 None 表示通道已关闭（终态之后不再接收）。"""
        if event not in EVENT_NAMES:
            raise ValueError(f"未知 SSE 事件: {event}")
        async with self._condition:
            if self._finished:
                return None
            if event in TERMINAL_EVENTS:
                if self._terminal_published:
                    # 终态唯一：第二次终态直接丢弃（并记录，便于测试发现）
                    logger.warning(
                        "duplicate terminal event dropped request_id=%s event=%s",
                        self.request_id,
                        event,
                    )
                    return None
                self._terminal_published = True

            await self._apply_backpressure_locked()

            self._seq += 1
            seq = self._seq
            timestamp = isoformat(now_utc()) or ""
            model = build(seq, timestamp)
            data = model if isinstance(model, dict) else sse_dump(model)
            event_obj = SseEvent(seq=seq, event=event, data=data)
            if len(self._events) < self.settings.max_buffer_events:
                self._events.append(event_obj)
            else:
                # 缓冲到顶：停止追加（seq 已分配，不产生空洞，连接侧已标记 slow）
                self._slow = True
            if event in TERMINAL_EVENTS:
                self._finished = True
            self._condition.notify_all()
            return event_obj

    async def _apply_backpressure_locked(self) -> None:
        pending = len(self._events) - self._cursor
        if pending < self.settings.event_queue_blocks:
            return
        try:
            await asyncio.wait_for(
                self._condition.wait_for(lambda: len(self._events) - self._cursor < self.settings.event_queue_blocks),
                timeout=self.settings.backpressure_seconds,
            )
        except asyncio.TimeoutError:
            # 慢连接：关闭连接由写出器执行，runner 继续收尾（不无限等待）
            self._slow = True

    # ---- 消费侧 ----
    async def next_event(
        self, cursor: int, *, heartbeat_seconds: float
    ) -> SseEvent | None:
        """等待下一条事件；``None`` = 心跳超时；``_CLOSED`` 语义用 ``closed_and_drained`` 判断。"""
        async with self._condition:
            if cursor < len(self._events):
                return self._events[cursor]
            if self._finished:
                return None
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(
                        lambda: len(self._events) > cursor or self._finished
                    ),
                    timeout=max(heartbeat_seconds, 0.1),
                )
            except asyncio.TimeoutError:
                return None
            if cursor < len(self._events):
                return self._events[cursor]
            return None

    async def advance(self, seq: int) -> None:
        async with self._condition:
            self._cursor = max(self._cursor, seq)
            self._condition.notify_all()

    def closed_and_drained(self, cursor: int) -> bool:
        return self._finished and cursor >= len(self._events)

    async def close(self) -> None:
        """runner 中止（异常路径）也要唤醒写出器，避免连接悬挂。"""
        async with self._condition:
            self._finished = True
            self._condition.notify_all()


async def iter_sse(
    channel: EventChannel,
    *,
    heartbeat_seconds: float | None = None,
) -> AsyncIterator[bytes]:
    """把通道翻译成 SSE 字节流；终态后立即结束，慢连接主动关闭。"""
    interval = heartbeat_seconds if heartbeat_seconds is not None else channel.settings.heartbeat_seconds
    sent = 0
    while True:
        event = await channel.next_event(sent, heartbeat_seconds=interval)
        if event is None:
            if channel.closed_and_drained(sent):
                return
            yield sse_comment()
            continue
        yield event.encode()
        sent = event.seq
        await channel.advance(event.seq)
        if event.event in TERMINAL_EVENTS:
            return
        if channel.slow:
            logger.warning(
                "slow SSE consumer closed request_id=%s seq=%s", channel.request_id, event.seq
            )
            return


async def drain_channel(channel: EventChannel, timeout: float = 5.0) -> list[SseEvent]:
    """测试/诊断用：等待终态并返回全部事件（不经过 socket）。"""
    collected: list[SseEvent] = []
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        async with channel._condition:  # noqa: SLF001 - 测试辅助，契约内自用
            pending = channel._events[len(collected) :]
        for event in pending:
            collected.append(event)
        if channel.closed_and_drained(len(collected)):
            return collected
        if asyncio.get_running_loop().time() > deadline:
            return collected
        await asyncio.sleep(0.01)


__all__ = [
    "EVENT_NAMES",
    "EventChannel",
    "SseEvent",
    "TERMINAL_EVENTS",
    "drain_channel",
    "iter_sse",
    "sse_comment",
]
