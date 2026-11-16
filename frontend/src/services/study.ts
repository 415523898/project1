import { ApiBase } from '@/utils/api-base'
import type { ProviderConfig } from '@/services/agent'
import type { SessionBinding } from '@/services/learning-exploration'

export interface StudyCardModel {
  card_id: string
  type: 'manual' | 'conversation' | 'method'
  title: string
  summary: string
  body: string
  method_ids: string[]
  evidence_status: string
  manual_fields: string[]
  revision: number
  binding?: SessionBinding
}
export interface StudyNode {
  card_id: string
  node_id: string
  x: number
  y: number
  group_id: string | null
  position_locked: boolean
  level_pin: number | null
  level: number
  revision: number
}
export interface StudySource {
  source_id: string
  card_id: string
  session_id: string | null
  availability: string
  adopted_facts: string[]
  event_refs: string[]
  revision: number
  experiment_id?: string | null
  version?: number | null
  turn_number?: number
  turn_start_seq?: number
  topic_key?: string
  snapshot_fingerprint?: string
  cutoff_seq?: number
  precision?: 'event' | 'legacy'
  event_turns?: Record<string, number>
}
export interface StudyEdge {
  edge_id: string
  from_id: string
  to_id: string
  type: 'prerequisite' | 'suggested_next' | 'alternative' | 'related'
  why: string
  revision: number
  semantic_locked: boolean
  created_by?: string
  manual_fields?: string[]
}
export type StudySide = 'left' | 'right' | 'top' | 'bottom'
export interface StudyEdgeRoute {
  edge_id: string
  waypoints: Array<{ x: number; y: number }>
  source_side?: StudySide | 'auto'
  target_side?: StudySide | 'auto'
  mode?: 'auto' | 'guided'
  route_locked?: boolean
  revision?: number
}
export interface StudyProgress {
  phase?: string
  message?: string
  last_action?: string
  completed_steps?: number
  changed_batches?: number
  graph_revision?: number
  layout_revision?: number
  event_sequence?: number
  elapsed_ms?: number
}
export interface StudyWorkspace {
  schema_version: 2
  mode: 'study_v2'
  enabled: true
  graph_revision: number
  layout_revision: number
  cards: StudyCardModel[]
  nodes: StudyNode[]
  edges: StudyEdge[]
  sources: StudySource[]
  groups: Array<{ group_id: string; title: string; revision: number }>
  edge_routes: StudyEdgeRoute[]
  capabilities: {
    manual: boolean
    canvas: boolean
    ai_relations: boolean
    ai_session: boolean
    history?: boolean
  }
  history?: {
    undo: { revision_id: string; label: string } | null
    redo: { revision_id: string; label: string } | null
    undo_count: number
    redo_count: number
  }
  pending_operation?: {
    operation_id: string
    kind: 'ai-relations'
    instruction: string
    progress?: StudyProgress
  } | null
  warnings?: StudyWarning[]
}
export interface StudyWarning {
  code: 'cycle' | 'number_reversed'
  card_ids: string[]
  edge_ids: string[]
  message: string
}
export interface StudyAiOptions {
  instruction: string
  cardIds: string[]
  allowManual: boolean
  includeRemoved: boolean
  arrangeLayout?: boolean
  connectAll?: boolean
  provider: ProviderConfig
}
export type StudyMode = StudyWorkspace
export type StudyOperation = { op: string; [key: string]: unknown }
export interface StudyChanges {
  schema_version: 2
  operation_id: string
  base_graph_revision: number
  base_layout_revision?: number
  operations: StudyOperation[]
  delete_choice?: 'only' | 'both'
}
export interface StudyResult {
  operation_id: string
  status: 'succeeded'
  changed: boolean
  graph_revision: number
  layout_revision: number
  id_map: Record<string, string>
  revision_id: string | null
  warnings?: StudyWarning[]
  ai_summary?: {
    created: number
    updated: number
    deleted: number
    protected: number
    scope_count: number
    message: string
    moved?: number
    fixed?: number
    strategy?: string
    rounds?: number
    steps?: number
    checked?: number
    downstream?: number
    isolated?: number
    missing_reference?: number
    restored?: number
    model_links?: number
    reference_links?: number
    pruned_shortcuts?: number
    declined_reference?: number
    reference_fallbacks?: string[]
    card_ids?: string[]
    declined?: Array<{ from_id: string; to_id: string; reason: string; source: string }>
    isolated_details?: Array<{ card_id: string; reason: string; suggestion?: string }>
  }
  progress?: StudyProgress
  history_action?: { direction: 'undo' | 'redo'; label: string }
  projection?: {
    base_graph_revision: number
    base_layout_revision: number
    changes: Array<{
      table: 'cards' | 'nodes' | 'edges' | 'edge_routes' | 'sources' | 'groups'
      id: string
      value: Record<string, unknown> | null
    }>
    levels: Record<string, number>
    history: StudyWorkspace['history']
  }
}
export type StudyOperationState =
  | StudyResult
  | {
      operation_id: string
      status: 'running' | 'failed'
      progress?: StudyProgress
      partial_result?: StudyResult
      failure?: { code: string; error?: string } | null
    }
export class StudyApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message)
  }
}

async function request<T>(
  path: string,
  signal: AbortSignal,
  body?: StudyChanges | Record<string, never>,
  owner?: string,
): Promise<T> {
  const headers: Record<string, string> = {}
  // A concurrency guard only; authentication and storage ownership still come from the server session.
  if (owner) headers['X-Study-Owner'] = encodeURIComponent(owner)
  if (body) headers['Content-Type'] = 'application/json'
  const response = await ApiBase.request('/api/study' + path, {
    signal,
    headers,
    ...(body ? { method: 'POST', body: JSON.stringify(body) } : {}),
  })
  const data = await response.json()
  if (!response.ok)
    throw new StudyApiError(
      data.error || '学习路线请求失败。',
      response.status,
      data.code || 'request_failed',
    )
  return data as T
}

export const studyApi = {
  async workspace(signal: AbortSignal, owner?: string): Promise<StudyMode> {
    const data = await request<StudyMode>('/workspace', signal, undefined, owner)
    if (data.schema_version !== 2 || data.mode !== 'study_v2')
      throw new StudyApiError('学习路线协议不兼容，请刷新服务。', 409, 'schema_version')
    return data
  },
  changes: (payload: StudyChanges, signal: AbortSignal, owner?: string) =>
    request<StudyOperationState>('/changes', signal, payload, owner),
  operation: (id: string, signal: AbortSignal, owner?: string) =>
    request<StudyOperationState>('/operations/' + encodeURIComponent(id), signal, undefined, owner),
  cancel: (id: string, signal: AbortSignal, owner?: string) =>
    request<StudyOperationState>(
      '/operations/' + encodeURIComponent(id) + '/cancel',
      signal,
      {},
      owner,
    ),
  revision: (signal: AbortSignal, owner?: string) =>
    request<{ graph_revision: number; layout_revision: number }>(
      '/revision',
      signal,
      undefined,
      owner,
    ),
}
export type StudyApi = Omit<typeof studyApi, 'cancel' | 'revision'> & {
  cancel?: typeof studyApi.cancel
  revision?: typeof studyApi.revision
}
