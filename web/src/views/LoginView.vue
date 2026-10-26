<script setup lang="ts">
/**
 * S01 登录 + 自助注册（§9.1；桌面自适应追加包 §15）。
 *
 * - 文案逐字取自 content-spec:51–59（S01）与 S15.5（两栏左栏 / 注册面板）；
 * - 失败**不改 state**（令牌保持 null），登录统一文案不区分「账号不存在」与「密码错误」；
 * - 登录失败后保留账号、清空密码、焦点回到密码框；
 * - 注册成功与登录**同一收尾**：写令牌 → `/me` → `consumePending()` → 回跳（§7.3 G2/G7）；
 *   `DUPLICATE_ACCOUNT`(409) 与 `VALIDATION_FAILED`(422) 的就近回填由 `RegisterForm` 负责；
 * - Tab 切换**只切面板**，不改路由、不发请求（§15.2）；
 * - **不实现**密码显示/隐藏切换：该控件的两态可访问名从未冻结（§8.4 #6、README 裁决 6）。
 */
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import LoginForm from '@/components/base/LoginForm.vue'
import RegisterForm from '@/components/base/RegisterForm.vue'
import BrandMark from '@/components/base/BrandMark.vue'
import Field from '@/components/base/Field.vue'
import Control from '@/components/base/Control.vue'
import Btn from '@/components/base/Btn.vue'
import Notice from '@/components/base/Notice.vue'
import { ICONS } from '@/components/base/icons'
import { S01, S02 } from '@/domain/copy'
import { mapErrorText } from '@/domain/mapError'
import { validateLogin } from '@/domain/validate'
import type { AppError } from '@/api/errors'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const session = useSessionStore()

/** 当前面板：默认「登录」；切换不发请求、不改 URL（§15.2）。 */
const tab = ref<'login' | 'register'>('login')

/* ---------------- 登录面板 ---------------- */
const account = ref('')
const password = ref('')
const pending = ref(false)
const failure = ref<AppError | null>(null)

const failureText = computed(() => {
  if (!failure.value) return null
  if (failure.value.code === 'FORBIDDEN') return S01.accountDisabled
  if (failure.value.httpStatus === 401) return S01.invalidCredentials
  return mapErrorText(failure.value)
})

/* ---------------- 注册面板 ---------------- */
const regPending = ref(false)
const regFailure = ref<AppError | null>(null)

/** 左栏三条能力的图标（装饰；文字已承担语义）。 */
const POINT_ICONS = [ICONS.calendar, ICONS.library, ICONS.listChecks]

/**
 * 两种凭据拿到令牌后的**同一收尾**（§15.5 末条 / §7.3 G7）：
 * 必须补 `/me` 才能放行；只有 `planDetail` 允许回跳，其余一律回 assistant。
 */
async function finishAuth(): Promise<void> {
  await session.fetchMe()
  const pendingTarget = session.consumePending()
  if (pendingTarget.routeName === 'planDetail' && pendingTarget.path) {
    await router.replace(pendingTarget.path)
  } else {
    await router.replace({ name: 'assistant' })
  }
}

async function onSubmitLogin(): Promise<void> {
  const issues = validateLogin({ account: account.value, password: password.value })
  if (issues.length > 0) return
  pending.value = true
  failure.value = null
  try {
    await session.login({ account: account.value.trim(), password: password.value })
    await finishAuth()
  } catch (e) {
    failure.value = e as AppError
    password.value = ''
    await nextTick()
    document.getElementById('login-password')?.focus()
  } finally {
    pending.value = false
  }
}

async function onSubmitRegister(payload: { account: string; display_name: string; password: string }): Promise<void> {
  regPending.value = true
  regFailure.value = null
  try {
    await session.register(payload)
    await finishAuth()
  } catch (e) {
    regFailure.value = e as AppError
  } finally {
    regPending.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <section class="login-page__intro">
      <div class="login__brand">
        <BrandMark size="sm" />
        <span class="login__sub">{{ S01.productName }}</span>
      </div>

      <h1>{{ S01.registerTitle }}</h1>
      <p class="login__lead">{{ S01.lead }}</p>

      <!-- 视觉带（§15.7 A 路线：手写线条 SVG）：课表 → 资料 → 计划。
           纯内联（零请求）、单色走 currentColor（--login-art-fg）、无文字；
           纯装饰 → aria-hidden，语义由下面三条能力承担；<1200 与能力清单一起隐藏。 -->
      <figure class="login__art" aria-hidden="true">
        <svg
          class="login__scene"
          viewBox="8 20 468 126"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          focusable="false"
        >
          <g stroke-dasharray="4 6" opacity=".75">
            <path d="M140 86h40" />
            <path d="M304 86h40" />
          </g>
          <g fill="currentColor" stroke="none">
            <circle cx="160" cy="86" r="2.4" />
            <circle cx="324" cy="86" r="2.4" />
          </g>

          <g>
            <rect x="16" y="32" width="124" height="108" rx="10" fill="currentColor" fill-opacity=".035" />
            <path d="M16 56h124" />
            <g opacity=".55">
              <path d="M44 26v6" />
              <path d="M112 26v6" />
            </g>
            <g fill="none" stroke-opacity=".42">
              <rect x="32" y="70" width="9" height="9" rx="2" /><rect x="58" y="70" width="9" height="9" rx="2" />
              <rect x="84" y="70" width="9" height="9" rx="2" /><rect x="110" y="70" width="9" height="9" rx="2" />
              <rect x="32" y="92" width="9" height="9" rx="2" /><rect x="84" y="92" width="9" height="9" rx="2" />
              <rect x="110" y="92" width="9" height="9" rx="2" /><rect x="32" y="114" width="9" height="9" rx="2" />
              <rect x="58" y="114" width="9" height="9" rx="2" />
            </g>
            <rect x="58" y="92" width="9" height="9" rx="2" fill="currentColor" fill-opacity=".8" stroke="none" />
          </g>

          <g>
            <rect x="180" y="32" width="124" height="108" rx="10" fill="currentColor" fill-opacity=".035" />
            <path d="M276 32h18a10 10 0 0 1 10 10v18" />
            <path d="M276 32v18h28" />
            <g transform="translate(192 42) scale(1.15)" stroke-width="1.4">
              <path d="M10 11H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v7a3 3 0 0 1-3 3" />
              <path d="M19 11h-4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v7a3 3 0 0 1-3 3" />
            </g>
            <g opacity=".5">
              <path d="M196 88h84" />
              <path d="M196 100h84" />
              <path d="M196 112h60" />
              <path d="M196 124h40" />
            </g>
          </g>

          <g>
            <rect x="344" y="32" width="124" height="108" rx="10" fill="currentColor" fill-opacity=".035" />
            <rect x="360" y="52" width="10" height="10" rx="3" /><path d="M362.5 57l2 2.2 4-5" /><path d="M380 57h52" opacity=".5" />
            <rect x="360" y="80" width="10" height="10" rx="3" /><path d="M362.5 85l2 2.2 4-5" /><path d="M380 85h44" opacity=".5" />
            <rect x="360" y="108" width="10" height="10" rx="3" /><path d="M380 113h32" opacity=".32" />
          </g>
        </svg>
      </figure>

      <ul class="login__points">
        <li v-for="(p, i) in S01.points" :key="p.title" class="login__point">
          <span class="login__point-ico" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
              <path v-for="(d, k) in POINT_ICONS[i]" :key="k" :d="d" />
            </svg>
          </span>
          <div>
            <b>{{ p.title }}</b>
            <span>{{ p.desc }}</span>
          </div>
        </li>
      </ul>

      <p class="login__note">{{ S02.boundaryNotice }}</p>
    </section>

    <LoginForm :tab="tab" @update:tab="tab = $event">
      <template #login>
        <form class="stack" @submit.prevent="onSubmitLogin">
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
              v-model="password"
              type="password"
              autocomplete="current-password"
              :invalid="!!failure"
            />
          </Field>

          <Btn id="login-submit" variant="primary" block type="submit" :disabled="pending">
            {{ S01.submit }}
          </Btn>

          <button type="button" class="login__switch" @click="tab = 'register'">{{ S01.toRegister }}</button>
        </form>
      </template>

      <template #register>
        <RegisterForm
          :pending="regPending"
          :failure="regFailure"
          @submit="onSubmitRegister"
          @switch="tab = 'login'"
        />
      </template>

      <template #foot>{{ S01.sessionFootnote }}</template>
    </LoginForm>
  </div>
</template>
