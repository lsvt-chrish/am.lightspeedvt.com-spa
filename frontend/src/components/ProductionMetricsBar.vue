<template>
  <div class="pmb-wrap">
    <div class="pmb-head">
      <div class="pmb-head-text">
        <span>{{ asOfLabel }}</span>
      </div>
      <button type="button" class="pmb-refresh" :disabled="refreshing" @click="onRefreshClick">
        {{ refreshing ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>

    <p v-if="error" class="pmb-error">{{ error }}</p>

    <template v-else>
      <div class="pmb-strip">
        <button
          v-for="m in TILES"
          :key="m.key"
          type="button"
          class="pmb-tile"
          :class="[m.key, { open: openTile === m.key }]"
          @click="onTileClick(m.key)"
        >
          <span class="pmb-info-wrap" @click.stop>
            <span class="pmb-info" tabindex="0" role="button" :aria-label="`About ${m.label}`">i</span>
            <span class="pmb-tooltip">{{ m.tooltip }}</span>
          </span>
          <div class="pmb-label">{{ m.label }}</div>
          <div class="pmb-val">{{ formatHours(metrics[m.key]) }}</div>
        </button>
        <div class="pmb-tile hours-open" :class="{ negative: (metrics.hoursOpen || 0) < 0 }">
          <span class="pmb-info-wrap">
            <span class="pmb-info" tabindex="0" role="button" aria-label="About Hours Open">i</span>
            <span class="pmb-tooltip">{{ HOURS_OPEN_TOOLTIP }}</span>
          </span>
          <div class="pmb-label">Hours Open</div>
          <div class="pmb-val">{{ formatHours(metrics.hoursOpen) }}</div>
        </div>
      </div>

      <div v-if="openTile" class="pmb-detail">
        <div class="pmb-detail-head">
          <span class="pmb-detail-title">{{ tileLabel(openTile) }} &mdash; current tickets</span>
          <div class="pmb-detail-actions">
            <a v-if="boardUrl" :href="boardUrl" target="_blank" rel="noopener" class="pmb-board-link">
              View board in Monday &rarr;
            </a>
            <button type="button" class="pmb-close" @click="openTile = null">&times;</button>
          </div>
        </div>

        <p v-if="detailLoading" class="pmb-sub">Loading&hellip;</p>
        <p v-else-if="detailError" class="pmb-sub" style="color:var(--red-dark, #7F1D1D);">{{ detailError }}</p>
        <p v-else-if="currentItems.length === 0" class="pmb-sub">No tickets currently in this bucket.</p>
        <div v-else class="pmb-table-wrap">
          <table class="pmb-table">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Status</th>
                <th>Hours</th>
                <th>Assigned</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in currentItems" :key="it.item_id">
                <td>
                  <a :href="it.monday_url" target="_blank" rel="noopener" class="pmb-item-link">
                    {{ it.name || it.item_id }}
                  </a>
                </td>
                <td>{{ it.status || '—' }}</td>
                <td>{{ formatHours(it.hours) }}</td>
                <td>{{ it.assigned_producer || '—' }}</td>
                <td>{{ it.updated_at ? new Date(it.updated_at).toLocaleDateString() : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

// Definitions per docs/monday-api-integration-plan.md ("Metric Definitions").
// detailKey maps each tile to its bucket name in the API's ?detail=true response.
const TILES = [
  {
    key: 'upNextHours',
    detailKey: 'upNext',
    label: 'Up Next',
    tooltip: 'Approved hours queued and ready to render. Monday status: Assigned. Click to see current tickets.',
  },
  {
    key: 'pipelineHours',
    detailKey: 'pipeline',
    label: 'Pipeline',
    tooltip:
      'Hours tied to samples already prepped and sent to the client, awaiting approval. Monday status: Pending Approval. Shown here as the full hours; only counted at 50% toward Hours Open. Click to see current tickets.',
  },
  {
    key: 'inProgressHours',
    detailKey: 'inProgress',
    label: 'In Progress',
    tooltip:
      'Hours of render work currently being actively worked on. Monday statuses: Render In Progress, Revisions In Progress, Sample In Progress. Click to see current tickets.',
  },
]

const HOURS_OPEN_TOOLTIP =
  'Remaining production capacity: Dynamic Goal − In Progress − Up Next − (Pipeline × 50%). Can go negative when production is overcommitted. Derived from the other three metrics -- no ticket list of its own.'

const POLL_MS = 15 * 60 * 1000 // matches the 15-min scheduled backend refresh

const metrics = ref({})
const detail = ref({}) // upNext/pipeline/inProgress -> { hours, items }
const boardUrl = ref(null)
const asOf = ref(null)
const error = ref(null)
const refreshing = ref(false)
const openTile = ref(null) // TILES[].key, or null
const detailLoading = ref(false)
const detailError = ref(null)
let intervalId = null

const asOfLabel = computed(() =>
  asOf.value ? `As of ${asOf.value.toLocaleTimeString()}` : ''
)

const currentItems = computed(() => {
  const tile = TILES.find((t) => t.key === openTile.value)
  if (!tile) return []
  return detail.value[tile.detailKey]?.items || []
})

function tileLabel(key) {
  return TILES.find((t) => t.key === key)?.label || key
}

function formatHours(v) {
  if (v === undefined || v === null) return '—'
  // Round to 2 decimals only to clear floating-point noise (e.g. 15.750000000000002),
  // not to simplify the displayed value -- then drop any trailing zeros so "15.75"
  // shows as-is while "3" or "3.5" don't grow spurious decimals.
  const rounded = Math.round(v * 100) / 100
  return `${rounded}h`
}

async function fetchDashboard(withDetail = false) {
  try {
    const url = withDetail ? '/api/production/dashboard?detail=true' : '/api/production/dashboard'
    const r = await fetch(url, { credentials: 'include' })
    if (!r.ok) {
      error.value = r.status === 404 ? 'No production data yet — click Refresh to pull it.' : r.statusText
      return
    }
    const data = await r.json()
    metrics.value = data.metrics
    boardUrl.value = data.boardUrl || null
    asOf.value = new Date(data.generatedAt)
    error.value = null
    if (withDetail) detail.value = data.detail || {}
  } catch (e) {
    error.value = e.message || 'Failed to load production dashboard data'
  }
}

async function onTileClick(key) {
  if (openTile.value === key) {
    openTile.value = null
    return
  }
  openTile.value = key
  detailError.value = null
  detailLoading.value = true
  try {
    await fetchDashboard(true)
  } catch (e) {
    detailError.value = e.message || 'Failed to load tickets'
  } finally {
    detailLoading.value = false
  }
}

async function onRefreshClick() {
  refreshing.value = true
  try {
    const r = await fetch('/api/monday/production/refresh', { method: 'POST', credentials: 'include' })
    if (!r.ok) throw new Error(r.statusText)
    await fetchDashboard(!!openTile.value)
  } catch (e) {
    error.value = e.message || 'Refresh failed'
  } finally {
    refreshing.value = false
  }
}

onMounted(() => {
  fetchDashboard()
  intervalId = setInterval(() => fetchDashboard(!!openTile.value), POLL_MS)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})
</script>

<style scoped>
.pmb-wrap { margin: 0 0 24px; }
.pmb-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.pmb-head-text { font-size: 12px; color: var(--darker-grey, #5F5F5F); }
.pmb-refresh {
  font-family: var(--font-body); font-size: 12.5px; font-weight: 500; color: #fff;
  background: var(--dark-blue, #12355A); border: none; border-radius: 8px; padding: 6px 14px; cursor: pointer;
}
.pmb-refresh:hover:not(:disabled) { background: var(--light-blue, #2098D0); }
.pmb-refresh:disabled { opacity: .6; cursor: default; }
.pmb-error, .pmb-sub { font-size: 13px; color: var(--darker-grey, #5F5F5F); margin: 0; }
.pmb-error { color: var(--red-dark, #7F1D1D); }
.pmb-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; }
.pmb-tile {
  position: relative; background: #fff; border: 1px solid var(--border, #E4E5E9);
  border-left: 4px solid var(--light-blue, #2098D0);
  border-radius: 12px; padding: 16px 16px 14px; box-shadow: 0 1px 3px rgba(18, 53, 90, .06);
  text-align: left; font-family: inherit; width: 100%;
}
.pmb-info-wrap { position: absolute; top: 10px; right: 10px; }
.pmb-info {
  width: 16px; height: 16px; border-radius: 50%;
  background: var(--light-grey, #FAFAFA); border: 1px solid var(--mid-grey, #E8E8E8);
  color: var(--darker-grey, #5F5F5F); font-family: var(--font-body); font-size: 10px; font-style: normal;
  font-weight: 700; line-height: 1; display: flex; align-items: center; justify-content: center; cursor: help;
  outline: none;
}
.pmb-info:hover, .pmb-info:focus-visible {
  background: var(--light-blue-accent, #EFF6FF); border-color: var(--light-blue, #2098D0); color: var(--light-blue, #2098D0);
}

/* Chat-bubble tooltip: a rounded card with a small tail pointing back at the info icon. Opens upward, above the icon. */
.pmb-tooltip {
  position: absolute; bottom: 24px; right: -6px; z-index: 20; width: 220px;
  background: var(--dark-blue, #12355A); color: #fff;
  font-family: var(--font-body); font-size: 11.5px; font-weight: 400; line-height: 1.45;
  text-transform: none; letter-spacing: normal; text-align: left;
  padding: 10px 12px; border-radius: 12px; box-shadow: 0 8px 20px rgba(18, 53, 90, .25);
  opacity: 0; visibility: hidden; transform: translateY(4px);
  transition: opacity .12s ease, transform .12s ease;
  pointer-events: none;
}
.pmb-tooltip::before {
  content: ''; position: absolute; bottom: -4px; right: 14px; width: 10px; height: 10px;
  background: var(--dark-blue, #12355A); border-radius: 2px; transform: rotate(45deg);
}
.pmb-info-wrap:hover .pmb-tooltip, .pmb-info:focus-visible + .pmb-tooltip {
  opacity: 1; visibility: visible; transform: translateY(0);
}
button.pmb-tile { cursor: pointer; }
button.pmb-tile:hover { border-color: var(--light-blue, #2098D0); }
button.pmb-tile.open { box-shadow: 0 0 0 2px var(--light-blue, #2098D0) inset; }
.pmb-tile.upNextHours { border-left-color: var(--light-blue, #2098D0); }
.pmb-tile.pipelineHours { border-left-color: var(--warning, #F59E0B); }
.pmb-tile.inProgressHours { border-left-color: var(--dark-blue, #12355A); }
.pmb-tile.hours-open { border-left-color: var(--green, #22C55E); }
.pmb-tile.hours-open.negative { border-left-color: var(--red, #EF4444); }
.pmb-label {
  font-family: var(--font-body); font-size: 11px; color: var(--darker-grey, #5F5F5F);
  text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px;
}
.pmb-val { font-family: var(--font-heading); font-size: 28px; font-weight: 700; color: var(--dark-blue, #12355A); line-height: 1; }
.hours-open.negative .pmb-val { color: var(--red-dark, #7F1D1D); }

.pmb-detail {
  margin-top: 14px; background: var(--light-grey, #FAFAFA); border: 1px solid var(--border, #E4E5E9);
  border-radius: 12px; padding: 14px 16px;
}
.pmb-detail-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
.pmb-detail-title { font-family: var(--font-heading); font-size: 13px; font-weight: 700; color: var(--dark-blue, #12355A); }
.pmb-detail-actions { display: flex; align-items: center; gap: 12px; }
.pmb-board-link { font-size: 12.5px; color: var(--light-blue, #2098D0); white-space: nowrap; }
.pmb-board-link:hover { text-decoration: underline; }
.pmb-close {
  width: 20px; height: 20px; border-radius: 50%; border: 1px solid var(--mid-grey, #E8E8E8); background: #fff;
  color: var(--dark-blue, #12355A); font-size: 12px; line-height: 1; cursor: pointer;
  display: flex; align-items: center; justify-content: center; font-family: var(--font-body);
}
.pmb-table-wrap { overflow-x: auto; }
.pmb-table { width: 100%; text-align: left; font-size: 12.5px; border-collapse: collapse; }
.pmb-table thead { color: var(--darker-grey, #5F5F5F); text-transform: uppercase; font-size: 10.5px; }
.pmb-table th, .pmb-table td { padding: 6px 10px 6px 0; }
.pmb-table tbody tr { border-top: 1px solid var(--border, #E4E5E9); }
.pmb-table tbody td:not(:first-child) { color: var(--darker-grey, #5F5F5F); }
.pmb-item-link { color: var(--light-blue, #2098D0); }
.pmb-item-link:hover { text-decoration: underline; }
</style>
