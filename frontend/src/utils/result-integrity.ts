import type { MetricEntry } from '@/types'

function record(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? Object.fromEntries(Object.entries(value))
    : undefined
}

/** Diagnose saved output without rewriting history or inventing replacement metrics. */
export function resultIntegrity(entry: MetricEntry): string[] {
  const metrics = entry.metrics ?? entry
  const issues: string[] = []
  const split = record(entry.split)
  for (const value of Object.values(entry.tables ?? {})) {
    const table = record(value)
    if (!table || !Array.isArray(table.columns) || !Array.isArray(table.rows)) continue
    const rows: unknown[][] = table.rows.filter((row): row is unknown[] => Array.isArray(row))
    const coefficient = table.columns.indexOf('coefficient')
    const complete = !table.truncated && Number(table.total_rows ?? rows.length) <= rows.length
    if (
      coefficient >= 0 &&
      complete &&
      rows.length &&
      rows.every(
        (row) => typeof row[coefficient] !== 'number' || !Number.isFinite(row[coefficient]),
      )
    ) {
      issues.push(
        '历史结果的系数全部缺失或无效，原准确率与森林图不能作为有效拟合证据；请重新运行实验。',
      )
    }
    const support = table.columns.indexOf('support')
    const classColumn = table.columns.indexOf('class')
    const overall = rows.find((row) => row[classColumn] === '整体')
    if (
      metrics.evaluation_scope === 'held_out_test' &&
      overall &&
      support >= 0 &&
      typeof split?.test === 'number' &&
      Number(overall[support]) !== split.test
    ) {
      issues.push('历史结果的分类报告样本量与测试集不一致，评价口径无效；请重新运行实验。')
    }
  }
  return [...new Set(issues)]
}
