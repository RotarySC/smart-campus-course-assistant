<!-- owns: card, chat, composer, cite, draft, kv, prose -->
# 对话与内容（Card / Chat / Composer / Citation / Draft / KVList / Prose）

本文件是方向 B「纸感墨绿 · 专注对话」的**对话与内容组件族**接口规格：7 个 L3 组件组
（`card` `chat` `composer` `cite` `draft` `kv` `prose`）、6 个组件、26 个 class。
实现锚点为 [`../responsive/rb.css`](../responsive/rb.css)（行号逐条给出）；
token 定义取自 [`tokens.json`](../tokens.json) 的 `component` 段，**解析值**列逐字取自
[`tokens.flat.json`](../tokens.flat.json)。

## 共享契约（6 个组件共同适用，各组件节不再重复）

| # | 契约 | 依据 | 对实现的硬约束 |
| --- | --- | --- | --- |
| S1 | **组件样式只消费 L3**。组件 CSS 里出现 `var(--p-*)`（L1）或 `var(--bg-*)`/`var(--state-*)`/`--pending`（L2）即跨层违规 | tokens.json `meta.purity_rules` 第 5 条 | 本文件所有 token 消费表只列 L3；表中出现的 L1/L2 名字**仅用于解释解析链**，不得写进组件 CSS |
| S2 | **状态不能只靠颜色**。每个状态 = 图标 + 文字 + 颜色三重 | README 硬要求 6、content-spec §1 | 状态类（`.cite--invalid` `.cite-mark--pending` `.draft--saved`）必须同时改变「文字」与「图标/线型」，不得只换色 |
| S3 | **文案只能来自 content-spec**。禁止「正在思考」「暂无数据」「AI 推理中」类表述 | README 硬要求 7、content-spec §3 | 逐字文案见各组件第 7 节；本文件不新增任何句子 |
| S4 | **断点只用 base/xs/sm/md/lg/xl 五档**（base `<480`、xs `480`、sm `768`、md `1024`、lg `1200`、xl `1440`） | b-responsive-spec §1、tokens.json `breakpoint` | 组件内禁止临时断点；`max-width` 档只允许写对应档 −1（如 `767px`） |
| S5 | **助手列宽 = 720px，`.wrap` 嵌套只留一层内边距** | rb.css:164–169 | 见下方「S5 专条」 |
| S6 | **禁止引用评审专用 class**：tokens.json `meta.scope.review` 列出的 6 个评审外壳类（断点指示器、视图编号 / 说明 / 备注、原型横幅） | tokens.json `meta.scope.review` | 本文件不在任何组件结构、示例或 CSS 片段中出现它们；需要写出来时一律省略前导点号 |
| S7 | **不得补实现中不存在的状态** | README 硬要求 4 | 本族**没有任何** `:active`、`:disabled`、`:hover`（除 `.btn`/`a.chip` 自有规则外）、`transition` 属性；状态矩阵只写 rb.css 真实存在的类与伪类 |

### S5 专条：`.wrap` 嵌套（rb.css:169）

```css
.wrap{max-width:var(--wrap-max);margin:0 auto;padding:var(--wrap-pad-y) var(--wrap-pad-x)}   /* rb.css:164 */
.wrap--assistant{max-width:var(--wrap-assistant-max)}                                        /* rb.css:165 */
@media (min-width:768px){ .wrap{padding:var(--wrap-pad-y-sm) var(--wrap-pad-x-sm)} }         /* rb.css:166 */
.wrap .wrap{padding-left:0;padding-right:0}                                                  /* rb.css:169 ← 坑 */
```

| 事实 | 值 | 说明 |
| --- | --- | --- |
| 外层 `.wrap` 内边距 | base `24px 18px`（`--wrap-pad-y` / `--wrap-pad-x`）→ ≥sm `36px 24px`（`--wrap-pad-y-sm` / `--wrap-pad-x-sm`） | 页面级留白 |
| `.wrap .wrap` 生效时 | `padding-left:0; padding-right:0`（= `--wrap-inner-pad-x: 0`） | 后代选择器，**不论中间隔多少层** |
| 内层**仍保留** `max-width:720px`（`--wrap-assistant-max` / `--wrap-assistant-max` 解析值 `720px`） | 是 | rb.css:169 只清零左右 padding，**没有**清 `max-width`；`margin:0 auto` 也保留，故助手列仍居中且恒宽 720px |
| 嵌套后果 | `.wrap > .wrap` 的实际左右内边距 = 24px/18px（外层），**不是** 48px/36px | 若内层是 `.wrap--assistant`，`max-width:720px` 在 ≥768 生效 → 720 + 2×24 = 768 > 720，内容列被外层 padding 决定 |

**实现约束**：
1. 助手片段（S02–S06 任一屏）**自带 `.wrap .wrap--assistant`**，可独立 `file://` 打开且列宽正确。
2. 助手片段被外壳包裹时，**必须**成为外层 `.wrap` 的后代，或干脆改造为外壳 `.wrap.wrap--assistant` 单层——不得同时出现「外壳 wrap + 片段 wrap」之外的第二层 wrap（第三层会再次套用 S5 的 0 padding，但**语义已不可读**，且 `max-width` 仍层层保留）。
3. 组件**不得**给自己加左右 padding 来"补偿"内层被清零的 padding——`.chat`、`.card`、`.draft`、`.cite`、`.composer`、`.kv`、`.prose` 都不含左右内边距以外壳 padding 的理由（`.card`/`.draft`/`.cite` 自己的 padding 是**卡片内部**内边距，与此无关）。
4. 该规则是 `.wrap .wrap`（后代），**不是** `> .wrap`（子代）：中间隔 `.chat` 也照样命中。写 Vue 组件时不要把 `.wrap` 当作用户可选的 props 一层层往下传。

### 组件结构清单（本文件全部 class，均在 rb.css 有定义）

| 组件 | class | rb.css 行 |
| --- | --- | --- |
| Card | `.card` `.card__head` `.card__body` `.card__foot` `.card-row` `.card-row--2` | 185–190、181–182 |
| Chat/Msg/Bubble | `.chat` `.msg` `.msg__who` `.msg--user` `.bubble` | 234–242 |
| Composer | `.composer` `.composer__row` `.composer__count` | 266–273 |
| Citation | `.cite` `.cite__head` `.cite__name` `.cite__loc` `.cite__body` `.cite--invalid` `.cite-mark--pending` | 276–288 |
| Draft | `.draft` `.draft--saved` `.draft__head` `.draft__kv` | 291–298 |
| KVList | `.kv` `.kv__row` `.kv__k` `.kv__v` | 381–384 |
| Prose | `.prose` | 170、106–110 |

**已验证的相邻组件（可复用但不在本文件 owns 内）**：`.pill` / `.pill--pending`（216）承载「未保存」「待确认」文字标记，
`.btn` / `.btn--primary` / `.btn--ghost` / `.btn--sm`（193–206）承载草稿与输入区按钮，
`.steps`（245–263）承载过程区。它们各自的 token 组归 02-actions-status.md；
本文件只规定**在哪放**，不重复定义。

### 上游契约（本文件必须体现的三条）

| # | 契约 | 出处 | 在本文件落点 |
| --- | --- | --- | --- |
| U1 | **未校验引用标记必须与已验证引用视觉可区分** | SRS FR-QA-002（260–262 行）、PRD QA-01（253–254 行）、SRS IF-007（462–472 行 `citations[]` / `Reference`） | §Citation 第 1、4、9 节 |
| U2 | **草稿默认「未保存」；写入结果未知必须显示「待确认」而不是失败** | SRS FR-CHAT-005（238–240 行）、后端详细设计 §12.2（520–545 行）、PRD PLAN-02（281–289 行） | §Draft 第 1、4、9 节 |
| U3 | **助手对话不进 URL** | SRS DEC-01（103 行）、PRD CHAT-03（241–245 行）、HLD-D03 / HLD-D11（97、105 行） | §Composer 第 1、9 节 |

---

## Card `.card`

### 1. 用途与边界

- **是**：对话族内一切「有边框的白色内容块」的底座——引用卡之外的说明卡、草稿卡之外的信息卡、并排对照（S08 两态、S10 并排说明）。
- **不是**：不是提示条（那是 `.notice`，rb.css:223）、不是空状态（`.empty`，301）、不是表容器（`.table-wrap`，334）。卡片**不承载语义色彩**：`--card-bg` 恒为卡片白，状态色只能由内部组件（`.cite--invalid`、`.draft`）带来。
- **边界**：`.card` 不得嵌套 `.card`（无对应 token，且双层 `--card-shadow` 叠加）；并排只能经 `.card-row` 承载，不得用内联 `display:flex`。
- **`.card-row--2` 语义澄清**：修饰类只定义在 `@media (min-width:768px)` 内（rb.css:182），即 **base/xs 下写不写它都一样是单列**——不要把它当成"声明两列意图"的标记，它是 sm 起的列数开关。

### 2. 结构（DOM 骨架）

```html
<!-- 单卡：__head/__body/__foot 三段均可省略，但顺序固定 -->
<section class="card">
  <header class="card__head">
    <h3>复习计划草稿</h3>
    <span class="pill pill--pending"><svg aria-hidden="true"><!-- 琥珀图标 --></svg>未保存</span>
  </header>
  <div class="card__body"> … </div>
  <footer class="card__foot">
    <button class="btn btn--primary">保存为我的计划</button>
    <button class="btn btn--ghost">继续修改</button>
  </footer>
</section>

<!-- 并排：.card-row 是栅格，子元素才是卡片；--2 只在 ≥768 起作用 -->
<div class="card-row card-row--2">
  <section class="card">…</section>
  <section class="card">…</section>
</div>
```

| 结构规则 | 说明 |
| --- | --- |
| `.card__head` 是 `display:flex; flex-wrap:wrap`（187–188） | 标题 + 状态胶囊天然一行，宽度不够自动换行；**不要**在 head 里塞正文 |
| `.card__head` 与 `.card__foot` 各带 1px `border-bottom` / 由 padding 构成视觉分区（188、190） | head 有分隔线，foot **没有** `border-top`——foot 靠 `padding-top:12px` 与 body 的 18px 内边距分层 |
| `.card-row` 只用 `gap`，不给卡片加 margin（181） | 卡片间距只能由 `--card-row-gap` 提供 |
| `.card__head` 内的状态胶囊必须是 `.pill` | 状态三重表达（图标+文字+颜色）在 02 号规格里定义，卡片不复制 |

### 3. API 表

| class | 元素 | 必填 | 允许的修饰/内容 | rb.css |
| --- | --- | --- | --- | --- |
| `.card` | `section` / `article` | 是 | 只允许 `.card__head/__body/__foot` 与 `.card-row`（后者仅在 body 内） | 185–186 |
| `.card__head` | `header` | 否 | `h2`–`h4` + `.pill`（可选）+ `.spacer`（391） | 187–188 |
| `.card__body` | `div` | 否 | 任意本文件组件（`.chat`/`.draft`/`.kv`/`.prose`/`.cite`） | 189 |
| `.card__foot` | `footer` | 否 | `.btn` 系列按钮，自动换行 | 190 |
| `.card-row` | `div` | 是（并排时） | 子元素 = `.card` | 181 |
| `.card-row--2` | 修饰 | 否 | 与 `.card-row` 同用；**≥sm 才有 2 列** | 182 |

属性约束：`.card__head` 的 `h*` 只允许 h2–h4（rb.css:106 只定义到 h4，且标题层级不得跳级）；
`.card__foot` 内按钮 ≥44px 触控高度由 `.btn` 的 `min-height:var(--btn-min-h)` 保证（195、rb.css:120）。

### 4. 状态矩阵

| 状态 | 是否存在 | rb.css | 视觉差别 | 文字/图标要求 |
| --- | --- | --- | --- | --- |
| 默认 | ✅ | 185–186 | 白底 + 1px 暖灰边 + 14px 圆角 + 极淡阴影 | — |
| 悬停 `:hover` | ❌ **实现中不存在** | — | 卡片不可点击，无悬停反馈 | 若某卡需要可点击，改用 `.btn`/`a.chip` 承载，不得给 `.card` 加 `:hover` |
| 按下 `:active` | ❌ 不存在 | — | — | — |
| 禁用 `[disabled]` | ❌ 不适用 | — | — | 卡片无禁用语义 |
| 聚焦 | 仅当内部含可聚焦元素 | 110 | `:focus-visible{outline:3px solid var(--focus);outline-offset:2px;border-radius:4px}` | 卡片本身不设 `tabindex` |
| 分段省略 | ✅ | 189–190 | 无 head/foot 时 body 独自 18px 内边距 | — |

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| 卡片底色 | `--card-bg` | `#FFFFFF` | 经 L2 `--bg-card`（上游解析链，非消费方） | 185 |
| 卡片边框色 | `--card-border-color` | `#E7E5E4` | 经 L2 `--border`（上游解析链，非消费方） | 185 |
| 卡片边框宽 | `--card-border-w` | `1px` | 外框 1px；`__head` 下分隔线同为 1px 但**无独立 token** | 185、188 |
| 卡片圆角 | `--card-radius` | `14px` | | 186 |
| 卡片阴影 | `--card-shadow` | `0 1px 1px rgba(28,25,23,.04)` | 经 L2 `--elevation-card`（上游解析链，非消费方） | 186 |
| head 上内边距 | `--card-head-pad-y` | `18px` | 简写 `padding:18px 18px 12px` | 187 |
| head 左右内边距 | `--card-head-pad-x` | `18px` | 同上 | 187 |
| head 下内边距 | `--card-head-pad-b` | `12px` | 同上 | 187 |
| head 子元素间距 | `--card-head-gap` | `12px` | `gap`，含换行后的行间距 | 187 |
| body 内边距 | `--card-body-pad` | `18px` | 四边同值 | 189 |
| foot 上内边距 | `--card-foot-pad-t` | `12px` | | 190 |
| foot 左右内边距 | `--card-foot-pad-x` | `18px` | | 190 |
| foot 下内边距 | `--card-foot-pad-b` | `18px` | | 190 |
| foot 子元素间距 | `--card-foot-gap` | `12px` | | 190 |
| 栅格间距 | `--card-row-gap` | `18px` | `.card-row` 的 `gap`；纵向（堆叠）与横向（≥sm）同值 | 181 |

**token 未覆盖的裸长度（诚实缺口，不得"补"成 token）**：`.card__head` 与 `.card__body` 之间的
`border-bottom:1px solid var(--border)`（188；`--border` 为上游 L2，非消费方）的宽度 `1px` 无独立 L3 token；
`--card-border-w` 语义是**外框**宽度，复用它会掩盖两者的可独立调整性。

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 语义元素 | 卡片用 `section`（带可访问名时）或 `article`；**不要**用 `div` 承载有标题的卡片 |
| 可访问名 | `.card__head` 内的 `h2`–`h4` 提供；无标题的纯装饰卡不得有 `aria-label` 之外的可见标题 |
| 标题层级 | 不跳级（content-spec §1「语义结构」）；`.card__head` 内的 `h*` 层级由页面决定，卡片不硬编码 |
| 分组 | 一张卡内的多组键值用 `.kv` 提供 `dl` 语义（见 §KVList），不要用裸 `div` 堆叠 |
| 对比度 | 正文 `#1C1917` on `#FFFFFF`；边框 `#E7E5E4` 是**非文字 UI**，不承担信息，不受 3:1 约束 |
| 触控 | 卡内按钮继承 `.btn` 的 `min-height:44px`（rb.css:120） |
| 状态 | 卡片自身无状态；内部状态胶囊必须三重表达（S2） |
| 焦点 | 卡片不做焦点容器（不设 `tabindex`），焦点由内部控件承载，`:focus-visible` 轮廓见 rb.css:110 |

### 7. 内容与文案规则

- 卡片标题用**短标签**（≤20 字），来自 content-spec 的 screen 标题，如「复习计划草稿」（S06）。
- 状态文字只能取 content-spec 的逐字文案：「未保存」（S06）、「已保存 · 计划编号 plan_7Q2F9K」（S06）。
- 卡片内不得出现 content-spec §3 的违禁项：不出现「暂无数据」、不出现模型推理口吻、不以 emoji 充当图标。
- 空卡片不允许存在：无内容时改用 `.empty`（301）承载空状态文案。

### 8. 响应式行为

| 档位 | 行为 | 依据 |
| --- | --- | --- |
| base `<480` | 单列；`.card-row` 堆叠；卡片 `max-width` 由外层 `.wrap` 决定；内部间距不变 | rb.css:181、b-responsive-spec §2 |
| xs `≥480` | 同 base（本组件在 xs 无规则） | — |
| sm `≥768` | `.card-row--2` 变 `repeat(2,1fr)`（rb.css:182）；`.wrap` 内边距升为 36/24 | 182、166 |
| md `≥1024` | 无组件级规则 | — |
| lg `≥1200` | 容器达 880px（`--wrap-max`），卡片变宽、内边距不变 | rb.css:164 |
| xl `≥1440` | 只增左右留白 | b-responsive-spec §1 |
| 嵌套警告 | 卡片放进助手片段时，外层 `.wrap` 已给 18/24px 左右内边距；`.wrap .wrap`（169）会清零内层 padding，卡片**不要**再加左右 margin 补偿 | rb.css:169、S5 专条 |

### 9. 契约依据与禁止事项

- **依据**：README 硬要求 1/5；rb.css:181–190；b-responsive-spec §2（并排卡片 768 分界）、§4（`.card-row--2` 行）。
- **禁止**：给 `.card` 加 `:hover`/`:active`/`transition`（实现里没有）；把 `.card-row--2` 当 base 生效的类；
  用 `.card` 承载语义色状态；用内联 `style` 覆盖 `--card-*`；把卡片当评审外壳使用（S6 禁列，整份文件共 6 个评审专用类名，一律不引用）。

---

## Chat / Msg / Bubble `.chat`

### 1. 用途与边界

- **是**：本轮对话的**唯一纵向流**容器，以及两条消息（用户 / 助手）与气泡的形态契约。助手回答正文、内联过程区（`.steps`）、引用卡（`.cite`）都作为助手侧消息的内容出现。
- **不是**：不做左右分栏（b-responsive-spec §4 明确"始终单列，不做左右分栏"）、不做头像列、不做时间戳列、不做"正在输入"占位气泡（content-spec §3 禁止把推理过程当过程状态）。
- **边界**：`.bubble` 的限宽是**内容可读性**约束（长回答不铺满整屏），不是布局列；`.msg--user` 只负责右对齐与尾巴圆角，不改字号。
- **消息身份**：只有两种——用户（`.msg--user`）与助手（无修饰类）。content-spec 没有第三种说话人，不得引入「系统提示」气泡（系统级提示用 `.notice`）。

### 2. 结构（DOM 骨架）

```html
<div class="chat">
  <!-- 助手消息：无修饰类 -->
  <article class="msg">
    <span class="msg__who">校园课程助手</span>
    <div class="bubble">
      <p>根据《数据结构实验指导书（2026 秋）》，下次实验前需要完成：…〔资料 1〕</p>
      <figure class="cite"> … </figure>
    </div>
  </article>

  <!-- 用户消息：右对齐 + 左下…右下角贴角 -->
  <article class="msg msg--user">
    <span class="msg__who">你</span>
    <div class="bubble"><p>明天有什么课？顺便看看实验课要准备什么。</p></div>
  </article>
</div>
```

| 结构规则 | 说明 |
| --- | --- |
| `.chat` 只管 `flex-direction:column` + `gap`（234） | 顺序即 DOM 顺序，不排序、不虚拟滚动 |
| `.msg` 是 `flex-column`，`--msg-gap` 分隔 who 与 bubble（235） | `.msg__who` 在前、`.bubble` 在后，不可倒置 |
| `.msg--user` 只做 `align-items:flex-end`（237）+ 气泡换色贴角（238–239） | **文字仍左对齐**（content-spec 未要求右对齐文本；`text-align` 无 token 且实现未设） |
| `.bubble` 内可放 `.p`、`.cite`、`.steps`；`.cite` 自带 `margin-top` | 引用卡贴在回答正文下方，不脱离气泡 |
| 助手气泡内的正文**不要**再包一层 `.prose` | `.prose{max-width:68ch}`（170）在 720px 助手列内会二次限宽；正文 measure 已由 `.wrap--assistant` 提供 |

### 3. API 表

| class | 元素 | 必填 | 允许内容 | rb.css |
| --- | --- | --- | --- | --- |
| `.chat` | `div` / `section` | 是 | `.msg` 序列 | 234 |
| `.msg` | `article` | 是 | `.msg__who` + `.bubble` | 235 |
| `.msg__who` | `span` | 否 | 说话人名称纯文本 | 236 |
| `.msg--user` | 修饰（与 `.msg` 同用） | 否 | 用户消息专用 | 237–239 |
| `.bubble` | `div` | 是 | `p` / `.cite` / `.steps` / `.pill` | 240–241 |

属性约束：`role="log"`（见第 6 节）加在 `.chat` 上；`.bubble` **不设** `tabindex`，
其内部可聚焦元素（引用展开按钮）自行承担键盘可达性。

### 4. 状态矩阵

| 状态 | 是否存在 | rb.css | 视觉差别 | 文字/图标要求 |
| --- | --- | --- | --- | --- |
| 助手消息（默认 `.msg`） | ✅ | 240–241 | 白底 + 1px 暖灰边 + 14px 圆角 | 说话人由 `.msg__who` 提供 |
| 用户消息 `.msg--user` | ✅ | 237–239 | 右对齐；底色与边框同为主色浅调 `#E3EDEB`；**右下角圆角降为 6px** 形成尾巴 | 说话人由 `.msg__who` 提供 |
| 流式追加（正文增量） | ✅ 结构上 | 235–241 | **无专属 class、无动画**：增量只是往同一 `.bubble` 追加文本节点 | 只更新当前回答气泡（PRD CHAT-02）；不得为流式新增 `transition`/`animation`（rb.css 未定义，S7） |
| 悬停 `:hover` | ❌ 不存在 | — | — | 气泡不可点 |
| 按下 `:active` | ❌ 不存在 | — | — | — |
| 禁用 | ❌ 不适用 | — | — | — |
| 失败/取消态 | ❌ **气泡自身无此状态** | — | 本轮失败的口径在结果层表达（终态、`.notice`、`.steps` 失败项），不要给 `.bubble` 加红边 | PRD CHAT-02「工具失败时显示对应失败状态，不出现绿色完成标记」 |
| 长回答限宽 | ✅ | 242 | base `max-width:100%`；`≥xs` `max-width:88%` | 限宽是防长回答铺满整屏 |

> ⚠ 常见错误：给助手气泡补 `.bubble--pending`、`.bubble--error` 之类类名。rb.css 没有这些类，也不该有
> ——「结果待确认」是**整轮**的状态，用 `.pill--pending` + `.notice` 表达（见 §Draft）。

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| 对话纵向间距 | `--chat-gap` | `18px` | `.chat` 的 `gap`；消息与消息之间 | 234 |
| 消息内间距 | `--msg-gap` | `6px` | `.msg` 的 `gap`；who 与 bubble 之间 | 235 |
| 说话人字号 | `--msg-who-fs` | `13px` | | 236 |
| 说话人颜色 | `--msg-who-fg` | `#6B6259` | 经 L2 `--text-muted`（上游解析链，非消费方） | 236 |
| 助手气泡底色 | `--bubble-bg` | `#FFFFFF` | | 240 |
| 气泡文字色 | `--bubble-fg` | `#1C1917` | 经 L2 `--text-primary`（上游解析链，非消费方） | 240 |
| 气泡边框色 | `--bubble-border-color` | `#E7E5E4` | | 240 |
| 气泡边框宽 | `--bubble-border-w` | `1px` | | 240 |
| 气泡圆角 | `--bubble-radius` | `14px` | 助手气泡四角同值 | 240 |
| 气泡上下内边距 | `--bubble-pad-y` | `12px` | | 241 |
| 气泡左右内边距 | `--bubble-pad-x` | `18px` | | 241 |
| 用户气泡底色 | `--bubble-user-bg` | `#E3EDEB` | 经 L2 `--accent-tint`（上游解析链，非消费方） | 238 |
| 用户气泡边框色 | `--bubble-user-border-color` | `#E3EDEB` | 与底色同值 = 视觉无边框 | 238 |
| 用户气泡尾巴圆角 | `--bubble-user-tail-radius` | `6px` | 只作用于 `border-bottom-right-radius` | 239 |
| 气泡限宽（base） | `--bubble-max-w` | `100%` | base/xs 分界前的取值 | 241 |
| 气泡限宽（≥xs） | `--bubble-max-w-xs` | `88%` | 「≥xs 限宽，避免长回答铺满整屏」 | 242 |

**token 未覆盖的裸值（诚实缺口）**：`.bubble` 的 `position`/`text-align` 未设置，故无对应 token；
`.msg` 的 `max-width:100%`（235）与 `--bubble-max-w` 语义重叠但无独立 token。
`.chat` 放进 `.composer` 外层容器时的左右内边距由 `.wrap` 提供（`--wrap-pad-x`，非本组）。

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 容器语义 | `.chat` 用 `role="log"` + `aria-live="polite"`（流式追加可被朗读），或用 `aria-live="off"` + 终态时一次性播报——**二选一并在实现里写死**；推荐后者以避免逐 token 朗读 |
| 消息语义 | 每条 `.msg` 用 `article`；说话人用 `.msg__who` 文本而非仅靠左右位置区分（**状态不能只靠颜色/位置**：`.msg--user` 必须同时有可见说话人文字） |
| 可访问名 | `.msg` 不需要 `aria-label`；若省略 `.msg__who`，必须用 `.sr-only`（rb.css:113）保留说话人文本 |
| 键盘 | `.chat` 自身不可聚焦；`.bubble` 内按钮（「展开片段」）用原生 `button`，`aria-expanded` 反映展开态 |
| 对比度 | 助手气泡 `#1C1917` on `#FFFFFF`；用户气泡文字 `#1C1917` on `#E3EDEB`，均 > 4.5:1 |
| 触控 | 气泡内按钮 ≥44px（rb.css:120）；引用卡展开控件若为小图标，须 ≥32×32 且带可访问名（content-spec §1） |
| Reflow | 320px 下 `.bubble` `max-width:100%`，长 URL/文件名靠 `overflow-wrap:break-word`（沿 `.cite`/`.kv__v` 的做法），页面级横向溢出必须为 0 |
| 动效 | 气泡与消息**无**任何 `transition`/`animation`；`prefers-reduced-motion` 降级（rb.css:111）在本组件上无内容可降 |

### 7. 内容与文案规则

- 用户消息逐字取自 content-spec，如 S03：「明天有什么课？顺便看看实验课要准备什么。」
- 助手回答逐字取自 S04：「根据《数据结构实验指导书（2026 秋）》，下次实验前需要完成：1）预习实验二排序算法；2）提交预习报告，不少于 500 字。〔资料 1〕」
- 引用标记写作 `〔资料 1〕`（全角方括号 + 空格 + 序号），**不得**改写成 Markdown 链接或脚注样式。
- 说话人文字：助手侧用产品名，用户侧用「你」；两者都是纯文本，不是按钮。
- 违禁：不得出现「正在思考」「AI 推理中」「暂无数据」；不得用 emoji 充当图标（content-spec §3）。

### 8. 响应式行为

| 档位 | 行为 | 依据 |
| --- | --- | --- |
| base `<480` | 单列；气泡 `max-width:100%`；`.chat` 间距恒 18px | rb.css:234、241 |
| xs `≥480` | 气泡 `max-width:88%`（rb.css:242）；`.msg--user` 仍靠右 | 242、b-responsive-spec §4 |
| sm `≥768` | 无组件级规则；`.wrap--assistant` 起 720px 列宽 | rb.css:165 |
| md `≥1024` | 无组件级规则 | — |
| lg `≥1200` | 助手列达 720px 上限，不再变宽 | b-responsive-spec §1、§2 |
| xl `≥1440` | 仅增留白 | b-responsive-spec §1 |
| 嵌套 | 助手片段自带 `.wrap`：`.wrap .wrap`（169）清零内层左右 padding，`.chat` 不得再加左右 margin | rb.css:169 |

### 9. 契约依据与禁止事项

- **依据**：rb.css:234–242；b-responsive-spec §4「`.chat` 对话：始终单列，不做左右分栏」；content-spec §2 S03/S04。
- **禁止**：给 `.msg`/`.bubble` 加 `:hover`/`:active`/`transition`/`animation`；新增 `--msg-*`/`--bubble-*` 之外的 L3；
  用左右位置代替说话人文字（状态不能只靠颜色/位置）；在助手气泡内再套 `.prose`（二次限宽 68ch）；
  把过程区做成右侧面板（b-responsive-spec §4 要求内联）。

---

## Composer `.composer`

### 1. 用途与边界

- **是**：**底部吸底**的输入区外壳：一行 = 可见 label 的 `<textarea>` + 发送按钮 + 计数。
- **不是**：**不承载任何路由或深链语义**（U3）。Composer 不得读写 URL、不得产生可分享链接、不得让步数进入 history，
  不得出现「复制链接」「分享这轮对话」类入口——SRS DEC-01 / PRD CHAT-03 / HLD-D03·D11 明确：对话只驻留当前浏览器标签页内存，
  刷新/关闭不恢复，服务端不承诺跨设备恢复，服务端历史是 P1。
- **不是**：不是对话历史入口（刷新后无历史可回）、不是文件上传口（content-spec §3 未承诺 OCR/附件）、不是设置面板。
- **边界**：`position:sticky`（266）意味着它**参与文档流并占位**，不是 `fixed` 浮层；因此不需要额外的等高占位元素，
  但页面底部必须为 `.tabbar` 预留（`body` 的 `padding-bottom`，rb.css:102–104）。

### 2. 结构（DOM 骨架）

```html
<form class="composer" data-no-route>
  <!-- 可见 label（content-spec S02 要求），不得用 placeholder 当唯一标签 -->
  <label class="field__label" for="ask">你的问题</label>
  <div class="composer__row">
    <textarea id="ask" class="textarea" rows="3"
              maxlength="2000" aria-describedby="ask-hint"></textarea>
    <button type="submit" class="btn btn--primary" disabled>发送</button>
  </div>
  <div class="row">
    <span class="field__hint" id="ask-hint">最多 2000 字</span>
    <span class="composer__count" aria-hidden="true">0 / 2000</span>
  </div>
</form>
```

| 结构规则 | 说明 |
| --- | --- |
| `.composer` 是吸底容器，**无左右内边距**（266–270：只有 `padding:12px 0`） | 左右留白由外层 `.wrap` 提供；组件不要自我补偿（S5） |
| `.composer__row` 是 `flex; align-items:flex-end; gap:12px`（272） | 按钮贴底与多行 textarea 底边对齐；`.btn` 自带 `min-height:44px` |
| `.composer__count` 用 `margin-left:auto` 靠右（273） | 计数器是**视觉冗余**：字符上限信息由 `aria-describedby` 的辅助文字承载，计数本身不播报（`aria-hidden="true"`） |
| 页脚辅助文字用 `.field__hint`（317） | 「最多 2000 字」是内容规格的辅助文案位，不是 `composer` 组 token |
| 空白不可提交 | content-spec S02：空白时按钮**展示禁用态**（`.btn[disabled]`，rb.css:205） |
| 示例入口 | 点击**只填入输入框，不自动提交**（content-spec S02）——它们不是 `.composer` 的一部分，用 `a.chip`/`.chip` 承载 |

### 3. API 表

| class | 元素 | 必填 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| `.composer` | `form` | 是 | 吸底外壳；`bottom` 由 token 控制 | 266–270 |
| `.composer__row` | `div` | 是 | textarea + 主按钮 | 272 |
| `.composer__count` | `span` | 否 | 计数/上限提示，靠右 | 273 |
| `.textarea` | `textarea` | 是 | 复用表单族（319–324），`min-height:120px` | 324 |
| `.btn--primary` | `button[type=submit]` | 是 | 「发送」；空白时 `disabled` | 200、205 |

属性约束：`.composer` 必须是 `form`（提交走 Enter/按钮，不绑全局快捷键）；
`maxlength="2000"`；`aria-describedby` **必须**指向上限说明节点 id。

### 4. 状态矩阵

| 状态 | 是否存在 | rb.css | 视觉差别 | 文字/图标要求 |
| --- | --- | --- | --- | --- |
| 默认（有输入） | ✅ | 266–273 | 页面底色 `#FAF8F5` + 顶部 1px 分隔线 | 「发送」按钮可点 |
| 空白（禁用） | ✅ 按钮侧 | 205 | `.btn[disabled]{opacity:.5;cursor:not-allowed}` | 按钮文字仍为「发送」；**不禁用** textarea |
| 聚焦（textarea） | ✅ | 110 | `:focus-visible{outline:3px solid #0F4A42;outline-offset:2px}` | label 常显 |
| 底部吸附 | ✅ | 267、271 | base/xs/sm：`bottom:56px`（= `--composer-bottom`，叠 `env(safe-area-inset-bottom)`）；`≥768`：`bottom:0` | — |
| 悬停 `:hover` | ❌ **`.composer` 无 hover** | — | 容器不可交互 | 按钮的 hover 归 `.btn`（201） |
| 按下 `:active` | ❌ 不存在 | — | — | — |
| 发送中（流式） | ⚠ 口径 | — | 本层**无**专属类；进行中由 `.steps` 与状态行表达，`.composer` 不变形 | 停止操作归过程区（content-spec S03） |

> ⚠ 常见错误：给 `.composer` 补 `:hover`/`:focus-within`，或补一个 `.composer--busy`。
> rb.css 里都没有；发送中不改变输入区外观。

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| 输入区底色 | `--composer-bg` | `#FAF8F5` | 经 L2 `--bg-page`（上游解析链，非消费方）：**与卡片白拉开层次** | 268 |
| 上边框色 | `--composer-border-color` | `#E7E5E4` | | 269 |
| 上边框宽 | `--composer-border-w` | `1px` | | 269 |
| 上下内边距 | `--composer-pad-y` | `12px` | 简写 `padding:12px 0`，**左右为 0** | 268 |
| 行内间距 | `--composer-gap` | `12px` | `.composer__row` 的 `gap`（textarea ↔ 发送） | 272 |
| 计数字号 | `--composer-count-fs` | `13px` | | 273 |
| 计数颜色 | `--composer-count-fg` | `#6B6259` | 经 L2 `--text-muted`（上游解析链，非消费方） | 273 |
| 层级 | `--composer-z` | `20` | 低于 `.appbar`/`.tabbar` 的 40（122、150） | 269 |
| 吸底偏移 | `--composer-bottom` | `56px` | 「窄屏吸附在标签栏之上；≥sm 归零」（rb.css:271 写 `bottom:0`） | 267 |

**token 未覆盖的裸值（诚实缺口）**：`position:sticky`（266）无 token；
`align-items:flex-end`（272）无 token；`env(safe-area-inset-bottom,0px)` 是运行时常量，无法 token 化（rb.css:267）；
`margin-left:auto`（273，等价于 `.spacer`，391）无 token。

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 标签 | `<label for>` **必须可见**（content-spec §1、S02「textarea 可见 label『你的问题』」）；禁止 placeholder 当唯一标签 |
| 上限说明 | `aria-describedby` 指向「最多 2000 字」节点；`maxlength="2000"` 与文案一致 |
| 计数 | `.composer__count` 加 `aria-hidden="true"`，避免与 `aria-describedby` 重复播报；若要求实时播报，改用 `aria-live="polite"` 且**去掉** `aria-hidden` |
| 禁用 | 空白不可提交时用 `disabled`（不用 `aria-disabled` 假装）——`.btn[disabled]` 有真实样式（205） |
| 键盘 | Enter 在 textarea 内换行、按钮提交（表单原生行为）；**不得**把「发送」绑到全局快捷键而抢走输入 |
| 焦点不被遮挡 | 吸底 `.composer` 不得盖住已聚焦元素：`body` 已为 `.tabbar` 预留（102–104），sm 起归零（104） |
| 触控 | 发送按钮 `min-height:44px`（rb.css:120） |
| 对比度 | 计数 `#6B6259` on `#FAF8F5`；辅助文字同为 `--text-muted`（上游 L2，rb.css:317） |
| 无路由 | **不得**有 `history.pushState`、`location.hash`、`<a href>` 跳到本轮对话的入口；输入内容不进 URL、不进 `sessionStorage` 之外的持久层（U3） |

### 7. 内容与文案规则

- label 逐字：「你的问题」；辅助文字逐字：「最多 2000 字」；主按钮逐字：「发送」；空态展示「发送」的**禁用态**（content-spec S02）。
- 示例入口逐字：「查今天的课」「根据资料回答问题」「制定学习计划」——**点击只填入输入框，不自动提交**（content-spec S02）。
- 边界提示条不属于 `.composer`：「对话只保存在当前浏览器标签页，刷新或关闭后不会恢复；已保存的计划不受影响。」
  + 次级操作「清空对话」（content-spec S02），用 `.notice` 承载。
- 违禁：不得出现「输入消息…」之外的营销式占位话术；不得用 placeholder 代替 label；不得出现「分享」「复制链接」类文案（U3）。

### 8. 响应式行为

| 档位 | 行为 | 依据 |
| --- | --- | --- |
| base `<480` | 吸底于 `bottom:56px + safe-area-inset-bottom`；单行 flex，textarea 与按钮同排；宽 100%（外层 `.wrap` 决定左右留白） | rb.css:267、b-responsive-spec §4 |
| xs `≥480` | 同 base（本组件在 xs 无规则） | — |
| sm `≥768` | `bottom:0`（rb.css:271）；`body` 的标签栏占位也归零（104） | 271、104 |
| md `≥1024` | 无组件级规则 | — |
| lg `≥1200` | 助手列 720px 上限；输入区随列宽 | rb.css:165 |
| xl `≥1440` | 仅增留白 | b-responsive-spec §1 |
| 键盘弹出（移动端） | 视觉视口收缩时 `.composer` 仍在视口底部可操作 | b-responsive-spec §4「键盘弹出时仍可用」 |
| 嵌套 | 外层 `.wrap` 给 18/24px 左右留白；`.wrap .wrap`（169）清零内层 padding 后，**输入框仍撑满 720px 列**，不需要自行补 padding | rb.css:169 |

### 9. 契约依据与禁止事项

- **依据**：rb.css:266–273；b-responsive-spec §2/§4/§7；content-spec S02。
- **U3 专条（助手对话不进 URL）**：Composer 是**纯内存输入**。规格层面禁止：
  ① 任何 `href`/`pushState`/`replaceState`/`hash` 写入；
  ② 把本轮对话序列化进 URL 或分享链接；
  ③ 把「恢复对话」做成 Composer 能力（刷新后无历史可恢复，DEC-01/CHAT-03）。
  实现者如需「深链」，只能指向**已保存计划**（`/me/plans/{id}`，HLD-D11 之外的持久对象），不得指向对话。
- **禁止**：给 `.composer` 加 `:hover`/`:active`/`transition`；给组件加左右 padding 抵消 `.wrap .wrap`；
  用 `.btn` 之外的裸 `button`（会丢 44px 触控高度）；把发送按钮做成浮动圆形按钮（实现与 token 均无此形态）。

---

## Citation `.cite`

### 1. 用途与边界

- **是**：**已验证引用**的展开卡：文档名 + 位置 + 片段原文；以及**未验证引用标记** `.cite-mark--pending` 的内联形态。
- **不是**：不是链接卡（不跳外链）、不是文件预览器（`GET /admin/documents/{id}/text` 是管理端能力）、不是「相关推荐」。
- **U1 专条（本组件存在的理由）**：**未校验引用标记必须与已验证引用视觉可区分**——这是 SRS FR-QA-002 与 PRD QA-01 的
  硬要求（「模型输出中不存在于清单的引用标记应被过滤并标注无法验证」），**不是风格选择**。两者的区分手段是**结构差异**：
  - 已验证 `.cite`：左侧 **4px 实心主色条**（`--cite-accent-w` = `4px`，颜色 `--cite-accent-color` = `#14665B`）；
  - 未验证 `.cite-mark--pending`：**琥珀虚下划线**（`--cite-mark-pending-underline` = `#B45309`，`dashed`）+ 文字色 `--cite-mark-pending-color` = `#8A4107`。
  即使把页面去色成灰度，`4px 实心竖条` 与 `1px 虚下划线` 仍可分——这就是"可区分"的验收口径。
- **边界**：引用**只来自本次真实检索**（PRD QA-01）；页码抽不到时**只显示文件名与位置**（`page_number` 在
  `sse_events` schema 里是可选字段，`location_label` 必填），不得编造页码。
- **第三个状态**：引用失效 `.cite--invalid`——对应 HTTP 410，文案「这条引用已失效（资料已被删除），依据可能已变化。」

### 2. 结构（DOM 骨架）

```html
<!-- ① 已验证引用：4px 实心主色左条（默认展开态，折叠态见下） -->
<figure class="cite">
  <div class="cite__head">
    <span class="cite__name">资料 1 · 数据结构实验指导书（2026 秋）.pdf</span>
    <span class="cite__loc">第 12 页 · 展开片段</span>
  </div>
  <figcaption class="cite__body">
    实验前须完成预习并提交预习报告，报告不少于 500 字……
  </figcaption>
</figure>

<!-- ② 无页码样例：page_number 缺失时只给文件名 + location_label -->
<figure class="cite">
  <div class="cite__head">
    <span class="cite__name">资料 2 · 实验二指导书.pdf</span>
    <span class="cite__loc">第 3 节「预习要求」</span><!-- 无「第 N 页」 -->
  </div>
  <figcaption class="cite__body">…</figcaption>
</figure>

<!-- ③ 引用失效（HTTP 410） -->
<figure class="cite cite--invalid">
  <div class="cite__head">
    <span class="cite__name">资料 1 · 数据结构实验指导书（2026 秋）.pdf</span>
    <span class="cite__loc">已失效</span>
  </div>
  <figcaption class="cite__body">这条引用已失效（资料已被删除），依据可能已变化。</figcaption>
</figure>

<!-- ④ 未验证标记：内联在正文里，1px 琥珀虚下划线，不是卡片 -->
<p>下次实验前需要完成预习〔<span class="cite-mark--pending">资料 1</span>〕。</p>
```

| 结构规则 | 说明 |
| --- | --- |
| `.cite` 的 `border-left` 与其余三边**必须分开写**（276–277） | `border:1px solid var(--cite-border-color)` + `border-left:4px solid var(--cite-accent-color)`；合成 `border` 简写会吃掉左条 |
| `.cite__head` 是 `flex; flex-wrap:wrap`，`gap:6px 12px`（279–280） | 文档名与位置在窄屏自动折行；≥sm 同行（b-responsive-spec §4） |
| `.cite__body` 有 `border-top:1px dashed var(--cite-border-color)`（283） | 虚线与卡片左实心条形态不同，**不会**被误读为"未验证" |
| `.cite-mark--pending` 只能用于**正文内联文本**（288） | 它是内联标记，不得当卡片用、不得包 `<figure>` |
| `.cite--invalid` 覆盖左条颜色与底色（285–286） | 失效引用**仍是已验证引用**（它来自清单），只是来源已删；与 `.cite-mark--pending` 是**三态中的两态**，不可合并 |
| 卡片内的 `.cite` | 由 `.cite` 自带 `margin-top:12px` 与上文正文分层，父容器不加 margin |

### 3. API 表

| class | 元素 | 必填 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| `.cite` | `figure` | 是 | 引用卡；`margin-top` 由 token 控制 | 276–278 |
| `.cite__head` | `div` | 是 | 名称 + 位置 | 279–280 |
| `.cite__name` | `span` | 是 | 文档名 + 引用序号 | 281 |
| `.cite__loc` | `span` | 是（可缺页码，不可缺位置） | 位置或页码范围 | 282 |
| `.cite__body` | `figcaption` | 否（折叠态省略） | 片段原文 | 283–284 |
| `.cite--invalid` | 修饰 | 否 | HTTP 410 失效态 | 285–286 |
| `.cite-mark--pending` | `span`（内联） | 否 | 未验证标记；与已验证引用必须可区分 | 288 |

属性约束：引用序号 `资料 N` 来自 `citations[]` 的顺序（`done` 事件的 `citations`），**不得**由模型文本决定；
`location_label` 与 `file_name` 必须来自 `Reference` 对象；`page_number` 缺失时 `__loc` 不含页码字样。

### 4. 状态矩阵

| 状态 | class | 是否存在 | rb.css | 视觉差别（结构化，非配色微调） | 文字/图标要求 |
| --- | --- | --- | --- | --- | --- |
| 已验证 · 展开 | `.cite` + `.cite__body` | ✅ | 276–284 | 白底、1px 暖灰边、**左侧 4px 实心主色条**、body 上方 1px 虚线分隔 | 名称 + 位置 + 片段原文 |
| 已验证 · 折叠 | `.cite`（省略 `__body`） | ✅ | 276–282 | 同上去掉 body 与虚线 | 必须出现「展开片段」文字入口（S04），且控件带 `aria-expanded` |
| 未验证标记 | `.cite-mark--pending` | ✅ | 288 | **1px 琥珀虚下划线** + 琥珀文字；**无左条、无卡片边界** | 文字必须是 `资料 N` 形式的标记文本；hover 不存在 |
| 引用失效 | `.cite--invalid` | ✅ | 285–286 | 左条与 `__name` 转危险色（`#9F1239`/`#7B0E2C`），底色转 `#FBE7EC` | 必须逐字给「这条引用已失效（资料已被删除），依据可能已变化。」 |
| 无页码 | `.cite`（`__loc` 无「第 N 页」） | ✅ | 282 | 与展开态同形，只是位置文本不同 | 只显示文件名与位置（PRD QA-01） |
| 悬停 `:hover` | ❌ **不存在** | — | — | rb.css 没有 `.cite:hover`、没有 `.cite-mark--pending:hover` | 若需提示"点击展开"，用可见文字按钮，不加 hover 样式 |
| 按下 `:active` | ❌ 不存在 | — | — | — | — |
| 聚焦 | 仅内部按钮 | 110 | `:focus-visible` 轮廓 | 「展开片段」用原生 `button` |
| 禁用 | ❌ 不适用 | — | — | — | — |

> ⚠ 本目录最容易犯的错：给 `.cite` 补 `:hover` 高亮、给 `.cite__loc` 补「可点击」样式、把 `.cite--invalid`
> 与 `.cite-mark--pending` 合并成一个"警告态"。三者（已验证 / 未验证 / 已失效）是三个**不同契约对象**。

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| 卡片底色 | `--cite-bg` | `#FFFFFF` | | 276 |
| 三边边框色 | `--cite-border-color` | `#E7E5E4` | 同时用于 `__body` 的上虚线 | 276、283 |
| **三边边框宽** | `--cite-border-w` | `1px` | 与左条宽度分开写；**收口时补齐**（原为诚实缺口，Lead 已补入 tokens.json） | 276 |
| **左条宽度** | `--cite-accent-w` | `4px` | 「左侧主色条——已验证引用的视觉标记」 | 277 |
| **左条颜色** | `--cite-accent-color` | `#14665B` | 经 L2 `--accent`（上游解析链，非消费方）；U1 的核心可区分特征 | 277 |
| 圆角 | `--cite-radius` | `10px` | | 277 |
| 上下内边距 | `--cite-pad-y` | `12px` | | 278 |
| 左右内边距 | `--cite-pad-x` | `18px` | | 278 |
| 上外边距 | `--cite-margin-t` | `12px` | 与上文正文分层 | 278 |
| head 行间距 | `--cite-head-gap` | `6px` | `gap:6px 12px` 的第一值（rb.css:279） | 279 |
| head 列间距 | `--cite-head-gap-x` | `12px` | `gap:6px 12px` 的第二值；**收口时补齐**——行/列间距不同，合并成一个 token 会写错列间距 | 279 |
| head 字号 | `--cite-head-fs` | `15px` | | 280 |
| 位置字号 | `--cite-loc-fs` | `13px` | | 282 |
| 位置颜色 | `--cite-loc-fg` | `#6B6259` | 经 L2 `--text-muted`（上游解析链，非消费方） | 282 |
| body 字号 | `--cite-body-fs` | `15px` | | 284 |
| body 颜色 | `--cite-body-fg` | `#5B544E` | 经 L2 `--text-secondary`（上游解析链，非消费方） | 284 |
| body 上外边距 | `--cite-body-margin-t` | `6px` | | 283 |
| body 上内边距 | `--cite-body-pad-t` | `6px` | 与上虚线配合形成分隔 | 283 |
| 失效左条色 | `--cite-invalid-border-color` | `#9F1239` | 经 L2 `--danger-border`（上游解析链，非消费方） | 285 |
| 失效底色 | `--cite-invalid-bg` | `#FBE7EC` | 经 L2 `--state-danger-tint`（上游解析链，非消费方） | 285 |
| 失效标题色 | `--cite-invalid-fg` | `#7B0E2C` | 经 L2 `--state-danger`（上游解析链，非消费方） | 286 |
| **未验证文字色** | `--cite-mark-pending-color` | `#8A4107` | 经 L2 `--pending`（上游解析链，非消费方） | 288 |
| **未验证下划线色** | `--cite-mark-pending-underline` | `#B45309` | 经 L2 `--pending-border`（上游解析链，非消费方）；`dashed` 线型本身**无 token** | 288 |

**token 未覆盖的裸值（诚实缺口）**：三边边框宽 `1px`（276）与 `__body` 上虚线宽 `1px`（283）无独立 L3；
`border-bottom-style:dashed`（288）与 `border-top-style:dashed`（283）的**线型**无 token（只有颜色有）；
`gap:6px 12px` 的列间距 `12px`（279）无独立 token（`--cite-head-gap` 只覆盖行间距）。

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 语义元素 | 引用卡用 `figure` + `figcaption`（片段原文是卡片的说明）；内联标记用 `span` |
| 可访问名 | `.cite__name` 提供引用名；卡片不需要额外 `aria-label` |
| **状态可访问** | `.cite--invalid` 必须在**文本**里说明失效（「这条引用已失效（资料已被删除），依据可能已变化。」），不得只靠危险色；`.cite-mark--pending` 必须带 `title` 或 `aria-label`（如「未验证引用：资料 1」）以补足虚线这一纯视觉线索（**状态不能只靠颜色**，S2） |
| 未验证标记的语义 | 建议 `aria-label="未验证引用"` 或可见文字「（未验证）」，二者至少一个；**只靠虚下划线不合格** |
| 折叠/展开 | 「展开片段」用原生 `button`，`aria-expanded="false|true"`，`aria-controls` 指向 `.cite__body` 的 id；折叠时 `__body` 用 `hidden` |
| 键盘 | 展开按钮可 Tab 聚焦、Enter/Space 触发；引用卡自身不设 `tabindex` |
| 对比度 | `#5B544E` on `#FFFFFF`、`#6B6259` on `#FFFFFF`、失效态 `#7B0E2C` on `#FBE7EC`、未验证 `#8A4107` on `#FFFFFF`/`#E3EDEB` 均需 ≥4.5:1（生成器 `contrast` 段已核） |
| 触控 | 展开控件 ≥44×44px；若为小图标按钮，≥32×32 且带可访问名（content-spec §1） |
| 长文本 | 文件名可换行：`.cite__name` 依赖 `.cite__head` 的 `flex-wrap:wrap`；片段原文靠 `.cite__body` 的自然换行（`overflow-wrap` 未设，见缺口） |
| 动效 | 无 `transition`（rb.css 未给 `.cite` 定义），展开态靠 `hidden`/DOM 切换 |

**诚实缺口**：`.cite__name`/`.cite__body` **未设** `overflow-wrap`（rb.css:281、283–284 只有颜色字号）。
超长无空格文件名（如 `aaaa…aaa.pdf`）在窄屏可能撑宽卡片；320px 实拍前需补 `overflow-wrap:break-word`
（content-spec §1 允许非表格长文本容器用 `anywhere`，但此处属卡片内长串，建议 `break-word`）。

### 7. 内容与文案规则

- 折叠态逐字：`资料 1` · `数据结构实验指导书（2026 秋）.pdf` · `第 12 页` · 「展开片段」（content-spec S04）。
- 无页码样例：只给文件名与位置，例如 `资料 2` · `实验二指导书.pdf` · `第 3 节「预习要求」`——**不得**出现「第 ? 页」或占位页码。
- 展开片段逐字示例：「实验前须完成预习并提交预习报告，报告不少于 500 字……」
- 失效态逐字：「这条引用已失效（资料已被删除），依据可能已变化。」（对应 HTTP 410，content-spec S04）
- 正文中的未验证标记写作 `〔资料 1〕`（content-spec S03），与已验证标记**同文本、异样式**——这样"被过滤并标注无法验证"在文本层仍可读。
- 内容性质标签：「课程规定」「一般学习建议」必须视觉区分、不得混排（content-spec S04）——用 `.pill--evidence` / `.pill--advice`（rb.css:219–220）承载，**不要**给 `.cite` 加第三种状态色。
- 违禁：不得出现「引用来源」「参考文献」式学术排版话术；不得出现外链图标（本组件不是链接卡）。

### 8. 响应式行为

| 档位 | 行为 | 依据 |
| --- | --- | --- |
| base `<480` | 单列；`.cite__head` 字段换行（`flex-wrap:wrap`），文档名与位置上下排 | rb.css:279、b-responsive-spec §4 |
| xs `≥480` | 同 base | — |
| sm `≥768` | `.cite__head` 字段同行（可用宽度足够）；其余不变 | b-responsive-spec §4 |
| md `≥1024` | 无组件级规则 | — |
| lg `≥1200` | 引用卡宽度随助手列 720px 封顶 | rb.css:165 |
| xl `≥1440` | 仅增留白 | b-responsive-spec §1 |
| 失效态 | 任何档位都保持左条 + 底色 + 文字三重表达，不因窄屏省略文字 | S2 |
| 嵌套 | `.cite` 在 `.bubble` 内时，其 `--cite-pad-x:18px` 与气泡的 `--bubble-pad-x:18px` 叠加 → 窄屏（320px）有效文字宽 = 320 − 2×18（wrap） − 2×18（气泡） − 2×18（引用） − 4（左条） ≈ 208px。**这是既定取舍**，若实测拥挤，改动只能落在 token（`--cite-pad-x`）而非加类 | rb.css:169、241、278 |

### 9. 契约依据与禁止事项

- **依据（U1）**：SRS FR-QA-002（252–254 行：「模型输出中不存在于清单的引用标记应被过滤并标注无法验证」）、
  PRD QA-01（251–254 行）、SRS IF-007（462–472 行：`done.citations[]`、`Reference.file_name/location_label/page_number`）、
  content-spec S03/S04。**已验证 = 4px 实心主色左条；未验证 = 琥珀虚下划线；已失效 = 危险色左条 + 危险底色。三态不可合并。**
- **禁止**：给 `.cite` 或 `.cite-mark--pending` 加 `:hover`/`:active`/`transition`（实现里没有）；
  把 `.cite-mark--pending` 做成卡片；给未验证标记加左条（会与已验证不可区分）；
  用颜色作为唯一区分手段（必须叠加线型/结构差异 + 文字/图标）；自造 `--cite-*` token；
  在 `.cite` 上加 `overflow-wrap:anywhere` 之外的花招（缺口见第 6 节，改动需同步进 rb.css 与 tokens.json）。

---

## Draft `.draft`

### 1. 用途与边界

- **是**：助手生成的**计划草稿便签纸**：标题 + 状态 + 键值明细 + 正文条目 + 动作区。
- **不是**：不是计划详情页（那是 `/me/plans/{id}`）、不是表单（字段不可编辑，编辑走「继续修改」）、不是 toast。
- **U2 专条（本组件存在的理由）**：**草稿默认「未保存」**，保存后才转「已保存」；**写入结果未知时必须显示「待确认」而不是失败**
  （SRS FR-CHAT-005：「网络断开时，客户端应将显示状态置为『结果待确认』，不得直接认定执行失败或未写入」；
  后端详细设计 §12.2：「当数据库不可用且不能核实操作时返回 503……客户端仍显示待确认，不将其转换为 failed」）。
- **三态与视觉绑定**（全部有真实实现）：

| 态 | class | 视觉 | 逐字文案 |
| --- | --- | --- | --- |
| 未保存（默认） | `.draft` | **2px 虚线琥珀边**（`--draft-border-w` + `--draft-border-color`） | 标题「复习计划草稿」+ 状态「未保存」 |
| 已保存 | `.draft` + `.draft--saved` | `border-style:solid` + `border-color:var(--draft-saved-border-color)` | 「已保存 · 计划编号 plan_7Q2F9K」+ 主按钮「打开计划」 |
| 待确认 | `.draft`（**保持未保存外观**） | 不做任何"失败"着色；用 `.pill--pending` + `.notice` 说明 | 「正在确认是否保存…」+「写入结果尚未确认，请勿重复创建；可稍后查询状态。」+ 次级按钮「查询写入状态」 |

> 「待确认」**不是** `.draft--failed`（实现里没有这个类），**也不是** `.draft--saved`。
> 它是「未保存外观 + 明确文字 + 不产生新写入」的组合。

### 2. 结构（DOM 骨架）

```html
<!-- ① 未保存（默认） -->
<section class="draft">
  <header class="draft__head">
    <h3>复习计划草稿</h3>
    <span class="pill pill--pending"><svg aria-hidden="true"><!-- 琥珀图标 --></svg>未保存</span>
  </header>
  <dl class="draft__kv">
    <dt>标题</dt><dd>实验二排序算法预习计划</dd>
    <dt>目标</dt><dd>实验前完成排序算法预习并提交预习报告</dd>
    <dt>覆盖日期</dt><dd>2026-10-22 → 2026-10-24</dd>
    <dt>依据</dt><dd>本人课表 + 课程资料〔资料 1〕</dd>
  </dl>
  <div class="card__body"><ol><li>…</li><li>…</li><li>…</li></ol></div>
  <footer class="card__foot">
    <button class="btn btn--primary">保存为我的计划</button>
    <button class="btn btn--ghost">继续修改</button>
  </footer>
</section>

<!-- ② 已保存：同一结构 + 一个修饰类 -->
<section class="draft draft--saved">
  <header class="draft__head">
    <h3>复习计划草稿</h3>
    <span class="pill pill--ok"><svg aria-hidden="true"><!-- 对勾 --></svg>已保存 · 计划编号 plan_7Q2F9K</span>
  </header>
  <dl class="draft__kv">…</dl>
  <footer class="card__foot"><button class="btn btn--primary">打开计划</button></footer>
</section>

<!-- ③ 待确认：外观仍是未保存；状态与说明用文字承载 -->
<section class="draft" aria-busy="true">
  <header class="draft__head">
    <h3>复习计划草稿</h3>
    <span class="pill pill--pending"><svg aria-hidden="true"><!-- 琥珀图标 --></svg>未保存</span>
  </header>
  <div class="notice notice--warn" role="status">
    <p><strong>正在确认是否保存…</strong></p>
    <p>写入结果尚未确认，请勿重复创建；可稍后查询状态。</p>
    <button class="btn btn--sm">查询写入状态</button>
  </div>
  <dl class="draft__kv">…</dl>
</section>
```

| 结构规则 | 说明 |
| --- | --- |
| `.draft` 边框是 **2px dashed**（291） | 与 `.card` 的 1px solid 形成"便签纸"身份；`--draft-border-w` = `2px` |
| `.draft--saved` **只改线型与颜色**（293） | `border-style:solid; border-color:var(--draft-saved-border-color)`；宽度仍 2px（无覆盖） |
| `.draft__head` 是 `flex; flex-wrap:wrap; gap:12px; margin-bottom:12px`（294–295） | 标题与状态胶囊同行，窄屏折行 |
| `.draft__kv` 是 `grid-template-columns:auto 1fr`（296） | 键列按内容自适应（`--draft-kv-key-col: auto`），与 `.kv` 的固定 `8em` **不同**——草稿的键是中文短标签 |
| `.draft__kv dt` 是 `white-space:nowrap`（297） | 键不折行；值列 `overflow-wrap:break-word`（298） |
| 动作区可复用 `.card__foot`（190） | 草稿内容区/动作区的排布与卡片一致，但 **`.draft` 自身不嵌套 `.card`**（会双层边框） |
| 「待确认」用 `.notice--warn` + `role="status"` | 不改变 `.draft` 外观，避免把"未知"渲染成"失败" |

### 3. API 表

| class | 元素 | 必填 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| `.draft` | `section` | 是 | 未保存便签；2px 虚线琥珀边 | 291–292 |
| `.draft--saved` | 修饰 | 否 | 已保存：实线 + 常规边框色 | 293 |
| `.draft__head` | `header` | 是 | 标题 + 状态胶囊 | 294–295 |
| `.draft__kv` | `dl` | 是 | 草稿字段键值（标题/目标/覆盖日期/依据/正文条目数） | 296 |
| `.draft__kv > dt` | `dt` | 是 | 字段名，不折行 | 297 |
| `.draft__kv > dd` | `dd` | 是 | 字段值，可断行 | 298 |
| `.card__foot` | `footer` | 否 | 动作区（复用卡片族） | 190 |

属性约束：`.draft__kv` **必须**是 `dl`（语义为键值对），不得用 `div` 模拟；
`dt` 与 `dd` 数量必须成对且顺序一致；状态胶囊必须是 `.pill` 系列（三重表达）。

### 4. 状态矩阵

| 状态 | class | 是否存在 | rb.css | 视觉差别 | 文字/图标要求 |
| --- | --- | --- | --- | --- | --- |
| 未保存（默认） | `.draft` | ✅ | 291–292 | 2px **虚线** 琥珀 `#B45309` 边 + 白底 + 14px 圆角 + 18px 内边距 | 状态文字「未保存」+ 琥珀图标（`.pill--pending`） |
| 已保存 | `.draft--saved` | ✅ | 293 | 2px **实线** + 边框色转 `#E7E5E4` | 「已保存 · 计划编号 plan_7Q2F9K」+ **对勾图标**（不能只靠绿色，content-spec S06）+ 主按钮「打开计划」 |
| 待确认（写入结果未知） | `.draft` + `.notice--warn` | ✅ 组合 | 227、291 | **外观仍是未保存态**；额外 `.notice--warn` 说明块 | 「正在确认是否保存…」+「写入结果尚未确认，请勿重复创建；可稍后查询状态。」+ 次级按钮「查询写入状态」 |
| 保存中（请求在途） | — | ⚠ 无专属类 | — | 用 `.btn[disabled]`（205）表达按钮不可重复点击 | 不得自造 `.draft--saving` |
| 保存失败（已确认失败） | — | ❌ **不是草稿类** | — | 失败用 `.notice--danger` + 保留草稿（PRD PLAN-02：「保存失败时保留草稿并提示原因」） | 不得把 `.draft` 变红 |
| 悬停 `:hover` | ❌ 不存在 | — | — | rb.css 无 `.draft:hover` | 草稿不是可点区域 |
| 按下 `:active` | ❌ 不存在 | — | — | — | — |
| 禁用 | ❌ 不适用 | — | — | — | — |
| 聚焦 | 仅内部按钮 | 110 | `:focus-visible` | 「保存为我的计划」「继续修改」「查询写入状态」用原生 `button` |

> ⚠ 关键区分：**「待确认」≠「失败」**。实现里没有 `.draft--failed`，也不应新增；
> 「待确认」保留未保存外观，靠文字 + `.notice--warn` 表达；只有**已确认**的失败才用 `.notice--danger`。
> 服务端 503 不能核实操作时，客户端**仍显示待确认**（后端详细设计 §12.2）。

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| 便签底色 | `--draft-bg` | `#FFFFFF` | | 291 |
| 边框宽 | `--draft-border-w` | `2px` | 未保存与已保存**同宽**，只有线型/颜色变 | 291、293 |
| 边框色（未保存） | `--draft-border-color` | `#B45309` | 「未保存态：虚线琥珀边」，经 L2 `--pending-border`（上游解析链，非消费方） | 291 |
| 圆角 | `--draft-radius` | `14px` | 与卡片同圆角 | 292 |
| 内边距 | `--draft-pad` | `18px` | 四边同值 | 292 |
| head 间距 | `--draft-head-gap` | `12px` | 标题 ↔ 状态胶囊 | 294 |
| head 下外边距 | `--draft-head-margin-b` | `12px` | | 295 |
| kv 键列宽 | `--draft-kv-key-col` | `auto` | **不是 `8em`**：键按内容自适应 | 296 |
| kv 行间距 | `--draft-kv-gap-y` | `6px` | `gap:6px 12px` 的行间距 | 296 |
| kv 列间距 | `--draft-kv-gap-x` | `12px` | 键列 ↔ 值列 | 296 |
| kv 键字号 | `--draft-kv-key-fs` | `13px` | | 297 |
| kv 键颜色 | `--draft-kv-key-fg` | `#6B6259` | 经 L2 `--text-muted`（上游解析链，非消费方） | 297 |
| 已保存边框色 | `--draft-saved-border-color` | `#E7E5E4` | 经 L2 `--border`（上游解析链，非消费方）；线型 `solid` **无 token** | 293 |

**token 未覆盖的裸值（诚实缺口）**：`border-style:dashed`（291）与 `solid`（293）的**线型**无 token；
`.draft__kv dd` 的 `overflow-wrap:break-word`（298）无 token；`.draft__kv dt` 的 `white-space:nowrap`（297）无 token。
「待确认」色（`#B45309` 同琥珀）与「未保存」同源，无需新 token——**这正是设计意图：未知不是失败，不引入错误色**。

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 语义元素 | 草稿用 `section` + `header` + `dl`；状态胶囊用 `.pill`（`span`） |
| 可访问名 | `.draft__head` 的 `h3` 提供；若一页有多份草稿，`aria-labelledby` 指向各自标题 id |
| **状态可访问（U2 核心）** | 「未保存」必须以**文字**出现（不只是虚线边）；「已保存」必须带**对勾图标**（不能只靠绿色，content-spec S06）；「待确认」必须以**文字**出现（「正在确认是否保存…」），不得只靠琥珀色 |
| 待确认播报 | `.notice--warn` 容器加 `role="status"`（或 `aria-live="polite"`）使状态变化被朗读；`.draft` 可加 `aria-busy="true"` 表示尚未定论 |
| 幂等提示 | 「重复提交同一操作只会得到同一份计划。」（content-spec S06）用小字 `.small`（388）+ `.muted`（387）呈现；必须**可见文本**，不能放 `title` |
| 键盘 | 「保存为我的计划」「继续修改」「查询写入状态」「打开计划」均为原生 `button`；Tab 顺序 = 视觉顺序 |
| 触控 | 按钮 ≥44px（rb.css:120，`.btn--sm` 也保持 44px） |
| 对比度 | 键 `#6B6259` on `#FFFFFF`；值 `#1C1917` on `#FFFFFF`；琥珀文字 `#8A4107` on `#FBF0DF`；边框 `#B45309` 是 2px 非文字 UI，需 ≥3:1（生成器已核） |
| 不靠颜色 | 未保存 = 虚线 + 琥珀 + 文字「未保存」；已保存 = 实线 + 中性边 + 对勾 + 文字 |
| 动效 | 无 `transition`/`animation`；保存成功不依赖动画 |

### 7. 内容与文案规则

- 逐字（content-spec S06）：标题「复习计划草稿」；状态「未保存」/「已保存 · 计划编号 plan_7Q2F9K」；
  主按钮「保存为我的计划」/「打开计划」；次级按钮「继续修改」/「查询写入状态」。
- 待确认逐字：**「正在确认是否保存…」** + **「写入结果尚未确认，请勿重复创建；可稍后查询状态。」**
  （用省略号 `…`，与 content-spec 一致）。
- 字段值逐字：「实验二排序算法预习计划」；「实验前完成排序算法预习并提交预习报告」；「2026-10-22 → 2026-10-24」；
  依据必须显式标注类型：「**本人课表**」+「**课程资料 〔资料 1〕**」（content-spec S06）。
- 幂等提示逐字：「重复提交同一操作只会得到同一份计划。」（content-spec S06，可放小字）。
- 计划编号形如 `plan_7Q2F9K`：来自 `plan_id`（IF-007 `tool_end.plan_id` / `done.plan_id`），**不得**前端伪造或截断显示。
- 违禁：不得出现「保存失败」当写入未知的口径（必须「待确认」）；不得出现「正在思考」；不得把日期写成中文年月日（须 `YYYY-MM-DD`，tabular-nums）。

### 8. 响应式行为

| 档位 | 行为 | 依据 |
| --- | --- | --- |
| base `<480` | 占满宽；`.draft__head` 折行；`.draft__kv` 键列 `auto` 自适应（中文短标签不挤值列） | rb.css:294–296、b-responsive-spec §4「`.draft` 占满宽」 |
| xs `≥480` | 同 base | — |
| sm `≥768` | 同 base；若放在 `.card-row--2` 里，单张宽度约为列宽一半 | rb.css:182 |
| md `≥1024` | 无组件级规则 | — |
| lg `≥1200` | 随助手列 720px 封顶 | rb.css:165 |
| xl `≥1440` | 仅增留白 | b-responsive-spec §1 |
| 日期/编号 | `font-variant-numeric:tabular-nums` 已由 `body` 全局提供（rb.css:100） | rb.css:100 |
| 嵌套 | 助手片段自带 `.wrap` → `.wrap .wrap`（169）清零内层 padding；`.draft` 不要加左右 margin | rb.css:169 |

### 9. 契约依据与禁止事项

- **依据（U2）**：SRS FR-CHAT-005（「网络断开时，客户端应将显示状态置为『结果待确认』，不得直接认定执行失败或未写入」）、
  PRD PLAN-02（「请求超时但写入结果未知时先查询该写入标识，确定是否已保存，再决定是否重试」）、
  后端详细设计 §12.2（「当数据库不可用且不能核实操作时返回 503……客户端仍显示待确认，不将其转换为 failed」）、
  content-spec S06、SRS IF-007（`tool_end.result_status` 枚举 `ok/empty/created/existing/failed`——`created` 与 `existing` 都是成功，`failed` 才是失败）。
- **状态映射（实现口径）**：`tool_end{success:true, result_status:created}` → `.draft--saved` + 新 `plan_id`；
  `result_status:existing`（幂等命中）→ 同样 `.draft--saved` + **原** `plan_id`（不是新计划）；
  `success:false, result_status:failed` → 草稿保留 + `.notice--danger`；
  **未收到终态 / 数据库不可核实（503）/ 网络断开** → 「待确认」，外观保持未保存；
  `state:deleted`（计划已保存后被删除，后端详细设计 §12.2）→ 不得回退成可再保存的草稿，须显式说明。
- **禁止**：新增 `.draft--failed` / `.draft--saving` / `.draft:hover`；用错误色表达「未知」；
  保存成功只给绿色不给对勾 + 文字；把 `plan_id` 截断或本地生成；
  给 `.draft` 加 `transition`（成功态是切换而非动画）。

---

## KVList `.kv`

### 1. 用途与边界

- **是**：详情/摘要用的**键值列表**：字段名固定、值可长。用在计划详情、课程信息、批次摘要等"少量字段一屏读完"的场景。
- **不是**：不是表格（`.table` 用于同构多行，见 04 号规格）、不是草稿字段区（那里用 `.draft__kv`，键列语义不同）。
- **与 `.draft__kv` 的区别（必须写清，否则实现者会混用）**：

| 维度 | `.kv` | `.draft__kv` |
| --- | --- | --- |
| 键列宽 | **固定 `8em`**（`--kv-row-key-col`），跨行对齐 | **`auto`**（`--draft-kv-key-col`），按内容自适应 |
| 键字号 | `15px`（`--kv-key-fs`） | `13px`（`--draft-kv-key-fs`） |
| 外层 | 独立组件 | `.draft` 内部专用 |
| rb.css | 381–384 | 296–298 |

- **边界**：`.kv` 只做"键 = 字段名、值 = 字段值"的两列；**不做**三列、不做合并单元格、不做排序。

### 2. 结构（DOM 骨架）

```html
<dl class="kv">
  <div class="kv__row"><dt class="kv__k">覆盖日期</dt><dd class="kv__v">2026-10-22 → 2026-10-24</dd></div>
  <div class="kv__row"><dt class="kv__k">来源</dt><dd class="kv__v">助手生成</dd></div>
  <div class="kv__row"><dt class="kv__k">更新时间</dt><dd class="kv__v">2026-10-21 17:20</dd></div>
</dl>
```

| 结构规则 | 说明 |
| --- | --- |
| `.kv` 是 `grid-template-columns:1fr`（381） | **单列格子**，每个 `.kv__row` 占一行 |
| `.kv__row` 才是两列栅格（382） | 在 `div`（或 `dl` 内的 `div`）上写 `display:grid; grid-template-columns:8em 1fr` |
| `dt`/`dd` 必须包在 `.kv__row` 里 | 否则键列与值列无法成对对齐——**这是唯一正确的 DOM 形态** |
| 值列 `overflow-wrap:break-word`（384）+ `dd{margin:0}` | 长值（文件名、ID）折行不留默认缩进 |
| 键列 `white-space` **未设置** | 键若超 `8em` 会折行；中文短标签不会 |

### 3. API 表

| class | 元素 | 必填 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| `.kv` | `dl` | 是 | 列表容器（单列栅格）；行间 `gap:6px` | 381 |
| `.kv__row` | `div` | 是 | 一行键值；`8em + 1fr` 两列 | 382 |
| `.kv__k` | `dt` | 是 | 字段名 | 383 |
| `.kv__v` | `dd` | 是 | 字段值 | 384 |

属性约束：`.kv` 必须是 `dl`；`.kv__row` 必须是 `.kv` 的**直接子元素**；
每行恰好一个 `.kv__k` + 一个 `.kv__v`；`.kv__v` 的 `margin:0` 由实现给出（rb.css:384），不得靠浏览器默认缩进。

### 4. 状态矩阵

| 状态 | 是否存在 | rb.css | 视觉差别 | 要求 |
| --- | --- | --- | --- | --- |
| 默认 | ✅ | 381–384 | 键 `#6B6259` 15px；值 `#1C1917`；行间 6px | — |
| 悬停 `:hover` | ❌ 不存在 | — | rb.css 无 `.kv:hover` / `.kv__row:hover` | 键值不可点 |
| 按下 `:active` | ❌ 不存在 | — | — | — |
| 禁用 | ❌ 不适用 | — | — | 只读字段用 `.input[readonly]`（325），**不是** KVList |
| 空值 | ✅ 文本层 | — | 无专属 class；空值单元格仍渲染 `.kv__k`，值可写「未设置日期」 | content-spec S09 逐字「未设置日期」 |
| 长值换行 | ✅ | 384 | `overflow-wrap:break-word` | — |
| 聚焦 | ❌ 不适用 | — | 无交互元素 | — |

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| 列表行间距 | `--kv-gap` | `6px` | `.kv` 的 `gap`（`.kv` 是单列栅格，故非行内列间距） | 381 |
| 键列宽 | `--kv-row-key-col` | `8em` | 「键列固定 8em」——跨 `.kv__row` 对齐 | 382 |
| 行内列间距 | `--kv-row-gap` | `12px` | 键列 ↔ 值列 | 382 |
| 键字号 | `--kv-key-fs` | `15px` | 值继承 `body` 的 17px（rb.css:99） | 383 |
| 键颜色 | `--kv-key-fg` | `#6B6259` | 经 L2 `--text-muted`（上游解析链，非消费方） | 383 |

**token 未覆盖的裸值（诚实缺口）**：`.kv__v` 的 `overflow-wrap:break-word` 与 `margin:0`（384）无 token；
值列字号未设（继承 `body` 17px），因此**没有** `--kv-value-fs`——不要发明。

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 语义元素 | 必须 `dl`/`dt`/`dd`；禁止 `div` + `span` 模拟（读屏无法建立键值关联） |
| 结构 | `.kv__row` 是 `div` 包裹 `dt`+`dd`：`div` 在 `dl` 内是 HTML5 允许的（用于成组），不得改成别的元素 |
| 可访问名 | 由 `dt` 文本提供，无需 `aria-label` |
| 数字 | 日期/编号必须 `tabular-nums`（rb.css:100 全局已给）；值内数字不跳动 |
| 长值 | 换行而非截断（文件名、ID 全文可见）；320px 下不得横向溢出 |
| 触控 | 本组件无交互元素，不涉触控目标 |
| 对比度 | 键 `#6B6259` on `#FFFFFF`；值 `#1C1917` on `#FFFFFF` —— 键与值的**颜色差异不作为唯一层级线索**，字重/位置也参与（键在上/左、值在主位） |

### 7. 内容与文案规则

- 字段名逐字取自 content-spec 的字段清单：S09「标题 / 覆盖日期 / 来源 / 更新时间」、S11「原名 / 类型 / 大小 / 上传时间 / 批次 / 错误原因」。
- 空值逐字：「未设置日期」（content-spec S09 第二条计划）。
- 无 `.kv__k` 的空字段不允许「暂无数据」；要么不渲染该行，要么给出业务明确文案（如「未设置日期」）。
- 日期格式 `YYYY-MM-DD`、时间 `YYYY-MM-DD HH:mm`（content-spec S09），不得中文化或缩写。
- 违禁：不得出现「暂无数据」「—」以外的模糊占位（`—` 也仅用于真正无值的可选项，且需与 content-spec 一致）。

### 8. 响应式行为

| 档位 | 行为 | 依据 |
| --- | --- | --- |
| base `<480` | **键值上下排列**（b-responsive-spec §4「`.kv`：键值上下排列」）——注意实现层是 `8em + 1fr` 两列：窄屏下 `8em ≈ 128px` 占掉可用宽（约 284px 的 45%），值列变窄但仍两列；若要求真正"上下排列"需在组件契约里显式声明改用 `.draft__kv`（`auto`）或给键列 `min-content` | rb.css:382、b-responsive-spec §4 |
| xs `≥480` | 同上 | — |
| sm `≥768` | `8em` 键列占比下降，值列变宽（b-responsive-spec §4「8em 标签列」） | 382 |
| md `≥1024` | 无组件级规则 | — |
| lg `≥1200` | 随容器 880px / 助手 720px 封顶 | rb.css:164–165 |
| xl `≥1440` | 仅增留白 | b-responsive-spec §1 |
| 嵌套 | 助手片段自带 `.wrap` → `.wrap .wrap`（169）清零内层 padding | rb.css:169 |

> ⚠ **规格与实现的口径差（已如实记录，未擅自"补"断点）**：b-responsive-spec §4 写的是 `<480` 「键值上下排列」，
> 但 rb.css:381–384 **没有**任何媒体查询——`.kv__row` 在所有宽度都是 `8em + 1fr`。
> 实现者不得自行加断点；若产品要求窄屏真正堆叠，须先改 rb.css + tokens.json，再更新本规格与 b-responsive-spec。
> 在此之前，**本组件的权威行为是 rb.css 的连续两列**。

### 9. 契约依据与禁止事项

- **依据**：rb.css:381–384；b-responsive-spec §4（`.kv` 行）；content-spec S09/S11 字段清单。
- **禁止**：给 `.kv` 加 `:hover`/`:active`；用 `.kv` 承载可编辑字段（那是 `.field`/`.control`）；
  在 `.kv` 内放三个以上单元格；用 `.table` 代替 `.kv` 呈现少量固定字段；
  自造 `--kv-value-*` token（值列无 token）；为"窄屏堆叠"私加媒体查询。

---

## Prose `.prose`

### 1. 用途与边界

- **是**：**长文正文**的可读性容器：限制 measure（`68ch`）、提供段落节奏、标题字重/行高、链接与行内代码样式。
- **不是**：不是排版主题（不给标题加边框/背景）、不是 Markdown 渲染器（渲染归属前端安全渲染层，PRD CHAT-02「Markdown 必须安全渲染」）、
  不承担引用样式（引用用 `.cite`）。
- **边界**：`.prose` 只做两件事——**限宽**与**继承全局排版的锚点**。它**不**定义自己的增删样式，
  因此它是本族唯一"零根规则、全靠全局元素选择器"的组件（见 §5 的诚实说明）。
- **与助手列的关系**：助手列已是 720px（`--wrap-assistant-max`）；`.prose{max-width:68ch}`（170）在 17px 字号下约 `68 × 8.5px ≈ 578px`，
  **比 720px 更窄**——所以助手回答正文**不需要**再包 `.prose`（会二次限宽、浪费列宽），它用于**内容页**的长文段落。

### 2. 结构（DOM 骨架）

```html
<div class="prose">
  <h3>实验二预习要求</h3>
  <p>根据《数据结构实验指导书（2026 秋）》，下次实验前需要完成：</p>
  <ol>
    <li>预习实验二排序算法；</li>
    <li>提交预习报告，不少于 500 字。〔资料 1〕</li>
  </ol>
  <p>相关命令示例：<code>sort -k2 -n data.txt</code>，详见 <a href="/me/plans">我的计划</a>。</p>
</div>
```

| 结构规则 | 说明 |
| --- | --- |
| `.prose` 自身**只有** `max-width:68ch`（170） | 无 padding、无边框、无背景；不要给它加 `.card`（会变成卡片） |
| 段落间距来自全局 `p{margin:0 0 18px}`（107） | `.prose` 不加自己的 `p` 规则；`--prose-para-margin-b` 描述的就是这条全局节奏 |
| 标题字重/行高来自全局 `h1,h2,h3,h4{line-height:1.35;font-weight:600}`（106） | 层级不跳级；`.prose` 内用 `h2`–`h4` |
| 链接色来自全局 `a{color:var(--prose-link-fg)}`（108） | 链接**必须**有可辨识文本，禁止「点击这里」 |
| 行内代码来自全局 `code,.mono{font-family:mono;font-size:.92em}`（109） | 只做行内代码；**没有**代码块样式（无 `pre` 规则）——需要代码块时须先登记 |
| 列表 | `ol`/`ul` 无自定义样式（用浏览器默认，`padding-inline-start` 约 40px）——窄屏长列表需实测不溢出 |

### 3. API 表

| class | 元素 | 必填 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| `.prose` | `div` / `section` | 是 | 长文容器；唯一规则是 `max-width:68ch` | 170 |

| 允许的内联/块元素 | 来源 | 约束 |
| --- | --- | --- |
| `p` | rb.css:107 | 下外边距 18px |
| `h1`–`h4` | rb.css:106 | `line-height:1.35; font-weight:600`；层级不跳级 |
| `a` | rb.css:108 | 主色深色 `#0F4A42`；必须可辨识 |
| `code` / `.mono` | rb.css:109 | 等宽 + `0.92em` |
| `ol` / `ul` / `li` | 浏览器默认 | 无 token；不得嵌套超过 2 层 |
| `.cite` / `.cite-mark--pending` | rb.css:276–288 | 引用标记随文内出现在 `.prose` 里是允许的 |

属性约束：`.prose` **不得**作为 `.bubble` 的直接子元素出现在助手回答里（见 §1 与 §8）；
`.prose` 内不得放交互组件（`.chat`/`.composer`），长文之外的结构归各自组件。

### 4. 状态矩阵

| 状态 | 是否存在 | rb.css | 说明 |
| --- | --- | --- | --- |
| 默认 | ✅ | 170、106–109 | 限宽 68ch + 全局排版节奏 |
| 链接默认 | ✅ | 108 | `#0F4A42` 下划线（浏览器默认 `text-decoration:underline`） |
| 链接悬停 | ❌ **`.prose a:hover` 不存在** | — | 全局也没写 `a:hover`；不要给 `.prose a` 加 hover 样式 |
| 链接聚焦 | ✅（全局） | 110 | `:focus-visible{outline:3px solid #0F4A42;outline-offset:2px}` |
| 已访问 | ⚠ 浏览器默认 | — | 无 token、无规则；不要用 `:visited` 上色（会泄露浏览史） |
| 悬停/按下/禁用 | ❌ 不适用 | — | `.prose` 是非交互容器 |
| 行内代码 | ✅ | 109 | 仅字体与字号 |

### 5. token 消费表

| 属性 | L3 token | 解析值 | 说明 | rb.css |
| --- | --- | --- | --- | --- |
| 正文 measure | `--prose-max` | `68ch` | 「≤68ch」（b-responsive-spec §2） | 170 |
| 段落下外边距 | `--prose-para-margin-b` | `18px` | 全局 `p` 规则的实际值 | 107 |
| 标题字重 | `--prose-h-fw` | `600` | 全局 `h1–h4` | 106 |
| 标题行高 | `--prose-h-lh` | `1.35` | 全局 `h1–h4` | 106 |
| 链接颜色 | `--prose-link-fg` | `#0F4A42` | 经 L2 `--accent-strong`（上游解析链，非消费方） | 108 |
| 行内代码字体 | `--prose-code-font` | `ui-monospace,SFMono-Regular,"Cascadia Mono",Consolas,monospace` | 全局 `code,.mono` | 109 |
| 行内代码字号 | `--prose-code-fs` | `0.92em` | 「行内代码字号（0.92em）」 | 109 |

**诚实说明（本组结构性缺口）**：上述 7 个 token 中有 6 个描述的是**全局元素规则**，而 rb.css 里
**不存在** `.prose p` / `.prose h3` / `.prose a` / `.prose code` 这些选择器——它们以 `p{}` / `h1,h2,h3,h4{}` /
`a{}` / `code,.mono{}`（106–109）的**全局形态**存在。因此：

- `--prose-*` 是**语义归组**，不是"`.prose` 作用域内的属性"；Vue 实现若把样式收进组件 `<style scoped>`，
  会导致 `.prose` 内的 `p`/`h`/`a`/`code` **失去这些样式**——必须保留全局层（或显式写成 `.prose p` 等等价选择器）。
- 唯一真正绑定 `.prose` 的是 `--prose-max`（rb.css:170）。
- 裸值缺口：列表 `ol/ul` 的缩进与标记样式（无 token）；`a` 的下划线（无 token）；`pre`（无规则）。

### 6. 无障碍要求

| 项 | 要求 |
| --- | --- |
| 语义元素 | `p`/`h*`/`ol`/`ul`/`a`/`code` 原生元素，**禁止**用 `div` + CSS 模拟段落 |
| 标题层级 | 不跳级（content-spec §1）；助手回答里若流式插入标题，须由渲染层保证层级 |
| 链接 | 必须有可辨识文本；不得用「点击这里」「了解更多」；站内链接用 `a`（浏览器默认下划线 + 主色） |
| 语言 | 中文正文靠 `lang="zh-CN"`（页面级），组件不重复声明 |
| 可读性 | measure ≤ 68ch；行高 1.75（`body`，rb.css:99）；窄屏不缩小正文（b-responsive-spec §6「窄屏不缩小」） |
| 行内代码 | 只表"这是代码"，不承担语义；不用于强调文字 |
| 数字 | 全局 `tabular-nums`（rb.css:100），日期/编号对齐 |
| 对比度 | 正文 `#1C1917` on `#FFFFFF`；链接 `#0F4A42` on `#FFFFFF`；行内代码同正文色 |
| 动效 | 无 |
| 安全渲染 | PRD CHAT-02「Markdown 必须安全渲染」：`.prose` 只接受白名单元素，禁止内联 `style`、`<script>`、事件属性（该要求由渲染层落实，规格在此声明边界） |

### 7. 内容与文案规则

- 正文逐字取自 content-spec，如 S04 回答原文（含 `〔资料 1〕` 标记）。
- 引用标记在正文里用 `.cite-mark--pending` 包裹（未验证时），已验证引用用 `.cite` 卡片紧随段落后——**两者同文本、异样式**（U1）。
- 「课程规定」（来自资料）与「一般学习建议」（非资料依据）必须视觉区分、不得混排（content-spec S04）——用 `.pill--evidence` / `.pill--advice`，**不要**在 `.prose` 内自造样式。
- 违禁：不得出现「正在思考」「AI 推理中」；不得把模型推理过程写成正文段落（content-spec §3）；
  不得出现「暂无数据」（空状态归 `.empty`）。

### 8. 响应式行为

| 档位 | 行为 | 依据 |
| --- | --- | --- |
| base `<480` | `max-width:68ch` 不生效（可用宽 < 68ch 时自然占满）；正文 17px **不缩小** | rb.css:170、b-responsive-spec §6 |
| xs `≥480` | 同上 | — |
| sm `≥768` | `.wrap` 内边距升为 36/24px；`.prose` 仍限宽 68ch（约 578px） | rb.css:166、170 |
| md `≥1024` | 无组件级规则 | — |
| lg `≥1200` | 容器达 880px；`.prose` 仍 68ch（此时限宽**真正生效**） | rb.css:164、170 |
| xl `≥1440` | 仅增留白；`.prose` 不变宽 | b-responsive-spec §1 |
| 助手列 | 助手列 720px > 68ch；回答正文**不要**套 `.prose`，measure 由 `.wrap--assistant` 提供 | rb.css:165、170 |
| 嵌套 | 助手片段自带 `.wrap` → `.wrap .wrap`（169）清零内层 padding；`.prose` 不加 padding/margin 补偿 | rb.css:169 |

### 9. 契约依据与禁止事项

- **依据**：rb.css:106–110、164–170；b-responsive-spec §2（正文 measure ≤68ch）、§6（正文字号与行高）；
  README 硬要求 7；content-spec §1（长文本换行、无 `word-break:break-all`）、S04。
- **禁止**：给 `.prose` 加 padding/背景/边框（那是 `.card`）；给 `.prose a` 或 `.prose code` 新增 hover/状态样式（实现里没有）；
  在助手气泡内套 `.prose`；把 `.prose` 当 Markdown 渲染器（安全渲染是渲染层职责）；
  用 `word-break:break-all`（content-spec §1 明确禁止）；把 `--prose-*` 收进 `scoped` 样式而丢掉全局 `p/h/a/code` 规则（见 §5 诚实说明）。

---

## 附：本文件 token 覆盖自检

| L3 组 | token 数 | 消费表出现处 |
| --- | --- | --- |
| `card` | 15 | §Card 第 5 节（全 15 行） |
| `chat` | 16 | §Chat 第 5 节（全 16 行） |
| `composer` | 9 | §Composer 第 5 节（全 9 行） |
| `cite` | 21 | §Citation 第 5 节（全 21 行） |
| `draft` | 13 | §Draft 第 5 节（全 13 行） |
| `kv` | 5 | §KVList 第 5 节（全 5 行） |
| `prose` | 7 | §Prose 第 5 节（全 7 行） |
| **合计** | **86** | 4 份规格并集 = tokens.json `component` 全部组 |

口径：本文件只声明 `card, chat, composer, cite, draft, kv, prose` 七组；`rb.css:169` 的
`.wrap .wrap` 规则由 `wrap` 组承担（01 号规格），本文件只按 S5 专条引用其**行为**，不声明该组。
所有「解析值」列逐字取自 `tokens.flat.json`。
