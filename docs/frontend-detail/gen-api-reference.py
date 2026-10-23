# -*- coding: utf-8 -*-
r"""
从 OpenAPI 生成前端字段参考   docs/frontend-detail/gen-api-reference.py

为什么要生成而不是手写：4 位作者并行写前端详细设计，最容易出现的错就是**字段名写错**
（例如把草稿的 `expected_draft_version` 写成计划里的 `expected_version`，
或误以为 `/chat/stream` 用 `Idempotency-Key` 头——实际它用 body 里的 `client_request_id`）。
手抄必错，所以从 `docs/backend/openapi_v0.1.json` 机械生成一份参考，作者只读不写。

产出：docs/frontend-detail/API-REFERENCE.md

运行：$env:PYTHONIOENCODING="utf-8"; python docs\frontend-detail\gen-api-reference.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "docs", "backend", "openapi_v0.1.json")
OUT = os.path.join(HERE, "API-REFERENCE.md")
REF = "$" + "ref"


def main():
    spec = json.load(open(SRC, encoding="utf-8"))
    comp = spec.get("components", {}).get("schemas", {})
    all_comp = {}
    for section in spec.get("components", {}).values():
        if isinstance(section, dict):
            all_comp.update(section)

    def deref(n, depth=0):
        while isinstance(n, dict) and REF in n and depth < 8:
            name = n[REF].split("/")[-1]
            n = comp.get(name) or all_comp.get(name)
            if n is None:
                return {}
            depth += 1
        return n

    def expand(n, depth=0):
        n = deref(n)
        if not isinstance(n, dict):
            return None
        if "properties" not in n:
            if "allOf" in n:
                merged = {}
                for x in n["allOf"]:
                    e = expand(x, depth)
                    if e:
                        merged.update(e)
                return merged or None
            if "items" in n:
                return expand(n["items"], depth)
            return None
        out = {}
        for k, v in n["properties"].items():
            v2 = deref(v)
            out[k] = v2
        return out

    def typ(v):
        v = deref(v)
        if not isinstance(v, dict):
            return "?"
        if "enum" in v:
            return "enum(" + "|".join(map(str, v["enum"])) + ")"
        t = v.get("type")
        if t == "array":
            it = deref(v.get("items", {}))
            if isinstance(it, dict) and "enum" in it:
                return "array<enum(" + "|".join(map(str, it["enum"])) + ")>"
            if isinstance(it, dict) and (it.get("type") == "object" or "properties" in it):
                return "array<object>"
            return "array<%s>" % (it.get("type", "?") if isinstance(it, dict) else "?")
        if t == "object" or "properties" in v:
            return "object"
        return t or "?"

    def fmt(fields, indent="    "):
        if not fields:
            return []
        lines = []
        for k, v in fields.items():
            req = ""
            lines.append("%s%s %s%s" % (indent, k, typ(v), req))
        return lines

    rows = []
    paths = spec["paths"]
    for path in sorted(paths):
        for method in ("get", "post", "put", "patch", "delete"):
            op = paths[path].get(method)
            if not isinstance(op, dict):
                continue
            L = []
            L.append("### `%s %s`\n" % (method.upper(), path))
            if op.get("summary"):
                L.append("%s\n" % op["summary"])
            internal = path.startswith("/internal/")
            if internal:
                L.append("> **内部接口：前端不得调用。**\n")
            rb = op.get("requestBody", {}).get("content", {})
            if rb:
                for ct_name, ct in rb.items():
                    f = expand(ct.get("schema"))
                    L.append("**请求体**（`%s`）%s\n" % (ct_name, "（multipart 上传）" if "multipart" in ct_name else ""))
                    L.append("```")
                    L += [x.strip() for x in fmt(f)] or ["(无字段)"]
                    L.append("```")
            pars = op.get("parameters") or []
            if pars:
                L.append("**参数/头**\n")
                L.append("| 位置 | 名 | 类型 | 必填 |")
                L.append("| --- | --- | --- | --- |")
                for p in pars:
                    p2 = deref(p)
                    L.append("| %s | `%s` | %s | %s |" % (
                        p2.get("in", "?"), p2.get("name", "?"), typ(p2.get("schema", {})),
                        "是" if p2.get("required") else "否"))
            if "Idempotency-Key" in json.dumps(op):
                L.append("\n> 该端点接受 `Idempotency-Key` 请求头。")
            L.append("")
            L.append("**响应**\n")
            L.append("| 码 | `data` 字段 |")
            L.append("| --- | --- |")
            for code, r in sorted(op.get("responses", {}).items()):
                sch = r.get("content", {}).get("application/json", {}).get("schema")
                desc = (r.get("description") or "").replace("\n", " ")[:80]
                dat = ""
                if sch:
                    f = expand(sch)
                    df = expand(f.get("data")) if f and "data" in f else None
                    if df:
                        dat = "<br>".join("`%s`: %s" % (k, typ(v)) for k, v in df.items())
                    elif f:
                        dat = "、".join("`%s`" % k for k in f) or "—"
                L.append("| %s | %s |" % (code, dat or desc or "—"))
            # 事件流
            ct = op.get("responses", {}).get("200", {}).get("content", {})
            if any("event-stream" in k for k in ct):
                L.append("\n> 响应为 `text/event-stream`：解析口径见 `docs/backend/sse_events_v0.1.schema.json`。")
            rows.append("\n".join(L))

    codes = set()
    def walk(o):
        if isinstance(o, dict):
            if "enum" in o and isinstance(o["enum"], list):
                for x in o["enum"]:
                    if isinstance(x, str) and x.isupper() and "_" in x:
                        codes.add(x)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(spec)
    async_codes = ["NO_TEXT_EXTRACTED", "DOCUMENT_ENCRYPTED", "PARSE_FAILED",
                   "EMBEDDING_FAILED", "CLEANUP_FAILED", "SERVICE_RESTARTED"]
    # SRS §8 列出但 OpenAPI 的 Error 枚举里没有的码。两者不一致时，前端以 SRS §8 为准
    # （SRS 承载"客户端行为"这一列，是前端要实现的语义），并把差异显式记下来而不是抹平。
    srs_only = sorted(c for c in ["FORBIDDEN"] if c not in codes)
    allowed = sorted(codes | set(srs_only))

    head = [
        "# 前端字段参考（自动生成，只读）",
        "",
        "> 由 `docs/frontend-detail/gen-api-reference.py` 从 `docs/backend/openapi_v0.1.json` 生成，**请勿手改**。",
        "> 用途：并行写作时**字段名的唯一来源**。文档里出现的每个端点与字段都必须能在这里查到。",
        "",
        "## 0. 通用约定",
        "",
        "- **所有响应都带信封**：`{ request_id, data }`。`request_id` 在前端用于 `NFR-OBS-001` 的贯通关联。",
        "- **`request_id` 也可能出现在响应头**，前端取 body 的为准；SSE 事件的 `request_id` 见 SSE schema。",
        "- `/api/v1/*` 共 26 个，前端可用；`/internal/v1/*` 共 4 个，**前端不得调用**。",
        "",
        "### 同步错误码（前端允许集合，%d 个）" % len(allowed),
        "",
        "来源：`openapi_v0.1.json` 的 `Error` 枚举（%d 个）∪ `SRS §8`（%d 个）" % (len(codes), len(srs_only)),
        "",
        "```",
        "、".join(allowed),
        "```",
        "",
        "> **上游不一致（已登记，未抹平）**：`SRS §8` 列出了 %s，但 `openapi_v0.1.json` 的 `Error` 枚举里**没有**。"
        % ("、".join('`%s`' % c for c in srs_only) if srs_only else "（无）"),
        "> 前端以 `SRS §8` 为准（它承载了「客户端行为」这一列，是前端要实现的语义），"
        "因此允许集合是两者并集。这一点需要后端确认是 OpenAPI 漏写还是 SRS 多写；**在确认前，前端按并集实现并保留该码的处理分支**。",
        "",
        "### 异步任务码（SRS §8，%d 个，出现在文档批次/文件状态里，不是 HTTP 错误）" % len(async_codes),
        "",
        "```",
        "、".join(async_codes),
        "```",
        "",
        "## 1. 端点逐条",
        "",
    ]
    # ---- §2 组件 schema 附录：嵌套对象的字段也要能查到 ----
    # 为什么必须有这一节：端点表的响应 `data` 只展开顶层，嵌套对象会显示成 `object`。
    # 作者一旦用到 `Document` / `Error.error` / `FieldError` 这类嵌套字段，就没法在这里核对了，
    # 于是「每个字段都能在 API-REFERENCE 里查到」这条就名存实亡。独立验证者会抽查字段名，
    # 所以这里把所有组件 schema 逐条展开（含枚举取值与必填标记）。
    appendix = ["", "## 2. 组件 schema 附录（嵌套对象的字段在这里查）", "",
                "端点的响应 `data` 只展开顶层；`object` 字样表示嵌套，其字段在本节查。",
                "枚举取值全部列出，必填字段标 `*`。", ""]
    for name in sorted(comp):
        sch = deref(comp[name])
        if not isinstance(sch, dict):
            continue
        props = expand(sch)
        req = set(sch.get("required") or [])
        appendix.append("### `%s`\n" % name)
        if sch.get("description"):
            appendix.append("%s\n" % sch["description"].strip().replace("\n", " "))
        if not props:
            appendix.append("（无字段，或为 `oneOf`/`allOf` 组合，见 OpenAPI 原文）\n")
            continue
        appendix.append("| 字段 | 类型 | 必填 |")
        appendix.append("| --- | --- | --- |")
        for k, v in props.items():
            appendix.append("| `%s` | %s | %s |" % (k, typ(v), "是" if k in req else ""))
        appendix.append("")

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(head + rows + appendix) + "\n")
    n_pub = len([p for p in paths if not p.startswith("/internal/")])
    print("已写出 %s" % OUT)
    print("  端点 %d（公开 %d / 内部 %d）" % (len(paths), n_pub, len(paths) - n_pub))
    print("  组件 schema %d 个（嵌套字段附录）" % len(comp))
    print("  同步错误码 %d 个（openapi %d ∪ SRS §8 独有 %d）；异步任务码 %d 个"
          % (len(allowed), len(codes), len(srs_only), len(async_codes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
