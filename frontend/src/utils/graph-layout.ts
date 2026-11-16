import { frontendConfig } from '@/config'
import type { MethodGraph, MethodLayer } from '@/types'

export interface CardSize {
  width: number
  height: number
}

export interface Point {
  x: number
  y: number
}

export interface LayerBand {
  level: number
  name: string
  hint: string
  count: number
  x: number
  y: number
  width: number
  height: number
  rows: number
  methods: string[]
}

export interface LayerColumn {
  x: number
  width: number
}

export interface GraphLayout {
  spots: Map<string, Point>
  bands: LayerBand[]
  columns: LayerColumn[]
  width: number
  height: number
}

export const PAD = frontendConfig.canvas.layout.padding
export const COLUMN_GAP = frontendConfig.canvas.layout.columnGap
export const ROW_GAP = frontendConfig.canvas.layout.rowGap
export const BAND_GAP = frontendConfig.canvas.layout.bandGap
export const BAND_HEADER = frontendConfig.canvas.layout.bandHeader

export const LAYER_ROWS = frontendConfig.canvas.layout.layerRows

export function buildLayers(layers: MethodLayer[], card: CardSize): GraphLayout {
  const spots = new Map<string, Point>()
  const bands: LayerBand[] = []
  const pitchX = card.width + COLUMN_GAP
  const pitchY = card.height + ROW_GAP
  const blocks = layers.map((layer) => {
    const count = layer.methods.length
    const columns = Math.max(1, Math.ceil((count || 1) / LAYER_ROWS))
    const rows = Math.max(1, Math.ceil((count || 1) / columns))
    return {
      count,
      rows,
      layer,
      width: columns * pitchX - COLUMN_GAP,
      height: rows * pitchY - ROW_GAP,
    }
  })
  const tallest = Math.max(card.height, ...blocks.map((block) => block.height))
  const columns: LayerColumn[] = []
  let cursorX = PAD

  layers.forEach((layer, index) => {
    const block = blocks[index]!
    const top = PAD + BAND_HEADER + (tallest - block.height) / 2
    layer.methods.forEach((id, order) => {
      spots.set(id, {
        x: Math.round(cursorX + Math.floor(order / block.rows) * pitchX),
        y: Math.round(top + (order % block.rows) * pitchY),
      })
    })
    bands.push({
      level: layer.level,
      name: layer.name,
      hint: layer.hint,
      count: block.count,
      x: cursorX,
      y: PAD,
      width: block.width,
      height: block.height,
      rows: block.rows,
      methods: layer.methods,
    })
    columns.push({ x: cursorX, width: block.width })
    cursorX += block.width + BAND_GAP
  })

  const last = columns[columns.length - 1]
  const right = last ? last.x + last.width : PAD
  return {
    spots,
    bands,
    columns,
    width: Math.max(card.width, right - PAD),
    height: BAND_HEADER + tallest,
  }
}

export function canvasBounds(layout: GraphLayout, minimum = { width: 640, height: 460 }): CardSize {
  return {
    width: Math.max(layout.width + PAD * 2, minimum.width),
    height: Math.max(layout.height + PAD * 2, minimum.height),
  }
}

export interface LayerGroup extends Point, CardSize {
  name: string
  count: number
}

export interface LayerNeighbor {
  level: number
  name: string
  count: number
}

export interface SingleLayerLayout extends CardSize {
  spots: Map<string, Point>
  groups: LayerGroup[]
  upstream: LayerNeighbor[]
  downstream: LayerNeighbor[]
  title: Point
  dockWidth: number
}

/** Give a selected layer its own group columns; cross-layer links become dock summaries. */
export function buildLayer(
  graph: MethodGraph | null,
  layer: MethodLayer | undefined,
  card: CardSize,
): SingleLayerLayout {
  const spots = new Map<string, Point>()
  const groups: LayerGroup[] = []
  const byId = new Map((graph?.cards ?? []).map((item) => [item.id, item]))
  const grouped = new Map<string, string[]>()
  for (const id of layer?.methods ?? []) {
    const item = byId.get(id)
    if (!item) continue
    const ids = grouped.get(item.group) ?? []
    ids.push(id)
    grouped.set(item.group, ids)
  }
  const dockWidth = 150
  const top = 92
  const header = 34
  const rowGap = 20
  const subGap = 24
  const maxRows = 6
  let x = dockWidth + 46
  let bottom = top + header + card.height
  for (const [name, ids] of grouped) {
    const members = new Set(ids)
    const ranks = new Map(ids.map((id) => [id, 0]))
    const incoming = new Map(ids.map((id) => [id, new Set<string>()]))
    const next = new Map(ids.map((id) => [id, new Set<string>()]))
    for (const id of ids)
      for (const before of byId.get(id)?.before ?? []) {
        if (members.has(before) && before !== id) {
          incoming.get(id)!.add(before)
          next.get(before)!.add(id)
        }
      }
    const queue = ids.filter((id) => !incoming.get(id)!.size)
    for (let index = 0; index < queue.length; index++) {
      const from = queue[index]!
      for (const to of next.get(from)!) {
        ranks.set(to, Math.max(ranks.get(to)!, ranks.get(from)! + 1))
        incoming.get(to)!.delete(from)
        if (!incoming.get(to)!.size) queue.push(to)
      }
    }
    const ordered = [...ids].sort((a, b) => ranks.get(a)! - ranks.get(b)!)
    const columns = Math.ceil(ordered.length / maxRows)
    ordered.forEach((id, index) =>
      spots.set(id, {
        x: x + Math.floor(index / maxRows) * (card.width + subGap),
        y: top + header + (index % maxRows) * (card.height + rowGap),
      }),
    )
    const width = columns * (card.width + subGap) - subGap
    const height = header + Math.min(maxRows, ordered.length) * (card.height + rowGap) - rowGap + 30
    groups.push({ name, count: ids.length, x: x - 18, y: top, width: width + 36, height })
    bottom = Math.max(bottom, top + height)
    x += width + 56
  }
  const up = new Map<number, number>()
  const down = new Map<number, number>()
  for (const kind of ['prerequisite', 'suggest'] as const) {
    for (const edge of graph?.edges[kind] ?? []) {
      const from = byId.get(edge.from)
      const to = byId.get(edge.to)
      if (spots.has(edge.to) && from && from.level < (layer?.level ?? 0)) {
        up.set(from.level, (up.get(from.level) ?? 0) + 1)
      }
      if (spots.has(edge.from) && to && to.level > (layer?.level ?? 0)) {
        down.set(to.level, (down.get(to.level) ?? 0) + 1)
      }
    }
  }
  const neighbors = (counts: Map<number, number>): LayerNeighbor[] =>
    [...counts]
      .sort(([a], [b]) => a - b)
      .map(([level, count]) => ({
        level,
        count,
        name: graph?.layers.find((item) => item.level === level)?.name ?? '',
      }))
  return {
    spots,
    groups,
    upstream: neighbors(up),
    downstream: neighbors(down),
    dockWidth,
    title: { x: dockWidth + 28, y: 14 },
    width: Math.max(x - 56 + 48 + dockWidth, 980),
    height: Math.max(bottom + 34, top + 62 + Math.max(up.size, down.size) * 64, 460),
  }
}

export interface FocusGroup {
  selected: string
  hardBefore: string[]
  softBefore: string[]
  hardAfter: string[]
  softAfter: string[]
  alternatives: string[]
}
