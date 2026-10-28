<script setup lang="ts">
/**
 * S09 计划详情 / 编辑（§9.9）。这是**唯一对外可寻址的私有资源**（§7.6 `/me/plans/:planId`）。
 *
 * - `source` 只读（SRS IF-005：请求体没有 `source`，不得提交）；
 * - `PATCH` 必须带 `expected_version`（取最近一次服务端响应的 `version`，不做本地乐观递增）；
 * - 409 `VERSION_CONFLICT`：**保留未提交的编辑**，重新加载详情，文案逐字取自 content-spec:137；
 * - 404 `RESOURCE_NOT_FOUND`：不区分「不存在」与「无权限」，回列表。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Wrap from '@/components/base/Wrap.vue'
import Card from '@/components/base/Card.vue'
import Btn from '@/components/base/Btn.vue'
import Control from '@/components/base/Control.vue'
import Field from '@/components/base/Field.vue'
import FormGrid from '@/components/base/FormGrid.vue'
import Notice from '@/components/base/Notice.vue'
import ErrorSummary from '@/components/base/ErrorSummary.vue'
import { S06, S09, S15 } from '@/domain/copy'
import { formatDateTime } from '@/domain/format'
import { validatePlanForm } from '@/domain/validate'
import type { AppError } from '@/api/errors'
import { usePlansStore } from '@/stores/plans'

const route = useRoute()
const router = useRouter()
const store = usePlansStore()

const form = ref({ title: '', goal: '', start_date: '', end_date: '', content: '' })
const issues = ref<ReturnType<typeof validatePlanForm>>([])
const conflict = ref(false)
const other = ref<AppError | null>(null)
const saving = ref(false)

const planId = computed(() => String(route.params.planId ?? ''))
const sourceLabel = computed(() => (store.detail?.source === 'assistant' ? S09.sourceAssistant : S09.sourceManual))
const issue = (field: string) => issues.value.find((i) => i.field === field)?.kind ?? null
const issueText = (field: string): string | null => {
  const kind = issue(field)
  if (!kind) return null
  return kind === 'date-range' ? S09.dateRangeError : kind === 'required' ? '必填' : null
}

/** 右栏只读信息层（§6.2）：全部取最近一次服务端响应的 `detail`，不做本地推导。 */
const railItems = computed(() => {
  const d = store.detail
  if (!d) return []
  return [
    { k: S09.labelStartDate, v: d.start_date ?? S09.noDates },
    { k: S09.labelEndDate, v: d.end_date ?? S09.noDates },
    { k: S09.labelSource, v: sourceLabel.value },
    { k: S09.colUpdatedAt, v: formatDateTime(d.updated_at) },
    { k: S15.labelVersion, v: String(d.version) },
  ]
})

function syncFromDetail() {
  const d = store.detail
  if (!d) return
  form.value = {
    title: d.title,
    goal: d.goal ?? '',
    start_date: d.start_date ?? '',
    end_date: d.end_date ?? '',
    content: d.content,
  }
}

async function load() {
  other.value = null
  conflict.value = false
  try {
    await store.get(planId.value)
    syncFromDetail()
  } catch (e) {
    const err = e as AppError
    if (err.code === 'RESOURCE_NOT_FOUND' || err.httpStatus === 404) {
      // 不显示目标是否存在（FR-AUTH-004）；直接回列表。
      await router.replace({ name: 'plans' })
      return
    }
    other.value = err
  }
}

async function save() {
  issues.value = validatePlanForm(form.value)
  if (issues.value.length > 0) return
  if (saving.value) return
  saving.value = true
  conflict.value = false
  try {
    // 只提交 PlanPatch 允许的字段：**没有 source**、**没有 expected_version**（由 store 自动带）。
    await store.patch(planId.value, {
      title: form.value.title,
      goal: form.value.goal === '' ? null : form.value.goal,
      start_date: form.value.start_date === '' ? null : form.value.start_date,
      end_date: form.value.end_date === '' ? null : form.value.end_date,
      content: form.value.content,
    })
    syncFromDetail()
  } catch (e) {
    const err = e as AppError
    if (err.code === 'VERSION_CONFLICT') {
      // 重新加载详情，**保留未提交的编辑**供核对（不覆盖用户输入）。
      conflict.value = true
      await store.get(planId.value).catch(() => undefined)
    } else {
      other.value = err
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <Wrap>
    <div class="split">
      <div>
        <Card :title="S09.listTitle">
      <ErrorSummary
        id="plan-edit-errors"
        :issues="issues.map((i) => ({ field: i.field, label: i.field, reason: issueText(i.field) ?? '' }))"
      />

      <Notice v-if="conflict" variant="warn" role="alert">
        <p>{{ S09.versionConflict }}</p>
        <template #actions>
          <Btn size="sm" @click="load">{{ S09.open }}</Btn>
        </template>
      </Notice>

      <Notice v-if="other" variant="danger" role="alert">
        <p>{{ other.code }}</p>
        <span class="small">{{ other.requestId }}</span>
      </Notice>

      <form class="stack" @submit.prevent="save">
        <FormGrid :columns="2">
          <Field :label="S09.labelTitle" for-id="detail-title" required :error="issueText('title')">
            <Control id="detail-title" v-model="form.title" :invalid="!!issue('title')" :maxlength="100" />
          </Field>
          <!-- 来源只读：编辑**不会**改写来源（§8.5.1）。 -->
          <Field :label="S09.labelSource" for-id="detail-source">
            <Control id="detail-source" v-model="sourceLabel" readonly />
          </Field>
          <Field :label="S09.labelStartDate" for-id="detail-start" :error="issueText('start_date')">
            <Control id="detail-start" v-model="form.start_date" type="date" :invalid="!!issue('start_date')" />
          </Field>
          <Field :label="S09.labelEndDate" for-id="detail-end" :error="issueText('end_date')">
            <Control id="detail-end" v-model="form.end_date" type="date" :invalid="!!issue('end_date')" />
          </Field>
          <Field :label="S09.labelGoal" for-id="detail-goal" wide>
            <Control id="detail-goal" v-model="form.goal" :maxlength="500" />
          </Field>
          <Field :label="S09.labelContent" for-id="detail-content" required wide :error="issueText('content')">
            <Control id="detail-content" as="textarea" v-model="form.content" :invalid="!!issue('content')" :maxlength="10000" />
          </Field>
        </FormGrid>
        <div class="row">
          <!-- 保存按钮复用 content-spec:106 的冻结文案「保存为我的计划」：
               上游没有为「详情页保存」单独冻结按钮文案，复用比自造安全。 -->
          <Btn variant="primary" type="submit" :disabled="saving">{{ S06.saveAsPlan }}</Btn>
          <Btn variant="ghost" @click="router.push({ name: 'plans' })">{{ S09.listTitle }}</Btn>
        </div>
      </form>
        </Card>
      </div>

      <!-- 右栏 280：只读信息层（§6.2）。<1200 时整块回落到主列下方，信息不丢。
           不用 KVList：`.kv` 的 8em 键列在 244px 可用宽里会把日期断成两行，
           右栏改用上下堆叠的键值对（同一组信息、无新 class/token）。 -->
      <aside class="split__rail">
        <Card>
          <div v-if="store.detail" class="stack">
            <div v-for="item in railItems" :key="item.k">
              <div class="small muted">{{ item.k }}</div>
              <div>{{ item.v }}</div>
            </div>
          </div>
          <p v-else class="small muted">{{ S15.railLoading }}</p>
        </Card>
      </aside>
    </div>
  </Wrap>
</template>
