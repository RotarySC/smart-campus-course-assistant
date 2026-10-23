# Phase 2 · 资料与知识链路（车道 K）交付报告

- 分支 / 工作树：`phase/02-knowledge` / `.worktrees/p02-knowledge`
- 基线：Phase 1 最终合入 `dev`（`65d50e5`），本车道提交：
  - `9e1ffec` K1–K6 存储/上传/Worker/解析/向量/发布事务
  - `57cac59` K7 检索/EvidenceSet 测试
  - `ef78e1a` K8/K9 文档管理 + 引用端点（含 `uq_document_one_active` 切版顺序修复）
  - `875e242` K3/K4/K5 租约-解析-向量测试
  - `K10` 本报告 + 契约/Worker CLI 测试
- 环境：Windows / Python 3.12.10（`<repo>/.venv`）/ MySQL 8.4 容器 `127.0.0.1:33061`
- 数据库：**只连 `cca_test_knowledge`**；测试与手动验证均使用真实 MySQL + 真实文件落盘。

---

## 1. 任务完成情况（K1–K10）

| 任务 | 内容 | 证据 |
| --- | --- | --- |
| K1 | `FileStore` 本地卷（上传隔离区/原件/attempt 前缀；键校验拒绝路径分隔符与穿越；流式计量） | `app/adapters/filestore/local.py`；`test_knowledge_upload.py`（11 用例） |
| K2 | `POST /admin/document-batches` multipart 202：校验 1–10 文件/20MiB/50MiB/后缀与内容签名/同名策略 → 单事务建 batch + documents + versions + background_tasks（persist 每文件 + publish）+ audit/outbox；事务失败补偿删暂存 | 同上；204 行文档/任务数一致断言 |
| K3 | Worker 租约：`FOR UPDATE SKIP LOCKED` 领取、30s 租约/10s 心跳、owner+fence+lease 三重 CAS、过期回收 `retry_wait`、2/4/8/16s ±25% 退避、最多 5 次、**丢租约不发布**；`--once` 单次排空 | `app/modules/knowledge/tasks.py`；`test_worker_lease.py`（4 用例） |
| K4 | 解析：txt/md（utf-8/utf-8-sig）、pdf（pypdf 文本层，逐页页码）、docx（段落序号）；空文本/加密/损坏明确失败码；固定窗口+重叠分块；`extracted-text` + `chunk-manifest` 落盘 | `app/adapters/parser/document_parser.py`；`test_knowledge_parse_vector.py` |
| K5 | 确定性 SHA-256 Embedding（默认 64 维、L2 归一、中英 token/2-gram）；本地 VectorStore（命名空间 `corpus_space/doc/version/task/fence`、幂等 upsert、按命名空间/前缀删除、**收敛屏障拒绝迟到写入**） | `app/adapters/embedding/*`、`app/adapters/vector/local.py`；同名测试 |
| K6 | 整批发布事务：锁顺序 corpus→batch→documents→versions→attempts(read)→tasks→audit/outbox；校验批次 processing/文档数/全版本 ready/attempt settled/命名空间匹配/索引可检索；一次切换 visibility=shared + active 指针 + batch=published + revision++；任一文件失败 → compensating → 清理任务 → failed（其他批次不受影响）；发布失败同任务重试；重建完成切版（旧版 retired、旧引用撤销、清理旧产物） | `tasks.py`；`test_knowledge_publish.py`（4 用例） |
| K7 | `knowledge.search(ctx, SearchQuery) -> EvidenceSet`：读 corpus revision/vector_space → 全库为空 `empty(corpus_empty=true)` → 候选 → 关系库权威复核（batch published/shared/未删/active 版本/version active/vector_space 一致/引用未撤销）→ 每文档一版 → 稳定 `reference_id`；revision 变化重试 | `app/modules/knowledge/service.py`；`test_knowledge_search.py`（6 用例） |
| K8 | 8 端点中的 7 个管理端点：列表分页/名称/状态、文本预览 offset/limit/next_offset；重建（Idempotency-Key + expected_version、DOCUMENT_BUSY、同键幂等、旧版持续可用→切版）；删除（202 立即不可见、revision++、引用立即 410、清理任务）；cleanup-retry（不恢复可见性）；引用端点 | `service.py`、`router.py`；`test_knowledge_manage.py`、`test_knowledge_citations.py`（10 用例） |
| K9 | `GET /citations/{id}`：认证 → 引用未撤销 + 文档 shared/未删 + 版本 active/当前 + 批次 published；失效/未知 → 410 `CITATION_UNAVAILABLE`；响应不含存储键 | 同上；`test_knowledge_citations.py` |
| K10 | 车道 T1 + 契约测试 + Worker CLI 冒烟 + 本报告 | `test_knowledge_contract.py`（3 用例，运行态 OpenAPI 与设计包 components 对齐） |

## 2. 验证命令与结果

```powershell
# 环境（仅知识车道测试库；真实 MySQL + 真实文件）
$env:DATABASE_URL="mysql+aiomysql://root:cca_dev_root@127.0.0.1:33061/cca_test_knowledge?charset=utf8mb4"
$env:CCA_ENV="test"
cd <worktree>/backend
pytest tests/test_knowledge_upload.py tests/test_knowledge_publish.py `
       tests/test_knowledge_search.py tests/test_knowledge_manage.py `
       tests/test_knowledge_citations.py tests/test_knowledge_contract.py `
       tests/test_knowledge_parse_vector.py tests/test_worker_lease.py -q
# → 48 passed in 171.38s

python -m app.entrypoints.worker --once --max-tasks 5
# → {"owner": "...:pid:...", "processed": 0, "recovered_leases": 0, "counters": {}}

python -m compileall -q app   # exit 0
```

> 未跑全量 `pytest`（用户约束：全量只在 Phase 5 跑一次）。测试 basetemp 指向工作树外
> （`.worktrees/.pytest-p02`），仓库内不产生 pytest 临时目录。

## 3. 接口与契约

| 方法与路径 | 成功码 | 响应 data |
| --- | --- | --- |
| POST `/api/v1/admin/document-batches` | 202 | `Batch`（batch_id/state/published/documents/tasks[/error_code]） |
| GET `/api/v1/admin/document-batches/{id}` | 200 | `Batch` |
| GET `/api/v1/admin/documents` | 200 | `DocumentPage`（items/page/page_size/total） |
| GET `/api/v1/admin/documents/{id}/text` | 200 | `DocumentText`（document_id/version_id/offset/next_offset/text） |
| POST `/api/v1/admin/documents/{id}/rebuild` | 202 | `DocumentMutation` |
| DELETE `/api/v1/admin/documents/{id}` | 202 | `DocumentMutation` |
| POST `/api/v1/admin/documents/{id}/cleanup-retry` | 202 | `DocumentMutation` |
| GET `/api/v1/citations/{reference_id}` | 200 / 410 | `Citation`（reference/text） |

- 错误码：`FORBIDDEN`(403)、`RESOURCE_NOT_FOUND`(404)、`DUPLICATE_FILENAME`/`DOCUMENT_BUSY`/`VERSION_CONFLICT`(409)、
  `CITATION_UNAVAILABLE`(410)、`UPLOAD_TOO_LARGE`(413)、`UNSUPPORTED_FILE_TYPE`(415)、`VALIDATION_FAILED`(422)、
  `STORAGE_UNAVAILABLE`/`RETRIEVAL_UNAVAILABLE`(503)。
- 运行态 OpenAPI：8 端点均声明 `operation_id`、`Envelope[<组件>]` 响应模型与 `ERROR_RESPONSES`；
  `Upload` multipart 请求体、`Rebuild` 请求体、`Idempotency-Key`/`expected_version` 参数与设计包一致
  （由 `test_knowledge_contract.py` 对 `docs/backend/openapi_v0.1.json` 断言 components 字段/必填集合）。

## 4. 确定性 Provider 声明（非生产 AI）

- **Embedding**：`app/adapters/embedding/deterministic.py`，SHA-256 派生特征 → 固定维度单位向量。
  同一文本永远得到同一向量；维度 `CCA_EMBEDDING_DIM`（默认 64，8–1024）。
  **这不是生产 Embedding 模型**，维度/Top-K/阈值属 TBD-04，未做真实语义质量评测。
- **VectorStore**：`app/adapters/vector/local.py`，本地 JSON 文件（`CCA_VECTOR_ROOT`，默认 `backend/var/vector/vector_store.json`），
  提供命名空间、幂等 upsert、按范围列举/删除、写入收敛屏障（`barrier(prefix, fence)` 拒绝旧代次写入并清除旧记录）。
  **这不是生产向量数据库**（TBD-07）；生产替换必须保持同样的幂等/列举/屏障语义（后端详细设计 §10.5）。
- **AI 质量**：仅验证检索/引用/发布/删除的算法链路与可重复性，**不得**宣称达到试点语义质量（TBD-04 未冻结）。
- 重置方法：删除 `CCA_VECTOR_ROOT` 目录或调用 `LocalVectorStore.reset()`；测试每个用例使用独立临时根目录。

## 5. 交接说明（Phase 3 / Phase 4）

### 5.1 启动 Worker

```powershell
# 常驻（1s 轮询；启动时回收过期租约）
python -m app.entrypoints.worker
# 单次排空（测试/运维；上传后一次即可完成解析→发布）
python -m app.entrypoints.worker --once --max-tasks 100
```
入口 `app/entrypoints/worker.py`；进程标识 `--owner` 可覆盖（默认 `host:pid:rand`）。

### 5.2 上传样本（管理员）

```powershell
curl.exe -X POST "http://127.0.0.1:8100/api/v1/admin/document-batches" `
  -H "Authorization: Bearer $TOKEN" `
  -F "files=@course.md;type=text/markdown" `
  -F "files=@rules.pdf;type=application/pdf"
# 202 → data.batch_id；随后 python -m app.entrypoints.worker --once
```
支持 txt / md / pdf（文本层）/ docx；扫描件与加密 PDF 会异步失败（`NO_TEXT_EXTRACTED`/`DOCUMENT_ENCRYPTED`）。

### 5.3 检索接口（Phase 3 对接）

```python
from app.modules.knowledge import SearchQuery, knowledge  # 或 knowledge.interface.KnowledgeInterface
evidence = await knowledge.search(ctx, SearchQuery(query=question, top_k=5))
evidence.to_dict()
# {"status":"ok|empty","corpus_empty":bool,"revision":int,
#  "chunks":[{"chunk_id","reference_id","document_id","version_id","text","location_label","page_number"?}],
#  "references":[{"reference_id","document_id","version_id","file_name","location_label","page_number"?}]}
```
- 全库为空 → `status="empty" + corpus_empty=true`（明确状态，不是失败）；
- 检索/存储依赖异常 → 抛 `ApiError("RETRIEVAL_UNAVAILABLE"|"STORAGE_UNAVAILABLE")`，不得伪装 empty；
- 返回结构严格按冻结 EvidenceSet / MCP `search_course_docs` 输出，**不含任何存储键**；如需新增字段先通知 Lead。

### 5.4 重建 / 删除 / 清理重试

- 重建：`POST /admin/documents/{id}/rebuild`，`Idempotency-Key` + `{"expected_version": n}` → 202 任务；旧版在切版前持续可检索。
- 删除：`DELETE /admin/documents/{id}?expected_version=n`（无请求体）→ 202 立即不可见；引用立即 410；`worker --once` 推进清理。
- 清理失败：`POST /admin/documents/{id}/cleanup-retry` + `Idempotency-Key`，只推进删除范围，不恢复可见性。
- 并发重建/删除 → 409 `DOCUMENT_BUSY`；版本不匹配 → 409 `VERSION_CONFLICT`。

### 5.5 配置项（环境变量；不改 Lead 单写者 `config.py`）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `CCA_FILESTORE_ROOT` | `backend/uploads` | 文件根目录（gitignore） |
| `CCA_VECTOR_ROOT` | `backend/var/vector` | 本地向量清单目录 |
| `CCA_VECTOR_SPACE` | `corpus_v1` | 语料向量空间（写入 `corpus_control.active_vector_space`） |
| `CCA_EMBEDDING_DIM` | 64 | 确定性向量维度 |
| `CCA_CHUNK_SIZE` / `CCA_CHUNK_OVERLAP` | 500 / 80 | 分块窗口与重叠（码点） |
| `CCA_UPLOAD_MAX_FILES` / `_FILE_BYTES` / `_TOTAL_BYTES` | 10 / 20MiB / 50MiB | 上传限制（来自 `config.Settings`） |

### 5.6 `publish_frozen` 语义（已与 Lead 裁决）

- 迁移默认 `TRUE`（安全默认：向量空间迁移/冻结期禁止发布）。
- 冻结期间 Worker **不发布、不失败、不半发布**：持久任务保持 ready，发布任务排到 10s 后重试；解冻后自动完成。
- 测试显式置 `FALSE`；开发/演示由 seed/运维置 FALSE（Lead 单写者文件）。
- 若长期冻结，管理员可见批次停留在 `processing`（文档仍不可见）；报告建议运维在解冻后触发 `worker --once`。

## 6. 未验证项 / 范围外（如实登记）

1. **真实外部 Embedding 模型与向量数据库**（TBD-04/TBD-07 未冻结）：当前为本地确定性 Provider / 本地 JSON 适配器，未做生产语义质量与性能评测。
2. **OCR / 扫描件 / 复杂格式**（TBD-05）：仅 txt/md/pdf 文本层/docx；扫描件与加密 PDF 明确失败。
3. **多机部署与共享文件存储**：FileStore 为本地卷；多机需替换支持幂等写/范围列举/屏障的对象存储实现。
4. **向量空间迁移流程（设计 §11.3）**：仅实现 `publish_frozen` 冻结/解冻与 `corpus_control.active_vector_space` 一致性校验；实际迁移切换、旧空间后台清理未验证。
5. **备份 / RPO / RTO、物理删除与墓碑保留期（TBD-06）**：版本/引用/attempt 墓碑按当前语义保留，物理删除未实现。
6. **真实 AI 质量评测（≥50 条固定集）**：未做；需待模型凭据与评测集冻结。
7. **20MiB/50MiB 边界**：用真实大文件路径做了 413 分支测试（通过配置覆盖限额），未在 CI 生成 50MiB 组合样本；格式/签名/路径注入/数量边界已覆盖。
8. **`test_release_migration.py`**（Phase 5 前置）会 downgrade 清库：未在本车道 T1 中运行，也**不得**与其他车道并行运行；Phase 5 由 Lead/qa-verifier 在独立库执行。

## 7. 已知风险与后续建议

- 发布事务在事务内只做数据库校验；向量索引完整性在事务外预检（`batch_precheck`）后、事务内复核 attempt settled 与版本 ready。若外部产物在预检后、事务提交前被删除，会出现“已发布但索引缺失”的窄窗口；本地 FileStore/VectorStore 无外部删除入口，风险受限；接入真实对象存储后需按 §10.5 增加屏障确认。
- 重建切版遵循 `uq_document_one_active` 即时唯一键：先更新旧版 `retired` 并 flush，再激活新版（已修复）。
- 引用列表在批次补偿/删除时保留“无正文墓碑”（`revoked_at`），符合设计 §11.2；引用端点对墓碑统一 410。
- `Batch.tasks` 中发布任务在正常路径由最后一个持久任务在发布事务内标记 `succeeded`；若发布冻结则显示 `retry_wait`（可观测，非失败）。

## 8. 出口判据对照（C1–C8）

| # | 判据 | 状态 |
| --- | --- | --- |
| C1 | 上传边界/签名/202 + 批次不可见 | ✅ 测试覆盖（数量/单文件/总量/伪造后缀/路径注入/同名/重复上传策略） |
| C2 | 领取唯一、租约回收、重试退避、丢租约不发布 | ✅ 4 用例（含旧 fence 提交拒绝、迟到发布拦截） |
| C3 | 全可见或全不可见；失败补偿；revision 递增 | ✅ 发布/补偿/冻结/重建 revision 断言 |
| C4 | 权威复核 EvidenceSet；空库 empty；未发布/删除不可见 | ✅ 6 用例 |
| C5 | 引用可展开；删除/切版/清理后 410；无存储键 | ✅ 管理+引用用例 |
| C6 | 旧版持续可用→切版；立即不可见；DOCUMENT_BUSY | ✅ 重建/删除/并发用例 |
| C7 | 8 端点契约（字段/状态码/错误码） | ✅ 行为测试 + 运行态 OpenAPI 对照设计包 |
| C8 | 车道 T1 全绿；报告登记非生产 Adapter | ✅ 48 passed；本报告 §4/§6 |
