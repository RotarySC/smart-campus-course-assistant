"""G3 反向注入：SSE 终态唯一 / 事件合法性门禁（用真实流录制 + 篡改副本）。

步骤：
  1) 从真实 `POST /chat/stream` 录制事件序列（8200，真实 socket）；
  2) 用 `docs/backend/sse_events_v0.1.schema.json` 的 oneOf 分支 + 流级约束校验：
     - 事件名必须属于 schema 声明的 6 类；
     - 每个事件必须有 id/event/data 且 data.seq == int(id)（单调，从 1 递增）；
     - 终态（done/error）恰好一个，且必须是最后一个事件；
  3) 原始序列必须 PASS；
  4) 向副本注入第二条 done（或把 done 提前）后，同一校验器必须 FAIL（证明门禁非空转）。

输出：`PASS/FAIL [G3...]`；记录写入 verification/evidence/sse-recorded.json。
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
API = "http://127.0.0.1:8200/api/v1"
SCHEMA = ROOT / "docs" / "backend" / "sse_events_v0.1.schema.json"
OUT = ROOT / "verification" / "evidence" / "sse-recorded.json"
TERMINAL = {"done", "error"}


def schema_events() -> set[str]:
    spec = json.loads(SCHEMA.read_text(encoding="utf-8"))
    names: set[str] = set()
    branches = spec.get("oneOf") or []
    for branch in branches:
        const = ((branch.get("properties") or {}).get("event") or {}).get("const")
        if const:
            names.add(str(const))
    return names


def validate(events: list[dict], allowed: set[str]) -> list[str]:
    errors: list[str] = []
    for ev in events:
        name = ev.get("event")
        data = ev.get("data") or {}
        if name not in allowed:
            errors.append(f"未知事件名 {name!r}")
            continue
        if "id" not in ev or "data" not in ev:
            errors.append(f"事件 {name} 缺 id/data")
        try:
            if int(str(ev.get("id"))) != int(data.get("seq")):
                errors.append(f"事件 {name} 的 id 与 data.seq 不一致")
        except Exception:
            errors.append(f"事件 {name} 的 id/seq 非整数")
    seqs = []
    for ev in events:
        try:
            seqs.append(int((ev.get("data") or {}).get("seq")))
        except Exception:
            seqs.append(-1)
    if seqs != sorted(seqs) or len(set(seqs)) != len(seqs):
        errors.append(f"seq 非严格单调：{seqs}")
    terminals = [e for e in events if e.get("event") in TERMINAL]
    if len(terminals) != 1:
        errors.append(f"终态事件应恰 1 个，实际 {len(terminals)}")
    elif events and events[-1].get("event") not in TERMINAL:
        errors.append("终态事件不在流末尾")
    return errors


async def record_stream() -> list[dict]:
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{API}/auth/login", json={"account": "student_demo", "password": "demo1234"})
        token = r.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}
        payload = {"client_request_id": "qa-g3-" + uuid.uuid4().hex[:16], "message": "明天有什么课？"}
        events: list[dict] = []
        async with client.stream("POST", f"{API}/chat/stream", json=payload, headers=headers) as resp:
            text = ""
            async for chunk in resp.aiter_text():
                text += chunk
            for block in text.replace("\r\n", "\n").split("\n\n"):
                if not block.strip():
                    continue
                ev_name = None
                ev_data = None
                ev_id = None
                for line in block.split("\n"):
                    if line.startswith("event:"):
                        ev_name = line[len("event:"):].strip()
                    elif line.startswith("data:"):
                        ev_data = line[len("data:"):].strip()
                    elif line.startswith("id:"):
                        ev_id = line[len("id:"):].strip()
                if ev_name is None and ev_data is not None:
                    try:
                        parsed = json.loads(ev_data)
                    except Exception:
                        continue
                    if isinstance(parsed, dict) and "event" in parsed:
                        events.append({"id": str(parsed.get("id") or ""), **parsed})
                        continue
                if ev_name and ev_data is not None:
                    try:
                        data = json.loads(ev_data)
                    except Exception:
                        data = {"raw": ev_data}
                    events.append({"id": ev_id or str(data.get("seq") or ""), "event": ev_name, "data": data})
        return events


async def main() -> int:
    allowed = schema_events()
    events = await record_stream()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"events": events}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"recorded {len(events)} events -> {OUT.relative_to(ROOT)}（事件名={sorted({e.get('event') for e in events})}）")

    ok = True
    errors = validate(events, allowed)
    if errors:
        ok = False
        print("FAIL  [G3-0] 真实流未通过校验：" + "; ".join(errors))
    else:
        print(f"PASS  [G3-0] 真实流通过 schema/终态唯一/seq 单调校验（{len(events)} 事件）")

    # 注入 1：重复终态
    doctored = json.loads(json.dumps(events))
    done = next((e for e in doctored if e.get("event") == "done"), None)
    if done is None:
        print("SKIP  [G3-1] 录制流无 done 事件，无法注入")
        ok = False
    else:
        dup = json.loads(json.dumps(done))
        dup["id"] = str(int(dup["data"]["seq"]) + 1)
        dup["data"]["seq"] = int(dup["data"]["seq"]) + 1
        doctored.append(dup)
        errs = validate(doctored, allowed)
        if errs:
            print("PASS  [G3-1] 注入第二条 done → 校验器 FAIL（终态唯一门禁有效）：" + "; ".join(errs))
        else:
            print("FAIL  [G3-1] 注入第二条 done 后校验器仍 PASS（门禁空转）")
            ok = False

    # 注入 2：把终态挪到中间（终态必须最后）
    doctored2 = [e for e in events if e.get("event") not in TERMINAL]
    terminals = [e for e in events if e.get("event") in TERMINAL]
    if terminals:
        doctored2.insert(max(0, len(doctored2) // 2), terminals[0])
        errs = validate(doctored2, allowed)
        if errs:
            print("PASS  [G3-2] 终态被挪到中间 → 校验器 FAIL：" + "; ".join(errs))
        else:
            print("FAIL  [G3-2] 终态不在末尾却仍 PASS（门禁空转）")
            ok = False

    # 还原：原始序列再校验一次必须 PASS
    errs = validate(json.loads(json.dumps(events)), allowed)
    if not errs:
        print("PASS  [G3-3] 还原原始序列 → 校验器 PASS")
    else:
        print("FAIL  [G3-3] 还原后仍失败：" + "; ".join(errs))
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(asyncio.run(main()))
