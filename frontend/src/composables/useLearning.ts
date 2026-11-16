import { computed, ref } from 'vue'
import { ApiBase } from '@/utils/api-base'
import type { LearningMap } from '@/types'

const curriculum = ref<LearningMap | null>(null)
const loading = ref(false)
const progressBusy = ref(false)
const error = ref('')
const learned = computed(() => [
  ...new Set(
    (curriculum.value?.nodes ?? [])
      .filter((node) => node.manual && node.status === 'done')
      .map((node) => String(node.id)),
  ),
])
let loaded = false
let generation = 0
let loadSequence = 0
let progressQueue: Promise<unknown> = Promise.resolve()

async function read(response: Response): Promise<LearningMap> {
  const value = (await response.json()) as LearningMap & { error?: string }
  if (!response.ok) throw new Error(value.error || '参考路线加载失败。')
  return value
}

async function load(force = false): Promise<void> {
  if (loaded && !force && curriculum.value) return
  loading.value = true
  error.value = ''
  const version = generation,
    sequence = ++loadSequence
  try {
    if (progressBusy.value) await progressQueue
    if (version !== generation || sequence !== loadSequence) return
    const value = await read(await ApiBase.request('/api/agent/learning'))
    if (version !== generation || sequence !== loadSequence) return
    curriculum.value = value
    loaded = true
  } catch (problem) {
    if (version === generation && sequence === loadSequence)
      error.value = (problem as Error).message
  } finally {
    if (version === generation && sequence === loadSequence) loading.value = false
  }
}

function updateProgress(path: string, body: Record<string, unknown>): Promise<boolean> {
  const version = generation
  ++loadSequence
  loading.value = false
  progressBusy.value = true
  const pending = progressQueue.then(async () => {
    if (version !== generation) return false
    error.value = ''
    try {
      const value = await read(await ApiBase.json(path, body))
      if (version !== generation) return false
      ++loadSequence
      loading.value = false
      curriculum.value = value
      return true
    } catch (problem) {
      if (version === generation) error.value = (problem as Error).message
      return false
    }
  })
  progressQueue = pending
  void pending.finally(() => {
    if (version === generation && progressQueue === pending) progressBusy.value = false
  })
  return pending
}

export function useLearning() {
  return {
    curriculum,
    learned,
    loading,
    progressBusy,
    error,
    load,
    reset() {
      generation++
      loadSequence++
      loaded = false
      curriculum.value = null
      loading.value = false
      progressBusy.value = false
      progressQueue = Promise.resolve()
      error.value = ''
    },
    setStudying: (key: string, active: boolean) =>
      updateProgress('/api/agent/learning/studying', { key, active }),
    setDone: (key: string, done: boolean) =>
      updateProgress('/api/agent/learning/progress', { key, done }),
    resetProgress: () => updateProgress('/api/agent/learning/progress', { reset: true }),
    async refresh() {
      loaded = false
      await load(true)
    },
  }
}
