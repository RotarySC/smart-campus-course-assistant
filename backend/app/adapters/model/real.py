"""真实模型 Adapter：OpenAI 兼容 ``POST {endpoint}/chat/completions``（TBD-04 落地形态）。

不绑定厂商：只要兼容 ``chat/completions`` 且支持 ``tools`` / tool_calls 即可
（OpenAI、DeepSeek、Qwen、vLLM、Ollama ``/v1`` 等都走这一条路径）。

配置来自 ``app.config.Settings`` 的 ``CCA_MODEL_*``（见 ``backend/.env.example``）；
``factory.build_model_provider`` 在 ``CCA_MODEL_PROVIDER=openai-compatible`` 时构造本类。
**不做静默回退**：配置了真实供应商就只会走真实供应商，失败即 ``MODEL_UNAVAILABLE``。

不变量（见 ``gateway.py`` 顶部与 SRS §6.9 / IF-009）：
1. **身份不外泄**：发给模型的 messages 只含 system 角色约束、受控历史、当前问题与
   服务端工具结果；``ModelContext`` 的 request/conversation 标识也不发送，密钥只进
   ``Authorization`` 头，永不进 prompt、日志或错误 message。
2. **工具白名单**：按本轮意图只暴露必要工具（课表→``get_my_schedule``、资料→
   ``search_course_docs``、计划→``draft_study_plan``）。前两个参数 shape 直接取自
   ``modules.assistant.contracts`` 的输入模型（单一真源）；``draft_study_plan`` 是
   **Provider 内部的结构化草稿通道**（不经过 MCP、不产生 tool 事件），``save_study_plan``
   由 runner 依据服务端许可编排，不暴露给模型。非暴露工具、坏参数一律 ``MODEL_UNAVAILABLE``。
3. **错误映射**：4xx / 坏 JSON / 结构不符 → ``MODEL_UNAVAILABLE``；网络错误、超时、5xx
   按 ``max_retries`` 有界重试（指数退避），耗尽后 ``MODEL_UNAVAILABLE``。日志只记状态码、
   异常类型与工具名，不记请求体、响应正文或密钥。
4. **预算**：每次决策前检查 ``ModelBudget``——决策数耗尽 → ``CALL_LIMIT_REACHED``，
   已过 ``deadline_at`` → ``EXECUTION_TIMEOUT``；重试只影响本次调用耗时，不额外扣决策数。
5. **可核验输出（AT-32 首跑修复）**：
   - 日期一律 ISO（``YYYY-MM-DD``）：system 给出今天/明天的 ISO 锚点，并对
     ``get_my_schedule`` 的真实结果做窄后处理——缺字段时追加「课表核对」清单，
     空结果追加固定句式「YYYY-MM-DD 没有课。」，保证答案可被逐项核验；
   - 计划问题产出 ``DraftIntent``（草稿 ≠ 已保存）：只有用户本轮明确指令才把
     ``save_candidate`` 置真（与 ``drafts.classify_direct_instruction`` 同一判定），
     保存许可仍由 runner/服务端签发；模型不得自称已保存；
   - 后处理统一收口草稿/保存措辞（未保存必须说「尚未保存」，已保存必须说
     「已按你的明确要求保存」），并剥掉正文里任何 ``cit_*`` 引用 ID（引用只来自服务端）。
6. **兜底**：模型该调工具却直接作答时，Server 按同一套意图规则补一次只读工具调度；
   计划问题若模型只给正文，则把该正文当作草稿内容转成 ``DraftIntent``，不让计划请求
   退化成"只聊不落草稿"。

本期已知边界：并行 tool_calls 只取第一条；不支持多模态 content；``stream_answer`` 为
"已定稿正文的流式渲染"（不复用决策请求的连接，见该方法注释）；一次计划请求最多产出一份
来源草稿（与 runner 的 ``create_turn_draft`` 语义一致）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, timezone
from typing import Any

import httpx

from app.adapters.model.deterministic import (
    schedule_range,
    wants_documents,
    wants_plan,
    wants_schedule,
)
from app.adapters.model.gateway import (
    Answer,
    DraftIntent,
    EmitToken,
    ModelAction,
    ModelBudget,
    ModelContext,
    ToolCall,
)
from app.modules.assistant.contracts import SearchToolInput, ScheduleToolInput
from app.modules.assistant.settings import get_assistant_settings
from app.shared.clock import now_utc
from app.shared.errors import ApiError

logger = logging.getLogger("cca.model.real")

DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 1

# 有界重试的退避（测试可 monkeypatch 为 0 提速）；重试只对网络错误/超时/5xx。
RETRY_BACKOFF_SECONDS = 0.2
RETRY_BACKOFF_MAX_SECONDS = 2.0
# 单个工具结果回灌给模型的字符上限（IF-009：只发完成任务的必要内容）。
TOOL_RESULT_CHAR_LIMIT = 8_000
# 草稿内容/标题的传输上限（plan payload 校验：标题 100、正文 10000）。
DRAFT_TITLE_LIMIT = 100
DRAFT_CONTENT_LIMIT = 4_000
# OpenAI 兼容服务端"不支持流式"时常见的状态码：此时退化为本地分块输出已定稿正文。
_STREAM_UNSUPPORTED_STATUS = frozenset({400, 404, 405, 422})
# 去掉 JSON Schema 中的 UI 字段，只留结构化约束。
_SCHEMA_UI_KEYS = frozenset({"title", "default"})
# 模型正文里出现服务端引用 ID 一律剥掉：引用只能来自检索结果（FR-QA-002）。
_CITATION_ID_RE = re.compile(r"\bcit_[A-Za-z0-9_-]+")
_DONE = object()


SYSTEM_PROMPT = (
    "你是校园课程智能助手。可调用 get_my_schedule 查询本人的课表、"
    "search_course_docs 检索已发布的共享课程资料。"
    "约束：涉及课程规定、评分、实验要求等资料事实时，必须先检索资料再回答；"
    "只能把工具返回的片段作为资料依据，不得编造课程规定、文件名、页码或引用编号；"
    "工具没有给出依据时明确说明依据不足；"
    "回答用简体中文、面向学生、直接给结论与必要依据，不要输出内部推理过程。"
)


def _clean_json_schema(node: Any) -> Any:
    """去掉 title/default，并把 ``anyOf: [X, null]`` 收成 ``X``（可选字段）。"""
    if isinstance(node, dict):
        cleaned = {
            key: _clean_json_schema(value)
            for key, value in node.items()
            if key not in _SCHEMA_UI_KEYS
        }
        branches = cleaned.get("anyOf")
        if isinstance(branches, list):
            non_null = [
                branch
                for branch in branches
                if not (isinstance(branch, dict) and branch.get("type") == "null")
            ]
            if len(non_null) == 1:
                return non_null[0]
        return cleaned
    if isinstance(node, list):
        return [_clean_json_schema(item) for item in node]
    return node


def _tool_parameters(model: Any) -> dict[str, Any]:
    """把契约输入模型转成 function.parameters（白名单参数的单一真源）。"""
    parameters = _clean_json_schema(model.model_json_schema())
    parameters.pop("title", None)
    parameters.setdefault("type", "object")
    parameters.setdefault("additionalProperties", False)
    return parameters


TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "type": "function",
        "function": {
            "name": "get_my_schedule",
            "description": (
                "读取当前学生本人的课表（只能查本人；日期范围含起止最多 31 天；"
                "不传日期默认今天）。"
            ),
            "parameters": _tool_parameters(ScheduleToolInput),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_course_docs",
            "description": (
                "检索已发布的共享课程资料，返回权威片段与引用；"
                "query 取用户问题原文，不要拼接历史或身份。"
            ),
            "parameters": _tool_parameters(SearchToolInput),
        },
    },
)

# ---- Provider 内部的结构化草稿通道（不是 MCP 工具，不产生 tool 事件）----
DRAFT_TOOL_NAME = "draft_study_plan"
DRAFT_TOOL_DEFINITION: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": DRAFT_TOOL_NAME,
        "description": (
            "为用户生成学习计划草稿（仅草稿，不保存）。只在用户要求制定/规划/安排"
            "学习计划时调用；title/content 必填。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": DRAFT_TITLE_LIMIT,
                    "description": "计划标题，例如「数据结构期末复习计划」",
                },
                "goal": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "计划目标（可省略）",
                },
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "开始日期 YYYY-MM-DD（与结束日期同时填写）",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "结束日期 YYYY-MM-DD（与开始日期同时填写）",
                },
                "content": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": DRAFT_CONTENT_LIMIT,
                    "description": "可直接执行的计划正文（分条、含时间安排）",
                },
            },
            "required": ["title", "content"],
            "additionalProperties": False,
        },
    },
}

# 模型可直接调度的只读工具名（与 runner.PROVIDER_TOOL_WHITELIST 一致）。
MODEL_CALLABLE_TOOLS: tuple[str, ...] = tuple(
    definition["function"]["name"] for definition in TOOL_DEFINITIONS
)

# deterministic 的 SCHEDULE_WORDS 没覆盖的课表问法（AT-32 S05「课在哪里上」）。
# 只补"哪里上/在哪上"这类指向上课地点的短语，避免把「办公室在哪里」误判成课表。
_EXTRA_SCHEDULE_MARKERS: tuple[str, ...] = (
    "哪里上",
    "在哪上",
    "什么地方上",
    "上课地点",
)

_SCHEDULE_TOOL = next(
    definition
    for definition in TOOL_DEFINITIONS
    if definition["function"]["name"] == "get_my_schedule"
)
_SEARCH_TOOL = next(
    definition
    for definition in TOOL_DEFINITIONS
    if definition["function"]["name"] == "search_course_docs"
)


class RealProviderAdapter:
    """OpenAI 兼容 chat/completions 适配器（真实网络调用）。"""

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, int(max_retries))
        # 仅测试/受控环境注入（httpx.MockTransport）；生产保持 None 走真实网络。
        self._transport = transport
        self.name = f"openai-compatible:{model or 'unset'}"

    # ------------------------------------------------------------------ 元信息
    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.model)

    @property
    def chat_completions_url(self) -> str:
        base = (self.endpoint or "").rstrip("/")
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    def describe(self) -> dict[str, Any]:
        """可安全外发的描述：只报密钥是否已配，不回显密钥原文。"""
        return {
            "provider": "openai-compatible",
            "name": self.name,
            "endpoint": self.endpoint or None,
            "model": self.model or None,
            "api_key_configured": bool(self.api_key),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "implemented": True,
        }

    # ------------------------------------------------------------------ 网关
    async def next_action(self, context: ModelContext, budget: ModelBudget) -> ModelAction:
        self._require_configured()
        self._check_budget(budget)
        tools = self._tools_for(context)
        payload = self._payload(self._messages(context, tools))
        if tools:
            payload["tools"] = list(tools)
        try:
            data = await self._request_json(payload)
            action = self._parse_action(data, context, tools)
        except ApiError:
            # 草稿已生成/已保存时，这一步只负责收口：即便输出不合同，也用服务端
            # 状态给一句可核验的最终回答，避免把已完成的草稿/保存判失败。
            if context.draft is not None:
                return Answer(text=self._state_answer(context))
            raise
        if isinstance(action, Answer):
            fallback = self._required_tool_fallback(context)
            if fallback is not None:
                return fallback
            if (
                context.draft is None
                and context.save is None
                and self._is_plan_request(context.message)
            ):
                draft = self._draft_from_text(context, action.text)
                if draft is not None:
                    return draft
            return Answer(
                text=self._finalize_answer(context, action.text),
                basis_types=action.basis_types,
            )
        return action

    def _payload(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    async def stream_answer(self, answer: Answer, emit: EmitToken) -> None:
        """把**已定稿**正文流式渲染给客户端。

        决策已在 ``next_action`` 完成，这里不再重新决策：用 ``stream=true`` 请求让上游
        原样输出同一段文字并逐块 ``emit``；上游不支持流式（非 SSE 响应/400/422/空流）
        则退化为本地按块输出 ``answer.text``。已 emit 的部分不撤回（与 runner 终态语义
        一致）；流中断/超时以 ``MODEL_UNAVAILABLE`` 收口，由上层终结本轮。
        """
        self._require_configured()
        text = answer.text or ""
        if not text:
            return
        limit = self._chunk_limit()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "下面这段是本轮已经确定的最终回答。请原样逐字输出这一段，"
                        "不要改写、不要解释、不要添加任何前后缀：\n\n" + text
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        streamed = await self._stream_text(payload, emit, limit)
        if not streamed:
            # 上游不支持流式（或没有给出增量）：退化为本地分块，仍保证正文完整。
            await self._emit_chunked(text, emit, limit)
            return
        if streamed == text:
            return
        if text.startswith(streamed):
            # 上游提前结束但内容一致：补齐剩余正文，保证总长度与 answer 一致。
            await self._emit_chunked(text[len(streamed) :], emit, limit)
            return
        logger.warning(
            "streamed answer differs from decided text streamed=%d decided=%d",
            len(streamed),
            len(text),
        )

    # ------------------------------------------------------------------ 守卫
    def _require_configured(self) -> None:
        if not self.configured:
            logger.warning("model provider is not fully configured")
            raise ApiError("MODEL_UNAVAILABLE")

    def _check_budget(self, budget: ModelBudget) -> None:
        if int(budget.remaining_decisions) <= 0:
            raise ApiError("CALL_LIMIT_REACHED")
        deadline = budget.deadline_at
        if deadline is not None:
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if now_utc() >= deadline:
                raise ApiError("EXECUTION_TIMEOUT")

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or ''}",
        }

    # ------------------------------------------------------------------ 意图与工具暴露
    @staticmethod
    def _is_schedule_request(message: str) -> bool:
        """课表请求：确定性 Provider 的关键词 + 「哪里上/在哪上」等地点问法。"""
        return wants_schedule(message) or any(
            marker in message for marker in _EXTRA_SCHEDULE_MARKERS
        )

    @classmethod
    def _is_plan_request(cls, message: str) -> bool:
        """计划请求：与确定性 Provider 同一套意图判定（课表/资料优先）。"""
        return (
            wants_plan(message)
            and not cls._is_schedule_request(message)
            and not wants_documents(message)
        )

    def _tools_for(self, context: ModelContext) -> tuple[dict[str, Any], ...]:
        """按本轮意图只暴露必要工具，避免模型调用评测不允许的工具。"""
        if context.draft is not None or context.save is not None:
            return ()  # 草稿已出/已保存：不要再次生成草稿或调度工具
        message = context.message
        if self._is_schedule_request(message):
            return (_SCHEDULE_TOOL,)
        if wants_documents(message):
            return (_SEARCH_TOOL,)
        if self._is_plan_request(message):
            return (DRAFT_TOOL_DEFINITION,)
        return ()

    def _required_tool_fallback(self, context: ModelContext) -> ToolCall | None:
        """模型该调工具却直接作答时，补一次只读工具调度（服务端按同一意图规则）。"""
        message = context.message
        if self._is_schedule_request(message) and context.result_of(
            "get_my_schedule"
        ) is None:
            start, end = schedule_range(context)
            return ToolCall(
                tool_name="get_my_schedule",
                arguments={"from_date": start, "to_date": end},
            )
        if (
            wants_documents(message)
            and not self._is_schedule_request(message)
            and context.result_of("search_course_docs") is None
        ):
            return ToolCall(
                tool_name="search_course_docs", arguments={"query": message}
            )
        return None

    # ------------------------------------------------------------------ 消息
    def _messages(
        self, context: ModelContext, tools: tuple[dict[str, Any], ...]
    ) -> list[dict[str, Any]]:
        """只发送角色约束 / 受控历史 / 当前问题 / 服务端工具结果（无任何身份字段）。"""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._system_prompt(context, tools)}
        ]
        messages.extend(self._history_messages(context))
        message = (context.message or "").strip()
        if message:
            messages.append({"role": "user", "content": message})
        messages.extend(self._tool_result_messages(context))
        return messages

    def _system_prompt(
        self, context: ModelContext, tools: tuple[dict[str, Any], ...]
    ) -> str:
        tool_names = [definition["function"]["name"] for definition in tools]
        lines = [
            "你是校园课程智能助手，面向学生回答课表与课程资料问题。",
            f"今天是 {context.today.isoformat()}（学校时区 {context.school_timezone}），"
            f"明天是 {context.tomorrow.isoformat()}。",
            "日期规则：回答中凡出现日期，必须写成 ISO 形式 YYYY-MM-DD"
            "（例：明天（2026-10-29））；不得只写「10月29日」或「2026年10月29日」。",
            f"本轮可用工具：{'、'.join(tool_names) if tool_names else '无（请直接回答）'}。",
            "课表规则：问课表/有没有课/几点上课/在哪里上课时，只调用 get_my_schedule；"
            "回答时逐条照抄工具返回的日期（YYYY-MM-DD）、时间（HH:MM-HH:MM）、课程名、"
            "地点，不合并、不改写、不翻译课程名；工具返回空列表时必须明确说"
            "「YYYY-MM-DD 没有课」。",
            "资料规则：涉及课程规定、评分、实验要求等事实时，先调用 search_course_docs；"
            "只依据返回片段回答，不得编造文件名、页码或引用编号；"
            "没有依据时明确说「依据不足」。",
            "计划规则：用户要求制定/规划/安排学习计划时，调用 draft_study_plan 生成草稿，"
            "不要用普通正文代替草稿，也不要先查课表或资料；草稿不等于已保存，"
            "保存需服务端依据用户本轮明确指令与保存许可决定，你不得声称已保存。",
            "回答使用简体中文、面向学生、直接给结论与必要依据，不输出内部推理过程。",
            "不要重复用户消息里出现的任何引用编号（cit_*）或文件路径。",
        ]
        state = self._state_line(context)
        if state:
            lines.append(state)
        return "\n".join(lines)

    @staticmethod
    def _state_line(context: ModelContext) -> str | None:
        if context.save is not None:
            return (
                "本轮状态：已保存学习计划（计划编号 "
                f"{context.save.plan_id}，由服务端签发许可并落库）。"
                "最终回答必须以「已按你的明确要求保存」开头并写明计划编号，"
                "不得再说「尚未保存」。"
            )
        if context.draft is not None:
            return (
                "本轮状态：已生成学习计划草稿（草稿 ≠ 已保存）。"
                "最终回答必须说明草稿尚未保存，可直接使用保存按钮。"
            )
        return None

    @staticmethod
    def _history_messages(context: ModelContext) -> list[dict[str, Any]]:
        """history 既可能是 ``HistoryMessage``，也可能是 (user, assistant) 文本对。"""
        messages: list[dict[str, Any]] = []
        for item in context.history or ():
            role = getattr(item, "role", None)
            if role in ("user", "assistant"):
                content = getattr(item, "content", None)
                if content:
                    messages.append({"role": role, "content": str(content)})
                continue
            if isinstance(item, (tuple, list)) and len(item) == 2:
                user_text, assistant_text = str(item[0] or ""), str(item[1] or "")
                if user_text:
                    messages.append({"role": "user", "content": user_text})
                if assistant_text:
                    messages.append({"role": "assistant", "content": assistant_text})
        return messages

    @classmethod
    def _tool_result_messages(cls, context: ModelContext) -> list[dict[str, Any]]:
        """把本轮已执行的真实结果按 tool_calls/tool 协议回灌，供下一步决策或作答。"""
        messages: list[dict[str, Any]] = []
        for index, record in enumerate(context.tool_results or (), start=1):
            call_id = f"call_{index}"
            arguments = record.arguments if isinstance(record.arguments, dict) else {}
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": record.tool_name,
                                "arguments": json.dumps(
                                    arguments, ensure_ascii=False, default=str
                                ),
                            },
                        }
                    ],
                }
            )
            messages.append(
                {"role": "tool", "tool_call_id": call_id, "content": cls._tool_content(record)}
            )
        return messages

    @staticmethod
    def _tool_content(record: Any) -> str:
        view: dict[str, Any] = {
            "success": bool(record.success),
            "result_status": record.result_status,
        }
        if record.code:
            view["code"] = record.code
        payload = record.payload if isinstance(record.payload, dict) else {}
        for key, value in payload.items():
            if isinstance(key, str) and key.startswith("_"):
                continue  # ``_evidence`` 等内部对象不发给模型
            view[key] = value
        text = json.dumps(view, ensure_ascii=False, default=str)
        if len(text) > TOOL_RESULT_CHAR_LIMIT:
            return text[:TOOL_RESULT_CHAR_LIMIT] + "…（结果已截断）"
        return text

    # ------------------------------------------------------------------ HTTP
    async def _request_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._post(payload)
        try:
            data = response.json()
        except ValueError as exc:
            logger.warning(
                "model response is not valid JSON status=%s", response.status_code
            )
            raise ApiError("MODEL_UNAVAILABLE") from exc
        if not isinstance(data, dict):
            logger.warning("model response is not a JSON object")
            raise ApiError("MODEL_UNAVAILABLE")
        return data

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """POST JSON；网络错误/超时/5xx 有界重试，其他一律 MODEL_UNAVAILABLE。"""
        delay = RETRY_BACKOFF_SECONDS
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self._transport
        ) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(
                        self.chat_completions_url, json=payload, headers=self._headers()
                    )
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt >= self.max_retries:
                        logger.warning(
                            "model request failed attempts=%d error=%s",
                            attempt + 1,
                            type(exc).__name__,
                        )
                        raise ApiError("MODEL_UNAVAILABLE") from exc
                    logger.warning(
                        "model request retry attempt=%d/%d error=%s",
                        attempt + 1,
                        self.max_retries + 1,
                        type(exc).__name__,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, RETRY_BACKOFF_MAX_SECONDS)
                    continue
                if 200 <= response.status_code < 300:
                    return response
                if 500 <= response.status_code < 600 and attempt < self.max_retries:
                    logger.warning(
                        "model request retry attempt=%d/%d status=%s",
                        attempt + 1,
                        self.max_retries + 1,
                        response.status_code,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, RETRY_BACKOFF_MAX_SECONDS)
                    continue
                logger.warning("model request failed status=%s", response.status_code)
                raise ApiError("MODEL_UNAVAILABLE")
        raise ApiError("MODEL_UNAVAILABLE")

    # ------------------------------------------------------------------ 解析
    def _parse_action(
        self,
        data: dict[str, Any],
        context: ModelContext,
        tools: tuple[dict[str, Any], ...],
    ) -> ModelAction:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            logger.warning("model response has no choices")
            raise ApiError("MODEL_UNAVAILABLE")
        first = choices[0]
        message = first.get("message") if isinstance(first, dict) else None
        if not isinstance(message, dict):
            logger.warning("model response has no message")
            raise ApiError("MODEL_UNAVAILABLE")

        tool_calls = message.get("tool_calls")
        if tool_calls:
            return self._parse_tool_call(tool_calls, context, tools)

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return Answer(text=content.strip())
        logger.warning("model response contains neither tool_calls nor text")
        raise ApiError("MODEL_UNAVAILABLE")

    def _parse_tool_call(
        self,
        tool_calls: Any,
        context: ModelContext,
        tools: tuple[dict[str, Any], ...],
    ) -> ModelAction:
        if not isinstance(tool_calls, list) or not isinstance(tool_calls[0], dict):
            logger.warning("model tool_calls structure is invalid")
            raise ApiError("MODEL_UNAVAILABLE")
        if len(tool_calls) > 1:
            logger.info(
                "model returned %d parallel tool calls; using the first", len(tool_calls)
            )
        function = tool_calls[0].get("function")
        if not isinstance(function, dict):
            logger.warning("model tool call has no function object")
            raise ApiError("MODEL_UNAVAILABLE")
        name = function.get("name")
        if not isinstance(name, str):
            logger.warning("model tool call has no name")
            raise ApiError("MODEL_UNAVAILABLE")
        if context.draft is not None or context.save is not None:
            # 草稿已生成/已保存：这一步只该给最终回答；不再调度工具（也避免重复草稿/保存）。
            return Answer(text=self._state_answer(context))
        exposed = {definition["function"]["name"] for definition in tools}
        if name not in exposed:
            logger.warning(
                "model requested a tool that is not exposed this turn name=%.64s", name
            )
            raise ApiError("MODEL_UNAVAILABLE")
        arguments = self._parse_arguments(function.get("arguments"))
        if name == DRAFT_TOOL_NAME:
            return self._draft_from_arguments(context, arguments)
        return ToolCall(tool_name=name, arguments=arguments)  # type: ignore[arg-type]

    @staticmethod
    def _parse_arguments(raw: Any) -> dict[str, Any]:
        """``arguments`` 原样交给下游 runner 二次校验；这里只保证是 JSON 对象。"""
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return {}
            try:
                parsed = json.loads(text)
            except ValueError as exc:
                logger.warning("model tool call arguments are not valid JSON")
                raise ApiError("MODEL_UNAVAILABLE") from exc
            if not isinstance(parsed, dict):
                logger.warning("model tool call arguments are not a JSON object")
                raise ApiError("MODEL_UNAVAILABLE")
            return parsed
        logger.warning("model tool call arguments have unsupported type")
        raise ApiError("MODEL_UNAVAILABLE")

    # ------------------------------------------------------------------ 草稿
    def _draft_from_arguments(
        self, context: ModelContext, arguments: dict[str, Any]
    ) -> DraftIntent:
        title = str(arguments.get("title") or "").strip()[:DRAFT_TITLE_LIMIT]
        content = str(arguments.get("content") or "").strip()[:DRAFT_CONTENT_LIMIT]
        goal_text = str(arguments.get("goal") or "").strip()[:500]
        start = self._parse_date(arguments.get("start_date"))
        end = self._parse_date(arguments.get("end_date"))
        if start is None or end is None or start > end:
            # 两日期同空或同填且有序（plan payload 跨字段规则），否则整体丢弃。
            start, end = None, None
        if not title:
            title = self._fallback_title(context.message)
        if not content:
            content = f"围绕「{title}」制定可执行的学习安排。"
        return DraftIntent(
            title=title,
            content=content,
            goal=goal_text or None,
            start_date=start,
            end_date=end,
            basis_types=self._basis_types(context),
            save_candidate=self._save_candidate(context),
        )

    def _draft_from_text(self, context: ModelContext, text: str) -> DraftIntent | None:
        """模型只给正文时的兜底：把正文当作草稿内容，避免计划请求不落草稿。"""
        content = (text or "").strip()[:DRAFT_CONTENT_LIMIT]
        if not content:
            return None
        return DraftIntent(
            title=self._fallback_title(context.message),
            content=content,
            goal=None,
            start_date=None,
            end_date=None,
            basis_types=self._basis_types(context),
            save_candidate=self._save_candidate(context),
        )

    @staticmethod
    def _fallback_title(message: str) -> str:
        text = (message or "").strip().replace("\n", " ")[:60]
        title = text or "学习计划"
        if "计划" not in title:
            title = f"{title}（学习计划）"
        return title[:DRAFT_TITLE_LIMIT]

    @staticmethod
    def _save_candidate(context: ModelContext) -> bool:
        """只是候选：与 runner 同源判定；真正授权仍由 runner/服务端签发。"""
        from app.modules.assistant.drafts import classify_direct_instruction

        return (
            classify_direct_instruction(context.message, draft_ready=True) == "explicit"
        )

    @staticmethod
    def _parse_date(raw: Any) -> date | None:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _basis_types(context: ModelContext) -> tuple[str, ...]:
        basis: list[str] = []
        schedule = context.result_of("get_my_schedule")
        if schedule is not None and schedule.result_status == "ok":
            basis.append("schedule")
        docs = context.result_of("search_course_docs")
        if docs is not None and docs.result_status == "ok":
            basis.append("documents")
        basis.append("general")
        return tuple(dict.fromkeys(basis))

    def _state_answer(self, context: ModelContext) -> str:
        if context.save is not None:
            return f"已按你的明确要求保存学习计划（计划编号 {context.save.plan_id}）。"
        return "以上内容已生成学习计划草稿，尚未保存；确认无误后可点击保存按钮保存。"

    # ------------------------------------------------------------------ 输出后处理
    def _finalize_answer(self, context: ModelContext, text: str) -> str:
        final = self._strip_citation_ids(text)
        final = self._ground_schedule(context, final)
        final = self._plan_state_wording(context, final)
        return final.strip()

    @staticmethod
    def _strip_citation_ids(text: str) -> str:
        """正文里不许出现服务端引用 ID（引用只从 done.citations 展示）。"""
        return _CITATION_ID_RE.sub("", text)

    @staticmethod
    def _ground_schedule(context: ModelContext, text: str) -> str:
        """课表答案可核验化：ISO 日期/时间/课程名/地点必须逐项出现，空课固定句式。"""
        record = context.result_of("get_my_schedule")
        if record is None or not record.success:
            return text
        payload = record.payload if isinstance(record.payload, dict) else {}
        items = [item for item in (payload.get("items") or []) if isinstance(item, dict)]
        if not items:
            if any(phrase in text for phrase in ("没有课", "无课", "没有查询到")):
                return text
            scope = RealProviderAdapter._date_label(payload)
            return f"{text.rstrip()}\n\n{scope}没有课。"
        missing: list[str] = []
        for item in items:
            name = str(item.get("course_name") or "")
            class_date = str(item.get("class_date") or "")
            start = str(item.get("start_time") or "")
            end = str(item.get("end_time") or "")
            location = str(item.get("location") or "")
            tokens = [token for token in (name, class_date, start, end, location) if token]
            if all(token in text for token in tokens):
                continue
            place = f"，地点 {location}" if location else ""
            missing.append(f"- {class_date} {start}-{end} {name}{place}")
        if not missing:
            return text
        return f"{text.rstrip()}\n\n【课表核对】\n" + "\n".join(missing)

    @staticmethod
    def _date_label(payload: dict[str, Any]) -> str:
        start = str(payload.get("from_date") or "")
        end = str(payload.get("to_date") or "")
        if start and start == end:
            return f"{start} "
        if start and end:
            return f"{start} 至 {end} "
        return "所选日期 "

    @staticmethod
    def _plan_state_wording(context: ModelContext, text: str) -> str:
        """草稿/保存措辞收口：未保存必须「尚未保存」，已保存必须「已按你的明确要求保存」。"""
        if context.save is not None:
            phrase = f"已按你的明确要求保存学习计划（计划编号 {context.save.plan_id}）。"
            text = text.replace("尚未保存", "已保存")
            if "已按你的明确要求保存" not in text:
                text = f"{text.rstrip()}\n\n{phrase}"
            return text
        if context.draft is not None:
            text = text.replace("已按你的明确要求保存", "草稿已生成，尚未保存")
            if "尚未保存" not in text:
                text = f"{text.rstrip()}\n\n以上内容已生成学习计划草稿，尚未保存。"
            return text
        return text

    # ------------------------------------------------------------------ 流式
    async def _stream_text(
        self, payload: dict[str, Any], emit: EmitToken, limit: int
    ) -> str:
        """读 SSE 增量并逐块 emit；返回累计正文；空串表示"未流式成功"（走本地分块）。"""
        delay = RETRY_BACKOFF_SECONDS
        response: httpx.Response | None = None
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds, transport=self._transport
        ) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    request = client.build_request(
                        "POST",
                        self.chat_completions_url,
                        json=payload,
                        headers=self._headers(),
                    )
                    candidate = await client.send(request, stream=True)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    if attempt >= self.max_retries:
                        logger.warning(
                            "model stream failed attempts=%d error=%s",
                            attempt + 1,
                            type(exc).__name__,
                        )
                        raise ApiError("MODEL_UNAVAILABLE") from exc
                    logger.warning(
                        "model stream retry attempt=%d/%d error=%s",
                        attempt + 1,
                        self.max_retries + 1,
                        type(exc).__name__,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, RETRY_BACKOFF_MAX_SECONDS)
                    continue
                if candidate.status_code in _STREAM_UNSUPPORTED_STATUS:
                    # 上游不认 stream=true：交给上层退化为本地分块输出。
                    await candidate.aclose()
                    logger.info(
                        "model stream unsupported status=%s; fallback to local chunks",
                        candidate.status_code,
                    )
                    return ""
                if 500 <= candidate.status_code < 600 and attempt < self.max_retries:
                    await candidate.aclose()
                    logger.warning(
                        "model stream retry attempt=%d/%d status=%s",
                        attempt + 1,
                        self.max_retries + 1,
                        candidate.status_code,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, RETRY_BACKOFF_MAX_SECONDS)
                    continue
                if not (200 <= candidate.status_code < 300):
                    await candidate.aclose()
                    logger.warning(
                        "model stream failed status=%s", candidate.status_code
                    )
                    raise ApiError("MODEL_UNAVAILABLE")
                response = candidate
                break

            if response is None:
                raise ApiError("MODEL_UNAVAILABLE")

            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type:
                # 200 但不是 SSE（不支持流式的兼容服务）：退化为本地分块。
                await response.aclose()
                logger.info(
                    "model stream response is not SSE content_type=%.64s; fallback",
                    content_type,
                )
                return ""

            chunks: list[str] = []
            try:
                async for line in response.aiter_lines():
                    delta = self._sse_delta(line)
                    if delta is _DONE:
                        break
                    if delta:
                        chunks.append(delta)  # type: ignore[arg-type]
                        await self._emit_chunked(delta, emit, limit)  # type: ignore[arg-type]
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                # 已 emit 的部分不撤回；本轮由上层以 MODEL_UNAVAILABLE 终结。
                logger.warning("model stream interrupted error=%s", type(exc).__name__)
                raise ApiError("MODEL_UNAVAILABLE") from exc
            finally:
                await response.aclose()
            return "".join(chunks)

    @staticmethod
    def _sse_delta(line: str) -> Any:
        """解析一行 SSE；返回增量文本 / ``_DONE`` / None。"""
        stripped = line.strip()
        if not stripped or stripped.startswith(":") or not stripped.startswith("data:"):
            return None
        data = stripped[len("data:") :].strip()
        if data == "[DONE]":
            return _DONE
        try:
            event = json.loads(data)
        except ValueError as exc:
            logger.warning("model stream chunk is not valid JSON")
            raise ApiError("MODEL_UNAVAILABLE") from exc
        if not isinstance(event, dict):
            raise ApiError("MODEL_UNAVAILABLE")
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first = choices[0]
        if not isinstance(first, dict):
            return None
        delta = first.get("delta")
        if delta is None:  # 部分兼容服务在流式里仍用 message 字段
            delta = first.get("message")
        if not isinstance(delta, dict):
            return None
        content = delta.get("content")
        if isinstance(content, str) and content:
            return content
        return None

    @staticmethod
    async def _emit_chunked(text: str, emit: EmitToken, limit: int) -> None:
        """按 ``CCA_ASSISTANT_TOKEN_CHUNK_LIMIT`` 切块输出；空块不 emit。"""
        size = max(1, int(limit))
        remaining = text
        while remaining:
            piece, remaining = remaining[:size], remaining[size:]
            if piece:
                await emit(piece)

    @staticmethod
    def _chunk_limit() -> int:
        return max(1, int(get_assistant_settings().token_chunk_limit))


__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT_SECONDS",
    "DRAFT_TOOL_DEFINITION",
    "DRAFT_TOOL_NAME",
    "MODEL_CALLABLE_TOOLS",
    "RETRY_BACKOFF_SECONDS",
    "SYSTEM_PROMPT",
    "TOOL_DEFINITIONS",
    "TOOL_RESULT_CHAR_LIMIT",
    "RealProviderAdapter",
]
