/**
 * `session` store —— 令牌（**只在内存**）、`/me` 身份、登录/登出、会话失效处理。
 *
 * 令牌的 7 个泄漏面逐条否定（§4.2.2）：不进 localStorage/sessionStorage/IndexedDB/
 * Cookie/URL/日志/埋点/下载文件名/AppError 序列化。因此本文件**不 import 任何存储 API**。
 *
 * 反向通知不用 import（§6.2）：`chat`/`drafts`/… 在自身 setup 里注册回调，
 * 因此 session 不需要 import 它们，静态依赖图无环。
 */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as authApi from '@/api/auth'
import type { RegisterInput } from '@/api/auth'
import * as meApi from '@/api/me'
import type { AuthSnapshot } from '@/api/client'
import type { AppError } from '@/api/errors'
import type { User } from '@/api/types'
import { useUiStore } from './ui'

export type AuthFailureReason = 'HTTP_401' | 'SSE_ERROR'
type SessionStatus = 'anonymous' | 'authenticating' | 'authenticated' | 'expired'

export interface LoginInput {
  account: string
  password: string
}

export const useSessionStore = defineStore('session', () => {
  const accessToken = ref<string | null>(null) // 唯一存放点
  const tokenType = ref<'Bearer' | null>(null)
  const expiresAt = ref<string | null>(null)
  const user = ref<User | null>(null)
  const schoolTimezone = ref<string | null>(null)
  const capabilities = ref<string[]>([])
  const status = ref<SessionStatus>('anonymous')
  const error = ref<AppError | null>(null)
  const lastRequestId = ref<string | null>(null)

  /** 未登录时被拦下的目标（**内存，不写 URL**，§7.3 G2）。 */
  const pendingPath = ref<string | null>(null)
  const pendingRouteName = ref<string | null>(null)

  const isAuthenticated = computed(() => accessToken.value !== null && status.value === 'authenticated')
  const canAdmin = computed(() => user.value?.role === 'admin')

  /** 令牌以参数注入请求层（§2.2 R2），请求层不 import 本 store。 */
  const auth = computed<AuthSnapshot>(() => ({
    accessToken: accessToken.value,
    tokenType: tokenType.value,
  }))

  /** 各 store 注册的「清理」回调（§6.14 第 4 步），按注册顺序执行。 */
  const cleanups: Array<() => void> = []
  /** §6.14 第 1–3 步（停流 / 冻结轮次 / 停轮询）：在清业务态**之前**执行。 */
  const preClearHooks: Array<() => void> = []

  /**
   * §4.6.3 第 6 步（`router.replace('/login')`）的注入点。
   * store **不 import router**（router 的守卫要 import session，会成环），
   * 由 `main.ts` 在装配阶段注入；未注入时只完成状态清理。
   */
  let expiredNavigator: (() => void) | null = null

  function registerExpiredNavigator(fn: (() => void) | null): void {
    expiredNavigator = fn
  }

  function registerCleanup(fn: () => void): void {
    cleanups.push(fn)
  }

  function registerPreClear(fn: () => void): void {
    preClearHooks.push(fn)
  }

  /** 登录失败**不改 state**（SRS FR-AUTH-001）：只写 error，令牌保持 null。 */
  async function login(input: LoginInput): Promise<void> {
    status.value = 'authenticating'
    error.value = null
    try {
      const res = await authApi.login(input)
      accessToken.value = res.access_token
      tokenType.value = res.token_type
      expiresAt.value = res.expires_at
      user.value = res.user
      status.value = 'authenticated'
    } catch (e) {
      error.value = e as AppError
      status.value = 'anonymous'
      throw e
    }
  }

  /**
   * 自助注册（`POST /auth/register`）：成功即自动登录，收尾与 `login()` 完全一致
   * （调用方随后仍必须 `fetchMe()` 补 capabilities —— §7.3 G7 对注册同样适用）。
   * 失败**不改 state**，只写 error 后抛出，由表单按 `code` 就近回填。
   */
  async function register(input: RegisterInput): Promise<void> {
    status.value = 'authenticating'
    error.value = null
    try {
      const res = await authApi.register(input)
      accessToken.value = res.access_token
      tokenType.value = res.token_type
      expiresAt.value = res.expires_at
      user.value = res.user
      status.value = 'authenticated'
    } catch (e) {
      error.value = e as AppError
      status.value = 'anonymous'
      throw e
    }
  }

  /** G7：登录成功后补齐 `capabilities`/`school_timezone`；**不回写令牌**（`/me` 不含令牌）。 */
  async function fetchMe(): Promise<void> {
    const me = await meApi.getMe(auth.value)
    user.value = me.user
    schoolTimezone.value = me.school_timezone
    expiresAt.value = me.session_expires_at
    capabilities.value = me.capabilities
    status.value = 'authenticated'
  }

  /** G8：登出幂等——无论响应如何都完成清理（SRS FR-AUTH-002）。 */
  async function logout(): Promise<void> {
    try {
      if (accessToken.value) await authApi.logout(auth.value)
    } catch {
      /* 幂等：忽略 */
    } finally {
      runFailureSequence('HTTP_401')
    }
  }

  /**
   * §6.14 的清理序列。顺序是契约的一部分：
   * 先停流 → 再冻结轮次 → 再停轮询 → 再清业务态 → 最后清令牌。
   * 幂等：重复触发（多个并发 401）只执行一次。
   */
  function runFailureSequence(reason: AuthFailureReason): void {
    if (status.value === 'expired') return
    void reason
    status.value = 'expired'
    for (const hook of preClearHooks) {
      try {
        hook()
      } catch {
        /* 收尾失败不阻断清理 */
      }
    }
    for (const fn of cleanups) {
      try {
        fn()
      } catch {
        /* 同上 */
      }
    }
    clear()
    useUiStore().clear()
    // §4.6.3 第 6 步：清理完成后唯一导航点；用 replace，避免回退键回到已清空的私有页面。
    try {
      expiredNavigator?.()
    } catch {
      /* 导航失败不阻断清理（测试环境可能未装 router） */
    }
  }

  /** 唯一失效出口（§4.6）。导航由守卫负责，本函数只负责状态。 */
  function onAuthFailure(reason: AuthFailureReason): void {
    runFailureSequence(reason)
  }

  /** 纯本地：清令牌与身份，**不发请求、不导航**。 */
  function clear(): void {
    accessToken.value = null
    tokenType.value = null
    expiresAt.value = null
    user.value = null
    schoolTimezone.value = null
    capabilities.value = []
    status.value = 'anonymous'
    error.value = null
  }

  function setPending(path: string, routeName: string | null): void {
    pendingPath.value = path
    pendingRouteName.value = routeName
  }

  function consumePending(): { path: string | null; routeName: string | null } {
    const out = { path: pendingPath.value, routeName: pendingRouteName.value }
    pendingPath.value = null
    pendingRouteName.value = null
    return out
  }

  return {
    accessToken,
    tokenType,
    expiresAt,
    user,
    schoolTimezone,
    capabilities,
    status,
    error,
    lastRequestId,
    pendingPath,
    pendingRouteName,
    isAuthenticated,
    canAdmin,
    auth,
    login,
    register,
    fetchMe,
    logout,
    onAuthFailure,
    registerCleanup,
    registerPreClear,
    registerExpiredNavigator,
    clear,
    setPending,
    consumePending,
  }
})
