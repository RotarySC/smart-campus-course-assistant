# 校园课程智能助手（Smart Campus Course Assistant）

面向学生的课程与学习助手：查课表、读课程资料、与助手对话生成并保存学习计划。
本仓库为 P0 交付（`main` @ tag `v0.2.0-p0`）：Vue 3 前端 + FastAPI 后端 + MySQL 8.4，
助手链路走真实 SSE + MCP 私有工具服务。

## 快速开始

```powershell
# 仓库根执行；需要 Docker Desktop（MySQL 容器）、仓库内 .venv 已装依赖
.\scripts\start.ps1        # 起 MySQL + 迁移 + 种子 + 后端四服务 + 前端，健康检查后打印入口
.\scripts\status.ps1       # 巡检
.\scripts\stop.ps1         # 停止（-StopDocker 连库一起停）
```

打开 `http://localhost:5173/`，用 `student_demo / demo1234`（或 `admin_demo / demo1234`）登录
（**仅开发种子账号**）。

详细参数、手动步骤、排障：[`docs/STARTUP.md`](docs/STARTUP.md)。

## 目录

| 路径 | 内容 |
| --- | --- |
| `web/` | Vue 3 + TS + Pinia + vue-router 4 + Vite 6 前端；默认走真实后端，mock 为显式 opt-in 夹具 |
| `backend/` | FastAPI + SQLAlchemy(async) + Alembic + MySQL；身份/课程/课表/计划/保存、资料知识链路、SSE 助手 + MCP |
| `scripts/` | 一键启动/停止/巡检（PowerShell，另有 `.cmd` 双击入口） |
| `design/` | 设计系统与原型（token、组件、评审记录） |

## 服务端口

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| 前端 dev | 5173 | `http://localhost:5173/`（只绑 localhost/`::1`） |
| 公共 API | 8100 | `/api/v1`，只回环；健康检查 `/api/v1/health` |
| 内部 API | 8101 | `/internal/v1`，只回环 |
| MCP server | 8102 | `/mcp`，私有 Streamable HTTP，三工具 |
| MySQL | 33061 | 容器 `cca-mysql`，演示库 `cca` |

## 验证与已知限制

- 发布验证结论：全量 184 passed / 0 skip，M1–M8 全 PASS（独立验证者出具，不复用实现者结论）。
- 未验证项：真实模型质量、生产向量库、OCR、多机/备份、性能 P95、Firefox/Safari、多机并发等。

## 开发约定

- 分支：`main` ← `dev` ← `phase/0x-*`；每车道一个 git worktree。
- 测试策略：日常只跑 T0 定向 / T1 车道门禁，**全量 T2 仅在收尾阶段**统一执行。
- 依赖安装走国内镜像（pip：阿里云；npm：`registry.npmmirror.com`）。
