<template>
  <div class="w-full max-w-5xl space-y-6">
    <div class="flex items-center gap-4">
      <router-link
        to="/user-training-data"
        class="text-content-muted hover:text-primary text-sm"
      >
        ← User Training Data
      </router-link>
    </div>
    <div v-if="exportLoading" class="w-full h-1 bg-edge rounded overflow-hidden">
      <div class="h-full bg-secondary animate-pulse" style="width: 100%"></div>
    </div>
    <h1 class="text-2xl font-bold text-primary">Export training data</h1>
    <p class="text-content-muted text-sm">
      Choose scope (per user, per location, or all users), select items, optionally filter by courses and date range, then download CSV.
    </p>

    <div v-if="!hasCredentials" class="rounded-lg bg-surface border border-edge p-4">
      <p class="text-content mb-2">API credentials are required to export training data.</p>
      <button
        type="button"
        class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90"
        @click="openCredentials"
      >
        Open Credentials
      </button>
    </div>

    <template v-else>
      <!-- Scope -->
      <fieldset class="space-y-2">
        <legend class="text-sm font-medium text-content">Scope</legend>
        <div class="flex flex-wrap gap-4">
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="scope" type="radio" value="user" class="rounded border-edge text-primary" />
            <span class="text-content">Per user</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="scope" type="radio" value="location" class="rounded border-edge text-primary" />
            <span class="text-content">Per location</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="scope" type="radio" value="all" class="rounded border-edge text-primary" />
            <span class="text-content">All users</span>
          </label>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <label class="text-content font-medium">User status:</label>
          <select
            v-model="userStatus"
            class="rounded bg-surface border border-edge text-content px-2 py-1 focus:border-secondary focus:outline-none"
          >
            <option value="active">Active users</option>
            <option value="inactive">Inactive users</option>
            <option value="all">All users</option>
          </select>
        </div>
      </fieldset>

      <!-- Per user: paginated user list with checkboxes -->
      <section v-if="scope === 'user'" class="space-y-3 rounded-lg border border-edge bg-surface p-4">
        <h2 class="text-lg font-semibold text-content">Select users</h2>
        <input
          v-model="userSearch"
          type="search"
          placeholder="Filter by name, email, or ID…"
          class="w-full max-w-md rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          @input="debouncedLoadUsers"
        />
        <div class="flex flex-wrap items-center gap-4 text-sm text-content-muted">
          <label class="flex items-center gap-2">
            <span>Show</span>
            <select
              v-model.number="userPageSize"
              class="rounded bg-surface border border-edge text-content px-2 py-1 focus:border-secondary focus:outline-none"
              @change="loadUsers"
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
              @click="userPage = Math.max(1, userPage - 1); loadUsers()"
            >
              Previous
            </button>
            <span>Page {{ userPage }} of {{ userTotalPages }}</span>
            <button
              type="button"
              :disabled="userPage >= userTotalPages"
              class="rounded px-2 py-1 text-primary hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
              @click="userPage = Math.min(userTotalPages, userPage + 1); loadUsers()"
            >
              Next
            </button>
          </span>
        </div>
        <p v-if="usersLoading" class="flex items-center gap-2 text-content-muted">
          <span class="inline-block h-3 w-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span>Loading users…</span>
        </p>
        <p v-else-if="usersError" class="text-red-500">{{ usersError }}</p>
        <div v-else class="overflow-x-auto rounded-lg border border-edge">
          <table class="w-full text-sm text-left">
            <thead class="bg-surface text-content">
              <tr>
                <th class="px-4 py-2 w-10">
                  <input
                    type="checkbox"
                    :checked="allUsersOnPageSelected"
                    :indeterminate="someUsersOnPageSelected && !allUsersOnPageSelected"
                    class="rounded border-edge text-primary"
                    @change="toggleAllUsersOnPage"
                  />
                </th>
                <th class="px-4 py-2">Name</th>
                <th class="px-4 py-2">Email</th>
                <th class="px-4 py-2">ID</th>
              </tr>
            </thead>
            <tbody class="text-content">
              <tr
                v-for="u in userItems"
                :key="u.id"
                class="border-t border-edge hover:bg-surface"
              >
                <td class="px-4 py-2">
                  <input
                    type="checkbox"
                    :checked="selectedUserIds.has(String(u.id))"
                    class="rounded border-edge text-primary"
                    @change="toggleUser(u.id)"
                  />
                </td>
                <td class="px-4 py-2">{{ u.name || '—' }}</td>
                <td class="px-4 py-2">{{ u.email || '—' }}</td>
                <td class="px-4 py-2">{{ u.id }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!usersLoading && !usersError && userItems.length === 0" class="text-content-muted">No users found.</p>
        <p v-if="selectedUserIds.size > 0" class="text-sm text-content-muted">{{ selectedUserIds.size }} user(s) selected.</p>
      </section>

      <!-- Per location: paginated location list with checkboxes -->
      <section v-if="scope === 'location'" class="space-y-3 rounded-lg border border-edge bg-surface p-4">
        <h2 class="text-lg font-semibold text-content">Select locations</h2>
        <input
          v-model="locationSearch"
          type="search"
          placeholder="Filter by name or ID…"
          class="w-full max-w-md rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          @input="debouncedLoadLocations"
        />
        <div class="flex flex-wrap items-center gap-4 text-sm text-content-muted">
          <label class="flex items-center gap-2">
            <span>Show</span>
            <select
              v-model.number="locationPageSize"
              class="rounded bg-surface border border-edge text-content px-2 py-1 focus:border-secondary focus:outline-none"
              @change="loadLocations"
            >
              <option v-for="n in pageSizeOptions" :key="n" :value="n">{{ n }}</option>
            </select>
            <span>per page</span>
          </label>
          <span v-if="locationTotalPages > 1" class="flex items-center gap-2">
            <button
              type="button"
              :disabled="locationPage <= 1"
              class="rounded px-2 py-1 text-primary hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
              @click="locationPage = Math.max(1, locationPage - 1); loadLocations()"
            >
              Previous
            </button>
            <span>Page {{ locationPage }} of {{ locationTotalPages }}</span>
            <button
              type="button"
              :disabled="locationPage >= locationTotalPages"
              class="rounded px-2 py-1 text-primary hover:bg-surface disabled:opacity-50 disabled:cursor-not-allowed"
              @click="locationPage = Math.min(locationTotalPages, locationPage + 1); loadLocations()"
            >
              Next
            </button>
          </span>
        </div>
        <p v-if="locationsLoading" class="flex items-center gap-2 text-content-muted">
          <span class="inline-block h-3 w-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span>Loading locations…</span>
        </p>
        <p v-else-if="locationsError" class="text-red-500">{{ locationsError }}</p>
        <div v-else class="overflow-x-auto rounded-lg border border-edge">
          <table class="w-full text-sm text-left">
            <thead class="bg-surface text-content">
              <tr>
                <th class="px-4 py-2 w-10">
                  <input
                    type="checkbox"
                    :checked="allLocationsOnPageSelected"
                    :indeterminate="someLocationsOnPageSelected && !allLocationsOnPageSelected"
                    class="rounded border-edge text-primary"
                    @change="toggleAllLocationsOnPage"
                  />
                </th>
                <th class="px-4 py-2">Name</th>
                <th class="px-4 py-2">ID</th>
              </tr>
            </thead>
            <tbody class="text-content">
              <tr
                v-for="loc in locationItems"
                :key="loc.id"
                class="border-t border-edge hover:bg-surface"
              >
                <td class="px-4 py-2">
                  <input
                    type="checkbox"
                    :checked="selectedLocationIds.has(String(loc.id))"
                    class="rounded border-edge text-primary"
                    @change="toggleLocation(loc.id)"
                  />
                </td>
                <td class="px-4 py-2">{{ loc.name || '—' }}</td>
                <td class="px-4 py-2">{{ loc.id }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!locationsLoading && !locationsError && locationItems.length === 0" class="text-content-muted">No locations found.</p>
        <p v-if="selectedLocationIds.size > 0" class="text-sm text-content-muted">{{ selectedLocationIds.size }} location(s) selected.</p>
      </section>

      <!-- All users: no selection needed -->
      <section v-if="scope === 'all'" class="rounded-lg border border-edge bg-surface p-4">
        <p class="text-content-muted text-sm">Training data for all users will be included. Use course and date filters below to narrow results.</p>
      </section>

      <!-- Filters: courses + date range -->
      <section class="space-y-4 rounded-lg border border-edge bg-surface p-4">
        <h2 class="text-lg font-semibold text-content">Filters</h2>
        <div class="flex flex-wrap gap-6">
          <div class="min-w-[200px] space-y-1">
            <div class="flex items-center gap-2 justify-between">
              <label class="block text-sm font-medium text-content mb-1">Courses (optional)</label>
              <span v-if="coursesLoading" class="flex items-center gap-1 text-xs text-content-muted">
                <span class="inline-block h-3 w-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                <span>Loading…</span>
              </span>
            </div>
            <select
              v-model="selectedCourseIds"
              multiple
              :disabled="allCourses"
              class="w-full max-w-md rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none min-h-[80px] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option v-for="c in courses" :key="c.id" :value="String(c.id)">
                {{ c.name || c.id }}
              </option>
            </select>
            <div class="flex items-center justify-between mt-1">
              <label class="flex items-center gap-2 text-xs text-content">
                <input
                  v-model="allCourses"
                  type="checkbox"
                  class="rounded border-edge text-primary"
                />
                <span>All courses</span>
              </label>
              <p class="text-xs text-content-muted">
                When unchecked, select one or more courses (Ctrl/Cmd+click).
              </p>
            </div>
          </div>
          <div class="flex flex-wrap items-end gap-4">
            <div>
              <label class="block text-sm font-medium text-content mb-1">Start date</label>
              <input
                v-model="startDate"
                type="date"
                class="rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-content mb-1">End date</label>
              <input
                v-model="endDate"
                type="date"
                class="rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Columns -->
      <section class="space-y-3 rounded-lg border border-edge bg-surface p-4">
        <div class="flex items-center justify-between gap-3">
          <h2 class="text-lg font-semibold text-content">Columns</h2>
          <div class="flex items-center gap-2 text-xs">
            <button
              type="button"
              class="px-2 py-1 rounded border border-edge text-content hover:bg-surface"
              @click="selectAllColumns"
            >
              Select all
            </button>
            <button
              type="button"
              class="px-2 py-1 rounded border border-edge text-content hover:bg-surface"
              @click="clearAllColumns"
            >
              Clear
            </button>
          </div>
        </div>
        <p v-if="columnsLoading" class="flex items-center gap-2 text-content-muted text-sm">
          <span class="inline-block h-3 w-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span>Loading columns…</span>
        </p>
        <p v-else-if="columnsError" class="text-red-500 text-sm">{{ columnsError }}</p>
        <div v-else class="max-h-40 overflow-auto text-sm space-y-1">
          <label
            v-for="col in availableColumns"
            :key="col.key"
            class="flex items-center gap-2 cursor-pointer"
          >
            <input
              type="checkbox"
              :value="col.key"
              v-model="selectedColumns"
              class="rounded border-edge text-primary"
            />
            <span class="text-content">{{ col.label }}</span>
          </label>
        </div>
        <p v-if="selectedColumns.length === 0" class="text-xs text-red-500">
          Select at least one column to include in the CSV.
        </p>
      </section>

      <!-- Export action -->
      <div class="flex items-center gap-4">
        <button
          type="button"
          :disabled="exportDisabled || exportLoading"
          class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          @click="downloadCsv"
        >
          {{ exportLoading ? 'Preparing…' : 'Download CSV' }}
        </button>
        <p v-if="exportError" class="text-red-500 text-sm">{{ exportError }}</p>
        <p v-else-if="exportSuccess" class="text-green-500 text-sm">{{ exportSuccess }}</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const pageSizeOptions = [10, 25, 50, 100]

const hasCredentials = ref(false)
const scope = ref('')

// Users
const userItems = ref([])
const userTotal = ref(0)
const userPage = ref(1)
const userPageSize = ref(10)
const userSearch = ref('')
const usersLoading = ref(false)
const usersError = ref(null)
const selectedUserIds = ref(new Set())
const userStatus = ref('active')

// Locations
const locationItems = ref([])
const locationTotal = ref(0)
const locationPage = ref(1)
const locationPageSize = ref(10)
const locationSearch = ref('')
const locationsLoading = ref(false)
const locationsError = ref(null)
const selectedLocationIds = ref(new Set())

// Courses
const courses = ref([])
const coursesLoading = ref(false)
const selectedCourseIds = ref([])
const allCourses = ref(true)

// Date range
const startDate = ref('')
const endDate = ref('')

// Export
const exportLoading = ref(false)
const exportError = ref(null)
const exportSuccess = ref('')

// Columns
const availableColumns = ref([])
const selectedColumns = ref([])
const columnsLoading = ref(false)
const columnsError = ref(null)

const userTotalPages = computed(() =>
  Math.max(1, Math.ceil(userTotal.value / userPageSize.value))
)
const locationTotalPages = computed(() =>
  Math.max(1, Math.ceil(locationTotal.value / locationPageSize.value))
)

const allUsersOnPageSelected = computed(() => {
  if (userItems.value.length === 0) return false
  return userItems.value.every((u) => selectedUserIds.value.has(String(u.id)))
})
const someUsersOnPageSelected = computed(() =>
  userItems.value.some((u) => selectedUserIds.value.has(String(u.id)))
)
const allLocationsOnPageSelected = computed(() => {
  if (locationItems.value.length === 0) return false
  return locationItems.value.every((loc) => selectedLocationIds.value.has(String(loc.id)))
})
const someLocationsOnPageSelected = computed(() =>
  locationItems.value.some((loc) => selectedLocationIds.value.has(String(loc.id)))
)

const exportDisabled = computed(() => {
  if (scope.value === 'user' && selectedUserIds.value.size === 0) return true
  if (scope.value === 'location' && selectedLocationIds.value.size === 0) return true
  if (startDate.value && endDate.value && startDate.value > endDate.value) return true
  if (selectedColumns.value.length === 0) return true
  return false
})

function openCredentials() {
  router.replace({ path: route.path, query: { ...route.query, openCredentials: '1' } })
}

async function checkCredentials() {
  try {
    const res = await fetch('/api/session/credentials', { credentials: 'include' })
    const data = await res.json()
    hasCredentials.value = data.has_credentials === true
  } catch {
    hasCredentials.value = false
  }
}

function handleCredentialsSaved() {
  checkCredentials()
}

let userSearchTimeout = null
function debouncedLoadUsers() {
  if (userSearchTimeout) clearTimeout(userSearchTimeout)
  userSearchTimeout = setTimeout(() => {
    userPage.value = 1
    loadUsers()
  }, 300)
}

async function loadUsers() {
  if (scope.value !== 'user') return
  usersLoading.value = true
  usersError.value = null
  try {
    const params = new URLSearchParams({
      page: String(userPage.value),
      pageSize: String(userPageSize.value),
      status: userStatus.value || 'active',
    })
    if (userSearch.value.trim()) params.set('search', userSearch.value.trim())
    const res = await fetch(`/api/training/users?${params}`, { credentials: 'include' })
    if (res.status === 401) {
      usersError.value = 'No credentials in session.'
      return
    }
    if (res.status === 429) {
      usersError.value = 'Too many requests. Please wait a minute and try again.'
      return
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      usersError.value = d.detail || res.statusText
      return
    }
    const data = await res.json()
    userItems.value = data.items || []
    userTotal.value = data.total ?? 0
  } catch (e) {
    usersError.value = e.message || 'Request failed'
  } finally {
    usersLoading.value = false
  }
}

let locationSearchTimeout = null
function debouncedLoadLocations() {
  if (locationSearchTimeout) clearTimeout(locationSearchTimeout)
  locationSearchTimeout = setTimeout(() => {
    locationPage.value = 1
    loadLocations()
  }, 300)
}

async function loadLocations() {
  if (scope.value !== 'location') return
  locationsLoading.value = true
  locationsError.value = null
  try {
    const params = new URLSearchParams({ page: String(locationPage.value), pageSize: String(locationPageSize.value) })
    if (locationSearch.value.trim()) params.set('search', locationSearch.value.trim())
    const res = await fetch(`/api/training/locations?${params}`, { credentials: 'include' })
    if (res.status === 401) {
      locationsError.value = 'No credentials in session.'
      return
    }
    if (res.status === 429) {
      locationsError.value = 'Too many requests. Please wait a minute and try again.'
      return
    }
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      locationsError.value = d.detail || res.statusText
      return
    }
    const data = await res.json()
    locationItems.value = data.items || []
    locationTotal.value = data.total ?? 0
  } catch (e) {
    locationsError.value = e.message || 'Request failed'
  } finally {
    locationsLoading.value = false
  }
}

async function loadCourses() {
  coursesLoading.value = true
  try {
    const res = await fetch('/api/training/courses', { credentials: 'include' })
    if (!res.ok) return
    const data = await res.json()
    courses.value = data.courses || []
  } finally {
    coursesLoading.value = false
  }
}

async function ensureCoursesLoaded() {
  if (courses.value.length > 0 || coursesLoading.value) return
  await loadCourses()
}

async function loadColumns() {
  if (availableColumns.value.length > 0 || columnsLoading.value) return
  columnsLoading.value = true
  columnsError.value = null
  try {
    const res = await fetch('/api/training/export/columns', { credentials: 'include' })
    if (!res.ok) {
      columnsError.value = 'Could not load column definitions.'
      return
    }
    const data = await res.json()
    availableColumns.value = data.columns || []
    // Default selection: columns with default === true
    const defaults = availableColumns.value.filter((c) => c.default).map((c) => c.key)
    selectedColumns.value = defaults.length ? defaults : availableColumns.value.map((c) => c.key)
  } catch (e) {
    columnsError.value = e.message || 'Failed to load columns.'
  } finally {
    columnsLoading.value = false
  }
}

function toggleUser(id) {
  const next = new Set(selectedUserIds.value)
  const sid = String(id)
  if (next.has(sid)) next.delete(sid)
  else next.add(sid)
  selectedUserIds.value = next
}

function toggleAllUsersOnPage() {
  if (allUsersOnPageSelected.value) {
    const next = new Set(selectedUserIds.value)
    userItems.value.forEach((u) => next.delete(String(u.id)))
    selectedUserIds.value = next
  } else {
    const next = new Set(selectedUserIds.value)
    userItems.value.forEach((u) => next.add(String(u.id)))
    selectedUserIds.value = next
  }
}

function toggleLocation(id) {
  const next = new Set(selectedLocationIds.value)
  const sid = String(id)
  if (next.has(sid)) next.delete(sid)
  else next.add(sid)
  selectedLocationIds.value = next
}

function toggleAllLocationsOnPage() {
  if (allLocationsOnPageSelected.value) {
    const next = new Set(selectedLocationIds.value)
    locationItems.value.forEach((loc) => next.delete(String(loc.id)))
    selectedLocationIds.value = next
  } else {
    const next = new Set(selectedLocationIds.value)
    locationItems.value.forEach((loc) => next.add(String(loc.id)))
    selectedLocationIds.value = next
  }
}

function selectAllColumns() {
  selectedColumns.value = availableColumns.value.map((c) => c.key)
}

function clearAllColumns() {
  selectedColumns.value = []
}

async function downloadCsv() {
  if (exportDisabled.value || exportLoading.value) return
  exportError.value = null
  exportSuccess.value = ''
  exportLoading.value = true
  try {
    const body = {
      scope: scope.value,
      userIds: scope.value === 'user' ? Array.from(selectedUserIds.value) : [],
      locationIds: scope.value === 'location' ? Array.from(selectedLocationIds.value) : [],
      courseIds: !allCourses.value && selectedCourseIds.value.length ? selectedCourseIds.value : [],
      startDate: startDate.value || null,
      endDate: endDate.value || null,
      userStatus: userStatus.value || 'active',
      columns: selectedColumns.value.slice(),
    }
    const res = await fetch('/api/training/export/csv', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (res.status === 401) {
      exportError.value = 'No credentials in session.'
      return
    }
    if (res.status === 429) {
      exportError.value = 'Too many requests. Please wait a minute and try again.'
      return
    }
    if (res.status === 400) {
      const d = await res.json().catch(() => ({}))
      exportError.value = d.detail || 'Bad request'
      return
    }
    if (!res.ok) {
      exportError.value = res.statusText || 'Export failed'
      return
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const disposition = res.headers.get('Content-Disposition')
    const match = disposition && disposition.match(/filename="?([^";]+)"?/)
    a.download = match ? match[1] : 'training-export.csv'
    a.click()
    URL.revokeObjectURL(url)
    exportSuccess.value = 'CSV download started.'
  } catch (e) {
    exportError.value = e.message || 'Download failed'
  } finally {
    exportLoading.value = false
  }
}

watch(scope, (s) => {
  if (!s) return
  if (s === 'user') {
    ensureCoursesLoaded()
    loadColumns()
    loadUsers()
  } else if (s === 'location') {
    ensureCoursesLoaded()
    loadColumns()
    loadLocations()
  } else if (s === 'all') {
    ensureCoursesLoaded()
    loadColumns()
  }
})
watch(userPage, () => loadUsers())
watch(locationPage, () => loadLocations())
watch(userStatus, () => {
  if (scope.value === 'user') {
    userPage.value = 1
    loadUsers()
  }
})

onMounted(() => {
  checkCredentials()
  if (typeof window !== 'undefined') {
    window.addEventListener('lsvt-credentials-saved', handleCredentialsSaved)
  }
})

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('lsvt-credentials-saved', handleCredentialsSaved)
  }
})
</script>
