import type { StudyEdge, StudyEdgeRoute } from '@/services/study'
import { createCanvasSpatialIndex } from '@/utils/canvas-spatial-index'
import {
  arrowIntersections,
  studyArrow,
  visibleCrossings,
  type ArrowCrossing,
  type ArrowNode,
  type StudyArrow,
} from '@/utils/study-arrows'

interface PairCrossings {
  lower: string
  upper: string
  points: ArrowCrossing[]
}

export function createStudyArrowCache() {
  const geometry = new Map<string, { stamp: string; arrow: StudyArrow }>()
  const index = createCanvasSpatialIndex()
  const pairs = new Map<string, PairCrossings>()
  const links = new Map<string, Set<string>>()
  const lowerPairs = new Map<string, Map<string, ArrowCrossing[]>>()
  const orderedPoints = new Map<string, ArrowCrossing[][]>()
  const gapCache = new Map<string, { gaps: StudyArrow['gaps']; minZoom: number; maxZoom: number }>()
  const dirtyLower = new Set<string>()
  let previousZoom = NaN,
    previousOrder = ''
  let result: StudyArrow[] = []
  const stats = { geometryBuilds: 0, pairChecks: 0, gapBuilds: 0 }

  function gapsFor(id: string, zoom: number) {
    const cached = gapCache.get(id)
    if (cached && zoom >= cached.minZoom && zoom < cached.maxZoom) return cached.gaps
    stats.gapBuilds++
    const radius = 1 / zoom,
      cell = radius * 2
    const buckets = new Map<string, Array<{ x: number; y: number }>>()
    const gaps: StudyArrow['gaps'] = []
    let minZoom = 0,
      maxZoom = Infinity
    for (const points of orderedPoints.get(id) ?? []) {
      for (const crossing of points) {
        const threshold = 10 / crossing.endpointDistance
        if (crossing.endpointDistance < 10 / zoom) maxZoom = Math.min(maxZoom, threshold)
        else minZoom = Math.max(minZoom, threshold)
      }
      for (const point of visibleCrossings(points, 10 / zoom)) {
        const x = Math.floor(point.x / cell),
          y = Math.floor(point.y / cell)
        let nearest = cell
        for (let dx = -1; dx <= 1; dx++)
          for (let dy = -1; dy <= 1; dy++)
            for (const old of buckets.get(x + dx + ':' + (y + dy)) ?? [])
              nearest = Math.min(nearest, Math.hypot(old.x - point.x, old.y - point.y))
        if (nearest < radius) {
          maxZoom = Math.min(maxZoom, 1 / nearest)
          continue
        }
        minZoom = Math.max(minZoom, 1 / nearest)
        gaps.push(point)
        const key = x + ':' + y,
          bucket = buckets.get(key) ?? []
        bucket.push(point)
        buckets.set(key, bucket)
      }
    }
    // These bounds preserve every endpoint and duplicate decision; zooming within them needs no new gap scan.
    const retained =
      cached &&
      cached.gaps.length === gaps.length &&
      cached.gaps.every((p, i) => p.x === gaps[i]!.x && p.y === gaps[i]!.y)
        ? cached.gaps
        : gaps
    gapCache.set(id, {
      gaps: retained,
      minZoom: minZoom * (1 + Number.EPSILON * 8),
      maxZoom: Number.isFinite(maxZoom) ? maxZoom * (1 - Number.EPSILON * 8) : Infinity,
    })
    return retained
  }

  function removePairs(id: string) {
    for (const key of links.get(id) ?? []) {
      const pair = pairs.get(key)!
      pairs.delete(key)
      links.get(pair.lower)?.delete(key)
      links.get(pair.upper)?.delete(key)
      lowerPairs.get(pair.lower)?.delete(pair.upper)
      dirtyLower.add(pair.lower)
    }
    links.delete(id)
  }
  function addPair(lower: string, upper: string, points: ArrowCrossing[]) {
    const key = JSON.stringify([lower, upper])
    pairs.set(key, { lower, upper, points })
    for (const id of [lower, upper]) {
      let keys = links.get(id)
      if (!keys) {
        keys = new Set()
        links.set(id, keys)
      }
      keys.add(key)
    }
    let items = lowerPairs.get(lower)
    if (!items) {
      items = new Map()
      lowerPairs.set(lower, items)
    }
    items.set(upper, points)
    dirtyLower.add(lower)
  }
  function build(edges: StudyEdge[], nodes: ArrowNode[], routes: StudyEdgeRoute[], zoom = 1) {
    const cards = new Map(nodes.map((node) => [node.card_id, node]))
    const presentations = new Map(routes.map((route) => [route.edge_id, route]))
    const ordered = [...edges]
      .sort((a, b) => a.edge_id.localeCompare(b.edge_id))
      .filter((edge) => cards.has(edge.from_id) && cards.has(edge.to_id))
    const live = new Set(ordered.map((edge) => edge.edge_id)),
      changed: string[] = []
    let refreshed = false
    for (const id of geometry.keys())
      if (!live.has(id)) {
        removePairs(id)
        index.remove(id)
        geometry.delete(id)
        lowerPairs.delete(id)
        orderedPoints.delete(id)
        gapCache.delete(id)
        refreshed = true
      }
    for (const edge of ordered) {
      const from = cards.get(edge.from_id)!,
        to = cards.get(edge.to_id)!,
        route = presentations.get(edge.edge_id)
      const stamp = JSON.stringify([
        edge.from_id,
        edge.to_id,
        from.x,
        from.y,
        to.x,
        to.y,
        edge.created_by,
        !!edge.manual_fields?.length,
        edge.semantic_locked,
        route?.source_side,
        route?.target_side,
        route?.mode,
        route?.route_locked,
      ])
      const known = geometry.get(edge.edge_id)
      if (!known || known.stamp !== stamp) {
        removePairs(edge.edge_id)
        const arrow = studyArrow(edge, from, to, route)
        geometry.set(edge.edge_id, { stamp, arrow })
        index.set(edge.edge_id, arrow.bounds)
        changed.push(edge.edge_id)
        stats.geometryBuilds++
        refreshed = true
      } else if (known.arrow.edge !== edge) {
        geometry.set(edge.edge_id, { stamp, arrow: { ...known.arrow, edge } })
        refreshed = true
      }
    }
    const checked = new Set<string>()
    for (const id of changed)
      for (const other of index.search(geometry.get(id)!.arrow.bounds)) {
        if (id === other) continue
        const lower = id.localeCompare(other) < 0 ? id : other
        const upper = lower === id ? other : id
        const key = JSON.stringify([lower, upper])
        if (checked.has(key)) continue
        checked.add(key)
        stats.pairChecks++
        const points = arrowIntersections(geometry.get(lower)!.arrow, geometry.get(upper)!.arrow)
        if (points.length) addPair(lower, upper, points)
      }
    for (const id of dirtyLower) {
      gapCache.delete(id)
      const items = lowerPairs.get(id)
      if (!items?.size) {
        lowerPairs.delete(id)
        orderedPoints.delete(id)
      } else
        orderedPoints.set(
          id,
          [...items].sort(([a], [b]) => a.localeCompare(b)).map(([, points]) => points),
        )
    }
    dirtyLower.clear()
    const order = JSON.stringify([...live])
    if (!refreshed && order === previousOrder && zoom === previousZoom) return result
    const previous = new Map(result.map((arrow) => [arrow.edge.edge_id, arrow]))
    const next = ordered.map((edge) => {
      const arrow = geometry.get(edge.edge_id)!.arrow,
        gaps = gapsFor(edge.edge_id, zoom),
        old = previous.get(edge.edge_id)
      return old && old.edge === arrow.edge && old.samples === arrow.samples && old.gaps === gaps
        ? old
        : { ...arrow, gaps }
    })
    if (next.length !== result.length || next.some((arrow, i) => arrow !== result[i])) result = next
    previousOrder = order
    previousZoom = zoom
    return result
  }
  return { build, stats }
}
