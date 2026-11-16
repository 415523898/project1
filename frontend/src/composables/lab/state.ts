import type { ChatTurn, SessionSummary, WorkspaceSummary } from '@/types'
import type { SnapshotContext } from '@/services/agent'
import * as authApi from '@/services/auth'
import { ApiBase } from '@/utils/api-base'
import { readSettings } from './settings'

export function initialLabState() {
  return {
    turns: [] as ChatTurn[],
    sessions: [] as SessionSummary[],
    workspaces: [] as WorkspaceSummary[],
    user: authApi.username(),
    authChecked: false,
    authExpired: false,
    messageActionBusy: false,
    sessionId: null as string | null,
    sessionTitle: '',
    activeSession: null as string | null,
    busy: false,
    connected: false,
    status: '',
    statusTone: 'muted' as 'muted' | 'busy' | 'error',
    settings: readSettings(),
    apiKey: '',
    backend: ApiBase.get(),
    experimentContext: null as SnapshotContext | null,
  }
}

export type LabState = ReturnType<typeof initialLabState>
export type StatusTone = LabState['statusTone']
