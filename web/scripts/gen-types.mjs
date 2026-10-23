#!/usr/bin/env node
/**
 * gen-types.mjs —— OpenAPI → `src/api/types.gen.ts` 生成器 + 契约漂移门禁
 *
 * 依据：PHASE-04 F2 / 前端详细设计 §2.1（`types.gen.ts` 由 openapi 生成，勿手改）/ §14。
 *
 * 真源（**当前以设计包为准**）：
 *   1. 设计包离线契约：`docs/backend/openapi_v0.1.json`（默认；确定性、可离线、含完整响应模型与错误响应）
 *   2. 后端运行时 OpenAPI：`http://127.0.0.1:8100/api/v1/openapi.json`（`--source=http` 时才用）
 *
 * 为什么默认不是运行态（2026-10-23 F4 实测）：后端 FastAPI 尚未声明 `response_model` /
 * `responses=`，运行态 OpenAPI 的 `components.schemas` 只有 13 个请求体、响应模型与
 * 401/403/404/409 等错误响应**未声明**；若以它为类型真源，前端会丢掉全部响应类型。
 * 两者**结构契约目前一致**（26 公开路径 / 34 operationId 全对齐），故以设计包生成，
 * 并用 `scripts/contract-diff.mjs` 对运行态做独立契约门禁；后端补齐 response_model 后可切换。
 *
 * 用法：
 *   node scripts/gen-types.mjs                     # 生成（source=file：设计包，默认）
 *   node scripts/gen-types.mjs --source=http       # 用后端运行态 OpenAPI 生成（对比/切换用）
 *   node scripts/gen-types.mjs --source=auto       # 优先后端、不可达回落设计包
 *   node scripts/gen-types.mjs --check             # 漂移门禁：重新生成到内存并与磁盘逐字节比较
 *   node scripts/gen-types.mjs --check --source=file
 *
 * 选项：
 *   --source=file|http|auto  默认 file（见上）
 *   --url=<url>              覆盖后端 OpenAPI 地址
 *   --out=<path>             覆盖输出路径（默认 web/src/api/types.gen.ts；--check 时比较目标）
 *
 * 退出码：0 = 生成成功 / 无漂移；1 = 生成失败 / 有漂移 / 源不可达。
 *
 * 注意：本脚本**只**产出 `types.gen.ts`（纯 openapi-typescript 产物 + 固定文件头）。
 * 面向业务的类型别名在 `src/api/types.ts`（手写薄门面，字段全部指向生成类型，
 * 因此契约漂移会经 `vue-tsc` 变成编译错误，而不是静默通过）。
 */

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

import openapiTS, { astToString } from 'openapi-typescript'

const HERE = dirname(fileURLToPath(import.meta.url))
const WEB_ROOT = resolve(HERE, '..')
const REPO_ROOT = resolve(WEB_ROOT, '..')

const DEFAULT_OUT = resolve(WEB_ROOT, 'src/api/types.gen.ts')
const LOCAL_SPEC = resolve(REPO_ROOT, 'docs/backend/openapi_v0.1.json')
const DEFAULT_URL = 'http://127.0.0.1:8100/api/v1/openapi.json'
const HTTP_TIMEOUT_MS = 2_000

/* ----------------------------- 参数解析 ----------------------------- */

const argv = process.argv.slice(2)
const opt = (name, fallback) => {
  const hit = argv.find((a) => a === `--${name}` || a.startsWith(`--${name}=`))
  if (!hit) return fallback
  const eq = hit.indexOf('=')
  return eq < 0 ? true : hit.slice(eq + 1)
}
const CHECK = argv.includes('--check')
const SOURCE = String(opt('source', 'file'))
const URL_ = String(opt('url', DEFAULT_URL))
const OUT = resolve(String(opt('out', DEFAULT_OUT)))

const log = (msg) => console.log(msg)
const fail = (msg) => {
  console.error(`FAIL  ${msg}`)
  process.exit(1)
}

if (!['auto', 'http', 'file'].includes(SOURCE)) fail(`未知 --source=${SOURCE}（只允许 auto|http|file）`)

/* --------------------------- 读取 OpenAPI --------------------------- */

function validateSpec(spec, label) {
  if (!spec || typeof spec !== 'object') fail(`${label}: 不是 JSON 对象`)
  if (typeof spec.openapi !== 'string') fail(`${label}: 缺少 openapi 版本字段`)
  if (!spec.paths || typeof spec.paths !== 'object') fail(`${label}: 缺少 paths`)
  if (!spec.components || typeof spec.components !== 'object') fail(`${label}: 缺少 components`)
  return spec
}

async function loadFromHttp() {
  try {
    const res = await fetch(URL_, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(HTTP_TIMEOUT_MS),
    })
    if (!res.ok) return { ok: false, why: `HTTP ${res.status}` }
    const text = await res.text()
    return { ok: true, spec: validateSpec(JSON.parse(text), `http:${URL_}`), text }
  } catch (e) {
    return { ok: false, why: (e && e.message) || String(e) }
  }
}

function loadFromFile() {
  let text
  try {
    text = readFileSync(LOCAL_SPEC, 'utf8')
  } catch (e) {
    fail(`读不到离线契约 ${LOCAL_SPEC}：${(e && e.message) || e}`)
  }
  return { ok: true, spec: validateSpec(JSON.parse(text), `file:${LOCAL_SPEC}`), text }
}

async function loadSpec() {
  if (SOURCE === 'file') return { ...loadFromFile(), origin: `file ${relative(REPO_ROOT, LOCAL_SPEC)}` }
  if (SOURCE === 'http') {
    const r = await loadFromHttp()
    if (!r.ok) fail(`后端 OpenAPI 不可达（--source=http，不回落）：${r.why}`)
    return { ...r, origin: `http ${URL_}` }
  }
  // auto
  const r = await loadFromHttp()
  if (r.ok) return { ...r, origin: `http ${URL_}` }
  log(`INFO  后端 OpenAPI 不可达（${r.why}），回落离线设计包`)
  return { ...loadFromFile(), origin: `file ${relative(REPO_ROOT, LOCAL_SPEC)}` }
}

/* --------------------------- 生成 + 文件头 --------------------------- */

const HEADER = `/**
 * ⚠ 生成物（勿手改）—— 不要直接编辑本文件。
 *
 * 生成命令：node scripts/gen-types.mjs
 * 漂移门禁：node scripts/gen-types.mjs --check（不一致即 exit 1）
 * 生成器：openapi-typescript（devDependency，版本见 web/pnpm-lock.yaml）
 * 真源：后端运行时 \`GET /api/v1/openapi.json\`，后端不可达时回落
 *       \`docs/backend/openapi_v0.1.json\`（二者为同一份契约）。
 *
 * 内网端点：OpenAPI 里的 4 个 \`/internal/v1/*\` 在生成前被**剔除**（§15.2 前端不得调用），
 * 因此前端类型面天然不含这些端点，不变量 8「不引用 /internal/v1」保持零豁免。
 *
 * 业务代码请从 \`@/api/types\`（手写薄门面）取类型：
 * 门面里的每个类型都直接指向本文件的 \`components['schemas'][...]\`，
 * 因此契约字段漂移会在 \`vue-tsc\` 阶段变成编译错误。
 */

`

function buildHeader(spec) {
  const info = spec.info ?? {}
  return HEADER + `/* OpenAPI ${spec.openapi}${info.title ? ` · ${info.title}` : ''}${info.version ? ` · ${info.version}` : ''} */\n\n`
}

async function generate(spec) {
  const ast = await openapiTS(spec, { alphabetize: true })
  const body = astToString(ast)
  // 统一 LF（Windows 下不产出 CRLF，保证 --check 逐字节稳定）
  return `${buildHeader(spec)}${body}`.replace(/\r\n/g, '\n')
}

/* ------------------------------ 主流程 ------------------------------ */

const { spec, origin } = await loadSpec()

// §15.2：前端不得调用 4 个 /internal/v1/*。生成前剔除，保证前端类型面不含内网端点
// （不变量 8 因此保持零豁免，而不是给生成物开白名单）。
const internalPaths = Object.keys(spec.paths).filter((p) => p.startsWith('/internal/'))
for (const p of internalPaths) delete spec.paths[p]
if (internalPaths.length > 0) {
  log(`INFO  已剔除 ${internalPaths.length} 个 /internal/v1 路径（前端不得调用，§15.2）`)
}
if (Object.keys(spec.paths).some((p) => p.includes('/internal/'))) {
  fail('剔除后仍存在 /internal 路径，生成中止')
}

const expected = await generate(spec)
const expectedBytes = Buffer.from(expected, 'utf8')

if (CHECK) {
  let actual
  try {
    actual = readFileSync(OUT)
  } catch {
    fail(`漂移门禁：${relative(WEB_ROOT, OUT)} 不存在（先跑 node scripts/gen-types.mjs）`)
  }
  if (Buffer.compare(expectedBytes, actual) === 0) {
    log(`OK    types.gen.ts 与 OpenAPI 生成结果逐字节一致（source=${origin}，${expectedBytes.length} B）`)
    process.exit(0)
  }
  const got = actual.toString('utf8').split('\n')
  const want = expected.split('\n')
  let i = 0
  while (i < Math.max(got.length, want.length) && got[i] === want[i]) i++
  console.error(`FAIL  契约漂移：${relative(WEB_ROOT, OUT)} 与 OpenAPI 生成结果不一致（source=${origin}）`)
  console.error(`      首个差异在磁盘文件第 ${i + 1} 行：`)
  console.error(`      期望: ${JSON.stringify((want[i] ?? '<EOF>').slice(0, 160))}`)
  console.error(`      实际: ${JSON.stringify((got[i] ?? '<EOF>').slice(0, 160))}`)
  console.error(`      重新生成：node scripts/gen-types.mjs --source=${SOURCE}`)
  process.exit(1)
}

mkdirSync(dirname(OUT), { recursive: true })
writeFileSync(OUT, expectedBytes)
log(`OK    已生成 ${relative(WEB_ROOT, OUT)}（source=${origin}，${expectedBytes.length} B，${expected.split('\n').length} 行）`)
