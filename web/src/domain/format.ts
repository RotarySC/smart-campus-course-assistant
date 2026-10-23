/**
 * 日期/时间/尺寸格式化。纯函数（§2.2 R1）。
 *
 * 两条口径：
 *   1. 长度一律按 **Unicode 码点**计数（SRS DR-001「字符串上限按 Unicode 码点计数」）→ `codePointLength`。
 *   2. 日期展示用 `schoolTimezone`，**不用浏览器时区**，时间不加时区偏移（SRS DR-002）。
 *      因此本文件对 `YYYY-MM-DD` 一律用 `Date.UTC` 算星期，绝不 `new Date('2026-10-22')`
 *      （那会按本地时区解析，UTC-x 机器上会退回前一天）。
 */

const WEEKDAYS_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'] as const

/** Unicode 码点长度（不是 UTF-16 code unit 长度）。 */
export function codePointLength(s: string): number {
  return [...s].length
}

interface Ymd {
  y: number
  m: number
  d: number
}

function parseYmd(date: string): Ymd | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date)
  if (!m) return null
  return { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) }
}

/** `2026-10-22` → `周四`。非法输入返回空串（调用方负责不展示）。 */
export function weekdayZh(date: string): string {
  const p = parseYmd(date)
  if (!p) return ''
  const dow = new Date(Date.UTC(p.y, p.m - 1, p.d)).getUTCDay()
  return WEEKDAYS_ZH[dow] ?? ''
}

/** `2026-10-22` → `2026-10-22（周四）`（content-spec:122 的日期形态）。 */
export function formatDateWithWeekday(date: string): string {
  const w = weekdayZh(date)
  return w ? `${date}（${w}）` : date
}

/** `08:00` + `09:40` → `08:00–09:40`（U+2013 en dash，content-spec:116 的形态）。 */
export function formatTimeRange(start: string, end: string): string {
  return `${start}–${end}`
}

/** ISO date-time → `2026-10-21 17:20`；不显示秒，不转时区。 */
export function formatDateTime(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(iso)
  if (!m) return iso
  return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}`
}

/** 计划覆盖日期：两端都空 → `未设置日期`（content-spec:132）。 */
export function formatDateRange(start: string | null | undefined, end: string | null | undefined, noDates: string): string {
  if (!start && !end) return noDates
  return `${start ?? ''} → ${end ?? ''}`.trim()
}

/** 字节数 → `2.4 MiB`（content-spec:154–158 的形态；1024 进制）。 */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return ''
  const mib = bytes / (1024 * 1024)
  if (mib >= 1) return `${mib.toFixed(1)} MiB`
  const kib = bytes / 1024
  return `${kib.toFixed(1)} KiB`
}

/** 文件类型 → 展示名（content-spec:154–158 用「PDF（含文字层）」这类形态）。 */
export function formatFileType(t: 'txt' | 'md' | 'pdf' | 'docx', hasTextLayer = true): string {
  switch (t) {
    case 'txt':
      return 'TXT'
    case 'md':
      return 'MD'
    case 'pdf':
      return hasTextLayer ? 'PDF（含文字层）' : 'PDF（无文字层）'
    case 'docx':
      return 'DOCX'
  }
}

/** `plan_7Q2F9K` → `已保存 · 计划编号 plan_7Q2F9K`（content-spec:107 的逐字形态）。 */
export function formatSavedPlanLabel(prefix: string, planId: string): string {
  return `${prefix} ${planId}`
}

/** 用 `{k}` 占位符填充模板；缺值原样保留占位符以便被不变量脚本发现。 */
export function fill(template: string, vars: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (whole, key: string) => vars[key] ?? whole)
}
