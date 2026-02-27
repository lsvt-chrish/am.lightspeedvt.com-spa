<template>
  <div class="w-full max-w-4xl space-y-6">
    <div class="flex items-center gap-4">
      <router-link
        to="/certifications"
        class="text-content-muted hover:text-primary text-sm"
      >
        ← Certifications
      </router-link>
    </div>
    <h1 class="text-2xl font-bold text-primary">Certifications for user</h1>
    <p class="text-content-muted text-sm">Enter a user ID to see all certifications that user has completed.</p>

    <form class="flex gap-3 items-end" @submit.prevent="submit">
      <div class="flex-1">
        <label for="user_id" class="block text-sm font-medium text-content mb-1">User ID</label>
        <input
          id="user_id"
          v-model="userId"
          type="text"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="e.g. 5832308"
        />
      </div>
      <button
        type="submit"
        :disabled="loading || !userId.trim()"
        class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50"
      >
        {{ loading ? 'Searching…' : 'Search' }}
      </button>
    </form>

    <p v-if="loading" class="text-content-muted">This may take a moment while we check each certification…</p>
    <p v-if="error" class="text-red-500">{{ error }}</p>

    <template v-if="certifications.length > 0">
      <div class="flex flex-wrap items-center gap-4 text-sm text-content-muted mb-2">
        <label class="flex items-center gap-2">
          <span>Show</span>
          <select
            v-model.number="pageSize"
            class="rounded bg-surface border border-edge text-content px-2 py-1 focus:border-secondary focus:outline-none"
          >
            <option v-for="n in pageSizeOptions" :key="n" :value="n">{{ n }}</option>
          </select>
          <span>per page</span>
        </label>
        <span v-if="totalPages > 1" class="flex items-center gap-2">
          <button
            type="button"
            :disabled="page <= 1"
            class="rounded px-2 py-1 text-primary hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
            @click="page = Math.max(1, page - 1)"
          >
            Previous
          </button>
          <span>Page {{ page }} of {{ totalPages }}</span>
          <button
            type="button"
            :disabled="page >= totalPages"
            class="rounded px-2 py-1 text-primary hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
            @click="page = Math.min(totalPages, page + 1)"
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
              <th class="px-4 py-2">Certification ID</th>
              <th class="px-4 py-2">Name</th>
              <th class="px-4 py-2">Completion date</th>
              <th class="px-4 py-2">Action</th>
            </tr>
          </thead>
          <tbody class="text-content">
            <tr
              v-for="(cert, i) in certificationsPaginated"
              :key="cert.cert_id"
              class="border-t border-edge hover:bg-surface"
            >
              <td class="px-4 py-2">{{ (page - 1) * pageSize + i + 1 }}</td>
              <td class="px-4 py-2">{{ cert.cert_id }}</td>
              <td class="px-4 py-2">{{ cert.cert_name }}</td>
              <td class="px-4 py-2">{{ cert.completeDate || '—' }}</td>
              <td class="px-4 py-2">
                <a
                  :href="certificateShareUrl(cert)"
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
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const pageSizeOptions = [10, 25, 50, 100]

const userId = ref('')
const loading = ref(false)
const error = ref(null)
const certifications = ref([])
const pageSize = ref(10)
const page = ref(1)

const totalPages = computed(() =>
  Math.max(1, Math.ceil(certifications.value.length / pageSize.value))
)
const certificationsPaginated = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return certifications.value.slice(start, start + pageSize.value)
})

watch(pageSize, () => { page.value = 1 })

function certificateShareUrl(cert) {
  const uid = cert.userId ?? userId.value
  return `https://vt.lightspeedvt.com/share/certificate/?id=${encodeURIComponent(uid)}&certID=${encodeURIComponent(cert.cert_id)}`
}

async function submit() {
  const uid = userId.value.trim()
  if (!uid) return
  loading.value = true
  error.value = null
  certifications.value = []
  try {
    const res = await fetch(`/api/certifications/by-user/${encodeURIComponent(uid)}`, {
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
    certifications.value = data.certifications || []
    page.value = 1
  } catch (e) {
    error.value = e.message || 'Request failed'
  } finally {
    loading.value = false
  }
}
</script>
