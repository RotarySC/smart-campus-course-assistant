# 前端详细设计 · 写作契约（冻结）

本文件是**并行写作的唯一接口**。所有章节作者必须遵守；改动本文件视为改契约，需 Lead 同意。

## 1. 交付物与文件划分

最终交付物：**`docs/校园课程智能助手_前端详细设计_v0.1.md`**（单文件，与 `docs/校园课程智能助手_后端详细设计_v0.1.md` 平行）。

作者写**各自的分册文件**，Lead 用 `docs/frontend-detail/build.py` 拼装成最终单文件：

| 分册（作者写这个） | 章节 | 作者 |
| --- | --- | --- |
| `parts/10-baseline-and-modules.md` | 1 技术基线 · 2 工程组织与模块界面 · 3 类型·错误·请求层 | Lead |
| `parts/20-sse-client.md` | 5 流式会话客户端（核心） | Lead |
| `parts/30-session-and-state.md` | 4 会话与鉴权 · 6 状态管理 | sys-actions |
| `parts/40-routing-and-screens.md` | 7 路由与导航 · 9 页面详细设计 S01–S13 | sys-shell |
| `parts/50-design-system-and-a11y.md` | 8 设计系统落地 · 10 组件 Vue 映射 · 12 无障碍与响应式实现 | sys-convo |
| `parts/60-forms-and-observability.md` | 11 表单·校验·写入确认 · 13 降级·错误·可观测 · 14 构建·配置·性能 · 15 验证方案与需求追踪 | sys-forms |
| `parts/90-open-items.md` | 16 待定项与实现入口条件 | Lead |

**章节编号固定**：`## 1.` … `## 16.`，子节 `### 1.1`，再下 `#### 1.1.1`。分册文件里**不要写 `#` 一级标题**（
Lead 会加文档标题），直接从 `## N.` 开始。分册第一行必须是声明注释：

```
<!-- part: 30-session-and-state; chapters: 4,6; owner: sys-actions -->
```

## 2. 上游真源（只读，不得改写）

| 真源 | 用途 |
| --- | --- |
| `docs/校园课程智能助手_PRD_v0.1.md` | 需求与业务规则编号（`PRD §5.1`、`QA-01`…） |
| `docs/校园课程智能助手_SRS_v0.1.md` | 功能／非功能需求编号（`FR-CHAT-003`、`NFR-UX-001`、`§8` 错误与异步码） |
| `docs/校园课程智能助手_HLD_v0.1.md` | 架构决策 `HLD-D01`–`HLD-D12` |
| `docs/backend/openapi_v0.1.json` | **端点与字段的唯一来源**（30 个 path，其中 4 个 `/internal/v1/*` 前端不得调用） |
| `docs/frontend-detail/API-REFERENCE.md` | **字段名的唯一来源（自动生成，只读）**：26 个公开端点逐条的请求体/参数/响应 `data` 字段 + 28 个同步错误码 + 6 个异步任务码。写文档时**照这里抄字段名**，不要凭记忆 |
| `docs/backend/sse_events_v0.1.schema.json` | **SSE 事件与字段的唯一来源** |
| `docs/backend/mcp_tools_v0.1.json` | 三个白名单工具（仅用于「工具白名单」表述，前端不直接调用） |
| `docs/backend/cca_schema_v0.1.sql` | 字段约束（仅作为理解后端语义的参考） |
| `design/system/tokens.json` / `tokens.css` / `tokens.md` | **样式与 token 的唯一来源**（518 个 token，四层） |
| `design/system/components/01–04*.md` | **组件 API 规格**（27 个组件族） |
| `design/directions/shared/content-spec.md` | **逐字文案的唯一来源**（S01–S13） |
| `docs/校园课程智能助手_后端详细设计_v0.1.md` | 与后端对齐的既有口径（§8 SSE、§12 端点目录） |

## 3. 冻结的架构口径（不得各自另立）

### 3.1 技术栈

| 项 | 冻结值 | 依据 |
| --- | --- | --- |
| 框架 | **Vue 3** + TypeScript（`strict`） | HLD-D01 |
| 构建 | Vite | HLD-D01 的落地细化 |
| 状态 | Pinia | 需跨路由持有对话流与会话态 |
| 路由 | vue-router 4，**history 模式** | 深链需求；但对话正文不入 URL（见 §3.3） |
| HTTP | **原生 `fetch`**，不引入 axios | 流式 reader 本来就要 fetch，避免两条请求通路 |
| UI 框架 / CSS 框架 | **无**。不自绘组件库、不引入 Tailwind | 设计系统已是唯一样式真源，引入第二套会造成双真源 |
| 样式 | 组件 `<style>` **只消费 L3 token**（`--<组件>-<部位>-<属性>`） | `design/system/README.md` 分层纯度规则 4 |
| 测试 | Vitest（单测）· @vue/test-utils（组件）· Playwright（E2E） | §15 |
| Lint | ESLint + `stylelint`（自定义规则：禁裸 hex／裸长度、禁消费 L1/L2） | 把分层规则做成 CI 门 |

### 3.2 目标目录（冻结；不得自创平行目录）

```
web/
├─ index.html  vite.config.ts  tsconfig.json  package.json
├─ .stylelintrc.cjs            # 分层纯度门 + 禁裸值
└─ src/
   ├─ main.ts  App.vue         # App.vue = 外壳（顶栏/标签栏/路由出口）
   ├─ styles/
   │  ├─ tokens.css            # 从 design/system/tokens.css 同步（生成物，勿手改）
   │  ├─ global.css            # html/body/元素级全局规则（消费 L3）
   │  └─ base.css              # 27 个组件族样式（消费 L3）；按族分块并标注 rb.css 行号锚点
   ├─ api/
   │  ├─ client.ts             # fetch 封装、认证头、错误归一化、超时、requestId
   │  ├─ errors.ts             # 错误码 → AppError（码表见 §3.6）
   │  ├─ types.gen.ts          # 由 openapi 生成（勿手改）
   │  ├─ auth.ts me.ts chat.ts admin.ts citations.ts
   │  └─ sse/
   │     ├─ parse.ts           # 字节流 → SSE 事件（分包 / UTF-8 边界 / 多行 data）
   │     └─ stream.ts          # POST+fetch reader、状态机、去重、取消
   ├─ domain/                  # 纯函数，不依赖 DOM / store
   │  ├─ chatMachine.ts  dedupe.ts  validate.ts  mapError.ts  format.ts
   ├─ stores/
   │  ├─ session.ts chat.ts schedules.ts plans.ts drafts.ts writeOps.ts admin.ts ui.ts
   ├─ router/  index.ts routes.ts guards.ts
   ├─ components/
   │  ├─ base/                 # 与 design/system/components 的 27 族一一对应
   │  └─ product/              # 组合件：ChatStream/CitationList/DraftCard/ScheduleTable/BatchPanel…
   ├─ views/                   # S01–S13 对应视图
   └─ a11y/  live.ts focus.ts
```

### 3.3 路由表（冻结）

| 路径 | name | 视图 | 屏幕 | 守卫 |
| --- | --- | --- | --- | --- |
| `/login` | `login` | `LoginView` | S01 | 已登录则重定向到 `assistant` |
| `/assistant` | `assistant` | `AssistantView` | S02–S06 | 需会话；**登录后默认页** |
| `/me/schedules` | `schedules` | `MyScheduleView` | S07–S08 | 需会话 |
| `/me/plans` | `plans` | `PlansView` | S09 | 需会话 |
| `/me/plans/:planId` | `planDetail` | `PlanDetailView` | S09 详情 | 需会话 |
| `/admin/courses` | `adminCourses` | `AdminCoursesView` | S10 | 需会话 + 管理员 |
| `/admin/documents` | `adminDocuments` | `AdminDocumentsView` | S11 | 需会话 + 管理员 |
| `/admin/document-batches/:batchId` | `adminBatch` | `AdminBatchView` | S11 批次 | 需会话 + 管理员 |
| `/admin/schedules` | `adminSchedules` | `AdminScheduleView` | S12 | 需会话 + 管理员 |
| `/admin/students` | `adminStudents` | `AdminStudentsView` | 管理 · 学生 | 需会话 + 管理员 |

**对话正文不进 URL**（SRS DEC-01／CHAT-03、HLD-D11）：`/assistant` 不带 `?q=`、不带对话 id、
不把轮次写进 `history`。理由写进 §7：会话令牌仅存内存、刷新即失效，写进 URL 等于承诺不存在的恢复能力。

### 3.4 store 名称与职责（冻结）

| store | 职责 |
| --- | --- |
| `session` | 令牌（内存）、`/me` 身份、登录/登出、会话失效处理 |
| `chat` | 当前对话轮次列表、进行中请求的流式状态、`request_id`、终态 |
| `schedules` | 我的课表；两种空态 |
| `plans` | 计划列表与详情、`version`（并发控制） |
| `drafts` | 草稿（未保存/已保存）、`draft_version` |
| `writeOps` | 写操作结果未知时的「待确认」态与 `operation_id` 核实轮询 |
| `admin` | 课程/学生/课表维护、文档与批次 |
| `ui` | 断点、live region 文案、全局提示 |

### 3.5 流式状态机（**权威口径，不得各自另立**）

状态：`idle → submitting → streaming → terminal`

`terminal ∈ { succeeded, cancelled, failed, unknown }`

| 事件 | 转换与必须做的动作 |
| --- | --- |
| 发起 | `submitting`；带 `Idempotency-Key`；记录 `request_id`（来自响应或首事件） |
| `status` | → `streaming`；`code=ACCEPTED` 时**必须**取到 `conversation_id`（schema 强制）；`code` 属容量类（`CAPACITY_LIMITED`/`CALL_LIMIT_REACHED`）时给出可理解提示 |
| `tool_start` | → `streaming`；按 `tool_call_id` 建步骤；`tool_name` 只可能是三个白名单值 |
| `tool_end` | 按 `tool_call_id` 配对；`success=false` ⇒ `result_status=failed` 且 `code` 必填；`created`/`existing` 都算**成功**（后者表示幂等命中，不是错误） |
| `token` | 追加 `text_delta` 到 `answer_block_id` 对应块；**不得抢焦点**（NFR-UX-001） |
| `done` | → `terminal`；`state∈{succeeded,cancelled}`；`citations` 以此为准 |
| `error` | → `terminal failed`；`code=AUTH_REQUIRED|SESSION_EXPIRED` 时**不得**携带 `plan_id`/`operation_id`，前端清空会话并跳 `/login` |
| 第二个终态事件 | **忽略**并记 `protocol_violation`（一个轮次最多一个终态） |
| `seq` 非严格递增 / 重复 | 按 `(request_id, seq)` 去重；`seq ≤ lastSeq` 直接丢弃；**不得**用「覆盖」代替去重 |
| 流结束但**无终态** | → `unknown`。**HTTP 关闭 ≠ 终态**。写操作落「待确认」并用 `operation_id` 核实；读操作提示未完成且可重试 |
| 取消 | `POST /chat/requests/{request_id}/cancel` + `AbortController.abort()`；取消后仍以服务端终态为准 |
| 断线 | **不自动重连、不续传**（HLD-D07／HLD-D11）：提示失败，允许用户重发（新 `request_id`） |

### 3.6 错误码允许集合（**唯一合法来源，禁自造**）

- **HTTP 同步码**：`docs/backend/openapi_v0.1.json` 中所有「全大写＋下划线」的 `code` 枚举的并集。校验脚本会自行求并集，**不要凭记忆写**。
- **异步任务码**：`NO_TEXT_EXTRACTED`、`DOCUMENT_ENCRYPTED`、`PARSE_FAILED`、`EMBEDDING_FAILED`、`CLEANUP_FAILED`、`SERVICE_RESTARTED`（SRS §8）。
- 前端映射表列固定为：`码 | HTTP | 触发场景 | 前端行为 | 用户可见文案（来源） | 是否可重试`。
- **文案不得自造**：逐字取自 `content-spec.md`／SRS §8；没有对应文案的码，写「复用 SRS §8 原文」并标注它，不得自行编写面向用户的句子。
- 页面级只允许用 `content-spec.md` 里已冻结的坏消息文案。

### 3.7 硬规则（违反即 FAIL）

1. **不得发明端点**：只能引用 `openapi_v0.1.json` 里的 26 个 `/api/v1/*`；4 个 `/internal/v1/*` 前端**不得调用**。
2. **不得发明错误码**（见 §3.6）。
3. **不得发明文案**；不得出现「正在思考」「AI 推理中」「推理过程」「思考中」；不得用「暂无数据」「暂无内容」合并「成功的空」与「失败的空」。
4. **令牌只在内存**：不得进 URL／`localStorage`／`sessionStorage`／`IndexedDB`／遥测／文件名／错误栈（NFR-SEC-002、HLD-D03）。
5. **组件样式只消费 L3 token**；需要新 token 时**不得就地写死**，须登记到 `tokens.json` 并重跑 `design/system/generate.py`。
6. **不得给组件补 `rb.css` 里不存在的状态**（如 `:active`、`transition`）——设计系统已机械核对过这一点。
7. 状态表达必须**图标 + 文字 + 颜色**三重（NFR-UX-001）。
8. 触控目标 ≥44px；断点只用 480／767／768／1024／1200／1440。
9. 引用标注必须能区分**已验证**与**未验证**（SRS FR-QA-002／IF-007）。
10. 管理端页面在窄屏允许表格横向滚动（NFR-COMP-001），但学生端核心流程（S07–S09）不得页面级横向溢出。

### 3.8 散文风格

- 中文；**表格优先**，能用表说清就不用段落。
- 每个关键论断后面给**编号或行号依据**（`SRS FR-CHAT-005`、`HLD-D07`、`openapi /api/v1/chat/stream`、
  `design/system/components/02-actions-status.md §4`、`rb.css:216`）。无依据的判断要显式写成「判断项」。
- 不写愿景、不写「总之」；写可执行的接口、序列、字段、状态、错误分支。
- 接口签名用 TS；流程用编号步骤或 mermaid（**只允许 `sequenceDiagram` 与 `flowchart`**，不得用需要外部渲染的图）。
- 篇幅不是目标，**可核对性**是目标。分册之间不重复：需要别章结论时用「见 §6.2」。

## 4. 与设计系统的接口（前置条件）

样式与组件**不要重新设计**，直接引用设计系统；设计系统里的 6 个必修项是本设计文档的**前置条件**，
必须在实现前修掉（详见 `design/system/README.md` 的裁决表与 W1–W3）：

| 编号 | 必修项 | 影响 |
| --- | --- | --- |
| #1 | 原型用 `pill--warn` 表示「处理中」→ 改 `pill--info`（2 处） | 状态语义 |
| #3 | `records.html:273` 危险胶囊自身缺图标 | 状态三重表达 |
| #6 | `content-spec` 点名密码显示/隐藏切换却未冻结文案 | 需先冻结文案再实现 |
| W1 | 缺 `scroll-padding-top`，锚点/skip-link 被顶栏遮挡 56.4–56.7px | 可用性 |
| W2 | `.steps__toggle` 聚焦无可见焦点（WCAG 2.4.7） | 无障碍 |
| W3 | `.kv__row{8em 1fr}` 的 `1fr` 下限 = min-content；`.cite__name` 等缺 `overflow-wrap` | 长串溢出 |

写作时：引用组件规格即可，**不要复制**它们的 token 表；需要时给「见 `components/03-conversation.md §5`」。
