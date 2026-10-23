# 阶段性进展与任务台账

- **文档编号**：CCA-PHASE-001
- **快照时间**：2026-10-23
- **当前 HEAD**：分支 `docs/align-rb-fix` @ `573e63a`；工作区干净
- **性质**：**状态台账**。只记录「已经做了什么、证据在哪、还剩什么」。需求与设计真源仍是 `docs/` 与 `design/`，本文件不复制它们。

---

## 1. 一览

| 阶段 | 范围 | 状态 | 验收依据 |
| --- | --- | --- | --- |
| **0** 设计阶段（前序） | 需求 → 详细设计 → UI/UX 设计系统 | ✅ **已完成**（本会话之前） | `design/` 各 `verification.md`；本文件只做状态承接 |
| **A** 设计系统必修项修复 | 修 6 项「实现期必修」缺陷 + 顶栏窄带治本 | ✅ **已完成并独立验证** | [`design/reviews/rb-verify-report.md`](../design/reviews/rb-verify-report.md)（6 项全 PASS） |
| **B** Vue 3 可运行骨架 | `web/` 落地：store / 路由 / SSE / 组件 / 视图 / mock | ✅ **已完成并冒烟验证** | [`web/BUILD-REPORT.md`](../web/BUILD-REPORT.md)；本文件 §3.3 冒烟记录 |
| **C** 版本控制 | 初始化仓库、分支策略、基线提交 | ✅ **已完成** | 本文件 §4；[`CONTRIBUTING.md`](../CONTRIBUTING.md) |
| **D** 文档对齐 | 结清阶段 A 遗留的文档待同步清单 | ✅ **已完成** | [`DOC-SYNC-PENDING.md`](frontend-detail/DOC-SYNC-PENDING.md) 开头小结 |
| **E** 下一阶段（未开工） | 接真实后端、补交互、组件代码生成 | ⬜ **未开始** | 见 §6 |

**当前可运行状态**：`web/` 可 `pnpm build` 成功、`pnpm dev` 可起，mock 数据下**登录 → 助手（SSE 流式）→ 课表 → 计划 → 管理中心**全链路可点通（§3.3）。

---

## 2. 阶段 A：设计系统必修项修复 ✅

### 2.1 完成清单

依据 `design/system/README.md`「收口裁决与遗留缺陷」与前端详细设计 §8.4，这 6 项原本被登记为「冻结期内不改、实现期必修」。**全部已修**：

| 项 | 缺陷 | 修法 | 独立验证 |
| --- | --- | --- | --- |
| **W1** | 缺 `scroll-padding-top`，锚点/skip-link 被 sticky 顶栏遮挡 56.4–56.7px | `rb.css` 的新 token `--root-scroll-offset`（= 56+6 = 62px），`html{scroll-padding-top}` 消费它 | **PASS**：13 个宽度实测遮挡 **0px** |
| **W1-b** | 追加：768–774px 顶栏因 navlink 换行升到 **72.17px**，使 62px 失效（仍遮 10px） | `.navlink` / `.appbar__user` 加 `white-space:nowrap` | **PASS**：18 个宽度顶栏恒 56.67px，页面溢出恒 0 |
| **W2** | `.steps__toggle` 聚焦无可见焦点（WCAG 2.4.7） | `<480` 给 `.steps__summary` 加 `:focus-visible` 补偿环；`≥480` 按裁决 J2 直接 `display:none` | **PASS**：真实 Tab 第 14 焦点命中，像素取证 1554 个焦点色像素全在环带 |
| **W3a** | `.kv__row` 的 `1fr` 下限是 min-content，第 2 轨被撑到 657.9px | 改 `8em minmax(0,1fr)` | **PASS**：注入 60 字符无空格串，溢出 0（基线 +444） |
| **W3b** | `.cite__name` / `.card__body` / `.bubble` 无断点 | 三处加 `overflow-wrap:anywhere`（表格单元格保持 `break-word` + `min-width`，未误伤） | **PASS**：三处溢出 0，按根因反注入分别回落 |
| **#1** | 「处理中」误用琥珀警告态（2 处） | `parts/admin.html:232`/`:302` → `pill--info`；`:519`「需确认后继续」**保持 warn 未误改** | **PASS** |
| **#3** | 危险胶囊「不可恢复」自身缺图标 | `parts/records.html:273` 补 24×24 内联 SVG，六项属性合规格 | **PASS** |
| **#6** | 密码显示/隐藏按钮文案与 `aria-pressed` 从未冻结 | `content-spec.md` **只冻结契约**；`login.html` MD5 未变（**未越界实现控件**） | **PASS** |

### 2.2 附带修复

- `design/responsive/shell.html` 的 `#main` 补 `tabindex="-1"` —— skip-link 跳转后焦点真正落到主内容（原 `activeElement` 是 `BODY`）。
- `design/system/components/01-shell-navigation.md` **范围外改动**：新 token 进了 `root` 组，`verify-system.py` 的「组内 token 未覆盖」是 FAIL 级，不补规格必失败。改动经独立验证确认**契约骨架完好**（`owns` 逐字未变、10 块 × 9 节结构完整），并已由 Lead **追认**。

### 2.3 独立验证判定

| 判据 | 结果 |
| --- | --- |
| 6 项必修 | **全部 PASS**，无必修级新缺陷 |
| 反向注入（证明判据真的会 FAIL） | W1 关掉 → 遮挡回 57px；W2 关掉 → 0 像素；W3 按根因分别回落；副本改 `--h-appbar` → `FAIL 2` exit 1 |
| 5 个校验脚本 | 全部 0 FAIL（含 `verify-system` PASS 31） |
| token 等价 | **两条独立通路**（自写解析器 + 真实浏览器 CSSOM）均为 **75/75、0 diff** |
| 六宽度页面级溢出 | **全部 0**（外加 18 宽度扫描） |

### 2.4 本轮最有价值的发现

独立验证者在**修复之前**就抓到：`.appbar` 在 **768–774px（7 个整数宽度）** 会因 navlink 文字换行升到 **72.17px**（根因：固有宽 723 vs 可用 717，缺 6px）。后果是：

1. 文档给的 `scroll-padding-top: 62px` 在这段窄带**不够**，目标仍被遮 10px；
2. **更严重**：文档 §8.4 自带的判据 `#main.top >= 61.5` 在此时是 `62.17` → **恰好通过，放行了一个仍然存在的遮挡**。

这条只有靠「修复前先量一遍 + 用比文档更强的判据」才能发现。后续据此**改掉了该判据**（见阶段 D）。

---

## 3. 阶段 B：Vue 3 可运行骨架 ✅

### 3.1 完成清单

`web/` 共 **117 个源文件 / 574 KB**（不含 `node_modules` 与 `dist`），其中 **53 个 `.vue`**。

| 模块 | 内容 | 依据 |
| --- | --- | --- |
| 状态管理 | **8 个 store**（名字取自冻结集合） | 前端详细设计 §6 |
| 路由 | **10 条路由** + 守卫链 G1–G4；对话正文不进 URL，唯一私有深链 `/me/plans/:planId` | §7、DEC-01 |
| 流式客户端 | SSE **字节级解析 P1–P12**（分包/编码边界/`id` 与 `seq` 冲突裁决）+ §5.4 状态机（终态唯一、「HTTP 关闭 ≠ 终态」） | §5；`sse_events_v0.1.schema.json` |
| 组件 | **27 个组件族** base + 5 个 product 组合件 | §10；`design/system/components/01–04*.md` |
| 视图 | **10 个视图**（S01–S12） | §9 |
| mock 层 | 同源 `/api/v1`，SSE 用真 `ReadableStream` 且**故意按 7 字节切片**以真实覆盖多字节边界 | §14.3；零外部请求 |
| 样式 | `global.css` + 27 族 `base.css`，**只消费 L3 token** | §8.2 门禁 |
| 工具 | `scripts/`：token 同步校验、10 项不变量、SFC 编译检查、纯函数 SSE 冒烟、门禁反向自测 | — |

### 3.2 验收证据（每项都已由 Lead 独立复跑确认）

| 证据 | 结果 |
| --- | --- |
| `tokens.css` / `tokens.ts` 与 `design/system/` | **逐字节一致**（`26EEE4F0…` / `03607588…`） |
| `vue-tsc --noEmit`（strict） | exit 0，**0 error** |
| 53 个 `.vue` 走真实 SFC 编译 | **53/53 PASS** |
| 10 项机械不变量 | **10/10 PASS** |
| 纯函数级流式冒烟 | **24/24 PASS** |
| stylelint 分层纯度门（5 条自定义规则） | **0 warning** |
| 门禁反向注入自测 | **12/12 被证明会 FAIL**，还原后全绿 |
| `pnpm build` | **✓ built in 1.96s，exit 0**，31 个产物（`index.html` 585 B / CSS 34.5 kB / vendor 98 kB） |
| `pnpm dev` | 起得来（`::1:5173`），首页 HTTP 200 |

### 3.3 真实浏览器冒烟（Edge via CDP）

对运行中的应用做了真实点击与真实键盘，**不是脚本自述**：

| 步骤 | 观察到的结果 |
| --- | --- |
| `/login` | 标题「登录 · 校园课程智能助手」；文案逐字命中 `content-spec`（含「登录会话有效期 2 小时…」）；skip-link 为第一个可聚焦元素 |
| 错误凭据 | 显示「账号或密码不正确，请重试。」——**不区分账号不存在/密码错**（SRS 要求） |
| 正确凭据登录 | → `/assistant`，导航出现「林晓」 |
| `/assistant` 空闲态 | 标题、能力说明、边界提示条、三个示例入口、「最多 2000 字」、`0 / 2000` 全对 |
| 提交问题 | **SSE 流式逐段出现**：「正在处理 · 最长 60 秒」+「停止」→「正在读取课表 · 2026-10-22（周四）」→「正在检索课程资料 ·『实验课 预习要求』」→「正在拟定计划草稿」→ token 文本流入 |
| 流式完成态 | 引用卡（文件名 + **第 12 页** + 展开片段）；草稿标记 **「未保存」**；**「待确认」**而非失败（「写入结果尚未确认，请勿重复创建…」+「查询写入状态」）；依据类型分列「本人课表」「课程资料」；「重复提交同一操作只会得到同一份计划」 |
| `/me/schedules` | 课程名/时间/地点表；「单次最多查询 31 天」；「时间为学校时区 Asia/Shanghai」 |
| `/me/plans` | 列表 + 按标题筛选；`未设置日期`、`助手生成` / `手动创建` |
| 管理端 | 学生身份**无** `/admin` 入口、无「管理中心」；`admin_demo` 登录后出现 `/admin/courses`，课程表与状态胶囊正常渲染 |
| 整页刷新 | 会话失效并回 `/login` —— **正面验证 DEC-01**（令牌仅内存、刷新需重登） |
| 无障碍 | 流式文本旁存在 `.sr-only` + `aria-live="polite"` + `aria-atomic="true"` 播报区（**这是正确做法，不是重复渲染**） |

### 3.4 一次被撤回的方向错误（记以免重犯）

骨架作者最初为绕过沙箱限制（见 §5）自写了 loader / SSR 钩子以获取「渲染证据」。Lead 判定这属于**给环境缺陷造基础设施**——会让「项目能跑」这个结论只在自建通道下成立，是**假阳性**。已撤回 3 个文件，只保留 1 个最小解析钩子（仅 `@/` 别名 + `.ts` 扩展名，**不挂 `load`、不做渲染**），并明确标注「不用它证明任何构建结论」。撤回清单见 `web/BUILD-REPORT.md` §7.6。

---

## 4. 阶段 C：版本控制 ✅

### 4.1 仓库结构

```
* 139a4eb  (docs/phase-status)   docs: 新增阶段性进展与任务台账 PHASE-STATUS.md（本文件）
* 573e63a  (docs/align-rb-fix)   docs: 结清阶段A 待同步清单（判据、计数、冻结哈希、既有瑕疵）
* f23ad27  (feat/phase-a-design-fixes-and-vue-skeleton)
                                 feat: 阶段A 设计系统必修项修复 + 阶段B Vue3 可运行骨架
* d813862  (main)                chore: 初始化仓库基线（空提交）
```

四个提交**严格线性**（每个分支都是前一个的直接子节点），因此可以**快进合并**到 `main`，无需解决冲突。

设计意图：`main` 是**纯基线**（空提交），实际工作落在阶段分支上，便于后续按阶段回看与挑选合并。

### 4.2 卫生状况

| 项 | 值 |
| --- | --- |
| 受控文件 | **199 个** |
| `.git` 体积 | 2.54 MB |
| `git fsck` | 无输出（数据库完好） |
| 工作区 | **干净**（dirty = 0） |
| `node_modules` / `dist` / `.pnpm-store` 入库 | **0 / 0 / 0**（76.8 MB + 77.4 MB 已由 `.gitignore` 排除） |
| 提交粒度 | 阶段 A+B 一个提交、文档对齐一个提交；提交信息含「重跑了哪些校验器及结果」 |

分支与测试节奏的团队约定见 [`CONTRIBUTING.md`](../CONTRIBUTING.md)：分支命名、冒烟/回归/全量三档测试、**会级联的文件**清单、以及 §5 的环境限制。

---

## 5. 阶段 D：文档对齐 ✅

阶段 A 修完之后，一批文档里的**写死数值与判据**已经与事实不符。当时**有意不立即改**：主文档是生成物，改它会让「已通过验证」的字节与仓库当前字节不一致。因此先建成登记册，随后在独立分支一次改完、一次重建、一次机械复核。

| TODO | 处置 | 实际改法 |
| --- | --- | --- |
| **TODO-1** §8.4 判据 | ✅ | 判据换成**实测遮挡量** `occlusion = appbar.bottom − target.top ≤ 0.5px`，并**补齐 768/772/774**；删掉对 `#main` 恒为 false 的 `top >= 61.5` |
| **TODO-2/3** 计数 518→519 | ✅ | `design/README.md`、`docs/frontend-detail/build.py:408`（主文档那句的真正来源）、`build.py:45`（移出已落地的处方 token）；分册 `10-…:13`、`50-…:4/14/39/142/153`、`90-…:28` |
| **TODO-4** 冻结哈希 | ✅ | `design/responsive/verification.md` 加 **superseding 声明块**（保留原哈希不改写）；主文档 §8.6 表**新增「阶段 A 已完成」行** |
| **TODO-5** 既有瑕疵 | ✅ | `components/02-actions-status.md:375` 的 `.pill--ok` 出处改正（原写 `records.html:203`，实为 `.pill--evidence`；真实实例逐一核到 `assistant.html:130/142/249/261/536`、`admin.html:67/279`） |
| **TODO-6** 判据缺口 | ⬜ **有意保留** | `verify-system.py` 仍无「规格消费表解析值 vs `tokens.flat.json`」比对。这是**新增判据**，不是文档同步 → 归入 §6 下一阶段 |

**证据纪律**：两份历史验证报告内的旧哈希与旧计数**一律保留原值、只加注**——它们是当时的实测记录，回溯改写会破坏证据链。

**重建结果**：主文档 `366,448 B / 4,388 行`，MD5 `725BECD070AA1FA8172499ECEB91CE04`，组装 **0 FAIL**，重跑哈希稳定（可复现）。

---

## 6. 未完成 / 下一阶段（**均未开工**）

### 6.1 工程任务

| # | 任务 | 说明 | 依据 |
| --- | --- | --- | --- |
| E1 | **接真实后端** | 去掉 mock 传输层，接 `/api/v1`；`VITE_USE_MOCK=false` 已预留 | 前端详细设计 §14.3 |
| E2 | **补 TODO-6 判据** | 给 `verify-system.py` 加「规格消费表解析值 ↔ `tokens.flat.json`」比对（目前无判据覆盖，与 README 的 M1 教训同源） | `DOC-SYNC-PENDING.md` |
| E3 | **Vue 侧代码生成** | `tokens.json` 已是机器可读真源，可产 Tailwind theme / Figma variables / 组件类型定义 | `design/README.md` §下一步 5 |
| E4 | **补交互** | 原型与骨架目前是状态展示为主；可补引用展开、重叠确认等更细交互 | `design/README.md` §下一步 4 |
| E5 | **接入真实测试** | 目前只有机械不变量 + 纯函数冒烟；Vitest / Playwright 骨架位置已预留，未铺用例 | §15 |
| E6 | **`.sr-only` 防回归** | 把「流式播报区」这类无障碍结构纳入不变量检查 | 本文件 §3.3 |
| E7 | **`prefers-reduced-motion` 实测** | 未做真实动效路径验证 | 阶段 A 未验证项 |

### 6.2 明确未验证项（不要当成已通过）

| # | 未验证内容 | 原因 |
| --- | --- | --- |
| U1 | **只测了 Edge 一个引擎** | SRS 只要求 Chrome/Edge，但 Firefox/Safari 未测 |
| U2 | **`env(safe-area-inset-*)` 恒为 0** → T6 刘海/圆角屏未验 | 需真机 |
| U3 | **屏幕阅读器未实听** | 无障碍结论全部是 DOM/CSS/像素层证据，无 NVDA/JAWS/VoiceOver |
| U4 | 视口宽度来自 CDP `Emulation.setDeviceMetricsOverride` | 是等价夹具，非物理拖窗 |
| U5 | `01-shell-navigation.md` 的**逐行 diff 边界** | 无改动前副本。**改动事实已确认**（前后哈希不同 + mtime + 旧哈希不匹配任何现存文件），但「恰好 +1 行 + 5 处替换」未验证 |
| U6 | `prefers-reduced-motion` 实际行为 | 见 E7 |
| U7 | 真实后端联调、性能目标（P95 ≤1s / ≤10s） | 无后端；文档已把该指标归给服务端与部署 |

### 6.3 已知非阻塞残留

- **768–773px 顶栏右内边距视觉收缩**：18px → **11.67px**（胶囊仍在边框盒内 11.67px，**无裁切、无溢出**），774px 起恢复。
- **4 处无图标的胶囊**（`records.html` 的另两个等）——阶段 A 只修了 `#3` 点名的那一处，其余按 `02-actions-status.md` 既有登记处理。

---

## 7. 环境限制（不是代码问题）

**DSH 沙箱内 `pnpm build` / `pnpm dev` 会失败**：沙箱拒绝 `child_process` 的 `stdio:'pipe'`，而 Vite 用它启动 esbuild 服务并 bundle 配置文件。

实测边界（三阶段）：
1. `vite build` + `vite.config.ts` → 死在 `bundleConfigFile`；
2. 换纯 `.mjs` 配置文件 → 同一位置（Vite 无条件走 esbuild bundling）；
3. programmatic API + `configFile:false` + `esbuild:false` → **越过配置阶段**（`✓ building for production`），改死在 `[commonjs--resolver]`。

**关键区分**：`esbuild` 原生 CLI **完全可用**（`--version` → `0.25.12`；`--bundle` 产出 93 B 产物），**只有 Node 的管道通道被拒**。所以这是**通道问题、不是工具缺失**——同一份代码在沙箱外（本机终端直接运行）是正常的。

> 本会话后期沙箱策略被放开为 `danger-full-access`，`pnpm build` 随即**成功**（§3.2）。§7 保留为「若在受限策略下复现」的说明。

---

## 8. 交付物索引

| 交付物 | 路径 |
| --- | --- |
| 前端可运行骨架 | [`web/`](../web/) |
| 骨架构建与验收报告 | [`web/BUILD-REPORT.md`](../web/BUILD-REPORT.md) |
| 协作约定（分支/测试/级联/环境限制） | [`CONTRIBUTING.md`](../CONTRIBUTING.md) |
| 阶段 A 修复报告 | [`design/reviews/rb-fix-report.md`](../design/reviews/rb-fix-report.md) |
| 阶段 A 独立验证报告 | [`design/reviews/rb-verify-report.md`](../design/reviews/rb-verify-report.md) |
| 文档待同步登记册（已结清） | [`DOC-SYNC-PENDING.md`](frontend-detail/DOC-SYNC-PENDING.md) |
| 前端详细设计（生成物，16 章） | [`校园课程智能助手_前端详细设计_v0.1.md`](校园课程智能助手_前端详细设计_v0.1.md) |
| 设计系统（三层 token + 组件规格） | [`design/system/`](../design/system/) |
| 响应式原型 | [`design/responsive/b-responsive.html`](../design/responsive/b-responsive.html) |
| 本文件 | `docs/PHASE-STATUS.md` |

---

## 9. 复现命令

```powershell
$env:PYTHONIOENCODING="utf-8"

# 设计系统 / 原型 / 详细设计（6 个校验器，全部必须 0 FAIL）
python design\system\generate.py
python design\system\build-system.py
python design\system\verify-system.py
python design\responsive\build.py
python design\reviews\verify.py
python docs\frontend-detail\build.py

# 前端骨架
cd web
pnpm install
pnpm build
node node_modules\vue-tsc\bin\vue-tsc.js --noEmit -p tsconfig.json
node scripts\check-sfc.mjs
node scripts\invariants.mjs
node scripts\sync-tokens.mjs --check
node node_modules\stylelint\bin\stylelint.mjs "src/**/*.{css,vue}"
node --import ./scripts/ts-alias-hook.mjs scripts\smoke-sse.mjs
pnpm dev     # http://localhost:5173/  mock 账号 student_demo / demo1234、admin_demo / demo1234
```
