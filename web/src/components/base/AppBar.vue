<script setup lang="ts">
/**
 * `appbar` 族（01-shell-navigation.md §2；rb.css:121–137）。
 *
 * 结构：品牌 → 导航（`margin-left:auto` 推到右侧）→ 用户区。
 * 用户区**只有一处登出入口**：菜单触发器 + `.usermenu__panel` 里的「退出登录」（§5.4）。
 *
 * 面板显隐**不用 CSS-only 悬停**（`:focus-within` 不在白名单，§5.2）：
 * `open` 状态驱动 + `v-show`；打开＝悬停或点击触发器，关闭＝移出、`Escape`、焦点移出容器、点击外部。
 * `aria-expanded` / `aria-controls` 跟随 `open`，两者是同一个状态的两种投影。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { CHROME } from '@/domain/copy'
import { ICONS } from '@/components/base/icons'

const props = defineProps<{ userLabel?: string }>()
const emit = defineEmits<{ logout: [] }>()

const open = ref(false)
const rootEl = ref<HTMLElement | null>(null)
const triggerEl = ref<HTMLButtonElement | null>(null)
const panelId = 'usermenu-panel'

/** 姓名首字圆牌：不请求任何图像资源（content-spec §0），文案来自数据。 */
const initial = computed(() => (props.userLabel ?? '').trim().slice(0, 1))

function show() {
  open.value = true
}
function hide() {
  open.value = false
}
function toggle() {
  open.value = !open.value
}

/** `Escape` 关闭后焦点必须留在触发器上，否则键盘用户会掉到文档开头。 */
function closeAndFocus() {
  open.value = false
  triggerEl.value?.focus()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) closeAndFocus()
}

function onPointerDown(e: Event) {
  const root = rootEl.value
  if (open.value && root && !root.contains(e.target as Node)) open.value = false
}

function onFocusOut(e: FocusEvent) {
  const root = rootEl.value
  const next = e.relatedTarget as Node | null
  if (root && next && !root.contains(next)) open.value = false
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('pointerdown', onPointerDown)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('pointerdown', onPointerDown)
})

defineExpose({ open })
</script>

<template>
  <header class="appbar">
    <div class="appbar__inner">
      <slot name="brand" />
      <nav class="appbar__nav" :aria-label="CHROME.primaryNav"><slot name="nav" /></nav>
      <div class="appbar__user">
        <div
          v-if="userLabel"
          ref="rootEl"
          class="usermenu"
          @mouseenter="show"
          @mouseleave="hide"
          @focusout="onFocusOut"
        >
          <button
            ref="triggerEl"
            type="button"
            class="usermenu__trigger"
            aria-haspopup="menu"
            :aria-expanded="open ? 'true' : 'false'"
            :aria-controls="panelId"
            @click="toggle"
          >
            <span class="usermenu__avatar" aria-hidden="true">{{ initial }}</span>
            <span class="small">{{ userLabel }}</span>
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
              focusable="false"
            >
              <path v-for="(d, i) in ICONS.chevronDown" :key="i" :d="d" />
            </svg>
          </button>
          <div v-show="open" :id="panelId" class="usermenu__panel" role="menu">
            <button type="button" class="usermenu__item" role="menuitem" @click="emit('logout')">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.75"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
                focusable="false"
              >
                <path v-for="(d, i) in ICONS.logOut" :key="i" :d="d" />
              </svg>
              {{ CHROME.logout }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>
