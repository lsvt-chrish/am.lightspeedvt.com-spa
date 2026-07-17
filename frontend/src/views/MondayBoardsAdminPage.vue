<template>
  <div class="w-full max-w-4xl space-y-6">
    <h1 class="text-2xl font-bold text-primary">Monday.com Board Config</h1>
    <p class="text-content-muted text-sm">
      Map each board's groups/statuses onto the four canonical buckets the ops dashboard charts on
      (open, pending, closed) or mark them <span class="text-content">excluded</span> to leave them out.
      Anything a board has produced that isn't classified yet shows up under "Unmapped values" below.
    </p>

    <p v-if="loading" class="text-content-muted">Loading&hellip;</p>
    <p v-else-if="error" class="text-red-500 text-sm">{{ error }}</p>

    <div class="rounded-lg border border-edge bg-surface p-4 space-y-3">
      <h2 class="text-sm font-semibold text-primary">Register a new board</h2>
      <div class="grid gap-2 sm:grid-cols-3">
        <input v-model="newBoard.board_id" placeholder="Board ID" class="rounded border border-edge bg-page text-content px-2 py-1.5 text-sm" />
        <input v-model="newBoard.name" placeholder="Board name" class="rounded border border-edge bg-page text-content px-2 py-1.5 text-sm" />
        <input v-model="newBoard.department" placeholder="Department" class="rounded border border-edge bg-page text-content px-2 py-1.5 text-sm" />
      </div>
      <button
        type="button"
        class="px-3 py-1.5 rounded bg-secondary text-secondary-accent text-sm font-medium hover:opacity-90 disabled:opacity-50"
        :disabled="!canCreate"
        @click="createBoard"
      >
        Add board
      </button>
    </div>

    <div v-for="board in boards" :key="board.board_id" class="rounded-lg border border-edge bg-surface p-4 space-y-4">
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div class="flex items-center gap-2 flex-wrap">
          <input
            v-model="board.name"
            class="rounded border border-edge bg-page text-primary font-semibold px-2 py-1 text-lg w-64"
            placeholder="Board name"
          />
          <input
            v-model="board.department"
            class="rounded border border-edge bg-page text-content px-2 py-1 text-sm w-40"
            placeholder="Department"
          />
          <span class="text-xs text-content-muted">board_id {{ board.board_id }}</span>
        </div>
        <button
          type="button"
          class="px-3 py-1.5 rounded bg-secondary text-secondary-accent text-sm font-medium hover:opacity-90 disabled:opacity-50"
          :disabled="saving[board.board_id]"
          @click="save(board)"
        >
          {{ saving[board.board_id] ? 'Saving…' : 'Save' }}
        </button>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <div>
          <h3 class="text-xs uppercase tracking-wide text-content-muted mb-2">Groups</h3>
          <div class="space-y-1">
            <div v-for="key in Object.keys(board.bucket_map.groups)" :key="key" class="flex items-center gap-2 text-sm">
              <span class="flex-1 text-content truncate" :title="key">{{ key }}</span>
              <select v-model="board.bucket_map.groups[key]" class="rounded border border-edge bg-page text-content px-2 py-1 text-sm">
                <option v-for="b in BUCKET_OPTIONS" :key="b" :value="b">{{ b }}</option>
              </select>
            </div>
            <p v-if="Object.keys(board.bucket_map.groups).length === 0" class="text-xs text-content-muted">None mapped yet.</p>
          </div>
        </div>

        <div>
          <h3 class="text-xs uppercase tracking-wide text-content-muted mb-2">Statuses</h3>
          <div class="space-y-1">
            <div v-for="key in Object.keys(board.bucket_map.statuses)" :key="key" class="flex items-center gap-2 text-sm">
              <span class="flex-1 text-content truncate" :title="key">{{ key }}</span>
              <select v-model="board.bucket_map.statuses[key]" class="rounded border border-edge bg-page text-content px-2 py-1 text-sm">
                <option v-for="b in BUCKET_OPTIONS" :key="b" :value="b">{{ b }}</option>
              </select>
            </div>
            <p v-if="Object.keys(board.bucket_map.statuses).length === 0" class="text-xs text-content-muted">None mapped yet.</p>
          </div>
        </div>
      </div>

      <div>
        <h3 class="text-xs uppercase tracking-wide text-content-muted mb-2">Unmapped values</h3>
        <p v-if="!unmapped[board.board_id] || unmapped[board.board_id].length === 0" class="text-xs text-content-muted">
          Nothing unmapped &mdash; every group/status this board has produced is classified.
        </p>
        <div v-else class="space-y-1">
          <div
            v-for="u in unmapped[board.board_id]"
            :key="`${u.kind}:${u.value}`"
            class="flex items-center gap-2 text-sm"
          >
            <span class="text-xs rounded bg-page border border-edge px-1.5 py-0.5 text-content-muted">{{ u.kind }}</span>
            <span class="flex-1 text-content truncate" :title="u.value">{{ u.value }}</span>
            <span class="text-xs text-content-muted">{{ u.count }}x &middot; last {{ formatDate(u.last_seen) }}</span>
            <select
              class="rounded border border-edge bg-page text-content px-2 py-1 text-sm"
              @change="assignUnmapped(board, u, $event.target.value)"
            >
              <option value="" disabled selected>assign&hellip;</option>
              <option v-for="b in BUCKET_OPTIONS" :key="b" :value="b">{{ b }}</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'

const BUCKET_OPTIONS = ['open', 'pending', 'closed', 'excluded']

const boards = ref([])
const unmapped = reactive({})
const saving = reactive({})
const loading = ref(true)
const error = ref(null)

const newBoard = ref({ board_id: '', name: '', department: '' })
const canCreate = computed(() => !!(newBoard.value.board_id && newBoard.value.name && newBoard.value.department))

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

async function loadUnmapped(boardId) {
  try {
    const r = await fetch(`/api/monday/boards/${encodeURIComponent(boardId)}/unmapped`, { credentials: 'include' })
    if (!r.ok) return
    unmapped[boardId] = await r.json()
  } catch {
    unmapped[boardId] = []
  }
}

async function loadBoards() {
  loading.value = true
  error.value = null
  try {
    const res = await fetch('/api/monday/boards', { credentials: 'include' })
    if (!res.ok) throw new Error(res.statusText)
    boards.value = await res.json()
    await Promise.all(boards.value.map((b) => loadUnmapped(b.board_id)))
  } catch (e) {
    error.value = e.message || 'Failed to load boards'
  } finally {
    loading.value = false
  }
}

async function save(board) {
  saving[board.board_id] = true
  try {
    const res = await fetch(`/api/monday/boards/${encodeURIComponent(board.board_id)}`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(board),
    })
    if (!res.ok) throw new Error(res.statusText)
    await loadUnmapped(board.board_id)
  } catch (e) {
    error.value = e.message || 'Failed to save board'
  } finally {
    saving[board.board_id] = false
  }
}

function assignUnmapped(board, unmappedValue, bucket) {
  if (!bucket) return
  const target = unmappedValue.kind === 'group' ? board.bucket_map.groups : board.bucket_map.statuses
  target[unmappedValue.value] = bucket
}

async function createBoard() {
  const { board_id, name, department } = newBoard.value
  if (!board_id || !name || !department) return
  try {
    const res = await fetch(`/api/monday/boards/${encodeURIComponent(board_id)}`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ board_id, name, department, bucket_map: { groups: {}, statuses: {} } }),
    })
    if (!res.ok) throw new Error(res.statusText)
    newBoard.value = { board_id: '', name: '', department: '' }
    await loadBoards()
  } catch (e) {
    error.value = e.message || 'Failed to create board'
  }
}

onMounted(loadBoards)
</script>
