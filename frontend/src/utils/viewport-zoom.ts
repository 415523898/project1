export interface ZoomLimits {
  min: number
  max: number
}

export interface WheelState {
  accumulator: number
}

export function clampZoom(value: number, limits: ZoomLimits): number {
  return Math.min(limits.max, Math.max(limits.min, value))
}

export function zoomStep(value: number): number {
  return Math.pow(2, Math.round(Math.log2(value)) - 4)
}

export function snapZoom(value: number, limits: ZoomLimits): number {
  const bounded = clampZoom(value, limits)
  const step = zoomStep(bounded)
  return clampZoom(Math.round(bounded / step) * step, limits)
}

export function alignPan(value: number, ratio = 1): number {
  return Math.round(value * ratio) / ratio
}

export function wheelNotches(
  state: WheelState,
  deltaY: number,
  deltaMode = 0,
  notch = 100,
): number {
  const scale = deltaMode === 1 ? 16 : deltaMode === 2 ? 400 : 1
  state.accumulator += -deltaY * scale
  const notches = state.accumulator / notch
  if (Math.abs(notches) < 1) return 0
  state.accumulator -= Math.trunc(notches) * notch
  return notches
}

export function zoomFactor(notches: number, perNotch: number): number {
  return Math.exp(notches * perNotch)
}

/** Keep the image coordinate under the cursor fixed while changing scale. */
export function zoomAt(
  pan: { x: number; y: number },
  cursor: { x: number; y: number },
  before: number,
  after: number,
) {
  const ratio = after / before
  return { x: cursor.x - (cursor.x - pan.x) * ratio, y: cursor.y - (cursor.y - pan.y) * ratio }
}
