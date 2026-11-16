import { frontendConfig } from '@/config'
const STORAGE_KEY = 'forest-backend-url-v1'

function withAuth(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers)
  if (!['GET', 'HEAD', 'OPTIONS'].includes((init?.method ?? 'GET').toUpperCase()))
    headers.set('X-Forest-Request', '1')
  return { ...(init ?? {}), headers, credentials: 'include' }
}

function normalize(value: unknown): string {
  if (typeof value !== 'string') return ''
  const trimmed = value.trim().replace(/\/+$/, '')
  if (!trimmed) return ''
  try {
    const url = new URL(trimmed)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return ''
    return url.origin
  } catch {
    return ''
  }
}

function fromStorage(): string {
  try {
    return normalize(localStorage.getItem(STORAGE_KEY))
  } catch {
    return ''
  }
}

function usable(value: string): string {
  if (!value) return ''
  if (location.protocol === 'https:' && value.startsWith('http:')) return ''
  return value
}

let current = usable(fromStorage()) || frontendConfig.api.baseUrl || location.origin

export const ApiBase = {
  get(): string {
    return current
  },
  set(value: unknown): boolean {
    const next = normalize(value)
    if (!next) return false
    current = next
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      void 0
    }
    return true
  },
  normalize,
  url(path: string): string {
    return current + (path.startsWith('/') ? path : '/' + path)
  },
  async request(path: string, init?: RequestInit): Promise<Response> {
    const backend = current
    const response = await fetch(ApiBase.url(path), withAuth(init))
    if (response.status === 401 && !path.startsWith('/api/auth/')) {
      window.dispatchEvent(new CustomEvent('forest-auth-expired', { detail: { backend } }))
    }
    return response
  },
  json(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
    return ApiBase.request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      ...(signal ? { signal } : {}),
    })
  },
  applyQueryOverride(): string {
    const explicit = normalize(new URLSearchParams(location.search).get('backend'))
    if (explicit) ApiBase.set(explicit)
    return current
  },
}
