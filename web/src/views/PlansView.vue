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
import Pill from '@/components/base/Pill.vue'
import { ICONS } from '@/components/base/icons'
import { S09, S12, S15 } from '@/domain/copy'
import { planDeleteConfirmText } from '@/domain/mapError'
import { formatDateRange, formatDateTime, fill } from '@/domain/format'
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
  { key: 'actions', label: S09.colActions },
]

/* ---- 只读信息层（§6.4）：进度、剩余天数全部前端按 start_date/end_date 计算，不新增接口 ---- */

function dayIndex(iso: string): number {
  return Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10))
}

function todayIso(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function spanDays(a: string, b: string): number {
  return Math.round((dayIndex(b) - dayIndex(a)) / 86_400_000)
}

/** 已进行比例：0–100 的整数；日期不全或区间非法时给 0（卡片上不画进度）。 */
function progressOf(p: Plan): number {
  if (!p.start_date || !p.end_date) return 0
  const total = spanDays(p.start_date, p.end_date)
  if (total <= 0) return 100
  return Math.max(0, Math.min(100, Math.round((spanDays(p.start_date, todayIso()) / total) * 100)))
}

function isOngoing(p: Plan): boolean {
  if (!p.start_date || !p.end_date) return false
  const t = todayIso()
  return p.start_date <= t && t <= p.end_date
}

function daysLeft(p: Plan): number | null {
  if (!p.end_date) return null
  return Math.max(0, spanDays(todayIso(), p.end_date))
}

const stats = computed(() => {
  const latest = store.items.reduce<string | null>(
    (acc, p) => (acc === null || p.updated_at > acc ? p.updated_at : acc),
    null,
  )
  return {
    total: store.total,
    ongoing: store.items.filter(isOngoing).length,
    assistant: store.items.filter((p) => p.source === 'assistant').length,
    updated: latest ? latest.slice(0, 10) : '—',
  }
})

/** 最近活动：按更新时间倒序取 3 条。 */
const recent = computed(() => [...store.items].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 3))

/** 即将结束：有截止日期的按截止日升序取 2 条。 */
const ending = computed(() =>
  store.items.filter((p) => p.end_date).sort((a, b) => (a.end_date ?? '').localeCompare(b.end_date ?? '')).slice(0, 2),
)

const rows = computed(() =>
  store.items.map((p) => ({
    id: p.id,
    title: p.title,
    source: p.source,
    sourceLabel: p.source === 'assistant' ? S09.sourceAssistant : S09.sourceManual,
    updatedLabel: formatDateTime(p.updated_at).slice(0, 10),
    rangeLabel: formatDateRange(p.start_date, p.end_date, S09.noDates),
    pct: progressOf(p),
    progressLabel: `已进行约 ${progressOf(p)}%`,
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
    <div class="split">
      <div class="stack">
        <div class="stat-grid">
          <div class="stat">
            <span class="stat__value">{{ stats.total }}</span>
            <span class="stat__label">{{ S15.statPlanTotal }}</span>
          </div>
          <div class="stat">
            <span class="stat__value">{{ stats.ongoing }}</span>
            <span class="stat__label">{{ S15.statPlanOngoing }}</span>
          </div>
          <div class="stat">
            <span class="stat__value">{{ stats.assistant }}</span>
            <span class="stat__label">{{ S15.statPlanAssistant }}</span>
          </div>
          <div class="stat">
            <span class="stat__value">{{ stats.updated }}</span>
            <span class="stat__label">{{ S15.statPlanUpdated }}</span>
          </div>
        </div>

        <Card :title="S09.listTitle">
          <!-- 卡片内所有块统一走 .stack 的 12px 间距：否则「新建计划」会贴在筛选框与表格之间 -->
          <div class="stack">
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
        <template #cell-title="{ row }">
          <span>{{ row.title }}</span>
          <Pill :variant="row.source === 'assistant' ? 'info' : 'default'">
            <template #icon>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
                <path v-for="(d, i) in (row.source === 'assistant' ? ICONS.messageCircle : ICONS.plus)" :key="i" :d="d" />
              </svg>
            </template>
            {{ row.sourceLabel }}
          </Pill>
          <span class="small muted">{{ row.updatedLabel }}</span>
        </template>
        <template #cell-range="{ row }">
          <span class="small">{{ row.rangeLabel }}</span>
          <span class="progress" role="img" :aria-label="row.progressLabel">
            <span class="progress__bar" :style="{ width: row.pct + '%' }"></span>
          </span>
        </template>
        <template #cell-actions="{ row }">
          <div class="row row--nowrap">
            <Btn size="sm" @click="openPlan(row.id)">{{ S09.open }}</Btn>
            <Btn size="sm" variant="danger" @click="askDelete(row.id)">
              <template #icon>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
                  <path v-for="(d, i) in ICONS.trash" :key="i" :d="d" />
                </svg>
              </template>
              {{ S09.remove }}
            </Btn>
          </div>
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
          </div>
        </Card>
      </div>

      <!-- 右栏 280：最近活动 / 即将结束 / 提示（§6.4）。<1200 整块回落主列下方。 -->
      <aside class="split__rail">
        <Card :title="S15.railRecent">
          <div v-if="recent.length > 0" class="timeline">
            <div v-for="p in recent" :key="p.id" class="timeline__item">
              <span class="timeline__time">{{ p.updated_at.slice(5, 10) }}</span>
              <div class="timeline__box">
                <b>{{ p.title }}</b>
                <div class="small muted">{{ p.source === 'assistant' ? S09.sourceAssistant : S09.sourceManual }}</div>
              </div>
            </div>
          </div>
          <p v-else class="small muted">{{ S09.emptyList }}</p>
        </Card>

        <Card :title="S15.railEnding">
          <div v-if="ending.length > 0" class="stack">
            <div v-for="p in ending" :key="p.id" class="stack">
              <b class="small">{{ p.title }}</b>
              <span class="small muted">{{ fill(S15.railDaysLeft, { N: String(daysLeft(p) ?? 0) }) }} · {{ p.end_date }}</span>
              <span class="progress" role="img" :aria-label="`已进行约 ${progressOf(p)}%`">
                <span class="progress__bar" :style="{ width: progressOf(p) + '%' }"></span>
              </span>
            </div>
          </div>
          <p v-else class="small muted">{{ S09.noDates }}</p>
        </Card>

        <Card>
          <p class="small muted">{{ S15.planHint }}</p>
        </Card>
      </aside>
    </div>
  </Wrap>
</template>
