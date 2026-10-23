/**
 * 应用入口。
 *
 * 顺序有意固定：
 *   1. 安装 mock 传输层（**仅** `VITE_USE_MOCK=true` 时；默认走真实后端）；
 *   2. `import './styles/tokens.css'`（**静态 import** → 进全局 chunk，§14.1 约束 3）；
 *   3. global.css（元素级全局规则）→ base.css（27 个组件族）；
 *   4. 建 Pinia → 注入会话失效出口（§4.6.1/§4.6.3）→ 注册路由守卫 → 挂载。
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import '@/styles/tokens.css'
import '@/styles/global.css'
import '@/styles/base.css'

import App from './App.vue'
import { router } from './router'
import { installMockTransport, useMock } from './api/mock'
import { setAuthFailureSink, setTraceSink } from './api/client'
import { useSessionStore } from './stores/session'

if (useMock()) installMockTransport()

// 埋点：只记 method/path/status/request_id/耗时，**不记请求体与响应体正文**（NFR-PRIV-001）。
// 本骨架不上报（`VITE_TELEMETRY_ENDPOINT` 留空即不上报），只落到内存数组供调试。
export const traces: Array<Record<string, unknown>> = []
setTraceSink((t) => {
  traces.push({ ...t })
})

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

// §4.6.1：两条失效路径（P1 同步 401 / P2 SSE error）共用同一出口 `session.onAuthFailure`。
// - P1：请求层识别到 401 认证类错误后回调（请求层不 import store，§2.2 R2）；
// - P2：`chat` store 收到 `error` 事件时直接调用。
const session = useSessionStore(pinia)
setAuthFailureSink(() => session.onAuthFailure('HTTP_401'))
// §4.6.3 第 6 步：清理完成后 `router.replace('/login')`（用 replace，避免回退到已清空的私有页）。
session.registerExpiredNavigator(() => {
  if (router.currentRoute.value.name !== 'login') void router.replace({ name: 'login' })
})

app.use(router)
app.mount('#app')
