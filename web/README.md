# web/ —— 校园课程智能助手前端

Vue 3 + TypeScript + Pinia + vue-router 4，Vite 构建。**Phase 4 起默认走真实后端**（`/api/v1` 经 Vite proxy → `127.0.0.1:8100`），mock 降级为**显式开启**的开发夹具。

> 本目录按模块边界组织骨架；阶段 B 交付 mock 骨架，**阶段 4（并行车道 F）完成真实后端联调**：
> `types.gen.ts` 由 OpenAPI 生成、401 统一会话失效、HTTP 级 E2E + 浏览器冒烟、契约漂移门禁。
> 证据与未覆盖项：阶段 B 见 [`BUILD-REPORT.md`](BUILD-REPORT.md)，阶段 4 见 [`reports/PHASE-04-REPORT.md`](reports/PHASE-04-REPORT.md)。

---

## 0. 常用命令

整套前后端（MySQL + 后端四服务 + 本目录 dev server）用仓库根的一键脚本：

```powershell
cd ..                        # 仓库根
.\scripts\start.ps1          # 起全套并做完健康检查；-NoFrontend 只起后端，-Mock 走 mock 夹具
.\scripts\status.ps1         # 巡检
.\scripts\stop.ps1           # 停止
```

单独跑前端：

```powershell
cd web
pnpm install                 # 仅首次（本工作树的 node_modules 是联接，见 §1.4）
pnpm build                   # 期望 exit 0
pnpm dev                     # http://localhost:5173，默认连真实后端 8100
pnpm check                   # 前端车道门禁（tokens/类型/SFC/不变量/types 漂移/流式冒烟/stylelint）
pnpm types:gen               # 由 OpenAPI 生成 src/api/types.gen.ts（默认设计包真源）
pnpm types:check             # 生成物漂移门禁（不一致 exit 1）
pnpm types:diff              # 设计包 vs 后端运行态 OpenAPI 的结构契约门禁（需后端在线）
pnpm e2e                     # HTTP 级真实链路 E2E（需后端 8100）
pnpm e2e:proxy               # 同上，但经 Vite proxy（验证 /api 代理）
pnpm smoke:browser           # 浏览器冒烟（Edge headless + CDP；--login/--pages 见脚本头）
```

> 端口/账号/停止方式见 `../docs/STARTUP.md`；dev server 默认只绑 `localhost`（本机解析到 `::1`），
> 探活用 `http://localhost:5173/`，用 `127.0.0.1` 会被拒连。

**mock 是显式 opt-in**：`VITE_USE_MOCK` 只有等于 `'true'` 才启用 mock 传输层；未设置/其他值一律走真实后端。
这样生产构建不会因为漏配 `.env` 而把 mock 假数据当成产品发布（PHASE-PLAN D5：验收以真实后端为准）。

```powershell
# 仅调试 UI、没有后端时：
$env:VITE_USE_MOCK='true'; pnpm dev      # PowerShell
# 或：VITE_USE_MOCK=true pnpm dev          （bash）
```

## 1. 本机环境的两个**刻意**设置（换机器要看这一节）

`pnpm-workspace.yaml` 里有两项不是「最佳配置」，而是**本沙箱环境限制下的显式取舍**。
换到普通开发机 / CI 时请重新评估，尤其是 `nodeLinker`。

> **一句话把边界说准**：本沙箱拒绝的是 **`child_process` 的 `stdio:'pipe'` 通道**（`spawn EPERM`），
> **不是 esbuild 缺失** —— esbuild 的**原生 CLI 完全可用**：
> ```
> esbuild.exe --version                        -> 0.25.12            exit=0
> esbuild.exe <f>.js --bundle --outfile=<o>.js  -> 产出 93 B          exit=0
> node -e "require('esbuild').transform(...)"   -> Error: spawn EPERM  exit≠0
> ```
> Vite 恰好用那条管道通道来起 esbuild 服务、并用来 bundle `vite.config.ts`，所以
> **`vite build` / `vite dev` 在沙箱内起不来**；**同一份代码在沙箱外（你自己机器上直接跑 `pnpm build`）是正常的**。
> 详见 [`BUILD-REPORT.md`](BUILD-REPORT.md) §1。

### 1.1 `allowBuilds: { esbuild: false, vue-demi: false }` —— 本沙箱限制下的**显式跳过**

**真实原因不是依赖有问题，而是沙箱禁止「用管道 stdio 生成子进程」**：
任何包的生命周期脚本（postinstall）都会失败，报

```
code: 'EPERM', syscall: 'spawn', errno: -4048
[ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: esbuild@0.25.12, vue-demi@0.14.10
```

pnpm 11 把「有构建脚本但未批准」当作**错误**（exit 1）。显式写 `false` 表示「已知并接受跳过」，
`pnpm install` 才会以 0 退出。**普通开发机不会有这个问题**，请把这两项去掉或改成 `true`。

跳过是安全的，因为：
- `esbuild` 的 postinstall 只做校验/兜底下载 —— 平台包 `@esbuild/win32-x64` 已由 pnpm 作为
  optionalDependency 落地，`esbuild.exe`（10.6 MiB）已在 store 内；
- `vue-demi` 的 postinstall 只切换 Vue 2/3 的 shim —— 本工程锁 Vue 3，默认即 v3 分支。

> pnpm 11 起**不再读 `package.json` 的 `pnpm` 字段**（会给出
> `[WARN] The "pnpm" field in package.json is no longer read`），这类设置只能放 `pnpm-workspace.yaml`。

### 1.2 `nodeLinker: hoisted` —— 本机 Node 不跟随 pnpm 的 junction

pnpm 默认的 `isolated` 布局用 NTFS **junction** 表达依赖边。本机 Node 解析时不跟随到 `.pnpm` 目标：

```
fs.realpathSync('node_modules/vite')            → .../web/node_modules/vite      （未解析到 .pnpm）
fs.lstatSync('node_modules/vite').isSymbolicLink() → false
```

于是 `vite` 找不到同级的 `picomatch` / `rollup` / `esbuild`：

```
Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'picomatch' imported from
  ...\web\node_modules\vite\dist\node\chunks\dep-CkSfqg8D.js
```

`nodeLinker: hoisted` = npm 式扁平 `node_modules`（真实目录 + 硬链接），Node 解析正常。

**可移植性代价**：失去 pnpm 的严格依赖隔离（未声明的依赖也能被 import）。
本骨架只有 `vue` / `vue-router` / `pinia` 三个运行时依赖，影响可控。
**换机器 / CI 换回 `isolated` 时，必须删除 `node_modules` 后重跑 `pnpm install`**（linker 变更不会被增量安装可靠地接手）。

### 1.3 脚本一律用 `node scripts/xxx.mjs` 形式

`package.json` 的 scripts 不依赖 `node_modules/.bin` 垫片 —— junction 不可 follow 时，
垫片是最先崩的一环（`pnpm exec` 本身也会触发一次 `pnpm install` 的依赖状态检查）。

---

## 2. 目录结构（与前端详细设计 §2.1 一致）

```
web/
├─ index.html  vite.config.ts  tsconfig.json  tsconfig.node.json  package.json
├─ pnpm-workspace.yaml           # pnpm 11 的构建设置 + nodeLinker（见 §1）
├─ .stylelintrc.cjs              # 分层纯度门（§8.2 冻结路径）
├─ stylelint-rules/layer-purity.cjs
├─ scripts/
│  ├─ sync-tokens.mjs            # design/system/tokens.{css,ts} → src/styles/（逐字节 + md5 校验）
│  ├─ invariants.mjs             # 10 项机械不变量（可进程内调用 runInvariants()）
│  ├─ check-sfc.mjs              # 53 个 .vue 的 SFC 编译检查（@vue/compiler-sfc，进程内）
│  ├─ smoke-sse.mjs              # 24 项**纯函数**级流式冒烟（domain/* + api/sse/parse.ts + mock）
│  ├─ verify-gates.mjs           # 12 项门禁反向注入自测（证明门禁真的会 FAIL）
│  └─ ts-alias-hook.mjs          # ⚠ 测试专用最小解析钩子（@/ 别名 + .ts 扩展名）；边界见下
└─ src/
   ├─ main.ts  App.vue           # App.vue = 外壳（顶栏 / 底部标签栏 / <main id="main">）
   ├─ styles/
   │  ├─ tokens.css              # 生成物：design/system/tokens.css 的逐字节副本（勿手改）
   │  ├─ tokens.ts               # 生成物：design/system/tokens.ts 的逐字节副本（断点真源）
   │  ├─ global.css              # html/body/*/h1–h4/p/a/code/:focus-visible/reduced-motion
   │  └─ base.css                # 27 个组件族样式（按族分块 + rb.css 行号锚点）
   ├─ api/
   │  ├─ client.ts errors.ts types.gen.ts transport.ts
   │  ├─ auth.ts me.ts chat.ts admin.ts citations.ts
   │  ├─ sse/ parse.ts stream.ts
   │  └─ mock/ db.ts handlers.ts sse.ts index.ts
   ├─ domain/                    # 纯函数：不碰 DOM、不碰 store、不碰 api
   │  ├─ constants.ts copy.ts sseTypes.ts
   │  ├─ chatMachine.ts dedupe.ts validate.ts mapError.ts format.ts breakpoints.ts
   ├─ stores/                    # 8 个，名字冻结：session/chat/schedules/plans/drafts/writeOps/admin/ui
   ├─ router/  index.ts routes.ts guards.ts
   ├─ components/ base/(27 族)  product/(5 组合件)
   ├─ views/                     # S01–S12
   └─ a11y/  live.ts focus.ts
```

**两处对 §2.1 的补充（已与 Lead 确认）**：
1. `src/styles/tokens.ts` —— §2.1 的 `styles/` 只列了 3 个文件，但 §8.3 明文要求
   `import { breakpoints } from '@/styles/tokens'` 来驱动 `matchMedia`。它与 `tokens.css`
   **同一个同步脚本、同样做哈希校验**。
2. `src/domain/copy.ts`、`src/domain/sseTypes.ts`、`src/api/transport.ts`、`src/api/mock/*`
   是 §2.1 未列出的文件。理由分别是：冻结文案的唯一落点、SSE 类型契约（让 `domain` 不必 import `api`，
   满足 §2.2 R1）、可替换传输层（让 mock 也跑真实代码路径）、mock 数据。**没有新增目录**。

---

## 3. 设计系统落地：`tokens.css` 是生成物

**任何时候想改样式数值，唯一合法路径**（§8.1）：

```powershell
# 1) 改 design/system/tokens.json
python design\system\generate.py            # → design/system/tokens.{css,ts}
python design\system\verify-system.py       # 独立校验
# 2) 同步到 web/
cd web
node scripts\sync-tokens.mjs                # 逐字节复制 tokens.css + tokens.ts
node scripts\sync-tokens.mjs --check        # CI 门：不一致即非 0
```

- `src/styles/tokens.css` 由 `python design\system\generate.py` 生成后同步，**勿手改**。
- 组件 `<style>` **只消费 L3 token**（形如 `--<组件>-<部位>-<属性>`）；出现 `var(--p-*)`（L1）
  或 `var(--bg-*)` / `var(--text-*)`（L2）即违纪（`design/system/README.md` 纯度规则 4）。
- 断点只用 `tokens.json` 的 6 档（base/xs 480/sm 768/md 1024/lg 1200/xl 1440），
  由 `src/styles/tokens.ts` 的 `breakpoints` 经 `domain/breakpoints.ts` 驱动 `matchMedia`；
  **只有 `ui` store 维护当前档位**，组件不得各自 `resize`。

### 关于 `animation` 的显式窄化

`base.css` 里**恰好一处** animation（`.step--running .step__ico` 的旋转），且消费 L3 token
`--step-running-spin-duration` / `--step-running-spin-easing`；`@keyframes` 也只有 `spin` 一个。
`prefers-reduced-motion` 重置只在 `global.css` 一处。

依据：rb.css:252–253 是本方向唯一动效，`design/system/README.md` 裁决 9 为它专设了 L3 token，
前端详细设计 §8.3（L1715–1725）以它作为 reduced-motion 重置的依据。
`:active` 与 `transition` 仍然**全禁**。这是对 §10.4 / `dsh/no-forbidden-states` 字面表述的**有意窄化**，
细节见 `stylelint-rules/layer-purity.cjs` 文件头与 `BUILD-REPORT.md`。

---

## 4. mock 层：开发夹具，**显式开启**，跑真实代码路径

> **Phase 4 起 mock 不再是默认路径**：验收一律 `VITE_USE_MOCK=false` + 真实后端 8100；
> mock 只用于没有后端时调试 UI。`useMock()` 仅在 `VITE_USE_MOCK === 'true'` 时返回真，
> 未设置/其他值都走真实 `fetch`（防止生产构建漏配 env 时把假数据当产品发布）。

`api/transport.ts` 把「怎么发请求」抽成可替换的 `Transport`：

- `httpTransport` = 原生 `fetch`（生产路径，§1.2 锁定「不引 axios」）；
- `mockTransport` = 同源 `/api/v1/*` 的路由处理器，返回**真正的 `Response`**（含 `ReadableStream` body）。

因此 `client.ts` 的信封解包、`sse/stream.ts` 的 `getReader()`、`sse/parse.ts` 的字节级增量解析、
`chatMachine` 的状态机**全部是真实代码**，只有最外层的「字节从哪来」被替换。
mock 的 SSE 流还**故意按 7 字节切片**，必然把中文/多字节字符切在中间，
从而在冒烟阶段就真实覆盖 `TextDecoder({stream:true})` 的码点边界。

切到 mock（仅调试 UI）：`$env:VITE_USE_MOCK='true'; pnpm dev`；切回真实后端：去掉该环境变量即可。

### mock 数据的时间锚点与演示触发词

| 项 | 值 | 说明 |
| --- | --- | --- |
| `MOCK_TODAY` | `2026-10-22` | content-spec 的样例日期。用真实系统日期会让 S07「有课」永远看不到 |
| `MOCK_SCHEDULE_FAIL_DATE` | `2026-10-25` | 查这一天返回 503 `RETRIEVAL_UNAVAILABLE`，用来验 S08 ②「课表无法读取」与 ① 「当天无安排」是**两种**状态 |
| 演示账号 | `student_demo` / `admin_demo`，密码 `demo1234` | `admin_demo` 才有 `/admin/*` 入口 |

助手提问里带下列**测试关键字**可切演示脚本（关键字只存在于 mock，不是用户可见文案）：

| 关键字 | 演示的状态 |
| --- | --- |
| （无） | S03 过程反馈 → S04 有据回答 + 引用 → S06 草稿 + 保存成功 |
| `依据不足` | S05 ① 检索成功但无足够依据 |
| `检索失败` | S05 ② 依赖异常（`tool_end` 失败 + `error` 事件） |
| `无终态` | A7：有写意图但**流关闭而无终态** ⇒ `unknown` ⇒ 落「待确认」并轮询核实 |
| `双终态` | A6：`done` 之后再来 `error` ⇒ 忽略第二个并记 `double-terminated` 协议违规 |

---

## 5. 自验

```powershell
cd web
pnpm install

# —— 沙箱内可跑（不依赖任何自建通道）——
node node_modules\vue-tsc\bin\vue-tsc.js --noEmit -p tsconfig.json   # typecheck（strict）
node node_modules\typescript\bin\tsc --noEmit -p tsconfig.node.json  # vite.config.ts
node scripts\sync-tokens.mjs --check                                 # tokens 逐字节一致
node scripts\check-sfc.mjs                                           # 53 个 .vue 编译
node scripts\invariants.mjs                                          # 10 项不变量
node node_modules\stylelint\bin\stylelint.mjs "src/**/*.{css,vue}"   # 分层纯度门
node scripts\verify-gates.mjs                                        # 12 项门禁反向注入自测

# —— 需要测试专用最小解析钩子（**纯函数**级，不涉渲染）——
node --import ./scripts/ts-alias-hook.mjs scripts/smoke-sse.mjs      # 24 项流式冒烟

# —— 必须在**沙箱外**（普通开发机 / CI）跑；沙箱内不可运行，见 §1 ——
pnpm build                                                           # ← dist/ 由这一条产出
pnpm dev                                                             # 然后浏览器点通核心链路
```

`scripts/ts-alias-hook.mjs` 的边界（**别误读**）：它**不参与构建**、**不是构建证据**、**不做任何渲染**；
只给 `smoke-sse.mjs` 补「`@/` 别名 + `.ts` 扩展名」两条路径约定。曾用于渲染的 3 个钩子文件已按 Lead 裁决删除，
清单与原因见 [`BUILD-REPORT.md`](BUILD-REPORT.md) §7.6。

原始输出与结论见 [`BUILD-REPORT.md`](BUILD-REPORT.md)；
逐步转录（**每节标注通道**）见 [`verify-transcript.txt`](verify-transcript.txt)。
