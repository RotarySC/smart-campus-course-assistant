# 校园课程智能助手（Smart Campus Course Assistant）

面向学生的课程与学习助手：查课表、读课程资料、与助手对话生成并保存学习计划。

Vue 3 + TypeScript 前端，FastAPI + SQLAlchemy(async) + MySQL 8.4 后端。助手链路是**真实 SSE 流式响应**
+ **私有 MCP 服务**（三个工具：`get_my_schedule` / `search_course_docs` / `save_study_plan`）。

## 能力

| 能力 | 说明 |
| --- | --- |
| 身份与会话 | 登录、**自助注册**（`POST /api/v1/auth/register`，注册即登录、固定学生角色）、Bearer 会话、登出即失效；学生与管理员两种角色 |
| 课表 | 本人课程与课表查询，跨度 ≤ 31 天 |
| 学习计划 | 计划列表/详情、对话内生成草稿、幂等保存（写入许可 + 容量槽） |
| 资料问答 | 上传（拖拽或选择文件）→ 解析 → 分块 → 向量 → 整批发布 → 检索；回答带可展开引用，文档删除后引用返回 410；「全库尚无资料」与「本次没检索到」是两个不同状态；管理员预览抽取文本不可用时返回 state（`processing` / `parse_failed`）并说明原因，而不是一律 404 |
| 助手对话 | `POST /api/v1/chat/stream`：六类 SSE 事件、工具调用与回执、对话内保存 |
| 管理端 | 课程、学生、课表、资料批次与发布的增删改查；四个管理页经二级导航互相直达 |
| 运行统计 | `GET /api/v1/admin/stats/overview`（管理员）：按学校时区自然日窗口统计回答终止分类（succeeded／empty／failed／cancelled／timeout／limit_reached／auth_expired／pending）与计划、草稿、引用、工具、批次、幂等命中、写入核实计数；另给 worker 任务积压快照（pending/running/retry_wait/failed）与清理达标情况（succeeded/failed/超 5 分钟目标数）；只读聚合，不含正文 |

## 快速开始

```powershell
.\scripts\start.ps1     # MySQL 容器 + 迁移 + 种子 + 后端四进程 + 前端
.\scripts\status.ps1    # 巡检
.\scripts\stop.ps1      # 停止（-StopDocker 连库一起停）
```

打开 <http://localhost:5173/>，用 `student_demo / demo1234`（或 `admin_demo / demo1234`）登录 —— **仅开发种子账号**。没有账号可以在登录页的「注册」Tab 自助创建（固定学生角色，注册即自动登录）。

前置条件：Docker Desktop（MySQL 容器）、仓库根 `.venv`（Python 3.12，依赖已装）、Node 24 + pnpm 11。

想要更完整的演示数据（8 名学生、8 门课程、两周课表、学习计划、5 份可检索的资料）：

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.cli.sample --yes
```

常用参数：`-NoFrontend` 只起后端；`-ResetDb` 重建演示库；`-Mock` 前端走 mock 夹具；
`-PublicPort/-InternalPort/-McpPort/-WebPort` 换端口（多实例并存）。

运维命令（后端目录下）：

```powershell
..\.venv\Scripts\python.exe -m app.entrypoints.worker --once             # 排空任务队列一轮
..\.venv\Scripts\python.exe -m app.entrypoints.worker --sweep-orphans    # 孤立文件巡检（默认只删 1 小时前无引用的文件）
```

worker 常驻模式**启动即做一次**孤立文件巡检（`--no-startup-sweep` 可关）；巡检按内部引用清理 `documents/`、`attempts/`、`uploads/` 下没有任何行指向且超过 1 小时未修改的文件（在途写入不会被误删），每次写一条 `storage.orphan_sweep` 审计；文档/批次清理从入队到完成超过 5 分钟会在 `document.cleanup`（或 `document.batch.compensated`）审计里带 `slow_cleanup: true` 与耗时。

## 服务与端口

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| 前端 dev | 5173 | <http://localhost:5173/>（只绑 localhost/`::1`） |
| 公共 API | 8100 | `/api/v1`，只回环；健康检查 `/api/v1/health` |
| 内部 API | 8101 | `/internal/v1`，只回环 |
| MCP server | 8102 | `/mcp`，私有 Streamable HTTP，三工具 |
| MySQL | 33061 | 容器 `cca-mysql`，演示库 `cca` |

## 配置项

后端配置集中在 `backend/.env`（复制 `backend/.env.example` 后修改；进程环境变量优先于 `.env`），
完整键集、默认值与注释都在该文件内。

### 助手模型

默认不接大模型：`CCA_MODEL_PROVIDER=deterministic` 走关键词规则 Provider —— 离线、可复现，**不是**生产 AI 能力。

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `CCA_MODEL_PROVIDER` | `deterministic` | `deterministic` 或 `openai-compatible`（兼容 `chat/completions` 的任意厂商） |
| `CCA_MODEL_BASE_URL` | 空 | 供应商地址，只接受 `http(s)://` 开头 |
| `CCA_MODEL_API_KEY` | 空 | 供应商密钥，只放本机 `.env` 或部署环境变量 |
| `CCA_MODEL_NAME` | 空 | 模型名，原样透传（如 `deepseek-chat`） |
| `CCA_MODEL_TEMPERATURE` | `0.3` | 采样温度 0–2 |
| `CCA_MODEL_MAX_TOKENS` | `2048` | 单次回复上限 1–32768 |
| `CCA_MODEL_TIMEOUT_SECONDS` | `30` | 单次请求超时 1–600 |
| `CCA_MODEL_MAX_RETRIES` | `1` | 网络/5xx 重试 0–3 |

切 `openai-compatible` 时 `BASE_URL`、`API_KEY`、`NAME` 缺一项**服务启动即失败**；真实调用尚未实现，
每个助手请求以 `503 MODEL_UNAVAILABLE`（「模型服务暂不可用」）显式失败，不会静默回退到确定性 Provider。
`CCA_ASSISTANT_*` 那组预算键由进程环境变量读取，写进 `.env` 不生效。

## 目录

| 路径 | 内容 |
| --- | --- |
| `web/` | Vue 3 + TS + Pinia + vue-router 4 + Vite；默认连真实后端，mock 为显式 opt-in |
| `backend/` | FastAPI + SQLAlchemy(async) + Alembic + MySQL；身份/课程/课表/计划/资料/助手 + MCP |
| `scripts/` | 一键启动/停止/巡检（PowerShell，另有 `.cmd` 双击入口） |
| `contracts/` | 契约真源：OpenAPI、MCP 工具、SSE 事件 schema、DDL（类型生成与门禁的输入） |

## 验证状态

- 后端 **282 个用例**在真实 MySQL 上全绿（0 failed / 0 skipped / 0 xfailed；本次全量一次跑出 264 passed + 1 例在 fixture 建连时撞 Docker 端口映射瞬时断连 `2003`，单例重跑通过）。检索依赖故障（向量库损坏等）统一映射为 **503 `RETRIEVAL_UNAVAILABLE`**，不再漏成 500 `INTERNAL_ERROR`；知识链路自己给出的稳定错误码原样透传（`test_retrieval_fallback.py` 守护）。AI 容量槽选槽对 `SKIP LOCKED` 的瞬时假满做毫秒级有界重试：先在无锁查询里判断是否真满（真满立即 429、不排队），仍有空闲才重试最多 6 次（`test_assistant_api.py` 3 例守护）。资料链路的解析/向量参数摘要（分块 + Embedding Provider/维度）与向量空间都按版本行冻结：改 `CCA_CHUNK_SIZE`/`CCA_CHUNK_OVERLAP`/`CCA_EMBEDDING_DIM` 后，旧参数构建的版本会在发布/切版时以 `PROCESSING_FAILED` 拒绝（需重建），`CCA_VECTOR_SPACE` 在入库中途变化也不会把向量写进别的空间（`test_knowledge_publish.py` 3 例守护）。测试环境的 Docker 端口映射偶发瞬时断连（`pymysql 2003`）由 `backend/tests/db_retry.py` 有界重试吸收：只对连接层错误码重试（默认 4 次、指数退避），约束冲突/语法错误/断言失败一律不重试，口径由 `test_db_retry.py` 的 14 例守护。
- 对话入口去空白后非空才接受（全角空格同样 422）；历史超过 30k 字符预算时只保留最近完整问答对，并在 SSE `status.code=CONTEXT_TRUNCATED` 后于界面上给出可见提示（FR-CHAT-001）。重启恢复有整链路用例：入库/删除清理中途"进程被杀"（running + 租约过期）后由新 worker 接管，结果只发布一次、清理完成、已删文档不复活（`test_worker_restart.py` 2 例）。\n- 批次发布要么整批可见、要么整批补偿：发布任务终态失败（重试预算耗尽或不可重试，如 `VECTOR_SPACE_MISMATCH`）会把批次推进 `compensating`→`failed` 并清理，不会永久停在 `processing`；发布事务内若发现文档已被并发删除，整批转补偿而绝不把 `removed` 文档改回 `shared`；未发布批次删掉其中一份文档时当场整批补偿（`test_knowledge_publish.py` 3 例守护）。
- 日志默认脱敏：SQLAlchemy 的 `[parameters: …]` / `[SQL: …]` 参数块与 `password=`、`token=`、`Bearer …`、`Set-Cookie` 等凭据形态在 formatter 之前替换为 `<redacted>`（`backend/app/shared/log_redaction.py`，含异常 traceback，9 例守护）。审计记录带请求级耗时，403/404 权限拒绝写 `access.denied` 审计行。
- 契约 `contracts/openapi_v0.1.json`：**40 个操作（公共 36）**，含 `POST /api/v1/auth/register`（201 + 与登录同结构的令牌、`409 DUPLICATE_ACCOUNT`、`422 VALIDATION_FAILED`）与 `GET /api/v1/admin/stats/overview`（运行统计聚合）。
- 前端门禁全过：类型检查、SFC 编译（56 个 `.vue`）、10 项不变量、stylelint 分层纯度、OpenAPI 类型漂移、契约漂移、生产构建。
- 端到端（真实四进程：公共/内部 API + MCP + worker）：接口链路 **32/32 步**（登录 → 课表 → 计划幂等/版本冲突 → SSE 三工具 → 引用展开 → 草稿保存 → 管理端增删改查）；
  headless 浏览器冒烟 **40/40 项**（登录页两栏与注册 Tab、SSE 文本流入、引用卡展开、助手输入条改版与整页单滚动）+ 逐屏走查 **69/69 项**
  （课表统计条图标与时间轴导轨 / 学习计划 / 登出菜单 / 管理端 4 页与二级导航可达性 / 文档页拖放区：形态、拖入态、拖入即发出上传请求（拦截后中止，不写库） / 表格 `caption` 视觉隐藏但仍作表格的可访问名 / 助手页一体式输入条：圆形发送按钮、悬停冒泡提示、对话再长也不动、右栏悬浮卡），控制台 0 error。
- 自助注册闭环另有浏览器级用例 **21/21 项**：空表单不发请求、密码不一致就地报错、注册即登录、`role=student`、重复账号 409 就近回填、退出后可用新账号登录。
- 检索空结果分两态：`tool_end.data.corpus_empty`（仅 `search_course_docs` 成功时出现）把「全库尚无资料」与「本次没检索到」分开；前者渲染 `inbox` 空态「管理员还没有上传可检索的课程资料。」而非「换个问法」。后端由 pytest 覆盖，前端由 mock 脚本 **9/9 项**覆盖。
- 固定 AI 评测（50 条主体 + 16 条对抗）已在确定性 Provider 基线上跑过：有依据答案 + 引用联合通过率 **0.60**（门槛 0.90）、未覆盖问题 0/10、课表 9/10、计划 10/10、权限/注入/冲突 13/13；写入正确与隔离通过。**当前结论是「基线不达标」**：确定性 Hash Embedding 下「有依据」与「未覆盖」的检索分数区间重叠（实测 top 分 0.21–0.55 vs 0.19–0.36），**靠阈值分不开**，需真实 Embedding（TBD-04）后重标；相关性阈值已做成配置项 `CCA_RETRIEVAL_MIN_SCORE`，但**默认关闭（0）**：实测短查询相似度可低于 0.05，任何非零默认值都会误杀正常命中，须等真实 Embedding（TBD-04）评测标定后再打开。多来源判定类问题现在会并列依据并提示「可能不一致」（FR-QA-004 的冲突半边）。
- 性能实测（本机单进程 + 真实 MySQL，200 份已发布文档、20 个在线用户 / 5 并发助手）：普通读取 **1200 次 100% 成功，P50/P95/P99 = 194/542/1226 ms**；助手 **120 个请求完成率 100%**（首状态 P95 470 ms、首段实质回答 P95 5.5 s）；1 MiB 内文本入库 **30 份 P95 4.7 s**；6 并发助手时 5 个进入执行、第 6 个 429 `CAPACITY_LIMITED`；模型/检索/向量库三类依赖故障下，课表、计划与课程管理仍全部可用。以上是**单机回环**数据，不含真实网络与真实模型时延。
- **未验证**：真实大模型与 Embedding 质量、生产向量库、OCR/扫描件、多机部署与真实网络下的性能、生产规模备份与 binlog 时间点恢复（本机单容器恢复演练已实测：46 KB dump 恢复 + 29 项校验 RTO 5.7 s，删除标记不复活、同 Idempotency-Key 重放 0 增量）、Firefox/Safari。
- **已知限制**：自助注册只收「账号 + 显示名 + 密码」，没有邮箱/手机验证、没有频率限制与验证码、没有找回密码；管理员账号不能自助注册。
  本地模型 / Embedding / 向量库均为确定性实现，**不要**当作生产 AI 能力对外宣称。

## 开发约定

- 分支：`main` ← `dev` ← `phase/0x-*`；每车道一个 git worktree。
- 测试分层：日常只跑 T0 定向 / T1 车道门禁，**T2 全量只在收尾阶段**统一执行。
- 依赖安装走国内镜像（pip：阿里云；npm：`registry.npmmirror.com`）。
- 过程性、开发、计划文档不入 git（需求 / 设计 / 计划 / 报告只留在磁盘，不随代码库分发）。
