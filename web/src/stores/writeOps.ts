/**
 * `writeOps` store —— 写操作结果未知时的「待确认」态与 `operation_id` 核实轮询。
 *
 * 核心口径（§6.9）：
 *   - **待确认 ≠ 失败**（FR-CHAT-005）：`state=pending` 继续核实，不显示失败；
 *   - 退避（**唯一权威表**）1s → 2s → 4s → 8s → 上限 10s，**无步数上限**，
 *     得到确定结果即停，页面不可见即暂停；
 *   - 连续 5 次仍未决 → **停止轮询并保持「待确认」**，出口交给用户（§5.9 的终止条件）；
 *   - 会话失效即 `freezeAll()`，不再轮询（§4.6.3 第 3 步）；
 *   - 与 `chat` 的终态**互不推断**（SRS INV-07）。
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as meApi from '@/api/me'
import type { AppError } from '@/api/errors'
import { WRITE_OP_BACKOFF_MS, WRITE_OP_UNDECIDED_LIMIT } from '@/domain/constants'
import { useSessionStore } from './session'
import { useUiStore } from './ui'

export type WriteOpState = 'pending' | 'succeeded' | 'failed' | 'deleted'
export type Resolution = 'confirmed' | 'recovering'
export type WriteOpSource = 'draft-save' | 'plan-create' | 'chat-tool' | 'chat-done'

export interface WriteOpRecord {
  operationId: string
  state: WriteOpState
  resolution: Resolution
  planId?: string
  errorCode?: string
  retryable: boolean
  source: WriteOpSource
  firstSeenAt: number
  lastPolledAt: number | null
  pollCount: number
  /** 会话失效后冻结，不再轮询。 */
  frozen: boolean
  lastRequestId: string | null
  /** 连续未决次数到达上限 → 保持「待确认」并停止自动轮询。 */
  manualOnly: boolean
}

export const useWriteOpsStore = defineStore('writeOps', () => {
  const session = useSessionStore()
  const ui = useUiStore()

  const records = ref<Record<string, WriteOpRecord>>({})
  const timers = new Map<string, ReturnType<typeof setTimeout>>()
  let visibilityBound = false

  /** 进入待确认并开始核实（首查立即执行，§6.9）。 */
  function track(input: { operationId: string; source: WriteOpSource }): void {
    const existing = records.value[input.operationId]
    if (existing) {
      // 同一 operation 重复 track：不重置状态（避免重复创建，§6.9 禁止项）。
      if (existing.state === 'pending' && !existing.frozen) schedule(existing.operationId, 0)
      return
    }
    records.value[input.operationId] = {
      operationId: input.operationId,
      state: 'pending',
      resolution: 'confirmed',
      retryable: false,
      source: input.source,
      firstSeenAt: Date.now(),
      lastPolledAt: null,
      pollCount: 0,
      frozen: false,
      lastRequestId: null,
      manualOnly: false,
    }
    bindVisibility()
    schedule(input.operationId, 0)
  }

  /** `GET /api/v1/me/write-operations/{operation_id}`；手动入口「查询写入状态」也调它。 */
  async function verify(operationId: string): Promise<void> {
    const rec = records.value[operationId]
    if (!rec || rec.frozen) return
    try {
      const op = await meApi.getWriteOperation(session.auth, operationId)
      rec.state = op.state
      rec.resolution = op.resolution
      rec.retryable = op.retryable
      if (op.plan_id !== undefined) rec.planId = op.plan_id
      if (op.error_code !== undefined) rec.errorCode = op.error_code
      rec.lastPolledAt = Date.now()
      rec.pollCount += 1
      rec.manualOnly = false
    } catch (e) {
      const err = e as AppError
      rec.lastPolledAt = Date.now()
      if (err.code === 'AUTH_REQUIRED' || err.code === 'SESSION_EXPIRED') {
        rec.frozen = true
        return
      }
      // 核实失败不改判定：仍是「待确认」，不转 failed（§5.9）。
      rec.pollCount += 1
      if (rec.pollCount >= WRITE_OP_UNDECIDED_LIMIT) rec.manualOnly = true
    }
  }

  function schedule(operationId: string, delayMs: number): void {
    clearTimer(operationId)
    const t = setTimeout(async () => {
      timers.delete(operationId)
      const rec = records.value[operationId]
      if (!rec || rec.frozen) return
      // 页面不可见即暂停（§6.9）。
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        schedule(operationId, WRITE_OP_BACKOFF_MS[0])
        return
      }
      await verify(operationId)
      const after = records.value[operationId]
      if (!after || after.frozen) return
      if (after.state !== 'pending') return // 得到确定结果即停
      if (after.manualOnly) return // 5 次未决 → 停轮询，保持待确认
      const step = Math.min(after.pollCount, WRITE_OP_BACKOFF_MS.length - 1)
      schedule(operationId, WRITE_OP_BACKOFF_MS[step] ?? 10_000)
    }, delayMs)
    timers.set(operationId, t)
  }

  function clearTimer(operationId: string): void {
    const t = timers.get(operationId)
    if (t !== undefined) {
      clearTimeout(t)
      timers.delete(operationId)
    }
  }

  function stopAll(): void {
    for (const id of [...timers.keys()]) clearTimer(id)
  }

  /** §4.6.3 第 3 步：停止轮询（保留记录以便界面继续显示「待确认」）。 */
  function freezeAll(): void {
    stopAll()
    for (const rec of Object.values(records.value)) rec.frozen = true
  }

  function clear(): void {
    stopAll()
    records.value = {}
  }

  function bindVisibility(): void {
    if (visibilityBound || typeof document === 'undefined') return
    visibilityBound = true
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        for (const rec of Object.values(records.value)) {
          if (rec.state === 'pending' && !rec.frozen && !rec.manualOnly) schedule(rec.operationId, 0)
        }
      } else {
        stopAll()
      }
    })
  }

  // 会话失效：第 3 步先冻结（§6.14）；第 4 步再清空。
  session.registerPreClear(() => freezeAll())
  session.registerCleanup(() => {
    clear()
    void ui
  })

  return { records, track, verify, freezeAll, clear }
})
