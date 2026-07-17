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

      <div
        class="inline-flex rounded-lg border border-edge overflow-hidden text-sm"
        title="Granularity of each chart data point: one dot per week, or one per calendar month. Independent of the From/To range below."
      >
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
    </div>

    <div class="rounded-lg border border-edge bg-surface p-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5 text-sm">
      <div title="Restrict the charts to one specific Monday.com board, instead of aggregating every board mapped to a department.">
        <label class="block text-xs text-content-muted mb-1">Board</label>
        <select v-model="selectedBoard" class="w-full rounded border border-edge bg-page text-content px-2 py-1.5" @change="onBoardChange">
          <option value="">All boards</option>
          <option v-for="b in boards" :key="b.board_id" :value="b.board_id">{{ b.name }}</option>
        </select>
      </div>
      <div title="Narrow to items currently sitting in one specific Monday.com group on the selected board (e.g. 'Awaiting Response'), regardless of which bucket it maps to. Pick a board first.">
        <label class="block text-xs text-content-muted mb-1">Group</label>
        <select v-model="selectedGroup" class="w-full rounded border border-edge bg-page text-content px-2 py-1.5" :disabled="!selectedBoard" @change="loadAll">
          <option value="">All groups</option>
          <option v-for="g in boardValues.groups" :key="g" :value="g">{{ g }}</option>
        </select>
      </div>
      <div title="Narrow to items whose most recent status change on the selected board was to this exact status label. Pick a board first.">
        <label class="block text-xs text-content-muted mb-1">Status</label>
        <select v-model="selectedStatus" class="w-full rounded border border-edge bg-page text-content px-2 py-1.5" :disabled="!selectedBoard" @change="loadAll">
          <option value="">All statuses</option>
          <option v-for="s in boardValues.statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
      <div title="Start of the date range to chart. Works together with the weekly/monthly toggle above, which sets how finely that range is broken into data points.">
        <label class="block text-xs text-content-muted mb-1">From</label>
        <input v-model="startDate" type="date" class="w-full rounded border border-edge bg-page text-content px-2 py-1.5" @change="loadAll" />
      </div>
      <div title="End of the date range to chart.">
        <label class="block text-xs text-content-muted mb-1">To</label>
        <input v-model="endDate" type="date" class="w-full rounded border border-edge bg-page text-content px-2 py-1.5" @change="loadAll" />
      </div>
    </div>

    <p v-if="loading" class="text-content-muted">Loading&hellip;</p>
    <p v-else-if="error" class="text-red-500 text-sm">{{ error }}</p>
    <p v-else-if="departments.length === 0" class="text-content-muted text-sm">
      No department data yet for this filter &mdash; connect a board's webhook automation, or widen the date range/filters.
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
            title="Click a point to see the items behind it"
            @point-click="onPointClick(dept, metric, $event)"
          />
        </div>

        <div
          v-if="openPanel && openPanel.dept === dept"
          class="rounded border border-edge bg-page p-3 text-sm space-y-2"
        >
          <div class="flex items-center justify-between">
            <span class="text-content-muted capitalize">{{ openPanel.metric }} &mdash; {{ openPanel.label }}</span>
            <button type="button" class="text-content-muted hover:text-content" @click="openPanel = null">&times;</button>
          </div>
          <p v-if="panelLoading" class="text-content-muted">Loading&hellip;</p>
          <p v-else-if="panelError" class="text-red-500">{{ panelError }}</p>
          <p v-else-if="panelItems.length === 0" class="text-content-muted">No items.</p>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-left">
              <thead class="text-content-muted text-xs uppercase">
                <tr>
                  <th class="pr-3 py-1">Item</th>
                  <th class="pr-3 py-1">Board</th>
                  <th class="pr-3 py-1">Group / Status</th>
                  <th class="pr-3 py-1">Updated</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="it in panelItems" :key="it.item_id" class="border-t border-edge">
                  <td class="pr-3 py-1">
                    <a :href="it.monday_url" target="_blank" rel="noopener" class="text-secondary hover:underline">
                      {{ it.item_name || it.item_id }}
                    </a>
                  </td>
                  <td class="pr-3 py-1 text-content-muted">{{ it.board_name || it.board_id }}</td>
                  <td class="pr-3 py-1 text-content-muted">{{ it.status || it.group_name || '—' }}</td>
                  <td class="pr-3 py-1 text-content-muted">{{ new Date(it.occurred_at).toLocaleDateString() }}</td>
                </tr>
              </tbody>
            </table>
          </div>
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

function isoDate(d) {
  return d.toISOString().slice(0, 10)
}

const period = ref('week')
const today = new Date()
const eightWeeksAgo = new Date(today.getTime() - 8 * 7 * 24 * 60 * 60 * 1000)
const startDate = ref(isoDate(eightWeeksAgo))
const endDate = ref(isoDate(today))

const boards = ref([])
const selectedBoard = ref('')
const selectedGroup = ref('')
const selectedStatus = ref('')
const boardValues = ref({ groups: [], statuses: [] })

const departments = ref([])
const trends = ref({}) // department -> period points array
const loading = ref(true)
const error = ref(null)

const openPanel = ref(null) // { dept, metric, index, label } | null
const panelItems = ref([])
const panelLoading = ref(false)
const panelError = ref(null)

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
  loadAll()
}

async function onBoardChange() {
  selectedGroup.value = ''
  selectedStatus.value = ''
  if (!selectedBoard.value) {
    boardValues.value = { groups: [], statuses: [] }
  } else {
    try {
      const r = await fetch(`/api/ops-dashboard/board-values?board_id=${encodeURIComponent(selectedBoard.value)}`, {
        credentials: 'include',
      })
      boardValues.value = r.ok ? await r.json() : { groups: [], statuses: [] }
    } catch {
      boardValues.value = { groups: [], statuses: [] }
    }
  }
  await loadAll()
}

function scopeParams() {
  const params = new URLSearchParams({ period: period.value, start: startDate.value, end: endDate.value })
  if (selectedBoard.value) params.set('board_id', selectedBoard.value)
  if (selectedGroup.value) params.set('group', selectedGroup.value)
  if (selectedStatus.value) params.set('status', selectedStatus.value)
  return params
}

async function loadAll() {
  loading.value = true
  error.value = null
  try {
    const currentParams = scopeParams()
    const res = await fetch(`/api/ops-dashboard/current?${currentParams}`, { credentials: 'include' })
    if (!res.ok) throw new Error(res.statusText)
    const current = await res.json()
    departments.value = current.map((c) => c.department)

    await Promise.all(
      departments.value.map(async (dept) => {
        const params = scopeParams()
        params.set('department', dept)
        const r = await fetch(`/api/ops-dashboard/trend?${params}`, { credentials: 'include' })
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

function onPointClick(dept, metric, index) {
  if (openPanel.value && openPanel.value.dept === dept && openPanel.value.metric === metric && openPanel.value.index === index) {
    openPanel.value = null
    return
  }
  const point = (trends.value[dept] || [])[index]
  if (!point) return
  openPanel.value = { dept, metric, index, label: periodLabelsFor(dept)[index] }
  loadPanelItems(dept, metric, point)
}

async function loadPanelItems(dept, metric, point) {
  panelLoading.value = true
  panelError.value = null
  panelItems.value = []
  try {
    const params = scopeParams()
    params.set('metric', metric)
    params.set('department', dept)
    params.set('period_start', point.period_start)
    params.set('period_end', point.period_end)
    const r = await fetch(`/api/ops-dashboard/items?${params}`, { credentials: 'include' })
    if (!r.ok) throw new Error(r.statusText)
    panelItems.value = await r.json()
  } catch (e) {
    panelError.value = e.message || 'Failed to load items'
  } finally {
    panelLoading.value = false
  }
}

onMounted(async () => {
  try {
    const r = await fetch('/api/monday/boards', { credentials: 'include' })
    boards.value = r.ok ? await r.json() : []
  } catch {
    boards.value = []
  }
  await loadAll()
})
</script>
