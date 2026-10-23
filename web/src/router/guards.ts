/**
 * 守卫链（§7.3）。**顺序即优先级**：G1 → G2 → G3 → G4。
 *
 * G5–G8 是运行期分支，不在 `beforeEach` 内（grep 可验）。
 *
 * 守卫**不做的三件事**（§7.3 末）：
 *   1. 不预取页面数据（列表首屏请求在视图 `onMounted` 内发起）；
 *   2. 不判细粒度能力（`role` 决定 G4；不发明 capability 字符串）；
 *   3. 不做轮询。
 */

import type { NavigationGuardNext, RouteLocationNormalized, Router } from 'vue-router'
import { TITLE_SUFFIX } from '@/domain/constants'
import { useSessionStore } from '@/stores/session'
import { useUiStore } from '@/stores/ui'

export function installGuards(router: Router): void {
  router.beforeEach((to: RouteLocationNormalized, _from: RouteLocationNormalized, next: NavigationGuardNext) => {
    const session = useSessionStore()
    const ui = useUiStore()

    // G1 未匹配（404）：不渲染「页面不存在」文案（无冻结文案），也不新增 catch-all 记录。
    if (to.matched.length === 0) {
      next(session.accessToken ? { name: 'assistant' } : { name: 'login' })
      return
    }

    const meta = to.meta

    // G2 未登录：存 pendingPath（**内存，不写 URL**）；只有 planDetail 允许登录后回跳。
    if (meta.requiresAuth && !session.accessToken) {
      session.setPending(to.fullPath, typeof to.name === 'string' ? to.name : null)
      next({ name: 'login' })
      return
    }

    // G3 已登录访问登录页 → assistant（契约 §3.3 第 1 行）。
    if (to.name === 'login' && session.accessToken) {
      next({ name: 'assistant' })
      return
    }

    // G4 非管理员访问 /admin/*：回 assistant + 播报一次失败提示；不重试、不重定向到管理页。
    if (meta.requiresAdmin && session.user?.role !== 'admin') {
      ui.announce('当前账号没有管理权限。')
      next({ name: 'assistant' })
      return
    }

    next()
  })

  // `document.title` = route.meta.title + 固定后缀（§7.2；后缀写法是判断项 J2）。
  router.afterEach((to) => {
    if (typeof document === 'undefined') return
    const title = typeof to.meta.title === 'string' ? to.meta.title : ''
    document.title = title === '' ? TITLE_SUFFIX.replace(/^ · /, '') : `${title}${TITLE_SUFFIX}`
  })
}
