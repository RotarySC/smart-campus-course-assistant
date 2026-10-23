/**
 * I/O 驱动层：取流 + 派发。**解析与状态转换都不在这里**（它们分别是
 * `api/sse/parse.ts` 与 `domain/chatMachine.ts`，都可纯函数单测）。
 *
 * 本文件只负责 §5 的四件事：
 *   - `POST` + `fetch` reader（**不用 EventSource**：它不能设 Authorization 头、只能 GET、且会自带重连）；
 *   - 建立流之前的错误用 JSON 信封 + HTTP 状态；建立之后的错误只在流内（SRS IF-010，**流内没有 HTTP 状态**）；
 *   - 三个超时（首字节 10s / 无事件间隔 30s / 整轮不设本地上限）；
 *   - **HTTP 关闭 ≠ 终态**：流正常结束而没有 done/error ⇒ `unknown`，不是 `failed`。
 */

import { PROTOCOL_ISSUE_BUDGET, TIMEOUTS } from '@/domain/constants'
import type { ProtocolIssue } from '@/domain/constants'
import { createTurn, reduce, toTerminal } from '@/domain/chatMachine'
import type { TerminalKind } from '@/domain/chatMachine'
import { accept } from '@/domain/dedupe'
import type { SseEvent } from '@/domain/sseTypes'
import { protocolError, httpError } from '../errors'
import { buildUrl, type AuthSnapshot } from '../client'
import { send } from '../transport'
import { createSseParser } from './parse'

export interface ChatStreamRequest {
  client_request_id: string
  conversation_id?: string
  message: string
  history?: Array<{ role: 'user' | 'assistant'; content: string }>
}

export interface StreamHandlers {
  onEvent(e: SseEvent): void
  onTerminal(t: TerminalKind): void
  onProtocolIssue(issue: ProtocolIssue): void
}

export interface StreamResult {
  requestId: string
  terminal: TerminalKind
  /** 已按 seq 去重后的完整序列（用于调试与埋点）。 */
  events: SseEvent[]
}

export async function startChatStream(
  body: ChatStreamRequest,
  h: StreamHandlers,
  signal: AbortSignal,
  auth?: AuthSnapshot,
): Promise<StreamResult> {
  const headers = new Headers({
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  })
  if (auth?.accessToken) headers.set('Authorization', `${auth.tokenType ?? 'Bearer'} ${auth.accessToken}`)

  // 首字节超时 10s。
  const firstByte = new AbortController()
  const firstTimer = setTimeout(
    () => firstByte.abort(new DOMException('first-byte-timeout', 'TimeoutError')),
    TIMEOUTS.streamFirstByte,
  )
  const onOuterAbort = () => firstByte.abort(signal.reason)
  signal.addEventListener('abort', onOuterAbort, { once: true })

  let res: Response
  try {
    res = await send(buildUrl('/chat/stream'), {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: firstByte.signal,
    })
  } catch (e) {
    clearTimeout(firstTimer)
    signal.removeEventListener('abort', onOuterAbort)
    if (signal.aborted) {
      h.onTerminal('cancelled')
      return { requestId: '', terminal: 'cancelled', events: [] }
    }
    throw e
  }
  clearTimeout(firstTimer)

  // 建立流之前的错误：非 2xx + JSON 错误信封 → 交给 client 的错误语义（由调用方归一化）。
  if (!res.ok) {
    signal.removeEventListener('abort', onOuterAbort)
    let payload: unknown = null
    try {
      payload = await res.json()
    } catch {
      payload = null
    }
    throw httpError(res.status, payload)
  }

  const contentType = (res.headers.get('content-type') ?? '').toLowerCase()
  if (!contentType.includes('text/event-stream')) {
    signal.removeEventListener('abort', onOuterAbort)
    throw protocolError(`2xx 但 Content-Type 不是 text/event-stream（实际：${contentType || '空'}）`)
  }

  const reader = res.body?.getReader()
  if (!reader) {
    signal.removeEventListener('abort', onOuterAbort)
    throw protocolError('响应没有 body（无法 getReader）')
  }

  const parser = createSseParser()
  const events: SseEvent[] = []
  const seen = new Set<string>()
  let lastSeq = 0
  let machine = createTurn(body.client_request_id)
  let issueCount = 0
  let parserIssueCursor = 0
  let stopped = false

  const bumpIssue = (): boolean => {
    issueCount++
    return issueCount >= PROTOCOL_ISSUE_BUDGET
  }
  const noteParserIssues = (): boolean => {
    const all = parser.issues()
    let hit = false
    for (; parserIssueCursor < all.length; parserIssueCursor++) {
      const issue = all[parserIssueCursor]
      if (issue === undefined) continue
      h.onProtocolIssue(issue)
      if (bumpIssue()) hit = true
    }
    return hit
  }

  // 无事件间隔超时 30s —— **不等于失败**（§5.8），按 §5.9 核实。
  let idleTimer: ReturnType<typeof setTimeout> | null = null
  const bumpIdle = () => {
    if (idleTimer) clearTimeout(idleTimer)
    idleTimer = setTimeout(() => {
      stopped = true
      void reader.cancel().catch(() => undefined)
    }, TIMEOUTS.streamIdleGap)
  }

  try {
    bumpIdle()
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      if (!value || value.byteLength === 0) continue
      bumpIdle()

      const parsed = parser.push(value)
      if (noteParserIssues()) {
        stopped = true
        break
      }
      for (const e of parsed) {
        if (accept(seen, lastSeq, e) !== 'accept') continue
        lastSeq = e.data.seq
        events.push(e)
        h.onEvent(e)
        const out = reduce(machine, e)
        machine = out.turn
        for (const eff of out.effects) {
          if (eff.kind === 'protocol-issue') {
            h.onProtocolIssue(eff.issue)
            if (bumpIssue()) stopped = true
          }
        }
        if (stopped || machine.terminal !== null) break
      }
      if (stopped || machine.terminal !== null) break
    }
  } catch (e) {
    // 读流中断（网络掉线/超时 abort）：**不是失败**，落 unknown 由调用方核实（§5.9）。
    if (!signal.aborted) {
      // 明确记录但不抛出：终态由下面统一推导。
      h.onProtocolIssue('truncated-frame')
    }
    void e
  } finally {
    if (idleTimer) clearTimeout(idleTimer)
    signal.removeEventListener('abort', onOuterAbort)
    try {
      await reader.cancel()
    } catch {
      /* 已关闭 */
    }
  }

  const tail = parser.end()
  if (tail.pendingBytes > 0) h.onProtocolIssue('truncated-frame')

  const how: 'stream-ended' | 'aborted' | 'error' = signal.aborted ? 'aborted' : 'stream-ended'
  let terminal = toTerminal(machine, how)

  // 协议违规累计到预算：终止并落 failed（§5.3）。
  if (stopped && machine.terminal === null) terminal = 'failed'

  h.onTerminal(terminal)
  return { requestId: machine.requestId ?? '', terminal, events }
}
