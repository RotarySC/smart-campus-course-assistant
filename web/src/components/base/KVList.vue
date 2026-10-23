<script setup lang="ts">
/**
 * `kv` 族（03-conversation.md §KVList；rb.css:381–384）。
 * 必须用 `dl`/`dt`/`dd`；`.kv__row` 是 `.kv` 的**直接子元素**。
 * W3：`.kv__row` 第 2 轨改 `minmax(0,1fr)`（`1fr` 的下限是 min-content，长串会撑破页面）。
 */
defineProps<{ items: Array<{ k: string; v: string }> }>()
</script>

<template>
  <dl class="kv">
    <div v-for="item in items" :key="item.k" class="kv__row">
      <dt class="kv__k">{{ item.k }}</dt>
      <dd class="kv__v">{{ item.v }}</dd>
    </div>
  </dl>
</template>
