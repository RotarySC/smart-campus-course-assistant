# 校园课程智能助手（Smart Campus Course Assistant）

面向学生的课程与学习助手：查课表、读课程资料、与助手对话生成并保存学习计划。

Vue 3 + TypeScript 前端，FastAPI + SQLAlchemy(async) + MySQL 8.4 后端；助手链路是真实 SSE 流式响应 +
私有 MCP 服务（三个工具：`get_my_schedule` / `search_course_docs` / `save_study_plan`）。

## 能力

| 能力 | 说明 |
| --- | --- |
| 身份与会话 | 登录、自助注册（注册即登录、固定学生角色）、Bearer 会话、登出即失效；学生/管理员两种角色 |
| 课表 | 本人课程与课表查询，单次跨度 ≤ 31 天，按学校时区 |
| 学习计划 | 计划列表/详情、对话内生成草稿、幂等保存（写入许可 + 容量槽） |
| 资料问答 | 上传 → 解析 → 分块 → 向量 → 整批发布 → 检索；回答带可展开引用，文档删除后引用 410；「全库无资料」与「本次没检索到」分开呈现；同名课程先补问；资料冲突时并列依据并提示可能不一致 |
| 助手对话 | `POST /api/v1/chat/stream`：六类 SSE 事件、工具调用与回执、对话内保存 |
| 管理端 | 课程、学生、课表、资料批次与发布的增删改查；四个管理页经二级导航互达 |
| 运行统计 | `GET /api/v1/admin/stats/overview`：按学校时区自然日统计回答终止分类、计划/草稿/引用/工具/批次计数、worker 积压与清理达标；只读聚合，不含正文 |

## 安装与启动

前置条件：Docker Desktop（MySQL 容器 `cca-mysql`）、仓库根 `.venv`（Python 3.12，依赖已装）、Node 24 + pnpm 11。

```powershell
.\scripts\start.ps1     # MySQL 容器 + 迁移 + 种子 + 后端四进程 + 前端
.\scripts\status.ps1    # 巡检（容器/端口/三个服务/日志错误行）
.\scripts\stop.ps1      # 停止（-StopDocker 连库一起停）
```

打开 <http://localhost:5173/>，用 `student_demo / demo1234`（或 `admin_demo / demo1234`）登录——仅开发种子账号；
没有账号可以在登录页「注册」Tab 自助创建（固定学生角色，注册即自动登录）。

想要更完整的演示数据（8 名学生、8 门课程、两周课表、每人 2 份计划、5 份可检索资料）：

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

worker 常驻模式**启动即做一次**孤立文件巡检（`--no-startup-sweep` 可关）；巡检按内部引用清理
`documents/`、`attempts/`、`uploads/` 下没有任何行指向且超过 1 小时未修改的文件（在途写入不会被误删），
每次写一条 `storage.orphan_sweep` 审计；文档/批次清理从入队到完成超过 5 分钟会在 `document.cleanup`
（或 `document.batch.compensated`）审计里带 `slow_cleanup: true` 与耗时。

## 用法

### 服务与端口

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| 前端 dev | 5173 | <http://localhost:5173/>（只绑 localhost/`::1`） |
| 公共 API | 8100 | `/api/v1`，只回环；健康检查 `/api/v1/health` |
| 内部 API | 8101 | `/internal/v1`，只回环 |
| MCP server | 8102 | `/mcp`，私有 Streamable HTTP，三工具 |
| MySQL | 33061 | 容器 `cca-mysql`，演示库 `cca` |

### 配置项

后端配置集中在 `backend/.env`（复制 `backend/.env.example` 后修改）；完整键集、默认值与注释都在该文件内。

#### 助手模型

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

切 `openai-compatible` 时 `BASE_URL`、`API_KEY`、`NAME` 缺一项**服务启动即失败**；填全后走真实的
`POST {BASE_URL}/chat/completions`：工具调用、草稿意图、正文流式、预算与有界重试均已实现（2026-10-28 实测）。
`BASE_URL` **要带 `/v1`**；推理模型要把 `CCA_MODEL_MAX_TOKENS` 提到 `4096`（2048 会被思考吃光，正文为空）。

所有 `CCA_*`（含 `CCA_ASSISTANT_*`、`CCA_EMBEDDING_*`、`CCA_RETRIEVAL_*`、`CCA_VECTOR_SPACE`、`CCA_CHUNK_*`）
都从 `backend/.env` 读取，优先级是**进程环境变量 > `backend/.env`（或 `CCA_ENV_FILE` 指向的文件）> 代码默认值**，
所以写进 `.env` 即生效，CI/容器仍可用环境变量临时覆盖。漏配的典型症状：provider 回落 64 维确定性向量，
而索引是 1024 维 → **检索静默返回空**，日志里只有一行 `cca.vector.local` 的"维度与查询维度不一致，已跳过 N 条"。
换 Embedding 服务端/升级后先跑内容级探针（仓库根执行）：

```powershell
.\.venv\Scripts\python.exe scripts\verify_embedding.py --samples 8
```

它把一批长度悬殊的文本同时送批量与单条接口、比对余弦（默认 ≥0.999）；条数/维度/范数校验发现不了的
批量错位只有这一步能拦住，退出码非 0 即失败。

#### 检索向量（Embedding）

默认 `deterministic`：SHA-256 特征向量（64 维），离线可复现，**只用于测试/演示**。
接真实语义向量时切 `openai-compatible`，走标准 `POST {BASE_URL}/embeddings`（OpenAI 兼容）。

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `CCA_EMBEDDING_PROVIDER` | `deterministic` | `deterministic` 或 `openai-compatible` |
| `CCA_EMBEDDING_BASE_URL` | 空 | 以 `/v1` 结尾的服务地址，只接受 `http(s)://` |
| `CCA_EMBEDDING_MODEL` | `Qwen3-Embedding-0.6B` | 服务端不校验时也必须填：它进冻结摘要与日志 |
| `CCA_EMBEDDING_API_KEY` | 空 | 非空才发 `Authorization: Bearer` |
| `CCA_EMBEDDING_DIM` | `1024` | 必须与服务端 `dim` 一致，不一致入库直接失败（不写不同源向量） |
| `CCA_EMBEDDING_BATCH_SIZE` | `16` | 单次请求条数（服务端上限常见 256） |
| `CCA_EMBEDDING_VERIFY_BATCH` | `0` | 1=批量内容级自检：每批多 1 次单条请求，比对批内最短那条余弦 >0.999 |
| `CCA_EMBEDDING_TIMEOUT_SECONDS` | `30` | 单次请求超时 |
| `CCA_EMBEDDING_MAX_RETRIES` | `2` | 连接/超时/5xx 有界重试；4xx 不重试 |

检索精排（Reranker / 跨编码器）与相关性门默认**都关闭**，开与不开的行为差异见「自验 → 已测结果」：

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `CCA_RERANK_ENABLED` | `0` | 1=开启精排层；开启后余弦硬门 `CCA_RETRIEVAL_MIN_SCORE` **不再过滤候选**（它改作"向量是否自信"的判据） |
| `CCA_RERANK_BASE_URL` | `http://127.0.0.1:8892` | 服务根地址（不含 path），只接受 `http(s)://` |
| `CCA_RERANK_PATH` | `/rerank` | 端点路径 |
| `CCA_RERANK_MODEL` | `bge-reranker-v2-m3` | 只进日志与 `Reranker.name`，**不进请求体**（契约无 model 字段） |
| `CCA_RERANK_TIMEOUT_S` | `20` | 单次请求超时；连接错误/超时/408/5xx 固定重试 1 次 |
| `CCA_RERANK_TOP_K` | `8` | 送入精排的候选数（余弦序前 K 条） |
| `CCA_RERANK_LOW` | `0.30` | 精排分低于此值**不再单独判空**：还要看余弦是否认为存在候选（见下方分数语义）；判官未装配时它是唯一分数门 |
| `CCA_RERANK_HIGH` | `0.90` | 精排分不低于此值直接放行（单次判官否定不足以推翻接近满分的片段） |
| `CCA_RERANK_NOISE_FLOOR` | `0.01` | 精排分的噪声底：低于它等于模型没找到对应关系，直接判空、不花 LLM 判官 |
| `CCA_RERANK_FAIL_OPEN` | `1` | 精排不可用（503/超时/契约不符）时 1=退回余弦分数门、0=判空 |
| `CCA_RERANK_MAX_DOC_CHARS` | `1200` | 单条文档送入前的截断长度 |
| `CCA_RERANK_MAX_DOCS` | `32` | 单次请求最多文档数（超出不送、分数按 0.0 对齐） |

分数语义（`LOW`/`HIGH` 由评测主集标定，达标区是成片的而非单点）——**精排分不再一票否决**，
`[噪声底, LOW)` 这一段要余弦复核：

| 精排分 | 余弦 top-1 | 处置 |
| --- | --- | --- |
| ≥ `HIGH` | 任意 | 放行 |
| ∈ [`NOISE_FLOOR`, `LOW`) | < 判官带下界（0.45） | 判空（两个信号一致：无依据，不花 LLM） |
| ∈ [`NOISE_FLOOR`, `LOW`) | ≥ 判官带下界 | 交 LLM 判官读片段复核 |
| < `NOISE_FLOOR` | 任意 | 判空（精排输出等于噪声） |
| ∈ [`LOW`, `HIGH`) | < 向量置信门（`CCA_RETRIEVAL_MIN_SCORE`） | 放行（判官对弱证据会随机否决） |
| ∈ [`LOW`, `HIGH`) | ≥ 向量置信门 | 交 LLM 判官读片段复核 |

为什么要余弦复核：实测 `bge-reranker-v2-m3` 的中文 logit 余量很薄，同一个片段换个问法就能从
0.99 掉到 0.05（同一权重、fp16 与 fp32 逐对复核一致，见「已知限制与未验证项」）。只按绝对分
判空会稳定误杀"有答案但问法不讨喜"的问题。判官不可用时按 `CCA_RETRIEVAL_JUDGE_FAIL_OPEN` 处理。

切换 Provider 会改变 `parser_config_digest` 与向量空间：**已发布版本必须重建**（重新入库发布），
否则检索查询向量与库内向量不同源。建议同时换 `CCA_VECTOR_SPACE`（如 `corpus_qwen3_v1`），
让新旧向量互不可见，而不是等摘要校验在发布时才报错。

示例（远端服务只绑回环时，先用 SSH 隧道把端口映射到本机，再指向隧道；精排与向量共用同一个端口）：

```bash
# 终端 1：保持隧道（8892 → 远端 127.0.0.1:8892，向量与精排都在这个端口后面）
ssh -N -L 8892:127.0.0.1:8892 <跳板主机>
# 终端 2：验证隧道通（/health 同时报告 embedding 与 rerank 两套状态）
curl -s http://127.0.0.1:8892/health
```

```dotenv
CCA_EMBEDDING_PROVIDER=openai-compatible
CCA_EMBEDDING_BASE_URL=http://127.0.0.1:8892/v1
CCA_EMBEDDING_MODEL=Qwen3-Embedding-0.6B
CCA_EMBEDDING_DIM=1024
CCA_VECTOR_SPACE=corpus_qwen3_v1
# 精排（可选）
CCA_RERANK_ENABLED=1
CCA_RERANK_BASE_URL=http://127.0.0.1:8892
CCA_RERANK_LOW=0.30
CCA_RERANK_HIGH=0.90
CCA_RERANK_NOISE_FLOOR=0.01
```

> 隧道断开时入库任务会以 `EMBEDDING_FAILED`（可重试）收敛，不会写成半截向量；检索请求则显式报依赖失败，不会假装没找到。

### 目录（内容结构）

| 路径 | 内容 |
| --- | --- |
| `web/` | Vue 3 + TS + Pinia + vue-router 4 + Vite；默认连真实后端，mock 为显式 opt-in（前端命令与门禁见 `web/README.md`） |
| `backend/` | FastAPI + SQLAlchemy(async) + Alembic + MySQL；身份/课程/课表/计划/资料/助手 + MCP（环境与端到端见 `backend/README.md`） |
| `scripts/` | 一键启动/停止/巡检（PowerShell，另有 `.cmd` 双击入口）与 Embedding 内容级探针 |
| `contracts/` | 契约真源：OpenAPI、MCP 工具、SSE 事件 schema、DDL（类型生成与门禁的输入） |

## 自验

先 `.\scripts\start.ps1`，再跑下面这组命令（约 1 分钟，无需额外数据）：

```powershell
.\scripts\status.ps1                                                                    # 容器/端口/三服务/日志错误行
(Invoke-RestMethod http://127.0.0.1:8100/api/v1/health).data | ConvertTo-Json -Compress   # process/database 两级健康
& .\.venv\Scripts\python.exe -m pytest backend\tests\test_identity.py -q --basetemp=.worktrees\pt\selfverify   # 22 passed
cd web
node scripts\check-sfc.mjs                                                               # 56 个 .vue 编译通过
```

全量后端测试（真实 MySQL，约 13 分钟）：

```powershell
& .\.venv\Scripts\python.exe -m pytest backend\tests -q --basetemp=.worktrees\pt\full
```

前端完整车道门禁见 `web/README.md`（其中 token 相关门禁需要设计源，设计源不随代码库分发，见「已知限制与未验证项」）。

### 已测结果

- 后端 **461 个用例**全绿：2026-10-29 全量一次跑出 **461 passed / 810.12 s**（真实 MySQL，0 failed / 0 skipped）。
- 前端门禁：类型检查、SFC 编译（56 个 `.vue`）、10 项不变量、stylelint 分层纯度、类型/契约漂移全过；
  `pnpm build` 生产构建需在无 `child_process` 管道限制的机器上执行（本机沙箱内不可用，原因见 `web/README.md`）。
- 契约 `contracts/openapi_v0.1.json`：**40 个操作（公共 36）**；DDL 23 张表。
- 端到端（真实四进程）：接口链路 **32/32 步**；headless 浏览器冒烟 **40/40 项**、逐屏走查 **69/69 项**；
  注册闭环 **21/21**；AT-31 无障碍与注入 **15/15**。
- 验收台账（33 条 AT）：**32 有证据 / 1 部分 / 0 无**；唯一「部分」仍是 AT-32——主集 66 条全部口径达标、
  留出集 `based` 全过但 `uncovered` 19/20，且语料仅 9 份、样本规模有限，不据此宣称"依据不足处理已普遍达标"。
- 真实 Embedding 已接入并标定：Qwen3-Embedding-0.6B（1024 维）入库 → 发布 → 检索全链路实测通过；
  基于 30 条 query 的标定显示**单一绝对阈值无法同时满足两门**（based 最低余弦 0.434、uncovered 最高 0.645，
  穷举 13272 条阈值规则 0 条可行），因此阈值默认关闭。
- 固定 AI 评测（真实模型 + 真实 1024 维向量 + 跨编码器精排，2026-10-29 全量 66 条 / 1107 s）：
  `based` 联合通过率 **20/20 = 1.00**（门槛 0.90，达标）、`uncovered` **10/10**（达标）、
  `schedule`/`plan` **10/10**、隔离 **3/3**、对抗 **13 pass / 0 fail / 3 not_executed** → **`passed_gate=true`**。
  首 token P50/P95 = 19.8 s / 29.7 s（评测副产物，非 PERF 证据）。
- **精排低分复核（2026-10-29 补）**：精排分落在 `[0.01, 0.30)` 时不再单独判空，而要余弦复核——余弦认为
  存在候选就交 LLM 判官读正文。这一步修掉两个先前稳定失败的用例：`B15`（冲突资料必须并列，见下一条）
  与 `INJ01`（注入资料的"评分规则"片段被精排打成 0.03，改由判官复核后正常作答并带真实引用）；
  同时把 `uncovered` 保持在 10/10（判官对 9 条中的 1 条会真正读正文，其余仍在噪声底直接判空）。
- **冲突资料口径对齐（FR-QA-004）**：`B15` 原先按"答案不得出现『包含级数』"判红，与 FR-QA-004
  "并列依据 + 提示可能不一致"直接冲突。判据改为**条件式**：引述「包含级数」本身不算违规，
  但必须同时出现"不一致/冲突/以任课教师"这类提示，裸断言仍然判红。
- **精排带来的变化（同一棵树、同一套数据的前后对比）**：`uncovered` 8/10 → **10/10**、`based` 18/20 → **20/20**
  （其中 B01 由"判空无引用"变为正常作答）、`isolation` false → **true**（PERM04 首次真正执行）。
  分数门由 30 条主集标定：`LOW=0.30`、`HIGH=0.90`，达标区是成片的（LOW 0.10–0.40 × HIGH 0.80–0.95 全部达标）。
- **独立留出集（40 条：20 based + 20 uncovered，未参与任何标定）**：`based` **20/20 = 1.00**、
  `uncovered` **19/20 = 0.95**（比上一轮的 19/20 + 20/20 是"把一个假阴性换成假阳性"：
  上一轮唯一失败 `H-B09`（高数题型分值）已通过；本轮唯一失败 `H-U11`（问"要不要提交课程设计"）
  是判官假阳性——检索回了 5 条引用并判 ok，而答案本身仍明确写着"资料中未提及…依据不足"）。
  `uncovered` 的验收口径是"必须 `empty` 且无引用"，因此 19/20 记为**未过门**，不按"答案说得对"折算。
- 这个过程里修掉三个与判定规则无关的缺陷：① 新题最初没沿用"资料里说……"的措辞，模型判断"这不是资料问题"
  就直接作答、不调检索工具，数字失真（首轮 17/20 + 15/20 已留档，不采信）；② MCP→内部 API 的调用超时
  只有 10 s，而检索链路最坏要 12.5 s（判官上限 12 s），慢查询会被这条内层超时切成 `MCP_UNAVAILABLE`；
  ③ `CONF02`（未确认的重叠课表）用例不自清理——上一轮真写入的那一行会让之后每轮先撞唯一键
  `DUPLICATE_SCHEDULE`，用例不可重复执行；现在先按"探针键"删残留，请求后再确认没被写回来。
- **口径**：主集 66 条与留出集 40 条都只在"各自集合内"记账；主集过门 + 留出集 based 全过，仍不等于
  "AI 质量普遍达标"（语料只有 9 份、留出集只有 40 条，且仍在"假阴性↔假阳性"之间腾挪）。
- 性能（本机单进程 + 真实 MySQL，200 份已发布文档、20 在线用户 / 5 并发助手）：普通读取 **1200 次 100% 成功，
  P50/P95/P99 = 194/542/1226 ms**；助手 **120 请求完成率 100%**（首状态 P95 470 ms、首段实质回答 P95 5.5 s）；
  1 MiB 内文本入库 **30 份 P95 4.7 s**；6 并发时第 6 个 429 `CAPACITY_LIMITED`。单机回环数据，不含真实网络与模型时延。

## 已知限制与未验证项

- **默认配置不是生产 AI**：默认 `deterministic`（本地 64 维 Embedding + 关键词 Provider）；`.env.example` 里的
  真实供应商配置是"可切"，不等于"已生产就绪"。生产必须覆盖数据库口令、`CCA_SERVICE_TOKEN`、`CCA_DELEGATION_SIGNING_KEY` 等秘密。
- **账号体系**：自助注册只收「账号 + 显示名 + 密码」，没有邮箱/手机验证、频率限制、验证码与找回密码；管理员账号不能自助注册。
- **AI 质量门槛**：主集 66 条过门（based 20/20、uncovered 10/10、隔离 3/3、对抗 13/13 可执行项全过）；
  留出集 40 条 `based` 20/20、`uncovered` 19/20（未过门，唯一失败 `H-U11` 是判官假阳性：检索判了 ok、
  答案仍写"资料中未提及…依据不足"）。**跨编码器精排对问句措辞极敏感**：同一片段换个问法，
  `bge-reranker-v2-m3` 的 sigmoid 分能从 0.99 掉到 0.05（同一权重、fp16 与 fp32 逐对复核一致，
  见 `verification/evidence/at32-retrieval/rerank-query-sensitivity.json`），所以绝对分阈值不能单独一票否决，
  低分区必须让余弦复核；这条规则目前只在主集标定过，`[0.01, 0.30)` 这一段仍可能在"假阴性↔假阳性"
  之间腾挪。语料只有 9 份、样本规模有限，要稳定过门仍需补语料与扩样本。
- **未验证/未实现**：生产向量库（当前是本地 JSON 实现）、OCR/扫描件、多机部署与真实网络下的性能、
  生产规模 binlog 时间点恢复、Firefox/Safari、密钥托管与轮换、登录频率限制。
- **本地门禁前提**：`web` 的 token 同步/漂移门禁与设计源逐字节比对，而设计源、需求/验证文档一样
  **不随代码库分发**；新克隆缺设计源时 token 相关门禁会失败，其余门禁可跑。
- **测试环境**：需要真实 MySQL（容器 `cca-mysql`）与短路径 `--basetemp`（Windows MAX_PATH）；
  `tests/test_release_migration.py` 会清空所连库，必须独占库串行执行。
