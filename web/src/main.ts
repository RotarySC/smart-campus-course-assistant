/**
 * 应用入口。
 *
 * 顺序有意固定：
 *   1. 安装 mock 传输层（**必须在任何请求之前**）；
 *   2. `import './styles/tokens.css'`（**静态 import** → 进全局 chunk，§14.1 约束 3）；
 *   3. global.css（元素级全局规则）→ base.css（27 个组件族）；
 *   4. 建 Pinia → 注册路由守卫 → 挂载。
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import '@/styles/tokens.css'
import '@/styles/global.css'
import '@/styles/base.css'

import App from './App.vue'
import { router } from './router'
import { installMockTransport, useMock } from './api/mock'
import { setTraceSink } from './api/client'

if (useMock()) installMockTransport()

// 埋点：只记 method/path/status/request_id/耗时，**不记请求体与响应体正文**（NFR-PRIV-001）。
// 本骨架不上报（`VITE_TELEMETRY_ENDPOINT` 留空即不上报），只落到内存数组供调试。
export const traces: Array<Record<string, unknown>> = []
setTraceSink((t) => {
  traces.push({ ...t })
})

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
