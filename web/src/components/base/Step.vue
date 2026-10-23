<script setup lang="ts">
/**
 * `steps` 族的单项（02-actions-status.md §Steps；rb.css:247–256）。
 *
 * 三项结果：进行中 / 完成 / **失败**。失败项**不得**出完成勾
 * —— 所以失败时只渲染失败图标，没有「成功」图标路径可走。
 */
import { ICONS } from './icons'
import type { StepStatus } from '@/domain/chatMachine'

const props = defineProps<{ status: StepStatus; title: string; sub?: string }>()

const isFailed = (): boolean => props.status === 'failed'
const isRunning = (): boolean => props.status === 'running'
</script>

<template>
  <li class="step" :class="{ 'step--running': isRunning(), 'step--done': status === 'ok' || status === 'created' || status === 'existing' || status === 'empty', 'step--failed': isFailed() }">
    <span class="step__ico" aria-hidden="true">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">
        <template v-if="isFailed()"><path v-for="(d, i) in ICONS.circleX" :key="i" :d="d" /></template>
        <template v-else-if="isRunning()"><path v-for="(d, i) in ICONS.loader" :key="i" :d="d" /></template>
        <template v-else><path v-for="(d, i) in ICONS.check" :key="i" :d="d" /></template>
      </svg>
    </span>
    <span class="step__title">{{ title }}</span>
    <span v-if="sub" class="step__sub">{{ sub }}</span>
    <slot />
  </li>
</template>
