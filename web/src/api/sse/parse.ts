/**
 * 字节流 → SSE 事件。**输入是字节，不是文本**（§5.3）。
 *
 * 为什么必须是字节：中文与 emoji 会被切在分片边界上，所以「字节→文本」这一段
 * 必须用 `TextDecoder` 的流式模式，而不是自己按字节拼字符串。
 *
 * 12 条解析规则（P1–P12）逐条对应 §5.3 的表，每条都有回归用例
 * （在 `scripts/smoke-sse.mjs` 的 24 项纯函数冒烟里；全量单测待补齐）：
 *   P1 行分隔符 CRLF / LF / CR 三者之一 —— 只按 \n 切会把 CRLF 留出多余空行产生幽灵 dispatch
 *   P2 `:` 开头是注释（keep-alive），忽略
 *   P3 `field: value`，冒号后**只吃一个**空格（吃多了会破坏 text_delta 的前导空格）
 *   P4 无冒号的行：整行是字段名、值为空串
 *   P5 多个 `data:` 行用 `\n` 连接成一个 payload
 *   P6 空行 dispatch；data 缓冲为空则**不派发**（但 id 更新仍生效）
 *   P7 `event:` 决定事件名，缺省 `message`；非 6 个白名单名字记协议违规
 *   P8 `id:` 更新 lastEventId；含 `\0` 时忽略；与 data.seq 不一致记 id-seq-mismatch，以 data.seq 为准
 *   P9 `retry:` 被容忍但**不使用**（不重连）
 *   P10 结束：flush decoder；残留非空 → truncated-frame
 *   P11 首个分片可能带 UTF-8 BOM，必须剥离
 *   P12 单事件 payload 与总缓冲上限，超限即记协议违规
 */

import { PROTOCOL_ISSUES, SSE_EVENT_NAMES, SSE_FRAME_LIMIT_BYTES } from '@/domain/constants'
import type { ProtocolIssue, SseEventName } from '@/domain/constants'
import type { ParserTail, SseEvent, SseParser } from '@/domain/sseTypes'

const EVENT_NAME_SET = new Set<string>(SSE_EVENT_NAMES)

function stripBom(s: string): string {
  return s.charCodeAt(0) === 0xfeff ? s.slice(1) : s
}

function byteLen(s: string): number {
  return new TextEncoder().encode(s).length
}

export function createSseParser(): SseParser {
  // fatal:false —— 非法字节由 U+FFFD 表示，不抛错、不中断整轮。
  const dec = new TextDecoder('utf-8', { fatal: false })
  let buf = ''
  let dataLines: string[] = []
  let eventName = ''
  let lastId = ''
  let sawBom = false
  let overLimit = false
  const issues: ProtocolIssue[] = []

  function note(issue: ProtocolIssue): void {
    if (PROTOCOL_ISSUES.includes(issue)) issues.push(issue)
  }

  function resetEvent(): void {
    dataLines = []
    eventName = ''
    overLimit = false
  }

  function dispatch(out: SseEvent[]): void {
    const name = eventName || 'message'
    const payload = dataLines.join('\n') // P5
    const id = lastId
    resetEvent() // P6：无论是否派发，缓冲都要清

    if (payload.length === 0) return // P6：data 为空不派发（避免状态机收到垃圾）

    if (!EVENT_NAME_SET.has(name)) {
      // P7：非 6 个白名单事件名 → 记协议违规并丢弃该事件。
      note('unknown-event')
      return
    }

    let data: unknown
    try {
      data = JSON.parse(payload)
    } catch {
      // 一个坏帧不得让用户丢失整段回答：只丢该事件。
      note('bad-event-json')
      return
    }

    if (!data || typeof data !== 'object') {
      note('bad-event-json')
      return
    }

    const seq = (data as { seq?: unknown }).seq
    if (typeof seq !== 'number' || !Number.isInteger(seq) || seq < 1) {
      note('bad-event-json')
      return
    }

    // P8：`id` 与 `data.seq` 必须一致；不一致不抛错，以 data.seq 为准。
    if (id !== '' && id !== String(seq)) note('id-seq-mismatch')

    out.push({ id: id === '' ? String(seq) : id, event: name as SseEventName, data: data as SseEvent['data'] } as SseEvent)
  }

  function handleLine(line: string, out: SseEvent[]): void {
    if (line === '') {
      dispatch(out) // P6
      return
    }
    if (line.charCodeAt(0) === 0x3a) return // P2：`:` 注释

    const colon = line.indexOf(':')
    let field: string
    let value: string
    if (colon === -1) {
      field = line // P4
      value = ''
    } else {
      field = line.slice(0, colon)
      const rest = line.slice(colon + 1)
      value = rest.charCodeAt(0) === 0x20 ? rest.slice(1) : rest // P3：只吃一个空格
    }

    switch (field) {
      case 'event':
        eventName = value // P7
        break
      case 'data':
        dataLines.push(value) // P5
        if (dataLines.join('\n').length > SSE_FRAME_LIMIT_BYTES && !overLimit) {
          overLimit = true
          note('buffer-limit-exceeded')
        }
        break
      case 'id':
        if (!value.includes('\0')) lastId = value // P8
        break
      case 'retry':
        // P9：容忍但**不使用**（不启用重连）。
        break
      default:
        break
    }
  }

  /** 把已完成的行全部取出；`atEnd` 时不再等待可能到来的 CRLF 后半。 */
  function drain(atEnd: boolean, out: SseEvent[]): void {
    for (;;) {
      const cr = buf.indexOf('\r')
      const lf = buf.indexOf('\n')
      if (cr === -1 && lf === -1) break

      let pos: number
      let len: number
      if (cr !== -1 && (lf === -1 || cr < lf)) {
        // CR 先到；可能是 CRLF，也可能是单 CR 终止。
        if (cr === buf.length - 1 && !atEnd) break // 等下一片来判断是不是 CRLF
        const isCrlf = buf.charCodeAt(cr + 1) === 0x0a
        pos = cr
        len = isCrlf ? 2 : 1
      } else {
        pos = lf
        len = 1
      }
      const line = buf.slice(0, pos)
      buf = buf.slice(pos + len)
      handleLine(line, out)
      if (overLimit) resetEvent()
    }
  }

  return {
    push(chunk: Uint8Array): SseEvent[] {
      const out: SseEvent[] = []
      // 关键：stream:true 保留半个码点。
      let text = dec.decode(chunk, { stream: true })
      if (!sawBom) {
        text = stripBom(text) // P11
        sawBom = true
      }
      buf += text
      if (byteLen(buf) > SSE_FRAME_LIMIT_BYTES) {
        note('buffer-limit-exceeded')
        buf = ''
        resetEvent()
      }
      drain(false, out)
      return out
    },

    end(): ParserTail {
      const out: SseEvent[] = []
      // P10：flush decoder，否则最后一帧会丢。
      const tail = dec.decode()
      buf += tail
      drain(true, out)
      const pending = buf
      if (pending.trim().length > 0) note('truncated-frame')
      return { pendingBytes: byteLen(pending), pendingEvent: pending }
    },

    issues(): ProtocolIssue[] {
      return [...issues]
    },
  }
}
