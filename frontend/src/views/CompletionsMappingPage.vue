<template>
  <div class="w-full max-w-6xl space-y-6">
    <div class="flex items-center gap-4">
      <router-link
        to="/user-training-data"
        class="text-content-muted hover:text-primary text-sm"
      >
        ← User Training Data
      </router-link>
    </div>

    <h1 class="text-2xl font-bold text-primary">Map user completions</h1>
    <p class="text-content-muted text-sm">
      Copy chapter-level course completions from a source LightSpeed VT user to a destination user
      in the same system. Preview the diff first, then choose how to handle chapters the destination
      already has.
    </p>

    <form class="space-y-3" @submit.prevent="loadPreview">
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label for="source_user_id" class="block text-sm font-medium text-content mb-1">Source user ID</label>
          <input
            id="source_user_id"
            v-model="sourceUserId"
            type="text"
            class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
            placeholder="e.g. 5832308"
          />
        </div>
        <div>
          <label for="destination_user_id" class="block text-sm font-medium text-content mb-1">Destination user ID</label>
          <input
            id="destination_user_id"
            v-model="destinationUserId"
            type="text"
            class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
            placeholder="e.g. 5832309"
          />
        </div>
      </div>
      <div class="grid gap-3 sm:grid-cols-[1fr,1fr,auto] items-end">
        <div>
          <label for="start_date" class="block text-sm font-medium text-content mb-1">Start date</label>
          <input
            id="start_date"
            v-model="startDate"
            type="date"
            class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          />
        </div>
        <div>
          <label for="end_date" class="block text-sm font-medium text-content mb-1">End date</label>
          <input
            id="end_date"
            v-model="endDate"
            type="date"
            class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          />
        </div>
        <button
          type="submit"
          :disabled="loadingPreview || !sourceUserId.trim() || !destinationUserId.trim()"
          class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50"
        >
          {{ loadingPreview ? 'Loading…' : 'Preview' }}
        </button>
      </div>
      <p class="text-xs text-content-muted">
        Without a date range, LightSpeed VT only returns the current month. Defaults to the last 12 months; clear the fields to force a current-month query.
      </p>
    </form>

    <p v-if="loadingPreview" class="text-content-muted">Fetching training info for both users…</p>
    <p v-if="error" class="text-red-500">{{ error }}</p>

    <template v-if="summary">
      <p v-if="queriedWindow" class="text-xs text-content-muted">
        Window queried: <span class="text-content">{{ queriedWindow }}</span>
      </p>
      <div class="rounded-lg border border-edge bg-surface p-4 grid gap-4 sm:grid-cols-4 text-sm">
        <div>
          <div class="text-content-muted">Source chapters</div>
          <div class="text-primary text-lg font-semibold">{{ summary.source_total }}</div>
        </div>
        <div>
          <div class="text-content-muted">Destination chapters</div>
          <div class="text-primary text-lg font-semibold">{{ summary.destination_total }}</div>
        </div>
        <div>
          <div class="text-content-muted">New (missing on destination)</div>
          <div class="text-emerald-500 text-lg font-semibold">{{ summary.new }}</div>
        </div>
        <div>
          <div class="text-content-muted">Already on destination</div>
          <div class="text-amber-500 text-lg font-semibold">{{ summary.existing }}</div>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-4 text-sm">
        <fieldset class="flex items-center gap-3">
          <legend class="sr-only">Conflict mode</legend>
          <span class="text-content-muted">Conflict mode:</span>
          <label class="flex items-center gap-1 text-content">
            <input v-model="conflictMode" type="radio" value="skip" />
            Skip existing
          </label>
          <label class="flex items-center gap-1 text-content">
            <input v-model="conflictMode" type="radio" value="overwrite" />
            Overwrite existing
          </label>
        </fieldset>
        <button
          type="button"
          class="rounded px-3 py-1 text-primary hover:bg-surface border border-edge"
          @click="selectAllNew"
        >
          Select all new
        </button>
        <button
          type="button"
          class="rounded px-3 py-1 text-primary hover:bg-surface border border-edge"
          @click="selectAll"
        >
          Select all
        </button>
        <button
          type="button"
          class="rounded px-3 py-1 text-primary hover:bg-surface border border-edge"
          @click="clearSelection"
        >
          Clear
        </button>
        <span class="text-content-muted ml-auto">
          {{ selectedCount }} selected
        </span>
        <button
          type="button"
          :disabled="applying || selectedCount === 0"
          class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50"
          @click="applyMapping"
        >
          {{ applying ? 'Applying…' : `Apply mapping (${selectedCount})` }}
        </button>
      </div>

      <div v-if="applyResult" class="rounded-lg border border-edge bg-surface p-3 text-sm">
        <span class="text-emerald-500 font-medium">{{ applyResult.created }} created</span>,
        <span class="text-amber-500 font-medium">{{ applyResult.skipped }} skipped</span>,
        <span class="text-red-500 font-medium">{{ applyResult.failed }} failed</span>.
      </div>

      <div v-if="chapters.length > 0" class="overflow-x-auto rounded-lg border border-edge">
        <table class="w-full text-sm text-left">
          <thead class="bg-surface text-content">
            <tr>
              <th class="px-3 py-2">
                <input
                  type="checkbox"
                  :checked="allVisibleSelected"
                  @change="toggleAllVisible($event.target.checked)"
                />
              </th>
              <th class="px-3 py-2">Course</th>
              <th class="px-3 py-2">Chapter</th>
              <th class="px-3 py-2">Source date</th>
              <th class="px-3 py-2">Status</th>
              <th class="px-3 py-2">Destination date</th>
              <th class="px-3 py-2">Result</th>
            </tr>
          </thead>
          <tbody class="text-content">
            <tr
              v-for="ch in chapters"
              :key="rowKey(ch)"
              class="border-t border-edge hover:bg-surface"
            >
              <td class="px-3 py-2">
                <input
                  v-model="selected[rowKey(ch)]"
                  type="checkbox"
                />
              </td>
              <td class="px-3 py-2">
                <div class="text-content">{{ ch.courseName || '—' }}</div>
                <div class="text-content-muted text-xs">ID {{ ch.courseId }}</div>
              </td>
              <td class="px-3 py-2">
                <div class="text-content">{{ ch.chapterName || '—' }}</div>
                <div class="text-content-muted text-xs">ID {{ ch.chapterId }}</div>
              </td>
              <td class="px-3 py-2">{{ ch.chapterAttemptDate || '—' }}</td>
              <td class="px-3 py-2">
                <span
                  v-if="ch.status === 'new'"
                  class="inline-flex items-center rounded px-2 py-0.5 text-xs bg-emerald-500/15 text-emerald-500"
                >
                  new
                </span>
                <span
                  v-else
                  class="inline-flex items-center rounded px-2 py-0.5 text-xs bg-amber-500/15 text-amber-500"
                >
                  existing
                </span>
              </td>
              <td class="px-3 py-2">
                {{ ch.destination_existing?.chapterAttemptDate || '—' }}
              </td>
              <td class="px-3 py-2 text-xs">
                <template v-if="resultsByKey[rowKey(ch)]">
                  <span
                    v-if="resultsByKey[rowKey(ch)].skipped"
                    class="text-amber-500"
                  >Skipped</span>
                  <span
                    v-else-if="resultsByKey[rowKey(ch)].ok"
                    class="text-emerald-500"
                  >Created</span>
                  <span v-else class="text-red-500" :title="resultsByKey[rowKey(ch)].error || ''">
                    Failed: {{ truncate(resultsByKey[rowKey(ch)].error, 60) }}
                  </span>
                </template>
                <span v-else class="text-content-muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-if="summary && chapters.length === 0" class="text-content-muted">
        No chapters found on the source user.
      </p>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

function isoDate(d) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
function defaultStartDate() {
  const d = new Date()
  d.setFullYear(d.getFullYear() - 1)
  return isoDate(d)
}
function defaultEndDate() {
  return isoDate(new Date())
}

const sourceUserId = ref('')
const destinationUserId = ref('')
const startDate = ref(defaultStartDate())
const endDate = ref(defaultEndDate())
const loadingPreview = ref(false)
const applying = ref(false)
const error = ref(null)
const chapters = ref([])
const summary = ref(null)
const conflictMode = ref('skip')
const selected = ref({})
const applyResult = ref(null)
const results = ref([])
const lastQuery = ref({ start: null, end: null })

const queriedWindow = computed(() => {
  const { start, end } = lastQuery.value
  if (!start && !end) return 'current month (LSVT default)'
  return `${start || '—'} → ${end || '—'}`
})

function rowKey(ch) {
  return `${ch.courseId}::${ch.chapterId}`
}

const selectedCount = computed(() =>
  Object.values(selected.value).filter(Boolean).length
)

const allVisibleSelected = computed(() => {
  if (chapters.value.length === 0) return false
  return chapters.value.every((ch) => selected.value[rowKey(ch)])
})

const resultsByKey = computed(() => {
  const map = {}
  for (const r of results.value) {
    map[`${r.courseId}::${r.chapterId}`] = r
  }
  return map
})

function truncate(s, n) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '…' : s
}

function selectAllNew() {
  const next = {}
  for (const ch of chapters.value) {
    if (ch.status === 'new') next[rowKey(ch)] = true
  }
  selected.value = next
}

function selectAll() {
  const next = {}
  for (const ch of chapters.value) next[rowKey(ch)] = true
  selected.value = next
}

function clearSelection() {
  selected.value = {}
}

function toggleAllVisible(checked) {
  const next = { ...selected.value }
  for (const ch of chapters.value) next[rowKey(ch)] = !!checked
  selected.value = next
}

watch([sourceUserId, destinationUserId, startDate, endDate], () => {
  // Reset previous results when changing inputs
  applyResult.value = null
  results.value = []
})

async function loadPreview() {
  const src = sourceUserId.value.trim()
  const dest = destinationUserId.value.trim()
  if (!src || !dest) return
  if (src === dest) {
    error.value = 'Source and destination must be different users.'
    return
  }
  const startTrim = (startDate.value || '').trim()
  const endTrim = (endDate.value || '').trim()
  if (startTrim && endTrim && startTrim > endTrim) {
    error.value = 'Start date must be before end date.'
    return
  }
  loadingPreview.value = true
  error.value = null
  chapters.value = []
  summary.value = null
  selected.value = {}
  applyResult.value = null
  results.value = []
  try {
    const params = new URLSearchParams({
      source_user_id: src,
      destination_user_id: dest,
    })
    if (startTrim) params.set('start_date', startTrim)
    if (endTrim) params.set('end_date', endTrim)
    const res = await fetch(`/api/completions-mapping/preview?${params.toString()}`, {
      credentials: 'include',
    })
    if (res.status === 401) {
      error.value = 'No credentials in session. Open Credentials and enter your API key and secret.'
      return
    }
    if (res.status === 429) {
      error.value = 'Too many requests. Please wait a minute and try again.'
      return
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      error.value = d.detail || res.statusText
      return
    }
    const data = await res.json()
    chapters.value = data.chapters || []
    summary.value = data.summary || null
    lastQuery.value = {
      start: data.start_date || null,
      end: data.end_date || null,
    }
    // Pre-select all "new" rows by default to nudge the safe path.
    selectAllNew()
  } catch (e) {
    error.value = e.message || 'Request failed'
  } finally {
    loadingPreview.value = false
  }
}

async function applyMapping() {
  if (selectedCount.value === 0) return
  applying.value = true
  error.value = null
  applyResult.value = null
  results.value = []
  try {
    const picked = chapters.value
      .filter((ch) => selected.value[rowKey(ch)])
      .map((ch) => ({
        courseId: ch.courseId,
        chapterId: ch.chapterId,
        chapterAttemptDate: ch.chapterAttemptDate || null,
        chapterAttemptScore:
          ch.chapterAttemptScore === '' || ch.chapterAttemptScore == null
            ? null
            : ch.chapterAttemptScore,
        chapterAttemptStatus: ch.chapterAttemptStatus || null,
      }))
    const res = await fetch('/api/completions-mapping/apply', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_user_id: sourceUserId.value.trim(),
        destination_user_id: destinationUserId.value.trim(),
        conflict_mode: conflictMode.value,
        start_date: (startDate.value || '').trim() || null,
        end_date: (endDate.value || '').trim() || null,
        chapters: picked,
      }),
    })
    if (res.status === 401) {
      error.value = 'No credentials in session. Open Credentials and enter your API key and secret.'
      return
    }
    if (res.status === 429) {
      error.value = 'Too many requests. Please wait a minute and try again.'
      return
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      error.value = d.detail || res.statusText
      return
    }
    const data = await res.json()
    applyResult.value = {
      created: data.created || 0,
      skipped: data.skipped || 0,
      failed: data.failed || 0,
    }
    results.value = data.results || []
  } catch (e) {
    error.value = e.message || 'Request failed'
  } finally {
    applying.value = false
  }
}
</script>
