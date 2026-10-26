<script setup lang="ts">
/**
 * `register` 面板（S01 自助注册；content-spec S15.5；openapi `POST /auth/register`）。
 *
 * - 客户端只为「明显不成立」把关（`validateRegister`）：不通过**不发请求**，
 *   错误就近显示在字段下并把焦点送到**首个**错误字段。
 * - 服务端 `VALIDATION_FAILED.field_errors[].reason` 是权威，按 `field` 就近回填；
 *   `DUPLICATE_ACCOUNT`(409) 落在账号字段（文案取自 `mapErrorText`，不自造）。
 * - 与字段无关的失败（网络 / 5xx / 未冻结码）走表单顶部 `Notice variant="danger" role="alert"`，
 *   只渲染「已冻结句子 ?? code」+ request_id —— 绝不展示 `AppError.message`（§3.3 末段）。
 * - 密码显示/隐藏切换**不实现**（design/system/README.md 裁决 6）。
 * - 本组件不发请求：提交只 `emit('submit', payload)`，由 `LoginView` 统一写令牌 + 回跳。
 */
import { computed, nextTick, ref, watch } from 'vue'
import Btn from './Btn.vue'
import Control from './Control.vue'
import Field from './Field.vue'
import Notice from './Notice.vue'
import { ICONS } from './icons'
import { S01 } from '@/domain/copy'
import { fieldIssueText, mapErrorText } from '@/domain/mapError'
import { MAXLEN, validateRegister } from '@/domain/validate'
import type { FieldIssues } from '@/domain/validate'
import type { AppError } from '@/api/errors'

const props = withDefaults(defineProps<{ pending?: boolean; failure?: AppError | null }>(), {
  pending: false,
  failure: null,
})
const emit = defineEmits<{
  submit: [{ account: string; display_name: string; password: string }]
  switch: []
}>()

const account = ref('')
const displayName = ref('')
const password = ref('')
const confirm = ref('')
const issues = ref<FieldIssues>([])

/** 字段名 → 控件 id（与 §15.5 的冻结 id 一致；错误文本要在就近位置显示并聚焦）。 */
const FIELD_ID: Record<string, string> = {
  account: 'register-account',
  display_name: 'register-name',
  password: 'register-password',
  confirm: 'register-password2',
}

/** 某字段的提示：服务端权威 reason 优先，其次重复账号（409），最后是客户端 kind。 */
function text(field: string): string | null {
  if (field === 'account' && props.failure?.code === 'DUPLICATE_ACCOUNT') {
    return mapErrorText(props.failure) // content-spec:251
  }
  const server = props.failure?.fieldErrors?.find((f) => f.field === field)?.reason
  if (server) return server
  const hit = issues.value.find((i) => i.field === field)
  return hit ? fieldIssueText(hit.kind, field) : null
}

/** 字段外的失败：没有就近落点时才升级到顶部提示。 */
const genericFailure = computed<{ text: string; requestId: string } | null>(() => {
  const f = props.failure
  if (!f) return null
  if (f.code === 'DUPLICATE_ACCOUNT') return null
  if (f.code === 'VALIDATION_FAILED' && (f.fieldErrors?.length ?? 0) > 0) return null
  return { text: mapErrorText(f) ?? f.code ?? '', requestId: f.requestId ?? '' }
})

function clearIssue(field: string): void {
  if (issues.value.length === 0) return
  issues.value = issues.value.filter((i) => i.field !== field)
}
watch(account, () => clearIssue('account'))
watch(displayName, () => clearIssue('display_name'))
watch(password, () => clearIssue('password'))
watch(confirm, () => clearIssue('confirm'))

async function onSubmit(): Promise<void> {
  issues.value = validateRegister({
    account: account.value,
    display_name: displayName.value,
    password: password.value,
    confirm: confirm.value,
  })
  if (issues.value.length > 0) {
    await nextTick()
    const first = issues.value[0]
    if (first) document.getElementById(FIELD_ID[first.field] ?? '')?.focus()
    return
  }
  emit('submit', {
    account: account.value.trim(),
    display_name: displayName.value.trim(),
    password: password.value,
  })
}
</script>

<template>
  <form class="stack" @submit.prevent="onSubmit">
    <Notice v-if="genericFailure" variant="danger" role="alert">
      <template #icon>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
          <path v-for="(d, i) in ICONS.triangleAlert" :key="i" :d="d" />
        </svg>
      </template>
      <b>{{ genericFailure.text }}</b>
      <span v-if="genericFailure.requestId" class="small">{{ genericFailure.requestId }}</span>
    </Notice>

    <Field :label="S01.labelAccount" for-id="register-account" required :error="text('account')">
      <Control
        id="register-account"
        v-model="account"
        type="text"
        autocomplete="username"
        :maxlength="MAXLEN.account"
        :invalid="!!text('account')"
        :describedby="text('account') ? 'register-account-error' : ''"
      />
    </Field>

    <Field :label="S01.labelName" for-id="register-name" required :error="text('display_name')">
      <Control
        id="register-name"
        v-model="displayName"
        type="text"
        autocomplete="nickname"
        :maxlength="MAXLEN.display_name"
        :invalid="!!text('display_name')"
        :describedby="text('display_name') ? 'register-name-error' : ''"
      />
    </Field>

    <Field :label="S01.labelPassword" for-id="register-password" required :error="text('password')">
      <Control
        id="register-password"
        v-model="password"
        type="password"
        autocomplete="new-password"
        :maxlength="MAXLEN.password"
        :invalid="!!text('password')"
        :describedby="text('password') ? 'register-password-error' : ''"
      />
    </Field>

    <Field :label="S01.labelConfirm" for-id="register-password2" required :error="text('confirm')">
      <Control
        id="register-password2"
        v-model="confirm"
        type="password"
        autocomplete="new-password"
        :maxlength="MAXLEN.password"
        :invalid="!!text('confirm')"
        :describedby="text('confirm') ? 'register-password2-error' : ''"
      />
    </Field>

    <Btn id="register-submit" variant="primary" block type="submit" :disabled="pending">
      {{ S01.submitRegister }}
    </Btn>

    <button type="button" class="login__switch" @click="emit('switch')">{{ S01.toLogin }}</button>
  </form>
</template>
