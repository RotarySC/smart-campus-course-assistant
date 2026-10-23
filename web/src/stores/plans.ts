/**
 * `plans` store —— 计划列表与详情、`version`（并发控制）。
 *
 * 三条易错点（§6.7）：
 *   - 创建必须带 `Idempotency-Key`；`existing`/`deleted` **都不是失败**（`existing` 是幂等命中）；
 *   - `PATCH` body 带 `expected_version`；`DELETE` 的 `expected_version` 在 **query**；
 *   - `202` 立即落「待确认」，**不**显示「保存成功」（FR-PLAN-005）。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as meApi from '@/api/me'
import type { AppError } from '@/api/errors'
import type { Plan, PlanCreate } from '@/api/types.gen'
import { useSessionStore } from './session'
import { useUiStore } from './ui'
import { useWriteOpsStore } from './writeOps'

export type CreateOutcome =
  | { kind: 'created'; operationId: string; planId: string }
  | { kind: 'existing'; operationId: string; planId: string }
  | { kind: 'deleted'; operationId: string; planId: string }
  | { kind: 'pending'; operationId: string }

type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

export const usePlansStore = defineStore('plans', () => {
  const session = useSessionStore()
  const ui = useUiStore()
  const writeOps = useWriteOpsStore()

  const items = ref<Plan[]>([])
  const page = ref(1)
  const pageSize = ref(20)
  const total = ref(0)
  const titleFilter = ref('')
  const detail = ref<Plan | null>(null)
  const status = ref<LoadStatus>('idle')
  const error = ref<AppError | null>(null)
  const lastRequestId = ref<string | null>(null)

  /** 空列表：`items=[]` 且 `error===null`（§6.7）。 */
  const isEmpty = computed(() => status.value === 'ready' && items.value.length === 0 && error.value === null)

  async function list(p: { page?: number; page_size?: number; title?: string } = {}): Promise<void> {
    status.value = 'loading'
    if (p.title !== undefined) titleFilter.value = p.title
    try {
      const res = await meApi.listPlans(session.auth, {
        page: p.page ?? 1,
        page_size: p.page_size ?? pageSize.value,
        title: titleFilter.value === '' ? undefined : titleFilter.value,
      })
      items.value = res.items
      page.value = res.page
      pageSize.value = res.page_size
      total.value = res.total
      error.value = null
      status.value = 'ready'
    } catch (e) {
      error.value = e as AppError
      status.value = 'error'
      throw e
    }
  }

  /** 深链唯一入口：`/me/plans/:planId`（§7.6）。非本人计划按 404 处理，不显示目标是否存在。 */
  async function get(id: string): Promise<void> {
    status.value = 'loading'
    try {
      detail.value = await meApi.getPlan(session.auth, id)
      error.value = null
      status.value = 'ready'
    } catch (e) {
      detail.value = null
      error.value = e as AppError
      status.value = 'error'
      throw e
    }
  }

  async function create(input: PlanCreate, idempotencyKey: string): Promise<CreateOutcome> {
    const res = await meApi.createPlan(session.auth, input, idempotencyKey)
    if (res.status === 'created') return { kind: 'created', operationId: res.operation_id, planId: res.plan_id }
    if (res.status === 'existing') return { kind: 'existing', operationId: res.operation_id, planId: res.plan_id }
    return { kind: 'deleted', operationId: res.operation_id, planId: res.plan_id }
  }

  /** 202 落「待确认」；界面**不得**显示「保存成功」。 */
  function markPending(operationId: string): CreateOutcome {
    writeOps.track({ operationId, source: 'plan-create' })
    return { kind: 'pending', operationId }
  }

  /** 自动带 `detail.version`（版本值一律取**最近一次服务端响应**，§6.13 规则 3）。 */
  async function patch(id: string, input: Omit<Parameters<typeof meApi.patchPlan>[2], 'expected_version'>): Promise<void> {
    const version = detail.value?.version
    if (version === undefined) throw new Error('plan detail not loaded')
    const next = await meApi.patchPlan(session.auth, id, { ...input, expected_version: version })
    detail.value = next // 用响应整体替换（含新 version）
  }

  async function remove(id: string, expectedVersion: number): Promise<void> {
    await meApi.deletePlan(session.auth, id, expectedVersion)
    items.value = items.value.filter((p) => p.id !== id)
    if (detail.value?.id === id) detail.value = null
  }

  function clear(): void {
    items.value = []
    page.value = 1
    total.value = 0
    titleFilter.value = ''
    detail.value = null
    status.value = 'idle'
    error.value = null
    void ui
  }

  session.registerCleanup(clear)

  return {
    items,
    page,
    pageSize,
    total,
    titleFilter,
    detail,
    status,
    error,
    lastRequestId,
    isEmpty,
    list,
    get,
    create,
    markPending,
    patch,
    remove,
    clear,
  }
})
