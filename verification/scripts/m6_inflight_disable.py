"""M6-4 独立验证：禁用与在途保存/创建并发（真实 HTTP + 真实 MySQL 行锁编排）。

复现 P05-PREP F-01 的场景，但**通过真实 HTTP socket**（8200）而不是 ASGI 进程内调用：
  1) 学生 C 登录（认证发生在"尚 enabled"时）；
  2) 测试连接持 `users(C)` 行锁（SELECT ... FOR UPDATE）；
  3) 管理员禁用 C（请求排在锁后）与 C 的写计划请求（认证已通过、随后排在同一把锁后）；
  4) 释放锁 → 禁用先提交，写请求再获锁；
  5) 断言：禁用 200 且 enabled=false；写请求 401 SESSION_EXPIRED；`study_plans` 无新增。

期望（冻结版本）：写请求在锁内复核 enabled 失败 → 不落库。若落库 → 缺陷（F-01 回归）。

用法：
  .\\.venv\\Scripts\\python.exe verification\\scripts\\m6_inflight_disable.py
"""

from __future__ import annotations

import asyncio
import random
import string
import sys
import time
import uuid

import httpx
import pymysql

API = "http://127.0.0.1:8200/api/v1"
DB = dict(host="127.0.0.1", port=33061, user="root", password="cca_dev_root", database="cca_test_release")


def db_conn():
    return pymysql.connect(**DB, autocommit=False)


def count_plans(user_id: str) -> int:
    conn = pymysql.connect(**DB, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM study_plans WHERE user_id=%s", (user_id,))
            return int(cur.fetchone()[0])
    finally:
        conn.close()


async def main() -> int:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    acc = f"qa_race_{suffix}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{API}/auth/login", json={"account": "admin_demo", "password": "demo1234"})
        admin = r.json()["data"]["access_token"]
        ah = {"Authorization": f"Bearer {admin}"}

        r = await client.post(f"{API}/admin/students", json={"account": acc, "display_name": "race", "initial_password": "demo1234"}, headers=ah)
        assert r.status_code == 201, (r.status_code, r.text[:300])
        user = r.json()["data"]
        uid = user["id"]

        r = await client.post(f"{API}/auth/login", json={"account": acc, "password": "demo1234"})
        assert r.status_code == 200, (r.status_code, r.text[:300])
        token = r.json()["data"]["access_token"]
        sh = {"Authorization": f"Bearer {token}"}

        # 1) 持学生行锁
        lock = db_conn()
        cur = lock.cursor()
        cur.execute("SELECT id FROM users WHERE id=%s FOR UPDATE", (uid,))
        assert cur.fetchone(), "user row not found"

        # 2) 禁用请求（排锁后）
        admin_task = asyncio.create_task(
            client.patch(f"{API}/admin/students/{uid}", json={"enabled": False, "expected_version": user["version"]}, headers=ah)
        )
        await asyncio.sleep(0.3)

        # 3) 学生写请求（认证已通过；同样排锁后）
        key = "qa-race-" + uuid.uuid4().hex[:20]
        write_task = asyncio.create_task(
            client.post(f"{API}/me/plans", json={"title": f"QA race {suffix}", "content": "in-flight write"}, headers={**sh, "Idempotency-Key": key})
        )
        await asyncio.sleep(0.3)

        # 4) 释放行锁（禁用先获锁提交）
        lock.commit()
        lock.close()

        admin_resp = await admin_task
        write_resp = await write_task

    plans = count_plans(uid)
    code = ""
    try:
        code = write_resp.json()["error"]["code"]
    except Exception:
        pass
    disable_ok = admin_resp.status_code == 200 and admin_resp.json()["data"]["enabled"] is False
    write_blocked = write_resp.status_code == 401 and code == "SESSION_EXPIRED"
    no_plan = plans == 0

    print(f"disable: {admin_resp.status_code} enabled={admin_resp.json().get('data', {}).get('enabled')}")
    print(f"in-flight write: {write_resp.status_code} code={code} plans_in_db={plans}")
    ok = disable_ok and write_blocked and no_plan
    print(("PASS" if ok else "FAIL") + "  [M6-4] 禁用先提交 → 在途写入被锁内复核阻断且不落库")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(asyncio.run(main()))
