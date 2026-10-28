# web/ —— 校园课程智能助手前端

Vue 3 + TypeScript + Pinia + vue-router 4，Vite 构建。**默认连真实后端**（`/api/v1` 经 Vite proxy →
`127.0.0.1:8100`）；mock 是**显式开启**的开发夹具，不是默认路径（验收一律走真实后端）。

## 0. 常用命令

整套前后端（MySQL + 后端四进程 + 本目录 dev server）：在仓库根执行 `.\scripts\start.ps1`。

本目录：

| 命令 | 作用 |
| --- | --- |
| `pnpm dev` | dev server，<http://localhost:5173>，默认连真实后端 8100 |
| `pnpm build` | 生产构建（沙箱内不可运行，见 §1） |
| `pnpm typecheck` | `vue-tsc` + `tsc`（strict） |
| `pnpm lint:styles` | stylelint 分层纯度门 |
| `pnpm check:sfc` | 56 个 `.vue` 的 SFC 编译检查 |
| `pnpm check:invariants` | 10 项机械不变量 |
| `pnpm check:gates` | 12 项门禁反向注入自测（证明门禁真的会 FAIL） |
| `pnpm smoke` | 24 项纯函数级流式冒烟（不涉渲染） |
| `pnpm check` | 车道门禁合集：tokens + 类型 + SFC + 不变量 + 类型漂移 + 冒烟 + stylelint |
| `pnpm tokens:sync` / `pnpm tokens:check` | token 生成物同步 / 逐字节漂移门 |
| `pnpm types:gen` / `pnpm types:check` | 由 OpenAPI 生成 `src/api/types.gen.ts` / 生成物漂移门 |
| `pnpm types:diff` | 设计契约 vs 后端运行态 OpenAPI 的结构对比（需后端在线） |
| `pnpm e2e` / `pnpm e2e:proxy` | HTTP 级真实链路 E2E（直连 8100 / 经 Vite proxy） |
| `pnpm smoke:browser` | 浏览器冒烟（headless + CDP；`--login` / `--pages` 见脚本头） |

## 1. 本机环境的两个刻意设置

`pnpm-workspace.yaml` 里有两项不是「最佳配置」，而是本沙箱环境限制下的显式取舍。换到普通开发机 /
CI 时请重新评估，尤其是 `nodeLinker`。

> **边界说准**：本沙箱拒绝的是 **`child_process` 的 `stdio:'pipe'` 通道**（`spawn EPERM`），
> **不是 esbuild 缺失**。esbuild 的原生 CLI 完全可用；但 Vite 用那条管道通道起 esbuild 服务并
> bundle `vite.config.ts`，所以 **`vite build` / `vite dev` 在本沙箱内起不来**；同一份代码在沙箱外
> （普通开发机 / CI）是正常的。

- `allowBuilds: { esbuild: false, vue-demi: false }`：pnpm 11 把「有构建脚本但未批准」当错误（exit 1），
  显式写 `false` 表示「已知并接受跳过」。跳过是安全的——平台包 `@esbuild/win32-x64` 已落地，
  `vue-demi` 的 postinstall 只切 Vue 2/3 shim（本工程锁 Vue 3）。
- `nodeLinker: hoisted`：本机 Node 不跟随 pnpm 的 junction，`isolated` 布局下 `vite` 找不到同级依赖，
  故用 npm 式扁平 `node_modules`。**换回 `isolated` 时必须删 `node_modules` 后重装**。
- 脚本一律 `node scripts/xxx.mjs` 形式，不依赖 `node_modules/.bin` 垫片。

## 2. 目录

```
web/
├─ index.html  vite.config.ts  tsconfig.json  tsconfig.node.json  package.json
├─ pnpm-workspace.yaml           # pnpm 11 的构建设置 + nodeLinker（见 §1）
├─ .stylelintrc.cjs              # 分层纯度门
├─ stylelint-rules/layer-purity.cjs
├─ scripts/
│  ├─ sync-tokens.mjs            # token 生成物同步（逐字节 + md5 校验）
│  ├─ invariants.mjs             # 10 项机械不变量（可进程内调用 runInvariants()）
│  ├─ check-sfc.mjs              # 56 个 .vue 的 SFC 编译检查
│  ├─ smoke-sse.mjs              # 24 项纯函数级流式冒烟
│  ├─ verify-gates.mjs           # 12 项门禁反向注入自测
│  ├─ gen-types.mjs              # OpenAPI → src/api/types.gen.ts
│  ├─ contract-diff.mjs          # 契约漂移对比
│  ├─ e2e-real.mjs               # HTTP 级真实链路 E2E
│  ├─ e2e-docs.mjs               # 资料批次链路段
│  ├─ cdp-smoke.mjs              # 浏览器冒烟（CDP）
│  └─ ts-alias-hook.mjs          # 测试专用最小解析钩子（@/ 别名 + .ts）
└─ src/
   ├─ main.ts  App.vue           # App.vue = 外壳（顶栏 / 底部标签栏 / <main id="main">）
   ├─ styles/
   │  ├─ tokens.css              # 生成物，勿手改
   │  ├─ tokens.ts               # 生成物，断点真源
   │  ├─ global.css              # html/body/*、h1–h4、p、a、code、:focus-visible、reduced-motion
   │  └─ base.css                # 27 个组件族样式
   ├─ api/                       # client / errors / transport / types.gen + 各域封装
   │  ├─ sse/ parse.ts stream.ts # 字节级增量解析 + 流式客户端
   │  └─ mock/ db.ts handlers.ts sse.ts index.ts
   ├─ domain/                    # 纯函数：不碰 DOM / store / api
   ├─ stores/                    # 8 个：session/chat/schedules/plans/drafts/writeOps/admin/ui
   ├─ router/                    # index / routes / guards
   ├─ components/                # base/(27 族) + product/(5 组合件)
   ├─ views/                     # 各页面视图
   └─ a11y/                      # live.ts focus.ts
```

## 3. 样式与 token 约束

- `src/styles/tokens.{css,ts}` 是**生成物**，**勿手改**；改数值走设计源 → `pnpm tokens:sync`，
  `pnpm tokens:check` 做逐字节校验（不一致即非 0）。
- 组件 `<style>` **只消费 L3 token**（形如 `--<组件>-<部位>-<属性>`）；出现 L1（`var(--p-*)`）或
  L2（`var(--bg-*)` / `var(--text-*)`）即违纪，由 `stylelint-rules/layer-purity.cjs` 拦截。
- 断点只用 `src/styles/tokens.ts` 的 6 档（base/xs 480/sm 768/md 1024/lg 1200/xl 1440），由
  `domain/breakpoints.ts` 驱动 `matchMedia`；**只有 `ui` store 维护当前档位**，组件不得各自 `resize`。
- 动效显式窄化：`base.css` 只有一处 animation（`.step--running .step__ico`，消费 L3 token），
  `@keyframes` 只有 `spin`，`prefers-reduced-motion` 重置只在 `global.css`；`:active` 与 `transition` 全禁。
  细节见 `stylelint-rules/layer-purity.cjs` 文件头。

## 4. mock 层：开发夹具，显式开启，跑真实代码路径

`useMock()` 仅在 `VITE_USE_MOCK === 'true'` 时返回真；未设置/其他值都走真实 `fetch`
（防止生产构建漏配 env 时把假数据当产品发布）。

`api/transport.ts` 把「怎么发请求」抽成可替换的 `Transport`：`httpTransport` = 原生 `fetch`（生产路径，
不引 axios）；`mockTransport` = 同源 `/api/v1/*` 的路由处理器，返回**真正的 `Response`**（含
`ReadableStream` body）。因此信封解包、`getReader()`、字节级增量解析、对话状态机全部是真实代码，
只有最外层的「字节从哪来」被替换。mock 的 SSE 流**故意按 7 字节切片**，必然把多字节字符切在中间，
从而在冒烟阶段就真实覆盖 `TextDecoder({stream:true})` 的码点边界。

切到 mock（仅调试 UI）：`$env:VITE_USE_MOCK='true'; pnpm dev`；切回真实后端：去掉该环境变量。

mock 演示触发词（只在 mock 生效，不是用户可见文案）：

| 关键字 | 演示的状态 |
| --- | --- |
| （无） | 过程反馈 → 有据回答 + 引用 → 草稿 + 保存成功 |
| `依据不足` | 检索成功但无足够依据 |
| `检索失败` | 依赖异常（`tool_end` 失败 + `error` 事件） |
| `无终态` | 有写意图但流关闭而无终态 ⇒ 落「待确认」并轮询核实 |
| `双终态` | `done` 之后再来 `error` ⇒ 忽略第二个并记协议违规 |

## 5. 自验

```powershell
cd web
pnpm install

# —— 沙箱内可跑（不依赖任何自建通道）——
node node_modules\vue-tsc\bin\vue-tsc.js --noEmit -p tsconfig.json   # typecheck（strict）
node node_modules\typescript\bin\tsc --noEmit -p tsconfig.node.json  # vite.config.ts
node scripts\sync-tokens.mjs --check                                 # tokens 逐字节一致
node scripts\check-sfc.mjs                                           # 56 个 .vue 编译
node scripts\invariants.mjs                                          # 10 项不变量
node node_modules\stylelint\bin\stylelint.mjs "src/**/*.{css,vue}"   # 分层纯度门
node scripts\verify-gates.mjs                                        # 12 项门禁反向注入自测
node --import ./scripts/ts-alias-hook.mjs scripts/smoke-sse.mjs      # 24 项流式冒烟

# —— 必须在沙箱外（普通开发机 / CI）跑，见 §1 ——
pnpm build                                                           # dist/ 由这一条产出
pnpm dev                                                             # 然后浏览器点通核心链路
```

`scripts/ts-alias-hook.mjs` 的边界（**别误读**）：它不参与构建、不是构建证据、不做任何渲染；
只给 `smoke-sse.mjs` 补「`@/` 别名 + `.ts` 扩展名」两条路径约定。

## 6. 注意

dev server 默认只绑 `localhost`（本机解析到 `::1`），探活用 <http://localhost:5173/>；
`http://127.0.0.1:5173/` 会被拒连。
