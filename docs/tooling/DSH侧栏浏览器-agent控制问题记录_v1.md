# DSH 侧栏浏览器 · agent 控制能力问题记录

- 文档编号：CCA-TOOL-001
- 版本：v1
- 记录日期：2026-10-21（事件发生于 17:47–19:37，时区 Asia/Shanghai）
- 记录人：lead（Team Lead）
- 触发场景：本项目前端 UI/UX 方向稿需要"在真实浏览器中打开页面取证"（截图 / console / 网络请求），以验证四份 HTML 交付物
- 结论一句话：**官方侧栏浏览器不提供 agent 控制能力；agent 可控的浏览操作由本地插件补齐。本次会话中该能力始终不可用 —— 页面从未被挂载进侧栏面板，随后会话被回收，因此"浏览器取证"这条验收路径整条不可用。**

> 标注约定：
> **【实测】** = 本会话中我亲自调用工具并观察到的原始输出
> **【澄清】** = 用户直接告知的架构事实
> **【推断】** = 我基于上述证据的推理，未经证实
> **【未验证】** = 本会话未取得证据

---

## 1. 架构事实

### 1.1 能力归属

| 层 | 归属 | 说明 |
| --- | --- | --- |
| 侧栏浏览器（宿主面板） | DSH 官方 | 在 GUI 侧栏里承载页面，**不提供 agent 控制能力**【澄清】 |
| agent 可控浏览能力（导航 / 快照 / 截图 / console 等） | **本地插件** | 由本地插件补齐 agent 侧的控制通道【澄清】 |

### 1.2 `browser_status` 中对应的证据【实测】

```jsonc
{
  "backend": "sidebar",
  "config": {
    "localPatch": "optional",      // 本地补丁/插件是可选组件
    "allowFullCdp": false,
    "allowEvaluate": false,
    "allowDebugger": false,
    "sidebarTier": "dom"
  },
  "localBridge": {
    "checked": true,
    "source": "probe",
    "available": true,             // 插件被探测到
    "enabled": true,
    "authState": "granted",        // 已授权
    "patchVersion": "1.1.1",
    "hookVersion": "0.3.0",
    "electron": "44.7.0",
    "appVersion": "0.2.1-rc.2",
    "checkedAt": "2026-10-20T14:22:33.654Z",
    "coverage": {
      "rootPage": true,
      "oopif": "unverified",
      "worker": "unsupported",
      "har": "from_attach",
      "screenshot": "capture_page",
      "note": "P1 attaches the page target only; OOPIF/worker targets are out of scope"
    }
  }
}
```

### 1.3 由证据得出的关键区分【推断】

**"插件可用" ≠ "侧栏里有可被 agent 控制的页面"。**

- `localBridge.available: true`、`authState: "granted"`、`patchState.ok: true` —— 插件本身是**已探测、已授权、状态正常**的。
- 但同一时刻 `sidebar.state.webview = { via: "absent", count: 0 }` —— **没有任何 webview 被挂载**。
- 于是 agent 侧的每条命令都拿不到 page target，全部以 `tab_not_found` 失败。

失败点不在插件安装或授权，而在**宿主面板没有把页面挂载进当前会话/分栏**。

### 1.4 一个需要注意的观测细节【实测 + 推断】

`localBridge.checkedAt` = `2026-10-20T14:22:33.654Z`，而本次会话是 `2026-10-21`，两者相差约 21 小时；同时 `source: "probe"`。

**推断**：`localBridge` 的探测结果是**缓存值**，`available: true` 未必反映调用当下的真实状态。因此**不能仅凭 `localBridge.available` 判断"现在能用"**，必须以 `sidebar.state.webview` 与 `capabilities` 为准。【未验证】缓存的失效/刷新语义。

---

## 2. 现象与确切报错

### 2.1 第一轮（面板未挂载）

| # | 调用 | 结果【实测】 |
| --- | --- | --- |
| 1 | `browser_status` | `sessionAlive: false`、`tabs: []`、`browserGeneration: 0`、`idleMsRemaining: 300000`；`pane: { tabs: 53, browser: 1, active: null, mountedSession: "session-f23797bb-…" }`；`webview: { via: "absent", count: 0 }`；note：`浏览器尚未启动（懒启动：第一次需要页面的命令才会 spawn）` |
| 2 | `browser_open({url:"about:blank"})` | `tab_not_found: 侧栏里没有已加载的页面（懒加载）。用 browser_tab action=restore（可带 url）恢复，或在面板上手动点一次「恢复页面」。` |
| 3 | `browser_tab({action:"restore", url:"about:blank"})` | `{"commandId":"cmd-2b57f152","restored":false,"mounted":0,"reason":"既没能点掉恢复卡，也没能请面板把这张页开出来（面板可能不在当前会话/分栏）"}` |
| 4 | `browser_tab({action:"list"})` | 同 #2 的 `tab_not_found` |
| 5 | `browser_tab({action:"new", url:"http://127.0.0.1:8791/…"})` | 同 #2 的 `tab_not_found` |

`restore` 的内部尝试链（**最能说明问题的一条证据**）：

```jsonc
[
  { "step": "start",            "cards": 0, "webviews": 0, "via": "absent", "browserTabs": 1 },
  { "step": "no-card",          "cards": 0, "webviews": 0, "via": "absent", "browserTabs": 1 },
  { "step": "openTab",  "ok": true, "cards": 0, "webviews": 0, "via": "absent", "browserTabs": 2 },
  { "step": "openTab-no-mount", "cards": 0, "webviews": 0, "via": "absent", "browserTabs": 2 }
]
```

读法：**它确实成功新开了一张 browser 标签（`browserTabs` 1→2），但 webview 始终没有被挂上（`webviews` 恒为 0，`via` 恒为 `absent`）**。所以不是"没开页"，而是"开了页但没挂载到 agent 可控制的位置"。

### 2.2 第二轮（约 1 小时 24 分后重试，会话已关闭）

| # | 调用 | 结果【实测】 |
| --- | --- | --- |
| 6 | `browser_status` | `browserGeneration` 0→1、`pane.browser` 1→3、`pane.active = { id: "tab4", kind: "browser" }`、`pane.tabs` 53→55 —— **面板侧确实发生了变化**；但 agent 侧仍是 `sessionAlive: false`、`tabs: []`、`webview.via: "absent"`、`idleMsRemaining: 0` |
| 7 | `browser_open({url:"http://127.0.0.1:8791/design/directions/index.html"})` | `Error: session browser has been closed` |
| 8 | `browser_tab({action:"new", url: 同上})` | `Error: session browser has been closed` |

`idleMsRemaining: 0` 与配置 `idleCloseMs: 300000`（5 分钟）一致。

**推断**：会话因空闲被回收关闭，而 agent 侧无法自行重建（`browser_open` 与 `browser_tab new` 都被拒）。【未验证】是否存在主动重建会话的接口。

### 2.3 能力边界（即使挂载成功也绕不过）

来自 `capabilities` 与工具契约【实测】：

| 限制 | 内容 | 后果 |
| --- | --- | --- |
| `navigate` 接受的 scheme | 仅 `http` / `https` / `about:blank` | **不能直接打开 `file://`**；本地 HTML 必须经 HTTP 服务器提供 |
| `capabilities.unsupported` | `closeTab`、`network`、`evaluate`、`perf`、`har`、`debug` | **没有 `browser_network` / `browser_har`** → 无法用它证明"零外部请求"；**没有 `evaluate`** → 读不到计算样式；`perf` 不可用 |
| `capabilities.supported` | `listTabs`、`newTab`、`activateTab`、`navigate`、`snapshot`、`act`、`waitFor`、`screenshot`、`console`、`restoreTab` | 只要页面被挂载，截图与 console 是**可用**的 —— 所以唯一的阻塞点就是"挂载" |
| 其他 config | `allowFullCdp: false`、`allowEvaluate: false`、`allowDownload: false`、`allowFileUpload: false`、`allowDebugger: false`、`headless: true`、`viewport: 1280×720`、`maxTabs: 32` | 无全量 CDP；无下载/上传/调试通道 |

---

## 3. 根因分层

| 层 | 现象 | 证据 | 性质 |
| --- | --- | --- | --- |
| L1 宿主/面板层 | webview 未挂载到当前会话/分栏 | `openTab` 成功但 `openTab-no-mount`；`webviews` 恒 0 | **本次的直接阻塞点** |
| L2 会话生命周期层 | 空闲 5 分钟后会话被回收，agent 无法重建 | `idleMsRemaining: 0`、`sessionAlive: false`、`session browser has been closed` | 二次阻塞 |
| L3 能力边界层 | 不能开 `file://`；无 network/har/evaluate | `capabilities` + 工具契约 | 设计约束，非故障 |
| L4 沙箱交互层 | 无法绕过侧栏自起浏览器 | headless Chromium 启动失败（见 §4.2） | 环境约束 |

**主因是 L1**：本地插件（控制通道）就绪，但宿主面板没有可供控制的页面 —— 两者缺一不可。

---

## 4. 影响范围

### 4.1 对本次交付的影响【实测】

- **无法进行真实渲染验证**：截图、console 报错、实际计算样式、实际渲染像素对比度、390px 窄屏真实排布、hover/focus 实际样式，全部未取得证据。
- **无法用 `browser_network` / `browser_har` 证明"零外部请求"**，只能改用静态扫描（正则扫 `https?://` / `<img` / `<link` / `@import` / `src=`）作为等价证据。
- 因此 `task-5`（独立校验）的验收口径必须从"浏览器取证"改写为"静态等价证据"，并在交付物中显式声明未验证项。
- 受影响交付物：`design/directions/direction-{a,b,c}.html`、`design/ia/sitemap.html`、`design/directions/index.html`。

### 4.2 绕过尝试的结果

| 尝试 | 结果 |
| --- | --- |
| 本地静态 HTTP 服务器（`python -m http.server 8791`，供人查看） | **成功**（HTTP 200）。但只对**人**有效，agent 侧仍无渲染能力 |
| headless Edge（`msedge --headless=new --screenshot`） | **失败**：`FATAL:mojo\public\cpp\platform\platform_channel.cc:187 Check failed: . : 拒绝访问。 (0x5)` |
| 同上 + `--no-sandbox` / 工作区内 `--user-data-dir` | **仍失败**（同上 FATAL）；另有 `crashpad_client_win.cc:456 OpenProcess: 拒绝访问。 (0x5)`、`Failed to grant sandbox access to cache directory …: 拒绝访问。 (0x5)` |
| `chrome-headless-shell`（Playwright 自带）+ `--remote-debugging-port` | **失败**：进程立即退出，`ERROR:headless\app\headless_shell.cc:260] Multiple targets are not supported.`；CDP 端口未监听 |

【推断】本机 Chromium 的进程间通道（mojo named pipe）被运行沙箱拒绝，属环境约束，非配置可解。
**副作用提醒**：`chrome-headless-shell` 会在**当前工作目录**写入 `debug.log`（我已在收尾时删除）。后续再试时请指定工作目录或清理该文件。

### 4.3 不是"我一个人踩到"

【实测】同一会话中的另外两名成员独立撞到同一面墙，错误串一致：

- verifier：侧栏后端懒加载、tabs 为空，无法加载页面，遂全程改用自研第二实现做静态核算；
- ia-architect：`browser_open` / `browser_tab new` 返回 `tab_not_found`，`restore` 亦失败。

→ 可判定为**环境性/架构性问题，而非某个 agent 的误用**。

---

## 5. 我自己的规划错误（记录以免重犯）

我最初写给验证者的 `task-5` 任务书，把验收方法写成"用 `browser_open` 打开 `file://…` 取证，并用 `browser_network` / `browser_har` 确认无外部请求"。

这一句**同时假设了两个不成立的前提**：

1. `navigate` 接受 `file://` —— 实际只接受 `http`/`https`/`about:blank`；
2. `browser_network` / `browser_har` 可用 —— 实际在 `capabilities.unsupported` 里。

**正确做法**：派发任何"浏览器取证"类任务之前，先跑一次 `browser_status` 并逐项读 `capabilities.supported` / `unsupported`、`config`、`sidebar.state.webview`，再据此写验收方法；不满足就把口径降级为静态等价证据，并把限制写进任务书。

---

## 6. 后续会话的前置检查清单（可操作）

派发"浏览器取证"任务前，按顺序确认：

1. `browser_status` → **`sessionAlive === true`**？
2. `browser_status` → **`tabs.length > 0`** 且 **`sidebar.state.webview.via !== "absent"`**？
   （`localBridge.available` 不足以判断，见 §1.4）
3. `browser_status` → `capabilities.supported` 是否包含本次需要的操作？（截图用 `screenshot`，报错用 `console`）
4. 目标 URL 是否为 **http(s)**？—— **不要用 `file://`**；本地文件请先起静态服务器。
5. 是否误用了 `browser_network` / `browser_har` / `evaluate` / `perf`？—— 这些**不可用**，请改用静态扫描或自研脚本。
6. 以上任一项不满足 → **不要把"浏览器取证"写进任务书**；改用静态等价证据，并在交付物中显式声明未验证项。

**恢复侧栏浏览器的方法（需要人在 GUI 侧操作）**：在 DSH 侧栏打开 browser 面板，让一张页真正加载出来（或点一次「恢复页面」），直到 `browser_status` 显示 `sessionAlive: true` 且 `tabs` 非空。

---

## 7. 复现步骤

```
# 1) 探测状态（关键：看 sessionAlive / tabs / sidebar.state.webview / capabilities）
browser_status()

# 2) 面板未挂载时，以下三条都会失败（tab_not_found）
browser_open({ url: "about:blank" })
browser_tab({ action: "restore", url: "about:blank" })
browser_tab({ action: "new", url: "http://127.0.0.1:8791/design/directions/index.html" })

# 3) 会话被回收后，错误变为 session browser has been closed
browser_open({ url: "http://127.0.0.1:8791/design/directions/index.html" })

# 4) 环境与版本快照
browser_status()   # 关注 localBridge.patchVersion / hookVersion / electron / appVersion
```

环境快照【实测】：`electron 44.7.0`、`appVersion 0.2.1-rc.2`、`localBridge.patchVersion 1.1.1`、`hookVersion 0.3.0`、`backend sidebar`、`headless true`、`viewport 1280×720`。

---

## 8. 待确认事项

| 编号 | 待确认内容 | 现状 |
| --- | --- | --- |
| T-01 | 官方侧栏浏览器与本地插件的能力边界：哪些操作属官方、哪些由插件补齐 | 仅有 §1.2 的字段证据，**未见插件源码**【未验证】 |
| T-02 | `localBridge.checkedAt` 的缓存语义：`available: true` 的有效期与刷新条件 | 观察到比会话早约 21 小时，**语义未知**【未验证】 |
| T-03 | 会话被 `idleCloseMs` 回收后，是否存在主动重建接口 | `browser_open` / `browser_tab new` 均被拒；**未找到重建方式**【未验证】 |
| T-04 | `openTab-no-mount` 的触发条件：是面板不在当前会话/分栏，还是插件 hook 未注入 | `restore` 的 reason 倾向后者之一，**无法区分**【推断】 |
| T-05 | `coverage.oopif: "unverified"`、`worker: "unsupported"` 是否影响原型评审 | 本次四份原型无 OOPIF / worker，**判定不影响**【推断】 |
| T-06 | 本机 Chromium 的 mojo 通道被拒，是否可通过宿主策略放行 | 已试 `--no-sandbox` / `--single-process` / 工作区 profile 均失败【未验证】 |

---

## 9. 相关文件

- `design/reviews/round1-verification.md` —— 独立校验报告，§13 声明了未验证项
- `design/reviews/verify.py` —— 静态等价校验器（本次用来替代浏览器取证）
- `design/reviews/verify-output.txt` —— 校验输出
- `design/directions/index.html` —— 评审入口，含"本次没有做真实浏览器渲染验证"的显式声明
