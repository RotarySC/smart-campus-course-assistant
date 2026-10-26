<script setup lang="ts">
/**
 * S02–S06 助手（§9.2–§9.6）。**登录后默认页**。
 *
 * - 对话正文**不进 URL**（§7.5）：本视图不读也不写任何 query；
 * - 边界提示条必须逐字出现（content-spec:64，不得改写、不得省略后半句）；
 * - 过程区只展示三类可核实工具动作，**绝不**出现「正在思考」类表述；
 * - 流式过程中**绝不移动焦点**；
 * - 「未保存 / 已保存 / 待确认」三态由 `DraftCard` 表达，待确认 ≠ 失败；
 * - 草稿绑定由**本视图**完成（§2.2 R5），因为 `chat` 不允许静态依赖 `drafts`（§6.2）；
 * - ≥1200 两栏（主列 + 280 右栏，桌面 spec §6.1）；右栏数据来自既有接口，**不新增接口**。
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
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
import ContextRail from '@/components/product/ContextRail.vue'
import { ICONS } from '@/components/base/icons'
import type { IconName } from '@/components/base/icons'
import { S02, S03, S05, S06, S15 } from '@/domain/copy'
import { canSubmitMessage } from '@/domain/validate'
import { mapErrorText } from '@/domain/mapError'
import { useChatStore } from '@/stores/chat'
import { useDraftsStore } from '@/stores/drafts'
import { usePlansStore } from '@/stores/plans'
import { useSchedulesStore } from '@/stores/schedules'
import { useWriteOpsStore } from '@/stores/writeOps'

const router = useRouter()
const chat = useChatStore()
const drafts = useDraftsStore()
const writeOps = useWriteOpsStore()
const schedules = useSchedulesStore()
const plans = usePlansStore()

const message = ref('')

const active = computed(() => chat.activeRound)
const canSubmit = computed(() => canSubmitMessage(message.value))
const showIdle = computed(() => chat.rounds.length === 0)

/**
 * 对话区自己滚（2026-10-26 起输入条不再参与页面滚动）。
 * 只在「用户本来就在底部」时跟随（`chat.shouldFollowScroll`，距底 < 48px），
 * 否则不动 —— 用户往上翻看历史时不能被流式文本强行拽回底部。
 */
const scrollEl = ref<HTMLElement | null>(null)
const streamChars = computed(() => {
  const rounds = chat.rounds.reduce(
    (n, r) => n + r.userMessage.length + r.blocks.reduce((m, b) => m + (b.text?.length ?? 0), 0),
    0,
  )
  return rounds + (active.value ? active.value.blocks.length : 0)
})
watch(streamChars, () => {
  const el = scrollEl.value
  if (!el) return
  if (chat.shouldFollowScroll(el)) void nextTick(() => { el.scrollTop = el.scrollHeight })
})

/** 三个示例入口的图标（装饰性，可访问名来自按钮文字）。 */
const EXAMPLE_ICON: IconName[] = ['calendar', 'search', 'listChecks']

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

/** 右栏「让助手拟定」：同样只填入示例入口的句子，不自动提交。 */
function draftPlan() {
  message.value = S02.examples[2] ?? ''
  void nextTick(() => document.getElementById('composer-input')?.focus())
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

/**
 * 右栏两份数据：都用**既有**接口，任一失败只影响自己那一栏（`allSettled`）。
 * store 会把失败记进 `status/error` 并 rethrow，这里吞掉即可（右栏自己渲染错误文案）。
 */
async function loadRail(): Promise<void> {
  await Promise.allSettled([schedules.fetchMine({}), plans.list({ page_size: 5 })])
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
  void loadRail()
})
</script>

<template>
  <Wrap>
    <div class="workspace">
      <div class="workspace__main">
        <!-- 对话区自己滚（.workspace__scroll），输入条留在滚动区外面，永远停在主列底部 -->
        <div ref="scrollEl" class="workspace__scroll">
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

          <div v-if="showIdle" class="suggest">
            <button
              v-for="(ex, i) in S02.examples"
              :key="ex"
              type="button"
              class="suggest__item"
              @click="useExample(ex)"
            >
              <span class="suggest__ico" aria-hidden="true">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
                  <path v-for="(d, j) in ICONS[EXAMPLE_ICON[i] ?? 'messageCircle']" :key="j" :d="d" />
                </svg>
              </span>
              <span>{{ ex }}</span>
            </button>
          </div>
          <EmptyState v-else-if="!active" variant="empty" icon="messageCircle" :title="S02.title">
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

            <!-- 全库为空（E3）：`.empty` + inbox，和下面「依据不足」是两个不同状态
                 （一个有资料但没命中，一个根本没有资料 → 该找管理员，不该换问法）。 -->
            <EmptyState
              v-else-if="
                active.terminal === 'succeeded' &&
                active.citations.length === 0 &&
                active.blocks.length > 0 &&
                active.corpusEmpty
              "
              variant="empty"
              icon="inbox"
              :title="S05.libraryEmpty"
            />

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
        </div>

        <Composer
          v-model="message"
          :label="S02.composerLabel"
          :hint="S02.composerHint"
          :enter-hint="S15.composerEnterHint"
          :pending="chat.isStreaming"
          @submit="submit"
        >
          <template #actions>
            <!-- 空白不可提交：**按钮**禁用（content-spec S02）；输入框不得因空白而禁用，
                 否则用户永远无法输入第一个字符（阶段 B 未渲染验证时漏掉的真实缺陷）。
                 用 `type="submit"` 走表单提交，避免再挂一个 click 处理器（会双触发）。
                 2026-10-26 改版：圆形图标按钮（上行箭头），可访问名仍是 `S02.send`；
                 快捷键说明改为它的冒泡提示（`data-tip`），禁用态由外层包一层 `.composer__send`
                 承接 hover（`:disabled` 的按钮本身收不到 `:hover`）。 -->
            <span class="composer__send" :data-tip="S15.composerEnterHint">
              <Btn
                class="btn--icon"
                variant="primary"
                type="submit"
                :disabled="!canSubmit || chat.isStreaming"
                :aria-label="S02.send"
                aria-describedby="composer-enter-hint"
              >
                <template #icon>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
                    <path v-for="(d, i) in ICONS.arrowUp" :key="i" :d="d" />
                  </svg>
                </template>
              </Btn>
            </span>
          </template>
        </Composer>
      </div>

      <ContextRail
        :schedule-status="schedules.status"
        :schedules="schedules.items"
        :plan-status="plans.status"
        :plans="plans.items"
        @draft-plan="draftPlan"
      />
    </div>
  </Wrap>
</template>
