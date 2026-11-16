import { computed, ref } from 'vue'

import { METHOD_GRAPH } from '@/data/method-graph'
import { connectionError } from '@/services/agent'
import { ApiBase } from '@/utils/api-base'
import { updateMethodNames } from '@/utils/learner-text'
import type { MethodCard, MethodGraph, RelationKind } from '@/types'

const graph = ref<MethodGraph | null>(METHOD_GRAPH)
const loading = ref(false)
const error = ref('')
let loaded = false

const cardsById = computed(() => {
  const index = new Map<string, MethodCard>()
  for (const card of graph.value?.cards ?? []) index.set(card.id, card)
  return index
})

export function useMethodGraph() {
  return {
    graph,
    loading,
    error,
    cardsById,

    card(id: string | null): MethodCard | null {
      if (!id) return null
      return cardsById.value.get(id) ?? null
    },

    label(id: string): string {
      return cardsById.value.get(id)?.label ?? id
    },

    edges(kind: RelationKind) {
      return graph.value?.edges?.[kind] ?? []
    },

    async load(force = false): Promise<void> {
      if (loaded && !force) return
      loading.value = true
      error.value = ''
      try {
        const response = await ApiBase.request('/api/agent/learning/graph')
        const value = (await response.json()) as MethodGraph & { error?: string }
        if (!response.ok) throw new Error(value?.error || '方法库加载失败。')
        if (
          !Array.isArray(value?.cards) ||
          !Array.isArray(value.tree) ||
          !Array.isArray(value.layers) ||
          !Array.isArray(value.scenarios) ||
          !Array.isArray(value.problems) ||
          !value.counts ||
          !(['prerequisite', 'suggest', 'alternative'] as const).every((kind) =>
            Array.isArray(value.edges?.[kind]),
          )
        )
          throw new Error('方法库数据不完整，请重试。')
        updateMethodNames(value.cards)
        graph.value = {
          ...value,
          counts: {
            ...value.counts,
            methods: value.cards.length,
            prerequisite: value.edges.prerequisite.length,
            suggest: value.edges.suggest.length,
            alternative: value.edges.alternative.length,
            levels: value.layers.length,
          },
        }
        loaded = true
      } catch (problem) {
        const message = connectionError(problem)
        error.value = message.includes('连接中断')
          ? `${message}（当前后端：${ApiBase.get()}）`
          : message
      } finally {
        loading.value = false
      }
    },
  }
}
