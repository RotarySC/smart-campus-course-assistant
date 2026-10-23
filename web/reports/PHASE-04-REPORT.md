# PHASE-04 · 前端真实联调报告（CCA-PHASE-04）

| 项 | 值 |
| --- | --- |
| 任务 | task-2（Phase 4 · 并行车道 F），owner `frontend-integration` |
| 分支 / 工作树 | `phase/04-frontend-integration` / `.worktrees/p04-web` |
| 后端 | Phase 1 完成版 @ 8100（`uvicorn app.entrypoints.public_api:app`），开发库 `cca`，已 seed |
| 前端 | `VITE_USE_MOCK=false`，Vite proxy `/api` → `http://127.0.0.1:8100` |
| 环境 | Node 24.18.0 / pnpm 11.21.0 / Windows / Edge 155（CDP headless） |
| 证据文件 | [`e2e-real-phase04.txt`](e2e-real-phase04.txt) · [`cdp-smoke-phase04.txt`](cdp-smoke-phase04.txt) · [`contract-diff-phase04.txt`](contract-diff-phase04.txt) · 截图 `reports/artifacts/`（gitignore） |
| 报告时状态 | **F1–F5、F8、F9 完成**；F6/F7 的 E2E 骨架已就位，真实链路等 P2/P3 合并（当前 chat/文档端点 501） |

---

## 0. 一句话结论

前端已从 mock 切到**真实后端**并跑通 Phase 1 全部已实现链路：
`登录 → /me → 我的课表（31 天区间）→ 学习计划 CRUD/幂等/409 → 写操作核实 → 管理中心（课程/学生/课表 + 重叠确认）→ 登出/会话失效`。
**HTTP 级 E2E 20 PASS / 0 FAIL / 10 SKIP**（SKIP 全是 P2/P3 的 501 桩），
**浏览器逐屏 39/39 PASS**，**契约门禁 FAIL=0**，前端车道门禁（build/typecheck/SFC/不变量/types/stylelint/流式冒烟）全绿。
F6/F7（真实 SSE、引用、草稿保存、文档批次）的断言与清理逻辑已写好，**对 501 明确 SKIP，不伪造 PASS**。

### B1–B8 验收对照

| # | 判据 | 状态 | 证据 |
| --- | --- | --- | --- |
| B1 | 类型生成 | ✅ | `types.gen.ts` 由 openapi-typescript 生成（设计包真源，2238 行）；`--check` exit 0；**反向注入字段名 → exit 1**；同源重复生成逐字节一致 |
| B2 | 真实传输 | ✅ | `VITE_USE_MOCK=false`；`/api/v1` 经 proxy → 8100（探测：后端未起时 proxy 返回 500，不是 SPA 回退）；401 统一失效（`client.ts` sink → `session.onAuthFailure` → 清理 → `router.replace('/login')`） |
| B3 | 核心链路 | ⚠ 部分 | 登录→课表→计划→管理中心 真实可操作（HTTP+浏览器证据）；**助手 SSE/引用/草稿待 P3** |
| B4 | 三态正确 | ✅ | S07「读取失败」与「当天无课」分离（浏览器断言不含「无法读取」）；S09 列表/空态分离；待确认 ≠ 失败（写操作状态核实路径已跑通） |
| B5 | 文档批次 | ⏸ 待 P2 | E2E 步骤已就绪（202→轮询→发布→文本预览→删除→引用失效路径），当前 501 → SKIP |
| B6 | 门禁 | ✅ | `pnpm check` exit 0（tokens/typecheck/SFC/不变量 10/10/types:check/24 项流式冒烟/stylelint 0 warning）+ `pnpm build` exit 0 |
| B7 | E2E | ✅ | `node scripts/e2e-real.mjs` 一条命令；失败定位到端点/request_id；`--via=proxy` 验证代理路径 |
| B8 | 无回退 | ✅ | mock 仍可用（显式 `VITE_USE_MOCK=true`，浏览器 21/21 PASS 曾验证）；设计系统 token 未改；无新路由/store 名；**新增 1 个非设计项**：Composer 缺陷修复（见 §5） |

---

## 1. 任务完成情况

| 任务 | 状态 | 交付 |
| --- | --- | --- |
| F1 工作树自检 | ✅ | build/typecheck/invariants 基线全绿；`pnpm-workspace.yaml` 加 `verifyDepsBeforeRun: false`（联接导致 pnpm 误判，不改依赖来源） |
| F2 类型生成 + 漂移门禁 | ✅ | `scripts/gen-types.mjs`（http/file 双真源、注解归一、剔除 internal 路径、`--check`）；`src/api/types.ts` 薄门面；3 处真实漂移修正 |
| F3 传输层切真 + 401 | ✅ | env/proxy 切 8100；mock 改显式 opt-in；401 统一失效（请求层 sink + session 导航注入）；浏览器冒烟脚本 |
| F4 身份/课表/计划 | ✅ | 登录、`/me`、课表区间、计划 CRUD/幂等/版本冲突/写操作核实；浏览器逐屏 |
| F5 管理中心 | ✅ | 课程/学生/课表 E2E（含重叠 409→确认 201、精确重复 409、删除 audit_id）；浏览器列表/表单 |
| F6 助手真实 SSE | ⏸ 骨架 | E2E 断言+草稿/取消步骤已写；等 P3 |
| F7 文档批次 | ⏸ 骨架 | E2E 上传/轮询/预览/删除步骤已写；等 P2 |
| F8 E2E + 浏览器冒烟 | ✅ | `e2e-real.mjs`、`cdp-smoke.mjs`（Edge CDP，零新增依赖） |
| F9 门禁 + 报告 | ✅ | 本报告 + 证据文件 |

---

## 2. 复现命令

```powershell
cd .worktrees/p04-web/web

# 前端门禁（离线可跑）
pnpm check                     # tokens / vue-tsc / SFC / invariants / types:check / 流式冒烟 / stylelint
pnpm build

# 契约（需后端 8100）
node scripts/contract-diff.mjs          # 设计包 vs 运行态：FAIL=0 / WARN=10
node scripts/gen-types.mjs --check      # 生成物漂移门禁
node scripts/gen-types.mjs --source=http --out=$env:TEMP/types.http.ts   # 双真源对比

# 真实链路 E2E（需后端 8100；开发种子 student_demo/admin_demo + demo1234）
node scripts/e2e-real.mjs               # 30 步：PASS 20 / FAIL 0 / SKIP 10
node scripts/e2e-real.mjs --via=proxy   # 经 Vite proxy（需 pnpm dev）

# 浏览器（需 pnpm dev 5173；Edge 由脚本自动探测）
$env:WEB_BASE='http://localhost:5173'
node scripts/cdp-smoke.mjs              # 9 项：守卫/登录页/刷新/控制台
node scripts/cdp-smoke.mjs --login      # +真实登录落地
node scripts/cdp-smoke.mjs --pages      # +逐屏走查（39/39）
```

---

## 3. 契约漂移清单与处置

### 3.1 已修复（F2 生成类型一上就抓到的真实漂移）

| # | 位置 | 期望（OpenAPI） | 实际（原实现） | 处置 |
| --- | --- | --- | --- | --- |
| D1 | `POST /admin/schedules` body.reason | `string`（minLength 1，**不可 null**） | `AdminScheduleView.payload()` 未确认重叠时发 `reason: null` | 前端改为**不发送**该字段（真实后端否则会 422） |
| D2 | `Task.state` | enum `pending/running/retry_wait/succeeded/failed` | mock 批次创建写 `'accepted'`（契约外值） | mock 改 `'pending'`（仅夹具） |
| D3 | `Task` 辅助函数 | 枚举收窄 | 参数 `state: string` 放宽 | 收窄为 `Task['state']` |

### 3.2 mock 夹具与契约的偏差（**仅开发夹具**，真实后端已实测符合契约）

| # | 端点 | 契约行为 | mock 行为 | 影响 |
| --- | --- | --- | --- | --- |
| D4 | `POST /auth/logout` | `200 {revoked:true}` | 返回 `{}` | mock 模式下 E2E 会 FAIL；真实后端 PASS |
| D5 | `DELETE /me/plans/{id}` | `200 PlanDelete{deleted,plan_id,version}` | 返回 `{}` | 同上 |
| D6 | `POST /me/plans` 同 key 重放 | `200 SaveReusedResult(status=existing)` | 再次 `201 created`（无幂等存储） | 同上 |

处置：**不改产品代码**；mock 仅作无后端时的 UI 夹具，验收与门禁以真实后端为准（PHASE-PLAN D5）。E2E 对 mock 的偏差如实失败，不做兼容。

### 3.3 运行态 OpenAPI 文档缺口（**WARN，非行为错**；已报 Lead 转 backend-core）

`node scripts/contract-diff.mjs`（设计包 vs 运行态 27 paths / 52 schemas）：
**FAIL=0（无真实漂移）**，WARN=10：

| 类别 | 明细 | 处置 |
| --- | --- | --- |
| `path` | 运行态多 `/api/v1/health`（运维端点） | 合理，非契约漂移 |
| `request-body` | `POST /admin/documents/{id}/rebuild`、`POST /chat/stream` 未声明请求体 | P2/P3 尚未实现（501），合并后再核 |
| `status-doc` | document-batches / rebuild / delete / cleanup-retry 未声明 `202` | P2；行为实测待实现 |
| `schema-doc` | 缺 24/56 schema：9 个 P2/P3（Citation/Task/Document/DocumentPage/Batch/Upload/DocumentText/Rebuild/DocumentMutation）、9 个 internal 工具模型（前端不消费）、6 个 P3/聚合（ChatInput/ChatState/Cancel/HistoryMessage/SaveResult/EmptyInput） | P2/P3 合并后应清零 |
| `enum-doc` | `ErrorDetails.state`、`SaveCreatedResult.status` 未声明 enum | 前端字面量收窄仍以设计包为准 |

**类型真源决策**：默认 **file（设计包）**；`--source=http|auto` 保留。切换条件 = 上述 `schema-doc`/`enum-doc` WARN 清零（P2/P3 合并后，运行态声明全部响应模型与枚举）。
为保证双真源可切换且 `--check` 稳定：生成前**剥离非结构性注解**（`description/summary/title/example/examples/externalDocs`、`x-*`），保留 `properties` 层的业务字段名（`Course.description`、`Plan.title` 必须保留——初版无脑删被 `vue-tsc` 抓到，已改为上下文感知）。实测同源重复生成逐字节一致（76882 B / 2246 行）。

### 3.4 联调中发现的行为事实（记录，不视为缺陷）

| # | 现象 | 判定 |
| --- | --- | --- |
| D7 | 对**已停用**课程/学生创建课表 → `404 RESOURCE_NOT_FOUND`（`request_id=req_LJjhxvMKIxFaEQqT1CdETA`） | **后端行为正确**（禁用目标不可选，content-spec:164）；是 E2E 脚本排序错误，已改为「先建表、末尾清理再停用」 |
| D8 | `POST /me/plans` 实测 201、同 key 重放 200 existing、陈旧 `expected_version` 409 `VERSION_CONFLICT`、删除后 GET 404 | 与设计契约一致（运行态 OpenAPI 文档未声明 201/202/409，但不影响行为） |

---

## 4. 真实联调证据（摘要，完整见证据文件）

### 4.1 HTTP 级（`e2e-real-phase04.txt`）

**30 步 = PASS 20 / FAIL 0 / SKIP 10**（SKIP：chat/引用/草稿/取消/文档 = P2/P3 的 501 或未产生草稿）。代表证据（均带 request_id）：

| 链路 | 结果 | request_id |
| --- | --- | --- |
| 登录 student_demo | 200 Bearer | `req_oxi9xGcEnelqY_nO9ilUEQ` |
| `/me` | Asia/Shanghai，capabilities=3 | `req_z3P9EihKwsHh7L_8tp_LoA` |
| 课表 31 天 | 3 条，区间回显一致 | `req_zTsGt1r-Uuh0_qS4so9n-g` |
| 课表默认（今天） | 区间=当日 | `req_7Xgz0-C0sdRmIGBKpWyEng` |
| 创建计划 | 201 created + operation_id | `req_6ZckSdlnJABPlzQ5SzYrJw` |
| **幂等重放** | 200 existing，operation_id 一致 | `req_mOnEkLPJCx48n0cL6nNtHw` |
| 更新 + **陈旧版本 409** | version 1→2；409 VERSION_CONFLICT | `req_0IgWtIw1z3vsICmc746TbQ` |
| 写操作核实 | succeeded/confirmed | `req_jxTrNWX6UbYIlnP4uOMHEQ` |
| 删除计划 + 404 复核 | deleted=true；GET 404 | `req_JyNvKxrNiHE59z1EnDKvUg` |
| 无效令牌 /me | 401 AUTH_REQUIRED | `req_Y53XBjivyVhL-eQzv8W5wQ` |
| 管理端课程 | 创建 201→改名 200→409 | `req_qePJI_29Kyg2TmkUjiyLVQ` |
| 管理端学生 | 创建 201→改名 200 | `req_OVT6RPKI6HqrVG28KMimTg` |
| 管理端课表 | 重叠 409→确认 201→精确重复 409 | `req_zXaGMnvjdtg9-gzeHc1-Dg` |
| 课表删除 | 200 + audit_id | （见证据文件） |
| 错误口令 401 / 登出后旧令牌 401 SESSION_EXPIRED | 符合契约 | `req_NEXSuW25stOugUJJqiV3UA` / `req_NyBKlJidOzGEiwGeCbJk4g` |

### 4.2 浏览器级（`cdp-smoke-phase04.txt`，Edge headless + CDP，零新增依赖）

**39/39 PASS**：
登录（真实输入）→ `/assistant`；S02 边界提示条逐字；G6 刷新不恢复；S07 课表 1 行真实数据且「读取失败」未与「无课」混同；S09 计划 1 行 + 新建表单展开/输入/取消；G8 退出登录回 `/login`；仅 admin 可见「管理中心」→ `/admin/courses`（含 CS101）+ 新建表单展开/取消；**控制台零 error、零未捕获异常**。

### 4.3 真实浏览器发现并修复的 P0 缺陷（阶段 B 静态门禁未抓到）

`AssistantView` 的 `Composer` 曾传 `:disabled="!canSubmit"` → **输入框在空白时被禁用，用户永远无法输入第一个字符**（自锁死）。静态检查（typecheck/SFC/invariants/stylelint）全绿也发现不了，只有真实浏览器交互暴露。
修复：只禁用「发送」按钮（content-spec S02 是「空白不可提交」，不是输入框禁用）；mock 模式 `--login --ask` 浏览器验证 21/21 PASS。

### 4.4 mock 模式仍可用（B8）

`$env:VITE_USE_MOCK='true'; pnpm dev -- --port 5174` → 浏览器真实登录→助手→SSE 文本流入 DOM（21/21 PASS，截图 `reports/artifacts/smoke-assistant-answer.png`）。

---

## 5. 设计/架构决策记录

| # | 决策 | 理由 |
| --- | --- | --- |
| J1 | mock 改为**显式 opt-in**（仅 `VITE_USE_MOCK==='true'`） | 生产构建不加载 `.env.development`；默认 mock 会在漏配 env 时把假数据当产品发布。Lead 已批准；`pnpm check` 的流式冒烟不依赖该默认值（直接 import mock 模块，24/24 仍绿） |
| J2 | 类型真源默认设计包，运行态作契约门禁 | 运行态缺 24 schema/枚举，直接作真源会让门面类型编译失败；契约先行 + contract-diff 独立门禁 |
| J3 | 生成器剥离非结构注解（上下文感知） | 让「结构一致 ⇒ 逐字节一致」成立，`--check` 在线/离线都稳定；`properties` 层业务字段名必须保留 |
| J4 | UI 写路径不做浏览器自动化 | 无头浏览器等列表重载的时序不稳，flaky 证据比不测更糟；写路径契约由 HTTP E2E 覆盖（201/200/409/幂等/404 全断言） |
| J5 | 401 统一失效用「请求层 sink + session 导航注入」 | 请求层不 import store（§2.2 R2）；session 不 import router（避免 store↔router 环）；`/auth/login` 的 401 明确排除（凭据错误 ≠ 会话过期） |
| J6 | 管理中心内部无 UI 导航（已知缺口） | 冻结路由只有 1 个顶栏「管理中心」入口 → `/admin/courses`；`/admin/{students,schedules,documents}` 仅能深链进入（令牌在内存，刷新即回登录）。属阶段 B 路由壳的设计遗留，**未自行新增导航/路由**；登记给 Phase 5 裁决 |

---

## 6. 未覆盖项与风险（如实登记）

1. **F6 真实 SSE 未联调**：P3 端点当前 501。E2E 已备好断言（事件序列/seq 单调/终态唯一/`HTTP 关闭≠终态`/取消/草稿/写入轮询），合并后只需重跑。
2. **F7 文档批次未联调**：P2 当前 501。E2E 已备好 202→3s 轮询→发布→文本预览→删除→清理重试路径。
3. **引用删除后失效（410）**：需 P2 文档删除 + P3 引用，端到端在 P2/P3 合并后补。
4. **管理中心内部导航缺口**（J6）：课程/学生/课表/文档四屏在 UI 上只有课程页可达。
5. **UI 写操作未做浏览器自动化**（J4）：创建/编辑/停用/删除的 UI 行为以 HTTP E2E 契约 + 表单展开/取消的手工断言覆盖。
6. **多浏览器/多分辨率矩阵**：继承 U1–U6 范围外；本报告只有 Edge headless 1366×850。
7. **样式/无障碍实测**：仅控制台与选择器级冒烟，未做 axe/键盘走查/横向溢出实测（阶段 B 未覆盖项延续）。
8. **`/health` 等运维端点**未纳入前端类型面（生成器剔除 health 以外不处理；前端不调用）。

---

## 7. 演示库残留与数据卫生（`cca`）

- **种子数据完好**：CS101 数据结构、MA201 高等数学、`student_demo` / `admin_demo`、3 条课表（2026-10-23 / 10-24 / 11-02）、示例计划「第一周学习计划」。
- **清理动作**：E2E 计划（HTTP 与 UI）创建后删除并 404 复核；E2E 课表创建后删除（回执含 audit_id）；草稿保存产生的计划当场删除。
- **已知残留**（契约无 DELETE 端点；已 `enabled=false`，Lead 决定 Phase 5 用受控 SQL 清理）：
  - 课程：`E2E-MVKYZY6J`、`E2E-MVKZ0JCR`、`E2EUI-*`（每次 E2E/早期 UI 走查各留 1 条，均 disabled）
  - 学生：`e2e_mvkyzy6j`、`e2e_mvkz0jcr`（disabled）
- E2E 每次运行仍会新增 1 条 disabled 课程 + 1 条 disabled 学生（用于验证创建/编辑/启停与重叠 409）；**不新增契约端点**。

---

## 8. 后续（Phase 5 输入）

1. P2/P3 合并后：重跑 `e2e-real.mjs`（预期 SKIP→PASS）、`cdp-smoke.mjs --full`（SSE 文本流入/引用展开）、`contract-diff.mjs`（schema-doc/enum-doc 清零后切 `--source=auto`）。
2. 全量矩阵（T2）一次：见 `docs/phases/PHASE-05-release-verification.md`。
3. 演示库残留清理（受控 SQL）。
4. 管理中心内部导航缺口的裁决（加页内导航需设计系统批准；否则登记为已知限制）。
5. 浏览器冒烟的样式/无障碍层可用 Playwright 补齐（本车道不新增依赖，交 Phase 5）。
