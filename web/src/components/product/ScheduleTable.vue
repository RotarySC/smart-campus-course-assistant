<script setup lang="ts">
/**
 * `ScheduleTable`（组合件，CONTRACT §3.2 点名）。
 *
 * 只负责把 `schedules` store 的数据喂给 `DataTable`：
 * 每行 `<td data-label>` 必须与列名对应；**按开始时间升序**用服务端顺序（SRS FR-SCH-001）。
 * 空态**不在这里**判断 —— 两种空态（成功的空 / 服务异常）互斥，由视图用 `EmptyState` 分别渲染。
 */
import { computed } from 'vue'
import DataTable from '@/components/base/DataTable.vue'
import { S07 } from '@/domain/copy'
import { formatTimeRange } from '@/domain/format'
import type { Schedule } from '@/api/types'

const props = defineProps<{ items: Schedule[]; caption: string }>()

const columns = [
  { key: 'time', label: S07.colTime, num: true },
  { key: 'course', label: S07.colCourse },
  { key: 'location', label: S07.colLocation },
]

const rows = computed(() =>
  props.items.map((s) => ({
    time: formatTimeRange(s.start_time, s.end_time),
    course: s.course_name,
    location: s.location ?? '',
  })),
)
</script>

<template>
  <DataTable :caption="caption" :columns="columns" :rows="rows" />
</template>
