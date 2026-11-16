import { env, pipeline } from '@huggingface/transformers'

import { METHOD_EMBEDDINGS } from '@/data/method-embeddings'
import { latestRequestQueue } from '@/utils/latest-request-queue'
import { normalizeQuery } from '@/utils/method-search'

env.allowRemoteModels = false
env.allowLocalModels = true
env.localModelPath = '/models/'

const RUNTIME = '/ort/ort-wasm-simd-threaded.asyncify.mjs'
const BINARY = '/ort/ort-wasm-simd-threaded.asyncify.wasm'

type Extractor = Awaited<ReturnType<typeof pipeline<'feature-extraction'>>>

let extractor: Extractor | null = null
let checked: Promise<void> | null = null

async function present(url: string, type: string, method = 'GET'): Promise<boolean> {
  try {
    const response = await fetch(url, { cache: 'no-store', method })
    const contentType = response.headers.get('content-type') || ''
    if (!response.ok || contentType.includes('text/html')) return false
    return type === 'any' || contentType.includes(type)
  } catch {
    return false
  }
}

async function runtimePaths(): Promise<{ mjs: string; wasm: string }> {
  const source = await (await fetch(RUNTIME)).text()
  const blob = URL.createObjectURL(new Blob([source], { type: 'text/javascript' }))
  return { mjs: blob, wasm: BINARY }
}

async function ready(): Promise<Extractor> {
  if (extractor) return extractor
  // Vite's SPA fallback answers missing assets with index.html, which transformers
  // would then try to JSON.parse. Probe first and fail with a plain "not installed".
  checked ??= (async () => {
    const base = `/models/${METHOD_EMBEDDINGS.model}`
    const [hasConfig, hasTokenizer, hasRuntime, hasWeight] = await Promise.all([
      present(`${base}/config.json`, 'json', 'HEAD'),
      present(`${base}/tokenizer.json`, 'json', 'HEAD'),
      present(RUNTIME, 'javascript', 'HEAD'),
      present(`${base}/onnx/model_quantized.onnx`, 'any', 'HEAD'),
    ])
    if (!hasConfig || !hasTokenizer || !hasRuntime || !hasWeight)
      throw new Error('语义检索资源未安装')
  })()
  await checked
  if (env.backends?.onnx?.wasm) {
    env.backends.onnx.wasm.numThreads = 1
    env.backends.onnx.wasm.wasmPaths = await runtimePaths()
  }
  extractor = await pipeline('feature-extraction', METHOD_EMBEDDINGS.model, { dtype: 'q8' })
  return extractor
}

interface Request {
  id: number
  action: string
  query?: string
  limit?: number
  documents?: Array<{ id: string; text: string }>
}

async function handle({ action, query, limit, documents }: Request) {
  try {
    if (action === 'warm') {
      await ready()
      return { ok: true, result: true }
    }
    if (action === 'search') {
      const indexed = new Map(
        METHOD_EMBEDDINGS.ids.map((id, index) => [id, METHOD_EMBEDDINGS.documents[index]]),
      )
      if (
        !documents ||
        documents.length !== indexed.size ||
        documents.some((item) => indexed.get(item.id) !== item.text)
      ) {
        throw new Error('卡片搜索资料已变化，语义索引待更新；已保留当前描述匹配。')
      }
      const model = await ready()
      const output = await model([query ?? ''], { pooling: 'mean', normalize: true })
      const needle = (output.tolist() as number[][])[0] ?? []
      const scored = METHOD_EMBEDDINGS.vectors.map((vector, position) => {
        let dot = 0
        const width = Math.min(vector.length, needle.length)
        for (let index = 0; index < width; index++) {
          dot += (vector[index] ?? 0) * (needle[index] ?? 0)
        }
        return { id: METHOD_EMBEDDINGS.ids[position] ?? '', score: dot }
      })
      scored.sort((left, right) => right.score - left.score)
      return { ok: true, result: scored.slice(0, limit ?? 10) }
    }
    return { ok: false, error: `未知动作：${action}` }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) }
  }
}

const enqueue = latestRequestQueue<Request, Awaited<ReturnType<typeof handle>>>(
  (request) =>
    JSON.stringify([
      request.action,
      normalizeQuery(request.query ?? ''),
      request.limit,
      request.documents,
    ]),
  handle,
  (request, response) => self.postMessage({ id: request.id, ...response }),
  (request) => self.postMessage({ id: request.id, ok: false, error: '已跳过过期的查询。' }),
)
self.onmessage = (event: MessageEvent<Request>) => enqueue(event.data)
