<script setup lang="ts">
/**
 * `wrap` 族（01-shell-navigation.md §9；rb.css:164–169）。
 * 每页至少一层；嵌套时内层**只清左右内边距**、**保留 720px**（助手列仍居中）。
 */
withDefaults(defineProps<{ assistant?: boolean }>(), { assistant: false })
</script>

<template>
  <div class="wrap" :class="{ 'wrap--assistant': assistant }"><slot /></div>
</template>
