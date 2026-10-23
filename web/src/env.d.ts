/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_BASE?: string
  readonly VITE_DEV_PROXY?: string
  readonly VITE_TELEMETRY_ENDPOINT?: string
  readonly VITE_BUILD_SHA?: string
  /** 本骨架专用：'false' 才关闭 mock 传输层。默认开启。 */
  readonly VITE_USE_MOCK?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}
