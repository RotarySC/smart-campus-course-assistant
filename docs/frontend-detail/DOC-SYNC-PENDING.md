# 文档待同步登记册（阶段 A 收口后）

> ## ✅ 已结清（2026-10-23，分支 `docs/align-rb-fix`）
>
> 本登记册列出的 TODO-1…TODO-6 **已全部处理完毕**，全量回归 6 个校验器 **0 FAIL**。
> 处理方式与「为什么当初只登记不立即改」如下：
>
> | TODO | 处置 | 实际改法 |
> | --- | --- | --- |
> | TODO-1 §8.4 判据 | ✅ 已改 | 判据换成**实测遮挡量** `occlusion = appbar.bottom − target.top ≤ 0.5px`，并**补齐 768/772/774**；删掉对 `#main` 恒为 false 的 `top >= 61.5` |
> | TODO-2 计数 | ✅ 已改 | `design/README.md`（2 处）、`docs/frontend-detail/build.py`（`:408` 源头、`:45` 移出已落地的处方 token） |
> | TODO-3 分册计数 | ✅ 已改 | `parts/10-…:13`、`parts/50-…:4/14/39/142/153`、`parts/90-…:28`；随后**重跑 `build.py` 重建主文档**（生成物，禁止手改） |
> | TODO-4 冻结哈希 | ✅ 已改 | `design/responsive/verification.md` 加 superseding 声明块（**保留原哈希**，不改写历史）；主文档 §8.6 表**新增「阶段 A 已完成」行** |
> | TODO-5 既有瑕疵 | ✅ 已改 | `design/system/components/02-actions-status.md:375` 的 `.pill--ok` 出处改正（原写 `records.html:203` 实为 `.pill--evidence`；真实 `check` 实例已逐一核到 `assistant.html:130/142/249/261/536`、`admin.html:67/279`） |
> | TODO-6 判据缺口 | ⬜ **未改（有意保留）** | `verify-system.py` 仍无「消费表解析值 vs `tokens.flat.json`」比对。**这属于新增判据，不属于「文档待同步」**，留作下一轮工程任务；本轮只在 README 侧记录 |
>
> **证据纪律**：所有历史验证报告（`design/responsive/verification.md`、`docs/frontend-detail/verification.md`）
> 内的旧哈希与旧计数**一律保留原值、只加注**——它们是当时的实测记录，回溯改写会破坏证据链。
>
> **主文档重建后**：`366,448 B / 4,388 行`，MD5 `725BECD070AA1FA8172499ECEB91CE04`，组装 **0 FAIL**。

**建立日期**：2026-10-23
**建立人**：lead（Team Lead）
**性质**：**登记，不是缺陷**。以下条目全部是「事实已改变、文档未跟上」，不涉及任何未修复的实现缺陷。
**来源**：`design/reviews/rb-fix-report.md` §6（执行清单）与 `design/reviews/rb-verify-report.md` §13（独立核对）。
**状态**：**已结清**（见上方小结）；下列原始登记内容保留供追溯。

---

## 0. 为什么不立即改（当时的判断，已由后续分支执行）

`docs/校园课程智能助手_前端详细设计_v0.1.md` 是**生成物**（由 `docs/frontend-detail/build.py` + `parts/*.md` 组装）。改它＝改分册 + 重跑组装 + 主文档字节与哈希变化。

阶段 A 收口时，独立验证报告锁定了 13 个文件的字节作为验收目标；当时立即改文档会让「已通过验证」的对象与仓库当前字节不一致，反而降低可核对性。因此当时**只登记**，并把清单做成可直接执行的表单；随后在独立分支 `docs/align-rb-fix` 上一次改完、一次重建、一次机械复核。

---

## 1. 判据缺陷（唯一一条有实质危害的条目）

| # | 位置 | 现状 | 应为 | 危害 |
| --- | --- | --- | --- | --- |
| TODO-1 | `docs/校园课程智能助手_前端详细设计_v0.1.md` §8.4「W1」行（分册 `parts/50-design-system-and-a11y.md`） | 验收判据写作 `#main` 的 `top >= 62 − 0.5` 且 `activeElement === #main` | 改为 **`occlusion = .appbar.getBoundingClientRect().bottom − 目标.getBoundingClientRect().top` ≤ 0.5px**，且**必须覆盖 768/772/774** | `#main` 紧跟在流首 appbar 之后，`scrollY` 被 clamp 到 0，`top` **恒为 56.67** → 该断言**永远为 false**（无意义）；更严重的是，在修复前的 768–774px 窄带里 `#main.top` 曾为 **62.17 ≥ 61.5 而通过**，**放行了一个仍然存在的 10px 真实遮挡** |

> 实测依据：`rb-verify-report.md` §3.2 / §4.1。修复后 13 个宽度遮挡均为 **0px**。

---

## 2. token 计数 518 → 519

阶段 A 在 L3 `root` 组新增 `--root-scroll-offset`，合计 **518 → 519**（L1 91 / L2 41 / L3 336→**337** / L0 50）。`design/system/` 内部已同步；以下为**未同步**处：

| # | 文件:行 | 现状 | 应为 |
| --- | --- | --- | --- |
| TODO-2 | `design/README.md:19` | 「四层 **518** 个 token」 | 519 |
| TODO-2 | `design/README.md:151` | 「三层 token **518** 个」 | 519 |
| TODO-3 | `docs/frontend-detail/parts/10-baseline-and-modules.md:13` | 「**518** 个 token 的四层设计系统」 | 519 |
| TODO-3 | `docs/frontend-detail/parts/50-design-system-and-a11y.md:4` | 「**518** 个 token」 | 519 |
| TODO-3 | `docs/frontend-detail/parts/50-design-system-and-a11y.md:14` | 「27 组、**336** 个」 | 337 |
| TODO-3 | `docs/frontend-detail/parts/50-design-system-and-a11y.md:142` | 「产物：**518 → 518+n**」 | 519 → 519+n |
| TODO-3 | `docs/frontend-detail/parts/50-design-system-and-a11y.md:153` | 「四层 `:root`，**518** 个 token」 | 519 |
| TODO-3 | `docs/frontend-detail/verification.md:390,413,667,687` | 518 / `518→518+n` | 519 |
| TODO-2 | `docs/frontend-detail/build.py:408` | 该处是**主文档 L7 那句「518 个 token」的真正来源**（只改分册改不到） | 519 |
| TODO-2 | `docs/frontend-detail/build.py:45` | `PROPOSED_TOKENS` 仍列 `--root-scroll-offset` 为「处方 token」 | 它已是 `tokens.css` 里的**真实 token**，可从处方清单移除 |

**合法保留项（不要误改）**：`design/system/components/04-forms-data.md` 里的 `336` 是 **`rb.css` 行号**不是 token 数；`design/system/README.md` 的 `164/198/283` 是刻意保留的历史与阶段 A 对照。

---

## 3. 冻结哈希更新

阶段 A 改了 `rb.css`，两个冻结哈希变化：

| # | 文件:行 | 现状 | 应为 |
| --- | --- | --- | --- |
| TODO-4 | `design/responsive/verification.md:306` | `rb.css = 94DF48EDFFC1DC33858A545C3574048F` | `0749FA7A47BC155F52A12406123DF6CC` |
| TODO-4 | `design/responsive/verification.md:308` | `b-responsive.html = 1DD81EAB2A90797AB01F4CEB0A645A17` | `5B73454136F261AC13E9A0203C0C6D73` |
| TODO-4 | `design/responsive/verification.md`（多处 74 / 518 语境） | 「74 个共同 token」/ 518 | 75 / 519（或显式注明「阶段 A 前」） |
| TODO-4 | `docs/校园课程智能助手_前端详细设计_v0.1.md:1796`（生成物） | 「哈希不变（`94DF48ED…`）」 | 更新为新哈希，或注明「阶段 A 前」 |
| TODO-4 | `design/system/components/02-actions-status.md` 等引 `01-shell-navigation.md` 的锚点 | 行号 318/331/486/883/936 | **全部 +1**（318→319、331→332、486→487、883→884、936→937） |

> 注意 `design/responsive/verification.md` 的 W1/W2/W3 结论本身建立**旧哈希**上，其结论随后被 `rb-verify-report.md` 取代——同步时应**改写结论**而非只换哈希。

---

## 4. 既有文档瑕疵（非本轮引入）

| # | 文件:行 | 现状 | 应为 |
| --- | --- | --- | --- |
| TODO-5 | `design/system/components/02-actions-status.md:375` | 把 `records.html:203` 记为 `.pill--ok` 的 `check` 图标实例 | 该行实为 **`pill--evidence`「plan_7Q2F9K」且无 svg**；这是一处**既有**错误（独立验证在阶段 A 之前的记录里已复现） |
| TODO-5 | `design/system/README.md` 收口裁决表 #1 | 「处理中」用 `pill--warn` 违规（2 处） | 阶段 A **已修**（改 `pill--info`），该行应标注为「阶段 A 已修」 |

---

## 4b. `01-shell-navigation.md` 变更的时点证据（补 `rb-verify-report.md` §12.1 的未验证项）

独立验证者声明它**没有改动前的字节**，因此只能证明改后结构自洽，**无法证明**「恰好 +1 行 + 5 处替换」。Lead 侧有一条可复现的**时点证据**，可把该未验证项的范围收窄（但**不能**消除）：

```
改动前快照（Lead 于 2026-10-23 12:34:55 独立跑 generate.py 时抓取）
    01-shell-navigation.md = 98EA16907882D7FA18F486ED68368A8F
当前值（阶段 A 冻结）
    01-shell-navigation.md = 0C33CD918F3C90758CD873BB7229C3D1
该文件 mtime = 2026-10-23 12:43:22   （晚于 12:34:55、早于 fix-rb 收尾 13:07）
```

两条佐证（性质不同，**不要混为一谈**）：

| 证据 | 性质 | 能证明什么 |
| --- | --- | --- |
| `98EA1690…` 在**整棵 `design/` 树**中不匹配任何当前文件（已按 MD5 与 MD4 各查一遍） | 变更证据 | 该文件**确实被改过** |
| `generate.py` 不写 `design/system/components/*`（grep `components/0[1-4]` 无匹配），且跑完该文件哈希不变 | **类型证据**（非变更证据） | 这次编辑**不可能来自生成器**，只能是手工编辑 |

> **结论边界**：可确认「确被手工编辑过」；**仍无法证明逐行 diff 恰好是「+1 行 + 5 处替换」**——那需要改动前的完整副本。任何后续引用都应保持这个限制。

---

## 5. 判据层缺口（值得单独记的一条教训）

| # | 位置 | 问题 |
| --- | --- | --- |
| TODO-6 | `design/system/verify-system.py` | **没有任何「组件规格消费表的『解析值』列 vs `tokens.flat.json`」比对**。`design/system/README.md` 硬要求 2 明写「解析值必须与 `tokens.flat.json` 一致」，但该要求**无判据覆盖**。当前唯一的偏差是良性的：`01-shell-navigation.md:148` 写 `62px`，而 `tokens.flat.json` 是 `calc(56px + 6px)`（语义相同、字面不等） |

> 这与 `design/system/README.md` 自己总结的 **M1 教训**同源：**文本层看起来对了，但没有任何检查把它钉住**。建议下一轮把这条补成 F/H 项的一个新判据。

---

## 6. TODO-1/2/3 的执行顺序（一次改完 + 一次重建）

```powershell
$env:PYTHONIOENCODING="utf-8"

# 1) 先改分册（TODO-1/2/3 中标注为 parts/* 的条目）
#    docs/frontend-detail/parts/10-baseline-and-modules.md
#    docs/frontend-detail/parts/50-design-system-and-a11y.md
# 2) 再改脚本与历史报告（TODO-2/4/5）
#    docs/frontend-detail/build.py、docs/frontend-detail/verification.md
#    design/README.md、design/responsive/verification.md
#    design/system/components/02-actions-status.md
# 3) 重建主文档（它是生成物，禁止手改）
python docs\frontend-detail\build.py          # 期望 0 FAIL

# 4) 机械复核：不得再有残留旧数字/旧哈希
Select-String -Path docs\校园课程智能助手_前端详细设计_v0.1.md,design\README.md `
  -Pattern '518 个 token|94DF48EDFFC1DC33858A545C3574048F|1DD81EAB2A90797AB01F4CEB0A645A17' -Encoding UTF8

# 5) 全套回归（收尾全量）
foreach ($s in @('design\system\generate.py','design\system\build-system.py',
                 'design\system\verify-system.py','design\responsive\build.py',
                 'design\reviews\verify.py','docs\frontend-detail\build.py')) { python $s }
```

**同步完成后必须重跑 `docs/frontend-detail/build.py`** —— 主文档是生成物，手改会被下次组装覆盖，且 `build.py` 的检查会报错。

---

（以下为**当时的登记原文**，保留供追溯；实际处置见开头小结。）

