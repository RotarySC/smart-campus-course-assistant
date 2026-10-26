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
import BatchPanel from '@/components/product/BatchPanel.vue'
import AdminNav from '@/components/product/AdminNav.vue'
import { ICONS } from '@/components/base/icons'
import { S11 } from '@/domain/copy'
import { useAdminStore } from '@/stores/admin'

const store = useAdminStore()
const fileInput = ref<HTMLInputElement | null>(null)
const allowDuplicateNames = ref(false)

async function load() {
  await store.listDocuments().catch(() => undefined)
}

function pick() {
  fileInput.value?.click()
}

async function onFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (files.length === 0) return
  await store.uploadBatch(files, { allow_duplicate_names: allowDuplicateNames.value }).catch(() => undefined)
  input.value = ''
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
        <p class="muted">{{ S11.uploadHint }}</p>
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
        <div class="row">
          <Btn variant="primary" @click="pick">
            <template #icon>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
                <path v-for="(d, i) in ICONS.upload" :key="i" :d="d" />
              </svg>
            </template>
            {{ S11.chooseFile }}
          </Btn>
          <label class="row small">
            <input v-model="allowDuplicateNames" type="checkbox" />
            <span>{{ S11.publishRule }}</span>
          </label>
        </div>
      </div>

      <BatchPanel
        :documents="store.documents.items"
        :batch="store.batch"
        :caption="S11.title"
        @preview="preview"
        @retry-cleanup="retryCleanup"
      />

      <Notice v-if="store.documentText" variant="evidence" role="note">
        <p class="small">{{ store.documentText.text }}</p>
      </Notice>

      <Notice v-if="store.error" variant="danger" role="alert">
        <p>{{ store.error.code }}</p>
        <span class="small">{{ store.error.requestId }}</span>
      </Notice>
    </Card>
  </Wrap>
</template>
