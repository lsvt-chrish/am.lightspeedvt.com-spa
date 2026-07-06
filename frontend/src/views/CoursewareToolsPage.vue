<template>
  <div class="w-full max-w-2xl space-y-6">
    <h1 class="text-2xl font-bold text-primary">Courseware Tools</h1>
    <p class="text-content-muted text-sm">
      Utilities that inspect and analyze LightSpeed VT courseware content.
    </p>

    <div class="grid gap-4 sm:grid-cols-2">
      <router-link
        to="/courseware-tools/scan"
        class="block rounded-lg border border-edge bg-surface p-5 text-left transition-colors hover:border-secondary"
      >
        <h2 class="text-lg font-semibold text-primary">Interactive Video Scanner</h2>
        <p class="mt-1 text-sm text-content-muted">
          Enumerate every user path through an interactive video and report segment and path durations.
        </p>
      </router-link>
    </div>
  </div>
</template>

<script setup></script>
