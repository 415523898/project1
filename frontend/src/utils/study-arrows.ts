import { frontendConfig } from '@/config'
import type { StudyEdge, StudyEdgeRoute, StudySide } from '@/services/study'

const { cardWidth: CARD_WIDTH, cardHeight: CARD_HEIGHT } = frontendConfig.canvas.study

export interface ArrowPoint {
  x: number
  y: number
}
export interface ArrowNode extends ArrowPoint {
  card_id: string
}
export interface StudyArrow {
  edge: StudyEdge
  sourceSide: StudySide
  targetSide: StudySide
  start: ArrowPoint
  end: ArrowPoint
  control1: ArrowPoint
  control2: ArrowPoint
  path: string
  samples: ArrowPoint[]
  gaps: ArrowPoint[]
  bounds: { x: number; y: number; width: number; height: number }
}
export const STUDY_SIDES: StudySide[] = ['top', 'right', 'bottom', 'left']
const normal: Record<StudySide, ArrowPoint> = {
  top: { x: 0, y: -1 },
  right: { x: 1, y: 0 },
  bottom: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
}
const steps = 48
const distance = (a: ArrowPoint, b: ArrowPoint) => Math.hypot(a.x - b.x, a.y - b.y)
const cross = (a: ArrowPoint, b: ArrowPoint) => a.x * b.y - a.y * b.x
const subtract = (a: ArrowPoint, b: ArrowPoint) => ({ x: a.x - b.x, y: a.y - b.y })

export function studyAnchor(node: ArrowPoint, side: StudySide): ArrowPoint {
  return {
    x: node.x + (side === 'left' ? 0 : side === 'right' ? CARD_WIDTH : CARD_WIDTH / 2),
    y: node.y + (side === 'top' ? 0 : side === 'bottom' ? CARD_HEIGHT : CARD_HEIGHT / 2),
  }
}

// Keep the original page's vertical-first, midpoint-to-midpoint port selection.
export function automaticSides(from: ArrowPoint, to: ArrowPoint): [StudySide, StudySide] {
  if (to.y >= from.y + CARD_HEIGHT) return ['bottom', 'top']
  if (to.y + CARD_HEIGHT <= from.y) return ['top', 'bottom']
  return to.x >= from.x + CARD_WIDTH ? ['right', 'left'] : ['left', 'right']
}
export function targetSideFor(point: ArrowPoint, target: ArrowPoint): StudySide {
  return STUDY_SIDES.reduce((best, side) =>
    distance(point, studyAnchor(target, side)) < distance(point, studyAnchor(target, best))
      ? side
      : best,
  )
}

export function cubicPoint(
  arrow: Pick<StudyArrow, 'start' | 'end' | 'control1' | 'control2'>,
  t: number,
): ArrowPoint {
  const s = 1 - t
  return {
    x:
      s ** 3 * arrow.start.x +
      3 * s * s * t * arrow.control1.x +
      3 * s * t * t * arrow.control2.x +
      t ** 3 * arrow.end.x,
    y:
      s ** 3 * arrow.start.y +
      3 * s * s * t * arrow.control1.y +
      3 * s * t * t * arrow.control2.y +
      t ** 3 * arrow.end.y,
  }
}
function derivative(arrow: StudyArrow, t: number): ArrowPoint {
  const s = 1 - t
  return {
    x:
      3 * s * s * (arrow.control1.x - arrow.start.x) +
      6 * s * t * (arrow.control2.x - arrow.control1.x) +
      3 * t * t * (arrow.end.x - arrow.control2.x),
    y:
      3 * s * s * (arrow.control1.y - arrow.start.y) +
      6 * s * t * (arrow.control2.y - arrow.control1.y) +
      3 * t * t * (arrow.end.y - arrow.control2.y),
  }
}

function automaticAiRoute(
  edge: StudyEdge,
  from: ArrowPoint,
  to: ArrowPoint,
  route?: StudyEdgeRoute,
): StudyEdgeRoute | undefined {
  if (
    edge.created_by !== 'ai' ||
    edge.manual_fields?.length ||
    edge.semantic_locked ||
    route?.route_locked ||
    route?.mode === 'guided'
  )
    return route
  const dx = to.x - from.x,
    dy = to.y - from.y
  let sides: [StudySide, StudySide]
  if (Math.abs(dx) >= CARD_WIDTH) sides = dx > 0 ? ['right', 'left'] : ['left', 'right']
  else if (Math.abs(dy) >= CARD_HEIGHT) sides = dy > 0 ? ['bottom', 'top'] : ['top', 'bottom']
  else return route
  return {
    ...route,
    edge_id: edge.edge_id,
    waypoints: route?.waypoints ?? [],
    source_side: sides[0],
    target_side: sides[1],
  }
}

export function studyArrow(
  edge: StudyEdge,
  from: ArrowPoint,
  to: ArrowPoint,
  route?: StudyEdgeRoute,
): StudyArrow {
  // Old AI results sometimes stored bottom ports before placing cards in columns.
  // Resolve these at display time as well, so a model rerun is unnecessary.
  route = automaticAiRoute(edge, from, to, route)
  const self = edge.from_id === edge.to_id
  const automatic: [StudySide, StudySide] = self ? ['right', 'top'] : automaticSides(from, to)
  const sourceSide =
    route?.source_side && route.source_side !== 'auto' ? route.source_side : automatic[0]
  const targetSide =
    route?.target_side && route.target_side !== 'auto' ? route.target_side : automatic[1]
  const start = studyAnchor(from, sourceSide),
    end = studyAnchor(to, targetSide)
  const sourceNormal = normal[sourceSide],
    targetNormal = normal[targetSide]
  const forward = (end.x - start.x) * sourceNormal.x + (end.y - start.y) * sourceNormal.y
  const opposite = sourceNormal.x === -targetNormal.x && sourceNormal.y === -targetNormal.y
  // This is the original cubic shape for opposite, facing ports. Other port
  // combinations use the same cubic construction; no obstacle router is added.
  const length = opposite && forward >= 0 ? forward / 2 : Math.max(40, distance(start, end) / 2)
  const control1 = { x: start.x + sourceNormal.x * length, y: start.y + sourceNormal.y * length }
  const control2 = { x: end.x + targetNormal.x * length, y: end.y + targetNormal.y * length }
  if (self) {
    const extent = 320
    Object.assign(control1, {
      x: start.x + sourceNormal.x * extent,
      y: start.y + sourceNormal.y * extent,
    })
    Object.assign(control2, {
      x: end.x + targetNormal.x * extent,
      y: end.y + targetNormal.y * extent,
    })
    if (opposite || sourceSide === targetSide) {
      const tangent = { x: -sourceNormal.y, y: sourceNormal.x }
      const sign = sourceSide === targetSide ? -1 : 1
      control1.x += tangent.x * extent
      control1.y += tangent.y * extent
      control2.x += tangent.x * extent * sign
      control2.y += tangent.y * extent * sign
    }
  }
  const points = [start, end, control1, control2]
  const x = Math.min(...points.map((p) => p.x)) - 20,
    y = Math.min(...points.map((p) => p.y)) - 20
  const arrow: StudyArrow = {
    edge,
    start,
    end,
    control1,
    control2,
    sourceSide,
    targetSide,
    path: `M ${start.x} ${start.y} C ${control1.x} ${control1.y}, ${control2.x} ${control2.y}, ${end.x} ${end.y}`,
    samples: [],
    gaps: [],
    bounds: {
      x,
      y,
      width: Math.max(...points.map((p) => p.x)) + 20 - x,
      height: Math.max(...points.map((p) => p.y)) + 20 - y,
    },
  }
  arrow.samples = Array.from({ length: steps + 1 }, (_, index) => cubicPoint(arrow, index / steps))
  return arrow
}

export interface ArrowCrossing {
  point: ArrowPoint
  endpointDistance: number
}

interface ArrowSegment {
  index: number
  start: ArrowPoint
  delta: ArrowPoint
  minX: number
  maxX: number
  minY: number
  maxY: number
}
const segmentCache = new WeakMap<
  ArrowPoint[],
  { segments: ArrowSegment[]; ordered: ArrowSegment[]; horizontal: boolean }
>()
function segmentsOf(arrow: StudyArrow) {
  let cached = segmentCache.get(arrow.samples)
  if (cached) return cached
  const segments = arrow.samples.slice(0, -1).map((start, index) => {
    const end = arrow.samples[index + 1]!
    return {
      index,
      start,
      delta: subtract(end, start),
      minX: Math.min(start.x, end.x),
      maxX: Math.max(start.x, end.x),
      minY: Math.min(start.y, end.y),
      maxY: Math.max(start.y, end.y),
    }
  })
  const horizontal = arrow.bounds.width >= arrow.bounds.height
  cached = {
    segments,
    horizontal,
    ordered: [...segments].sort((a, b) => (horizontal ? a.minX - b.minX : a.minY - b.minY)),
  }
  segmentCache.set(arrow.samples, cached)
  return cached
}

export function arrowIntersections(a: StudyArrow, b: StudyArrow): ArrowCrossing[] {
  const found: ArrowCrossing[] = []
  if (
    a.bounds.x > b.bounds.x + b.bounds.width ||
    b.bounds.x > a.bounds.x + a.bounds.width ||
    a.bounds.y > b.bounds.y + b.bounds.height ||
    b.bounds.y > a.bounds.y + a.bounds.height
  )
    return found
  const aSegments = segmentsOf(a),
    bSegments = segmentsOf(b)
  for (const first of aSegments.segments) {
    const candidates: ArrowSegment[] = []
    for (const second of bSegments.ordered) {
      if (bSegments.horizontal ? second.minX > first.maxX + 1e-6 : second.minY > first.maxY + 1e-6)
        break
      if (
        second.maxX + 1e-6 >= first.minX &&
        second.minX <= first.maxX + 1e-6 &&
        second.maxY + 1e-6 >= first.minY &&
        second.minY <= first.maxY + 1e-6
      )
        candidates.push(second)
    }
    // Restore the original sample order after conservative broad-phase filtering.
    candidates.sort((a, b) => a.index - b.index)
    for (const second of candidates) {
      const i = first.index,
        j = second.index
      const p = first.start,
        q = second.start,
        r = first.delta,
        s = second.delta
      const denominator = cross(r, s)
      if (Math.abs(denominator) < 1e-8) continue // Coincident lines are handled by the selection menu.
      const delta = subtract(q, p),
        t = cross(delta, s) / denominator,
        u = cross(delta, r) / denominator
      if (t < 0 || t > 1 || u < 0 || u > 1) continue
      let ta = (i + t) / steps,
        tb = (j + u) / steps
      for (let iteration = 0; iteration < 5; iteration++) {
        const difference = subtract(cubicPoint(a, ta), cubicPoint(b, tb)),
          da = derivative(a, ta),
          db = derivative(b, tb),
          det = cross(da, db)
        if (Math.abs(det) < 1e-8) break
        ta -= cross(difference, db) / det
        tb -= cross(difference, da) / det
      }
      if (ta <= 0 || ta >= 1 || tb <= 0 || tb >= 1) continue
      const point = cubicPoint(a, ta),
        da = derivative(a, ta),
        db = derivative(b, tb)
      if (
        distance(point, cubicPoint(b, tb)) > 0.1 ||
        Math.abs(cross(da, db)) < 0.05 * Math.hypot(da.x, da.y) * Math.hypot(db.x, db.y)
      )
        continue
      found.push({
        point,
        endpointDistance: Math.min(
          ...[a.start, a.end, b.start, b.end].map((end) => distance(point, end)),
        ),
      })
    }
  }
  return found
}

// Filter before deduplication: a nearby endpoint may hide one of two close candidates at a given zoom.
export function visibleCrossings(
  crossings: ArrowCrossing[],
  endpointPadding: number,
): ArrowPoint[] {
  const found: ArrowPoint[] = []
  for (const crossing of crossings) {
    if (crossing.endpointDistance < endpointPadding) continue
    if (!found.some((old) => distance(old, crossing.point) < 0.5)) found.push(crossing.point)
  }
  return found
}

export function buildStudyGeometry(
  edges: StudyEdge[],
  nodes: ArrowNode[],
  routes: StudyEdgeRoute[],
): StudyArrow[] {
  const cards = new Map(nodes.map((node) => [node.card_id, node])),
    presentations = new Map(routes.map((route) => [route.edge_id, route]))
  return [...edges]
    .sort((a, b) => a.edge_id.localeCompare(b.edge_id))
    .flatMap((edge) => {
      const from = cards.get(edge.from_id),
        to = cards.get(edge.to_id)
      return from && to ? [studyArrow(edge, from, to, presentations.get(edge.edge_id))] : []
    })
}

export function buildStudyArrows(
  edges: StudyEdge[],
  nodes: ArrowNode[],
  routes: StudyEdgeRoute[],
  zoom = 1,
): StudyArrow[] {
  const arrows = buildStudyGeometry(edges, nodes, routes)
  for (let lower = 0; lower < arrows.length; lower++)
    for (let upper = lower + 1; upper < arrows.length; upper++) {
      for (const gap of visibleCrossings(
        arrowIntersections(arrows[lower]!, arrows[upper]!),
        10 / zoom,
      )) {
        if (!arrows[lower]!.gaps.some((old) => distance(old, gap) < 1 / zoom))
          arrows[lower]!.gaps.push(gap)
      }
    }
  return arrows
}

export function arrowsNear(
  arrows: StudyArrow[],
  point: ArrowPoint,
  tolerance: number,
): StudyArrow[] {
  return arrows.filter((arrow) =>
    arrow.samples.slice(1).some((end, index) => {
      const start = arrow.samples[index]!,
        dx = end.x - start.x,
        dy = end.y - start.y
      const fraction = Math.max(
        0,
        Math.min(
          1,
          ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy || 1),
        ),
      )
      return (
        distance(point, { x: start.x + fraction * dx, y: start.y + fraction * dy }) <= tolerance
      )
    }),
  )
}
