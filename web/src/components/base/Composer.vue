<script setup lang="ts">
/**
 * `composer` 族（03-conversation.md §Composer；rb.css:266–273）。
 *
 * 硬要求：`<form>` + **可见 `<label for>`** + `aria-describedby` 指上限说明；
 * **不得承载任何路由/深链语义** —— 正文不进 URL（§7.5、SRS DEC-01）。
 * 空白不可提交（按钮禁用，content-spec S02）。
 */
import { computed } from 'vue'
import { codePointLength } from '@/domain/format'

const props = withDefaults(
  defineProps<{ modelValue: string; maxlength?: number; disabled?: boolean; pending?: boolean; label: string; hint?: string }>(),
  { maxlength: 2000, disabled: false, pending: false, hint: '' },
)
const emit = defineEmits<{ 'update:modelValue': [string]; submit: []; stop: [] }>()

const fieldId = 'composer-input'
const hintId = 'composer-hint'
const count = computed(() => codePointLength(props.modelValue))
const canSubmit = computed(() => props.modelValue.trim().length > 0 && count.value <= props.maxlength)

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLTextAreaElement).value)
}
function onSubmit() {
  if (!canSubmit.value || props.disabled) return
  emit('submit')
}
</script>

<template>
  <form class="composer" @submit.prevent="onSubmit">
    <label class="field__label" :for="fieldId">{{ label }}</label>
    <div class="composer__row">
      <textarea
        :id="fieldId"
        class="textarea"
        :value="modelValue"
        :maxlength="maxlength"
        :disabled="disabled || pending"
        :aria-describedby="hintId"
        @input="onInput"
        @keydown.enter.exact.prevent="onSubmit"
      />
      <div class="stack">
        <slot name="actions" />
      </div>
    </div>
    <div class="row">
      <span :id="hintId" class="field__hint">{{ hint }}</span>
      <span class="composer__count">{{ count }} / {{ maxlength }}</span>
    </div>
  </form>
</template>
