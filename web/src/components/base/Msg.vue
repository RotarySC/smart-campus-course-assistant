<script setup lang="ts">
/**
 * `chat` 族的消息容器（03-conversation.md §Chat；rb.css:234–242）。
 * `.msg--user` **必须同时有可见说话人文字**（不能只靠对齐方向区分）。
 * 无 `:hover`/`:active`/`transition`。
 */
withDefaults(defineProps<{ who: string; user?: boolean }>(), { user: false })
</script>

<template>
  <article class="msg" :class="{ 'msg--user': user }">
    <span class="msg__who">{{ who }}</span>
    <slot />
  </article>
</template>
