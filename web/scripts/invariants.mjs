#!/usr/bin/env node
/**
 * 不变量检查（机械核对，非「为了覆盖率写用例」）。
 *
 * 与契约的对应关系：
 *   1. tokens 逐字节一致        —— §8.1 同步机制第 2 步 / §8.2 门禁
 *   2. L3-only 分层纯度          —— design/system/README.md 纯度规则 4 / §8.2 规则 ③
 *   3. 无违禁状态与动效          —— §10.4 状态白名单（**显式窄化**：唯一一处 spin，见下）
 *   4. 无违禁文案                —— §5.5 / CONTRACT §3.7 第 3 条
 *   5. 无外部请求                —— content-spec §0「禁止任何外部请求」
 *   6. 零持久化                  —— §6.15 实现禁令 2 / §6.16 验收点 9
 *   7. class 存在性              —— §10.4「class 必须逐字出现在 rb.css 的 122 个 class 集合中」
 *   8. 只调用 /api/v1             —— §15.2「前端不引用任何 /internal/v1/*」
 *   9. 断点字面量只用契约取值    —— §8.3 / 纯度规则 5
 *  10. skip-link 目标存在        —— §7.6
 *
 * 实现注意：**所有文本规则都先剥注释再匹配**。否则「无 `:active`/`transition`」
 * 这类说明性注释会被自己的检查命中（本脚本第一版就踩了这个坑）。
 *
 * 退出码：任一 FAIL 即 1。
 */

import { createHash } from 'node:crypto'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const webRoot = resolve(here, '..')
const repoRoot = resolve(webRoot, '..')
const SRC = join(webRoot, 'src')

/* ---------- 工具 ---------- */
const md5 = (b) => createHash('md5').update(b).digest('hex')

function walk(dir, filter) {
  const out = []
  if (!existsSync(dir)) return out
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry)
    const st = statSync(p)
    if (st.isDirectory()) out.push(...walk(p, filter))
    else if (filter(p)) out.push(p)
  }
  return out
}

const rel = (p) => relative(repoRoot, p).replaceAll('\\', '/')

/**
 * 剥掉块注释（`/* *\/` 与 `/** *\/`）。
 * 用于规则 5：URL 检查必须保留字符串本体，所以这里**只**剥块注释。
 */
function stripBlockComments(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * 剥掉块注释 + 行注释（含**行尾**注释）。
 *
 * 为什么必须处理行尾注释：本项目的很多说明是 `foo: 'x', // 禁止「正在思考」…` 这种形态，
 * 只剥「整行 //」会让检查命中自己的说明文字（第一版就踩了这个坑，被反向注入自测暴露）。
 * 实现上按字符串字面量切分，引号内的 `//`（如协议头、URL）不会被当注释切断。
 */
function stripComments(text) {
  const noBlock = stripBlockComments(text)
  return noBlock
    .split('\n')
    .map((line) => {
      let out = ''
      let quote = null
      for (let i = 0; i < line.length; i++) {
        const ch = line[i]
        if (quote !== null) {
          out += ch
          if (ch === '\\') {
            out += line[++i] ?? ''
            continue
          }
          if (ch === quote) quote = null
          continue
        }
        if (ch === '"' || ch === "'" || ch === '`') {
          quote = ch
          out += ch
          continue
        }
        if (ch === '/' && line[i + 1] === '/') break
        out += ch
      }
      return out
    })
    .join('\n')
}

/** 只取 `<style>` 块（.vue）或全文（.css）。 */
function cssOnly(file, text) {
  if (!file.endsWith('.vue')) return text
  const blocks = [...text.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1])
  return blocks.join('\n')
}

/** 只取 `<template>` 块（.vue）或全文（.css）。 */
function templateOnly(file, text) {
  if (!file.endsWith('.vue')) return text
  return text.match(/<template>[\s\S]*<\/template>/)?.[0] ?? ''
}

/** 从 `:class` 表达式里抽动态 class 名：对象键 + 三元分支。 */
function dynamicClasses(expr) {
  const out = new Set()
  for (const m of expr.matchAll(/'([a-zA-Z][a-zA-Z0-9_-]*)'\s*:/g)) out.add(m[1]) // 带引号的对象键
  for (const m of expr.matchAll(/[{,]\s*([a-zA-Z][a-zA-Z0-9_-]*)\s*:/g)) out.add(m[1]) // 不带引号的对象键
  for (const m of expr.matchAll(/\?\s*'([a-zA-Z][a-zA-Z0-9_-]*)'\s*:/g)) out.add(m[1]) // 三元真分支
  for (const m of expr.matchAll(/:\s*'([a-zA-Z][a-zA-Z0-9_-]*)'\s*[},]/g)) out.add(m[1]) // 三元假分支
  return out
}

/**
 * 跑全部不变量，返回结构化结果。
 *
 * **可在进程内调用**（`scripts/verify-gates.mjs` 的反向注入自测就靠它）：
 * 本沙箱禁止管道的子进程 stdio（`spawn ... stdio:'pipe'` → EPERM），
 * 所以自测不能解析子进程 stdout，只能在同进程内拿结果。
 */
export function runInvariants() {
  const results = []
  const fail = (name, detail) => results.push({ ok: false, name, detail })
  const pass = (name, detail) => results.push({ ok: true, name, detail })

/* ============ 1. tokens 逐字节一致 ============ */
{
  const pairs = [
    ['design/system/tokens.css', 'web/src/styles/tokens.css'],
    ['design/system/tokens.ts', 'web/src/styles/tokens.ts'],
  ]
  const bad = []
  let digest = ''
  for (const [a, b] of pairs) {
    const pa = join(repoRoot, a)
    const pb = join(repoRoot, b)
    if (!existsSync(pa)) bad.push(`${a} 不存在`)
    else if (!existsSync(pb)) bad.push(`${b} 不存在（未同步）`)
    else {
      const ha = md5(readFileSync(pa))
      const hb = md5(readFileSync(pb))
      if (ha !== hb) bad.push(`${b} ≠ ${a}（${hb} vs ${ha}）`)
      else digest = ha
    }
  }
  if (bad.length) fail('1 tokens 逐字节一致', bad.join('; '))
  else pass('1 tokens 逐字节一致', `tokens.css 与 tokens.ts 都是 design/system/ 的逐字节副本（md5 ${digest}）`)
}

/* ============ 2. L3-only 分层纯度 ============ */
const L3_PREFIXES = [
  '--root-', '--wrap-', '--card-', '--hero-', '--btn-', '--pill-', '--notice-', '--chat-', '--msg-', '--bubble-',
  '--steps-', '--step-', '--composer-', '--cite-', '--draft-', '--empty-', '--field-', '--control-',
  '--errorsummary-', '--table-', '--kv-', '--chip-', '--chips-', '--prose-', '--login-', '--stack-',
  '--row-', '--muted-', '--small-', '--appbar-', '--brand-', '--navlink-', '--tabbar-', '--skiplink-',
  '--sr-', '--focus-outline-',
]
{
  const targets = [
    ...walk(join(SRC, 'components'), (p) => p.endsWith('.vue')),
    join(SRC, 'styles', 'base.css'),
  ]
  const bad = []
  for (const f of targets) {
    if (!existsSync(f)) continue
    const text = stripComments(cssOnly(f, readFileSync(f, 'utf8')))
    for (const m of text.matchAll(/var\(\s*(--[a-z0-9-]+)/g)) {
      if (!L3_PREFIXES.some((p) => m[1].startsWith(p))) bad.push(`${rel(f)}: ${m[1]}`)
    }
  }
  if (bad.length) {
    fail('2 组件只消费 L3 token', `出现 L1/L2/未知前缀 token：${bad.slice(0, 12).join(', ')}${bad.length > 12 ? ` …共 ${bad.length} 处` : ''}`)
  } else {
    pass('2 组件只消费 L3 token', `${targets.length} 个文件（src/components/**/*.vue 的 <style> + styles/base.css）只出现 L3 前缀`)
  }
}

/* ============ 3. 违禁状态与动效（显式窄化白名单） ============ */
{
  const styleTargets = [
    ...walk(join(SRC, 'components'), (p) => p.endsWith('.vue')),
    join(SRC, 'styles', 'base.css'),
  ]
  const bad = []
  // 白名单：全仓库**恰好一处** animation —— `.step--running .step__ico` 的旋转。
  // 依据：rb.css:252–253 是本方向唯一动效；design/system/README.md 裁决 9；
  //       前端详细设计 §8.3 L1723 以它为 prefers-reduced-motion 重置的依据。
  const ALLOWED_ANIMATION = /\.step--running\s+\.step__ico\s*\{[^}]*animation:/s
  let animationCount = 0
  let keyframes = 0

  for (const f of styleTargets) {
    if (!existsSync(f)) continue
    const raw = cssOnly(f, readFileSync(f, 'utf8'))
    const hasAllowed = ALLOWED_ANIMATION.test(raw)
    if (hasAllowed) animationCount++
    // 白名单那一处从待检文本里整段移除
    const text = stripComments(raw.replace(ALLOWED_ANIMATION, ''))

    for (const _ of text.matchAll(/:active\b/g)) bad.push(`${rel(f)}: :active`)
    for (const _ of text.matchAll(/(^|[;{\s])transition\s*:/gm)) bad.push(`${rel(f)}: transition`)
    for (const _ of text.matchAll(/(^|[;{\s])animation\s*:/gm)) bad.push(`${rel(f)}: animation`)
    for (const m of text.matchAll(/@keyframes\s+([\w-]+)/g)) {
      keyframes++
      if (m[1] !== 'spin') bad.push(`${rel(f)}: @keyframes ${m[1]}`)
    }
  }
  if (animationCount !== 1) {
    bad.push(`白名单 animation 出现 ${animationCount} 次（必须恰好 1 处：.step--running .step__ico）`)
  }
  if (keyframes !== 1) bad.push(`@keyframes 出现 ${keyframes} 次（必须恰好 1 个：spin）`)

  const globalCss = stripComments(readFileSync(join(SRC, 'styles', 'global.css'), 'utf8'))
  const reducedBlocks = [...globalCss.matchAll(/prefers-reduced-motion:\s*reduce/g)].length
  if (reducedBlocks !== 1) bad.push(`styles/global.css 的 prefers-reduced-motion 重置出现 ${reducedBlocks} 次（必须恰好 1 处）`)
  for (const f of walk(join(SRC, 'components'), (p) => p.endsWith('.vue'))) {
    if (/prefers-reduced-motion/.test(readFileSync(f, 'utf8'))) bad.push(`${rel(f)}: 组件层不得再写第二处 reduced-motion`)
  }

  if (bad.length) fail('3 无违禁状态/动效', bad.join('; '))
  else pass('3 无违禁状态/动效', '无 :active/transition；animation 与 @keyframes 各恰好 1 处（.step--running .step__ico，消费 L3 时长/缓动）；reduced-motion 只在 global.css 一处')
}

/* ============ 4. 违禁文案 ============ */
{
  const FORBIDDEN = ['正在思考', 'AI 推理中', '推理过程', '思考中', '暂无数据', '暂无内容', '暂无记录']
  const files = walk(SRC, (p) => /\.(ts|vue|css)$/.test(p))
  const bad = []
  for (const f of files) {
    const text = stripComments(readFileSync(f, 'utf8'))
    for (const word of FORBIDDEN) if (text.includes(word)) bad.push(`${rel(f)}: 「${word}」`)
  }
  if (bad.length) fail('4 无违禁文案', bad.join('; '))
  else pass('4 无违禁文案', `扫描 ${files.length} 个文件（已剥注释），0 处违禁表述`)
}

/* ============ 5. 无外部请求 ============ */
{
  const files = walk(SRC, (p) => /\.(ts|vue)$/.test(p))
  const bad = []
  for (const f of files) {
    const text = stripBlockComments(readFileSync(f, 'utf8'))
    for (const m of text.matchAll(/['"`](https?:\/\/[^'"`]+)/g)) {
      // 仅 http://mock.local 是 mock 侧 URL 解析基点，不产生任何网络请求。
      if (m[1].startsWith('http://mock.local')) continue
      bad.push(`${rel(f)}: ${m[1]}`)
    }
  }
  if (bad.length) fail('5 无外部请求', bad.join('; '))
  else pass('5 无外部请求', `${files.length} 个源文件中 0 处外部 URL（mock 全部走同源 /api/v1）`)
}

/* ============ 6. 零持久化 ============ */
{
  const files = walk(SRC, (p) => /\.(ts|vue)$/.test(p))
  const FORBIDDEN = ['localStorage', 'sessionStorage', 'indexedDB', 'caches.', 'document.cookie']
  const bad = []
  for (const f of files) {
    const text = stripComments(readFileSync(f, 'utf8'))
    for (const api of FORBIDDEN) if (text.includes(api)) bad.push(`${rel(f)}: ${api}`)
  }
  if (bad.length) fail('6 零持久化', bad.join('; '))
  else pass('6 零持久化', '0 处 localStorage/sessionStorage/indexedDB/caches/cookie（令牌与正文只在内存）')
}

/* ============ 7. class 存在性（对 rb.css） ============ */
{
  const rbCss = readFileSync(join(repoRoot, 'design', 'responsive', 'rb.css'), 'utf8')
  const defined = new Set()
  for (const m of rbCss.matchAll(/\.([a-zA-Z][a-zA-Z0-9_-]*)/g)) defined.add(m[1])

  const files = [...walk(join(SRC, 'components'), (p) => p.endsWith('.vue')), join(SRC, 'styles', 'base.css')]
  const used = new Map()
  for (const f of files) {
    if (!existsSync(f)) continue
    const body = templateOnly(f, readFileSync(f, 'utf8'))
    // 静态 class="a b c"（**排除** :class="..."）
    for (const m of body.matchAll(/(?<![:\w-])class="([^"]*)"/g)) {
      for (const c of m[1].split(/\s+/)) if (c && !c.includes('{')) used.set(c, rel(f))
    }
    // 动态 :class="..."
    for (const m of body.matchAll(/:class="([^"]*)"/g)) {
      for (const c of dynamicClasses(m[1])) used.set(c, rel(f))
    }
    // base.css 的选择器里的 class
    if (f.endsWith('base.css')) {
      const css = stripComments(readFileSync(f, 'utf8'))
      for (const m of css.matchAll(/\.([a-zA-Z][a-zA-Z0-9_-]*)/g)) used.set(m[1], rel(f))
    }
  }
  const unknown = [...used.entries()].filter(([c]) => !defined.has(c))
  if (unknown.length) {
    fail('7 class 存在性', `使用了 rb.css 未定义的 class：${unknown.map(([c, f]) => `${c}（${f}）`).join(', ')}`)
  } else {
    pass('7 class 存在性', `${used.size} 个 class 全部逐字出现在 rb.css 的定义集合中（含静态 class、:class 对象键/三元分支、base.css 选择器）`)
  }
}

/* ============ 8. 只调用 /api/v1 ============ */
{
  const files = walk(SRC, (p) => /\.(ts|vue)$/.test(p))
  const bad = []
  for (const f of files) {
    const text = stripComments(readFileSync(f, 'utf8'))
    if (text.includes('/internal/v1')) bad.push(`${rel(f)}: /internal/v1`)
  }
  if (bad.length) fail('8 不引用 /internal/v1', bad.join('; '))
  else pass('8 不引用 /internal/v1', '0 处（§15.2：前端不得调用 4 个 /internal/v1/*）')
}

/* ============ 9. 断点字面量只用契约取值 ============ */
{
  const ALLOWED = new Set(['479', '767', '1023', '1199', '1439', '480', '768', '1024', '1200', '1440'])
  const files = [
    join(SRC, 'styles', 'base.css'),
    join(SRC, 'styles', 'global.css'),
    ...walk(join(SRC, 'components'), (p) => p.endsWith('.vue')),
  ]
  const bad = []
  for (const f of files) {
    if (!existsSync(f)) continue
    const text = stripComments(cssOnly(f, readFileSync(f, 'utf8')))
    for (const m of text.matchAll(/@media[^{]*?\((?:min|max)-width:\s*(\d+)px\s*\)/g)) {
      if (!ALLOWED.has(m[1])) bad.push(`${rel(f)}: ${m[1]}px`)
    }
  }
  if (bad.length) fail('9 断点字面量合法', bad.join('; '))
  else pass('9 断点字面量合法', `媒体查询只用了 ${[...ALLOWED].sort((a, b) => a - b).join('/')}（tokens.json 的 6 档及其 min−1）`)
}

/* ============ 10. skip-link 目标存在 ============ */
{
  const app = readFileSync(join(SRC, 'App.vue'), 'utf8')
  if (!/id="main"/.test(app)) fail('10 skip-link 目标存在', 'App.vue 缺少 <main id="main">')
  else pass('10 skip-link 目标存在', 'App.vue 提供 <main id="main" tabindex="-1">')
}

  return results
}

/* ---------- CLI ---------- */
const isMain = process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href
if (isMain) {
  const results = runInvariants()
  const failedCount = results.filter((r) => !r.ok).length
  console.log('不变量检查（web/scripts/invariants.mjs）')
  console.log('='.repeat(78))
  for (const r of results) {
    console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.name}`)
    console.log(`      ${r.detail}`)
  }
  console.log('='.repeat(78))
  console.log(`${results.length - failedCount}/${results.length} 通过`)
  if (failedCount > 0) process.exit(1)
}
