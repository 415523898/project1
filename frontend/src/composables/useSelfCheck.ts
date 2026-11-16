import { computed, ref } from 'vue'
import {
  selfCheckApi,
  SelfCheckError,
  type SelfCheckAttempt,
  type SelfCheckOperation,
  type SelfCheckState,
} from '@/services/self-check'
import type { ProviderConfig } from '@/services/agent'

const identifier = () =>
  'self-check-' +
  (globalThis.crypto?.randomUUID?.() ??
    Date.now().toString(36) + '-' + Math.random().toString(36).slice(2))
const same = (left: unknown, right: unknown) =>
  JSON.stringify(Object.entries(left ?? {}).sort()) ===
  JSON.stringify(Object.entries(right ?? {}).sort())
export function createSelfCheckState(api = selfCheckApi) {
  const data = ref<SelfCheckState | null>(null),
    attempt = ref<SelfCheckAttempt | null>(null),
    operation = ref<SelfCheckOperation | null>(null)
  const answers = ref<Record<string, string>>({}),
    error = ref(''),
    loading = ref(false),
    submitting = ref(false),
    saving = ref(false),
    dirty = ref(false),
    conflict = ref(false),
    syncFailed = ref(false)
  const historyView = ref(false),
    reading = ref(false)
  const resendAllowed = ref(false)
  let pendingSend: ((signal: AbortSignal) => Promise<SelfCheckOperation>) | null = null
  let owner = '',
    session = '',
    generation = 0,
    failures = 0,
    pollTimer: ReturnType<typeof setTimeout> | undefined,
    draftTimer: ReturnType<typeof setTimeout> | undefined
  let flight: Promise<boolean> | null = null
  let pendingFresh: string | null = null
  let stateRead = 0
  const controllers = new Set<AbortController>()
  const running = computed(
    () => submitting.value || operation.value?.status === 'running' || reading.value,
  )
  const draftKey = (id: string) =>
    'forest-self-check-draft-v1:' + encodeURIComponent(owner) + ':' + session + ':' + id
  function remember() {
    if (!attempt.value) return
    try {
      localStorage.setItem(
        draftKey(attempt.value.id),
        JSON.stringify({ answers: answers.value, base_revision: attempt.value.revision }),
      )
    } catch {
      // Browser storage is optional; the current answers remain in memory.
    }
  }
  function forget(id: string) {
    try {
      localStorage.removeItem(draftKey(id))
    } catch {
      // Browser storage is optional; the current answers remain in memory.
    }
  }
  async function request<T>(call: (signal: AbortSignal) => Promise<T>) {
    const controller = new AbortController()
    controllers.add(controller)
    const timer = setTimeout(
      () => controller.abort(new DOMException('读取自测超过 15 秒。', 'TimeoutError')),
      15000,
    )
    try {
      return await call(controller.signal)
    } finally {
      clearTimeout(timer)
      controllers.delete(controller)
    }
  }
  function reset() {
    generation++
    clearTimeout(pollTimer)
    clearTimeout(draftTimer)
    for (const c of controllers) c.abort()
    controllers.clear()
    data.value = null
    attempt.value = null
    operation.value = null
    answers.value = {}
    error.value = ''
    loading.value = false
    submitting.value = false
    saving.value = false
    dirty.value = false
    conflict.value = false
    syncFailed.value = false
    reading.value = false
    historyView.value = false
    failures = 0
    flight = null
    pendingFresh = null
    pendingSend = null
    resendAllowed.value = false
    stateRead = 0
  }
  function accept(value: SelfCheckAttempt, preserve = false) {
    if (attempt.value?.id === value.id && value.revision < attempt.value.revision) return
    const keep = preserve && attempt.value?.id === value.id && dirty.value
    const oldRevision = attempt.value?.revision
    attempt.value = value
    if (value.status !== 'ready') {
      answers.value = { ...(value.submitted ?? value.draft) }
      dirty.value = false
      conflict.value = false
      forget(value.id)
      return
    }
    if (keep) {
      if (same(value.draft, answers.value)) {
        dirty.value = false
        conflict.value = false
        forget(value.id)
      } else if (oldRevision !== value.revision) {
        conflict.value = true
        error.value = '服务器草稿已有更新，本机填写保留，请核对后再保存。'
      }
      return
    }
    let local: { answers: Record<string, string>; base_revision: number } | null = null
    try {
      local = JSON.parse(localStorage.getItem(draftKey(value.id)) || 'null')
    } catch {
      // Browser storage is optional; the current answers remain in memory.
    }
    if (local?.answers && !same(local.answers, value.draft)) {
      answers.value = { ...local.answers }
      dirty.value = true
      conflict.value = local.base_revision !== value.revision
      if (conflict.value)
        error.value = '本机未同步的填写已恢复，服务器草稿也有变化。请核对后决定是否保存本机填写。'
      else scheduleSave()
    } else {
      answers.value = { ...value.draft }
      dirty.value = false
      conflict.value = false
      forget(value.id)
    }
  }
  function schedule(wait = 1000) {
    clearTimeout(pollTimer)
    if (operation.value?.status === 'running' || reading.value)
      pollTimer = setTimeout(() => void poll(), wait)
  }
  async function refresh(preserve = true) {
    const version = generation,
      ticket = ++stateRead
    const result = await request((signal) => api.state(session, owner, signal))
    if (version !== generation || ticket !== stateRead) return
    if (
      result.attempt?.id === attempt.value?.id &&
      result.attempt &&
      attempt.value &&
      result.attempt.revision < attempt.value.revision
    )
      result.attempt = attempt.value
    data.value = result
    if (!historyView.value && result.attempt) {
      accept(result.attempt, preserve)
      if (['generating', 'grading'].includes(result.attempt.status)) {
        operation.value = {
          id: result.attempt.operation_id,
          attempt_id: result.attempt.id,
          kind: result.attempt.status === 'grading' ? 'grade' : 'generate',
          status: 'running',
          message: '正在恢复原自测任务…',
          calls: 0,
          used_tokens: 0,
        }
        schedule(150)
      } else if (operation.value?.id === result.attempt.operation_id) {
        operation.value = null
        reading.value = false
        syncFailed.value = false
        failures = 0
        clearTimeout(pollTimer)
      }
    }
  }
  async function bind(user: string, sid: string) {
    reset()
    owner = user
    session = sid
    if (!owner || !session) return
    const version = generation
    loading.value = true
    try {
      await refresh(false)
    } catch (problem) {
      if (version === generation) error.value = (problem as Error).message
    } finally {
      if (version === generation) loading.value = false
    }
  }
  async function poll() {
    const op = operation.value,
      version = generation
    if (!op) return
    try {
      if (!reading.value) {
        try {
          const result = await request((signal) => api.operation(op.id, owner, signal))
          if (version !== generation) return
          operation.value = result
          if (result.status === 'running') {
            failures = 0
            schedule()
            return
          }
        } catch (problem) {
          if (problem instanceof SelfCheckError && problem.status === 404) {
            // A response can be lost when the server reuses an existing attempt.
            await refresh()
            if (version !== generation) return
            if (
              data.value?.attempt &&
              !['generating', 'grading'].includes(data.value.attempt.status) &&
              (!pendingFresh || data.value.attempt.id !== pendingFresh) &&
              (op.kind !== 'grade' || !!data.value.attempt.submitted)
            ) {
              accept(data.value.attempt, true)
              operation.value = null
              syncFailed.value = false
              pendingSend = null
              resendAllowed.value = false
              error.value = ''
              return
            }
            if (
              data.value?.attempt &&
              ['generating', 'grading'].includes(data.value.attempt.status) &&
              data.value.attempt.id !== pendingFresh
            ) {
              pendingSend = null
              return
            }
            operation.value = op
            resendAllowed.value = !!pendingSend
          }
          throw problem
        }
      }
      reading.value = true
      const current = operation.value!
      const result = await request((signal) => api.attempt(current.attempt_id, owner, signal))
      if (version !== generation) return
      accept(result)
      reading.value = false
      syncFailed.value = false
      failures = 0
      error.value = ''
      pendingFresh = null
      pendingSend = null
      resendAllowed.value = false
      await refresh().catch(() => {})
    } catch {
      if (version !== generation) return
      failures++
      if (failures > 3) {
        reading.value = false
        syncFailed.value = true
        error.value = '暂时无法读取原任务。试卷与作答保留，请重新读取；无需再次运行模型。'
        return
      }
      error.value = '连接暂时中断，正在重新读取原自测任务…'
      schedule(300 * failures)
    }
  }
  async function reconnect() {
    syncFailed.value = false
    failures = 0
    error.value = ''
    if (operation.value) await poll()
    else
      try {
        await refresh()
      } catch (problem) {
        error.value = (problem as Error).message
      }
  }
  function edit(id: string, value: string) {
    if (attempt.value?.status !== 'ready' || historyView.value || !attempt.value.binding_valid)
      return
    answers.value = { ...answers.value, [id]: value }
    dirty.value = true
    remember()
    scheduleSave()
  }
  function scheduleSave() {
    clearTimeout(draftTimer)
    if (!conflict.value) draftTimer = setTimeout(() => void flush(), 600)
  }
  async function flush(): Promise<boolean> {
    clearTimeout(draftTimer)
    if (flight) return flight
    if (!dirty.value) return true
    if (conflict.value || attempt.value?.status !== 'ready') return false
    const version = generation,
      aid = attempt.value.id
    const promise = (async () => {
      saving.value = true
      try {
        while (dirty.value && attempt.value?.id === aid) {
          const captured = { ...answers.value },
            revision = attempt.value.revision
          let saved: SelfCheckAttempt
          try {
            saved = await request((signal) => api.draft(aid, revision, captured, owner, signal))
          } catch {
            // Confirm an acknowledged write using reads before any new write.
            saved = await request((signal) => api.attempt(aid, owner, signal))
            if (version !== generation) return false
            if (!same(saved.draft, captured)) {
              attempt.value = saved
              conflict.value = true
              error.value = '服务器草稿已变化，本机填写已保留。请核对后再保存。'
              return false
            }
          }
          if (version !== generation) return false
          if (attempt.value?.id === aid && saved.revision < attempt.value.revision)
            saved = attempt.value
          attempt.value = saved
          if (saved.status !== 'ready') {
            accept(saved)
            if (['generating', 'grading'].includes(saved.status)) {
              operation.value = {
                id: saved.operation_id,
                attempt_id: saved.id,
                kind: 'grade',
                status: 'running',
                message: '正在恢复其他页面已提交的任务…',
                calls: 0,
                used_tokens: 0,
              }
              schedule(150)
            } else {
              operation.value = null
              reading.value = false
              clearTimeout(pollTimer)
            }
            return false
          }
          if (same(captured, answers.value)) {
            dirty.value = false
            forget(aid)
          } else remember()
        }
        error.value = ''
        return true
      } catch (problem) {
        if (version === generation)
          error.value = '草稿尚未同步，本机填写已保留。' + (problem as Error).message
        return false
      } finally {
        if (version === generation) saving.value = false
      }
    })()
    flight = promise
    try {
      return await promise
    } finally {
      if (flight === promise) flight = null
    }
  }
  async function saveLocal() {
    conflict.value = false
    await flush()
  }
  async function dispatch(
    kind: 'generate' | 'grade' | 'retry',
    provider: ProviderConfig,
    fresh = false,
  ) {
    if (running.value || loading.value || syncFailed.value) return
    submitting.value = true
    error.value = ''
    const version = generation,
      id = identifier()
    if (kind === 'grade' && !(await flush())) {
      submitting.value = false
      return
    }
    const current = attempt.value
    if (version !== generation) return
    operation.value = {
      id,
      attempt_id: current?.id ?? '',
      kind:
        kind === 'generate'
          ? 'generate'
          : current?.submitted
            ? 'grade'
            : kind === 'grade'
              ? 'grade'
              : 'generate',
      status: 'running',
      message: kind === 'generate' ? '正在检查学习范围并准备题目…' : '正在提交原卷的简答评价…',
      calls: 0,
      used_tokens: 0,
    }
    pendingFresh = kind === 'generate' && fresh ? (current?.id ?? '__none__') : null
    historyView.value = false
    const captured = { ...answers.value }
    pendingSend = (signal) =>
      kind === 'generate'
        ? api.start(session, id, fresh, provider, owner, signal)
        : kind === 'grade'
          ? api.submit(current!.id, id, current!.revision, captured, provider, owner, signal)
          : api.retry(current!.id, id, provider, owner, signal)
    try {
      const result = await request(pendingSend)
      if (version !== generation) return
      pendingFresh = null
      pendingSend = null
      resendAllowed.value = false
      operation.value = result
      failures = 0
      syncFailed.value = false
      schedule(150)
      if (result.status !== 'running') {
        reading.value = true
        await poll()
      }
    } catch (problem) {
      if (version !== generation) return
      if (
        !(problem instanceof SelfCheckError) ||
        problem.status >= 500 ||
        [408, 429].includes(problem.status)
      ) {
        error.value = '提交结果待确认，正在查询原任务…'
        schedule(250)
      } else {
        operation.value = null
        pendingSend = null
        error.value = problem.message
      }
    } finally {
      if (version === generation) submitting.value = false
    }
  }
  async function resend() {
    if (!syncFailed.value || !resendAllowed.value || !pendingSend || submitting.value) return
    const version = generation
    submitting.value = true
    error.value = ''
    try {
      const result = await request(pendingSend)
      if (version !== generation) return
      operation.value = result
      pendingSend = null
      resendAllowed.value = false
      syncFailed.value = false
      failures = 0
      schedule(150)
      if (result.status !== 'running') {
        reading.value = true
        await poll()
      }
    } catch (problem) {
      if (version === generation)
        error.value = '原请求仍未确认，请重新读取后再处理。' + (problem as Error).message
    } finally {
      if (version === generation) submitting.value = false
    }
  }
  async function cancel() {
    const current = operation.value,
      version = generation
    if (!current) return
    try {
      const result = await request((signal) => api.cancel(current.id, owner, signal))
      if (version !== generation) return
      operation.value = result
      reading.value = true
      await poll()
    } catch (problem) {
      if (version === generation) error.value = (problem as Error).message
    }
  }
  async function view(id: string) {
    if (dirty.value && !(await flush())) return
    const version = generation
    loading.value = true
    try {
      const result = await request((signal) => api.attempt(id, owner, signal))
      if (version !== generation) return
      historyView.value = id !== data.value?.attempt?.id
      accept(result)
    } catch (problem) {
      if (version === generation) error.value = (problem as Error).message
    } finally {
      if (version === generation) loading.value = false
    }
  }
  return {
    data,
    attempt,
    operation,
    answers,
    error,
    loading,
    submitting,
    saving,
    dirty,
    conflict,
    syncFailed,
    reading,
    running,
    historyView,
    resendAllowed,
    bind,
    reset,
    refresh,
    reconnect,
    resend,
    edit,
    flush,
    saveLocal,
    dispatch,
    cancel,
    view,
  }
}
