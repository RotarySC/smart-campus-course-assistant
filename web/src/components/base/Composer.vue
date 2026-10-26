<script setup lang="ts">
/**
 * `composer` 族（03-conversation.md §Composer；rb.css 阶段 B 输入条）。
 *
 * 结构（2026-10-26 改版，用户需求：一体式、贴底、圆形发送按钮）：
 *   **一个容器**里放 textarea + 底栏（字数 / 上限提示 / 发送按钮）。
 *   标签不再是可见 `<label>`，而是 **placeholder + `.sr-only` label** 双份：
 *   placeholder 只是视觉提示，读屏与浏览器自动填充仍需要真正的 `<label for>`。
 *   「Enter 发送 · Shift+Enter 换行」不再占一行，改为发送按钮的冒泡提示
 *   （`.btn--icon` 的 `data-tip`），同时保留 `.sr-only` 文案供 `aria-describedby`。
 *
 * 硬要求：`<form>` + `aria-describedby` 指「上限」与「快捷键」两处说明；
 * **不得承载任何路由/深链语义** —— 正文不进 URL（§7.5、SRS DEC-01）。
 * 空白不可提交（按钮禁用，content-spec S02）。
 *
 * 自动增高：min 52 / max 200 由 CSS token 封顶；中间高度由**行内 height** 承担
 * （已登记例外，不进 CSS 门禁），超出后内部滚动。
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

defineExpose({ hintId })

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
    <div class="composer__box">
      <label class="sr-only" :for="fieldId">{{ label }}</label>
      <textarea
        ref="inputEl"
        :id="fieldId"
        class="textarea composer__input"
        rows="1"
        :value="modelValue"
        :placeholder="label"
        :maxlength="maxlength"
        :disabled="disabled || pending"
        :aria-describedby="describedBy"
        @input="onInput"
        @keydown.enter.exact.prevent="onSubmit"
      />
      <div class="composer__bar">
        <span class="composer__foot">
          <span :id="limitId" class="composer__hint">{{ hint }}</span>
          <span class="composer__count">{{ count }} / {{ maxlength }}</span>
        </span>
        <!-- 快捷键说明：视觉上是发送按钮的冒泡提示，读屏里由 aria-describedby 关联 -->
        <span :id="hintId" class="sr-only">{{ enterHint }}</span>
        <slot name="actions" />
      </div>
    </div>
  </form>
</template>
