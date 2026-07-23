<template>
  <div class="osd-exec-strip">
    <div v-for="m in METRICS" :key="m" class="osd-exec-tile" :class="m">
      <div class="osd-exec-label">{{ m }}</div>
      <div class="osd-exec-val">{{ totals[m] }}</div>
      <div class="osd-exec-delta">{{ asOfLabel }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  boardId: { type: String, default: '' },
  group: { type: String, default: '' },
  status: { type: String, default: '' },
})

const METRICS = ['new', 'open', 'pending', 'closed']
const POLL_MS = 15000

const totals = ref({ new: 0, open: 0, pending: 0, closed: 0 })
const asOf = ref(null)
let intervalId = null

const asOfLabel = computed(() => (asOf.value ? `as of ${asOf.value.toLocaleTimeString()}` : ''))

async function fetchTotals() {
  const params = new URLSearchParams()
  if (props.boardId) params.set('board_id', props.boardId)
  if (props.group) params.set('group', props.group)
  if (props.status) params.set('status', props.status)
  try {
    const r = await fetch(`/api/ops-dashboard/live-totals?${params}`, { credentials: 'include' })
    if (!r.ok) return
    const data = await r.json()
    totals.value = { new: data.new, open: data.open, pending: data.pending, closed: data.closed }
    asOf.value = new Date(data.as_of)
  } catch {
    // keep showing the last known totals on a transient fetch failure
  }
}

function startPolling() {
  stopPolling()
  intervalId = setInterval(fetchTotals, POLL_MS)
}

function stopPolling() {
  if (intervalId) clearInterval(intervalId)
  intervalId = null
}

function onVisibilityChange() {
  if (document.hidden) {
    stopPolling()
  } else {
    fetchTotals()
    startPolling()
  }
}

defineExpose({ refresh: fetchTotals })

watch(() => [props.boardId, props.group, props.status], fetchTotals)

onMounted(() => {
  fetchTotals()
  startPolling()
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<style scoped>
.osd-exec-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; margin: 0 0 24px; }
.osd-exec-tile {
  background: #fff; border: 1px solid var(--border, #E4E5E9); border-left: 4px solid var(--light-blue, #2098D0);
  border-radius: 12px; padding: 18px 18px 16px; box-shadow: 0 1px 3px rgba(18, 53, 90, .06);
}
.osd-exec-tile.new { border-left-color: var(--light-blue, #2098D0); }
.osd-exec-tile.open { border-left-color: var(--warning, #F59E0B); }
.osd-exec-tile.pending { border-left-color: var(--dark-blue, #12355A); }
.osd-exec-tile.closed { border-left-color: var(--green, #22C55E); }
.osd-exec-label {
  font-family: var(--font-body); font-size: 11.5px; color: var(--darker-grey, #5F5F5F);
  text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px;
}
.osd-exec-val { font-family: var(--font-heading); font-size: 32px; font-weight: 700; color: var(--dark-blue, #12355A); line-height: 1; margin-bottom: 6px; }
.osd-exec-delta { font-size: 12px; color: var(--darker-grey, #5F5F5F); }
</style>
