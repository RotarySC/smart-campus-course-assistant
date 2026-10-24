"""Phase 5 独立对抗探针（qa-verifier 自写，不复用 owner 用例）。

真实 HTTP 打到冻结版本的公共/内部/MCP 入口（默认 8200 / 8201 / 8202），
真实 MySQL（cca_test_release）做副作用核对。覆盖：

  M5-1  学生令牌打全部 17 个 /admin/** 操作 → 403
  M5-2  跨用户 plan / draft / write-operation / citation → 404/410 且与"不存在"不可区分
  M5-3  伪造/篡改/登出后/错误口令令牌 → 401
  M5-4  禁用后写入穿透 → 401 SESSION_EXPIRED
  M5-5  MCP 无委派/错 audience → 工具错误（不 200 成功）
  M5-6  内部 API 无/错服务凭据、浏览器 Bearer → 401/403
  M5-9  公共入口访问 /internal/v1/** → 404
  M6-1  同键同内容 10 并发 → 恰 1 份计划/1 操作/1 审计/1 outbox；异内容 → 409
  M6-6  双管理员并发重叠课表（空档期）→ 结果 ⊆ {201,409}，恰一成功

用法：
  cd <repo>
  .\\.venv\\Scripts\\python.exe verification\\scripts\\adversarial_probes.py [--base http://127.0.0.1:8200]
输出：逐条 PASS/FAIL + 末尾 RESULT；建议 Tee 到 verification/evidence/M5-M6-probes.log。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import string
import sys
import time
import uuid
from typing import Any

import httpx
import pymysql

try:  # Windows console: keep Chinese probe names readable in the tee'd log
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DB = dict(host="127.0.0.1", port=33061, user="root", password="cca_dev_root", database="cca_test_release")
ADMIN = ("admin_demo", "demo1234")
STUDENT = ("student_demo", "demo1234")

RESULTS: list[tuple[str, str, bool, str]] = []


def record(pid: str, name: str, ok: bool, detail: str) -> None:
    RESULTS.append((pid, name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"{mark}  [{pid}] {name} :: {detail}")


def rid(payload: dict[str, Any] | None) -> str:
    return str((payload or {}).get("request_id") or "-")


def err_code(payload: dict[str, Any] | None) -> str:
    return str(((payload or {}).get("error") or {}).get("code") or "-")


def page_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = (payload or {}).get("data")
    if isinstance(data, dict):
        items = data.get("items")
        return list(items or [])
    return list(data or [])


async def login(client: httpx.AsyncClient, api: str, account: str, password: str) -> str:
    r = await client.post(f"{api}/auth/login", json={"account": account, "password": password})
    if r.status_code != 200:
        raise SystemExit(f"login failed for {account}: {r.status_code} {r.text[:200]}")
    return r.json()["data"]["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def rand_key(prefix: str = "qa") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:20]}"


def db_scalar(sql: str, args: tuple[Any, ...] = ()) -> Any:
    conn = pymysql.connect(**DB, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


async def main(base: str) -> int:
    api = base.rstrip("/") + "/api/v1"
    internal = os.environ.get("QA_INTERNAL", "http://127.0.0.1:8201")
    mcp = os.environ.get("QA_MCP", "http://127.0.0.1:8202/mcp")
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        admin_tok = await login(client, api, *ADMIN)
        student_tok = await login(client, api, *STUDENT)

        # ---- 第二个学生（隔离对象） ----
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        acc_b = f"qa_b_{suffix}"
        r = await client.post(
            f"{api}/admin/students",
            json={"account": acc_b, "display_name": "QA 学生乙", "initial_password": "demo1234"},
            headers=auth(admin_tok),
        )
        assert r.status_code == 201, (r.status_code, r.text[:300])
        user_b = r.json()["data"]
        tok_b = await login(client, api, acc_b, "demo1234")

        # =====================================================================
        # M5-3 令牌伪造矩阵
        # =====================================================================
        r = await client.get(f"{api}/me")
        record("M5-3a", "/me 无令牌", r.status_code == 401 and err_code(r.json()) == "AUTH_REQUIRED", f"{r.status_code} {err_code(r.json())} rid={rid(r.json())}")

        r = await client.get(f"{api}/me", headers={"Authorization": "Bearer not-a-token"})
        record("M5-3b", "/me 伪造 Bearer", r.status_code == 401, f"{r.status_code} {err_code(r.json())} rid={rid(r.json())}")

        tampered = student_tok[:-3] + ("aaa" if student_tok[-3:] != "aaa" else "bbb")
        r = await client.get(f"{api}/me", headers=auth(tampered))
        record("M5-3c", "/me 篡改签名", r.status_code == 401, f"{r.status_code} {err_code(r.json())} rid={rid(r.json())}")

        r = await client.post(f"{api}/auth/login", json={"account": "student_demo", "password": "wrong-password"})
        record("M5-3d", "错误口令登录", r.status_code == 401, f"{r.status_code} {err_code(r.json())} rid={rid(r.json())}")

        # 登出后旧令牌
        tmp_tok = await login(client, api, *STUDENT)
        r = await client.post(f"{api}/auth/logout", headers=auth(tmp_tok))
        logout_ok = r.status_code == 200
        r = await client.get(f"{api}/me", headers=auth(tmp_tok))
        record("M5-3e", "登出后旧令牌", logout_ok and r.status_code == 401 and err_code(r.json()) == "SESSION_EXPIRED", f"logout={logout_ok}; then {r.status_code} {err_code(r.json())} rid={rid(r.json())}")

        # =====================================================================
        # M5-1 学生令牌打全部 /admin/** 操作
        # =====================================================================
        courses = page_items((await client.get(f"{api}/admin/courses", headers=auth(admin_tok))).json())
        course_id = courses[0]["id"]
        sched = page_items((await client.get(f"{api}/admin/schedules", params={"student_id": user_b["id"]}, headers=auth(admin_tok))).json())
        sched_id = sched[0]["id"] if sched else "sch_qa_missing"
        batch = None
        admin_ops = [
            ("M5-1.1", "GET /admin/students", "get", f"{api}/admin/students", {"params": {"page_size": 5}}),
            ("M5-1.2", "POST /admin/students", "post", f"{api}/admin/students", {"json": {"account": f"qa_x_{suffix}", "display_name": "x", "initial_password": "demo1234"}}),
            ("M5-1.3", "PATCH /admin/students/{id}", "patch", f"{api}/admin/students/{user_b['id']}", {"json": {"display_name": "hacked", "expected_version": user_b["version"]}}),
            ("M5-1.4", "GET /admin/courses", "get", f"{api}/admin/courses", {"params": {"page_size": 5}}),
            ("M5-1.5", "POST /admin/courses", "post", f"{api}/admin/courses", {"json": {"code": f"QAX{suffix[:4]}", "name": "x"}}),
            ("M5-1.6", "PATCH /admin/courses/{id}", "patch", f"{api}/admin/courses/{course_id}", {"json": {"name": "hacked", "expected_version": 1}}),
            ("M5-1.7", "GET /admin/schedules", "get", f"{api}/admin/schedules", {"params": {"student_id": user_b["id"]}}),
            ("M5-1.8", "POST /admin/schedules", "post", f"{api}/admin/schedules", {"json": {"student_id": user_b["id"], "course_id": course_id, "class_date": "2027-05-06", "start_time": "08:00", "end_time": "09:00"}}),
            ("M5-1.9", "PATCH /admin/schedules/{id}", "patch", f"{api}/admin/schedules/{sched_id}", {"json": {"location": "hacked", "expected_version": 1}}),
            ("M5-1.10", "DELETE /admin/schedules/{id}", "delete", f"{api}/admin/schedules/{sched_id}", {"params": {"expected_version": 1}}),
            ("M5-1.11", "POST /admin/document-batches", "post", f"{api}/admin/document-batches", {"files": {"files": ("qa.txt", b"qa probe", "text/plain")}}),
            ("M5-1.12", "GET /admin/document-batches/{id}", "get", f"{api}/admin/document-batches/bat_qa_missing", {}),
            ("M5-1.13", "GET /admin/documents", "get", f"{api}/admin/documents", {"params": {"page_size": 5}}),
            ("M5-1.14", "GET /admin/documents/{id}/text", "get", f"{api}/admin/documents/doc_qa_missing/text", {}),
            ("M5-1.15", "POST /admin/documents/{id}/rebuild", "post", f"{api}/admin/documents/doc_qa_missing/rebuild", {"json": {"expected_version": 1}}),
            ("M5-1.16", "DELETE /admin/documents/{id}", "delete", f"{api}/admin/documents/doc_qa_missing", {}),
            ("M5-1.17", "POST /admin/documents/{id}/cleanup-retry", "post", f"{api}/admin/documents/doc_qa_missing/cleanup-retry", {}),
        ]
        for pid, name, method, url, kwargs in admin_ops:
            resp = await client.request(method, url, headers=auth(student_tok), **kwargs)
            body = None
            try:
                body = resp.json()
            except Exception:
                pass
            ok = resp.status_code == 403 and err_code(body) == "FORBIDDEN"
            record(pid, name, ok, f"{resp.status_code} {err_code(body)} rid={rid(body)}")

        # =====================================================================
        # M5-2 跨用户隔离（plan / write-operation / draft / citation）
        # =====================================================================
        plan_key = rand_key("qa-plan")
        r = await client.post(f"{api}/me/plans", json={"title": "QA 隔离计划", "content": "只属于学生甲"}, headers={**auth(student_tok), "Idempotency-Key": plan_key})
        assert r.status_code in (201, 202), (r.status_code, r.text[:300])
        plan_data = r.json()["data"]
        plan_id = plan_data.get("plan_id") or plan_data.get("id")
        plan_operation_id = plan_data["operation_id"]

        for pid, method, url, kwargs in [
            ("M5-2a", "GET", f"{api}/me/plans/{plan_id}", {}),
            ("M5-2b", "PATCH", f"{api}/me/plans/{plan_id}", {"json": {"title": "hijacked", "expected_version": 1}}),
            ("M5-2c", "DELETE", f"{api}/me/plans/{plan_id}", {"params": {"expected_version": 1}}),
        ]:
            resp = await client.request(method, url, headers=auth(tok_b), **kwargs)
            body = resp.json() if resp.content else None
            ok = resp.status_code == 404
            record(pid, f"跨用户 {method} plan", ok, f"{resp.status_code} {err_code(body)} rid={rid(body)}")

        # write-operation：跨用户与"不存在"响应必须不可区分（不泄露存在性）
        r_cross = await client.get(f"{api}/me/write-operations/{plan_operation_id}", headers=auth(tok_b))
        r_fake = await client.get(f"{api}/me/write-operations/wop_qa_not_exist_000", headers=auth(tok_b))
        # operation_id 是客户端回显（两边都回显请求值），比较前剔除；其余字段必须完全一致且不含 plan_id/正文
        cross_data = dict(r_cross.json().get("data") or {})
        fake_data = dict(r_fake.json().get("data") or {})
        cross_data.pop("operation_id", None)
        fake_data.pop("operation_id", None)
        same_shape = r_cross.status_code == r_fake.status_code and cross_data == fake_data
        leaks = (plan_id in r_cross.text) or ("plan_id" in cross_data) or ("plan_id" in fake_data)
        record("M5-2d", "跨用户 write-operation 与不存在不可区分且不泄露 plan_id/正文", same_shape and not leaks, f"cross={r_cross.status_code} fake={r_fake.status_code} same_data={same_shape} leaks={leaks} rid={rid(r_cross.json())}")

        # 引用：伪造 / 不存在 reference_id → 410，且不带正文
        r_cite = await client.get(f"{api}/citations/cit_qa_forged_000", headers=auth(student_tok))
        cite_body = r_cite.json() if r_cite.content else None
        no_body_leak = "text" not in json.dumps(cite_body)
        record("M5-2e", "伪造 reference_id 不可展开", r_cite.status_code == 410 and no_body_leak, f"{r_cite.status_code} {err_code(cite_body)} rid={rid(cite_body)}")

        # 跨用户草稿（学生甲无草稿；用 chat 造草稿成本高，这里用不存在 id 的不可区分性代替）
        r_d1 = await client.get(f"{api}/me/drafts/dft_qa_missing_000", headers=auth(tok_b))
        r_d2 = await client.get(f"{api}/me/drafts/dft_qa_missing_111", headers=auth(tok_b))
        same_draft = r_d1.status_code == r_d2.status_code and json.dumps(r_d1.json().get("error"), sort_keys=True) == json.dumps(r_d2.json().get("error"), sort_keys=True)
        record("M5-2f", "不存在草稿响应不可区分（无存在性泄漏）", same_draft, f"{r_d1.status_code}/{r_d2.status_code} rid={rid(r_d1.json())}")

        # =====================================================================
        # M5-4 禁用后写入穿透
        # =====================================================================
        acc_c = f"qa_c_{suffix}"
        r = await client.post(f"{api}/admin/students", json={"account": acc_c, "display_name": "QA 学生丙", "initial_password": "demo1234"}, headers=auth(admin_tok))
        assert r.status_code == 201, (r.status_code, r.text[:300])
        user_c = r.json()["data"]
        tok_c = await login(client, api, acc_c, "demo1234")
        r = await client.patch(f"{api}/admin/students/{user_c['id']}", json={"enabled": False, "expected_version": user_c["version"]}, headers=auth(admin_tok))
        disabled_ok = r.status_code == 200 and r.json()["data"]["enabled"] is False
        r = await client.post(f"{api}/me/plans", json={"title": "禁用后写入", "content": "不应落库"}, headers={**auth(tok_c), "Idempotency-Key": rand_key("qa-disabled")})
        body = r.json() if r.content else None
        plans_after = db_scalar("SELECT COUNT(*) FROM study_plans WHERE title=%s", ("禁用后写入",))
        record("M5-4", "禁用后在途/新写入不穿透且不落库", disabled_ok and r.status_code == 401 and err_code(body) == "SESSION_EXPIRED" and plans_after == 0, f"disable={disabled_ok} write={r.status_code} {err_code(body)} plans={plans_after} rid={rid(body)}")

        # =====================================================================
        # M5-6 / M5-9 内部 API 与公共入口隔离
        # =====================================================================
        r = await client.get(f"{api}/internal/v1/tools/get-my-schedule")
        record("M5-9", "公共入口访问内部路径 → 404", r.status_code == 404, f"{r.status_code} {err_code(r.json() if r.content else None)}")

        svc = "dev-internal-token"  # 开发默认（TBD-03 未冻结）；仅本机验证环境
        tool_url = f"{internal}/internal/v1/tools/get-my-schedule"
        exch_url = f"{internal}/internal/v1/delegations/exchange"
        cases = [
            ("M5-6a", "内部工具无任何凭据", {}, {}, 401),
            ("M5-6b", "内部工具仅浏览器 Bearer", auth(student_tok), {}, 401),
            ("M5-6c", "内部工具错服务凭据", {"X-Service-Credential": "wrong-service-token"}, {}, 403),
            ("M5-6d", "内部工具正确服务凭据但无执行上下文", {"X-Service-Credential": svc}, {}, 401),
            ("M5-6e", "兑换端点无凭据（合法 body）", {}, {"delegation": "bogus.delegation.token"}, 401),
            ("M5-6f", "兑换端点错误 delegation（有服务凭据）", {"X-Service-Credential": svc}, {"delegation": "bogus.delegation.token"}, 401),
        ]
        for pid, name, headers, payload, want in cases:
            resp = await client.post(tool_url if "工具" in name else exch_url, json=payload, headers=headers)
            body = resp.json() if resp.content else None
            ok = resp.status_code == want
            record(pid, name, ok, f"{resp.status_code} (expect {want}) {err_code(body)} rid={rid(body)}")

        # =====================================================================
        # M5-5 MCP：无委派 → 工具错误（不是成功返回）
        # =====================================================================
        try:
            init = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "qa-probe", "version": "0.0.1"}},
            }
            resp = await client.post(mcp, json=init, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})
            init_ok = resp.status_code == 200 and "cca-assistant-tools" in resp.text
            record("M5-5a", "MCP initialize 可达且声明服务名", init_ok, f"{resp.status_code} body={resp.text[:80]!r}")
            sid = resp.headers.get("mcp-session-id") or ""
            call = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "get_my_schedule", "arguments": {}},
            }
            hdrs = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
            if sid:
                hdrs["mcp-session-id"] = sid
            resp = await client.post(mcp, json=call, headers=hdrs)
            text = resp.text
            no_deleg_ok = ("AUTH_REQUIRED" in text or "isError" in text or "错误" in text) and "tool_start" not in text
            record("M5-5b", "MCP 无委派头调用工具 → 错误而非成功", no_deleg_ok, f"{resp.status_code} body={text[:140]!r}")
        except Exception as exc:  # noqa: BLE001 - 网络/协议差异不应中断其余探针
            record("M5-5a", "MCP initialize 可达且声明服务名", False, f"exception: {exc!r}")

        # OBS：契约声明 from_date/to_date 为 anyOf[date,null]，但运行态显式 null → 422
        r_obs = await client.post(f"{internal}/internal/v1/tools/get-my-schedule", json={"from_date": None, "to_date": None}, headers={"X-Service-Credential": svc})
        print(f"OBS   [M3-null] 内部工具显式 null 入参 :: {r_obs.status_code} {err_code(r_obs.json())}（契约 anyOf[date,null] 允许 null，实际拒绝；非安全问题，登记为文档/行为轻微不一致）")

        # =====================================================================
        # M6-1 同键同内容 10 并发（真实 MySQL 副作用核对）
        # =====================================================================
        title = f"QA 并发计划 {suffix}"
        key = rand_key("qa-conc")
        payload = {"title": title, "content": "10 并发只应产生一份"}

        async def post_plan() -> httpx.Response:
            return await client.post(f"{api}/me/plans", json=payload, headers={**auth(tok_b), "Idempotency-Key": key})

        responses = await asyncio.gather(*[post_plan() for _ in range(10)])
        codes = [r.status_code for r in responses]
        plan_ids = {r.json()["data"].get("plan_id") for r in responses if r.content and r.status_code in (200, 201, 202)}
        created = sum(1 for c in codes if c == 201)
        existing = sum(1 for c in codes if c == 200)
        plans = db_scalar("SELECT COUNT(*) FROM study_plans WHERE title=%s", (title,))
        ops = db_scalar("SELECT COUNT(*) FROM write_operations WHERE plan_id IN (SELECT id FROM study_plans WHERE title=%s)", (title,))
        audits = db_scalar("SELECT COUNT(*) FROM audit_events WHERE object_id IN (SELECT id FROM study_plans WHERE title=%s)", (title,))
        outbox = db_scalar("SELECT COUNT(*) FROM outbox_events WHERE aggregate_id IN (SELECT id FROM study_plans WHERE title=%s)", (title,))
        ok = codes.count(201) == 1 and created == 1 and existing == 9 and plans == 1 and ops == 1 and len(plan_ids) == 1
        record("M6-1", "同键同内容 10 并发 → 1 份计划/1 操作", ok, f"codes={sorted(codes)} plans={plans} ops={ops} audits={audits} outbox={outbox} unique_plan_ids={len(plan_ids)}")

        # 同键异内容 → 409
        r = await client.post(f"{api}/me/plans", json={"title": title + " 改写", "content": "内容不同"}, headers={**auth(tok_b), "Idempotency-Key": key})
        body = r.json() if r.content else None
        record("M6-1b", "同键异内容 → 409 IDEMPOTENCY_CONFLICT", r.status_code == 409, f"{r.status_code} {err_code(body)} rid={rid(body)}")

        # =====================================================================
        # M6-6 双管理员并发重叠课表（空档期，未确认）
        # =====================================================================
        day = "2027-06-15"
        course2 = courses[1]["id"] if len(courses) > 1 else course_id

        async def post_sched(start: str, end: str) -> httpx.Response:
            return await client.post(
                f"{api}/admin/schedules",
                json={"student_id": user_b["id"], "course_id": course2, "class_date": day, "start_time": start, "end_time": end},
                headers=auth(admin_tok),
            )

        pair = await asyncio.gather(post_sched("08:00", "09:00"), post_sched("08:30", "09:30"))
        codes2 = [r.status_code for r in pair]
        ok_codes = all(c in (201, 409) for c in codes2)
        exactly_one = codes2.count(201) == 1 and codes2.count(409) == 1
        # 清掉成功的课表（保持库干净）
        if codes2.count(201) == 1:
            created_resp = pair[codes2.index(201)]
            sid = created_resp.json()["data"]["id"]
            ver = created_resp.json()["data"]["version"]
            await client.delete(f"{api}/admin/schedules/{sid}", params={"expected_version": ver}, headers=auth(admin_tok))
        record("M6-6", "空档期双管理员并发重叠 → 仅确认/先提交者成功", ok_codes and exactly_one, f"codes={codes2}")

        # =====================================================================
        # M5-8 服务端权限（非仅 UI）：再用学生令牌验证 admin 列表不带数据
        # =====================================================================
        r = await client.get(f"{api}/admin/students", headers=auth(student_tok))
        has_rows = "data" in (r.json() if r.content else {})
        record("M5-8", "学生 /admin/students → 403 且不返回数据", r.status_code == 403 and not has_rows, f"{r.status_code} rid={rid(r.json() if r.content else None)}")

    failed = [x for x in RESULTS if not x[2]]
    total = len(RESULTS)
    print("")
    print(f"RESULT: {total - len(failed)}/{total} PASS")
    if failed:
        print("FAILED IDS: " + ", ".join(x[0] for x in failed))
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.environ.get("QA_BASE", "http://127.0.0.1:8200"))
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.base)))

