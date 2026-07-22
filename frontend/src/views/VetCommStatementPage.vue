<template>
  <div id="form" class="w-full max-w-2xl space-y-6">
    <h1 class="text-2xl font-bold text-primary">VetComm Statement Generator</h1>
    <p class="text-content-muted text-sm">
      Enter the veteran's condition and claim details to generate a VA-ready personal statement.
    </p>

    <div v-if="errorMessage" class="rounded border border-red-400/50 bg-red-400/10 px-3 py-2 text-sm text-red-400">
      {{ errorMessage }}
      <ul v-if="missingFields.length" class="mt-1 list-disc list-inside">
        <li v-for="f in missingFields" :key="f">{{ f }}</li>
      </ul>
    </div>

    <div v-if="!statement" class="space-y-4">
      <div>
        <label class="block text-sm font-medium text-content mb-1">Condition name</label>
        <input
          v-model="form.condition.name"
          type="text"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="Right knee strain"
        />
      </div>

      <div>
        <label class="block text-sm font-medium text-content mb-1">Category</label>
        <select
          v-model="form.condition.category"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
        >
          <option value="" disabled>Select a category</option>
          <option v-for="c in categories" :key="c" :value="c">{{ formatLabel(c) }}</option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium text-content mb-1">Claim path</label>
        <select
          v-model="form.condition.claim_path"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
        >
          <option value="" disabled>Select a claim path</option>
          <option v-for="p in claimPaths" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>

      <div>
        <label class="block text-sm font-medium text-content mb-1">In-service cause</label>
        <textarea
          v-model="form.veteran_input.in_service_cause"
          rows="3"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="What was the veteran doing during service that caused this?"
        ></textarea>
      </div>

      <div>
        <label class="block text-sm font-medium text-content mb-1">What developed</label>
        <textarea
          v-model="form.veteran_input.what_developed"
          rows="3"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="What symptom or condition emerged, when, and how it progressed."
        ></textarea>
      </div>

      <div>
        <label class="block text-sm font-medium text-content mb-1">
          Medical care during service <span class="text-content-muted">(optional)</span>
        </label>
        <textarea
          v-model="form.veteran_input.medical_care_during_service"
          rows="2"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="Whether they got medical care during service and what it was."
        ></textarea>
      </div>

      <div>
        <label class="block text-sm font-medium text-content mb-1">Current impact</label>
        <textarea
          v-model="form.veteran_input.current_impact"
          rows="3"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="How the condition affects them today."
        ></textarea>
      </div>

      <button
        type="button"
        :disabled="submitting || !canSubmit"
        class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50"
        @click="submit"
      >
        {{ submitting ? 'Generating...' : 'Generate statement' }}
      </button>
    </div>

    <div v-else class="space-y-4">
      <div>
        <label class="block text-sm font-medium text-content mb-1">Generated statement</label>
        <textarea
          :value="statement"
          readonly
          rows="6"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 text-sm"
        ></textarea>
        <p class="mt-1 text-content-muted text-xs">
          {{ characterCount }} characters &middot; attempt {{ attemptNumber }} of 5
        </p>
        <button
          type="button"
          class="mt-2 px-4 py-2 rounded border border-edge text-content font-medium hover:opacity-90"
          @click="copyStatement"
        >
          {{ copied ? 'Copied!' : 'Copy' }}
        </button>
      </div>

      <div v-if="attemptNumber < 5" class="space-y-2">
        <label class="block text-sm font-medium text-content mb-1">Feedback for regeneration</label>
        <textarea
          v-model="feedback"
          rows="2"
          class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
          placeholder="Add that the pain is worse in cold weather. Remove the part about ibuprofen."
        ></textarea>
        <button
          type="button"
          :disabled="submitting || !feedback.trim()"
          class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50"
          @click="regenerate"
        >
          {{ submitting ? 'Regenerating...' : 'Regenerate' }}
        </button>
      </div>
      <p v-else class="text-content-muted text-sm">Maximum of 5 attempts reached for this condition.</p>

      <button
        type="button"
        class="px-4 py-2 rounded border border-edge text-content font-medium hover:opacity-90"
        @click="startOver"
      >
        Start over
      </button>
    </div>
  </div>
</template>

<style scoped>
#form{
    background: #fff;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, .08);
}
</style>

<script setup>
import { computed, reactive, ref } from 'vue'

const categories = [
  'hearing_loss', 'tinnitus', 'ptsd', 'mst', 'depression_anxiety', 'tbi',
  'sleep_apnea', 'foot', 'ankle', 'knee', 'hip', 'back_spine', 'shoulder',
  'nerve_damage', 'heart', 'hypertension', 'sinusitis_rhinitis', 'asthma',
  'gerd', 'migraine', 'other',
]

const claimPaths = ['new', 'increase', 'supplemental', 'secondary']

const form = reactive({
  condition: { name: '', category: '', claim_path: '' },
  veteran_input: {
    in_service_cause: '',
    what_developed: '',
    medical_care_during_service: '',
    current_impact: '',
  },
})

const submitting = ref(false)
const errorMessage = ref('')
const missingFields = ref([])
const statement = ref('')
const characterCount = ref(0)
const attemptNumber = ref(1)
const feedback = ref('')
const copied = ref(false)

function formatLabel(str) {
  return str
    .replace(/_/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase());
}

const canSubmit = computed(() =>
  form.condition.name.trim() &&
  form.condition.category &&
  form.condition.claim_path &&
  form.veteran_input.in_service_cause.trim() &&
  form.veteran_input.what_developed.trim() &&
  form.veteran_input.current_impact.trim()
)

async function callApi(body) {
  errorMessage.value = ''
  missingFields.value = []
  submitting.value = true
  try {
    const res = await fetch('/api/vetcomm/statements', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    if (!res.ok) {
      const detail = data.detail || {}
      errorMessage.value = detail.message || 'Failed to generate statement.'
      missingFields.value = detail.required_fields_missing || []
      return
    }
    statement.value = data.statement
    characterCount.value = data.character_count
    attemptNumber.value = data.attempt_number
    feedback.value = ''
    copied.value = false
  } catch (e) {
    errorMessage.value = 'Network error contacting the server.'
  } finally {
    submitting.value = false
  }
}

function submit() {
  callApi({
    condition: { ...form.condition },
    veteran_input: { ...form.veteran_input },
    regeneration: null,
  })
}

function regenerate() {
  callApi({
    condition: { ...form.condition },
    veteran_input: { ...form.veteran_input },
    regeneration: {
      previous_statement: statement.value,
      veteran_feedback: feedback.value,
      attempt_number: attemptNumber.value + 1,
    },
  })
}

function startOver() {
  statement.value = ''
  characterCount.value = 0
  attemptNumber.value = 1
  feedback.value = ''
  errorMessage.value = ''
  missingFields.value = []
  copied.value = false
}

async function copyStatement() {
  try {
    await navigator.clipboard.writeText(statement.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch (e) {
    errorMessage.value = 'Could not copy to clipboard.'
  }
}
</script>
