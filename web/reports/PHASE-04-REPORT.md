# PHASE-04 · 前端真实联调报告（CCA-PHASE-04）

| 项 | 值 |
| --- | --- |
| 任务 | task-2（Phase 4 · 并行车道 F），owner `frontend-integration` |
| 分支 / 工作树 | `phase/04-frontend-integration` / `.worktrees/p04-web` |
| 后端 | P1+P2+P3 合入 dev 后的 8100（27 paths / 67 schemas；8101 internal / 8102 MCP 由 Lead 托管） |
| 前端 | `VITE_USE_MOCK=false`，Vite proxy `/api` → `http://127.0.0.1:8100` |
| 环境 | Node 24.18.0 / pnpm 11.21.0 / Windows / Edge 155（CDP headless） |
| 证据文件 | [`e2e-real-phase04.txt`](e2e-real-phase04.txt) · [`e2e-docs-phase04.txt`](e2e-docs-phase04.txt) · [`cdp-smoke-phase04.txt`](cdp-smoke-phase04.txt) · [`contract-diff-phase04.txt`](contract-diff-phase04.txt) · 截图 `reports/artifacts/`（gitignore） |
| 状态 | **F1–F9 全部完成**（F6/F7 已完成真实链路联调） |

---

## 0. 一句话结论

前端已从 mock 切到**真实后端**并跑通完整链路：
`登录 → /me → 我的课表（31 天区间）→ 学习计划 CRUD/幂等/409 → 写操作核实 → 助手真实 SSE（课表工具/资料检索+真实引用/计划草稿）→ 引用展开 → 草稿保存（幂等+写入核实）→ 取消 → 管理中心（课程/学生/课表 + 重叠确认）→ 文档批次（上传 202→worker 发布→文本预览→删除→404 失效）→ 登出/会话失效`。

**最终证据**：
- HTTP 级 E2E：`e2e-real.mjs` **32 步全部 PASS（32/0/0）**；`e2e-docs.mjs` **6 步全部 PASS（6/0/0）**
- 浏览器级：守卫 9/9、登录 17/17、逐屏 39/39、`--full`（真实 SSE+引用展开）27/27
- 契约门禁：`contract-diff` **FAIL=0 / WARN=4**（WARN 经 Lead 裁决为命名/文档差异，见 §3.3）
- 前端门禁：`pnpm check` / `pnpm build` 全绿
- **真实联调抓到 2 个静态门禁抓不到的前端缺陷**（Composer 输入框自锁死、草稿保存幂等键），均已修复

### B1–B8 验收对照

| # | 判据 | 状态 | 证据 |
| --- | --- | --- | --- |
| B1 | 类型生成 | ✅ | `types.gen.ts` 由 openapi-typescript 生成（设计包真源，2238 行）；`--check` exit 0；反向注入字段名 → exit 1；同源重复生成逐字节一致 |
| B2 | 真实传输 | ✅ | `VITE_USE_MOCK=false`；`/api/v1` 经 proxy → 8100（后端未起时 proxy 500 而非 SPA 回退）；401 统一失效（client sink → `session.onAuthFailure` → §6.14 清理 → `replace('/login')`；登录端点 401 明确排除） |
| B3 | 核心链路 | ✅ | 登录/课表/计划/助手 SSE/引用/草稿/管理中心 全部真实可操作（HTTP + 浏览器证据） |
| B4 | 三态正确 | ✅ | S07「读取失败」与「当天无课」分离；S09 列表/空态分离；「待确认 ≠ 失败」（写操作状态核实）；引用失效不缓存、不让整轮失败 |
| B5 | 文档批次 | ✅ | 上传 202 → worker 发布 → 文本预览（marker 逐字）→ 删除 202 → 清理至 deleted → 删除后 text 404（`e2e-docs` 6/6 PASS） |
| B6 | 门禁 | ✅ | `pnpm check` exit 0（tokens/typecheck/53 SFC/invariants 10/10/types:check/24 项流式冒烟/stylelint 0 warning）+ `pnpm build` exit 0 |
| B7 | E2E | ✅ | `node scripts/e2e-real.mjs` 一条命令可复现；失败定位到端点/request_id；`--via=proxy` 可用 |
| B8 | 无回退 | ✅ | mock 仍可用（显式 `VITE_USE_MOCK=true`，浏览器 21/21 曾验证）；设计系统 token 未改；无新路由/store 名 |

---

## 1. 任务完成情况

| 任务 | 状态 | 交付 |
| --- | --- | --- |
| F1 工作树自检 | ✅ | build/typecheck/invariants 基线全绿；`pnpm-workspace.yaml` 加 `verifyDepsBeforeRun: false`（联接导致 pnpm 误判，不改依赖来源） |
| F2 类型生成 + 漂移门禁 | ✅ | `gen-types.mjs`（双真源、注解归一、剔除 internal 路径、`--check`）；`types.ts` 薄门面；3 处真实漂移修正 |
| F3 传输层切真 + 401 | ✅ | env/proxy 切 8100；mock 改显式 opt-in；401 统一失效；浏览器冒烟脚本 |
| F4 身份/课表/计划 | ✅ | 登录、`/me`、课表区间、计划 CRUD/幂等/版本冲突/写操作核实；浏览器逐屏 |
| F5 管理中心 | ✅ | 课程/学生/课表 E2E（含重叠 409→确认 201、精确重复 409、删除 audit_id）；浏览器列表/表单 |
| F6 助手真实 SSE | ✅ | 三场景真实 SSE（get_my_schedule / search_course_docs+真实引用 / DRAFT_READY）+ 草稿读取编辑保存 + 取消 + 状态核实；浏览器 `--full` 真实流与引用展开 |
| F7 文档批次 | ✅ | `e2e-docs.mjs` 分段/一键：上传 202→发布→文本预览→删除→404；worker 常驻/一次性前提已写清 |
| F8 E2E + 浏览器冒烟 | ✅ | `e2e-real.mjs`、`e2e-docs.mjs`、`cdp-smoke.mjs`（Edge CDP，零新增依赖） |
| F9 门禁 + 报告 | ✅ | 本报告 + 证据文件 + 门禁全绿 |

---

## 2. 复现命令

```powershell
cd .worktrees/p04-web/web

# 前端门禁（离线可跑）
pnpm check                     # tokens / vue-tsc / SFC / invariants / types:check / 流式冒烟 / stylelint
pnpm build

# 契约（需后端 8100）
node scripts/contract-diff.mjs          # 设计包 vs 运行态：FAIL=0 / WARN=4（WARN 已裁决）
node scripts/gen-types.mjs --check      # 生成物漂移门禁
node scripts/gen-types.mjs --source=http --out=$env:TEMP/types.http.ts   # 双真源对比

# 真实链路 E2E（需后端 8100 + 种子账号 student_demo/admin_demo + demo1234）
node scripts/e2e-real.mjs               # 32 步：PASS 32 / FAIL 0 / SKIP 0
node scripts/e2e-real.mjs --via=proxy   # 经 Vite proxy（需 pnpm dev）
node scripts/e2e-docs.mjs               # F7 一键：上传→发布→预览→删除→404（需常驻 worker）
node scripts/e2e-docs.mjs --batch-id=<id> --marker=<m>   # 续跑既有批次

# 浏览器（需 pnpm dev 5173；Edge 自动探测）
$env:WEB_BASE='http://localhost:5173'
node scripts/cdp-smoke.mjs              # 9 项：守卫/登录页/刷新/控制台
node scripts/cdp-smoke.mjs --login      # +真实登录落地
node scripts/cdp-smoke.mjs --pages      # +逐屏走查（39/39）
node scripts/cdp-smoke.mjs --full       # +真实 SSE 文本流入 + 引用展开（27/27）
```

**运行前提（不是产品缺陷）**：演示库 `publish_frozen=FALSE`，文档发布/清理依赖 worker。
Lead 已启动**常驻 worker**（后台轮询）；若 worker 不在，`e2e-docs.mjs` 会返回 `NEED_WORKER`（exit 2）而不是 FAIL，`e2e-real.mjs` 对文档步骤 SKIP。

---

## 3. 契约漂移清单与处置

### 3.1 已修复（F2 类型生成抓到的真实漂移）

| # | 位置 | 期望（OpenAPI） | 实际（原实现） | 处置 |
| --- | --- | --- | --- | --- |
| D1 | `POST /admin/schedules` body.reason | `string`（minLength 1，**不可 null**） | `AdminScheduleView.payload()` 未确认重叠时发 `reason: null` | 前端改为**不发送**该字段 |
| D2 | `Task.state` | enum `pending/running/retry_wait/succeeded/failed` | mock 批次创建写 `'accepted'`（契约外值） | mock 改 `'pending'`（仅夹具） |
| D3 | `Task` 辅助函数 | 枚举收窄 | 参数 `state: string` 放宽 | 收窄为 `Task['state']` |

### 3.2 mock 夹具与契约的偏差（**仅开发夹具**，真实后端已实测符合契约）

| # | 端点 | 契约行为 | mock 行为 |
| --- | --- | --- | --- |
| D4 | `POST /auth/logout` | `200 {revoked:true}` | 返回 `{}` |
| D5 | `DELETE /me/plans/{id}` | `200 PlanDelete{deleted,plan_id,version}` | 返回 `{}` |
| D6 | `POST /me/plans` 同 key 重放 | `200 SaveReusedResult(status=existing)` | 再次 `201 created`（无幂等存储） |

处置：不改产品代码；mock 仅作无后端时的 UI 夹具，验收与门禁以真实后端为准（PHASE-PLAN D5）。

### 3.3 运行态 OpenAPI 的命名/文档差异（**FAIL=0 / WARN=4**，Lead 已裁决，不追清零）

| 类别 | 明细 | 裁决 |
| --- | --- | --- |
| `path` | 运行态多 `/api/v1/health` | 运维端点，合理；前端不消费 |
| `schema-doc` | 缺 15/56 命名 schema：9 个 internal 工具模型（不进公共 OpenAPI）、`SaveResult`（设计包聚合；运行态拆 `SaveCreatedResult/SaveReusedResult`，**语义等价**）、`Upload/EmptyInput/HistoryMessage/ChatState/Cancel`（运行态以 **inline** 请求/响应体表达） | 命名差异，接受 |
| `enum-doc` | `ErrorDetails.state`、`SaveCreatedResult.status` 运行态未声明 enum（字面量收窄） | 结构等价，接受 |

**类型真源**：默认 **file（设计包）**，`--source=http|auto` 保留作对比。Phase 5 M3 判定口径 = 「路径/operationId/请求字段/状态码/错误码零差异 + 上述命名差异已裁决」。
为保证双真源可切换且 `--check` 稳定：生成前**上下文感知地**剥离非结构性注解（`description/summary/title/example/examples/externalDocs`、`x-*`），`properties` 层的业务字段名（`Course.description`、`Plan.title`）一律保留。实测同源重复生成逐字节一致（76882 B / 2246 行）。

### 3.4 D9（真实联调发现的前端缺陷，非契约变更）

`POST /me/drafts/{draft_id}/save` 的 **`Idempotency-Key` 取值必须等于该草稿版本的 `Draft.operation_id`**（服务端预分配）。该约束只存在于后端实现（`planning.service.save_draft`），OpenAPI/API-REFERENCE 未表达。
- 实测缺陷：前端原用自造键 `save_<draftId>_<version>` → **422 `SAVE_NOT_AUTHORIZED`**（`request_id=req_mwGoBBPZz_VH8dpVHQDuCw`）
- 修复：`drafts.save()` 缺省使用 `draft.operation_id`（缺失即报错）；视图改 `drafts.save()`
- 修复后：save 201 `op=dop_sZPvaBqVCEwPlqSs3npwuA`（`req_YxBEiQUvhvC5G-c7F12Njw`），同 key 重放 200 existing
- 处置（Lead 裁决）：不改设计包 OpenAPI（避免双源漂移）；登记本报告 + Phase 5 发布说明；backend-core 在 Phase 1/3 报告实现备注补一句。

### 3.5 联调中发现的行为事实（记录，不视为缺陷）

| # | 现象 | 判定 |
| --- | --- | --- |
| D7 | 对**已停用**课程/学生创建课表 → `404 RESOURCE_NOT_FOUND`（`request_id=req_LJjhxvMKIxFaEQqT1CdETA`） | 后端行为正确（禁用目标不可选，content-spec:164）；是 E2E 脚本排序错误，已修正 |
| D8 | 文档删除 202 后需 worker 消费清理任务才到 `deleted` | 运行前提（演示库 `publish_frozen=FALSE`），不是产品缺陷；常驻 worker 下自动完成 |

---

## 4. 真实联调证据（摘要，完整见证据文件）

### 4.1 HTTP 级 `e2e-real.mjs`：**32 步 = PASS 32 / FAIL 0 / SKIP 0**

| 链路 | 结果 | request_id |
| --- | --- | --- |
| 登录 student_demo | 200 Bearer | `req_oxi9xGcEnelqY_nO9ilUEQ`（历次一致行为） |
| `/me` | Asia/Shanghai，capabilities=3 | `req_z3P9EihKwsHh7L_8tp_LoA` |
| 课表 31 天 | 3 条，区间回显一致 | `req_zTsGt1r-Uuh0_qS4so9n-g` |
| 创建计划 | 201 created + operation_id | `req_6ZckSdlnJABPlzQ5SzYrJw` |
| **幂等重放** | 200 existing，operation_id 一致 | `req_mOnEkLPJCx48n0cL6nNtHw` |
| 更新 + 陈旧版本 409 | version 1→2；409 VERSION_CONFLICT | `req_0IgWtIw1z3vsICmc746TbQ` |
| 写操作核实 | succeeded/confirmed | `req_jxTrNWX6UbYIlnP4uOMHEQ` |
| 删除计划 + 404 复核 | deleted=true；GET 404 | `req_JyNvKxrNiHE59z1EnDKvUg` |
| **SSE 课表工具** | `status(ACCEPTED/RUNNING)→tool_start(get_my_schedule)→tool_end→token→done`，正文 62 字 | `req_PzQ3oqplgDaSJlpJOYMPSg` |
| **SSE 资料检索 + 真实引用** | `tool_start(search_course_docs)`，`done.citations=[cit_S5vEcpiZVBSsb334TWPWYA]` | `req_sfyVYc2gUKrV7OmiNR5lQw` |
| **SSE 计划草稿** | `status(DRAFT_READY, dft_kJJoSsrG1_sCHmtDCwaM3g@1)` | `req_4dHKY5-gmL5Gly-Uo-tYug` |
| 引用展开 | 200，片段 88 字 | `req_gQ70raUa53X12eIZH9EIqQ` |
| 草稿读取/编辑 | `expected_draft_version` 1→2 | `req_hsWjz0zSxFUu108W7B87Bw` |
| 草稿保存（幂等键修复后） | 201 `op=dop_sZPvaBqVCEwPlqSs3npwuA`，计划当场删除 | `req_YxBEiQUvhvC5G-c7F12Njw` |
| 取消（已结束请求） | 200 `accepted=false` | `req_4VLk608litRL-ctBhzWxZg` |
| 管理端课程 | 创建 201→改名 200→陈旧 409 | `req_2J-N00vVLeUN-3ytdWZWgg` |
| 管理端学生 | 创建 201→改名 200 | `req_QlJR1Jo-IqCQycTH_UXddA` |
| 管理端课表 | 重叠 409→确认 201→精确重复 409→删除 audit_id | `req_3KolZj0E6XvCN9eP0KOKVQ` |
| 文档批次（常驻 worker） | 202→published→预览 36 字→删除→deleted | `req_rAknFRwY8REH5u68Be79OQ` / `req_veayRicyb2OjH4enuKNZAg` |
| 错误口令 401 / 登出后旧令牌 401 | AUTH_REQUIRED / SESSION_EXPIRED | `req_3rw6GudJdAnNPzhySF6cug` / `req_DoU6t26420FzWEZh9641AA` |

### 4.2 F7 专项 `e2e-docs.mjs`：**6 步 = PASS 6 / FAIL 0 / SKIP 0**（常驻 worker）

上传 202（`batch_id=bat_2DrseQmLZWjzY43XLDcjLg`，`req_xpt2gyv3GBl27oXfQwWb2g`）→ published → 文本预览 41 字含 marker（`req_ATkRKjigPLpNokcG1tLwFQ`）→ DELETE 202 → `deleted` → 删除后 `GET /text` **404 RESOURCE_NOT_FOUND**（`req_ZuQwCWLrDY_c0Z2cjFJbsw`）。

### 4.3 浏览器级（Edge headless + CDP，零新增依赖）

- `--full` **27/27 PASS**：真实 SSE 文本流入 DOM（102 字）→ 第二轮资料问句 → `.cite` 引用卡 1 张 → 点「展开片段」→ `.cite__body` 86 字，未出现 410 失效文案；控制台零 error、零未捕获异常。
- `--pages` **39/39 PASS**：S07 真实课表行且「读取失败」未与「无课」混同；S09 计划列表 + 新建表单展开/取消；G8 登出回 `/login`；仅 admin 可见「管理中心」→ `/admin/courses`（含 CS101）+ 新建表单展开/取消。
- 截图：`reports/artifacts/{smoke-login,smoke-assistant,smoke-assistant-answer,smoke-assistant-citations,pages-schedules,pages-plans,pages-admin-courses}.png`。

### 4.4 真实联调抓到、静态门禁抓不到的两个前端缺陷

| # | 缺陷 | 发现方式 | 修复 |
| --- | --- | --- | --- |
| **X1** | `AssistantView` 的 `Composer` 传 `:disabled="!canSubmit"` → **空白时输入框被禁用，用户永远无法输入第一个字符**（自锁死）。typecheck/SFC/invariants/stylelint 全绿也发现不了 | F3 真实浏览器交互 | 只禁用「发送」按钮（content-spec S02 是「空白不可提交」，不是输入框禁用） |
| **X2** | 草稿保存幂等键用前端自造 `save_<draftId>_<version>` → 真实后端 **422 SAVE_NOT_AUTHORIZED** | F6 真实 HTTP E2E | 用 `Draft.operation_id` 作幂等键（见 D9） |

### 4.5 mock 模式仍可用（B8）

`$env:VITE_USE_MOCK='true'; pnpm dev -- --port 5174` → 浏览器真实登录→助手→SSE 文本流入 DOM（21/21 PASS，截图 `reports/artifacts/smoke-assistant-answer.png`）。

---

## 5. 设计/架构决策记录

| # | 决策 | 理由 |
| --- | --- | --- |
| J1 | mock 改为**显式 opt-in**（仅 `VITE_USE_MOCK==='true'`） | 生产构建不加载 `.env.development`；默认 mock 会在漏配 env 时把假数据当产品发布（Lead 已批准；`pnpm check` 的流式冒烟不依赖该默认值，24/24 仍绿） |
| J2 | 类型真源默认设计包；运行态作契约门禁 | 运行态命名/文档差异经裁决接受；设计包确定性、可离线、含完整响应模型 |
| J3 | 生成器上下文感知剥离非结构注解 | 让「结构一致 ⇒ 逐字节一致」成立；`properties` 层业务字段必须保留（初版无脑删被 vue-tsc 抓到） |
| J4 | UI 写路径不做浏览器自动化 | 无头浏览器等列表重载时序不稳，flaky 证据比不测更糟；写路径契约由 HTTP E2E 覆盖（201/200/409/幂等/404 全断言） |
| J5 | 401 统一失效用「请求层 sink + session 导航注入」 | 请求层不 import store（§2.2 R2）；session 不 import router（避免环）；`/auth/login` 的 401 明确排除（凭据错误 ≠ 会话过期） |
| J6 | 管理中心内部无 UI 导航（已知缺口） | 冻结路由只有 1 个顶栏「管理中心」入口 → `/admin/courses`；其余 `/admin/*` 仅能深链（令牌在内存，刷新即回登录）。阶段 B 路由壳设计遗留，未自行新增导航/路由 |
| J7 | F7 采用分段 E2E（`e2e-docs.mjs`）+ worker 前提 | 演示库 `publish_frozen=FALSE`；`NEED_WORKER`(exit 2) 与 FAIL 严格区分，不把「等 worker」当失败 |

---

## 6. 未覆盖项与风险（如实登记）

1. **引用删除后 410 未端到端覆盖**：我们上传的 E2E 文档未被助手引用；被引用的样本文档属演示基线，不能删除。`CITATION_UNAVAILABLE` 分支由前端单测/状态机冒烟覆盖，端到端 410 留 Phase 5（可用专用测试库）。
2. **进行中取消未覆盖**：E2E 只对已结束请求调用 cancel（200 accepted=false）；in-flight cancel + 服务端终态一致性需慢流场景，留 Phase 5。
3. **管理中心内部导航缺口（J6）**：课程/学生/课表/文档四屏在 UI 上只有课程页可达。
4. **UI 写操作未做浏览器自动化（J4）**：创建/编辑/停用/删除以 HTTP E2E 契约 + 表单展开/取消断言覆盖。
5. **多浏览器/多分辨率矩阵**：继承 U1–U6 范围外；仅 Edge headless 1366×850。
6. **样式/无障碍实测**：仅控制台与选择器级冒烟，未做 axe/键盘走查/横向溢出实测（阶段 B 未覆盖项延续）。
7. **worker 前提**：文档发布/清理依赖 worker（常驻或 `--once`）；未驻留时相关步骤明确 `NEED_WORKER`/SKIP。

---

## 7. 演示库残留与数据卫生（`cca`）

- **种子数据完好**：CS101 数据结构、MA201 高等数学（enabled）、`student_demo`/`admin_demo`、3 条课表（2026-10-23 / 10-24 / 11-02）、示例计划「第一周学习计划」。
- **清理动作**：E2E 计划（HTTP/草稿保存产生）创建后删除并 404 复核；E2E 课表创建后删除（回执含 audit_id）；E2E 文档批次上传后删除（cleanup→deleted，text 404）。
- **已知残留**（契约无 DELETE 端点；已 `enabled=false`，Lead 决定 Phase 5 用受控 SQL 清理）：
  - 课程 11 条：`E2E-MVKYZY6J`、`E2E-MVKZ0JCR`、`E2EUI-MVKZ5KBR`、`E2EUI-MVKZ6NJC`、`E2EUI-MVKZ85WJ`、`E2E-MVKZJZWR`、`E2E-MVKZM7RB`、`E2E-MVL0JBDO`、`E2E-MVL0WG93`、`E2E-MVL10M0Z`、`E2E-MVL1CMGW`（均 disabled）
  - 学生 8 条：`e2e_mvkyzy6j`、`e2e_mvkz0jcr`、`e2e_mvkzjzwr`、`e2e_mvkzm7rb`、`e2e_mvl0jbdo`、`e2e_mvl0wg93`、`e2e_mvl10m0z`、`e2e_mvl1cmgw`（均 disabled）
- 说明：每次完整 `e2e-real` 会新增 1 条 disabled 课程 + 1 条 disabled 学生（用于验证创建/编辑/启停与重叠 409）；**不新增契约端点**，由 Phase 5 受控 SQL 清理。

---

## 8. 后续（Phase 5 输入）

1. Phase 5 全量矩阵（T2）一次：见 `docs/phases/PHASE-05-release-verification.md`；M3 契约判定按 §3.3 的裁决口径。
2. 演示库残留清理（受控 SQL）；种子数据不动。
3. 引用 410 端到端 + in-flight 取消（慢流/中断场景）。
4. 管理中心内部导航缺口裁决（加页内导航需设计系统批准；否则登记为已知限制）。
5. 浏览器冒烟的样式/无障碍层可用 Playwright 补齐（本车道不新增依赖，交 Phase 5）。
