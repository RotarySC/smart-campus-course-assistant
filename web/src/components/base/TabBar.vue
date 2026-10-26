<script setup lang="ts">
/**
 * `tabbar` 族（01-shell-navigation.md §5/§6；rb.css:149–161）。
 *
 * 列数 = `--tabbar-cols`（4，由 CSS 消费）；**<768 才渲染**由媒体查询决定，
 * 且**不在 JS 里按宽度增删节点**（§7.4）。两套载体共用同一份 4 项数据与同一个 `activeNav`。
 */
import { RouterLink } from 'vue-router'
import { NAV_ITEMS } from '@/router/routes'
import type { ActiveNav } from '@/router/routes'
import { CHROME } from '@/domain/copy'

withDefaults(defineProps<{ activeNav?: ActiveNav; showAdmin?: boolean }>(), { showAdmin: false })
</script>

<template>
  <!-- 与 AppBar 共用同一个 landmark 名：两者由媒体查询互斥显示（另一方 display:none，
       不进无障碍树），因此同一视口下只会暴露一个「主导航」。 -->
  <nav class="tabbar" :aria-label="CHROME.primaryNav">
    <RouterLink
      v-for="item in NAV_ITEMS.filter((i) => i.key !== 'admin' || showAdmin)"
      :key="item.key"
      class="tabbar__item"
      :to="item.to"
      :aria-current="activeNav === item.key ? 'page' : undefined"
    >
      <!-- 注意：插槽名固定为 `icon`，条目 key 必须走**另一个** prop。
           写成 name="icon" :name="item.key" 会被编译器判成「插槽名被绑定值覆盖」，
           插槽实际变成 item.key（'assistant'），传内容的地方永远拿不到。 -->
      <span aria-hidden="true"><slot name="icon" :item="item.key" /></span>
      <span>{{ item.tabbar }}</span>
    </RouterLink>
  </nav>
</template>
