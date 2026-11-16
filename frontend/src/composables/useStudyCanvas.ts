import { frontendConfig } from '@/config'
import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import {
  routeBounds,
  snapRoutePosition,
  type RouteBox,
  type SnapCapture,
  type SnapGuide,
} from '@/utils/route-layout'

import { useCanvasViewport } from '@/composables/useCanvasViewport'
import { useCanvasZoom, CANVAS_ZOOM_LIMITS as limits, canvasPan } from '@/composables/useCanvasZoom'

export interface StudyCanvasNode {
  card_id: string
  x: number
  y: number
  position_locked: boolean
}

export const STUDY_CARD_WIDTH = frontendConfig.canvas.study.cardWidth,
  STUDY_CARD_HEIGHT = frontendConfig.canvas.study.cardHeight
const inputTarget = (target: EventTarget | null) =>
  target instanceof Element &&
  Boolean(target.closest('input,textarea,select,button,[contenteditable="true"]'))

export function useStudyCanvas(
  container: Ref<HTMLElement | null>,
  nodes: Ref<StudyCanvasNode[]>,
  commit: (
    positions: Record<string, { x: number; y: number }>,
    basis: Record<string, { x: number; y: number }>,
  ) => void,
  notice: (message: string) => void,
) {
  const selected = ref<string[]>([]),
    inspectorOpen = ref(false)
  const camera = useCanvasViewport()
  const { pan, zoom } = camera
  const viewport = ref({ width: 800, height: 600 })
  const { applyZoom, zoomBy, wheel } = useCanvasZoom(container, camera)
  const guides = ref<SnapGuide[]>([])
  const gestureKind = ref<'idle' | 'pan' | 'drag' | 'marquee' | 'select' | 'connect'>('idle')
  const preview = ref<Record<string, { x: number; y: number }>>({})
  const positions = new Map<string, { x: number; y: number }>()
  const marquee = ref<{ x: number; y: number; width: number; height: number } | null>(null)
  let cancelGesture: (() => void) | null = null,
    space = false
  const boxes = computed<RouteBox[]>(() =>
    nodes.value.map((node) => ({
      key: node.card_id,
      ...position(node),
      width: STUDY_CARD_WIDTH,
      height: STUDY_CARD_HEIGHT,
      locked: node.position_locked,
    })),
  )
  const bounds = computed(() => routeBounds(boxes.value, 40))
  function position(node: StudyCanvasNode) {
    const moving = preview.value[node.card_id]
    if (moving) return moving
    let stable = positions.get(node.card_id)
    if (!stable || stable.x !== node.x || stable.y !== node.y) {
      stable = { x: node.x, y: node.y }
      positions.set(node.card_id, stable)
    }
    return stable
  }
  function world(clientX: number, clientY: number) {
    const rect = container.value?.getBoundingClientRect()
    return {
      x: (clientX - (rect?.left ?? 0) - pan.value.x) / zoom.value,
      y: (clientY - (rect?.top ?? 0) - pan.value.y) / zoom.value,
    }
  }
  function select(ids: string[], open = true) {
    selected.value = [...new Set(ids)]
    if (open) inspectorOpen.value = true
  }
  function cancel() {
    cancelGesture?.()
  }
  function connect(
    event: PointerEvent,
    update: (event: PointerEvent) => void,
    finish: (event: PointerEvent, dragged: boolean) => void,
    aborted: () => void,
  ) {
    if (event.button !== 0) return
    cancel()
    camera.stopView()
    container.value?.focus({ preventScroll: true })
    if (space) {
      aborted()
      return
    }
    gestureKind.value = 'connect'
    let dragged = false
    const move = (next: PointerEvent) => {
      if (next.pointerId !== event.pointerId) return
      dragged ||= Math.hypot(next.clientX - event.clientX, next.clientY - event.clientY) > 3
      update(next)
    }
    const stop = (next?: PointerEvent) => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', cancelled)
      container.value?.removeEventListener('lostpointercapture', cancelled)
      cancelGesture = null
      gestureKind.value = 'idle'
      try {
        container.value?.releasePointerCapture(event.pointerId)
      } catch {
        /* Already released. */
      }
      if (next)
        finish(
          next,
          dragged || Math.hypot(next.clientX - event.clientX, next.clientY - event.clientY) > 3,
        )
      else aborted()
    }
    const up = (next: PointerEvent) => {
      if (next.pointerId === event.pointerId) stop(next)
    }
    const cancelled = (next: Event) => {
      if ((next as PointerEvent).pointerId === event.pointerId) stop()
    }
    cancelGesture = () => stop()
    try {
      container.value?.setPointerCapture(event.pointerId)
    } catch {
      /* Synthetic pointers. */
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', cancelled)
    container.value?.addEventListener('lostpointercapture', cancelled)
  }
  function fit(centerOnly = false, cardIds?: string[]) {
    if (!container.value) return
    cancel()
    const width = container.value.clientWidth || 800,
      height = container.value.clientHeight || 600
    const ids = cardIds?.length ? cardIds : selected.value
    const scope = ids.length ? boxes.value.filter((box) => ids.includes(box.key)) : []
    let box = scope.length ? routeBounds(scope, 40) : bounds.value
    const fitScale = () => Math.min(1, (width - 32) / box.width, (height - 96) / box.height)
    // A large route remains pannable. Start with a readable entry card rather
    // than reducing every label to a handful of pixels on a phone.
    if (!centerOnly && !scope.length && fitScale() < 0.85 && boxes.value[0])
      box = routeBounds([boxes.value[0]], 24)
    const value = centerOnly ? zoom.value : Math.max(0.85, fitScale())
    const scale = Math.min(limits.max, Math.max(limits.min, value))
    camera.moveView({
      zoom: scale,
      pan: {
        x: canvasPan((width - box.width * scale) / 2 - box.left * scale),
        y: canvasPan((height - 48 - box.height * scale) / 2 - box.top * scale),
      },
    })
  }
  function pointerDown(event: PointerEvent, cardId?: string) {
    if (event.button !== 0 || inputTarget(event.target)) return
    if (
      !cardId &&
      event.target instanceof Element &&
      event.target.closest('[data-role="study-card"]')
    )
      return
    cancel()
    camera.stopView()
    container.value?.focus({ preventScroll: true })
    const originalSelection = [...selected.value],
      originPan = { ...pan.value }
    const start = world(event.clientX, event.clientY),
      startClient = { x: event.clientX, y: event.clientY }
    let capture: SnapCapture = {},
      travelled = false
    const mode: typeof gestureKind.value = space
      ? 'pan'
      : cardId
        ? event.ctrlKey || event.metaKey
          ? 'select'
          : 'drag'
        : event.shiftKey
          ? 'marquee'
          : 'pan'
    if (cardId && mode === 'drag') {
      if (!selected.value.includes(cardId)) selected.value = [cardId]
      inspectorOpen.value = true
    }
    const picked = boxes.value.filter((box) => selected.value.includes(box.key))
    const movingBox = routeBounds(picked, 0)
    const origin = Object.fromEntries(picked.map((box) => [box.key, { x: box.x, y: box.y }]))
    const fixed = picked.some((box) => box.locked)
    const obstacles = boxes.value.filter((box) => !selected.value.includes(box.key))
    gestureKind.value = mode
    try {
      container.value?.setPointerCapture(event.pointerId)
    } catch {
      /* Synthetic pointer tests may not implement capture. */
    }
    const move = (next: PointerEvent) => {
      if (next.pointerId !== event.pointerId) return
      travelled ||= Math.hypot(next.clientX - startClient.x, next.clientY - startClient.y) > 3
      if (!travelled) return
      if (mode === 'pan') {
        pan.value = {
          x: originPan.x + next.clientX - startClient.x,
          y: originPan.y + next.clientY - startClient.y,
        }
      } else if (mode === 'marquee') {
        const point = world(next.clientX, next.clientY)
        marquee.value = {
          x: Math.min(start.x, point.x),
          y: Math.min(start.y, point.y),
          width: Math.abs(point.x - start.x),
          height: Math.abs(point.y - start.y),
        }
        const area = marquee.value
        const inside = boxes.value
          .filter(
            (box) =>
              box.x + box.width >= area.x &&
              box.x <= area.x + area.width &&
              box.y + box.height >= area.y &&
              box.y <= area.y + area.height,
          )
          .map((box) => box.key)
        selected.value =
          event.ctrlKey || event.metaKey ? [...new Set([...originalSelection, ...inside])] : inside
      } else if (mode === 'drag' && !fixed) {
        const dx = (next.clientX - startClient.x) / zoom.value,
          dy = (next.clientY - startClient.y) / zoom.value
        const raw = {
          key: '__selection__',
          x: movingBox.left + dx,
          y: movingBox.top + dy,
          width: movingBox.width,
          height: movingBox.height,
        }
        const snapped = next.altKey
          ? { ...raw, guides: [], capture: {} }
          : snapRoutePosition(raw, obstacles, zoom.value, 7, { equalGaps: true, previous: capture })
        let deltaX = snapped.x - movingBox.left,
          deltaY = snapped.y - movingBox.top
        deltaX = Math.max(
          -20000 - movingBox.left,
          Math.min(20000 - Math.max(...picked.map((box) => box.x)), deltaX),
        )
        deltaY = Math.max(
          -20000 - movingBox.top,
          Math.min(20000 - Math.max(...picked.map((box) => box.y)), deltaY),
        )
        preview.value = Object.fromEntries(
          picked.map((box) => [
            box.key,
            { x: origin[box.key]!.x + deltaX, y: origin[box.key]!.y + deltaY },
          ]),
        )
        const constrained =
          Math.abs(deltaX - (snapped.x - movingBox.left)) > 1e-6 ||
          Math.abs(deltaY - (snapped.y - movingBox.top)) > 1e-6
        guides.value = constrained ? [] : snapped.guides
        capture = constrained ? {} : snapped.capture
      }
    }
    const stop = (cancelled = false) => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      window.removeEventListener('pointercancel', aborted)
      container.value?.removeEventListener('lostpointercapture', lost)
      cancelGesture = null
      const final = preview.value
      preview.value = {}
      guides.value = []
      marquee.value = null
      gestureKind.value = 'idle'
      try {
        container.value?.releasePointerCapture(event.pointerId)
      } catch {
        /* Already lost capture. */
      }
      if (cancelled) {
        pan.value = originPan
        selected.value = originalSelection
        return
      }
      if (mode === 'select' && cardId)
        select(
          originalSelection.includes(cardId)
            ? originalSelection.filter((id) => id !== cardId)
            : [...originalSelection, cardId],
        )
      else if (mode === 'drag') {
        if (travelled && fixed) notice('选中内容含固定卡片，请先解除固定再整体移动。')
        else if (
          travelled &&
          Object.keys(final).some(
            (id) => final[id]!.x !== origin[id]!.x || final[id]!.y !== origin[id]!.y,
          )
        )
          commit(final, origin)
      } else if (mode === 'pan' && !travelled) selected.value = []
    }
    const up = (next: PointerEvent) => {
      if (next.pointerId === event.pointerId) stop()
    }
    const aborted = (next: PointerEvent) => {
      if (next.pointerId === event.pointerId) stop(true)
    }
    const lost = (next: Event) => {
      if ((next as PointerEvent).pointerId === event.pointerId) stop(true)
    }
    cancelGesture = () => stop(true)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    window.addEventListener('pointercancel', aborted)
    container.value?.addEventListener('lostpointercapture', lost)
  }
  function down(event: KeyboardEvent) {
    if (inputTarget(event.target)) return
    if (event.code === 'Space' && container.value?.contains(document.activeElement)) {
      event.preventDefault()
      space = true
    }
    if (event.key === 'Escape') cancel()
  }
  function up(event: KeyboardEvent) {
    if (event.code === 'Space') space = false
  }
  function blur() {
    space = false
    cancel()
  }
  watch(
    () => nodes.value.map((node) => node.card_id).join('|'),
    () => {
      cancel()
      const visible = new Set(nodes.value.map((node) => node.card_id))
      for (const id of positions.keys()) if (!visible.has(id)) positions.delete(id)
      selected.value = selected.value.filter((id) => visible.has(id))
    },
  )
  let resize: ResizeObserver | null = null
  onMounted(() => {
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('blur', blur)
    const element = container.value
    if (element && typeof ResizeObserver !== 'undefined') {
      let width = element.clientWidth,
        height = element.clientHeight
      if (width && height) viewport.value = { width, height }
      resize = new ResizeObserver(() => {
        const nextWidth = element.clientWidth,
          nextHeight = element.clientHeight
        if (nextWidth && nextHeight) viewport.value = { width: nextWidth, height: nextHeight }
        if (width && height && nextWidth && nextHeight) {
          cancel()
          camera.stopView()
          pan.value = {
            x: pan.value.x + (nextWidth - width) / 2,
            y: pan.value.y + (nextHeight - height) / 2,
          }
        }
        width = nextWidth
        height = nextHeight
      })
      resize.observe(element)
    }
  })
  onBeforeUnmount(() => {
    resize?.disconnect()
    cancel()
    window.removeEventListener('keydown', down)
    window.removeEventListener('keyup', up)
    window.removeEventListener('blur', blur)
  })
  return {
    selected,
    inspectorOpen,
    pan,
    zoom,
    viewport,
    guides,
    gestureKind,
    marquee,
    boxes,
    bounds,
    position,
    world,
    select,
    cancel,
    connect,
    pointerDown,
    wheel,
    applyZoom,
    zoomBy,
    fit,
  }
}
