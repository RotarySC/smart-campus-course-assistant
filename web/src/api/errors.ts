/**
 * 错误归一化：把网络/超时/HTTP/协议问题统一成 §3.3 的 `AppError`。
 *
 * 硬规则：
 *   - `message` **只用于诊断**，绝不直接展示（§3.3 末段）；用户可见文案走 `domain/mapError.ts`。
 *   - 禁止把原始 `Error` 对象塞进 store（会把请求头带进 state，违反 §4.2.2 L8）。
 *   - `AppError` 的序列化结果不得含令牌（§6.16 验收点 10）。
 */

import { ASYNC_TASK_CODES, SYNC_ERROR_CODES } from '@/domain/constants'

export type ErrorKind =
  | 'network'
  | 'timeout'
  | 'http'
  | 'protocol'
  | 'stream-protocol'
  | 'stream-unknown'
  | 'aborted'

export interface FieldError {
  field: string
  /** openapi `FieldError.reason`（服务端逐字文本，权威）。 */
  reason: string
}

export interface AppError {
  kind: ErrorKind
  code?: string
  httpStatus?: number
  /** 服务端 `message`：仅用于诊断，**不直接展示给用户**。 */
  message?: string
  requestId?: string
  retryable: boolean
  /** 仅 `VALIDATION_FAILED`。 */
  fieldErrors?: FieldError[]
  /** `openapi` `ErrorDetails` 的已知子字段（409/410 分支要用）。 */
  details?: {
    existing_request_id?: string
    operation_id?: string
    plan_id?: string
    state?: string
    retryable?: boolean
    overlaps?: unknown[]
  }
}

/** 前端允许出现的码集合 = §3.4 的 29 个同步码 ∪ 6 个异步任务码。 */
export const CODES: readonly string[] = [...SYNC_ERROR_CODES, ...ASYNC_TASK_CODES]

const CODE_SET = new Set<string>(CODES)

/** 码是否在允许集合内；不在则说明前端发明了错误码（§15.2 契约断言）。 */
export function isKnownCode(code: string): boolean {
  return CODE_SET.has(code)
}

export function appError(e: AppError): AppError {
  return e
}

export function httpError(httpStatus: number, body: unknown, requestId?: string): AppError {
  const envelope = (body ?? {}) as Record<string, unknown>
  const err = (envelope.error ?? envelope) as Record<string, unknown>
  const code = typeof err.code === 'string' ? err.code : undefined
  const message = typeof err.message === 'string' ? err.message : undefined
  const details = (err.details ?? undefined) as AppError['details']
  const rawFields = Array.isArray(err.field_errors) ? (err.field_errors as unknown[]) : []
  const fieldErrors: FieldError[] = rawFields
    .map((f) => {
      const o = f as Record<string, unknown>
      const field = typeof o.field === 'string' ? o.field : ''
      const reason = typeof o.reason === 'string' ? o.reason : typeof o.message === 'string' ? o.message : ''
      return { field, reason }
    })
    .filter((f) => f.field !== '')

  const out: AppError = {
    kind: 'http',
    httpStatus,
    retryable: httpStatus >= 500,
  }
  if (code !== undefined) out.code = code
  if (message !== undefined) out.message = message
  const rid = typeof envelope.request_id === 'string' ? envelope.request_id : requestId
  if (rid !== undefined) out.requestId = rid
  if (details !== undefined) out.details = details
  if (fieldErrors.length > 0) out.fieldErrors = fieldErrors
  if (details?.retryable !== undefined) out.retryable = details.retryable
  return out
}

export function networkError(cause?: unknown): AppError {
  return { kind: 'network', retryable: true, message: describe(cause) }
}

export function timeoutError(): AppError {
  return { kind: 'timeout', retryable: true }
}

export function abortedError(): AppError {
  return { kind: 'aborted', retryable: false }
}

export function protocolError(message: string, requestId?: string): AppError {
  const e: AppError = { kind: 'protocol', retryable: false, message }
  if (requestId !== undefined) e.requestId = requestId
  return e
}

export function streamProtocolError(message: string, requestId?: string): AppError {
  const e: AppError = { kind: 'stream-protocol', retryable: false, message }
  if (requestId !== undefined) e.requestId = requestId
  return e
}

/** HTTP 关闭但无终态：**不是失败**（§5.9）。 */
export function streamUnknownError(requestId?: string): AppError {
  const e: AppError = { kind: 'stream-unknown', retryable: true }
  if (requestId !== undefined) e.requestId = requestId
  return e
}

/**
 * 安全序列化：`AppError` 里可能带服务端 `message`，但**绝不**含请求头/令牌。
 * 供埋点与日志使用（§13.5 红线）。
 */
export function serializeAppError(e: AppError): Record<string, unknown> {
  return {
    kind: e.kind,
    code: e.code ?? null,
    httpStatus: e.httpStatus ?? null,
    requestId: e.requestId ?? null,
    retryable: e.retryable,
    fields: e.fieldErrors?.map((f) => f.field) ?? null,
  }
}

function describe(cause: unknown): string {
  if (cause instanceof Error) return cause.name
  return typeof cause === 'string' ? cause : 'unknown'
}
