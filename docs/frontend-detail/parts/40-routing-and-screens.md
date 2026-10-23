<!-- part: 40-routing-and-screens; chapters: 7,9; owner: sys-shell -->

## 7. 路由与导航

本章定义**唯一的路由真源落地方式**：路由表照抄 `CONTRACT.md` §3.3 的 10 条（不得增删路径），`meta` 为本章新补；守卫链、导航换形态、深链范围与「对话正文不进 URL」的代价在此收口。组件外观不在此重复——需要时指向 `design/system/components/01-shell-navigation.md`。

### 7.1 冻结路由表（10 条 + `meta`）

> 前 5 列逐字来自 `CONTRACT.md` §3.3；后 4 列为本册补的 `meta`。**路径、name、视图名不得改动**。

| 路径 | name | 视图 | 屏幕 | 守卫（契约原文） | `requiresAuth` | `requiresAdmin` | `title`（`document.title`） | `activeNav` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/login` | `login` | `LoginView` | S01 | 已登录则重定向到 `assistant` | 否 | 否 | 登录 | — |
| `/assistant` | `assistant` | `AssistantView` | S02–S06 | 需会话；**登录后默认页** | 是 | 否 | 助手 | `assistant` |
| `/me/schedules` | `schedules` | `MyScheduleView` | S07–S08 | 需会话 | 是 | 否 | 我的课表 | `schedules` |
| `/me/plans` | `plans` | `PlansView` | S09 | 需会话 | 是 | 否 | 学习计划 | `plans` |
| `/me/plans/:planId` | `planDetail` | `PlanDetailView` | S09 详情 | 需会话 | 是 | 否 | 学习计划 | `plans` |
| `/admin/courses` | `adminCourses` | `AdminCoursesView` | S10 | 需会话 + 管理员 | 是 | 是 | 管理中心 · 课程管理 | `admin` |
| `/admin/documents` | `adminDocuments` | `AdminDocumentsView` | S11 | 需会话 + 管理员 | 是 | 是 | 管理中心 · 文档与批次 | `admin` |
| `/admin/document-batches/:batchId` | `adminBatch` | `AdminBatchView` | S11 批次 | 需会话 + 管理员 | 是 | 是 | 管理中心 · 文档与批次 | `admin` |
| `/admin/schedules` | `adminSchedules` | `AdminScheduleView` | S12 | 需会话 + 管理员 | 是 | 是 | 管理中心 · 课表维护 | `admin` |
| `/admin/students` | `adminStudents` | `AdminStudentsView` | 管理 · 学生（`content-spec` 无屏幕块） | 需会话 + 管理员 | 是 | 是 | 管理中心 · 学生账号 | `admin` |

**`title` 的来源**：`content-spec.md` S01「登录」(`content-spec:51`)、S07「我的课表」(`:112`)、S09「学习计划」(`:128`)、S10「管理中心 · 课程管理」(`:140`)、S11「管理中心 · 文档与批次」(`:150`)、S12「管理中心 · 课表维护」(`:163`)、S02 助手 (`:61`)。最后一行的「管理中心 · 学生账号」**没有 content-spec 依据**，是为满足 `FR-AUTH-003`（学生账号维护）与 `CONTRACT.md` §3.3 路由而**登记待冻结**的标题（见 §9.15 T1）。

**`activeNav` 的取值域**＝4 个一级入口，取自 `tokens.json` → `--tabbar-cols` 的 `d`（「一级入口数：助手/课表/计划/管理」）：`assistant | schedules | plans | admin`。`/login` 为 `undefined`（登录屏不渲染主导航）。映射到顶栏/标签栏文案见 §7.4。

**列表状态不进 URL（判断项 J1）**：`GET /me/plans` 的 `title` 筛选、`GET /admin/*` 的 `query/enabled/page` 等**分页与筛选状态只存在 store**，不写进 query string。依据：本册的深链口径只有 `/me/plans/:planId`（§7.6），`HLD-D11` 不承诺跨刷新恢复视图状态。若产品要「可分享的筛选结果」，需先改这条口径。

### 7.2 `meta` 类型与约定

```ts
// router/routes.ts
import type { RouteRecordRaw } from 'vue-router'

export interface ShellMeta {
  requiresAuth: boolean          // false 仅 /login
  requiresAdmin: boolean         // 5 条 /admin/* 为 true，其余 false
  title: string                  // 写入 document.title（见 7.1 表）
  activeNav?: 'assistant' | 'schedules' | 'plans' | 'admin'  // 4 个一级入口之一
}

declare module 'vue-router' {
  interface RouteMeta extends ShellMeta {}
}
```

| 约定 | 值 | 依据 |
| --- | --- | --- |
| 路由模式 | vue-router 4 **history** | `CONTRACT.md` §3.1 |
| 未匹配路径 | **不新增路由记录**；在 `router.beforeEach` 内用 `to.matched.length === 0` 判定后重定向 | 契约 §3.3 只有 10 条，`CONTRACT.md` §3.1「不得自创」 |
| `document.title` | `route.meta.title` + 固定后缀「· 校园课程智能助手」 | 产品名取自 `content-spec:52`；后缀写法为**判断项 J2**（未在任何真源冻结） |
| 滚动行为 | `scrollBehavior` 返回 `{ top: 0 }`（新路由）与 `{ el: to.hash }`（同页锚点）；**依赖 W1 的 `scroll-padding-top`** | §7.6 |
| 视图与外壳 | 10 条路由共用 `App.vue` 外壳（顶栏/标签栏/`<main id="main">`）；`/login` 是否套外壳见 §7.6 (P3) | `CONTRACT.md` §3.2 |

### 7.3 守卫链（顺序即优先级）

`router/guards.ts` 导出单个 `beforeEach`，按 G1→G4 顺序判定；G5–G8 是运行期分支（不在 `beforeEach` 内）。

| 序 | 条件 | 动作 | 依据 |
| --- | --- | --- | --- |
| **G1** 未匹配（404） | `to.matched.length === 0` | 未登录 → `login`；已登录 → `assistant`。**不渲染「页面不存在」文案**（无冻结文案），也不新增 catch-all 路由记录 | 契约 §3.3 冻结 10 条；`CONTRACT.md` §3.7-3 |
| **G2** 未登录 | `to.meta.requiresAuth && !session.token` | 重定向 `login`；把 `to.fullPath` 存 `session.pendingPath`（**内存，不写 URL**），仅当 `to.name === 'planDetail'` 时登录后回跳，其余一律回 `assistant` | §7.5 / §7.6 |
| **G3** 已登录访问登录页 | `to.name === 'login' && session.token` | 重定向 `assistant` | 契约 §3.3 第 1 行 |
| **G4** 非管理员 | `to.meta.requiresAdmin && session.user?.role !== 'admin'` | 重定向 `assistant` + `ui` 播报一次失败提示；**不重试、不重定向到管理页** | SRS §8 403 行「返回可访问页面，不重试」；`FR-AUTH-004` |
| **G5** 会话失效（运行期） | 任一端点返回 401 `AUTH_REQUIRED`/`SESSION_EXPIRED`；或 SSE `error` 事件 `code` 为这两者 | `session.clear()` → 清空 chat/drafts 临时态 → 跳 `login`；**不提示具体资源** | SRS §8 401 行；`CONTRACT.md` §3.5 error 行（该事件不得携带 `plan_id`/`operation_id`）；`FR-AUTH-002` |
| **G6** 刷新页面 | 令牌在内存（`HLD-D03`）→ 刷新后 `session.token` 为空 | 自然落到 G2：**刷新即回登录页**是设计行为，不是缺陷 | `HLD-D03`「浏览器仅内存保存…刷新后需重新登录」；SRS `DEC-01` |
| **G7** 登录成功 | `POST /auth/login` 200 后 | `await GET /me`（补齐 `capabilities`、`school_timezone`、`session_expires_at`）→ 再放行；`pendingPath` 为 `planDetail` 则回跳，否则 `assistant` | `openapi /api/v1/me`；`FR-AUTH-001` |
| **G8** 登出 | `POST /auth/logout` | 无论 200 还是 401，一律 `session.clear()` + 跳 `login` + 清空问答与草稿引用 | `FR-AUTH-002`「登出应撤销当前会话并清除浏览器临时身份、问答和草稿引用」 |

**守卫不做的三件事**（避免与其它章重复）：

1. 守卫**不预取页面数据**（列表首屏请求在视图 `onMounted` 内发起），因此守卫不持有 `schedules/plans/admin` store。
2. 守卫**不判细粒度能力**：`role` 决定 G4；`Me.capabilities`（`array<string>`，枚举未在 openapi 冻结）只做功能开关的数据源，**不发明 capability 字符串**（判断项 J3，见 §9.15）。
3. 守卫**不做轮询**：`writeOps` 的 `operation_id` 核实与批次状态轮询都在视图/store 内（见 §9.6、§9.11）。

```mermaid
flowchart TD
  A[导航请求] --> B{to.matched 为空?}
  B -- 是 --> C{有令牌?}
  C -- 否 --> L[/login/]
  C -- 是 --> AS[/assistant/]
  B -- 否 --> D{requiresAuth 且无令牌?}
  D -- 是 --> L
  D -- 否 --> E{name=login 且有令牌?}
  E -- 是 --> AS
  E -- 否 --> F{requiresAdmin 且 role≠admin?}
  F -- 是 --> AS2[/assistant/ + 提示]
  F -- 否 --> G[渲染视图]
```

### 7.4 导航换形态与当前项

形态切换点**只有一个：`768px`**（`tokens.json` → `breakpoint.sm`）。外观与状态细节在 `components/01-shell-navigation.md`，此处只定行为契约。

| 断点 | 顶栏内联 `.appbar__nav` | 底部标签栏 `.tabbar` | 组件规格 |
| --- | --- | --- | --- |
| `< 768`（base–xs） | `display:none`（`rb.css:136`） | `display:grid;repeat(4,1fr)`（`rb.css:151`） | `components/01-shell-navigation.md` §2 AppBar · §5 Tabbar |
| `≥ 768`（sm 起） | `display:flex`（`rb.css:146`） | `display:none`（`rb.css:161`） | `components/01-shell-navigation.md` §4 NavLink · §6 TabbarItem |

| `activeNav` | 顶栏文案（≥768） | 标签栏文案（<768） | 目标路由 | 文案来源 |
| --- | --- | --- | --- | --- |
| `assistant` | 课程助手 | 助手 | `/assistant` | `content-spec:61`（S02 标题同产品名）+ `--tabbar-cols` 的 `d` |
| `schedules` | 我的课表 | 课表 | `/me/schedules` | `content-spec:112`（S07 页面标题） |
| `plans` | 学习计划 | 计划 | `/me/plans` | `content-spec:128`（S09 列表标题） |
| `admin` | 管理中心 | 管理 | `/admin/courses` | `content-spec:140`（S10 区块名） |

- **当前项**：`aria-current="page"` 加在 `activeNav === route.meta.activeNav` 的那一个 `<a>` 上；`/me/plans/:planId` 与 5 条 `/admin/*` 都分别归属 `plans` 与 `admin`（§7.1 表）。样式：顶栏三色（主色+底色+600），标签栏两色（主色+600）——`components/01-shell-navigation.md` §4/§6 状态矩阵。
- **只渲染一个可见导航**：两套载体共用同一份 4 项数据与同一个 `activeNav`，可见性交给媒体查询，**不在 JS 里按宽度增删节点**。
- **触控目标**：顶栏项 ≥44px（`rb.css:139`），标签栏项 ≥56px（`rb.css:156`）；320px 下标签栏每项宽 320÷4=80px。
- **层级**：`.appbar`/`.tabbar` `z-index:40`，跳过链接 `z-index:60`（`rb.css:122/150/115`）；焦点不得被粘性栏遮挡（WCAG 2.2 2.4.11）→ 依赖 W1。
- **管理端入口**：`admin` 项对 `role==='admin'` 才渲染（`FR-AUTH-003`「不得授予管理员的界面」反向约束：学生不显示管理入口）。渲染条件用 `session.user.role`，不用 `capabilities`。

### 7.5 为什么助手对话不进 URL（含代价）

依据链：SRS `DEC-01`（`SRS:103`「浏览器内存保存当前会话；刷新、退出、关闭页面后不保证恢复」，明确 `CHAT-03`）、`FR-CHAT-002`（临时上下文与可信度）、`HLD-D11`（「对话正文只驻留浏览器和运行内存…不承诺正文断线续传或跨设备恢复」）、`HLD-D03`（令牌仅内存）、`NFR-SEC-002`（令牌不进 URL）。

| 项 | 做法 | 依据 |
| --- | --- | --- |
| 路由形态 | `/assistant` **不带 `?q=`、不带对话 id、不带轮次序号**；一轮问答不产生新的 history 记录 | 契约 §3.3 末尾；`HLD-D11` |
| `conversation_id` | 只存在 `chat` store 内存 + `ChatInput.conversation_id` 请求体；首轮可不传，由服务端分配（`status` 事件 `code=ACCEPTED` 时必带 `conversation_id`） | `openapi /chat/stream`；SSE schema `status` 行 |
| 轮次数据 | `chat` store 内存（`HistoryMessage{role,content}`，`FR-CHAT-002` 只接受 user/assistant，上限 20 问答对＝`SRS §3.2`） | `FR-CHAT-002`；`SRS §3.2`「传入历史轮数 20」 |
| 令牌 | 只存 `session` store 内存字段；**不进 URL/localStorage/sessionStorage/IndexedDB/遥测/文件名/错误栈** | `HLD-D03`；`NFR-SEC-002`；`CONTRACT.md` §3.7-4 |
| 清空时机 | 登出、账号切换、用户点「清空对话」、刷新（内存丢失）都清空临时上下文；清空前说明不删除已保存计划 | `FR-CHAT-002`；`content-spec:64`（S02 边界提示条逐字） |

**代价（必须写清，不是遗漏）**

| 代价 | 具体表现 | 是否接受 |
| --- | --- | --- |
| 浏览器**后退键无法在对话轮次之间移动** | 每轮问答不产生 history 记录，后退会直接离开 `/assistant`（回到上一个路由，通常是 `/me/plans` 或上一入口），不会回到「上一轮回答」 | 接受：`DEC-01` 只承诺内存级临时上下文 |
| **前进键**同理，不能重放上一轮；也不能用「后退再前进」找回已流式输出的正文 | 刷新/离开后 `chat` store 清空 | 接受 |
| **无法分享某一轮问答**：分享链接只能指向 4 个一级入口 | 无对话 id，链接不能定位轮次 | 接受；`HLD-D11` |
| **多标签页各自独立**：两个标签的助手会话互不可见 | 令牌在各自内存 | 接受；`HLD-D11` |
| 断线后**不自动重连、不续传**，只能由用户显式重发（新 `request_id`） | 无 URL 可回放 | 接受；`HLD-D07`、`FR-CHAT-005`、契约 §3.5 断线行 |
| 唯一例外：**计划详情可深链** | `/me/plans/:planId` 是唯一对外可寻址的私有资源 | 需要：`FR-PLAN-005`「提供 plan_id 和详情入口」 |

**对用户可见的承诺**只有一条，且已冻结：`content-spec:64`「对话只保存在当前浏览器标签页，刷新或关闭后不会恢复；已保存的计划不受影响。」——实现时该条必须出现在 S02 边界提示条，不得改写、不得省略后半句。

**反向假设**：若产品要求「刷新后回到上轮对话」，必须改成服务端持久化会话，与 `DEC-01`/`HLD-D11` 直接冲突，属**改契约**而非改前端。

### 7.6 深链范围与前置条件

| 项 | 口径 | 依据 |
| --- | --- | --- |
| 允许的深链集合 | **仅 `/me/plans/:planId`**（+ 公开的 `/login`） | task-12；`FR-PLAN-005` |
| 其余 `requiresAuth` 路由的登录前 URL | **不恢复**，登录后统一到 `/assistant` | §7.5；`DEC-01` |
| `/assistant` 的参数 | 无（连 `?q=` 都没有） | 契约 §3.3 |
| 计划详情的授权 | 非本人计划按 `RESOURCE_NOT_FOUND` 404 处理，不显示目标是否存在 | `FR-AUTH-004`；SRS §8 404 行 |
| skip-link | `.skip-link` → `#main`；`<main id="main">` 由 `App.vue` 提供，**10 条路由的所有视图内都必须存在**（否则跳过链接目标缺失） | `components/01-shell-navigation.md` §7；`b-responsive-spec.md` §7 |
| 锚点/跳转偏移 | `html{scroll-padding-top:calc(var(--appbar-min-h) + var(--sp-1))}`（**W1 修的正是这条**） | W1；`design/system/README.md:206–211` 实测遮挡 56.4–56.7px |
| 同页锚点 | 产品页面不提供页内目录；仅有 `#main` 一个目标 | 评审期屏幕导航不进产品（`components/01-shell-navigation.md` 族概览「原型双角色」） |

**实现前置条件（不改冻结产物，但必须在 Vue 落地前修掉）**

| 编号 | 与本册的关系 | 影响的路由/屏幕 |
| --- | --- | --- |
| **W1** | 无 `scroll-padding-top` → `#main` 与任何锚点跳转被顶栏遮 56.4–56.7px | 全部 10 条路由；§7.4 当前项跳转、SkipLink |
| **W2** | `.steps__toggle` 聚焦无可见焦点（WCAG 2.4.7） | S03（过程区折叠）、S13 |
| **W3** | `.kv__v`/`.cite__name`/`.card__body`/`.bubble` 长串溢出 | S04（引用）、S06（草稿）、S09（详情） |
| **#1** | 「处理中」不得用 `pill--warn` → 改 `pill--info` | S11（文件/批次处理中）、S06（待确认） |
| **#3** | `records.html:273` 危险胶囊缺图标 → 实现期按规格补 | S09（删除确认） |
| **#6** | 密码显示/隐藏切换的**文案从未冻结** | **S01 阻塞项**：文案冻结前该控件不得实现（§9.1、§9.15 T2） |

### 7.7 路由 ↔ store 触发边界（不重复 §6）

| 时机 | 触发的 store 动作 | 说明 |
| --- | --- | --- |
| G7 登录成功 | `session.setFromLogin(Login.user)` → `session.loadMe()` | `Me` 提供 `capabilities`/`school_timezone`/`session_expires_at` |
| 进入 `/me/schedules` | `schedules.fetch({from_date,to_date})` | 默认今天（`FR-SCH-001`） |
| 进入 `/me/plans`、`/me/plans/:planId` | `plans.fetchList()` / `plans.fetchOne(planId)` | 详情深链的唯一入口 |
| 进入 5 条 `/admin/*` | `admin.fetchXxx()` | 管理端不复用学生端 store 动作 |
| 离开 `/assistant` | **不清空** `chat`（同会话内切页应保留）；仅登出/刷新清空 | `FR-CHAT-002` 的清空时机见 §7.5 |
| 401（G5） | `session.clear()` + `chat.reset()` + `drafts.reset()` | 见 §7.3 |

---

## 9. 页面详细设计 S01–S13

屏幕块编号与文案一律取 `design/directions/shared/content-spec.md`（S01–S13）。**每屏固定 8 项**：路由与进入条件 / 数据依赖 / 组件组成 / 状态清单 / 交互与事件 / 错误分支 / 无障碍要点 / 响应式行为。

### 9.0 通用约定（13 屏共同适用）

| 项 | 约定 | 依据 |
| --- | --- | --- |
| 数据依赖的写法 | 端点一律写全 `/api/v1/...`；响应字段用 `API-REFERENCE.md` 的 `data` 字段名；**所有响应都是信封 `{request_id, data}`**，下文表格只列 `data` 内字段 | `API-REFERENCE.md` §0；契约 §3.7-1 |
| 请求标识 | `request_id` 取自响应 **body**，用于错误提示与支持定位（`NFR-OBS-001`）；**不进 URL** | `API-REFERENCE.md` §0；`NFR-SEC-002` |
| 幂等头 | 只有声明了 `Idempotency-Key` 的写端点才带：`POST /me/plans`、`POST /me/drafts/{draft_id}/save`、`POST /admin/documents/{id}/rebuild`、`POST /admin/documents/{id}/cleanup-retry`。**`POST /chat/stream` 与 `POST /admin/schedules` 没有该头** | `API-REFERENCE.md` 逐条 |
| 并发控制字段 | 计划/课程/学生/课表/文档用 `expected_version`；**草稿用 `expected_draft_version`**；`DELETE` 类把 `expected_version` 放在 **query** | `API-REFERENCE.md` 逐条 |
| 三态语义 | 200＝已有结果（幂等命中）/ 201＝新建成功 / 202＝受理中或待核实。**202 不得渲染成成功** | `API-REFERENCE.md`；`FR-PLAN-005` |
| 三态渲染（loading/empty/failed） | 「成功的空」与「失败」**必须两套**（S08 是最硬的一处）；加载中**只用 `aria-busy` + 禁用控件**表达，设计系统无 skeleton 组件，**不自造「加载中」文案** | 契约 §3.7-3；`FR-SCH-001`；`components/02-actions-status.md` Empty §1 |
| 坏消息文案 | 页面级坏消息只能用 `content-spec` 已冻结的句子；没有对应句子的码，按契约 §3.6 写「复用 SRS §8 原文」并标注 | 契约 §3.6 |
| 错误映射 | 码→行为统一查 §3.4 的映射表（本章各屏只给「码 → 本屏行为」）；`field_errors` 存在时渲染到字段下方并用 `.error-summary` 聚焦 | 契约 §3.6；`components/04-forms-data.md` §四 |
| 401/403 的处理 | 全部由 §7.3 G5/G4 承担，页面**不自行跳登录、不自行隐藏报错** | §7.3 |
| 状态三重 | 状态表达必须图标 + 文字 + 颜色（`NFR-UX-001`），不得只靠颜色 | 契约 §3.7-7 |
| 轮询（管理端批次状态） | 仅在页面可见时轮询；`document-visibilitychange` 变 hidden 即暂停；页面离开即停止。间隔 3s 起、指数退避至 10s（**判断项 J4**，任何真源未冻结间隔）。<br>**分工**：这里是**管理端批次状态**轮询；**`operation_id` 写操作核实**的退避节奏以 §6.9 为唯一权威表（`1s→2s→4s→8s→10s 封顶`），两者不是同一套间隔 | `FR-DOC-002`（异步任务可查状态）、`FR-PLAN-005`（据持久操作记录核实） |
| 时间与数字 | 日期/时间/编号用 `tabular-nums`；学校时区取 `Me.school_timezone`（默认 `Asia/Shanghai`） | `content-spec:21`、`content-spec:118`；`SRS §3.2` |

### 9.1 S01 登录 `/login`

#### 路由与进入条件
`name=login`；`requiresAuth=false`。进入：未持令牌（含刷新后，§7.3 G6）、G5 会话失效跳转、G1 未匹配兜底。已持令牌进入 → G3 重定向 `assistant`。屏幕块 `content-spec:51–59`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求字段 | 响应 `data` 字段 | 说明 |
| --- | --- | --- | --- | --- |
| 提交 | `POST /api/v1/auth/login` | `account`(3–64)、`password`(1–1024) | `access_token`、`token_type`、`expires_at`、`user{id,account,display_name,role,enabled,version}` | 200；令牌只进 `session` 内存 |
| 成功后 | `GET /api/v1/me` | — | `user`、`session_expires_at`、`school_timezone`、`capabilities[]` | 补齐角色与能力，再放行（§7.3 G7） |
| 忘记会话时 | `POST /api/v1/auth/logout` | — | `revoked` | 仅用于「已有令牌但失效」的清理路径 |

#### 组件组成
`components/01-shell-navigation.md` §10 Login（`.login`/`.login__brand`/`.login__sub`/`.login__foot`）、§3 BrandMark、§1 全局根（`:focus-visible`）；`components/04-forms-data.md` §一 Field、§二 Control；`components/02-actions-status.md` Button、Notice。**不引用任何 token 表**。

#### 状态清单
| 状态 | 触发 | 表现 |
| --- | --- | --- |
| 正常 | 初始 | 账号 + 密码 + 主按钮「登录」；页脚提示 |
| 凭据错误 | 401 | `notice--danger` + `role="alert"`，文案「账号或密码不正确，请重试。」（`content-spec:56`）；账号保留、密码清空、**焦点回密码框** |
| 账号不可用 | 403（**判断项 T3**：openapi 同时声明 401/403，SRS §8 只把 `FORBIDDEN` 绑定到管理能力） | 同款危险提示块，文案「当前账号不可用，请联系管理员。」（`content-spec:59`）；控件与主按钮禁用 |
| 字段校验失败 | 422 `VALIDATION_FAILED` + `field_errors[]` | 字段下方错误 + 顶部 `.error-summary` 并聚焦 |
| 提交中 | 请求飞行 | 主按钮禁用（`.btn[disabled]`，`rb.css:205`）；`aria-busy` |
| 密码明文切换 | 用户点击 | **`content-spec:54` 要求该控件，但文案从未冻结 → 实现前置条件未满足，本状态不得实现**（`design/system/README.md:144` 裁决 6） |

#### 交互与事件
1. 提交：Enter / 点击「登录」 → 校验非空 → `POST /auth/login` → 成功则 §7.3 G7；失败按上表。
2. 失败后：清空密码、保留账号、`focus()` 到密码输入框（`content-spec:57` 行为说明）。
3. 显示/隐藏切换：**槽位已预留**（`components/01-shell-navigation.md` §10 §3 表），文案冻结前不实现。
4. 页脚提示常显，不做可关闭组件。

#### 错误分支
| 码 | HTTP | 本屏行为 | 用户可见文案（来源） | 可重试 |
| --- | --- | --- | --- | --- |
| — | 401 | 统一失败态（不区分账号不存在/密码错误） | 「账号或密码不正确，请重试。」（`content-spec:56`） | 是 |
| `FORBIDDEN` | 403 | 账号不可用态，控件禁用 | 「当前账号不可用，请联系管理员。」（`content-spec:59`） | 否 |
| `VALIDATION_FAILED` | 422 | 字段错误 + 摘要聚焦 | 复用 SRS §8 原文（无冻结句子） | 是 |
| `CAPACITY_LIMITED` | 429 | 留在本屏，允许重试 | 复用 SRS §8 原文 | 是 |
| `INTERNAL_ERROR` | 500 | 留在本屏 + 显示 `request_id` | 复用 SRS §8 原文 | 是 |
| `MODEL_UNAVAILABLE`/`STORAGE_UNAVAILABLE` 等 | 503 | 留在本屏 | 复用 SRS §8 原文 | 是 |
| `EXECUTION_TIMEOUT` | 504 | 留在本屏 | 复用 SRS §8 原文 | 是 |

#### 无障碍要点
可见 `<label for>`（「账号」「密码」）+ 文字「必填」（`content-spec:54`；内容契约 §1）；提示块 `role="alert"`；字段错误 `aria-describedby` + `aria-invalid`；失败后焦点移到密码框（不是摘要，因为本屏字段少且失败文案统一）；`autocomplete="username"` / `"current-password"`；对比度见 `components/01-shell-navigation.md` §10 §6；触控 ≥44px（`rb.css:195/320`）。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | `.login{max-width:420px;margin:0 auto}` → 可视宽 320−36＝284px，满宽卡片、单列、无横向滚动 |
| `480–767` | 同上，不换列 |
| `≥ 768` | 同上；**不随断点加宽**，字段列数恒为 1（`components/01-shell-navigation.md` §10 §8） |

### 9.2 S02 助手 · 空闲态 `/assistant`

#### 路由与进入条件
`name=assistant`；`requiresAuth=true`；G7 后默认落地页。进入条件：`chat.state === 'idle'`（契约 §3.5 状态机初态）。屏幕块 `content-spec:61–69`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求 | 响应 `data` 字段 | 说明 |
| --- | --- | --- | --- | --- |
| 进入 | `GET /api/v1/me` | — | `school_timezone`、`session_expires_at`、`capabilities[]` | 时区用于相对日期说明；会话有效期用于边界提示 |
| 提交 | `POST /api/v1/chat/stream` | `client_request_id`、`conversation_id`(可省)、`message`(1–2000)、`history[]` | `text/event-stream` | 首个请求可不传 `conversation_id`（`FR-CHAT-001`） |
| 无 | — | — | — | **没有「取会话历史」端点**：`DEC-01`/`HLD-D11` |

#### 组件组成
`components/03-conversation.md` Chat/Composer/Prose；`components/02-actions-status.md` Button、Empty；`components/01-shell-navigation.md` §9 Wrap（`.wrap--assistant` 720px 助手列）。

#### 状态清单
| 状态 | 触发 | 表现 |
| --- | --- | --- |
| 空闲 | `chat.state==='idle'` | 标题「你好，我是校园课程助手」（`content-spec:62`）+ 能力说明（`:63`）+ 边界提示条（`:64`）+ 3 个示例入口（`:65–68`）+ 输入区 |
| 空白不可提交 | `message.trim()===''` | 主按钮「发送」禁用（`.btn[disabled]`，`rb.css:205`），依赖 `FR-CHAT-001`「去空白后非空」 |
| 可提交 | 非空且 ≤2000 码点 | 按钮可用；超出时按 `field` 错误处理（`ChatInput.message` `maxLength=2000`） |
| 加载中 | 首屏 `GET /me` 飞行 | `aria-busy`；不新增 loading 文案（§9.0） |
| 失败 | `GET /me` 失败 | 按 §9.0 错误映射；401 走 G5 |

#### 交互与事件
1. 3 个示例入口**只把文本填入输入框、不自动提交**（`FR-CHAT-001` 明文）；填入后焦点移到输入框。
2. 输入区 `<textarea>` 可见 label「你的问题」，辅助文字「最多 2000 字」（`content-spec:69`；上限依据 `SRS §3.2`「单条当前问题 2,000」）。
3. 主按钮「发送」（`content-spec:69`）。
4. 次级操作「清空对话」（`content-spec:64`）：清空 `chat` store 与 `HistoryMessage[]`，**不删除已保存计划**（`FR-CHAT-002`）。
5. 提交 → 转 S03（`submitting`，契约 §3.5）。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| `AUTH_REQUIRED`/`SESSION_EXPIRED` | 401 | G5：清会话 → `/login` | 复用 SRS §8 原文 | 否（需重登） |
| `VALIDATION_FAILED` | 422 | 输入框下方错误 + `aria-invalid` | 复用 SRS §8 原文 | 是 |
| `CAPACITY_LIMITED` | 429 | 留在本屏；**不自动重发** | 复用 SRS §8 原文 | 是（手动） |
| `CHAT_IN_PROGRESS`/`REQUEST_ALREADY_EXISTS` | 409 | 转入 S03 并查 `GET /chat/requests/{request_id}` | 复用 SRS §8 原文 | 否，改查询 |
| `INTERNAL_ERROR`/503 类 | 500/503 | 留在本屏 + `request_id` | 复用 SRS §8 原文 | 是 |

#### 无障碍要点
`<textarea>` 必须可见 `<label>`（不得用 placeholder 当唯一标签，契约 §3.7/内容契约 §1）；辅助文字用 `aria-describedby` 关联；发送按钮禁用用原生 `disabled`；示例入口是 `<button type="button">`（不提交表单）；流式内容**不得抢焦点**（`NFR-UX-001`）。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | 单列；`.composer` 吸底并避开标签栏（`rb.css:267`，`bottom:56px+safe-area`）；示例入口换行 |
| `480–767` | 同上；气泡限宽 88%（`rb.css:242`） |
| `≥ 768` | 助手列 720px 居中（`.wrap--assistant`）；`.composer{bottom:0}`（`rb.css:271`）；示例入口同行 |

### 9.3 S03 助手 · 执行中（过程反馈） `/assistant`

> **本屏逐字文案（`content-spec:71–80` 冻结，实现时照抄，不得自拟）**：
> 过程区标题「**本轮执行**」；三个可核实步骤「**正在读取课表**」→ 完成 · 2 条记录、
> 「**正在检索课程资料**」→ 完成 · 3 个片段、「**正在拟定计划草稿**」→ 进行中（**唯一的进行中项**，
> 用动画时须支持 `prefers-reduced-motion`）；顶部状态行「**正在处理 · 最长 60 秒**」+ 次级按钮「**停止**」；
> 正文区含一个**待验证引用标记**（样式必须与已验证引用可区分）。
> 过程区**只允许**出现三个白名单工具（`get_my_schedule`/`search_course_docs`/`save_study_plan`）的可核实动作，
> **禁止**出现「正在思考」类表述（`content-spec:73`、SRS IF-008）。

#### 路由与进入条件
同一路由 `name=assistant`；`chat.state ∈ {submitting, streaming}`（契约 §3.5）。进入：S02 提交、或从 `GET /chat/requests/{request_id}` 恢复显示（`FR-CHAT-005`）。屏幕块 `content-spec:71–80`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求 | 响应/事件字段 | 说明 |
| --- | --- | --- | --- | --- |
| 发起 | `POST /api/v1/chat/stream` | `client_request_id`、`conversation_id`、`message`、`history[]` | **SSE 六类事件**：`status`/`tool_start`/`tool_end`/`token`/`done`/`error` | **无 `Idempotency-Key`**；`seq` 单调，`(request_id,seq)` 去重 |
| 流中 | — | — | `status{request_id,seq,timestamp,code,message,conversation_id?,draft_id?,draft_version?}`；`tool_start{tool_call_id,tool_name,display_name}`；`tool_end{tool_call_id,success,result_status,code?,plan_id?,operation_id?}`；`token{text_delta,answer_block_id}`；`done{state,citations[],plan_id?,operation_id?}`；`error{state:'failed',code,message}` | 字段名取自 `sse_events_v0.1.schema.json` |
| 停止 | `POST /api/v1/chat/requests/{request_id}/cancel` | — | `accepted`、`request{ChatState}` | 配合 `AbortController.abort()`；取消后仍以服务端终态为准 |
| 断线后 | `GET /api/v1/chat/requests/{request_id}` | — | `request_id`、`conversation_id`、`state(accepted\|running\|succeeded\|failed\|cancelled)`、`cancel_requested`、`accepted_at`、`finished_at`、`terminal_reason`、`model_calls`、`tool_calls`、`plan_id`、`operation_id` | `FR-CHAT-005` 的状态查询接口 |

#### 组件组成
`components/02-actions-status.md` Steps（`.steps`/`.step`，三态：进行中/完成/失败）、Button（「停止」为次级按钮）、Pill；`components/03-conversation.md` Chat/Composer；`components/01-shell-navigation.md` §1 全局根（`prefers-reduced-motion` 归零动画）。

#### 状态清单
| 状态 | 触发 | 表现（逐字文案见 `content-spec:73–77`） |
| --- | --- | --- |
| 顶部状态行 | `status` 事件后 | 「正在处理 · 最长 60 秒」+ 次级按钮「停止」（60 秒＝`SRS §3.2` 单轮调度时限） |
| 步骤 · 进行中 | `tool_start` 已到、`tool_end` 未到 | 图标旋转 + 「进行中」；`prefers-reduced-motion` 下不旋转（`rb.css:111`，W2 关联折叠控件） |
| 步骤 · 完成 | `tool_end.success=true`（`result_status ∈ ok/empty/created/existing`） | 图标 + 摘要文字（如「完成 · 2 条记录」「完成 · 3 个片段」） |
| 步骤 · 失败 | `tool_end.success=false`（`result_status='failed'`，`code` 必填） | 危险色 + 失败文字；**不得显示完成勾** |
| 正文流入 | `token` 事件 | 追加到 `answer_block_id` 对应块；待验证引用标记 `〔资料 1〕` 与已验证可区分 |
| 一键停止 | 点击「停止」 | 按钮禁用 + 取消请求；终态仍以服务端为准 |

**只允许出现的工具（白名单 3 个）**：`get_my_schedule`、`search_course_docs`、`save_study_plan`（`sse_events_v0.1.schema.json` → `tool_name` enum；`docs/backend/mcp_tools_v0.1.json`；`FR-GUARD-001`）。步骤标题取事件的 **`display_name`**，不得改用模型文本。

**绝对禁止的表述**：界面只展示任务阶段与实际工具动作（`FR-CHAT-003`），**不得出现模型内部推理类措辞**；过程区文案只能来自 `content-spec:73–77` 的三种步骤句与状态行。

#### 交互与事件
1. 「停止」→ `POST /chat/requests/{request_id}/cancel` + `abort()`；`accepted=true` 时按钮变禁用，等待 `done{state:'cancelled'}`。
2. 第二个终态事件 → 忽略并记 `protocol_violation`（契约 §3.5）。
3. `token` 到达**不移动焦点、不滚动到底**（除非用户已在底部，`NFR-UX-001`「流式内容不持续抢夺焦点」）。
4. 断线/流结束但无终态 → `unknown`：读操作提示未完成且可重试；写操作（本屏通常无）落「待确认」；**HTTP 关闭 ≠ 终态**（契约 §3.5）。
5. `status.code ∈ {CAPACITY_LIMITED, CALL_LIMIT_REACHED}` → 给出可理解提示，不自动重发（`SRS §8` 429/504 行）。

#### 错误分支
| 码/事件 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| `error{code=AUTH_REQUIRED\|SESSION_EXPIRED}` | 流内 | 清会话 → `/login`；**该事件不得带 `plan_id`/`operation_id`** | 复用 SRS §8 原文 | 否 |
| `error{code=MODEL_UNAVAILABLE}` | 流内 | 终态失败，保留已完成步骤 | 复用 SRS §8 原文 | 是（新 `request_id`） |
| `error{code=RETRIEVAL_UNAVAILABLE}` | 流内 | 终态失败 → 转入 S05「检索失败」态 | S05 文案（`content-spec:94`） | 是 |
| `error{code=MCP_UNAVAILABLE}` | 流内 | 终态失败，步骤标失败 | 复用 SRS §8 原文 | 是 |
| `error{code=EXECUTION_TIMEOUT}` / `CALL_LIMIT_REACHED` | 流内 | 终态失败；若有 `plan_id`/`operation_id` 则提供核实入口 | 复用 SRS §8 原文 | 视 `operation_id` 核实 |
| `tool_end.success=false` | 流内 | 该步骤失败，其余步骤继续 | 步骤内文本取 `content-spec:79` 的「失败」语义 | 由下一步骤决定 |
| 无终态（断流） | — | `unknown`：提示未完成、可重发 | 复用 SRS §8 原文 | 是 |
| `CAPACITY_LIMITED` | 429 | 首事件前可能为 HTTP 429 | 复用 SRS §8 原文 | 是（手动） |

#### 无障碍要点
过程区用 `.steps` 列表（`components/02-actions-status.md` Steps §6）；状态三重（图标+文字+颜色）；步骤状态变化通过 `a11y/live.ts` 的 polite live region 播报，**不逐 token 播报**；「停止」按钮有可访问名且 ≥44px；进行中动画在 `prefers-reduced-motion:reduce` 下关闭（`rb.css:111`）；`answer_block_id` 块用 `aria-busy="true"`→终态清除。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | 过程区**默认折叠为一行摘要**（`rb.css:261–263`），可展开；输入区吸底避标签栏；触控 ≥44px；点击折叠控件必须可见焦点（W2） |
| `480–767` | 过程区常显（`rb.css:263`） |
| `≥ 768` | 常显；助手列 720px；`.composer{bottom:0}` |

### 9.4 S04 助手 · 有据回答 + 引用展开 `/assistant`

#### 路由与进入条件
同一路由；`chat.state === 'terminal'` 且 `done.state==='succeeded'`，`citations[]` 非空（契约 §3.5 done 行）。屏幕块 `content-spec:81–89`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求 | 响应 `data` 字段 | 说明 |
| --- | --- | --- | --- | --- |
| 终态 | `done` 事件 | — | `state(succeeded\|cancelled)`、`citations[]: Reference{reference_id,document_id,version_id,file_name,location_label,page_number?}` | **引用以 `done` 为准**（契约 §3.5） |
| 展开片段 | `GET /api/v1/citations/{reference_id}` | path `reference_id` | `reference{...}`、`text`(1–20000) | 折叠态不请求；展开才请求（省流量且避免无谓失效） |
| 流中 | — | — | `tool_end{result_status}` | `search_course_docs` 的 `SearchToolOutput{status,corpus_empty,revision,chunks[],references[]}` 只用于过程区摘要 |

#### 组件组成
`components/03-conversation.md` Citation（`.cite`/`.cite--invalid`/`cite-mark--pending`）、Prose（`68ch` measure）、Chat；`components/02-actions-status.md` Pill（内容性质标签）、Notice；`components/04-forms-data.md` §八 Utility。

#### 状态清单
| 状态 | 触发 | 表现 |
| --- | --- | --- |
| 引用折叠 | 默认 | 「资料 1」+ 文件名 + 位置 + 「展开片段」（`content-spec:85`） |
| 引用展开 | 点击 | 片段原文（`content-spec:86`） |
| 无页码引用 | `Reference.page_number` 缺失 | 只显示文件名与位置（`content-spec:87`；`FR-QA-002`「无法可靠抽取页码时不展示页码」） |
| 未验证标记 | 正文流中的 `〔资料 1〕` 校验前 | 待验证样式，与已验证**可区分**（`content-spec:78`；`FR-QA-002`；`IF-007`） |
| 引用失效 | `GET /citations/{id}` 410 | `.cite--invalid` + 危险色 + 文案（`content-spec:89`） |
| 内容性质标签 | 回答含资料事实/建议 | 「课程规定」（来自资料）与「一般学习建议」（非资料依据）视觉区分、**不得混排**（`content-spec:88`；`FR-QA-003`） |

#### 交互与事件
1. 折叠→展开：`GET /citations/{reference_id}`；成功后渲染 `text`，按 `location_label` 显示位置。
2. 展开失败 410 → 该引用卡转失效态，**保留已渲染的答案文字**（`FR-DOC-006`「已经发送的答案文字不承诺撤回」）。
3. 引用标记点击 → 滚动并展开对应引用卡；焦点移到该卡（可访问名 = 文件名 + 位置）。
4. 正文 Markdown **必须安全渲染**（`FR-CHAT-003`）：禁用原始 HTML，链接 `rel="noopener noreferrer"`。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| `CITATION_UNAVAILABLE` | 410 | 该引用卡转失效态；答案文字保留 | 「这条引用已失效（资料已被删除），依据可能已变化。」（`content-spec:89`） | 否（需重新检索） |
| `RESOURCE_NOT_FOUND` | 404 | 同 410 的降级表现（不透露是否存在） | 复用 SRS §8 原文 | 否 |
| `STORAGE_UNAVAILABLE` | 503 | 引用卡保留折叠态 + 可重试 | 复用 SRS §8 原文 | 是 |
| `AUTH_REQUIRED`/`SESSION_EXPIRED` | 401 | G5 | 复用 SRS §8 原文 | 否 |

#### 无障碍要点
展开按钮用 `<button aria-expanded aria-controls>`，展开区 `id` 对应；引用卡的 `location_label` 与文件名共同构成可访问名；失效引用不能只靠颜色（危险色 + 文字 + 图标 = 三重）；`〔资料 1〕` 标记的未验证态除样式外必须有可读文本或 `aria-label`；长文件名溢出按 W3 处理（`.cite__name` 补 `overflow-wrap`，`design/system/README.md:218–226`）。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | 引用卡单列，头部字段换行；正文 measure 自然宽；无页面级横向溢出（W3 修后） |
| `480–767` | 单列；气泡 ≤88% |
| `≥ 768` | 单列，头部字段同行；`.prose{max-width:68ch}`（`rb.css:170`） |

### 9.5 S05 助手 · 依据不足 / 检索失败 / 全库为空（三态并列） `/assistant`

#### 路由与进入条件
同一路由；三个互斥终态。进入条件：`tool_end` 的检索结果、或 `error` 事件的 `RETRIEVAL_UNAVAILABLE`。屏幕块 `content-spec:91–96`。三个态**必须与 S04「有据」在视觉上一眼可分**，且**都不能用成功色**。

#### 数据依赖（端点 + 字段）
| 时机 | 端点/事件 | 判定字段 | 说明 |
| --- | --- | --- | --- |
| 依据不足 | `tool_end`（`search_course_docs`） | `success=true`、`result_status='ok'` 但答案被判定依据不足；检索侧对应 `SearchToolOutput.status='ok'` 且 `chunks[]` 不足以支撑 | `FR-QA-003`「有效检索但依据不足」 |
| 检索失败 | `error{code:'RETRIEVAL_UNAVAILABLE'}`（HTTP 503） | `code` | `SRS §8` 503 行 |
| 全库为空 | `tool_end`（`search_course_docs`） | `SearchToolOutput.corpus_empty=true`（`status='empty'`） | `FR-QA-004`「全库为空时提示管理员尚未提供材料」 |
| 均无 | — | — | 不调用 `GET /citations/*`（无引用可查） |

#### 组件组成
`components/02-actions-status.md` Empty（`.empty`/`.empty--error`，两者视觉必须可分）、Notice、Button（「换个问法」「联系管理员补充材料」「重试」）。

#### 状态清单
| 状态 | 逐字文案（`content-spec`） | 动作 | 颜色语义 |
| --- | --- | --- | --- |
| 依据不足 | 「已检索共享资料，但没有找到足以回答这项要求的内容。」（`:92`） | 「换个问法」/「联系管理员补充材料」（`:93`） | 中性/警示，**不得用成功色** |
| 检索失败 | 「课程资料暂时无法查询，请稍后重试。」（`:94`） | 主按钮「重试」（`:94`） | 错误语义（`.empty--error`） |
| 全库为空 | 「管理员还没有上传可检索的课程资料。」（`:95`） | — | 中性 |

**严禁**：把「成功的空」（依据不足/全库为空）与「失败」（检索失败）合并为同一种视觉或同一句「空」文案（`FR-QA-003`；契约 §3.7-3）。

#### 交互与事件
1. 「换个问法」→ 焦点回输入框并保留原问题文本供修改（不自动提交）。
2. 「重试」→ 以**新的** `client_request_id` 重新提交（读操作允许重试；写操作必须先核实，`FR-CHAT-005`）。
3. 「联系管理员补充材料」→ 纯提示性动作（无对应端点，**不做假链接**）。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| — | 200 | 依据不足态（`status='ok'` 但无有效依据） | `content-spec:92` | 是（换问法） |
| `RETRIEVAL_UNAVAILABLE` | 503 | 检索失败态 | `content-spec:94` | 是 |
| `MODEL_UNAVAILABLE`/`MCP_UNAVAILABLE` | 503 | 按下述映射到检索失败或独立提示 | 复用 SRS §8 原文 | 是 |
| `CAPACITY_LIMITED` | 429 | 留在本屏 | 复用 SRS §8 原文 | 是 |
| `EXECUTION_TIMEOUT` | 504 | 提示超时；**若有写入则先核实** | 复用 SRS §8 原文 | 视核实结果 |
| `AUTH_REQUIRED`/`SESSION_EXPIRED` | 401 | G5 | 复用 SRS §8 原文 | 否 |

#### 无障碍要点
三态各自用 `.empty` 容器且标题不同、插画/图标不同（不能只靠颜色）；`role="status"` 播报终态；「重试」为 `<button>` 且 ≥44px；`aria-describedby` 关联说明文字；错误态不得只改颜色。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | 单列居中；动作按钮纵向堆叠（`.btn--block` 可用） |
| `480–767` | 单列；动作按钮同行换行 |
| `≥ 768` | 单列居中，动作按钮同行 |

### 9.6 S06 助手 · 草稿未保存 → 保存成功 / 结果待确认 `/assistant`

#### 路由与进入条件
同一路由；由 `status` 事件携带 `draft_id`/`draft_version`（SSE schema 中 `status` 的可选字段）或 `tool_end`（`save_study_plan`，`created`/`existing` 都算成功）驱动。屏幕块 `content-spec:98–110`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求字段 | 响应 `data` 字段 | 说明 |
| --- | --- | --- | --- | --- |
| 取草稿 | `GET /api/v1/me/drafts/{draft_id}` | path `draft_id` | `draft_id`、`draft_version`、`operation_id`、`title`、`goal`、`start_date`、`end_date`、`content`、`basis_types[]`、`references[]`、`expires_at` | `expires_at` 与「草稿 30 分钟」对应（`SRS §3.2`） |
| 改草稿 | `PATCH /api/v1/me/drafts/{draft_id}` | `title`、`goal`、`start_date`、`end_date`、`content`、**`expected_draft_version`** | 同上（`Draft`） | 版本字段名与计划不同，注意区别 |
| 保存 | `POST /api/v1/me/drafts/{draft_id}/save` | header `Idempotency-Key`；body `draft_version` | **200** `status(existing\|deleted)`+`operation_id`+`plan_id`；**201** `status(created)`+…；**202** `operation_id`、`state(pending\|succeeded\|failed\|deleted)`、`resolution(confirmed\|recovering)`、`plan_id`、`error_code`、`retryable` | 三态必须分别渲染 |
| 核实 | `GET /api/v1/me/write-operations/{operation_id}` | path `operation_id` | 同 202 的 `WriteOperation` | `FR-PLAN-005`；轮询策略见 §9.0 J4 |
| 计划详情 | `GET /api/v1/me/plans/{id}` | path `id` | `Plan{...version...}` | 「打开计划」跳 `/me/plans/:planId` |

#### 组件组成
`components/03-conversation.md` Draft（`.draft`/`.draft--saved`、未保存＝琥珀虚线+文字双标记）、Chat；`components/02-actions-status.md` Button、Pill（`pill--pending` 表示未保存/待确认，**不得用 `pill--warn`**，`design/system/README.md:139`）；`components/03-conversation.md` KVList（依据字段）。

#### 状态清单
| 状态 | 触发 | 表现（逐字文案见 `content-spec:100–110`） |
| --- | --- | --- |
| 未保存 | 草稿存在、未保存 | 标题「复习计划草稿」+ 状态「**未保存**」（文字 + 视觉双标记）；依据显式标注「本人课表」+「课程资料 〔资料 1〕」 |
| 保存中 | 请求飞行 | 「保存为我的计划」禁用 + `aria-busy` |
| 已保存 | 201（或 200 `existing`） | 「已保存 · 计划编号 plan_7Q2F9K」+ 对勾图标 + 主按钮「打开计划」（对勾+文字，不能只靠绿色） |
| 结果待确认 | **202** | 「正在确认是否保存…」+「写入结果尚未确认，请勿重复创建；可稍后查询状态。」+ 次级按钮「查询写入状态」 |
| 草稿过期 | 410 `DRAFT_EXPIRED` | 提示重新生成，**不以客户端文本重建草稿**（`FR-PLAN-002`） |
| 幂等命中 | 200 `status='existing'` | 按已保存渲染（同一 `plan_id`），**不新建**（`FR-PLAN-004`） |
| 同轮上限 | 409 `SAVE_LIMIT_REACHED` | 展示已有结果，不新建 |

#### 交互与事件
1. 「保存为我的计划」→ `POST .../save`（带 `Idempotency-Key`，同一逻辑操作**复用同一个键**，`FR-PLAN-004`）。
2. 202 → 进入待确认；点「查询写入状态」→ `GET /me/write-operations/{operation_id}`；`state='succeeded'` 且 `resolution='confirmed'` → 转已保存。
3. 「继续修改」→ `PATCH .../drafts/{id}` 带 `expected_draft_version`；成功后旧许可失效（`FR-PLAN-005`），需重新发起保存。
4. 「打开计划」→ `router.push({name:'planDetail', params:{planId}})`（唯一深链）。
5. 小字说明「重复提交同一操作只会得到同一份计划。」（`content-spec:110`）。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| — | 202 | 待确认态（**不得渲染成成功**） | `content-spec:109` | 轮询核实 |
| — | 200 `existing`/`deleted` | 幂等命中，按已保存/已删除渲染 | `content-spec:107` | 否 |
| `DRAFT_EXPIRED` | 410 | 草稿失效，要求重新生成 | 复用 SRS §8 原文 | 是（重新生成） |
| `VERSION_CONFLICT` | 409 | 提示重载；**保留未提交编辑** | 复用 SRS §8 原文（S09 有对应句） | 是（重载后） |
| `IDEMPOTENCY_CONFLICT` | 409 | 展示已有结果，不新建 | 复用 SRS §8 原文 | 否 |
| `SAVE_LIMIT_REACHED` | 409 | 展示已有结果 | 复用 SRS §8 原文 | 否 |
| `SAVE_NOT_AUTHORIZED` | 422 | 保持预览 + 提供保存按钮（不自动保存） | 复用 SRS §8 原文 | 是（用户显式点） |
| `EXECUTION_TIMEOUT`/`CALL_LIMIT_REACHED` | 504 | **先按 `operation_id` 核实再决定** | 复用 SRS §8 原文 | 视核实 |
| 无终态 | — | 待确认（`unknown` ≠ 失败） | `content-spec:109` | 核实 |

#### 无障碍要点
「未保存」必须文字 + 视觉双标记（`content-spec:99`；`NFR-UX-001` 状态三重）；保存结果变化用 polite live region 播报；「打开计划」是链接语义还是按钮语义二选一并保持一致（判断项 J5）；草稿字段与表单组件参考 `components/04-forms-data.md` §一/§二；对勾图标 `aria-hidden="true"` 且有同义文字。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | 草稿卡占满宽；条目一行一条；按钮纵向（`.btn--block`） |
| `480–767` | 占满宽；按钮可同行换行 |
| `≥ 768` | 占满助手列 720px；按钮同行 |

### 9.7 S07 课表有课 `/me/schedules`

#### 路由与进入条件
`name=schedules`；`requiresAuth=true`；`activeNav='schedules'`。进入：底部/顶栏「课表」入口，或登录后手动导航。默认查询**学校时区当日**（`FR-SCH-001`）。屏幕块 `content-spec:112–119`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求参数 | 响应 `data` 字段 | 说明 |
| --- | --- | --- | --- | --- |
| 进入/翻日期 | `GET /api/v1/me/schedules` | `page`、`page_size`（默认 20，最大 100）、`from_date`(date)、`to_date`(date) | `items[]: Schedule{id,student_id,course_id,course_name,class_date,start_time,end_time,location,version}`、`page`、`page_size`、`total`、`from_date`、`to_date`、`school_timezone` | 两端都不传＝今天；只传一端＝该单日；`from_date ≤ to_date`（`SRS:174`） |
| 无 | — | — | — | **学生端没有「按学生查课表」的端点**：`GET /admin/schedules` 有必填 `student_id`，是管理接口，学生端不得调用（`FR-GUARD-001`） |

#### 组件组成
`components/04-forms-data.md` §六 Table（+`§5` 的 `--stack` 判定规则）、§五 TableWrap、§八 Utility；`components/01-shell-navigation.md` §9 Wrap；`components/02-actions-status.md` Empty、Button。

#### 状态清单
| 状态 | 触发 | 表现 |
| --- | --- | --- |
| 有课 | `items.length > 0` | 页面标题「我的课表」；日期导航 `‹ 2026-10-22 周四 ›` + 「今天」按钮 + 说明「单次最多查询 31 天」（`content-spec:114`，31＝`SRS §3.2`「个人课表查询跨度」）；列表按 `start_time` 升序 |
| 加载中 | 请求飞行 | `aria-busy` + 控件禁用（无 skeleton） |
| 空 | 200 且 `items=[]` | **转入 S08 状态①**（本屏不渲染自己的空态） |
| 失败 | 非 2xx | **转入 S08 状态②** |
| 页脚 | 常显 | 「时间为学校时区 Asia/Shanghai」（`content-spec:118`；值取 `school_timezone`） |

每行字段＝「开始–结束时间 / 课程名 / 地点」（`content-spec:115`）：`start_time`–`end_time`、`course_name`、`location`（`location` 可为 null → 显示占位由内容契约决定，**不得自造**）。

#### 交互与事件
1. `‹`/`›` → 日期 ±1 天并重新请求；「今天」→ 回到当日（`from_date=to_date=今天`）。
2. 跨度校验：`from_date`/`to_date` 相差 >31 天时**前端先拦**（不发请求），按 `VALIDATION_FAILED` 的字段错误处理。
3. 分页：用 `page`/`page_size`（**不进 URL**，§7.1 J1）。
4. 时间显示统一 `tabular-nums`，不因数字宽度抖动（`content-spec:21`）。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| `STORAGE_UNAVAILABLE` | 503 | 转 S08 状态②（**不得渲染成空列表**） | 「课表数据暂时无法读取，这不代表当天没有课。」（`content-spec:124`） | 是 |
| `VALIDATION_FAILED` | 422 | 日期范围错误提示在控件下方 | 复用 SRS §8 原文 | 是 |
| `RESOURCE_NOT_FOUND` | 404 | 不适用（无资源 id）；若出现按 SRS §8 原文 | 复用 SRS §8 原文 | 否 |
| `CAPACITY_LIMITED` | 429 | 保留当前列表，提示稍后重试 | 复用 SRS §8 原文 | 是 |
| `EXECUTION_TIMEOUT` | 504 | 转 S08 状态② | `content-spec:124` | 是 |
| `AUTH_REQUIRED`/`SESSION_EXPIRED` | 401 | G5 | 复用 SRS §8 原文 | 否 |

#### 无障碍要点
表格必须有 `<caption>` 与 `scope`（内容契约 §1）；窄屏卡片化后字段名由 `data-label` 提供（`b-responsive-spec.md` §5 规则 3，构建期有检查）；日期切换按钮需可访问名（文案未冻结 → 按钮用图标 + 现有 `aria-label` 口径，**登记 T6**）；列表更新用 polite live region 播报条数；「今天」按钮 ≥44px。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | `.table--stack` 卡片化：`thead` 隐藏、`tr` 成卡、首列 `.cell-name` 独占一行 17px；**页面级横向溢出必须为 0** |
| `480–767` | 同上卡片化 |
| `≥ 768` | 恢复表格 + `thead`；`.table-wrap{overflow-x:auto}` 作兜底 |

**硬约束**：学生端核心流程 S07–S09 **不得页面级横向溢出**（契约 §3.7-10）；`NFR-COMP-001` 的横向滚动豁免**只给管理端**。

### 9.8 S08 课表 · 两种空状态（必须并列且视觉可分）`/me/schedules`

#### 路由与进入条件
同一路由 `name=schedules`。两个状态**互斥且都由本屏渲染**，来源不同：状态①是 HTTP 200 的空集合，状态②是 HTTP 失败。屏幕块 `content-spec:121–126`。

#### 数据依赖（端点 + 字段）
| 状态 | 端点 | 判定字段 | 依据 |
| --- | --- | --- | --- |
| ① 查询成功但无记录 | `GET /api/v1/me/schedules` | **200** 且 `items.length === 0`、`total === 0` | `FR-SCH-001`「查询成功无记录时返回空集合」；`SRS:174` |
| ② 服务异常 | 同上 | 非 2xx（如 503 `STORAGE_UNAVAILABLE`、504 `EXECUTION_TIMEOUT`） | `FR-SCH-001`「数据源失败应返回错误而非空集合」 |

#### 组件组成
`components/02-actions-status.md` Empty（`.empty` 用中性；`.empty--error` 用错误语义 —— **两者视觉必须可分**）、Button（「换个日期」/「重试」）。

#### 状态清单
| # | 逐字文案（`content-spec`） | 动作 | 视觉 | 禁止 |
| --- | --- | --- | --- | --- |
| ① | 「2026-10-22（周四）没有课程安排。」（`:122`） | 「换个日期」（`:122`） | 中性插画/图标，**不得使用错误色** | 不得使用成功色或错误色 |
| ② | 「课表数据暂时无法读取，这不代表当天没有课。」（`:124`） | 「重试」（`:124`） | 错误/警告语义，与①明显不同 | 不得渲染成①的任何变体 |

**这是 PRD/SRS 的硬验收点**（`content-spec:126`）：两个态**禁止合并**成一个「空」表述；契约 §3.7-3 同时禁止用无信息量的合并式说法把「成功的空」与「失败的空」写成同一件事。

#### 交互与事件
1. ①「换个日期」→ 打开日期选择/前后翻日（复用 S07 的日期导航），**不改变路由**。
2. ②「重试」→ 以相同 `from_date`/`to_date` 重新请求（读操作允许重试，`FR-CHAT-005`）。
3. 两态都保留页面标题与日期导航，用户能看出「查的是哪一天」。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| — | 200（`items=[]`） | 状态①，**不是错误** | `content-spec:122` | 不适用 |
| `STORAGE_UNAVAILABLE` | 503 | 状态② | `content-spec:124` | 是 |
| `EXECUTION_TIMEOUT` | 504 | 状态② | `content-spec:124` | 是 |
| `RETRIEVAL_UNAVAILABLE` 等其它 503 码 | 503 | 状态②（本屏不细分依赖来源） | `content-spec:124` | 是 |
| `AUTH_REQUIRED`/`SESSION_EXPIRED` | 401 | G5 | 复用 SRS §8 原文 | 否 |
| `VALIDATION_FAILED` | 422 | 日期错误（不是空态） | 复用 SRS §8 原文 | 是 |

#### 无障碍要点
两态用不同 `role`：① `role="status"`（非错误），② `role="alert"`（错误）；两态标题文字不同（读屏用户也必须能区分）；「重试」≥44px；空态插画 `aria-hidden="true"`；不得只靠颜色区分两态。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | 单列居中；按钮全宽可用（`.btn--block`）；无横向溢出 |
| `480–767` | 单列居中；按钮同行 |
| `≥ 768` | 单列居中；内容列 880px |

### 9.9 S09 计划列表 + 详情编辑 `/me/plans`、`/me/plans/:planId`

#### 路由与进入条件
两条路由共用一个屏幕块：`plans`（列表，S09）与 `planDetail`（详情，S09 详情）。`requiresAuth=true`；`activeNav='plans'`。**`planDetail` 是唯一对外可深链的私有路由**（§7.6）；未登录深链 → 存 `pendingPath` → 登录后回跳。列表排序按 `updated_at` + `id` 倒序（`FR-PLAN-001`；`SRS:268`）。屏幕块 `content-spec:128–138`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求字段/参数 | 响应 `data` 字段 | 说明 |
| --- | --- | --- | --- | --- |
| 列表 | `GET /api/v1/me/plans` | `page`、`page_size`、`title`（按标题筛选） | `items[]: Plan{id,title,goal,start_date,end_date,content,source(manual\|assistant),basis_types[](schedule\|documents\|general),references[],version,created_at,updated_at}`、`page`、`page_size`、`total` | 搜索框 label 可见（`content-spec:129`） |
| 新建 | `POST /api/v1/me/plans` | header `Idempotency-Key`（必填）；body `PlanCreate{title(1–100),goal,start_date,end_date,content(1–10000)}` | **200** `SaveReusedResult{status(existing\|deleted),operation_id,plan_id}`；**201** `SaveCreatedResult{status(created),…}`；**202** `WriteOperation{operation_id,state,resolution,plan_id,error_code,retryable}` | 三态分别渲染 |
| 详情 | `GET /api/v1/me/plans/{id}` | path `id` | `Plan`（同上） | `source` 只读；`references[]` 展示依据 |
| 编辑 | `PATCH /api/v1/me/plans/{id}` | body `PlanPatch{title,goal,start_date,end_date,content,**expected_version**}` | `Plan` | 并发用 `expected_version` |
| 删除 | `DELETE /api/v1/me/plans/{id}` | query `expected_version`（必填） | `PlanDelete{deleted,plan_id,version}` | 删除前确认文案见下 |
| 核实 | `GET /api/v1/me/write-operations/{operation_id}` | path | `WriteOperation` | 202 后核实（`FR-PLAN-005`） |

长度上限取自 `SRS §3.2`「计划标题／目标／正文长度 100／500／10,000」（正文上限 10,000 与 `PlanCreate.content maxLength=10000` 一致）。

#### 组件组成
`components/04-forms-data.md` §六 Table + §五 TableWrap、§一 Field、§二 Control、§三 FormGrid、§四 ErrorSummary、§八 Utility；`components/02-actions-status.md` Button、Empty、Notice；`components/03-conversation.md` KVList（详情只读字段）。

#### 状态清单
| 状态 | 触发 | 表现 |
| --- | --- | --- |
| 列表有数据 | `total>0` | 标题「学习计划」+ 搜索框；表格列＝标题 / 覆盖日期 / 来源 / 更新时间 / 操作（`content-spec:130`） |
| 空列表 | 200 且 `items=[]` | 「还没有学习计划。」+「手动新建」（`content-spec:133`） |
| 新建 | 点「新建计划」 | 空表单；`source='manual'` |
| 详情查看 | 深链或「打开」 | 字段：标题 / 目标 / 开始日期 / 结束日期 / 正文 / **来源（只读）**（`content-spec:135`） |
| 保存中 | 请求飞行 | 主按钮禁用 + `aria-busy` |
| 保存成功 | 201 | 展示 `plan_id` 与详情入口（`FR-PLAN-005`） |
| 结果待确认 | 202 | 待确认态 + 核实入口（文案复用 S06 的 `content-spec:109`） |
| 版本冲突 | 409 | 保留未提交编辑供核对（`content-spec:137` 文案） |
| 删除确认 | 点「删除」 | 展示学生/课程/时间无关；本屏展示标题与「删除后无法恢复。助手对话不受影响。」 |
| 加载/失败 | 飞行 / 非 2xx | `aria-busy`；失败按 §9.0 映射 |

**空值显示**：`goal`/`start_date`/`end_date` 可为 null。列表「覆盖日期」列在 `start_date`/`end_date` 均空时显示 `content-spec:132` 的「未设置日期」（该串已冻结，用于第二行示例）。

#### 交互与事件
1. 搜索：输入 `title` → debounce 后请求（间隔为**判断项 J4**）；空输入＝清筛选。
2. 新建/编辑校验：`title` 必填 ≤100、`content` 必填 ≤10,000、`goal` ≤500；日期「可同时不填，若填写则须起止完整且有序」（`FR-PLAN-001`）→ 违反时文案 `content-spec:136`「开始与结束日期需要同时填写，且开始日期不能晚于结束日期。」
3. 保存：新建用 `Idempotency-Key`（同一逻辑操作复用同一个键）；编辑用 `expected_version`。
4. 删除：二次确认（文案 `content-spec:138`）→ `DELETE ...?expected_version=` → 成功后从列表移除并 `router.replace({name:'plans'})`（若在详情页）。
5. 详情页深链：`GET /me/plans/{id}` 404 → 按 §9.0「复用 SRS §8 原文」，**不显示该计划是否存在**（`FR-AUTH-004`）。
6. 依据展示：`basis_types[]` 与 `references[]` 映射到 `content-spec:131` 的「助手生成 / 手动创建」与依据类型；`source` 只读字段必须可见。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| `VERSION_CONFLICT` | 409 | 提示重载；**保留未提交编辑** | 「这份计划已被其他标签页修改，请重新加载后再提交；你未提交的编辑会保留。」（`content-spec:137`） | 是（重载后） |
| `VALIDATION_FAILED` | 422 | 字段错误 + `.error-summary` 聚焦；日期错误用冻结句 | `content-spec:136`（日期）／复用 SRS §8 原文（其它） | 是 |
| `RESOURCE_NOT_FOUND` | 404 | 详情目标不存在 | 复用 SRS §8 原文（不透露存在性） | 否 |
| `IDEMPOTENCY_CONFLICT` | 409 | 展示已有结果，不新建 | 复用 SRS §8 原文 | 否 |
| `SAVE_LIMIT_REACHED` | 409 | 展示已有结果 | 复用 SRS §8 原文 | 否 |
| `SAVE_NOT_AUTHORIZED` | 422 | 仅手动表单路径不产生此码；若出现按未授权处理 | 复用 SRS §8 原文 | 是 |
| — | 202 | 待确认（**不得渲染为成功**） | `content-spec:109` | 核实 |
| `CAPACITY_LIMITED` | 429 | 保留编辑内容 | 复用 SRS §8 原文 | 是 |
| `INTERNAL_ERROR`/503 类 | 500/503 | 保留编辑内容 + `request_id` | 复用 SRS §8 原文 | 是 |
| `AUTH_REQUIRED`/`SESSION_EXPIRED` | 401 | G5（**先落盘编辑内容到内存再跳转**） | 复用 SRS §8 原文 | 否 |

#### 无障碍要点
搜索框必须有可见 `<label>`（`content-spec:129`；不得用 placeholder 当唯一标签）；表格 `<caption>` + `scope`；窄屏 `data-label` 齐全；错误摘要 `role="alert"` 且聚焦；删除确认是危险操作 → 语义危险色 + 二次确认 + 与主操作分离（内容契约 §1）、并使用 `.pill--danger`（**实现期须补图标**，#3）；日期输入用原生 `type="date"` 或等价控件并提供可见标签。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | 表格卡片化；`.cell-name` 独占行；**页面级溢出 0** |
| `480–767` | 同上卡片化 |
| `≥ 768` | 表格形态；`form-grid--2` 两列（宽字段 `field--wide` 跨列） |

**已知风险（必须在实现期实测）**：`b-responsive-spec.md` §5 的 ⚠ 记录 S09 表格在 **767–899px 有 25–57px 内部滚动**（768 下 57px），目前封闭在 `.table-wrap` 内、页面级仍为 0。改动本屏表格列宽或删掉 `table--stack` 会立刻变成页面级溢出。

### 9.10 S10 管理中心 · 课程管理 `/admin/courses`

#### 路由与进入条件
`name=adminCourses`；`requiresAuth=true` + `requiresAdmin=true`（`role==='admin'`，否则 G4）。入口：顶栏/标签栏「管理中心」（`activeNav='admin'`）→ 默认落本屏。屏幕块 `content-spec:140–148`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求字段/参数 | 响应 `data` 字段 | 说明 |
| --- | --- | --- | --- | --- |
| 列表/筛选 | `GET /api/v1/admin/courses` | `page`、`page_size`、`query`（按代码或名称）、`enabled` | `items[]: Course{id,code,name,description,enabled,version}`、`page`、`page_size`、`total` | 必须有筛选/搜索区（`content-spec:148`） |
| 新建 | `POST /api/v1/admin/courses` | `CourseCreate{code(1–32),name(1–100),description,enabled}` | `Course` | 201；**无 `Idempotency-Key`** |
| 编辑 | `PATCH /api/v1/admin/courses/{id}` | `CoursePatch{name,description,enabled,expected_version}` | `Course` | 200 |
| 无 | — | — | — | **没有课程删除端点**（`FR-COURSE-002`「本期不暴露课程物理删除接口」）→ 界面不得有删除按钮 |

#### 组件组成
`components/04-forms-data.md` §六 Table、§五 TableWrap、§一 Field、§二 Control、§三 FormGrid、§四 ErrorSummary；`components/02-actions-status.md` Button、Pill（启用/已停用）、Notice。

#### 状态清单
| 状态 | 触发 | 表现 |
| --- | --- | --- |
| 列表有数据 | `total>0` | 表格列＝课程代码 / 名称 / 简介 / 状态 / 操作（`content-spec:141`）；行内含「编辑」+「停用」（启用中）或「启用」（已停用） |
| 空列表 | 200 且 `items=[]` | 用 `.empty`；**文案未在 content-spec 冻结** → 不自造（登记 T6） |
| 新建表单 | 点「新建课程」 | 课程代码可编辑；名称必填；简介 ≤2000；启用状态开关 |
| 编辑表单 | 点「编辑」 | **课程代码只读**且说明「课程代码创建后不可修改」（`content-spec:145`） |
| 重复代码 | 409 | 字段错误：`content-spec:146` |
| 停用确认 | 点「停用」 | 二次确认，说明 `content-spec:147` |
| 保存中/失败 | 飞行 / 非 2xx | 按钮禁用 + `aria-busy`；失败按 §9.0 |

#### 交互与事件
1. 筛选区：输入 `query`（代码或名称）+ `enabled` 过滤 → 重新请求（**不进 URL**，§7.1 J1）。
2. 新建：`POST /admin/courses`；`code` 唯一（`FR-COURSE-001`），成功后回到列表并高亮新行。
3. 编辑：`PATCH` 带 `expected_version`；`code` 字段渲染为只读控件并加说明文字。
4. 停用/启用：`PATCH {enabled:false|true}` + `expected_version`；停用前二次确认。
5. **停用课程不可用于新增课表**（`FR-COURSE-001`）→ 该约束在 S12 的下拉里生效（本屏只负责把 `enabled=false` 落库）。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| `DUPLICATE_COURSE` | 409 | 课程代码字段错误 | 「该课程代码已存在，请更换。」（`content-spec:146`） | 是（改代码） |
| `VERSION_CONFLICT` | 409 | 提示重载并保留编辑 | 复用 SRS §8 原文 | 是 |
| `VALIDATION_FAILED` | 422 | 字段错误 + 摘要聚焦 | 复用 SRS §8 原文 | 是 |
| `RESOURCE_NOT_FOUND` | 404 | 目标课程不存在（可能已被并发停用/删除流程影响） | 复用 SRS §8 原文 | 否 |
| `FORBIDDEN` | 403 | G4（正常不会到达本屏） | 复用 SRS §8 原文 | 否 |
| `INTERNAL_ERROR`/503 类 | 500/503 | 保留表单内容 + `request_id` | 复用 SRS §8 原文 | 是 |

#### 无障碍要点
表格 `<caption>` + `scope`；只读字段用 `readonly`（不是 `disabled`），并用 `aria-describedby` 关联「课程代码创建后不可修改」（只读与禁用必须视觉可区分，内容契约 §1）；启用状态用 `pill--ok`/中性胶囊 + 文字 + 图标三重；停用确认面板焦点管理（进入时聚焦面板标题，确认后回触发按钮）；弹层不做无冻结支撑的自造结构。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | **允许表格横向滚动**（`NFR-COMP-001`；`b-responsive-spec.md` §5 规则 4）——滚动必须由 `.table-wrap` 承担，不是页面 |
| `480–767` | 同上；表单单列 |
| `≥ 768` | 表格形态；`form-grid--2` 两列 |

### 9.11 S11 管理中心 · 文档与批次 `/admin/documents`、`/admin/document-batches/:batchId`

#### 路由与进入条件
两条路由：`adminDocuments`（列表 + 上传，S11）与 `adminBatch`（批次详情，S11 批次，`:batchId` 与端点 `{id}` 对应）。均 `requiresAuth+requiresAdmin`。屏幕块 `content-spec:150–161`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求字段/参数 | 响应 `data` 字段 | 说明 |
| --- | --- | --- | --- | --- |
| 上传 | `POST /api/v1/admin/document-batches` | `multipart/form-data`：`files`（数组）、`allow_duplicate_names` | **202** `Batch{batch_id,state(accepted\|processing\|published\|compensating\|failed),published,documents[],tasks[],error_code}` | 受理即 202（`FR-DOC-001`） |
| 批次详情 | `GET /api/v1/admin/document-batches/{id}` | path `id` | `Batch`（同上，含 `documents[]`、`tasks[]`） | 与路由 `:batchId` 一对一对齐 |
| 文档列表 | `GET /api/v1/admin/documents` | `page`、`page_size`、`name`、`state` | `items[]: Document{id,batch_id,original_name,file_type(txt\|md\|pdf\|docx),byte_size(≤20971520),visibility(unpublished\|shared\|removed),processing_state(processing\|available\|failed\|rebuilding\|deleting\|delete_failed\|deleted),version,uploaded_at,error_code,cleanup_state(not_required\|pending\|running\|succeeded\|failed)}`、`page`、`page_size`、`total` | `state` 是**自由字符串（1–32 字符，openapi 未枚举）**→ 筛选值域未冻结（J6） |
| 任务 | 同批次/列表 | — | `Task{task_id,state(pending\|running\|retry_wait\|succeeded\|failed),error_code,retryable}` | 异步任务码见下 |
| 预览 | `GET /api/v1/admin/documents/{id}/text` | `offset`(≥0)、`limit`(1–20000) | `document_id`、`version_id`、`offset`、`next_offset`、`text` | 入口文案「预览抽取文本」（`content-spec:161`） |
| 重建 | `POST /api/v1/admin/documents/{id}/rebuild` | header `Idempotency-Key`（必填）；body `Rebuild{expected_version}` | **202** `DocumentMutation{document_id,visibility,task,version}` | `FR-DOC-005` |
| 删除 | `DELETE /api/v1/admin/documents/{id}` | query `expected_version` | **202** `DocumentMutation` | 先不可见再异步清理（`FR-DOC-006`） |
| 重试清理 | `POST /api/v1/admin/documents/{id}/cleanup-retry` | header `Idempotency-Key`（必填） | **202** `DocumentMutation` | 「重试清理」（`content-spec:158`） |

#### 组件组成
`components/04-forms-data.md` §六 Table、§五 TableWrap、§一 Field、§二 Control、§四 ErrorSummary；`components/02-actions-status.md` Pill、Notice、Button、Empty；`components/03-conversation.md` Prose（预览纯文本容器）。**不复制 token 表**。

#### 状态清单

**① 上传区**：拖拽区 + 「选择文件」（`content-spec:151`）；限制说明逐字＝「TXT / MD / 含文字层的 PDF / DOCX；单文件 ≤ 20 MiB；单批 ≤ 10 个、合计 ≤ 50 MiB」（`content-spec:151`；20 MiB＝`Document.byte_size` max 20971520，10 个/50 MiB＝`SRS §3.2`）。

**② 批次卡**：`batch_id`（示例 `batch_9F3K`）、文件数、状态、发布规则「**整批可见或整批不可见**」（`content-spec:152`）。

**③ 文件 5 种状态（必须全部画出）**：

| `content-spec` 标签（`:154–158`） | `Document` 判定字段 | 附加显示 | 缺口/备注 |
| --- | --- | --- | --- |
| 可检索 | `processing_state='available'` 且 `visibility='shared'` | — | — |
| 处理中（带进度） | `processing_state='processing'` | 进度指示 | **openapi 无进度数值字段**（只有状态枚举）→ 进度只能用不定式指示或由 `Task.state` 推断（登记 T4） |
| 失败 | `processing_state='failed'` | `error_code` 与原因：`content-spec:156`「未提取到文字，可能是扫描件；本期不支持 OCR。」 | 对应异步码 `NO_TEXT_EXTRACTED`（SRS §8；`FR-DOC-002`） |
| 删除中 | `processing_state='deleting'`（`visibility='removed'`） | `cleanup_state ∈ pending/running` | — |
| 删除失败 | `processing_state='delete_failed'` | `cleanup_state='failed'` + 按钮「重试清理」 | 对应 `CLEANUP_FAILED`（`FR-DOC-007`） |

**未覆盖的枚举值**：`rebuilding`、`deleted` 在 `content-spec` 里**没有对应标签**（重建中/已删除）→ 不得自造文案（登记 T5）。

**④ 整批可见性**：`Batch.published===true && Batch.state==='published'` 才算「整批可见」；任一文件 `processing_state='failed'` → 整批不发布、`state='compensating'`，并显示 `content-spec:159`「本批 1 个文件失败，整批未发布；其他批次不受影响。」（`FR-DOC-003`）

**⑤ 异步任务码（6 个，不是 HTTP 错误）**：`NO_TEXT_EXTRACTED`、`DOCUMENT_ENCRYPTED`、`PARSE_FAILED`、`EMBEDDING_FAILED`、`CLEANUP_FAILED`、`SERVICE_RESTARTED`（`API-REFERENCE.md` §0；SRS §8）→ 出现在 `Document.error_code` / `Task.error_code`，**不改变批次查询接口本身的 HTTP 状态**。

#### 交互与事件
1. 选择/拖拽文件 → 前端先查单批 ≤10 个、单文件 ≤20 MiB、合计 ≤50 MiB、后缀白名单 → `POST /admin/document-batches`（multipart）→ 202 后进入批次详情并开始轮询 `GET /admin/document-batches/{id}`（§9.0 J4）。
2. 同名文件：`409 DUPLICATE_FILENAME` → 提示要求「取消或作为独立文档继续」（`FR-DOC-004`）；继续时重传并带 `allow_duplicate_names=true`。
3. 列表行操作：`预览抽取文本`（按 `offset`/`next_offset` 分页加载）、`重建`、`删除`（带 `expected_version`，202 后 `deleting` → `deleted`/`delete_failed`）、`重试清理`。
4. 删除确认：`FR-DOC-006` 要求「首先提交不可见标记」；删除后新检索立即排除该文档——前端只需正确渲染 202 与后续状态，不承诺撤回已发出的答案文字。
5. 并发变更：`409 DOCUMENT_BUSY`（同一文档一次仅允许一个重建或删除变更，`FR-DOC-005`）→ 提示等待。
6. 列表额外信息「原名、类型、大小、上传时间、批次、错误原因」（`content-spec:160`）→ `original_name`/`file_type`/`byte_size`/`uploaded_at`/`batch_id`/`error_code`；**不展示服务器磁盘路径**（`FR-DOC-004`；openapi 也无该字段）。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| `UPLOAD_TOO_LARGE` | 413 | 上传区错误；整批不提交 | 复用 SRS §8 原文（限额已在限制说明里冻结） | 是 |
| `UNSUPPORTED_FILE_TYPE` | 415 | 选中文件标失败，其余可继续 | 复用 SRS §8 原文 | 是 |
| `DUPLICATE_FILENAME` | 409 | 提示取消或按独立文档继续 | 复用 SRS §8 原文（`FR-DOC-004` 语义） | 是 |
| `DOCUMENT_BUSY` | 409 | 禁用该行操作，提示等待 | 复用 SRS §8 原文 | 是 |
| `VERSION_CONFLICT` | 409 | 重新拉取该行（版本变了） | 复用 SRS §8 原文 | 是 |
| `VALIDATION_FAILED` | 422 | 字段错误 | 复用 SRS §8 原文 | 是 |
| `RESOURCE_NOT_FOUND` | 404 | 该文档/批次不存在 | 复用 SRS §8 原文 | 否 |
| `INTERNAL_ERROR`/`STORAGE_UNAVAILABLE` 等 | 500/503 | 保留列表现状 + `request_id` | 复用 SRS §8 原文 | 是 |
| 异步 `error_code` 6 个 | — | 只影响该文件/任务的状态与原因，**不整屏报错** | 复用 SRS §8 原文 | 视 `Task.retryable` |

#### 无障碍要点
表格 `<caption>` + `scope`；**状态三重**：5 种文件状态各自需要图标 + 文字 + 颜色（`NFR-UX-001`；「处理中」用 `pill--info`，**不得用 `pill--warn`**，#1）；上传区必须键盘可达（拖拽是增强，不是唯一通路）并提供可见按钮；预览文本放在可聚焦容器并说明可滚动；异步状态变化用 polite live region 播报（避免每 3s 播报一次，只在状态**变化**时播报）。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | **允许表格横向滚动**（`NFR-COMP-001`）；上传区纵向堆叠；预览区内部滚动 |
| `480–767` | 同上；表格可保持表格形态 |
| `≥ 768` | 表格形态；`.table-wrap{overflow-x:auto}` 兜底 |

### 9.12 S12 管理中心 · 课表维护（含重叠冲突确认）`/admin/schedules`

#### 路由与进入条件
`name=adminSchedules`；`requiresAuth+requiresAdmin`。屏幕块 `content-spec:163–171`。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求字段/参数 | 响应 `data` 字段 | 说明 |
| --- | --- | --- | --- | --- |
| 查询 | `GET /api/v1/admin/schedules` | **`student_id`（必填）**、`from_date`、`to_date`、`page`、`page_size` | `items[]: Schedule{id,student_id,course_id,course_name,class_date,start_time,end_time,location,version}`、`page`、`page_size`、`total`、`from_date`、`to_date`、`school_timezone` | `student_id` 必填 → 未选学生**不发请求** |
| 学生选择 | `GET /api/v1/admin/students` | `query`、`enabled`、`page`、`page_size` | `items[]: User{id,account,display_name,role,enabled,version}`、`page`、`page_size`、`total` | 搜索选择（`content-spec:164`） |
| 课程下拉 | `GET /api/v1/admin/courses` | `enabled=true`、`query` | `items[]: Course{...enabled...}` | **停用课程不可选**（`content-spec:164`；`FR-COURSE-001`） |
| 新增 | `POST /api/v1/admin/schedules` | `ScheduleCreate{student_id,course_id,class_date,start_time,end_time,location,overlap_acknowledged,reason(≤500)}` | `Schedule` | 201；**无 `Idempotency-Key`** |
| 修改 | `PATCH /api/v1/admin/schedules/{id}` | `SchedulePatch{course_id,class_date,start_time,end_time,location,overlap_acknowledged,reason,expected_version}` | `Schedule` | 200 |
| 删除 | `DELETE /api/v1/admin/schedules/{id}` | query `expected_version` | `ScheduleDelete{deleted,schedule_id,audit_id}` | 保留 `audit_id` 供审计（`FR-SCH-004`） |

#### 组件组成
`components/04-forms-data.md` §六 Table、§五 TableWrap、§一 Field、§二 Control、§三 FormGrid、§四 ErrorSummary、§八 Utility；`components/02-actions-status.md` Button、Notice、Pill。

#### 状态清单
| 状态 | 触发 | 表现 |
| --- | --- | --- |
| 未选学生 | 初始 | 不请求 `GET /admin/schedules`（`student_id` 必填）；空列表文案未冻结 → **不自造**（T6） |
| 列表有数据 | `total>0` | 展示该学生的记录（学生/课程/日期/起止/地点） |
| 表单 | 新增/编辑 | 字段＝学生（搜索选择）、课程（下拉，停用不可选）、上课日期、开始时间、结束时间、地点（`content-spec:164`） |
| 时段校验失败 | 提交前 | `content-spec:165` 文案 |
| 精确重复 | 409 `DUPLICATE_SCHEDULE` | 字段/表单级错误（文案 `content-spec:166`） |
| 时间重叠 | 409 `SCHEDULE_OVERLAP` | **冲突确认面板**（见下） |
| 删除前确认 | 点删除 | 展示学生、课程与时间供核对，并说明将记录操作人（`content-spec:171`） |
| 保存中/失败 | 飞行 / 非 2xx | 禁用 + `aria-busy`；失败按 §9.0 |

**冲突确认面板**（`content-spec:167–170`；`FR-SCH-004`）：冲突提示「与 2026-10-22 10:00–11:40 大学英语 时间重叠。」（`:168`，具体值取 `Error.details.overlaps[0]` 的 `class_date`/`start_time`/`end_time`/`course_name`）→ 重叠记录摘要（学生 / 课程 / 日期 / 起止 / 地点，取 `details.overlaps[]: Schedule`）→ 勾选/填写 **原因（必填，≤500 字）** + 主按钮「确认保存」+ 次级「取消」（`:170`）。确认后再提交 **`overlap_acknowledged=true` + `reason`**，且**服务端会重新检查**（`FR-SCH-004`：保存时应重新检查）→ 若再次 409，面板保持打开并刷新 `overlaps[]`。

#### 交互与事件
1. 选学生 → 请求 `GET /admin/schedules?...&student_id=`（默认当日或最近日期）。
2. 提交时段校验：结束必须晚于开始且同日（`content-spec:165`；`FR-SCH-003`）→ 不通过则不发请求。
3. `overlap_acknowledged` 只在用户在面板显式确认后才置 `true`；`reason` 与它**同时提交**。
4. 删除：核对摘要 → `DELETE ...?expected_version=` → 成功展示 `audit_id`（审计口径 `FR-OPS-001`）。
5. 用户归属创建后不可更改（`FR-SCH-003`）→ 编辑表单中 `student_id` 只读；「转移安排使用删除和新建完成」。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| `SCHEDULE_OVERLAP` | 409 | 打开/刷新冲突确认面板；`details.overlaps[]` 渲染摘要 | 「与 … 时间重叠。」（`content-spec:168`，值来自 `overlaps[0]`） | 是（填原因后确认） |
| `DUPLICATE_SCHEDULE` | 409 | 表单错误，不打开面板 | 「该学生在同一天已有完全相同时间段的这门课，不能重复保存。」（`content-spec:166`） | 是（改时间） |
| `VALIDATION_FAILED` | 422 | 字段错误 + 摘要聚焦；时段错误用冻结句 | `content-spec:165`／复用 SRS §8 原文 | 是 |
| `VERSION_CONFLICT` | 409 | 提示重载并保留编辑 | 复用 SRS §8 原文 | 是 |
| `RESOURCE_NOT_FOUND` | 404 | 记录已被删除 | 复用 SRS §8 原文 | 否 |
| `FORBIDDEN` | 403 | G4 | 复用 SRS §8 原文 | 否 |
| `INTERNAL_ERROR`/503 类 | 500/503 | 保留表单/面板 | 复用 SRS §8 原文 | 是 |

#### 无障碍要点
冲突面板必须可被读屏完整读取：用 `role="dialog"`（或 `fieldset`+`legend`）并在打开时移动焦点到面板标题、关闭后回触发按钮（判断项 J7：冻结源未指定结构）；「原因」必须可见 `<label>` + 「必填」文字标记（内容契约 §1）；确认与取消按钮 ≥44px 且语义分离；`overlaps[]` 摘要是表格/描述列表而非纯文本堆叠；错误先聚焦摘要。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | **允许表格横向滚动**（管理端，`NFR-COMP-001`）；表单单列；冲突面板全屏宽 |
| `480–767` | 同上 |
| `≥ 768` | 表格形态；`form-grid--2` 两列；面板限宽居中 |

### 9.13 S13 窄屏 390×844（响应式验收块）

#### 路由与进入条件
不是独立路由：S13 是**在 390×844（及 320 宽）下对 S01–S12 的逐屏验收**。进入方式：任一学生端路由 + 视口 390×844。屏幕块 `content-spec:173–177`。

#### 数据依赖（端点 + 字段）
与所验收的屏幕一致（S02–S06 用 `POST /chat/stream` 与 SSE 事件；S07–S09 用 `/me/schedules`、`/me/plans`）。**S13 本身不引入任何新端点**。

#### 组件组成
`components/01-shell-navigation.md` §5 Tabbar、§6 TabbarItem、§7 SkipLink、§9 Wrap；`components/04-forms-data.md` §五/§六/§七（表格→卡片规则）；`components/03-conversation.md` Composer、Steps。

#### 状态清单

逐屏窄屏行为如下表。

| 屏幕 | 390×844 必须成立的行为 | 依据 |
| --- | --- | --- |
| S01 登录 | 单列、420px 列被视口压到满宽；无横向滚动 | `content-spec:174`；`components/01-shell-navigation.md` §10 |
| S02–S06 助手 | 单列；过程区**折叠为一行摘要可展开**；输入区吸底（避开标签栏 56px + 安全区）；示例入口换行/横滑；气泡 ≤88% | `content-spec:174`；`rb.css:263/267/242` |
| S07–S08 课表 | **卡片式列表、无横向滚动**；两空态可区分 | `content-spec:175`；`FR-SCH-001` |
| S09 计划 | 表格卡片化；`data-label` 齐全；页面级溢出 0 | `content-spec` 隐含 + `b-responsive-spec.md` §5 |
| S10–S12 管理 | **允许表格横向滚动**（由 `.table-wrap` 承担，不是页面） | `content-spec:176`；`NFR-COMP-001` |

#### 交互与事件
1. 底部标签栏 4 项切换一级入口（`aria-current="page"` 跟随，§7.4）。
2. 跳过链接在第 1 次 Tab 时可见（`:focus`，`rb.css:118`），跳到 `#main`；**依赖 W1**（否则被 56.7px 顶栏遮挡）。
3. 过程区折叠控件（`.steps__toggle`）键盘可用：**W2 修的正是它聚焦无焦点**。
4. 触控目标：`.btn`/`.input`/`a.chip` ≥44px，`.tabbar__item` ≥56px（`verification.md` §4 实测 44.0/56.0）。

#### 错误分支
| 场景 | 本块行为 | 依据 |
| --- | --- | --- |
| 页面级横向溢出 >0 | **验收失败**：`documentElement.scrollWidth − clientWidth` 必须为 0（六个宽度） | `b-responsive-spec.md` §9 第 1 条 |
| 学生端（S07–S09）出现横向滚动 | 验收失败；管理端允许 | 契约 §3.7-10 |
| 长串（文件名/引用名）撑破 390 | 按 W3 修法处理（`.kv__v` 用 `minmax(0,1fr)`；`.cite__name`/`.card__body`/`.bubble` 加 `overflow-wrap`） | `design/system/README.md:218–226` |
| 焦点被吸底栏遮挡 | 验收失败（WCAG 2.2 2.4.11）：`.composer`/`.tabbar` 已预留占位（`rb.css:102/267`） | `b-responsive-spec.md` §7 |

#### 无障碍要点
390 下键盘走查必须覆盖：跳过链接 → 顶栏/标签栏 → 主内容 → 吸底输入区，全程焦点可见且不被遮挡；过程区折叠控件的焦点补偿（W2）；`.tabbar__item` 的当前态两重（颜色 + 字重）；触控目标实测值记录在验收报告。

#### 响应式行为
| 档位 | 阈值 | 本块口径 |
| --- | --- | --- |
| base | `< 480` | 最窄按 **320px** 验收（WCAG 1.4.10 Reflow） |
| xs | `≥ 480` | 过程区由折叠转常显；气泡 88% |
| sm | `≥ 768` | 导航换形态（顶栏内联）、表格恢复、表单两列 |
| md/lg/xl | `≥ 1024 / 1200 / 1440` | 本块只需确认「不再变宽、不放大字号」 |

验收尺寸：**320 / 390 / 768 / 1024 / 1366 / 1440**（`b-responsive-spec.md` §1；390×844 与 1366×768 为 SRS 明确要求）。

### 9.14 管理 · 学生 `/admin/students`（契约 §3.3 有路由，`content-spec` 无屏幕块）

#### 路由与进入条件
`name=adminStudents`；`requiresAuth+requiresAdmin`。**`content-spec` 的 S01–S13 没有对应屏幕块**：本屏需求来自 `FR-AUTH-003`（创建学生、查询列表、改显示名、启用/禁用）+ `CONTRACT.md` §3.3 路由表。**因此全部可见文案未冻结**（登记 T1）。

#### 数据依赖（端点 + 字段）
| 时机 | 端点 | 请求字段/参数 | 响应 `data` 字段 |
| --- | --- | --- | --- |
| 列表/筛选 | `GET /api/v1/admin/students` | `page`、`page_size`、`query`、`enabled` | `items[]: User{id,account,display_name,role(student\|admin),enabled,version}`、`page`、`page_size`、`total` |
| 新建 | `POST /api/v1/admin/students` | `StudentCreate{account(3–64),display_name(1–50),initial_password}` | `User`（201） |
| 编辑 | `PATCH /api/v1/admin/students/{id}` | `StudentPatch{display_name,enabled,expected_version}` | `User`（200） |
| 无 | — | — | **没有删除用户接口、没有自助注册、没有授予管理员的接口**（`FR-AUTH-003`）→ 界面不得出现对应入口 |

#### 组件组成
`components/04-forms-data.md` §六 Table、§五 TableWrap、§一 Field、§二 Control、§三 FormGrid、§四 ErrorSummary；`components/02-actions-status.md` Button、Pill、Notice。

#### 状态清单
| 状态 | 触发 | 表现（**文案均未冻结，实现前必须补 `content-spec` 屏幕块**） |
| --- | --- | --- |
| 列表有数据 | `total>0` | 表格列＝账号 / 显示名 / 角色 / 状态 / 操作（列名待冻结） |
| 空列表 | `items=[]` | 用 `.empty`，文案待冻结 |
| 新建 | 点新建 | 账号 / 显示名 / 初始口令；账号唯一且**创建后不可修改** |
| 编辑 | 点编辑 | 仅 `display_name` 与 `enabled`；`role` 不可设（`FR-AUTH-003`） |
| 重复账号 | 409 | 字段错误，文案待冻结 |
| 禁用/启用 | `PATCH {enabled}` | 禁用即撤销该账号全部会话（`FR-AUTH-002`） |

#### 交互与事件
1. 搜索/筛选：`query` + `enabled`（不进 URL，J1）。
2. 新建：`POST /admin/students`，`initial_password` 只提交一次、**绝不回显、不进日志/遥测**（`NFR-SEC-002`）。
3. 编辑：`PATCH` 带 `expected_version`；禁用为高影响操作 → 需二次确认（内容契约 §1「危险操作」口径）。
4. 不得提供「设为管理员」入口（`FR-AUTH-003`）。

#### 错误分支
| 码 | HTTP | 本屏行为 | 文案 | 可重试 |
| --- | --- | --- | --- | --- |
| `DUPLICATE_ACCOUNT` | 409 | 账号字段错误 | 复用 SRS §8 原文（冻结句缺失，T1） | 是 |
| `VERSION_CONFLICT` | 409 | 重载并保留编辑 | 复用 SRS §8 原文 | 是 |
| `VALIDATION_FAILED` | 422 | 字段错误 + 摘要 | 复用 SRS §8 原文 | 是 |
| `RESOURCE_NOT_FOUND` | 404 | 目标不存在 | 复用 SRS §8 原文 | 否 |
| `FORBIDDEN` | 403 | G4 | 复用 SRS §8 原文 | 否 |

#### 无障碍要点
表格 `<caption>`/`scope`；初始口令输入为 `type="password"` 且**不提供复制按钮**；禁用/启用是状态变更 → 图标 + 文字 + 颜色三重；二次确认面板焦点管理；表单错误聚焦摘要。

#### 响应式行为
| 档位 | 行为 |
| --- | --- |
| `< 480` | 允许表格横向滚动（管理端，`NFR-COMP-001`） |
| `480–767` | 同上 |
| `≥ 768` | 表格形态；`form-grid--2` 两列 |

### 9.15 本册登记的实现待定项（供 §16 收录）

| # | 事项 | 事实与依据 | 建议处理 |
| --- | --- | --- | --- |
| **T1** | `/admin/students` 没有任何 `content-spec` 屏幕块与冻结文案 | `content-spec` S01–S13 无此屏；`FR-AUTH-003` 要求该能力；`CONTRACT.md` §3.3 已给它路由 | 先在 `content-spec` 补一块（列名/按钮/空态/错误文案），再实现；否则本屏只能「复用 SRS §8 原文」且没有标题类文案 |
| **T2** | S01 密码显示/隐藏切换的**文案未冻结** | `content-spec:54` 要求控件；`design/system/README.md:144` 裁决 6 已定性为内容契约缺口 | 冻结文案 + `aria-pressed` 语义后再实现（本册 §9.1 已标注为阻塞） |
| **T3** | 「账号被禁用」在登录接口上对应哪个 HTTP/code 未绑定 | openapi `POST /auth/login` 同时声明 401 与 403；SRS §8 只把 `FORBIDDEN` 绑定到「角色无权操作管理能力」 | 后端确认后写入 §3.4 映射表；本册暂按 403→状态 B、401→状态 A，并标为判断项 |
| **T4** | S11「处理中（带进度）」**没有进度数值字段** | `Document.processing_state` 只有枚举；`Batch`/`Task` 也无百分比字段 | 或后端补字段，或产品把「带进度」降级为不定式指示（当前不得伪装进度） |
| **T5** | `processing_state` 的 `rebuilding` / `deleted` 无 `content-spec` 标签 | 枚举有 7 值，`content-spec:154–158` 只冻结 5 种 | 补两块标签文案（重建中/已删除），否则这两个状态下界面无合格文案 |
| **T6** | 若干空态/按钮的可访问名或空态文案未冻结（S07 日期切换按钮名、S10/S12 未选学生与空列表） | `content-spec` 只给 S08/S09 的空态句 | 补冻结或明确「复用 SRS §8 原文」的写法；本册未自造 |
| **J1** | 列表筛选/分页**不进 URL** | 本册深链口径只有 `/me/plans/:planId`（task-12）；`HLD-D11` 不承诺恢复视图状态 | 若产品要可分享筛选，需改这条口径 |
| **J2** | `document.title` 的后缀「· 校园课程智能助手」 | 无真源冻结写法 | 统一到一个常量，勿散落 |
| **J3** | `Me.capabilities` 是 `array<string>`，**枚举未冻结** | openapi 只给类型 | 前端不得写死 capability 字符串；用于功能开关前需冻结取值 |
| **J4** | 轮询间隔 | 任何真源都未冻结间隔 | **三类分开，不是一套**：① `operation_id` 写操作核实 → **以 §6.9 为唯一权威表**（`1s→2s→4s→8s→10s 封顶`）；② 管理端批次状态 → 暂定 3s 起、退避到 10s；③ 列表搜索 debounce → 暂定 300ms。三者均页面不可见即暂停。已按 §16.5 J25 统一，**不得再出现第三套数值** |
| **J5** | 「打开计划」是 `<a>` 还是 `<button>` | 两种语义都可用；`FR-PLAN-005` 只要求「提供 plan_id 和详情入口」 | 建议 `<a href>`（可新标签打开、可复制链接），并在组件规格里固定 |
| **J6** | `GET /admin/documents` 的 `state` 参数是**自由字符串**（1–32，无枚举） | `API-REFERENCE.md`：`state` string | 筛选下拉的取值域需后端冻结，否则前端只能按 `processing_state` 枚举做前端筛选 |
| **J7** | 冲突确认面板与删除确认面板的结构（`dialog` vs `fieldset`） | 设计系统未定义弹层组件 | 用现有组件组合（`.card`+`.fieldset` 语义），不新增组件族 |
| **已核对** | 契约 §3.7-1 的「26 个 `/api/v1/*`」与 `openapi_v0.1.json` **逐条一致** | 脚本清点：公开路径 **26** 条、内部 `/internal/v1/*` **4** 条，合计 30 条路径（契约 §2 的「30 个 path」同源） | 本册引用的公开路径全部命中、0 条越界、0 条引用内部接口（见下表「自检」） |

**自检（本册，脚本可复现）**

| 判据 | 做法 | 结果 |
| --- | --- | --- |
| 端点真实 | 抽取本册所有 `/api/v1/...` 字面，与 `openapi_v0.1.json` 的 `paths` 键集合比对 | 引用 **26** 条，全部命中；越界 **0**；引用 `/internal/v1/*` **0** |
| 错误码合法 | 抽取本册所有全大写下划线标识，与「openapi 28 个同步码 + SRS §8 的 6 个异步码 + SSE `ACCEPTED`」求差 | 越界 **0** |
| 字段名真实 | 抽取本册全部反引号 `snake_case` 标识（115 个），与「openapi 全部 schema 属性 + 参数名 + SSE 字段 + 三白名单工具名 + 契约 §3.5 状态名」比对 | 未命中 19 个，全部为 HTML/ARIA 术语（`dialog`/`fieldset`/`legend`/`scope`/`thead`/`readonly`/`disabled`）、SSE 事件名（`tool_start`/`tool_end`/`done`）、契约状态名（`submitting`/`unknown`/`protocol_violation`）、`Error.error.field_errors` 与 3 个工具名——**无自造字段** |
| 屏幕齐全 | 检查 `### 9.1`–`### 9.13` 与每屏 8 个固定小节 | 13/13 齐全，8×13 小节齐全 |
| 违禁表述 | 全文检索契约 §3.7-3 的禁用表述与合并式「空」说法 | 0 命中 |
| 结构 | 首行 `<!-- part: ... -->`；无 `#` 一级标题；仅有 `## 7.` 与 `## 9.` | 通过 |

