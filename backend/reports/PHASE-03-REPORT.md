# Phase 3 · 助手执行链路报告（CCA-PHASE-03-REPORT）

- 分支 / 工作树：`phase/03-assistant` / `.worktrees/p03-assistant`
- 基线：Phase 1 合并后的 `dev`（本报告基于 `bfd0725`、`615624d`、`65d50e5` 三次合入后的工作树）
- 车道：L3 backend-assistant（只写 assistant 模块 + model/mcp 适配器 + `entrypoints/{internal_api,mcp_server}` + 助手测试）
- 测试库：`cca_test_assistant`（真 MySQL 127.0.0.1:33061，**未使用 SQLite**）
- 报告日期：2026-10-23

---

## 1. 交付范围（A1–A9）

| 任务 | 交付 | 状态 |
| --- | --- | --- |
| A1 | `ModelGateway` 契约 + `DeterministicProvider`（同一输入同一动作序列）+ 真实 Provider 占位 | ✅ |
| A2 | 双跳委派：`aud=cca-mcp` → `/delegations/exchange` → `aud=cca-internal`；HS256、≤30s、jti 一次性 | ✅ |
| A3 | 内部 API 四端点（兑换 + 三工具），身份固定为委派用户、读完整日期范围、`isError` 语义 | ✅ |
| A4 | MCP Server（mcp 2.3.0 `MCPServer` + `streamable_http_app`），三工具、严格 schema、仅回环 | ✅ |
| A5 | 接受事务：`client_request_id` 去重、同会话单活动轮、5 个 AI 容量槽（DB 时间租约） | ✅ |
| A6 | Runner：6 决策 / 10 工具 / 60s、fence、30s 租约 + 10s 续租、取消、启动回收 `SERVICE_RESTARTED` | ✅ |
| A7 | SSE 六类事件 + `seq` + `tool_call_id` 配对 + 终态唯一 + 心跳 + 背压；`/chat/*` 三端点 | ✅ |
| A8 | 草稿（不可变版本 + 预分配 operation_id）、`direct_instruction` 许可、对话内保存、同轮槽上限、取消竞态 | ✅ |
| A9 | 车道测试 58 passed；本报告 | ✅ |

**与 Phase 1 的边界**：未修改 `shared/**`、`config.py`、`public_api.py`、`migrations/**`、其他模块与 `web/**`。
合并 `dev` 时对 `assistant/router.py`、`assistant/internal_router.py` 的冲突**保留本车道实现并补 `responses=ERROR_RESPONSES`**（Phase 1 T09 约定）。

---

## 2. 命令与证据

### 2.1 车道 T1（定向全车道）

```powershell
$env:DATABASE_URL="mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_assistant?charset=utf8mb4"
$env:CCA_ENV="test"
.venv\Scripts\python.exe -m pytest backend/tests/test_assistant_provider.py `
  backend/tests/test_assistant_api.py backend/tests/test_assistant_runner.py `
  backend/tests/test_assistant_save.py backend/tests/test_mcp_server.py -q
```

```
58 passed in 185.96s (0:03:05)
```

| 测试文件 | 用例 | 覆盖 |
| --- | --- | --- |
| `test_assistant_provider.py` | 18 | Provider 确定性、日期锚点（今天/明天/本周/下周）、资料/规定/计划意图、空证据拒答、流式分块、工具白名单 |
| `test_assistant_api.py` | 10 | SSE 六类事件 + `jsonschema` 逐事件校验、seq 连续、工具配对、终态唯一、去重 409、单活动轮 409、容量 429/释放、状态归属、取消幂等/运行中取消、422/401 |
| `test_assistant_runner.py` | 5 | 决策预算、工具预算、60s 截止（`FixedClock`）、租约过期回收、fence 被接管后旧 runner 不发终态 |
| `test_assistant_save.py` | 17 | 直接指令判定矩阵、明确保存恰一份计划、疑问/否定只留草稿、取消后保存失败零新增、同轮第二份草稿 `SAVE_LIMIT_REACHED`、同键 `existing`、跨用户草稿 404、scope 不足 403 |
| `test_mcp_server.py` | 8 | 真实回环 uvicorn（内部 API + MCP）+ SDK 客户端：initialize / list_tools 契约 / 三工具真实双跳调用 / 无凭据 / 错 audience / 过期 / jti 重放 / 未知参数 -32602 / 浏览器 Origin 拒绝 |

### 2.2 可启动性

```powershell
uvicorn app.entrypoints.internal_api:app --host 127.0.0.1 --port 8101
python -m app.entrypoints.mcp_server          # 127.0.0.1:8102/mcp
```

实测：两条命令启动后端口 8101 / 8102 均可建立 TCP 连接，停止进程后端口释放。测试内亦用同一路径起真实回环服务（`tests/assistant_support.serve_app`）。公共 API 8100 由 Lead 托管的联调服务占用，本车道未触碰。

### 2.3 SSE 冒烟脚本（交给 Phase 4）

```python
import asyncio, httpx, json

async def main():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8100", timeout=30) as client:
        login = await client.post("/api/v1/auth/login",
                                  json={"account": "student_demo", "password": "demo1234"})
        token = login.json()["data"]["access_token"]
        body = {"client_request_id": "smoke_001", "message": "明天有课吗"}
        async with client.stream("POST", "/api/v1/chat/stream", json=body,
                                 headers={"Authorization": f"Bearer {token}"}) as r:
            event, data = None, []
            async for line in r.aiter_lines():
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data.append(line.split(":", 1)[1].strip())
                elif line == "" and event:
                    print(event, json.loads("".join(data)))
                    event, data = None, []

asyncio.run(main())
```

---

## 3. 确定性 Provider 行为说明（非生产 AI）

- 类型：`app.adapters.model.deterministic.DeterministicProvider`；同一 `message + 上下文状态` 必然产出同一动作序列。
- 触发关键词（集中在该模块，便于行为评测）：
  - 课表：`课表 / 有课 / 上课 / 课程安排 / 几点上课 / 在哪上课`（日期词：`今天/今日/今晚`、`明天/明日`、`本周/这周/一周`、`下周`）；
  - 资料：`资料 / 课件 / 依据 / 要求 / 预习 / 评分 / 规定 / 实验 / 作业要求 / 考试范围 / 成绩 / 大纲`；
  - 计划：`计划 / 制定 / 规划 / 复习安排 / 学习安排 / 安排学习 / 复习`；
  - 保存候选：`保存 / 存下来 / 存到 / 记录下来 / 记到我的计划 / 帮我存 / 加入计划`（**仅候选**）。
- 日期锚点：本轮 `accepted_at` + `Asia/Shanghai`；`明天` → 当日单天，`本周` → 周一至周日，`下周` → 下周一至周日，仅“课表/有课” → 今天。
- 数据依赖顺序：课表 → 资料 → 草稿 → 答案（FR-CHAT-006）；无证据且属规定类问题 → 明确“依据不足”；普通建议标注“一般学习建议（非课程资料规定）”。
- 边界：provider 不接触用户身份/会话/许可；`save_candidate` 只是候选，是否签发许可由 `classify_direct_instruction` + 服务端保存事务决定。
- 真实模型：`RealProviderAdapter` 为占位（TBD-04 未冻结），未配置时显式 `MODEL_UNAVAILABLE`，不会静默回退到确定性 Provider 冒充真实 AI。

---

## 4. MCP 2.3.0 实测结论

- 入口：`from mcp.server.mcpserver import MCPServer`（**不是** 1.x `FastMCP`）；HTTP 用 `streamable_http_app(streamable_http_path="/mcp", transport_security=...)`，`run_streamable_http_async(host="127.0.0.1", port=8102, ...)`。
- 工具注册：`@server.tool(name=...)`；工具函数接收 `Context` 读取传输头（`ctx.headers`）拿 `X-CCA-Delegation`。
- 客户端：`mcp.client.streamable_http.streamable_http_client(url, http_client=create_mcp_http_client(headers=...))` + `mcp.ClientSession.initialize()/list_tools()/call_tool()`；`list_tools()` 返回 `ListToolsResult`（取 `.tools`）。
- 输入 schema：由函数签名自动生成；本车道在注册后**收紧**为契约形状（`additionalProperties:false`、去 `title/default`、补 `required:[]`），并用 `tools/call` 中间件在协议层拒绝未声明参数（JSON-RPC `-32602`），避免“伪造 student_id 被静默忽略”。
- 输出 schema：`structured_output`（pydantic 输出模型）自动生成；业务失败返回 `CallToolResult(isError=True, structuredContent={code,message,request_id})`，与协议错误（JSON-RPC）严格分开。
- 传输安全：`TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=["127.0.0.1:*","localhost:*"])`；浏览器 `Origin` 请求实测被拒（非 200）。
- **已知偏差（登记）**：`get_my_schedule` 的可选日期在运行态 schema 为 `anyOf[date, null]`（设计包为纯 `date`、键可缺省）。语义更严/等价（允许显式 null 表示“不传”），未放宽任何可伪造语义。输出 schema 保留 `$defs` 形态（设计包用 `$ref` 组件），字段集合与必填集合逐项一致。

---

## 5. 双跳委派与内部 API

- claims：`iss=cca-api / aud / sub / session_id / auth_version / request_id / conversation_id / scope / fence / iat / exp / jti`。
- `aud` 固定 `cca-mcp`（API→MCP）与 `cca-internal`（MCP→内部工具）；HS256 开发密钥来自 `settings.delegation_signing_key`（TBD-03 未冻结，登记）。
- 有效期 `min(30s, 本轮 deadline)`；每次工具调用签发**新 jti**；兑换端点消费 jti，重放返回 401。中间服务不得延长有效期（`exp-iat > 31s` 直接拒绝）、不得放大 scope。
- 内部端点每次复核：用户 `enabled`、`auth_version`、`AuthSession`（未撤销/未过期）、`ChatRequest` 归属/会话/会话绑定/fence/状态/取消/截止；保存另核 true 许可。
- 用户原始 Bearer **不进入 MCP**，也不进入工具参数；浏览器无法直连（仅回环 + Host/Origin 校验）。

---

## 6. 生命周期与竞态语义（实测）

| 场景 | 行为 |
| --- | --- |
| 重复 `client_request_id` | 409 `REQUEST_ALREADY_EXISTS` + `details.request_id/status_endpoint`（不重放模型） |
| 同会话已有运行轮 | 409 `CHAT_IN_PROGRESS` + 原请求入口 |
| 5 槽耗尽 | 429 `CAPACITY_LIMITED`（接受事务回滚）；终态/回收释放槽 |
| 预算 | 决策超限/工具超限 → `failed/CALL_LIMIT_REACHED`，`model_calls`/`tool_calls` 与事件一致 |
| 60s 截止 | `failed/EXECUTION_TIMEOUT`（注入时钟验证） |
| 取消（运行中） | 边界检查持久 `cancel_requested` → `done(state=cancelled, reason=USER_CANCELLED)`，恰一次 |
| 取消（已终态） | `accepted=false` + 当前状态，幂等 |
| 取消 vs 保存 | 保存事务锁内见 `cancel_requested` → `SAVE_NOT_AUTHORIZED`，**零新增**；先提交的保存不可撤回 |
| 同轮换键 | 第二份草稿保存 → `SAVE_LIMIT_REACHED`，计划仍只有 1 份 |
| 重复保存同键 | 同草稿版本重复保存 → `existing`，同 `plan_id`，不重复计数 |
| 进程丢失 | 租约过期扫描 → `failed/SERVICE_RESTARTED`、fence+1、释放槽与活动会话；旧 runner 下一边界退出且**不发终态**（fence 校验证明） |

---

## 7. 未验证项 / 已知缺口（如实登记）

1. **真实大模型与 Embedding**（TBD-04 未冻结）：仅确定性 Provider；未做真实 AI 质量评测。真实 Adapter 为显式失败的占位。
2. **跨进程崩溃物理验证**：用 DB fence + 租约 + 回收语义验证，未做真实多进程 kill -9 演练；`SERVICE_RESTARTED` 为模拟回收。
3. **jti 重放注册表为进程内**：单进程/单实例验证；多进程部署需共享存储（Redis/DB），未实现，Phase 5 发布说明需列。
4. **检索为固定 EvidenceSet stub**：Phase 2 未合并；`knowledge.service.search` 出现后自动切换（`assistant/retrieval.py`）。切换后需补“真实 EvidenceSet → SSE 引用 → citations 展开”端到端用例。
5. **背压慢连接**：实现了 64 块/2s/连接关闭语义，但未做真实慢消费者压测（确定性轮次事件量 < 128）。
6. **前端消费**：Phase 4 负责；本报告给出 SSE 冒烟脚本与事件 schema 校验方法。
7. **`student_id` 语义**：`get_my_schedule` 输出 items 含 `student_id`（契约要求），但输入不接受目标用户；已用协议层 -32602 验证伪造参数被拒。
8. **报告/答案引用标记过滤**：确定性 Provider 不输出数字引用标记；`done.citations` 只来自工具返回的权威 references。真实模型接入后需补“模型伪造引用标记过滤”用例。

---

## 8. 与契约的差异与裁决记录

| 项 | 设计包 | 实现 | 裁决 |
| --- | --- | --- | --- |
| MCP 可选日期入参 | `type: string, format: date`（可缺省） | `anyOf[date, null]` | 更严/等价，不放宽可伪造语义（Lead 已确认登记） |
| MCP 输出 schema 形态 | `$ref` 组件 | 内联 `$defs` | 字段/必填集合一致，前端不直接消费 MCP |
| 中途认证失效 | 只发通用 `error`，不带私有标识 | 工具返回 `AUTH_REQUIRED/SESSION_EXPIRED` → 终态 error 不含 `plan_id/operation_id` | 一致 |
| 保存失败后仍可继续回答 | 工具失败不伪成功 | `tool_end(success=false, code)` + 终态按取消/继续规则处理 | 一致 |

---

## 9. 代码位置

```
backend/app/adapters/model/{gateway,deterministic,real}.py   ModelGateway / 确定性 Provider / 真实占位
backend/app/adapters/mcp/{delegation,client}.py              双跳委派 / MCP 与内部 API 客户端
backend/app/modules/assistant/contracts.py                   端到端 schema（OpenAPI/SSE/MCP）
backend/app/modules/assistant/accept.py                      接受/去重/容量/状态/取消/回收
backend/app/modules/assistant/runner.py                      预算/fence/终态/事件编排
backend/app/modules/assistant/sse.py                         EventChannel + SSE 写出器
backend/app/modules/assistant/drafts.py                      直接指令判定 + 草稿落库
backend/app/modules/assistant/save.py                        direct_instruction 保存事务
backend/app/modules/assistant/{schedule_tool,retrieval}.py   三工具的服务端实现（检索可切真实）
backend/app/modules/assistant/{router,internal_router}.py    公共 /chat/* 与 /internal/v1/*
backend/app/modules/assistant/runtime.py                     runner 注册表/事件通道/恢复扫描
backend/app/entrypoints/{internal_api,mcp_server}.py         内部 API 8101 / MCP 8102
backend/tests/{assistant_support,test_assistant_*,test_mcp_server}.py
```

---

## 10. 交接

- **Phase 4（前端联调）**：`POST /api/v1/chat/stream` 事件序列（含 `answer_block_id`、`draft_id/version`、`plan_id/operation_id`）；`GET /chat/requests/{id}` 轮询；`POST /chat/requests/{id}/cancel`；`GET /chat/requests/{id}` 在写未知时返回 `pending/recovering`（Phase 1 写入状态接口）。
- **Phase 5（全量验证）**：把本报告 §6 的竞态用例并入全量矩阵；补齐 §7 的未验证项；`backend/tests/test_contract_core.py` 中 `/chat/*` 三条 501 断言需由 backend-core 改为真实断言（本车道不改该文件）。
