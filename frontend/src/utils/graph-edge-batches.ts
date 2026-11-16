import type { RelationKind } from '@/types'
import type { RoutedEdge } from '@/utils/graph-edges'

export interface EdgeBatch {
  key: string
  kind: RelationKind
  opacity: number
  path: string
  arrows: string
}

const point = (value: number) => Math.round(value * 100) / 100

function arrowPath(path: string): string {
  const values = path.match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/gi)?.map(Number) ?? []
  const [controlX, controlY, x, y] = values.slice(-4)
  if (x === undefined || y === undefined || controlX === undefined || controlY === undefined)
    return ''
  const distance = Math.hypot(x - controlX, y - controlY)
  if (!distance) return ''
  const dx = (x - controlX) / distance
  const dy = (y - controlY) / distance
  // Match the existing 8×8 marker at a stroke width of 1.7 and marker width of 5.
  const unit = (5 * 1.7) / 8
  const tipX = x + dx * unit
  const tipY = y + dy * unit
  const baseX = x - dx * 7 * unit
  const baseY = y - dy * 7 * unit
  return `M ${point(tipX)} ${point(tipY)} L ${point(baseX - dy * 4 * unit)} ${point(baseY + dx * 4 * unit)} L ${point(baseX + dy * 4 * unit)} ${point(baseY - dx * 4 * unit)} Z`
}

/** Share paint nodes while retaining every curve and arrowhead as a separate SVG subpath. */
function groupEdges(edges: RoutedEdge[], arrowFor: (edge: RoutedEdge) => string): EdgeBatch[] {
  const batches = new Map<
    string,
    { kind: RelationKind; opacity: number; paths: string[]; arrows: string[] }
  >()
  for (const edge of edges) {
    // The topology layer owns its fade; offscreen card opacity must never hide a crossing curve.
    const opacity = edge.kind === 'suggest' ? 0.75 : 1
    const key = edge.kind
    let batch = batches.get(key)
    if (!batch) {
      batch = { kind: edge.kind, opacity, paths: [], arrows: [] }
      batches.set(key, batch)
    }
    batch.paths.push(edge.path)
    if (edge.marker) batch.arrows.push(arrowFor(edge))
  }
  return [...batches].map(([key, batch]) => ({
    key,
    kind: batch.kind,
    opacity: batch.opacity,
    path: batch.paths.join(' '),
    arrows: batch.arrows.filter(Boolean).join(' '),
  }))
}

export function batchEdges(edges: RoutedEdge[]): EdgeBatch[] {
  return groupEdges(edges, (edge) => arrowPath(edge.path))
}

export function createEdgeBatchCache() {
  const arrows = new Map<string, { path: string; marker: string; arrow: string }>()
  let previous: Array<Pick<RoutedEdge, 'key' | 'path' | 'marker' | 'kind'>> = []
  let result: EdgeBatch[] = []
  const stats = { arrowParses: 0 }
  function build(edges: RoutedEdge[]) {
    if (
      previous.length === edges.length &&
      edges.every((edge, i) => {
        const old = previous[i]!
        return (
          old.key === edge.key &&
          old.path === edge.path &&
          old.kind === edge.kind &&
          old.marker === edge.marker
        )
      })
    )
      return result
    result = groupEdges(edges, (edge) => {
      let known = arrows.get(edge.key)
      if (!known || known.path !== edge.path || known.marker !== edge.marker) {
        known = { path: edge.path, marker: edge.marker, arrow: arrowPath(edge.path) }
        arrows.set(edge.key, known)
        stats.arrowParses++
      }
      return known.arrow
    })
    previous = edges.map(({ key, path, marker, kind }) => ({ key, path, marker, kind }))
    while (arrows.size > 512) arrows.delete(arrows.keys().next().value!)
    return result
  }
  return { build, stats }
}
