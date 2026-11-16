import { ref } from 'vue'

const CONSENT_KEY = 'forest-consent-v1'

function stored(): 'yes' | 'local' | null {
  try {
    const value = localStorage.getItem(CONSENT_KEY)
    return value === 'yes' || value === 'local' ? value : null
  } catch {
    return null
  }
}

const choice = stored()
const agreed = ref(choice === 'yes')
const reviewed = ref(choice !== null)

function choose(value: 'yes' | 'local'): void {
  agreed.value = value === 'yes'
  reviewed.value = true
  try {
    localStorage.setItem(CONSENT_KEY, value)
  } catch {
    void 0
  }
}

export function useConsent() {
  return {
    agreed,
    reviewed,
    accept(): void {
      choose('yes')
    },
    localOnly(): void {
      choose('local')
    },
    revoke(): void {
      agreed.value = false
      reviewed.value = false
      try {
        localStorage.removeItem(CONSENT_KEY)
      } catch {
        void 0
      }
    },
  }
}
