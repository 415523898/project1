import { frontendConfig } from '@/config'
import { onBeforeUnmount, ref, shallowRef } from 'vue'
import type { Point } from '@/utils/graph-layout'

export interface CanvasView {
  pan: Point
  zoom: number
}
export const CANVAS_MOVE_MS = frontendConfig.canvas.moveMs
export const CANVAS_VIEW_MS = frontendConfig.canvas.viewMs

export function useCanvasViewport() {
  const pan = shallowRef({ x: 0, y: 0 })
  const zoom = ref(1)
  const moving = ref(false)
  let frame = 0
  let disposed = false
  let tween: { from: CanvasView; to: CanvasView; started: number; duration: number } | null = null
  const currentView = (): CanvasView => ({ pan: { ...pan.value }, zoom: zoom.value })
  const getView = (): CanvasView => tween?.to ?? currentView()
  function apply(view: CanvasView) {
    pan.value = { ...view.pan }
    zoom.value = view.zoom
  }
  function stopView() {
    if (frame) cancelAnimationFrame(frame)
    frame = 0
    tween = null
    moving.value = false
  }
  function setView(view: CanvasView) {
    stopView()
    apply(view)
  }
  function shiftView(delta: Point) {
    if (disposed || (!delta.x && !delta.y)) return
    const shift = (view: CanvasView): CanvasView => ({
      ...view,
      pan: { x: view.pan.x + delta.x, y: view.pan.y + delta.y },
    })
    apply(shift(currentView()))
    if (tween) {
      // Move both camera endpoints so panel resizing keeps the original easing and deadline.
      tween.from = shift(tween.from)
      tween.to = shift(tween.to)
    }
  }
  function step(now: number) {
    frame = 0
    if (!tween || disposed) return
    const ratio = Math.min(1, Math.max(0, (now - tween.started) / tween.duration))
    const t = 1 - (1 - ratio) ** 3
    const mix = (a: number, b: number) => a + (b - a) * t
    apply({
      zoom: mix(tween.from.zoom, tween.to.zoom),
      pan: { x: mix(tween.from.pan.x, tween.to.pan.x), y: mix(tween.from.pan.y, tween.to.pan.y) },
    })
    if (ratio === 1) {
      apply(tween.to)
      tween = null
      moving.value = false
    } else frame = requestAnimationFrame(step)
  }
  function moveView(view: CanvasView, duration?: number) {
    if (disposed) return
    const from = currentView()
    if (
      window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
      (duration !== undefined && duration <= 0) ||
      (from.zoom === view.zoom && from.pan.x === view.pan.x && from.pan.y === view.pan.y)
    ) {
      setView(view)
      return
    }
    const travel = Math.hypot(view.pan.x - from.pan.x, view.pan.y - from.pan.y)
    tween = {
      from,
      to: view,
      started: performance.now(),
      duration:
        duration ??
        Math.min(
          CANVAS_MOVE_MS,
          Math.max(CANVAS_VIEW_MS, travel / 6, Math.abs(Math.log(view.zoom / from.zoom)) * 160),
        ),
    }
    moving.value = true
    if (!frame) frame = requestAnimationFrame(step)
  }
  onBeforeUnmount(() => {
    disposed = true
    stopView()
  })
  return { pan, zoom, moving, currentView, getView, stopView, setView, shiftView, moveView }
}
