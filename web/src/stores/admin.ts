/**
 * `admin` store —— 课程/学生/课表维护、文档与批次。
 *
 * 刷新规则（§6.10）：
 *   - 文档批次用**定时轮询** `getBatch()`（3s，进终态即停）；
 *   - 课程/学生/课表/文档列表**不轮询**，只在显式动作后失效重取。
 *
 * 并发控制的字段位置逐端点不同（§6.13）：更新走 body 的 `expected_version`，
 * 课表/文档删除走 **query**；文档变更返回 202 + `DocumentMutation`。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as adminApi from '@/api/admin'
import type { AppError } from '@/api/errors'
import type {
  Batch,
  Course,
  CourseCreate,
  CoursePatch,
  Document,
  DocumentText,
  Schedule,
  ScheduleCreate,
  SchedulePatch,
  StudentCreate,
  StudentPatch,
  User,
} from '@/api/types.gen'
import { BATCH_POLL_MS } from '@/domain/constants'
import { useSessionStore } from './session'
import { useUiStore } from './ui'

type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

interface ListState<T, F> {
  items: T[]
  page: number
  pageSize: number
  total: number
  filters: F
}

export const useAdminStore = defineStore('admin', () => {
  const session = useSessionStore()
  const ui = useUiStore()

  const courses = ref<ListState<Course, { query: string; enabled: boolean | null }>>({
    items: [],
    page: 1,
    pageSize: 20,
    total: 0,
    filters: { query: '', enabled: null },
  })
  const students = ref<ListState<User, { query: string; enabled: boolean | null }>>({
    items: [],
    page: 1,
    pageSize: 20,
    total: 0,
    filters: { query: '', enabled: null },
  })
  const schedules = ref<
    ListState<Schedule, { studentId: string | null; fromDate: string | null; toDate: string | null }>
  >({
    items: [],
    page: 1,
    pageSize: 50,
    total: 0,
    filters: { studentId: null, fromDate: null, toDate: null },
  })
  const documents = ref<ListState<Document, { name: string | null; state: string | null }>>({
    items: [],
    page: 1,
    pageSize: 20,
    total: 0,
    filters: { name: null, state: null },
  })

  const batch = ref<Batch | null>(null)
  const documentText = ref<DocumentText | null>(null)
  /** 409 `SCHEDULE_OVERLAP` 的 `error.details.overlaps`。 */
  const overlap = ref<Schedule[] | null>(null)
  const status = ref<LoadStatus>('idle')
  const error = ref<AppError | null>(null)
  const lastRequestId = ref<string | null>(null)

  let batchTimer: ReturnType<typeof setInterval> | null = null

  const coursesEmpty = computed(() => status.value === 'ready' && courses.value.items.length === 0 && error.value === null)

  /* ---------------- 课程 ---------------- */
  async function listCourses(p: { page?: number; page_size?: number; query?: string; enabled?: boolean } = {}): Promise<void> {
    status.value = 'loading'
    if (p.query !== undefined) courses.value.filters.query = p.query
    if (p.enabled !== undefined) courses.value.filters.enabled = p.enabled
    try {
      const res = await adminApi.listCourses(session.auth, {
        page: p.page ?? courses.value.page,
        page_size: p.page_size ?? courses.value.pageSize,
        query: courses.value.filters.query === '' ? undefined : courses.value.filters.query,
        enabled: courses.value.filters.enabled === null ? undefined : courses.value.filters.enabled,
      })
      courses.value.items = res.items
      courses.value.page = res.page
      courses.value.total = res.total
      error.value = null
      status.value = 'ready'
    } catch (e) {
      error.value = e as AppError
      status.value = 'error'
      throw e
    }
  }

  async function createCourse(input: CourseCreate): Promise<Course> {
    const c = await adminApi.createCourse(session.auth, input)
    await listCourses()
    return c
  }

  /** 课程代码不可改：`CoursePatch` 里根本没有 `code` 字段。 */
  async function patchCourse(id: string, input: Omit<CoursePatch, 'expected_version'>, expectedVersion: number): Promise<Course> {
    const c = await adminApi.patchCourse(session.auth, id, { ...input, expected_version: expectedVersion })
    await listCourses()
    return c
  }

  /* ---------------- 学生 ---------------- */
  async function listStudents(p: { page?: number; page_size?: number; query?: string; enabled?: boolean } = {}): Promise<void> {
    status.value = 'loading'
    if (p.query !== undefined) students.value.filters.query = p.query
    if (p.enabled !== undefined) students.value.filters.enabled = p.enabled
    try {
      const res = await adminApi.listStudents(session.auth, {
        page: p.page ?? students.value.page,
        page_size: p.page_size ?? students.value.pageSize,
        query: students.value.filters.query === '' ? undefined : students.value.filters.query,
        enabled: students.value.filters.enabled === null ? undefined : students.value.filters.enabled,
      })
      students.value.items = res.items
      students.value.page = res.page
      students.value.total = res.total
      error.value = null
      status.value = 'ready'
    } catch (e) {
      error.value = e as AppError
      status.value = 'error'
      throw e
    }
  }

  async function createStudent(input: StudentCreate): Promise<User> {
    const u = await adminApi.createStudent(session.auth, input)
    await listStudents()
    return u
  }

  async function patchStudent(id: string, input: Omit<StudentPatch, 'expected_version'>, expectedVersion: number): Promise<User> {
    const u = await adminApi.patchStudent(session.auth, id, { ...input, expected_version: expectedVersion })
    await listStudents()
    return u
  }

  /* ---------------- 课表维护 ---------------- */
  async function listAdminSchedules(p: {
    student_id: string
    page?: number
    page_size?: number
    from_date?: string
    to_date?: string
  }): Promise<void> {
    status.value = 'loading'
    schedules.value.filters.studentId = p.student_id
    try {
      const res = await adminApi.adminSchedules(session.auth, p)
      schedules.value.items = res.items
      schedules.value.page = res.page
      schedules.value.total = res.total
      schedules.value.filters.fromDate = res.from_date
      schedules.value.filters.toDate = res.to_date
      error.value = null
      status.value = 'ready'
    } catch (e) {
      error.value = e as AppError
      status.value = 'error'
      throw e
    }
  }

  async function createSchedule(input: ScheduleCreate): Promise<Schedule> {
    overlap.value = null
    try {
      const s = await adminApi.createSchedule(session.auth, input)
      await refreshScheduleList()
      return s
    } catch (e) {
      const err = e as AppError
      // 409 SCHEDULE_OVERLAP：读 error.details.overlaps 渲染冲突摘要（§6.10）。
      if (err.code === 'SCHEDULE_OVERLAP') {
        overlap.value = (err.details?.overlaps as Schedule[] | undefined) ?? []
      }
      throw e
    }
  }

  async function patchSchedule(id: string, input: Omit<SchedulePatch, 'expected_version'>, expectedVersion: number): Promise<Schedule> {
    overlap.value = null
    try {
      const s = await adminApi.patchSchedule(session.auth, id, { ...input, expected_version: expectedVersion })
      await refreshScheduleList()
      return s
    } catch (e) {
      const err = e as AppError
      if (err.code === 'SCHEDULE_OVERLAP') {
        overlap.value = (err.details?.overlaps as Schedule[] | undefined) ?? []
      }
      throw e
    }
  }

  async function deleteSchedule(id: string, expectedVersion: number): Promise<void> {
    await adminApi.deleteSchedule(session.auth, id, expectedVersion)
    await refreshScheduleList()
  }

  async function refreshScheduleList(): Promise<void> {
    const sid = schedules.value.filters.studentId
    if (!sid) return
    const p: { student_id: string; from_date?: string; to_date?: string } = { student_id: sid }
    if (schedules.value.filters.fromDate) p.from_date = schedules.value.filters.fromDate
    if (schedules.value.filters.toDate) p.to_date = schedules.value.filters.toDate
    await listAdminSchedules(p)
  }

  function clearOverlap(): void {
    overlap.value = null
  }

  /* ---------------- 文档与批次 ---------------- */
  async function listDocuments(p: { page?: number; page_size?: number; name?: string; state?: string } = {}): Promise<void> {
    status.value = 'loading'
    if (p.name !== undefined) documents.value.filters.name = p.name
    if (p.state !== undefined) documents.value.filters.state = p.state
    try {
      const res = await adminApi.listDocuments(session.auth, {
        page: p.page ?? documents.value.page,
        page_size: p.page_size ?? documents.value.pageSize,
        name: documents.value.filters.name ?? undefined,
        state: documents.value.filters.state ?? undefined,
      })
      documents.value.items = res.items
      documents.value.page = res.page
      documents.value.total = res.total
      error.value = null
      status.value = 'ready'
    } catch (e) {
      error.value = e as AppError
      status.value = 'error'
      throw e
    }
  }

  /** 上传即异步：202 只拿到 `batch_id` 与状态，进度靠轮询。 */
  async function uploadBatch(files: File[], opts: { allow_duplicate_names?: boolean } = {}): Promise<Batch> {
    const b = await adminApi.uploadBatch(session.auth, files, opts)
    batch.value = b
    startBatchPolling(b.batch_id)
    return b
  }

  async function getBatch(batchId: string): Promise<Batch> {
    const b = await adminApi.getBatch(session.auth, batchId)
    batch.value = b
    return b
  }

  /** 批次轮询：3s，进入终态 `published`/`failed` 即停（§6.10）。 */
  function startBatchPolling(batchId: string): void {
    stopBatchPolling()
    batchTimer = setInterval(() => {
      void getBatch(batchId)
        .then((b) => {
          if (b.state === 'published' || b.state === 'failed') stopBatchPolling()
        })
        .catch(() => stopBatchPolling())
    }, BATCH_POLL_MS)
  }

  function stopBatchPolling(): void {
    if (batchTimer !== null) {
      clearInterval(batchTimer)
      batchTimer = null
    }
  }

  async function previewDocumentText(id: string, p: { offset?: number; limit?: number } = {}): Promise<DocumentText> {
    documentText.value = await adminApi.previewDocument(session.auth, id, p)
    return documentText.value
  }

  async function rebuildDocument(id: string, expectedVersion: number, idempotencyKey: string): Promise<void> {
    await adminApi.rebuildDocument(session.auth, id, expectedVersion, idempotencyKey)
    await listDocuments()
  }

  async function deleteDocument(id: string, expectedVersion: number): Promise<void> {
    await adminApi.deleteDocument(session.auth, id, expectedVersion)
    await listDocuments()
  }

  async function retryCleanup(id: string, idempotencyKey: string): Promise<void> {
    await adminApi.retryCleanup(session.auth, id, idempotencyKey)
    await listDocuments()
  }

  function clear(): void {
    stopBatchPolling()
    courses.value = { items: [], page: 1, pageSize: 20, total: 0, filters: { query: '', enabled: null } }
    students.value = { items: [], page: 1, pageSize: 20, total: 0, filters: { query: '', enabled: null } }
    schedules.value = {
      items: [],
      page: 1,
      pageSize: 50,
      total: 0,
      filters: { studentId: null, fromDate: null, toDate: null },
    }
    documents.value = { items: [], page: 1, pageSize: 20, total: 0, filters: { name: null, state: null } }
    batch.value = null
    documentText.value = null
    overlap.value = null
    status.value = 'idle'
    error.value = null
    void ui
  }

  session.registerCleanup(clear)

  return {
    courses,
    students,
    schedules,
    documents,
    batch,
    documentText,
    overlap,
    status,
    error,
    lastRequestId,
    coursesEmpty,
    listCourses,
    createCourse,
    patchCourse,
    listStudents,
    createStudent,
    patchStudent,
    listAdminSchedules,
    createSchedule,
    patchSchedule,
    deleteSchedule,
    clearOverlap,
    listDocuments,
    uploadBatch,
    getBatch,
    startBatchPolling,
    stopBatchPolling,
    previewDocumentText,
    rebuildDocument,
    deleteDocument,
    retryCleanup,
    clear,
  }
})
