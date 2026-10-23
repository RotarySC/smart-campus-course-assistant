"""运行态 OpenAPI vs 设计包契约对比（T09 追加项）。

覆盖范围：Phase 1 已实现的 23 个公共端点。
对比维度：路径/方法/operationId、请求体属性名与必填集合、属性类型与枚举、
成功状态码集合、标准错误状态码集合、响应 data 的字段名/必填/枚举。

设计包路径：``<repo>/docs/backend/openapi_v0.1.json``（docs 不入 git；缺失时 skip 并说明）。
差异逐条收集后统一断言并打印，便于前端 ``contract-diff`` 门禁复用同一判定。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
DESIGN_OPENAPI = BACKEND_DIR.parent / "docs" / "backend" / "openapi_v0.1.json"

# Phase 1 已实现端点（method, path）
IMPLEMENTED_ENDPOINTS = [
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/logout"),
    ("get", "/api/v1/me"),
    ("get", "/api/v1/admin/students"),
    ("post", "/api/v1/admin/students"),
    ("patch", "/api/v1/admin/students/{id}"),
    ("get", "/api/v1/admin/courses"),
    ("post", "/api/v1/admin/courses"),
    ("patch", "/api/v1/admin/courses/{id}"),
    ("get", "/api/v1/me/schedules"),
    ("get", "/api/v1/admin/schedules"),
    ("post", "/api/v1/admin/schedules"),
    ("patch", "/api/v1/admin/schedules/{id}"),
    ("delete", "/api/v1/admin/schedules/{id}"),
    ("get", "/api/v1/me/plans"),
    ("post", "/api/v1/me/plans"),
    ("get", "/api/v1/me/plans/{id}"),
    ("patch", "/api/v1/me/plans/{id}"),
    ("delete", "/api/v1/me/plans/{id}"),
    ("get", "/api/v1/me/drafts/{draft_id}"),
    ("patch", "/api/v1/me/drafts/{draft_id}"),
    ("post", "/api/v1/me/drafts/{draft_id}/save"),
    ("get", "/api/v1/me/write-operations/{operation_id}"),
]

SUCCESS_CODES = {"200", "201", "202"}


def _resolve(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    seen = 0
    while isinstance(schema, dict) and "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = components[name]
        seen += 1
        if seen > 10:  # pragma: no cover - 防御循环引用
            break
    return schema or {}


def _enum_signature(schema: dict[str, Any], components: dict[str, Any]) -> Any:
    schema = _resolve(schema, components)
    if "enum" in schema:
        return tuple(schema["enum"])
    if "const" in schema:
        return (schema["const"],)
    if schema.get("type") == "array":
        items = _resolve(schema.get("items", {}), components)
        if "enum" in items:
            return ("array:", tuple(items["enum"]))
        return ("array:", items.get("type"))
    return schema.get("type")


def _object_signature(
    schema: dict[str, Any], components: dict[str, Any]
) -> tuple[dict[str, Any], set[str]]:
    schema = _resolve(schema, components)
    properties = schema.get("properties", {}) or {}
    signature: dict[str, Any] = {}
    for name, prop in properties.items():
        signature[name] = _enum_signature(prop, components)
    return signature, set(schema.get("required", []) or [])


def _request_schema(operation: dict[str, Any]) -> dict[str, Any] | None:
    body = operation.get("requestBody")
    if not body:
        return None
    content = body.get("content", {})
    for media_type in ("application/json", "multipart/form-data"):
        if media_type in content:
            return content[media_type].get("schema", {})
    return None


def _success_response_schema(
    operation: dict[str, Any], status: str
) -> dict[str, Any] | None:
    response = operation.get("responses", {}).get(status)
    if not response:
        return None
    content = response.get("content", {})
    if "application/json" not in content:
        return None
    return content["application/json"].get("schema")


def _diff_endpoint(
    method: str, path: str, design: dict[str, Any], runtime: dict[str, Any]
) -> list[str]:
    diffs: list[str] = []
    label = f"{method.upper()} {path}"

    design_op = design["paths"].get(path, {}).get(method)
    runtime_op = runtime["paths"].get(path, {}).get(method)
    if design_op is None:
        diffs.append(f"{label}: 设计包缺少该端点")
        return diffs
    if runtime_op is None:
        diffs.append(f"{label}: 运行态缺少该端点")
        return diffs

    if design_op.get("operationId") != runtime_op.get("operationId"):
        diffs.append(
            f"{label}: operationId {runtime_op.get('operationId')} != "
            f"{design_op.get('operationId')}"
        )

    # ---- 请求体 ----
    design_req = _request_schema(design_op)
    runtime_req = _request_schema(runtime_op)
    if (design_req is None) != (runtime_req is None):
        diffs.append(f"{label}: 请求体存在性不一致")
    elif design_req is not None and runtime_req is not None:
        design_props, design_required = _object_signature(
            design_req, design["components"]["schemas"]
        )
        runtime_props, runtime_required = _object_signature(
            runtime_req, runtime["components"]["schemas"]
        )
        if set(design_props) != set(runtime_props):
            diffs.append(
                f"{label}: 请求字段不一致 设计={sorted(design_props)} 运行态={sorted(runtime_props)}"
            )
        if design_required != runtime_required:
            diffs.append(
                f"{label}: 请求必填不一致 设计={sorted(design_required)} "
                f"运行态={sorted(runtime_required)}"
            )
        for name in sorted(set(design_props) & set(runtime_props)):
            if design_props[name] != runtime_props[name]:
                diffs.append(
                    f"{label}.{name}: 类型/枚举 设计={design_props[name]} 运行态={runtime_props[name]}"
                )

    # ---- 状态码 ----
    design_codes = set(design_op.get("responses", {}))
    runtime_codes = set(runtime_op.get("responses", {}))
    design_success = {code for code in design_codes if code in SUCCESS_CODES}
    runtime_success = {code for code in runtime_codes if code in SUCCESS_CODES}
    if design_success != runtime_success:
        diffs.append(
            f"{label}: 成功状态码不一致 设计={sorted(design_success)} 运行态={sorted(runtime_success)}"
        )
    design_errors = {code for code in design_codes if code not in SUCCESS_CODES}
    missing_errors = design_errors - runtime_codes
    if missing_errors:
        diffs.append(f"{label}: 缺少错误响应声明 {sorted(missing_errors)}")

    # ---- 成功响应 data schema ----
    for status in sorted(design_success & runtime_success):
        design_schema = _success_response_schema(design_op, status)
        runtime_schema = _success_response_schema(runtime_op, status)
        if design_schema is None or runtime_schema is None:
            if (design_schema is None) != (runtime_schema is None):
                diffs.append(f"{label}[{status}]: 响应体存在性不一致")
            continue
        design_env, _ = _object_signature(design_schema, design["components"]["schemas"])
        runtime_env, _ = _object_signature(
            runtime_schema, runtime["components"]["schemas"]
        )
        if set(design_env) != set(runtime_env):
            diffs.append(
                f"{label}[{status}]: 信封字段不一致 设计={sorted(design_env)} 运行态={sorted(runtime_env)}"
            )
            continue
        design_data = _resolve(
            design_schema, design["components"]["schemas"]
        ).get("properties", {}).get("data", {})
        runtime_data = _resolve(
            runtime_schema, runtime["components"]["schemas"]
        ).get("properties", {}).get("data", {})
        design_props, design_required = _object_signature(
            design_data, design["components"]["schemas"]
        )
        runtime_props, runtime_required = _object_signature(
            runtime_data, runtime["components"]["schemas"]
        )
        if set(design_props) != set(runtime_props):
            diffs.append(
                f"{label}[{status}]: 响应 data 字段不一致 "
                f"设计={sorted(design_props)} 运行态={sorted(runtime_props)}"
            )
        if design_required != runtime_required:
            diffs.append(
                f"{label}[{status}]: 响应 data 必填不一致 "
                f"设计={sorted(design_required)} 运行态={sorted(runtime_required)}"
            )
        for name in sorted(set(design_props) & set(runtime_props)):
            if design_props[name] != runtime_props[name]:
                diffs.append(
                    f"{label}[{status}].{name}: 类型/枚举 设计={design_props[name]} "
                    f"运行态={runtime_props[name]}"
                )
    return diffs


async def test_runtime_openapi_matches_design_package(client):
    if not DESIGN_OPENAPI.exists():
        pytest.skip(f"设计包不存在（docs 不入 git）：{DESIGN_OPENAPI}")
    design = json.loads(DESIGN_OPENAPI.read_text(encoding="utf-8"))
    response = await client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    runtime = response.json()

    diffs: list[str] = []
    for method, path in IMPLEMENTED_ENDPOINTS:
        diffs.extend(_diff_endpoint(method, path, design, runtime))

    if diffs:
        print("\n运行态 OpenAPI 与设计包差异：")
        for item in diffs:
            print(" -", item)
    assert not diffs, f"契约差异 {len(diffs)} 条（见上）"


async def test_create_endpoints_document_201_and_errors(client):
    spec = (await client.get("/api/v1/openapi.json")).json()
    for method, path in IMPLEMENTED_ENDPOINTS:
        operation = spec["paths"][path][method]
        responses = operation["responses"]
        for code in ("401", "403", "404", "409", "410", "422"):
            assert code in responses, (method, path, code)
        if method == "post" and path not in (
            "/api/v1/auth/login",
            "/api/v1/auth/logout",
        ):
            assert "201" in responses, (method, path)
        if path in ("/api/v1/me/plans", "/api/v1/me/drafts/{draft_id}/save") and method == "post":
            assert "202" in responses, (method, path)
        for status, payload in responses.items():
            if status in ("400", "401", "403", "404", "409", "410", "413", "415", "422", "429", "500", "503", "504"):
                schema = payload["content"]["application/json"]["schema"]
                assert schema["$ref"].endswith("/Error"), (method, path, status)
