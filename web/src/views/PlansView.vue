<script setup lang="ts">
/**
 * S09 学习计划 · 列表（§9.9）。
 *
 * - **筛选状态不进 URL**（判断项 J1）：`title` 过滤只存在 store 里；
 * - 空列表 = `items=[]` 且 `error===null` ⇒ content-spec:133「还没有学习计划。」+「手动新建」；
 * - 删除二次确认文案逐字取自 content-spec:138（占位符替换标题）；
 * - 「新建计划」不进新路由（§7.1 冻结表只有 10 条）—— 用**内联表单**完成，
 *   因为 CONTRACT §3.3 明令「不得自创路由记录」。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Wrap from '@/components/base/Wrap.vue'
import Card from '@/components/base/Card.vue'
import Btn from '@/components/base/Btn.vue'
import Control from '@/components/base/Control.vue'
import Field from '@/components/base/Field.vue'
import FormGrid from '@/components/base/FormGrid.vue'
import DataTable from '@/components/base/DataTable.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import Notice from '@/components/base/Notice.vue'
import ErrorSummary from '@/components/base/ErrorSummary.vue'
import { ICONS } from '@/components/base/icons'
import { S09, S12 } from '@/domain/copy'
import { planDeleteConfirmText } from '@/domain/mapError'
import { formatDateRange, formatDateTime } from '@/domain/format'
import { validatePlanForm } from '@/domain/validate'
import type { Plan } from '@/api/types'
import { usePlansStore } from '@/stores/plans'

const router = useRouter()
const store = usePlansStore()

const titleInput = ref('')
const confirmPlan = ref<Plan | null>(null)
const creating = ref(false)
const creating2 = ref(false) // 防止重复提交（写操作不自动重试）

const form = ref({ title: '', goal: '', start_date: '', end_date: '', content: '' })
const issues = ref<ReturnType<typeof validatePlanForm>>([])

const columns = [
  { key: 'title', label: S09.colTitle },
  { key: 'range', label: S09.colRange, num: true },
  { key: 'source', label: S09.colSource },
  { key: 'updated', label: S09.colUpdatedAt, num: true },
  { key: 'actions', label: S09.colActions },
]

const rows = computed(() =>
  store.items.map((p) => ({
    id: p.id,
    title: p.title,
    range: formatDateRange(p.start_date, p.end_date, S09.noDates),
    source: p.source === 'assistant' ? S09.sourceAssistant : S09.sourceManual,
    updated: formatDateTime(p.updated_at),
    actions: '',
  })),
)

const confirmText = computed(() => (confirmPlan.value ? planDeleteConfirmText(confirmPlan.value.title) : ''))
const issue = (field: string) => issues.value.find((i) => i.field === field)?.kind ?? null
const issueText = (field: string): string | null => {
  const kind = issue(field)
  if (!kind) return null
  return kind === 'date-range' ? S09.dateRangeError : kind === 'required' ? '必填' : null
}

async function load() {
  await store.list({ title: titleInput.value }).catch(() => undefined)
}

function openPlan(id: string) {
  void router.push({ name: 'planDetail', params: { planId: id } })
}

function askDelete(id: string) {
  confirmPlan.value = store.items.find((p) => p.id === id) ?? null
}

async function doDelete() {
  const p = confirmPlan.value
  confirmPlan.value = null
  if (!p) return
  await store.remove(p.id, p.version).catch(() => undefined)
  await load()
}

async function submitCreate() {
  issues.value = validatePlanForm(form.value)
  if (issues.value.length > 0) return
  if (creating2.value) return
  creating2.value = true
  try {
    // 幂等键：同一逻辑创建复用同一键（§6.3）；键必须匹配 ^[A-Za-z0-9._:-]+$。
    const key = `plan_create_${Date.now().toString(36)}`
    const outcome = await store.create(
      {
        title: form.value.title,
        goal: form.value.goal === '' ? null : form.value.goal,
        start_date: form.value.start_date === '' ? null : form.value.start_date,
        end_date: form.value.end_date === '' ? null : form.value.end_date,
        content: form.value.content,
      },
      key,
    )
    creating.value = false
    form.value = { title: '', goal: '', start_date: '', end_date: '', content: '' }
    if (outcome.kind === 'pending') return
    if (outcome.kind === 'deleted') return
    // created / existing 都算成功（existing 是幂等命中，不是错误）。
    await load()
    openPlan(outcome.planId)
  } finally {
    creating2.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <Wrap>
    <Card :title="S09.listTitle">
      <FormGrid>
        <Field :label="S09.searchLabel" for-id="plan-search">
          <Control id="plan-search" v-model="titleInput" type="search" @blur="load" />
        </Field>
      </FormGrid>

      <div class="row">
        <Btn variant="primary" @click="creating = !creating">
          <template #icon>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
              <path v-for="(d, i) in ICONS.plus" :key="i" :d="d" />
            </svg>
          </template>
          {{ S09.create }}
        </Btn>
      </div>

      <form v-if="creating" class="stack" @submit.prevent="submitCreate">
        <ErrorSummary
          id="plan-create-errors"
          :issues="issues.map((i) => ({ field: i.field, label: i.field, reason: issueText(i.field) ?? '' }))"
        />
        <FormGrid :columns="2">
          <Field :label="S09.labelTitle" for-id="plan-title" required :error="issueText('title')">
            <Control id="plan-title" v-model="form.title" :invalid="!!issue('title')" :maxlength="100" />
          </Field>
          <Field :label="S09.labelStartDate" for-id="plan-start" :error="issueText('start_date')">
            <Control id="plan-start" v-model="form.start_date" type="date" :invalid="!!issue('start_date')" />
          </Field>
          <Field :label="S09.labelEndDate" for-id="plan-end" :error="issueText('end_date')">
            <Control id="plan-end" v-model="form.end_date" type="date" :invalid="!!issue('end_date')" />
          </Field>
          <Field :label="S09.labelGoal" for-id="plan-goal" wide>
            <Control id="plan-goal" v-model="form.goal" :maxlength="500" />
          </Field>
          <Field :label="S09.labelContent" for-id="plan-content" required wide :error="issueText('content')">
            <Control id="plan-content" as="textarea" v-model="form.content" :invalid="!!issue('content')" :maxlength="10000" />
          </Field>
        </FormGrid>
        <div class="row">
          <Btn variant="primary" type="submit" :disabled="creating2">{{ S09.create }}</Btn>
          <Btn variant="ghost" @click="creating = false">{{ S12.cancel }}</Btn>
        </div>
      </form>

      <DataTable v-if="rows.length > 0" :caption="S09.listTitle" :columns="columns" :rows="rows" name-key="title">
        <template #cell-actions="{ row }">
          <Btn size="sm" @click="openPlan(row.id)">{{ S09.open }}</Btn>
          <Btn size="sm" variant="danger" @click="askDelete(row.id)">
            <template #icon>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
                <path v-for="(d, i) in ICONS.trash" :key="i" :d="d" />
              </svg>
            </template>
            {{ S09.remove }}
          </Btn>
        </template>
      </DataTable>

      <EmptyState v-else-if="store.isEmpty" variant="empty" icon="listChecks" :title="S09.emptyList">
        <template #actions>
          <Btn size="sm" @click="creating = true">{{ S09.createManual }}</Btn>
        </template>
      </EmptyState>

      <Notice v-else-if="store.error" variant="danger" role="alert">
        <p>{{ store.error.code }}</p>
        <span class="small">{{ store.error.requestId }}</span>
      </Notice>

      <Notice v-if="confirmPlan" variant="danger" role="alert">
        <p>{{ confirmText }}</p>
        <template #actions>
          <Btn size="sm" variant="danger" @click="doDelete">{{ S09.remove }}</Btn>
          <Btn size="sm" variant="ghost" @click="confirmPlan = null">{{ S12.cancel }}</Btn>
        </template>
      </Notice>
    </Card>
  </Wrap>
</template>
