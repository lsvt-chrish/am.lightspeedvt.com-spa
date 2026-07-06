<template>
  <div class="w-full max-w-2xl space-y-6">
    <h1 class="text-2xl font-bold text-primary">Integration Tools</h1>
    <p class="text-content-muted text-sm">
      Helpers for connecting LightSpeed VT to external systems, landing pages, and attribution links.
    </p>

    <div class="grid gap-4 sm:grid-cols-2">
      <router-link
        to="/integration-tools/link-builder"
        class="block rounded-lg border border-edge bg-surface p-5 text-left transition-colors hover:border-secondary"
      >
        <h2 class="text-lg font-semibold text-primary">Attribute Link Builder</h2>
        <p class="mt-1 text-sm text-content-muted">
          Build a link that forwards LSVT user attributes to an external URL as query parameters.
        </p>
      </router-link>
    </div>
  </div>
</template>

<script setup></script>
