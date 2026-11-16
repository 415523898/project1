import { frontendConfig } from '@/config'
import {
  inferProvider,
  modelFamily,
  presetDefaults,
  validProfileId,
  type Protocol,
} from '@/utils/model-providers'
import { configuredModels, availableEfforts, type ConfiguredModel } from '@/utils/model-config'
import type { DetailLevel } from '@/types'

export const SETTINGS_KEY = 'forest-ai-settings-v1'

export interface StoredSettings {
  base_url: string
  model: string
  allow_tools: boolean
  detail: DetailLevel
  provider_id: string
  preset_id?: string
  profile_name?: string
  provider_family: string
  protocol: Protocol
  reasoning_effort: string
  enabled: boolean
  models: ConfiguredModel[]
}

export const DEFAULT_BASE_URL = frontendConfig.defaults.baseUrl
export const DEFAULT_MODEL = frontendConfig.defaults.model

export function profileSettings(id: string, value: Partial<StoredSettings> = {}): StoredSettings {
  const defaults = presetDefaults(id, value),
    preset = defaults.preset
  const protocol = (
    ['chat', 'responses', 'anthropic', 'gemini'].includes(value.protocol ?? '')
      ? value.protocol
      : defaults.protocol
  ) as Protocol
  const model = typeof value.model === 'string' ? value.model : (preset.models[0]?.id ?? '')
  const models = configuredModels(preset.id, protocol, model, value.models)
  const effort = availableEfforts(
    id,
    protocol,
    model,
    models.find((item) => item.id === model),
    preset.id,
  ).includes(value.reasoning_effort ?? '')
    ? value.reasoning_effort!
    : 'auto'
  return {
    provider_id: id,
    preset_id: preset.id,
    profile_name: typeof value.profile_name === 'string' ? value.profile_name.slice(0, 80) : '',
    provider_family: modelFamily(id, model, preset.id),
    protocol,
    models,
    model,
    reasoning_effort: effort,
    base_url: typeof value.base_url === 'string' ? value.base_url : defaults.base_url,
    enabled: value.enabled !== false,
    allow_tools: value.allow_tools !== false,
    detail: value.detail === 'concise' || value.detail === 'detailed' ? value.detail : 'normal',
  }
}

export function defaultSettings(): StoredSettings {
  return profileSettings(frontendConfig.defaults.provider)
}

export function readSettings(): StoredSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY)
    if (!raw) return defaultSettings()
    const parsed = JSON.parse(raw) as Partial<StoredSettings>
    const base =
      typeof parsed.base_url === 'string' && parsed.base_url.trim()
        ? parsed.base_url
        : DEFAULT_BASE_URL
    const model =
      typeof parsed.model === 'string' && parsed.model.trim() ? parsed.model : DEFAULT_MODEL
    const inferred = inferProvider(base, model)
    return profileSettings(validProfileId(parsed.provider_id) ? parsed.provider_id : inferred.id, {
      ...parsed,
      base_url: base,
      model,
    })
  } catch {
    return defaultSettings()
  }
}
