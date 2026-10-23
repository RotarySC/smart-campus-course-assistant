<script setup lang="ts">
/** `.card-row` / `.card-row--2`：`.card-row--2` **≥sm 才生效**（rb.css:181–182）。 */
withDefaults(defineProps<{ columns?: 1 | 2 }>(), { columns: 1 })
</script>

<template>
  <div class="card-row" :class="{ 'card-row--2': columns === 2 }"><slot /></div>
</template>
