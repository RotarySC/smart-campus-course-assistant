# 阶段 A 独立验证报告（task-2）

**验证者**：`rb-verifier`（独立验证者，非修复者）
**被验修订**：阶段 A 修复（task-1，owner `fix-rb`）
**验证日期**：2026-10-23
**写入范围**：本文件（`design/reviews/rb-verify-report.md`）+ 平台临时目录；被验收文件一律只读，未做任何修改

---

## 0. 结论摘要

| # | 判据 | 判定 | 一句话依据 |
| --- | --- | --- | --- |
| **W1** | 锚点 / skip-link 目标不被 sticky 顶栏遮挡 | **PASS** | 13 个宽度实测遮挡 **0px**（基线 57 / 56.67px）；真实 Tab+Enter 后 `activeElement = MAIN#main` |
| **W1-b** | 768–774px 顶栏变高是否已治本、且未换成宽度溢出 | **PASS（含一条轻微残留）** | 13 宽度 `appbarH` 恒 **56.67**、页面溢出恒 0、无内容裁切；仅 768–773px 右内边距被挤到 11.67px（非裁切） |
| **W2** | `<480` `.steps__toggle` 聚焦有可见焦点指示 | **PASS** | 真实 Tab 命中第 14 个焦点；补偿环像素级取证 **1554 px，100% 落在环带**；反注入归 0 |
| **W2-b** | `≥480` `display:none` 是否让折叠控件丢功能 | **PASS** | `display:none` 移出 Tab 序，但 `.steps__body` 默认 `flex`（225.7px / 73 字 / 3 步），内容零丢失；`<480` 真键盘 Space 仍可展开/收起 |
| **W3a** | `.kv__v` 60 字符无空格串 320px 页面溢出 | **PASS** | 0（基线 +444）；反注入回落 +444 |
| **W3b** | `.cite__name` / `.card__body` / `.bubble` 同上 | **PASS** | 三处均 0（基线 +255 / +296 / +296）；反注入分别回落 |
| **#1** | 「处理中」→`pill--info`；「需确认后继续」仍 `pill--warn` | **PASS** | 232/302 = info；519 = warn（**未误改**）；已传导到 `b-responsive.html` |
| **#3** | `records.html:273` `.pill--danger` 带合规 svg | **PASS** | `<svg>` 六项属性全合规格；尺寸写法与仓库既有 pill 图标写法一致 |
| **#6** | content-spec 冻结文案与 `aria-pressed` | **PASS** | 两态逐字文案 + `aria-pressed` 语义已冻结；`login.html` **MD5 未变**，未越界实现控件 |
| 反向验证 | 5 脚本 / token 等价 / 六宽度 / 判据敏感性 | **PASS** | 5 脚本全 0 FAIL；75/75 等价（双通路）；六宽度溢出 0；负向对照全部按预期 FAIL |

**总判定：6 个必修项全部 PASS，未发现必修级新缺陷。** 有 2 条轻微残留 / 观察项、1 条判据层缺口、1 份文档待同步清单（均列于 §7–§9），都不阻塞阶段 A 收口。

---

## 1. 被验修订的字节冻结核验（无漂移）

Lead 冻结的 13 个文件，我逐一重算 MD5 与字节数：

```powershell
Get-FileHash -Algorithm MD5 <file>; (Get-Item <file>).Length
```

```
OK     design\responsive\rb.css                             0749FA7A47BC155F52A12406123DF6CC   23086B
OK     design\responsive\shell.html                         E8B7294B9B4A8424ACA94C17068F2F60    6064B
OK     design\system\tokens.json                            4EEA1276DC4A069C29DBE56A55B152D6   54283B
OK     design\system\tokens.css                             26EEE4F0348C6E4DA9DB1840D17F2163   30504B
OK     design\system\tokens.ts                              03607588E7EC217959DA681F51B363E7   16947B
OK     design\system\tokens.flat.json                       7D3050EEB85CD7122B40D8099F62531D   15674B
OK     design\system\tokens.md                              2A01AA51DABACC783D9219ECC3AC12AF   49473B
OK     design\responsive\b-responsive.html                  5B73454136F261AC13E9A0203C0C6D73  126723B
OK     design\responsive\parts\admin.html                   D35DAFE4E61D9F42ADFB94BCCB6C5761   35966B
OK     design\responsive\parts\records.html                 9ED257DC24A550AD0E9CE952298E9E71   17059B
OK     design\directions\shared\content-spec.md             5191543D3F42EEC73BE1478421810D3B   16637B
OK     design\system\README.md                              1FBDD745D6CC1CFE6C5739446BBC7C65   32682B
OK     design\system\components\01-shell-navigation.md      0C33CD918F3C90758CD873BB7229C3D1   75868B

>>> 漂移文件数: 0
```

**本报告所有实测数字都取自上述字节**（渲染测试前又抓了一次哈希快照，见 §10 `out/00-hashes.txt`，与冻结表逐条一致）。

---

## 2. 方法与独立性

### 2.1 为什么不用 proxy 的 `/eval`

`cdp-proxy.mjs` 只暴露 `/health /targets /new /close /navigate /back /eval /click /clickAt /setFiles /scroll /screenshot /info`（我通读了路由表，第 324–615 行）。**没有任何原始 CDP 透传端点**，因此拿不到：

- `Input.dispatchKeyEvent`（真实键盘 —— `:focus-visible` 的必要条件）
- `Emulation.setDeviceMetricsOverride`（改视口宽度）

### 2.2 第二套实现：自写极简 CDP 客户端

我从 `%LOCALAPPDATA%\Microsoft\Edge\User Data\DevToolsActivePort` 读出 `9222 / /devtools/browser/dd607a9a-…`，用 **Node v24 内建 WebSocket** 直连 browser endpoint，自己实现了 `Target.createTarget / attachToTarget(flatten) / Runtime.evaluate / Page.navigate / Page.captureScreenshot / Input.dispatchKeyEvent / Emulation.setDeviceMetricsOverride`（约 150 行，`$TEMP\rbverify\cdp.mjs`）。

**独立性声明**：

- 判据脚本 **全部自写**（`w1.mjs` / `w2.mjs` / `w3.mjs` / `sixwidth.mjs` / `band2.mjs` / `negctl.mjs` / `static.mjs` / `risks.mjs` / `tokens-browser.mjs`），**没有复用 fix-rb 的任何脚本**，也没有读它的判据实现去凑结论。
- 我没有 import `generate.py`；token 等价性我用**两条互相独立的通路**（自写文本解析器 + 真实浏览器 CSSOM/计算值）各算一遍。
- 我**没有采信 `rb-fix-report.md` 的自述**；它的每一处数字我都自己重测（§8 列出分歧/一致点）。

### 2.3 安全边界

- 只操作我自己 `/new` 出来的 tab；进入前后目标数均为 4（用户原有 4 个 tab 未触碰），每个 tab 测完 `/close`。
- 测完 `clearDeviceMetricsOverride`。
- 全部仓库文件只读；负向对照只做**运行时 `<style>` 注入**或**平台临时目录副本**。

---

## 3. W1 —— 锚点 / skip-link 遮挡：**PASS**

### 3.1 原始命令

```powershell
cd $env:TEMP\rbverify
node w1.mjs "http://127.0.0.1:8799/design/responsive/b-responsive.html" "320,390,479,480,767,768,775,1024,1366"
node w1.mjs "http://127.0.0.1:8799/design/responsive/b-responsive.html" "770,772,773,774"
```

`w1.mjs` 做两件事，**都走浏览器真实路径**：

1. `location.hash='#v-S11'` → 浏览器按 `scroll-padding-top` 定位；
2. **真实键盘**：`Input.dispatchKeyEvent` 发 `Tab`（焦点落到 `.skip-link`）→ 发 `Enter` 激活 → 读 `#main` 几何。

遮挡判据（Lead 裁定，我采用）：`occlusion = .appbar.getBoundingClientRect().bottom − 目标.getBoundingClientRect().top`，要求 **≤ 0.5px**。

### 3.2 原始输出（13 个宽度）

```
=== SUMMARY ===
w= 320 appbarH= 56.67 spTop=  62px | #v-S11 top=   61.7 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 390 appbarH= 56.67 spTop=  62px | #v-S11 top=  61.67 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 479 appbarH= 56.67 spTop=  62px | #v-S11 top=  61.75 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 480 appbarH= 56.67 spTop=  62px | #v-S11 top=  62.04 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 767 appbarH= 56.67 spTop=  62px | #v-S11 top=     62 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 768 appbarH= 56.67 spTop=  62px | #v-S11 top=  61.81 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 770 appbarH= 56.67 spTop=  62px | #v-S11 top=  62.06 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 772 appbarH= 56.67 spTop=  62px | #v-S11 top=  62.06 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 773 appbarH= 56.67 spTop=  62px | #v-S11 top=  62.06 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 774 appbarH= 56.67 spTop=  62px | #v-S11 top=  62.06 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w= 775 appbarH= 56.67 spTop=  62px | #v-S11 top=  62.06 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w=1024 appbarH= 56.67 spTop=  62px | #v-S11 top=  62.23 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
w=1366 appbarH= 56.67 spTop=  62px | #v-S11 top=  62.23 occ=      0 | #main top=  56.67 occ=      0 activeEl=MAIN#main
```

### 3.3 判定理由

- `html` 计算值 `scroll-padding-top = 62px`（13/13 宽度），即 `--root-scroll-offset` 真的解析成了 62px（`rb.css:84` 声明、`rb.css:94` 消费）。
- 目标 `top` 落在 61.67–62.23 之间，sticky 顶栏底 56.67 → **遮挡 0px**。基线对照：`#v-S11` 遮挡 57px（文档 56.4）、`#main` 遮挡 56.67px（文档 56.7）—— 我自己的夹具在修复前复现过这两个数（见 `out/` 与下文 §6.4）。
- **阈值 0.5px 的理由**：遮挡量是 `appbar.bottom − target.top` 的直接几何差；sticky 顶栏完全遮住目标意味着差 > 0。取 0.5px 是为吸收子像素取整（本环境 `appbar.height = 56.66666793823242`，坐标存在 ~1/3 px 级取整）。62 − 56.67 = 5.33px 的余量远大于取整噪声，所以这个阈值既严格又不脆弱。
- **`activeIsMain = true`**：真实键盘激活 skip-link 后 `document.activeElement` 是 `MAIN#main`（`shell.html:62` 已补 `tabindex="-1"`），说明焦点确实落到了主内容上——这比"页面滚了但焦点还在链接上"更符合 skip-link 的意图。
- **注意**：文档 §8.4 的字面判据 `#main.top >= 62 − 0.5` 在我这里恒为 **false**（`#main.top = 56.67`）。这不是缺陷，而是**该判据对 `#main` 不适用**：`#main` 紧跟在文档流顶部的 appbar 之后，`scrollY` 被 clamp 到 0，`top` 永远到不了 62；正确断言应当用「遮挡 ≤ 0.5px」（Lead 已裁定改用它，我同意）。`#v-S11` 那一侧文档判据是成立的。**建议把 §8.4 里 `#main` 的判据改为遮挡式**，否则未来实现者会照抄一条永远失败（或永远无意义）的断言。

### 3.4 W1 反向对照（证明判据真的会 FAIL）

```powershell
node negctl.mjs "http://127.0.0.1:8799/design/responsive/b-responsive.html"
```

```
### NEG-1  W1 scroll-padding-top 关掉 --> 遮挡应回来
  fixed : {"appbarBottom":56.67,"top":61.67,"occlusion":0,"spTop":"62px"}
  killed: {"appbarBottom":56.67,"top":-0.33,"occlusion":57,"spTop":"auto"}
  -> 判据敏感: YES
```

同一页面、同一夹具，只注入 `html{scroll-padding-top:auto!important}`，遮挡立刻回到 **57px**、`spTop` 回到 `auto`。判据对真实原因敏感。

---

## 4. W1-b（阶段 A 追加）—— 768–774px 治本：**PASS，含一条轻微残留**

### 4.1 我在修复前独立发现的根因

修复前我实测：`<768px` 与 `≥775px` 顶栏 56.67px，但 **768–774px（7 个整数宽度）顶栏 72.17px**，因为 `.appbar__nav` 变 flex 后 4 个 navlink **文字换行**（nav 高 59.5px）。因此 62px 的 `scroll-padding-top` 在那个窄带里不够，`#main` 仍被遮挡 **10.00px**：

```
   768px appbarBottom= 72.17 | #v-S11 top=  61.98 occ= 10.19 | #main top=  62.17 occ=    10  <-- 仍被遮挡
```
（等价夹具：在基线页面上注入 `html{scroll-padding-top:62px}`）

**要害**：文档 §8.4 的判据 `#main.top >= 61.5` 在此时是 **62.17 → 通过**，即该判据会放行一个仍有 10px 遮挡的页面。这条我在修复前已报 Lead。

### 4.2 修复后复测：窄带消失

`band2.mjs` + `sixwidth.mjs` + `w1.mjs` 三处独立测量一致：

```
  width appbarH innerCl innerSc diff | navH navCl navSc | pillRight innerRight ok | pageOverflow
    766  56.67   751   751    0 |     0     0     0 |   732.67    732.67 OK  | 0
    767  56.67   752   752    0 |     0     0     0 |      734       734 OK  | 0
    768  56.67   753   753    0 |    44   482   482 |      741    734.67 CLIP | 0
    773  56.67   758   758    0 |    44   482   482 |      741       740 CLIP | 0
    774  56.67   759   759    0 |    44   482   482 |      741    740.67 OK  | 0
    775  56.67   760   760    0 |    44   482   482 |      742       742 OK  | 0
   1024  56.67   880   880    0 |    44   482   482 |   926.33    926.33 OK  | 0
```

- **顶栏恒 56.67px**（18 个宽度扫描 + 13 个判据宽度），nav 高 44px —— 换行消失，W1 的 62px 从此在所有宽度都够用。
- **没有把"高度增高"换成"宽度溢出"**：`pageOverflow` 恒 0；`.appbar__inner` 的 `scrollWidth − clientWidth` 恒 **0**（内部无滚动溢出）；4 个 navlink 的 `scrollWidth == clientWidth == 116`（文字未被裁）。
- 页面级横向溢出：六宽度 320/390/480/768/1024/1366 与 18 宽度扫描（含 1440）**全部 0**。

### 4.3 一条轻微残留（非缺陷，登记备查）

上表我标了 `CLIP`，但那是我第一版判据拿"内容盒右边界"比，**过严**。精确复测（`clip768.mjs`）：

```
768px  {"clientW":753,"inner":[0,752.67],"contentBox":[18,734.67],"pillR":741,"pillW":59,
        "pillBeyondInnerBorder":-11.67,"pillBeyondAppbar":-11.67,"pillIntrudesIntoPadding":6.33}
770px  {...,"pillIntrudesIntoPadding":4.33}
773px  {...,"pillIntrudesIntoPadding":1}
775px  {...,"pillIntrudesIntoPadding":0}
pill 内容检查 @768: {"text":"管理员","cl":59,"sc":59,"visible":"visible"}
```

- 「管理员」胶囊右缘 741px，`appbar__inner` 边框盒右缘 752.67px → **仍在盒内 11.67px，未被裁切**，文字完整、`visibility:visible`。768px 截图目视确认胶囊完整。
- 真实残留是：768–773px（6 个整数宽度）里，行内固有宽比内容盒宽约 6.3px，flex 只能把这点差值压进 `padding-right`，于是**视觉右间距从设计的 18px 收缩到最小 11.67px**（774px 起恢复 18px）。
- **定性**：不违反任何验收判据（无溢出、无裁切、无遮挡），是纯外观层面的轻微收缩。修法（供 Lead 裁决，我不动手）：把 `.appbar__inner` 的 `padding-inline` 在 sm 档略减，或允许 `.appbar__brand` 在该窄带内收缩若干 px。**不阻塞收口。**

---

## 5. W2 —— `.steps__toggle` 可见焦点：**PASS**

Lead 指出 fix-rb 测不出这条（程序化 `focus()` 不触发 `:focus-visible`）。我用**真实 `Input.dispatchKeyEvent`** 通道补上了。

### 5.1 原始命令与输出（`<480`）

```powershell
node w2.mjs "http://127.0.0.1:8799/design/responsive/b-responsive.html" "320,390,479,480,768"
```

```
{"width":320,"tabIndexToToggle":14,"toggleFocusVisible":true,"toggleOutline":"solid 2.66667px rgb(15, 74, 66)","toggleRect":{"w":1,"h":1},"labelDisplay":"flex","labelOutline":"solid 2.66667px rgb(15, 74, 66)","labelOutlineDrawn":true}
{"width":390,"tabIndexToToggle":14,...同上...,"labelOutlineDrawn":true}
{"width":479,"tabIndexToToggle":14,...同上...,"labelOutlineDrawn":true}
{"width":480,"tabIndexToToggle":null,"labelOutline":null,...}   <- ≥480：toggle display:none，进不了 Tab 序
{"width":768,"tabIndexToToggle":null,"labelOutline":null,...}
```

- 从**文档开头**真实 Tab，第 **14** 个焦点命中 `#s03-steps-toggle`（`tabIndexToToggle=14`，可复现）。
- 命中时 `toggle.matches(':focus-visible') === true` → 真实键盘通路确实触发了 `:focus-visible`。
- 该 toggle 对应的 `label.steps__summary`：`display:flex`、**338.67 × 44px 真实可见**，计算 `outline: solid … rgb(15,74,66)`（= `--focus` `#0F4A42`）、`outline-offset:2px`、`border-radius:4px`。

### 5.2 像素级取证（不靠眼睛，也不靠「规则存在」）

`w2-pixel2.mjs`：全视口截图 → **在浏览器里用 canvas 解码** → 统计目标 label 周围环带内的焦点色像素。

```
从文档开头真实 Tab 命中: #14  id=s03-steps-toggle
聚焦态: {"focusedId":"s03-steps-toggle","focusVisible":true,"labelOutline":"solid 2.66667px rgb(15, 74, 66)","rect":{"x":18,"y":458.7,"w":338.7,"h":44}}
  聚焦态像素: {"region":[8,448,367,513],"focusColorPixels":1554,"focusColorOnRingBand":1554}
  反向注入「.steps__toggle:focus-visible ~ .steps__summary{outline:none!important}」后: {"focusColorPixels":0,...}
  注入后 computed outline = none
  失焦态像素: {"focusColorPixels":0,...}
  失焦 computed outline = none
```

- **1554 个焦点色像素，1554/1554 全部落在 label 内框之外的环带上** → 画出来的确实是一圈**环绕摘要行的环**，不是别的东西。
- 失焦态 0 像素、`outline-style:none` → 环只在聚焦时出现。
- 反向注入后 0 像素 → 判据对"环存在"敏感。
- 目视复核（`shot/w2v2-focused.png`，390×900）：`本轮执行 · 3 项动作（1 项进行中）` 那行外侧有清晰的墨绿圆角环。

### 5.3 关于 `2.66667px`（必须显式声明的环境因素）

本环境把**指定 `3px`** 的 `outline-width` 算成 `2.66667px`。我用参照元素证伪了"这是本页面特有"：

```
参照元素：outline 指定值 vs computed 值
 "1px -> 0.666667px"
 "2px -> 2px"
 "3px -> 2.66667px"
 "4px -> 4px"
 "6px -> 6px"
 "30px -> 30px"
```

是 Chromium 在本 emulation（`devicePixelRatio ≈ 1.00000003`）下的 outline 设备像素取整，**与本次修复无关**（参照元素同样被缩放）。因此：
- 我**没有**用文档 §8.4 的 `outline-width ≥ 3px` 当门槛（那会误判成 FAIL）；
- 我改用「`outline-style !== 'none'` + 宽度 > 0 + 载体真实可见（有面积、`display!=='none'`）」+ 参照元素同宽 + 像素取证。

### 5.4 `≥480` 的 `display:none` 是否丢功能（Lead 重点提问）：**没丢**

```
### B) ≥480：.steps__toggle display:none 后的可折叠功能面
  480px -> {"toggleDisplay":"none","toggleFocusable":false,"labelDisplay":"none","bodyDisplay":"flex","bodyHeight":225.7,"bodyTextLen":73,"stepItems":3}
  768px -> {"toggleDisplay":"none","toggleFocusable":false,"labelDisplay":"none","bodyDisplay":"flex","bodyHeight":225.7,"bodyTextLen":73,"stepItems":3}
 1024px -> {"toggleDisplay":"none","toggleFocusable":false,"labelDisplay":"none","bodyDisplay":"flex","bodyHeight":225.7,"bodyTextLen":73,"stepItems":3}
```

- `display:none` 把 toggle 移出 Tab 序（真实 Tab 扫 400 次都到不了），同时 `.steps__body` 是 **`display:flex` 常显**（225.7px 高、73 字、3 个 `li.step`）→ **展开态即默认态，用户不可能因此丢失内容**。
- 这正是 `docs` §8.7 J2 声明的意图（"让 `.steps__body` 常显、toggle 与摘要一并 `display:none`"），实现与裁决一致。
- **`<480` 的折叠功能本身仍可用**（真键盘 Space 实测）：

```
### C) <480：真实键盘 Space 能否展开/收起
  Tab 命中 id=s03-steps-toggle  初始: {"checked":false,"bodyDisplay":"none","bodyH":0,"focusVisible":true}
  按下 Space 后: {"checked":true,"bodyDisplay":"flex","bodyH":225.7,"focusVisible":true}
  再按 Space 后: {"checked":false,"bodyDisplay":"none","bodyH":0,"focusVisible":true}
```

展开/收起来回一次都正确，且聚焦环全程可见 → 补偿环没有干扰控件的真实功能。

---

## 6. W3a / W3b —— 长串溢出：**PASS**

注入串：**60 个 `a`**（我明确声明所用字形；文档基线未记录字形，故绝对 px 不可比，语义可比）。

### 6.1 修复后：四容器全 0

```powershell
node w3.mjs "http://127.0.0.1:8799/design/responsive/b-responsive.html" 320 a --probe
```

```
--- baseline ---
  .kv__v        overflow=     0  wrap=break-word grid=136px 83.3333px  path=dd.kv__v < div.kv__row < dl.kv
  .cite__name   overflow=     0  wrap=anywhere  grid=none  path=span.cite__name < div.cite__head < div.cite
  .card__body   overflow=     0  wrap=anywhere  grid=none  path=div.card__body.stack < div.card < div.login
  .bubble       overflow=     0  wrap=anywhere  grid=none  path=div.bubble < div.msg.msg--user < div.chat
```

### 6.2 内容无关性（比基线更强的判据）

同一注入换成越来越"宽"的字形，**页面溢出恒 0**，且 `.kv__row` 第 2 轨恒 83.33px（不再被 min-content 撑开）：

```
--- glyph probe (.kv__v 第 2 轨 / 页面溢出) ---
  glyph=a  overflow=     0  track=136px 83.3333px  minContent=563.8
  glyph=m  overflow=     0  track=136px 83.3333px  minContent=955.8
  glyph=M  overflow=     0  track=136px 83.3333px  minContent=996.6
  glyph=W  overflow=     0  track=136px 83.3333px  minContent=1037.9
  glyph=0  overflow=     0  track=136px 83.3333px  minContent=598.2
  glyph=测  overflow=     0  track=136px 83.3333px  minContent=17
```

`min-content` 高达 1037.9px 的串也不再造成任何页面级横向滚动 → 修复是**内容无关**的，不是"恰好这个夹具不溢出"。

### 6.3 分根因分离（在**修复前**的冻结产物上做，因为修复后两根因已被同时消除）

我在准备期（`rb.css` 仍是基线 `94DF48ED…` 时）用运行时 `<style>` 覆盖做过分离实验：

- `A` = 只改 `.kv__row{grid-template-columns:8em minmax(0,1fr)}`
- `B` = 只加 `.cite__name,.card__body,.bubble{overflow-wrap:anywhere}`

```
--- baseline ---     .kv__v 444 | .cite__name 255 | .card__body 296 | .bubble 296
--- minmaxOnly ---   .kv__v   0 | .cite__name 255 | .card__body 296 | .bubble 296
--- wrapOnly ---     .kv__v 444 | .cite__name   0 | .card__body   0 | .bubble   0
--- both ---         .kv__v   0 | .cite__name   0 | .card__body   0 | .bubble   0
```

**与文档记载的机制完全一致**：只改 `minmax(0,1fr)` 只救 `.kv__v`；只加 `overflow-wrap` 只救其余三处；`overflow-wrap` 救不了 `.kv__v`（因为它不影响 min-content）。绝对 px 与文档的 +523/+359/+375/+375 不同，纯粹是因为文档没记录注入字形——上表 glyph probe 已给出这个敏感性证据。

### 6.4 修复后的分根因反注入（`negctl.mjs` NEG-3）

```
### NEG-3  W3 分别关掉两处修复 --> 溢出应按根因分别回来
  .kv__v        fixed=    0 killed=  444  -> 判据敏感: YES
  .cite__name   fixed=    0 killed=  255  -> 判据敏感: YES
  .card__body   fixed=    0 killed=  296  -> 判据敏感: YES
  .bubble       fixed=    0 killed=  296  -> 判据敏感: YES
```

关掉 `minmax` 只让 `.kv__v` 回落；关掉 `overflow-wrap` 只让另外三处回落，**数值与 6.3 的基线逐字相同** → 两条独立通路互相印证。

### 6.5 表格未被误伤

```
rb.css:346  .table .cell-name{overflow-wrap:break-word;min-width:180px;font-weight:600}
rb.css:360-361  .table--stack td{...grid-template-columns:7.5em minmax(0,1fr);...overflow-wrap:break-word}
```

文档 W3 修法明确要求「表格单元格仍用 `break-word` + `min-width`，不得改成 `anywhere`」——实测保持一致，未被顺手改坏。

---

## 7. #1 / #3 / #6

### 7.1 #1 —— 琥珀语义：**PASS**

`static.mjs` 独立解析 `<span class="pill …">` 元素（自写正则 + 行号回溯）：

```
admin.warnSites   [(519, '需确认后继续')]
admin.progressSites [(232, 'pill pill--info', '处理中'), (302, 'pill pill--info', '处理中')]
admin.mustWarn    [(519, 'pill pill--warn', '需确认后继续')]
built.progress  [{'line': 1701, 'cls': 'pill pill--info', 'text': '处理中'}, {'line': 1771, 'cls': 'pill pill--info', 'text': '处理中'}]
built.mustWarn  [{'line': 1988, 'cls': 'pill pill--warn', 'text': '需确认后继续'}]
```

- `admin.html:232`、`:302` 的「处理中」→ `pill--info` ✓（两处都改到，svg 保留）
- `admin.html:519`「需确认后继续」→ **仍是 `pill--warn`** ✓（**未误改**；我用"全文件只剩 1 个 pill--warn"这条更强的判据验证，而不只是看目标行）
- 改动已传导到生成物 `b-responsive.html`（1701/1771 = info，1988 = warn）✓

### 7.2 #3 —— 危险胶囊图标：**PASS**

```
recordsDanger [{ "line": 273, "cls": "pill pill--danger", "text": "不可恢复", "hasSvg": true,
  "attrs": { "fill":"none", "stroke":"currentColor", "stroke-width":"1.75",
             "aria-hidden":"true", "focusable":"false",
             "width":"24", "height":"24", "viewBox":"0 0 24 24",
             "style":"width:14px;height:14px" } }]
```

六项规格属性全部齐备且取值正确。

**尺寸写法一致性**（判据原文要求"与同文件其它 pill 的尺寸写法一致"）：`records.html` 的另外两个胶囊（`:30` `pill--advice`、`:203` `pill--evidence`）**都没有 svg**，所以同文件内无先例可比。我改与全仓写法比：

```
pillIconConvention { "24x24 style=width:14px;height:14px": 11, "NO-SVG": 5, "13x13": 25 }
```

- 本次新增的写法（`24×24` + 内联 `style="width:14px;height:14px"`）与 `admin.html:233/237` 等 **11 处**完全相同；
- 仓库更主流的写法是 `13×13`（**25 处**）；
- `components/02-actions-status.md:339` 明写「胶囊图标在冻结原型中统一 **13×13**（少数为 **14×14**，如 `admin.html:233/237`）」→ **两种都在规格允许范围内**。

结论：**合规，但与同文件的另两个胶囊仍不统一**（因为那两个本就没有图标——这正是 `02` 已登记的既有缺口）。若要完全统一，需要在 4 处无图标胶囊上一并补；这不在本轮 6 项范围内。

> 附带发现（既有文档瑕疵，非本轮引入）：`02-actions-status.md:375` 把 `records.html:203` 记为 `.pill--ok` 的 `check` 图标实例，但该行实际是 `pill--evidence`「plan_7Q2F9K」，且无 svg。建议 Lead 排入文档待同步。

### 7.3 #6 —— 密码切换契约冻结：**PASS（且未越界实现）**

content-spec 新增（`design/directions/shared/content-spec.md`，16637 B）：

```
L55: - 密码「显示/隐藏切换」按钮 —— **内容契约（阶段 A 冻结；控件本身尚未实现）**：
L56: - **两态文案（逐字，唯一来源）**：密码当前被遮蔽（默认态）时按钮文字 = **显示密码**；
L57: 密码当前明文可见时 = **隐藏密码**。不得只给图标不给文字，也不得简写成「显示」「隐藏」「眼睛」等。
L58: - **`aria-pressed` 语义** = 「密码当前是否已切换为明文可见」。默认 `aria-pressed="false"`（遮蔽，按钮名＝「显示密码」）；
L59: 切换后 `aria-pressed="true"`（明文可见，按钮名＝「隐藏密码」）。两态文案与 `aria-pressed` **必须始终一致**，
L60: 不得出现「按钮名＝显示密码但 `aria-pressed="true"`」这类自相矛盾的组合。
L62: - 行为：切换只把密码框的 `type` 在 `password` 与 `text` 之间改一次；**不得**清空已输入内容、不得移动焦点、不得触发校验。
```

两态可访问名 + `aria-pressed` 语义 + 一致性约束 + 行为边界，齐备。

**未越界实现**：`parts/login.html` 的 MD5 与我修复前抓的基线快照**完全相同**：

```
login { "bytes": 5495, "hasAriaPressed": false, "hasToggleWord": false,
        "svgCount": 4, "passwordCount": 3, "buttons": ["登录","登录","登录"] }
基线 MD5（准备期抓取）: 85EE3572452B0BAAB3A46844607C0E64   ← 与当前一致
```

→ fix-rb **只冻结契约、没有实现控件**，符合 §8.4 #6「先冻结再实现」与 `01-shell-navigation.md:936`「U9 未解决前该槽位不得实现」。这正是任务书要我重点确认的越界风险，结论是**未越界**。

---

## 8. 反向验证：判据是否真的会 FAIL

### 8.1 5 个校验脚本（我自己跑的）

```powershell
pwsh -File $env:TEMP\rbverify\run-validators.ps1
```

```
design\system\generate.py          exit=0
design\system\build-system.py      exit=0
design\system\verify-system.py     exit=0
design\responsive\build.py         exit=0
design\reviews\verify.py           exit=0
```

关键原始输出：

```
01-generate.txt:
  primitive 91 / semantic 41 / component 337 / compat 50 / 合计 519
  rb.css 等价 75/75
  [PASS] rb.css 等价性             75/75 逐值等价
  [PASS] 规则 prelude             58 条规则的 prelude 全部恰好是 :root
  FAIL 0 / WARN 0

02-build-system.txt:  组装通过：0 FAIL。产物已写出。
03-verify-system.txt: PASS 31 / WARN 0 / FAIL 0
     [PASS] H tokens.md 等价性声明  75/75
     [PASS] I README 计数一致      合计 519
     [PASS] J 声明可达性           519 个 token 在浏览器里都会真正生效
04-build-responsive.txt: 全部通过（class 契约 / data-label / 无 style / 无 @media / 无裸 hex / 无 emoji）
05-verify-reviews.txt: exit 0
```

**0 FAIL 全部由我自己的执行复现**（没有采信 Lead 或 fix-rb 的运行结果）。

修完 5 个脚本后我重测了全部哈希，与冻结表一致 → 脚本是确定性的、没有因为"我跑过"而改变被验字节。

### 8.2 静态负向对照（在平台临时目录副本里做）

把 `design/` + `docs/` 复制到 `$TEMP\rbverify\repocopy`，把 `rb.css` 的 `--h-appbar:56px` 改成 `58px`：

```
[FAIL] rb.css 等价性   --h-appbar 值不一致：rb.css=58px / tokens.css=56px
[FAIL] rb.css 等价性   --root-scroll-offset 值不一致：rb.css=calc(58px + 6px) / tokens.css=calc(56px + 6px)
FAIL 2 / WARN 0
生成失败：请先修 tokens.json，不要使用本次产出。
exit=1
```

判据真的会 FAIL，且这条还顺带证明了 `--root-scroll-offset` 确实由 `--h-appbar` 派生。**仓库文件未受影响**（全程只在副本里改）。

### 8.3 rb.css ↔ tokens.css 逐值等价（两条独立通路，均不 import generate.py）

**通路 1：自写文本解析器 + 递归 var() 解析**（`static.mjs`）

```
rbRootVars 75   tokensDecls 519
equivalence total=75 equal=75  valueDiff=[] missingInTokens=[] caseOnlyDiff=[]
```

**通路 2：真实浏览器 CSSOM + computed value**（`tokens-browser.mjs`；把两个文件分别注入两个同源 iframe，读 `getComputedStyle` 的 75 个共同变量）

```
{ "rbCount": 75, "tkCount": 519, "sharedCount": 75,
  "missing": [], "diff": [], "caseOnly": [],
  "sample": { "--bg-page": ["#FAF8F5","#FAF8F5"],
              "--accent": ["#14665B","#14665B"],
              "--root-scroll-offset": ["calc(56px + 6px)","calc(56px + 6px)"] } }
```

两条通路结论一致：**75/75 逐值相等、0 差异**（连大小写差异都没有）。注意 `rb.css` 的 `:root` 变量数已由 74 → **75**（新增 `--root-scroll-offset`），`tokens.css` 由 518 → **519**（L1 91 / L2 41 / L3 337 / L0 50）。

> 我第一版 PowerShell 数出 80 个，是因为把 `:root` 注释块里作为文档的 `--bp-*`（5 个）也数进去了；换成**注释感知**的解析器后是 75。这也是我坚持自写解析器的原因之一。

### 8.4 「六宽度页面级溢出为 0」重测（这条会被改 rb.css 直接影响）

```powershell
node sixwidth.mjs
```

```
=== 六宽度页面级溢出（无注入） ===
   320px  pageOverflow=  0  (scrollW=305 clientW=305)  appbarH=56.67
   390px  pageOverflow=  0  (scrollW=375 clientW=375)  appbarH=56.67
   480px  pageOverflow=  0  (scrollW=465 clientW=465)  appbarH=56.67
   768px  pageOverflow=  0  (scrollW=753 clientW=753)  appbarH=56.67
  1024px  pageOverflow=  0  (scrollW=1009 clientW=1009)  appbarH=56.67
  1366px  pageOverflow=  0  (scrollW=1351 clientW=1351)  appbarH=56.67
```

外加 18 个宽度扫描（320…1440，含 600/700/767/800/900/1000/1023/1100/1200）**全部 overflow=0**。重启后的这条历史结论在新的 `rb.css` 上依然成立。

### 8.5 旧计数残留反查（grep）

**已同步**：`design/system/README.md`（74→75、336→337、518→519、新增 `--root-scroll-offset` 行与 510→518→**519** 变更表）、`design/system/tokens.md`（91/41/337、75/75）、`design/system/generate.py:383,488`（75/50）、`design/system/verify-system-output.json`（519/75）、`design/system/README.md:331-332`（新哈希）。

**仍残留旧数字/旧哈希**（见 §9 清单）。

---

## 9. 三处新引入风险的独立裁决

### 9.1 `components/01-shell-navigation.md` 越界改动 —— **接受，契约骨架未受损**

它不在 task-1 的写入范围里，但改动原因是 `verify-system.py` 的 F 项「组内 token 未覆盖」是 FAIL 级：新 token 进了 `root` 组，不改规格必然 FAIL。我独立核了骨架与内容一致性（`risks.mjs`）：

```
owns 行: <!-- owns: root, focus, skiplink, sr, appbar, brand, navlink, tabbar, wrap, login -->
h1: # 外壳与导航（全局根 / AppBar / BrandMark / NavLink / Tabbar / TabbarItem / SkipLink / SR-only / Wrap / Login）
组件块数: 10
9 节齐备的块: 10 / 10
禁用评审 class 出现: []
规格引用 token 104 个，其中不在 tokens.flat.json 的: [ '--skiplink-fg' ]
  消费表 --root-scroll-offset: 文档写 62px / flat = "calc(56px + 6px)"
  消费表 --appbar-min-h: 文档写 56px / flat = "56px"
  消费表 --focus-outline-w: 文档写 3px / flat = "3px"
```

- `owns` 声明**逐字未变**（仍是 10 组，与 `tokens.json` 的 `root, focus, skiplink, sr, appbar, brand, navlink, tabbar, wrap, login` 一致），h1 未变，**10 块 × 9 节结构完好**，无禁用评审 class → **契约骨架没有被破坏**。
- 唯一的"不存在 token"命中 `--skiplink-fg` 是**我的正则的假阳性**：它出现在 `01:87` 的否定句「**无** `--skiplink-fg`；Vue 阶段应显式声明…」里，是在说明"这个 token 不存在"，不是引用。→ 无矛盾。
- 5 处就地替换我抽查了三处（`U3` 行、`§5` 消费表新行、`§6` 无障碍段），**说法与新 token 一致**：
  - `01:88` U3 行保留了历史现状「rb.css 无 `scroll-padding-top`」但紧接着写明「**已在阶段 A（实现期）修复**：L3 `root` 组新增 `--root-scroll-offset`，rb.css:84 声明、rb.css:94 由 `html{scroll-padding-top}` 消费（56px + 6px = 62px），不再待补」→ 不矛盾，是"现状→已修"的正确写法。
  - `01:148` 消费表新增行 `| html{scroll-padding-top} | --root-scroll-offset | 62px | rb.css:84 声明、rb.css:94 消费…` ✓
  - `01:157` 无障碍段补上了「解析值 62px」✓
  - `01:94` U9 行同步了 #6 的冻结结论（文案已冻结、控件未实现）✓

**一条轻微不一致（低）**：消费表把解析值写成 `62px`，而 `tokens.flat.json` 里是 `calc(56px + 6px)`。README 硬要求 2 说「解析值**必须与 `tokens.flat.json` 一致**」。二者语义相同（56+6=62），但字面不等。我进一步查了判据本身：

```powershell
grep -n "解析值|flat|calc|消费表" design/system/verify-system.py
# → 无「解析值」相关匹配；F 项只做「骨架 / 组归属不重不漏 / 组内覆盖」，H 项只核对 tokens.ts 断点与 tokens.md 等价性数字
```

即 **`verify-system.py` 并不机械校验消费表的「解析值」列**（grep 全文没有任何 calc/解析值 比对）。所以这一格既不会被抓，也不会误判 —— 真正值得记的是**这条硬要求目前没有判据覆盖**（与 README 自己总结的 M1 教训同类：文本层像了，但没有检查把它钉住）。

### 9.2 L3 值写成 `calc(var(--shell-appbar-h) + var(--p-space-1))` —— **接受，层级归属正确**

Lead 要我落实两点，我都独立查了：

**① 解析值是否真的逐字相同** → **是**。`tokens.flat.json`：

```
--shell-appbar-h      = "56px"        --p-space-1  = "6px"
--appbar-min-h        = "56px"        --h-appbar   = "56px"     --sp-1 = "6px"
--root-scroll-offset  = "calc(56px + 6px)"
```

浏览器通路也确认 `rb.css` 与 `tokens.css` 的 `--root-scroll-offset` 都是 `calc(56px + 6px)`，且页面 `html` 的**计算** `scroll-padding-top` 实测为 `62px`（§3.2，13/13 宽度）。所以文档字面的 `calc(--appbar-min-h + --sp-1)` 与实际落地值**解析结果相同**。

**② `--shell-appbar-h` 到底在哪一层** → **L2，不是 L3**（我自己按 `tokens.css` 的段界判定的，没有采信它的自述）：

```
分层段边界: [{"layer":"L1","line":27},{"layer":"L2","line":178},{"layer":"L3","line":255},{"layer":"L0","line":676}]
{"name":"--shell-appbar-h","line":240,"layer":"L2","decl":"--shell-appbar-h:var(--p-size-appbar);"}
{"name":"--appbar-min-h","line":298,"layer":"L3","decl":"--appbar-min-h:var(--shell-appbar-h);"}
{"name":"--root-scroll-offset","line":265,"layer":"L3","decl":"--root-scroll-offset:calc(var(--shell-appbar-h) + var(--p-space-1));..."}
{"name":"--p-space-1","line":74,"layer":"L1","decl":"--p-space-1:6px;"}
{"name":"--h-appbar","line":724,"layer":"L0","decl":"--h-appbar:var(--p-size-appbar);"}
{"name":"--sp-1","line":703,"layer":"L0","decl":"--sp-1:var(--p-space-1);"}
```

`--shell-appbar-h` 在第 240 行，落在 L2 段（178–254）内，值是 `var(--p-size-appbar)`（合法 L2→L1）。因此 `--root-scroll-offset`（L3）= **L2 + L1**，**不构成 L3 互引**，`verify-system.py` 的 B 项「L3 不互引」不会（也不应）FAIL。fix-rb 的理由成立。

（Lead 之前的表述"它应是 L1 或 L0"与实测不符：它是 L2。L2 是"尺寸/布局语义别名"层，`--shell-appbar-h`（顶栏高度语义）放 L2、`--appbar-min-h`（组件属性）放 L3，是符合本项目分层定义的。）

### 9.3 `≥480` 的 `.steps__toggle{display:none}` —— **接受，实测未丢功能**

见 §5.4：`display:none` 移出 Tab 序 + `.steps__body` 默认 `flex` 常显（225.7px / 73 字 / 3 步）+ `<480` 真键盘 Space 展开收起正常。与 `docs` §8.7 J2 原文一致，且**没有把折叠控件在需要它的宽度上变成不可达**（`<480` 仍可聚焦、仍有环、仍能操作）。

---

## 10. 「修复后是否引入了新缺陷」——我的独立扫描

结论：**没有发现新的必修级缺陷**。我一共提了 3 个假设并逐个实测，其中 1 个被自己的实验否证：

1. **`white-space:nowrap` 会不会把"高度溢出"换成"宽度溢出/裁切"？**
   → 实测 `pageOverflow` 恒 0、`inner.scrollWidth − clientWidth` 恒 0、navlink 文字未裁、胶囊未裁（在边框盒内 11.67px）。
   **残留**：768–773px 右内边距视觉收缩到 11.67px（§4.3）。非缺陷，登记。

2. **`shell.html` 新增 `tabindex="-1"` 会不会让 `#main` 拿到 `:focus-visible`，从而画出环绕 22,201px 高的整页巨环？**
   → 计算样式层面**确实会**：激活 skip-link 后 `#main` 的 `outline` = `solid 2.66667px rgb(15,74,66)`、`matches(':focus-visible') = true`、`rect.height = 22201.9`。
   → 但**像素层否证了它可见**：注入 `#main{outline:none}` 前后两张截图的逐像素差异只有 **5 个像素**（bbox `x=374, y=52–56`）。原因是 `outline-offset:2px` 把环画到 body 边缘之外（横向被视口裁掉），上边又被 sticky appbar 盖住。
   → **结论：不构成视觉缺陷**。这个假设是我自己提出、也由我自己证伪的，记录在此以免后续有人重复担心。
   （附带：`#main` 拿到焦点本身是**好事**——它让 `document.activeElement === #main` 成立，符合 §8.4 的意图。）

3. **`tabindex="-1"` 会不会破坏 Tab 序？** → 不会（`tabIndex` 属性值 −1，不进顺序聚焦；`<480` 下真实 Tab 序列第 14 位命中 steps toggle，与修复前一致）。

另外两项越界改动：`shell.html`（+14B，`<main id="main" tabindex="-1">`）与 `components/01-shell-navigation.md`（+710B）。**二者都在 `rb-fix-report.md` 里被显式披露**（报告 `:27/:55/:247-250` 写明了 `shell.html:62` 的改动、理由与自测），不是隐藏改动；`shell.html` 未列入 task-1 的写入范围，属**已披露的范围外改动**。

> **结案（Lead 裁定，2026-10-23）**：`shell.html` 的该处范围外改动**已被 Lead 追认**——理由是它为 §8.4 的 `activeElement === #main` 断言所必需，且我已实测无副作用（含我自己否证的"整页巨环"假设）。**「已披露 + 已追认」与「未披露」是两种性质完全不同的事**：前者是有据可查的工程决定，后者是流程缺陷。本项闭环。`components/01-shell-navigation.md` 的越界改动，Lead 同批复核后接受（见 §9.1）。

---

## 11. 与 fix-rb 自述的分歧 / 交叉印证

| 项 | fix-rb 自述 | 我的独立实测 | 关系 |
| --- | --- | --- | --- |
| W1 `#v-S11` | 「−5.0…−5.56」（即 `appbarBottom − top` 的有符号值） | `#v-S11 top = 61.67…62.23`，`appbarBottom = 56.67` → 有符号差 = **−5.00…−5.56** | **一致**（它报的是有符号差，我报的是遮挡量 0） |
| W1 `#main` | 0 | `top = 56.67`，遮挡 0 | **一致** |
| 9 个宽度 `appbarH` 恒 56.67 | 自报 | 我扫 **18 个宽度**（320–1440）全 56.67 | **一致且更强** |
| 缺口由胶囊右内边距吸收 | 自述 `inner.scrollWidth−clientWidth=0` | 确认 = 0；并量化到 **侵入 6.33px（768px）**，从不越出边框盒 | **一致 + 我补了量化** |
| W2 `<480` | 「测不出来」（程序化 focus 不触发 `:focus-visible`） | 用真实 Tab 通道测得：**第 14 焦点命中、环真实绘制（1554 像素）** | **我补上了它测不了的那条**，结论 PASS |
| `--shell-appbar-h` 是 L2 | 自述 L2 | 我按段界独立判定 = **L2**（`tokens.css:240`） | **一致** |
| `--root-scroll-offset` 解析值 | `calc(56px + 6px)` | 两条通路均 `calc(56px + 6px)`；页面计算值 62px | **一致** |
| 5 脚本全绿 | 自报 PASS 31 / FAIL 0 等 | 我自己重跑，逐条复现 | **一致** |
| `01-shell-navigation.md:` +1 行 + 5 处替换 | 自述 | 我无法拿到改动前字节，**只验证了改后结构与取值自洽**（§9.1） | **部分未能独立验证**（见 §12） |
| 文档旧计数清单（D/P/S 表） | 列了 D1–D7 / P1–P25 / S1–S6 | 抽样核对 `design/README.md:19,151`、`design/responsive/verification.md:306,308`、`docs/frontend-detail/parts/10-…:13`、`50-…:4,14,142,153`、`docs/frontend-detail/verification.md:390,413,667,687` —— **确实都还是旧数字/旧哈希** | **一致，它的清单是准的** |

**未发现 fix-rb 自述与实测矛盾的条目。** 唯一"分歧"是我把它的有符号差读成遮挡量时的口径差，已在表内澄清。

---

## 12. 未验证项清单（诚实声明）

1. **`01-shell-navigation.md` 的改动 diff 边界**：改动前哈希由 Lead 提供（`98EA16907882D7FA18F486ED68368A8F`，抓取于 12:34:55，早于该文件 mtime 12:43:22），且该哈希**不匹配 `design/` 树中任何当前文件**（我自己把 `design/` 下 57 个文件逐个算 MD5 扫过，0 命中）→ 可确认该文件**确实被手工编辑过**。
   两点证据要分开记，不能混在一句里：
   - **变更证据**：改动前哈希（`98EA1690…`，12:34:55）≠ 当前冻结值（`0C33CD91…`），且文件 mtime `12:43:22` 落在抓取之后；`98EA1690…` 在 `design/` 树里不匹配任何现存文件 —— 这条证明"**文件变了**"。姊妹规格 `02/03/04-*.md` 的 mtime 仍是上午 10:2x、哈希未动，可佐证只有 `01` 被本次触碰。
   - **类型证据**（**不是**变更证据）：`generate.py` 只写 `tokens.css` / `tokens.md` / `tokens.ts` / `tokens.flat.json`（源码 `:671-676`），全文没有向 `components/` 写入的代码 —— 这只说明"编辑**不可能**来自生成器"，**不能**用它推断文件被改过。
   但**逐行 diff 仍未被独立复现**（无改动前副本），因此「**恰好 +1 行 + 5 处替换**」这一具体边界**仍未验证**。我只验证了改后文件的骨架完整性与取值自洽性。正确的表述是「**改动事实已确认，diff 边界未验证**」——不升级为「已证实为 +1 行 + 5 处」。
2. **视口宽度来自 CDP `Emulation.setDeviceMetricsOverride`**，不是物理拖动用户窗口。这是等价夹具（布局由 CSS 决定），但不是"真人拖窗口"；我未做物理窗口缩放的交叉验证。
3. **只测了 Edge 一个引擎**（用户本机 Edge），未测 Firefox/Safari/移动端真机。`env(safe-area-inset-*)` 在本环境恒为 0，**刘海/圆角屏的 T6 待裁决项我没有验证**（文档也标为真机复测项）。
4. **`prefers-reduced-motion` 未实测**（本轮改动不涉及动效路径）。
5. **W3 注入只在 320px 做**（按判据要求）；未在其他宽度重做四容器注入矩阵。
6. **`system.html`（活样式手册）未做视觉复核**。它的外壳是 `static` 的 `shell-head`，W1 在其中**本就不复现**（README 已披露）；我复核了它的生成（`build-system.py` 0 FAIL、`verify-system.py` 的 G 项全 PASS），但没有再看图确认 W2 补偿环在手册里的表现。
7. **`#6` 的行为面不可测**：content-spec 冻结的是**契约**，`login.html` 未实现控件（这是正确的），所以"切换按钮"没有可测行为——只能核契约文本与"未实现"这一事实。
8. **屏幕阅读器未实测**：所有无障碍结论都是 DOM/CSS/像素层证据，没有 NVDA/JAWS/VoiceOver 实听。`aria-pressed` 语义、可访问名等只做了文本与属性核对。
9. **字体相关**：所有 px 都基于本机字体栈（`system-ui` → Segoe UI / Microsoft YaHei）。换字体会改变 §4.3 那个 6.33px 收缩量的具体数值（定性结论不变）。
10. **未验证 `docs/` 与 `design/README.md` 的同步**——按 Lead 指示我不改它们（不在任何写入范围），只列清单（§13）。

---

## 13. 文档待同步清单（报 Lead，我未做任何修改）

以下都**不在任何人的写入范围**，按 Lead 指示仅登记。`design/system/` 内部已同步，无需处理。

| 类别 | 文件:行 | 现状 | 应为 |
| --- | --- | --- | --- |
| 旧计数 | `design/README.md:19` | 「四层 **518** 个 token」 | 519 |
| 旧计数 | `design/README.md:151` | 「三层 token **518** 个」 | 519 |
| 旧哈希 | `design/responsive/verification.md:306` | `rb.css … 94DF48EDFFC1DC33858A545C3574048F` | `0749FA7A47BC155F52A12406123DF6CC` |
| 旧哈希 | `design/responsive/verification.md:308` | `b-responsive.html … 1DD81EAB2A90797AB01F4CEB0A645A17` | `5B73454136F261AC13E9A0203C0C6D73` |
| 旧计数 | `design/responsive/verification.md`（多处，74/518 语境） | 74 个共同 token / 518 | 75 / 519（或注明"阶段 A 前"） |
| 旧计数 | `docs/frontend-detail/parts/10-baseline-and-modules.md:13` | 「**518** 个 token 的四层设计系统」 | 519 |
| 旧计数 | `docs/frontend-detail/parts/50-design-system-and-a11y.md:4` | 「**518** 个 token」 | 519 |
| 旧计数 | `docs/frontend-detail/parts/50-design-system-and-a11y.md:14` | 「27 组、**336** 个」 | 337 |
| 旧计数 | `docs/frontend-detail/parts/50-design-system-and-a11y.md:142` | 「产物：**518 → 518+n**」 | 519 |
| 旧计数 | `docs/frontend-detail/parts/50-design-system-and-a11y.md:153` | 「四层 `:root`，**518** 个 token」 | 519 |
| 旧计数 | `docs/frontend-detail/verification.md:390,413,667,687` | 518 / 518→518+n | 519 |
| 旧哈希 | `docs/校园课程智能助手_前端详细设计_v0.1.md:1796` | 「哈希不变（`94DF48ED…`）」 | 更新或注明阶段 A |
| **判据** | `docs/校园课程智能助手_前端详细设计_v0.1.md` §8.4（W1 行） | 判据「`#main` 的 `top >= 62 − 0.5` 且 `activeElement === #main`」 | `#main` 的 `top ≥ 62` **永远不可达**（`scrollY` 被 clamp 到 0，实测恒 56.67）；应改为「遮挡 ≤ 0.5px」 |
| 文档瑕疵 | `design/system/components/02-actions-status.md:375` | 把 `records.html:203` 记为 `.pill--ok` 的 check 图标实例 | 该行实为 `pill--evidence`「plan_7Q2F9K」且无 svg（既有瑕疵） |
| 判据缺口 | `design/system/verify-system.py` | 无任何「消费表解析值 vs `tokens.flat.json`」比对 | README 硬要求 2 目前无判据覆盖（`01:148` 写 `62px`、flat 是 `calc(56px + 6px)` 无人抓） |

---

## 14. 原始命令与产物索引

全部原始输出保存在 `%TEMP%\rbverify\out\`（平台临时目录，UTF-8）：

| 文件 | 内容 |
| --- | --- |
| `00-hashes.txt` / `00-hashes.json` | 渲染测试前抓的哈希快照（与冻结表一致） |
| `01-generate.txt` … `05-verify-reviews.txt` | 5 个校验脚本的完整原始输出 |
| `10-sixwidth.txt` | 六宽度页面溢出 + 18 宽度 appbar 扫描 |
| `11-w1.txt` / `22-w1-band.txt` | W1 遮挡（13 个宽度，含 770/772/773/774） |
| `12-w2.txt` | W2 `<480` / `≥480` |
| `13-w3.txt` | W3 四容器 + 分根因 + 字形探针 |
| `14-negctl.txt` | NEG-1/2/3 反向注入 |
| `15-static.txt` | #1/#3/#6 静态解析全量 JSON |
| `16-tokens-browser.txt` | 浏览器通路 token 等价 |
| `17-risks.txt` | 层级归属 / 骨架 / 消费表一致性 |
| `18-band2.txt` | 768–775 顶栏带宽 + `≥480` 功能面 + Space 折叠 |
| `19-clip768.txt` | 胶囊裁切精确几何 |
| `20-mainfocus.txt` / `21-mainring.txt` | `#main` 焦点环假设的检验（被否证） |

判据脚本（自写）：`cdp.mjs` `w1.mjs` `w2.mjs` `w3.mjs` `sixwidth.mjs` `band.mjs` `band2.mjs` `clip768.mjs` `negctl.mjs` `static.mjs` `risks.mjs` `tokens-browser.mjs` `w2-pixel2.mjs` `mainfocus.mjs` `w1-sim.mjs`。

截图证据：`%TEMP%\rbverify\shot\`（`w2v2-focused.png` 焦点环、`w2v2-unfocused.png` 对照、`appbar-768/770/773/775.png` 顶栏、`skiplink-after.png`、`main-ring-on/off.png`）。

---

## 15. 给 Lead 的三条建议（不含必修项）——**均已结案（Lead 2026-10-23 裁定）**

1. **追认 `shell.html` 的范围外改动**（`<main id="main" tabindex="-1">`）：已披露、有理由、实测无副作用，且是 §8.4 那条 `activeElement` 断言的前提。→ **已追认**（见 §10 结案框）。
2. **把 §8.4 中 `#main` 的判据从 `top >= 61.5` 改成「遮挡 ≤ 0.5px」**：前者对 `#main` 恒为 false（无意义），而它在 768–774px 场景下还会放行 10px 的真实遮挡（修复前我已实测）。→ **本轮不改 `docs/`**（改主文档会改字节/哈希、降低"阶段 A 已验证"的可核对性，且主文档是生成物、须改分册再重跑 `build.py`）；Lead 已把本项与 fix-rb 的清单合并为 **`docs/frontend-detail/DOC-SYNC-PENDING.md` 的 TODO-1**（可执行登记册）。该登记册不在我的写入范围，我未修改。
3. **登记两条非阻塞残留**：(a) 768–773px 顶栏右内边距视觉收缩到 11.67px；(b) 消费表「解析值」列没有任何判据覆盖 —— 这次只是"62px vs calc(56px+6px)"的良性不一致，但同类问题下次可能藏住真错。→ **已登记**：(a) 入登记册第 4 节、留待下一轮；(b) 记为 **TODO-6**，并与 `design/system/README.md` 自己的 **M1 教训**（文本层像了、但没有检查把它钉住）明确同源。

> `design/` 类同步项（原 §13 清单）由 Lead 逐条抽查 8 条**全部 HIT**，已合并进上述登记册；本报告 §13 保留为独立留痕。
