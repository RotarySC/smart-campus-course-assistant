<script setup lang="ts">
/**
 * `sr` 族（01-shell-navigation.md §8；rb.css:113–114）。
 * 只放短标签，**不用 `display:none` 代替**（那样读屏也拿不到）。
 */
withDefaults(defineProps<{ as?: string }>(), { as: 'span' })
</script>

<template>
  <component :is="as" class="sr-only"><slot /></component>
</template>
