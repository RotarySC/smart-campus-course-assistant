<script setup lang="ts">
/** `utility` 族（04-forms-data.md §八；rb.css:388）。 */
withDefaults(defineProps<{ as?: string }>(), { as: 'span' })
</script>

<template>
  <component :is="as" class="small"><slot /></component>
</template>
