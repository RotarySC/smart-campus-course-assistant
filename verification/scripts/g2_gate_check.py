"""G2 门禁复核：管理员鉴权旁路必须让"学生打 /admin/** → 403"这条门禁 FAIL。

断言（门禁）：学生 Bearer 调 `GET /admin/students` → 403 FORBIDDEN。
  - 健康实例 8200：PASS（403）
  - 坏实例 8299（g2_broken_app.py：get_admin 旁路）：预期非 403 → 断言 FAIL
  - 还原后再打健康实例：PASS（403）

输出 `PASS/FAIL [G2...]`；退出码 0 表示反向注入闭环成立（破坏→FAIL→还原→PASS）。
"""

from __future__ import annotations

import sys

import httpx

HEALTHY = "http://127.0.0.1:8200/api/v1"
BROKEN = "http://127.0.0.1:8299/api/v1"


def student_call(base: str) -> tuple[int, str]:
    with httpx.Client(timeout=20) as client:
        r = client.post(f"{base}/auth/login", json={"account": "student_demo", "password": "demo1234"})
        if r.status_code != 200:
            return -1, f"login failed {r.status_code}"
        token = r.json()["data"]["access_token"]
        r = client.get(f"{base}/admin/students", params={"page_size": 5}, headers={"Authorization": f"Bearer {token}"})
    code = ""
    try:
        code = r.json()["error"]["code"]
    except Exception:
        pass
    return r.status_code, code


def main() -> int:
    ok = True

    status, code = student_call(HEALTHY)
    gate_healthy = status == 403 and code == "FORBIDDEN"
    print(("PASS" if gate_healthy else "FAIL") + f"  [G2-1] 健康实例：学生 /admin/students :: {status} {code}（门禁应 PASS）")
    ok = ok and gate_healthy

    status, code = student_call(BROKEN)
    gate_broken = status != 403  # 旁路后必须不再 403（证明门禁抓得到）
    print(("PASS" if gate_broken else "FAIL") + f"  [G2-2] 鉴权旁路实例：学生 /admin/students :: {status} {code}（门禁必须 FAIL）")
    ok = ok and gate_broken

    status, code = student_call(HEALTHY)
    restored = status == 403 and code == "FORBIDDEN"
    print(("PASS" if restored else "FAIL") + f"  [G2-3] 还原健康实例 :: {status} {code}")
    ok = ok and restored

    print("G2 RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
