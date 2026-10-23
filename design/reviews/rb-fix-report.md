# 阶段 A 修复报告 · rb.css / tokens 六项必修 + 原型 #1/#3/#6 + W1-b

- 执行者：fix-rb（task-1）
- 日期：2026-10-23
- 工作区：`Smart Campus Course Assistant`
- 依据：`design/system/README.md`（收口裁决与 W1–W3）、`docs/校园课程智能助手_前端详细设计_v0.1.md` §8.4 / §8.7（裁决 J2）、
  `design/system/components/01–04*.md`、`design/responsive/verification.md`、`design/system/verification.md`、`design/directions/shared/content-spec.md`
- 状态：**6 项 + Lead 追加的 W1-b 全部落地；5 个校验脚本 0 FAIL；真实浏览器实测已做（含反向注入）**

> 本报告只描述我这一轮做了什么、怎么自测的。**独立验证（task-2）由另一位验证者用第二套实现复核**，
> 本节的自测结论不能替代他的验收。

---

## 0. 结论速览

| 项 | 落点（阶段 A 后） | 自测结论 | 真实浏览器实测 |
| --- | --- | --- | --- |
| W1 偏移 | `rb.css:84`、`rb.css:94` + `tokens.json` L3 `root` | ✅ | ✅ 9 个宽度遮挡 ≤0.5px |
| W1-b 顶栏增高 | `rb.css:137`、`rb.css:141` | ✅ | ✅ `appbarH` 恒 56.67px（含 768/772/774） |
| W2 折叠控件焦点 | `rb.css:425`（补偿环）、`rb.css:263`（≥480 隐藏） | ⚠️ 规则与 ≥480 分支已实测；**<480 补偿环未能在浏览器里触发**（见 §5 U1） | ⚠️ 部分 |
| W3a 键值列 | `rb.css:382` | ✅ | ✅ 反向注入复现 +583px，修复态 0 |
| W3b 长串断行 | `rb.css:189`、`:241`、`:281` | ✅ | ✅ 反向注入复现 +406/+435/+435px，修复态 0 |
| #1 处理中改 info | `parts/admin.html:232`、`:302` | ✅ | ✅ DOM 实测 2 处 `pill--info`，`:519` 仍 `pill--warn` |
| #3 危险胶囊补图标 | `parts/records.html:273` | ✅ | ✅ 6 项 svg 属性 + 实例 14×14，胶囊高度未变 |
| #6 冻结显隐按钮文案 | `content-spec.md` §2 S01 | ✅（只冻结契约，未实现控件） | — （纯文本契约，不可渲染） |
| §8.4 附带：skip-link 焦点 | `shell.html:62` → `b-responsive.html` | ✅ | ✅ 点击后 `activeElement.id === "main"` |

五脚本自验：`generate.py` FAIL 0 / WARN 0；`build-system.py` 0 FAIL；`verify-system.py` **PASS 31 / WARN 0 / FAIL 0**；
`responsive/build.py` 构建期契约检查全部通过；`reviews/verify.py` exit 0。

### 0.1 Lead 收尾裁定（2026-10-23，已确认）

| 我的提交 | Lead 裁定 |
| --- | --- |
| 越界改 `components/01-shell-navigation.md` | **接受**；已请独立验证者专审 `owns` 与 9 节骨架是否被破坏 |
| `--root-scroll-offset` 用 `--shell-appbar-h` + `--p-space-1` | **接受**（层级归属已另行核实，见 §4 J-2：`--shell-appbar-h` 是 L2，不是变相 L3 互引） |
| W2 额外做 ≥480 的 `display:none` | **接受，有据**（docs §8.7 裁决 J2 原文） |
| 行号冻结策略（1–415 逐行一致） | **接受并感谢**；写入 §1.4，后续阶段（含 Vue 骨架）沿用 |
| `white-space` 不 token 化 / `tokens.json` 1.1.0 | **接受** |
| #6 两态文案与 `aria-pressed` 语义由我拟定 | **确认为判断项**，由 Lead 写入交付说明（见 §4.0 J-8） |
| §8.4 旧判据需同步 | **Lead 决定不改 `docs/`**（它是已独立验证过的冻结件，本轮无写入租约）：判据以实测遮挡量（≤0.5px）为准，旧判据的放行缺陷写进**验证报告与最终交付说明**，作为「文档待同步」留给下一轮 → 已落成本报告 §6 的可执行待办 |

---

## 1. 改动清单（含前后哈希）

### 1.1 手写文件

| 文件 | 字节 | MD5（改后） | 改前 MD5 | 改了什么 |
| --- | --- | --- | --- | --- |
| `design/responsive/rb.css` | 23,086 | `0749FA7A47BC155F52A12406123DF6CC` | `94DF48EDFFC1DC33858A545C3574048F`（21,734B，冻结版） | 9 行就地改 + 文件末尾追加「阶段 A 修复」小节（+12 行）；**1–415 行号与冻结版逐行一致** |
| `design/responsive/parts/admin.html` | 35,966 | `D35DAFE4E61D9F42ADFB94BCCB6C5761` | `F09525E06851037A90633BC175EFB444` | 2 处 class：`pill--warn` → `pill--info` |
| `design/responsive/parts/records.html` | 17,059 | `9ED257DC24A550AD0E9CE952298E9E71` | `65A93462A08C40E0AC64CE8069853CF4` | 273 行危险胶囊补 1 个内联 SVG（+2 行，`<span>` 仍在 273 行） |
| `design/responsive/shell.html` | 6,064 | `E8B7294B9B4A8424ACA94C17068F2F60` | `0E2C4FFFBFF4C9999D98BD7747E5568A`（6,050B） | `#main` 补 `tabindex="-1"` |
| `design/directions/shared/content-spec.md` | 16,637 | `5191543D3F42EEC73BE1478421810D3B` | `8AB8C22609F2B01F1BE0D5F56195FAB8` | S01 新增密码显隐按钮的冻结契约（7 条） |
| `design/system/tokens.json` | 54,283 | `4EEA1276DC4A069C29DBE56A55B152D6` | `924A6C27FB7D7BFB5DF3571D33DF34BF` | L3 `root` 组新增 `--root-scroll-offset`；`meta.version` 1.0.0→1.1.0；`changeLog` 增 v1.1.0；`meta.upstream`/`compat._note` 计数同步 |
| `design/system/generate.py` | 32,691 | `89E8A0CF7516C2D7F801FC532A9B2D2B` | `5FB4F922C8845D8FFED33930FA3EA2B2` | 文件头注释与 `gen_md` 的「74 个变量 / 24 个同名」表述改为 75 / 25（L2 24 + L3 1） |
| `design/system/README.md` | 32,682 | `1FBDD745D6CC1CFE6C5739446BBC7C65` | `FC0AE63D44D09E37E166B2741EEAF953` | 计数（518→519、336→337、74/74→75/75、122 class 不变）、两个哈希、「阶段 A 修复清单」、W1-b 段、判据口径、行号策略 |
| `design/system/components/01-shell-navigation.md` | 75,868 | `0C33CD918F3C90758CD873BB7229C3D1` | （未记录；改动见 J-1：+1 行 + 5 处就地替换） | **被迫的最小改动**：见 §4 J-1 |

### 1.2 生成物（只由脚本产生，未手改）

| 文件 | 字节 | MD5 | 由谁产生 |
| --- | --- | --- | --- |
| `design/system/tokens.css` | 30,504 | `26EEE4F0348C6E4DA9DB1840D17F2163` | `generate.py` |
| `design/system/tokens.md` | 49,473 | `2A01AA51DABACC783D9219ECC3AC12AF` | `generate.py` |
| `design/system/tokens.ts` | 16,947 | `03607588E7EC217959DA681F51B363E7` | `generate.py` |
| `design/system/tokens.flat.json` | 15,674 | `7D3050EEB85CD7122B40D8099F62531D` | `generate.py` |
| `design/system/system.html` | 190,014 | `BC064300B7EDAB9EDB9AE4F93AE0F17E` | `build-system.py` |
| `design/responsive/b-responsive.html` | 126,723 | `5B73454136F261AC13E9A0203C0C6D73`（冻结版 `1DD81EAB2A90797AB01F4CEB0A645A17`） | `build.py` |
| `design/reviews/verify-output.txt` / `.json` | — | — | `reviews/verify.py`（内容由未改动的三方向稿决定，重跑确定） |

**未手改任何生成物**；`tokens.css/md/ts/flat.json` 的每一次变化都能由 `tokens.json` 的变化解释，
`system.html` / `b-responsive.html` 同理（`system.html` 由 `build-system.py` 重生成，
其 L3 组 token 清单是自动生成的，所以新增 token 会自动出现在「本组 L3 token」表里 —— 这也是 `verify-system.py` G 项「L3 全覆盖」能过的原因）。

### 1.3 最终 rb.css 差异（逐行）

| 行 | 改前 | 改后 |
| --- | --- | --- |
| 84 | `  --h-appbar:56px;` | `  --h-appbar:56px; --root-scroll-offset:calc(var(--h-appbar) + var(--sp-1));  /* W1：锚点/跳转链接避让 sticky 顶栏 */` |
| 94 | `html{-webkit-text-size-adjust:100%}` | `html{-webkit-text-size-adjust:100%;scroll-padding-top:var(--root-scroll-offset)}` |
| 137 | `.appbar__user{…gap:var(--sp-2)}` | `.appbar__user{…gap:var(--sp-2);white-space:nowrap}` |
| 141 | `…font-weight:500;` | `…font-weight:500;white-space:nowrap` |
| 189 | `.card__body{padding:var(--sp-3)}` | `.card__body{padding:var(--sp-3);overflow-wrap:anywhere}` |
| 241 | `…max-width:100%}` | `…max-width:100%;overflow-wrap:anywhere}` |
| 263 | `@media (min-width:480px){ .steps__summary{display:none} .steps__body{display:flex} }` | `…{ .steps__summary{display:none} .steps__toggle{display:none} .steps__body{display:flex} }` |
| 281 | `.cite__name{font-weight:600}` | `.cite__name{font-weight:600;overflow-wrap:anywhere}` |
| 382 | `.kv__row{…grid-template-columns:8em 1fr;…}` | `.kv__row{…grid-template-columns:8em minmax(0,1fr);…}` |
| 416–427 | （文件到 415 行结束） | 新增「阶段 A（实现期）修复」小节：W2 的 `.steps__toggle:focus-visible ~ .steps__summary` 补偿环 + 说明注释；`.table` 单元格**未**改用 `anywhere` |

---

### 1.4 行号冻结策略（本轮采用，**后续阶段沿用**）

改动 `rb.css` 时用三条规则，使 **`rb.css:1–415` 的行号与冻结版逐行一致**：

1. **改属性 → 就地追加**：不新起一行（如 `white-space:nowrap`、`overflow-wrap:anywhere`、`minmax(0,1fr)`）。
2. **新增 `:root` 声明 → 与语义最近的既有声明同行**：`--root-scroll-offset` 与 `--h-appbar` 同行
   （本文件 33–35、61–64、71、74 行早有「一行多声明」的写法，风格不突兀）。
3. **新增规则块 → 追加到文件末尾**，并用小节标题写明目的（本例：`/* 阶段 A（实现期）修复 */`）。

代价与收益：代价是「84 行两个声明」「W2 规则不在过程区小节」这类排版上的不够紧凑；
收益是 4 份组件规格、`b-responsive-spec.md`、`design/system/verification.md` 与 `docs/`
里 **200 余处 `rb.css:<行号>` 锚点全部继续有效**，不必做一次跨 6 个文件的重新编号。

执行这条策略时必须自检：**改完用 `Select-String` 复核关键锚点行号未变**
（本轮复核过 84 / 94 / 110 / 137 / 141 / 189 / 241 / 263 / 281 / 382 / 425），
并注意**不要引入新的 `.`+字母序列**（`build.py` 用 `\.([A-Za-z][\w-]*)` 数 class 数，
我第一版注释里的 `b-responsive-spec.md` 就被误数成第 123 个 class，已改掉；复核值 122）。

---

## 2. 逐项：改了什么 / 依据 / 怎么自测 / 原始输出

### W1 缺 `scroll-padding-top`（+ 阶段 A 追加的 W1-b）

**改了什么**

1. `tokens.json` → L3 `component.root` 新增：
   `"--root-scroll-offset": { "v": "calc(var(--shell-appbar-h) + var(--p-space-1))", "d": "…62px…" }`
2. `rb.css:84` 用 L0 名声明同值：`--root-scroll-offset:calc(var(--h-appbar) + var(--sp-1))`（66 行 `--sp-1:6px`、84 行 `--h-appbar:56px`）。
3. `rb.css:94`：`html{…;scroll-padding-top:var(--root-scroll-offset)}`。
4. **W1-b（Lead 追加）**：`rb.css:137` / `rb.css:141` 加 `white-space:nowrap`。

**依据**：README「W1（高）」+ `design/system/verification.md` §6.1 的实测（`#v-S11` 遮挡 56.4px、skip-link 到 `#main` 遮挡 56.7px）；
W1-b 来自 Lead 的 768–774px 复查（我独立用第二条通路复现，见下）。

**自测（真实浏览器，Edge/Chromium，iframe 夹具给出真实视口）**

`html` 的计算值：`{"scrollPaddingTop":"62px"}`；
9 个宽度下 `#main` 与 `#v-S11` 的实测遮挡（判据 `occlusion = .appbar.bottom − 目标.top ≤ 0.5`）：

| 视口 | appbarH | docOvf | navH | linkH | #main top/bottom/occl | #v-S11 top/bottom/occl | skip-link 点击后 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 320 | 56.67 | −15 | 0 | — | 56.67 / 56.67 / **0** | 61.70 / 56.67 / **−5.03** | `activeElement=main`, hash `#main`, occl 0 |
| 390 | 56.67 | −15 | 0 | — | 56.67 / 56.67 / **0** | 61.67 / 56.67 / **−5.00** | 同上 |
| 480 | 56.67 | −15 | 0 | — | 56.67 / 56.67 / **0** | 62.04 / 56.67 / **−5.37** | 同上 |
| **768** | **56.67** | −15 | 44 | 44,44,44,44 | 56.67 / 56.67 / **0** | 61.81 / 56.67 / **−5.15** | 同上 |
| **772** | **56.67** | −15 | 44 | 44×4 | 0 | 62.06 / 56.67 / **−5.40** | 同上 |
| **774** | **56.67** | −15 | 44 | 44×4 | 0 | 62.06 / 56.67 / **−5.40** | 同上 |
| 775 | 56.67 | −15 | 44 | 44×4 | 0 | 62.06 / 56.67 / **−5.40** | 同上 |
| 1024 | 56.67 | −15 | 44 | 44×4 | 0 | 62.23 / 56.67 / **−5.56** | 同上 |
| 1366 | 56.67 | −15 | 44 | 44×4 | 0 | 62.23 / 56.67 / **−5.56** | 同上 |

`docOvf = −15` 即「无横向溢出」（`scrollWidth − innerWidth` = −滚动条槽）；`#main` 的 occl = 0 是因为它紧邻文档顶部、
滚动被 clamp，目标上沿正好落在顶栏下沿（不重叠）。

**W1-b 的根因实测（改前，768px）**：

```
inner 内容宽 717px，三个 flex 子项固有宽 = 品牌 134 + 导航左偏移 12 + 导航 482 + 2×18 间距 + 用户胶囊 59 = 723px  → 缺口 6px
默认 flex-shrink 把 6px 摊到  导航 −5.65px、用户胶囊 −0.69px
→ .navlink 内容盒 90.58px < 文字 68 + 图标 18 + gap 6 = 92px → 4 个 navlink 全部折成 2 行（h 44 → 59.5）
→ .appbar 56.667px → 72.167px
```

改后同宽度：`navH 44`、`linkH 44,44,44,44`、`inner.scrollWidth − clientWidth = 0`、`appbarH 56.67`。
`white-space` 与 `overflow-wrap` / `display` 同属「结构属性、刻意不 token 化」一类，**未新增断点、未改任何 token 值**。

### W2 `.steps__toggle` 聚焦无可见指示

**改了什么**：① `rb.css:425` 追加
`.steps__toggle:focus-visible ~ .steps__summary{outline:3px solid var(--focus);outline-offset:2px;border-radius:4px}`
（值与 `rb.css:110` 的全局焦点环逐字一致）；② `rb.css:263` 的 ≥480 媒体查询里加 `.steps__toggle{display:none}`
（全文档 §8.7 裁决 J2 的「加强」：该宽度下 `.steps__body` 已强制常显，复选框只剩隐形焦点陷阱这一个作用）。

**自测（真实浏览器）**

```json
"ruleInCSSOM": [".steps__toggle:focus-visible ~ .steps__summary"],
"toggleGe480": {"display":"none","focusableByScript":false},
"fx320": {"lt480":true,"toggleDisplay":"block","summaryDisplay":"flex","siblings":"3/3"}
```

✅ ≥480 分支：`display:none` 且脚本 `focus()` 不再能聚焦（已移出 Tab 序）；
✅ 规则在 CSSOM 里存在，且 3/3 个实例的 `.steps__toggle ~ .steps__summary` 兄弟关系成立（选择器能命中）。
❌ **<480 的补偿环没能在浏览器里被触发**：用「先聚焦文本控件、再脚本聚焦 checkbox」想复现 Chromium 的
`:focus-visible` 继承启发式，实测 `toggleFocusVisible: false` → 摘要行 `outline-style` 仍为 `none`。
这与上一轮验证者遇到的是同一个限制（程序化 `focus()` 不触发 `:focus-visible`），真实键盘 Tab 才能判定。见 §5 U1。

### W3 长串溢出（两条根因）

**改了什么**：W3a `rb.css:382` → `minmax(0,1fr)`；W3b `rb.css:189/:241/:281` 加 `overflow-wrap:anywhere`。
`.table .cell-name` **保持** `break-word` + `min-width`（实测 `overflow-wrap: break-word`、320px 卡片化下 `min-width:0px`）。

**自测（真实浏览器，320px iframe 夹具，注入 60 字符无空格串）**：修复态 vs 反向注入（把三处改回修复前写法）

```json
"W3_fixed":    {"base":-15, ".kv__v":-15, ".cite__name":-15, ".card__body":-15, ".bubble":-15},
"W3_reverted": {"base":-15, ".kv__v":583, ".cite__name":406, ".card__body":435, ".bubble":435},
"tableCells":  ["break-word / min-width:0px", "break-word / min-width:0px"]
```

即：**差异确实由这三处修复造成**（还原后 4 个容器分别溢出 +583 / +406 / +435 / +435px，与验证者给出的
「只改一处时仍溢出」的形状一致；绝对值不同是因为我的探针是往容器**追加**一个 60 字符文本节点，
而非替换容器内容）。修复态四个容器都回到基线 −15（无溢出）。

### #1 琥珀语义（`parts/admin.html`）

**改了什么**：`:232`（批次卡「处理中」）与 `:302`（文件行「处理中」）的 `pill--warn` → `pill--info`；
**未动** icons/svg，**未动** `:519`（「需确认后继续」仍 `pill--warn`）。

**自测**：

```json
"pills_处理中": ["pill pill--info", "pill pill--info"],
"pills_需确认后继续": ["pill pill--warn"],
"warnPills": ["检索成功·没有足够依据","未保存","待确认·写入结果未知","需确认后继续"]
```

剩余的 4 处 warn 正好是 README 裁决 1 认可的 4 类语义（依据不足 / 未保存 / 待确认 / 需确认后继续），
说明这次只改了该改的两处。

### #3 危险胶囊补图标（`parts/records.html:273`）

**改了什么**：按 `components/02-actions-status.md` 的 Pill 规格与 Lead 的指示补 24×24 内联 SVG
（`circle-x`：`<circle cx="12" cy="12" r="10"/>` + `m15 9-6 6` + `m9 9 6 6`），实例走行内 `style="width:14px;height:14px"`。

**自测**：

```json
"dangerPill_不可恢复": {"fill":"none","stroke":"currentColor","sw":"1.75","aria":"true",
                        "focusable":"false","style":"width:14px;height:14px",
                        "rendered":"14x14","pillH":24.79}
```

同页其它 5 个 `.pill--danger` 的 `pillH` 也都是 **24.79px** → 补图标后胶囊高度未变（无布局影响）；
`computedStroke = rgb(123, 14, 44)` = `#7B0E2C`（`--state-danger`），随文字色 `currentColor` 生效。

### #6 冻结密码显隐按钮的文案与 `aria-pressed`

**改了什么**：只在 `content-spec.md` §2 S01 增补冻结契约，**未实现控件**（`parts/login.html` 本轮未动）：
两态逐字文案（遮蔽＝**显示密码**／明文＝**隐藏密码**）、`aria-pressed` 语义（`false`＝遮蔽、`true`＝明文可见，
且必须与两态文案一致）、`type="button"`、`aria-controls`、只改 `type` 不清空/不移动焦点、
触控 ≥44px、图标槽 token 本轮不新增。

**依据**：README 收口表 #6 + 全文档 §8.4 #6 的裁决「**先冻结再实现**：在 `content-spec.md` 补一组两态可访问名 + `aria-pressed` 语义」。

**自测**：契约是纯文本，不可渲染；已核对它与 `01-shell-navigation.md:907` 已有的按钮要求不冲突
（那条早已要求 `aria-pressed` 表达是否明文、`aria-controls`、两态不同名、≥44px、不清空内容/不改焦点），
并同步更新了 01 里「文案未冻结」的两处过期表述（U9 行、§7 文案表行、§9 禁止项行）。

### §8.4 附带：skip-link 焦点落点

**改了什么**：`shell.html:62` `<main id="main">` → `<main id="main" tabindex="-1">`，重跑 `build.py`。

**自测**：真实点击 skip-link 后 `afterSkipLink: {"activeElement":"main","hash":"#main","occlusion":0}`
（改前实测 `activeElement === BODY`）。

---

## 3. 五个校验脚本的原始输出（最终一次）

```
##### 1/5 python design\system\generate.py #####
  primitive   91 个 token
  semantic    41 个 token
  component  337 个 token
  compat      50 个 token
  合计       519
  L1 未被引用   0
  对比度配对  41，全部达标 是
  rb.css 等价 75/75
[PASS] L1 覆盖度                 全部 91 个 primitive 都有引用面
[PASS] 对比度（含 alpha 合成）        41 对全部达标
[PASS] rb.css 等价性             75/75 逐值等价
[PASS] 规则 prelude             58 条规则的 prelude 全部恰好是 :root
[PASS] 声明可达性                  519 个 token 的声明都落在 prelude=:root 的规则里
FAIL 0 / WARN 0
已写出：tokens.css  tokens.md  tokens.ts  tokens.flat.json
EXIT=0

##### 2/5 python design\system\build-system.py #####
  L3 组数        27
  演示块          27
  内联 tokens.css 26838 字节
  内联组件样式    25492 字节
  产物            190014 字节 / 2915 行
  对比度配对      41（全部达标：True）
组装通过：0 FAIL。产物已写出。
EXIT=0

##### 3/5 python design\system\verify-system.py #####
  L1 91 / L2 41 / L3 337 / L0 50 = 519 个 token
[PASS] A 生成保真        tokens.json ↔ tokens.css：519 个 token 逐值一致
[PASS] B L1 纯字面量或 L1 内部组合 / B L2 只指向 L1 / B L3 无裸色值/裸长度 / B L3 取色经 L2 /
       B L3 不互引 / B 引用完整性
[PASS] C L1 覆盖度 / C L3 规模（337）
[PASS] D 对比度（独立实现，含 alpha 合成）   41 对全部达标，最低 4.74:1
[PASS] E rb.css 等价       rb.css 的 75 个 :root 变量在新系统中逐值相等
[PASS] J 规则 prelude 全部为 :root（58 条）/ J 声明可达性（519 个）
[PASS] F 骨架 ×4 份 / F 组归属不重不漏（27 组）
[PASS] G ds-tokens 逐字节一致（26838 字节）/ G 27 组齐全 / G 组件样式无裸值 / G 组件样式只消费 L3 /
       G 零外部请求 / G 无 emoji / G 卡片化表格 data-label / G 单一 h1（63 个标题）/ G 标题不跳级 /
       G L3 全覆盖（337 个）
[PASS] H tokens.ts 断点一致（6 个）/ H tokens.md 等价性声明 75/75
[PASS] I README 计数一致      合计 519
PASS 31 / WARN 0 / FAIL 0
EXIT=0

##### 4/5 python design\responsive\build.py #####
  parts/login.html       视图 S01       v-S01  (5495 字节)
  parts/assistant.html   视图 S02–S06   v-S02,…,v-S06  (36932 字节)
  parts/records.html     视图 S07–S09   v-S07,v-S08,v-S09  (17059 字节)
  parts/admin.html       视图 S10–S12   v-S10,v-S11,v-S12  (35966 字节)
产物：design/responsive/b-responsive.html  124587 字节
内联 CSS 23086 字节；rb.css 定义 class 122 个
产物外部引用：无
产物 <img>/<link>/<script src>：0/0/0
产物视图 12 个：v-S01 … v-S12
构建期契约检查：
  全部通过（class 契约 / data-label / 无 style / 无 @media / 无裸 hex / 无 emoji）
EXIT=0

##### 5/5 python design\reviews\verify.py #####
（三个方向稿 [B] 15/15、[C] 逐字文案 15/15、[E] 对比度全 OK、[G] 无 emoji、[I] 裸 hex 0、[J] 标记结构一致）
已写入 design/reviews/verify-output.txt 与 .json
EXIT=0
```

> 说明：`build.py` 打印的字节数（124587）是**字符串的 UTF-8 字节**，磁盘文件是 126723 字节 ——
> 差额来自 Windows 的 `\n → \r\n` 换行转换（每行 +1 字节）。冻结版同样如此（打印 122900 / 磁盘 125021）。
> README 里登记的是**磁盘哈希**，用 `Get-FileHash` 复核过。

---

## 4. 判断项（无法从源码断定，只能做判断的地方）

### 4.0 判断项清单（交付说明需引用）

| # | 判断项 | 我的取值 | 依据 / 性质 |
| --- | --- | --- | --- |
| J-8 | **#6 密码显隐按钮的两态文案与 `aria-pressed` 语义** | 遮蔽＝**显示密码**（`aria-pressed="false"`）／明文＝**隐藏密码**（`aria-pressed="true"`）；`aria-pressed` = 「密码当前是否已切换为明文可见」，且必须与两态文案始终一致 | **源文件从未指定措辞**，只要求「带显示/隐藏切换」。这是本轮唯一的「产品文案由实现者拟定」项，Lead 已确认保留并写进交付说明 |
| J-9 | `tokens.json` 版本号与变更记录 | 1.0.0 → **1.1.0**，`changeLog` 增 v1.1.0 | 非任务要求；token 源新增了 token，`changeLog` 是它唯一的记录面 |
| J-6 | #3 图标的尺寸档 | 24×24 viewBox + 行内 **14×14**（`circle-x`，`r=10`，与 `assistant.html:375` 同形） | 规格 §3 说胶囊图标「统一 13×13，少数 14×14」；取 14×14 是照 Lead 指示与 `admin.html:233/237` 的写法 |
| J-7 | `white-space` 不 token 化 | 按结构属性处理 | 与 `.appbar__brand` 冻结版既有 `white-space:nowrap` 同类，且 README 的「刻意不 token 化」清单含 `overflow-wrap`/`display`/`flex 方向` |
| J-10 | W1-b 的前提 | 顶栏 4 个标签是冻结的 4 字标签；换更长标签时 768px 会先吃光右内边距再溢出 | 未加固（加固＝给标签 `max-width`+省略号，属设计决策） |

以下 J-1…J-10 逐条说明。

**J-1（被迫的越界改动，最重要）**：`verify-system.py` 的 F 项有一条 **FAIL 级检查「组内 token 未覆盖」**——
它要求 `tokens.json` 里每个 L3 组的每个 token，都必须在拥有该组的组件规格文件里以 `` `--name` `` 形式出现。
`root` 组归 `components/01-shell-navigation.md`，所以新增 `--root-scroll-offset` 后，**不改规格就必然 FAIL**
（我在基线跑过：改前 PASS 31/FAIL 0；只加 token 不改规格时 F 会报「F 组内 token 未覆盖」）。
因此我对 `components/01-shell-navigation.md` 做了**最小、契约骨架不变**的改动：
§5 token 消费表 +1 行、U3 行改成「已在阶段 A 修复」、§6 无障碍那条改成已补偿，
并把 §7/§9 里「密码切换按钮文案未冻结」的两处过期表述指向新冻结的 content-spec S01。
**这超出了任务书给的写入范围**，但目的正是让 `verify-system.py` 回到 FAIL 0；请 Lead 确认是否接受这个方式
（替代方案是把 token 放 L0 compat 层 —— 那会让它逃过等价性检查的语义，且与 README 的 W1 建议冲突，我不推荐）。

**J-2 W1 的 L3 取值不用 `var(--appbar-min-h)`（对任务书字面值的必要偏离）**：任务书与 README 建议
`calc(var(--appbar-min-h) + var(--sp-1))`，但 `verify-system.py` B 项「L3 不互引」会把 L3 引用 L3 判 **FAIL**
（代码：`l3_names = {k for k, _v in flat_pairs(tj["component"])}`，命中即 `l3_cross.append(...)`）。
我改用 `calc(var(--shell-appbar-h) + var(--p-space-1))`。

**层级归属已核实（Lead 要求确认：`--shell-appbar-h` 不是 L3，所以这不是「变相 L3 互引」）**：

```
tokens.json:  semantic -> shell => {"v": "var(--p-size-appbar)"}     ← L2（值只指向 L1，符合 B 项「L2 只指向 L1」）
L3 名单核对:  --shell-appbar-h in L3 names? False
              --appbar-min-h   in L3 names? True                    ← 若写成它才会触发 B 项 FAIL
              --p-space-1      in L3 names? False                   ← L1 primitive
tokens.md:    `--shell-appbar-h` 出现在 §4「L2 semantic」第 319 行，不在 §5「L3 component」
```

即 `--root-scroll-offset`（L3）= **L2 `--shell-appbar-h` + L1 `--p-space-1`**，
是先例 `--navlink-min-h:var(--size-control-min)`（L3→L2）、`--appbar-pad-y:var(--p-space-1)`（L3→L1）的同类组合，
**不构成 L3→L3，也没有「绕过检查」**——检查看的是名字集合，而它确实不在 L3 集合里。
`--appbar-min-h` 自身是 L3（值也是 `var(--shell-appbar-h)`），两者解析值逐字相同（`calc(56px + 6px)`）。
**rb.css 侧的声明用 L0 名** `calc(var(--h-appbar) + var(--sp-1))` ——rb.css 里没有 `--appbar-min-h`，
若照抄会让 `generate.py` 报「rb.css 解析」WARN（任务要求 WARN 0）。

**J-3 行号冻结策略**：为了让 4 份组件规格 / `b-responsive-spec.md` / `docs/` 里 200 余处 `rb.css:<行号>` 锚点
不整体失准，我用「就地追加 + 同行声明 + 追加到文件末尾」的方式做到 **`rb.css:1–415` 行号与冻结版逐行一致**。
代价：`:root` 里第 84 行有两个声明（本文件已有同类写法，如 33–35、61–64、71、74 行）、
W2 的规则放在文件末尾的「阶段 A 修复」小节而不是「过程区」小节。若 Lead 认为可读性优先，
一次重编号就能换回「一小节一行」的排版——但那要同时改 4 份规格与 docs，不在本轮范围。

**J-4 W2 额外做了 ≥480 的 `display:none`（超出任务书表格）**：任务书只写「加 `:focus-visible` 补偿环」，
但 `docs/…前端详细设计` §8.7 与 `docs/frontend-detail/parts/90-open-items.md` 的裁决 **J2** 已明确
「**采纳其建议并加强**：`<480` 给摘要行加补偿环；**`≥480` 直接把 `.steps__toggle` 隐藏**」。
我按这条更完整的裁决实现（零新增行：写进已有的 480 媒体查询），并实测生效。若 Lead 认为该裁决不适用于原型层，请告知，我回退这一处。

**J-5 W2 用 `:focus-visible` 而不是 `:focus`**：与 `rb.css:110` 的全局焦点环语义一致（鼠标点击不画环，
键盘才画），组件规格也明确「无 `:focus`，仅 `:focus-visible`」。若实现期改用 `:focus`，会让点击折叠控件也出现焦点环。

**J-6 #3 的图标几何与尺寸**：规格 §3 说胶囊图标「冻结原型中统一 13×13，少数 14×14（如 admin.html:233/237）」，
§9 建议补 `circle-x`。我按 Lead 的明确指示取「24×24 viewBox + 行内 14×14」，几何用 Lucide `circle-x`
（`r=10`，与 `assistant.html:375` 那个 `.pill--danger` 同形）。若要求与规格「统一 13×13」严格一致，
改 `style` 即可，但我判断 14×14 与 admin.html 的同类写法一致、且不影响 `pillH`（实测 24.79px 未变）。

**J-7 `white-space:nowrap` 属于结构属性、不 token 化**：README 的「刻意不 token 化」清单列了
`position/display/align-items/flex 方向/overflow-wrap/border-style/env()/gap 合并`，`white-space` 与它们同类
（`.appbar__brand` 早在冻结版里就有 `white-space:nowrap`）。若 Lead 认为该清单是封闭枚举、必须补 token，
需要新增 `--navlink-white-space` 之类的关键字 token 并同步规格——我判断不值得，故未做。

**J-8 `#6` 的两态用词是我拟的**：源文件只要求「带显示/隐藏切换」，没有指定措辞。我选
「显示密码」/「隐藏密码」（动作 + 对象，脱离上下文可懂、可与 `aria-pressed` 自洽），并明确禁止只给图标。
`aria-pressed` 的语义我定义为「密码是否已切换为明文可见」，并要求与两态文案始终一致。

**J-9 `tokens.json` 版本号 1.0.0 → 1.1.0 并补 `changeLog` v1.1.0**：非任务书要求。理由：token 源新增了一个 token，
而 `changeLog` 是它唯一的变更记录面（`tokens.md` 的 §11 与 `tokens.css` 无关）；全文没有脚本或文档断言 1.0.0。

**J-10 W1-b 的作用域**：修法是「让文案永不折行」，前提是顶栏那 4 个标签就是冻结的 4 字标签。
若实现期换更长的标签（如「学习计划管理」），768px 下会先吃光容器右内边距、然后才出现横向溢出。
这是我**没有**加固的地方（加固需要给标签设 `max-width` + 省略号，属设计决策），已登记。

---

## 5. 未验证 / 未做的部分（明确列出）

**U1 W2 的 `<480` 补偿环没有在浏览器里被真正触发。** 程序化 `.focus()` 不触发 `:focus-visible`
（实测 `toggleMatchesFocusVisible: false`），所以「聚焦后摘要行是否真的画出 3px 环」这一步**未取得实测证据**。
已证的是：规则存在于 CSSOM、选择器文本正确、3/3 实例兄弟关系成立、≥480 分支真实生效。
需要**真实键盘 Tab**（CDP `Input.dispatchKeyEvent`，本会话的 proxy 未暴露按键通道）或人工走查才能定论。
同行评审提醒：`design/system/verification.md` §6.1 的同一项在上一轮也停在同样的 UNKNOWN。

**U2 六宽度全量重跑未做。** 我在真实浏览器里量了 9 个宽度的 `appbarH` / 页面级横向溢出 / 锚点遮挡，
但**没有**做原验证口径的全量重测（六宽度截图、`.table--stack` 卡片化逐项、无障碍计数、人工看图）。
冻结期的「六宽度溢出为 0」结论建立在旧哈希上，按 README 的说法必须由独立验证重跑。

**U3 屏幕阅读器实读未做**（NVDA/JAWS/VoiceOver）：`aria-pressed` 的播报、`#main` 获得焦点后的朗读起点，
都只核了 DOM 属性与 `activeElement`，没有真听。`#6` 冻结的是**契约**，控件未实现，故不存在可测行为。

**U4 跨浏览器未做**：只测了 Windows 上的 Microsoft Edge（Chromium）。
`overflow-wrap:anywhere`、`minmax(0,1fr)`、`white-space:nowrap` 的 flex 最小尺寸交互、
`:focus-visible` 在 Firefox/Safari 的历史差异，都没有验证。

**U5 顶栏修复在其它滚动条宽度下未测**：我的实测环境滚动条槽 15.33px（缺口 6px）。
若某平台槽宽 ≥21px（缺口 ≥12px），用户胶囊会吃光 18px 右内边距并开始出现横向溢出——
这个边界我只做了算术推断（`18px 内边距 − 缺口`），没有实测。建议独立验证者用 `Emulation.setDeviceMetricsOverride` 或 overlay-scrollbar 环境复核。

**U6 `white-space:nowrap` 对 320–480px 无影响这一点**：320/390/480 的 `appbarH` 实测仍是 56.67、
`navH = 0`（`.appbar__nav{display:none}`），可认为无影响；但**底栏 `.tabbar` 的标签**（4 项，含 2 字标签）
我没有顺带核查是否也需要 nowrap（不在本轮范围）。

**U7 `docs/` 与本目录外的关联更新一律未做**（见 §6）。

---

## 6. 「文档待同步」待办清单（可直接执行）

**背景**：本轮只改代码与设计系统，**没有**写入 `docs/` 与 `design/` 下若干登记件的租约。
以下是 `grep` 反查得到的**全部**与阶段 A 冲突/过期的位置，按「可直接执行的待办」给出。
每条都写清 `文件:行号 → 应改成什么`。**行号是 2026-10-23 本轮结束时的行号。**

> 通用口径：凡「已落地」的表述，建议一律写成
> `**阶段 A 已落地**（`design/reviews/rb-fix-report.md` §1；自验通过，独立验证见 `design/reviews/rb-verify-report.md`）`。

### 6.1 `design/` 内（4 处文件）

| # | 文件:行号 | 现在写的 | 应改成 |
| --- | --- | --- | --- |
| D1 | `design/README.md:19` | 「L3 component 四层 **518** 个 token」 | **519** |
| D2 | `design/README.md:151` | 「三层 token **518** 个、4 份组件 API 规格、…」 | **519 个** |
| D3 | `design/responsive/verification.md:306` | 表格行 `rb.css … 94DF48EDFFC1DC33858A545C3574048F … ✅ 已变（M1）` | 哈希改 **`0749FA7A47BC155F52A12406123DF6CC`**（23,086 B），备注改「阶段 A 已变」 |
| D4 | `design/responsive/verification.md:308` | `b-responsive.html … 1DD81EAB2A90797AB01F4CEB0A645A17 …` | 哈希改 **`5B73454136F261AC13E9A0203C0C6D73`**（126,723 B） |
| D5 | `design/responsive/verification.md` 全文 | W1（sticky 遮挡）、W2（`.steps__toggle` 焦点）、W3（长串溢出）三条 **FAIL/缺陷确认** 结论 | 重跑六宽度后改写为「已修 + 复验结论」；该文件是**冻结期报告**，建议加一节「阶段 A 复验」而不是直接抹掉旧结论 |
| D6 | `design/system/verification.md:72,73,114,551` | 「`:root` **74** 个共同 token / rb.css **74** 个变量」 | **75**（冻结期数字可保留但需注明「阶段 A 后 75」） |
| D7 | `design/system/verification.md:424,547,556,581,615` | 「**518**」「515/518」「518/518 token」「30/518」等 M1 轮数字 | 历史数字，建议加注「M1 轮为 518；阶段 A 后 519」 |
| D8 | `design/system/verification.md:408,412,413,415,438,522,589,590` | 引用 `01-shell-navigation.md:883 / 486 / 318 / 331 / 936` | 全部 **+1**：`884 / 487 / 319 / 332 / 937`（因 01 规格 §5 新增了 1 行） |
| D9 | `design/system/components/02-actions-status.md:468–469` | 引文：「`admin.html:232`（`pill--warn` → 「处理中」，批次）、`admin.html:302`（`pill--warn` → 「处理中」，文件）」 | 改为 **`pill--info`**，并注明「阶段 A 已改（`pill--info`），此处为冻结期记录」 |
| D10 | `design/system/components/02-actions-status.md:480` | 「冻结原型有 4 处无图标胶囊 … **`records.html:273`**（`pill--danger`「不可恢复」）… 登记为待补（建议补 `circle-x`）」 | 从「待补」清单移除 `records.html:273`，改为「**阶段 A 已补 `circle-x`**（24×24 + 行内 14×14）」；其余 3 处中性标签不变 |
| D11 | `design/system/components/02-actions-status.md:965` | §9 登记表第 3 行「4 处胶囊缺图标（硬要求违例 1 处）… `records.html:273` 登记为待补图标」 | 同上：改为「273 已补图标（阶段 A），剩 3 处中性标签允许无图标」 |

> D9–D11 我**没有**改：它们不触发任何 FAIL 级检查（`verify-system.py` F 项只查 `owns`/9 节/token 覆盖/违例文案），
> 且组件规格不在我的写入范围。若 Lead 认为该规格应保持「与实现同步」，这三处需要一次小的写入授权。

### 6.2 `docs/frontend-detail/parts/*.md`（**这是可编辑源**，改完必须重跑组装）

`docs/校园课程智能助手_前端详细设计_v0.1.md` 是**生成物**（`build.py` 的 `OUT`），
**不要手改**；改动一律落在 `docs/frontend-detail/parts/*.md`，然后：

```powershell
$env:PYTHONIOENCODING="utf-8"; python docs\frontend-detail\build.py   # 期望 0 FAIL
```

| # | 分册:行号（→ 主文档行号） | 现在写的 | 应改成 |
| --- | --- | --- | --- |
| P1 | `50-design-system-and-a11y.md:482`（→ 主文档 L3435） | 判据：「六宽度下 skip-link 与页内锚点目标 `top ≥ 62−0.5`」；值写成 `calc(var(--appbar-min-h) + var(--sp-1))` | 判据换成**实测遮挡量**：`occlusion = .appbar.getBoundingClientRect().bottom − 目标.top ≤ 0.5px`，并注明「**必须含 768 / 772 / 774** 三个宽度」（旧判据在该区间放行 10px 遮挡）；值写成实际落地的 `--root-scroll-offset = calc(var(--shell-appbar-h) + var(--p-space-1))`（解析值 `calc(56px + 6px)` = 62px） |
| P2 | `50-…:134`（→ L1741） | W1 缺陷行：实测 `top=0.3px`、顶栏底 `56.7px` → 遮挡 56.4/56.7px；修法 `calc(var(--appbar-min-h) + var(--sp-1))`；判据 `#main.top >= 62 - 0.5` 且 `activeElement === #main` | 保留为**冻结期实测**，追加「**阶段 A 已修**：`rb.css:84` 声明 + `rb.css:94` 消费；实测遮挡 `#v-S11` −5.0…−5.56px、`#main` 0px（9 个宽度）；`#main` 已补 `tabindex="-1"`，`activeElement === #main` 已成立」；判据同 P1 替换 |
| P3 | `50-…:135`（→ L1742） | W2 缺陷行 + 「给可见摘要行加补偿环（3 行）」 | 追加「**阶段 A 已修**：`rb.css:425` 补偿环 + `rb.css:263` ≥480 `display:none`（裁决 J2）」 |
| P4 | `50-…:136`（→ L1743） | W3 表格：`.kv__v +523 / .cite__name +359 / .card__body +375 / .bubble +375` | 追加「**阶段 A 已修**：`rb.css:382` `minmax(0,1fr)` + `rb.css:189/241/281` `overflow-wrap:anywhere`；反向注入复验：还原后 +583/+406/+435/+435，修复态 0」 |
| P5 | `50-…:131,132`（→ L1738,1739） | #1/#3 缺陷行 | 追加「**阶段 A 已落地**」（#1 两处 `pill--info`；#3 补 `circle-x`） |
| P6 | `50-…:133`（→ L1740） | #6 缺陷行：`content-spec.md:54` 要求切换但文案从未冻结；`LoginView` 该槽位不得实现 | 追加「**阶段 A 已冻结契约**：`content-spec.md` §2 S01 现有两态逐字文案（显示密码 / 隐藏密码）+ `aria-pressed` 语义 + `aria-controls` + `type="button"`；**控件本轮仍未实现**」；其验收列的「被 §15 追踪表引用」需在 §15 追踪表补一行（本次未做） |
| P7 | `50-…:140–142`（→ L1747–1749） | 「1. 改 rb.css …；2. 在 tokens.json 补 `--root-scroll-offset`…；产物：518 → 518+n」 | 标为**已完成**；数字改 **519**，并写明新增的是 L3 `root` 组 `--root-scroll-offset` |
| P8 | `50-…:4`、`:14`、`:153`（→ L1611、L1621、L1760） | 「**518** 个 token」「L3 … 27 组、**336** 个」「tokens.css … **518** 个 token」 | **519** / **337** / **519** |
| P9 | `50-…:154`（→ L1761） | `global.css` 行含「`scroll-padding-top`」 | 保持；可补一句「实际值来自 `--root-scroll-offset`（`<style id="ds-tokens">` 里已有该变量）」 |
| P10 | `50-…:203–204`（→ L1810–1811） | 待裁决 1/2：token 名与归属组；值是否等于 `calc(--appbar-min-h + --sp-1)`（62px）还是含 `env(safe-area-inset-top)` | 第 1 条改为**已裁决**（`root` 组、名 `--root-scroll-offset`，与 J1 一致）；第 2 条：62px 已落地，`env(safe-area-inset-top)` **仍未决**（保留为 T6 真机复测项） |
| P11 | `50-…:427`（→ L3380） | 「`scroll-padding-top` = 62px」 | 补「且顶栏高度在全部宽度下恒 56.67px（阶段 A W1-b 修掉 768–774px 的 72.167px）」 |
| P12 | `50-…:464,467`（→ L3416+、L3419+） | `global.css` 的 W1/W2 片段（`scroll-padding-top: var(--root-scroll-offset)`、`.steps__toggle:focus-visible ~ .steps__summary {…}`） | **与实现一致**，无需改；建议注明「rb.css 里的等价实现：`:84`/`:94`/`:425`（`--focus` vs `--focus-outline-color` 是同一色的 L2/L3 两种写法）」 |
| P13 | `40-routing-and-screens.md:53`、`:111`、`:906`（→ L1483、L1541、L2546） | 「**依赖 W1** 的 `scroll-padding-top`」「→ 依赖 W1」「**依赖 W1**（否则被 56.7px 顶栏遮挡）」 | 改为「**W1 已落地**（阶段 A）：顶栏恒 56.67px，锚点遮挡 ≤0.5px」 |
| P14 | `40-…:150`、`:157`（→ L1580、L1587） | 修法串 `calc(var(--appbar-min-h) + var(--sp-1))`；「被顶栏遮 56.4–56.7px」 | 修法串改 `var(--root-scroll-offset)`（= `calc(var(--shell-appbar-h) + var(--p-space-1))`）；「56.4–56.7px」标注为**冻结期实测**，补 768–774px 的 72.167px 事实 |
| P15 | `40-…:158,159,160,161,162`（→ L1588–1592） | §15.3 前置批次 C 类：#1/#3/W2/W3/#6 待办 | 全部标为**已完成**（#6 为「契约已冻结、控件仍未实现」）；#1 注明两处 `pill--info` 已完成 |
| P16 | `40-…:812`（→ L2200 附近） | 「「处理中」用 `pill--info`，**不得用 `pill--warn`**」 | 已是目标状态，无需改；可注明「阶段 A 已对齐」 |
| P17 | `40-…:987`（→ L2432） | T2：S01 密码切换**文案未冻结**（阻塞 S01） | 改为**已解除阻塞**：`content-spec.md` §2 S01 已冻结两态文案与 `aria-pressed`（判断项，见本报告 §4.0 J-8） |
| P18 | `10-baseline-and-modules.md:13`（→ L42） | 「**518** 个 token 的四层设计系统」 | **519** |
| P19 | `90-open-items.md:9`（→ L4280 附近） | T2 同上 | 同 P17 |
| P20 | `90-open-items.md:23`（→ L4267） | J1 裁决：名 `--root-scroll-offset`、`root` 组 | 标为**已落地**（`tokens.json` L3 `root` 组；`rb.css:84` 用 L0 名同值声明） |
| P21 | `90-open-items.md:24,25`（→ L4268,4269） | J2（W2 全宽度）、J3（#1 与 rb.css 同批） | 标为**已落地**（`rb.css:263` + `:425`；`admin.html:232/302`） |
| P22 | `90-open-items.md:13`（→ L4257） | T6：`scroll-padding-top` 是否叠 `env(safe-area-inset-top)` | **保持未决**（真机复测项，与本轮无关；但可补「62px 已在 9 个宽度实测通过」） |
| P23 | `90-open-items.md:34`（→ L4278） | J12：#3 降级为一致性缺陷、实现期补图标 | 标为**已落地**（`records.html:273`） |
| P24 | `90-open-items.md:48,49,50`（→ L4292,4293,4294） | §16.3 前置批次三条待办 | 标为**已完成**；第 3 条的脚本串 `calc(var(--appbar-min-h) + var(--p-space-1))` 改为实际值 `--root-scroll-offset` |
| P25 | `60-forms-and-observability.md:1120`（→ L4102） | C6 用例行「`scroll-padding-top`｜锚点/skip-link 不被顶栏遮挡」 | 无需改（用例仍有效）；建议补判据「occlusion ≤0.5px」 |

### 6.3 `docs/frontend-detail` 的脚本与其它文件

| # | 文件:行号 | 现在写的 | 应改成 |
| --- | --- | --- | --- |
| S1 | `docs/frontend-detail/build.py:408` | 组装模板里的前言：「（**518** 个 token 的四层设计系统 + 27 个组件族规格）」 | **519**（这是主文档 L7 那句的来源，改分册改不到它） |
| S2 | `docs/frontend-detail/build.py:45` | `PROPOSED_TOKENS = {"--root-scroll-offset", "--appbar-scroll-offset"}` | `--root-scroll-offset` **已真实存在**于 `tokens.css`，可从「处方 token」名单移除（保留 `--appbar-scroll-offset` 作为未采纳的备选名）。不移除也不会 FAIL，属清理项 |
| S3 | `docs/frontend-detail/verification.md:390` | 「在 `tokens.css` 的 **518** 个 token 中存在｜28」 | **519**（该表是「28 个引用」的审计口径，需按 519 重算不影响结论） |
| S4 | `docs/frontend-detail/verification.md:413` | 引 L2559：「在 `tokens.json` **补** W1 的 `--root-scroll-offset`；产物：**518 → 518+n**」 | 「**已补**（阶段 A）；产物 518 → **519**」 |
| S5 | `docs/frontend-detail/verification.md:687` | 「token 引用全部可解析（**518**）」 | **519** |
| S6 | `docs/frontend-detail/verification.md` 全文 | 对 §8.4 判据与「约定 token 幽灵引用」的验证口径 | 追加一段「阶段 A 复验」：`--root-scroll-offset` 已从「处方 token」变为真实 token（幽灵引用审计口径随之变化） |
| S7 | `docs/frontend-detail/CONTRACT.md` | token 源为唯一真源（无计数） | 无需改 |

### 6.4 执行后的机械复核（建议作为该项待办完成判据）

```powershell
$env:PYTHONIOENCODING="utf-8"
# 1) 组装 0 FAIL
python docs\frontend-detail\build.py
# 2) 旧计数是否清干净（应只剩带「历史/冻结期/阶段 A 前」字样的行）
Select-String -Path design\*.md,design\system\*.md,docs\*.md,docs\**\*.md -Pattern '\b518\b|\b510\b|\b74/74\b|74 个 :root'
# 3) 01 规格行号引用是否全部 +1
Select-String -Path design\system\*.md,docs\**\*.md -Pattern '01-shell-navigation\.md:(\d+)'
# 4) 冻结哈希是否只剩「冻结版」语境
Select-String -Path design\**\*.md,docs\**\*.md -Pattern '94DF48ED|1DD81EAB'
# 5) 设计系统自校验仍全绿
python design\system\verify-system.py      # 期望 PASS 31 / WARN 0 / FAIL 0
```

> 注意：#2 的输出里 `design/system/README.md:164,198,283`、`design/system/verification.md` 的 M1 轮数字、
> `components/04-forms-data.md` 的 `336`（那是 **rb.css 行号**，不是 token 数）都是**合法保留项**，不要误改。

---

## 7. 复现命令（我要留的原始入口）

```powershell
$env:PYTHONIOENCODING="utf-8"
python design\system\generate.py       # FAIL 0 / WARN 0，rb.css 等价 75/75，对比度 41 对达标
python design\system\build-system.py   # 0 FAIL
python design\system\verify-system.py  # PASS 31 / WARN 0 / FAIL 0
python design\responsive\build.py      # 构建期契约检查全部通过
python design\reviews\verify.py        # exit 0
```

真实浏览器实测（本会话用过、并已关闭自建 tab）：
`node "C:\Users\Rotary\.agents\skills\web-access\scripts\check-deps.mjs" --browser edge`
→ `curl -X POST --data-raw <b-responsive.html 的 127.0.0.1:8799 URL> http://localhost:3456/new`
→ `curl -X POST "http://localhost:3456/eval?target=<id>" --data-binary @<探针.js>`
→ `curl -X POST "http://localhost:3456/close?target=<id>"`。
视口宽度用**同源 iframe 夹具**（`<iframe style="width:320px…">` 加载同一 URL）获得——
iframe 的媒体查询按它自己的视口求值，等价于真实窄视口；探针只读取，不改任何文件。
