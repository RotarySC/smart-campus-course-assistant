<script setup lang="ts">
/** `utility` 族（04-forms-data.md §八；rb.css:387）。 */
withDefaults(defineProps<{ as?: string }>(), { as: 'span' })
</script>

<template>
  <component :is="as" class="muted"><slot /></component>
</template>
