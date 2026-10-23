/**
 * 传输层抽象：把「怎么发请求」与「请求长什么样」分开。
 *
 * 为什么需要它（而不是像正式实现那样直接 `fetch`）：
 *   阶段 B 明确「mock 数据，不接真实后端」，但**不接后端 ≠ 不跑真实代码路径**。
 *   因此这里把 `fetch` 换成一个可替换的 transport：
 *     - `httpTransport` 用原生 `fetch`（生产路径，§1.2 锁定「原生 fetch，不引 axios」）；
 *     - `mockTransport` 返回**真正的 `Response` 对象**（含 `ReadableStream` body），
 *       于是 `client.ts` 的信封解包、`sse/stream.ts` 的 `getReader()`、
 *       `sse/parse.ts` 的字节级增量解析、`chatMachine` 的状态机**全部是真实代码**，
 *       只有最外层的「字节从哪来」被替换。
 *   这样切到真实后端只需 `setTransport(httpTransport)`，零改动其余代码。
 *
 * 硬约束：mock 也是**同源 /api/v1 路径**，不产生任何外部请求（§13/§1.2）。
 */

export interface TransportInput {
  /** 完整 URL（`VITE_API_BASE` + path + query）。 */
  url: string
  init: RequestInit
}

export type Transport = (input: TransportInput) => Promise<Response>

export const httpTransport: Transport = ({ url, init }) => fetch(url, init)

let current: Transport = httpTransport

export function setTransport(t: Transport): void {
  current = t
}

export function getTransport(): Transport {
  return current
}

/** 供 `api/client.ts` 与 `api/sse/stream.ts` 共用。 */
export function send(url: string, init: RequestInit): Promise<Response> {
  return current({ url, init })
}
