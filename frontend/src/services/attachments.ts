import { ApiBase } from '@/utils/api-base'
import { readableError } from '@/services/agent'
import type { ChatAttachment } from '@/types'
import { isRecord } from '@/utils/records'

export const isAudio = (file: File) => /\.(wav|mp3|m4a|aac|ogg|opus|flac|webm)$/i.test(file.name)
function isChatAttachment(value: unknown): value is ChatAttachment {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.session_id === 'string' &&
    typeof value.name === 'string' &&
    typeof value.mime === 'string' &&
    typeof value.size === 'number' &&
    Number.isSafeInteger(value.size) &&
    value.size >= 0 &&
    typeof value.kind === 'string' &&
    ['image', 'audio', 'document', 'table', 'file'].includes(value.kind) &&
    typeof value.read_status === 'string' &&
    ['text', 'image', 'unreadable', 'error'].includes(value.read_status) &&
    typeof value.note === 'string' &&
    typeof value.truncated === 'boolean'
  )
}
export function attachmentKind(file: File): ChatAttachment['kind'] {
  if (/\.(png|jpe?g|webp|gif)$/i.test(file.name)) return 'image'
  if (isAudio(file)) return 'audio'
  if (/\.(csv|tsv|xlsx|xls|xlsm)$/i.test(file.name)) return 'table'
  return /\.(pdf|docx|txt|md|markdown)$/i.test(file.name) ? 'document' : 'file'
}

export async function uploadAttachment(
  file: File,
  session: string,
  id: string,
  wav?: Blob,
  audioError?: string,
  signal?: AbortSignal,
): Promise<ChatAttachment> {
  const body = new FormData()
  body.append('file', file)
  body.append('session', session)
  body.append('id', id)
  if (wav) body.append('wav', wav, 'transcription.wav')
  if (audioError) body.append('audio_error', audioError)
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 120_000)
  const cancel = () => {
    window.clearTimeout(timeout)
    controller.abort()
  }
  if (signal?.aborted) cancel()
  else signal?.addEventListener('abort', cancel, { once: true })
  try {
    const response = await ApiBase.request('/api/attachments', {
      method: 'POST',
      body,
      signal: controller.signal,
    })
    if (!response.ok) throw new Error(await readableError(response))
    const data: unknown = await response.json()
    if (!isChatAttachment(data) || data.id !== id || data.session_id !== session)
      throw new Error('附件响应无效，请重试上传。')
    return data
  } catch (problem) {
    if (signal?.aborted) throw problem
    if (controller.signal.aborted) throw new Error('附件处理超时，可以重试。', { cause: problem })
    if (problem instanceof TypeError)
      throw new Error('附件上传未能连接服务器，可以重试。', { cause: problem })
    throw problem
  } finally {
    signal?.removeEventListener('abort', cancel)
    window.clearTimeout(timeout)
  }
}

export function attachmentUrl(
  file: ChatAttachment,
  action: 'download' | 'preview' | 'text' = 'download',
  message?: string,
): string {
  const path = `/api/attachments/${encodeURIComponent(file.session_id)}/${encodeURIComponent(file.id)}/${action}`
  return ApiBase.url(path + (message ? `?message=${encodeURIComponent(message)}` : ''))
}
