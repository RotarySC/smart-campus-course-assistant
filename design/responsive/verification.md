# 方向 B 响应式原型 · 独立验证报告（task-4）

- **验证者**：`rb-verifier`（独立于三个片段的作者与组装者）
- **验证时间**：2026-10-23
- **被验收冻结点**（MD5 全部复核一致，见 §0）
- **验证方式**：真实渲染（本机 Edge via CDP Proxy `http://localhost:3456`）+ 同源 iframe 精确宽度探针 + 9 张截图人工目视 + 静态契约分析
- **本文件结构**：§0–§7 为 **2026-10-23 第 1 轮（首次验证，冻结点 6AA14702…）**；文末 **「增量复验（第 2 轮）」** 为 M1 / M2 修复后的复验（冻结点 1DD81EAB…）。**两轮结论冲突时以第 2 轮为准。**
- **唯一写入**：本文件。**未修改任何被验收文件**（rb.css / b-responsive.html / build.py / parts/*.html 全程只读）

---

## 0. 冻结点复核

```
Get-FileHash -Algorithm MD5 <file>
```

| 文件 | Lead 声明 MD5 | 我实测 MD5 | 一致 |
| --- | --- | --- | --- |
| `design/responsive/rb.css` | CD00A18ED6E6D9CF35B408FA7F65DFA0 | CD00A18ED6E6D9CF35B408FA7F65DFA0 | ✅ |
| `design/responsive/b-responsive.html` | 6AA14702FB3FFB9A7F3FEB84DB1D9DF7 | 6AA14702FB3FFB9A7F3FEB84DB1D9DF7 | ✅ |
| `design/responsive/build.py` | 266D89BC92ECCA599FCA447C33AF6A58 | 266D89BC92ECCA599FCA447C33AF6A58 | ✅ |
| `parts/login.html` | 85EE3572452B0BAAB3A46844607C0E64 | 85EE3572452B0BAAB3A46844607C0E64 | ✅ |
| `parts/assistant.html` | 045A2DD2786F42D42BA38E811EB23BFC | 045A2DD2786F42D42BA38E811EB23BFC | ✅ |
| `parts/records.html` | 65A93462A08C40E0AC64CE8069853CF4 | 65A93462A08C40E0AC64CE8069853CF4 | ✅ |
| `parts/admin.html` | F09525E06851037A90633BC175EFB444 | F09525E06851037A90633BC175EFB444 | ✅ |

页面标题 `校园课程智能助手 · 方向 B 响应式原型`；`document.readyState === complete`；12 个 `.view`（`v-S01`…`v-S12`）。

---

## 1. 结论摘要

| # | 验证项 | 结论 |
| --- | --- | --- |
| 1 | 真实重排（六宽度页面级横向溢出 = 0，越界元素扫描） | **PASS** |
| 2 | 导航换形态（<768 底部标签栏 / ≥768 顶栏内联） | **PASS** |
| 3 | 表格 → 卡片（含 `data-label` 齐全） | **PARTIAL** —— 形态与标签全 PASS，但卡片内**多子元素单元格错槽**（见 M1） |
| 4 | 触控目标 ≥44 / `.tabbar__item` ≥56 | **PASS** |
| 5 | 文案保真（content-spec 逐字） | **PASS**（93 条期望文案 0 缺失） |
| 6 | 无障碍 | **PARTIAL** —— 控件命名 / SVG / focus-visible 规则 / 无 emoji 全 PASS；**缺 `<h1>`**（见 M2），焦点环目视证据不足（见 §6.4） |
| 7 | 自包含（零子资源） | **PASS** |
| 8 | 视觉确认（390 / 1366 + 390 表格卡片逐块） | **PASS（有发现）** —— 6 张图逐一看过，发现 M1 / m1 / m2 |
| 9 | 契约一致性（class 定义 / 错误码白名单） | **PASS** |

**核心验收点结论：320 / 390 / 768 / 1024 / 1366 / 1440 六个宽度下 `documentElement.scrollWidth − clientWidth` 全部为 0，越界元素 0 个。页面级横向滚动为 0 —— 我独立复现，与 Lead 一致。**
`<768` 确实变成底部标签栏 + 表格卡片化，`≥768` 恢复顶栏内联导航 + 表格形态。

**必修 2 项**（M1 卡片内文字被压进 97.5px 的标签列；M2 全页无 h1），**建议 3 项**。M1 是纯数值检查抓不到、必须看图才能发现的缺陷。

---

## 2. 逐项证据

### 探针与命令（可复现）

被验收页面经静态服务器访问：`http://127.0.0.1:8791/design/responsive/b-responsive.html`（`python -m http.server 8791 --bind 127.0.0.1 --directory "<项目根>"`）。
自建 tab（未触碰任何用户已有 tab）：

```bash
# 自建 tab
node cdp.mjs new "http://127.0.0.1:8791/design/responsive/b-responsive.html"
# 注入探针后跑六宽度矩阵（同源 iframe，见下）
node cdp.mjs run <TAB> probe.js run-inspect.js inspect.json
# 截图（需先 Page.bringToFront，否则 Page.captureScreenshot 在后台 tab 超时）
node cdp.mjs shot <TAB> raw.png && node crop-png.mjs raw.png out.png <x> <y> <w> <h> <scale> <dpr>
```

**固定宽度方法**：在页面内插入**同源 iframe**（`iframe.style.width='320px'` … `'1440px'`），读 `iframe.contentDocument.documentElement`。为让测量宽度精确等于目标断点，探针在 iframe 内注入 `html{scrollbar-width:none}`，使 `clientWidth` 与请求宽度**逐像素相等**（实测 320/390/768/1024/1366/1440 六者 `clientWidth` 均等于请求值，偏差 0）。页面 DPR = 1.5，窗口 CSS 视口 1272×502，故截图后按 1.5 倍比裁剪。

### 1. 真实重排 —— **PASS**

| 宽度 | clientWidth | scrollWidth | scrollWidth−clientWidth | 越界元素（排除被 `overflow-x` 祖先裁剪） | 合法裁剪数 |
| --- | --- | --- | --- | --- | --- |
| 320 | 320 | 320 | **0** | 0 | 0 |
| 390 | 390 | 390 | **0** | 0 | 0 |
| 768 | 768 | 768 | **0** | 0 | 10 |
| 1024 | 1024 | 1024 | **0** | 0 | 0 |
| 1366 | 1366 | 1366 | **0** | 0 | 0 |
| 1440 | 1440 | 1440 | **0** | 0 | 0 |

越界扫描口径：遍历 `body *`，凡 `getBoundingClientRect().right − clientWidth > 1` 即候选；凡该元素自身 `scrollWidth > clientWidth`（`overflow-x:auto` 容器）或存在 `overflow-x ∈ {auto,hidden,scroll}` 的祖先（逐级走到 `<html>` 为止）则计入"合法裁剪"，不计为缺陷。六宽度下"无合法裁剪路径的越界元素"均为 0。768 的 10 个合法裁剪项全部属于 `.table--stack` 卡片化前的 `.table-wrap{overflow-x:auto}` 内部（见 §3 的 S09）。

`body.scrollWidth` 六宽度均等于 `clientWidth`，无隐藏的次级滚动源。

### 2. 导航换形态 —— **PASS**

`getComputedStyle` 实测：

| 宽度 | `.appbar__nav` display | `.tabbar` display | `.tabbar` rect | `body` padding-bottom |
| --- | --- | --- | --- | --- |
| 320 | `none` | `grid` | 320×56.7，`position:fixed`，底边贴 320 视口底 | 56px |
| 390 | `none` | `grid` | 390×56.7 | 56px |
| 768 | `flex` | `none` | 0×0 | 0px |
| 1024 | `flex` | `none` | 0×0 | 0px |
| 1366 | `flex` | `none` | 0×0 | 0px |
| 1440 | `flex` | `none` | 0×0 | 0px |

断点边界精确复测（`__frameAt`）：

| 宽度 | nav | tabbar | `.table--stack thead` | `tbody tr` | caption | body padding-bottom |
| --- | --- | --- | --- | --- | --- | --- |
| 767 | `none` | `grid` | `table-header-group` | `table-row` | `table-caption` | 56px |
| 768 | `flex` | `none` | `table-header-group` | `table-row` | `table-caption` | 0px |

即断点严格落在 768：767 仍是卡片 + 底部标签栏，768 起是表格 + 顶栏内联导航。390 下 `.tabbar` 顶边 787.3 / 底边 844（`innerHeight` 844），说明底部标签栏真实吸附在视口底部，未被 `body` 的占位内边距顶出屏幕；`.composer` 为 `position:sticky; bottom:56px`，正确叠在标签栏之上。

### 3. 表格 → 卡片 —— **PARTIAL**

`<768`（以 320 / 390 实测，两宽度结论一致）：

| 视图 | `thead` display | `td` display | `tr` display | `.table-wrap` overflow-x | wrap 内可滚 | `td` 总数 | 缺 `data-label` | 空文本 `td` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v-S07 | `none` | `grid` | `block` | `visible` | 0 | 6 | 0 | 0 |
| v-S09 | `none` | `grid`(name 单元格 `block`) | `block` | `visible` | 0 | 10 | 0 | 0 |
| v-S10 | `none` | `grid` | `block` | `visible` | 0 | 10 | 0 | 0 |
| v-S11 | `none` | `grid`(name 单元格 `block`) | `block` | `visible` | 0 | 30 | 0 | 0 |

`data-label` **4 个表 × 56 个 `td` 全部齐全，缺 0 个，空文本 0 个**。`≥768`（768 / 1024 / 1366 / 1440）`thead` 回到 `table-header-group`、`td` 回到 `table-cell`、`tr` 回到 `table-row`、`.table-wrap` 回到 `overflow-x:auto`。

卡片模式下页面级横向溢出仍为 0；`.num{white-space:nowrap}` 在窄屏被 `white-space:normal` 覆盖、`.cell-name{min-width:0}`、`grid-template-columns:7.5em minmax(0,1fr)` 均已生效（实测 320 最窄卡片单元格宽 210.7px，值列 101.2px，未被压成 1 字符）。

**扣分点**：卡片内**一个 `td` 含多个子元素时，第二个子元素会被排进"标签列"槽位**，而不是接在值列下方 → 见 §7 **M1**。

### 4. 触控目标 —— **PASS**

`getBoundingClientRect().height` 最小值：

| 宽度 | `.btn`（n=57） | `.tabbar__item`（n=4） | `a.chip` | `.input/.select/.textarea`（n=25） |
| --- | --- | --- | --- | --- |
| 320 | **44.0** | **56.0** | 页面无 `a.chip` 实例 | 44.0 |
| 390 | **44.0** | **56.0** | 页面无 `a.chip` 实例 | 44.0 |
| 768 | 44.0 | `display:none`（不计） | — | 44.0 |

要求为 `.btn` / `a.chip` ≥44、`.tabbar__item` ≥56，均满足，且全部 57 个按钮**无一低于 44px**（不是只看最小值，是取全体最小值）。`.chip` 类在 `rb.css` 有定义但片段未实际使用，故无实例可测（记为"未使用"而非 FAIL，见 §9）。`.navlink` 最小高度 44px（320 下为 0，因为该元素 `display:none`）。

### 5. 文案保真 —— **PASS**

把 content-spec 的关键文案写成 13 组 93 条期望串（`expect.json`），对页面 **390 宽度下的 `body.innerText` + `body.textContent`（12,938 字符，覆盖 `sr-only` 与 `aria-hidden` 内的文字）** 做归一化逐字包含比对：
归一化仅处理排版噪声：`NBSP→空格`、各类破折号/连字符统一为 `-`、`→` 记作 `->`、`…` 记作 `...`、空白折叠，以及**行内元素边界插入的、位于全角括号前的空格**（如 `…500 字。 〔资料 1〕`）—— 不算文案漂移。

结果：**13 组全部 PASS，0 条缺失**。含题目点名的 S05 / S08 / S11：

- s05（5/5）：`已检索共享资料，但没有找到足以回答这项要求的内容。` / `课程资料暂时无法查询，请稍后重试。` / `管理员还没有上传可检索的课程资料。` / `换个问法` / `联系管理员补充材料`
- s08（4/4）：`2026-10-22（周四）没有课程安排。` / `课表数据暂时无法读取，这不代表当天没有课。` / `换个日期` / `重试`
- s11（6/6）：`本批 1 个文件失败，整批未发布；其他批次不受影响。` / `未提取到文字，可能是扫描件；本期不支持 OCR。` / `重试清理` / `整批可见或整批不可见` / `TXT / MD / 含文字层的 PDF / DOCX；单文件 ≤ 20 MiB；单批 ≤ 10 个、合计 ≤ 50 MiB` / `预览抽取文本`
- s11_status（5/5）：`可检索` / `处理中` / `失败` / `删除中` / `删除失败`
- 其余 s01/s02/s03/s04/s06/s07/s09/s10/s12 全部 0 缺失（含 `plan_7Q2F9K`、`〔资料 1〕`、S07 两条课时、S09 的 409 文案与删除确认、S12 的重叠与重复文案）

一处需要说明的**非缺陷**：S04 的回答原文 `…不少于 500 字。〔资料 1〕` 在 DOM 中 `。` 与 `〔资料 1〕` 分属两个行内元素，`innerText` 因此插入一个空格（首个断言在字符级 diff 中于第 63 字符失配）。这是行内元素边界产物，正文文本节点本身逐字一致 —— 我按"非文案漂移"处理，并在上方归一化中显式记录该规则。

### 6. 无障碍 —— **PARTIAL**

**6.1 表单控件可访问名称 —— PASS**
30 个 `input/select/textarea`：**30/30 具名**（其中 `label[for]` 显式关联 30 个，`aria-label` 0 个，`<label>` 包裹 0 个），**无名称 0 个**，**仅靠 placeholder 的 0 个**，30 个 `<label>` 全部可见（无一被 `.sr-only` 隐藏，`labelsTotal=30, labelsSrOnly=0`）。只读态 2 个、禁用态 2 个，与"只读 vs 禁用视觉可分"的要求配合见 §9。

**6.2 装饰性 SVG —— PASS**
121 个 `<svg>`：自身带 `aria-hidden="true"` 116 个 + 由祖先 `[aria-hidden="true"]` 覆盖 5 个 = **121/121 全部对辅助技术隐藏，0 个裸露**（那 5 个是 `login.html` 里的图标，被父级 `aria-hidden` 覆盖）。`fill` 非 `none` 的 0 个；`stroke-width` 取值集合仅 `{1.75}`；`viewBox` 取值集合仅 `{0 0 24 24}` —— 与"Lucide 24×24 / 1.75 / fill:none / currentColor"契约一致。

**6.3 `:focus-visible` 样式存在 —— PASS**
样式表中确有规则：`:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; border-radius: 4px; }`（`--focus: var(--c-green-900) = #0F4A42`），3px > 2px 要求。CSSOM 层确认，非 grep。

**6.4 焦点环的真实渲染 —— UNKNOWN（证据不足，不放宽也不判失败）**
在 iframe 内对 `#v-S01 .btn--primary`（"登录"）调用 `.focus()` 后取截图 `/tmp…/v390-focus.png`：**图上未见焦点环**；`getComputedStyle` 读到 `outline-style:none`。原因无法在 iframe 环境下判定：Chromium 对**程序化 `focus()` 通常不触发 `:focus-visible`**，且 iframe 非聚焦文档时 `:focus-visible` 匹配本就受限。因此我**不能**据此判失败，也**不能**判通过 —— 记为 UNKNOWN，需在顶层 tab 用真实 Tab 键走查（见 §8 未验证项）。规则本身存在且规格合规（6.3 PASS）。

**6.5 无 emoji 作图标 —— PASS**
全页文本节点扫描命中的 3 处"疑似 emoji"全部是 **U+2192（→）箭头字符**，出现在 `.view__cap`/正文文案里当分隔符用（`助手 · 草稿未保存 → 保存成功 / 结果待确认`、`2026-10-22 → 2026-10-24`），**不是图标**。图标位 100% 由内联 SVG 承担，`0` 处图形性 emoji。

**6.6 扣分点：缺 `<h1>`** —— 见 §7 **M2**。

### 7. 自包含 —— **PASS**

`performance.getEntriesByType('resource')` 在 **320 / 390 / 768 / 1024 / 1366 / 1440 六个宽度下均为 `[]`（length 0）**。这是比 grep 更强的证据：连内联 `<style>` 被解析也不产生 resource entry，说明**零子资源、零外部请求**。

旁证：`document.querySelectorAll('script')` = 1 个，`src` 为 `null`（纯内联 966 字符）；`document.querySelectorAll('link')` **= 0**；唯一的 `<style>` 元素的 `media` 属性为空字符串（**无 `media="print"`**，不存在"只在打印时才应用"的样式分支）；片段中 `<style>` / `@media` / 外部 `src|href` 均为 0。

### 8. 视觉确认 —— **PASS（有发现）**

**这一项只能靠看。** 我实际看了以下 9 张截图（全部由我自建 tab 截图 → 按 DPR 1.5 裁剪；为避免后台 tab 里 `Page.captureScreenshot` 超时，取图前用 `Page.bringToFront` 激活我自己的 tab）：

| 截图 | 内容 | 我看到了什么 |
| --- | --- | --- |
| `v390-top.png` | 390 顶屏 + `.appbar` | 顶栏只有品牌 + "管理员"胶囊，**无内联导航**；S00 说明卡 4 条自适应换行正常；S01 标题与说明未裁切 |
| `v1366-top.png` | 1366 顶屏 + `.appbar` | 顶栏内联导航 4 项 + `aria-current="page"` 高亮"课程助手"；内容居中限宽 ~880px，两侧留白正常，无重叠 |
| `v390-v-S07.png` | 390 · S07 卡片 | 日期导航 `‹ 2026-10-22 周四 ›` + 「今天」正常；卡片内 `时间  08:00–09:40` **标签左、值右正确对齐**；`课程`/`地点` 顺次成块 |
| `v390-v-S09.png` | 390 · S09 | 搜索框有可见 label「按标题筛选」；「新建计划」主按钮渲染完整；列表 caption 换行正常（非竖排） |
| `v390-s10table.png` | 390 · S10 表格卡片 | 列名与值对齐，状态胶囊"启用/已停用"带图标 |
| `v390-s11table.png` / `v390-s11m.png` / `v390-s11fail.png` | 390 · S11 五态卡片 | 「文件」标题字号更大、`原名：…` 小字成块；`类型/大小/上传时间` 标签与值**对齐正确**；5 种状态图标 + 文字 + 颜色三重表达均可辨；失败态无完成勾 |
| `v390-focus.png` | 390 · S01 焦点态 | 见 §6.4（焦点环目视不可见，原因未定论） |

**从图上看到的问题**（数值探针当时全部报 0 溢出）：

1. **S11「状态」列描述文字被压进 97.5px 的标签列**（M1，必修）。`v390-s11m.png` / `v390-s11fail.png` 上肉眼可见：`解析与向量化进行中 · 42%（最长 60 秒）`、`原因：未提取到文字，可能是扫描件；本期不支持 OCR。`、`清理未完成；不会因此恢复可见性。` 都挤成 3–4 行、每行 6–8 个字，且**与上方胶囊左边缘不对齐**（胶囊占值列 208.5px，描述却占标签列 97.5px）。
2. **S09 列表 caption 在 390 下 3 行、字号偏小**（正常，非缺陷；仅记录"我没有看出竖排/压塌"这一正向结论）。
3. **S09「新建计划」按钮在窄屏右对齐、与下方 caption 间距偏紧**（m1，建议）。
4. 未发现元素重叠、文字被裁、卡片错位；未发现列被压塌成每行一字（Lead 报告的 caption 竖排缺陷在冻结点上**已不可复现**，见 §10）。

### 9. 契约一致性 —— **PASS**

**class 定义**：四个片段（含 `login.html`）抛出的 class 共 **104 个**，`rb.css` 定义 **121 个** → **未定义 class = 0**（`undefinedClasses: []`）。片段卫生检查：`<style>` 标签 0、`@media` 0、`<html>/<head>/<body>` 0、外部 `src|href` 0、`<script>` 0、裸 hex 0、emoji 0。表单控件与可见 `<label>` 计数逐文件配平（assistant 4/4、records 7/7、admin 13/13、login 6/6）。

**rb.css 中定义但未被片段使用**的 6 个 class：`chip`、`draft--saved`、`notice--evidence`、`pill--pending`、`prose`、`r`。这**不是**任务书要求判 FAIL 的方向（任务书只对"片段用到但 rb.css 未定义"记 FAIL），但对"契约瘦身"有意义 → 列入 §7 建议 m3。

**业务错误码**：白名单我独立构建为 **35 个** = SRS §8 表格的 29 个 HTTP 错误码 + 同段落列出的 6 个异步 `task_error_code`（`NO_TEXT_EXTRACTED` / `DOCUMENT_ENCRYPTED` / `PARSE_FAILED` / `EMBEDDING_FAILED` / `CLEANUP_FAILED` / `SERVICE_RESTARTED`）。与 `docs/backend/openapi_v0.1.json` 交叉核对：**openapi 的 29 个码 100% 落在白名单内，白名单多出的 6 个正是 SRS §8 的异步码**（openapi 里没有，属预期）。

- 页面文本中形如"大写+下划线"的 token 全量扫描结果（含 `sr-only` / `aria-hidden` 内文字）只有：`DOCX`、`HTTP`、`WCAG`、`FFFFFF`。其中后三者出现在技术说明文字里、`FFFFFF` 来自 CSS 值，**均非业务错误码**。
- 片段层扫描命中的 `HTTP`（assistant / records）与 `DOCX`（admin）同理，是技术名词。
- **自造业务错误码 = 0**；白名单内码在页面上的实际出现数 = 0（页面用中文自然语言描述状态，未暴露机器码），因此这一项是"**不违规**"而非"覆盖到"。这与任务书要求（"不得出现自造码"）一致。

> 任务书括注的"允许集合 36 个"与我从 SRS §8 + openapi 独立数出的 **35 个** 差 1；我按可追溯的一手来源取 35 并在此显式记录这个分歧（见 §10.4）。

---

## 3. 必修问题

### M1（高）卡片化后，含多个子元素的 `td` 会把第 2 个子元素排进"标签列"

- **现象**：`<768` 时 `.table--stack td{display:grid;grid-template-columns:7.5em minmax(0,1fr)}` 把每个 `td` 变成"标签 + 值"两列网格。当 `td` 内有 **≥2 个子元素**时，第 1 个进值列（正确），**第 2 个落进下一个网格槽位——即标签列**，宽度只剩标签列宽。
- **实测（390）**：`#v-S11` 「状态」单元格宽 318px，`grid-template-columns: 97.5px 208.5px`；
  - 子元素 1：`span.pill` 宽 **208.5px**（值列，正确）
  - 子元素 2：`p.small` 宽 **97.5px**（落到标签列）
  受影响行：处理中、失败、删除中、删除失败（4/5 个文档行）；320 下同样成立。
- **后果**：`原因：未提取到文字，可能是扫描件；本期不支持 OCR。`（28 字）在 97.5px 里折成 4 行、每行 6–8 字，与上方胶囊左边缘**不对齐**；页面级溢出仍为 0，所以**任何数值溢出检查都抓不到**。这是一处真实可读性缺陷，不是审美偏好。
- **最小修复建议（不动 `rb.css` 也可做）**：让"多子元素单元格"在 markup 层合并成单个子元素，例如把描述文字放进与胶囊同一个容器：
  `<td data-label="状态"><span class="stack" style="display:flex;flex-direction:column;gap:6px"> … </span></td>`。
  若允许改 `rb.css`，最小改动是给这类单元格一个"跨两列并纵向堆叠"的规则，例如
  `.table--stack td[data-multi]{display:flex;flex-direction:column;gap:var(--sp-1)}`
  （配合 `td::before` 仍作标签）。两种改法都不影响 ≥768 的表格形态。
- **注意**：`td.cell-name`（`.table--stack td.cell-name{display:block}`）**不受影响** —— 它的多个子元素正常纵向堆叠（实测 320/390/768 均为 `display:block`，子元素宽 136.4 / 248 等，正常）。所以**修法不要动 `.cell-name`**。

### M2（中）全页没有任何 `<h1>`，标题层级从 h2 起

- **实测**：`h1 = 0`、`h2 = 12`、`h3 = 24`、`h4 = 3`。`<title>` 存在、`main` 地标存在、`lang="zh-CN"` 存在。
- **依据**：content-spec §1 硬要求「语义结构：标题层级不跳级」。页面最高层级是 h2，文档大纲缺少一级标题，屏幕阅读器用户按标题导航时没有页面主标题。
- **最小修复建议**：在 `shell.html` 的 `.appbar__brand`（或 `main` 开头）加一个 `<h1>`；若不想改变视觉，可用 `<h1 class="sr-only">校园课程智能助手 · 方向 B 响应式原型</h1>`（`.sr-only` 已在 `rb.css` 定义），并把现有 12 个 `h2` 保持不变即可（h1 → h2 不跳级）。

---

## 4. 建议改进

- **m1（低）S09「新建计划」在窄屏右对齐、与下方 caption 间距偏紧。** 390 截图可见：按钮单独占一行、右对齐，紧贴下方表格 caption。建议窄屏用 `.btn--block` 或放进 `.card__foot` 统一间距。
- **m2（低）S09 表格在 768–899px 区间会在 `.table-wrap` 内部横向滚动 25–57px。** 实测：767px → 45px、768px → **57px**、800px → 25px、900px → 0px。成因是 `.cell-name{min-width:180px}` 与 `.table thead th{white-space:nowrap}`、`.table .num{white-space:nowrap}` 叠加出的最小内容宽 738px，在 768 视口的 681px 容器里放不下。**这完全落在 `.table-wrap{overflow-x:auto}` 内部，页面级溢出仍为 0**（越界元素扫描把它正确归入"合法裁剪"）。是否接受见 §10.2。
- **m3（低）`rb.css` 中 6 个 class 定义了但从未使用**：`chip`、`draft--saved`、`notice--evidence`、`pill--pending`、`prose`、`r`。`a.chip` 还占着"触控目标 ≥44"的验收口，却没有实例。建议要么在片段里用上（例如示例入口用 `a.chip`），要么从契约里删掉，避免下一个方向复用时误判。

---

## 5. 我没有验证的部分

1. **焦点环的真实键盘渲染**（§6.4）。iframe 环境下程序化 `.focus()` 不触发 `:focus-visible`，无法定论；需在顶层 tab 用真实 Tab 键走查，并确认粘性 `.appbar`（`z-index:40`）不遮挡焦点轮廓。
2. **真实设备 / 真实触屏手势**。所有触控尺寸是 `getBoundingClientRect()` 的 CSS px 高度，未做真机点击、未验证 iOS `env(safe-area-inset-bottom)` 的实机表现。
3. **`prefers-reduced-motion: reduce`**。`.step--running .step__ico{animation:spin}` 与 `rb.css` 的降级规则都在静态层可见，但我没有在开启该偏好的媒体环境下实跑确认动画确实停止。
4. **对比度**（content-spec §1 要求正文 ≥4.5:1）。我没有做像素级对比度计算，只核对了"颜色来自语义 token、无裸 hex"。
5. **`<360px` 更极窄宽度**。验收只要求到 320，我未测 280 等更窄值。
6. **纵向滚动在真实窗口下的表现**（`.appbar` sticky 与锚点跳转的交互）。我是在隐藏滚动条的 iframe 里测的横向重排。
7. **错误码在运行时的真实产生路径**（页面不暴露机器码，见 §2.9）。
8. **`design/responsive/shots/` 与 `_*.js` 等 Lead 的临时文件**，按 Lead 说明不属于验收范围，我未纳入也未删除。

---

## 6. 与 Lead 结论的分歧

### 6.1 六宽度页面级溢出 = 0 —— **一致**
我独立复现：六宽度 `scrollWidth − clientWidth` 全为 0，无合法裁剪路径的越界元素 0 个。与 Lead 的数值一致。

### 6.2 320px 曾溢出 65px、caption 曾竖排 —— **两项都在冻结点上不可复现（已修好），且我验证了修复生效**
- **320 溢出**：冻结点上 320 的 `scrollWidth − clientWidth = 0`，最窄卡片单元格 210.7px、值列 101.2px。`.num` 在窄屏被 `white-space:normal` 覆盖、`.cell-name{min-width:0}`、`grid-template-columns:7.5em minmax(0,1fr)` 三项修复都实测生效。我**无法**验证"曾溢出 65px"这一历史陈述（那时的文件已被覆盖），只能确认**当前冻结版本没有这个问题**。
- **caption 竖排**：冻结点上 `<768` 的 caption 一律 `display:block` 且宽 246.7–354px、320 下每行仍可排 8–18 字（v-S07 17 字/行、v-S11 18 字/行），**没有任何 caption 退化成每行一字**。Lead 把它归因于 `display:table-caption` 的 shrink-to-fit，我同意这个根因判断，并且确认 `.table--stack caption{display:block;width:auto}` 已生效。

### 6.3 768–1024 区间 S11 六列横向滚动是否可接受 —— **我同意 Lead 的裁定，但要点名一处我与他口径不同的地方**
- **同意接受**：S11 六列在 768 只有 `0px` 内部滚动（实测 wrap 681 / scroll 681）；真正出现内部滚动的是 **S09**（768 下 57px），且**完全封闭在 `.table-wrap{overflow-x:auto}` 内**，页面级仍是 0，越界扫描正确判为"合法裁剪"。SRS NFR-COMP-001 明确允许管理端窄屏横向滚动。所以**这一条我判 PASS**，不记缺陷，只记 m2 建议。
- **但我要把风险说重一点**：这个"合法内部滚动"的豁免是**唯一**让"页面级溢出 = 0"这个核心验收点保持成立的机制。如果后续有人把 `.table-wrap` 的 `overflow-x` 去掉（窄屏 `.table-wrap--stackable` 就是这么干的），同一处会立刻变成页面级溢出。所以核心验收点虽为 PASS，**它的成立依赖一个可以被一行 CSS 推翻的前提**，建议在验收结论里显式记录这个前提。
- 另外：Lead 说"我给 `.table--stack` 加了 `overflow-x:visible`" —— 实测确认，`<768` 四个表格的 `.table-wrap` 计算值均为 `overflow-x: visible`，且内部可滚 0；而 `≥768` 回到 `auto`。

### 6.4 我发现了 Lead 报告里没有的问题（请重点复核 M1）
Lead 报告的两个缺陷（320 溢出、caption 竖排）我都确认已修；但**卡片内多子元素单元格错槽**（M1）**不在他的清单里**，而且它同样"数值检查抓不到、只有看图能发现"——这正是他让我重点找的同类。此外 **M2（无 h1）** 也未被提及。两处最小修复都在 §3。

### 6.5 白名单条数分歧
任务书括注"允许集合 36 个"，我从 SRS §8 + `openapi_v0.1.json` 一手来源数出 **35 个**（29 HTTP + 6 异步 task_error_code）。由于页面实际产出的业务错误码为 0，**这个 ±1 不影响任何判定**，但我按"不确定就标出来"的原则记录在此。若 Lead 手上有第 36 个码的出处，请指出，我会更新口径。

---

## 7. 附：证据文件清单

工作区外（`%TEMP%\dsh-Fs8H4c\rb-verify\`，非交付物、未进入仓库）：

- `inspect.json`（六宽度完整测量 + 每表 `td` 明细 + 390 全文文本）、`report.json`（13 组 93 条文案比对结果）
- `probe2.json`（全文本 token 扫描、SVG 祖先覆盖、768/1024 wrap 溢出归因、caption 几何）
- `multichild.json`（六宽度"错槽单元格"扫描）、`s11cells.json`（S11 五态单元格几何）
- `static.json`（class 定义/使用对比、错误码白名单交叉核对、片段卫生）
- 截图：`v390-top.png`、`v1366-top.png`、`v390-v-S07.png`、`v390-v-S09.png`、`v390-s10table.png`、`v390-s11table.png`、`v390-s11m.png`、`v390-s11fail.png`、`v390-focus.png`

被验收文件全程只读；本次验证**唯一写入**为 `design/responsive/verification.md`。

---

# 增量复验（第 2 轮 · 2026-10-23 · M1 / M2 修复后）

> **本轮为增量复验。** 范围经 Lead 限定为 4 项（冻结点复核、M1 已修、M2 已修、回归）。
> **其余 5 项（#4 触控目标、#5 文案保真、#6 无障碍的控件命名/SVG/emoji 子项、#7 自包含、#9 契约一致性）沿用 2026-10-23 首次验证结论，本轮未重跑。**
> **#6 的焦点环子项仍为 UNKNOWN**（详见首轮 §5 第 1 条），本轮未改变该判定。

## R0. 冻结点复核 —— 一致

> ⚠ **本节的哈希已被阶段 A（实现期）取代，仅作历史留痕，不要据它校验当前文件。**
> 阶段 A 修了 W1/W2/W3 与原型 #1/#3/#6，`rb.css` / `shell.html` / `b-responsive.html` 的字节均已变化。
> **当前冻结点**（以 [`../reviews/rb-verify-report.md`](../reviews/rb-verify-report.md) §1 为准）：
>
> | 文件 | 阶段 A 后的 MD5 |
> | --- | --- |
> | `design/responsive/rb.css` | `0749FA7A47BC155F52A12406123DF6CC` |
> | `design/responsive/shell.html` | `E8B7294B9B4A8424ACA94C17068F2F60` |
> | `design/responsive/b-responsive.html` | `5B73454136F261AC13E9A0203C0C6D73` |
>
> 另外本节及下文出现的 **74 个共同 token / 518 个 token** 均为阶段 A 之前的数值；
> 阶段 A 后为 **75 / 519**（新增 L3 `--root-scroll-offset`）。
> 本文件记录的 W1/W2/W3 结论（当时为 FAIL / 缺陷确认）**已被 `rb-verify-report.md` 取代**（6 项全 PASS）。

| 文件 | Lead 声明 MD5（新冻结点） | 我实测 MD5 | 一致 | 与首轮相比 |
| --- | --- | --- | --- | --- |
| `design/responsive/rb.css` | 94DF48EDFFC1DC33858A545C3574048F | 94DF48EDFFC1DC33858A545C3574048F | ✅ | **已变**（M1） |
| `design/responsive/shell.html` | 0E2C4FFFBFF4C9999D98BD7747E5568A | 0E2C4FFFBFF4C9999D98BD7747E5568A | ✅ | **已变**（M2） |
| `design/responsive/b-responsive.html` | 1DD81EAB2A90797AB01F4CEB0A645A17 | 1DD81EAB2A90797AB01F4CEB0A645A17 | ✅ | **已变**（产物） |
| `parts/login.html` | 85EE3572452B0BAAB3A46844607C0E64 | 85EE3572452B0BAAB3A46844607C0E64 | ✅ | 未变 |
| `parts/assistant.html` | 045A2DD2786F42D42BA38E811EB23BFC | 045A2DD2786F42D42BA38E811EB23BFC | ✅ | 未变 |
| `parts/records.html` | 65A93462A08C40E0AC64CE8069853CF4 | 65A93462A08C40E0AC64CE8069853CF4 | ✅ | 未变 |
| `parts/admin.html` | F09525E06851037A90633BC175EFB444 | F09525E06851037A90633BC175EFB444 | ✅ | 未变 |

**7/7 一致**。产物一致性另做两层核对（防止"源改了但产物没重建"）：

- `b-responsive.html`（9:49:04）**晚于** `rb.css` / `shell.html`（9:45:34），时间序正确；
- 直接在产物原文里确认两处修复都已内联：`.table--stack td > *{grid-column:2}` = 存在；`<h1 class="sr-only">` = 存在（`<h1` 计数 = 1，`<style` 计数 = 2）。

## R1. M1（卡片内多子元素单元格错槽）—— **已修**

`.table--stack td > *{grid-column:2}` 位于 `rb.css` 的 `max-width:767px` 块内、带完整注释，`::before` 仍占第 1 列。

**实测几何**（判定口径：卡片单元格内所有真实子元素的 `left` 必须相同，且左边缘落在**值列**范围内）
值列左边界 = `td.left + padding-left + 标签列宽 + column-gap`；值列右边界 = `td.right − padding-right`。

| 宽度 | 视图 / 列 | `td` 宽 | `grid-template-columns` | 值列范围 | 子元素 `left` | 子元素宽 | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **390** | v-S11 · 状态(失败) | 318 | `97.5px 208.5px` | [145.5, 354] | **145.5 / 145.5** | **208.5 / 208.5** | PASS |
| 390 | v-S11 · 状态(处理中/删除中/删除失败) | 318 | `97.5px 208.5px` | [145.5, 354] | 145.5 / 145.5 | 208.5 / 208.5 | PASS |
| **320** | v-S11 · 状态(失败) | 248 | `97.5px 138.5px` | [145.5, 284] | **145.5 / 145.5** | **138.5 / 138.5** | PASS |
| 320 | v-S11 · 状态(其余 3 态) | 248 | `97.5px 138.5px` | [145.5, 284] | 145.5 / 145.5 | 138.5 / 138.5 | PASS |
| 360 / 480 | v-S11 · 状态(5 态) | 288 / 408 | `97.5px 178.5px` / `97.5px 298.5px` | 值列同步变宽 | 各态均相同 | 各态均相同 | PASS |

**修复前后对比（390 · v-S11 · 状态单元格）**：

| | 第 1 子元素 `span.pill` | 第 2 子元素 `p.small` |
| --- | --- | --- |
| 首轮（修复前） | left 145.5 / 宽 **208.5**（值列 ✅） | left **47.5** / 宽 **97.5**（落进标签列 ❌） |
| 本轮（修复后） | left 145.5 / 宽 208.5（值列 ✅） | left **145.5** / 宽 **208.5**（值列 ✅） |

**全表扫描（本轮最关键的回归面）**：`.table--stack td > *` 是**全局窄屏规则**，我扫了 **S07 / S09 / S10 / S11 全部 4 张 stack 表**，在 320 / 360 / 390 / 480 / 767 五个宽度下枚举每个"含 ≥2 个子元素"的卡片单元格：

- **多子元素单元格总数 = 9，全部落在 `v-S11`**（4 个「文件」+ 5 个「状态」）。
- **S07 / S09 / S10 一张都没有多子元素单元格** —— 它们的卡片单元格是纯文本或单子元素，这条新规则**对它们没有任何作用面**，不存在"被改坏"的可能。
- 9 个单元格 × 5 个宽度 = **45 个观测点，problems = 0**。
- `.cell-name`（`display:block`，不走网格）实测：320/390/480 下两个子元素 `left` 均相同（36 / 36），宽 211.9–285.4 与 248–408，**未被这条规则影响**，与首轮一致。
- `≥768` 表格形态下该规则不生效（在 `max-width:767px` 块内），实测 768/1024/1366/1440 各子元素 `left` 也相同。

**看图确认**（`r-390fail-crop.png`、`r-320fail2-crop.png`）：

- 390：`清理未完成；不会因此恢复可见性。` 现为**单行**，左边缘与上方 `删除失败` 胶囊**严格对齐**在值列起点（修复前是 97.5px 内 3 行、左边缘缩进到标签列）。
- 320：`原因：未提取到文字，可能是扫描件；本期不支持 OCR。` 在 138.5px 值列内折 3 行，**每行左边缘与胶囊对齐**；标签「状态」在第 1 列、值在第 2 列，不再出现"标签列里塞正文"。

> **一处我要更正自己**：我第一版自动判据写成"子元素 `left − td.left` ≥ 标签列宽即判失败"，这是**错的** —— 值列本身就从标签列之后开始，390 下 `left − td.left = 97.5` 在旧 CSS 里也是正常的。该判据把**已修复的 4 个正确单元格误报为 FLAGGED 4**。改用"值列绝对边界 + 子元素 `left` 一致性"后重扫，结果为 0 问题。保留这段说明，因为"判据本身写错"比"缺陷被漏报"更值得记录。

## R2. M2（全页无 `<h1>`）—— **已修**

| 检查 | 实测 | 判定 |
| --- | --- | --- |
| `h1` 数量 | **1** | PASS |
| `h1` 文本 | `校园课程智能助手 · 方向 B 响应式原型` | PASS |
| `h1` 位置 | `main` 的直接子元素（首个） | PASS |
| 标题层级序列 | `H1 → H2 → H3 → H3 …` | PASS |
| **跳级（level jump > 1）** | **0 处**（共 40 个标题，逐对检查） | PASS |
| 各级计数 | h1=1 / h2=12 / h3=24 / h4=3 | — |
| 是否干扰布局 | `.sr-only` 生效：1×1px、`position:absolute`、`clip:rect(0,0,0,0)`、`overflow:hidden`，**不影响视觉** | PASS |
| `.appbar` 高度 | 320/390/768/1366 均 56.7px（与首轮一致，未被 h1 顶开） | PASS |
| `.tabbar__item` 高度 | 320/390 = **56px**（与首轮一致） | PASS |

`h1 → h2` 不跳级已确认；content-spec §1「标题层级不跳级」达成。

## R3. 回归 —— 六宽度全部保持

| 宽度 | `clientWidth` | `scrollWidth` | **页面级溢出** | `body` 溢出 | `nav` | `tabbar` | `thead` | `tr` | `td` 数 / 缺 `data-label` | 外部资源 | 越界元素（排除合法裁剪） |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 320 | 320 | 320 | **0** | 0 | `none` | `grid` | `none` | `block` | 56 / **0** | **0** | **0** |
| 390 | 390 | 390 | **0** | 0 | `none` | `grid` | `none` | `block` | 56 / **0** | **0** | **0** |
| 768 | 768 | 768 | **0** | 0 | `flex` | `none` | `table-header-group` | `table-row` | 56 / **0** | **0** | **0** |
| 1024 | 1024 | 1024 | **0** | 0 | `flex` | `none` | `table-header-group` | `table-row` | 56 / **0** | **0** | **0** |
| 1366 | 1366 | 1366 | **0** | 0 | `flex` | `none` | `table-header-group` | `table-row` | 56 / **0** | **0** | **0** |
| 1440 | 1440 | 1440 | **0** | 0 | `flex` | `none` | `table-header-group` | `table-row` | 56 / **0** | **0** | **0** |

- `.table-wrap` 的 `overflow-x`：`<768` 全为 `visible`、`≥768` 全为 `auto`；内部可滚 `<768` 全 0，`≥768` 仅 **S09 在 768 = 57px**（与首轮完全一致，属首轮 §6.3 已接受的合法内滚，位置归因仍为 **S09**）。
- caption `display`：`<768` 全 `block`、`≥768` 全 `table-caption`（回归通过，未回退到首轮前的竖排缺陷）。
- 四张表的 `tableW` 与首轮对比：320 / 390 / 768 / 1024 分别 246.7 / 316.7 / 681.3–737.5 / 718.7–793.3，**与首轮逐项相差 ≤0.3px（亚像素舍入）**，无几何回归。

## R4. 本轮附带复核（因文件已变，顺手确认首轮结论未被破坏）

- **契约一致性（首轮 #9）**：`rb.css` 已变，故重跑静态分析 —— 片段抛出 class **104** 个 / `rb.css` 定义 **121** 个 → **未定义 class = 0**；裸 hex = 0；自造业务错误码 = **0**（文本 token 仍只有 `HTTP` / `DOCX` / `WCAG` / `FFFFFF`，均非业务错误码）。**首轮结论保持 PASS。**
- **自包含（首轮 #7）**：六宽度 `performance.getEntriesByType('resource').length` 全为 **0**（见 R3 表）。**首轮结论保持 PASS。**

## R5. 增量复验结论

| 项目 | 结论 |
| --- | --- |
| R0 冻结点 | **PASS**（7/7 一致 + 产物确实包含两处修复） |
| R1 M1 已修 | **PASS**（45 个观测点 0 问题；390/320 看图确认折行与左边缘对齐；S07/S09/S10 无作用面） |
| R2 M2 已修 | **PASS**（h1=1，跳级 0，不干扰布局） |
| R3 回归 | **PASS**（六宽度溢出 0；nav/tab/thead/tr 切换正确；缺 `data-label` 0；外部资源 0） |

**首轮 2 项必修（M1 / M2）全部关闭。** 首轮结论相应更新为：

- #3 表格 → 卡片：**PARTIAL → PASS**（多子元素单元格错槽已修）。
- #6 无障碍：**PARTIAL → PASS**（缺 `<h1>` 已修；**焦点环子项仍为 UNKNOWN**，不计入 PASS）。
- #1 / #2 / #4 / #5 / #7 / #8 / #9 保持首轮 **PASS**。
- 首轮「建议改进」三条（S09「新建计划」按钮位置、S09 在 767–899px 的 25–57px 内部滚动、`rb.css` 6 个未使用 class）**本轮未处理**，仍在有效状态。
- 首轮「与 Lead 的分歧」四条（六宽度一致 / 320 与 caption 历史缺陷不可复现 / S11 内滚裁定与"S09 才是真正内滚位置" / 错误码 35 个）**均已由 Lead 接受并更正认知**，无新增分歧。

## R6. 本轮未验证

沿用首轮 §5 未验证清单（真实键盘焦点环、真机触屏、`prefers-reduced-motion` 实跑、像素级对比度、<360px 极窄宽度、真实窗口下 sticky 交互、错误码运行时产生路径）。本轮**新增**两点未覆盖：

1. **多子元素单元格只在 320 / 360 / 390 / 480 / 767 五个宽度逐态枚举**；`768–1440` 只验证了"该规则不生效 + 子元素 `left` 一致"，未逐态枚举（该区间是表格形态，本就不受此规则影响）。
2. **未在真实窗口（非 iframe）下复核 M1**。若真实浏览器的 `scrollbar-gutter` / 缩放与我的测量环境不同，值列**宽度**会有差异，但"子元素 `left` 相同且落在值列内"这一结构性质与容器宽度无关。

## R7. 本轮证据文件

- `recheck.json`（多子元素扫描 / 标题层级 / 六宽度回归 / 越界扫描）
- `recheck2.json`（修正判据后的值列边界判定，覆盖 320/360/390/480/767）
- `recheck3-new.json`（六宽度表几何快照，与首轮 `inspect.json` 对比无回归）
- `static2.json`（新版 `rb.css` 的 class 契约复核）
- 截图：`r-390fail-crop.png`、`r-320fail2-crop.png`（均为修复后）

本轮**唯一写入**仍为 `design/responsive/verification.md`；被验收文件验证前后 MD5 未变。
