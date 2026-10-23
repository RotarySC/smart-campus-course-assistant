<script setup lang="ts">
/**
 * S12 管理中心 · 课表维护（§9.12），含重叠冲突确认面板。
 *
 * 三种 409 的分工（§11.5）：
 *   - `DUPLICATE_SCHEDULE`（同日完全相同时间段）→ **字段级错误**，无确认面板，始终拒绝；
 *   - `SCHEDULE_OVERLAP`（时间重叠）→ 打开冲突确认面板：摘要 + 原因必填 ≤500 + 「确认保存」；
 *   - `VERSION_CONFLICT` → 重新加载、保留未提交编辑。
 * 停用课程不可选（content-spec:164）。
 */
import { computed, onMounted, ref } from 'vue'
import Wrap from '@/components/base/Wrap.vue'
import Card from '@/components/base/Card.vue'
import Btn from '@/components/base/Btn.vue'
import Control from '@/components/base/Control.vue'
import Field from '@/components/base/Field.vue'
import FormGrid from '@/components/base/FormGrid.vue'
import Notice from '@/components/base/Notice.vue'
import DataTable from '@/components/base/DataTable.vue'
import { ICONS } from '@/components/base/icons'
import { ACTIONS, S12 } from '@/domain/copy'
import { overlapText } from '@/domain/mapError'
import { formatTimeRange } from '@/domain/format'
import { canAcknowledgeOverlap, validateScheduleForm } from '@/domain/validate'
import type { AppError } from '@/api/errors'
import type { ScheduleCreate } from '@/api/types'
import { useAdminStore } from '@/stores/admin'
import { useSchedulesStore } from '@/stores/schedules'

const admin = useAdminStore()
const schedules = useSchedulesStore()

const form = ref({
  student_id: 'u_stu_001',
  course_id: '',
  class_date: '2026-10-22',
  start_time: '08:00',
  end_time: '09:40',
  location: '',
  reason: '',
})
const errors = ref<Record<string, string>>({})
const duplicate = ref(false)
const showPanel = ref(false)

const columns = [
  { key: 'date', label: S12.labelClassDate, num: true },
  { key: 'time', label: S12.labelStartTime, num: true },
  { key: 'course', label: S12.labelCourse },
  { key: 'location', label: S12.labelLocation },
]

const rows = computed(() =>
  admin.schedules.items.map((s) => ({
    date: s.class_date,
    time: formatTimeRange(s.start_time, s.end_time),
    course: s.course_name,
    location: s.location ?? '',
  })),
)

const enabledCourses = computed(() => admin.courses.items.filter((c) => c.enabled))

const overlapSummary = computed(() =>
  (admin.overlap ?? []).map((s) =>
    overlapText({ date: s.class_date, start: s.start_time, end: s.end_time, course: s.course_name }),
  ),
)

async function load() {
  await admin.listCourses().catch(() => undefined)
  await admin.listAdminSchedules({ student_id: form.value.student_id, from_date: form.value.class_date, to_date: form.value.class_date }).catch(() => undefined)
}

function payload(acknowledged: boolean): ScheduleCreate {
  const base: ScheduleCreate = {
    student_id: form.value.student_id,
    course_id: form.value.course_id,
    class_date: form.value.class_date,
    start_time: form.value.start_time,
    end_time: form.value.end_time,
    location: form.value.location,
    overlap_acknowledged: acknowledged,
  }
  // OpenAPI `ScheduleCreate.reason` 是**非空字符串**（minLength 1，不可为 null）：
  // 未确认重叠时**不发送**该字段（而不是发 null），否则真实后端会 422。
  return acknowledged ? { ...base, reason: form.value.reason } : base
}

async function submit(acknowledged: boolean) {
  errors.value = {}
  duplicate.value = false
  const issues = validateScheduleForm(form.value)
  if (issues.length > 0) {
    errors.value = { [issues[0]!.field]: issues[0]!.kind === 'time-range' ? S12.timeRangeError : '必填' }
    return
  }
  if (acknowledged && !canAcknowledgeOverlap(form.value)) {
    // 重叠确认：原因**必填**（content-spec:170）。
    errors.value = { reason: '必填' }
    return
  }
  try {
    await admin.createSchedule(payload(acknowledged))
    showPanel.value = false
    await load()
  } catch (e) {
    const err = e as AppError
    if (err.code === 'DUPLICATE_SCHEDULE') {
      duplicate.value = true
      errors.value = { start_time: S12.duplicateSchedule }
      return
    }
    if (err.code === 'SCHEDULE_OVERLAP') {
      showPanel.value = true
      return
    }
    if (err.code === 'VERSION_CONFLICT') {
      errors.value = { class_date: err.code }
    }
  }
}

onMounted(() => void load())
void schedules
</script>

<template>
  <Wrap>
    <Card :title="S12.title">
      <form class="stack" @submit.prevent="submit(false)">
        <FormGrid :columns="2">
          <Field :label="S12.labelStudent" for-id="sch-student" required :error="errors.student_id ?? null">
            <Control id="sch-student" v-model="form.student_id" :invalid="!!errors.student_id" />
          </Field>
          <Field :label="S12.labelCourse" for-id="sch-course" required :error="errors.course_id ?? null">
            <Control id="sch-course" as="select" v-model="form.course_id" :invalid="!!errors.course_id">
              <!-- 停用课程不可选（content-spec:164）。 -->
              <option value=""></option>
              <option v-for="c in enabledCourses" :key="c.id" :value="c.id">{{ c.name }}</option>
            </Control>
          </Field>
          <Field :label="S12.labelClassDate" for-id="sch-date" required :error="errors.class_date ?? null">
            <Control id="sch-date" v-model="form.class_date" type="date" :invalid="!!errors.class_date" />
          </Field>
          <Field :label="S12.labelLocation" for-id="sch-loc">
            <Control id="sch-loc" v-model="form.location" :maxlength="200" />
          </Field>
          <Field :label="S12.labelStartTime" for-id="sch-start" required :error="errors.start_time ?? null">
            <Control id="sch-start" v-model="form.start_time" type="time" :invalid="!!errors.start_time" />
          </Field>
          <Field :label="S12.labelEndTime" for-id="sch-end" required :error="errors.end_time ?? null">
            <Control id="sch-end" v-model="form.end_time" type="time" :invalid="!!errors.end_time" />
          </Field>
        </FormGrid>
        <div class="row">
          <Btn variant="primary" type="submit">{{ ACTIONS.save }}</Btn>
        </div>
      </form>

      <Notice v-if="duplicate" variant="danger" role="alert">
        <p>{{ S12.duplicateSchedule }}</p>
      </Notice>

      <!-- 重叠冲突确认面板：冲突摘要 + 原因必填 + 确认保存/取消 -->
      <Notice v-if="showPanel" variant="warn" role="alert">
        <p v-for="(line, i) in overlapSummary" :key="i">{{ line }}</p>
        <Field :label="S12.labelReason" for-id="sch-reason" required :error="errors.reason ?? null">
          <Control id="sch-reason" v-model="form.reason" :maxlength="500" :invalid="!!errors.reason" />
        </Field>
        <template #actions>
          <Btn size="sm" variant="primary" @click="submit(true)">{{ S12.confirmSave }}</Btn>
          <Btn size="sm" variant="ghost" @click="showPanel = false; admin.clearOverlap()">{{ S12.cancel }}</Btn>
        </template>
      </Notice>

      <DataTable v-if="rows.length > 0" :caption="S12.title" :columns="columns" :rows="rows" name-key="course" />

      <Notice v-if="admin.error" variant="danger" role="alert">
        <p>{{ admin.error.code }}</p>
        <span class="small">{{ admin.error.requestId }}</span>
        <template #actions>
          <Btn size="sm" @click="load">
            <template #icon>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
                <path v-for="(d, i) in ICONS.listChecks" :key="i" :d="d" />
              </svg>
            </template>
            {{ S12.title }}
          </Btn>
        </template>
      </Notice>
    </Card>
  </Wrap>
</template>
