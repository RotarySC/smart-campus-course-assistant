<script setup lang="ts">
/**
 * `App.vue` = 外壳（顶栏 / 底部标签栏 / 路由出口 + `main#main`）。
 *
 * - `GlobalRoot`（族 1）在此内联：`lang="zh-CN"` 在 index.html、`scroll-padding-top` 在 global.css。
 * - `<main id="main">` 必须存在 —— skip-link 的目标（§7.6）。10 条路由共用本外壳。
 * - live region 用 `aria-live="polite"` 的**独立节点**，只播文案、不播令牌（§6.11、§12）。
 * - `ui.initBreakpoints()` 只在**这里**调一次；组件不得各自 `resize`（§8.3）。
 */
import { computed, onMounted, onUnmounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppBar from '@/components/base/AppBar.vue'
import TabBar from '@/components/base/TabBar.vue'
import BrandMark from '@/components/base/BrandMark.vue'
import NavLink from '@/components/base/NavLink.vue'
import SkipLink from '@/components/base/SkipLink.vue'
import { NAV_ITEMS } from '@/router/routes'
import type { ActiveNav } from '@/router/routes'
import { S01, CHROME } from '@/domain/copy'
import { ICONS } from '@/components/base/icons'
import type { IconName } from '@/components/base/icons'
import { useSessionStore } from '@/stores/session'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const session = useSessionStore()
const ui = useUiStore()

const activeNav = computed<ActiveNav | undefined>(() => route.meta.activeNav)
const showNav = computed(() => activeNav.value !== undefined)
const showAdmin = computed(() => session.canAdmin)
const navItems = computed(() => NAV_ITEMS.filter((i) => i.key !== 'admin' || showAdmin.value))

/**
 * 导航图标只属于展示层，放在外壳里映射（不放 `routes.ts`：路由数据不依赖组件资源）。
 * 顶栏 18×18、底栏 22×22 见 01-shell-navigation.md §4/§6。
 */
const NAV_ICON: Record<ActiveNav, IconName> = {
  assistant: 'messageCircle',
  schedules: 'calendar',
  plans: 'listChecks',
  admin: 'sliders',
}

onMounted(() => ui.initBreakpoints())
onUnmounted(() => ui.disposeBreakpoints())
</script>

<template>
  <SkipLink />
  <AppBar v-if="showNav" :user-label="session.user?.display_name ?? ''" @logout="session.logout()">
    <template #brand>
      <BrandMark :name="S01.productName" />
    </template>
    <template #nav>
      <NavLink v-for="item in navItems" :key="item.key" :to="item.to" :current="activeNav === item.key">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
          <path v-for="(d, i) in ICONS[NAV_ICON[item.key]]" :key="i" :d="d" />
        </svg>
        {{ item.appbar }}
      </NavLink>
    </template>
  </AppBar>

  <main id="main" tabindex="-1" :aria-label="CHROME.mainLandmark">
    <RouterView />
  </main>

  <TabBar v-if="showNav" :active-nav="activeNav" :show-admin="showAdmin">
    <template #icon="{ item }">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
        <path v-for="(d, i) in ICONS[NAV_ICON[item]]" :key="i" :d="d" />
      </svg>
    </template>
  </TabBar>

  <!-- 底部标签栏占位：**只有渲染了 TabBar 才有这块留白**（<768）。
       早先是给 body 无条件加 padding-bottom，于是登录页（没有标签栏）也白白多出 56px 可滚动空白。 -->
  <div v-if="showNav" class="tabbar-spacer"></div>

  <!-- 流式播报的独立 live region：`polite`，且**绝不**抢焦点（NFR-UX-001）。 -->
  <p class="sr-only" aria-live="polite" aria-atomic="true">{{ ui.liveMessage }}</p>
</template>
