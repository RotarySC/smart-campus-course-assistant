/**
 * 前端业务类型门面（手写，**不含字段定义**）。
 *
 * 分工：
 *   - `types.gen.ts` = openapi-typescript 从 OpenAPI **生成**的唯一字段真源（勿手改）。
 *   - 本文件 = 薄别名层：把调用点需要的名字指向 `components['schemas'][...]`，
 *     再派生少量字面量联合（如 `Role = User['role']`）。
 *
 * 为什么需要这层：生成物的类型挂在 `components['schemas'][...]` 路径下，
 * 直接在各处写路径会把字段来源埋进调用点；集中别名后：
 *   1. 字段名/必填性/枚举仍**只有生成物一个来源**（本文件不重复任何字段名）；
 *   2. 契约漂移（字段改名/枚举变化）会在 `vue-tsc` 阶段变成编译错误；
 *   3. 通用信封 `Envelope<T>` / 分页 `Page<T>` 不属于 OpenAPI `components.schemas`
 *      （各响应内联声明），故在此**结构性地**定义一次。
 *
 * 硬约束：本文件**不得**手写业务字段（新增字段一律先去 OpenAPI 真源再重新生成）。
 */

import type { components } from './types.gen'

/** `components['schemas']` 的短别名。 */
export type Schemas = components['schemas']

/* ===================== 通用信封（OpenAPI 各响应内联，非 schema） ===================== */

/** 统一响应信封 `{ request_id, data }`（NFR-OBS-001）；前端在 client.ts 里做运行时校验。 */
export interface Envelope<T> {
  request_id: string
  data: T
}

/** 统一分页信封（`*Page` schema 的公共骨架）。 */
export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

/* ===================== 身份与会话 ===================== */

export type User = Schemas['User']
export type Role = User['role']
export type LoginInput = Schemas['LoginInput']
export type Login = Schemas['Login']
export type Me = Schemas['Me']
export type Logout = Schemas['Logout']

/* ===================== 课表 ===================== */

export type Schedule = Schemas['Schedule']
export type ScheduleCreate = Schemas['ScheduleCreate']
export type SchedulePatch = Schemas['SchedulePatch']
export type ScheduleDelete = Schemas['ScheduleDelete']
export type SchedulePage = Schemas['SchedulePage']

/* ===================== 计划 ===================== */

export type Reference = Schemas['Reference']
export type Plan = Schemas['Plan']
export type PlanCreate = Schemas['PlanCreate']
export type PlanPatch = Schemas['PlanPatch']
export type PlanDelete = Schemas['PlanDelete']
export type PlanPage = Schemas['PlanPage']
export type PlanSource = Plan['source']
export type BasisType = Plan['basis_types'][number]
export type SaveResult = Schemas['SaveResult']
export type SaveStatus = SaveResult['status']

/* ===================== 草稿 ===================== */

export type Draft = Schemas['Draft']
export type DraftPatch = Schemas['DraftPatch']
export type DraftSave = Schemas['DraftSave']

/* ===================== 写操作核实 ===================== */

export type WriteOperation = Schemas['WriteOperation']
export type WriteOpState = WriteOperation['state']
export type WriteResolution = WriteOperation['resolution']

/* ===================== 引用与对话 ===================== */

export type Citation = Schemas['Citation']
export type HistoryMessage = Schemas['HistoryMessage']
export type ChatInput = Schemas['ChatInput']
export type ChatState = Schemas['ChatState']
export type ChatRunState = ChatState['state']

/* ===================== 管理端：课程 / 学生 ===================== */

export type Course = Schemas['Course']
export type CourseCreate = Schemas['CourseCreate']
export type CoursePatch = Schemas['CoursePatch']
export type CoursePage = Schemas['CoursePage']
export type StudentCreate = Schemas['StudentCreate']
export type StudentPatch = Schemas['StudentPatch']
export type StudentPage = Schemas['StudentPage']

/* ===================== 管理端：文档与批次 ===================== */

export type Document = Schemas['Document']
export type DocumentPage = Schemas['DocumentPage']
export type DocumentMutation = Schemas['DocumentMutation']
export type DocumentText = Schemas['DocumentText']
export type Batch = Schemas['Batch']
export type Task = Schemas['Task']
export type TaskState = Task['state']
export type FileType = Document['file_type']
export type Visibility = Document['visibility']
export type ProcessingState = Document['processing_state']
export type CleanupState = Document['cleanup_state']
export type BatchState = Batch['state']

/* ===================== 管理端：写操作回执 ===================== */

export type Upload = Schemas['Upload']
export type Rebuild = Schemas['Rebuild']
export type Cancel = Schemas['Cancel']
