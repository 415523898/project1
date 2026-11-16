import { onScopeDispose, ref, shallowRef } from 'vue'
import { cancelSession, type StreamHooks } from '@/services/agent'
import type { ChatTurn, ToolTrace, ExperimentResult } from '@/types'
import type { LabState, StatusTone } from './state'

export interface ConversationRun {
  owner: string
  current(): boolean
  canCancel(): boolean
  id: string
  title: string
  turns: ChatTurn[]
  controller: AbortController
  token: string | null
  tool: ToolTrace | null
  busy: boolean
  stopped: boolean
  status: string
  tone: 'muted' | 'busy' | 'error'
}

const EXPERIMENT_TOOL = 'run_ml_suite'

interface RuntimeActions {
  indexBlocks(): void
  acceptExperimentResult(result: ExperimentResult, id: string, owner: string): void
  setStatus(text: string, tone?: StatusTone): void
}
type RunState = Pick<LabState, 'user' | 'sessionId' | 'busy' | 'activeSession'>

export function createConversationRuns(state: RunState, actions: RuntimeActions) {
  const { indexBlocks, acceptExperimentResult, setStatus } = actions
  const runs = new Map<string, ConversationRun>()
  let disposed = false
  const activeTool = ref<ToolTrace | null>(null)
  const controller = shallowRef<AbortController | null>(null)
  const runningSessionIds = ref<string[]>([])
  let recoveryTimer: ReturnType<typeof setTimeout> | null = null
  let recoveredSession: string | null = null

  function clearRecovery(): void {
    if (recoveryTimer !== null) clearTimeout(recoveryTimer)
    recoveryTimer = null
    recoveredSession = null
    updateRunning()
  }
  onScopeDispose(() => {
    disposed = true
    clearRecovery()
    cancelAll()
    cancelConnection()
  })

  function updateRunning(): void {
    runningSessionIds.value = [
      ...new Set([
        ...[...runs.values()].filter((run) => run.busy && run.current()).map((run) => run.id),
        ...(recoveredSession ? [recoveredSession] : []),
      ]),
    ]
  }

  function showRun(run: ConversationRun): void {
    if (disposed || !run.current() || state.user !== run.owner || state.sessionId !== run.id) return
    state.busy = run.busy
    state.activeSession = run.token
    activeTool.value = run.tool
    setStatus(run.status, run.tone)
    indexBlocks()
    // Streaming state and historical results must not change the user's panel choice.
  }

  function hooks(run: ConversationRun, current: () => boolean): StreamHooks {
    return {
      onToken: () => undefined,
      onSession: (token) => {
        if (disposed || run.stopped) {
          if (run.canCancel()) cancelSession(token)
          return
        }
        if (!current()) return
        run.token = token
        showRun(run)
      },
      onStep: (_turn, phase) => {
        if (!current()) return
        if (phase === 'tool') {
          run.status = 'agent 正在后端运行实验…'
          showRun(run)
        } else if (phase === 'connected') {
          run.status = '已连接，等待模型响应…'
          showRun(run)
        } else if (phase === 'thinking') {
          run.status = '模型正在思考…'
          showRun(run)
        } else if (phase === 'tool_call') {
          run.status = '模型正在准备工具调用…'
          showRun(run)
        } else if (phase === 'generating') {
          run.status = '模型正在生成回答…'
          showRun(run)
        } else {
          run.status = '模型正在分析并组织回答…'
          run.tone = 'busy'
          showRun(run)
        }
      },
      onRetry: (_turn, event) => {
        if (!current()) return
        const seconds = Math.ceil((event.delay_ms ?? 0) / 1000)
        run.status = `模型请求暂时失败，${seconds > 0 ? `${seconds} 秒后` : '正在'}重试（第 ${event.attempt ?? 2} 次）…`
        showRun(run)
      },
      onToolCall: (_turn, tool) => {
        if (!current()) return
        run.tool = tool
        run.status = 'agent 正在后端运行实验…'
        showRun(run)
      },
      onToolResult: (_turn, tool) => {
        if (disposed || !current()) return
        if (tool.name === EXPERIMENT_TOOL && tool.result)
          acceptExperimentResult(tool.result, run.id, run.owner)
        run.tool = null
        run.status = '后端实验已结束，等待解释…'
        showRun(run)
      },
    }
  }

  function stop(): void {
    const run = state.sessionId ? runs.get(state.sessionId) : undefined
    if (run?.busy) {
      run.stopped = true
      run.controller.abort()
      if (run.canCancel()) cancelSession(run.token)
      return
    }
    const abort = controller.value
    if (abort) abort.abort()
    cancelSession(state.activeSession)
    state.activeSession = null
  }

  function registerRun(run: ConversationRun) {
    runs.set(run.id, run)
    updateRunning()
    showRun(run)
  }
  function cancelRun(id: string) {
    const run = runs.get(id)
    if (run) {
      run.stopped = true
      run.controller.abort()
      if (run.canCancel()) cancelSession(run.token)
      runs.delete(id)
      updateRunning()
    }
  }
  function cancelAll() {
    for (const run of runs.values()) {
      run.stopped = true
      run.controller.abort()
      if (run.canCancel()) cancelSession(run.token)
    }
    runs.clear()
    updateRunning()
  }
  function cancelConnection() {
    const active = controller.value
    controller.value = null
    active?.abort()
  }
  function scheduleRecovery(poll: () => Promise<void>) {
    if (disposed) return
    recoveryTimer = setTimeout(async () => {
      recoveryTimer = null
      await poll()
    }, 1000)
  }
  return {
    activeTool,
    controller,
    runningSessionIds,
    clearRecovery,
    updateRunning,
    showRun,
    hooks,
    stop,
    registerRun,
    cancelConnection,
    cancelRun,
    cancelAll,
    scheduleRecovery,
    getRun: (id: string) => {
      const run = runs.get(id)
      return run?.current() ? run : undefined
    },
    forgetRun: (id: string) => runs.delete(id),
    get recoveredSession() {
      return recoveredSession
    },
    set recoveredSession(value: string | null) {
      recoveredSession = value
    },
  }
}
