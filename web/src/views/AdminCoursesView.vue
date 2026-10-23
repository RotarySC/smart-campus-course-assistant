<script setup lang="ts">
/**
 * S10 管理中心 · 课程管理（§9.10）。
 *
 * - 课程代码**创建后不可修改** → 编辑期渲染为 `readonly` 并给出逐字说明（content-spec:145）；
 * - `CoursePatch` 里没有 `code` 字段，所以编辑提交体里也不带；
 * - 重复代码 409 `DUPLICATE_COURSE` → 字段级错误落在 `code`；
 * - 停用确认文案逐字取自 content-spec:147。
 */
import { computed, onMounted, ref } from 'vue'
import Wrap from '@/components/base/Wrap.vue'
import Card from '@/components/base/Card.vue'
import Btn from '@/components/base/Btn.vue'
import Control from '@/components/base/Control.vue'
import Field from '@/components/base/Field.vue'
import FormGrid from '@/components/base/FormGrid.vue'
import DataTable from '@/components/base/DataTable.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import Pill from '@/components/base/Pill.vue'
import Notice from '@/components/base/Notice.vue'
import { ICONS } from '@/components/base/icons'
import { ACTIONS, S01, S10 } from '@/domain/copy'
import { validateCourseForm } from '@/domain/validate'
import type { AppError } from '@/api/errors'
import type { Course } from '@/api/types.gen'
import { useAdminStore } from '@/stores/admin'

const store = useAdminStore()

const query = ref('')
const editing = ref<Course | null>(null)
const creating = ref(false)
const form = ref({ code: '', name: '', description: '' })
const fieldError = ref<Record<string, string>>({})
const disableTarget = ref<Course | null>(null)

const columns = [
  { key: 'code', label: S10.colCode, num: true },
  { key: 'name', label: S10.colName },
  { key: 'description', label: S10.colDescription },
  { key: 'enabled', label: S10.colEnabled },
  { key: 'actions', label: S10.colActions },
]

const rows = computed(() =>
  store.courses.items.map((c) => ({
    id: c.id,
    code: c.code,
    name: c.name,
    description: c.description ?? '',
    enabled: c.enabled ? S10.enabled : S10.disabled,
    actions: '',
    isEnabled: c.enabled,
  })),
)

async function load() {
  await store.listCourses({ query: query.value }).catch(() => undefined)
}

function startCreate() {
  creating.value = true
  editing.value = null
  fieldError.value = {}
  form.value = { code: '', name: '', description: '' }
}

function startEdit(c: Course) {
  creating.value = false
  editing.value = c
  fieldError.value = {}
  form.value = { code: c.code, name: c.name, description: c.description ?? '' }
}

async function submit() {
  fieldError.value = {}
  const issues = validateCourseForm(form.value, creating.value)
  if (issues.length > 0) {
    fieldError.value = { [issues[0]!.field]: S01.required }
    return
  }
  try {
    if (creating.value) {
      await store.createCourse({ code: form.value.code, name: form.value.name, description: form.value.description })
    } else if (editing.value) {
      await store.patchCourse(
        editing.value.id,
        { name: form.value.name, description: form.value.description },
        editing.value.version,
      )
    }
    creating.value = false
    editing.value = null
  } catch (e) {
    const err = e as AppError
    if (err.code === 'DUPLICATE_COURSE') {
      fieldError.value = { code: S10.duplicateCode }
      return
    }
    fieldError.value = { name: err.code ?? 'INTERNAL_ERROR' }
  }
}

async function toggleEnabled(c: Course) {
  if (c.enabled) {
    disableTarget.value = c
    return
  }
  await store.patchCourse(c.id, { enabled: true }, c.version).catch(() => undefined)
}

async function confirmDisable() {
  const c = disableTarget.value
  disableTarget.value = null
  if (!c) return
  await store.patchCourse(c.id, { enabled: false }, c.version).catch(() => undefined)
}

onMounted(() => void load())
</script>

<template>
  <Wrap>
    <Card :title="S10.title">
      <FormGrid>
        <Field :label="S10.filterLabel" for-id="course-query">
          <Control id="course-query" v-model="query" type="search" @blur="load" />
        </Field>
      </FormGrid>

      <div class="row">
        <Btn variant="primary" @click="startCreate">
          <template #icon>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
              <path v-for="(d, i) in ICONS.plus" :key="i" :d="d" />
            </svg>
          </template>
          {{ S10.create }}
        </Btn>
      </div>

      <form v-if="creating || editing" class="stack" @submit.prevent="submit">
        <FormGrid :columns="2">
          <Field
            :label="S10.labelCode"
            for-id="course-code"
            :required="creating"
            :hint="editing ? S10.codeReadonlyNote : ''"
            :error="fieldError.code ?? null"
          >
            <!-- 编辑期 `readonly` + 说明原因（content-spec:145）；不是 disabled。 -->
            <Control id="course-code" v-model="form.code" :readonly="!creating" :invalid="!!fieldError.code" :maxlength="32" />
          </Field>
          <Field :label="S10.labelName" for-id="course-name" required :error="fieldError.name ?? null">
            <Control id="course-name" v-model="form.name" :invalid="!!fieldError.name" :maxlength="100" />
          </Field>
          <Field :label="S10.labelDescription" for-id="course-desc" wide>
            <Control id="course-desc" v-model="form.description" :maxlength="2000" />
          </Field>
        </FormGrid>
        <div class="row">
          <Btn variant="primary" type="submit">{{ ACTIONS.save }}</Btn>
          <Btn variant="ghost" @click="creating = false; editing = null">{{ ACTIONS.cancel }}</Btn>
        </div>
      </form>

      <DataTable v-if="rows.length > 0" :caption="S10.title" :columns="columns" :rows="rows" name-key="name">
        <template #cell-enabled="{ row }">
          <Pill :variant="row.isEnabled ? 'ok' : 'advice'">
            <template #icon>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
                <path v-for="(d, i) in ICONS.check" :key="i" :d="d" />
              </svg>
            </template>
            {{ row.enabled }}
          </Pill>
        </template>
        <template #cell-actions="{ row }">
          <Btn size="sm" @click="startEdit(store.courses.items.find((c) => c.id === row.id)!)">{{ S10.edit }}</Btn>
          <Btn size="sm" @click="toggleEnabled(store.courses.items.find((c) => c.id === row.id)!)">
            {{ row.isEnabled ? S10.disabled : S10.enabled }}
          </Btn>
        </template>
      </DataTable>

      <EmptyState v-else-if="store.coursesEmpty" variant="empty" :title="S10.title" />

      <Notice v-if="store.error" variant="danger" role="alert">
        <p>{{ store.error.code }}</p>
        <span class="small">{{ store.error.requestId }}</span>
      </Notice>

      <Notice v-if="disableTarget" variant="warn" role="alert">
        <p>{{ S10.disableConfirm }}</p>
        <template #actions>
          <Btn size="sm" variant="danger" @click="confirmDisable">{{ S10.disabled }}</Btn>
          <Btn size="sm" variant="ghost" @click="disableTarget = null">{{ ACTIONS.cancel }}</Btn>
        </template>
      </Notice>
    </Card>
  </Wrap>
</template>
