import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

/** Retain native modal/focus behavior until the exit completes, including rapid reopen. */
export function useDialogMotion(
  dialog: Ref<HTMLDialogElement | null>,
  isOpen: () => boolean,
  options: {
    beforeOpen?: () => void
    afterClose?: () => void
    requestClose: () => void
  },
) {
  let animation: Animation | undefined,
    revision = 0
  watch(
    [dialog, isOpen],
    async ([node, open]) => {
      const current = ++revision
      const interrupted = Boolean(animation)
      const from = node?.open
        ? { opacity: getComputedStyle(node).opacity, transform: getComputedStyle(node).transform }
        : null
      animation?.cancel()
      animation = undefined
      if (!node) return
      if (open && !node.open) {
        options.beforeOpen?.()
        await nextTick()
        if (current !== revision || !isOpen()) return
        node.showModal()
      } else if (!open && !node.open) return
      node.dataset.motion = open ? 'opening' : 'closing'
      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      if (node.animate && !reduced) {
        const start =
          interrupted && from
            ? from
            : open
              ? { opacity: '0', transform: 'translateY(10px) scale(.985)' }
              : { opacity: '1', transform: 'none' }
        const end = open
          ? { opacity: '1', transform: 'none' }
          : { opacity: '0', transform: 'translateY(6px) scale(.99)' }
        animation = node.animate([start, end], {
          duration: open ? 200 : 140,
          easing: 'cubic-bezier(.2,.7,.2,1)',
          fill: 'both',
        })
        await animation.finished.catch(() => {})
        if (current !== revision) return
        animation.cancel()
        animation = undefined
      }
      node.dataset.motion = open ? 'open' : 'closed'
      if (!open) {
        node.close()
        options.afterClose?.()
      }
    },
    { flush: 'post', immediate: true },
  )
  onBeforeUnmount(() => {
    ++revision
    animation?.cancel()
    if (dialog.value?.open) dialog.value.close()
  })
  function onNativeClose(event: Event) {
    // Native close events are queued; ignore an old event after the same modal reopens.
    if (event.target === dialog.value && !dialog.value?.open && isOpen()) options.requestClose()
  }
  return { onNativeClose }
}

/** Animate intrinsic page changes without a fixed-height dialog or a last-frame shrink. */
export function useDialogSizeMotion(
  dialog: Ref<HTMLDialogElement | null>,
  region: Ref<HTMLElement | null>,
  isOpen: () => boolean,
) {
  let observer: ResizeObserver | undefined,
    animation: Animation | undefined,
    lastHeight = 0,
    revision = 0
  let frame: number | undefined,
    lastContent = '',
    viewportChanging = false,
    settle: number | undefined
  const compact = window.matchMedia('(max-width: 760px)')
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
  function clear() {
    ++revision
    animation?.cancel()
    animation = undefined
    if (dialog.value) {
      dialog.value.style.height = ''
      delete dialog.value.dataset.resizing
    }
  }
  function viewportChanged() {
    viewportChanging = true
    clear()
    if (settle !== undefined) window.clearTimeout(settle)
    settle = window.setTimeout(() => {
      viewportChanging = false
      lastHeight = dialog.value?.offsetHeight ?? 0
    }, 250)
  }
  window.addEventListener('resize', viewportChanged)
  window.visualViewport?.addEventListener('resize', viewportChanged)
  compact.addEventListener?.('change', viewportChanged)
  reduced.addEventListener?.('change', viewportChanged)
  watch(
    [dialog, region, isOpen],
    ([node, body, open]) => {
      observer?.disconnect()
      if (frame !== undefined) cancelAnimationFrame(frame)
      frame = undefined
      if (!node || !body) {
        clear()
        return
      }
      clear()
      lastHeight = node.offsetHeight
      lastContent = ''
      if (!open || typeof ResizeObserver === 'undefined') return
      observer = new ResizeObserver(() => {
        // Observe intrinsic content only. The animated dialog is an output, never an input.
        const content = `${body.scrollHeight}:${body.offsetWidth}`
        if (content === lastContent) return
        const initial = !lastContent
        lastContent = content
        if (initial) {
          lastHeight = node.offsetHeight
          return
        }
        if (frame !== undefined) return
        frame = requestAnimationFrame(() => {
          frame = undefined
          if (
            !node.open ||
            node.dataset.motion !== 'open' ||
            compact.matches ||
            reduced.matches ||
            viewportChanging
          ) {
            clear()
            lastHeight = node.offsetHeight
            return
          }
          const from = animation ? node.getBoundingClientRect().height : lastHeight
          clear()
          const to = node.offsetHeight,
            border = node.offsetHeight - node.clientHeight
          if (Math.abs(from - to) < 1 || !node.animate) {
            lastHeight = to
            return
          }
          const current = ++revision
          node.style.height = `${to - border}px`
          node.dataset.resizing = 'true'
          const resize = node.animate(
            [
              { height: `${Math.max(0, from - border)}px` },
              { height: `${Math.max(0, to - border)}px` },
            ],
            { duration: 200, easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'both' },
          )
          animation = resize
          void resize.finished.then(
            () => {
              if (current === revision) {
                clear()
                lastHeight = node.offsetHeight
              }
            },
            () => {},
          )
        })
      })
      observer.observe(body)
    },
    { flush: 'post', immediate: true },
  )
  onBeforeUnmount(() => {
    observer?.disconnect()
    clear()
    if (frame !== undefined) cancelAnimationFrame(frame)
    if (settle !== undefined) window.clearTimeout(settle)
    window.removeEventListener('resize', viewportChanged)
    window.visualViewport?.removeEventListener('resize', viewportChanged)
    compact.removeEventListener?.('change', viewportChanged)
    reduced.removeEventListener?.('change', viewportChanged)
  })
}

/** Keyboard/toolbars may resize the visual viewport without resizing the layout viewport. */
export function useDialogViewport(dialog: Ref<HTMLDialogElement | null>) {
  let frame: number | undefined
  function update() {
    if (frame !== undefined) return
    frame = requestAnimationFrame(() => {
      frame = undefined
      const viewport = window.visualViewport
      dialog.value?.toggleAttribute(
        'data-compact-height',
        (viewport?.height ?? window.innerHeight) <= 480,
      )
      dialog.value?.style.setProperty(
        '--dialog-viewport-height',
        `${viewport?.height ?? window.innerHeight}px`,
      )
      dialog.value?.style.setProperty('--dialog-viewport-top', `${viewport?.offsetTop ?? 0}px`)
    })
  }
  watch(dialog, update, { flush: 'post' })
  window.addEventListener('resize', update)
  window.visualViewport?.addEventListener('resize', update)
  window.visualViewport?.addEventListener('scroll', update)
  onBeforeUnmount(() => {
    if (frame !== undefined) cancelAnimationFrame(frame)
    window.removeEventListener('resize', update)
    window.visualViewport?.removeEventListener('resize', update)
    window.visualViewport?.removeEventListener('scroll', update)
  })
}
