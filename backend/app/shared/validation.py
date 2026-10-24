"""严格校验基类与常用注解类型（设计 §3.1 / §3.2）。

- JSON 请求对象一律 ``extra="forbid"``（额外字段 422）。
- 布尔、整数不做宽松字符串强转（``StrictBool`` / ``StrictInt``）；日期用 ISO 日期。
- PATCH 用 ``model_fields_set`` 区分“缺失”与“显式 null”。
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

PAGE_DEFAULT = 20
PAGE_MAX = 100


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequestModel(StrictModel):
    """公共请求体基类：额外字段一律拒绝。"""


ExpectedVersion = Annotated[StrictInt, Field(ge=1, description="乐观锁版本（≥1）")]

PageNumber = Annotated[StrictInt, Field(ge=1)]

__all__ = [
    "ExpectedVersion",
    "PAGE_DEFAULT",
    "PAGE_MAX",
    "PageNumber",
    "RequestModel",
    "StrictBool",
    "StrictInt",
    "StrictModel",
]
