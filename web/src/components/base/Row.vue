<script setup lang="ts">
/** `utility` 族（04-forms-data.md §八；rb.css:390）。 */
withDefaults(defineProps<{ as?: string }>(), { as: 'div' })
</script>

<template>
  <component :is="as" class="row"><slot /></component>
</template>
