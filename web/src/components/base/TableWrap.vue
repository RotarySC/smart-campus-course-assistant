<script setup lang="ts">
/**
 * `table` 族的滚动容器（04-forms-data.md §五/§六；rb.css:334）。
 *
 * `<768` 时 `.table-wrap--stackable` 去掉横向滚动、去掉边框与底色，
 * 让表格自身卡片化（rb.css:377）。管理端窄屏**允许**表格自身横向滚动（NFR-COMP-001）。
 */
withDefaults(defineProps<{ stackable?: boolean }>(), { stackable: true })
</script>

<template>
  <div class="table-wrap" :class="{ 'table-wrap--stackable': stackable }"><slot /></div>
</template>
