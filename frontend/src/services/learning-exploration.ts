import { ApiBase } from '@/utils/api-base'
import { readableError, type ProviderConfig } from '@/services/agent'

export interface LearningMatch {
  id: string
  name: string
  confidence: number
  reason: string
}
export interface SessionBinding {
  session_id: string
  method_id: string
  card_id: string
  card_missing?: boolean
  session_missing?: boolean
}
export interface ExplorationState {
  origin_id: string | null
  current_id: string | null
  enabled: boolean
  mode: 'free' | 'guided'
  matches: LearningMatch[]
  ready: boolean
  pending?: boolean
  binding?: SessionBinding | null
  proposal_id?: string | null
  drift_id?: string | null
  awaiting_goal?: boolean
  maintenance_error?: string
  last_error: string
  usage: {
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    calls?: number
    unknown_calls?: number
  }
}
export function emptyExploration(): ExplorationState {
  return {
    origin_id: null,
    current_id: null,
    enabled: true,
    mode: 'free',
    matches: [],
    ready: false,
    last_error: '',
    usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  }
}
async function read(response: Response): Promise<ExplorationState> {
  if (!response.ok) throw new Error(await readableError(response))
  return { ...emptyExploration(), ...((await response.json()) as ExplorationState) }
}
export async function loadExploration(
  session: string,
  signal?: AbortSignal,
): Promise<ExplorationState> {
  return read(
    await ApiBase.request(
      '/api/learning-exploration/state?session=' + encodeURIComponent(session),
      { signal },
    ),
  )
}
export interface ExplorationChange {
  source?: string
  confirm?: string
  dismiss_proposal?: boolean
  dismiss_drift?: boolean
  provider?: ProviderConfig
}
export async function saveExploration(
  session: string,
  change: ExplorationChange,
): Promise<ExplorationState> {
  return read(await ApiBase.json('/api/learning-exploration/state', { session, ...change }))
}

export interface TopicCardResult {
  created: string
  title: string
  summary: string
}

export async function createSessionCard(
  session: string,
  provider: ProviderConfig,
  signal?: AbortSignal,
): Promise<TopicCardResult> {
  const response = await ApiBase.request('/api/learning-exploration/session-card', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session, provider }),
    signal,
  })
  if (!response.ok) throw new Error(await readableError(response))
  return response.json() as Promise<TopicCardResult>
}

export async function matchSessionCard(
  session: string,
  provider: ProviderConfig,
  signal?: AbortSignal,
): Promise<{ matched: boolean; binding: SessionBinding | null; reason?: string }> {
  const response = await ApiBase.request('/api/learning-exploration/match-card', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session, provider }),
    signal,
  })
  if (!response.ok) throw new Error(await readableError(response))
  return response.json()
}
