<template>
  <div class="flex flex-col items-center justify-center p-8">
    <h1 class="text-4xl font-bold text-primary mb-4">
      AM Lightspeed VT
    </h1>
    <p v-if="loading" class="text-content-muted">Loading…</p>
    <p v-else-if="error" class="text-red-500">{{ error }}</p>
    <p v-else-if="data" class="text-content">{{ data.message }}</p>
    <p class="text-content-muted mt-4 text-sm">Vue.js + Tailwind CSS frontend</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const data = ref(null)
const loading = ref(true)
const error = ref(null)

onMounted(async () => {
  try {
    const res = await fetch('/api', { credentials: 'include' })
    if (!res.ok) throw new Error(res.statusText)
    data.value = await res.json()
  } catch (e) {
    error.value = e.message || 'Failed to load from backend'
  } finally {
    loading.value = false
  }
})
</script>
