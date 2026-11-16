import { frontendConfig } from '@/config'
import { computed, reactive, watch } from 'vue'

const KEY = 'forest-panel-widths-v1'
const limits = frontendConfig.panels
type Panel = keyof typeof limits

function stored(): Record<string, unknown> {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) || '{}')
    return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

function clamp(panel: Panel, value: unknown): number {
  const { initial, min, max } = limits[panel]
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.min(max, Math.max(min, Math.round(value)))
    : initial
}

const saved = stored()
const widths = reactive(
  Object.fromEntries(
    (Object.keys(limits) as Panel[]).map((panel) => [panel, clamp(panel, saved[panel])]),
  ) as Record<Panel, number>,
)

watch(widths, (value) => {
  try {
    localStorage.setItem(KEY, JSON.stringify(value))
  } catch {
    /* Storage may be unavailable. */
  }
})

export function usePanelWidth(panel: Panel) {
  return {
    width: computed(() => widths[panel]),
    ...limits[panel],
    set(value: number): void {
      widths[panel] = clamp(panel, value)
    },
  }
}
