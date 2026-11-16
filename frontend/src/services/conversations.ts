import { ApiBase } from '@/utils/api-base'
import { readableError, providerSettings } from '@/services/agent'
import type { ProviderConfig } from '@/services/agent'
import type { ChatTurn, SessionRecord, SessionSummary, WorkspaceSummary } from '@/types'

const ACTIVE_KEY = 'forest-active-session-v1'

export function isUntitledSession(title: string): boolean {
  return !title.trim() || title.trim() === '新的对话'
}

export function needsSessionTitle(
  title: string,
  turns: ChatTurn[],
  source?: SessionSummary['title_source'],
): boolean {
  if (source === 'manual' || source === 'ai') return false
  if (source === 'fallback' || source === 'branch' || isUntitledSession(title)) return true
  const first = sessionTitle(turns).replace(/…$/, '')
  const value = title.trim().replace(/…$/, '')
  if (value === first) return true
  const branch = value.replace(/^分支\s*·\s*/, '')
  return branch !== value && !!branch && first.startsWith(branch)
}

export function sessionTitle(turns: ChatTurn[]): string {
  for (const turn of turns) {
    if (typeof turn.question === 'string' && turn.question.trim()) {
      const text = turn.question.trim().replace(/\s+/g, ' ')
      return text.length > 60 ? text.slice(0, 60) + '…' : text
    }
  }
  return '新的对话'
}

export function serializableTurns(turns: ChatTurn[]): ChatTurn[] {
  return turns.map((turn) => {
    if (!turn.tools?.length) return { ...turn }
    return { ...turn, tools: turn.tools.map((tool) => ({ ...tool, result: tool.result })) }
  })
}

export function activeSessionId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_KEY)
  } catch {
    return null
  }
}

export function rememberActiveSession(id: string | null): void {
  try {
    if (id) localStorage.setItem(ACTIVE_KEY, id)
    else localStorage.removeItem(ACTIVE_KEY)
  } catch {
    // Remembering the active conversation is best effort; no server mutation depends on it.
  }
}

export function useConversationApi() {
  async function list(): Promise<SessionSummary[]> {
    try {
      const response = await ApiBase.request('/api/conversations')
      if (!response.ok) throw new Error(await readableError(response))
      const data = (await response.json()) as { sessions?: SessionSummary[] }
      return data.sessions ?? []
    } catch {
      return []
    }
  }

  async function workspaces(): Promise<WorkspaceSummary[]> {
    try {
      const response = await ApiBase.request('/api/conversations/workspaces')
      if (!response.ok) return []
      const data = (await response.json()) as { workspaces?: WorkspaceSummary[] }
      return data.workspaces ?? []
    } catch {
      return []
    }
  }

  async function load(id: string, signal?: AbortSignal): Promise<SessionRecord | null> {
    const response = await ApiBase.request('/api/conversations/get?id=' + encodeURIComponent(id), {
      signal,
    })
    if (!response.ok) {
      const error = new Error(await readableError(response)) as Error & { status: number }
      error.status = response.status
      throw error
    }
    return (await response.json()) as SessionRecord
  }

  async function save(
    id: string | null,
    turns: ChatTurn[],
    title?: string,
  ): Promise<SessionRecord | null> {
    if (!turns.length && !id) return createEmpty()
    const response = await ApiBase.json('/api/conversations/save', {
      id: id ?? undefined,
      title: title ?? sessionTitle(turns),
      title_source: 'fallback',
      view: document.body.dataset.view ?? 'chat',
      turns: serializableTurns(turns),
    })
    if (!response.ok) throw new Error(await readableError(response))
    return (await response.json()) as SessionRecord
  }

  async function rename(id: string, title: string): Promise<SessionRecord | null> {
    const response = await ApiBase.json('/api/conversations/save', {
      id,
      title,
      title_source: 'manual',
    })
    if (!response.ok) throw new Error(await readableError(response))
    return (await response.json()) as SessionRecord
  }

  async function name(
    id: string,
    config: ProviderConfig,
  ): Promise<{ title: string; source: SessionSummary['title_source'] }> {
    const response = await ApiBase.json('/api/conversations/title', {
      id,
      ...providerSettings(config),
    })
    if (!response.ok) throw new Error(await readableError(response))
    const value = (await response.json()) as {
      title?: string
      title_source?: SessionSummary['title_source']
    }
    return { title: value.title ?? '', source: value.title_source ?? 'ai' }
  }

  async function createEmpty(): Promise<SessionRecord | null> {
    const response = await ApiBase.json('/api/conversations/save', {
      title: '',
      turns: [],
      view: document.body.dataset.view ?? 'chat',
    })
    if (!response.ok) throw new Error(await readableError(response))
    return (await response.json()) as SessionRecord
  }

  async function remove(id: string, syncCard = false): Promise<boolean> {
    const response = await ApiBase.json('/api/conversations/delete', {
      id,
      delete_choice: syncCard ? 'both' : 'only',
    })
    if (!response.ok) throw new Error(await readableError(response))
    return true
  }

  async function fork(id: string, event_id: string): Promise<SessionRecord> {
    const response = await ApiBase.json('/api/conversations/fork', { id, event_id })
    if (!response.ok) throw new Error(await readableError(response))
    return (await response.json()) as SessionRecord
  }

  return { list, workspaces, load, save, rename, name, createEmpty, remove, fork }
}
