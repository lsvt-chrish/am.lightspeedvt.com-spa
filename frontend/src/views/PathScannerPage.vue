<template>
  <div class="w-full max-w-lg space-y-6">
    <h1 class="text-2xl font-bold text-primary">Interactive Video Scanner</h1>

    <form class="space-y-4" @submit.prevent="scan">
      <div>
        <label for="json_url" class="block text-sm font-medium text-content mb-1">JSON URL</label>
        <input
          id="json_url"
          v-model="jsonUrl"
          type="url"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="https://lsvt-courseware.s3.amazonaws.com/files/121/interactiveFiles/ultimate_vapor_app_screener_july_2024_b_BDF7.json"
        />
      </div>
      <button
        type="submit"
        :disabled="loading"
        class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50"
      >
        {{ loading ? 'Scanning…' : 'Scan' }}
      </button>
    </form>

    <p v-if="error" class="text-red-400">{{ error }}</p>

    <div v-if="result" class="space-y-3 pt-4 border-t border-edge">
      <h2 class="text-lg font-semibold text-content">Results</h2>
      <dl class="grid gap-2 text-sm">
        <div class="flex justify-between gap-4 items-center">
          <dt class="text-content-muted">Total duration (all segments)</dt>
          <dd
            class="text-content font-medium cursor-pointer hover:text-secondary hover:underline select-all"
            title="Click to copy"
            @click="copyTime(formatSec(result.total_segment_duration_seconds))"
          >
            {{ formatSec(result.total_segment_duration_seconds) }} ({{ result.total_segment_duration_seconds }}s)
            <span v-if="copied === 'total'" class="text-secondary text-xs ml-1">Copied!</span>
          </dd>
        </div>
        <div class="flex justify-between gap-4 items-center">
          <dt class="text-content-muted">Total segments</dt>
          <dd class="text-content font-medium">{{ result.total_segments }}</dd>
        </div>
        <div class="flex justify-between gap-4 items-center">
          <dt class="text-content-muted">Total paths</dt>
          <dd class="text-content font-medium">{{ result.total_paths }}</dd>
        </div>
        <div class="flex justify-between gap-4 items-center">
          <dt class="text-content-muted">Shortest path</dt>
          <dd
            class="text-content font-medium cursor-pointer hover:text-secondary hover:underline select-all"
            title="Click to copy"
            @click="copyTime(result.shortest_path_duration_display, 'shortest')"
          >
            {{ result.shortest_path_duration_display }} ({{ result.shortest_path_seconds }}s)
            <span v-if="copied === 'shortest'" class="text-secondary text-xs ml-1">Copied!</span>
          </dd>
        </div>
        <div class="flex justify-between gap-4 items-center">
          <dt class="text-content-muted">Longest path</dt>
          <dd
            class="text-content font-medium cursor-pointer hover:text-secondary hover:underline select-all"
            title="Click to copy"
            @click="copyTime(result.longest_path_duration_display, 'longest')"
          >
            {{ result.longest_path_duration_display }} ({{ result.longest_path_seconds }}s)
            <span v-if="copied === 'longest'" class="text-secondary text-xs ml-1">Copied!</span>
          </dd>
        </div>
        <div class="flex justify-between gap-4 items-center">
          <dt class="text-content-muted">Average path</dt>
          <dd
            class="text-content font-medium cursor-pointer hover:text-secondary hover:underline select-all"
            title="Click to copy"
            @click="copyTime(result.average_path_duration_display, 'average')"
          >
            {{ result.average_path_duration_display }} ({{ result.average_path_seconds.toFixed(1) }}s)
            <span v-if="copied === 'average'" class="text-secondary text-xs ml-1">Copied!</span>
          </dd>
        </div>
      </dl>

      <div v-if="result.paths && result.paths.length" class="pt-4 border-t border-edge">
        <h3 class="text-base font-semibold text-content mb-2">Unique paths ({{ result.paths.length }})</h3>
        <p class="text-content-muted text-xs mb-2">Each path is one distinct segment sequence from start to end.</p>
        <ul class="space-y-2 text-sm">
          <li
            v-for="(path, idx) in result.paths"
            :key="idx"
            class="rounded bg-surface px-3 py-2 text-content space-y-0.5"
          >
            <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <span class="font-medium text-content">Path {{ idx + 1 }}</span>
              <span class="text-content-muted text-xs uppercase" :class="{ 'bg-green-500 text-white px-1 py-0.5 rounded-md': path.terminal_type === 'complete', 'bg-red-500 text-white px-1 py-0.5 rounded-md': path.terminal_type === 'redirect' }">{{ path.terminal_type || 'redirect' }}</span>
              <span class="text-primary dark:text-secondary-accent">{{ formatSec(path.duration_seconds) }}</span>
            </div>
            <div class="text-content-muted text-xs">Segments: {{ path.segment_ids.join(' → ') }}</div>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const jsonUrl = ref('')
const loading = ref(false)
const error = ref(null)
const result = ref(null)
const copied = ref(null)
let copyTimeout = null

function formatSec(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function copyTime(text, key = 'total') {
  if (copyTimeout) clearTimeout(copyTimeout)
  navigator.clipboard.writeText(text).then(() => {
    copied.value = key
    copyTimeout = setTimeout(() => { copied.value = null }, 2000)
  }).catch(() => {})
}

async function scan() {
  loading.value = true
  error.value = null
  result.value = null
  try {
    const res = await fetch('/api/scan/paths', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ json_url: jsonUrl.value }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      const detail = data.detail
      const msg = Array.isArray(detail) ? detail.map((d) => d.msg || d.message).join(', ') : (detail || res.statusText || 'Scan failed')
      error.value = res.status === 404
        ? 'Scan endpoint not found (404). Rebuild the backend image and ensure the server is up to date.'
        : msg
      return
    }
    result.value = data
  } catch (e) {
    error.value = e.message || 'Failed to scan'
  } finally {
    loading.value = false
  }
}
</script>
