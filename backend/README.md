# 校园课程智能助手 · 后端（Phase 1）

FastAPI + SQLAlchemy(async) + Alembic + MySQL 8.4。本阶段交付 P0 非 AI 业务闭环：
身份认证、学生账号、课程、课表、学习计划、草稿、保存（幂等/许可/槽位）、写入状态、
审计/Outbox 与开发种子；知识链路（Phase 2）与助手链路（Phase 3）的路由与 Interface 已冻结。

## 1. 环境

| 项 | 值 |
| --- | --- |
| Python | 3.12（仓库根 `.venv`，依赖已装齐） |
| 数据库 | MySQL 8.4 容器 `cca-mysql`，`127.0.0.1:33061`，root/`cca_dev_root` |
| 测试库 | `cca_test_core`（**禁止**连开发库 `cca` 跑测试） |
| 公共 API | 8100（`/api/v1`） |
| 内部 API | 8101（`/internal/v1`，Phase 3 实现，当前 501 桩） |

```powershell
# 在 backend/ 目录执行；<repo> 为仓库根
$py = "<repo>\.venv\Scripts\python.exe"
$env:DATABASE_URL = "mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_core?charset=utf8mb4"
```

配置项见 `.env.example`（复制为 `backend/.env`，`.env` 不入库）。关键键：
`DATABASE_URL`、`CCA_ENV`、`CCA_SCHOOL_TIMEZONE`、`CCA_SESSION_TTL_SECONDS`、
`CCA_DRAFT_TTL_SECONDS`、`CCA_PAGE_DEFAULT_SIZE`、`CCA_PAGE_MAX_SIZE`、
`CCA_SCHEDULE_MAX_DAYS`、上传限额、`CCA_CORS_ORIGINS`、`CCA_SERVICE_TOKEN`。

## 2. 迁移

DDL 权威：`docs/backend/cca_schema_v0.1.sql`（23 表）。Phase 1 一次性转为初始迁移，
Phase 2/3 **不新增/不修改**迁移。

```powershell
& $py -m alembic upgrade head     # 空库 → 23 表（含控制记录 corpus_control / ai_capacity_slots）
& $py -m alembic downgrade base   # 回空库（测试用）
```

## 3. 启动

```powershell
# 公共 API
& $py -m uvicorn app.entrypoints.public_api:app --port 8100

# 内部 API（只回环；Phase 3 实现业务）
& $py -m uvicorn app.entrypoints.internal_api:app --port 8101

# Worker（Phase 1 骨架：Outbox no-op 派发一轮后退出）
& $py -m app.entrypoints.worker

# MCP server（Phase 3 实现；当前空壳退出）
& $py -m app.entrypoints.mcp_server
```

- `GET /api/v1/health`：进程 + 数据库两级健康检查。
- `GET /api/v1/openapi.json`：**运行态 OpenAPI**（前端 `openapi-typescript` 与漂移门禁真源）。
- 成功信封 `{request_id,data}`；失败 `{request_id,error:{code,message,field_errors?,details?}}`。
- 未知路径/未知查询参数/额外字段一律拒绝；错误码见 `app/shared/errors.py`（SRS IF-010）。

## 4. 种子（仅开发/演示）

```powershell
& $py -m app.cli.seed --demo
```

可重复执行（按规范值/唯一键/操作键判重）。产出：`student_demo` / `admin_demo`（口令
`demo1234`，仅开发）、课程 `CS101` / `MA201`、今天/明天/下周一（Asia/Shanghai）三条课表、
一份示例计划。生产部署路径**不经过**该命令（首个管理员用受控部署流程，见 TBD-03）。

## 5. 测试（车道内定向）

```powershell
& $py -m pytest tests/ -q                 # Phase 1 全车道（47 用例）
& $py -m pytest tests/test_identity.py -q
& $py -m pytest tests/test_academics.py -q
& $py -m pytest tests/test_planning.py -q
& $py -m pytest tests/test_operations.py -q
& $py -m pytest tests/test_contract_core.py tests/test_contract_openapi_diff.py -q
```

测试使用真实 MySQL（aiomysql），`conftest.py` 在会话开始时 `alembic upgrade head`，
每个用例清表并恢复控制记录。库名由 `DATABASE_URL` 覆盖（P2/P3 用
`cca_test_knowledge` / `cca_test_assistant`），非 `_test_` 库直接拒绝启动。

复用夹具（冻结命名）：`client`（httpx ASGI）、`db`（async_sessionmaker）、
`seeded`（admin/student/course 已登录）、`make_draft`（造草稿）、`login`。

## 6. 目录

```
backend/
  app/
    main.py                     # app factory / 中间件 / 路由挂载
    config.py                   # pydantic-settings（启动校验）
    shared/                     # ids / clock / errors / context / security / payload / http / validation / api_models
    adapters/db/{engine,models,uow}.py
    modules/
      identity/{interface,service,router,schemas}.py
      academics/{service,router,schemas}.py
      planning/{service,router,schemas}.py
      operations/service.py     # 审计 / Outbox
      knowledge/{interface,router}.py   # ★ Phase 2 桩（501）
      assistant/{interface,router,internal_router}.py  # ★ Phase 3 桩（501）
    entrypoints/{public_api,internal_api,worker,mcp_server}.py
    cli/seed.py
  migrations/                   # Alembic（0001 初始迁移，23 表）
  tests/
  reports/PHASE-01-REPORT.md
```

## 7. 交接给 Phase 2 / Phase 3

1. **路由已挂载**：`knowledge/router.py`、`assistant/router.py`、`assistant/internal_router.py`
   已 include 到公共/内部入口；实现后替换 501 返回即可，**不要改** `entrypoints/public_api.py`。
2. **迁移冻结**：不要新增/修改 Alembic 迁移；需要表调整先找 Lead。
3. **共享能力直接复用**：错误信封、`ActorContext`、`Clock`、`IdGenerator`、UoW/锁助手、
   `api_models.Envelope`、测试夹具。
4. **依赖已锁定**：不新增第三方依赖；确需新增走 Lead。
5. 详细冻结签名/配置键/测试夹具说明见 `reports/PHASE-01-REPORT.md`。
