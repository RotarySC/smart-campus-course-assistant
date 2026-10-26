/**
 * 客户端即时校验。纯函数（§2.2 R1）。
 *
 * **本文件不产生任何用户可见句子。** 它只返回「字段 + 问题种类」，
 * 由 `domain/mapError.ts` 的 `fieldIssueText()` 把种类映射到已经冻结的逐字文案
 * （content-spec 或「必填」标记）。原因：
 *   - 前端详细设计 §4.8 明文「逐字段 `reason` 由**服务端**给出；字段级提示格式见 §11」；
 *   - CONTRACT §3.7 第 3 条 / §8.5.1 硬规则③ 禁止实现者自造文案。
 *   - §11.1 又要求「客户端即时校验只为减少一次往返，**不是权威**」，
 *     所以客户端能做的是：拦住明显不成立的提交 + 给字段打 `aria-invalid` + 就近定位；
 *     真正的 `reason` 文本走服务端 `error.field_errors[]`。
 *
 * 长度上限通过原生 `maxlength` 属性在输入侧封死（结构约束，不是文案），
 * `too-long` 只作为「绕过 maxlength（粘贴/脚本）时的兜底」；
 * 服务端 `VALIDATION_FAILED` 仍是权威。
 *
 * 所有长度按 Unicode 码点（SRS DR-001）。
 */

import { LIMITS } from './constants'
import { codePointLength } from './format'

export type IssueKind =
  | 'required'
  | 'too-long'
  | 'too-short'
  | 'mismatch'
  | 'missing-selection'
  | 'date-range'
  | 'time-range'
  | 'range-days'

export interface FieldIssue {
  field: string
  kind: IssueKind
}

export type FieldIssues = FieldIssue[]

/** 取值超出码点上限的字段名，供 UI 挂 `maxlength`（结构约束，非文案）。 */
export const MAXLEN: Record<string, number> = {
  title: LIMITS.planTitle,
  goal: LIMITS.planGoal,
  content: LIMITS.planContent,
  code: LIMITS.courseCode,
  name: LIMITS.courseName,
  description: LIMITS.courseDescription,
  location: LIMITS.scheduleLocation,
  reason: LIMITS.overlapReason,
  account: LIMITS.registerAccountMax,
  display_name: LIMITS.studentDisplayName,
  password: LIMITS.registerPasswordMax,
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const TIME_HM = /^(?:[01]\d|2[0-3]):[0-5]\d$/
/** 幂等键：`^[A-Za-z0-9._:-]+$`、≤96（§6.3，来自 openapi 的 IdempotencyKey）。 */
const IDEMPOTENCY_KEY = /^[A-Za-z0-9._:-]+$/
const IDEMPOTENCY_KEY_MAX = 96

function tooLong(field: string, value: string): FieldIssue | null {
  const max = MAXLEN[field]
  if (max === undefined) return null
  return codePointLength(value) > max ? { field, kind: 'too-long' } : null
}

/* ===================== S01 登录（openapi POST /auth/login：account/password） ===================== */
export interface LoginInput {
  account: string
  password: string
}

export function validateLogin(input: LoginInput): FieldIssues {
  const out: FieldIssues = []
  // openapi Login：account 3..64；password 1..1024
  if (input.account.trim().length === 0) out.push({ field: 'account', kind: 'required' })
  if (input.password.length === 0) out.push({ field: 'password', kind: 'required' })
  return out
}

/* ===================== S01 注册（openapi POST /auth/register：account/display_name/password） ===================== */
export interface RegisterInput {
  account: string
  display_name: string
  password: string
  /** 确认密码**只存在于表单**，不是 `RegisterInput` 的字段（openapi 里没有它）。 */
  confirm: string
}

/**
 * 客户端只为「明显不成立」把关（§11.1：减少一次往返，**不是权威**）。
 * - 账号：trim 后 3–64（与 `RegisterInput.account` 一致）
 * - 显示名：非空白 1–50
 * - 密码：8–1024（与 `RegisterInput.password` 一致）
 * - 确认密码：与密码**逐字**相等
 * 服务端 `VALIDATION_FAILED.errors[].reason` 仍是权威文案来源。
 */
export function validateRegister(input: RegisterInput): FieldIssues {
  const out: FieldIssue[] = []
  const account = input.account.trim()
  if (account.length === 0) out.push({ field: 'account', kind: 'required' })
  else if (codePointLength(account) < LIMITS.registerAccountMin) out.push({ field: 'account', kind: 'too-short' })
  if (input.display_name.trim().length === 0) out.push({ field: 'display_name', kind: 'required' })
  if (input.password.length === 0) out.push({ field: 'password', kind: 'required' })
  else if (codePointLength(input.password) < LIMITS.registerPasswordMin)
    out.push({ field: 'password', kind: 'too-short' })
  if (input.confirm !== input.password) out.push({ field: 'confirm', kind: 'mismatch' })
  for (const f of ['account', 'display_name', 'password'] as const) {
    const i = tooLong(f, input[f])
    if (i) out.push(i)
  }
  return out
}

/* ===================== S09 计划表单（PlanCreate / PlanPatch） ===================== */
export interface PlanFormValues {
  title: string
  goal: string
  start_date: string
  end_date: string
  content: string
}

/**
 * 跨字段规则（§11.4）：两端日期要么都填、要么都不填；且 start ≤ end。
 * 文案由调用方用 content-spec:136 的逐字串渲染（见 mapError.fieldIssueText）。
 */
export function validatePlanForm(v: PlanFormValues): FieldIssues {
  const out: FieldIssues = []
  if (v.title.trim().length === 0) out.push({ field: 'title', kind: 'required' })
  if (v.content.trim().length === 0) out.push({ field: 'content', kind: 'required' })
  for (const f of ['title', 'goal', 'content'] as const) {
    const i = tooLong(f, v[f])
    if (i) out.push(i)
  }

  const s = v.start_date.trim()
  const e = v.end_date.trim()
  const bothOrNeither = (s === '') === (e === '')
  const bothValid = (s === '' || ISO_DATE.test(s)) && (e === '' || ISO_DATE.test(e))
  // YYYY-MM-DD 的字典序即时序。
  const ordered = s === '' || e === '' || s <= e
  if (!bothOrNeither || !bothValid || !ordered) {
    out.push({ field: 'start_date', kind: 'date-range' })
    out.push({ field: 'end_date', kind: 'date-range' })
  }
  return out
}

/* ===================== S10 课程表单（CourseCreate / CoursePatch） ===================== */
export interface CourseFormValues {
  code: string
  name: string
  description: string
}

export function validateCourseForm(v: CourseFormValues, creating: boolean): FieldIssues {
  const out: FieldIssues = []
  if (creating) {
    // CoursePatch 无 code 字段 → 编辑期 code 只读，不校验。
    if (v.code.trim().length === 0) out.push({ field: 'code', kind: 'required' })
    const c = tooLong('code', v.code)
    if (c) out.push(c)
  }
  if (v.name.trim().length === 0) out.push({ field: 'name', kind: 'required' })
  for (const f of ['name', 'description'] as const) {
    const i = tooLong(f, v[f])
    if (i) out.push(i)
  }
  return out
}

/* ===================== S12 课表表单（ScheduleCreate / SchedulePatch） ===================== */
export interface ScheduleFormValues {
  student_id: string
  course_id: string
  class_date: string
  start_time: string
  end_time: string
  location: string
  reason: string
}

export function validateScheduleForm(v: ScheduleFormValues): FieldIssues {
  const out: FieldIssues = []
  if (v.student_id.trim() === '') out.push({ field: 'student_id', kind: 'missing-selection' })
  if (v.course_id.trim() === '') out.push({ field: 'course_id', kind: 'missing-selection' })
  if (!ISO_DATE.test(v.class_date)) out.push({ field: 'class_date', kind: 'required' })
  const okTime = TIME_HM.test(v.start_time) && TIME_HM.test(v.end_time)
  // 「结束时间必须晚于开始时间，且不支持跨日记录」（content-spec:165）：HH:MM 字典序即时序。
  if (!okTime || v.end_time <= v.start_time) {
    out.push({ field: 'start_time', kind: 'time-range' })
    out.push({ field: 'end_time', kind: 'time-range' })
  }
  for (const f of ['location', 'reason'] as const) {
    const i = tooLong(f, v[f])
    if (i) out.push(i)
  }
  return out
}

/** 重叠确认面板的提交前置条件：`overlap_acknowledged=true` + **非空** `reason`（§6.10 / S12）。 */
export function canAcknowledgeOverlap(v: Pick<ScheduleFormValues, 'reason'>): boolean {
  return v.reason.trim().length > 0
}

/* ===================== 其它 ===================== */
/** 幂等键格式校验（§6.3）；只有 4 个端点允许带该头。 */
export function isValidIdempotencyKey(key: string): boolean {
  return key.length > 0 && key.length <= IDEMPOTENCY_KEY_MAX && IDEMPOTENCY_KEY.test(key)
}

/**
 * 课表单次查询跨度：最多 31 个自然日，含起止（SRS §3.2）
 * → 前端在选择器上限制，不发超限请求（§6.6）。
 */
export function validateScheduleRange(fromDate: string, toDate: string): FieldIssues {
  if (!ISO_DATE.test(fromDate) || !ISO_DATE.test(toDate)) return []
  const a = Date.UTC(+fromDate.slice(0, 4), +fromDate.slice(5, 7) - 1, +fromDate.slice(8, 10))
  const b = Date.UTC(+toDate.slice(0, 4), +toDate.slice(5, 7) - 1, +toDate.slice(8, 10))
  const days = Math.round((b - a) / 86_400_000) + 1
  if (days < 1 || days > LIMITS.scheduleRangeDays) return [{ field: 'from_date', kind: 'range-days' }]
  return []
}

/** 聊天输入：去首尾空白后非空，且码点数 ≤2000（§6.5 submit 规则 1）。空白时按钮保持禁用。 */
export function canSubmitMessage(message: string): boolean {
  const t = message.trim()
  return t.length > 0 && codePointLength(t) <= LIMITS.chatMessage
}
