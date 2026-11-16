export interface CanvasRect {
  x: number
  y: number
  width: number
  height: number
}

export function rectsOverlap(a: CanvasRect, b: CanvasRect): boolean {
  return (
    a.x <= b.x + b.width && b.x <= a.x + a.width && a.y <= b.y + b.height && b.y <= a.y + a.height
  )
}

export function createCanvasSpatialIndex(cellSize = 512) {
  const entries = new Map<string, { bounds: CanvasRect; cells: string[] | null }>()
  const cells = new Map<string, Set<string>>()
  const spanning = new Set<string>()
  function keys(bounds: CanvasRect, limit: number): string[] | null {
    const left = Math.floor(bounds.x / cellSize),
      top = Math.floor(bounds.y / cellSize)
    const right = Math.floor((bounds.x + bounds.width) / cellSize),
      bottom = Math.floor((bounds.y + bounds.height) / cellSize)
    if (
      ![left, top, right, bottom].every(Number.isFinite) ||
      (right - left + 1) * (bottom - top + 1) > limit
    )
      return null
    const result: string[] = []
    for (let x = left; x <= right; x++) for (let y = top; y <= bottom; y++) result.push(`${x}:${y}`)
    return result
  }
  function remove(id: string) {
    const entry = entries.get(id)
    if (!entry) return
    if (entry.cells)
      for (const key of entry.cells) {
        const bucket = cells.get(key)
        bucket?.delete(id)
        if (!bucket?.size) cells.delete(key)
      }
    spanning.delete(id)
    entries.delete(id)
  }
  function set(id: string, bounds: CanvasRect) {
    remove(id)
    const occupied = keys(bounds, 64)
    entries.set(id, { bounds: { ...bounds }, cells: occupied })
    if (!occupied) spanning.add(id)
    else
      for (const key of occupied) {
        let bucket = cells.get(key)
        if (!bucket) {
          bucket = new Set()
          cells.set(key, bucket)
        }
        bucket.add(id)
      }
  }
  function search(bounds: CanvasRect): string[] {
    const occupied = keys(bounds, 4096)
    const ids = occupied ? new Set(spanning) : new Set(entries.keys())
    if (occupied) for (const key of occupied) for (const id of cells.get(key) ?? []) ids.add(id)
    return [...ids].filter((id) => rectsOverlap(entries.get(id)!.bounds, bounds))
  }
  return { set, remove, search }
}
