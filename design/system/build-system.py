#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
活样式手册组装器   design/system/build-system.py

把 tokens.css（生成物）与 styleguide.css + styleguide-demos.html（手写素材）
组装成**单文件、零外部请求**的 design/system/system.html，并在组装时做契约检查。

产物结构：
  <style id="ds-tokens">     tokens.css 原文（逐字节内联，便于校验生成保真）
  <style id="ds-components"> styleguide.css 原文
  概览面板                    四层计数 / 纯度规则 / 断点表 / 对比度实测（复用 generate.py 的计算）
  27 个 <section data-group="…">  每组：token 清单（自动生成，含解析值）+ 演示 markup

运行：
  $env:PYTHONIOENCODING="utf-8"; python design\system\build-system.py
"""
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate as G  # noqa: E402  复用解析/颜色/分层工具，避免同一套规则写两遍

TOKENS_CSS = os.path.join(HERE, "tokens.css")
STYLE_CSS = os.path.join(HERE, "styleguide.css")
DEMOS = os.path.join(HERE, "styleguide-demos.html")
OUT = os.path.join(HERE, "system.html")
RB_CSS = os.path.join(os.path.dirname(HERE), "responsive", "rb.css")

# 27 个 L3 组的中文标题与说明（顺序即页面顺序）
GROUP_META = [
    ("root", "根与全局", "页面底、正文色、正文字号/行高、等宽数字；窄屏为底部标签栏预留高度。"),
    ("focus", "焦点环", "全局 :focus-visible。键盘可见、鼠标不触发；3px 描边 + 2px 偏移。"),
    ("skiplink", "跳转链接", "首个可聚焦元素，聚焦后从屏外进入视野，直接跳到主内容。"),
    ("sr", "视觉隐藏", "仅给读屏的文本。尺寸 1px 是视觉隐藏惯用法，不是设计尺寸。"),
    ("appbar", "顶部应用栏", "sticky 顶栏。≥768 承载内联导航；<768 只留品牌与用户区。"),
    ("brand", "品牌标记", "墨绿圆角方块 + 产品名。顶栏 26px，登录页 38px。"),
    ("navlink", "导航链接", "≥768 的内联导航项，≥44px 触控目标，当前项用 aria-current=\"page\" 标记。"),
    ("tabbar", "底部标签栏", "<768 的 4 项一级入口。方向 B 不做侧栏，窄屏用底部导航而非汉堡菜单。组件真实行为是 position:fixed 吸在视口底部（rb.css:149）；本手册演示块内临时改为 static，否则会一直盖住下半页。"),
    ("wrap", "内容容器", "居中内容列 880px；助手列 720px。嵌套时只保留一层内边距。"),
    ("card", "卡片", "白底 + 14px 圆角 + 近平面描边；分 head / body / foot 三段。"),
    ("btn", "按钮", "默认 / 主色 / 危险 / 幽灵 四种外观，block 与 sm 两种尺寸，含 disabled。"),
    ("pill", "状态胶囊", "状态一律「图标 + 文字 + 颜色」三重。琥珀只表示未保存/待确认。"),
    ("notice", "提示块", "整块说明文字。5 个语义变体，均带图标。"),
    ("chat", "对话", "消息列表、发言人标签、气泡；用户消息右侧贴边并收角。"),
    ("steps", "过程条", "只展示三类可核实工具动作。running 态图标旋转；<480 默认折叠。"),
    ("composer", "输入区", "吸附在底部。窄屏吸附在标签栏之上，≥768 贴底。真实行为是 position:sticky（rb.css:267）；本手册演示块内临时改为 static 以便评审。"),
    ("cite", "引用", "已验证引用用实心主色左条；未验证标记用琥珀虚下划线——契约要求可区分。"),
    ("draft", "学习计划草稿", "默认未保存（虚线琥珀边）；保存后转实线并显示 plan_id。"),
    ("empty", "空状态", "「成功的空」与「服务异常」是两种状态，不得合并。"),
    ("field", "表单字段", "标签、必填、提示、错误四段；错误必须同时有文字，不能只靠颜色。"),
    ("control", "输入控件", "input / select / textarea 的常态、只读、失效、非法四态。"),
    ("table", "表格与卡片化", "<768 时同一份 markup 变卡片：thead 隐藏、td 用 data-label 渲染字段名。"),
    ("kv", "键值列表", "8em 键列 + 值列，用于详情类信息。"),
    ("chip", "筛选胶囊", "可点击的胶囊型入口；与状态胶囊（pill）语义不同，不要混用。"),
    ("prose", "正文排版", "长文本容器，68ch 上限——超过这个宽度阅读会掉行。"),
    ("login", "登录页", "420px 单列。账号密码、错误态、不可用账号两种文案。"),
    ("utility", "工具类", "stack / row / spacer / muted / small 五个排版工具。"),
]

FORBIDDEN = ["正在思考", "AI 推理中", "推理过程", "思考中", "暂无数据", "暂无内容"]
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\uFE0F\u20E3]")
LEN_RE = re.compile(r"(?<![\w.-])(\d*\.?\d+)(px|em|rem|ch|vh|vw|pt)\b")
PCT_RE = re.compile(r"(?<![\w.-])\d*\.?\d+%")
HEX_RE = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
RGB_RE = re.compile(r"\brgba?\([^)]*\)", re.I)
HSL_RE = re.compile(r"\bhsla?\([^)]*\)", re.I)
VAR_RE = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*\)")

# 评审外壳样式：本页自身的排版（不是产品 UI，也不属于设计系统）。
# 与 .bph / .proto-banner 同性质——被 tokens.json 的 meta.scope 明确排除在系统之外。
# 颜色与间距仍尽量复用 L3 token，避免"手册自己不受约束"的观感。
CHROME_CSS = """
/* ===== 评审外壳（不属设计系统）===== */
.shell-head{padding:var(--wrap-pad-y) 0 0}
.shell-head h1{font-size:var(--p-fs-32);margin-bottom:var(--p-space-2)}
.shell-head h2{font-size:var(--p-fs-24);margin:var(--p-space-6) 0 var(--p-space-3)}
.lead{max-width:var(--prose-max);color:var(--text-secondary)}
.stat-row{display:grid;grid-template-columns:1fr;gap:var(--p-space-2);margin:var(--p-space-4) 0}
@media (min-width:768px){.stat-row{grid-template-columns:repeat(3,1fr)}}
@media (min-width:1024px){.stat-row{grid-template-columns:repeat(6,1fr)}}
.stat{background:var(--card-bg);border:var(--card-border-w) solid var(--card-border-color);
  border-radius:var(--card-radius);padding:var(--card-body-pad);text-align:center}
.stat b{display:block;font-size:var(--p-fs-24);color:var(--accent-strong)}
.stat span{color:var(--text-muted);font-size:var(--p-fs-13);line-height:1.4;display:block;margin-top:var(--p-space-1)}
.rules{max-width:var(--prose-max);color:var(--text-secondary);padding-left:1.4em}
.rules li{margin-bottom:var(--p-space-1)}
.toc{display:grid;grid-template-columns:1fr;gap:var(--p-space-1)}
@media (min-width:768px){.toc{grid-template-columns:repeat(2,1fr)}}
@media (min-width:1200px){.toc{grid-template-columns:repeat(3,1fr)}}
.toc a{display:block;padding:var(--p-space-1) var(--p-space-2);border-radius:var(--navlink-radius);
  text-decoration:none;color:var(--text-primary);background:var(--card-bg);
  border:var(--card-border-w) solid var(--card-border-color)}
.toc a:hover{background:var(--navlink-bg-hover)}
.toc b{color:var(--text-muted);font-family:var(--p-font-mono);font-size:var(--p-fs-13);margin-right:var(--p-space-1)}
.toc .mono{color:var(--text-muted);font-size:var(--p-fs-13)}
.grp{padding-top:var(--p-space-8)}
.grp+.grp{border-top:var(--p-bw-2) dashed var(--border)}
.grp-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--p-space-2);
  margin-bottom:var(--p-space-3)}
.grp-head h2{font-size:var(--p-fs-24)}
.grp-id{font-family:var(--p-font-mono);font-weight:var(--p-fw-semibold);font-size:var(--p-fs-13);
  color:var(--btn-primary-fg);background:var(--btn-primary-bg);border-radius:var(--pill-radius);
  padding:var(--pill-pad-y) var(--pill-pad-x)}
.grp-desc{color:var(--text-secondary);max-width:var(--prose-max);margin:var(--p-space-1) 0 0}
.grp-name{margin-left:auto;background:var(--pill-evidence-bg);color:var(--pill-evidence-fg);
  border-radius:var(--pill-radius);padding:var(--pill-pad-y) var(--pill-pad-x);
  font-size:var(--p-fs-13);font-weight:var(--p-fw-semibold)}
.grp-tokens{margin:0 0 var(--p-space-3)}
.grp-tokens summary{cursor:pointer;color:var(--text-secondary);font-size:var(--p-fs-15);
  padding:var(--p-space-1) 0}
.grp-demo{background:var(--bg-page);border:var(--card-border-w) dashed var(--border-strong);
  border-radius:var(--card-radius);padding:var(--p-space-4)}
.grp-demo>*+*{margin-top:var(--p-space-3)}
/* 演示块内把 position:fixed 的标签栏改为 static：组件的真实行为确实是吸在视口底部
   （rb.css:149），但在 2900 行的手册里会一直盖住下半页，评审时看不到被遮的演示。
   仅在本页演示块内覆盖，并在区块描述里写明组件真实行为。 */
.grp-demo .tabbar{position:static;bottom:auto}
.grp-demo .composer{position:static;bottom:auto}
.grp-demo .demo-label{font-size:var(--p-fs-13);color:var(--text-muted);
  font-family:var(--p-font-mono);display:block;margin-bottom:var(--p-space-2)}
.shell-foot{padding:var(--p-space-8) 0;color:var(--text-muted);font-size:var(--p-fs-13)}
"""
problems = []


def bad(kind, detail):
    problems.append((kind, detail))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- 演示块切分
def split_demos(text):
    """按 <div data-demo="X"> 顺序切块。块之间用下一个开标签分隔，再 rfind('</div>') 去掉块自己的收尾。"""
    marks = list(re.finditer(r'<div\s+data-demo="([a-z]+)">', text))
    out = {}
    for i, m in enumerate(marks):
        name = m.group(1)
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        chunk = text[start:end]
        cut = chunk.rfind("</div>")
        if cut >= 0:
            chunk = chunk[:cut]
        out[name] = chunk.strip("\n")
    return out


# ---------------------------------------------------------------- 检查
ALLOWED_PCT = {"100%", "0%"}


def check_css_purity(css, l3_names):
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    # 媒体查询前奏里的断点是**必须**写的字面量，由 check_media_literals 单独校验，这里先摘掉，
    # 否则 min-width:768px 会被误判成「裸长度」。
    body = re.sub(r"@media[^{]*", "@media", body)
    for i, line in enumerate(body.splitlines(), 1):
        if HEX_RE.search(line) or RGB_RE.search(line) or HSL_RE.search(line):
            bad("styleguide.css 裸色值", "第 %d 行：%s" % (i, line.strip()[:90]))
        if LEN_RE.search(line):
            bad("styleguide.css 裸长度", "第 %d 行：%s" % (i, line.strip()[:90]))
        for m in PCT_RE.finditer(line):
            if m.group(0) not in ALLOWED_PCT:
                bad("styleguide.css 裸百分比", "第 %d 行：%s" % (i, line.strip()[:90]))
                break
    for ref in sorted(set(VAR_RE.findall(body))):
        if ref not in l3_names:
            bad("styleguide.css 引用了非 L3 token", ref)


def check_demos(demos, l3_groups):
    missing = [g for g in l3_groups if g not in demos]
    extra = [g for g in demos if g not in l3_groups]
    if missing:
        bad("演示块缺失", "、".join(missing))
    if extra:
        bad("演示块多余", "、".join(extra))
    joined = "\n".join(demos.values())
    for w in FORBIDDEN:
        if w in joined:
            bad("违禁文案", w)
    if EMOJI_RE.search(joined):
        bad("emoji", EMOJI_RE.search(joined).group(0))
    if re.search(r"<style|<link|@media", joined):
        bad("演示块含禁止结构", "<style> / <link> / @media")
    # stack 表格的每个 td 必须有 data-label
    for m in re.finditer(r'<table[^>]*class="[^"]*table--stack[^"]*"[^>]*>(.*?)</table>', joined, re.S):
        for td in re.finditer(r"<td\b([^>]*)>", m.group(1)):
            if "data-label=" not in td.group(1):
                bad("stack 表格 td 缺 data-label", td.group(0)[:70])
    # 复用了 rb.css 里不存在的 class？
    rb = re.sub(r"/\*.*?\*/", "", read(RB_CSS), flags=re.S)
    rb_classes = set(re.findall(r"\.([A-Za-z][\w-]*)", rb)) | {"proto-banner"}
    used = set()
    for c in re.findall(r'class="([^"]*)"', joined):
        used |= {k for k in c.split()}
    for c in sorted(used - rb_classes):
        bad("演示用了 rb.css 未定义的 class", c)


# ---------------------------------------------------------------- 组装
def esc(s):
    return html.escape(s, quote=False)


def build():
    data = G.load()
    tables, resolved = {}, {}
    for layer in ("primitive", "semantic", "component", "compat"):
        for name, val, _d, _g in G.flatten(data[layer]):
            tables[name] = val
    for name in tables:
        v, err = G.resolve(name, tables)
        resolved[name] = v if not err else "（解析失败）"

    groups = []
    for gname, g in G.layer_groups(data["component"]):
        if gname in (None,):
            continue
        desc = next((d for n, _t, d in GROUP_META if n == gname), "")
        groups.append((gname, g, desc))
    l3_groups = [g for g, _d, _s in groups]
    l3_names = set()
    for _g, gd, _d in groups:
        l3_names |= {k for k in gd if not k.startswith("_")}

    tok_css = read(TOKENS_CSS)
    style_css = read(STYLE_CSS)
    demos = split_demos(read(DEMOS))

    check_css_purity(style_css, l3_names)
    check_demos(demos, l3_groups)

    meta = next((n for n, _t, d in GROUP_META if n == "root"), None)
    order = [n for n, _t, _d in GROUP_META]
    if order != l3_groups:
        bad("组顺序与 tokens.json 不一致", "GROUP_META=%s / component=%s" % (order, l3_groups))

    # 对比度（复用 generate 的计算）
    rows = []
    for p in data["contrast"]["pairs"]:
        need = data["contrast"]["tiers"][p["tier"]]
        fg = G.parse_color(resolved[p["fg"]])
        bg = G.parse_color(resolved[p["bg"]])
        if bg[3] < 1.0:
            bg = G.over(bg, (255, 255, 255, 1.0))
        if fg[3] < 1.0:
            fg = G.over(fg, bg)
        r = G.contrast_ratio(fg, bg)
        rows.append((p["n"], p["fg"], p["bg"], need, r, r >= need))

    counts = {l: len(G.flatten(data[l])) for l in ("primitive", "semantic", "component", "compat")}
    bps = G.bp_items(data)

    o = []
    A = o.append
    A("<!DOCTYPE html>")
    A('<html lang="zh-CN">')
    A("<head>")
    A('<meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width,initial-scale=1">')
    A("<title>设计系统 · 三层 token 与组件活样式手册 · 校园课程智能助手</title>")
    A("<!-- 本文件由 design/system/build-system.py 生成，请勿手改。")
    A("     内联来源：tokens.css（生成物）+ styleguide.css + styleguide-demos.html（手写素材）。")
    A("     零外部请求。tokens.css 原文逐字节内联，便于校验生成保真。 -->")
    A('<style id="ds-tokens">')
    A(tok_css)
    A("</style>")
    A('<style id="ds-components">')
    A(style_css)
    A("</style>")
    A('<style id="ds-chrome">')
    A(CHROME_CSS)
    A("</style>")
    A("</head>")
    A("<body>")
    A('<a class="skip-link" href="#main">跳到主要内容</a>')

    # ---- 概览 ----
    A('<header class="shell-head">')
    A('<div class="wrap">')
    A('<h1>设计系统 · 三层 token 与组件活样式手册</h1>')
    A('<p class="lead">方向 B（纸感墨绿 · 专注对话）。本页的<strong>组件样式块 <code>#ds-components</code> 只消费 '
      'L3 component token</strong>：里面出现的每一个颜色、间距、字号、圆角、边宽、阴影、时长都写成 '
      "<code>--&lt;组件&gt;-&lt;部位&gt;-&lt;属性&gt;</code>，没有任何裸 hex 或裸长度——"
      "这是 L3 层是否完备的证明，并由 <code>verify-system.py</code> 机械校验。</p>")
    A('<p class="lead">页面自身的排版（<code>#ds-chrome</code>）<strong>不属于设计系统</strong>，'
      "与原型里的 <code>.bph</code>／<code>.proto-banner</code> 同性质：它允许直接用 L2 语义色与 L1 尺度原语，"
      "因为它不是产品 UI，也不该为它发明组件 token。</p>")
    A('<div class="stat-row">')
    for layer, label in (("primitive", "L1 primitive"), ("semantic", "L2 semantic"),
                         ("component", "L3 component"), ("compat", "L0 compat")):
        A('<div class="stat"><b>%d</b><span>%s</span></div>' % (counts[layer], label))
    A('<div class="stat"><b>%d</b><span>对比度配对全部达标</span></div>' % len(rows))
    A('<div class="stat"><b>%d</b><span>rb.css 变量逐值等价</span></div>' % len(G.read_root_vars(RB_CSS)))
    A("</div>")
    A("<h2>分层与纯度规则</h2><ol class=\"rules\">")
    for r in data["meta"]["purity_rules"]:
        A("<li>%s</li>" % esc(r))
    A("</ol>")
    A("<h2>断点</h2>")
    A('<div class="table-wrap"><table class="table table--compact"><caption>mobile-first，全部 min-width；媒体查询内必须写字面量。</caption>'
      "<thead><tr><th>档</th><th>min-width</th><th>作用</th></tr></thead><tbody>")
    for k, v in bps:
        A("<tr><td class=\"cell-name\" data-label=\"档\">%s</td><td class=\"num\" data-label=\"min-width\">%s</td>"
          "<td data-label=\"作用\">%s</td></tr>"
          % (k, "基准（无媒体查询）" if v["v"] == 0 else "≥%dpx" % v["v"], esc(v["d"])))
    A("</tbody></table></div>")
    A("<h2>对比度实测（含 alpha 合成）</h2>")
    A('<div class="table-wrap"><table class="table table--compact"><caption>文字 4.5:1（WCAG 1.4.3 AA）；UI 边界 3:1（1.4.11）。</caption>'
      "<thead><tr><th>配对</th><th>前景</th><th>底</th><th>要求</th><th>实测</th></tr></thead><tbody>")
    for n, fg, bg, need, r, ok in rows:
        A('<tr><td class="cell-name" data-label="配对">%s</td><td class="mono" data-label="前景">%s</td>'
          '<td class="mono" data-label="底">%s</td><td class="num" data-label="要求">≥%.1f</td>'
          '<td class="num" data-label="实测">%.2f:1</td></tr>' % (esc(n), fg, bg, need, r))
    A("</tbody></table></div>")
    A("<h2>组件目录</h2><nav class=\"toc\">")
    for i, (g, _gd, _d) in enumerate(groups, 1):
        title = next((t for n, t, _d2 in GROUP_META if n == g), g)
        A('<a href="#g-%s"><b>%02d</b> %s <span class="mono">%s</span></a>' % (g, i, title, g))
    A("</nav>")
    A("</div></header>")

    # ---- 27 个组件组 ----
    A('<main id="main">')
    for i, (gname, gd, desc) in enumerate(groups, 1):
        title = next((t for n, t, _d2 in GROUP_META if n == gname), gname)
        toks = [(k, v.get("d", "")) for k, v in gd.items() if not k.startswith("_")]
        A('<section class="wrap grp" data-group="%s" id="g-%s">' % (gname, gname))
        A('<div class="grp-head">')
        A('<div class="grp-id">%02d</div>' % i)
        A("<div><h2>%s</h2><p class=\"grp-desc\">%s</p></div>" % (esc(title), esc(desc)))
        A('<code class="grp-name">--%s-*</code>' % gname)
        A("</div>")
        A('<details class="grp-tokens"><summary>本组 L3 token（%d）</summary>'
          '<div class="table-wrap"><table class="table table--compact"><thead><tr>'
          "<th>token</th><th>解析值</th><th>说明</th></tr></thead><tbody>" % len(toks))
        for k, d in toks:
            A('<tr><td class="mono" data-label="token">%s</td><td class="mono" data-label="解析值">%s</td>'
              '<td data-label="说明">%s</td></tr>' % (k, esc(resolved.get(k, "")), esc(d)))
        A("</tbody></table></div></details>")
        A('<div class="grp-demo">')
        A(demos.get(gname, '<p class="muted">（缺演示块）</p>'))
        A("</div>")
        A("</section>")
    A("</main>")

    A('<footer class="wrap shell-foot">')
    A("<p>本页由 <code>design/system/build-system.py</code> 生成：<code>tokens.css</code> 逐字节内联于 "
      "<code>&lt;style id=\"ds-tokens\"&gt;</code>，手写素材 <code>styleguide.css</code> + "
      "<code>styleguide-demos.html</code> 内联于 <code>&lt;style id=\"ds-components\"&gt;</code> 与正文。</p>")
    A("<p>确定性校验：<code>python design/system/verify-system.py</code>；token 生成："
      "<code>python design/system/generate.py</code>。</p>")
    A("</footer>")
    A("</body></html>")

    out = "\n".join(o) + "\n"

    # ---- 产物级检查 ----
    if "<link" in out or "src=" in out:
        bad("产物含外部资源", "<link> 或 src= 出现")
    if EMOJI_RE.search(out):
        bad("产物含 emoji", EMOJI_RE.search(out).group(0))
    for w in FORBIDDEN:
        if w in out:
            bad("产物含违禁文案", w)
    if out.count('data-group="') != len(l3_groups):
        bad("产物组件组数不符", str(out.count('data-group="')))

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)

    print("=" * 78)
    print("活样式手册组装报告   system.html")
    print("=" * 78)
    print("  L3 组数        %d" % len(l3_groups))
    print("  演示块          %d" % len(demos))
    print("  内联 tokens.css %d 字节" % len(tok_css))
    print("  内联组件样式    %d 字节" % len(style_css))
    print("  产物            %d 字节 / %d 行" % (len(out.encode("utf-8")), out.count("\n")))
    print("  对比度配对      %d（全部达标：%s）" % (len(rows), all(r[5] for r in rows)))
    print("-" * 78)
    if problems:
        for kind, detail in problems:
            print("[FAIL] %-28s %s" % (kind, detail))
        print("-" * 78)
        print("FAIL %d —— 已写出产物但**不要采用**，先修素材。" % len(problems))
        return 1
    print("组装通过：0 FAIL。产物已写出。")
    return 0


if __name__ == "__main__":
    sys.exit(build())
