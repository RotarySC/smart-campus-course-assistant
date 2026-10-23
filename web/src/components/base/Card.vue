<script setup lang="ts">
/**
 * `card` 族（03-conversation.md §Card；rb.css:185–190）。
 * `.card` 不得内嵌 `.card`；卡片自身**不设 `tabindex`**。
 */
defineProps<{ title?: string }>()
</script>

<template>
  <section class="card">
    <header v-if="title || $slots.head" class="card__head">
      <h2 v-if="title" class="field__label">{{ title }}</h2>
      <slot name="head" />
    </header>
    <div class="card__body"><slot /></div>
    <footer v-if="$slots.foot" class="card__foot"><slot name="foot" /></footer>
  </section>
</template>
