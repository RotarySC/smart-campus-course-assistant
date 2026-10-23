<script setup lang="ts">
/**
 * `cite` 族的引用标记（03-conversation.md §Citation；rb.css:288）。
 *
 * 未验证引用标记必须与已验证引用**视觉可区分**：`.cite-mark--pending` = 琥珀虚下划线 + 独立可访问名
 * （SRS FR-QA-002、IF-007、content-spec:78）。
 */
withDefaults(defineProps<{ pending?: boolean; label?: string }>(), { pending: false, label: '' })
</script>

<template>
  <span :class="{ 'cite-mark--pending': pending }" :aria-label="label || undefined"><slot /></span>
</template>
