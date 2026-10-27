<script setup lang="ts">
/**
 * S11 管理中心 · 文档与批次（§9.11）—— 状态最密集的一屏。
 *
 * - 上传区限制说明逐字取自 content-spec:151；上传即异步（202 + `batch_id`）；
 * - 5 种文件状态由 `BatchPanel` 的 `processing_state` 映射驱动；
 * - 「处理中」**必须** `pill--info`，不得用 `pill--warn`（§8.4 #1）；
 * - 「预览抽取文本」对应 `GET /admin/documents/{id}/text`（`previewDocument`）。
 */
import { onMounted, ref } from 'vue'
import Wrap from '@/components/base/Wrap.vue'
import Card from '@/components/base/Card.vue'
import Btn from '@/components/base/Btn.vue'
import Notice from '@/components/base/Notice.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import BatchPanel from '@/components/product/BatchPanel.vue'
import AdminNav from '@/components/product/AdminNav.vue'
import { S11 } from '@/domain/copy'
import { useAdminStore } from '@/stores/admin'

const store = useAdminStore()
const fileInput = ref<HTMLInputElement | null>(null)
const allowDuplicateNames = ref(false)
/** 拖放区「正被拖入」态：只由 JS 切类（白名单里没有 `:drag-over` 这类伪类）。 */
const dragOver = ref(false)

async function load() {
  await store.listDocuments().catch(() => undefined)
}

function pick() {
  fileInput.value?.click()
}

async function uploadFiles(files: File[]) {
  if (files.length === 0) return
  await store.uploadBatch(files, { allow_duplicate_names: allowDuplicateNames.value }).catch(() => undefined)
}

async function onFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  await uploadFiles(files)
  input.value = ''
}

/** 「选择文件」与拖放走同一条上传路径（同一批限制、同一发布规则）。 */
async function onDrop(e: DragEvent) {
  dragOver.value = false
  await uploadFiles(Array.from(e.dataTransfer?.files ?? []))
}

/** `dragleave` 在子元素间移动也会触发：只有离开整个区域才熄掉高亮。 */
function onDragLeave(e: DragEvent) {
  const el = e.currentTarget as HTMLElement | null
  const to = e.relatedTarget as Node | null
  if (!el || !to || !el.contains(to)) dragOver.value = false
}

async function preview(id: string) {
  await store.previewDocumentText(id).catch(() => undefined)
}

async function retryCleanup(id: string) {
  const doc = store.documents.items.find((d) => d.id === id)
  if (!doc) return
  await store.retryCleanup(id, `cleanup_${id}_${doc.version}`).catch(() => undefined)
}

onMounted(() => void load())
</script>

<template>
  <Wrap>
    <Card :title="S11.title">
      <AdminNav />

      <div class="stack">
        <input
          ref="fileInput"
          class="sr-only"
          type="file"
          multiple
          accept=".txt,.md,.pdf,.docx"
          aria-hidden="true"
          tabindex="-1"
          @change="onFiles"
        />
        <!-- 上传区 = 拖拽区 + 「选择文件」（content-spec S11）；E4「上传引导」就是这块虚线区，
             不是遗漏态：整块 `.empty` 同时是落点与说明，键盘/点击走区内按钮。 -->
        <EmptyState
          variant="empty"
          icon="upload"
          :class="{ 'empty--over': dragOver }"
          :title="S11.dropTitle"
          :hint="S11.uploadHint"
          @dragover.prevent="dragOver = true"
          @dragleave="onDragLeave"
          @drop.prevent="onDrop"
        >
          <template #actions>
            <Btn variant="primary" @click="pick">{{ S11.chooseFile }}</Btn>
          </template>
        </EmptyState>
        <label class="row small">
          <input v-model="allowDuplicateNames" type="checkbox" />
          <span>{{ S11.publishRule }}</span>
        </label>
      </div>

      <BatchPanel
        :documents="store.documents.items"
        :batch="store.batch"
        :caption="S11.title"
        @preview="preview"
        @retry-cleanup="retryCleanup"
      />

      <Notice v-if="store.documentText" variant="evidence" role="note">
        <p v-if="store.documentText.state === 'available'" class="small">
          {{ store.documentText.text }}
        </p>
        <p v-else class="small">
          {{
            store.documentText.state === 'processing'
              ? S11.previewUnavailableProcessing
              : S11.previewUnavailableFailed
          }}
        </p>
      </Notice>

      <Notice v-if="store.error" variant="danger" role="alert">
        <p>{{ store.error.code }}</p>
        <span class="small">{{ store.error.requestId }}</span>
      </Notice>
    </Card>
  </Wrap>
</template>
