"""计划 / 草稿 / 保存 Schema 与视图（字段以 OpenAPI 为权威）。"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from pydantic import Field, field_validator, model_validator

from app.adapters.db.models import PlanDraft, PlanDraftVersion, StudyPlan
from app.shared.clock import isoformat, time_str  # noqa: F401 - time_str 供 Phase 3 复用
from app.shared.payload import normalize_plan_payload, payload_from_row
from app.shared.validation import ExpectedVersion, RequestModel, StrictInt

ID_PATTERN = r"^[A-Za-z0-9_-]+$"
OPERATION_PATTERN = r"^[A-Za-z0-9._:-]+$"


def validate_plan_payload(payload: Mapping[str, Any], *, field_prefix: str = "") -> None:
    """跨字段规则：两日期同空或同填且有序；标题/正文 trim 后非空。"""
    from app.shared.errors import validation_error

    prefix = f"{field_prefix}" if field_prefix else ""
    if not str(payload.get("title") or "").strip():
        raise validation_error((f"{prefix}title", "标题不能为空白"))
    if not str(payload.get("content") or "").strip():
        raise validation_error((f"{prefix}content", "正文不能为空白"))
    start = payload.get("start_date")
    end = payload.get("end_date")
    if (start is None) != (end is None):
        raise validation_error(
            (f"{prefix}start_date", "开始与结束日期需要同时填写"),
            (f"{prefix}end_date", "开始与结束日期需要同时填写"),
        )
    if start is not None and end is not None:
        start_date = date.fromisoformat(str(start))
        end_date = date.fromisoformat(str(end))
        if start_date > end_date:
            raise validation_error((f"{prefix}end_date", "开始日期不能晚于结束日期"))


class PlanCreate(RequestModel):
    title: str = Field(min_length=1, max_length=100)
    goal: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    content: str = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def _cross_fields(self) -> "PlanCreate":
        validate_plan_payload(
            {
                "title": self.title,
                "content": self.content,
                "start_date": self.start_date,
                "end_date": self.end_date,
            }
        )
        return self


class PlanPatch(RequestModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    goal: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    expected_version: ExpectedVersion

    @model_validator(mode="after")
    def _patch_shape(self) -> "PlanPatch":
        provided = self.model_fields_set
        mutable = {"title", "goal", "start_date", "end_date", "content"}
        if not provided.intersection(mutable):
            raise ValueError("至少提供一个可修改字段")
        for name in ("title", "content"):
            if name in provided and getattr(self, name) is None:
                raise ValueError(f"{name} 不允许为 null")
        return self


class DraftPatch(RequestModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    goal: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    expected_draft_version: StrictInt = Field(ge=1)

    @model_validator(mode="after")
    def _patch_shape(self) -> "DraftPatch":
        provided = self.model_fields_set
        mutable = {"title", "goal", "start_date", "end_date", "content"}
        if not provided.intersection(mutable):
            raise ValueError("至少提供一个可修改字段")
        for name in ("title", "content"):
            if name in provided and getattr(self, name) is None:
                raise ValueError(f"{name} 不允许为 null")
        return self


class DraftSave(RequestModel):
    draft_version: StrictInt = Field(ge=1)


def plan_view(plan: StudyPlan) -> dict[str, Any]:
    payload = payload_from_row(
        title=plan.title,
        goal=plan.goal,
        start_date=plan.start_date,
        end_date=plan.end_date,
        content=plan.content,
        basis_snapshot=plan.basis_snapshot,
    )
    return {
        "id": plan.id,
        "title": payload["title"],
        "goal": payload["goal"],
        "start_date": payload["start_date"],
        "end_date": payload["end_date"],
        "content": payload["content"],
        "source": plan.source,
        "basis_types": payload["basis_types"],
        "references": payload["references"],
        "version": int(plan.version),
        "created_at": isoformat(plan.created_at),
        "updated_at": isoformat(plan.updated_at),
    }


def draft_view(
    draft: PlanDraft, version: PlanDraftVersion, payload: Mapping[str, Any]
) -> dict[str, Any]:
    normalized = normalize_plan_payload(payload)
    return {
        "draft_id": draft.id,
        "draft_version": int(version.draft_version),
        "operation_id": version.operation_id,
        "title": normalized["title"],
        "goal": normalized["goal"],
        "start_date": normalized["start_date"],
        "end_date": normalized["end_date"],
        "content": normalized["content"],
        "basis_types": normalized["basis_types"],
        "references": normalized["references"],
        "expires_at": isoformat(draft.expires_at),
    }
