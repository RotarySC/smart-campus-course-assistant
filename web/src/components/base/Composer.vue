<script setup lang="ts">
/**
 * `composer` 族（03-conversation.md §Composer；rb.css:266–273 + 阶段 B 新增块）。
 *
 * 结构（§7）：「标签 + 输入容器（textarea + 提示行/发送）+ 计数行」三段。
 * 硬要求：`<form>` + **可见 `<label for>`** + `aria-describedby` 指提示与上限；
 * **不得承载任何路由/深链语义** —— 正文不进 URL（§7.5、SRS DEC-01）。
 * 空白不可提交（按钮禁用，content-spec S02）。
 *
 * 自动增高：52→200px 由**行内 height** 承担（已登记例外，不进 CSS 门禁）；
 * 上限用 `--composer-input-max-h` 在 CSS 里封顶，超出后内部滚动。
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { codePointLength } from '@/domain/format'

const props = withDefaults(
  defineProps<{
    modelValue: string
    maxlength?: number
    disabled?: boolean
    pending?: boolean
    label: string
    hint?: string
    enterHint?: string
  }>(),
  { maxlength: 2000, disabled: false, pending: false, hint: '', enterHint: '' },
)
const emit = defineEmits<{ 'update:modelValue': [string]; submit: []; stop: [] }>()

const fieldId = 'composer-input'
const hintId = 'composer-enter-hint'
const limitId = 'composer-limit'
const inputEl = ref<HTMLTextAreaElement | null>(null)

const count = computed(() => codePointLength(props.modelValue))
const canSubmit = computed(() => props.modelValue.trim().length > 0 && count.value <= props.maxlength)
const describedBy = `${hintId} ${limitId}`

function autoGrow() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLTextAreaElement).value)
  autoGrow()
}

function onSubmit() {
  if (!canSubmit.value || props.disabled) return
  emit('submit')
}

// 程序化填值（示例入口只填不提交）也要重算高度。
watch(
  () => props.modelValue,
  () => void nextTick(autoGrow),
)
onMounted(autoGrow)
</script>

<template>
  <form class="composer" @submit.prevent="onSubmit">
    <label class="field__label" :for="fieldId">{{ label }}</label>
    <div class="composer__box">
      <textarea
        ref="inputEl"
        :id="fieldId"
        class="textarea composer__input"
        rows="1"
        :value="modelValue"
        :maxlength="maxlength"
        :disabled="disabled || pending"
        :aria-describedby="describedBy"
        @input="onInput"
        @keydown.enter.exact.prevent="onSubmit"
      />
      <div class="composer__bar">
        <span :id="hintId" class="composer__hint">{{ enterHint }}</span>
        <slot name="actions" />
      </div>
    </div>
    <div class="composer__foot">
      <span :id="limitId" class="field__hint">{{ hint }}</span>
      <span class="composer__count">{{ count }} / {{ maxlength }}</span>
    </div>
  </form>
</template>
