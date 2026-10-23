// vite.config.ts —— 依据 docs/校园课程智能助手_前端详细设计_v0.1.md §14.1
// 硬约束：不引 UI 框架 / 不引 CSS 框架；Admin* 视图动态 import；生产 sourcemap=false。
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  base: process.env.VITE_BASE ?? '/',
  build: {
    target: 'es2022',
    sourcemap: false, // §14.1 红线：错误栈不得外泄
    assetsInlineLimit: 4096, // §14.1 显式写死，防止被上层配置覆盖
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
        },
      },
    },
  },
  server: {
    port: 5173,
    // §14.3：开发期同源代理。本骨架走 mock 传输层（VITE_USE_MOCK 默认 true），
    // 代理配置保留以便切到真实后端时无需改配置。
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_PROXY ?? 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
})
