/**
 * 路由实例。vue-router 4 + **history 模式**（§7.2，CONTRACT §3.1）。
 *
 * `scrollBehavior` 返回 `{ top: 0 }`（新路由）与 `{ el: to.hash }`（同页锚点）；
 * 锚点不被 sticky 顶栏遮挡依赖 W1（`html{scroll-padding-top}`，见 global.css）。
 */

import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './routes'
import { installGuards } from './guards'

export const router = createRouter({
  history: createWebHistory(import.meta.env.VITE_BASE ?? '/'),
  routes,
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, top: 0 }
    return { top: 0 }
  },
})

installGuards(router)

export { routes }
