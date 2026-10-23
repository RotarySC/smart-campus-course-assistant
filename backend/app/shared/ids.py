"""带类型前缀的不透明 ID 生成（设计 BE-D01）。

规则：
- 格式 ``<prefix>_<suffix>``；ASCII、仅 ``[A-Za-z0-9_-]``、长度 ≤ 64。
- 默认随机源用 ``secrets``（不可预测、不可枚举）。
- 测试可注入 :class:`IdGenerator(deterministic=True)` 复现同一串 ID。
"""

from __future__ import annotations

import itertools
import secrets
from typing import Final

MAX_ID_LENGTH: Final = 64
# 16 字节随机 → 22 个 base64url 字符，加前缀后仍在 64 字节以内。
RANDOM_BYTES: Final = 16

# 资源前缀（设计 T02 清单；operation_id 由 Idempotency-Key 决定，无前缀约束）
PREFIX_USER: Final = "usr"
PREFIX_SESSION: Final = "ses"
PREFIX_COURSE: Final = "crs"
PREFIX_SCHEDULE: Final = "sch"
PREFIX_PLAN: Final = "plan"
PREFIX_DRAFT: Final = "dft"
PREFIX_DRAFT_OPERATION: Final = "dop"
PREFIX_GRANT: Final = "grt"
PREFIX_REQUEST: Final = "req"
PREFIX_CONVERSATION: Final = "cnv"
PREFIX_AUDIT: Final = "aud"
PREFIX_OUTBOX: Final = "evt"
PREFIX_BATCH: Final = "bat"
PREFIX_DOCUMENT: Final = "doc"
PREFIX_VERSION: Final = "dvs"
PREFIX_CHUNK: Final = "chk"
PREFIX_CITATION: Final = "cit"
PREFIX_TASK: Final = "tsk"
PREFIX_ATTEMPT: Final = "att"


def _check_prefix(prefix: str) -> None:
    if not prefix or not prefix.isascii() or not prefix.isalnum():
        raise ValueError("ID 前缀必须是 ASCII 字母数字")


class IdGenerator:
    """ID 生成器；``deterministic=True`` 时产出可复现序列（仅测试用）。"""

    def __init__(self, deterministic: bool = False) -> None:
        self._deterministic = deterministic
        self._counter = itertools.count(1)

    def new_id(self, prefix: str) -> str:
        _check_prefix(prefix)
        if self._deterministic:
            suffix = f"{next(self._counter):016d}"
        else:
            suffix = secrets.token_urlsafe(RANDOM_BYTES)
        return f"{prefix}_{suffix}"[:MAX_ID_LENGTH]

    def __call__(self, prefix: str) -> str:  # pragma: no cover - 便捷别名
        return self.new_id(prefix)


_default_generator = IdGenerator()


def new_id(prefix: str) -> str:
    """生成带前缀的不透明 ID。"""
    return _default_generator.new_id(prefix)


def set_id_generator(generator: IdGenerator | None) -> None:
    """测试用：替换全局生成器。"""
    global _default_generator
    _default_generator = generator or IdGenerator()


def get_id_generator() -> IdGenerator:
    return _default_generator
