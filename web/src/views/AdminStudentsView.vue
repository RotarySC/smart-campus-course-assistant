<script setup lang="ts">
/**
 * 管理 · 学生账号 `/admin/students`（§9.14）。
 *
 * 文案：content-spec **S15.6** 已冻结本屏两句——页面标题「管理中心 · 学生账号」与筛选 label
 * 「按账号或名称筛选」（此前标题是登记待冻结、筛选误用课程页的「按课程代码或名称筛选」）。
 * 其余只渲染 `API-REFERENCE.md` 能查到的字段（`account`/`display_name`/`enabled`/`version`）
 * 与 §3.4 的码，**不自造任何屏幕文案**。
 */
import { computed, onMounted, ref } from 'vue'
import Wrap from '@/components/base/Wrap.vue'
import Card from '@/components/base/Card.vue'
import Btn from '@/components/base/Btn.vue'
import Control from '@/components/base/Control.vue'
import Field from '@/components/base/Field.vue'
import FormGrid from '@/components/base/FormGrid.vue'
import DataTable from '@/components/base/DataTable.vue'
import Notice from '@/components/base/Notice.vue'
import Pill from '@/components/base/Pill.vue'
import { ICONS } from '@/components/base/icons'
import AdminNav from '@/components/product/AdminNav.vue'
import { ACTIONS, S10, S15 } from '@/domain/copy'
import { useAdminStore } from '@/stores/admin'

const store = useAdminStore()
const query = ref('')
const form = ref({ account: '', display_name: '', initial_password: '' })
const errorCode = ref<string | null>(null)

const columns = [
  { key: 'account', label: '账号' },
  { key: 'display_name', label: S10.colName },
  { key: 'enabled', label: S10.colEnabled },
  { key: 'actions', label: S10.colActions },
]

const rows = computed(() =>
  store.students.items.map((u) => ({
    id: u.id,
    account: u.account,
    display_name: u.display_name,
    enabled: u.enabled ? S10.enabled : S10.disabled,
    actions: '',
    isEnabled: u.enabled,
  })),
)

async function load() {
  await store.listStudents({ query: query.value }).catch(() => undefined)
}

async function submit() {
  errorCode.value = null
  try {
    await store.createStudent({
      account: form.value.account,
      display_name: form.value.display_name,
      initial_password: form.value.initial_password,
    })
    form.value = { account: '', display_name: '', initial_password: '' }
  } catch (e) {
    errorCode.value = (e as { code?: string }).code ?? 'INTERNAL_ERROR'
  }
}

async function toggle(u: { id: string; isEnabled: boolean }) {
  const target = store.students.items.find((s) => s.id === u.id)
  if (!target) return
  await store.patchStudent(u.id, { enabled: !u.isEnabled }, target.version).catch(() => undefined)
}

onMounted(() => void load())
</script>

<template>
  <Wrap>
    <Card :title="S15.adminStudentsTitle">
      <AdminNav />

      <FormGrid>
        <Field :label="S15.adminStudentsFilter" for-id="student-query">
          <Control id="student-query" v-model="query" type="search" @blur="load" />
        </Field>
      </FormGrid>

      <form class="stack" @submit.prevent="submit">
        <FormGrid :columns="2">
          <Field label="账号" for-id="student-account" required>
            <Control id="student-account" v-model="form.account" />
          </Field>
          <Field :label="S10.labelName" for-id="student-name" required>
            <Control id="student-name" v-model="form.display_name" :maxlength="50" />
          </Field>
          <Field label="初始密码" for-id="student-password" required wide>
            <Control id="student-password" v-model="form.initial_password" type="password" autocomplete="new-password" />
          </Field>
        </FormGrid>
        <div class="row">
          <Btn variant="primary" type="submit">{{ ACTIONS.save }}</Btn>
        </div>
      </form>

      <DataTable v-if="rows.length > 0" :caption="S15.adminStudentsTitle" :columns="columns" :rows="rows" name-key="display_name">
        <template #cell-enabled="{ row }">
          <Pill :variant="row.isEnabled ? 'ok' : 'advice'">
            <template #icon>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
                <path v-for="(d, i) in ICONS.user" :key="i" :d="d" />
              </svg>
            </template>
            {{ row.enabled }}
          </Pill>
        </template>
        <template #cell-actions="{ row }">
          <Btn size="sm" @click="toggle({ id: String(row.id), isEnabled: Boolean(row.isEnabled) })">{{ row.isEnabled ? S10.disabled : S10.enabled }}</Btn>
        </template>
      </DataTable>

      <Notice v-if="errorCode" variant="danger" role="alert">
        <p>{{ errorCode }}</p>
      </Notice>
    </Card>
  </Wrap>
</template>
