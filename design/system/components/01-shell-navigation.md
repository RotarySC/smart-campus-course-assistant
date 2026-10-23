<!-- owns: root, focus, skiplink, sr, appbar, brand, navlink, tabbar, wrap, login -->
# 外壳与导航（全局根 / AppBar / BrandMark / NavLink / Tabbar / TabbarItem / SkipLink / SR-only / Wrap / Login）

**族概览**

| # | 组件 | class | 负责的 L3 组 | rb.css 锚点区间 |
| --- | --- | --- | --- | --- |
| 1 | 全局根 GlobalRoot | `:root` `body` `:focus-visible` | root, focus | 12–111 |
| 2 | AppBar | `.appbar` `.appbar__inner` `.appbar__nav` `.appbar__user` | appbar | 121–137 |
| 3 | BrandMark | `.appbar__brand` `.appbar__mark` `.login__mark` `.login__name` | brand | 132–134 / 407–409 |
| 4 | NavLink | `.navlink` | navlink | 138–144 |
| 5 | Tabbar | `.tabbar` | tabbar | 149–154 |
| 6 | TabbarItem | `.tabbar__item` | tabbar | 155–160 |
| 7 | SkipLink | `.skip-link` | skiplink | 115–118 |
| 8 | SR-only | `.sr-only` | sr | 113–114 |
| 9 | Wrap | `.wrap` `.wrap--assistant` | wrap | 164–169 |
| 10 | Login | `.login` `.login__brand` `.login__sub` `.login__foot` | login | 405–411 |

本文件负责 **77 个 L3 token**（root 7 + focus 4 + skiplink 11 + sr 2 + appbar 9 + brand 9 + navlink 10 + tabbar 11 + wrap 7 + login 7），每个 token 恰好出现在下表指定的一个组件的「token 消费表」里：

| L3 组 | token 数 | 唯一消费组件 | 覆盖自查 |
| --- | --- | --- | --- |
| root | 7 | 1 全局根 | 7/7 |
| focus | 4 | 1 全局根 | 4/4 |
| skiplink | 11 | 7 SkipLink | 11/11 |
| sr | 2 | 8 SR-only | 2/2 |
| appbar | 9 | 2 AppBar | 9/9 |
| brand | 9 | 3 BrandMark | 9/9 |
| navlink | 10 | 4 NavLink | 10/10 |
| tabbar | 11 | 5 Tabbar 5 个 + 6 TabbarItem 6 个 | 11/11 |
| wrap | 7 | 9 Wrap | 7/7 |
| login | 7 | 10 Login | 7/7 |
| **合计** | **77** | — | **77/77** |

**断点档位**（取自 `tokens.json` → `breakpoint`，媒体查询内只能写这些字面量）

| 档位 | 值 | 本文件用途 |
| --- | --- | --- |
| base | 0（无媒体查询，最窄按 320px 验收） | 移动底栏 + 底栏占位 + `.wrap` 24/18 内边距 |
| xs | 480 | 本族**未使用**（无任何壳层规则落在 480） |
| sm | 768 | **导航换形态**：`.appbar__nav` 由 `none`→`flex`（rb.css:145–147）、`.tabbar` 由 `grid`→`none`（rb.css:161）、`body` 底栏占位归零（rb.css:104）、`.wrap` 24/18→36/24（rb.css:166） |
| md | 1024 | 本族**未使用** |
| lg | 1200 | 本族**未使用**（`.appbar__inner`/`.wrap` 在 sm 档已达 880px 上限，rgblogic 不再加宽） |
| xl | 1440 | 本族**未使用** |

**导航换形态契约**（与 `b-responsive-spec.md` §3 逐条对应）

| 断点 | `.appbar__nav` | `.tabbar` | 一级入口 | 当前项 |
| --- | --- | --- | --- | --- |
| `< 768`（base–xs） | `display:none`（rb.css:136） | `display:grid`，`repeat(4,1fr)`（rb.css:151） | 4 项：助手 / 课表 / 计划 / 管理 | `aria-current="page"` + 主色 + 加粗（rb.css:160） |
| `≥ 768`（sm 起） | `display:flex`（rb.css:146） | `display:none`（rb.css:161） | 同上 4 项：课程助手 / 我的课表 / 学习计划 / 管理中心 | `aria-current="page"` + 主色 + 底色 + 加粗（rb.css:144） |

- 同一时刻**只有一个**可见导航：两套载体共用同一份 4 项数据源与同一个当前项状态，不允许各自维护高亮。
- 断点严格落在 768：767 仍是底部标签栏、768 起是顶栏内联（`verification.md` §2 实测：767 `tabbar=grid`、768 `tabbar=none`）。
- 标签栏项高 ≥56px（rb.css:156），320px 下每项宽 320÷4=80px，宽高均 ≥44px 触控目标。
- `.tabbar` 与 `.appbar` 同为 `z-index:40`（rb.css:122、150）；`.skip-link` 60（rb.css:115）在最上层。
- **原型的双角色，必须在实现期拆开**：冻结原型里 `.appbar__nav`/`.tabbar` 同时承担两件事——(a) 产品一级导航、(b) 评审页的屏幕跳转（content-spec §0 要求「顶部提供粘性屏幕导航」），所以原型的 `href` 指向的是文档内屏幕锚点。设计系统只承认 (a)：产品期 `href` 指向 4 个一级入口的路由，评审期跳转不进设计系统；不得把「跳到 S01/S07…」当成产品导航的语义。

**导航契约：助手对话不进 URL**（上游取舍，非本规格发明）

| 项 | 结论 | 依据 |
| --- | --- | --- |
| 4 个一级入口 | **有地址**。`.navlink`/`.tabbar__item` 必须是 `<a href>`，可被书签、可被浏览器前进/后退 | 导航语义；`b-responsive-spec.md` §3 |
| 助手会话（对话流 / 过程区 / 未保存草稿正文） | **不进 URL、不进 history、不进 query**。刷新后落在助手的空闲态，而不是恢复会话 | SRS DEC-01「浏览器内存保存当前会话；刷新、退出、关闭页面后不保证恢复」；content-spec S02 边界提示条逐字文案 |
| 导航承诺 | 导航只承诺「切到某个一级入口」，**不承诺**「回到上一轮对话」。不得为此新增会话历史 / 分享链接 / 深链到某一轮 / 跨设备历史入口 | content-spec §3 禁止项（跨设备历史）；SRS DEC-01 |
| 凭据 | href 只写路径，**不带任何令牌或会话参数** | SRS NFR-SEC-002 / §令牌不可出现在 URL |
| 代价 | 用户无法用浏览器后退键在对话轮次之间移动；这是刻意取舍，不是缺陷 | 会话仅内存（DEC-01）+ 令牌不入 URL（NFR-SEC-002） |
| 例外 | 「我的课表」的查询日期、`GET /admin/documents/{id}/text` 的预览等**业务查询**是否进 URL 由各自页面规格决定，本规格不冻结 | — |

**全族硬约束**（10 个组件全部适用）

1. **只消费 L3**。各组件「token 消费表」的 L3 token 列不得出现 L1（`--p-*`）或 L2（`--bg-*`/`--text-*`/`--accent*`/`--border*`/`--focus`/`--layout-*`/`--shell-*`）。上游 token 只在「说明」列以「上游 L1/L2」字样出现，不作为消费方。
2. **状态只写 rb.css 真实存在的**。本族全部交互态穷举如下，此外不得新增：`:focus-visible`（rb.css:110）、`.skip-link:focus`（rb.css:118）、`.navlink:hover`（rb.css:143）、`.navlink[aria-current="page"]`（rb.css:144）、`.tabbar__item[aria-current="page"]`（rb.css:160）。**rb.css 全程无 `:active` 规则；导航项无自己的 `:focus`/`:focus-visible` 规则；全文件无 `transition` 声明**——唯一出现 `transition` 字样的地方是 rb.css:111 在 `prefers-reduced-motion:reduce` 下把它置为 `none!important`。
3. **状态不能只靠颜色**：导航当前态在本族一律 ≥2 重表达（颜色 + 字重，顶栏再加底色）。
4. **文案唯一来源** `directions/shared/content-spec.md`。本文件另引用 4 处「原型锚定串」（逐条标注行号），不得再扩写；禁止 content-spec §3 的禁止项。
5. **禁止引用评审专用外壳 class**：以 `tokens.json` → `meta.scope.review` 枚举的 6 个类名为准，本文件不出现其字面。
6. **断点只允许** 480 / 768 / 1024 / 1200 / 1440；`max-width` 下写法只允许「min-width 档 − 1」（rb.css:351 的 767 是先例）。
7. 每个属性必须给 `rb.css:行号`；「解析值」列必须与 `tokens.flat.json` 逐字一致。
8. 触控目标：`.navlink` ≥44px（rb.css:139）、`.tabbar__item` ≥56px（rb.css:156）、`.skip-link` 由 `12px+2px 边框+文字(17px/1.75≈30px)` 组成 ≈56px 高。
9. 正文文字 ≥4.5:1，非文字 UI/图形 ≥3:1；粘性栏不得遮挡键盘焦点（WCAG 2.2 2.4.11）。

**未决项（本规格无法从 rb.css / tokens.json 断定的东西，不代上游发明）**

| # | 未决项 | 事实 | 处理 |
| --- | --- | --- | --- |
| U1 | `.appbar__nav{gap:6px;margin-left:12px}`（rb.css:136）、`.appbar__user{gap:12px}`（rb.css:137） | tokens.json 的 `appbar` 组 9 个 token **不覆盖**这三处；也无其它组认领 | 不发明 token；Vue 阶段需补 `--appbar-nav-gap` / `--appbar-nav-offset-x` / `--appbar-user-gap` |
| U2 | `.skip-link` 未设 `color` | 文字色来自 rb.css:108 的全局 `a{color:var(--accent-strong)}`，不是 L3 | 无 `--skiplink-fg`；Vue 阶段应显式声明以免受全局 `a` 规则影响 |
| U3 | `.appbar` sticky（56px）与页内锚点跳转 | rb.css 无 `scroll-padding-top`/`scroll-margin-top`；`verification.md` 未验证清单第 6 条同列此项 | **已在阶段 A（实现期）修复**：L3 `root` 组新增 `--root-scroll-offset`，rb.css:84 声明、rb.css:94 由 `html{scroll-padding-top}` 消费（56px + 6px = 62px），不再待补 |
| U4 | `--wrap-pad-y-sm` / `--wrap-pad-x-sm` 名称后缀 `md` | rb.css:166 实际生效于 `min-width:768px`，即 **sm** 档（md=1024） | 命名误导；本规格按 sm 描述，Token 组待更名或加注 |
| U5 | 顶栏短名「校园课程助手」、身份胶囊「管理员」、两个 `nav` 的 `aria-label` | content-spec 未冻结这三串，只在原型 shell.html 出现 | 标为原型锚定串，产品阶段待确认 |
| U6 | 登录路由是否渲染 AppBar/Tabbar | rb.css 无任何「登录屏隐藏外壳」规则；原型把登录屏放在统一外壳内 | 本规格只描述块本身，不新增 class；待产品定 |
| U7 | 品牌位是否可点击 | 原型是 `<span class="appbar__brand">` | 骨架按原型给 `<span>`，若改为链接需同步 `.navlink` 的触控/焦点要求 |
| U8 | `.tabbar` / `body` 的 `env(safe-area-inset-bottom)` | 环境变量无法 token 化（rb.css:102、153） | 保留字面 `env()`，不建 token |
| U9 | 密码「显示/隐藏切换」控件 | content-spec S01 明确要求密码字段**带显示/隐藏切换**，但冻结原型 `parts/login.html:29–33` **没有实现该控件** | **文案已由阶段 A 冻结**：content-spec S01 给出两态逐字文案（遮蔽＝「显示密码」/ 明文＝「隐藏密码」）与 `aria-pressed` 语义；**控件本身仍不在原型内实现**（本轮只冻结契约），实现时按 §7 的按钮要求与 content-spec 逐字消费 |

---

## 1. 全局根 GlobalRoot `:root` `body` `:focus-visible`

### 1. 用途与边界
- `:root` 是 token 声明面（rb.css:12–90）；`body` 是本方向唯一的页面底色 / 字体 / 数字对齐来源（rb.css:95–103）；`:focus-visible` 是全应用唯一的焦点环定义（rb.css:110）。
- **边界**：本组件不定义任何排版元素（`h1`–`h4`/`p`/`a`/`code` 属通用元素规则，rb.css:106–109，不在本文件范围）；不定义骨架以外的组件；不引入暗色模式（`b-responsive-spec.md` §8 已显式否决）。
- 全局 `a{color:var(--accent-strong)}`（rb.css:108）是 SkipLink 的文字色来源，属上游通用规则，本组件不认领其 token。

### 2. 结构（DOM 骨架）
```html
<html lang="zh-CN">                     <!-- 原型 shell.html:2 -->
<head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body>
  <a class="skip-link" href="#main">跳到主要内容</a>   <!-- 第一个可聚焦元素 -->
  <header class="appbar">…</header>
  <main id="main">…</main>
  <nav class="tabbar" aria-label="主导航（窄屏）">…</nav>
</body>
</html>
```

### 3. API 表
| 名称 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `:root` | token 面 | 是 | 由 `tokens.css` 提供；组件 CSS 不在此写属性 |
| `body` | 元素 | 是 | 页面底 / 正文 / 字体 / 数字对齐 / 底栏占位，全部由 L3 提供 |
| `:focus-visible` | 伪类 | 是 | 全局唯一焦点环；不得在组件内改写成 `:focus` |
| `@media (prefers-reduced-motion:reduce)` | 媒体查询 | 是 | 关闭 `transition`/`animation` |
| `<main id="main">` | 跳转目标 | 是 | SkipLink 的 `href` 目标，全页唯一 |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 常态 | `body` | 任意 | 底 `#FAF8F5`、正文 `#1C1917`、17px/1.75、`tabular-nums` | rb.css:95–103 |
| 窄屏底栏占位 | `body`（<768） | 视口 <768px | `padding-bottom:calc(56px + env(safe-area-inset-bottom,0px))` | rb.css:102 |
| ≥sm 取消占位 | `body`（≥768） | 视口 ≥768px | `padding-bottom:0` | rb.css:104 |
| 键盘焦点 | `:focus-visible` | 键盘 Tab 到任一可聚焦元素 | 3px 实线 `#0F4A42`，`outline-offset:2px`，圆角 4px | rb.css:110 |
| 降低动效 | `@media (prefers-reduced-motion:reduce)` | 系统开启减弱动效 | `*{transition:none!important;animation:none!important}` | rb.css:111 |

**本组件没有的状态**：无 `:hover`、**无 `:active`**、无 `:focus`（仅 `:focus-visible`）、无组件级 `transition`（rb.css 只在 rb.css:111 的降级里出现该字样）。鼠标点击不显示焦点环，键盘操作必须显示——这是 `:focus-visible` 的语义，不得改成 `:focus`。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `body{background}` | `--root-bg` | `#FAF8F5` | rb.css:97 页面底；上游 L2 `--bg-page` |
| `body{color}` | `--root-fg` | `#1C1917` | rb.css:98 正文色；对比页面底 16.50:1 |
| `body{font-family}` | `--root-font` | `system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif` | rb.css:99 中文栈；上游 L1 `--p-font-sans` |
| `body{font-size}` | `--root-fs` | `17px` | rb.css:99 窄屏不缩小（≥16px 避免 iOS 聚焦缩放） |
| `body{line-height}` | `--root-lh` | `1.75` | rb.css:99 低密度方向的核心手感 |
| `body{font-variant-numeric}` | `--root-font-variant` | `tabular-nums` | rb.css:100 时间/编号/日期列不跳动 |
| `body{padding-bottom}` | `--root-tabbar-reserve` | `56px` | rb.css:102 为固定标签栏留白、rb.css:104 在 ≥sm 归零；`env()` 部分无法 token 化（U8） |
| `html{scroll-padding-top}` | `--root-scroll-offset` | `62px` | rb.css:84 声明、rb.css:94 消费；顶栏 56px + 一个间距档 6px，使锚点与 skip-link 跳到 `#main`/`#v-Sxx` 时目标不被 sticky 顶栏遮挡（W1） |
| `:focus-visible{outline-width}` | `--focus-outline-w` | `3px` | rb.css:110 ≥2px 可见轮廓 |
| `:focus-visible{outline-color}` | `--focus-outline-color` | `#0F4A42` | rb.css:110 对页面底 9.53:1、对卡片底 10.10:1（均 ≥3:1） |
| `:focus-visible{outline-offset}` | `--focus-outline-offset` | `2px` | rb.css:110 与相邻元素拉开，不被裁切 |
| `:focus-visible{border-radius}` | `--focus-outline-radius` | `4px` | rb.css:110 贴合控件圆角的最小可用值 |

### 6. 无障碍要求
- `html[lang]` 必须为 `zh-CN`（原型 shell.html:2）；`<main id="main">` 全页唯一，是 SkipLink 的目标。
- **焦点环对比度**：`--focus-outline-color` 对上游 `--bg-page` 9.53:1、对上游 `--bg-card` 10.10:1（≥3:1 非文字 UI，tokens.md 判 PASS）。焦点环必须完整可见：`.appbar`/`.tabbar` 的 `z-index:40`、`.skip-link` 的 `z-index:60` 是遮挡判据（rb.css:122、150、115）。
- **粘性栏不遮挡焦点（WCAG 2.2 2.4.11）**：`body` 已为底部标签栏留出 56px（rb.css:102）；顶栏为 `sticky`，`html{scroll-padding-top:var(--root-scroll-offset)}`（rb.css:94，解析值 62px）已补偿锚点与跳转链接的偏移（见 U3）。
- **文字缩放 200%**：`html{-webkit-text-size-adjust:100%}`（rb.css:94），字阶为相对单位，不锁字号。
- **降低动效**：只关闭动画声明，不改布局、不移除内容。
- 本组件不产生可点击目标，不承载可访问名。

### 7. 内容与文案规则
- 本组件无可见文案。
- SkipLink 的 `href="#main"` 必须与 `<main id="main">` 逐字对应（拼错等于跳过链接失效）。

### 8. 响应式行为
| 档位 | 行为 |
| --- | --- |
| base / xs（<768） | `body` 预留 56px + 安全区；正文 17px/1.75 不缩小 |
| sm（≥768） | `body` 占位归零（rb.css:104） |
| md / lg / xl | 本组件无变化（字号不放大，`b-responsive-spec.md` §6） |

- 验收口径：320 / 390 / 768 / 1024 / 1366 / 1440 六宽度 `documentElement.scrollWidth − clientWidth = 0`（`verification.md` §1，六宽度实测 0）。

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `breakpoint`（五档）、`purity_rules`；`b-responsive-spec.md` §1/§6/§7；`verification.md` §1。
- 禁止：把 `:focus-visible` 改成 `:focus` 或 `:focus-visible{outline:none}`；在 reset 里写 `:root{--...:字面值}`；给 `body` 加 `overflow-x:hidden` 掩盖溢出（本项目以「溢出=0」为验收，掩盖会藏掉真实缺陷）；新增暗色模式分支。

---

## 2. AppBar `header.appbar`

### 1. 用途与边界
- 顶栏外壳：粘性定位、卡片底、1px 底边（rb.css:121–125），内部三段式 `.appbar__brand` / `.appbar__nav` / `.appbar__user`（rb.css:132、136、137）。
- **边界**：AppBar 只管外壳与三段槽位；品牌几何属 BrandMark（组件 3）、导航项属 NavLink（组件 4）、右侧身份胶囊是 `.pill`（属 02-actions-status.md）。AppBar 不定义任何二级导航、不定义汉堡菜单（方向 B 显式否决侧栏/抽屉，`b-responsive-spec.md` §2/§8）。
- `≥1200` 前不追加任何右侧控件（`b-responsive-spec.md` §3）。

### 2. 结构（DOM 骨架）
```html
<header class="appbar">                       <!-- 必须挂在 <body> 下才保有 banner 语义 -->
  <div class="appbar__inner">
    <span class="appbar__brand">…</span>       <!-- BrandMark，见组件 3 -->
    <nav class="appbar__nav" aria-label="主导航">
      <a class="navlink" href="…" aria-current="page">…课程助手</a>
      <a class="navlink" href="…">…我的课表</a>
      <a class="navlink" href="…">…学习计划</a>
      <a class="navlink" href="…">…管理中心</a>
    </nav>
    <div class="appbar__user"><span class="pill pill--info">管理员</span></div>
  </div>
</header>
```
> 骨架里的 `href` 是占位：本规格只冻结「4 个一级入口 + 当前项 `aria-current="page"` + 会话内容不进 URL」，不冻结路由字面量（见「导航契约」）。

### 3. API 表
| class | 元素 | 必需 | 变体 | 必需属性 |
| --- | --- | --- | --- | --- |
| `.appbar` | `<header>` | 是 | 无 | 无（landmark 由 `<header>` 语义提供） |
| `.appbar__inner` | `<div>` | 是 | 无 | 无；`max-width:880px;margin:0 auto` 由自身提供 |
| `.appbar__brand` | `<span>` | 是 | 无 | 无（见 U7） |
| `.appbar__nav` | `<nav>` | 是 | 无 | `aria-label`（与标签栏的 `<nav>` 区分） |
| `.appbar__user` | `<div>` | 是 | 无 | 无；`margin-left:auto` 把身份槽推到行尾 |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 常驻 | `.appbar` | 页面滚动 | `position:sticky;top:0;z-index:40`，卡片底，1px 底边 | rb.css:121–125 |
| 导航内联 | `.appbar__nav`（≥768） | 视口 ≥768px | `display:flex` | rb.css:146 |
| 导航隐藏 | `.appbar__nav`（<768） | 视口 <768px | `display:none` | rb.css:136 |

**本组件没有的状态**：无 `:hover`、**无 `:active`**、无 `:focus-visible` 自身规则（焦点环来自全局 rb.css:110）、无 `transition`、无滚动收缩/阴影加深态。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `.appbar{background}` | `--appbar-bg` | `#FFFFFF` | rb.css:123 顶栏底；上游 L2 `--bg-card` |
| `.appbar{border-bottom-color}` | `--appbar-border-color` | `#E7E5E4` | rb.css:124 与页面底 1.26:1，属**分隔线**判定项（见 §6） |
| `.appbar{border-bottom-width}` | `--appbar-border-w` | `1px` | rb.css:124 方向 B 靠 1px 暖色分隔线而非阴影分层 |
| `.appbar__inner{min-height}` | `--appbar-min-h` | `56px` | rb.css:128 顶栏高度；上游 L2 `--shell-appbar-h` |
| `.appbar__inner{padding-block}` | `--appbar-pad-y` | `6px` | rb.css:130 纵向内边距 |
| `.appbar__inner{padding-inline}` | `--appbar-pad-x` | `18px` | rb.css:130、164 与 `.wrap` 窄屏边距同为 18px，保证左右对齐 |
| `.appbar__inner{gap}` | `--appbar-gap` | `18px` | rb.css:129 三段槽位间距（品牌｜导航｜用户区） |
| `.appbar__nav{gap}` | `--appbar-nav-gap` | `6px` | rb.css:136 导航项间距。**收口时补齐**：U1 原本登记为「appbar 组 9 个 token 不覆盖」，Lead 已补入 tokens.json（v1.0.0 收口），此处同步 |
| `.appbar__nav{margin-left}` | `--appbar-nav-offset-x` | `12px` | rb.css:136 把导航区与品牌分开；同属收口补齐项 |
| `.appbar__user{gap}` | `--appbar-user-gap` | `12px` | rb.css:137 用户区图标与身份标签间距；同属收口补齐项 |
| `.appbar{z-index}` | `--appbar-z` | `40` | rb.css:122 与 `.tabbar` 同级、低于 `.skip-link`(60) |
| `.appbar__inner{max-width}` | `--appbar-max-w` | `880px` | rb.css:127 与 `.wrap` 同宽，顶栏内容与正文列对齐 |

### 6. 无障碍要求
- `.appbar` 用 `<header>`：**只有直接挂在 `<body>` 下才是 `banner` landmark**；嵌进 `<main>`/`<section>` 会退化为普通 header，这是骨架里的硬约束。
- 可访问名：landmark 无需命名；内部 `<nav>` 必须有 `aria-label`，且与标签栏的 `<nav aria-label>` **不同名**（两处导航同时存在，同名会造成两个同名 landmark）。原型用「主导航」/「主导航（窄屏）」。
- 键盘：品牌位不可聚焦（原型为 `<span>`，U7）；4 个导航项按 DOM 顺序进入 Tab 序列；不设 `tabindex`、不劫持方向键、不做 roving tabindex（条目仅 4 个，Tab 逐项更可预期）。
- 对比：品牌文字 `#1C1917` on `#FFFFFF` = 17.49:1（≥4.5:1）；分隔线 `#E7E5E4` on `#FFFFFF` = 1.26:1 —— 按 tokens.md §7「卡片边框」的判定逻辑（分隔线不是可交互组件、不承载信息），**不纳入 1.4.11 硬判据**，属判定项。
- 触控：顶栏自身非目标；项内 `.navlink` ≥44px（rb.css:139）。
- 遮挡：`sticky` 顶栏会盖住页内锚点目标，需 `scroll-padding-top`（U3）。

### 7. 内容与文案规则
| 位置 | 逐字文案 | 来源 |
| --- | --- | --- |
| 品牌位 | 「校园课程助手」（短名） | 原型锚定：`design/responsive/shell.html:30`；content-spec 只冻结全名（见 U5） |
| 导航项 1–4 | 课程助手 / 我的课表 / 学习计划 / 管理中心 | 「我的课表」「学习计划」「管理中心」取自 content-spec S07/S09/S10 页面标题；「课程助手」为原型锚定（shell.html:38） |
| 右侧身份胶囊 | 「管理员」 | 原型锚定：shell.html:57（不在 content-spec，U5） |
| `aria-label` | 「主导航」 | 原型锚定：shell.html:33（非可见文案） |

- 禁止：在顶栏加功能入口（选课 / 成绩 / 考勤 / 提醒 / 通知等 content-spec §3 未承诺项）；写死「正在处理」等状态文案（状态行属对话组件）。

### 8. 响应式行为
| 档位 | `.appbar__inner` | `.appbar__nav` | `.appbar__user` |
| --- | --- | --- | --- |
| base / xs（<768） | `padding:6px 18px`，`min-height:56px` | `display:none` | 显示（`margin-left:auto`） |
| sm（≥768） | 同 base（内边距不随断点放大） | `display:flex`，`gap:6px`，`margin-left:12px` | 同 base |
| md / lg / xl | `max-width:880px` 居中，不再加宽 | 同 sm | 同 base |

- 实测：顶栏高度 320/390/768/1366 均 56.7px；320 无内联导航、1366 内联 4 项且「课程助手」带 `aria-current="page"`（`verification.md` §2 与 §逐屏）。
- 中等宽度不会出现控件被挤成竖排：产品导航只有 4 项且 `≥1200` 前不追加右侧控件（`b-responsive-spec.md` §3）。

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `component.appbar`（9 token）；`b-responsive-spec.md` §2/§3；`verification.md` §2。
- 禁止：把顶栏做成 `position:fixed` 而不更新 `body` 占位；在 AppBar 内再嵌一个 `<nav>`（会与 `.appbar__nav` 产生 4 个以上同级 landmark）；给 `.appbar__brand` 直接写品牌几何（属 BrandMark）；引用评审专用 class。

---

## 3. BrandMark `span.appbar__brand` / `.appbar__mark` / `.login__mark` / `.login__name`

### 1. 用途与边界
- 品牌锁定的两个尺寸：**紧凑**（顶栏，26px 方标 + 短名，rb.css:132–134）与**大号**（登录，38px 方标 + 全名 + 由 Login 提供的副标题，rb.css:407–409）。
- **边界**：`--brand-name-fs`(24px) 的消费方是 `.login__name`（rb.css:409），因此全名尺寸归本组件；`--login-sub-*` 对应的 `.login__sub` 属 Login（组件 10）。方标是纯装饰（`aria-hidden="true"`），可访问名一律来自相邻文字。
- 不定义品牌图形本身（内联 SVG 由内容侧提供，见 §7 图形规范）。

### 2. 结构（DOM 骨架）
```html
<!-- 紧凑：AppBar 内（原型 shell.html:23–31） -->
<span class="appbar__brand">
  <span class="appbar__mark" aria-hidden="true">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">…</svg>
  </span>
  校园课程助手
</span>

<!-- 大号：登录块内（原型 parts/login.html:9–20） -->
<div class="login__brand">
  <span class="login__mark" aria-hidden="true">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">…</svg>
  </span>
  <div>
    <div class="login__name">校园课程智能助手</div>
    <div class="login__sub">…</div>   <!-- 副标题属 Login，见组件 10 -->
  </div>
</div>
```

### 3. API 表
| class | 元素 | 必需 | 变体 | 必需属性 |
| --- | --- | --- | --- | --- |
| `.appbar__brand` | `<span>` | 是 | 无 | 文字可访问名即为此处的短名文本 |
| `.appbar__mark` | `<span>` | 是 | 26px / 圆角 7px | `aria-hidden="true"` |
| `.login__mark` | `<span>` | 是 | 38px / 圆角 10px | `aria-hidden="true"` |
| `.login__name` | `<div>` | 是 | 24px/600 | 无 |
| `.login__brand` | `<div>` | 是 | 无 | 容器间距属 Login（`--login-brand-gap`） |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 紧凑 | `.appbar__brand` / `.appbar__mark` | 顶栏内 | 26px 方标、圆角 7px、`gap:6px`、600 字重 | rb.css:132–134 |
| 大号 | `.login__brand` / `.login__mark` / `.login__name` | 登录块内 | 38px 方标、圆角 10px、24px 全名 | rb.css:406–409 |

**本组件没有的状态**：无 `:hover`、**无 `:active`**、无 `[aria-current]`、无 disabled、无 `transition`；两个尺寸是**类名差异**而非状态差异，不得用媒体查询在两者间切换（窄屏/宽屏都用同一尺寸）。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `.appbar__brand{gap}` | `--brand-gap` | `6px` | rb.css:132 方标与短名间距 |
| `.appbar__brand{font-weight}` | `--brand-fw` | `600` | rb.css:132 短名加粗 |
| `.login__name{font-weight}` | `--brand-fw` | `600` | rb.css:409 同一 token 的第二个消费方（全名加粗） |
| `.appbar__mark{width,height}` | `--brand-mark-size` | `26px` | rb.css:133 紧凑方标边长；上游 L1 `--p-size-mark-sm` |
| `.appbar__mark{border-radius}` | `--brand-mark-radius` | `7px` | rb.css:133 紧凑方标圆角 |
| `.appbar__mark{background}`、`.login__mark{background}` | `--brand-mark-bg` | `#14665B` | rb.css:133、407 方标底；上游 L2 `--accent`；对顶栏底 6.82:1 |
| `.appbar__mark{color}`、`.login__mark{color}` | `--brand-mark-fg` | `#E3EDEB` | rb.css:134、408 方标内图形色；对方标底 5.71:1（≥3:1 图形） |
| `.login__mark{width,height}` | `--brand-mark-size-lg` | `38px` | rb.css:407 大号方标边长 |
| `.login__mark{border-radius}` | `--brand-mark-radius-lg` | `10px` | rb.css:407 大号方标圆角；与 `--r-control` 同值 |
| `.login__name{font-size}` | `--brand-name-fs` | `24px` | rb.css:409 全名字号（字阶 24 档，不新增中间字号） |

### 6. 无障碍要求
- 方标必须 `aria-hidden="true"`（原型 shell.html:24、parts/login.html:10）：它是装饰，可访问名来自相邻的短名/全名文本。
- 可访问名来源：`.appbar__brand` 的文本节点「校园课程助手」；`.login__brand` 内为「校园课程智能助手」+ 副标题（副标题也在可访问名里，顺序为全名→副标题，与视觉一致）。
- 图形对比（WCAG 1.4.11 非文字）：方标底 `#14665B` 对顶栏底 `#FFFFFF` = 6.82:1；方标内图形 `#E3EDEB` 对方标底 = 5.71:1。两对均 ≥3:1（本规格按 WCAG 2.x 相对亮度公式实算）。
- 品牌位不是触控目标（U7）：若产品期改为首页链接，必须同时满足 ≥44px 触控与全局 `:focus-visible` 焦点环。
- SVG 规范：`viewBox="0 0 24 24"`、`fill="none"`、`stroke="currentColor"`、`stroke-width="1.75"`、`stroke-linecap/linejoin="round"`；渲染尺寸 16px（顶栏）/20px（登录）；不得用 emoji 充当图标（content-spec §3）。

### 7. 内容与文案规则
| 位置 | 逐字文案 | 来源 |
| --- | --- | --- |
| 顶栏短名 | 校园课程助手 | 原型锚定：shell.html:30（U5） |
| 登录全名 | **校园课程智能助手** | content-spec S01「产品名」逐字 |
| 登录副标题 | 查课表 · 问资料 · 存计划，一个入口 | content-spec S01「副标题」逐字（渲染在 `.login__sub`，属组件 10） |

- 短名与全名**并存但不互相替换**：顶栏受 56px 高度约束用短名，登录页用全名；不得在顶栏自行截断全名或加省略号。
- 禁止自造 slogan / 版本号 / 英文副名。

### 8. 响应式行为
| 档位 | 行为 |
| --- | --- |
| base–xl（全档） | 尺寸与字重**不随断点变化**：紧凑 26px + 短名（`.appbar__brand` 有 `white-space:nowrap`，rb.css:132），大号 38px + 24px 全名 |

- 顶栏短名 `white-space:nowrap`（rb.css:132）保证 320px 下品牌不被折行；因此顶栏不得再加品牌副文本。
- 登录块居中方式由 `.login{max-width:420px;margin:0 auto}` 承担（组件 10），本组件不写宽度。

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `component.brand`（9 token）；tokens.md §10 迁移行（`.appbar__mark` 圆角 7px、`.login__mark` 圆角 10px、`26px/38px` 尺寸）；`content-spec.md` S01。
- 禁止：用 CSS 背景图/字体图标替代内联 SVG（content-spec §0 零外部请求）；给方标加 `role="img"` 再加 `aria-label`（会造出与相邻文字重复的可访问名）；把品牌做成两套断点尺寸。

---

## 4. NavLink `a.navlink`

### 1. 用途与边界
- 顶栏内联导航项（rb.css:138–144）：唯一在 `≥768` 出现的一级导航载体；常态 / `:hover` / 当前页三态。
- **边界**：只管一个 `<a>` 的外观与状态；导航容器是 `.appbar__nav`（组件 2），当前项语义是 `aria-current="page"`（不是 `.is-active` 之类的自造 class）；**不用它承载底部标签栏**（那是 TabbarItem，组件 6，二者状态表达不同）。
- 不定义下拉/二级菜单、不定义徽标计数（PRD 未承诺提醒/推送）。

### 2. 结构（DOM 骨架）
```html
<nav class="appbar__nav" aria-label="主导航">
  <a class="navlink" href="…" aria-current="page">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">…</svg>
    课程助手
  </a>
  <a class="navlink" href="…">
    <svg … aria-hidden="true">…</svg>我的课表
  </a>
</nav>
```
> 图标 18×18；只有当前项写 `aria-current="page"`，其余项**不写**该属性（不要写 `aria-current="false"`）。

### 3. API 表
| class | 元素 | 必需 | 变体 | 必需属性 |
| --- | --- | --- | --- | --- |
| `.navlink` | `<a href>` | 是 | 当前项 = `[aria-current="page"]` | `href`（路径，不带令牌/会话参数） |
| 图标 | `<svg>` | 是 | 18×18 | `aria-hidden="true"` |
| 文字 | 文本节点 | 是 | — | 图标 + 文字共同构成可访问名 |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 常态 | `.navlink` | — | 文字 `#5B544E`、字重 500、无底色 | rb.css:138–142 |
| 指针悬停 | `.navlink:hover` | 鼠标悬停（≥768 可见时） | 底色 `rgba(28,25,23,.04)` | rb.css:143 |
| 当前页 | `.navlink[aria-current="page"]` | 该入口为当前页 | 文字 `#0F4A42` + 底色 `#E3EDEB` + 字重 600（**三重**） | rb.css:144 |
| 键盘焦点 | 全局 `:focus-visible` | Tab 聚焦 | 3px `#0F4A42` 轮廓、偏移 2px | rb.css:110 |

**本组件没有的状态**：**无 `:active`**、无 `.navlink:focus`/`.navlink:focus-visible` 自身规则、无 `transition`、无 disabled、无 visited 自定义、无「未读/角标」态。`aria-current` 只有 `page` 一种取值（原型与 `b-responsive-spec.md` §3 一致）。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `.navlink{min-height}` | `--navlink-min-h` | `44px` | rb.css:139 触控目标下限；上游 L2 `--size-control-min`（= `--tap`） |
| `.navlink{padding-inline}` | `--navlink-pad-x` | `12px` | rb.css:140 左右内边距 |
| `.navlink{gap}` | `--navlink-gap` | `6px` | rb.css:139 图标与文字间距；rb.css:139 此处是裸字面量 `6px`，tokens.md §10 未单列，由本 token 承接 |
| `.navlink{border-radius}` | `--navlink-radius` | `10px` | rb.css:140 悬停/当前底色圆角 |
| `.navlink{color}` | `--navlink-fg` | `#5B544E` | rb.css:141 常态文字；对顶栏底 `#FFFFFF` 7.44:1 |
| `.navlink{font-weight}` | `--navlink-fw` | `500` | rb.css:141 常态字重；上游 L1 `--p-fw-medium` |
| `.navlink:hover{background}` | `--navlink-bg-hover` | `rgba(28,25,23,.04)` | rb.css:143 悬停底色；无 alpha 合成需求（叠在 `#FFFFFF` 上） |
| `.navlink[aria-current="page"]{background}` | `--navlink-current-bg` | `#E3EDEB` | rb.css:144 当前项底色 |
| `.navlink[aria-current="page"]{color}` | `--navlink-current-fg` | `#0F4A42` | rb.css:144 当前项文字；对当前项底 8.46:1（tokens.md 判 PASS） |
| `.navlink[aria-current="page"]{font-weight}` | `--navlink-current-fw` | `600` | rb.css:144 第三重表达，保证状态不只靠颜色 |

### 6. 无障碍要求
- 元素必须是 `<a href>`：只有链接才有「当前页」语义；用 `<button>` + JS 切路由会让 `aria-current` 语义与浏览器能力（新标签打开、复制链接、前进后退）全部丢失。
- 当前项用 `aria-current="page"`；**不要**再用 `aria-pressed`/`aria-selected`/`role="tab"`（这是页面级导航，不是标签面板）。
- 可访问名 = 图标（`aria-hidden="true"`）+ 文字「课程助手 / 我的课表 / 学习计划 / 管理中心」，名称唯一、可区分，不得只靠图标。
- 键盘：Tab 逐项进入；焦点环由全局 `:focus-visible` 提供（rb.css:110），`outline-offset:2px` 使其不被相邻项底色吞掉；无键盘快捷键、无方向键导航。
- 对比：常态 7.44:1（=`--text-secondary` on `--bg-card`，与 tokens.md 的「标签栏常态项/标签栏底」同色对）；当前项 8.46:1；悬停底色上的文字 7.02:1（`#5B544E` on `#FAF8F5`，悬停底色合成后仍 ≥4.5:1）。均 PASS。
- 触控：`min-height:44px`（rb.css:139）；`verification.md` §4 实测 `.navlink` 最小高度 44px，320 下为 0 是因为该元素 `display:none`。
- 状态三重：颜色 + 字重 + 底色（当前项），悬停态只加底色而**不改文字色**，避免与当前项混淆。

### 7. 内容与文案规则
| 位置 | 逐字文案 | 来源 |
| --- | --- | --- |
| 项 1 | 课程助手 | 原型锚定：shell.html:38（S02 标题「你好，我是校园课程助手」的同一产品名） |
| 项 2 | 我的课表 | content-spec S07「页面标题」逐字 |
| 项 3 | 学习计划 | content-spec S09「列表标题」逐字 |
| 项 4 | 管理中心 | content-spec S10 区块名逐字 |

- 四项**顺序固定**（与 `--tabbar-cols` 的 `d`「助手/课表/计划/管理」同序），顶栏与标签栏不得各自排序。
- 顶栏用全称、标签栏用简称（见组件 6 §7），两套文案必须一一对应。
- 禁止：加未承诺入口、加「新」角标、加计数气泡；禁止把项名写成图标以外的自造缩写。

### 8. 响应式行为
| 档位 | 行为 |
| --- | --- |
| base / xs（<768） | 随 `.appbar__nav{display:none}` 整体不参与布局、不进入 Tab 序列（`display:none` 会移出可访问性树，`verification.md` §4「320 下最小高度 0」即此） |
| sm（≥768） | `display:flex` 可见；内边距、字重、触控高度**不变**（组件内部间距不随断点放大，`b-responsive-spec.md` §6） |
| md / lg / xl | 同上，无追加项、无收缩 |

- 断点边界实测：767 隐藏 / 768 可见（`verification.md` §2）。
- 只有 4 项，保证 768×～1200 区间不换行、不竖排（`b-responsive-spec.md` §3）。

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `component.navlink`（10 token）；`b-responsive-spec.md` §3；`verification.md` §2/§4；content-spec S07/S09/S10。
- 禁止：用 `.tabbar__item` 样式冒充顶栏项（两者当前态表达不同：顶栏三重、标签栏两重）；给 `.navlink` 补 `:active`/`transition`（rb.css 无此实现）；把当前项写成 `.is-current` 之类自造 hook 而非 `aria-current`；在同一页同时高亮两项。

---

## 5. Tabbar `nav.tabbar`

### 1. 用途与边界
- 窄屏（<768）唯一的一级导航载体：固定贴底、4 列等分、卡片底 + 1px 顶边（rb.css:149–154、161）。
- **边界**：`.tabbar` 只管容器（网格列数、固定定位、安全区、层级、断点可见性）；单项外观属 TabbarItem（组件 6）。它**不**处理内容遮挡——占位由 `body{padding-bottom}`（组件 1）承担，吸底输入区的避让由 `.composer`（属 03-conversation.md）承担。
- 不引入侧栏/抽屉/汉堡菜单（方向 B 身份，`b-responsive-spec.md` §2/§8）。

### 2. 结构（DOM 骨架）
```html
<nav class="tabbar" aria-label="主导航（窄屏）">
  <a class="tabbar__item" href="…" aria-current="page">…助手</a>
  <a class="tabbar__item" href="…">…课表</a>
  <a class="tabbar__item" href="…">…计划</a>
  <a class="tabbar__item" href="…">…管理</a>
</nav>
```
> `.tabbar` 与 `.appbar` **同时存在于 DOM**：可见性交给媒体查询，不要在 JS 里增删节点（否则键盘与读屏顺序会随视口变化而抖动）。

### 3. API 表
| class | 元素 | 必需 | 变体 | 必需属性 |
| --- | --- | --- | --- | --- |
| `.tabbar` | `<nav>` | 是 | 无 | `aria-label`（与顶栏 `<nav>` 区分） |
| `.tabbar__item` | `<a href>` ×4 | 是 | 当前项 = `[aria-current="page"]` | `href`（路径，不带令牌/会话参数） |
| 列数 | — | 是 | 恒为 4 | 由 `--tabbar-cols` 表述；增删项必须同步改该 token |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 窄屏可见 | `.tabbar`（<768） | 视口 <768px | `position:fixed;bottom:0`，`display:grid`，4 列，卡片底，1px 顶边 | rb.css:149–154 |
| ≥sm 隐藏 | `.tabbar`（≥768） | 视口 ≥768px | `display:none` | rb.css:161 |

**本组件没有的状态**：无 `:hover`、**无 `:active`**、无 `:focus-within`、无 `transition`、无隐藏/展开/收起态（不做「滚动时自动隐藏」）。当前项状态在 TabbarItem 上（组件 6）。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `.tabbar{background}` | `--tabbar-bg` | `#FFFFFF` | rb.css:152 底栏底；上游 L2 `--bg-card` |
| `.tabbar{border-top-color}` | `--tabbar-border-color` | `#E7E5E4` | rb.css:152 与底栏底同色的分隔线（分隔线判定项，同 AppBar §6 逻辑） |
| `.tabbar{border-top-width}` | `--tabbar-border-w` | `1px` | rb.css:152 1px 暖色线分隔，不用阴影 |
| `.tabbar{grid-template-columns}` | `--tabbar-cols` | `4` | rb.css:151 一级入口数 4（助手/课表/计划/管理）；`repeat(4,1fr)` |
| `.tabbar{z-index}` | `--tabbar-z` | `40` | rb.css:150 与 `.appbar` 同级；须低于 `.skip-link`(60)、高于吸底 `.composer`(20) |

### 6. 无障碍要求
- `.tabbar` 用 `<nav>` + `aria-label`；与顶栏 `<nav>` 的 label 必须不同名（原型「主导航」/「主导航（窄屏）」），避免两个同名 landmark。
- 窄屏下顶栏 `<nav>` 为 `display:none`，会移出可访问性树，因此任一时刻只有一个主导航 landmark 可用；但不依赖这一点做命名区分（媒体查询切换不应改变读屏语义）。
- 遮挡与占位：`.tabbar` 是 `position:fixed`，占位由 `body{padding-bottom:var(--root-tabbar-reserve)}`（rb.css:102）承担；320/390 实测底栏顶边 787.3 / 底边 844（= `innerHeight`），未被占位内边距顶出视口（`verification.md` §2）。CSS 声明顺序上 `.tabbar`（rb.css:149）晚于 `body`（rb.css:95）且互不冲突（一个 fixed、一个 padding），无需层级 hack。
- 安全区：`padding-bottom:env(safe-area-inset-bottom,0px)`（rb.css:153）——环境变量无法 token 化（U8），不得替换成固定值。
- 触控：容器非目标，项 ≥56px（见组件 6 §6）。
- 键盘：`<a>` 原生可聚焦，Tab 顺序 = DOM 顺序 = 视觉顺序（左→右）；不得用 CSS `order` 改变视觉顺序而造成焦点顺序与视觉不一致。
- 对比：底栏底 `#FFFFFF` 与项文字/图标见组件 6；容器无文字。

### 7. 内容与文案规则
| 位置 | 逐字文案 | 来源 |
| --- | --- | --- |
| `aria-label` | 主导航（窄屏） | 原型锚定：shell.html:78（非可见文案） |
| 4 个项名 | 助手 / 课表 / 计划 / 管理 | `tokens.json` → `--tabbar-cols` 的 `d` 字面给出「助手/课表/计划/管理」；原型 shell.html:83、88、93、98 同串 |

- 标签栏用**简称**（2–3 字），与顶栏全称一一对应（课程助手↔助手、我的课表↔课表、学习计划↔计划、管理中心↔管理）；不得在标签栏写长名导致 13px 下折行。
- 禁止第 5 项（底部导航 ≤5 项且本项目一级入口恰为 4 项）；禁止角标/红点/未读数（PRD 未承诺提醒）。

### 8. 响应式行为
| 档位 | 行为 |
| --- | --- |
| base / xs（<768） | `display:grid`，4 列等分，固定贴底；`body` 预留 56px + 安全区；320 下每项宽 80px |
| sm（≥768） | `display:none`；`body` 占位归零（rb.css:104）；导航改由 `.appbar__nav` 承担 |
| md / lg / xl | 同上（不显示） |

- 断点严格 768：767 `grid` / 768 `none`（`verification.md` §2）。`xs`(480) 档对底栏无影响（仍显示）。
- `.composer` 的 `bottom` 也以 56px 标签栏为基准（rb.css:267），与 `body`/`.tabbar` 三者共用同一个 `--shell-tabbar-h` 语义值，改高度必须三处同步。

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `component.tabbar`（本组件 5 token + 组件 6 的 6 token）；`b-responsive-spec.md` §2/§3/§7；`verification.md` §2/§4。
- **导航与 URL 的取舍**（与组件 2 共用同一契约）：4 个一级入口有地址；助手会话不进 URL/history/query（SRS DEC-01），导航不得承诺「回到上一轮对话」；href 不带令牌（SRS NFR-SEC-002）。详见文首「导航契约」。
- 禁止：用 `position:sticky` 替代 `fixed`（吸底输入区会覆盖）；增删列数而不改 `--tabbar-cols` 与 `repeat(4,1fr)`；在窄屏把顶栏与底栏同时显示（会出现两套主导航）；为底栏加自动隐藏动效（rb.css 无实现，且 reduced-motion 下无意义）。

---

## 6. TabbarItem `a.tabbar__item`

### 1. 用途与边界
- 底部标签栏的单项：图标在上、文字在下、列内居中（rb.css:155–159），当前项用主色 + 加粗（rb.css:160）。
- **边界**：单项外观与「当前项」语义在本组件；容器列数与定位属 Tabbar（组件 5）。**不复用 `.navlink`**：两者当前态表达不同（顶栏三重含底色，标签栏只有颜色 + 字重，rb.css:144 vs 160），且标签栏是纵排图标+文字、顶栏是横排。
- 不定义为按钮（不用 `<button>`）、不承载徽标。

### 2. 结构（DOM 骨架）
```html
<a class="tabbar__item" href="…" aria-current="page">
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">…</svg>
  助手
</a>
```
> 图标 22×22（比顶栏 18×18 大一档，补偿无底色的当前态表达）；文字 13px 单行。

### 3. API 表
| class | 元素 | 必需 | 变体 | 必需属性 |
| --- | --- | --- | --- | --- |
| `.tabbar__item` | `<a href>` | 是 | 当前项 = `[aria-current="page"]` | `href` |
| 图标 | `<svg>` 22×22 | 是 | — | `aria-hidden="true"` |
| 文字 | 文本节点 | 是 | — | 图标 + 文字构成可访问名 |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 常态 | `.tabbar__item` | — | 图标与文字 `#5B544E`、13px、无字重强调 | rb.css:155–159 |
| 当前页 | `.tabbar__item[aria-current="page"]` | 该入口为当前页 | 文字与图标 `#0F4A42` + 字重 600（**两重**） | rb.css:160 |
| 键盘焦点 | 全局 `:focus-visible` | Tab 聚焦 | 3px `#0F4A42` 轮廓、偏移 2px | rb.css:110 |

**本组件没有的状态**：**无 `:hover`**（触屏为主，rb.css 未定义）、**无 `:active`**、无自身 `:focus`/`:focus-visible` 规则、无 `transition`、无 disabled、无「选中 + 未读」组合态。**当前项不得只靠颜色**：颜色 + 字重两重，图标复用同一 SVG（不换实心图标，因为 rb.css 未定义第二套图标规则）。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `.tabbar__item{min-height}` | `--tabbar-item-min-h` | `56px` | rb.css:156 项高 ≥56px；上游 L2 `--shell-tabbar-h` |
| `.tabbar__item{gap}` | `--tabbar-item-gap` | `2px` | rb.css:157 图标与文字间距；rb.css:157 为裸字面量 `2px` |
| `.tabbar__item{font-size}` | `--tabbar-item-fs` | `13px` | rb.css:158 项文字 13px（字阶最小档） |
| `.tabbar__item{color}` | `--tabbar-item-fg` | `#5B544E` | rb.css:158 常态图标+文字；对底栏底 7.44:1 |
| `.tabbar__item[aria-current="page"]{color}` | `--tabbar-item-current-fg` | `#0F4A42` | rb.css:160 当前项色；对底栏底 10.10:1 |
| `.tabbar__item[aria-current="page"]{font-weight}` | `--tabbar-item-current-fw` | `600` | rb.css:160 第二重表达 |

### 6. 无障碍要求
- `<a href>` + `aria-current="page"`（与顶栏 NavLink 同一约定）；不要 `role="tab"`、不要 `aria-selected`。
- 可访问名 = 22×22 装饰图标（`aria-hidden="true"`）+ 2 字简称；四个名称唯一。
- 触控目标：高度 56px（rb.css:156，`verification.md` §4 实测 56.0）；宽度 = 视口 ÷ 4（320px 下 80px），两个方向均 ≥44px。
- 对比：常态 7.44:1、当前项 10.10:1（tokens.md 判 PASS）。图标与文字同色同源（`color`），不额外做图标对比判定。
- 键盘：Tab 顺序 = DOM 顺序 = 视觉左→右；`.tabbar` 是 `fixed`，聚焦项的焦点环可能贴近视口底边——`outline-offset:2px` + 56px 项高保证轮廓完整可见（不裁切）。
- 状态不只靠颜色：当前项 = 主色 + 600 字重；与顶栏当前项相比少一层底色，这是 56px 高度约束下的取舍，**不允许**为了凑「三重」而在此新增 rb.css 未定义的底色。

### 7. 内容与文案规则
| 位置 | 逐字文案 | 来源 |
| --- | --- | --- |
| 4 个项名 | 助手 / 课表 / 计划 / 管理 | `tokens.json` → `--tabbar-cols` 的 `d`；原型 shell.html:83/88/93/98 |

- 每项 **2–3 个汉字**、单行不折行（13px 下 80px 宽可容 4 字以上）；不得加副标题、不得加数字角标。
- 与顶栏全称的对应关系必须一对一（见组件 5 §7）。

### 8. 响应式行为
| 档位 | 行为 |
| --- | --- |
| base / xs（<768） | 每项 56px 高、`flex-direction:column`、`gap:2px`；宽 = 视口/4 |
| sm（≥768） | 随 `.tabbar{display:none}` 隐藏，不进入布局与 Tab 序列（`verification.md` §4 记 768 为 `display:none` 不计入触控统计） |
| md / lg / xl | 隐藏 |

- 单项样式**不随断点变化**（无 480/768 的项级媒体查询），保证 320–767 全区间手感一致。

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `component.tabbar` 中的 `--tabbar-item-*` 6 个；`b-responsive-spec.md` §2/§6；`verification.md` §2/§4。
- 禁止：给标签栏项补 `:hover`/`:active`/`transition`（rb.css 无实现）；用 `order`/`grid-area` 改视觉顺序；用图标替换文字（可访问名会退化）；把两项同时设为 `aria-current="page"`。

---

## 7. SkipLink `a.skip-link`

### 1. 用途与边界
- 键盘用户的第一个焦点停靠点：默认移出视口，`:focus` 时落到左上角可见位置（rb.css:115–118）；它是 WCAG 2.4.1「绕过区块」的实现。
- **边界**：只提供「跳到主要内容」一个跳转；不实现页内锚点目录（评审期的屏幕导航不属于产品 UI，本项目已排除评审外壳）。不负责滚动偏移（见 U3）。
- 它必须能跳过 `.appbar` 的 4 个导航项。

### 2. 结构（DOM 骨架）
```html
<body>
  <a class="skip-link" href="#main">跳到主要内容</a>
  <header class="appbar">…</header>
  <main id="main">…</main>
```
> 必须是 `<body>` 内**第一个可聚焦元素**；目标 `<main id="main">` 的 `id` 必须逐字匹配。

### 3. API 表
| class | 元素 | 必需 | 变体 | 必需属性 |
| --- | --- | --- | --- | --- |
| `.skip-link` | `<a href="#main">` | 是（每页一个） | 无 | `href` 指向唯一 `<main>`；文字可访问名 |
| `<main id="main">` | `<main>` | 是 | 无 | `id="main"`，可用 `tabindex="-1"` 以承接程序化焦点（rb.css 未定义，属实现补充） |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 隐藏（默认） | `.skip-link` | 未聚焦 | `top:-100px`，仍在 DOM 与 Tab 序列中 | rb.css:115 |
| 聚焦可见 | `.skip-link:focus` | 键盘 Tab 到它 / 程序化聚焦 | `top:12px`，左上角 12px 处，白底、2px 焦点色边框、圆角 10px、600 字重 | rb.css:118、115–117 |

**本组件没有的状态**：**无 `:hover`**、**无 `:active`**、无 `:focus-visible`（用的是 `:focus`，见 §9 说明）、无 `transition`、无 visited 自定义。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `.skip-link{background}` | `--skiplink-bg` | `#FFFFFF` | rb.css:116 可见态底色；上游 L2 `--bg-card` |
| `.skip-link{border-color}` | `--skiplink-border-color` | `#0F4A42` | rb.css:116 与前程色一致，2px；对页面底 9.53:1 |
| `.skip-link{border-width}` | `--skiplink-border-w` | `2px` | rb.css:116 ≥2px 可见边界 |
| `.skip-link{border-radius}` | `--skiplink-radius` | `10px` | rb.css:116 与 `--r-control` 同值 |
| `.skip-link{padding-block}` | `--skiplink-pad-y` | `12px` | rb.css:117 纵向内边距；与 17px/1.75 文字合计 ≈56px 高 |
| `.skip-link{padding-inline}` | `--skiplink-pad-x` | `18px` | rb.css:117 横向内边距 |
| `.skip-link{left}` | `--skiplink-offset-x` | `12px` | rb.css:115 可见态左偏移（隐藏态同为 `left:12px`） |
| `.skip-link:focus{top}` | `--skiplink-offset-y-visible` | `12px` | rb.css:118 可见态上偏移 |
| `.skip-link{top}` | `--skiplink-offset-y-hidden` | `-100px` | rb.css:115 隐藏态屏外偏移；上游 L1 `--p-offset-offscreen` |
| `.skip-link{z-index}` | `--skiplink-z` | `60` | rb.css:115 高于 `.appbar`/`.tabbar`(40)，保证不被粘性栏遮挡 |
| `.skip-link{font-weight}` | `--skiplink-fw` | `600` | rb.css:117 加粗以在页面内容上可辨 |

> 文字色**无 L3 token**：`.skip-link` 未设 `color`，实际取 rb.css:108 的全局 `a{color:var(--accent-strong)}` = `#0F4A42`（对白底 10.10:1）。见 U2。

### 6. 无障碍要求
- 可访问名 = 文字「跳到主要内容」；`href="#main"` 必须指向存在的 `id`，否则点击只是跳到页顶而**不会移动焦点**。
- 键盘行为：Tab 一次即可聚焦；Enter 触发跳转后，焦点应落到 `<main>`（建议给 `<main id="main" tabindex="-1">`，rb.css 未定义，需实现侧补）；跳转后下一站是主内容第一个可聚焦元素，而不是又回到 `.appbar`。
- 可见性：`:focus`（不是 `:focus-visible`，rb.css:118）——鼠标点击也会显示，这是刻意选择：跳转链接只要获得焦点就必须可见，避免「用鼠标点了但看不到它」。
- 遮挡：`z-index:60`（rb.css:115）高于顶栏 40；`top:12px` 落在顶栏（56px）下方区域之上，可见态不会被顶栏盖住。
- 对比：文字 `#0F4A42` on 白底 10.10:1；边框 `#0F4A42` vs 页面底 9.53:1（均 ≥3:1/4.5:1）。
- 触控：由 12px 内边距 + 17px/1.75 文字 + 2px 边框组成，高约 56px，≥44px。

### 7. 内容与文案规则
| 位置 | 逐字文案 | 来源 |
| --- | --- | --- |
| 链接文字 | 跳到主要内容 | 原型锚定：`design/responsive/shell.html:19`（**不在 content-spec 中**，见 U5；不得改写为「跳到主内容」「跳过导航」等变体） |

- 只有一条跳转链接；目标必须是 `#main`，不指向具体屏幕块。

### 8. 响应式行为
| 档位 | 行为 |
| --- | --- |
| base–xl（全档） | 无任何媒体查询：隐藏/可见两种位置在所有断点一致；`left:12px` 在 320px 下仍完整可见（宽约「跳到主要内容」5 字 ×17px + 36px 内边距 ≈ 121px） |

- 不因窄屏改为全宽、不因宽屏改为居中。

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `component.skiplink`（11 token）；`b-responsive-spec.md` §7「跳转链接 `.skip-link` 在聚焦时可见」；tokens.md §10（屏外偏移 `-100px`、z-index 60）。
- 禁止：用 `display:none`/`visibility:hidden`/`clip-path` 隐藏（会移出 Tab 序列，等于没有跳转链接）；改成 `:focus-visible`（鼠标点击时会不可见）；把 `top` 改成 `0`（会被粘性顶栏遮住）；写成 `.skip-link{opacity:0}` 之类依赖动画的显示方式（reduced-motion 下不可靠）。

---

## 8. 屏幕阅读器专用 SR-only `span.sr-only` / `.sr-only`

### 1. 用途与边界
- 视觉隐藏但保留在读屏树中的工具类（rb.css:113–114）：用于给纯视觉结构补齐可访问名与标题层级（页面 `<h1>`、区块标题、checkbox 型折叠控件的 label）。
- **边界**：纯工具类，不含文案、不含布局意图；**不是**用来隐藏可见内容的（可见内容用真隐藏属性）。它保留元素在可访问性树内，因此不得用在「必须对所有人隐藏」的场景。
- 文本仍参与复制/搜索/读屏，视觉上被裁成 1×1 并绝对定位。

### 2. 结构（DOM 骨架）
```html
<!-- 页面唯一 h1：视觉上由顶栏品牌承担，语义上必须有 h1 -->
<main id="main">
  <h1 class="sr-only">校园课程智能助手</h1>
  …
</main>

<!-- 折叠控件：checkbox 视觉隐藏，label 承载可访问名 -->
<input type="checkbox" class="sr-only" id="steps-toggle">
<label class="steps__summary" for="steps-toggle">…</label>
```
> 折叠控件用法已在原型 parts/assistant.html:118 等处验证；`<label for>` 的关联不依赖视觉隐藏。

### 3. API 表
| class | 元素 | 必需 | 变体 | 必需属性 |
| --- | --- | --- | --- | --- |
| `.sr-only` | 任意 | 是 | 无 | 元素本身的可访问语义/文案必须完整（隐藏的是视觉，不是语义） |
| 典型用法 A | `<h1>` | 是 | — | 提供页面唯一的 h1（`verification.md` §未验证/修复建议同款做法） |
| 典型用法 B | `<input type="checkbox">` | 是 | — | 必须配 `id` + `<label for>` |
| 典型用法 C | 区块 `<h2>` | 视情况 | — | 卡片化区块在视觉上没标题时，用 sr-only h2 维持层级 |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 恒隐藏 | `.sr-only` | 任意（含聚焦） | `1×1`、`margin:-1px`、`padding:0`、`overflow:hidden`、`clip:rect(0 0 0 0)`、`white-space:nowrap`、`border:0` | rb.css:113–114 |

**本组件没有的状态**：无 `:hover`、**无 `:active`**、无 `:focus`/`:focus-visible` 覆盖、无 `transition`、无断点变化。

> **注意**：`.sr-only` 元素**仍是可聚焦的**——若把它用在 `<input>`/`<a>`/`<button>` 上，键盘 Tab 会聚焦到 1×1 的元素，焦点环几乎不可见（rb.css 无针对此的补偿）。因此它只用于**不可聚焦**元素（`<h1>`/`<h2>`/`<span>`）或**与可见 label 配对的 checkbox/radio**（焦点由 label 呈现）。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `.sr-only{width,height}` | `--sr-size` | `1px` | rb.css:113 1×1 内部盒；上游 L1 `--p-sr-clip-size` |
| `.sr-only{margin}` | `--sr-offset` | `-1px` | rb.css:113 负外边距抵消 1px 占位，避免产生多余空隙 |

### 6. 无障碍要求
- 隐藏方式为 `clip:rect(0 0 0 0)` + `1×1`（rb.css:114），**保留在读屏树**：不得替换为 `display:none`/`visibility:hidden`/`aria-hidden="true"`（那会连语义一起删掉）。
- 可访问名/标题层级来源：sr-only 内的文本本身。页面必须有唯一 `<h1>`，其后标题不得跳级（content-spec §1「标题层级不跳级」）。
- 聚焦风险：见 §4 注意；用于可聚焦元素时必须同时提供可见焦点指示（rb.css 未定义 → 本规格禁止该用法）。
- 长文本：`white-space:nowrap`（rb.css:114）意味着 sr-only 文本不会换行；因此只放短标题/短标签，不放段落（长段落放进 sr-only 会在读屏里正常朗读，但无法被视觉用户选中复制——本项目未要求）。
- 不参与布局：1×1 + 负 margin 使其不产生空隙，不会破坏 320px 下的零横向溢出验收。

### 7. 内容与文案规则
| 用法 | 逐字文案 | 来源 |
| --- | --- | --- |
| 页面 h1 | 校园课程智能助手 | content-spec S01「产品名」逐字（**产品期不带任何评审后缀**） |
| 区块 h2 | 取该屏 content-spec 标题，如「我的课表」 | content-spec S07 等各屏标题逐字 |
| 折叠控件 label | 取该控件可见文案 | content-spec 对应屏逐字 |

- 禁止在 sr-only 里写与可见文本不同的第二套说法（读屏与视觉用户会得到不同信息）；禁止用 sr-only 塞关键词。
- 禁止使用评审期出现过的「· 方向 B 响应式原型」这类后缀——那是评审上下文，不进产品。

### 8. 响应式行为
| 档位 | 行为 |
| --- | --- |
| base–xl（全档） | 无媒体查询、无断点差异；`1×1` 与 `-1px` 在所有宽度一致 |

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `component.sr`（2 token）；`verification.md` §未验证清单的 h1 修复建议（用 `.sr-only` 提供不改变视觉的 `<h1>`）；content-spec §1「语义结构」。
- 禁止：`display:none` 式隐藏；用 `.sr-only` 藏可见内容（如把按钮文字藏起来只留图标）；给 `.sr-only` 加 `transition`/`:hover`；在 `.sr-only` 里放 emoji。

---

## 9. Wrap `div.wrap` / `.wrap--assistant`

### 1. 用途与边界
- 内容列容器：`max-width:880px` 居中 + 响应式内边距（rb.css:164、166）；`.wrap--assistant` 把列宽收到 720px（rb.css:165）。
- **嵌套规则（本组最易错的点）**：助手片段自带 `.wrap`，与外壳的 `.wrap` 嵌套时必须只保留一层左右内边距（rb.css:169）——内层 `padding-left/right` 归零，但**仍保留自己的 `max-width`**，从而既避免双重缩进、又维持 720px 助手列并居中。
- **边界**：只管列宽与内边距；不做栅格、不做分栏（方向 B 单列，`b-responsive-spec.md` §2）。正文 measure（`68ch`，rb.css:170）属 `.prose`，不在本组。

### 2. 结构（DOM 骨架）
```html
<main id="main">
  <div class="wrap">                    <!-- 外壳列：880px -->
    <div class="wrap wrap--assistant">  <!-- 助手片段自带 wrap：内层左右内边距归零，仍限 720px -->
      …
    </div>
  </div>
</main>
```
> 也可单层使用：只有助手页时直接 `<div class="wrap wrap--assistant">`（不做嵌套，内边距保持 18/24px）。

### 3. API 表
| class | 元素 | 必需 | 变体 | 必需属性 |
| --- | --- | --- | --- | --- |
| `.wrap` | `<div>` | 是（每页至少一个） | 无 | 无（宽度/内边距由自身提供） |
| `.wrap--assistant` | 与 `.wrap` 同时用 | 助手页必需 | 720px 列 | 无 |
| `.wrap .wrap` | 后代选择器 | 嵌套时（助手片段） | 内层左右内边距 0 | 内层须**同时**带 `.wrap` 与自身 max-width 语义 |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 常态 | `.wrap` | — | `max-width:880px;margin:0 auto;padding:24px 18px` | rb.css:164 |
| 助手窄列变体 | `.wrap--assistant` | 助手页 | `max-width:720px`（内边距同上） | rb.css:165 |
| ≥sm 加宽内边距 | `.wrap`（≥768） | 视口 ≥768px | `padding:36px 24px` | rb.css:166 |
| 嵌套内层 | `.wrap .wrap` | 两层 `.wrap` 相套 | 内层 `padding-left/right:0`（保留 max-width 与 `margin:auto`） | rb.css:169 |

**本组件没有的状态**：无 `:hover`、**无 `:active`**、无 `:focus`、无 `transition`、无 disabled。两个 class 差异是**变体**不是状态。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `.wrap{max-width}` | `--wrap-max` | `880px` | rb.css:164 内容列上限；上游 L2 `--layout-content-max`；与 `.appbar__inner` 同宽以对齐 |
| `.wrap{padding-block}` | `--wrap-pad-y` | `24px` | rb.css:164 窄屏纵向节奏（`--sp-4`） |
| `.wrap{padding-inline}` | `--wrap-pad-x` | `18px` | rb.css:164 窄屏左右边距（`--sp-3`），与窄屏顶栏 18px 对齐 |
| `.wrap{padding-block}`（≥768） | `--wrap-pad-y-sm` | `36px` | rb.css:166 sm 档纵向节奏（`--sp-6`）；**token 名后缀 md 与实现档位 sm 不一致，见 U4** |
| `.wrap{padding-inline}`（≥768） | `--wrap-pad-x-sm` | `24px` | rb.css:166 sm 档左右边距 |
| `.wrap--assistant{max-width}` | `--wrap-assistant-max` | `720px` | rb.css:165 助手列上限；上游 L2 `--layout-assistant-max` |
| `.wrap .wrap{padding-inline}` | `--wrap-inner-pad-x` | `0` | rb.css:169 **嵌套坑**：内层左右内边距归零避免双重缩进；内层 `max-width:720px` 与 `margin:0 auto` **保留**，所以 720px 助手列仍居中成立 |

### 6. 无障碍要求
- 纯布局容器，无 `role`、无 `tabindex`、不承载可访问名。
- 不得使用 `order` 改变 DOM 顺序：视觉顺序必须等于 DOM 顺序（键盘 Tab 顺序依赖 DOM）。
- 阅读顺序：`.wrap` 是单列，天然满足「视觉顺序 = 阅读顺序」；`b-responsive-spec.md` §2 已否决侧栏与左右分栏。
- 320px 下的零横向溢出：内边距 18px + 内容自身换行策略共同保证；`.wrap` 内不得放固定宽度 > 320−36 的元素（`verification.md` §1 六宽度溢出为 0）。
- 焦点可见性不受影响（容器不可聚焦）。

### 7. 内容与文案规则
- 本组件无可见文案。
- 结构约束：每页至少一个 `.wrap`；助手页的内层 `.wrap--assistant` 必须保持「自带 wrap」的形态（片段可独立查看是上游需求，rb.css:167–168 注释）。

### 8. 响应式行为
| 档位 | `.wrap` | `.wrap--assistant` |
| --- | --- | --- |
| base / xs（<768） | `max-width:880px`（实际受视口限制）、`padding:24px 18px` | 同左但 `max-width:720px` |
| sm（≥768） | `padding:36px 24px`（rb.css:166）；列宽仍 880px 上限 | 内边距同 `.wrap`，列宽 720px |
| md / lg / xl | 与 sm 相同；`≥1200` 后不再加宽（`b-responsive-spec.md` §1「达到内容最大宽，不再变宽」） | 同左 |

- 断点依据：页面外边距 18→24px、纵向节奏 24→36px 都发生在 **sm(768)**，与 `b-responsive-spec.md` §2 布局规则表逐条一致；组件内部间距不随断点放大。
- 实测：1366 下内容居中限宽 ~880px、两侧留白正常（`verification.md` §逐屏 v1366）。

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `component.wrap`（7 token）；`b-responsive-spec.md` §2/§6；rb.css:167–169 的嵌套注释；`verification.md` §1/§逐屏。
- 禁止：给内层 `.wrap` 写 `padding:0`（会一并清掉纵向内边距，正确写法只清左右，rb.css:169）；给内层写 `max-width:none`（720px 助手列会失效）；用 `.wrap` 做两栏；用负 margin 抵消嵌套内边距；在 `.wrap` 上写死 `width`。

---

## 10. Login `div.login`

### 1. 用途与边界
- 登录页的主列：`max-width:420px` 居中、纵向 18px 间距（rb.css:405），内含品牌锁定（`.login__brand`，品牌几何见组件 3）、表单卡（`.card`，属 04-forms-data.md）、页脚提示（`.login__foot`）。
- **边界**：Login 只管**块的宽度、间距、品牌行间距、副标题与页脚排版**；字段/错误/按钮/禁用态分别属 `.field`/`.notice`/`.btn` 各组件规格（04、02）。本组件声明三种业务态**如何组合**，不重新定义子组件外观。
- 登录屏允许的表单列数为 1（`.login` 内不用 `.form-grid--2`）。

### 2. 结构（DOM 骨架）
```html
<div class="login">
  <div class="login__brand">
    <span class="login__mark" aria-hidden="true">…</span>   <!-- BrandMark -->
    <div>
      <div class="login__name">校园课程智能助手</div>          <!-- BrandMark（24px） -->
      <div class="login__sub">查课表 · 问资料 · 存计划，一个入口</div>
    </div>
  </div>

  <div class="card"><div class="card__body stack">
    <div class="field">
      <label class="field__label" for="login-account">账号 <span class="field__req">必填</span></label>
      <input class="input" id="login-account" name="account" type="text" autocomplete="username">
    </div>
    <div class="field">
      <label class="field__label" for="login-password">密码 <span class="field__req">必填</span></label>
      <div class="row">
        <input class="input" id="login-password" name="password" type="password" autocomplete="current-password">
        <button class="btn btn--ghost btn--sm" type="button"
                aria-pressed="false" aria-controls="login-password" aria-label="…">…</button>
        <!-- 显示/隐藏切换：content-spec S01 要求，冻结原型未实现；文案待产品补（U9） -->
      </div>
    </div>
    <button class="btn btn--primary btn--block" type="submit">登录</button>
  </div></div>

  <p class="login__foot">登录会话有效期 2 小时，到期后需要重新登录。</p>
</div>
```

### 3. API 表
| class | 元素 | 必需 | 变体 | 必需属性 |
| --- | --- | --- | --- | --- |
| `.login` | `<div>` | 是 | 无（三态共用同一容器） | 无 |
| `.login__brand` | `<div>` | 是 | 无 | 内部含 BrandMark（组件 3） |
| `.login__sub` | `<div>` | 是 | 无 | 文案取自 content-spec S01 |
| `.login__foot` | `<p>` | 是 | 无 | 文案取自 content-spec S01 |
| 表单 | `.card` + `.field` + `.btn--block` | 是 | 三态见 §4 | 每个控件可见 `<label for>`；必填标「必填」 |
| 密码切换 | `.row` + `.btn.btn--ghost.btn--sm` | 是（S01 要求） | 明文 / 密文两态用 `aria-pressed` 表达 | 复用 02（`.btn`）与 04（`.row`/`.field`）的既有 class，**本规格不新增 class**；文案待补（U9） |

### 4. 状态矩阵
| 状态 | 选择器 | 触发 | 视觉表现 | 锚点 |
| --- | --- | --- | --- | --- |
| 常态 | `.login` | 未提交 | 420px 居中列、纵向 18px 间距 | rb.css:405 |
| 凭据错误 | `.login` 内的 `.notice--danger` + `.field--invalid` | 登录失败 | 危险色提示块（图标+文字+颜色）+ 两组字段危险边 + 3px 危险外描边；账号保留、密码清空、焦点回密码框 | rb.css:228、327–328（`.notice`/`.field` 属 02/04 规格） |
| 账号不可用 | `.login` 内的 `.notice--danger` + `[disabled]` 控件 | 账号被禁用 | 同款危险提示块（不同文案）+ 整组降透明度 `opacity:.5` | rb.css:228、326、205 |

**本组件（`.login*` 自身）没有的状态**：无 `:hover`、**无 `:active`**、无 `:focus`、无 `transition`、无 disabled、无断点态。三种业务态**不是 `.login` 的类名变体**——`rb.css` 没有 `.login--error` 之类规则，态差异全部由子组件承担（这也是本规格不新增变体的原因）。

### 5. token 消费表
| 属性 | L3 token | 解析值 | 说明 |
| --- | --- | --- | --- |
| `.login{max-width}` | `--login-max-w` | `420px` | rb.css:405 窄卡片居中；上游 L1 `--p-size-login-max`；窄屏满宽（320−36=284px 可视宽） |
| `.login{gap}` | `--login-gap` | `18px` | rb.css:405 品牌行 / 卡片 / 页脚之间的纵向节奏（`--sp-3`） |
| `.login__brand{gap}` | `--login-brand-gap` | `12px` | rb.css:406 大号方标与文字列的间距（`--sp-2`），比顶栏品牌间距大一档 |
| `.login__sub{font-size}` | `--login-sub-fs` | `15px` | rb.css:410 副标题 15px（字阶第二档） |
| `.login__sub{color}` | `--login-sub-fg` | `#5B544E` | rb.css:410 副标题色；对页面底 7.02:1 |
| `.login__foot{font-size}` | `--login-foot-fs` | `13px` | rb.css:411 页脚提示 13px |
| `.login__foot{color}` | `--login-foot-fg` | `#6B6259` | rb.css:411 页脚色；对页面底 5.63:1（仍 ≥4.5:1） |

> `.login__brand` 内的 `.login__mark`（38px/圆角 10px/底色/前景色）与 `.login__name`（24px/600）的 token 归 BrandMark（组件 3），本表不重复认领；`.login__sub` 的容器（`<div>` 包裹）与 `.login__name` 同层。

### 6. 无障碍要求
- 结构：`<form>` 包裹字段（骨架中省略 `<form>` 仅为聚焦本组件；实现必须用 `<form>` + `type="submit"`），每个控件有可见 `<label for>`，必填带文字「必填」（不用仅符号）。
- 错误：统一文案的提示块用 `role="alert"`（原型 parts/login.html:45/85），并把焦点移到**密码字段**（原型行为：账号保留、密码清空）。字段级错误用 `aria-describedby` 指向错误文本并加 `aria-invalid="true"`（原型 parts/login.html:64）——这两个属性属 `.field` 组件（04），本组件只声明组合顺序。
- 可访问名：控件名来自 `<label>`；品牌方标 `aria-hidden="true"`，可访问名来自「校园课程智能助手」。
- 对比：`--login-sub-fg` 7.02:1、`--login-foot-fg` 5.63:1、品牌全名（`--root-fg` 系）16.50:1，均 ≥4.5:1；三态提示块的颜色对比属 `.notice--danger`（02 规格，tokens.md 已判）。
- 触控：`<button class="btn btn--block">` 全宽、`min-height:44px`（rb.css:195）；输入框同样 44px（rb.css:320）。
- **状态不能只靠颜色**：凭据错误与账号不可用是两种不同原因，除颜色外必须靠**不同文案 + 不同图标**区分（content-spec S01 逐字文案 + 原型两种图标），且两者都不得使用成功色。
- 密码字段类型 `password` + `autocomplete="current-password"`；账号 `autocomplete="username"`（原型 parts/login.html:26/31）。
- **密码显示/隐藏切换**（content-spec S01 要求，原型未实现 → U9）：必须是 `<button type="button">`（不能进表单提交流）；`aria-pressed` 表达当前是否明文；`aria-controls` 指向密码 `<input>` 的 `id`；可访问名必须随状态变化（明文 ↔ 密文两态不同名），**不能只靠图标变化或颜色变化**；触控 ≥44px（`.btn` min-height，rb.css:195）；切换不得清空已输入内容，也不得改变焦点位置（焦点留在该按钮上，或按产品约定回密码框）。
- 会话有效期提示（`login__foot`）是文本，不得做成徽标/图标。

### 7. 内容与文案规则
| 位置 | 逐字文案 | 来源 |
| --- | --- | --- |
| 产品名（品牌行） | 校园课程智能助手 | content-spec S01 |
| 副标题 | 查课表 · 问资料 · 存计划，一个入口 | content-spec S01 |
| 账号 label | 账号（+ 必填） | content-spec S01 |
| 密码 label | 密码（+ 必填） | content-spec S01，且需显示/隐藏切换 |
| 主按钮 | 登录 | content-spec S01 |
| 状态 A 提示 | **账号或密码不正确，请重试。** | content-spec S01「错误态（统一文案，不区分账号不存在/密码错误）」逐字 |
| 状态 B 提示 | **当前账号不可用，请联系管理员。** | content-spec S01「账号被禁用」逐字 |
| 页脚 | 登录会话有效期 2 小时，到期后需要重新登录。 | content-spec S01「页脚提示」逐字 |
| 密码切换按钮 | **已冻结（阶段 A，content-spec S01）**：遮蔽态「显示密码」（`aria-pressed="false"`）／明文态「隐藏密码」（`aria-pressed="true"`） | 逐字消费 content-spec S01，不可自造或简写；原型本轮仍未实现该控件（U9） |

- 两种错误态**文案不互相替代**（一个是凭据错、一个是账号不可用）；不得合并成一句。
- 禁止在登录页出现任何未承诺入口（忘记密码 / 注册 / 第三方登录 / 验证码——PRD 未承诺）；禁止出现 content-spec §3 的禁止表述。

### 8. 响应式行为
| 档位 | `.login` |
| --- | --- |
| base / xs（<768） | `max-width:420px` + `margin:0 auto`：320px 下可视宽 320−2×18=284px，满宽卡片，不横向滚动 |
| sm / md / lg / xl（≥768） | 同一条规则：420px 居中，**不随断点加宽**、不改列数（单列恒为 1） |

- 字段列数恒为 1（不用 `.form-grid--2`），因此登录屏在 sm 档不发生列表变化。
- 外壳关系：`rb.css` 对「登录屏是否渲染 AppBar/Tabbar」无任何规则；`body{padding-bottom}` 的底栏占位（rb.css:102）在登录屏同样生效。本规格不新增 class 来实现隐藏，见 U6。

### 9. 契约依据与禁止事项
- 依据：`tokens.json` → `component.login`（7 token）；`content-spec.md` S01（含三种状态与逐字文案）；`b-responsive-spec.md` §2/§6；tokens.md §10（`.login` 最大宽 420px 迁移行）。
- 禁止：新增 `.login--error`/`.login--disabled` 之类变体（rb.css 无此实现，态由子组件承载）；把 420px 改成百分比或断点值；用 placeholder 代替可见 label；错误态只改颜色不给文案；复用评审专用外壳 class 拼装登录屏；**为密码切换控件自拟文案或只给图标不给可访问名**（阶段 A 已冻结两态文案，实现时必须逐字消费 content-spec S01；该控件本轮仍未实现）。

---

**自检**

| 硬要求 | 状态 |
| --- | --- |
| `<!-- owns: -->` 首行列全 10 组 | ✅ root, focus, skiplink, sr, appbar, brand, navlink, tabbar, wrap, login |
| 77/77 token 出现在消费表，且与 `tokens.flat.json` 逐字一致 | ✅ 见文首归属矩阵 |
| 10 个组件 × 9 节骨架 | ✅ |
| 状态矩阵无实现中不存在的状态（无 `:active`、无 `transition`） | ✅ 每节显式列出「没有的状态」 |
| 不引用 L1/L2 作为消费方 | ✅ 仅在「说明」列以上游标注出现 |
| 不引用评审专用 class | ✅ 以 `meta.scope.review` 引用代替字面 |
| 导航换形态 + 对话不入 URL 取舍 | ✅ 文首「导航换形态契约」「导航契约」+ 组件 2/5 §9 |
| 未决/无法断定项 | ✅ U1–U8 |
