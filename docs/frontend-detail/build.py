#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
前端详细设计组装器 + 契约检查   docs/frontend-detail/build.py

把 7 个分册拼装成单文件 `docs/校园课程智能助手_前端详细设计_v0.1.md`，
并在组装时做机械检查：章节编号、端点存在性、错误码合法性、字段名可解析、
违禁文案、store/路由名冻结、token 幽灵引用。

为什么这些检查必须做在组装期：4 位作者并行写作，最常见的错是**各自发明**——
发明端点、发明错误码、发明 token、发明 store 名。这类错在散文里读起来毫无破绽，
只能靠与 `openapi_v0.1.json` / `SRS §8` / `tokens.css` 的机械比对来抓。

运行：$env:PYTHONIOENCODING="utf-8"; python docs\frontend-detail\build.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "docs", "校园课程智能助手_前端详细设计_v0.1.md")
OPENAPI = os.path.join(ROOT, "docs", "backend", "openapi_v0.1.json")
TOKENS_CSS = os.path.join(ROOT, "design", "system", "tokens.css")
RB_CSS = os.path.join(ROOT, "design", "responsive", "rb.css")

PARTS = [
    ("10-baseline-and-modules.md", "1,2,3"),
    ("20-sse-client.md", "5"),
    ("30-session-and-state.md", "4,6"),
    ("40-routing-and-screens.md", "7,9"),
    ("50-design-system-and-a11y.md", "8,10,12"),
    ("60-forms-and-observability.md", "11,13,14,15"),
    ("90-open-items.md", "16"),
]
TOTAL_CHAPTERS = sum(len(c.split(",")) for _f, c in PARTS)

STORES = ["session", "chat", "schedules", "plans", "drafts", "writeOps", "admin", "ui"]
ROUTES = ["/login", "/assistant", "/me/schedules", "/me/plans", "/me/plans/:planId",
          "/admin/courses", "/admin/documents", "/admin/document-batches/:batchId",
          "/admin/schedules", "/admin/students"]
# 本文档**处方的**新 token：它们在 §16.3 的前置批次里才落地，落地后就不再是幽灵。
# 但必须显式登记，否则"处方一个新 token"与"写错一个 token 名"就分不出来了。
# 阶段 A（实现期）已落地 `--root-scroll-offset`（现为 `tokens.css` 里的真实 token，已移出本集合）。
PROPOSED_TOKENS = {"--appbar-scroll-offset"}
# 组件组名前缀（与 tokens.json 的 component 分组一致）。**不要**用 L2 前缀来猜，
# 否则 `.btn--danger` 里的 `--danger` 会被误判成 token（这个坑在设计系统那轮已踩过一次）。
GROUP_PREFIX = {"root", "focus", "skiplink", "sr", "appbar", "brand", "navlink", "tabbar",
                "wrap", "login", "btn", "chip", "pill", "notice", "steps", "empty", "card",
                "chat", "composer", "cite", "draft", "kv", "prose", "field", "control",
                "table", "utility"}
FORBIDDEN = ["正在思考", "AI 推理中", "推理过程", "思考中", "暂无数据", "暂无内容"]
# 这是**设计文档**不是产品 UI：排印符号（⚠ ✓ ✗ → 等）是正文用法，不算 emoji。
# 只把图形化 emoji 区段算违规。
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\uFE0F\u20E3]")
NEG = ["不得", "禁止", "不出现", "排除", "违禁", "反例", "误用", "不应", "没有", "不可", "不属于", "不要"]
NEG_WIN = 30

problems = []


def bad(kind, detail):
    problems.append((kind, detail))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def in_negation(text, idx, win=NEG_WIN):
    ls = text.rfind("\n", 0, idx) + 1
    le = text.find("\n", idx)
    line = text[ls:le if le >= 0 else len(text)]
    if any(n in line for n in NEG):
        return True
    return any(n in text[max(0, idx - win):idx] for n in NEG)


def raw_hits(text, needle):
    out, start = [], 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            return out
        if not in_negation(text, i):
            out.append(i)
        start = i + 1


def split_rows(tbl):
    return [r for r in tbl.splitlines() if r.strip().startswith("|")]


def strip_fences(text):
    """去掉 ``` 围栏代码块。标题类检查必须在围栏之外做——
    文档里会示范「往 README 里写什么」，其中的 `# 标题` 不是本文档的标题。"""
    out, in_fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def rewrite_part_links(text):
    """把分册里的相对链接改写成**最终文件视角**的正确路径。

    分册住在 `docs/frontend-detail/parts/`，最终文件住在 `docs/`。作者写链接时可能以三种基点为参照：
    （a）分册自身目录（`../../design/system/...`）、（b）`docs/frontend-detail/`（裸 `API-REFERENCE.md`）、
    （c）`docs/`（`design/system/...`）。逐个去试哪个基点能让目标真实存在，然后换算成 `docs/` 视角的相对路径。
    这样作者用哪种写法都能得到正确链接，而不是靠"记得该写几个 ../"。
    """
    docs_dir = os.path.dirname(OUT)
    fd_dir = HERE
    bases = [os.path.join(fd_dir, "parts"), fd_dir, docs_dir]

    def repl(m):
        target = m.group(1)
        frag = ""
        if "#" in target:
            target, frag = target.split("#", 1)
            frag = "#" + frag
        if not target or "|" in target or "\\" in target or "{" in target:
            return m.group(0)
        for base in bases:
            cand = os.path.normpath(os.path.join(base, target))
            if os.path.exists(cand):
                rel = os.path.relpath(cand, docs_dir).replace(os.sep, "/")
                return "](%s%s)" % (rel, frag)
        return m.group(0)

    return re.sub(r"\]\(([^)\s]+)\)", repl, text)


# 由后续步骤产出、组装时尚不存在的文件（独立验证报告）。缺它不是错误，但要在报告里说出来。
PENDING_ARTIFACTS = {"frontend-detail/verification.md"}


def check_links(text):
    """组装后的每个相对 markdown 链接都必须能在磁盘上找到对应文件。
    为什么要有这条：作者的分册比最终文件深一层，路径写错时 Markdown 渲染器不会报错，
    只有点开才发现 404——而这类错在 7 个分册并行写作时几乎必犯。"""
    bad_links, pending = [], []
    for m in re.finditer(r"\]\(([^)\s]+)\)", text):
        t = m.group(1)
        if t.startswith("#") or "://" in t or t.startswith(("mailto:", "/")) or "|" in t or "\\" in t:
            continue
        t = t.split("#")[0]
        if not t:
            continue
        p = os.path.normpath(os.path.join(os.path.dirname(OUT), t))
        if os.path.exists(p):
            continue
        (pending if t in PENDING_ARTIFACTS else bad_links).append(t)
    for b in sorted(set(bad_links)):
        bad("链接目标不存在", b)
    if pending:
        print("  [--] 链接指向待产出文件（非错误）：%s" % "、".join(sorted(set(pending))))
    if not bad_links:
        print("  [OK] 相对链接全部可解析")


def split_chapters(text):
    """把分册切成 (前言, {章号: 章正文})。
    一个分册可以携带多个章（如 `30` 带 §4 与 §6），而分册之间的章号是交错的。
    因此**必须先切块再按章号重排**——按分册顺序直接拼接会产出 `…3,5,4,6,9,8…` 的错序文档。"""
    parts = re.split(r"^(##\s+(\d+)\.[^\n]*)$", text, flags=re.M)
    pre = parts[0]
    ch = {}
    for i in range(1, len(parts), 3):
        num = int(parts[i + 1])
        ch[num] = parts[i] + parts[i + 2]
    return pre, ch


def sort_subsections(block, chap_no, label):
    """把一章内的 `### N.M` 子节按 M 升序重排。
    前言（第一个子节之前的内容）保持最前；**未编号的 `###` 无法排序，会被报告出来**——
    它同时也是「读者按编号找不到」的来源。"""
    marks = list(re.finditer(r"^###\s+(?:(\d+)\.(\d+)\s*([^\n]*)|([^\n]*))$", block, re.M))
    if not marks:
        return block, []
    intro = block[:marks[0].start()]
    numbered, unnumbered = [], []
    for i, mm in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(block)
        seg = block[mm.start():end]
        if mm.group(1) and mm.group(2):
            numbered.append((int(mm.group(1)), int(mm.group(2)), seg))
        else:
            unnumbered.append(((mm.group(4) or "").strip(), seg))
    numbered.sort(key=lambda x: (x[0], x[1]))
    out = intro + "".join(s for _a, _b, s in numbered) + "".join(s for _n, s in unnumbered)
    for name, _s in unnumbered:
        bad("章内有未编号 ### 子节", "%s（第 %s 章）：%s" % (label, chap_no, name[:40]))
    return out, [n for n, _s in unnumbered]


def check_parts(files):
    """① 分册存在、首行声明正确；② 章节编号恰好 1..16、不重不漏。"""
    texts, chapters = {}, []
    for fname, expect in PARTS:
        p = os.path.join(HERE, "parts", fname)
        if not os.path.exists(p):
            bad("分册缺失", fname)
            continue
        t = read(p)
        texts[fname] = t
        first = t.lstrip().splitlines()[0] if t.strip() else ""
        m = re.match(r"<!--\s*part:\s*([^;]+);\s*chapters:\s*([^;]+);\s*owner:\s*([^>]+?)\s*-->", first)
        if not m:
            bad("分册首行声明缺失或格式错", "%s：%r" % (fname, first[:80]))
        else:
            if m.group(1).strip() != fname.replace(".md", ""):
                bad("分册声明名不符", "%s 声明为 %s" % (fname, m.group(1).strip()))
            got = [x.strip() for x in m.group(2).split(",")]
            exp = [x.strip() for x in expect.split(",")]
            if got != exp:
                bad("分册章节声明与文件映射不符", "%s：声明 %s / 期望 %s" % (fname, got, exp))
            chapters += got
        if re.search(r"^#\s+\S", strip_fences(t), re.M):
            bad("分册含一级标题", fname)
    nums = sorted(int(c) for c in chapters if c.isdigit())
    want = list(range(1, TOTAL_CHAPTERS + 1))
    if nums != want:
        bad("章节编号不连续", "得到 %s / 期望 1..%d" % (nums, TOTAL_CHAPTERS))
    else:
        print("  [OK] 章节编号 %d 章连续无重复" % len(nums))
    # 正文里实际出现的 ## N. 必须与声明一致（同样忽略围栏）
    seen = []
    for fname, t in texts.items():
        for m in re.finditer(r"^##\s+(\d+)\.", strip_fences(t), re.M):
            seen.append(int(m.group(1)))
    if sorted(seen) != want:
        bad("正文 ## 编号与声明不符", "正文得到 %s" % sorted(seen))
    return texts


def check_endpoints(all_text, paths):
    """③ 文档里出现的每个端点都必须存在于 openapi；内部端点不得被当作可调用。"""
    found = set()
    for m in re.finditer(r"`?(/(?:api|internal)/v1/[A-Za-z0-9_\-{}/]+)`?", all_text):
        found.add(m.group(1))
    ghost, internal_used = [], []
    for f in sorted(found):
        norm = re.sub(r"\{[^}]+\}", "{x}", f)
        if norm not in {re.sub(r"\{[^}]+\}", "{x}", p) for p in paths} and f not in paths:
            ghost.append(f)
        if f.startswith("/internal/"):
            if raw_hits(all_text, f):
                internal_used.append(f)
    if ghost:
        for g in ghost:
            bad("文档写了 openapi 没有的端点", g)
    else:
        print("  [OK] 端点引用 %d 个全部存在于 openapi" % len(found))
    if internal_used:
        for i in set(internal_used):
            bad("把内部端点当作前端可用", i)
    # 覆盖率提示（不作为 FAIL）
    pub = {p for p in paths if p.startswith("/api/")}
    mentioned = {f for f in found if f.startswith("/api/")}
    miss = sorted(p for p in pub
                  if re.sub(r"\{[^}]+\}", "{x}", p) not in {re.sub(r"\{[^}]+\}", "{x}", m) for m in mentioned})
    if miss:
        print("  [--] openapi 有但文档未提及的端点 %d 个：%s" % (len(miss), "、".join(miss)))
    return found


def check_codes(all_text, allowed):
    """④ 错误码必须属于合法集合（openapi 并集 ∪ SRS §8 独有 ∪ 6 个异步码）。"""
    found = set(re.findall(r"`([A-Z][A-Z0-9]{2,}(?:_[A-Z0-9]+)+)`", all_text))
    found |= set(re.findall(r"\b([A-Z][A-Z0-9]{2,}(?:_[A-Z0-9]+)+)\b", all_text))
    ignore = {"HTTP", "API", "SSE", "JSON", "TS", "URL", "URI", "DOM", "CSS", "HTML", "SQL",
              "WCAG", "ARIA", "UUID", "BOM", "CRLF", "UTF", "GET", "POST", "PATCH", "DELETE",
              "PUT", "HEAD", "OPTIONS", "P95", "P99", "P50", "NFR", "FR", "SRS", "PRD", "HLD",
              "CI", "CD", "MIT", "OK", "PASS", "FAIL", "UNKNOWN", "TODO", "TBD", "W1", "W2", "W3",
              "J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "J10", "J11", "J12", "J13",
              "J14", "J15", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "M1", "M2", "M3",
              "R1", "R2", "R3", "R4", "R5", "R6", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8",
              "P9", "P10", "P11", "P12", "ABC", "L1", "L2", "L3", "L0", "XSS", "CSRF", "CSP"}
    ghost = sorted(c for c in found if c not in allowed and c not in ignore
                   and not c.startswith(("FR_", "NFR_", "VITE_"))
                   and not re.search(r"(?:const|let|export const)\s+%s\b" % re.escape(c), all_text)
                   and not re.search(r"`%s`\s*(?::|=)" % re.escape(c), all_text)
                   and raw_hits(all_text, "`%s`" % c))
    if ghost:
        for g in ghost:
            bad("自造错误码", g)
    else:
        print("  [OK] 错误码引用全部属于合法集合（%d 个）" % len(allowed))
    return found


def check_stores_and_routes(all_text):
    """⑤ store 名与路由名必须取自冻结集合。"""
    ghosts = set()
    for m in re.finditer(r"use([A-Z][A-Za-z]*)Store", all_text):
        name = m.group(1)
        name = name[0].lower() + name[1:]
        if name not in STORES:
            ghosts.add(m.group(0))
    if ghosts:
        for g in sorted(ghosts):
            bad("store 名不在冻结集合", g)
    else:
        print("  [OK] store 名全部属于冻结的 8 个")
    rghosts = set()
    def normroute(r):
        return re.sub(r"(\{[^}]+\}|:[A-Za-z]+)", ":x", r)
    frozen = {normroute(x) for x in ROUTES}
    for m in re.finditer(r"`(/[A-Za-z0-9_:/{}\-]*)`", all_text):
        r = m.group(1)
        if r.startswith(("/api/", "/internal/")):
            continue
        if r.startswith(("/me/", "/admin/", "/login", "/assistant")) and normroute(r) not in frozen:
            rghosts.add(r)
    if rghosts:
        for r in sorted(rghosts):
            bad("路由不在冻结路由表", r)
    else:
        print("  [OK] 路由引用全部属于冻结的 10 条")


def check_forbidden(all_text):
    for w in FORBIDDEN:
        for i in raw_hits(all_text, w):
            bad("违禁表述", "%s @ %d" % (w, i))
    if EMOJI_RE.search(all_text):
        bad("emoji", EMOJI_RE.search(all_text).group(0))
    if not any("正在思考" in t for _f, t in []):
        pass
    print("  [OK] 违禁表述与 emoji 扫描完成")


def check_tokens(all_text, token_names):
    """⑥ 文档里出现的 --token 必须真实存在（排除 BEM 片段与否定语境）。"""
    ghosts = set()
    for m in re.finditer(r"`(--[A-Za-z][A-Za-z0-9_-]*)`", all_text):
        name = m.group(1)
        if name.endswith("-") or name in token_names or name in PROPOSED_TOKENS:
            continue
        if in_negation(all_text, m.start()):
            continue
        first = name.lstrip("-").split("-")[0]
        if first == "p" or first in GROUP_PREFIX:
            ghosts.add(name)
    if ghosts:
        for g in sorted(ghosts):
            bad("幽灵 token 引用", g)
    else:
        print("  [OK] token 引用全部可解析（tokens.css 共 %d 个）" % len(token_names))


def main():
    print("=" * 78)
    print("前端详细设计组装   docs/校园课程智能助手_前端详细设计_v0.1.md")
    print("=" * 78)
    spec = json.load(open(OPENAPI, encoding="utf-8"))
    paths = set(spec["paths"].keys())

    allowed = set()
    def walk(o):
        if isinstance(o, dict):
            if "enum" in o and isinstance(o["enum"], list):
                for x in o["enum"]:
                    if isinstance(x, str) and x.isupper() and "_" in x:
                        allowed.add(x)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(spec)
    allowed |= {"FORBIDDEN"}          # SRS §8 独有（openapi 漏写，见 API-REFERENCE §0）
    allowed |= {"NO_TEXT_EXTRACTED", "DOCUMENT_ENCRYPTED", "PARSE_FAILED",
                "EMBEDDING_FAILED", "CLEANUP_FAILED", "SERVICE_RESTARTED"}

    token_names = set(re.findall(r"(--[A-Za-z][A-Za-z0-9_-]*)\s*:", read(TOKENS_CSS)))

    texts = check_parts(None)
    all_text = "\n".join(texts.get(f, "") for f, _c in PARTS)
    check_endpoints(all_text, paths)
    check_codes(all_text, allowed)
    check_stores_and_routes(all_text)
    check_forbidden(all_text)
    check_tokens(all_text, token_names)

    if problems:
        print("-" * 78)
        for kind, detail in problems:
            print("[FAIL] %-28s %s" % (kind, detail))
        print("-" * 78)
        print("FAIL %d —— 先修分册，不要采用本次产物。" % len(problems))
        return 1

    # ---- 组装 ----
    head = [
        "# 校园课程智能助手前端详细设计",
        "",
        "**版本** v0.1　**对应上游** PRD / SRS / HLD v0.1、`openapi_v0.1.json`、`sse_events_v0.1.schema.json`",
        "",
        "> 本文件由 `docs/frontend-detail/build.py` 从 7 个分册组装而成，**请勿手改**；改动请改分册后重跑组装。",
        "> 字段名的唯一来源是 [`API-REFERENCE.md`](frontend-detail/API-REFERENCE.md)（由 OpenAPI 机械生成）；",
        "> 样式与组件的唯一来源是 [`design/system/`](../design/system/)（519 个 token 的四层设计系统 + 27 个组件族规格）；",
        "> 写作契约与冻结口径见 [`CONTRACT.md`](frontend-detail/CONTRACT.md)；独立验证见 "
        "[`verification.md`](frontend-detail/verification.md)。",
        "",
        "## 目录",
        "",
    ]
    # ---- 组装：**先按章号重排**，再按顺序输出 ----
    # 分册与章号是交错的（如 `30` 带 §4 与 §6，而 §5 在 `20` 里），按分册顺序直接拼接会错序。
    rewritten = {f: rewrite_part_links(texts.get(f, "<!-- 分册缺失 -->")) for f, _c in PARTS}
    blocks, owner = {}, {}
    for f, _c in PARTS:
        pre, ch = split_chapters(rewritten[f])
        for n, blk in ch.items():
            if n in blocks:
                bad("章号重复", "第 %d 章同时来自 %s 与 %s" % (n, owner[n], f))
                continue
            blocks[n] = blk
            owner[n] = f
        # 前言挂在该分册的第一个章之前
        if ch:
            first = min(ch)
            blocks[first] = (pre.strip() + "\n\n" + blocks[first]) if pre.strip() else blocks[first]
    order = sorted(blocks)
    if order != list(range(1, TOTAL_CHAPTERS + 1)):
        bad("章号不连续", "得到 %s" % order)
    for n in order:
        blk, _u = sort_subsections(blocks[n], n, owner[n])
        blocks[n] = blk

    toc = []
    for n in order:
        # 必须用 re.search 而不是 re.match：分册的**第一章**块首被粘上了分册前言
        # （`<!-- part: … -->`），块不再以 `## ` 开头，锚定的 match 会返回 None
        # 并**静默丢掉 7 条目录条目**——这正是上一版 TOC 只列 9/16 章的原因。
        h = re.search(r"^##\s+(\d+\.\s*[^\n]+)", blocks[n], re.M)
        if h:
            toc.append("- [%s](#%s)" % (h.group(1).strip(),
                                        re.sub(r"[^\w\u4e00-\u9fff]+", "-", h.group(1)).strip("-").lower()))
        else:
            bad("目录条目缺失", "第 %d 章取不到标题" % n)
    if len(toc) != TOTAL_CHAPTERS:
        bad("目录条目数不符", "%d != %d" % (len(toc), TOTAL_CHAPTERS))
    else:
        print("  [OK] 目录 %d 条，与章数一致" % len(toc))
    body = ["\n".join(head + toc), ""]
    for n in order:
        body.append(blocks[n].rstrip())
        body.append("")
    out = "\n".join(body) + "\n"

    # 断言：拼接后正文的 ## N. 序列必须严格递增（这正是上一版漏掉的那条）
    seq = [int(x) for x in re.findall(r"^##\s+(\d+)\.", strip_fences(out), re.M)]
    if seq != sorted(seq) or len(seq) != TOTAL_CHAPTERS:
        bad("拼接后章序非严格递增", "实际序列 %s" % seq)
    else:
        print("  [OK] 拼接后章序严格递增 1..%d" % len(seq))

    check_links(out)
    if problems:
        print("-" * 78)
        for kind, detail in problems:
            print("[FAIL] %-28s %s" % (kind, detail))
        print("-" * 78)
        print("FAIL %d —— 先修分册，不要采用本次产物。" % len(problems))
        return 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    lines = out.count("\n")
    print("-" * 78)
    print("  分册        %d" % len(PARTS))
    print("  章节        %d" % TOTAL_CHAPTERS)
    print("  产物        %s" % os.path.relpath(OUT, ROOT))
    print("  规模        %d 字节 / %d 行" % (len(out.encode("utf-8")), lines))
    print("  端点引用    见上")
    print("组装通过：0 FAIL。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
