import type { MetricEntry } from '@/types'
import { learnerText, learnerValue } from '@/utils/learner-text'

export interface DisplayMetric {
  key: string
  label: string
  value: string
}
const labels: Record<string, string> = {
  accuracy: '准确率',
  train_accuracy: '训练准确率',
  test_accuracy: '测试准确率',
  roc_auc: 'AUC',
  roc_auc_ovr: 'AUC',
  f1: 'F1',
  f1_macro: '宏平均 F1',
  f1_weighted: '加权 F1',
  precision: '精确率',
  precision_macro: '宏平均精确率',
  recall: '召回率',
  recall_macro: '宏平均召回率',
  train_loss: '训练损失',
  test_loss: '测试损失',
  train_r2: '训练 R²',
  test_r2: '测试 R²',
  r_squared: 'R²',
  adj_r_squared: '调整 R²',
  r2: 'R²',
  rmse: 'RMSE',
  mae: 'MAE',
  mse: 'MSE',
  test_rmse: '测试 RMSE',
  test_mae: '测试 MAE',
  train_rmse: '训练 RMSE',
  rows: '样本数',
  records: '样本数',
  observations: '观测数',
  evaluation_rows: '评价样本数',
  evaluation_scope: '预测评价范围',
  fit_scope: '拟合统计范围',
  converged: '优化器已收敛',
  inference_available: '系数推断可用',
  coefficient_plot_status: '系数图状态',
  diagnostic_plot: '替代诊断图',
  n: '样本数',
  n_obs: '观测数',
  columns: '统计列数',
  features: '特征数',
  levels: '水平数',
  count: '频数',
  total: '总数',
  clusters: '聚类数',
  noise: '噪声点数',
  noise_points: '噪声点数',
  fpc: 'FPC',
  silhouette: '轮廓系数',
  inertia: '簇内平方和',
  calinski_harabasz: 'CH 指数',
  davies_bouldin: 'DB 指数',
  p_value: 'p 值',
  p: 'p 值',
  statistic: '统计量',
  test_statistic: '检验统计量',
  df: '自由度',
  dof: '自由度',
  t: 't 值',
  f: 'F 值',
  z: 'z 值',
  chi2: 'χ²',
  coefficient: '系数',
  coefficients: '系数表',
  intercept: '截距',
  estimate: '估计值',
  std_error: '标准误',
  standard_error: '标准误',
  ci_low: '置信区间下限',
  ci_high: '置信区间上限',
  lower: '下限',
  upper: '上限',
  confidence_level: '置信水平',
  aic: 'AIC',
  bic: 'BIC',
  mean: '均值',
  median: '中位数',
  std: '标准差',
  min: '最小值',
  max: '最大值',
  skewness: '偏度',
  kurtosis: '峰度',
  variance: '方差',
  correlation: '相关系数',
  missing: '缺失数',
  missing_before: '处理前缺失数',
  missing_after: '处理后缺失数',
  imputed: '填补数',
  dropped: '删除数',
  rows_before: '处理前样本数',
  rows_after: '处理后样本数',
  duplicates: '重复数',
  duplicates_removed: '删除重复数',
  outliers: '异常值数',
  method: '方法',
  strategy: '处理策略',
  components: '成分数',
  explained_variance_ratio: '解释方差占比',
  cumulative_variance: '累计解释方差',
  explained_variance: '解释方差',
  documents: '文档数',
  text_column: '文本列',
  vocabulary: '词汇数',
  vocabulary_size: '词汇数',
  positive: '正面文档数',
  negative: '负面文档数',
  neutral: '中性文档数',
  mean_score: '平均得分',
  top_term: '最高频词',
  top_terms: '关键词数',
  topics: '主题数',
  positive_words: '正向词数',
  negative_words: '负向词数',
  negation_flips: '否定修正数',
  negation_window: '否定词窗口',
  detail_rows: '明细行数',
  perplexity: '困惑度',
  respondents: '受访者数',
  nps: 'NPS 净推荐值',
  promoters: '推荐者数',
  passives: '被动者数',
  detractors: '贬损者数',
  nps_ci_low: 'NPS 置信区间下限',
  nps_ci_high: 'NPS 置信区间上限',
  nps_std_error: 'NPS 标准误',
  zero_test_p: '与零比较的 p 值',
  zero_test_z: '与零比较的 z 值',
  items: '题项数',
  cronbach_alpha: 'Cronbach α',
  mcdonald_omega: 'McDonald ω',
  kmo: 'KMO',
  bartlett_p: 'Bartlett 检验 p 值',
  cs_better: '满意系数',
  cs_worse: '不满意系数',
  options: '选项数',
  profiles: '方案数',
  attributes: '属性数',
  terms: '模型项数',
  cp: 'Cp',
  cpk: 'Cpk',
  pp: 'Pp',
  ppk: 'Ppk',
  cpu: 'Cpu',
  cpl: 'Cpl',
  chart: '控制图类型',
  violation_points: '异常点数',
  subgroups: '子组数',
  subgroup_size: '子组容量',
  lower_spec: '规格下限',
  upper_spec: '规格上限',
  shape: '形状参数',
  scale: '尺度参数',
  studies: '研究数',
  pooled_effect: '合并效应',
  i_squared: 'I²',
  tau_squared: 'τ²',
  duration_column: '时间列',
  event_column: '事件列',
  events: '事件数',
  censored: '删失数',
  concordance: '一致性指数',
  concordance_index: '一致性指数',
  median_survival: '中位生存时间',
  hazard_ratio: '风险比',
  survival_at_horizon: '指定时间生存率',
  horizon: '预测时间',
  group_column: '分组列',
  groups: '分组数',
  column: '分析列',
  target: '目标列',
  split_train: '训练样本数',
  split_test: '测试样本数',
  split_validation: '验证样本数',
  split_mode: '数据划分方式',
  elapsed_ms: '运行时间',
  frequency: '频数表',
  distribution: '分布表',
  summary: '汇总表',
  top_terms_table: '关键词表',
  cluster_sizes: '各簇样本数',
  confusion_matrix: '混淆矩阵',
  predictions: '预测结果',
  residuals: '残差',
  ranking: '排序结果',
  weights: '权重',
  scores: '得分',
  categories: '分类分布',
  topics_table: '主题表',
  term: '变量',
  feature: '特征',
  label: '类别',
  ratio: '占比',
  cumulative: '累计占比',
  adjusted_r_squared: '调整 R²',
  pseudo_r_squared: '伪 R²',
  log_likelihood: '对数似然',
  significant: '是否显著',
  degrees_of_freedom: '自由度',
  f_statistic: 'F 统计量',
  t_statistic: 't 统计量',
  q_statistic: 'Q 统计量',
  h_statistic: 'H 统计量',
  u_statistic: 'U 统计量',
  chi_square: 'χ² 统计量',
  odds_ratio: '优势比',
  fuzzy_partition_coefficient: '模糊分区系数',
  accuracy_at_threshold: '阈值下准确率',
  outlier_cells: '异常单元格数',
  treated_cells: '已处理单元格数',
  rows_with_outlier: '含异常的样本数',
  rows_dropped: '删除样本数',
  missing_cells_before: '处理前缺失数',
  missing_cells_after: '处理后缺失数',
  imputed_columns: '填补列数',
  columns_with_missing: '含缺失列数',
  skipped_columns: '跳过列数',
  duplicate_rows: '重复样本数',
  unique_rows: '唯一样本数',
  duplicate_groups: '重复分组数',
  categorical_columns: '分类列数',
  encoded_features: '编码特征数',
  created: '新增特征数',
  features_after: '处理后特征数',
  features_total: '总特征数',
  features_in: '输入特征数',
  features_out: '输出特征数',
  clipped_cells: '截尾单元格数',
  clipped_rows: '截尾样本数',
  mean_skew_before: '处理前平均偏度',
  mean_skew_after: '处理后平均偏度',
  classes: '类别数',
  imbalance_ratio: '不平衡比例',
  explained_first: '首成分解释占比',
  explained_total: '累计解释占比',
  mean_relative_error: '平均相对误差',
  train_rows: '训练样本数',
  test_rows: '测试样本数',
  numeric_columns: '数值列数',
  constant_columns: '常数列数',
  high_missing_columns: '高缺失列数',
  high_cardinality_columns: '高基数列数',
  cells: '单元格数',
  row_variable: '行变量',
  column_variable: '列变量',
  overall_mean: '总体均值',
  largest_group: '最大分组',
  largest_count: '最大分组样本数',
  smallest_group: '最小分组',
  smallest_count: '最小分组样本数',
  required_per_group: '每组所需样本数',
  required_second_group: '第二组所需样本数',
  required_total: '所需总样本数',
  alpha: '显著性水平 / 参数 α',
  target_power: '目标检验功效',
  effect_size: '效应量',
  first_correlation: '首对典型相关系数',
  mean_shared_variance: '平均共享方差',
  max_vif: '最大 VIF',
  worst_feature: '最高 VIF 特征',
  count_over_threshold: '超阈值特征数',
  mean_vif: '平均 VIF',
  direct_effect: '直接效应',
  indirect_effect: '间接效应',
  total_effect: '总效应',
  interaction_beta: '交互项系数',
  interaction_p: '交互项 p 值',
  adf_statistic: 'ADF 统计量',
  adf_p_value: 'ADF p 值',
  stationary_by_adf: 'ADF 判定平稳',
  kpss_statistic: 'KPSS 统计量',
  kpss_p_value: 'KPSS p 值',
  stationary_by_kpss: 'KPSS 判定平稳',
  order: '模型阶数',
  seasonal_order: '季节阶数',
  next_forecast: '下一步预测值',
  ljung_box_p: 'Ljung–Box p 值',
  cointegrated_pairs: '协整变量对数',
  significant_pairs: '显著变量对数',
  strongest_pair: '最强关联变量对',
  smallest_p: '最小 p 值',
  did_effect: 'DID 效应',
  did_p_value: 'DID p 值',
  att_effect: 'ATT 效应',
  matched_pairs: '匹配对数',
  matched_controls: '匹配对照数',
  imbalanced_after: '匹配后不平衡变量数',
  local_linear_effect: '局部线性效应',
  local_linear_p: '局部线性 p 值',
  actual_effect: '实际效应',
  placebo_mean: '安慰剂效应均值',
  selection_bias: '是否存在选择偏差',
  lambda_p_value: '选择偏差 p 值',
  indicators: '指标数',
  objects: '评价对象数',
  factors: '因子数',
  runs: '试验次数',
  top_weight: '最大权重指标',
  top_weight_value: '最大权重',
  best_closeness: '最高贴近度',
  worst_closeness: '最低贴近度',
  best_compromise: '最小妥协指数',
  best_rsr: '最高 RSR',
  efficient_units: '有效决策单元数',
  mean_efficiency: '平均效率',
  best_score: '最高得分',
  best_grade: '最高关联度',
  dominant: '主导需求类型',
  top_option: '首选项',
  top_share: '首选项份额',
  most_important: '最重要属性',
  optimal_price: '最优价格',
  indifference_price: '无差异价格',
  out_of_control: '失控点数',
  center_line: '中心线',
  upper_control: '控制上限',
  lower_control: '控制下限',
  mean_life: '平均寿命',
  median_life: '中位寿命',
  b10_life: 'B10 寿命',
  expected_defect_rate: '预计不合格率',
  heterogeneity: '异质性',
  q_p_value: '异质性检验 p 值',
  treatments: '处理组数',
  blocks: '区组数',
  posthoc: '事后比较',
  group_nps: '分组 NPS',
  zero_test: '与零比较',
  level: '水平',
  cumulative_ratio: '累计占比',
  class_names: '类别名称',
  columns_used: '使用列',
}
const countKeys = new Set(
  (
    'rows records observations evaluation_rows n n_obs columns features levels count total clusters noise_points ' +
    'missing missing_before missing_after imputed dropped rows_before rows_after duplicates duplicates_removed outliers ' +
    'components documents vocabulary vocabulary_size positive negative neutral positive_words negative_words ' +
    'negation_flips negation_window detail_rows topics respondents promoters passives detractors items options profiles ' +
    'attributes terms violation_points subgroups subgroup_size studies events censored groups split_train split_test split_validation ' +
    'outlier_cells treated_cells rows_with_outlier rows_dropped missing_cells_before missing_cells_after imputed_columns ' +
    'columns_with_missing skipped_columns duplicate_rows unique_rows duplicate_groups categorical_columns encoded_features created ' +
    'features_after features_total features_in features_out clipped_cells clipped_rows classes train_rows test_rows numeric_columns ' +
    'constant_columns high_missing_columns high_cardinality_columns cells largest_count smallest_count required_per_group ' +
    'required_second_group required_total cointegrated_pairs significant_pairs matched_pairs matched_controls imbalanced_after ' +
    'indicators objects factors runs efficient_units out_of_control treatments blocks'
  ).split(' '),
)
const percentKeys = new Set(
  (
    'accuracy train_accuracy test_accuracy precision precision_macro precision_weighted ' +
    'recall recall_macro recall_weighted ratio cumulative confidence_level survival_at_horizon accuracy_at_threshold ' +
    'explained_first explained_total mean_relative_error top_share expected_defect_rate target_power'
  ).split(' '),
)
const metadata = new Set([
  'label',
  'task',
  'category',
  'group',
  'method',
  'params',
  'parameters',
  'data',
  'figures',
  'notes',
  'warnings',
  'tables',
  'metrics',
  'elapsed_ms',
  'split_fingerprint',
  'dataset',
  'dataset_label',
  'source',
])

export function displayLabel(key: string): string {
  return labels[key] ?? learnerText(key.replace(/_/g, ' '))
}

export function displayValue(value: unknown, key = ''): string {
  if (value === null || value === undefined || value === '') return '未提供'
  if (key === 'evaluation_scope' || key === 'fit_scope') {
    if (value === 'held_out_test') return '留出测试集'
    if (value === 'training_only') return '训练集'
  }
  if (key === 'coefficient_plot_status') {
    if (value === 'unavailable_inference') return '推断不可用'
    if (value === 'not_generated') return '未生成'
    if (value === 'generated') return '已生成'
  }
  if (key === 'diagnostic_plot' && value === 'confusion_matrix') return '分类混淆矩阵'
  if (Array.isArray(value)) {
    if (key === 'order' || key === 'seasonal_order') return `(${value.map(String).join(', ')})`
    return value.map((item) => displayValue(item)).join('、')
  }
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '未提供'
    if (percentKeys.has(key)) return `${(value * 100).toFixed(1)}%`
    if (countKeys.has(key)) return String(value)
    if (value !== 0 && Math.abs(value) < 0.0001) return value.toExponential(2)
    return value.toFixed(4)
  }
  return typeof value === 'object'
    ? JSON.stringify(learnerValue(value))
    : learnerText(String(value))
}

/** Nested library results and older flat results share one set of labels and formatting. */
export function entryMetrics(
  entry: MetricEntry,
  method = String(entry.method ?? ''),
): DisplayMetric[] {
  const merged: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(entry)) if (!metadata.has(key)) merged[key] = value
  if (entry.metrics && typeof entry.metrics === 'object' && !Array.isArray(entry.metrics)) {
    for (const [key, value] of Object.entries(entry.metrics))
      if (!metadata.has(key)) merged[key] = value
  }
  return Object.entries(merged)
    .filter(
      ([, value]) =>
        (typeof value === 'number' && Number.isFinite(value)) ||
        typeof value === 'boolean' ||
        (typeof value === 'string' && value.trim() !== '') ||
        (Array.isArray(value) &&
          value.length > 0 &&
          value.every(
            (item) =>
              item === null ||
              typeof item === 'string' ||
              typeof item === 'boolean' ||
              (typeof item === 'number' && Number.isFinite(item)),
          )),
    )
    .map(([key, value]) => ({
      key,
      label:
        method === 'ml.knn' && key === 'p'
          ? '距离阶数 p'
          : key === 'classes' && Array.isArray(value)
            ? '类别标签'
            : displayLabel(key),
      value: method === 'ml.knn' && key === 'p' ? String(value) : displayValue(value, key),
    }))
}

export function messages(value: unknown): string[] {
  const list = Array.isArray(value) ? value : typeof value === 'string' ? [value] : []
  return [
    ...new Set(
      list
        .filter((item): item is string => typeof item === 'string' && Boolean(item.trim()))
        .map(learnerText),
    ),
  ]
}
