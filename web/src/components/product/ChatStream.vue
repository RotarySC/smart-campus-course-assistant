<script setup lang="ts">
/**
 * `ChatStream`（组合件，CONTRACT §3.2 点名）。
 *
 * product 件**自身零样式**（不写颜色/尺度，不写 `var(--*)`），只把 store 数据喂给 base 件；
 * 状态语义一律落在 base 件的 props 上，不在这里用本地布尔量自己实现一遍（§10.3）。
 *
 * 终态 / 「待确认」/「依据不足」这些**跨 store** 的表达不由本件负责 ——
 * 它们需要同时读 `chat` 与 `writeOps`，按 §2.2 R5「只有 views 可以读多个 store 并组合」
 * 放在 `AssistantView` 里，本件只提供 `#terminal` 槽位。
 */
import { computed } from 'vue'
import Msg from '@/components/base/Msg.vue'
import Bubble from '@/components/base/Bubble.vue'
import Steps from '@/components/base/Steps.vue'
import Step from '@/components/base/Step.vue'
import { S03 } from '@/domain/copy'
import { unpairedSteps } from '@/domain/chatMachine'
import type { ChatRoundVM } from '@/stores/chat'

const props = defineProps<{ round: ChatRoundVM }>()

const answer = computed(() => props.round.blocks.map((b) => b.text).join(''))
const pending = computed(() => unpairedSteps(props.round))
const settled = computed(() => props.round.steps.filter((s) => !pending.value.includes(s)))
/** 仍为 running 的步骤一律渲染为「未完成」，既不是成功也不是失败（§5.4 收尾规则）。 */
const ordered = computed(() => [...settled.value, ...pending.value])
</script>

<template>
  <div class="chat">
    <Msg who="你" user>
      <Bubble>{{ round.userMessage }}</Bubble>
    </Msg>

    <Msg who="校园课程助手">
      <Steps v-if="round.steps.length > 0" :summary="S03.processTitle" :model-value="false">
        <Step
          v-for="step in ordered"
          :key="step.toolCallId"
          :status="step.status"
          :title="step.displayName"
          :sub="step.code ?? undefined"
        />
      </Steps>

      <Bubble>{{ answer }}</Bubble>
      <slot name="terminal" />
    </Msg>
  </div>
</template>
