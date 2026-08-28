<template>
  <div id="form" class="container-fluid">
    <div v-if="loadingInitial" class="loading-overlay">
      <div class="spinner" role="status" aria-label="Loading"></div>
    </div>

    <h1 class="h3 fw-bold" style="color: var(--primary-color)">VetComm Statement Generator</h1>
    <p class="text-muted small">
      Enter the veteran's condition and claim details to generate a VA-ready personal statement.
      Fields marked <span class="text-danger">*</span> are required.
    </p>

    <div
      v-if="errorMessage"
      ref="errorBanner"
      class="alert alert-danger"
      role="alert"
    >
      {{ errorMessage }}
      <ul v-if="missingFields.length" class="mb-0 mt-1">
        <li v-for="f in missingFields" :key="f">{{ f }}</li>
      </ul>
    </div>

    <form v-show="!statement" @submit.prevent="submit">
      <div data-field="name" :class="groupClass('name')">
        <input
          v-model="form.condition.name"
          type="text"
          class="form__control"
          placeholder=" "
        />
        <label class="form__label">Condition name <span class="text-danger">*</span></label>
      </div>

      <div data-field="category" :class="groupClass('category')">
        <select ref="categorySelect" v-model="form.condition.category" class="form__control">
          <option value="" disabled>Select a category</option>
          <option v-for="c in categories" :key="c" :value="c">{{ formatLabel(c) }}</option>
        </select>
        <label class="form__label">Category <span class="text-danger">*</span></label>
      </div>

      <div data-field="claim_path" :class="groupClass('claim_path')">
        <select ref="claimPathSelect" v-model="form.condition.claim_path" class="form__control">
          <option value="" disabled>Select a claim path</option>
          <option v-for="p in claimPaths" :key="p" :value="p">{{ formatLabel(p) }}</option>
        </select>
        <label class="form__label">Claim path <span class="text-danger">*</span></label>
      </div>

      <div data-field="branch_of_service" :class="groupClass('branch_of_service')">
        <select
          ref="branchSelect"
          v-model="form.service_context.branch_of_service"
          class="form__control"
          multiple
        >
          <option v-for="b in branches" :key="b" :value="b">{{ b }}</option>
        </select>
        <label class="form__label">Branch of service <span class="text-danger">*</span></label>
        <p class="form__message text-muted small">
          Hold Ctrl (Windows) or Cmd (Mac) and click each branch you want. Ctrl/Cmd-click a selected branch again to remove it.
        </p>
      </div>

      <div data-field="mos" :class="groupClass('mos')">
        <input
          v-model="form.service_context.mos"
          type="text"
          class="form__control"
          placeholder=" "
        />
        <label class="form__label">MOS / Rate / AFSC <span class="text-danger">*</span></label>
      </div>

      <div
        v-if="form.condition.claim_path !== 'secondary'"
        data-field="happened_on_deployment"
        :class="groupClass('happened_on_deployment')"
      >
        <select v-model="happenedOnDeployment" class="form__control">
          <option value="" disabled>Select an answer</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
        <label class="form__label">Did this happen on a deployment? <span class="text-danger">*</span></label>
      </div>

      <div
        v-if="form.condition.claim_path !== 'secondary' && happenedOnDeployment === 'yes'"
        data-field="combat_deployment"
        :class="groupClass('combat_deployment')"
      >
        <select v-model="combatDeployment" class="form__control">
          <option value="" disabled>Select an answer</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
        <label class="form__label">Was that a combat deployment? <span class="text-danger">*</span></label>
      </div>

      <div data-field="in_service_cause" :class="groupClass('in_service_cause')">
        <textarea
          v-model="form.veteran_input.in_service_cause"
          rows="3"
          class="form__control"
          placeholder=" "
        ></textarea>
        <label class="form__label">In-service cause <span class="text-danger">*</span></label>
        <p class="form__message text-muted small">
          What was the veteran doing during service that caused this?
        </p>
      </div>

      <div data-field="what_developed" :class="groupClass('what_developed')">
        <textarea
          v-model="form.veteran_input.what_developed"
          rows="3"
          class="form__control"
          placeholder=" "
        ></textarea>
        <label class="form__label">What developed <span class="text-danger">*</span></label>
        <p class="form__message text-muted small">
          What symptom or condition emerged, when, and how it progressed.
        </p>
      </div>

      <div data-field="medical_care_during_service" :class="groupClass('medical_care_during_service')">
        <textarea
          v-model="form.veteran_input.medical_care_during_service"
          rows="2"
          class="form__control"
          placeholder=" "
        ></textarea>
        <label class="form__label">Medical care during service (optional)</label>
        <p class="form__message text-muted small">
          Whether they got medical care during service and what it was.
        </p>
      </div>

      <div data-field="current_impact" :class="groupClass('current_impact')">
        <textarea
          v-model="form.veteran_input.current_impact"
          rows="3"
          class="form__control"
          placeholder=" "
        ></textarea>
        <label class="form__label">Current impact <span class="text-danger">*</span></label>
        <p class="form__message text-muted small">How the condition affects them today.</p>
      </div>

      <button
        type="submit"
        :disabled="submitting"
        class="btn btn-secondary-brand fw-medium"
      >
        {{ submitting ? 'Generating...' : 'Generate statement' }}
      </button>
      <button
        v-if="wasAutofilled"
        type="button"
        :disabled="submitting"
        class="btn btn-outline-secondary fw-medium ms-2"
        @click="clearForm"
      >
        Clear form
      </button>
    </form>

    <div v-show="statement">
      <div class="form__group form__group--active form__group--hidden-label">
        <textarea
          :value="statement"
          readonly
          rows="6"
          class="form__control small"
        ></textarea>
        <p class="mt-1 text-muted small">
          {{ characterCount }} characters &middot; attempt {{ attemptNumber }} of 5
        </p>
        <button
          type="button"
          class="btn btn-outline-secondary mt-2"
          @click="copyStatement"
        >
          {{ copied ? 'Copied!' : 'Copy' }}
        </button>
        <button
          type="button"
          class="btn btn-outline-secondary mt-2 ms-2"
          :disabled="saving"
          @click="saveStatement"
        >
          {{ saving ? 'Saving...' : (saved ? 'Saved!' : 'Save for later') }}
        </button>
        <p v-if="saveError" class="mt-1 text-danger small">{{ saveError }}</p>
      </div>

      <div v-if="attemptNumber < 5" class="form__group form__group--active form__group--hidden-label">
        <textarea
          v-model="feedback"
          rows="2"
          class="form__control"
          placeholder="Add that the pain is worse in cold weather. Remove the part about ibuprofen."
        ></textarea>
        <button
          type="button"
          :disabled="submitting || !feedback.trim()"
          class="btn btn-secondary-brand fw-medium mt-2"
          @click="regenerate"
        >
          {{ submitting ? 'Regenerating...' : 'Regenerate' }}
        </button>
      </div>
      <p v-else class="text-muted small">Maximum of 5 attempts reached for this condition.</p>

      <button
        type="button"
        class="btn btn-outline-secondary"
        @click="startOver"
      >
        Start over
      </button>
    </div>
  </div>
</template>

<style scoped>
#form {
    position: relative;
    background: #fff;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, .08);
    width: 100%;
    max-width: 42rem;

    /* Page-scoped brand colors sourced from the LightSpeedVT theme CSS
       injected at runtime (see THEME_CSS_URLS below); safe fallbacks in case
       that stylesheet fails to load. */
    --primary-color: #082c4b;
    --primary-color-accent: #ffffff;
    --secondary-color: #ee232b;
    --secondary-color-accent: #ffffff;
}

#form .btn-secondary-brand {
    background-color: var(--secondary-color);
    color: var(--secondary-color-accent);
    border-color: var(--secondary-color);
}

#form .btn-secondary-brand:hover:not(:disabled) {
    opacity: .9;
    color: var(--secondary-color-accent);
}

#form .btn-secondary-brand:disabled {
    opacity: .5;
}

/* Covers the form/result content while we check for a saved statement to
   resume, without display:none-ing the underlying elements -- Select2 reads
   its target element's width when it initializes, which breaks if that
   element (or an ancestor) is display:none at the time. An overlay hides
   the flash of the wrong view without touching the layout underneath. */
#form .loading-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #fff;
    border-radius: 10px;
    z-index: 10;
}

#form .spinner {
    width: 2rem;
    height: 2rem;
    border: .25rem solid #dee2e6;
    border-top-color: var(--secondary-color);
    border-radius: 50%;
    animation: form-spin .7s linear infinite;
}

@keyframes form-spin {
    to { transform: rotate(360deg); }
}
</style>

<!--
  Unscoped on purpose: Select2 appends its open dropdown/results list to
  <body> (outside this component's DOM), so a `scoped` rule can never reach
  it. Without this, the floating `.form__label` (z-index: 1, see
  form-input.css) renders above the dropdown's option list while scrolling
  it, making selected/hovered text hard to read.
-->
<style>
.select2-dropdown {
    z-index: 2000;
}
</style>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import jQuery from 'jquery'
// `?url` gives us the built asset's final URL instead of importing the
// module as ESM. select2's dist file is an old-style UMD script that
// expects to run as a plain <script> tag, patching whatever `window.jQuery`
// it finds at that moment -- importing it as an ES module (even a dynamic
// one) lets the bundler resolve/duplicate its internal `require('jquery')`
// into a *different* module instance than the one we import and call
// `.select2()` on below, so the plugin silently attaches to the wrong
// object ("select2 is not a function" even though the chunk loaded fine).
// A real <script> tag, injected after window.jQuery is set (see
// loadSelect2Script in onMounted), sidesteps all of that: it's the exact
// mechanism the host page itself uses for its own plugins.
import select2ScriptUrl from 'select2/dist/js/select2.full.min.js?url'

// The host page (this is embedded into LightSpeedVT) already loads its own
// jQuery before this component ever mounts, so this assignment matters:
// select2 patches whatever window.jQuery is at the moment its script runs.
window.jQuery = window.$ = jQuery

let select2ScriptPromise = null
function loadSelect2Script() {
  if (jQuery.fn.select2) return Promise.resolve()
  if (!select2ScriptPromise) {
    select2ScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = select2ScriptUrl
      script.onload = resolve
      script.onerror = reject
      document.head.appendChild(script)
    })
  }
  return select2ScriptPromise
}

// LightSpeedVT host styles/scripts so this iframed page visually matches the
// parent app instead of this app's own Tailwind styling. Order matters for
// the stylesheets: style-guide base + form-select skin load first, then the
// site theme last so its brand colors/overrides win the cascade.
const THEME_CSS_URLS = [
  'https://static.lightspeedvt.com/style-guide/assets/main.e90ef0edf72154adbce3.css',
  'https://static.lightspeedvt.com/style-guide/assets/globals.5792cb6ee7379b46991a.css',
  'https://static.lightspeedvt.com/style-guide/assets/buttons.efbc44e50a0170455298.css',
  'https://static.lightspeedvt.com/style-guide/assets/alert.64e9874cd1c52527f0d4.css',
  'https://static.lightspeedvt.com/style-guide/assets/form-input.0c7f556d03b74cb1421f.css',
  'https://static.lightspeedvt.com/style-guide/assets/form-select.5448a98ddb8f7384920c.css',
  'https://static.lightspeedvt.com/style-guide/assets/form-select-jq.6e1e38bf1d282efe0986.css',
  'https://static.lightspeedvt.com/themer2-vt/5069/css/theme-4CAF754E-BC4B-5B07-7BA756E81A79072F.css',
]
let themeLinkEls = []

// This page is iframed into LightSpeed VT and must always render in light
// mode, independent of the embedding app's dark-mode class/localStorage
// preference or the visitor's OS setting (see useTheme.js, class-based).
let hadDarkClass = false

const categorySelect = ref(null)
const claimPathSelect = ref(null)
const branchSelect = ref(null)

// Wires up the real Select2 widget (same one the LightSpeedVT host uses,
// styled by form-select-jq.css) on a native <select>, keeping it in sync
// with the given Vue ref both ways.
function initSelect2(el, modelRef) {
  const $el = jQuery(el)
  $el.select2({ width: '100%', minimumResultsForSearch: Infinity })
  $el.on('change', () => { modelRef.value = $el.val() })
  return $el
}

let select2Instances = []

onMounted(async () => {
  hadDarkClass = document.documentElement.classList.contains('dark')
  document.documentElement.classList.remove('dark')
  document.body.classList.remove('dark')

  themeLinkEls = THEME_CSS_URLS.map(href => {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = href
    document.head.appendChild(link)
    return link
  })

  await loadSelect2Script()

  // Both the form and result views are always mounted now (v-show, not
  // v-if/v-else -- see hydrateSavedStatement()'s comment below for why), so
  // it's safe to bind Select2 here exactly once regardless of which view
  // ends up visible.
  select2Instances = [
    initSelect2(categorySelect.value, computed({
      get: () => form.condition.category,
      set: v => { form.condition.category = v },
    })),
    initSelect2(claimPathSelect.value, computed({
      get: () => form.condition.claim_path,
      set: v => { form.condition.claim_path = v },
    })),
    initSelect2(branchSelect.value, computed({
      get: () => form.service_context.branch_of_service,
      // jQuery .val() on a multi-select returns null (nothing selected) or
      // an array of selected values.
      set: v => { form.service_context.branch_of_service = v || [] },
    })),
  ]

  hydrateSavedStatement()
})

onUnmounted(() => {
  if (hadDarkClass) {
    document.documentElement.classList.add('dark')
    document.body.classList.add('dark')
  }
  themeLinkEls.forEach(link => link.remove())
  themeLinkEls = []
  select2Instances.forEach($el => $el.select2('destroy'))
  select2Instances = []
})

const categories = [
  'hearing_loss', 'tinnitus', 'ptsd', 'mst', 'depression_anxiety', 'tbi',
  'sleep_apnea', 'foot', 'ankle', 'knee', 'hip', 'back_spine', 'shoulder',
  'nerve_damage', 'heart', 'hypertension', 'sinusitis_rhinitis', 'asthma',
  'gerd', 'migraine', 'other',
]

const claimPaths = ['new', 'increase', 'supplemental', 'secondary']

// Exact strings VetComm expects for branch of service. Must match verbatim.
const branches = [
  'Air Force', 'Army', 'Coast Guard', 'Marine Corps', 'Merchant Marines',
  'National Guard', 'Navy', 'Space Force',
]

const form = reactive({
  condition: { name: '', category: '', claim_path: '' },
  service_context: { branch_of_service: [], mos: '' },
  veteran_input: {
    in_service_cause: '',
    what_developed: '',
    medical_care_during_service: '',
    current_impact: '',
  },
})

// happened_on_deployment / combat_deployment are booleans on the wire but
// driven by yes/no selects here; '' means "unanswered". Kept separate from
// `form` so clearing them on claim-path change doesn't fight the selects.
const happenedOnDeployment = ref('')
const combatDeployment = ref('')

// Secondary claims omit these fields entirely (see spec); reset them when
// the veteran switches to/from that claim path so a stale answer doesn't
// linger and get sent (or block submission) incorrectly.
watch(() => form.condition.claim_path, path => {
  if (path === 'secondary') {
    happenedOnDeployment.value = ''
    combatDeployment.value = ''
  }
})
watch(happenedOnDeployment, v => {
  if (v !== 'yes') combatDeployment.value = ''
})

// Keep the select2 widgets' displayed value in sync when the model changes
// from outside user interaction with the widget itself (e.g. startOver()).
watch(() => form.condition.category, v => categorySelect.value && jQuery(categorySelect.value).val(v).trigger('change.select2'))
watch(() => form.condition.claim_path, v => claimPathSelect.value && jQuery(claimPathSelect.value).val(v).trigger('change.select2'))
watch(() => form.service_context.branch_of_service, v => branchSelect.value && jQuery(branchSelect.value).val(v).trigger('change.select2'))

// True until the resume-on-load check (hydrateSavedStatement) finishes;
// covered by an overlay (not display:none -- see its CSS) rather than
// hiding the form/result content, since Select2 needs real layout to
// initialize against.
const loadingInitial = ref(true)
const submitting = ref(false)
const errorMessage = ref('')
const missingFields = ref([])
const statement = ref('')
const characterCount = ref(0)
const attemptNumber = ref(1)
const feedback = ref('')
const copied = ref(false)
const errorBanner = ref(null)
const saving = ref(false)
const saved = ref(false)
const saveError = ref('')
// The exact request body sent to /api/vetcomm/statements for the current
// `statement`, kept so Save-for-later can submit the full interaction
// (inputs + output), not just the generated text.
const lastRequest = ref(null)

// True once the form has been autofilled from a previously saved statement
// (see hydrateSavedStatement). Gates the "Clear form" button -- there's
// nothing meaningful to "clear" on a form the veteran is filling out fresh.
const wasAutofilled = ref(false)

// Reads a cookie set by the LightSpeedVT host page (this component is
// iframed into it, so it shares the same cookie jar/domain).
function readCookie(name) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : null
}

// On load, checks whether this veteran already has a saved statement and,
// if so, resumes straight into the result view with it instead of showing
// the blank form. Fails open to the blank form on any missing cookie,
// network error, or "nothing saved" response -- this is a convenience, not
// something that should ever block the page.
//
// Runs after Select2 is bound (see onMounted). `loadingInitial` covers the
// form/result content with an overlay (not display:none) while this runs,
// so there's no flash of the wrong view -- Select2 itself still measures
// real layout underneath, since the overlay doesn't hide the content, just
// visually covers it.
async function hydrateSavedStatement() {
  const userId = readCookie('LSVT_GUSERID')
  if (!userId) {
    loadingInitial.value = false
    return
  }
  try {
    const res = await fetch(`/api/vetcomm/statements/${encodeURIComponent(userId)}/latest`, {
      credentials: 'include',
    })
    if (!res.ok) return
    const data = await res.json()
    if (!data.found) return

    const req = data.request
    form.condition = { ...req.condition }
    form.service_context = {
      branch_of_service: [...(req.service_context?.branch_of_service || [])],
      mos: req.service_context?.mos || '',
    }
    form.veteran_input = {
      in_service_cause: req.veteran_input?.in_service_cause || '',
      what_developed: req.veteran_input?.what_developed || '',
      medical_care_during_service: req.veteran_input?.medical_care_during_service || '',
      current_impact: req.veteran_input?.current_impact || '',
    }
    happenedOnDeployment.value = req.veteran_input?.happened_on_deployment === true ? 'yes'
      : req.veteran_input?.happened_on_deployment === false ? 'no' : ''
    combatDeployment.value = req.veteran_input?.combat_deployment === true ? 'yes'
      : req.veteran_input?.combat_deployment === false ? 'no' : ''
    lastRequest.value = req
    wasAutofilled.value = true

    statement.value = data.statement
    characterCount.value = data.character_count
    attemptNumber.value = data.attempt_number
  } catch (e) {
    // Network error -- fall through to the blank form.
  } finally {
    loadingInitial.value = false
  }
}

function formatLabel(str) {
  return str
    .replace(/_/g, ' ')
    .replace(/\b\w/g, char => char.toUpperCase());
}

function isFieldMissing(key) {
  return missingFields.value.some(f => f === key || f.endsWith(`.${key}`))
}

// LightSpeedVT's floating-label form design: the wrapper carries the
// active/invalid state classes (see form-input.css), not the control itself.
function groupClass(key) {
  const classes = ['form__group', 'form__group--active']
  if (isFieldMissing(key)) classes.push('form__group--invalid')
  return classes
}

// Same order the fields appear in the form -- used both to build the
// missing-fields list and to find the *first* one to scroll to.
const FORM_FIELD_ORDER = [
  'name', 'category', 'claim_path', 'branch_of_service', 'mos',
  'happened_on_deployment', 'combat_deployment',
  'in_service_cause', 'what_developed', 'current_impact',
]

function getMissingFields() {
  const missing = []
  if (!form.condition.name.trim()) missing.push('name')
  if (!form.condition.category) missing.push('category')
  if (!form.condition.claim_path) missing.push('claim_path')
  if (form.service_context.branch_of_service.length === 0) missing.push('branch_of_service')
  if (!form.service_context.mos.trim()) missing.push('mos')
  if (form.condition.claim_path !== 'secondary') {
    if (!happenedOnDeployment.value) missing.push('happened_on_deployment')
    else if (happenedOnDeployment.value === 'yes' && !combatDeployment.value) missing.push('combat_deployment')
  }
  if (!form.veteran_input.in_service_cause.trim()) missing.push('in_service_cause')
  if (!form.veteran_input.what_developed.trim()) missing.push('what_developed')
  if (!form.veteran_input.current_impact.trim()) missing.push('current_impact')
  return missing
}

// Scrolls to the first invalid field (by form order, not necessarily the
// order the API/local validation reported them in), falling back to the
// error banner if none of the reported fields match a known one on screen.
async function scrollToFirstInvalidField() {
  await nextTick()
  const firstKey = FORM_FIELD_ORDER.find(isFieldMissing)
  const el = firstKey && document.querySelector(`#form [data-field="${firstKey}"]`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  } else {
    errorBanner.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

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
      await scrollToFirstInvalidField()
      return
    }
    statement.value = data.statement
    characterCount.value = data.character_count
    attemptNumber.value = data.attempt_number
    lastRequest.value = body
    feedback.value = ''
    copied.value = false
    saved.value = false
    saveError.value = ''
  } catch (e) {
    errorMessage.value = 'Network error contacting the server.'
    await nextTick()
    errorBanner.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } finally {
    submitting.value = false
  }
}

// Builds veteran_input, including happened_on_deployment/combat_deployment
// only when applicable per the spec (omitted entirely for secondary claims,
// combat_deployment omitted unless happened_on_deployment is true).
function buildVeteranInput() {
  const input = { ...form.veteran_input }
  if (form.condition.claim_path !== 'secondary') {
    input.happened_on_deployment = happenedOnDeployment.value === 'yes'
    if (happenedOnDeployment.value === 'yes') {
      input.combat_deployment = combatDeployment.value === 'yes'
    }
  }
  return input
}

function submit() {
  const missing = getMissingFields()
  if (missing.length) {
    errorMessage.value = 'Please complete all required fields.'
    missingFields.value = missing
    scrollToFirstInvalidField()
    return
  }
  callApi({
    condition: { ...form.condition },
    service_context: {
      branch_of_service: [...form.service_context.branch_of_service],
      mos: form.service_context.mos,
    },
    veteran_input: buildVeteranInput(),
    regeneration: null,
  })
}

function regenerate() {
  callApi({
    condition: { ...form.condition },
    service_context: {
      branch_of_service: [...form.service_context.branch_of_service],
      mos: form.service_context.mos,
    },
    veteran_input: buildVeteranInput(),
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
  saved.value = false
  saveError.value = ''
}

// (form fields themselves are intentionally left populated on startOver so
// a veteran can regenerate for a related condition without retyping everything)

// Explicit wipe of the form's answers -- unlike startOver(), which
// deliberately preserves them. Reassigning form.condition/service_context/
// veteran_input wholesale is enough to also reset the Select2 widgets: the
// existing watchers on those fields re-sync Select2's displayed value
// whenever they change.
function clearForm() {
  form.condition = { name: '', category: '', claim_path: '' }
  form.service_context = { branch_of_service: [], mos: '' }
  form.veteran_input = {
    in_service_cause: '',
    what_developed: '',
    medical_care_during_service: '',
    current_impact: '',
  }
  happenedOnDeployment.value = ''
  combatDeployment.value = ''
  errorMessage.value = ''
  missingFields.value = []
  lastRequest.value = null
  wasAutofilled.value = false
}

function copyWithExecCommand() {
  const textarea = document.createElement('textarea')
  textarea.value = statement.value
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch (e) {
    ok = false
  }
  document.body.removeChild(textarea)
  return ok
}

async function saveStatement() {
  saveError.value = ''
  saved.value = false
  const userId = readCookie('LSVT_GUSERID')
  if (!userId) {
    saveError.value = 'Could not identify the current user. Try reloading the page.'
    return
  }
  saving.value = true
  try {
    const res = await fetch('/api/vetcomm/statements/save', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        generated_at: new Date().toISOString(),
        // Full request/response pair so the whole interaction is stored,
        // not just the final statement text.
        request: lastRequest.value,
        statement: statement.value,
        character_count: characterCount.value,
        attempt_number: attemptNumber.value,
      }),
    })
    if (!res.ok) throw new Error('save failed')
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch (e) {
    saveError.value = 'Could not save the statement. Please try again.'
  } finally {
    saving.value = false
  }
}

async function copyStatement() {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(statement.value)
    } else if (!copyWithExecCommand()) {
      throw new Error('execCommand copy failed')
    }
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch (e) {
    // Clipboard API can be blocked by iframe permissions policy (this page is
    // meant to be iframed into LightSpeed VT); fall back to execCommand before
    // giving up.
    if (copyWithExecCommand()) {
      copied.value = true
      setTimeout(() => { copied.value = false }, 2000)
    } else {
      errorMessage.value = 'Could not copy to clipboard.'
    }
  }
}
</script>
