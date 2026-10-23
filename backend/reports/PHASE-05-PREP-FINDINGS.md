# Phase 5 前置 · 跨切面安全隔离与迁移反注入 —— 发现记录

- **任务**：task-5（Owner: backend-core）
- **分支**：`phase/01-backend-core`
- **范围**：只新增测试文件，未修改业务源码
- **测试**：`tests/test_security_isolation.py`、`tests/test_release_migration.py`
- **运行**（真实 MySQL `cca_test_core`）：

```powershell
$env:DATABASE_URL="mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_core?charset=utf8mb4"
pytest tests/test_security_isolation.py tests/test_release_migration.py -q
```

**结果（修复前）**：12 passed / 3 xfailed / 1 failed（39.7s + 14.0s）——唯一失败为真实缺陷 F-01（严格失败，未弱化断言）。
**结果（修复后）**：`test_security_isolation.py` 13 passed / 3 xfailed；Lead 指定的六文件车道 T1 = **49 passed, 3 xfailed（118.53s）**；另跑契约两文件 11 passed（原 47 项 Phase 1 测试无回归）。

---

## F-01（真实缺陷，已修复）禁用提交后，在途敏感写入仍可落库

- **严重度**：中（跨切面一致性 / 账号禁用穿透）
- **违反**：后端详细设计 §5.1「所有敏感写入先锁定当前操作者 User；……验证双方角色与启用状态」、§14.2-4「禁用与保存并发，提交顺序可解释；已提交不撤回，**新工具不穿透**」
- **复现用例**：`tests/test_security_isolation.py::test_disable_committed_before_inflight_save_blocks_write`
- **最小复现步骤**（确定性编排，非概率竞态）：
  1. 学生登录，准备一份草稿（`make_draft`）。
  2. 测试连接执行 `SELECT ... FROM users WHERE id=学生 FOR UPDATE` 持学生行锁。
  3. 发出管理员禁用请求（`PATCH /admin/students/{id}`，enabled=false）→ 阻塞在用户行锁（排队第 1）。
  4. 发出学生保存请求（`POST /me/drafts/{id}/save`）→ 认证通过（此时 enabled=true），随后阻塞在用户行锁（排队第 2）。
  5. 释放行锁 → 禁用先获锁并提交；保存随后获锁。
- **实际结果**：禁用 200、`enabled=0` 之后，保存返回 **201 created** 并落库 1 份计划（`study_plans=1`）。
- **期望结果**：保存请求在锁内复核到账号已禁用 → 401/403/422，计划数 0。
- **根因**：写路径（`identity.create_student/patch_student`、`academics.*`、`planning.create_plan_manual/patch_plan/delete_plan/revise_draft/save_draft`）在事务中调用 `UoW.lock_user(s)`，但**只锁不校验** `enabled` / `auth_version` / `role`；认证依赖在请求进入时检查一次，无法覆盖“认证后、提交前被禁用”的窗口。
- **影响面**：管理员禁用学生时，该学生已认证但在途的写请求（计划创建/更新/删除、草稿保存）仍可能提交；新请求已正确 401（用例后半段验证）。管理员账号无禁用入口，故不涉及管理写路径。
- **建议 owner**：backend-core（Phase 1 代码）。
- **建议修复（最小改动）**：
  1. 在 `app/adapters/db/uow.py` 增加：
     ```python
     async def lock_and_validate_actor(self, actor) -> User:
         user = await self.lock_user(actor.user_id)
         if user is None or not user.enabled or int(user.auth_version) != int(actor.auth_version):
             raise ApiError("SESSION_EXPIRED")
         return user
     ```
  2. 在敏感写入事务开头用 `await tx.lock_and_validate_actor(actor)` 替换 `lock_user(actor.user_id)`（涉及 identity/academics/planning 的写服务；涉及目标学生时仍按 ID 升序 `lock_users`，可在锁后复核目标 enabled）。
  3. 修复后本用例应转绿；不需要改测试断言。

### 修复实施（Lead 裁决 A）与语义说明

- `app/adapters/db/uow.py`
  - 新增 `_validate_actor_row(actor, user)`：锁内复核 `enabled`、`auth_version`、`role`，不一致抛 `SESSION_EXPIRED`（401）。
  - 新增 `lock_and_validate_actor(actor)`：锁定操作者 User（§5.2 全局锁顺序第 1 位）后复核。
  - 新增 `lock_users_and_validate_actor(actor, extra_ids)`：按 ID 升序锁定操作者+目标用户后复核操作者（顺序不变）。
- 接入点（所有敏感写事务开头；认证依赖保持不变，这是“提交前二次校验”而非替代请求级认证）：

| 模块 | 端点 / 服务 | 校验方式 |
| --- | --- | --- |
| identity | `POST /auth/logout` | `lock_and_validate_actor` |
| identity | `POST /admin/students` | `lock_and_validate_actor` |
| identity | `PATCH /admin/students/{id}` | `lock_users_and_validate_actor(actor,[target])` |
| academics | `POST/PATCH /admin/courses` | `lock_and_validate_actor` |
| academics | `POST/PATCH/DELETE /admin/schedules` | `lock_users_and_validate_actor(actor,[student])` |
| planning | `POST /me/plans`（pending 意图 + 主事务） | `lock_and_validate_actor` |
| planning | `PATCH/DELETE /me/plans/{id}` | `lock_and_validate_actor` |
| planning | `PATCH /me/drafts/{id}` | `lock_and_validate_actor` |
| planning | `POST /me/drafts/{id}/save`（pending 意图 + 主事务） | `lock_and_validate_actor` |

- 错误码：统一 `SESSION_EXPIRED`（401），与既有认证矩阵一致（撤销/过期/禁用/auth_version 变化）。
- 为什么必须阻断“已认证但在途写入”：认证依赖只在请求进入时检查一次；管理员可在“已认证 → 尚未提交”的窗口禁用账号。若不锁内复核，§14.2-4 的“新工具不穿透”只对新请求成立，禁用对学生已发出的在途写入无效，违反 §5.1“所有敏感写入先锁操作者 User 并验证启用状态”。锁内复核把“是否仍然启用”的线性化点放到提交边界：禁用一旦提交，任何尚未提交的敏感写入都会失败；已提交的写入不撤回（与取消/保存的提交点语义一致）。
- 修复前后：修复前 F-01 返回 201 且落库 1 份计划（严格失败）；修复后返回 401 `SESSION_EXPIRED` 且 0 份计划，用例转绿，**断言未修改**。

---

## 已覆盖且通过（未发现缺陷）

| 设计条目 | 用例 | 结果 |
| --- | --- | --- |
| §14.2-1 同键同内容 10 并发 / 同键异内容 | `test_same_key_concurrent_creates_one_plan_and_one_audit` | 通过：1 次 201 + 9 次 200，plan/operation/audit/outbox 各 1；异内容 409 |
| §14.2-2 同轮换 operation_id | `test_same_draft_version_cannot_be_saved_with_another_key` | 通过：换键 422 SAVE_NOT_AUTHORIZED，原键 200 existing |
| §14.2-3 响应丢失/未知提交 | `test_lost_response_retry_returns_original_plan` | 通过：原键返回原 plan_id；未知操作 pending(recovering) |
| §14.2-4 取消与保存并发 | `test_cancel_vs_save_race` | **xfail(strict)**：chat 取消为 Phase 3 501 桩，Phase 5 由 assistant 车道覆盖 |
| §14.2-5 删除/旧版本/旧许可重放 | `test_deleted_plan_replay_does_not_resurrect_or_leak_body`、`test_old_draft_version_and_consumed_grant_replay` | 通过：不复活、正文清空、旧版本 422、原键 existing |
| §14.2-6 空档期并发重叠 | `test_empty_date_concurrent_overlap_only_acknowledged_commits` | 通过：结果 ⊆{201,409}；未确认者必为先提交者；后续未确认重叠必 409 |
| §14.2-10 伪造上下文/凭据/摘要 | `test_forged_context_fields_and_bearer_rejected` | 通过：user_id/role/session_id/save_grant/source → 422；伪造 Bearer → 401 |
| §14.2-10 伪造 system/tool 历史、audience | `test_forged_history_and_audience_rejected` | **xfail(strict)**：chat 端点 Phase 3 501 桩 |
| §14.2-10 资料内容注入 | `test_document_prompt_injection_cannot_authorize` | **xfail(strict)**：文档端点 Phase 2 501 桩 |
| 隔离矩阵：角色 | `test_student_forbidden_on_all_admin_endpoints` | 通过：9 个管理端点全部 403 FORBIDDEN |
| 隔离矩阵：跨用户 | `test_cross_user_resources_404_and_no_existence_leak` | 通过：plan/draft 读改删 404；write-operation 跨用户与不存在响应不可区分且无 plan_id |
| 会话状态 | `test_session_state_matrix` | 通过：无/伪造令牌 401 AUTH_REQUIRED；登出/过期/auth_version 变化/禁用 401 SESSION_EXPIRED |
| 迁移生命周期 | `test_migration_upgrade_downgrade_upgrade_idempotent` | 通过：downgrade→0 表；upgrade→23 表；二次 upgrade 幂等；表集合与 DDL 完全一致 |
| 数据库反注入 | `test_database_rejects_invalid_data` | 通过：12 类坏数据全部被 MySQL 拒绝（CHECK/唯一键/FK/长度） |

### 迁移断言耗时（本次实测）

| 断言 | 耗时 |
| --- | --- |
| `downgrade base` → 0 表 | 1.99s |
| `upgrade head`（空库）→ 23 表 | 3.41s |
| 二次 `upgrade head`（幂等） | 1.36s |
| 恢复 `head`（finally） | 1.41s |
| 12 类坏数据拒绝 | 8.7–18.6 ms/项 |

### 破坏性前提（迁移测试）

`test_release_migration.py` 会对 `DATABASE_URL` 指向的库执行 `alembic downgrade base`（清空全部业务表）再 upgrade。前提：

- 只在专用测试库 `cca_test_core` 运行（`conftest.py` 对非 `_test_` 库直接拒绝启动）；
- **不得与其他测试/进程并行**（pytest 默认串行；用例 `finally` 强制恢复 `head`，断言失败也会恢复）；
- 不要指向开发库 `cca` 或 P2/P3/P4 的测试库；Phase 5 跑全量时它与其它用例同属串行执行。

### 备注（非缺陷）

- 跨用户 `GET /me/write-operations/{id}` 返回 200 `pending(recovering)`（而非 404），与“完全不存在的操作”响应完全一致 → 不泄露存在性；符合 Phase 1 裁决（未知提交不解释为确定失败）。若 Phase 5 要求严格 404，需产品/设计裁决，不建议在测试里硬判。
- 空档期并发重叠存在两种合法提交顺序（未确认者先提交 → 两条都成功；确认者先提交 → 未确认者 409）。用例按**不变量**断言（未确认者必须是先提交者），不强行要求 1 条 201 + 1 条 409，避免把合法顺序判成失败。

---

## Phase 5 前置（二）· 契约与 xfail 收口（P2/P3 合并后）

- **前置**：`git merge dev`（dev tip `f5d5742`，含 Phase 2/3）。
- **契约收口**（`tests/test_contract_core.py`）：
  - 移除 knowledge 8 条 + `/chat/*` 3 条的 501 清单；
  - 新增 11 端点真实契约断言：路径/operationId、请求必填字段与属性集合、成功状态码集合（202/200）、标准错误响应集合（400–504 且统一 `Error` schema）；
  - 新增断言：公共 API 不再存在任何 501 响应；内部 4 端点在公共 OpenAPI 中不存在（公共入口访问返回 404 信封），只存在于内部应用 OpenAPI。
- **xfail 收口**（`tests/test_security_isolation.py`，3 个 `xfail(strict)` 全部转真断言）：
  1. 取消/保存并发：取消先提交 → `SAVE_NOT_AUTHORIZED` 且零新增；保存先提交 → 取消不撤回（计划仍在、操作仍 succeeded）。
  2. 伪造历史与 audience：chat `history` 的 system/tool 角色、历史项保留字段、顶层 user_id/session_id → 422；内部 API 无服务凭据/浏览器 Bearer → 401、错服务凭据 → 403、错 audience（aud=cca-mcp 当内部凭据、aud=cca-internal 再兑换）→ 403、伪造执行上下文 → 401/403。
  3. 资料注入与伪造引用：注入文本可作为检索内容展示，但伪造 `reference_id` 不进入权威引用清单、不可展开（410），注入内容不产生任何 `study_plans`/`save_grants`；真实引用可展开；未发布批次内容不可检索。
- **结果**：`pytest tests/test_contract_core.py tests/test_contract_openapi_diff.py tests/test_security_isolation.py -q` → **29 passed（0 xfailed / 0 failed，68.5s）**。
- **新发现**：无业务缺陷。
- **环境提示（非业务缺陷）**：
  - pytest basetemp 产物 `backend/pytest-of-Rotary/` 当前未被 `.gitignore` 覆盖（本任务只改测试文件，提交前已清理）；建议 Lead 在 `.gitignore` 增加该路径。
  - Windows 传统 MAX_PATH(260)：知识注入用例的 `attempts/<task>/<fence>/<version>/...` 键在 pytest `tmp_path` 下会超长；该用例改用系统临时短路径并在用例结束清理（`request.addfinalizer`）。

---

## Phase 5 前置（三）· 全端点契约一致性门禁（运行态 ↔ 设计包）

- **覆盖**：`tests/test_contract_openapi_diff.py` 扩展为 **38 个操作**（34 公共 + 4 内部）。
  公共取 `GET /api/v1/openapi.json`，内部取 `create_internal_app().openapi()`；设计包缺失时 skip。
  逐端点递归对比：路径/方法/operationId、请求体 media/属性/必填/类型/枚举、
  成功状态码集合、错误状态码集合、响应 data 字段/必填/类型/枚举（含数组元素与嵌套对象）。
- **等价规则（非白名单）**：`const x` ≡ 单值 `enum [x]`；`anyOf[T, null]` 解包为可空 T。
- **已裁决接受（精确条目，逐条必须命中）**：
  - 运行态多 `/api/v1/health`（运维端点，设计包未列）；
  - 5 个 PATCH 端点的对象级 `anyOf`（“至少一个可变字段”）约束无法用 Pydantic 表达（业务仍 422）；
  - `POST /api/v1/chat/stream` 200 为 SSE（`text/event-stream`），不适合 JSON Envelope 表达（事件由 SSE schema 约束）。
  - 内部端点不出现在公共 OpenAPI（由测试结构断言固定，不是白名单掩盖）。
- **真实差异（未裁决，门禁严格失败）**：共 **27 条**，按 owner 分组：

| Owner | 条数 | 差异 | 修复建议 |
| --- | --- | --- | --- |
| backend-core（Phase 1 响应模型） | 5 | `Reference.page_number` 设计为可选非 nullable，运行态 `int\|None` 为 nullable（Plan/Draft 的 5 个响应） | 改为 `page_number: int = Field(default=None)` |
| backend-knowledge（Phase 2 响应模型） | 11 | `Batch/Document/Task.error_code` 设计为可选非 nullable string，运行态 nullable（10 处）；`Citation.reference.page_number` 同上（1 处） | 改为 `error_code: str = Field(default=None)`、`page_number: int = Field(default=None)` |
| backend-assistant（Phase 3 请求/响应模型） | 11 | chat `conversation_id/history` 与内部课表 `from_date/to_date` 运行态允许显式 null（4 处）；chat state/cancel、内部 exchange/3 个工具共 7 个响应 schema 为空（未声明 response_model）；内部 save 缺 202 文档响应（1 处） | 可选字段去掉 `\| None`；补 `response_model=Envelope[设计包同名 Schema]`；save 补 202 |

- **门禁现状**：`test_full_openapi_structure_matches_design` 对上述 27 条**严格失败**并逐条打印 [owner]；
  白名单/已知差异条目若未被命中也会失败（防陈旧条目掩盖）。`test_design_package_shape_is_38_operations`
  与 `test_all_operations_document_errors_and_success` 通过。
- **结果**：`pytest tests/test_contract_openapi_diff.py -q` → **1 failed（27 条已知缺口）/ 2 passed**；
  `pytest tests/test_contract_core.py -q` → **11 passed**（回归无影响）。
- **后续**：owner 修复后删除 `KNOWN_DOC_GAPS` 对应条目并复跑；全绿即 Phase 5 M3 机器判据成立。


