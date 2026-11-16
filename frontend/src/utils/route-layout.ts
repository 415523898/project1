export interface RouteBox {
  key: string
  x: number
  y: number
  width: number
  height: number
  locked?: boolean
}
export interface SnapGuide {
  axis: 'x' | 'y'
  value: number
  start: number
  end: number
  fraction: number
  kind?: 'alignment' | 'gap'
  gaps?: Array<{ start: number; end: number; at: number }>
}
export type SnapCapture = Partial<Record<'x' | 'y', string>>
const fractions = [0, 1, 0.5, 1 / 3, 2 / 3]

export function routeBounds(boxes: RouteBox[], margin = 40) {
  if (!boxes.length) return { left: -margin, top: -margin, width: 640, height: 420 }
  const left = Math.min(...boxes.map((box) => box.x)) - margin
  const top = Math.min(...boxes.map((box) => box.y)) - margin
  return {
    left,
    top,
    width: Math.max(1, Math.max(...boxes.map((box) => box.x + box.width)) + margin - left),
    height: Math.max(1, Math.max(...boxes.map((box) => box.y + box.height)) + margin - top),
  }
}

// A screen-space threshold keeps snapping equally usable at every zoom level.
export function snapRoutePosition(
  moving: RouteBox,
  boxes: RouteBox[],
  zoom: number,
  threshold = 7,
  options: { previous?: SnapCapture; releaseThreshold?: number; equalGaps?: boolean } = {},
) {
  const scale = Math.max(0.01, zoom)
  const result = { x: moving.x, y: moving.y, guides: [] as SnapGuide[], capture: {} as SnapCapture }
  type Candidate = { id: string; shift: number; priority: number; guide: SnapGuide }
  for (const axis of ['x', 'y'] as const) {
    const size = axis === 'x' ? 'width' : 'height'
    const cross = axis === 'x' ? 'y' : 'x'
    const length = cross === 'x' ? 'width' : 'height'
    const candidates: Candidate[] = []
    const visible = boxes.filter((box) => box.key !== moving.key)
    const add = (candidate: Candidate) => {
      const held = options.previous?.[axis] === candidate.id
      if (
        Math.abs(candidate.shift) * scale <=
        (held ? (options.releaseThreshold ?? 10) : threshold) + 1e-7
      )
        candidates.push(candidate)
    }
    for (const box of visible) {
      for (const anchor of fractions)
        for (const reference of fractions) {
          const target = box[axis] + box[size] * reference
          const shift = target - (moving[axis] + moving[size] * anchor)
          add({
            id: `align:${box.key}:${fractions.indexOf(anchor)}:${fractions.indexOf(reference)}`,
            shift,
            priority:
              (anchor === 0 || anchor === 1) && (reference === 0 || reference === 1)
                ? 1
                : anchor === 0.5 || reference === 0.5
                  ? 2
                  : 3,
            guide: {
              axis,
              value: target,
              fraction: reference,
              kind: 'alignment',
              start: Math.min(moving[cross], box[cross]) - 12 / scale,
              end: Math.max(moving[cross] + moving[length], box[cross] + box[length]) + 12 / scale,
            },
          })
        }
    }
    if (options.equalGaps) {
      // Branch cards can straddle the moving row without sharing half its height.
      const band = visible
        .filter(
          (box) =>
            Math.min(box[cross] + box[length], moving[cross] + moving[length]) -
              Math.max(box[cross], moving[cross]) >
            1e-7,
        )
        .sort(
          (a, b) =>
            Math.abs(a[axis] - moving[axis]) - Math.abs(b[axis] - moving[axis]) ||
            a.key.localeCompare(b.key),
        )
        .slice(0, 12)
        .sort((a, b) => a[axis] - b[axis] || a.key.localeCompare(b.key))
      for (let index = 0; index < band.length - 1; index++) {
        const a = band[index]!,
          b = band[index + 1]!
        const aEnd = a[axis] + a[size],
          bEnd = b[axis] + b[size],
          gap = b[axis] - aEnd
        if (gap < 0 || gap > 800) continue
        const at =
          Math.max(moving[cross] + moving[length], a[cross] + a[length], b[cross] + b[length]) +
          14 / scale
        const propose = (
          kind: string,
          target: number,
          gaps: Array<{ start: number; end: number; at: number }>,
        ) => {
          if (gaps.some((item) => item.end < item.start)) return
          if (
            band.some(
              (box) =>
                target < box[axis] + box[size] - 1e-7 && target + moving[size] > box[axis] + 1e-7,
            )
          )
            return
          add({
            id: `gap:${kind}:${a.key}:${b.key}`,
            shift: target - moving[axis],
            priority: 0,
            guide: { axis, value: target, start: 0, end: 0, fraction: 0, kind: 'gap', gaps },
          })
        }
        const between = (aEnd + b[axis] - moving[size]) / 2
        propose('between', between, [
          { start: aEnd, end: between, at },
          { start: between + moving[size], end: b[axis], at },
        ])
        const before = a[axis] - gap - moving[size],
          after = bEnd + gap
        propose('before', before, [
          { start: before + moving[size], end: a[axis], at },
          { start: aEnd, end: b[axis], at },
        ])
        propose('after', after, [
          { start: aEnd, end: b[axis], at },
          { start: bEnd, end: after, at },
        ])
      }
    }
    const nearest = Math.min(...candidates.map((candidate) => Math.abs(candidate.shift) * scale))
    const finalists = candidates.filter(
      (candidate) => Math.abs(candidate.shift) * scale <= nearest + 0.5,
    )
    finalists.sort((a, b) => {
      const held =
        Number(options.previous?.[axis] === b.id) - Number(options.previous?.[axis] === a.id)
      return held || a.priority - b.priority || a.id.localeCompare(b.id)
    })
    const best = finalists[0]
    if (best) {
      result[axis] += best.shift
      result.guides.push(best.guide)
      result.capture[axis] = best.id
      // A held alignment must not hide an equal-gap measurement at that position.
      if (best.guide.kind !== 'gap') {
        const gap = candidates.find(
          (candidate) =>
            candidate.guide.kind === 'gap' && Math.abs(candidate.shift - best.shift) < 1e-7,
        )
        if (gap) result.guides.push(gap.guide)
      }
    }
  }
  return result
}
