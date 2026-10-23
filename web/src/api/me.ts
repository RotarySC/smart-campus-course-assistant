/**
 * `/me/*` 端点封装（身份 / 课表 / 计划 / 草稿 / 写操作核实）。
 * 函数名 = `openapi` 的 `operationId`（§2.4）。
 *
 * 并发控制字段的位置**逐端点不同**（§6.13 三条硬规则，最易写错）：
 *   - 计划更新：`expected_version` 在 **body**
 *   - 计划删除：`expected_version` 在 **query**
 *   - 草稿编辑：`expected_draft_version` 在 **body**（**不得**与计划的字段混用）
 *   - 草稿保存：body 只有 `draft_version`
 */

import type { AuthSnapshot, RequestOptions } from './client'
import { request } from './client'
import type {
  Draft,
  DraftPatch,
  DraftSave,
  Me,
  Plan,
  PlanCreate,
  PlanPage,
  PlanPatch,
  SaveResult,
  SchedulePage,
  WriteOperation,
} from './types.gen'

/** `GET /api/v1/me`（operationId `getMe`） */
export function getMe(auth: AuthSnapshot): Promise<Me> {
  return request<Me>({ method: 'GET', path: '/me', auth })
}

/** `GET /api/v1/me/schedules`（operationId `mySchedules`） */
export function mySchedules(
  auth: AuthSnapshot,
  p: { page?: number; page_size?: number; from_date?: string; to_date?: string } = {},
  signal?: AbortSignal,
): Promise<SchedulePage> {
  const o: RequestOptions = {
    method: 'GET',
    path: '/me/schedules',
    query: { page: p.page, page_size: p.page_size, from_date: p.from_date, to_date: p.to_date },
    auth,
  }
  if (signal) o.signal = signal
  return request<SchedulePage>(o)
}

/* ===================== 计划 ===================== */

/** `GET /api/v1/me/plans`（operationId `listPlans`） */
export function listPlans(
  auth: AuthSnapshot,
  p: { page?: number; page_size?: number; title?: string } = {},
): Promise<PlanPage> {
  return request<PlanPage>({
    method: 'GET',
    path: '/me/plans',
    query: { page: p.page, page_size: p.page_size, title: p.title },
    auth,
  })
}

/** `GET /api/v1/me/plans/{id}`（operationId `getPlan`） */
export function getPlan(auth: AuthSnapshot, id: string): Promise<Plan> {
  return request<Plan>({ method: 'GET', path: `/me/plans/${encodeURIComponent(id)}`, auth })
}

/** `POST /api/v1/me/plans`（operationId `createPlan`）—— 必须带 `Idempotency-Key`。 */
export function createPlan(auth: AuthSnapshot, body: PlanCreate, idempotencyKey: string): Promise<SaveResult> {
  return request<SaveResult>({ method: 'POST', path: '/me/plans', body, idempotencyKey, auth })
}

/** `PATCH /api/v1/me/plans/{id}`（operationId `patchPlan`）—— body 必带 `expected_version`。 */
export function patchPlan(auth: AuthSnapshot, id: string, body: PlanPatch): Promise<Plan> {
  return request<Plan>({ method: 'PATCH', path: `/me/plans/${encodeURIComponent(id)}`, body, auth })
}

/** `DELETE /api/v1/me/plans/{id}`（operationId `deletePlan`）—— **query** 参数 `expected_version`。 */
export function deletePlan(auth: AuthSnapshot, id: string, expectedVersion: number): Promise<Record<string, never>> {
  return request<Record<string, never>>({
    method: 'DELETE',
    path: `/me/plans/${encodeURIComponent(id)}`,
    query: { expected_version: expectedVersion },
    auth,
  })
}

/* ===================== 草稿 ===================== */

/** `GET /api/v1/me/drafts/{draft_id}`（operationId `getDraft`） */
export function getDraft(auth: AuthSnapshot, draftId: string): Promise<Draft> {
  return request<Draft>({ method: 'GET', path: `/me/drafts/${encodeURIComponent(draftId)}`, auth })
}

/** `PATCH /api/v1/me/drafts/{draft_id}`（operationId `reviseDraft`）—— body 必带 `expected_draft_version`。 */
export function reviseDraft(auth: AuthSnapshot, draftId: string, body: DraftPatch): Promise<Draft> {
  return request<Draft>({ method: 'PATCH', path: `/me/drafts/${encodeURIComponent(draftId)}`, body, auth })
}

/** `POST /api/v1/me/drafts/{draft_id}/save`（operationId `saveDraft`）—— 必须带 `Idempotency-Key`。 */
export function saveDraft(
  auth: AuthSnapshot,
  draftId: string,
  body: DraftSave,
  idempotencyKey: string,
): Promise<SaveResult> {
  return request<SaveResult>({
    method: 'POST',
    path: `/me/drafts/${encodeURIComponent(draftId)}/save`,
    body,
    idempotencyKey,
    auth,
  })
}

/* ===================== 写操作核实 ===================== */

/** `GET /api/v1/me/write-operations/{operation_id}`（operationId `getWriteOperation`） */
export function getWriteOperation(auth: AuthSnapshot, operationId: string): Promise<WriteOperation> {
  return request<WriteOperation>({
    method: 'GET',
    path: `/me/write-operations/${encodeURIComponent(operationId)}`,
    auth,
  })
}
