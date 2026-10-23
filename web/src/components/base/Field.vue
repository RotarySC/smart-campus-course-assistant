<script setup lang="ts">
/**
 * `field` 族（04-forms-data.md §一；rb.css:314–318）。
 *
 * 硬要求：可见 `<label for>`；必填标「必填」（content-spec:54 冻结的标记）；
 * 错误**就近**显示并 `aria-describedby` 关联；**不得发明** `.field--valid/--warning/--loading`。
 */
import { ICONS } from './icons'
import { S01 } from '@/domain/copy'

withDefaults(
  defineProps<{ label: string; forId: string; required?: boolean; hint?: string; error?: string | null; wide?: boolean }>(),
  { required: false, hint: '', error: null, wide: false },
)
</script>

<template>
  <div class="field" :class="{ 'field--invalid': !!error, 'field--wide': wide }">
    <label class="field__label" :for="forId">
      {{ label }}
      <span v-if="required" class="field__req">{{ S01.required }}</span>
    </label>
    <slot />
    <span v-if="hint" class="field__hint" :id="`${forId}-hint`">{{ hint }}</span>
    <span v-if="error" class="field__error" :id="`${forId}-error`">
      <span aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
          <path v-for="(d, i) in ICONS.circleAlert" :key="i" :d="d" />
        </svg>
      </span>
      <span>{{ error }}</span>
    </span>
    <slot name="label-extra" />
  </div>
</template>
