<script setup lang="ts">
/**
 * `appbar` 族（01-shell-navigation.md §2；rb.css:121–137）。
 * `<header>`；`nav` 里当前项 `aria-current="page"`。管理端入口只对 `role==='admin'` 渲染。
 */
import { CHROME } from '@/domain/copy'

defineProps<{ userLabel?: string }>()
</script>

<template>
  <header class="appbar">
    <div class="appbar__inner">
      <slot name="brand" />
      <nav class="appbar__nav" :aria-label="CHROME.primaryNav"><slot name="nav" /></nav>
      <div class="appbar__user">
        <slot name="user" />
        <span v-if="userLabel" class="muted small">{{ userLabel }}</span>
      </div>
    </div>
  </header>
</template>
