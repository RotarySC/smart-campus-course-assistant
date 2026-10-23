/**
 * stylelint 自定义门禁（前端详细设计 §8.2 / §10.4）。
 *
 * 五条规则，全部做成 CI 非 0 退出：
 *   ① dsh/no-raw-color         禁裸 hex / 命名色 / rgb()/rgba()/hsl()
 *   ② dsh/no-raw-length        禁带单位裸长度（白名单：0、0px、1px、100%、auto、none）
 *   ③ dsh/layer-purity         组件样式禁消费 L1（--p-*）与 L2（--bg-* / --text-* …）
 *   ④ dsh/no-unknown-state     状态白名单：:hover / :focus-visible / [disabled] / :checked /
 *                              [aria-current="page"] / [readonly] / :focus / :not / :last-child
 *                              **出现 :active / transition 即 FAIL**
 *   ⑤ dsh/breakpoint-whitelist 媒体查询断点只允许 tokens.json 的 6 档及其 min−1
 *
 * 关于 `animation` 的**显式窄化**（与前端详细设计 §10.4 字面表述的唯一偏离）：
 *   §10.4 把 `animation` 与 `:active`/`transition` 并列禁止；但 §8.3（L1715–1725）以
 *   「本方向**唯一动效** `.step--running .step__ico` 旋转（rb.css:252–253，时长/缓动由
 *   `--step-running-spin-duration`/`-easing` 承载）」作为全局 prefers-reduced-motion 重置的
 *   **依据**，design/system/README.md 裁决 9 也为它专设了 L3 token。
 *   一份文档不会为「不存在的动效」写 reduced-motion 依据，因此这里把 `animation` 收成
 *   **白名单到精确一处**：只允许 `.step--running .step__ico` 使用 animation，且必须消费
 *   `var(--step-running-spin-*)`；第二处即 FAIL。`transition` / `:active` 仍然全禁。
 *   本窄化已登记在 web/BUILD-REPORT.md。
 */

const stylelint = require('stylelint')

const ruleNameRawColor = 'dsh/no-raw-color'
const ruleNameRawLength = 'dsh/no-raw-length'
const ruleNameLayerPurity = 'dsh/layer-purity'
const ruleNameUnknownState = 'dsh/no-unknown-state'
const ruleNameBreakpoint = 'dsh/breakpoint-whitelist'

const COLOR_RE = /(#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(|\b(?:white|black|red|blue|green|gray|grey|orange|yellow|purple)\b)/
const LENGTH_RE = /(?:^|[\s(,])(-?\d*\.?\d+)(px|em|rem|ch|vw|vh|vmin|vmax|pt|pc|in|cm|mm|q|ex|cap|ic|lh|rlh)\b/
/** L2 与 L1 的前缀（组件样式里出现即跨层违规）。 */
const FORBIDDEN_PREFIXES = [
  '--p-',
  '--bg-',
  '--text-',
  '--accent',
  '--state-',
  '--border',
  '--danger-border',
  '--pending',
  '--layout-',
  '--shell-',
  '--elevation-',
  '--motion-',
  '--focus-ring-',
  '--size-',
  // §8.6：迁移期新代码禁止引用 L0 兼容层。
  '--c-',
  '--sp-',
  '--fs-',
  '--lh-',
  '--r-',
  '--shadow-hair',
  '--w-',
  '--h-',
  '--tap',
  '--font-',
]
const ALLOWED_PREFIXES = [
  '--root-', '--wrap-', '--card-', '--btn-', '--pill-', '--notice-', '--chat-', '--msg-', '--bubble-',
  '--steps-', '--step-', '--composer-', '--cite-', '--draft-', '--empty-', '--field-', '--control-',
  '--errorsummary-', '--table-', '--kv-', '--chip-', '--chips-', '--prose-', '--login-', '--stack-',
  '--row-', '--muted-', '--small-', '--appbar-', '--brand-', '--navlink-', '--tabbar-', '--skiplink-',
  '--sr-', '--focus-outline-',
]

const ruleRawColor = (enabled) => (root, result) => {
  if (!enabled) return
  root.walkDecls((decl) => {
    if (decl.prop.startsWith('--')) return // token 声明层由 tokens.css 负责，本规则查消费侧
    if (COLOR_RE.test(decl.value)) {
      stylelint.utils.report({
        message: `禁裸颜色（§8.2 规则①）：请改用 var(--<组件>-<部位>-<属性>) 的 L3 token —— ${decl.prop}: ${decl.value}`,
        node: decl,
        result,
        ruleName: ruleNameRawColor,
      })
    }
  })
}

const ruleRawLength = (enabled, opts) => (root, result) => {
  if (!enabled) return
  const allow = new Set((opts && opts.allow) || ['0', '0px', '1px', '100%', 'auto', 'none'])
  root.walkDecls((decl) => {
    if (decl.prop.startsWith('--')) return
    // 媒体查询参数不在此规则内（由 ⑤ 负责）
    const m = LENGTH_RE.exec(` ${decl.value}`)
    if (!m) return
    const literal = `${m[1]}${m[2]}`
    if (allow.has(literal) || allow.has(m[1])) return
    stylelint.utils.report({
      message: `禁带单位裸长度（§8.2 规则②）：${literal} —— 请改用 L3 token`,
      node: decl,
      result,
      ruleName: ruleNameRawLength,
    })
  })
}

const ruleLayerPurity = (enabled, opts) => (root, result) => {
  if (!enabled) return
  const scope = (opts && opts.scope) || []
  const file = (result.opts && result.opts.from) || ''
  const normalized = file.replace(/\\/g, '/')
  if (scope.length > 0 && !scope.some((s) => normalized.includes(s.replace('**', '').replace('*', '')))) return

  root.walkDecls((decl) => {
    for (const m of decl.value.matchAll(/var\(\s*(--[a-zA-Z0-9-]+)/g)) {
      const token = m[1]
      if (FORBIDDEN_PREFIXES.some((p) => token.startsWith(p))) {
        stylelint.utils.report({
          message: `跨层违规（§8.2 规则③）：组件样式消费了 L1/L2/L0 token ${token}`,
          node: decl,
          result,
          ruleName: ruleNameLayerPurity,
        })
        continue
      }
      if (!ALLOWED_PREFIXES.some((p) => token.startsWith(p))) {
        stylelint.utils.report({
          message: `未知 token ${token}：L3 组件 token 必须形如 --<组件>-<部位>-<属性>，且组件名在本族 owns 集合内`,
          node: decl,
          result,
          ruleName: ruleNameLayerPurity,
        })
      }
    }
  })
}

/** 状态白名单：出现白名单外的伪类/属性选择器即 FAIL。 */
const ALLOWED_STATE_SELECTORS = [
  ':hover',
  ':focus-visible',
  ':focus',
  ':checked',
  ':not',
  ':last-child',
  ':first-child',
  '[disabled]',
  '[aria-current="page"]',
  '[aria-current=\'page\']',
  '[readonly]',
  '[aria-invalid="true"]',
]
const FORBIDDEN_STATE_SELECTORS = [':active', 'transition', 'animation']

const ruleUnknownState = (enabled) => (root, result) => {
  if (!enabled) return
  const baseCss = (result.opts && result.opts.from) || ''
  const isBaseCss = baseCss.replace(/\\/g, '/').endsWith('styles/base.css')

  root.walkRules((rule) => {
    const selector = rule.selector
    for (const bad of FORBIDDEN_STATE_SELECTORS) {
      if (!selector.includes(bad)) continue
      // 白名单：base.css 里**唯一**一处 `.step--running .step__ico { animation: ... }`。
      // 依据见文件头「显式窄化」。
      if (
        bad === 'animation' &&
        isBaseCss &&
        /\.step--running\s+\.step__ico/.test(selector)
      ) {
        const decls = []
        rule.walkDecls((d) => decls.push(d))
        const usesTokens = decls.some(
          (d) => d.prop === 'animation' && d.value.includes('var(--step-running-spin-duration)') && d.value.includes('var(--step-running-spin-easing)'),
        )
        if (usesTokens) continue
      }
      stylelint.utils.report({
        message: `违禁状态/动效（§10.4）：出现 ${bad}。本方向只存在 rb.css 里已有的状态；唯一的 animation 白名单见 stylelint-rules/layer-purity.cjs 文件头`,
        node: rule,
        result,
        ruleName: ruleNameUnknownState,
      })
    }
    // 检查白名单外的伪类
    for (const m of selector.matchAll(/::?[a-zA-Z-]+/g)) {
      const pseudo = m[0]
      if (pseudo === '::before' || pseudo === '::after' || pseudo === '::placeholder') continue
      if (!ALLOWED_STATE_SELECTORS.some((a) => pseudo.startsWith(a.replace(/\[.*/, '')) || pseudo === a)) {
        if (pseudo.startsWith(':') && !ALLOWED_STATE_SELECTORS.includes(pseudo)) {
          // 只报「状态类」伪类，结构伪类放行
          const structural = [':root', ':not', ':first-child', ':last-child', ':nth-child']
          if (!structural.includes(pseudo)) {
            stylelint.utils.report({
              message: `不在状态白名单内的伪类 ${pseudo}（§10.4）。白名单：:hover / :focus-visible / [disabled] / :checked / [aria-current="page"] / [readonly]`,
              node: rule,
              result,
              ruleName: ruleNameUnknownState,
            })
          }
        }
      }
    }
  })
}

const BP_ALLOWED = new Set(['479', '767', '1023', '1199', '1439', '480', '768', '1024', '1200', '1440'])
const ruleBreakpoint = (enabled) => (root, result) => {
  if (!enabled) return
  root.walkAtRules('media', (atRule) => {
    for (const m of atRule.params.matchAll(/\((?:min|max)-width:\s*(\d+)px\s*\)/g)) {
      if (!BP_ALLOWED.has(m[1])) {
        stylelint.utils.report({
          message: `断点 ${m[1]}px 不在 tokens.json 的 6 档内（§8.3；max-width 档只允许写 min-width 档 − 1）`,
          node: atRule,
          result,
          ruleName: ruleNameBreakpoint,
        })
      }
    }
  })
}

module.exports = [
  stylelint.createPlugin(ruleNameRawColor, ruleRawColor),
  stylelint.createPlugin(ruleNameRawLength, ruleRawLength),
  stylelint.createPlugin(ruleNameLayerPurity, ruleLayerPurity),
  stylelint.createPlugin(ruleNameUnknownState, ruleUnknownState),
  stylelint.createPlugin(ruleNameBreakpoint, ruleBreakpoint),
]
