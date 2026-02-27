import { ref } from 'vue'

const STORAGE_KEY = 'am-lightspeedvt-theme'

function getStored() {
  if (typeof localStorage === 'undefined') return null
  const v = localStorage.getItem(STORAGE_KEY)
  return v === 'dark' || v === 'light' ? v : null
}

function getSystemDark() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function getAppDocument() {
  if (typeof document === 'undefined') return null
  const root = document.getElementById('app')
  return root ? root.ownerDocument : document
}

function applyTheme(isDark) {
  const doc = getAppDocument()
  if (!doc) return
  const html = doc.documentElement
  const body = doc.body
  if (isDark) {
    html.classList.add('dark')
    if (body) body.classList.add('dark')
  } else {
    html.classList.remove('dark')
    if (body) body.classList.remove('dark')
  }
}

// Singleton so all components share the same theme state; survive Vite HMR
let isDarkRef = null

/** @returns {{ isDark: import('vue').Ref<boolean>, setTheme: (value: 'light' | 'dark') => void }} */
export function useTheme() {
  if (!isDarkRef) {
    if (import.meta.hot?.data?.themeRef) {
      isDarkRef = import.meta.hot.data.themeRef
    } else {
      const stored = getStored()
      const initialDark = stored === 'dark' ? true : stored === 'light' ? false : getSystemDark()
      isDarkRef = ref(initialDark)
      if (import.meta.hot) import.meta.hot.data.themeRef = isDarkRef
    }
  }

  function setTheme(value) {
    const nextDark = value === 'dark'
    isDarkRef.value = nextDark
    applyTheme(nextDark)
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch (_) {}
  }

  return { isDark: isDarkRef, setTheme }
}

export function initTheme() {
  const stored = getStored()
  if (stored === 'dark') {
    applyTheme(true)
  } else if (stored === 'light') {
    applyTheme(false)
  } else {
    applyTheme(getSystemDark())
  }
}
