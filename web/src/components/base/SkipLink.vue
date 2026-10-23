<script setup lang="ts">
/**
 * `skiplink` 族（01-shell-navigation.md §7；rb.css:115–118）。
 *
 * 必须是页面**第一个**可聚焦元素；`href` 指向真实存在的 id（App.vue 提供 `<main id="main">`）。
 */
import { CHROME } from '@/domain/copy'

withDefaults(defineProps<{ target?: string; label?: string }>(), {
  target: CHROME.mainId,
  // 组件 chrome 文案，归组件规格管辖（design/system/README.md 裁决 13）。
  label: CHROME.skipToMain,
})
</script>

<template>
  <a class="skip-link" :href="`#${target}`">{{ label }}</a>
</template>
