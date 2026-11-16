import type { MethodCard } from '@/types'
import { BILINGUAL_PROFILES, embeddingProfile, SEARCH_PROFILES } from '@/utils/method-search-corpus'

export interface SearchHit {
  id: string
  label: string
  group: string
  score: number
  reason?: string
  source?: 'description' | 'semantic'
  exact?: boolean
}

export function normalizeQuery(value: string): string {
  return value
    .normalize('NFKC')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .replace(/\s+/g, ' ')
}

function fields(card: MethodCard) {
  const bilingual = BILINGUAL_PROFILES[card.id]
  return [
    { name: '方法名称', text: card.label, weight: 8 },
    { name: '方法标识', text: card.id, weight: 5 },
    { name: '使用场景', text: card.when, weight: 7 },
    { name: '方法描述', text: card.note, weight: 7 },
    { name: '适用问题', text: card.scenarios?.join(' '), weight: 5 },
    { name: '输入', text: card.inputs?.join(' '), weight: 3 },
    { name: '输出', text: card.outputs?.join(' '), weight: 3 },
    { name: '分组', text: `${card.group} ${card.category_name ?? ''}`, weight: 1 },
    { name: '名称别名', text: SEARCH_PROFILES[card.id]?.aliases?.join(' '), weight: 8 },
    { name: '场景补充', text: SEARCH_PROFILES[card.id]?.terms?.join(' '), weight: 5 },
    { name: '英文名称', text: bilingual?.en_name, weight: 7 },
    { name: '英文描述', text: bilingual?.en_description, weight: 5 },
    { name: '英文关键词', text: bilingual?.en_keywords?.join(' '), weight: 5 },
    { name: '中文示例', text: bilingual?.zh_examples?.join(' '), weight: 4 },
    { name: '英文示例', text: bilingual?.en_examples?.join(' '), weight: 4 },
  ].map((field) => ({
    ...field,
    text: field.text ?? '',
    normalized: normalizeQuery(field.text ?? ''),
  }))
}

function terms(value: string): string[] {
  const result = new Set<string>()
  for (const part of value.match(/[a-z0-9]+|[\u3400-\u9fff]+/g) ?? []) {
    if (!/[\u3400-\u9fff]/.test(part) || part.length <= 2) result.add(part)
    else
      for (let index = 0; index < part.length - 1; index++) result.add(part.slice(index, index + 2))
  }
  return [...result].filter(
    (term) =>
      ![
        '怎么',
        '如何',
        '什么',
        '是否',
        '进行',
        '可以',
        '一个',
        '需要',
        '的数',
        '据的',
        '帮我',
        '一张',
      ].includes(term),
  )
}

function queryConditions(query: string) {
  const compare =
    /比较|差异|均值|检验|重复测量/.test(query) &&
    /两组|三组|多组|配对|独立样本|同一批对象/.test(query)
  // Negation must be checked before the positive phrase. Missing information stays unknown.
  const nonparametric =
    /非参数|偏态|非正态|不(?:近似|符合|服从)正态|不满足.*(?:正态|方差分析)|正态性.*不成立/.test(
      query,
    )
  const explicit = query.replace(
    /(?:不是|并非|非|不)(?:独立样本|配对样本|分类标签|分类|连续量|连续|计数)/g,
    '',
  )
  const samples = /独立样本/.test(explicit)
    ? 'independent'
    : /配对|同一批对象|重复测量/.test(explicit)
      ? 'paired'
      : ''
  const groups = /三组|多组|多个条件|三个.*时点/.test(query)
    ? 'many'
    : /两组|前后配对|配对样本/.test(query)
      ? 'two'
      : ''
  const target = /目标列.*(?:没有说明|未知|未说明)/.test(query)
    ? ''
    : /二值响应/.test(explicit)
      ? 'binary'
      : /目标列.*(?:分类|标签)/.test(explicit)
        ? 'categorical'
        : /目标列.*(?:计数|次数|件数)/.test(explicit)
          ? 'count'
          : /目标列.*(?:连续|金额)/.test(explicit)
            ? /为正/.test(explicit)
              ? 'positive'
              : 'continuous'
            : ''
  return {
    compare,
    samples,
    groups,
    target,
    distribution: nonparametric ? 'nonparametric' : /近似正态/.test(query) ? 'normal' : '',
    temporal: /时间顺序|时间序列|序列/.test(query) && /预测/.test(query),
  }
}

function conditionRank(card: MethodCard, query: string): number {
  const conditions = queryConditions(query),
    profile = SEARCH_PROFILES[card.id]
  if (!profile) return 0
  let rank = 0
  if (conditions.compare && profile.samples) {
    rank = 1 // Relevant comparison family; no guessed distribution or sampling design.
    for (const [value, allowed] of [
      [conditions.samples, profile.samples],
      [conditions.groups, profile.groups],
    ] as const) {
      if (value && allowed) rank += allowed.includes(value) ? 1 : -3
    }
    if (conditions.distribution && profile.distribution)
      rank += conditions.distribution === profile.distribution ? 1 : -2
  }
  if (conditions.target && profile.target) {
    rank +=
      conditions.target === profile.target ||
      (conditions.target === 'positive' && profile.target === 'continuous')
        ? 1
        : -1
  }
  if (conditions.temporal && profile.temporalForecast) rank += 1
  return rank
}

export function searchGuidance(query: string): string {
  const conditions = queryConditions(query)
  if (normalizeQuery(query) === 'psm')
    return 'PSM 有两种含义：倾向得分匹配与价格敏感度测试，请按用途选择。'
  if (conditions.compare && (!conditions.samples || !conditions.distribution)) {
    return '请确认独立还是配对样本、分布及差值条件；候选卡片列出各自适用场景，非参数方法不等同于任意分布的均值检验。'
  }
  if (conditions.temporal)
    return '按时间顺序建模；还需确认单变量或多变量、平稳性及季节周期，时间顺序本身不能确定这些条件。'
  if (/目标列/.test(query) && !conditions.target)
    return '目标类型尚未明确：连续量、分类标签与计数需要不同模型，请结合卡片场景选择。'
  return ''
}

export function searchDescriptions(cards: MethodCard[], query: string, limit = 12): SearchHit[] {
  const normalized = normalizeQuery(query)
  if (!normalized) return []
  const needles = terms(normalized)
  const documents = cards.map((card) => ({ card, fields: fields(card) }))
  const frequencies = new Map(
    needles.map((term) => [
      term,
      documents.filter((document) =>
        document.fields.some((field) => field.normalized.includes(term)),
      ).length,
    ]),
  )
  return documents
    .flatMap(({ card, fields }) => {
      const exact = [card.label, card.id, ...(SEARCH_PROFILES[card.id]?.aliases ?? [])].some(
        (name) => normalizeQuery(name).replaceAll(' ', '') === normalized.replaceAll(' ', ''),
      )
      let score = exact ? 200 : 0
      let best = '',
        bestScore = 0
      const matched = new Set<string>()
      for (const field of fields) {
        let contribution = field.normalized.includes(normalized) ? field.weight * 4 : 0
        for (const term of needles) {
          if (!field.normalized.includes(term)) continue
          matched.add(term)
          contribution +=
            field.weight * Math.log(1 + cards.length / (1 + (frequencies.get(term) ?? 0)))
        }
        score += contribution
        if (contribution > bestScore) {
          bestScore = contribution
          best = `${field.name}：${field.text.slice(0, 80)}`
        }
      }
      if (!exact && (!matched.size || score < 3)) return []
      score *= exact ? 1 : 0.4 + (0.6 * matched.size) / Math.max(1, needles.length)
      return [
        {
          id: card.id,
          label: card.label,
          group: card.group,
          score,
          reason: exact
            ? '方法名称或别名匹配'
            : conditionRank(card, query) > 0 && card.when
              ? `适用条件：${card.when}`
              : best,
          source: 'description' as const,
          exact,
          condition: conditionRank(card, query),
        },
      ]
    })
    .sort(
      (a, b) =>
        Number(b.exact) - Number(a.exact) ||
        b.condition - a.condition ||
        b.score - a.score ||
        a.id.localeCompare(b.id),
    )
    .slice(0, limit)
}

export function searchVersion(cards: MethodCard[]): string {
  return JSON.stringify([
    SEARCH_PROFILES,
    cards.map((card) => [card.id, fields(card).map((field) => field.text), embeddingProfile(card)]),
  ])
}

export function supplementDescriptions(
  current: SearchHit[],
  semantic: Array<{ id: string; score: number }>,
  cards: MethodCard[],
): SearchHit[] {
  const byId = new Map(cards.map((card) => [card.id, card]))
  const semanticScores = new Map(
    semantic.filter((item) => byId.has(item.id)).map((item) => [item.id, item.score]),
  )
  const maxText = Math.max(1, ...current.map((hit) => hit.score))
  // Blend semantic similarity into the ordering instead of only appending unseen
  // cards: a scenario description can lift a card above a weaker name match.
  const result = current.map((hit) => {
    if (hit.exact) return hit
    const similarity = semanticScores.get(hit.id) ?? 0
    const weighted = (hit.score / maxText) * 0.3 + Math.max(0, similarity) * 0.7
    const labelled = similarity >= 0.35 && hit.source === 'description' && hit.reason
    return {
      ...hit,
      score: weighted,
      reason: labelled ? `${hit.reason} · 语义相关` : hit.reason,
    }
  })
  const seen = new Set(result.map((hit) => hit.id))
  for (const item of semantic) {
    const card = byId.get(item.id)
    // A local relevance cutoff, not an applicability probability. Audited on queries.json.
    if (!card || seen.has(item.id) || item.score < 0.5) continue
    seen.add(item.id)
    result.push({
      id: card.id,
      label: card.label,
      group: card.group,
      score: item.score,
      reason: `语义补充：${(card.when || card.note || card.label).slice(0, 80)}`,
      source: 'semantic',
    })
  }
  result.sort(
    (a, b) =>
      Number(b.exact) - Number(a.exact) ||
      b.score - a.score ||
      a.id.localeCompare(b.id),
  )
  return result.slice(0, 12)
}
