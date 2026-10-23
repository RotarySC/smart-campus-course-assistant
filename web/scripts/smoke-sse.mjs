#!/usr/bin/env node
/**
 * 流式链路冒烟（§15.3 A 类用例的**可执行**版本）。
 *
 * 直接 import 项目的 **真实模块**（不是复刻实现）：
 *   api/mock/sse.ts（脚本 + 真 ReadableStream，7 字节切片）
 *   api/sse/parse.ts（字节级增量解析，P1–P12）
 *   domain/chatMachine.ts（状态机 / 终态唯一 / HTTP 关闭 ≠ 终态）
 *   domain/dedupe.ts · validate.ts · format.ts · mapError.ts · constants.ts
 *
 * 为什么不用 Vitest：用户明确要求**开发期只做冒烟**，收尾才铺全量套件。
 * 本脚本不引入任何测试框架，靠 `node:assert` + 手写断言，零依赖、秒级。
 *
 * 运行： node --import ./scripts/ts-alias-hook.mjs scripts/smoke-sse.mjs
 */

import assert from 'node:assert/strict'
import { createSseParser } from '../src/api/sse/parse.ts'
import { buildScript, createChatResponse } from '../src/api/mock/sse.ts'
import { createTurn, reduce, toTerminal, closeTransport, hasWriteIntent } from '../src/domain/chatMachine.ts'
import { accept } from '../src/domain/dedupe.ts'
import { validatePlanForm, validateScheduleForm, canSubmitMessage, isValidIdempotencyKey } from '../src/domain/validate.ts'
import { formatBytes, formatDateWithWeekday, codePointLength } from '../src/domain/format.ts'
import { mapErrorText, isAuthFailureCode } from '../src/domain/mapError.ts'
import { SSE_EVENT_NAMES, TOOL_NAMES } from '../src/domain/constants.ts'

let passed = 0
const rows = []
function check(name, fn) {
  try {
    fn()
    passed++
    rows.push(`PASS  ${name}`)
  } catch (e) {
    rows.push(`FAIL  ${name}\n        ${e.message}`)
    process.exitCode = 1
  }
}

const enc = new TextEncoder()

/** 把事件序列化成 SSE 线格式（与 mock 侧一致的 CRLF 形态）。 */
function sse(id, event, data) {
  return `id: ${id}\r\nevent: ${event}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`
}

function feed(text, chunkSize) {
  const parser = createSseParser()
  const bytes = enc.encode(text)
  const out = []
  for (let i = 0; i < bytes.length; i += chunkSize) out.push(...parser.push(bytes.slice(i, i + chunkSize)))
  parser.end()
  return { events: out, issues: parser.issues() }
}

/* ================= A1/A2：分包边界与 UTF-8 截断 ================= */
const sampleEvent = sse(1, 'token', {
  request_id: 'req_1',
  seq: 1,
  timestamp: '2026-10-22T10:05:00+08:00',
  text_delta: '下节课要带《数据结构》讲义 🎒',
  answer_block_id: 'blk_1',
})

check('A1/A2 按 1/3/7/64 字节切分：事件数、内容、UTF-8 均不变，且不出现 U+FFFD', () => {
  for (const size of [1, 3, 7, 64]) {
    const { events } = feed(sampleEvent, size)
    assert.equal(events.length, 1, `chunkSize=${size} 事件数应为 1`)
    assert.equal(events[0].data.text_delta, '下节课要带《数据结构》讲义 🎒', `chunkSize=${size} 内容被破坏`)
    assert.ok(!events[0].data.text_delta.includes('\uFFFD'), `chunkSize=${size} 出现替换字符`)
  }
})

/* ================= A3：多行 data ================= */
check('A3 多个 data: 行按 \\n 连接（不是覆盖）', () => {
  const text =
    'id: 1\r\nevent: token\r\ndata: {"request_id":"r","seq":1,"timestamp":"t","answer_block_id":"b",\r\ndata: "text_delta":"分两行"}\r\n\r\n'
  const { events } = feed(text, 5)
  assert.equal(events.length, 1)
  assert.equal(events[0].data.text_delta, '分两行')
})

/* ================= A4/A5：seq 去重与回退 ================= */
check('A4/A5 重复 seq 与回退 seq 都被拒绝（且不得用覆盖代替去重）', () => {
  const seen = new Set()
  let lastSeq = 0
  const ev = (seq) => ({ data: { request_id: 'r', seq } })
  assert.equal(accept(seen, lastSeq, ev(1)), 'accept')
  lastSeq = 1
  assert.equal(accept(seen, lastSeq, ev(1)), 'duplicate')
  assert.equal(accept(seen, lastSeq, ev(2)), 'accept')
  lastSeq = 2
  assert.equal(accept(seen, lastSeq, ev(2)), 'duplicate', '重复 seq 必须是 duplicate')
  assert.equal(accept(new Set(['r:5']), 5, ev(3)), 'out-of-order', '回退 seq 必须是 out-of-order')
})

/* ================= A6：双终态 ================= */
check('A6 done 之后再来 error：终态仍是 succeeded，且记 double-terminal 违规', () => {
  const turn = createTurn('crid_1')
  const mk = (id, event, data) => ({ id: String(id), event, data })
  let t = reduce(turn, mk(1, 'done', { request_id: 'r', seq: 1, timestamp: 't', state: 'succeeded', citations: [] })).turn
  assert.equal(t.terminal, 'succeeded')
  t = reduce(t, mk(2, 'error', { request_id: 'r', seq: 2, timestamp: 't', state: 'failed', code: 'INTERNAL_ERROR', message: 'late' })).turn
  assert.equal(t.terminal, 'succeeded', '第二个终态不得覆盖第一个')
  assert.deepEqual(t.issues, ['double-terminal'])
})

/* ================= A7：无终态关闭（HTTP 关闭 ≠ 终态） ================= */
check('A7 流关闭而无终态 ⇒ unknown（不是 failed）；有写意图时进入核实路径', async () => {
  const turn = createTurn('crid_2')
  let t = reduce(turn, {
    id: '1',
    event: 'tool_start',
    data: { request_id: 'r', seq: 1, timestamp: 't', tool_call_id: 'tc1', tool_name: 'save_study_plan', display_name: '正在拟定计划草稿' },
  }).turn
  t = reduce(t, {
    id: '2',
    event: 'tool_end',
    data: { request_id: 'r', seq: 2, timestamp: 't', tool_call_id: 'tc1', success: true, result_status: 'created', operation_id: 'op_1' },
  }).turn
  assert.equal(t.terminal, null)
  assert.ok(hasWriteIntent(t), '应识别出写意图')
  const closed = closeTransport(t).turn
  assert.equal(closed.terminal, 'unknown', 'HTTP 关闭 ≠ 终态')
  assert.equal(closed.transportClosed, true)
  assert.equal(toTerminal(t, 'stream-ended'), 'unknown')
  assert.equal(toTerminal(t, 'aborted'), 'cancelled')
})

/* ================= A8：取消竞态（服务端终态优先） ================= */
check('A8 取消后收到 done：以服务端终态为准，不重复取消', () => {
  const t0 = createTurn('crid_3')
  const cancelled = reduce(t0, { id: '1', event: 'status', data: { request_id: 'r', seq: 1, timestamp: 't', code: 'ACCEPTED', message: 'ok', conversation_id: 'conv_1' } }).turn
  const afterDone = reduce(cancelled, { id: '2', event: 'done', data: { request_id: 'r', seq: 2, timestamp: 't', state: 'succeeded', citations: [] } }).turn
  assert.equal(toTerminal(afterDone, 'aborted'), 'succeeded', '已有服务端终态时 aborted 不得改写为 cancelled')
})

/* ================= A9/A10：tool_end 配对与失败码 ================= */
check('A9 孤立 tool_end：忽略 + 记 unpaired-tool，不渲染步骤', () => {
  const t = reduce(createTurn('crid_4'), {
    id: '1',
    event: 'tool_end',
    data: { request_id: 'r', seq: 1, timestamp: 't', tool_call_id: 'nope', success: true, result_status: 'ok' },
  }).turn
  assert.equal(t.steps.length, 0, '不得渲染孤立步骤')
  assert.ok(t.issues.includes('unpaired-tool'))
})

check('A10 success=false 且缺 code：仍按 failed 渲染', () => {
  let t = reduce(createTurn('crid_5'), {
    id: '1',
    event: 'tool_start',
    data: { request_id: 'r', seq: 1, timestamp: 't', tool_call_id: 'tc1', tool_name: 'get_my_schedule', display_name: '正在读取课表' },
  }).turn
  t = reduce(t, {
    id: '2',
    event: 'tool_end',
    data: { request_id: 'r', seq: 2, timestamp: 't', tool_call_id: 'tc1', success: false, result_status: 'failed' },
  }).turn
  assert.equal(t.steps[0].status, 'failed')
})

/* ================= A11：ACCEPTED 缺 conversation_id ================= */
check('A11 status.code=ACCEPTED 缺 conversation_id ⇒ 记违规并进 unknown', () => {
  const t = reduce(createTurn('crid_6'), {
    id: '1',
    event: 'status',
    data: { request_id: 'r', seq: 1, timestamp: 't', code: 'ACCEPTED', message: 'ok' },
  }).turn
  assert.ok(t.issues.includes('missing-conversation-id'))
  assert.equal(t.terminal, 'unknown')
})

/* ================= A12/A13：未知事件名与心跳注释 ================= */
check('A12 未知 event 名：丢弃该事件并记 unknown-event', () => {
  const { events, issues } = feed('id: 1\r\nevent: ping\r\ndata: {"request_id":"r","seq":1,"timestamp":"t"}\r\n\r\n', 7)
  assert.equal(events.length, 0)
  assert.deepEqual(issues, ['unknown-event'])
})

check('A13 心跳注释（: keep-alive）被忽略且不影响 seq', () => {
  const text = ': keep-alive\r\n\r\n' + sse(1, 'token', { request_id: 'r', seq: 1, timestamp: 't', text_delta: 'x', answer_block_id: 'b' })
  const { events, issues } = feed(text, 7)
  assert.equal(events.length, 1)
  assert.equal(events[0].data.seq, 1)
  assert.deepEqual(issues, [])
})

/* ================= P3/P5/P6/P8/P11/P12 ================= */
check('P3 冒号后只吃一个空格（保留 text_delta 的前导空格）', () => {
  const { events } = feed(
    'id: 1\r\nevent: token\r\ndata: {"request_id":"r","seq":1,"timestamp":"t","answer_block_id":"b","text_delta":"   两个前导空格"}\r\n\r\n',
    7,
  )
  assert.equal(events[0].data.text_delta, '   两个前导空格')
})

check('P6 空行但 data 为空：不派发事件', () => {
  const { events } = feed('id: 7\r\n\r\nid: 8\r\nevent: token\r\ndata: {"request_id":"r","seq":8,"timestamp":"t","text_delta":"y","answer_block_id":"b"}\r\n\r\n', 7)
  assert.equal(events.length, 1, '空 data 不得派发成空事件')
  assert.equal(events[0].data.seq, 8)
})

check('P8 id 与 data.seq 不一致：以 data.seq 为准并记 id-seq-mismatch', () => {
  const { events, issues } = feed(
    'id: 99\r\nevent: token\r\ndata: {"request_id":"r","seq":3,"timestamp":"t","text_delta":"z","answer_block_id":"b"}\r\n\r\n',
    7,
  )
  assert.equal(events.length, 1)
  assert.equal(events[0].data.seq, 3)
  assert.ok(issues.includes('id-seq-mismatch'))
})

check('P11 首个分片带 UTF-8 BOM：必须剥离（否则第一帧全丢）', () => {
  const payload = '\uFEFF' + sse(1, 'token', { request_id: 'r', seq: 1, timestamp: 't', text_delta: 'ok', answer_block_id: 'b' })
  const { events } = feed(payload, 7)
  assert.equal(events.length, 1, 'BOM 未剥离会丢掉第一帧')
})

check('P12 单事件 payload 超限：记 buffer-limit-exceeded', () => {
  const huge = 'x'.repeat((1 << 20) + 10)
  const { issues } = feed(`id: 1\r\nevent: token\r\ndata: {"request_id":"r","seq":1,"timestamp":"t","answer_block_id":"b","text_delta":"${huge}"}\r\n\r\n`, 4096)
  assert.ok(issues.includes('buffer-limit-exceeded'))
})

check('P10 最后一帧中途结束：记 truncated-frame', () => {
  const parser = createSseParser()
  parser.push(enc.encode('id: 1\r\nevent: token\r\ndata: {"request_id":"r","seq":1,"tim'))
  const tail = parser.end()
  assert.ok(tail.pendingBytes > 0)
  assert.ok(parser.issues().includes('truncated-frame'))
})

/* ================= 端到端：mock 真流 → 解析 → 状态机 ================= */
async function e2e() {
  const steps = buildScript('明天有什么课？顺便看看实验课要准备什么。', 'req_mock_e2e', 'conv_mock_e2e')
  const res = createChatResponse(steps, null)
  assert.equal(res.status, 200)
  assert.match(res.headers.get('content-type') ?? '', /text\/event-stream/)

  const reader = res.body.getReader()
  const parser = createSseParser()
  const collected = []
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    collected.push(...parser.push(value))
  }
  parser.end()

  assert.equal(collected.length, steps.length, `事件数应与脚本一致：${collected.length} vs ${steps.length}`)
  assert.deepEqual(parser.issues(), [], `不应有协议违规，实际：${parser.issues().join(',')}`)
  for (const e of collected) assert.ok(SSE_EVENT_NAMES.includes(e.event), `未知事件名 ${e.event}`)
  for (const e of collected) {
    if (e.event === 'tool_start') assert.ok(TOOL_NAMES.includes(e.data.tool_name), `工具名越界 ${e.data.tool_name}`)
  }

  let turn = createTurn('crid_e2e')
  const seen = new Set()
  let lastSeq = 0
  for (const e of collected) {
    if (accept(seen, lastSeq, e) !== 'accept') continue
    lastSeq = e.data.seq
    turn = reduce(turn, e).turn
  }
  assert.equal(turn.terminal, 'succeeded')
  assert.equal(turn.citations.length, 1, 'done.citations 必须被采纳')
  assert.equal(turn.citations[0].file_name, '数据结构实验指导书（2026 秋）.pdf')
  assert.equal(turn.conversationId, 'conv_mock_e2e')
  assert.equal(turn.steps.length, 3, '三个工具步骤')
  assert.deepEqual(turn.steps.map((s) => s.status), ['ok', 'ok', 'created'], 'created 与 existing 都算成功')
  const answer = turn.blocks.map((b) => b.text).join('')
  assert.ok(answer.includes('预习实验二排序算法'), '正文应完整拼接')
  assert.ok(answer.includes('〔资料 1〕'), '未验证引用标记应在正文里')
  assert.equal(turn.planId, 'plan_7Q2F9K')
  assert.equal(turn.draftId, 'draft_mock_1')

  // 写工具产生了 track-write-op 副作用指令
  const effects = []
  for (const e of collected) effects.push(...reduce(createTurn('crid_e2e'), e).effects)
  assert.ok(effects.some((x) => x.kind === 'track-write-op'), 'save_study_plan 必须触发写操作核实')

  return { eventCount: collected.length, steps: turn.steps.length, citations: turn.citations.length, answerLen: answer.length }
}

/* ================= 其余纯函数 ================= */
check('validatePlanForm：两端日期必须同时填且有序（§11.4）', () => {
  assert.equal(validatePlanForm({ title: 't', goal: '', start_date: '', end_date: '', content: 'c' }).length, 0)
  const onlyStart = validatePlanForm({ title: 't', goal: '', start_date: '2026-10-22', end_date: '', content: 'c' })
  assert.deepEqual(onlyStart.map((i) => i.kind), ['date-range', 'date-range'])
  const reversed = validatePlanForm({ title: 't', goal: '', start_date: '2026-10-24', end_date: '2026-10-22', content: 'c' })
  assert.equal(reversed.length, 2)
  const missing = validatePlanForm({ title: '', goal: '', start_date: '', end_date: '', content: '' })
  assert.equal(missing.length, 2, '标题与正文必填')
})

check('validateScheduleForm：结束时间必须晚于开始时间且不跨日（content-spec:165）', () => {
  const ok = validateScheduleForm({ student_id: 'u', course_id: 'c', class_date: '2026-10-22', start_time: '08:00', end_time: '09:40', location: '', reason: '' })
  assert.equal(ok.length, 0)
  const bad = validateScheduleForm({ student_id: 'u', course_id: 'c', class_date: '2026-10-22', start_time: '10:00', end_time: '09:00', location: '', reason: '' })
  assert.deepEqual(bad.map((i) => i.kind), ['time-range', 'time-range'])
})

check('canSubmitMessage：空白不可提交（content-spec S02）', () => {
  assert.equal(canSubmitMessage('   '), false)
  assert.equal(canSubmitMessage('查今天的课'), true)
  assert.equal(canSubmitMessage('字'.repeat(2001)), false)
})

check('isValidIdempotencyKey：只允许 ^[A-Za-z0-9._:-]+$ 且 ≤96（§6.3）', () => {
  assert.equal(isValidIdempotencyKey('plan_create_abc:123'), true)
  assert.equal(isValidIdempotencyKey('has space'), false)
  assert.equal(isValidIdempotencyKey('x'.repeat(97)), false)
})

check('format：星期用 Date.UTC 算（不随本地时区漂移）、码点计数、字节格式化', () => {
  // 2026-10-22 是周四
  assert.equal(formatDateWithWeekday('2026-10-22'), '2026-10-22（周四）')
  assert.equal(codePointLength('🎒'), 1)
  assert.equal(codePointLength('中文'), 2)
  assert.equal(formatBytes(2516582), '2.4 MiB')
})

check('mapError：只有冻结文案的码返回句子；会话失效码可识别', () => {
  assert.equal(mapErrorText({ code: 'DUPLICATE_COURSE' }), '该课程代码已存在，请更换。')
  assert.equal(mapErrorText({ code: 'VERSION_CONFLICT' }), '这份计划已被其他标签页修改，请重新加载后再提交；你未提交的编辑会保留。')
  assert.equal(mapErrorText({ code: 'RESOURCE_NOT_FOUND' }), null, '没冻结文案的码必须返回 null，不得自造')
  assert.equal(isAuthFailureCode('SESSION_EXPIRED'), true)
  assert.equal(isAuthFailureCode('INTERNAL_ERROR'), false)
})

/* ---------- 输出 ---------- */
const e2eResult = await e2e()
rows.push(`PASS  E2E mock 真流 → 解析 → 状态机（${e2eResult.eventCount} 事件 / ${e2eResult.steps} 步骤 / ${e2eResult.citations} 引用 / 正文 ${e2eResult.answerLen} 字）`)
passed++

console.log('流式链路冒烟（node --import ./scripts/ts-alias-hook.mjs scripts/smoke-sse.mjs）')
console.log('='.repeat(78))
for (const r of rows) console.log(r)
console.log('='.repeat(78))
console.log(`${passed}/${rows.length} 通过`)
