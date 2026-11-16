import { computed, onScopeDispose, reactive, ref } from 'vue'
import { ApiBase } from '@/utils/api-base'
import { readableError } from '@/services/agent'
import { changeExperiment, loadExperimentSidebar } from '@/services/experiment-sidebar'
import { explanationInput } from '@/services/result-explanation'
import { experimentRows } from '@/utils/result-summary'
import type {
  ChatTurn,
  ToolTrace,
  ExperimentResult,
  ExperimentSidebar,
  SidebarExperiment,
} from '@/types'
import type { LabState, StatusTone } from './state'

export interface ResultBlock {
  experiment?: SidebarExperiment
  key: string
  identity: string
  turn: ChatTurn
  tool: ToolTrace | null
  panel: number
  title: string
  result: ExperimentResult
  kind: 'tool' | 'experiment'
}

const EXPERIMENT_TOOL = 'run_ml_suite'

type ExperimentState = Pick<LabState, 'user' | 'sessionId' | 'turns'>

export function createExperimentState(
  state: ExperimentState,
  setStatus: (text: string, tone?: StatusTone) => void,
  captureAccount: () => { owner: string; current(): boolean },
) {
  let disposed = false
  const requests = new AbortController()
  onScopeDispose(() => {
    disposed = true
    requests.abort()
    sidebarPending.clear()
  })
  const blocks = ref<ResultBlock[]>([])
  const selectedKey = ref<string | null>(null)
  const sidebarStates = reactive(new Map<string, ExperimentSidebar>())
  const sidebarPending = reactive(new Set<string>())
  const sidebarSaving = computed(() => sidebarPending.has(sidebarScope()))
  const sidebarWrites = new Map<string, Promise<void>>()
  const sidebarTickets = new Map<string, number>()
  const checkedExplanations = new Set<string>()
  let visibilityScope = ''
  let hiddenResults = new Set<string>()
  const sidebarScope = (id = state.sessionId, owner = state.user) => JSON.stringify([owner, id])
  const currentSidebar = () => sidebarStates.get(sidebarScope())

  function adoptSidebar(
    value: ExperimentSidebar | undefined,
    id = state.sessionId,
    owner = state.user,
  ): void {
    if (disposed || !value || !Array.isArray(value.experiments)) return
    sidebarStates.set(sidebarScope(id, owner), value)
    if (id === state.sessionId && owner === state.user) indexBlocks()
  }

  async function refreshSidebar(id = state.sessionId, owner = state.user): Promise<void> {
    if (disposed || !id || !owner) return
    const account = captureAccount()
    try {
      const value = await loadExperimentSidebar(id)
      if (disposed || !account.current()) return
      adoptSidebar(value, id, owner)
    } catch {
      // The sidebar is auxiliary: a failed refresh must not affect the turn.
    }
  }

  function acceptExperimentResult(
    result: ExperimentResult,
    id = state.sessionId,
    owner = state.user,
  ): void {
    if (disposed || !result.experiment_id || !result.experiment_version) return
    const scope = sidebarScope(id, owner)
    const value = sidebarStates.get(scope) ?? {
      schema: 1,
      revision: 0,
      selected_id: null,
      experiments: [],
    }
    let item = value.experiments.find((item) => item.id === result.experiment_id)
    if (!item) {
      item = {
        id: result.experiment_id,
        number: result.experiment_number ?? value.experiments.length + 1,
        title: result.title ?? '',
        source_key: result.experiment_id,
        active_version: result.experiment_version,
        versions: [],
      }
      value.experiments.push(item)
    }
    if (!item.versions.some((version) => version.version === result.experiment_version)) {
      item.versions.push({
        version: result.experiment_version,
        created_at: new Date().toISOString(),
        result,
        explanations: {},
      })
    }
    item.active_version = result.experiment_version
    value.selected_id = item.id
    sidebarStates.set(scope, value)
    if (id === state.sessionId && owner === state.user) {
      selectedKey.value = item.id
      indexBlocks()
    }
  }

  function writeSidebar(
    action: 'select' | 'delete' | 'version',
    identifier: string,
    version?: number,
  ): void {
    if (disposed) return
    const id = state.sessionId,
      owner = state.user
    const account = captureAccount()
    if (!id) return
    const scope = sidebarScope(id, owner),
      ticket = (sidebarTickets.get(scope) ?? 0) + 1
    sidebarTickets.set(scope, ticket)
    sidebarPending.add(scope)
    const write = (sidebarWrites.get(scope) ?? Promise.resolve())
      .catch(() => undefined)
      .then(async () => {
        if (disposed || !account.current()) return
        const value = await changeExperiment(id, action, identifier, version, requests.signal)
        if (disposed || !account.current()) return
        if (sidebarTickets.get(scope) === ticket) adoptSidebar(value, id, owner)
      })
      .finally(() => {
        if (sidebarTickets.get(scope) === ticket) sidebarPending.delete(scope)
      })
    sidebarWrites.set(scope, write)
    void write.catch((error) => {
      if (!disposed && account.current() && sidebarScope() === scope)
        setStatus(`实验状态保存失败，请重试：${(error as Error).message}`, 'error')
    })
  }

  function switchExperimentVersion(key: string, delta: number): void {
    const block = blocks.value.find((item) => item.key === key),
      item = block?.experiment
    if (!item || sidebarSaving.value) return
    const index = item.versions.findIndex((version) => version.version === item.active_version)
    const next = item.versions[index + delta]
    if (next) writeSidebar('version', item.id, next.version)
  }

  async function revealExperimentVersion(identifier: string, version: number): Promise<void> {
    if (!state.sessionId || !Number.isInteger(version) || version < 1) return
    writeSidebar('select', identifier)
    writeSidebar('version', identifier, version)
    await sidebarWrites.get(sidebarScope())
  }

  async function syncSavedExplanations(id: string, owner: string): Promise<void> {
    const account = captureAccount()
    if (disposed || !account.current() || account.owner !== owner) return
    const sidebar = sidebarStates.get(sidebarScope(id, owner))
    const inputs = (sidebar?.experiments ?? [])
      .filter((item) => !item.deleted)
      .flatMap((item) => {
        const version = item.versions.find((value) => value.version === item.active_version)
        if (!version) return []
        return experimentRows(version.result)
          .filter((row) => row.status === 'success' && row.entry && !version.explanations[row.id])
          .map((row) => explanationInput(version.result, row.id, row.entry!, id, row.label))
      })
    let next = 0
    await Promise.all(
      Array.from({ length: Math.min(4, inputs.length) }, async () => {
        while (next < inputs.length) {
          if (disposed || !account.current()) return
          const input = inputs[next++]!
          const key = JSON.stringify([owner, input])
          if (checkedExplanations.has(key)) continue
          const response = await ApiBase.json(
            '/api/experiments/explain/saved',
            input,
            requests.signal,
          )
          if (!response.ok) throw new Error(await readableError(response))
          if (disposed || !account.current()) return
          checkedExplanations.add(key)
        }
      }),
    )
  }

  function syncResultVisibility(): void {
    const scope = `forest-hidden-result-panels-v1:${JSON.stringify([state.user, state.sessionId])}`
    if (scope === visibilityScope) return
    visibilityScope = scope
    hiddenResults = new Set()
    if (!state.sessionId) return
    try {
      const values: unknown = JSON.parse(localStorage.getItem(scope) ?? '[]')
      if (Array.isArray(values))
        hiddenResults = new Set(
          values.filter((value): value is string => typeof value === 'string'),
        )
    } catch {
      /* Browser preferences are optional; experiment evidence stays in the conversation. */
    }
  }

  function indexBlocks(): void {
    syncResultVisibility()
    const items: ResultBlock[] = []
    state.turns.forEach((turn, turnIndex) => {
      if (turn.kind === 'experiment' && turn.result) {
        items.push({
          key: `${turnIndex}-experiment`,
          identity: `experiment:${turn.created_at ?? 'legacy'}:${turnIndex}`,
          turn,
          tool: null,
          panel: items.length + 1,
          title: turn.result.title ?? '实验结果',
          result: turn.result,
          kind: 'experiment',
        })
        return
      }
      ;(turn.tools ?? []).forEach((tool, toolIndex) => {
        if (!tool.result || tool.name !== EXPERIMENT_TOOL) return
        items.push({
          key: `${turnIndex}-${toolIndex}`,
          identity:
            tool.id && tool.id !== tool.name
              ? `tool:${tool.id}`
              : `tool:${turn.created_at ?? turnIndex}:${toolIndex}`,
          turn,
          tool,
          panel: items.length + 1,
          title: tool.result.title ?? tool.name,
          result: tool.result,
          kind: 'tool',
        })
      })
    })
    const sidebar = currentSidebar()
    const managed = sidebar
      ? sidebar.experiments
          .filter(
            (item) =>
              !item.deleted &&
              ![item.id, 'experiment:' + item.id, item.source_key, ...(item.aliases ?? [])].some(
                (key) => hiddenResults.has(key),
              ),
          )
          .map((item) => {
            const version = item.versions.find((version) => version.version === item.active_version)
            if (!version) return null
            const original = items.find(
              (block) =>
                block.result.experiment_id === item.id ||
                block.identity === item.source_key ||
                item.aliases?.includes(block.identity),
            )
            const result = version.result
            return {
              key: item.id,
              identity: 'experiment:' + item.id,
              experiment: item,
              panel: item.number,
              title: item.title,
              result,
              kind: original?.kind ?? 'experiment',
              tool: original?.tool ?? null,
              turn: original?.turn ?? {
                kind: 'experiment',
                question: item.title,
                answer: '',
                status: 'complete',
                result,
              },
            } as ResultBlock
          })
          .filter((item): item is ResultBlock => Boolean(item))
      : null
    const unmigrated = sidebar
      ? items.filter((block) => {
          const identifier = block.result.experiment_id
          if (!identifier) return false
          const known = sidebar.experiments.some((item) => item.id === identifier)
          if (known) return false
          return !hiddenResults.has(block.identity)
        })
      : []
    const visible = managed
      ? [...managed, ...unmigrated]
      : items.filter((item) => !hiddenResults.has(item.identity))
    blocks.value = visible
    if (selectedKey.value && !visible.some((item) => item.key === selectedKey.value)) {
      selectedKey.value = visible.at(-1)?.key ?? null
    }
    if (sidebar?.selected_id && visible.some((item) => item.key === sidebar.selected_id))
      selectedKey.value = sidebar.selected_id
    if (!selectedKey.value) selectedKey.value = visible.at(-1)?.key ?? null
  }

  function removeBlock(key: string): void {
    syncResultVisibility()
    const index = blocks.value.findIndex((block) => block.key === key)
    const block = blocks.value[index]
    if (!block) return
    hiddenResults.add(block.identity)
    if (selectedKey.value === key)
      selectedKey.value = (blocks.value[index + 1] ?? blocks.value[index - 1])?.key ?? null
    if (block.experiment) {
      block.experiment.deleted = true
      const sidebar = currentSidebar()
      if (sidebar) sidebar.selected_id = selectedKey.value
      writeSidebar('delete', block.experiment.id)
    }
    indexBlocks()
    if (state.sessionId) {
      try {
        localStorage.setItem(visibilityScope, JSON.stringify([...hiddenResults]))
      } catch {
        setStatus('结果卡片已移除，但浏览器无法保存这项设置。', 'error')
      }
    }
  }

  function selectBlock(key: string): void {
    if (!key) return
    selectedKey.value = key
    const item = blocks.value.find((item) => item.key === key)?.experiment
    const sidebar = currentSidebar()
    if (item && sidebar && sidebar.selected_id !== item.id) {
      sidebar.selected_id = item.id
      writeSidebar('select', item.id)
    }
  }

  function clearSelection() {
    blocks.value = []
    selectedKey.value = null
  }
  function resetView() {
    clearSelection()
    visibilityScope = ''
    hiddenResults = new Set()
  }
  function contextView() {
    return {
      selected_id: currentSidebar()?.selected_id ?? null,
      hidden_source_keys: [...hiddenResults],
      active_versions: Object.fromEntries(
        (currentSidebar()?.experiments ?? [])
          .filter((item) => !item.deleted)
          .map((item) => [item.id, item.active_version]),
      ),
    }
  }
  const flush = (id: string | null, owner: string) => sidebarWrites.get(sidebarScope(id, owner))
  return {
    blocks,
    selectedKey,
    sidebarSaving,
    adoptSidebar,
    refreshSidebar,
    acceptExperimentResult,
    switchExperimentVersion,
    revealExperimentVersion,
    syncSavedExplanations,
    syncResultVisibility,
    indexBlocks,
    removeBlock,
    selectBlock,
    sidebarScope,
    contextView,
    resetView,
    clearSelection,
    flush,
  }
}
