/**
 * 无障碍助手（§12）。
 *
 * `live.ts`：流式文本进 live region 的**节流批量提交**。两条同时成立：
 *   - 不逐字朗读、不逐 token 触发渲染；
 *   - **流式内容绝不抢焦点**（NFR-UX-001）—— live region 只播报，不 `.focus()`。
 *
 * `focus.ts`：焦点落点与回收（`ui.focusReturnTo`）。

 * 这里不做任何路由/DOM 之外的事；两文件都在 `a11y/`，由视图与组件调用。
 */

import { LIVE_FLUSH_MS } from '@/domain/constants'

export interface LiveBuffer {
  push(text: string): void
  flush(): void
  clear(): void
  /** 供 ui store 渲染的当前播报内容。 */
  read(): string
}

/**
 * 纯内存的播报缓冲：按 `flushMs` 合并提交，终态时调用 `flush()` 一次性提交完整结论。
 * `sink` 由调用方注入（通常是 `ui.announce`），因此本模块不认识 store。
 */
export function createLiveBuffer(opts: {
  politeness: 'polite' | 'assertive'
  flushMs: number
  sink: (message: string) => void
}): LiveBuffer {
  let pending = ''
  let current = ''
  let timer: ReturnType<typeof setTimeout> | null = null

  const commit = () => {
    timer = null
    if (pending === '') return
    current = pending
    pending = ''
    opts.sink(current)
  }

  return {
    push(text: string) {
      if (text === '') return
      pending += text
      if (timer === null) timer = setTimeout(commit, opts.flushMs)
    },
    flush() {
      if (timer !== null) {
        clearTimeout(timer)
        timer = null
      }
      commit()
    },
    clear() {
      if (timer !== null) {
        clearTimeout(timer)
        timer = null
      }
      pending = ''
      current = ''
    },
    read() {
      return current
    },
  }
}

/** 默认礼貌级别：流式过程用 `polite`（`assertive` 只用于错误摘要）。 */
export const DEFAULT_LIVE_FLUSH_MS = LIVE_FLUSH_MS
