<script setup lang="ts">
/**
 * `CitationList`（组合件，CONTRACT §3.2 点名）。
 *
 * 引用正文**不缓存**：每次展开都重新请求 `GET /api/v1/citations/{reference_id}`（§6.12 末行）；
 * 失效引用（410 `CITATION_UNAVAILABLE`）**不得**被缓存展示，也不得让整轮失败（§3.4 的 410 行）。
 * 内容性质标签（**课程规定** / **一般学习建议**）必须视觉区分、不得混排（content-spec:88）。
 */
import { ref } from 'vue'
import CitationCard from '@/components/base/CitationCard.vue'
import Pill from '@/components/base/Pill.vue'
import { ICONS } from '@/components/base/icons'
import { S04 } from '@/domain/copy'
import * as citationsApi from '@/api/citations'
import type { AppError } from '@/api/errors'
import type { Reference } from '@/domain/sseTypes'
import { useSessionStore } from '@/stores/session'

const props = defineProps<{ references: Reference[]; sourced?: boolean }>()
const session = useSessionStore()

const expanded = ref<Record<string, boolean>>({})
const body = ref<Record<string, string>>({})
const invalid = ref<Record<string, boolean>>({})

async function toggle(ref: Reference) {
  const next = !expanded.value[ref.reference_id]
  expanded.value = { ...expanded.value, [ref.reference_id]: next }
  if (!next || body.value[ref.reference_id] !== undefined) return
  try {
    const c = await citationsApi.getCitation(session.auth, ref.reference_id)
    body.value = { ...body.value, [ref.reference_id]: c.text }
  } catch (e) {
    // 410：只标记该引用不可用，**不**让整轮失败。
    const err = e as AppError
    if (err.code === 'CITATION_UNAVAILABLE' || err.httpStatus === 410) {
      invalid.value = { ...invalid.value, [ref.reference_id]: true }
      expanded.value = { ...expanded.value, [ref.reference_id]: false }
    }
  }
}
void props
</script>

<template>
  <div class="stack">
    <Pill :variant="sourced ? 'evidence' : 'advice'">
      <template #icon>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
          <path v-for="(d, i) in ICONS.quote" :key="i" :d="d" />
        </svg>
      </template>
      {{ sourced ? S04.sourcedTag : S04.adviceTag }}
    </Pill>

    <CitationCard
      v-for="ref in references"
      :key="ref.reference_id"
      :citation="ref"
      :expanded="!!expanded[ref.reference_id]"
      :invalid="!!invalid[ref.reference_id]"
      @update:expanded="toggle(ref)"
    >
      <template #body>{{ body[ref.reference_id] }}</template>
    </CitationCard>
  </div>
</template>
