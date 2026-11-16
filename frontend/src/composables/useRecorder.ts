import { computed, ref } from 'vue'

import { toWav } from '@/services/audio'

const MAX_SECONDS = 60
const TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']

function supportedType(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined
  if (typeof MediaRecorder.isTypeSupported !== 'function') return undefined
  return TYPES.find((type) => MediaRecorder.isTypeSupported(type))
}

export function recordingBlocked(): string | null {
  const local = ['127.0.0.1', 'localhost', '::1'].includes(location.hostname)
  if (!navigator.mediaDevices?.getUserMedia) {
    if (!window.isSecureContext && !local) {
      return (
        `当前地址（${location.origin}）拿不到麦克风：浏览器只在 https 或本机地址下提供。` +
        '手机请使用服务器的 HTTPS 入口，或用回形针上传音频文件。'
      )
    }
    return '这个浏览器没有提供麦克风接口，可以用回形针上传音频文件转文字。'
  }
  if (typeof MediaRecorder === 'undefined') {
    return '这个浏览器没有 MediaRecorder，无法录音；可以用回形针上传音频文件转文字。'
  }
  return null
}

export function useRecorder(
  options: {
    onRecorded?: (wav: Blob, signal: AbortSignal) => Promise<void>
    onError?: (error: Error) => void
  } = {},
) {
  const recording = ref(false)
  const transcribing = ref(false)
  const phase = ref<
    | 'idle'
    | 'requesting'
    | 'recording'
    | 'stopping'
    | 'converting'
    | 'transcribing'
    | 'success'
    | 'error'
  >('idle')
  const diagnostic = ref({ mime: '', seconds: 0, bytes: 0, wavBytes: 0, error: '' })
  const busy = computed(() =>
    ['requesting', 'recording', 'stopping', 'converting', 'transcribing'].includes(phase.value),
  )
  const seconds = ref(0)
  let recorder: MediaRecorder | null = null
  let stream: MediaStream | null = null
  let chunks: Blob[] = []
  let timer: number | undefined
  let revision = 0
  let stopped: Promise<Blob> | null = null
  let processing: Promise<Blob | null> | null = null
  let controller: AbortController | null = null

  function release(): void {
    if (timer !== undefined) window.clearInterval(timer)
    timer = undefined
    for (const track of stream?.getTracks() ?? []) track.stop()
    stream = null
    recorder = null
    chunks = []
    recording.value = false
  }

  async function start(): Promise<void> {
    if (busy.value) return
    const blocked = recordingBlocked()
    if (blocked) throw new Error(blocked)
    const current = ++revision
    phase.value = 'requesting'
    diagnostic.value = { mime: '', seconds: 0, bytes: 0, wavBytes: 0, error: '' }
    try {
      const captured = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      })
      if (current !== revision) {
        captured.getTracks().forEach((track) => track.stop())
        return
      }
      stream = captured
      const type = supportedType()
      const instance = type
        ? new MediaRecorder(captured, { mimeType: type })
        : new MediaRecorder(captured)
      chunks = []
      instance.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data)
      }
      // Register before start so a natural stop still resolves the same promise.
      stopped = new Promise<Blob>((resolve, reject) => {
        instance.onstop = () => resolve(new Blob(chunks, { type: instance.mimeType || type || 'audio/webm' }))
        instance.onerror = () => reject(new Error('浏览器录音失败，请重试或上传音频。'))
      })
      recorder = instance
      instance.start()
      recording.value = true
      phase.value = 'recording'
      diagnostic.value.mime = instance.mimeType || type || '浏览器默认'
      seconds.value = 0
      const began = Date.now()
      timer = window.setInterval(() => {
        seconds.value = Math.min(MAX_SECONDS, Math.floor((Date.now() - began) / 1000))
        if (seconds.value >= MAX_SECONDS) void finish().catch(() => {})
      }, 250)
    } catch (problem) {
      if (current !== revision) return
      release()
      phase.value = 'error'
      const error = problem instanceof Error ? problem : new Error(String(problem))
      const reason =
        error.name === 'NotAllowedError'
          ? '麦克风权限被拒绝，请在浏览器站点权限中允许录音后重试。'
          : error.name === 'NotFoundError'
            ? '没有找到可用麦克风。'
            : error.name === 'NotReadableError'
              ? '麦克风正被占用或无法读取，请关闭其他录音后重试。'
              : error.message
      diagnostic.value.error = reason
      throw new Error(reason, { cause: problem })
    }
  }

  function finish(): Promise<Blob | null> {
    if (processing) return processing
    const instance = recorder
    const done = stopped
    if (!instance || !done) {
      release()
      return Promise.resolve(null)
    }
    const current = revision
    const abort = new AbortController()
    controller = abort
    diagnostic.value.seconds = seconds.value
    if (timer !== undefined) window.clearInterval(timer)
    timer = undefined
    recording.value = false
    phase.value = 'stopping'
    transcribing.value = true
    processing = Promise.resolve()
      .then(async () => {
        try {
          if (instance.state !== 'inactive') instance.stop()
          const raw = await done
          if (current !== revision) return null
          release()
          diagnostic.value.bytes = raw.size
          if (!raw.size) throw new Error('没有录到声音，请确认麦克风后重试。')
          phase.value = 'converting'
          const wav = await toWav(raw)
          if (current !== revision) return null
          diagnostic.value.wavBytes = wav.size
          phase.value = 'transcribing'
          await options.onRecorded?.(wav, abort.signal)
          if (current !== revision) return null
          phase.value = 'success'
          return wav
        } catch (problem) {
          if (current !== revision) return null
          phase.value = 'error'
          diagnostic.value.error = (problem as Error).message
          options.onError?.(problem as Error)
          throw problem
        } finally {
          if (current === revision) {
            release()
            transcribing.value = false
            processing = null
            controller = null
            stopped = null
          }
        }
      })
    return processing
  }

  function cancel(): void {
    ++revision
    controller?.abort()
    controller = null
    try {
      if (recorder?.state !== 'inactive') recorder?.stop()
    } catch {
      void 0
    }
    release()
    processing = null
    stopped = null
    transcribing.value = false
    phase.value = 'idle'
  }

  return {
    recording,
    transcribing,
    busy,
    phase,
    diagnostic,
    seconds,
    start,
    finish,
    cancel,
    maxSeconds: MAX_SECONDS,
  }
}
