<script setup lang="ts">
/**
 * `cite` 族（03-conversation.md §Citation；rb.css:276–288）。
 *
 * 已验证 = 4px 实心主色左条；未验证 = 琥珀虚下划线（走 `CiteMark`）；失效 = 危险色 + **文字说明**
 * （content-spec:89，不能只靠颜色）。折叠按钮带 `aria-expanded` / `aria-controls`。
 * `page_number` 可缺 → 只显示文件名与位置（content-spec:87 的「无页码」样例）。
 *
 * **文案**：只用了 content-spec:85 冻结的「展开片段」与 content-spec:89 的失效说明。
 * 「收起片段」这类反向文案**上游没有冻结**，所以不写——展开态由 `aria-expanded="true"` 表达，
 * 视觉上片段正文本身已经说明它是展开的（见 BUILD-REPORT 的未冻结文案登记）。
 */
import type { Reference } from '@/domain/sseTypes'
import { S04 } from '@/domain/copy'

const props = withDefaults(defineProps<{ citation: Reference; expanded?: boolean; invalid?: boolean }>(), {
  expanded: false,
  invalid: false,
})
const emit = defineEmits<{ 'update:expanded': [boolean] }>()
const bodyId = `cite-body-${props.citation.reference_id}`

function toggle() {
  emit('update:expanded', !props.expanded)
}
</script>

<template>
  <div class="cite" :class="{ 'cite--invalid': invalid }">
    <div class="cite__head">
      <span class="cite__name">{{ citation.file_name }}</span>
      <span class="cite__loc">{{ citation.location_label }}</span>
      <button class="btn btn--sm" type="button" :aria-expanded="expanded" :aria-controls="bodyId" @click="toggle">
        {{ S04.expandSnippet }}
      </button>
    </div>
    <p v-if="invalid" class="cite__loc">{{ S04.citeInvalid }}</p>
    <div v-if="expanded" :id="bodyId" class="cite__body"><slot name="body" /></div>
  </div>
</template>
