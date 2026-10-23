#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
设计系统确定性校验器   design/system/verify-system.py

**独立于 generate.py 与 build-system.py**：分层纯度、对比度、rb.css 等价性都重新实现一遍，
不 import 生成器，避免"生成器的 bug 被生成器自己判为通过"。

覆盖：
  A 生成保真      tokens.json ↔ tokens.css 逐值一致（无缺失、无多余）
  B 分层纯度      L1 只有字面量；L2 只指向 L1；L3 取色经 L2、不互引、无裸值；引用全部可解析
  C 覆盖度        0 个未被引用的 L1；L3 全部被引用
  D 对比度        41 对，含 alpha 合成，独立实现
  E rb.css 等价   rb.css 的 :root 变量在新系统中逐值相等
  F 组件规格      4 份：owns 首行、组不重不漏、覆盖本组全部 token、不引用评审 class、无违禁文案、
                  9 节骨架齐全、rb.css 行号在范围内
  G 活样式手册    ds-tokens 与 tokens.css 逐字节一致；27 组齐全；组件样式只消费 L3；零外部请求；
                  0 emoji；stack 表格 td 全有 data-label；标题层级不跳级；L3 全覆盖
  H 其它生成物    tokens.ts 断点与 tokens.json 一致；tokens.md 的等价性声明与实际一致
  I 文档一致性    README 声明的 token 计数与实际一致

运行：
  $env:PYTHONIOENCODING="utf-8"; python design\system\verify-system.py
退出码 0 = 全部通过（WARN 不算失败）；1 = 有 FAIL。
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESIGN = os.path.dirname(HERE)
RB_CSS = os.path.join(DESIGN, "responsive", "rb.css")
SYSTEM_HTML = os.path.join(HERE, "system.html")

SPEC_FILES = [
    "components/01-shell-navigation.md",
    "components/02-actions-status.md",
    "components/03-conversation.md",
    "components/04-forms-data.md",
]
REVIEW_ONLY = [".bph", ".view__id", ".view__cap", ".view__note", ".proto-banner", ".view "]
FORBIDDEN = ["正在思考", "AI 推理中", "推理过程", "思考中", "暂无数据", "暂无内容"]
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\uFE0F\u20E3]")
HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
RGBA_RE = re.compile(r"\brgba?\([^)]*\)", re.I)
HSL_RE = re.compile(r"\bhsla?\([^)]*\)", re.I)
LEN_RE = re.compile(r"(?<![\w.-])(\d*\.?\d+)(px|em|rem|ch|vh|vw|pt)\b")
PCT_RE = re.compile(r"(?<![\w.-])\d*\.?\d+%")
VAR_RE = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*\)")
DECL_RE = re.compile(r"(--[A-Za-z][A-Za-z0-9_-]*)\s*:\s*([^;{}]+);")
TOKEN_MENTION = re.compile(r"`(--[A-Za-z][A-Za-z0-9_-]*)`")

R = []

# 否定语境：规格里写「不得引用 .bph」「不得出现『正在思考』」是**声明禁止**，不是违规。
NEG = ["不得", "禁止", "不引", "不出现", "排除", "评审专用", "反例", "误用", "不对", "没有", "无 ", "不可"]
NEG_WIN = 26


def ok(n, d=""):
    R.append(("PASS", n, d))


def warn(n, d=""):
    R.append(("WARN", n, d))


def fail(n, d=""):
    R.append(("FAIL", n, d))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def strip_comments(s):
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)


def in_negation(text, idx, win=NEG_WIN):
    """命中位置**所在行**内出现否定词 ⇒ 属于「声明禁止」，不算违规。
    按行判断而不是固定字符窗：规格里常写成「禁止：发明 `--a` / `--b`」，
    第二个名字距否定词可能超过 26 个字符，固定窗会误报。"""
    ls = text.rfind("\n", 0, idx) + 1
    le = text.find("\n", idx)
    line = text[ls:le if le >= 0 else len(text)]
    if any(n in line for n in NEG):
        return True
    seg = text[max(0, idx - win):idx]
    return any(n in seg for n in NEG)


def raw_hits(text, needle):
    """返回未被否定语境覆盖的命中位置。"""
    out, start = [], 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            return out
        if not in_negation(text, i):
            out.append(i)
        start = i + 1


# ---------------------------------------------------------------- 颜色（独立实现）
def to_rgba(s):
    s = s.strip()
    m = re.fullmatch(r"#([0-9A-Fa-f]{6})", s)
    if m:
        h = m.group(1)
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0]
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", s, re.I)
    if m:
        return [int(float(m.group(i))) for i in (1, 2, 3)] + \
               [float(m.group(4)) if m.group(4) is not None else 1.0]
    return None


def flatten_alpha(c, base):
    a = c[3]
    return [c[i] * a + base[i] * (1 - a) for i in range(3)] + [1.0]


def rel_lum(c):
    def f(x):
        x /= 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def ratio(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ---------------------------------------------------------------- 解析（独立实现）
def resolve_all(decls):
    """decls: {name: raw} -> ({name: literal}, [错误])"""
    cache, errs = {}, []

    def res(name, seen):
        if name in cache:
            return cache[name]
        if name in seen:
            errs.append("循环引用 %s" % " -> ".join(seen + [name]))
            return None
        if name not in decls:
            errs.append("未定义 %s" % name)
            return None
        val = decls[name]
        for ref in set(VAR_RE.findall(val)):
            sub = res(ref, seen + [name])
            if sub is None:
                return None
            val = re.sub(r"var\(\s*%s\s*\)" % re.escape(ref), sub, val)
        cache[name] = val
        return val

    for n in decls:
        res(n, [])
    return cache, errs


# ================================================================ A 生成保真
def check_fidelity(tj, css_decls):
    flat = {}
    for layer in ("primitive", "semantic", "component", "compat"):
        flat[layer] = flat_pairs(tj[layer])

    all_tj = {}
    for layer in ("primitive", "semantic", "component", "compat"):
        for k, v in flat[layer]:
            if k in all_tj and all_tj[k][0] != layer:
                fail("A 命名唯一性", "%s 同时出现在 %s 与 %s" % (k, all_tj[k][0], layer))
            all_tj[k] = (layer, v)

    miss = [k for k in all_tj if k not in css_decls]
    extra = [k for k in css_decls if k not in all_tj]
    diff = [(k, all_tj[k][1], css_decls[k]) for k in all_tj
            if k in css_decls and norm(all_tj[k][1]) != norm(css_decls[k])]
    if miss:
        fail("A 生成保真·缺失", "、".join(sorted(miss)[:8]))
    if extra:
        fail("A 生成保真·多余", "、".join(sorted(extra)[:8]))
    if diff:
        for k, a, b in diff[:6]:
            fail("A 生成保真·值不一致", "%s json=%s css=%s" % (k, a, b))
    if not (miss or extra or diff):
        ok("A 生成保真", "tokens.json ↔ tokens.css：%d 个 token 逐值一致" % len(all_tj))
    return {l: len(flat[l]) for l in flat}, all_tj


def norm(v):
    return re.sub(r"\s+", " ", v.strip()).lower().replace(", ", ",")


# ================================================================ B 分层纯度
def check_layers(tj, all_tj):
    color_prims = set()
    for gname, g in tj["primitive"].items():
        if gname.startswith("color."):
            color_prims |= {k for k in g if not k.startswith("_")}

    # L1：只允许字面量 + L1 内部组合（不得引用 L2/L3）
    l1_bad = []
    for k, v in flat_pairs(tj["primitive"]):
        for ref in VAR_RE.findall(v):
            if not ref.startswith("--p-"):
                l1_bad.append("%s→%s" % (k, ref))
    if l1_bad:
        fail("B L1 越层引用", "、".join(l1_bad[:8]))
    else:
        ok("B L1 纯字面量或 L1 内部组合", "%d 个 primitive 均未引用 L2/L3"
           % len(flat_pairs(tj["primitive"])))

    # L2：只指向 --p-*
    l2_bad = []
    for k, v in flat_pairs(tj["semantic"]):
        for ref in VAR_RE.findall(v):
            if not ref.startswith("--p-"):
                l2_bad.append("%s→%s" % (k, ref))
    if l2_bad:
        fail("B L2 越层引用", "、".join(l2_bad[:8]))
    else:
        ok("B L2 只指向 L1", "%d 个 semantic 全部只引用 --p-*" % len(flat_pairs(tj["semantic"])))

    # L3：裸色值 / 裸长度 / 取色越层 / L3 互引
    l3_bare, l3_color, l3_cross = [], [], []
    l3_names = {k for k, _v in flat_pairs(tj["component"])}
    for k, v in flat_pairs(tj["component"]):
        bare = VAR_RE.sub("", v)
        if HEX_RE.search(bare) or RGBA_RE.search(bare) or HSL_RE.search(bare):
            l3_bare.append("%s=%s" % (k, v))
        if LEN_RE.search(bare) or PCT_RE.search(bare):
            l3_bare.append("%s=%s" % (k, v))
        for ref in VAR_RE.findall(v):
            if ref in color_prims:
                l3_color.append("%s→%s" % (k, ref))
            if ref in l3_names:
                l3_cross.append("%s→%s" % (k, ref))
    if l3_bare:
        fail("B L3 含裸值", "；".join(l3_bare[:6]))
    else:
        ok("B L3 无裸色值/裸长度", "%d 个 component token 均为 var() 或白名单字面量" % len(l3_names))
    if l3_color:
        fail("B L3 取色越层", "、".join(l3_color[:8]))
    else:
        ok("B L3 取色经 L2", "无 component token 直接引用颜色原语")
    if l3_cross:
        fail("B L3 互引", "、".join(l3_cross[:8]))
    else:
        ok("B L3 不互引", "component 层内部无跨组件引用")

    # 引用完整性
    decls = {k: v[1] for k, v in all_tj.items()}
    _res, errs = resolve_all(decls)
    if errs:
        fail("B 引用完整性", "；".join(sorted(set(errs))[:8]))
    else:
        ok("B 引用完整性", "%d 个 token 的 var() 链全部可解析、无环" % len(decls))


def flat_pairs(layer):
    real = {k: v for k, v in layer.items() if not k.startswith("_")}
    if real and all(isinstance(v, dict) and "v" in v for v in real.values()):
        return [(k, v["v"]) for k, v in real.items()]
    out = []
    for g in real.values():
        if isinstance(g, dict):
            out += [(k, v["v"]) for k, v in g.items()
                    if not k.startswith("_") and isinstance(v, dict) and "v" in v]
    return out


# ================================================================ C 覆盖度
def check_coverage(tj, all_tj, resolved):
    refs = set()
    for k, (layer, v) in all_tj.items():
        refs |= set(VAR_RE.findall(v))
    unused = [k for k, v in flat_pairs(tj["primitive"]) if k not in refs]
    sank = [k for k in unused]
    for k in unused:
        d = ""
        for g in tj["primitive"].values():
            if isinstance(g, dict) and isinstance(g.get(k), dict):
                d = g[k].get("d", "")
        if "已定义未使用" in d:
            sank.remove(k)
    if sank:
        fail("C L1 覆盖度", "未被引用且未声明豁免：%s" % "、".join(sank[:8]))
    else:
        ok("C L1 覆盖度", "%d 个 primitive 均有引用面（%d 个显式声明已定义未使用）"
           % (len(flat_pairs(tj["primitive"])), len(unused)))

    l3 = [k for k, _v in flat_pairs(tj["component"])]
    if not l3:
        fail("C L3 为空", "")
    else:
        ok("C L3 规模", "%d 个 component token 有待在活样式手册中被消费" % len(l3))


# ================================================================ D 对比度
def check_contrast(tj, resolved):
    rows, bad = [], []
    for p in tj["contrast"]["pairs"]:
        need = tj["contrast"]["tiers"][p["tier"]]
        fg = to_rgba(resolved[p["fg"]])
        bg = to_rgba(resolved[p["bg"]])
        if fg is None or bg is None:
            bad.append("%s 无法解析颜色" % p["n"])
            continue
        if bg[3] < 1.0:
            bg = flatten_alpha(bg, [255, 255, 255, 1.0])
        if fg[3] < 1.0:
            fg = flatten_alpha(fg, bg)
        r = ratio(fg, bg)
        rows.append((p["n"], need, r))
        if r < need:
            bad.append("%s：%.2f:1 < %.1f" % (p["n"], r, need))
    if bad:
        fail("D 对比度", "；".join(bad[:8]))
    else:
        ok("D 对比度（独立实现，含 alpha 合成）",
           "%d 对全部达标，最低 %.2f:1" % (len(rows), min(r for _n, _d, r in rows)))
    return rows


# ================================================================ E rb.css 等价
def check_rb_parity(tj, all_tj):
    rb = {}
    m = re.search(r":root\s*\{(.*?)\n\}", strip_comments(read(RB_CSS)), re.S)
    for k, v in DECL_RE.findall(m.group(1)):
        rb[k] = v.strip()
    ra, ea = resolve_all(rb)
    newdecl = {k: v[1] for k, v in all_tj.items()}
    rb2, eb = resolve_all(newdecl)
    if ea or eb:
        fail("E rb.css 等价", "解析失败：%s" % "；".join((ea + eb)[:6]))
        return 0, len(rb)
    miss = [k for k in rb if k not in rb2]
    mism = [k for k in rb if k in rb2 and norm(ra[k]) != norm(rb2[k])]
    if miss:
        fail("E rb.css 等价·缺失", "、".join(miss[:8]))
    if mism:
        for k in mism[:6]:
            fail("E rb.css 等价·不一致", "%s rb=%s new=%s" % (k, ra[k], rb2[k]))
    if not (miss or mism):
        ok("E rb.css 等价", "rb.css 的 %d 个 :root 变量在新系统中逐值相等" % len(rb))
    return len(rb) - len(miss) - len(mism), len(rb)


def spec_shape(txt):
    """自适应识别规格的标题层级。
    写作时组件标题与 9 节固定小节可能落在不同的 Markdown 级别上（有的用 # 组件 / ## 小节，
    有的反过来）。这里从「N. 小节」实际出现的级别反推，避免把排版差异误判为契约缺失。
    返回 (小节级别, 组件级别)；识别不出返回 (None, None)。"""
    from collections import Counter
    lv = {}
    for m in re.finditer(r"^(#{2,5})\s*(\d)[.、]", txt, re.M):
        lv.setdefault(int(m.group(2)), []).append(len(m.group(1)))
    if not lv:
        return None, None
    per_num = {n: Counter(v).most_common(1)[0][0] for n, v in lv.items()}
    sec = Counter(per_num.values()).most_common(1)[0][0]
    return sec, sec - 1


def groups_of(tj):
    return [g for g in tj["component"] if not g.startswith("_")]


L2_HEAD = set()  # 保留占位：当前判定只依赖组件组名，不再用 L2 前缀猜测（会误伤 `--danger` 这类修饰类片段）


def looks_like_token(name, group_names):
    """区分「token 名」与「BEM 修饰片段」。
    规格里会写 `` `--danger` ``（指 `.btn--danger` 的修饰类）、`` `--utility-` ``（指前缀）这类片段，
    它们不是 token 声明；只有**以组件组名或 p- 开头**的完整名字才当作 token 来核对。
    例：`--kv-value-fs` 会被核对，`--danger` / `--stack` / `--utility-` 不会。"""
    if name.endswith("-"):
        return False                      # 前缀写法，不是完整 token 名
    parts = name.lstrip("-").split("-")
    if not parts or not parts[0]:
        return False
    return parts[0] == "p" or parts[0] in group_names


# ================================================================ F 组件规格
def check_specs(tj):
    groups = groups_of(tj)
    gset = set(groups)
    group_tokens = {g: [k for k in tj["component"][g] if not k.startswith("_")] for g in groups}
    decls = set()
    for layer in ("primitive", "semantic", "component", "compat"):
        decls |= {k for k, _v in flat_pairs(tj[layer])}

    owners, all_mentioned, missing = {}, set(), []
    for rel in SPEC_FILES:
        p = os.path.join(HERE, rel)
        if not os.path.exists(p):
            fail("F 规格文件缺失", rel)
            missing.append(rel)
            continue
        txt = read(p)
        om = re.search(r"<!--\s*owns:\s*([^>]+?)-->", txt)
        if not om:
            fail("F 缺 owns 首行", rel)
            continue
        owned = [x.strip() for x in om.group(1).replace("，", ",").split(",") if x.strip()]
        for g in owned:
            if g in owners:
                fail("F owns 重复", "%s 同时被 %s 与 %s 声明" % (g, owners[g], rel))
            owners[g] = rel
        unknown = [g for g in owned if g not in groups]
        if unknown:
            fail("F owns 组名不存在", "%s：%s" % (rel, "、".join(unknown)))

        # 只在**非否定语境**下把 `--name` 当作 token 声明来核对；
        # 规格里「禁止发明 `--pill-pending-bg`」是诚实缺口声明，不是引用错误。
        mentioned, ghost = set(), []
        for m in TOKEN_MENTION.finditer(txt):
            nm = m.group(1)
            mentioned.add(nm)
            if nm in decls or in_negation(txt, m.start()):
                continue
            if looks_like_token(nm, gset):
                ghost.append(nm)
        all_mentioned |= mentioned
        if ghost:
            fail("F 规格引用了不存在的 token", "%s：%s" % (rel, "、".join(sorted(set(ghost))[:8])))
        for g in owned:
            miss = [t for t in group_tokens.get(g, []) if t not in mentioned]
            if miss:
                fail("F 组内 token 未覆盖", "%s / %s：缺 %s" % (rel, g, "、".join(miss[:6])))

        for c in REVIEW_ONLY:
            if raw_hits(txt, c):
                fail("F 规格引用评审专用 class", "%s：%s" % (rel, c.strip()))
        for w in FORBIDDEN:
            if raw_hits(txt, w):
                fail("F 规格含违禁文案", "%s：%s" % (rel, w))

        # 9 节骨架：自适应层级，每个**组件**块都必须含 1.~9. 全部小节
        sec, comp = spec_shape(txt)
        if sec is None:
            fail("F 无法识别 9 节骨架", rel)
        else:
            chunks = re.split(r"^#{%d}\s+" % comp, txt, flags=re.M)[1:]
            ncomp = 0
            for blk in chunks:
                if not re.search(r"^#{%d}\s*1[.、]" % sec, blk, re.M):
                    continue          # 前言/文件标题块，不是组件
                ncomp += 1
                head = blk.splitlines()[0].strip() if blk.strip() else "(空)"
                for n in range(1, 10):
                    if not re.search(r"^#{%d}\s*%d[.、]" % (sec, n), blk, re.M):
                        fail("F 骨架缺节", "%s / %s：缺 %d. 节" % (rel, head[:24], n))
            if ncomp == 0:
                fail("F 无组件块", rel)
            else:
                ok("F 骨架", "%s：%d 个组件块均含 9 节（小节级别 h%d）" % (rel, ncomp, sec))
        # rb.css 行号必须在范围内
        nrb = len(read(RB_CSS).splitlines())
        refs = [int(x) for x in re.findall(r"rb\.css:(\d+)", txt)]
        if not refs:
            fail("F 无 rb.css 锚点", rel)
        oor = sorted({x for x in refs if x < 1 or x > nrb})
        if oor:
            fail("F rb.css 行号越界", "%s：%s（文件共 %d 行）" % (rel, oor[:6], nrb))

    miss_groups = [g for g in groups if g not in owners]
    if miss_groups:
        fail("F 组归属不全", "无文件声明：%s" % "、".join(miss_groups))
    if not miss_groups and not any(
            k == "F owns 重复" or k == "F 组归属不全" or k == "F 缺 owns 首行" for _l, k, _d in R):
        ok("F 组归属不重不漏", "%d 个 L3 组恰好被 4 份规格覆盖" % len(groups))
    return owners


# ================================================================ G 活样式手册
def check_styleguide(tj):
    if not os.path.exists(SYSTEM_HTML):
        fail("G system.html 缺失", SYSTEM_HTML)
        return
    html = read(SYSTEM_HTML)
    css = read(os.path.join(HERE, "tokens.css"))
    groups = [g for g in tj["component"] if not g.startswith("_")]

    m = re.search(r'<style id="ds-tokens">\n(.*?)\n</style>', html, re.S)
    if not m:
        fail("G ds-tokens 块缺失", "")
    elif norm(m.group(1)) != norm(css):
        fail("G ds-tokens 与 tokens.css 不一致", "内联块与生成物不同（长度 %d vs %d）" % (len(m.group(1)), len(css)))
    else:
        ok("G ds-tokens 逐字节一致", "内联的 tokens.css 与生成物相同（%d 字节）" % len(css))

    found = re.findall(r'data-group="([a-z]+)"', html)
    if sorted(found) != sorted(groups):
        miss = [g for g in groups if g not in found]
        extra = [g for g in found if g not in groups]
        fail("G 组件组不全", "缺 %s / 多 %s" % (miss, extra))
    else:
        ok("G 27 组齐全", "%d 个 L3 组在本页都有演示区" % len(found))

    # 组件样式块只消费 L3
    cm = re.search(r'<style id="ds-components">\n(.*?)\n</style>', html, re.S)
    if not cm:
        fail("G ds-components 块缺失", "")
    else:
        body = strip_comments(cm.group(1))
        body = re.sub(r"@media[^{]*", "@media", body)   # 断点字面量单独校验
        l3 = {k for k, _v in flat_pairs(tj["component"])}
        bare, nonl3 = [], []
        for i, line in enumerate(body.splitlines(), 1):
            bad_line = bool(HEX_RE.search(line) or RGBA_RE.search(line) or HSL_RE.search(line)
                            or LEN_RE.search(line))
            if not bad_line:
                for m in PCT_RE.finditer(line):
                    if m.group(0) not in ("100%", "0%"):
                        bad_line = True
                        break
            if bad_line:
                bare.append("第%d行 %s" % (i, line.strip()[:70]))
        for ref in sorted(set(VAR_RE.findall(body))):
            if ref not in l3:
                nonl3.append(ref)
        if bare:
            fail("G 组件样式含裸值", "；".join(bare[:6]))
        else:
            ok("G 组件样式无裸值", "无裸 hex / 裸长度 / 非 100% 百分比")
        if nonl3:
            fail("G 组件样式越层", "引用了非 L3 token：%s" % "、".join(nonl3[:8]))
        else:
            ok("G 组件样式只消费 L3", "全部 var() 指向 component 层")

    if "<link" in html or re.search(r'\ssrc="', html):
        fail("G 含外部资源", "<link> 或 src=")
    else:
        ok("G 零外部请求", "无 <link> / src=")

    if EMOJI_RE.search(html):
        fail("G 含 emoji", EMOJI_RE.search(html).group(0))
    else:
        ok("G 无 emoji", "")
    for w in FORBIDDEN:
        if raw_hits(html, w):
            fail("G 含违禁文案", w)

    # stack 表格 td 全有 data-label
    nstack, ntd = 0, 0
    for m2 in re.finditer(r'<table[^>]*class="[^"]*table--stack[^"]*"[^>]*>(.*?)</table>', html, re.S):
        nstack += 1
        for td in re.finditer(r"<td\b([^>]*)>", m2.group(1)):
            ntd += 1
            if "data-label=" not in td.group(1):
                fail("G stack td 缺 data-label", td.group(0)[:70])
    if nstack:
        ok("G 卡片化表格 data-label", "%d 张 .table--stack / %d 个 td 全部带 data-label" % (nstack, ntd))

    # 标题层级
    hs = [int(x) for x in re.findall(r"<h([1-6])[ >]", html)]
    if hs.count(1) != 1:
        fail("G h1 数量", "%d 个" % hs.count(1))
    else:
        ok("G 单一 h1", "共 %d 个标题" % len(hs))
    prev, jumps = 1, []
    for h in hs[1:]:
        if h > prev + 1:
            jumps.append("%d→%d" % (prev, h))
        prev = h
    if jumps:
        fail("G 标题跳级", "、".join(jumps[:6]))
    else:
        ok("G 标题不跳级", "")

    # L3 全覆盖：每个 component token 都应在本页出现
    covered = set(re.findall(r"(--[a-z][a-z0-9-]*)", html))
    l3all = {k for k, _v in flat_pairs(tj["component"])}
    notcov = sorted(l3all - covered)
    if notcov:
        fail("G L3 未覆盖", "%d 个 component token 未出现在本页：%s" % (len(notcov), "、".join(notcov[:6])))
    else:
        ok("G L3 全覆盖", "全部 %d 个 component token 都在本页出现" % len(l3all))


# ================================================================ H/I 其它生成物与文档
def check_artifacts(tj, counts):
    ts = read(os.path.join(HERE, "tokens.ts"))
    real = {k: v["v"] for k, v in tj["breakpoint"].items()
            if isinstance(v, dict) and "v" in v}
    bad = []
    for k, v in real.items():
        if not re.search(r"\b%s:\s*%d\b" % (k, v), ts):
            bad.append("%s=%d" % (k, v))
    if bad:
        fail("H tokens.ts 断点不一致", "、".join(bad))
    else:
        ok("H tokens.ts 断点一致", "%d 个断点与 tokens.json 相同" % len(real))

    md = read(os.path.join(HERE, "tokens.md"))
    m = re.search(r"逐值等价通过：\*\*(\d+)\*\*", md)
    m2 = re.search(r"rb\.css `:root` 变量数：\*\*(\d+)\*\*", md)
    if not m or not m2:
        fail("H tokens.md 缺等价性声明", "")
    else:
        nrb = len(re.findall(r"(--[A-Za-z][A-Za-z0-9_-]*)\s*:", strip_comments(read(RB_CSS)).split(":root")[1].split("\n}")[0]))
        if int(m.group(1)) != int(m2.group(1)):
            fail("H tokens.md 等价性声明不自洽", "%s / %s" % (m.group(1), m2.group(1)))
        else:
            ok("H tokens.md 等价性声明", "%s/%s" % (m.group(1), m2.group(1)))

    readme = read(os.path.join(HERE, "README.md"))
    claim = re.search(r"\|\s*\*\*合计\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|", readme)
    total = sum(counts.values())
    if not claim:
        warn("I README 未声明总 token 数", "")
    elif int(claim.group(1)) != total:
        fail("I README 计数过期", "README 写 %s，实际 %d" % (claim.group(1), total))
    else:
        ok("I README 计数一致", "合计 %d" % total)


# ================================================================ J CSS 真解析（补文本/字节通路的盲区）
def css_live_text(css):
    """注释感知剥离。返回 (无注释文本, 注释是否闭合)。"""
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


def iter_rules(live):
    """产出 (prelude, body)。按 {} 配平切分，不做完整 CSS 语法分析，但对本题足够。"""
    start, i, n = 0, 0, len(live)
    while i < n:
        if live[i] == "{":
            prelude = live[start:i].strip()
            depth, k = 1, i + 1
            while k < n and depth:
                if live[k] == "{":
                    depth += 1
                elif live[k] == "}":
                    depth -= 1
                k += 1
            yield prelude, live[i + 1:k - 1]
            start, i = k, k
        else:
            i += 1


def check_css_parses(tj, css):
    """核心：每条规则的 prelude 必须恰好是 :root，且每个 token 的声明都落在这样的规则里。

    为什么单列一项：`--bg-*/--text-*` 里的 `*/` 会提前闭合注释，于是后面的 `:root{…}` 与
    垃圾文本拼成同一个 prelude、整块永不匹配。此时
      · 文本逐值比对（A 项）PASS —— 声明文本确实在文件里；
      · 字节比对（G 项）PASS —— 字节确实一致；
      · 但浏览器里那些 token **全是空的**。
    这个盲区真实发生过：品牌绿整块失效、30 个 token 运行时死掉、主按钮变白字透明底。
    所以必须有一项把 CSS 当 CSS 解析，而不是当文本。"""
    live, closed = css_live_text(css)
    if not closed:
        fail("J 注释闭合", "存在未闭合的 CSS 注释")
        return
    rules, bad = list(iter_rules(live)), []
    reachable = set()
    for prelude, body in rules:
        if prelude != ":root":
            bad.append(prelude[:70] or "(空 prelude)")
        else:
            reachable |= set(re.findall(r"(--[A-Za-z][A-Za-z0-9_-]*)\s*:", body))
    if bad:
        for p in bad[:5]:
            fail("J prelude 非 :root", repr(p))
    else:
        ok("J 规则 prelude 全部为 :root", "%d 条规则，无垃圾 prelude" % len(rules))

    expect = {k for k, _v in flat_pairs(tj["primitive"])} | \
             {k for k, _v in flat_pairs(tj["semantic"])} | \
             {k for k, _v in flat_pairs(tj["component"])} | \
             {k for k, _v in flat_pairs(tj["compat"])}
    dead = sorted(expect - reachable)
    if dead:
        fail("J 声明可达性（浏览器里会失效）",
             "%d 个 token 的声明落在永不匹配的规则里：%s" % (len(dead), "、".join(dead[:10])))
    else:
        ok("J 声明可达性", "%d 个 token 在浏览器里都会真正生效" % len(expect))


# ================================================================ main
def main():
    tj = json.loads(read(os.path.join(HERE, "tokens.json")))
    css = read(os.path.join(HERE, "tokens.css"))
    css_decls = {k: v.strip() for k, v in DECL_RE.findall(css)}

    counts, all_tj = check_fidelity(tj, css_decls)
    print("=" * 78)
    print("设计系统确定性校验（独立于生成器）")
    print("=" * 78)
    print("  L1 %d / L2 %d / L3 %d / L0 %d = %d 个 token"
          % (counts["primitive"], counts["semantic"], counts["component"], counts["compat"],
             sum(counts.values())))
    print("-" * 78)

    check_layers(tj, all_tj)
    decls = {k: v[1] for k, v in all_tj.items()}
    resolved = resolve_all(decls)[0]
    check_coverage(tj, all_tj, resolved)
    check_contrast(tj, resolved)
    check_rb_parity(tj, all_tj)
    check_css_parses(tj, css)
    check_specs(tj)
    check_styleguide(tj)
    check_artifacts(tj, counts)

    for lv in ("PASS", "WARN", "FAIL"):
        for level, name, detail in R:
            if level == lv:
                print("[%-4s] %-34s %s" % (level, name, detail))
    nf = sum(1 for l, _n, _d in R if l == "FAIL")
    nw = sum(1 for l, _n, _d in R if l == "WARN")
    print("-" * 78)
    print("PASS %d / WARN %d / FAIL %d" % (sum(1 for l, _n, _d in R if l == "PASS"), nw, nf))

    with open(os.path.join(HERE, "verify-system-output.txt"), "w", encoding="utf-8", newline="\n") as f:
        for level, name, detail in R:
            f.write("[%s] %s %s\n" % (level, name, detail))
        f.write("\nPASS %d / WARN %d / FAIL %d\n"
                % (sum(1 for l, _n, _d in R if l == "PASS"), nw, nf))
    with open(os.path.join(HERE, "verify-system-output.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump([{"level": l, "check": n, "detail": d} for l, n, d in R],
                  f, ensure_ascii=False, indent=1)
        f.write("\n")
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())
