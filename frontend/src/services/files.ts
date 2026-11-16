import { readableError, providerSettings, type ProviderConfig } from '@/services/agent'
import { ApiBase } from '@/utils/api-base'
import type { DatasetChoice, UploadedFile } from '@/types'

export interface DatasetSuggestion {
  id: string
  task: 'classification' | 'regression' | 'clustering'
  target: string | null
  time: string | null
  group: string | null
  reason: string
  model: string
  usage: { total_tokens?: number } | null
}

export interface CurrentDatasetInfo {
  selection_mode: 'manual' | 'auto'
  dataset: DatasetChoice & { description: string; notes?: string[] }
  reason?: string
  notes: string[]
}
export interface DatasetPage {
  dataset: string
  label: string
  kind: 'builtin' | 'upload'
  column_names: string[]
  total_rows: number
  offset: number
  limit: number
  rows: Array<Array<string | null>>
}
export async function previewDataset(
  dataset: string,
  offset = 0,
  limit = 50,
  signal?: AbortSignal,
): Promise<DatasetPage> {
  const query = new URLSearchParams({ dataset, offset: String(offset), limit: String(limit) })
  const response = await ApiBase.request('/api/files/preview?' + query, { signal })
  if (!response.ok) throw new Error(await readableError(response))
  return response.json()
}
export async function currentDatasetInfo(
  session: string,
  signal?: AbortSignal,
): Promise<CurrentDatasetInfo | null> {
  const response = await ApiBase.request(
    '/api/files/current?session=' + encodeURIComponent(session),
    { signal },
  )
  if (!response.ok) throw new Error(await readableError(response))
  return ((await response.json()) as { current_dataset: CurrentDatasetInfo | null }).current_dataset
}

export async function suggestDataset(
  id: string,
  config: ProviderConfig,
  signal?: AbortSignal,
): Promise<DatasetSuggestion> {
  const response = await ApiBase.request('/api/files/suggest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({ id, ...providerSettings(config) }),
  })
  if (!response.ok) throw new Error(await readableError(response))
  return response.json()
}

export async function datasetLibrary(): Promise<{
  files: DatasetChoice[]
  builtins: DatasetChoice[]
}> {
  const response = await ApiBase.request('/api/files')
  if (!response.ok) throw new Error(await readableError(response))
  return response.json()
}

export async function configureDataset(
  id: string,
  values: { target: string | null; task: string; time: string | null; group: string | null },
): Promise<DatasetChoice> {
  const response = await ApiBase.json('/api/files/configure', { id, ...values })
  if (!response.ok) throw new Error(await readableError(response))
  return response.json()
}

export async function selectDataset(
  session: string,
  dataset: string | null,
): Promise<DatasetChoice | null> {
  const response = await ApiBase.json('/api/files/select', { session, dataset })
  if (!response.ok) throw new Error(await readableError(response))
  return ((await response.json()) as { selected_dataset: DatasetChoice | null }).selected_dataset
}

export async function uploadTable(session: string, file: File): Promise<UploadedFile> {
  const body = new FormData()
  body.append('file', file)
  body.append('session', session)
  const response = await ApiBase.request('/api/files', { method: 'POST', body })
  if (!response.ok) throw new Error(await readableError(response))
  return (await response.json()) as UploadedFile
}

export async function listTables(session: string): Promise<UploadedFile[]> {
  const response = await ApiBase.request(`/api/files?session=${encodeURIComponent(session)}`)
  if (!response.ok) throw new Error(await readableError(response))
  const data = (await response.json()) as { files?: UploadedFile[] }
  return data.files ?? []
}

export async function deleteTable(id: string): Promise<{ deleted: string; label: string }> {
  const response = await ApiBase.json('/api/files/delete', { id })
  if (!response.ok) throw new Error(await readableError(response))
  return response.json()
}

export function fileSizeLabel(file: File): string {
  if (file.size < 1024) return `${file.size} B`
  if (file.size < 1024 * 1024) return `${Math.round(file.size / 1024)} KB`
  return `${(file.size / 1048576).toFixed(1)} MB`
}
