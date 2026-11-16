import { ApiBase } from '@/utils/api-base'
import { readableError, type ErrorContext } from '@/services/agent'
import { isRecord } from '@/utils/records'
import type { ProviderConfig } from '@/services/agent'

export interface ProviderConnection {
  answer: string
  model?: string
  elapsed_ms?: number
}

export async function testProviderConnection(
  config: ProviderConfig,
  signal: AbortSignal,
): Promise<ProviderConnection> {
  const data = await response(
    ApiBase.request('/api/ai/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
      signal,
    }),
  )
  if (!isRecord(data) || typeof data.answer !== 'string' || !data.answer)
    throw new Error('接口没有返回正文。')
  return {
    answer: data.answer,
    model: typeof data.model === 'string' ? data.model : undefined,
    elapsed_ms:
      typeof data.elapsed_ms === 'number' && Number.isFinite(data.elapsed_ms)
        ? data.elapsed_ms
        : undefined,
  }
}

export interface SavedProvider {
  id: string
  has_key: boolean
  settings: Record<string, unknown>
}
function isSavedProvider(value: unknown): value is SavedProvider {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.has_key === 'boolean' &&
    isRecord(value.settings)
  )
}
async function response(
  promise: Promise<Response>,
  context: ErrorContext = 'session',
): Promise<unknown> {
  const value = await promise
  if (!value.ok) throw new Error(await readableError(value, context))
  return value.json()
}
export const providerApi = {
  list: async (signal?: AbortSignal): Promise<{ providers: SavedProvider[] }> => {
    const data = await response(ApiBase.request('/api/providers', { signal }))
    if (!isRecord(data) || !Array.isArray(data.providers) || !data.providers.every(isSavedProvider))
      throw new Error('提供商配置响应无效，请重新读取。')
    return { providers: data.providers }
  },
  save: async (id: string, settings: unknown, key?: string): Promise<SavedProvider> => {
    const data = await response(
      ApiBase.json('/api/providers/' + encodeURIComponent(id), {
        settings,
        ...(key !== undefined ? { api_key: key } : {}),
      }),
    )
    if (!isSavedProvider(data) || data.id !== id)
      throw new Error('提供商配置响应无效，请重新读取。')
    return data
  },
  remove: (id: string) =>
    response(ApiBase.json('/api/providers/' + encodeURIComponent(id) + '/delete', {})),
  secure: (action: 'reauthenticate' | 'password' | 'logout-all', password: string, next?: string) =>
    response(
      ApiBase.json('/api/auth/' + action, { password, ...(next ? { new_password: next } : {}) }),
      'credentials',
    ),
}
