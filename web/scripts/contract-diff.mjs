#!/usr/bin/env node
/**
 * contract-diff.mjs —— 契约门禁：**设计包 OpenAPI** vs **后端运行态 OpenAPI**
 *
 * 依据：PHASE-04 F2/F3「发现后端与 OpenAPI 不一致 → 记录端点/期望/实际并报告」、
 * PHASE-PLAN R3「契约漂移」。
 *
 * 为什么需要它（而不是让 gen-types 直接吃运行态 OpenAPI）：
 *   后端 FastAPI 目前未声明 `response_model` / `responses=`，运行态 OpenAPI 缺全部响应模型与
 *   错误响应（2026-10-23 实测 components.schemas 仅 13 个请求体）。若以它为类型真源，前端会
 *   丢掉 `Me/Plan/Schedule/Session` 等全部响应类型。因此：
 *     - 类型生成以**设计包**为真源（确定性、可离线、含完整契约）；
 *     - 本脚本把运行态当**被检对象**，抓「真实契约漂移」；
 *     - 后端补齐文档后，可把 `gen-types.mjs --source=http` 切为真源（切换条件见 WARN 清零）。
 *
 * 严重度：
 *   FAIL —— 前端会因此写错：路径/operationId 缺失或改名、请求体字段/必填不一致、
 *           同名 schema 字段/必填不一致、枚举不一致。
 *   WARN —— 文档化缺口（行为可能正确，但 OpenAPI 未表达）：缺响应模型、缺错误响应、
 *           创建/异步端点文档状态码与设计不一致、运行态多出的内部路径。
 *
 * 用法：
 *   node scripts/contract-diff.mjs                          # 默认对比 http://127.0.0.1:8100/api/v1/openapi.json
 *   node scripts/contract-diff.mjs --url=<url>              # 指定运行态 OpenAPI
 *   node scripts/contract-diff.mjs --runtime=<file.json>    # 用离线的运行态快照对比
 *   node scripts/contract-diff.mjs --json=<out.json>        # 结构化结果落盘
 *
 * 退出码：0 = 无 FAIL（允许 WARN）；1 = 有 FAIL / 运行态不可达。
 */

import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const WEB_ROOT = resolve(HERE, '..')
const REPO_ROOT = resolve(WEB_ROOT, '..')
const DESIGN_SPEC = resolve(REPO_ROOT, 'contracts/openapi_v0.1.json')
const DEFAULT_URL = 'http://127.0.0.1:8100/api/v1/openapi.json'

const argv = process.argv.slice(2)
const opt = (name, fallback) => {
  const hit = argv.find((a) => a === `--${name}` || a.startsWith(`--${name}=`))
  if (!hit) return fallback
  const i = hit.indexOf('=')
  return i < 0 ? true : hit.slice(i + 1)
}

const URL_ = String(opt('url', DEFAULT_URL))
const RUNTIME_FILE = opt('runtime', null)
const JSON_OUT = opt('json', null)

const fails = []
const warns = []
const info = []
const FAIL = (area, msg) => {
  fails.push({ area, msg })
  console.log(`FAIL  [${area}] ${msg}`)
}
const WARN = (area, msg) => {
  warns.push({ area, msg })
  console.log(`WARN  [${area}] ${msg}`)
}
const INFO = (msg) => {
  info.push(msg)
  console.log(`INFO  ${msg}`)
}
const METHODS = ['get', 'post', 'patch', 'delete', 'put']
const isPublic = (p) => !p.startsWith('/internal')

const design = JSON.parse(readFileSync(DESIGN_SPEC, 'utf8'))

async function loadRuntime() {
  if (RUNTIME_FILE) {
    return JSON.parse(readFileSync(String(RUNTIME_FILE), 'utf8'))
  }
  try {
    const res = await fetch(URL_, { headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(5000) })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const text = await res.text()
    if (!text.trimStart().startsWith('{')) throw new Error('响应不是 JSON（可能是 SPA 回退）')
    return JSON.parse(text)
  } catch (e) {
    console.error(`FATAL 运行态 OpenAPI 不可读：${RUNTIME_FILE ?? URL_}（${e?.message ?? e}）`)
    console.error('      后端未启动时无法做运行态契约对比；离线可用 --runtime=<snapshot.json>')
    process.exit(1)
  }
}

const runtime = await loadRuntime()

console.log('== 契约对比：设计包 vs 运行态 ==')
console.log(`design : ${DESIGN_SPEC}`)
console.log(`runtime: ${RUNTIME_FILE ?? URL_}`)
console.log('')

/* ------------------------------ 1. 路径与操作 ------------------------------ */

const dPaths = Object.keys(design.paths ?? {}).filter(isPublic)
const rPaths = Object.keys(runtime.paths ?? {}).filter(isPublic)
const rSet = new Set(rPaths)
const dSet = new Set(dPaths)

for (const p of dPaths) {
  if (!rSet.has(p)) FAIL('path', `设计有、运行态缺失：${p}`)
}
for (const p of rPaths) {
  if (!dSet.has(p)) WARN('path', `运行态多出设计包没有的路径：${p}`)
}

const dOps = {}
const rOps = {}
for (const p of dPaths) for (const m of METHODS) if (design.paths[p]?.[m]) dOps[`${m} ${p}`] = design.paths[p][m]
for (const p of rPaths) for (const m of METHODS) if (runtime.paths[p]?.[m]) rOps[`${m} ${p}`] = runtime.paths[p][m]

for (const k of Object.keys(dOps)) {
  if (!rOps[k]) FAIL('operation', `设计有、运行态缺失：${k.toUpperCase()}`)
}
for (const k of Object.keys(dOps)) {
  const a = dOps[k]
  const b = rOps[k]
  if (!b) continue
  if (a.operationId !== b.operationId) FAIL('operationId', `${k.toUpperCase()}：设计=${a.operationId} 运行态=${b.operationId}`)
}

/* ---------------------------- 2. 请求体字段/必填 ---------------------------- */

function requestBodySchema(op) {
  const s = op.requestBody?.content?.['application/json']?.schema
  if (!s) return null
  if (s.$ref) {
    const name = s.$ref.split('/').pop()
    return { name, schema: design.components.schemas[name] ?? {} }
  }
  return { name: '(inline)', schema: s }
}

for (const k of Object.keys(dOps)) {
  const db = requestBodySchema(dOps[k])
  if (!db) continue
  const rSchema = rOps[k]?.requestBody?.content?.['application/json']?.schema
  if (!rSchema) {
    WARN('request-body', `${k.toUpperCase()}：设计声明请求体 ${db.name}，运行态未声明（需确认后端实现是否接收）`)
    continue
  }
  let rb
  if (rSchema.$ref) {
    const n = rSchema.$ref.split('/').pop()
    rb = { name: n, schema: runtime.components.schemas?.[n] ?? {} }
  } else {
    rb = { name: '(inline)', schema: rSchema }
  }
  const dProps = Object.keys(db.schema.properties ?? {})
  const rProps = Object.keys(rb.schema.properties ?? {})
  const missing = dProps.filter((x) => !rProps.includes(x))
  const extra = rProps.filter((x) => !dProps.includes(x))
  const dReq = db.schema.required ?? []
  const rReq = rb.schema.required ?? []
  const reqMissing = dReq.filter((x) => !rReq.includes(x))
  const reqExtra = rReq.filter((x) => !dReq.includes(x))
  if (missing.length || extra.length || reqMissing.length || reqExtra.length) {
    FAIL(
      'request-body',
      `${k.toUpperCase()}：字段缺=[${missing.join(',')}] 多=[${extra.join(',')}] 必填缺=[${reqMissing.join(',')}] 必填多=[${reqExtra.join(',')}]`,
    )
  }
}

/* ------------------------------ 3. 状态码（文档化） ------------------------------ */

for (const k of Object.keys(dOps)) {
  if (!rOps[k]) continue
  const dCodes = Object.keys(dOps[k].responses ?? {})
  const rCodes = Object.keys(rOps[k].responses ?? {})
  const missing = dCodes.filter((c) => !rCodes.includes(c))
  if (missing.length > 0) {
    WARN('status-doc', `${k.toUpperCase()}：运行态未声明响应码 [${missing.join(',')}]（设计含 ${dCodes.length} 个）`)
  }
}

/* ------------------------------ 4. schema 字段/枚举 ------------------------------ */

const dSchemas = Object.keys(design.components.schemas ?? {})
const rSchemas = Object.keys(runtime.components.schemas ?? {})
const missingSchemas = dSchemas.filter((n) => !rSchemas.includes(n))
if (missingSchemas.length > 0) {
  WARN(
    'schema-doc',
    `运行态缺 ${missingSchemas.length}/${dSchemas.length} 个 schema（响应模型/错误模型未声明）：${missingSchemas.slice(0, 8).join(',')}${missingSchemas.length > 8 ? ' …' : ''}`,
  )
}

for (const n of dSchemas) {
  if (!rSchemas.includes(n)) continue
  const a = design.components.schemas[n]
  const b = runtime.components.schemas[n]
  const dProps = Object.keys(a.properties ?? {})
  const rProps = Object.keys(b.properties ?? {})
  const missing = dProps.filter((x) => !rProps.includes(x))
  const extra = rProps.filter((x) => !dProps.includes(x))
  const dReq = a.required ?? []
  const rReq = b.required ?? []
  const reqMissing = dReq.filter((x) => !rReq.includes(x))
  const reqExtra = rReq.filter((x) => !dReq.includes(x))
  if (missing.length || extra.length || reqMissing.length || reqExtra.length) {
    FAIL('schema', `${n}：字段缺=[${missing.join(',')}] 多=[${extra.join(',')}] 必填缺=[${reqMissing.join(',')}] 必填多=[${reqExtra.join(',')}]`)
  }
  for (const [field, ap] of Object.entries(a.properties ?? {})) {
    const bp = b.properties?.[field]
    if (!bp) continue
    const ae = ap.enum ?? ap.items?.enum
    const be = bp.enum ?? bp.items?.enum
    if (ae && be && JSON.stringify(ae) !== JSON.stringify(be)) {
      FAIL('enum', `${n}.${field}：设计=${JSON.stringify(ae)} 运行态=${JSON.stringify(be)}`)
    }
    if (ae && !be) WARN('enum-doc', `${n}.${field}：设计有 enum，运行态未声明（需确认实现）`)
  }
}

/* --------------------------------- 结果 -------------------------------- */

INFO(`公开路径：设计 ${dPaths.length} / 运行态 ${rPaths.length}；操作：设计 ${Object.keys(dOps).length} / 运行态 ${Object.keys(rOps).length}`)
INFO(`schema：设计 ${dSchemas.length} / 运行态 ${rSchemas.length}`)

const report = {
  generatedAt: new Date().toISOString(),
  design: DESIGN_SPEC,
  runtime: RUNTIME_FILE ?? URL_,
  counts: {
    designPaths: dPaths.length,
    runtimePaths: rPaths.length,
    designOps: Object.keys(dOps).length,
    runtimeOps: Object.keys(rOps).length,
    designSchemas: dSchemas.length,
    runtimeSchemas: rSchemas.length,
  },
  fails,
  warns,
}
if (JSON_OUT) writeFileSync(String(JSON_OUT), JSON.stringify(report, null, 2))

console.log('')
if (fails.length === 0) {
  console.log(`OK    无真实契约漂移（FAIL=0；WARN=${warns.length}，均为已裁决的运行态命名/文档差异）`)
  console.log('      裁决（PHASE-04 报告 §3.3）：WARN 不追清零；gen-types 默认真源保持 file，--source=http 仅作对比。')
  process.exit(0)
} else {
  console.log(`FAIL  真实契约漂移 ${fails.length} 项（WARN=${warns.length}）；详见上方 FAIL 行。`)
  process.exit(1)
}
