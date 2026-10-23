<script setup lang="ts">
/**
 * `DraftCard`（组合件，CONTRACT §3.2 点名）—— 示例见前端详细设计 §10.3。
 *
 * 三态**没有新增 class**：`unsaved`/`saved` 用 `.draft` 与 `.draft--saved`；
 * `unconfirmed` 复用 `.draft` 外观 + `.notice--warn role="status"`。
 * 文案逐字取自 content-spec S06 / S09；`plan_id` 来自 `done.plan_id`／`tool_end.plan_id`，**不得前端伪造**。
 */
import Draft from '@/components/base/Draft.vue'
import Pill from '@/components/base/Pill.vue'
import Notice from '@/components/base/Notice.vue'
import KVList from '@/components/base/KVList.vue'
import Btn from '@/components/base/Btn.vue'
import { ICONS } from '@/components/base/icons'
import { S06, S09 } from '@/domain/copy'
import { formatDateRange, formatSavedPlanLabel } from '@/domain/format'

const props = defineProps<{
  state: 'unsaved' | 'saved' | 'unconfirmed'
  planId?: string | null
  fields: { title: string; goal: string | null; start_date: string | null; end_date: string | null; content: string }
  basisSchedule?: boolean
  basisDocuments?: boolean
}>()
defineEmits<{ save: []; edit: []; queryStatus: [] }>()

const rows = () => [
  { k: S09.labelTitle, v: props.fields.title },
  { k: S09.labelGoal, v: props.fields.goal ?? '' },
  { k: S09.colRange, v: formatDateRange(props.fields.start_date, props.fields.end_date, S09.noDates) },
  { k: S09.labelContent, v: props.fields.content },
]
</script>

<template>
  <Draft :state="state">
    <template #head>
      <h2 class="field__label">{{ S06.draftTitle }}</h2>
      <Pill :variant="state === 'saved' ? 'ok' : state === 'unconfirmed' ? 'warn' : 'pending'">
        <template #icon>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
            <template v-if="state === 'saved'"><path v-for="(d, i) in ICONS.check" :key="i" :d="d" /></template>
            <template v-else><path v-for="(d, i) in ICONS.clock" :key="i" :d="d" /></template>
          </svg>
        </template>
        {{ state === 'saved' && planId ? formatSavedPlanLabel(S06.savedPrefix, planId) : S06.unsaved }}
      </Pill>
    </template>

    <KVList :items="rows()" />

    <!-- 依据类型必须**显式标注**（content-spec:104）：本人课表 / 课程资料。 -->
    <div v-if="basisSchedule || basisDocuments" class="chips">
      <Pill v-if="basisSchedule" variant="evidence">
        <template #icon>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
            <path v-for="(d, i) in ICONS.calendar" :key="i" :d="d" />
          </svg>
        </template>
        {{ S06.basisSchedule }}
      </Pill>
      <Pill v-if="basisDocuments" variant="evidence">
        <template #icon>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
            <path v-for="(d, i) in ICONS.fileText" :key="i" :d="d" />
          </svg>
        </template>
        {{ S06.basisDocuments }}
      </Pill>
    </div>

    <p class="small muted">{{ S06.idempotencyNote }}</p>

    <Notice v-if="state === 'unconfirmed'" variant="warn" role="status">
      <p>{{ S06.confirming }}</p>
      <p>{{ S06.unconfirmedNotice }}</p>
    </Notice>

    <template #actions>
      <Btn v-if="state === 'saved'" variant="primary" @click="$emit('edit')">{{ S06.openPlan }}</Btn>
      <Btn v-else-if="state === 'unconfirmed'" @click="$emit('queryStatus')">{{ S06.queryWriteStatus }}</Btn>
      <template v-else>
        <Btn variant="primary" @click="$emit('save')">{{ S06.saveAsPlan }}</Btn>
        <Btn variant="ghost" @click="$emit('edit')">{{ S06.continueEditing }}</Btn>
      </template>
    </template>
  </Draft>
</template>
