import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import type { useLab } from '@/composables/useLab'
import { useLearning } from '@/composables/useLearning'
import {
  emptyExploration,
  loadExploration,
  saveExploration,
  type ExplorationChange,
} from '@/services/learning-exploration'

type LabFacade = ReturnType<typeof useLab>
type Lab = Pick<
  LabFacade,
  'ensureSession' | 'modelReady' | 'config' | 'refreshSessions' | 'forkTurn' | 'draft' | 'setDraft'
> & {
  state: Pick<
    LabFacade['state'],
    'user' | 'sessionId' | 'authExpired' | 'busy' | 'turns' | 'status'
  >
}
export async function recordLearningSource(lab: Lab, source: string): Promise<string> {
  const owner = lab.state.user
  const session = await lab.ensureSession()
  if (!session) throw new Error('请先登录。')
  if (lab.state.user !== owner || lab.state.sessionId !== session)
    throw new Error('已切换会话，请重新开始学习。')
  // The reference-route click is already an explicit human choice. Ordinary
  // Harness suggestions still use the separate proposal/confirmation flow.
  const result = await saveExploration(session, { source, confirm: source })
  if (result.binding?.method_id !== source || result.binding.card_missing)
    throw new Error('方法绑定尚未确认，请重试进入当前会话。')
  return session
}
export function useLearningExploration(lab: Lab) {
  const state = ref(emptyExploration()),
    loading = ref(false),
    saving = ref(false),
    error = ref(''),
    forking = ref(false)
  let generation = 0,
    timer: ReturnType<typeof setTimeout> | null = null,
    abort: AbortController | null = null
  async function refresh(ticket = generation) {
    const session = lab.state.sessionId
    if (!session || !lab.state.user || lab.state.authExpired) return
    const controller = new AbortController()
    abort = controller
    const timeout = setTimeout(() => controller.abort(), 15000)
    try {
      const value = await loadExploration(session, controller.signal)
      if (ticket === generation) {
        const changed = state.value.binding?.card_id !== value.binding?.card_id
        state.value = value
        error.value = ''
        if (changed && value.binding) void useLearning().refresh()
      }
    } catch (problem) {
      if (ticket === generation && (problem as Error).name !== 'AbortError')
        error.value = (problem as Error).message
    } finally {
      clearTimeout(timeout)
      if (ticket === generation && !lab.state.authExpired) {
        loading.value = false
        abort = null
        timer = setTimeout(() => void refresh(ticket), 2500)
      }
    }
  }
  watch(
    () => [lab.state.user, lab.state.sessionId, lab.state.authExpired] as const,
    () => {
      generation++
      abort?.abort()
      if (timer) clearTimeout(timer)
      if (lab.state.authExpired) {
        loading.value = false
        error.value = ''
        return
      }
      state.value = emptyExploration()
      error.value = ''
      loading.value = !!lab.state.sessionId
      if (lab.state.user && lab.state.sessionId) void refresh()
    },
    { immediate: true },
  )
  async function change(change: ExplorationChange) {
    if (saving.value || loading.value) return
    const owner = lab.state.user,
      session = await lab.ensureSession()
    await nextTick()
    if (!session || owner !== lab.state.user || session !== lab.state.sessionId) return
    const ticket = ++generation
    abort?.abort()
    if (timer) clearTimeout(timer)
    loading.value = false
    saving.value = true
    error.value = ''
    try {
      const value = await saveExploration(session, change)
      if (ticket === generation) state.value = value
    } catch (problem) {
      if (ticket === generation) error.value = (problem as Error).message
    } finally {
      saving.value = false
      if (ticket === generation) timer = setTimeout(() => void refresh(ticket), 2500)
    }
  }
  async function confirm() {
    const proposal = state.value.proposal_id
    if (proposal) {
      await change({
        confirm: proposal,
        ...(lab.modelReady.value ? { provider: lab.config() } : {}),
      })
      if (state.value.binding) await Promise.all([lab.refreshSessions(), useLearning().refresh()])
    }
  }
  async function settle(limit = 6000) {
    const started = Date.now()
    while ((loading.value || saving.value) && Date.now() - started < limit)
      await new Promise((resolve) => setTimeout(resolve, 60))
  }
  async function newChat(label: string) {
    const method = state.value.drift_id
    if (!method || forking.value || lab.state.busy || lab.state.authExpired) return
    const index = lab.state.turns
      .map((turn) => turn.kind !== 'experiment' && turn.status === 'complete')
      .lastIndexOf(true)
    if (index < 0) {
      error.value = '请等当前回复完整结束后，再继承讨论开启新会话。'
      return
    }
    const previousDraft = lab.draft.value
    forking.value = true
    error.value = ''
    try {
      if (!(await lab.forkTurn(index))) {
        error.value = lab.state.status || '暂时无法继承上下文，请稍后重试。'
        return
      }
      await nextTick()
      // The branch starts its own exploration load; submitting while it is in flight
      // would be dropped by the loading guard, so wait (and retry) before proposing.
      let proposed = false
      for (let attempt = 0; attempt < 3 && !proposed; attempt++) {
        await settle()
        await change({ source: method })
        proposed = state.value.proposal_id === method || state.value.binding?.method_id === method
        if (!proposed) await new Promise((resolve) => setTimeout(resolve, 180))
      }
      if (!proposed) error.value = '已继承原讨论，但新方法的学习建议还没保存，请稍后重试。'
      else if (!previousDraft.trim())
        lab.setDraft(`我想继续学习「${label}」，请结合上面的讨论说明适用前提和下一步学习安排。`)
    } catch (problem) {
      error.value = (problem as Error).message
    } finally {
      forking.value = false
    }
  }
  onBeforeUnmount(() => {
    generation++
    abort?.abort()
    if (timer) clearTimeout(timer)
  })
  return {
    state,
    loading,
    saving,
    error,
    forking,
    confirm,
    newChat,
    dismissProposal: () => change({ dismiss_proposal: true }),
    dismissDrift: () => change({ dismiss_drift: true }),
  }
}
