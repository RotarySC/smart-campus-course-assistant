/**
 * `schedules` store —— 我的课表；**两种空态必须分开**。
 *
 * 最关键的规则（SRS INV-05 / FR-SCH-001、§6.6）：
 *   - `items.length === 0 && error === null` ⇒ **成功的空**（S08 ①）；
 *   - `error !== null` ⇒ **服务异常**（S08 ②）。
 *   **禁止把错误转成空列表** —— 那会让「当天无安排」与「课表读不到」变成同一种视觉，
 *   而这两条是本项目的硬验收点（AT-06）。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as meApi from '@/api/me'
import type { AppError } from '@/api/errors'
import type { Schedule } from '@/api/types.gen'
import { useSessionStore } from './session'
import { useUiStore } from './ui'

type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

export const useSchedulesStore = defineStore('schedules', () => {
  const session = useSessionStore()
  const ui = useUiStore()

  const items = ref<Schedule[]>([])
  const page = ref(1)
  const pageSize = ref(50)
  const total = ref(0)
  const fromDate = ref<string | null>(null)
  const toDate = ref<string | null>(null)
  const schoolTimezone = ref<string | null>(null)
  const status = ref<LoadStatus>('idle')
  const error = ref<AppError | null>(null)
  const lastRequestId = ref<string | null>(null)

  /** ① 成功的空：无错误且无记录。 */
  const isEmpty = computed(() => status.value === 'ready' && items.value.length === 0 && error.value === null)
  /** ② 服务异常：与 ① 互斥，绝不合并成「暂无数据」。 */
  const hasError = computed(() => error.value !== null)

  async function fetchMine(p: { page?: number; page_size?: number; from_date?: string; to_date?: string } = {}): Promise<void> {
    status.value = 'loading'
    // 不传日期即服务端当日（学校时区）—— **前端不猜日期**，回显服务端给的 from_date/to_date。
    const query: { page?: number; page_size?: number; from_date?: string; to_date?: string } = {
      page: p.page ?? 1,
      page_size: p.page_size ?? pageSize.value,
    }
    if (p.from_date !== undefined) query.from_date = p.from_date
    if (p.to_date !== undefined) query.to_date = p.to_date
    // 「只传一端视为查询该单日」（SRS FR-SCH-001）。
    else if (p.from_date !== undefined) query.to_date = p.from_date

    try {
      const res = await meApi.mySchedules(session.auth, query)
      // 切换查询日期即**整表替换**，不做增量合并（§6.6 失效行）。
      items.value = res.items
      page.value = res.page
      pageSize.value = res.page_size
      total.value = res.total
      fromDate.value = res.from_date
      toDate.value = res.to_date
      schoolTimezone.value = res.school_timezone
      error.value = null
      status.value = 'ready'
    } catch (e) {
      // **不得**把失败写成空列表：items 保持上一次的值，error 独立表达。
      error.value = e as AppError
      status.value = 'error'
      throw e
    }
  }

  function clear(): void {
    items.value = []
    page.value = 1
    total.value = 0
    fromDate.value = null
    toDate.value = null
    schoolTimezone.value = null
    status.value = 'idle'
    error.value = null
    void ui
  }

  session.registerCleanup(clear)

  return {
    items,
    page,
    pageSize,
    total,
    fromDate,
    toDate,
    schoolTimezone,
    status,
    error,
    lastRequestId,
    isEmpty,
    hasError,
    fetchMine,
    clear,
  }
})
