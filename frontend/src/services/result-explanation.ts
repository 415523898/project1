import { reactive } from 'vue'
import { ApiBase } from '@/utils/api-base'
import {
  readableError,
  connectionError,
  providerSettings,
  type ProviderConfig,
} from '@/services/agent'
import { methodContext } from '@/services/experiments'
import { resultTables } from '@/utils/result-summary'
import { messages } from '@/utils/result-format'
import { resultIntegrity } from '@/utils/result-integrity'
import type { ExperimentResult, MetricEntry } from '@/types'

export interface ExplanationInput {
  experiment_id?: string
  experiment_version?: number
  session: string
  method: string
  label: string
  metrics: Record<string, unknown>
  tables: unknown[]
  params?: unknown
  data?: unknown
  split?: unknown
  evaluation_scope?: unknown
  source?: unknown
  warnings: string[]
  figures: string[]
}
export interface ExplanationState {
  text: string
  busy: boolean
  error: string
  model: string
  usage: { total_tokens?: number } | null
  loaded?: boolean
  loading?: boolean
}
const states = new Map<string, ExplanationState>()
const loads = new WeakMap<ExplanationState, Promise<void>>()
const metadata = new Set([
  'method',
  'label',
  'task',
  'category',
  'group',
  'tables',
  'figures',
  'notes',
  'warnings',
  'data',
  'params',
  'parameters',
  'split',
  'evaluation_scope',
  'dataset',
  'dataset_label',
  'source',
  'error',
])

export function explanationInput(
  result: ExperimentResult,
  method: string,
  entry: MetricEntry,
  session: string,
  label: string,
): ExplanationInput {
  const scoped = methodContext(result, method)
  const metrics =
    entry.metrics ?? Object.fromEntries(Object.entries(entry).filter(([key]) => !metadata.has(key)))
  const tables = resultTables(entry)
    .slice(0, 8)
    .map((table) => ({
      name: table.label,
      columns: table.columns.slice(0, 32),
      total_rows: table.total,
      rows: table.rows.slice(0, 12).map((row) => row.slice(0, 32)),
      truncated: table.truncated || table.total > 12,
      ...(table.raw ? { raw: table.raw } : {}),
    }))
  return {
    session,
    method,
    label,
    experiment_id: result.experiment_id,
    experiment_version: result.experiment_version,
    metrics,
    tables,
    params: entry.params ?? scoped.parameters,
    data: scoped.data,
    split: scoped.split,
    evaluation_scope: entry.evaluation_scope ?? metrics.evaluation_scope,
    source: scoped.dataset_label ?? scoped.source ?? scoped.dataset,
    warnings: [
      ...new Set([
        ...messages(result.warnings),
        ...messages(entry.warnings),
        ...resultIntegrity(entry),
      ]),
    ],
    figures: (Array.isArray(entry.figures) ? entry.figures : (result.figures ?? []))
      .map((figure) => (typeof figure === 'string' ? figure : String(figure?.name ?? '')))
      .filter(Boolean),
  }
}

export function explanationState(
  owner: string,
  input: ExplanationInput,
  base: string,
  model: string,
): ExplanationState {
  const signature = JSON.stringify(['100-150-characters', ApiBase.get(), owner, base, model, input])
  let state = states.get(signature)
  if (!state) {
    state = reactive({ text: '', busy: false, error: '', model: '', usage: null })
    states.set(signature, state)
    if (states.size > 256) states.delete(states.keys().next().value!)
  }
  return state
}

export async function generateExplanation(
  state: ExplanationState,
  input: ExplanationInput,
  config: ProviderConfig,
  force = false,
): Promise<void> {
  if (state.busy || (!force && (state.text || state.error))) return
  state.busy = true
  state.error = ''
  try {
    const response = await ApiBase.json('/api/experiments/explain', {
      ...input,
      ...providerSettings(config),
      force,
    })
    if (!response.ok) throw new Error(await readableError(response))
    const value = (await response.json()) as {
      text?: string
      model?: string
      usage?: ExplanationState['usage']
    }
    if (!value.text?.trim()) throw new Error('模型未按要求返回解读，请点击重新解读。')
    state.text = value.text
    state.model = value.model ?? config.model
    state.usage = value.usage ?? null
  } catch (error) {
    state.error = connectionError(error, config.api_key)
  } finally {
    state.busy = false
  }
}

export function loadExplanation(state: ExplanationState, input: ExplanationInput): Promise<void> {
  if (state.loaded || state.text) return Promise.resolve()
  const pending = loads.get(state)
  if (pending) return pending
  state.loading = true
  const request = (async () => {
    try {
      const response = await ApiBase.json(
        '/api/experiments/explain/saved',
        input as unknown as Record<string, unknown>,
      )
      if (!response.ok) throw new Error(await readableError(response))
      const value = (await response.json()) as {
        text?: string
        model?: string
        usage?: ExplanationState['usage']
      }
      state.error = ''
      if (value.text?.trim()) {
        state.text = value.text
        state.model = value.model ?? ''
        state.usage = value.usage ?? null
        state.error = ''
      }
      state.loaded = true
    } catch (error) {
      state.error = `读取已保存解读失败：${connectionError(error)}`
    } finally {
      state.loading = false
      loads.delete(state)
    }
  })()
  loads.set(state, request)
  return request
}
