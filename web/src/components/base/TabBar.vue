<script setup lang="ts">
/**
 * `tabbar` 族（01-shell-navigation.md §5/§6；rb.css:149–161）。
 *
 * 列数 = `--tabbar-cols`（由 CSS 消费）；**<768 才渲染**由媒体查询决定，
 * 且**不在 JS 里按宽度增删节点**（§7.4）。两套载体共用同一份数据与同一个 `activeNav`。
 *
 * 2026-10-27 修正：列数必须 = **实际渲染的项数**（学生 3 项、管理员 4 项）。
 * 原实现把 `--tabbar-cols` 写死 4，学生账号只有 3 项时第 4 列空着，
 * 三项各占 1/4 宽、整体左偏 —— 用户实测「下方导航栏不等宽」。
 * 每一项的可见性只由 `showAdmin` 决定，与视口宽度无关，所以这里在 JS 里算列数是安全的。
 */
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { NAV_ITEMS } from '@/router/routes'
import type { ActiveNav } from '@/router/routes'
import { CHROME } from '@/domain/copy'

const props = withDefaults(defineProps<{ activeNav?: ActiveNav; showAdmin?: boolean }>(), { showAdmin: false })

/** 渲染项 = 导航表去掉「管理」除非当前账号可见。列数跟着它走，不做第二处真源。 */
const items = computed(() => NAV_ITEMS.filter((i) => i.key !== 'admin' || props.showAdmin))
</script>

<template>
  <!-- 与 AppBar 共用同一个 landmark 名：两者由媒体查询互斥显示（另一方 display:none，
       不进无障碍树），因此同一视口下只会暴露一个「主导航」。 -->
  <nav class="tabbar" :aria-label="CHROME.primaryNav" :style="{ '--tabbar-cols': items.length }">
    <RouterLink
      v-for="item in items"
      :key="item.key"
      class="tabbar__item"
      :to="item.to"
      :aria-current="activeNav === item.key ? 'page' : undefined"
    >
      <!-- 注意：插槽名固定为 `icon`，条目 key 必须走**另一个** prop。
           写成 name="icon" :name="item.key" 会被编译器判成「插槽名被绑定值覆盖」，
           插槽实际变成 item.key（'assistant'），传内容的地方永远拿不到。 -->
      <span class="tabbar__ico" aria-hidden="true"><slot name="icon" :item="item.key" /></span>
      <span class="tabbar__label">{{ item.tabbar }}</span>
    </RouterLink>
  </nav>
</template>
