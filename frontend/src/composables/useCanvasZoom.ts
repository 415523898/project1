import { frontendConfig } from '@/config'
import { onBeforeUnmount, type Ref } from 'vue'
import type { CanvasView } from '@/composables/useCanvasViewport'
import { alignPan, snapZoom, wheelNotches, zoomFactor } from '@/utils/viewport-zoom'

export const CANVAS_ZOOM_LIMITS = frontendConfig.canvas.zoom
export const canvasDeviceRatio = () => window.devicePixelRatio || 1
export const canvasPan = (value: number) => alignPan(value, canvasDeviceRatio())

interface Camera {
  getView: () => CanvasView
  currentView: () => CanvasView
  moveView: (view: CanvasView) => void
  setView: (view: CanvasView) => void
}

export function useCanvasZoom(container: Ref<HTMLElement | null>, camera: Camera) {
  const state = { accumulator: 0 }
  let idle: ReturnType<typeof setTimeout> | undefined
  function applyZoom(value: number, clientX?: number, clientY?: number) {
    const view = camera.currentView()
    const next = snapZoom(value, CANVAS_ZOOM_LIMITS)
    const rect = container.value?.getBoundingClientRect()
    if (!rect) {
      camera.moveView({ ...view, zoom: next })
      return
    }
    const x = clientX === undefined ? rect.width / 2 : clientX - rect.left
    const y = clientY === undefined ? rect.height / 2 : clientY - rect.top
    const ratio = next / view.zoom
    camera.moveView({
      zoom: next,
      pan: {
        x: canvasPan(x - (x - view.pan.x) * ratio),
        y: canvasPan(y - (y - view.pan.y) * ratio),
      },
    })
  }
  function zoomBy(factor: number) {
    applyZoom(camera.getView().zoom * factor)
  }
  function wheel(event: WheelEvent) {
    if (event.deltaY === 0 && event.deltaX === 0) return
    event.preventDefault()
    if (event.ctrlKey || event.metaKey || event.shiftKey) {
      applyZoom(
        camera.getView().zoom * Math.exp(-event.deltaY * 0.01),
        event.clientX,
        event.clientY,
      )
      return
    }
    if (event.deltaMode === 0 && Math.abs(event.deltaX) > 0.5 && Math.abs(event.deltaY) < 0.5) {
      const view = camera.currentView()
      camera.setView({
        ...view,
        pan: { x: canvasPan(view.pan.x - event.deltaX), y: canvasPan(view.pan.y - event.deltaY) },
      })
      return
    }
    if (idle) clearTimeout(idle)
    idle = setTimeout(() => {
      state.accumulator = 0
    }, 160)
    const notches = wheelNotches(state, event.deltaY, event.deltaMode, 100)
    if (notches)
      applyZoom(camera.getView().zoom * zoomFactor(notches, 0.14), event.clientX, event.clientY)
  }
  onBeforeUnmount(() => {
    if (idle) clearTimeout(idle)
  })
  return { applyZoom, zoomBy, wheel }
}
