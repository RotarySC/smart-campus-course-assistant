<script setup lang="ts">
/**
 * S02–S06 助手（§9.2–§9.6）。**登录后默认页**。
 *
 * - 对话正文**不进 URL**（§7.5）：本视图不读也不写任何 query；
 * - 边界提示条必须逐字出现（content-spec:64，不得改写、不得省略后半句）；
 * - 过程区只展示三类可核实工具动作，**绝不**出现「正在思考」类表述；
 * - 流式过程中**绝不移动焦点**；
 * - 「未保存 / 已保存 / 待确认」三态由 `DraftCard` 表达，待确认 ≠ 失败；
 * - 草稿绑定由**本视图**完成（§2.2 R5），因为 `chat` 不允许静态依赖 `drafts`（§6.2）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import Wrap from '@/components/base/Wrap.vue'
import Card from '@/components/base/Card.vue'
import Btn from '@/components/base/Btn.vue'
import Notice from '@/components/base/Notice.vue'
import Composer from '@/components/base/Composer.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import Pill from '@/components/base/Pill.vue'
import ChatStream from '@/components/product/ChatStream.vue'
import CitationList from '@/components/product/CitationList.vue'
import DraftCard from '@/components/product/DraftCard.vue'
import { ICONS } from '@/components/base/icons'
import { S02, S03, S05, S06 } from '@/domain/copy'
import { canSubmitMessage } from '@/domain/validate'
import { mapErrorText } from '@/domain/mapError'
import { useChatStore } from '@/stores/chat'
import { useDraftsStore } from '@/stores/drafts'
import { useWriteOpsStore } from '@/stores/writeOps'

const router = useRouter()
const chat = useChatStore()
const drafts = useDraftsStore()
const writeOps = useWriteOpsStore()

const message = ref('')

const active = computed(() => chat.activeRound)
const canSubmit = computed(() => canSubmitMessage(message.value))
const showIdle = computed(() => chat.rounds.length === 0)

const draftState = computed<'unsaved' | 'saved' | 'unconfirmed'>(() => {
  if (!drafts.draftId) return 'unsaved'
  const rec = drafts.operationId ? writeOps.records[drafts.operationId] : undefined
  if (rec && rec.state === 'pending') return 'unconfirmed'
  if (drafts.saved && drafts.planId) return 'saved'
  return 'unsaved'
})

const activeWriteOp = computed(() => {
  const id = active.value?.operationId ?? drafts.operationId
  return id ? writeOps.records[id] : undefined
})

async function submit() {
  if (!canSubmit.value) return
  const text = message.value
  message.value = ''
  await chat.submit(text)
}

function useExample(text: string) {
  // PRD：示例入口点击**只填入输入框，不自动提交**。
  message.value = text
}

function clearConversation() {
  chat.clearConversation()
}

async function queryWriteStatus() {
  const id = activeWriteOp.value?.operationId
  if (id) await writeOps.verify(id)
}

function openPlan() {
  const id = drafts.planId ?? active.value?.planId
  if (id) void router.push({ name: 'planDetail', params: { planId: id } })
}

// 草稿绑定：状态机只把 draftId 记在 turn 上，绑定动作由视图完成（§2.2 R5）。
watch(
  () => active.value?.draftId,
  (id) => {
    if (!id) return
    drafts.bind(id, active.value?.draftVersion ?? undefined)
    void drafts.load(id)
  },
)

onMounted(() => {
  // 依赖已经建立（writeOps 在 drafts 之前被 use）。
  void drafts
  void writeOps
})
</script>

<template>
  <Wrap assistant>
    <Card :title="S02.title">
      <p>{{ S02.capability }}</p>

      <Notice variant="info" role="note">
        <template #icon>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
            <path v-for="(d, i) in ICONS.info" :key="i" :d="d" />
          </svg>
        </template>
        <p>{{ S02.boundaryNotice }}</p>
        <template #actions>
          <Btn size="sm" @click="clearConversation">{{ S02.clearConversation }}</Btn>
        </template>
      </Notice>

      <div v-if="showIdle" class="chips">
        <Btn v-for="ex in S02.examples" :key="ex" size="sm" @click="useExample(ex)">{{ ex }}</Btn>
      </div>
      <EmptyState v-else-if="!active" variant="empty" :title="S02.title">
        <template #actions>
          <Btn size="sm" @click="clearConversation">{{ S02.clearConversation }}</Btn>
        </template>
      </EmptyState>

      <p v-if="active && chat.isStreaming" class="row">
        <Pill variant="info">
          <template #icon>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
              <path v-for="(d, i) in ICONS.loader" :key="i" :d="d" />
            </svg>
          </template>
          {{ S03.processing }}
        </Pill>
        <Btn size="sm" @click="chat.cancel(active.requestId ?? '')">{{ S03.stop }}</Btn>
      </p>
    </Card>

    <ChatStream v-if="active" :round="active">
      <template #terminal>
        <CitationList v-if="active.citations.length > 0" :references="active.citations" sourced />

        <!-- 「待确认」：**不是失败**。文案逐字取自 S06。 -->
        <Notice v-if="activeWriteOp && activeWriteOp.state === 'pending'" variant="warn" role="status">
          <p>{{ S06.confirming }}</p>
          <p>{{ S06.unconfirmedNotice }}</p>
          <template #actions>
            <Btn size="sm" @click="queryWriteStatus">{{ S06.queryWriteStatus }}</Btn>
          </template>
        </Notice>

        <!-- 依据不足（检索成功但没有足够依据）。 -->
        <Notice
          v-else-if="active.terminal === 'succeeded' && active.citations.length === 0 && active.blocks.length > 0"
          variant="warn"
          role="note"
        >
          <p>{{ S05.insufficient }}</p>
          <template #actions>
            <Btn size="sm" @click="useExample(S02.examples[1] ?? '')">{{ S05.rephrase }}</Btn>
          </template>
        </Notice>
      </template>
    </ChatStream>

    <DraftCard
      v-if="drafts.draftId"
      :state="draftState"
      :plan-id="drafts.planId"
      :fields="drafts.fields"
      :basis-schedule="drafts.basisTypes.includes('schedule')"
      :basis-documents="drafts.basisTypes.includes('documents')"
      @save="drafts.save()"
      @edit="openPlan"
      @query-status="queryWriteStatus"
    />

    <Notice v-if="chat.error" variant="danger" role="alert">
      <p>{{ mapErrorText(chat.error) ?? chat.error.code }}</p>
      <span class="small">{{ chat.error.requestId }}</span>
    </Notice>

    <Composer
      v-model="message"
      :label="S02.composerLabel"
      :hint="S02.composerHint"
      :pending="chat.isStreaming"
      @submit="submit"
    >
      <template #actions>
        <!-- 空白不可提交：**按钮**禁用（content-spec S02）；输入框不得因空白而禁用，
             否则用户永远无法输入第一个字符（阶段 B 未渲染验证时漏掉的真实缺陷）。 -->
        <Btn variant="primary" :disabled="!canSubmit || chat.isStreaming" @click="submit">{{ S02.send }}</Btn>
      </template>
    </Composer>
  </Wrap>
</template>
