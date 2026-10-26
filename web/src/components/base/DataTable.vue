<script setup lang="ts">
/**
 * `table` 族（04-forms-data.md §五/§六；rb.css:336–378）。
 *
 * 硬要求：`<caption>` + `th[scope="col"]`；**每个 `<td>` 必须有非空 `data-label`**
 * （`design/responsive/build.py` 已把它做成构建期检查，这里保持同一约定）。
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
      <caption>{{ caption }}</caption>
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
