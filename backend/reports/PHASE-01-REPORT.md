# Phase 1 交付报告 · 后端地基与业务闭环

- **编号**：CCA-PHASE-01-REPORT
- **分支 / 工作树**：`phase/01-backend-core` / `.worktrees/p01-backend`
- **Owner**：`backend-core`
- **日期**：2026-10-23
- **状态**：车道门全绿（47 用例）；23/23 Phase 1 端点按 OpenAPI 可用；四个入口可启动
- **契约权威**：`docs/backend/openapi_v0.1.json`（字段/状态码）、`docs/backend/cca_schema_v0.1.sql`（23 表）、SRS IF-010（错误码）

---

## 1. 结论摘要

| 出口判据 | 结果 | 证据 |
| --- | --- | --- |
| A1 23 表迁移 | ✅ | 空库 `upgrade head` → 23 表；`downgrade base` → 0；再 upgrade → 23（幂等） |
| A2 23 公共端点 | ✅ | 契约测试逐项通过；文档/对话端点 501 信封 |
| A3 权限隔离 | ✅ | 学生访问 admin → 403；跨用户计划/草稿/写入状态 → 404；禁用即撤销会话 |
| A4 并发正确性 | ✅ | 保存同键 10 并发 → 1 份计划；课表重叠并发 → 仅确认者成功（真 MySQL） |
| A5 错误语义 | ✅ | 401/403/404/409/410/422 与 SRS §8 一致；响应/日志无 SQL 原文 |
| A6 冻结交接 | ✅ | P2/P3 路由已挂载、迁移冻结、共享能力/夹具冻结；四入口可导入/启动 |
| A7 车道测试 | ✅ | `pytest tests/ -q` → **47 passed**（96s） |

---

## 2. 命令与原始结果摘要

```powershell
# cwd = backend/；<repo> = 仓库根
$py = "<repo>\.venv\Scripts\python.exe"
$env:DATABASE_URL = "mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_core?charset=utf8mb4"
```

| 命令 | 结果 |
| --- | --- |
| `& $py -m alembic upgrade head` | 23 表（`information_schema` 计数，排除 `alembic_version`） |
| `& $py -m alembic downgrade base` | 0 表；再 upgrade 回到 23 表（迁移幂等） |
| `& $py -m pytest tests/ -q` | **47 passed in 96.31s** |
| `& $py -m pytest tests/test_identity.py -q` | 14 passed |
| `& $py -m pytest tests/test_academics.py -q` | 8 passed |
| `& $py -m pytest tests/test_planning.py -q` | 8 passed |
| `& $py -m pytest tests/test_operations.py -q` | 6 passed |
| `& $py -m pytest tests/test_contract_core.py tests/test_contract_openapi_diff.py -q` | 9 + 2 passed（OpenAPI vs 设计包 **0 差异**） |
| `& $py -m app.cli.seed --demo`（连续两次） | 第一次 `created=true / schedules_created=3 / demo_plan_created=1`；第二次 `created=false / schedules_created=0 / demo_plan_created=0` |
| `uvicorn app.entrypoints.public_api:app --port 8110` + 冒烟脚本 | health 200；student_demo 登录 200；`/me` 200；`/me/schedules` 今日 1 条；创建计划 201；查询计划 200；写入状态 `succeeded`；同键重放 200 `existing`；admin 列表 200；`/api/v1/openapi.json` 200（27 paths） |
| `python -m app.entrypoints.worker` | 空转一轮 Outbox no-op 派发后退出 |
| `python -m app.entrypoints.mcp_server` | 打印未启用后退出（Phase 3 实现） |

并发用例（真 MySQL，无 mock）：

- `test_save_concurrent_same_key_creates_one_plan`：同草稿/同键/同内容 **10 次并发** → 1 次 201、9 次 200 existing，`plan_id` 全同，DB 计划数 = 1。
- `test_concurrent_overlap_only_acknowledged_succeeds`：预置重叠基准后并发提交“确认/未确认”两条重叠 → 未确认 409 `SCHEDULE_OVERLAP`，确认者 201；最终记录数 = 基准 + 确认者。

---

## 3. 23 端点覆盖表

| # | 方法 | 路径（`/api/v1`） | 成功码 | 关键错误码 | 行为要点 |
| --- | --- | --- | --- | --- | --- |
| 1 | POST | `/auth/login` | 200 | 401 AUTH_REQUIRED / 422 | 规范值查询；虚拟摘要等成本；2h 会话；令牌仅返回一次 |
| 2 | POST | `/auth/logout` | 200 | 401 AUTH_REQUIRED / SESSION_EXPIRED | 撤销当前会话；返回 `revoked` |
| 3 | GET | `/me` | 200 | 401 AUTH_REQUIRED / SESSION_EXPIRED | 当前用户/时区/能力/会话到期 |
| 4 | GET | `/admin/students` | 200 | 401 / 403 FORBIDDEN / 422 | 仅学生；分页/关键字/enabled 严格布尔 |
| 5 | POST | `/admin/students` | 201 | 401 / 403 / 409 DUPLICATE_ACCOUNT / 422 | 固定 `role=student`；口令策略（TBD-03 默认 8–1024） |
| 6 | PATCH | `/admin/students/{id}` | 200 | 401 / 403 / 404 / 409 VERSION_CONFLICT / 422 | 仅 display_name/enabled；禁用=递增 auth_version+撤销全部会话+撤销未消费许可 |
| 7 | GET | `/admin/courses` | 200 | 401 / 403 / 422 | 分页/关键字/enabled |
| 8 | POST | `/admin/courses` | 201 | 401 / 403 / 409 DUPLICATE_COURSE / 422 | code trim+casefold 唯一 |
| 9 | PATCH | `/admin/courses/{id}` | 200 | 401 / 403 / 404 / 409 VERSION_CONFLICT / 422 | code 不可改 |
| 10 | GET | `/me/schedules` | 200 | 401 / 422 | 默认今天；单端=单日；跨度 ≤31 天；按日期/开始时间/ID 升序 |
| 11 | GET | `/admin/schedules` | 200 | 401 / 403 / 404 / 422 | 必须显式 student_id；不共用可替换用户参数 |
| 12 | POST | `/admin/schedules` | 201 | 401 / 403 / 404 / 409 DUPLICATE_SCHEDULE / 409 SCHEDULE_OVERLAP / 422 | 锁学生+课程；精确重复始终拒绝；半开区间重叠；确认需非空 reason |
| 13 | PATCH | `/admin/schedules/{id}` | 200 | 401 / 403 / 404 / 409 VERSION_CONFLICT / SCHEDULE_OVERLAP / 422 | 归属学生不可改；仅排课字段变化才重查冲突 |
| 14 | DELETE | `/admin/schedules/{id}` | 200 | 401 / 403 / 404 / 409 VERSION_CONFLICT / 422 | `expected_version` 走查询参数；返回 audit_id |
| 15 | GET | `/me/plans` | 200 | 401 / 422 | 本人；标题子串；按 updated_at+id 倒序 |
| 16 | POST | `/me/plans` | 201 / 200 | 401 / 409 IDEMPOTENCY_CONFLICT / 422 | `Idempotency-Key`=operation_id；同键同摘要 200 existing |
| 17 | GET | `/me/plans/{id}` | 200 | 401 / 404 | 先限定归属；跨用户 404 不泄露 |
| 18 | PATCH | `/me/plans/{id}` | 200 | 401 / 404 / 409 VERSION_CONFLICT / 422 | PATCH 缺失 vs null；合并后校验日期 |
| 19 | DELETE | `/me/plans/{id}` | 200 | 401 / 404 / 409 VERSION_CONFLICT / 422 | 清空正文/依据快照；保留墓碑；操作置 deleted |
| 20 | GET | `/me/drafts/{draft_id}` | 200 | 401 / 404 / 410 DRAFT_EXPIRED | 本人且当前会话；不可变版本快照 |
| 21 | PATCH | `/me/drafts/{draft_id}` | 200 | 401 / 404 / 409 VERSION_CONFLICT / 410 / 422 | 新版本；撤销旧版未消费许可 |
| 22 | POST | `/me/drafts/{draft_id}/save` | 201 / 200 | 401 / 404 / 409 IDEMPOTENCY_CONFLICT / SAVE_LIMIT_REACHED / 410 / 422 SAVE_NOT_AUTHORIZED | 许可签发/校验、操作行锁、当前版校验、槽位唯一、计划插入、审计/Outbox 同事务 |
| 23 | GET | `/me/write-operations/{operation_id}` | 200 | 401 | pending/succeeded/failed/deleted + resolution；未知提交 pending(recovering) |

未实现（有意桩，501 统一信封）：文档 8 端点（Phase 2）、chat 3 端点（Phase 3）、内部 API 4 端点（Phase 3）。

---

## 4. 运行态 OpenAPI 与契约门禁

- `GET /api/v1/openapi.json` 返回运行态文档：**27 paths / 52 schemas**。
- 23 个 Phase 1 端点均声明 `response_model=Envelope[<设计包同名 Schema>]`，创建类 `status_code=201`，
  计划创建/草稿保存另声明 `200/201/202` 三种文档响应。
- 每个端点声明标准错误响应 `400/401/403/404/409/410/413/415/422/429/500/503/504`（统一 `Error` schema）。
- `test_contract_openapi_diff.py` 对 23 端点逐项对比设计包：路径/方法/operationId、请求字段名+必填+
  类型/枚举、成功状态码集合、错误状态码集合、响应 `data` 字段名+必填+类型/枚举 → **0 差异**。
  设计包缺失时该测试 `skip`（docs 不入 git）。
- 已知命名差异：运行态信封为泛型 `Envelope_Xxx_`（设计包为每个响应内联 `{request_id,data}`）；
  字段结构一致，已由 diff 门禁覆盖。

---

## 5. 冻结接口与交接（Phase 2 / Phase 3）

### 5.1 路由挂载（已 include，不要改公共入口）

| 文件 | 端点 | 当前行为 |
| --- | --- | --- |
| `modules/knowledge/router.py` | 文档批次/列表/预览/重建/删除/清理重试/引用 8 个 | 501 信封（Phase 2 实现） |
| `modules/assistant/router.py` | `/chat/stream`、`/chat/requests/{id}`、`/chat/requests/{id}/cancel` | 501 信封（Phase 3 实现） |
| `modules/assistant/internal_router.py` | `/internal/v1/delegations/exchange`、三工具 | 501 信封（Phase 3 实现） |

### 5.2 模块 Interface（签名冻结）

```python
# identity/interface.py
async def get_actor(request) -> ActorContext       # Bearer 认证（每次查 User+AuthSession 当前状态）
async def get_admin(actor) -> ActorContext         # 学生 403

# 服务层（模块内部，供 router/工具复用）
identity.service.login/logout/get_me/list_students/create_student/patch_student
academics.service.list_courses/create_course/patch_course/
                 list_my_schedules/list_admin_schedules/
                 create_schedule/patch_schedule/delete_schedule
planning.service.list_plans/get_plan/create_plan_manual/patch_plan/delete_plan/
                 get_draft/revise_draft/save_draft/get_write_operation
operations.service.append_audit/append_outbox/dispatch_outbox_once
```

`shared/` 能力：`ids`（前缀不透明 ID）、`clock`（可注入 Clock；UTC 存库/Asia-Shanghai 业务日期）、
`errors`（错误码→HTTP/安全文案/DB 唯一键映射）、`context`（ActorContext/ExecutionContext/SaveCommand）、
`security`（Argon2id、令牌摘要、虚拟校验）、`payload`（计划正文规范化摘要）、
`http`（信封/中间件/严格查询/分页）、`api_models`（响应模型 + `Envelope` + `ERROR_RESPONSES`）。

### 5.3 配置键（`.env.example`）

`DATABASE_URL`、`CCA_ENV`、`CCA_SCHOOL_TIMEZONE`、`CCA_SESSION_TTL_SECONDS`（7200）、
`CCA_DRAFT_TTL_SECONDS`（1800）、`CCA_PAGE_DEFAULT_SIZE`（20）、`CCA_PAGE_MAX_SIZE`（100）、
`CCA_SCHEDULE_MAX_DAYS`（31）、上传限额（Phase 2）、`CCA_CORS_ORIGINS`、
`CCA_SERVICE_TOKEN`/`CCA_DELEGATION_SIGNING_KEY`（Phase 3 占位）。

### 5.4 测试夹具（`tests/conftest.py`，命名冻结）

- `client`：httpx ASGI 客户端（真实应用 + 真实 MySQL）。
- `db`：`async_sessionmaker`，用于造数据/断言。
- `seeded`：admin/student/other + 课程 + 已登录头。
- `make_draft`：造 conversation/chat_request/plan_draft/version（供保存路径测试）。
- `login`：登录辅助函数。
- 库名由 `DATABASE_URL` 覆盖；非 `_test_` 库直接拒绝运行。

### 5.5 迁移

`migrations/versions/0001_initial_schema.py` 一次性建 23 表（DDL 逐字转写，含 6 条循环外键后置
ALTER 与控制记录）。**Phase 2/3 不新增/不修改迁移**；需要表调整先找 Lead。

---

## 6. 偏差与已知缺口登记（如实）

| # | 项 | 现状 / 处理 | 影响 |
| --- | --- | --- | --- |
| D1 | 本机无 `tzdata` 包 | `Asia/Shanghai` 用固定 +08:00 回退（中国 1991 年后无夏令时，业务等价）。**这是本机环境缺陷下的等价回退，不是"按时区库实现"**；配置其它时区且缺 tzdata 时启动校验失败（不静默降级） | 无业务影响；生产 Linux 可装 tzdata 后自然切换 |
| D2 | Argon2id 参数 / 口令策略 | 采用 argon2-cffi 默认参数；创建学生口令 8–1024，登录仅校验非空。属 **TBD-03**，开发默认值非试点冻结 | 试点前需冻结参数与策略 |
| D3 | 文档 / chat / 内部 API 端点 | 有意 501 桩（Phase 2/3），信封正确 | 不是缺陷；前端已确认 501 行为 |
| D4 | `202`（提交结果未知） | 文档已声明 `202 + WriteOperation`，但本实现不产生 COMMIT 未知状态（未实现连接异常检测/恢复器）。`GET /me/write-operations` 对未知操作返回 `pending(recovering)` | Phase 5 故障注入/恢复器补齐 |
| D5 | `direct_instruction` 保存来源 | 模型判定留 Phase 3；服务端许可校验基建（save_grants 绑定/摘要/过期/消费、操作槽）已就绪，Phase 3 写入时复用 | 本阶段公开入口仅 manual_form / draft_button |
| D6 | 登录失败状态码 | 账号不存在/口令错误/禁用统一 401 `AUTH_REQUIRED`「账号或密码不正确」（SRS FR-AUTH-001 裁决，SRS > 前端 open item T10） | 前端禁用文案需按统一文案实现 |
| D7 | 个人课表跨度口径 | 采用 `(to_date - from_date).days ≤ 31`（与前端校验 `dateDiff<=31` 一致；即最多 32 个日历日）。设计原文"≤31 自然日"存在歧义 | 如需改为"31 个日历日"仅需一行 |
| D8 | `/api/v1/health` | 设计包无此路径（运行态 27 paths vs 设计 26）；Phase 5 门禁排除 | 运行态健康检查需要 |
| D9 | 运行态信封 schema 名 | 泛型 `Envelope_Xxx_`，设计包为内联响应对象；字段结构一致（diff 门禁 0 差异） | 前端生成类型时以结构为准 |
| D10 | 管理课表 PATCH 重查重叠 | 仅 course/date/start/end 变化时重查；只改 location 不要求重新确认既有重叠 | 避免"改地点需重填原因"的可用性缺陷 |
| D11 | 审计保留期 / Outbox 真实派发 / 备份恢复 | 只落表与 no-op 骨架；保留期 180 天仅常量，不自动清理（TBD-02/06） | Phase 5 / 运维补齐 |
| D12 | `Idempotency-Key` 直接作为 `operation_id` | 客户端可见的逻辑操作标识；DB 唯一键保证一用户一操作一结果 | 与设计"页面与工具共用 operation_id"一致 |
| D13 | 草稿创建入口 | 无公共创建草稿端点（设计如此：草稿由助手生成）；本阶段由种子/测试夹具造数，Phase 3 写入 | 非缺陷 |
| D14 | 内部 API 服务认证 | Phase 1 仅桩，未加服务凭据校验；Phase 3 按 §9.2 双跳委派实现 | Phase 3 补齐 |
| D15 | 限流 / 429 | 仅错误码与映射就绪；chat 容量槽逻辑 Phase 3 实现 | 属 Phase 3 范围 |

**未完成项**：以上 D3–D5、D11、D14、D15 均为设计划归 Phase 2/3/5 或 TBD，不阻塞 Phase 1 出口。
无静默跳过项。

---

## 7. 如何启动 / 如何接 Phase 2、3（速查）

```powershell
# 迁移 + 启动 + 种子 + 测试（详见 README.md）
& $py -m alembic upgrade head
& $py -m uvicorn app.entrypoints.public_api:app --port 8100
& $py -m app.cli.seed --demo
& $py -m pytest tests/ -q
```

- P2：只改 `app/modules/knowledge/**` 与自己的 adapters/worker；替换 501；复用 `client/db/seeded` 夹具与 `shared/`。
- P3：只改 `app/modules/assistant/**`、自己的 adapters、`entrypoints/{internal_api,mcp_server}.py`；复用 UoW/锁序与 `SaveCommand`。
- 任何需要改 `shared/`、`config.py`、`public_api.py`、`migrations/`、`conftest.py` 的需求 → 走 Lead。
