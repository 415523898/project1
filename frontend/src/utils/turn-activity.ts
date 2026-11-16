import type { ChatTurn, TurnActivity } from '@/types'
import { assistantDisplay } from './assistant-display'

/** Legacy logs have tool rows followed by a single answer; never guess missing boundaries. */
export function activities(turn: ChatTurn): TurnActivity[] {
  if (turn.activity) return turn.activity
  const blocks: TurnActivity[] = (turn.tools ?? []).map((_, index) => ({ kind: 'tool', index }))
  if (turn.answer)
    blocks.push({
      kind: 'message',
      text: turn.answer,
      phase: turn.status === 'complete' ? 'final' : 'working',
    })
  return blocks
}

export function appendActivityText(turn: ChatTurn, text: string, step?: number): void {
  if (!text) return
  turn.activity ??= activities(turn)
  turn.answer += text
  const last = turn.activity.at(-1)
  if (last?.kind === 'message' && !last.phase && (step === undefined || last.step === step))
    last.text += text
  else turn.activity.push({ kind: 'message', text, step })
}

export function endActivityMessage(
  turn: ChatTurn,
  phase: 'working' | 'final',
  step?: number,
): void {
  const message = turn.activity
    ?.slice()
    .reverse()
    .find((item) => item.kind === 'message' && (step === undefined || item.step === step))
  if (message?.kind === 'message') message.phase = phase
}

export function resetActivityMessage(turn: ChatTurn, step?: number): void {
  const blocks = turn.activity
  if (!blocks) return
  for (let index = blocks.length - 1; index >= 0; index--) {
    const block = blocks[index]
    if (
      !block ||
      block.kind !== 'message' ||
      block.phase ||
      (step !== undefined && block.step !== step)
    )
      continue
    blocks.splice(index, 1)
    turn.answer = blocks.flatMap((item) => (item.kind === 'message' ? [item.text] : [])).join('')
    return
  }
}

export function appendActivityTool(turn: ChatTurn, index: number): void {
  turn.activity ??= activities(turn)
  endActivityMessage(turn, 'working')
  if (!turn.activity.some((item) => item.kind === 'tool' && item.index === index)) {
    turn.activity.push({ kind: 'tool', index })
  }
}

export function finishActivity(turn: ChatTurn): void {
  const last = turn.activity?.at(-1)
  if (last?.kind === 'message' && last.phase !== 'working') last.phase = 'final'
}

export function finalAnswer(turn: ChatTurn): string {
  return activities(turn)
    .filter(
      (item): item is Extract<TurnActivity, { kind: 'message' }> =>
        item.kind === 'message' && item.phase === 'final',
    )
    .map((item) => assistantDisplay(item.text).text)
    .join('\n\n')
}

export function previewAnswer(turn: ChatTurn): string {
  const last = activities(turn)
    .slice()
    .reverse()
    .find((item) => item.kind === 'message')
  return finalAnswer(turn) || (last?.kind === 'message' ? last.text : '')
}
