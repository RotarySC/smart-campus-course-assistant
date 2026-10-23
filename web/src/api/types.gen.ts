/**
 * ⚠ 生成物（勿手改）。
 *
 * 真源：`docs/backend/openapi_v0.1.json`（v0.1）。
 *
 * **诚实说明**：本文件当前由人工按 `openapi_v0.1.json` 的 `components.schemas` 逐字段转写，
 * 因为阶段 B 不引入代码生成器（§1.2 的技术选型里没有 openapi-generator）。
 * 字段名、类型、必填性、枚举值都与真源逐字一致，但**它仍是人工产物**：
 * 后续应换成 `openapi-typescript` 之类的生成器产出同名文件，并把 §15.2 的
 * 「字段名 ∈ openapi schema」契约测试跑起来，才能把「人工转写」这条风险关掉。
 * 见 `web/BUILD-REPORT.md`「未覆盖 / 待裁决」。
 */

/* ===================== 通用信封 ===================== */
export interface Envelope<T> {
  request_id: string
  data: T
}

export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

/* ===================== 身份与会话 ===================== */
export type Role = 'student' | 'admin'

export interface User {
  id: string
  account: string
  display_name: string
  role: Role
  enabled: boolean
  version: number
}

/** `POST /api/v1/auth/login` → 200 */
export interface Login {
  access_token: string
  token_type: 'Bearer'
  expires_at: string
  user: User
}

/** `GET /api/v1/me` → 200 */
export interface Me {
  user: User
  session_expires_at: string
  school_timezone: string
  capabilities: string[]
}

/* ===================== 课表 ===================== */
export interface Schedule {
  id: string
  student_id: string
  course_id: string
  course_name: string
  class_date: string
  start_time: string
  end_time: string
  location: string | null
  version: number
}

/** `GET /api/v1/me/schedules` 与 `GET /api/v1/admin/schedules` → 200 */
export interface SchedulePage extends Page<Schedule> {
  from_date: string
  to_date: string
  school_timezone: string
}

export interface ScheduleCreate {
  student_id: string
  course_id: string
  class_date: string
  start_time: string
  end_time: string
  location?: string | null
  overlap_acknowledged?: boolean
  reason?: string | null
}

export interface SchedulePatch {
  course_id?: string
  class_date?: string
  start_time?: string
  end_time?: string
  location?: string | null
  overlap_acknowledged?: boolean
  reason?: string | null
  expected_version: number
}

export interface ScheduleDelete {
  schedule_id: string
  audit_id: string
}

/* ===================== 计划 ===================== */
export type PlanSource = 'manual' | 'assistant'
export type BasisType = 'schedule' | 'documents' | 'general'

export interface Reference {
  reference_id: string
  document_id: string
  version_id: string
  file_name: string
  location_label: string
  page_number?: number
}

export interface Plan {
  id: string
  title: string
  goal?: string | null
  start_date?: string | null
  end_date?: string | null
  content: string
  source: PlanSource
  basis_types: BasisType[]
  references: Reference[]
  version: number
  created_at: string
  updated_at: string
}

export interface PlanCreate {
  title: string
  goal?: string | null
  start_date?: string | null
  end_date?: string | null
  content: string
}

export interface PlanPatch {
  title?: string
  goal?: string | null
  start_date?: string | null
  end_date?: string | null
  content?: string
  expected_version: number
}

export interface SaveCreatedResult {
  status: 'created'
  operation_id: string
  plan_id: string
}

export interface SaveReusedResult {
  status: 'existing' | 'deleted'
  operation_id: string
  plan_id: string
}

export type SaveResult = SaveCreatedResult | SaveReusedResult

/** `GET /api/v1/me/plans` 与 `GET /api/v1/admin/courses` 等共用同构分页信封。 */
export interface PlanPage extends Page<Plan> {}

/* ===================== 草稿 ===================== */
export interface Draft {
  draft_id: string
  draft_version: number
  operation_id: string
  title: string
  goal?: string | null
  start_date?: string | null
  end_date?: string | null
  content: string
  basis_types: BasisType[]
  references: Reference[]
  expires_at: string
}

export interface DraftPatch {
  title?: string
  goal?: string | null
  start_date?: string | null
  end_date?: string | null
  content?: string
  expected_draft_version: number
}

export interface DraftSave {
  draft_version: number
}

/* ===================== 写操作核实 ===================== */
export type WriteOpState = 'pending' | 'succeeded' | 'failed' | 'deleted'
export type WriteResolution = 'confirmed' | 'recovering'

export interface WriteOperation {
  operation_id: string
  state: WriteOpState
  resolution: WriteResolution
  plan_id?: string
  error_code?: string
  retryable: boolean
}

/* ===================== 对话 ===================== */
export interface HistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatInput {
  client_request_id: string
  conversation_id?: string
  message: string
  history?: HistoryMessage[]
}

/** `GET /api/v1/chat/requests/{request_id}` → 200 */
export interface ChatState {
  request_id: string
  conversation_id: string
  state: 'accepted' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  cancel_requested: boolean
  accepted_at: string
  finished_at: string | null
  terminal_reason?: string
  model_calls: number
  tool_calls: number
  plan_id?: string
  operation_id?: string
}

export interface Citation {
  reference: Reference
  text: string
}

/* ===================== 管理端：课程 ===================== */
export interface Course {
  id: string
  code: string
  name: string
  description: string | null
  enabled: boolean
  version: number
}

export interface CourseCreate {
  code: string
  name: string
  description?: string | null
  enabled?: boolean
}

/** `CoursePatch` 无 `code` 字段 —— 课程代码创建后不可修改（SRS FR-COURSE-001）。 */
export interface CoursePatch {
  name?: string
  description?: string | null
  enabled?: boolean
  expected_version: number
}

/* ===================== 管理端：学生 ===================== */
export interface StudentCreate {
  account: string
  display_name: string
  initial_password: string
}

/** `StudentPatch` 只有显示名/启用/版本（SRS IF-002）。 */
export interface StudentPatch {
  display_name?: string
  enabled?: boolean
  expected_version: number
}

/* ===================== 管理端：文档与批次 ===================== */
export type FileType = 'txt' | 'md' | 'pdf' | 'docx'
export type Visibility = 'unpublished' | 'shared' | 'removed'
export type ProcessingState =
  | 'processing'
  | 'available'
  | 'failed'
  | 'rebuilding'
  | 'deleting'
  | 'delete_failed'
  | 'deleted'
export type CleanupState = 'not_required' | 'pending' | 'running' | 'succeeded' | 'failed'

export interface Document {
  id: string
  batch_id: string
  original_name: string
  file_type: FileType
  byte_size: number
  visibility: Visibility
  processing_state: ProcessingState
  version: number
  uploaded_at: string
  error_code?: string
  cleanup_state: CleanupState
}

export interface Task {
  task_id: string
  state: string
  error_code?: string
  retryable: boolean
}

export interface Batch {
  batch_id: string
  state: 'accepted' | 'processing' | 'published' | 'compensating' | 'failed'
  published: boolean
  documents: Document[]
  tasks: Task[]
  error_code?: string
}

export interface DocumentMutation {
  document_id: string
  visibility: Visibility
  task: Task
  version: number
}

export interface DocumentText {
  document_id: string
  version_id: string
  offset: number
  next_offset: number | null
  text: string
}
