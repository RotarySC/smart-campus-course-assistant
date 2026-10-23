<script setup lang="ts">
/**
 * S01 登录（§9.1）。
 *
 * - 文案逐字取自 content-spec:51–59；
 * - 失败**不改 state**（令牌保持 null），统一文案不区分「账号不存在」与「密码错误」；
 * - 失败后保留账号、清空密码、焦点回到密码框；
 * - **不实现**密码显示/隐藏切换：该控件的两态可访问名从未冻结（§8.4 #6）。
 */
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import LoginForm from '@/components/base/LoginForm.vue'
import BrandMark from '@/components/base/BrandMark.vue'
import Field from '@/components/base/Field.vue'
import Control from '@/components/base/Control.vue'
import Btn from '@/components/base/Btn.vue'
import Notice from '@/components/base/Notice.vue'
import Wrap from '@/components/base/Wrap.vue'
import { ICONS } from '@/components/base/icons'
import { S01 } from '@/domain/copy'
import { mapErrorText } from '@/domain/mapError'
import { validateLogin } from '@/domain/validate'
import type { AppError } from '@/api/errors'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const session = useSessionStore()

const account = ref('')
const password = ref('')
const pending = ref(false)
const failure = ref<AppError | null>(null)
const passwordRef = ref<{ $el?: HTMLElement } | null>(null)

const failureText = computed(() => {
  if (!failure.value) return null
  if (failure.value.code === 'FORBIDDEN') return S01.accountDisabled
  if (failure.value.httpStatus === 401) return S01.invalidCredentials
  return mapErrorText(failure.value)
})

async function onSubmit() {
  const issues = validateLogin({ account: account.value, password: password.value })
  if (issues.length > 0) return
  pending.value = true
  failure.value = null
  try {
    await session.login({ account: account.value.trim(), password: password.value })
    // G7：登录成功后必须补 /me，再放行。
    await session.fetchMe()
    const pendingTarget = session.consumePending()
    // 只有 planDetail 允许登录后回跳，其余一律回 assistant（§7.3 G2 / §7.6）。
    if (pendingTarget.routeName === 'planDetail' && pendingTarget.path) {
      await router.replace(pendingTarget.path)
    } else {
      await router.replace({ name: 'assistant' })
    }
  } catch (e) {
    failure.value = e as AppError
    password.value = ''
    await nextTick()
    const el = document.getElementById('login-password')
    el?.focus()
  } finally {
    pending.value = false
  }
}
void passwordRef
</script>

<template>
  <Wrap>
    <LoginForm :pending="pending" @submit="onSubmit">
      <template #brand>
        <BrandMark size="lg" :name="S01.productName">
          <span class="login__name">{{ S01.productName }}</span>
        </BrandMark>
        <span class="login__sub">{{ S01.subtitle }}</span>
      </template>

      <Notice v-if="failureText" variant="danger" role="alert">
        <template #icon>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
            <path v-for="(d, i) in ICONS.triangleAlert" :key="i" :d="d" />
          </svg>
        </template>
        <b>{{ failureText }}</b>
      </Notice>

      <Field :label="S01.labelAccount" for-id="login-account" required>
        <Control
          id="login-account"
          v-model="account"
          type="text"
          autocomplete="username"
          :invalid="!!failure"
        />
      </Field>

      <Field :label="S01.labelPassword" for-id="login-password" required>
        <Control
          id="login-password"
          ref="passwordRef"
          v-model="password"
          type="password"
          autocomplete="current-password"
          :invalid="!!failure"
        />
      </Field>

      <Btn variant="primary" block type="submit" :disabled="pending">{{ S01.submit }}</Btn>

      <template #foot>{{ S01.sessionFootnote }}</template>
    </LoginForm>
  </Wrap>
</template>
