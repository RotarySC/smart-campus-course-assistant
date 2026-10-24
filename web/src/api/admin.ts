/**
 * 管理端端点封装。函数名 = `openapi` 的 `operationId`（§2.4）。
 *
 * 逐端点差异（易错，照抄 §6.13 / API-REFERENCE）：
 *   - `PATCH /admin/courses/{id}`：`expected_version` 在 **body**
 *   - `PATCH /admin/schedules/{id}`：`expected_version` 在 **body**
 *   - `DELETE /admin/schedules/{id}`：`expected_version` 在 **query**
 *   - `DELETE /admin/documents/{id}`：`expected_version` 在 **query**
 *   - `POST /admin/documents/{id}/rebuild`：`expected_version` 在 **body** + `Idempotency-Key`
 *   - `POST /admin/documents/{id}/cleanup-retry`：只有 `Idempotency-Key`
 *   - `POST /admin/document-batches`：multipart（`files` 1–10 个 + 可选 `allow_duplicate_names`）
 */

import type { AuthSnapshot, RequestOptions } from './client'
import { request } from './client'
import type {
  Batch,
  Course,
  CourseCreate,
  CoursePatch,
  Document,
  DocumentMutation,
  DocumentText,
  Page,
  Schedule,
  ScheduleCreate,
  ScheduleDelete,
  SchedulePage,
  SchedulePatch,
  StudentCreate,
  StudentPatch,
  User,
} from './types'

/* ===================== 课程 ===================== */

export function listCourses(
  auth: AuthSnapshot,
  p: { page?: number; page_size?: number; query?: string; enabled?: boolean } = {},
): Promise<Page<Course>> {
  return request<Page<Course>>({
    method: 'GET',
    path: '/admin/courses',
    query: { page: p.page, page_size: p.page_size, query: p.query, enabled: p.enabled },
    auth,
  })
}

export function createCourse(auth: AuthSnapshot, body: CourseCreate): Promise<Course> {
  return request<Course>({ method: 'POST', path: '/admin/courses', body, auth })
}

export function patchCourse(auth: AuthSnapshot, id: string, body: CoursePatch): Promise<Course> {
  return request<Course>({ method: 'PATCH', path: `/admin/courses/${encodeURIComponent(id)}`, body, auth })
}

/* ===================== 学生 ===================== */

export function listStudents(
  auth: AuthSnapshot,
  p: { page?: number; page_size?: number; query?: string; enabled?: boolean } = {},
): Promise<Page<User>> {
  return request<Page<User>>({
    method: 'GET',
    path: '/admin/students',
    query: { page: p.page, page_size: p.page_size, query: p.query, enabled: p.enabled },
    auth,
  })
}

export function createStudent(auth: AuthSnapshot, body: StudentCreate): Promise<User> {
  return request<User>({ method: 'POST', path: '/admin/students', body, auth })
}

export function patchStudent(auth: AuthSnapshot, id: string, body: StudentPatch): Promise<User> {
  return request<User>({ method: 'PATCH', path: `/admin/students/${encodeURIComponent(id)}`, body, auth })
}

/* ===================== 课表维护 ===================== */

/** `student_id` **必填**（openapi 把它列为 required query）。 */
export function adminSchedules(
  auth: AuthSnapshot,
  p: { student_id: string; page?: number; page_size?: number; from_date?: string; to_date?: string },
): Promise<SchedulePage> {
  return request<SchedulePage>({
    method: 'GET',
    path: '/admin/schedules',
    query: {
      student_id: p.student_id,
      page: p.page,
      page_size: p.page_size,
      from_date: p.from_date,
      to_date: p.to_date,
    },
    auth,
  })
}

export function createSchedule(auth: AuthSnapshot, body: ScheduleCreate): Promise<Schedule> {
  return request<Schedule>({ method: 'POST', path: '/admin/schedules', body, auth })
}

export function patchSchedule(auth: AuthSnapshot, id: string, body: SchedulePatch): Promise<Schedule> {
  return request<Schedule>({ method: 'PATCH', path: `/admin/schedules/${encodeURIComponent(id)}`, body, auth })
}

/** `expected_version` 在 **query**，不是 body。响应给 `audit_id`（仅用于回执，不拼进 URL）。 */
export function deleteSchedule(auth: AuthSnapshot, id: string, expectedVersion: number): Promise<ScheduleDelete> {
  return request<ScheduleDelete>({
    method: 'DELETE',
    path: `/admin/schedules/${encodeURIComponent(id)}`,
    query: { expected_version: expectedVersion },
    auth,
  })
}

/* ===================== 文档与批次 ===================== */

/** multipart 上传：字段名 `files`（1–10 个）+ 可选 `allow_duplicate_names`。 */
export function uploadBatch(
  auth: AuthSnapshot,
  files: File[],
  opts: { allow_duplicate_names?: boolean } = {},
): Promise<Batch> {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  if (opts.allow_duplicate_names !== undefined) form.append('allow_duplicate_names', String(opts.allow_duplicate_names))
  return request<Batch>({ method: 'POST', path: '/admin/document-batches', body: form, auth })
}

export function getBatch(auth: AuthSnapshot, batchId: string): Promise<Batch> {
  return request<Batch>({
    method: 'GET',
    path: `/admin/document-batches/${encodeURIComponent(batchId)}`,
    auth,
  })
}

export function listDocuments(
  auth: AuthSnapshot,
  p: { page?: number; page_size?: number; name?: string; state?: string } = {},
): Promise<Page<Document>> {
  return request<Page<Document>>({
    method: 'GET',
    path: '/admin/documents',
    query: { page: p.page, page_size: p.page_size, name: p.name, state: p.state },
    auth,
  })
}

export function previewDocument(
  auth: AuthSnapshot,
  id: string,
  p: { offset?: number; limit?: number } = {},
): Promise<DocumentText> {
  return request<DocumentText>({
    method: 'GET',
    path: `/admin/documents/${encodeURIComponent(id)}/text`,
    query: { offset: p.offset, limit: p.limit },
    auth,
  })
}

export function rebuildDocument(
  auth: AuthSnapshot,
  id: string,
  expectedVersion: number,
  idempotencyKey: string,
): Promise<DocumentMutation> {
  return request<DocumentMutation>({
    method: 'POST',
    path: `/admin/documents/${encodeURIComponent(id)}/rebuild`,
    body: { expected_version: expectedVersion },
    idempotencyKey,
    auth,
  })
}

/** `expected_version` 在 **query**。 */
export function deleteDocument(auth: AuthSnapshot, id: string, expectedVersion: number): Promise<DocumentMutation> {
  return request<DocumentMutation>({
    method: 'DELETE',
    path: `/admin/documents/${encodeURIComponent(id)}`,
    query: { expected_version: expectedVersion },
    auth,
  })
}

export function retryCleanup(auth: AuthSnapshot, id: string, idempotencyKey: string): Promise<DocumentMutation> {
  return request<DocumentMutation>({
    method: 'POST',
    path: `/admin/documents/${encodeURIComponent(id)}/cleanup-retry`,
    idempotencyKey,
    auth,
  })
}

export type { RequestOptions }
