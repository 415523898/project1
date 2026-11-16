import type { MethodCard } from '@/types'
import bilingual from '@/data/method-search-bilingual.json'
import profiles from '@/data/method-search-profiles.json'

interface SearchProfile {
  aliases?: string[]
  terms?: string[]
  samples?: string[]
  groups?: string[]
  distribution?: string
  target?: string
  temporalForecast?: boolean
  basis: string
}
export interface BilingualProfile {
  en_name: string
  en_description: string
  en_keywords: string[]
  zh_examples: string[]
  en_examples: string[]
}
export const SEARCH_PROFILES: Record<string, SearchProfile> = profiles.methods
export const BILINGUAL_PROFILES: Record<string, BilingualProfile> =
  bilingual.methods as Record<string, BilingualProfile>

export function embeddingProfile(card: MethodCard): string {
  const profile = SEARCH_PROFILES[card.id]
  const extra = BILINGUAL_PROFILES[card.id]
  return [
    card.label,
    card.group,
    card.category_name,
    card.kind,
    card.when,
    card.note,
    ...(card.scenarios ?? []),
    ...(card.inputs ?? []),
    ...(card.outputs ?? []),
    ...(profile?.aliases ?? []),
    ...(profile?.terms ?? []),
    extra?.en_name,
    extra?.en_description,
    ...(extra?.en_keywords ?? []),
    ...(extra?.zh_examples ?? []),
    ...(extra?.en_examples ?? []),
  ]
    .filter(Boolean)
    .join(' ')
}
