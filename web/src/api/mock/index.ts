/**
 * 安装 mock 传输层。
 *
 * 默认开启（`.env.development` 的 `VITE_USE_MOCK=true`）；
 * `VITE_USE_MOCK=false` 时保持 `httpTransport`，即走真实 `fetch` + `server.proxy`（§14.3）。
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

export function useMock(): boolean {
  const v = import.meta.env.VITE_USE_MOCK
  return v === undefined || v === '' ? true : v !== 'false'
}
