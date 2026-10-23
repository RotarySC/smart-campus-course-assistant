<script setup lang="ts">
/**
 * `login` 族（01-shell-navigation.md §10；rb.css:405–411）。
 *
 * **禁止实现密码显示/隐藏切换**：该控件的两态可访问名从未在 content-spec 冻结
 * （design/system/README.md 裁决 6、前端详细设计 §8.4 #6、01-shell-navigation.md:936）。
 * 在文案冻结前该槽位不得实现。
 */
defineProps<{ pending?: boolean }>()
defineEmits<{ submit: [] }>()
</script>

<template>
  <div class="login">
    <div class="login__brand"><slot name="brand" /></div>
    <div class="card">
      <form class="card__body stack" @submit.prevent="$emit('submit')">
        <slot />
      </form>
    </div>
    <p class="login__foot"><slot name="foot" /></p>
  </div>
</template>
