#!/usr/bin/env node
/**
 * e2e-docs.mjs —— F7「文档批次」的分段联调脚本（与 e2e-real.mjs 互补）
 *
 * 为什么分段：演示库 `publish_frozen=FALSE`，上传后必须由 Lead 在 8100 侧跑一次
 * worker（`worker --once`）才会发布。因此本脚本支持三段式：
 *   ① 上传：`node scripts/e2e-docs.mjs`                 → 打印 `BATCH_ID=<id>`（未发布时 exit 2）
 *   ② 等 worker：请 Lead 跑 worker --once
 *   ③ 续跑：`node scripts/e2e-docs.mjs --batch-id=<id>` → 轮询至 published → 文本预览 → 删除 → 失效复核
 *
 * 断言（全部真实 HTTP，不 mock）：
 *   - 上传 multipart 必须 202 + Batch{state,published,documents,tasks}；
 *   - 轮询 `GET /admin/document-batches/{id}`；accepted/processing 是**正常中间态**（不是失败）；
 *   - 发布后 `published=true`、文档 `processing_state=available`；
 *   - `GET /admin/documents/{id}/text` 返回包含 marker 的文本；
 *   - `DELETE /admin/documents/{id}?expected_version=` → 202；轮询至 deleted；
 *   - 删除后 `GET /{id}/text` → 404（资源已失效）。
 *
 * 退出码：0 = 全绿；2 = 需要 worker（中间态等待超时，不是失败）；1 = 真实 FAIL。
 *
 * 环境变量：E2E_BASE / E2E_ADMIN_ACCOUNT / E2E_ADMIN_PASSWORD / E2E_BATCH_TIMEOUT_MS（默认 240000）
 */

const BASE = (process.env.E2E_BASE ?? 'http://127.0.0.1:8100/api/v1').replace(/\/$/, '')
const ADMIN_ACCOUNT = process.env.E2E_ADMIN_ACCOUNT ?? 'admin_demo'
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'demo1234'
const TIMEOUT_MS = Number(process.env.E2E_BATCH_TIMEOUT_MS ?? 240_000)
const BATCH_ID_ARG = (process.argv.find((a) => a.startsWith('--batch-id=')) ?? '').split('=')[1] ?? ''
// 续跑既有批次时，上传内容里的 marker 由调用方传入（脚本无法从服务端反推原文）
const MARKER_ARG = (process.argv.find((a) => a.startsWith('--marker=')) ?? '').split('=')[1] ?? ''

const rows = []
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
class Skip extends Error {}
class NeedsWorker extends Error {}
class Fail extends Error {}
const assert = (c, m) => {
  if (!c) throw new Fail(m)
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
    } else if (e instanceof NeedsWorker) {
      blockedByWorker = true
      rows.push({ name, endpoint, kind: 'NEED_WORKER', detail: e.message })
      console.log(`NEED_WORKER  ${name} — ${e.message}`)
    } else {
      rows.push({ name, endpoint, kind: 'FAIL', detail: e.message ?? String(e) })
      console.log(`FAIL  ${name} — ${rows.at(-1).detail}`)
    }
  }
}

async function request(path, { method = 'GET', token, body, query, timeoutMs = 30_000 } = {}) {
  const url = new URL(`${BASE}${path}`)
  for (const [k, v] of Object.entries(query ?? {})) if (v !== undefined) url.searchParams.set(k, String(v))
  const headers = { Accept: 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  let payload
  if (body !== undefined) {
    if (body instanceof FormData) payload = body
    else {
      headers['Content-Type'] = 'application/json'
      payload = JSON.stringify(body)
    }
  }
  let res
  try {
    res = await fetch(url, { method, headers, body: payload, signal: AbortSignal.timeout(timeoutMs) })
  } catch (e) {
    throw new Fail(`网络错误 ${method} ${path}：${e?.message ?? e}`)
  }
  const json = (res.headers.get('content-type') ?? '').includes('application/json') ? await res.json().catch(() => null) : null
  return { status: res.status, requestId: json?.request_id ?? null, data: json?.data ?? null, error: json?.error ?? null }
}
const rid = (r) => (r.requestId ? `request_id=${r.requestId}` : 'request_id=<缺失>')

let token = null
let marker = MARKER_ARG || `E2E-DOC-MARKER-${Date.now()}`
/** 续跑既有批次且未给 --marker 时，无法知道上传原文里的 marker → 只断言文本非空。 */
const strictMarker = MARKER_ARG !== '' || !BATCH_ID_ARG
/** 上游 NEED_WORKER 后，依赖「已发布」的步骤一律 SKIP（不把等待当失败）。 */
let blockedByWorker = false

async function main() {
  console.log(`== F7 文档批次联调（BASE=${BASE}${BATCH_ID_ARG ? `，续跑 batch=${BATCH_ID_ARG}` : '，新上传'}）==`)

  await step('前置：后端可达', 'GET /health', async () => {
    const r = await fetch(`${BASE}/health`, { signal: AbortSignal.timeout(3000) })
    assert(r.ok, `health HTTP ${r.status}`)
    return `HTTP ${r.status}`
  })

  await step('管理员登录', 'POST /auth/login', async () => {
    const r = await request('/auth/login', { method: 'POST', body: { account: ADMIN_ACCOUNT, password: ADMIN_PASSWORD } })
    assert(r.status === 200, `期望 200，实际 ${r.status}`)
    assert(r.data?.user?.role === 'admin', `role 非 admin：${r.data?.user?.role}`)
    token = r.data.access_token
    return `admin=${r.data.user.account}，${rid(r)}`
  })

  let batchId = BATCH_ID_ARG
  await step('上传批次（multipart → 202）', 'POST /admin/document-batches', async () => {
    if (batchId) throw new Skip(`复用 --batch-id=${batchId}（不重复上传）`)
    const fd = new FormData()
    fd.append('files', new Blob([`${marker}\nF7 文档批次联调内容。\n`], { type: 'text/plain' }), `e2e-${Date.now()}.txt`)
    const r = await request('/admin/document-batches', { method: 'POST', token, body: fd })
    assert(r.status === 202, `期望 202，实际 ${r.status}（${r.error?.code ?? '-'}，${rid(r)}）`)
    assert(typeof r.data?.batch_id === 'string' && r.data.batch_id.length > 0, '缺 batch_id')
    assert(Array.isArray(r.data.documents), 'documents 不是数组')
    assert(Array.isArray(r.data.tasks), 'tasks 不是数组')
    batchId = r.data.batch_id
    console.log(`BATCH_ID=${batchId}`)
    console.log(`MARKER=${marker}`)
    return `batch_id=${batchId}，documents=${r.data.documents.length}，${rid(r)}`
  })

  if (!batchId) {
    printTable()
    process.exitCode = 1
    return
  }
  console.log(`INFO  使用批次 ${batchId}（若未发布，请 Lead 在 8100 侧跑 worker --once）`)

  await step('批次轮询至发布', 'GET /admin/document-batches/{id}', async () => {
    const deadline = Date.now() + TIMEOUT_MS
    let last = null
    for (;;) {
      const r = await request(`/admin/document-batches/${encodeURIComponent(batchId)}`, { token })
      assert(r.status === 200, `期望 200，实际 ${r.status}（${r.error?.code ?? '-'}，${rid(r)}）`)
      last = r.data
      if (['published', 'failed', 'compensating'].includes(last.state)) break
      if (Date.now() > deadline) {
        throw new NeedsWorker(
          `批次仍为 ${last.state}（等待 ${Math.round(TIMEOUT_MS / 1000)}s）。演示库 publish_frozen=FALSE：请 Lead 在 8100 侧执行 worker --once 后用 --batch-id=${batchId} 续跑（不是 FAIL）`,
        )
      }
      await sleep(3000)
    }
    if (last.state !== 'published' || last.published !== true) {
      throw new Fail(`批次终态异常：state=${last.state} published=${last.published} error_code=${last.error_code ?? '-'}`)
    }
    for (const t of last.tasks ?? []) assert(['succeeded', 'failed', 'pending', 'running', 'retry_wait'].includes(t.state), `task.state 非法：${t.state}`)
    return `published，documents=${last.documents.length}，tasks=${last.tasks.length}`
  })

  let docId = null
  let docVersion = 0
  await step('文本预览（marker 逐字）', 'GET /admin/documents/{id}/text', async () => {
    if (blockedByWorker) throw new Skip('等待 worker 发布（上游 NEED_WORKER）')
    const list = await request('/admin/documents', { token, query: { page: 1, page_size: 100 } })
    assert(list.status === 200, `文档列表期望 200，实际 ${list.status}`)
    const inBatch = (list.data?.items ?? []).filter((d) => d.batch_id === batchId)
    assert(inBatch.length > 0, `列表中没有批次 ${batchId} 的文档`)
    const doc = inBatch.find((d) => d.processing_state === 'available') ?? inBatch[0]
    if (['deleting', 'deleted'].includes(doc.processing_state)) {
      throw new Skip(`文档已进入删除流程（state=${doc.processing_state}），跳过预览`)
    }
    assert(doc.processing_state === 'available', `文档未 available：${doc.processing_state}`)
    docId = doc.id
    docVersion = doc.version
    const txt = await request(`/admin/documents/${encodeURIComponent(docId)}/text`, { token, query: { offset: 0, limit: 2000 } })
    assert(txt.status === 200, `文本预览期望 200，实际 ${txt.status}（${txt.error?.code ?? '-'}，${rid(txt)}）`)
    const text = txt.data?.text ?? ''
    if (strictMarker) {
      assert(typeof text === 'string' && text.includes(marker), `预览文本未含 marker（前 80 字：${text.slice(0, 80)}）`)
    } else {
      assert(text.length > 0, '预览文本为空')
    }
    return `${docId}（${doc.original_name}）预览 ${text.length} 字${strictMarker ? '' : '（续跑：未给 --marker，只断言非空）'}，${rid(txt)}`
  })

  await step('删除文档 → 失效复核', 'DELETE /admin/documents/{id}', async () => {
    if (blockedByWorker) throw new Skip('等待 worker 发布（上游 NEED_WORKER）')
    // 文档可能已被（外部）清理流程置为 deleting/deleted：此时只需复核「删除后不可读」。
    if (!docId) {
      const list = await request('/admin/documents', { token, query: { page: 1, page_size: 100 } })
      const doc = (list.data?.items ?? []).find((d) => d.batch_id === batchId)
      if (!doc || ['deleting', 'deleted'].includes(doc.processing_state)) {
        const id = doc?.id
        if (id) {
          const deadline0 = Date.now() + 120_000
          for (;;) {
            const l2 = await request('/admin/documents', { token, query: { page: 1, page_size: 100 } })
            const d2 = (l2.data?.items ?? []).find((x) => x.id === id)
            if (!d2 || d2.processing_state === 'deleted') break
            if (Date.now() > deadline0) throw new Fail(`文档 120s 未删除（state=${d2.processing_state}）`)
            await sleep(3000)
          }
          const after0 = await request(`/admin/documents/${encodeURIComponent(id)}/text`, { token })
          assert([404, 410].includes(after0.status), `删除后文本预览期望 404/410，实际 ${after0.status}`)
          return `文档 ${id} 已在删除流程并完成（state=deleted），text HTTP ${after0.status}`
        }
        throw new Skip('批次内已无文档（可能已被清理）')
      }
    }
    assert(docId, '无可用文档（上游失败）')
    const del = await request(`/admin/documents/${encodeURIComponent(docId)}`, {
      method: 'DELETE',
      token,
      query: { expected_version: docVersion },
    })
    assert(del.status === 202, `删除期望 202，实际 ${del.status}（${del.error?.code ?? '-'}，${rid(del)}）`)
    assert(del.data?.document_id === docId, 'document_id 不一致')
    const deadline = Date.now() + 120_000
    let state = null
    for (;;) {
      const list = await request('/admin/documents', { token, query: { page: 1, page_size: 100 } })
      const doc = (list.data?.items ?? []).find((d) => d.id === docId)
      state = doc?.processing_state ?? 'deleted'
      if (state === 'deleted' || !doc) break
      if (Date.now() > deadline) throw new Fail(`文档 120s 未删除（state=${state}）`)
      await sleep(3000)
    }
    assert(state === 'deleted' || state === null, `删除未完成：state=${state}`)
    const after = await request(`/admin/documents/${encodeURIComponent(docId)}/text`, { token })
    assert([404, 410].includes(after.status), `删除后文本预览期望 404/410，实际 ${after.status}`)
    return `删除完成（state=${state}），删除后 text HTTP ${after.status}（${after.error?.code ?? '-'}），${rid(del)}`
  })

  printTable()
}

function printTable() {
  console.log('\n================ F7 文档链路结果 ================')
  for (const [i, r] of rows.entries()) console.log(`${i + 1} | ${r.kind} | ${r.name} | ${r.endpoint} | ${r.detail}`)
  const pass = rows.filter((r) => r.kind === 'PASS').length
  const fail = rows.filter((r) => r.kind === 'FAIL').length
  const skip = rows.filter((r) => r.kind === 'SKIP').length
  const need = rows.filter((r) => r.kind === 'NEED_WORKER').length
  console.log(`\n合计：${rows.length} 步 = PASS ${pass} / FAIL ${fail} / SKIP ${skip} / NEED_WORKER ${need}`)
  if (fail > 0) process.exitCode = 1
  else if (need > 0) process.exitCode = 2
}

main().catch((e) => {
  console.error(`FATAL ${e?.stack ?? e?.message ?? e}`)
  process.exitCode = 1
})
