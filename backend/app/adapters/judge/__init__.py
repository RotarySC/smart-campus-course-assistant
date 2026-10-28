"""检索充分性判官（LLM 判「候选片段能否回答该问题」）。

``app.adapters.judge.llm``：两段式分数门 + 判官，配置见 ``CCA_RETRIEVAL_JUDGE*``。
"""

from app.adapters.judge.llm import (
    SNIPPET_LIMIT,
    RetrievalJudge,
    build_judge,
    judge_band,
    judge_enabled,
    judge_fail_open,
    parse_judgement,
    parse_verdict,
)

__all__ = [
    "SNIPPET_LIMIT",
    "RetrievalJudge",
    "build_judge",
    "judge_band",
    "judge_enabled",
    "judge_fail_open",
    "parse_judgement",
    "parse_verdict",
]
