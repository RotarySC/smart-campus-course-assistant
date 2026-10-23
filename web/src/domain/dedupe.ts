/**
 * seq 去重（§5.4 表「`seq` 重复／倒退」行）。
 *
 * 判据：去重键 `k = request_id + ":" + seq`；`if (seen.has(k) || seq <= lastSeq) return`。
 * **不得用覆盖代替去重**。
 *
 * 纯函数：不碰 DOM、不碰 store、不发请求（§2.2 R1）。
 */

export type DedupeVerdict = 'accept' | 'duplicate' | 'out-of-order'

export interface SeqCarrier {
  data: { seq: number }
}

/** 生成去重键。 */
export function dedupeKey(requestId: string, seq: number): string {
  return `${requestId}:${seq}`
}

/**
 * @param seen      已接受过的去重键集合（本函数会就地写入）
 * @param lastSeq   当前去重水位线
 * @param e         候选事件（只读其 `data.seq`，因此 domain 不必 import api）
 */
export function accept(seen: Set<string>, lastSeq: number, e: SeqCarrier): DedupeVerdict {
  const seq = e.data.seq
  const key = dedupeKey(requestIdOf(e), seq)
  if (seen.has(key)) return 'duplicate'
  if (seq <= lastSeq) return 'out-of-order'
  seen.add(key)
  return 'accept'
}

function requestIdOf(e: SeqCarrier): string {
  const rid = (e as { data?: { request_id?: unknown } }).data?.request_id
  return typeof rid === 'string' ? rid : ''
}
