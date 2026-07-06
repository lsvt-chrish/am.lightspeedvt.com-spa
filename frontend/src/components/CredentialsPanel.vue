<template>
  <div class="w-full max-w-md space-y-6">
    <div class="flex items-center justify-between gap-4">
      <h2 class="text-xl font-bold text-primary">API credentials</h2>
      <button
        v-if="showClose"
        type="button"
        class="rounded p-1.5 text-content-muted hover:bg-surface hover:text-content transition-colors"
        aria-label="Close"
        @click="$emit('close')"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <p v-if="statusLoading" class="text-content-muted">Checking session…</p>
    <p v-else-if="hasCredentials" class="text-content">Credentials are saved in this session.</p>

    <form v-if="!statusLoading" class="space-y-4" @submit.prevent="save">
      <div>
        <label :for="inputId('api_key')" class="block text-sm font-medium text-content mb-1">API Key</label>
        <input
          :id="inputId('api_key')"
          v-model="apiKey"
          type="text"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="Your API key"
        />
      </div>
      <div>
        <label :for="inputId('api_secret')" class="block text-sm font-medium text-content mb-1">API Secret</label>
        <input
          :id="inputId('api_secret')"
          v-model="apiSecret"
          type="password"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="Your API secret"
        />
      </div>
      <div class="flex gap-3">
        <button
          type="submit"
          :disabled="saveLoading"
          class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50"
        >
          {{ saveLoading ? 'Saving…' : 'Save credentials' }}
        </button>
        <button
          v-if="hasCredentials"
          type="button"
          :disabled="clearLoading"
          class="px-4 py-2 rounded bg-default text-primary-accent font-medium hover:opacity-90 disabled:opacity-50"
          @click="clear"
        >
          {{ clearLoading ? 'Clearing…' : 'Clear credentials' }}
        </button>
      </div>
    </form>

    <p v-if="error" class="text-red-500">{{ error }}</p>
    <p v-if="success" class="text-secondary">{{ success }}</p>

    <!-- <div v-if="!statusLoading" class="pt-4 border-t border-slate-200 dark:border-slate-700">
      <button
        type="button"
        :disabled="dataLoading || !hasCredentials"
        class="px-4 py-2 rounded bg-slate-600 dark:bg-slate-700 text-slate-100 dark:text-slate-200 font-medium hover:bg-slate-500 dark:hover:bg-slate-600 disabled:opacity-50"
        @click="pullData"
      >
        {{ dataLoading ? 'Loading…' : 'Pull data' }}
      </button>
      <div v-if="data" class="mt-3 p-3 rounded bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-sm space-y-1">
        <p><span class="font-medium">System ID:</span> {{ data.system_id || '—' }}</p>
        <p><span class="font-medium">System name:</span> {{ data.system_name || '—' }}</p>
      </div>
    </div> -->
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

defineProps({
  showClose: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

const apiKey = ref('')
const apiSecret = ref('')
const hasCredentials = ref(false)
const statusLoading = ref(true)
const saveLoading = ref(false)
const clearLoading = ref(false)
const dataLoading = ref(false)
const error = ref(null)
const success = ref(null)
const data = ref(null)

const uid = Math.random().toString(36).slice(2, 9)
function inputId(name) {
  return `credentials-${uid}-${name}`
}

const api = (path, options = {}) => {
  const url = path.startsWith('/') ? `/api${path}` : `/api/${path}`
  return fetch(url, { credentials: 'include', ...options })
}

async function loadStatus() {
  statusLoading.value = true
  error.value = null
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 10000)
  try {
    const res = await api('/session/credentials', { signal: controller.signal })
    clearTimeout(timeoutId)
    if (!res.ok) throw new Error(res.statusText)
    const json = await res.json()
    hasCredentials.value = json.has_credentials === true
  } catch (e) {
    clearTimeout(timeoutId)
    if (e.name === 'AbortError') {
      error.value = 'Request timed out. Is the backend running at ' + (import.meta.env.VITE_API_TARGET || 'http://localhost:8000') + '?'
    } else {
      error.value = e.message || 'Failed to load status'
    }
  } finally {
    statusLoading.value = false
  }
}

async function save() {
  saveLoading.value = true
  error.value = null
  success.value = null
  try {
    const res = await api('/session/credentials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey.value, api_secret: apiSecret.value }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || res.statusText)
    }
    hasCredentials.value = true
    success.value = 'Credentials saved.'
    // Notify rest of app that credentials are now present
    if (typeof window !== 'undefined' && window.dispatchEvent) {
      window.dispatchEvent(new CustomEvent('lsvt-credentials-saved'))
    }
  } catch (e) {
    error.value = e.message || 'Failed to save'
  } finally {
    saveLoading.value = false
  }
}

async function clear() {
  clearLoading.value = true
  error.value = null
  success.value = null
  try {
    const res = await api('/session/credentials', { method: 'DELETE' })
    if (!res.ok) throw new Error(res.statusText)
    hasCredentials.value = false
    apiKey.value = ''
    apiSecret.value = ''
    data.value = null
    success.value = 'Credentials cleared.'
  } catch (e) {
    error.value = e.message || 'Failed to clear'
  } finally {
    clearLoading.value = false
  }
}

async function pullData() {
  dataLoading.value = true
  error.value = null
  data.value = null
  try {
    const res = await api('/session/data')
    if (res.status === 401) {
      error.value = 'No credentials in session. Save credentials first.'
      return
    }
    if (!res.ok) throw new Error(res.statusText)
    data.value = await res.json()
  } catch (e) {
    error.value = e.message || 'Failed to pull data'
  } finally {
    dataLoading.value = false
  }
}

onMounted(loadStatus)
</script>
