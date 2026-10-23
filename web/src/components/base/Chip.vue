<script setup lang="ts">
/**
 * `chip` 族（02-actions-status.md §Chip；rb.css:392–396）。
 * `.chips` 是纯布局容器，**不加 `role`**；`a.chip` 无 `:active`/`[disabled]`/`[aria-current]`。
 */
import { RouterLink } from 'vue-router'

defineProps<{ to: string }>()
</script>

<template>
  <RouterLink class="chip" :to="to"><slot name="icon" /><slot /></RouterLink>
</template>
