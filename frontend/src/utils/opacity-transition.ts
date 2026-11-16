/** Compositor fades avoid Vue's CSS-transition forced layout on a newly populated graph. */
export function opacityTransition(enterMs = 180, leaveMs = 120) {
  const animations = new WeakMap<Element, Animation>()
  const fade = (element: Element, done: () => void, entering: boolean) => {
    const previous = animations.get(element)
    let from = entering ? 0 : 1
    if (
      previous?.effect &&
      typeof KeyframeEffect !== 'undefined' &&
      previous.effect instanceof KeyframeEffect
    ) {
      const frames = previous.effect.getKeyframes()
      const progress = previous.effect.getComputedTiming().progress ?? 1
      from =
        Number(frames[0]?.opacity ?? from) +
        (Number(frames.at(-1)?.opacity ?? from) - Number(frames[0]?.opacity ?? from)) * progress
    }
    previous?.cancel()
    if (!element.animate || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      done()
      return
    }
    const animation = element.animate([{ opacity: from }, { opacity: entering ? 1 : 0 }], {
      duration: entering ? enterMs : leaveMs,
      easing: 'ease-out',
      fill: 'both',
    })
    animations.set(element, animation)
    const finish = () => {
      if (animations.get(element) === animation) animations.delete(element)
      done()
      animation.cancel()
    }
    void animation.finished.then(finish, () => {
      if (animations.get(element) === animation) {
        animations.delete(element)
        done()
      }
    })
  }
  return {
    enter: (element: Element, done: () => void) => fade(element, done, true),
    leave: (element: Element, done: () => void) => fade(element, done, false),
  }
}
