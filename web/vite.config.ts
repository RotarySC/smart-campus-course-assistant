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
    // 编辑器/脚本的原子写会短暂产生 .tmp / .tmpdir（Windows 上 chokidar 可能 EBUSY 让 dev server 崩），
    // 这些不是源码，忽略即可。
    watch: {
      ignored: ['**/*.tmp', '**/*.tmpdir/**', '**/.cdp-*/**', '**/reports/artifacts/**'],
    },
    // §14.3：开发期同源代理 → 真实后端。
    // 端口按 docs/phases/PHASE-PLAN.md §8.2 的分配：公共 API = 8100（设计文档 §14.3 的 8080 是通用示例，
    // 本项目以阶段计划的端口分配为准）。mock 仅在显式 `VITE_USE_MOCK=true` 时启用，不走本代理。
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_PROXY ?? 'http://127.0.0.1:8100',
        changeOrigin: true,
      },
    },
  },
})
