import { nextTick, type ObjectDirective } from 'vue'

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

// Restore inline styles when a transition finishes or reverses direction.
const pending = new WeakMap<HTMLElement, () => void>()
function animateHeight(
  element: HTMLElement,
  from: number,
  to: number,
  opening: boolean,
  done: () => void,
): void {
  pending.get(element)?.()
  if (reducedMotion() || typeof element.animate !== 'function') {
    done()
    return
  }
  const overflow = element.style.overflow
  const boxSizing = element.style.boxSizing
  const pointerEvents = element.style.pointerEvents
  element.style.overflow = 'hidden'
  element.style.boxSizing = 'border-box'
  if (!opening) element.style.pointerEvents = 'none'
  const animation = element.animate(
    [
      { height: `${from}px`, opacity: opening ? 0 : 1 },
      { height: `${to}px`, opacity: opening ? 1 : 0 },
    ],
    { duration: opening ? 200 : 140, easing: 'cubic-bezier(.22, 1, .36, 1)' },
  )
  const restore = () => {
    element.style.overflow = overflow
    element.style.boxSizing = boxSizing
    element.style.pointerEvents = pointerEvents
    pending.delete(element)
  }
  pending.set(element, () => {
    animation.cancel()
    restore()
  })
  void animation.finished.then(
    () => {
      restore()
      done()
    },
    () => {},
  )
}

export function enterDisclosure(node: Element, done: () => void): void {
  const element = node as HTMLElement
  animateHeight(element, 0, element.getBoundingClientRect().height, true, done)
}
export function leaveDisclosure(node: Element, done: () => void): void {
  const element = node as HTMLElement
  animateHeight(element, element.getBoundingClientRect().height, 0, false, done)
}
export function cancelDisclosure(node: Element): void {
  pending.get(node as HTMLElement)?.()
}

// Native <details> keeps its summary visible while its content fades and resizes.
const cleanups = new WeakMap<HTMLDetailsElement, () => void>()
export const vDisclosureMotion: ObjectDirective<
  HTMLDetailsElement,
  ((open: boolean) => void) | undefined
> = {
  mounted(details, binding) {
    let target = details.open
    let inFlight = false
    let revision = 0
    let animations: Animation[] = []
    let restore = () => {}
    const cancel = () => {
      animations.forEach((animation) => animation.cancel())
      animations = []
      restore()
      restore = () => {}
    }
    const toggle = async (event: MouseEvent) => {
      const summary = details.querySelector(':scope > summary')
      if (!(event.target instanceof Node) || !summary?.contains(event.target)) return
      if (event.target instanceof Element && event.target.closest('a, button, input, select'))
        return
      event.preventDefault()
      const stamp = ++revision
      const from = details.getBoundingClientRect().height
      target = inFlight ? !target : !details.open
      inFlight = true
      cancel()
      details.dataset.disclosureExpanded = String(target)
      // Prepare lazy content before nextTick, so the animation measures its final height.
      // Native toggle is delivered in a later task and can arrive after that measurement.
      binding.value?.(target)
      const compactSettings =
        details.closest('.settings-dialog,.model-config-dialog') &&
        window.matchMedia('(max-width: 760px)').matches
      if (reducedMotion() || compactSettings || typeof details.animate !== 'function') {
        details.open = target
        inFlight = false
        return
      }
      // Closing stays open until its content has faded; rapid toggles cancel cleanly.
      details.open = true
      await nextTick()
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
      if (stamp !== revision || !details.isConnected) return
      const style = getComputedStyle(details)
      const summaryStyle = getComputedStyle(summary!)
      const collapsed =
        summary!.getBoundingClientRect().height +
        parseFloat(style.paddingTop) +
        parseFloat(style.paddingBottom) +
        parseFloat(style.borderTopWidth) +
        parseFloat(style.borderBottomWidth) +
        parseFloat(summaryStyle.marginTop) +
        parseFloat(summaryStyle.marginBottom)
      const height = target ? details.getBoundingClientRect().height : collapsed
      const overflow = details.style.overflow
      const boxSizing = details.style.boxSizing
      details.style.overflow = 'hidden'
      details.style.boxSizing = 'border-box'
      restore = () => {
        details.style.overflow = overflow
        details.style.boxSizing = boxSizing
      }
      const timing = { duration: target ? 200 : 140, easing: 'cubic-bezier(.22, 1, .36, 1)' }
      animations = [details.animate([{ height: `${from}px` }, { height: `${height}px` }], timing)]
      for (const child of details.children) {
        if (child !== summary)
          animations.push(
            child.animate([{ opacity: target ? 0 : 1 }, { opacity: target ? 1 : 0 }], timing),
          )
      }
      void Promise.all(animations.map((animation) => animation.finished)).then(
        () => {
          if (stamp !== revision) return
          details.open = target
          inFlight = false
          cancel()
        },
        () => {},
      )
    }
    details.addEventListener('click', toggle)
    cleanups.set(details, () => {
      ++revision
      cancel()
      details.removeEventListener('click', toggle)
    })
  },
  unmounted(details) {
    cleanups.get(details)?.()
    cleanups.delete(details)
  },
}
