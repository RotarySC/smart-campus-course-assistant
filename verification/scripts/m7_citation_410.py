"""M7 补充：引用 → 删除文档 → 引用展开 410（Phase-04 §6 遗留缺口，独立端到端验证）。

流程（真实 HTTP 8200 + 常驻 worker + 真实文件存储）：
  1) 管理员上传含唯一 marker 的 txt（202），轮询至批次 published；
  2) 学生提问（确定性 Provider 触发资料检索），断言 done.citations 非空；
  3) GET /citations/{id} → 200 且有正文，且不出现存储键（uploads/ / attempts/ 等）；
  4) 管理员 DELETE 文档（202），等 worker 清理完成（text → 404）；
  5) 再 GET 同一 citation → 期望 410 CITATION_UNAVAILABLE，且无正文。

输出逐条 PASS/FAIL；退出码 0 表示闭环成立。证据建议 Tee 到 verification/evidence/M7-citation-410.log。
"""

from __future__ import annotations

import json
import sys
import time
import uuid

import httpx

API = "http://127.0.0.1:8200/api/v1"
RESULTS: list[tuple[str, bool, str]] = []


def rec(pid: str, ok: bool, detail: str) -> None:
    RESULTS.append((pid, ok, detail))
    print(("PASS" if ok else "FAIL") + f"  [{pid}] {detail}")


def login(client: httpx.Client, account: str) -> str:
    r = client.post(f"{API}/auth/login", json={"account": account, "password": "demo1234"})
    assert r.status_code == 200, (account, r.status_code, r.text[:200])
    return r.json()["data"]["access_token"]


def chat(client: httpx.Client, token: str, message: str) -> list[dict]:
    payload = {"client_request_id": "qa-cite-" + uuid.uuid4().hex[:16], "message": message}
    events: list[dict] = []
    with client.stream("POST", f"{API}/chat/stream", json=payload, headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}) as resp:
        text = "".join(resp.iter_text()).replace("\r\n", "\n")
    for block in text.split("\n\n"):
        name = data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if name and data:
            try:
                events.append({"event": name, "data": json.loads(data)})
            except Exception:
                pass
    return events


def main() -> int:
    marker = "QA-CITE-" + uuid.uuid4().hex[:8].upper()
    body = (
        "实验课预习要求\n\n"
        f"{marker}：实验课预习要求包括阅读实验指导书第 3 章、完成预习报告，并在上课前提交电子版；"
        "实验课开始前需通过安全测验。\n\n"
    ) * 3

    with httpx.Client(timeout=120) as client:
        admin = login(client, "admin_demo")
        student = login(client, "student_demo")
        ah = {"Authorization": f"Bearer {admin}"}
        sh = {"Authorization": f"Bearer {student}"}

        r = client.post(f"{API}/admin/document-batches", files={"files": (f"qa-cite-{marker}.txt", body.encode("utf-8"), "text/plain")}, headers=ah)
        rec("M7-410-1", r.status_code == 202, f"上传批次 → {r.status_code} batch={r.json().get('data', {}).get('batch_id')} rid={r.json().get('request_id')}")
        if r.status_code != 202:
            return 1
        batch_id = r.json()["data"]["batch_id"]

        state = ""
        doc_id = ""
        doc_version = None
        for _ in range(60):
            r = client.get(f"{API}/admin/document-batches/{batch_id}", headers=ah)
            data = r.json()["data"]
            state = data["state"]
            docs = data.get("documents") or []
            if docs:
                doc_id = docs[0]["id"]
                doc_version = docs[0].get("version")
            if state in ("published", "failed"):
                break
            time.sleep(1)
        rec("M7-410-2", state == "published" and bool(doc_id), f"批次发布 → state={state} doc={doc_id}")

        events = chat(client, student, "实验课预习要求是什么？")
        tool_end = next((e["data"] for e in events if e["event"] == "tool_end"), {})
        done = next((e["data"] for e in events if e["event"] == "done"), {})
        citations = done.get("citations") or []
        rec("M7-410-3", bool(tool_end.get("success")) and len(citations) >= 1, f"检索 tool_end success={tool_end.get('success')} citations={len(citations)} rid={done.get('request_id')}")
        if not citations:
            return 1

        # 同一问题可能命中多份文档（如基线样本）；必须挑出属于本次上传文档的那条引用
        ref_id = None
        ref_hit = None
        for ref in citations:
            cand = ref if isinstance(ref, str) else ref.get("reference_id")
            r_probe = client.get(f"{API}/citations/{cand}", headers=sh)
            if r_probe.status_code != 200:
                continue
            data_probe = r_probe.json().get("data") or {}
            rid_doc = ((data_probe.get("reference") or {}).get("document_id"))
            if rid_doc == doc_id:
                ref_id = cand
                ref_hit = r_probe
                break
        rec("M7-410-3b", ref_id is not None, f"引用归属本次上传文档（citations={len(citations)}, doc={doc_id}, ref={ref_id}）")
        if ref_id is None:
            return 1
        r = ref_hit
        cite_text = ""
        try:
            cite_text = json.dumps(r.json()["data"], ensure_ascii=False)
        except Exception:
            cite_text = r.text
        no_key_leak = not any(k in cite_text for k in ("uploads/", "attempts/", "documents/", "sealed-original", "extracted-text"))
        rec("M7-410-4", r.status_code == 200 and len(cite_text) > 20 and no_key_leak, f"引用展开 → {r.status_code} {len(cite_text)} 字 存储键泄漏={not no_key_leak} rid={r.json().get('request_id')}")

        r = client.delete(f"{API}/admin/documents/{doc_id}", params={"expected_version": doc_version}, headers=ah)
        rec("M7-410-5", r.status_code == 202, f"删除文档（expected_version={doc_version}） → {r.status_code} rid={r.json().get('request_id')}")

        cleaned = False
        for _ in range(90):
            r = client.get(f"{API}/admin/documents/{doc_id}/text", headers=ah)
            if r.status_code == 404:
                cleaned = True
                break
            time.sleep(1)
        rec("M7-410-6", cleaned, "worker 清理完成（文本 404）")

        r = client.get(f"{API}/citations/{ref_id}", headers=sh)
        rjson = r.json()
        code = (rjson.get("error") or {}).get("code")
        body_has_text = "text" in json.dumps(rjson.get("data") or {}, ensure_ascii=False)
        rec("M7-410-7", r.status_code == 410 and code == "CITATION_UNAVAILABLE" and not body_has_text, f"删除后引用 → {r.status_code} {code} rid={rjson.get('request_id')}")

    failed = [x for x in RESULTS if not x[1]]
    print(f"\nRESULT: {len(RESULTS) - len(failed)}/{len(RESULTS)} PASS")
    return 0 if not failed else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
