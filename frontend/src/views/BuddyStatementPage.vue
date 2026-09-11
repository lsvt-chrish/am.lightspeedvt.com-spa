<template>
  <div id="form" class="container-fluid">
    <h1 class="h3 fw-bold" style="color: var(--primary-color)">Buddy Statement Generator</h1>
    <p class="text-muted small">
      Statements from the people who know you strengthen your claim. Build them here.
    </p>

    <div class="why-panel">
      <div class="why-title"><span class="why-icon">!</span><span>Why buddy statements matter</span></div>
      <div class="why-body">
        <p>
          Buddy statements are written by people who know you personally: family, friends, or the
          folks you served with. They give the VA a picture your medical records cannot: what you
          were like before, what happened, and how your condition affects the people close to you.
        </p>
        <div class="why-list">
          <div><strong>Family</strong> sees the daily impact on your life at home.</div>
          <div><strong>Service buddies</strong> saw what happened, or lived through the same events.</div>
          <div><strong>Friends and former officers</strong> can speak to who you were before service.</div>
        </div>
        <p class="why-closer">We recommend at least 3 statements, from at least 2 different perspectives.</p>
      </div>
    </div>

    <div class="portal-info-panel">
      <div class="portal-info-item">
        <span class="portal-info-label">Your name</span>
        <input
          v-model="veteranName"
          type="text"
          class="form__control portal-name-input"
          placeholder="Your full name"
        />
      </div>
      <div class="portal-info-hint">
        Each buddy statement will read &ldquo;Statement from [Their Name] for {{ veteranName || '[Your Name]' }}&rdquo;
        at the top. Correct it above if it's not right.
      </div>
    </div>

    <div class="counter-bar">
      <span class="counter-text"><span class="count-num">{{ buddies.length }}</span> of {{ MAX_BUDDIES }} buddy statements added</span>
      <span class="counter-rec">Recommended: at least 3, from at least 2 different perspectives</span>
    </div>

    <div class="not-saved-banner">
      <div class="not-saved-banner-icon">!</div>
      <div>
        <strong>Save each statement to come back to it later.</strong> Anything you have not
        saved is lost if you close this page or refresh. Saving keeps a draft on your account
        only. You still need to download each statement and have it signed before you can
        upload it to your VA claim.
      </div>
    </div>

    <div v-for="(b, i) in buddies" :key="b.key" class="buddy-statement" :class="{ saved: b.downloaded }">
      <div class="buddy-header">
        <span class="buddy-num">Buddy Statement #{{ i + 1 }}</span>
        <div class="buddy-header-actions">
          <span v-if="b.condition.name" class="buddy-condition-tag">{{ b.condition.name }}</span>
          <span v-if="b.downloaded" class="downloaded-badge">Downloaded</span>
          <button type="button" class="btn-remove" title="Remove" @click="removeBuddy(i)">&times;</button>
        </div>
      </div>

      <div v-if="b.error" class="alert alert-danger" role="alert">{{ b.error }}</div>

      <!-- 1. Condition -->
      <div class="section">
        <div class="section-label">1. Which condition is this buddy statement about?</div>
        <div class="section-hint">Pick the condition this statement supports.</div>
        <div class="field-row">
          <div class="field">
            <label>Condition name</label>
            <input v-model="b.condition.name" type="text" class="form__control" placeholder="e.g. Right knee condition" @input="resetOutput(b)" />
          </div>
          <div class="field">
            <label>Category</label>
            <select v-model="b.condition.category" class="form__control" @change="resetOutput(b)">
              <option value="" disabled>Select a category</option>
              <option v-for="c in CATEGORIES" :key="c" :value="c">{{ formatLabel(c) }}</option>
            </select>
          </div>
        </div>
      </div>

      <!-- 2. Relationship -->
      <div class="section">
        <div class="section-label">2. Who is writing this statement?</div>
        <div class="rel-grid">
          <button
            v-for="r in RELATIONSHIPS"
            :key="r.value"
            type="button"
            class="rel-btn"
            :class="{ selected: b.relationship === r.value }"
            @click="selectRelationship(b, r.value)"
          >
            <span class="rel-title">{{ r.title }}</span>
            <span class="rel-sub">{{ r.sub }}</span>
          </button>
        </div>
      </div>

      <!-- 3. About them -->
      <div v-if="b.relationship" class="section">
        <div class="section-label">3. About them</div>
        <div class="field-row">
          <div class="field">
            <label>Their name</label>
            <input v-model="b.theirName" type="text" class="form__control" :placeholder="placeholdersFor(b.relationship).name" />
          </div>
          <div class="field">
            <label>Their relationship to you</label>
            <input v-model="b.theirRelDetail" type="text" class="form__control" :placeholder="placeholdersFor(b.relationship).rel" />
          </div>
        </div>
        <div class="field" style="margin-top:12px;">
          <label>How and when did they first meet you?</label>
          <p class="form__message text-muted small">Date, place, and circumstance. Gives their statement credibility with the VA.</p>
          <textarea v-model="b.howMet" rows="2" class="form__control" :placeholder="placeholdersFor(b.relationship).met"></textarea>
        </div>
      </div>

      <!-- 4. Witness type -->
      <div v-if="b.relationship" class="section">
        <div class="section-label">4. What can they speak to?</div>
        <div class="section-hint">Pick one or both. This shapes what the statement is about.</div>
        <div class="witness-toggles">
          <label class="witness-toggle" :class="{ checked: b.witnessEvent }">
            <input type="checkbox" v-model="b.witnessEvent" @change="resetOutput(b)" />
            <div class="witness-content">
              <span class="witness-title">They were there when it happened</span>
              <span class="witness-sub">Witnessed the incident, injury, or exposure firsthand</span>
            </div>
          </label>
          <label class="witness-toggle" :class="{ checked: b.witnessImpact }">
            <input type="checkbox" v-model="b.witnessImpact" @change="resetOutput(b)" />
            <div class="witness-content">
              <span class="witness-title">They've seen how the condition affects you</span>
              <span class="witness-sub">Has known you long enough to see the changes over time</span>
            </div>
          </label>
        </div>
      </div>

      <!-- 5a. Event -->
      <div v-if="b.witnessEvent" class="section">
        <div class="section-label">5. The event they witnessed</div>
        <div class="perspective-note"><strong>Answer in your own voice.</strong> Just tell us what happened. Our AI will rewrite it from your buddy's perspective, in their voice.</div>
        <div class="field">
          <label>When did it happen?</label>
          <p class="form__message text-muted small">A date, month, deployment, or general timeframe is fine.</p>
          <input v-model="b.event.when" type="text" class="form__control" placeholder="e.g. November 12th, 2004, or during my 2007 deployment to Iraq" />
        </div>
        <div class="field">
          <label>Where?</label>
          <input v-model="b.event.where" type="text" class="form__control" placeholder="e.g. On patrol outside Fallujah, or during training at Fort Bragg" />
        </div>
        <div class="field">
          <label>What happened?</label>
          <p class="form__message text-muted small">Be specific. What happened to you, and what your buddy saw.</p>
          <textarea v-model="b.event.what" rows="3" class="form__control" placeholder="e.g. My Humvee hit an IED. He was three vehicles behind me and was one of the first to reach us."></textarea>
        </div>
      </div>

      <!-- 5b. Impact -->
      <div v-if="b.witnessImpact" class="section">
        <div class="section-label">5. What has changed for you</div>
        <div class="perspective-note"><strong>Answer in your own voice.</strong> Tell us what has changed for you since service, and what your buddy has noticed. Our AI will write it in their voice.</div>
        <div class="field">
          <label>What has changed for you that they've noticed?</label>
          <p class="form__message text-muted small">Symptoms, behavior, mood, physical limitations, relationships. In your own words.</p>
          <textarea v-model="b.impact.change" rows="3" class="form__control" placeholder="e.g. Constant back pain since my second tour. Nightmares. I avoid crowds now."></textarea>
        </div>
        <div class="field">
          <label>Specific examples they might mention <span class="optional">(optional)</span></label>
          <p class="form__message text-muted small">Concrete moments make the statement more powerful.</p>
          <textarea v-model="b.impact.examples" rows="3" class="form__control" placeholder="e.g. I missed our family reunion because the drive was too much."></textarea>
        </div>
      </div>

      <!-- Generate -->
      <div v-if="(b.witnessEvent || b.witnessImpact) && b.attemptNumber === 0" class="generate-row">
        <button type="button" class="btn btn-secondary-brand fw-medium" :disabled="b.submitting" @click="generate(b)">
          {{ b.submitting ? 'Drafting the buddy statement...' : 'Generate this buddy statement' }}
        </button>
        <div class="generate-hint">
          Our AI drafts a detailed, factual statement in your buddy's voice. Target length is
          1,500 to 2,000 characters. You can regenerate up to 5 times with feedback.
        </div>
      </div>

      <!-- Output -->
      <div v-if="b.attemptNumber > 0" class="output-wrap">
        <div class="output-header">
          <span class="output-title">The buddy statement</span>
          <span class="attempt-badge">Attempt {{ b.attemptNumber }} of 5</span>
        </div>
        <textarea v-model="b.statement" rows="9" class="form__control output-text"></textarea>
        <div class="output-meta">
          <span class="char-count" :class="{ over: b.statement.length > HARD_CAP }">{{ b.statement.length }} characters</span>
          <span class="output-hint">You can edit directly, or use feedback below.</span>
        </div>

        <!-- Regenerate -->
        <div v-if="b.attemptNumber < MAX_ATTEMPTS && !b.downloaded" class="regen-wrap">
          <div class="regen-label">Want to change something?</div>
          <div class="regen-hint">Tell us what to add, remove, or adjust the tone.</div>
          <textarea v-model="b.feedback" rows="2" class="form__control" placeholder='e.g. "Make it more emotional" or "Add that she missed my surgery in 2019"'></textarea>
          <div class="regen-actions">
            <button type="button" class="btn btn-outline-secondary fw-medium" :disabled="b.submitting || !b.feedback.trim()" @click="regenerate(b)">
              {{ b.submitting ? 'Regenerating...' : 'Regenerate with this feedback' }}
            </button>
          </div>
        </div>
        <div v-else-if="!b.downloaded" class="max-attempts">
          You've used all 5 regeneration attempts. Edit the statement directly in the box above if you want small tweaks, then download.
        </div>

        <!-- Download -->
        <div v-if="!b.downloaded" class="not-saved-inline">
          <strong v-if="b.saved">Saved to your account.</strong>
          <strong v-else>Not saved yet.</strong>
          <template v-if="b.saved">You can close this page and pick this statement back up later.</template>
          <template v-else>The statement above lives only in this browser tab until you save it.</template>
          To use it on your claim, download it and send the file to
          <strong>{{ b.theirName || 'the person writing it' }}</strong> for their signature, then upload the signed copy to your VA claim.
        </div>
        <div v-if="!b.downloaded" class="save-row">
          <button type="button" class="btn btn-outline-secondary fw-medium" :disabled="b.saving" @click="saveStatement(b)">
            {{ b.saving ? 'Saving...' : (b.saved ? 'Saved' : 'Save for later') }}
          </button>
          <span v-if="b.saveError" class="save-error">{{ b.saveError }}</span>
        </div>
        <div v-if="!b.downloaded" class="download-choice-header">Choose your download format:</div>
        <div v-if="!b.downloaded" class="download-buttons-row">
          <button type="button" class="btn-download-option" @click="downloadPDF(b)">
            <span class="option-title">Simple statement (PDF)</span>
            <span class="option-sub">A signed letter your buddy attaches to your VA claim. Simplest option.</span>
          </button>
          <button type="button" class="btn-download-option" :disabled="b.vaFormDownloading" @click="downloadVAForm(b)">
            <span class="option-title">{{ b.vaFormDownloading ? 'Filling out the form...' : 'Filled VA Form 21-10210' }}</span>
            <span class="option-sub">The official VA lay statement form, pre-filled where we can.</span>
          </button>
        </div>
        <p v-if="b.vaFormError" class="alert alert-danger" role="alert" style="margin-top:8px;">{{ b.vaFormError }}</p>

        <!-- Downloaded state -->
        <div v-else class="downloaded-notice">
          <strong>Downloaded.</strong> Send the file to <strong>{{ b.theirName || 'the person writing it' }}</strong>
          for their signature. Then upload the signed copy to your VA claim.
          <template v-if="!b.saved"> This statement is not saved yet, so it will be gone if you close this page.</template>
          <div class="downloaded-actions-row">
            <button v-if="!b.saved" type="button" class="btn btn-outline-secondary" :disabled="b.saving" @click="saveStatement(b)">
              {{ b.saving ? 'Saving...' : 'Save for later' }}
            </button>
            <button type="button" class="btn btn-outline-secondary" @click="downloadPDF(b)">Download simple statement again</button>
            <button type="button" class="btn btn-outline-secondary" @click="downloadVAForm(b)">Download VA Form again</button>
            <button type="button" class="btn btn-outline-secondary" @click="editAgain(b)">Edit and regenerate</button>
          </div>
        </div>
      </div>
    </div>

    <div class="add-buddy-wrap">
      <button type="button" class="btn btn-outline-secondary btn-add-buddy" :disabled="buddies.length >= MAX_BUDDIES" @click="addBuddy">
        {{ buddies.length >= MAX_BUDDIES ? 'Maximum of 5 buddy statements reached' : '+ Add another buddy statement' }}
      </button>
      <div v-if="buddies.length < MAX_BUDDIES" class="add-buddy-limit">Can add {{ MAX_BUDDIES - buddies.length }} more</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from 'vue'

const MAX_BUDDIES = 5
const MAX_ATTEMPTS = 5
const HARD_CAP = 2500

// Same category enum as the personal statement page (VetCommStatementPage.vue) --
// the buddy-statement API doc says condition.category is "same enum as personal statements".
const CATEGORIES = [
  'hearing_loss', 'tinnitus', 'ptsd', 'mst', 'depression_anxiety', 'tbi',
  'sleep_apnea', 'foot', 'ankle', 'knee', 'hip', 'back_spine', 'shoulder',
  'nerve_damage', 'heart', 'hypertension', 'sinusitis_rhinitis', 'asthma',
  'gerd', 'migraine', 'other',
]

const RELATIONSHIPS = [
  { value: 'family', title: 'Family', sub: 'Spouse, sibling, parent, adult child' },
  { value: 'friend', title: 'Friend', sub: 'Long-time friend, someone who knows you well' },
  { value: 'buddy', title: 'Service Buddy', sub: 'Someone you served with' },
  { value: 'officer', title: 'Officer / NCO', sub: 'Superior, unit leadership, chain of command' },
  { value: 'other', title: 'Other', sub: 'Neighbor, employer, clergy, coworker' },
]

const PLACEHOLDERS = {
  family: { name: 'e.g. Sarah Johnson', rel: 'e.g. My wife of 22 years', met: 'e.g. Married in June 2001' },
  friend: { name: 'e.g. Marcus Chen', rel: 'e.g. Best friend since high school', met: 'e.g. Met in ninth grade at Central High School in September 2001' },
  buddy: { name: 'e.g. SSgt Mike Rivera', rel: 'e.g. Served with me in 2nd Battalion, 5th Marines', met: 'e.g. Met at Parris Island during basic training in November 2002' },
  officer: { name: 'e.g. Cpt. James Whitfield', rel: 'e.g. My platoon commander in Afghanistan', met: 'e.g. He was my platoon commander during our 2010-2011 deployment to Kandahar' },
  other: { name: 'e.g. Pastor David Lin', rel: 'e.g. My pastor for 15 years', met: 'e.g. Been my pastor at Grace Community Church since March 2013' },
}
function placeholdersFor(rel) {
  return PLACEHOLDERS[rel] || { name: '', rel: '', met: '' }
}

function formatLabel(str) {
  return str.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

// Seeded from the veteran's latest saved personal statement (see
// prefillConditionFromLatestPersonalStatement) once that lookup resolves.
// Every block created after that -- including ones added later via "+ Add
// another buddy statement" -- starts with this condition already filled in,
// since buddy statements are usually written in a batch for one condition;
// the veteran can still change it per block.
const defaultCondition = reactive({ name: '', category: '' })

let nextKey = 1
function newBuddy() {
  return reactive({
    key: nextKey++,
    condition: { name: defaultCondition.name, category: defaultCondition.category },
    relationship: '',
    theirName: '',
    theirRelDetail: '',
    howMet: '',
    witnessEvent: false,
    witnessImpact: false,
    event: { when: '', where: '', what: '' },
    impact: { change: '', examples: '' },
    statement: '',
    attemptNumber: 0,
    feedback: '',
    submitting: false,
    error: '',
    downloaded: false,
    vaFormDownloading: false,
    vaFormError: '',
    // The exact request body sent to /api/vetcomm/buddy-statements for this
    // block's current `statement`, kept so Save can submit the full
    // interaction (inputs + output), not just the generated text.
    lastRequest: null,
    saving: false,
    saved: false,
    saveError: '',
  })
}

const buddies = ref([newBuddy()])

function addBuddy() {
  if (buddies.value.length >= MAX_BUDDIES) return
  buddies.value.push(newBuddy())
}

function removeBuddy(i) {
  buddies.value.splice(i, 1)
}

function selectRelationship(b, rel) {
  b.relationship = rel
  resetOutput(b)
}

function resetOutput(b) {
  if (b.attemptNumber > 0) {
    b.attemptNumber = 0
    b.statement = ''
    b.downloaded = false
    b.lastRequest = null
    b.saved = false
    b.saveError = ''
  }
}

function validate(b) {
  if (!b.condition.name.trim()) return 'Enter which condition this statement is about.'
  if (!b.condition.category) return 'Pick a category for this condition.'
  if (!b.relationship) return 'Pick who is writing this statement.'
  if (!b.theirName.trim()) return 'Enter their name.'
  if (!b.theirRelDetail.trim()) return 'Enter their relationship to you.'
  if (!b.howMet.trim() || b.howMet.trim().length < 5) return 'Tell us how and when they first met you.'
  if (!b.witnessEvent && !b.witnessImpact) return 'Pick at least one thing they can speak to.'
  if (b.witnessEvent && (!b.event.what.trim() || b.event.what.trim().length < 15)) {
    return 'Add more detail about what they witnessed (at least 15 characters).'
  }
  if (b.witnessImpact && (!b.impact.change.trim() || b.impact.change.trim().length < 15)) {
    return 'Add more detail about what has changed for you (at least 15 characters).'
  }
  return ''
}

function buildBody(b, regeneration) {
  return {
    veteran_name: veteranName.value.trim(),
    condition: { name: b.condition.name.trim(), category: b.condition.category },
    witness: {
      relationship: b.relationship,
      name: b.theirName.trim(),
      relationship_detail: b.theirRelDetail.trim(),
      how_met: b.howMet.trim(),
      witnessed_event: b.witnessEvent,
      witnessed_impact: b.witnessImpact,
    },
    event: b.witnessEvent ? { when: b.event.when.trim(), where: b.event.where.trim(), what: b.event.what.trim() } : null,
    impact: b.witnessImpact ? { change: b.impact.change.trim(), examples: b.impact.examples.trim() } : null,
    regeneration,
  }
}

async function callApi(b, body) {
  b.error = ''
  b.submitting = true
  try {
    const res = await fetch('/api/vetcomm/buddy-statements', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    if (!res.ok) {
      const detail = data.detail || {}
      b.error = detail.message || 'Failed to generate statement.'
      return
    }
    b.statement = data.statement
    b.attemptNumber = data.attempt_number
    b.feedback = ''
    b.downloaded = false
    b.lastRequest = body
    // A regenerated statement is a different statement -- it has not been
    // saved yet even if the previous attempt was.
    b.saved = false
    b.saveError = ''
  } catch (e) {
    b.error = 'Network error contacting the server.'
  } finally {
    b.submitting = false
  }
}

function generate(b) {
  const err = validate(b)
  if (err) { b.error = err; return }
  callApi(b, buildBody(b, null))
}

function regenerate(b) {
  if (!b.feedback.trim()) return
  callApi(b, buildBody(b, {
    previous_statement: b.statement,
    veteran_feedback: b.feedback.trim(),
    attempt_number: b.attemptNumber + 1,
  }))
}

function editAgain(b) {
  b.downloaded = false
}

/* ---------------------------------------------------------------------
   Save / resume. Mirrors the personal statement page
   (VetCommStatementPage.vue), with one difference: a veteran has up to 5
   buddy statements at once, so each block saves independently and the
   restore on load rebuilds every saved block instead of a single one.
--------------------------------------------------------------------- */

async function saveStatement(b) {
  b.saveError = ''
  b.saved = false
  const userId = readCookie('LSVT_GUSERID')
  if (!userId) {
    b.saveError = 'Could not identify the current user. Try reloading the page.'
    return
  }
  // The statement box is editable, so what is on screen may differ from what
  // the API returned. Save what the veteran can see.
  const request = { ...(b.lastRequest || buildBody(b, null)) }
  b.saving = true
  try {
    const res = await fetch('/api/vetcomm/buddy-statements/save', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        generated_at: new Date().toISOString(),
        request,
        statement: b.statement,
        character_count: b.statement.length,
        attempt_number: b.attemptNumber,
      }),
    })
    if (!res.ok) throw new Error('save failed')
    b.saved = true
  } catch (e) {
    b.saveError = 'Could not save this buddy statement. Please try again.'
  } finally {
    b.saving = false
  }
}

// Rebuilds a form block from a saved record's stored generate request, so a
// resumed block is editable and regenerable exactly like a fresh one.
function buddyFromSaved(record) {
  const req = record.request || {}
  const b = newBuddy()
  b.condition = { name: req.condition?.name || '', category: req.condition?.category || '' }
  b.relationship = req.witness?.relationship || ''
  b.theirName = req.witness?.name || ''
  b.theirRelDetail = req.witness?.relationship_detail || ''
  b.howMet = req.witness?.how_met || ''
  b.witnessEvent = !!req.witness?.witnessed_event
  b.witnessImpact = !!req.witness?.witnessed_impact
  b.event = {
    when: req.event?.when || '',
    where: req.event?.where || '',
    what: req.event?.what || '',
  }
  b.impact = {
    change: req.impact?.change || '',
    examples: req.impact?.examples || '',
  }
  b.statement = record.statement || ''
  b.attemptNumber = record.attempt_number || 1
  b.lastRequest = req
  b.saved = true
  return b
}

// On load, restores any previously saved buddy statements instead of showing
// a single blank block. Fails open to the blank block on a missing cookie,
// network error, or empty response -- this is a convenience, not something
// that should ever block the page.
async function hydrateSavedStatements(userId) {
  try {
    const r = await fetch(`/api/vetcomm/buddy-statements/${encodeURIComponent(userId)}/saved`, {
      credentials: 'include',
    })
    if (!r.ok) return false
    const data = await r.json()
    const records = (data.statements || []).slice(0, MAX_BUDDIES)
    if (!records.length) return false
    buddies.value = records.map(buddyFromSaved)
    return true
  } catch (e) {
    return false
  }
}

/* ---------------------------------------------------------------------
   Download: PDF via the browser print dialog (no Word/DOCX option).
   Kept close to the reviewed mock's print-window HTML/CSS -- these are
   standalone printable documents, not part of this page's own theme.
--------------------------------------------------------------------- */

function escapeHTML(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function markDownloaded(b) {
  b.downloaded = true
}

function downloadPDF(b) {
  const w = window.open('', '_blank')
  if (!w) { alert('Please allow pop-ups so we can open the PDF preview.'); return }
  w.document.write(buildDownloadHTML(b))
  w.document.close()
  setTimeout(() => { w.focus(); w.print() }, 300)
  markDownloaded(b)
}

async function downloadVAForm(b) {
  b.vaFormError = ''
  b.vaFormDownloading = true
  try {
    const res = await fetch('/api/vetcomm/buddy-statements/va-form', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        veteran_name: veteranName.value.trim(),
        witness_name: b.theirName.trim(),
        relationship: b.relationship,
        relationship_detail: b.theirRelDetail.trim(),
        statement: b.statement.trim(),
      }),
    })
    if (!res.ok) throw new Error('Failed to fill the VA form.')
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'VA-Form-21-10210.pdf'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    markDownloaded(b)
  } catch (e) {
    b.vaFormError = e.message || 'Failed to download the VA form.'
  } finally {
    b.vaFormDownloading = false
  }
}

function buildDownloadHTML(b) {
  const stmt = b.statement.trim()
  const theirName = b.theirName.trim() || '[Their Name]'
  const veteran = veteranName.value.trim() || '[Veteran Name]'
  const regarding = b.condition.name ? `VA Disability Claim, ${b.condition.name}` : 'VA Disability Claim'
  const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Statement from ${escapeHTML(theirName)} for ${escapeHTML(veteran)}</title>
    <style>
      body { font-family: 'Times New Roman', Times, serif; max-width: 700px; margin: 40px auto; padding: 0 40px; color: #000; line-height: 1.7; font-size: 12pt; }
      .title-block { text-align: center; margin-bottom: 30px; border-bottom: 2px solid #000; padding-bottom: 16px; }
      h1 { font-size: 15pt; margin: 0 0 6px; letter-spacing: 0.5px; font-weight: bold; }
      .for-line { font-size: 13pt; margin: 0; }
      .meta { margin-bottom: 24px; font-size: 11pt; }
      .meta div { margin-bottom: 4px; }
      .salutation { margin: 24px 0 16px; font-size: 12pt; }
      .statement { margin: 16px 0 30px; text-align: justify; }
      .certification { margin-top: 30px; font-size: 12pt; font-style: italic; }
      .contact-offer { margin-top: 20px; font-size: 12pt; }
      .signature-block { margin-top: 40px; }
      .sig-line { border-top: 1px solid #000; width: 320px; margin-top: 40px; padding-top: 4px; font-size: 10pt; }
      @media print { body { margin: 20px auto; } }
    </style></head><body>
    <div class="title-block">
      <h1>Statement from ${escapeHTML(theirName)}</h1>
      <p class="for-line">for ${escapeHTML(veteran)}</p>
    </div>
    <div class="meta">
      <div><strong>Relationship to Veteran:</strong> ${escapeHTML(b.theirRelDetail)}</div>
      <div><strong>Date:</strong> ${today}</div>
      <div><strong>Regarding:</strong> ${escapeHTML(regarding)}</div>
    </div>
    <div class="salutation">To whom it may concern:</div>
    <div class="statement">${escapeHTML(stmt).replace(/\n/g, '<br><br>')}</div>
    <div class="certification">I, ${escapeHTML(theirName)}, certify that the statements above are true and correct to the best of my knowledge and belief.</div>
    <div class="contact-offer">If you have any further questions, please do not hesitate to contact me at any time.</div>
    <div class="signature-block">
      <div class="sig-line">Name</div>
      <div class="sig-line">Date</div>
    </div>
    </body></html>`
}

/* ---------------------------------------------------------------------
   Host theme + veteran-name prefill (same LSVT_GUSERID cookie pattern as
   VetCommStatementPage.vue). No Select2 here -- blocks are added/removed
   dynamically, so plain host-styled <select>s are used instead.
--------------------------------------------------------------------- */

const THEME_CSS_URLS = [
  'https://static.lightspeedvt.com/style-guide/assets/main.e90ef0edf72154adbce3.css',
  'https://static.lightspeedvt.com/style-guide/assets/globals.5792cb6ee7379b46991a.css',
  'https://static.lightspeedvt.com/style-guide/assets/buttons.efbc44e50a0170455298.css',
  'https://static.lightspeedvt.com/style-guide/assets/alert.64e9874cd1c52527f0d4.css',
  'https://static.lightspeedvt.com/style-guide/assets/form-input.0c7f556d03b74cb1421f.css',
  'https://static.lightspeedvt.com/themer2-vt/5069/css/theme-4CAF754E-BC4B-5B07-7BA756E81A79072F.css',
]
let themeLinkEls = []
let hadDarkClass = false

const veteranName = ref('')

function readCookie(name) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[1]) : null
}

// Convenience prefill: buddy statements are often written back-to-back with
// a personal statement for the same condition, so reuse it as a starting
// point if one was saved. Buddy statements themselves are never saved (see
// docs/vetcomm-buddy-statement-api.md), so this is the personal-statement
// page's save/resume data (GET /vetcomm/statements/{user_id}/latest), not
// anything buddy-statement-specific.
//
// Sets `defaultCondition`, which every block created from this point on
// (including the already-created first block, and any later added via "+ Add
// another buddy statement") picks up -- see newBuddy(). Only touches the
// first block directly here, and only if the veteran hasn't already typed
// something into it; later blocks get it for free through defaultCondition.
async function prefillConditionFromLatestPersonalStatement(userId) {
  const first = buddies.value[0]
  try {
    const r = await fetch(`/api/vetcomm/statements/${encodeURIComponent(userId)}/latest`, { credentials: 'include' })
    if (!r.ok) return
    const data = await r.json()
    const condition = data.found && data.request?.condition
    if (!condition) return
    defaultCondition.name = condition.name || ''
    defaultCondition.category = condition.category || ''
    if (first && !first.condition.name.trim() && !first.condition.category) {
      first.condition.name = defaultCondition.name
      first.condition.category = defaultCondition.category
    }
  } catch (e) {
    // Best-effort prefill only -- fall through to a blank, editable field.
  }
}

onMounted(async () => {
  hadDarkClass = document.documentElement.classList.contains('dark')
  document.documentElement.classList.remove('dark')
  document.body.classList.remove('dark')

  themeLinkEls = THEME_CSS_URLS.map((href) => {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = href
    document.head.appendChild(link)
    return link
  })

  const userId = readCookie('LSVT_GUSERID')
  if (userId) {
    try {
      const r = await fetch(`/api/vetcomm/veteran-name/${encodeURIComponent(userId)}`, { credentials: 'include' })
      if (r.ok) {
        const data = await r.json()
        if (data.name) veteranName.value = data.name
      }
    } catch (e) {
      // Best-effort prefill only -- fall through to the blank/editable field.
    }
    // Restoring saved buddy statements takes precedence: those blocks
    // already carry their own condition, so the personal-statement prefill
    // is only useful when starting from a blank block.
    const restored = await hydrateSavedStatements(userId)
    if (!restored) await prefillConditionFromLatestPersonalStatement(userId)
  }
})

onUnmounted(() => {
  if (hadDarkClass) {
    document.documentElement.classList.add('dark')
    document.body.classList.add('dark')
  }
  themeLinkEls.forEach((link) => link.remove())
  themeLinkEls = []
})

window.addEventListener('beforeunload', (e) => {
  if (buddies.value.some((b) => b.attemptNumber > 0 && !b.downloaded && !b.saved)) {
    e.preventDefault()
    e.returnValue = ''
  }
})
</script>

<style scoped>
#form {
  position: relative;
  background: #fff;
  border-radius: 10px;
  padding: 1.25rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, .08);
  width: 100%;
  max-width: 52rem;

  /* Page-scoped brand colors, sourced from the LightSpeedVT theme CSS
     injected at runtime (see THEME_CSS_URLS); safe fallbacks otherwise. */
  --primary-color: #082c4b;
  --primary-color-accent: #ffffff;
  --secondary-color: #ee232b;
  --secondary-color-accent: #ffffff;
  --gray-50: #f8f9fb; --gray-100: #f1f3f8; --gray-200: #e5e8ef;
  --gray-300: #d1d6e0; --gray-400: #a3adc0; --gray-500: #6b7383;
  --green: #2e7d32; --yellow: #f9a825; --yellow-light: #fffbe6;
  font-size: 14px;
}

#form .btn-secondary-brand {
  background-color: var(--secondary-color);
  color: var(--secondary-color-accent);
  border-color: var(--secondary-color);
}
#form .btn-secondary-brand:hover:not(:disabled) { opacity: .9; color: var(--secondary-color-accent); }
#form .btn-secondary-brand:disabled { opacity: .5; }

.why-panel { background: var(--primary-color); border-radius: 12px; padding: 18px 22px; margin-bottom: 22px; border-left: 5px solid var(--secondary-color); }
.why-title { display: flex; align-items: center; gap: 11px; color: #fff; font-size: 15px; font-weight: 800; margin-bottom: 12px; line-height: 1.35; }
.why-icon { width: 28px; height: 28px; border-radius: 7px; background: rgba(238,35,43,.25); color: var(--secondary-color); font-size: 15px; font-weight: 900; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.why-body p { color: rgba(255,255,255,.85); font-size: 13px; line-height: 1.65; margin: 0 0 12px; }
.why-body strong { color: #fff; font-weight: 700; }
.why-list { background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 12px 14px; margin-bottom: 12px; }
.why-list > div { font-size: 12.5px; color: rgba(255,255,255,.78); line-height: 1.55; margin-bottom: 6px; }
.why-list > div:last-child { margin-bottom: 0; }
.why-list strong { color: #fff; margin-right: 3px; }
.why-closer { color: #fff; font-size: 13px; margin: 6px 0 0; font-weight: 700; }

.portal-info-panel { background: var(--gray-50); border: 1px solid var(--gray-200); border-radius: 8px; padding: 14px 16px; margin-bottom: 18px; }
.portal-info-item { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.portal-info-label { font-size: 12px; font-weight: 600; color: var(--gray-500); text-transform: uppercase; letter-spacing: .4px; }
.portal-name-input { max-width: 280px; font-size: 15px !important; font-weight: 700; }
.portal-info-hint { font-size: 11.5px; color: var(--gray-500); margin-top: 8px; line-height: 1.5; }

.counter-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: var(--gray-50); border: 1px solid var(--gray-200); border-radius: 8px; margin-bottom: 18px; flex-wrap: wrap; gap: 8px; }
.counter-text { font-size: 14px; font-weight: 700; color: var(--primary-color); }
.count-num { color: var(--secondary-color); }
.counter-rec { font-size: 12px; color: var(--gray-500); font-weight: 500; }

.not-saved-banner, .not-saved-inline {
  background: var(--yellow-light); border: 1.5px solid var(--yellow); border-radius: 8px;
  padding: 11px 14px; color: #5d3a00; font-size: 12.5px; line-height: 1.55;
  display: flex; align-items: flex-start; gap: 10px;
}
.not-saved-banner { margin-bottom: 18px; }
.not-saved-inline { margin-top: 14px; font-weight: 600; }
.not-saved-banner-icon {
  width: 22px; height: 22px; background: var(--yellow); color: #5d3a00; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 13px; flex-shrink: 0; line-height: 1;
}
.not-saved-banner strong, .not-saved-inline strong { color: #5d3a00; font-weight: 800; }

.buddy-statement { border: 1px solid var(--gray-200); border-radius: 12px; padding: 18px; margin-bottom: 14px; background: var(--gray-50); }
.buddy-statement.saved { background: #f0f9ee; border-color: #c8e6c9; }
.buddy-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.buddy-num { font-size: 13px; font-weight: 800; color: var(--primary-color); text-transform: uppercase; letter-spacing: .4px; }
.buddy-header-actions { display: flex; align-items: center; gap: 10px; }
.btn-remove { background: none; border: none; font-size: 20px; color: var(--gray-400); cursor: pointer; padding: 0 6px; line-height: 1; }
.btn-remove:hover { color: var(--secondary-color); }
.buddy-condition-tag { display: inline-flex; align-items: center; background: rgba(8,44,75,.08); color: var(--primary-color); font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 100px; }
.downloaded-badge { font-size: 11px; font-weight: 700; color: var(--green); display: inline-flex; align-items: center; gap: 5px; }
.downloaded-badge::before { content: "\2713"; font-size: 12px; font-weight: 900; }

.section { background: #fff; border: 1px solid var(--gray-200); border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; }
.section-label { font-size: 12px; font-weight: 800; color: var(--primary-color); text-transform: uppercase; letter-spacing: .4px; margin-bottom: 11px; }
.section-hint { font-size: 11.5px; color: var(--gray-500); line-height: 1.5; margin-top: -6px; margin-bottom: 11px; }

.rel-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 9px; }
@media (min-width: 640px) { .rel-grid { grid-template-columns: repeat(3, 1fr); } }
.rel-btn {
  background: #fff; border: 1.5px solid var(--gray-300); border-radius: 8px; padding: 11px 12px;
  text-align: left; cursor: pointer; transition: all .15s; display: flex; flex-direction: column;
  align-items: flex-start; gap: 3px; min-height: 64px; font-family: inherit;
}
.rel-btn:hover { border-color: var(--primary-color); background: rgba(8,44,75,.02); }
.rel-btn.selected { border-color: var(--primary-color); background: rgba(8,44,75,.06); border-width: 2px; padding: 10px 11px; }
.rel-title { font-size: 13px; font-weight: 800; color: var(--primary-color); }
.rel-sub { font-size: 10.5px; font-weight: 500; color: var(--gray-500); line-height: 1.35; }

.field-row { display: grid; grid-template-columns: 1fr; gap: 12px; }
@media (min-width: 520px) { .field-row { grid-template-columns: 1fr 2fr; } }
.field { margin-bottom: 0; }
.field label { display: block; font-size: 12px; font-weight: 700; color: var(--primary-color); margin-bottom: 4px; }
.field label .optional { font-weight: 500; color: var(--gray-500); font-size: 11px; margin-left: 4px; }

.witness-toggles { display: flex; flex-direction: column; gap: 8px; }
.witness-toggle {
  display: flex; align-items: flex-start; gap: 10px; padding: 11px 13px; border: 1.5px solid var(--gray-300);
  border-radius: 8px; cursor: pointer; background: #fff; transition: all .15s;
}
.witness-toggle:hover { border-color: var(--primary-color); }
.witness-toggle.checked { border-color: var(--primary-color); background: rgba(8,44,75,.04); }
.witness-toggle input[type="checkbox"] { margin-top: 2px; width: 16px; height: 16px; accent-color: var(--primary-color); flex-shrink: 0; cursor: pointer; }
.witness-content { display: flex; flex-direction: column; gap: 2px; }
.witness-title { font-size: 13px; font-weight: 700; color: var(--primary-color); }
.witness-sub { font-size: 11.5px; font-weight: 500; color: var(--gray-500); line-height: 1.4; }

.perspective-note { background: #e8f0fe; border-left: 3px solid var(--primary-color); padding: 9px 12px; font-size: 11.5px; color: var(--primary-color); line-height: 1.5; border-radius: 0 4px 4px 0; margin-bottom: 12px; }

.generate-row { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 6px 0; }
.generate-hint { font-size: 11px; color: var(--gray-500); text-align: center; max-width: 380px; line-height: 1.5; }

.output-wrap { margin-top: 12px; background: #fff; border: 2px solid var(--primary-color); border-radius: 8px; padding: 14px 16px; }
.output-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 6px; }
.output-title { font-size: 12px; font-weight: 700; color: var(--primary-color); text-transform: uppercase; letter-spacing: .4px; }
.attempt-badge { font-size: 11px; font-weight: 700; color: var(--gray-500); background: var(--gray-100); padding: 3px 9px; border-radius: 100px; }
.output-text { font-size: 13.5px !important; line-height: 1.65; }
.output-meta { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; gap: 14px; flex-wrap: wrap; }
.char-count { font-size: 11px; font-weight: 700; color: var(--gray-500); }
.char-count.over { color: var(--secondary-color); }
.output-hint { font-size: 11px; color: var(--gray-400); font-style: italic; }

.regen-wrap { margin-top: 12px; padding: 14px 16px; background: #fff; border: 1px dashed var(--gray-300); border-radius: 8px; }
.regen-label { font-size: 13px; font-weight: 700; color: var(--primary-color); margin-bottom: 3px; }
.regen-hint { font-size: 11px; color: var(--gray-500); margin-bottom: 8px; }
.regen-actions { margin-top: 12px; }

.save-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-top: 12px; }
.save-error { font-size: 12px; color: var(--bs-danger, #dc3545); }

.max-attempts { margin-top: 12px; padding: 12px 16px; background: var(--yellow-light); border: 1px solid #ffe082; border-radius: 8px; font-size: 12px; color: #5d3a00; line-height: 1.5; }

.download-choice-header { font-size: 12px; font-weight: 800; color: var(--primary-color); text-transform: uppercase; letter-spacing: .4px; margin: 14px 0 10px; }
.download-buttons-row { display: flex; flex-direction: column; gap: 10px; }
@media (min-width: 640px) { .download-buttons-row { flex-direction: row; } }
.btn-download-option {
  background: #fff; border: 2px solid var(--secondary-color); color: var(--primary-color); border-radius: 8px;
  padding: 14px 16px; text-align: left; cursor: pointer; transition: all .15s; font-family: inherit;
  display: flex; flex-direction: column; gap: 5px; flex: 1; min-width: 0;
}
.btn-download-option:hover:not(:disabled) { background: #fff5f5; }
.btn-download-option:disabled { opacity: .6; cursor: wait; }
.btn-download-option .option-title { font-size: 14px; font-weight: 800; color: var(--secondary-color); display: flex; align-items: center; gap: 8px; }
.btn-download-option .option-title::before { content: "\2193"; font-size: 15px; font-weight: 900; }
.btn-download-option .option-sub { font-size: 11.5px; font-weight: 500; color: var(--gray-500); line-height: 1.4; }

.downloaded-notice { margin-top: 12px; padding: 12px 14px; background: #f0f9ee; border: 1px solid #c8e6c9; border-radius: 8px; color: #1b5e20; font-size: 12.5px; line-height: 1.55; }
.downloaded-notice strong { font-weight: 800; }
.downloaded-actions-row { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }

.add-buddy-wrap { margin-top: 6px; text-align: center; }
.btn-add-buddy { width: 100%; }
.add-buddy-limit { font-size: 11px; color: var(--gray-500); margin-top: 8px; }
</style>
