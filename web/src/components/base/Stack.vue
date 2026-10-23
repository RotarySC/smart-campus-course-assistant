<script setup lang="ts">
/** `utility` 族（04-forms-data.md §八；rb.css:389）。纯布局容器，不承载语义与焦点。 */
withDefaults(defineProps<{ as?: string }>(), { as: 'div' })
</script>

<template>
  <component :is="as" class="stack"><slot /></component>
</template>
