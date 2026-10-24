/**
 * mock 的 SSE 流构造器。
 *
 * **关键设计**：它产出的是**真正的 `ReadableStream<Uint8Array>`**，
 * 并且**故意按 7 字节切片**——中文与 U+2013 等字符是多字节，7 字节切片必然把码点切在中间。
 * 于是 `api/sse/parse.ts` 的 `TextDecoder({stream:true})`、CRLF/LF 行切分、
 * 多行 `data:` 拼接、`id`/`seq` 互校这些逻辑**在冒烟里就被真实跑到了**，
 * 而不是靠一个「直接给 JS 对象」的假流绕过。
 *
 * 事件名与字段严格照 `contracts/sse_events_v0.1.schema.json`。
 */

import type { SseEventName } from '@/domain/constants'
import type { Reference } from '../types'
import { MOCK_TODAY, references } from './db'

export interface MockSseEvent {
  event: SseEventName
  data: Record<string, unknown>
}

/** 每个事件之间的间隔（ms）；同事件内的字节分片不额外延迟。 */
export interface ScriptStep {
  event: MockSseEvent
  delayMs: number
  /** true = 发完这一条就结束流（可能没有终态事件）。 */
  last?: boolean
}

const CITE_ANSWER =
  '根据《数据结构实验指导书（2026 秋）》，下次实验前需要完成：1）预习实验二排序算法；2）提交预习报告，不少于 500 字。'

/**
 * 依用户消息选择一个演示脚本。
 * 触发词是**测试用关键字**（仅存在于 mock，不是用户可见文案）。
 */
export function buildScript(message: string, requestId: string, conversationId: string): ScriptStep[] {
  const mk = (event: SseEventName, data: Record<string, unknown>): MockSseEvent => ({
    event,
    data: { request_id: requestId, timestamp: '2026-10-22T10:05:00+08:00', ...data },
  })
  const steps: ScriptStep[] = []
  let seq = 0
  const push = (e: MockSseEvent, delayMs: number, last = false) => {
    seq += 1
    e.data.seq = seq
    steps.push({ event: e, delayMs, last })
  }

  // ---------- A7：无终态关闭（HTTP 关闭 ≠ 终态）+ 写意图 → 落「待确认」 ----------
  if (message.includes('无终态')) {
    push(mk('status', { code: 'ACCEPTED', message: 'ACCEPTED', conversation_id: conversationId }), 0)
    push(mk('tool_start', { tool_call_id: 'tc_1', tool_name: 'get_my_schedule', display_name: '正在读取课表' }), 200)
    push(mk('tool_end', { tool_call_id: 'tc_1', success: true, result_status: 'ok' }), 200)
    push(
      mk('tool_start', { tool_call_id: 'tc_2', tool_name: 'save_study_plan', display_name: '正在拟定计划草稿' }),
      200,
    )
    push(
      mk('tool_end', {
        tool_call_id: 'tc_2',
        success: true,
        result_status: 'created',
        plan_id: 'plan_7Q2F9K',
        operation_id: 'op_mock_pending_1',
      }),
      200,
      true,
    )
    return steps
  }

  // ---------- A6：双终态 ----------
  if (message.includes('双终态')) {
    push(mk('status', { code: 'ACCEPTED', message: 'ACCEPTED', conversation_id: conversationId }), 0)
    push(mk('token', { text_delta: '先给一个终态，再来一个。', answer_block_id: 'blk_1' }), 120)
    push(mk('done', { state: 'succeeded', citations: [references.ref_lab_001 as Reference] }), 160)
    push(mk('error', { state: 'failed', code: 'INTERNAL_ERROR', message: 'late error' }), 160, true)
    return steps
  }

  // ---------- S05 ②：检索失败（依赖异常） ----------
  if (message.includes('检索失败')) {
    push(mk('status', { code: 'ACCEPTED', message: 'ACCEPTED', conversation_id: conversationId }), 0)
    push(
      mk('tool_start', { tool_call_id: 'tc_1', tool_name: 'search_course_docs', display_name: '正在检索课程资料' }),
      200,
    )
    push(
      mk('tool_end', {
        tool_call_id: 'tc_1',
        success: false,
        result_status: 'failed',
        code: 'RETRIEVAL_UNAVAILABLE',
      }),
      240,
    )
    push(
      mk('error', { state: 'failed', code: 'RETRIEVAL_UNAVAILABLE', message: 'retrieval down' }),
      240,
      true,
    )
    return steps
  }

  // ---------- S05 ①：依据不足（检索成功但无足够依据） ----------
  if (message.includes('依据不足')) {
    push(mk('status', { code: 'ACCEPTED', message: 'ACCEPTED', conversation_id: conversationId }), 0)
    push(
      mk('tool_start', { tool_call_id: 'tc_1', tool_name: 'search_course_docs', display_name: '正在检索课程资料' }),
      200,
    )
    push(mk('tool_end', { tool_call_id: 'tc_1', success: true, result_status: 'empty' }), 220)
    push(mk('done', { state: 'succeeded', citations: [] }), 220, true)
    return steps
  }

  // ---------- 默认：S03 过程反馈 → S04 有据回答 + 引用 → S06 草稿 + 保存成功 ----------
  push(mk('status', { code: 'ACCEPTED', message: 'ACCEPTED', conversation_id: conversationId }), 0)
  push(
    mk('tool_start', {
      tool_call_id: 'tc_1',
      tool_name: 'get_my_schedule',
      display_name: `正在读取课表 · ${MOCK_TODAY}（周四）`,
    }),
    220,
  )
  push(mk('tool_end', { tool_call_id: 'tc_1', success: true, result_status: 'ok' }), 220)
  push(
    mk('tool_start', {
      tool_call_id: 'tc_2',
      tool_name: 'search_course_docs',
      display_name: '正在检索课程资料 · 「实验课 预习要求」',
    }),
    220,
  )
  push(mk('tool_end', { tool_call_id: 'tc_2', success: true, result_status: 'ok' }), 240)

  const answer = [...CITE_ANSWER]
  // 每 6 个码点一片，制造真实的分片与节流场景（§5.10）。
  for (let i = 0; i < answer.length; i += 6) {
    push(mk('token', { text_delta: answer.slice(i, i + 6).join(''), answer_block_id: 'blk_1' }), 70)
  }
  push(mk('token', { text_delta: '〔资料 1〕', answer_block_id: 'blk_1' }), 70)

  // status 携带 draft_id/draft_version → chat store 调 drafts.bind()（§6.8）
  push(
    mk('status', {
      code: 'DRAFT_READY',
      message: 'draft ready',
      conversation_id: conversationId,
      draft_id: 'draft_mock_1',
      draft_version: 1,
    }),
    160,
  )
  push(
    mk('tool_start', {
      tool_call_id: 'tc_3',
      tool_name: 'save_study_plan',
      display_name: '正在拟定计划草稿',
    }),
    160,
  )
  push(
    mk('tool_end', {
      tool_call_id: 'tc_3',
      success: true,
      result_status: 'created',
      plan_id: 'plan_7Q2F9K',
      operation_id: 'op_mock_created_1',
    }),
    240,
  )
  push(
    mk('done', {
      state: 'succeeded',
      citations: [references.ref_lab_001 as Reference],
      plan_id: 'plan_7Q2F9K',
      operation_id: 'op_mock_created_1',
    }),
    240,
    true,
  )
  return steps
}

/** 把一条事件序列化成 SSE 线格式。`id:` 与 `data.seq` 保持一致（schema 要求二者相等）。 */
export function serialize(step: MockSseEvent): string {
  const seq = String(step.data.seq)
  const lines = [`id: ${seq}`, `event: ${step.event}`, `data: ${JSON.stringify(step.data)}`]
  // CRLF：真实服务端常见形态，也用来验证 P1（只按 \n 切会产生幽灵 dispatch）。
  return lines.join('\r\n') + '\r\n\r\n'
}

const encoder = new TextEncoder()

/**
 * 把脚本变成 `Response`。刻意按 7 字节切片 —— 必然把多字节字符切在中间，
 * 从而在冒烟阶段就真实覆盖 `TextDecoder({stream:true})` 的码点边界。
 */
export function createChatResponse(steps: ScriptStep[], signal: AbortSignal | null): Response {
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      const CHUNK = 7
      try {
        for (const step of steps) {
          if (signal?.aborted) break
          if (step.delayMs > 0) await sleep(step.delayMs)
          if (signal?.aborted) break
          const bytes = encoder.encode(serialize(step.event))
          for (let i = 0; i < bytes.byteLength; i += CHUNK) {
            if (signal?.aborted) break
            controller.enqueue(bytes.slice(i, i + CHUNK))
          }
          if (step.last) break
        }
        controller.close()
      } catch {
        try {
          controller.close()
        } catch {
          /* 已关闭 */
        }
      }
    },
    cancel() {
      /* 客户端取消：什么都不做，让上面的循环在下一轮退出 */
    },
  })
  return new Response(body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  })
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}
