"""G5 反向注入：MCP 双跳委派（audience / 过期 / scope / 会话绑定 / 签名 / TTL 放大）。

用开发签名密钥（TBD-03 未冻结，默认值）自签委派，证明 MCP 与内部 API 不是"只检查有没有头"：
  G5-1 aud=cca-internal 当 MCP 用           → 受众不匹配（FORBIDDEN）
  G5-2 已过期（exp 在过去）                  → 委派已过期（AUTH_REQUIRED）
  G5-3 scope 缺少 docs:search               → 范围不足（FORBIDDEN）
  G5-4 会话绑定伪造（session_id 不存在）    → 兑换失败（工具错误，绝不 200 成功）
  G5-5 同上，直接打内部兑换端点             → 401/403
  G5-6 错误签名密钥                          → 凭据无效（AUTH_REQUIRED）
  G5-7 exp-iat=120s（中间服务放大 TTL）      → 有效期超上限（FORBIDDEN）

输出 `PASS/FAIL [G5-n] ...`；任一不满足 → 退出码 1。
"""

from __future__ import annotations

import json
import secrets
import sys
import time

import httpx
import jwt

MCP = "http://127.0.0.1:8202/mcp"
INTERNAL = "http://127.0.0.1:8201"
SVC = "dev-internal-token"
KEY = "dev-delegation-key-not-for-production"
WRONG_KEY = "not-the-delegation-key"
ISSUER = "cca-api"


def mint(aud: str, *, scope=("schedule:read",), iat=None, exp=None, key=KEY, session_id="ses_fake_qa_000", sub="usr_fake_qa_000") -> str:
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "aud": aud,
        "sub": sub,
        "session_id": session_id,
        "auth_version": 1,
        "request_id": "req_qa_g5_%s" % secrets.token_hex(6),
        "conversation_id": "cnv_fake_qa_000",
        "scope": list(scope),
        "fence": 1,
        "iat": iat if iat is not None else now,
        "exp": exp if exp is not None else now + 25,
        "jti": secrets.token_urlsafe(12),
    }
    return str(jwt.encode(payload, key, algorithm="HS256"))


def mcp_error_text(resp: httpx.Response) -> tuple[bool, str]:
    text = resp.text
    is_error = '"isError":true' in text or '"isError": true' in text
    code = ""
    for candidate in ("FORBIDDEN", "AUTH_REQUIRED", "委派受众不匹配", "委派已过期", "委派范围不足", "委派有效期超出上限", "委派凭据无效", "缺少委派凭据", "MCP_UNAVAILABLE"):
        if candidate in text:
            code += candidate + " "
    return is_error, code.strip()


def call_tool(client: httpx.Client, session_id: str, token: str, tool: str, arguments: dict) -> httpx.Response:
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if session_id:
        headers["mcp-session-id"] = session_id
    if token:
        headers["X-CCA-Delegation"] = token
        headers["X-Service-Credential"] = SVC
    payload = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}
    return client.post(MCP, json=payload, headers=headers)


def main() -> int:
    ok = True
    with httpx.Client(timeout=30) as client:
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "qa-g5", "version": "0"}}}
        r = client.post(MCP, json=init, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})
        sid = r.headers.get("mcp-session-id") or ""

        cases = [
            ("G5-1", "aud=cca-internal 当 MCP 用", mint("cca-internal"), "get_my_schedule", {}, ("FORBIDDEN", "受众")),
            ("G5-2", "已过期委派", mint("cca-mcp", iat=int(time.time()) - 60, exp=int(time.time()) - 30), "get_my_schedule", {}, ("AUTH_REQUIRED", "过期")),
            ("G5-3", "scope 缺 docs:search", mint("cca-mcp", scope=("schedule:read",)), "search_course_docs", {"query": "q"}, ("FORBIDDEN", "范围")),
            ("G5-4", "会话绑定伪造", mint("cca-mcp", scope=("docs:search",)), "search_course_docs", {"query": "q"}, ("AUTH_REQUIRED", "FORBIDDEN", "EXECUTION", "MCP_UNAVAILABLE", "SESSION_EXPIRED", "会话")),
            ("G5-6", "错误签名密钥", mint("cca-mcp", key=WRONG_KEY), "get_my_schedule", {}, ("AUTH_REQUIRED", "凭据")),
            ("G5-7", "TTL 放大到 120s", mint("cca-mcp", iat=int(time.time()), exp=int(time.time()) + 120), "get_my_schedule", {}, ("FORBIDDEN", "有效期")),
        ]
        for pid, name, token, tool, args, needles in cases:
            resp = call_tool(client, sid, token, tool, args)
            is_error, code = mcp_error_text(resp)
            hit = is_error and any(n in resp.text for n in needles)
            print(("PASS" if hit else "FAIL") + f"  [{pid}] {name} :: isError={is_error} 命中={code!r} status={resp.status_code}")
            ok = ok and hit

        # G5-5 直接打内部兑换端点（正确服务凭据 + 伪造会话的合法签名委派）
        token = mint("cca-mcp", scope=("docs:search",))
        r = client.post(f"{INTERNAL}/internal/v1/delegations/exchange", json={"delegation": token}, headers={"X-Service-Credential": SVC})
        hit = r.status_code in (401, 403)
        print(("PASS" if hit else "FAIL") + f"  [G5-5] 内部兑换：合法签名但会话伪造 :: {r.status_code} {r.text[:120]!r}")
        ok = ok and hit

    print("G5 RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())

