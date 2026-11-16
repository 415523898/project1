import { computed, ref, watch } from 'vue'

const STORAGE_KEY = 'forest-sidebar-collapsed-v1'
const NARROW = '(max-width: 900px)'

function stored(): boolean | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (value === '1') return true
    if (value === '0') return false
    return null
  } catch {
    return null
  }
}

function narrow(): boolean {
  try {
    return window.matchMedia(NARROW).matches
  } catch {
    return false
  }
}

const saved = stored()
const collapsed = ref(saved ?? narrow())
const narrowViewport = ref(narrow())
const mobileOpen = ref(false)
const wide = computed(() => (narrowViewport.value ? mobileOpen.value : !collapsed.value))
const compact = computed(() => !wide.value)

if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  const query = window.matchMedia(NARROW)
  const update = (event: MediaQueryListEvent) => {
    narrowViewport.value = event.matches
    mobileOpen.value = false
  }
  if (typeof query.addEventListener === 'function') query.addEventListener('change', update)
  else if (typeof query.addListener === 'function') query.addListener(update)
}

function apply(): void {
  document.body.dataset.sidebar = compact.value ? 'rail' : 'open'
}

watch(collapsed, (value) => {
  try {
    localStorage.setItem(STORAGE_KEY, value ? '1' : '0')
  } catch {
    void 0
  }
})

watch([collapsed, mobileOpen, narrowViewport], apply, { immediate: true })

if (typeof window !== 'undefined') {
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !event.defaultPrevented && mobileOpen.value) {
      mobileOpen.value = false
      document
        .querySelector<HTMLButtonElement>(
          '[data-action="expand-sidebar"], [data-action="collapse-sidebar"]',
        )
        ?.focus({ preventScroll: true })
    }
  })
}

export function useSidebar() {
  return {
    collapsed,
    narrow: narrowViewport,
    wide,
    compact,
    toggle(): void {
      if (narrowViewport.value) mobileOpen.value = !mobileOpen.value
      else collapsed.value = !collapsed.value
    },
    expand(): void {
      if (narrowViewport.value) mobileOpen.value = true
      else collapsed.value = false
    },
    close(): void {
      if (narrowViewport.value) mobileOpen.value = false
      else collapsed.value = true
    },
    closeMobile(): void {
      mobileOpen.value = false
    },
    sync(): void {
      apply()
    },
  }
}
