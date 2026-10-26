<script setup lang="ts">
/**
 * `empty` 族（02-actions-status.md §Empty；rb.css:301–308）。
 *
 * **两态绝不合并**：`variant='empty'` 是「成功的空」，`variant='error'` 是服务异常；
 * 后者必须 `role="alert"`，且两者用不同图标 + 不同标题 + 不同容器外观（三重表达）。
 * 文案由调用方传入（必须来自 content-spec）。
 */
import { ICONS } from './icons'
import type { IconName } from './icons'

const props = withDefaults(
  defineProps<{ variant?: 'empty' | 'error'; title: string; hint?: string; icon?: IconName }>(),
  {
    variant: 'empty',
    hint: '',
  },
)
const isError = (): boolean => props.variant === 'error'
/** 6 种语义必须靠**不同图标**区分（02-actions-status.md §Empty：E1–E6）；未传则退回旧兜底。 */
const iconName = (): IconName => props.icon ?? (isError() ? 'circleAlert' : 'image')
</script>

<template>
  <div class="empty" :class="{ 'empty--error': isError() }" :role="isError() ? 'alert' : undefined">
    <div class="empty__art" aria-hidden="true">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
        <path v-for="(d, i) in ICONS[iconName()]" :key="i" :d="d" />
      </svg>
    </div>
    <p class="empty__title">{{ title }}</p>
    <p v-if="hint" class="empty__hint">{{ hint }}</p>
    <slot />
    <!-- 不新增 class：居中由 base.css 的 `.empty > .row` 结构规则提供（§10.4 class 存在性） -->
    <div v-if="$slots.actions" class="row"><slot name="actions" /></div>
  </div>
</template>
