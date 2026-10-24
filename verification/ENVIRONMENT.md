# Phase 5 独立验证环境（qa-verifier）

- 角色：独立验证者（`qa-verifier`），不写业务源码，只写 `verification/**`
- 被测对象：仓库 `dev` 分支，**最终冻结提交 `8b32cef690a443c054e7c26ebc3bc3988aab6de1`**（中间冻结：`ab36103` → `de9a34d` → `8b32cef`，逐次仅测试修正 / MCP 修复）；**发布 HEAD `9a787c82751eefcabd2e152527641d0d5c540695`** 仅追加 `backend/.env.example` 文档补全（QA-02），运行时代码 0 改动
- 本文件是**第三方可复现**的环境说明：库名、端口、目录、环境变量、命令、隔离边界
- 环境自检证据：首轮 [`evidence/preflight-phaseA-20261023.log`](evidence/preflight-phaseA-20261023.log)；冻结期 [`evidence/freeze-preflight-ab36103.log`](evidence/freeze-preflight-ab36103.log)；恢复后复核见 `RELEASE-VERIFICATION.md` §0/§5

> 结论先行：环境已就绪。2026-10-23 实测 `PREFLIGHT RESULT: PASS`；空库 `alembic upgrade head` → 24 张表（23 业务表 + `alembic_version`）；8200/8201/8202/5273 四端口自持；8200 `/health` 两级检查 `process=ok, database=ok`；`/api/v1/openapi.json` 27 paths。

---

## 1. 隔离边界（硬约束）

| 项 | Lead / 演示环境（**禁止触碰**） | 本验证环境（**独占**） |
| --- | --- | --- |
| 数据库 | `cca`（演示）、`cca_test_core/knowledge/assistant`、`cca_test_lead`（Lead 全量） | **`cca_test_release`**（Lead 已确认独占给我） |
| 公共 API | 8100 | **8200** |
| 内部 API | 8101 | **8201** |
| MCP | 8102 | **8202** |
| 前端 dev | 5173 | **5273** |
| 文件存储 | `backend/uploads` | **`verification/runtime/filestore`** |
| 向量存储 | `backend/var/vector` | **`verification/runtime/vector`** |
| 日志/PID | — | `verification/runtime/{logs,pids,launchers}` |

- 不清理演示库 `cca`，不重启/停止 Lead 的 8100–8102 与常驻 worker。
- Lead 已确认：Phase B 期间 `cca_test_release` 独占给我；Lead 自己的全量跑在 `cca_test_lead`（不复用我的库）。
- 前端不重建 `web/node_modules`（p04 联接约束），只在 `web/` 下跑脚本。
- 证据策略（Lead 裁决）：`verification/*.md` + `verification/scripts/` 入库；`verification/evidence/`、`runtime/`、`**/*.log`、`**/*.pid` 由根 `.gitignore` 排除。因此报告正文必须自带关键输出摘要，日志仅作本地复现凭证。
- `docs/**`、`backend/**`、`web/**`、`design/**` 一律只读；唯一例外是"反向注入"的**临时副本**（见 CHECKLIST §5，不落在源码目录）。

---

## 2. 固定环境变量（服务）

在 `backend/` 下启动服务时使用（`env.ps1` 会写入启动包装脚本，逐项落盘可复现）：

```powershell
$env:DATABASE_URL         = "mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_release?charset=utf8mb4"
$env:CCA_ENV              = "dev"                 # 服务用 pooled engine（贴近生产）；pytest 用 test（NullPool）
$env:CCA_SCHOOL_TIMEZONE  = "Asia/Shanghai"
$env:CCA_FILESTORE_ROOT   = "<repo>\verification\runtime\filestore"
$env:CCA_VECTOR_ROOT      = "<repo>\verification\runtime\vector"
$env:CCA_INTERNAL_API_URL = "http://127.0.0.1:8201"
$env:CCA_MCP_URL          = "http://127.0.0.1:8202/mcp"
$env:CCA_MCP_HOST         = "127.0.0.1"
$env:CCA_MCP_PORT         = "8202"
$env:CCA_MCP_PATH         = "/mcp"
$env:CCA_CORS_ORIGINS     = "http://localhost:5273,http://127.0.0.1:5273"
```

pytest 进程额外使用 `$env:CCA_ENV="test"`（否则每个用例的事件循环会复用池连接，出现 "Event loop is closed"）；库名必须含 `_test_`，`backend/tests/conftest.py` 会硬拒绝非测试库。

契约/E2E/浏览器脚本所需变量：

```powershell
$env:VITE_DEV_PROXY = "http://127.0.0.1:8200"          # pnpm dev 的 /api 代理目标
$env:E2E_BASE       = "http://127.0.0.1:8200/api/v1"   # e2e-real.mjs --base 等价
$env:BACKEND_BASE   = "http://127.0.0.1:8200/api/v1"   # cdp-smoke.mjs
$env:WEB_BASE       = "http://localhost:5273"          # cdp-smoke.mjs
```

---

## 3. 准备（一次）

```powershell
# 1) 等价的显式命令（env.ps1 内部一致）
docker exec cca-mysql mysql -uroot -pcca_dev_root -e "CREATE DATABASE IF NOT EXISTS cca_test_release CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;"
cd backend
$env:DATABASE_URL="mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_release?charset=utf8mb4"
..\.venv\Scripts\python.exe -m alembic upgrade head

# 2) 或使用封装脚本
pwsh -NoProfile -File verification/scripts/env.ps1 -Action prepare
pwsh -NoProfile -File verification/scripts/env.ps1 -Action env      # 打印环境块
pwsh -NoProfile -File verification/scripts/preflight.ps1            # 只读自检
```

实测（2026-10-23）：`alembic upgrade head` 从空库执行，`0001` 迁移通过；表数 **24**（23 业务表 + `alembic_version`）。业务表集合与 `docs/backend/cca_schema_v0.1.sql` 一致（Phase B M4 用独立 SQL 断言再次核对）。

---

## 4. 启动 / 停止服务

```powershell
pwsh -NoProfile -File verification/scripts/env.ps1 -Action start
pwsh -NoProfile -File verification/scripts/env.ps1 -Action status
pwsh -NoProfile -File verification/scripts/env.ps1 -Action stop
```

- `start` 生成 `verification/runtime/launchers/<svc>.cmd`（环境变量 + 命令 + 日志重定向全部落盘），用 `Start-Process cmd /c` 隐藏窗口启动；PID 记在 `runtime/pids/`。
- venv 的 `python.exe` 会再 exec 系统解释器，**实际监听进程是孙进程**，所以 `stop` 用进程树整棵杀（实测 4 个服务各 2–3 个子孙进程，停止后 8200/8201/8202 全部释放）。
- ⚠️ 在本 agent 的 `pwsh` 工具里，`start` 会因服务进程持有控制台句柄而**不立即返回**（脚本本身已完成）；因此验证会话中用后台作业执行 `start`，或用 `env.ps1 -Action stop` 结束。人类在普通终端运行不受影响。
- 前端：

```powershell
cd web
$env:VITE_DEV_PROXY="http://127.0.0.1:8200"
pnpm dev -- --port 5273 --strictPort
```

---

## 5. 环境自检结果（阶段 A，2026-10-23）

| 检查 | 结果 |
| --- | --- |
| 分支 / 提交 | `dev` / **`8b32cef690a443c054e7c26ebc3bc3988aab6de1`**（最终冻结；工作树除 `verification/` 外干净） |
| 工作树 | 除 `verification/`（我的写作用域，未纳入 Git）外干净 |
| Python | 3.12.10（`.venv`），pytest 8.3.4，alembic 1.14.0 |
| Node / pnpm | v24.18.0 / 11.21.0；`web/node_modules` 在位 |
| MySQL | 容器 `cca-mysql` running，8.4.13，`cca_test_release` 在位，24 表 |
| 端口 | 8200/8201/8202/5273 空闲；Lead 的 8100/8101/8102/5173 在听（未触碰） |
| 服务冒烟 | 8200 `/health` → `{"status":"ok","checks":{"process":"ok","database":"ok"}}`；公共 OpenAPI 27 paths；8201/8202 端口在听 |
| 测试规模（独立计数） | 22 个测试文件，`def test_` 167 处（参数化后实际收集数在 M1 记录） |

### 契约冻结锚点（docs 不入 Git，用 SHA-256 锚定真源）

Freeze 时与恢复后均重新计算并与下表比对（最终核对 4/4 一致；docs 现为 33 文件，含 7 份 phases）；任何变化都要求 Lead 说明，否则按"真源被改动"处理（M3 的对抗性检查 A9）。

| 文件 | 字节 | SHA-256 |
| --- | --- | --- |
| `docs/backend/openapi_v0.1.json` | 170103 | `fef94de03660e45877543e61cccfcb29a254220e00b3ecce19acd0c0a7b635a9` |
| `docs/backend/mcp_tools_v0.1.json` | 10729 | `94af215c731f951f3ca084699eb88d2fa963acef6d16f154e2d8e7c908904795` |
| `docs/backend/sse_events_v0.1.schema.json` | 13823 | `0122f8e449a99605b2a537a3d8db25a4a590166dd2d09de3ceb69fe6cba46aa1` |
| `docs/backend/cca_schema_v0.1.sql` | 24316 | `11a1bc5f5ef74f87881247b0199effa8031d3e59e7e071c17343f1b4e38620a1` |

---

## 6. 目录与已知风险

```
verification/
  ENVIRONMENT.md              本文件
  CHECKLIST-M1-M9.md          独立验证清单（命令 / 期望 / 证据格式 / 对抗性检查 / 反向注入）
  RELEASE-VERIFICATION.md     判定报告（骨架 → 阶段 B 填证据）
  scripts/{env.ps1,preflight.ps1}
  evidence/                   原始命令输出（每条入报告时引用文件名 + 摘要）
  runtime/                    filestore / vector / logs / pids / launchers（不入报告正文）
```

| 风险 | 处置 |
| --- | --- |
| `test_release_migration.py` 会 `downgrade base` 清库 | 库名硬绑 `cca_test_release`；全量 pytest 串行执行，不与其它进程并行；M4 前后各核一次表数 |
| pytest 与 Lead 的服务共用 MySQL 实例 | 不同库；`cca_test_release` 仅本验证者使用（FREEZE 消息中向 Lead 确认） |
| `docs/` 不在 Git，改真源不可见 | 用 §5 SHA-256 锚点比对 |
| 服务进程树（venv 二次 exec） | `env.ps1 stop` 整树杀；停止后核对端口释放 |
| Windows 传统 MAX_PATH | 知识链路 tmp 路径由用例自行用短路径（P05-PREP 已登记）；我的产物放 `verification/runtime`，不写长路径 |
| 浏览器 | 仅 Edge headless（CDP），不新增依赖；Firefox/Safari/真机/读屏属范围外（E8 登记） |
