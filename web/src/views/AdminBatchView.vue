<script setup lang="ts">
/**
 * S11 批次详情 `/admin/document-batches/:batchId`（§9.11 批次）。
 *
 * 批次四种展示态由 `Batch.state`（accepted/processing/published/compensating/failed）+ `published` 驱动；
 * 整批回滚文案逐字取自 content-spec:159；
 * 轮询 3s、进终态即停（§6.10）——由 `admin` store 负责，本视图只负责启动/停止。
 */
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import Wrap from '@/components/base/Wrap.vue'
import Card from '@/components/base/Card.vue'
import Notice from '@/components/base/Notice.vue'
import Pill from '@/components/base/Pill.vue'
import BatchPanel from '@/components/product/BatchPanel.vue'
import AdminNav from '@/components/product/AdminNav.vue'
import { ICONS } from '@/components/base/icons'
import { S11 } from '@/domain/copy'
import { useAdminStore } from '@/stores/admin'

const route = useRoute()
const store = useAdminStore()

const batchId = computed(() => String(route.params.batchId ?? ''))
const stateLabel = computed(() => {
  const b = store.batch
  if (!b) return ''
  return b.published ? S11.statusSearchable : b.state === 'failed' ? S11.statusFailed : S11.statusProcessing
})

onMounted(async () => {
  await store.getBatch(batchId.value).catch(() => undefined)
  store.startBatchPolling(batchId.value)
})
onUnmounted(() => store.stopBatchPolling())
</script>

<template>
  <Wrap>
    <Card :title="S11.title">
      <AdminNav />

      <div class="row">
        <Pill :variant="store.batch?.state === 'failed' ? 'danger' : store.batch?.published ? 'ok' : 'info'">
          <template #icon>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
              <path v-for="(d, i) in ICONS.fileText" :key="i" :d="d" />
            </svg>
          </template>
          {{ stateLabel }}
        </Pill>
        <span class="small muted">{{ S11.publishRule }}</span>
      </div>

      <BatchPanel
        :documents="store.batch?.documents ?? []"
        :batch="store.batch"
        :caption="S11.title"
        @preview="() => undefined"
        @retry-cleanup="() => undefined"
      />

      <Notice v-if="store.error" variant="danger" role="alert">
        <p>{{ store.error.code }}</p>
      </Notice>
    </Card>
  </Wrap>
</template>
