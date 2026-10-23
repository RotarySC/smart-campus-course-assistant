<script setup lang="ts">
/**
 * `btn` 族（design/system/components/02-actions-status.md §Button；rb.css:193–206）。
 *
 * 要点（§10.2 第 11 行）：
 *   - 原生 `<button type>`；禁用用 `[disabled]`，**不用** `aria-disabled`；
 *   - 尺寸只有 `md` / `sm`（rb.css 无 `.btn--lg`），**没有对应修饰类就不渲染**；
 *   - 图标走 `#icon` 槽，由调用方给 `aria-hidden="true"`（装饰性）。
 */
withDefaults(defineProps<{ variant?: 'default' | 'primary' | 'danger' | 'ghost'; size?: 'md' | 'sm'; block?: boolean; disabled?: boolean; type?: 'button' | 'submit' | 'reset' }>(), {
  variant: 'default',
  size: 'md',
  block: false,
  disabled: false,
  type: 'button',
})
</script>

<template>
  <button
    class="btn"
    :class="[{ 'btn--primary': variant === 'primary', 'btn--danger': variant === 'danger', 'btn--ghost': variant === 'ghost' }, { 'btn--sm': size === 'sm' }, { 'btn--block': block }]"
    :type="type"
    :disabled="disabled"
  >
    <slot name="icon" />
    <slot />
  </button>
</template>
