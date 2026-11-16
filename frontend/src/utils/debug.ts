import type { useLab } from '@/composables/useLab'

type LabApi = ReturnType<typeof useLab>

interface DebugWindow extends Window {
  __lab?: LabApi
}

export function attachDebug(lab: LabApi): void {
  const target = window as DebugWindow
  target.__lab = lab
}
