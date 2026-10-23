/**
 * `chat` store —— 当前对话轮次列表、进行中请求的流式状态、`request_id`、终态。
 *
 * 允许的静态依赖：`session`、`ui`、`writeOps`（§6.2）。
 * 本 store **零持久化**：正文只驻留内存，`clear()` 后不可恢复（HLD-D11）。
 *
 * 它是 §5.4 状态机的**唯一入口**：所有事件都经 `applyEvent()`，
 * 状态转换本身在 `domain/chatMachine.ts`（纯函数、可穷举单测）。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as chatApi from '@/api/chat'
import { startChatStream } from '@/api/sse/stream'
import type { AppError } from '@/api/errors'
import { abortedError } from '@/api/errors'
import { createLiveBuffer } from '@/a11y/live'
import { createTurn, hasWriteIntent, reduce, closeTransport, toTerminal } from '@/domain/chatMachine'
import type { ChatTurn, Effect, TerminalKind } from '@/domain/chatMachine'
import { LIMITS, SCROLL_FOLLOW_THRESHOLD_PX, STREAM_FLUSH_MS } from '@/domain/constants'
import { codePointLength } from '@/domain/format'
import type { SseEvent } from '@/domain/sseTypes'
import type { HistoryMessage } from '@/api/types.gen'
import { useSessionStore } from './session'
import { useUiStore } from './ui'
import { useWriteOpsStore } from './writeOps'

export interface ChatRoundVM extends ChatTurn {
  /** 用户这一轮说的话（只用于渲染气泡；不进 history 以外的任何地方）。 */
  userMessage: string
}

type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

export const useChatStore = defineStore('chat', () => {
  const session = useSessionStore()
  const ui = useUiStore()
  const writeOps = useWriteOpsStore()

  const rounds = ref<ChatRoundVM[]>([])
  const activeIndex = ref<number | null>(null)
  const status = ref<LoadStatus>('idle')
  const error = ref<AppError | null>(null)
  const lastRequestId = ref<string | null>(null)

  let controller: AbortController | null = null

  const live = createLiveBuffer({
    politeness: 'polite',
    flushMs: 500,
    sink: (m) => ui.announce(m),
  })

  const activeRound = computed(() => (activeIndex.value === null ? null : rounds.value[activeIndex.value] ?? null))
  const isStreaming = computed(() => activeRound.value?.phase === 'submitting' || activeRound.value?.phase === 'streaming')
  /** 本轮是否出现过写意图 ⇒ `unknown` 时必须核实而不是让人重试（§5.9）。 */
  const activeHasWriteIntent = computed(() => (activeRound.value ? hasWriteIntent(activeRound.value) : false))

  function applyEffects(effects: Effect[]): void {
    for (const eff of effects) {
      switch (eff.kind) {
        case 'track-write-op':
          writeOps.track({ operationId: eff.operationId, source: eff.source })
          break
        case 'auth-failure':
          // §4.6：唯一失效出口。清理序列由 session 负责。
          session.onAuthFailure('SSE_ERROR')
          break
        case 'capacity-limited':
        case 'protocol-issue':
          // 容量类提示与协议违规只记录；具体呈现由视图按 code 决定（§6.5、§13.6）。
          break
      }
    }
  }

  /** 发起一轮（§6.5 的 7 条规则）。 */
  async function submit(message: string, history?: HistoryMessage[]): Promise<void> {
    const text = message.trim()
    if (text.length === 0 || codePointLength(text) > LIMITS.chatMessage) return
    // 同一会话内已有一轮进行中：不得发起第二轮（§6.5 规则 7）。
    if (isStreaming.value) return

    // 规则 2：client_request_id 用 crypto.randomUUID()（满足 ^[A-Za-z0-9_-]+$ 与 ≤64）。
    const clientRequestId = newId()
    // 规则 3：conversation_id 取本会话内最近一轮的；首轮不传。
    const lastConversation = [...rounds.value].reverse().find((r) => r.conversationId)?.conversationId ?? undefined
    // 规则 4：history 只含 user/assistant 完整问答对，最多 20 轮，禁止工具结果与 system 内容。
    const builtHistory = history ?? buildHistory(rounds.value)

    const turn = createTurn(clientRequestId)
    const round: ChatRoundVM = { ...turn, userMessage: text }
    rounds.value.push(round)
    const index = rounds.value.length - 1
    activeIndex.value = index
    status.value = 'ready'
    error.value = null
    live.clear()

    controller = new AbortController()
    const body: Parameters<typeof startChatStream>[0] = { client_request_id: clientRequestId, message: text }
    if (lastConversation !== undefined) body.conversation_id = lastConversation
    if (builtHistory.length > 0) body.history = builtHistory

    const target = rounds.value[index] as ChatRoundVM

    try {
      const result = await startChatStream(
        body,
        {
          onEvent: (e) => applyEvent(e, index),
          onTerminal: (t) => {
            if (target.terminal === null) {
              target.terminal = t
              target.phase = 'terminal'
            }
          },
          onProtocolIssue: () => {
            /* 记在 turn.issues 内（applyEvent 走的是同一 reducer） */
          },
        },
        controller.signal,
        session.auth,
      )
      lastRequestId.value = result.requestId
      target.terminal = result.terminal
      target.phase = 'terminal'
      closeTransport(target)
      if (result.terminal === 'unknown') await handleUnknown(index)
    } catch (e) {
      const err = e as AppError
      if (err.kind === 'aborted') {
        // 用户取消：本地乐观 cancelled（§5.7），服务端终态到达后以其为准。
        target.terminal = target.terminal ?? 'cancelled'
        target.phase = 'terminal'
      } else {
        error.value = err
        target.terminal = target.terminal ?? 'failed'
        target.phase = 'terminal'
        if (err.code === 'AUTH_REQUIRED' || err.code === 'SESSION_EXPIRED') {
          session.onAuthFailure('HTTP_401')
        } else if (err.code === 'CHAT_IN_PROGRESS' || err.code === 'REQUEST_ALREADY_EXISTS') {
          // 用原 request_id 接管显示，**不新建轮次**（§3.4 409 行）。
          const existing = err.details?.existing_request_id
          if (existing) await verifyByState(existing)
        }
      }
    } finally {
      controller = null
      live.flush()
      // 终态时一次性提交完整结论（§5.10）。
      const answer = target.blocks.map((b) => b.text).join('')
      if (answer !== '') ui.announce(answer)
    }
  }

  /** 状态机唯一入口。索引可省（默认当前轮），便于 `onEvent` 直接复用。 */
  function applyEvent(ev: SseEvent, index?: number): void {
    const i = index ?? activeIndex.value
    if (i === null) return
    const round = rounds.value[i]
    if (!round) return
    const seeded = seed(round)
    const out = reduce(seeded, ev)
    Object.assign(round, out.turn)
    applyEffects(out.effects)
    if (ev.event === 'token') {
      // live region 按 500ms 批量提交；**绝不移动焦点**（§5.10）。
      live.push(ev.data.text_delta)
    }
  }

  /** HTTP 关闭 ≠ 终态（§5.9）。 */
  function onTransportClosed(index: number): void {
    const round = rounds.value[index]
    if (!round) return
    const out = closeTransport(seed(round))
    Object.assign(round, out.turn)
  }

  async function handleUnknown(index: number): Promise<void> {
    const round = rounds.value[index]
    if (!round) return
    if (hasWriteIntent(round) && round.operationId) {
      // 写操作必须核实：交 writeOps（§5.9）。
      writeOps.track({ operationId: round.operationId, source: 'chat-done' })
      return
    }
    if (round.requestId) {
      // 读操作：用服务端权威状态核实（只读，不改服务端）。
      await verifyByState(round.requestId, index)
    }
  }

  /** `GET /api/v1/chat/requests/{request_id}` —— 只读核实。 */
  async function verifyByState(requestId: string, index?: number): Promise<void> {
    try {
      const st = await chatApi.getChatState(session.auth, requestId)
      lastRequestId.value = requestId
      const i = index ?? activeIndex.value
      if (i === null) return
      const round = rounds.value[i]
      if (!round) return
      switch (st.state) {
        case 'accepted':
        case 'running':
          // 仍是「结果待确认」；不判定失败，不判定未写入（FR-CHAT-005）。
          round.terminal = 'unknown'
          break
        case 'succeeded':
          round.terminal = 'succeeded'
          if (st.plan_id !== undefined) round.planId = st.plan_id
          if (st.operation_id !== undefined) {
            round.operationId = st.operation_id
            writeOps.track({ operationId: st.operation_id, source: 'chat-done' })
          }
          break
        case 'failed':
          round.terminal = 'failed'
          round.terminalReason = st.terminal_reason ?? null
          break
        case 'cancelled':
          round.terminal = 'cancelled'
          break
      }
      round.phase = 'terminal'
    } catch {
      /* 核实失败不改判定：保持 unknown。 */
    }
  }

  /** 取消顺序固定：**先 POST cancel，再 abort**（顺序反了会丢服务端的取消机会，§5.7）。 */
  async function cancel(requestId: string): Promise<void> {
    try {
      await chatApi.cancelChat(session.auth, requestId)
    } catch {
      /* 取消失败不阻断本地中止 */
    }
    abortActiveStream()
  }

  /** 仅 abort，不调接口（§4.5/§4.6.3 的收尾用）。 */
  function abortActiveStream(): void {
    controller?.abort(abortedError())
    controller = null
  }

  /** 会话失效：该轮 → `unknown`（**不误报失败**，§6.14 第 2 步）。 */
  function freezeActiveRound(reason: 'AUTH_FAILED' | 'LOGOUT'): void {
    void reason
    const round = activeRound.value
    if (!round) return
    if (round.terminal === null) round.terminal = toTerminal(round, 'stream-ended')
    round.phase = 'terminal'
  }

  function clear(): void {
    abortActiveStream()
    live.clear()
    rounds.value = []
    activeIndex.value = null
    status.value = 'idle'
    error.value = null
    lastRequestId.value = null
  }

  /** 清空对话（S02 的「清空对话」）；**不删除已保存的计划**（content-spec:64 的后半句）。 */
  function clearConversation(): void {
    clear()
  }

  /** 供视图做「距底 < 48px 才自动跟随」的判定（§5.10）。 */
  function shouldFollowScroll(el: HTMLElement): boolean {
    return el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_FOLLOW_THRESHOLD_PX
  }

  function buildHistory(list: ChatRoundVM[]): HistoryMessage[] {
    const pairs: HistoryMessage[] = []
    for (const r of list) {
      const answer = r.blocks.map((b) => b.text).join('')
      if (r.userMessage === '' || answer === '') continue
      pairs.push({ role: 'user', content: r.userMessage.slice(0, LIMITS.chatHistoryContent) })
      pairs.push({ role: 'assistant', content: answer.slice(0, LIMITS.chatHistoryContent) })
    }
    // 最多 20 轮（= 40 条消息，与 ChatInput.history 的 maxItems:40 一致）。
    return pairs.slice(-LIMITS.chatHistoryRounds * 2)
  }

  session.registerPreClear(() => abortActiveStream())
  session.registerPreClear(() => freezeActiveRound('AUTH_FAILED'))
  session.registerCleanup(clear)

  return {
    rounds,
    activeIndex,
    status,
    error,
    lastRequestId,
    activeRound,
    isStreaming,
    activeHasWriteIntent,
    submit,
    applyEvent,
    onTransportClosed,
    verifyByState,
    cancel,
    abortActiveStream,
    freezeActiveRound,
    clear,
    clearConversation,
    shouldFollowScroll,
    STREAM_FLUSH_MS,
  }
})

/** 展开 `ChatTurn` 的可变副本（`reduce` 内部已 clone，这里只补 `userMessage`）。 */
function seed(round: ChatRoundVM): ChatTurn {
  const { userMessage: _drop, ...turn } = round
  void _drop
  return turn
}

function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `crid_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

export type { TerminalKind }
