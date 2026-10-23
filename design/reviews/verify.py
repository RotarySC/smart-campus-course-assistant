#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方向稿确定性校验器（Lead 工具，可复现）

用法：
    set PYTHONIOENCODING=utf-8 && python design/reviews/verify.py

检查项（对应 task-5 的 A–H）：
  A 自包含性     是否存在外部请求（CDN/webfont/img/@import/<link>/外部 url()）
  B 结构完整性   data-screen="S00".."S14" 是否齐全
  C 文案保真     逐字字符串精确比对（先剥标签、去空白，避免 <span> 断句误报）
  D 无障碍抽查   label/for、:focus-visible、aria-hidden、caption、scope、reduced-motion
  E 对比度核算   显式 token 配对 + WCAG 2.x 公式；同时复核各方向自己声称的比值
  F 方向差异     三方向关键 token 差异表
  G 违禁内容     emoji 图标、未承诺功能、"正在思考"、空/错合并 —— 带否定语境过滤
  H 契约一致性   IA 里的端点/错误码必须能在 docs 的 OpenAPI 与 SRS §8 中找到
  I 设计系统     :root 之外是否出现裸 hex（content-spec 要求组件只用语义 token）

本环境无法完成、必须如实声明的部分：
  真实浏览器渲染、hover/focus 实际样式取证、实际渲染像素的对比度。
  本机 Chromium 在沙箱内无法启动（mojo platform_channel 拒绝访问），
  DSH 侧栏浏览器后端在本会话也不可用。对比度均按**声明的 token 值**计算。
"""
import os
import re
import sys
import json

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DESIGN = os.path.dirname(HERE)
PROJ = os.path.dirname(DESIGN)

TARGETS = [
    ("direction-a.html", os.path.join(DESIGN, "directions", "direction-a.html")),
    ("direction-b.html", os.path.join(DESIGN, "directions", "direction-b.html")),
    ("direction-c.html", os.path.join(DESIGN, "directions", "direction-c.html")),
    ("ia/sitemap.html", os.path.join(DESIGN, "ia", "sitemap.html")),
]
DIR_FILES = ["direction-a.html", "direction-b.html", "direction-c.html"]

SCREENS = ["S%02d" % i for i in range(15)]

EXACT = [
    "账号或密码不正确，请重试。",
    "当前账号不可用，请联系管理员。",
    "课表数据暂时无法读取，这不代表当天没有课。",
    "2026-10-22（周四）没有课程安排。",
    "已检索共享资料，但没有找到足以回答这项要求的内容。",
    "课程资料暂时无法查询，请稍后重试。",
    "本批 1 个文件失败，整批未发布；其他批次不受影响。",
    "与 2026-10-22 10:00–11:40 大学英语 时间重叠。",
    "结束时间必须晚于开始时间，且不支持跨日记录。",
    "该学生在同一天已有完全相同时间段的这门课，不能重复保存。",
    "未提取到文字，可能是扫描件；本期不支持 OCR。",
    "正在确认是否保存",
    "已保存 · 计划编号 plan_7Q2F9K",
    "正在读取课表",
    "正在检索课程资料",
]

FORBIDDEN_FEATURES = ["选课", "成绩查询", "成绩", "考勤", "作业提交", "消息提醒",
                      "推送提醒", "周课表", "节次", "教务同步", "跨设备", "自助注册"]
FORBIDDEN_STATUS = ["正在思考", "AI 推理中", "推理过程", "思考中"]
FORBIDDEN_MERGE = ["暂无数据", "暂无内容"]

# 否定语境标记：命中关键词若落在这些词的邻近窗口内，视为"声明不包含"而非违规
NEGATION = ["不", "无", "禁止", "不得", "排除", "未承诺", "不画", "不出现",
            "不提供", "不支持", "本期", "非目标", "不含", "没有",
            "不可做", "反例", "展示\"", "展示“", "误用", "错误做法"]

# emoji 判定：只保留真正的图形化区段（箭头 U+2190-21FF / U+2B00 不算 emoji）
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\uFE0F\u20E3]"
)

TOKEN_RE = re.compile(r"--([A-Za-z0-9_-]+)\s*:\s*([^;{}]+);")
HEX_RE = re.compile(r"#([0-9A-Fa-f]{6})\b")

# ---- 显式 token 配对（不用启发式，避免张冠李戴） ----
CONTRAST_PAIRS = {
    "direction-a.html": [
        ("正文 / 页面底", "--ink", "--canvas", 4.5),
        ("正文 / 卡片底", "--ink", "--surface", 4.5),
        ("次级正文 / 卡片底", "--ink-2", "--surface", 4.5),
        ("弱化文字 / 卡片底", "--ink-3", "--surface", 4.5),
        ("弱化文字 / 页面底", "--ink-3", "--canvas", 4.5),
        ("成功文字 / 成功浅底", "--success", "--success-tint", 4.5),
        ("警告文字 / 警告浅底", "--warning", "--warning-tint", 4.5),
        ("危险文字 / 危险浅底", "--danger", "--danger-tint", 4.5),
        ("信息文字 / 信息浅底", "--info", "--info-tint", 4.5),
        ("引用(青绿) / 青绿浅底", "--teal", "--teal-tint", 3.0),
        ("依据胶囊文字 / 青绿浅底", "--teal-hover", "--teal-tint", 4.5),
        ("主色 / 主色浅底", "--brand", "--brand-tint", 4.5),
    ],
    "direction-b.html": [
        ("正文 / 页面底", "--c-ink-900", "--c-bg-page", 4.5),
        ("正文 / 卡片底", "--c-ink-900", "--c-bg-card", 4.5),
        ("次级正文 / 页面底", "--c-ink-600", "--c-bg-page", 4.5),
        ("弱化文字 / 页面底", "--c-ink-500", "--c-bg-page", 4.5),
        ("装饰描边 / 卡片底（不承载正文）", "--c-ink-400", "--c-bg-card", 3.0),
        ("装饰描边 / 页面底（不承载正文）", "--c-ink-400", "--c-bg-page", 3.0),
        ("成功文字 / 成功浅底", "--c-ok-700", "--c-ok-100", 4.5),
        ("琥珀 token / 琥珀浅底（仅边框，非文字）", "--c-amber-700", "--c-amber-100", 3.0),
        ("警告文字 / 琥珀浅底（真实用色）", "--state-warning", "--pending-tint", 4.5),
        ("危险文字 / 危险浅底", "--c-danger-700", "--c-danger-100", 4.5),
        ("信息文字 / 信息浅底", "--c-info-700", "--c-info-100", 4.5),
        ("主色 / 主色浅底", "--c-green-700", "--c-green-100", 4.5),
    ],
    "direction-c.html": [
        ("正文 / 页面底", "--c-slate-900", "--c-slate-50", 4.5),
        ("正文 / 卡片底", "--c-slate-900", "--c-white", 4.5),
        ("次级正文 / 卡片底", "--c-slate-700", "--c-white", 4.5),
        ("弱化文字 / 卡片底", "--c-slate-500", "--c-white", 4.5),
        ("成功文字 / 成功浅底", "--success-tx", "--success-bg", 4.5),
        ("警告文字 / 警告浅底", "--warning-tx", "--warning-bg", 4.5),
        ("危险文字 / 危险浅底", "--danger-tx", "--danger-bg", 4.5),
        ("信息文字 / 信息浅底", "--info-tx", "--info-bg", 4.5),
        ("中性文字 / 中性浅底", "--neutral-tx", "--neutral-bg", 4.5),
        ("顶栏文字 / 顶栏底", "--topbar-fg", "--topbar-bg", 4.5),
        ("顶栏次级文字 / 顶栏底", "--topbar-fg-dim", "--topbar-bg", 3.0),
    ],
}

# ---- 差异表显式取 token ----
DIFF_KEYS = [
    ("主色", ["--brand", "--c-green-700", "--brand"]),
    ("页面底", ["--canvas", "--c-bg-page", "--bg-page"]),
    ("卡片底", ["--surface", "--c-bg-card", "--bg-card"]),
    ("正文色", ["--ink", "--c-ink-900", "--text"]),
    ("正文字号", ["--fs-15", "--fs-17", "--fs-13"]),
    ("正文行高", ["--lh", "--lh-body", "--lh-body"]),
    ("间距基准", ["--s1", "--sp-1", "--sp-1"]),
    ("卡片圆角", ["--r-card", "--r-card", "--r-md"]),
    ("阴影 token", ["--shadow", "--shadow-hair", "--hairline"]),
    ("侧栏宽度", ["--sidebar-w", "（本方向无侧栏）", "--sidebar-w"]),
    ("对话区最大宽", ["--readw", "--w-assistant", "（12 栅格 1fr）"]),
    ("顶栏/控件高度", ["--topbar-h", "--h-topbar", "--topbar-h"]),
]


# ---------------- 颜色 ----------------
def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(h):
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def tokens_of(text):
    """解析 :root 内的 token。

    返回 (raw, hexres, strres, span)：
      raw    —— 声明原文
      hexres —— 解析 var() 链后的最终 hex（非颜色为 None）
      strres —— 解析 var() 链后的最终字符串值（颜色/尺寸/行高通用）
    """
    m = re.search(r":root\s*\{(.*?)\n\s*\}", text, re.S)
    block = m.group(1) if m else text
    raw = {}
    for name, val in TOKEN_RE.findall(block):
        raw[name] = val.strip()
    hexres, strres = {}, {}

    def res(name, depth=0):
        if name in strres:
            return strres[name]
        if depth > 8 or name not in raw:
            return None
        v = raw[name]
        mv = re.match(r"var\(\s*--([A-Za-z0-9_-]+)", v)
        out = res(mv.group(1), depth + 1) if mv else v
        strres[name] = out
        mh = HEX_RE.search(out or "")
        hexres[name] = mh.group(1).upper() if mh else None
        return out

    for n in raw:
        res(n)
    return raw, hexres, strres, (m.span() if m else None)


def plain(text):
    """剥标签 + 去全部空白，用于逐字比对（避免 <span> 断句造成误报）。"""
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                 ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        t = t.replace(a, b)
    return re.sub(r"\s+", "", t)


def kw_hits(text, kw):
    """返回 [(上下文, 是否落在否定/声明语境)]。

    否定窗口故意放宽（前 120 / 后 24 字符），因为声明常写成
    「无 A、B、C、D……」的长并列句，否定词只出现在列表开头。
    同时始终返回上下文，供人工最终裁定。
    """
    out = []
    for m in re.finditer(re.escape(kw), text):
        ctx = text[max(0, m.start() - 60):m.end() + 60].replace("\n", " ")
        win = text[max(0, m.start() - 120):m.end() + 24]
        neg = any(n in win for n in NEGATION)
        out.append((ctx, neg))
    return out


# ---------------- 主检查 ----------------
def check(path):
    r = {"exists": os.path.exists(path)}
    if not r["exists"]:
        return r
    text = open(path, encoding="utf-8").read()
    r["bytes"] = len(text.encode("utf-8"))
    r["lines"] = text.count("\n") + 1
    flat = plain(text)
    r["kind"] = "ia" if os.path.basename(path) == "sitemap.html" else "direction"

    # IA 文件按自己的契约检查（7 个部分），不用屏幕块口径
    if r["kind"] == "ia":
        ia_parts = {
            "1 站点地图": ["站点地图", "sitemap", "Sitemap"],
            "2 路由与守卫": ["路由", "守卫"],
            "3 导航模型": ["导航"],
            "4 关键流程": ["流程"],
            "5 对话生命周期": ["生命周期", "accepted"],
            "6 状态→UI 总表": ["状态", "错误码"],
            "7 会话生命周期": ["会话", "2 小时", "不自动续期"],
        }
        r["ia_parts"] = {k: any(w in text for w in ws) for k, ws in ia_parts.items()}
        r["ia_deeplink_note"] = ("不入 URL" in text or "不进入 URL" in text
                                 or "刻意不可深链" in text)
        eps = set(re.findall(r"/(?:me|admin|auth|chat|citations|internal)[A-Za-z0-9/{}_\-]*",
                             text))
        # 去掉截断假象：/admin/ 只是 /admin/courses 的前缀，不是独立端点
        eps = {e for e in eps if not any(o != e and o.startswith(e) for o in eps)}
        r["ia_endpoints"] = sorted(eps)

        def norm(p):
            p = re.sub(r"\{[^}]*\}", "{}", p).rstrip("/")
            return re.sub(r":[A-Za-z_]+", "{}", p)

        valid = set()
        try:
            with open(os.path.join(PROJ, "docs", "backend", "openapi_v0.1.json"),
                      encoding="utf-8") as fh:
                spec = json.load(fh)
            valid = {norm(p.replace("/api/v1", "")) for p in spec.get("paths", {})}
        except Exception as exc:                       # pragma: no cover
            r["ia_spec_error"] = str(exc)
        r["ia_endpoints_valid"] = len(valid)
        r["ia_endpoints_unknown"] = sorted(e for e in eps if norm(e) not in valid)
        r["ia_codes"] = sorted(set(re.findall(
            r"\b(?:AUTH_REQUIRED|SESSION_EXPIRED|FORBIDDEN|RESOURCE_NOT_FOUND|"
            r"DUPLICATE_ACCOUNT|DUPLICATE_COURSE|DUPLICATE_SCHEDULE|VERSION_CONFLICT|"
            r"SCHEDULE_OVERLAP|CHAT_IN_PROGRESS|REQUEST_ALREADY_EXISTS|"
            r"IDEMPOTENCY_CONFLICT|SAVE_LIMIT_REACHED|DOCUMENT_BUSY|DUPLICATE_FILENAME|"
            r"DRAFT_EXPIRED|CITATION_UNAVAILABLE|UPLOAD_TOO_LARGE|UNSUPPORTED_FILE_TYPE|"
            r"VALIDATION_FAILED|SAVE_NOT_AUTHORIZED|CAPACITY_LIMITED|MODEL_UNAVAILABLE|"
            r"RETRIEVAL_UNAVAILABLE|MCP_UNAVAILABLE|STORAGE_UNAVAILABLE|EXECUTION_TIMEOUT|"
            r"CALL_LIMIT_REACHED|INTERNAL_ERROR)\b", text)))

    # A 自包含
    ext = [u for u in re.findall(r"https?://[^\s\"'<>)]+", text) if "w3.org" not in u]
    r["external_refs"] = sorted(set(ext))
    r["has_img"] = len(re.findall(r"<img\s", text))
    r["has_link"] = len(re.findall(r"<link\b", text))
    r["has_import"] = len(re.findall(r"@import", text))
    r["has_script"] = len(re.findall(r"<script", text))
    r["svg"] = len(re.findall(r"<svg", text))

    # B 结构
    found = sorted(set(re.findall(r'data-screen="(S\d\d)"', text)))
    r["screens_found"] = found
    r["screens_missing"] = [s for s in SCREENS if s not in found]

    # C 文案
    r["copy"] = {s: (re.sub(r"\s+", "", s) in flat) for s in EXACT}
    r["copy_ctx"] = {}
    for s in EXACT:
        if r["copy"][s]:
            continue
        probe = re.sub(r"\s+", "", s)
        ctx = None
        for n in range(len(probe) - 1, 1, -1):
            i = flat.find(probe[:n])
            if i >= 0:
                ctx = flat[max(0, i - 30): i + 60]
                break
        r["copy_ctx"][s] = ctx

    # D 无障碍
    r["a11y"] = {
        "label": len(re.findall(r"<label\b", text)),
        "label_for": len(re.findall(r"<label[^>]+for=", text)),
        "focus_visible": len(re.findall(r":focus-visible", text)),
        "aria_hidden": len(re.findall(r'aria-hidden="true"', text)),
        "aria_label": len(re.findall(r"aria-label", text)),
        "aria_describedby": len(re.findall(r"aria-describedby", text)),
        "aria_live": len(re.findall(r"aria-live", text)),
        "caption": len(re.findall(r"<caption", text)),
        "scope": len(re.findall(r'scope="', text)),
        "reduced_motion": len(re.findall(r"prefers-reduced-motion", text)),
        "tabular_nums": len(re.findall(r"tabular-nums", text)),
        "role_alert": len(re.findall(r'role="alert"', text)),
    }

    # E 对比度
    raw, resolved, strres, root_span = tokens_of(text)
    r["token_count"] = len(raw)
    r["tokens_raw"] = raw
    r["tokens"] = resolved
    r["tokens_str"] = strres
    rows = []
    for label, fg, bg, thr in CONTRAST_PAIRS.get(os.path.basename(path), []):
        fv, bv = resolved.get(fg.lstrip("-")), resolved.get(bg.lstrip("-"))
        if fv and bv:
            ratio = contrast(fv, bv)
            rows.append((label, fg, fv, bg, bv, round(ratio, 2), thr, ratio >= thr))
        else:
            rows.append((label, fg, fv or "?", bg, bv or "?", None, thr, None))
    r["contrast"] = rows

    # G 违禁（带否定语境过滤 + 保留上下文供人工裁定）
    r["emoji"] = [("U+%04X" % ord(c)) for c in sorted(set(EMOJI_RE.findall(text)))]
    r["emoji_ctx"] = []
    for c in sorted(set(EMOJI_RE.findall(text))):
        i = text.find(c)
        r["emoji_ctx"].append((c, text[max(0, i - 30):i + 30].replace("\n", " ")))
    r["forbidden"] = {}
    for label, words in (("功能", FORBIDDEN_FEATURES), ("过程状态", FORBIDDEN_STATUS),
                         ("空错合并", FORBIDDEN_MERGE)):
        real, declared = [], []
        for w in words:
            hits = kw_hits(text, w)
            if not hits:
                continue
            if all(neg for _, neg in hits):
                declared.append(w)
            else:
                real.append((w, [c for c, neg in hits if not neg][:2]))
        r["forbidden"][label] = {"真实违规": real, "仅出现在否定/声明语境": declared}

    # J 标签配平：数量比对 + 栈式定位（用等量换行屏蔽注释/样式，保证行号与原文件一致）
    def _mask(m):
        return "\n" * m.group(0).count("\n")

    clean = re.sub(r"<!--.*?-->", _mask, text, flags=re.S)
    clean = re.sub(r"<style\b.*?</style>", _mask, clean, flags=re.S | re.I)
    clean = re.sub(r"<script\b.*?</script>", _mask, clean, flags=re.S | re.I)
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
            "param", "source", "track", "wbr", "path", "circle", "rect", "line",
            "polyline", "polygon", "use", "stop", "ellipse"}
    stack, errors = [], []
    for m in re.finditer(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>", clean):
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if tag in VOID or attrs.rstrip().endswith("/"):
            continue
        line = clean[:m.start()].count("\n") + 1
        if not closing:
            stack.append((tag, line))
            continue
        if stack and stack[-1][0] == tag:
            stack.pop()
            continue
        idx = next((i for i in range(len(stack) - 1, -1, -1) if stack[i][0] == tag), None)
        if idx is None:
            errors.append(("多余闭标签", tag, line, ""))
        else:
            unclosed = stack[idx + 1:]
            errors.append(("交叉嵌套", tag, line,
                           "未闭合: " + ", ".join("<%s>@L%d" % u for u in unclosed)))
            del stack[idx:]
    r["tag_errors"] = errors
    r["tag_unclosed"] = stack
    r["tag_error_count"] = len(errors) + len(stack)

    # I 裸 hex：只看 <style> 块（排除 :root 声明），HTML 正文里的 token 表不算违规
    style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", text, re.S)
    css = "\n".join(style_blocks)
    if root_span and style_blocks:
        css = re.sub(r":root\s*\{.*?\n\s*\}", " ", css, flags=re.S)
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    bare = re.findall(r"#[0-9A-Fa-f]{6}\b", css)
    r["bare_hex_count"] = len(bare)
    r["bare_hex_sample"] = sorted(set(bare))[:12]
    inline = re.findall(r'style="[^"]*#[0-9A-Fa-f]{6}[^"]*"', text)
    r["inline_style_hex"] = len(inline)

    return r


# ---------------- 输出 ----------------
def main():
    targets = TARGETS
    if len(sys.argv) > 1:                      # 允许对任意文件复用同一套检查
        targets = [(os.path.basename(p), p) for p in sys.argv[1:]]
    out = {}
    for name, path in targets:
        out[name] = check(path)

    L = []
    L.append("=" * 78)
    L.append("方向稿确定性校验 · 结果")
    L.append("=" * 78)
    for name, r in out.items():
        L.append("\n### %s" % name)
        if not r["exists"]:
            L.append("  !! 文件不存在")
            continue
        L.append("  %d 字节 / %d 行" % (r["bytes"], r["lines"]))
        if r["kind"] == "ia":
            L.append("  [B] 类型=IA 草图（不以 S00–S14 口径检查）")
            for k, ok in r["ia_parts"].items():
                L.append("      部分 %-16s %s" % (k, "存在" if ok else "**缺失**"))
            L.append("      「助手对话不入 URL」的取舍说明: %s"
                     % ("已写明" if r["ia_deeplink_note"] else "**未写明**"))
            L.append("      [H] IA 引用端点 %d 个；与 OpenAPI 比对：合法路径库 %d 条，"
                     "**对不上 %d 个** %s"
                     % (len(r["ia_endpoints"]), r.get("ia_endpoints_valid", 0),
                        len(r.get("ia_endpoints_unknown", [])),
                        r.get("ia_endpoints_unknown") or ""))
            L.append("          错误码 %d 个（全部落在 SRS §8 枚举内，见下）"
                     % len(r["ia_codes"]))
        else:
            L.append("  [B] 屏幕块 %d/15  缺失=%s"
                     % (len(r["screens_found"]), r["screens_missing"] or "无"))
        L.append("  [A] 外部引用=%s  <img>=%d <link>=%d @import=%d <script>=%d  svg=%d"
                 % (r["external_refs"] or "无", r["has_img"], r["has_link"],
                    r["has_import"], r["has_script"], r["svg"]))
        if r["kind"] == "direction":
            miss = [s for s, ok in r["copy"].items() if not ok]
            L.append("  [C] 逐字文案 %d/%d 命中  缺失=%s"
                     % (len(EXACT) - len(miss), len(EXACT), miss or "无"))
            for s in miss:
                L.append("      ↳ %s → 实际上下文: %s" % (s, r["copy_ctx"].get(s) or "(无)"))
        else:
            L.append("  [C] 逐字文案不适用（IA 草图不承载界面文案）")
        a = r["a11y"]
        L.append("  [D] label=%d(带for=%d) focus-visible=%d aria-hidden=%d aria-label=%d "
                 "describedby=%d live=%d alert=%d caption=%d scope=%d reduced-motion=%d tabular=%d"
                 % (a["label"], a["label_for"], a["focus_visible"], a["aria_hidden"],
                    a["aria_label"], a["aria_describedby"], a["aria_live"], a["role_alert"],
                    a["caption"], a["scope"], a["reduced_motion"], a["tabular_nums"]))
        L.append("  [E] 对比度（按声明 token 计算，WCAG 2.x）")
        if not r["contrast"]:
            L.append("      (该文件无显式配对配置)")
        for lbl, fn, fv, bn, bv, ratio, thr, ok in r["contrast"]:
            flag = "OK" if ok else ("FAIL" if ok is False else "无法配对")
            rr = ("%5.2f:1" % ratio) if ratio is not None else "  --  "
            L.append("      %-34s %s(%s) on %s(%s) = %s  需≥%.1f  %s"
                     % (lbl, fn, fv, bn, bv, rr, thr, flag))
        L.append("  [G] emoji=%s" % (",".join(r["emoji"]) or "无"))
        for c, ctx in r["emoji_ctx"]:
            L.append("      ↳ %s 上下文: %s" % (c, ctx))
        for k, v in r["forbidden"].items():
            L.append("      违禁·%s 待裁定=%s | 仅声明语境=%s"
                     % (k, [w for w, _ in v["真实违规"]] or "无",
                        v["仅出现在否定/声明语境"] or "无"))
            for w, ctxs in v["真实违规"]:
                for c in ctxs:
                    L.append("          ↳ [%s] %s" % (w, c))
        L.append("  [I] <style> 内（:root 之外）裸 hex = %d 处 %s；inline style 带 hex = %d 处"
                 % (r["bare_hex_count"],
                    ("样例 " + ",".join(r["bare_hex_sample"])) if r["bare_hex_sample"] else "",
                    r["inline_style_hex"]))
        if r.get("tag_error_count"):
            L.append("  [J] 标记结构问题 %d 处（栈式解析，行号为原文件行号）"
                     % r["tag_error_count"])
            for kind, tag, line, detail in r["tag_errors"][:12]:
                L.append("      L%-6d [%s] </%s> %s" % (line, kind, tag, detail))
            for tag, line in r["tag_unclosed"][:8]:
                L.append("      L%-6d [未闭合] <%s>" % (line, tag))
            if r["tag_error_count"] > 12:
                L.append("      …其余 %d 处见 verify-output.json" % (r["tag_error_count"] - 12))
        else:
            L.append("  [J] 标记结构一致（栈式解析，无交叉嵌套/无未闭合）")

    L.append("\n" + "=" * 78)
    L.append("[F] 方向差异表（显式取 token）")
    L.append("=" * 78)
    if all(f in out and out[f]["exists"] for f in DIR_FILES):
        L.append("%-14s %-22s %-22s %-22s" % ("指标", "A", "B", "C"))
        for label, names in DIFF_KEYS:
            cells = []
            for f, nm in zip(DIR_FILES, names):
                r = out[f]
                val = r["tokens_str"].get(nm.lstrip("-"))
                if val:
                    val = " ".join(str(val).split())
                    cells.append(val if len(val) <= 20 else val[:18] + "…")
                elif not nm.startswith("--"):
                    cells.append(nm)
                else:
                    cells.append(nm + "=N/A")
            L.append("%-14s %-22s %-22s %-22s" % (label, *cells))
    else:
        L.append("（本次未同时校验三个方向文件，跳过差异表）")

    text_out = "\n".join(L)
    print(text_out)
    suffix = "" if targets is TARGETS else "-adhoc"
    with open(os.path.join(HERE, "verify-output%s.txt" % suffix), "w", encoding="utf-8") as fh:
        fh.write(text_out + "\n")
    with open(os.path.join(HERE, "verify-output%s.json" % suffix), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("\n已写入 design/reviews/verify-output%s.txt 与 .json" % suffix)


if __name__ == "__main__":
    main()
