import { computed, ref } from 'vue'
import {
  sessionCardsApi,
  SessionCardsError,
  type SessionCardJob,
  type SessionCardList,
} from '@/services/session-cards'
import type { ProviderConfig } from '@/services/agent'

/** Independent from the active chat stream; a remount resumes the persisted server task. */
export function createSessionCardsState(api = sessionCardsApi) {
  const owner = ref(''),
    session = ref(''),
    data = ref<SessionCardList | null>(null),
    job = ref<SessionCardJob | null>(null)
  const loading = ref(false),
    starting = ref(false),
    error = ref('')
  const readingResult = ref(false),
    syncFailed = ref(false)
  const clientTimings = ref({ accepted_ms: 0, readback_ms: 0, total_ms: 0 })
  const requests = new Set<AbortController>()
  let generation = 0,
    epoch = 0,
    readSequence = 0,
    readFailures = 0,
    clickedAt = 0,
    timer: ReturnType<typeof setTimeout> | null = null
  let listFlight: { version: number; epoch: number; promise: Promise<void> } | null = null
  const running = computed(
    () =>
      starting.value ||
      (!syncFailed.value && (job.value?.status === 'running' || readingResult.value)),
  )
  async function request<T>(call: (signal: AbortSignal) => Promise<T>) {
    const controller = new AbortController()
    requests.add(controller)
    const timeout = setTimeout(
      () => controller.abort(new DOMException('读取超过 15 秒。', 'TimeoutError')),
      15000,
    )
    try {
      return await call(controller.signal)
    } finally {
      clearTimeout(timeout)
      requests.delete(controller)
    }
  }
  function reset() {
    generation++
    epoch++
    readSequence++
    if (timer) clearTimeout(timer)
    timer = null
    for (const controller of requests) controller.abort()
    requests.clear()
    data.value = null
    job.value = null
    error.value = ''
    loading.value = false
    starting.value = false
    listFlight = null
    readingResult.value = false
    syncFailed.value = false
    readFailures = 0
    clickedAt = 0
    clientTimings.value = { accepted_ms: 0, readback_ms: 0, total_ms: 0 }
  }
  function refresh(version = generation): Promise<void> {
    if (listFlight?.version === version && listFlight.epoch === epoch) return listFlight.promise
    const ticket = epoch,
      sequence = ++readSequence,
      started = performance.now(),
      sid = session.value,
      user = owner.value
    const promise = (async () => {
      const result = await request((signal) =>
        data.value?.stamp
          ? api.list(sid, user, signal, data.value.stamp)
          : api.list(sid, user, signal),
      )
      if (version !== generation || ticket !== epoch || sequence !== readSequence) return
      if ('unchanged' in result) {
        readingResult.value = false
        syncFailed.value = false
        readFailures = 0
        error.value = ''
        schedule(version)
        return
      }
      const reused = job.value?.reused && job.value.operation_id === result.job?.operation_id,
        wasReading = readingResult.value
      data.value = result
      job.value = result.job ? { ...result.job, ...(reused ? { reused: true } : {}) } : null
      readingResult.value = false
      syncFailed.value = false
      readFailures = 0
      error.value = ''
      if (wasReading || !clickedAt)
        clientTimings.value.readback_ms = Math.round(performance.now() - started)
      if (wasReading && clickedAt)
        clientTimings.value.total_ms = Math.round(performance.now() - clickedAt)
      schedule(version)
    })()
    const flight = { version, epoch: ticket, promise }
    listFlight = flight
    void promise
      .finally(() => {
        if (listFlight === flight) listFlight = null
      })
      .catch(() => {})
    return promise
  }
  function schedule(version: number, wait = 1000) {
    if (timer) clearTimeout(timer)
    if (
      version !== generation ||
      syncFailed.value ||
      (job.value?.status !== 'running' && !readingResult.value)
    )
      return
    timer = setTimeout(() => {
      timer = null
      void poll(version)
    }, wait)
  }
  async function poll(version = generation) {
    const id = job.value?.operation_id,
      ticket = epoch
    if (!id) return
    try {
      if (readingResult.value && job.value?.status !== 'running') {
        await refresh(version)
        return
      }
      const result = await request((signal) => api.job(id, owner.value, signal))
      if (version !== generation || ticket !== epoch) return
      job.value = result
      error.value = ''
      if (result.status !== 'running') {
        readingResult.value = true
        await refresh(version)
        if (version === generation && result.failure) error.value = result.failure.error
      }
    } catch (problem) {
      if (version === generation && ticket === epoch) {
        if (problem instanceof SessionCardsError && [401, 403, 404, 409].includes(problem.status)) {
          error.value = problem.message
          if (job.value) job.value = { ...job.value, status: 'interrupted' }
          readingResult.value = false
        } else {
          readFailures++
          if (readFailures > 3) {
            syncFailed.value = true
            readingResult.value = false
            error.value =
              '暂时无法读取更新结果，原任务和已保存内容均保留。可重新读取，无需再运行 AI。'
          } else
            error.value = readingResult.value
              ? '卡片已提交，正在自动重新读取。'
              : '暂时无法读取进度，任务可能仍在后台运行；正在重新连接。'
        }
      }
    } finally {
      if (ticket === epoch) schedule(version)
    }
  }
  async function bind(nextOwner: string, nextSession: string) {
    reset()
    owner.value = nextOwner
    session.value = nextSession
    if (!nextOwner || !nextSession) return
    const version = generation
    loading.value = true
    try {
      await refresh(version)
      schedule(version)
    } catch (problem) {
      if (version === generation) error.value = (problem as Error).message
    } finally {
      if (version === generation) loading.value = false
    }
  }
  async function start(instruction: string, provider: ProviderConfig) {
    if (running.value || !owner.value || !session.value) return
    const version = generation
    epoch++
    readSequence++
    if (timer) clearTimeout(timer)
    timer = null
    clickedAt = performance.now()
    clientTimings.value = { accepted_ms: 0, readback_ms: 0, total_ms: 0 }
    syncFailed.value = false
    readFailures = 0
    job.value = null
    const id =
      'session-' +
      (globalThis.crypto?.randomUUID?.() ??
        Date.now().toString(36) + '-' + Math.random().toString(36).slice(2))
    starting.value = true
    error.value = ''
    try {
      const result = await request((signal) =>
        api.start(
          { operation_id: id, session_id: session.value, instruction, provider },
          owner.value,
          signal,
        ),
      )
      if (version !== generation) return
      clientTimings.value.accepted_ms = Math.round(performance.now() - clickedAt)
      job.value = result
      if (result.status === 'succeeded') {
        readingResult.value = true
        await refresh(version)
      } else schedule(version, 150)
    } catch (problem) {
      if (version !== generation) return
      if (job.value?.status === 'succeeded') {
        readingResult.value = true
        error.value = '卡片已提交，正在自动重新读取。'
        schedule(version, 250)
      } else if (
        !(problem instanceof SessionCardsError) ||
        problem.status >= 500 ||
        [408, 429].includes(problem.status)
      ) {
        // The POST may have committed before a timeout; confirm its stable id.
        job.value = { operation_id: id, session_id: session.value, status: 'running' }
        error.value = '请求结果待确认，正在检查原任务。'
        schedule(version)
      } else error.value = problem.message
    } finally {
      if (version === generation) starting.value = false
    }
  }
  async function cancel() {
    const id = job.value?.operation_id,
      version = generation
    if (!id || starting.value || job.value?.status !== 'running') return
    epoch++
    readSequence++
    try {
      const result = await request((signal) => api.cancel(id, owner.value, signal))
      if (version !== generation) return
      if (timer) clearTimeout(timer)
      timer = null
      job.value = result
      await refresh(version)
    } catch (problem) {
      if (version === generation) error.value = (problem as Error).message
    }
  }
  return {
    data,
    job,
    running,
    loading,
    starting,
    readingResult,
    syncFailed,
    clientTimings,
    error,
    bind,
    start,
    cancel,
    reset,
    refresh,
  }
}
