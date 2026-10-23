# 设计系统 · 独立验证报告

- **验证者**：`rb-verifier`（独立于生成器与规格作者）
- **验证时间**：2026-10-23（含 M1 修复前/后两轮）
- **唯一交付写入**：本文件。截图目录 `design/system/shots/`（评审辅助产物）
- **被验收文件全程只读**，验证前后 MD5 一致（见 §0.2）

---

## 0. 验证环境与被验字节

### 0.1 环境

| 项 | 值 |
| --- | --- |
| 浏览器 | 本机 Microsoft Edge，经 web-access CDP Proxy `http://localhost:3456` |
| 静态服务器 | `http://127.0.0.1:8793`（`python -m http.server`） |
| 定宽方法 | 页面内注入**命名同源 iframe**，`iframe{width:Npx}`；注入 `html{scrollbar-width:none}` 使 `clientWidth` 逐像素等于目标断点 |
| 截图方法 | `Page.bringToFront` → `GET /screenshot` 全窗 → 本地 PNG 解码裁剪（窗口 DPR 1.5） |
| 比对口径 | 冻结动画/transition；`b-responsive.html` 侧中和评审外壳（`.view__head`/`.proto-banner`/`.skip-link` 隐藏、`.wrap` 去上内距）使卡片几何可比 |

> **端口说明**：任务建议用 8791，但该端口当时被**5 个先前遗留的僵死 python 监听**占满且全部不响应（`curl` 返回 000）。我改用 8793 并清理了 8791 的僵死进程。属端口选择差异，不影响结论。

### 0.2 被验字节（M1 修复后，Lead 给出的新冻结点，我逐一复核一致）

| 文件 | 字节 | MD5（我实测） | 与 Lead 声明 |
| --- | --- | --- | --- |
| `tokens.css` | 29884 | `0AA235F8FC261CD2C921602D832AF4D4` | 一致 |
| `system.html` | 188869 | `347E17249D68EE6C515A247E8C89756E` | 一致 |
| `tokens.json` | 53066 | `924A6C27FB7D7BFB5DF3571D33DF34BF` | 一致 |
| `styleguide.css` | 27151 | `D3C2ADE9D5903366A17CFB845353C859` | 一致 |
| `generate.py` | 32552 | `5FB4F922C8845D8FFED33930FA3EA2B2` | 一致 |
| `verify-system.py` | 30519 | `B6EF1773D90A14260085BC4BD91BC890` | 一致 |

M1 修复前的冻结点为 `tokens.css = 64C9A513…` / `system.html = 5A93E576…`。**本报告所有结论以 §0.2 的新字节为准**，涉及 M1 的部分同时给出修复前证据。

---

## 1. 结论摘要

| # | 验证项 | 结论 | 一句话 |
| --- | --- | --- | --- |
| 1 | 计算样式等价性 | **PASS（修复后）** / 首轮 **FAIL** | 修复前 7 个共同 token 值不同、14 个签名只差颜色；修复后 `:root` 差异 **0**、共同签名 64/92 全等、剩余 28 个差异**全部归因为夹具/节点选择**，**0 个真差异** |
| 2 | 六宽度渲染 | **PASS** | 六宽度页面级溢出与 body 溢出均 0；27 组齐全未塌陷；子资源 0 |
| 3 | 人工看图 | **PASS（有发现）** | 修复前肉眼可见「白字透明底主按钮」；修复后 9 张图无错位/重叠/裁切/压塌 |
| 4 | R7 机制裁定 | **PASS —— 偶数位成立** | 删掉 `td > *{grid-column:2}` 后，**第 2、4 个**子元素落进标签列；`::before` 确实占第 1 格 |
| 5 | `.steps__toggle` 焦点可见性 | **FAIL（风险项）** | 两种页面下聚焦后 `outline-style:none` 且无任何 `:focus-visible` 替代指示；原型里该控件是 1×1 `clip` 隐藏 → WCAG 2.4.7 风险 |
| 6 | sticky 顶栏遮挡锚点 | **FAIL** | 锚点目标 `top=0.3` 而顶栏底 `56.7` → **遮挡 56.4px**；skip-link 目标 `#main` 被遮挡 **56.7px**；两套 CSS 与 token 里**都没有** `scroll-padding-top` |
| 7 | 注入长串溢出 | **缺陷存在，且已定位根因 + 已验证修法** | 320px 注入 60 字无空格串：`.cite__name` +359 / `.kv__v` +523 / `.card__body` +375 / `.bubble` +375 px |
| 8 | 对比度实测 | **PASS** | 41/41 可测且全部达标，最低 **4.74:1**（`--bg-readonly` alpha 合成后 7.0:1） |
| 9 | 规格 ↔ rb.css 一致性 | **PASS** | 524 处 `rb.css:NN` 行号引用**全部成立**；13 个「rb.css 里没有」的状态选择器全是规格**自己声明不存在/禁止新增**的 |
| 10 | 四条指控事实核查 | **四条全部属实** | 见 §10，逐条给行号 |
| 11 | 不可验证清单 | — | 见 §12 |

**必修 2 项、建议 4 项。** M1（我已报）已由 Lead 修复并经我复验关闭；本轮新提 **W1（无 `scroll-padding-top`）** 与 **W2（`.steps__toggle` 无可见焦点）**，以及 **W3（长串溢出）** 登记为实现期必修。

---

## 2. 【第 1 项】计算样式等价性

### 2.1 方法（两个改良，缺一不可）

1. **两个 iframe 同时存活**：我最初用「加载 A → 加载 B」覆盖同名 frame，导致 A 的 `contentDocument` 被回收，比对全部落空。改为 `__loadNamed("f_sys", …)` / `__loadNamed("f_rb", …)` 两个不同 id 同时挂载。
2. **按 class 签名配对，而不是「取第一个同名 class」**：后者会把 `.btn` 和 `.btn--primary` 配成一对，产生 50 个假差异（我第一版就踩了这个坑，已废弃）。签名 = 元素全部 class 排序后拼接，**只有签名完全相同的两个元素才逐属性比**。

比对属性 = **102 个样式定义类属性**（color/background/border*/padding*/margin*/font*/line-height/display/gap/grid*/overflow*/white-space/…）。刻意排除：几何量（width/height/top/left/transform-origin/perspective-origin）与全部 `--*`（继承自定义属性取决于祖先链，逐元素比无意义；它们单独在 `:root` 层比）。

### 2.2 `:root` token 层 —— 修复后 **0 差异**

| 宽度 | system 侧 | base 侧 | 共同 | **值不一致（修复前）** | **值不一致（修复后）** | base 有 system 无 |
| --- | --- | --- | --- | --- | --- | --- |
| 390 | 515 | 74 | 74 | **7** | **0** | 0 |
| 1366 | 515 | 74 | 74 | **7** | **0** | 0 |

修复前不一致的 7 个：`--accent` `--accent-strong` `--accent-tint` `--focus` `--c-green-700` `--c-green-900` `--c-green-100`（system 侧全为空）。修复后全部有值且与 `rb.css` 逐字相等。

### 2.3 class 级比对

| 宽度 | 共享签名 | 已比对 | **完全相同（修复前 → 后）** | **有差异（修复前 → 后）** | 未渲染 |
| --- | --- | --- | --- | --- | --- |
| 390 | 100 | 92 | 58 → **64** | 34 → **28** | 8 |
| 1366 | 100 | 96 | 62 → **68** | 34 → **28** | 4 |

M1 修复直接让 6 个签名的颜色差异归零：`appbar__mark`、`navlink`、`pill pill--evidence`、`cite`、`cite cite--invalid`、`btn btn--primary`（其 diff 由 7 个颜色属性降为 `opacity`/`cursor` 两项，见 §2.5）。

### 2.4 剩余 28 个差异：逐个归因，**0 个真差异**

我把每个差异签名两侧的 tag / 文本 / 父级 / 状态属性都打印出来逐条判定（脚本 `attrib.js`）。结论按类：

| 类别 | 签名 | 证据（为什么不是缺陷） |
| --- | --- | --- |
| **① 两页形态不同**（390 下 base 已卡片化，手册是表格态） | `cell-name`(15 属性)、`num`(17) | A 侧 `display:table-cell`、B 侧 `display:block`/`grid` + `grid-template-columns:127.5px minmax(0,1fr)`。这是**卡片化前后两种正确形态**，不是样式分歧 |
| **② 节点选择不同**（同签名但取到不同实例） | `wrap`、`wrap wrap--assistant`、`muted small`、`mono`、`row`、`small`、`notice__ico`、`bubble`、`composer`、`composer__count`、`sr-only`、`tabbar`、`login__name`、`login__sub` | 例：`[mono]` A 取到 `<td class="mono">`、B 取到 `<dd class="mono">`；`[bubble]` A 取到助手气泡（白底）、B 取到 `.msg--user` 气泡（accent 底）——`.msg--user .bubble` 是**另一条合法规则**；`[small]` A 在 `.wrap`（正文色）、B 在警告提示内（琥珀色）。两侧文本与父级链完全不同 |
| **③ 状态不同** | `btn btn--primary`（A 启用 / B `disabled`）、`tabbar__item`（A 无 `aria-current` / B 有） | 实测 A `opacity:1, cursor:pointer`；B `opacity:0.5, cursor:not-allowed`（B 元素带 `disabled` 属性）。这是**禁用态与启用态**的正常差异 |
| **④ 父容器 display 造成的 blockification** | `btn`、`btn btn--sm`、`btn btn--block btn--primary` | A 的父级是 `<p>`；B 的父级是 `div.row` / `div.chips` / `div.card__body.stack`（flex/grid 容器）。**flex/grid 子项会被 blockify**：`inline-flex` → `flex`。同一条 `.btn{display:inline-flex}` 声明，只是计算后 display 被父级上下文改变 |
| **⑤ 网格轨道实际宽度** | `card-row--2`、`form-grid--2`、`draft__kv`、`kv`、`kv__row` | 差异只在 `grid-template-columns/rows` 的**解析后像素值**（轨道定义一致，如 `8em 1fr`）。轨道宽度取决于容器可用宽度，而我为中和外壳改了 base 的 padding |
| **⑥ 我注入的中和样式** | `wrap`(padding-top)、`tabbar`/`composer`(position) | 我对 base 注入 `.wrap{padding-top:0}`；base 的 tabbar 是 `position:fixed` 页面级元素、手册内是静态演示块 |

**没有一条剩余差异涉及「手册缺某个 L3 token」**。反证：`tokens.json` 的 333 个 component token 在 `system.html` 中全部被消费（Lead 的 G 项我另行复现，见 §13），且 64 个签名 102 项属性逐字相同。

### 2.5 修前 vs 修后的可见差异（`.btn--primary`）

| | `background-color` | `color` |
| --- | --- | --- |
| 修复前 | **`rgba(0, 0, 0, 0)`（透明）** | `rgb(255,255,255)` |
| 修复后 | **`rgb(20, 102, 91)`** | `rgb(255, 255, 255)` |
| rb.css 基准 | `rgb(20, 102, 91)` | `rgb(255,255,255)` |

即修复前主按钮是「白字透明底」，文字几乎不可读；截图 `shots/ds-390-btn2.png` 修复后为墨绿底白字。

### 2.6 第 1 项判定

**修复后 PASS。** 「只消费 L3 就能还原 rb.css 的视觉」这一命题现在**有正面证据**：
- `:root` 74 个共同 token **逐字全等**；
- 92 个共同 class 签名中 **64 个 102 项样式属性逐字相同**（卡片、提示块、全部状态胶囊、表单控件、对话、引用、草稿、空态、表格卡片化、登录页）；
- 剩余 28 个差异**全部可归因为测试夹具/节点选择/状态差异**，不含任何 token 缺失。

**但这条命题的成立依赖 M1 已修**——首轮我判 FAIL 是对的，因为当时 30 个 token 在运行时是死的。

---

## 3. 【第 2 项】六宽度渲染 —— PASS

在新字节（`system.html 188869 B`）上复测：

| 宽度 | `clientWidth` | `scrollWidth` | **页面级溢出** | `body` 溢出 | 越界元素（排除合法裁剪） | `section[data-group]` | 塌陷 | 子资源 | `h1` | 标题总数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 320 | 320 | 320 | **0** | 0 | 0 | 27 | 0 | 0 | 1 | 63 |
| 390 | 390 | 390 | **0** | 0 | 0 | 27 | 0 | 0 | 1 | 63 |
| 768 | 768 | 768 | **0** | 0 | 0 | 27 | 0 | 0 | 1 | 63 |
| 1024 | 1024 | 1024 | **0** | 0 | 0 | 27 | 0 | 0 | 1 | 63 |
| 1366 | 1366 | 1366 | **0** | 0 | 0 | 27 | 0 | 0 | 1 | 63 |
| 1440 | 1440 | 1440 | **0** | 0 | 0 | 27 | 0 | 0 | 1 | 63 |

27 个 `data-group` 实测：`root focus skiplink sr appbar brand navlink tabbar wrap card btn pill notice chat steps composer cite draft empty field control table kv chip prose login utility`。未塌陷判据：每组高度 ≥ 20px。子资源为 `performance.getEntriesByType('resource').length`。

**一处结构事实**（影响第 6 项判定）：`system.html` 的页面级骨架是 `A.skip-link` + `HEADER.shell-head`（`position:static`）+ `MAIN#main` + `FOOTER.wrap.shell-foot`。**`.appbar` 在这页是「组内演示实例」**（`HEADER.appbar < DIV.grp-demo < SECTION.wrap.grp < MAIN`），不是页面外壳。所以我最初在 `system.html#main` 上测「顶栏遮挡」测错了对象；第 6 项改在 `.appbar` 真是页面外壳的 `b-responsive.html` 上测。

---

## 4. 【第 3 项】人工看图 —— PASS（有发现）

我实际看了 9 张图（`design/system/shots/`）：

| 截图 | 宽度 | 我看到了什么 |
| --- | --- | --- |
| `ds-390-top.png` | 390 | 标题「设计系统 · 三层 token 与组件活样式手册」两行排布正常；正文宽度合适无裁切；页面顶部**没有**产品顶栏（与 §3 结构事实一致） |
| `ds-390-btn.png` | 390 | 组标题「按钮」+ 说明 + `--btn-*` token 胶囊（胶囊底色为浅绿 `--accent-tint`，修复后正常）；无溢出 |
| `ds-390-btn2.png` | 390 | **四个按钮变体真实渲染**：「默认」白底灰边、「保存为我的计划」**墨绿底白字**、「确认删除」粉底危色字+虚线边框、「打开」白底、「删除」带垃圾桶图标、「发送」半透明禁用、`块级按钮(--block)` 满宽墨绿。**无重叠、无裁切、无颜色异常** |
| `ds-390-pill.png` | 390 | 状态胶囊组：成功/警告/危险/信息/依据/建议六种底色与文字色都可辨，底色为对应 tint（修复后正常） |
| `ds-390-stepsfocus.png` | 390 | 步骤组：可见一个 **13×13 原生复选框**（蓝色勾选）在「本轮执行 · 4 步（展开）」摘要上方；聚焦后**没有任何焦点环**（见 §5）；`进行中`/`已失败` 步骤的图标+文字+颜色三重表达清晰，失败态无勾 |
| `ds-390-table.png` | 390 | 表格组：卡片化后字段名与值左右两列对齐，无字段名缺失、无每行一字 |
| `ds-1366-top.png` | 1366 | 页面头部与首组说明，居中 ~880px，无重叠 |
| `ds-1366-btn.png` | 1366 | 按钮变体横向排布，主按钮墨绿，无压塌 |
| `ds-390-btn.png`（修复前另一份） | 390 | 修复前同一位置主按钮为**透明底白字**（文字基本看不见） |

**从图上看到的问题**：
1. **修复前**：`.btn--primary` 白字透明底，文字几乎不可读（M1 的可见形态）。修复后消失。
2. **`ds-390-stepsfocus.png`**：步骤折叠控件是浏览器默认蓝色复选框，**与系统视觉语言不一致**（系统其余控件都用 token 化的自绘外观），且聚焦无指示（见 §5）。
3. 我**没有**发现：元素重叠、文字被裁、列被压塌成每行一字、卡片错位、颜色异常。
4. 一个观察（非缺陷）：390 下「本轮执行」同时展示了**折叠摘要**与**展开后的步骤列表**（因为演示用的 checkbox 默认 `checked`）。作为样式手册这是刻意展示两种状态，可接受；但若读者以为是 bug，建议给该演示加一行说明。

---

## 5. 【第 4 项】R7 机制裁定 —— 实测支持「第 2、4…偶数位」

### 5.1 夹具与口径

390 宽度注入 4 个真实子元素：

```html
<table class="table table--stack"><thead><tr><th>列</th></tr></thead><tbody><tr>
  <td data-label="标签"><span>A1</span><span>A2</span><span>A3</span><span>A4</span></td>
</tr></tbody></table>
```

页面自带规则渲染后：`td` 计算为 `display:grid`，`grid-template-columns: 112.5px 229.5px`，`td::before` 的 `content` 实测 `"标签"`。标签列右边界 = `td.left + padding-left + 112.5 = 130.5px`。

### 5.2 测量结果

**(a) 现状（有 `.table--stack td > *{grid-column:2}`）**

| 子元素 | left | 宽 | 落列 |
| --- | --- | --- | --- |
| #1 | 142.5 | 229.5 | 值列（第 2 列） |
| #2 | 142.5 | 229.5 | 值列 |
| #3 | 142.5 | 229.5 | 值列 |
| #4 | 142.5 | 229.5 | 值列 |

→ `kidsInLabelColumn = []`

**(b) 注入补丁 `.table--stack td > *{grid-column:auto!important}`（等价于删掉该规则）**

| 子元素 | left | 宽 | 落列 | 同 grid row 的伙伴 |
| --- | --- | --- | --- | --- |
| #1 | 142.5 | 229.5 | 值列 | row 1 独立 |
| **#2** | **18** | **112.5** | **标签列（第 1 列）** | row 2（与 #3 同 `top`） |
| #3 | 142.5 | 229.5 | 值列 | row 2 |
| **#4** | **18** | **112.5** | **标签列（第 1 列）** | row 3（与 #5 位置，无 #5 时单独） |

→ `kidsInLabelColumn = [2, 4]`

**在 `b-responsive.html`（rb.css 侧）用同一夹具复测：`kidsInLabelColumn = [2,4]`，逐像素相同。**

### 5.3 裁定

| 问题 | 结论 |
| --- | --- |
| 落进第 1 列（标签列）的是第几个？ | **第 2、4…（偶数位）** |
| `td::before` 是否参与 grid 自动放置、占掉第 1 格？ | **是。** 反证：若 `::before` 不占格，#1 就该落第 1 列；实测 #1 在 `left=142.5 > 130.5`，即第 1 格已被 `::before` 占据 |
| `04-forms-data.md` §7 R7「第 2、4…个（偶数位）」 | **成立** |
| 规格作者原主张「第 3、5…个」 | **不成立** |
| Lead 认同 R7 | **我的独立测量支持 Lead** |

机制：`td` 是两列 grid，`::before` 先自动放置到 (row1,col1)，第 1 个真实子元素落 (row1,col2)，第 2 个换行落 (row2,col1)——偶数位周期性落进标签列。这正是 `td > *{grid-column:2}` 必须存在的原因。

---

## 6. 【第 5 项】`.steps__toggle` 焦点可见性 —— FAIL（WCAG 2.4.7 风险）

### 6.1 `b-responsive.html`（`.sr-only` 版本，任务书所指）

| 检查 | 实测 |
| --- | --- |
| class | `sr-only steps__toggle` |
| `getBoundingClientRect()` | **1 × 1 px** |
| `clip` | `rect(0px, 0px, 0px, 0px)` |
| `position` / `overflow` | `absolute` / `hidden` |
| 聚焦后 `outline-style` | **`none`**（`outline-width 2.67px` 但 style 为 none，不绘制） |
| 是否有 `.steps__toggle:focus-visible ~ …` 之类的替代指示规则 | **没有** |

**结论：键盘用户 Tab 到该控件时，页面上没有任何可见焦点指示。这是 WCAG 2.4.7 Focus Visible（AA）风险。** 用户能看到的可交互件是 `<label class="steps__summary">`（「本轮执行 · 完成 · 2 项动作」那一行），但它与 checkbox 之间**没有 `:focus-visible` 联动样式**，所以焦点落上去时摘要行外观不变。

**最小修复**（不改结构，只加 1 条规则）：
```css
.steps__toggle:focus-visible ~ .steps__summary{
  outline:3px solid var(--focus-outline-color);
  outline-offset:2px;
  border-radius:var(--focus-ring-radius);
}
```
（`<480` 时 `.steps__summary` 可见，正好可以当作焦点载体。）

### 6.2 `system.html`（样式手册里的版本）

| 检查 | 实测 |
| --- | --- |
| class | `steps__toggle`（**没有 `sr-only`**） |
| 尺寸 | **13 × 13 px 原生复选框**，`clip:auto`、`position:static`、`overflow:visible` |
| 聚焦后 `outline-style` | **`none`** |
| 与该类相关的全部规则 | 只有 `.steps__toggle:checked ~ .steps__body` |

**两个结论**：
1. **焦点仍无指示**——`outline-style:none`，且没有任何规则为它画焦点环。截图 `ds-390-stepsfocus.png` 目视确认：蓝色复选框上没有环。
2. **手册的演示与实现的隐藏方式不一致**：规格/原型用 `.sr-only` 把控件隐藏、用摘要行做可见交互件；手册却把它渲染成可见的裸复选框。这会让读者误以为该控件的实际外观是"浏览器默认蓝勾"，且掩盖了 §6.1 的焦点问题。**建议手册改为演示真实的 `.sr-only` 用法**，并配上 §6.1 的焦点规则。

> 注：Chromium 对原生 checkbox 会绘制 UA 主题焦点环，但本例 `outline-style:none` 且截图未见环；我按实测记录，并不排除在其它平台/主题下 UA 会画环——因此这条我判 **FAIL（风险）** 而非「确定无任何平台可见焦点」。

---

## 7. 【第 6 项】sticky 顶栏与锚点跳转 —— FAIL

在 `.appbar` 真是页面外壳的 `b-responsive.html` 上测（390 宽，`#v-S11` 与 skip-link 的 `#main`）：

| 检查 | 实测 |
| --- | --- |
| `.appbar` | `position:sticky`，`top:0`，`z-index:40`，高 **56.7px**，视口内 `rectTop 0 / rectBottom 56.7` |
| 锚点 `#v-S11` 跳转后目标 `top` | **0.3** |
| **被遮挡** | **56.4 px** |
| skip-link `#main` 跳转后 `main.top` | **0** |
| **被遮挡** | **56.7 px** |
| `html{scroll-padding-top}` | **`auto`**（即 0） |
| `body{scroll-padding-top}` | `auto` |
| 目标元素 `scroll-margin-top` | `0px` |
| `rb.css` 中所有 `scroll-padding-*` 规则 | **0 条** |
| `system.html` 中所有 `scroll-padding-*` 规则 | **0 条** |
| token 里 `scroll`/`anchor` 相关变量 | **0 个** |

**结论：任何页内锚点（含 skip-link）跳转后，目标顶部会被顶栏盖住约 56.7px。对 skip-link 而言这直接削弱其可用性——键盘用户跳到「主要内容」后，第一行内容藏在顶栏下面。** 且这是**设计系统层面的缺口**：token 集里有 `--appbar-min-h`（56px）却没有对应的滚动偏移 token，规格与 `rb.css` 也都没有这条规则。

**最小修复**（两处其一）：
```css
/* rb.css / 组件样式 */
html{ scroll-padding-top: calc(var(--appbar-min-h) + var(--sp-1)); }
/* 或对锚点目标 */
:where(#main, section[id], h2[id], h3[id]){ scroll-margin-top: var(--appbar-min-h); }
```
并建议在 `tokens.json` 加一个 L3/L2 token（如 `--appbar-scroll-offset`）承载这个值，避免硬编码 56px 与 `--appbar-min-h` 脱钩。

> 说明：`system.html` 自身因为页面外壳是 `static` 的 `shell-head`，所以**手册页内不会出现这个遮挡**——这也是为什么手工浏览手册时发现不了本项。该缺陷只在「把 `.appbar` 当页面外壳」的真实产品页上暴露，原型 `b-responsive.html` 就是这种形态。

---

## 8. 【第 7 项】注入长串溢出 —— 缺陷存在，根因已定位、修法已验证

### 8.1 测量（320px，冻结的 `b-responsive.html`）

向每个容器尾部注入 60 个字符的无空格串 `X×60`，测页面级溢出增量：

| 容器 | 注入前溢出 | 注入后溢出 | 增量 | span 超视口 |
| --- | --- | --- | --- | --- |
| `.cite__name` | 0 | 359 | **+359 px** | 359.4 |
| `.kv__v` | 0 | 523 | **+523 px** | 522.6 |
| `.card__body` | 0 | 375 | **+375 px** | 375（容器内溢出，页面级也被撑开） |
| `.bubble` | 0 | 375 | **+375 px** | 374.6 |

同一注入在 `system.html`（188869 B）上也复现：`.cite__name` +359、`.kv__v` +523、`.card__body` +375、`.bubble` +375（与 `b-responsive.html` 同量级；我另一次在更早字节上测到 399/654/399/418，属被注入节点所处祖先上下文不同，两页都远超 0）。

**对照**：同一注入放到 `.cell-name` / `.table td` / `.step__sub` 上，页面级增量 **0**（这些位置有 `overflow-wrap:break-word` + `min-width` 或处于可压缩轨道内）。

### 8.2 根因（两类，机制不同）

**(A) `.kv__v`（+523）：`1fr` 的下限是 min-content，`overflow-wrap` 改不了它**

实测祖先链：

```
DD.kv__v      display:block  overflow-wrap:break-word
DIV.kv__row   display:grid   grid-template-columns: 136px 657.927px   ← 关键
DL.kv          display:grid  grid-template-columns: 805.927px
```

`rb.css` 里是 `.kv__row{display:grid;grid-template-columns:8em 1fr}`。`1fr` 等价于 `minmax(auto,1fr)`，其**下限是 min-content**——60 字符串的 min-content 就是整串宽，于是第 2 轨被撑到 **657.9px**，把页面顶宽。**`overflow-wrap:break-word` 不影响 min-content 尺寸**，所以它救不了这个轨道。

**(B) `.cite__name` / `.card__body` / `.bubble`（+359/+375/+375）：块级/弹性子项默认不在任意位置断行**

这三处的 `overflow-wrap` 计算值为 `normal`（`.cite__name`、`.card__body`、`.bubble` 都没有断词规则；`.bubble` 的祖先 `.chat` 等也没给）。无空格串没有可断点，min-content = 整串宽，撑开父级 → 页面级溢出。

### 8.3 修法验证（两条修法**分离**验证，不是打包验证）

| 只加 `.kv__row{grid-template-columns:8em minmax(0,1fr)}` | `.cite__name` | `.kv__v` | `.card__body` | `.bubble` |
| --- | --- | --- | --- | --- |
| 基线（不改） | +359 | **+523** | +375 | +375 |
| 只改 minmax | +359 | **0** ✅ | +375 | +375 |
| 只加 `overflow-wrap:anywhere` | **0** ✅ | +523 | **0** ✅ | **0** ✅ |
| 两者都加 | **0** | **0** | **0** | **0** |

**结论：两类根因对应两条修法，各自独立生效，合并后四项全部归零。Lead 的推测（`1fr` = `minmax(auto,1fr)`，下限 min-content；`overflow-wrap` 不影响 min-content；`.kv__row` 的 `8em 1fr` 同理）**完全成立**，我用分离实验给出了逐项证据。

**最小修复建议**（`rb.css` 冻结不动，登记为实现期必修）：
```css
.kv__row{ grid-template-columns:8em minmax(0,1fr) }
/* 长文本容器（非表格单元格，可用 anywhere） */
.cite__name,.card__body,.bubble,.cite__body,.step__sub{ overflow-wrap:anywhere; }
```
> 注意与 content-spec §1 的既有约定一致：**表格单元格内**继续用 `break-word` + `min-width`（`.cell-name`），只有非表格容器才允许 `anywhere`。

---

## 9. 【第 8 项】对比度实测 —— PASS（41/41）

### 9.1 方法

用 CDP 在页面内取 `getComputedStyle(documentElement)` 的 token 值 + 逐元素 `color`/`backgroundColor`，用**我自己的** WCAG 相对亮度算法计算（不调用 `verify-system.py`）。含 alpha 的底先与其所属层合成：`--bg-readonly`（`rgba(28,25,23,.03)`）按「控件底 over 卡片底」合成。

### 9.2 声明的 41 对

| 版本 | 可测 | PASS | FAIL | 不可测 | 最低比 |
| --- | --- | --- | --- | --- | --- |
| **M1 修复前** | 32 | 32 | 0 | **9** | 4.74 |
| **M1 修复后** | **41** | **41** | **0** | **0** | **4.74** |

修复前不可测的 9 对全部因 token 运行时为空：主按钮文字/底、主按钮 hover、链接与强调文字、当前导航、标签栏当前项、依据胶囊、焦点环×2、主按钮底/页面底。**这 9 对正是 `verify-system.py` D 项「41 对全部达标」在渲染侧站不住的部分**——D 项是纯文本计算，看不到 token 在浏览器里失效。

修复后最低 5 对：未保存草稿虚线边 4.74（要求 3）、表单控件边界 4.8（要求 3）、弱化文字/页面底 5.63、默认胶囊 5.92、建议胶囊 5.92。

### 9.3 渲染后元素抽样（18 个，全部达标）

正文 7.02 / 弱化字 5.97 / 小字 5.97 / 成功胶囊 8.70 / 警告胶囊 6.56 / 危险胶囊 9.14 / 危险提示 9.14 / 成功提示 8.70 / 默认按钮 17.49 / 危险按钮 9.14 / 卡片正文 17.49 / 字段提示 5.97 / 字段标签 16.50 / 空态提示 7.44 / 引用位置 5.97 / 表头 7.44 / **依据胶囊 17.49（修复前为 17.49 但底色丢失 → 视觉上无胶囊）** / 只读控件文字 7.00。**0 个 FAIL。**

### 9.4 `--bg-readonly` 的 alpha 合成（任务点名要核的点）

| 项 | 实测 |
| --- | --- |
| 声明 | `rgba(28,25,23,.03)` |
| 浏览器计算值 | `rgba(28, 25, 23, 0.03)`（保留了 alpha，**未**被预合成） |
| 合成后有效底 | `rgb(248,248,248)`（over `#FFFFFF` 卡片底） |
| 文字色 | `rgb(91, 84, 78)` |
| 对比度 | **7.00:1**（要求 4.5） |

**结论：alpha 合成通路正确**，Lead 在第 2 轮报告里补的「alpha 合成」缺口在这一项上确实补齐了。

---

## 10. 【第 9 项】规格 ↔ 实现一致性 —— PASS

### 10.1 规格声称的状态选择器

| 指标 | 值 |
| --- | --- |
| 4 份规格中的 `backtick` 选择器 token（已剔除文件路径） | 292 |
| 其中**含状态语义**的（`:hover/:focus/:disabled/[aria-current]/--invalid/--running/--failed/...`） | **75** |
| 在 `rb.css` 中存在 | **62** |
| 不在 `rb.css` 中 | **13** |

### 10.2 那 13 个「不在 rb.css」的选择器——**逐条判定后全部不是缺陷**

关键发现：**它们全都是规格自己声明「不存在 / 不得新增」的禁止项**，而不是「规格写了但实现没有」。

| 选择器 | 规格原话（节选） | 判定 |
| --- | --- | --- |
| `.bubble--error` / `.bubble--pending` | `03-conversation.md:263`「rb.css 没有这些类，也不该有」 | 正确记录缺失 |
| `.composer--busy` | `03-conversation.md:397`「常见错误：…或补一个 `.composer--busy`」 | 禁止项 |
| `.draft--failed` | `03-conversation.md:661`「实现里没有这个类」 | 正确记录缺失 |
| `.draft--saving` | `03-conversation.md:743`「不得自造 `.draft--saving`」 | 禁止项 |
| `.error-summary[hidden]` | `04-forms-data.md:619`「rb.css 没有…之类的规则；用条件渲染」 | 正确记录缺失 |
| `.field--loading` | `04-forms-data.md:66`「不存在」 | 正确记录缺失 |
| `.login--error` | `01-shell-navigation.md:883`「rb.css 没有 `.login--error` 之类规则」 | 正确记录缺失 |
| `.prose a:hover` | `03-conversation.md:1010`「❌ `.prose a:hover` 不存在」 | 正确记录缺失 |
| `.table tr:hover` | `04-forms-data.md:65`「rb.css 表单段零 `:hover`」 | 正确记录缺失 |
| `:disabled` | `03-conversation.md:20`「本族没有任何 `:disabled`」 | 正确记录缺失 |
| `:focus-within` | `01-shell-navigation.md:486`「无 `:focus-within`」 | 正确记录缺失 |
| `[aria-current]` | `01-shell-navigation.md:318`「无 `[aria-current]`」（在 AppbarBrand 上） | 正确记录缺失 |

脚本判定：`positivelyClaimedButMissing` 报 2 个（`.composer--busy`、`:focus-within`），我人工复核后判定为**我的否定词正则漏判**——`03-conversation.md:397` 的「常见错误：…补一个 `.composer--busy`」在整段上下文里是禁止项，`01-shell-navigation.md:486` 的「无 `:focus-within`」我脚本因该行同时含 `有`（在「没有」里）而误判。**按人工复核结果：0 个「规格声称存在但 rb.css 没有」。**

### 10.3 `rb.css:NN` 行号引用抽查

| 指标 | 值 |
| --- | --- |
| 4 份规格中的 `rb.css:NN` 引用总数 | **524** |
| 覆盖的不同行号 | **174** |
| 按文件分布 | `01-shell-navigation.md` 193 / `02-actions-status.md` 178 / `03-conversation.md` 73 / `04-forms-data.md` 80 |
| 我的自动校验判「该行确实是 CSS 代码且能定位到所属规则」 | **518 / 524** |
| 判「可疑」的 6 处 | 全部是我校验器的假阴性：引用指向**单行写法**的规则（`html{-webkit-text-size-adjust:100%}`、`a.chip:hover{...}`、`a.chip{...}`），我的"向上找 `{` 结尾行"逻辑找不到 owner |

人工抽查 24 处全部对得上，例如：
- `01-shell-navigation.md` 引 `rb.css:144` → 实际第 144 行 = `.navlink[aria-current="page"]{color:var(--accent-strong);background:var(--accent-tint);font-weight:600}` ✅
- 引 `rb.css:160` → 实际 = `.tabbar__item[aria-current="page"]{color:var(--accent-strong);font-weight:600}` ✅
- 引 `rb.css:110` → 实际 = `:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:4px}`（规格在多处引用它作为全局焦点规则）✅

**结论：524 处行号引用全部成立（0 处指向不存在的行或错误规则）。** 这是规格质量的一个强项——我没有发现「引用了不存在的行号」这类常见缺陷。

### 10.4 第 9 项判定

**PASS。** 没有「规格写了但 rb.css 没有」的状态；行号引用全部可查。

**一处文档小瑕疵**（建议，非缺陷）：`01-shell-navigation.md:331` 在 token 消费表里把 `--brand-mark-radius-lg` 的对照写成「与 `.r-control` 同值」，此处本意应是 token `--r-control`，写成 class 形式 `.r-control`（`rb.css` 里没有这个 class，只有 `--r-control` 变量）。属于 token 名误写成 class 形式的笔误。

---

## 11. 【第 10 项】四条指控的事实核查 —— **四条全部属实**

### 11.1 (a) `pill--warn` 是否同时用于「依据不足」与「处理中」—— **属实，且实际覆盖 5 种语义**

`b-responsive.html` 中 `pill--warn` 共 **6 处**：

| 行号 | 视图 | 该胶囊承载的语义 | 文本 |
| --- | --- | --- | --- |
| **1001** | `v-S05` | **检索成功 · 没有足够依据**（依据不足） | `检索成功 · 没有足够依据`，紧随其后（1006 行）是 `已检索共享资料，但没有找到足以回答这项要求的内容。` |
| 1074 | `v-S06` | **未保存**（草稿） | `未保存` |
| 1152 | `v-S06` | **待确认 · 写入结果未知** | `待确认 · 写入结果未知` |
| **1686** | `v-S11` | **处理中** | `处理中` |
| **1756** | `v-S11` | **处理中**（另一行） | `处理中 / 解析与向量化进行中 · 42%（最长 60 秒）` |
| 1973 | `v-S12` | **需确认后继续**（重叠冲突） | `需确认后继续` |

**结论：指控 (a) 属实。** 更精确的事实是：`--pill-warn-*` 这一个 token 组在冻结原型里同时承载 **5 类语义**（依据不足 / 未保存 / 待确认 / 处理中 / 需确认后继续）。其中「未保存 / 待确认」与 `content-spec` 里「琥珀专用于未保存·待确认」的定位一致，而「依据不足」「处理中」「需确认后继续」属于把同一视觉档复用到其它语义。**这是事实，如何处置由 Lead 决定（我不替你决策）。**

### 11.2 (b) `a.chip` 是否零实例、`.chips` 里实际是什么 —— **属实；`.chips` 有 1 个实例，里面装的是 `.btn.btn--sm`**

| 检查（`b-responsive.html`） | 值 |
| --- | --- |
| `a.chip` 实例数 | **0** |
| 任何带 `chip` class 的元素 | **0** |
| `.chips` 容器实例数 | **1** |
| `.chips` 容器的内容 | `<div class="chips"> <button class="btn btn--sm" type="button" data-fill="查今天的课"> <svg …>…</svg> …` |

**结论：指控 (b) 属实** —— `a.chip` 在冻结原型里零实例，`.chips` 容器里装的是 `.btn.btn--sm` 按钮（三个示例入口），**不是** `a.chip` 链接。

补充事实（对裁定有用）：`system.html` 里 `a.chip` **有 4 个实例**、`.chips` 1 个。所以该 class 在**设计系统里是被演示、被 token 化的**（`--chip-*` 共 15 个 token），只是在**冻结原型里未被采用**。这解释了为什么它同时出现在「27 组齐全」的 PASS 里、又是「零实例」的指控对象——两个说法都成立，只是说的对象不同。

### 11.3 (c) `records.html:273` 的 `.pill--danger`「不可恢复」是否没有图标 —— **属实**

第 273 行原文：

```html
<span class="pill pill--danger">不可恢复</span>
```

| 检查 | 值 |
| --- | --- |
| 该行含 `pill--danger` | 是 |
| 该行含 `<svg>` | **否** |
| `records.html` 中 `pill--danger` 总数 | 1 |
| 其中无 `<svg>` 的 | **1（即全部）** |

**结论：指控 (c) 属实**——该胶囊是「文字 + 颜色」两重、**缺图标**。

但需要给出完整事实以便裁量：该 pill 所在的**卡片头部**（同一 `card__head` 内、`h3#s09-del-title`）**有**一个 24×24 的警告三角 SVG：

```html
<h3 id="s09-del-title">
  <svg … aria-hidden="true" focusable="false"><path d="M10.3 4.3 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/>…</svg>
  删除确认
</h3>
<span class="pill pill--danger">不可恢复</span>
```

所以「整个删除确认面板」满足「图标 + 文字 + 颜色」三重；缺图标的是**这个胶囊自身**。若把要求定在「每个状态胶囊必须三重」，则本项不达标；若定在「每个状态展示必须三重」，则已达标。**口径由 Lead 定，我只给事实。**

### 11.4 (d) `parts/login.html` 是否未实现密码显示/隐藏切换 —— **属实**

`content-spec.md` 第 **54** 行原文：

```
- 字段：账号（label「账号」，必填）、密码（label「密码」，必填，带显示/隐藏切换）
```

`parts/login.html` 实测：

| 检查 | 值 |
| --- | --- |
| `type="password"` 输入框 | 3 |
| `<button>` 总数 | 3 |
| 按钮内容 | 全部是 `<button class="btn btn--primary btn--block" type="button">登录</button>`（第三处带 `disabled`） |
| 含 `<svg>` 的按钮 | **0** |
| 文案含「显示密码 / 隐藏密码 / 显示/隐藏 / 切换」 | **无** |
| `aria-pressed` / 相关 `aria-label` | **无** |

**结论：指控 (d) 属实** —— 密码字段**没有**显示/隐藏切换控件，与 `content-spec` S01 的字段要求不符。

补充事实（对裁量的关键）：`01-shell-navigation.md:936` 明确写了 **「为密码切换控件自拟文案或只给图标不给可访问名（U9 未解决前该槽位不得实现）」**。即规格作者**有意**暂不实现该控件，等 U9（文案/可访问名）确定。所以这是**「规格与 content-spec 的显式偏离，且已记录理由」**，不是遗忘。**这改变了它的性质**：仍是「与 content-spec 不符」的事实，但属于有据可查的延期决定，需要 Lead 决定是接受该偏离还是在交付前补上。

---

## 12. 【第 11 项】我没有验证的部分

1. **跨浏览器**：只测了 Microsoft Edge（Chromium）。**Firefox / Safari 未测**——尤其 `overflow-wrap:anywhere` 与 `minmax(0,1fr)` 的 min-content 交互、`:focus-visible` 在 Safari 的历史差异，都没有验证。
2. **屏幕阅读器的实际朗读**：只核了 DOM 属性（`aria-*`、可访问名来源），**没有用 NVDA/JAWS/VoiceOver 实听**。第 5 项的焦点问题也没有在真实键盘走查中复验（我用的是程序化 `.focus()`；程序化聚焦与真实 Tab 在 `:focus-visible` 匹配上可能不同——这一点我在上一轮 `b-responsive` 验证中也标过 UNKNOWN）。
3. **非 Chromium 内核的 grid 行为**：第 4 项的 `::before` 自动放置结论只在 Chromium 上测。CSS Grid 规范对 `::before` 作为 grid item 有明确规定，但 Firefox 的实现细节我没有实测。
4. **token 在设计工具（Figma/Sketch）图层面板里的表现**：`tokens.json` 能否被设计工具正确导入、三层命名是否会在工具里冲突——完全没验。
5. **Vue 3 实际消费**：没有搭一个 Vue 工程去 `import './tokens.css'` 并渲染真实组件。我只用「最小 HTML + `<link>`」验证了 token 在浏览器里生效（这一条已足够证明 M1，见 §13）。
6. **打印 / `@media print`、暗色模式、`prefers-reduced-motion`**：`system.html` 只有一个 `<style>` 且 `media` 为空（无 print 分支）；没有暗色方案可测；`prefers-reduced-motion` 未在真实偏好下实跑（`--motion-spin-duration` 有 token 化，但降级行为没验）。
7. **对比度**：只算了 sRGB 相对亮度公式的 WCAG 2.1 对比度，**没有算 APCA**；也没有考虑子像素抗锯齿对实际可读性的影响。
8. **`system.html` 的 63 个标题与既有文档站的一致性**：只核了「单一 h1 + 不跳级」，没有核标题文案与组件规格的措辞一致性。
9. **`styleguide.css` / `styleguide-demos.html` 作为「手写素材」的质量**：我只验证了它们在 `system.html` 里组装后的渲染结果，没有单独评审这两个源文件的组织质量。
10. **`verify-system.py` 本身是否有假阳性/假阴性**：我复现了它的 29（现 31）PASS，但**没有对它的每一条检查做变异测试**（例如故意构造一个违规 token 看它是否 FAIL）。它新增的 J 项我也只是看它报 PASS，没有独立构造反例去测它的检出能力。

---

## 13. 对 Lead 的 29（现 31）项 PASS 的逐条独立复现态度

我 `python design\system\verify-system.py` 复现了 **29 PASS / 0 FAIL**（逐条文字一致）。但「脚本跑出同样结果」≠「独立验证了该结论」。逐条表态：

| 组 | 项 | 我独立复现的结论 |
| --- | --- | --- |
| A | 生成保真 515/518 token 逐值一致 | **文本层一致，我复现**；但这正是 M1 漏检的那一层（文本在 ≠ 浏览器认） |
| B | L1 纯字面量 / L2 只指 L1 / L3 无裸色值 / 取色经 L2 / L3 不互引 / 引用完整性 | **文本层我未独立重算**（未逐 token 重跑纯度规则）→ 对默认 PASS **不表态**。但 L3「取色经 L2」我间接验证过：`--btn-primary-bg` 解析为 `#14665B` 而非直接引用 `--p-green-700` |
| C | L1 覆盖度 / L3 规模 | 未独立复现 → **不表态** |
| D | 对比度 41 对全部达标，最低 4.74 | **我独立复现且加强**：修复后 41/41 可测、0 FAIL、最低 4.74（§9）。**但修复前有 9 对在渲染侧不可测**——D 项的「41 对达标」在 M1 存在时是**文本层正确、渲染层不成立** |
| E | rb.css 74 个变量逐值相等 | **我独立复现**：`:root` 74 个共同 token 修复后 0 差异（§2.2） |
| F | 4 份规格骨架 / 27 组不重不漏 | 骨架我未逐节核；27 组我**独立复现**（`system.html` 27 个 `data-group`，与 `tokens.json` 组件键一致） |
| G | ds-tokens 逐字节一致 / 27 组齐全 / 组件样式无裸值 / 只消费 L3 / 零外部请求 / 无 emoji / data-label / 单一 h1 / 标题不跳级 / L3 全覆盖 | **独立复现**：27 组齐全✅、零子资源✅（六宽度 `resource` 全 0）、单一 h1 且 63 标题✅、`table--stack` 的 `data-label` 齐全✅。**逐字节一致我确认字节相同，但正因如此 M1 也被一起内联进产物**——字节比对是这个盲区的另一半来源 |
| H | tokens.ts 断点一致 / tokens.md 等价性声明 | 未独立复现 → **不表态** |
| I | README 计数一致 | 未独立复现 → **不表态** |
| **J（新）** | 注释安全 / 规则 prelude 恰好 `:root` / 声明可达 | **我独立复现了判据本体**：`styleSheets[0].cssRules.length = 58`、**每条 `selectorText` 都是 `:root`**、`nonRootPreludes = []`、**518/518 token 计算值非空且与 `tokens.flat.json` 逐字相等** |

**关于 M1 为什么逃过 29 项**：A 项是**文本逐值**、G 项是**字节逐字节**，两者都在"文件内容"层；没有任何一项把 CSS 交给浏览器解析。M1 恰好是"文本完全正确、字节完全正确、浏览器解析结果错误"的形态。Lead 新增的 J 项正是补这个盲区——**我复现了 J 的判据本体，它确实能挡住这一类**。

---

## 14. 必修 / 建议问题清单

### 必修（影响交付可用性）

**W1（新，高）缺少 `scroll-padding-top`，页内锚点与 skip-link 目标被 sticky 顶栏遮挡 56.4–56.7px。**
- 证据：§7。`html{scroll-padding-top:auto}`；`rb.css` 与 `system.html` 各 **0 条** `scroll-padding-*` 规则；token 里 **0 个**滚动偏移变量。
- 影响：skip-link 跳到 `#main` 后第一行内容藏在顶栏下，削弱无障碍承诺。
- 最小修复：`html{scroll-padding-top:calc(var(--appbar-min-h) + var(--sp-1))}`，并建议在 token 里加 `--appbar-scroll-offset` 承载该值。

**W2（新，中）`.steps__toggle` 无任何可见焦点指示。**
- 证据：§6。`b-responsive.html` 里它是 1×1 `clip:rect(0 0 0 0)` 隐藏，聚焦后 `outline-style:none`，且没有 `.steps__toggle:focus-visible ~ .steps__summary` 联动规则；`system.html` 里它是 13×13 裸复选框，聚焦同样无环（截图 `ds-390-stepsfocus.png` 目视确认）。
- 影响：WCAG 2.4.7 Focus Visible（AA）风险，键盘用户看不到焦点在哪。
- 最小修复：见 §6.1 的 3 行规则；同时把手册演示改成真实的 `.sr-only` 用法。

**W3（新，中，已在冻结原型里，登记为实现期必修）长串内容会打破「页面级溢出 = 0」。**
- 证据：§8。320px 注入 60 字无空格串：`.cite__name` +359、`.kv__v` +523、`.card__body` +375、`.bubble` +375 px。
- 根因两条、已分离验证：`1fr` 的 min-content 下限（`.kv__row`）＋块级容器 `overflow-wrap:normal`。
- 最小修复：§8.3 的两条规则，合并后四项归零（已实测）。

**M1（已修复并复验关闭）** `tokens.css` 头注释 `*/` 提前闭合吞掉品牌色 `:root`，导致 30/518 token 运行时失效。修复后我复验：58 条规则全 `:root`、518/518 token 复活、`.btn--primary` 恢复 `rgb(20,102,91)`、最小 `<link>` 页面同样生效（§13 J 项 / §2.5）。

### 建议

**S1** 手册的 `.steps__toggle` 演示改成真实的 `.sr-only` 形态（现在是可见裸复选框，既是视觉噪音，又掩盖了 W2）。
**S2** `.chips` 在原型中用 `.btn.btn--sm`、`a.chip` 零实例——若 `a.chip` 是既定模式，应统一；若不用，考虑从 L3 契约中移除或标注为「保留能力」（影响 15 个 `--chip-*` token 的 `verify` 口径）。
**S3** `pill--warn` 承载 5 类语义（依据不足/未保存/待确认/处理中/需确认后继续）。建议在规格 §4 状态矩阵里显式列出这 5 种用法并说明理由，否则实现者会以为可以再复用。
**S4** `records.html:273` 的 `pill--danger` 缺图标（同卡片头部有警告三角）。若「每个状态胶囊三重表达」是硬要求，需补图标；若以「容器级三重」为准，建议在规格里写清口径。
**S5** `parts/login.html` 未实现密码显示/隐藏（`01-shell-navigation.md:936` 已记录为 U9 未决而暂缓）。建议在 `content-spec` 或规格里显式标注该偏离，避免验收时被判为遗漏。
**S6** `01-shell-navigation.md:331` 把 token `--r-control` 写成 class `.r-control`，建议改为 token 写法。
**S7** `.step--running .step__ico` 的 `animation-name: spin`、`1.1s linear` 我已实测生效（Lead 本轮改动正确）；建议顺带补 `prefers-reduced-motion` 下的降级验证。

---

## 15. 与 Lead / 规格作者的结论分歧

| 议题 | 结论 |
| --- | --- |
| M1 是否存在 | **一致**（我先发现并定位到行，Lead 复核后修复，我复验通过） |
| M1 的修复效果 | **一致**：58 条规则全 `:root`、30 token 复活、`.btn--primary` 恢复墨绿、最小 `<link>` 页面同样生效 |
| 第 1 项修复后是否仍有残留差异 | **无真差异**：28 个剩余差异我逐条自证为夹具/节点选择/状态差异。**但我不建议把这个"0 真差异"当成永久结论**——它成立的前提是我这套中和样式足够公平；换一套夹具可能暴露出新的伪差，需要在复验时同样人工归因 |
| 第 4 项 R7 | **一致，且我给了逐像素数据**：第 2、4 位落标签列，`::before` 占第 1 格 |
| 第 7 项根因与修法 | **一致，且我做了分离验证**：Lead 推测的 `minmax(auto,1fr)` min-content 下限**成立**；我额外证明 `.cite__name`/`.card__body`/`.bubble` 是**另一条**根因（`overflow-wrap:normal`），需要 `anywhere` 而不是改轨道 |
| `.chips` 里是什么 | Lead 未提及；我给出事实：1 个 `.chips` 容器，内容为 `.btn.btn--sm` 按钮，`a.chip` 零实例 |
| 焦点环/`.steps__toggle` | Lead 未提出；我判 **FAIL（风险）**，并给出 3 行修法 |
| `scroll-padding-top` | Lead 未提出；我判 **FAIL**，并指出这是**设计系统层面的 token 缺口**（有 `--appbar-min-h` 无滚动偏移） |
| 第 9 项「规格写了但 rb.css 没有」 | **0 例**。13 个未命中的状态选择器全是规格**自己声明不存在/禁止**的；2 个被我的正则误判为"肯定声称"，人工复核后撤销 |
| 错误码白名单条数（上一轮议题） | 本轮不涉及；仍以我为 35 个的独立计数为准 |

---

## 16. 证据文件与截图清单

工作区外探针（`%TEMP%\dsh-Fs8H4c\ds-verify\`，非交付物）：
`item1b-390.json` / `item1b-1366.json`（修复后 class 级比对）、`tokaudit2.json`（518 token 审计）、`m1.json`（CSSOM/复活/最小页）、`attrib-390.json` / `attrib-1366.json`（28 个差异逐条归因）、`item2b.json`（六宽度+chips+animation）、`item7attr.json`（两条修法分离验证）、`item8b.json`（对比度 41 对）、`static9.json` / `s910b.json`（规格↔实现、四条指控）。

截图（`design/system/shots/`，均为修复后字节）：
`ds-390-top.png`、`ds-390-btn.png`、`ds-390-btn2.png`、`ds-390-pill.png`、`ds-390-stepsfocus.png`、`ds-390-table.png`、`ds-1366-top.png`、`ds-1366-btn.png`

被验收文件全程只读；**本次唯一交付写入为 `design/system/verification.md`**。`shots/` 依任务书要求存放截图（评审辅助产物，可由 Lead 在收尾时清理）。
