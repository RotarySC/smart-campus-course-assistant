<script setup lang="ts">
/**
 * `prose` 族（03-conversation.md §Prose；rb.css:170 + 106–110）。
 *
 * **只允许白名单元素**，不引入 `v-html` 直出（NFR-SEC-003）。
 * 生产实现应把 Markdown 渲染成白名单 VNode；本骨架直接渲染纯文本行，
 * 这样「不得 v-html」这条禁令在骨架阶段就已经成立。
 * `--prose-*` 的**全局元素规则留在 `global.css`**（§8.5 的特殊警告）：
 * 若搬进本组件的 `scoped` 样式，`.prose` 内的段落节奏/标题字重/链接色/行内代码字体会静默丢失。
 */
defineProps<{ text: string }>()
</script>

<template>
  <div class="prose">
    <p v-for="(line, i) in text.split('\n')" :key="i">{{ line }}</p>
  </div>
</template>
