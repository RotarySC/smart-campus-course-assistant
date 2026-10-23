/**
 * `ui` store —— 断点、live region 文案、全局提示、焦点回收目标。
 *
 * 允许的静态依赖：**无**（§6.2 表）。它是依赖图的最底层。
 * 断点只用 6 档，且**只有这里**维护「当前档位」一个值；
 * 组件不得各自 `addEventListener('resize')`（§8.3）。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { BP } from '@/domain/breakpoints'
import type { BreakpointName } from '@/domain/breakpoints'

export interface Toast {
  id: string
  code: string
  level: 'info' | 'warn' | 'danger' | 'ok'
}

let toastSeq = 0

export const useUiStore = defineStore('ui', () => {
  const breakpoint = ref<BreakpointName>('base')
  const liveMessage = ref('')
  const toasts = ref<Toast[]>([])
  const focusReturnTo = ref<string | null>(null)

  /** 当前档位是否 ≥ 某档（供视图做行为分支；**渲染分支一律交给 CSS 媒体查询**）。 */
  const atLeast = computed(() => (name: BreakpointName) => {
    const min = BP[name].min
    if (min === null) return true
    return (BP[breakpoint.value].min ?? 0) >= min
  })

  function computeBreakpoint(width: number): BreakpointName {
    // 升序取「最后一个满足 min ≤ width」的档位。
    let current: BreakpointName = 'base'
    for (const [name, range] of Object.entries(BP) as Array<[BreakpointName, { min: number | null }]>) {
      if (range.min !== null && width >= range.min) current = name
    }
    return current
  }

  let listeners: Array<{ mql: MediaQueryList; fn: (e: MediaQueryListEvent) => void }> = []

  /** 注册 6 档 matchMedia（幂等）。 */
  function initBreakpoints(): void {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    if (listeners.length > 0) return

    const recompute = () => {
      breakpoint.value = computeBreakpoint(window.innerWidth)
    }
    for (const range of Object.values(BP)) {
      if (range.min === null) continue
      const mql = window.matchMedia(`(min-width:${range.min}px)`)
      const fn = () => recompute()
      mql.addEventListener('change', fn)
      listeners.push({ mql, fn })
    }
    recompute()
  }

  function disposeBreakpoints(): void {
    for (const { mql, fn } of listeners) mql.removeEventListener('change', fn)
    listeners = []
  }

  /** 写入 live region 文案。由 `a11y/live.ts` 节流批量调用；不播令牌/私有标识。 */
  function announce(message: string): void {
    liveMessage.value = message
  }

  function pushToast(code: string, level: Toast['level']): void {
    // 文案由 §3.4 码表给出；ui 不新增句子（§6.11）。
    toasts.value.push({ id: `t_${++toastSeq}`, code, level })
  }

  function dismissToast(id: string): void {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  function setFocusReturn(target: string | null): void {
    focusReturnTo.value = target
  }

  function clear(): void {
    liveMessage.value = ''
    toasts.value = []
    focusReturnTo.value = null
  }

  return {
    breakpoint,
    liveMessage,
    toasts,
    focusReturnTo,
    atLeast,
    initBreakpoints,
    disposeBreakpoints,
    announce,
    pushToast,
    dismissToast,
    setFocusReturn,
    clear,
  }
})
