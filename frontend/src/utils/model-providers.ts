import catalog from '../../../backend/agent/assets/model-providers.json'
export type Protocol = 'chat' | 'responses' | 'anthropic' | 'gemini'
export interface ModelChoice {
  id: string
  efforts: string[]
  budget?: boolean
}
export interface EndpointPreset {
  id: string
  label: string
  base_url: string
  protocols: Protocol[]
  plans: string[]
  source: string
  note?: string
  models_url?: string
}
export interface ProviderPreset {
  id: string
  label: string
  family: string
  protocol: Protocol
  base_url: string
  models: ModelChoice[]
  endpoints: EndpointPreset[]
  source?: string
  logo?: string
}
export interface ProfileIdentity {
  preset_id?: unknown
  profile_name?: string
  base_url?: string
  protocol?: Protocol
}
const families = catalog.model_families
const aliases: Record<string, string> = catalog.legacy_aliases
const legacy: Record<
  string,
  { preset_id: string; base_url: string; protocol: string; family: string }
> = catalog.legacy_defaults
export const providers: ProviderPreset[] = catalog.providers.map((item) => ({
  ...item,
  protocol: item.protocol as Protocol,
  endpoints: item.endpoints.map((endpoint) => ({
    ...endpoint,
    protocols: endpoint.protocols as Protocol[],
  })),
  models: families.find((family) => family.id === item.family)?.models ?? [],
}))
export const custom: ProviderPreset = {
  id: 'custom',
  label: '自定义接口',
  family: 'custom',
  protocol: 'chat',
  base_url: '',
  models: [],
  endpoints: [],
}
export const presets = [...providers, custom]
export function validProfileId(id: unknown): id is string {
  return typeof id === 'string' && /^[a-z][a-z0-9-]{0,79}$/.test(id)
}
export function presetFor(id: string, settings?: ProfileIdentity): ProviderPreset {
  const explicit =
    typeof settings?.preset_id === 'string'
      ? presets.find((p) => p.id === settings.preset_id)
      : undefined
  return explicit ?? presets.find((p) => p.id === (aliases[id] ?? id)) ?? custom
}
export function presetDefaults(id: string, settings?: ProfileIdentity) {
  const preset = presetFor(id, settings),
    old = !settings?.preset_id ? legacy[id] : undefined
  return {
    preset,
    base_url: old?.base_url ?? preset.base_url,
    protocol: (old?.protocol ?? preset.protocol) as Protocol,
    family: old?.family ?? preset.family,
  }
}
export function endpointFor(
  preset: ProviderPreset,
  base: string,
  protocol: Protocol,
): EndpointPreset | undefined {
  return preset.endpoints.find(
    (endpoint) =>
      endpoint.base_url.replace(/\/$/, '') === base.replace(/\/$/, '') &&
      endpoint.protocols.includes(protocol),
  )
}
export function profileLabel(id: string, settings?: ProfileIdentity): string {
  const name = settings?.profile_name?.trim()
  if (name) return name
  const preset = presetFor(id, settings)
  if (id === preset.id) return preset.label
  const endpoint =
    settings?.base_url && settings.protocol
      ? endpointFor(preset, settings.base_url, settings.protocol)
      : undefined
  return `${preset.label} · ${endpoint?.label ?? '独立配置'}`
}
export const protocols: Record<Protocol, string> = {
  chat: 'OpenAI Chat Completions',
  responses: 'OpenAI Responses',
  anthropic: 'Anthropic Messages',
  gemini: 'Gemini GenerateContent',
}
export const effortLabels: Record<string, string> = {
  auto: '服务商默认',
  off: '关闭思考',
  enabled: '开启思考',
  none: '无',
  minimal: '最少',
  low: '低',
  medium: '中',
  high: '高',
  xhigh: '很高',
  max: '最高',
}
export function modelEfforts(family: string, model: string, protocol: Protocol = 'chat'): string[] {
  if (family === 'custom')
    return protocol === 'gemini'
      ? ['auto', 'low', 'medium', 'high']
      : protocol === 'anthropic'
        ? ['auto', 'off', 'low', 'medium', 'high', 'max']
        : ['auto', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']
  const expected = families.find((p) => p.id === family)?.protocol
  if (
    protocol !== expected &&
    !(family === 'mimo' && protocol === 'anthropic') &&
    !(['openai', 'grok', 'muse'].includes(family) && protocol === 'chat')
  )
    return ['auto']
  return [
    'auto',
    ...(families
      .find((provider) => provider.id === family)
      ?.models.find((item) => item.id === model)?.efforts ?? []),
  ]
}
export function inferProvider(base: string, model: string): ProviderPreset {
  const matches = providers.filter((provider) =>
    provider.endpoints.some((endpoint) => {
      try {
        const value = new URL(base),
          known = new URL(endpoint.base_url)
        return (
          value.origin === known.origin &&
          (value.pathname.replace(/\/$/, '') === known.pathname.replace(/\/$/, '') ||
            value.pathname.startsWith(known.pathname.replace(/\/$/, '') + '/'))
        )
      } catch {
        return false
      }
    }),
  )
  return (
    matches.find((provider) => provider.models.some((item) => item.id === model)) ??
    matches[0] ??
    custom
  )
}
/** Resolve model parameter compatibility independently of the saved profile identifier. */
export function modelFamily(upstream: string, model: string, presetId?: string): string {
  return (
    families.find((p) => p.models.some((m) => m.id.toLowerCase() === model.toLowerCase()))?.id ??
    presetFor(upstream, { preset_id: presetId }).family
  )
}
