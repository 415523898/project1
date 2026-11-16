import type { MethodCard, MethodGraph, RelationKind } from '@/types'
import type { CardSize, FocusGroup, Point } from '@/utils/graph-layout'

export interface RoutedEdge {
  key: string
  kind: RelationKind
  from: string
  to: string
  path: string
  marker: string
  why: string
}

export interface EdgeInput {
  graph: MethodGraph | null
  selected: string | null
  highlight: RelationKind[]
  spots: Map<string, EdgePoint>
  card: CardSize
  index?: EdgeIndex
  anchorSpots?: Map<string, Point>
  horizontalColumns?: boolean
}

export interface EdgePoint extends Point {
  scale?: number
}
export interface EdgeIndex {
  cards: Map<string, MethodCard>
  reasons: Map<string, string>
  lanes: Map<string, number>
}

const VERTICAL_TOLERANCE = 8
const MIN_RUN = 4
const LANE_STEP = 10
type Direction = 'up' | 'down' | 'left' | 'right'

export function indexGraphEdges(graph: MethodGraph | null): EdgeIndex {
  const cards = new Map((graph?.cards ?? []).map((card) => [card.id, card]))
  const reasons = new Map<string, string>()
  const lanes = new Map<string, number>()
  for (const kind of ['prerequisite', 'suggest', 'alternative'] as RelationKind[]) {
    const groups = new Map<string, Set<string>>()
    for (const edge of graph?.edges[kind] ?? []) {
      const key = `${kind}:${edge.from}->${edge.to}`
      if (!reasons.has(key)) reasons.set(key, edge.why ?? '')
      if (!groups.has(edge.from)) groups.set(edge.from, new Set())
      groups.get(edge.from)!.add(edge.to)
    }
    for (const [from, targets] of groups)
      [...targets].sort().forEach((to, index) => {
        const step = Math.min(Math.ceil(index / 2) * LANE_STEP, LANE_STEP * 3)
        lanes.set(`${kind}:${from}->${to}`, index === 0 ? 0 : index % 2 ? step : -step)
      })
  }
  return { cards, reasons, lanes }
}

function directionOf(start: Point, end: Point, card: CardSize, horizontal = false): Direction {
  if (horizontal && Math.abs(start.x - end.x) >= VERTICAL_TOLERANCE)
    return end.x > start.x ? 'right' : 'left'
  if (Math.abs(start.x - end.x) < VERTICAL_TOLERANCE) return end.y > start.y ? 'down' : 'up'
  if (end.y >= start.y + card.height) return 'down'
  if (start.y >= end.y + card.height) return 'up'
  return end.x > start.x ? 'right' : 'left'
}

function geometry(
  start: EdgePoint,
  end: EdgePoint,
  card: CardSize,
  lane = 0,
  direction?: Direction,
  targetOffset = 0,
): string | null {
  const width1 = card.width * (start.scale ?? 1)
  const width2 = card.width * (end.scale ?? 1)
  const height1 = card.height * (start.scale ?? 1)
  const height2 = card.height * (end.scale ?? 1)
  const cx1 = start.x + width1 / 2
  const cx2 = end.x + width2 / 2
  const top1 = start.y
  const bottom1 = start.y + height1
  const top2 = end.y
  const bottom2 = end.y + height2
  const offset = targetOffset * (end.scale ?? 1)

  const orientation = direction ?? directionOf(start, end, card)
  if (
    !direction &&
    !offset &&
    Math.abs(start.x - end.x) < VERTICAL_TOLERANCE &&
    (orientation === 'down' || orientation === 'up')
  ) {
    return orientation === 'down'
      ? `M ${cx1} ${bottom1} L ${cx2} ${top2}`
      : `M ${cx1} ${top1} L ${cx2} ${bottom2}`
  }

  if (orientation === 'down') {
    const bend = Math.max(18, (top2 - bottom1) / 2)
    return `M ${cx1} ${bottom1} C ${cx1} ${bottom1 + Math.max(18, bend + lane)}, ${cx2 + offset} ${top2 - Math.max(18, bend - lane)}, ${cx2 + offset} ${top2}`
  }

  if (orientation === 'up') {
    const bend = Math.max(18, (top1 - bottom2) / 2)
    return `M ${cx1} ${top1} C ${cx1} ${top1 - Math.max(18, bend + lane)}, ${cx2 + offset} ${bottom2 + Math.max(18, bend - lane)}, ${cx2 + offset} ${bottom2}`
  }

  if (orientation === 'right') {
    const x1 = start.x + width1
    const x2 = end.x
    if (!direction && x2 <= x1 + MIN_RUN) return null
    const y1 = start.y + height1 / 2
    const y2 = end.y + height2 / 2 + offset
    const bend = Math.max(18, (x2 - x1) / 2)
    return `M ${x1} ${y1} C ${x1 + Math.max(18, bend + lane)} ${y1}, ${x2 - Math.max(18, bend - lane)} ${y2}, ${x2} ${y2}`
  }

  const x1 = start.x
  const x2 = end.x + width2
  if (!direction && x1 <= x2 + MIN_RUN) return null
  const y1 = start.y + height1 / 2
  const y2 = end.y + height2 / 2 + offset
  const bend = Math.max(18, (x1 - x2) / 2)
  return `M ${x1} ${y1} C ${x1 - Math.max(18, bend - lane)} ${y1}, ${x2 + Math.max(18, bend + lane)} ${y2}, ${x2} ${y2}`
}

export function routeEdges(input: EdgeInput): RoutedEdge[] {
  const connections = new Map<string, Omit<RoutedEdge, 'path'>>()
  if (!input.graph) return []

  const index = input.index ?? indexGraphEdges(input.graph)
  const active = input.selected
  const { spots, card } = input

  const push = (kind: RelationKind, from: string, to: string, why: string) => {
    if (!input.highlight.includes(kind)) return
    if (!index.cards.has(from) || !index.cards.has(to)) return
    const key = `${kind}:${from}->${to}`
    if (connections.has(key)) return
    connections.set(key, {
      key,
      kind,
      from,
      to,
      marker: kind === 'alternative' ? '' : 'arrow',
      why,
    })
  }

  const whyOf = (kind: RelationKind, from: string, to: string) => {
    return index.reasons.get(`${kind}:${from}->${to}`) ?? ''
  }

  if (active) {
    const card0 = index.cards.get(active)
    if (card0) {
      for (const need of card0.before ?? [])
        push('prerequisite', need, active, whyOf('prerequisite', need, active))
      for (const next of card0.after ?? [])
        push('prerequisite', active, next, whyOf('prerequisite', active, next))
      for (const need of card0.suggests ?? [])
        push('suggest', need, active, whyOf('suggest', need, active))
      for (const next of card0.more ?? [])
        push('suggest', active, next, whyOf('suggest', active, next))
      for (const other of card0.similar ?? []) {
        const why = card0.similar_why?.[other] ?? ''
        if (other < active) push('alternative', other, active, why)
        else push('alternative', active, other, why)
      }
    }
  } else {
    for (const kind of input.highlight) {
      for (const edge of input.graph.edges[kind] ?? []) {
        push(kind, edge.from, edge.to, edge.why ?? '')
      }
    }
  }

  // Use the complete target layout so animation and viewport culling cannot reorder arrow ports.
  const anchors = input.anchorSpots ?? spots
  const groups = new Map<string, Array<{ key: string; along: number; across: number }>>()
  for (const edge of connections.values()) {
    if (!edge.marker) continue
    const start = anchors.get(edge.from),
      end = anchors.get(edge.to)
    if (!start || !end) continue
    const direction = directionOf(start, end, card, input.horizontalColumns)
    const vertical = direction === 'up' || direction === 'down'
    const key = `${edge.to}:${direction}`
    const group = groups.get(key) ?? []
    group.push({
      key: edge.key,
      along: vertical ? start.x : start.y,
      across: vertical ? start.y : start.x,
    })
    groups.set(key, group)
  }
  const offsets = new Map<string, number>()
  for (const [key, group] of groups) {
    group.sort((a, b) => a.along - b.along || a.across - b.across || a.key.localeCompare(b.key))
    const vertical = key.endsWith(':up') || key.endsWith(':down')
    const span = Math.max(0, (vertical ? card.width : card.height) - 24)
    const step = group.length > 1 ? Math.min(16, span / (group.length - 1)) : 0
    group.forEach((edge, position) =>
      offsets.set(edge.key, (position - (group.length - 1) / 2) * step),
    )
  }

  const visible: RoutedEdge[] = []
  for (const edge of connections.values()) {
    const start = spots.get(edge.from),
      end = spots.get(edge.to)
    if (!start || !end) continue
    const anchorStart = input.anchorSpots?.get(edge.from),
      anchorEnd = input.anchorSpots?.get(edge.to)
    const direction =
      anchorStart && anchorEnd
        ? directionOf(anchorStart, anchorEnd, card, input.horizontalColumns)
        : undefined
    // Focused neighborhoods must not inherit lane numbers from hidden catalogue branches.
    const lane =
      active ||
      (anchorStart && anchorEnd && Math.abs(anchorStart.x - anchorEnd.x) < VERTICAL_TOLERANCE)
        ? 0
        : (index.lanes.get(edge.key) ?? 0)
    const path = geometry(start, end, card, lane, direction, offsets.get(edge.key) ?? 0)
    if (path) visible.push({ ...edge, path })
  }
  return visible
}

export interface RelationMark {
  text: string
  kind: RelationKind
  why: string
}

export function relationMarks(
  selected: string | null,
  graph: MethodGraph | null,
): Map<string, RelationMark> {
  const marks = new Map<string, RelationMark>()
  if (!selected || !graph) return marks
  const card = graph.cards.find((item) => item.id === selected)
  if (!card) return marks
  const whyOf = (kind: RelationKind, from: string, to: string) =>
    (graph.edges[kind] ?? []).find((edge) => edge.from === from && edge.to === to)?.why ?? ''

  const add = (id: string, text: string, kind: RelationKind, why: string) => {
    if (id === selected || marks.has(id)) return
    marks.set(id, { text, kind, why })
  }
  for (const need of card.before ?? []) {
    add(need, '先学', 'prerequisite', whyOf('prerequisite', need, selected))
  }
  for (const next of card.after ?? []) {
    add(next, '之后学', 'prerequisite', whyOf('prerequisite', selected, next))
  }
  for (const need of card.suggests ?? []) {
    add(need, '先看', 'suggest', whyOf('suggest', need, selected))
  }
  for (const next of card.more ?? []) {
    add(next, '可选下一步', 'suggest', whyOf('suggest', selected, next))
  }
  for (const other of card.similar ?? []) {
    add(other, '可换用', 'alternative', card.similar_why?.[other] ?? '')
  }
  return marks
}

export function relatedLevel(selected: string | null, graph: MethodGraph | null): number {
  if (!selected || !graph) return 0
  const byId = new Map(graph.cards.map((card) => [card.id, card]))
  const card = byId.get(selected)
  if (!card) return 0
  const ids = [
    selected,
    ...(card.before ?? []),
    ...(card.after ?? []),
    ...(card.suggests ?? []),
    ...(card.more ?? []),
    ...(card.similar ?? []),
  ]
  let level = 0
  for (const id of ids) {
    const other = byId.get(id)
    if (other) level = Math.max(level, other.level ?? 1)
  }
  return level
}

export function focusGroupOf(
  selected: string | null,
  graph: MethodGraph | null,
): FocusGroup | null {
  if (!selected || !graph) return null
  const card = graph.cards.find((item) => item.id === selected)
  if (!card) return null
  return {
    selected,
    hardBefore: [...(card.before ?? [])],
    softBefore: [...(card.suggests ?? [])],
    hardAfter: [...(card.after ?? [])],
    softAfter: [...(card.more ?? [])],
    alternatives: [...(card.similar ?? [])],
  }
}

export function focusedNodes(selected: string | null, cards: Map<string, MethodCard>): Set<string> {
  if (!selected) return new Set<string>()
  const marks = new Set<string>([selected])
  const card = cards.get(selected)
  if (!card) return marks
  card.before?.forEach((id) => marks.add(id))
  card.after?.forEach((id) => marks.add(id))
  card.suggests?.forEach((id) => marks.add(id))
  card.more?.forEach((id) => marks.add(id))
  card.similar?.forEach((id) => marks.add(id))
  return marks
}

export function cardIndexOf(cards: MethodCard[]): Map<string, MethodCard> {
  const index = new Map<string, MethodCard>()
  for (const card of cards) index.set(card.id, card)
  return index
}
