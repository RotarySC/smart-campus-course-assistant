/**
 * mock 的 HTTP 处理器：**同源 `/api/v1` 路径**，返回真正的 `Response`
 * （含 `{ request_id, error: { code, message } }` 形态的错误信封）。
 *
 * 不产生任何外部请求；所有响应都带 `{ request_id, data }` 信封（NFR-OBS-001）。
 * 错误码只用 `openapi` 的 `Error.code` 枚举值（不发明码）。
 */

import type { SyncErrorCode } from '@/domain/constants'
import type {
  Batch,
  Course,
  Draft,
  Plan,
  SaveResult,
  Schedule,
  SchedulePage,
  WriteOperation,
} from '../types'
import { createChatResponse, buildScript } from './sse'
import {
  MOCK_SCHEDULE_FAIL_DATE,
  MOCK_TODAY,
  MOCK_TIMEZONE,
  batches,
  courses,
  documents,
  drafts,
  meOf,
  plans,
  references,
  schedules,
  sessions,
  users,
  writeOperations,
} from './db'

let seq = 0
const rid = (): string => `req_mock_${String(++seq).padStart(6, '0')}`
let opSeq = 0
const opId = (): string => `op_mock_${String(++opSeq).padStart(4, '0')}`
let planSeq = 100
const planId = (): string => `plan_${planSeq++}`


function ok<T>(data: T): Response {
  return json(200, { request_id: rid(), data })
}

function created<T>(data: T): Response {
  return json(201, { request_id: rid(), data })
}

function accepted<T>(data: T): Response {
  return json(202, { request_id: rid(), data })
}

function fail(
  status: number,
  code: SyncErrorCode | string,
  message: string,
  extra?: { field_errors?: Array<{ field: string; reason: string }>; details?: unknown },
): Response {
  return json(status, {
    request_id: rid(),
    error: { code, message, ...(extra ?? {}) },
  })
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  })
}

function unauthorized(): Response {
  return fail(401, 'AUTH_REQUIRED', 'no session')
}

/** 从 Authorization 头解析出当前用户（mock 侧同样「令牌只在内存」）。 */
function currentUser(init: RequestInit): (typeof users)[number] | null {
  const h = new Headers(init.headers)
  const auth = h.get('Authorization')
  if (!auth) return null
  const token = auth.replace(/^Bearer\s+/i, '')
  const uid = sessions.get(token)
  if (!uid) return null
  return users.find((u) => u.id === uid) ?? null
}

function requireAdmin(init: RequestInit): Response | null {
  const u = currentUser(init)
  if (!u) return unauthorized()
  if (u.role !== 'admin') return fail(403, 'FORBIDDEN', 'not admin')
  return null
}

function body<T>(init: RequestInit): T {
  if (typeof init.body !== 'string') return {} as T
  try {
    return JSON.parse(init.body) as T
  } catch {
    return {} as T
  }
}

function paged<T>(items: T[], page: number, pageSize: number) {
  const start = (page - 1) * pageSize
  return { items: items.slice(start, start + pageSize), page, page_size: pageSize, total: items.length }
}

function isoNow(): string {
  return '2026-10-22T10:05:00+08:00'
}

/* =========================================================================
   主入口
   ========================================================================= */
export async function handleMock(rawUrl: string, init: RequestInit): Promise<Response> {
  const url = new URL(rawUrl, 'http://mock.local')
  const path = url.pathname.replace(/^\/api\/v1/, '')
  const method = (init.method ?? 'GET').toUpperCase()
  const q = url.searchParams
  const signal = init.signal ?? null

  /* ---------------- 鉴权 ---------------- */
  if (method === 'POST' && path === '/auth/login') {
    const b = body<{ account?: string; password?: string }>(init)
    const account = (b.account ?? '').trim()
    const password = b.password ?? ''
    if (account.length < 3 || account.length > 64 || password.length < 1) {
      return fail(422, 'VALIDATION_FAILED', 'invalid login payload', {
        field_errors: [{ field: 'account', reason: '账号长度需在 3 到 64 个字符之间。' }],
      })
    }
    const u = users.find((x) => x.account === account)
    // 统一失败文案：不区分「账号不存在」与「密码错误」（SRS FR-AUTH-001）。
    if (!u || u.password !== password) return fail(401, 'AUTH_REQUIRED', 'invalid credentials')
    if (!u.enabled) return fail(403, 'FORBIDDEN', 'account disabled')
    const token = `tok_${u.id}_${Date.now().toString(36)}`
    sessions.set(token, u.id)
    return ok({
      access_token: token,
      token_type: 'Bearer',
      expires_at: '2026-10-22T21:47:00+08:00',
      user: { id: u.id, account: u.account, display_name: u.display_name, role: u.role, enabled: u.enabled, version: u.version },
    })
  }

  if (method === 'POST' && path === '/auth/logout') {
    const h = new Headers(init.headers)
    const token = (h.get('Authorization') ?? '').replace(/^Bearer\s+/i, '')
    if (token) sessions.delete(token)
    return ok({})
  }

  if (method === 'GET' && path === '/me') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    return ok(meOf(u))
  }

  /* ---------------- 我的课表 ---------------- */
  if (method === 'GET' && path === '/me/schedules') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const from = q.get('from_date') ?? MOCK_TODAY
    const to = q.get('to_date') ?? from
    // S08 ②：服务异常必须返回错误，**不得**返回空集合（SRS INV-05 / FR-SCH-001）。
    if (from === MOCK_SCHEDULE_FAIL_DATE && to === MOCK_SCHEDULE_FAIL_DATE) {
      return fail(503, 'RETRIEVAL_UNAVAILABLE', 'schedule source down')
    }
    const items = schedules
      .filter((s) => s.student_id === u.id && s.class_date >= from && s.class_date <= to)
      .sort((a, b) => (a.class_date + a.start_time + a.id).localeCompare(b.class_date + b.start_time + b.id))
    const page: SchedulePage = {
      ...paged(items, Number(q.get('page') ?? 1), Number(q.get('page_size') ?? 50)),
      from_date: from,
      to_date: to,
      school_timezone: MOCK_TIMEZONE,
    }
    return ok(page)
  }

  /* ---------------- 计划 ---------------- */
  if (path === '/me/plans' && method === 'GET') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const title = (q.get('title') ?? '').trim()
    const items = plans.filter((p) => (title ? p.title.includes(title) : true))
    return ok(paged(items, Number(q.get('page') ?? 1), Number(q.get('page_size') ?? 20)))
  }

  if (path === '/me/plans' && method === 'POST') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const b = body<Partial<Plan>>(init)
    const title = (b.title ?? '').trim()
    if (title.length === 0 || title.length > 100) {
      return fail(422, 'VALIDATION_FAILED', 'invalid plan', {
        field_errors: [{ field: 'title', reason: '标题长度需在 1 到 100 个字符之间。' }],
      })
    }
    if ((b.content ?? '').trim().length === 0) {
      return fail(422, 'VALIDATION_FAILED', 'invalid plan', {
        field_errors: [{ field: 'content', reason: '正文长度需在 1 到 10000 个字符之间。' }],
      })
    }
    const id = planId()
    const now = isoNow()
    const p: Plan = {
      id,
      title,
      goal: b.goal ?? null,
      start_date: b.start_date ?? null,
      end_date: b.end_date ?? null,
      content: b.content ?? '',
      // source 不可由请求体决定（SRS IF-005：手动创建不接受 source=assistant）。
      source: 'manual',
      basis_types: ['general'],
      references: [],
      version: 1,
      created_at: now,
      updated_at: now,
    }
    plans.unshift(p)
    const operation: WriteOperation = {
      operation_id: opId(),
      state: 'succeeded',
      resolution: 'confirmed',
      plan_id: id,
      retryable: false,
    }
    writeOperations[operation.operation_id] = operation
    const result: SaveResult = { status: 'created', operation_id: operation.operation_id, plan_id: id }
    return created(result)
  }

  const planMatch = /^\/me\/plans\/([^/]+)$/.exec(path)
  if (planMatch) {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const id = decodeURIComponent(planMatch[1] ?? '')
    const idx = plans.findIndex((p) => p.id === id)
    if (idx === -1) return fail(404, 'RESOURCE_NOT_FOUND', 'plan not found')
    const target = plans[idx] as Plan

    if (method === 'GET') return ok(target)

    if (method === 'PATCH') {
      const b = body<Partial<Plan> & { expected_version?: number }>(init)
      if (b.expected_version !== target.version) {
        return fail(409, 'VERSION_CONFLICT', 'version mismatch', {
          details: { plan_id: target.id, state: 'succeeded', retryable: false },
        })
      }
      const next: Plan = {
        ...target,
        title: b.title ?? target.title,
        goal: b.goal === undefined ? target.goal : b.goal,
        start_date: b.start_date === undefined ? target.start_date : b.start_date,
        end_date: b.end_date === undefined ? target.end_date : b.end_date,
        content: b.content ?? target.content,
        version: target.version + 1,
        updated_at: isoNow(),
      }
      plans[idx] = next
      return ok(next)
    }

    if (method === 'DELETE') {
      // 计划的 expected_version 是 **query** 参数（§6.13）。
      const expected = Number(q.get('expected_version'))
      if (expected !== target.version) return fail(409, 'VERSION_CONFLICT', 'version mismatch')
      plans.splice(idx, 1)
      return ok({})
    }
  }

  /* ---------------- 草稿 ---------------- */
  const draftMatch = /^\/me\/drafts\/([^/]+)$/.exec(path)
  const draftSaveMatch = /^\/me\/drafts\/([^/]+)\/save$/.exec(path)

  if (draftMatch && method === 'GET') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const id = decodeURIComponent(draftMatch[1] ?? '')
    const d = drafts[id]
    if (!d) return fail(410, 'DRAFT_EXPIRED', 'draft expired')
    return ok(d)
  }

  if (draftMatch && method === 'PATCH') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const id = decodeURIComponent(draftMatch[1] ?? '')
    const d = drafts[id]
    if (!d) return fail(410, 'DRAFT_EXPIRED', 'draft expired')
    const b = body<Partial<Draft> & { expected_draft_version?: number }>(init)
    if (b.expected_draft_version !== d.draft_version) {
      return fail(409, 'VERSION_CONFLICT', 'draft version mismatch')
    }
    const next: Draft = {
      ...d,
      title: b.title ?? d.title,
      goal: b.goal === undefined ? d.goal : b.goal,
      start_date: b.start_date === undefined ? d.start_date : b.start_date,
      end_date: b.end_date === undefined ? d.end_date : b.end_date,
      content: b.content ?? d.content,
      draft_version: d.draft_version + 1,
    }
    drafts[id] = next
    return ok(next)
  }

  if (draftSaveMatch && method === 'POST') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const id = decodeURIComponent(draftSaveMatch[1] ?? '')
    const d = drafts[id]
    if (!d) return fail(410, 'DRAFT_EXPIRED', 'draft expired')
    const b = body<{ draft_version?: number }>(init)
    if (b.draft_version !== d.draft_version) return fail(409, 'VERSION_CONFLICT', 'draft version mismatch')
    const newPlanId = planId()
    const now = isoNow()
    plans.unshift({
      id: newPlanId,
      title: d.title,
      goal: d.goal ?? null,
      start_date: d.start_date ?? null,
      end_date: d.end_date ?? null,
      content: d.content,
      source: 'assistant',
      basis_types: d.basis_types,
      references: d.references,
      version: 1,
      created_at: now,
      updated_at: now,
    })
    const operation: WriteOperation = {
      operation_id: d.operation_id,
      state: 'succeeded',
      resolution: 'confirmed',
      plan_id: newPlanId,
      retryable: false,
    }
    writeOperations[operation.operation_id] = operation
    return created<SaveResult>({ status: 'created', operation_id: d.operation_id, plan_id: newPlanId })
  }

  /* ---------------- 写操作核实 ---------------- */
  const woMatch = /^\/me\/write-operations\/([^/]+)$/.exec(path)
  if (woMatch && method === 'GET') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const id = decodeURIComponent(woMatch[1] ?? '')
    const op = writeOperations[id]
    if (!op) {
      // 未登记的 operation：先给 pending/confirmed，第 2 次查询起给 succeeded，
      // 用来演示 §6.9 的轮询到终态即停。
      const attempt = (pendingAttempts.get(id) ?? 0) + 1
      pendingAttempts.set(id, attempt)
      if (attempt < 2) {
        const p: WriteOperation = { operation_id: id, state: 'pending', resolution: 'confirmed', retryable: false }
        writeOperations[id] = p
        return ok(p)
      }
      const done: WriteOperation = {
        operation_id: id,
        state: 'succeeded',
        resolution: 'confirmed',
        plan_id: 'plan_7Q2F9K',
        retryable: false,
      }
      writeOperations[id] = done
      return ok(done)
    }
    return ok(op)
  }

  /* ---------------- 对话 ---------------- */
  if (path === '/chat/stream' && method === 'POST') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const b = body<{ client_request_id?: string; conversation_id?: string; message?: string }>(init)
    const requestId = `req_${(b.client_request_id ?? rid()).replace(/[^A-Za-z0-9_-]/g, '')}`.slice(0, 64)
    const conversationId = b.conversation_id ?? `conv_${Date.now().toString(36)}`
    const script = buildScript(b.message ?? '', requestId, conversationId)
    return createChatResponse(script, signal)
  }

  const chatStateMatch = /^\/chat\/requests\/([^/]+)$/.exec(path)
  if (chatStateMatch && method === 'GET') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const requestId = decodeURIComponent(chatStateMatch[1] ?? '')
    // 只读核实，不改服务端（§6.5）。
    return ok({
      request_id: requestId,
      conversation_id: 'conv_mock_1',
      state: 'succeeded',
      cancel_requested: false,
      accepted_at: '2026-10-22T10:05:00+08:00',
      finished_at: '2026-10-22T10:05:06+08:00',
      model_calls: 1,
      tool_calls: 2,
      plan_id: 'plan_7Q2F9K',
    })
  }

  const cancelMatch = /^\/chat\/requests\/([^/]+)\/cancel$/.exec(path)
  if (cancelMatch && method === 'POST') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    return ok({})
  }

  /* ---------------- 引用 ---------------- */
  const citeMatch = /^\/citations\/([^/]+)$/.exec(path)
  if (citeMatch && method === 'GET') {
    const u = currentUser(init)
    if (!u) return unauthorized()
    const id = decodeURIComponent(citeMatch[1] ?? '')
    const ref = references[id]
    if (!ref) return fail(410, 'CITATION_UNAVAILABLE', 'citation gone')
    if (id === 'ref_gone_001') return fail(410, 'CITATION_UNAVAILABLE', 'citation gone')
    return ok({
      reference: ref,
      text: '实验前须完成预习并提交预习报告，报告不少于 500 字……',
    })
  }

  /* ---------------- 管理端：课程 ---------------- */
  if (path === '/admin/courses' && method === 'GET') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const query = (q.get('query') ?? '').trim()
    const enabled = q.get('enabled')
    const items = courses.filter(
      (c) =>
        (query ? c.code.includes(query) || c.name.includes(query) : true) &&
        (enabled === null ? true : String(c.enabled) === enabled),
    )
    return ok(paged(items, Number(q.get('page') ?? 1), Number(q.get('page_size') ?? 20)))
  }

  if (path === '/admin/courses' && method === 'POST') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const b = body<Partial<Course>>(init)
    const code = (b.code ?? '').trim()
    if (courses.some((c) => c.code === code)) {
      return fail(409, 'DUPLICATE_COURSE', 'duplicate course code', {
        field_errors: [{ field: 'code', reason: '该课程代码已存在，请更换。' }],
      })
    }
    const c: Course = {
      id: `c_${code.toLowerCase()}`,
      code,
      name: (b.name ?? '').trim(),
      description: b.description ?? null,
      enabled: b.enabled ?? true,
      version: 1,
    }
    courses.push(c)
    return created(c)
  }

  const courseMatch = /^\/admin\/courses\/([^/]+)$/.exec(path)
  if (courseMatch && method === 'PATCH') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const id = decodeURIComponent(courseMatch[1] ?? '')
    const idx = courses.findIndex((c) => c.id === id)
    if (idx === -1) return fail(404, 'RESOURCE_NOT_FOUND', 'course not found')
    const target = courses[idx] as Course
    const b = body<Partial<Course> & { expected_version?: number }>(init)
    if (b.expected_version !== target.version) return fail(409, 'VERSION_CONFLICT', 'version mismatch')
    // CoursePatch 无 code 字段：代码创建后不可修改（SRS FR-COURSE-001）。
    const next: Course = {
      ...target,
      name: b.name ?? target.name,
      description: b.description === undefined ? target.description : b.description,
      enabled: b.enabled ?? target.enabled,
      version: target.version + 1,
    }
    courses[idx] = next
    return ok(next)
  }

  /* ---------------- 管理端：学生 ---------------- */
  if (path === '/admin/students' && method === 'GET') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const query = (q.get('query') ?? '').trim()
    const enabled = q.get('enabled')
    const items = users
      .filter((u) => u.role === 'student')
      .filter(
        (u) =>
          (query ? u.account.includes(query) || u.display_name.includes(query) : true) &&
          (enabled === null ? true : String(u.enabled) === enabled),
      )
      .map(({ password: _pw, ...u }) => u)
    return ok(paged(items, Number(q.get('page') ?? 1), Number(q.get('page_size') ?? 20)))
  }

  if (path === '/admin/students' && method === 'POST') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const b = body<{ account?: string; display_name?: string; initial_password?: string }>(init)
    const account = (b.account ?? '').trim()
    if (users.some((u) => u.account === account)) {
      return fail(409, 'DUPLICATE_ACCOUNT', 'duplicate account', {
        field_errors: [{ field: 'account', reason: '该账号已存在。' }],
      })
    }
    const u = {
      id: `u_${account}`,
      account,
      display_name: (b.display_name ?? '').trim(),
      role: 'student' as const,
      enabled: true,
      version: 1,
      password: b.initial_password ?? 'demo1234',
    }
    users.push(u)
    const { password: _pw, ...rest } = u
    return created(rest)
  }

  const studentMatch = /^\/admin\/students\/([^/]+)$/.exec(path)
  if (studentMatch && method === 'PATCH') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const id = decodeURIComponent(studentMatch[1] ?? '')
    const idx = users.findIndex((u) => u.id === id)
    if (idx === -1) return fail(404, 'RESOURCE_NOT_FOUND', 'student not found')
    const target = users[idx] as (typeof users)[number]
    const b = body<{ display_name?: string; enabled?: boolean; expected_version?: number }>(init)
    if (b.expected_version !== target.version) return fail(409, 'VERSION_CONFLICT', 'version mismatch')
    // StudentPatch 只有 display_name / enabled / expected_version（SRS IF-002）。
    const next = {
      ...target,
      display_name: b.display_name ?? target.display_name,
      enabled: b.enabled ?? target.enabled,
      version: target.version + 1,
    }
    users[idx] = next
    const { password: _pw, ...rest } = next
    return ok(rest)
  }

  /* ---------------- 管理端：课表维护 ---------------- */
  if (path === '/admin/schedules' && method === 'GET') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const studentId = q.get('student_id')
    if (!studentId) return fail(422, 'VALIDATION_FAILED', 'student_id required')
    const from = q.get('from_date') ?? MOCK_TODAY
    const to = q.get('to_date') ?? from
    const items = schedules
      .filter((s) => s.student_id === studentId && s.class_date >= from && s.class_date <= to)
      .sort((a, b) => (a.class_date + a.start_time + a.id).localeCompare(b.class_date + b.start_time + b.id))
    const page: SchedulePage = {
      ...paged(items, Number(q.get('page') ?? 1), Number(q.get('page_size') ?? 50)),
      from_date: from,
      to_date: to,
      school_timezone: MOCK_TIMEZONE,
    }
    return ok(page)
  }

  if (path === '/admin/schedules' && method === 'POST') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const b = body<Partial<Schedule> & { overlap_acknowledged?: boolean; reason?: string | null }>(init)
    const dup = schedules.find(
      (s) =>
        s.student_id === b.student_id &&
        s.class_date === b.class_date &&
        s.start_time === b.start_time &&
        s.end_time === b.end_time &&
        s.course_id === b.course_id,
    )
    // DUPLICATE_SCHEDULE 始终拒绝，不因 overlap_acknowledged 放行（SRS FR-SCH-004）。
    if (dup) return fail(409, 'DUPLICATE_SCHEDULE', 'duplicate schedule', {
      field_errors: [{ field: 'start_time', reason: '该学生在同一天已有完全相同时间段的这门课，不能重复保存。' }],
    })
    const overlaps = schedules.filter(
      (s) =>
        s.student_id === b.student_id &&
        s.class_date === b.class_date &&
        s.start_time < (b.end_time ?? '') &&
        s.end_time > (b.start_time ?? ''),
    )
    if (overlaps.length > 0 && b.overlap_acknowledged !== true) {
      return fail(409, 'SCHEDULE_OVERLAP', 'overlap', { details: { overlaps, retryable: false } })
    }
    const s: Schedule = {
      id: `sch_${Date.now().toString(36)}`,
      student_id: b.student_id ?? '',
      course_id: b.course_id ?? '',
      course_name: courses.find((c) => c.id === b.course_id)?.name ?? '',
      class_date: b.class_date ?? MOCK_TODAY,
      start_time: b.start_time ?? '00:00',
      end_time: b.end_time ?? '00:00',
      location: b.location ?? null,
      version: 1,
    }
    schedules.push(s)
    return created(s)
  }

  const schedMatch = /^\/admin\/schedules\/([^/]+)$/.exec(path)
  if (schedMatch) {
    const denied = requireAdmin(init)
    if (denied) return denied
    const id = decodeURIComponent(schedMatch[1] ?? '')
    const idx = schedules.findIndex((s) => s.id === id)
    if (idx === -1) return fail(404, 'RESOURCE_NOT_FOUND', 'schedule not found')
    const target = schedules[idx] as Schedule
    if (method === 'PATCH') {
      const b = body<Partial<Schedule> & { expected_version?: number; overlap_acknowledged?: boolean }>(init)
      if (b.expected_version !== target.version) return fail(409, 'VERSION_CONFLICT', 'version mismatch')
      const overlaps = schedules.filter(
        (s) =>
          s.id !== target.id &&
          s.student_id === target.student_id &&
          s.class_date === (b.class_date ?? target.class_date) &&
          s.start_time < (b.end_time ?? target.end_time) &&
          s.end_time > (b.start_time ?? target.start_time),
      )
      if (overlaps.length > 0 && b.overlap_acknowledged !== true) {
        return fail(409, 'SCHEDULE_OVERLAP', 'overlap', { details: { overlaps, retryable: false } })
      }
      const next: Schedule = { ...target, ...b, version: target.version + 1 }
      schedules[idx] = next
      return ok(next)
    }
    if (method === 'DELETE') {
      // 课表删除的 expected_version 在 **query**。
      const expected = Number(q.get('expected_version'))
      if (expected !== target.version) return fail(409, 'VERSION_CONFLICT', 'version mismatch')
      schedules.splice(idx, 1)
      return ok({ schedule_id: target.id, audit_id: `audit_${target.id}` })
    }
  }

  /* ---------------- 管理端：文档与批次 ---------------- */
  if (path === '/admin/documents' && method === 'GET') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const name = (q.get('name') ?? '').trim()
    const state = q.get('state')
    const items = documents
      .filter((d) => d.processing_state !== 'deleted')
      .filter((d) => (name ? d.original_name.includes(name) : true))
      .filter((d) => (state ? d.processing_state === state : true))
    return ok(paged(items, Number(q.get('page') ?? 1), Number(q.get('page_size') ?? 20)))
  }

  const docTextMatch = /^\/admin\/documents\/([^/]+)\/text$/.exec(path)
  if (docTextMatch && method === 'GET') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const id = decodeURIComponent(docTextMatch[1] ?? '')
    const doc = documents.find((d) => d.id === id)
    if (!doc) return fail(404, 'RESOURCE_NOT_FOUND', 'document not found')
    return ok({
      document_id: doc.id,
      version_id: 'ver_lab_2026_3',
      offset: 0,
      next_offset: null,
      text: '实验前须完成预习并提交预习报告，报告不少于 500 字……',
    })
  }

  const docRebuildMatch = /^\/admin\/documents\/([^/]+)\/rebuild$/.exec(path)
  if (docRebuildMatch && method === 'POST') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const id = decodeURIComponent(docRebuildMatch[1] ?? '')
    const doc = documents.find((d) => d.id === id)
    if (!doc) return fail(404, 'RESOURCE_NOT_FOUND', 'document not found')
    doc.processing_state = 'rebuilding'
    doc.version += 1
    return accepted({
      document_id: doc.id,
      visibility: doc.visibility,
      task: { task_id: `task_rebuild_${doc.id}`, state: 'processing', retryable: true },
      version: doc.version,
    })
  }

  const docCleanupMatch = /^\/admin\/documents\/([^/]+)\/cleanup-retry$/.exec(path)
  if (docCleanupMatch && method === 'POST') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const id = decodeURIComponent(docCleanupMatch[1] ?? '')
    const doc = documents.find((d) => d.id === id)
    if (!doc) return fail(404, 'RESOURCE_NOT_FOUND', 'document not found')
    doc.processing_state = 'deleting'
    doc.cleanup_state = 'running'
    doc.version += 1
    return accepted({
      document_id: doc.id,
      visibility: doc.visibility,
      task: { task_id: `task_cleanup_${doc.id}`, state: 'running', retryable: true },
      version: doc.version,
    })
  }

  const docMatch = /^\/admin\/documents\/([^/]+)$/.exec(path)
  if (docMatch && method === 'DELETE') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const id = decodeURIComponent(docMatch[1] ?? '')
    const doc = documents.find((d) => d.id === id)
    if (!doc) return fail(404, 'RESOURCE_NOT_FOUND', 'document not found')
    const expected = Number(q.get('expected_version'))
    if (expected !== doc.version) return fail(409, 'VERSION_CONFLICT', 'version mismatch')
    doc.processing_state = 'deleting'
    doc.visibility = 'removed'
    doc.version += 1
    return accepted({
      document_id: doc.id,
      visibility: doc.visibility,
      task: { task_id: `task_delete_${doc.id}`, state: 'running', retryable: true },
      version: doc.version,
    })
  }

  if (path === '/admin/document-batches' && method === 'POST') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const b: Batch = {
      batch_id: `batch_${Date.now().toString(36)}`,
      state: 'accepted',
      published: false,
      documents: [],
      tasks: [{ task_id: `task_${Date.now().toString(36)}`, state: 'pending', retryable: false }],
    }
    batches.push(b)
    return accepted(b)
  }

  const batchMatch = /^\/admin\/document-batches\/([^/]+)$/.exec(path)
  if (batchMatch && method === 'GET') {
    const denied = requireAdmin(init)
    if (denied) return denied
    const id = decodeURIComponent(batchMatch[1] ?? '')
    const b = batches.find((x) => x.batch_id === id)
    if (!b) return fail(404, 'RESOURCE_NOT_FOUND', 'batch not found')
    return ok(b)
  }

  return fail(404, 'RESOURCE_NOT_FOUND', `mock 未实现该端点：${method} ${path}`)
}

/** §6.9 核实轮询的演示计数：同一 operation 第二次查询才落定。 */
const pendingAttempts = new Map<string, number>()
