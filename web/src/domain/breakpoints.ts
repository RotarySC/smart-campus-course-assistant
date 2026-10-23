/**
 * 断点工程常量。**唯一真源是 `design/system/tokens.json` 的 `breakpoint` 表**，
 * 经 `design/system/generate.py` 产出 `design/system/tokens.ts`，
 * 再由 `scripts/sync-tokens.mjs` 逐字节同步到 `src/styles/tokens.ts`。
 *
 * §8.3 明文要求：JS 侧 `import { breakpoints } from '@/styles/tokens'` 驱动 `matchMedia`，
 * 且「只在 `ui` store 里维护当前档位一个值，组件不得各自 addEventListener('resize')」。
 * 因此本文件只做形状转换，不复制任何数值。
 */

import { breakpoints } from '@/styles/tokens'

export type BreakpointName = keyof typeof breakpoints

export interface BreakpointRange {
  /** `min-width` 档位；`base` 无媒体查询故为 `null`。 */
  min: number | null
  /** `max-width` 档**只允许写 min-width 档 − 1**（design/system/README.md 纯度规则 5）。 */
  max: number | null
}

/** 6 档，mobile-first；`base` 无下界。 */
export const BP: Record<BreakpointName, BreakpointRange> = {
  base: { min: null, max: null },
  xs: { min: breakpoints.xs, max: breakpoints.xs - 1 },
  sm: { min: breakpoints.sm, max: breakpoints.sm - 1 },
  md: { min: breakpoints.md, max: breakpoints.md - 1 },
  lg: { min: breakpoints.lg, max: breakpoints.lg - 1 },
  xl: { min: breakpoints.xl, max: breakpoints.xl - 1 },
}

/** 有下界的档位，升序（供 matchMedia 逐档判定）。 */
export const BP_ORDERED: Array<{ name: Exclude<BreakpointName, 'base'>; min: number }> = (
  ['xs', 'sm', 'md', 'lg', 'xl'] as const
).map((name) => ({ name, min: BP[name].min as number }))

/** 断言：档位表与 tokens 真源一致（供 scripts/invariants.mjs 之外的就地自检）。 */
export function assertBreakpointsMatchTokens(): void {
  const expect = [0, 480, 768, 1024, 1200, 1440]
  const actual = [breakpoints.base, breakpoints.xs, breakpoints.sm, breakpoints.md, breakpoints.lg, breakpoints.xl]
  if (actual.join(',') !== expect.join(',')) {
    throw new Error(`断点表与契约不一致：期望 ${expect.join(',')}，实际 ${actual.join(',')}`)
  }
}
