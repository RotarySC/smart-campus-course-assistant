/**
 * 安装 / 卸载 mock 传输层。
 *
 * mock 是**开发夹具**，不是默认路径（PHASE-PLAN D5：验收以真实后端为准）：
 *   - 仅当 `VITE_USE_MOCK === 'true'` 时安装；
 *   - 未设置、空串或其他值 → 保持 `httpTransport`，即原生 `fetch` + `server.proxy` → 127.0.0.1:8100（§14.3）。
 *
 * 显式 opt-in 的理由：生产构建不会带上 `.env.development`，若默认开启 mock，
 * 一次忘记设置就会把「假数据」当成真实产品发布。默认走真实后端，失败可见，更安全。
 *
 * **不产生任何外部请求**：所有 URL 都是同源 `/api/v1/*`。
 */

import { httpTransport, setTransport } from '../transport'
import { handleMock } from './handlers'

export function installMockTransport(): void {
  setTransport(({ url, init }) => handleMock(url, init))
}

export function uninstallMockTransport(): void {
  setTransport(httpTransport)
}

/** mock 开关：**只有显式 `'true'` 才启用**（默认 false = 真实后端）。 */
export function useMock(): boolean {
  return import.meta.env.VITE_USE_MOCK === 'true'
}
