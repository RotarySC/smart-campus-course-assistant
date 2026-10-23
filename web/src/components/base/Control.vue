<script setup lang="ts">
/**
 * `control` 族（04-forms-data.md §二；rb.css:319–328）。
 * 三态一组件：`input` / `select` / `textarea`。
 *
 * `[readonly]` 与 `[disabled]` **视觉可分**（只读=灰底无边框语义、禁用=降透明度）；
 * 出错时加 `aria-invalid`（语义）与 `.field--invalid`（视觉，由 Field 提供）。
 * 只读要**说明原因**，原因文案由调用方以冻结文案给出（如 S10.codeReadonlyNote）。
 */
withDefaults(
  defineProps<{
    as?: 'input' | 'select' | 'textarea'
    modelValue: string
    type?: string
    id: string
    readonly?: boolean
    disabled?: boolean
    invalid?: boolean
    /** `aria-describedby` 的目标 id 列表（hint / error）。 */
    describedby?: string
    autocomplete?: string
    maxlength?: number
  }>(),
  { as: 'input', type: 'text', readonly: false, disabled: false, invalid: false, describedby: '', autocomplete: 'off', maxlength: undefined },
)
const emit = defineEmits<{ 'update:modelValue': [string]; blur: [] }>()

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value)
}
</script>

<template>
  <textarea
    v-if="as === 'textarea'"
    :id="id"
    class="textarea"
    :value="modelValue"
    :readonly="readonly"
    :disabled="disabled"
    :aria-invalid="invalid ? 'true' : undefined"
    :aria-describedby="describedby || undefined"
    :maxlength="maxlength"
    @input="onInput"
    @blur="$emit('blur')"
  />
  <select
    v-else-if="as === 'select'"
    :id="id"
    class="select"
    :value="modelValue"
    :disabled="disabled"
    :aria-invalid="invalid ? 'true' : undefined"
    :aria-describedby="describedby || undefined"
    @change="onInput"
    @blur="$emit('blur')"
  >
    <slot />
  </select>
  <input
    v-else
    :id="id"
    class="input"
    :type="type"
    :value="modelValue"
    :readonly="readonly"
    :disabled="disabled"
    :aria-invalid="invalid ? 'true' : undefined"
    :aria-describedby="describedby || undefined"
    :autocomplete="autocomplete"
    :maxlength="maxlength"
    @input="onInput"
    @blur="$emit('blur')"
  />
</template>
