<script setup lang="ts">
/**
 * `draft` 族（03-conversation.md §Draft；rb.css:291–298）。
 *
 * 三态**没有新增 class**：
 *   - `unsaved` → `.draft`（虚线琥珀边 + 文字标记）
 *   - `saved` → `.draft--saved`（实线；`plan_id` + 对勾 + 文字）
 *   - `unconfirmed` → 保持 `.draft` 外观 + `.notice--warn role="status"`
 *     （rb.css 无 `.draft--failed`，**不得新增**；未知 ≠ 失败，FR-CHAT-005）
 */
withDefaults(defineProps<{ state: 'unsaved' | 'saved' | 'unconfirmed' }>(), { state: 'unsaved' })
</script>

<template>
  <section class="draft" :class="{ 'draft--saved': state === 'saved' }">
    <header class="draft__head"><slot name="head" /></header>
    <slot />
    <div v-if="$slots.actions" class="card__foot"><slot name="actions" /></div>
  </section>
</template>
