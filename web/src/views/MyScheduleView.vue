<script setup lang="ts">
/**
 * S07–S08 我的课表（§9.7–§9.8）。
 *
 * **硬验收点**：两种空状态必须并列且视觉可分，**绝不合并**成「暂无数据」：
 *   ① `items.length === 0 && error === null` ⇒ 成功的空（content-spec:122，「换个日期」）；
 *   ② `error !== null` ⇒ 服务异常（content-spec:124，「重试」），且**不得**把错误转成空列表。
 * 日期展示用 `schoolTimezone`（服务端给），不用浏览器时区。
 */
import { computed, onMounted, ref } from 'vue'
import Wrap from '@/components/base/Wrap.vue'
import Card from '@/components/base/Card.vue'
import Btn from '@/components/base/Btn.vue'
import Control from '@/components/base/Control.vue'
import Field from '@/components/base/Field.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ScheduleTable from '@/components/product/ScheduleTable.vue'
import { ICONS } from '@/components/base/icons'
import { S07, S08, S15 } from '@/domain/copy'
import { noCoursesText } from '@/domain/mapError'
import { formatDateWithWeekday, formatTimeRange, fill, weekdayZh } from '@/domain/format'
import { useSchedulesStore } from '@/stores/schedules'

const store = useSchedulesStore()

const dateInput = ref('')
const loaded = ref(false)

const currentDate = computed(() => store.fromDate ?? '')
const dateLabel = computed(() => (currentDate.value ? formatDateWithWeekday(currentDate.value) : ''))
const emptyTitle = computed(() => noCoursesText(currentDate.value, weekdayZh(currentDate.value)))
const footer = computed(() => fill(S07.footerTemplate, { timezone: store.schoolTimezone ?? '' }))

/**
 * 只读信息层（§6.4）：全部来自**当前已加载的那一天**，不新增接口、不做周范围查询。
 * 「下一节课」= 开始时间晚于当前时刻的第一节；没有就渲染破折号（不写自造句）。
 */
const nowHHMM = computed(() => {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

const nextClass = computed(() => store.items.find((s) => s.start_time > nowHHMM.value) ?? null)

const dayEnd = computed(() =>
  store.items.reduce<string | null>((acc, s) => (acc === null || s.end_time > acc ? s.end_time : acc), null),
)

async function load(date?: string) {
  try {
    if (date) await store.fetchMine({ from_date: date, to_date: date })
    else await store.fetchMine()
  } catch {
    /* 错误已记在 store.error，界面用 S08 ② 渲染；这里不吞成空列表。 */
  } finally {
    loaded.value = true
    dateInput.value = store.fromDate ?? ''
  }
}

function shiftDay(delta: number) {
  const base = currentDate.value
  if (!base) return
  const t = Date.UTC(+base.slice(0, 4), +base.slice(5, 7) - 1, +base.slice(8, 10)) + delta * 86_400_000
  const d = new Date(t)
  const iso = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`
  void load(iso)
}

// 「今天」由服务端定义（学校时区当日）—— 不传日期即当日。
function goToday() {
  void load()
}

onMounted(() => void load())
</script>

<template>
  <Wrap>
    <div class="split">
      <div class="stack">
        <!-- 统计条：4 卡，全部来自当前已加载数据（§6.4） -->
        <div class="stat-grid">
          <div class="stat">
            <span class="stat__value">{{ store.items.length }}</span>
            <span class="stat__label">{{ S15.statTodayCourses }}</span>
          </div>
          <div class="stat">
            <span class="stat__value">{{ nextClass ? nextClass.start_time : '—' }}</span>
            <span class="stat__label">{{ S15.statNextClass }}</span>
          </div>
          <div class="stat">
            <span class="stat__value">{{ dayEnd ?? '—' }}</span>
            <span class="stat__label">{{ S15.statDayEnd }}</span>
          </div>
          <div class="stat">
            <span class="stat__value">&le; 31 天</span>
            <span class="stat__label">{{ S15.statRange }}</span>
          </div>
        </div>

        <Card :title="S07.title">
      <div class="row">
        <Btn size="sm" :aria-label="S07.prevDay" @click="shiftDay(-1)">
          <template #icon>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
              <path v-for="(d, i) in ICONS.chevronLeft" :key="i" :d="d" />
            </svg>
          </template>
        </Btn>
        <span class="field__label" aria-live="polite">{{ dateLabel }}</span>
        <Btn size="sm" :aria-label="S07.nextDay" @click="shiftDay(1)">
          <template #icon>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
              <path v-for="(d, i) in ICONS.chevronRight" :key="i" :d="d" />
            </svg>
          </template>
        </Btn>
        <Btn size="sm" @click="goToday">{{ S07.today }}</Btn>
        <span class="small muted">{{ S07.rangeLimit }}</span>
      </div>

      <Field :label="S15.dateField" for-id="schedule-date">
        <Control id="schedule-date" v-model="dateInput" type="date" @blur="load(dateInput || undefined)" />
      </Field>

      <ScheduleTable v-if="store.items.length > 0" :items="store.items" :caption="S07.title" />

      <!-- ① 成功的空：中性，**不得**使用错误色。 -->
      <EmptyState v-else-if="store.isEmpty" variant="empty" icon="calendar" :title="emptyTitle">
        <template #actions>
          <Btn size="sm" @click="goToday">{{ S08.changeDate }}</Btn>
        </template>
      </EmptyState>

      <!-- ② 服务异常：错误语义 + role="alert"，与 ① 明显不同。 -->
      <EmptyState v-else-if="store.hasError" variant="error" icon="triangleAlert" :title="S08.fetchFailed">
        <template #actions>
          <Btn size="sm" @click="load(currentDate || undefined)">{{ S08.retry }}</Btn>
        </template>
      </EmptyState>

      <p v-else-if="!loaded" class="muted small">{{ S07.title }}</p>
    </Card>
      </div>

      <aside class="split__rail">
        <!-- 时间轴只渲染已加载日；无课/错误时不渲染（§6.4 裁决） -->
        <Card v-if="store.items.length > 0" :title="S15.timelineToday">
          <div class="timeline">
            <div v-for="s in store.items" :key="s.id" class="timeline__item">
              <span class="timeline__time">{{ s.start_time }}</span>
              <div class="timeline__box">
                <b>{{ s.course_name }}</b>
                <div class="small muted">
                  {{ formatTimeRange(s.start_time, s.end_time) }}<span v-if="s.location"> · {{ s.location }}</span>
                </div>
              </div>
            </div>
          </div>
          <p class="small muted">{{ S15.timelineEnd }}</p>
        </Card>

        <Card :title="S15.scheduleNoteTitle">
          <p class="small muted">{{ footer }}</p>
          <p class="small muted">{{ S07.rangeLimit }}</p>
        </Card>
      </aside>
    </div>
  </Wrap>
</template>
