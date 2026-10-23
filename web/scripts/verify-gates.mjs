#!/usr/bin/env node
/**
 * 门禁反向注入自测：**证明每一道门禁真的会 FAIL**，而不是「静默通过」。
 *
 * 为什么要做这个：一个什么都不检查的 stylelint 插件和一个全绿的脚本，退出码都是 0。
 * 所以这里对每条规则注入一个**已知违规**，断言它确实被抓到，然后**必然还原**（try/finally）。
 *
 * 实现约束：**全程在同一进程内**（`runInvariants()` 直接调用；stylelint 用 Node API）。
 * 不能用子进程 —— 本沙箱禁止管道的子进程 stdio（`spawn ... stdio:'pipe'` → EPERM），
 * 那正是本项目 `pnpm build` 起不来的同一条边界（见 BUILD-REPORT）。
 *
 * 运行： node scripts/verify-gates.mjs
 * 它不修改任何交付物：注入前备份、断言后还原，最后重跑门禁确认回到全绿。
 */

import { copyFileSync, existsSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import stylelint from 'stylelint'
import { runInvariants } from './invariants.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const webRoot = resolve(here, '..')

const results = []

/* ---------------- 不变量脚本的反向注入 ---------------- */
function inject(file, mutate, { name, ruleIndex }) {
  const abs = join(webRoot, file)
  const bak = `${abs}.gatebak`
  copyFileSync(abs, bak)
  try {
    writeFileSync(abs, mutate(readFileSync(abs, 'utf8')), 'utf8')
    const rows = runInvariants()
    const row = rows[ruleIndex]
    // 断言：**目标规则本身**必须变红（不接受「被别的规则顺带抓到」）
    const reallyCaught = row !== undefined && row.ok === false
    results.push({
      name,
      ok: reallyCaught,
      detail: reallyCaught
        ? `按预期 FAIL —— 「${row.name}」：${row.detail.slice(0, 110)}`
        : `**未被抓住**：第 ${ruleIndex + 1} 条规则仍为 PASS`,
    })
  } finally {
    renameSync(bak, abs)
  }
}

// 规则名里的序号即 results 下标：1..10
inject('src/styles/tokens.css', (t) => `${t}\n/* injected drift */\n`, {
  name: '门禁1 tokens 逐字节一致：改动 tokens.css 一个字节',
  ruleIndex: 0,
})

inject(
  'src/components/base/Wrap.vue',
  (t) => t.replace('</template>', '</template>\n\n<style scoped>\n.wrap-probe {\n  color: var(--p-ink-900);\n}\n</style>\n'),
  { name: '门禁2 分层纯度：组件 style 消费 L1 token var(--p-ink-900)', ruleIndex: 1 },
)

inject('src/styles/base.css', (t) => `${t}\n.step--injected { animation: spin 1s linear infinite; }\n`, {
  name: '门禁3-a 违禁动效：base.css 出现**第二处** animation',
  ruleIndex: 2,
})

inject('src/styles/base.css', (t) => `${t}\n.probe:active { color: var(--card-bg); }\n`, {
  name: '门禁3-b 违禁状态：出现 :active',
  ruleIndex: 2,
})

inject('src/domain/format.ts', (t) => `${t}\nexport const PROBE_FORBIDDEN = '暂无数据'\n`, {
  name: '门禁4 违禁文案：代码里出现字符串「暂无数据」',
  ruleIndex: 3,
})

inject('src/components/base/Wrap.vue', (t) => t.replace('class="wrap"', 'class="wrap wrap-probe-unknown"'), {
  name: '门禁7 class 存在性：使用 rb.css 未定义的 class',
  ruleIndex: 6,
})

inject('src/api/client.ts', (t) => `${t}\nexport const PROBE_INTERNAL = '/internal/v1/probe'\n`, {
  name: '门禁8 不引用 /internal/v1：出现 /internal/v1 字面量',
  ruleIndex: 7,
})

/* ---------------- stylelint 五条规则 ---------------- */
const STYLELINT_CONFIG = { configFile: join(webRoot, '.stylelintrc.cjs'), cwd: webRoot }

/**
 * `target` 必须落在规则 scope 内才会被检查：`dsh/layer-purity` 的 scope 是
 * `src/components/**` 与 `src/styles/base.css`（§8.2 冻结值），
 * 所以「禁消费 L2」这一条要用组件内的探针文件来验，用 `src/styles/__probe__.css` 验不出来。
 */
async function stylelintProbe(css, { name, expectRule, target = 'src/styles/__probe__.css' }) {
  const abs = join(webRoot, target)
  writeFileSync(abs, css, 'utf8')
  try {
    const relTarget = target.replaceAll('\\', '/')
    const r = await stylelint.lint({ files: relTarget, ...STYLELINT_CONFIG })
    const warnings = r.results.flatMap((x) => x.warnings)
    const hit = warnings.some((w) => w.rule === expectRule)
    results.push({
      name,
      ok: hit,
      detail: hit
        ? `按预期 FAIL —— ${expectRule}: ${warnings.find((w) => w.rule === expectRule)?.text?.slice(0, 90)}`
        : `**未被抓住**：期望 ${expectRule}，实际 warnings = ${JSON.stringify(warnings.map((w) => w.rule))}`,
    })
  } finally {
    if (existsSync(abs)) rmSync(abs)
  }
}

await stylelintProbe('.probe { color: #14665B; }\n', { name: 'stylelint① 禁裸颜色', expectRule: 'dsh/no-raw-color' })
await stylelintProbe('.probe { padding: 18px; }\n', { name: 'stylelint② 禁带单位裸长度', expectRule: 'dsh/no-raw-length' })
await stylelintProbe(
  '<template>\n  <div class="probe" />\n</template>\n\n<style scoped>\n.probe {\n  background: var(--bg-card);\n}\n</style>\n',
  { name: 'stylelint③ 禁消费 L2 token（组件 scope 内）', expectRule: 'dsh/layer-purity', target: 'src/components/base/__probe__.vue' },
)
await stylelintProbe('.probe:active { color: var(--card-bg); }\n', { name: 'stylelint④ 禁 :active', expectRule: 'dsh/no-unknown-state' })
await stylelintProbe('@media (min-width: 900px) { .probe { display: block; } }\n', {
  name: 'stylelint⑤ 断点只允许契约 6 档',
  expectRule: 'dsh/breakpoint-whitelist',
})

/* ---------------- 输出 ---------------- */
console.log('门禁反向注入自测（scripts/verify-gates.mjs）')
console.log('='.repeat(78))
let bad = 0
for (const r of results) {
  if (!r.ok) bad++
  console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}`)
  console.log(`      ${r.detail}`)
}
console.log('='.repeat(78))
console.log(`${results.length - bad}/${results.length} 门禁被证明会 FAIL`)

// 还原后必须回到全绿
const rows = runInvariants()
const invFail = rows.filter((r) => !r.ok).length
const sl = await stylelint.lint({ files: 'src/**/*.{css,vue}', ...STYLELINT_CONFIG })
const slWarn = sl.results.flatMap((x) => x.warnings).length
console.log('')
console.log(`还原后重跑：invariants ${rows.length - invFail}/${rows.length} 通过；stylelint warnings=${slWarn}`)
if (invFail > 0 || slWarn > 0) {
  console.log(rows.filter((r) => !r.ok).map((r) => `${r.name}: ${r.detail}`).join('\n'))
  process.exit(1)
}
console.log('还原后全绿 ✓')
if (bad > 0) process.exit(1)
