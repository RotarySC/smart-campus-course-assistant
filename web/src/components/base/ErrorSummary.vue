<script setup lang="ts">
/**
 * `.error-summary`（04-forms-data.md §四；rb.css:329–331）。
 *
 * `role="alert"` + `tabindex="-1"`（脚本焦点落点）；错误项是 `<a href="#字段id">`，
 * 锚点必须真实存在；**无错时不渲染 DOM**，不用 `display:none` 切换。
 *
 * 文案：**完全不出现自造句子**。每条 = 「可见字段名（content-spec 冻结）：服务端 reason（§4.8 权威）」，
 * 容器本身是 `role="alert"`，读屏会把列表内容作为整体播报，因此不需要一个额外的标题句
 * （上游从未冻结「请修正以下问题」这类文案）。
 *
 * **不新增 class**：列表的两条排版由 base.css 里 `.error-summary ul` / `.error-summary li` 的
 * 结构规则提供（§10.4 要求组件使用的每个 class 都逐字出现在 rb.css 里）。
 */
import { ICONS } from './icons'

withDefaults(defineProps<{ id?: string; issues: Array<{ field: string; label: string; reason: string }> }>(), {
  id: 'error-summary',
})
</script>

<template>
  <div v-if="issues.length > 0" :id="id" class="error-summary" role="alert" tabindex="-1">
    <ul>
      <li v-for="issue in issues" :key="issue.field">
        <a :href="`#${issue.field}`">
          <span class="row">
            <span aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
                <path v-for="(d, i) in ICONS.circleAlert" :key="i" :d="d" />
              </svg>
            </span>
            <span>{{ issue.label }}</span>
          </span>
        </a>
        <span>{{ issue.reason }}</span>
      </li>
    </ul>
  </div>
</template>
