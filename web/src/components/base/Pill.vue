<script setup lang="ts">
/**
 * `pill` 族（02-actions-status.md §Pill；rb.css:209–220）。
 *
 * 硬要求：**状态三重表达** = 图标 + 文字 + 颜色。因此 `icon` 槽是**必需**的，
 * 缺项时开发期抛错（CONTRACT §3.7 第 7 条、NFR-UX-001）。
 * 7 个 variant 必须逐个映射到 rb.css 已存在的修饰类，没有对应类就不渲染。
 */
import { onMounted, useSlots } from 'vue'

const props = withDefaults(
  defineProps<{ variant?: 'default' | 'ok' | 'warn' | 'pending' | 'danger' | 'info' | 'evidence' | 'advice' }>(),
  { variant: 'default' },
)
const slots = useSlots()

const VARIANT_CLASS: Record<string, string> = {
  default: '',
  ok: 'pill--ok',
  warn: 'pill--warn',
  pending: 'pill--pending',
  danger: 'pill--danger',
  info: 'pill--info',
  evidence: 'pill--evidence',
  advice: 'pill--advice',
}

onMounted(() => {
  if (!slots.icon) {
    // 开发期警告，不是运行时异常：缺图标的胶囊在灰度/色盲下会退化成「只剩颜色」。
    console.warn(`[Pill] variant="${props.variant}" 缺少 #icon 槽：状态必须图标+文字+颜色三重（NFR-UX-001）。`)
  }
})
</script>

<template>
  <span class="pill" :class="VARIANT_CLASS[variant]">
    <slot name="icon" />
    <slot />
  </span>
</template>
