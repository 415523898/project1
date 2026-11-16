import { frontendConfig } from '@/config'
import type { CanvasRect } from '@/utils/canvas-spatial-index'

export function canvasWindow(
  pan: { x: number; y: number },
  zoom: number,
  viewport: { width: number; height: number },
  previous?: CanvasRect,
): CanvasRect {
  const step = frontendConfig.canvas.visibilityStep,
    padding = frontendConfig.canvas.visibilityPadding
  const x = Math.floor((-pan.x - padding) / zoom / step) * step
  const y = Math.floor((-pan.y - padding) / zoom / step) * step
  const right = Math.ceil((viewport.width - pan.x + padding) / zoom / step) * step
  const bottom = Math.ceil((viewport.height - pan.y + padding) / zoom / step) * step
  const next = { x, y, width: right - x, height: bottom - y }
  return previous &&
    Object.keys(next).every(
      (key) => next[key as keyof CanvasRect] === previous[key as keyof CanvasRect],
    )
    ? previous
    : next
}

export function pathBounds(path: string): CanvasRect {
  const numbers = path.match(/-?\d+(?:\.\d+)?(?:e[+-]?\d+)?/gi)?.map(Number) ?? []
  const xs = numbers.filter((_, i) => i % 2 === 0),
    ys = numbers.filter((_, i) => i % 2 !== 0)
  const x = Math.min(...xs),
    y = Math.min(...ys)
  return { x: x - 24, y: y - 24, width: Math.max(...xs) - x + 48, height: Math.max(...ys) - y + 48 }
}

export function clippedRect(a: CanvasRect, b?: CanvasRect): CanvasRect {
  if (!b) return a
  const x = Math.max(a.x, b.x),
    y = Math.max(a.y, b.y)
  return {
    x,
    y,
    width: Math.max(0, Math.min(a.x + a.width, b.x + b.width) - x),
    height: Math.max(0, Math.min(a.y + a.height, b.y + b.height) - y),
  }
}
