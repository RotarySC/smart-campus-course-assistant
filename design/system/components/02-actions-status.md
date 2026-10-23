<!-- owns: btn, chip, pill, notice, steps, empty -->
# 动作与状态（按钮 / 标签胶囊 / 提示块 / 过程条 / 空状态）

方向 B「纸感墨绿 · 专注对话」的**动作与状态族**组件 API 规格。实现锚点一律指
[`../../responsive/rb.css`](../../responsive/rb.css)；文案来源一律
[`../../directions/shared/content-spec.md`](../../directions/shared/content-spec.md)（下称 content-spec）。

## 0. 本文件约定

| 约定 | 内容 |
| --- | --- |
| 行号锚点 | `rb.css:NNN` 指 `design/responsive/rb.css` 的行号，全部为 1-based |
| 解析值 | 与 [`tokens.flat.json`](../tokens.flat.json) **逐字相等**；表内用反引号包裹，去掉反引号后逐字相等（如 `#FFFFFF`、`transparent`、`0.5`） |
| 消费层级 | 组件只消费 L3（`--btn-*` / `--chip-*` / `--pill-*` / `--notice-*` / `--step*` / `--empty-*`）。凡出现 L2/L1 名字，一律显式标注**上游**，且仅用于说明，不作为消费面 |
| 状态矩阵 | **只登记 `rb.css` 真实存在的状态**。`rb.css` 全文没有 `:active`、没有任何 `transition` 声明（`grep transition` 只命中 rb.css:111 的降级复位）；`:hover` 只出现在 rb.css:143（`.navlink`）、**rb.css:201（`.btn--primary:hover`）**、**rb.css:396（`a.chip:hover`）**。本族所有其它组件**没有 hover 态** |
| 图标 | content-spec §0：内联 SVG，Lucide 风格 24×24 线性路径，`stroke-width:1.75`，`fill:none`，纯装饰图标必须 `aria-hidden="true" focusable="false"`。禁止 emoji 充当图标（content-spec §3） |
| 禁用表述 | ① 禁止把**模型内部推理过程**写成过程步骤（Steps 的标题只能是可核实工具动作）；② 禁止用一句**中性兜底文案**同时表达「成功的空」与「服务异常」。违禁词原文清单见 content-spec:73 与 content-spec §3——**本规格刻意不复述原文**，避免被逐字复制进 UI |

### 覆盖索引（owns 6 组 / 99 个 L3 token，全部必须出现在某一 token 消费表）

| L3 组 | token 数 | 组件 | 代码锚点 |
| --- | --- | --- | --- |
| `btn` | 22 | Button | rb.css:193–206 |
| `chip` | 12 | Chip / Chips | rb.css:392–396 |
| `pill` | 21 | Pill | rb.css:209–220 |
| `notice` | 17 | Notice | rb.css:223–231 |
| `steps` | 13 | Steps | rb.css:245–263 |
| `empty` | 14 | Empty | rb.css:301–308 |
| 合计 | **99** | | |

> 组名前缀注意：`steps` 组同时含 `--steps-*`（容器/摘要）与 `--step-*`（单步）两段前缀；
> `chip` 组同时含 `--chip-*` 与 `--chips-gap`（容器）。

---

## Button `.btn`

### 1. 用途与边界

- **是**：页面里唯一的动作控件。基类 `.btn` 即**次级按钮**（白底 / 暖灰边 / 深字），没有 `.btn--secondary`。
- **是**：一个视区内**至多一个** `.btn--primary`（主操作），危险操作用 `.btn--danger`，低权重次操作用 `.btn--ghost`。
- **不是**：不是链接入口。示例入口在冻结原型里用 `.btn--sm`（见 Chip 章 §9 的登记），不是裸 `<a>`。
- **不是**：不自带加载态、不带图标位专用槽、不带尺寸档（除 `--sm` 外无 `--lg`）。任何「加载中 / 执行中」语义必须由 Notice 或 Steps 承载，不得写进按钮文案。

### 2. 结构（DOM 骨架）

```html
<!-- 主操作（唯一）：带前置装饰图标 -->
<button class="btn btn--primary" type="button">
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
       stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
       aria-hidden="true" focusable="false"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
  发送
</button>

<!-- 纯图标按钮（表内次级操作）：可见文字缺失 → 必须 aria-label -->
<button class="btn btn--sm" type="button" aria-label="查看前一天">…svg…</button>

<!-- 修饰类组合（冻结原型既有组合，records.html:156 / login.html:34 / assistant.html:543） -->
<button class="btn btn--sm btn--danger" type="button" aria-label="删除计划：期末复习总纲">…</button>
<button class="btn btn--primary btn--block" type="button">登录</button>
<button class="btn btn--primary btn--sm" type="button">…</button>
<button class="btn btn--primary" type="button" disabled>…</button>
```

- 图标放在文字**之前**（rb.css:194 的 `gap` 只作用于相邻子项，顺序决定视觉）；纯文本按钮无子元素，`gap` 无效果。
- 同一元素上**禁止**同时挂两个互斥颜色修饰类（`--primary` / `--danger` / `--ghost`）：三者特异性相同，胜负由源码顺序决定（rb.css:200 → 202 → 203），会有非预期覆盖。

### 3. API 表

| class / 属性 | rb.css | 必需 | 语义与用途 |
| --- | --- | --- | --- |
| `.btn` | 193–199 | 是 | 基类，次级按钮（白底 / 暖灰边 / 深字），`min-height:44px` |
| `.btn--primary` | 200（hover 201） | 否 | 主操作。实心主色底 + 白字 + 同色描边；**唯一有 hover 态的按钮** |
| `.btn--danger` | 202 | 否 | 危险操作（删除 / 停用 / 确认删除）。**浅危险底 + 深危险边 + 深危险字**，不是实心红，与主操作视觉分离 |
| `.btn--ghost` | 203 | 否 | 低权重次操作（取消 / 清空对话 / 展开片段）。透明底 + 透明边 + 次级文字色 |
| `.btn--block` | 204 | 否 | `width:100%`，占满父容器（登录页） |
| `.btn--sm` | 206 | 否 | 小号：横向内边距 18→12px、字号降到 15px；**`min-height` 仍是 44px，不降高** |
| `[disabled]` | 205 | — | 属性，非 class。`opacity:.5` + `cursor:not-allowed` |

| 档位 | 字号 / 行高 | 来源 |
| --- | --- | --- |
| `.btn`（默认） | 继承 `font:inherit`（rb.css:197）→ 正文 17px / 1.75（上游） | rb.css:197 |
| `.btn--sm` | 15px（`--btn-fs-sm`） | rb.css:206 |

### 4. 状态矩阵（只写 rb.css 真实存在的状态）

| 状态 | 选择器 | rb.css | 表现 | 备注 |
| --- | --- | --- | --- | --- |
| 常态 | `.btn` | 193–199 | 白底 `#FFFFFF` / 边 `#C9C3BC` / 字 `#1C1917` | 与卡片同底，靠 1px 暖灰边成形 |
| 悬停 | `.btn--primary:hover` | **201（全族唯一按钮 hover）** | 底 `#14665B` → `#0F4A42` | 无过渡动画（rb.css 无 `transition`），瞬时切换 |
| 禁用 | `.btn[disabled]` | 205 | `opacity:.5`、`cursor:not-allowed` | 仅降透明度，**未`pointer-events:none`** |
| 键盘焦点 | 全局 `:focus-visible` | 110 | 3px `--focus` 轮廓、offset 2px、圆角 4px | 上游（L2）；非 `.btn` 专属规则 |
| 按下 | — | — | **不存在**：rb.css 无 `:active` | 不得在规格或实现里补 `:active` |
| 主按钮 / 危险 / 幽灵的 hover | — | — | **不存在**：201 只覆盖 `.btn--primary` | 不得声称其它变体有 hover 反馈 |

**已核实现象（实现时必须知道）**：`.btn--primary[disabled]:hover` 仍会变深——rb.css:201 的特异性 (0,2,0) 与 rb.css:205 相同，两条规则设置的是不同属性（`background` vs `opacity`），205 并未覆盖 201。设计系统**不新增**禁用态 hover 抑制规则——新增抑制规则就必须新增 L3 token 并重跑 `rb.css` 逐值等价性验证，超出本轮范围。

> 判定：属冻结产物的既有行为，登记为「已知现象」，不视为缺陷；Vue 阶段若要消除，须先改 `tokens.json` 再重新生成并复验。

### 5. token 消费表（22 个 `btn` 组 token，全覆盖）

| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| 常态底色 | `--btn-bg` | `#FFFFFF` | rb.css:198；卡片同底，靠描边成形 |
| 常态文字色 | `--btn-fg` | `#1C1917` | rb.css:198 |
| 常态描边色 | `--btn-border-color` | `#C9C3BC` | rb.css:198 |
| 描边宽度 | `--btn-border-w` | `1px` | rb.css:196；对应 `border:1px solid transparent` |
| 最小高度 | `--btn-min-h` | `44px` | rb.css:195；`--sm` 不覆盖它（rb.css:206 仍写 44px）＝触控目标下限 |
| 横向内边距（默认） | `--btn-pad-x` | `18px` | rb.css:195 |
| 横向内边距（sm） | `--btn-pad-x-sm` | `12px` | rb.css:206 |
| 图标与文字间距 | `--btn-gap` | `6px` | rb.css:194 |
| 圆角 | `--btn-radius` | `10px` | rb.css:196 |
| 字重 | `--btn-fw` | `600` | rb.css:197 |
| 小号字号 | `--btn-fs-sm` | `15px` | rb.css:206 |
| 禁用不透明度 | `--btn-disabled-opacity` | `0.5` | rb.css:205 |
| 主按钮底色 | `--btn-primary-bg` | `#14665B` | rb.css:200 |
| 主按钮文字色 | `--btn-primary-fg` | `#FFFFFF` | rb.css:200（rb.css 此处写裸 `#FFFFFF`，L3 已收敛为 `--text-on-accent`） |
| 主按钮描边色 | `--btn-primary-border-color` | `#14665B` | rb.css:200；实心底 + 同色边 |
| 主按钮悬停底色 | `--btn-primary-bg-hover` | `#0F4A42` | rb.css:201；全族唯一 hover 面 |
| 危险按钮底色 | `--btn-danger-bg` | `#FBE7EC` | rb.css:202 |
| 危险按钮文字色 | `--btn-danger-fg` | `#7B0E2C` | rb.css:202 |
| 危险按钮描边色 | `--btn-danger-border-color` | `#9F1239` | rb.css:202；危险按钮是「浅底+深边」，非实心 |
| 幽灵按钮底色 | `--btn-ghost-bg` | `transparent` | rb.css:203 |
| 幽灵按钮文字色 | `--btn-ghost-fg` | `#5B544E` | rb.css:203 |
| 幽灵按钮描边色 | `--btn-ghost-border-color` | `transparent` | rb.css:203 |

**无 L3 token 的规则（仍有锚点）**

| 属性 | 值 | rb.css | 说明 |
| --- | --- | --- | --- |
| 布局 | `display:inline-flex` + `align-items:center` + `justify-content:center` | 194 | 图标与文字垂直居中；按钮宽度随内容 |
| 字体 | `font:inherit` | 197 | 继承正文 17px/1.75（上游） |
| 光标 | `cursor:pointer` | 197 | — |
| 块级 | `width:100%` | 204 | `.btn--block` |
| 禁用光标 | `cursor:not-allowed` | 205 | 与 `opacity` 同时生效 |

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 元素 | 一律原生 `<button type="button">`（提交用 `type="submit"`）。禁止用 `<div>` 伪造按钮 |
| 可访问名 | 有可见文字 → 文字即名；**纯图标按钮必须有 `aria-label`**（冻结原型 records.html:22/26 的「查看前一天 / 查看后一天」是范例） |
| 图标 | 装饰图标 `aria-hidden="true"` + `focusable="false"`；按钮的可访问名**不得**依赖图标 |
| 触控目标 | `--btn-min-h` = 44px（rb.css:195），`.btn--sm` 同样 44px（rb.css:206）→ 所有按钮 ≥44×44 CSS px |
| 键盘 | 原生 `<button>`：Tab 聚焦、Enter/Space 激活；禁用元素不进入 Tab 序（原生行为） |
| 焦点可见 | 全局 `:focus-visible`（rb.css:110，上游 `--focus` L2）：3px 轮廓 + 2px offset，不被吸底 `.composer` 遮挡（b-responsive-spec §7） |
| 对比度 | 主按钮文字/底 `6.82:1`、hover 文字/底 `10.10:1`、主按钮底/页面底 `6.43:1`（tokens.md §7 实测，全部 PASS）。默认按钮文字 `#1C1917`/`#FFFFFF` 远高于 4.5:1 |
| 状态不靠颜色 | 按钮本身不编码状态；危险操作除颜色外还有**独立文案**（「确认删除」「确认停用」）与位置分离（content-spec §1 危险操作行） |
| 禁用可理解 | `opacity:.5` 只是视觉；禁用按钮必须伴随可读原因（如 assistant.html:64「空白不可提交，发送按钮为禁用态」）。不得让禁用态成为唯一解释 |

### 7. 内容与文案规则

| 位置 | 取值 | 来源 |
| --- | --- | --- |
| 主按钮（登录） | 登录 | content-spec:56 |
| 主按钮（发送） | 发送 | content-spec:69 |
| 主按钮（保存） | 保存为我的计划 | content-spec:106 |
| 次级按钮 | 继续修改 / 取消 / 重新加载 | content-spec:106/170/137 |
| 危险按钮 | 确认删除 / 确认停用 | content-spec:138/147 |
| 空状态动作 | 换个日期 / 重试 / 手动新建 / 新建计划 / 选择文件 | content-spec:122/124/133/134/151 |
| 过程操作 | 停止 / 查询写入状态 / 换个问法 / 联系管理员补充材料 | content-spec:77/109/93/93 |

- 文案一律 **2–6 个汉字**，动宾结构，不加句号（冻结原型全部按钮无尾句号）。
- 禁止：省略号式「提交中…」（无加载态）、「点击这里」、英文动词、emoji。
- 危险按钮文案必须**自证后果**（「确认删除」而非「确定」）。

### 8. 响应式行为

| 档 | 行为 | 依据 |
| --- | --- | --- |
| base（<480） | 与其它档完全一致；`min-height:44px`、横向内边距 18px / sm 12px | rb.css:193–206 **无任何 @media** |
| xs ≥480 / sm ≥768 / md ≥1024 / lg ≥1200 / xl ≥1440 | 无变化（组件内部间距与字号不随断点变化） | b-responsive-spec §6「间距不随断点线性放大」 |
| 全部档 | `inline-flex` 随内容收缩；`.btn--block` 撑满父容器。窄屏行内多按钮靠容器 `.row{flex-wrap:wrap}`（rb.css:390）换行，不由按钮自身换行 | rb.css:390 |

### 9. 契约依据与禁止事项

- 上游依据：content-spec §1（触控目标、焦点可见、危险操作二次确认且视觉分离、只读 vs 禁用可区分）；b-responsive-spec §6（最小触控目标 44×44）、§9.4（`<768` 下 `.btn` 高度 ≥44px 为验收项）。
- **禁止**：补写 `:active` / `transition` / `:hover`（除 `.btn--primary:hover`）/ 加载态 / 尺寸档 `--lg`——`rb.css` 里都不存在。
- **禁止**：把 `.btn--danger` 写成实心红底白字（rb.css:202 是浅底深字深边）。
- **禁止**：在 `.btn--sm` 上写 `min-height` 小于 44px。
- **禁止**：发明新 token（如 `--btn-lg-*`、`--btn-hover-*`）；`.btn` 的消费面恰好是本章 §5 的 22 个。
- 上游引用（仅说明，不作消费面）：`.btn` 的字体继承 `--root-fs` / `--root-lh`（L3·root 组）；焦点环 `--focus`（L2）。

---

## Chip 与 Chips `a.chip` `.chips`

### 1. 用途与边界

- 两个 class 承担**两种不同角色**，必须分清：
  1. **`.chips`（容器）**：横向可换行的标签/入口行（rb.css:392）。冻结原型在 assistant.html:43–56 用它承载 S02「试试这样问」的三个**示例入口**（子元素是 `.btn.btn--sm`）。
  2. **`a.chip`（元素）**：胶囊形的**链接入口**（rb.css:393–396）。**它是元素限定选择器**——只在 `<a class="chip">` 上生效，`<button class="chip">` 与 `<div class="chip">` 都拿不到任何样式。
- **不是**：`a.chip` 不编码状态。状态一律走 Pill；不要用 chip 承载「已选/已完成」。
- **不是**：`.chips` 不是列表容器，不承担语义（无 `role="list"`），换行由 `flex-wrap` 完成。

### 2. 结构（DOM 骨架）

```html
<!-- 容器：任何"可换行的胶囊行" -->
<div class="chips"> … </div>

<!-- A. 契约形态（a.chip）：链接入口。注意必须是 <a> -->
<div class="chips">
  <a class="chip" href="#v-S02">
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
         stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
         aria-hidden="true" focusable="false"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M3 10h18"/></svg>
    查今天的课
  </a>
</div>

<!-- B. 冻结原型实际形态（assistant.html:43-56）：容器 + .btn--sm 子元素 -->
<div class="chips">
  <button class="btn btn--sm" type="button" data-fill="查今天的课">…</button>
  <button class="btn btn--sm" type="button" data-fill="根据资料回答问题">…</button>
  <button class="btn btn--sm" type="button" data-fill="制定学习计划">…</button>
</div>
```

### 3. API 表

| class | rb.css | 宿主 | 用途 |
| --- | --- | --- | --- |
| `.chips` | 392 | 任意块级元素（原型用 `<div>`） | 胶囊行容器：`display:flex` + `flex-wrap:wrap` + `gap:6px` |
| `a.chip` | 393–395 | **仅 `<a>`** | 胶囊形链接：白底 / 暖灰边 / 深字 / 999px 圆角 / 44px 高 / 无下划线 / 字重 500 |
| `a.chip:hover` | 396 | 仅 `<a>` | 边 → 主色 `#14665B`，字 → 深主色 `#0F4A42`（唯一 hover 面） |

| 项 | 值 | 来源 |
| --- | --- | --- |
| 触控目标 | 44px（`--chip-min-h` = `--size-control-min`） | rb.css:393 → b-responsive-spec §6/§9.4 |
| 圆角 | 999px（胶囊） | rb.css:394 |
| 与 `.btn--sm` 的差别 | `a.chip` 字重 500（更轻）、圆角 999px（胶囊）、无下划线；`.btn--sm` 字重 600、圆角 10px（控件） | rb.css:206 vs 393–395 |

### 4. 状态矩阵（只写 rb.css 真实存在的状态）

| 状态 | 选择器 | rb.css | 表现 |
| --- | --- | --- | --- |
| 常态 | `a.chip` | 393–395 | 白底 / 边 `#C9C3BC` / 字 `#1C1917` |
| 悬停 | `a.chip:hover` | **396** | 边 `#14665B`、字 `#0F4A42`；无过渡（rb.css 无 `transition`） |
| 键盘焦点 | 全局 `:focus-visible` | 110 | 3px 轮廓（上游 `--focus` L2） |
| 按下 / 禁用 / 选中 / 当前 | — | — | **均不存在**。`a.chip` 没有 `:active`、没有 `[aria-current]`、没有 `[disabled]`（链接不可禁用）。若需「当前项」语义，必须改用 `.navlink[aria-current="page"]` 形态，不得在 chip 上自造 |

### 5. token 消费表（12 个 `chip` 组 token，全覆盖）

| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| 最小高度 | `--chip-min-h` | `44px` | rb.css:393；触控目标下限 |
| 横向内边距 | `--chip-pad-x` | `18px` | rb.css:394 |
| 图标与文字间距 | `--chip-gap` | `6px` | rb.css:394 |
| 圆角 | `--chip-radius` | `999px` | rb.css:394；胶囊身份 |
| 底色 | `--chip-bg` | `#FFFFFF` | rb.css:394 |
| 文字色 | `--chip-fg` | `#1C1917` | rb.css:394 |
| 描边色 | `--chip-border-color` | `#C9C3BC` | rb.css:394 |
| 描边宽度 | `--chip-border-w` | `1px` | rb.css:394（`border:1px solid` 的宽度位） |
| 字重 | `--chip-fw` | `500` | rb.css:395；比 `.btn`（600）轻一档 |
| 悬停描边色 | `--chip-hover-border-color` | `#14665B` | rb.css:396 |
| 悬停文字色 | `--chip-hover-fg` | `#0F4A42` | rb.css:396 |
| 容器子项间距 | `--chips-gap` | `6px` | rb.css:392；`.chips` 的 `gap`，**不是** `--chip-gap` |

**无 L3 token 的规则（仍有锚点）**

| 属性 | 值 | rb.css | 说明 |
| --- | --- | --- | --- |
| 容器布局 | `display:flex` + `flex-wrap:wrap` | 392 | 窄屏自动换行，不横向滚动 |
| 元素布局 | `display:inline-flex` + `align-items:center` | 393 | 图标与文字居中 |
| 去下划线 | `text-decoration:none` | 395 | 链接默认下划线被清除 |

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 元素语义 | 链接入口用 `<a href>`（有链接角色，支持「在新标签打开」「复制链接」）；**触发动作**（填入输入框、提交）必须用 `<button>`，不得用 `a.chip`。冻结原型 S02 三个入口是「点击只填入输入框，不自动提交」（content-spec:65）→ 属动作，用 `.btn--sm` 正确 |
| 可访问名 | 由可见文字提供 |
| 图标 | `aria-hidden="true"` + `focusable="false"` |
| 触控目标 | 44px（`--chip-min-h`，rb.css:393），满足 b-responsive-spec §9.4 的 `<768` 验收项 |
| 键盘 | `<a>` 原生 Tab + Enter；`:focus-visible` 轮廓 3px（rb.css:110） |
| 对比度 | 文字 `#1C1917` / 底 `#FFFFFF` ≥ 4.5:1；hover 文字 `#0F4A42` / 白底亦达标（tokens.md §7 中 `--accent-strong`/卡片底为 PASS） |
| 状态不靠颜色 | `a.chip` 不编码状态（唯一状态差异是 hover 的边色+字色，且 hover 不是语义状态） |
| 容器 | `.chips` 是纯布局容器，不加 `role`；若入口语义上是一组选项，应由外层业务组件补 `role="group"` + `aria-label`，不由本 class 决定 |

### 7. 内容与文案规则

| 位置 | 取值（逐字） | 来源 |
| --- | --- | --- |
| 示例入口 1 | 查今天的课 | content-spec:66 |
| 示例入口 2 | 根据资料回答问题 | content-spec:67 |
| 示例入口 3 | 制定学习计划 | content-spec:68 |
| 引导小字 | 点击只填入输入框，不自动提交。 | content-spec:65 |

- 每个 chip 只放**一个动作短语**，不换行、不折行（长文案属于按钮或链接正文）。
- 示例入口的点击行为固定为「只填入输入框，不自动提交」（content-spec:65）——API 层实现为对 textarea 赋值 + 聚焦，**不得**触发提交。

### 8. 响应式行为

| 档 | 行为 | 依据 |
| --- | --- | --- |
| base（<480） | `.chips` 单行放不下即换行（`flex-wrap:wrap`）；每个 chip 仍 ≥44px 高 | rb.css:392–393 **无 @media** |
| xs ≥480 / sm ≥768 / md ≥1024 / lg ≥1200 / xl ≥1440 | 无变化；不因变宽而改为横向滚动 | b-responsive-spec §4（窄屏示例入口「换行/横滑」，方向 B 选**换行**）、§6 |
| 全部档 | chip 内部间距（`--chip-gap`/`--chips-gap`/`--chip-pad-x`）不随断点变化 | b-responsive-spec §6 |

### 9. 契约依据与禁止事项

- 上游依据：content-spec:65–68（三个示例入口文案与「只填入不提交」行为）；b-responsive-spec §9.4（`.btn` / `a.chip` 在 `<768` 高度 ≥44px 为验收项）。
- **登记（重要）**：`a.chip` 在冻结原型中**没有任何实例**——`.chips` 容器内实际是 `.btn.btn--sm`（assistant.html:43–56、b-responsive.html:637–650）。`a.chip` 属「已在 `rb.css` 登记、token 已定义、但原型未渲染」的契约 class。本规格保留其完整定义（`chip` 组 12 个 token 全部有消费面），但实现者**不得**据此把既有示例入口改写成 `a.chip`（那是行为从「动作」变成「导航」的语义变更）。
- **禁止**：给 `a.chip` 补 `:active` / `[disabled]` / `[aria-current]` 样式——`rb.css` 没有。
- **禁止**：把 `.chips` 的子元素间距写成 `--chip-gap`（容器用的是 `--chips-gap`，两者解析值同为 6px 但语义不同）。
- **禁止**：用 `<button class="chip">`（选择器是 `a.chip`，会完全无样式）。

---

## Pill `.pill`

### 1. 用途与边界

- **是**：**状态胶囊**——用「图标 + 文字 + 颜色」三重表达一个**已确定的业务状态**（完成 / 待确认 / 失败 / 进行中 / 有据 / 建议 / 中性标签）。
- **不是**：不是按钮、不是可点击筛选器（`rb.css` 里 `.pill` 无 `:hover`、无 `cursor:pointer`，且原型里全是 `<span>`）。
- **不是**：不承载长句。胶囊文字是**状态摘要**（≤14 个汉字），解释性句子属于 Notice / `.empty__hint`。
- **不是**：`--warn` / `--pending` **不是**通用「黄色警告」。语义边界见 §9。

### 2. 结构（DOM 骨架）

```html
<!-- 状态胶囊：图标在前，文字在后（rb.css:210 的 gap 生效） -->
<span class="pill pill--ok">
  <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"
       stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
       aria-hidden="true" focusable="false"><path d="M20 6 9 17l-5-5"/></svg>
  完成 · 2 条记录
</span>

<!-- 无修饰类的默认胶囊（中性标签 / 待验证标记） -->
<span class="pill">
  <svg …signpost…></svg>
  〔资料 1〕待验证
</span>
```

- 胶囊图标在冻结原型中统一 **13×13**（少数为 14×14，如 admin.html:233/237），`stroke-width:1.75`，随文字色 `currentColor`。
- 胶囊常内嵌于 `.step__sub`（Steps 章）与 `.notice` 的标题行内（`.row`）。

### 3. API 表

| class | rb.css | 语义 | 强制图标 |
| --- | --- | --- | --- |
| `.pill` | 209–214 | 中性标签 / 待验证标记。底 `#E7E5E4`、字 `#5B544E` | 状态用法需；纯标签用法可省（§9 登记） |
| `.pill--ok` | 215 | **成功 / 已完成** | 勾 `M20 6 9 17l-5-5` |
| `.pill--warn` | 216 | **未保存 / 待确认**（琥珀，见 §9） | 三角警告或旗标 |
| `.pill--pending` | 216 | 与 `--warn` **同一条规则、同一组 token**；语义专指「待确认」 | 同上 |
| `.pill--danger` | 217 | **失败 / 不可恢复 / 已失效** | 圆叉或三角警告 |
| `.pill--info` | 218 | **进行中 / 处理中 / 中性提示** | 进行中弧线或图层图标 |
| `.pill--evidence` | 219 | **有据**（引用已验证 / 计划编号等主色徽标） | 勾或书本 |
| `.pill--advice` | 220 | **一般建议（非资料依据）** / 中性说明 | 火花或省略 |

- `.pill--warn` 与 `.pill--pending` 在 `rb.css:216` 是同一条选择器列表，**没有** `--pill-pending-*` token；`pill` 组 21 个 token 里不存在 pending 专用项。实现时两者可互换，语义靠文字与图标表达。
- `.pill` 无尺寸档、无 `--sm`、无 `[disabled]`。

### 4. 状态矩阵（只写 rb.css 真实存在的状态）

| 状态 | 选择器 | rb.css | 表现 |
| --- | --- | --- | --- |
| 默认（中性） | `.pill` | 209–214 | 底 `#E7E5E4` / 字 `#5B544E` |
| 成功 | `.pill--ok` | 215 | 底 `#ECF2DF` / 字 `#2F4A0D` |
| 警告 = 待确认 | `.pill--warn`, `.pill--pending` | 216 | 底 `#FBF0DF` / 字 `#8A4107` |
| 危险 | `.pill--danger` | 217 | 底 `#FBE7EC` / 字 `#7B0E2C` |
| 信息 | `.pill--info` | 218 | 底 `#E3EEF2` / 字 `#164A5B` |
| 依据 | `.pill--evidence` | 219 | 底 `#E3EDEB` / 字 `#0F4A42` |
| 建议 | `.pill--advice` | 220 | 底 `#E7E5E4` / 字 `#5B544E`（与默认同值，语义靠图标+文字区分） |
| 悬停 / 按下 / 禁用 / 焦点 | — | — | **全部不存在**。`.pill` 不是可交互元素；不写 `cursor:pointer`、不进 Tab 序 |

**「图标 + 文字 + 颜色」三重：颜色只占 1/3，禁止只靠颜色区分状态。** 图标与文字来源见下表。

| 变体 | 图标（Lucide 名 · 冻结原型出处） | 文字（逐字来源） |
| --- | --- | --- |
| `.pill--ok` | `check`（assistant.html:131/262、records.html:203 后置） | 「完成 · 2 条记录」「完成 · 3 个片段」「已保存 · 计划编号 plan_7Q2F9K」（content-spec:74/75/107） |
| `.pill--warn` / `--pending` | `triangle-alert`（assistant.html:408）、`signpost`（assistant.html:559 待确认、assistant.html:480 未保存） | 「未保存」（content-spec:100）、「待确认 · 写入结果未知」（content-spec:109）、「需确认后继续」（content-spec:167–170 场景） |
| `.pill--danger` | `circle-x`（assistant.html:375/434）、`triangle-alert`（admin.html:374） | 「失败 · 未取得片段」「引用已失效」「不可恢复」（content-spec:79/89/138） |
| `.pill--info` | `loader-circle`（assistant.html:155 进行中、admin.html:232/302 处理中） | 「进行中」（content-spec:76）、「处理中」（content-spec:155） |
| `.pill--evidence` | `check`（assistant.html:175/282）、`book`（assistant.html:343） | 「已验证引用」（content-spec:78）、「〔资料 1〕」（content-spec:78/85） |
| `.pill--advice` | `sparkles`（assistant.html:358） | 「一般学习建议（非资料依据）」（content-spec:88） |
| `.pill`（默认） | `signpost`（assistant.html:171）、`inbox`（assistant.html:455） | 「〔资料 1〕待验证」（content-spec:78）、「尚无已发布资料」（content-spec:95） |

### 5. token 消费表（21 个 `pill` 组 token，全覆盖）

| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| 默认底色 | `--pill-bg` | `#E7E5E4` | rb.css:213 |
| 默认文字色 | `--pill-fg` | `#5B544E` | rb.css:213 |
| 字号 | `--pill-fs` | `13px` | rb.css:211；字阶最低档 |
| 字重 | `--pill-fw` | `600` | rb.css:211 |
| 行高 | `--pill-lh` | `1.6` | rb.css:211；胶囊专用紧凑行高（上游 `--p-lh-control`） |
| 纵向内边距 | `--pill-pad-y` | `2px` | rb.css:212；像素级微调档 |
| 横向内边距 | `--pill-pad-x` | `10px` | rb.css:212 |
| 图标与文字间距 | `--pill-gap` | `5px` | rb.css:210 |
| 圆角 | `--pill-radius` | `999px` | rb.css:212 |
| 成功底 | `--pill-ok-bg` | `#ECF2DF` | rb.css:215 |
| 成功字 | `--pill-ok-fg` | `#2F4A0D` | rb.css:215 |
| 警告/待确认底 | `--pill-warn-bg` | `#FBF0DF` | rb.css:216（`--warn` 与 `--pending` 共用） |
| 警告/待确认字 | `--pill-warn-fg` | `#8A4107` | rb.css:216 |
| 危险底 | `--pill-danger-bg` | `#FBE7EC` | rb.css:217 |
| 危险字 | `--pill-danger-fg` | `#7B0E2C` | rb.css:217 |
| 信息底 | `--pill-info-bg` | `#E3EEF2` | rb.css:218 |
| 信息字 | `--pill-info-fg` | `#164A5B` | rb.css:218 |
| 依据底 | `--pill-evidence-bg` | `#E3EDEB` | rb.css:219 |
| 依据字 | `--pill-evidence-fg` | `#0F4A42` | rb.css:219 |
| 建议底 | `--pill-advice-bg` | `#E7E5E4` | rb.css:220（与默认底同值） |
| 建议字 | `--pill-advice-fg` | `#5B544E` | rb.css:220（与默认字同值） |

**无 L3 token 的规则（仍有锚点）**

| 属性 | 值 | rb.css | 说明 |
| --- | --- | --- | --- |
| 布局 | `display:inline-flex` + `align-items:center` | 210 | 图标与文字同一基线组，随文字宽 |

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 元素 | 纯展示 → `<span class="pill …">`，**不可交互、不进 Tab 序**（rb.css 无 `cursor:pointer`，原型全部为 `span`） |
| 状态三重 | 每个状态胶囊必须同时有：**内联 SVG 图标** + **状态文字** + **色彩**。颜色是辅助通道，不是唯一通道（content-spec §1 第 1 行；b-responsive-spec §7） |
| 图标 | `aria-hidden="true" focusable="false"`；可访问名**只来自文字**，图标不得承载唯一信息 |
| 文字 | 状态文字必须是完整短句状态（「完成 · 2 条记录」），**禁止**只写数字或只写「✓」 |
| 对比度 | 7 组文字/底全部 ≥4.5:1（tokens.md §7 实测）：默认/建议 5.92:1、成功 8.70:1、警告 6.56:1、危险 9.14:1、信息 8.21:1、依据 8.46:1，全部 PASS |
| 朗读 | 胶囊内嵌在句子中时（如 assistant.html:271 的〔资料 1〕），文字应可被连续朗读，不打断句子；不要给胶囊加 `role="status"`（它不是 live region） |
| 动态更新 | 状态由「进行中」变为「完成」时，胶囊本身不做 live 播报；播报交由外层（Steps 摘要 / 对话区）负责，避免重复播报 |

### 7. 内容与文案规则

| 场景 | 逐字文案 | 来源 |
| --- | --- | --- |
| 步骤完成 | 完成 · 2 条记录 / 完成 · 3 个片段 | content-spec:74/75 |
| 步骤进行中 | 进行中 | content-spec:76 |
| 步骤失败 | 失败（不得显示完成勾） | content-spec:79 |
| 未保存 | 未保存 | content-spec:100 |
| 保存成功 | 已保存 · 计划编号 plan_7Q2F9K | content-spec:107 |
| 结果待确认 | 正在确认是否保存… + 待确认 · 写入结果未知 | content-spec:109 |
| 引用 | 已验证引用 / 〔资料 1〕待验证 | content-spec:83/78 |
| 引用失效 | 引用已失效 | content-spec:89 |
| 内容性质 | 课程规定 / 一般学习建议（非资料依据） | content-spec:88 |
| 文档状态 | 可检索 / 处理中 / 失败 / 删除中 / 删除失败 | content-spec:154–158 |
| 依据不足 | 检索成功 · 没有足够依据 | content-spec:92 |
| 全库为空 | 尚无已发布资料 | content-spec:95 |

- 分隔符统一用 `·`（U+00B7）加前后空格。
- **禁止**：无根因的占位词（「加载中」「未知状态」之类）与 content-spec §3 明列的禁用表述。
- 长度上限：胶囊文字 ≤ 14 个汉字（超出则下沉为 Notice 正文）。

### 8. 响应式行为

| 档 | 行为 | 依据 |
| --- | --- | --- |
| base（<480） | 随文字收缩；内嵌在 `.step__sub` 内且该行放不下时，靠 `.step{flex-wrap:wrap}`（rb.css:247）换到下一行 | rb.css:209–220 **无 @media** |
| xs ≥480 / sm ≥768 / md ≥1024 / lg ≥1200 / xl ≥1440 | 无变化；字号恒为 13px，内边距恒为 2px/10px | b-responsive-spec §6「组件内部间距保持不变」 |
| 全部档 | 不设 `max-width`、不做截断；长文案由调用方改写，不靠 CSS 省略号 | rb.css 无 `text-overflow` |

### 9. 契约依据与禁止事项

**琥珀语义边界（硬性，写死）**

- `--pill-warn-*`（解析值 `#FBF0DF` / `#8A4107`）与 `.pill--pending`：**只允许表达「未保存 / 待确认」两类语义**。
  - 「未保存」= 草稿存在但未提交（content-spec:100）。
  - 「待确认」= 写入结果未知 / 需要人工确认后继续（content-spec:109、167–170）。
- 上游依据：`rb.css:27` 的原始注释「琥珀：专用于「未保存 / 待确认」」，以及 `tokens.json` → `primitive.color.pending` 的说明「琥珀：**专用于「未保存 / 待确认」**，不得用于其他语义」。
- **禁止**用它表达：一般警告、性能提示、信息不足、超时、离线、表单校验错误（后者属 `.field__error` / `.notice--danger` / `.error-summary`）。

> ⚠️ **与冻结原型的差异（必须由 Lead 裁决，登记不改写）**：冻结原型有 3 处把琥珀胶囊用在了「未保存 / 待确认」之外的语义上——
> `assistant.html:407`（`pill--warn` → 「检索成功 · 没有足够依据」）、
> `admin.html:232`（`pill--warn` → 「处理中」，批次）、
> `admin.html:302`（`pill--warn` → 「处理中」，文件）。
> 这两处「处理中」与 `.pill--info`（assistant.html:155 的「进行中」）语义重复。
> 本规格按题面契约把边界写死为「未保存 / 待确认」；上述 3 处属冻结产物中的既有用法，**不在本轮修改范围**，
> 交由 Lead 决定是「改原型」还是「扩边界」。实现者遇到「处理中 / 依据不足」时**用 `.pill--info`**。

**其它禁止事项**

- **禁止**：给胶囊加 `:hover` / `:active` / `cursor:pointer`——三个都不是可交互元素。
- **禁止**：只用颜色区分（例如同一行放两个仅底色不同的胶囊而不写文字差异）。
- **禁止**：把 `.pill--advice` 与 `.pill` 当作两种视觉（解析值完全相同：`#E7E5E4` / `#5B544E`），它们的区别**只在语义与图标**。
- **禁止**：发明 `--pill-pending-bg` / `--pill-pending-fg` —— `pill` 组没有这两个 token。
- **登记（图标缺失，属硬要求违例）**：冻结原型有 4 处无图标胶囊——`records.html:30`（`pill--advice`「单次最多查询 31 天」）、`admin.html:118`（`pill--info`「编辑 CS201 …」）、`admin.html:586`（`pill`「请核对 …」）、`records.html:273`（**`pill--danger`「不可恢复」**）。前 3 处属「中性标签」用法（无状态语义），可省图标；**`records.html:273` 带危险状态语义却缺图标**，违反「图标+文字+颜色」三重，登记为待补（建议补 `circle-x`）。

---

## Notice `.notice`

### 1. 用途与边界

- **是**：**块级提示**——承载一句到一段的解释性信息，且**必须带图标**（`.notice__ico` 是结构的一部分，不是可选项）。
- **是**：可容纳标题 + 正文 + 动作按钮（`.notice` 内嵌 `.stack` / `.row`，如 assistant.html:28–36、551–570）。
- **不是**：不是状态胶囊（那是 Pill）；不是空状态（那是 Empty）。三者边界：**胶囊 = 状态摘要**、**提示块 = 解释 + 动作**、**空状态 = 整块区域无内容**。
- **不是**：不承载表单字段级错误——字段错误用 `.field__error`（rb.css:318）与 `.error-summary`（rb.css:329）。

### 2. 结构（DOM 骨架）

```html
<!-- A. 图标用 <span class="notice__ico"> 包裹（assistant.html:24-37） -->
<div class="notice notice--info" role="note">
  <span class="notice__ico">
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
         stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
         aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
  </span>
  <div class="stack">
    <p>对话只保存在当前浏览器标签页，刷新或关闭后不会恢复；已保存的计划不受影响。</p>
    <div class="row">
      <button class="btn btn--ghost btn--sm" type="button">…清空对话</button>
    </div>
  </div>
</div>

<!-- B. 图标直接挂 class（admin.html:248-251）——两种形态都合法 -->
<div class="notice notice--danger" role="alert">
  <svg class="notice__ico" width="24" height="24" viewBox="0 0 24 24" … aria-hidden="true" focusable="false">…</svg>
  <span><b>本批 1 个文件失败，整批未发布；其他批次不受影响。</b>…</span>
</div>
```

- `.notice` 是 `display:flex` 且**没有 `flex-wrap`**（rb.css:223）：图标与内容列并排；内容列内部用 `.stack` / `.row` 自行换行。
- 图标实例尺寸：22×22（assistant.html:26/402/531/553）、20×20（admin.html:173/249/507/524 用行内 `style` 覆盖）。content-spec §0 的 24×24 是**路径坐标系**，实例尺寸可缩放。
- 段内强调用 `<b>`：`rb.css:231` 强制 `color:inherit`，因此强调**不改变颜色**，只加粗。

### 3. API 表

| class | rb.css | 语义 | 角色建议 |
| --- | --- | --- | --- |
| `.notice` | 223–224 | 中性提示块。底 `#E7E5E4`、字 `#1C1917`、下外边距 18px | `role="note"` |
| `.notice__ico` | 225 | 图标槽：`flex:0 0 auto` + `margin-top:2px`（与首行文字视觉对齐） | 装饰，`aria-hidden="true"` |
| `.notice--info` | 226 | 信息 / 边界说明（对话不持久化） | `role="note"` |
| `.notice--warn` | 227 | 警告：需确认后继续 / 依据不足 | 需用户确认时 `role="alert"` |
| `.notice--danger` | 228 | 危险 / 失败（登录失败、整批回滚、删除确认） | `role="alert"` |
| `.notice--ok` | 229 | 成功（已保存 · 计划编号） | `role="status"` 或无 |
| `.notice--evidence` | 230 | 依据/引用类强调块 | `role="note"` |
| `.notice b` | 231 | 段内强调，`color:inherit` | — |

### 4. 状态矩阵（只写 rb.css 真实存在的状态）

| 状态 | 选择器 | rb.css | 表现 |
| --- | --- | --- | --- |
| 中性 | `.notice` | 223–224 | 底 `#E7E5E4` / 字 `#1C1917` |
| 信息 | `.notice--info` | 226 | 底 `#E3EEF2` / 字 `#164A5B` |
| 警告 | `.notice--warn` | 227 | 底 `#FBF0DF` / 字 `#8A4107`（琥珀，边界见 §9） |
| 危险 | `.notice--danger` | 228 | 底 `#FBE7EC` / 字 `#7B0E2C` |
| 成功 | `.notice--ok` | 229 | 底 `#ECF2DF` / 字 `#2F4A0D` |
| 依据 | `.notice--evidence` | 230 | 底 `#E3EDEB` / 字 `#0F4A42` |
| 悬停 / 按下 / 禁用 / 焦点 | — | — | **全部不存在**。`.notice` 是静态容器；块内按钮自己带焦点与 hover 行为 |
| 变体并列 | 多个 `.notice` 相邻 | 224 | 每个自带 `margin-bottom:18px`，形成纵向节奏；≥sm 并排需外部 `.card-row--2`（rb.css:182） |

### 5. token 消费表（17 个 `notice` 组 token，全覆盖）

| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| 默认底色 | `--notice-bg` | `#E7E5E4` | rb.css:224 |
| 默认文字色 | `--notice-fg` | `#1C1917` | rb.css:224 |
| 图标与内容列间距 | `--notice-gap` | `12px` | rb.css:223 |
| 内边距 | `--notice-pad` | `18px` | rb.css:223（四边同值） |
| 圆角 | `--notice-radius` | `10px` | rb.css:223 |
| 下外边距 | `--notice-margin-b` | `18px` | rb.css:224（`margin:0 0 18px`） |
| 图标上偏移 | `--notice-ico-offset-y` | `2px` | rb.css:225；让图标与首行文字对齐基线 |
| 信息底 | `--notice-info-bg` | `#E3EEF2` | rb.css:226 |
| 信息字 | `--notice-info-fg` | `#164A5B` | rb.css:226 |
| 警告底 | `--notice-warn-bg` | `#FBF0DF` | rb.css:227 |
| 警告字 | `--notice-warn-fg` | `#8A4107` | rb.css:227 |
| 危险底 | `--notice-danger-bg` | `#FBE7EC` | rb.css:228 |
| 危险字 | `--notice-danger-fg` | `#7B0E2C` | rb.css:228 |
| 成功底 | `--notice-ok-bg` | `#ECF2DF` | rb.css:229 |
| 成功字 | `--notice-ok-fg` | `#2F4A0D` | rb.css:229 |
| 依据底 | `--notice-evidence-bg` | `#E3EDEB` | rb.css:230 |
| 依据字 | `--notice-evidence-fg` | `#0F4A42` | rb.css:230 |

**无 L3 token 的规则（仍有锚点）**

| 属性 | 值 | rb.css | 说明 |
| --- | --- | --- | --- |
| 布局 | `display:flex`（**无 `flex-wrap`**） | 223 | 图标与内容列并排；换行由内容列的 `.stack`/`.row` 负责 |
| 图标不收缩 | `flex:0 0 auto` | 225 | 长文本下图标不被压扁 |
| 段内强调 | `color:inherit` | 231 | `<b>` 只加粗不改色 |

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 角色 | 静态说明 `role="note"`（assistant.html:24）；**需要立即被读到**的失败/警告用 `role="alert"`（login.html:45、admin.html:172/248/506/523）。成功态可用 `role="status"`，不要用 `alert` |
| 图标 | `.notice__ico` 一律 `aria-hidden="true"`（`<span>` 形态还需在其内部 svg 上同理），文本必须独立可读 |
| 可访问名 | 无。提示块不是控件；其内容就是可读文本 |
| 键盘 | 容器不可聚焦；**块内按钮**照常可 Tab（content-spec §1） |
| 焦点不被遮挡 | 提示块内的按钮聚焦时不得被吸底 `.composer` 遮挡（b-responsive-spec §7，WCAG 2.2 2.4.11） |
| 触控目标 | 块内 `.btn--sm` 仍为 44px（rb.css:206）；`.btn--ghost.btn--sm` 组合在原型中每处都 ≥44px |
| 对比度 | 6 组文字/底全部 ≥4.5:1（tokens.md §7 实测）：中性 13.93:1、信息 8.21:1、警告 6.56:1、危险 9.14:1、成功 8.70:1，全部 PASS |
| 状态不靠颜色 | 变体差异除底色外**必须**有：图标形状 + 标题文字（「已保存」/「正在确认是否保存…」/「依据不足」）+ 动作按钮文案 |
| 语序 | 图标在前、文字在后（rb.css:223 的 flex 顺序）；`role="alert"` 的内容必须自解释（不含「见上文」） |

### 7. 内容与文案规则

| 场景 | 逐字文案 | 来源 |
| --- | --- | --- |
| 对话不持久化（info） | 对话只保存在当前浏览器标签页，刷新或关闭后不会恢复；已保存的计划不受影响。 | content-spec:64 |
| 登录失败（danger） | 账号或密码不正确，请重试。 | content-spec:56 |
| 账号禁用（danger） | 当前账号不可用，请联系管理员。 | content-spec:59 |
| 依据不足（warn） | 已检索共享资料，但没有找到足以回答这项要求的内容。 | content-spec:92 |
| 检索失败（danger） | 课程资料暂时无法查询，请稍后重试。 | content-spec:94 |
| 保存成功（ok） | 已保存 · 计划编号 plan_7Q2F9K | content-spec:107 |
| 待确认（warn） | 正在确认是否保存… + 写入结果尚未确认，请勿重复创建；可稍后查询状态。 | content-spec:109 |
| 整批回滚（danger） | 本批 1 个文件失败，整批未发布；其他批次不受影响。 | content-spec:159 |
| 停用确认（warn） | 停用后不能再为该课程新增课表记录；已有课表和计划仍可查看。 | content-spec:147 |
| 时间重叠确认（warn） | 与 2026-10-22 10:00–11:40 大学英语 时间重叠。 | content-spec:168 |
| 版本冲突（danger） | 这份计划已被其他标签页修改，请重新加载后再提交；你未提交的编辑会保留。 | content-spec:137 |

- 结构约定：**标题（可选，`<h3>`）+ 正文 + 动作行**；危险/警告变体的正文必须写清**后果**与**下一步**。
- 段内强调只用 `<b>`（rb.css:231 保色），**禁止**用 `<strong style>` 或内联色。
- `.notice--evidence` 在冻结原型中**无实例**（`rb.css:230` 已定义、`notice` 组 token 已配齐）→ 属契约预置变体，可用但不得据此改动既有页面。

### 8. 响应式行为

| 档 | 行为 | 依据 |
| --- | --- | --- |
| base（<480） | 占满容器宽；内边距恒 18px；图标与内容列并排 | rb.css:223–231 **无 @media** |
| xs ≥480 / sm ≥768 / md ≥1024 / lg ≥1200 / xl ≥1440 | 无变化 | b-responsive-spec §6 |
| 并排（≥sm） | 两个 notice 并排由外部容器 `.card-row--2` 完成（rb.css:182，`≥768` 转 2 列），**不是** notice 自己的能力 | b-responsive-spec §4（S08 两态、S10 并排说明） |
| 全部档 | 窄屏下内容列必须能收缩（`.notice` 无 `flex-wrap`）：内容列内长串（文件名 / 编号）用 `.mono` + 允许换行，不得依赖 `word-break:break-all` | content-spec §1 长文本行 |

### 9. 契约依据与禁止事项

- 上游依据：content-spec §1（危险操作用语义危险色 + 二次确认）、§2-S06（保存成功 / 待确认）、§2-S11（整批回滚）；b-responsive-spec §7（状态不靠颜色）。
- **边界**：`.notice--warn`（rb.css:227）与 `--pill-warn-*` 解析值同源（`#FBF0DF` / `#8A4107`，上游 `--state-warning-*` 直取同一组琥珀 primitive）。**Pill 章的「琥珀只用于未保存/待确认」硬边界按题面只约束 `--pill-warn-*` / `--pending*`**；`--notice-warn-*` 在冻结原型中还承载「依据不足」「确认后继续」（assistant.html:400、admin.html:172、admin.html:523）。本规格不做扩张性解释：**notice--warn 的允许语义 = 需用户确认或需说明风险**，且必须配警告图标与完整句文案。这条与 Pill 的差异已在 Pill §9 登记，交由 Lead 统一。
- **禁止**：写无图标的 `.notice`——`.notice__ico` 是结构性要求（rb.css:225 为它单独定义了对齐规则）。
- **禁止**：给 `.notice` 加 `:hover` / 可点击行为 / `cursor:pointer`。
- **禁止**：用 `.notice--ok` 表达「一切正常」（无事件不提示）；成功提示只在一次写入/保存完成后出现。
- **禁止**：发明 `--notice-evidence-ico-*` 之类 token；消费面恰好是 §5 的 17 个。

---

## Steps `.steps` / `.step`

### 1. 用途与边界

- **是**：**内联在对话里的过程反馈**（方向 B 的过程反馈形态，不用右侧面板）。展示「本轮执行」的**可核实工具动作**清单，每步三态：进行中 / 完成 / 失败。
- **是**：只允许出现三类**可核实工具动作**（PRD §11.2 / SRS IF-008 白名单）：
  `get_my_schedule`、`search_course_docs`、`save_study_plan`。
- **不是**：**不得**表达模型内部过程。禁止任何把「推理 / 理解 / 分析」当步骤的写法——步骤标题只能是白名单动作的动作名（content-spec:73 与 content-spec §3 列出了禁用表述原文，本规格不复述）。
- **不是**：不是进度百分比控件（无 token、无样式）；不是可折叠手风琴的通用容器（折叠仅一种：摘要 ↔ 步骤体）。

### 2. 结构（DOM 骨架）

```html
<!-- 三个兄弟元素，顺序不可换：checkbox → label → ol -->
<input type="checkbox" class="sr-only steps__toggle" id="s03-steps-toggle">
<label class="steps__summary" for="s03-steps-toggle">
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
       stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
       aria-hidden="true" focusable="false"><path d="m9 18 6-6-6-6"/></svg>
  本轮执行 · 3 项动作（1 项进行中）
</label>
<ol class="steps steps__body">
  <li class="step step--done">
    <span class="step__ico"><svg …circle-check… aria-hidden="true" focusable="false">…</svg></span>
    <span class="step__title">正在读取课表</span>
    <span class="step__sub">明天 2026-10-22（周四）
      <span class="pill pill--ok">…完成 · 2 条记录</span>
    </span>
  </li>
  <li class="step step--running"> …正在拟定计划草稿… </li>
  <li class="step step--failed"> …正在检索课程资料… </li>
</ol>
```

**结构硬约束（来自 rb.css 的机械前提）**

1. `.steps` 与 `.steps__body` 必须是**同一个元素**：`<ol class="steps steps__body">`。rb.css:261 的 `display:none` 与 rb.css:245 的 `display:flex;flex-direction:column` 靠**同特异性 + 源码顺序**决出（261 在后，故默认隐藏），rb.css:263 在 `≥480` 再改回 `flex`（列向仍来自 245）。
2. `input.steps__toggle` 必须是 `.steps__body` 的**前序兄弟**，中间可隔 `<label>`：rb.css:262 用 `~` 兄弟选择器。
3. `.steps__toggle` 用 `.sr-only`（rb.css:113–114）视觉隐藏；它**仍在 Tab 序内**，用 Space 切换。
4. 折叠态下**必须**由 `.steps__summary` 文字承载步骤数量与关键状态（如「本轮执行 · 3 项动作（1 项进行中）」），否则窄屏用户看不到任何状态。

### 3. API 表

| class / 元素 | rb.css | 用途 |
| --- | --- | --- |
| `.steps` | 245–246 | `<ol>` 容器：去列表符、左侧 2px 竖轨 + 18px 缩进、纵向 6px 间距 |
| `.steps__body` | 261–263 | 与 `.steps` 同元素；`<480` 隐藏、`≥480` 常显 |
| `.steps__toggle` | 262 | `<input type="checkbox">` + `.sr-only`；`:checked` 时展开 |
| `.steps__summary` | 259–260, 263 | `<label for>` 摘要行，44px 高；`≥480` 隐藏 |
| `.step` | 247 | `<li>`：图标 + 标题 + 副行的横向 flex，允许换行 |
| `.step__ico` | 248, 253 | 图标槽；`--running` 时旋转 |
| `.step__title` | 249, 252, 255 | 动作名（字重 600） |
| `.step__sub` | 250–251, 255 | 参数/结果副行；`flex:1 1 100%` 强制换到下一行 |
| `.step--running` | 252–253 | 进行中：标题回正文字色，图标旋转 |
| `.step--done` | 254 | 完成：整步文字降为次级色 |
| `.step--failed` | 255 | 失败：标题与副行用危险色 |
| `@keyframes spin` | 256 | `to{transform:rotate(360deg)}`；被 rb.css:111 的 reduced-motion 复位关闭 |

**白名单与状态文案映射（写死）**

| 工具（白名单） | 步骤标题（逐字，content-spec） | 允许的结果胶囊 |
| --- | --- | --- |
| `get_my_schedule` | 正在读取课表（content-spec:74） | `pill--ok`「完成 · N 条记录」/ `pill--danger`「失败 · …」 |
| `search_course_docs` | 正在检索课程资料（content-spec:75） | `pill--ok`「完成 · N 个片段」/ `pill--danger`「失败 · 未取得片段」 |
| `save_study_plan` | 正在拟定计划草稿（content-spec:76）；保存阶段为「正在确认是否保存…」（content-spec:109） | `pill--info`「进行中」/ `pill--warn`「待确认 · 写入结果未知」/ `pill--ok`「已保存 · 计划编号 …」 |

- 标题保持「正在 + 动词」的**动作名**形态（完成态也是「正在读取课表」，结果由胶囊表达）——这是 content-spec:74–76 的逐字写法，**不得**改写成「已读取课表」。
- 每轮**至多一项** `step--running`（content-spec:76 明确「唯一的进行中项」）。

### 4. 状态矩阵（只写 rb.css 真实存在的状态）

| 状态 | 选择器 | rb.css | 表现 |
| --- | --- | --- | --- |
| 进行中 | `.step--running .step__title` | 252 | 标题色回到正文字色（其余步骤标题继承已完成/常态色） |
| 进行中（图标） | `.step--running .step__ico` | 253 | `animation:spin 1.1s linear infinite`；`prefers-reduced-motion:reduce` 下被 rb.css:111 关闭 → 退化为静态图标 |
| 完成 | `.step--done` | 254 | 整步 `color` 降为次级色 `#5B544E`（标题与副行同时变浅） |
| 失败 | `.step--failed .step__title`, `.step--failed .step__sub` | 255 | 标题与副行用危险色 `#7B0E2C`；**不得显示完成勾**（content-spec:79） |
| 展开 | `.steps__toggle:checked ~ .steps__body` | 262 | `<480` 下由隐藏变 `display:flex` |
| 折叠 | `.steps__body`（默认） | 261 | `<480` 默认隐藏；`≥480` 恒显示（263） |
| 悬停 / 按下 / 禁用 / 焦点环 | — | — | **均不存在**。`.step` 不是控件；可聚焦的只有 `.steps__toggle`，其焦点环见 §6 已知缺口 |

- 三态由**类名**驱动，不由颜色驱动：`--running` / `--done` / `--failed` 必须显式写类，不得靠 CSS 推断。

### 5. token 消费表（13 个 `steps` 组 token，全覆盖）

| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| 步骤纵向间距 | `--steps-gap` | `6px` | rb.css:245 |
| 左侧竖轨宽度 | `--steps-rail-w` | `2px` | rb.css:246（`border-left:2px`） |
| 左侧竖轨颜色 | `--steps-rail-color` | `#E7E5E4` | rb.css:246 |
| 竖轨缩进 | `--steps-indent` | `18px` | rb.css:246（`padding-left:18px`） |
| 图标与内容间距 | `--step-gap` | `12px` | rb.css:247 |
| 图标上偏移 | `--step-ico-offset-y` | `3px` | rb.css:248；与首行文字对齐 |
| 副行字号 | `--step-sub-fs` | `15px` | rb.css:250 |
| 副行文字色 | `--step-sub-fg` | `#5B544E` | rb.css:250 |
| 失败色 | `--step-failed-fg` | `#7B0E2C` | rb.css:255；同时作用于 `.step__title` 与 `.step__sub` |
| 摘要行最小高度 | `--steps-min-h` | `44px` | rb.css:259；= 触控目标 |
| 摘要行字号 | `--steps-summary-fs` | `15px` | rb.css:260 |
| 摘要行文字色 | `--steps-summary-fg` | `#5B544E` | rb.css:260 |
| 摘要行图标间距 | `--steps-summary-gap` | `6px` | rb.css:259（`gap:6px`） |
| **running 旋转时长** | `--step-running-spin-duration` | `1100ms` | rb.css:253。**收口时补齐**：组件规则只能消费 L3，而 `--motion-spin-duration` 在 L2 跨层取不到，此前只能不写 duration（动画不会真的转） |
| **running 旋转缓动** | `--step-running-spin-easing` | `linear` | rb.css:253，同属收口补齐项 |

**无 L3 token 的规则（仍有锚点；含 2 处 rb.css 直取 L2 —— 上游登记）**

| 属性 | 值 | rb.css | 说明 |
| --- | --- | --- | --- |
| 容器去列表符 | `list-style:none; margin:0; padding:0` | 245 | `<ol>` 语义保留，视觉去符 |
| 容器方向 | `display:flex; flex-direction:column` | 245 | `≥480` 由 263 恢复 `display:flex` 时仍沿用列向 |
| 单步布局 | `display:flex; align-items:flex-start; flex-wrap:wrap` | 247 | 副行靠 `flex:1 1 100%` 换行 |
| 副行占满整行 | `flex:1 1 100%` | 250 | 副行永远另起一行，避免与标题挤在一行 |
| 副行长文本 | `overflow-wrap:break-word` | 251 | 课程名/文件名允许换行（content-spec §1） |
| 标题字重 | `font-weight:600` | 249 | 动作名加粗 |
| 进行中标题色 | `color:var(--text-primary)` | 252 | **上游（L2）直取**；无 `--step-running-fg` token |
| 完成态文字色 | `color:var(--text-secondary)` | 254 | **上游（L2）直取**；无 `--step-done-fg` token，解析值同 `--step-sub-fg`（`#5B544E`） |
| 旋转动画 | `animation:spin 1.1s linear infinite` | 253 | 时长 `1.1s` 是 rb.css 的**裸字面量**，`steps` 组无对应 token；reduced-motion 关闭（111） |

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 结构 | 步骤列表用 `<ol>`（顺序有意义）；`.steps` 与 `.steps__body` 同元素，不额外套一层 |
| 折叠控件 | `<input type="checkbox" class="sr-only steps__toggle">` + `<label class="steps__summary" for>`：标签文字即 checkbox 的可访问名（必须含「本轮执行」与步骤数量）；键盘用 Space 切换 |
| 摘要文字 | 折叠态下摘要**必须**能独立说明过程（数量 + 进行中/失败项数），这是 `<480` 唯一可见的信息 |
| 图标 | `.step__ico`、摘要行箭头一律 `aria-hidden="true" focusable="false"`；**步骤状态不得只靠图标**——`.step__sub` 内必须有文本胶囊（`pill--ok`/`--danger`/`--info`） |
| 触控目标 | `.steps__summary` 44px（`--steps-min-h`，rb.css:259） |
| 动效 | 只有 `.step--running .step__ico` 旋转；`prefers-reduced-motion:reduce` 下 rb.css:111 全局关闭（`animation:none!important`）→ 必须有**静态替代**（不同图标形状），不得让「进行中」只能靠动画表达 |
| 状态三重 | 每步 = 图标（`.step__ico`）+ 文字（`.step__title` + `.step__sub` 内的胶囊）+ 颜色（`.step--*` 与胶囊底色） |
| 对比度 | 副行 `#5B544E` / 卡片底达标；失败色 `#7B0E2C` / 卡片底达标（tokens.md §7 危险胶囊 9.14:1） |
| ⚠ 已知缺口 | `.steps__toggle` 被 `.sr-only` 的 `clip:rect(0 0 0 0)` 裁掉（rb.css:113–114），全局 `:focus-visible`（rb.css:110）的 3px 轮廓画在 1×1px 被裁元素上 → **键盘焦点视觉不可见**（WCAG 2.2 2.4.7 / 2.4.11 风险）。`rb.css` 未提供 `.steps__toggle:focus-visible ~ .steps__summary` 的焦点补偿。本规格**登记为待修**（需新增强调 token 并重跑 rb.css 等价性验证），不在本轮改 `rb.css` |

### 7. 内容与文案规则

| 位置 | 逐字文案 | 来源 |
| --- | --- | --- |
| 过程区标题 | 本轮执行 | content-spec:73 |
| 步骤① 标题 | 正在读取课表 | content-spec:74 |
| 步骤① 结果 | 完成 · 2 条记录 | content-spec:74 |
| 步骤② 标题 | 正在检索课程资料 | content-spec:75 |
| 步骤② 结果 | 完成 · 3 个片段 | content-spec:75 |
| 步骤③ 标题 | 正在拟定计划草稿 | content-spec:76 |
| 步骤③ 状态 | 进行中（唯一进行中项） | content-spec:76 |
| 失败结果 | 失败（且不得显示完成勾） | content-spec:79 |
| 顶部状态行 | 正在处理 · 最长 60 秒 | content-spec:77 |
| 待确认 | 正在确认是否保存… | content-spec:109 |

- **违禁表述（绝对禁止）**：任何把推理 / 理解 / 分析过程当步骤的措辞（原文清单见 content-spec:73 与 §3，本规格不复述）。判据：步骤标题必须能在白名单三工具中找到对应动作，且能在 content-spec 找到逐字出处。
- 步骤标题只允许白名单三动作的动作名；出现第四种动作名即视为越界（PRD §11.2 / SRS IF-008）。
- 摘要文案格式固定为 `本轮执行 · N 项动作（M 项进行中）`；全部完成时写 `本轮执行 · 完成 · N 项动作`（assistant.html:240 逐字形态）。

### 8. 响应式行为

| 档 | 行为 | 依据 |
| --- | --- | --- |
| base（<480） | **默认折叠**：`.steps__summary` 可见（44px 高），`.steps__body` `display:none`；勾选后步骤体展开 | rb.css:261–262 |
| xs ≥480 | **常显**：`.steps__summary` `display:none`，`.steps__body` `display:flex`（列向来自 rb.css:245） | rb.css:263；b-responsive-spec §4「过程区由折叠转常显」 |
| sm ≥768 / md ≥1024 / lg ≥1200 / xl ≥1440 | 无额外变化；`.steps` 始终内联在对话列内（720px 助手列，b-responsive-spec §2） | b-responsive-spec §4「方向 B 的过程反馈内联在对话里，不用右侧面板」 |
| 全部档 | 组件内部间距固定（`--steps-gap` 6px / `--step-gap` 12px / `--steps-indent` 18px），不随断点变化 | b-responsive-spec §6 |
| 390×844（SRS 指定尺寸） | 过程区折叠为一行摘要、可展开；输入区吸底不受影响 | content-spec:174；b-responsive-spec §9 |

### 9. 契约依据与禁止事项

- 上游依据：content-spec:73–79（过程区文案与三态）、content-spec:174（390 折叠为一行摘要）；b-responsive-spec §4（`.steps` 折叠/常显）、§7（仅步骤条进行中图标旋转，reduced-motion 关闭）。
- **禁止**（工具白名单）：展示白名单之外的动作；出现任何推理过程类表述；把步骤数当作进度百分比。
- **禁止**：给 `.step` 加 `:hover` / 点击 / `cursor:pointer`。
- **禁止**：完成态改写标题时态（保持「正在读取课表」+ 胶囊「完成 · 2 条记录」）。
- **禁止**：失败步骤显示完成勾图标，或让后续步骤假装已引用资料（assistant.html:205 的显式说明）。
- **禁止**：把 `.steps__body` 单独用于非 `.steps` 元素，或改变 checkbox → label → ol 的兄弟顺序（会让 rb.css:262 失效）。
- **禁止**：新增 `--step-running-fg` / `--step-done-fg` / 动画时长 token——`rb.css` 与 `tokens.json` 都没有；如需，走「先改 token 源 + 重跑生成器 + 重跑等价性验证」的流程。
- **登记（待裁决项）**：① `.steps__toggle` 焦点环不可见（§6）；② rb.css:252/254 两处直取 L2（跨层登记，见 §5 表）；③ 旋转时长 `1.1s` 未 token 化。

---

## Empty `.empty`

### 1. 用途与边界

- **是**：**整块区域没有可展示内容**时的占位块，同时说明「为什么没有」与「下一步能做什么」。
- **是**：必须区分两种根因完全不同的状态，**不得合并**：
  - **「成功的空」**（`records.html:78`、`records.html:185`、`assistant.html:449`、`admin.html:210`）：请求成功、列表确实为空 / 全库尚无资料 / 拖拽引导 → **中性色、虚线边、不得用错误色**（content-spec:122–123）。
  - **「服务异常」**（`records.html:94`、`assistant.html:428`）：读取失败 / 检索依赖异常 → **危险语义、实线边、危险底**，且必须保留「未知」语义（content-spec:124–125）。
- **不是**：不是把所有「没有内容」合并成同一种中性块。`FORBIDDEN_MERGE`：把「没有课」与「读不到课表」合并成同一个视觉/文案（content-spec:126、§3）。
- **不是**：不承载表单校验错误（用 `.error-summary` / `.field__error`）。

**`empty` 组的 6 个语义状态（必须靠 图标 + 标题 + 动作 三者区分）**

| # | 语义 | class | 图标（Lucide） | 标题（逐字） | 动作 | 出处 |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | 查询成功但无记录 | `.empty` | `calendar` | 2026-10-22（周四）没有课程安排。 | 换个日期 | content-spec:122；records.html:78–91 |
| E2 | 列表为空 | `.empty` | 计划/清单类 | 还没有学习计划。 | 手动新建 | content-spec:133；records.html:185 |
| E3 | 全库尚无资料 | `.empty` | `inbox` | 管理员还没有上传可检索的课程资料。 | —（可用引导文案） | content-spec:95；assistant.html:449 |
| E4 | 上传引导（非遗漏） | `.empty` | `upload` | 把文件拖到这里，或选择文件 | 选择文件 | content-spec:151；admin.html:210 |
| E5 | **服务异常**（课表） | `.empty--error` | `triangle-alert` | 课表数据暂时无法读取，这不代表当天没有课。 | 重试 | content-spec:124；records.html:94–106 |
| E6 | **服务异常**（检索失败） | `.empty--error` | `circle-x` | 课程资料暂时无法查询，请稍后重试。 | 重试 | content-spec:94；assistant.html:428–446 |

- E1/E2/E3/E4 用 `.empty`，E5/E6 用 `.empty--error`。**同一页面里 E1 与 E5、或 E3 与 E6 并列展示时，必须一眼可分**（content-spec:121）。

### 2. 结构（DOM 骨架）

```html
<!-- 「成功的空」：虚线 + 中性色 -->
<div class="empty">
  <p class="empty__art">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
         aria-hidden="true" focusable="false"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>
  </p>
  <p class="empty__title">2026-10-22（周四）没有课程安排。</p>
  <p class="empty__hint">查询成功 · 无记录：当天确实没有课程安排，不是读取失败。</p>
  <p><button class="btn" type="button">…换个日期</button></p>
</div>

<!-- 「服务异常」：实线 + 危险色 + role="alert" -->
<div class="empty empty--error" role="alert">
  <p class="empty__art">
    <svg width="24" height="24" …><path d="M10.3 4.3 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>
  </p>
  <p class="empty__title">课表数据暂时无法读取，这不代表当天没有课。</p>
  <p class="empty__hint">服务异常 · 无法判断有无课：读取失败保留了「未知」语义，不能显示成「没有课」。</p>
  <p><button class="btn btn--primary" type="button">…重试</button></p>
</div>
```

- `.empty__art` 的宿主可以是 `<p>`（records.html:79）或 `<div>`（assistant.html:429）：两者都只是 class 槽位，`<p>` 含 `<svg>` 合法。插图尺寸随语义放大：小图标 24×24、需要更强的坏消息用 40×40（assistant.html:430）。
- 动作行放在最后，用 `<p>` 或 `.row` 包裹 `.btn`；E1 用默认 `.btn`，E5/E6 用 `.btn--primary`（主操作是「重试」）。
- 两态并排用外部 `.card-row.card-row--2`（`≥768` 转 2 列），<768 自动堆叠。

### 3. API 表

| class | rb.css | 用途 |
| --- | --- | --- |
| `.empty` | 301–302 | 中性空状态：居中、`padding:36px 18px`、**虚线** 1px 边、圆角 14px、白底 |
| `.empty__art` | 303 | 插图/图标槽：色 `#78716C`、下外边距 12px |
| `.empty__title` | 304 | 标题（字重 600，下外边距 6px）。**逐字文案位**，状态靠它区分 |
| `.empty__hint` | 305 | 说明（15px、次级色）。可多条（records.html:83–84） |
| `.empty--error` | 307 | 服务异常：**实线**边 `#9F1239`、底 `#FBE7EC` |
| `.empty--error .empty__art` / `.empty__title` | 308 | 插图与标题转危险色 `#7B0E2C` |

- `.empty` 与 `.empty--error` **只差三个属性**（`border-style` / `border-color` / `background`）+ 插图与标题色，因此**必须**同时靠图标、标题、动作三者区分，颜色只是第三通道。

### 4. 状态矩阵（只写 rb.css 真实存在的状态）

| 状态 | 选择器 | rb.css | 表现 |
| --- | --- | --- | --- |
| 成功的空（中性） | `.empty` | 301–302 | `border:1px dashed #C9C3BC` + 底 `#FFFFFF`；插图 `#78716C`；标题正文字色 |
| 服务异常 | `.empty--error` | 307 | `border-style:solid` + `border-color:#9F1239` + 底 `#FBE7EC` |
| 服务异常（插图/标题） | `.empty--error .empty__art`, `.empty--error .empty__title` | 308 | 两者转 `#7B0E2C`；**`.empty__hint` 不变色**（仍 `#5B544E`） |
| 悬停 / 按下 / 禁用 / 焦点 | — | — | **均不存在**。`.empty` 是静态区域；块内按钮自带交互态 |
| 复杂空状态（含胶囊） | `.empty` 内嵌 `.pill` | 209–220 | 如 assistant.html:454–457「尚无已发布资料」；胶囊属 Pill 组，不计入 `empty` token |

### 5. token 消费表（14 个 `empty` 组 token，全覆盖）

| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| 纵向内边距 | `--empty-pad-y` | `36px` | rb.css:301 |
| 横向内边距 | `--empty-pad-x` | `18px` | rb.css:301 |
| 描边宽度 | `--empty-border-w` | `1px` | rb.css:302（`1px dashed`） |
| 描边色（中性态） | `--empty-border-color` | `#C9C3BC` | rb.css:302 |
| 圆角 | `--empty-radius` | `14px` | rb.css:302；与卡片同档 |
| 底色（中性态） | `--empty-bg` | `#FFFFFF` | rb.css:302 |
| 插图/图标色 | `--empty-art-fg` | `#78716C` | rb.css:303（rb.css 写 `var(--c-ink-400)`，L3 已收敛为 `--text-art`） |
| 插图下外边距 | `--empty-art-margin-b` | `12px` | rb.css:303 |
| 标题下外边距 | `--empty-title-margin-b` | `6px` | rb.css:304 |
| 说明字号 | `--empty-hint-fs` | `15px` | rb.css:305 |
| 说明文字色 | `--empty-hint-fg` | `#5B544E` | rb.css:305 |
| 异常态描边色 | `--empty-error-border-color` | `#9F1239` | rb.css:307 |
| 异常态底色 | `--empty-error-bg` | `#FBE7EC` | rb.css:307 |
| 异常态文字色 | `--empty-error-fg` | `#7B0E2C` | rb.css:308；作用于 `.empty__art` 与 `.empty__title` |

**无 L3 token 的规则（仍有锚点）**

| 属性 | 值 | rb.css | 说明 |
| --- | --- | --- | --- |
| 居中对齐 | `text-align:center` | 301 | 块内所有文本居中 |
| 虚线边框样式 | `border-style:dashed`（中性）→ `solid`（异常） | 302 / 307 | **两态的第一视觉差异**，先于颜色被感知 |
| 标题字重 | `font-weight:600` | 304 | — |

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 角色 | 服务异常态（E5/E6）用 `role="alert"`——冻结原型用法见 records.html:94。**首屏即存在**时沿用该形态；由交互**动态注入**时同样必须带 `role="alert"`，否则屏幕阅读器不会播报。成功的空（E1–E4）**不加** live region（不是告警） |
| ⚠ 已登记不一致 | `assistant.html:428` 的 `.empty--error`（检索失败）**未加 `role="alert"`**，与 `records.html:94` 不一致 → 登记为待统一（本规格要求按 records.html:94 的形态加 `role="alert"`） |
| 插图 | `.empty__art` 内 SVG 一律 `aria-hidden="true" focusable="false"`（插图是装饰，语义由标题承载） |
| 可访问名 | 无（不是控件）。标题是状态的可访问来源 → **标题必须逐字写清根因**，不能只写「出错了」 |
| 键盘 | `.empty__hint` 不可聚焦；只有当 `.empty--error` 由提交失败触发时，才按 content-spec §1 把焦点移到顶部错误摘要（`.error-summary`），**不是**移到 `.empty` |
| 触控目标 | 块内 `.btn` 44px（rb.css:195）；窄屏动作按钮之间留 `.row` 的 12px 间距（rb.css:390） |
| 对比度 | 说明/底 `7.44:1`、异常文字/异常底 `9.14:1`（tokens.md §7 实测，PASS） |
| 状态三重 | **每个空状态必须同时有：不同图标（calendar / inbox / upload / triangle-alert / circle-x）+ 逐字标题 + 颜色**。E1 与 E5 的差别不能只是底色 |
| 「未知」语义 | 服务异常态文案必须显式说明「这不代表当天没有课 / 不代表没有相关资料」（content-spec:124、assistant.html:439）——这是 SRS 的硬验收点（content-spec:126） |

### 7. 内容与文案规则

| 状态 | 标题（逐字） | 说明/辅助（逐字） | 动作 | 来源 |
| --- | --- | --- | --- | --- |
| E1 成功的空 | 2026-10-22（周四）没有课程安排。 | 查询成功 · 无记录：当天确实没有课程安排，不是读取失败。 | 换个日期 | content-spec:122 |
| E2 列表为空 | 还没有学习计划。 | — | 手动新建 | content-spec:133 |
| E3 全库为空 | 管理员还没有上传可检索的课程资料。 | 这是「还没有材料」，既不是检索失败，也不是「没有这项规定」。 | — | content-spec:95 |
| E4 上传引导 | 把文件拖到这里，或选择文件（admin.html:214 逐字） | TXT / MD / 含文字层的 PDF / DOCX；单文件 ≤ 20 MiB；单批 ≤ 10 个、合计 ≤ 50 MiB | 选择文件 | content-spec:151 |
| E5 服务异常（课表） | 课表数据暂时无法读取，这不代表当天没有课。 | 服务异常 · 无法判断有无课：读取失败保留了「未知」语义。 | 重试 | content-spec:124 |
| E6 服务异常（检索） | 课程资料暂时无法查询，请稍后重试。 | 本次检索没有完成，不代表「没有相关资料」，也不代表「课程没有这项规定」。 | 重试 | content-spec:94 |

- **FORBIDDEN_MERGE**：任何把 E1/E2/E3 与 E5/E6 写成同一句中性兜底文案（无根因、无「暂时/不代表」措辞）的实现都违反内容契约（content-spec:126、§3）。
- 服务异常的标题必须含「暂时 / 这不代表 / 不代表」这类**保留未知**的措辞。
- `empty__hint` 可有多条（records.html:83–84）；每条 <30 字，不只写「请重试」。
- 禁止 emoji（content-spec §3）；图标一律内联 SVG。

### 8. 响应式行为

| 档 | 行为 | 依据 |
| --- | --- | --- |
| base（<480） | 单列居中，`padding:36px 18px`；动作按钮占满可用宽或按内容 | rb.css:301–308 **无 @media** |
| xs ≥480 / sm ≥768 / md ≥1024 / lg ≥1200 / xl ≥1440 | `.empty` 自身无变化；两态并排由外部 `.card-row--2` 在 `≥768` 转为 2 列（rb.css:182） | b-responsive-spec §4（`.empty` / `.empty--error` 单列，两者必须视觉可分） |
| 全部档 | 内边距与字号不随断点变化（36/18px、15px） | b-responsive-spec §6 |
| 320px（Reflow 验收） | E4 的限制说明是长中文串，必须允许换行；不得引入横向滚动 | content-spec §1 长文本行；b-responsive-spec §9.1 |

### 9. 契约依据与禁止事项

- 上游依据：content-spec:121–126（S08 两态并列、逐字文案、禁止合并）、content-spec:133/151/95（E2/E4/E3）、content-spec §3（禁止把空结果与读取失败合并）；b-responsive-spec §4/§7。
- **禁止**：把 `.empty` 与 `.empty--error` 合并为一个中性兜底块；禁止在 `.empty` 上使用危险色；禁止在 `.empty--error` 上使用成功色或中性底。
- **禁止**：用 `.empty` 表达表单校验错误或权限不足（那是 `.error-summary` / `.notice--danger`）。
- **禁止**：给 `.empty` 加 `:hover` / 点击态 / `role="button"`。
- **禁止**：发明 `--empty-error-title-fg` 之类 token；消费面恰好是 §5 的 14 个。
- 上游引用（仅说明，不作消费面）：`.empty--error` 的边色与 `--danger-border`、按钮危险边同源（L2）；`.empty__art` 的色源为 `--text-art`（L2）。

---

## 附：本文件登记的全部不确定点 / 待裁决项

| # | 事项 | 证据 | 本规格的处理 |
| --- | --- | --- | --- |
| 1 | 琥珀胶囊被用于「未保存/待确认」之外 | `assistant.html:407`（依据不足）、`admin.html:232`/`302`（处理中）用 `pill--warn` | 边界按题面写死为「未保存/待确认」；实现时「处理中/依据不足」改用 `pill--info`；差异交 Lead 裁决 |
| 2 | `.pill--pending` 在原型中零实例 | 原型未保存态用 `pill--warn`（assistant.html:480、407） | 保留为 `--warn` 的语义别名（rb.css:216 同一规则），无专用 token |
| 3 | 4 处胶囊缺图标（硬要求违例 1 处） | `records.html:30`、`admin.html:118`、`admin.html:586`（中性标签）、**`records.html:273`（`pill--danger`「不可恢复」）** | 中性标签用法允许；273 登记为待补图标 |
| 4 | `a.chip` 原型零实例 | `.chips` 内实为 `.btn--sm`（assistant.html:43–56） | 保留完整定义（12 token），但不得改写既有示例入口 |
| 5 | `.notice--evidence` 原型零实例 | 仅 rb.css:230 定义 | 保留定义，不得据此改页面 |
| 6 | `.steps__toggle` 焦点环不可见 | `.sr-only` 的 `clip`（rb.css:113–114）+ 全局 `:focus-visible`（110） | 登记为待修，需新增焦点补偿规则并重跑 rb.css 等价性验证 |
| 7 | `.empty--error` 的 `role` 不一致 | `records.html:94` 有 `role="alert"`；`assistant.html:428` 无 | 要求按 records.html:94 统一 |
| 8 | 禁用主按钮仍响应 hover | rb.css:201 与 205 特异性相同、属性不同 | 登记为已知现象，不新增规则 |
| 9 | rb.css 直取 L2 的 3 处 | rb.css:252（running 标题色）、254（done 文字色）、303（art 色） | 303 已有 L3（`--empty-art-fg`）；252/254 无 L3，登记为跨层待补 |
| 10 | 步骤旋转时长 `1.1s` 未 token 化 | rb.css:253 | 登记；改需走 token 源 + 重新生成流程 |
