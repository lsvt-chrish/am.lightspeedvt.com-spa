<template>
  <div class="w-full max-w-2xl space-y-6">
    <h1 class="text-2xl font-bold text-primary">Attribute Link Builder</h1>
    <p class="text-content-muted text-sm">
      Build a link that passes LSVT user attributes to an external URL. When someone clicks the link,
      they are redirected to your URL with the selected attributes as query parameters.
    </p>

    <div>
      <label for="redirect_url" class="block text-sm font-medium text-content mb-1">
        Redirect URL <span class="text-content-muted">(required)</span>
      </label>
      <input
        id="redirect_url"
        v-model="redirectUrl"
        type="url"
        class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none"
        placeholder="https://example.com/landing"
      />
      <p v-if="redirectUrlError" class="mt-1 text-sm text-red-400">{{ redirectUrlError }}</p>
    </div>

    <div>
      <label class="block text-sm font-medium text-content mb-2">Attributes to pass</label>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div
          v-for="group in attributeGroups"
          :key="group.name"
          class="rounded-lg border border-edge bg-surface/50 p-4 bg-white dark:bg-surface"
        >
          <h3 class="text-sm font-semibold text-content mb-3">{{ group.name }}</h3>
          <div class="grid grid-cols-1 gap-2">
            <label
              v-for="attr in group.attributes"
              :key="attr"
              class="flex items-center gap-2 cursor-pointer"
            >
              <input
                v-model="selectedAttributes"
                type="checkbox"
                :value="attr"
                class="rounded border-edge bg-surface text-secondary focus:ring-secondary"
              />
              <span :class="blockedAttributes.includes(attr) ? 'text-content-muted' : 'text-content'" class="text-sm">
                {{ attributeLabels[attr] ?? attr }}
              </span>
            </label>
          </div>
        </div>
      </div>
      <p class="mt-2 text-content-muted text-xs">
        Blocked attributes (password, apiKey, etc.) are never sent; the server filters them.
      </p>
    </div>

    <div v-if="allowedSelectedAttributes.length > 0" class="space-y-3">
      <h2 class="text-sm font-medium text-content">
        Parameter key mapping <span class="text-content-muted">(optional)</span>
      </h2>
      <p class="text-content-muted text-sm">
        Customize how attribute names appear in the final URL parameters.
      </p>
      <div class="space-y-3">
        <div
          v-for="attr in allowedSelectedAttributes"
          :key="attr"
          class="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end"
        >
          <div>
            <label class="block text-xs text-content-muted mb-1">Internal</label>
            <input
              type="text"
              :value="attr"
              readonly
              class="w-full rounded bg-surface border border-edge text-content-muted px-3 py-2 text-sm"
            />
          </div>
          <div class="sm:col-span-2">
            <label class="block text-xs text-content-muted mb-1">Output key name</label>
            <input
              v-model="keyMapOutputs[attr]"
              type="text"
              class="w-full rounded bg-surface border border-edge text-content px-3 py-2 focus:border-secondary focus:outline-none text-sm"
              :placeholder="attr"
            />
            <!-- <p class="text-content-muted text-xs mt-0.5">Leave empty to use internal name</p> -->
          </div>
        </div>
      </div>
    </div>

    <div>
      <label class="block text-sm font-medium text-content mb-1">Generated link</label>
      <div class="flex gap-2">
        <input
          :value="generatedLink"
          type="text"
          readonly
          class="flex-1 rounded bg-surface border border-edge text-content px-3 py-2 text-sm"
        />
        <button
          type="button"
          :disabled="!generatedLink"
          class="px-4 py-2 rounded bg-secondary text-secondary-accent font-medium hover:opacity-90 disabled:opacity-50 shrink-0"
          @click="copyLink"
        >
          {{ copied ? 'Copied' : 'Copy' }}
        </button>
      </div>
      <p v-show="showTestInstructions" class="mt-2 text-content-muted text-sm">
        To test with params appended: click
        <a href="/test/set-cookie" class="text-primary hover:opacity-80 font-medium">Set test cookie</a>
        on this page (same origin), then open the generated link.
        If you set the cookie on a different port or host, params will not be appended.
        Add <code class="px-1 py-0.5 rounded bg-surface text-content text-xs">apl_debug=1</code> to the link to see JSON diagnostics instead of redirecting.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const attributeGroups = [
  {
    name: 'User',
    attributes: [
      'userId',
      'username',
      'firstName',
      'lastName',
      'email',
      'phone1',
      'phone2',
      'address1',
      'address2',
      'city',
      'state',
      'zip',
      'country',
      'companyName',
      'title',
      'accessLevel',
      'misc1',
      'misc2',
    ],
  },
  {
    name: 'Location',
    attributes: ['locationId', 'locationName', 'locationVendorId'],
  },
  {
    name: 'System',
    attributes: ['systemId', 'systemName'],
  },
]

const availableAttributes = attributeGroups.flatMap((g) => g.attributes)

// Optional display labels for attributes (attribute name -> label in UI)
const attributeLabels = {
  misc1: 'misc1 (other info 1)',
  misc2: 'misc2 (other info 2)',
  locationVendorId: 'Location Vendor Id',
  locationName: 'Location Name',
  locationId: 'Location Id',
  systemId: 'System Id',
  systemName: 'System Name',
  phone1: 'Phone 1',
  phone2: 'Phone 2',
  address1: 'Address 1',
  address2: 'Address 2',
  city: 'City',
  state: 'State',
  zip: 'Zip',
  country: 'Country',
  companyName: 'Company Name',
  title: 'Title',
  accessLevel: 'Access Level',
  firstName: 'First Name',
  lastName: 'Last Name',
  email: 'Email',
  userId: 'User Id',
  username: 'Username',
}

const blockedAttributes = ['password', 'apiKey', 'apiSecret', 'secret', 'token']

const redirectUrl = ref('')
const selectedAttributes = ref([])
const keyMapOutputs = ref({})
const copied = ref(false)
const showTestInstructions = ref(false)
const allowedSelectedAttributes = computed(() =>
  selectedAttributes.value.filter(
    (a) => availableAttributes.includes(a) && !blockedAttributes.includes(a)
  )
)

const redirectUrlError = computed(() => {
  if (!redirectUrl.value.trim()) return ''
  const u = redirectUrl.value.trim()
  if (!/^https?:\/\//i.test(u)) return 'URL must start with http:// or https://'
  return ''
})

const keyMapParsed = computed(() => {
  const map = {}
  for (const attr of allowedSelectedAttributes.value) {
    const out = (keyMapOutputs.value[attr] ?? '').trim() || attr
    if (out !== attr) map[attr] = out
  }
  return Object.keys(map).length > 0 ? map : null
})

const generatedLink = computed(() => {
  const base = typeof window !== 'undefined' ? window.location.origin : ''
  const url = redirectUrl.value.trim()
  if (!url) return ''
  if (redirectUrlError.value) return ''
  const allowed = allowedSelectedAttributes.value
  if (allowed.length === 0) return base + '/apl?redirect_url=' + encodeURIComponent(url)

  const params = new URLSearchParams()
  params.set('params', allowed.join(','))
  params.set('redirect_url', url)
  if (keyMapParsed.value && Object.keys(keyMapParsed.value).length > 0) {
    params.set('key_map', JSON.stringify(keyMapParsed.value))
  }
  return base + '/apl?' + params.toString()
})

function copyLink() {
  if (!generatedLink.value) return
  navigator.clipboard.writeText(generatedLink.value).then(() => {
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  })
}

</script>
