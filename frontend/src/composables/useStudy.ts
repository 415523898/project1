import { computed, ref, shallowRef } from 'vue'
import { useLearning } from '@/composables/useLearning'
import {
  studyApi,
  StudyApiError,
  type StudyApi,
  type StudyCardModel,
  type StudyChanges,
  type StudyMode,
  type StudyAiOptions,
  type StudyEdge,
  type StudyOperation,
  type StudyOperationState,
  type StudyProgress,
  type StudyResult,
  type StudySide,
  type StudyWorkspace,
} from '@/services/study'

export type StudyIntent =
  | {
      kind: 'move'
      positions: Record<string, { x: number; y: number }>
      basis?: Record<string, { x: number; y: number }>
    }
  | {
      kind: 'edit'
      cardId: string
      values: Partial<Pick<StudyCardModel, 'title' | 'summary' | 'body'>>
      levelPin?: number | null
      basis?: Partial<{ title: string; summary: string; body: string; levelPin: string }>
    }
  | { kind: 'create'; title: string; summary: string; x: number; y: number }
  | { kind: 'delete' | 'remove' | 'add'; cardIds: string[]; syncSessions?: boolean }
  | { kind: 'lock'; cardIds: string[]; locked: boolean }
  | {
      kind: 'create-edge'
      fromId: string
      toId: string
      sourceSide: StudySide
      targetSide: StudySide
    }
  | {
      kind: 'delete-edge'
      edgeId: string
      basis?: Pick<StudyEdge, 'revision' | 'from_id' | 'to_id' | 'type' | 'why'>
    }
  | { kind: 'history'; direction: 'undo' | 'redo'; revisionId: string }
  | { kind: 'ai-relations'; options: StudyAiOptions }
  | { kind: 'resume-ai'; instruction: string }

export interface StudyQueueEntry {
  id: string
  intent: StudyIntent
  status: 'queued' | 'saving' | 'failed' | 'unknown' | 'conflict' | 'committed'
  payload?: StudyChanges
  result?: StudyResult
  error: string
  progress?: StudyProgress
  readAttempts?: number
  recoveryAttempts?: number
}
export interface CardDraft {
  title: string
  summary: string
  body: string
  levelPin: string
  version: number
  dirty: boolean
  baseline: { title: string; summary: string; body: string; levelPin: string }
}
let idCounter = 0
const freshId = () =>
  'study-' +
  (globalThis.crypto?.randomUUID?.() ??
    `${Date.now().toString(36)}-${++idCounter}-${Math.random().toString(36).slice(2)}`)
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T

/** One account-scoped queue survives route navigation; auth changes invalidate all callbacks. */
export function createStudyState(
  api: StudyApi = studyApi,
  bindingsChanged: () => Promise<void> = async () => {},
) {
  const workspace = shallowRef<StudyMode | null>(null)
  const loading = ref(false),
    loadError = ref(''),
    error = ref(''),
    owner = ref<string | null>(null)
  const queue = ref<StudyQueueEntry[]>([])
  const drafts = ref<Record<string, CardDraft>>({})
  const newCardDraft = ref({ title: '', summary: '' })
  const feedback = ref('')
  const syncing = ref(false),
    syncError = ref('')
  const lastResult = shallowRef<StudyResult | null>(null)
  const completion = new Map<string, (result: StudyResult | null) => void>()
  const requests = new Set<AbortController>()
  let generation = 0,
    processing = false,
    loadSequence = 0
  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let validationTimer: ReturnType<typeof setTimeout> | null = null
  const delays = new Map<ReturnType<typeof setTimeout>, () => void>()
  let backgroundFlight: Promise<void> | null = null,
    backgroundAgain = false,
    forceValidation = false
  const aiIntent = (intent: StudyIntent) =>
    intent.kind === 'ai-relations' || intent.kind === 'resume-ai'
  const graph = computed(() => (workspace.value?.mode === 'study_v2' ? workspace.value : null))
  const paused = computed(() =>
    Boolean(queue.value[0] && !['queued', 'saving'].includes(queue.value[0].status)),
  )
  const saving = computed(() =>
    queue.value.some((entry) => ['saving', 'committed'].includes(entry.status)),
  )
  const status = computed(() => {
    const first = queue.value[0]
    if (first?.status === 'committed')
      return first.readAttempts && first.readAttempts > 3 ? '已提交，暂未同步' : '已提交，正在同步…'
    if (first?.status === 'unknown') {
      if (!aiIntent(first.intent)) return '保存结果待确认'
      const progress = first.progress
      return progress
        ? `${progress.message || 'AI 正在整理'} · 已完成 ${progress.completed_steps ?? 0} 步${progress.elapsed_ms === undefined ? '' : ` · ${Math.floor(progress.elapsed_ms / 1000)} 秒`}`
        : 'AI 正在整理…'
    }
    if (first?.status === 'conflict') return '修订冲突，修改已保留'
    if (first?.status === 'failed')
      return aiIntent(first.intent)
        ? first.progress?.changed_batches
          ? `AI 整理中断，已保存 ${first.progress.changed_batches} 批调整`
          : 'AI 整理失败，路线未改动'
        : '保存失败，修改已保留'
    if (queue.value.length) return saving.value ? '保存中…' : '未保存'
    return Object.values(drafts.value).some((draft) => draft.dirty) ||
      newCardDraft.value.title ||
      newCardDraft.value.summary
      ? '未保存'
      : '已保存'
  })

  async function request<T>(call: (signal: AbortSignal) => Promise<T>): Promise<T> {
    const requestGeneration = generation
    const controller = new AbortController()
    requests.add(controller)
    const timer = setTimeout(
      () => controller.abort(new DOMException('请求超过 15 秒。', 'TimeoutError')),
      15000,
    )
    try {
      return await call(controller.signal)
    } catch (problem) {
      if (
        requestGeneration === generation &&
        problem instanceof StudyApiError &&
        problem.code === 'account_changed'
      ) {
        reset()
        loadError.value = '登录账号已变化，请重新登录。'
      }
      throw problem
    } finally {
      clearTimeout(timer)
      requests.delete(controller)
    }
  }
  function reset(nextOwner: string | null = null) {
    generation++
    loadSequence++
    for (const controller of requests) controller.abort()
    requests.clear()
    for (const finish of completion.values()) finish(null)
    completion.clear()
    owner.value = nextOwner
    workspace.value = null
    queue.value = []
    drafts.value = {}
    newCardDraft.value = { title: '', summary: '' }
    if (pollTimer) clearTimeout(pollTimer)
    if (validationTimer) clearTimeout(validationTimer)
    for (const [timer, done] of delays) {
      clearTimeout(timer)
      done()
    }
    delays.clear()
    validationTimer = null
    backgroundFlight = null
    backgroundAgain = false
    forceValidation = false
    syncing.value = false
    syncError.value = ''
    pollTimer = null
    feedback.value = ''
    lastResult.value = null
    loading.value = false
    loadError.value = ''
    error.value = ''
    processing = false
  }
  async function open(nextOwner: string, force = false) {
    if (owner.value !== nextOwner) reset(nextOwner)
    if (workspace.value && !force) return
    const version = generation,
      sequence = ++loadSequence
    loading.value = true
    loadError.value = ''
    try {
      const value = await request((signal) => api.workspace(signal, nextOwner))
      if (version === generation && sequence === loadSequence) {
        if (
          value.mode === 'study_v2' &&
          graph.value &&
          (value.graph_revision < graph.value.graph_revision ||
            value.layout_revision < graph.value.layout_revision)
        )
          return
        workspace.value = value
        if (value.mode === 'study_v2' && value.pending_operation && !queue.value.length) {
          const pending = value.pending_operation
          const entry: StudyQueueEntry = {
            id: pending.operation_id,
            intent: { kind: 'resume-ai', instruction: pending.instruction },
            status: 'unknown',
            error: 'AI 正在整理，完成后会直接保存。',
            progress: pending.progress,
          }
          queue.value.push(entry)
          schedulePoll(entry, version)
        }
      }
    } catch (problem) {
      if (
        version === generation &&
        problem instanceof StudyApiError &&
        problem.code === 'account_changed'
      ) {
        reset()
        loadError.value = '登录账号已变化，请重新登录。'
        return
      }
      if (version === generation && sequence === loadSequence)
        loadError.value = (problem as Error).message || '学习路线加载失败。'
    } finally {
      if (version === generation && sequence === loadSequence) loading.value = false
    }
  }
  function operations(intent: StudyIntent, value: StudyWorkspace): StudyOperation[] {
    const card = (id: string) => {
      const row = value.cards.find((item) => item.card_id === id)
      if (!row) throw new Error('卡片已不存在，请核对草稿。')
      return row
    }
    const node = (id: string) => {
      const row = value.nodes.find((item) => item.card_id === id)
      if (!row) throw new Error('节点已移出路线，请核对草稿。')
      return row
    }
    switch (intent.kind) {
      case 'move':
        return [
          {
            op: 'move_nodes',
            nodes: Object.entries(intent.positions).map(([id, position]) => ({
              card_id: id,
              expected_revision: node(id).revision,
              ...position,
            })),
          },
        ]
      case 'edit': {
        const result: StudyOperation[] = []
        if (Object.keys(intent.values).length)
          result.push({
            op: 'update_card',
            card_id: intent.cardId,
            expected_revision: card(intent.cardId).revision,
            changes: intent.values,
          })
        if (intent.levelPin !== undefined)
          result.push({
            op: 'set_level_pin',
            card_id: intent.cardId,
            expected_revision: node(intent.cardId).revision,
            level_pin: intent.levelPin,
          })
        return result
      }
      case 'create':
        return [
          {
            op: 'create_card',
            client_ref: 'new_card',
            values: { title: intent.title, summary: intent.summary },
          },
          { op: 'add_node', card_id: 'new_card', x: intent.x, y: intent.y },
        ]
      case 'delete':
        return intent.cardIds.map((id) => ({
          op: 'delete_card',
          card_id: id,
          expected_revision: card(id).revision,
        }))
      case 'remove':
        return intent.cardIds.map((id) => ({
          op: 'remove_node',
          card_id: id,
          expected_revision: node(id).revision,
        }))
      case 'add':
        return intent.cardIds.map((id) => ({
          op: 'add_node',
          card_id: id,
          expected_revision: card(id).revision,
        }))
      case 'lock':
        return intent.cardIds.map((id) => ({
          op: 'set_node_lock',
          card_id: id,
          expected_revision: node(id).revision,
          position_locked: intent.locked,
        }))
      case 'create-edge':
        node(intent.fromId)
        node(intent.toId)
        return [
          {
            op: 'create_edge',
            client_ref: 'new_edge',
            from_id: intent.fromId,
            to_id: intent.toId,
            type: 'suggested_next',
            why: '用户设定',
          },
          {
            op: 'set_edge_route',
            edge_id: 'new_edge',
            changes: { source_side: intent.sourceSide, target_side: intent.targetSide },
          },
        ]
      case 'delete-edge': {
        const edge = value.edges.find((edge) => edge.edge_id === intent.edgeId)
        if (!edge) throw new Error('这条连线已不存在，请核对待保存修改。')
        return [{ op: 'delete_edge', edge_id: edge.edge_id, expected_revision: edge.revision }]
      }
      case 'history':
        return [{ op: intent.direction, revision_id: intent.revisionId }]
      case 'ai-relations':
        return [
          {
            op: 'ai_relations',
            instruction: intent.options.instruction,
            card_ids: intent.options.cardIds,
            allow_manual: intent.options.allowManual,
            include_removed: intent.options.includeRemoved,
            arrange_layout: intent.options.arrangeLayout ?? false,
            connect_all: intent.options.connectAll ?? false,
            provider: intent.options.provider,
          },
        ]
      case 'resume-ai':
        throw new Error('刷新恢复的整理仅查询原任务，不重新发起模型调用。')
    }
  }
  async function refresh(version: number) {
    const sequence = ++loadSequence
    const value = await request((signal) => api.workspace(signal, owner.value ?? undefined))
    if (generation !== version) return null
    if (value.mode !== 'study_v2') throw new Error('服务端账号模式已变化，请重新打开路线。')
    if (sequence !== loadSequence) return graph.value
    if (
      graph.value &&
      (value.graph_revision < graph.value.graph_revision ||
        value.layout_revision < graph.value.layout_revision)
    )
      return graph.value
    workspace.value = value
    loading.value = false
    return value
  }
  function delay(ms: number) {
    return new Promise<void>((resolve) => {
      const timer = setTimeout(() => {
        delays.delete(timer)
        resolve()
      }, ms)
      delays.set(timer, resolve)
    })
  }
  const transient = (problem: unknown) =>
    !(problem instanceof StudyApiError) ||
    problem.status >= 500 ||
    [408, 429].includes(problem.status)
  async function readCommitted(entry: StudyQueueEntry, result: StudyResult, version: number) {
    for (let attempt = 0; attempt < 4; attempt++) {
      if (version !== generation) return null
      entry.readAttempts = attempt + 1
      try {
        const current = await refresh(version)
        if (!current || version !== generation) return null
        if (
          current.graph_revision < result.graph_revision ||
          current.layout_revision < result.layout_revision
        )
          throw new Error('最新版本尚未可读。')
        return current
      } catch (problem) {
        if (version !== generation) return null
        if (!transient(problem) || attempt === 3) throw problem
        entry.error = '修改已提交，正在自动重新读取。'
        await delay([200, 600, 1400][attempt]!)
      }
    }
    return null
  }
  function project(result: StudyResult): StudyWorkspace | null {
    const current = graph.value,
      patch = result.projection
    if (
      !current ||
      !patch ||
      current.graph_revision !== patch.base_graph_revision ||
      current.layout_revision !== patch.base_layout_revision
    )
      return null
    const next = clone(current)
    const ids = {
      cards: 'card_id',
      nodes: 'card_id',
      edges: 'edge_id',
      edge_routes: 'edge_id',
      sources: 'source_id',
      groups: 'group_id',
    } as const
    for (const change of patch.changes) {
      if (!(change.table in ids)) return null
      const rows = next[change.table] as unknown as Array<Record<string, unknown>>
      const index = rows.findIndex((row) => row[ids[change.table]] === change.id)
      if (change.value === null) {
        if (index >= 0) rows.splice(index, 1)
      } else if (index >= 0) rows[index] = clone(change.value)
      else rows.push(clone(change.value))
    }
    for (const node of next.nodes)
      if (patch.levels[node.card_id] !== undefined) node.level = patch.levels[node.card_id]!
    next.graph_revision = result.graph_revision
    next.layout_revision = result.layout_revision
    if (next.pending_operation?.operation_id === result.operation_id) next.pending_operation = null
    next.history = patch.history ? clone(patch.history) : undefined
    next.warnings = result.warnings ?? []
    ++loadSequence
    loading.value = false
    workspace.value = next
    return next
  }
  function scheduleValidation(version: number, force = false) {
    if (!api.revision || version !== generation) return
    forceValidation ||= force
    if (validationTimer) clearTimeout(validationTimer)
    validationTimer = setTimeout(() => {
      validationTimer = null
      void validateBackground(version)
    }, 250)
  }
  async function validateBackground(version: number): Promise<void> {
    if (version !== generation) return
    if (backgroundFlight) {
      backgroundAgain = true
      return backgroundFlight
    }
    syncing.value = true
    const flight = (async () => {
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          if (version !== generation) return
          const stamp = api.revision
            ? await request((signal) => api.revision!(signal, owner.value ?? undefined))
            : null
          if (version !== generation) return
          if (
            forceValidation ||
            !stamp ||
            !graph.value ||
            stamp.graph_revision > graph.value.graph_revision ||
            stamp.layout_revision > graph.value.layout_revision
          ) {
            await refresh(version)
          }
          if (version === generation) {
            syncError.value = ''
            forceValidation = false
          }
          return
        } catch (problem) {
          if (version !== generation) return
          if (!transient(problem) || attempt === 3) {
            syncError.value = '修改已保存，暂时无法校验最新路线。'
            return
          }
          await delay([200, 600, 1400][attempt]!)
        }
      }
    })()
    backgroundFlight = flight
    try {
      await flight
    } finally {
      if (version === generation && backgroundFlight === flight) {
        backgroundFlight = null
        syncing.value = false
        if (backgroundAgain) {
          backgroundAgain = false
          scheduleValidation(version)
        }
      }
    }
  }
  async function recoverRejected(entry: StudyQueueEntry, message: string, version: number) {
    entry.status = 'conflict'
    entry.error = message
    if (!aiIntent(entry.intent))
      for (const pending of queue.value) {
        if (pending.intent.kind !== 'edit') continue
        const existing = drafts.value[pending.intent.cardId]
        const kept = draft(pending.intent.cardId)
        if (kept) {
          for (const field of ['title', 'summary', 'body'] as const) {
            const value = pending.intent.values[field]
            if (value !== undefined && (!existing || kept[field] === kept.baseline[field]))
              kept[field] = value
          }
          if (
            pending.intent.levelPin !== undefined &&
            (!existing || kept.levelPin === kept.baseline.levelPin)
          ) {
            kept.levelPin = pending.intent.levelPin == null ? '' : String(pending.intent.levelPin)
          }
          kept.dirty = true
        }
      }
    try {
      await refresh(version)
    } catch {
      if (version === generation) entry.error += ' 当前服务端数据暂不可读取。'
    }
    if (version !== generation || aiIntent(entry.intent)) return
    // Conflicts never overwrite another page. Keep text editable against the refreshed baseline.
    for (const [id, draft] of Object.entries(drafts.value)) {
      const card = graph.value?.cards.find((card) => card.card_id === id)
      const node = graph.value?.nodes.find((node) => node.card_id === id)
      if (!card) continue
      const baseline = {
        title: card.title,
        summary: card.summary,
        body: card.body,
        levelPin: node?.level_pin == null ? '' : String(node.level_pin),
      }
      for (const field of ['title', 'summary', 'body', 'levelPin'] as const) {
        if (draft[field] === draft.baseline[field]) draft[field] = baseline[field]
      }
      draft.baseline = baseline
      draft.dirty = (['title', 'summary', 'body', 'levelPin'] as const).some(
        (field) => draft[field] !== baseline[field],
      )
    }
    error.value = `${entry.error} 文字草稿已保留，可继续编辑后保存；其他操作请重新执行。`
    for (const pending of queue.value) {
      if (pending.intent.kind === 'create' && !newCardDraft.value.title) {
        newCardDraft.value = { title: pending.intent.title, summary: pending.intent.summary }
      }
      completion.get(pending.id)?.(null)
      completion.delete(pending.id)
    }
    queue.value = []
  }
  async function committed(entry: StudyQueueEntry, result: StudyResult, version: number) {
    if (version !== generation) return
    entry.result = result
    entry.status = 'committed'
    entry.error = ''
    try {
      const projected = project(result)
      const current = projected ?? (await readCommitted(entry, result, version))
      const changedBindings =
        result.changed && (entry.intent.kind === 'delete' || entry.intent.kind === 'history')
      if (changedBindings) void bindingsChanged().catch(() => {})
      if (!current || version !== generation) return
      if (entry.intent.kind === 'delete')
        for (const id of entry.intent.cardIds) delete drafts.value[id]
      for (const [id, draft] of Object.entries(drafts.value)) {
        const card = current.cards.find((card) => card.card_id === id),
          node = current.nodes.find((node) => node.card_id === id)
        if (entry.intent.kind === 'edit' && entry.intent.cardId === id) {
          Object.assign(draft.baseline, entry.intent.values)
          if (entry.intent.levelPin !== undefined)
            draft.baseline.levelPin =
              entry.intent.levelPin == null ? '' : String(entry.intent.levelPin)
          draft.dirty = (['title', 'summary', 'body', 'levelPin'] as const).some(
            (field) => draft[field] !== draft.baseline[field],
          )
        }
        if (
          card &&
          draft.title === card.title &&
          draft.summary === card.summary &&
          draft.body === card.body &&
          draft.levelPin === (node?.level_pin == null ? '' : String(node.level_pin))
        )
          draft.dirty = false
      }
      queue.value = queue.value.filter((item) => item.id !== entry.id)
      if (result.ai_summary) {
        const summary = result.ai_summary
        feedback.value = `AI 整理完成：新增 ${summary.created}、修改 ${summary.updated}、删除 ${summary.deleted}、保护保留 ${summary.protected} 条关系。${summary.moved === undefined ? '' : `已重新排列 ${summary.moved} 张卡片。`}${result.changed ? '可向后撤回。' : '路线未发生变化。'}`
        if (summary.strategy === 'reference_v1')
          feedback.value += `已按参考路线完成两轮检查，覆盖 ${summary.checked} 张卡片，${summary.isolated} 张暂无顺序连接。`
        if (summary.strategy === 'tools_v1')
          feedback.value += `已完成 ${summary.steps ?? 0} 个工具步骤，回读检查 ${summary.checked} 张卡片。`
        if (summary.strategy === 'tools_v1' && (summary.model_links || summary.reference_links)) {
          feedback.value += `其中模型自行判断 ${summary.model_links ?? 0} 条关系，采用参考骨架 ${summary.reference_links ?? 0} 条。`
        }
        if (summary.pruned_shortcuts)
          feedback.value += `已去掉 ${summary.pruned_shortcuts} 条可由间接路径表达的冗余连线。`
        if (summary.declined_reference)
          feedback.value += `模型说明了 ${summary.declined_reference} 条参考关系为何不采纳。`
        if (summary.reference_fallbacks?.length)
          feedback.value += `采用参考骨架的原因：${summary.reference_fallbacks.join('；')}`
        if (summary.restored) feedback.value += `补回 ${summary.restored} 条有依据的流程连接。`
      } else if (result.history_action)
        feedback.value = `${result.history_action.direction === 'undo' ? '已向后撤回' : '已向前撤回'}：${result.history_action.label}`
      lastResult.value = result
      completion.get(entry.id)?.(result)
      completion.delete(entry.id)
      if (projected) scheduleValidation(version, changedBindings)
      const next = queue.value[0]
      const nextWritesLayout = next && ['move', 'lock'].includes(next.intent.kind)
      if (
        next &&
        (current.graph_revision !== result.graph_revision ||
          (nextWritesLayout && current.layout_revision !== result.layout_revision))
      ) {
        next.status = 'conflict'
        next.error = '其他页面已修改路线，请核对当前值和待保存修改。'
      }
    } catch {
      if (version === generation)
        entry.error = '修改已提交，自动同步暂未完成。可重新同步，不会重复保存或执行 AI。'
    }
  }
  async function handleState(entry: StudyQueueEntry, state: StudyOperationState, version: number) {
    if (version !== generation) return
    if (state.status === 'succeeded') await committed(entry, state, version)
    else if (state.status === 'running') {
      entry.status = 'unknown'
      entry.error = aiIntent(entry.intent)
        ? 'AI 正在整理，完成后会直接保存。'
        : '服务端仍在处理，请确认保存结果后继续。'
      if (state.progress) {
        entry.progress = state.progress
        if (
          graph.value &&
          ((state.progress.graph_revision !== undefined &&
            state.progress.graph_revision !== graph.value.graph_revision) ||
            (state.progress.layout_revision !== undefined &&
              state.progress.layout_revision !== graph.value.layout_revision))
        )
          await refresh(version)
      }
      entry.recoveryAttempts = 0
      schedulePoll(entry, version)
    } else if ((state.partial_result || state.progress) && aiIntent(entry.intent)) {
      await refresh(version)
      if (version !== generation) return
      if (pollTimer) clearTimeout(pollTimer)
      pollTimer = null
      const batches = state.progress?.changed_batches ?? 0
      const saved = state.partial_result?.changed || batches > 0
      error.value = `${state.failure?.error || '整理中断。'} ${
        saved
          ? `${batches ? `已保存 ${batches} 批调整` : '已保存部分调整'}，整理尚未完成，可向后撤回整次整理。`
          : '本次整理未修改路线，可调整提示词后重试。'
      }`
      queue.value = queue.value.filter((item) => item.id !== entry.id)
      completion.get(entry.id)?.(null)
      completion.delete(entry.id)
    } else if (state.failure?.code?.includes('conflict'))
      await recoverRejected(entry, state.failure.error || '修订已变化。', version)
    else if (!aiIntent(entry.intent))
      await recoverRejected(entry, state.failure?.error || '变更未提交，请调整后再保存。', version)
    else {
      entry.status = 'failed'
      entry.error = state.failure?.error || '变更未提交，可以重试。'
    }
  }
  function schedulePoll(entry: StudyQueueEntry, version: number) {
    if (pollTimer) clearTimeout(pollTimer)
    if ((entry.recoveryAttempts ?? 0) > 3) return
    pollTimer = setTimeout(
      async () => {
        pollTimer = null
        if (generation !== version || queue.value[0]?.id !== entry.id || entry.status !== 'unknown')
          return
        if (processing) {
          schedulePoll(entry, version)
          return
        }
        processing = true
        try {
          const found = await confirmResult(entry, version)
          if (found === 'missing' && generation === version) {
            entry.status = 'failed'
            entry.error = '原整理任务不存在，请重新发起整理。'
          }
        } finally {
          if (generation === version) {
            processing = false
            if (entry.status === 'unknown') schedulePoll(entry, version)
            else void process()
          }
        }
      },
      entry.recoveryAttempts ? Math.min(5000, 800 * 2 ** entry.recoveryAttempts) : 800,
    )
  }
  async function confirmResult(
    entry: StudyQueueEntry,
    version: number,
  ): Promise<'missing' | 'handled'> {
    try {
      await handleState(
        entry,
        await request((signal) => api.operation(entry.id, signal, owner.value ?? undefined)),
        version,
      )
      return 'handled'
    } catch (problem) {
      if (version !== generation) return 'handled'
      if (problem instanceof StudyApiError && problem.code === 'account_changed') {
        reset()
        loadError.value = '登录账号已变化，请重新登录。'
        return 'handled'
      }
      if (problem instanceof StudyApiError && problem.status === 404) return 'missing'
      entry.status = 'unknown'
      entry.recoveryAttempts = (entry.recoveryAttempts ?? 0) + 1
      entry.error = '暂时无法确认保存结果，修改已保留，正在自动重连。'
      if (entry.recoveryAttempts <= 3) schedulePoll(entry, version)
      return 'handled'
    }
  }
  async function send(entry: StudyQueueEntry, version: number) {
    if (version !== generation) return
    if (!entry.payload) {
      const current = graph.value
      if (!current) return
      if (entry.intent.kind === 'move' && entry.intent.basis) {
        for (const [id, point] of Object.entries(entry.intent.basis)) {
          const node = current.nodes.find((node) => node.card_id === id)
          if (!node || Math.abs(node.x - point.x) > 0.001 || Math.abs(node.y - point.y) > 0.001)
            throw new StudyApiError(
              '拖动期间位置已变化，请核对保留的移动草稿。',
              409,
              'layout_conflict',
            )
        }
      }
      if (entry.intent.kind === 'edit' && entry.intent.basis) {
        const intent = entry.intent,
          card = current.cards.find((card) => card.card_id === intent.cardId)
        const node = current.nodes.find((node) => node.card_id === intent.cardId)
        for (const [field, oldValue] of Object.entries(entry.intent.basis)) {
          const currentValue =
            field === 'levelPin'
              ? node?.level_pin == null
                ? ''
                : String(node.level_pin)
              : card?.[field as 'title' | 'summary' | 'body']
          if (currentValue !== oldValue)
            throw new StudyApiError(
              '编辑期间内容已变化，请核对当前值和文字草稿。',
              409,
              'object_conflict',
            )
        }
      }
      if (entry.intent.kind === 'delete-edge' && entry.intent.basis) {
        const intent = entry.intent,
          edge = current.edges.find((edge) => edge.edge_id === intent.edgeId)
        if (
          !edge ||
          Object.entries(intent.basis!).some(
            ([key, value]) => edge[key as keyof StudyEdge] !== value,
          )
        )
          throw new StudyApiError('连线已变化，请核对当前关系后再删除。', 409, 'object_conflict')
      }
      entry.payload = {
        schema_version: 2,
        operation_id: entry.id,
        base_graph_revision: current.graph_revision,
        base_layout_revision: current.layout_revision,
        operations: operations(entry.intent, current),
        ...(entry.intent.kind === 'delete'
          ? { delete_choice: entry.intent.syncSessions ? ('both' as const) : ('only' as const) }
          : {}),
      }
    }
    entry.status = 'saving'
    entry.error = ''
    try {
      await handleState(
        entry,
        await request((signal) => api.changes(entry.payload!, signal, owner.value ?? undefined)),
        version,
      )
    } catch (problem) {
      if (version !== generation) return
      if (problem instanceof StudyApiError) {
        if (problem.code === 'account_changed') {
          reset()
          loadError.value = '登录账号已变化，请重新登录。'
        } else if (problem.status === 409) await recoverRejected(entry, problem.message, version)
        else if (!aiIntent(entry.intent) && problem.status >= 400 && problem.status < 500)
          await recoverRejected(entry, problem.message, version)
        else if (problem.status >= 500) {
          if ((await confirmResult(entry, version)) === 'missing') {
            entry.status = 'failed'
            entry.error = '服务端未确认提交，修改已保留。'
          }
        } else {
          entry.status = 'failed'
          entry.error = problem.message
        }
      } else if ((await confirmResult(entry, version)) === 'missing') {
        entry.status = 'failed'
        entry.error = '连接中断，服务端未记录提交结果。修改已保留，可重试。'
      }
    }
  }
  async function process() {
    if (processing || !graph.value) return
    const version = generation
    processing = true
    try {
      while (generation === version && queue.value[0]?.status === 'queued') {
        const entry = queue.value[0]
        try {
          await send(entry, version)
        } catch (problem) {
          if (generation !== version) return
          if (problem instanceof StudyApiError && problem.status === 409)
            await recoverRejected(entry, problem.message, version)
          else {
            entry.status = 'failed'
            entry.error = (problem as Error).message
          }
        }
      }
    } finally {
      if (generation === version) processing = false
    }
  }
  function submit(intent: StudyIntent): Promise<StudyResult | null> {
    if (!graph.value) return Promise.resolve(null)
    error.value = ''
    feedback.value = ''
    const entry: StudyQueueEntry = {
      id: freshId(),
      intent: clone(intent),
      status: 'queued',
      error: '',
    }
    const result = new Promise<StudyResult | null>((resolve) => completion.set(entry.id, resolve))
    queue.value.push(entry)
    void process()
    return result
  }
  async function restartAi(options: StudyAiOptions): Promise<StudyResult | null> {
    const previous = queue.value[0]
    if (
      !previous ||
      !aiIntent(previous.intent) ||
      !['failed', 'conflict'].includes(previous.status) ||
      processing
    )
      return null
    const version = generation
    try {
      await refresh(version)
      if (generation !== version || queue.value[0]?.id !== previous.id) return null
      if (pollTimer) clearTimeout(pollTimer)
      pollTimer = null
      completion.get(previous.id)?.(null)
      completion.delete(previous.id)
      const entry: StudyQueueEntry = {
        id: freshId(),
        intent: { kind: 'ai-relations', options: clone(options) },
        status: 'queued',
        error: '',
      }
      const result = new Promise<StudyResult | null>((resolve) => completion.set(entry.id, resolve))
      queue.value = [entry, ...queue.value.slice(1)]
      feedback.value = ''
      error.value = ''
      void process()
      return result
    } catch (problem) {
      if (version === generation) previous.error = (problem as Error).message
      return null
    }
  }
  async function retry() {
    const entry = queue.value[0]
    if (!entry) {
      await validateBackground(generation)
      return
    }
    if (processing || entry.status === 'conflict') return
    entry.recoveryAttempts = 0
    const version = generation
    processing = true
    try {
      if (entry.result) await committed(entry, entry.result, version)
      else if ((await confirmResult(entry, version)) === 'missing' || entry.status === 'failed')
        await send(entry, version)
    } finally {
      if (version === generation) {
        processing = false
        void process()
      }
    }
  }
  async function acceptExternal(nextOwner: string, result: StudyResult) {
    if (owner.value !== nextOwner || !graph.value) return
    if (project(result)) scheduleValidation(generation)
    else if (
      graph.value.graph_revision < result.graph_revision ||
      graph.value.layout_revision < result.layout_revision
    )
      await open(nextOwner, true)
  }
  async function cancelAi() {
    const entry = queue.value[0]
    if (!entry || !aiIntent(entry.intent) || !api.cancel || entry.status === 'committed') return
    const version = generation
    try {
      const result = await request((signal) =>
        api.cancel!(entry.id, signal, owner.value ?? undefined),
      )
      if (version !== generation) return
      if (result.status === 'succeeded') await committed(entry, result, version)
      else if (result.partial_result) {
        await handleState(entry, result, version)
        void process()
      } else if (result.status === 'failed' && result.failure?.code === 'cancelled') {
        if (pollTimer) clearTimeout(pollTimer)
        pollTimer = null
        queue.value = queue.value.filter((item) => item.id !== entry.id)
        completion.get(entry.id)?.(null)
        completion.delete(entry.id)
        feedback.value = '整理已停止，结果未应用。'
        void process()
      } else await handleState(entry, result, version)
    } catch (problem) {
      if (version === generation) entry.error = (problem as Error).message
    }
  }
  const view = computed(() => {
    const value = graph.value
    if (!value) return null
    const result = clone(value)
    for (const { intent } of queue.value) {
      if (intent.kind === 'move')
        for (const node of result.nodes) Object.assign(node, intent.positions[node.card_id] ?? {})
      if (intent.kind === 'edit') {
        const card = result.cards.find((card) => card.card_id === intent.cardId)
        if (card) Object.assign(card, intent.values)
        const node = result.nodes.find((node) => node.card_id === intent.cardId)
        if (node && intent.levelPin !== undefined) node.level_pin = intent.levelPin
      }
    }
    return result
  })
  function draft(cardId: string): CardDraft | null {
    const card = graph.value?.cards.find((item) => item.card_id === cardId)
    if (!card) return null
    const node = graph.value?.nodes.find((item) => item.card_id === cardId)
    const existing = drafts.value[cardId]
    if (existing?.dirty) return existing
    const baseline = {
      title: card.title,
      summary: card.summary,
      body: card.body,
      levelPin: node?.level_pin == null ? '' : String(node.level_pin),
    }
    if (!existing || JSON.stringify(existing.baseline) !== JSON.stringify(baseline))
      drafts.value[cardId] = { ...baseline, baseline, version: 0, dirty: false }
    return drafts.value[cardId]!
  }
  function editDraft(
    cardId: string,
    field: 'title' | 'summary' | 'body' | 'levelPin',
    text: string,
  ) {
    const value = draft(cardId)
    if (!value) return
    value[field] = text
    value.version++
    value.dirty = true
  }
  async function saveDraft(cardId: string) {
    const value = draft(cardId)
    if (!value || paused.value) return
    if (!value.title.trim()) {
      error.value = '请填写卡片标题。'
      return
    }
    const pin = value.levelPin.trim() ? Number(value.levelPin) : null
    if (
      pin !== null &&
      (!/^\d+$/.test(value.levelPin.trim()) || !Number.isInteger(pin) || pin < 1 || pin > 999)
    ) {
      error.value = '编号须为 1–999 的整数，留空恢复自动等级。'
      return
    }
    error.value = ''
    const values: Extract<StudyIntent, { kind: 'edit' }>['values'] = {}
    for (const field of ['title', 'summary', 'body'] as const)
      if (value[field] !== value.baseline[field]) values[field] = value[field]
    const levelPin = value.levelPin !== value.baseline.levelPin ? pin : undefined
    if (!Object.keys(values).length && levelPin === undefined) {
      value.dirty = false
      return
    }
    const version = value.version
    const basis: Extract<StudyIntent, { kind: 'edit' }>['basis'] = {}
    for (const field of Object.keys(values) as Array<keyof typeof values>)
      basis[field] = value.baseline[field]
    if (levelPin !== undefined) basis.levelPin = value.baseline.levelPin
    // Earlier local edits provide the expected values for the next serial edit.
    for (const pending of queue.value)
      if (pending.intent.kind === 'edit' && pending.intent.cardId === cardId) {
        for (const field of Object.keys(values) as Array<keyof typeof values>)
          if (pending.intent.values[field] !== undefined)
            basis[field] = pending.intent.values[field]
        if (levelPin !== undefined && pending.intent.levelPin !== undefined)
          basis.levelPin = pending.intent.levelPin == null ? '' : String(pending.intent.levelPin)
      }
    const result = await submit({ kind: 'edit', cardId, values, levelPin, basis })
    if (result && drafts.value[cardId]?.version === version) {
      delete drafts.value[cardId]
      draft(cardId)
    }
  }
  return {
    workspace,
    graph,
    view,
    loading,
    loadError,
    error,
    owner,
    queue,
    drafts,
    newCardDraft,
    paused,
    saving,
    status,
    feedback,
    lastResult,
    syncing,
    syncError,
    open,
    reset,
    submit,
    retry,
    draft,
    editDraft,
    saveDraft,
    cancelAi,
    restartAi,
    acceptExternal,
  }
}

const state = createStudyState(studyApi, () => useLearning().refresh())
export function useStudy() {
  return state
}
