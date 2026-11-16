import { computed, ref } from 'vue'
import type { MethodGraph } from '@/types'
import {
  normalizeQuery,
  searchDescriptions,
  searchGuidance,
  searchVersion,
  supplementDescriptions,
  type SearchHit,
} from '@/utils/method-search'
import { embeddingProfile } from '@/utils/method-search-corpus'
import { latestRequestQueue } from '@/utils/latest-request-queue'
import { isRecord } from '@/utils/records'

export type { SearchHit } from '@/utils/method-search'
type Status = 'idle' | 'ready' | 'failed'
const status = ref<Status>('idle'),
  failure = ref(''),
  query = ref(''),
  hits = ref<SearchHit[]>([])
const running = ref(false),
  submittedQuery = ref(''),
  catalogueCount = ref(0)
let worker: Worker | null = null,
  sequence = 0,
  searchSequence = 0,
  warming: Promise<void> | null = null
let warmFailure = ''
let semanticDisabled = false
const cache = new Map<string, SearchHit[]>()
const inFlight = new Map<string, Promise<Array<{ id: string; score: number }>>>()
const pending = new Map<
  number,
  {
    resolve: (value: unknown) => void
    reject: (error: Error) => void
    timer: ReturnType<typeof setTimeout>
  }
>()
type SemanticResult = Array<{ id: string; score: number }>
function isSemanticResult(value: unknown): value is SemanticResult {
  return (
    Array.isArray(value) &&
    value.every(
      (item) =>
        isRecord(item) &&
        typeof item.id === 'string' &&
        typeof item.score === 'number' &&
        Number.isFinite(item.score),
    )
  )
}
type SemanticJob = {
  id: number
  key: string
  payload: Record<string, unknown>
  resolve: (value: SemanticResult) => void
  reject: (error: Error) => void
}
let jobSequence = 0
// Main-thread backpressure also works while ONNX blocks the worker's message loop.
const enqueue = latestRequestQueue<SemanticJob, { found: SemanticResult } | { error: Error }>(
  (job) => job.key,
  async (job) => {
    try {
      return { found: await call('search', job.payload, isSemanticResult) }
    } catch (problem) {
      return { error: problem instanceof Error ? problem : new Error(String(problem)) }
    }
  },
  (job, result) => {
    if ('found' in result) job.resolve(result.found)
    else job.reject(result.error)
  },
  (job) => {
    inFlight.delete(job.key)
    job.reject(new Error('已跳过过期的查询。'))
  },
)

function call<T>(
  action: 'warm' | 'search',
  payload: Record<string, unknown>,
  accepts: (value: unknown) => value is T,
): Promise<T> {
  const id = ++sequence
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () => {
        pending.delete(id)
        reject(new Error('语义补充超时，已保留描述匹配结果。'))
      },
      action === 'warm' ? 120000 : 30000,
    )
    pending.set(id, {
      resolve: (value) => {
        if (accepts(value)) resolve(value)
        else reject(new Error('语义补充响应无效，已保留描述匹配结果。'))
      },
      reject,
      timer,
    })
    try {
      worker!.postMessage({ id, action, ...payload })
    } catch (problem) {
      clearTimeout(timer)
      pending.delete(id)
      reject(problem)
    }
  })
}

function boot(): Worker {
  if (worker) return worker
  worker = new Worker(new URL('../models/method-search.worker.ts', import.meta.url), {
    type: 'module',
  })
  const current = worker
  worker.onmessage = (event: MessageEvent<unknown>) => {
    const data = event.data
    if (!isRecord(data) || typeof data.id !== 'number') return
    const entry = pending.get(data.id)
    if (!entry) return
    clearTimeout(entry.timer)
    pending.delete(data.id)
    if (data.ok === true) entry.resolve(data.result)
    else if (data.ok === false)
      entry.reject(new Error(typeof data.error === 'string' ? data.error : '语义补充失败。'))
    else entry.reject(new Error('语义补充响应无效，已保留描述匹配结果。'))
  }
  worker.onerror = (event) => {
    if (worker !== current) return
    status.value = 'failed'
    warmFailure = event.message || '端侧模型加载失败。'
    for (const entry of pending.values()) {
      clearTimeout(entry.timer)
      entry.reject(new Error(warmFailure))
    }
    pending.clear()
    current.terminate()
    worker = null
  }
  return worker
}

async function warm(): Promise<void> {
  if (status.value === 'ready' || semanticDisabled) return
  if (warming) return warming
  warming = Promise.resolve()
    .then(async () => {
      boot()
      await call('warm', {}, (value): value is boolean => typeof value === 'boolean')
      status.value = 'ready'
      warmFailure = ''
    })
    .catch((problem) => {
      status.value = 'failed'
      warmFailure = problem instanceof Error ? problem.message : String(problem)
      // Semantic matching is an optional enhancement: never surface its internal
      // loading errors (e.g. an asset answered with index.html). Text matching stays.
      semanticDisabled = true
      console.warn('[method-search] semantic model unavailable:', warmFailure)
    })
    .finally(() => {
      warming = null
    })
  return warming
}

async function run(graph: MethodGraph | null): Promise<void> {
  const request = ++searchSequence,
    text = query.value.trim()
  if (!text || !graph) {
    enqueue.discardQueued()
    hits.value = []
    running.value = false
    return
  }
  catalogueCount.value = graph.cards.length
  submittedQuery.value = text
  failure.value = ''
  const version = searchVersion(graph.cards),
    key = `${normalizeQuery(text)}\n${version}`,
    saved = cache.get(key)
  enqueue.discardQueued(key)
  const initial = saved ? [...saved] : searchDescriptions(graph.cards, text, 8)
  hits.value = initial
  running.value = false
  if (saved || hits.value[0]?.exact) return
  running.value = true
  try {
    if (status.value !== 'ready') await warm()
    if (request !== searchSequence || semanticDisabled) return
    if (status.value !== 'ready') throw new Error(warmFailure || '语义模型不可用。')
    let inference = inFlight.get(key)
    if (!inference) {
      inference = new Promise<SemanticResult>((resolve, reject) =>
        enqueue({
          id: ++jobSequence,
          key,
          payload: {
            query: text,
            limit: 12,
            documents: graph.cards.map((card) => ({ id: card.id, text: embeddingProfile(card) })),
          },
          resolve,
          reject,
        }),
      )
      inFlight.set(key, inference)
      // Delete only this request; an older timeout must not evict a newer retry.
      void inference
        .finally(() => {
          if (inFlight.get(key) === inference) inFlight.delete(key)
        })
        .catch(() => {})
    }
    const found = await inference
    if (request !== searchSequence) return
    hits.value = supplementDescriptions(initial, found, graph.cards)
    cache.set(key, [...hits.value])
    if (cache.size > 40) cache.delete(cache.keys().next().value!)
  } catch (problem) {
    if (request === searchSequence) {
      // Text hits are already displayed; a failed semantic supplement must not
      // replace them with a raw loader error (which may contain HTML/JSON text).
      semanticDisabled = true
      console.warn(
        '[method-search] semantic supplement failed:',
        problem instanceof Error ? problem.message : String(problem),
      )
    }
  } finally {
    if (request === searchSequence) running.value = false
  }
}

function clear(): void {
  searchSequence++
  enqueue.discardQueued()
  query.value = ''
  submittedQuery.value = ''
  hits.value = []
  failure.value = ''
  running.value = false
}

export function useMethodSearch() {
  return {
    status,
    failure,
    query,
    submittedQuery,
    hits,
    running,
    warm,
    run,
    clear,
    guidance: computed(() => searchGuidance(submittedQuery.value)),
    count: computed(() => catalogueCount.value),
  }
}
