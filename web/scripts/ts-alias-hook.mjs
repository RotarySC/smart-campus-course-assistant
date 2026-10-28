/**
 * ⚠ 沙箱专用 / 仅测试 —— 最小 ESM 解析钩子。
 *
 * ## 它是什么
 * 给 Node 补两条本项目的路径约定，**只有这两条**：
 *   1. `@/x` → `<web>/src/x`（与 `tsconfig.json` 的 `paths`、`vite.config.ts` 的 `resolve.alias` 同源）；
 *   2. 无扩展名的相对/别名路径补 `.ts`（TS 允许省略，Node 不允许）。
 *
 * ## 它不是什么（边界，别误读）
 * - **不参与构建**：`pnpm build` / `pnpm dev` 走的是标准 Vite 配置，与本文件无关；
 *   本文件不注册任何 Vite 插件、不改 `vite.config.ts` / `tsconfig.json`、不碰 `src/**`。
 * - **不是构建证据**：它的存在只是让 `scripts/smoke-sse.mjs`（**纯函数**级冒烟）
 *   能在没有打包器的进程里 import 到源码。**任何依赖本钩子的结论都不能当作「构建通过」**。
 * - **不渲染任何组件**：没有 `.vue` 加载器、没有 SSR。曾用于渲染的 3 个文件已删除。
 *
 * ## 为什么需要它
 * 本沙箱拒绝 `child_process` 的 `stdio:'pipe'` 通道（`spawn EPERM`），
 * 而 Vite 用该通道起 esbuild 服务、并用来 bundle `vite.config.ts` → `vite build` / `vite dev` 在沙箱内无法启动。
 *
 * ## 实现说明
 * 用 `module.registerHooks()`（Node 22.15+ 的**同线程**钩子 API），因此
 * 单个文件即可自注册，不需要「主线程注册 + 独立钩子模块」那套两文件结构。
 * 只挂 `resolve`，**不挂 `load`** —— 不 shortCircuit 才能让 Node 内置的 TS 类型剥离正常工作
 * （早先版本挂了 `load` 并返回源码，直接撞上 `SyntaxError: Unexpected token ':'`）。
 *
 * 用法：`node --import ./scripts/ts-alias-hook.mjs scripts/smoke-sse.mjs`
 */

import { existsSync, statSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { dirname, join, resolve as presolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const WEB_ROOT = presolve(dirname(fileURLToPath(import.meta.url)), '..')
const EXT_CANDIDATES = ['', '.ts', '.mts', '.js', '.mjs']

function firstExisting(base) {
  for (const ext of EXT_CANDIDATES) {
    const p = base + ext
    if (existsSync(p) && statSync(p).isFile()) return p
  }
  for (const ext of ['.ts', '.js']) {
    const p = join(base, `index${ext}`)
    if (existsSync(p)) return p
  }
  return null
}

registerHooks({
  resolve(specifier, context, next) {
    // ① `@/x` 别名
    if (specifier.startsWith('@/')) {
      const found = firstExisting(join(WEB_ROOT, 'src', specifier.slice(2)))
      if (found) return next(pathToFileURL(found).href, context)
    }
    // ② 相对路径补扩展名
    if ((specifier.startsWith('./') || specifier.startsWith('../')) && context.parentURL?.startsWith('file:')) {
      const found = firstExisting(presolve(dirname(fileURLToPath(context.parentURL)), specifier))
      if (found) return next(pathToFileURL(found).href, context)
    }
    return next(specifier, context)
  },
})
