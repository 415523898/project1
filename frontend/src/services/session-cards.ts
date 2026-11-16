import { ApiBase } from '@/utils/api-base'
import type { ProviderConfig } from '@/services/agent'
import type { SessionBinding } from '@/services/learning-exploration'
import type { StudyCardModel, StudySource, StudyWorkspace, StudyResult } from '@/services/study'

export interface SessionCardJob {
  operation_id: string
  session_id: string
  status: 'running' | 'succeeded' | 'failed' | 'cancelled' | 'interrupted'
  snapshot?: {
    turns: number
    cutoff_seq: number
    fingerprint: string
    evidence_quality: string
    source_scan_complete: boolean
    unit_count: number
    invalid_records: number
  }
  progress?: {
    phase: string
    message: string
    completed_chunks: number
    total_chunks: number
    completed_cards: number
    total_cards: number
    calls: number
    used_tokens: number
    usage_estimated: boolean
    cached_chunks?: number
  }
  reused?: boolean
  timings?: {
    context_ms?: number
    preparation_ms?: number
    queued_ms?: number
    model_ms?: number
    commit_ms?: number
    route_wait_ms?: number
    server_ms?: number
  }
  summary?: {
    created: number
    updated: number
    protected: number
    excluded: number
    sources: number
    turns: number
    message: string
    coverage: Record<string, number>
    source_scan_complete: boolean
    extraction_complete: boolean
    evidence_quality: string
  } | null
  failure?: { code: string; error: string } | null
  elapsed_ms?: number
  result?: StudyResult | null
}
export interface SessionCardList {
  stamp?: string
  binding?: SessionBinding | null
  cards: StudyCardModel[]
  sources: StudySource[]
  history?: StudyWorkspace['history']
  job: SessionCardJob | null
  graph_revision: number
  layout_revision: number
}
export interface SourceLocation {
  session_id: string
  turn_index: number
  event_ref: string
  experiment_id?: string | null
  version?: number | null
  precision?: string
  superseded?: boolean
}
export class SessionCardsError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message)
  }
}

async function request<T>(
  path: string,
  owner: string,
  signal: AbortSignal,
  body?: unknown,
): Promise<T> {
  const response = await ApiBase.request('/api/study' + path, {
    signal,
    headers: {
      'X-Study-Owner': encodeURIComponent(owner),
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
    },
    ...(body === undefined ? {} : { method: 'POST', body: JSON.stringify(body) }),
  })
  if (!response.headers.get('Content-Type')?.includes('json'))
    throw new SessionCardsError(
      response.status === 404
        ? '后端尚未加载会话整理接口，请更新后端服务。'
        : '会话整理接口返回了无法读取的响应。',
      response.status === 404 ? 'backend_outdated' : 'invalid_response',
      response.status === 404 ? 409 : response.status,
    )
  const data = await response.json()
  if (!response.ok)
    throw new SessionCardsError(
      data.error || '会话整理请求失败。',
      data.code || 'request_failed',
      response.status,
    )
  return data as T
}

export const sessionCardsApi = {
  list: (id: string, owner: string, signal: AbortSignal, stamp?: string) =>
    request<SessionCardList | { unchanged: true; stamp: string }>(
      '/sessions/' +
        encodeURIComponent(id) +
        '/cards' +
        (stamp ? '?since=' + encodeURIComponent(stamp) : ''),
      owner,
      signal,
    ),
  start: (
    payload: {
      operation_id: string
      session_id: string
      instruction: string
      provider: ProviderConfig
    },
    owner: string,
    signal: AbortSignal,
  ) => request<SessionCardJob>('/organize/session', owner, signal, payload),
  job: (id: string, owner: string, signal: AbortSignal) =>
    request<SessionCardJob>('/organize/session/' + encodeURIComponent(id), owner, signal),
  cancel: (id: string, owner: string, signal: AbortSignal) =>
    request<SessionCardJob>(
      '/organize/session/' + encodeURIComponent(id) + '/cancel',
      owner,
      signal,
      {},
    ),
  locate: (id: string, owner: string, signal: AbortSignal, eventRef?: string) =>
    request<SourceLocation>(
      '/sources/' +
        encodeURIComponent(id) +
        '/locate' +
        (eventRef ? '?event_ref=' + encodeURIComponent(eventRef) : ''),
      owner,
      signal,
    ),
}
