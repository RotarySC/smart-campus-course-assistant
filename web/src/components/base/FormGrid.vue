<script setup lang="ts">
/**
 * `.form-grid` / `.form-grid--2`（04-forms-data.md §三；rb.css:311–313）。
 * `.field--wide` 只在 **≥sm 且父级带 `--2`** 时跨列。
 */
withDefaults(defineProps<{ columns?: 1 | 2 }>(), { columns: 1 })
</script>

<template>
  <div class="form-grid" :class="{ 'form-grid--2': columns === 2 }"><slot /></div>
</template>
