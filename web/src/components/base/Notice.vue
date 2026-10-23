<script setup lang="ts">
/**
 * `notice` 族（02-actions-status.md §Notice；rb.css:223–231）。
 *
 * `role` 按变体走：静态 `note`、成功 `status`、失败/警告 `alert`（§10.2 第 14 行）。
 * `alert` 的内容必须自解释 —— 所以 `#actions` 槽里的按钮文案也要是冻结文案。
 */
withDefaults(
  defineProps<{
    variant?: 'default' | 'info' | 'warn' | 'danger' | 'ok' | 'evidence'
    role?: 'note' | 'status' | 'alert'
  }>(),
  { variant: 'default', role: 'note' },
)

const VARIANT_CLASS: Record<string, string> = {
  default: '',
  info: 'notice--info',
  warn: 'notice--warn',
  danger: 'notice--danger',
  ok: 'notice--ok',
  evidence: 'notice--evidence',
}
</script>

<template>
  <div class="notice" :class="VARIANT_CLASS[variant]" :role="role">
    <span class="notice__ico" aria-hidden="true"><slot name="icon" /></span>
    <div>
      <slot />
      <div v-if="$slots.actions" class="row"><slot name="actions" /></div>
    </div>
  </div>
</template>
