import { modelEfforts, modelFamily, presetFor, type Protocol } from './model-providers'
import { isRecord } from './records'

export const inputTypes = [
  { value: 'text', label: '文本' },
  { value: 'image', label: '图片' },
  { value: 'audio', label: '音频' },
  { value: 'document', label: '文档' },
  { value: 'video', label: '视频' },
] as const
export type InputType = (typeof inputTypes)[number]['value']

const defaultInputTypes: InputType[] = ['text', 'image']

export function normalizeInputTypes(value: unknown): InputType[] {
  if (!Array.isArray(value)) return [...defaultInputTypes]
  return inputTypes
    .filter((type) => type.value === 'text' || value.includes(type.value))
    .map((type) => type.value)
}

export interface ConfiguredModel {
  id: string
  enabled: boolean
  context_window: number | null
  max_output_tokens: number | null
  input_types: InputType[]
  efforts: string[]
  effort_mapping: Record<string, Record<string, unknown>>
}
export interface ModelOptions {
  max_output_tokens?: number
  input_types: InputType[]
  efforts: string[]
  effort_mapping: Record<string, Record<string, unknown>>
}
export function isEffortMapping(value: unknown): value is Record<string, Record<string, unknown>> {
  return isRecord(value) && Object.values(value).every(isRecord)
}
// Keep the public three-argument ABI; defaults are independent of provider context.
export function modelDefaults(id: string, _upstream: string, _protocol: Protocol): ConfiguredModel {
  return {
    id,
    enabled: true,
    context_window: null,
    max_output_tokens: null,
    input_types: [...defaultInputTypes],
    efforts: [],
    effort_mapping: {},
  }
}
export function configuredModels(
  upstream: string,
  protocol: Protocol,
  current: string,
  stored?: unknown,
): ConfiguredModel[] {
  const rows = Array.isArray(stored) ? stored : presetFor(upstream).models
  const result: ConfiguredModel[] = [],
    seen = new Set<string>()
  for (const raw of rows.slice(0, 100)) {
    if (
      !raw ||
      typeof raw.id !== 'string' ||
      !raw.id.trim() ||
      raw.id.length > 200 ||
      seen.has(raw.id.trim())
    )
      continue
    const id = raw.id.trim(),
      defaults = modelDefaults(id, upstream, protocol)
    // Older profiles used smart:true to mean "ignore all custom fields". Keep
    // that meaning on read; new profiles never send the flag.
    const legacyAuto = raw.smart === true
    const numeric = (value: unknown) =>
      typeof value === 'number' && Number.isInteger(value) && value > 0 && value <= 1048576
        ? value
        : null
    result.push({
      ...defaults,
      enabled: raw.enabled !== false,
      context_window: legacyAuto ? null : numeric(raw.context_window),
      max_output_tokens: legacyAuto ? null : numeric(raw.max_output_tokens),
      input_types: legacyAuto ? [...defaultInputTypes] : normalizeInputTypes(raw.input_types),
      efforts:
        legacyAuto || !Array.isArray(raw.efforts)
          ? []
          : [
              ...new Set<string>(
                raw.efforts.filter(
                  (s: unknown) => typeof s === 'string' && /^[a-z][a-z0-9_-]{0,31}$/.test(s),
                ),
              ),
            ].slice(0, 12),
      effort_mapping:
        !legacyAuto &&
        raw.effort_mapping &&
        typeof raw.effort_mapping === 'object' &&
        !Array.isArray(raw.effort_mapping)
          ? JSON.parse(JSON.stringify(raw.effort_mapping))
          : {},
    })
    seen.add(id)
  }
  if (!Array.isArray(stored) && current && !seen.has(current))
    result.unshift(modelDefaults(current, upstream, protocol))
  return result
}
export function selectedModelOptions(model: ConfiguredModel | undefined): ModelOptions | undefined {
  if (!model) return undefined
  const types = normalizeInputTypes(model.input_types)
  const defaultTypes = types.length === 2 && types[0] === 'text' && types[1] === 'image'
  const efforts = [...model.efforts]
  const mapping = efforts.length ? JSON.parse(JSON.stringify(model.effort_mapping)) : {}
  if (model.max_output_tokens == null && defaultTypes && !efforts.length) return undefined
  return {
    input_types: types,
    efforts,
    ...(model.max_output_tokens != null ? { max_output_tokens: model.max_output_tokens } : {}),
    effort_mapping: mapping,
  }
}
export function availableEfforts(
  upstream: string,
  protocol: Protocol,
  id: string,
  model?: ConfiguredModel,
  presetId?: string,
): string[] {
  const levels = model?.efforts?.length
    ? model.efforts
    : modelEfforts(modelFamily(upstream, id, presetId), id, protocol)
  return [...new Set(['auto', ...levels])]
}
export function mappingError(mapping: unknown, protocol?: Protocol, levels?: string[]): string {
  if (!mapping || typeof mapping !== 'object' || Array.isArray(mapping))
    return '推理参数映射需要填写 JSON 对象。'
  const allowed = new Set([
    'thinking',
    'reasoning',
    'reasoning_effort',
    'enable_thinking',
    'output_config',
    'generationConfig',
    'reasoning_split',
  ])
  for (const [level, patch] of Object.entries(mapping)) {
    if (
      !/^[a-z][a-z0-9_-]{0,31}$/.test(level) ||
      !patch ||
      typeof patch !== 'object' ||
      Array.isArray(patch)
    )
      return '每个推理等级需要对应一个参数对象。'
    if (Object.keys(patch).some((key) => !allowed.has(key)))
      return '映射只允许思考相关参数，不能覆盖模型、消息或鉴权。'
    const scoped = protocol
      ? {
          chat: ['thinking', 'reasoning_effort', 'enable_thinking', 'reasoning_split'],
          responses: ['reasoning'],
          anthropic: ['thinking', 'output_config'],
          gemini: ['generationConfig'],
        }[protocol]
      : null
    if (scoped && Object.keys(patch).some((key) => !scoped.includes(key)))
      return '映射字段与当前 API 格式不匹配。'
    if (levels && !levels.includes(level)) return '参数映射中有未声明的推理等级。'
  }
  return JSON.stringify(mapping).length > 12000 ? '推理参数映射过长。' : ''
}
