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

    <h1 class="text-2xl font-bold text-primary">Check users in bulk</h1>
    <p class="text-content-muted text-sm">
      Upload a CSV or XLSX of users. Each row is checked against LightSpeed VT to see if the user
      already exists in your system. Results are split into two lists that you can download as CSV.
    </p>

    <div class="rounded-lg border border-edge bg-surface p-4 space-y-3">
      <label class="block text-sm font-medium text-content">Step 1 &mdash; Upload spreadsheet</label>
      <input
        ref="fileInput"
        type="file"
        accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        class="block w-full text-sm text-content file:mr-3 file:rounded file:border-0 file:bg-secondary file:text-secondary-accent file:font-medium file:px-4 file:py-2 hover:file:opacity-90"
        @change="onFileSelected"
      />
      <p v-if="file" class="text-xs text-content-muted">
        Selected: <span class="text-content">{{ file.name }}</span>
        <span v-if="preview"> &middot; {{ preview.format.toUpperCase() }} &middot; {{ preview.row_count }} rows &middot; {{ preview.headers.length }} columns</span>
      </p>
      <p v-if="previewLoading" class="text-xs text-content-muted">Reading file&hellip;</p>
      <p v-if="previewError" class="text-red-500 text-sm">{{ previewError }}</p>
    </div>

    <div v-if="preview" class="rounded-lg border border-edge bg-surface p-4 space-y-4">
      <label class="block text-sm font-medium text-content">Step 2 &mdash; Configure the lookup</label>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label for="lookup_column" class="block text-sm text-content mb-1">Lookup column</label>
          <select
            id="lookup_column"
            v-model="lookupColumn"
            class="w-full rounded bg-page border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          >
            <option value="" disabled>Select a column&hellip;</option>
            <option v-for="h in preview.headers" :key="h" :value="h">{{ h }}</option>
          </select>
        </div>
        <div>
          <span class="block text-sm text-content mb-1">Lookup key type</span>
          <div class="flex gap-4 items-center pt-1">
            <label class="flex items-center gap-1 text-content text-sm">
              <input v-model="lookupKeyType" type="radio" value="email" />
              Email
            </label>
            <label class="flex items-center gap-1 text-content text-sm">
              <input v-model="lookupKeyType" type="radio" value="username" />
              Username
            </label>
            <label class="flex items-center gap-1 text-content text-sm">
              <input v-model="lookupKeyType" type="radio" value="userId" />
              User ID
            </label>
          </div>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <button
          type="button"
          :disabled="!canCheck || checking"
          class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50"
          @click="runCheck"
        >
          {{ checking ? 'Checking\u2026' : 'Check users' }}
        </button>
        <p v-if="checkError" class="text-red-500 text-sm">{{ checkError }}</p>
      </div>
    </div>

    <template v-if="result">
      <div class="rounded-lg border border-edge bg-surface p-4 grid gap-4 sm:grid-cols-4 text-sm">
        <div>
          <div class="text-content-muted">Total rows</div>
          <div class="text-primary text-lg font-semibold">{{ result.summary.total }}</div>
        </div>
        <div>
          <div class="text-content-muted">Exists in LSVT</div>
          <div class="text-emerald-500 text-lg font-semibold">{{ result.summary.exists }}</div>
        </div>
        <div>
          <div class="text-content-muted">Missing</div>
          <div class="text-amber-500 text-lg font-semibold">{{ result.summary.missing }}</div>
        </div>
        <div>
          <div class="text-content-muted">Blank lookup</div>
          <div class="text-content text-lg font-semibold">{{ result.summary.blank_lookup }}</div>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-3 text-sm">
        <div class="inline-flex rounded-lg border border-edge overflow-hidden">
          <button
            type="button"
            :class="[activeTab === 'exists' ? 'bg-secondary text-secondary-accent' : 'text-content hover:bg-surface']"
            class="px-3 py-1"
            @click="activeTab = 'exists'"
          >
            Exists ({{ result.summary.exists }})
          </button>
          <button
            type="button"
            :class="[activeTab === 'missing' ? 'bg-secondary text-secondary-accent' : 'text-content hover:bg-surface']"
            class="px-3 py-1"
            @click="activeTab = 'missing'"
          >
            Missing ({{ result.summary.missing }})
          </button>
        </div>
        <div class="ml-auto flex items-center gap-2">
          <button
            type="button"
            :disabled="result.summary.exists === 0"
            class="px-3 py-1.5 rounded border border-edge text-primary hover:bg-surface disabled:opacity-50"
            @click="downloadBucket('exists')"
          >
            Download exists.csv
          </button>
          <button
            type="button"
            :disabled="result.summary.missing === 0"
            class="px-3 py-1.5 rounded border border-edge text-primary hover:bg-surface disabled:opacity-50"
            @click="downloadBucket('missing')"
          >
            Download missing.csv
          </button>
        </div>
      </div>

      <div class="overflow-x-auto rounded-lg border border-edge">
        <table class="w-full text-sm text-left">
          <thead class="bg-surface text-content">
            <tr>
              <th class="px-3 py-2 whitespace-nowrap">#</th>
              <th
                v-for="h in tableHeaders"
                :key="h"
                class="px-3 py-2 whitespace-nowrap"
              >
                {{ h }}
              </th>
            </tr>
          </thead>
          <tbody class="text-content">
            <tr
              v-for="(row, i) in visibleRows"
              :key="i"
              class="border-t border-edge hover:bg-surface"
            >
              <td class="px-3 py-2 text-content-muted">{{ i + 1 }}</td>
              <td
                v-for="h in tableHeaders"
                :key="h"
                class="px-3 py-2 whitespace-nowrap"
              >
                {{ row[h] ?? '' }}
              </td>
            </tr>
            <tr v-if="visibleRows.length === 0">
              <td :colspan="tableHeaders.length + 1" class="px-3 py-4 text-content-muted text-center">
                No rows in this bucket.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="bucketRows.length > visibleRows.length" class="text-xs text-content-muted">
        Showing {{ visibleRows.length }} of {{ bucketRows.length }} rows. Use the download button to get the full list.
      </p>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const PREVIEW_ROWS_SHOWN = 50

const fileInput = ref(null)
const file = ref(null)
const preview = ref(null)
const previewLoading = ref(false)
const previewError = ref(null)

const lookupColumn = ref('')
const lookupKeyType = ref('email')

const checking = ref(false)
const checkError = ref(null)
const result = ref(null)
const activeTab = ref('exists')

const canCheck = computed(() => !!file.value && !!preview.value && !!lookupColumn.value && !!lookupKeyType.value)

const bucketRows = computed(() => (result.value ? result.value[activeTab.value] : []))
const visibleRows = computed(() => bucketRows.value.slice(0, PREVIEW_ROWS_SHOWN))
const tableHeaders = computed(() => {
  if (!result.value) return []
  const extras =
    activeTab.value === 'exists'
      ? result.value.extra_headers_exists || []
      : result.value.extra_headers_missing || []
  return [...(result.value.headers || []), ...extras]
})

watch(lookupColumn, () => {
  // Reset stale results when the config changes.
  result.value = null
})
watch(lookupKeyType, () => {
  result.value = null
})

async function onFileSelected(event) {
  const selected = event.target.files?.[0] || null
  file.value = selected
  preview.value = null
  result.value = null
  lookupColumn.value = ''
  previewError.value = null
  if (!selected) return
  previewLoading.value = true
  try {
    const fd = new FormData()
    fd.append('file', selected)
    const res = await fetch('/api/user-check/preview', {
      method: 'POST',
      credentials: 'include',
      body: fd,
    })
    if (res.status === 401) {
      previewError.value = 'No credentials in session. Open Credentials and enter your API key and secret.'
      return
    }
    if (res.status === 429) {
      previewError.value = 'Too many requests. Please wait a minute and try again.'
      return
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      previewError.value = d.detail || res.statusText
      return
    }
    preview.value = await res.json()
    lookupColumn.value = guessLookupColumn(preview.value.headers)
  } catch (e) {
    previewError.value = e.message || 'Failed to read file'
  } finally {
    previewLoading.value = false
  }
}

function guessLookupColumn(headers) {
  const wanted = ['email', 'e-mail', 'username', 'user id', 'userid', 'user_id']
  const lower = headers.map((h) => h.toLowerCase())
  for (const w of wanted) {
    const i = lower.indexOf(w)
    if (i >= 0) return headers[i]
  }
  return headers[0] || ''
}

async function runCheck() {
  if (!canCheck.value) return
  checking.value = true
  checkError.value = null
  result.value = null
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    fd.append('lookup_column', lookupColumn.value)
    fd.append('lookup_key_type', lookupKeyType.value)
    const res = await fetch('/api/user-check/check', {
      method: 'POST',
      credentials: 'include',
      body: fd,
    })
    if (res.status === 401) {
      checkError.value = 'No credentials in session. Open Credentials and enter your API key and secret.'
      return
    }
    if (res.status === 429) {
      checkError.value = 'Too many requests. Please wait a minute and try again.'
      return
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      checkError.value = d.detail || res.statusText
      return
    }
    result.value = await res.json()
    activeTab.value = result.value.summary.exists >= result.value.summary.missing ? 'exists' : 'missing'
  } catch (e) {
    checkError.value = e.message || 'Request failed'
  } finally {
    checking.value = false
  }
}

function toCsv(headers, rows) {
  const esc = (v) => {
    const s = v == null ? '' : String(v)
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s
  }
  const lines = [headers.map(esc).join(',')]
  for (const r of rows) lines.push(headers.map((h) => esc(r[h])).join(','))
  return lines.join('\r\n')
}

function downloadBucket(bucket) {
  if (!result.value) return
  const rows = result.value[bucket] || []
  if (rows.length === 0) return
  const extras =
    bucket === 'exists'
      ? result.value.extra_headers_exists || []
      : result.value.extra_headers_missing || []
  const headers = [...(result.value.headers || []), ...extras]
  const csv = toCsv(headers, rows)
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  a.href = url
  a.download = `user-check-${bucket}-${stamp}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
</script>
