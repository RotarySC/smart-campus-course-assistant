#!/usr/bin/env node
/**
 * tokens 同步器（前端详细设计 §8.1 同步机制 + §14.4）。
 *
 * 唯一的合法路径：
 *   1) 改 `design/system/tokens.json`
 *   2) `python design/system/generate.py`      → 产出 design/system/tokens.{css,ts}
 *   3) `node web/scripts/sync-tokens.mjs`      → 逐字节复制到 web/src/styles/
 *   4) `node web/scripts/sync-tokens.mjs --check` + `node web/scripts/invariants.mjs`
 *
 * **两个文件都要同步、都要校验哈希**（前端详细设计 §8.3 要求 JS 侧从
 * `@/styles/tokens` 读断点，所以 tokens.ts 与 tokens.css 同等重要）。
 *
 * `--check`：内容不一致即非 0 退出（CI 门 §14.5 第 4 条）。
 * 不使用 `node_modules/.bin` 垫片，只用 node 内置模块（见 README 的沙箱说明）。
 */

import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const webRoot = resolve(here, '..')
const repoRoot = resolve(webRoot, '..')

const PAIRS = [
  { src: join(repoRoot, 'design', 'system', 'tokens.css'), dst: join(webRoot, 'src', 'styles', 'tokens.css') },
  { src: join(repoRoot, 'design', 'system', 'tokens.ts'), dst: join(webRoot, 'src', 'styles', 'tokens.ts') },
]

const checkOnly = process.argv.includes('--check')

function md5(buf) {
  return createHash('md5').update(buf).digest('hex')
}

let failed = false

for (const { src, dst } of PAIRS) {
  const rel = relative(repoRoot, src).replaceAll('\\', '/')
  const dstRel = relative(repoRoot, dst).replaceAll('\\', '/')

  if (!existsSync(src)) {
    console.error(`FAIL  ${rel} 不存在 —— 先跑 \`python design/system/generate.py\``)
    failed = true
    continue
  }
  const srcBuf = readFileSync(src)

  if (checkOnly) {
    if (!existsSync(dst)) {
      console.error(`FAIL  ${dstRel} 不存在（未同步）`)
      failed = true
      continue
    }
    const dstBuf = readFileSync(dst)
    if (md5(srcBuf) === md5(dstBuf)) {
      console.log(`OK    ${dstRel} 与 ${rel} 逐字节一致（md5 ${md5(srcBuf)}）`)
    } else {
      console.error(`FAIL  ${dstRel} 与 ${rel} 不一致`)
      console.error(`      src md5=${md5(srcBuf)}  bytes=${srcBuf.length}`)
      console.error(`      dst md5=${md5(readFileSync(dst))}  bytes=${readFileSync(dst).length}`)
      failed = true
    }
    continue
  }

  mkdirSync(dirname(dst), { recursive: true })
  const before = existsSync(dst) ? readFileSync(dst) : null
  writeFileSync(dst, srcBuf)
  if (before === null) {
    console.log(`WROTE ${dstRel}（新建，md5 ${md5(srcBuf)}）`)
  } else if (md5(before) === md5(srcBuf)) {
    console.log(`SAME  ${dstRel}（内容未变）`)
  } else {
    const a = before.toString('utf8').split('\n')
    const b = srcBuf.toString('utf8').split('\n')
    const diff = Math.abs(a.length - b.length) + a.filter((l, i) => l !== b[i]).length
    console.log(`WROTE ${dstRel}（覆盖，约 ${diff} 行差异，新 md5 ${md5(srcBuf)}）`)
  }
}

if (failed) {
  console.error('\n同步校验未通过：web/src/styles/tokens.{css,ts} 必须是 design/system/ 产物的逐字节副本。')
  process.exit(1)
}
console.log('\n同步校验全部通过。')
