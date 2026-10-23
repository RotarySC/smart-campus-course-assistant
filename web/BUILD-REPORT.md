# web/BUILD-REPORT.md —— 阶段 B「Vue 3 可运行响应式骨架」交付报告

| 项 | 值 |
| --- | --- |
| 任务 | task-3（阶段 B：Vue3 + TS + Pinia 可运行骨架，mock，L3-only） |
| 依据 | `docs/校园课程智能助手_前端详细设计_v0.1.md`（§2.1/§5/§6/§7/§8/§9/§10）+ `docs/backend/*` + `design/system/*` + `design/directions/shared/content-spec.md` |
| 上游 | 阶段 A（task-1）已冻结：`design/system/tokens.css` MD5 `26eee4f0348c6e4da9db1840d17f2163`、`tokens.ts` MD5 `03607588e7ec217959da681f51b363e7` |
| 环境 | node v24.18.0 · pnpm 11.21.0 · Windows · **DSH 沙箱 `workspace-write`** |
| 结论 | 源码全量落地。**生产构建与组件渲染在本沙箱内不可能验证**（环境限制，非代码问题）；其余门禁全绿 |

---

## 0. 一句话结论

`web/` 的目标目录、8 个 store、10 条路由、SSE 流式客户端（P1–P12 + §5.4 状态机）、27 个组件族、
S01–S12 视图与 mock 层**全部落地**；`tokens.css`/`tokens.ts` 与 `design/system/` **逐字节一致**；
`vue-tsc --strict`、stylelint 分层纯度门、10 项机械不变量、53 个 SFC 编译检查、24 项**纯函数**级流式冒烟**全部 exit 0**。

> ## ⚠ 未经独立确认的两件事
> 1. **生产构建（`pnpm build`）未经独立确认** —— 本沙箱内无法运行（§1），`web/dist/` **不存在**。
> 2. **组件渲染未经独立确认** —— 未做浏览器冒烟，也**没有**用任何自建通道去替代它（§7.6）。
>
> 这两项必须在**沙箱外**（用户自己的开发机 / CI）按 §3.1 的六条命令补验。

---

## 1. 标准路径 vs 沙箱内等价证据（两栏口径）

### 1.1 左栏：标准路径 —— **在本沙箱内无法验证**

| 命令 | 沙箱内状态 | 证据 |
| --- | --- | --- |
| `pnpm install` | ✅ 可运行，exit 0 | §3.2 A |
| **`pnpm build`** | ❌ **无法运行**（exit 1） | §1.2 原始报错 |
| **`pnpm dev`** | ❌ **无法运行**（exit 1） | §1.2 原始报错 |
| `curl http://localhost:5173/` | ❌ 无服务器可访问 | 同上 |
| 浏览器点击冒烟（S01→S12） | ❌ 未做 | 同上 |

**`web/dist/`（含 `dist/index.html`）不存在**：因环境限制未产出，**非代码问题**，也**不是**为了让它存在而接自建打包器。

### 1.2 根因：`child_process` 的 `stdio:'pipe'` 通道被沙箱拒绝

**准确的说法是「通道」问题，不是「工具缺失」问题。** esbuild 的**原生 CLI 完全可用**：

```
PS> node_modules\@esbuild\win32-x64\esbuild.exe --version
0.25.12                                                              [exit=0]
PS> esbuild.exe <f>.js --bundle --outfile=<o>.js          （Lead 实测）
产出 93 B                                                            [exit=0]
PS> node -e "require('esbuild').transform(...)"           （Lead 实测）
Error: spawn EPERM                                                   [exit≠0]
```

被拒的**只有**「Node JS 库 ↔ 常驻服务」这条管道通道。Vite 恰好用它来起 esbuild 服务、并用来 bundle `vite.config.ts`。

**原始报错（一字未改）**：

```
PS> pnpm build
[ELIFECYCLE] Command failed with exit code 1.
[stderr]
$ vite build
failed to load config from C:\Users\Rotary\Documents\Comprehensive\Files\Projects\Smart Campus Course Assistant\web\vite.config.ts
error during build:
Error: spawn EPERM
    at ChildProcess.spawn (node:internal/child_process:441:11)
    at Object.spawn (node:child_process:796:9)
    at ensureServiceIsRunning (C:\...\web\node_modules\esbuild\lib\main.js:1978:29)
    at build (C:\...\web\node_modules\esbuild\lib\main.js:1876:26)
    at bundleConfigFile (file:///C:/.../web/node_modules/vite/dist/node/chunks/dep-CkSfqg8D.js:49636:24)
    at async bundleAndLoadConfigFile (...:49620:19)
    at async loadConfigFromFile (...:49584:44)
    at async resolveConfig (...:49079:24)
    at async createBuilder (...:47054:18)
    at async CAC.<anonymous> (.../vite/dist/node/cli.js:862:23)
```

`pnpm dev` 同一个错，仅最后一行换成 `error when starting dev server`。
两者都**在读取配置文件阶段**就失败 —— 根本没走到我们的源码。因此**别名、tsconfig `paths`、依赖都不是自变量**。

### 1.3 三向隔离实验（证明是通道而非配置）

**(i) 同一份 `esbuild.exe`，只换 stdio 模式**：

```
exe = ...\web\node_modules\@esbuild\win32-x64\esbuild.exe
inherit => status 0
ignore  => status 0
pipe    => status null   err EPERM
```

→ 只有 `stdio:'pipe'` 被拒。而 `esbuild/lib/main.js` 的 `ensureServiceIsRunning` 显式用 `stdio:['pipe','pipe','inherit']`
（它要靠管道收发 `--service` 协议）。**传输方式被判死，不是配置问题。**

**(ii) 排除「配置文件类型」与「我们的 tsconfig / 别名 / 依赖」**：
用纯 `.mjs`、只 import `vite` + `@vitejs/plugin-vue`、完全不涉及 `tsconfig` `paths` 的探针配置，
并同时关掉 `esbuild:false` / `build.minify:false` / `build.cssMinify:false` / `optimizeDeps.noDiscovery:true`，
**仍然死在同一个位置**（`bundleConfigFile → esbuild → spawn EPERM`）。（探针已删除，无残留。）

**(iii) 同一条边界在三个不同 spawn 点反复出现**：
- 包生命周期脚本：`[ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: esbuild@0.25.12, vue-demi@0.14.10` + `code:'EPERM', syscall:'spawn', errno:-4048`
- `terminal_open`：`PTY shell exited during startup`
- `vite build` / `vite dev`：`spawn EPERM`

### 1.4 Lead 复核的三阶段实测（引用）：`configFile:false` 能越过配置阶段，但触发点不止一个

```
① vite build + vite.config.ts
   -> failed to load config from ...vite.config.ts / spawn EPERM
      at bundleConfigFile -> esbuild ensureServiceIsRunning

② 纯 .mjs 配置文件（只 import vite/plugin-vue 的探针配置，绝对路径）
   -> failed to load config from ...vite-probe.config.mjs / spawn EPERM
      at bundleConfigFile          <- 同一个位置

③ programmatic API：build({ configFile:false, esbuild:false, plugins:[vue()] })
   -> "vite v6.4.5 building for production..."      <- 越过配置阶段了
   -> "✓ 0 modules transformed."
   -> ✗ Build failed: [commonjs--resolver] spawn EPERM   <- 换了个触发点
```

**精确结论**：`configFile:false` **确实**绕过了 `bundleConfigFile`（我原先方向判断对了，但以为关键是 `esbuild:false` —— 实际是 `configFile:false`）；
但 esbuild 的管道通道在构建链上**至少有三个触发点**：① config bundling ② `@rollup/plugin-commonjs` 的 resolver ③ 依赖预打包；
其中 ② **连 `esbuild:false` 都关不掉**（commonjs resolver 自己起服务）。
→ **本沙箱内不可能产出构建产物，这不是配置能解决的问题。我们没有为此接任何自建打包器。**

### 1.5 右栏：沙箱内等价证据（**不依赖任何自建通道**）

| # | 证据 | 命令 | 结果 | 通道 |
| --- | --- | --- | --- | --- |
| B1 | TypeScript 全量类型检查 | `vue-tsc --noEmit -p tsconfig.json` | **exit 0，0 error** | 不依赖自建通道 |
| B2 | `vite.config.ts` 类型检查 | `tsc --noEmit -p tsconfig.node.json` | **exit 0** | 不依赖自建通道 |
| C | tokens 逐字节一致（两文件） | `node scripts/sync-tokens.mjs --check` + PowerShell `Get-FileHash` | **exit 0，md5 两侧一致** | 不依赖自建通道 |
| D | 53 个 `.vue` 的 SFC 编译 | `node scripts/check-sfc.mjs`（`@vue/compiler-sfc` 进程内） | **53/53 PASS，exit 0** | 不依赖自建通道 |
| E | 10 项机械不变量 | `node scripts/invariants.mjs` | **10/10 PASS，exit 0** | 不依赖自建通道 |
| F | 24 项**纯函数**级流式冒烟 | `node --import ./scripts/ts-alias-hook.mjs scripts/smoke-sse.mjs` | **24/24 PASS，exit 0** | **需测试钩子**（§7.6） |
| G | stylelint 分层纯度门 | `stylelint "src/**/*.{css,vue}"` | **0 warning，exit 0** | 不依赖自建通道 |
| H | 12 项门禁反向注入自测 | `node scripts/verify-gates.mjs` | **12/12 按预期 FAIL；还原后全绿** | 不依赖自建通道 |

完整转录（**每节都标了通道**）：[`verify-transcript.txt`](verify-transcript.txt)。

---

## 2. 已交付内容

### 2.1 目录（与前端详细设计 §2.1 一致）

```
web/
├─ index.html  vite.config.ts  tsconfig.json  tsconfig.node.json  package.json
├─ pnpm-workspace.yaml            # pnpm 11 构建设置 + nodeLinker（见 §5）
├─ .stylelintrc.cjs  stylelint-rules/layer-purity.cjs
├─ .env.example  .env.development
├─ README.md  BUILD-REPORT.md  verify-transcript.txt
├─ scripts/  sync-tokens.mjs · invariants.mjs · check-sfc.mjs · smoke-sse.mjs
│            verify-gates.mjs · ts-alias-hook.mjs（测试专用，边界见 §7.6）
└─ src/
   ├─ main.ts  App.vue（外壳 + <main id="main">）
   ├─ styles/  tokens.css（生成物）· tokens.ts（生成物）· global.css · base.css（27 族）
   ├─ api/     client.ts errors.ts types.gen.ts transport.ts auth.ts me.ts chat.ts admin.ts citations.ts
   │           sse/parse.ts sse/stream.ts   mock/{db,handlers,sse,index}.ts
   ├─ domain/  constants.ts copy.ts sseTypes.ts chatMachine.ts dedupe.ts validate.ts mapError.ts format.ts breakpoints.ts
   ├─ stores/  session chat schedules plans drafts writeOps admin ui（**8 个，名字冻结**）
   ├─ router/  index.ts routes.ts（10 条）guards.ts（G1–G4）
   ├─ components/ base/（27 族）product/（ChatStream / CitationList / DraftCard / ScheduleTable / BatchPanel）
   ├─ views/   LoginView AssistantView MyScheduleView PlansView PlanDetailView
   │           AdminCoursesView AdminDocumentsView AdminBatchView AdminScheduleView AdminStudentsView
   └─ a11y/    live.ts focus.ts
```

**规模**：`.vue` 53 个 · 源文件 97 个 · 组件用到的 class 114 个（全部逐字存在于 `rb.css`）。

### 2.2 对 §2.1 的两处补充（已与 Lead 确认）

1. **`src/styles/tokens.ts`** —— §2.1 的 `styles/` 只列 3 个文件，但 §8.3 明文要求
   `import { breakpoints } from '@/styles/tokens'` 驱动 `matchMedia`。它与 `tokens.css` **同一个同步脚本、同样做 md5 校验**。
2. **`domain/copy.ts`、`domain/sseTypes.ts`、`api/transport.ts`、`api/mock/*`** —— §2.1 未列出的**文件**（未新增目录）。
   理由：冻结文案唯一落点；SSE 类型契约（让 `domain` 不必 import `api`，满足 §2.2 R1）；可替换传输层（让 mock 跑真实代码路径）；mock 数据。

### 2.3 契约硬点的落位（抽查）

| 契约点 | 落位 | 机械证据 |
| --- | --- | --- |
| §6 八个 store 名字冻结 | `stores/{session,chat,schedules,plans,drafts,writeOps,admin,ui}.ts` | 文件名 + `defineStore('x')` |
| §6.2 静态依赖无环 | `chat` **不**依赖 `drafts`（草稿绑定移到视图，§2.2 R5） | typecheck + 代码结构；见 §7.2 |
| §7 十条路由 | `router/routes.ts`（含 `/me/plans/:planId` 唯一私有深链） | 10 个 `path` |
| §5.3 P1–P12 解析规则 | `api/sse/parse.ts` | 冒烟 F 的 9 条 |
| §5.4 事件转换 / 终态唯一 / HTTP 关闭≠终态 | `domain/chatMachine.ts` | 冒烟 F 的 A6/A7/A8 |
| §8.2 只消费 L3 | `styles/base.css` + 组件 `<style>` | 不变量 2 + stylelint ③ |
| §8.3 断点 6 档 | `domain/breakpoints.ts` + `ui.initBreakpoints()` | 不变量 9 |
| §9 S08 两种空态**不合并** | `schedules.items`/`error` 分离 + `MyScheduleView` 两个 `EmptyState` 分支 | 代码结构（**渲染未验证**，见 §4.2） |
| §10.4 class 存在性 | 全部 class 逐字来自 `rb.css` | 不变量 7 |
| §7.5 对话正文不进 URL | `/assistant` 无 query；视图不读写 `route.query` | 代码结构 |

---

## 3. 复现方式

### 3.1 必须在**沙箱外**（普通开发机 / CI）补跑的五条

```powershell
cd web
pnpm install
pnpm build                       # 期望 exit 0  → 产出 dist/index.html
pnpm dev                         # 期望起在 http://localhost:5173
curl.exe -s http://localhost:5173/ | Select-Object -First 5
# 然后在浏览器里点通：登录 → 课程助手（SSE 流式）→ 我的课表 → 学习计划 → 管理员
```

**沙箱内已跑通的部分**（不依赖自建通道）：

```powershell
cd web
node node_modules\vue-tsc\bin\vue-tsc.js --noEmit -p tsconfig.json
node node_modules\typescript\bin\tsc --noEmit -p tsconfig.node.json
node scripts\sync-tokens.mjs --check
node scripts\check-sfc.mjs
node scripts\invariants.mjs
node node_modules\stylelint\bin\stylelint.mjs "src/**/*.{css,vue}"
node scripts\verify-gates.mjs
# 唯一需要测试钩子的一条（纯函数级，不涉渲染）：
node --import ./scripts/ts-alias-hook.mjs scripts/smoke-sse.mjs
```

### 3.2 转录摘要（完整见 `verify-transcript.txt`）

```
C  tokens 逐字节一致                                        [exit=0]
   OK web/src/styles/tokens.css 与 design/system/tokens.css 逐字节一致（md5 26eee4f0348c6e4da9db1840d17f2163）
   OK web/src/styles/tokens.ts  与 design/system/tokens.ts  逐字节一致（md5 03607588e7ec217959da681f51b363e7）
   PowerShell 侧独立复算：两个文件的 Hash 各自两侧一致

D  SFC 编译检查                                             [exit=0]
   PASS  53 个 .vue 全部通过 parse → compileScript → compileTemplate → compileStyle

E  不变量 10 项                                             [exit=0]
   PASS 1 tokens 逐字节一致 · 2 只消费 L3 token（43 文件）· 3 无违禁状态/动效
   PASS 4 无违禁文案（97 文件，已剥注释）· 5 零外部请求（94 文件）· 6 零持久化
   PASS 7 class 存在性（114 class）· 8 不引用 /internal/v1 · 9 断点 6 档 · 10 skip-link 目标
   10/10 通过

F  纯函数级流式冒烟 24 项                                    [exit=0]
   24/24 通过（含 E2E：mock 真 ReadableStream → 解析 → 状态机，21 事件 / 3 步骤 / 1 引用 / 正文 69 字）

G  stylelint                                                [exit=0]  0 warning

H  门禁反向注入自测                                          [exit=0]
   12/12 门禁被证明会 FAIL —— 含 Lead 指定的「第二处 animation」用例：
   门禁3-a 违禁动效：base.css 出现**第二处** animation → 按预期 FAIL
   还原后重跑：invariants 10/10 通过；stylelint warnings=0；还原后全绿 ✓
```

> **Lead 特别要求的那条**（「确保不变量脚本第 3 条真的会在出现第二处 `animation` 时 FAIL，做一次反向注入自测」）：
> 已做，见 `门禁3-a`。断言的是**目标规则本身**变红（`row.ok === false`），**不接受**「被别的规则顺带抓到」。

### 3.3 `--check` 哈希门禁会不会在构建时挡住漂移？—— 诚实说明

| 位置 | 机制 | 本沙箱状态 |
| --- | --- | --- |
| `pnpm tokens:check` / `pnpm check` | `sync-tokens.mjs --check` 不一致即 exit 1 | ✅ 可跑，已用 `门禁1` 反向注入证明会 FAIL |
| `scripts/invariants.mjs` 第 1 条 | 独立重算两个文件的 md5 并比对 | ✅ 可跑，已验 |
| **`pnpm build` 前置门** | `package.json` 的 `build` **当前只**是 `vite build` | ❌ **未落成构建前置** |

**我没有把 `tokens:check` 挂到 `build` 之前**：那会改变阶段 C 的构建语义，且让「build 失败」的原因不再唯一。**建议由 Lead 在阶段 C 决定**：

```jsonc
// 方案 1：构建即校验
"build": "node scripts/sync-tokens.mjs --check && vite build"
// 方案 2（推荐，失败原因单一）：build 保持纯粹，CI 串行
"build": "vite build",
"ci": "node scripts/sync-tokens.mjs --check && node scripts/invariants.mjs && vite build"
```

---

## 4. 冒烟覆盖了什么 / 没覆盖什么

### 4.1 已覆盖（**均为沙箱内等价证据**，可复核）

| 层 | 覆盖 | 证据 | 通道 |
| --- | --- | --- | --- |
| 类型 | `src/**/*.ts` + 53 个 `.vue` 的 `strict` 检查 | B1/B2 | 不依赖自建通道 |
| SFC 编译 | 53 个 `.vue` 的 `parse/compileScript/compileTemplate/compileStyle` | D | 不依赖自建通道 |
| SSE 解析 | P3/P6/P8/P10/P11/P12 + 分包（1/3/7/64 字节）/ 多字节跨边界 / BOM / CRLF / 注释 / 多行 data / 空 data / 超限 | F | **需钩子**（纯函数） |
| 流式状态机 | §5.4 全表：终态唯一、HTTP 关闭≠终态、去重、孤立 `tool_end`、失败缺码、ACCEPTED 缺字段、未知事件名、心跳 | F | **需钩子**（纯函数） |
| 端到端流 | mock 真 `ReadableStream`（7 字节切片）→ 解析 → 状态机 | F | **需钩子**（纯函数） |
| 纯函数 | 计划/课表校验、输入门禁、幂等键、格式化、错误码映射 | F | **需钩子**（纯函数） |
| 设计系统纯度与不变量 | L3-only、无违禁状态/文案、零外部请求、零持久化、class 存在性、断点 6 档 | E + G | 不依赖自建通道 |
| tokens 同步 | 两文件逐字节一致（PowerShell 侧复算 md5） | C | 不依赖自建通道 |
| 门禁有效性 | 12 条规则反向注入全部按预期 FAIL | H | 不依赖自建通道 |

### 4.2 **未覆盖**（明确列出，不得被上面的绿光掩盖）

1. **`pnpm build` 未验证** → `dist/` 不存在；Rollup 依赖图解析、tree-shaking、分包（`manualChunks`）、
   CSS 抽取与 `cssCodeSplit`、`assetsInlineLimit` **都没跑过**。
2. **`pnpm dev` 未验证** → 开发服务器、HMR、`optimizeDeps` 预打包、`server.proxy` **没跑过**。
3. **组件渲染未验证** → 没有任何 `.vue` 被真正挂载过（既没有浏览器冒烟，也**没有**用自建通道替代）。
4. **核心链路未点击** → 「登录 → 课程助手（SSE 流式）→ 我的课表 → 学习计划 → 管理员」**没有在任何浏览器里点过**。
5. **真实网络路径未做** → `fetch` 到真实后端、真实 SSE 字节流、`AbortController` 的 10s/30s 超时、CORS/代理。
6. **CSS 计算样式与布局未做** → 无「页面级横向溢出 = 0」、无 6 宽度重排、无触控目标 ≥44px 实测、
   无表格卡片化（`data-label`）实测、无 `scroll-padding-top` 的 `#main.top ≥ 62` 实测（W1）。
7. **无障碍树与键盘走查未做** → 无 skip-link 的 `Tab/Enter` 真实焦点断言、无 `.steps__toggle` 聚焦可见（W2）实测、
   无 axe 扫描、无屏幕阅读器顺序。
8. **`matchMedia` 断点联动未做** → `ui.initBreakpoints()` 只在浏览器里有意义。
9. **真实 API 契约未对跑** → mock 按 `openapi_v0.1.json` 人工造；`types.gen.ts` 亦为人工转写（见 §6.3）。
10. **`prefers-reduced-motion` 未实测** → 只做了「全局唯一一处」的静态核对。
11. **管理端 multipart 上传未实测** → `FormData` + 202 + 批次轮询的 UI 通路没跑过。

---

## 5. 环境侧的两项刻意配置（换机器必看）

```yaml
# web/pnpm-workspace.yaml
allowBuilds:
  esbuild: false     # ⚠ 本沙箱限制下的**显式跳过**，不是「正确配置」
  vue-demi: false
nodeLinker: hoisted  # ⚠ 默认 isolated 在本机 Node 上不可用
```

- **`allowBuilds: false` 的真实原因是沙箱**：任何 postinstall 都 `EPERM -4048`；pnpm 11 把「有构建脚本但未批准」当错误（exit 1），
  显式写 `false` 才是「已知并接受跳过」。**普通开发机不会有这个问题**，请去掉或改 `true`。
  跳过本身安全：`@esbuild/win32-x64/esbuild.exe` 已落地；`vue-demi` 锁 Vue 3 默认即 v3 分支。
- **`nodeLinker: hoisted`**：默认 `isolated` 用 NTFS junction 表示依赖边，本机 Node 不跟随到 `.pnpm` 目标
  （`fs.realpathSync('node_modules/vite')` 返回 junction 自身、`lstatSync().isSymbolicLink() === false`），
  导致 `vite` 找不到同级 `picomatch/rollup/esbuild` → `ERR_MODULE_NOT_FOUND: picomatch`。
  **代价**：失去 pnpm 严格依赖隔离。**换回 `isolated` 必须删 `node_modules` 后重跑 `pnpm install`。**
- pnpm 11 起**不再读 `package.json` 的 `pnpm` 字段**（有 WARN），设置只能放 `pnpm-workspace.yaml`。
- scripts 一律 `node scripts/xxx.mjs` / `node node_modules/...`，不依赖 `node_modules/.bin` 垫片。

### 5.1 一个越出我写入范围的副作用

`pnpm install` 在**仓库根**建了 `.pnpm-store/`（`C:\...\Smart Campus Course Assistant\.pnpm-store\v11`）。
它在 `web/**` 之外，是 pnpm 自己的 store 路径解析结果，非我主动写入。
**请阶段 C 的 `.gitignore` 覆盖它**（我未在 `web/` 下写 `.gitignore`，按 Lead 指示留给收尾统一处理）。

---

## 6. 判断项与缺口登记

### 6.1 token 缺口（**登记缺口、不发明 token**）

按 `design/system/README.md` 纯度规则 4 原文——「禁止裸**色值**与带单位**裸长度**；允许**无单位数值**（含 `0`）」——
下列裸数值**不违规**，且 L3 确实未为它们建模，故按 `rb.css` 原值抄写并登记，与设计系统既有 8 处缺口登记同一口径：

| 位置 | 值 | 说明 |
| --- | --- | --- |
| `base.css` `.step__title` | `font-weight: 600` | `steps`/`step` 组无字重 token；`rb.css:249` 原文即裸 `600` |
| `base.css` `.field__req` | `font-weight: 600` | `field` 组无字重 token；`rb.css:316` 原文即裸 `600` |
| `base.css` `.cite__name` / `.table .cell-name` / `.empty__title` | `font-weight: 600` | 同上，均为 `rb.css` 原文 |

`base.css` 里 `.pill--warn, .pill--pending` 共用 `--pill-warn-*`：`rb.css:216` 两者本就同值，L3 只建模了 `--pill-warn-*` ——
**不发明 `--pill-pending-*`**，按现状复用。

### 6.2 未冻结文案的缺口（**不自造句子**）

对**没有冻结文案**的码，`domain/mapError.ts` 的 `mapErrorText()` 返回 `null`，界面只渲染 `code` + `request_id` + 已冻结的「重试」动作。
清单见 `domain/copy.ts` 的 `UNFROZEN_ERROR_CODES`（19 个码）。另：

| 缺口 | 我的处理 | 需要谁补 |
| --- | --- | --- |
| 19 个码的用户可见句子 | 只显示 code + request_id | **content-spec 需补** |
| 组件 chrome 文案（`请求编号`/`错误码`/`跳到主要内容`/`主导航`/`退出登录`/`主要内容`） | 集中登记在 `copy.ts` 的 `CHROME` | 按 `design/system/README.md` 裁决 13 的口径归**组件规格**管辖 |
| 通用表单动作 | 复用 `content-spec:170` 的 `取消`/`确认保存`（登记为**有意复用**） | content-spec 可补更贴切的 |
| 引用卡展开态的反向文案（「收起片段」类） | **不写**：展开态由 `aria-expanded="true"` 表达 | content-spec 需补 |
| `ErrorSummary` 标题句 | **不写**：容器 `role="alert"` 已整体播报，列表项 = 可见字段名 + 服务端 reason | 无需补 |
| 密码显示/隐藏切换 | **未实现**（§8.4 #6：文案从未冻结，`01-shell-navigation.md:936` 明令不得实现） | content-spec 需先冻结 |
| 过期/容量类提示（`DRAFT_EXPIRED` 等） | 已按 §3.4 行为要求建模，但**删掉了自造句子** | content-spec 需补 |

### 6.3 `types.gen.ts` 是**人工转写**，不是生成物

文件名来自 §2.1（「由 openapi 生成，勿手改」），但**阶段 B 没有引入代码生成器**，所以它是我按
`openapi_v0.1.json` 的 `components.schemas` **逐字段人工转写**的（字段名/类型/必填/枚举照抄）。文件头已如实标注。
**风险**：契约漂移不会在编译期暴露。**建议阶段 C**：换 `openapi-typescript` 产出同名文件，并把 §15.2 的
「字段名 ∈ openapi schema」契约测试跑起来。

### 6.4 判断项（无上游数值依据）

| # | 事项 | 取值 | 依据 |
| --- | --- | --- | --- |
| J1 | `document.title` 后缀 | ` · 校园课程智能助手` | §7.2「判断项 J2」 |
| J2 | 登录后回跳载体 | `session.pendingPath`（**内存**），仅 `planDetail` 回跳 | §7.3 G2 / §7.6 |
| J3 | 「新建计划」的载体 | **内联表单**（不新增路由） | §7.1 冻结 10 条 + CONTRACT §3.3「不得自创路由记录」 |
| J4 | `writeOps` 退避 | 1s→2s→4s→8s→10s 封顶，无步数上限；5 次未决转手动 | §6.9 唯一权威表 + §5.9 终止条件 |
| J5 | 批次轮询 | 3s，终态即停 | §6.10 |
| J6 | `capabilities` 参与菜单判定 | **不参与**（用 `user.role`） | §4.10-1 |

---

## 7. 与契约的**有意偏离**、以及**被撤回的自研代码**

### 7.1 对 `dsh/no-forbidden-states` 的显式窄化：保留**恰好一处** animation

- §10.4 字面把 `animation` 与 `:active`/`transition` 并列禁止；
- 但 §8.3（L1715–1725）以「本方向**唯一动效** `.step--running .step__ico` 旋转（`rb.css:252–253`，
  时长/缓动由 `--step-running-spin-duration`/`-easing` 承载）」作为全局 `prefers-reduced-motion` 重置的**依据**，
  `design/system/README.md` 裁决 9 也为它专设了 L3 token。一份文档不会为「不存在的动效」写 reduced-motion 依据。
- 处置（**Lead 已裁定**）：白名单到精确一处，且**必须消费 L3 token**（不硬编码 `1.1s linear`）：

```css
.step--running .step__ico { animation: spin var(--step-running-spin-duration) var(--step-running-spin-easing) infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
```

`prefers-reduced-motion` 重置**只在 `global.css` 一处**；组件层不得再写第二处。
不变量第 3 条与 stylelint `dsh/no-unknown-state` 都实现成「白名单 + **第二处即 FAIL**」，已用 `门禁3-a` 反向注入证明。
**打字机效果不做**（无 token，§8.3 明文）。

### 7.2 `chat → drafts` 的依赖边移到视图（§6.2 与 §6.5 的冲突）

§6.5 要求 `status` 事件带 `draft_id` 时调 `drafts.bind()`，但 §6.2 的静态依赖表**只允许** `chat → {session, ui, writeOps}`，
且 §6.16 验收点 2 会机械核对「表之外没有新的依赖边」。**处置**：状态机只把 `draftId`/`draftVersion` 记在 turn 上，
由视图侦测后调 `drafts.bind()` + `load()` —— 符合 §2.2 R5「只有 views 可以读多个 store 并组合」。`chatMachine.ts` 文件头已写明。

### 7.3 `chat` 的第二遍 `reduce` 只做终态预言机

§2.3 的 `startChatStream` 契约要求返回 `terminal`，但 `StreamHandlers` 没有「把 turn 交回」的通道。
**处置**：`stream.ts` 内部维护一个本地 turn 仅用于推导终态（同一份纯 reducer，结论必然一致），
store 侧仍以 `applyEvent()` 为唯一状态入口。多跑一次纯函数，无副作用。

### 7.4 `ErrorSummary` / `EmptyState` 不新增 class

§10.4 要求组件使用的每个 class 逐字存在于 `rb.css`。因此列表排版与动作行居中**不新增 class**，
改用 `base.css` 里 `.error-summary ul` / `.error-summary li > span` / `.empty > .row` 的**后代选择器**。
（初稿时我曾在 `EmptyState.vue`/`ErrorSummary.vue` 里加 `.empty__actions`/`.error-summary__list`，
被不变量第 7 条抓出来后改成现在这样 —— 这也是那条规则有用的直接证据。）

### 7.5 其它

- `mapError.isPendingNotFailedCode()` 标注了 `EXECUTION_TIMEOUT`/`CALL_LIMIT_REACHED`/`STORAGE_UNAVAILABLE`
  为「待确认而非失败」（§3.4 的 504 行）；因文案未冻结（§6.2），界面目前只显示 code。
- `src/api/mock/sse.ts` 的演示触发词（`依据不足`/`检索失败`/`无终态`/`双终态`）只存在于 mock，**不是用户可见文案**。
- mock 的时间锚点 `MOCK_TODAY = 2026-10-22`、`MOCK_SCHEDULE_FAIL_DATE = 2026-10-25` 是**mock 数据取舍**，不是产品行为，已在 `README.md` 写明。

### 7.6 ⚠ **被撤回的自研代码清单**（Lead 裁决 = 选项 B）

**为什么撤回**：本沙箱禁止 `stdio:'pipe'` 子进程，Vite 起不来。我为了在无打包器环境下拿到「组件是否真能渲染」的证据，
自写了模块加载/解析钩子。**Lead 判定这属于「给沙箱缺陷造 loader」——会让「项目能不能跑」的结论只在自建通道下成立，
是验收假阳性。我同意，并已按裁决全部撤回渲染相关部分。**

| 文件 | 处置 | 原因 |
| --- | --- | --- |
| `scripts/vue-loader-hooks.mjs` | **已删除** | 现场编译 `.vue` 用的 `load` 钩子 → **为渲染自建通道**，属假阳性风险 |
| `scripts/ts-resolve-hooks.mjs` | **已删除** | 与上一个配套的双文件钩子结构 → 同上；重整进单文件后用不到了 |
| `scripts/smoke-ssr.mjs` | **已删除** | 把 store 数据喂给视图做 SSR 字符串渲染 → **正是 Lead 明确禁止的「用假阳性冒充跑通」** |
| `scripts/ts-alias-hook.mjs` | **保留（已收窄为最小）** | 仅 `@/` 别名 + `.ts` 扩展名解析，**只**给纯函数级 `smoke-sse.mjs` 用；不挂 `load`、不碰 `.vue`、不渲染 |

**撤回后 `scripts/` 只剩 6 个文件**：`sync-tokens.mjs`、`invariants.mjs`、`check-sfc.mjs`、
`smoke-sse.mjs`、`verify-gates.mjs`、`ts-alias-hook.mjs`。

**保留件的边界（不越界声明）**：
- **不参与构建**：`pnpm build` / `pnpm dev` 走标准 Vite 配置，与本文件无关；它不改 `vite.config.ts` / `tsconfig.json` / 任何 `src/**`。
- **不是构建证据**：只在 `--import` 显式启动的测试进程里生效；删掉不影响交付物。
- **不做渲染**：只让 `smoke-sse.mjs` 能 import 到**纯逻辑模块**（`domain/*`、`api/sse/parse.ts`、`mock/sse.ts`、`mock/db.ts`）。
- **没有**为了让 `dist/index.html` 存在而接任何自建打包器 —— 那会比 loader 严重得多，会变成「标准工程 + 自研构建」两套路径。

---

## 8. `tokens.css` 的 520 行 vs 519 token（避免以后被当 bug 追）

`design/system/tokens.css` 的声明行数是 `520`，token 数是 `519`。**差值不是 bug**：
L0 兼容层里有 24 个与 L2 同名的变量**不再重复声明**（重复会让变量自引用而失效，见生成器注释），
加上 L3 的 `--root-scroll-offset` 也走同样的排除规则，因此「声明行数」比「token 数」多 1。
判定口径：**以 `tokens.json` 的 token 数为准，`^\s*--` 计数只能当粗筛。**

`--root-scroll-offset` 的 L3 值是 `calc(var(--shell-appbar-h) + var(--p-space-1))` = L2 + L1，
按纯度规则 3（尺度类原语可直取 L1）合规；`global.css` 只写 `scroll-padding-top: var(--root-scroll-offset)`，
**不硬编码 `calc(...)`**（W1 的落位要求）。

---

## 9. 相关文件

- 环境与取舍说明：[`README.md`](README.md)
- 完整自验转录（**每节标注通道**）：[`verify-transcript.txt`](verify-transcript.txt)
