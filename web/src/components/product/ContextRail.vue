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
 * 只用 `.workspace__rail` / `.card` / `.stack` / `.small` / `.muted` 这些既有 class。
 */
import { computed } from 'vue'
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
</script>

<template>
  <aside class="workspace__rail">
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
  </aside>
</template>
