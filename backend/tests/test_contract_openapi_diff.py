"""全端点契约一致性门禁：运行态 OpenAPI ↔ 设计包（Phase 5 M3 机器判据）。

覆盖 **34 个公共端点 + 4 个内部端点**（P1/P2/P3 全部已实现面）：
- 公共应用：``GET /api/v1/openapi.json``（运行态）；
- 内部应用：``create_internal_app().openapi()``（内部端点只在此暴露）；
- 设计包：``<repo>/contracts/openapi_v0.1.json``（缺失时 skip）。

逐端点对比：路径/方法/operationId、请求体属性/必填/类型/枚举、成功状态码集合、
错误状态码集合（统一 Error schema）、响应 data 字段/必填/类型/枚举（递归到数组元素）。

已裁决接受的结构表达差异放在 ``ACCEPTED_DIFFS``（精确条目 + 理由，逐条必须被命中，
不允许通配符）；真实差异放 ``KNOWN_DOC_GAPS``（精确条目 + owner），门禁对它们**严格失败**，
由 Lead 转派 owner 修复后删除对应条目。白名单未被命中同样失败（防陈旧条目掩盖变化）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
DESIGN_OPENAPI = BACKEND_DIR.parent / "contracts" / "openapi_v0.1.json"

SUCCESS_CODES = {"200", "201", "202"}
ERROR_CODES = (
    "400",
    "401",
    "403",
    "404",
    "409",
    "410",
    "413",
    "415",
    "422",
    "429",
    "500",
    "503",
    "504",
)

# 设计包无、运行态有的运维端点（精确条目）
RUNTIME_ONLY_PATHS = {
    "/api/v1/health": "运维健康检查（进程 + 数据库两级），设计包未列出；Phase 5 门禁排除",
}

# 已裁决接受的结构表达差异：key = (method, path, kind, locator)
ACCEPTED_DIFFS: dict[tuple[str, str, str, str], str] = {
    (
        "PATCH",
        "/api/v1/admin/students/{id}",
        "request",
        "anyOf-constraint",
    ): "PATCH 的“至少一个可变字段”为对象级 anyOf 约束；Pydantic 请求模型无法表达，运行态由模型校验器执行（仍是 422）",
    (
        "PATCH",
        "/api/v1/admin/courses/{id}",
        "request",
        "anyOf-constraint",
    ): "同上：对象级 anyOf 约束不可表达，业务校验等价",
    (
        "PATCH",
        "/api/v1/admin/schedules/{id}",
        "request",
        "anyOf-constraint",
    ): "同上：对象级 anyOf 约束不可表达，业务校验等价",
    (
        "PATCH",
        "/api/v1/me/plans/{id}",
        "request",
        "anyOf-constraint",
    ): "同上：对象级 anyOf 约束不可表达，业务校验等价",
    (
        "PATCH",
        "/api/v1/me/drafts/{draft_id}",
        "request",
        "anyOf-constraint",
    ): "同上：对象级 anyOf 约束不可表达，业务校验等价",
    (
        "POST",
        "/api/v1/chat/stream",
        "response",
        "200",
    ): "SSE（text/event-stream）不适合 JSON Envelope 表达；运行态为流式响应，事件结构由 sse_events_v0.1.schema.json 单独约束（P3 测试覆盖）",
}

# 真实差异（未裁决）：全部 27 条已于 Phase 5 前置（三）收口修复（见 findings），
# 保留空表以便未来新增差异时按同样格式登记 owner + 修复建议。
KNOWN_DOC_GAPS: dict[tuple[str, str, str, str], tuple[str, str]] = {}


# --------------------------------------------------------------------------- #
# schema 结构比较
# --------------------------------------------------------------------------- #
def _resolve(schema: Any, components: dict[str, Any]) -> dict[str, Any]:
    seen = 0
    while isinstance(schema, dict) and "$ref" in schema:
        schema = components[schema["$ref"].rsplit("/", 1)[-1]]
        seen += 1
        if seen > 10:  # pragma: no cover - 防御循环引用
            break
    return schema or {}


def _split_nullable(schema: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """anyOf[T, null] → (T, True)；其余原样返回。"""
    branches = schema.get("anyOf")
    if isinstance(branches, list):
        non_null = [b for b in branches if isinstance(b, dict) and b.get("type") != "null"]
        has_null = any(isinstance(b, dict) and b.get("type") == "null" for b in branches)
        if has_null and len(non_null) == 1:
            rest = {key: value for key, value in schema.items() if key != "anyOf"}
            merged = {**non_null[0], **rest}
            return merged, True
    return schema, False


def _enum_values(schema: dict[str, Any]) -> tuple[Any, ...] | None:
    if "const" in schema:  # const 与单值 enum 等价
        return (schema["const"],)
    if "enum" in schema:
        return tuple(schema["enum"])
    return None


def _compare(
    design_schema: Any,
    runtime_schema: Any,
    dcomps: dict[str, Any],
    rcomps: dict[str, Any],
    locator: str,
    diffs: list[tuple[str, str]],
) -> None:
    design = _resolve(design_schema, dcomps)
    runtime = _resolve(runtime_schema, rcomps)

    if not runtime:
        diffs.append((locator, "运行态响应 schema 为空（未声明响应模型）"))
        return

    design, design_nullable = _split_nullable(design)
    runtime, runtime_nullable = _split_nullable(runtime)
    if design_nullable != runtime_nullable:
        diffs.append(
            (
                f"{locator}.nullable",
                f"可空性 设计={design_nullable} 运行态={runtime_nullable}",
            )
        )

    design_enum = _enum_values(design)
    runtime_enum = _enum_values(runtime)
    if design_enum is not None or runtime_enum is not None:
        if design_enum != runtime_enum:
            diffs.append(
                (f"{locator}.enum", f"枚举 设计={design_enum} 运行态={runtime_enum}")
            )
        return

    design_type = design.get("type")
    runtime_type = runtime.get("type")
    if design_type != runtime_type:
        diffs.append(
            (f"{locator}.type", f"类型 设计={design_type} 运行态={runtime_type}")
        )
        return

    if design_type == "object" or "properties" in design:
        design_props = design.get("properties") or {}
        runtime_props = runtime.get("properties") or {}
        if set(design_props) != set(runtime_props):
            diffs.append(
                (
                    f"{locator}.properties",
                    f"字段集合 设计={sorted(design_props)} 运行态={sorted(runtime_props)}",
                )
            )
        design_required = set(design.get("required") or [])
        runtime_required = set(runtime.get("required") or [])
        if design_required != runtime_required:
            diffs.append(
                (
                    f"{locator}.required",
                    f"必填 设计={sorted(design_required)} 运行态={sorted(runtime_required)}",
                )
            )
        for name in sorted(set(design_props) & set(runtime_props)):
            _compare(
                design_props[name],
                runtime_props[name],
                dcomps,
                rcomps,
                f"{locator}.{name}",
                diffs,
            )
        return

    if design_type == "array":
        for key in ("maxItems", "minItems"):
            if design.get(key) != runtime.get(key):
                diffs.append(
                    (
                        f"{locator}.{key}",
                        f"{key} 设计={design.get(key)} 运行态={runtime.get(key)}",
                    )
                )
        _compare(
            design.get("items", {}),
            runtime.get("items", {}),
            dcomps,
            rcomps,
            f"{locator}[]",
            diffs,
        )


def _object_required_constraint(schema: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """识破对象级 anyOf=[{required:[...]}, ...] 的“至少一个字段”约束。"""
    branches = schema.get("anyOf")
    if (
        isinstance(branches, list)
        and branches
        and all(
            isinstance(branch, dict) and set(branch) <= {"required"} for branch in branches
        )
    ):
        base = {key: value for key, value in schema.items() if key != "anyOf"}
        return base, True
    return schema, False


def _request_schema(operation: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    body = operation.get("requestBody")
    if not body:
        return None, None
    content = body.get("content", {})
    for media in ("application/json", "multipart/form-data"):
        if media in content:
            return media, content[media].get("schema", {})
    return None, None


def _response_schema(operation: dict[str, Any], status: str) -> Any:
    response = (operation.get("responses") or {}).get(status)
    if not response:
        return None
    return (response.get("content") or {}).get("application/json", {}).get("schema")


def _diff_operation(
    method: str,
    path: str,
    design_op: dict[str, Any],
    runtime_op: dict[str, Any],
    dcomps: dict[str, Any],
    rcomps: dict[str, Any],
) -> list[tuple[str, str, str]]:
    """返回 [(kind, locator, detail)]。"""
    diffs: list[tuple[str, str, str]] = []

    if design_op.get("operationId") != runtime_op.get("operationId"):
        diffs.append(
            (
                "operationId",
                "operationId",
                f"设计={design_op.get('operationId')} 运行态={runtime_op.get('operationId')}",
            )
        )

    # ---- 请求体 ----
    design_media, design_schema = _request_schema(design_op)
    runtime_media, runtime_schema = _request_schema(runtime_op)
    if (design_schema is None) != (runtime_schema is None):
        diffs.append(
            ("request", "body", f"存在性 设计={design_media} 运行态={runtime_media}")
        )
    elif design_schema is not None and runtime_schema is not None:
        if design_media != runtime_media:
            diffs.append(
                ("request", "media", f"media 设计={design_media} 运行态={runtime_media}")
            )
        base_schema, has_constraint = _object_required_constraint(
            _resolve(design_schema, dcomps)
        )
        structural: list[tuple[str, str]] = []
        _compare(base_schema, runtime_schema, dcomps, rcomps, "request", structural)
        if has_constraint and not structural:
            diffs.append(
                (
                    "request",
                    "anyOf-constraint",
                    "设计包有对象级 anyOf（至少一个可变字段）约束，运行态无法表达",
                )
            )
        else:
            for locator, detail in structural:
                diffs.append(("request", locator, detail))

    # ---- 状态码 ----
    design_codes = set(design_op.get("responses", {}))
    runtime_codes = set(runtime_op.get("responses", {}))
    design_success = {code for code in design_codes if code in SUCCESS_CODES}
    runtime_success = {code for code in runtime_codes if code in SUCCESS_CODES}
    if design_success != runtime_success:
        diffs.append(
            (
                "success_codes",
                "success",
                f"设计={sorted(design_success)} 运行态={sorted(runtime_success)}",
            )
        )
    design_errors = {code for code in design_codes if code not in SUCCESS_CODES}
    runtime_errors = {code for code in runtime_codes if code not in SUCCESS_CODES}
    if design_errors != runtime_errors:
        diffs.append(
            (
                "error_codes",
                "error",
                f"设计={sorted(design_errors)} 运行态={sorted(runtime_errors)}",
            )
        )

    # ---- 成功响应结构 ----
    for status in sorted(design_success & runtime_success):
        design_schema = _response_schema(design_op, status)
        runtime_schema = _response_schema(runtime_op, status)
        if design_schema is None and runtime_schema is None:
            continue
        if design_schema is None:
            diffs.append(
                (
                    "response",
                    status,
                    "设计包无 application/json 响应体，运行态声明了 JSON schema",
                )
            )
            continue
        if runtime_schema is None or runtime_schema == {}:
            diffs.append(("response", status, "运行态响应 schema 缺失/为空"))
            continue
        structural = []
        _compare(design_schema, runtime_schema, dcomps, rcomps, status, structural)
        for locator, detail in structural:
            diffs.append(("response", locator, detail))

    return diffs


# --------------------------------------------------------------------------- #
# 端点清单与加载
# --------------------------------------------------------------------------- #
def _endpoint_key(
    method: str, path: str, kind: str, locator: str
) -> tuple[str, str, str, str]:
    return (method.upper(), path, kind, locator)


async def _load_specs(client) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from app.main import create_internal_app

    public = (await client.get("/api/v1/openapi.json")).json()
    internal = create_internal_app().openapi()
    design = json.loads(DESIGN_OPENAPI.read_text(encoding="utf-8"))
    return design, public, internal


def _all_operations(spec: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (method.upper(), path)
        for path, operations in spec["paths"].items()
        for method in operations
        if method in ("get", "post", "patch", "delete")
    ]


def test_design_package_shape_is_40_operations():
    """设计包自身必须是 39 操作（35 公共 + 4 内部），防止对比基数漂移。

    39 = 原 38 + `POST /api/v1/auth/register`（桌面自适应追加包 §15.4，自助注册）。
    """
    if not DESIGN_OPENAPI.exists():
        pytest.skip(f"契约文件缺失：{DESIGN_OPENAPI}")
    design = json.loads(DESIGN_OPENAPI.read_text(encoding="utf-8"))
    operations = _all_operations(design)
    assert len(operations) == 40
    public = [(m, p) for m, p in operations if not p.startswith("/internal/v1")]
    internal = [(m, p) for m, p in operations if p.startswith("/internal/v1")]
    assert len(public) == 36 and len(internal) == 4


async def test_full_openapi_structure_matches_design(client):
    if not DESIGN_OPENAPI.exists():
        pytest.skip(f"契约文件缺失：{DESIGN_OPENAPI}")

    design, public, internal = await _load_specs(client)
    design_ops = _all_operations(design)
    public_ops = _all_operations(public)
    internal_ops = _all_operations(internal)

    design_public = [(m, p) for m, p in design_ops if not p.startswith("/internal/v1")]
    assert len(design_public) == 36
    assert len(public_ops) == 36 + len(RUNTIME_ONLY_PATHS)
    assert len(internal_ops) == 4

    internal_paths = {p for _, p in design_ops if p.startswith("/internal/v1")}
    assert set(public["paths"]) & internal_paths == set()
    assert set(internal["paths"]) == internal_paths

    runtime_extra = set(public["paths"]) - set(design["paths"])
    assert runtime_extra == set(RUNTIME_ONLY_PATHS), (
        f"运行态多出未登记路径: {sorted(runtime_extra - set(RUNTIME_ONLY_PATHS))}"
    )

    accepted_used: set[tuple[str, str, str, str]] = set()
    known_used: set[tuple[str, str, str, str]] = set()
    unexpected: list[str] = []
    known_hits: list[str] = []

    dcomps = design["components"]["schemas"]
    pcomps = public["components"]["schemas"]
    icomps = internal["components"]["schemas"]

    for method, path in design_ops:
        if path.startswith("/internal/v1"):
            runtime_spec, rcomps = internal, icomps
        else:
            runtime_spec, rcomps = public, pcomps
        runtime_op = (runtime_spec["paths"].get(path) or {}).get(method.lower())
        if runtime_op is None:
            unexpected.append(f"{method} {path}: 运行态缺少端点")
            continue
        design_op = design["paths"][path][method.lower()]
        for kind, locator, detail in _diff_operation(
            method, path, design_op, runtime_op, dcomps, rcomps
        ):
            key = _endpoint_key(method, path, kind, locator)
            if key in ACCEPTED_DIFFS:
                accepted_used.add(key)
            elif key in KNOWN_DOC_GAPS:
                known_used.add(key)
                owner, reason = KNOWN_DOC_GAPS[key]
                known_hits.append(
                    f"[{owner}] {method} {path} · {kind}:{locator} · {detail} — {reason}"
                )
            else:
                unexpected.append(f"{method} {path} · {kind}:{locator} — {detail}")

    unused_accepted = set(ACCEPTED_DIFFS) - accepted_used
    if known_hits:
        print("\n已知契约文档缺口（等待 owner 修复，门禁严格失败）：")
        for item in known_hits:
            print(" -", item)
    if unexpected:
        print("\n未裁决契约差异：")
        for item in unexpected:
            print(" -", item)
    print("\nunused accepted:", sorted(unused_accepted))
    assert not unused_accepted, (
        f"已裁决白名单条目未命中（可能契约已变化，需更新）: {sorted(unused_accepted)}"
    )
    unused_known = set(KNOWN_DOC_GAPS) - known_used
    assert not unused_known, f"已知差异条目未命中（可能已修复，需删除）: {sorted(unused_known)}"

    assert not unexpected, (
        f"未裁决契约差异 {len(unexpected)} 条（见上）；请 owner 修复或按裁决加入白名单"
    )
    assert not known_hits, f"仍有 {len(known_hits)} 条已知契约缺口未修复（见上）"


async def test_all_operations_document_errors_and_success(client):
    """所有 38 个操作：标准错误响应齐全且统一 Error schema；创建/异步类状态码正确。"""
    if not DESIGN_OPENAPI.exists():
        pytest.skip(f"契约文件缺失：{DESIGN_OPENAPI}")
    design, public, internal = await _load_specs(client)
    for spec in (public, internal):
        for path, operations in spec["paths"].items():
            if path in RUNTIME_ONLY_PATHS:
                continue
            for method, operation in operations.items():
                if method not in ("get", "post", "patch", "delete"):
                    continue
                responses = operation["responses"]
                for code in ERROR_CODES:
                    assert code in responses, (method, path, code)
                    schema = responses[code]["content"]["application/json"]["schema"]
                    assert schema.get("$ref", "").endswith("/Error"), (path, code)
                assert "501" not in responses, (path, "仍有 501 桩")
