"""Runner：预算、调度、终态与 fence（设计 §8.2–§8.3；PHASE-03 A6/A7）。

生命周期：``accepted → running → succeeded | failed | cancelled``。

硬约束：
- 预算：**先检查后分配**；6 次模型决策、10 次工具、接受后 60s（时钟可注入）。
- 终态更新条件 ``state IN ('accepted','running') AND fence=:fence``，恰好一个更新者。
- 终态**先持久化再发 done/error**；连接断开不回滚状态。
- 租约 30s、每 10s 续租；续租失败（fence 被回收）→ 旧 runner 在下一个边界退出。
- 取消：在可中止边界检查持久 ``cancel_requested``；已提交的保存不可撤回。
- 依赖状态：``satisfied/empty/failed/ambiguous``；必需依据未满足时**不得自动保存**。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, text, update

from app.adapters.db.models import ChatRequest
from app.adapters.db.uow import uow
from app.adapters.mcp.client import ToolExecutor
from app.adapters.model.gateway import (
    Answer,
    DraftIntent,
    DraftRecord,
    EvidenceSet,
    ModelAction,
    ModelBudget,
    ModelContext,
    ModelGateway,
    SaveRecord,
    ToolCall,
    ToolExecutionRecord,
)
from app.config import get_settings
from app.modules.assistant.contracts import (
    TOOL_DISPLAY_NAMES,
    DoneData,
    ErrorData,
    StatusData,
    TokenData,
    ToolEndData,
    ToolStartData,
    validate_tool_call,
)
from app.modules.assistant.drafts import (
    classify_direct_instruction,
    create_turn_draft,
)
from app.modules.assistant.settings import AssistantSettings, get_assistant_settings
from app.modules.assistant.sse import EventChannel
from app.modules.operations.service import append_outbox
from app.shared.clock import now_utc, school_date, to_db
from app.shared.context import ActorContext, ExecutionContext
from app.shared.errors import ERROR_MESSAGE, ApiError
from app.shared.ids import PREFIX_REQUEST, new_id

logger = logging.getLogger("cca.assistant.runner")

# provider 只能请求这两类只读工具；保存工具由 runner 依据服务端许可编排调用
PROVIDER_TOOL_WHITELIST = frozenset({"get_my_schedule", "search_course_docs"})
AUTH_ERROR_CODES = frozenset({"AUTH_REQUIRED", "SESSION_EXPIRED"})
MODEL_TOOL_NAME = "save_study_plan"
SEARCH_TOOL_NAME = "search_course_docs"


@dataclass
class RunnerDeps:
    provider: ModelGateway
    executor: ToolExecutor
    settings: AssistantSettings = field(default_factory=get_assistant_settings)


@dataclass
class RunnerState:
    decisions: int = 0
    tools: int = 0
    records: list[ToolExecutionRecord] = field(default_factory=list)
    evidence: list[EvidenceSet] = field(default_factory=list)
    draft: DraftRecord | None = None
    save: SaveRecord | None = None
    answer_text: str = ""
    save_succeeded: bool = False


class Runner:
    def __init__(
        self,
        *,
        accept: Any,
        actor: ActorContext,
        channel: EventChannel,
        deps: RunnerDeps,
    ) -> None:
        self.accept = accept
        self.actor = actor
        self.channel = channel
        self.deps = deps
        self.settings = deps.settings
        self.request_id: str = accept.request_id
        self.conversation_id: str = accept.conversation_id
        self.fence: int = accept.fence
        self.accepted_at: datetime = accept.accepted_at
        self.deadline_at: datetime = accept.deadline_at
        self.exec_ctx = ExecutionContext(
            actor=actor,
            chat_request_id=self.request_id,
            conversation_id=self.conversation_id,
            accepted_at=self.accepted_at,
            school_timezone=get_settings().school_timezone,
            deadline_at=self.deadline_at,
            execution_fence=self.fence,
        )
        self.state = RunnerState()
        self._lost = False
        self._renew_task: asyncio.Task[None] | None = None
        self._state_machine_started = False
        self._terminal_done = False

    # ------------------------------------------------------------------ #
    # 入口
    # ------------------------------------------------------------------ #
    async def run(self) -> None:
        try:
            await self._run()
        except asyncio.CancelledError:
            logger.info("runner cancelled request_id=%s", self.request_id)
            await self._terminal(
                "failed", reason="SERVICE_RESTARTED", code="INTERNAL_ERROR", publish_error=True
            )
            raise
        except Exception:  # noqa: BLE001 - runner 兜底：任何异常都必须收敛终态
            logger.exception("runner crashed request_id=%s", self.request_id)
            await self._terminal(
                "failed", reason="INTERNAL_ERROR", code="INTERNAL_ERROR", publish_error=True
            )
        finally:
            if self._renew_task is not None:
                self._renew_task.cancel()
            await self.channel.close()

    async def _run(self) -> None:
        # seq=1：首个 status 必须含 conversation_id（§8.4）
        await self.channel.publish(
            "status",
            lambda seq, ts: StatusData(
                request_id=self.request_id,
                seq=seq,
                timestamp=ts,
                code="ACCEPTED",
                message="已接受请求，正在准备执行",
                conversation_id=self.conversation_id,
            ),
        )
        if self.accept.context_truncated:
            await self.channel.publish(
                "status",
                lambda seq, ts: StatusData(
                    request_id=self.request_id,
                    seq=seq,
                    timestamp=ts,
                    code="CONTEXT_TRUNCATED",
                    message="历史对话超出预算，已仅保留最近的完整问答对",
                ),
            )

        claimed = await self._claim()
        if not claimed:
            logger.warning("runner lost claim before start request_id=%s", self.request_id)
            return
        await self.channel.publish(
            "status",
            lambda seq, ts: StatusData(
                request_id=self.request_id,
                seq=seq,
                timestamp=ts,
                code="RUNNING",
                message="正在生成回答",
            ),
        )
        self._renew_task = asyncio.create_task(self._renew_loop())

        while True:
            context = self._build_context()
            boundary = await self._check_boundary()
            if boundary is not None:
                state, reason, code = boundary
                await self._terminal(state, reason=reason, code=code, publish_error=state == "failed")
                return

            budget = ModelBudget(
                remaining_decisions=max(self.settings.model_decision_limit - self.state.decisions, 0),
                remaining_tools=max(self.settings.tool_call_limit - self.state.tools, 0),
                deadline_at=self.deadline_at,
            )
            if budget.remaining_decisions <= 0:
                await self._terminal(
                    "failed",
                    reason="CALL_LIMIT_REACHED",
                    code="CALL_LIMIT_REACHED",
                    publish_error=True,
                )
                return

            await self._count_decision()
            try:
                action: ModelAction = await self.deps.provider.next_action(context, budget)
            except ApiError as exc:
                await self._terminal(
                    "failed", reason=exc.code, code=exc.code, publish_error=True
                )
                return
            except Exception:  # noqa: BLE001 - 模型适配器异常统一 MODEL_UNAVAILABLE
                logger.exception("model gateway failed request_id=%s", self.request_id)
                await self._terminal(
                    "failed",
                    reason="MODEL_UNAVAILABLE",
                    code="MODEL_UNAVAILABLE",
                    publish_error=True,
                )
                return

            if isinstance(action, ToolCall):
                await self._run_tool_action(action)
                if self._terminal_done:
                    return
                continue
            if isinstance(action, DraftIntent):
                await self._run_draft_action(action)
                if self._terminal_done:
                    return
                continue
            if isinstance(action, Answer):
                await self._run_answer_action(action)
                return
            # 未知动作类型：按内部错误收敛
            await self._terminal(
                "failed", reason="INTERNAL_ERROR", code="INTERNAL_ERROR", publish_error=True
            )
            return

    # ------------------------------------------------------------------ #
    # 上下文 / 状态机
    # ------------------------------------------------------------------ #
    def _build_context(self) -> ModelContext:
        today = school_date(self.accepted_at)
        return ModelContext(
            request_id=self.request_id,
            conversation_id=self.conversation_id,
            message=self.accept.message,
            history=tuple(self.accept.history),
            accepted_at=self.accepted_at,
            school_timezone=self.exec_ctx.school_timezone,
            today=today,
            tomorrow=today + timedelta(days=1),
            tool_results=self.state.records,
            draft=self.state.draft,
            save=self.state.save,
        )

    async def _claim(self) -> bool:
        async with uow() as tx:
            result = await tx.session.execute(
                update(ChatRequest)
                .where(
                    ChatRequest.id == self.request_id,
                    ChatRequest.fence == self.fence,
                    ChatRequest.state == "accepted",
                )
                .values(
                    state="running",
                    owner_instance=self.settings.instance_id,
                    lease_until=to_db(now_utc() + timedelta(seconds=self.settings.lease_seconds)),
                )
            )
            await tx.commit()
        self._state_machine_started = result.rowcount == 1
        return self._state_machine_started

    async def _renew_loop(self) -> None:
        interval = max(self.settings.lease_renew_seconds, 1)
        try:
            while not self._lost:
                await asyncio.sleep(interval)
                renewed = await self._renew_once()
                if not renewed:
                    logger.warning("lease lost request_id=%s", self.request_id)
                    self._lost = True
                    return
        except asyncio.CancelledError:  # pragma: no cover - 正常关闭路径
            return

    async def _renew_once(self) -> bool:
        async with uow() as tx:
            result = await tx.session.execute(
                update(ChatRequest)
                .where(
                    ChatRequest.id == self.request_id,
                    ChatRequest.fence == self.fence,
                    ChatRequest.state == "running",
                )
                .values(
                    lease_until=to_db(now_utc() + timedelta(seconds=self.settings.lease_seconds))
                )
            )
            await tx.commit()
        return result.rowcount == 1

    async def _check_boundary(self) -> tuple[str, str, str] | None:
        """可中止边界：丢失执行权 / 取消 / 截止 / 预算。返回 (state, reason, code)。"""
        if self._lost:
            return ("failed", "EXECUTION_LOST", "INTERNAL_ERROR")
        row = await self._read_request()
        if row is None:
            return ("failed", "INTERNAL_ERROR", "INTERNAL_ERROR")
        if row.fence != self.fence or row.state not in ("accepted", "running"):
            # fence 被回收或已被他人终结：不再提交终态
            self._lost = True
            return ("failed", "EXECUTION_LOST", "INTERNAL_ERROR")
        if row.cancel_requested:
            if self.state.save_succeeded:
                # 已提交保存不可撤回（§5.3）：以成功收尾并说明
                return ("succeeded", "CANCELLED_AFTER_SAVE", "")
            return ("cancelled", "USER_CANCELLED", "")
        if now_utc() >= self.deadline_at:
            return ("failed", "EXECUTION_TIMEOUT", "EXECUTION_TIMEOUT")
        return None

    async def _read_request(self) -> ChatRequest | None:
        async with uow() as tx:
            result = await tx.session.execute(
                select(ChatRequest).where(ChatRequest.id == self.request_id)
            )
            return result.scalar_one_or_none()

    async def _count_decision(self) -> None:
        self.state.decisions += 1
        async with uow() as tx:
            await tx.session.execute(
                update(ChatRequest)
                .where(
                    ChatRequest.id == self.request_id,
                    ChatRequest.fence == self.fence,
                )
                .values(model_calls=ChatRequest.model_calls + 1)
            )
            await tx.commit()

    async def _count_tool(self) -> None:
        self.state.tools += 1
        async with uow() as tx:
            await tx.session.execute(
                update(ChatRequest)
                .where(
                    ChatRequest.id == self.request_id,
                    ChatRequest.fence == self.fence,
                )
                .values(tool_calls=ChatRequest.tool_calls + 1)
            )
            await tx.commit()

    # ------------------------------------------------------------------ #
    # 动作
    # ------------------------------------------------------------------ #
    async def _run_tool_action(self, call: ToolCall) -> None:
        if call.tool_name not in PROVIDER_TOOL_WHITELIST:
            # 白名单外的工具请求（含由模型自行发起的保存）一律拒绝执行
            record = _failed_record(call, "FORBIDDEN", "工具不在模型可调度白名单内")
            self.state.records.append(record)
            await self._publish_tool_pair(call, record, tool_call_id=self._new_tool_call_id())
            return
        try:
            arguments = validate_tool_call(call.tool_name, call.arguments)
        except ApiError as exc:
            record = _failed_record(call, exc.code, exc.message)
            self.state.records.append(record)
            await self._publish_tool_pair(call, record, tool_call_id=self._new_tool_call_id())
            return

        if self.state.tools >= self.settings.tool_call_limit:
            await self._terminal(
                "failed",
                reason="CALL_LIMIT_REACHED",
                code="CALL_LIMIT_REACHED",
                publish_error=True,
            )
            return

        safe_call = ToolCall(tool_name=call.tool_name, arguments=arguments)
        tool_call_id = self._new_tool_call_id()
        await self.channel.publish(
            "tool_start",
            lambda seq, ts: ToolStartData(
                request_id=self.request_id,
                seq=seq,
                timestamp=ts,
                tool_call_id=tool_call_id,
                tool_name=safe_call.tool_name,
                display_name=TOOL_DISPLAY_NAMES[safe_call.tool_name],
            ),
        )
        await self._count_tool()
        record = await self.deps.executor.execute(safe_call, self.exec_ctx)
        self.state.records.append(record)
        if record.tool_name == "search_course_docs":
            evidence = record.payload.get("_evidence")
            if isinstance(evidence, EvidenceSet):
                self.state.evidence.append(evidence)
        await self._publish_tool_end(record, tool_call_id)

        if not record.success and record.code in AUTH_ERROR_CODES:
            await self._terminal(
                "failed", reason=record.code, code=record.code, publish_error=True
            )

    async def _run_draft_action(self, intent: DraftIntent) -> None:
        try:
            references = self._evidence_references_payload()
            draft = await create_turn_draft(self.exec_ctx, intent, references=references)
        except ApiError as exc:
            await self._terminal(
                "failed", reason=exc.code, code=exc.code, publish_error=True
            )
            return
        self.state.draft = draft
        await self.channel.publish(
            "status",
            lambda seq, ts: StatusData(
                request_id=self.request_id,
                seq=seq,
                timestamp=ts,
                code="DRAFT_READY",
                message="已生成学习计划草稿（尚未保存）",
                draft_id=draft.draft_id,
                draft_version=draft.draft_version,
            ),
        )
        # 保存：模型候选 + 服务端按 §7.1 规则判定 + 必需依据全部 satisfied
        decision = classify_direct_instruction(self.accept.message, draft_ready=True)
        if not intent.save_candidate or decision != "explicit":
            if decision in ("ambiguous", "denied"):
                await self.channel.publish(
                    "status",
                    lambda seq, ts: StatusData(
                        request_id=self.request_id,
                        seq=seq,
                        timestamp=ts,
                        code="SAVE_NOT_AUTHORIZED",
                        message="未能确定你的保存意图，草稿已保留，可使用保存按钮",
                    ),
                )
            return
        if not self._required_dependencies_satisfied():
            await self.channel.publish(
                "status",
                lambda seq, ts: StatusData(
                    request_id=self.request_id,
                    seq=seq,
                    timestamp=ts,
                    code="BASIS_INCOMPLETE",
                    message="必需依据尚未取得，暂不自动保存",
                ),
            )
            return
        await self._run_save_tool(draft)

    def _required_dependencies_satisfied(self) -> bool:
        """必需依据（课表/资料）非 satisfied 时阻断自动保存（FR-CHAT-006）。"""
        for record in self.state.records:
            if record.tool_name in ("get_my_schedule", "search_course_docs"):
                if record.dependency_state == "failed":
                    return False
        return True

    async def _run_save_tool(self, draft: DraftRecord) -> None:
        if self.state.tools >= self.settings.tool_call_limit:
            await self._terminal(
                "failed",
                reason="CALL_LIMIT_REACHED",
                code="CALL_LIMIT_REACHED",
                publish_error=True,
            )
            return
        call = ToolCall(
            tool_name=MODEL_TOOL_NAME,
            arguments={"draft_id": draft.draft_id, "draft_version": draft.draft_version},
        )
        tool_call_id = self._new_tool_call_id()
        await self.channel.publish(
            "tool_start",
            lambda seq, ts: ToolStartData(
                request_id=self.request_id,
                seq=seq,
                timestamp=ts,
                tool_call_id=tool_call_id,
                tool_name=MODEL_TOOL_NAME,
                display_name=TOOL_DISPLAY_NAMES[MODEL_TOOL_NAME],
            ),
        )
        await self._count_tool()
        record = await self.deps.executor.execute(call, self.exec_ctx)
        self.state.records.append(record)
        if record.success and record.result_status in ("created", "existing"):
            plan_id = str(record.payload.get("plan_id") or "")
            operation_id = str(record.payload.get("operation_id") or "")
            if plan_id and operation_id:
                self.state.save = SaveRecord(
                    plan_id=plan_id,
                    operation_id=operation_id,
                    status=record.result_status,  # type: ignore[arg-type]
                )
                self.state.save_succeeded = True
        await self._publish_tool_end(record, tool_call_id)
        if not record.success and record.code in AUTH_ERROR_CODES:
            await self._terminal(
                "failed", reason=record.code, code=record.code, publish_error=True
            )

    async def _run_answer_action(self, answer: Answer) -> None:
        text_value = answer.text[: self.settings.max_text_length]
        block_id = new_id(PREFIX_REQUEST)
        emitted = False
        pending: list[str] = []

        async def _flush() -> None:
            nonlocal emitted
            if not pending:
                return
            delta = "".join(pending)
            pending.clear()
            if not delta:
                return
            emitted = True
            await self.channel.publish(
                "token",
                lambda seq, ts, delta=delta: TokenData(
                    request_id=self.request_id,
                    seq=seq,
                    timestamp=ts,
                    text_delta=delta[: self.settings.token_chunk_limit],
                    answer_block_id=block_id,
                ),
            )

        async def emit(delta: str) -> None:
            if not delta:
                return
            pending.append(delta)
            if sum(len(item) for item in pending) >= 64:
                await _flush()

        await self.deps.provider.stream_answer(Answer(text=text_value), emit)
        await _flush()
        if not emitted:
            # 空答案也要有一条可见正文，避免前端空白
            await self.channel.publish(
                "token",
                lambda seq, ts: TokenData(
                    request_id=self.request_id,
                    seq=seq,
                    timestamp=ts,
                    text_delta="（没有可展示的内容）",
                    answer_block_id=block_id,
                ),
            )
        self.state.answer_text = text_value
        await self._terminal("succeeded", reason="OK", code="", publish_error=False)

    # ------------------------------------------------------------------ #
    # 终态
    # ------------------------------------------------------------------ #
    async def _terminal(
        self,
        state: str,
        *,
        reason: str,
        code: str,
        publish_error: bool,
    ) -> None:
        if self._terminal_done:
            return
        self._terminal_done = True
        if state == "failed" and reason == "EXECUTION_LOST":
            # 已被回收：不写终态、不发事件（HTTP 连接由 channel.close 收敛）
            return

        persisted = await self._persist_terminal(state, reason=reason)
        if not persisted:
            return

        citations = self._citations_payload()
        plan_id = self.state.save.plan_id if self.state.save else None
        operation_id = self.state.save.operation_id if self.state.save else None
        if state == "failed":
            error_code = code or "INTERNAL_ERROR"
            message = ERROR_MESSAGE.get(error_code, ERROR_MESSAGE["INTERNAL_ERROR"])
            include_refs = error_code not in AUTH_ERROR_CODES
            await self.channel.publish(
                "error",
                lambda seq, ts: ErrorData(
                    request_id=self.request_id,
                    seq=seq,
                    timestamp=ts,
                    state="failed",
                    code=error_code,
                    message=message[:500],
                    plan_id=plan_id if include_refs else None,
                    operation_id=operation_id if include_refs and operation_id else None,
                ),
            )
            return
        done_reason = None if reason in ("", "OK") else reason
        await self.channel.publish(
            "done",
            lambda seq, ts: DoneData(
                request_id=self.request_id,
                seq=seq,
                timestamp=ts,
                state=state,  # type: ignore[arg-type]
                reason=done_reason,
                citations=citations,
                plan_id=plan_id,
                operation_id=operation_id,
            ),
        )

    async def _persist_terminal(self, state: str, *, reason: str) -> bool:
        """终态恰好一次：条件更新命中者才发事件。"""
        now = to_db(now_utc())
        terminal_reason = (reason or "OK")[:64]
        try:
            async with uow() as tx:
                result = await tx.session.execute(
                    update(ChatRequest)
                    .where(
                        ChatRequest.id == self.request_id,
                        ChatRequest.fence == self.fence,
                        ChatRequest.state.in_(("accepted", "running")),
                    )
                    .values(
                        state=state,
                        finished_at=now,
                        terminal_reason=terminal_reason,
                        lease_until=None,
                    )
                )
                if result.rowcount != 1:
                    await tx.rollback()
                    return False
                await tx.session.execute(
                    text(
                        "UPDATE ai_capacity_slots SET request_id = NULL, owner_instance = NULL, "
                        "lease_until = NULL WHERE request_id = :rid"
                    ),
                    {"rid": self.request_id},
                )
                await tx.session.execute(
                    text(
                        "UPDATE conversation_states SET active_request_id = NULL, updated_at = :now "
                        "WHERE id = :cid AND active_request_id = :rid"
                    ),
                    {"cid": self.conversation_id, "rid": self.request_id, "now": now},
                )
                append_outbox(
                    tx,
                    event_type="chat_finished" if state != "failed" else "chat_failed",
                    aggregate_id=self.request_id,
                    request_id=self.request_id,
                    metadata={
                        "state": state,
                        "reason": terminal_reason,
                        "model_calls": self.state.decisions,
                        "tool_calls": self.state.tools,
                        "plan_id": self.state.save.plan_id if self.state.save else None,
                    },
                )
                await tx.commit()
        except Exception:  # noqa: BLE001 - 终态写失败不能伪装成功，但仍需释放连接
            logger.exception("persist terminal failed request_id=%s", self.request_id)
            await self.channel.close()
            return False
        return True

    # ------------------------------------------------------------------ #
    # 事件辅助
    # ------------------------------------------------------------------ #
    def _new_tool_call_id(self) -> str:
        return f"call_{new_id(PREFIX_REQUEST)[4:]}"

    async def _publish_tool_pair(
        self, call: ToolCall, record: ToolExecutionRecord, *, tool_call_id: str
    ) -> None:
        await self.channel.publish(
            "tool_start",
            lambda seq, ts: ToolStartData(
                request_id=self.request_id,
                seq=seq,
                timestamp=ts,
                tool_call_id=tool_call_id,
                tool_name=call.tool_name,  # type: ignore[arg-type]
                display_name=TOOL_DISPLAY_NAMES.get(call.tool_name, call.tool_name),
            ),
        )
        await self._publish_tool_end(record, tool_call_id)

    async def _publish_tool_end(
        self, record: ToolExecutionRecord, tool_call_id: str
    ) -> None:
        plan_id = None
        operation_id = None
        corpus_empty = None
        if record.tool_name == MODEL_TOOL_NAME and record.success:
            plan_id = record.payload.get("plan_id")
            operation_id = record.payload.get("operation_id")
        if record.tool_name == SEARCH_TOOL_NAME and record.success:
            # 全库为空 ≠ 本次没检索到：前者要告诉用户「找管理员」，后者提示「换个问法」。
            evidence = record.payload.get("_evidence")
            if isinstance(evidence, EvidenceSet):
                corpus_empty = bool(evidence.corpus_empty)
            else:
                corpus_empty = bool(record.payload.get("corpus_empty", False))
        await self.channel.publish(
            "tool_end",
            lambda seq, ts: ToolEndData(
                request_id=self.request_id,
                seq=seq,
                timestamp=ts,
                tool_call_id=tool_call_id,
                success=bool(record.success),
                result_status=record.result_status,  # type: ignore[arg-type]
                code=record.code,
                plan_id=plan_id,
                operation_id=operation_id,
                corpus_empty=corpus_empty,
            ),
        )

    def _evidence_references_payload(self) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for evidence in self.state.evidence:
            for reference in evidence.references:
                seen.setdefault(reference.reference_id, reference.as_public_dict())
        return list(seen.values())

    def _citations_payload(self) -> list[Any]:
        from app.modules.assistant.contracts import ReferenceOut

        citations: list[ReferenceOut] = []
        for item in self._evidence_references_payload():
            if item.get("file_name") and item.get("location_label"):
                citations.append(ReferenceOut(**item))
        return citations


def _failed_record(call: ToolCall, code: str, message: str) -> ToolExecutionRecord:
    return ToolExecutionRecord(
        tool_name=call.tool_name,
        arguments=call.arguments,
        success=False,
        result_status="failed",
        dependency_state="failed",
        code=code,
        payload={"code": code, "message": message},
    )


__all__ = [
    "AUTH_ERROR_CODES",
    "PROVIDER_TOOL_WHITELIST",
    "Runner",
    "RunnerDeps",
    "RunnerState",
]
