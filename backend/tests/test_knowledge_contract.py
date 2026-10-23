"""C7：知识链路 8 端点的运行态 OpenAPI 契约与 Worker CLI 冒烟。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
DESIGN_OPENAPI = BACKEND_DIR.parent / "docs" / "backend" / "openapi_v0.1.json"

ENDPOINTS = [
    ("post", "/api/v1/admin/document-batches", "202", "Batch"),
    ("get", "/api/v1/admin/document-batches/{id}", "200", "Batch"),
    ("get", "/api/v1/admin/documents", "200", "DocumentPage"),
    ("get", "/api/v1/admin/documents/{id}/text", "200", "DocumentText"),
    ("post", "/api/v1/admin/documents/{id}/rebuild", "202", "DocumentMutation"),
    ("delete", "/api/v1/admin/documents/{id}", "202", "DocumentMutation"),
    ("post", "/api/v1/admin/documents/{id}/cleanup-retry", "202", "DocumentMutation"),
    ("get", "/api/v1/citations/{reference_id}", "200", "Citation"),
]

ERROR_STATUSES = {"400", "401", "403", "404", "409", "410", "413", "415", "422", "429", "500", "503", "504"}


async def test_runtime_openapi_matches_design_for_knowledge(client):
    runtime = (await client.get("/api/v1/openapi.json")).json()
    design = None
    if DESIGN_OPENAPI.exists():
        design = json.loads(DESIGN_OPENAPI.read_text(encoding="utf-8"))

    for method, path, success_status, component in ENDPOINTS:
        operation = runtime["paths"][path][method]
        assert success_status in operation["responses"], (method, path)
        schema = operation["responses"][success_status]["content"]["application/json"]["schema"]
        ref = schema.get("$ref", "")
        assert ref.rsplit("_", 2)[-2] == component or component in ref, (method, path, ref)
        for status in ERROR_STATUSES:
            response = operation["responses"].get(status)
            assert response is not None, (method, path, status)
            error_schema = response["content"]["application/json"]["schema"]
            assert error_schema.get("$ref", "").endswith("/Error"), (method, path, status)

        runtime_props = set(runtime["components"]["schemas"][component]["properties"])
        runtime_required = set(runtime["components"]["schemas"][component].get("required", []))
        if design is not None:
            design_schema = design["components"]["schemas"][component]
            design_props = set(design_schema["properties"])
            design_required = set(design_schema.get("required", []))
            assert runtime_props == design_props, (component, runtime_props ^ design_props)
            assert runtime_required == design_required, (
                component,
                runtime_required ^ design_required,
            )


async def test_openapi_parameters_and_request_bodies(client):
    spec = (await client.get("/api/v1/openapi.json")).json()
    upload = spec["paths"]["/api/v1/admin/document-batches"]["post"]
    assert "multipart/form-data" in upload["requestBody"]["content"]

    rebuild = spec["paths"]["/api/v1/admin/documents/{id}/rebuild"]["post"]
    header_names = {
        parameter["name"]
        for parameter in rebuild["parameters"]
        if parameter["in"] == "header"
    }
    assert "Idempotency-Key" in header_names
    assert "Rebuild" in json.dumps(rebuild["requestBody"])

    delete = spec["paths"]["/api/v1/admin/documents/{id}"]["delete"]
    query_names = {
        parameter["name"]
        for parameter in delete["parameters"]
        if parameter["in"] == "query"
    }
    assert "expected_version" in query_names

    preview = spec["paths"]["/api/v1/admin/documents/{id}/text"]["get"]
    query = {parameter["name"]: parameter for parameter in preview["parameters"] if parameter["in"] == "query"}
    assert query["offset"]["schema"]["minimum"] == 0
    assert query["limit"]["schema"]["maximum"] == 20000


async def test_worker_cli_once_runs_against_test_database():
    """`python -m app.entrypoints.worker --once` 可跑（空队列也正常退出）。"""
    env = dict(os.environ)
    env.setdefault("CCA_ENV", "test")
    result = subprocess.run(
        [sys.executable, "-m", "app.entrypoints.worker", "--once", "--max-tasks", "5"],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload_line = [line for line in result.stdout.splitlines() if line.strip().startswith("{")]
    assert payload_line, result.stdout
    payload = json.loads(payload_line[-1])
    assert "processed" in payload
    assert payload["owner"]
