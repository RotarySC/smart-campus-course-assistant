"""计划正文规范化摘要（设计 §4.4）。

PlanPayload 字段集合固定：title、goal、start_date、end_date、content、
basis_types、references；UTF-8、键排序、无额外空白 JSON；集合字段去重稳定排序；
正文与换行原样保留；schema_version 参与摘要。
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1

BASIS_TYPES = ("schedule", "documents", "general")

REFERENCE_FIELDS = (
    "reference_id",
    "document_id",
    "version_id",
    "file_name",
    "location_label",
    "page_number",
)


def _date_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def normalize_basis_types(values: Iterable[str] | None) -> list[str]:
    cleaned = {str(v) for v in (values or []) if str(v) in BASIS_TYPES}
    return sorted(cleaned)


def normalize_references(values: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """引用保持给定顺序（保存时快照），字段集合固定、缺省字段不写出。"""
    result: list[dict[str, Any]] = []
    for item in values or []:
        if not isinstance(item, Mapping):
            continue
        ref: dict[str, Any] = {}
        for key in REFERENCE_FIELDS:
            value = item.get(key)
            if value is None:
                continue
            if key == "page_number":
                ref[key] = int(value)
            else:
                ref[key] = str(value)
        if "reference_id" in ref:
            result.append(ref)
    return result


def normalize_plan_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """从任意映射提取固定字段集合的计划载荷。"""
    return {
        "title": str(payload.get("title") or ""),
        "goal": None if payload.get("goal") is None else str(payload.get("goal")),
        "start_date": _date_text(payload.get("start_date")),
        "end_date": _date_text(payload.get("end_date")),
        "content": str(payload.get("content") or ""),
        "basis_types": normalize_basis_types(payload.get("basis_types")),
        "references": normalize_references(payload.get("references")),
    }


def canonical_payload(payload: Mapping[str, Any]) -> bytes:
    normalized = normalize_plan_payload(payload)
    document = {"schema_version": SCHEMA_VERSION, **normalized}
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def plan_payload_digest(payload: Mapping[str, Any]) -> bytes:
    """SHA-256 内容摘要（BINARY(32)）。"""
    return hashlib.sha256(canonical_payload(payload)).digest()


def payload_from_row(
    *,
    title: str | None,
    goal: str | None,
    start_date: date | None,
    end_date: date | None,
    content: str | None,
    basis_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """由 study_plans 行还原 PlanPayload（墓碑行返回空载荷前由调用方拦下）。"""
    snapshot = basis_snapshot or {}
    return normalize_plan_payload(
        {
            "title": title or "",
            "goal": goal,
            "start_date": start_date,
            "end_date": end_date,
            "content": content or "",
            "basis_types": snapshot.get("basis_types") or [],
            "references": snapshot.get("references") or [],
        }
    )


def basis_snapshot_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_plan_payload(payload)
    return {
        "basis_types": normalized["basis_types"],
        "references": normalized["references"],
    }
