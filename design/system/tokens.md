# 设计系统 token 参考（自动生成）

> 本文件由 `design/system/generate.py` 从 [`tokens.json`](tokens.json) 生成，**请勿手改**。
> 数值列是解析到字面量后的最终值（`var()` 链已展开）。

## 1. 分层与规则

| 层 | 前缀 | 职责 | 允许的值 | 数量 |
| --- | --- | --- | --- | --- |
| L1 primitive | `--p-*` | 原始值，只描述「是什么」 | 字面量 | 91 |
| L2 semantic | `--bg-*` `--text-*` `--accent*` `--state-*` `--border*` `--layout-*` … | 用途别名 | 只 `var(--p-*)` | 41 |
| L3 component | `--<组件>-<部位>-<属性>` | 组件属性 | 只 `var()`；无单位数值/关键字除外 | 337 |
| L0 compat | `--c-*` `--sp-*` `--fs-*` … | rb.css 兼容，deprecated | `var()` | 50 |

- L1 的值必须是字面量（hex / rgba / px / em / ch / % / 无单位数 / 关键字 / 字体栈）。允许 L1 内部组合（如阴影引用 alpha 原语），但不得引用 L2/L3。
- L2 的值只能是 var(--p-*) 组合，不得出现字面量。
- L3 的值只能是 var(--...) 组合。颜色**必须经 L2**（禁止直接从 L1 取色）；间距/字号/行高/字重/边宽/圆角/尺寸/时长/缓动/z-index 等**尺度类**原语允许直取 L1（尺度只是数字，不承载语义）；禁止 L3 之间互相引用。禁止裸色值与带单位裸长度。允许无单位数值（含 0）、关键字（transparent/auto/none/tabular-nums/inherit）以及由 var() 拼接的复合值。
- 媒体查询的 max-width 档只允许写 (min-width 档 − 1)，如 sm 档的向下写法是 max-width:767px。
- 组件 CSS 规则只允许消费 L3。跨层引用（组件直接用 L2/L1）视为违规。
- 媒体查询断点无法用 CSS 变量表达，必须写字面量；取值只允许来自本文件 breakpoint 表。
- 新增 L1 值必须同时新增对应 L2/L3 引用面，否则视为未使用 token（校验脚本会报）。

## 2. 断点

| 档 | min-width | 作用 |
| --- | --- | --- |
| base | 无媒体查询（基准） | 基准档，无媒体查询；最窄按 320px 验收（WCAG 1.4.10 Reflow） |
| xs | ≥480px | 大手机：气泡限宽 88%、过程区摘要由折叠转展开 |
| sm | ≥768px | 主分界线：导航换形态 + 表格→卡片 + 表单转两列，三件事压在同一断点以减少验证组合 |
| md | ≥1024px | 桌面 |
| lg | ≥1200px | 宽屏：内容列与助手列达到最大宽 |
| xl | ≥1440px | 超宽屏 |

## 3. L1 primitive

### color.brand

品牌墨绿。green-700 是主色，green-900 是强调/深色态，green-100 是浅底。

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-green-900` | `#0F4A42` |  |
| `--p-green-700` | `#14665B` |  |
| `--p-green-100` | `#E3EDEB` |  |

### color.pending

琥珀：**专用于「未保存 / 待确认」**，不得用于其他语义。

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-amber-800` | `#8A4107` | 作为文字色使用（对比度达标） |
| `--p-amber-700` | `#B45309` | 仅作边框/虚下划线，不作为文字色 |
| `--p-amber-100` | `#FBF0DF` |  |

### color.state

语义状态色。每族两个文字档（700 用于浅底上的文字，800 用于与浅底配对的最深文字）+ 一个浅底档。

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-ok-800` | `#2F4A0D` |  |
| `--p-ok-700` | `#3F6212` |  |
| `--p-ok-100` | `#ECF2DF` |  |
| `--p-danger-800` | `#7B0E2C` |  |
| `--p-danger-700` | `#9F1239` |  |
| `--p-danger-100` | `#FBE7EC` |  |
| `--p-info-800` | `#164A5B` |  |
| `--p-info-700` | `#1E5F74` |  |
| `--p-info-100` | `#E3EEF2` |  |

### color.neutral

暖灰中性阶。ink-400 及更深可用于 UI 边界；ink-300 只作装饰分隔线（不承担识别职责）。

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-ink-900` | `#1C1917` |  |
| `--p-ink-700` | `#44403C` |  |
| `--p-ink-600` | `#5B544E` |  |
| `--p-ink-500` | `#6B6259` |  |
| `--p-ink-400` | `#78716C` |  |
| `--p-ink-300` | `#C9C3BC` | 装饰分隔线；不可作为唯一识别手段 |
| `--p-ink-200` | `#E7E5E4` |  |

### color.surface

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-white` | `#FFFFFF` |  |
| `--p-sand-50` | `#FAF8F5` | 页面底：比卡片底更暖一档，形成近无边的分组感 |

### color.alpha

同色透明的原始值。必须由校验脚本做 alpha 合成后再判对比度。

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-ink-900-a04` | `rgba(28,25,23,.04)` | 弱 hover 底 |
| `--p-ink-900-a03` | `rgba(28,25,23,.03)` | 只读控件底 |

### space.rhythm

布局节奏，6px 基准。方向 B 刻意避开 4 的倍数，形成密度身份。编号 n ⇒ n×6px。

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-space-1` | `6px` |  |
| `--p-space-2` | `12px` |  |
| `--p-space-3` | `18px` |  |
| `--p-space-4` | `24px` |  |
| `--p-space-6` | `36px` |  |
| `--p-space-8` | `48px` |  |
| `--p-space-12` | `72px` |  |

### space.micro

像素级微调，命名直接带 px 以区别于节奏档。只允许用于胶囊/单元格内边距与图标微对齐。

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-space-2px` | `2px` |  |
| `--p-space-3px` | `3px` |  |
| `--p-space-5px` | `5px` |  |
| `--p-space-8px` | `8px` |  |
| `--p-space-10px` | `10px` |  |

### font.family

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-font-sans` | `system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif` |  |
| `--p-font-mono` | `ui-monospace,SFMono-Regular,"Cascadia Mono",Consolas,monospace` |  |

### font.size

字阶。正文 17px 是方向 B 的阅读舒适度选择（不是 14/16 的常规档）。

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-fs-13` | `13px` | 辅助信息、胶囊、表头、字段名 |
| `--p-fs-15` | `15px` | 次级正文、表格内容 |
| `--p-fs-17` | `17px` | 正文基准 |
| `--p-fs-20` | `20px` |  |
| `--p-fs-24` | `24px` | 登录页品牌名 |
| `--p-fs-32` | `32px` |  |
| `--p-fs-code` | `0.92em` | 行内代码相对字号 |

### font.lineHeight

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-lh-body` | `1.75` |  |
| `--p-lh-tight` | `1.35` | 标题 |
| `--p-lh-control` | `1.6` | 胶囊与文本域 |

### font.weight

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-fw-medium` | `500` |  |
| `--p-fw-semibold` | `600` |  |

### radius

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-radius-4` | `4px` | 焦点环圆角 |
| `--p-radius-6` | `6px` | 用户气泡的收角 |
| `--p-radius-7` | `7px` | 小标记方块 |
| `--p-radius-10` | `10px` | 控件 |
| `--p-radius-14` | `14px` | 卡片 |
| `--p-radius-pill` | `999px` |  |

### border.width

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-bw-1` | `1px` |  |
| `--p-bw-2` | `2px` |  |
| `--p-bw-3` | `3px` |  |
| `--p-bw-4` | `4px` |  |

### elevation

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-shadow-1` | `0 1px 1px var(--p-ink-900-a04)` | 唯一的层级：近平面，靠留白与边框分组而非投影 |

### motion

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-duration-spin` | `1100ms` |  |
| `--p-easing-linear` | `linear` |  |
| `--p-duration-fast` | `120ms` | 已定义未使用：交互过渡接入时用 |
| `--p-duration-base` | `200ms` | 已定义未使用：交互过渡接入时用 |
| `--p-easing-standard` | `cubic-bezier(.2,0,0,1)` | 已定义未使用：交互过渡接入时用 |

### zIndex

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-z-composer` | `20` |  |
| `--p-z-appbar` | `40` |  |
| `--p-z-tabbar` | `40` |  |
| `--p-z-skiplink` | `60` |  |

### size

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-size-mark-sm` | `26px` | 顶栏品牌标记 |
| `--p-size-mark-lg` | `38px` | 登录页品牌标记 |
| `--p-size-appbar` | `56px` |  |
| `--p-size-tabbar` | `56px` |  |
| `--p-size-tap` | `44px` | 最小触控目标（WCAG 2.2 2.5.8 要求 24px，本设计取 44px） |
| `--p-size-textarea-min` | `120px` |  |
| `--p-size-cellname-min` | `180px` | 表格文件名列最小宽；小于此值 break-word 会把列压成 1 字符宽 |
| `--p-size-full` | `100%` |  |
| `--p-offset-offscreen` | `-100px` | 跳转链接未聚焦时移出视口的位置 |
| `--p-size-content-max` | `880px` |  |
| `--p-size-assistant-max` | `720px` |  |
| `--p-size-login-max` | `420px` |  |
| `--p-size-prose-max` | `68ch` |  |
| `--p-size-label-col` | `7.5em` | 卡片化表格的字段名列 |
| `--p-size-kv-key-col` | `8em` |  |
| `--p-size-bubble-max` | `88%` |  |
| `--p-sr-clip-size` | `1px` | 仅供视觉隐藏（sr-only）使用，不是视觉设计尺寸 |
| `--p-sr-clip-offset` | `-1px` |  |

### opacity

| token | 值 | 说明 |
| --- | --- | --- |
| `--p-opacity-disabled` | `0.5` |  |

## 4. L2 semantic

### surface

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--bg-page` | `var(--p-sand-50)` | `#FAF8F5` | 页面底 |
| `--bg-card` | `var(--p-white)` | `#FFFFFF` | 卡片/控件底 |
| `--bg-muted` | `var(--p-ink-200)` | `#E7E5E4` | 中性块底（默认胶囊、普通提示块） |
| `--bg-readonly` | `var(--p-ink-900-a03)` | `rgba(28,25,23,.03)` | 只读控件底（含 alpha，判对比度须先合成） |
| `--bg-hover-weak` | `var(--p-ink-900-a04)` | `rgba(28,25,23,.04)` | 弱 hover 底 |

### text

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--text-primary` | `var(--p-ink-900)` | `#1C1917` | 正文 |
| `--text-secondary` | `var(--p-ink-600)` | `#5B544E` | 次级正文 |
| `--text-muted` | `var(--p-ink-500)` | `#6B6259` | 弱化文字：字段名、说明、时间戳 |
| `--text-on-accent` | `var(--p-white)` | `#FFFFFF` | 主色底上的文字 |
| `--text-art` | `var(--p-ink-400)` | `#78716C` | 空状态插图/装饰图标的颜色（不承载正文） |

### accent

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--accent` | `var(--p-green-700)` | `#14665B` | 主色：主按钮底、品牌标记底 |
| `--accent-strong` | `var(--p-green-900)` | `#0F4A42` | 深主色：链接、当前导航、浅底上的强调文字、焦点环 |
| `--accent-tint` | `var(--p-green-100)` | `#E3EDEB` | 主色浅底 |

### pending

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--pending` | `var(--p-amber-800)` | `#8A4107` | 未保存 / 待确认的文字色 |
| `--pending-tint` | `var(--p-amber-100)` | `#FBF0DF` | 未保存 / 待确认的浅底 |
| `--pending-border` | `var(--p-amber-700)` | `#B45309` | 未保存 / 待确认的边框与虚下划线（不作文本色） |

### state

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--state-success` | `var(--p-ok-800)` | `#2F4A0D` |  |
| `--state-success-tint` | `var(--p-ok-100)` | `#ECF2DF` |  |
| `--state-warning` | `var(--p-amber-800)` | `#8A4107` |  |
| `--state-warning-tint` | `var(--p-amber-100)` | `#FBF0DF` |  |
| `--state-danger` | `var(--p-danger-800)` | `#7B0E2C` |  |
| `--state-danger-tint` | `var(--p-danger-100)` | `#FBE7EC` |  |
| `--state-info` | `var(--p-info-800)` | `#164A5B` |  |
| `--state-info-tint` | `var(--p-info-100)` | `#E3EEF2` |  |

### border

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--border` | `var(--p-ink-200)` | `#E7E5E4` | 装饰分隔线（卡片边、行分隔） |
| `--border-strong` | `var(--p-ink-300)` | `#C9C3BC` | 次级控件边（按钮、空状态虚线框） |
| `--border-field` | `var(--p-ink-400)` | `#78716C` | 表单控件边界：唯一需满足 1.4.11 非文本对比 3:1 的边框 |
| `--danger-border` | `var(--p-danger-700)` | `#9F1239` | 危险态边框（比 --state-danger 浅一档，仅作边不作文） |
| `--focus` | `var(--p-green-900)` | `#0F4A42` | 焦点环颜色 |

### a11y

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--focus-ring-w` | `var(--p-bw-3)` | `3px` | 焦点环宽度 |
| `--focus-ring-offset` | `var(--p-space-2px)` | `2px` |  |
| `--focus-ring-radius` | `var(--p-radius-4)` | `4px` |  |

### layout

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--layout-content-max` | `var(--p-size-content-max)` | `880px` |  |
| `--layout-assistant-max` | `var(--p-size-assistant-max)` | `720px` |  |
| `--layout-prose-max` | `var(--p-size-prose-max)` | `68ch` |  |

### shell

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--shell-appbar-h` | `var(--p-size-appbar)` | `56px` |  |
| `--shell-tabbar-h` | `var(--p-size-tabbar)` | `56px` |  |
| `--size-control-min` | `var(--p-size-tap)` | `44px` | 所有可点击控件的最小高度（按钮/导航/胶囊入口） |

### elevation

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--elevation-card` | `var(--p-shadow-1)` | `0 1px 1px rgba(28,25,23,.04)` |  |

### motion

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--motion-spin-duration` | `var(--p-duration-spin)` | `1100ms` |  |
| `--motion-spin-easing` | `var(--p-easing-linear)` | `linear` |  |

## 5. L3 component

### root

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--root-bg` | `var(--bg-page)` | `#FAF8F5` |  |
| `--root-fg` | `var(--text-primary)` | `#1C1917` |  |
| `--root-font` | `var(--p-font-sans)` | `system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif` |  |
| `--root-fs` | `var(--p-fs-17)` | `17px` |  |
| `--root-lh` | `var(--p-lh-body)` | `1.75` |  |
| `--root-font-variant` | `tabular-nums` | `tabular-nums` | 等宽数字：时间/编号列对齐 |
| `--root-tabbar-reserve` | `var(--shell-tabbar-h)` | `56px` | 窄屏底部为标签栏留白，≥sm 归零 |
| `--root-scroll-offset` | `calc(var(--shell-appbar-h) + var(--p-space-1))` | `calc(56px + 6px)` | html 的 scroll-padding-top：顶栏 56px + 一个间距档 6px = 62px，锚点与 skip-link 跳转时目标不被 sticky 顶栏遮挡（rb.css:84 声明、rb.css:94 消费）。取值与 rb.css 的 `calc(var(--h-appbar) + var(--sp-1))` 解析后逐字相等；此处不写 `var(--appbar-min-h)`，因为 L3 之间互引是 verify-system.py B 项的 FAIL 级违规 |

### focus

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--focus-outline-w` | `var(--focus-ring-w)` | `3px` |  |
| `--focus-outline-color` | `var(--focus)` | `#0F4A42` |  |
| `--focus-outline-offset` | `var(--focus-ring-offset)` | `2px` |  |
| `--focus-outline-radius` | `var(--focus-ring-radius)` | `4px` |  |

### skiplink

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--skiplink-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--skiplink-border-color` | `var(--focus)` | `#0F4A42` |  |
| `--skiplink-border-w` | `var(--p-bw-2)` | `2px` |  |
| `--skiplink-radius` | `var(--p-radius-10)` | `10px` |  |
| `--skiplink-pad-y` | `var(--p-space-2)` | `12px` |  |
| `--skiplink-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--skiplink-offset-x` | `var(--p-space-2)` | `12px` |  |
| `--skiplink-offset-y-visible` | `var(--p-space-2)` | `12px` |  |
| `--skiplink-offset-y-hidden` | `var(--p-offset-offscreen)` | `-100px` |  |
| `--skiplink-z` | `var(--p-z-skiplink)` | `60` |  |
| `--skiplink-fw` | `var(--p-fw-semibold)` | `600` |  |

### sr

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--sr-size` | `var(--p-sr-clip-size)` | `1px` |  |
| `--sr-offset` | `var(--p-sr-clip-offset)` | `-1px` |  |

### appbar

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--appbar-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--appbar-border-color` | `var(--border)` | `#E7E5E4` |  |
| `--appbar-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--appbar-min-h` | `var(--shell-appbar-h)` | `56px` |  |
| `--appbar-pad-y` | `var(--p-space-1)` | `6px` |  |
| `--appbar-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--appbar-gap` | `var(--p-space-3)` | `18px` |  |
| `--appbar-nav-gap` | `var(--p-space-1)` | `6px` | 内联导航项之间的间距（rb.css:136），与 --appbar-gap 不同 |
| `--appbar-nav-offset-x` | `var(--p-space-2)` | `12px` | 导航区左侧偏移（rb.css:136 margin-left），把导航与品牌分开 |
| `--appbar-user-gap` | `var(--p-space-2)` | `12px` | 用户区图标与身份标签的间距（rb.css:137） |
| `--appbar-z` | `var(--p-z-appbar)` | `40` |  |
| `--appbar-max-w` | `var(--layout-content-max)` | `880px` |  |

### brand

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--brand-gap` | `var(--p-space-1)` | `6px` |  |
| `--brand-fw` | `var(--p-fw-semibold)` | `600` |  |
| `--brand-mark-size` | `var(--p-size-mark-sm)` | `26px` |  |
| `--brand-mark-radius` | `var(--p-radius-7)` | `7px` |  |
| `--brand-mark-bg` | `var(--accent)` | `#14665B` |  |
| `--brand-mark-fg` | `var(--accent-tint)` | `#E3EDEB` |  |
| `--brand-mark-size-lg` | `var(--p-size-mark-lg)` | `38px` |  |
| `--brand-mark-radius-lg` | `var(--p-radius-10)` | `10px` |  |
| `--brand-name-fs` | `var(--p-fs-24)` | `24px` |  |

### navlink

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--navlink-min-h` | `var(--size-control-min)` | `44px` |  |
| `--navlink-pad-x` | `var(--p-space-2)` | `12px` |  |
| `--navlink-gap` | `var(--p-space-1)` | `6px` |  |
| `--navlink-radius` | `var(--p-radius-10)` | `10px` |  |
| `--navlink-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--navlink-fw` | `var(--p-fw-medium)` | `500` |  |
| `--navlink-bg-hover` | `var(--bg-hover-weak)` | `rgba(28,25,23,.04)` |  |
| `--navlink-current-bg` | `var(--accent-tint)` | `#E3EDEB` |  |
| `--navlink-current-fg` | `var(--accent-strong)` | `#0F4A42` |  |
| `--navlink-current-fw` | `var(--p-fw-semibold)` | `600` |  |

### tabbar

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--tabbar-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--tabbar-border-color` | `var(--border)` | `#E7E5E4` |  |
| `--tabbar-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--tabbar-cols` | `4` | `4` | 一级入口数：助手/课表/计划/管理 |
| `--tabbar-item-min-h` | `var(--shell-tabbar-h)` | `56px` |  |
| `--tabbar-item-gap` | `var(--p-space-2px)` | `2px` |  |
| `--tabbar-item-fs` | `var(--p-fs-13)` | `13px` |  |
| `--tabbar-item-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--tabbar-item-current-fg` | `var(--accent-strong)` | `#0F4A42` |  |
| `--tabbar-item-current-fw` | `var(--p-fw-semibold)` | `600` |  |
| `--tabbar-z` | `var(--p-z-tabbar)` | `40` |  |

### wrap

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--wrap-max` | `var(--layout-content-max)` | `880px` |  |
| `--wrap-pad-y` | `var(--p-space-4)` | `24px` |  |
| `--wrap-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--wrap-pad-y-sm` | `var(--p-space-6)` | `36px` | ≥sm(768px) 的纵向内边距（rb.css:166）。 命名用 sm 而非 md：该规则写在 min-width:768px 档 |
| `--wrap-pad-x-sm` | `var(--p-space-4)` | `24px` | ≥sm(768px) 的横向内边距（rb.css:166） |
| `--wrap-assistant-max` | `var(--layout-assistant-max)` | `720px` |  |
| `--wrap-inner-pad-x` | `0` | `0` | 嵌套 .wrap（助手片段自带 wrap）时内层左右内边距归零，避免双重缩进 |

### card

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--card-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--card-border-color` | `var(--border)` | `#E7E5E4` |  |
| `--card-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--card-radius` | `var(--p-radius-14)` | `14px` |  |
| `--card-shadow` | `var(--elevation-card)` | `0 1px 1px rgba(28,25,23,.04)` |  |
| `--card-head-pad-y` | `var(--p-space-3)` | `18px` |  |
| `--card-head-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--card-head-pad-b` | `var(--p-space-2)` | `12px` |  |
| `--card-head-gap` | `var(--p-space-2)` | `12px` |  |
| `--card-body-pad` | `var(--p-space-3)` | `18px` |  |
| `--card-foot-pad-t` | `var(--p-space-2)` | `12px` |  |
| `--card-foot-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--card-foot-pad-b` | `var(--p-space-3)` | `18px` |  |
| `--card-foot-gap` | `var(--p-space-2)` | `12px` |  |
| `--card-row-gap` | `var(--p-space-3)` | `18px` |  |

### btn

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--btn-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--btn-fg` | `var(--text-primary)` | `#1C1917` |  |
| `--btn-border-color` | `var(--border-strong)` | `#C9C3BC` |  |
| `--btn-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--btn-min-h` | `var(--size-control-min)` | `44px` |  |
| `--btn-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--btn-pad-x-sm` | `var(--p-space-2)` | `12px` |  |
| `--btn-gap` | `var(--p-space-1)` | `6px` |  |
| `--btn-radius` | `var(--p-radius-10)` | `10px` |  |
| `--btn-fw` | `var(--p-fw-semibold)` | `600` |  |
| `--btn-fs-sm` | `var(--p-fs-15)` | `15px` |  |
| `--btn-disabled-opacity` | `var(--p-opacity-disabled)` | `0.5` |  |
| `--btn-primary-bg` | `var(--accent)` | `#14665B` |  |
| `--btn-primary-fg` | `var(--text-on-accent)` | `#FFFFFF` |  |
| `--btn-primary-border-color` | `var(--accent)` | `#14665B` |  |
| `--btn-primary-bg-hover` | `var(--accent-strong)` | `#0F4A42` |  |
| `--btn-danger-bg` | `var(--state-danger-tint)` | `#FBE7EC` |  |
| `--btn-danger-fg` | `var(--state-danger)` | `#7B0E2C` |  |
| `--btn-danger-border-color` | `var(--danger-border)` | `#9F1239` |  |
| `--btn-ghost-bg` | `transparent` | `transparent` |  |
| `--btn-ghost-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--btn-ghost-border-color` | `transparent` | `transparent` |  |

### pill

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--pill-bg` | `var(--bg-muted)` | `#E7E5E4` |  |
| `--pill-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--pill-fs` | `var(--p-fs-13)` | `13px` |  |
| `--pill-fw` | `var(--p-fw-semibold)` | `600` |  |
| `--pill-lh` | `var(--p-lh-control)` | `1.6` |  |
| `--pill-pad-y` | `var(--p-space-2px)` | `2px` |  |
| `--pill-pad-x` | `var(--p-space-10px)` | `10px` |  |
| `--pill-gap` | `var(--p-space-5px)` | `5px` |  |
| `--pill-radius` | `var(--p-radius-pill)` | `999px` |  |
| `--pill-ok-bg` | `var(--state-success-tint)` | `#ECF2DF` |  |
| `--pill-ok-fg` | `var(--state-success)` | `#2F4A0D` |  |
| `--pill-warn-bg` | `var(--state-warning-tint)` | `#FBF0DF` |  |
| `--pill-warn-fg` | `var(--state-warning)` | `#8A4107` |  |
| `--pill-danger-bg` | `var(--state-danger-tint)` | `#FBE7EC` |  |
| `--pill-danger-fg` | `var(--state-danger)` | `#7B0E2C` |  |
| `--pill-info-bg` | `var(--state-info-tint)` | `#E3EEF2` |  |
| `--pill-info-fg` | `var(--state-info)` | `#164A5B` |  |
| `--pill-evidence-bg` | `var(--accent-tint)` | `#E3EDEB` |  |
| `--pill-evidence-fg` | `var(--accent-strong)` | `#0F4A42` |  |
| `--pill-advice-bg` | `var(--bg-muted)` | `#E7E5E4` |  |
| `--pill-advice-fg` | `var(--text-secondary)` | `#5B544E` |  |

### notice

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--notice-bg` | `var(--bg-muted)` | `#E7E5E4` |  |
| `--notice-fg` | `var(--text-primary)` | `#1C1917` |  |
| `--notice-gap` | `var(--p-space-2)` | `12px` |  |
| `--notice-pad` | `var(--p-space-3)` | `18px` |  |
| `--notice-radius` | `var(--p-radius-10)` | `10px` |  |
| `--notice-margin-b` | `var(--p-space-3)` | `18px` |  |
| `--notice-ico-offset-y` | `var(--p-space-2px)` | `2px` |  |
| `--notice-info-bg` | `var(--state-info-tint)` | `#E3EEF2` |  |
| `--notice-info-fg` | `var(--state-info)` | `#164A5B` |  |
| `--notice-warn-bg` | `var(--state-warning-tint)` | `#FBF0DF` |  |
| `--notice-warn-fg` | `var(--state-warning)` | `#8A4107` |  |
| `--notice-danger-bg` | `var(--state-danger-tint)` | `#FBE7EC` |  |
| `--notice-danger-fg` | `var(--state-danger)` | `#7B0E2C` |  |
| `--notice-ok-bg` | `var(--state-success-tint)` | `#ECF2DF` |  |
| `--notice-ok-fg` | `var(--state-success)` | `#2F4A0D` |  |
| `--notice-evidence-bg` | `var(--accent-tint)` | `#E3EDEB` |  |
| `--notice-evidence-fg` | `var(--accent-strong)` | `#0F4A42` |  |

### chat

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--chat-gap` | `var(--p-space-3)` | `18px` |  |
| `--msg-gap` | `var(--p-space-1)` | `6px` |  |
| `--msg-who-fs` | `var(--p-fs-13)` | `13px` |  |
| `--msg-who-fg` | `var(--text-muted)` | `#6B6259` |  |
| `--bubble-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--bubble-fg` | `var(--text-primary)` | `#1C1917` |  |
| `--bubble-border-color` | `var(--border)` | `#E7E5E4` |  |
| `--bubble-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--bubble-radius` | `var(--p-radius-14)` | `14px` |  |
| `--bubble-pad-y` | `var(--p-space-2)` | `12px` |  |
| `--bubble-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--bubble-user-bg` | `var(--accent-tint)` | `#E3EDEB` |  |
| `--bubble-user-border-color` | `var(--accent-tint)` | `#E3EDEB` |  |
| `--bubble-user-tail-radius` | `var(--p-radius-6)` | `6px` |  |
| `--bubble-max-w` | `var(--p-size-full)` | `100%` |  |
| `--bubble-max-w-xs` | `var(--p-size-bubble-max)` | `88%` | ≥xs 限宽，避免长回答铺满整屏 |

### steps

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--steps-gap` | `var(--p-space-1)` | `6px` |  |
| `--steps-rail-w` | `var(--p-bw-2)` | `2px` |  |
| `--steps-rail-color` | `var(--border)` | `#E7E5E4` |  |
| `--steps-indent` | `var(--p-space-3)` | `18px` |  |
| `--step-gap` | `var(--p-space-2)` | `12px` |  |
| `--step-ico-offset-y` | `var(--p-space-3px)` | `3px` |  |
| `--step-sub-fs` | `var(--p-fs-15)` | `15px` |  |
| `--step-sub-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--step-failed-fg` | `var(--state-danger)` | `#7B0E2C` |  |
| `--steps-min-h` | `var(--size-control-min)` | `44px` |  |
| `--steps-summary-fs` | `var(--p-fs-15)` | `15px` |  |
| `--steps-summary-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--steps-summary-gap` | `var(--p-space-1)` | `6px` |  |
| `--step-running-spin-duration` | `var(--p-duration-spin)` | `1100ms` | running 态图标旋转时长（rb.css:253）。必须放在 L3：组件规则只能消费 L3，而 --motion-spin-duration 在 L2，跨层取不到——这是收口时补入的原因 |
| `--step-running-spin-easing` | `var(--p-easing-linear)` | `linear` | running 态旋转缓动（rb.css:253） |

### composer

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--composer-bg` | `var(--bg-page)` | `#FAF8F5` |  |
| `--composer-border-color` | `var(--border)` | `#E7E5E4` |  |
| `--composer-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--composer-pad-y` | `var(--p-space-2)` | `12px` |  |
| `--composer-gap` | `var(--p-space-2)` | `12px` |  |
| `--composer-count-fs` | `var(--p-fs-13)` | `13px` |  |
| `--composer-count-fg` | `var(--text-muted)` | `#6B6259` |  |
| `--composer-z` | `var(--p-z-composer)` | `20` |  |
| `--composer-bottom` | `var(--shell-tabbar-h)` | `56px` | 窄屏吸附在标签栏之上；≥sm 归零 |

### cite

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--cite-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--cite-border-color` | `var(--border)` | `#E7E5E4` |  |
| `--cite-border-w` | `var(--p-bw-1)` | `1px` | 三边实线宽度；__body 的上分隔线用同宽虚线 |
| `--cite-accent-w` | `var(--p-bw-4)` | `4px` | 左侧主色条——已验证引用的视觉标记 |
| `--cite-accent-color` | `var(--accent)` | `#14665B` |  |
| `--cite-radius` | `var(--p-radius-10)` | `10px` |  |
| `--cite-pad-y` | `var(--p-space-2)` | `12px` |  |
| `--cite-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--cite-margin-t` | `var(--p-space-2)` | `12px` |  |
| `--cite-head-gap` | `var(--p-space-1)` | `6px` | 行间距（rb.css:279 的 gap 第一值） |
| `--cite-head-gap-x` | `var(--p-space-2)` | `12px` | 列间距（rb.css:279 的 gap 第二值）；与行间距不同，不可合并成一个 token |
| `--cite-head-fs` | `var(--p-fs-15)` | `15px` |  |
| `--cite-loc-fs` | `var(--p-fs-13)` | `13px` |  |
| `--cite-loc-fg` | `var(--text-muted)` | `#6B6259` |  |
| `--cite-body-fs` | `var(--p-fs-15)` | `15px` |  |
| `--cite-body-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--cite-body-margin-t` | `var(--p-space-1)` | `6px` |  |
| `--cite-body-pad-t` | `var(--p-space-1)` | `6px` |  |
| `--cite-invalid-border-color` | `var(--danger-border)` | `#9F1239` |  |
| `--cite-invalid-bg` | `var(--state-danger-tint)` | `#FBE7EC` |  |
| `--cite-invalid-fg` | `var(--state-danger)` | `#7B0E2C` |  |
| `--cite-mark-pending-color` | `var(--pending)` | `#8A4107` |  |
| `--cite-mark-pending-underline` | `var(--pending-border)` | `#B45309` | 未验证引用标记：虚下划线，与已验证引用必须可区分 |

### draft

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--draft-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--draft-border-w` | `var(--p-bw-2)` | `2px` |  |
| `--draft-border-color` | `var(--pending-border)` | `#B45309` | 未保存态：虚线琥珀边 |
| `--draft-radius` | `var(--p-radius-14)` | `14px` |  |
| `--draft-pad` | `var(--p-space-3)` | `18px` |  |
| `--draft-head-gap` | `var(--p-space-2)` | `12px` |  |
| `--draft-head-margin-b` | `var(--p-space-2)` | `12px` |  |
| `--draft-kv-key-col` | `auto` | `auto` |  |
| `--draft-kv-gap-y` | `var(--p-space-1)` | `6px` |  |
| `--draft-kv-gap-x` | `var(--p-space-2)` | `12px` |  |
| `--draft-kv-key-fs` | `var(--p-fs-13)` | `13px` |  |
| `--draft-kv-key-fg` | `var(--text-muted)` | `#6B6259` |  |
| `--draft-saved-border-color` | `var(--border)` | `#E7E5E4` |  |

### empty

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--empty-pad-y` | `var(--p-space-6)` | `36px` |  |
| `--empty-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--empty-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--empty-border-color` | `var(--border-strong)` | `#C9C3BC` |  |
| `--empty-radius` | `var(--p-radius-14)` | `14px` |  |
| `--empty-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--empty-art-fg` | `var(--text-art)` | `#78716C` |  |
| `--empty-art-margin-b` | `var(--p-space-2)` | `12px` |  |
| `--empty-title-margin-b` | `var(--p-space-1)` | `6px` |  |
| `--empty-hint-fs` | `var(--p-fs-15)` | `15px` |  |
| `--empty-hint-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--empty-error-border-color` | `var(--danger-border)` | `#9F1239` |  |
| `--empty-error-bg` | `var(--state-danger-tint)` | `#FBE7EC` |  |
| `--empty-error-fg` | `var(--state-danger)` | `#7B0E2C` |  |

### field

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--field-gap` | `var(--p-space-1)` | `6px` |  |
| `--field-label-fs` | `var(--p-fs-15)` | `15px` |  |
| `--field-label-fw` | `var(--p-fw-semibold)` | `600` |  |
| `--field-req-fg` | `var(--state-danger)` | `#7B0E2C` |  |
| `--field-req-fs` | `var(--p-fs-13)` | `13px` |  |
| `--field-hint-fs` | `var(--p-fs-13)` | `13px` |  |
| `--field-hint-fg` | `var(--text-muted)` | `#6B6259` |  |
| `--field-error-fs` | `var(--p-fs-13)` | `13px` |  |
| `--field-error-fg` | `var(--state-danger)` | `#7B0E2C` |  |
| `--field-error-gap` | `var(--p-space-5px)` | `5px` |  |
| `--field-grid-gap` | `var(--p-space-3)` | `18px` |  |

### control

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--control-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--control-fg` | `var(--text-primary)` | `#1C1917` |  |
| `--control-border-color` | `var(--border-field)` | `#78716C` |  |
| `--control-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--control-radius` | `var(--p-radius-10)` | `10px` |  |
| `--control-min-h` | `var(--size-control-min)` | `44px` |  |
| `--control-pad-y` | `var(--p-space-10px)` | `10px` |  |
| `--control-pad-x` | `var(--p-space-2)` | `12px` |  |
| `--control-textarea-min-h` | `var(--p-size-textarea-min)` | `120px` |  |
| `--control-textarea-lh` | `var(--p-lh-control)` | `1.6` |  |
| `--control-readonly-bg` | `var(--bg-readonly)` | `rgba(28,25,23,.03)` |  |
| `--control-readonly-border-color` | `var(--border)` | `#E7E5E4` |  |
| `--control-readonly-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--control-disabled-opacity` | `var(--p-opacity-disabled)` | `0.5` |  |
| `--control-invalid-border-color` | `var(--danger-border)` | `#9F1239` |  |
| `--control-invalid-ring` | `0 0 0 var(--p-bw-3) var(--state-danger-tint)` | `0 0 0 3px #FBE7EC` |  |
| `--errorsummary-border-color` | `var(--danger-border)` | `#9F1239` |  |
| `--errorsummary-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--errorsummary-bg` | `var(--state-danger-tint)` | `#FBE7EC` |  |
| `--errorsummary-radius` | `var(--p-radius-10)` | `10px` |  |
| `--errorsummary-pad-y` | `var(--p-space-2)` | `12px` |  |
| `--errorsummary-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--errorsummary-margin-b` | `var(--p-space-3)` | `18px` |  |
| `--errorsummary-fg` | `var(--state-danger)` | `#7B0E2C` |  |

### table

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--table-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--table-border-color` | `var(--border)` | `#E7E5E4` |  |
| `--table-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--table-radius` | `var(--p-radius-14)` | `14px` |  |
| `--table-fs` | `var(--p-fs-15)` | `15px` |  |
| `--table-caption-fs` | `var(--p-fs-13)` | `13px` |  |
| `--table-caption-fg` | `var(--text-muted)` | `#6B6259` |  |
| `--table-caption-pad-t` | `var(--p-space-2)` | `12px` |  |
| `--table-caption-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--table-cell-pad-y` | `var(--p-space-2)` | `12px` |  |
| `--table-cell-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--table-head-fs` | `var(--p-fs-13)` | `13px` |  |
| `--table-head-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--table-cellname-min-w` | `var(--p-size-cellname-min)` | `180px` |  |
| `--table-compact-fs` | `var(--p-fs-13)` | `13px` |  |
| `--table-compact-pad-y` | `var(--p-space-8px)` | `8px` |  |
| `--table-compact-pad-x` | `var(--p-space-2)` | `12px` |  |
| `--table-stack-label-col` | `var(--p-size-label-col)` | `7.5em` |  |
| `--table-stack-row-pad-y` | `var(--p-space-2)` | `12px` |  |
| `--table-stack-row-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--table-stack-cell-pad-y` | `var(--p-space-5px)` | `5px` |  |
| `--table-stack-label-fs` | `var(--p-fs-13)` | `13px` |  |
| `--table-stack-label-fg` | `var(--text-muted)` | `#6B6259` |  |
| `--table-stack-label-fw` | `var(--p-fw-semibold)` | `600` |  |
| `--table-stack-name-fs` | `var(--p-fs-17)` | `17px` |  |
| `--table-stack-name-pad-b` | `var(--p-space-8px)` | `8px` |  |
| `--table-stack-name-label-margin-b` | `var(--p-space-2px)` | `2px` | 卡片标题单元格里 ::before 字段名的下边距（rb.css:372）。与 --table-stack-name-pad-b(8px) 是两处不同的值，不可互相借用 |
| `--table-stack-caption-pad-b` | `var(--p-space-2)` | `12px` |  |

### kv

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--kv-gap` | `var(--p-space-1)` | `6px` |  |
| `--kv-row-key-col` | `var(--p-size-kv-key-col)` | `8em` |  |
| `--kv-row-gap` | `var(--p-space-2)` | `12px` |  |
| `--kv-key-fs` | `var(--p-fs-15)` | `15px` |  |
| `--kv-key-fg` | `var(--text-muted)` | `#6B6259` |  |

### chip

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--chip-min-h` | `var(--size-control-min)` | `44px` |  |
| `--chip-pad-x` | `var(--p-space-3)` | `18px` |  |
| `--chip-gap` | `var(--p-space-1)` | `6px` |  |
| `--chip-radius` | `var(--p-radius-pill)` | `999px` |  |
| `--chip-bg` | `var(--bg-card)` | `#FFFFFF` |  |
| `--chip-fg` | `var(--text-primary)` | `#1C1917` |  |
| `--chip-border-color` | `var(--border-strong)` | `#C9C3BC` |  |
| `--chip-border-w` | `var(--p-bw-1)` | `1px` |  |
| `--chip-fw` | `var(--p-fw-medium)` | `500` |  |
| `--chip-hover-border-color` | `var(--accent)` | `#14665B` |  |
| `--chip-hover-fg` | `var(--accent-strong)` | `#0F4A42` |  |
| `--chips-gap` | `var(--p-space-1)` | `6px` |  |

### prose

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--prose-max` | `var(--layout-prose-max)` | `68ch` |  |
| `--prose-para-margin-b` | `var(--p-space-3)` | `18px` |  |
| `--prose-h-fw` | `var(--p-fw-semibold)` | `600` |  |
| `--prose-h-lh` | `var(--p-lh-tight)` | `1.35` |  |
| `--prose-link-fg` | `var(--accent-strong)` | `#0F4A42` |  |
| `--prose-code-font` | `var(--p-font-mono)` | `ui-monospace,SFMono-Regular,"Cascadia Mono",Consolas,monospace` |  |
| `--prose-code-fs` | `var(--p-fs-code)` | `0.92em` | 行内代码字号（0.92em） |

### login

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--login-max-w` | `var(--p-size-login-max)` | `420px` |  |
| `--login-gap` | `var(--p-space-3)` | `18px` |  |
| `--login-brand-gap` | `var(--p-space-2)` | `12px` |  |
| `--login-sub-fs` | `var(--p-fs-15)` | `15px` |  |
| `--login-sub-fg` | `var(--text-secondary)` | `#5B544E` |  |
| `--login-foot-fs` | `var(--p-fs-13)` | `13px` |  |
| `--login-foot-fg` | `var(--text-muted)` | `#6B6259` |  |

### utility

| token | 指向 | 解析值 | 说明 |
| --- | --- | --- | --- |
| `--stack-gap` | `var(--p-space-2)` | `12px` |  |
| `--row-gap` | `var(--p-space-2)` | `12px` |  |
| `--muted-fg` | `var(--text-muted)` | `#6B6259` |  |
| `--small-fs` | `var(--p-fs-13)` | `13px` |  |

## 6. L0 compat（deprecated）

保留 rb.css 的 75 个 `:root` 变量名中不与 L2/L3 重名的 50 个，逐值等价（见 §9 等价性证明）。新代码不得引用。

| token | 指向 | 解析值 |
| --- | --- | --- |
| `--c-green-900` | `var(--p-green-900)` | `#0F4A42` |
| `--c-green-700` | `var(--p-green-700)` | `#14665B` |
| `--c-green-100` | `var(--p-green-100)` | `#E3EDEB` |
| `--c-amber-800` | `var(--p-amber-800)` | `#8A4107` |
| `--c-amber-700` | `var(--p-amber-700)` | `#B45309` |
| `--c-amber-100` | `var(--p-amber-100)` | `#FBF0DF` |
| `--c-ok-800` | `var(--p-ok-800)` | `#2F4A0D` |
| `--c-ok-700` | `var(--p-ok-700)` | `#3F6212` |
| `--c-ok-100` | `var(--p-ok-100)` | `#ECF2DF` |
| `--c-danger-800` | `var(--p-danger-800)` | `#7B0E2C` |
| `--c-danger-700` | `var(--p-danger-700)` | `#9F1239` |
| `--c-danger-100` | `var(--p-danger-100)` | `#FBE7EC` |
| `--c-info-800` | `var(--p-info-800)` | `#164A5B` |
| `--c-info-700` | `var(--p-info-700)` | `#1E5F74` |
| `--c-info-100` | `var(--p-info-100)` | `#E3EEF2` |
| `--c-ink-900` | `var(--p-ink-900)` | `#1C1917` |
| `--c-ink-700` | `var(--p-ink-700)` | `#44403C` |
| `--c-ink-600` | `var(--p-ink-600)` | `#5B544E` |
| `--c-ink-500` | `var(--p-ink-500)` | `#6B6259` |
| `--c-ink-400` | `var(--p-ink-400)` | `#78716C` |
| `--c-ink-300` | `var(--p-ink-300)` | `#C9C3BC` |
| `--c-ink-200` | `var(--p-ink-200)` | `#E7E5E4` |
| `--c-bg-page` | `var(--p-sand-50)` | `#FAF8F5` |
| `--c-bg-card` | `var(--p-white)` | `#FFFFFF` |
| `--sp-1` | `var(--p-space-1)` | `6px` |
| `--sp-2` | `var(--p-space-2)` | `12px` |
| `--sp-3` | `var(--p-space-3)` | `18px` |
| `--sp-4` | `var(--p-space-4)` | `24px` |
| `--sp-6` | `var(--p-space-6)` | `36px` |
| `--sp-8` | `var(--p-space-8)` | `48px` |
| `--sp-12` | `var(--p-space-12)` | `72px` |
| `--fs-13` | `var(--p-fs-13)` | `13px` |
| `--fs-15` | `var(--p-fs-15)` | `15px` |
| `--fs-17` | `var(--p-fs-17)` | `17px` |
| `--fs-20` | `var(--p-fs-20)` | `20px` |
| `--fs-24` | `var(--p-fs-24)` | `24px` |
| `--fs-32` | `var(--p-fs-32)` | `32px` |
| `--lh-body` | `var(--p-lh-body)` | `1.75` |
| `--lh-tight` | `var(--p-lh-tight)` | `1.35` |
| `--r-card` | `var(--p-radius-14)` | `14px` |
| `--r-control` | `var(--p-radius-10)` | `10px` |
| `--r-pill` | `var(--p-radius-pill)` | `999px` |
| `--shadow-hair` | `var(--p-shadow-1)` | `0 1px 1px rgba(28,25,23,.04)` |
| `--w-content` | `var(--p-size-content-max)` | `880px` |
| `--w-assistant` | `var(--p-size-assistant-max)` | `720px` |
| `--h-appbar` | `var(--p-size-appbar)` | `56px` |
| `--h-tabbar` | `var(--p-size-tabbar)` | `56px` |
| `--tap` | `var(--p-size-tap)` | `44px` |
| `--font-sans` | `var(--p-font-sans)` | `system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif` |
| `--font-mono` | `var(--p-font-mono)` | `ui-monospace,SFMono-Regular,"Cascadia Mono",Consolas,monospace` |

## 7. 对比度（实测，含 alpha 合成）

判据：文字 4.5:1（WCAG 1.4.3 AA）；UI 边界 3:1（WCAG 1.4.11）。
含 alpha 的底先与卡片底合成，含 alpha 的前景先与底合成——这是对第 2 轮「未做 alpha 合成」的补齐。

| 配对 | 前景 | 底 | 要求 | 实测 | 判定 |
| --- | --- | --- | --- | --- | --- |
| 正文 / 页面底 | `--text-primary` | `--bg-page` | ≥4.5 | 16.50:1 | PASS |
| 正文 / 卡片底 | `--text-primary` | `--bg-card` | ≥4.5 | 17.49:1 | PASS |
| 次级正文 / 页面底 | `--text-secondary` | `--bg-page` | ≥4.5 | 7.02:1 | PASS |
| 次级正文 / 卡片底 | `--text-secondary` | `--bg-card` | ≥4.5 | 7.44:1 | PASS |
| 弱化文字 / 页面底 | `--text-muted` | `--bg-page` | ≥4.5 | 5.63:1 | PASS |
| 弱化文字 / 卡片底 | `--text-muted` | `--bg-card` | ≥4.5 | 5.97:1 | PASS |
| 主按钮文字 / 主按钮底 | `--btn-primary-fg` | `--btn-primary-bg` | ≥4.5 | 6.82:1 | PASS |
| 主按钮 hover 文字 / hover 底 | `--btn-primary-fg` | `--btn-primary-bg-hover` | ≥4.5 | 10.10:1 | PASS |
| 链接与强调文字 / 页面底 | `--accent-strong` | `--bg-page` | ≥4.5 | 9.53:1 | PASS |
| 当前导航文字 / 当前导航底 | `--navlink-current-fg` | `--navlink-current-bg` | ≥4.5 | 8.46:1 | PASS |
| 标签栏当前项 / 标签栏底 | `--tabbar-item-current-fg` | `--tabbar-bg` | ≥4.5 | 10.10:1 | PASS |
| 标签栏常态项 / 标签栏底 | `--tabbar-item-fg` | `--tabbar-bg` | ≥4.5 | 7.44:1 | PASS |
| 默认胶囊文字 / 胶囊底 | `--pill-fg` | `--pill-bg` | ≥4.5 | 5.92:1 | PASS |
| 成功胶囊文字 / 成功胶囊底 | `--pill-ok-fg` | `--pill-ok-bg` | ≥4.5 | 8.70:1 | PASS |
| 警告胶囊文字 / 警告胶囊底 | `--pill-warn-fg` | `--pill-warn-bg` | ≥4.5 | 6.56:1 | PASS |
| 危险胶囊文字 / 危险胶囊底 | `--pill-danger-fg` | `--pill-danger-bg` | ≥4.5 | 9.14:1 | PASS |
| 信息胶囊文字 / 信息胶囊底 | `--pill-info-fg` | `--pill-info-bg` | ≥4.5 | 8.21:1 | PASS |
| 依据胶囊文字 / 依据胶囊底 | `--pill-evidence-fg` | `--pill-evidence-bg` | ≥4.5 | 8.46:1 | PASS |
| 建议胶囊文字 / 建议胶囊底 | `--pill-advice-fg` | `--pill-advice-bg` | ≥4.5 | 5.92:1 | PASS |
| 提示块正文 / 提示块底 | `--notice-fg` | `--notice-bg` | ≥4.5 | 13.93:1 | PASS |
| 信息提示文字 / 信息提示底 | `--notice-info-fg` | `--notice-info-bg` | ≥4.5 | 8.21:1 | PASS |
| 警告提示文字 / 警告提示底 | `--notice-warn-fg` | `--notice-warn-bg` | ≥4.5 | 6.56:1 | PASS |
| 危险提示文字 / 危险提示底 | `--notice-danger-fg` | `--notice-danger-bg` | ≥4.5 | 9.14:1 | PASS |
| 成功提示文字 / 成功提示底 | `--notice-ok-fg` | `--notice-ok-bg` | ≥4.5 | 8.70:1 | PASS |
| 空状态说明 / 空状态底 | `--empty-hint-fg` | `--empty-bg` | ≥4.5 | 7.44:1 | PASS |
| 异常空状态文字 / 异常空状态底 | `--empty-error-fg` | `--empty-error-bg` | ≥4.5 | 9.14:1 | PASS |
| 未保存草稿文字 / 草稿底 | `--pending` | `--draft-bg` | ≥4.5 | 7.39:1 | PASS |
| 未验证引用标记 / 卡片底 | `--cite-mark-pending-color` | `--bg-card` | ≥4.5 | 7.39:1 | PASS |
| 失效引用文字 / 失效引用底 | `--cite-invalid-fg` | `--cite-invalid-bg` | ≥4.5 | 9.14:1 | PASS |
| 字段错误文字 / 页面底 | `--field-error-fg` | `--bg-page` | ≥4.5 | 10.20:1 | PASS |
| 只读控件文字 / 只读控件底（需 alpha 合成） | `--control-readonly-fg` | `--control-readonly-bg` | ≥4.5 | 7.00:1 | PASS |
| 正文 / 只读控件底（需 alpha 合成） | `--text-primary` | `--control-readonly-bg` | ≥4.5 | 16.47:1 | PASS |
| 表格正文 / 表格底 | `--text-primary` | `--table-bg` | ≥4.5 | 17.49:1 | PASS |
| 表头文字 / 表格底 | `--table-head-fg` | `--table-bg` | ≥4.5 | 7.44:1 | PASS |
| 卡片化字段名 / 卡片底 | `--table-stack-label-fg` | `--table-bg` | ≥4.5 | 5.97:1 | PASS |
| 表单控件边界 / 控件底 | `--control-border-color` | `--control-bg` | ≥3.0 | 4.80:1 | PASS |
| 焦点环 / 页面底 | `--focus-outline-color` | `--bg-page` | ≥3.0 | 9.53:1 | PASS |
| 焦点环 / 卡片底 | `--focus-outline-color` | `--bg-card` | ≥3.0 | 10.10:1 | PASS |
| 主按钮底 / 页面底 | `--btn-primary-bg` | `--bg-page` | ≥3.0 | 6.43:1 | PASS |
| 失效引用左条 / 页面底 | `--cite-invalid-border-color` | `--bg-page` | ≥3.0 | 7.56:1 | PASS |
| 未保存草稿虚线边 / 页面底 | `--draft-border-color` | `--bg-page` | ≥3.0 | 4.74:1 | PASS |

### 判定项（不是已证实事实）

**卡片边框与按钮边框（--card-border-color / --border-strong）** —— 比值 1.05:1（卡片底 vs 页面底）与 1.5:1（--border-strong vs 卡片底）

- 结论：不纳入 1.4.11 硬判据，但属于**判定项而非已证实事实**
- 理由：卡片是容器不是可交互组件；按钮虽有 1.5:1 的边，但其文字标签对比度 15.9:1，按 WCAG 1.4.11 理解文档，控件可由文字识别时边界不必满足 3:1。表单控件（可交互且无内文标签）已单独用 --border-field 达到 4.7:1。
- 若被推翻：把 --border-strong 改为 --p-ink-400 即可达 4.7:1，代价是方向 B「近平面、靠留白分组」的身份被削弱。

## 8. 覆盖度

- L1 primitive 未被任何 L2/L3/L0 引用的：无
- rb.css 未被 token 化的裸字面量 → 迁移对照：见 §10。
- 未被任何视图使用的 class：`chip` `draft--saved` `notice--evidence` `pill--pending` `prose` `r`（6 个，已在 rb.css 定义但无视图使用；本系统保留它们的 token，供 Vue 阶段接入）

## 9. rb.css 等价性证明

判据：rb.css `:root` 的每个变量，其**解析后字面值**必须在 tokens.css 中逐字相等。
这样已验证的响应式原型零改动继续工作，设计系统是它的严格超集。

- rb.css `:root` 变量数：**75**
- 逐值等价通过：**75**
- 不一致：**0**

## 10. 裸字面量迁移对照

rb.css 保持冻结（已独立验证），因此不改写；下表是 Vue 阶段消费 tokens.css 时的对照依据。

| rb.css 位置 | 裸字面量 | L1 token | L3 消费方 |
| --- | --- | --- | --- |
| `.btn--primary` 文字色 | `#FFFFFF ×1` | `--p-white` | --btn-primary-fg |
| `.bph` 文字色 | `#FFFFFF ×1` | `--p-white` | 评审外壳，刻意不纳入系统 |
| `.navlink:hover` 底色 | `rgba(28,25,23,.04)` | `--p-ink-900-a04` | --navlink-bg-hover |
| `--bg-readonly` 来源值 | `rgba(28,25,23,.03)` | `--p-ink-900-a03` | --bg-readonly |
| `--shadow-hair` 来源值 | `rgba(28,25,23,.04)` | `--p-ink-900-a04` | --p-shadow-1 → --elevation-card |
| `.appbar` / `.tabbar` z-index | `40 ×2` | `--p-z-appbar / --p-z-tabbar` | --appbar-z / --tabbar-z |
| `.composer` z-index | `20` | `--p-z-composer` | --composer-z |
| `.skip-link` z-index | `60` | `--p-z-skiplink` | --skiplink-z |
| `.step--running` 旋转 | `1.1s linear` | `--p-duration-spin / --p-easing-linear` | --motion-spin-duration / --motion-spin-easing |
| `.appbar__mark` 圆角 | `7px` | `--p-radius-7` | --brand-mark-radius |
| `.login__mark` 圆角 | `10px` | `--p-radius-10` | --brand-mark-radius-lg |
| `:focus-visible` 圆角 | `4px` | `--p-radius-4` | --focus-outline-radius |
| `.appbar__mark` / `.login__mark` 尺寸 | `26px / 38px` | `--p-size-mark-sm / --p-size-mark-lg` | --brand-mark-size / --brand-mark-size-lg |
| `.textarea` 最小高 | `120px` | `--p-size-textarea-min` | --control-textarea-min-h |
| `.table .cell-name` 最小宽 | `180px` | `--p-size-cellname-min` | --table-cellname-min-w |
| `.login` 最大宽 | `420px` | `--p-size-login-max` | --login-max-w |
| `.prose` 最大宽 | `68ch` | `--p-size-prose-max` | --prose-max |
| `.bubble` xs 限宽 | `88%` | `--p-size-bubble-max` | --bubble-max-w-xs |
| `.table--stack td` 字段名列宽 | `7.5em` | `--p-size-label-col` | --table-stack-label-col |
| `.kv__row` 键列宽 | `8em` | `--p-size-kv-key-col` | --kv-row-key-col |
| `.skip-link` 屏外偏移 | `-100px` | `--p-offset-offscreen` | --skiplink-offset-y-hidden |
| .pill 内边距 / 间距 | `2px 10px / 5px` | `--p-space-2px / --p-space-10px / --p-space-5px` | --pill-pad-y / --pill-pad-x / --pill-gap |
| `.table--stack td` 单元格内边距 | `5px 0` | `--p-space-5px` | --table-stack-cell-pad-y |
| `.table--compact` 内边距 | `8px` | `--p-space-8px` | --table-compact-pad-y |
| `.table--stack td.cell-name` 下边距 | `8px` | `--p-space-8px` | --table-stack-name-pad-b |
| `.input` 等纵向内边距 | `10px` | `--p-space-10px` | --control-pad-y |
| `.step__ico` 顶部偏移 | `3px` | `--p-space-3px` | --step-ico-offset-y |
| `.notice__ico` 顶部偏移 | `2px` | `--p-space-2px` | --notice-ico-offset-y |
| `.tabbar__item` 图标与文字间距 | `2px` | `--p-space-2px` | --tabbar-item-gap |
| `.field--invalid` 外描边 | `box-shadow 0 0 0 3px` | `--p-bw-3` | --control-invalid-ring |
| `.cite` 左侧色条宽 | `4px` | `--p-bw-4` | --cite-accent-w |
| `.draft` 虚线边宽 | `2px` | `--p-bw-2` | --draft-border-w |

## 11. 变更记录

- **v1.0.0** —— 首版。把 rb.css 的 74 个 :root 变量拆为 L1/L2/L3 + 兼容层；补齐 rb.css 中未 token 化的字面量：--p-white（原 #FFFFFF ×2）、--p-ink-900-a03/a04（原裸 rgba ×2）、z-index 4 档、动效时长与缓动、9 个尺寸、11 个字体/圆角/边宽档位。
- **v1.1.0** —— 阶段 A（实现期）修复：L3 的 root 组新增 --root-scroll-offset（值 calc(var(--shell-appbar-h) + var(--p-space-1))，解析值 calc(56px + 6px)），供 rb.css:94 的 html{scroll-padding-top} 消费，锚点与 skip-link 不再被 sticky 顶栏遮挡（W1）。token 总数 518 → 519（L1 91 / L2 41 / L3 336 → 337 / L0 50）；rb.css 的 :root 变量 74 → 75，等价性检查 75/75。之所以写 var(--shell-appbar-h) 而不是 var(--appbar-min-h)：后者会让 L3 引用 L3，被 verify-system.py 的 B 项「L3 不互引」判 FAIL，两者解析值相同。
