import { frontendConfig } from '@/config'
import { computed, onBeforeUnmount, ref, shallowRef } from 'vue'
import type { CardPose } from '@/utils/graph-focus'
import type { CardSize } from '@/utils/graph-layout'
import {
  useCanvasViewport,
  CANVAS_MOVE_MS,
  CANVAS_VIEW_MS,
  type CanvasView,
} from '@/composables/useCanvasViewport'

export type GraphView = CanvasView
export const GRAPH_MOVE_MS = CANVAS_MOVE_MS
export const GRAPH_VIEW_MS = CANVAS_VIEW_MS
const CARD_ENTER_SCALE = frontendConfig.canvas.enterScale
const CARD_ENTER_OFFSET = frontendConfig.canvas.enterOffset

interface PoseTween {
  from: Map<string, CardPose>
  ends: Map<string, CardPose>
  hidden: Map<string, CardPose>
  target: Map<string, CardPose>
  started: number
  duration: number
}

/** Layout transitions and the shared camera can be interrupted independently. */
export function useGraphMotion(card: CardSize) {
  const poses = shallowRef(new Map<string, CardPose>())
  const camera = useCanvasViewport()
  const { pan, zoom, currentView, moveView, setView, shiftView, stopView, getView } = camera
  const layoutMoving = ref(false)
  const moving = computed(() => layoutMoving.value || camera.moving.value)
  let frame = 0
  let disposed = false
  let layout: PoseTween | null = null
  const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const mix = (a: number, b: number, t: number) => a + (b - a) * t
  const ease = (t: number) => 1 - (1 - t) ** 3
  const progress = (now: number, started: number, duration: number) =>
    Math.min(1, Math.max(0, (now - started) / duration))
  const schedule = () => {
    layoutMoving.value = Boolean(layout)
    if (layout && !frame && !disposed) frame = requestAnimationFrame(step)
  }

  function step(now: number): void {
    frame = 0
    if (disposed) return
    if (layout) {
      const ratio = progress(now, layout.started, layout.duration)
      const t = ease(ratio)
      if (ratio === 1) {
        poses.value = layout.target
        layout = null
      } else {
        // Offscreen cards keep stable poses instead of rebuilding all 116 cards every frame.
        const next = new Map(layout.hidden)
        for (const [id, end] of layout.ends) {
          const start = layout.from.get(id)!
          next.set(id, {
            ...end,
            x: mix(start.x, end.x, t),
            y: mix(start.y, end.y, t),
            scale: mix(start.scale, end.scale, t),
            opacity: mix(start.opacity, end.opacity, t),
          })
        }
        poses.value = next
      }
    }
    schedule()
  }

  function move(
    target: Map<string, CardPose>,
    view: GraphView,
    viewport: CardSize,
    animate = true,
    duration: number = GRAPH_MOVE_MS,
    anchorId?: string,
  ): void {
    if (disposed) return
    if (frame) {
      cancelAnimationFrame(frame)
      frame = 0
    }
    layout = null
    layoutMoving.value = false
    stopView()
    if (!animate || reduced() || !poses.value.size) {
      poses.value = new Map(target)
      setView(view)
      return
    }
    const anchor = anchorId ? poses.value.get(anchorId) : undefined
    const destination = anchorId ? target.get(anchorId) : undefined
    if (anchor && destination && currentView().zoom === view.zoom) {
      // Rebase local focus coordinates into the full graph without moving any screen pixels.
      // This avoids a cancelling camera/card journey through thousands of world-space pixels.
      const dx = destination.x - anchor.x
      const dy = destination.y - anchor.y
      if (dx || dy) {
        poses.value = new Map(
          [...poses.value].map(([id, pose]) => [id, { ...pose, x: pose.x + dx, y: pose.y + dy }]),
        )
        shiftView({ x: -dx * zoom.value, y: -dy * zoom.value })
      }
    }
    const from = new Map<string, CardPose>()
    const ends = new Map<string, CardPose>()
    const hidden = new Map<string, CardPose>()
    const oldView = currentView()
    const visible = (pose: CardPose, cameraView: GraphView) => {
      const x = cameraView.pan.x + pose.x * cameraView.zoom
      const y = cameraView.pan.y + pose.y * cameraView.zoom
      return (
        pose.opacity > 0.01 &&
        x + card.width * pose.scale * cameraView.zoom >= 0 &&
        y + card.height * pose.scale * cameraView.zoom >= 0 &&
        x <= viewport.width &&
        y <= viewport.height
      )
    }
    for (const [id, old] of poses.value) {
      const end = target.get(id)
      if (end && (visible(old, oldView) || visible(end, view))) {
        from.set(id, old)
        ends.set(id, end)
      } else if (!end && visible(old, oldView)) {
        const scale = Math.min(old.scale, CARD_ENTER_SCALE)
        from.set(id, { ...old, role: 'leaving' })
        ends.set(id, {
          ...old,
          role: 'leaving',
          scale,
          opacity: 0,
          x: old.x + (card.width * (old.scale - scale)) / 2,
          y: old.y - CARD_ENTER_OFFSET,
        })
      }
    }
    for (const [id, end] of target) {
      if (from.has(id)) continue
      if (visible(end, view)) {
        from.set(id, { ...end, y: end.y + CARD_ENTER_OFFSET, scale: CARD_ENTER_SCALE, opacity: 0 })
        ends.set(id, end)
      } else hidden.set(id, { ...end, opacity: 0 })
    }
    poses.value = new Map([...hidden, ...from])
    layout = { from, ends, hidden, target: new Map(target), started: performance.now(), duration }
    moveView(view, duration)
    schedule()
  }

  /** Sidebar resizing follows its own width transition without interrupting an active card transition. */
  function reflow(target: Map<string, CardPose>, view: GraphView, viewport: CardSize): void {
    const pending = layout
    const remaining = pending
      ? Math.max(0, pending.started + pending.duration - performance.now())
      : 0
    move(target, view, viewport, remaining > 0, remaining)
    if (layout && pending) {
      for (const [id, end] of pending.ends) {
        // Keep the original exit destination when repeated resize frames retarget the layout.
        if (end.role === 'leaving' && !target.has(id) && layout.ends.has(id))
          layout.ends.set(id, end)
      }
    }
  }

  onBeforeUnmount(() => {
    disposed = true
    if (frame) cancelAnimationFrame(frame)
    frame = 0
    layout = null
    stopView()
  })
  return {
    poses,
    pan,
    zoom,
    moving,
    move,
    reflow,
    moveView,
    setView,
    shiftView,
    stopView,
    getView,
    currentView,
  }
}
