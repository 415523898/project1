import { ApiBase } from '@/utils/api-base'
import { providerSettings, type ProviderConfig } from '@/services/agent'

export interface SelfCheckQuestion {
  id: string
  type: 'true_false' | 'single' | 'short'
  prompt: string
  point_ids: string[]
  options: Array<{ id: string; text: string }>
  basis_kind: 'learning' | 'experiment' | 'example'
}
export interface SelfCheckRules {
  objective_points: number
  short_points: number
  total_points: number
  pass_total: number
  pass_short: number
  minimum_turns: number
}
export interface SelfCheckResult {
  total: number
  short_points: number
  passed: boolean
  scope: string
  objective: Array<{
    id: string
    correct: boolean
    points: number
    answer: string
    explanation: string
  }>
  short: {
    evaluations: Array<{
      id: string
      level: 'met' | 'partial' | 'missing'
      evidence: string
      reason: string
      points: number
    }>
    feedback: string
    advice: string[]
    misconceptions: string[]
  }
}
export interface SelfCheckAttempt {
  requires_refresh?: boolean
  content_notice?: string
  id: string
  session_id: string
  method_id: string
  card_id: string
  label: string
  summary?: string
  status:
    | 'generating'
    | 'ready'
    | 'insufficient'
    | 'grading'
    | 'completed'
    | 'generate_failed'
    | 'grade_failed'
  revision: number
  created_at: number
  updated_at: number
  operation_id: string
  binding_valid: boolean
  candidate_count: number
  valid_count: number | null
  scope_note: string
  selection_partial: boolean
  rules: SelfCheckRules
  questions?: SelfCheckQuestion[]
  draft: Record<string, string>
  submitted?: Record<string, string>
  reason?: string
  missing_points?: string[]
  advice?: string[]
  covered_points?: Array<{ id: string; title: string }>
  uncovered_points?: string[]
  result?: SelfCheckResult
  failure?: { code: string; error: string } | null
  review?: Array<{
    id: string
    answer: string
    explanation: string
    rubric: Array<{ id: string; text: string; points: number }>
    evidence: Array<{ id: string; quote: string }>
    lesson_quote: string
  }>
}
export interface SelfCheckOperation {
  id: string
  attempt_id: string
  kind: 'generate' | 'grade'
  status: 'running' | 'succeeded' | 'failed' | 'cancelled' | 'interrupted'
  message: string
  calls: number
  used_tokens: number
  model?: string
  failure?: { code: string; error: string }
}
export interface SelfCheckState {
  binding: {
    method_id: string
    card_id: string
    card_missing?: boolean
    session_missing?: boolean
  } | null
  candidate_count: number
  can_start: boolean
  rules: SelfCheckRules
  attempt: SelfCheckAttempt | null
  generation_version?: number
  history: Array<{
    id: string
    method_id: string
    label: string
    status: SelfCheckAttempt['status']
    created_at: number
    result?: SelfCheckResult
  }>
}
export class SelfCheckError extends Error {
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
    throw new SelfCheckError(
      '自测接口无法读取，请确认后端已更新。',
      'backend_outdated',
      response.status,
    )
  const result = await response.json()
  if (!response.ok)
    throw new SelfCheckError(
      result.error || '自测请求失败。',
      result.code || 'request_failed',
      response.status,
    )
  return result as T
}
const aid = (id: string) => '/self-check/attempts/' + encodeURIComponent(id)
export const selfCheckApi = {
  state: (session: string, owner: string, signal: AbortSignal) =>
    request<SelfCheckState>(
      '/sessions/' + encodeURIComponent(session) + '/self-check',
      owner,
      signal,
    ),
  attempt: (id: string, owner: string, signal: AbortSignal) =>
    request<SelfCheckAttempt>(aid(id), owner, signal),
  operation: (id: string, owner: string, signal: AbortSignal) =>
    request<SelfCheckOperation>('/self-check/operations/' + encodeURIComponent(id), owner, signal),
  start: (
    session: string,
    id: string,
    fresh: boolean,
    provider: ProviderConfig,
    owner: string,
    signal: AbortSignal,
  ) =>
    request<SelfCheckOperation>('/self-check/start', owner, signal, {
      session_id: session,
      operation_id: id,
      new_attempt: fresh,
      provider: providerSettings(provider),
    }),
  draft: (
    id: string,
    revision: number,
    answers: Record<string, string>,
    owner: string,
    signal: AbortSignal,
  ) => request<SelfCheckAttempt>(aid(id) + '/draft', owner, signal, { revision, answers }),
  submit: (
    id: string,
    operation: string,
    revision: number,
    answers: Record<string, string>,
    provider: ProviderConfig,
    owner: string,
    signal: AbortSignal,
  ) =>
    request<SelfCheckOperation>(aid(id) + '/submit', owner, signal, {
      operation_id: operation,
      revision,
      answers,
      provider: providerSettings(provider),
    }),
  retry: (
    id: string,
    operation: string,
    provider: ProviderConfig,
    owner: string,
    signal: AbortSignal,
  ) =>
    request<SelfCheckOperation>(aid(id) + '/retry', owner, signal, {
      operation_id: operation,
      provider: providerSettings(provider),
    }),
  cancel: (id: string, owner: string, signal: AbortSignal) =>
    request<SelfCheckOperation>(
      '/self-check/operations/' + encodeURIComponent(id) + '/cancel',
      owner,
      signal,
      {},
    ),
}
