# AGENTS.md

给在本仓库工作的自动化代理与协作者的约定。**动手之前先读这一页。**

## 1. 不要把这三类文档放进 git

过程性、开发、计划文档一律**不入库**（不 `git add`、不写进提交、不放进 PR）：

| 类别 | 典型内容 |
| --- | --- |
| **过程性文档** | 阶段/任务报告、复验报告、验收记录、进度台账、里程碑、交接说明、验证证据（命令输出、日志、截图、JSON 快照、覆盖率/性能数据）、评审与复核记录、临时笔记、调试过程 |
| **开发文档** | 需求、概要设计、详细设计、接口与字段说明、开发说明、实现备忘（即 `docs/` 那一类内容） |
| **计划文档** | 计划、排期、路线图、任务拆分、待办清单 |

这些内容**只留在磁盘**（或通过对话与 PR 描述里的摘要沟通）。仓库只承载**产物本身**。

## 2. 该进 git 的

- 代码与测试：`backend/`、`web/`
- 可复现的工程配置：`scripts/`、`.gitignore`、`.gitattributes`、`package.json`、`pyproject.toml`、`alembic` 迁移
- 仓库入口与约定：`README.md`、`AGENTS.md`

## 3. 现状（不要"顺手补齐"）

| 路径 | 状态 |
| --- | --- |
| `docs/` | 整体忽略；需求、设计、计划、台账都不在 git |
| `design/` | 整体忽略；方案与原型（设计方向、响应式原型、设计系统源）只在磁盘 |
| `verification/` | 整体忽略；报告、脚本、证据只在磁盘 |
| `backend/reports/`、`web/reports/`、`web/BUILD-REPORT.md`、`design/reviews/`、`design/**/verification.md`、`design/**/shots/` | 已整体移出索引并加入忽略；历史报告只保留在磁盘 |
| `backend/var/`、`backend/uploads/` | 运行期产物，已忽略 |

## 4. 容易踩的坑

1. **契约真源不在 git**：`docs/backend/{openapi_v0.1.json, mcp_tools_v0.1.json, sse_events_v0.1.schema.json, cca_schema_v0.1.sql}` 随 `docs/` 一起被忽略，但它们是门禁依赖——缺失会让
   `web/scripts/gen-types.mjs --check`、`contract-diff.mjs`、`verification/scripts/preflight.ps1` 与后端契约用例失败或静默 skip。换机器/新克隆时先确认这 4 个文件在位。
2. **设计源不在 git**：`design/system/tokens.{json,css,ts}` 随 `design/` 一起被忽略，但 `web` 的 `tokens:check` / `tokens:sync` 依赖它们；缺失时该门禁失败。改样式数值只走设计源 → 同步脚本，**不要手改** `web/src/styles/tokens.*`。
3. **不要用改名绕过忽略规则**（把报告改成 `.txt`、塞进别的目录混进去之类）。
4. 确需临时恢复跟踪某个被忽略的文件：`git add -f <path>`，并在提交说明里写明理由与后续移除时点。

## 5. 提交前自检

- [ ] 本次提交只含代码 / 配置 / 入口文档，没有过程性、开发或计划文档
- [ ] 没有日志、证据、截图、覆盖率或性能数据被夹带进来
- [ ] 一个提交一个主题
