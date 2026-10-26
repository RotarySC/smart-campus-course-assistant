<script setup lang="ts">
/**
 * `ContextRail`（组合件，阶段 B 新增；03-conversation.md 组合件一节）。
 *
 * 助手页右栏：今日课表 + 学习计划。**不新增接口** —— 数据只来自既有
 * `GET /me/schedules`（服务端当日）与 `GET /me/plans`，由视图加载后传进来。
 *
 * 两种空态必须分开（SRS INV-05）：`error` 是「读取失败」，`items=[]` 是「今天没有课」，
 * 前者**不得**渲染成后者的视觉或文案。
 *
 * 它是**组合件**，不是 `components/base/*`：不新增 L3 组、不自带样式，
 * 只用 `.workspace__rail*` / `.card` / `.stack` / `.small` / `.muted` 这些既有 class。
 *
 * 折叠（2026-10-26 用户需求）：≥1200 时右栏是 `position:fixed` 的悬浮卡，**放不下就会被视口底切掉**
 * 且滚不到。所以量一次「正文自然高度 + 顶部偏移」，一旦超出视口就折成一行摘要
 * （标题 + 条数，各自链到「我的课表 / 学习计划」页），视口拉高再自动展开。
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import Card from '@/components/base/Card.vue'
import { S15 } from '@/domain/copy'
import { formatTimeRange } from '@/domain/format'
import type { Plan, Schedule } from '@/api/types'

type LoadStatus = 'idle' | 'loading' | 'ready' | 'error'

const props = defineProps<{
  scheduleStatus: LoadStatus
  schedules: Schedule[]
  planStatus: LoadStatus
  plans: Plan[]
}>()

const emit = defineEmits<{ 'draft-plan': [] }>()

/** 加载中与未开始都显示「正在读取…」：未开始的一瞬不该闪出空态。 */
const scheduleBusy = computed(() => props.scheduleStatus === 'idle' || props.scheduleStatus === 'loading')
const planBusy = computed(() => props.planStatus === 'idle' || props.planStatus === 'loading')

/* ---------- 折叠判定 ---------- */
/** 摘要条与视口底至少留出的空隙（与输入条的浮起间距同一量级，判定用，不上样式）。 */
const RAIL_BOTTOM_GAP = 12

const railEl = ref<HTMLElement | null>(null)
const collapsed = ref(false)

function syncCollapse(): void {
  const el = railEl.value
  const body = el?.querySelector<HTMLElement>('.workspace__rail-body')
  if (!el || !body) return
  // 折叠时正文是绝对定位隐藏的，仍是"完整展开"的布局尺寸，所以这个判断在两种状态下都成立。
  const needed = el.getBoundingClientRect().top + body.scrollHeight + RAIL_BOTTOM_GAP
  collapsed.value = needed > window.innerHeight
}

onMounted(() => {
  syncCollapse()
  window.addEventListener('resize', syncCollapse)
})

onUnmounted(() => window.removeEventListener('resize', syncCollapse))

// 课表 / 计划条数变化会改变正文高度，量一次再定
watch(
  () => [props.schedules.length, props.plans.length, props.scheduleStatus, props.planStatus],
  () => void nextTick(syncCollapse),
)
</script>

<template>
  <aside ref="railEl" class="workspace__rail" :class="{ 'workspace__rail--collapsed': collapsed }">
    <div class="workspace__rail-body">
      <Card :title="S15.railScheduleTitle">
        <p v-if="scheduleBusy" class="small muted">{{ S15.railLoading }}</p>
        <p v-else-if="scheduleStatus === 'error'" class="small muted">{{ S15.railScheduleError }}</p>
        <p v-else-if="schedules.length === 0" class="small muted">{{ S15.railNoClass }}</p>
        <div v-else class="stack">
          <div v-for="s in schedules" :key="s.id" class="small">
            <b>{{ formatTimeRange(s.start_time, s.end_time) }}</b>
            {{ s.course_name }}
            <span v-if="s.location" class="muted"> · {{ s.location }}</span>
          </div>
        </div>
        <template #foot>
          <RouterLink class="small" :to="{ name: 'schedules' }">{{ S15.railWeekLink }}</RouterLink>
        </template>
      </Card>

      <Card :title="S15.railPlansTitle">
        <p v-if="planBusy" class="small muted">{{ S15.railLoading }}</p>
        <p v-else-if="planStatus === 'error'" class="small muted">{{ S15.railPlansError }}</p>
        <template v-else-if="plans.length === 0">
          <p class="small muted">{{ S15.railNoPlans }}</p>
          <button type="button" class="btn btn--sm" @click="emit('draft-plan')">{{ S15.railDraftAction }}</button>
        </template>
        <div v-else class="stack">
          <div v-for="p in plans" :key="p.id" class="small">
            <RouterLink :to="{ name: 'planDetail', params: { planId: p.id } }">{{ p.title }}</RouterLink>
            <span v-if="p.start_date" class="muted"> · {{ p.start_date }}</span>
          </div>
        </div>
        <template #foot>
          <RouterLink class="small" :to="{ name: 'plans' }">{{ S15.railAllLink }}</RouterLink>
        </template>
      </Card>
    </div>

    <!-- 折叠摘要：只用既有文案（两块的标题）+ 数字，不新增文案 -->
    <div class="workspace__rail-summary">
      <RouterLink class="small" :to="{ name: 'schedules' }">
        {{ S15.railScheduleTitle }}<span v-if="scheduleStatus === 'ready'" class="muted"> · {{ schedules.length }}</span>
      </RouterLink>
      <RouterLink class="small" :to="{ name: 'plans' }">
        {{ S15.railPlansTitle }}<span v-if="planStatus === 'ready'" class="muted"> · {{ plans.length }}</span>
      </RouterLink>
    </div>
  </aside>
</template>
