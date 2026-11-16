import type { MethodGraph } from '@/types'
import type { CardSize, FocusGroup, Point } from '@/utils/graph-layout'

export type CardRole =
  'overview' | 'current' | 'previous' | 'prerequisite' | 'next' | 'alternative' | 'leaving'
export interface CardPose extends Point {
  scale: number
  opacity: number
  role: CardRole
}
export const FOCUS_GAP_X = 24
export const FOCUS_GAP_Y = 48

/** Forward choices extend the path; switching a peer replaces the current step. */
export function followPath(
  path: string[],
  selected: string | null,
  graph: MethodGraph | null,
): string[] {
  if (!selected || !graph?.cards.some((card) => card.id === selected)) return []
  const current = path.at(-1)
  if (current === selected) return path
  const visited = path.indexOf(selected)
  if (visited >= 0) return path.slice(0, visited + 1)
  const previous = graph.cards.find((card) => card.id === current)
  const next = graph.cards.find((card) => card.id === selected)
  if (previous?.similar.includes(selected) || (current && next?.similar.includes(current))) {
    return [...path.slice(0, -1), selected]
  }
  if (previous?.after.includes(selected) || previous?.more.includes(selected))
    return [...path, selected]
  return [selected]
}

/** Focus coordinates never depend on the original catalogue layer or branch count. */
export function focusPoses(
  group: FocusGroup,
  path: string[],
  card: CardSize,
  availableWidth: number,
  availableHeight = Infinity,
): Map<string, CardPose> {
  const poses = new Map<string, CardPose>()
  const pitchX = card.width + FOCUS_GAP_X
  const perRow = Math.max(1, Math.min(4, Math.floor((availableWidth + FOCUS_GAP_X) / pitchX)))
  const visited = new Set(path.slice(0, -1))
  const previous = path.at(-2)
  const nextIds = [...new Set([...group.hardAfter, ...group.softAfter])].filter(
    (id) => id !== group.selected && !visited.has(id) && !group.alternatives.includes(id),
  )
  const nextRows = Math.max(1, Math.ceil(nextIds.length / perRow))
  // Reserve space below the last row for the canvas controls; keep cards readable on short screens.
  const pitchY = Math.min(
    card.height + FOCUS_GAP_Y,
    Math.max(card.height + 24, ((availableHeight * 2) / 3 - card.height / 2 - 56) / nextRows),
  )
  const place = (id: string, x: number, y: number, role: CardRole) => {
    if (!poses.has(id)) poses.set(id, { x, y, scale: 1, opacity: 1, role })
  }
  const rows = (ids: string[], direction: number, role: CardRole, includeVisited = false) => {
    const unique = [...new Set(ids)].filter(
      (id) => id !== group.selected && !poses.has(id) && (includeVisited || !visited.has(id)),
    )
    for (let offset = 0; offset < unique.length; offset += perRow) {
      const row = unique.slice(offset, offset + perRow)
      row.forEach((id, column) =>
        place(
          id,
          (column - (row.length - 1) / 2) * pitchX,
          direction * (1 + offset / perRow) * pitchY,
          id === previous ? 'previous' : role,
        ),
      )
    }
  }
  place(group.selected, 0, 0, 'current')
  const alternatives = [...new Set(group.alternatives)].filter(
    (id) => !poses.has(id) && !visited.has(id),
  )
  alternatives.forEach((id, index) => {
    const side = index % 2 === 0 ? 1 : -1
    place(id, side * (1 + Math.floor(index / 2)) * pitchX, 0, 'alternative')
  })
  // Navigation history must not hide other direct prerequisites, including earlier visited cards.
  rows(
    [...(previous ? [previous] : []), ...group.hardBefore, ...group.softBefore],
    -1,
    'prerequisite',
    true,
  )
  rows([...group.hardAfter, ...group.softAfter], 1, 'next')
  return poses
}
