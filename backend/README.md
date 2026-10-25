# 校园课程智能助手 · 后端

FastAPI + SQLAlchemy(async) + Alembic + MySQL 8.4 + MCP，提供公共 API、内部 API、MCP 服务与后台 Worker 四个入口。

## 能力

| 域 | 内容 |
| --- | --- |
| 身份 | 登录 / Bearer 会话 / 登出即失效；学生与管理员角色；服务身份与委派上下文 |
| 学业 | 课程、课表、学习计划、草稿、保存（幂等键 = 草稿 `operation_id`，写入许可 + 容量槽）、写入状态 |
| 资料 | 上传 202 → Worker（租约 / 心跳 / 重试）→ 解析 → 分块 → 向量 → 整批发布 → 检索 → 引用展开 / 410 → 重建 / 删除 |
| 助手 | `POST /chat/stream`：六类 SSE 事件、5 容量槽 / 6 决策 / 10 工具 / 60s 预算、MCP 三工具、双跳委派、对话内保存 |
| 运维 | 审计事件、Outbox、健康检查、运行态 OpenAPI |

## 1. 环境

| 项 | 值 |
| --- | --- |
| Python | 3.12（仓库根 `.venv`，依赖已装齐） |
| 数据库 | MySQL 8.4 容器 `cca-mysql`，`127.0.0.1:33061`，root / `cca_dev_root`，UTC，utf8mb4_0900_bin |
| 演示库 | `cca`（种子数据，可重建） |
| 测试库 | `cca_test_core` / `cca_test_knowledge` / `cca_test_assistant` / `cca_test_release` / `cca_test_lead`（**每车道一个，禁止共用，禁止连 `cca` 跑测试**） |
| 公共 API | 8100（`/api/v1`，只回环） |
| 内部 API | 8101（`/internal/v1`，只回环，不接受公网代理） |
| MCP server | 8102（`/mcp`，私有 Streamable HTTP） |
| Worker | 独立进程（轮询，无端口） |

连接串（把库名换成自己的车道库）：

```
mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca?charset=utf8mb4
```

## 2. 启动

在**仓库根**执行（不是 `backend/` 里）：

```powershell
.\scripts\start.ps1          # 容器 + 迁移 + 种子 + 四进程 + 前端，健康检查后打印入口
.\scripts\status.ps1         # 巡检：容器 / 库 / 迁移版本 / 端口 / health / Worker
.\scripts\stop.ps1           # 停应用（-StopDocker 连库一起停）
```

脚本幂等，六步：前置检查 → MySQL 容器 → `backend/.env` → `alembic upgrade head` → `seed --demo` →
四进程与前端。常用参数：`-NoFrontend`、`-SkipSeed`、`-ResetDb`、`-SkipDocker`、`-Mock`，
以及 `-PublicPort/-InternalPort/-McpPort/-WebPort` 换端口。

## 3. 手动启动

每一步都能单独跑，失败点即脚本的失败点。

```powershell
cd backend
$py = "..\.venv\Scripts\python.exe"
$env:DATABASE_URL = "mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca?charset=utf8mb4"

# 1) 迁移（空库 → 23 张业务表；二次执行幂等）
& $py -m alembic upgrade head
& $py -m alembic downgrade base        # 回空库（仅测试/重建）

# 2) 开发种子（student_demo / admin_demo，口令 demo1234；可重复执行）
& $py -m app.cli.seed --demo

# 3) 公共 API（8100）
& $py -m uvicorn app.entrypoints.public_api:app --host 127.0.0.1 --port 8100

# 4) 内部 API（8101，另开窗口）
& $py -m uvicorn app.entrypoints.internal_api:app --host 127.0.0.1 --port 8101

# 5) MCP server（8102，另开窗口；端口由 CCA_MCP_PORT 决定）
& $py -m app.entrypoints.mcp_server

# 6) Worker（另开窗口；--once 跑一轮排空后退出）
& $py -m app.entrypoints.worker
```

## 4. 配置

- `.env.example` 是**完整键集合**（37 个：`DATABASE_URL` + 36 个 `CCA_*`），复制为 `backend/.env`
  （不入库）；`start.ps1` 在缺失时自动由示例生成并把 `DATABASE_URL` 指向演示库 `cca`。
- **优先级**：进程环境变量 > `backend/.env` > 代码默认值（pydantic-settings）。
- 生产必须覆盖的键在 `.env.example` 内有标注（数据库口令、`CCA_SERVICE_TOKEN`、
  `CCA_DELEGATION_SIGNING_KEY` 等）。

## 5. 迁移

DDL 的唯一入库表达是 `migrations/versions/0001_initial_schema.py`（23 张业务表）；后续阶段**不新增、
不修改**迁移。注意 `tests/test_release_migration.py` 会清空 `DATABASE_URL` 指向的库，必须独占库串行执行。
契约真源在仓库根 `contracts/`（OpenAPI / MCP 工具 / SSE 事件 schema / DDL），是类型生成与契约门禁的输入。

## 6. 种子（仅开发/演示）

`python -m app.cli.seed --demo` 产出：`student_demo` / `admin_demo`（口令 `demo1234`，仅开发）、
课程 `CS101` / `MA201`、按 `Asia/Shanghai` 的今天/明天/下周一三条课表、一份示例计划，并把
`corpus_control.publish_frozen` 置 0（允许上传发布）。生产部署路径**不经过**该命令。

`python -m app.cli.sample --yes` 再补一批「打开就能演示 / 能测」的样例数据（同样只用于开发库，
可重复执行，按账号 / 课程码 / 操作键 / 固定 id 判重）：

| 内容 | 数量 |
| --- | --- |
| 学生账号 `student_s01`…`student_s08`（口令 `demo1234`） | 8 |
| 课程（CS101/MA201/CS201/CS301/CS302/MA202/PHY101/SE201） | 8 |
| 每名学生未来两周的课表 | 6 节/人 |
| 每名学生的学习计划（含 `write_operations` 记录） | 2 份/人 |
| 已发布课程资料（含 chunk、citation 与本地向量，可直接检索出引用） | 5 份 |

## 7. 健康与常用端点

| 端点 | 用途 |
| --- | --- |
| `GET /api/v1/health` | 进程 + 数据库两级健康检查（`{status, checks:{process,database}}`） |
| `GET /api/v1/openapi.json` | 运行态 OpenAPI（前端类型生成与契约漂移门禁的比对对象） |
| `POST /api/v1/auth/login` | 登录取 Bearer |
| `GET /api/v1/me/schedules?from_date=&to_date=` | 本人课表（跨度 ≤ 31 天） |
| `GET/POST /api/v1/me/plans`、`/me/drafts/{id}`、`/me/drafts/{id}/save` | 计划 / 草稿 / 保存（幂等键 = 草稿 `operation_id`） |
| `POST /api/v1/chat/stream` | 助手 SSE（需 `client_request_id`，`Accept: text/event-stream`） |
| `GET /api/v1/citations/{reference_id}` | 引用展开（文档删除后 410） |
| `POST /mcp`（8102） | MCP Streamable HTTP，三工具 `get_my_schedule` / `search_course_docs` / `save_study_plan` |

成功信封 `{request_id,data}`；失败 `{request_id,error:{code,message,field_errors?,details?}}`。
未知路径 / 未知查询参数 / 额外字段一律拒绝；错误码见 `app/shared/errors.py`。

## 8. 测试

| 层 | 命令 | 何时跑 |
| --- | --- | --- |
| T0 定向 | `& $py -m pytest tests/test_identity.py -q` 等单文件 | 改完一个模块 |
| T1 车道门禁 | `& $py -m pytest tests/ -q`（本车道库） | 提交前 |
| T2 全量 | 收尾阶段统一跑 | 仅在收尾 |

测试使用真实 MySQL（aiomysql）：`conftest.py` 会话开始 `alembic upgrade head`、用例间清表并恢复控制记录；
`DATABASE_URL` 必须指向 `cca_test_*`，否则直接拒绝启动。Windows 上全量需要短路径 `--basetemp`
（深路径会触发 MAX_PATH 并打断引用用例）。

## 9. 目录

```
backend/
  app/
    main.py                    # app factory / 中间件 / 公共与内部路由挂载
    config.py                  # pydantic-settings（启动校验）
    shared/                    # ids / clock / errors / context / security / payload / http / validation / api_models / timezones
    adapters/
      db/{engine,models,uow}.py
      mcp/{client,delegation}.py
      parser/ embedding/ vector/ model/ filestore/
    modules/
      identity academics planning operations     # 身份 / 学业 / 计划 / 审计
      knowledge                                   # 上传、发布、引用、Worker 任务
      assistant                                   # SSE runner、预算、草稿保存、内部工具、MCP 入口
    entrypoints/{public_api,internal_api,worker,mcp_server}.py
    cli/seed.py
  migrations/                  # Alembic（0001 初始迁移，23 表）
  tests/                       # 真实 MySQL 用例
```

## 10. 已知限制

真实大模型 / Embedding / 向量库、OCR 与扫描件、多机部署与备份、性能 P95、MCP jti 跨进程注册表等
均未验证。`adapters/model`、`adapters/embedding`、`adapters/vector` 是本地确定性实现，**不要**把
它们当作生产 AI 能力对外宣称。
