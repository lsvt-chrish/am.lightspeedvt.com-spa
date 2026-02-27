<template>
  <div class="w-full max-w-5xl space-y-6">
    <div class="flex items-center gap-4">
      <router-link
        to="/certifications"
        class="text-content-muted hover:text-primary text-sm"
      >
        ← Certifications
      </router-link>
    </div>
    <h1 class="text-2xl font-bold text-primary">Users for a certification</h1>
    <p class="text-content-muted text-sm">Select a certification to see who has completed it.</p>

    <div v-if="listError" class="text-red-500">{{ listError }}</div>
    <div v-else class="space-y-3">
      <input
        v-model="searchQuery"
        type="search"
        placeholder="Filter certifications…"
        class="w-full max-w-md rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
      />
      <div v-if="filteredCerts.length > 0" class="flex flex-wrap items-center gap-4 text-sm text-content-muted">
        <label class="flex items-center gap-2">
          <span>Show</span>
          <select
            v-model.number="certPageSize"
            class="rounded bg-surface border border-edge text-content px-2 py-1 focus:border-secondary focus:outline-none"
          >
            <option v-for="n in pageSizeOptions" :key="n" :value="n">{{ n }}</option>
          </select>
          <span>per page</span>
        </label>
        <span v-if="certTotalPages > 1" class="flex items-center gap-2">
          <button
            type="button"
            :disabled="certPage <= 1"
            class="rounded px-2 py-1 text-primary hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
            @click="certPage = Math.max(1, certPage - 1)"
          >
            Previous
          </button>
          <span>Page {{ certPage }} of {{ certTotalPages }}</span>
          <button
            type="button"
            :disabled="certPage >= certTotalPages"
            class="rounded px-2 py-1 text-primary hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
            @click="certPage = Math.min(certTotalPages, certPage + 1)"
          >
            Next
          </button>
        </span>
      </div>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <button
          v-for="cert in certsPaginated"
          :key="cert.id"
          type="button"
          class="rounded-lg border p-4 text-left transition-colors"
          :class="selectedCert?.id === cert.id
            ? 'border-secondary bg-surface'
            : 'border-edge bg-surface hover:border-secondary'"
          @click="selectCert(cert)"
        >
          <span class="font-medium text-content">{{ cert.name }}</span>
          <span class="block mt-1 text-xs text-content-muted">ID: {{ cert.id }}</span>
          <p v-if="cert.description" class="mt-2 text-sm text-content-muted line-clamp-2">
            {{ cert.description }}
          </p>
        </button>
      </div>
      <p v-if="loadingList" class="text-content-muted">Loading certifications…</p>
      <p v-if="!loadingList && certifications.length === 0 && !listError" class="text-content-muted">
        No certifications found.
      </p>
    </div>

    <template v-if="selectedCert">
      <h2 class="text-lg font-semibold text-content">
        Completed: {{ selectedCert.name }}
      </h2>
      <p v-if="loadingReport" class="text-content-muted">Loading report…</p>
      <p v-else-if="reportError" class="text-red-500">{{ reportError }}</p>
      <template v-else-if="reportUsers.length > 0">
        <div class="flex flex-wrap items-center gap-4 text-sm text-content-muted mb-2">
          <label class="flex items-center gap-2">
            <span>Show</span>
            <select
              v-model.number="userPageSize"
              class="rounded bg-surface border border-edge text-content px-2 py-1 focus:border-secondary focus:outline-none"
            >
              <option v-for="n in pageSizeOptions" :key="n" :value="n">{{ n }}</option>
            </select>
            <span>per page</span>
          </label>
          <span v-if="userTotalPages > 1" class="flex items-center gap-2">
            <button
              type="button"
              :disabled="userPage <= 1"
              class="rounded px-2 py-1 text-primary hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
              @click="userPage = Math.max(1, userPage - 1)"
            >
              Previous
            </button>
            <span>Page {{ userPage }} of {{ userTotalPages }}</span>
            <button
              type="button"
              :disabled="userPage >= userTotalPages"
              class="rounded px-2 py-1 text-primary hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
              @click="userPage = Math.min(userTotalPages, userPage + 1)"
            >
              Next
            </button>
          </span>
        </div>
        <div class="overflow-x-auto rounded-lg border border-edge">
          <table class="w-full text-sm text-left">
            <thead class="bg-surface text-content">
              <tr>
                <th class="px-4 py-2">#</th>
                <th class="px-4 py-2">Name</th>
                <th class="px-4 py-2">Username</th>
                <th class="px-4 py-2">Email</th>
                <th class="px-4 py-2">Action</th>
              </tr>
            </thead>
            <tbody class="text-content">
              <tr
                v-for="(u, i) in usersPaginated"
                :key="u.userId || i"
                class="border-t border-edge hover:bg-surface"
              >
                <td class="px-4 py-2">{{ (userPage - 1) * userPageSize + i + 1 }}</td>
                <td class="px-4 py-2">{{ [u.firstName, u.lastName].filter(Boolean).join(' ') || '—' }}</td>
                <td class="px-4 py-2">{{ u.username || '—' }}</td>
                <td class="px-4 py-2">{{ u.email || '—' }}</td>
                <td class="px-4 py-2">
                  <a
                    :href="certificateShareUrl(u)"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-primary hover:opacity-80"
                  >
                    View certificate
                  </a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <p v-else class="text-content-muted">No completions for this certification.</p>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'

const pageSizeOptions = [10, 25, 50, 100]

const certifications = ref([])
const loadingList = ref(false)
const listError = ref(null)
const searchQuery = ref('')
const certPageSize = ref(10)
const certPage = ref(1)
const selectedCert = ref(null)
const reportUsers = ref([])
const loadingReport = ref(false)
const reportError = ref(null)
const userPageSize = ref(10)
const userPage = ref(1)

const filteredCerts = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return certifications.value
  return certifications.value.filter(
    (c) =>
      String(c.name || '').toLowerCase().includes(q) ||
      String(c.id ?? '').toLowerCase().includes(q) ||
      String(c.description || '').toLowerCase().includes(q)
  )
})

const certTotalPages = computed(() =>
  Math.max(1, Math.ceil(filteredCerts.value.length / certPageSize.value))
)
const certsPaginated = computed(() => {
  const start = (certPage.value - 1) * certPageSize.value
  return filteredCerts.value.slice(start, start + certPageSize.value)
})

const userTotalPages = computed(() =>
  Math.max(1, Math.ceil(reportUsers.value.length / userPageSize.value))
)
const usersPaginated = computed(() => {
  const start = (userPage.value - 1) * userPageSize.value
  return reportUsers.value.slice(start, start + userPageSize.value)
})

watch(searchQuery, () => { certPage.value = 1 })
watch(certPageSize, () => { certPage.value = 1 })
watch(certTotalPages, (total) => { if (certPage.value > total) certPage.value = Math.max(1, total) })
watch(userPageSize, () => { userPage.value = 1 })
watch(userTotalPages, (total) => { if (userPage.value > total) userPage.value = Math.max(1, total) })

function certificateShareUrl(user) {
  const certId = selectedCert.value?.id
  const uid = user.userId ?? user.id
  return `https://vt.lightspeedvt.com/share/certificate/?id=${encodeURIComponent(uid)}&certID=${encodeURIComponent(certId)}`
}

async function loadList() {
  loadingList.value = true
  listError.value = null
  try {
    const res = await fetch('/api/certifications', { credentials: 'include' })
    if (res.status === 401) {
      listError.value = 'No credentials in session. Open Credentials and enter your API key and secret.'
      return
    }
    if (res.status === 429) {
      listError.value = 'Too many requests. Please wait a minute and try again.'
      return
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      listError.value = d.detail || res.statusText
      return
    }
    const data = await res.json()
    certifications.value = data.certifications || []
  } catch (e) {
    listError.value = e.message || 'Request failed'
  } finally {
    loadingList.value = false
  }
}

async function selectCert(cert) {
  if (selectedCert.value?.id === cert.id) return
  selectedCert.value = cert
  reportUsers.value = []
  reportError.value = null
  loadingReport.value = true
  try {
    const res = await fetch(
      `/api/certifications/${encodeURIComponent(cert.id)}/users/report`,
      { credentials: 'include' }
    )
    if (res.status === 401) {
      reportError.value = 'No credentials in session.'
      return
    }
    if (res.status === 429) {
      reportError.value = 'Too many requests. Please wait a minute and try again.'
      return
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      reportError.value = d.detail || res.statusText
      return
    }
    const data = await res.json()
    reportUsers.value = data.users || []
    userPage.value = 1
  } catch (e) {
    reportError.value = e.message || 'Request failed'
  } finally {
    loadingReport.value = false
  }
}

onMounted(loadList)
</script>
