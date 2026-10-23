<!-- owns: field, control, table, utility -->
# 表单与数据（Field / Control / Table / Utility）

> 本文件是 [`04-forms-data.md`](04-forms-data.md) 的组件 API 规格，供 Vue 3 实现者直接消费。
> **实现锚点**：[`../responsive/rb.css`](../../responsive/rb.css)（下称 `rb.css`），每条属性都带行号。
> **token 真源**：[`../tokens.json`](../tokens.json) 的 `component.field / control / table / utility` 四组；
> **解析值真源**：[`../tokens.flat.json`](../tokens.flat.json)。
> **响应式依据**：[`../../responsive/b-responsive-spec.md`](../../responsive/b-responsive-spec.md)（下称 `b-spec`）。
> **文案真源**：[`../../directions/shared/content-spec.md`](../../directions/shared/content-spec.md)（下称 `content-spec`）。

---

### 0. 总则（四个组件族共用）

### 0.1 token 消费的硬边界

| 规则 | 含义 | 违反后果 |
| --- | --- | --- |
| 组件规则只消费 L3 | 组件 `<style>` 里只允许出现 `--field-*` / `--control-*` / `--table-*` / `--stack-gap` / `--row-gap` / `--muted-fg` / `--small-fs` | `generate.py` 的分层纯度校验报 FAIL（README 分层纯度规则 4） |
| 颜色必须经 L2 | L3 的**值**可写 L2（如 `--bg-card`），但**组件规则**里不得直接写它 | 同上；详见 §0.2 的「上游解析链」标注法 |
| 不消费 L1 | 组件规则里出现 `var(--p-*)` 即违规 | 同上 |
| 不自造 token | 本文件出现的每个名字都可在 `tokens.flat.json` 查到 | 规格↔token 覆盖比对失败 |

### 0.2 三个值的三种写法（本文统一口径，勿混）

以 `--control-invalid-border-color` 为例：

| 列名 | 写什么 | 示例 |
| --- | --- | --- |
| **L3 token** | `tokens.json` 里的键 | `--control-invalid-border-color` |
| **解析值**（必须与 `tokens.flat.json` 逐字相等） | `var()` 链展开后的最终字面量 | `#9F1239` |
| **上游链**（仅供解释，**不得被组件消费**） | L3→L2→L1 的路径 | `--danger-border`(L2) → `--p-danger-700`(L1) |

**只有第 1 列是组件可以写的。** 第 3 列只出现在「说明」列里。

### 0.3 断点口径（`b-spec` §1）

| 档 | 区间 | 本文中出现的媒体查询字面量 | rb.css 行号 |
| --- | --- | --- | --- |
| base | <480 | 无（基准规则） | — |
| xs | 480–767 | `min-width:480px`（本文件范围**不使用**） | — |
| **base–xs（表格卡片档）** | **<768** | **`max-width:767px`**（= sm 768 − 1，规则源自 `tokens.json` `meta.purity_rules`） | rb.css:351 |
| sm | ≥768 | `min-width:768px` | rb.css:312 |
| md/lg/xl | ≥1024/1200/1440 | 本文件范围**不使用** | — |

**768 是唯一分界线**：表格↔卡片、表单 1 列↔2 列同时在这里切换，是刻意把两个变化压在同一档（`b-spec` §1「为什么 768 是主分界线」）。

### 0.4 状态清单：只写 rb.css 里真实存在的

这是本文件**最容易被挑错**的地方。下表是四个组件族**全部**真实存在的状态，**规格里不得出现此表之外的状态**：

| 组件 | 真实存在的状态选择器 | rb.css 行号 |
| --- | --- | --- |
| Field | `.field--invalid` | 327 |
| Control | `.input[readonly]` | 325 |
| Control | `.input[disabled]`、`.select[disabled]` | 326 |
| Table | `.table--compact` | 347–348 |
| Table | `.table--stack` | 351–378 |
| Table | `tbody tr:last-child` | 342、358 |

**明确不存在**（禁止写进规格、禁止在实现里"补上"）：

| 不存在的状态 | 说明 |
| --- | --- |
| `.input:hover` / `.table tr:hover` / 任何表单 `:hover` | rb.css 表单段（310–331）**零** `:hover` |
| `.field--valid` / `.field--warning` / `.field--loading` | 不存在 |
| `.input:active` / `.input:focus` | 不存在；**焦点是全局规则** `:focus-visible`（rb.css:110），不在组件内改写 |
| `.table--striped` / `.table--bordered` / `.table--hover` | 不存在 |
| `.textarea[readonly]` / `.textarea[disabled]` / `.select[readonly]` | **rb.css 未定义**。见 §2.9 的缺口登记 |
| `.field--invalid` 作用在 `.textarea` 以外 | 存在：`.field--invalid .input` / `.select` / `.textarea` 三者都在 rb.css:327–328 |

> **焦点环归属**：`:focus-visible{outline:3px solid <L2 --focus>;outline-offset:2px;border-radius:4px}`（rb.css:110）
> 是**全局**规则，覆盖 `input/select/textarea/a/button`。组件规格**不得**复制或覆盖它。
> 对比度：焦点环 vs 页面底 9.53:1、vs 卡片底 10.10:1（`tokens.md` §7，均 ≥3:1）。

---

## 一、Field 家族 `.field`

### 1. 用途与边界

| 项 | 内容 |
| --- | --- |
| 用途 | 单个表单字段的**容器**：把 label、必填标记、控件、辅助文字、错误文字竖向排成一组，并保证 label 与控件的可见关联 |
| 用 | 任何 `input`/`select`/`textarea` 的包裹；S01 登录（账号/密码）、S09 计划编辑（标题/目标/开始/结束/正文/来源只读）、S10 课程表单、S12 课表维护表单 |
| 不用 | 纯按钮组、筛选 chips（用 `.row` / `.chips`）；只读展示型数据（用 `.kv` 或 `.table`） |
| 与 `.kv` 的分界 | 可编辑 → `.field`；只读键值展示 → `.kv`（rb.css:381–384，不属本文件 owns） |

### 2. 结构（DOM 骨架）

```html
<!-- 普通字段：label → 控件 → 辅助文字（顺序即 DOM 顺序，视觉顺序 = DOM 顺序） -->
<div class="field">
  <label class="field__label" for="plan-title">标题 <span class="field__req">必填</span></label>
  <input class="input" id="plan-title" name="title" maxlength="100"
         aria-describedby="plan-title-hint">
  <p class="field__hint" id="plan-title-hint">最多 100 字</p>
</div>

<!-- 非法字段：控件的 aria-invalid + aria-describedby 指向 field__error；文字是硬要求 -->
<div class="field field--invalid">
  <label class="field__label" for="plan-end">结束日期 <span class="field__req">必填</span></label>
  <input class="input" id="plan-end" name="end" type="date"
         aria-invalid="true" aria-describedby="plan-end-err">
  <p class="field__error" id="plan-end-err">
    <svg class="ico" aria-hidden="true" width="16" height="16" viewBox="0 0 24 24"
         fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="9"/>
      <path d="M12 7v6M12 16.5v.01"/></svg>
    <span>开始与结束日期需要同时填写，且开始日期不能晚于结束日期。</span>
  </p>
</div>

<!-- 只读字段：必须带 >说明原因< 的辅助文字（content-spec §1「只读用灰底无边框样式并说明原因」） -->
<div class="field">
  <label class="field__label" for="course-code">课程代码 <span class="field__req">必填</span></label>
  <input class="input" id="course-code" name="code" value="CS201" readonly
         aria-describedby="course-code-hint">
  <p class="field__hint" id="course-code-hint">课程代码创建后不可修改</p>
</div>

<!-- 两列表单里的跨列字段 -->
<div class="field field--wide"> … </div>
```

| DOM 约束 | 依据 |
| --- | --- |
| `.field` 的直接子元素顺序固定：`__label` → 控件 → `__hint` / `__error` | rb.css:314 `flex-direction:column`（视觉顺序 = DOM 顺序） |
| `field__error` 必须在**所描述控件之后**的 DOM 位置 | README 硬要求 6 + `content-spec` §1「错误就近…在该字段下方」 |
| 一个 `.field` 内**最多一个** `field__error` | `aria-describedby` 允许多 id，但多错误文案会破坏「就近」判读 |
| `field__hint` 与 `field__error` **不同时出现**于同一字段的同一时刻 | 两者都占同一位置；同时出现会让错误被辅助文字淹没 |

### 3. API 表

| class | 元素 | 作用 | rb.css |
| --- | --- | --- | --- |
| `.field` | `div` | 字段容器，纵向 flex，间距 `--field-gap`；`min-width:0` 防 flex/grid 子项撑破 | rb.css:314 |
| `.field--invalid` | 修饰 `.field` | 让**后代** `.input`/`.select`/`.textarea` 进入非法外观 | rb.css:327–328 |
| `.field__label` | `label` | 可见字段名，`font-weight:600`，字号 15px | rb.css:315 |
| `.field__req` | `span` | 「必填」文字标记（**文字**，不是 `*` 符号） | rb.css:316 |
| `.field__hint` | `p` / `span` | 辅助文字（字数上限、只读原因） | rb.css:317 |
| `.field__error` | `p` | 错误文字，flex 行内放 16px 图标 + 文本 | rb.css:318 |
| `.field--wide` | 修饰 `.field` | 在 `.form-grid--2` 下跨两列；**仅在 ≥768 生效**（在 base–xs 是空操作，因为那时只有 1 列） | rb.css:313 |
| `.input` / `.select` / `.textarea` | 控件 | 见 §二 | rb.css:319–324 |

**必须存在的属性（不是可选）**

| 属性 | 位置 | 要求 |
| --- | --- | --- |
| `for`（= 控件 `id`） | `.field__label` | **硬要求**，每个控件必须有非空可访问名（`b-spec` 验收清单 5） |
| `id` | 控件 | 与 `for` 配对；同页唯一 |
| `aria-describedby` | 控件 | 指向 `field__hint` 或 `field__error` 的 `id`（可两个 id 空格分隔） |
| `aria-invalid="true"` | 控件 | 非法时必加；`.field--invalid` 只负责**视觉** |
| `readonly` / `disabled` | 控件 | 原生属性，不用 class 模拟（rb.css 选择器就是属性选择器：325–326） |
| `maxlength` | 控件 | 按 `content-spec` 上限：标题 100、目标 500、正文 10000、简介 2000、原因 500 |

### 4. 状态矩阵

**只列真实存在的状态**（依据 §0.4）。「无样式」= rb.css 未定义，实现也不得自行发明。

| 状态 | 触发 | label | 控件外观 | 文字 | rb.css |
| --- | --- | --- | --- | --- | --- |
| 常态 | — | 正常 | 1px `--control-border-color` | 可有 `field__hint` | 314–318 |
| 必填 | 字段必填 | 追加 `field__req` = 「必填」 | — | — | 316 |
| 非法 | `.field--invalid` | 正常 | 边 1px `--control-invalid-border-color` + box-shadow `--control-invalid-ring` | **必须**有 `field__error` 文字 | 327–328 |
| hover / active / focus（组件级） | — | **不存在** | **不存在** | — | — |
| 焦点 | `:focus-visible` | 正常 | 全局 3px 实线轮廓 + 2px 偏移 | — | 110（全局，非本组件） |

**非法态的三重表达（硬要求，禁止只靠颜色）**

| 通道 | 实现 | 缺了会怎样 |
| --- | --- | --- |
| 颜色 | `border-color` = `--control-invalid-border-color`（`#9F1239`）+ 外环 `--control-invalid-ring` | 单独用会让红绿色觉障碍者无法识别（WCAG 1.4.1） |
| 文字 | `field__error` 内**逐字**错误文案 | **不可省略**——这是本文件与 `content-spec` §1 的硬约束 |
| 图形 | `field__error` 内的 16px 内联 SVG（`aria-hidden="true"`） | 图标是纯装饰，不给可访问名，避免与文字重复播报 |
| 语义 | 控件 `aria-invalid="true"` + `aria-describedby` 指向错误 `id` | 屏幕阅读器读不到错误 |

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明（含上游链，仅供解释） |
| --- | --- | --- | --- |
| `.field` `gap` | `--field-gap` | `6px` | label 与控件之间；上游 `--p-space-1` |
| `.field__label` `font-size` | `--field-label-fs` | `15px` | 上游 `--p-fs-15` |
| `.field__label` `font-weight` | `--field-label-fw` | `600` | 上游 `--p-fw-semibold` |
| `.field__req` `color` | `--field-req-fg` | `#7B0E2C` | 经 L2 `--state-danger` |
| `.field__req` `font-size` | `--field-req-fs` | `13px` | 上游 `--p-fs-13` |
| `.field__hint` `font-size` | `--field-hint-fs` | `13px` | 上游 `--p-fs-13` |
| `.field__hint` `color` | `--field-hint-fg` | `#6B6259` | 经 L2 `--text-muted` |
| `.field__error` `font-size` | `--field-error-fs` | `13px` | 上游 `--p-fs-13` |
| `.field__error` `color` | `--field-error-fg` | `#7B0E2C` | 经 L2 `--state-danger` |
| `.field__error` `gap`（图标↔文字） | `--field-error-gap` | `5px` | 上游 `--p-space-5px` |
| `.form-grid` `gap` | `--field-grid-gap` | `18px` | 上游 `--p-space-3`；见 §三 |

> 实现注记：rb.css:318 的 `gap` 写的是裸 `5px` 而非 `var(--sp-2)`（rb.css 冻结，不改写）；迁移到 tokens.css 后
> 该属性消费 `--field-error-gap`（`generate.py` 的 MIGRATION 表已收录同类项）。

### 6. 无障碍要求

| 要求 | 具体做法 |
| --- | --- |
| 可访问名 | `.field__label` 的 `for` 指向控件 `id`；**不得**用 `placeholder` 当唯一标签（`content-spec` §1） |
| 描述 | 控件 `aria-describedby` 指向 `field__hint` / `field__error` 的 `id` |
| 非法语义 | 控件 `aria-invalid="true"`；`.field--invalid` **只是视觉**，不能替代语义 |
| 错误播报 | 客户端校验产生的 `field__error` 若为动态插入，容器加 `role="alert"`（隐含 `aria-live="assertive"`）；若页面加载即存在则无需 |
| 图标 | `field__error` / `field__req` 里的 SVG 一律 `aria-hidden="true"` 且无 `focusable` 依赖；图标不承载唯一信息 |
| 触控 | 控件 `min-height` = `--control-min-h` = `44px`（rb.css:320） |
| 对比度 | `field__error` 文字 ✓ 10.20:1（vs 页面底）/ 10.82:1（vs 卡片底）；`field__hint` / `field__req` 详见 §2.6 |
| 焦点 | 不覆盖全局 `:focus-visible`（rb.css:110）；错误摘要聚焦时程序化 `focus()` 到 `.error-summary`（§四） |
| 布局 | 错误文字**换行不截断**，不得用 `text-overflow:ellipsis` 藏错误 |

### 7. 内容与文案规则

**逐字取自 `content-spec`，不得改写、不得自造。**

| 用途 | 逐字文案 | 出处 |
| --- | --- | --- |
| 必填标记 | `必填` | content-spec:38 |
| 只读说明（S10 课程代码） | `课程代码创建后不可修改` | content-spec:145 |
| 字数上限（S02 输入区） | `最多 2000 字` | content-spec:69 |
| 登录整体失败（S01） | `账号或密码不正确，请重试。` | content-spec:56 |
| 账号被禁用（S01） | `当前账号不可用，请联系管理员。` | content-spec:59 |
| 日期校验（S09） | `开始与结束日期需要同时填写，且开始日期不能晚于结束日期。` | content-spec:136 |
| 版本冲突 409（S09） | `这份计划已被其他标签页修改，请重新加载后再提交；你未提交的编辑会保留。` | content-spec:137 |
| 重复课程代码（S10） | `该课程代码已存在，请更换。` | content-spec:146 |
| 时段校验（S12） | `结束时间必须晚于开始时间，且不支持跨日记录。` | content-spec:165 |
| 精确重复 409 DUPLICATE_SCHEDULE（S12） | `该学生在同一天已有完全相同时间段的这门课，不能重复保存。` | content-spec:166 |
| 冲突面板原因必填（S12） | `必填` | content-spec:170 |
| 停用确认（S10） | `停用后不能再为该课程新增课表记录；已有课表和计划仍可查看。` | content-spec:147 |

**禁止**：`content-spec` §3 列出的全部表述。本文件范围内尤其禁止出现
「正在思考」「AI 推理中」「暂无数据」；禁止把「查询成功但无记录」与「读取失败」写成同一种错误文案
（那两个态属 `.empty` / `.empty--error`，不属本文件 owns，但表单/表格不得替它们兜底成中性文案）。

### 8. 响应式行为

| 档 | 行为 | rb.css |
| --- | --- | --- |
| base–xs（<768） | `.field` 宽度 100%；`min-width:0` 生效于任何容器；`.field--wide` **无效果** | 314 |
| sm（≥768） | `.form-grid--2 .field--wide{grid-column:1/-1}` 生效 | 313 |
| md–xl | **无变化**（`b-spec` §6「间距不随断点线性放大」） | — |

`.field` 自身**不写任何媒体查询**：列数由父级 `.form-grid--2` 控制（§三）。

### 9. 契约依据与禁止事项

| 依据 | 内容 |
| --- | --- |
| rb.css | 314–318（基础）、313（`--wide`）、327–328（非法） |
| README 硬要求 | 5（每个属性可锚行号）、6（无障碍具体到属性）、7（文案不自造） |
| b-spec | §1 断点、§2 表单列数、§6 密度、§7 无障碍 |
| content-spec | §1 表单标签/错误就近/只读 vs 禁用/触控；§2 各屏文案 |

**禁止**

1. 禁止为 `.field` 发明 `:hover`、`:focus-within`、`.field--valid` 等 rb.css 中不存在的状态。
2. 禁止用 `placeholder` 代替 `.field__label`。
3. 禁止只用颜色表达非法态——必须同时有 `field__error` 文字与 `aria-invalid`。
4. 禁止在 `.field` 上消费 L1/L2 token（例如把颜色直接写成 L2 的 `--state-danger` 而不是 `--field-error-fg`）。
5. 禁止把 `readonly` 与 `disabled` 互换：朗读/可聚焦性不同（§2.9）。

---

## 二、Control `.input` / `.select` / `.textarea`

### 1. 用途与边界

| 项 | 内容 |
| --- | --- |
| 用途 | 三种文本类表单控件；同一套边框/圆角/内边距/最小高度，差异只在 `textarea` 的最小高与行高 |
| 用 | `input`：账号、密码、日期、时间、搜索框（S09 列表搜索、S10 筛选）、`select`：课程下拉（S12，停用课程不可选）、`textarea`：问题输入（S02）、正文（S09 上限 10000）、目标（500）、简介（2000）、冲突原因（500） |
| 不用 | 开关/勾选（checkbox/radio/switch 本文件范围**不含**，rb.css 未定义相关 class，不得自造）；文件上传拖拽区（属 S11，不在本文件 owns） |
| 只读 vs 禁用 | **必须视觉可分**（`content-spec` §1）：只读 = 灰底 + 浅边 + 次级文字 + **说明原因的文字**；禁用 = 降透明度 + `not-allowed` |

### 2. 结构（DOM 骨架）

```html
<!-- 文本输入 -->
<input class="input" id="q" name="q" type="search" placeholder="按标题筛选">

<!-- 日期 / 时间：使用原生类型，不引第三方选择器（content-spec 禁止外部请求） -->
<input class="input" id="start-date" name="start_date" type="date">
<input class="input" id="start-time" name="start_time" type="time">

<!-- 下拉：停用课程不可选 → 用 option[disabled]，不用 CSS 假装 -->
<select class="select" id="course" name="course_id" aria-describedby="course-hint">
  <option value="">请选择课程</option>
  <option value="CS201">数据结构</option>
  <option value="CS310" disabled>操作系统（已停用）</option>
</select>
<p class="field__hint" id="course-hint">已停用的课程不可选</p>

<!-- 多行文本 -->
<textarea class="textarea" id="plan-body" name="body" maxlength="10000"
          aria-describedby="plan-body-hint"></textarea>
<p class="field__hint" id="plan-body-hint">最多 10,000 字</p>

<!-- 只读：说明原因的文字是硬要求 -->
<input class="input" id="source" name="source" value="助手生成" readonly
       aria-describedby="source-hint">
<p class="field__hint" id="source-hint">来源由系统记录，不可修改</p>

<!-- 真禁用 -->
<input class="input" id="locked" name="locked" value="—" disabled>
```

| DOM 约束 | 依据 |
| --- | --- |
| 控件必须位于 `.field` 内（`.field--invalid` 是**后代**选择器，脱离 `.field` 就无法进入非法外观） | rb.css:327–328 |
| `readonly` / `disabled` 用**原生属性**，不用 class | rb.css:325–326 是属性选择器 |
| `select` 的 `disabled` 只作用于 `option`（课程不可选），控件本身不用 `disabled` | rb.css:326 只给 `.select[disabled]` 定样式，**整体禁用下拉**是另一件事 |
| 日期/时间控件不得用 `type="text"` 伪装 | 触屏键盘与可访问名依赖原生类型 |

### 3. API 表

| class | 元素 | 作用 | rb.css |
| --- | --- | --- | --- |
| `.input` | `input` | 单行文本/日期/时间/搜索 | 319（共同规则）、320（尺寸） |
| `.select` | `select` | 下拉 | 319–320 |
| `.textarea` | `textarea` | 多行 | 319–320 + 324 |
| `.input[readonly]` | 属性 | 灰底 + 浅边 + 次级文字 | 325 |
| `.input[disabled]` / `.select[disabled]` | 属性 | `opacity:.5` + `cursor:not-allowed` | 326 |
| `.field--invalid .input` / `.select` / `.textarea` | 后代 | 危险边 + 3px 外环 | 327–328 |

**共同几何（rb.css:319–320，三个控件共享同一条规则）**

| 属性 | 值 | L3 token |
| --- | --- | --- |
| `width` | `100%` | 字面量（无 token） |
| `min-height` | `44px` | `--control-min-h` |
| `padding` | `10px 12px` | `--control-pad-y` / `--control-pad-x` |
| `border` | `1px solid #78716C` | `--control-border-w` / `--control-border-color` |
| `border-radius` | `10px` | `--control-radius` |
| `background` | `#FFFFFF` | `--control-bg` |
| `color` | `#1C1917` | `--control-fg` |
| `font` | `inherit` | 继承 `body` 的 17px/1.75（rb.css:99） |

**独有**：`.textarea{min-height:120px;line-height:1.6}`（rb.css:324）→ `--control-textarea-min-h` / `--control-textarea-lh`。

### 4. 状态矩阵

| 状态 | 选择器 | background | border-color | color | 其他 | rb.css |
| --- | --- | --- | --- | --- | --- | --- |
| 常态 | `.input` / `.select` / `.textarea` | `--control-bg` `#FFFFFF` | `--control-border-color` `#78716C` | `--control-fg` `#1C1917` | — | 319–323 |
| 只读 | `.input[readonly]` | `--control-readonly-bg` `rgba(28,25,23,.03)` | `--control-readonly-border-color` `#E7E5E4` | `--control-readonly-fg` `#5B544E` | 保留可聚焦、可选中 | 325 |
| 禁用 | `.input[disabled]` / `.select[disabled]` | **不覆盖**（仍是 `#FFFFFF`） | **不覆盖**（仍是 `#78716C`） | **不覆盖** | `opacity:.5`、`cursor:not-allowed` | 326 |
| 非法 | `.field--invalid .input` 等 | 不覆盖 | `--control-invalid-border-color` `#9F1239` | 不覆盖 | `box-shadow: 0 0 0 3px #FBE7EC` | 327–328 |
| hover / active | — | — | — | — | **不存在** | — |
| 焦点 | `:focus-visible`（全局） | 不覆盖 | 不覆盖 | 不覆盖 | `outline:3px solid #0F4A42; offset 2px` | 110 |

**状态可组合性（实现必须处理）**

| 组合 | 结果 | 说明 |
| --- | --- | --- |
| `readonly` + `.field--invalid` | 危险边 **覆盖** 只读浅边（327–328 在 325 之后、特异性更高） | 语义上罕见：只读字段不应有校验错误 |
| `disabled` + `.field--invalid` | 危险边生效，但整控件 `opacity:.5` | 允许；错误文字仍须给出 |
| `readonly` + `disabled` | 两者都生效 | 无意义组合，实现应禁止 |
| `.textarea[readonly]` | **无 rb.css 规则** → 与常态**视觉完全相同** | **缺口，见 §2.9** |

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明（上游链仅供解释） |
| --- | --- | --- | --- |
| 控件 `background` | `--control-bg` | `#FFFFFF` | 经 L2 `--bg-card` |
| 控件 `color` | `--control-fg` | `#1C1917` | 经 L2 `--text-primary` |
| 控件 `border-color` | `--control-border-color` | `#78716C` | 经 L2 `--border-field` |
| 控件 `border-width` | `--control-border-w` | `1px` | 上游 `--p-bw-1` |
| 控件 `border-radius` | `--control-radius` | `10px` | 上游 `--p-radius-10` |
| 控件 `min-height` | `--control-min-h` | `44px` | 经 L2 `--size-control-min`；**触控目标验收值** |
| 控件 `padding-block` | `--control-pad-y` | `10px` | 上游 `--p-space-10px` |
| 控件 `padding-inline` | `--control-pad-x` | `12px` | 上游 `--p-space-2` |
| `.textarea` `min-height` | `--control-textarea-min-h` | `120px` | 上游 `--p-size-textarea-min` |
| `.textarea` `line-height` | `--control-textarea-lh` | `1.6` | 上游 `--p-lh-control` |
| `[readonly]` `background` | `--control-readonly-bg` | `rgba(28,25,23,.03)` | 经 L2 `--bg-readonly`；**含 alpha** |
| `[readonly]` `border-color` | `--control-readonly-border-color` | `#E7E5E4` | 经 L2 `--border` |
| `[readonly]` `color` | `--control-readonly-fg` | `#5B544E` | 经 L2 `--text-secondary` |
| `[disabled]` `opacity` | `--control-disabled-opacity` | `0.5` | 上游 `--p-opacity-disabled` |
| `.field--invalid` `border-color` | `--control-invalid-border-color` | `#9F1239` | 经 L2 `--danger-border` |
| `.field--invalid` `box-shadow` | `--control-invalid-ring` | `0 0 0 3px #FBE7EC` | 复合值；`3px` 上游 `--p-bw-3`，色经 L2 `--state-danger-tint` |
| `.error-summary` `border-color` | `--errorsummary-border-color` | `#9F1239` | 见 §四 |
| `.error-summary` `border-width` | `--errorsummary-border-w` | `1px` | 见 §四 |
| `.error-summary` `background` | `--errorsummary-bg` | `#FBE7EC` | 见 §四 |
| `.error-summary` `border-radius` | `--errorsummary-radius` | `10px` | 见 §四 |
| `.error-summary` `padding-block` | `--errorsummary-pad-y` | `12px` | 见 §四 |
| `.error-summary` `padding-inline` | `--errorsummary-pad-x` | `18px` | 见 §四 |
| `.error-summary` `margin-bottom` | `--errorsummary-margin-b` | `18px` | 见 §四 |
| `.error-summary` `color` | `--errorsummary-fg` | `#7B0E2C` | 见 §四 |

> **`--control-invalid-ring` 的解析值必须逐字为 `0 0 0 3px #FBE7EC`**：`--p-bw-3` 是 `3px`，`--state-danger-tint` 是 `#FBE7EC`。
> 实现里把颜色写成 L2 的 `--state-danger-tint` 是**跨层违规**；写成 `0 0 0 3px #FBE7EC`（裸值）同样违规。
> 唯一正确写法：`box-shadow: var(--control-invalid-ring)`。

### 6. 无障碍要求

| 要求 | 具体做法 |
| --- | --- |
| 可访问名 | 由 `.field__label` 的 `for` 提供；`select` 无 `label` 时不得用首个 `option` 顶替 |
| 触控目标 | `min-height` = `--control-min-h` = **44px**（rb.css:320）；`b-spec` §6 与 `b-spec` 验收清单 4 |
| 非法语义 | `aria-invalid="true"` + `aria-describedby` = 错误 `id` |
| 只读语义 | 原生 `readonly`：**可聚焦、可选中、会被提交**，屏幕阅读器播报「只读」 |
| 禁用语义 | 原生 `disabled`：**不可聚焦、不提交**；不得用 `aria-disabled` + CSS 假装 |
| 只读 vs 禁用可辨 | 只读：灰底 + 浅边 + 次级文字 + 说明原因的文字；禁用：`opacity:.5`（视觉与语义双通道，`content-spec` §1） |
| 焦点 | 全局 `:focus-visible`（rb.css:110）；组件**不得**改写 `outline` |
| 对比度 | 控件边界 vs 控件底 **4.80:1** ≥3:1（1.4.11）；只读文字 vs 只读底 **7.00:1** ≥4.5:1（含 alpha 合成，`tokens.md` §7） |
| 缩放 | 正文 17px 不随断点缩小（`b-spec` §6），≥16px 避免 iOS 自动缩放；`html{-webkit-text-size-adjust:100%}`（rb.css:94） |
| 数字不跳动 | `body{font-variant-numeric:tabular-nums}`（rb.css:100）——时间/日期输入的值显示需继承 |

### 7. 内容与文案规则

| 场景 | 逐字文案 | 出处 |
| --- | --- | --- |
| 只读原因（S10 课程代码） | `课程代码创建后不可修改` | content-spec:145 |
| 只读原因（S09 来源） | 来源字段标 **只读** | content-spec:135 |
| S02 输入区辅助文字 | `最多 2000 字` | content-spec:69 |
| S02 输入区 label | `你的问题` | content-spec:69 |
| S09 搜索框 label | 可见 label，按标题筛选 | content-spec:129 |
| 字数上限 | 标题 ≤100 / 目标 ≤500 / 正文 ≤10,000 / 简介 ≤2000 / 冲突原因 ≤500 | content-spec:135、145、170 |
| 冲突原因 | `必填` | content-spec:170 |

**禁止**：用 `placeholder` 承载唯一说明（必需说明写进 `field__hint`）；用 emoji 当图标（`content-spec` §3）；自造错误文案。

### 8. 响应式行为

| 档 | 行为 | rb.css |
| --- | --- | --- |
| base–xs（<768） | 控件**始终 100% 宽**、`min-height:44px`；不因窄屏缩小字号或内边距 | 319–320 |
| sm（≥768） | **控件本身无变化**；变的是父级 `.form-grid--2` 变成 2 列 | 312–313 |
| md–xl | 无变化 | — |

> 关键点：`b-spec` §6 明确「间距不随断点线性放大，组件内部间距保持不变」。
> 因此 `.input` 的 `padding`/`min-height` 在任何档位都是同一组 token，**不写媒体查询**。

### 9. 契约依据与禁止事项

| 依据 | 内容 |
| --- | --- |
| rb.css | 319–324（基础+textarea）、325（只读）、326（禁用）、327–328（非法）、110（全局焦点） |
| README 硬要求 | 4（状态矩阵只写真实状态）、5（行号锚点）、6（无障碍具体到属性） |
| b-spec | §6 触控目标、§7 表单无障碍、验收清单 4/5 |
| content-spec | §1 只读 vs 禁用、触控 44px、标签可见；§2 各屏上限 |

**已登记的缺口（rb.css 未实现，规格不补写、实现不得发明）**

| 缺口 | 现状 | 影响与建议 |
| --- | --- | --- |
| `.textarea[readonly]` | rb.css:325 只写 `.input[readonly]` | 只读 textarea 与常态**视觉完全相同**。当前 S09/S10 的只读字段都是 `input`（来源、课程代码），**未触发**。若将来出现只读 textarea，须先改 rb.css 再改本规格（不得在组件里补 CSS） |
| `.textarea[disabled]` / `.select[readonly]` | 同上，未定义 | `textarea[disabled]` 仍受浏览器默认降透明度影响，但**不是** `--control-disabled-opacity` 的统一值 |
| `.input[disabled]` 的底色 | rb.css:326 只改 `opacity` | 禁用控件的底色仍是纯白，与只读的灰底在**弱视觉**下易混；区分主要靠 `opacity` 与不可聚焦性 |
| `.field--invalid` 的 `field__error` | CSS 只负责 `.field--invalid` 后代控件的边框 | `field__error` **不会**因 `.field--invalid` 自动出现，必须由模板条件渲染 |

**禁止**

1. 禁止写 `.input:hover`、`.input:focus`、`.input:active`、`.input.valid` 等 rb.css 中不存在的状态。
2. 禁止在组件里覆盖 `:focus-visible`。
3. 禁止用 `border-color` 单通道表达非法（必须配文字 + `aria-invalid`）。
4. 禁止把 `min-height` 降到 44px 以下（`--control-min-h` 是验收值）。
5. 禁止对 `.select` 用 `appearance:none` 后再自绘箭头——rb.css 未定义，会引入未登记样式。
6. 禁止在组件规则里写 `var(--p-*)` 或 `var(--bg-*)` 等 L1/L2。

---

## 三、FormGrid `.form-grid`

### 1. 用途与边界

| 项 | 内容 |
| --- | --- |
| 用途 | 表单字段的**列容器**。base–xs 单列；sm 起 `.form-grid--2` 变两列，`.field--wide` 跨满两列 |
| 用 | S09 计划编辑表单、S10 课程新建/编辑表单、S12 课表维护表单、S01 登录（单列，不加 `--2`） |
| 不用 | 字段之外的布局（卡片并排用 `.card-row--2`，rb.css:181–182，不属本文件 owns）；纯按钮组用 `.row`（§五） |
| 归属说明 | `.form-grid` 的 token 落在 **`field` 组**（`--field-grid-gap`），class 在本节定义 |

### 2. 结构（DOM 骨架）

```html
<!-- S09 / S10 表单：≥768 两列，标题与正文跨列 -->
<form class="form-grid form-grid--2" novalidate>
  <div class="field">
    <label class="field__label" for="t">标题 <span class="field__req">必填</span></label>
    <input class="input" id="t" name="title" maxlength="100">
  </div>
  <div class="field">
    <label class="field__label" for="s">开始日期</label>
    <input class="input" id="s" name="start_date" type="date">
  </div>
  <div class="field field--wide">                          <!-- 跨两列 -->
    <label class="field__label" for="b">正文 <span class="field__req">必填</span></label>
    <textarea class="textarea" id="b" name="body" maxlength="10000"></textarea>
  </div>
</form>

<!-- S01 登录：单列，不加 --2 -->
<form class="form-grid"> … </form>
```

| DOM 约束 | 依据 |
| --- | --- |
| 直接子元素必须是 `.field`（`grid-template-columns` 的轨道数按子元素计） | rb.css:311–313 |
| `.field--wide` 必须**同时**是 `.form-grid--2` 的后代，否则 `grid-column:1/-1` 不生效 | rb.css:313 |
| 不要把 `<button>` 直接放进 `.form-grid` 参与列轨道——放进 `.field--wide` 内的 `.row`（§五） | rb.css:311 |
| 表单不得嵌在 `.table-wrap` 内做内联编辑（会与卡片化 grid 冲突） | §四.9 |

### 3. API 表

| class | 元素 | 作用 | rb.css |
| --- | --- | --- | --- |
| `.form-grid` | `form` / `div` | `display:grid; gap:--field-grid-gap; grid-template-columns:1fr` | 311 |
| `.form-grid--2` | 修饰 | **仅 ≥768** 时 `repeat(2,1fr)` | 312 |
| `.field--wide` | 修饰 `.field` | **仅 ≥768 且父级有 `--2`** 时 `grid-column:1/-1` | 313 |

### 4. 状态矩阵

| 状态 | 是否存在 | 说明 |
| --- | --- | --- |
| 单列（默认） | ✅ | base–xs 的全部宽度；`.form-grid` 不带 `--2` 时的全部宽度 |
| 两列 | ✅ | `min-width:768px` **且** 元素有 `.form-grid--2`（rb.css:312） |
| 跨列 | ✅ | 上一条件 **且** 子元素有 `.field--wide`（rb.css:313） |
| 折叠 / 展开 / 加载 | ❌ | rb.css 未定义，不得发明 |

> 注意：`.form-grid--2` **单独**在 `<768` 下不会变成两列——312 整条声明在媒体查询内部。
> `.field--wide` 在 `<768` 下是**空操作**（单列时 `1/-1` 与 `1` 等价，即便生效也看不出差别）。

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明（上游链仅供解释） |
| --- | --- | --- | --- |
| `.form-grid` `gap` | `--field-grid-gap` | `18px` | 上游 `--p-space-3`；行/列间距同一个值 |

### 6. 无障碍要求

| 要求 | 具体做法 |
| --- | --- |
| 结构语义 | 表单用 `<form>`；字段顺序 = DOM 顺序 = 视觉顺序（`grid` 不重排，`order` 未使用） |
| 分组 | 字段多时可加 `<fieldset>` + `<legend>`；**不得**用 `role="group"` 代替可见标题 |
| 错误汇总 | 提交失败时在**表单之前**放 `.error-summary`（§四），并把焦点移到它 |
| 焦点顺序 | `grid` 的两列仍是 DOM 顺序（左→右、上→下），无需 `tabindex` 干预 |
| 触控 | 不改变子控件尺寸；子控件自身满足 44px（§二.6） |

### 7. 内容与文案规则

本组件**不承载文案**（纯布局）。文案全部在 `.field` 内（§一.7）。

### 8. 响应式行为

| 档 | 列数 | 依据 |
| --- | --- | --- |
| base–xs（<768） | **1 列**（`.form-grid--2` 也不生效） | rb.css:311–312；`b-spec` §2「表单列数 1」 |
| sm（≥768） | **2 列**（仅 `.form-grid--2`） | rb.css:312；`b-spec` §2「表单列数 2」 |
| md–xl | 2 列，**不再加宽列数** | `b-spec` §1（xl「不放大字号、不加宽内容」） |

`b-spec` §4 组件响应式行为表的原始行：

| 组件 | `<480` | `480–767` | `≥768` |
| --- | --- | --- | --- |
| `.form-grid--2` | 1 列 | 1 列 | 2 列（`.field--wide` 跨两列） |

### 9. 契约依据与禁止事项

| 依据 | 内容 |
| --- | --- |
| rb.css | 311（基础）、312（两列）、313（跨列） |
| b-spec | §1 断点、§2 表单列数、§4 组件行为表 |
| README 硬要求 | 9（响应式用断点档位表述） |

**禁止**

1. 禁止把 `.form-grid--2` 写成「窄屏也两列」——312 整条在媒体查询内。
2. 禁止引入第三个断点（如 640px 折中）——`b-spec` §1「组件里不得出现临时断点」。
3. 禁止给 `.form-grid` 写 `grid-template-columns` 的 `minmax` 响应式魔法值；列数只由这两个 class 决定。
4. 禁止在 `.form-grid` 内混入非 `.field` 的裸控件（会被当成独立网格项放进某列）。

---

## 四、ErrorSummary `.error-summary`

### 1. 用途与边界

| 项 | 内容 |
| --- | --- |
| 用途 | 提交失败时在表单顶部集中列出**全部**错误，并把焦点移到这里（`content-spec` §1「提交失败同时给出顶部错误摘要并把焦点移到摘要」） |
| 用 | S09 计划保存失败（日期校验、正文必填、409 版本冲突）、S10 课程保存失败（重复代码）、S12 课表维护校验与冲突 |
| 不用 | 单字段校验（用 `.field__error`，§一）；整页级失败且无字段可定位（用 `.notice--danger`，不属本文件 owns） |
| 与 `.field__error` 的关系 | **两者同时出现**：摘要给全局视图与聚焦落点，字段错误给就近定位。摘要里的每条是锚到字段 `id` 的链接 |

### 2. 结构（DOM 骨架）

```html
<!-- 提交失败后：摘要位于 <form> 之前，role=alert 播报，焦点移入 -->
<div class="error-summary" role="alert" tabindex="-1" id="form-errors">
  <p><strong>有 2 处需要修改：</strong></p>
  <ul>
    <li><a href="#plan-start">开始与结束日期需要同时填写，且开始日期不能晚于结束日期。</a></li>
    <li><a href="#plan-body">正文未填写。</a></li>
  </ul>
</div>

<form class="form-grid form-grid--2" novalidate> … </form>
```

| DOM 约束 | 依据 |
| --- | --- |
| 位置：`<form>` **之前**（`margin-bottom:--errorsummary-margin-b` 说明它是上方块） | rb.css:330 |
| `tabindex="-1"` 是**必需**的：`.error-summary` 本身不可聚焦，不设就无法用脚本 `focus()` | 用户可见焦点落点要求 |
| 每条错误是 `<a href="#字段id">`，锚点必须指向**真实存在**的字段 `id` | rb.css:331 给 `.error-summary a` 定色，说明链接是预期用法 |
| 仅在**存在错误时**渲染；无错误时**不渲染空的摘要容器** | 空容器会被屏幕阅读器读到 |

### 3. API 表

| class / 属性 | 元素 | 作用 | rb.css |
| --- | --- | --- | --- |
| `.error-summary` | `div` / `section` | 危险色边框 + 危险色浅底 + 圆角 + 内边距 + 下外边距 | 329–330 |
| `.error-summary a` | `a` | 错误项链接，危险色 | 331 |
| `role="alert"` | 摘要容器 | 动态插入时立即播报 | — |
| `tabindex="-1"` | 摘要容器 | 允许脚本 `focus()` 作为焦点落点 | — |

### 4. 状态矩阵

| 状态 | 是否存在 | 说明 |
| --- | --- | --- |
| 显示（有错误） | ✅ | rb.css:329–331 |
| 隐藏（无错误） | ✅（靠**不渲染 DOM**） | rb.css **没有** `.error-summary[hidden]` 之类的规则；用条件渲染，不用 `display:none` 切换 |
| 单错 / 多错 | 同一个样式 | 无 `--single` / `--multi` 变体 |
| hover / focus（容器本身） | ❌（容器不可聚焦） | 内部 `<a>` 的 hover 由浏览器默认，rb.css 未定义 `.error-summary a:hover` |
| 焦点落点 | ✅（`tabindex="-1"` + `.focus()`） | 视觉上由全局 `:focus-visible` 决定；脚本聚焦不触发 `:focus-visible`（符合规范，不额外加轮廓） |

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明（上游链仅供解释） |
| --- | --- | --- | --- |
| `.error-summary` `border-color` | `--errorsummary-border-color` | `#9F1239` | 经 L2 `--danger-border` |
| `.error-summary` `border-width` | `--errorsummary-border-w` | `1px` | 上游 `--p-bw-1` |
| `.error-summary` `background` | `--errorsummary-bg` | `#FBE7EC` | 经 L2 `--state-danger-tint` |
| `.error-summary` `border-radius` | `--errorsummary-radius` | `10px` | 上游 `--p-radius-10` |
| `.error-summary` `padding-block` | `--errorsummary-pad-y` | `12px` | 上游 `--p-space-2` |
| `.error-summary` `padding-inline` | `--errorsummary-pad-x` | `18px` | 上游 `--p-space-3` |
| `.error-summary` `margin-bottom` | `--errorsummary-margin-b` | `18px` | 上游 `--p-space-3` |
| `.error-summary` `color` | `--errorsummary-fg` | `#7B0E2C` | 经 L2 `--state-danger` |
| `.error-summary a` `color` | `--errorsummary-fg` | `#7B0E2C` | rb.css:331 与容器同色 |

> `--errorsummary-fg` 与 `--field-error-fg` 解析值不同（`#7B0E2C` vs `#7B0E2C`）——**两者相同但不得互借**：
> L3 禁止互引（README 分层纯度规则 3），且未来任一方调整时不应连带。

### 6. 无障碍要求

| 要求 | 具体做法 |
| --- | --- |
| 播报 | 容器 `role="alert"`（隐含 `aria-live="assertive"`）；仅在实际出现错误时插入 DOM |
| 焦点落点 | `tabindex="-1"` + `element.focus()`；`b-spec` §7「多错时给出 `.error-summary` 并可聚焦」 |
| 就近关联 | 每个错误项是 `<a href="#字段id">`，点击/回车把焦点带到出错字段 |
| 不替代字段错误 | 摘要**不能**取代 `.field__error`——屏幕阅读器用户按字段表浏览时仍需就地看到错误 |
| 图标 | 若加警示图标，`aria-hidden="true"`；标题文字（如「有 2 处需要修改：」）承载语义 |
| 对比度 | 容器文字 `#7B0E2C` 在 `#FBE7EC` 上：与 `.notice--danger` 同一配对（9.14:1，`tokens.md` §7） |
| 触控 | 错误项链接若做成块级，行高 ≥44px；不得小于 44px 的可点区域 |

### 7. 内容与文案规则

| 场景 | 逐字文案 | 出处 |
| --- | --- | --- |
| S09 日期校验 | `开始与结束日期需要同时填写，且开始日期不能晚于结束日期。` | content-spec:136 |
| S09 版本冲突 409 | `这份计划已被其他标签页修改，请重新加载后再提交；你未提交的编辑会保留。` | content-spec:137 |
| S10 重复课程代码 | `该课程代码已存在，请更换。` | content-spec:146 |
| S12 时段校验 | `结束时间必须晚于开始时间，且不支持跨日记录。` | content-spec:165 |
| S12 精确重复 409 | `该学生在同一天已有完全相同时间段的这门课，不能重复保存。` | content-spec:166 |
| S01 登录失败 | `账号或密码不正确，请重试。` | content-spec:56 |
| S01 账号被禁用 | `当前账号不可用，请联系管理员。` | content-spec:59 |

**摘要标题**（「有 N 处需要修改：」这类计数引导句）不在 `content-spec` 的逐字清单内。
**规则**：若实现需要引导句，只能由**错误条数**拼出计数，**不得**引入 `content-spec` 之外的新业务表述；
更保守的做法是省略引导句、直接排 `<ul>`（本规格推荐后者，避免自造文案）。

### 8. 响应式行为

| 档 | 行为 | rb.css |
| --- | --- | --- |
| base–xl | **无变化**：任何宽度下都是满宽块 | 329–330 |

`.error-summary` 不含媒体查询；错误文字换行由块级流自然完成。

### 9. 契约依据与禁止事项

| 依据 | 内容 |
| --- | --- |
| rb.css | 329（容器）、330（内边距与下外边距）、331（链接色） |
| content-spec | §1「提交失败同时给出顶部错误摘要并把焦点移到摘要」 |
| b-spec | §7「多错时给出 `.error-summary` 并可聚焦」 |

**禁止**

1. 禁止用 `.error-summary` 替代 `.field__error`（两者必须同时存在）。
2. 禁止在没有错误时渲染空摘要容器。
3. 禁止用 `display:none` 切换显隐——`role="alert"` 需要在插入时播报。
4. 禁止自造错误文案（只能取 §7 表中的逐字文案）。
5. 禁止把 `.error-summary` 放进 `.table-wrap` 或表格内部（会破坏卡片化 grid 轨道）。

---

## 五、TableWrap `.table-wrap`

### 1. 用途与边界

| 项 | 内容 |
| --- | --- |
| 用途 | 表格的**滚动容器 + 卡片外观**（1px 边 + 14px 圆角 + 白底）。≥768 时承担「表格自己横向滚动」的职责，保证页面级溢出为 0 |
| 用 | 所有 `.table` 的外层；S09 计划列表、S10 课程列表、S11 文档列表 |
| 不用 | 键值展示（`.kv`）；文档性超宽表格（仍用 `.table-wrap`，只是**不加** `--stackable`，见 `b-spec` §5 决策规则 4） |
| 与 `.card` 的分界 | 表格用 `.table-wrap`（无阴影、无头部区）；内容卡片用 `.card`（rb.css:185–190，不属本文件 owns） |

### 2. 结构（DOM 骨架）

```html
<!-- 必须卡片化的列表（学生主流程：<768 不允许页面级横向滚动） -->
<div class="table-wrap table-wrap--stackable">
  <table class="table table--stack">
    <caption>学习计划（按更新时间倒序）</caption>
    <thead>
      <tr><th scope="col">标题</th><th scope="col">覆盖日期</th><th scope="col">来源</th>
          <th scope="col">更新时间</th><th scope="col">操作</th></tr>
    </thead>
    <tbody>
      <tr>
        <td class="cell-name" data-label="标题">实验二排序算法预习计划</td>
        <td class="num" data-label="覆盖日期">2026-10-22 → 2026-10-24</td>
        <td data-label="来源">助手生成</td>
        <td class="num" data-label="更新时间">2026-10-21 17:20</td>
        <td data-label="操作"><a class="btn btn--sm" href="#">打开</a></td>
      </tr>
    </tbody>
  </table>
</div>

<!-- 不卡片化的文档性表格：保留自身的横向滚动，不加 --stackable -->
<div class="table-wrap">
  <table class="table"> … </table>
</div>
```

| DOM 约束 | 依据 |
| --- | --- |
| `.table-wrap` 必须是 `<table>` 的**直接父级**（`overflow-x` 作用域就是它） | rb.css:334 |
| 学生主流程的列表：`.table-wrap` **同时**带 `--stackable`，`<table>` **同时**带 `--stack` | `b-spec` §5 决策规则 2 |
| 文档性超宽表格：只带 `.table-wrap`，**不带** `--stackable` | `b-spec` §5 决策规则 4 |

### 3. API 表

| class | 元素 | 作用 | rb.css |
| --- | --- | --- | --- |
| `.table-wrap` | `div` | `overflow-x:auto`；`border:1px solid --table-border-color`；`border-radius:--table-radius`；`background:--table-bg` | 334–335 |
| `.table-wrap--stackable` | 修饰 | **仅 <768** 取消自身滚动容器与外观：`overflow-x:visible;border:0;background:transparent` | 377 |

### 4. 状态矩阵

| 状态 | 断点 | `.table-wrap` 计算值 | rb.css |
| --- | --- | --- | --- |
| 可滚动 + 卡片外观（默认） | 全部（≥768 也如此） | `overflow-x:auto; border:1px solid #E7E5E4; border-radius:14px; background:#FFFFFF` | 334–335 |
| `--stackable` 撤销态 | **<768** | `overflow-x:visible; border:0; background:transparent` | 377 |
| `--stackable` 在 ≥768 | ≥768 | 同默认态（377 在媒体查询内，不生效） | 377 媒体查询外无 |

**这是 `b-spec` §5 那条「页面级横向溢出 = 0」⚠ 的核心机制**，原文：

> `<768` 的 `.table-wrap--stackable{overflow-x:visible}` —— 它刻意取消了表格自己的滚动容器，
> 此时宽度**只能**靠 `table--stack` 卡片化来消化。也就是说：**如果后续有人删掉 `table--stack`
> 或把 `overflow-x:auto` 去掉，同一处会立刻变成页面级溢出**。

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明（上游链仅供解释） |
| --- | --- | --- | --- |
| `.table-wrap` `border-width` | `--table-border-w` | `1px` | 上游 `--p-bw-1` |
| `.table-wrap` `border-color` | `--table-border-color` | `#E7E5E4` | 经 L2 `--border` |
| `.table-wrap` `border-radius` | `--table-radius` | `14px` | 上游 `--p-radius-14` |
| `.table-wrap` `background` | `--table-bg` | `#FFFFFF` | 经 L2 `--bg-card` |

### 6. 无障碍要求

| 要求 | 具体做法 |
| --- | --- |
| 滚动容器可键盘操作 | `overflow-x:auto` 的区域在 Chrome/Edge 现代版本可被键盘聚焦滚动；若需显式支持，给容器加 `tabindex="0"` + `role="region"` + 可访问名（**由实现决定，rb.css 不提供**） |
| 焦点不被裁切 | 容器滚动时焦点元素的 `:focus-visible` 轮廓不得被 `overflow` 裁掉（`outline-offset:2px`，rb.css:110） |
| 不遮挡 | `--stackable` 在 <768 取消滚动，因此窄屏无「滚动容器吞掉焦点」的问题 |
| 语义 | `.table-wrap` 是**纯布局**容器，不加 `role`；表格语义全部由内部 `<table>` 承担 |

### 7. 内容与文案规则

本组件**不承载文案**。

### 8. 响应式行为

| 档 | `.table-wrap` | `.table-wrap--stackable` | rb.css |
| --- | --- | --- | --- |
| base–xs（<768） | `overflow-x:auto` + 卡片外观 | **覆盖**为 `overflow-x:visible; border:0; background:transparent` | 377 |
| sm（≥768） | `overflow-x:auto` + 卡片外观 | 与无修饰时相同 | — |
| md–xl | 不变 | 不变 | — |

### 9. 契约依据与禁止事项

| 依据 | 内容 |
| --- | --- |
| rb.css | 334–335（基础）、377（`--stackable`） |
| b-spec | §5 决策规则 2/4 + ⚠ 前提框 |
| README 硬要求 | 5（行号）、9（断点档位） |

**禁止**

1. 禁止在 `<768` 的 `.table-wrap--stackable` 上重新引入 `overflow-x:auto`——那会让页面级溢出验收失去前提（`b-spec` §5 ⚠）。
2. 禁止给 `.table-wrap` 加 `.card` 的阴影（`--shadow-hair` 不在 `table` 组内，会引入未登记 token 消费）。
3. 禁止把 `.table-wrap` 套在非表格元素外（`overflow-x` 会意外裁切绝对定位内容）。

---

## 六、Table `.table`

### 1. 用途与边界

| 项 | 内容 |
| --- | --- |
| 用途 | **同构多行 + 字段名固定**的列表；<768 时靠 `.table--stack` 把同一份 markup 变成卡片 |
| 用 | S09 学习计划列表（标题/覆盖日期/来源/更新时间/操作）、S10 课程列表（代码/名称/简介/状态/操作）、S11 文档与批次列表 |
| 不用 | 键值展示（`.kv`）；文档性超宽表格（不加 `--stack`，允许自身横向滚动，`b-spec` §5 规则 4）；非表格数据不得用 `<table>` 硬凑 |
| 三列数据的分界 | `content-spec` S07 课表明确「容器需给出『列表/卡片』两种可选呈现之一」——那是**列表**语义，不是表格；本组件只服务 S09/S10/S11 |

### 2. 结构（DOM 骨架）

```html
<!-- 完整示例见 §五.2。这里是必须存在的要素清单 -->
<div class="table-wrap table-wrap--stackable">
  <table class="table table--stack">
    <caption>学习计划（按更新时间倒序）</caption>          <!-- ① 必须有 caption -->
    <thead>
      <tr>
        <th scope="col">标题</th>                          <!-- ② 必须 scope="col" -->
        <th scope="col" class="r">更新时间</th>            <!-- ③ 数字列加 .r 右对齐 -->
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="cell-name" data-label="标题">期末复习总纲</td>   <!-- ④ 首列 .cell-name -->
        <td class="num r" data-label="更新时间">2026-10-20 09:05</td>
        <td data-label="操作"><a class="btn btn--sm" href="#">打开</a></td>  <!-- ⑤ 每个 td 都有 data-label -->
      </tr>
    </tbody>
  </table>
</div>
```

**要素清单（缺一不可）**

| # | 要素 | 依据 |
| --- | --- | --- |
| ① | `<caption>` | `content-spec` §1「表格有 `<caption>` 与 `scope`」 |
| ② | `th[scope="col"]` | 同上 |
| ③ | 数字列（时间/日期/编号）加 `.num`；需右对齐时另加 `.r` | rb.css:343–344 |
| ④ | 每行首列（名称/标题）加 `.cell-name` | rb.css:346、370–372 |
| ⑤ | **每个 `<td>` 都有非空 `data-label`** | rb.css:367、369；`b-spec` §5 规则 3；`build.py` 构建期硬检查 |
| ⑥ | 父级 `.table-wrap`，可卡片化的加 `--stackable` | rb.css:334、377 |
| ⑦ | 需要卡片化时 `<table>` 同时带 `.table--stack` | rb.css:351–378 |
| ⑧ | 操作列的可点元素用 `.btn--sm`（`min-height:44px`） | rb.css:206；`content-spec` §1 触控目标 |

### 3. API 表

| class | 元素 | 作用 | rb.css |
| --- | --- | --- | --- |
| `.table` | `table` | `width:100%; border-collapse:collapse; font-size:15px` | 336 |
| `.table caption` | `caption` | 左对齐、13px、弱化色、上内边距 | 337–338 |
| `.table th` / `.table td` | 单元格 | `padding:12px 18px`、左对齐、1px 下边框、`vertical-align:top` | 339–340 |
| `.table thead th` | 表头 | 13px、次级色、**`white-space:nowrap`** | 341 |
| `.table tbody tr:last-child td` | 末行 | 去掉下边框 | 342 |
| `.table .num` | 修饰 | `font-variant-numeric:tabular-nums; white-space:nowrap` | 343 |
| `.table .r` | 修饰 | `text-align:right` | 344 |
| `.table .cell-name` | 修饰 | `overflow-wrap:break-word; min-width:180px; font-weight:600` | 346 |
| `.table--compact` | 修饰 | `font-size:13px` + 单元格 `padding:8px 12px` | 347–348 |
| `.table--stack` | 修饰 | **仅 <768** 触发卡片化（§七） | 351–378 |

### 4. 状态矩阵

**表格真实存在的状态只有两个修饰符 + 一个末行规则**（§0.4）：

| 状态 | 触发 | 效果 | rb.css |
| --- | --- | --- | --- |
| 基础 | `.table` | 15px 正文 + 12/18px 内边距 + `thead` 13px nowrap + 1px 分隔线 | 336–342 |
| `--compact` | `.table--compact` | 字号 13px；单元格内边距降为 `8px 12px` | 347–348 |
| `--stack` | `.table--stack`（<768） | `thead` 隐藏、行变卡、单元格变 grid | 351–378 |
| 末行 | `tbody tr:last-child td` | `border-bottom:0` | 342（宽屏）/ 358（卡片） |
| `--compact` + `--stack` | 两者叠加 | 允许：347–348 的字号/内边距在卡片形态下仍生效（`td` 的 `padding` 被 359 覆盖为 `5px 0`） | 347–359 |
| `:hover` / `--striped` / `--bordered` | — | **不存在** | — |

> **`--compact` 与 `--stack` 叠加的实测推算**：`b-spec` §4 说 `.table--compact`「不适用」于 <480、`≥768` 才「可叠加使用」。
> 原因是 compact 的单元格高度约 `8+8+13×1.75 ≈ 38.75px`（rb.css:348 的 `8px` 是**裸字面量**，未 token 化），
> 低于 44px 触控目标。**结论：`--compact` 只用于 ≥768 的管理后台表格**，
> 若在 compact 表格内放可点元素（如「编辑」「停用」），必须让按钮自带 `min-height:44px`（`.btn--sm` 满足，rb.css:206）。

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明（上游链仅供解释） |
| --- | --- | --- | --- |
| `.table` 容器 `background` | `--table-bg` | `#FFFFFF` | 经 L2 `--bg-card` |
| `.table` 分隔线 `border-color` | `--table-border-color` | `#E7E5E4` | 经 L2 `--border` |
| `.table` 分隔线 `border-width` | `--table-border-w` | `1px` | 上游 `--p-bw-1` |
| `.table` `border-radius`（由 wrap 承担） | `--table-radius` | `14px` | 上游 `--p-radius-14` |
| `.table` `font-size` | `--table-fs` | `15px` | 上游 `--p-fs-15` |
| `caption` `font-size` | `--table-caption-fs` | `13px` | 上游 `--p-fs-13` |
| `caption` `color` | `--table-caption-fg` | `#6B6259` | 经 L2 `--text-muted` |
| `caption` `padding-top` | `--table-caption-pad-t` | `12px` | 上游 `--p-space-2` |
| `caption` `padding-inline` | `--table-caption-pad-x` | `18px` | 上游 `--p-space-3` |
| `th`/`td` `padding-block` | `--table-cell-pad-y` | `12px` | 上游 `--p-space-2` |
| `th`/`td` `padding-inline` | `--table-cell-pad-x` | `18px` | 上游 `--p-space-3` |
| `thead th` `font-size` | `--table-head-fs` | `13px` | 上游 `--p-fs-13` |
| `thead th` `color` | `--table-head-fg` | `#5B544E` | 经 L2 `--text-secondary` |
| `.cell-name` `min-width` | `--table-cellname-min-w` | `180px` | 上游 `--p-size-cellname-min`；**宽屏专用**，卡片化时被置 0 |
| `.table--compact` `font-size` | `--table-compact-fs` | `13px` | 上游 `--p-fs-13` |
| `.table--compact` `padding-block` | `--table-compact-pad-y` | `8px` | 上游 `--p-space-8px` |
| `.table--compact` `padding-inline` | `--table-compact-pad-x` | `12px` | 上游 `--p-space-2` |
| 卡片化字段名列宽 | `--table-stack-label-col` | `7.5em` | 上游 `--p-size-label-col`；见 §七 |
| 卡片行 `padding-block` | `--table-stack-row-pad-y` | `12px` | 上游 `--p-space-2` |
| 卡片行 `padding-inline` | `--table-stack-row-pad-x` | `18px` | 上游 `--p-space-3` |
| 卡片单元格 `padding-block` | `--table-stack-cell-pad-y` | `5px` | 上游 `--p-space-5px` |
| 卡片字段名 `font-size` | `--table-stack-label-fs` | `13px` | 上游 `--p-fs-13` |
| 卡片字段名 `color` | `--table-stack-label-fg` | `#6B6259` | 经 L2 `--text-muted` |
| 卡片字段名 `font-weight` | `--table-stack-label-fw` | `600` | 上游 `--p-fw-semibold` |
| 卡片标题 `font-size` | `--table-stack-name-fs` | `17px` | 上游 `--p-fs-17` |
| 卡片标题 `padding-bottom` | `--table-stack-name-pad-b` | `8px` | 上游 `--p-space-8px` |
| 卡片标题字段名 `margin-bottom` | `--table-stack-name-label-margin-b` | `2px` | rb.css:372。**收口时补齐**：与上一行是**两处不同的值**（8px vs 2px），此前只能借用 `--notice-ico-offset-y`（值同为 2px 但语义不符） |
| 卡片 caption `padding-bottom` | `--table-stack-caption-pad-b` | `12px` | 上游 `--p-space-2` |

**`--table-stack-*` 六个 token 全部只在 `max-width:767px` 内被消费**（rb.css:355–375），
这解释了为什么它们的名字带 `stack`：宽屏形态完全不使用它们。

### 6. 无障碍要求

| 要求 | 具体做法 |
| --- | --- |
| 表格语义 | 必须是真 `<table>`；不得用 `div` + `role="table"` 拼 |
| 标题 | `<caption>` 必须有（可见） |
| 表头关联 | `<th scope="col">`；行头用 `<th scope="row">`（rb.css 未对 `th` 做区别样式，默认样式即可） |
| 卡片化的语义代价 | `<768` 下 `thead{display:none}`（rb.css:352）会让表头从**可访问性树中消失**。补偿：`td::before{content:attr(data-label)}` 只是**视觉**文本，屏幕阅读器**不会**把它当成表头 |
| 因此 | 每个 `<td>` 的 `data-label` 是**唯一**的字段名兜底；这也是「必须写 `data-label`」除了视觉之外的第二重理由 |
| 装饰图标 | 单元格内的内联 SVG 一律 `aria-hidden="true"` |
| 操作按钮 | 表格内次级图标按钮 ≥32×32 且带可访问名（`content-spec` §1）；本方向统一用 `.btn--sm`（`min-height:44px`，rb.css:206）更保险 |
| 数字 | `.num` 的 `tabular-nums` 同时服务「不跳动」与可读性 |
| 对比度 | 表格正文 `#1C1917`/`#FFFFFF` **17.49:1**；表头 `#5B544E`/`#FFFFFF` **7.44:1**；卡片字段名 `#6B6259`/`#FFFFFF` **5.97:1**（均 ≥4.5:1，`tokens.md` §7） |

### 7. 内容与文案规则

| 场景 | 逐字文案 | 出处 |
| --- | --- | --- |
| S09 列名 | `标题` / `覆盖日期` / `来源` / `更新时间` / `操作` | content-spec:130 |
| S09 行数据 | `实验二排序算法预习计划` / `2026-10-22 → 2026-10-24` / `助手生成` / `2026-10-21 17:20` / 「打开」「删除」 | content-spec:131 |
| S09 第二行 | `期末复习总纲` / `未设置日期` / `手动创建` / `2026-10-20 09:05` / 「打开」「删除」 | content-spec:132 |
| S09 空列表 | `还没有学习计划。` | content-spec:133 |
| S09 新建 | `新建计划` | content-spec:134 |
| S09 删除确认 | `删除「实验二排序算法预习计划」？删除后无法恢复。助手对话不受影响。` | content-spec:138 |
| S10 列名 | `课程代码` / `名称` / `简介` / `状态` / `操作` | content-spec:141 |
| S10 行数据 | `CS201` / `数据结构` / `计算机学院专业基础课` / `启用` / 「编辑」「停用」 | content-spec:142 |
| S10 第二行 | `CS310` / `操作系统` / `计算机学院专业基础课` / `已停用` / 「编辑」「启用」 | content-spec:143 |
| S10 主按钮 | `新建课程` | content-spec:144 |
| S11 批次摘要 | `批次 batch_9F3K · 3 个文件 · 状态 处理中 · 发布规则 整批可见或整批不可见` | content-spec:152 |
| S11 五态 | `可检索` / `处理中` / `失败` / `删除中` / `删除失败` | content-spec:154–158 |
| S11 OCR 失败原因 | `未提取到文字，可能是扫描件；本期不支持 OCR。` | content-spec:156 |
| S11 整批回滚 | `本批 1 个文件失败，整批未发布；其他批次不受影响。` | content-spec:159 |
| S11 行内额外信息 | 原名、类型、大小、上传时间、批次、错误原因（**不得出现服务器磁盘路径**） | content-spec:160 |

**规则**

| 规则 | 内容 |
| --- | --- |
| `data-label` 的值 | 必须与同一列 `thead th` 的**可见文本逐字相同**（S09/S10 列名见上表）。不得为了卡片好看而缩写 |
| 空值表达 | `未设置日期`（content-spec:132）——**不得**用 `—`、`N/A`、`暂无` 顶替 |
| 状态列 | 用 `.pill`（「图标 + 文字 + 颜色」三重，rb.css:209–220，不属本文件 owns）；文字必须逐字取上表 |
| 禁止 | 「暂无数据」「共有 N 条」这类 `content-spec` 之外的表述 |

### 8. 响应式行为

| 档 | 形态 | rb.css |
| --- | --- | --- |
| base–xs（<768） | **卡片**（仅当带 `.table--stack`）：`thead` 隐藏、`tr` 为卡、`td` 为两列 grid | 351–378 |
| sm（≥768） | **表格**：`thead` 出现，`th` 13px nowrap，单元格 12/18px；超宽时由 `.table-wrap` 横向滚动 | 336–348 |
| md–xl | 表格，无变化 | — |

`b-spec` §5 决策规则（写死，不得各页各写一套）：

| # | 规则 |
| --- | --- |
| 1 | 数据是**同构多行 + 字段名固定**的列表 → 用 `.table` |
| 2 | 该列表在 `<768` 下**不允许**页面级横向滚动 → `.table` 必须同时加 `.table--stack`，并用 `.table-wrap` 包裹 |
| 3 | 每张 `.table--stack` 的**每个 `<td>` 都必须写 `data-label="字段名"`** |
| 4 | 超宽表格（如文档 Token 表）允许保留横向滚动，**不卡片化**，但必须是表格自己滚动 |

### 9. 契约依据与禁止事项

| 依据 | 内容 |
| --- | --- |
| rb.css | 336–348（基础与修饰）、351–378（卡片化，详见 §七） |
| b-spec | §4 组件行为表、§5 判定规则与 ⚠、§9 验收清单 3 |
| content-spec | §1 表格 `<caption>`+`scope`、长文本 `break-word`+`min-width`；§2 S09/S10/S11 文案 |
| build.py | 构建期检查「带 `table--stack` 的表格里每个 `<td>` 都有 `data-label`」 |

**禁止**

1. **禁止在表格单元格里用 `overflow-wrap:anywhere`**（rb.css:345 的注释就是为这条写的）：它会降低 min-content 宽度，在 `table-layout:auto` 下把该列压到约 1 个字符宽。表格内一律 `break-word` + `min-width`。
2. 禁止给非表格元素加 `.num` / `.r` / `.cell-name`（三者的选择器都带 `.table` 前缀，脱离表格无效果，属于死代码）。
3. 禁止用 `.table--stack` 却不写 `data-label`（构建期会失败，且窄屏渲染空字段名）。
4. 禁止把 `.table--stack` 用在文档性超宽表格上（会破坏 `b-spec` §5 规则 4 的「允许横向滚动」路径）。
5. 禁止在 `<768` 给 `.table` 加自定义 `min-width` 来"保住列宽"——堆叠形态下每一行都是卡片，任何 `min-width` 都会撑破卡片（§七.6）。
6. 禁止在 `<td>` 内嵌套 `<table>`（卡片化后 grid 轨道会被内层表格破坏）。

---

### 7. 表格 → 卡片（`max-width:767px`）逐条判定规则

> **本节是整份原型里最难、踩坑最多的部分**（`b-spec` §5 与 rb.css:350–378 的注释都是实测换来的）。
> 下面**每一条都逐行对应 rb.css:351–378**，并给出**为什么**以及**漏掉它的实测代价**。
> 「实测」指原型在 320/390/768 宽度下的实拍与数值探针（来源：`b-spec` §5、rb.css:353–355 与 362–365 的注释）。


**7.1. 规则作用域**

| 项 | 值 |
| --- | --- |
| 媒体查询 | `@media (max-width:767px)`（rb.css:351） |
| 覆盖档位 | **base（<480）+ xs（480–767）** 两档合并 |
| 断点来源 | `tokens.json` `breakpoint.sm = 768`；`max-width` 只能写 `768 − 1 = 767`（`meta.purity_rules`） |
| 生效前提 | `<table>` 必须带 `.table--stack`（rb.css 所有规则的祖先选择器都是它） |
| 退出条件 | ≥768 时整块不生效，表格回到 `thead` 可见的宽屏形态 |


**7.2. 逐条规则 + 为什么**

| # | 规则（逐字对应 rb.css） | 行号 | 为什么 / 漏掉的实测代价 |
| --- | --- | --- | --- |
| **R1** | `.table--stack thead{display:none}` | 352 | 卡片形态下字段名由 `td::before` 提供，表头行会变成一张空卡（5 个 13px 列名挤成一行）。隐藏后**表头从可访问性树消失**，因此 `data-label` 成为唯一字段名兜底（§六.6） |
| **R2** | `.table--stack caption{display:block;width:auto;padding:0 0 12px}` | 353–355 | **必须同时改 `display:block`。** 表格变 `display:block` 后，`table-caption` 会 shrink-to-fit 到 **min-content（约 62px）**，说明文字**每行只排一个字**。320/390 实拍确认过。只改 `width:auto` 不够——`display:table-caption` 的 shrink-to-fit 由 display 决定 |
| **R3** | `.table--stack,.table--stack tbody,.table--stack tr,.table--stack td{display:block;width:auto}` | 356 | 四层**全部**要改 `display:block`。少改 `tbody`：浏览器的表格布局算法仍参与，`tr` 的 block 化不彻底；少改 `width:auto`：`table` 的 `width:100%`（rb.css:336）会让卡片宽度计算错位 |
| **R4** | `.table--stack tr{border-bottom:1px solid ...;padding:12px 18px}` | 357 | `<tr>` 成为**一张卡**：用下边框做卡间分隔，`12px 18px` 是卡片内边距（`--table-stack-row-pad-y/x`） |
| **R5** | `.table--stack tr:last-child{border-bottom:0}` | 358 | 去掉最后一张卡的多余下边框（与宽屏 342 的 `tbody tr:last-child td` 对应） |
| **R6** | `.table--stack td{border:0;padding:5px 0;display:grid;grid-template-columns:7.5em minmax(0,1fr);gap:12px;align-items:start;overflow-wrap:break-word}` | 359–361 | 单元格变**两列 grid**：第 1 列字段名（`7.5em` ≈ 97.5px），第 2 列值。`minmax(0,1fr)` 而非 `1fr` 是必须的——`1fr` 的最小值默认 `auto`，长内容会把轨道顶宽；`minmax(0,…)` 允许收缩到 0，配合 `overflow-wrap:break-word` 才能真正换行。`border:0` 是因为卡片的分隔线已由 `tr` 承担。**`gap:12px` 用 L2 `--sp-2`，未 token 化** |
| **R7** | `.table--stack td > *{grid-column:2}` | 366 | **本节最关键的一条。** `td` 是 `display:grid` 且 `grid-auto-flow:row`（默认）。注意自动放置的**格子顺序里 `::before` 也是第 1 个 grid item**（R8 给了它 `content:attr(data-label)`，有 content 的伪元素就是网格项），所以顺序是 `::before → 子元素1 → 子元素2 → …`：`::before` 占 (行1,列1)，**子元素 1 占 (行1,列2)**，**子元素 2 占 (行2,列1)**，子元素 3 占 (行2,列2)，子元素 4 占 (行3,列1)……于是**偶数位子元素（第 2、4…个）被拉进第 1 列，与字段名伪元素抢那 97.5px**。实测把 OCR 失败原因压成**每行 6–8 字**，且与上方状态胶囊**左边缘不对齐**（胶囊在第 2 列起点，被挤到第 1 列的文字在第 1 列起点）。**当时页面级横向溢出仍是 0、所有数值探针都放行了，只有看图才发现。** 本规则把所有真实子元素钉到第 2 列；伪元素 `::before` 不受 `td > *` 选择器影响（它不是**元素**子节点），仍占第 1 列且独享该列。⚠ **机制佐证**：M1 那处 `td` 里恰好只有两个子元素（状态胶囊 + 失败原因 `<p>`），实测被压的是**第 2 个**（失败原因）——只有「第 2 个落进第 1 列」的模型能解释这个现象；若按「第 3、5…个才落第 1 列」，该单元格根本不会有元素落错列。`rb.css:362-365` 的原注释与本条一致 |
| **R8** | `.table--stack td::before{content:attr(data-label);color:#6B6259;font-size:13px;font-weight:600}` | 367–368 | 字段名由 **`data-label` 属性**渲染，不是复制一份 DOM。这就是「每个 `<td>` 都必须有 `data-label`」的视觉侧原因（`build.py` 构建期硬检查；漏写则 `::before` 渲染出**空字段名**，卡片里只剩值） |
| **R9** | `.table--stack td:not([data-label])::before{content:""}` | 369 | 兜底：没写 `data-label` 的 `td` 至少不渲染出垃圾文本。**这不是可以漏写 `data-label` 的许可**——R8 已经说明漏写的后果，构建期仍会报错 |
| **R10** | `.table--stack td.cell-name{display:block;font-size:17px;padding-bottom:8px;min-width:0}` | 370–371 | 首列升级为**卡片标题**：不再两列 grid 而是独占一行、字号升到 17px（`--table-stack-name-fs`）。**`min-width:0` 是重点**：宽屏的 `.cell-name` 有 `min-width:180px`（rb.css:346），在 320px 卡片里会**撑破卡片**（实测页面溢出 65px）。这是「宽屏 `min-width:180px`」与「窄屏 `min-width:0`」**两条不同规则**，不得写混 |
| **R11** | `.table--stack td.cell-name::before{content:attr(data-label);display:block;margin-bottom:2px}` | 372 | 标题单元格也用 `data-label` 做字段名，但改为**块级**（在标题上方）而非左侧列——因为该 `td` 已是 `display:block`（R10），不再是 grid |
| **R12** | `.table--stack .num{white-space:normal}` | 374 | 宽屏 `.num` 是 `nowrap`（rb.css:343）。在 **320px 卡片**里，`nowrap` 的时间/日期值列会撑破卡片（实测页面溢出 65px）。窄屏必须允许换行 |
| **R13** | `.table--stack .r{text-align:left}` | 375 | grid 两列形态下「右对齐」没有意义（值列左边缘已由 grid 定位）；恢复左对齐避免值列与字段名列视觉错位 |
| **R14** | `.table-wrap--stackable{overflow-x:visible;border:0;background:transparent}` | 377 | 卡片化后表格不再需要自己的横向滚动容器。**刻意取消** `overflow-x:auto`——这是 `b-spec` §5 ⚠ 的前提：宽度只能靠 `.table--stack` 卡片化消化，**删掉 `table--stack` 或改回 `overflow-x:auto` 会立刻变成页面级溢出** |


**7.3. 逐条「为什么」的代价清单（漏掉会怎样）**

| 漏掉的规则 | 可观测后果 | 严重度 |
| --- | --- | --- |
| R2 只改 `width:auto` 不改 `display:block` | caption 排成**每行 1 个字**（min-content ≈62px） | 高（看一眼就废） |
| R7（`td > *`） | 多子元素单元格里**落在第 1 列的真实子元素**（第 2、4…个，即偶数位）与字段名伪元素抢 7.5em：OCR 失败原因每行 **6–8 字**、与上方胶囊左边缘不对齐；**页面级溢出仍为 0，数值探针全部放行** | **最高**（只有看图才发现） |
| R8 / `data-label` 漏写 | 卡片渲染**空字段名**；`build.py` 构建期直接失败 | 高（构建即拦） |
| R10 `min-width:0` | 320px 卡片被 `.cell-name` 的 `min-width:180px` 撑破，**页面溢出 65px** | 高 |
| R12 `.num` 换行 | 320px 下时间/日期值列 `nowrap` 撑破卡片，**页面溢出 65px** | 高 |
| R14 | 若同时删掉 `.table--stack`：**立刻变成页面级溢出**（`b-spec` §5 ⚠ 原文） | 高 |
| R1 | 表头行变空卡；且用户仍以为表头可用 | 中 |
| R3 漏改 `tbody` | 表格布局算法残留，卡片宽度/边框错位 | 中 |
| R9 | 漏写 `data-label` 的格子在卡片里多出空白占位 | 低 |
| R13 | 值列右对齐导致与字段名列错位 | 低 |


**7.4. `data-label` 硬要求（构建期检查）**

> **每个 `.table--stack` 的每个 `<td>` 都必须有 `data-label`。**
> 规则作用于 **base–xs（<768）档**，由 `@media (max-width:767px)` 内的 `td::before{content:attr(data-label)}`（rb.css:367）消费。

| 项 | 内容 |
| --- | --- |
| 检查器 | [`build.py`](../../responsive/build.py) 的 `check_stack_tables()`（build.py:59–68） |
| 检查方式 | 正则找出所有 `<table>`；对带 `table--stack` 的，逐个 `<td>` 检查 `data-label` 是否存在（build.py:61–67） |
| 报错文本 | `%s: 一处 <td> 缺 data-label（窄屏会显示空字段名）：%s`（build.py:68） |
| 构建期汇总 | build.py:140 的「全部通过（class 契约 / data-label / 无 style / 无 @media / 无裸 hex / 无 emoji）」 |
| 值的要求 | `data-label` 的值必须与同列 `thead th` 的可见文本**逐字相同**（§六.7） |
| 不接受 | `data-label=""`（空串）、只有空格、用序号代替字段名 |

**两重理由**（都在本节出现过，实现者必须同时理解）：

1. **视觉**：R8 —— `td::before` 是字段名的唯一来源。
2. **语义**：R1 —— `thead{display:none}` 让表头从可访问性树消失，`data-label` 是屏幕阅读器用户拿到字段名的唯一线索（`::before` 的 `content` 不进入可访问性树）。


**7.5. 卡片形态的完整 DOM 断言清单**

一份合规的 S09 行，在 <768 下必须满足：

```text
tr                       → display:block，border-bottom 1px #E7E5E4，padding 12px 18px
  td.cell-name           → display:block（非 grid），font-size 17px，padding-bottom 8px，min-width 0
    td.cell-name::before → content:"标题"（来自 data-label），display:block，margin-bottom 2px
    td.cell-name 的文本  → 「实验二排序算法预习计划」
  td.num[data-label]     → display:grid，两列 [7.5em | minmax(0,1fr)]，gap 12px，padding 5px 0
    td::before           → content:"覆盖日期"，13px，600，#6B6259，占第 1 列
    值元素（直接子元素）  → grid-column:2（R7）
    .num                 → white-space:normal（R12）
  td[data-label="操作"]  → display:grid，两列
    td::before           → "操作"
    a.btn.btn--sm        → grid-column:2，min-height 44px
```


**7.6. 反例清单（实测踩过的坑，逐条禁止）**

| 反例 | 为什么错 |
| --- | --- |
| 卡片里给 `td` 加 `min-width:180px` 或复用 `.cell-name` 的宽屏 `min-width` | 320px 卡片被撑破，页面溢出 **65px**（R10） |
| 卡片里保留 `.num{white-space:nowrap}` | 同上，**65px** 溢出（R12） |
| 表格单元格用 `overflow-wrap:anywhere` | 降低 min-content，`table-layout:auto` 下该列被压到**约 1 字符宽**（rb.css:345、`content-spec` §1、`b-spec` §5） |
| 只改 `caption{width:auto}` 不改 `display:block` | caption **每行 1 个字**（R2） |
| 用 `div` + CSS grid 手搓卡片，不用 `.table--stack` | 双份 markup，且失去 `data-label` 的构建期检查；`b-spec` §5 明确要求「同 markup 双形态」 |
| 在 `<768` 给 `.table-wrap--stackable` 加回 `overflow-x:auto` | 与 `b-spec` §5 ⚠ 冲突，掩盖卡片化失效 |
| 认为"数值探针放行 = 没问题" | R7 的 bug **页面级溢出为 0、所有数值探针都放行**，只有看图才发现。表格改动**必须**在 320/390/768 三宽度截图人工确认（`b-spec` 验收清单 7） |


**7.7. 已知的临界区（改动时必须重测）**

| 项 | 内容 |
| --- | --- |
| 位置 | **S09 学习计划表** |
| 现象 | **767–899px** 区间有 **25–57px 的内部滚动**（768 下为 **57px**） |
| 现状 | 滚动被封闭在 `.table-wrap` 内，**页面级 `scrollWidth − clientWidth` 仍为 0**，判定为可接受 |
| 为什么是临界区 | 它是「页面级溢出 = 0 完全依赖 `.table-wrap{overflow-x:auto}` 消化超宽内容」这条前提的**活例证**（`b-spec` §5 ⚠） |
| 行动 | 任何触及此表的改动（列增删、`.cell-name` 文案变长、`--table-cellname-min-w` 调整）**必须重测 767–899px 区间**的容器内滚动量 |

---

## 八、Utility `.stack` / `.row` / `.spacer` / `.muted` / `.small`

### 1. 用途与边界

| class | 用途 | 用 | 不用 |
| --- | --- | --- | --- |
| `.stack` | 纵向 flex 容器，间距 `--stack-gap`（12px） | 表单外的纵向排布：错误摘要内的条目、卡片体内的字段组 | 表单字段列（用 `.form-grid`）；`.chat` 已有自己的 `gap`（rb.css:234） |
| `.row` | 横向 flex，`flex-wrap:wrap`，垂直居中，间距 `--row-gap`（12px） | 按钮组、日期导航（`‹` + 日期 + `›`）+「今天」、页脚工具行 | 需要精确列宽的布局（用 grid） |
| `.spacer` | `margin-left:auto` 把后续元素推到行尾 | `.row` / `.card__foot` 里的「主操作靠右」 | 单独使用（没有 flex 父级时无效果） |
| `.muted` | 弱化文字色 `--muted-fg`（`#6B6259`） | 页脚时间说明、统计性小字 | 正文（对比度达标但语义上会削弱层级）；**不得**用于错误文案 |
| `.small` | 13px 小字 | 与 `.muted` 搭配的辅助信息 | 正文；**不得**用于唯一信息的承载（13px 偏小，不承担关键文案） |

**共同定位**：这 5 个是**布局/排版原子**，不是组件。它们不出现在 `tokens.json` 的组件命名规范里，
但 `utility` 组是它们的 token 归属（`--stack-gap` / `--row-gap` / `--muted-fg` / `--small-fs`）。

### 2. 结构（DOM 骨架）

```html
<!-- .row + .spacer：主操作靠右 -->
<div class="row">
  <span class="muted small">时间为学校时区 Asia/Shanghai</span>
  <button class="btn btn--primary">保存为我的计划</button>
  <span class="spacer"></span>                    <!-- 放在要推开的元素之前 -->
  <button class="btn btn--ghost">继续修改</button>
</div>

<!-- .stack：纵向间距 -->
<div class="stack">
  <div class="field"> … </div>
  <div class="field"> … </div>
</div>

<!-- .muted + .small：弱化小字 -->
<p class="muted small">登录会话有效期 2 小时，到期后需要重新登录。</p>
```

| DOM 约束 | 依据 |
| --- | --- |
| `.spacer` 必须是 `.row` / `.card__foot` 等 flex 容器的**直接子元素** | `margin-left:auto` 只对 flex 项生效（rb.css:391） |
| `.spacer` 本身**无内容**（用空 `<span>`），不得塞文本 | 它只承载 `margin-left:auto` |
| `.muted` 与 `.small` 可叠加，顺序无关（两者属性不冲突） | rb.css:387–388 |

### 3. API 表

| class | 元素 | 作用 | rb.css |
| --- | --- | --- | --- |
| `.stack` | `div` | `display:flex; flex-direction:column; gap:--stack-gap` | 389 |
| `.row` | `div` | `display:flex; flex-wrap:wrap; gap:--row-gap; align-items:center` | 390 |
| `.spacer` | `span` | `margin-left:auto` | 391 |
| `.muted` | 任意 | `color:--muted-fg` | 387 |
| `.small` | 任意 | `font-size:--small-fs` | 388 |

**注意 `.row` 没有 `justify-content`**：其行为完全靠 `flex-wrap:wrap` + `.spacer` 驱动。
**`.row` 没有 `row-gap` 单独值**：`gap` 同时作用于行与列（`--row-gap` = 12px）。

### 4. 状态矩阵

| 状态 | 是否存在 | 说明 |
| --- | --- | --- |
| `.stack` 常态 | ✅ | rb.css:389 |
| `.row` 常态 | ✅ | rb.css:390 |
| `.row` 换行（内容超宽） | ✅（行为，非状态） | `flex-wrap:wrap` 自动换行；**这是窄屏不溢出的关键** |
| `.spacer` 有 flex 父级 | ✅ | rb.css:391 |
| `.spacer` 无 flex 父级 | 无效果 | `margin-left:auto` 在块级流里等于 `margin-left:auto`（右推但块级已满宽） |
| `.muted` / `.small` 常态 | ✅ | rb.css:387–388 |
| `:hover` / `:focus` / `--active` | ❌ | **不存在**，不得发明 |
| 响应式变体（`--stack--row` 之类） | ❌ | **不存在**；任何断点都保持同一行为 |

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明（上游链仅供解释） |
| --- | --- | --- | --- |
| `.stack` `gap` | `--stack-gap` | `12px` | 上游 `--p-space-2` |
| `.row` `gap`（行与列） | `--row-gap` | `12px` | 上游 `--p-space-2` |
| `.muted` `color` | `--muted-fg` | `#6B6259` | 经 L2 `--text-muted` |
| `.small` `font-size` | `--small-fs` | `13px` | 上游 `--p-fs-13` |

> 这 4 个 token 的名字**不带** `--utility-` 前缀（对比 `--field-*` / `--control-*` / `--table-*`），
> 这是 `tokens.json` 的既有事实，**不得**为实现整齐而改名。
> `.spacer` 的唯一属性 `margin-left:auto` **没有 token**（关键字 `auto` 无需 token 化）——这是有意的，不是遗漏。

### 6. 无障碍要求

| 要求 | 具体做法 |
| --- | --- |
| 语义中性 | 这 5 个 class **不产生语义**：`.row` 不是 `role="group"`，`.stack` 不是列表。需要分组语义时必须用 `<ul>` / `<fieldset>` |
| 阅读顺序 | `.row` 的 `flex-wrap:wrap` 可能视觉换行，但 **DOM 顺序不变**，屏幕阅读器与键盘顺序仍正确 |
| 焦点顺序 | 禁止用 `order` / `flex-direction:row-reverse` 反转视觉顺序（会造成焦点顺序与视觉不符，WCAG 2.4.3） |
| `.muted` 的对比度 | `#6B6259` vs 页面底 **5.63:1**、vs 卡片底 **5.97:1**，均 ≥4.5:1（`tokens.md` §7）——所以它能用在正文级文字上，但**不承担错误语义** |
| `.small` 的字号 | 13px 低于 16px；**不得**承载唯一的关键信息（如错误文案、按钮文字） |
| `.spacer` | 空元素，无文本，不影响可访问名 |

### 7. 内容与文案规则

| 场景 | 逐字文案 | 出处 |
| --- | --- | --- |
| S07 页脚时区说明 | `时间为学校时区 Asia/Shanghai` | content-spec:118 |
| S01 页脚 | `登录会话有效期 2 小时，到期后需要重新登录。` | content-spec:58 |
| S02 边界提示条 | `对话只保存在当前浏览器标签页，刷新或关闭后不会恢复；已保存的计划不受影响。` | content-spec:64 |
| S06 幂等小字 | `重复提交同一操作只会得到同一份计划。` | content-spec:110 |
| S12 删除前说明 | `将记录操作人` | content-spec:171 |

**规则**：`.muted` / `.small` 只用在**辅助信息**上；上述文案中属"说明性"的才可弱化，
属"必须被读到"的（如 S06 的未保存标记「未保存」）**不得**用 `.muted` 降级（该场景用 `.pill--pending` / `.draft` 承担三重表达）。

### 8. 响应式行为

| 档 | 行为 | rb.css |
| --- | --- | --- |
| base–xl | **无变化**：5 个 class 全部不含媒体查询 | 387–391 |

这是 `b-spec` §6「间距不随断点线性放大」的直接体现：`.stack` / `.row` 的 gap 在任何宽度都是 12px。
`.row` 的**换行**才是它唯一的响应式表现，而换行由内容宽度自然触发，不写断点。

### 9. 契约依据与禁止事项

| 依据 | 内容 |
| --- | --- |
| rb.css | 387（`.muted`）、388（`.small`）、389（`.stack`）、390（`.row`）、391（`.spacer`） |
| b-spec | §6 间距基准与「间距不随断点线性放大」 |
| README 硬要求 | 4（只写真实状态）、5（行号）、9（断点档位） |

**禁止**

1. 禁止给这 5 个 class 发明 `:hover` / `--active` / 断点变体。
2. 禁止用 `.row` 替代 `.form-grid--2` 做两列表单（`.row` 的换行时机由内容决定，无法保证等宽列）。
3. 禁止用 `order` / `row-reverse` 改变视觉顺序。
4. 禁止把 `.spacer` 用在非 flex 父级里当作"空占位"。
5. 禁止把本次未列出的 utility 类（`.chips`、`a.chip`，rb.css:392–396）算进本文件 owns——它们属 `chip/chips` 组，由另一份规格负责。

---

### 九、跨组件验收清单（可直接测）

| # | 检查项 | 判据 | 依据 |
| --- | --- | --- | --- |
| 1 | 表格卡片化生效 | <768 下 `.table--stack` 的 `thead` 计算值 `display:none`；`tr`/`td` 为 `block` | rb.css:352、356 |
| 2 | `data-label` 完整 | 每张 `.table--stack` 的每个 `<td>` 都有非空 `data-label`；`build.py` 构建期通过 | build.py:59–68、140 |
| 3 | 页面级横向溢出为 0 | 320/390/768/1024/1366/1440 六宽度下 `documentElement.scrollWidth − clientWidth = 0` | `b-spec` §9 验收 1 |
| 4 | `--compact` 不用于窄屏 | <768 无 `.table--compact` 实例 | `b-spec` §4 |
| 5 | 每个控件有可访问名 | 每个 `input`/`select`/`textarea` 都有非空可访问名（由 `.field__label[for]` 提供） | `b-spec` §9 验收 5 |
| 6 | 触控目标 | `input`/`select`/`textarea`/`.btn`/`a.chip` 高度 ≥44px | rb.css:320、195、393 |
| 7 | 非法态三重 | 每个非法字段同时有：危险边（`--control-invalid-border-color`）+ 外环（`--control-invalid-ring`）+ `field__error` 文字 + `aria-invalid="true"` | §一.4、§二.6 |
| 8 | 只读 vs 禁用可辨 | 只读有灰底/浅边/次级文字 + 说明文字；禁用有 `opacity:.5`、不可聚焦 | rb.css:325–326、`content-spec` §1 |
| 9 | 错误摘要可聚焦 | `.error-summary` 有 `tabindex="-1"`，提交失败后 `focus()` 到它 | `b-spec` §7 |
| 10 | 断点唯一 | 本文件范围内只出现 `max-width:767px` 与 `min-width:768px` 两个字面量 | `meta.purity_rules` |
| 11 | token 全覆盖 | `field`(11) + `control`(16 个 `--control-*` + 8 个 `--errorsummary-*` = 24) + `table`(27) + `utility`(4) = **66** 个 L3 token，全部出现在 §一.5 / §二.5 / §三.5 / §四.5 / §五.5 / §六.5 / §八.5 的消费表中；且每张表的「解析值」列与 `tokens.flat.json` 逐字相等 | `tokens.flat.json` |
| 12 | 无违禁 class | 本文件不出现 `tokens.json` `meta.scope.review` 排除的 6 个评审专用 class（断点指示器 / 视图编号 / 视图说明 / 原型横幅）；本文件对这些 class **零字面引用** | `tokens.json` `meta.scope` |
| 13 | 人工看图 | 320/390/768 三宽度截图人工确认：无压塌列、无错位、多子元素单元格左边缘对齐 | `b-spec` §9 验收 7 + §7.3 的 R7 教训 |

### 附：本文件 token 覆盖自检

| 组 | token 数 | 逐项覆盖位置 |
| --- | --- | --- |
| `field` | 11 | §一.5（`--field-error-*` 两项、`--field-gap`、`--field-label-*` 两项、`--field-req-*` 两项、`--field-hint-*` 两项、`--field-grid-gap`） |
| `control` | **24** | 16 个 `--control-*` 在 §二.5 逐项展开；8 个 `--errorsummary-*` 在 §四.5 逐项展开（并在 §二.5 汇总列出） |
| `table` | 27 | §六.5（27 项；其中 `--table-stack-*` 6 项在 §7 展开语义） |
| `utility` | 4 | §八.5（`--stack-gap`、`--row-gap`、`--muted-fg`、`--small-fs`） |
| **合计** | **66** | 11 + 24 + 27 + 4，与 `tokens.json` `component.field / control / table / utility` 的实际键数逐一相等 |

> 计数口径：`tokens.json` 把 `--errorsummary-*` 写在 `component.control` 组内，
> 因此 `control` 组按**组**算是 24 个，按**前缀**（`--control-*`）算是 16 个。
> 本规格按**组**计数（24），与 `generate.py` 的分组口径一致。
> 校验脚本若要按前缀统计，四组应按 58 计——两种口径都在此列出，避免对不上。
