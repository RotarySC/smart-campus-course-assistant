"""同名课程消歧（FR-QA-004 / AT-23）。

SRS §4.5 FR-QA-004：「无法区分同名课程时应先补问」。本模块只回答一个问题——
**这一轮问题里的课程名是不是对应多门不同课程**——判定与文案都在模型侧；服务端不替用户挑一门。

判定口径（可复现，便于评测）：
1. 取启用中的课程目录 ``(code, name)``；
2. 问题文本里出现的课程名里选**最长**的那些（避免「数学」把「高等数学」吃掉）；
3. 该名字对应 **≥2 个不同 code** 才算「无法区分」；
4. 若问题里已带上其中某个 code（用户直接报了课程代码），视为已消歧，不再补问。

限制（与 SRS 一致，不是缺陷）：MVP「无明确课程标签时不提供强课程级过滤保证」，因此补问只解决
「问的是哪一门」，不承诺把检索结果过滤到该课程；资料未打课程标签时，回答仍会说明依据可能来自同名课程。
"""

from __future__ import annotations

from typing import Iterable, Sequence

from sqlalchemy import select

from app.adapters.db.models import Course
from app.adapters.db.uow import uow
from app.adapters.model.gateway import AmbiguousCourse

# 太短的名字（单字）容易误命中文档正文，不作为课程名匹配。
MIN_COURSE_NAME_LENGTH = 2


def ambiguous_candidates(
    message: str, catalog: Sequence[tuple[str, str]]
) -> tuple[AmbiguousCourse, ...]:
    """纯函数：按课程目录判定本轮问题里的同名课程候选（空元组＝无需补问）。"""
    text = (message or "").strip()
    if not text:
        return ()
    lowered = text.lower()

    # 1) 命中的课程名（去空白后参与匹配，避免目录里名字带空格导致永不命中）
    matched: list[tuple[str, list[str]]] = []
    for code, name in catalog:
        clean = (name or "").strip()
        if len(clean) < MIN_COURSE_NAME_LENGTH or clean not in text:
            continue
        for entry_name, codes in matched:
            if entry_name == clean:
                if code not in codes:
                    codes.append(code)
                break
        else:
            matched.append((clean, [code]))
    if not matched:
        return ()

    # 2) 只保留最长匹配（多个同名长度的分组都保留，依次补问）
    longest = max(len(name) for name, _ in matched)
    groups = [(name, codes) for name, codes in matched if len(name) == longest]

    candidates: list[AmbiguousCourse] = []
    for name, codes in groups:
        if len(set(codes)) < 2:
            continue
        # 3) 问题里已带候选 code → 用户已指明是哪一门
        if any(code and code.lower() in lowered for code in codes):
            continue
        for code in sorted(set(codes)):
            candidates.append(AmbiguousCourse(code=code, name=name))
    return tuple(candidates)


async def lookup_ambiguous_courses(message: str) -> tuple[AmbiguousCourse, ...]:
    """按数据库里的启用课程目录判定同名课程候选。"""
    async with uow() as tx:
        result = await tx.session.execute(
            select(Course.code, Course.name).where(Course.enabled.is_(True))
        )
        catalog = [(str(code), str(name)) for code, name in result.all()]
    return ambiguous_candidates(message, catalog)


def group_candidates(
    candidates: Iterable[AmbiguousCourse],
) -> dict[str, list[str]]:
    """把候选按课程名分组（供补问文案使用，保持稳定顺序）。"""
    groups: dict[str, list[str]] = {}
    for item in candidates:
        groups.setdefault(item.name, []).append(item.code)
    return {name: sorted(codes) for name, codes in groups.items()}


__all__ = [
    "MIN_COURSE_NAME_LENGTH",
    "ambiguous_candidates",
    "group_candidates",
    "lookup_ambiguous_courses",
]
