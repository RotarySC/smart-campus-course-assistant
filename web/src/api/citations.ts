/**
 * 引用端点封装。函数名 = `openapi` 的 `operationId`（§2.4）。
 *
 * 引用正文**不缓存**：每次展开都重新请求；失效引用不得被缓存展示
 * （SRS FR-QA-002、`content-spec.md` S04 引用失效态、§6.12 末行）。
 */

import type { AuthSnapshot } from './client'
import { request } from './client'
import type { Citation } from './types.gen'

/** `GET /api/v1/citations/{reference_id}`（operationId `getCitation`） */
export function getCitation(auth: AuthSnapshot, referenceId: string): Promise<Citation> {
  return request<Citation>({
    method: 'GET',
    path: `/citations/${encodeURIComponent(referenceId)}`,
    auth,
  })
}
