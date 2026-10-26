<script setup lang="ts">
/**
 * `table` 族（04-forms-data.md §五/§六；rb.css:336–378）。
 *
 * 硬要求：`<caption>` + `th[scope="col"]`；**每个 `<td>` 必须有非空 `data-label`**
 * （`design/responsive/build.py` 已把它做成构建期检查，这里保持同一约定）。
 * `<caption>` 视觉隐藏（`.sr-only`，rb.css:113–114）：7 张表格（6 处模板调用，
 * `BatchPanel` 被两个管理页复用）传的都是**卡头标题**，可见的 caption 会与
 * `.card__head` 逐字重复（P5b 裁决 B1）。它仍留在 DOM 里当表格的
 * 可访问名 —— content-spec §1「表格必须有 caption」不因视觉隐藏而豁免。
 * `<768` 卡片化：`thead` 隐藏、`tr` 成卡片、`td` 用 `data-label` 渲染字段名。
 * 表格单元格用 `break-word` + `min-width`，**不得**改成 `anywhere`（content-spec §1 v1.1 修正）。
 */
withDefaults(
  defineProps<{
    caption: string
    columns: Array<{ key: string; label: string; num?: boolean; right?: boolean; nowrap?: boolean }>
    rows: Array<Record<string, any>>
    /** 首列（字段名）用 `.cell-name` 呈现。 */
    nameKey?: string
    compact?: boolean
    stack?: boolean
  }>(),
  { nameKey: '', compact: false, stack: true },
)
</script>

<template>
  <div class="table-wrap" :class="{ 'table-wrap--stackable': stack }">
    <table class="table" :class="{ 'table--compact': compact, 'table--stack': stack }">
      <caption class="sr-only">{{ caption }}</caption>
      <thead>
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            scope="col"
            :class="{ r: col.right }"
            :data-nowrap="col.nowrap ? 'true' : undefined"
          >
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, ri) in rows" :key="ri">
          <td
            v-for="col in columns"
            :key="col.key"
            :data-label="col.label"
            :data-nowrap="col.nowrap ? 'true' : undefined"
            :class="{ num: col.num, r: col.right, 'cell-name': col.key === nameKey }"
          >
            <slot :name="`cell-${col.key}`" :row="row">{{ row[col.key] }}</slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
