/**
 * 全仓库常量集中点（§2.4「常量：错误码、事件名、路由名集中在 domain/constants.ts，禁止散落字符串」）。
 * 纯数据，无副作用；`domain/**` 不得 import stores/api/vue（§2.2 R1）。
 */

/* ============ 路由名（§7.1 冻结路由表，10 条，不得增删改名） ============ */
export const ROUTE_NAMES = [
  'login',
  'assistant',
  'schedules',
  'plans',
  'planDetail',
  'adminCourses',
  'adminDocuments',
  'adminBatch',
  'adminSchedules',
  'adminStudents',
] as const
export type RouteName = (typeof ROUTE_NAMES)[number]

/** 4 个一级入口（取 tokens.json → --tabbar-cols 的 d：「助手/课表/计划/管理」）。 */
export const NAV_KEYS = ['assistant', 'schedules', 'plans', 'admin'] as const
export type NavKey = (typeof NAV_KEYS)[number]

/** `document.title` 固定后缀的产品名（content-spec:52）。 */
export const TITLE_SUFFIX = ' · 校园课程智能助手'

/** 唯一的私有深链（§7.6）：仅计划详情。 */
export const DEEP_LINK_ONLY = 'planDetail'

/* ============ SSE 事件名（sse_events_v0.1.schema.json 的 6 个 const，§5.5） ============ */
export const SSE_EVENT_NAMES = ['status', 'tool_start', 'tool_end', 'token', 'done', 'error'] as const
export type SseEventName = (typeof SSE_EVENT_NAMES)[number]

/** 工具白名单（PRD §11.2、SRS IF-008）。 */
export const TOOL_NAMES = ['get_my_schedule', 'search_course_docs', 'save_study_plan'] as const
export type ToolName = (typeof TOOL_NAMES)[number]

/** 出现过写工具 ⇒ 本轮含写意图，`unknown` 时须核实而非重试（§5.9）。 */
export const WRITE_TOOLS: readonly ToolName[] = ['save_study_plan']

/** `tool_end.result_status` 取值（SSE schema）。 */
export const TOOL_RESULT_STATUSES = ['ok', 'empty', 'created', 'existing', 'failed'] as const
export type ToolResultStatus = (typeof TOOL_RESULT_STATUSES)[number]

/** `status` 事件里被前端特别处理的三个 code。 */
export const STATUS_CODE_ACCEPTED = 'ACCEPTED'
export const CAPACITY_CODES = ['CAPACITY_LIMITED', 'CALL_LIMIT_REACHED'] as const

/** 协议违规种类（§5.3/§5.4），用于 `protocolViolations` 与埋点。 */
export const PROTOCOL_ISSUES = [
  'truncated-frame',
  'bad-event-json',
  'unknown-event',
  'id-seq-mismatch',
  'double-terminal',
  'unpaired-tool',
  'missing-conversation-id',
  'buffer-limit-exceeded',
] as const
export type ProtocolIssue = (typeof PROTOCOL_ISSUES)[number]

/** 累计 3 次协议违规即终止并落 failed（§5.3）。 */
export const PROTOCOL_ISSUE_BUDGET = 3

/** 单事件 payload 上限与总缓冲上限（§5.3 P12）。 */
export const SSE_FRAME_LIMIT_BYTES = 1 << 20

/* ============ 错误码（§3.4 权威表；29 同步 + 6 异步） ============ */
export const SYNC_ERROR_CODES = [
  'AUTH_REQUIRED',
  'CALL_LIMIT_REACHED',
  'CAPACITY_LIMITED',
  'CHAT_IN_PROGRESS',
  'CITATION_UNAVAILABLE',
  'DOCUMENT_BUSY',
  'DRAFT_EXPIRED',
  'DUPLICATE_ACCOUNT',
  'DUPLICATE_COURSE',
  'DUPLICATE_FILENAME',
  'DUPLICATE_SCHEDULE',
  'EXECUTION_TIMEOUT',
  'FORBIDDEN',
  'IDEMPOTENCY_CONFLICT',
  'INTERNAL_ERROR',
  'MCP_UNAVAILABLE',
  'MODEL_UNAVAILABLE',
  'REQUEST_ALREADY_EXISTS',
  'RESOURCE_NOT_FOUND',
  'RETRIEVAL_UNAVAILABLE',
  'SAVE_LIMIT_REACHED',
  'SAVE_NOT_AUTHORIZED',
  'SCHEDULE_OVERLAP',
  'SESSION_EXPIRED',
  'STORAGE_UNAVAILABLE',
  'UNSUPPORTED_FILE_TYPE',
  'UPLOAD_TOO_LARGE',
  'VALIDATION_FAILED',
  'VERSION_CONFLICT',
] as const
export type SyncErrorCode = (typeof SYNC_ERROR_CODES)[number]

/** 异步任务码：出现在批次/文件状态里，不是 HTTP 错误（§3.4）。 */
export const ASYNC_TASK_CODES = [
  'NO_TEXT_EXTRACTED',
  'DOCUMENT_ENCRYPTED',
  'PARSE_FAILED',
  'EMBEDDING_FAILED',
  'CLEANUP_FAILED',
  'SERVICE_RESTARTED',
] as const
export type AsyncTaskCode = (typeof ASYNC_TASK_CODES)[number]

/** 会话失效的两个码（§4.6：唯一失效出口）。 */
export const AUTH_FAILURE_CODES = ['AUTH_REQUIRED', 'SESSION_EXPIRED'] as const

/* ============ 幂等键（§6.3：仅 4 个端点接受 Idempotency-Key 头） ============ */
export const IDEMPOTENT_ENDPOINTS = [
  'POST /me/plans',
  'POST /me/drafts/{draft_id}/save',
  'POST /admin/documents/{id}/rebuild',
  'POST /admin/documents/{id}/cleanup-retry',
] as const
/** 幂等键取值约束：`^[A-Za-z0-9._:-]+$`、≤96。 */
export const IDEMPOTENCY_KEY_RE = /^[A-Za-z0-9._:-]+$/
export const IDEMPOTENCY_KEY_MAX = 96

/* ============ 字段约束（§11.1；字符串上限按 Unicode 码点计数，SRS DR-001） ============ */
export const LIMITS = {
  chatMessage: 2000,
  chatHistoryRounds: 20,
  chatHistoryContent: 20000,
  planTitle: 100,
  planGoal: 500,
  planContent: 10000,
  courseCode: 32,
  courseName: 100,
  courseDescription: 2000,
  studentDisplayName: 50,
  scheduleLocation: 200,
  overlapReason: 500,
  uploadMaxFiles: 10,
  uploadMaxFileBytes: 20 * 1024 * 1024,
  uploadMaxBatchBytes: 50 * 1024 * 1024,
  scheduleRangeDays: 31,
  /** `RegisterInput.account`（openapi）：trim 后 3–64。 */
  registerAccountMin: 3,
  registerAccountMax: 64,
  /** `RegisterInput.password`：8–1024。 */
  registerPasswordMin: 8,
  registerPasswordMax: 1024,
} as const

/* ============ 超时（§5.8） ============ */
export const TIMEOUTS = {
  request: 15_000,
  streamFirstByte: 10_000,
  streamIdleGap: 30_000,
} as const

/* ============ 轮询节奏（§6.9 唯一权威表 / §6.10） ============ */
export const WRITE_OP_BACKOFF_MS = [1_000, 2_000, 4_000, 8_000, 10_000] as const
export const WRITE_OP_UNDECIDED_LIMIT = 5
export const BATCH_POLL_MS = 3_000

/* ============ 渲染节流（§5.10） ============ */
export const STREAM_FLUSH_MS = 100
export const LIVE_FLUSH_MS = 500
export const SCROLL_FOLLOW_THRESHOLD_PX = 48
