/**
 * 流式轮次状态机（纯函数）。权威口径 = 前端详细设计 §5.4 的转换表 + §6.5 的 store 侧义务。
 *
 * 三条不可动摇的规则：
 *   1. **HTTP 关闭 ≠ 终态**（§5.9）：流结束而没有 done/error ⇒ `unknown`，不是 `failed`。
 *   2. **终态唯一**：第二个 done/error 被忽略并记 `double-terminal`。
 *   3. **去重不靠覆盖**：`(request_id, seq)` 只应用一次（见 domain/dedupe.ts）。
 *
 * 纯函数：不发请求、不碰 DOM、不碰 store（§2.2 R1）。
 */

import { PROTOCOL_ISSUES, STATUS_CODE_ACCEPTED, TOOL_NAMES, WRITE_TOOLS } from './constants'
import type { AsyncTaskCode, ProtocolIssue, ToolName } from './constants'
import { accept, dedupeKey } from './dedupe'
import type { Reference, SseEvent } from './sseTypes'

export type Phase = 'idle' | 'submitting' | 'streaming' | 'terminal'
export type TerminalKind = 'succeeded' | 'cancelled' | 'failed' | 'unknown'

/** 步骤的展示状态（§6.5 `ChatStepVM.status`）。 */
export type StepStatus = 'running' | 'ok' | 'empty' | 'created' | 'existing' | 'failed'

export interface ToolStep {
  toolCallId: string
  toolName: ToolName
  /** 逐字取自事件，前端不得改写（§6.5）。 */
  displayName: string
  status: StepStatus
  code?: string
  planId?: string
  operationId?: string
}

export interface AnswerBlock {
  answerBlockId: string
  text: string
}

export interface ChatTurn {
  clientRequestId: string
  requestId: string | null
  conversationId: string | null
  phase: Phase
  terminal: TerminalKind | null
  terminalReason: string | null
  lastSeq: number
  /** 去重键集合：`${request_id}:${seq}`（§6.5）。 */
  seen: Set<string>
  blocks: AnswerBlock[]
  steps: ToolStep[]
  citations: Reference[]
  issues: ProtocolIssue[]
  /** 传输层已关闭 —— **不等于**终态（§5.9）。 */
  transportClosed: boolean
  planId: string | null
  operationId: string | null
  draftId: string | null
  draftVersion: number | null
  /** `search_course_docs` 报「全库尚无已发布资料」（S05 第 3 态）；与「依据不足」不同。 */
  corpusEmpty: boolean
  /** 服务端提示历史被截断（status.code=CONTEXT_TRUNCATED，SRS FR-CHAT-001）。 */
  contextTruncated: boolean
}

/**
 * 状态机输出的副作用指令；由 store 执行，状态机自己不执行（§2.3）。
 *
 * 注意：**没有** `bind-draft` 这一项。§6.5 要求 `status` 事件带 `draft_id` 时调 `drafts.bind()`，
 * 但 §6.2 的静态依赖表里 `chat` 不允许依赖 `drafts`（依赖图只有 `chat --> writeOps`），
 * 而 §6.16 验收点 2 会机械核对「表之外没有新的依赖边」。
 * 因此草稿绑定改由**视图**完成（§2.2 R5「只有 views 可以读多个 store 并组合」）：
 * 状态机只把 `draftId`/`draftVersion` 记在 turn 上，`AssistantView` 侦测到后调 `drafts.bind()`。
 */
export type Effect =
  | { kind: 'track-write-op'; operationId: string; source: 'chat-tool' | 'chat-done' }
  | { kind: 'auth-failure'; code: string }
  | { kind: 'protocol-issue'; issue: ProtocolIssue }
  | { kind: 'capacity-limited'; code: string }

export function createTurn(clientRequestId: string): ChatTurn {
  return {
    clientRequestId,
    requestId: null,
    conversationId: null,
    phase: 'submitting',
    terminal: null,
    terminalReason: null,
    lastSeq: 0,
    seen: new Set<string>(),
    blocks: [],
    steps: [],
    citations: [],
    issues: [],
    transportClosed: false,
    planId: null,
    operationId: null,
    draftId: null,
    draftVersion: null,
    corpusEmpty: false,
    contextTruncated: false,
  }
}

/** 本轮是否出现过写意图（§5.9 的判定行）。 */
export function hasWriteIntent(turn: ChatTurn): boolean {
  return turn.steps.some((s) => WRITE_TOOLS.includes(s.toolName)) || turn.operationId !== null || turn.planId !== null
}

/** 未配对的（仍为 running 的）工具步骤：终态时渲染为「未完成」，既不是成功也不是失败（§5.4）。 */
export function unpairedSteps(turn: ChatTurn): ToolStep[] {
  return turn.steps.filter((s) => s.status === 'running')
}

/**
 * 终态推导。**第三个分支是本章最易写错的地方**：
 * 读超时 / 网络中断 / 流正常关闭但没有终态事件，一律 `unknown`，不得直接判 failed（§5.8、§5.9）。
 */
export function toTerminal(turn: ChatTurn, how: 'stream-ended' | 'aborted' | 'error'): TerminalKind {
  if (turn.terminal !== null) return turn.terminal
  if (how === 'aborted') return 'cancelled' // 本地乐观值；服务端终态到达后以其为准（§5.7）
  return 'unknown'
}

function clone(turn: ChatTurn): ChatTurn {
  return {
    ...turn,
    seen: new Set(turn.seen),
    blocks: turn.blocks.map((b) => ({ ...b })),
    steps: turn.steps.map((s) => ({ ...s })),
    citations: [...turn.citations],
    issues: [...turn.issues],
  }
}

function pushIssue(t: ChatTurn, issue: ProtocolIssue, effects: Effect[]): void {
  if (!PROTOCOL_ISSUES.includes(issue)) return
  t.issues.push(issue)
  effects.push({ kind: 'protocol-issue', issue })
}

/**
 * 旧状态 + 事件 → 新状态 + 副作用指令。
 * 事件已被去重（`accept`）与白名单（`parse`）过滤；本函数仍防御 `terminal !== null` 的情况。
 */
export function reduce(prev: ChatTurn, e: SseEvent): { turn: ChatTurn; effects: Effect[] } {
  const turn = clone(prev)
  const effects: Effect[] = []

  // 终态已定：后续事件一律忽略，第二个终态事件记 double-terminal（§5.4 末行）。
  if (turn.terminal !== null) {
    if (e.event === 'done' || e.event === 'error') pushIssue(turn, 'double-terminal', effects)
    return { turn, effects }
  }

  const seq = e.data.seq
  const key = dedupeKey(e.data.request_id, seq)
  const verdict = accept(turn.seen, turn.lastSeq, e)
  if (verdict !== 'accept') {
    // accept() 已把新键写入；重复/倒退事件不得改变 blocks（§6.16 验收点 6）。
    if (verdict === 'duplicate') turn.seen.delete(key)
    return { turn, effects }
  }
  turn.lastSeq = seq
  turn.requestId = turn.requestId ?? e.data.request_id

  switch (e.event) {
    case 'status': {
      turn.phase = 'streaming'
      if (e.data.code === STATUS_CODE_ACCEPTED) {
        if (e.data.conversation_id) {
          turn.conversationId = e.data.conversation_id
        } else {
          // A11：ACCEPTED 缺 conversation_id ⇒ 记协议违规并进 unknown。
          pushIssue(turn, 'missing-conversation-id', effects)
          turn.terminal = 'unknown'
          turn.phase = 'terminal'
        }
      }
      if (e.data.draft_id) {
        // 只记在 turn 上；`drafts.bind()` 由视图调用（见本文件上方 Effect 的说明）。
        turn.draftId = e.data.draft_id
        turn.draftVersion = e.data.draft_version ?? null
      }
      if (e.data.code === 'CAPACITY_LIMITED' || e.data.code === 'CALL_LIMIT_REACHED') {
        effects.push({ kind: 'capacity-limited', code: e.data.code })
      }
      if (e.data.code === 'CONTEXT_TRUNCATED') {
        // 服务端已按预算保留最近完整问答对：这里只负责让提示"可见"（SRS FR-CHAT-001）。
        turn.contextTruncated = true
      }
      break
    }

    case 'tool_start': {
      turn.phase = 'streaming'
      if (!TOOL_NAMES.includes(e.data.tool_name)) {
        // §5.4：tool_name 只可能是三个白名单值，出现别的即协议违规。
        pushIssue(turn, 'unknown-event', effects)
        break
      }
      const existing = turn.steps.find((s) => s.toolCallId === e.data.tool_call_id)
      if (existing) {
        existing.status = 'running'
        existing.displayName = e.data.display_name
      } else {
        turn.steps.push({
          toolCallId: e.data.tool_call_id,
          toolName: e.data.tool_name,
          displayName: e.data.display_name,
          status: 'running',
        })
      }
      break
    }

    case 'tool_end': {
      turn.phase = 'streaming'
      const step = turn.steps.find((s) => s.toolCallId === e.data.tool_call_id)
      if (!step) {
        // A9：tool_end 无配对 tool_start ⇒ 忽略 + 埋点，不渲染孤立步骤。
        pushIssue(turn, 'unpaired-tool', effects)
        break
      }
      // 全库为空是**结果性质**，不是步骤状态：记在本轮上，由终态区域决定渲染哪种文案。
      if (e.data.corpus_empty === true) turn.corpusEmpty = true
      if (e.data.success === false) {
        step.status = 'failed'
        // A10：缺 code 时按 failed 渲染，用通用失败文案（文案由 mapError 提供）。
        if (e.data.code) step.code = e.data.code
      } else {
        // created / existing **都算成功**；existing 是幂等命中，不是错误（§5.4）。
        step.status = e.data.result_status
      }
      if (e.data.plan_id) {
        step.planId = e.data.plan_id
        turn.planId = e.data.plan_id
      }
      if (e.data.operation_id) {
        step.operationId = e.data.operation_id
        turn.operationId = e.data.operation_id
        if (step.toolName === 'save_study_plan') {
          effects.push({ kind: 'track-write-op', operationId: e.data.operation_id, source: 'chat-tool' })
        }
      }
      break
    }

    case 'token': {
      turn.phase = 'streaming'
      const block = turn.blocks.find((b) => b.answerBlockId === e.data.answer_block_id)
      if (block) block.text += e.data.text_delta
      else turn.blocks.push({ answerBlockId: e.data.answer_block_id, text: e.data.text_delta })
      break
    }

    case 'done': {
      turn.terminal = e.data.state
      turn.terminalReason = e.data.reason ?? null
      turn.phase = 'terminal'
      // 引用以 done 为准，替换过程中的临时引用（§5.4）。
      turn.citations = e.data.citations ?? []
      if (e.data.plan_id) turn.planId = e.data.plan_id
      if (e.data.operation_id) {
        turn.operationId = e.data.operation_id
        if (hasWriteIntent(turn)) {
          effects.push({ kind: 'track-write-op', operationId: e.data.operation_id, source: 'chat-done' })
        }
      }
      markUnpaired(turn, effects)
      break
    }

    case 'error': {
      turn.terminal = 'failed'
      turn.terminalReason = e.data.code
      turn.phase = 'terminal'
      // §6.5：error 分支**不读** plan_id / operation_id（AUTH 两码 schema 亦禁止携带）。
      if (e.data.code === 'AUTH_REQUIRED' || e.data.code === 'SESSION_EXPIRED') {
        effects.push({ kind: 'auth-failure', code: e.data.code })
      }
      markUnpaired(turn, effects)
      break
    }
  }

  return { turn, effects }
}

function markUnpaired(turn: ChatTurn, effects: Effect[]): void {
  if (unpairedSteps(turn).length > 0) pushIssue(turn, 'unpaired-tool', effects)
}

/** 传输层关闭时的收尾（§6.5 `onTransportClosed`）。返回是否落 unknown。 */
export function closeTransport(prev: ChatTurn): { turn: ChatTurn; effects: Effect[] } {
  const turn = clone(prev)
  const effects: Effect[] = []
  turn.transportClosed = true
  if (turn.terminal === null) {
    // 正常关闭就是成功路径——只有当没有终态时才落 unknown。
    turn.terminal = 'unknown'
    turn.phase = 'terminal'
    markUnpaired(turn, effects)
  }
  return { turn, effects }
}

export type { AsyncTaskCode }
