<template>
  <div class="w-full max-w-5xl space-y-6">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-2xl font-bold text-primary">Ops Dashboard</h1>
        <p class="text-content-muted text-sm">
          Open / new / pending / closed trend per department, sourced from Monday.com status-change
          webhooks. History only accumulates from the point each board's webhook was connected forward.
        </p>
        <router-link to="/ops-dashboard/boards" class="text-xs text-secondary hover:underline">
          Configure board mappings &rarr;
        </router-link>
      </div>

      <div class="flex items-center gap-2 text-sm">
        <div class="inline-flex rounded-lg border border-edge overflow-hidden">
          <button
            v-for="p in ['week', 'month']"
            :key="p"
            type="button"
            :class="[period === p ? 'bg-secondary text-secondary-accent' : 'text-content hover:bg-surface']"
            class="px-3 py-1.5 capitalize"
            @click="setPeriod(p)"
          >
            {{ p }}ly
          </button>
        </div>
        <select
          v-model.number="count"
          class="rounded border border-edge bg-page text-content px-2 py-1.5"
          @change="loadTrends"
        >
          <option v-for="c in countOptions" :key="c" :value="c">
            Last {{ c }} {{ period }}{{ c === 1 ? '' : 's' }}
          </option>
        </select>
      </div>
    </div>

    <p v-if="loading" class="text-content-muted">Loading&hellip;</p>
    <p v-else-if="error" class="text-red-500 text-sm">{{ error }}</p>
    <p v-else-if="departments.length === 0" class="text-content-muted text-sm">
      No department data yet &mdash; connect a board's webhook automation to start logging events.
    </p>

    <div v-else class="space-y-6">
      <div
        v-for="dept in departments"
        :key="dept"
        class="rounded-lg border border-edge bg-surface p-4 space-y-3"
      >
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold text-primary">{{ dept }}</h2>
          <div class="flex gap-4 text-sm text-content-muted">
            <span>Open: <span class="text-content font-medium">{{ latestOf(dept, 'open') }}</span></span>
            <span>Pending: <span class="text-content font-medium">{{ latestOf(dept, 'pending') }}</span></span>
          </div>
        </div>

        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <TrendSparkline
            v-for="metric in METRICS"
            :key="metric"
            :label="metric"
            :points="seriesFor(dept, metric)"
            :week-labels="periodLabelsFor(dept)"
            :mode="FLOW_METRICS.includes(metric) ? 'sum' : 'latest'"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import TrendSparkline from '../components/TrendSparkline.vue'

const METRICS = ['open', 'new', 'pending', 'closed']
const FLOW_METRICS = ['new', 'closed'] // summed across the selected range, not just the latest period
const COUNT_OPTIONS = { week: [4, 8, 12, 26], month: [3, 6, 12] }

const period = ref('week')
const count = ref(8)
const countOptions = ref(COUNT_OPTIONS.week)

const departments = ref([])
const trends = ref({}) // department -> period points array
const loading = ref(true)
const error = ref(null)

function seriesFor(dept, metric) {
  return (trends.value[dept] || []).map((p) => p[metric])
}

function periodLabelsFor(dept) {
  const fmt = period.value === 'month' ? { month: 'short', year: '2-digit' } : { month: 'short', day: 'numeric' }
  return (trends.value[dept] || []).map((p) => new Date(p.period_start).toLocaleDateString(undefined, fmt))
}

function latestOf(dept, metric) {
  const series = trends.value[dept] || []
  return series.length ? series[series.length - 1][metric] : 0
}

function setPeriod(p) {
  if (period.value === p) return
  period.value = p
  countOptions.value = COUNT_OPTIONS[p]
  count.value = COUNT_OPTIONS[p][1] ?? COUNT_OPTIONS[p][0]
  loadTrends()
}

async function loadTrends() {
  loading.value = true
  error.value = null
  try {
    await Promise.all(
      departments.value.map(async (dept) => {
        const r = await fetch(
          `/api/ops-dashboard/trend?department=${encodeURIComponent(dept)}&period=${period.value}&count=${count.value}`,
          { credentials: 'include' }
        )
        if (!r.ok) return
        const data = await r.json()
        trends.value[dept] = data.points
      })
    )
  } catch (e) {
    error.value = e.message || 'Failed to load ops dashboard data'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const res = await fetch('/api/ops-dashboard/current', { credentials: 'include' })
    if (!res.ok) throw new Error(res.statusText)
    const current = await res.json()
    departments.value = current.map((c) => c.department)
    await loadTrends()
  } catch (e) {
    error.value = e.message || 'Failed to load ops dashboard data'
    loading.value = false
  }
})
</script>
