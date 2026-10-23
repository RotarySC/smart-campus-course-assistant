#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
设计系统 token 生成器 + 校验器   design/system/generate.py

单一真源：design/system/tokens.json
产出：
  tokens.css        四层 :root（L1 primitive / L2 semantic / L3 component / L0 compat）
  tokens.md         人类可读参考：分层表 + 解析值 + 对比度实测 + 裸字面量迁移表
  tokens.ts         TS 常量（含断点），供 Vue 3 + TS 阶段直接 import
  tokens.flat.json  全部 token 的解析后字面值，供其它工具消费

把校验做在生成里：任何一项 FAIL 都会以非 0 退出码结束，避免产出与规范不一致的文件。

运行：
  $env:PYTHONIOENCODING="utf-8"; python design\system\generate.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESIGN = os.path.dirname(HERE)
RB_CSS = os.path.join(DESIGN, "responsive", "rb.css")
SRC = os.path.join(HERE, "tokens.json")

VAR_RE = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*\)")
HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
RGBA_RE = re.compile(r"\brgba?\([^)]*\)", re.I)
HSL_RE = re.compile(r"\bhsla?\([^)]*\)", re.I)
LEN_RE = re.compile(r"(?<![\w.-])(\d*\.?\d+)(px|em|rem|ch|vh|vw|vmin|vmax|pt)\b")
PCT_RE = re.compile(r"(?<![\w.-])\d*\.?\d+%")
MEDIA_RE = re.compile(r"@media[^{]*?\(\s*(?:min|max)-width\s*:\s*(\d+)px\s*\)")

results = []


def rec(level, name, detail=""):
    results.append((level, name, detail))


# ---------------------------------------------------------------- 载入
def load():
    with open(SRC, encoding="utf-8") as f:
        return json.load(f)


def layer_groups(layer):
    """把一层规范化为 [(组名, {token: {...}})]。
    支持两种书写：分组式（primitive/semantic/component）与扁平式（compat）。"""
    real = {k: v for k, v in layer.items() if not k.startswith("_")}
    if real and all(isinstance(v, dict) and "v" in v for v in real.values()):
        return [(None, layer)]
    return [(k, v) for k, v in real.items() if isinstance(v, dict)]


def flatten(layer):
    """-> [(name, value, desc, group)]。"""
    out = []
    for gname, g in layer_groups(layer):
        for k, v in g.items():
            if k.startswith("_"):
                continue
            if not isinstance(v, dict) or "v" not in v:
                rec("FAIL", "tokens.json 结构", "%s.%s 缺少 v 字段" % (gname, k))
                continue
            out.append((k, v["v"], v.get("d", ""), gname or "(flat)"))
    return out


# ---------------------------------------------------------------- 解析
def resolve(name, table, stack=None):
    """把值里的 var() 一路替换到字面量。返回 (value, error)。"""
    stack = stack or []
    if name in stack:
        return None, "循环引用: " + " -> ".join(stack + [name])
    if name not in table:
        return None, "未定义: " + name
    val = table[name]
    if not isinstance(val, str):
        return val, None
    if not VAR_RE.search(val):
        return val, None
    out = val
    for ref in VAR_RE.findall(val):
        sub, err = resolve(ref, table, stack + [name])
        if err:
            return None, err
        out = out.replace("var(%s)" % ref, sub, 1)
    # 复合值里可能是 var(--a) var(--b) 交替，循环到干净
    guard = 0
    while VAR_RE.search(out):
        guard += 1
        if guard > 40:
            return None, "解析未收敛: " + name
        for ref in VAR_RE.findall(out):
            sub, err = resolve(ref, table, stack + [name])
            if err:
                return None, err
            out = out.replace("var(%s)" % ref, sub, 1)
    return out, None


def check_comment_safety(comment_texts):
    """注释里出现「星号紧跟斜杠」会提前终止注释。
    最恶的后果不是语法报错，而是后面的第一个 :root 块被并进一个**永不匹配**的垃圾选择器：
    声明文本还在（文本比对 PASS）、字节也在（字节比对 PASS），但浏览器里这些 token 全是空的。
    这个坑真实发生过一次——品牌绿整块失效，30 个 token 在运行时死掉。"""
    for label, t in comment_texts:
        # 注释模板本身以 */ 收尾是合法的：只允许「恰好一个、且在末尾」。
        n = t.count("*/")
        if n > 1 or (n == 1 and not t.rstrip().endswith("*/")):
            rec("FAIL", "注释安全", "%s 的注释含提前终止序列（共 %d 处）：%s"
                % (label, n, t[:60]))


def strip_css_comments(css):
    """注释感知地剥掉 CSS 注释（不能只用正则，正则会把已失效的注释也当成注释）。"""
    out, k, depth = [], 0, 0
    while k < len(css):
        if depth == 0 and css.startswith("/*", k):
            depth, k = 1, k + 2
        elif depth and css.startswith("*/", k):
            depth, k = 0, k + 2
        elif depth:
            k += 1
        else:
            out.append(css[k])
            k += 1
    return "".join(out), depth == 0


def check_rule_preludes(css):
    """每条规则的 prelude 必须**恰好**是 :root。
    只验「声明文本存在」是不够的：如果注释提前闭合，垃圾文本会和 :root 拼成同一个 prelude，
    于是 :root{...} 变成「垃圾选择器 :root{...}」，声明一条都不生效。"""
    live, closed = strip_css_comments(css)
    if not closed:
        rec("FAIL", "注释闭合", "存在未闭合的注释")
        return
    prelude_start, rules, bad_preludes = 0, 0, []
    for m in re.finditer(r"\{", live):
        prelude = live[prelude_start:m.start()].strip()
        rules += 1
        if prelude != ":root":
            bad_preludes.append(prelude[:80] or "(空)")
        # 找配对的 }
        depth, k = 1, m.end()
        while k < len(live) and depth:
            if live[k] == "{":
                depth += 1
            elif live[k] == "}":
                depth -= 1
            k += 1
        prelude_start = k
    if bad_preludes:
        for p in bad_preludes[:5]:
            rec("FAIL", "规则 prelude 非 :root", repr(p))
    else:
        rec("PASS", "规则 prelude", "%d 条规则的 prelude 全部恰好是 :root" % rules)
    return rules


def check_declarations_reachable(css, expected_names):
    """每个 token 的声明都必须落在某个 prelude 恰好为 :root 的规则里。"""
    live, _ = strip_css_comments(css)
    reachable, prelude_start = set(), 0
    for m in re.finditer(r"\{", live):
        prelude = live[prelude_start:m.start()].strip()
        depth, k = 1, m.end()
        while k < len(live) and depth:
            if live[k] == "{":
                depth += 1
            elif live[k] == "}":
                depth -= 1
            k += 1
        if prelude == ":root":
            reachable |= set(re.findall(r"(--[A-Za-z][A-Za-z0-9_-]*)\s*:", live[m.end():k]))
        prelude_start = k
    missing = sorted(n for n in expected_names if n not in reachable)
    if missing:
        rec("FAIL", "声明可达性", "%d 个 token 在浏览器里永不生效：%s"
            % (len(missing), "、".join(missing[:10])))
    else:
        rec("PASS", "声明可达性", "%d 个 token 的声明都落在 prelude=:root 的规则里" % len(expected_names))


def norm(v):
    return re.sub(r"\s+", " ", v.strip()).lower().replace(", ", ",")


# ---------------------------------------------------------------- 颜色
def parse_color(s):
    s = s.strip()
    m = re.fullmatch(r"#([0-9A-Fa-f]{6})", s)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", s, re.I)
    if m:
        return (int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3))),
                float(m.group(4)) if m.group(4) is not None else 1.0)
    return None


def over(fg, bg):
    """fg 叠在 bg 上（bg 必须不透明）。"""
    a = fg[3]
    return (round(fg[0] * a + bg[0] * (1 - a)),
            round(fg[1] * a + bg[1] * (1 - a)),
            round(fg[2] * a + bg[2] * (1 - a)), 1.0)


def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(c):
    return 0.2126 * _lin(c[0]) + 0.7152 * _lin(c[1]) + 0.0722 * _lin(c[2])


def contrast_ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------- 分层校验
def check_purity(layer, items, table):
    for name, val, _d, _g in items:
        bare = VAR_RE.sub("", val)
        # 禁：裸色值
        for rx, what in ((HEX_RE, "hex"), (RGBA_RE, "rgb/rgba"), (HSL_RE, "hsl/hsla")):
            if rx.search(bare):
                rec("FAIL", "分层纯度·%s" % layer, "%s 含裸%s：%s" % (name, what, val))
        # 禁：带单位的裸长度
        m = LEN_RE.search(bare) or PCT_RE.search(bare)
        if m:
            rec("FAIL", "分层纯度·%s" % layer, "%s 含带单位裸长度：%s" % (name, val))
        if not VAR_RE.search(val):
            # 只允许无单位数值 / 关键字 / 零
            allowed = re.fullmatch(
                r"[-\d.\s]+|(transparent|auto|none|inherit|currentcolor|tabular-nums|linear|"
                r"proportional-nums|normal|hidden|visible|solid|dashed|break-word)", bare.strip(), re.I)
            if not allowed:
                rec("FAIL", "分层纯度·%s" % layer, "%s 无 var() 引用且非白名单字面量：%s" % (name, val))


def check_l2_only_primitives(items):
    for name, val, _d, _g in items:
        for ref in VAR_RE.findall(val):
            if not ref.startswith("--p-"):
                rec("FAIL", "L2 只指向 L1", "%s 引用了 %s（应为 --p-*）" % (name, ref))


def check_l3_color_via_l2(data):
    """L3 取色必须经 L2。尺度类原语（space/radius/fs/lh/fw/bw/size/duration/easing/z/opacity/font）允许直取。"""
    color_prims = set()
    for gname, g in layer_groups(data["primitive"]):
        if (gname or "").startswith("color."):
            color_prims |= {k for k in g if not k.startswith("_")}
    for name, val, _d, _g in flatten(data["component"]):
        for ref in VAR_RE.findall(val):
            if ref in color_prims:
                rec("FAIL", "L3 取色必须经 L2", "%s 直接引用了颜色原语 %s，应在 L2 增加语义别名" % (name, ref))


def check_defined(all_names, tables):
    for name, val, _d, _g in all_names:
        for ref in VAR_RE.findall(val):
            if ref not in tables:
                rec("FAIL", "引用完整性", "%s 引用了未定义的 %s" % (name, ref))


# ---------------------------------------------------------------- 断点
def check_media_literals(paths, allowed):
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            txt = f.read()
        for m in MEDIA_RE.finditer(txt):
            v = int(m.group(1))
            if v not in allowed:
                rec("FAIL", "断点字面量", "%s 出现未登记断点 %dpx" % (os.path.basename(p), v))


# ---------------------------------------------------------------- rb.css 等价
def rb_parity(rb_table, all_table):
    """rb.css 的每个 :root 变量，必须与新系统的解析值逐值等价。"""
    missing, mismatch, ok = [], [], 0
    for name, raw in rb_table.items():
        a, ea = resolve(name, rb_table)
        b, eb = resolve(name, all_table)
        if eb:
            missing.append((name, eb))
            continue
        if ea:
            rec("WARN", "rb.css 解析", "%s 在 rb.css 内无法解析：%s" % (name, ea))
            continue
        if norm(a) != norm(b):
            mismatch.append((name, a, b))
        else:
            ok += 1
    for name, err in missing:
        rec("FAIL", "rb.css 等价性", "%s 在新系统中缺失或不可解析：%s" % (name, err))
    for name, a, b in mismatch:
        rec("FAIL", "rb.css 等价性", "%s 值不一致：rb.css=%s / tokens.css=%s" % (name, a, b))
    return ok, len(rb_table)


def read_root_vars(path):
    """读一个文件 :root 里的变量。先剥注释——注释里的 `---- 品牌色 ----` 会被误当成变量名。"""
    with open(path, encoding="utf-8") as f:
        txt = re.sub(r"/\*.*?\*/", "", f.read(), flags=re.S)
    m = re.search(r":root\s*\{(.*?)\n\}", txt, re.S)
    if not m:
        return {}
    return {("--" + k): v.strip() for k, v in
            re.findall(r"--([A-Za-z][A-Za-z0-9_-]*)\s*:\s*([^;{}]+);", m.group(1))}


# ---------------------------------------------------------------- 迁移表
# rb.css 里尚未 token 化的字面量 → 新系统所属 token。
# rb.css 保持原样（已冻结且已验证），本表是 Vue 阶段消费 tokens.css 时的对照依据。
MIGRATION = [
    ("`.btn--primary` 文字色", "#FFFFFF ×1", "--p-white", "--btn-primary-fg"),
    ("`.bph` 文字色", "#FFFFFF ×1", "--p-white", "评审外壳，刻意不纳入系统"),
    ("`.navlink:hover` 底色", "rgba(28,25,23,.04)", "--p-ink-900-a04", "--navlink-bg-hover"),
    ("`--bg-readonly` 来源值", "rgba(28,25,23,.03)", "--p-ink-900-a03", "--bg-readonly"),
    ("`--shadow-hair` 来源值", "rgba(28,25,23,.04)", "--p-ink-900-a04", "--p-shadow-1 → --elevation-card"),
    ("`.appbar` / `.tabbar` z-index", "40 ×2", "--p-z-appbar / --p-z-tabbar", "--appbar-z / --tabbar-z"),
    ("`.composer` z-index", "20", "--p-z-composer", "--composer-z"),
    ("`.skip-link` z-index", "60", "--p-z-skiplink", "--skiplink-z"),
    ("`.step--running` 旋转", "1.1s linear", "--p-duration-spin / --p-easing-linear", "--motion-spin-duration / --motion-spin-easing"),
    ("`.appbar__mark` 圆角", "7px", "--p-radius-7", "--brand-mark-radius"),
    ("`.login__mark` 圆角", "10px", "--p-radius-10", "--brand-mark-radius-lg"),
    ("`:focus-visible` 圆角", "4px", "--p-radius-4", "--focus-outline-radius"),
    ("`.appbar__mark` / `.login__mark` 尺寸", "26px / 38px", "--p-size-mark-sm / --p-size-mark-lg", "--brand-mark-size / --brand-mark-size-lg"),
    ("`.textarea` 最小高", "120px", "--p-size-textarea-min", "--control-textarea-min-h"),
    ("`.table .cell-name` 最小宽", "180px", "--p-size-cellname-min", "--table-cellname-min-w"),
    ("`.login` 最大宽", "420px", "--p-size-login-max", "--login-max-w"),
    ("`.prose` 最大宽", "68ch", "--p-size-prose-max", "--prose-max"),
    ("`.bubble` xs 限宽", "88%", "--p-size-bubble-max", "--bubble-max-w-xs"),
    ("`.table--stack td` 字段名列宽", "7.5em", "--p-size-label-col", "--table-stack-label-col"),
    ("`.kv__row` 键列宽", "8em", "--p-size-kv-key-col", "--kv-row-key-col"),
    ("`.skip-link` 屏外偏移", "-100px", "--p-offset-offscreen", "--skiplink-offset-y-hidden"),
    (".pill 内边距 / 间距", "2px 10px / 5px", "--p-space-2px / --p-space-10px / --p-space-5px", "--pill-pad-y / --pill-pad-x / --pill-gap"),
    ("`.table--stack td` 单元格内边距", "5px 0", "--p-space-5px", "--table-stack-cell-pad-y"),
    ("`.table--compact` 内边距", "8px", "--p-space-8px", "--table-compact-pad-y"),
    ("`.table--stack td.cell-name` 下边距", "8px", "--p-space-8px", "--table-stack-name-pad-b"),
    ("`.input` 等纵向内边距", "10px", "--p-space-10px", "--control-pad-y"),
    ("`.step__ico` 顶部偏移", "3px", "--p-space-3px", "--step-ico-offset-y"),
    ("`.notice__ico` 顶部偏移", "2px", "--p-space-2px", "--notice-ico-offset-y"),
    ("`.tabbar__item` 图标与文字间距", "2px", "--p-space-2px", "--tabbar-item-gap"),
    ("`.field--invalid` 外描边", "box-shadow 0 0 0 3px", "--p-bw-3", "--control-invalid-ring"),
    ("`.cite` 左侧色条宽", "4px", "--p-bw-4", "--cite-accent-w"),
    ("`.draft` 虚线边宽", "2px", "--p-bw-2", "--draft-border-w"),
]


def bp_items(data):
    """breakpoint 段落里的真实断点项（跳过 _note / note 之类的说明字段）。"""
    return [(k, v) for k, v in data["breakpoint"].items()
            if isinstance(v, dict) and not k.startswith("_") and "v" in v]


# ---------------------------------------------------------------- 生成 CSS
HEAD = """/* ============================================================================
   校园课程智能助手 · 设计系统 token（方向 B）   tokens.css
   ----------------------------------------------------------------------------
   本文件由 design/system/generate.py 从 tokens.json 生成，**请勿手改**。
   重新生成：$env:PYTHONIOENCODING="utf-8"; python design\\system\\generate.py

   四层结构（层序即 :root 书写顺序，后者可安全覆盖前者）：
     L1 primitive  --p-*                  原始值。唯一允许出现字面量的一层。
     L2 semantic   --bg-* / --text-* / …  用途别名，只指向 L1。颜色语义在此收敛。
     L3 component  --<组件>-<部位>-<属性>  组件属性。颜色必须经 L2，尺度类原语可直取 L1。
                                          组件 CSS 规则只消费这一层。
     L0 compat     --c-* / --sp-* / …     rb.css 变量名的兼容声明（deprecated）。
                                          rb.css 的 75 个 :root 变量里有 25 个已由 L2/L3 同名承担
                                          （24 个 L2 + L3 的 --root-scroll-offset），
                                          不在此重复声明——重复会导致变量自引用而失效。

   注意：本注释里**绝对不能出现「星号紧跟斜杠」两个字符**：那会提前终止注释，
   让紧随其后的第一个 :root 块被并进一个永不匹配的垃圾选择器（品牌绿会整体失效，
   而纯文本比对查不出来）。generate.py 已加 check_comment_safety() 守这条；
   写 glob 通配时请用「星号 空格 斜杠」。

   断点（min-width，mobile-first）：{bps}
   媒体查询无法引用 CSS 变量，必须写字面量，取值只能来自上表。
   ============================================================================ */
"""


def gen_css(data, resolved):
    bp_txt = " / ".join("%s=%d" % (k, v["v"]) for k, v in bp_items(data) if k != "base") + " / base=<480"
    out = [HEAD.format(bps=bp_txt)]
    titles = {
        "primitive": "L1 · primitive —— 原始值（唯一允许字面量的一层）",
        "semantic": "L2 · semantic —— 用途别名（只指向 L1）",
        "component": "L3 · component —— 组件属性（颜色经 L2，尺度类原语可直取 L1；组件规则只消费这一层）",
        "compat": "L0 · compat —— rb.css 兼容层（deprecated，新代码不得引用）",
    }
    for layer in ("primitive", "semantic", "component", "compat"):
        out.append("\n/* ======================== %s ======================== */" % titles[layer])
        for gname, g in layer_groups(data[layer]):
            note = g.get("_note")
            if gname:
                out.append("/* ---- %s%s ---- */" % (gname, ("　" + note) if note else ""))
            out.append(":root{")
            if note and not gname:
                out.append("  /* %s */" % note)
            for k, v in g.items():
                if k.startswith("_"):
                    continue
                line = "  %s:%s;" % (k, v["v"])
                if v.get("d"):
                    line = line.ljust(58) + " /* %s */" % v["d"]
                out.append(line)
            out.append("}")
        out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 生成 MD
def gen_md(data, all_items, resolved, contrast_rows, unused, parity, unused_classes_note):
    L = []
    A = L.append
    A("# 设计系统 token 参考（自动生成）\n")
    A("> 本文件由 `design/system/generate.py` 从 [`tokens.json`](tokens.json) 生成，**请勿手改**。")
    A("> 数值列是解析到字面量后的最终值（`var()` 链已展开）。\n")
    A("## 1. 分层与规则\n")
    A("| 层 | 前缀 | 职责 | 允许的值 | 数量 |")
    A("| --- | --- | --- | --- | --- |")
    counts = {}
    for layer in ("primitive", "semantic", "component", "compat"):
        counts[layer] = len(flatten(data[layer]))
    A("| L1 primitive | `--p-*` | 原始值，只描述「是什么」 | 字面量 | %d |" % counts["primitive"])
    A("| L2 semantic | `--bg-*` `--text-*` `--accent*` `--state-*` `--border*` `--layout-*` … | 用途别名 | 只 `var(--p-*)` | %d |" % counts["semantic"])
    A("| L3 component | `--<组件>-<部位>-<属性>` | 组件属性 | 只 `var()`；无单位数值/关键字除外 | %d |" % counts["component"])
    A("| L0 compat | `--c-*` `--sp-*` `--fs-*` … | rb.css 兼容，deprecated | `var()` | %d |" % counts["compat"])
    A("")
    for r in data["meta"]["purity_rules"]:
        A("- %s" % r)
    A("")
    A("## 2. 断点\n")
    A("| 档 | min-width | 作用 |")
    A("| --- | --- | --- |")
    for k, v in bp_items(data):
        A("| %s | %s | %s |" % (k, "无媒体查询（基准）" if v["v"] == 0 else "≥%dpx" % v["v"], v["d"]))
    A("")
    A("## 3. L1 primitive\n")
    for gname, g in layer_groups(data["primitive"]):
        A("### %s\n" % gname)
        if g.get("_note"):
            A("%s\n" % g["_note"])
        A("| token | 值 | 说明 |")
        A("| --- | --- | --- |")
        for k, v in g.items():
            if k.startswith("_"):
                continue
            A("| `%s` | `%s` | %s |" % (k, v["v"], v.get("d", "")))
        A("")
    A("## 4. L2 semantic\n")
    for gname, g in layer_groups(data["semantic"]):
        A("### %s\n" % gname)
        A("| token | 指向 | 解析值 | 说明 |")
        A("| --- | --- | --- | --- |")
        for k, v in g.items():
            if k.startswith("_"):
                continue
            A("| `%s` | `%s` | `%s` | %s |" % (k, v["v"], resolved.get(k, ""), v.get("d", "")))
        A("")
    A("## 5. L3 component\n")
    for gname, g in layer_groups(data["component"]):
        A("### %s\n" % gname)
        A("| token | 指向 | 解析值 | 说明 |")
        A("| --- | --- | --- | --- |")
        for k, v in g.items():
            if k.startswith("_"):
                continue
            A("| `%s` | `%s` | `%s` | %s |" % (k, v["v"], resolved.get(k, ""), v.get("d", "")))
        A("")
    A("## 6. L0 compat（deprecated）\n")
    A("保留 rb.css 的 75 个 `:root` 变量名中不与 L2/L3 重名的 50 个，逐值等价（见 §9 等价性证明）。新代码不得引用。\n")
    A("| token | 指向 | 解析值 |")
    A("| --- | --- | --- |")
    for _gname, g in layer_groups(data["compat"]):
        for k, v in g.items():
            if k.startswith("_"):
                continue
            A("| `%s` | `%s` | `%s` |" % (k, v["v"], resolved.get(k, "")))
    A("")
    A("## 7. 对比度（实测，含 alpha 合成）\n")
    A("判据：文字 4.5:1（WCAG 1.4.3 AA）；UI 边界 3:1（WCAG 1.4.11）。")
    A("含 alpha 的底先与卡片底合成，含 alpha 的前景先与底合成——这是对第 2 轮「未做 alpha 合成」的补齐。\n")
    A("| 配对 | 前景 | 底 | 要求 | 实测 | 判定 |")
    A("| --- | --- | --- | --- | --- | --- |")
    for r in contrast_rows:
        A("| %s | `%s` | `%s` | ≥%.1f | %.2f:1 | %s |" %
          (r["n"], r["fg"], r["bg"], r["min"], r["ratio"], "PASS" if r["ok"] else "**FAIL**"))
    A("")
    if data["contrast"].get("judgment"):
        A("### 判定项（不是已证实事实）\n")
        for j in data["contrast"]["judgment"]:
            A("**%s** —— 比值 %s\n" % (j["n"], j["ratio"]))
            A("- 结论：%s" % j["verdict"])
            A("- 理由：%s" % j["reason"])
            A("- 若被推翻：%s\n" % j["if_challenged"])
    A("## 8. 覆盖度\n")
    A("- L1 primitive 未被任何 L2/L3/L0 引用的：%s" %
      ("无" if not unused else "、".join("`%s`" % u for u in unused)))
    A("- rb.css 未被 token 化的裸字面量 → 迁移对照：见 §10。")
    A("- 未被任何视图使用的 class：%s" % unused_classes_note)
    A("")
    A("## 9. rb.css 等价性证明\n")
    A("判据：rb.css `:root` 的每个变量，其**解析后字面值**必须在 tokens.css 中逐字相等。")
    A("这样已验证的响应式原型零改动继续工作，设计系统是它的严格超集。\n")
    A("- rb.css `:root` 变量数：**%d**" % parity[1])
    A("- 逐值等价通过：**%d**" % parity[0])
    A("- 不一致：**%d**" % (parity[1] - parity[0]))
    A("")
    A("## 10. 裸字面量迁移对照\n")
    A("rb.css 保持冻结（已独立验证），因此不改写；下表是 Vue 阶段消费 tokens.css 时的对照依据。\n")
    A("| rb.css 位置 | 裸字面量 | L1 token | L3 消费方 |")
    A("| --- | --- | --- | --- |")
    for row in MIGRATION:
        if len(row) == 4:
            A("| %s | `%s` | `%s` | %s |" % row)
    A("")
    A("## 11. 变更记录\n")
    for c in data.get("changeLog", []):
        A("- **v%s** —— %s" % (c["v"], c["d"]))
    A("")
    return "\n".join(L)


# ---------------------------------------------------------------- 生成 TS
def gen_ts(data, resolved):
    L = ["// 设计系统 token（方向 B）· 由 design/system/generate.py 生成，请勿手改。",
         "// 用途：Vue 3 + TS 侧读取断点与 token 解析值；样式请优先用 tokens.css 的 CSS 变量。",
         "", "export const breakpoints = {"]
    for k, v in bp_items(data):
        L.append("  %s: %d," % (k, v["v"]))
    L += ["} as const;", "", "export type BreakpointName = keyof typeof breakpoints;", "",
          "/** 断点升序数组，供 matchMedia / ResizeObserver 逻辑使用 */",
          "export const breakpointList = (Object.keys(breakpoints) as BreakpointName[])",
          "  .filter((k) => breakpoints[k] > 0)",
          "  .sort((a, b) => breakpoints[a] - breakpoints[b]);", "",
          "/** 全部 token 的解析后字面值（var() 链已展开） */", "export const tokens = {"]
    for k in sorted(resolved):
        L.append('  "%s": %s,' % (k, json.dumps(resolved[k], ensure_ascii=False)))
    L += ["} as const;", "", "export type TokenName = keyof typeof tokens;", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- main
def main():
    data = load()
    tables = {}
    all_items = []
    for layer in ("primitive", "semantic", "component", "compat"):
        items = flatten(data[layer])
        all_items += items
        for name, val, _d, _g in items:
            if name in tables:
                rec("FAIL", "命名唯一性", "%s 在多层重复定义" % name)
            tables[name] = val

    check_defined(all_items, tables)
    check_l2_only_primitives(flatten(data["semantic"]))
    check_l3_color_via_l2(data)

    # 注释安全：注释里出现「星号紧跟斜杠」会让后面的 :root 块被并进垃圾选择器
    comments = [("tokens.css 文件头", HEAD)]
    for layer in ("primitive", "semantic", "component", "compat"):
        for gname, g in layer_groups(data[layer]):
            if g.get("_note"):
                comments.append(("%s._note" % (gname or layer), g["_note"]))
            for k, v in g.items():
                if not k.startswith("_") and isinstance(v, dict) and v.get("d"):
                    comments.append(("%s 的说明" % k, v["d"]))
    check_comment_safety(comments)

    # 分层纯度：L2 / L3 严格；L1 只要求「值存在」
    check_purity("L2", flatten(data["semantic"]), tables)
    check_purity("L3", flatten(data["component"]), tables)

    # 解析全部
    resolved, bad = {}, []
    for name in tables:
        v, err = resolve(name, tables)
        if err:
            bad.append((name, err))
        else:
            resolved[name] = v
    for name, err in bad:
        rec("FAIL", "解析", "%s：%s" % (name, err))

    # 未使用的 L1
    used = set()
    for name in tables:
        for ref in VAR_RE.findall(tables[name]):
            used.add(ref)
    skip = set()
    for g in ("motion",):
        for k, v in data["primitive"].get(g, {}).items():
            if isinstance(v, dict) and "已定义未使用" in v.get("d", ""):
                skip.add(k)
    unused = [k for k, _v, _d, _g in flatten(data["primitive"]) if k not in used and k not in skip]
    if unused:
        rec("WARN", "L1 覆盖度", "未被引用的 primitive：%s" % "、".join(unused))
    else:
        rec("PASS", "L1 覆盖度", "全部 %d 个 primitive 都有引用面" % len(flatten(data["primitive"])))

    # 对比度
    rows = []
    for p in data["contrast"]["pairs"]:
        need = data["contrast"]["tiers"][p["tier"]]
        fg_s, bg_s = resolved.get(p["fg"]), resolved.get(p["bg"])
        if fg_s is None or bg_s is None:
            rec("FAIL", "对比度", "%s 引用了不存在的 token" % p["n"])
            continue
        fg, bg = parse_color(fg_s), parse_color(bg_s)
        if fg is None or bg is None:
            rec("WARN", "对比度", "%s 无法解析颜色：%s / %s" % (p["n"], fg_s, bg_s))
            continue
        white = (255, 255, 255, 1.0)
        if bg[3] < 1.0:
            bg = over(bg, white)      # 半透明底先合成到卡片底（白）
        if fg[3] < 1.0:
            fg = over(fg, bg)
        r = contrast_ratio(fg, bg)
        ok = r >= need
        rows.append({"n": p["n"], "fg": p["fg"], "bg": p["bg"], "min": need, "ratio": r, "ok": ok})
        if not ok:
            rec("FAIL", "对比度", "%s：%.2f:1 < %.1f" % (p["n"], r, need))
    if rows and all(r["ok"] for r in rows):
        rec("PASS", "对比度（含 alpha 合成）", "%d 对全部达标" % len(rows))

    # rb.css 等价
    rb_table = read_root_vars(RB_CSS)
    parity = rb_parity(rb_table, tables) if rb_table else (0, 0)
    if rb_table and parity[0] == parity[1]:
        rec("PASS", "rb.css 等价性", "%d/%d 逐值等价" % parity)

    # 断点字面量
    # 断点字面量：min-width 用原值，max-width 只允许「档−1」
    bp_ok = set()
    for k, v in bp_items(data):
        if v["v"] > 0:
            bp_ok.add(v["v"])
            bp_ok.add(v["v"] - 1)
    check_media_literals([os.path.join(HERE, "tokens.css"),
                          os.path.join(HERE, "system.html"),
                          os.path.join(DESIGN, "responsive", "rb.css")],
                         bp_ok)

    unused_classes_note = "`chip` `draft--saved` `notice--evidence` `pill--pending` `prose` `r`（6 个，已在 rb.css 定义但无视图使用；本系统保留它们的 token，供 Vue 阶段接入）"

    # 产出
    css = gen_css(data, resolved)
    # 在写盘前先证明「声明真的会在浏览器里生效」——文本比对与字节比对都查不出这件事
    check_rule_preludes(css)
    check_declarations_reachable(css, tables.keys())
    md = gen_md(data, all_items, resolved, rows, unused, parity, unused_classes_note)
    ts = gen_ts(data, resolved)
    for fname, content in (("tokens.css", css), ("tokens.md", md), ("tokens.ts", ts)):
        with open(os.path.join(HERE, fname), "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    with open(os.path.join(HERE, "tokens.flat.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(resolved, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")

    # 报告
    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print("=" * 78)
    print("设计系统 token 生成报告   tokens.json -> tokens.css / tokens.md / tokens.ts")
    print("=" * 78)
    for layer in ("primitive", "semantic", "component", "compat"):
        print("  %-10s %3d 个 token" % (layer, counts_of(data, layer)))
    print("  合计       %3d" % len(tables))
    print("  L1 未被引用 %3d" % len(unused))
    print("  对比度配对 %3d，全部达标 %s" % (len(rows), "是" if rows and all(r["ok"] for r in rows) else "否"))
    print("  rb.css 等价 %d/%d" % parity)
    print("-" * 78)
    for lv in ("PASS", "WARN", "FAIL"):
        for level, name, detail in results:
            if level == lv:
                print("[%-4s] %-22s %s" % (level, name, detail))
    print("-" * 78)
    print("FAIL %d / WARN %d" % (len(fails), len(warns)))
    if fails:
        print("生成失败：请先修 tokens.json，不要使用本次产出。")
        return 1
    print("已写出：tokens.css  tokens.md  tokens.ts  tokens.flat.json")
    return 0


def counts_of(data, layer):
    return len(flatten(data[layer]))


if __name__ == "__main__":
    sys.exit(main())
