import { computed, shallowRef } from 'vue'

import { METHOD_GRAPH } from '@/data/method-graph'
import type { MethodCard } from '@/types'

const names = shallowRef(new Map(METHOD_GRAPH.cards.map((card) => [card.id, card.label])))
const methodPattern = computed(
  () =>
    new RegExp(
      `(?<![\\w.])(?:${[...names.value.keys()].map((id) => id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') || '(?!)'})(?![\\w.])`,
      'g',
    ),
)

export function updateMethodNames(cards: Pick<MethodCard, 'id' | 'label'>[]): void {
  // Historical results retain readable labels without adding methods to the live catalogue.
  const next = new Map(names.value)
  for (const card of cards) next.set(card.id, card.label)
  names.value = next
}
const toolNames: Record<string, string> = {
  search_ml_methods: '检索分析方法',
  inspect_datasets: '查看数据集',
  run_ml_suite: '运行分析实验',
  experiment: '运行分析实验',
  view_experiment_image: '查看实验图像',
  read_experiment_figure_data: '读取图表数据',
  report_formula_learning: '公式学习意愿',
  report_learning_direction: '学习目标确认',
  extract_learning_units: '提取学习要点',
  compose_learning_card: '整理学习卡片',
  connect_learning_cards: '整理卡片关系',
  prepare_self_check: '准备学习自测',
  grade_self_check: '评价自测作答',
}
const toolPattern = new RegExp(
  `\\b(?:${Object.keys(toolNames)
    .filter((name) => name !== 'experiment')
    .join('|')})\\b`,
  'g',
)
const privateCode =
  /(?:\b(?:from|import)\s+(?:backend|engine|agent|ml_tools|registry)\b|\b(?:engine\.params|params\.for_method|ml_tools\.)|backend[\\/]\w)/
const privatePath =
  /(?:[A-Za-z]:[\\/](?:[A-Za-z0-9_\u4e00-\u9fff .-]+[\\/])+[^\s`<>"，。；）]+|\bbackend[\\/](?:agent|engine|api|tools|utils)[\\/][^\s`<>"，。；）]+)/g

export function learnerText(text: string): string {
  const pattern = methodPattern.value
  return text
    .replace(/(`{3,}|~{3,})[^\n]*\n[\s\S]*?\1/g, (block) => {
      pattern.lastIndex = 0
      toolPattern.lastIndex = 0
      return privateCode.test(block) || pattern.test(block) || toolPattern.test(block)
        ? '> 此历史代码示例依赖应用内部功能。可继续询问使用公开 Python 库的独立示例。'
        : block
    })
    .replace(/代码入口\s*/g, '')
    .replace(privatePath, '应用内部实现')
    .replace(pattern, (id) => names.value.get(id) ?? id)
    .replace(toolPattern, (name) => toolNames[name] ?? name)
    .replace(/\b(?:engine\.params|params\.for_method|ml_tools\.\w+)\b/g, '实验参数设置')
}

const privateFields = new Set([
  'implementation',
  'traceback',
  'stack',
  'file_path',
  'path',
  'module',
  'entrypoint',
  'handler',
  'session_id',
  'card_id',
  'point_ids',
  'evidence_ids',
])
const fieldNames: Record<string, string> = {
  methods: '分析方法',
  method_id: '方法',
  params: '参数设置',
  dataset: '数据集',
  source: '数据来源',
  reason: '操作目的',
  figures: '生成图表',
  query: '检索内容',
  target: '目标变量',
  features: '特征变量',
  label: '名称',
  note: '说明',
}

export function learnerValue(value: unknown): unknown {
  if (typeof value === 'string') return learnerText(value)
  if (Array.isArray(value)) return value.map(learnerValue)
  if (value && typeof value === 'object')
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !privateFields.has(key))
        .map(([key, item]) => [names.value.get(key) ?? fieldNames[key] ?? key, learnerValue(item)]),
    )
  return value
}

export const learnerToolName = (name: string) => toolNames[name] ?? '学习辅助操作'
