import { ApiBase } from '@/utils/api-base'

function absolute(path: string): string {
  return ApiBase.url('/' + path.replace(/^\/+/, ''))
}

export function figureSrc(name: string, value: string | null | undefined): string {
  const raw = (value ?? '').trim()
  if (!raw) return ''
  if (/^https?:\/\//i.test(raw)) return raw
  const path = raw.replace(/^\/+|\/+$/g, '')
  if (!path) return ''
  const stem = (name ?? '').trim()
  const tail = path.split('/').pop() ?? ''
  const looksLikeFile = tail.includes('.')
  const target = !stem || looksLikeFile ? path : `${path}/${stem}`
  return absolute(target.startsWith('api/') ? target : `api/figures/${target}`)
}
