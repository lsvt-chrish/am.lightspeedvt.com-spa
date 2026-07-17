<template>
  <div class="rounded border border-edge bg-page p-3">
    <div class="flex items-baseline justify-between mb-1">
      <span class="text-xs uppercase tracking-wide text-content-muted">{{ label }}</span>
      <span class="text-sm font-semibold text-content">{{ displayValue }}</span>
    </div>
    <div class="h-16 cursor-pointer">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
} from 'chart.js'

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip)

const props = defineProps({
  label: { type: String, required: true },
  points: { type: Array, required: true }, // array of numbers, oldest first
  weekLabels: { type: Array, default: () => [] }, // matching x-axis labels, oldest first
  // "latest": current-state snapshot (open/pending) -> show the most recent point.
  // "sum": flow metric (new/closed) -> show the total across the whole selected range.
  mode: { type: String, default: 'latest' },
})

const emit = defineEmits(['point-click'])

const displayValue = computed(() => {
  if (props.points.length === 0) return 0
  if (props.mode === 'sum') return props.points.reduce((a, b) => a + b, 0)
  return props.points[props.points.length - 1]
})

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

const chartData = computed(() => ({
  labels: props.weekLabels.length === props.points.length ? props.weekLabels : props.points.map((_, i) => i),
  datasets: [
    {
      data: props.points,
      borderColor: cssVar('--secondary-color') || '#f8aa17',
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 2,
      tension: 0.3,
    },
  ],
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  onClick(_evt, elements) {
    if (elements.length) emit('point-click', elements[0].index)
  },
  plugins: {
    legend: { display: false },
    tooltip: { enabled: true, intersect: false, mode: 'index' },
  },
  scales: {
    x: { display: false },
    y: { display: false, beginAtZero: true },
  },
}
</script>
