/**
 * 请求层。职责与顺序严格照 §3.2 的 6 步。
 *
 * 硬约束：
 *   - **不 import store**（§2.2 R2）：令牌以 `auth` 参数注入。
 *   - `path` 必须是 `API-REFERENCE.md` 里的 26 个 `/api/v1/*` 之一；
 *     不得出现任何 `/internal/v1/*`（§15.2 契约断言）。
 *   - 幂等头只允许出现在 4 个端点（§6.3）；用错即开发期报错，不静默降级。
 *   - 只记 method/path/status/request_id/耗时；**不记请求体与响应体正文**（NFR-PRIV-001）。
 */

import { IDEMPOTENT_ENDPOINTS } from '@/domain/constants'
import type { Envelope } from './types'
import { abortedError, httpError, networkError, protocolError, timeoutError } from './errors'
import type { AppError } from './errors'
import { send } from './transport'

/** §2.3 的接口形状；`auth` 是唯一令牌入口。 */
export interface AuthSnapshot {
  accessToken: string | null
  tokenType: 'Bearer' | null
}

export interface RequestOptions {
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  path: string
  query?: Record<string, string | number | boolean | undefined>
  body?: unknown
  idempotencyKey?: string
  signal?: AbortSignal
  timeoutMs?: number
  auth?: AuthSnapshot
}

/** `API-REFERENCE.md` 的 26 个 `/api/v1/*`（逐字，前端唯一可用集合）。 */
export const API_PATHS = [
  '/auth/login',
  '/auth/logout',
  '/me',
  '/me/schedules',
  '/me/plans',
  '/me/plans/{id}',
  '/me/drafts/{draft_id}',
  '/me/drafts/{draft_id}/save',
  '/me/write-operations/{operation_id}',
  '/chat/stream',
  '/chat/requests/{request_id}',
  '/chat/requests/{request_id}/cancel',
  '/citations/{reference_id}',
  '/admin/courses',
  '/admin/courses/{id}',
  '/admin/students',
  '/admin/students/{id}',
  '/admin/schedules',
  '/admin/schedules/{id}',
  '/admin/documents',
  '/admin/documents/{id}',
  '/admin/documents/{id}/text',
  '/admin/documents/{id}/rebuild',
  '/admin/documents/{id}/cleanup-retry',
  '/admin/document-batches',
  '/admin/document-batches/{id}',
] as const

export const DEFAULT_TIMEOUT_MS = 15_000

/** 请求层记录的埋点行；只含 §3.2 第 6 步允许的字段。 */
export interface RequestTrace {
  method: string
  path: string
  status: number | null
  requestId: string | null
  durationMs: number
  errorKind?: string
}

export type TraceSink = (t: RequestTrace) => void
let traceSink: TraceSink | null = null
export function setTraceSink(fn: TraceSink | null): void {
  traceSink = fn
}

export function apiBase(): string {
  const b = import.meta.env.VITE_API_BASE
  return typeof b === 'string' && b.length > 0 ? b : '/api/v1'
}

export function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = `${apiBase()}${path}`
  if (!query) return url
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined) continue
    sp.set(k, String(v))
  }
  const qs = sp.toString()
  return qs ? `${url}?${qs}` : url
}

function isIdempotentEndpoint(method: string, path: string): boolean {
  // 与常量表逐字比对；`{id}` / `{draft_id}` 用占位符形态匹配。
  const key = `${method} ${path}`
  if ((IDEMPOTENT_ENDPOINTS as readonly string[]).includes(key)) return true
  return (
    (method === 'POST' && /^\/admin\/documents\/[^/]+\/rebuild$/.test(path)) ||
    (method === 'POST' && /^\/admin\/documents\/[^/]+\/cleanup-retry$/.test(path)) ||
    (method === 'POST' && /^\/me\/drafts\/[^/]+\/save$/.test(path)) ||
    (method === 'POST' && path === '/me/plans')
  )
}

function authHeaders(auth: AuthSnapshot | undefined, extra?: HeadersInit): Headers {
  const h = new Headers(extra)
  if (auth?.accessToken) h.set('Authorization', `${auth.tokenType ?? 'Bearer'} ${auth.accessToken}`)
  h.set('Accept', 'application/json')
  return h
}

/**
 * 成功返回 `data`；失败抛 `AppError`。所有响应信封的 `request_id` 都会被保留到 `AppError.requestId`。
 */
export async function request<T>(o: RequestOptions): Promise<T> {
  // 步骤 3：幂等头误用是开发期错误，直接抛（不静默忽略）。
  if (o.idempotencyKey !== undefined && !isIdempotentEndpoint(o.method, o.path)) {
    throw protocolError(`端点 ${o.method} ${o.path} 不接受 Idempotency-Key（§6.3 只允许 4 个端点）`)
  }

  // 重试策略：只对幂等读（GET）在网络错误或 5xx 时重试 1 次，退避 300ms。
  const attempts = o.method === 'GET' ? 2 : 1
  let last: AppError | null = null
  for (let i = 0; i < attempts; i++) {
    try {
      return await once<T>(o)
    } catch (e) {
      const err = e as AppError
      last = err
      const retryable = err.kind === 'network' || (err.kind === 'http' && (err.httpStatus ?? 0) >= 500)
      if (i === attempts - 1 || !retryable) throw err
      await delay(300)
    }
  }
  throw last ?? networkError()
}

async function once<T>(o: RequestOptions): Promise<T> {
  const url = buildUrl(o.path, o.query)
  const headers = authHeaders(o.auth, o.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' })
  if (o.idempotencyKey !== undefined) headers.set('Idempotency-Key', o.idempotencyKey)

  const ctrl = new AbortController()
  const timeoutMs = o.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const timer = setTimeout(() => ctrl.abort(new DOMException('timeout', 'TimeoutError')), timeoutMs)
  const onOuterAbort = () => ctrl.abort(o.signal?.reason)
  o.signal?.addEventListener('abort', onOuterAbort, { once: true })

  const started = Date.now()
  let status: number | null = null
  try {
    const res = await send(url, {
      method: o.method,
      headers,
      body: o.body === undefined ? undefined : o.body instanceof FormData ? o.body : JSON.stringify(o.body),
      signal: ctrl.signal,
    })
    status = res.status

    let payload: unknown = null
    try {
      payload = await res.json()
    } catch {
      payload = null
    }

    const requestId = readRequestId(payload)

    if (!res.ok) {
      throw httpError(res.status, payload, requestId ?? undefined)
    }

    // 步骤 5：2xx 必须符合 { request_id, data } 信封，否则是协议错误。
    const envelope = payload as Envelope<T> | null
    if (!envelope || typeof envelope !== 'object' || typeof envelope.request_id !== 'string' || !('data' in envelope)) {
      throw protocolError('响应缺少 { request_id, data } 信封（NFR-OBS-001）')
    }
    trace(o, status, envelope.request_id, started, undefined)
    return envelope.data
  } catch (e) {
    if (e && typeof e === 'object' && 'kind' in (e as AppError)) {
      const ae = e as AppError
      trace(o, status, ae.requestId ?? null, started, ae.kind)
      throw ae
    }
    if (isAbort(e)) {
      const aborted = o.signal?.aborted ? abortedError() : timeoutError()
      trace(o, status, null, started, aborted.kind)
      throw aborted
    }
    const ne = networkError(e)
    trace(o, status, null, started, ne.kind)
    throw ne
  } finally {
    clearTimeout(timer)
    o.signal?.removeEventListener('abort', onOuterAbort)
  }
}

function readRequestId(payload: unknown): string | null {
  if (payload && typeof payload === 'object' && typeof (payload as Envelope<unknown>).request_id === 'string') {
    return (payload as Envelope<unknown>).request_id
  }
  return null
}

function trace(o: RequestOptions, status: number | null, requestId: string | null, started: number, errorKind?: string): void {
  if (!traceSink) return
  const row: RequestTrace = {
    method: o.method,
    path: o.path,
    status,
    requestId,
    durationMs: Date.now() - started,
  }
  if (errorKind !== undefined) row.errorKind = errorKind
  traceSink(row)
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException && (e.name === 'AbortError' || e.name === 'TimeoutError')
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}
