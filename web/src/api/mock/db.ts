/**
 * mock 数据仓库。**不接真实后端**，但字段名/枚举/必填性一律照
 * `docs/backend/openapi_v0.1.json` 造，因此它能被 §15.2 的契约断言直接核对。
 *
 * 时间锚点：`MOCK_TODAY = '2026-10-22'`（content-spec 的样例日期）。
 * 学生端课表默认查「学校时区当日」，用真实系统日期会让 S07「有课」永远看不到；
 * 固定锚点是**mock 数据的取舍**，不是产品行为，已在 `web/README.md` 写明。
 */

import type {
  Batch,
  Course,
  Document,
  Draft,
  Me,
  Plan,
  Reference,
  Schedule,
  Task,
  User,
  WriteOperation,
} from '../types'

/** mock 的「学校时区当日」。 */
export const MOCK_TODAY = '2026-10-22'
export const MOCK_TIMEZONE = 'Asia/Shanghai'

/**
 * S08 ② 的触发日（mock-only）：查这一天会得到 503 `RETRIEVAL_UNAVAILABLE`，
 * 用来验证「课表无法读取」与「当天无安排」是两种不同状态（SRS INV-05）。
 */
export const MOCK_SCHEDULE_FAIL_DATE = '2026-10-25'

export interface MockUser extends User {
  /** 仅 mock 侧持有；**不进任何响应体**（openapi 的 User 没有该字段）。 */
  password: string
}

export const users: MockUser[] = [
  { id: 'u_stu_001', account: 'student_demo', display_name: '林晓', role: 'student', enabled: true, version: 1, password: 'demo1234' },
  { id: 'u_adm_001', account: 'admin_demo', display_name: '管理员', role: 'admin', enabled: true, version: 1, password: 'demo1234' },
  { id: 'u_stu_002', account: 'student_lin', display_name: '陈昊', role: 'student', enabled: true, version: 2, password: 'demo1234' },
  { id: 'u_stu_003', account: 'student_off', display_name: '停用账号', role: 'student', enabled: false, version: 1, password: 'demo1234' },
]

export const courses: Course[] = [
  { id: 'c_cs201', code: 'CS201', name: '数据结构', description: '计算机学院专业基础课', enabled: true, version: 4 },
  { id: 'c_cs310', code: 'CS310', name: '操作系统', description: '计算机学院专业基础课', enabled: false, version: 2 },
]

export const schedules: Schedule[] = [
  {
    id: 'sch_0001',
    student_id: 'u_stu_001',
    course_id: 'c_cs201',
    course_name: '数据结构',
    class_date: '2026-10-22',
    start_time: '08:00',
    end_time: '09:40',
    location: '主楼 A-305',
    version: 1,
  },
  {
    id: 'sch_0002',
    student_id: 'u_stu_001',
    course_id: 'c_cs310',
    course_name: '大学英语',
    class_date: '2026-10-22',
    start_time: '10:00',
    end_time: '11:40',
    location: '文科楼 B-102',
    version: 1,
  },
  {
    id: 'sch_0003',
    student_id: 'u_stu_002',
    course_id: 'c_cs201',
    course_name: '数据结构',
    class_date: '2026-10-22',
    start_time: '08:00',
    end_time: '09:40',
    location: '主楼 A-305',
    version: 1,
  },
]

export const references: Record<string, Reference> = {
  ref_lab_001: {
    reference_id: 'ref_lab_001',
    document_id: 'doc_lab_2026',
    version_id: 'ver_lab_2026_3',
    file_name: '数据结构实验指导书（2026 秋）.pdf',
    location_label: '第 12 页',
    page_number: 12,
  },
  /** 「无页码」样例：页码抽不到时只显示文件名与位置（content-spec:87）。 */
  ref_lab_002: {
    reference_id: 'ref_lab_002',
    document_id: 'doc_lab_2026',
    version_id: 'ver_lab_2026_3',
    file_name: '实验二指导书.pdf',
    location_label: '第 3 节',
  },
  /** 引用失效样例（对应 HTTP 410 CITATION_UNAVAILABLE，content-spec:89）。 */
  ref_gone_001: {
    reference_id: 'ref_gone_001',
    document_id: 'doc_deleted',
    version_id: 'ver_deleted_1',
    file_name: '评分说明.pdf',
    location_label: '第 1 页',
    page_number: 1,
  },
}

export const plans: Plan[] = [
  {
    id: 'plan_7Q2F9K',
    title: '实验二排序算法预习计划',
    goal: '实验前完成排序算法预习并提交预习报告',
    start_date: '2026-10-22',
    end_date: '2026-10-24',
    content: '1）通读实验指导书第 12 页的排序算法部分。\n2）实现快速排序与归并排序并对比复杂度。\n3）整理预习报告，不少于 500 字。',
    source: 'assistant',
    basis_types: ['schedule', 'documents'],
    references: [references.ref_lab_001 as Reference],
    version: 3,
    created_at: '2026-10-21T09:12:00+08:00',
    updated_at: '2026-10-21T09:20:00+08:00',
  },
  {
    id: 'plan_2M8XQ1',
    title: '期末复习总纲',
    goal: null,
    start_date: null,
    end_date: null,
    content: '按章节梳理知识点，先过一遍数据结构与操作系统。',
    source: 'manual',
    basis_types: ['general'],
    references: [],
    version: 1,
    created_at: '2026-10-20T01:05:00+08:00',
    updated_at: '2026-10-20T01:05:00+08:00',
  },
]

const task = (id: string, state: Task['state'], retryable = false): Task => ({ task_id: id, state, retryable })

export const documents: Document[] = [
  {
    id: 'doc_lab_2026',
    batch_id: 'batch_9F3K',
    original_name: '数据结构实验指导书（2026 秋）.pdf',
    file_type: 'pdf',
    byte_size: 2_516_582,
    visibility: 'shared',
    processing_state: 'available',
    version: 3,
    uploaded_at: '2026-10-21T08:40:00+08:00',
    cleanup_state: 'not_required',
  },
  {
    id: 'doc_lab2',
    batch_id: 'batch_9F3K',
    original_name: '实验二指导书.pdf',
    file_type: 'pdf',
    byte_size: 1_153_433,
    visibility: 'unpublished',
    processing_state: 'processing',
    version: 1,
    uploaded_at: '2026-10-21T08:40:00+08:00',
    cleanup_state: 'not_required',
  },
  {
    id: 'doc_scan',
    batch_id: 'batch_9F3K',
    original_name: '课堂扫描件.pdf',
    file_type: 'pdf',
    byte_size: 9_122_611,
    visibility: 'unpublished',
    processing_state: 'failed',
    version: 1,
    uploaded_at: '2026-10-21T08:41:00+08:00',
    error_code: 'NO_TEXT_EXTRACTED',
    cleanup_state: 'not_required',
  },
  {
    id: 'doc_old',
    batch_id: 'batch_7K2A',
    original_name: '旧版讲义.docx',
    file_type: 'docx',
    byte_size: 629_145,
    visibility: 'removed',
    processing_state: 'deleting',
    version: 2,
    uploaded_at: '2026-10-21T07:02:00+08:00',
    cleanup_state: 'running',
  },
  {
    id: 'doc_grading',
    batch_id: 'batch_7K2A',
    original_name: '评分说明.pdf',
    file_type: 'pdf',
    byte_size: 419_430,
    visibility: 'removed',
    processing_state: 'delete_failed',
    version: 2,
    uploaded_at: '2026-10-21T06:55:00+08:00',
    error_code: 'CLEANUP_FAILED',
    cleanup_state: 'failed',
  },
]

export const batches: Batch[] = [
  {
    batch_id: 'batch_9F3K',
    state: 'failed',
    published: false,
    documents: documents.filter((d) => d.batch_id === 'batch_9F3K'),
    tasks: [task('task_9F3K_1', 'failed')],
    error_code: 'NO_TEXT_EXTRACTED',
  },
  {
    batch_id: 'batch_7K2A',
    state: 'published',
    published: true,
    documents: documents.filter((d) => d.batch_id === 'batch_7K2A'),
    tasks: [task('task_7K2A_1', 'succeeded')],
  },
]

/**
 * 草稿种子。
 *
 * **必须和 `mock/sse.ts` 的默认脚本一致**：那条流会在 `status` 事件里给 `draft_id=draft_mock_1`，
 * 随后视图调 `GET /me/drafts/draft_mock_1`。若这里没有对应记录，mock 会返回 410 `DRAFT_EXPIRED`，
 * S06 的正常路径就永远演示不出来（这个缺口是渲染冒烟抓出来的）。
 *
 * 字段取值逐字对应 `content-spec.md` S06:
 *   标题字段=实验二排序算法预习计划 · 目标=实验前完成排序算法预习并提交预习报告
 *   覆盖日期=2026-10-22 → 2026-10-24 · 依据=本人课表 + 课程资料〔资料 1〕· 正文 3 条
 */
export const drafts: Record<string, Draft> = {
  draft_mock_1: {
    draft_id: 'draft_mock_1',
    draft_version: 1,
    operation_id: 'op_mock_draft_1',
    title: '实验二排序算法预习计划',
    goal: '实验前完成排序算法预习并提交预习报告',
    start_date: '2026-10-22',
    end_date: '2026-10-24',
    content:
      '1）通读实验指导书第 12 页的排序算法部分。\n2）实现快速排序与归并排序并对比复杂度。\n3）整理预习报告，不少于 500 字。',
    basis_types: ['schedule', 'documents'],
    references: [references.ref_lab_001 as Reference],
    expires_at: '2026-10-22T10:35:00+08:00',
  },
}

export const writeOperations: Record<string, WriteOperation> = {}

export const meOf = (u: MockUser): Me => ({
  user: { id: u.id, account: u.account, display_name: u.display_name, role: u.role, enabled: u.enabled, version: u.version },
  session_expires_at: '2026-10-22T21:47:00+08:00',
  school_timezone: MOCK_TIMEZONE,
  capabilities: u.role === 'admin' ? ['chat', 'plans', 'schedules', 'admin'] : ['chat', 'plans', 'schedules'],
})

/** 会话表：token → user id。mock 侧同样「仅内存」。 */
export const sessions = new Map<string, string>()
