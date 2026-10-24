# 独立验证报告 · 一键启动/停止/巡检脚本与启动文档（task-11）

| 项 | 值 |
| --- | --- |
| 验证者 | `qa-verifier`（独立于交付者，不接受 Lead 自测结论） |
| 被验证对象 | **`main` @ `1d4ce11` + 工作树 9 行未提交补丁**（见 R3：复验时脚本工作树比提交多 9 行 `instance-<port>.db` 标记逻辑；我的实测跑的就是这棵树）：`scripts/start.ps1` / `stop.ps1` / `status.ps1` + `start.cmd` / `stop.cmd` / `status.cmd` + `.gitattributes`；文档 `README.md`（根）、`backend/README.md`、`web/README.md`、`docs/STARTUP.md`、`docs/PHASE-STATUS-002.md` §6、`docs/phases/PHASE-PLAN.md` §8.2。首轮对象为 `eb613e1` 的未提交交付（`d0a`/`d1` 两轮，见 §1） |
| 验证方式 | 逐行读脚本 → 真实环境端到端执行（停/启/幂等/多实例/负向/巡检/`.cmd` 入口），真实 HTTP + SSE + MySQL 数据核对 |
| 环境 | Windows / PowerShell 7 / Node 24.18.0 / pnpm 11.21.0 / `.venv` Python 3.12.10 / Docker `cca-mysql`（MySQL 8.4）|
| 数据边界 | 未 `-StopDocker`、未 `-ResetDb`、未删演示数据；`cca` 实测前后 **24 表 / 17 用户**不变；D7 用一次性库 `cca_alt` 复验后已 DROP |
| 复验轮次 | 第 1 轮（`eb613e1` 未提交交付）：**FAIL**（阻断 D2）。第 2 轮（`1d4ce11` 提交）：**PASS** —— D2/D1/D3/D4/D5–D8 全部闭环，仅剩 2 条低危文档措辞建议（R1/R2），不阻断 |
| **最终判定** | **PASS（`1d4ce11`）** |

---

## 0. 结论摘要

- **Lead 本轮修复的两个缺陷都验证通过**：
  - Vite 只绑 `localhost`：脚本/文档统一用 `http://localhost:5173/`；实测 `localhost` → 200，`127.0.0.1:5173` → `ConnectError`（与文档 §6.3 描述一致）。
  - 多实例隔离：`stop.ps1 -PublicPort 8200 -InternalPort 8201 -McpPort 8202` **不再误杀**默认实例的 5173；停完 8100/8101/8102/5173 仍 UP，前端 200。
- **主路径（`.\scripts\*.ps1`）功能全部通过**：全新启动、真实链路（health/login/课表/SSE 终态 succeeded）、幂等重启、双实例并存、负向不崩溃、巡检字段（容器/33061/24 表/0001/四服务+前端）。
- **阻断项**：`scripts/*.cmd` 三个文件是 **LF 换行**（CR=0/LF=6），`cmd.exe` 解析异常 —— 实测双击式执行会先打印 `'d' is not recognized as an internal or external command`（`stop.cmd`/`start.cmd`）；`status.cmd` 还会多打印一段 cmd banner + 提示符。`.ps1` 不受影响（pwsh 接受 LF）。
- **非阻断缺陷 3 个**：非默认实例汇总表 Worker 行误报 DOWN（D1）；`stop.ps1` 的 `$WebPort`/`$webPort` 大小写冲突导致确认行显示 `…/0` 且 `-WebPort` 对非默认实例失效（D3）；`status.ps1` 对非默认实例仍拿默认 5173 判前端 + 健康状态下也输出 stderr 段（D4）。
- **文档差异**：`-ResetDb` 说明与代码相反（D5）、`status.ps1` 端口参数未文档化（D6）、多实例"不同库"缺可操作说明（D7）、两份 README 测试库清单不一致（D8）。

### 复验摘要（`1d4ce11`，第 2 轮）

| 项 | 首轮 | 复验 | 关键证据 |
| --- | --- | --- | --- |
| D2 `.cmd` 换行（阻断） | FAIL | **PASS** | CR=6/LF=6；`.gitattributes`（`*.cmd text eol=crlf`）；`git check-attr` 确认；三个 `.cmd` 实跑无 `'d' is not recognized`、无 banner，exit 0 |
| D1 汇总表 Worker 行 | FAIL（低） | **PASS** | 默认实例停止时起 8200 实例 → 汇总 `Worker … UP`；pid 指向 `worker-8200.pid`；status 同 |
| D3 `$WebPort` 大小写冲突 | FAIL（低） | **PASS** | `stop.ps1 -PublicPort 8200 …` 输出 `8200/8201/8202 已全部释放`（无 `/0`、无 5173），默认实例 5173 不受影响 |
| D4 status 跨实例/噪音 | FAIL（低） | **PASS** | 8200 实例：`前端 - DOWN 该实例未起前端`；日志段 `无 ERROR/Traceback（仅有 INFO 级启动日志）` |
| D5 `-ResetDb` 文案 | 事实错误 | **PASS** | STARTUP §2.1 改为"清空重建迁移，然后照常写种子；跳过种子加 `-SkipSeed`"，与代码一致 |
| D6 status/stop 端口参数 | 缺文档 | **PASS** | STARTUP 第 78 行写明两者接受同样四个端口参数 |
| D7 多实例换库 | 表述不完整 | **PASS（实测）** | 建 `cca_alt` → `$env:DATABASE_URL=…cca_alt` → 起 8200：WARN"使用进程环境变量 DATABASE_URL"、`演示库：cca_alt`、`cca_alt` 24 表、`instance-8200.db=cca_alt`、health ok、`cca` 不受影响；停后 DROP 干净 |
| D8 测试库清单 | 不同步 | **PASS** | `backend/README.md` 已含 `cca_test_lead` |
| 第 9 项（`-SkipSeed` 汇总） | — | **PASS** | 汇总打印 `演示账号：未写入（-SkipSeed）` |
| 第 10 项（CI/管道说明） | — | **部分（R1）** | `pwsh -File start.ps1 -NoFrontend` 无下游缓冲时 **13s 返回 exit 0** ✓；但 `… | Out-String`（需 EOF 缓冲）**>50s 不返回**，`.cmd` 同样；文档把"ps1 不阻塞 / cmd 阻塞"绝对化，需改为"取决于调用方是否按 EOF 缓冲" |

**复验结论：阻断项 D2 已闭环 → PASS。** 新发现仅为 2 条低危文档建议（R1 见上、R2 见 §4），不影响发布。


---

## 1. 改动面（检查项 1）

命令：`git status --porcelain`、`git diff --stat`（工作树，非提交）

```
 M .gitignore
 M backend/README.md
 M backend/migrations/env.py
 M web/README.md
?? README.md
?? scripts/
```

`git diff --stat`：`.gitignore +7/-4`、`backend/README.md 194 行`、`backend/migrations/env.py 2 行`、`web/README.md +14`。

- **第 1 轮（`eb613e1`）**：交付**尚未 commit**，`scripts/`、根 `README.md` 为未跟踪新文件。
- **第 2 轮（本轮复验对象）**：`main` = `1d4ce11`；`git show --stat 1d4ce11` = 12 files / +1035 −81，含 `scripts/*`（6 个）、`.gitattributes`（新增）、根 `README.md`、`backend/README.md`、`web/README.md`、`.gitignore`、`backend/migrations/env.py`（r-string 修复）。
  - **复验时工作树另有 3 个脚本的 9 行未提交新增**（R3）：`scripts/start.ps1`（写 `instance-<公共端口>.db`）、`scripts/status.ps1`（优先读该文件显示实例库名）、`scripts/stop.ps1`（删除该文件）；`git diff --stat scripts/` = 3 files / +9 −0，mtime 10:48:17–10:48:31（复验开始前）。我逐行核对：该补丁**未触及** D1/D3/D4 的修复逻辑、也未触及 `.cmd`（D2），只新增 marker 写/读/删；我实测的行为即为「提交 + 该补丁」。
  - 工作树另有 ` M verification/README.md`（Lead 更新报告索引）+ `?? verification/STARTUP-SCRIPTS-VERIFICATION.md`（本报告）。
  - 换行策略：`.gitattributes` 含 `*.cmd text eol=crlf` / `*.bat` / `*.ps1 text eol=lf`；`git check-attr` → `scripts/start.cmd: eol=crlf`、`scripts/start.ps1: eol=lf`；实测三个 `.cmd` 均 `CR=6/LF=6`。
- **注意**：`backend/migrations/env.py` 的改动（docstring 前加 `r` 前缀，消除 `SyntaxWarning: invalid escape sequence '\.'`）**超出 task 声明的"scripts + 文档"范围**。我独立验证该改动是良性的：`compile()` 在 `warnings.simplefilter("always")` 下 **SyntaxWarning = 0**（修复前该警告每次 alembic 都出现），零运行时行为变化。
- 参数表核对（脚本 `param()` 提取 vs `docs/STARTUP.md` §2.1）：
  - `start.ps1`：`PublicPort, InternalPort, McpPort, WebPort, NoFrontend, Mock, SkipSeed, SkipDocker, ResetDb, SkipInstall, WaitSeconds`（11 个）↔ 文档 8 行覆盖全部（四端口合并一行）✅
  - `stop.ps1`：上述四端口 + `StopDocker`（5 个）↔ 文档 §5/§7 覆盖 ✅
  - `status.ps1`：上述四端口（4 个）↔ **文档未提及**（见 D6）
- `.cmd` 三件套均存在，结构一致（`chcp 65001` → `pwsh -File <同名>.ps1 %*` → `exit /b`），参数透传；但存在换行缺陷（D2）。

---

## 2. 逐项 PASS/FAIL

| # | 检查项 | 判定 | 证据摘要 |
| --- | --- | --- | --- |
| 1 | 改动面/脚本存在/参数表与文档一致 | **PASS（附 D6/D8 差异）** | §1；参数提取对照；`.cmd` 存在但见 D2 |
| 2 | `stop.ps1` 清场（MySQL 保留） | **PASS** | exit 0，4s；kill 前端 PID 20252/5173 owner 20380、worker、mcp、internal、public；`8100/8101/8102/5173 已全部释放`；`cca-mysql` 仍 Up |
| 3 | 全新 `start.ps1` | **PASS** | exit 0；六行汇总表全 UP；MySQL/迁移/种子/四服务/前端各步 `[OK]` |
| 4 | 真实链路 | **PASS** | health `status=ok database=ok process=ok`；login 200；`/me/schedules` 200（4 条，10 天区间）；SSE `status,status,tool_start,tool_end,token,done`，`done.state=succeeded`；`localhost:5173` 200；`127.0.0.1:5173` 拒连（符合文档） |
| 5 | 幂等（二次 `start.ps1`） | **PASS** | exit 0；监听 PID 不变（8100=8644 / 8101=19940 / 8102=8344 / 5173=16260）；5 个 PID 文件内容逐字节不变；`app.entrypoints` python 进程数 8→8（4 服务 × venv launcher + 真解释器） |
| 6 | 多实例隔离 | **PASS（重点修复项）** | 起 `-NoFrontend -PublicPort 8200 -InternalPort 8201 -McpPort 8202`：exit 0，8200 SSE `done.succeeded`；PID 文件 `public-8200/internal-8201/mcp-8202/worker-8200` 与默认实例并存；停 8200 后 **8100/8101/8102/5173 全部仍 UP**、前端 200、8200–8202 释放 |
| 7 | `status.ps1` | **PASS（附 D4 噪音）** | 容器 running；33061 监听中；`cca` 24 表；迁移 `0001`；用户 17；四服务 + 前端 UP；`health=ok（process=ok database=ok）`；exit 0。**但**"日志中的 stderr"段在健康状态也输出（见 D4） |
| 8 | 负向：对已停实例执行 | **PASS（附 D3 显示问题）** | `stop.ps1` 重复执行 exit 0（逐项 `[WARN] 未在运行`）；`status.ps1 -PublicPort 8200…` exit 0（公共/内部/MCP/Worker 显式 DOWN，不崩溃）；已停 8200 的 `stop.ps1` exit 0（确认行显示 `8200/8201/8202/0`，见 D3） |
| 9 | 文档一致性 | **FAIL（差异见 §4）** | D5/D6/D7/D8；另有 D2 使"`.cmd` 双击入口"描述与事实不符 |
| 10 | 收尾 | **PASS** | 最终 `stop.ps1` 后 8100/8101/8102/5173/8200/8201/8202 全 free；`cca-mysql` Up 53 min；`app.entrypoints` 进程 0；`backend/var/run` PID 文件 0；`cca` 24 表/17 用户不变 |

### 2.1 关键输出（原文节选）

**全新启动（检查 3）**
```
==> 0/6 前置检查      [OK] Python / Node v24.18.0 / pnpm 11.21.0
==> 1/6 MySQL         [OK] 容器已在运行 / MySQL 已就绪 / 演示库 cca 存在
==> 2/6 配置          [OK] backend/.env 已存在（沿用其中配置）
==> 3/6 数据库迁移    [OK] 迁移完成：cca
==> 4/6 开发种子      [OK] 种子就绪（created:false，全部幂等）
==> 5/6 后端服务      [OK] public 19632 / internal 7432 / mcp 6664 / worker 4928
==> 6/6 前端          [OK] 前端已启动（PID 20336，mock=false）

服务       地址                                状态
公共 API   http://127.0.0.1:8100/api/v1        UP
健康检查   http://127.0.0.1:8100/api/v1/health UP
内部 API   http://127.0.0.1:8101/internal/v1   UP
MCP server http://127.0.0.1:8102/mcp           UP
Worker     后台轮询（无端口）                  UP
前端       http://localhost:5173/              UP
```

**真实链路（检查 4）**
```
health: 200 status= ok database= ok process= ok rid=req_ZgVy7sAVtnwBXi8Z8Zoutg
login: 200 token_len= 43 rid=req_OvjjSF-4vtyZ_68CFUfOHA
schedules: 200 items= 4 range= 2026-10-24 ~ 2026-11-03 rid=req_IJ4eZzMs8_qJPojhEas0Jg
sse events: ['status','status','tool_start','tool_end','token','done']
done: state= succeeded rid=req_fHSIaw1ywv9KfmLXtR3Vqg citations= 0
web localhost: 200   web 127.0.0.1: refused -> ConnectError
```

**多实例隔离（检查 6，本轮修复点）**
```
start 8200: EXITCODE=0；8200 sse: [... 'tool_start','tool_end','token','done'] done.state=succeeded
pid files: internal-8201.pid / mcp-8202.pid / public-8200.pid / worker-8200.pid 与默认实例的 *.pid 并存
stop 8200: EXITCODE=0；[OK] 8200/8201/8202/0 已全部释放
停后默认实例: 8100 UP / 8101 UP / 8102 UP / 5173 UP；frontend localhost: 200
```

---

## 3. 缺陷（脚本，需 Lead 修；我未改任何文件）

> **复验状态（`1d4ce11`）**：D2/D1/D3/D4 全部 **PASS**（修复落点：`.cmd` 改 CRLF + `.gitattributes`；`start.ps1` Worker 行改用 `$workerStem`；`stop.ps1` 改 `$frontendPort` 且非默认实例确认不含 5173；`status.ps1` 非默认实例前端显示 `端口=- / DOWN 该实例未起前端` + 日志只筛 ERROR/Traceback）。以下为**首轮（`eb613e1`）缺陷原文**，保留作证据。

### D2（**阻断**）`.cmd` 入口为 LF 换行，cmd.exe 解析异常

- **现象**：通过真实 `.cmd` 启动器（模拟双击 / cmd 窗口）执行：
  - `scripts\stop.cmd`、`scripts\start.cmd` 先输出一行
    `'d' is not recognized as an internal or external command, operable program or batch file.`
  - `scripts\status.cmd` 先输出 `Microsoft Windows [Version ...]` + `C:\...>` 提示符，然后才输出巡检内容；
  - 脚本本体仍能继续执行并最终 `exit 0`（`.ps1` 被正常调用）。
- **根因（实测）**：三个 `.cmd` 文件均为 **LF-only**：`start.cmd bytes=219 CR=0 LF=6`、`stop.cmd 217/0/6`、`status.cmd 227/0/6`（首 64 字节 `40 65 63 68 6f 20 6f 66 66 0a …` = `@echo off\n`）。`cmd.exe` 要求 CRLF，LF 会使行被错误拼接（本例拼出 `d`/交互命令）。
- **影响**：所有使用 `.cmd` 双击入口的用户在每次启动/停止/巡检时都会先看到一条"不是内部或外部命令"的错误；`exit /b %ERRORLEVEL%` 的解析位置也受影响（当前恰好仍返回 0）。
- **复现**：
  ```powershell
  # 任意目录，用 cmd 的真实双击等价路径（不要用 pwsh 直接跑 .ps1）
  cmd /c "call ""<repo>\scripts\stop.cmd"""     # 首行出现 'd' is not recognized
  cmd /c "call ""<repo>\scripts\status.cmd"""   # 首行出现 cmd banner + 提示符
  ```
- **修复建议**（交给 Lead，我不改）：把 3 个 `.cmd` 以 **CRLF** 重新保存（如 `Set-Content -Encoding ASCII` 写回），并在仓库根加 `.gitattributes`：
  ```
  *.cmd text eol=crlf
  *.ps1 text eol=crlf
  ```
  仓库当前**没有** `.gitattributes`（`Test-Path .gitattributes` = False），否则换行会在下一次格式化/合并时再次被破坏。

### D1（非阻断，低-中）非默认实例的汇总表 Worker 行误报 DOWN

- **现象**：在默认实例**未运行**时启动 8200 实例（`-NoFrontend -PublicPort 8200 …`），汇总表打印
  `Worker 后台轮询（无端口） DOWN`，但磁盘上 `worker-8200.pid=5016` 存在、进程 5016/9448 均在运行，8200 `/health` = `ok`。
- **根因**：`start.ps1` 汇总行硬编码 `Get-RecordedPid 'worker'`（第 422 行），未使用本实例的 `$workerStem`（`worker-<PublicPort>`）；当默认实例在跑时读到默认 `worker.pid`，会**假 UP**（更隐蔽）。
- **影响**：多实例用户会误以为 Worker 没起来（或反之），与 `docs/STARTUP.md` §2.2 "Worker … UP" 的成功判据冲突；不影响服务实际运行。
- **复现**：`stop.ps1` → `start.ps1 -NoFrontend -PublicPort 8200 -InternalPort 8201 -McpPort 8202` → 看汇总表 Worker 行；同时 `Get-Content backend\var\run\worker-8200.pid` 有活 PID。
- **修复建议**：汇总行改用本实例 `$workerStem`（与 stop/status 的既有写法一致）。

### D3（非阻断，低）`stop.ps1` 的 `$WebPort`/`$webPort` 大小写冲突

- **现象**：停止非默认实例时端口确认行打印 `8200/8201/8202/0 已全部释放`（不是 `…/5173` 或用户传入的 `-WebPort`）。
- **根因**：PowerShell 变量大小写不敏感；`stop.ps1` 中 `$webPort = if ($PublicPort -eq 8100) { $WebPort } else { 0 }` 实际**覆盖了参数 `$WebPort`**，后续确认循环读到的就是 0。
- **影响**：确认信息失真；对非默认实例（尤其自带前端、`-WebPort` 非默认时）`-WebPort` 参数被静默忽略，端口兜底清理与确认都不覆盖该端口（若前端不是由脚本启动、无 `web-<port>.pid`，会残留）。
- **修复建议**：局部变量改名（如 `$frontendPort`），确认循环对非默认实例使用 `0`/跳过并在输出里注明"前端按 PID 文件停止，不做端口兜底"。

### D4（非阻断，低）`status.ps1` 的两处跨实例/噪音问题

1. **跨实例前端误报**：默认实例在跑时执行 `status.ps1 -PublicPort 8200 -InternalPort 8201 -McpPort 8202`，输出 `前端 5173 UP HTTP 200` —— 那是**默认实例**的前端；该 8200 实例是用 `-NoFrontend` 起的，根本没有前端。末尾"未运行"列表也因此不含前端。
2. **健康状态下也输出 stderr 段**：`status.ps1` 扫描 `backend/var/logs/*.err.log` 全部非空文件 → uvicorn 默认把 INFO 写 stderr，所以任何健康实例都会让该段有内容；还会把**已停止实例**的旧 `*-8200.err.log` 一并打印。这与 task 检查项 7 的"无 stderr 噪音"不符（信息本身无害，但输出噪音大）。
- **修复建议**：① 非默认实例的前端状态按 `web-<PublicPort>.pid` +（可选）`-WebPort` 判定，默认 5173 只在默认实例使用；② stderr 段只显示 `ERROR/WARN/CRITICAL/Traceback` 关键行（或仅当前实例 stem 的日志），其余归为"日志正常"。

---

## 4. 文档与实际行为的差异清单（哪怕只是措辞）

| # | 文档位置 | 文档说法 | 实际/代码 | 类型 |
| --- | --- | --- | --- | --- |
| D5（已修） | `docs/STARTUP.md` §2.1 `-ResetDb` | "**清空演示库 cca 全部表**后重建迁移，再写种子（**默认不写，除非同时 `-SkipSeed`**）" | 代码：`-ResetDb` 只影响迁移前 `downgrade base`；**种子默认会写**，只有 `-SkipSeed` 才跳过（`start.ps1` §4/6 逻辑）。括号内描述与事实相反 | **事实错误（措辞）** |
| D6（已修） | `docs/STARTUP.md` §5/§7 | 只给出无参 `status.ps1`；§7 的多实例示例只有 start/stop | `status.ps1` 支持 `-PublicPort/-InternalPort/-McpPort/-WebPort`（我实测用它巡检 8200 实例），文档未说明 | 缺文档 |
| D7（已修） | `docs/STARTUP.md` §7 边界 2 | "两套实例同时跑时务必用不同端口 + **不同库**" | 脚本**没有数据库参数**；第二套实例复用 `backend/.env` 的 `DATABASE_URL`（我实测两套都连 `cca`）。要换库只能手改共享的 `.env`，且会影响后续启动，文档未说明操作方法 | 表述不完整 |
| D8（已修） | `backend/README.md` §1 测试库 | 列出 `cca_test_core/knowledge/assistant/release` | 实际磁盘上还有 `cca_test_lead`（Lead 全量验证用）；`docs/PHASE-STATUS-002.md` §6 已列出 lead，两份文档不一致 | 清单不同步（`1d4ce11` 已补） |
| R1 | `docs/STARTUP.md` §2.1 CI 注记 | 声称「直接 `pwsh -File start.ps1` 在管道里能正常返回（约 11 s）；经 `.cmd` 入口再被管道捕获会一直等」 | 实测：`pwsh -File start.ps1 -NoFrontend` **无下游缓冲**时 13s 返回 exit 0 ✓；但加 `| Out-String`（需 EOF 缓冲）**>50s 不返回**，`.cmd` 同样；重定向到文件时两者都 13s 返回。真实规则是「调用方是否按 EOF 缓冲」，不是 ps1/cmd 之别 | 措辞需精确（低危，不阻断） |
| R2 | `docs/STARTUP.md` §8 日志与 PID | 只列 `*.pid` / `*.out.log` / `*.err.log` | 新增 `backend/var/run/instance-<公共端口>.db`（记录实例当前库名；start 第 326 行写、stop 第 118 行删；实测 `instance-8100.db=cca`、`instance-8200.db=cca_alt`） | 建议补一行说明（极低危） |
| R3 | 交付状态（流程） | task-11 复验时 `git status` 本应只有报告文件 | 实际 `scripts/start.ps1|status.ps1|stop.ps1` 各有未提交新增（`+9` 行，`instance-<port>.db` 标记）；即**发布对象 ≠ 提交 `1d4ce11`**。逐行核对：不触及 D2/D1/D3/D4 修复逻辑，属加载项（我实测已通过）；但报告口径需注明，建议把该补丁一并提交并给出新 sha | 流程/口径（不阻断功能） |
| D9 | 根 `README.md` / `docs/STARTUP.md` 头部 | "另有 `.cmd` 双击入口" | `.cmd` 存在，但 LF 换行导致双击时先报错（D2） | 与事实不符（缺陷导致） |
| D10 | `docs/STARTUP.md` §2.2 | 启动成功表 6 行（含 Worker UP） | 默认实例一致 ✅；非默认实例只有 5 行且 Worker 行可能误报（D1） | 场景未覆盖 |
| D11 | `docs/STARTUP.md` §2 表格 2/6 | ".env 缺失则由 .env.example 生成" | 与代码一致 ✅（`backend/.env` 已存在时沿用） | 无差异 |
| D12 | `docs/STARTUP.md` §6.3 & 根 README 端口表 | "Vite 只绑 `localhost`（`::1`），`127.0.0.1` 会拒连；探活用 `localhost`" | 实测 `localhost:5173` 200、`127.0.0.1:5173` `ConnectError` ✅ | 无差异（修复已生效） |
| D13 | `docs/STARTUP.md` §7 边界 1 | "`stop.ps1 -PublicPort 8200` 不会按 5173 清理前端，只按 PID 停自己那套" | 实测正确 ✅（停 8200 后默认 5173 仍 UP、前端 200） | 无差异（修复已生效） |
| D14 | `docs/STARTUP.md` §8 | "日志按次覆盖（不追加）" | 实测 `Start-Process` 重定向确为覆盖（同一实例重启后日志只剩本次进程行）✅；但旧实例日志文件不会随停止删除（D4 噪音来源） | 描述正确，可补一句 |

---

## 5. 未执行 / 限制（如实登记）

1. **`-ResetDb` 未执行**（会清空演示库，task 明确禁止）；仅代码审阅 + D5 文案核对。
   - 第 2 轮补：D7 已用**一次性库 `cca_alt`** 实测（建库 → `$env:DATABASE_URL` → 起 8200 → 验证 → 停 → DROP），演示库 `cca` 未受影响。
2. **`-Mock` 未执行**（需起前端并占 5173；代码路径明确 `VITE_USE_MOCK=true`，本轮未做 UI mock 回归）。
3. **`-SkipInstall` 未执行**（需删除/改造 `web/node_modules`，属破坏性操作）。
4. **`-WaitSeconds` 未单独压测**（默认 90s 内全部就绪；代码路径审阅）。
5. **"端口被非本项目进程占用"场景未构造**（代码审阅：`start.ps1` 会把任何监听 8100 的进程当作"已在运行"并信任其 `/health`；`stop.ps1` 会强杀占用目标端口的任意进程）。这是设计取舍，**文档未提示"会杀非本项目进程"的风险**，建议补一句。
6. **`start.ps1` 在"stdout 被父进程管道捕获"时不返回**：本轮用本 agent 的管道捕获执行时，脚本自身完成（表已打印、服务已起）但调用方等到超时；改用 `cmd /c "… > 文件"` 后正常返回 `EXITCODE=0`。普通交互终端不受影响，但文档把 `-NoFrontend` 标为"CI 常用"，CI 里 stdout 通常是管道 —— 建议文档补一句"CI 中请重定向输出或后台运行"。**未列为阻断**（只影响 CI 场景）。
7. **`.cmd` 缺陷修复后需复验**：替换为 CRLF 后我应在真实 cmd 下复跑 start/stop/status 三个 `.cmd`（约 2 分钟）。
8. 未跑全量 pytest（按项目策略与 task 约束）。

---

## 6. 最终判定

**PASS（`1d4ce11`）** —— 首轮的 1 个阻断项（D2 `.cmd` 换行）与 7 项非阻断缺陷/差异（D1、D3、D4、D5、D6、D7、D8）全部闭环并通过复验；仅剩 **2 条低危文档措辞建议（R1、R2）**，均不阻断发布。

- **第 1 轮（`eb613e1` 未提交交付）判定 FAIL**：`.cmd` 三件套 LF 换行导致真实 cmd 下报 `'d' is not recognized…`（D2）；另有 D1/D3/D4 脚本缺陷与 D5–D8 文档差异。
- **第 2 轮（`1d4ce11`）复验全部 PASS**（逐条证据见 §8）：
  - D2：`.cmd` → CRLF（CR=6/LF=6）+ `.gitattributes`（`git check-attr` 确认）；三个 `.cmd` 真实入口实跑：无 `'d'`、无 banner，`stop/status` exit 0，`start` 13s 完成且六行全 UP（health ok / 前端 200 / SSE succeeded）。
  - D1：默认实例停止时起 8200 实例，汇总 `Worker … UP`，pid = `worker-8200.pid`（不再取默认 `worker.pid`）。
  - D3：`stop.ps1 -PublicPort 8200 …` 输出 `8200/8201/8202 已全部释放`（无 `/0`、无 5173），默认实例全 UP。
  - D4：`status.ps1 -PublicPort 8200 …` → `前端 - DOWN 该实例未起前端`、日志段 `无 ERROR/Traceback（仅有 INFO 级启动日志）`，不再串默认 5173。
  - D5/D6/D7/D8：文档与代码/实测一致（D7 用 `cca_alt` 实测通过）。
  - 第 9 项：`-SkipSeed` 汇总打印「演示账号：未写入（-SkipSeed）」。
- **剩余非阻断差异**：R1（CI 注记把 ps1/cmd 阻塞差异绝对化，应改为「取决于调用方是否按 EOF 缓冲」）、R2（§8 未列 `instance-<port>.db` 标记文件）、R3（复验时工作树比提交多 9 行未提交脚本补丁；见 §1，建议一并提交并给新 sha；不影响 D2/D1/D3/D4 的 PASS 判定）。建议发布前一并补，不影响合并。
- 本轮未发现新的功能缺陷。

---

## 7. 现场与数据完整性

- 收尾状态：`8100/8101/8102/5173/8200/8201/8202` 全部 **free**；`backend/var/run` PID 文件 **0**；`app.entrypoints` 进程 **0**；MySQL 容器 `cca-mysql` **Up（未停）**。
- 演示库 `cca`：验证前 / 验证后均 **24 表 / 17 用户**；种子执行均为 `created:false`（幂等，未新增/未删除数据）。
- `backend/.env` 未被修改（mtime 仍为交付前 9:53）；我未写任何项目文件（除本报告）。

验证者：`qa-verifier`，2026-10-24。

---

## 8. 第 2 轮复验证据（`1d4ce11`，逐条命令与输出摘要）

> 复验范围按 Lead 指定：D2 三入口实跑；D1/D3/D4 用 8200 实例 + `status.ps1 -PublicPort 8200 …`；D5–D8 只读代码/文档对照；D7 用一次性库。其余首轮结论（真实链路、幂等、巡检字段、负向）不重跑。

### D2 · `.cmd` 三入口（阻断项闭环）

- 换行与属性：`start.cmd bytes=196 CR=6 LF=6`；`stop.cmd 193/6/6`；`status.cmd 199/6/6`；`.gitattributes` = `*.cmd text eol=crlf` / `*.ps1 text eol=lf`；`git check-attr` → `scripts/start.cmd: eol=crlf`、`scripts/start.ps1: eol=lf`。
- `cmd /c "call ""scripts\stop.cmd"""` → `EXITCODE=0 elapsed=4s`；14 行输出；`has_d_error=False  has_banner=False`；端口确认 `8100/8101/8102/5173 已全部释放`。
- `cmd /c "call ""scripts\status.cmd"""` → `EXITCODE=0`；`has_d_error=False  has_banner=False`；容器/库/服务表正常输出。
- `cmd /c "call ""scripts\start.cmd"""` → `EXITCODE=0 elapsed=13s`；`has_d_error=False  has_banner=False`；六行汇总全 UP；`health=ok`、`frontend=200`；随后 SSE：`['status','status','tool_start','tool_end','token','done']`，`done.state=succeeded`。
- 结论：**PASS**（首轮三类症状全部消失）。

### D1 · Worker 行按实例（unmasked）

- 条件：默认实例已 `stop.ps1` 停止；仅起 8200 实例（`-NoFrontend -SkipSeed`）。
- 汇总表：`Worker     后台轮询（无端口）                  UP`（首轮此场景为 DOWN）；`worker-8200.pid=6456` 且进程存活；`status.ps1 -PublicPort 8200` → `Worker - UP PID 6456`。
- 结论：**PASS**。

### D3 · `stop.ps1` 非默认实例端口确认

- 条件：默认实例在跑（8100/8101/8102/5173 UP）；停 8200 实例。
- 输出：`[OK]   8200/8201/8202 已全部释放`；断言 `no '/0'` = True、`no 5173 in confirm` = True。
- 停后默认实例：8100/8101/8102/5173 全 UP；`default health=ok`、`default frontend=200`；8200–8202 free。
- 结论：**PASS**。

### D4 · `status.ps1` 非默认实例

```
公共 API   8200 UP   health=ok（process=ok database=ok）
内部 API   8201 UP   只回环
MCP server 8202 UP   私有 Streamable HTTP
Worker        - UP   PID 6456
前端          - DOWN 该实例未起前端
日志：无 ERROR/Traceback（仅有 INFO 级启动日志）
```

- 断言：`has '该实例未起前端'=True`；`no cross 5173 UP row=True`；exit 0。首轮两处问题（跨实例 5173 误报、健康状态刷 stderr）均消失。
- 结论：**PASS**。

### D5/D6/D8 · 文档（只读）

- D5：`docs/STARTUP.md` 第 72 行 `-ResetDb` = \u201c清空演示库 `cca` 全部表后重建迁移，然后照常写种子；要跳过种子再加 `-SkipSeed`\u201d → 与 `start.ps1` §4（`SkipSeed` 才跳过）一致 ✓
- D6：第 78 行 \u201c`stop.ps1` 与 `status.ps1` 接受同样的四个端口参数\u201d ✓
- D8：`backend/README.md` 第 22 行测试库清单含 `cca_test_lead` ✓
- 结论：**PASS**。

### D7 · 多实例换库（一次性库实测）

- 建库 `cca_alt`（utf8mb4_0900_bin）→ exit 0。
- `$env:DATABASE_URL=\".../cca_alt?...\"; pwsh -File scripts\start.ps1 -NoFrontend -SkipSeed -PublicPort 8200 -InternalPort 8201 -McpPort 8202` → `EXITCODE=0`。
- 断言：WARN `使用进程环境变量 DATABASE_URL（覆盖 backend/.env 的值）`；`演示库：cca_alt`；`instance-8200.db=cca_alt`（**该 marker 属 R3 未提交补丁**）；`8200 health=ok`；`cca_alt` **24 表**；`cca` **24 表/17 用户**不变。核心「env DATABASE_URL 生效」由 `cca_alt` 24 表独立证明，不依赖 marker。
- 清理：`stop.ps1 -PublicPort 8200 …` → `8200/8201/8202 已全部释放`；`DROP DATABASE cca_alt` → 不存在；`cca` 仍 24 表/17 用户。文档 §7 步骤与实测完全一致。
- 结论：**PASS**。

### 第 9 项 · `-SkipSeed` 汇总

- 输出：`演示账号：未写入（-SkipSeed）`（首轮为固定打印 demo 账号）→ **PASS**。

### 第 10 项 · CI / 管道说明（部分成立 → R1）

- `pwsh -NoProfile -File scripts\start.ps1 -NoFrontend -PublicPort 8200 …`（工具直接捕获、无下游缓冲管道）→ **EXITCODE=0，13s 返回**，三端口 UP。
- 同一命令加 `| Out-String`（需要 EOF 的缓冲管道）→ **>50s 未返回**（服务已起；`stop.ps1` 停服务后才结束）。
- `cmd /c "scripts\start.cmd …" | Out-String` → 同样 **>50s 未返回**；`cmd` 重定向到文件 → 13s 返回。
- 结论：文档 \u201cps1 正常返回 / cmd 阻塞\u201d 的二分不准确；实际取决于调用方是否按 EOF 缓冲。建议改写为：\u201c若调用方按 EOF 缓冲管道输出（如 `| Out-String`、`| Select -Last`），任何入口都会等到后台服务退出；CI 请重定向到文件或后台运行。\u201d → **R1（低危，不阻断）**。

### 环境与数据（复验轮收尾）

- 收尾：`8100/8101/8102/5173/8200/8201/8202` 全 free；`backend/var/run` PID/标记文件 0；`app.entrypoints` 进程 0；`cca-mysql` Up（未 `-StopDocker`）。
- `cca`：24 表 / 17 用户（未变）；`cca_alt` 已 DROP；`backend/.env` 未改；未跑全量 pytest、未 `-ResetDb`。
