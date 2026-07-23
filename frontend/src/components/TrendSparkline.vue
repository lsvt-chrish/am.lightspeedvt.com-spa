<template>
  <div class="rounded border border-edge bg-page p-3">
    <div class="flex items-baseline justify-between mb-1">
      <span class="text-xs uppercase tracking-wide text-content-muted">{{ label }}</span>
      <span class="flex items-baseline gap-2">
        <span class="text-sm font-semibold text-content">{{ displayValue }}</span>
        <span
          v-if="deltaPct !== null"
          class="text-xs font-semibold"
          :class="deltaPct > 0 ? 'text-green-600' : deltaPct < 0 ? 'text-red-500' : 'text-content-muted'"
        >
          {{ deltaPct > 0 ? '+' : '' }}{{ deltaPct }}%
        </span>
      </span>
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
  // Optional prior-period series (same length/mode as `points`), overlaid as a dashed line.
  comparePoints: { type: Array, default: null },
})

const emit = defineEmits(['point-click'])

function aggregate(points, mode) {
  if (!points || points.length === 0) return 0
  if (mode === 'sum') return points.reduce((a, b) => a + b, 0)
  return points[points.length - 1]
}

const displayValue = computed(() => aggregate(props.points, props.mode))

const deltaPct = computed(() => {
  if (!props.comparePoints || props.comparePoints.length === 0) return null
  const previous = aggregate(props.comparePoints, props.mode)
  if (previous === 0) return null
  return Math.round(((displayValue.value - previous) / previous) * 100)
})

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

const chartData = computed(() => {
  const datasets = [
    {
      data: props.points,
      borderColor: cssVar('--secondary-color') || '#f8aa17',
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 2,
      pointHitRadius: 12,
      tension: 0.3,
    },
  ]
  if (props.comparePoints) {
    datasets.push({
      data: props.comparePoints,
      borderColor: '#9CA3AF',
      backgroundColor: 'transparent',
      borderWidth: 2,
      borderDash: [4, 4],
      pointRadius: 0,
      tension: 0.3,
    })
  }
  return {
    labels: props.weekLabels.length === props.points.length ? props.weekLabels : props.points.map((_, i) => i),
    datasets,
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  // Match click hit-testing to the tooltip's forgiving "nearest column" behavior below
  // (default click detection requires landing exactly on the tiny 2px point, which the
  // tooltip box visually sitting over the point makes practically impossible to hit).
  interaction: { mode: 'index', intersect: false },
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
