import { ApiBase } from '@/utils/api-base'
import { entryMetrics } from '@/utils/result-format'
import { hideRetriedFailures } from '@/utils/tool-traces'
import {
  appendActivityText,
  appendActivityTool,
  endActivityMessage,
  finalAnswer,
  finishActivity,
  resetActivityMessage,
} from '@/utils/turn-activity'
import type {
  AgentEvent,
  ChatAttachment,
  ChatTurn,
  DatasetChoice,
  DetailLevel,
  ExperimentResult,
  MetricEntry,
  ToolFigure,
  ToolTrace,
  TurnImage,
} from '@/types'

export interface ProviderConfig {
  base_url: string
  model: string
  api_key: string
  credential_id?: string
  allow_tools: boolean
  protocol?: import('@/utils/model-providers').Protocol
  provider_family?: string
  reasoning_effort?: string
  model_options?: import('@/utils/model-config').ModelOptions
}

/** Carry the same protocol and effort into every auxiliary model request. */
export function providerSettings(config: Omit<ProviderConfig, 'allow_tools'>) {
  return {
    base_url: config.base_url,
    model: config.model,
    api_key: config.api_key,
    ...(config.credential_id ? { credential_id: config.credential_id } : {}),
    ...(config.protocol ? { protocol: config.protocol } : {}),
    ...(config.provider_family ? { provider_family: config.provider_family } : {}),
    ...(config.reasoning_effort ? { reasoning_effort: config.reasoning_effort } : {}),
    ...(config.model_options ? { model_options: config.model_options } : {}),
  }
}

export interface SnapshotFile {
  id: string
  name: string
  dataset: string
  rows: number
  columns: number
  column_names: string[]
  dtypes: Record<string, string>
  target: string | null
  task: string
  head: unknown[][]
}

export interface SnapshotContext {
  sidebar_view?: {
    selected_id: string | null
    hidden_source_keys: string[]
    active_versions: Record<string, number>
  }
  selected_dataset?: DatasetChoice | null
  captured_at: string
  engine: string
  draft: Record<string, unknown>
  current: Record<string, unknown> | null
  capabilities: Record<string, unknown>
  notes: string[]
  files?: SnapshotFile[]
}

export const MAX_HISTORY_TURNS = 6

export function bootstrapContext(): SnapshotContext {
  return {
    captured_at: new Date().toISOString(),
    engine: 'server-experiment-panel',
    draft: { noise: 0, n_samples: 0, train_ratio: 0.7, seed: 42 },
    current: null,
    capabilities: {
      independent_fast_training_tool: true,
      tool_execution: 'server',
      tool_turn_limit: 3,
      experiment_panel: true,
    },
    notes: [
      '由模型根据问题和方法选择合适数据；手动指定为可选覆盖。实验由服务端执行，结果显示在右侧栏。',
    ],
  }
}

export function snapshotLabel(context: SnapshotContext | null): string {
  if (!context) return '尚未训练'
  const current = context.current as { label?: string } | null
  if (current?.label) return current.label
  const draft = context.draft as { dataset?: string; n_samples?: number } | undefined
  if (draft?.n_samples) return `${draft.dataset ?? '数据'}（${draft.n_samples} 条）`
  return '本地数据集'
}

export function cleanError(message: string, key?: string): string {
  const text = String(message ?? '')
  if (!key) return text
  return text.split(key).join('[已隐藏]')
}

export function connectionError(error: unknown, key?: string): string {
  const text = cleanError(error instanceof Error ? error.message : String(error), key)
  return /^(Failed to fetch|fetch failed|network error|Load failed|NetworkError.*|terminated)$/i.test(
    text,
  )
    ? '与本地服务的连接中断。已完成的实验结果仍保留，请在服务恢复后继续。'
    : text
}

export type ErrorContext = 'session' | 'credentials'

export async function readableError(
  response: Response,
  context: ErrorContext = 'session',
): Promise<string> {
  // A rejected password is also HTTP 401, but does not mean an existing session expired.
  if (response.status === 401 && context === 'session')
    return '登录已失效，请重新登录后继续；已有会话和实验结果仍保留。'
  if (response.status === 501 || response.status === 404) {
    return context === 'credentials'
      ? '账号服务暂时不可用，请稍后重试。'
      : '本地服务尚未返回该接口，请确认 Flask 后端已在 18737 端口启动。'
  }
  const fallback =
    context === 'credentials' && response.status === 401
      ? '用户名或密码不正确。'
      : context === 'credentials' && response.status === 429
        ? '登录尝试过多，请稍后重试。'
        : context === 'credentials' && response.status >= 500
          ? '账号服务暂时不可用，请稍后重试。'
          : `接口返回 HTTP ${response.status}。`
  try {
    const data = (await response.json()) as { error?: unknown } | null
    return typeof data?.error === 'string' && data.error.trim() ? data.error : fallback
  } catch {
    return fallback
  }
}

function settlePendingTools(turn: ChatTurn, message: string, hooks: StreamHooks): void {
  for (const tool of turn.tools ?? []) {
    if (tool.status !== 'running') continue
    tool.status = 'error'
    tool.result = { error: message }
    hooks.onToolResult(turn, tool)
  }
}

export function toolResultStatus(result: ExperimentResult | null): ToolTrace['status'] {
  return !result ||
    result.error ||
    (result.failures?.length && !Object.keys(result.methods ?? {}).length)
    ? 'error'
    : 'complete'
}

export interface StreamHooks {
  onAccepted?: () => void
  onUserMessage?: (turn: ChatTurn) => void
  onToken: (turn: ChatTurn) => void
  onStep: (turn: ChatTurn, phase: string) => void
  onToolCall: (turn: ChatTurn, tool: ToolTrace) => void
  onToolResult: (turn: ChatTurn, tool: ToolTrace) => void
  onSession?: (token: string) => void
  onRetry?: (turn: ChatTurn, event: AgentEvent) => void
}

export interface StreamHandle {
  session: string | null
}

const TOKEN_FLUSH_MS = 16
const MAX_PENDING_TOKEN_CHARS = 4096

export async function consumeStream(
  response: Response,
  turn: ChatTurn,
  key: string,
  signal: AbortSignal,
  hooks: StreamHooks,
): Promise<StreamHandle> {
  const handle: StreamHandle = { session: null }
  const contentType = response.headers.get('Content-Type') ?? ''
  if (!contentType.includes('text/event-stream')) {
    const data = (await response.json()) as {
      answer?: string
      model?: string
      usage?: ChatTurn['usage']
      elapsed_ms?: number
    }
    appendActivityText(turn, cleanError(data.answer ?? '', key))
    if (!data.answer) throw new Error('没有收到回答正文。')
    if (data.model) turn.model = data.model
    if (data.usage) turn.usage = data.usage
    if (typeof data.elapsed_ms === 'number') turn.elapsed_ms = data.elapsed_ms
    finishActivity(turn)
    return handle
  }

  const body = response.body
  if (!body) throw new Error('接口没有返回响应体。')
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let done = false
  let step: number | undefined
  let pendingText = ''
  let pendingStep: number | undefined
  let firstToken = true
  let tokenTimer: ReturnType<typeof setTimeout> | undefined

  const flushTokens = (): void => {
    if (tokenTimer !== undefined) clearTimeout(tokenTimer)
    tokenTimer = undefined
    if (!pendingText) return
    const text = pendingText
    pendingText = ''
    turn.model_phase = 'generating'
    appendActivityText(turn, text, pendingStep)
    hooks.onToken(turn)
  }

  const queueToken = (event: AgentEvent): void => {
    const nextStep = event.step ?? step
    if (pendingStep !== nextStep) {
      flushTokens()
      firstToken = true
    }
    pendingStep = nextStep
    pendingText += cleanError(event.text ?? '', key)
    if (!pendingText) return
    if (firstToken || pendingText.length >= MAX_PENDING_TOKEN_CHARS) {
      firstToken = false
      flushTokens()
    } else if (tokenTimer === undefined) {
      tokenTimer = setTimeout(flushTokens, TOKEN_FLUSH_MS)
    }
  }

  const stop = (): void => {
    flushTokens()
    void reader.cancel().catch(() => undefined)
  }
  signal.addEventListener('abort', stop, { once: true })

  const apply = (event: AgentEvent): void => {
    // Control events must observe all preceding text, including the final tail.
    if (event.type !== 'token') {
      flushTokens()
      firstToken = true
    }
    switch (event.type) {
      case 'user_message':
        turn.event_id = event.event_id
        hooks.onUserMessage?.(turn)
        break
      case 'start':
        handle.session = event.session ?? handle.session
        if (event.model) turn.model = event.model
        if (handle.session) hooks.onSession?.(handle.session)
        break
      case 'token':
        queueToken(event)
        break
      case 'message_reset':
        resetActivityMessage(turn, event.step ?? step)
        turn.model_phase = 'connecting'
        hooks.onToken(turn)
        break
      case 'message_end':
        endActivityMessage(turn, event.phase === 'final' ? 'final' : 'working', event.step ?? step)
        break
      case 'error':
        done = true
        throw new Error(event.message || '回答中断。')
      case 'step':
        if (event.phase !== 'tool') turn.model_phase = 'connecting'
        if (typeof event.step === 'number') turn.steps = event.step
        if (event.phase !== 'tool') step = event.step
        if (event.phase === 'tool') hooks.onStep(turn, 'tool')
        else hooks.onStep(turn, 'model')
        break
      case 'model_status':
        if (
          ['connecting', 'connected', 'thinking', 'generating', 'tool_call'].includes(
            event.phase ?? '',
          )
        ) {
          turn.model_phase = event.phase as ChatTurn['model_phase']
          hooks.onStep(turn, event.phase!)
        }
        break
      case 'retry':
        turn.model_phase = 'connecting'
        hooks.onRetry?.(turn, event)
        break
      case 'tool_call': {
        if (event.id && turn.tools?.some((tool) => tool.id === event.id)) break
        const tool: ToolTrace = {
          id: event.id,
          name: event.name ?? 'tool',
          arguments: event.arguments ?? {},
          reason: String((event.arguments ?? {}).reason ?? ''),
          status: 'running',
          result: null,
        }
        turn.tools = [...(turn.tools ?? []), tool]
        appendActivityTool(turn, turn.tools.length - 1)
        hooks.onToolCall(turn, turn.tools[turn.tools.length - 1]!)
        break
      }
      case 'tool_result': {
        const tools = turn.tools ?? []
        const tool = event.id
          ? tools.find((item) => item.id === event.id)
          : tools.find(
              (item) => item.status === 'running' && (!event.name || item.name === event.name),
            )
        if (tool) {
          const result = (event.result ?? {}) as ExperimentResult
          tool.result = result
          tool.status = toolResultStatus(result)
          if (tool.status !== 'error') hideRetriedFailures(tools, tool)
          hooks.onToolResult(turn, tool)
        }
        break
      }
      case 'done':
        done = true
        finishActivity(turn)
        if (event.model) turn.model = event.model
        if (event.usage) turn.usage = event.usage
        if (typeof event.elapsed_ms === 'number') turn.elapsed_ms = event.elapsed_ms
        if (typeof event.steps === 'number') turn.steps = event.steps
        break
      default:
        break
    }
  }

  const dispatch = (block: string): void => {
    const text = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n')
    if (!text) return
    apply(JSON.parse(text) as AgentEvent)
  }

  try {
    for (;;) {
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
      const next = await reader.read()
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
      buffer += decoder.decode(next.value ?? new Uint8Array(), { stream: !next.done })
      let match = /\r?\n\r?\n/.exec(buffer)
      while (match && !done) {
        dispatch(buffer.slice(0, match.index))
        buffer = buffer.slice(match.index + match[0].length)
        match = /\r?\n\r?\n/.exec(buffer)
      }
      if (done) break
      if (next.done) {
        if (buffer.trim()) dispatch(buffer)
        break
      }
    }
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    if (!done) throw new Error('回答流提前中断，请重试。')
    if (turn.tools?.some((tool) => tool.status === 'running'))
      throw new Error('回答已结束，但部分工具没有返回执行结果。')
    if (!turn.answer) throw new Error('没有收到回答正文。')
    if (!finalAnswer(turn).trim()) throw new Error('没有收到最终回答正文。')
  } catch (error) {
    flushTokens()
    const message = signal.aborted
      ? '本轮已停止，未收到工具执行结果。'
      : connectionError(error, key)
    settlePendingTools(turn, message, hooks)
    throw error
  } finally {
    signal.removeEventListener('abort', stop)
    flushTokens()
    void reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }

  return handle
}

export interface AskResult {
  ok: boolean
  turn: ChatTurn
  session: string | null
  error: string | null
  stopped: boolean
}

export async function askAgent(options: {
  config: ProviderConfig
  question: string
  context: SnapshotContext
  detail: DetailLevel
  turn: ChatTurn
  controller: AbortController
  hooks: StreamHooks
  session?: string | null
  images?: TurnImage[] | null
  attachments?: ChatAttachment[]
  revision?: { action: 'regenerate' | 'edit'; event_id: string }
}): Promise<AskResult> {
  const {
    config,
    question,
    context,
    detail,
    turn,
    controller,
    hooks,
    session,
    images: attached,
  } = options
  const started = performance.now()
  try {
    const response = await ApiBase.request('/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({
        ...config,
        question,
        context,
        detail_level: detail,
        session: session ?? null,
        ...(options.revision ? { revision: options.revision } : {}),
        images: (attached ?? []).map((image) => ({
          data_url: image.data_url,
          name: image.name,
          width: image.width,
          height: image.height,
        })),
        attachments: (options.attachments ?? []).map((file) => ({ id: file.id })),
      }),
    })
    if (!response.ok) throw new Error(await readableError(response))
    hooks.onAccepted?.()
    const handle = await consumeStream(response, turn, config.api_key, controller.signal, hooks)
    turn.status = 'complete'
    if (turn.elapsed_ms === undefined) turn.elapsed_ms = Math.round(performance.now() - started)
    return { ok: true, turn, session: handle.session, error: null, stopped: false }
  } catch (error) {
    const aborted = (error as Error).name === 'AbortError'
    turn.status = aborted ? 'stopped' : 'error'
    turn.elapsed_ms = Math.round(performance.now() - started)
    if (aborted) return { ok: false, turn, session: null, error: null, stopped: true }
    const message = connectionError(error, config.api_key)
    turn.error = message
    turn.answer += (turn.answer ? '\n\n' : '') + message
    return { ok: false, turn, session: null, error: message, stopped: false }
  }
}

export function cancelSession(session: string | null): void {
  if (!session) return
  ApiBase.request('/api/agent/cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session }),
  }).catch(() => undefined)
}

export function metricRows(entry: MetricEntry): Array<{ label: string; value: string }> {
  return entryMetrics(entry).map(({ label, value }) => ({ label, value }))
}

export function figureList(result: ExperimentResult | null): ToolFigure[] {
  return (result?.figures ?? []).filter((figure) => Boolean(figure.url))
}
