# verification/ · Phase 5 独立验证（qa-verifier）

本目录是 Phase 5 的**独立验证**产物：不复用 owner 结论，只认我自己跑出的原始命令与输出。

| 文件 | 内容 |
| --- | --- |
| [`ENVIRONMENT.md`](ENVIRONMENT.md) | 独立环境（库 `cca_test_release`、端口 8200/8201/8202/5273、独立存储目录）、环境变量、启动方式、自检结果、契约真源哈希锚点 |
| [`CHECKLIST-M1-M9.md`](CHECKLIST-M1-M9.md) | 全量矩阵 M1–M9 的独立命令 / 期望 / 证据格式；对抗性检查 A1–A12；反向注入 G1–G5；§14.2 竞态 1–10 映射；未验证项预登记 |
| [`RELEASE-VERIFICATION.md`](RELEASE-VERIFICATION.md) | 判定报告（当前为阶段 A 骨架，所有行 `PENDING`；阶段 B 填 PASS/FAIL + 证据） |
| `scripts/env.ps1` | 准备/启动/停止/状态/重置库/种子（自持 8200–8202，不碰 Lead 的 8100–8102） |
| `scripts/preflight.ps1` | 只读环境自检（Git/工具链/MySQL/端口/契约哈希/测试规模） |
| `scripts/m4-injection.sql` | M4 数据库反注入探针（12 条坏数据 + 合法对照） |
| `evidence/` | 原始命令输出日志（报告中只贴摘要；该目录与 `runtime/`、`**/*.log`、`**/*.pid` 由根 `.gitignore` 排除，不入库） |

## 快速开始

```powershell
pwsh -NoProfile -File verification/scripts/preflight.ps1          # 只读自检
pwsh -NoProfile -File verification/scripts/env.ps1 -Action prepare # 建库 + alembic upgrade head
pwsh -NoProfile -File verification/scripts/env.ps1 -Action start   # 8200/8201/8202 + worker
pwsh -NoProfile -File verification/scripts/env.ps1 -Action status
pwsh -NoProfile -File verification/scripts/env.ps1 -Action stop
```

## 边界

- 只读 `backend/**`、`web/**`、`design/**`、`docs/**`；只写 `verification/**`。
- 不触碰 Lead 的 8100/8101/8102、5173 与常驻 worker；不清理演示库 `cca`。
- 反向注入只改 `verification/` 下的副本或数据面，不改源码。
