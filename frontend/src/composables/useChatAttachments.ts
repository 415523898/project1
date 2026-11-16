import { computed, onScopeDispose, ref, watch } from 'vue'
import type { ChatAttachment } from '@/types'
import { toWav } from '@/services/audio'
import {
  attachmentKind,
  isAudio,
  uploadAttachment,
} from '@/services/attachments'

export type DraftAttachment = ChatAttachment & {
  source: File
  state: 'queued' | 'preparing' | 'uploading' | 'ready' | 'error'
  error: string
}

const ALLOWED_SUFFIXES = new Set([
  '.csv',
  '.tsv',
  '.txt',
  '.md',
  '.markdown',
  '.xlsx',
  '.xls',
  '.xlsm',
  '.pdf',
  '.docx',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
  '.wav',
  '.mp3',
  '.m4a',
  '.aac',
  '.ogg',
  '.opus',
  '.flac',
  '.webm',
])

function suffixOf(name: string): string {
  const index = name.lastIndexOf('.')
  return index >= 0 ? name.slice(index).toLowerCase() : ''
}

interface ComposerScope {
  owner: string
  session: string | null
  version: number
}
interface AttachmentOwner {
  scope(): ComposerScope
  ensureSession(): Promise<string | null>
}

export function toMessageAttachment(item: DraftAttachment): ChatAttachment {
  const file: ChatAttachment & Partial<Pick<DraftAttachment, 'source' | 'state' | 'error'>> = {
    ...item,
  }
  delete file.source
  delete file.state
  delete file.error
  return file
}

// One instance per ChatView mount; its refs are consumed directly by the view.
export function useChatAttachments({ scope, ensureSession }: AttachmentOwner) {
  let disposed = false
  const requests = new Map<string, AbortController>()
  const cancelAll = () => {
    for (const request of requests.values()) request.abort()
    requests.clear()
  }
  onScopeDispose(() => {
    disposed = true
    cancelAll()
  })
  watch(() => [scope().owner, scope().session], cancelAll, { flush: 'sync' })
  const attachments = ref<DraftAttachment[]>([])
  watch(
    () => attachments.value.map((item) => item.id),
    (ids) => {
      for (const [id, request] of requests) if (!ids.includes(id)) request.abort()
    },
    { flush: 'sync' },
  )
  const preparing = computed(() =>
    attachments.value.some((item) => ['queued', 'preparing', 'uploading'].includes(item.state)),
  )
  function attachmentIssue(file: File, existing: DraftAttachment[], retryId?: string): string {
    if (!file.size) return '文件为空，请重新选择。'
    if (!ALLOWED_SUFFIXES.has(suffixOf(file.name)))
      return '不支持该文件类型，请选择表格、文本、PDF、Word、图片或音频文件。'
    const active = existing.filter((item) => item.id !== retryId && item.state !== 'error')
    if (
      active.some(
        (item) =>
          item.source.name === file.name &&
          item.source.size === file.size &&
          item.source.lastModified === file.lastModified,
      )
    )
      return '本轮已经选择了相同文件，移除重复项后发送。'
    return ''
  }
  async function prepareAttachment(item: DraftAttachment): Promise<void> {
    if (disposed) return
    const version = scope().version
    const controller = new AbortController()
    requests.set(item.id, controller)
    const current = () =>
      !disposed &&
      !controller.signal.aborted &&
      version === scope().version &&
      attachments.value.some((file) => file.id === item.id)
    item.error = ''
    item.state = 'uploading'
    let wav: Blob | undefined, audioError: string | undefined
    try {
      if (isAudio(item.source)) {
        item.state = 'preparing'
        try {
          wav = await toWav(item.source)
        } catch (problem) {
          audioError = (problem as Error).message
        }
        if (!current()) return
        item.state = 'uploading'
      }
      const record = await uploadAttachment(
        item.source,
        item.session_id,
        item.id,
        wav,
        audioError,
        controller.signal,
      )
      if (!current()) return
      Object.assign(item, record, { state: 'ready', error: '' })
    } catch (problem) {
      if (current()) {
        item.state = 'error'
        item.error = (problem as Error).message
      }
    } finally {
      if (requests.get(item.id) === controller) requests.delete(item.id)
    }
  }
  async function retryAttachment(item: DraftAttachment): Promise<void> {
    if (['queued', 'preparing', 'uploading'].includes(item.state)) return
    const issue = attachmentIssue(item.source, attachments.value, item.id)
    if (issue) {
      item.state = 'error'
      item.error = issue
      return
    }
    await prepareAttachment(item)
  }
  async function uploadFiles(chosen: File[]): Promise<void> {
    if (disposed || !chosen.length) return
    let session: string | null = null,
      issue = ''
    const owner = scope().owner,
      version = scope().version
    try {
      session = await ensureSession()
    } catch (problem) {
      issue = (problem as Error).message
    }
    if (
      disposed ||
      owner !== scope().owner ||
      (session && session !== scope().session) ||
      (!session && version !== scope().version)
    )
      return
    const queued: string[] = []
    for (const source of chosen) {
      const error = issue || attachmentIssue(source, attachments.value)
      const item: DraftAttachment = {
        id: crypto.randomUUID().replace(/-/g, ''),
        session_id: session ?? '',
        source,
        name: source.name,
        size: source.size,
        mime: source.type,
        kind: attachmentKind(source),
        read_status: 'unreadable',
        note: '',
        truncated: false,
        state: error ? 'error' : 'queued',
        error,
      }
      attachments.value.push(item)
      if (!error) queued.push(item.id)
    }
    for (const id of queued) {
      const item = attachments.value.find((file) => file.id === id)
      if (item) await prepareAttachment(item)
    }
  }

  const messageAttachments = () => attachments.value.map(toMessageAttachment)
  return { attachments, preparing, retryAttachment, uploadFiles, messageAttachments }
}
