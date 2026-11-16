import { readableError } from '@/services/agent'
import { ApiBase } from '@/utils/api-base'
import type { Catalog, ExperimentResult, MethodSpec, ParameterSpec, SourceSpec } from '@/types'

export interface RunRequest {
  experiment_id?: string
  experiment_version?: number
  kind?: 'library' | 'sklearn'
  reason?: string
  methods: string[]
  params?: Record<string, unknown>
  source?: string | null
  session?: string | null
  target?: string | null
  group?: string | null
  time?: string | null
  figures?: boolean
}

export async function fetchCatalog(): Promise<Catalog> {
  const response = await ApiBase.request('/api/experiments/catalog')
  if (!response.ok) throw new Error(await readableError(response))
  return (await response.json()) as Catalog
}

export async function runExperiment(request: RunRequest): Promise<ExperimentResult> {
  const reason = request.reason ?? '从右侧栏参数面板运行一次实验。'
  const source = request.source || 'iris'
  const body: Record<string, unknown> =
    (request.kind ?? 'library') === 'sklearn'
      ? {
          reason,
          method: request.methods[0],
          parameters: request.params ?? {},
          source,
          session: request.session ?? null,
        }
      : {
          reason,
          methods: request.methods,
          params: request.params ?? {},
          source,
          session: request.session ?? null,
          target: request.target ?? null,
          group: request.group ?? null,
          time: request.time ?? null,
        }
  if (typeof request.figures === 'boolean') body.figures = request.figures
  if (request.experiment_id) {
    body.experiment_id = request.experiment_id
    body.experiment_version = request.experiment_version
  }
  const response = await ApiBase.json('/api/experiments/run', body)
  if (!response.ok) throw new Error(await readableError(response))
  return (await response.json()) as ExperimentResult
}

export function methodSpec(catalog: Catalog | null, id: string | null): MethodSpec | null {
  if (!catalog || !id) return null
  return (
    (catalog.library ?? []).find((item) => item.id === id) ??
    (catalog.methods ?? []).find((item) => item.id === id) ??
    null
  )
}

export function methodGroups(
  method: MethodSpec | null,
): Array<{ name: string; params: ParameterSpec[] }> {
  if (!method) return []
  const groups = method.groups ?? []
  if (groups.length) return groups
  const order: string[] = []
  const buckets: Record<string, ParameterSpec[]> = {}
  for (const spec of method.params ?? []) {
    const name = spec.group || '参数'
    if (!buckets[name]) {
      buckets[name] = []
      order.push(name)
    }
    buckets[name].push(spec)
  }
  return order.map((name) => ({ name, params: buckets[name] ?? [] }))
}

export function methodParams(method: MethodSpec | null): ParameterSpec[] {
  return methodGroups(method).flatMap((group) => group.params)
}

export function sourceLabel(catalog: Catalog | null, id: string | null): string {
  if (!id) return '本地数据集'
  if (id === 'page') return '数据入口确认的数据'
  if (id.startsWith('file:')) return '本次对话上传的表格'
  const found = (catalog?.sources ?? []).find((item) => item.id === id)
  return found ? found.label : id
}

export function sourceColumns(
  result: ExperimentResult | null,
  source?: SourceSpec | null,
): string[] {
  const names = result?.data?.column_names
  if (Array.isArray(names)) return [...new Set(names.map(String).filter((name) => name.trim()))]
  const features = result?.data?.features
  const list = [
    ...(Array.isArray(features) ? features : []),
    ...(source?.columns ?? []),
    result?.data?.target,
    result?.data?.group,
    result?.data?.time,
  ]
  return [
    ...new Set(
      list
        .filter((name) => name !== undefined && name !== null)
        .map(String)
        .filter((name) => name.trim()),
    ),
  ]
}

export function resultSource(result: ExperimentResult | null): string {
  const id = result?.dataset ?? result?.data?.dataset
  if (typeof id === 'string' && id) return id
  if (result && typeof result.source === 'string' && result.source) {
    return result.source.startsWith('本地数据集 ')
      ? result.source.slice('本地数据集 '.length)
      : result.source
  }
  const dataset = result?.data?.dataset
  if (typeof dataset === 'string' && dataset) return dataset
  return 'iris'
}

/** Scope the parameter editor to the method's own data and parameters in a multi-method run. */
export function methodContext(result: ExperimentResult, id: string | null): ExperimentResult {
  const entry = id ? result.methods?.[id] : undefined
  const dataset = result.datasets?.find((item) => id && item.methods?.includes(id))
  const data =
    entry?.data && typeof entry.data === 'object'
      ? (entry.data as ExperimentResult['data'])
      : result.data
  return {
    ...result,
    methods: entry && id ? { [id]: entry } : {},
    data,
    dataset:
      typeof entry?.dataset === 'string' ? entry.dataset : (dataset?.dataset ?? result.dataset),
    dataset_label:
      typeof entry?.dataset_label === 'string'
        ? entry.dataset_label
        : (dataset?.label ?? result.dataset_label),
    source: typeof entry?.source === 'string' ? entry.source : (dataset?.source ?? result.source),
    split:
      entry?.split && typeof entry.split === 'object'
        ? (entry.split as ExperimentResult['split'])
        : result.split,
    parameters:
      entry?.params && typeof entry.params === 'object'
        ? (entry.params as Record<string, unknown>)
        : result.parameters,
  }
}

export function appliedParams(result: ExperimentResult | null): Record<string, unknown> {
  if (!result) return {}
  const top = result.parameters
  if (top && typeof top === 'object' && !Array.isArray(top)) return top as Record<string, unknown>
  for (const entry of Object.values(result.methods ?? {})) {
    const params = (entry as { params?: unknown }).params
    if (params && typeof params === 'object' && !Array.isArray(params)) {
      return params as Record<string, unknown>
    }
  }
  return {}
}
