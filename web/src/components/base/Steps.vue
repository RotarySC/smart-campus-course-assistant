<script setup lang="ts">
/**
 * `steps` 族（02-actions-status.md §Steps；rb.css:245–263）。
 *
 * `<ol>` 语义保留；toggle 是 `.sr-only` checkbox 且必须是 `.steps__body` 的**前序兄弟**。
 * <480 默认折叠（摘要一行 + 可展开），≥480 摘要 `display:none`、body 常显。
 * W2 的焦点补偿（`.steps__toggle:focus-visible ~ .steps__summary`）在 `base.css` 的 steps 块里。
 */
import { ref } from 'vue'
import { ICONS } from './icons'

const props = withDefaults(defineProps<{ summary?: string; modelValue?: boolean }>(), {
  summary: '',
  modelValue: false,
})
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const open = ref(props.modelValue)
const id = `steps-${Math.random().toString(36).slice(2, 8)}`

function toggle(e: Event) {
  open.value = (e.target as HTMLInputElement).checked
  emit('update:modelValue', open.value)
}
</script>

<template>
  <div class="stack">
    <input :id="id" class="sr-only steps__toggle" type="checkbox" :checked="open" @change="toggle" />
    <label class="steps__summary" :for="id">
      <span aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
          <path v-for="(d, i) in ICONS.listChecks" :key="i" :d="d" />
        </svg>
      </span>
      <span>{{ summary }}</span>
    </label>
    <ol class="steps steps__body"><slot /></ol>
  </div>
</template>
