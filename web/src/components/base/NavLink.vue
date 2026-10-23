<script setup lang="ts">
/**
 * `navlink` 族（01-shell-navigation.md §4；rb.css:138–144）。
 * `<a>` + `aria-current="page"`；≥44px。`:hover` 与 `[aria-current]` 是 rb.css 里**仅有的两个**状态。
 */
import { RouterLink } from 'vue-router'

defineProps<{ to: string; current?: boolean }>()
</script>

<template>
  <RouterLink class="navlink" :to="to" :aria-current="current ? 'page' : undefined">
    <slot />
  </RouterLink>
</template>
