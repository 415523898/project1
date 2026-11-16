import { computed, onScopeDispose, reactive, ref, shallowReadonly, watch } from 'vue'
import type { ChatAttachment } from '@/types'
import { defineStore, storeToRefs } from 'pinia'

import { ApiBase } from '@/utils/api-base'
import { appendActivityText } from '@/utils/turn-activity'
import {
  askAgent,
  bootstrapContext,
  connectionError,
  snapshotLabel,
  type ProviderConfig,
  type SnapshotContext,
} from '@/services/agent'
import {
  activeSessionId,
  rememberActiveSession,
  sessionTitle,
  isUntitledSession,
  needsSessionTitle,
  useConversationApi,
  serializableTurns,
} from '@/services/conversations'
import * as authApi from '@/services/auth'
import { createConversationRuns, type ConversationRun } from '@/composables/lab/conversation-runs'
import { createExperimentState } from '@/composables/lab/experiments'
import { turnsFromEvents } from '@/utils/conversation-events'
import { initialLabState } from '@/composables/lab/state'
import { createProviderSettings } from '@/composables/lab/provider-settings'
import { selectDataset } from '@/services/files'
import { testProviderConnection } from '@/services/providers'
import { useConsent } from '@/composables/useConsent'
import { useLearning } from '@/composables/useLearning'
import { useStudy } from '@/composables/useStudy'
import type {
  ChatTurn,
  DatasetChoice,
  ExperimentResult,
  SessionRecord,
  SessionSummary,
  TurnImage,
  UploadedFile,
} from '@/types'

export const useLabStore = defineStore('lab', () => {
  let disposed = false
  const state = reactive(initialLabState())
  const expired = (event: Event) => {
    if (
      (event as CustomEvent<{ backend: string }>).detail?.backend !== ApiBase.get() ||
      !state.user
    )
      return
    state.authExpired = true
    state.connected = false
    state.status = '登录已失效，请重新登录后继续；已完成的实验结果仍保留。'
    state.statusTone = 'error'
  }
  window.addEventListener('forest-auth-expired', expired)
  onScopeDispose(() => window.removeEventListener('forest-auth-expired', expired))

  const panelOpen = ref(false)
  const lightbox = ref<{ url: string; name: string } | null>(null)
  const settingsOpen = ref(false)
  const draft = ref('')
  const conversationDrafts = new Map<string, string>()

  function switchConversationDraft(nextId: string | null): void {
    if (nextId && nextId === state.sessionId) return
    const key = (id: string) => `${state.user}\u0000${id}`
    if (state.sessionId) conversationDrafts.set(key(state.sessionId), draft.value)
    draft.value = nextId ? (conversationDrafts.get(key(nextId)) ?? '') : ''
  }
  const files = ref<UploadedFile[]>([])
  const activeDataset = ref<DatasetChoice | null>(null)
  const sessionDatasets = new Map<string, DatasetChoice | null>()
  const experiments = createExperimentState(state, setStatus, captureAccountScope)
  const {
    blocks,
    selectedKey,
    sidebarSaving,
    adoptSidebar,
    acceptExperimentResult,
    switchExperimentVersion,
    revealExperimentVersion,
    syncSavedExplanations,
    syncResultVisibility,
    indexBlocks,
    removeBlock,
    selectBlock,
    sidebarScope,
  } = experiments
  const pendingTitles = new Set<string>()
  let sessionListSequence = 0
  const titleSources = new Map<string, SessionSummary['title_source']>()
  const api = useConversationApi()
  let pendingSession: {
    owner: string
    version: number
    promise: Promise<string>
    current: () => boolean
  } | null = null
  let selectionVersion = 0
  let pendingSelection: {
    id: string
    current: () => boolean
    controller: AbortController
    promise: Promise<void>
  } | null = null
  function cancelSelection(): void {
    pendingSelection?.controller.abort()
    pendingSelection = null
  }
  watch(() => [state.user, state.authExpired, state.backend], cancelSelection, { flush: 'sync' })
  onScopeDispose(() => {
    disposed = true
    selectionVersion++
    cancelSelection()
  })
  const runtime = createConversationRuns(state, { indexBlocks, acceptExperimentResult, setStatus })
  const {
    activeTool,
    controller,
    runningSessionIds,
    clearRecovery,
    updateRunning,
    showRun,
    hooks,
    stop,
    getRun,
  } = runtime
  function setBodyView(view: 'chat' | 'results'): void {
    document.body.dataset.view = view
  }

  function viewName(): 'chat' | 'results' {
    return panelOpen.value ? 'results' : 'chat'
  }

  function openSettings(): void {
    settingsOpen.value = true
  }

  function closeSettings(): void {
    settingsOpen.value = false
  }

  function setStatus(text: string, tone: 'muted' | 'busy' | 'error' = 'muted'): void {
    state.status = text
    state.statusTone = tone
  }

  function setDraft(text: string): void {
    draft.value = text
  }

  function setFiles(list: UploadedFile[]): void {
    const seen = new Set<string>()
    files.value = list.filter((file) => {
      if (!file?.id || seen.has(file.id)) return false
      seen.add(file.id)
      return true
    })
  }

  function addFile(file: UploadedFile): void {
    setFiles([...files.value.filter((item) => item.id !== file.id), file])
  }

  function removeFile(id: string): void {
    files.value = files.value.filter((file) => file.id !== id)
  }

  function clearFiles(): void {
    files.value = []
  }

  async function chooseDataset(dataset: string | null): Promise<void> {
    if (disposed) return
    if (state.busy) throw new Error('请等待当前回答完成后再切换数据。')
    const version = selectionVersion
    const account = captureAccountScope()
    const session = await ensureSession()
    if (!session) throw new Error('请先登录后选择数据。')
    if (version !== selectionVersion || !account.current()) return
    const selected = await selectDataset(session, dataset)
    if (!account.current()) return
    sessionDatasets.set(session, selected)
    if (state.sessionId !== session || version !== selectionVersion) return
    activeDataset.value = selected
    // Files belong to the library; detaching only changes this conversation.
    files.value = selected?.kind === 'upload' ? [selected as UploadedFile] : []
    state.experimentContext = null
  }

  const providers = createProviderSettings(state, { setStatus, openSettings, closeSettings })
  const {
    saveSettings,
    providerLoading,
    providerLoadError,
    providerProfiles,
    addedProviderIds,
    clearCredentials,
    invalidateProviderLoad,
    refreshProviders,
    saveServerProvider,
    deleteServerProvider,
    hasSavedCredential,
    keyAvailable,
    selectProvider,
    selectModel,
    setReasoningEffort,
    providerReady,
    providerProfile,
    applyProviderProfiles,
    removeProvider,
    configurationIssue,
    modelAccess,
    modelReady,
    resolveModelAccess,
    config,
    setDetail,
    setAllowTools,
    setApiKey,
    resetProvider,
  } = providers

  function captureAccountScope() {
    const owner = state.user,
      backend = ApiBase.get(),
      epoch = providers.credentialEpoch
    return {
      owner,
      canCancel: () => state.user === owner && ApiBase.get() === backend,
      current: () =>
        !disposed &&
        state.user === owner &&
        ApiBase.get() === backend &&
        providers.credentialEpoch === epoch,
    }
  }

  function context(): SnapshotContext {
    syncResultVisibility()
    if (!state.experimentContext) state.experimentContext = bootstrapContext()
    return {
      ...state.experimentContext,
      sidebar_view: experiments.contextView(),
      ...(activeDataset.value
        ? {
            selected_dataset: activeDataset.value,
            draft: { ...state.experimentContext.draft, dataset: activeDataset.value.dataset },
          }
        : {}),
      files: files.value.map((file) => ({
        id: file.id,
        name: file.name,
        dataset: file.dataset,
        rows: file.rows,
        columns: file.columns,
        column_names: file.column_names,
        dtypes: file.dtypes,
        target: file.target,
        task: file.task,
        head: file.head,
      })),
    }
  }

  function provider(): ProviderConfig {
    const selected = config()
    const snapshot = context()
    return {
      ...selected,
      allow_tools:
        selected.allow_tools && snapshot.capabilities.independent_fast_training_tool !== false,
    }
  }

  async function ask(
    question: string,
    images: TurnImage[] = [],
    onAccepted?: () => void,
    revision?: { action: 'regenerate' | 'edit'; event_id: string },
    attachments: ChatAttachment[] = [],
  ): Promise<boolean> {
    if (disposed || state.busy) return false
    const text = question.trim()
    if (!text) return false
    const account = captureAccountScope(),
      version = selectionVersion
    let selected: ProviderConfig
    try {
      selected = config()
      await ensureSession()
      if (!account.current() || version !== selectionVersion) return false
      const id = state.sessionId,
        owner = state.user
      await experiments.flush(id, owner)
      if (id) await syncSavedExplanations(id, owner)
      if (state.sessionId !== id || !account.current() || version !== selectionVersion) return false
    } catch (error) {
      if (!account.current() || version !== selectionVersion) return false
      setStatus(connectionError(error), 'error')
      return false
    }
    saveSettings()
    const id = state.sessionId!
    if (getRun(id)?.busy) return false
    const abort = new AbortController()
    const snapshot = context()
    selected.allow_tools =
      selected.allow_tools && snapshot.capabilities.independent_fast_training_tool !== false
    const turn = reactive<ChatTurn>({
      kind: 'chat',
      question: text,
      answer: '',
      tools: [],
      context: snapshot as unknown as Record<string, unknown>,
      images: [...images],
      attachments: attachments.map((file) => ({ ...file })),
      model: selected.model,
      status: 'pending',
      detail_level: state.settings.detail,
      created_at: new Date().toISOString(),
    })
    const revisionIndex = revision
      ? state.turns.map((item) => item.kind !== 'experiment').lastIndexOf(true)
      : -1
    const previous = revision ? state.turns[revisionIndex] : undefined
    if (revision) state.turns.splice(revisionIndex, 1, turn)
    else state.turns.push(turn)
    const run: ConversationRun = {
      owner: state.user,
      current: account.current,
      canCancel: account.canCancel,
      id,
      title: state.sessionTitle,
      turns: state.turns,
      controller: abort,
      token: null,
      tool: null,
      busy: true,
      stopped: false,
      status: `依据：${snapshotLabel(snapshot)}。`,
      tone: 'busy',
    }
    runtime.registerRun(run)
    let accepted = false
    const accept = () => {
      if (accepted) return
      accepted = true
      if (account.current() && state.sessionId === id) onAccepted?.()
    }
    const result = await askAgent({
      config: selected,
      question: text,
      context: snapshot,
      detail: state.settings.detail,
      turn,
      controller: abort,
      hooks: {
        ...hooks(run, account.current),
        onAccepted: () => {
          if (!revision && !attachments.length) accept()
        },
        onUserMessage: accept,
      },
      session: id,
      images: turn.images ?? [],
      attachments: turn.attachments,
      revision,
    })
    if (getRun(id) !== run || !account.current()) return true
    if (result.session) run.token = result.session
    run.busy = false
    run.tool = null
    run.tone = 'muted'
    if (result.ok) {
      state.connected = true
      run.status = `回答完成 · 依据 ${snapshotLabel(snapshot)}。`
    } else if (result.stopped) {
      run.status = '已停止回答。'
    } else {
      state.connected = false
      run.status = result.error ?? '回答失败。'
      run.tone = 'error'
    }
    updateRunning()
    showRun(run)
    if (revision && !turn.event_id && previous) {
      // A rejected HTTP request must not replace an existing answer locally.
      run.turns.splice(run.turns.indexOf(turn), 1, previous)
      indexBlocks()
    }
    try {
      await api.save(
        id,
        run.turns,
        isUntitledSession(run.title) ? sessionTitle(run.turns) : run.title,
      )
      if (getRun(id) !== run || !account.current()) return true
      await refreshSessions()
      if (result.ok) await nameSession(id, selected)
      // Tool-run experiments are registered from the finished events; pull the
      // refreshed sidebar so a second experiment appears without reopening.
      void experiments.refreshSidebar(id, account.owner)
    } catch (error) {
      run.status = connectionError(error, selected.api_key)
      run.tone = 'error'
      showRun(run)
    }
    return true
  }

  async function messageTarget(index: number, action: 'revision' | 'fork'): Promise<string> {
    const account = captureAccountScope()
    const owner = account.owner,
      id = state.sessionId,
      turn = state.turns[index]
    if (!owner || !id || !turn || state.authExpired) throw new Error('请先登录并打开会话。')
    const record = await api.load(id)
    if (!account.current() || id !== state.sessionId || state.turns[index] !== turn)
      throw new Error('会话已切换，请在当前消息上重新操作。')
    if (!record?.message_actions?.[action])
      throw new Error('当前后端尚未加载消息操作功能，请使用本轮新版预览。')
    const messages = record.events?.filter((event) => event.kind === 'user/message') ?? []
    const chatIndex = state.turns
      .slice(0, index)
      .filter((item) => item.kind !== 'experiment').length
    const event = turn.event_id
      ? messages.find((event) => (event.id || 'seq:' + event.seq) === turn.event_id)
      : messages[chatIndex]
    if (!event || event.text !== turn.question)
      throw new Error('会话内容已更新，请重新打开后操作。')
    return String(event.id || 'seq:' + event.seq)
  }

  async function reviseLatest(
    action: 'regenerate' | 'edit',
    text?: string,
    onAccepted?: () => void,
  ): Promise<boolean> {
    if (state.busy || state.messageActionBusy) return false
    const index = state.turns.map((turn) => turn.kind !== 'experiment').lastIndexOf(true),
      original = state.turns[index]
    if (!original || (action === 'regenerate' && original.status !== 'complete')) return false
    state.messageActionBusy = true
    try {
      const event_id = await messageTarget(index, 'revision')
      return await ask(
        action === 'edit' ? (text ?? '') : original.question,
        original.images ?? (original.image ? [original.image] : []),
        onAccepted,
        { action, event_id },
        original.attachments ?? [],
      )
    } catch (error) {
      setStatus(connectionError(error), 'error')
      return false
    } finally {
      state.messageActionBusy = false
    }
  }

  async function forkTurn(index: number): Promise<boolean> {
    if (state.messageActionBusy || state.authExpired) return false
    state.messageActionBusy = true
    try {
      const event_id = await messageTarget(index, 'fork')
      const account = captureAccountScope()
      const id = state.sessionId!
      const record = await api.fork(id, event_id)
      if (!account.current() || id !== state.sessionId) return false
      await refreshSessions()
      await openSession(record.id)
      setStatus('已分支到新聊天，可以从这里继续。')
      return true
    } catch (error) {
      setStatus(connectionError(error), 'error')
      return false
    } finally {
      state.messageActionBusy = false
    }
  }

  async function testConnection(override?: ProviderConfig): Promise<void> {
    if (disposed) return
    let selected: ProviderConfig
    try {
      if (override) {
        const consent = useConsent()
        if (!consent.agreed.value) {
          closeSettings()
          consent.revoke()
          throw new Error('请先阅读数据使用说明，再允许连接模型服务商。')
        }
        if (
          !override.base_url.trim() ||
          !override.model.trim() ||
          (!override.api_key.trim() && !override.credential_id)
        )
          throw new Error('请填写上游地址、模型和 API Key。')
        selected = override
      } else selected = config()
    } catch (error) {
      setStatus(connectionError(error), 'error')
      return
    }
    if (!override) saveSettings()
    runtime.cancelConnection()
    const abort = new AbortController()
    const owner = state.user,
      backend = ApiBase.get(),
      version = selectionVersion
    const current = () =>
      controller.value === abort &&
      owner === state.user &&
      backend === ApiBase.get() &&
      version === selectionVersion
    controller.value = abort
    state.busy = true
    setStatus('连接测试中…', 'busy')
    const timeout = setTimeout(() => abort.abort(), 95000)
    const clearProbeTimeout = () => clearTimeout(timeout)
    abort.signal.addEventListener('abort', clearProbeTimeout, { once: true })
    try {
      const result = await testProviderConnection(selected, abort.signal)
      if (!current()) return
      if (!override) state.connected = true
      const seconds = ((result.elapsed_ms ?? 0) / 1000).toFixed(1)
      setStatus(`连接成功 · ${result.model || selected.model} · ${seconds} 秒`)
    } catch (error) {
      if (!current()) return
      state.connected = false
      const aborted = (error as Error).name === 'AbortError'
      setStatus(
        aborted ? '连接测试已停止。' : connectionError(error, selected.api_key),
        aborted ? 'muted' : 'error',
      )
    } finally {
      clearTimeout(timeout)
      abort.signal.removeEventListener('abort', clearProbeTimeout)
      const visible = current()
      if (controller.value === abort) controller.value = null
      if (visible) state.busy = false
    }
  }

  async function refreshSessions(): Promise<void> {
    if (disposed) return
    const account = captureAccountScope(),
      owner = account.owner,
      ticket = ++sessionListSequence
    const [sessions, workspaces] = await Promise.all([api.list(), api.workspaces()])
    if (!account.current() || ticket !== sessionListSequence) return
    state.sessions = sessions
    for (const session of sessions) {
      if (session.title_source)
        titleSources.set(sidebarScope(session.id, owner), session.title_source)
    }
    state.workspaces = workspaces
  }

  async function persist(): Promise<void> {
    if (disposed) return
    const account = captureAccountScope(),
      version = selectionVersion,
      id = state.sessionId
    try {
      const record = await api.save(
        state.sessionId,
        state.turns,
        isUntitledSession(state.sessionTitle) ? sessionTitle(state.turns) : state.sessionTitle,
      )
      if (!record || !account.current() || version !== selectionVersion || state.sessionId !== id)
        return
      state.sessionId = record.id
      rememberActiveSession(record.id)
      await refreshSessions()
    } catch (error) {
      if (!account.current() || version !== selectionVersion || state.sessionId !== id) return
      setStatus(connectionError(error), 'error')
    }
  }

  async function nameSession(id = state.sessionId, selected?: ProviderConfig): Promise<void> {
    if (disposed) return
    if (!id || configurationIssue.value || !useConsent().agreed.value) return
    const account = captureAccountScope(),
      owner = account.owner
    const run = getRun(id)
    const current = state.sessionId === id
    if (!run && !current) return
    const title = run?.title ?? state.sessionTitle
    const turns = run?.turns ?? state.turns
    const scope = sidebarScope(id, owner)
    if (
      !needsSessionTitle(title, turns, titleSources.get(scope)) ||
      run?.busy ||
      (!run && state.busy) ||
      pendingTitles.has(scope) ||
      !turns.some(
        (turn) => turn.kind === 'chat' && turn.status === 'complete' && turn.answer.trim(),
      )
    )
      return
    pendingTitles.add(scope)
    try {
      const generated = await api.name(id, selected ?? config())
      if (!generated.title || !account.current() || titleSources.get(scope) === 'manual') return
      if (generated.source !== 'ai' && generated.source !== 'manual') return
      titleSources.set(scope, generated.source)
      // The next reply may already be running; the title still belongs to this conversation.
      const latest = getRun(id)
      if (latest?.owner === owner) latest.title = generated.title
      if (state.sessionId === id) state.sessionTitle = generated.title
      await refreshSessions()
    } catch {
      // The saved question remains a fallback; a later completed answer can retry.
    } finally {
      pendingTitles.delete(scope)
    }
  }

  async function renameSession(id: string, title: string): Promise<boolean> {
    if (disposed) return false
    const account = captureAccountScope()
    const clean = title.trim().slice(0, 60)
    if (!clean) return false
    try {
      await api.rename(id, clean)
    } catch (error) {
      if (account.current()) setStatus(connectionError(error), 'error')
      return false
    }
    if (!account.current()) return false
    if (state.sessionId === id) state.sessionTitle = clean
    titleSources.set(sidebarScope(id), 'manual')
    const run = getRun(id)
    if (run) run.title = clean
    await refreshSessions()
    return true
  }

  async function ensureSession(): Promise<string | null> {
    if (disposed) throw new Error('工作区已关闭，请重新打开后操作。')
    if (state.authExpired) throw new Error('登录已失效，请重新登录后继续。')
    if (state.sessionId) return state.sessionId
    if (!state.user) throw new Error('请先登录。')
    if (
      !pendingSession ||
      pendingSession.owner !== state.user ||
      pendingSession.version !== selectionVersion ||
      !pendingSession.current()
    ) {
      const account = captureAccountScope(),
        owner = account.owner
      const version = selectionVersion
      const promise = (async () => {
        const record = await api.createEmpty()
        if (!record?.id) throw new Error('创建会话失败，请重试。')
        if (!account.current()) throw new Error('账号已切换，请重新开始实验。')
        if (state.authExpired) throw new Error('登录已失效，请重新登录后继续。')
        if (version !== selectionVersion) throw new Error('已切换会话，请在当前会话重试。')
        state.sessionId = record.id
        rememberActiveSession(record.id)
        return record.id
      })().finally(() => {
        if (pendingSession?.promise === promise) pendingSession = null
      })
      pendingSession = { owner, version, promise, current: account.current }
    }
    return pendingSession.promise
  }

  function showRecord(record: SessionRecord): void {
    adoptSidebar(record.experiment_sidebar)
    const running = record.run?.running === true
    const restored = turnsFromEvents(record.events ?? [], running)
    const pending = restored.at(-1)
    if (running && pending?.status === 'pending' && typeof record.run?.answer === 'string') {
      const whole = record.run.answer
      if (whole.startsWith(pending.answer))
        appendActivityText(pending, whole.slice(pending.answer.length), record.run.step)
    }
    if (running && pending?.status === 'pending') {
      const phase = record.run?.phase
      pending.model_phase = [
        'connecting',
        'connected',
        'thinking',
        'generating',
        'tool_call',
      ].includes(phase ?? '')
        ? (phase as ChatTurn['model_phase'])
        : 'connected'
    }
    // Keep the visible turn objects stable while synchronising incremental text.
    // Replacing the array on every update resets the reader's scroll-follow choice.
    if (
      restored.length === state.turns.length &&
      restored.every(
        (turn, index) =>
          turn.question === state.turns[index]?.question &&
          turn.created_at === state.turns[index]?.created_at,
      )
    ) {
      restored.forEach((turn, index) => Object.assign(state.turns[index]!, turn))
    } else state.turns = restored
    state.busy = running
    state.activeSession = running ? (record.run?.token ?? null) : null
    const last = state.turns.at(-1)
    if (running && last) {
      if (record.run?.model) last.model = record.run.model
      if (record.run?.step !== undefined) last.steps = record.run.step
    }
    activeTool.value = running
      ? (last?.tools?.find((tool) => tool.status === 'running') ?? null)
      : null
    runtime.recoveredSession = running ? state.sessionId : null
    updateRunning()
    indexBlocks()
    if (running)
      setStatus(
        record.run?.cancelled
          ? '正在停止这轮回答…'
          : record.run?.phase === 'tool'
            ? 'agent 正在后端运行实验…'
            : '模型正在分析并组织回答…',
        'busy',
      )
    else if (last?.status === 'error') setStatus(last.error ?? '这轮回答已中断。', 'error')
    else if (last?.answer.trim()) {
      state.connected = true
      setStatus('回答已同步。')
    } else setStatus('')
  }

  function recoverSession(id: string, owner: string, version: number): void {
    const account = captureAccountScope()
    runtime.scheduleRecovery(async () => {
      if (
        state.sessionId !== id ||
        !account.current() ||
        state.user !== owner ||
        version !== selectionVersion
      )
        return
      try {
        const record = await api.load(id)
        if (
          state.sessionId !== id ||
          !account.current() ||
          state.user !== owner ||
          version !== selectionVersion
        )
          return
        const local = getRun(id)
        if (local?.busy) {
          clearRecovery()
          state.turns = local.turns
          showRun(local)
          return
        }
        if (!record) {
          clearRecovery()
          state.busy = false
          return
        }
        showRecord(record)
        if (!record.run?.running) {
          void refreshSessions()
          void nameSession()
          return
        }
      } catch (error) {
        if (
          state.sessionId !== id ||
          !account.current() ||
          state.user !== owner ||
          version !== selectionVersion
        )
          return
        if ([401, 403, 404].includes((error as Error & { status?: number }).status ?? 0)) {
          clearRecovery()
          state.busy = false
          state.activeSession = null
          const turn = state.turns.at(-1)
          if (turn?.status === 'pending') {
            turn.status = 'error'
            turn.error = (error as Error).message
          }
          setStatus(connectionError(error), 'error')
          return
        }
        setStatus(`暂时无法同步回答，将继续重试：${connectionError(error)}`, 'busy')
      }
      recoverSession(id, owner, version)
    })
  }

  function openSession(id: string): Promise<void> {
    if (disposed) return Promise.resolve()
    if (pendingSelection?.id === id && pendingSelection.current()) return pendingSelection.promise
    cancelSelection()
    const version = ++selectionVersion
    const account = captureAccountScope()
    const request = {
      id,
      current: account.current,
      controller: new AbortController(),
      promise: Promise.resolve(),
    }
    pendingSelection = request
    request.promise = selectSession(id, version, account, request.controller.signal).finally(() => {
      if (pendingSelection === request) pendingSelection = null
    })
    return request.promise
  }

  async function selectSession(
    id: string,
    version: number,
    account: ReturnType<typeof captureAccountScope>,
    signal: AbortSignal,
  ): Promise<void> {
    runtime.cancelConnection()
    const owner = account.owner
    clearRecovery()
    try {
      let run = getRun(id)
      const record =
        run && !run.turns.some((turn) => turn.status === 'error' || turn.status === 'stopped')
          ? null
          : await api.load(id, signal)
      if (signal.aborted || version !== selectionVersion || !account.current()) return
      // A request may have started while the HTTP snapshot was in flight.
      // Its live turns take precedence over that older snapshot.
      run = getRun(id)
      if (!record && !run) return
      if (record && !run?.busy) {
        runtime.forgetRun(id)
        run = undefined
      }
      switchConversationDraft(id)
      state.sessionId = id
      if (run) state.turns = run.turns
      else showRecord(record!)
      state.sessionTitle = run ? run.title : (record!.title ?? '')
      if (record?.title_source) titleSources.set(sidebarScope(id, owner), record.title_source)
      if (run) {
        state.busy = run.busy
        state.activeSession = run.token
        activeTool.value = run.tool
      }
      rememberActiveSession(id)
      activeDataset.value =
        record && 'selected_dataset' in record
          ? (record.selected_dataset ?? null)
          : (sessionDatasets.get(id) ?? null)
      sessionDatasets.set(id, activeDataset.value)
      state.experimentContext = null
      setFiles(
        state.turns.flatMap((turn) => {
          const attached = (turn.context ?? {}).files
          return Array.isArray(attached) ? (attached as UploadedFile[]) : []
        }),
      )
      if (activeDataset.value)
        files.value =
          activeDataset.value.kind === 'upload' ? [activeDataset.value as UploadedFile] : []
      else if (record && 'selected_dataset' in record) files.value = []
      selectedKey.value = null
      indexBlocks()
      if (run) showRun(run)
      else if (record?.run?.running) recoverSession(id, owner, version)
      if (!state.busy) void nameSession()
    } catch (error) {
      if (!signal.aborted && version === selectionVersion && account.current())
        setStatus(connectionError(error), 'error')
    }
  }

  async function dropSession(id: string, syncCard = false): Promise<boolean> {
    if (disposed) return false
    const account = captureAccountScope()
    try {
      if (!(await api.remove(id, syncCard)) || !account.current()) return false
      runtime.cancelRun(id)
      if (state.sessionId === id) newSession()
      conversationDrafts.delete(`${state.user}\u0000${id}`)
      const learning = useLearning()
      await refreshSessions()
      await learning.refresh()
      return true
    } catch (error) {
      if (account.current()) setStatus(connectionError(error), 'error')
      return false
    }
  }

  function newSession(): void {
    cancelSelection()
    runtime.cancelConnection()
    switchConversationDraft(null)
    selectionVersion += 1
    clearRecovery()
    activeDataset.value = null
    state.experimentContext = null
    state.activeSession = null
    state.sessionId = null
    state.sessionTitle = ''
    state.turns = []
    state.busy = false
    activeTool.value = null
    files.value = []
    experiments.resetView()
    panelOpen.value = false
    rememberActiveSession(null)
    setStatus('')
  }

  function recordExperiment(result: ExperimentResult): void {
    acceptExperimentResult(result)
    const title = result.title ?? '实验'
    const turn: ChatTurn = {
      kind: 'experiment',
      question: `运行 ${title}`,
      answer: '',
      result,
      status: 'complete',
      created_at: new Date().toISOString(),
    }
    state.turns.push(turn)
    indexBlocks()
    selectedKey.value = blocks.value.at(-1)?.key ?? null
    openPanel()
    setStatus(`实验完成：${title}`)
    void persist()
  }

  async function restoreActive(): Promise<void> {
    await refreshSessions()
    const id = activeSessionId()
    if (id && state.sessions.some((item) => item.id === id)) await openSession(id)
  }

  async function checkAuth(): Promise<boolean> {
    if (disposed) return false
    const backend = ApiBase.get(),
      epoch = providers.credentialEpoch
    if (state.user) providerLoading.value = true
    const name = await authApi.current()
    if (backend !== ApiBase.get() || epoch !== providers.credentialEpoch) return false
    if ((name ?? '') !== state.user) {
      clearCredentials()
      conversationDrafts.clear()
      draft.value = ''
      useStudy().reset()
      useLearning().reset()
    }
    state.user = name ?? ''
    state.authExpired = false
    state.authChecked = true
    if (state.user) await refreshProviders()
    if (!state.user) {
      providerLoading.value = false
      state.sessions = []
      state.workspaces = []
    }
    return Boolean(state.user)
  }

  async function signIn(name: string, password: string): Promise<void> {
    if (disposed) throw new Error('工作区已关闭，请重新打开后操作。')
    const backend = ApiBase.get(),
      epoch = providers.credentialEpoch
    const user = await authApi.login(name, password)
    if (backend !== ApiBase.get() || epoch !== providers.credentialEpoch)
      throw new Error('账号或后端已变化，请在当前服务重新登录。')
    const recovering = state.authExpired && state.user === user.username
    if (state.user !== user.username) clearCredentials()
    else invalidateProviderLoad()
    useStudy().reset()
    useLearning().reset()
    state.user = user.username
    state.authExpired = false
    state.authChecked = true
    await refreshProviders()
    if (recovering) {
      await refreshSessions()
      setStatus('已重新登录，可以继续原会话。')
      return
    }
    resetToEmpty()
    await restoreActive()
  }

  async function signUp(name: string, password: string): Promise<void> {
    if (disposed) throw new Error('工作区已关闭，请重新打开后操作。')
    const backend = ApiBase.get(),
      epoch = providers.credentialEpoch
    const user = await authApi.register(name, password)
    if (backend !== ApiBase.get() || epoch !== providers.credentialEpoch)
      throw new Error('账号或后端已变化，请在当前服务重新登录。')
    clearCredentials()
    useStudy().reset()
    useLearning().reset()
    state.user = user.username
    state.authExpired = false
    state.authChecked = true
    await refreshProviders()
    resetToEmpty()
    await restoreActive()
  }

  async function signOut(): Promise<void> {
    if (disposed) return
    const backend = ApiBase.get(),
      epoch = providers.credentialEpoch
    try {
      await authApi.logout()
    } catch {
      if (backend === ApiBase.get() && epoch === providers.credentialEpoch)
        setStatus('退出登录未完成，请检查连接后重试。', 'error')
      return
    }
    if (backend !== ApiBase.get() || epoch !== providers.credentialEpoch) return
    useStudy().reset()
    useLearning().reset()
    clearCredentials()
    state.user = ''
    state.authExpired = false
    resetToEmpty()
    setStatus('已退出登录。')
  }

  function resetToEmpty(): void {
    cancelSelection()
    conversationDrafts.clear()
    draft.value = ''
    selectionVersion += 1
    clearRecovery()
    activeDataset.value = null
    sessionDatasets.clear()
    state.experimentContext = null
    runtime.cancelAll()
    runtime.cancelConnection()
    state.activeSession = null
    state.sessionId = null
    state.busy = false
    activeTool.value = null
    state.turns = []
    state.sessions = []
    state.workspaces = []
    files.value = []
    experiments.clearSelection()
    panelOpen.value = false
    rememberActiveSession(null)
  }

  function openLightbox(url: string, name: string): void {
    lightbox.value = { url, name }
  }

  function closeLightbox(): void {
    lightbox.value = null
  }

  function togglePanel(): void {
    panelOpen.value = !panelOpen.value
  }

  function openPanel(): void {
    panelOpen.value = true
  }

  function closePanel(): void {
    panelOpen.value = false
  }

  function setBackend(value: string): boolean {
    if (disposed) return false
    const previous = ApiBase.get()
    if (!ApiBase.set(value)) return false
    if (previous !== ApiBase.get()) {
      clearCredentials()
      runtime.cancelAll()
      runtime.cancelConnection()
      clearRecovery()
      state.busy = false
      state.activeSession = null
      activeTool.value = null
      state.authChecked = false
    }
    state.backend = ApiBase.get()
    state.connected = false
    if (previous !== ApiBase.get())
      void checkAuth().then((authenticated) => {
        if (authenticated) void refreshSessions()
      })
    else void refreshSessions()
    return true
  }

  return {
    state,
    blocks,
    selectedKey,
    panelOpen,
    lightbox,
    settingsOpen,
    activeTool,
    runningSessionIds,
    controller,
    indexBlocks,
    sidebarSaving,
    acceptExperimentResult,
    switchExperimentVersion,
    revealExperimentVersion,
    setBodyView,
    viewName,
    openSettings,
    closeSettings,
    setStatus,
    saveSettings,
    config,
    configurationIssue,
    modelAccess,
    modelReady,
    resolveModelAccess,
    providerLoading,
    providerLoadError,
    context,
    provider,
    ask,
    reviseLatest,
    forkTurn,
    testConnection,
    stop,
    refreshSessions,
    persist,
    nameSession,
    renameSession,
    ensureSession,
    openSession,
    dropSession,
    newSession,
    recordExperiment,
    restoreActive,
    checkAuth,
    signIn,
    signUp,
    signOut,
    openLightbox,
    closeLightbox,
    selectBlock,
    removeBlock,
    togglePanel,
    openPanel,
    closePanel,
    setDetail,
    setAllowTools,
    setApiKey,
    resetProvider,
    selectProvider,
    selectModel,
    setReasoningEffort,
    providerProfile,
    applyProviderProfiles,
    providerProfiles,
    hasSavedCredential,
    keyAvailable,
    refreshProviders,
    saveServerProvider,
    deleteServerProvider,
    addedProviderIds,
    providerReady,
    removeProvider,
    setBackend,
    draft,
    setDraft,
    files,
    activeDataset,
    chooseDataset,
    setFiles,
    addFile,
    removeFile,
    clearFiles,
  }
})

export function useLab() {
  const store = useLabStore()
  const refs = storeToRefs(store)
  return {
    ...refs,
    state: shallowReadonly(store.state),
    raw: store.state,
    selectedBlock: computed(
      () => refs.blocks.value.find((item) => item.key === refs.selectedKey.value) ?? null,
    ),
    turnCount: computed(() => store.state.turns.length),
    blockCount: computed(() => refs.blocks.value.length),
    suggestedTitle: computed(() => sessionTitle(store.state.turns)),
    indexBlocks: store.indexBlocks,
    acceptExperimentResult: store.acceptExperimentResult,
    switchExperimentVersion: store.switchExperimentVersion,
    revealExperimentVersion: store.revealExperimentVersion,
    setBodyView: store.setBodyView,
    viewName: store.viewName,
    openSettings: store.openSettings,
    closeSettings: store.closeSettings,
    openPanel: store.openPanel,
    closePanel: store.closePanel,
    togglePanel: store.togglePanel,
    selectBlock: store.selectBlock,
    removeBlock: store.removeBlock,
    openLightbox: store.openLightbox,
    closeLightbox: store.closeLightbox,
    ask: store.ask,
    reviseLatest: store.reviseLatest,
    forkTurn: store.forkTurn,
    stop: store.stop,
    testConnection: store.testConnection,
    refreshSessions: store.refreshSessions,
    persist: store.persist,
    nameSession: store.nameSession,
    renameSession: store.renameSession,
    ensureSession: store.ensureSession,
    openSession: store.openSession,
    dropSession: store.dropSession,
    newSession: store.newSession,
    recordExperiment: store.recordExperiment,
    restoreActive: store.restoreActive,
    checkAuth: store.checkAuth,
    signIn: store.signIn,
    signUp: store.signUp,
    signOut: store.signOut,
    setDetail: store.setDetail,
    setAllowTools: store.setAllowTools,
    setApiKey: store.setApiKey,
    setBackend: store.setBackend,
    resetProvider: store.resetProvider,
    selectProvider: store.selectProvider,
    selectModel: store.selectModel,
    setReasoningEffort: store.setReasoningEffort,
    providerProfile: store.providerProfile,
    applyProviderProfiles: store.applyProviderProfiles,
    providerProfiles: store.providerProfiles,
    hasSavedCredential: store.hasSavedCredential,
    keyAvailable: store.keyAvailable,
    resolveModelAccess: store.resolveModelAccess,
    refreshProviders: store.refreshProviders,
    saveServerProvider: store.saveServerProvider,
    deleteServerProvider: store.deleteServerProvider,
    providerReady: store.providerReady,
    removeProvider: store.removeProvider,
    saveSettings: store.saveSettings,
    setStatus: store.setStatus,
    setDraft: store.setDraft,
    addFile: store.addFile,
    removeFile: store.removeFile,
    clearFiles: store.clearFiles,
    setFiles: store.setFiles,
    chooseDataset: store.chooseDataset,
    config: store.config,
    context: store.context,
    provider: store.provider,
    serializableTurns,
  }
}
