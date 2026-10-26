<script setup lang="ts">
/**
 * `login` 族 · 右卡（01-shell-navigation.md §10；rb.css:503–535）。
 *
 * 职责边界：
 * - 只管「Tab 组 + 两个面板的显隐 + 会话说明」，**不持有表单状态、不发请求**；
 *   两个面板由 `LoginView` 通过 `#login` / `#register` 槽注入（字段级校验各自就近显示）。
 * - Tab 语义按 §15.2：`role="tablist"` + 两个 `role="tab"`（`aria-selected` / `aria-controls`）
 *   + 两个 `role="tabpanel"`（`aria-labelledby`；非当前面板 `hidden`，不是 `display:none` 切换）。
 * - 触发只用原生 `button`（点击 + Enter/Space），**不实现**左右箭头 roving —— 已登记为已知简化。
 * - 选中态只认 `[aria-selected="true"]`，不自造 `.is-on` 状态类（`no-unknown-state` 白名单）。
 * - **禁止实现密码显示/隐藏切换**：该控件的两态可访问名从未在 content-spec 冻结
 *   （design/system/README.md 裁决 6、01-shell-navigation.md:936）。在文案冻结前该槽位不得实现。
 */
import { S01 } from '@/domain/copy'

/** 两个面板的标识；与 `LoginView` 的 `tab` 状态同名字面量（不引入循环 import）。 */
const props = defineProps<{ tab: 'login' | 'register' }>()
const emit = defineEmits<{ 'update:tab': ['login' | 'register'] }>()

const TABS: ReadonlyArray<{ id: 'login' | 'register'; label: string; panel: string }> = [
  { id: 'login', label: S01.tabLogin, panel: 'login-panel' }, // content-spec:243
  { id: 'register', label: S01.tabRegister, panel: 'register-panel' }, // content-spec:243
]
</script>

<template>
  <section class="login__card">
    <div class="login__tabs" role="tablist">
      <button
        v-for="t in TABS"
        :id="`${t.id}-tab`"
        :key="t.id"
        type="button"
        class="login__tab"
        role="tab"
        :aria-selected="props.tab === t.id"
        :aria-controls="t.panel"
        @click="emit('update:tab', t.id)"
      >
        {{ t.label }}
      </button>
    </div>

    <div
      id="login-panel"
      class="login__panel"
      role="tabpanel"
      aria-labelledby="login-tab"
      :hidden="props.tab !== 'login'"
    >
      <slot name="login" />
    </div>

    <div
      id="register-panel"
      class="login__panel"
      role="tabpanel"
      aria-labelledby="register-tab"
      :hidden="props.tab !== 'register'"
    >
      <slot name="register" />
    </div>

    <p class="login__foot"><slot name="foot" /></p>
  </section>
</template>
