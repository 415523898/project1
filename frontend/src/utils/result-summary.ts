import type { ExperimentResult, MetricEntry } from '@/types'
import { displayLabel, entryMetrics, messages } from '@/utils/result-format'
import { resultIntegrity } from '@/utils/result-integrity'
import { learnerText } from '@/utils/learner-text'

const preferred = [
  'accuracy',
  'test_accuracy',
  'roc_auc_ovr',
  'roc_auc',
  'test_r2',
  'r_squared',
  'adj_r_squared',
  'adjusted_r_squared',
  'test_rmse',
  'rmse',
  'test_mae',
  'mae',
  'fpc',
  'fuzzy_partition_coefficient',
  'clusters',
  'silhouette',
  'nps',
  'cronbach_alpha',
  'cpk',
  'pooled_effect',
  'p_value',
  'statistic',
  'f_statistic',
  't_statistic',
  'q_statistic',
  'h_statistic',
  'u_statistic',
  'chi_square',
  'p',
  'rows',
  'records',
  'observations',
  'respondents',
  'documents',
  'columns',
  'levels',
]
const byMethod: Record<string, string[]> = {
  'model.logistic': ['accuracy', 'accuracy_at_threshold', 'evaluation_rows', 'observations'],
  'model.probit': ['accuracy_at_threshold', 'evaluation_rows', 'observations'],
  'prep.outliers': ['outlier_cells', 'treated_cells', 'rows_dropped'],
  'prep.missing': ['missing_cells_before', 'missing_cells_after', 'rows_after'],
  'prep.duplicates': ['duplicate_rows', 'unique_rows', 'rows_after'],
  'prep.encoding': ['categorical_columns', 'encoded_features', 'strategy'],
  'prep.derive': ['created', 'features_after', 'kind'],
  'prep.winsorize': ['clipped_cells', 'clipped_rows', 'features'],
  'prep.transform': ['mean_skew_before', 'mean_skew_after', 'features'],
  'prep.balance': ['classes', 'imbalance_ratio', 'rows'],
  'prep.pca': ['components', 'explained_total', 'explained_first'],
  'prep.spectral': ['features_in', 'features_out', 'time_points'],
  'describe.power': ['required_total', 'required_per_group', 'target_power'],
  'model.vif': ['max_vif', 'worst_feature', 'count_over_threshold'],
  'model.canonical': ['first_correlation', 'mean_shared_variance', 'components'],
  'model.mediation': ['indirect_effect', 'direct_effect', 'total_effect'],
  'model.moderation': ['interaction_beta', 'interaction_p', 'observations'],
  'series.arima': ['aic', 'next_forecast', 'observations'],
  'series.sarima': ['aic', 'next_forecast', 'observations'],
  'series.adf': ['adf_p_value', 'adf_statistic', 'stationary_by_adf'],
  'series.coint': ['cointegrated_pairs', 'smallest_p', 'observations'],
  'series.granger': ['significant_pairs', 'strongest_pair', 'smallest_p'],
  'series.gm11': ['next_forecast', 'mean_relative_error', 'observations'],
  'causal.did': ['did_effect', 'did_p_value', 'observations'],
  'causal.psmdid': ['did_effect', 'did_p_value', 'matched_pairs'],
  'causal.psm': ['att_effect', 'p_value', 'matched_pairs'],
  'causal.rd': ['local_linear_effect', 'local_linear_p', 'observations'],
  'causal.heckman': ['lambda', 'lambda_p_value', 'selection_bias'],
  'causal.placebo': ['actual_effect', 'p_value', 'placebo_mean'],
  'eval.pca': ['components', 'explained_total', 'indicators'],
  'eval.factor': ['factors', 'explained_total', 'indicators'],
  'eval.entropy': ['top_weight', 'top_weight_value', 'objects'],
  'eval.critic': ['top_weight', 'top_weight_value', 'indicators'],
  'eval.topsis': ['best_closeness', 'worst_closeness', 'objects'],
  'eval.vikor': ['best_compromise', 'objects', 'indicators'],
  'eval.rsr': ['best_rsr', 'worst_rsr', 'objects'],
  'eval.dea': ['efficient_units', 'mean_efficiency', 'objects'],
  'eval.fuzzy': ['best_score', 'objects', 'indicators'],
  'eval.grey': ['best_grade', 'objects', 'indicators'],
  'domain.sentiment': ['positive', 'negative', 'neutral', 'documents', 'mean_score'],
  'domain.nps': ['nps', 'respondents', 'nps_ci_low', 'nps_ci_high'],
  'domain.kano': ['dominant', 'cs_better', 'cs_worse', 'respondents'],
  'domain.wordfreq': ['documents', 'vocabulary', 'vocabulary_size', 'top_term'],
  'domain.tfidf': ['documents', 'vocabulary', 'vocabulary_size', 'top_term'],
  'domain.lda': ['topics', 'documents', 'perplexity'],
  'domain.km': ['observations', 'events', 'median_survival'],
  'domain.cox': ['concordance', 'concordance_index', 'observations', 'events'],
  'domain.reliability': ['cronbach_alpha', 'mcdonald_omega', 'respondents', 'items'],
  'domain.control': ['chart', 'violation_points', 'observations', 'subgroups'],
  'domain.capability': ['cpk', 'cp', 'observations'],
  'domain.weibull': ['shape', 'scale', 'observations'],
  'domain.meta': ['pooled_effect', 'i_squared', 'tau_squared', 'studies'],
  'domain.maxdiff': ['top_option', 'top_share', 'respondents'],
  'domain.psm': ['optimal_price', 'indifference_price', 'respondents'],
}

export interface ResultTable {
  key: string
  label: string
  columns: string[]
  rows: unknown[][]
  total: number
  truncated: boolean
  raw?: unknown
}
const tableLabels: Record<string, string> = {
  frequency: '频数表',
  top_terms: '关键词表',
  documents: '文档明细',
  topics: '主题表',
  items: '题项结果',
  groups: '分组结果',
  treatments: '处理组结果',
  coefficients: '系数表',
  features: '特征结果',
  loadings: '载荷表',
  scores: '得分表',
  forecast: '预测表',
  importance: '重要性表',
}
export function resultTables(entry: MetricEntry): ResultTable[] {
  const tables = entry.tables
  if (!tables || typeof tables !== 'object' || Array.isArray(tables)) return []
  return Object.entries(tables)
    .filter(([, value]) => value && typeof value === 'object' && Object.keys(value).length)
    .map(([key, value]) => {
      const table = value as {
        columns?: unknown
        rows?: unknown
        total_rows?: unknown
        truncated?: boolean
      }
      const valid = Array.isArray(table.columns) && Array.isArray(table.rows)
      const rows = valid ? ((table.rows as unknown[]).filter(Array.isArray) as unknown[][]) : []
      const columns = valid ? (table.columns as unknown[]).map(String) : []
      const total =
        typeof table.total_rows === 'number' && Number.isFinite(table.total_rows)
          ? table.total_rows
          : rows.length
      return {
        key,
        label: tableLabels[key] ?? displayLabel(key),
        columns,
        rows,
        total,
        truncated: Boolean(table.truncated) || total > rows.length,
        ...(!valid ? { raw: value } : {}),
      }
    })
}

export function resultSummary(entry: MetricEntry, method = ''): string {
  const issues = resultIntegrity(entry)
  if (issues.length) return '历史结果存在无效拟合或评价口径冲突，请重新运行'
  const order = [...(byMethod[method || String(entry.method ?? '')] ?? []), ...preferred]
  const rank = (key: string) => {
    const index = order.indexOf(key)
    return index < 0 ? order.length : index
  }
  const rows = entryMetrics(entry, method || String(entry.method ?? '')).sort(
    (a, b) => rank(a.key) - rank(b.key),
  )
  if (rows.length)
    return (
      rows
        .slice(0, 3)
        .map((row) => `${row.label} ${row.value}`)
        .join(' · ') + (entry.metrics?.inference_available === false ? ' · 系数推断不可用' : '')
    )
  const tables = resultTables(entry)
  if (tables.length)
    return `已返回 ${tables.length} 张结果表 · ${tables
      .slice(0, 2)
      .map((table) => table.label)
      .join('、')}`
  const notes = messages(entry.notes)
  if (notes.length) return notes[0]!
  const figures = Array.isArray(entry.figures) ? entry.figures : []
  if (figures.length) return `已返回 ${figures.length} 张图形`
  return '本次运行未返回可展示的指标或结果表。'
}

export interface OutcomeRow {
  id: string
  label: string
  summary: string
  status: 'success' | 'error' | 'empty'
  entry: MetricEntry | null
}
export function requestedMethods(arguments_: Record<string, unknown> | undefined): string[] {
  const values = Array.isArray(arguments_?.methods)
    ? arguments_.methods
    : arguments_?.method
      ? [arguments_.method]
      : []
  return [
    ...new Set(
      values
        .map((value) =>
          typeof value === 'string'
            ? value
            : value && typeof value === 'object'
              ? ((value as { method?: unknown; id?: unknown }).method ??
                (value as { id?: unknown }).id)
              : null,
        )
        .filter((value): value is string => typeof value === 'string' && Boolean(value.trim())),
    ),
  ]
}

/** Older conversations stored retrieval-card ids that the library never ran under, so show the method they meant. */
const historicalNames: Record<string, string> = {
  'clf.lda': '判别分析 LDA',
  'clf.logistic_regression': 'Logistic 回归',
  'clf.decision_tree': '决策树分类',
  'clf.random_forest': '随机森林分类',
  logistic_regression: 'Logistic 回归',
  lda: '判别分析 LDA',
  decision_tree: '决策树分类',
  random_forest_classifier: '随机森林分类',
}

/** Use the actual methods even when the tool's generic title is run_ml_suite. */
export function experimentName(
  result: ExperimentResult,
  requested: string[] = [],
  labelOf: (id: string) => string | undefined = () => undefined,
): string {
  const labels = experimentRows(result, requested, labelOf)
    .filter((row) => !row.id.startsWith('__'))
    .map((row) => row.label)
  if (labels.length) return [...new Set(labels)].join('、')
  return result.title && result.title !== 'run_ml_suite' ? result.title : '实验结果'
}

export function experimentRows(
  result: ExperimentResult,
  requested: string[] = [],
  labelOf: (id: string) => string | undefined = () => undefined,
): OutcomeRow[] {
  const rows = new Map<string, OutcomeRow>()
  const label = (id: string, value?: unknown) =>
    learnerText(
      typeof value === 'string' && value.trim() ? value : labelOf(id) || historicalNames[id] || id,
    )
  for (const [id, entry] of Object.entries(result.methods ?? {})) {
    if (!entry || typeof entry !== 'object') continue
    const error = typeof entry.error === 'string' && entry.error.trim() ? entry.error : ''
    rows.set(id, {
      id,
      label: label(id, entry.label),
      summary: learnerText(error || resultSummary(entry, id)),
      status: error
        ? 'error'
        : entryMetrics(entry).length ||
            resultTables(entry).length ||
            messages(entry.notes).length ||
            (Array.isArray(entry.figures) && entry.figures.length)
          ? 'success'
          : 'empty',
      entry: error ? null : entry,
    })
  }
  if (!rows.size && result.metrics && Object.keys(result.metrics).length) {
    const id = result.method || '__result'
    const entry = { metrics: result.metrics, tables: result.tables, notes: result.notes }
    rows.set(id, {
      id,
      label: label(id, result.title || (id === '__result' ? '本次实验' : undefined)),
      summary: resultSummary(entry, id),
      status: 'success',
      entry,
    })
  }
  for (const failure of result.failures ?? []) {
    if (!failure || typeof failure.method !== 'string') continue
    rows.set(failure.method, {
      id: failure.method,
      label: label(failure.method, failure.label),
      summary: failure.error || '方法未完成，未返回具体原因。',
      status: 'error',
      entry: null,
    })
  }
  for (const id of [...new Set([...(result.method ? [result.method] : []), ...requested])]) {
    if (!rows.has(id))
      rows.set(id, {
        id,
        label: label(id),
        summary: result.error || '本次运行未返回该方法的结果。',
        status: result.error ? 'error' : 'empty',
        entry: null,
      })
  }
  if (
    result.error &&
    ![...rows.values()].some((row) => row.status === 'error' && row.summary === result.error)
  ) {
    rows.set('__error', {
      id: '__error',
      label: '本次实验',
      summary: result.error,
      status: 'error',
      entry: null,
    })
  }
  return [...rows.values()]
}

/** Rerunning one method must retain its sibling results and remove that method's stale output. */
export function mergeExperiment(
  previous: ExperimentResult,
  next: ExperimentResult,
  method?: string,
): ExperimentResult {
  const replaced = new Set([
    ...Object.keys(next.methods ?? {}),
    ...(next.failures ?? []).map((item) => item.method),
    ...(method ? [method] : []),
  ])
  if (!replaced.size) return next
  const removedFigures = new Set(
    [...replaced].flatMap((id) => {
      const figures = previous.methods?.[id]?.figures
      return Array.isArray(figures) ? figures.map((figure) => figure?.name).filter(Boolean) : []
    }),
  )
  const methods = {
    ...Object.fromEntries(
      Object.entries(previous.methods ?? {}).filter(([id]) => !replaced.has(id)),
    ),
    ...next.methods,
  }
  const failures = [
    ...(previous.failures ?? []).filter((item) => !replaced.has(item.method)),
    ...(next.failures ?? []),
  ]
  const keptFigures = Object.keys(previous.methods ?? {}).every((id) => replaced.has(id))
    ? []
    : (previous.figures ?? []).filter((figure) => !removedFigures.has(figure.name))
  const figures = [
    ...new Map(
      [...keptFigures, ...(next.figures ?? [])].map((figure) => [
        figure.url || figure.name,
        figure,
      ]),
    ).values(),
  ]
  const sourcesOf = (result: ExperimentResult, ids: string[]) => {
    const sources = (result.datasets ?? [])
      .map((source) => ({ ...source, methods: source.methods.filter((id) => ids.includes(id)) }))
      .filter((source) => source.methods.length)
    for (const id of ids) {
      if (sources.some((source) => source.methods.includes(id))) continue
      const entry = result.methods?.[id]
      sources.push({
        methods: [id],
        dataset: typeof entry?.dataset === 'string' ? entry.dataset : result.dataset,
        label:
          typeof entry?.dataset_label === 'string' ? entry.dataset_label : result.dataset_label,
        source: typeof entry?.source === 'string' ? entry.source : result.source,
      })
    }
    return sources
  }
  const datasets = [
    ...sourcesOf(
      previous,
      Object.keys(previous.methods ?? {}).filter((id) => !replaced.has(id)),
    ),
    ...sourcesOf(next, [...replaced]),
  ]
  return {
    ...previous,
    ...next,
    title: previous.title ?? next.title,
    methods,
    failures,
    figures,
    datasets,
    notes: next.notes,
    warnings: next.warnings,
    error: next.error,
    failures_note: next.failures_note,
  }
}
