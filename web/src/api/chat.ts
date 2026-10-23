/**
 * 对话端点封装（含流式）。函数名 = `openapi` 的 `operationId`（§2.4）。
 *
 * `POST /chat/stream` **没有 `Idempotency-Key` 头**（§6.3）：重复提交靠 body 的
 * `client_request_id` 去重（SRS FR-CHAT-001）。
 */

import type { AuthSnapshot } from './client'
import { request } from './client'
import type { ChatInput, ChatState } from './types.gen'

/** `GET /api/v1/chat/requests/{request_id}`（operationId `getChatState`） */
export function getChatState(auth: AuthSnapshot, requestId: string): Promise<ChatState> {
  return request<ChatState>({
    method: 'GET',
    path: `/chat/requests/${encodeURIComponent(requestId)}`,
    auth,
  })
}

/** `POST /api/v1/chat/requests/{request_id}/cancel`（operationId `cancelChat`） */
export function cancelChat(auth: AuthSnapshot, requestId: string): Promise<Record<string, never>> {
  return request<Record<string, never>>({
    method: 'POST',
    path: `/chat/requests/${encodeURIComponent(requestId)}/cancel`,
    auth,
  })
}

export type { ChatInput }
