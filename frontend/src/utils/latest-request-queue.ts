// One active task plus one newest queued task. Retries of active work share its result.
export function latestRequestQueue<T extends { id: number }, R>(
  key: (request: T) => string,
  execute: (request: T) => Promise<R>,
  reply: (request: T, result: R) => void,
  skipped: (request: T) => void,
) {
  type Group = { key: string; request: T; waiters: T[] }
  let active: Group | null = null,
    latest: Group | null = null
  async function drain(group: Group): Promise<void> {
    active = group
    try {
      const result = await execute(group.request)
      for (const waiter of group.waiters) reply(waiter, result)
    } finally {
      active = null
      if (latest) {
        const next = latest
        latest = null
        void drain(next)
      }
    }
  }
  function discardQueued(exceptKey?: string): void {
    if (latest && latest.key !== exceptKey) {
      const discarded = latest
      latest = null
      for (const waiter of discarded.waiters) skipped(waiter)
    }
  }
  return Object.assign(
    (request: T): void => {
      const identity = key(request)
      if (latest?.key === identity) {
        latest.waiters.push(request)
        return
      }
      discardQueued()
      if (active?.key === identity) {
        active.waiters.push(request)
        return
      }
      const group = { key: identity, request, waiters: [request] }
      if (active) latest = group
      else void drain(group)
    },
    { discardQueued },
  )
}
