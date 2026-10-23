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
import Btn from '@/components/base/Btn.vue'
import { NAV_ITEMS } from '@/router/routes'
import type { ActiveNav } from '@/router/routes'
import { S01, CHROME } from '@/domain/copy'
import { useSessionStore } from '@/stores/session'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const session = useSessionStore()
const ui = useUiStore()

const activeNav = computed<ActiveNav | undefined>(() => route.meta.activeNav)
const showNav = computed(() => activeNav.value !== undefined)
const showAdmin = computed(() => session.canAdmin)
const navItems = computed(() => NAV_ITEMS.filter((i) => i.key !== 'admin' || showAdmin.value))

onMounted(() => ui.initBreakpoints())
onUnmounted(() => ui.disposeBreakpoints())
</script>

<template>
  <SkipLink />
  <AppBar v-if="showNav" :user-label="session.user?.display_name ?? ''">
    <template #brand>
      <BrandMark :name="S01.productName" />
    </template>
    <template #nav>
      <NavLink v-for="item in navItems" :key="item.key" :to="item.to" :current="activeNav === item.key">
        {{ item.appbar }}
      </NavLink>
    </template>
    <template #user>
      <Btn size="sm" variant="ghost" @click="session.logout()">{{ CHROME.logout }}</Btn>
    </template>
  </AppBar>

  <main id="main" tabindex="-1" :aria-label="CHROME.mainLandmark">
    <RouterView />
  </main>

  <TabBar v-if="showNav" :active-nav="activeNav" :show-admin="showAdmin" />

  <!-- 流式播报的独立 live region：`polite`，且**绝不**抢焦点（NFR-UX-001）。 -->
  <p class="sr-only" aria-live="polite" aria-atomic="true">{{ ui.liveMessage }}</p>
</template>
