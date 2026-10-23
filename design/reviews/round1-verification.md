# Round 1 独立校验报告 · 三方向稿 + IA 草图

- 校验者：verifier（独立验证者，task-5 owner）
- 校验对象：`design/directions/direction-a.html`、`direction-b.html`、`direction-c.html`、`design/ia/sitemap.html`
- 校验依据：`design/directions/shared/content-spec.md`、`docs/backend/openapi_v0.1.json`、`docs/校园课程智能助手_SRS_v0.1.md` §6/§8
- 约束遵守：**未修改任何被验收文件**；本轮唯一写入 = 本报告文件
- 取证方式：**静态等价证据**（自研第二实现 + grep 逐条上下文裁定）。本会话无可用浏览器，详见文末「我没有验证的部分」

---

## 0. 结论摘要

| 文件 | 结论 | 一句话总评 |
| --- | --- | --- |
| `design/directions/direction-a.html` | **PARTIAL** | 结构/文案/无障碍/自包含全部通过，但存在 **2 处真实对比度不达标**，且都作用在真实正文与状态文字上 |
| `design/directions/direction-b.html` | **PASS**（含非阻塞文档缺陷） | 全项通过；Lead 报的琥珀色不达标经核查为 **token 层假阳性**，真实用色 6.56:1；两处 token 注释自述比值写错 |
| `design/directions/direction-c.html` | **FAIL** | 对比度全项最优（12/12 通过），但 **17 处组件内裸 hex** 违反 content-spec §0，且与它自己在 S14 的声明矛盾；另有 Lead 报告的标记不平衡（我未独立复核） |
| `design/ia/sitemap.html` | **PASS** | 契约一致性最强项：**34/34 方法与路径引用有效、29/29 错误码↔HTTP 映射与 SRS §8 完全一致**；3 个「对不上」的路径经核查均非自造端点，属路由/通配写法 |
| `design/reviews/verify.py`（Lead 提供的校验器） | **不可用** | **脚本无法运行**（第 363 行赋值被注释吞掉 → `NameError`）；缓存输出已失效。本报告不依赖其结论 |

**一句话总评**：三个方向在结构与文案上高度可信（15/15 屏幕块、31/31 逐字文案、全零外部请求、全零 emoji、label/for 零悬空），方向差异是**真实的**而非换色；主要缺陷集中在 A 的对比度与 C 的 token 纪律，两者都是**局部、可机械修复**的问题，不构成方向整体推翻的理由。

---

## 1. A — 自包含性 / 无外部请求

**方法**：正则扫描 `https?://`、`<img>`、`<link>`、`@import`、`<script src>`、`<iframe>`、`url(http…)`、`@font-face`/webfont 特征串；`python -` 内联第二实现（脚本落在 `%TEMP%`，不入工作区）。

**证据**：

| 文件 | 外部 url | w3.org | img | link | @import | script(src) | iframe | url(http) | webfont | svg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| direction-a | 无 | 无 | 0 | 0 | 0 | 0 | 0 | 0 | 无 | 186 |
| direction-b | 无 | 1 | 0 | 0 | 0 | 1(0) | 0 | 0 | 无 | 146 |
| direction-c | 无 | 无 | 0 | 0 | 0 | 1(0) | 0 | 0 | 无 | 139 |
| ia/sitemap | 无 | 无 | 0 | 0 | 0 | 0 | 0 | 0 | 无 | 28 |

- B 的唯一 `http://www.w3.org/2000/svg` 是 `--paper-grain` 的 **data URI 内 `xmlns` 命名空间声明**（`direction-b.html` `:root` 段），不是网络请求。
- A/B/C 的 `<script>` 均为**内联**且 `src=0`；`sitemap.html` 无脚本。content-spec 允许「极小量内联 script」。

**结论**：**PASS（四文件全部）**。零 CDN、零 webfont、零图片文件、零外部字体。

---

## 2. B — 结构完整性（S00–S14）

**方法**：提取全部 `data-screen="Sxx"`，比对 15 个 id 的集合、重复数、出现顺序；再逐块打印首个可见文本以确认「带可见小标题」。

**证据**（第二实现输出）：

| 文件 | 唯一屏幕块 | 缺失 | 重复 | 顺序升序 |
| --- | --- | --- | --- | --- |
| direction-a | 15/15 | 无 | 无 | 是 |
| direction-b | 15/15 | 无 | 无 | 是 |
| direction-c | 15/15 | 无 | 无 | 是 |

- `direction-c.html` **不含** `class="screen-head"` 标记（A/B 各 16 处），但其 15 个块**逐个都有可见小标题**，实测首文本为：
  `S00 方向 C` / `S01 登录` / `S02 助手 · 空闲态` / `S03 助手 · 执行中` / `S04 助手 · 有据回答 + 引用展开` / `S05 助手 · 依据不足 / 检索失败` / `S06 助手 · 草稿未保存 → 保存成功 / 结果待确认` / `S07 我的课表 · 有课` / `S08 我的课表 · 两种空状态` / `S09 学习计划 · 列表 + 详情编辑` / `S10 管理中心 · 课程管理` / `S11 管理中心 · 文档与批次` / `S12 管理中心 · 课表维护` / `S13 窄屏 390 × 844` / `S14 设计 token 表`。
- 因此「C 缺 screen-head」是我方**类名启发式的假警报**，不是缺陷：content-spec 要求的是「带可见的小标题」，C 满足。

**结论**：**PASS（三个方向）**。

---

## 3. C — 文案保真（逐字比对）

**方法**：剥标签（去 `<script>/<style>`、注释、标签本身）→ 解 HTML 实体 → 删除全部空白 → 子串精确匹配。自查清单共 **31 条**（task-5 指定的 8 条 + content-spec 中其余加粗/标注逐字的字符串，含 `当前账号不可用，请联系管理员。`、`未提取到文字，可能是扫描件；本期不支持 OCR。`、`该学生在同一天已有完全相同时间段的这门课，不能重复保存。`、`已保存 · 计划编号 plan_7Q2F9K`、`TXT / MD / 含文字层的 PDF / DOCX；单文件 ≤ 20 MiB；单批 ≤ 10 个、合计 ≤ 50 MiB` 等）。

**证据**：

| 文件 | 命中 | 缺失 |
| --- | --- | --- |
| direction-a | **31/31** | 无 |
| direction-b | **31/31** | 无 |
| direction-c | **31/31** | 无 |

task-5 点名的 8 条全部逐字命中，包括易错的两条：
- `与 2026-10-22 10:00–11:40 大学英语 时间重叠。`（含 U+2013 en dash）
- `2026-10-22（周四）没有课程安排。`（含全角括号）

**结论**：**PASS（三个方向）**。逐字文案无缺字、无改字。

---

## 4. D — 无障碍抽查

**方法**：不只计数，还**真实解析 `label for=` ↔ 文档内 `id`**（比计数更强）；并统计 `:focus-visible`、`aria-hidden="true"`、`aria-describedby`、`aria-live`、`role="alert"`、`<caption>`/`<table>` 配平、`scope`、`prefers-reduced-motion`、`tabular-nums`。

**证据**：

| 文件 | label(带 for) | for 悬空 | focus-visible | aria-hidden | aria-describedby | caption/table | scope | reduced-motion | tabular-nums |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| direction-a | 33(33) | **0** | 5 | 214 | 19 | 8/8 | 39 | 2 | 13 |
| direction-b | 22(22) | **0** | 5 | 146 | 20 | 7/7 | 30 | 2 | 5 |
| direction-c | 28(28) | **0** | 8 | 150 | 18 | 15/15 | 59 | 4 | 2 |
| ia/sitemap | 0 | 0 | 2 | 50 | 1 | 8/8 | 39 | 1 | 1 |

抽查四项全部落实：
1. **可见 label 与控件关联**：A 33/33、B 22/22、C 28/28，**零悬空 `for`**，且无「有 label 但无 for」者。
2. **`:focus-visible` 存在**：A `outline:3px solid var(--brand)`（3px ≥ 2px）；C 另有 `.topbar/.sidebar/.dnav` 的 `outline:2px solid #A5B4FC`（但见 §9 裸 hex 问题）；B 亦定义于全站。
3. **状态「图标+文字+颜色」三重表达**：三方向状态胶囊均为内联 SVG + 文字 + 语义色。视觉去色后仍可读的文案实例（A）：`完成 · 2 条记录`、`删除失败`、`依据不足`（`direction-a.html:3461` 自述，正文中同名文本可见于 S03/S11 各块）。
4. **表格 `<caption>`/`scope`**：A 8 表 8 caption、B 7 表 7 caption、C 15 表 15 caption，**每张表都有 caption**；`scope` 分别 39/30/59。

补充：C 全局 `body{font-variant-numeric:tabular-nums}`，故显式出现仅 2 处即已满足 content-spec 的「数字必须 tabular-nums」。

**结论**：**PASS（三个方向）**。

---

## 5. E — 对比度核算（独立复算）

**公式（WCAG 2.x，可复现）**：
```
对每个 sRGB 通道 c∈{R,G,B}，先归一化 c/255：
  if c <= 0.04045: c' = c/12.92
  else:            c' = ((c+0.055)/1.055)^2.4
相对亮度 L = 0.2126*R' + 0.7152*G' + 0.0722*B'
对比度 = (L_亮 + 0.05) / (L_暗 + 0.05)
```
**公式自检**（证明实现正确）：`#000000/#FFFFFF = 21.000:1`（理论值恰为 21）；`#767676/#FFFFFF = 4.542:1`（WCAG AA 的著名边界灰）。

**方法**：从每个文件 `:root` 读取**声明值**（解析 `var()` 链），用上式计算。**再单独做第二步**：用 grep 找出每个 token 的**实际使用位置**，判定它落在正文/小字还是仅图标/非文字，据此裁定真实影响。

### 5.1 三方向全量配对结果

| 方向 | 配对 | 计算值 | 阈值 | 判定 |
| --- | --- | --- | --- | --- |
| A | `--ink` #0F172A / `--canvas` #F1F5F9 | 16.296:1 | 4.5 | OK |
| A | `--ink` / `--surface` #FFFFFF | 17.853:1 | 4.5 | OK |
| A | `--ink-2` #334155 / `--surface` | 10.355:1 | 4.5 | OK |
| A | `--ink-3` #64748B / `--surface` | 4.759:1 | 4.5 | OK |
| A | **`--ink-3` / `--canvas`** | **4.344:1** | 4.5 | **FAIL** |
| A | `--ink-3` / `--surface-2` #F8FAFC | 4.548:1 | 4.5 | OK（余量仅 0.048） |
| A | `--success` #15803D / `--success-tint` #DCFCE7 | 4.567:1 | 4.5 | OK |
| A | `--warning` #B45309 / `--warning-tint` #FEF3C7 | **4.510:1** | 4.5 | OK（余量 0.010，脆弱） |
| A | `--danger` #B91C1C / `--danger-tint` #FEE2E2 | 5.296:1 | 4.5 | OK |
| A | `--info` #0369A1 / `--info-tint` #E0F2FE | 5.171:1 | 4.5 | OK |
| A | **`--teal` #0F766E / `--teal-tint` #D7EDEB** | **4.484:1** | 4.5 | **FAIL** |
| A | `--teal` / `--teal-tint-2` #EFFAF8 | 5.134:1 | 4.5 | OK |
| A | `--teal` / `--surface` | 5.473:1 | 4.5 | OK |
| A | 主按钮 `#FFF` / `--brand` #1D4ED8 | 6.702:1 | 4.5 | OK |
| A | `--brand` #1D4ED8 / `--brand-tint` #DBEAFE | 5.493:1 | 4.5 | OK |
| B | `--c-ink-900` #1C1917 / `--c-bg-page` #FAF8F5 | 16.498:1 | 4.5 | OK |
| B | `--c-ink-900` / `--c-bg-card` #FFFFFF | 17.488:1 | 4.5 | OK |
| B | `--c-ink-600` #5B544E / `--c-bg-page` | 7.018:1 | 4.5 | OK（注释自述 ≈5.8，见 5.3） |
| B | `--c-ink-500` #6B6259 / `--c-bg-page` | 5.634:1 | 4.5 | OK（注释自述 ≈4.8，见 5.3） |
| B | `--c-ink-500` / `--c-ink-200` #E7E5E4 | 4.756:1 | 4.5 | OK |
| B | `--c-ink-400` #78716C / `--c-bg-card` | 4.798:1 | 3.0（非文字） | OK |
| B | `--c-ok-700` #3F6212 / `--c-ok-100` #ECF2DF | 6.179:1 | 4.5 | OK |
| B | `--c-amber-700` #B45309 / `--c-amber-100` #FBF0DF | 4.455:1 | 4.5 | **数值不达标，但实际未这样用 → 见 5.2** |
| B | `--c-amber-800` #8A4107 / `--c-amber-100` | **6.561:1** | 4.5 | **OK（这才是真实用色）** |
| B | `--c-danger-700` #9F1239 / `--c-danger-100` #FBE7EC | 6.773:1 | 4.5 | OK |
| B | `--c-info-700` #1E5F74 / `--c-info-100` #E3EEF2 | 6.038:1 | 4.5 | OK |
| B | `--c-green-700` #14665B / `--c-green-100` #E3EDEB | 5.705:1 | 4.5 | OK |
| B | 主按钮 `#FFF` / `--c-green-700` | 6.815:1 | 4.5 | OK |
| C | `--c-slate-900` #0F172A / `--c-slate-50` #F8FAFC | 17.063:1 | 4.5 | OK |
| C | `--c-slate-900` / `--c-white` #FFFFFF | 17.853:1 | 4.5 | OK |
| C | `--c-slate-700` #334155 / `--c-white` | 10.355:1 | 4.5 | OK |
| C | `--c-slate-500` #64748B / `--c-white` | 4.759:1 | 4.5 | OK |
| C | `--success-tx` #15803D / `--success-bg` #F0FDF4 | 4.791:1 | 4.5 | OK（余量 0.291） |
| C | `--warning-tx` #B45309 / `--warning-bg` #FFFBEB | 4.842:1 | 4.5 | OK（余量 0.342） |
| C | `--danger-tx` #B91C1C / `--danger-bg` #FEF2F2 | 5.915:1 | 4.5 | OK |
| C | `--info-tx` #0369A1 / `--info-bg` #F0F9FF | 5.566:1 | 4.5 | OK |
| C | `--neutral-tx` #334155 / `--neutral-bg` #F1F5F9 | 9.452:1 | 4.5 | OK |
| C | `--topbar-fg` #E6EDF7 / `--topbar-bg` #0B1220 | 15.889:1 | 4.5 | OK |
| C | `--topbar-fg-dim` #9FB0C9 / `--topbar-bg` | 8.495:1 | 3.0 | OK |
| C | 主按钮 `#FFF` / `--brand` #4F46E5 | 6.288:1 | 4.5 | OK |

**计数**：A 不达标 **2** 处；B 数值不达标 1 处但**实际未如此使用**；C 不达标 **0** 处。

### 5.2 三处临界的**实际影响**裁定（关键裁定，非只看 token）

**A-① `--ink-3` #64748B on `--canvas` #F1F5F9 = 4.344:1 → 真实不达标，影响正文小字**
- 使用位置（grep `var(--ink-3)`，共 40 处）中，**直接位于 `--canvas` 画布上**的有：
  - `direction-a.html:132` `.screen-note{color:var(--ink-3);font-size:var(--fs-13)}`，实例见 `direction-a.html:871`、`:980`、`:1143`、`:1444`、`:1717`、`:1857`、`:2119`、`:2658`、`:3159`、`:3373` —— 这些 `<p class="screen-note">` 是 `<section class="screen">` 的直接子元素，而 `.screen` 无背景，继承 `body{background:var(--canvas)}`。
  - `direction-a.html:490` `.sub{font-size:var(--fs-13);color:var(--ink-3)}`，画布层实例见 `:768`、`:869`、`:978`。
- 字号为 **13px（`--fs-13`）与 12px（`--fs-12`）**，远小于「大字」界线（18.66px / 14pt 粗体），因此适用 **4.5:1**，不适用 3:1。
- 注意 `direction-a.html:3406` 的 S14 自述写「4.76:1，仅用于 ≥13px 文本」——该 4.76 是**对 `--surface` 白底**的值；token 表未声明它在画布底上只有 4.34:1。

**A-② `--teal` #0F766E on `--teal-tint` #D7EDEB = 4.484:1 → 真实不达标，影响状态胶囊文字**
- 使用位置（grep `var(--teal)` / `var(--teal-tint)`，共 11 处）：
  - `direction-a.html:316` `.pill--evidence{background:var(--teal-tint);color:var(--teal);border-color:transparent}` —— **正是「有依据」语义胶囊的文字**（图标 + 文字 + 颜色），命中即真实文字。
  - 其余 teal 用法安全：`:252-253` 用 `--teal-tint-2` 底（5.134:1）、`:263` 为左 3px 边框（非文字）、`:272` 在白卡上（5.473:1）、`:2478/:2679/:2967` 为头像底色（非文字）。
- 灰色区间仅差 0.016。

**B-③ `--c-amber-700` #B45309 on `--c-amber-100` #FBF0DF = 4.455:1 → token 层假阳性，实际无影响**
- grep `var(--pending)` / `var(--pending-tint)` / `var(--pending-strong)`（共 7 处）显示：
  - `--pending`（=#B45309）**从不作文字色**，只用于：`:462` `border:2px dashed var(--pending)`（2px 虚线边框 = 非文字 UI）、`:470` `background:var(--pending);opacity:.5`（装饰条）、`:270/:477/:480` 的 `color-mix(... 30%/40%)` 边框。
  - 真正压在琥珀浅底上的**文字**用的是 `--pending-strong` / `--state-warning`（= `--c-amber-800` = **#8A4107**）：`:270` `.cap-pending{background:var(--pending-tint);color:var(--pending-strong)}`、`:617` `.inline-alert.warn{background:var(--pending-tint);color:var(--state-warning)}` → 实测 **6.561:1**，达标且余量充足。
  - 作为非文字 UI 时：`#B45309` 在白卡上 5.022:1、在页面底 4.737:1，均 ≥3:1。
- 结论：**B 不存在琥珀色对比度失败**。这是「按 token 表配对」而非「按实际使用配对」造成的误报。

### 5.3 B 自述比值的复核

| 位置 | 注释自述 | 实际计算 | 判定 |
| --- | --- | --- | --- |
| `direction-b.html` `--c-ink-600:#5B544E` 注释 | 「对页面底 ≈5.8:1」 | **7.018:1** | **注释错误**（低估 1.2，方向偏安全） |
| `direction-b.html` `--c-ink-500:#6B6259` 注释 | 「对页面底 ≈4.8:1（已通过 4.5:1）」 | **5.634:1** | **注释错误**（低估 0.8，方向偏安全） |
| `direction-b.html:2011` / `:2012` S14 表同值复述 | 同上 | 同上 | 同上，**错误在 token 注释与 S14 表两处重复出现** |

两处均**低估**（actual 更好），因此不构成无障碍风险，但属**事实性文档缺陷**。

**结论（E）**：**A = FAIL（2 处真实不达标）**；**B = PASS**（Lead 所报不达标不成立；但注释比值错误需更正）；**C = PASS（12/12）**。

---

## 6. F — 方向差异真实性

**方法**：从三份文件 `:root` 逐个取 token 值（解析 `var()` 链），按内容/结构/密度/层次四个维度对比。

**实测差异表**（`—` = 该方向未定义此 token）：

| 指标 | A 学院蓝 · 清晰秩序 | B 纸感专注 · 对话优先 | C 数据密集 · 运维控制台 |
| --- | --- | --- | --- |
| 主色 | `--brand` **#1D4ED8** 靛蓝 | `--accent`→`--c-green-700` **#14665B** 墨绿 | `--brand`→`--c-indigo-600` **#4F46E5** 靛紫 |
| 正文字号 | `--fs-15` **15px** | `--fs-17` **17px** | `--fs-13` **13.5px** |
| 正文行高 | `--lh` **1.6** | `--lh-body` **1.75** | `--lh-body` **1.45** |
| 间距基准 | `--s1` **4px**（4/8/12/16/20/24/32/48） | `--sp-1` **6px**（6/12/18/24/36/48/72，**刻意非 4 的倍数**） | `--sp-1` **2px**（2/4/6/8/12/16/24/32，更紧） |
| 卡片圆角 | `--r-card` **10px** | `--r-card` **14px** | `--r-md` **6px** |
| 控件圆角 | `--r-ctl` **8px** | `--r-control` **10px** | `--r-sm` **4px** |
| 阴影策略 | `--shadow` 双层 `0 1px 2px rgba(15,23,42,.06), 0 1px 3px rgba(15,23,42,.10)` | `--shadow-hair` 极淡单层 `0 1px 1px rgba(28,25,23,.04)`，层次靠留白+1px 暖分隔线 | `--hairline` = `1px solid var(--border)`，**零阴影，纯边框分层** |
| 布局结构 | 侧栏 `--sidebar-w` **240px** + 顶栏 `--topbar-h` **56px** + 助手三栏（`--readw` **760px** / 面板 `--panelw` **320px**） | **无侧栏**，单列居中（`--w-content` **880px** / 助手 `--w-assistant` **720px**）+ 顶栏 `--h-topbar` **64px** | 可折叠侧栏 `--sidebar-w` **216px** / 折叠 `--sidebar-collapsed-w` **56px** + **深色顶栏** `--topbar-h` **48px** + 12 栅格 max 1600px |
| 页面底 | `--canvas` **#F1F5F9**（slate 冷灰） | `--c-bg-page` **#FAF8F5**（暖纸白） | `--c-slate-50` **#F8FAFC**（slate 冷灰） |
| 正文色 | `--ink` **#0F172A** | `--c-ink-900` **#1C1917**（暖黑） | `--c-slate-900` **#0F172A** |
| 语义色策略 | 4 语义色 + 青绿辅色（**仅「有依据」**） | 4 语义色 + 琥珀（**仅「未保存/待确认」**） | 高饱和语义色**仅小面积**；主色靛紫 |
| token 总数 | **52** | **84** | **103** |
| 过程区形态 | 右侧 `--panelw` 320px「本轮执行 + 引用 + 草稿」面板（`direction-a.html:978` 自述「三栏：240px 侧栏｜对话主区 max 760px｜320px 本轮执行面板（带折叠把手）」） | **UNKNOWN — 本轮未取证**（仅可确认无侧栏、单列 720px） | 事件流形态（S03 标题自述「只展示可核实动作；事件流与 SSE 契约对齐（status / tool_start / tool_end...）」） |
| S11 文档 5 状态呈现 | `direction-a.html:2658` 自述「胶囊 + 进度条 + 原因文字三列排布，1366px 下不需要横向滚动」 | `<li>` 列表行 + `span.help` 承载原因（`:1686`） | `<tr>` 表格行（`:1882`、`:2243`），"后台表格允许横向滚动" |

**独立判断**：**不是同一套皮换色**。理由：
1. **密度不同量级**：正文 15 / 17 / 13.5px，行高 1.6 / 1.75 / 1.45，间距基准 4 / 6 / 2px，表格行高在 C 为 36px、B 另有紧凑变体 40px/14px。这是三种真实的信息密度选择，不是配色差异。
2. **层次策略互斥**：A 用阴影、B 用留白+暖分隔线、C 明令「零阴影，一律 1px 边框」。这是结构性的视觉语言差异。
3. **布局拓扑不同**：A 有 240px 固定侧栏 + 320px 右面板（三栏）；B **完全无侧栏**（单列 880px / 助手 720px）；C 是可折叠 216/56px + 深色 48px 顶栏 + 12 栅格。三者的一级导航形态互不相同（B 的助手过程区具体形态本轮未取证，标 UNKNOWN，不影响本项判定）。
4. **圆角/字号阶梯各自独立**，token 总数 52/84/103 说明语义抽象层次不同，而非改色。

**结论**：**PASS**。

---

## 7. G — 违禁内容扫描与逐条裁定

**方法**：自研 emoji 正则（图形区段 `U+1F000–1FAFF`、`U+2600–27BF`、`U+2B00–2BFF`、`U+FE0F`、`U+20E3`；**刻意不含箭头 U+2190–21FF**，因为 `→`/`‹`/`›` 是 content-spec 自身使用的排版符号）+ 全部违禁关键词的**逐条上下文打印**（前 95 / 后 95 字符），由我人工裁定。

### 7.1 emoji 作图标

| 文件 | 命中 |
| --- | --- |
| direction-a / b / c / ia | **零**（全部图形区段无任何码位） |

### 7.2 未承诺功能入口

**全部命中均为「声明不包含」语境**，无一处是真实入口：

| 关键词 | 命中位置 | 上下文裁定 |
| --- | --- | --- |
| 选课/成绩/考勤/作业提交/提醒/推送/周次/节次/教务同步/跨设备/社交/评论 | `direction-a.html:3474` | 「**不画** PRD 未承诺的入口：**无**选课、成绩、考勤、作业提交、提醒推送、OCR、周次节次、教务同步、跨设备历史、社交评论。」→ 否定式清单 |
| 同上 | `direction-c.html:2413` | 「**无**选课、成绩、考勤、作业提交、提醒/推送、OCR、周次/节次、教务同步、跨设备历史、社交入口。」→ 否定式清单 |
| 同上 | `sitemap.html:320` | 「不适用场景 …… 本期**均未承诺**，IA **不为其预留入口**。」 |
| 同上 | `sitemap.html:536` | 「站点地图里没有的东西同样重要：**无**选课、成绩、考勤、作业提交、提醒推送、OCR、周课表、教务同步、跨设备历史。这些不是"待补"，而是 PRD 未承诺，IA 不预留入口。」 |
| OCR | `direction-a.html:2713`、`:2811`、`:3337`；`direction-b.html:1637`、`:1686`；`direction-c.html:1882`、`:2243`；`sitemap.html:967` | 全部为「**本期不支持 OCR**」——**content-spec S11 明文要求逐字出现**这句失败原因，属必需内容 |
| 提醒/推送 | `direction-b.html` | 无命中（B 未出现该词） |

### 7.3 真实学校名 / 师生姓名

- **真实学校名：四个文件全部零命中**（对 32 所国内高校名做了全量扫描）。
- 学校/地点均为虚构：`计算机学院`、`主楼 A-305`、`文科楼 B-102`。
- 人物标签为匿名占位，**非真实姓名**：A 用 `李同学`（学生）/`王老师`（管理员）；B 用 `stu_2026001（张同学）`；IA 用 `张同学`。均为「姓 + 通用称谓」的虚构占位，无完整真实姓名。→ 判定**不违规**，但 B 的 `stu_2026001` 形似真实学号，列入「建议改进」。

### 7.4 「正在思考」当过程状态

| 位置 | 上下文 | 裁定 |
| --- | --- | --- |
| `direction-a.html:1143` | 「过程区只展示可核实的动作，**不出现**「正在思考」「AI 推理中」。」 | 反例说明 |
| `direction-a.html:3475` | 「**不把**「正在思考 / 模型推理」写成过程状态。」 | 反例说明 |
| `direction-c.html:2412` | 「**无**「正在思考 / 模型推理中」类过程状态；过程区只列可核实动作。」 | 反例说明 |
| `sitemap.html:1107` | 「**禁止**"正在思考""AI 推理中"；tool_start 只代表"已被调度"…」 | 反例说明 |
| `sitemap.html:1079` | 生命周期表 `running` 行的**最后一列**值：`展示"正在思考 / AI 推理中"；把 tool_start 当作已完成` | **反例说明** |

**关于 IA L1079 的关键核实**：该表表头（`sitemap.html:1067`）为
`<thead><tr><th scope="col">state</th><th scope="col">来源事件</th><th scope="col">UI 显示</th><th scope="col">可做操作</th><th scope="col">不可做</th></tr></thead>`
→ 该单元格位于 **「不可做」列**，确属**反例说明**，不是被声称为真实过程状态。**不违规**。

### 7.5 空结果与读取失败合并呈现

`暂无数据` 的每一次出现都是**禁止合并**的声明，且两态在实现上是**分离的不同元素/不同色/不同动作**：
- A：`direction-a.html:2117`「硬验收点：**不得**合并成一个「暂无数据」」、`:2181`「这两种状态**不得**合并为「暂无数据」，也**不得**共用同一个图标或同一个动作」；正文中两态各自独立：①「查询成功但无记录」用中性插画（`:1798-1802`）②「服务异常」用危险色 + 警告三角（`:2133`）。
- B：`direction-b.html:1358`「**禁止**合并成一个「暂无数据」。①不得使用错误色；②必须使用错误/警告语义。」
- C：`direction-c.html:1423`「**禁止**合并成一个「暂无数据」。」
- IA：`sitemap.html:328`「"空结果"与"读取失败"在 IA 层就是两条不同分支（S08 ①②），**不会**在实现时被合并成一个"暂无数据"。」

**结论（G）**：**PASS（四个文件）**。零 emoji、零真实校名、零真实姓名、零未承诺入口、零「正在思考」真实状态、零空/错合并。

---

## 8. H — IA 契约一致性

**方法**：把 `sitemap.html` 中所有路径式字符串与 `docs/backend/openapi_v0.1.json` 的 `paths` 逐一规范化比对（`{id}`/`:id` 归一并去尾斜杠、去 query/hash）；再由独立正则抽取**所有 `VERB /path` 形式的 API 引用**做全量校验；最后把 IA 中「HTTP 状态 / 错误码」单元格对与 SRS §8 表格逐行比对。

**证据**：

1. **方法与路径引用全量校验：34 条命中，34 条有效，0 条无效。**
2. **端点集合**：抽出 30 个路径式 token，其中 **27 个精确匹配 OpenAPI**，例如：
   `/admin/courses` ↔ `/api/v1/admin/courses`、`/admin/document-batches/{id}` ↔ `/api/v1/admin/document-batches/{id}`、`/me/schedules` ↔ `/api/v1/me/schedules`、`/chat/stream`、`/citations/{reference_id}`、`/me/drafts/{draft_id}/save`、`/me/write-operations/{operation_id}`、`/admin/documents/{id}/cleanup-retry`、`/admin/documents/{id}/rebuild`、`/admin/documents/{id}/text` 等。
3. **3 个「对不上」的 token —— 全部经核查为非端点，不属自造**：

| token | 出现位置 | 实际性质 | 裁定 |
| --- | --- | --- | --- |
| `/admin` | `sitemap.html:606`、`:608` | **路由表**中的「管理中心入口页（**不承载业务**）」，行为=重定向到 `/admin/courses` | 前端路由，非端点声明 → **不算自造** |
| `/admin/*` | `sitemap.html:453`、`:454`、`:550`、`:687` | **通配 glob**，用于描述「管理中心子树」的守卫行为（「学生访问 `/admin/*` → 通用拒绝页」）；`/me/*` 同形 | 通配模式，非端点 → **不算自造** |
| `/admin/documents/batches/:batchId` | `sitemap.html:357`、`:497`、`:630`、`:632`、`:655`、`:726` | **页面路由**（路由与守卫表 L630 明确列在「path」列） | 前端路由，非端点 → **不算自造** |

   **决定性反证**：IA 在真正引用 API 的地方**用的是正确路径**——`sitemap.html:499` `POST /admin/document-batches（202）`、`:500` `GET /admin/document-batches/{id}`、`:947`、`:953`、`:955` 均正确。即 IA **从未把 `/admin/documents/batches/:batchId` 当作 API 端点**。

4. **错误码**：IA 共使用 **29 个 SRS §8 表内错误码**（即 §8 表格全部 29 条，无遗漏），另加 6 个异步任务码 `NO_TEXT_EXTRACTED` / `DOCUMENT_ENCRYPTED` / `PARSE_FAILED` / `EMBEDDING_FAILED` / `CLEANUP_FAILED` / `SERVICE_RESTARTED`（§8 末段明文允许）。全部落在 SRS §8 内。
   - 唯一不在 §8 的全大写 token 是 `DELETE` / `DOCTYPE` / `PATCH`——HTTP 方法与 DOCTYPE 声明，非错误码。
5. **错误码 ↔ HTTP 状态映射：29/29 与 SRS §8 完全一致，0 不一致**（含 `413 UPLOAD_TOO_LARGE`、`415 UNSUPPORTED_FILE_TYPE`、`409 SCHEDULE_OVERLAP`、`409 VERSION_CONFLICT`、`409 CHAT_IN_PROGRESS`、`410 DRAFT_EXPIRED`、`410 CITATION_UNAVAILABLE`、`422 SAVE_NOT_AUTHORIZED`、`429 CAPACITY_LIMITED`、`503 RETRIEVAL_UNAVAILABLE`、`504 EXECUTION_TIMEOUT` 等）。

**结论（H）**：**PASS**。无自造端点、无自造错误码。

**责任归属说明**：`/admin/documents/batches/:batchId` 这个路由名是 **Lead 在 task-4 任务书里写下的**（task-4 原文要求覆盖 `/admin/documents/batches/:batchId`），ia-architect 按任务书忠实实现。OpenAPI 中对应的资源实为 `/admin/document-batches/{id}`。因此**命名不对称的根因在任务书，而非 IA 作者**；但任务书同时要求「与 docs 的端点一致」，故仍建议 IA 侧对齐路由名（见建议改进）。另：Lead 在 task-5 revision 3 与来信中把该路径写成 `/admin/documents/batches/`（带尾斜杠、丢 `:batchId`），与实际字符串不符。

---

## 9. I — 设计系统纪律（裸 hex）

**方法**：取出全部 `<style>` 块 → 剔除 `:root{…}` 段 → 剔除 `/* 注释 */` → 统计 `#RRGGBB`；另统计 HTML 内联 `style="…"` 中的 hex 并**定位到行**，再逐行读上下文判定是「组件样式」还是「S14 token 文档表」。

| 文件 | `<style>` 内（`:root` 外）裸 hex | inline style 带 hex | 性质裁定 |
| --- | --- | --- | --- |
| direction-a | **0** | **0** | 完全合规（S14 表用 `style="background:var(--ink-3)"` + 文本列写字面值） |
| direction-b | **0** | **24** | 24 处**全部**位于 `:1997–2017`，即 S14「设计 token 表」的色块 `<i style="background:#14665B">` + 「值」列字面量 → **文档性用法**，非组件样式 |
| direction-c | **16** | **17**（1 处组件 `:2126` + 16 处 S14 表 `:2284–2299`） | 16 处**确为组件 CSS** → **违反 content-spec §0** |
| ia/sitemap | 0 | 0 | 合规 |

**C 的 16 处组件裸 hex 逐行证据**（均在 `<style>` 内、`:root` 之外）：

| 行 | 代码 | 问题 |
| --- | --- | --- |
| 119 | `.topbar :focus-visible,.sidebar :focus-visible,.dnav :focus-visible{ outline:2px solid #A5B4FC; ...}` | 焦点轮廓硬编码，未走 `--focus`/`--focus-ring` |
| 137 | `background:#0E1626; color:var(--topbar-fg-dim)` | 同一行里一半用 token 一半用裸值 |
| 146 | `.topbar .kbd{border-color:#2A3A55;background:#131C2E;color:#C7D6EA}` | 3 个裸值（已有 `--topbar-border`/`--topbar-hover` 可复用） |
| 153 | `border:1px solid #2E3E5C; background:#131C2E; color:#DCE6F5` | 3 个裸值 |
| 162 | `.nav-label{… color:#6B7E9C …}` | 裸值 |
| 170 | `.nav-item .badge-n{margin-left:auto;font-size:var(--fs-11);color:#93A6C4}` | 裸值 |
| 171 | `.sidebar-foot{… color:#6B7E9C}` | 裸值 |
| 325 | `.input::placeholder,.textarea::placeholder{color:#8A99AE}` | 裸值 |
| 362 | `.tbl tbody tr:hover{background:#FBFCFE}` | 裸值 |
| 367 | `.tbl-zebra tbody tr:nth-child(even){background:#FCFDFE}` | 裸值 |
| 409 | `.ref-b{… background:#FCFDFF …}` | 裸值 |
| 447 | `… background:#FCFDFF` | 裸值 |

外加 `:2126` 组件内联 `<span style="margin-left:auto;font-size:13px;color:#9FB0C9">9:41</span>`（390px 模拟框内的手机状态栏）——同样是组件内写死裸色，且该色本身就是 `--topbar-fg-dim` 的值。

**违反的规则原文**（`content-spec.md:27`）：
> 所有颜色必须来自文件顶部的 CSS 自定义属性（语义 token），**不允许在组件里写裸 hex**。

**加重情节**：C 自己在 S14 的标题里声明「S14 设计 token 表 全部 CSS 自定义属性；**组件内只引用语义 token，不写裸 hex**」——即 **C 的自我声明被 C 自己的样式表证伪**（16 处）。这是自相矛盾，而非单纯风格偏好。

**结论（I）**：**A PASS / B PASS（附非阻塞建议）/ C FAIL / IA PASS**。

---

## 10. J — 标记完整性（补充项，部分 UNKNOWN）

- 我本轮**没有独立执行标签开闭配平检查**，因此不对三份文件的 DOM 平衡性下结论。
- **Lead 报告（我未独立复核）**：`direction-c.html` 有 **11 处多余 `</div>`**，行号 L1027 / L1137 / L1208 / L1329 / L1425 / L1479 / L1638 / L1784 / L1976 / L2105 / L2269，根因为 11 处 `<span class="right">…</span></div>` 少一个 `</span>`；designer-c 正在修复。
- 若该报告属实，属**必修**级别（DOM 结构错误）。**本项判定：PARTIAL / 依赖 Lead 数据**。
- Lead 另报告其评审页 `design/directions/index.html` 亦通过同一校验器——**该文件不在我的验收范围内，我未验证**。

---

## 11. 必修问题（阻塞评审）

| # | 文件 | 问题 | 证据 | 最小修复建议 |
| --- | --- | --- | --- | --- |
| M1 | `direction-a.html` | `--ink-3`(#64748B) on `--canvas`(#F1F5F9) = **4.344:1 < 4.5**，且**真实用于 13px 画布正文/说明**（`.screen-note` L132、`.sub` L490；画布层实例 L768/869/871/978/980…） | §5.1、§5.2 A-① | 二选一：①把画布上的说明文字改用 `--ink-2`(#334155)；②把 `--ink-3` 整体调深到在 `#FFFFFF` 与 `#F1F5F9` 两处都 ≥4.5:1。修完须**重新计算**两处底色的比值，不要沿用 S14 里对白底的 4.76 |
| M2 | `direction-a.html` | `--teal`(#0F766E) on `--teal-tint`(#D7EDEB) = **4.484:1 < 4.5**，真实用于「有依据」状态胶囊文字 `.pill--evidence`（L316） | §5.1、§5.2 A-② | 把 `.pill--evidence` 的文字色改用更深的 `--teal-hover`(#0D5F59)，或提亮 `--teal-tint`；改后需重新核算（本轮未计算替换值，不预设结论） |
| M3 | `direction-c.html` | **17 处组件内裸 hex**（`<style>` 内 16 处：L119/137/146/153/162/170/171/325/362/367/409/447；组件内联 1 处：L2126），违反 `content-spec.md:27`「不允许在组件里写裸 hex」，并与 C 自己 S14 的声明矛盾 | §9 | 为深色顶栏/侧栏补齐语义 token（已有 `--topbar-fg`/`--topbar-fg-dim`/`--topbar-border`/`--topbar-hover`/`--sidebar-active`/`--brand` 等），把 `#0E1626 #131C2E #2A3A55 #2E3E5C #6B7E9C #93A6C4 #C7D6EA #DCE6F5 #A5B4FC #8A99AE #FBFCFE #FCFDFE #FCFDFF` 逐一收敛为 token；L119 的焦点轮廓改用 `--focus` |
| M4 | `direction-c.html` | **11 处多余 `</div>`**（DOM 不平衡）—— **Lead 报告，我未独立复核** | §10（Lead 数据） | 在 11 处 `<span class="right">…</span></div>` 补回缺失的 `</span>`（designer-c 正在修）。修完请重跑配平检查并给出复核结论 |
| M5 | `design/reviews/verify.py`（Lead 的校验工具，非交付物） | **脚本完全无法运行**：L363 的 `style_blocks = re.findall(...)` 与注释挤在同一行被 `#` 吞掉 → L364 `NameError: name 'style_blocks' is not defined`。`verify-output.txt` 内容仅为该 traceback（mtime 18:01:56），`verify-output.json`（mtime 18:01:03）**早于** `verify.py` 当前版本（mtime 18:02:08），故**缓存结论已失效** | 直接运行 `python design/reviews/verify.py` 得到 traceback；`Get-Content design/reviews/verify-output.txt` 见完整堆栈 | 把 L363 的赋值拆到独立一行（移出注释）。修好后其 A–I 输出才能作为可复现证据；**我无法代为修改**（超出我的写范围） |
| M6 | `direction-b.html` | token 注释中的**自述比值错误**：`--c-ink-600` 称「≈5.8:1」实际 **7.018:1**；`--c-ink-500` 称「≈4.8:1」实际 **5.634:1**（S14 表 L2011/L2012 重复同一错误） | §5.3 | 更正为实测值。误差方向安全（低估），故不阻塞无障碍，但**属错误陈述**，评审若引用会得出错误结论 |

> M1/M2 是**真实的无障碍不达标**，必须修；M3 是**明文规则违反 + 自我声明矛盾**，必须修；M4 待复核但按报告属必修；M5/M6 是**流程与文档正确性**问题。

---

## 12. 建议改进（不阻塞）

1. **A：`--warning` #B45309 / `--warning-tint` #FEF3C7 = 4.510:1** —— 仅高出阈值 **0.010**。任何对警告底色的微调都会立即跌破 AA。建议把余量提到 ≥4.8:1。
2. **C：`--success-tx`/`--success-bg` = 4.791:1、`--warning-tx`/`--warning-bg` = 4.842:1** —— 通过但余量 < 0.35。建议留出同等余量以免后续调色回退。
3. **A：`--ink-3` / `--surface-2` = 4.548:1** —— 余量仅 0.048（`.tokens thead th` L696、`.emptyart` L1798）。修 M1 时一并处理。
4. **B：S14 token 表的 24 处 inline hex（L1997–2017）** —— 属文档性用法（「值」列本就必须显示字面量），**不判违规**；但 A 展示了更干净的模式（色块用 `var(...)`、字面值只出现在文本列）。建议 B 对齐，以便「裸 hex」扫描在四文件上得到一致结果。
5. **IA：`sitemap.html:356–357` 的「路径」列把 UI 路由与 API 路径混在同一列**（该列同时出现 `/plans/:id`、`/admin/courses`、`/admin/documents`、`/admin/documents/batches/:batchId`）。这正是不必要的误读来源（也是本轮 3 个「对不上」的来源）。建议拆成「页面路由」「API 端点」两列。
6. **IA：路由名与资源名不对称** —— 页面 `/admin/documents/batches/:batchId` vs 接口 `/admin/document-batches/{id}`。建议路由改为 `/admin/document-batches/:id`。**注：现名来自 Lead 的 task-4 任务书**，IA 作者系忠实执行；若要改，需同时改任务书与 `sitemap.html`。
7. **B：占位账号 `stu_2026001（张同学）`**（`direction-b.html:1740`、`:1790`、`:1822`）形似真实学号；A 用 `student_demo`。建议统一为明显的虚构格式（如 `demo_student_01`），避免被误认为真实学生数据。
8. **C：`footer`/表格数字**：C 用全局 `body{font-variant-numeric:tabular-nums}`（满足要求），而 A 用 `.ds` 类、B 用 `time,.num,td.num,th.num` 选择器。三种都合规，仅记录差异；建议在 S14 里注明是全局生效，避免评审误判为「只有 2 处」。
9. **A：`.sitenav` 背景为 `rgba(255,255,255,.96)`**（半透明），`--ink-3` 在其上的实际对比度取决于背后内容。本轮未做 alpha 合成计算；建议改为不透明色以便静态可核算。

---

## 13. 我没有验证的部分

以下为**明确未验证**项，均不下 PASS 结论：

1. **真实浏览器渲染 —— 完全未验证。** 本会话无可用浏览器。依据 task-5 revision 3 记载的环境事实（Lead 实测）：DSH 侧栏浏览器后端返回 `tab_not_found`、`restore` 报「面板可能不在当前会话/分栏」；本机 Chromium（Edge 与 chrome-headless-shell）在 DSH 沙箱内启动即失败（`FATAL:mojo\public\cpp\platform\platform_channel.cc:187 Check failed: 拒绝访问`），且该后端不支持 `network`/`har`/`evaluate`。**我本人未复现该失败**（按任务书要求未再尝试），因此「能否打开」这一项**没有直接证据**，本报告的 A 项只证明「静态无外部引用」，不能等价替代「浏览器可打开、无 console error」。
2. **hover / focus / active / disabled 的实际样式 —— 未验证。** 只能读到 CSS 源码，未观察到真实聚焦环、悬停态、抽屉展开、标签页切换的渲染结果。
3. **实际渲染像素对比度 —— 未验证。** §5 全部数值均由**声明的 token hex 值**按 WCAG 2.x 公式计算，**未做 alpha 合成**，也未考虑：
   - 半透明层（A 的 `.sitenav{background:rgba(255,255,255,.96)}`、C 的 `--focus-ring:rgba(79,70,229,.30)`）；
   - B 的 `color-mix(in srgb, …)` 混合色（`--wash-ink-*`、`--wash-amber-*` 及各 `color-mix` 边框）；
   - 渐变、`opacity`（`direction-b.html:470` 用 `opacity:.5`）、`backdrop-filter`。
   因此**真实像素对比度可能与本报告数值有细微差异**。
4. **C 的 11 处多余 `</div>` —— 未独立复核。** 见 §10，属 Lead 数据。
5. **`design/directions/index.html`（Lead 的评审页）—— 未验证**，不在 task-5 验收范围内。
6. **响应式实渲染（1366px / 390×844）—— 未验证。** 只能确认 CSS 中存在 `@media` 与 390px 模拟框标记，无法确认实际排布、是否出现横向滚动、输入区是否真的吸底。
7. **屏幕阅读器阅读顺序 / Tab 次序 / 焦点管理 —— 未验证。** 仅能确认 `label for`↔`id` 全量可解析、`aria-*` 属性存在，不能确认实际可达性。
8. **F 表中的「B 过程区形态」单元格 —— UNKNOWN。** 本轮未取证 B 的助手过程区具体呈现方式（仅能确认无侧栏、单列、`--w-assistant:720px`）。
9. **脚本行为 —— 未验证。** B、C 各含 1 个内联 `<script>`（A 为 0），我未阅读其内容，也未验证其是否真能完成标签页/折叠演示，或是否在无脚本时仍可读懂。
10. **字体实际回退 —— 未验证。** 中文栈声明的字体在本机是否可用、`tabular-nums` 是否对中文字体生效，均未验证。

---

## 14. 与 Lead 结论的分歧

1. **「其余小节用你已跑到的 `python design/reviews/verify.py` 输出即可」—— 无法执行，且该工具的缓存结论已失效。**
   `verify.py` 当前版本**根本跑不起来**：L363 把 `style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", text, re.S)` 挤在注释行尾被 `#` 吞掉，L364 抛 `NameError: name 'style_blocks' is not defined`。`verify-output.txt`（18:01:56）内容**只是这段 traceback**；`verify-output.json`（18:01:03）的 mtime **早于** `verify.py`（18:02:08），说明它由更早的版本产生，**不能代表当前文件状态**。因此我没有引用它的任何数字，全部改用自研第二实现重算。建议先修 L363（我无法代改，超出写范围）。

2. **Lead：「B：`--c-amber-700` on `--c-amber-100` = 4.46:1（<4.5）」→ 我确认算术（4.455:1），但不同意「B 存在对比度不达标」的结论。**
   该配对**在 B 中从未以「文字 on 琥珀浅底」的形式出现**。`--pending`(#B45309) 只用于 2px 虚线边框（`:462`）、`opacity:.5` 装饰条（`:470`）与 30%/40% `color-mix` 边框（`:270/477/480`）——**全是非文字 UI**，适用 3:1 且实测 5.022:1（白卡）/ 4.737:1（页面底）；真正压在琥珀浅底上的文字是 `--pending-strong`/`--state-warning` = `--c-amber-800`(#8A4107)，实测 **6.561:1**。→ **B 无琥珀对比度失败**，这是一处 token 层假阳性。B 因此判 **PASS**。

3. **Lead：「A：`--ink-3`(#64748B) on `--canvas`(#F1F5F9) = 4.34:1」→ 我确认并强化。**
   我算得 **4.344:1**（Lead 的 4.34 是截断值）。更重要的是我补上了**实际影响证据**：`.screen-note`(L132) 与 `.sub`(L490) 以 13px 直接落在 `body{background:var(--canvas)}` 上（`.screen` 无背景），**不是仅图标或大字号**，故 4.5:1 阈值适用、不影响「是否算违规」的结论。A 的 `--teal`/`--teal-tint` 4.484:1 亦确认，且真实作用于 `.pill--evidence` 的状态文字。

4. **Lead：「IA 有 3 个路径与 OpenAPI 对不上（`/admin`、`/admin/`、`/admin/documents/batches/`），这 3 个是否属于自造」→ 我不同意「自造端点」的定性。**
   三个 token 均**不是端点声明**：`/admin` 是路由表里标注「不承载业务」的入口页（`:606/:608`）；`/admin/*` 是描述管理子树守卫的通配 glob（`:453/:454/:550/:687`）；`/admin/documents/batches/:batchId` 是页面路由（`:357/:497/:630/:632/:655/:726`）。**决定性反证**：IA 在真正引用 API 处全部使用正确路径（`:499` `POST /admin/document-batches`、`:500` `GET /admin/document-batches/{id}`、`:947/:953/:955`），并且**全量 34 条 `VERB /path` 引用 100% 有效**。因此 H 判 **PASS**；真正的问题只是 `:356–357` 那一列**把路由和端点混排**（建议改进第 5 条）。
   另外，Lead 在 revision 3 与来信中把该路径写作 `/admin/documents/batches/`（**带尾斜杠且丢失 `:batchId`**），与实际文件内容不符。

5. **Lead：「B 有 24 处 inline style 带 hex、C 有 16 处 `<style>` 内裸 hex」→ 计数我全部确认，但两者性质不同，不能并列。**
   B 的 24 处**全部**位于 `:1997–2017` 的 S14「设计 token 表」内，是该表「值」列与色块的字面量（content-spec 要求 S14 必须列出「名称、值、用途」）；且 B 的 `<style>` 在 `:root` 之外**裸 hex 为 0**。C 的 16 处则**确为组件 CSS**（`.topbar :focus-visible`、`.nav-label`、`.input::placeholder`、`.tbl tbody tr:hover` 等），并且**与 C 自己 S14 的「组件内只引用语义 token，不写裸 hex」声明直接矛盾**。→ B 的非阻塞、C 的判 FAIL。

6. **Lead：「A/B/IA 标记结构一致；C 有 11 处多余 `</div>`」→ 我未独立复核，标为 UNKNOWN。**
   本轮我未实现标签配平检查，不对此结论背书也不反驳。报告中仅作为「Lead 报告」转述（§10、M4）。

---

## 15. 可复现命令

```powershell
# 1) 运行 Lead 的校验器（会崩溃，这是本报告的分歧点 1）
python design/reviews/verify.py
Get-Content design/reviews/verify-output.txt          # 内容只有 traceback
Get-ChildItem design/reviews/ | Select Name,Length,LastWriteTime   # 对比 mtime 证明 JSON 过期

# 2) 结构 / 文案 / 无障碍 / emoji / 裸 hex（自研第二实现，脚本落在 %TEMP%）
#    见本轮内联 python 脚本：strip() 剥标签去空白后做 31 条逐字子串匹配；
#    label for= ↔ id 全量解析；emoji 正则 [\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\uFE0F\u20E3]

# 3) 对比度（WCAG 2.x，独立实现；自检 #000/#FFF=21.000、#767676/#FFF=4.542）
#    公式：c<=0.04045 ? c/12.92 : ((c+0.055)/1.055)^2.4 ；L=0.2126R+0.7152G+0.0722B
#    ratio=(Lmax+0.05)/(Lmin+0.05)

# 4) IA 契约一致性
#    OpenAPI paths: python -c "import json;print('\n'.join(json.load(open('docs/backend/openapi_v0.1.json',encoding='utf-8'))['paths']))"
```
