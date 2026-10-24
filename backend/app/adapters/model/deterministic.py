"""确定性 Model Provider（设计 §8.2 / PHASE-03 §3 D2；非生产）。

目标：**同一输入必然产出同一动作序列**，用于全链路可重复测试与行为评测；
真实供应商 Adapter 留空位（见 ``app.adapters.model.real``，TBD-04）。

行为规则（与 PHASE-03 §4 A1 一致）：
1. 含日期/课表意图（今天/明天/本周/下周/课表/有课/上课）→ 调用 ``get_my_schedule``；
   日期锚点按本轮 ``accepted_at`` + 学校时区（今天/明天/本周/下周）。
2. 含资料意图（资料/课件/依据/要求/预习/评分/规定/实验）→ 调用 ``search_course_docs``，
   query 严格取用户问题原文（不拼接历史、不拼接身份）。
3. 含计划意图（计划/制定/复习/安排/规划）→ 形成 ``DraftIntent``；
   ``save_candidate`` 只是候选（“保存/存下来/记录下来”等词），**不构成许可**。
4. 其余 → ``Answer``：有证据（课表/资料）才陈述事实；无证据时说“依据不足”，
   普通学习建议明确标注为建议。

provider 内不出现任何身份、许可或令牌概念；返回的工具参数只含白名单字段。
"""

from __future__ import annotations

import re
from datetime import timedelta

from app.adapters.model.gateway import (
    Answer,
    DraftIntent,
    EmitToken,
    EvidenceSet,
    ModelAction,
    ModelBudget,
    ModelContext,
    ToolCall,
    ToolExecutionRecord,
)

# --------------------------------------------------------------------------- #
# 关键词（冻结于此，便于行为评测；改动需同步测试）
# --------------------------------------------------------------------------- #
SCHEDULE_WORDS = (
    "课表",
    "有课",
    "上课",
    "课程安排",
    "几点上课",
    "在哪上课",
    # 自然口语（冒烟回归）：注意“课件”不应触发课表
    "有什么课",
    "什么课",
    "上什么课",
    "几节课",
    "哪几门课",
    "有课吗",
    "有没有课",
    "几门课",
)
TODAY_WORDS = ("今天", "今日", "今晚")
TOMORROW_WORDS = ("明天", "明日")
THIS_WEEK_WORDS = ("本周", "这周", "这星期", "这个星期", "一周")
NEXT_WEEK_WORDS = ("下周", "下个星期", "下星期")

DOC_WORDS = (
    "资料",
    "课件",
    "依据",
    "要求",
    "预习",
    "评分",
    "规定",
    "实验",
    "作业要求",
    "考试范围",
    "成绩",
    "大纲",
)
PLAN_WORDS = ("计划", "制定", "规划", "复习安排", "学习安排", "安排学习", "复习")
SAVE_WORDS = ("保存", "存下来", "存到", "记录下来", "记到我的计划", "帮我存", "加入计划")
REGULATION_WORDS = ("规定", "要求", "评分", "考勤", "作业提交", "截止时间", "考试范围")

TOKEN_CHUNK_SIZE = 24

_PUNCT = re.compile(r"[\s，。！？、；：,.!?;:]+")


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def wants_schedule(message: str) -> bool:
    # “课件/资料”类问题不应被口语化的课表关键词（有什么课…）误触发
    if "课件" in message and not _has_any(
        message, ("课表", "有课", "上课", "课程安排")
    ):
        return False
    return _has_any(message, SCHEDULE_WORDS)


def wants_documents(message: str) -> bool:
    return _has_any(message, DOC_WORDS)


def wants_plan(message: str) -> bool:
    return _has_any(message, PLAN_WORDS)


def mentions_save(message: str) -> bool:
    return _has_any(message, SAVE_WORDS)


def schedule_range(context: ModelContext) -> tuple[str, str]:
    """按 accepted_at 的学校时区日期锚点确定查询范围（同轮跨午夜不变）。"""
    message = context.message
    today = context.today
    if _has_any(message, TOMORROW_WORDS):
        target = today + timedelta(days=1)
        return target.isoformat(), target.isoformat()
    if _has_any(message, NEXT_WEEK_WORDS):
        # 下周一为起点（周一起算）
        start = today + timedelta(days=(7 - today.weekday()))
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    if _has_any(message, THIS_WEEK_WORDS):
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    if _has_any(message, TODAY_WORDS):
        return today.isoformat(), today.isoformat()
    # “课表/有课”但未给日期：今天
    return today.isoformat(), today.isoformat()


class DeterministicProvider:
    """可复现的本地 Provider（测试/演示用，非生产 AI 质量）。"""

    name = "deterministic"

    # ---- ModelGateway ----
    async def next_action(self, context: ModelContext, budget: ModelBudget) -> ModelAction:
        message = context.message
        schedule_done = context.result_of("get_my_schedule")
        docs_done = context.result_of("search_course_docs")

        # 1) 课表（先查数据依赖顺序：课表 → 资料 → 草稿/答案）
        if wants_schedule(message) and schedule_done is None:
            start, end = schedule_range(context)
            return ToolCall(
                tool_name="get_my_schedule",
                arguments={"from_date": start, "to_date": end},
            )

        # 2) 资料检索
        if wants_documents(message) and docs_done is None:
            return ToolCall(tool_name="search_course_docs", arguments={"query": message})

        # 3) 草稿 / 保存候选
        if wants_plan(message) and context.draft is None:
            return self._draft_intent(context, schedule_done, docs_done)

        # 4) 答案
        return Answer(
            text=self._answer_text(context, schedule_done, docs_done),
            basis_types=self._basis_types(schedule_done, docs_done),
        )

    async def stream_answer(self, answer: Answer, emit: EmitToken) -> None:
        text = answer.text
        for start in range(0, len(text), TOKEN_CHUNK_SIZE):
            await emit(text[start : start + TOKEN_CHUNK_SIZE])

    # ---- 内部：构造草稿 ----
    def _draft_intent(
        self,
        context: ModelContext,
        schedule: ToolExecutionRecord | None,
        docs: ToolExecutionRecord | None,
    ) -> DraftIntent:
        topics: list[str] = []
        if docs is not None:
            evidence = _evidence_of(docs)
            for reference in evidence.references[:3]:
                topics.append(f"《{reference.file_name}》{reference.location_label}")
        if schedule is not None:
            payload = schedule.payload or {}
            names = [
                str(item.get("course_name"))
                for item in payload.get("items", [])
                if item.get("course_name")
            ]
            topics.extend(names[:5])
        topic_text = "、".join(dict.fromkeys(topics)) or "课程学习"
        title = f"{topic_text} 学习计划"
        if len(title) > 100:
            title = title[:99] + "…"

        lines = [
            f"目标：围绕 {topic_text} 制定可执行的复习安排。",
            "安排：",
            "1. 先梳理本周课程与资料中的关键要求；",
            "2. 按课程进度划分复习顺序，优先处理标注的要求与考点；",
            "3. 每完成一个主题做一次自测，记录薄弱点；",
            "4. 周末回顾本周薄弱点并补齐。",
        ]
        if schedule is not None and schedule.result_status == "empty":
            lines.append("说明：所选日期范围内没有查到课程安排，计划默认按自主学习处理。")
        if docs is not None and docs.result_status == "empty":
            lines.append("说明：未检索到课程资料依据，以上内容仅为一般学习建议。")
        basis: list[str] = []
        if schedule is not None and schedule.result_status == "ok":
            basis.append("schedule")
        if docs is not None and docs.result_status == "ok":
            basis.append("documents")
        basis.append("general")
        return DraftIntent(
            title=title,
            content="\n".join(lines),
            goal="按课程进度完成复习与自测",
            basis_types=tuple(dict.fromkeys(basis)),
            save_candidate=mentions_save(context.message),
        )

    # ---- 内部：答案 ----
    def _answer_text(
        self,
        context: ModelContext,
        schedule: ToolExecutionRecord | None,
        docs: ToolExecutionRecord | None,
    ) -> str:
        parts: list[str] = []
        if schedule is not None:
            payload = schedule.payload or {}
            items = payload.get("items") or []
            if schedule.result_status == "ok" and items:
                from_date = payload.get("from_date", "")
                to_date = payload.get("to_date", "")
                scope = from_date if from_date == to_date else f"{from_date} 至 {to_date}"
                parts.append(f"{scope} 的课程安排如下：")
                for item in items:
                    location = f"，地点 {item['location']}" if item.get("location") else ""
                    parts.append(
                        f"- {item.get('class_date')} {item.get('start_time')}-"
                        f"{item.get('end_time')} {item.get('course_name')}{location}"
                    )
            else:
                parts.append("所选日期范围内没有查询到课程安排。")

        if docs is not None:
            evidence = _evidence_of(docs)
            if docs.result_status == "ok" and evidence.chunks:
                parts.append("根据已发布的课程资料：")
                for reference in evidence.references[:3]:
                    parts.append(
                        f"- 依据《{reference.file_name}》{reference.location_label}："
                        f"{_snippet(evidence, reference.reference_id)}"
                    )
            elif evidence.corpus_empty:
                parts.append("当前知识库还没有已发布的课程资料，暂时无法给出资料依据。")
            else:
                parts.append("没有检索到可用的课程资料依据，暂时无法回答这项资料类问题。")

        if not parts:
            if _has_any(context.message, REGULATION_WORDS):
                parts.append(
                    "依据不足：目前没有取得课程资料或课表证据，不能确认这项规定，"
                    "请补充资料或换一种问法。"
                )
            else:
                parts.append(
                    "以下为一般学习建议（非课程资料规定）：先明确目标与时间范围，"
                    "再把任务拆成每天可完成的小块，完成后做一次自测。"
                )
        if context.save is not None:
            parts.append(
                "已按你的明确要求保存学习计划（计划编号 "
                f"{context.save.plan_id}）。"
            )
        elif context.draft is not None:
            parts.append(
                "以上内容已生成草稿，尚未保存；确认无误后可点击保存按钮保存。"
            )
        return "\n".join(parts)

    @staticmethod
    def _basis_types(
        schedule: ToolExecutionRecord | None, docs: ToolExecutionRecord | None
    ) -> tuple[str, ...]:
        basis: list[str] = []
        if schedule is not None and schedule.result_status == "ok":
            basis.append("schedule")
        if docs is not None and docs.result_status == "ok":
            basis.append("documents")
        basis.append("general")
        return tuple(dict.fromkeys(basis))


def _evidence_of(record: ToolExecutionRecord) -> EvidenceSet:
    raw = record.payload.get("_evidence")
    if isinstance(raw, EvidenceSet):
        return raw
    return EvidenceSet(status="empty", corpus_empty=False, revision=0)


def _snippet(evidence: EvidenceSet, reference_id: str, limit: int = 80) -> str:
    for chunk in evidence.chunks:
        if chunk.reference_id == reference_id:
            text = chunk.text.strip().replace("\n", " ")
            if len(text) > limit:
                return text[: limit - 1] + "…"
            return text
    return "（内容略）"


__all__ = [
    "DeterministicProvider",
    "SCHEDULE_WORDS",
    "DOC_WORDS",
    "PLAN_WORDS",
    "SAVE_WORDS",
    "mentions_save",
    "schedule_range",
    "wants_documents",
    "wants_plan",
    "wants_schedule",
]
