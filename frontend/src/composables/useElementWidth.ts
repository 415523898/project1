import { onBeforeUnmount, ref, watch, type Ref } from 'vue'

/** Measure the workspace after navigation panels have taken their share. */
export function useElementWidth(element: Ref<HTMLElement | null>) {
  const width = ref(typeof window === 'undefined' ? 1200 : window.innerWidth - 56)
  let observer: ResizeObserver | null = null
  watch(
    element,
    (host) => {
      observer?.disconnect()
      if (!host) return
      const measure = () => {
        if (host.clientWidth) width.value = host.clientWidth
      }
      measure()
      if (typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(measure)
        observer.observe(host)
      }
    },
    { flush: 'post' },
  )
  onBeforeUnmount(() => observer?.disconnect())
  return width
}
