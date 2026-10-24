# 前端 UI/UX 设计工作区

本目录是本项目**前端 UI/UX 设计的交付区**。

## 现在处于哪一步

**第一步：方向稿（已完成）。** 三个视觉方向 + 一份方向无关的信息架构草图。
评审入口 → [`directions/index.html`](directions/index.html)；结论：**采用方向 B（纸感墨绿 · 专注对话）**。

**第二步：方向 B 响应式原型（已完成）。**
响应式规范 + 一个**真正会重排**的单文件原型（不是画好的手机框）。

评审入口 → **[`responsive/b-responsive.html`](responsive/b-responsive.html)** — 双击打开后**直接拖动窗口宽度**：
≥768px 用顶栏内联导航、<768px 自动换成底部标签栏；表格在 <768px 变成卡片；右下角实时显示当前断点。

配套规范 → [`responsive/b-responsive-spec.md`](responsive/b-responsive-spec.md)

**第三步：设计系统 · 三层 token 与组件 API 规格（当前交付）。**
把方向 B 的视觉形式化为 L1 primitive → L2 semantic → L3 component 四层 519 个 token
+ 4 份组件 API 规格 + 一个**只消费 L3 token** 的活样式手册。

评审入口 → **[`system/system.html`](system/system.html)** — 双击打开：27 个组件族、
每组列出全部 L3 token 与解析值、每组下面是对应的真实渲染演示。

规范与契约 → [`system/README.md`](system/README.md)（分层纯度规则、组件规格契约、收口裁决）
token 参考 → [`system/tokens.md`](system/tokens.md)　组件 API → [`system/components/`](system/components)

## 目录结构

```
design/
├─ README.md                          本文件
├─ directions/                        第一步：方向稿
│  ├─ index.html                      ★ 方向评审入口（对比 + 量化对照 + 校验结论）
│  ├─ direction-a.html                方向 A：学院蓝 · 清晰秩序
│  ├─ direction-b.html                方向 B：纸感墨绿 · 专注对话  ← 已采用
│  ├─ direction-c.html                方向 C：深色控制台 · 数据密集
│  └─ shared/content-spec.md          内容与状态冻结清单（屏幕块 S00–S14、逐字文案、无障碍硬要求）
├─ ia/sitemap.html                    信息架构草图（方向无关，7 个部分）
├─ responsive/                        第二步：方向 B 响应式原型
│  ├─ b-responsive.html               ★ 最终产物：单文件、零外部请求、真实重排
│  ├─ b-responsive-spec.md            响应式规范（断点 / 布局 / 组件行为 / 验收清单）
│  ├─ rb.css                          样式契约（唯一样式来源，122 个 class）← 设计系统的上游
│  ├─ shell.html                      外壳模板（顶栏 + 底部标签栏 + 断点指示器）
│  ├─ build.py                        组装脚本 + 构建期契约检查
│  ├─ parts/                          四个 markup 片段（login / assistant / records / admin）
│  └─ verification.md                 独立渲染验证报告
├─ system/                            第三步：设计系统（三层 token + 组件 API 规格）
│  ├─ system.html                     ★ 评审入口：活样式手册（27 组真实渲染）
│  ├─ tokens.json                     ★ 单一真源：四层 token / 断点 / 对比度判据 / 纯度规则
│  ├─ generate.py                     生成器 + 校验器 → tokens.css / tokens.md / tokens.ts
│  ├─ tokens.css                      四层 :root（L1/L2/L3 + rb.css 兼容层）
│  ├─ tokens.md                       人类可读 token 参考（含对比度实测、迁移对照）
│  ├─ tokens.ts                       TS 常量（断点 + 解析值），供 Vue 3 直接 import
│  ├─ styleguide.css                  L3-only 组件样式（活样式手册的素材）
│  ├─ styleguide-demos.html           27 组演示 markup（活样式手册的素材）
│  ├─ build-system.py                 组装 system.html + 组装期契约检查
│  ├─ verify-system.py                独立于生成器的确定性校验（29 项）
│  ├─ components/                     4 份组件 API 规格（27 个组件族不重不漏）
│  └─ verification.md                 独立验证报告
└─ reviews/                           校验与验证记录
   ├─ verify.py                       确定性校验器（结构 / 文案 / 对比度 / 裸 hex / 标签配平）
   ├─ verify-output.txt/.json         校验输出
   ├─ round1-verification.md          Round 1 独立验证报告（静态等价证据）
   └─ render-verification-round2.md   Round 2 真实渲染验证记录（CDP）
```

## 方向 B 的响应式设计要点

- **5 个断点**：base(<480) / XS(≥480) / **SM(≥768)** / MD(≥1024) / LG(≥1200) / XL(≥1440)，全部 mobile-first。
  `768` 是主分界线，同时承担三件事：导航换形态、表格↔卡片、表单列数——刻意压在一个断点，减少验证组合。
- **不做侧栏**：方向 B 的身份就是「无侧栏、单列专注」。窄屏用**底部标签栏**承载 4 个一级入口
  （比汉堡菜单省一次点击，也符合移动端底部导航惯例）。
- **表格 → 卡片**：同一份 markup，`<768` 时 `thead` 隐藏、`tr` 成卡片、`td` 用 `data-label` 渲染字段名。
  每张 `.table--stack` 的每个 `<td>` 都必须有 `data-label`（`build.py` 构建期检查）。
- **两条来自真实渲染的硬教训**（详见 `reviews/render-verification-round2.md` 与 `rb.css` 注释）：
  1. 表格单元格**不要**用 `overflow-wrap: anywhere` —— 它降低 min-content，会让该列被压到约 1 个字符宽；
     表格内用 `break-word` + 给该列 `min-width`。
  2. 表格改 `display:block` 后，`<caption>` 必须同时改 `display:block`，
     否则 `table-caption` 会 shrink-to-fit 到约 62px，说明文字每行只排一个字。

## 已从 docs 固化下来的关键设计结论

这些不是设计偏好，而是上游契约推导出的必然结果：

| 结论 | 依据 |
| --- | --- |
| 登录后默认进「课程助手」 | PRD §5.1 |
| 助手对话**不进 URL** | 会话仅存内存、刷新即失效（SRS DEC-01 / CHAT-03、HLD-D03/D11）。写进 URL 等于承诺不存在的恢复能力 |
| 「当天无安排」与「课表无法读取」必须是两种状态 | PRD §6.3 SCHEDULE-01、SRS INV-05、AT-06 |
| 过程区只展示三类可核实工具动作 | 工具白名单仅 `get_my_schedule` / `search_course_docs` / `save_study_plan`（PRD §11.2、SRS IF-008） |
| 未校验引用标记必须与已验证引用视觉可区分 | SRS FR-QA-002、IF-007 |
| 草稿默认「未保存」，保存后给 plan_id | PRD PLAN-01/02、SRS FR-PLAN-002/005 |
| 写入结果未知时显示"待确认"而非失败 | SRS FR-CHAT-005、§7.3、后端详细设计 §12.2 |
| 文档批次整批可见或整批不可见，五种文件状态 | PRD DOC-02、SRS FR-DOC-003、§7.2 |
| 令牌仅内存、2 小时不续期、刷新需重登 | SRS §3.2 配置表、HLD-D03 |
| 至少覆盖 1366×768 与 390×844 | SRS NFR-COMP-001 |

## 校验与验证

**静态确定性校验**（可复现）：

```powershell
$env:PYTHONIOENCODING="utf-8"
python design\reviews\verify.py
```

检查结构完整性、零外部请求、逐字文案、无障碍计数、WCAG 对比度（按声明 token）、裸 hex、
标签配平（栈式解析）、方向差异真实性、违禁内容、与 OpenAPI/SRS 的契约一致性。

**构建期契约检查**：

```powershell
python design\responsive\build.py
```

检查片段 class 是否都在 `rb.css` 里定义、每个 stack 表格的 `<td>` 是否有 `data-label`、
片段是否含 `<style>/@media/`裸 hex/emoji，并打印产物视图清单。

**设计系统校验（第三步）**：

```powershell
$env:PYTHONIOENCODING="utf-8"
python design\system\generate.py      # token 源 → tokens.css/md/ts，并校验分层纯度、对比度、rb.css 等价性
python design\system\build-system.py  # 素材 → system.html，并校验 L3 纯度、27 组齐备、data-label
python design\system\verify-system.py # 独立于生成器的确定性校验，29 项
```

`verify-system.py` 刻意**不 import 生成器**，把分层纯度、对比度、`rb.css` 等价性重新实现一遍，
避免「生成器的 bug 被生成器自己判为通过」。它同时机械核对：4 份组件规格的 `owns` 并集是否
**恰好等于** 27 个 L3 组且不重复、每份是否覆盖本组全部 token、是否引用了不存在的 token、
规格里的 `rb.css:NNN` 锚点是否越界、活样式手册内联的 `tokens.css` 是否与生成物逐字节一致。

**真实渲染验证**：Round 2 起用 `web-access` 技能（CDP Proxy 直连本机 Edge）完成了真实渲染取证 ——
六宽度页面级横向溢出、导航换形态、表格卡片化、触控目标、真实加载资源数、以及**人工看图**。
记录见 [`reviews/render-verification-round2.md`](reviews/render-verification-round2.md)
与 [`responsive/verification.md`](responsive/verification.md)。

> 补充说明：DSH **官方侧栏浏览器不提供 agent 控制能力**（本会话中页面始终未挂载进侧栏面板，
> `sidebar.state.webview.via: "absent"`，随后会话被空闲回收且 agent 无法自行重建）；
> agent 可控的浏览操作由**本地插件**（web-access / CDP）补齐。

**仍未验证**：hover/focus/active 的真实渲染样式；真实渲染像素的对比度（现有对比度均按**声明的 token 值**计算，
未做 alpha 与 `color-mix` 合成后实测）；Firefox / Safari（SRS 只要求 Chrome/Edge）；
无障碍树与屏幕阅读器实际朗读顺序。

## 下一步可选

1. ~~**设计系统与组件规格**~~ —— **已完成**（本目录第三步）。三层 token 519 个、4 份组件 API 规格、
   只消费 L3 的活样式手册、31 项独立确定性校验；独立渲染验证 11 项见
   [`system/verification.md`](system/verification.md)。
   **落地前必修的 6 项已由阶段 A 修完**（#1/#3/#6 + W1/W2/W3）：见
   [`reviews/rb-fix-report.md`](reviews/rb-fix-report.md)（修复）与
   [`reviews/rb-verify-report.md`](reviews/rb-verify-report.md)（独立验证，6 项全 PASS）。
   > 追加修复：修复过程中独立验证发现 768–774px 顶栏会因 navlink 换行升到 **72.17px**，
   > 使 `scroll-padding-top:62px` 失效（仍遮 10px）。已用 `white-space:nowrap` 治本，
   > 18 个宽度顶栏恒 56.67px。
   > 既有产物哈希随之变化：`rb.css = 0749FA7A47BC155F52A12406123DF6CC`、
   > `b-responsive.html = 5B73454136F261AC13E9A0203C0C6D73`；token 合计 **519**。
2. ~~**前端详细设计**~~ —— **已完成**（16 章）。它把本目录的设计产物接到实现：
   目标目录与模块边界、SSE 流式客户端（分包/编码边界/去重/终态唯一/「HTTP 关闭 ≠ 终态」）、
   8 个 store、10 条路由、S01–S13 逐屏、27 个组件族的 Vue 映射、无障碍与响应式实现、
   以及 6 个必修项作为**实现前置批次**。
3. ~~**Vue 3 可运行响应式骨架**~~ —— **已完成**（阶段 B）：见 [`../web/`](../web/)，
   Vue 3 + TS + Pinia + vue-router 4，8 个 store、10 条路由、SSE 字节级解析（P1–P12）+ 状态机、
   27 个组件族、S01–S12 视图、mock 层（同源 `/api/v1`，零外部请求）。
   验收与未覆盖项见 [`../web/BUILD-REPORT.md`](../web/BUILD-REPORT.md)。
   > ⚠ DSH 沙箱内 `pnpm build` 走不通（`stdio:'pipe'` 被拒），**沙箱外可正常构建**；
   > 详见 [`../CONTRIBUTING.md`](../CONTRIBUTING.md) §4。
4. **补齐交互**：原型现在是静态状态展示；可补流式回答、引用展开、草稿保存、重叠确认等真实交互与状态机。
5. **组件规格 → 代码生成**：`tokens.json` 已经是机器可读真源，可再产 Tailwind theme / Figma variables / 组件类型定义。
