/**
 * SSE 事件的类型契约。真源：`contracts/sse_events_v0.1.schema.json`。
 *
 * 放在 `domain/` 而不是 `api/`，是为了满足 §2.2 R1：
 * `domain/**` 不得 import `stores/**`、`api/**`。`api/sse/parse.ts` 反向 import 本文件的类型，
 * 依赖方向单向（api → domain），不成环。
 */

import type { ProtocolIssue, SseEventName, ToolName, ToolResultStatus } from './constants'

export interface Reference {
  reference_id: string
  document_id: string
  version_id: string
  file_name: string
  location_label: string
  page_number?: number
}

interface SseBase {
  request_id: string
  seq: number
  timestamp: string
}

export interface StatusEventData extends SseBase {
  code: string
  message: string
  conversation_id?: string
  draft_id?: string
  draft_version?: number
}

export interface ToolStartEventData extends SseBase {
  tool_call_id: string
  tool_name: ToolName
  display_name: string
}

export interface ToolEndEventData extends SseBase {
  tool_call_id: string
  success: boolean
  result_status: ToolResultStatus
  code?: string
  plan_id?: string
  operation_id?: string
  /** 仅 `search_course_docs` 成功时出现；true = 全库尚无已发布资料（S05 第 3 态）。 */
  corpus_empty?: boolean
}

export interface TokenEventData extends SseBase {
  text_delta: string
  answer_block_id: string
}

export interface DoneEventData extends SseBase {
  state: 'succeeded' | 'cancelled'
  reason?: string
  citations: Reference[]
  plan_id?: string
  operation_id?: string
}

export interface ErrorEventData extends SseBase {
  state: 'failed'
  code: string
  message: string
}

export interface SseEventMap {
  status: StatusEventData
  tool_start: ToolStartEventData
  tool_end: ToolEndEventData
  token: TokenEventData
  done: DoneEventData
  error: ErrorEventData
}

export type SseEvent = {
  [K in SseEventName]: {
    /** SSE 的 `id:` 字段；schema 要求与 data.seq 一致。 */
    id: string
    event: K
    data: SseEventMap[K]
  }
}[SseEventName]

/** §5.3 `end()` 的诊断信息：不产生事件。 */
export interface ParserTail {
  pendingBytes: number
  pendingEvent: string
}

export interface SseParser {
  /** 喂入一个 Uint8Array 分片（可能是半个多字节字符、半个事件）。 */
  push(chunk: Uint8Array): SseEvent[]
  /** 流结束：flush decoder 并返回残留缓冲诊断。 */
  end(): ParserTail
  /** 解析过程中累计的协议违规（§5.3）。 */
  issues(): ProtocolIssue[]
}
