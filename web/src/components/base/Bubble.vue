<script setup lang="ts">
/**
 * `chat` 族的气泡（03-conversation.md §Chat；rb.css:240–242）。
 * W3：`.bubble` 加 `overflow-wrap:anywhere`（非表格容器才用 anywhere），在 base.css 消费。
 */
</script>

<template>
  <div class="bubble"><slot /></div>
</template>
