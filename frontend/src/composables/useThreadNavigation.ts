import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { ChatTurn } from '@/types'

/** Follow the visible conversation only; an older message stays put while reading. */
export function useThreadNavigation(
  session: Readonly<Ref<string | null>>,
  turns: Readonly<Ref<ChatTurn[]>>,
) {
  const scroll = ref<HTMLElement | null>(null)
  const content = ref<HTMLElement | null>(null)
  const active = ref(0)
  let following = true
  let frame = 0
  let revision = 0
  let observer: ResizeObserver | undefined
  let dimensions = ''
  let cachedAnchors: HTMLElement[] = []
  let anchorRoot: HTMLElement | null = null

  const size = (host: HTMLElement) =>
    `${host.clientWidth}/${host.clientHeight}/${host.scrollHeight}`

  function anchors(): HTMLElement[] {
    if (anchorRoot !== content.value || cachedAnchors.length !== turns.value.length) {
      anchorRoot = content.value
      cachedAnchors = Array.from(
        content.value?.querySelectorAll<HTMLElement>('[data-turn-index]') ?? [],
      )
    }
    return cachedAnchors
  }

  function updateActive(): void {
    const host = scroll.value
    if (!host) return
    if (host.scrollHeight - host.clientHeight - host.scrollTop <= 2) {
      active.value = Math.max(0, turns.value.length - 1)
      return
    }
    const threshold = host.getBoundingClientRect().top + Math.min(120, host.clientHeight * 0.28)
    const items = anchors()
    let low = 0
    let high = items.length
    while (low < high) {
      const middle = (low + high) >>> 1
      if (items[middle]!.getBoundingClientRect().top <= threshold) low = middle + 1
      else high = middle
    }
    active.value = low ? Number(items[low - 1]!.dataset.turnIndex) : 0
  }

  function layout(): void {
    const host = scroll.value
    if (host) {
      dimensions = size(host)
      const bottom = host.scrollHeight - host.clientHeight
      if (following && Math.abs(bottom - host.scrollTop) > 1) host.scrollTop = bottom
    }
    updateActive()
  }

  function schedule(): void {
    if (frame) return
    frame = requestAnimationFrame(() => {
      frame = 0
      layout()
    })
  }

  async function followLatest(): Promise<void> {
    const current = ++revision
    following = true
    await nextTick()
    if (current !== revision) return
    layout()
    schedule()
  }

  function onScroll(): void {
    const host = scroll.value
    if (!host) return
    if (host.scrollHeight - host.clientHeight - host.scrollTop <= 2) following = true
    else if (following && dimensions !== size(host)) {
      // Reflow may dispatch scroll before ResizeObserver (for example sidebar width changes).
      schedule()
      return
    } else following = false
    // A scroll event must never write scrollTop: only content/layout changes follow.
    updateActive()
  }

  function pauseFollowing(): void {
    following = false
    ++revision
  }
  function onWheel(event: WheelEvent): void {
    if (event.deltaY < 0) pauseFollowing()
  }
  function onKeydown(event: KeyboardEvent): void {
    if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) pauseFollowing()
  }
  function onPointerdown(event: PointerEvent): void {
    if (event.target === scroll.value) pauseFollowing()
  }

  function jumpTo(index: number): void {
    const host = scroll.value
    const anchor = anchors().find((item) => Number(item.dataset.turnIndex) === index)
    if (!host || !anchor) return
    ++revision
    following = false
    if (frame) {
      cancelAnimationFrame(frame)
      frame = 0
    }
    host.scrollTop =
      index === 0
        ? 0
        : Math.max(
            0,
            host.scrollTop +
              anchor.getBoundingClientRect().top -
              host.getBoundingClientRect().top -
              16,
          )
    updateActive()
  }

  watch(
    [session, () => turns.value],
    () => {
      void followLatest()
    },
    { flush: 'post' },
  )
  watch(
    () => turns.value.length,
    (length, previous) => {
      if (length > previous) void followLatest()
    },
    { flush: 'post' },
  )

  onMounted(() => {
    observer = new ResizeObserver(schedule)
    if (content.value) observer.observe(content.value)
    if (scroll.value) observer.observe(scroll.value)
    void followLatest()
  })
  onBeforeUnmount(() => {
    ++revision
    observer?.disconnect()
    if (frame) cancelAnimationFrame(frame)
  })
  return {
    scroll,
    content,
    active,
    onScroll,
    jumpTo,
    followLatest,
    pauseFollowing,
    onWheel,
    onKeydown,
    onPointerdown,
  }
}
