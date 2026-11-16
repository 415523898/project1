import { ApiBase } from '@/utils/api-base'
import { readableError } from '@/services/agent'

const USER_KEY = 'forest-user-v1'

export interface AuthUser {
  username: string
}

export function username(): string {
  try {
    return localStorage.getItem(USER_KEY) ?? ''
  } catch {
    return ''
  }
}

export function remember(user: AuthUser | null): void {
  try {
    if (user) localStorage.setItem(USER_KEY, user.username)
    else localStorage.removeItem(USER_KEY)
  } catch {
    void 0
  }
}

async function post(path: string, body: Record<string, unknown>): Promise<AuthUser> {
  const response = await ApiBase.json(path, body)
  if (!response.ok) throw new Error(await readableError(response, 'credentials'))
  const data = (await response.json()) as { username?: string }
  return { username: data.username ?? '' }
}

export async function register(name: string, password: string): Promise<AuthUser> {
  const user = await post('/api/auth/register', { username: name, password })
  remember(user)
  return user
}

export async function login(name: string, password: string): Promise<AuthUser> {
  const user = await post('/api/auth/login', { username: name, password })
  remember(user)
  return user
}

export async function logout(): Promise<void> {
  const response = await ApiBase.json('/api/auth/logout', {})
  if (!response.ok) throw new Error(await readableError(response))
  remember(null)
}

export async function current(): Promise<string | null> {
  try {
    const response = await ApiBase.request('/api/auth/me')
    if (response.status === 401) {
      remember(null)
      return null
    }
    if (!response.ok) return username() || null
    const data = (await response.json()) as { username?: string }
    if (typeof data.username !== 'string' || !data.username) return username() || null
    remember({ username: data.username })
    return data.username
  } catch {
    return username() || null
  }
}
