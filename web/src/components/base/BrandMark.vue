<script setup lang="ts">
/**
 * `brand` 族（01-shell-navigation.md §3；rb.css:132–134）。
 * 标记 SVG 必须 `aria-hidden="true" focusable="false"`；`white-space:nowrap` 保证 320px 不折行。
 */
import { ICONS } from './icons'

withDefaults(defineProps<{ size?: 'sm' | 'lg'; name?: string }>(), { size: 'sm', name: '' })
</script>

<template>
  <span class="appbar__brand">
    <span :class="size === 'lg' ? 'login__mark' : 'appbar__mark'" aria-hidden="true">
      <svg
        :width="size === 'lg' ? 22 : 16"
        :height="size === 'lg' ? 22 : 16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.75"
        stroke-linecap="round"
        stroke-linejoin="round"
        focusable="false"
      >
        <path v-for="(d, i) in ICONS.library" :key="i" :d="d" />
      </svg>
    </span>
    <span :class="size === 'lg' ? 'login__name' : ''">
      <slot>{{ name }}</slot>
    </span>
  </span>
</template>
