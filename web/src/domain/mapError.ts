/**
 * 错误码 → 用户可见文案的**唯一映射点**。纯函数（§2.2 R1）。
 *
 * 三条硬规则：
 *   1. 分支**只看 `code`**，不得用 `error.message` 做判断（§4.8 禁止事项），
 *      也不得看 HTTP 状态码（SRS IF-010：流内没有 HTTP 状态，同一错误三处同码）。
 *   2. 文案只取自 `domain/copy.ts` 的冻结集合；没有冻结文案的码**不自造句子**，
 *      只展示 `errorCodeLabel` + code + `requestIdLabel` + request_id（见 copy.ts 的缺口登记）。
 *   3. 待确认 ≠ 失败（FR-CHAT-005）：未知写入结果走 writeOps，不经过本文件的失败分支。
 */

import { S01, S04, S05, S06, S07, S08, S09, S10, S11, S12 } from './copy'
import { AUTH_FAILURE_CODES } from './constants'
import type { IssueKind } from './validate'

/** `api/errors.ts` 的 `AppError` 的结构子集 —— domain 不得 import api（§2.2 R1）。 */
export interface MappableError {
  code?: string
  httpStatus?: number | null
  requestId?: string | null
  /** 服务端 `Error.error.field_errors[]`：权威的字段级 reason（§4.8）。 */
  fieldErrors?: ReadonlyArray<{ field: string; reason: string }>
  /** `openapi` `ErrorDetails` 的已知子字段。 */
  details?: {
    existing_request_id?: string
    operation_id?: string
    plan_id?: string
    state?: string
    retryable?: boolean
  }
}

/** 已冻结文案的码 → 文案。表里没有的码返回 `null`（**不自造**）。 */
const FROZEN_BY_CODE: Record<string, string> = {
  DUPLICATE_COURSE: S10.duplicateCode, // content-spec:146（S10）
  DUPLICATE_SCHEDULE: S12.duplicateSchedule, // content-spec:166（S12）
  VERSION_CONFLICT: S09.versionConflict, // content-spec:137（S09）
  IDEMPOTENCY_CONFLICT: S06.idempotencyNote, // content-spec:110（S06）
  RETRIEVAL_UNAVAILABLE: S05.retrievalFailed, // content-spec:94（S05）
  CITATION_UNAVAILABLE: S04.citeInvalid, // content-spec:89（S04）
  NO_TEXT_EXTRACTED: S11.noTextExtracted, // content-spec:156（S11 失败原因）
  UPLOAD_TOO_LARGE: S11.uploadHint, // content-spec:151（S11 限额说明）
  UNSUPPORTED_FILE_TYPE: S11.uploadHint, // content-spec:151（S11 允许类型）
  DUPLICATE_ACCOUNT: S01.duplicateAccount, // content-spec:251（S15.5 注册）
}

/** 该码是否属于「会话失效」路径（§4.6 唯一失效出口）。 */
export function isAuthFailureCode(code: string): boolean {
  return (AUTH_FAILURE_CODES as readonly string[]).includes(code)
}

/** 该码是否按「待确认」而非「失败」处理（FR-CHAT-005 / §5.9 / §3.4 的 504 行）。 */
export function isPendingNotFailedCode(code: string): boolean {
  return code === 'EXECUTION_TIMEOUT' || code === 'CALL_LIMIT_REACHED' || code === 'STORAGE_UNAVAILABLE'
}

/**
 * 返回该错误的用户可见句子；`null` 表示「内容契约未冻结该码的文案」，
 * 调用方改为只渲染 `errorCodeLabel` + code + `requestIdLabel` + request_id，不自造 prose。
 */
export function mapErrorText(e: MappableError): string | null {
  if (e.code === undefined) return null
  return FROZEN_BY_CODE[e.code] ?? null
}

/**
 * 字段级校验问题的文案。
 *
 * - 服务端 `field_errors[].reason` 是**权威**，由组件直接渲染，不走本函数；
 * - 客户端即时校验产生的 `kind` 在这里映射到已冻结文案；
 * - `too-long` 返回 `null`：长度已被原生 `maxlength` 在输入侧封死，
 *   绕过它（粘贴/脚本）的情况由服务端 `VALIDATION_FAILED` 给出权威 reason。
 * - `too-short` 的文案按**字段**区分（账号 3 / 密码 8 是两条冻结句），因此 `field` 是必需入参。
 */
export function fieldIssueText(kind: IssueKind, field?: string): string | null {
  switch (kind) {
    case 'required':
    case 'missing-selection':
      // content-spec:54 只冻结了「必填」这个标记本身；不再自造「不能为空」。
      return S01.required
    case 'date-range':
      return S09.dateRangeError // content-spec:136
    case 'time-range':
      return S12.timeRangeError // content-spec:165
    case 'range-days':
      return S07.rangeLimit // content-spec:114
    case 'too-short':
      if (field === 'account') return S01.accountTooShort // content-spec:247
      if (field === 'password') return S01.passwordTooShort // content-spec:248
      return null
    case 'mismatch':
      return S01.passwordMismatch // content-spec:249
    case 'too-long':
      return null
  }
}

/** S12 重叠确认面板的冲突提示；模板逐字取自 content-spec:168，仅做占位符替换。 */
export function overlapText(vars: { date: string; start: string; end: string; course: string }): string {
  return S12.overlapTemplate
    .replace('{date}', vars.date)
    .replace('{start}', vars.start)
    .replace('{end}', vars.end)
    .replace('{course}', vars.course)
}

/** S09 删除确认文案；模板逐字取自 content-spec:138，仅做占位符替换。 */
export function planDeleteConfirmText(title: string): string {
  return S09.deleteConfirmTemplate.replace('{title}', title)
}

/** S08 ① 成功的空（无课程）：占位符 {date}/{weekday} 逐字取自 content-spec:122。 */
export function noCoursesText(date: string, weekday: string): string {
  return S08.noCoursesTemplate.replace('{date}', date).replace('{weekday}', weekday)
}
