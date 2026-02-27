<template>
  <div class="min-h-screen bg-page text-content flex">
    <aside class="w-56 shrink-0 border-r border-edge flex flex-col p-4 gap-1">
      <router-link
        to="/"
        class="rounded-lg px-3 py-2 text-primary hover:bg-surface transition-colors"
        exact-active-class="bg-surface text-primary"
      >
        Home
      </router-link>
      <button
        type="button"
        class="rounded-lg px-3 py-2 text-left text-primary hover:bg-surface transition-colors"
        @click="credentialsOpen = true"
      >
        Credentials
      </button>
      <router-link
        to="/link-builder"
        class="rounded-lg px-3 py-2 text-primary hover:bg-surface transition-colors"
        exact-active-class="bg-surface text-primary"
      >
        Link Builder
      </router-link>
      <router-link
        to="/scan"
        class="rounded-lg px-3 py-2 text-primary hover:bg-surface transition-colors"
        exact-active-class="bg-surface text-primary"
      >
        Interactive Video Scanner
      </router-link>
      <router-link
        to="/certifications"
        class="rounded-lg px-3 py-2 text-primary hover:bg-surface transition-colors"
        active-class="bg-surface text-primary"
      >
        Certifications
      </router-link>
      <button
        type="button"
        class="mt-auto rounded-lg px-3 py-2 text-content-muted hover:bg-surface transition-colors flex items-center gap-2 w-full text-left"
        :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
        @click.prevent.stop="toggleTheme"
      >
        <span v-if="isDark" aria-hidden="true">☀️</span>
        <span v-else aria-hidden="true">🌙</span>
        {{ isDark ? 'Light mode' : 'Dark mode' }}
      </button>
    </aside>
    <main class="flex-1 flex flex-col items-center justify-center p-8 min-w-0">
      <router-view />
    </main>

    <!-- Credentials drawer: follows user on every page -->
    <Teleport to="body">
      <Transition name="drawer">
        <div
          v-show="credentialsOpen"
          class="fixed inset-0 z-50 flex justify-end"
          aria-modal="true"
          role="dialog"
          aria-label="API credentials"
        >
          <div
            class="absolute inset-0 bg-black/50"
            aria-hidden="true"
            @click="credentialsOpen = false"
          />
          <div
            class="relative w-full max-w-md bg-page border-l border-edge shadow-xl flex flex-col overflow-hidden"
          >
            <div class="p-4 overflow-auto">
              <CredentialsPanel show-close @close="credentialsOpen = false" />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CredentialsPanel from './components/CredentialsPanel.vue'
import { useTheme } from './composables/useTheme'

const { isDark, setTheme } = useTheme()
const credentialsOpen = ref(false)

function toggleTheme() {
  setTheme(isDark.value ? 'light' : 'dark')
}
const route = useRoute()
const router = useRouter()

watch(
  () => route.query.openCredentials,
  (val) => {
    if (val) {
      credentialsOpen.value = true
      router.replace({ path: route.path, query: { ...route.query, openCredentials: undefined } })
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.2s ease;
}
.drawer-enter-active .relative,
.drawer-leave-active .relative {
  transition: transform 0.25s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from .relative,
.drawer-leave-to .relative {
  transform: translateX(100%);
}
</style>
