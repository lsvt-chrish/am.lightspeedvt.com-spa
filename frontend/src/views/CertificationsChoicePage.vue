<template>
  <div class="w-full max-w-2xl space-y-6">
    <h1 class="text-2xl font-bold text-primary">Certifications</h1>
    <p class="text-content-muted text-sm">
      Explore LightSpeed VT certifications and completion status. Choose how you want to view the data.
    </p>

    <div v-if="!hasCredentials" class="rounded-lg bg-surface border border-edge p-4">
      <p class="text-content mb-2">API credentials are required to use certifications.</p>
      <button
        type="button"
        class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90"
        @click="openCredentials"
      >
        Open Credentials
      </button>
    </div>

    <div v-else class="grid gap-4 sm:grid-cols-2">
      <router-link
        to="/certifications/by-certification"
        class="block rounded-lg border border-edge bg-surface p-5 text-left transition-colors hover:border-secondary"
      >
        <h2 class="text-lg font-semibold text-primary">View users for a certification</h2>
        <p class="mt-1 text-sm text-content-muted">Who has completed certification X?</p>
      </router-link>
      <router-link
        to="/certifications/by-user"
        class="block rounded-lg border border-edge bg-surface p-5 text-left transition-colors hover:border-secondary"
      >
        <h2 class="text-lg font-semibold text-primary">View certifications for a user</h2>
        <p class="mt-1 text-sm text-content-muted">What certifications has user Y completed?</p>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const hasCredentials = ref(false)

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

onMounted(checkCredentials)
</script>
