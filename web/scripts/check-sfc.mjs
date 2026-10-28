#!/usr/bin/env node
/**
 * SFC 编译检查（`pnpm build` 在本沙箱不可用时的**代偿证据**）。
 *
 * 用 `@vue/compiler-sfc` 在**进程内**把每个 `.vue` 走一遍真实编译管线：
 *   parse → compileScript（`<script setup lang="ts">`）→ compileTemplate → compileStyle（scoped）
 *
 * 这覆盖了 Vite 构建里 SFC 那一层会报错的绝大多数情况：模板语法错误、`<script setup>`
 * 宏用法错误、`v-for`/`v-if` 结构错误、`<style scoped>` 解析错误、未闭合标签等。
 *
 * **它不能替代什么**（诚实说明）：
 *   - 不能证明依赖图可被 Rollup 打包（bare import 解析、循环依赖、tree-shaking）；
 *   - 不能证明 CSS 的最终层叠结果；
 *   - 不能证明浏览器里真的跑得起来（没有真实 DOM 与 fetch）。
 * 这三项必须在能跑 esbuild 的环境里由 `pnpm build` + 浏览器冒烟补齐。
 */

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse, compileScript, compileTemplate, compileStyle } from '@vue/compiler-sfc'

const here = dirname(fileURLToPath(import.meta.url))
const webRoot = resolve(here, '..')
const SRC = join(webRoot, 'src')

function walk(dir, filter) {
  const out = []
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry)
    const st = statSync(p)
    if (st.isDirectory()) out.push(...walk(p, filter))
    else if (filter(p)) out.push(p)
  }
  return out
}

const files = walk(SRC, (p) => p.endsWith('.vue')).sort()
let ok = 0
const failures = []

for (const file of files) {
  const relPath = relative(webRoot, file).replaceAll('\\', '/')
  const source = readFileSync(file, 'utf8')
  try {
    const { descriptor, errors } = parse(source, { filename: file })
    if (errors.length > 0) throw new Error(`parse: ${errors.map((e) => e.message).join('; ')}`)

    const id = relPath.replace(/[^a-zA-Z0-9]/g, '')
    let bindings
    if (descriptor.scriptSetup || descriptor.script) {
      const script = compileScript(descriptor, { id })
      bindings = script.bindings
    }
    if (descriptor.template) {
      const tpl = compileTemplate({
        source: descriptor.template.content,
        filename: file,
        id,
        compilerOptions: { bindingMetadata: bindings },
      })
      if (tpl.errors.length > 0) {
        throw new Error(`template: ${tpl.errors.map((e) => (typeof e === 'string' ? e : e.message)).join('; ')}`)
      }
    }
    for (const style of descriptor.styles) {
      const res = compileStyle({ source: style.content, filename: file, id, scoped: style.scoped })
      if (res.errors.length > 0) throw new Error(`style: ${res.errors.map((e) => String(e)).join('; ')}`)
    }
    ok++
  } catch (e) {
    failures.push(`${relPath}: ${e.message}`)
  }
}

console.log('SFC 编译检查（@vue/compiler-sfc，进程内）')
console.log('='.repeat(78))
if (failures.length > 0) {
  for (const f of failures) console.log(`FAIL  ${f}`)
  console.log('='.repeat(78))
  console.log(`${ok}/${files.length} 编译通过`)
  process.exit(1)
}
console.log(`PASS  ${files.length} 个 .vue 全部通过 parse → compileScript → compileTemplate → compileStyle`)
console.log('='.repeat(78))
