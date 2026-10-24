# Phase 5 · 发布独立验证报告（qa-verifier）

| 项 | 值 |
| --- | --- |
| 验证者 | `qa-verifier`（独立于全部 owner 车道） |
| 被验证对象 | 业务代码 `dev` @ **`8b32cef690a443c054e7c26ebc3bc3988aab6de1`**（最终 FREEZE）；发布 HEAD **`9a787c82751eefcabd2e152527641d0d5c540695`** = `merge --no-ff 5bffbe5`（仅 `backend/.env.example` 文档补全，运行时代码 0 改动） |
| 复核方式 | 冻结版本上**独立复跑**（不复用 owner/Lead 结论），真实 MySQL 8.4 / 真实 HTTP socket / 真实文件落盘 |
| 环境 | 独立库 `cca_test_release`（独占）；8200 公共 / 8201 内部 / 8202 MCP / 5273 前端；独立 filestore + vector 目录。详见 [`ENVIRONMENT.md`](ENVIRONMENT.md) |
| 验证清单 | [`CHECKLIST-M1-M9.md`](CHECKLIST-M1-M9.md) |
| 证据目录 | `verification/evidence/`（本地原始日志；按 Lead 裁决不入 Git，本报告正文自带摘要） |
| **最终判定** | **PASS（M1–M8 + 反向注入全通过；QA-02 已闭环；QA-03 为文档措辞差异，不阻塞）** |

---

## 0. 独立性声明

1. 全部 PASS 均为我在冻结提交上自己跑出的命令与输出；owner / Lead 的结论只作待证命题。
2. 我未修改任何业务源码（`backend/**`、`web/**`、`design/**`、`docs/**`）。反向注入只作用于 `verification/` 下副本、独立进程中的运行时补丁、或数据库数据面。
3. 未触碰 Lead 的 8100/8101/8102、5173/5174 与常驻 worker；未清理演示库 `cca`。
4. 影响面策略（Lead 已确认）：`de9a34d → 8b32cef` 的 diff 仅 5 个文件（`backend/app/entrypoints/mcp_server.py`、`backend/app/adapters/mcp/client.py`、2 个 assistant/mcp 测试、`backend/reports/PHASE-03-REPORT.md`；`web/**` 0 改动），因此 **M1 全量重跑 + M7 全量复跑 + M3 复核**；M2/M4/M5/M6 沿用 `de9a34d` 上证据并说明理由（这些层零改动，且 M1 套内含其契约/迁移/隔离/竞态用例）。
5. 最终发布 HEAD 复核：`git rev-parse HEAD` = `9a787c82751eefcabd2e152527641d0d5c540695`，父提交 = `8b32cef` + `5bffbe5`；`git diff --name-only 8b32cef HEAD` 仅 `backend/.env.example`（运行时代码/`web/**` 0 改动）。故 M1–M7 的结论对发布 HEAD 继续成立，只需复核 M8。
5. `docs/` 曾于 22:25 被第三方误删，恢复来源 Git `525be49`；恢复后 4 份契约 SHA-256 与阶段 A 锚点**逐一一致**（`fef94de0…` / `94af215c…` / `0122f8e4…` / `11a1bc5f…`），按"真源未篡改"判定，不算契约变更（记为验证期环境事故，见 §4 OBS-02）。

---

## 1. 判定总表

| # | 层 | 判据摘要 | 判定 | 关键证据 |
| --- | --- | --- | --- | --- |
| M1 | 后端全量 | 真实 MySQL 全绿；skip/xfail=0 | **PASS** | `184 passed in 389.49s`（0 failed / 0 skipped / 0 xfailed）`evidence/M1-pytest-full-8b32cef.log` |
| M2 | 前端全量 | 9 条门禁逐条 exit 0 + build | **PASS**（9/9） | `M2-gates.log`、`M3-contract.log`；dist 30 文件 |
| M3 | 契约 | FAIL=0；WARN 全在已裁决清单；后端 38 操作契约用例 0 failed | **PASS** | `M3-contract-recheck-8b32cef.log`（FAIL=0 / WARN=4）、`M3-contract-tests.log`（14 passed） |
| M4 | 数据层 | 空库 23 表 / downgrade / 二次 upgrade / 坏数据被拒 | **PASS** | `M4-migration.log`、`M4-tableset.log`、`M4-injection.log`（12/12） |
| M5 | 权限与隔离 | 17 个管理端点 403；跨用户 404；伪造凭据 401；MCP 委派矩阵 | **PASS**（42/42） | `M5-M6-probes.log`、`G2-gate-check.log`、`G5-delegation.log` |
| M6 | 并发与竞态 | §14.2 1–10 均有断言与证据 | **PASS**（10/10） | `M5-M6-probes.log`（M6-1/1b/6）、`M6-4-inflight-disable.log` + M1 套内用例 |
| M7 | 端到端 | HTTP + 文档 + 引用/410 + 浏览器 | **PASS** | `M7-e2e-real-8b32cef.log`（**32/32 PASS**）、`M7-e2e-docs-8b32cef.log`（6/6）、`M7-citation-410-8b32cef.log`（8/8）、`M7-cdp-full-8b32cef.log`（**49/49**） |
| M8 | 构建与产物 | dist / 四入口 / `.env.example` 完整 / 无秘密 | **PASS（5/5）** | `M8-env-example-recheck.log`：37 键 / 0 缺失 / 0 未知 / 无重复；dist 30 文件、四入口、无秘密均 PASS（QA-02 已闭环） |
| M9 | 文档与发布 | 台账/README/索引/tag/未验证项 | **PENDING（Lead 收尾）** | `docs/` 33 文件已恢复；tag 尚未打 |

### 出口判据（PHASE-05 §5）

| # | 判据 | 判定 | 说明 |
| --- | --- | --- | --- |
| E1 | M1/M2 一次通过（无临时跳过） | **PASS** | M1 184 passed / 0 skip / 0 xfail；M2 9/9 |
| E2 | M3 零未裁决差异 | **PASS** | FAIL=0；WARN=4 全部落在 Phase-04 §3.3 已裁决清单 |
| E3 | M5 全部拒绝且无信息泄漏 | **PASS** | 42/42；跨用户 write-operation 与不存在响应剔除客户端回显后逐字段一致 |
| E4 | M6 十项均有证据 | **PASS** | §2.6 映射表 |
| E5 | M7 HTTP + 浏览器通过 | **PASS** | 32/32、6/6、8/8、49/49；0 console error；真实引用 2 张可展开 |
| E6 | qa-verifier 报告 PASS | **PASS** | 本报告（QA-02 已闭环；QA-03 已登记不阻塞） |
| E7 | `main` 合并 + tag + 台账 | **PENDING** | Lead 执行 |
| E8 | 未验证项逐条列明 | **PASS** | §6 |

---

## 2. 逐条证据

### 2.1 M1 · 后端全量（真实 MySQL，184 cases）

```powershell
cd backend
$env:DATABASE_URL="mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_release?charset=utf8mb4"
$env:CCA_ENV="test"; $env:CCA_FILESTORE_ROOT=<repo>\verification\runtime\filestore; $env:CCA_VECTOR_ROOT=<repo>\verification\runtime\vector
..\.venv\Scripts\python.exe -m pytest tests -q -rs --durations=15 --basetemp=Y:\m1
```

- 结果：**`184 passed in 389.49s (0:06:29)`，exit 0；0 failed / 0 skipped / 0 xfailed**。
- 收集数 181→184：`8b32cef` 新增 MCP/assistant e2e 用例（+3）。
- 环境前提（已登记，非产品缺陷）：`--basetemp` 必须用**短路径**；本次用 `subst Y:` + `Y:\m1`。曾用 `Y:\pt-8b32cef` 跑出 18 failed，全部是 knowledge 落盘 `FileNotFoundError`，实测真实路径 **279 字符 > MAX_PATH(260)**；改成 251 字符的 `Y:\m1` 后 184 全绿（`evidence/M1-maxpath-explained.log`）。
- 另一环境前提：跑 pytest 前必须停掉连同一测试库的 worker（本轮已停）；conftest 每用例清表，跑完需重新 seed 才能做 E2E。
- 日志：`evidence/M1-pytest-full-8b32cef.log`（上一轮因 docs 误删作废的保留在 `M1-pytest-INVALID-docs-missing.log`）。
- 覆盖：`test_release_migration.py` 真实 `downgrade base → upgrade head`（5.92s）；`test_security_isolation.py` 16 用例；两个契约文件 14 用例；MCP e2e（含 `test_real_evidence_flows_into_sse_citations_and_expands`）全部通过 → 从套内交叉确认 QA-01 修复。

### 2.2 M2 · 前端门禁（逐条，基于 `de9a34d`；`8b32cef` 未改 `web/**`）

| 门禁 | 命令 | exit | 摘要 |
| --- | --- | --- | --- |
| tokens | `node scripts/sync-tokens.mjs --check` | 0 | tokens.css/ts 逐字节一致（md5 26eee4f0…/03607588…） |
| vue-tsc | `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p tsconfig.json` | 0 | — |
| tsc(node) | `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.node.json` | 0 | — |
| SFC | `node scripts/check-sfc.mjs` | 0 | 53 个 .vue 全通过 |
| invariants | `node scripts/invariants.mjs` | 0 | 10/10 |
| types:check | `node scripts/gen-types.mjs --check` | 0 | 与设计包逐字节一致（76882 B）；`8b32cef` 复核仍 0 |
| smoke-sse | `node --import ./scripts/ts-alias-hook.mjs scripts/smoke-sse.mjs` | 0 | 24/24（单元级，不作真实 SSE 证据） |
| stylelint | `node node_modules/stylelint/bin/stylelint.mjs "src/**/*.{css,vue}"` | 0 | 0 error 0 warning |
| build | `node node_modules/vite/bin/vite.js build` | 0 | `✓ built in 3.06s`；dist 30 文件（29 assets + index.html），无 sourcemap |

### 2.3 M3 · 契约（设计包 ↔ 运行态）

- 在 `8b32cef` 运行态（8200）复核：`contract-diff` → **FAIL=0，WARN=4**（`M3-contract-recheck-8b32cef.log`）：
  1. `path`：运行态多 `/api/v1/health`（运维端点，前端不消费）；
  2. `schema-doc`：缺 14/56 schema —— 我独立做集合差集核实 = 9 个 internal 工具模型 + `SaveResult` 聚合 + 4 个 inline 请求体（`Cancel/EmptyInput/HistoryMessage/Upload`）；
  3. `enum-doc`：`ErrorDetails.state` 未声明 enum；
  4. `enum-doc`：`SaveCreatedResult.status` 未声明 enum。
- 数量对账：设计 26 公共路径 / 34 操作 / 56 schema；运行态 27 / 35 / 71 → 差值恰为 `/health` 与 envelope 包装，**无未裁决新差异**。
- 后端契约用例（`de9a34d` 显式单跑，`8b32cef` 套内复跑通过）：`pytest tests/test_contract_openapi_diff.py tests/test_contract_core.py -q` → **14 passed in 36.19s**（38 操作覆盖；internal 4 端点不在公共 OpenAPI；公共入口访问返回 404）。
- 双真源：默认 `--check`（file 源）exit 0；`--source=http` 的逐字节差异全部来自已裁决的 `/health` 与 envelope 命名，按结构口径（由 contract-diff 保证）判无漂移。
- 真源哈希：4/4 与冻结锚点一致。

### 2.4 M4 · 数据层（空库往返 + 12 条反注入，基于 `de9a34d`；迁移/DDL 在 `8b32cef` 零改动）

| 断言 | 期望 | 实际 |
| --- | --- | --- |
| 迁移后 | 24 表（23 业务 + alembic_version） | 24 / business 23 |
| `downgrade base` | 业务表 0 | 1（仅 alembic_version）/ business 0 |
| `upgrade head` | 23 业务表 | 24 / business 23 |
| 二次 `upgrade head` | 幂等 | 无变更，`0001 (head)` |
| 表集合 vs DDL | 集合相同 | 独立解析 DDL 23 表 = 实测 23 表，完全一致 |
| 坏数据拒绝 | 全部被 MySQL 拒 | **12/12**：CHECK 3819 ×9、唯一键 1062 ×2、FK 1452 ×1；合法对照行成功 |
| 驱动脚本 | — | `verification/scripts/m4-injection.{ps1,sql}`（只允许 `cca_test_release`，脚本硬校验） |

### 2.5 M5 · 权限与隔离（42 条独立探针，真实 HTTP，`de9a34d`；`8b32cef` 未改 identity/academics/planning/knowledge）

| 组 | 探针 | 结果 |
| --- | --- | --- |
| 令牌 | 无令牌 / 伪造 Bearer / 篡改签名 / 错误口令 / 登出后旧令牌 | 401 AUTH_REQUIRED ×4；登出后 401 SESSION_EXPIRED |
| 管理端点 | **17 个 `/admin/**` 操作**全部用学生令牌 | 全部 **403 FORBIDDEN**，不返回数据 |
| 跨用户 | plan GET/PATCH/DELETE（学生乙） | 全部 **404 RESOURCE_NOT_FOUND** |
| 存在性泄漏 | 跨用户 write-operation vs 不存在 operation | 两者 200；剔除客户端回显 `operation_id` 后 data 逐字段相同，无 `plan_id`/正文 |
| 引用 | 伪造 reference_id | **410 CITATION_UNAVAILABLE**，无正文 |
| 草稿 | 不存在草稿错误体 | 两次 404，错误体一致 |
| 禁用穿透 | 禁用后写入 + 真实行锁编排的"禁用先提交、写入在途" | 均 401 SESSION_EXPIRED，`study_plans=0` |
| 内部 API | 无凭据 / 仅浏览器 Bearer / 错服务凭据 / 正确凭据无执行上下文 / 兑换无凭据 / 错 delegation | 401 / 401 / **403** / 401 / 401 / 401 |
| 公共入口 | 访问 `/internal/v1/**` | **404** |
| MCP | initialize；无委派调用工具 | 200 且服务名正确；`isError=true` |
| 页面权限 | 学生深链 `/admin/courses` | 服务端 403（另有 G2 系统级反证） |

### 2.6 M6 · 并发与竞态（§14.2 1–10）

| §14.2 | 证据 | 结果 |
| --- | --- | --- |
| 1 同键 10 并发 | 独立 HTTP 探针 | codes=[201×1, 200×9]；DB `study_plans=1 / write_operations=1 / audit_events=1 / outbox_events=1`；同键异内容 → 409 |
| 2 同轮换 operation_id | M1 套内草稿版本绑定用例 | PASS |
| 3 COMMIT 未知提交 | M1 套内 lost-response 用例 + M6-1 同键重放 200 existing | PASS |
| 4 禁用/取消 与保存并发 | 独立真实 HTTP + MySQL 行锁编排（`m6_inflight_disable.py`）：禁用 200 → 在途写入 401 → 0 行 | PASS（F-01 修复承重） |
| 5 删除/旧版本/旧许可重放 | M1 套内用例（不复活、正文清空、旧版本 422、原键 existing） | PASS |
| 6 空档期重叠并发 | 独立探针两管理员并发重叠 | codes=[409, 201]：恰一成功 |
| 7 半批失败/发布点 | M1 套内 knowledge 批次补偿/发布用例 | PASS（无物理崩溃） |
| 8 重建/删除/迟到写入 | M1 套内 worker lease + barrier 用例 | PASS（语义级） |
| 9 容量槽/租约 | M1 套内 runner/lease 用例 | PASS（进程内） |
| 10 伪造上下文/历史/audience | M1 套内 `test_forged_*` + G5（aud/过期/scope/会话/密钥/TTL）+ M6-1b | PASS |

### 2.7 M7 · 端到端（**最终 PASS**，QA-01 已闭环）

| 子项 | 结果 | 证据 |
| --- | --- | --- |
| HTTP `e2e-real.mjs`（直连 8200） | **32 步 = PASS 32 / FAIL 0 / SKIP 0** | `M7-e2e-real-8b32cef.log` |
| 资料检索 + 真实引用 | 步骤 14 PASS：1 条真实引用 `cit_DXnBz4KZC-QGmHkj6MizKQ`，`req_8Zp8A3fGkfaF4apMKs80pA` | 同上 |
| 引用展开 | 步骤 17 PASS：片段 496 字，`req_90AkbNRU5Jwu7qlxtDnBNw` | 同上 |
| 文档链路 `e2e-docs.mjs` | **6/6 PASS**：上传 202 → published → 预览 41 字含 marker → 删除 → text 404 | `M7-e2e-docs-8b32cef.log` |
| **引用删除后 410（Phase-04 §6 遗留）** | **8/8 PASS**：上传→发布→检索 3 citations→引用 200/487 字无存储键泄漏→`DELETE expected_version` 202→worker 清理→同一引用 **410 CITATION_UNAVAILABLE** | `M7-citation-410-8b32cef.log` |
| 浏览器 `--pages --full`（Edge headless，5273→8200） | **49/49 PASS**；真实引用卡 2 张、展开 239 字、410 未发生；控制台 0 error、0 未捕获异常 | `M7-cdp-full-8b32cef.log` |

- 数据前提（环境事实）：`e2e-real` 步骤 14 期望"库里已有可检索资料"。在**全新** `cca_test_release` 上首次跑得到 `citations=[]`（`result_status=empty`，非缺陷）；我按演示库口径先发布 1 份 baseline 文档后再跑，得到 32/32（`M7-baseline-doc.log`）。演示库 `cca` 的种子资料未被我触碰。
- 我在 `de9a34d` 上曾独立复现 QA-01（`tool_end success=false code=MCP_UNAVAILABLE`，`req_qV29FsMweoL9oH5PKxgWiA`）；`8b32cef` 复跑同场景已 `success=true` 并返回真实引用 → **QA-01 关闭**。

### 2.8 M8 · 构建与产物（**PASS 5/5**，QA-02 闭环后复核）

| 项 | 结果 |
| --- | --- |
| 前端产物 | `web/dist/index.html` + `assets/` 共 30 文件；无 sourcemap（设计红线） |
| 四入口 | 8200/8201/8202/worker 均在冻结代码上启动；`/health` → process=ok、database=ok；公共 27 paths；MCP `initialize` 200 |
| `.env.example` 完整性 | **PASS（QA-02 闭环）**：独立复算 **37 键 / 0 缺失 / 0 未知 / 无重复**（见下） |
| 无秘密入库 | PASS：`.env` 未入库；tracked 文件无真实密钥（示例值均为开发占位） |

`.env.example` 复核（`5bffbe5` 修复 + `9a787c8` 合并后，我独立复算，不接受 owner 自查）：

- 命令：扫描 `backend/app/**/*.py` 中 `os.environ.get(...)`／`os.environ[...]`／`os.getenv(...)`／`alias="..."` 的**全部环境变量字面量**，与 `backend/.env.example` 的 `KEY=VALUE` 键集合做双向差集（`evidence/M8-env-example-recheck.log`）。
- 结果：示例 **37 键**；代码读取集合与示例集合**双向 0 缺失**；无重复键；示例中每个键都能在 `backend/app` 中以字面量找到（排除拼写错误/过期键）；`DATABASE_URL` 前缀仍为 `mysql+aiomysql://`。
- 注意：`CCA_FILESTORE_ROOT=`、`CCA_VECTOR_ROOT=` 为**空值**——这是预期：代码用 `os.environ.get(...).strip()` 后空值回落到默认目录（`backend/uploads`、`backend/var/vector`），文档注释已说明。
- 数值合理性：23 个整数键全部可解析且落在合理区间（TTL ≥60、容量 1–50、deadline 1–600、分页 ≤100、课表跨度 ≤31 等），无 `0`/负值/异常放大。
- diff 范围：`git diff --name-only 8b32cef 9a787c8` → 仅 `backend/.env.example`；`backend/app/**`、`web/**` 改动 **0**；`git status` 除 `verification/` 外干净。

### 2.9 M9 · 文档与发布（PENDING，Lead 主责）

- `docs/` 33 文件已恢复（含 7 份 phases）；我核对 4 份契约哈希 4/4 一致。
- `docs/PHASE-STATUS.md` 在位；`README` 与 Phase 报告索引由 Lead/owner 收尾。
- tag `v0.2.0-p0` 尚未打；`dev → main` 由 Lead 执行。
- 我提供：本报告 + 未验证项清单，供发布说明使用。

---

## 3. 反向注入（证伪门禁，全部 PASS）

| # | 门禁 | 破坏方式（未改源码） | 破坏后 | 还原后 | 判定 |
| --- | --- | --- | --- | --- | --- |
| G1 | 契约字段 / 生成类型 | 复制 `types.gen.ts` → `plan_id` 改 `planId`（8 处），`gen-types --check --out=<副本>` | exit 1，指出第 470 行漂移 | 覆盖原件 → exit 0；仓库默认门禁 exit 0 | **PASS** |
| G2 | 服务端管理员鉴权 | 8299 独立进程加载真实应用，导入路由前把 `get_admin` 换成"不校验角色" | 学生 `GET /admin/students` → **200**（门禁 FAIL） | 健康 8200 → **403** | **PASS** |
| G3 | SSE 终态唯一 + seq 单调 | 录制真实 6 事件流 → 注入第二条 `done`；再把终态挪到中间 | 校验器 FAIL（终态应恰 1 个 / 终态不在末尾 / seq 不单调） | 原始序列 PASS | **PASS** |
| G4 | 数据库约束 | 12 条坏数据直接 INSERT（绕过应用） | MySQL 拒 12/12（3819/1062/1452） | 合法对照行成功 | **PASS** |
| G5 | MCP 双跳委派 | 自签 JWT：错 audience / 过期 / 缺 scope / 会话伪造 / 错密钥 / TTL 放大 | 全部 `isError=true` 且错误码正确；内部兑换 401 | 正常链路（M7 课表工具）通 | **PASS** |

---

## 4. 缺陷与观察

| ID | 严重度 | 判据 | 标题 | 状态 |
| --- | --- | --- | --- | --- |
| **QA-01** | 高（已闭环） | M7/E5 | 资料检索 `MCP_UNAVAILABLE` → `done.citations=[]`（根因：MCP `structuredContent` 含 null 触发客户端 outputSchema 校验失败） | **已修复**（task-9，`8b32cef`）；8b32cef 复跑 M7 全通过：e2e-real 32/32、引用展开 496 字、410 端到端 8/8、浏览器 49/49 |
| **QA-02** | 低（已闭环） | M8 | `backend/.env.example` 缺 20 个代码读取的配置键 | **已修复**（`5bffbe5`，经 `9a787c8` 合入）；我独立复算 37 键 / 0 缺失 / 0 未知 / 无重复，diff 仅该文件 → **关闭** |
| QA-03 | 信息/低 | M3 观察 | 内部工具 `from_date/to_date` 契约声明 `anyOf[date,null]`，运行态显式 `null` → 422（省略正常）；不影响前端（从不显式传 null），非安全问题 | **保留为文档措辞差异（Lead 裁定不阻塞）**，建议发布说明登记 |
| OBS-01 | 信息 | 流程 | `ab36103` 全量因过期用例 `test_worker_run_once_importable` 失败（F-02）；`de9a34d` 仅改该测试（1 file，+7/−2，非测试路径 0），我已独立核对 | 已修（测试-only） |
| OBS-02 | 信息 | 环境 | 验证期 `docs/` 被第三方 `mklink /J` + 递归删除误删；Git `525be49` 恢复，哈希 4/4 一致 | 已恢复（真源无损） |
| OBS-03 | 信息 | 环境 | 测试库残留（qa_ 前缀学生/计划、E2E 停用课程/学生、baseline 文档）仅存在于 `cca_test_release`；演示库 `cca` 未动 | 说明 |

---

## 5. 关键环境事实（复现必读）

1. **`--basetemp` 必须短路径**：`C:\cca-pt` 不可写（WinError 5）；`subst Y: <repo>\.worktrees\pytest-release` + `--basetemp=Y:\m1`（真实路径 251 字符）。长一档（`Y:\pt-8b32cef`，279 字符）会让 knowledge 落盘用例 `FileNotFoundError`。
2. **跑 pytest 前停掉连同一测试库的 worker**；conftest 每用例清表，跑完需 `app.cli.seed --demo` 才能做 E2E。
3. **E2E 资料检索需要已发布文档**：全新测试库先发布 1 份 baseline，否则步骤 14 得到合理的 `empty`（不是缺陷）。
4. 服务进程树：venv `python.exe` 会再 exec 系统解释器，监听进程是孙进程；`env.ps1 -Action stop` 整树杀并核对端口释放（8200–8202 均释放）。
5. 本 agent shell 中 `env.ps1 -Action start` 不立即返回（服务持有控制台句柄，脚本已完成）；用后台作业 + `status` 核对，不影响证据。

---

## 6. 未验证 / 范围外（E8，必须写入发布说明）

| # | 项 | 为什么未验证 | 是否影响判定 |
| --- | --- | --- | --- |
| 1 | 真实大模型 / Embedding 质量、≥50 条固定评测（TBD-04） | 无 API 凭据、TBD-04 未冻结；仅验证确定性 Provider 行为 | 不影响，需列明 |
| 2 | 生产向量库 / 写入屏障产品（TBD-07） | 未选型；仅本地 Adapter 语义 | 不影响 |
| 3 | OCR / 扫描件 / 复杂版式（TBD-05） | 范围外（pypdf 文本层） | 不影响 |
| 4 | 多机部署、备份/RPO/RTO、跨进程物理崩溃恢复（TBD-02/06） | 单机；§14.2-7/8/9 用 fence/租约语义验证 | 不影响，需列明 |
| 5 | Firefox/Safari、真机刘海屏、屏幕阅读器实听（U1–U6） | 仅 Edge headless | 不影响 |
| 6 | 性能压测（SRS 样本量 / 5 并发 P95） | 仅单机冒烟 | 不影响，不宣称达标 |
| 7 | 5 容量槽跨进程并发 | 需多 API 进程；仅进程内语义 | 不影响 |
| 8 | 资料内指令注入的独立 HTTP 端到端探针 | 由 owner 单测 + M1 覆盖（`test_document_injection_cannot_forge_references_or_authorize` 等）；我未单列 HTTP 注入 | 不影响（G5/M6-10 已覆盖伪造授权面） |
| 9 | 管理中心页内导航（P04 J6） | 设计系统未批准；Lead 裁决为已知限制 | 不影响 |
| 10 | in-flight 取消（慢流）独立复现 | 确定性 Provider 流式太快，取消时序不可稳定复现；由 M1 套内取消/保存竞态用例覆盖 | 不影响 |

---

## 7. 结论

**最终判定：PASS（M1–M8 与 G1–G5 全部通过；QA-02 已闭环；QA-03 保留为文档措辞差异，不阻塞）。**

- 冻结提交 `8b32cef` 上：M1（184 passed）、M2（9/9）、M3（FAIL=0、WARN=4 已裁决）、M4（23 表往返 + 12/12 反注入）、M5（42/42）、M6（10/10）、M7（32/32 + 6/6 + 8/8 + 49/49）、G1–G5 全部通过。
- QA-01（发布阻塞缺陷）已修复并复验闭环。
- 发布 HEAD `9a787c8` 已在 `8b32cef` 基础上完成 QA-02 修复（仅 `backend/.env.example`）；M8 复核 PASS，运行时代码与 M1–M7 结论不受影响。
- QA-03（内部工具显式 `null` 日期入参 → 422，契约 `anyOf[date,null]`）保留为**文档措辞差异**，不阻塞发布，建议在发布说明登记。
- M9（合并/tag/台账）由 Lead 执行，我把本报告与未验证项清单交给发布说明引用。

签署：`qa-verifier`，2026-10-24（发布 HEAD `9a787c8`，业务代码 = `8b32cef`）。
