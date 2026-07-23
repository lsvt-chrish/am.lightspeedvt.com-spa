<template>
  <div class="osd-wrap">
    <div class="osd-header">
      <div class="osd-header-text">
        <p class="osd-eyebrow">Ops pulse</p>
        <h1 class="osd-h1">Pipeline volume, by department</h1>
      </div>
    </div>

    <div class="osd-body">
      <p class="osd-sub">
        Open / new / pending / closed trend per department, sourced from Monday.com status-change
        webhooks. History only accumulates from the point each board's webhook was connected forward.
        <router-link to="/ops-dashboard/boards" class="osd-config-link">Configure board mappings &rarr;</router-link>
      </p>

      <p class="osd-section-title">Live metrics</p>
      <p class="osd-notice">
        Real-time counts across all departments &mdash; refreshes automatically every 15 seconds, no
        page reload needed. Scoped by the board/group/status filters below, if set.
      </p>
      <LiveMetricsBar :board-id="selectedBoard" :group="selectedGroup" :status="selectedStatus" />

      <p class="osd-section-title">Trend analysis</p>
      <p class="osd-sub">
        Open / new / pending / closed trend per department, sourced from Monday.com status-change
        webhooks. History only accumulates from the point each board's webhook was connected forward.
        <router-link to="/ops-dashboard/boards" class="osd-config-link">Configure board mappings &rarr;</router-link>
      </p>

      <div class="osd-form">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <p class="osd-section-title" style="margin:0;">Filters</p>
          <div style="display:flex; gap:8px; flex-wrap:wrap;">
            <div
              class="osd-view-toggle"
              title="Compare the selected range against a comparable prior period, overlaid as a dashed line on each chart. Also sets each chart's granularity: day-over-day, week-over-week, or month-over-month."
            >
              <button
                v-for="c in COMPARE_OPTIONS"
                :key="c.value"
                type="button"
                class="osd-view-btn"
                :class="{ on: compareMode === c.value }"
                @click="setCompareMode(c.value)"
              >
                {{ c.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="osd-form-grid">
          <div class="osd-field" title="Restrict the charts to one specific Monday.com board, instead of aggregating every board mapped to a department.">
            <label>Board</label>
            <select v-model="selectedBoard" @change="onBoardChange">
              <option value="">All boards</option>
              <option v-for="b in boards" :key="b.board_id" :value="b.board_id">{{ b.name }}</option>
            </select>
          </div>
          <div class="osd-field" title="Narrow to items currently sitting in one specific Monday.com group on the selected board (e.g. 'Awaiting Response'), regardless of which bucket it maps to. Pick a board first.">
            <label>Group</label>
            <select v-model="selectedGroup" :disabled="!selectedBoard" @change="loadAll">
              <option value="">All groups</option>
              <option v-for="g in boardValues.groups" :key="g" :value="g">{{ g }}</option>
            </select>
          </div>
          <div class="osd-field" title="Narrow to items whose most recent status change on the selected board was to this exact status label. Pick a board first.">
            <label>Status</label>
            <select v-model="selectedStatus" :disabled="!selectedBoard" @change="loadAll">
              <option value="">All statuses</option>
              <option v-for="s in boardValues.statuses" :key="s" :value="s">{{ s }}</option>
            </select>
          </div>
          <div class="osd-field" title="Start of the date range to chart. Works together with the weekly/monthly toggle above, which sets how finely that range is broken into data points.">
            <label>From</label>
            <input v-model="startDate" type="date" @change="loadAll" />
          </div>
          <div class="osd-field" title="End of the date range to chart.">
            <label>To</label>
            <input v-model="endDate" type="date" @change="loadAll" />
          </div>
        </div>
      </div>

      <p v-if="loading" class="osd-sub">Loading&hellip;</p>
      <p v-else-if="error" class="osd-sub" style="color:var(--red-dark);">{{ error }}</p>
      <p v-else-if="departments.length === 0" class="osd-empty">
        No department data yet for this filter &mdash; connect a board's webhook automation, or widen the date range/filters.
      </p>

      <template v-else>
        <div class="osd-chip-row">
          <span
            v-for="dept in departments"
            :key="dept"
            class="osd-chip"
            :title="`Open: ${latestOf(dept, 'open')} &middot; Pending: ${latestOf(dept, 'pending')}`"
          >
            <span class="osd-chip-dot" :class="statusFor(dept)"></span>
            {{ dept }}
            <span class="osd-chip-note">{{ latestOf(dept, 'open') }} open &middot; {{ latestOf(dept, 'pending') }} pending</span>
          </span>
        </div>

        <div class="osd-weekbar">
          <span class="lbl">Viewing</span>
          <button class="osd-weeknav" type="button" title="Shift range back" @click="shiftRange(-1)">&larr;</button>
          <span style="font-family:var(--font-heading); font-size:13.5px; font-weight:700; color:var(--dark-blue); padding:2px 4px;">
            {{ startDate }} &rarr; {{ endDate }}
          </span>
          <button class="osd-weeknav" type="button" title="Shift range forward" @click="shiftRange(1)">&rarr;</button>
        </div>

        <div class="osd-dept-panels">
        <div
          v-for="dept in departments"
          :key="dept"
          class="osd-detail-panel"
        >
          <div class="osd-dept-head">
            <p class="osd-detail-title" style="margin:0;">{{ dept }}</p>
            <div class="flex gap-2">
              <span class="osd-badge" :class="statusFor(dept)">Open {{ latestOf(dept, 'open') }}</span>
              <span class="osd-badge" :class="statusFor(dept)">Pending {{ latestOf(dept, 'pending') }}</span>
            </div>
          </div>

          <div class="osd-spark-grid" style="margin-top:12px;">
            <div v-for="metric in METRICS" :key="metric" class="osd-spark-card">
              <TrendSparkline
                :label="metric"
                :points="seriesFor(dept, metric)"
                :week-labels="periodLabelsFor(dept)"
                :mode="FLOW_METRICS.includes(metric) ? 'sum' : 'latest'"
                :compare-points="previousSeriesFor(dept, metric)"
                title="Click a point to see the items behind it"
                @point-click="onPointClick(dept, metric, $event)"
              />
            </div>
          </div>

          <div
            v-if="openPanel && openPanel.dept === dept"
            class="osd-detail-tile"
            style="margin-top:12px; background:#fff;"
          >
            <div class="flex items-center justify-between">
              <span class="osd-detail-label capitalize" style="margin:0;">{{ openPanel.metric }} &mdash; {{ openPanel.label }}</span>
              <button type="button" class="osd-weeknav" style="width:20px;height:20px;font-size:12px;" @click="openPanel = null">&times;</button>
            </div>
            <p v-if="panelLoading" class="osd-sub" style="margin:8px 0 0;">Loading&hellip;</p>
            <p v-else-if="panelError" class="osd-sub" style="margin:8px 0 0; color:var(--red-dark);">{{ panelError }}</p>
            <p v-else-if="panelItems.length === 0" class="osd-sub" style="margin:8px 0 0;">No items.</p>
            <div v-else class="overflow-x-auto" style="margin-top:8px;">
              <table class="w-full text-left" style="font-size:12.5px;">
                <thead style="color:var(--darker-grey); text-transform:uppercase; font-size:10.5px;">
                  <tr>
                    <th class="pr-3 py-1">Item</th>
                    <th class="pr-3 py-1">Board</th>
                    <th class="pr-3 py-1">Group / Status</th>
                    <th class="pr-3 py-1">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="it in panelItems" :key="it.item_id" style="border-top:1px solid var(--border);">
                    <td class="pr-3 py-1">
                      <a :href="it.monday_url" target="_blank" rel="noopener" style="color:var(--light-blue);">
                        {{ it.item_name || it.item_id }}
                      </a>
                    </td>
                    <td class="pr-3 py-1" style="color:var(--darker-grey);">{{ it.board_name || it.board_id }}</td>
                    <td class="pr-3 py-1" style="color:var(--darker-grey);">{{ it.status || it.group_name || '—' }}</td>
                    <td class="pr-3 py-1" style="color:var(--darker-grey);">{{ new Date(it.occurred_at).toLocaleDateString() }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import TrendSparkline from '../components/TrendSparkline.vue'
import LiveMetricsBar from '../components/LiveMetricsBar.vue'

const METRICS = ['new', 'open', 'pending', 'closed']
const FLOW_METRICS = ['new', 'closed'] // summed across the selected range, not just the latest period

const COMPARE_OPTIONS = [
  { value: '', label: 'No compare' },
  { value: 'previous_day', label: 'Prev day' },
  { value: 'previous_week', label: 'Prev week' },
  { value: 'previous_month', label: 'Prev month' },
]
const compareMode = ref('')

// Chart granularity follows the compare choice: day-over-day, week-over-week,
// month-over-month. With no compare selected, default to weekly.
const PERIOD_BY_COMPARE = { '': 'week', previous_day: 'day', previous_week: 'week', previous_month: 'month' }
const period = computed(() => PERIOD_BY_COMPARE[compareMode.value])

function setCompareMode(value) {
  if (compareMode.value === value) return
  compareMode.value = value
  loadAll()
}

function statusFor(dept) {
  const open = latestOf(dept, 'open')
  const pending = latestOf(dept, 'pending')
  const backlog = open + pending
  if (backlog > 100) return 'danger'
  if (backlog > 50) return 'busy'
  if (backlog > 20) return 'slow'
  return 'normal'
}

function shiftRange(direction) {
  const start = new Date(startDate.value)
  const end = new Date(endDate.value)
  const spanMs = end.getTime() - start.getTime()
  start.setTime(start.getTime() + direction * spanMs)
  end.setTime(end.getTime() + direction * spanMs)
  startDate.value = isoDate(start)
  endDate.value = isoDate(end)
  loadAll()
}

function isoDate(d) {
  return d.toISOString().slice(0, 10)
}

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
const previousTrends = ref({}) // department -> prior-period points array, when compareMode is set
const loading = ref(true)
const error = ref(null)

const openPanel = ref(null) // { dept, metric, index, label } | null
const panelItems = ref([])
const panelLoading = ref(false)
const panelError = ref(null)

function seriesFor(dept, metric) {
  return (trends.value[dept] || []).map((p) => p[metric])
}

function previousSeriesFor(dept, metric) {
  const previous = previousTrends.value[dept]
  return previous ? previous.map((p) => p[metric]) : null
}

function periodLabelsFor(dept) {
  const fmt = period.value === 'month' ? { month: 'short', year: '2-digit' } : { month: 'short', day: 'numeric' }
  return (trends.value[dept] || []).map((p) => new Date(p.period_start).toLocaleDateString(undefined, fmt))
}

function latestOf(dept, metric) {
  const series = trends.value[dept] || []
  return series.length ? series[series.length - 1][metric] : 0
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
  if (compareMode.value) params.set('compare', compareMode.value)
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
        previousTrends.value[dept] = data.previous_points || null
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

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Public+Sans:wght@400;500&display=swap');

.osd-wrap {
  --dark: #212121; --light: #F7FAFD; --light-blue: #2098D0; --light-blue-accent: #EFF6FF;
  --dark-blue: #12355A; --red: #EF4444; --red-light: #FEF2F2; --red-dark: #7F1D1D;
  --green: #22C55E; --green-light: #DCFCE7; --green-dark: #166534;
  --warning: #F59E0B; --warning-light: #FFFBEB; --warning-dark: #92400E;
  --mid-grey: #E8E8E8; --light-grey: #FAFAFA; --darker-grey: #5F5F5F; --border: #E4E5E9;
  --font-heading: 'Montserrat', Helvetica, Arial, sans-serif;
  --font-body: 'Public Sans', Helvetica, Arial, sans-serif;
  background: var(--light-grey);
  color: var(--dark);
  font-family: var(--font-body);
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
}
.osd-header { background: var(--dark-blue); padding: 22px 32px; }
.osd-eyebrow { font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: #BFDCEE; margin: 0 0 2px; }
.osd-h1 { font-family: var(--font-heading); font-size: 19px; font-weight: 700; color: var(--light); margin: 0; }
.osd-body { padding: 24px 32px 40px; }
.osd-sub { font-size: 13px; color: var(--darker-grey); margin: 0 0 16px; }
.osd-config-link { color: var(--light-blue); font-size: 12px; margin-left: 8px; }
.osd-config-link:hover { text-decoration: underline; }
.osd-notice {
  background: var(--light-blue-accent); border: 1px solid #BFE0F0; color: var(--dark-blue);
  font-size: 12.5px; border-radius: 8px; padding: 10px 14px; margin: 0 0 20px;
}
.osd-section-title { font-family: var(--font-heading); font-size: 13px; font-weight: 700; margin: 0 0 12px; color: var(--dark); }
.osd-form { background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; margin-bottom: 20px; }
.osd-form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-top: 12px; }
.osd-field label { display: flex; align-items: center; font-size: 11px; color: var(--darker-grey); margin-bottom: 4px; }
.osd-field select, .osd-field input {
  width: 100%; background: var(--light-grey); border: 1px solid var(--mid-grey); color: var(--dark);
  border-radius: 6px; padding: 7px 8px; font-size: 13px; font-family: var(--font-body);
}
.osd-field select:focus, .osd-field input:focus { outline: none; border-color: var(--light-blue); }
.osd-view-toggle { display: flex; gap: 4px; background: var(--light-grey); border: 1px solid var(--border); border-radius: 9999px; padding: 3px; flex: 0 0 auto; }
.osd-view-btn { font-family: var(--font-body); font-size: 12px; font-weight: 500; padding: 5px 14px; border-radius: 9999px; border: none; background: transparent; color: var(--darker-grey); cursor: pointer; }
.osd-view-btn.on { background: var(--dark-blue); color: var(--light); }
.osd-empty { text-align: center; padding: 30px; color: var(--darker-grey); font-size: 13px; }
.osd-chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 20px; }
.osd-chip {
  display: inline-flex; align-items: center; gap: 7px; background: #fff; border: 1px solid var(--border);
  border-radius: 9999px; padding: 7px 14px 7px 10px; font-size: 12.5px; color: var(--dark);
}
.osd-chip-dot { width: 9px; height: 9px; border-radius: 50%; flex: 0 0 auto; background: var(--darker-grey); }
.osd-chip-dot.busy { background: var(--warning); }
.osd-chip-dot.danger { background: var(--red); }
.osd-chip-dot.slow { background: var(--light-blue); }
.osd-chip-dot.normal { background: var(--green); }
.osd-chip-note { color: var(--darker-grey); font-size: 11.5px; }
.osd-weekbar {
  display: flex; align-items: center; gap: 10px; margin: 0 0 20px; padding: 8px 10px 8px 16px;
  background: #fff; border: 1px solid var(--border); border-radius: 9999px; width: fit-content;
}
.osd-weekbar .lbl { font-size: 11px; color: var(--darker-grey); text-transform: uppercase; letter-spacing: .04em; margin-right: 2px; }
.osd-weeknav {
  width: 28px; height: 28px; flex: 0 0 auto; border-radius: 50%; border: 1px solid var(--mid-grey);
  background: #fff; color: var(--dark-blue); font-size: 14px; line-height: 1; cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-family: var(--font-body);
}
.osd-weeknav:hover { background: var(--light-blue-accent); border-color: var(--light-blue); }
.osd-dept-panels { display: flex; flex-direction: column; gap: 16px; }
.osd-detail-panel { background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; }
.osd-dept-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.osd-detail-title { font-family: var(--font-heading); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: var(--dark-blue); }
.osd-detail-label { font-size: 11.5px; color: var(--darker-grey); }
.osd-badge {
  display: inline-block; font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: .04em;
  padding: 3px 10px; border-radius: 20px;
}
.osd-badge.busy { background: var(--warning-light); color: var(--warning-dark); }
.osd-badge.slow { background: var(--light-blue-accent); color: var(--light-blue); }
.osd-badge.normal { background: var(--light-grey); color: var(--darker-grey); border: 1px solid var(--mid-grey); }
.osd-badge.danger { background: var(--red-light); color: var(--red-dark); }
.osd-spark-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.osd-spark-card :deep(.border-edge) { border-color: var(--border) !important; border-radius: 10px !important; }
.osd-spark-card :deep(.bg-page) { background: var(--light-grey) !important; }
.osd-detail-tile { background: var(--light-grey); border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px; }
</style>
