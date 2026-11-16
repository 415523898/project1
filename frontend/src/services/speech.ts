import { readableError } from '@/services/agent'
import { ApiBase } from '@/utils/api-base'

export interface SpeechStatus {
  available: boolean
  model: string | null
  size_mb: number
  dir: string
}

export async function speechStatus(): Promise<SpeechStatus> {
  const response = await ApiBase.request('/api/speech/status')
  if (!response.ok) throw new Error(await readableError(response))
  return (await response.json()) as SpeechStatus
}

export async function transcribe(blob: Blob, signal?: AbortSignal): Promise<string> {
  const abort = new AbortController()
  const cancel = () => abort.abort()
  signal?.addEventListener('abort', cancel, { once: true })
  if (signal?.aborted) abort.abort()
  const timeout = window.setTimeout(
    () => abort.abort(new Error('语音识别超时，请稍后重试。')),
    90_000,
  )
  try {
    const response = await ApiBase.request('/api/speech/transcribe', {
      method: 'POST',
      headers: { 'Content-Type': 'audio/wav' },
      body: blob,
      signal: abort.signal,
    })
    if (!response.ok) throw new Error(await readableError(response))
    const data = (await response.json()) as { text?: string; error?: string }
    if (data.error) throw new Error(data.error)
    return data.text ?? ''
  } catch (problem) {
    if (signal?.aborted) throw problem
    if (abort.signal.aborted) throw new Error('语音识别超时，请稍后重试。', { cause: problem })
    if (problem instanceof TypeError)
      throw new Error('语音识别请求未能连接服务器，请检查网络后重试。', { cause: problem })
    throw problem
  } finally {
    window.clearTimeout(timeout)
    signal?.removeEventListener('abort', cancel)
  }
}
