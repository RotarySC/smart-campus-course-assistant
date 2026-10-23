# 设计系统：三层 token 与组件 API 规格

方向 B（纸感墨绿 · 专注对话）的**设计系统**。上游是 [`../responsive/rb.css`](../responsive/rb.css)
（响应式原型样式契约。冻结版为 74 个 `:root` 变量、122 个 class；阶段 A 修复后 75 个 `:root` 变量、class 数不变），
本目录把它形式化为可被 Vue 3 实现直接消费的三层 token + 组件规格。

## 目录

| 文件 | 是什么 |
| --- | --- |
| [tokens.json](tokens.json) | **单一真源**。四层 token 定义、断点表、对比度判据、分层纯度规则 |
| [generate.py](generate.py) | 生成器 + 校验器。产出下列文件；任一项 FAIL 就以非 0 退出且不产出 |
| [tokens.css](tokens.css) | 生成物。四层 `:root`，可直接被页面/框架引入 |
| [tokens.md](tokens.md) | 生成物。人类可读参考：分层表、解析值、对比度实测、裸字面量迁移对照 |
| [tokens.ts](tokens.ts) | 生成物。TS 常量（断点 + 解析值），供 Vue 3 + TS 直接 import |
| [tokens.flat.json](tokens.flat.json) | 生成物。全部 token 的解析后字面值，供其它工具/校验脚本消费 |
| [components/](components/) | 组件 API 规格（4 份，按组件族分） |
| [system.html](system.html) | **活样式手册**：真实渲染三层 token 与全部组件状态。双击打开即可评审 |
| [verify-system.py](verify-system.py) | 独立于生成器的确定性校验（token 一致性、规格↔token 覆盖、活手册 token 纯度） |
| [verification.md](verification.md) | 独立验证报告 |

重新生成：

```powershell
$env:PYTHONIOENCODING="utf-8"; python design\system\generate.py
```

## 四层结构

```
L1 primitive  --p-*                    原始值。唯一允许出现字面量的一层。
      ↓ 只指向 L1
L2 semantic   --bg-* --text-* --accent* --state-* --border* --layout-* …
                                       用途别名。颜色语义在此收敛。
      ↓ 颜色必须经 L2；尺度类原语可直取 L1
L3 component  --<组件>-<部位>-<属性>     组件属性。组件 CSS 规则只消费这一层。
      ↓
L0 compat     --c-* --sp-* --fs-* …     rb.css 变量名的兼容声明（deprecated）
```

### 分层纯度规则（由 `generate.py` 强制）

1. **L1** 的值必须是字面量（hex / rgba / px / em / ch / % / 无单位数 / 关键字 / 字体栈）。
2. **L2** 的值只能是 `var(--p-*)`，不得出现字面量；MUST NOT 引用 L2 或 L3。
3. **L3** 的值只能是 `var()` 组合：
   - **颜色必须经 L2**。`--btn-primary-bg:var(--p-green-700)` 是违规，必须写成 `var(--accent)`。
   - 间距/字号/行高/字重/边宽/圆角/尺寸/时长/缓动/z-index 这些**尺度类**原语允许直取 L1——
     尺度只是数字，不承载语义。
   - 禁止 L3 之间互相引用（`--a-x:var(--b-y)` 违规），避免组件耦合与顺序依赖。
   - 禁止裸色值与带单位裸长度；允许无单位数值（含 `0`）、关键字（`transparent`/`auto`/`none`/`tabular-nums`/`inherit`）与 `var()` 拼接的复合值。
4. **组件 CSS 规则只允许消费 L3**。组件样式里出现 `var(--p-*)` 或 `var(--bg-*)` 都算跨层违规——
   这一条在 `system.html` 上被机械校验。
5. 媒体查询断点无法用 CSS 变量表达，必须写字面量，取值只能来自 `tokens.json` 的 `breakpoint` 表；
   `max-width` 档只允许写 `min-width 档 − 1`（如 `sm` 的向下写法是 `767px`）。

### 为什么要有 L0 兼容层

`rb.css` 是**已独立验证并冻结**的产物（六宽度页面级溢出为 0、表格卡片化、无障碍计数等）。
设计系统不重写它，而是做它的**严格超集**：`generate.py` 会逐值比对 `rb.css` 的每个 `:root` 变量与
新系统的解析值，要求逐字相等。这样原型零改动继续工作，Vue 阶段则直接消费 `tokens.css`。

`rb.css` 的 75 个 `:root` 变量里有 **25 个**已经由**同名**的系统层承担（24 个 L2：`--bg-page`…`--focus`；
1 个 L3：阶段 A 新增的 `--root-scroll-offset`），**不在 L0 重复声明**——重复声明会让变量自引用
（`--bg-page:var(--bg-page)`）而在计算值阶段失效。这个坑是生成器第一次运行时抓出来的。

## 已固化的规模

| 层 | 数量 | 说明 |
| --- | --- | --- |
| L1 primitive | 91 | 含 rb.css 未 token 化的 `#FFFFFF`×2、裸 `rgba`×2、z-index×4、动效时长/缓动、尺寸档 |
| L2 semantic | 41 | 颜色语义 + 布局/尺寸/动效语义 |
| L3 component | 337 | 覆盖 27 个组件族的每一个可配置属性 |
| L0 compat | 50 | `rb.css` 中不与 L2 重名的变量名 |
| **合计** | **519** | |

`generate.py` 同时保证：**0 个未引用的 L1 token**、**41 对对比度全部达标**、**75/75 rb.css 逐值等价**。

对比度这一轮**新增了 alpha 合成**：`--bg-readonly`/`--bg-hover-weak` 带 alpha，
判对比度前先与卡片底合成；第 2 轮报告里「未做 alpha 合成」的缺口在这条通路上补齐。

## 组件规格契约

组件规格是**给实现者看的接口文档**，不是设计说明。每份必须严格按下面的骨架写，
以便校验脚本能做机械比对。

```markdown
<!-- owns: <L3 token 组名，逗号分隔> -->
# <族名>

## <组件名> `<class>`
### 1. 用途与边界
### 2. 结构（DOM 骨架）
### 3. API 表
### 4. 状态矩阵
### 5. token 消费表
### 6. 无障碍要求
### 7. 内容与文案规则
### 8. 响应式行为
### 9. 契约依据与禁止事项
```

### 硬要求

1. **`<!-- owns: ... -->`** 必须列全本文件负责的 L3 token 组名（即 `tokens.json` 的
   `component` 下的组名，如 `btn`、`pill`、`table`）。全部 4 份的并集必须**恰好等于**全部 L3 组，
   且不得有两个文件声明同一组——校验脚本会查。
2. **token 消费表**逐行给：`属性 | L3 token | 解析值 | 说明`。解析值必须与 `tokens.flat.json` 一致。
3. **只能引用真实存在的 token**。不得发明 token 名；不得引用 L1/L2（除非在解释分层时显式标注为「上游」）。
4. **状态矩阵**必须覆盖该组件在 `rb.css` 里真实存在的状态。若只有 `:hover`，就只写 `:hover`，
   不要补想象出来的 `:active`——**规格里不得出现实现中没有的状态**（这是本目录最容易犯的错）。
5. **每个组件的每个属性都要能锚到 `rb.css` 的行号**（写成 `rb.css:193`）。规格与实现的对应关系必须可查。
6. **无障碍要求**要具体到属性：`role`、可访问名来源、键盘行为、`aria-*`、对比度要求、触控目标。
   「状态不能只靠颜色」是硬要求：必须图标 + 文字 + 颜色三重。
7. **内容与文案**只能引用 [`../directions/shared/content-spec.md`](../directions/shared/content-spec.md)
   的逐字文案，不得自造。尤其不得出现「正在思考」「暂无数据」这类违禁表述。
8. **禁止引用评审专用 class**：`.bph`、`.view`、`.view__id`、`.view__cap`、`.view__note`、`.proto-banner`。
   它们被 `tokens.json` 的 `meta.scope` 明确排除在设计系统之外。
9. 响应式行为必须用 `tokens.json` 的断点档位表述（base/xs/sm/md/lg/xl），不得写 4 个数字以外的临时断点。

## 组件族与文件归属

| 文件 | 组件族（`owns`，共 27 组，不重不漏） |
| --- | --- |
| [components/01-shell-navigation.md](components/01-shell-navigation.md) | root, focus, skiplink, sr, appbar, brand, navlink, tabbar, wrap, login |
| [components/02-actions-status.md](components/02-actions-status.md) | btn, chip, pill, notice, steps, empty |
| [components/03-conversation.md](components/03-conversation.md) | card, chat, composer, cite, draft, kv, prose |
| [components/04-forms-data.md](components/04-forms-data.md) | field, control, table, utility |

> 精确的组名清单以 `tokens.json` → `component` 的实际分组键为准；`verify-system.py` 会机械核对
> 4 份的 `owns` 并集是否**恰好等于**全部 L3 组、且无重复。

## 收口裁决与遗留缺陷

4 位规格作者与样式手册作者共提出 20 余处「无法从 rb.css 断定」的点。以下是 Lead 的逐条裁决。
**裁决 1–5 涉及冻结产物（`rb.css` / `parts/*` / `b-responsive.html`），本轮一律不改**——改动它们会使
上一阶段「六宽度页面级溢出为 0」的独立验证失效、哈希变化，需要重跑整套渲染验证。
因此这些是**已登记的缺陷 + 实现期必修项**，不是被忽略的问题。

| # | 议题 | 裁决 | 性质 |
| --- | --- | --- | --- |
| 1 | **琥珀语义边界**：原型把 `pill--warn` 用在「检索成功 · 没有足够依据」(assistant.html:1001) 与「处理中」(admin.html:1686/1756) 等 6 处 | 独立验证确认它实际承载 **5 类语义**（依据不足／未保存／待确认／处理中／需确认后继续）。token 层本就分了两条通路：`--pending*`（专用于未保存/待确认）与 `--state-warning`（一般警告）。据此：**依据不足、待确认、需确认后继续用 warn 合规**；**「处理中」用 warn 违规**（进行中不是警告）→ 实现期改 `pill--info`（2 处）；用 `pill--warn` 表示未保存属视觉等价但**语义标签选错**，应改 `pill--pending` | 2 处原型缺陷 + 1 处标签误用 |
| 2 | `a.chip` 在冻结原型中**零实例**（`.chips` 容器里实际是 `.btn--sm`，assistant.html:43–56） | 验证确认：原型里 `a.chip` 0 实例、`.chips` 容器有 1 个装的是 `<button class="btn btn--sm">`；而 `system.html` 里 `a.chip` 有 4 实例。两句都对——**它在设计系统里被 token 化并演示（15 个 `--chip-*`），只是原型未采用**。保留 token，**不得**把既有示例入口改写成 `a.chip`（那是「动作」变「导航」的语义变更） | 已知「定义但原型未用」，与上一阶段 6 个未用 class 同类 |
| 3 | `records.html:273` 的 `.pill--danger`「不可恢复」**没有图标** | 验证给出关键补充：该胶囊自身确无 `<svg>`，但**同一卡片的 `<h3 id="s09-del-title">` 有 24×24 警告三角**——整块删除确认面板的三重编码是齐的，缺的是**胶囊自身**的图标。据此**下调严重度**：不是 WCAG 违例，是与组件规格「状态胶囊自带图标」不一致的**一致性缺陷**，实现期按规格补图标即可 | 一致性问题（非无障碍违例） |
| 4 | `.steps__toggle` 用 `.sr-only` 的 `clip:rect(0 0 0 0)` 隐藏，`<480` 折叠态**键盘聚焦无可见焦点** | 独立验证 **FAIL 确认**：`b-responsive.html` 里聚焦后 `outline-style:none`，且**没有** `.steps__toggle:focus-visible ~ .steps__summary` 联动规则。确认为 WCAG 2.4.7 风险（见下方 W2） | 原型无障碍缺陷 |
| 5 | sticky 顶栏 56px，但 rb.css **无 `scroll-padding-top`** → 锚点跳转（含 skip-link 到 `#main`）目标被顶栏遮住 | 独立验证 **FAIL 确认并量化**：`#v-S11` 跳转后目标 `top=0.3px` 而顶栏底 `56.7px`，遮挡 **56.4px**；skip-link 到 `#main` 遮挡 **56.7px**。`rb.css`、`system.html` 与 token 层的 `scroll-padding-*` / 滚动偏移变量各 **0 条**。**注意：`system.html` 自身不复现**——它的外壳是 `static` 的 `shell-head`，`.appbar` 只是组内演示实例，所以手工浏览手册发现不了（见下方 W1） | 原型可用性缺陷 |
| 6 | `content-spec.md`:54 要求密码「带显示/隐藏切换」，`parts/login.html:29–33` **未实现**，且该按钮文案也没在任何地方冻结 | 验证确认 `login.html` 里 3 个 password 输入、3 个按钮全是「登录」、0 个含 svg、无「显示/隐藏」字样、无 `aria-pressed`。同时确认 `01-shell-navigation.md:937` 明写「为密码切换控件自拟文案或只给图标不给可访问名」是禁止项——**是有据可查的延期决定，不是遗忘**。定性为**内容契约自身不完整**：content-spec 点名了一个控件却从未冻结它的文案。修法：先在 content-spec 里冻结该按钮的文案与 `aria-pressed` 语义，再实现 | 内容契约缺口（先于实现解决） |
| 7 | `--wrap-pad-*-md` 命名后缀是 `md`，实现却在 `min-width:768px`（= `sm`） | **是 Lead 的命名错误**，已改名 `--wrap-pad-y-sm` / `--wrap-pad-x-sm`，并在 token 说明里写明档位。这类错名会让每个实现者按 1024px 去理解 | 已修（token 源缺陷） |
| 8 | `.table--stack td > *` 的机制表述 | 规格作者主张「落进标签列的是第 3、5…个」；Lead 判定为**第 2、4…个（偶数位）**——漏算了 `td::before`（有 `content` 的伪元素**也是** grid item，占掉第 1 格，所以顺序是 `::before → 子1 → 子2 …`）。**证据**：M1 那处 `td` 里只有两个子元素（胶囊 + 失败原因），实测被压的是第 2 个；只有「第 2 个落第 1 列」能解释该现象。规格已更正，并请独立验证者用真实测量裁定 | 已更正表述，机制结论待独立验证 |
| 9 | `--motion-spin-*` 在 L2，L3 无组件级 motion token → `.step--running` 的旋转**没有 duration，动画不会真的转** | 确认为 token 建模缺口。已在 `steps` 组补 `--step-running-spin-duration` / `--step-running-spin-easing`（取 L1 的 `--p-duration-spin` / `--p-easing-linear`），样式手册改为消费它们 | 已修（token 源 + 手册） |
| 10 | `.textarea[readonly]` / `.textarea[disabled]` / `.select[readonly]` 在 rb.css 中**未定义**；`.input[disabled]` 只改透明度不改底色 | 如实登记为缺口，规格作者未发明样式，处理正确。当前屏幕未触发这些组合；实现期若要使用，需先补 rb.css 并重测 | 登记缺口 |
| 11 | `--table-stack-name-pad-b`(8px) 被借用来表达 rb.css:372 的 2px | 确认为两处不同值。已补 `--table-stack-name-label-margin-b`(2px) 并改用手册消费，不再借用 `--notice-ico-offset-y` | 已修（token 源 + 手册） |
| 12 | `.appbar__nav{gap/margin-left}`、`.appbar__user{gap}` 三处无 token | 已补 `--appbar-nav-gap` / `--appbar-nav-offset-x` / `--appbar-user-gap`，并同步进 01 的消费表 | 已修 |
| 13 | 4 处原型锚定串（「跳到主要内容」「校园课程助手」「管理员」、两个 `aria-label`）不在 content-spec | 这是**组件级 UI 字符串**（跳转链接、landmark 命名），不是屏幕内容，归组件规格管辖而非 content-spec。其中「管理员」是登录身份数据、不应硬编码。已登记，口径统一为：content-spec 管屏幕内容文案，组件规格管组件 chrome 文案 | 口径澄清 |
| 14 | `.kv` 的 `b-responsive-spec` 声明与实现不符（文档称 `<480` 上下排列，`rb.css:381-382` 全宽两列无断点） | **是 Lead 的文档错误**。已按 rb.css 真实行为改正并在 `b-responsive-spec.md` §4 加勘误；rb.css 为冻结产物，文档与它冲突时以它为准 | 已修（文档缺陷） |

### 收口时对 token 源的净变更

| 变更 | 数量 | 触发者 |
| --- | --- | --- |
| 新增 L3（`--cite-border-w`、`--cite-head-gap-x`、`--appbar-nav-gap`、`--appbar-nav-offset-x`、`--appbar-user-gap`、`--step-running-spin-duration`、`--step-running-spin-easing`、`--table-stack-name-label-margin-b`） | +8 | 规格作者的诚实缺口登记 |
| 改名 L3（`--wrap-pad-y-md`/`-x-md` → `-sm`） | 2 | 命名与实现档位不符 |
| 删除 L3（`--card-head-border-color`，与 `--card-border-color` 重复） | −1 | Lead 自查 |
| 阶段 A 新增 L3（`--root-scroll-offset`，W1 的配套 token） | +1 | 独立验证给出的 W1 修法 |
| 合计 | 510 → 518 → **519** | |

**净变更全部来自「规格作者报缺口 → Lead 判定是设计决策还是结构属性 → 是决策就补 token」这条通路。**
被判定为**结构属性、刻意不 token 化**的有：`position`/`display`/`align-items`/`flex` 方向、`overflow-wrap`、
`border-style` 关键字、`env(safe-area-inset-*)`、`gap` 的行/列在两值相同时的合并。这些归组件规格 §2/§3 管辖。

### 本轮的 M1：一个「文本比对与字节比对双双放行」的交付级缺陷

这是本轮最重要的教训，值得单独记。

`generate.py` 生成 `tokens.css` 的文件头注释里写了 `--bg-*/--text-*/...`。
其中那个 `*/` **提前闭合了注释**，于是紧随其后的品牌色 `:root{…}` 与残留的垃圾文本被 CSS 解析器
拼成了**同一条规则**：prelude 是「垃圾文本 + `:root`」而不是 `:root`，那条规则**永不匹配**。

后果：`--p-green-900/700/100` 三个 primitive 从未生效，连带 **30 个 token 在运行时是空的**
（`--accent`、`--accent-strong`、`--focus`、`--btn-primary-bg`、`--cite-accent-color`…）。
最直观的可见后果是 `.btn--primary` 变成 **`background: rgba(0,0,0,0)` 配白字**——主按钮几乎不可读。
任何按本章程推荐方式 `import './tokens.css'` 的 Vue 页面都会失去整个品牌绿。

**为什么原来的 29 项校验全部放行**：
- A 项「生成保真」是 `tokens.json ↔ tokens.css` 的**文本逐值比对**——声明文本确实在文件里；
- G 项「ds-tokens 逐字节一致」是**字节比对**——字节确实一致。
两者都在「文件内容」层，**没有任何一项把 CSS 交给解析器**。这是纯文本通路的**结构性盲区**，
不是某一项写错了。与上一轮「数值检查全绿、只有看图才发现列被压塌」是同一类病：**证据的通路覆盖不到缺陷所在的层**。

修法与防线（都已落地）：
1. 文件头改为 `--bg-* / --text-* / …`（用「星号 空格 斜杠」），并在注释里写明这条禁忌；
2. `generate.py` 增 `check_comment_safety()`（注释里出现提前终止序列即 FAIL，只允许末尾那一个 `*/`）；
3. `generate.py` 增 `check_rule_preludes()` + `check_declarations_reachable()`：
   注释感知剥离后，**每条规则的 prelude 必须恰好等于 `:root`**，且每个 token 的声明都要落在这样的规则里；
4. `verify-system.py` 增**独立实现**的 J 项做同一件事（不 import 生成器）。
   现在报 `58 条规则，无垃圾 prelude` / `519 个 token 在浏览器里都会真正生效`。

独立验证者在真实浏览器里复核了这条判据（`cssRules.length = 58`、每条 `selectorText` 都是 `:root`、
518/518 token 计算值非空且与 `tokens.flat.json` 逐字相等——该数字是 M1 复验当时的规模，阶段 A 新增 1 个
L3 token 后为 519/519），确认 J 项能挡住这一类。

> 讽刺的是：我在给样式手册作者的指令里明确警告过 `*/` 提前闭合这个坑（他发现并修掉了自己文件里的同类问题），
> 却没有检查自己生成器模板里的同一处。**同一个坑在两个文件里各犯一次**——这类缺陷靠"我记得要小心"是防不住的，
> 只能靠把判据做成检查。

### 独立验证发现的 3 个必修项（W1–W3，均有已验证的修法）——**阶段 A 已修**

以下三条都由独立验证在**真实浏览器**里复现、定位到根因、并验证了修法。收口时它们全在冻结的 `rb.css` 里，
按「冻结 + 已独立验证」的约定当轮不改；**阶段 A（实现期）已按下列修法全部落地**（明细见本节末尾的
「阶段 A 修复清单」）。落地后 `rb.css` 不再是原冻结哈希产物，六宽度渲染验证需要重跑。

**W1（高）缺 `scroll-padding-top`，锚点与 skip-link 被顶栏遮挡 56.4–56.7px。**
实测 `#v-S11` 跳转后目标 `top = 0.3px`，而 sticky 顶栏底边在 `56.7px`。
修法（验证者给出）：`html{scroll-padding-top:calc(var(--appbar-min-h) + var(--sp-1))}`。
配套建议：在 L3 的 `root` 组新增 `--root-scroll-offset`，避免在实现里硬编码。
**阶段 A 落地形态**：L3 `root` 组新增 `--root-scroll-offset:calc(var(--shell-appbar-h) + var(--p-space-1))`
（解析值 `calc(56px + 6px)`）；`rb.css:84` 用 L0 名声明同值，`rb.css:94` 由
`html{scroll-padding-top:var(--root-scroll-offset)}` 消费。
**与修法原文的差异（判断项）**：L3 的值**没有**写成 `var(--appbar-min-h)`——那是 L3 引用 L3，
会被 `verify-system.py` 的 **B 项「L3 不互引」判 FAIL**（规则见上文「分层纯度规则」第 3 条）。
`--shell-appbar-h` 与 `--appbar-min-h` 指向同一个值，两者解析结果逐字相同，故 rb.css 等价性不受影响。

**W1 的第二段（阶段 A 复查时才暴露，独立验证与 Lead 各自用一条通路复现）**：62px 的偏移在 **768–774px 视口带**
不够用——该区间顶栏实测 **72.167px**，锚点目标仍被遮约 10px。根因不是 `scroll-padding-top` 写错，而是
**顶栏自身在这 7px 宽的区间里变高了**：

| 视口宽 | `.appbar` 高 | `.appbar__nav` 高 | `.navlink` 高 |
| --- | --- | --- | --- |
| ≤767 | 56.667px | 0（`display:none`） | — |
| **768 / 772 / 774** | **72.167px** | 59.5px | **59.5px（文字折成 2 行）** |
| ≥775 | 56.667px | 44px | 44px |

机制（阶段 A 实测，非推测）：≥768 时三个 flex 子项的**固有宽度** = 品牌 134 + 导航左偏移 12 + 导航 482 +
两个 18px 间距 + 用户胶囊 59 = **723px**；而 768px 视口扣掉滚动条槽 15.33px 与容器左右内边距 36px 后只有
**717px**，缺口 6px。默认 `flex-shrink:1` 把这 6px 按比例摊到导航（−5.65px）与用户胶囊（−0.69px）上，
于是**两者的文字各差 1–2px 放不下当前行宽而折行**（`.navlink` 从 44px 变 59.5px），顶栏随之从 56.667 涨到 72.167。
775px 起缺口消失，故只有 768–774 这 7px 区间异常。

**修法（治本，已落地）**：给 `.navlink`（`rb.css:141`）与 `.appbar__user`（`rb.css:137`）加 `white-space:nowrap`，
让二者不可再被压缩到折行；缺口 6px 由「用户胶囊右侧吃进容器右内边距」吸收（`inner.scrollWidth − clientWidth = 0`，
页面级横向溢出仍为 0）。**未**新增断点、**未**改任何 token 值：`white-space` 与 `overflow-wrap`/`display` 同属
「结构属性、刻意不 token 化」那一类（见上文「收口时对 token 源的净变更」末段）。
落地后实测 9 个宽度（320 / 390 / 480 / 768 / 772 / 774 / 775 / 1024 / 1366）**`appbarH` 恒为 56.67px**，
`.navlink` 恒为 44px，页面级横向溢出恒为 −15px（= 无溢出）。

> **验收判据也要跟着改**：全文档 §8.4 写的 `#main.top >= 62 − 0.5` 在 768px 下**会放行一个仍存在的遮挡**
> （实测 `#main.top = 62.17`，判据通过，但元素实际被盖 10px）。阶段 A 起改用**实测遮挡量**：
> `occlusion = .appbar 的 getBoundingClientRect().bottom − 目标.top`，要求 **≤0.5px**。按此判据实测
> （9 个宽度，`#main` 与 `#v-S11` 两个目标）：`#v-S11` 的 occlusion 为 **−5.0 … −5.56px**，`#main` 为 **0px**
> （它紧邻文档顶部，滚动被 clamp，目标上沿正好落在顶栏下沿，不重叠）。全部 ≤0.5px ✅。
> 该判据的**文档口径更新属于 `docs/` 范围，不在阶段 A 的写入范围内**，已登记给 Lead。

**附带修（skip-link 焦点落点）**：`<main id="main">` 原本不可聚焦，skip-link 跳转后实测
`document.activeElement === BODY`，焦点没落到主内容上（对读屏/键盘用户等于跳转失效）。
已在 `design/responsive/shell.html` 给 `#main` 加 `tabindex="-1"`；实测真实点击 skip-link 后
`document.activeElement.id === "main"`，遮挡 0px。
> **本章程自身不复现这条缺陷**：`system.html` 的外壳是 `static` 的 `shell-head`，`.appbar` 只是组内演示实例。
> 这正是「手工浏览手册发现不了、必须靠真实跳转测量」的例子。

**W2（中）`.steps__toggle` 聚焦时没有任何可见焦点指示。**
它是 `.sr-only` 的 1×1 `clip:rect(0 0 0 0)` 元素，聚焦后 `outline-style:none`，
且没有 `.steps__toggle:focus-visible ~ .steps__summary` 联动规则 → 键盘用户看不到焦点在哪（WCAG 2.4.7）。
修法（3 行，见 `verification.md` §6.1）：给摘要行加 `:focus-visible` 补偿环。
**阶段 A 落地形态（覆盖全宽度，含全文档 §8.7 的裁决 J2）**：
① `rb.css:425` 加 `.steps__toggle:focus-visible ~ .steps__summary{outline:3px solid var(--focus);outline-offset:2px;border-radius:4px}`；
② `rb.css:263` 在 `≥480` 的媒体查询里把该复选框 `display:none`，移出 Tab 序——该宽度下 `.steps__body` 已由
同一条规则强制常显，复选框完全惰性，只剩「隐形焦点陷阱」这一个作用。

**W3（中）长串溢出：两条独立根因，修法已分别验证。**
往四个容器注入 60 字符**无空格**串，320px 下页面级溢出（验证者的分离实验）：

| 容器 | 基线 | 只改 `minmax(0,1fr)` | 只加 `overflow-wrap:anywhere` | 两者 |
| --- | --- | --- | --- | --- |
| `.kv__v` | +523px | **0** | +523px | 0 |
| `.cite__name` | +359px | +359px | **0** | 0 |
| `.card__body` | +375px | +375px | **0** | 0 |
| `.bubble` | +375px | +375px | **0** | 0 |

- `.kv__v` 的病根是 `.kv__row{grid-template-columns:8em 1fr}`：`1fr` 等价 `minmax(auto,1fr)`，
  下限是 min-content，实测第 2 轨被撑到 **657.9px**。**`overflow-wrap` 不影响 min-content，所以它救不了这一处**——
  必须改 `minmax(0,1fr)`（阶段 A 已改，`rb.css:382`）。这与表格那一课是同一个道理，只是当初没在 `.kv` 上同样处理。
- 其余三处是 `overflow-wrap:normal`（无空格串没有断点）。
- 这条同时说明「页面级溢出 = 0」这个结论**依赖内容可控**：夹具里没有超长无空格串，所以两轮验证都放行了。

### 阶段 A（实现期）修复清单

| 项 | 落点（阶段 A 后） | 具体改动 |
| --- | --- | --- |
| W1 | `rb.css:84`、`rb.css:94` | L3 `root` 组新增 `--root-scroll-offset`（token 源），`html{scroll-padding-top}` 消费它；锚点与 skip-link 不再被 56px sticky 顶栏遮挡 |
| W1-b | `rb.css:137`、`rb.css:141` | 顶栏 768–774px 增高到 72.167px 的治本修法：`.navlink` / `.appbar__user` 加 `white-space:nowrap`，9 个宽度 `appbarH` 恒为 56.67px |
| W2 | `rb.css:263`、`rb.css:425` | `<480` 给摘要行加 `:focus-visible` 补偿环；`≥480` 把惰性 `.steps__toggle` 置 `display:none`（全文档 §8.7 裁决 J2） |
| W3a | `rb.css:382` | `.kv__row` 第 2 轨 `1fr` → `minmax(0,1fr)`（`1fr` 的下限是 min-content，实测被无空格长串撑到 657.9px） |
| W3b | `rb.css:189`、`rb.css:241`、`rb.css:281` | `.card__body` / `.bubble` / `.cite__name` 各加 `overflow-wrap:anywhere`；`.table` 单元格保持 `break-word` + `min-width`，**未**改用 `anywhere` |
| #1 | `parts/admin.html:232`、`:302` | 「处理中」两处 `pill--warn` → `pill--info`（进行中不是警告）；`:519` 的「需确认后继续」保持 `pill--warn` 不动 |
| #3 | `parts/records.html:273` | 「不可恢复」危险胶囊补 24×24 内联 SVG（`circle-x`：`fill="none"`/`stroke="currentColor"`/`stroke-width="1.75"`/`aria-hidden="true"`/`focusable="false"`，实例 14×14） |
| #6 | `directions/shared/content-spec.md` §2 S01 | 冻结密码显隐按钮的两态逐字文案（「显示密码」/「隐藏密码」）与 `aria-pressed` 语义；**控件本身仍未实现**（`parts/login.html` 本轮不动） |
| §8.4 附带 | `shell.html:62`（产物 `b-responsive.html`） | `#main` 补 `tabindex="-1"`：skip-link 跳转后焦点真正落到主内容（实测 `activeElement.id === "main"`，此前是 `BODY`） |

**行号策略（值得记）**：W1/W2/W3 的落地刻意做到**不移动 `rb.css` 已有行号**——新增的 `--root-scroll-offset`
与 `--h-appbar` 同行声明、`white-space:nowrap` 就地追加、W2 的补偿环追加在文件末尾，
因此 `rb.css:1–415` 的行号与冻结版逐行一致（改动只落在 84/94/137/141/189/241/263/281/382 这 9 行上）。
理由：4 份组件规格、`b-responsive-spec.md` 与 `docs/` 里有 200 余处 `rb.css:<行号>` 锚点，
整体移动会让它们失准，而重编号不在本轮写入范围内。
副作用：`design/system/components/01-shell-navigation.md` 因新增 1 行消费表行，其**自身**行号在 +1 之后偏移了
1 行（如 U9 那条从 936 → 937）；引用它的 `design/system/verification.md` 与 `docs/` 未同步（写入范围外，已登记）。

### 关于本手册演示与真实用法的两处刻意偏差（已披露）

1. `.steps__toggle` 在 `styleguide-demos.html` 里**没有**加 `.sr-only`，所以手册里显示为一个 13×13 的裸复选框。
   这是刻意的：加了 `.sr-only` 之后它在页面上不可见，评审反而看不到这个控件。
   **真实用法是 `.sr-only` + 摘要 label**，组件规格 §2 写的是真实用法。副作用是 W2 在手册里表现为「裸复选框无焦点环」。
2. `.tabbar` / `.composer` 的演示块把 `position` 覆盖成了 `static`（见 `build-system.py` 的 `CHROME_CSS`），
   否则它们会吸在视口底部、一直盖住下半页。**组件真实行为仍是 `fixed` / `sticky`**，已在各区块描述里写明。

### 本轮独立验证的结论（`verification.md`）

11 项：**PASS 8 / FAIL 2 / 缺陷确认 1**（`1` 计算样式等价性、`2` 六宽度、`3` 人工看图、`4` R7 裁定、
`8` 对比度实测、`9` 规格↔rb.css 全为 PASS；`5` `.steps__toggle` 焦点、`6` sticky 遮挡为 FAIL；
`7` 长串溢出为缺陷确认）。其中两项判定值得单独记：

- **第 1 项（L3 分层忠实性的硬证据）**：修复 M1 后，`system.html`（只消费 L3）与 `b-responsive.html`（rb.css）
  在共同 class 上的计算样式——390px 下 SAME 64 / DIFF 28、1366px 下 SAME 68 / DIFF 28，
  **28 个差异被逐条归因，0 个是真差异**（形态不同、节点选择不同、状态不同、父容器 blockification、网格轨道解析宽度、验证者注入的中和样式）。
  74 个共同 `:root` token 差异 **0**（阶段 A 前为 74 个；加入 `--root-scroll-offset` 后应为 75 个，需独立复验重测）。
- **第 4 项（R7 机制争议）**：独立测量裁定 **Lead 的「第 2、4…个（偶数位）」成立**。
  删掉 `td > *{grid-column:2}` 后 4 子元素 `left` = 142.5 / **18** / 142.5 / **18**（标签列右边界 130.5）；
  `::before` 确实占掉第 1 格。规格作者的「第 3、5…个」不成立。

## 与已冻结产物的关系

- **阶段 A（实现期）起解除冻结**：`rb.css`、`parts/*`、`shell.html` 与产物 `b-responsive.html` 已按「阶段 A 修复清单」修改，哈希随之为新值：
  `rb.css = 0749FA7A47BC155F52A12406123DF6CC`（23,086 B；冻结版为 `94DF48EDFFC1DC33858A545C3574048F` / 21,734 B）、
  `b-responsive.html = 5B73454136F261AC13E9A0203C0C6D73`。
  冻结期「rb.css / b-responsive.html 哈希不变」的声明到此作废。
- 冻结期的三条已验证结论（六宽度页面级溢出为 0、表格卡片化、无障碍计数）建立在旧哈希上，
  **必须重跑**才能再次成立——W3 的两处改动（`minmax(0,1fr)`、`overflow-wrap:anywhere`）、W2 的
  `display:none`、W1-b 的 `white-space:nowrap` 与 `#main` 的 `tabindex="-1"` 都会改变布局盒或键盘行为；
  已列入独立验证任务。阶段 A 的自验已在真实浏览器里量到 9 个宽度（320–1366）：
  `appbarH` 恒 56.67px、页面级横向溢出恒 0、锚点遮挡 ≤0.5px，但**六宽度全量重测（含截图与人工看图）仍未做**。
- 本目录是**增量**：新增 token 源、组件规格、活样式手册、独立校验。
- Vue 3 阶段的落地路径：`import './tokens.css'` → 组件 `<style>` 只消费 L3 token →
  用 `tokens.ts` 的 `breakpoints` 驱动 `matchMedia`；`rb.css` 的 L0 兼容层在迁移完成后删除。
- 上表的 **#1**（处理中改 `pill--info`）、**#3**（危险胶囊补图标）、**#6**（content-spec 冻结密码显隐文案）、
  **#4/W2**（`.steps__toggle` 可见焦点）、**#5/W1**（sticky 顶栏滚动偏移）与 **W3** 已在阶段 A 一次性改完，
  并按原建议整体重跑生成与校验（而不是零散打补丁）。
- 其余登记项性质未变：#2（`a.chip` 原型零实例）仍是「定义但未用于原型」；#10（`.textarea[readonly]` /
  `.select[readonly]` 无样式）仍是实现期缺口；#7–#9、#11–#14 的处置同原文。
