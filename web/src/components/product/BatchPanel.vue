<script setup lang="ts">
/**
 * `BatchPanel`（组合件，CONTRACT §3.2 点名）—— S11 的 5 种文件状态。
 *
 * 状态映射（§6.10）由 `processing_state` → 展示驱动：
 *   available + visibility==='shared' ⇒ 可检索
 *   processing / rebuilding          ⇒ 处理中（**必须 `pill--info`**，不得用 `pill--warn`：见 §8.4 #1）
 *   failed                           ⇒ 失败（原因文案逐字取自 content-spec:156）
 *   deleting                         ⇒ 删除中
 *   delete_failed                    ⇒ 删除失败 + 「重试清理」
 *   deleted                          ⇒ 不展示
 * 整批规则：整批可见或整批不可见（content-spec:152 / 159）。
 */
import Pill from '@/components/base/Pill.vue'
import Btn from '@/components/base/Btn.vue'
import DataTable from '@/components/base/DataTable.vue'
import Notice from '@/components/base/Notice.vue'
import { ICONS } from '@/components/base/icons'
import { S11 } from '@/domain/copy'
import { formatBytes, formatDateTime, formatFileType } from '@/domain/format'
import type { Batch, Document } from '@/api/types.gen'

const props = defineProps<{ documents: Document[]; batch?: Batch | null; caption: string }>()
defineEmits<{ preview: [string]; retryCleanup: [string] }>()

type Variant = 'ok' | 'info' | 'danger' | 'warn' | 'pending'
interface Row {
  id: string
  name: string
  type: string
  size: string
  uploaded: string
  status: string
  actions: string
  variant: Variant
  error: string
  cleanupRetryable: boolean
}

/** `processing_state` → 展示态。`deleted` 不展示。 */
function display(d: Document): { label: string; variant: Variant } {
  switch (d.processing_state) {
    case 'available':
      return d.visibility === 'shared'
        ? { label: S11.statusSearchable, variant: 'ok' }
        : { label: S11.statusProcessing, variant: 'info' }
    case 'processing':
    case 'rebuilding':
      return { label: S11.statusProcessing, variant: 'info' }
    case 'failed':
      return { label: S11.statusFailed, variant: 'danger' }
    case 'deleting':
      return { label: S11.statusDeleting, variant: 'info' }
    case 'delete_failed':
      return { label: S11.statusDeleteFailed, variant: 'danger' }
    case 'deleted':
      return { label: '', variant: 'pending' }
  }
}

const columns = [
  { key: 'name', label: S11.colFile },
  { key: 'type', label: S11.colType },
  { key: 'size', label: S11.colSize, num: true },
  { key: 'uploaded', label: S11.colUploadedAt, num: true },
  { key: 'status', label: S11.colStatus },
  { key: 'actions', label: S11.colActions },
]

function rows(): Row[] {
  return props.documents
    .filter((d) => d.processing_state !== 'deleted')
    .map((d) => {
      const disp = display(d)
      return {
        id: d.id,
        name: d.original_name,
        type: formatFileType(d.file_type, d.processing_state !== 'failed'),
        size: formatBytes(d.byte_size),
        uploaded: formatDateTime(d.uploaded_at),
        status: disp.label,
        actions: '',
        variant: disp.variant,
        error: d.error_code === 'NO_TEXT_EXTRACTED' ? S11.noTextExtracted : '',
        cleanupRetryable: d.processing_state === 'delete_failed',
      }
    })
}
</script>

<template>
  <div class="stack">
    <Notice v-if="batch && batch.state === 'failed'" variant="warn" role="alert">
      {{ S11.batchRollback }}
    </Notice>

    <DataTable :caption="caption" :columns="columns" :rows="rows()" name-key="name">
      <template #cell-name="{ row }">
        <span>{{ row.name }}</span>
        <span v-if="row.error" class="field__error">{{ row.error }}</span>
      </template>
      <template #cell-status="{ row }">
        <Pill :variant="row.variant">
          <template #icon>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
              <path v-for="(d, i) in ICONS.fileText" :key="i" :d="d" />
            </svg>
          </template>
          {{ row.status }}
        </Pill>
      </template>
      <template #cell-actions="{ row }">
        <Btn size="sm" @click="$emit('preview', row.id)">{{ S11.previewText }}</Btn>
        <Btn v-if="row.cleanupRetryable" size="sm" @click="$emit('retryCleanup', row.id)">{{ S11.retryCleanup }}</Btn>
      </template>
    </DataTable>
  </div>
</template>
