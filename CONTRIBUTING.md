# 协作约定：分支策略与测试节奏

本文件是**团队约定**，不是产品需求。需求与设计真源在 `docs/`，设计产物在 `design/`，前端实现在 `web/`。

---

## 1. 分支策略

| 分支 | 用途 | 说明 |
| --- | --- | --- |
| `main` | 集成基线 | 只接受「证据齐全」的合并。每个合并点必须是**可复现、可回归**的状态 |
| `docs/align-*` | 文档对齐 | 如 `docs/align-rb-fix`，用于 `docs/frontend-detail/DOC-SYNC-PENDING.md` 里的 TODO 批次 |
| `fix/*` | 缺陷修复 | 一类问题一个分支，例如 `fix/rb-w1-scroll-occlusion` |
| `feat/*` | 功能开发 | 例如 `feat/assistant-live-backend` |

**提交粒度**：一次提交只做一件事。凡是**改了会级联的文件**（见 §3），提交信息里必须写明「已重跑哪些生成器/校验器」及其结果。

**禁止**：
- 直接往 `main` 推未经校验的生成物变更；
- 手改生成物（`design/system/tokens.css`、`design/system/tokens.md`、`design/system/tokens.ts`、`design/system/tokens.flat.json`、`design/responsive/b-responsive.html`、`design/system/system.html`、`docs/校园课程智能助手_前端详细设计_v0.1.md`）——它们必须由脚本产出。

---

## 2. 测试节奏（按成本分三档）

| 档 | 何时用 | 跑什么 | 成本 |
| --- | --- | --- | --- |
| **冒烟** | 开发过程中每次改动 | `web/`：`node scripts/invariants.mjs` + `node scripts/check-sfc.mjs`；改动 `design/` 时：只跑受影响的那一个脚本 | 秒级 |
| **回归** | 修一个 bug / 动一处共享文件 | 该 bug 对应用例 + 相邻的 1–2 个校验脚本 | 十秒级 |
| **全量** | 阶段收尾、合并回 `main` 前 | 下面 §2.1 全部 | 分钟级 |

> 原则：**全量只用于收尾**。不要在开发中途反复跑全套，那会把时间花在等待上而不是在找错上。

### 2.1 全量清单

```powershell
$env:PYTHONIOENCODING="utf-8"

# --- 设计系统 / 响应式原型（6 个校验器，全部必须 0 FAIL） ---
python design\system\generate.py            # token 源 → 生成物；含 rb.css 逐值等价、对比度、分层纯度
python design\system\build-system.py        # 组装 system.html
python design\system\verify-system.py       # 独立于生成器的 31 项确定性校验
python design\responsive\build.py           # 组装 b-responsive.html + 构建期契约检查
python design\reviews\verify.py             # 方向稿 / 结构 / 文案 / 对比度 / 裸 hex / 标签配平
python docs\frontend-detail\build.py        # 组装前端详细设计主文档（它是生成物）

# --- 前端骨架（web/） ---
cd web
pnpm install
pnpm build                                   # 生产构建（沙箱内会因 stdio:'pipe' 被拒而失败，见 §4）
node node_modules\vue-tsc\bin\vue-tsc.js --noEmit -p tsconfig.json
node scripts\check-sfc.mjs                   # 53 个 .vue 走真实 SFC 编译
node scripts\invariants.mjs                  # 10 项机械不变量
node scripts\sync-tokens.mjs --check         # tokens 与 design/system/ 逐字节一致
node node_modules\stylelint\bin\stylelint.mjs "src/**/*.{css,vue}"
node --import ./scripts/ts-alias-hook.mjs scripts\smoke-sse.mjs   # 纯函数级流式冒烟
```

### 2.2 承重不变量（每次改动都要保证，不能只靠全量）

1. `web/src/styles/tokens.css|ts` 与 `design/system/tokens.css|ts` **逐字节一致**；
2. 组件 `<style>` **只消费 L3 token**；
3. 不出现 `:active` / `transition` / `animation`（唯一白名单：`.step--running .step__ico` 的旋转，见 §3）；
4. 文案只用 `design/directions/shared/content-spec.md` 已冻结的逐字文本；
5. 令牌只在内存，不进 `localStorage` / `sessionStorage` / `IndexedDB` / URL / 日志；
6. 对话正文不进 URL；唯一私有深链 `/me/plans/:planId`；
7. 零外部请求。

---

## 3. 会级联的文件（改动前先读这一节）

改这些文件**不会只影响它自己**：

| 改了 | 必须同步 | 否则 |
| --- | --- | --- |
| `design/responsive/rb.css` 的 `:root` 变量 | `design/system/tokens.json`（L3 或 L0）→ 重跑 `generate.py` | `generate.py` 的「rb.css 每个变量逐值等价」是 **FAIL 级** |
| `design/system/tokens.json` | 重跑 `generate.py`；同步 `design/system/README.md` 里的计数（token 总数 / 各层数量 / 对比度对数 / 两个冻结哈希） | `verify-system.py` 的「README 计数一致」FAIL |
| `design/responsive/parts/*.html` | 重跑 `responsive/build.py` | 产物与源不一致 |
| `docs/frontend-detail/parts/*.md` | 重跑 `docs/frontend-detail/build.py` | 主文档是生成物，手改会被覆盖 |
| 任何改 `rb.css` 的提交 | 重跑六宽度页面级溢出测量 | 「六宽度溢出为 0」这条已验证结论会失效 |

**唯一动效白名单**：`.step--running .step__ico` 的旋转（消费 L3 `--step-running-spin-duration` / `--step-running-spin-easing`）。这是对 CI 规则 `dsh/no-forbidden-states` 的**显式窄化**，依据是前端详细设计 §8.5 自身以该动效为 `prefers-reduced-motion` 重置的依据。**出现第二处 animation 即 FAIL。**

---

## 4. 已知环境限制（不是代码问题）

**DSH 沙箱内 `pnpm build` / `pnpm dev` 无法运行**：沙箱拒绝 `child_process` 的 `stdio:'pipe'`，而 Vite 用该通道启动 esbuild 服务并 bundle 配置文件。

- `esbuild` 原生 CLI **完全可用**（`esbuild.exe --version` → `0.25.12`，`--bundle` 能出产物）；
- 只有 Node 的「JS 库 ↔ 常驻服务」这条管道通道被拒；
- **同一份代码在沙箱外（或本机终端直接运行）是正常的**。

实测边界：`vite build` 死在 `bundleConfigFile`；改用 programmatic API + `configFile:false` 可越过配置阶段，但仍会死在 `@rollup/plugin-commonjs` 的 resolver。

**证据与未覆盖项**见 `web/BUILD-REPORT.md`；两条 task 层面的验收判据（`pnpm build` exit 0、`pnpm dev` 首页可访问）需在**沙箱外**补验。

---

## 5. 证据纪律

- 结论必须给**原始命令 + 原始输出**；推断、实测、未验证三者分开标注。
- **不得用替代证据冒充**原判据。做不到就写「未验证」。
- 区分**变更证据**（前后字节不同、mtime、哈希不匹配）与**类型证据**（某生成器不写该文件）——后者不能证明前者。
- 判据本身也要能被攻击：关键门禁应有**反向注入自测**（故意制造违规，确认它会 FAIL）。
