/**
 * 冻结路由表（**10 条**，§7.1）。
 *
 * 前 5 列逐字来自 `CONTRACT.md` §3.3；`meta` 是本册补的。
 * **路径、name、视图名不得改动**；未匹配路径**不新增 catch-all 记录**
 * （在 `guards.ts` 里用 `to.matched.length === 0` 判定后重定向）。
 */

import type { RouteRecordRaw } from 'vue-router'
import { S07, S09, S10, S11, S12, S15 } from '@/domain/copy'

export type ActiveNav = 'assistant' | 'schedules' | 'plans' | 'admin'

export interface ShellMeta {
  requiresAuth: boolean
  requiresAdmin: boolean
  /** 写入 `document.title`（+ 固定后缀「· 校园课程智能助手」）。 */
  title: string
  /** 4 个一级入口之一；`/login` 为 undefined（登录屏不渲染主导航）。 */
  activeNav?: ActiveNav
}

declare module 'vue-router' {
  interface RouteMeta extends ShellMeta {}
}

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false, requiresAdmin: false, title: S01Title() },
  },
  {
    path: '/assistant',
    name: 'assistant',
    component: () => import('@/views/AssistantView.vue'),
    meta: { requiresAuth: true, requiresAdmin: false, title: '助手', activeNav: 'assistant' },
  },
  {
    path: '/me/schedules',
    name: 'schedules',
    component: () => import('@/views/MyScheduleView.vue'),
    meta: { requiresAuth: true, requiresAdmin: false, title: S07.title, activeNav: 'schedules' },
  },
  {
    path: '/me/plans',
    name: 'plans',
    component: () => import('@/views/PlansView.vue'),
    meta: { requiresAuth: true, requiresAdmin: false, title: S09.listTitle, activeNav: 'plans' },
  },
  {
    path: '/me/plans/:planId',
    name: 'planDetail',
    component: () => import('@/views/PlanDetailView.vue'),
    meta: { requiresAuth: true, requiresAdmin: false, title: S09.listTitle, activeNav: 'plans' },
  },
  {
    // §14.1 分包硬约束 1：Admin* 必须动态 import，不得进首屏 chunk。
    path: '/admin/courses',
    name: 'adminCourses',
    component: () => import('@/views/AdminCoursesView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: S10.title, activeNav: 'admin' },
  },
  {
    path: '/admin/documents',
    name: 'adminDocuments',
    component: () => import('@/views/AdminDocumentsView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: S11.title, activeNav: 'admin' },
  },
  {
    path: '/admin/document-batches/:batchId',
    name: 'adminBatch',
    component: () => import('@/views/AdminBatchView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: S11.title, activeNav: 'admin' },
  },
  {
    path: '/admin/schedules',
    name: 'adminSchedules',
    component: () => import('@/views/AdminScheduleView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, title: S12.title, activeNav: 'admin' },
  },
  {
    path: '/admin/students',
    name: 'adminStudents',
    component: () => import('@/views/AdminStudentsView.vue'),
    // content-spec S15.6 已冻结该标题（原先是登记待冻结的硬编码串）。
    meta: { requiresAuth: true, requiresAdmin: true, title: S15.adminStudentsTitle, activeNav: 'admin' },
  },
]

function S01Title(): string {
  // content-spec:51「登录」（页面标题）
  return '登录'
}

/** 4 个一级入口的顶栏/标签栏文案（§7.4）。 */
export const NAV_ITEMS: Array<{ key: ActiveNav; appbar: string; tabbar: string; to: string }> = [
  // 顶栏与标签栏的短文案取自 --tabbar-cols 的 d 与各屏标题
  { key: 'assistant', appbar: '课程助手', tabbar: '助手', to: '/assistant' },
  { key: 'schedules', appbar: S07.title, tabbar: '课表', to: '/me/schedules' },
  { key: 'plans', appbar: S09.listTitle, tabbar: '计划', to: '/me/plans' },
  { key: 'admin', appbar: '管理中心', tabbar: '管理', to: '/admin/courses' },
]

/**
 * 管理中心二级导航的页面顺序（4 个管理页 + 文档批次详情页归入「文档与批次」）。
 *
 * 标签不在这里重复写：`AdminNav` 从对应路由的 `meta.title` 去掉冻结前缀「管理中心 · 」得到，
 * 这样标题只有一处真源，不会与 `document.title` 漂移。
 */
export const ADMIN_PAGES = ['adminCourses', 'adminStudents', 'adminSchedules', 'adminDocuments'] as const
export type AdminPageName = (typeof ADMIN_PAGES)[number]

/** 详情页（`adminBatch`）没有自己的入口，导航上归属「文档与批次」。 */
export const ADMIN_DETAIL_PARENT: AdminPageName = 'adminDocuments'
