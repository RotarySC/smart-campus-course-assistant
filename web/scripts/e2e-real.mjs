#!/usr/bin/env node
/**
 * e2e-real.mjs —— **HTTP 级**真实联调 E2E（Phase 4 · F8）
 *
 * 与 `cdp-smoke.mjs` 的分工：
 *   - 本脚本直连**真实后端**（或经 Vite proxy），按 OpenAPI 契约逐端点断言；
 *   - `cdp-smoke.mjs` 负责浏览器渲染与控制台（UI 层）。
 *
 * 覆盖主链路（不可用/未实现的后端阶段自动 SKIP，不算 FAIL）：
 *   前置（后端 + OpenAPI 可达）→ 登录 → /me → 课表 31 天区间 → 计划创建/幂等重放/详情/更新+版本冲突/
 *   写操作核实/删除 → chat SSE（事件序列/seq/终态/状态核实）→ 引用展开 →
 *   管理端文档批次上传/发布轮询/文本预览/删除失效 → 登录负路径与登出。
 *
 * 用法：
 *   node scripts/e2e-real.mjs                        # 直连 http://127.0.0.1:8100/api/v1
 *   node scripts/e2e-real.mjs --via=proxy            # 经 http://localhost:5173/api/v1（验证 Vite proxy）
 *   node scripts/e2e-real.mjs --base=http://127.0.0.1:8100/api/v1
 *
 * 环境变量：E2E_BASE / E2E_WEB / E2E_ACCOUNT / E2E_PASSWORD / E2E_ADMIN_ACCOUNT / E2E_ADMIN_PASSWORD /
 *           E2E_CHAT_MESSAGE / E2E_TIMEOUT_MS
 *
 * 退出码：0 = 无 FAIL（允许 SKIP）；1 = 有 FAIL 或前置不可达。
 *
 * 说明：本脚本**不写产品代码路径**；种子账号只在脚本默认值里出现（PHASE-PLAN §8.3 的开发种子），
 * 可通过环境变量覆盖。上传的文档使用唯一文件名 `e2e-<时间戳>.txt`，结束时删除，避免污染演示数据。
 */

const ARG = (name, fallback) => {
  const hit = process.argv.find((a) => a === `--${name}` || a.startsWith(`--${name}=`))
  if (!hit) return fallback
  const i = hit.indexOf('=')
  return i < 0 ? true : hit.slice(i + 1)
}

const VIA_PROXY = ARG('via', '') === 'proxy'
const SKIP = new Set(String(ARG('skip', '') || '').split(',').filter(Boolean))
const WEB = String(process.env.E2E_WEB ?? 'http://localhost:5173').replace(/\/$/, '')
const BASE = String(
  ARG('base', '') || process.env.E2E_BASE || (VIA_PROXY ? `${WEB}/api/v1` : 'http://127.0.0.1:8100/api/v1'),
).replace(/\/$/, '')
const ORIGIN = BASE.replace(/\/api\/v1$/, '')
const TIMEOUT_MS = Number(process.env.E2E_TIMEOUT_MS ?? 15_000)
const ACCOUNT = process.env.E2E_ACCOUNT ?? 'student_demo'
const PASSWORD = process.env.E2E_PASSWORD ?? 'demo1234'
const ADMIN_ACCOUNT = process.env.E2E_ADMIN_ACCOUNT ?? 'admin_demo'
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'demo1234'
const CHAT_MESSAGE = process.env.E2E_CHAT_MESSAGE ?? '明天有什么课？'
const DAY = 86_400_000

/* ------------------------------- 结果与断言 ------------------------------- */

const rows = []
class Fail extends Error {}
class Skip extends Error {}

const assert = (cond, msg) => {
  if (!cond) throw new Fail(msg)
}
const require_ = (cond, reason) => {
  if (!cond) throw new Skip(reason)
}

async function step(name, endpoint, fn) {
  try {
    const detail = await fn()
    rows.push({ name, endpoint, kind: 'PASS', detail: detail ?? '' })
    console.log(`PASS  ${name}${detail ? ` — ${detail}` : ''}`)
  } catch (e) {
    if (e instanceof Skip) {
      rows.push({ name, endpoint, kind: 'SKIP', detail: e.message })
      console.log(`SKIP  ${name} — ${e.message}`)
    } else if (e instanceof Fail) {
      rows.push({ name, endpoint, kind: 'FAIL', detail: e.message })
      console.log(`FAIL  ${name} — ${e.message}`)
    } else {
      rows.push({ name, endpoint, kind: 'FAIL', detail: `异常：${e?.stack ?? e}` })
      console.log(`FAIL  ${name} — 异常：${e?.message ?? e}`)
    }
  }
}

/* -------------------------------- HTTP 基座 -------------------------------- */

function buildUrl(path, query) {
  const url = new URL(`${BASE}${path}`)
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
  }
  return url
}

async function request(path, o = {}) {
  const { method = 'GET', token, body, query, idempotencyKey, headers = {}, timeoutMs = TIMEOUT_MS } = o
  const h = { Accept: 'application/json', ...headers }
  if (token) h.Authorization = `Bearer ${token}`
  let payloadBody
  if (body !== undefined) {
    if (body instanceof FormData) payloadBody = body
    else {
      h['Content-Type'] = 'application/json'
      payloadBody = JSON.stringify(body)
    }
  }
  if (idempotencyKey) h['Idempotency-Key'] = idempotencyKey

  let res
  try {
    res = await fetch(buildUrl(path, query), {
      method,
      headers: h,
      body: payloadBody,
      signal: AbortSignal.timeout(timeoutMs),
    })
  } catch (e) {
    throw new Fail(`网络错误 ${method} ${path}：${e?.message ?? e}`)
  }
  let json = null
  const ct = res.headers.get('content-type') ?? ''
  if (ct.includes('application/json')) {
    json = await res.json().catch(() => null)
  } else {
    await res.text().catch(() => undefined)
  }
  return {
    status: res.status,
    requestId: json?.request_id ?? null,
    data: json?.data ?? null,
    error: json?.error ?? null,
    json,
  }
}

const isNotImplemented = (r) => r.status === 501
const ecode = (r) => r.error?.code ?? '<无错误码>'
const rid = (r) => (r.requestId ? `request_id=${r.requestId}` : 'request_id=<缺失>')

/** 401/403/404/409/422 等负路径断言（要求错误信封严格符合契约）。 */
function assertErrorEnvelope(r, expectedStatus, expectedCode) {
  assert(r.status === expectedStatus, `期望 HTTP ${expectedStatus}，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
  assert(typeof r.requestId === 'string' && r.requestId.length > 0, `错误响应缺 request_id（${expectedStatus}）`)
  assert(typeof r.error?.code === 'string', `错误响应缺 error.code（${expectedStatus}，${rid(r)}）`)
  if (expectedCode) {
    const codes = Array.isArray(expectedCode) ? expectedCode : [expectedCode]
    assert(codes.includes(r.error.code), `期望 code ∈ {${codes.join('|')}}，实际 ${r.error.code}（${rid(r)}）`)
  }
}

/* --------------------------------- 日期工具 --------------------------------- */

function shanghaiToday() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai' }).format(new Date())
}
function addDays(dateStr, n) {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d) + n * DAY).toISOString().slice(0, 10)
}

/* ---------------------------------- SSE ---------------------------------- */

function parseSseFrame(frame) {
  let event = 'message'
  const dataLines = []
  for (const line of frame.split('\n')) {
    if (line === '' || line.startsWith(':')) continue
    const i = line.indexOf(':')
    const field = i < 0 ? line : line.slice(0, i)
    let value = i < 0 ? '' : line.slice(i + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') dataLines.push(value)
  }
  if (dataLines.length === 0) return null
  return { event, data: JSON.parse(dataLines.join('\n')) }
}

async function chatStream(body, token) {
  const h = { Accept: 'text/event-stream', 'Content-Type': 'application/json' }
  if (token) h.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(buildUrl('/chat/stream'), {
      method: 'POST',
      headers: h,
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(120_000),
    })
  } catch (e) {
    throw new Fail(`POST /chat/stream 网络错误：${e?.message ?? e}`)
  }
  if (!res.ok) {
    const payload = await res.json().catch(() => null)
    return { notOk: true, status: res.status, requestId: payload?.request_id ?? null, error: payload?.error ?? null }
  }
  const ct = (res.headers.get('content-type') ?? '').toLowerCase()
  assert(ct.includes('text/event-stream'), `chat/stream 200 但 Content-Type=${ct || '<空>'}`)
  const reader = res.body?.getReader()
  assert(reader, 'chat/stream 响应没有 body')
  const dec = new TextDecoder()
  let buf = ''
  const events = []
  let sawTerminal = false
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      // 帧分隔符兼容 LF 与 CRLF（不同后端/SDK 会不同；真实后端常见 CRLF）。
      for (;;) {
        const lf = buf.indexOf('\n\n')
        const crlf = buf.indexOf('\r\n\r\n')
        let idx
        let sepLen
        if (crlf >= 0 && (lf < 0 || crlf < lf)) {
          idx = crlf
          sepLen = 4
        } else if (lf >= 0) {
          idx = lf
          sepLen = 2
        } else {
          break
        }
        const frame = buf.slice(0, idx).replace(/\r/g, '')
        buf = buf.slice(idx + sepLen)
        const ev = parseSseFrame(frame)
        if (!ev) continue
        events.push(ev)
        if (ev.event === 'done' || ev.event === 'error') sawTerminal = true
      }
      if (sawTerminal) break
    }
  } finally {
    try {
      await reader.cancel()
    } catch {
      /* 已结束 */
    }
  }
  return { notOk: false, status: res.status, events }
}

/* ---------------------------------- 主流程 ---------------------------------- */

const ctx = {
  token: null,
  user: null,
  adminToken: null,
  schedule: null,
  planId: null,
  planVersion: 0,
  operationId: null,
  chatRequestId: null,
  chatCitations: [],
}

async function main() {
  console.log(`== 真实联调 E2E（HTTP 级）==`)
  console.log(`BASE=${BASE}${VIA_PROXY ? '（经 Vite proxy）' : ''}`)
  console.log('')

  // ---- 前置：后端 / OpenAPI 可达 ----
  let reachable = false
  let openapi = null
  try {
    const r = await fetch(`${ORIGIN}/health`, { signal: AbortSignal.timeout(3000) })
    reachable = r.status < 500
  } catch {
    reachable = false
  }
  try {
    const r = await fetch(`${BASE}/openapi.json`, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(5000),
    })
    if (r.ok) {
      const text = await r.text()
      // Vite dev server 的 SPA 回退会让任意路径 200 并返回 HTML —— 必须按内容判断。
      if (text.trimStart().startsWith('{')) openapi = JSON.parse(text)
    }
  } catch {
    openapi = null
  }
  if (!openapi) {
    console.error(`FATAL 后端不可达或 OpenAPI 不可读：${BASE}/openapi.json 未返回 JSON。`)
    console.error(`      health 探测（${ORIGIN}/health）：${reachable ? 'HTTP<500' : '失败'}；`)
    console.error('      先启动后端：uvicorn app.entrypoints.public_api:app --port 8100（见 PHASE-PLAN §8）')
    process.exitCode = 1
    return
  }

  await step('前置：后端与 OpenAPI 可达', 'GET /health + /openapi.json', async () => {
    require_(openapi, `后端进程可达但 /openapi.json 不可读（health=${reachable}）`)
    assert(typeof openapi.openapi === 'string', 'OpenAPI 缺 openapi 版本字段')
    const publicPaths = Object.keys(openapi.paths ?? {}).filter((p) => !p.startsWith('/internal'))
    return `openapi=${openapi.openapi}，公开路径 ${publicPaths.length} 条`
  })

  /* ------------------------------ 身份 ---------------- */

  await step('登录（种子学生账号）', 'POST /auth/login', async () => {
    const r = await request('/auth/login', { method: 'POST', body: { account: ACCOUNT, password: PASSWORD } })
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(typeof r.requestId === 'string' && /^[A-Za-z0-9_-]+$/.test(r.requestId), `request_id 缺失或非法：${r.requestId}`)
    assert(typeof r.data?.access_token === 'string' && r.data.access_token.length > 0, '登录响应缺 access_token')
    assert(r.data.token_type === 'Bearer', `token_type 期望 Bearer，实际 ${r.data.token_type}`)
    assert(r.data.user?.role === 'student' || r.data.user?.role === 'admin', `user.role 非法：${r.data.user?.role}`)
    ctx.token = r.data.access_token
    ctx.user = r.data.user
    return `user=${r.data.user.account} role=${r.data.user.role}，${rid(r)}`
  })

  await step('当前身份 /me', 'GET /me', async () => {
    require_(ctx.token, '无令牌（登录失败）')
    const r = await request('/me', { token: ctx.token })
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.user?.id === ctx.user?.id, `user.id 不一致：/me=${r.data?.user?.id} login=${ctx.user?.id}`)
    assert(typeof r.data.school_timezone === 'string' && r.data.school_timezone.length > 0, '缺 school_timezone')
    assert(Array.isArray(r.data.capabilities), 'capabilities 不是数组')
    ctx.school = r.data.school_timezone
    return `school_timezone=${r.data.school_timezone}，capabilities=${r.data.capabilities.length}，${rid(r)}`
  })

  await step('会话失效契约（无效令牌 401）', 'GET /me（伪造令牌）', async () => {
    const r = await request('/me', { token: 'e2e_invalid_token' })
    assertErrorEnvelope(r, 401, ['AUTH_REQUIRED', 'SESSION_EXPIRED'])
    return `code=${r.error.code}，${rid(r)}`
  })

  /* ------------------------------ 课表 ---------------- */

  await step('我的课表：31 天区间', 'GET /me/schedules', async () => {
    require_(ctx.token, '无令牌（登录失败）')
    const from = shanghaiToday()
    const to = addDays(from, 30)
    const r = await request('/me/schedules', { token: ctx.token, query: { from_date: from, to_date: to, page: 1, page_size: 100 } })
    if (isNotImplemented(r)) throw new Skip('端点返回 501（Phase 1 未实现该端点）')
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.from_date === from && r.data.to_date === to, `区间回显不一致：${r.data?.from_date}..${r.data?.to_date}`)
    assert(Array.isArray(r.data.items), 'items 不是数组（空结果也必须是数组）')
    for (const s of r.data.items) {
      assert(typeof s.id === 'string' && typeof s.course_name === 'string', '课表项缺 id/course_name')
      assert(s.class_date >= from && s.class_date <= to, `课表日期 ${s.class_date} 越界 ${from}..${to}`)
      assert(typeof s.version === 'number', '课表项缺 version')
    }
    assert(typeof r.data.school_timezone === 'string' && r.data.school_timezone.length > 0, '课表响应缺 school_timezone')
    ctx.schedule = r.data
    return `${r.data.items.length} 条，${from}..${to}，tz=${r.data.school_timezone}，${rid(r)}`
  })

  await step('课表默认区间（不传参）', 'GET /me/schedules', async () => {
    require_(ctx.token, '无令牌（登录失败）')
    const r = await request('/me/schedules', { token: ctx.token })
    if (isNotImplemented(r)) throw new Skip('端点返回 501')
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(typeof r.data?.from_date === 'string' && typeof r.data.to_date === 'string', '缺默认区间回显')
    return `默认 ${r.data.from_date}..${r.data.to_date}，${rid(r)}`
  })

  /* ------------------------------ 计划 ---------------- */

  const planTitle = `E2E 联调计划 ${Date.now()}`
  await step('创建计划（Idempotency-Key）', 'POST /me/plans', async () => {
    require_(ctx.token, '无令牌（登录失败）')
    ctx.idemKey = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const body = { title: planTitle, content: 'E2E：先齐作业，再复习数据结构。', goal: '通过期末', start_date: shanghaiToday(), end_date: addDays(shanghaiToday(), 7) }
    const r = await request('/me/plans', { method: 'POST', token: ctx.token, body, idempotencyKey: ctx.idemKey })
    if (isNotImplemented(r)) throw new Skip('端点返回 501')
    assert(r.status === 201 || r.status === 200 || r.status === 202, `期望 201/200/202，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(typeof r.data?.operation_id === 'string', '缺 operation_id')
    ctx.operationId = r.data.operation_id
    if (r.status === 202) {
      // 待核实：轮询写操作，再按标题在列表里定位
      const resolved = await pollWriteOp(ctx.operationId)
      assert(resolved.state === 'succeeded' || resolved.state === 'deleted', `写操作未成功：state=${resolved.state} code=${resolved.error_code ?? '-'}`)
      ctx.planId = resolved.plan_id
    } else {
      assert(r.status === 201, `首次创建未新建（status=${r.status}，data.status=${r.data.status}）`)
      assert(r.data.status === 'created', `首次创建 status 期望 created，实际 ${r.data.status}`)
      ctx.planId = r.data.plan_id
    }
    return `plan_id=${ctx.planId ?? '<待列表定位>'} op=${ctx.operationId}，${rid(r)}`
  })

  await step('幂等重放（同 key 不新建）', 'POST /me/plans', async () => {
    require_(ctx.token && ctx.idemKey, '无令牌或未创建（上游失败）')
    const body = { title: planTitle, content: 'E2E：先齐作业，再复习数据结构。', goal: '通过期末', start_date: shanghaiToday(), end_date: addDays(shanghaiToday(), 7) }
    const r = await request('/me/plans', { method: 'POST', token: ctx.token, body, idempotencyKey: ctx.idemKey })
    if (isNotImplemented(r)) throw new Skip('端点返回 501')
    assert(r.status === 200, `重放期望 200（不新建），实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.operation_id === ctx.operationId, `重放 operation_id 不一致：${r.data?.operation_id} vs ${ctx.operationId}`)
    if (ctx.planId) assert(r.data.plan_id === ctx.planId, `重放 plan_id 不一致：${r.data.plan_id} vs ${ctx.planId}`)
    else ctx.planId = r.data.plan_id
    return `status=${r.data.status} op 一致，${rid(r)}`
  })

  await step('计划详情', 'GET /me/plans/{id}', async () => {
    require_(ctx.token && ctx.planId, '无 plan_id（上游失败）')
    const r = await request(`/me/plans/${encodeURIComponent(ctx.planId)}`, { token: ctx.token })
    if (isNotImplemented(r)) throw new Skip('端点返回 501')
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.id === ctx.planId, `id 不一致：${r.data?.id}`)
    assert(r.data.title === planTitle, `title 不一致：${r.data.title}`)
    assert(typeof r.data.version === 'number' && r.data.version >= 1, `version 非法：${r.data.version}`)
    ctx.planVersion = r.data.version
    return `version=${r.data.version}，${rid(r)}`
  })

  await step('更新计划 + 版本冲突（409）', 'PATCH /me/plans/{id}', async () => {
    require_(ctx.token && ctx.planId, '无 plan_id（上游失败）')
    const patch = { title: `${planTitle}（已更新）`, expected_version: ctx.planVersion }
    const r = await request(`/me/plans/${encodeURIComponent(ctx.planId)}`, { method: 'PATCH', token: ctx.token, body: patch })
    if (isNotImplemented(r)) throw new Skip('端点返回 501')
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.version === ctx.planVersion + 1, `version 期望 ${ctx.planVersion + 1}，实际 ${r.data?.version}`)
    const staleVersion = ctx.planVersion
    ctx.planVersion = r.data.version
    // 用旧版本再改一次 → 必须 409 VERSION_CONFLICT
    const stale = await request(`/me/plans/${encodeURIComponent(ctx.planId)}`, {
      method: 'PATCH',
      token: ctx.token,
      body: { title: '冲突写入', expected_version: staleVersion },
    })
    assertErrorEnvelope(stale, 409, 'VERSION_CONFLICT')
    return `version ${staleVersion}→${ctx.planVersion}，陈旧版本 409 ${stale.error.code}，${rid(r)}`
  })

  await step('写操作状态核实', 'GET /me/write-operations/{operation_id}', async () => {
    require_(ctx.token && ctx.operationId, '无 operation_id（上游失败）')
    const op = await request(`/me/write-operations/${encodeURIComponent(ctx.operationId)}`, { token: ctx.token })
    if (isNotImplemented(op)) throw new Skip('端点返回 501')
    assert(op.status === 200, `期望 200，实际 ${op.status}（${ecode(op)}，${rid(op)}）`)
    assert(op.data?.operation_id === ctx.operationId, 'operation_id 不一致')
    assert(['pending', 'succeeded', 'failed', 'deleted'].includes(op.data.state), `state 非法：${op.data.state}`)
    assert(['confirmed', 'recovering'].includes(op.data.resolution), `resolution 非法：${op.data.resolution}`)
    const resolved = op.data.state === 'pending' ? await pollWriteOp(ctx.operationId) : op.data
    assert(resolved.state === 'succeeded' || resolved.state === 'deleted', `最终 state 非成功：${resolved.state}`)
    return `state=${resolved.state} resolution=${resolved.resolution}，${rid(op)}`
  })

  await step('删除计划（expected_version 在 query）', 'DELETE /me/plans/{id}', async () => {
    require_(ctx.token && ctx.planId, '无 plan_id（上游失败）')
    const r = await request(`/me/plans/${encodeURIComponent(ctx.planId)}`, {
      method: 'DELETE',
      token: ctx.token,
      query: { expected_version: ctx.planVersion },
    })
    if (isNotImplemented(r)) throw new Skip('端点返回 501')
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.deleted === true, `期望 deleted=true，实际 ${r.data?.deleted}`)
    const after = await request(`/me/plans/${encodeURIComponent(ctx.planId)}`, { token: ctx.token })
    assertErrorEnvelope(after, 404, 'RESOURCE_NOT_FOUND')
    return `deleted=${ctx.planId}，删除后 GET 404，${rid(r)}`
  })

  /* ------------------------------ 助手 SSE ---------------- */

  await step('对话流（SSE 事件序列）', 'POST /chat/stream', async () => {
    require_(ctx.token, '无令牌（登录失败）')
    const clientRequestId = `e2e-${Date.now().toString(36)}`
    const res = await chatStream({ client_request_id: clientRequestId, message: CHAT_MESSAGE }, ctx.token)
    if (res.notOk) {
      if (res.status === 501) throw new Skip('端点返回 501（Phase 3 未实现）')
      assert(false, `期望 200 text/event-stream，实际 ${res.status}（${res.error?.code ?? '<无错误码>'}）`)
    }
    const events = res.events
    assert(events.length > 0, 'SSE 未收到任何事件')
    const first = events[0]
    assert(first.event === 'status', `首个事件应为 status，实际 ${first.event}`)
    assert(typeof first.data?.request_id === 'string', 'status 事件缺 request_id')
    ctx.chatRequestId = first.data.request_id
    assert(first.data.code === 'ACCEPTED', `status.code 期望 ACCEPTED，实际 ${first.data.code}`)
    assert(typeof first.data.conversation_id === 'string' && first.data.conversation_id.length > 0, 'ACCEPTED 缺 conversation_id（schema 强制）')

    // seq 严格递增（按 (request_id, seq) 去重后不得回退/重复）
    let lastSeq = 0
    for (const ev of events) {
      assert(typeof ev.data?.seq === 'number' && ev.data.seq > lastSeq, `seq 非严格递增：${ev.data?.seq} ≤ ${lastSeq}（${ev.event}）`)
      lastSeq = ev.data.seq
      assert(ev.data.request_id === ctx.chatRequestId, `事件 request_id 不一致：${ev.data.request_id}`)
    }
    // 终态唯一
    const terminals = events.filter((e) => e.event === 'done' || e.event === 'error')
    assert(terminals.length === 1, `终态事件数应为 1，实际 ${terminals.length}`)
    const term = terminals[0]
    if (term.event === 'done') {
      assert(['succeeded', 'cancelled'].includes(term.data.state), `done.state 非法：${term.data.state}`)
      assert(Array.isArray(term.data.citations), 'done.citations 必须是数组')
      ctx.chatCitations = term.data.citations
    } else {
      assert(typeof term.data.code === 'string', 'error 事件缺 code')
      assert(!(term.data.code === 'AUTH_REQUIRED' || term.data.code === 'SESSION_EXPIRED') || (term.data.plan_id === undefined && term.data.operation_id === undefined), '认证类 error 不得携带 plan_id/operation_id')
    }
    const codes = events.map((e) => e.event)
    return `${events.length} 事件（${[...new Set(codes)].join('/')}），终态 ${term.event}${term.data.state ? `:${term.data.state}` : ''}，${ctx.chatRequestId}`
  })

  await step('对话状态可核实', 'GET /chat/requests/{request_id}', async () => {
    require_(ctx.token && ctx.chatRequestId, '无 request_id（上游失败）')
    const r = await request(`/chat/requests/${encodeURIComponent(ctx.chatRequestId)}`, { token: ctx.token })
    if (isNotImplemented(r)) throw new Skip('端点返回 501')
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.request_id === ctx.chatRequestId, 'request_id 不一致')
    assert(['accepted', 'running', 'succeeded', 'failed', 'cancelled'].includes(r.data.state), `state 非法：${r.data.state}`)
    return `state=${r.data.state}，${rid(r)}`
  })

  await step('引用展开', 'GET /citations/{reference_id}', async () => {
    require_(ctx.token, '无令牌（登录失败）')
    if (!ctx.chatCitations || ctx.chatCitations.length === 0) throw new Skip('本轮回答无引用（确定性 Provider 未检索到资料）')
    const ref = ctx.chatCitations[0]
    const r = await request(`/citations/${encodeURIComponent(ref.reference_id)}`, { token: ctx.token })
    if (isNotImplemented(r)) throw new Skip('端点返回 501')
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.reference?.reference_id === ref.reference_id, 'reference_id 不一致')
    assert(typeof r.data.text === 'string' && r.data.text.length > 0, '引用片段为空')
    return `reference_id=${ref.reference_id}，片段 ${r.data.text.length} 字，${rid(r)}`
  })

  /* ---------------------------- 管理端文档批次 ---------------- */

  let adminOk = false
  await step('管理员登录', 'POST /auth/login（admin）', async () => {
    const r = await request('/auth/login', { method: 'POST', body: { account: ADMIN_ACCOUNT, password: ADMIN_PASSWORD } })
    if (isNotImplemented(r) || r.status === 401) throw new Skip(`管理员种子账号不可用（HTTP ${r.status}）`)
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.user?.role === 'admin', `期望 role=admin，实际 ${r.data?.user?.role}`)
    ctx.adminToken = r.data.access_token
    adminOk = true
    return `admin=${r.data.user.account}，${rid(r)}`
  })

  const marker = `E2E-MARKER-${Date.now()}`
  let docId = null
  await step('文档批次上传（multipart → 202）', 'POST /admin/document-batches', async () => {
    if (SKIP.has('docs')) throw new Skip('--skip=docs（Phase 2 未就绪）')
    require_(ctx.adminToken, '无管理员令牌（上游失败）')
    const fd = new FormData()
    const name = `e2e-${Date.now()}.txt`
    fd.append('files', new Blob([`${marker}\nE2E 文档批次内容。\n`], { type: 'text/plain' }), name)
    const r = await request('/admin/document-batches', { method: 'POST', token: ctx.adminToken, body: fd })
    if (isNotImplemented(r)) throw new Skip('端点返回 501（Phase 2 未实现）')
    assert(r.status === 202, `期望 202，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(typeof r.data?.batch_id === 'string', '缺 batch_id')
    assert(Array.isArray(r.data.documents), 'documents 不是数组')
    ctx.batchId = r.data.batch_id
    ctx.uploadName = name
    return `batch_id=${ctx.batchId}，${r.data.documents.length} 个文档，${rid(r)}`
  })

  await step('批次轮询至发布', 'GET /admin/document-batches/{id}', async () => {
    if (SKIP.has('docs')) throw new Skip('--skip=docs')
    require_(ctx.adminToken && ctx.batchId, '无 batch_id（上游失败）')
    const deadline = Date.now() + 90_000
    let last = null
    for (;;) {
      const r = await request(`/admin/document-batches/${encodeURIComponent(ctx.batchId)}`, { token: ctx.adminToken })
      if (isNotImplemented(r)) throw new Skip('端点返回 501')
      assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
      last = r.data
      if (['published', 'failed', 'compensating'].includes(last.state)) break
      if (Date.now() > deadline) throw new Fail(`批次 90s 未达终态（最后 state=${last?.state}）`)
      await sleep(3000)
    }
    assert(last.state === 'published' && last.published === true, `批次未发布：state=${last.state} published=${last.published} err=${last.error_code ?? '-'}`)
    const doc = last.documents.find((d) => d.original_name === ctx.uploadName) ?? last.documents[0]
    assert(doc, '批次内没有文档')
    if (doc.processing_state === 'available') docId = doc.id
    return `published，doc=${doc?.original_name} state=${doc?.processing_state}`
  })

  await step('文档列表与文本预览', 'GET /admin/documents + /{id}/text', async () => {
    if (SKIP.has('docs')) throw new Skip('--skip=docs')
    require_(ctx.adminToken && ctx.batchId, '无批次（上游失败）')
    if (!docId) throw new Skip('文档尚未 available（可能仍在处理）')
    const list = await request('/admin/documents', { token: ctx.adminToken, query: { page: 1, page_size: 100 } })
    if (isNotImplemented(list)) throw new Skip('端点返回 501')
    assert(list.status === 200, `文档列表期望 200，实际 ${list.status}（${ecode(list)}）`)
    assert(list.data?.items?.some((d) => d.id === docId), `列表未包含上传文档 ${docId}`)
    const txt = await request(`/admin/documents/${encodeURIComponent(docId)}/text`, { token: ctx.adminToken, query: { offset: 0, limit: 2000 } })
    assert(txt.status === 200, `文本预览期望 200，实际 ${txt.status}（${ecode(txt)}，${rid(txt)}）`)
    assert(typeof txt.data?.text === 'string' && txt.data.text.includes(marker), `预览文本未包含 marker（前 80 字：${txt.data?.text?.slice(0, 80)}）`)
    return `${docId} 预览 ${txt.data.text.length} 字，${rid(txt)}`
  })

  await step('文档删除 → 清理', 'DELETE /admin/documents/{id}', async () => {
    if (SKIP.has('docs')) throw new Skip('--skip=docs')
    require_(ctx.adminToken && docId, '无文档（上游失败）')
    const doc = (await request('/admin/documents', { token: ctx.adminToken, query: { page: 1, page_size: 100 } })).data?.items?.find((d) => d.id === docId)
    const version = doc?.version ?? 1
    const r = await request(`/admin/documents/${encodeURIComponent(docId)}`, {
      method: 'DELETE',
      token: ctx.adminToken,
      query: { expected_version: version },
    })
    if (isNotImplemented(r)) throw new Skip('端点返回 501')
    assert(r.status === 202, `期望 202，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.document_id === docId, 'document_id 不一致')
    // 轮询至删除终态（deleted）或清理完成
    const deadline = Date.now() + 60_000
    let last = null
    for (;;) {
      const list = await request('/admin/documents', { token: ctx.adminToken, query: { page: 1, page_size: 100 } })
      last = list.data?.items?.find((d) => d.id === docId)
      if (!last || last.processing_state === 'deleted') break
      if (Date.now() > deadline) throw new Fail(`文档 60s 未删除（state=${last?.processing_state}）`)
      await sleep(3000)
    }
    const state = last?.processing_state ?? 'deleted'
    assert(state === 'deleted' || !last, `删除未完成：state=${state}`)
    return `删除完成（state=${state}），${rid(r)}`
  })

  /* ------------------------------ 负路径 / 登出 ---------------- */

  await step('登录负路径（错误口令 401）', 'POST /auth/login', async () => {
    const r = await request('/auth/login', { method: 'POST', body: { account: ACCOUNT, password: `${PASSWORD}-wrong` } })
    assertErrorEnvelope(r, 401, ['AUTH_REQUIRED'])
    return `code=${r.error.code}，${rid(r)}`
  })

  await step('登出并确认会话撤销', 'POST /auth/logout', async () => {
    require_(ctx.token, '无令牌（登录失败）')
    const r = await request('/auth/logout', { method: 'POST', token: ctx.token })
    assert(r.status === 200, `期望 200，实际 ${r.status}（${ecode(r)}，${rid(r)}）`)
    assert(r.data?.revoked === true, `期望 revoked=true，实际 ${r.data?.revoked}`)
    const after = await request('/me', { token: ctx.token })
    assertErrorEnvelope(after, 401, ['AUTH_REQUIRED', 'SESSION_EXPIRED'])
    return `revoked，旧令牌 /me 401 ${after.error.code}，${rid(r)}`
  })

  printTable()
}

async function pollWriteOp(operationId, timeoutMs = 30_000) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    const r = await request(`/me/write-operations/${encodeURIComponent(operationId)}`, { token: ctx.token })
    if (r.status === 200 && r.data && r.data.state !== 'pending') return r.data
    if (Date.now() > deadline) {
      throw new Fail(`写操作 ${operationId} 30s 未决（最后 HTTP ${r.status}，state=${r.data?.state ?? '-'}）`)
    }
    await sleep(1000)
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function printTable() {
  const icon = { PASS: 'PASS', FAIL: 'FAIL', SKIP: 'SKIP' }
  console.log('\n================ E2E 结果表 ================')
  const cols = ['#', '结果', '步骤', '端点', '证据/原因']
  console.log(cols.join(' | '))
  rows.forEach((r, i) => {
    console.log([String(i + 1), icon[r.kind], r.name, r.endpoint, r.detail].join(' | '))
  })
  const pass = rows.filter((r) => r.kind === 'PASS').length
  const fail = rows.filter((r) => r.kind === 'FAIL').length
  const skip = rows.filter((r) => r.kind === 'SKIP').length
  console.log(`\n合计：${rows.length} 步 = PASS ${pass} / FAIL ${fail} / SKIP ${skip}`)
  if (fail > 0) process.exitCode = 1
}

main().catch((e) => {
  console.error(`FATAL E2E 脚本异常：${e?.stack ?? e?.message ?? e}`)
  process.exitCode = 1
})
