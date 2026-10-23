<!-- part: 10-baseline-and-modules; chapters: 1,2,3; owner: lead -->
## 1. 设计产物与技术基线

### 1.1 产物清单

本文件是**前端详细设计**，与 `docs/校园课程智能助手_后端详细设计_v0.1.md` 平行。上游输入与下游承接如下。

| 类别 | 产物 | 关系 |
| --- | --- | --- |
| 上游需求 | `PRD_v0.1.md`、`SRS_v0.1.md`、`HLD_v0.1.md` | 本文的实现依据；编号引用一律用 `PRD §x` / `FR-xxx` / `HLD-Dxx` |
| 上游契约 | `docs/backend/openapi_v0.1.json`、`sse_events_v0.1.schema.json`、`mcp_tools_v0.1.json`、`cca_schema_v0.1.sql` | 端点、字段、事件、工具白名单的**唯一来源** |
| 上游设计 | `design/responsive/`（已冻结并通过六宽度渲染验证的响应式原型 + `rb.css`） | 视觉与响应式行为的基线 |
| 上游设计 | `design/system/`（518 个 token 的四层设计系统 + 27 个组件族 API 规格 + 活样式手册） | 样式与组件的唯一真源；本文**引用而不复制** |
| 上游内容 | `design/directions/shared/content-spec.md`（S01–S13 逐字文案） | 用户可见文案的唯一来源 |
| 本文 | 16 章；分册见 `docs/frontend-detail/CONTRACT.md` | 前端实现入口条件见 §16 |
| 下游 | Vue 3 + TypeScript 工程（目前尚未创建，目标目录见 §2.1） | 本文交付后进入实现 |
| 不在本文范围 | 后端实现、MCP 内部接口实现、向量库选型、部署与运维 | 见后端详细设计与 HLD |

**本文不含**：可运行的代码、组件视觉稿（已在设计系统里冻结）、性能实测数据（无实现可测，见 §14 与 §15）。

### 1.2 技术选择

HLD-D01 只锁定「Vue + TypeScript」，其余由本文锁定并给出理由；锁定值同时写入 `CONTRACT.md` §3.1。

| 项 | 冻结值 | 理由 | 依据 |
| --- | --- | --- | --- |
| 框架 | Vue 3（Composition API，`<script setup>`） | HLD-D01 已定；组合式 API 便于把流式解析与 UI 解耦成可单测的纯函数 | HLD-D01 |
| 语言 | TypeScript，`strict: true` | 端点字段与 SSE 事件字段都由 JSON Schema 可生成类型，`strict` 让契约漂移在编译期暴露 | HLD-D12 |
| 构建 | Vite | 原生 ESM 开发服务器；按路由分包；官方 Vue 支持 | — |
| 状态 | Pinia | 对话流与流式状态需跨路由存活；避免把流状态塞进组件树 | HLD-D11 |
| 路由 | vue-router 4，history 模式 | 深链入门（`/me/plans/{id}`）；但对话正文不入 URL（§7.3） | SRS DEC-01 |
| HTTP | **原生 `fetch`** | 流式必须用 `fetch` + `ReadableStream` reader；同时保留 axios 会造成两条请求通路与两套错误语义 | HLD-D07 |
| UI / CSS 框架 | **不引入**（含 Tailwind） | 设计系统已是样式唯一真源；引入第二套会产生双真源与"该改哪个"的持续歧义 | `design/system/README.md` |
| 样式落地 | 组件 `<style>` **只消费 L3 token**，并用 `stylelint` 自定义规则做成 CI 门 | 把分层纯度从文档约定变成机器约束 | §8 |
| Markdown 渲染 | 自实现白名单渲染（**不引入** `v-html` 直出） | 需清除脚本、事件处理器与危险 URI | NFR-SEC-003 |
| 测试 | Vitest（纯函数与 store）· @vue/test-utils（组件）· Playwright（E2E 与流式） | §15 |
| 时间/日期 | 原生 `Intl` + `Temporal` 不可用时用 `Date` 封装在 `domain/format.ts` | 日期跨字段校验与展示需统一口径（§11） |

**明确不做的选择及其原因**（避免评审时反复）：

| 不做 | 原因 |
| --- | --- |
| 服务端渲染（SSR） | 会话令牌仅存内存（HLD-D03），SSR 无法携带会话；且试点为内网单机，首屏指标无 SSR 诉求 |
| 自动重连 / 断点续传 | HLD-D07 明确「不以自动重连恢复执行」、HLD-D11 明确「不承诺正文断线续传」 |
| 把对话正文持久化到浏览器 | HLD-D11：正文只驻留浏览器内存与运行内存 |
| SW / 离线缓存 | 与「刷新即需重新登录」冲突，且会引入令牌或正文的落盘风险（NFR-SEC-002） |
| 多标签页会话共享 | 令牌在内存 ⇒ 新标签页天然无会话；共享需落盘，与 NFR-SEC-002 冲突（§4.5 说明其后果） |

### 1.3 对 HLD 的细化

| HLD 决策 | 前端落点 | 章节 |
| --- | --- | --- |
| HLD-D01 客户端技术路线 | 冻结为 §1.2 的选型表；工程结构与模块边界见 §2 | §1.2、§2 |
| HLD-D03 不透明 Bearer、仅内存、刷新需重登 | 令牌只存在于 `session` store 的模块级变量；逐条否定 7 个泄漏面 | §4 |
| HLD-D07 POST + Fetch 流式读取、不自动重连、须处理分包/去重/状态核实 | 流式客户端：字节流解析器 + 事件状态机 + 去重 + 未知终态核实 | §5 |
| HLD-D11 正文只驻留浏览器与服务端运行内存 | 不持久化任何正文；`chat` store 不落盘；不提供跨设备或断线恢复 | §6.4 |
| HLD-D12 统一 `request_id`、错误码、结果状态 | 请求层统一提取 `{request_id, data}` 信封；`AppError` 携带 `requestId`；埋点以它为关联键 | §3、§13 |
| SRS IF-010 同一错误在 API/SSE/MCP 用相同 code | 流内**没有 HTTP 状态**，只能靠 `error.code` / `tool_end.code`；前端不得用状态码判断流内错误 | §5.6 |
| NFR-REL-001 依赖故障时直接业务仍可用 | 降级矩阵按功能逐项给「可用/不可用/只读」 | §13.2 |
| NFR-UX-001 状态不只靠颜色、流式内容不抢焦点 | 状态三重表达 + `aria-live` 节流策略 + 焦点落点规则 | §12 |
| NFR-COMP-001 浏览器与视口 | Chrome/Edge 当前稳定版 + 前一主要版本；1366×768 与 390×844 为核心验收视口 | §12.7 |

## 2. 工程组织与模块界面

### 2.1 目标目录

目录结构与 `CONTRACT.md` §3.2 一致，落地时**不得自创平行目录**。

```
web/
├─ index.html  vite.config.ts  tsconfig.json  package.json
├─ .stylelintrc.cjs              # 分层纯度门：禁裸 hex/裸长度、禁消费 L1/L2
└─ src/
   ├─ main.ts  App.vue           # App.vue = 外壳（顶栏 / 底部标签栏 / 路由出口）
   ├─ styles/
   │  ├─ tokens.css              # 由 design/system/tokens.css 同步（生成物，勿手改）
   │  ├─ global.css              # html/body 与元素级全局规则（消费 L3）
   │  └─ base.css                # 27 个组件族样式；按族分块并标注 rb.css 行号锚点
   ├─ api/
   │  ├─ client.ts               # fetch 封装：认证头、超时、信封解包、错误归一化
   │  ├─ errors.ts               # 码表与 AppError 构造（与 §3.4 一一对应）
   │  ├─ types.gen.ts            # 由 openapi 生成（勿手改）
   │  ├─ auth.ts  me.ts  chat.ts  admin.ts  citations.ts
   │  └─ sse/ parse.ts  stream.ts
   ├─ domain/                    # 纯函数，不碰 DOM、不碰 store、可 100% 单测
   │  ├─ chatMachine.ts  dedupe.ts  validate.ts  mapError.ts  format.ts
   ├─ stores/                    # 会话与业务状态（8 个，名字固定，见 §6.1）
   ├─ router/ index.ts  routes.ts  guards.ts
   ├─ components/ base/  product/
   ├─ views/                     # S01–S13
   └─ a11y/ live.ts  focus.ts
```

### 2.2 模块边界与依赖方向

依赖**只能向下**，禁止反向与跨层回环：

```
views/  components/
      ↓
stores/            ← 唯一持有跨路由状态的地方
      ↓
api/  domain/      ← api 管 I/O；domain 是纯函数
      ↓
styles/（tokens.css 由构建期同步）
```

| 规则 | 内容 | 违例后果 |
| --- | --- | --- |
| R1 | `domain/**` **不得** import `stores/**`、`api/**`、`vue` 之外的任何东西；不得有副作用 | 无法单测；流式逻辑会与 UI 耦合 |
| R2 | `api/**` 不得 import `stores/**`（令牌通过参数注入，见 §3.2） | 循环依赖 |
| R3 | `stores/**` 之间禁止环形依赖；允许的依赖方向在 §6.5 穷举 | 初始化顺序不确定 |
| R4 | `components/base/**` 不得 import `api/**` 或 `stores/**`（纯展示组件） | 组件复用性丧失，无法在设计系统层面核对 |
| R5 | 只有 `views/**` 可以读多个 store 并组合 | 逻辑散落 |
| R6 | `styles/base.css` 里不得出现裸 hex、裸长度、`--p-*`、L2 语义名 | `stylelint` 直接失败（§8.3） |

`domain/` 是本文最看重的一层：**流式解析、去重、状态机、校验、错误映射都放在这里**，因为它们是最容易出错、
又最适合被纯函数单测覆盖的部分（§15.2 的高风险用例全部落在这一层）。

### 2.3 主要接口签名

```ts
// ---------- api/client.ts ----------
export interface RequestOptions {
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  path: string                                   // 必须是 API-REFERENCE.md 里的路径
  query?: Record<string, string | number | undefined>
  body?: unknown
  idempotencyKey?: string                        // 仅 4 个端点允许（见 API-REFERENCE §0）
  signal?: AbortSignal
  timeoutMs?: number                             // 默认 15_000；流式不走此超时
  auth?: AuthSnapshot                            // 令牌以参数注入，见 R2
}
export interface Envelope<T> { request_id: string; data: T }

/** 成功返回 data；失败抛 AppError。所有响应信封的 request_id 都会被保留到 AppError.requestId。 */
export function request<T>(o: RequestOptions): Promise<T>

// ---------- api/sse/parse.ts ----------
/** 字节流 → SSE 事件。纯函数式增量解析，可在单测里用任意分片喂入。 */
export interface SseParser {
  /** 喂入一个 Uint8Array 分片（可能是半个多字节字符、半个事件） */
  push(chunk: Uint8Array): SseEvent[]
  /** 流结束：返回残留缓冲的诊断信息（不产生事件） */
  end(): { pendingBytes: number; pendingEvent: string }
}
export function createSseParser(): SseParser

// ---------- api/sse/stream.ts ----------
export interface StreamHandlers {
  onEvent(e: SseEvent): void
  onTerminal(t: TerminalState): void
  onProtocolIssue(issue: ProtocolIssue): void
}
export interface StreamResult {
  requestId: string
  terminal: TerminalState            // 含 unknown
  events: SseEvent[]                 // 已按 seq 去重后的完整序列（用于调试与埋点）
}
export function startChatStream(
  body: ChatStreamRequest,           // { client_request_id, conversation_id, message, history }
  h: StreamHandlers,
  signal: AbortSignal,
): Promise<StreamResult>

// ---------- domain/chatMachine.ts ----------
export type Phase = 'idle' | 'submitting' | 'streaming' | 'terminal'
export type TerminalKind = 'succeeded' | 'cancelled' | 'failed' | 'unknown'
export interface ChatTurn { /* 见 §5.4 的状态形状 */ }
/** 纯函数：旧状态 + 事件 → 新状态 + 副作用指令列表（不发请求、不碰 DOM） */
export function reduce(turn: ChatTurn, e: SseEvent): { turn: ChatTurn; effects: Effect[] }
export function toTerminal(turn: ChatTurn, how: 'stream-ended' | 'aborted' | 'error'): TerminalState

// ---------- domain/dedupe.ts ----------
/** seq 严格递增 + 终态唯一。返回 { accepted, dropped }，dropped 用于埋点。 */
export function accept(seen: Set<number>, lastSeq: number, e: SseEvent): 'accept' | 'duplicate' | 'out-of-order'

// ---------- a11y/live.ts ----------
/** 流式文本进 live region 的节流批量提交；保证不抢焦点、不逐字朗读 */
export function createLiveBuffer(opts: { politeness: 'polite' | 'assertive'; flushMs: number }): {
  push(text: string): void
  flush(): void
  clear(): void
}
```

### 2.4 命名与文件约定

| 对象 | 约定 | 例 |
| --- | --- | --- |
| 组件文件 | `PascalCase.vue`，与设计系统的组件族同名 | `Pill.vue`、`TableStack.vue` |
| 组件 class | **沿用 `rb.css` 的既有 class 名**，不另造 | `.pill--warn`、`.table--stack` |
| store | `use<Name>Store` | `useSessionStore` |
| 纯函数 | 动词开头，无副作用 | `reduce`、`validatePlanForm`、`mapError` |
| 端点封装 | 与 `API-REFERENCE.md` 的端点一一对应，函数名用其 `operationId` | `saveDraft`、`listPlans` |
| 常量 | 错误码、事件名、路由名集中在 `domain/constants.ts`，禁止散落字符串 | — |

## 3. 类型、错误与请求层

### 3.1 类型来源

| 类型 | 来源 | 手改 |
| --- | --- | --- |
| 端点请求/响应类型 | `openapi_v0.1.json` → `api/types.gen.ts` | **禁止**（生成物） |
| SSE 事件类型 | `sse_events_v0.1.schema.json` → `api/sse/types.gen.ts` | **禁止**（生成物） |
| 前端内部状态 | 手写于 `domain/` 与 `stores/` | 允许 |
| 样式 token | `design/system/tokens.ts` | **禁止**（生成物） |

字段名以 `docs/frontend-detail/API-REFERENCE.md` 为准。三个已确认的易错点，实现时按此写：

| 事项 | 正确写法 | 常见错误 |
| --- | --- | --- |
| 响应结构 | 一律 `{ request_id, data }` 信封，`request_id` 在 **body** | 以为只有响应头 |
| `/chat/stream` 幂等 | body 里的 `client_request_id` | 以为用 `Idempotency-Key` 头 |
| 并发版本 | 草稿 `expected_draft_version`；计划 `expected_version` | 两处写成同一个名字 |

### 3.2 请求层职责

`request<T>()` 的实现顺序固定如下，任一步失败都归一化为 `AppError`（§3.3）：

1. **拼 URL**：`VITE_API_BASE` + `path` + `query`。`path` 必须出现在 `API-REFERENCE.md` 中——实现期加一条单测，把代码里出现的所有 `path` 常量与 `API-REFERENCE.md` 的路径集合比对。
2. **注入认证头**：`Authorization: Bearer <token>`。令牌从 `auth` 参数传入，**请求层不 import store**（R2）。无令牌时对需要认证的端点直接短路为 `AUTH_REQUIRED`，不发请求。
3. **注入幂等头**：仅当 `idempotencyKey` 存在且端点属于 4 个允许端点时设置 `Idempotency-Key`；否则实现期报错（防止误用）。
4. **设超时**：`AbortController` + `timeoutMs`（默认 15s）。**流式请求不使用该超时**（§5.8 单独处理）。
5. **发请求并解包**：非 2xx 时读 body 的 `code`/`message` 构造 `AppError`；2xx 时返回 `data`，同时把 `request_id` 交给调用方用于埋点。
6. **记录**：只记 `method`、`path`、状态、`request_id`、耗时。**不记请求体与响应体正文**（NFR-PRIV-001，§13.4）。

**重试策略**：只对**幂等读**（`GET`）在网络错误或 5xx 时重试 1 次，退避 300ms。**所有写操作不自动重试**
——写入必须走显式用户动作或 `operation_id` 核实（SRS §8 的 429 行明确「不自动重放写操作」）。

### 3.3 错误归一化

```ts
export type ErrorKind =
  | 'network'        // fetch 抛错 / DNS / 连接中断
  | 'timeout'        // 本地超时
  | 'http'           // 收到非 2xx，带 code
  | 'protocol'       // 2xx 但信封或字段不符合契约（如缺 request_id）
  | 'stream-protocol'// 流内协议违规：seq 回退、双终态、事件字段不合法
  | 'stream-unknown' // 流结束但无终态（HTTP 关闭 ≠ 终态）
  | 'aborted'        // 用户取消

export interface AppError {
  kind: ErrorKind
  code?: string          // 合法集合见 §3.4；'protocol'/'network' 等无 code
  httpStatus?: number
  message?: string       // 服务端 message，仅用于诊断，不直接展示给用户
  requestId?: string     // 有则必带，用于支持定位（NFR-OBS-001）
  retryable: boolean
  fieldErrors?: Array<{ field: string; code: string; message: string }>  // 仅 VALIDATION_FAILED
}
```

**展示文案一律不取 `AppError.message`**：`message` 是诊断信息（可能含内部细节），用户可见文案只能来自
`content-spec.md` 或 SRS §8 的原文（出处是 §4.8 与各屏「错误分支」表里的「用户可见文案（来源）」列；
§3.4 本表用 5 列形式，把该列并入了「客户端行为」与「前端落点」，见该节末的列映射说明）。
`INTERNAL_ERROR` 必须展示「安全文案 + `request_id`」（SRS §8 原文要求）。

### 3.4 错误码映射（权威表）

**码的允许集合**（`API-REFERENCE.md` §0 同）：`openapi` 的 `Error` 枚举（28 个）∪ `SRS §8`（1 个独有，
即 `FORBIDDEN`）= **29 个同步码**；另有 **6 个异步任务码**（`NO_TEXT_EXTRACTED`、`DOCUMENT_ENCRYPTED`、
`PARSE_FAILED`、`EMBEDDING_FAILED`、`CLEANUP_FAILED`、`SERVICE_RESTARTED`），它们出现在文档批次/文件状态里，
**不是 HTTP 错误**，也不代表批次查询接口本身失败（SRS §8 原文）。

> **上游不一致（登记，未抹平）**：`SRS §8` 有 `FORBIDDEN`(403)，但 `openapi` 的 `Error` 枚举没有。
> 前端按并集实现并保留该分支；需后端确认是 OpenAPI 漏写还是 SRS 多写。**在确认前不得删除该分支。**

下表第二至四列**逐字取自 SRS §8**；第五列是前端落点（本文新增，便于实现期直接跳转）。

| HTTP | code | 条件（SRS §8 原文） | 客户端行为（SRS §8 原文） | 前端落点 |
| --- | --- | --- | --- | --- |
| 401 | `AUTH_REQUIRED` / `SESSION_EXPIRED` | 无有效会话、过期或撤销 | 停止后续请求，重新登录 | 清空 `session` → 按 §4.3 的顺序清全部 store → `router.replace('/login')`；**不弹"是否重试"** |
| 403 | `FORBIDDEN` | 角色无权操作管理能力 | 返回可访问页面，不重试 | 不渲染 `requiresAdmin` 路由；已进入时回退到 `/assistant` 并给出无权限提示（§7.2） |
| 404 | `RESOURCE_NOT_FOUND` | 不存在或不属于当前用户 | 不显示目标是否真实存在 | 文案不得区分"不存在"与"无权限"；计划详情 404 → 回 `/me/plans`（§9.5） |
| 409 | `DUPLICATE_ACCOUNT` / `DUPLICATE_COURSE` / `DUPLICATE_SCHEDULE` | 唯一键冲突 | 修改输入 | 字段级错误落在对应字段（§11.3）；`DUPLICATE_SCHEDULE` 是**同日完全相同时间段**，不可保存 |
| 409 | `VERSION_CONFLICT` | 更新版本不匹配 | 重新加载，保留未提交编辑供核对 | 保留用户已填内容，拉取最新 `version` 并展示差异；**不得直接覆盖用户的编辑**（§11.5） |
| 409 | `SCHEDULE_OVERLAP` | 时间重叠未确认 | 展示冲突，管理员可说明后确认 | 打开重叠确认面板：冲突摘要 + 原因必填 ≤500 + 确认/取消（§11.4） |
| 409 | `CHAT_IN_PROGRESS` / `REQUEST_ALREADY_EXISTS` | 同会话运行或请求重复 | 查询原请求状态 | 用原 `request_id` 调 `GET /api/v1/chat/requests/{request_id}` 接管显示，**不新建轮次**（§5.9） |
| 409 | `IDEMPOTENCY_CONFLICT` / `SAVE_LIMIT_REACHED` | 同键异内容或同轮第二次创建 | 展示已有结果，不新建 | 展示已有结果（`plan_id` 若已知则给入口）；`SAVE_LIMIT_REACHED` 明确说明"本轮已创建过" |
| 409 | `DOCUMENT_BUSY` / `DUPLICATE_FILENAME` | 文档变更并行或同名待处理 | 等待，或明确按独立文档上传 | 批次面板给"等待后重试"与"按独立文档上传"两个动作（§9.8） |
| 410 | `DRAFT_EXPIRED` / `CITATION_UNAVAILABLE` | 临时内容或引用失效 | 重新生成或检索 | 草稿过期 → 转「未保存」并提示重新生成；引用失效 → 标记该引用不可用而非整轮失败（§9.4） |
| 413 | `UPLOAD_TOO_LARGE` | 单文件或整批超限 | 提示限额 | 提示规格上限；**不得**回显服务端具体阈值以外的内部信息 |
| 415 | `UNSUPPORTED_FILE_TYPE` | 类型不受支持 | 选择允许文件 | 提示允许类型清单；文件行状态转失败（§9.8 的 5 种状态之一） |
| 422 | `VALIDATION_FAILED` / `SAVE_NOT_AUTHORIZED` | 字段错误、日期错误、许可不成立 | 修正输入或展示未保存草稿 | `VALIDATION_FAILED` → 错误摘要 + 字段定位（§11.2）；`SAVE_NOT_AUTHORIZED` → 草稿保持「未保存」外观 |
| 429 | `CAPACITY_LIMITED` | 达到部署并发保护上限 | 告知稍后重试，不自动重放写操作 | 提示稍后重试；**禁止**自动排队与自动重放（NFR-PERF-004） |
| 503 | `MODEL_UNAVAILABLE` / `RETRIEVAL_UNAVAILABLE` / `MCP_UNAVAILABLE` / `STORAGE_UNAVAILABLE` | 依赖失败 | 提示具体能力暂不可用 | 按 §13.2 降级矩阵处理；**直接业务（课表、计划、管理）必须仍可用**（NFR-REL-001） |
| 504 | `EXECUTION_TIMEOUT` / `CALL_LIMIT_REACHED` | 时间或执行预算耗尽 | 核实写入结果后再决定后续操作 | 若本轮有写意图 → 落「待确认」并用 `operation_id` 核实（§11.6），**不得直接判失败** |
| 500 | `INTERNAL_ERROR` | 未预期系统错误 | 安全文案及 request_id，用于支持定位 | 展示安全文案 + `request_id` 字符串（可复制），供支持定位 |

**流内错误**（`error` 事件 / `tool_end.code`）与上表**同码同义**（SRS IF-010），但没有 HTTP 状态：
前端判断分支必须只看 `code`，**不得**假设某个状态码。其中 `AUTH_REQUIRED` / `SESSION_EXPIRED`
在流内被 schema 强制**不得**携带 `plan_id` / `operation_id`——前端不得指望这两个字段来补救。

**本表的列映射（与 CONTRACT §3.6 的 6 列形式的对应）**：`CONTRACT §3.6` 规定映射表为
`码 | HTTP | 触发场景 | 前端行为 | 用户可见文案（来源） | 是否可重试` 六列。本表用**五列**
（`HTTP | code | 条件 | 客户端行为 | 前端落点`），少的那一列来自**把末两列折进前两列**——
`码` 与 `HTTP` 仍各占一列（未合并），`触发场景`→`条件`、`前端行为`→`前端落点`；
折叠的理由是 SRS §8 原文本身就把「行为」与「文案要求」写在了一起。具体映射如下。

| CONTRACT §3.6 的列 | 本表落在哪 |
| --- | --- |
| `码` / `HTTP` | 「code」与「HTTP」仍各占一列（本表第 2、3 列），未合并 |
| `触发场景` | 「条件（SRS §8 原文）」 |
| `前端行为` | 「前端落点」 |
| `用户可见文案（来源）` | 并入「客户端行为（SRS §8 原文）」与「前端落点」；逐字文案的完整出处另有 §4.8 与各屏「错误分支」表 |
| `是否可重试` | 并入「前端落点」：**部分码行**显式写了重试/不重试，「重试」一词未逐行出现——凡未写的，按 SRS §8「客户端行为」列判定（该列不是"是否可重试"的同义表述） |

这是**声明的偏离**，不是漏列；若评审要求严格六列，按上表拆开即可，信息无损失。

### 3.5 请求层与埋点的接口

每个请求完成（成功或失败）都产出一条埋点记录，字段与 §13.3 的清单一致；`requestId` 是 `NFR-OBS-001`
要求的跨服务关联键。埋点**不含**请求体、响应体、正文、令牌、密码（NFR-PRIV-001）。
