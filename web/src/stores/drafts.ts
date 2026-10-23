/**
 * `drafts` store —— 草稿（未保存/已保存）、`draft_version`。
 *
 * 三条易错点（§6.8）：
 *   - `PATCH` 必带 **`expected_draft_version`**（不是 `expected_version`，那是计划的）；
 *   - `POST .../save` 的 body **只有 `draft_version`**，不得夹带正文改写；
 *   - `dirty=true` 时旧版本的保存许可失效：必须先 `revise()` 再 `save()`，
 *     否则会撞 `SAVE_NOT_AUTHORIZED`（SRS §7.3 / FR-PLAN-005）。
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as meApi from '@/api/me'
import type { AppError } from '@/api/errors'
import type { BasisType, Reference, SaveResult } from '@/api/types.gen'
import { useSessionStore } from './session'
import { useUiStore } from './ui'
import { useWriteOpsStore } from './writeOps'

export type SaveOutcome =
  | { kind: 'created'; operationId: string; planId: string }
  | { kind: 'existing'; operationId: string; planId: string }
  | { kind: 'deleted'; operationId: string; planId: string }
  | { kind: 'pending'; operationId: string }

export interface DraftFields {
  title: string
  goal: string | null
  start_date: string | null
  end_date: string | null
  content: string
}

type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

export const useDraftsStore = defineStore('drafts', () => {
  const session = useSessionStore()
  const ui = useUiStore()
  const writeOps = useWriteOpsStore()

  const draftId = ref<string | null>(null)
  const draftVersion = ref<number | null>(null)
  /** 服务端预分配的 operation_id（保存后用于核实）。 */
  const operationId = ref<string | null>(null)
  const fields = ref<DraftFields>({ title: '', goal: null, start_date: null, end_date: null, content: '' })
  const basisTypes = ref<BasisType[]>([])
  const references = ref<Reference[]>([])
  const expiresAt = ref<string | null>(null)
  const saved = ref(false)
  const planId = ref<string | null>(null)
  const dirty = ref(false)
  const status = ref<LoadStatus>('idle')
  const error = ref<AppError | null>(null)
  const lastRequestId = ref<string | null>(null)

  /** 由 chat 的 `status` 事件触发（§6.8）：只记 id/version，随后 `load()` 取全文。 */
  function bind(id: string, version?: number): void {
    draftId.value = id
    if (typeof version === 'number') draftVersion.value = version
    saved.value = false
    planId.value = null
  }

  async function load(id: string): Promise<void> {
    status.value = 'loading'
    error.value = null
    try {
      const d = await meApi.getDraft(session.auth, id)
      draftId.value = d.draft_id
      draftVersion.value = d.draft_version
      operationId.value = d.operation_id
      fields.value = {
        title: d.title,
        goal: d.goal ?? null,
        start_date: d.start_date ?? null,
        end_date: d.end_date ?? null,
        content: d.content,
      }
      basisTypes.value = d.basis_types
      references.value = d.references
      expiresAt.value = d.expires_at
      dirty.value = false
      status.value = 'ready'
    } catch (e) {
      error.value = e as AppError
      status.value = 'error'
      // 410 DRAFT_EXPIRED：清本地草稿，提示重新生成；**不得**用客户端 assistant 文本重建（§6.8）。
      if ((e as AppError).code === 'DRAFT_EXPIRED') clear()
    }
  }

  /** 编辑：必带 `expected_draft_version`；成功后用响应覆盖本地版本。 */
  async function revise(patch: Partial<Omit<DraftFields, never>>): Promise<void> {
    const id = draftId.value
    const version = draftVersion.value
    if (!id || version === null) return
    status.value = 'loading'
    try {
      const d = await meApi.reviseDraft(session.auth, id, { ...patch, expected_draft_version: version })
      draftVersion.value = d.draft_version
      fields.value = {
        title: d.title,
        goal: d.goal ?? null,
        start_date: d.start_date ?? null,
        end_date: d.end_date ?? null,
        content: d.content,
      }
      basisTypes.value = d.basis_types
      references.value = d.references
      dirty.value = false
      status.value = 'ready'
    } catch (e) {
      error.value = e as AppError
      status.value = 'error'
      throw e
    }
  }

  /** 保存：body 只有 `draft_version`；202 → 立即进入「待确认」，**不**显示保存成功。 */
  async function save(idempotencyKey: string): Promise<SaveOutcome> {
    const id = draftId.value
    const version = draftVersion.value
    if (!id || version === null) throw new Error('draft not bound')
    if (dirty.value) throw new Error('draft dirty: revise() first')
    const res: SaveResult = await meApi.saveDraft(session.auth, id, { draft_version: version }, idempotencyKey)
    operationId.value = res.operation_id
    if (res.status === 'deleted') {
      // 墓碑：计划已被删除，不可复活、不重新创建（§6.7）。
      planId.value = res.plan_id
      saved.value = false
      return { kind: 'deleted', operationId: res.operation_id, planId: res.plan_id }
    }
    planId.value = res.plan_id
    saved.value = true
    return res.status === 'created'
      ? { kind: 'created', operationId: res.operation_id, planId: res.plan_id }
      : { kind: 'existing', operationId: res.operation_id, planId: res.plan_id }
  }

  /** 202 落「待确认」：交给 writeOps 核实，界面**不得**显示「保存成功」。 */
  function markPending(id: string): SaveOutcome {
    writeOps.track({ operationId: id, source: 'draft-save' })
    return { kind: 'pending', operationId: id }
  }

  function clear(): void {
    draftId.value = null
    draftVersion.value = null
    operationId.value = null
    fields.value = { title: '', goal: null, start_date: null, end_date: null, content: '' }
    basisTypes.value = []
    references.value = []
    expiresAt.value = null
    saved.value = false
    planId.value = null
    dirty.value = false
    status.value = 'idle'
    error.value = null
    void ui
  }

  session.registerCleanup(clear)

  return {
    draftId,
    draftVersion,
    operationId,
    fields,
    basisTypes,
    references,
    expiresAt,
    saved,
    planId,
    dirty,
    status,
    error,
    lastRequestId,
    bind,
    load,
    revise,
    save,
    markPending,
    clear,
  }
})
