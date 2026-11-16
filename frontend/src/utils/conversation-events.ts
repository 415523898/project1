import {
  appendActivityText,
  appendActivityTool,
  endActivityMessage,
  finishActivity,
} from '@/utils/turn-activity'
import { toolResultStatus } from '@/services/agent'
import { hideRetriedFailures } from '@/utils/tool-traces'
import type { ChatTurn, ToolTrace, TurnImage, ChatAttachment, ExperimentResult } from '@/types'

const EXPERIMENT_TOOL = 'run_ml_suite'

function turnImages(event: Record<string, unknown>): TurnImage[] {
  const list = event.images
  if (Array.isArray(list)) return list as TurnImage[]
  const single = event.image
  return single ? [single as TurnImage] : []
}

export function turnsFromEvents(events: unknown[], running = false): ChatTurn[] {
  const turns: ChatTurn[] = []
  let current: ChatTurn | null = null
  let pending: Record<string, ToolTrace> = {}
  let step: number | undefined
  for (const raw of events) {
    const event = raw as Record<string, unknown>
    const kind = event.kind
    if (kind === 'user/message') {
      current = {
        kind: 'chat',
        question: String(event.text ?? ''),
        event_id: String(event.id || 'seq:' + event.seq),
        answer: '',
        activity: [],
        tools: [],
        context: (event.context as Record<string, unknown> | null) ?? null,
        images: turnImages(event),
        attachments: Array.isArray(event.attachments)
          ? (event.attachments as ChatAttachment[])
          : [],
        status: 'pending',
        created_at: typeof event.at === 'string' ? event.at : undefined,
      }
      pending = {}
      step = undefined
      turns.push(current)
    } else if (kind === 'step/start') {
      step = typeof event.step === 'number' ? event.step : undefined
    } else if (kind === 'assistant/message' && current) {
      const messageStep = typeof event.step === 'number' ? event.step : step
      appendActivityText(current, String(event.text ?? ''), messageStep)
      if (event.phase === 'working' || event.phase === 'final')
        endActivityMessage(current, event.phase, messageStep)
    } else if (kind === 'tool/call' && current) {
      const id = String(event.call ?? event.name ?? '')
      const trace: ToolTrace = {
        id,
        name: String(event.name ?? 'tool'),
        reason: typeof event.reason === 'string' ? event.reason : undefined,
        status: 'running',
        result: null,
        arguments: (event.arguments as Record<string, unknown> | undefined) ?? undefined,
      }
      pending[id] = trace
      current.tools = [...(current.tools ?? []), trace]
      appendActivityTool(current, current.tools.length - 1)
    } else if (kind === 'tool/result' && current) {
      const id = String(event.call ?? event.name ?? '')
      const result = (event.result as ExperimentResult | undefined) ?? null
      const trace =
        pending[id] ??
        (!event.call
          ? (current.tools ?? []).find(
              (tool) => tool.status === 'running' && tool.name === event.name,
            )
          : undefined)
      if (trace) {
        trace.status = toolResultStatus(result)
        trace.result = result
        if (trace.status !== 'error') hideRetriedFailures(current.tools, trace)
      }
    } else if (kind === 'turn/end' && current) {
      current.status = 'complete'
      if (typeof event.model === 'string') current.model = event.model
      if (typeof event.steps === 'number') current.steps = event.steps
      if (typeof event.elapsed_ms === 'number') current.elapsed_ms = event.elapsed_ms
      if (typeof event.interrupted === 'string' && event.interrupted) {
        current.status = 'error'
        current.error = event.interrupted
      } else finishActivity(current)
      if (!current.answer.trim() && !(current.tools ?? []).length) turns.pop()
      current = null
    }
  }
  for (const turn of turns) {
    // Only the last unfinished turn can belong to the server's live request.
    if (turn.status === 'pending' && !(running && turn === current)) {
      turn.status = 'error'
      const hasSavedExperiment = turn.tools?.some(
        (tool) =>
          tool.status === 'complete' &&
          [EXPERIMENT_TOOL, 'experiment'].includes(tool.name) &&
          Object.keys(tool.result?.methods ?? {}).length > 0,
      )
      turn.error = hasSavedExperiment
        ? '这轮回答已中断，已完成的实验结果仍保留。可以继续提问，无需重跑已完成的实验。'
        : turn === current
          ? '这轮回答没有完整结束，服务端当前没有运行中的请求。请重试。'
          : '这轮回答已中断，未保存完整结果。'
    }
    for (const tool of turn.tools ?? []) {
      if (tool.status === 'running' && !(running && turn === current)) {
        tool.status = 'error'
        tool.result = { error: '这次工具调用没有保存执行结果，可能已被中断。' }
      }
    }
  }
  return turns
}
