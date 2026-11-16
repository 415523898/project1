import type { MethodGraph } from '@/types'

export const METHOD_GRAPH: MethodGraph = {
 "cards": [
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "数据清洗",
   "id": "prep.outliers",
   "inputs": [
    "数据表"
   ],
   "kind": "数据清洗",
   "label": "异常值处理",
   "level": 2,
   "math": {
    "conditions": "极端值可能是真实信号；不同分位数插值约定会改变边界。预测任务只从训练集估计阈值。",
    "example": "教学示例（非真实实验）：Q1=2、Q3=6、k=1.5，IQR=4，边界为 [-4,12]；13 被标记。",
    "formula": "IQR=Q_3-Q_1,\\quad [L,U]=[Q_1-kIQR,Q_3+kIQR]",
    "meaning": "把落在四分位区间扩展边界之外的观测标为异常候选。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · iqr",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.iqr.html"
     }
    ],
    "steps": "先选列并估计边界，再标记；report、clip、winsorize、drop 分别报告、截断、缩尾或删行。z-score 比较标准分数，MAD 比较中位数绝对偏差，不能共用 IQR 阈值。",
    "symbols": "$Q_1,Q_3$ 为四分位数；$k$ 为倍数（通常 1.5）；$L,U$ 为下上界。",
    "variant": "默认 IQR 检测；另有 z-score 与 MAD，默认 report 不删除样本。",
    "version": 1
   },
   "missing": [],
   "more": [
    "prep.winsorize",
    "prep.transform"
   ],
   "needs": null,
   "note": "IQR / Z 分数识别并按截断或缩尾处理。",
   "outputs": [
    "清洗后数据"
   ],
   "scenarios": [
    "数据清洗"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification",
    "regression",
    "clustering"
   ],
   "when": "个别点明显偏离其余样本、又确认不是录入错误时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "数据清洗",
   "id": "prep.missing",
   "inputs": [
    "数据表"
   ],
   "kind": "数据清洗",
   "label": "缺失值处理",
   "level": 2,
   "math": {
    "conditions": "填补不能消除非随机缺失偏差；训练/测试隔离，目标标签不随意填补；整列缺失没有可估计的中位数。",
    "example": "教学示例（非真实实验）：[1,缺失,5] 的非缺失中位数为 3，得到 [1,3,5]。",
    "formula": "\\tilde x_i=\\begin{cases}x_i,&x_i\\text{ observed}\\\\m,&x_i\\text{ missing}\\end{cases}",
    "meaning": "这是中位数填补的分段规则，不是所有缺失处理的统一公式。",
    "sources": [
     {
      "section": "Filling missing data; interpolation; dropping missing data",
      "title": "pandas · 缺失数据",
      "url": "https://pandas.pydata.org/docs/user_guide/missing_data.html"
     },
     {
      "section": "Univariate versus multivariate imputation",
      "title": "scikit-learn · Univariate versus multivariate imputation",
      "url": "https://scikit-learn.org/stable/modules/impute.html"
     }
    ],
    "steps": "先报告缺失比例与机制，再选策略。KNN 从邻居估计，迭代填补逐列建模；时序插值与前向填充依赖排序。",
    "symbols": "$x_i$ 为原观测；$m$ 为拟合样本的非缺失中位数；$\\tilde x_i$ 为填补后数值。",
    "variant": "默认中位数填补；均值、众数、插值、前向填充、KNN、迭代和删除为不同规则。",
    "version": 1
   },
   "missing": [],
   "more": [
    "prep.encoding",
    "prep.derive",
    "prep.balance",
    "prep.scale"
   ],
   "needs": null,
   "note": "均值/中位数/众数填充、KNN 填充、迭代回归填充。",
   "outputs": [
    "清洗后数据"
   ],
   "scenarios": [
    "数据清洗"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.duplicates"
   ],
   "tasks": [
    "classification",
    "regression",
    "clustering"
   ],
   "when": "表格里有空缺，而且不能直接把整行丢掉时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "数据清洗",
   "id": "prep.duplicates",
   "inputs": [
    "数据表"
   ],
   "kind": "数据清洗",
   "label": "重复值处理",
   "level": 2,
   "math": {
    "conditions": "先核对业务主键与重复测量；默认特征键未必包含目标、分组和时间列。",
    "example": "教学示例（非真实实验）：键为城市，trim_lower 后 ' A ' 与 'a' 属于同组；keep=first 将后者标记为重复。",
    "formula": "",
    "meaning": "重复指选定键相等，不等于所有业务含义相同。",
    "sources": [
     {
      "section": "subset and keep; compare local drop behavior",
      "title": "pandas · duplicated",
      "url": "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.duplicated.html"
     }
    ],
    "steps": "选择键 → 文本归一化 → 将缺失值按查重规则比较 → 标记重复组 → 报告/删行/增添标记。drop时keep=first/last保留首/末条，keep=none对应pandas keep=False，删除重复组全部成员。",
    "symbols": "键是参与比较的列；keep 决定标记口径；normalize 决定是否去空格、统一大小写。",
    "variant": "按选定键、文本归一化和 keep 规则查重；默认 report。没有统一数学目标函数。",
    "version": 1
   },
   "missing": [],
   "more": [
    "prep.missing"
   ],
   "needs": null,
   "note": "识别并去重。",
   "outputs": [
    "清洗后数据"
   ],
   "scenarios": [
    "数据清洗"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification",
    "regression",
    "clustering"
   ],
   "when": "合并了多张表或采集存在重复提交，要先确认唯一性时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "特征工程",
   "id": "prep.encoding",
   "inputs": [
    "数据表",
    "特征矩阵"
   ],
   "kind": "特征构造",
   "label": "数据编码",
   "level": 3,
   "math": {
    "conditions": "无序类别的整数编码不代表距离；目标编码若用测试标签或训练样本自身目标会泄漏，需要折外估计等保护。",
    "example": "教学示例（非真实实验）：A 的两个训练目标为 2、4，均值编码为 3；onehot 的 A 行则为 [1,0]（另一个类别为 B）。",
    "formula": "z_{ic}=\\mathbf1(x_i=c),\\qquad e(c)=\\frac{1}{n_c}\\sum_{i:x_i=c}y_i",
    "meaning": "左式把类别展开成指示列；右式是均值目标编码，两者不可混同。",
    "sources": [
     {
      "section": "Standardization; scaling; encoding categorical features; power transforms",
      "title": "scikit-learn · Standardization; scaling; encoding categorical features; power transforms",
      "url": "https://scikit-learn.org/stable/modules/preprocessing.html"
     }
    ],
    "steps": "先确定类别字典与未知类别策略；ordinal 按指定顺序映射整数；target 仅在训练数据上估计。",
    "symbols": "$c$ 为类别；$n_c$ 为该类别拟合样本数；$y_i$ 为目标；$z_{ic}$ 为 0/1 指示值。",
    "variant": "onehot / ordinal / target；target 可取组内均值或中位数。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "独热、序号、目标编码。",
   "outputs": [
    "新特征"
   ],
   "scenarios": [
    "特征构造"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.missing"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "有分类变量要送进模型，而模型只吃数值时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "特征工程",
   "id": "prep.derive",
   "inputs": [
    "数据表",
    "特征矩阵"
   ],
   "kind": "特征构造",
   "label": "生成变量",
   "level": 3,
   "math": {
    "conditions": "避免未来信息、目标泄漏和不合理量纲；高次多项式会放大极值。",
    "example": "教学示例（非真实实验）：x1=2、x2=4，交互=8、比例=0.5；x1 的平方=4。",
    "formula": "z=x_1x_2,\\quad r=\\frac{x_1}{x_2},\\quad p=x^d",
    "meaning": "交互刻画乘积关系，比例刻画相对量，多项式允许弯曲关系；分箱按边界离散化。",
    "sources": [
     {
      "section": "Standardization; scaling; encoding categorical features; power transforms",
      "title": "scikit-learn · Standardization; scaling; encoding categorical features; power transforms",
      "url": "https://scikit-learn.org/stable/modules/preprocessing.html"
     }
    ],
    "steps": "选列与规则 → 检查零分母及单位 → 构造特征；分箱可用等宽、分位数或 KMeans 边界。",
    "symbols": "$x_1,x_2$ 为原特征；$d$ 为次数；$z,r,p$ 为派生特征。",
    "variant": "interaction、ratio、polynomial、bin 各自构造不同特征。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "比值、乘积、多项式、分箱离散化。",
   "outputs": [
    "新特征"
   ],
   "scenarios": [
    "特征构造"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.missing"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "现成字段不够用，需要从原始列组合出更有解释力的变量时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "特征工程",
   "id": "prep.winsorize",
   "inputs": [
    "数据表",
    "特征矩阵"
   ],
   "kind": "特征构造",
   "label": "缩尾处理 Winsorize",
   "level": 2,
   "math": {
    "conditions": "分位数缩尾会改变尾部分布；不等同删掉离群样本。",
    "example": "教学示例（非真实实验）：边界 [2,8]，原值 [1,5,10] 变为 [2,5,8]。",
    "formula": "x_i'=\\min(U,\\max(L,x_i))",
    "meaning": "把边界外数值替换为边界，保留行数。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · mstats.winsorize",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mstats.winsorize.html"
     }
    ],
    "steps": "选列 → 从拟合样本估计边界 → 按 side 只处理下侧、上侧或双侧 → 对比受影响记录。",
    "symbols": "$L,U$ 为当前策略估计的下上界；$x_i'$ 为截断后的观测。",
    "variant": "默认分位数缩尾；支持 IQR、zscore、MAD 边界和单侧处理。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "按分位数压缩极端值。",
   "outputs": [
    "新特征"
   ],
   "scenarios": [
    "特征构造"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.outliers"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "想保留极端值的存在、但不让它主导结果时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "特征工程",
   "id": "prep.transform",
   "inputs": [
    "数据表",
    "特征矩阵"
   ],
   "kind": "特征构造",
   "label": "数据变换 Box-Cox / Yeo-Johnson",
   "level": 2,
   "math": {
    "conditions": "不能把 Box-Cox 套在零或负数；比较结果时注明后续是否标准化。",
    "example": "教学示例（非真实实验）：Box-Cox 的 λ=0、x=e 时输出 1；Yeo-Johnson 的 λ=1 时是恒等变换。",
    "formula": "T_\\lambda(x)=\\begin{cases}(x^\\lambda-1)/\\lambda,&\\lambda\\ne0\\\\\\log x,&\\lambda=0\\end{cases}",
    "meaning": "幂变换缓解偏态；不是保证正态的定理。",
    "sources": [
     {
      "section": "Standardization; scaling; encoding categorical features; power transforms",
      "title": "scikit-learn · Standardization; scaling; encoding categorical features; power transforms",
      "url": "https://scikit-learn.org/stable/modules/preprocessing.html"
     },
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · boxcox",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.boxcox.html"
     },
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · yeojohnson",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.yeojohnson.html"
     }
    ],
    "steps": "检查定义域 → 估计 λ → 变换。Yeo-Johnson 对 x≥0 用 Box-Cox(x+1)，对 x<0 用负的 Box-Cox(1−x,2−λ)；log 与 sqrt 有各自定义域。",
    "symbols": "$x>0$ 为 Box-Cox 输入；$\\lambda$ 为幂参数，通常用似然估计。",
    "variant": "Yeo-Johnson 默认；下式展示 Box-Cox 正数分支，Yeo-Johnson 另含负数分支。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "稳定方差、接近正态。",
   "outputs": [
    "新特征"
   ],
   "scenarios": [
    "特征构造"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.outliers"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "变量明显右偏、方差随均值增大，想让分布接近正态时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "特征工程",
   "id": "prep.balance",
   "inputs": [
    "分类目标"
   ],
   "kind": "特征构造",
   "label": "样本均衡",
   "level": 3,
   "math": {
    "conditions": "不要重采样测试集；SMOTE 需要足够同类近邻，不能直接把类别整数当连续坐标。",
    "example": "教学示例（非真实实验）：80/20 的二分类，权重为 100/(2×80)=0.625 与 2.5；SMOTE 在 2 和 4 之间 u=0.5 生成 3。",
    "formula": "w_c=\\frac{n}{K n_c},\\qquad x_{new}=x_i+u(x_{nn}-x_i),\\quad u\\in[0,1]",
    "meaning": "左式为平衡类权重；右式仅是 SMOTE 的线性插值。",
    "sources": [
     {
      "section": "SMOTE: sample generation",
      "title": "imbalanced-learn · Over-sampling",
      "url": "https://imbalanced-learn.org/stable/over_sampling.html"
     },
     {
      "section": "balanced heuristic",
      "title": "scikit-learn · compute_class_weight",
      "url": "https://scikit-learn.org/stable/modules/generated/sklearn.utils.class_weight.compute_class_weight.html"
     }
    ],
    "steps": "先划分数据 → 统计训练类别 → 按策略重采样或计算权重 → 在原始分布测试集评价。",
    "symbols": "$n$ 为训练记录数，$K$ 为类别数，$n_c$ 为类别频数；$x_{nn}$ 为同类近邻。",
    "variant": "默认报告；weights、随机过/欠采样、SMOTE 为不同策略。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "类别权重、随机过采样、SMOTE、欠采样；重采样选项需要 imbalanced-learn，权重与分布报告不需要。",
   "outputs": [
    "清洗后数据"
   ],
   "scenarios": [
    "特征构造"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.missing"
   ],
   "tasks": [
    "classification"
   ],
   "when": "分类样本严重不平衡，模型只会预测多数类时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "特征工程",
   "id": "prep.scale",
   "inputs": [
    "数据表",
    "特征矩阵"
   ],
   "kind": "特征构造",
   "label": "标准化与归一化",
   "level": 3,
   "math": {
    "conditions": "zscore 不等于样本标准差 ddof=1；尺度敏感模型受影响，树模型通常无需标准化。",
    "example": "教学示例（非真实实验）：[2,4] 的 μ=3、σ=1，zscore 为 [-1,1]；minmax 为 [0,1]。",
    "formula": "z_i=\\frac{x_i-\\mu}{\\sigma},\\quad\\sigma^2=\\frac1n\\sum_i(x_i-\\mu)^2;\\qquad u_i=\\frac{x_i-x_{min}}{x_{max}-x_{min}}",
    "meaning": "统一尺度；右式为映射到 [0,1] 的 minmax。",
    "sources": [
     {
      "section": "Standardization; scaling; encoding categorical features; power transforms",
      "title": "scikit-learn · Standardization; scaling; encoding categorical features; power transforms",
      "url": "https://scikit-learn.org/stable/modules/preprocessing.html"
     }
    ],
    "steps": "只从训练集估计变换量 → 对验证/测试应用同一规则。robust 用中位数与 IQR，maxabs 除以最大绝对值；常数列需保护零分母。",
    "symbols": "$\\mu,\\sigma$ 为拟合样本均值与标准差；$n$ 为拟合样本数；$x_{min},x_{max}$ 为边界。",
    "variant": "默认 zscore（StandardScaler，总体式方差 ddof=0）；另有 minmax、robust、maxabs。",
    "version": 1
   },
   "missing": [],
   "more": [
    "prep.tsne",
    "prep.pca",
    "model.ridge",
    "model.lasso",
    "model.elasticnet",
    "ml.kmeans",
    "ml.hierarchical",
    "ml.dbscan",
    "ml.svm",
    "ml.knn",
    "ml.mlp",
    "ml.rbf",
    "ml.lda_qda"
   ],
   "needs": null,
   "note": "Z 分数与 Min-Max。",
   "outputs": [
    "新特征"
   ],
   "scenarios": [
    "特征构造"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.missing"
   ],
   "tasks": [
    "classification",
    "regression",
    "clustering"
   ],
   "when": "变量量纲相差很大，而方法依赖距离或梯度时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "降维",
   "id": "prep.tsne",
   "inputs": [
    "特征矩阵"
   ],
   "kind": "降维",
   "label": "t-SNE 降维可视化",
   "level": 8,
   "math": {
    "conditions": "坐标轴和全局簇间距离通常无解释；随机种子和困惑度会改变图，不是聚类显著性证据。",
    "example": "教学示例（非真实实验）：某对点 p=0.2、q=0.1，则该项为 0.2 ln 2≈0.1386；总 KL 还需对全部有序点对求和。",
    "formula": "KL(P\\Vert Q)=\\sum_{i\\ne j}p_{ij}\\log\\frac{p_{ij}}{q_{ij}},\\qquad q_{ij}\\propto(1+\\|z_i-z_j\\|^2)^{-1}",
    "meaning": "让低维邻居概率接近高维邻居概率，主要保留局部邻域。",
    "sources": [
     {
      "section": "t-SNE objective and perplexity",
      "title": "scikit-learn · t-SNE objective and perplexity",
      "url": "https://scikit-learn.org/stable/modules/manifold.html#t-sne"
     }
    ],
    "steps": "缩放 → 用困惑度确定邻域带宽 → 构造 P → 初始化 → 迭代降低 KL。",
    "symbols": "$p_{ij}$ 为对称化高维相似概率，$q_{ij}$ 为低维概率，$z_i$ 为嵌入坐标。",
    "variant": "二维/低维可视化；Barnes-Hut 与 exact 是近似和精确优化路线。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "非线性降维散点。",
   "outputs": [
    "降维坐标"
   ],
   "scenarios": [
    "降维与可视化"
   ],
   "similar": [
    "prep.pca"
   ],
   "similar_why": {
    "prep.pca": "用于低维可视化时可比较两者：PCA 保留总体方差，t-SNE 侧重局部邻域；后者不能作为一般下游建模的等价替换。"
   },
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "classification",
    "regression",
    "clustering"
   ],
   "when": "只想看看高维数据能不能分成几团，不打算用降维结果建模时。"
  },
  {
   "after": [
    "eval.pca"
   ],
   "before": [
    "model.correlation"
   ],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "降维",
   "id": "prep.pca",
   "inputs": [
    "特征矩阵"
   ],
   "kind": "降维",
   "label": "主成分分析 PCA",
   "level": 8,
   "math": {
    "conditions": "协方差分母是 n−1；scale=none 不做标准化但仍中心化；主成分大方差不保证预测价值。",
    "example": "教学示例（非真实实验）：中心化矩阵 $X_c=\\begin{bmatrix}-1&-1\\\\1&1\\end{bmatrix}$，$S=\\begin{bmatrix}2&2\\\\2&2\\end{bmatrix}$；第一轴 $(1,1)/\\sqrt2$，方差 4、得分 $\\pm\\sqrt2$。",
    "formula": "S=\\frac{X_c^\\top X_c}{n-1},\\quad Sv_j=\\lambda_jv_j,\\quad Z=X_cV_k",
    "meaning": "找到保留最大方差的正交投影，不使用目标标签。",
    "sources": [
     {
      "section": "PCA: centered data, singular values and explained variance",
      "title": "scikit-learn · PCA: centered data, singular values and explained variance",
      "url": "https://scikit-learn.org/stable/modules/decomposition.html#pca"
     }
    ],
    "steps": "拟合缩放 → 中心化 → SVD/特征分解 → 按解释方差选 k → 投影；白化还会再缩放得分。",
    "symbols": "$X_c$ 为 n×p 中心化矩阵；$v_j$ 为单位特征向量；$\\lambda_j$ 为方差；$V_k$ 为前 k 列向量。",
    "variant": "先按 scale 参数变换；随后 PCA 中心化。主成分符号可整体翻转。",
    "version": 1
   },
   "missing": [],
   "more": [
    "eval.factor"
   ],
   "needs": null,
   "note": "碎石图与载荷图。",
   "outputs": [
    "降维坐标"
   ],
   "scenarios": [
    "降维与可视化"
   ],
   "similar": [
    "prep.tsne"
   ],
   "similar_why": {
    "prep.tsne": "用于低维可视化时可比较两者：PCA 保留总体方差，t-SNE 侧重局部邻域；后者不能作为一般下游建模的等价替换。"
   },
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "classification",
    "regression",
    "clustering"
   ],
   "when": "变量多且高度相关，想压成少数几个综合维度再往下做时。"
  },
  {
   "after": [],
   "before": [],
   "category": "prep",
   "category_name": "数据准备与特征工程",
   "group": "时序特征",
   "id": "prep.spectral",
   "inputs": [
    "时间序列"
   ],
   "kind": "特征构造",
   "label": "时序谱特征",
   "level": 9,
   "math": {
    "conditions": "需要近似等间隔采样；功率、幅度、单边加倍与归一化不同，不能直接比较不同口径。",
    "example": "教学示例（非真实实验）：[1,−1,1,−1]，Δt=1；k=2 的 FFT 值为 4，频率 0.5，表示每 2 个采样重复。",
    "formula": "X_k=\\sum_{t=0}^{n-1}x_t e^{-2\\pi\\mathrm{i}kt/n},\\quad f_k=\\frac{k}{n\\Delta t}",
    "meaning": "把等间隔序列分解为不同频率的复数振幅。",
    "sources": [
     {
      "section": "Discrete Fourier transforms; normalization",
      "title": "SciPy · Fourier transforms",
      "url": "https://docs.scipy.org/doc/scipy/tutorial/fft.html"
     }
    ],
    "steps": "按时间排序 → 去趋势/加窗 → FFT → 取正频率 → 根据幅度或功率约定找峰值。",
    "symbols": "$n$ 为长度，$\\Delta t$ 为采样间隔，$k$ 为频率索引，$\\mathrm{i}^2=-1$。",
    "variant": "FFT 频谱；窗、去趋势、采样间隔及是否功率谱决定数值尺度。",
    "version": 1
   },
   "missing": [],
   "more": [
    "series.sarima"
   ],
   "needs": null,
   "note": "FFT 主频、谱熵、能量占比。",
   "outputs": [
    "新特征"
   ],
   "scenarios": [
    "特征构造",
    "时序预测"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "拿到的是长时间序列，想用频域特征描述它的周期结构时。"
  },
  {
   "after": [
    "test.gof",
    "domain.wordfreq",
    "domain.kano"
   ],
   "before": [],
   "category": "describe",
   "category_name": "基础统计与描述性分析",
   "group": "描述统计",
   "id": "describe.frequency",
   "inputs": [
    "分类变量"
   ],
   "kind": "描述统计",
   "label": "频数分析",
   "level": 1,
   "math": {
    "conditions": "隐藏缺失时分母为非缺失数，包含缺失时分母为全部记录数；Top 或占比筛选后不重新归一化，真实类别与缺失标记分开。",
    "example": "教学示例（非真实实验）：A,A,空值：隐藏缺失时 A 频数2、频率1；包含缺失时 A 频率2/3、空值频率1/3。",
    "formula": "p_c=\\frac{n_c}{\\sum_j n_j}",
    "meaning": "统计每一类占当前缺失口径下有效分母的比例。",
    "sources": [
     {
      "section": "normalize and dropna",
      "title": "pandas · value_counts",
      "url": "https://pandas.pydata.org/docs/reference/api/pandas.Series.value_counts.html"
     }
    ],
    "steps": "先决定是否包含缺失 → 统计各类别 → 除以对应总数 → 排序与筛选；加权频数需要另行声明权重。",
    "symbols": "$n_c$ 为类别 c 次数，$p_c$ 为频率；分母在类别筛选前确定。",
    "variant": "默认排除缺失并按有效观测计频率；包含缺失时按全部记录计频率。",
    "version": 1
   },
   "missing": [],
   "more": [
    "describe.crosstab",
    "domain.nps"
   ],
   "needs": null,
   "note": "分类变量频数与占比。",
   "outputs": [
    "汇总表"
   ],
   "scenarios": [
    "分布探索"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "想先知道每个分类变量有哪些取值、各占多少时。"
  },
  {
   "after": [
    "test.ttest",
    "test.anova",
    "test.wilcoxon",
    "test.mannwhitney",
    "test.kruskal",
    "test.friedman",
    "model.correlation",
    "series.garch",
    "series.moran",
    "domain.cox",
    "domain.competing",
    "domain.control",
    "domain.meta"
   ],
   "before": [],
   "category": "describe",
   "category_name": "基础统计与描述性分析",
   "group": "描述统计",
   "id": "describe.stats",
   "inputs": [
    "数据表"
   ],
   "kind": "描述统计",
   "label": "描述性统计",
   "level": 1,
   "math": {
    "conditions": "样本方差和均值t区间要求 n>1；t区间还需核对独立性与分布条件；标准差是方差开平方，有原量纲。",
    "example": "教学示例（非真实实验）：[1,2,3] 均值 2；样本方差 1，总体式方差 2/3。",
    "formula": "\\bar x=\\frac1n\\sum_i x_i,\\quad s^2=\\frac{\\sum_i(x_i-\\bar x)^2}{n-1},\\quad\\sigma_N^2=\\frac{\\sum_i(x_i-\\bar x)^2}{n}",
    "meaning": "均值描述中心，方差描述平方离散程度。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · describe",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.describe.html"
     },
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · sem",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.sem.html"
     },
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · ttest_1samp",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_1samp.html"
     }
    ],
    "steps": "逐列去除缺失 → 算中心、分位数与离散量 → 明确标准差样本/总体模式 → 用样本标准误计算均值t区间。",
    "symbols": "$n$ 为非缺失数；$s^2$ 为样本方差；$\\sigma_N^2$ 为总体式方差。",
    "variant": "默认显示样本标准差；总体模式仅改变标准差展示口径，均值t区间独立使用样本标准误。",
    "version": 1
   },
   "missing": [],
   "more": [
    "describe.aggregate",
    "describe.explore",
    "ml.nb",
    "ml.trees",
    "series.adf",
    "eval.grey",
    "domain.km",
    "domain.reliability",
    "domain.maxdiff",
    "domain.conjoint",
    "domain.psm",
    "domain.weibull"
   ],
   "needs": null,
   "note": "均值、标准差、分位数、偏峰度。",
   "outputs": [
    "汇总表",
    "分布指标"
   ],
   "scenarios": [
    "分布探索"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "拿到一份新数据，第一件事是看集中趋势、离散程度和分布形状时。"
  },
  {
   "after": [
    "test.cochran",
    "test.chi2",
    "test.fisher"
   ],
   "before": [],
   "category": "describe",
   "category_name": "基础统计与描述性分析",
   "group": "描述统计",
   "id": "describe.crosstab",
   "inputs": [
    "分类变量"
   ],
   "kind": "描述统计",
   "label": "列联表",
   "level": 1,
   "math": {
    "conditions": "交叉表本身不是独立性检验；结构零、缺失类别和样本权重需要单独处理。",
    "example": "教学示例（非真实实验）：某行 [2,3]，行百分比 [40%,60%]。",
    "formula": "p_{j\\mid i}=\\frac{n_{ij}}{\\sum_j n_{ij}}",
    "meaning": "展示两个类别变量的联合分布；此式仅对应行百分比。",
    "sources": [
     {
      "section": "normalize",
      "title": "pandas · crosstab",
      "url": "https://pandas.pydata.org/docs/reference/api/pandas.crosstab.html"
     }
    ],
    "steps": "保留行类别并交叉计数 → 依 percent 选择分母 → 比较分布；列百分比改除列和，总百分比改除有效成对记录总数。",
    "symbols": "$n_{ij}$ 为第 i 行第 j 列频数；分母为第 i 行总数。",
    "variant": "列联计数及行/列/总百分比。",
    "version": 1
   },
   "missing": [],
   "more": [
    "causal.did"
   ],
   "needs": null,
   "note": "交叉频数与行列表百分比。",
   "outputs": [
    "汇总表"
   ],
   "scenarios": [
    "分布探索"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.frequency"
   ],
   "tasks": [
    "classification"
   ],
   "when": "两个分类变量放在一起，想看清交叉分布时。"
  },
  {
   "after": [],
   "before": [],
   "category": "describe",
   "category_name": "基础统计与描述性分析",
   "group": "描述统计",
   "id": "describe.aggregate",
   "inputs": [
    "分组列"
   ],
   "kind": "描述统计",
   "label": "分类汇总",
   "level": 1,
   "math": {
    "conditions": "组均值直接平均通常不等于全体均值，应按组样本数加权；std/var 核对 ddof。",
    "example": "教学示例（非真实实验）：A 组 [2,4] 均值 3；B 组 [9] 均值 9；全体均值 5。",
    "formula": "\\bar x_g=\\frac1{n_g}\\sum_{i\\in g}x_i",
    "meaning": "按分组分别汇总，不改变组内观测的定义。",
    "sources": [
     {
      "section": "Aggregation",
      "title": "pandas · GroupBy",
      "url": "https://pandas.pydata.org/docs/user_guide/groupby.html"
     }
    ],
    "steps": "选分组键 → 选统计量 → 分组计算；计数直接统计原列非缺失值，文本列也适用，空组计数为0。",
    "symbols": "$g$ 为组，$n_g$ 为该组非缺失数。",
    "variant": "按类别分组后，选择均值、求和、中位数、标准差、范围或非缺失计数等统计量。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "按分组变量聚合统计。",
   "outputs": [
    "汇总表"
   ],
   "scenarios": [
    "分布探索"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "想按某个分组变量分组求均值、求和或计数时。"
  },
  {
   "after": [],
   "before": [],
   "category": "describe",
   "category_name": "基础统计与描述性分析",
   "group": "描述统计",
   "id": "describe.explore",
   "inputs": [
    "数据表"
   ],
   "kind": "描述统计",
   "label": "数据探索",
   "level": 1,
   "math": {
    "conditions": "探索结果不能自动当成事先指定的显著性结论；相关不等于因果。",
    "example": "教学示例（非真实实验）：10 行中 2 行缺失，缺失率 20%；这不说明应自动删列。",
    "formula": "",
    "meaning": "先了解结构、分布、缺失、离群与变量关系，再决定正式模型。",
    "sources": [
     {
      "section": "Filling missing data; interpolation; dropping missing data",
      "title": "pandas · 缺失数据",
      "url": "https://pandas.pydata.org/docs/user_guide/missing_data.html"
     },
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · pearsonr",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html"
     }
    ],
    "steps": "查表结构 → 统计缺失与唯一值 → 看分布与散点 → 检查相关；保留观察和假设的区分。",
    "symbols": "记录数、列类型、缺失比例、分位数、相关系数分别反映不同性质。",
    "variant": "探索是多步骤诊断，没有单一公式；相关类型可选 Pearson/Spearman/Kendall。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "缺失、唯一值、类型、分布摘要。",
   "outputs": [
    "汇总表",
    "分布指标"
   ],
   "scenarios": [
    "分布探索"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "classification",
    "regression",
    "clustering"
   ],
   "when": "想一次扫完缺失、类型、唯一值和分布概览时。"
  },
  {
   "after": [],
   "before": [
    "test.ttest",
    "test.anova"
   ],
   "category": "describe",
   "category_name": "基础统计与描述性分析",
   "group": "功效分析",
   "id": "describe.power",
   "inputs": [
    "分组列"
   ],
   "kind": "统计检验",
   "label": "检验功效与样本量",
   "level": 11,
   "math": {
    "conditions": "Cohen d、比例差与 ANOVA f 不能互换；事后用观测效应计算的功效不替代区间估计。",
    "example": "教学示例（非真实实验）：功效 0.8 表示在给定备择假设下重复 100 次约有 80 次拒绝 H0，不是 H1 为真的概率 80%。",
    "formula": "1-\\beta=P_{H_1}(\\text{reject }H_0)",
    "meaning": "在指定真实效应下检出该效应的概率。",
    "sources": [
     {
      "section": "Power and sample size",
      "title": "statsmodels · Power and sample size",
      "url": "https://www.statsmodels.org/stable/stats.html#power-and-sample-size-calculations"
     }
    ],
    "steps": "确定检验类型与效应量 → 指定 α、样本量/目标功效 → 用相应分布数值求解。",
    "symbols": "$\\alpha$ 为一类错误率，$\\beta$ 为二类错误率；效应量、样本量和单双侧决定功效。",
    "variant": "t、proportion、anova 使用不同备择分布；下式是功效定义而非通用样本量闭式解。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "功效分析、最小样本量计算。",
   "outputs": [
    "评价指标"
   ],
   "scenarios": [
    "实验设计"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "实验开始之前，想算清楚最少要收多少样本时。"
  },
  {
   "after": [
    "describe.power",
    "test.anova"
   ],
   "before": [
    "describe.stats"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "参数检验",
   "id": "test.ttest",
   "inputs": [
    "两分组列",
    "连续目标"
   ],
   "kind": "统计检验",
   "label": "T 检验（单样本/独立/配对）",
   "level": 4,
   "math": {
    "conditions": "独立检验要求组间独立；配对检验要求差值近似正态或样本充分。auto 的方差分支依代码诊断，不能直接视为 Welch。",
    "example": "教学示例（非真实实验）：两组均值 5、3，样本方差均为 4，各 n=8，Welch 标准误=1，t=2，自由度14。",
    "formula": "t=\\frac{\\bar x-\\bar y}{\\sqrt{s_x^2/n_x+s_y^2/n_y}},\\quad\\nu=\\frac{(s_x^2/n_x+s_y^2/n_y)^2}{(s_x^2/n_x)^2/(n_x-1)+(s_y^2/n_y)^2/(n_y-1)}",
    "meaning": "用均值差相对标准误判断证据，Welch 不要求两组方差相等。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · ttest_ind",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html"
     },
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · ttest_1samp",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_1samp.html"
     },
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · ttest_rel",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_rel.html"
     }
    ],
    "steps": "单样本 t=(均值−μ0)/(s/√n)；配对先算每对差值再做单样本检验；等方差用合并方差 sp²=[(nx−1)sx²+(ny−1)sy²]/(nx+ny−2)，自由度 nx+ny−2。最后按备择方向计算 p。",
    "symbols": "$s_x^2,s_y^2$ 使用各自 n−1 分母；$\\nu$ 为 Welch-Satterthwaite 自由度。",
    "variant": "独立样本默认需核对 variance；此处先列 Welch，再给单样本/配对/等方差口径。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "scipy",
   "note": "三种 T 检验与效应量。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较"
   ],
   "similar": [
    "test.mannwhitney",
    "test.wilcoxon"
   ],
   "similar_why": {
    "test.mannwhitney": "两组独立样本可比较：T 检验针对均值，方差不齐可用 Welch；Mann–Whitney 针对分布差异，额外条件下才可解释位置差异。",
    "test.wilcoxon": "配对比较可选择配对 T 或 Wilcoxon 符号秩检验；后者检验差值分布是否关于零对称，不能只因偏态就直接替换。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "比较两组均值有没有差异，且样本近似正态时。"
  },
  {
   "after": [
    "describe.power",
    "design.factorial"
   ],
   "before": [
    "describe.stats",
    "test.ttest"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "参数检验",
   "id": "test.anova",
   "inputs": [
    "分组列",
    "连续目标"
   ],
   "kind": "统计检验",
   "label": "方差分析（单因素 / 协方差）",
   "level": 4,
   "math": {
    "conditions": "独立、残差近似正态、方差齐性；重复测量还需考虑被试相关与球形性；显著不说明所有组都不同。",
    "example": "教学示例（非真实实验）：k=3、n=9、SSB=12、SSW=6，F=(12/2)/(6/6)=6。",
    "formula": "F=\\frac{SS_B/(k-1)}{SS_W/(n-k)},\\quad SS_B=\\sum_gn_g(\\bar x_g-\\bar x)^2,\\quad SS_W=\\sum_g\\sum_i(x_{gi}-\\bar x_g)^2",
    "meaning": "比较组间均值变化与组内随机变化。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · f_oneway",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.f_oneway.html"
     },
     {
      "section": "ANOVA; repeated measures ANOVA",
      "title": "statsmodels · ANOVA; repeated measures ANOVA",
      "url": "https://www.statsmodels.org/stable/anova.html"
     }
    ],
    "steps": "明确设计 → 拟合相应线性模型 → 选正确平方和/误差项 → F 检验 → 必要时做经校正的事后比较。",
    "symbols": "$k$ 为组数，$n$ 为总样本量；$SS_B,SS_W$ 为组间、组内平方和。",
    "variant": "下式仅为单因素独立同方差 ANOVA；多因素/ANCOVA/重复测量使用不同设计与误差项。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "单因素独立组 ANOVA 与含一个协变量的 ANCOVA；不提供重复测量或多因素 ANOVA。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较"
   ],
   "similar": [
    "test.friedman",
    "test.kruskal"
   ],
   "similar_why": {
    "test.friedman": "仅在重复测量或配组设计下比较：重复测量 ANOVA 与 Friedman 的假设及检验目标不同，独立组 ANOVA 不可直接换成 Friedman。",
    "test.kruskal": "仅限多个独立组的比较：ANOVA 针对均值，Kruskal–Wallis 使用秩；将后者解释为位置差异需结合分布形状，不能直接替换重复测量 ANOVA。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "比较三组及以上均值，或要看因素之间的交互作用时。"
  },
  {
   "after": [],
   "before": [
    "describe.stats"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "非参数检验",
   "id": "test.wilcoxon",
   "inputs": [
    "两分组列",
    "连续目标"
   ],
   "kind": "统计检验",
   "label": "Wilcoxon 符号秩检验",
   "level": 4,
   "math": {
    "conditions": "配对间独立；位置解释需差值分布对称，不是任意分布下的中位数检验。",
    "example": "教学示例（非真实实验）：差为 [1,−2,3]，秩 1,2,3，W+=4、W−=2，双侧统计量 2。",
    "formula": "W^+=\\sum_{d_i>0}\\operatorname{rank}(|d_i|),\\quad W^-=\\sum_{d_i<0}\\operatorname{rank}(|d_i|)",
    "meaning": "同时使用差值方向和绝对差值的秩；双侧统计量常取两者较小值。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · wilcoxon",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html"
     }
    ],
    "steps": "算配对差 → 处理零 → 排绝对值秩 → 分别求正负秩和 → 按单双侧与精确/渐近分布求 p。",
    "symbols": "$d_i$ 为成对差；秩按绝对差排序，并列取平均秩。",
    "variant": "配对差值的 Wilcoxon 符号秩；零差值与并列秩按 zero_method 处理。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "scipy",
   "note": "配对样本的非参数替代。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较"
   ],
   "similar": [
    "test.ttest"
   ],
   "similar_why": {
    "test.ttest": "配对比较可选择配对 T 或 Wilcoxon 符号秩检验；后者检验差值分布是否关于零对称，不能只因偏态就直接替换。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "配对或重复测量数据，差值明显偏态时。"
  },
  {
   "after": [],
   "before": [
    "describe.stats"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "非参数检验",
   "id": "test.mannwhitney",
   "inputs": [
    "两分组列",
    "连续目标"
   ],
   "kind": "统计检验",
   "label": "Mann-Whitney U 检验",
   "level": 4,
   "math": {
    "conditions": "观测独立；只有分布形状等条件成立时才可主要解释为位置差；不能无条件称为中位数检验。",
    "example": "教学示例（非真实实验）：x=[1,2]、y=[3,4]，Rx=3，Ux=0，Uy=4。",
    "formula": "U_x=R_x-\\frac{n_x(n_x+1)}2,\\qquad U_y=n_xn_y-U_x",
    "meaning": "比较一组取值相对另一组的排序优势。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · mannwhitneyu",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mannwhitneyu.html"
     }
    ],
    "steps": "合并排名 → 求组秩和 → 算 U → 按备择方向和 method 求 p。",
    "symbols": "$R_x$ 为合并排序后 x 组秩和；$n_x,n_y$ 为两组大小。",
    "variant": "两独立样本秩和；精确与渐近、并列校正为不同 p 值口径。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "scipy",
   "note": "两独立样本的非参数替代。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较"
   ],
   "similar": [
    "test.ttest"
   ],
   "similar_why": {
    "test.ttest": "两组独立样本可比较：T 检验针对均值，方差不齐可用 Welch；Mann–Whitney 针对分布差异，额外条件下才可解释位置差异。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "两组独立样本，正态性或方差齐性不成立时。"
  },
  {
   "after": [],
   "before": [
    "describe.stats"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "非参数检验",
   "id": "test.kruskal",
   "inputs": [
    "分组列",
    "连续目标"
   ],
   "kind": "统计检验",
   "label": "Kruskal-Wallis H 检验",
   "level": 4,
   "math": {
    "conditions": "组间独立；分布形状不一致时不单纯反映中位数；显著后需校正的两两比较。",
    "example": "教学示例（非真实实验）：两组 [1,2]、[3,4] 的秩和为3、7，H=2.4。",
    "formula": "H=\\frac{12}{n(n+1)}\\sum_g\\frac{R_g^2}{n_g}-3(n+1)",
    "meaning": "比较多组的合并秩分布。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · kruskal",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kruskal.html"
     }
    ],
    "steps": "合并排名 → 计算 H → 有并列时除以校正因子 → 参考 χ²(k−1) 或更合适的小样本方法。",
    "symbols": "$R_g$ 为第 g 组秩和；$n_g$ 为组大小；$n=\\sum_g n_g$。",
    "variant": "独立多组的 Kruskal-Wallis；下式未做并列秩校正。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "scipy",
   "note": "多组非参数替代。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较"
   ],
   "similar": [
    "test.anova"
   ],
   "similar_why": {
    "test.anova": "仅限多个独立组的比较：ANOVA 针对均值，Kruskal–Wallis 使用秩；将后者解释为位置差异需结合分布形状，不能直接替换重复测量 ANOVA。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "三组及以上独立样本，不满足方差分析前提时。"
  },
  {
   "after": [],
   "before": [
    "describe.stats"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "非参数检验",
   "id": "test.friedman",
   "inputs": [
    "分组列"
   ],
   "kind": "统计检验",
   "label": "Friedman 检验",
   "level": 4,
   "math": {
    "conditions": "区组间独立、区组内配对完整；小样本 χ² 近似可能不准。",
    "example": "教学示例（非真实实验）：n=2、k=3，两行秩均 [1,2,3]，列秩和 [2,4,6]，Q=4。",
    "formula": "Q=\\frac{12}{nk(k+1)}\\sum_j R_j^2-3n(k+1)",
    "meaning": "先在每个区组内部排序，再比较各条件秩和。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · friedmanchisquare",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.friedmanchisquare.html"
     }
    ],
    "steps": "每行排名 → 汇总列秩和 → 并列校正 → 选 χ² 或 F 近似；F=(n−1)Q/[n(k−1)−Q]。",
    "symbols": "$n$ 为区组数，$k$ 为条件数，$R_j$ 为条件 j 的区组内秩和。",
    "variant": "同一被试/区组多条件的秩检验；可选 Iman-Davenport F 近似。",
    "version": 1
   },
   "missing": [],
   "more": [
    "test.cochran"
   ],
   "needs": "scipy",
   "note": "随机区组重复测量的非参数检验。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较"
   ],
   "similar": [
    "test.anova"
   ],
   "similar_why": {
    "test.anova": "仅在重复测量或配组设计下比较：重复测量 ANOVA 与 Friedman 的假设及检验目标不同，独立组 ANOVA 不可直接换成 Friedman。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "同一批对象在多个条件下重复测量，要做非参数比较时。"
  },
  {
   "after": [],
   "before": [
    "describe.crosstab"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "非参数检验",
   "id": "test.cochran",
   "inputs": [
    "分组列"
   ],
   "kind": "统计检验",
   "label": "Cochran's Q 检验",
   "level": 4,
   "math": {
    "conditions": "对象间独立；全为一致响应时分母可为零，不能报告常规 Q。",
    "example": "教学示例（非真实实验）：两对象响应 [1,0,0] 和 [1,1,0]，C=[2,1,0]、R=[1,2]、T=3，Q=3。",
    "formula": "Q=(k-1)\\frac{k\\sum_j C_j^2-T^2}{kT-\\sum_i R_i^2}",
    "meaning": "检验相关二元条件的成功率是否相同。",
    "sources": [
     {
      "section": "Cochran Q",
      "title": "statsmodels · Cochran Q",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.cochrans_q.html"
     }
    ],
    "steps": "核对 0/1 与配对 → 算行列和 → Q → χ²(k−1) 近似 → 必要时校正 McNemar 事后比较。",
    "symbols": "$C_j$ 为列成功数，$R_i$ 为行成功数，$T$ 为总成功数，$k$ 为条件数。",
    "variant": "同一对象 k 个二元条件的 Cochran Q。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "二分响应重复测量。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "test.friedman"
   ],
   "tasks": [
    "classification"
   ],
   "when": "同一批对象的二值响应在三个以上时点重复测量时。"
  },
  {
   "after": [],
   "before": [
    "describe.crosstab"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "离散数据检验",
   "id": "test.chi2",
   "inputs": [
    "分类变量"
   ],
   "kind": "统计检验",
   "label": "卡方检验",
   "level": 4,
   "math": {
    "conditions": "计数、独立抽样；期望频数太低时优先精确/模拟方法；2×2 Yates 校正会改变统计量。",
    "example": "教学示例（非真实实验）：O=[[8,2],[2,8]]，E 全为5，无校正 χ²=7.2。",
    "formula": "E_{ij}=\\frac{R_iC_j}{n},\\quad\\chi^2=\\sum_{ij}\\frac{(O_{ij}-E_{ij})^2}{E_{ij}}",
    "meaning": "比较独立假设下的期望频数与观测频数。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · chi2_contingency",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2_contingency.html"
     }
    ],
    "steps": "建频数表 → 算期望 → 按 statistic/correction 选统计量 → 渐近或 Monte Carlo 求 p。",
    "symbols": "$O,E$ 为观测和期望；$R,C$ 为边际频数；自由度 (r−1)(c−1)。",
    "variant": "下式为 Pearson 独立性 χ²、无连续性校正；另有 G 检验/Cressie-Read 等。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "scipy",
   "note": "列联表独立性检验。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较",
    "分类预测"
   ],
   "similar": [
    "test.fisher"
   ],
   "similar_why": {
    "test.fisher": "在同一 2×2 计数表上可检验独立性：卡方使用渐近近似，稀疏或小样本可考虑 Fisher 精确检验。"
   },
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "想知道两个分类变量是否相互独立时。"
  },
  {
   "after": [],
   "before": [
    "describe.frequency"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "离散数据检验",
   "id": "test.gof",
   "inputs": [
    "分类变量"
   ],
   "kind": "统计检验",
   "label": "卡方拟合优度检验",
   "level": 4,
   "math": {
    "conditions": "期望频数不可过小；已估参数时 df 通常为 k−1−参数数，小样本/数据驱动分箱须谨慎。",
    "example": "教学示例（非真实实验）：骰子两类简例 O=[8,12]、p=[0.5,0.5]，χ²=0.8。",
    "formula": "\\chi^2=\\sum_{j=1}^k\\frac{(O_j-np_j)^2}{np_j}",
    "meaning": "检验观测类别比例是否符合指定分布。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · chisquare",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chisquare.html"
     }
    ],
    "steps": "给定分箱/类别 → 估计或指定期望概率 → 核对总和 → 统计量 → 明确自由度扣除了几个估计参数。",
    "symbols": "$p_j$ 为零假设概率，$n$ 为总数，$k$ 为类别数。",
    "variant": "单变量类别频数拟合优度；uniform 和拟合 normal 的期望构造不同。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "scipy",
   "note": "观测分布与理论分布比较。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较",
    "分类预测"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "想检验观测频数是否符合某个理论分布或比例时。"
  },
  {
   "after": [],
   "before": [
    "describe.crosstab"
   ],
   "category": "test",
   "category_name": "差异性检验与假设检验",
   "group": "离散数据检验",
   "id": "test.fisher",
   "inputs": [
    "分类变量"
   ],
   "kind": "统计检验",
   "label": "Fisher 精确检验",
   "level": 4,
   "math": {
    "conditions": "抽样设计应符合条件分析；零单元会使样本 OR 为零/无穷，不应随意加0.5冒充原结果。",
    "example": "教学示例（非真实实验）：表全为1时样本 OR=1；该表概率为 4/6，双侧 p=1。",
    "formula": "P(A=a)=\\frac{\\binom{a+b}{a}\\binom{c+d}{c}}{\\binom{n}{a+c}},\\quad OR_{sample}=\\frac{ad}{bc}",
    "meaning": "在零假设与固定边际下枚举可行表，不依赖大样本 χ² 近似。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · fisher_exact",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html"
     }
    ],
    "steps": "计算观测表概率 → 按备择方向加总同样或更极端的表；双侧 p 不是简单把单侧翻倍。",
    "symbols": "表为 $\\begin{bmatrix}a&b\\\\c&d\\end{bmatrix}$；$n=a+b+c+d$。",
    "variant": "2×2 固定边际的精确检验；sample 与 conditional 比值比估计不同。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "scipy",
   "note": "小样本 2×2 精确检验。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "组间差异比较",
    "分类预测"
   ],
   "similar": [
    "test.chi2"
   ],
   "similar_why": {
    "test.chi2": "在同一 2×2 计数表上可检验独立性：卡方使用渐近近似，稀疏或小样本可考虑 Fisher 精确检验。"
   },
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "2×2 列联表里出现期望频数小于 5 的小样本时。"
  },
  {
   "after": [
    "prep.pca",
    "model.canonical",
    "model.vif",
    "model.linear",
    "ml.lda_qda",
    "eval.factor"
   ],
   "before": [
    "describe.stats"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "相关分析",
   "id": "model.correlation",
   "inputs": [
    "特征矩阵"
   ],
   "kind": "相关分析",
   "label": "相关分析",
   "level": 3,
   "math": {
    "conditions": "常数列分母为零；显著相关不证明因果；不同缺失样本集的相关不可直接比较。",
    "example": "教学示例（非真实实验）：x=[1,2,3]、y=[2,4,6]，r=1。",
    "formula": "r=\\frac{\\sum_i(x_i-\\bar x)(y_i-\\bar y)}{\\sqrt{\\sum_i(x_i-\\bar x)^2\\sum_i(y_i-\\bar y)^2}}",
    "meaning": "衡量线性共变方向与强度。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · pearsonr",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html"
     },
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · spearmanr",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html"
     },
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · kendalltau",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kendalltau.html"
     }
    ],
    "steps": "选相关类型 → 成对有效值 → 计算系数/检验 → 必要时多重校正。",
    "symbols": "$x_i,y_i$ 为成对观测；$r\\in[-1,1]$。",
    "variant": "Pearson 线性相关；Spearman 对秩算 Pearson，Kendall 用一致/不一致对。",
    "version": 1
   },
   "missing": [],
   "more": [
    "series.moran"
   ],
   "needs": null,
   "note": "Pearson、Spearman、Kendall、偏相关。",
   "outputs": [
    "相关系数"
   ],
   "scenarios": [
    "关联探索",
    "影响因素分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "想先判断哪些连续变量之间存在线性关联时。"
  },
  {
   "after": [],
   "before": [
    "model.correlation"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "相关分析",
   "id": "model.canonical",
   "inputs": [
    "特征矩阵"
   ],
   "kind": "相关分析",
   "label": "典型相关分析",
   "level": 8,
   "math": {
    "conditions": "样本量需支持协方差估计；共线和高维会使训练典型相关虚高，应做验证。",
    "example": "教学示例（非真实实验）：X 只有 x、Y 只有 2x 且 x 非常数时，第一典型相关为1。",
    "formula": "\\max_{a,b}\\ \\operatorname{corr}(Xa,Yb),\\quad a^\\top S_{XX}a=b^\\top S_{YY}b=1",
    "meaning": "寻找两组特征最相关的方向。",
    "sources": [
     {
      "section": "CCA",
      "title": "scikit-learn · CCA",
      "url": "https://scikit-learn.org/stable/modules/cross_decomposition.html#canonical-correlation-analysis"
     }
    ],
    "steps": "划分两组 → 中心化/缩放 → 解第一对方向 → 在约束下求后续正交方向。",
    "symbols": "$X,Y$ 为两组中心化数据，$a,b$ 为权重；$S$ 为样本协方差块。",
    "variant": "典型相关 CCA：两组变量的线性组合。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "sklearn",
   "note": "两组变量之间的相关结构。",
   "outputs": [
    "相关系数",
    "估计量与显著性"
   ],
   "scenarios": [
    "关联探索",
    "影响因素分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "一组自变量与一组因变量之间整体上怎么相关时。"
  },
  {
   "after": [],
   "before": [
    "model.correlation"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "相关分析",
   "id": "model.vif",
   "inputs": [
    "特征矩阵"
   ],
   "kind": "相关分析",
   "label": "VIF 共线性诊断",
   "level": 7,
   "math": {
    "conditions": "不用于证明因果或预测质量；完全共线趋于无穷；阈值不是普适定理。",
    "example": "教学示例（非真实实验）：Rj²=0.8，VIF=5。",
    "formula": "VIF_j=\\frac1{1-R_j^2}",
    "meaning": "度量该变量系数方差因共线性而膨胀的倍数。",
    "sources": [
     {
      "section": "Variance inflation factor",
      "title": "statsmodels · Variance inflation factor",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.stats.outliers_influence.variance_inflation_factor.html"
     }
    ],
    "steps": "逐列辅助回归 → 取 R² → 计算 VIF → 结合业务检查冗余。",
    "symbols": "$R_j^2$ 是用其他解释变量预测第 j 列的决定系数。",
    "variant": "每个解释变量对其余解释变量回归的共线诊断。",
    "version": 1
   },
   "missing": [],
   "more": [
    "model.ridge",
    "model.lasso"
   ],
   "needs": "statsmodels",
   "note": "方差膨胀因子与容忍度。",
   "outputs": [
    "模型诊断量"
   ],
   "scenarios": [
    "关联探索",
    "影响因素分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "回归之前想确认自变量之间有没有严重共线性时。"
  },
  {
   "after": [
    "model.ridge",
    "model.lasso",
    "model.logistic",
    "model.probit",
    "model.robust",
    "model.mediation",
    "model.moderation",
    "model.gamma",
    "model.poisson",
    "model.gee",
    "model.mixed",
    "series.panel",
    "series.threshold",
    "series.tobit",
    "series.quantile",
    "causal.did",
    "causal.rd"
   ],
   "before": [
    "model.correlation"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "回归分析",
   "id": "model.linear",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "线性回归",
   "level": 7,
   "math": {
    "conditions": "线性条件均值与外生性；同方差用于常规标准误；秩亏时需广义逆；拟合相关不自动是因果。",
    "example": "教学示例（非真实实验）：点 (0,1)、(1,3)、(2,5)，含截距 OLS 得 β0=1、β1=2，残差均为0。",
    "formula": "\\hat\\beta=\\arg\\min_\\beta\\|y-X\\beta\\|_2^2,\\qquad\\hat\\beta=(X^\\top X)^{-1}X^\\top y",
    "meaning": "寻找平方残差总和最小的线性预测。",
    "sources": [
     {
      "section": "OLS",
      "title": "scikit-learn · OLS",
      "url": "https://scikit-learn.org/stable/modules/linear_model.html#ordinary-least-squares"
     }
    ],
    "steps": "建矩阵 → 用数值分解拟合（非显式求逆） → 看残差、系数与区间 → 按划分评价。",
    "symbols": "$X$ 为设计矩阵（可含截距列），$y$ 为目标，$\\beta$ 为系数。右式要求满列秩。",
    "variant": "OLS；截距由参数决定，HC0/HC1/HC3 改标准误口径，不改 OLS 目标。",
    "version": 1
   },
   "missing": [],
   "more": [
    "domain.meta"
   ],
   "needs": "statsmodels",
   "note": "系数、标准误、t 值、R²。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "因变量连续，想量化各自变量的影响方向与大小并做预测时。"
  },
  {
   "after": [
    "model.elasticnet"
   ],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "回归分析",
   "id": "model.ridge",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "岭回归",
   "level": 7,
   "math": {
    "conditions": "此处未除 n，与 Lasso 的 α 尺度不同；缩放影响惩罚；通常不会产生严格零系数。",
    "example": "教学示例（非真实实验）：无截距，X=[1]、y=[2]、α=1，β=2/(1+1)=1。",
    "formula": "\\min_\\beta\\ \\|y-X\\beta\\|_2^2+\\alpha\\|\\beta\\|_2^2",
    "meaning": "收缩系数减轻方差和共线不稳定。",
    "sources": [
     {
      "section": "Ridge objective",
      "title": "scikit-learn · Ridge objective",
      "url": "https://scikit-learn.org/stable/modules/linear_model.html#ridge-regression-and-classification"
     }
    ],
    "steps": "训练集缩放 → 按参数/交叉验证选 α → 拟合 → 留出集验证。",
    "symbols": "$\\alpha\\ge0$ 为惩罚强度，$\\beta$ 为受惩罚系数。",
    "variant": "sklearn Ridge：残差和 + αL2；通常不惩罚截距。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "L2 正则与系数路径。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [
    "model.lasso"
   ],
   "similar_why": {
    "model.lasso": "都在线性回归上加正则：岭回归保留全部变量只压小系数，Lasso 会把系数压到 0 做特征选择。"
   },
   "suggests": [
    "prep.scale",
    "model.vif"
   ],
   "tasks": [
    "regression"
   ],
   "when": "自变量共线性强、样本数少于变量数，需要让系数稳定下来时。"
  },
  {
   "after": [
    "model.elasticnet"
   ],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "回归分析",
   "id": "model.lasso",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "Lasso 回归",
   "level": 7,
   "math": {
    "conditions": "强相关变量可能被不稳定选择；非零不意味着因果；α 不能直接套用 Ridge 口径。",
    "example": "教学示例（非真实实验）：n=1、X=[1]、y=[2]、无截距、α=0.5，软阈值解 β=1.5。",
    "formula": "\\min_\\beta\\ \\frac1{2n}\\|y-X\\beta\\|_2^2+\\alpha\\|\\beta\\|_1",
    "meaning": "L1 惩罚可把部分系数压到零。",
    "sources": [
     {
      "section": "Lasso objective",
      "title": "scikit-learn · Lasso objective",
      "url": "https://scikit-learn.org/stable/modules/linear_model.html#lasso"
     }
    ],
    "steps": "缩放 → 选 α → 坐标下降等优化 → 核查收敛与样本外误差。",
    "symbols": "$n$ 为训练行数；$\\alpha$ 为惩罚强度；$\\|\\beta\\|_1$ 为绝对值和。",
    "variant": "sklearn Lasso：平方误差除以 2n；截距通常不惩罚。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "L1 正则做特征选择。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [
    "model.ridge"
   ],
   "similar_why": {
    "model.ridge": "都在线性回归上加正则：岭回归保留全部变量只压小系数，Lasso 会把系数压到 0 做特征选择。"
   },
   "suggests": [
    "prep.scale",
    "model.vif"
   ],
   "tasks": [
    "regression"
   ],
   "when": "变量很多，想让模型自动把没用的系数压到 0 时。"
  },
  {
   "after": [],
   "before": [
    "model.ridge",
    "model.lasso"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "回归分析",
   "id": "model.elasticnet",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "ElasticNet",
   "level": 7,
   "math": {
    "conditions": "r=1 为 Lasso；r=0 是此归一化下的 L2，α 数值不直接等于 Ridge 的 α。",
    "example": "教学示例（非真实实验）：β=2、α=1、r=0.5 时，L1 项为1、L2 项为1，总惩罚2。",
    "formula": "\\min_\\beta\\ \\frac1{2n}\\|y-X\\beta\\|^2+\\alpha r\\|\\beta\\|_1+\\frac{\\alpha(1-r)}2\\|\\beta\\|_2^2",
    "meaning": "结合稀疏选择与稳定收缩。",
    "sources": [
     {
      "section": "Elastic-Net objective",
      "title": "scikit-learn · Elastic-Net objective",
      "url": "https://scikit-learn.org/stable/modules/linear_model.html#elastic-net"
     }
    ],
    "steps": "缩放 → 联合选 α、r → 优化并看收敛 → 验证。",
    "symbols": "$r\\in[0,1]$ 为 l1_ratio，$\\alpha$ 为总强度。",
    "variant": "sklearn ElasticNet 的 l1_ratio 混合惩罚。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "L1+L2 混合正则。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "regression"
   ],
   "when": "变量成组相关，Lasso 只留一个、岭回归一个都不删时。"
  },
  {
   "after": [
    "model.glmm",
    "causal.psm"
   ],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "回归分析",
   "id": "model.logistic",
   "inputs": [
    "特征矩阵",
    "分类目标"
   ],
   "kind": "预测模型",
   "label": "Logistic 回归（二分类/多分类）",
   "level": 7,
   "math": {
    "conditions": "独立观测与 logit 线性；完全分离时估计可能不存在；优势比不是风险比。",
    "example": "教学示例（非真实实验）：η=ln3，二分类 p=3/4；三类 η 全为0，softmax 各1/3。",
    "formula": "p_i=\\frac1{1+e^{-x_i^\\top\\beta}},\\quad\\ell=\\sum_i[y_i\\log p_i+(1-y_i)\\log(1-p_i)]",
    "meaning": "通过最大似然估计类别概率；不是最小二乘拟合类别编号。",
    "sources": [
     {
      "section": "Logit",
      "title": "statsmodels · Logit",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.discrete.discrete_model.Logit.html"
     },
     {
      "section": "Multinomial logit",
      "title": "statsmodels · Multinomial logit",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.discrete.discrete_model.MNLogit.html"
     }
    ],
    "steps": "确认类别编码 → 最大化似然 → 阈值分类/概率评价；多类 P(k|x)=exp(ηk)/Σexp(ηl)。",
    "symbols": "$y_i\\in\\{0,1\\}$，$p_i=P(y_i=1\\mid x_i)$；$e^{\\beta_j}$ 为条件优势比。",
    "variant": "二分类 logit；multinomial 用 softmax，需指定基准类/可识别参数化。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "三种响应类型与优势比。",
   "outputs": [
    "回归系数",
    "优势比",
    "预测概率"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [
    "model.probit",
    "ml.lda_qda"
   ],
   "similar_why": {
    "ml.lda_qda": "同一分类任务可比较两者；判别分析对类内分布与协方差有假设，不能在任意数据上直接互换。",
    "model.probit": "同为二元响应回归，分别使用 Logit 与 Probit 链接；需结合模型假设和验证表现选择。"
   },
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "因变量是二分类（或有序、多分类），要解释优势比时。"
  },
  {
   "after": [
    "causal.heckman"
   ],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "回归分析",
   "id": "model.probit",
   "inputs": [
    "特征矩阵",
    "分类目标"
   ],
   "kind": "预测模型",
   "label": "Probit 回归",
   "level": 7,
   "math": {
    "conditions": "边际效应依赖 x；离散变量宜比较预测概率差；不能把 exp(β)解释成优势比。",
    "example": "教学示例（非真实实验）：η=0 时 p=0.5；βj=1 时局部边际效应 φ(0)≈0.399。",
    "formula": "P(y_i=1\\mid x_i)=\\Phi(x_i^\\top\\beta),\\qquad\\frac{\\partial p_i}{\\partial x_{ij}}=\\phi(x_i^\\top\\beta)\\beta_j",
    "meaning": "用正态累积分布把线性预测映为概率。",
    "sources": [
     {
      "section": "Probit",
      "title": "statsmodels · Probit",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.discrete.discrete_model.Probit.html"
     }
    ],
    "steps": "二元编码 → 最大似然 → 计算个体或平均边际效应。",
    "symbols": "$\\Phi,\\phi$ 为标准正态 CDF、密度；$\\beta_j$ 为潜在尺度系数。",
    "variant": "二分类标准正态链接；系数指数不是 logit 的优势比。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "正态链接函数的二分类模型。",
   "outputs": [
    "回归系数",
    "预测概率"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [
    "model.logistic"
   ],
   "similar_why": {
    "model.logistic": "同为二元响应回归，分别使用 Logit 与 Probit 链接；需结合模型假设和验证表现选择。"
   },
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "二分类问题，但理论设定是正态潜变量时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "回归分析",
   "id": "model.robust",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "稳健性检验",
   "level": 7,
   "math": {
    "conditions": "稳健回归不等于 OLS 的稳健标准误；对高杠杆点未必稳健；不同损失不可混称 Huber。",
    "example": "教学示例（非真实实验）：Huber 阈值1时残差3的损失为 1×3−1/2=2.5；平方损失为4.5（此示例仅 Huber）。",
    "formula": "\\min_\\beta\\sum_i\\rho\\!\\left(\\frac{y_i-x_i^\\top\\beta}{s}\\right)",
    "meaning": "降低大残差对拟合的影响。",
    "sources": [
     {
      "section": "Robust linear models and norms",
      "title": "statsmodels · Robust linear models and norms",
      "url": "https://www.statsmodels.org/stable/rlm.html"
     }
    ],
    "steps": "初始化 → 估计尺度 → 按 ψ(u)/u 更新权重 → 加权拟合直到收敛。",
    "symbols": "$s$ 为稳健尺度，$\\rho$ 为选定稳健损失。",
    "variant": "RLM；默认 bisquare，huber/hampel/andrew 是不同损失。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "稳健标准误与多种设定对比。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "数据有异方差或离群点，想确认结论没被个别点带偏时。"
  },
  {
   "after": [
    "model.chained"
   ],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "机制分析",
   "id": "model.mediation",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "影响机制",
   "label": "中介效应",
   "level": 7,
   "math": {
    "conditions": "因果解释需要时间顺序与无未控制混杂等额外假设；非线性模型不能直接套 c=c'+ab。",
    "example": "教学示例（非真实实验）：a=0.5、b=2，间接效应=1。",
    "formula": "M=aX+u,\\qquad Y=c'X+bM+v,\\qquad IE=ab",
    "meaning": "把通过中介 M 的路径系数乘积作为间接效应。",
    "sources": [
     {
      "section": "Mediation; references and assumptions",
      "title": "statsmodels · Mediation; references and assumptions",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.stats.mediation.Mediation.html"
     }
    ],
    "steps": "拟合两条回归 → 算 ab → 对完整观测单位重采样估计区间。",
    "symbols": "$a,b$ 为两条路径；$c'$ 为直接效应；截距/控制变量在式中省略。",
    "variant": "线性单中介乘积法；区间可用 percentile/normal/BCa bootstrap。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "Baron-Kenny 与 Bootstrap 间接效应。",
   "outputs": [
    "因果效应估计",
    "估计量与显著性"
   ],
   "scenarios": [
    "影响机制"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "想说明「A 通过中间变量 M 影响 B」的作用路径时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "机制分析",
   "id": "model.moderation",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "影响机制",
   "label": "调节效应",
   "level": 7,
   "math": {
    "conditions": "主效应是另一变量为零时的条件效应；避免超出观测范围推断。",
    "example": "教学示例（非真实实验）：β1=1、β3=0.5，Z=2 时 X 的斜率为2。",
    "formula": "E[Y\\mid X,Z]=\\beta_0+\\beta_1X+\\beta_2Z+\\beta_3XZ,\\quad\\frac{\\partial E[Y]}{\\partial X}=\\beta_1+\\beta_3Z",
    "meaning": "X 的效应随 Z 改变。",
    "sources": [
     {
      "section": "Interactions using formulas",
      "title": "statsmodels · Interactions using formulas",
      "url": "https://www.statsmodels.org/stable/example_formulas.html"
     }
    ],
    "steps": "编码/中心化 → 构造乘积 → 拟合 → 在有意义 Z 值报告简单斜率。",
    "symbols": "$Z$ 为调节变量；$\\beta_3$ 为交互系数。",
    "variant": "线性交互项调节效应，中心化改变主效应解释。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "交互项与简单斜率。",
   "outputs": [
    "因果效应估计",
    "估计量与显著性"
   ],
   "scenarios": [
    "影响机制"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "想说明「A 对 B 的影响在什么条件下更强或更弱」时。"
  },
  {
   "after": [],
   "before": [
    "model.mediation"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "机制分析",
   "id": "model.chained",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "影响机制",
   "label": "链式中介",
   "level": 7,
   "math": {
    "conditions": "路径排序是理论假设，回归拟合本身不能证明；因果解释仍需无混杂。",
    "example": "教学示例（非真实实验）：a1=0.5、d=0.4、b2=2，串联效应=0.4。",
    "formula": "M_1=a_1X+u_1,\\quad M_2=a_2X+dM_1+u_2,\\quad Y=c'X+b_1M_1+b_2M_2+v",
    "meaning": "串联间接效应 a1·d·b2，不包括两条单中介路径。",
    "sources": [
     {
      "section": "Product of coefficients and resampling; local extension to two mediators",
      "title": "statsmodels · Product of coefficients and resampling; local extension to two mediators",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.stats.mediation.Mediation.html"
     }
    ],
    "steps": "分别拟合三条回归 → 算三条间接路径 → 对同一行联合 bootstrap。",
    "symbols": "$a_1,d,b_2$ 为串联路径系数；另两条间接效应为 $a_1b_1,a_2b_2$。",
    "variant": "线性串联双中介，区分各间接路径。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "多中介串联的间接效应分解。",
   "outputs": [
    "因果效应估计",
    "估计量与显著性"
   ],
   "scenarios": [
    "影响机制"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "影响要经过两个以上中介环节串联传递时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "广义模型",
   "id": "model.gamma",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "Gamma 回归",
   "level": 7,
   "math": {
    "conditions": "零值不符合普通 Gamma；identity/inverse 需保证预测均值为正。",
    "example": "教学示例（非真实实验）：log 链接 η=ln2，则预测均值2；φ=0.5 时条件方差2。",
    "formula": "g(\\mu_i)=x_i^\\top\\beta,\\qquad\\operatorname{Var}(Y_i\\mid x_i)=\\phi\\mu_i^2",
    "meaning": "对正连续且方差随均值平方变化的数据建模。",
    "sources": [
     {
      "section": "Gamma variance and links",
      "title": "statsmodels · Gamma variance and links",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.genmod.families.family.Gamma.html"
     }
    ],
    "steps": "检查严格正目标 → 指定链接 → 似然/IRLS 拟合 → 看残差与预测。",
    "symbols": "$\\mu_i=E[Y_i|x_i]$，$\\phi$ 为离散参数；默认 $g(\\mu)=\\log\\mu$。",
    "variant": "Gamma GLM；默认 log，identity/inverse 改链接。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "正连续响应的广义线性模型。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "因变量是正的连续量（时长、金额），且方差随均值增大时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "广义模型",
   "id": "model.poisson",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "泊松回归",
   "level": 7,
   "math": {
    "conditions": "非整数连续数据不宜按计数解释；quasi 不具有相同完整似然，AIC 不能照搬。",
    "example": "教学示例（非真实实验）：μ=2，P(Y=0)=e^(−2)≈0.1353；NB2 α=0.5 时方差4。",
    "formula": "\\mu_i=e^{x_i^\\top\\beta},\\quad P(Y_i=y)=\\frac{e^{-\\mu_i}\\mu_i^y}{y!},\\quad\\operatorname{Var}(Y_i|x_i)=\\mu_i",
    "meaning": "对非负计数建模。",
    "sources": [
     {
      "section": "Poisson family",
      "title": "statsmodels · Poisson family",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.genmod.families.family.Poisson.html"
     },
     {
      "section": "NB2 variance",
      "title": "statsmodels · NB2 variance",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.genmod.families.family.NegativeBinomial.html"
     }
    ],
    "steps": "确认计数与暴露量 → 拟合 → 查过度离散；quasi 改为 φμ，NB2 改为 μ+αμ²。",
    "symbols": "$y=0,1,\\ldots$；$\\mu_i$ 为条件期望。",
    "variant": "Poisson、quasipoisson、NB 不同方差口径；下式为基础 Poisson log 链接。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "计数响应与发生率比。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "因变量是计数（次数、件数、人数）时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "广义模型",
   "id": "model.gee",
   "inputs": [
    "个体列",
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "GEE 广义估计方程",
   "level": 7,
   "math": {
    "conditions": "群组之间独立；稳健推断通常需足够群组；不是随机效应个体条件模型。",
    "example": "教学示例（非真实实验）：工作独立且同方差、仅截距时，方程化为 Σ(y−μ)=0，μ 为样本均值。",
    "formula": "\\sum_g D_g^\\top V_g^{-1}(y_g-\\mu_g)=0",
    "meaning": "用群组内工作相关处理相关观测，估计总体平均效应。",
    "sources": [
     {
      "section": "Generalized estimating equations",
      "title": "statsmodels · Generalized estimating equations",
      "url": "https://www.statsmodels.org/stable/gee.html"
     }
    ],
    "steps": "指定群组/链接/工作相关 → 迭代解估计方程 → 选 robust/naive 协方差。",
    "symbols": "$D_g=\\partial\\mu_g/\\partial\\beta^\\top$；$V_g$ 为工作协方差；$g$ 为独立群组。",
    "variant": "边际 GEE，family 与工作相关可配置；稳健协方差不等同工作相关正确。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "聚类相关数据的总体平均模型。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "数据按个体或班级聚类，只关心总体平均效应时。"
  },
  {
   "after": [],
   "before": [
    "model.logistic"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "广义模型",
   "id": "model.glmm",
   "inputs": [
    "个体列",
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "GLMM 广义线性混合模型",
   "level": 7,
   "math": {
    "conditions": "当前仅支持 Poisson 与 Binomial 随机截距；后验可信区间不能解释成频率学派显著性检验。",
    "example": "教学示例（非真实实验）：log 链接固定部分 ln3、组截距 ln2 时，该组条件均值为6。",
    "formula": "g(\\mu_{ij})=x_{ij}^\\top\\beta+b_j,\\quad b_j\\sim N(0,\\sigma_b^2)",
    "meaning": "在固定效应之外估计个体/群组随机截距。",
    "sources": [
     {
      "section": "Generalized linear mixed models",
      "title": "statsmodels · Generalized linear mixed models",
      "url": "https://www.statsmodels.org/stable/mixed_glm.html"
     }
    ],
    "steps": "指定目标与组 → 建立固定/随机效应设计矩阵 → 变分贝叶斯拟合 → 报告后验与收敛状态。",
    "symbols": "$g$ 为 log 或 logit；$b_j$ 是组随机截距；$\\sigma_b$ 是组间标准差。",
    "variant": "实际使用变分贝叶斯拟合 Poisson/log 或 Binomial/logit 分组随机截距；区间为后验可信区间，不是频率学派置信区间。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "Poisson/log 或 Binomial/logit 随机截距；变分贝叶斯后验估计。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "聚类数据、因变量非正态，还想要随机效应时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "model",
   "category_name": "关系与影响建模",
   "group": "广义模型",
   "id": "model.mixed",
   "inputs": [
    "个体列",
    "时间列",
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "混合效应模型",
   "level": 7,
   "math": {
    "conditions": "组间独立，指定协方差合理；随机效应正态是假设；比较不同固定效应模型时不直接比 REML 似然。",
    "example": "教学示例（非真实实验）：固定截距2，组随机截距0.5，则该组条件截距2.5。",
    "formula": "y_g=X_g\\beta+Z_gb_g+\\epsilon_g,\\quad b_g\\sim N(0,G),\\quad\\epsilon_g\\sim N(0,\\sigma^2I)",
    "meaning": "把总体固定效应与组特异偏差分开。",
    "sources": [
     {
      "section": "Linear mixed effects models",
      "title": "statsmodels · Linear mixed effects models",
      "url": "https://www.statsmodels.org/stable/mixed_linear.html"
     }
    ],
    "steps": "指定组与随机结构 → ML/REML 拟合 → 检查收敛/方差边界 → 解读固定和随机效应。",
    "symbols": "$X,Z$ 为固定/随机设计矩阵；$G$ 为随机效应协方差。",
    "variant": "线性混合模型，随机截距/斜率；ML 与 REML 的方差估计不同。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "随机截距与随机斜率。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "影响因素分析",
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "有嵌套或重复测量结构，需要随机截距、随机斜率时。"
  },
  {
   "after": [
    "ml.fcm"
   ],
   "before": [],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "聚类分析",
   "id": "ml.kmeans",
   "inputs": [
    "特征矩阵"
   ],
   "kind": "聚类",
   "label": "K-Means 聚类",
   "level": 5,
   "math": {
    "conditions": "尺度敏感；局部最优；偏好近球形簇，编号无大小意义。",
    "example": "教学示例（非真实实验）：点 [0,2,8,10] 分两簇中心1、9，总平方距离4。",
    "formula": "\\min_{C,\\mu}\\sum_{k=1}^K\\sum_{i\\in C_k}\\|x_i-\\mu_k\\|_2^2",
    "meaning": "让每簇围绕自己的均值尽量紧凑。",
    "sources": [
     {
      "section": "K-means inertia",
      "title": "scikit-learn · K-means inertia",
      "url": "https://scikit-learn.org/stable/modules/clustering.html#k-means"
     }
    ],
    "steps": "初始化中心 → 分配最近中心 → 更新均值 → 多次初始化择优。",
    "symbols": "$C_k$ 为簇，$\\mu_k$ 为中心，$K$ 为簇数。",
    "variant": "欧氏 KMeans，Lloyd/Elkan 求解相同平方距离目标。",
    "version": 1
   },
   "missing": [],
   "more": [
    "ml.dbscan"
   ],
   "needs": null,
   "note": "肘部法与轮廓系数。",
   "outputs": [
    "分组标签",
    "簇中心",
    "评价指标"
   ],
   "scenarios": [
    "客户分群",
    "结构发现"
   ],
   "similar": [
    "ml.hierarchical"
   ],
   "similar_why": {
    "ml.hierarchical": "都可做距离分群：K-Means 先给定 k，层次聚类可以结合树状图选择切分层级。"
   },
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "clustering"
   ],
   "when": "想按数值特征把样本分成 k 组，且各组大致呈球形时。"
  },
  {
   "after": [],
   "before": [],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "聚类分析",
   "id": "ml.hierarchical",
   "inputs": [
    "特征矩阵"
   ],
   "kind": "聚类",
   "label": "分层聚类",
   "level": 5,
   "math": {
    "conditions": "Ward 不可任意搭配非欧氏距离；树状顺序不是时间或因果关系。",
    "example": "教学示例（非真实实验）：两个单点0、2，Ward 平方和增量=2；并非直接把它当所有库的树高。",
    "formula": "\\Delta(A,B)=\\frac{n_An_B}{n_A+n_B}\\|\\mu_A-\\mu_B\\|^2",
    "meaning": "上式是 Ward 合并造成的簇内平方和增量，非所有 linkage 的距离定义。",
    "sources": [
     {
      "section": "Ward, single, complete, average linkage definitions",
      "title": "SciPy · linkage",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html"
     }
    ],
    "steps": "各点为一簇 → 按 linkage 合并 → 切树。single/complete/average 用最小/最大/平均成对距离；SciPy Ward 输出距离还可能使用平方根缩放。",
    "symbols": "$n_A,n_B$ 为簇大小，$\\mu_A,\\mu_B$ 为簇均值。",
    "variant": "凝聚层次聚类；Ward 为默认且需欧氏距离。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "scipy",
   "note": "树状图与多种连接方式。",
   "outputs": [
    "分组标签"
   ],
   "scenarios": [
    "客户分群",
    "结构发现"
   ],
   "similar": [
    "ml.kmeans",
    "ml.dbscan"
   ],
   "similar_why": {
    "ml.dbscan": "都靠距离结构分群，样本有噪声点时 DBSCAN 更合适。",
    "ml.kmeans": "都可做距离分群：K-Means 先给定 k，层次聚类可以结合树状图选择切分层级。"
   },
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "clustering"
   ],
   "when": "事先不知道分几类，想用树状图看层次结构时。"
  },
  {
   "after": [],
   "before": [],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "聚类分析",
   "id": "ml.dbscan",
   "inputs": [
    "特征矩阵"
   ],
   "kind": "聚类",
   "label": "DBSCAN 聚类",
   "level": 5,
   "math": {
    "conditions": "对尺度和 eps 敏感；不同密度簇难用一组阈值；噪声标签 −1 不代表必定错误数据。",
    "example": "教学示例（非真实实验）：一维0、0.1、5，eps=0.2、m=2，前两点成簇，5为噪声。",
    "formula": "N_\\varepsilon(x)=\\{y:d(x,y)\\le\\varepsilon\\},\\quad |N_\\varepsilon(x)|\\ge m",
    "meaning": "邻域足够密的点为核心点，核心点连通扩展成簇。",
    "sources": [
     {
      "section": "DBSCAN core samples",
      "title": "scikit-learn · DBSCAN core samples",
      "url": "https://scikit-learn.org/stable/modules/clustering.html#dbscan"
     }
    ],
    "steps": "按 metric 算邻域 → 标核心 → 扩展密度可达点 → 其余标噪声。",
    "symbols": "$\\varepsilon$ 为 eps，$m$ 为 min_samples；sklearn 邻域计数包含自身。",
    "variant": "密度连通聚类，含核心点、边界点与噪声。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "密度聚类与噪声点识别。",
   "outputs": [
    "分组标签"
   ],
   "scenarios": [
    "客户分群",
    "结构发现"
   ],
   "similar": [
    "ml.hierarchical"
   ],
   "similar_why": {
    "ml.hierarchical": "都靠距离结构分群，样本有噪声点时 DBSCAN 更合适。"
   },
   "suggests": [
    "prep.scale",
    "ml.kmeans"
   ],
   "tasks": [
    "clustering"
   ],
   "when": "分群形状不规则，而且希望把噪声点单独剔出来时。"
  },
  {
   "after": [],
   "before": [
    "ml.kmeans"
   ],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "聚类分析",
   "id": "ml.fcm",
   "inputs": [
    "特征矩阵"
   ],
   "kind": "聚类",
   "label": "模糊 C 均值聚类",
   "level": 5,
   "math": {
    "conditions": "需处理零距离与零权重；隶属度不是经过概率校准的类别概率。",
    "example": "教学示例（非真实实验）：点0、2对某簇的 u 都为0.5、m=2，中心为1。",
    "formula": "J_m=\\sum_i\\sum_k u_{ik}^m\\|x_i-c_k\\|^2,\\quad c_k=\\frac{\\sum_i u_{ik}^m x_i}{\\sum_i u_{ik}^m}",
    "meaning": "允许一个样本部分属于多个簇。",
    "sources": [
     {
      "section": "Fuzzy c-means objective and updates",
      "title": "Bezdek et al. (1984) · FCM",
      "url": "https://doi.org/10.1016/0098-3004(84)90020-7"
     }
    ],
    "steps": "初始化隶属度/中心 → 按距离更新 u → 按加权均值更新中心 → 迭代。",
    "symbols": "$u_{ik}\\ge0,\\sum_k u_{ik}=1$；$m$ 为模糊指数；$c_k$ 为中心。",
    "variant": "模糊 C 均值，m>1；每点隶属度和为1。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "隶属度矩阵与模糊划分系数。",
   "outputs": [
    "分组标签",
    "簇中心"
   ],
   "scenarios": [
    "客户分群",
    "结构发现"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "clustering"
   ],
   "when": "边界样本不该被硬性归到某一类，需要隶属度时。"
  },
  {
   "after": [],
   "before": [
    "ml.trees"
   ],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "集成学习",
   "id": "ml.random_forest",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "随机森林",
   "level": 6,
   "math": {
    "conditions": "不同任务的 criterion 不通用；特征重要性有偏，不能作因果解释；sklearn 不是简单多数硬投票。",
    "example": "教学示例（非真实实验）：两棵树对正类概率0.9、0.2，平均0.55，二分类预测正类；回归预测2、4则均值3。",
    "formula": "\\hat p_k(x)=\\frac1B\\sum_{b=1}^B p_{bk}(x),\\quad\\hat y_{clf}=\\arg\\max_k\\hat p_k(x),\\quad\\hat y_{reg}=\\frac1B\\sum_b T_b(x)",
    "meaning": "用重采样与随机特征减少树之间的相关性，再汇总预测。",
    "sources": [
     {
      "section": "Random forests; averaging class probabilities; gradient boosting; AdaBoost",
      "title": "scikit-learn · Random forests; averaging class probabilities; gradient boosting; AdaBoost",
      "url": "https://scikit-learn.org/stable/modules/ensemble.html"
     }
    ],
    "steps": "从训练集 bootstrap → 每节点随机选特征并按 criterion 分裂 → 汇总概率/预测 → 同一测试集评价。",
    "symbols": "$B$ 为树数，$p_{bk}$ 为第 b 树对类 k 的叶概率，$T_b$ 为回归预测。",
    "variant": "sklearn 分类平均叶概率后取 argmax；回归平均树预测。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "特征重要性与袋外误差。",
   "outputs": [
    "预测值",
    "特征重要性",
    "评价指标"
   ],
   "scenarios": [
    "预测建模",
    "特征重要性"
   ],
   "similar": [
    "ml.xgboost",
    "ml.lightgbm"
   ],
   "similar_why": {
    "ml.lightgbm": "同一预测任务可比较袋装树与梯度提升树，结合数据规模、资源限制及验证表现选择。",
    "ml.xgboost": "同一个预测任务选一个强模型：随机森林走 Bagging，XGBoost 走 Boosting。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "表格数据要一个稳、少调参的强基线预测模型时。"
  },
  {
   "after": [],
   "before": [
    "ml.trees"
   ],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "集成学习",
   "id": "ml.xgboost",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "XGBoost",
   "level": 6,
   "math": {
    "conditions": "是单轮近似目标；不能把分类梯度当平方误差残差；gain 不代表因果效应。",
    "example": "教学示例（非真实实验）：某叶 G=−4、H=3、λ=1，未乘学习率的最佳叶权 −G/(H+λ)=1。",
    "formula": "\\mathcal L^{(t)}\\approx\\sum_i[g_if_t(x_i)+\\tfrac12h_if_t(x_i)^2]+\\gamma T+\\tfrac\\lambda2\\sum_jw_j^2",
    "meaning": "用损失一二阶导数选择新树并惩罚复杂度。",
    "sources": [
     {
      "section": "Regularized objective; Taylor expansion; leaf weights",
      "title": "XGBoost · Model",
      "url": "https://xgboost.readthedocs.io/en/stable/tutorials/model.html"
     }
    ],
    "steps": "初始化 → 计算梯度/Hessian → 建树 → 以 learning_rate 加入预测 → 验证。",
    "symbols": "$g_i,h_i$ 为当前损失导数，$T$ 为叶数，$w_j$ 为叶权，$\\gamma,\\lambda$ 为惩罚。",
    "variant": "加法树及二阶目标近似；具体分类/回归损失由任务决定。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "xgboost",
   "note": "梯度提升与早停。",
   "outputs": [
    "预测值",
    "特征重要性",
    "评价指标"
   ],
   "scenarios": [
    "预测建模",
    "特征重要性"
   ],
   "similar": [
    "ml.random_forest",
    "ml.lightgbm"
   ],
   "similar_why": {
    "ml.lightgbm": "同为梯度提升的工程实现；速度和精度取决于数据、参数及训练条件，没有固定的优劣保证。",
    "ml.random_forest": "同一个预测任务选一个强模型：随机森林走 Bagging，XGBoost 走 Boosting。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "追求预测精度，也愿意花时间调参时。"
  },
  {
   "after": [],
   "before": [
    "ml.trees"
   ],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "集成学习",
   "id": "ml.lightgbm",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "LightGBM",
   "level": 6,
   "math": {
    "conditions": "叶优先可能过拟合小数据；二分类累计分数需经 sigmoid 才是概率。",
    "example": "教学示例（非真实实验）：旧分数1、新树输出0.5、η=0.1，新分数1.05。",
    "formula": "F_t(x)=F_{t-1}(x)+\\eta f_t(x)",
    "meaning": "逐轮拟合改善当前损失的树，用叶数等参数控制复杂度。",
    "sources": [
     {
      "section": "Histogram based algorithms; leaf-wise growth",
      "title": "LightGBM · Features",
      "url": "https://lightgbm.readthedocs.io/en/stable/Features.html"
     }
    ],
    "steps": "按任务选损失 → 量化直方图 → 选增益最大叶分裂 → 加入新树 → 验证。",
    "symbols": "$F_t$ 为累计预测分数，$f_t$ 为新树，$\\eta$ 为学习率。",
    "variant": "梯度提升树，直方图与叶优先生长；GOSS/EFB 是可选优化而非每次必启用。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "lightgbm",
   "note": "直方图梯度提升。",
   "outputs": [
    "预测值",
    "特征重要性",
    "评价指标"
   ],
   "scenarios": [
    "预测建模",
    "特征重要性"
   ],
   "similar": [
    "ml.random_forest",
    "ml.xgboost"
   ],
   "similar_why": {
    "ml.random_forest": "同一预测任务可比较袋装树与梯度提升树，结合数据规模、资源限制及验证表现选择。",
    "ml.xgboost": "同为梯度提升的工程实现；速度和精度取决于数据、参数及训练条件，没有固定的优劣保证。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "样本量大、特征维度高，训练速度成为瓶颈时。"
  },
  {
   "after": [],
   "before": [
    "ml.trees"
   ],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "集成学习",
   "id": "ml.adaboost",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "AdaBoost",
   "level": 6,
   "math": {
    "conditions": "二分类式不能直接套到多类或回归；噪声点可能被反复放大；实际系数与 learning_rate/版本实现有关。",
    "example": "教学示例（非真实实验）：经典二分类 et=0.25，α=0.5ln3≈0.5493，误分点相对正确点权重倍率3。",
    "formula": "\\alpha_t=\\tfrac12\\log\\frac{1-e_t}{e_t},\\quad w_i'\\propto w_i\\exp[-\\alpha_ty_ih_t(x_i)]",
    "meaning": "增加难分样本权重，再加权组合弱学习器。",
    "sources": [
     {
      "section": "Random forests; averaging class probabilities; gradient boosting; AdaBoost",
      "title": "scikit-learn · Random forests; averaging class probabilities; gradient boosting; AdaBoost",
      "url": "https://scikit-learn.org/stable/modules/ensemble.html"
     }
    ],
    "steps": "初始化等权 → 拟合弱树 → 估计错误 → 更新样本权重 → 集成。回归按所选 linear/square/exponential 相对误差更新，预测为加权中位数。",
    "symbols": "$y_i,h_t\\in\\{-1,1\\}$，$e_t$ 为加权错误率；多类 SAMME 的系数改为 log((1−e)/e)+log(K−1)。",
    "variant": "分类与回归 AdaBoost 不同；下式仅解释经典二分类 AdaBoost，回归分支为 AdaBoost.R2。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "自适应提升。",
   "outputs": [
    "预测值",
    "特征重要性",
    "评价指标"
   ],
   "scenarios": [
    "预测建模",
    "特征重要性"
   ],
   "similar": [
    "ml.gbdt"
   ],
   "similar_why": {
    "ml.gbdt": "两种提升思路：GBDT 拟合负梯度，AdaBoost 提高错分样本权重。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "想用一批简单弱学习器逐步加权组合出一个强模型时。"
  },
  {
   "after": [],
   "before": [
    "ml.trees"
   ],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "集成学习",
   "id": "ml.gbdt",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "GBDT 梯度提升树",
   "level": 6,
   "math": {
    "conditions": "只有平方误差下负梯度与普通残差成比例；分类输出分数要转换为概率。",
    "example": "教学示例（非真实实验）：平方误差 ℓ=(y−F)²/2，y=3、F=1，负梯度2。",
    "formula": "r_{it}=-\\left.\\frac{\\partial\\ell(y_i,F)}{\\partial F}\\right|_{F=F_{t-1}(x_i)},\\quad F_t=F_{t-1}+\\eta f_t",
    "meaning": "新树逼近当前损失的负梯度。",
    "sources": [
     {
      "section": "Random forests; averaging class probabilities; gradient boosting; AdaBoost",
      "title": "scikit-learn · Random forests; averaging class probabilities; gradient boosting; AdaBoost",
      "url": "https://scikit-learn.org/stable/modules/ensemble.html"
     }
    ],
    "steps": "初始化 → 计算负梯度 → 拟合树并更新叶值 → 缩步相加。",
    "symbols": "$\\ell$ 为损失，$r_{it}$ 为伪残差，$\\eta$ 为学习率。",
    "variant": "梯度提升；默认具体损失取决于分类/回归。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "逐步拟合负梯度。",
   "outputs": [
    "预测值",
    "特征重要性",
    "评价指标"
   ],
   "scenarios": [
    "预测建模",
    "特征重要性"
   ],
   "similar": [
    "ml.adaboost"
   ],
   "similar_why": {
    "ml.adaboost": "两种提升思路：GBDT 拟合负梯度，AdaBoost 提高错分样本权重。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "想理解梯度提升到底在拟合什么时。"
  },
  {
   "after": [],
   "before": [],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "经典算法",
   "id": "ml.svm",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "支持向量机 SVM",
   "level": 6,
   "math": {
    "conditions": "核参数与尺度耦合；决策分数不是概率；分类式不描述 SVR 的 ε 管道。",
    "example": "教学示例（非真实实验）：某分类样本间隔0.7，则所需松弛至少0.3；SVR 误差0.2、ε=0.1时损失0.1。",
    "formula": "\\min_{w,b,\\xi}\\tfrac12\\|w\\|^2+C\\sum_i\\xi_i,\\quad y_i(w^\\top\\phi(x_i)+b)\\ge1-\\xi_i,\\quad\\xi_i\\ge0",
    "meaning": "在大间隔与误分类惩罚之间折中。",
    "sources": [
     {
      "section": "SVC and SVR mathematical formulation",
      "title": "scikit-learn · SVC and SVR mathematical formulation",
      "url": "https://scikit-learn.org/stable/modules/svm.html"
     }
    ],
    "steps": "缩放 → 选 kernel/C/gamma → 优化支持向量 → 分类或回归。",
    "symbols": "$C$ 为惩罚，$\\phi$ 为核特征映射，$y_i=\\pm1$；SVR 损失为 $\\max(0,|y-f|-\\varepsilon)$。",
    "variant": "分类软间隔式；回归使用 ε 不敏感 SVR。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "核函数与支持向量。",
   "outputs": [
    "预测值",
    "评价指标"
   ],
   "scenarios": [
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "样本量中等、维度高，类别边界比较清晰时。"
  },
  {
   "after": [],
   "before": [],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "经典算法",
   "id": "ml.knn",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "K 近邻 KNN",
   "level": 5,
   "math": {
    "conditions": "高维距离会退化；类别编号不能用回归均值冒充分类投票。",
    "example": "教学示例（非真实实验）：三近邻回归目标2、4、6等权均值4；分类 A,A,B 投 A。",
    "formula": "\\hat y_{reg}=\\frac{\\sum_{i\\in N_k(x)}w_iy_i}{\\sum_{i\\in N_k(x)}w_i},\\quad\\hat y_{clf}=\\arg\\max_c\\sum_{i\\in N_k(x)}w_i\\mathbf1(y_i=c)",
    "meaning": "从局部相似观测推断目标。",
    "sources": [
     {
      "section": "Nearest neighbors classification and regression",
      "title": "scikit-learn · Nearest neighbors classification and regression",
      "url": "https://scikit-learn.org/stable/modules/neighbors.html"
     }
    ],
    "steps": "训练集缩放 → 选度量 → 找近邻 → 按任务汇总。",
    "symbols": "$N_k$ 为最近 k 个训练点，uniform 时 $w_i=1$；distance 按距离倒数并保护零距离。",
    "variant": "分类加权投票、回归加权均值；uniform/distance 两种权重。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "距离度量与 k 选择。",
   "outputs": [
    "预测值",
    "评价指标"
   ],
   "scenarios": [
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "需要没有训练过程的直观基线，或做小规模分类回归时。"
  },
  {
   "after": [],
   "before": [],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "经典算法",
   "id": "ml.nb",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "朴素贝叶斯",
   "level": 5,
   "math": {
    "conditions": "条件独立通常近似；Multinomial 要求非负；平滑约定影响零频数。",
    "example": "教学示例（非真实实验）：两类先验均0.5，某二元特征出现概率0.8、0.2，则见该特征后正类后验0.8。",
    "formula": "P(c\\mid x)\\propto P(c)\\prod_jP(x_j\\mid c)",
    "meaning": "在给定类别条件独立假设下组合特征证据。",
    "sources": [
     {
      "section": "Naive Bayes variants",
      "title": "scikit-learn · Naive Bayes variants",
      "url": "https://scikit-learn.org/stable/modules/naive_bayes.html"
     }
    ],
    "steps": "估计类先验与分布参数 → 用对数相加避免下溢 → 比较后验得分。",
    "symbols": "$c$ 为类别，$P(c)$ 为先验；Gaussian 连续正态，Multinomial 计数，Bernoulli 二元。",
    "variant": "Gaussian/Multinomial/Bernoulli 使用不同类条件分布。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "高斯与多项式朴素贝叶斯。",
   "outputs": [
    "预测值",
    "评价指标"
   ],
   "scenarios": [
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "classification"
   ],
   "when": "文本或高维稀疏特征的快速基线分类时。"
  },
  {
   "after": [],
   "before": [],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "神经网络",
   "id": "ml.mlp",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "神经网络 MLP",
   "level": 6,
   "math": {
    "conditions": "损失与输出取决于任务；正则系数的样本归一化以具体库为准；随机初始化影响解。",
    "example": "教学示例（非真实实验）：单神经元 ReLU，w=2、b=−1、x=1，输出 max(0,1)=1。",
    "formula": "h^{(l)}=\\sigma(W^{(l)}h^{(l-1)}+b^{(l)}),\\qquad\\min_\\theta\\frac1n\\sum_i\\ell(y_i,f_\\theta(x_i))+\\lambda R(\\theta)",
    "meaning": "通过多层非线性映射学习预测关系。",
    "sources": [
     {
      "section": "Multilayer perceptron and regularization",
      "title": "scikit-learn · Multilayer perceptron and regularization",
      "url": "https://scikit-learn.org/stable/modules/neural_networks_supervised.html"
     }
    ],
    "steps": "训练集缩放 → 前向计算 → 反向求梯度 → 用 adam/sgd/lbfgs 优化 → 验证收敛。",
    "symbols": "$h^{(0)}=x$，$W,b$ 为权重偏置，$\\sigma$ 为 relu/tanh/logistic。",
    "variant": "多层前馈网络；分类输出概率，回归通常线性输出。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "多层感知机与损失曲线。",
   "outputs": [
    "预测值",
    "评价指标"
   ],
   "scenarios": [
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "变量之间的关系明显非线性，且数据量足够时。"
  },
  {
   "after": [],
   "before": [],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "神经网络",
   "id": "ml.rbf",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "RBF 径向基网络",
   "level": 6,
   "math": {
    "conditions": "gamma 与尺度相关；分类输出层与回归不同，RBF 响应本身不是概率。",
    "example": "教学示例（非真实实验）：x=1、中心0、γ=1时响应 e^(−1)≈0.3679。",
    "formula": "\\phi_j(x)=\\exp(-\\gamma\\|x-c_j\\|^2),\\quad f(x)=b+\\sum_jw_j\\phi_j(x)",
    "meaning": "用离中心的距离构造局部响应再拟合输出。",
    "sources": [
     {
      "section": "RBF kernel",
      "title": "scikit-learn · RBF kernel",
      "url": "https://scikit-learn.org/stable/modules/metrics.html#radial-basis-function-rbf-kernel"
     }
    ],
    "steps": "缩放 → 选中心 → 算 RBF 矩阵 → 拟合输出层 → 按任务预测。",
    "symbols": "$c_j$ 为中心，$\\gamma>0$ 为宽度倒数尺度，$w_j,b$ 为输出参数。",
    "variant": "RBF 特征 + 输出层；中心可用 KMeans 或随机初始化。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "径向基核的浅层网络。",
   "outputs": [
    "预测值",
    "评价指标"
   ],
   "scenarios": [
    "预测建模"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "需要局部响应的浅层网络，而训练样本不太多时。"
  },
  {
   "after": [
    "ml.random_forest",
    "ml.xgboost",
    "ml.lightgbm",
    "ml.adaboost",
    "ml.gbdt"
   ],
   "before": [],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "树模型",
   "id": "ml.trees",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "预测模型",
   "label": "CART 决策树（基尼 / 熵）",
   "level": 5,
   "math": {
    "conditions": "原 C4.5 的增益率、CHAID 的卡方合并、QUEST 的选择机制并未由当前实现完整提供；不能把标签当算法保证。",
    "example": "教学示例（非真实实验）：父节点各半两类，Gini=0.5；切成两个纯叶时下降0.5。",
    "formula": "\\Delta I=I(P)-\\frac{n_L}{n_P}I(L)-\\frac{n_R}{n_P}I(R),\\quad H=-\\sum_kp_k\\log p_k,\\quad G=1-\\sum_kp_k^2",
    "meaning": "选择带来最大不纯度下降的切分。",
    "sources": [
     {
      "section": "Decision tree criteria and mathematical formulation",
      "title": "scikit-learn · Decision tree criteria and mathematical formulation",
      "url": "https://scikit-learn.org/stable/modules/tree.html"
     }
    ],
    "steps": "枚举候选切分 → 算不纯度下降 → 按深度/叶样本限制递归 → 剪枝。",
    "symbols": "$P,L,R$ 为父/左右子节点，$p_k$ 为节点类别比例；$I$ 可为熵或 Gini。",
    "variant": "实际实现 sklearn CART 二叉树，支持基尼或熵不纯度；不以 CART 冒充 C4.5、CHAID 或 QUEST。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "实际使用 CART 二叉树，以基尼或熵下降分裂；不声称实现 C4.5/CHAID/QUEST。",
   "outputs": [
    "规则集",
    "特征重要性"
   ],
   "scenarios": [
    "预测建模",
    "规则提取"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "想要可读的 if-then 规则和特征重要性时。"
  },
  {
   "after": [],
   "before": [
    "model.correlation"
   ],
   "category": "ml",
   "category_name": "分类、聚类与机器学习",
   "group": "经典算法",
   "id": "ml.lda_qda",
   "inputs": [
    "特征矩阵",
    "分类目标"
   ],
   "kind": "预测模型",
   "label": "判别分析 LDA / QDA",
   "level": 8,
   "math": {
    "conditions": "协方差须可估且稳定；LDA 边界线性、QDA 二次；小样本 QDA 易病态。",
    "example": "教学示例（非真实实验）：等先验、一维共同方差1、类均值0和2，LDA 边界为1。",
    "formula": "\\delta_k^{LDA}=x^\\top\\Sigma^{-1}\\mu_k-\\tfrac12\\mu_k^\\top\\Sigma^{-1}\\mu_k+\\log\\pi_k",
    "meaning": "用高斯类条件模型推导判别函数。",
    "sources": [
     {
      "section": "LDA and QDA mathematical formulation",
      "title": "scikit-learn · LDA and QDA mathematical formulation",
      "url": "https://scikit-learn.org/stable/modules/lda_qda.html"
     }
    ],
    "steps": "估计类均值/协方差 → 算判别分数 → 最大者分类。QDA 分数=−log|Σk|/2−(x−μk)ᵀΣk⁻¹(x−μk)/2+logπk。",
    "symbols": "$\\mu_k,\\pi_k$ 为类均值/先验；LDA 共用 $\\Sigma$；QDA 用 $\\Sigma_k$。",
    "variant": "LDA 共享协方差，QDA 每类协方差；此处 LDA 是判别分析，不是主题模型。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "线性与二次判别边界。",
   "outputs": [
    "分组标签",
    "回归系数",
    "评价指标"
   ],
   "scenarios": [
    "预测建模"
   ],
   "similar": [
    "model.logistic"
   ],
   "similar_why": {
    "model.logistic": "同一分类任务可比较两者；判别分析对类内分布与协方差有假设，不能在任意数据上直接互换。"
   },
   "suggests": [
    "prep.scale"
   ],
   "tasks": [
    "classification"
   ],
   "when": "分类任务，同时想得到判别边界和降维结果时。"
  },
  {
   "after": [
    "series.sarima"
   ],
   "before": [
    "series.adf"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "时间序列",
   "id": "series.arima",
   "inputs": [
    "时间序列"
   ],
   "kind": "时序建模",
   "label": "ARIMA",
   "level": 9,
   "math": {
    "conditions": "差分后需平稳、MA 可逆；有积分时常数趋势受限制，不能把 ARIMA 的回归截距直接当 AR 方程常数。",
    "example": "教学示例（非真实实验）：ARIMA(1,0,0)、均值 m=10、φ=0.5，当前12且未来创新均值0，下一步预测11。",
    "formula": "\\phi(B)(1-B)^d(y_t-m_t)=\\theta(B)\\epsilon_t,\\quad\\phi(B)=1-\\sum_{j=1}^p\\phi_jB^j,\\quad\\theta(B)=1+\\sum_{j=1}^q\\theta_jB^j",
    "meaning": "差分后用过去值与过去创新解释当前误差序列。",
    "sources": [
     {
      "section": "ARIMA model specification and trend restrictions",
      "title": "statsmodels · ARIMA model specification and trend restrictions",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html"
     }
    ],
    "steps": "按时间排序 → 选 p,d,q/趋势 → 似然估计 → 检查残差 → 预测并还原差分。",
    "symbols": "$By_t=y_{t-1}$，$d$ 为差分阶数；$m_t$ 为允许的确定性趋势；$\\epsilon_t$ 为白噪声。",
    "variant": "statsmodels ARIMA 把趋势作为回归项、误差为 ARIMA；MA 项采用加号。",
    "version": 1
   },
   "missing": [],
   "more": [
    "series.garch",
    "series.panel"
   ],
   "needs": "statsmodels",
   "note": "自回归差分移动平均与预测。",
   "outputs": [
    "时序预测值",
    "模型诊断量"
   ],
   "scenarios": [
    "时序预测",
    "平稳性诊断"
   ],
   "similar": [
    "series.gm11"
   ],
   "similar_why": {
    "series.gm11": "都要拟合趋势做外推：ARIMA 要求序列平稳或差分平稳、样本量足够，灰色预测适合小样本、近似指数增长的数据。"
   },
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "单变量序列（差分后）平稳，要做短期预测时。"
  },
  {
   "after": [],
   "before": [
    "series.arima"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "时间序列",
   "id": "series.sarima",
   "inputs": [
    "时间序列"
   ],
   "kind": "时序建模",
   "label": "季节性 ARIMA",
   "level": 9,
   "math": {
    "conditions": "趋势与 ARIMA 回归趋势参数化不同；至少需足够季节周期；季节差分不等于去除全部季节结构。",
    "example": "教学示例（非真实实验）：s=12、D=1、其余零且无趋势时，月度季节随机游走下一年同月预测为今年同月值。",
    "formula": "\\phi(B)\\Phi(B^s)(1-B)^d(1-B^s)^Dy_t=c_t+\\theta(B)\\Theta(B^s)\\epsilon_t",
    "meaning": "同时建模短期依赖与季节重复。",
    "sources": [
     {
      "section": "SARIMAX multiplicative seasonal model",
      "title": "statsmodels · SARIMAX multiplicative seasonal model",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html"
     }
    ],
    "steps": "确定采样周期 → 普通/季节差分 → 选阶 → 拟合诊断 → 按时间预测。",
    "symbols": "$s$ 为季节长度，$\\Phi,\\Theta$ 为季节 AR/MA 多项式；$c_t$ 为允许趋势。",
    "variant": "乘法季节 ARIMA；季节参数 P,D,Q,s，实际趋势口径以 SARIMAX 实现为准。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "含季节项的 ARIMA。",
   "outputs": [
    "时序预测值",
    "模型诊断量"
   ],
   "scenarios": [
    "时序预测",
    "平稳性诊断"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "prep.spectral"
   ],
   "tasks": [
    "regression"
   ],
   "when": "序列有稳定的季节周期，比如月度、季度数据时。"
  },
  {
   "after": [],
   "before": [
    "describe.stats"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "时间序列",
   "id": "series.garch",
   "inputs": [
    "时间序列"
   ],
   "kind": "时序建模",
   "label": "GARCH 波动率",
   "level": 9,
   "math": {
    "conditions": "条件方差不是收益预测；重尾分布的参数与尺度需核对。",
    "example": "教学示例（非真实实验）：ω=0.1、α=0.2、β=0.7，上一残差平方2、方差1，则新方差1.2。",
    "formula": "\\epsilon_t=\\sigma_tz_t,\\quad\\sigma_t^2=\\omega+\\alpha\\epsilon_{t-1}^2+\\beta\\sigma_{t-1}^2",
    "meaning": "波动随上一期冲击和波动递推。",
    "sources": [
     {
      "section": "GARCH variance equation",
      "title": "arch · Volatility modeling",
      "url": "https://arch.readthedocs.io/en/latest/univariate/univariate_volatility_modeling.html"
     }
    ],
    "steps": "拟合均值 → 对残差条件方差建模 → 选创新分布 → 检验标准化残差 → 预测波动。",
    "symbols": "$z_t$ 标准化创新，$\\omega>0$，$\\alpha,\\beta\\ge0$；有限无条件方差通常需 α+β<1。",
    "variant": "GARCH(p,q)，此式展示对称 GARCH(1,1)；分布可为 normal/t/skewt。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "arch",
   "note": "条件异方差与波动率预测。",
   "outputs": [
    "时序预测值",
    "模型诊断量"
   ],
   "scenarios": [
    "时序预测",
    "平稳性诊断"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "series.arima"
   ],
   "tasks": [
    "regression"
   ],
   "when": "关心的不是水平而是波动率，比如金融收益率时。"
  },
  {
   "after": [],
   "before": [
    "series.adf"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "时间序列",
   "id": "series.var",
   "inputs": [
    "时间序列"
   ],
   "kind": "时序建模",
   "label": "VAR 向量自回归",
   "level": 9,
   "math": {
    "conditions": "VAR 稳定性要求特征根条件；脉冲响应识别取决于排序/结构假设，不能自动视为因果。",
    "example": "教学示例（非真实实验）：$A_1=\\begin{bmatrix}0.5&0\\\\0.2&0.4\\end{bmatrix}$，$y_t=(2,1)^\\top$、c=0，下一步预测 $(1,0.8)^\\top$。",
    "formula": "y_t=c+A_1y_{t-1}+\\cdots+A_py_{t-p}+u_t",
    "meaning": "每个变量由所有变量的滞后共同预测。",
    "sources": [
     {
      "section": "Vector autoregressions",
      "title": "statsmodels · Vector autoregressions",
      "url": "https://www.statsmodels.org/stable/vector_ar.html"
     }
    ],
    "steps": "对齐时间 → 检查平稳/协整 → 定阶 → 拟合 → 稳定性、残差、脉冲响应诊断。",
    "symbols": "$y_t$ 为向量，$A_j$ 为系数矩阵，$u_t$ 为向量创新。",
    "variant": "多变量 VAR(p)，可选确定性趋势和滞后定阶。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "多变量相互动态与脉冲响应。",
   "outputs": [
    "时序预测值",
    "回归系数"
   ],
   "scenarios": [
    "时序预测",
    "平稳性诊断"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "多个时间序列相互影响，要看脉冲响应时。"
  },
  {
   "after": [
    "series.arima",
    "series.var",
    "series.coint",
    "series.granger"
   ],
   "before": [],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "时间序列",
   "id": "series.adf",
   "inputs": [
    "时间序列"
   ],
   "kind": "时序建模",
   "label": "单位根检验 ADF",
   "level": 9,
   "math": {
    "conditions": "结构突变会影响结果；未拒绝不等于证明单位根；KPSS 的 H0 为平稳。",
    "example": "教学示例（非真实实验）：若统计量−1而对应5%临界值−2.9，不能拒绝单位根（仅示例临界值，实际以工具结果为准）。",
    "formula": "\\Delta y_t=a+bt+\\gamma y_{t-1}+\\sum_{j=1}^p\\delta_j\\Delta y_{t-j}+u_t",
    "meaning": "ADF 检验 H0:γ=0（单位根），不是普通 t 分布检验。",
    "sources": [
     {
      "section": "ADF",
      "title": "statsmodels · ADF",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.adfuller.html"
     },
     {
      "section": "KPSS",
      "title": "statsmodels · KPSS",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.kpss.html"
     }
    ],
    "steps": "选常数/趋势 → 选滞后 → 回归 → 用 Dickey-Fuller 专用分布/临界值判断。",
    "symbols": "$\\Delta y_t=y_t-y_{t-1}$；$p$ 为差分滞后数；a,b 按 regression 选择。",
    "variant": "ADF 可带常数/趋势；附带 KPSS 的零假设相反。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "平稳性检验。",
   "outputs": [
    "检验统计量与 p 值",
    "模型诊断量"
   ],
   "scenarios": [
    "时序预测",
    "平稳性诊断"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "regression"
   ],
   "when": "建模之前必须确认序列平稳，否则会做出伪回归时。"
  },
  {
   "after": [],
   "before": [
    "series.adf"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "时间序列",
   "id": "series.coint",
   "inputs": [
    "时间序列"
   ],
   "kind": "时序建模",
   "label": "协整检验",
   "level": 9,
   "math": {
    "conditions": "不能套普通残差 ADF 的 p 值当协整 p 值；协整不自动给因果方向。",
    "example": "教学示例（非真实实验）：y=2x+平稳噪声且 x 为随机游走时，y−2x 平稳，可能协整。",
    "formula": "y_t=a+\\beta x_t+u_t,\\qquad u_t\\sim I(0)\\text{ while }x_t,y_t\\sim I(1)",
    "meaning": "两个非平稳序列存在平稳线性组合。",
    "sources": [
     {
      "section": "Augmented Engle-Granger two-step test",
      "title": "statsmodels · Augmented Engle-Granger two-step test",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.coint.html"
     }
    ],
    "steps": "检验单整阶 → 估计长期回归 → 残差单位根检验，使用协整专用临界值。",
    "symbols": "$I(1)$ 为一阶单整，$I(0)$ 为平稳，$u_t$ 为长期关系残差。",
    "variant": "Engle-Granger 两步协整；不是所有多变量协整检验的公式。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "长期均衡关系。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "时序预测",
    "平稳性诊断"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "多个非平稳序列之间存在长期均衡关系时。"
  },
  {
   "after": [],
   "before": [
    "series.adf"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "时间序列",
   "id": "series.granger",
   "inputs": [
    "时间序列"
   ],
   "kind": "时序建模",
   "label": "格兰杰因果检验",
   "level": 9,
   "math": {
    "conditions": "要求时间与滞后设定合理；遗漏变量会造成预测关系，不能等同干预因果。",
    "example": "教学示例（非真实实验）：RSSR=120、RSSU=100、m=2、n−kU=20，F=2。",
    "formula": "F=\\frac{(RSS_R-RSS_U)/m}{RSS_U/(n-k_U)}",
    "meaning": "检验加入 X 的 m 个滞后是否改善对 Y 的条件预测。",
    "sources": [
     {
      "section": "Granger noncausality tests",
      "title": "statsmodels · Granger noncausality tests",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.grangercausalitytests.html"
     }
    ],
    "steps": "对齐序列 → 选滞后 → 拟合两模型 → 联合检验 X 滞后系数全零。",
    "symbols": "$R,U$ 为受限/非受限模型；$k_U$ 为非受限参数数；$n$ 为有效行数。",
    "variant": "预测意义的 Granger，比较含/不含另一序列滞后的嵌套模型。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "领先滞后预测关系。",
   "outputs": [
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "时序预测",
    "平稳性诊断"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "想判断一个序列是否有助于预测另一个序列时。"
  },
  {
   "after": [],
   "before": [],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "时间序列",
   "id": "series.gm11",
   "inputs": [
    "时间序列"
   ],
   "kind": "时序建模",
   "label": "灰色预测 GM(1,1)",
   "level": 9,
   "math": {
    "conditions": "适合小样本近指数而非任意序列；a≈0 要单独处理；DGM 用离散递推，Verhulst 用饱和增长项。",
    "example": "教学示例（非真实实验）：原值 [2,3,4] 累加为 [2,5,9]，标准均值背景为 [3.5,7]，用后两项建立两条方程。",
    "formula": "x^{(1)}_k=\\sum_{i=1}^k x^{(0)}_i,\\quad x^{(0)}_k+a z^{(1)}_k=b,\\quad z^{(1)}_k=\\tfrac12(x^{(1)}_k+x^{(1)}_{k-1})",
    "meaning": "累加降低波动，用一阶灰微分近似指数趋势再差分还原。",
    "sources": [
     {
      "section": "Grey differential models; local implementation specifies background variants",
      "title": "Deng (1982) · Grey systems",
      "url": "https://doi.org/10.1016/S0167-6911(82)80025-X"
     }
    ],
    "steps": "累加 → 构背景值 → 最小二乘估 a,b → 时间响应 → 差分还原；当前可优化背景权重，需读取 used_background。",
    "symbols": "$x^{(0)}$ 为原序列，$x^{(1)}$ 为累加序列，$a,b$ 为待估参数。",
    "variant": "标准 GM(1,1)；DGM、Verhulst 及背景权重优化是不同变体。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "小样本累加生成预测。",
   "outputs": [
    "时序预测值",
    "评价指标"
   ],
   "scenarios": [
    "时序预测",
    "平稳性诊断"
   ],
   "similar": [
    "series.arima"
   ],
   "similar_why": {
    "series.arima": "都要拟合趋势做外推：ARIMA 要求序列平稳或差分平稳、样本量足够，灰色预测适合小样本、近似指数增长的数据。"
   },
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "样本极少（四五个点以上）且近似指数增长时。"
  },
  {
   "after": [
    "series.spatial"
   ],
   "before": [
    "describe.stats"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "空间计量",
   "id": "series.moran",
   "inputs": [
    "空间坐标",
    "目标列"
   ],
   "kind": "空间建模",
   "label": "空间自相关 Moran's I",
   "level": 9,
   "math": {
    "conditions": "权重必须有业务依据；孤立点和不对称矩阵影响推断；I 不总被严格限制在 [−1,1]。",
    "example": "教学示例（非真实实验）：两点互为唯一邻居，取值1、3，I=−1，显示高低相邻。",
    "formula": "I=\\frac{n}{S_0}\\frac{\\sum_{ij}w_{ij}(x_i-\\bar x)(x_j-\\bar x)}{\\sum_i(x_i-\\bar x)^2},\\quad S_0=\\sum_{ij}w_{ij}",
    "meaning": "度量邻近位置取值的相似性。",
    "sources": [
     {
      "section": "Moran I and spatial weights",
      "title": "PySAL · Moran",
      "url": "https://pysal.org/esda/stable/generated/esda.Moran.html"
     }
    ],
    "steps": "选邻居定义 → 构 W → 中心化 → I → 解析/置换推断；局部 Moran 是另一个统计量。",
    "symbols": "$w_{ij}$ 为邻接/距离权重；$n$ 为位置数；随机置换下常见期望为 −1/(n−1)。",
    "variant": "全局 Moran I；空间权重及行标准化会改变数值。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "空间聚集程度与局部指标。",
   "outputs": [
    "检验统计量与 p 值",
    "分组标签"
   ],
   "scenarios": [
    "空间分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "model.correlation"
   ],
   "tasks": [
    "regression"
   ],
   "when": "想知道空间上是否聚集，近处是相似还是相反时。"
  },
  {
   "after": [],
   "before": [
    "series.moran"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "空间计量",
   "id": "series.spatial",
   "inputs": [
    "空间坐标",
    "特征矩阵"
   ],
   "kind": "空间建模",
   "label": "空间滞后/误差/杜宾模型",
   "level": 9,
   "math": {
    "conditions": "SAR 中系数不直接等于总边际效应，需考虑 (I−ρW)⁻¹ 反馈；W 与外生性假设决定解释。",
    "example": "教学示例（非真实实验）：两地互邻，ρ=0.2、基础预测均为1时，对称均衡预测为1/(1−0.2)=1.25。",
    "formula": "y=\\rho Wy+X\\beta+\\epsilon\\quad(SAR),\\qquad y=X\\beta+u,\\ u=\\lambda Wu+\\epsilon\\quad(SEM)",
    "meaning": "SAR 关联邻近结果，SEM 关联误差，Durbin 再引入 WX。",
    "sources": [
     {
      "section": "ML_Lag, ML_Error and slx_lags",
      "title": "PySAL spreg · Spatial models",
      "url": "https://pysal.org/spreg/api.html"
     }
    ],
    "steps": "构 W → 选模型 → 估计 → 诊断；Durbin 为 y=ρWy+Xβ+WXθ+ε，OLS 则不含空间项。",
    "symbols": "$W$ 为已知空间权重，$\\rho,\\lambda$ 为空间参数。",
    "variant": "lag / error / durbin / ols 为不同模型。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "spreg",
   "note": "含空间权重的回归模型。",
   "outputs": [
    "估计量与显著性"
   ],
   "scenarios": [
    "空间分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "空间自相关显著，回归必须带上空间权重时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "面板数据",
   "id": "series.panel",
   "inputs": [
    "个体列",
    "时间列",
    "特征矩阵",
    "目标列"
   ],
   "kind": "面板建模",
   "label": "面板数据模型",
   "level": 9,
   "math": {
    "conditions": "固定效应不能估计被吸收的时间不变量；聚类层级、样本选择与共同趋势影响推断。",
    "example": "教学示例（非真实实验）：同一人 y 从3到5、x从1到2，去均值后固定截距消除，简单斜率为2。",
    "formula": "y_{it}=\\alpha_i+\\tau_t+x_{it}^\\top\\beta+u_{it}",
    "meaning": "利用个体内时间变化，控制不随时间变的个体差异。",
    "sources": [
     {
      "section": "Fixed effects, random effects, between estimators",
      "title": "linearmodels · Panel models",
      "url": "https://bashtage.github.io/linearmodels/panel/mathematical-formula.html"
     }
    ],
    "steps": "确定面板索引 → 选效应 → within/相应估计 → 选聚类标准误；random 还要求个体效应与解释变量不相关，between 对个体均值回归。",
    "symbols": "$i,t$ 为个体和时间；$\\alpha_i,\\tau_t$ 为个体与时间效应。",
    "variant": "固定效应、随机效应、between；下式是双向固定效应。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "linearmodels",
   "note": "固定效应、随机效应、系统 GMM。",
   "outputs": [
    "估计量与显著性",
    "模型诊断量"
   ],
   "scenarios": [
    "面板分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "series.arima"
   ],
   "tasks": [
    "regression"
   ],
   "when": "同时有多个个体和多个时期的面板数据时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "面板数据",
   "id": "series.threshold",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "面板建模",
   "label": "门槛回归",
   "level": 9,
   "math": {
    "conditions": "门槛由数据选出，不能把固定门槛常规 p 值直接当门槛存在性证据；不同于因果断点设计。",
    "example": "教学示例（非真实实验）：q≤5 时 y=x，q>5 时 y=2x；x=3 的两段预测分别3、6。",
    "formula": "y_i=x_i^\\top\\beta_1\\mathbf1(q_i\\le\\gamma)+x_i^\\top\\beta_2\\mathbf1(q_i>\\gamma)+u_i",
    "meaning": "允许回归关系在门槛两侧不同。",
    "sources": [
     {
      "section": "Threshold regression and nonstandard inference",
      "title": "Hansen (2000) · Sample splitting and threshold estimation",
      "url": "https://users.ssc.wisc.edu/~bhansen/papers/ecnmt_00.pdf"
     }
    ],
    "steps": "确定搜索区间及最小段样本 → 遍历门槛 → 最小化残差平方和 → 适当 bootstrap 不确定性。",
    "symbols": "$q_i$ 为门槛变量，$\\gamma$ 为门槛，$\\beta_1,\\beta_2$ 为分段系数。",
    "variant": "按门槛变量分段的回归；门槛搜索非普通固定分组检验。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "按门槛变量分段估计。",
   "outputs": [
    "估计量与显著性"
   ],
   "scenarios": [
    "面板分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "影响关系可能在某个门槛值前后发生改变时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "面板数据",
   "id": "series.tobit",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "面板建模",
   "label": "Tobit 回归",
   "level": 9,
   "math": {
    "conditions": "从观测最值猜边界不能证明删失；遗漏边界外对象的截断抽样需要不同归一化似然；潜在与观测边际效应不同。",
    "example": "教学示例（非真实实验）：L=0、潜在值−2时观测为0；μ=0、σ=1时落在下界的概率0.5。",
    "formula": "y_i^*=x_i^\\top\\beta+\\epsilon_i,\\quad\\epsilon_i\\sim N(0,\\sigma^2),\\quad y_i=\\max(L,y_i^*)\\ \\text{(left)}",
    "meaning": "边界值记录仍在样本内，代表潜在值落在边界外。",
    "sources": [
     {
      "section": "Censored normal model",
      "title": "Tobin (1958) · Limited dependent variables",
      "url": "https://doi.org/10.2307/1907382"
     },
     {
      "section": "Methods and formulas: left/right/two-limit censored normal likelihood",
      "title": "Stata · Tobit",
      "url": "https://www.stata.com/manuals/rtobit.pdf"
     }
    ],
    "steps": "明确机制/真实边界 → 内部值用正态密度、下边界用 Φ((L−μ)/σ)、上边界用1−Φ((U−μ)/σ) → 最大似然。",
    "symbols": "$y^*$ 为潜在值，$L$ 为已知删失下限；右删失用 min(U,y*)，双侧用 clip。",
    "variant": "受限因变量删失似然；不是截断抽样回归，left/right/both 口径不同。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "受限因变量（截断/删失）。",
   "outputs": [
    "回归系数",
    "模型诊断量"
   ],
   "scenarios": [
    "面板分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "因变量被截断或删失，比如低于检测限一律记为 0 时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "series",
   "category_name": "时间序列与空间计量",
   "group": "面板数据",
   "id": "series.quantile",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "面板建模",
   "label": "分位数回归",
   "level": 9,
   "math": {
    "conditions": "独立/相关样本要选相应推断；多个分位数可能交叉；τ=0.5 是中位数回归。",
    "example": "教学示例（非真实实验）：τ=0.8 时 u=2 损失1.6，u=−2损失0.4，更惩罚低估。",
    "formula": "\\min_\\beta\\sum_i\\rho_\\tau(y_i-x_i^\\top\\beta),\\quad\\rho_\\tau(u)=u(\\tau-\\mathbf1(u<0))",
    "meaning": "估计目标条件分位数而非条件均值。",
    "sources": [
     {
      "section": "Quantile regression",
      "title": "statsmodels · Quantile regression",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.regression.quantile_regression.QuantReg.html"
     }
    ],
    "steps": "选 τ → 优化非对称绝对损失 → 估计协方差 → 比较不同 τ 系数。",
    "symbols": "$\\tau\\in(0,1)$ 为分位点，$u$ 为残差。",
    "variant": "条件分位数回归，kernel/bandwidth 用于标准误估计。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "不同分位点上的条件影响。",
   "outputs": [
    "回归系数",
    "估计量与显著性"
   ],
   "scenarios": [
    "面板分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "关心的不是平均水平，而是高分段、低分段各自的影响因素时。"
  },
  {
   "after": [
    "causal.psmdid",
    "causal.placebo"
   ],
   "before": [
    "model.linear"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "因果推断",
   "id": "causal.did",
   "inputs": [
    "分组列",
    "两分组列",
    "目标列"
   ],
   "kind": "因果推断",
   "label": "双重差分 DID",
   "level": 10,
   "math": {
    "conditions": "无提前反应、平行的未处理趋势、稳定组构成、无溢出；前趋势未显著不能证明平行；多期 TWFE 异质效应需专门方法。",
    "example": "教学示例（非真实实验）：处理组10→15，对照组8→10，DID=(15−10)−(10−8)=3。",
    "formula": "\\tau=(\\bar Y_{T,post}-\\bar Y_{T,pre})-(\\bar Y_{C,post}-\\bar Y_{C,pre})",
    "meaning": "用对照组变化扣除共同时间变化。",
    "sources": [
     {
      "section": "Four averages and three subtractions; identification assumptions",
      "title": "Cunningham · Difference-in-Differences",
      "url": "https://mixtape.scunning.com/09-difference_in_differences"
     }
    ],
    "steps": "定义组与期 → 四均值或回归 Y=α+βT+γPost+τT·Post+Xδ+u → 合理聚类标准误。",
    "symbols": "$T,C$ 为处理/对照，pre/post 为前/后；$\\tau$ 为处理组平均处理效应的识别量。",
    "variant": "经典两组两期 DID；协变量扩展不自动解决错位处理时点问题。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "处理组与对照组前后变化。",
   "outputs": [
    "因果效应估计",
    "估计量与显著性"
   ],
   "scenarios": [
    "因果效应评估",
    "政策评估"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.crosstab"
   ],
   "tasks": [
    "regression"
   ],
   "when": "有处理组和对照组，而且都有政策前后的两期数据时。"
  },
  {
   "after": [
    "causal.psmdid"
   ],
   "before": [
    "model.logistic"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "因果推断",
   "id": "causal.psm",
   "inputs": [
    "特征矩阵",
    "两分组列",
    "目标列"
   ],
   "kind": "因果推断",
   "label": "倾向得分匹配 PSM",
   "level": 10,
   "math": {
    "conditions": "需要无未测混杂、重叠与一致性；匹配无法修复未观测混杂；不能用处理后变量匹配。",
    "example": "教学示例（非真实实验）：一个处理对象结果8，两个等权匹配对照为4、6，则该对象差为3。",
    "formula": "e(x)=P(D=1\\mid X=x),\\quad\\widehat{ATT}=\\frac1{n_T}\\sum_{i:D_i=1}\\left[Y_i-\\sum_{j:D_j=0}w_{ij}Y_j\\right]",
    "meaning": "在观测协变量相近的对象间比较结果。",
    "sources": [
     {
      "section": "Propensity score balancing and strong ignorability",
      "title": "Rosenbaum & Rubin (1983)",
      "url": "https://doi.org/10.1093/biomet/70.1.41"
     },
     {
      "section": "Propensity scores, matching, overlap and ATT",
      "title": "Cunningham · Unconfoundedness",
      "url": "https://mixtape.scunning.com/05-causal_cross_sectional_designs"
     }
    ],
    "steps": "仅用处理前协变量估 e → 检查共同支持 → 匹配 → 平衡诊断 → 报告匹配样本与效应。",
    "symbols": "$D$ 为处理，$w_{ij}$ 是每个处理对象的对照权重，通常和为1。",
    "variant": "倾向得分匹配，nearest/radius/kernel/stratify 权重不同。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "匹配后比较与平衡性检验。",
   "outputs": [
    "因果效应估计",
    "汇总表"
   ],
   "scenarios": [
    "因果效应评估",
    "政策评估"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "处理组与对照组基线差异大，想先配对出可比样本时。"
  },
  {
   "after": [],
   "before": [
    "causal.psm",
    "causal.did"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "因果推断",
   "id": "causal.psmdid",
   "inputs": [
    "特征矩阵",
    "两分组列",
    "目标列"
   ],
   "kind": "因果推断",
   "label": "PSM-DID",
   "level": 10,
   "math": {
    "conditions": "仍需条件平行趋势、重叠、无提前反应；匹配不自动消除时间变化混杂。",
    "example": "教学示例（非真实实验）：处理变化5，对照加权变化2，PSM-DID=3。",
    "formula": "\\widehat\\tau=\\frac1{n_T}\\sum_{i:D_i=1}\\left[\\Delta Y_i-\\sum_{j:D_j=0}w_{ij}\\Delta Y_j\\right]",
    "meaning": "把匹配权重用于 DID 的变化差。",
    "sources": [
     {
      "section": "Four averages and three subtractions; identification assumptions",
      "title": "Cunningham · Difference-in-Differences",
      "url": "https://mixtape.scunning.com/09-difference_in_differences"
     },
     {
      "section": "Conditional difference in differences and matching",
      "title": "Heckman, Ichimura & Todd (1997)",
      "url": "https://doi.org/10.2307/2171882"
     }
    ],
    "steps": "估倾向得分 → 匹配和平衡 → 计算变化/加权 DID → 用合适标准误。",
    "symbols": "$\\Delta Y=Y_{post}-Y_{pre}$，$w_{ij}$ 为基于处理前协变量的匹配权重。",
    "variant": "先匹配再比较前后变化，ATT 针对匹配后可比较人群。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "匹配后再做双重差分。",
   "outputs": [
    "因果效应估计",
    "估计量与显著性"
   ],
   "scenarios": [
    "因果效应评估",
    "政策评估"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "既想缓解选择偏误、又要做前后对比时。"
  },
  {
   "after": [],
   "before": [
    "model.linear"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "因果推断",
   "id": "causal.rd",
   "inputs": [
    "特征矩阵",
    "目标列"
   ],
   "kind": "因果推断",
   "label": "断点回归 RD",
   "level": 10,
   "math": {
    "conditions": "阈值附近潜在结果连续、无精确操纵；效应仅局部；若处理概率非0→1跳变需 fuzzy RD 除以处理概率跳跃。",
    "example": "教学示例（非真实实验）：阈值处右预测12、左预测10，sharp RD 效应2。",
    "formula": "\\tau=\\lim_{x\\downarrow c}E[Y\\mid X=x]-\\lim_{x\\uparrow c}E[Y\\mid X=x]",
    "meaning": "比较刚过阈值与刚低于阈值的局部结果差。",
    "sources": [
     {
      "section": "Sharp and fuzzy designs; continuity",
      "title": "Cunningham · Regression discontinuity",
      "url": "https://mixtape.scunning.com/06-regression_discontinuity"
     }
    ],
    "steps": "核对阈值处理规则 → 选带宽/核 → 两侧局部拟合 → 截距差 → 敏感性与操纵检查。",
    "symbols": "$X$ 为运行变量、$c$ 为断点；右极限减左极限。",
    "variant": "当前为 sharp 局部多项式断点；不是 fuzzy RD 的比率估计。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "阈值附近的局部效应。",
   "outputs": [
    "因果效应估计",
    "估计量与显著性"
   ],
   "scenarios": [
    "因果效应评估",
    "政策评估"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "处理只发生在某个阈值两侧，比如分数线、年龄线时。"
  },
  {
   "after": [],
   "before": [
    "model.probit"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "因果推断",
   "id": "causal.heckman",
   "inputs": [
    "特征矩阵",
    "两分组列",
    "目标列"
   ],
   "kind": "因果推断",
   "label": "Heckman 两步法",
   "level": 10,
   "math": {
    "conditions": "需排除限制等识别依据及误差分布假设；逆 Mills 比只对应正态 probit；结果不稳需报告。",
    "example": "教学示例（非真实实验）：probit 指数0时 λ=φ(0)/Φ(0)≈0.7979；ρσ=2 时修正项≈1.5958。",
    "formula": "P(S=1\\mid z)=\\Phi(z^\\top\\gamma),\\quad\\lambda(z)=\\frac{\\phi(z^\\top\\gamma)}{\\Phi(z^\\top\\gamma)},\\quad E[Y\\mid S=1,x,z]=x^\\top\\beta+\\rho\\sigma\\lambda(z)",
    "meaning": "对因选择而可见的结果样本加入选择修正项。",
    "sources": [
     {
      "section": "Two-step normal selection correction",
      "title": "Heckman (1979) · Sample selection bias",
      "url": "https://doi.org/10.2307/1912352"
     },
     {
      "section": "Methods and formulas: two-step estimator and inverse Mills ratio",
      "title": "Stata · Heckman",
      "url": "https://www.stata.com/manuals/rheckman.pdf"
     }
    ],
    "steps": "全部样本估选择 → 计算选中者修正项 → 结果回归；MLE 则联合最大似然。当前选 logit 时按实现的替代修正规则解读。",
    "symbols": "$S$ 为可观测指示；$z$ 为选择解释变量；$\\rho$ 为两方程误差相关。",
    "variant": "下式为经典 probit 选择的两步法；logit 选择修正不是同一正态逆 Mills 比。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "样本选择偏误修正。",
   "outputs": [
    "回归系数",
    "估计量与显著性"
   ],
   "scenarios": [
    "因果效应评估",
    "政策评估"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "样本经过自选择，只观测到愿意参与的那部分人时。"
  },
  {
   "after": [],
   "before": [
    "causal.did"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "因果推断",
   "id": "causal.placebo",
   "inputs": [
    "两分组列",
    "目标列"
   ],
   "kind": "因果推断",
   "label": "安慰剂检验",
   "level": 10,
   "math": {
    "conditions": "需要适当交换性/随机化设计；一般观察数据的置换不能证明因果，安慰剂通过也不能证明识别假设。",
    "example": "教学示例（非真实实验）：B=20 有2次至少一样极端，当前输出 p=2/20=0.1；若采用加1约定则为3/21。",
    "formula": "\\hat p=\\frac1B\\sum_{b=1}^B\\mathbf1(|\\hat\\tau_b|\\ge|\\hat\\tau_{obs}|)",
    "meaning": "将真实统计量和伪处理下统计量比较，检查设计是否容易产生假信号。",
    "sources": [
     {
      "section": "Permutation p-values should never be zero",
      "title": "Phipson & Smyth (2010)",
      "url": "https://doi.org/10.2202/1544-6115.1585"
     },
     {
      "section": "Notes: permutation types and conservative add-one convention; local code instead uses absolute tail count/B",
      "title": "SciPy · permutation_test",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html"
     }
    ],
    "steps": "保留合理交换结构 → 伪处理 → 重估同模型 → 对比效应分布；移动时点与随机置换不是同一零分布。",
    "symbols": "$B$ 为重抽次数，$\\hat\\tau_b$ 为伪处理效应；当前实现可得0，不应把有限模拟的0解释为严格零概率；加1校正是另一个约定。",
    "variant": "处理组置换或处理期移动的安慰剂；当前代码使用不加1的经验尾部比例。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "随机化处理时点或组别的稳健性。",
   "outputs": [
    "因果效应估计",
    "检验统计量与 p 值"
   ],
   "scenarios": [
    "因果效应评估",
    "政策评估"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "做完 DID 之后，想验证结论不是趋势巧合时。"
  },
  {
   "after": [
    "design.orthogonal",
    "design.uniform",
    "design.rsm",
    "design.ccd",
    "design.boxbehnken"
   ],
   "before": [
    "test.anova"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "实验设计",
   "id": "design.factorial",
   "inputs": [
    "因子列",
    "目标列"
   ],
   "kind": "实验设计",
   "label": "全因子设计",
   "level": 11,
   "math": {
    "conditions": "试验顺序和误差独立性重要；无重复的饱和模型没有纯误差自由度。",
    "example": "教学示例（非真实实验）：3因子各2水平，组合数2³=8；每组合重复2次需16次。",
    "formula": "N=\\prod_{j=1}^k L_j,\\qquad y=\\beta_0+\\sum_j\\beta_jx_j+\\sum_{j<l}\\beta_{jl}x_jx_l+\\epsilon",
    "meaning": "覆盖各因子所有水平组合，分离主效应和交互。",
    "sources": [
     {
      "section": "5.3.3.3.2 Full factorial example",
      "title": "NIST/SEMATECH · 5.3.3.3.2 Full factorial example",
      "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri3332.htm"
     }
    ],
    "steps": "确定因子水平 → 生成笛卡尔积 → 随机化/重复 → 拟合主效应与交互。",
    "symbols": "$L_j$ 为因子 j 的水平数；$N$ 为不含重复的运行数；编码 $x_j$ 与原单位不同。",
    "variant": "全因子设计及其主效应/交互回归。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "主效应与交互效应估计。",
   "outputs": [
    "估计量与显著性",
    "试验方案表"
   ],
   "scenarios": [
    "实验设计"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "想同时看多个因素的主效应和交互效应时。"
  },
  {
   "after": [],
   "before": [
    "design.factorial"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "实验设计",
   "id": "design.orthogonal",
   "inputs": [
    "因子列"
   ],
   "kind": "实验设计",
   "label": "正交设计",
   "level": 11,
   "math": {
    "conditions": "正交不是无交互；分数设计会混杂效应；混合水平不能一律用±1编码。",
    "example": "教学示例（非真实实验）：两因子四运行 [−1,−1]、[−1,1]、[1,−1]、[1,1]，两列内积0。",
    "formula": "X^\\top X\\ \\text{is diagonal (orthogonal coded columns)}",
    "meaning": "编码列互不相关时，主效应估计可分开。",
    "sources": [
     {
      "section": "Fractional factorial designs; orthogonality and aliasing",
      "title": "NIST/SEMATECH · Fractional factorial designs; orthogonality and aliasing",
      "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri334.htm"
     }
    ],
    "steps": "确定水平/运行数 → 选正交表或当前构造 → 检查列平衡与混杂 → 随机化。",
    "symbols": "$X$ 为中心化/正交对比编码的设计矩阵；含截距时其余列和需为0。",
    "variant": "正交/混合水平设计；实际构造的平衡与正交性需检查，不是任意行数都存在标准正交表。",
    "version": 1
   },
   "missing": [],
   "more": [
    "design.uniform"
   ],
   "needs": null,
   "note": "正交表安排多因素试验。",
   "outputs": [
    "试验方案表"
   ],
   "scenarios": [
    "实验设计"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "因素多、全因子试验次数根本做不完时。"
  },
  {
   "after": [],
   "before": [
    "design.factorial"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "实验设计",
   "id": "design.uniform",
   "inputs": [
    "因子列"
   ],
   "kind": "实验设计",
   "label": "均匀设计",
   "level": 11,
   "math": {
    "conditions": "不同构造不能套同一生成式；离散化可能重复点；空间均匀不等于统计独立或最优因果设计。",
    "example": "教学示例（非真实实验）：二进制 1、10、11 的反根为0.5、0.25、0.75。",
    "formula": "u_{ij}=\\varphi_{b_j}(i)\\quad\\text{(Halton)}",
    "meaning": "用不同素数基的反根序列填充单位超立方体。",
    "sources": [
     {
      "section": "Van der Corput sequence in prime bases",
      "title": "SciPy · Halton",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Halton.html"
     }
    ],
    "steps": "生成 lattice/Halton 点 → 映射因子水平 → 按 centered/wrap L2 discrepancy 评价 → 随机化/重复。",
    "symbols": "$b_j$ 为互异素数，$\\varphi_b$ 把整数的 b 进制数字反向放到小数位。",
    "variant": "均匀设计 lattice 或 Halton，目标是覆盖空间，不保证正交。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "均匀散布的试验点。",
   "outputs": [
    "试验方案表"
   ],
   "scenarios": [
    "实验设计"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "design.orthogonal"
   ],
   "tasks": [
    "regression"
   ],
   "when": "因素水平多、正交表不够用，只想让试验点均匀散布时。"
  },
  {
   "after": [],
   "before": [
    "design.factorial"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "实验设计",
   "id": "design.rsm",
   "inputs": [
    "因子列",
    "目标列"
   ],
   "kind": "实验设计",
   "label": "响应面分析 RSM",
   "level": 11,
   "math": {
    "conditions": "是局部近似；求出的极值可能在边界或为鞍点，不能外推全局最优。",
    "example": "教学示例（非真实实验）：ŷ=5−(x−1)²，允许 x∈[0,2]，最优 x=1、ŷ=5。",
    "formula": "\\hat y=\\beta_0+\\sum_j\\beta_jx_j+\\sum_j\\beta_{jj}x_j^2+\\sum_{j<l}\\beta_{jl}x_jx_l",
    "meaning": "用低阶多项式近似局部响应并在约束内优化。",
    "sources": [
     {
      "section": "5.3.3.6 Quadratic response surface equations",
      "title": "NIST/SEMATECH · 5.3.3.6 Quadratic response surface equations",
      "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri336.htm"
     }
    ],
    "steps": "设计实验 → 拟合 → 残差/失拟诊断 → 在范围内搜索最优 → 新实验确认。",
    "symbols": "$x_j$ 为编码因子；$\\beta_{jj}$ 为曲率；$\\beta_{jl}$ 为交互。",
    "variant": "线性或二阶响应面，以下为二阶。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "二阶模型与最优区域。",
   "outputs": [
    "回归系数",
    "排序结果"
   ],
   "scenarios": [
    "实验设计"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "design.ccd",
    "design.boxbehnken"
   ],
   "tasks": [
    "regression"
   ],
   "when": "想找因素的最优组合，而不只是判断谁显著时。"
  },
  {
   "after": [],
   "before": [
    "design.factorial"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "实验设计",
   "id": "design.ccd",
   "inputs": [
    "因子列"
   ],
   "kind": "实验设计",
   "label": "中心复合设计 CCD",
   "level": 11,
   "math": {
    "conditions": "可旋转 α 仅对应相应核心与假设；面心 α=1；不能把编码轴点当原单位。",
    "example": "教学示例（非真实实验）：k=2、Nf=4、n0=1，N=9，可旋转 α=√2。",
    "formula": "N=N_f+2k+n_0,\\qquad\\alpha=N_f^{1/4}\\ \\text{(rotatable full factorial core)}",
    "meaning": "因子核心、轴点和中心点共同支持二阶模型。",
    "sources": [
     {
      "section": "5.3.3.6.1 Central composite designs and alpha",
      "title": "NIST/SEMATECH · 5.3.3.6.1 Central composite designs and alpha",
      "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri3361.htm"
     }
    ],
    "steps": "生成因子核心 → 加每轴±α → 加中心/区组/重复 → 检查可行范围。",
    "symbols": "$k$ 为因子数，$N_f$ 为因子核心运行数，$n_0$ 为中心次数；$\\alpha$ 为轴点半径。",
    "variant": "中心复合设计；rotatable/orthogonal/face 使用不同 α。",
    "version": 1
   },
   "missing": [],
   "more": [
    "design.rsm"
   ],
   "needs": "statsmodels",
   "note": "可拟合二次曲面的经典设计。",
   "outputs": [
    "试验方案表"
   ],
   "scenarios": [
    "实验设计"
   ],
   "similar": [
    "design.boxbehnken"
   ],
   "similar_why": {
    "design.boxbehnken": "拟合二次响应面的两种设计：CCD 含轴点，Box–Behnken 避开全因素同时处于极端水平；试验数取决于因素数和中心点配置。"
   },
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "响应面试验需要一个能拟合二次曲面、还能外推的设计时。"
  },
  {
   "after": [],
   "before": [
    "design.factorial"
   ],
   "category": "causal",
   "category_name": "因果推断与实验设计",
   "group": "实验设计",
   "id": "design.boxbehnken",
   "inputs": [
    "因子列"
   ],
   "kind": "实验设计",
   "label": "Box-Behnken 设计",
   "level": 11,
   "math": {
    "conditions": "式子对应当前成对构造，不概括所有高维压缩设计表；扩展半径会改变几何性质；不可宣称有 CCD 轴点。",
    "example": "教学示例（非真实实验）：k=3、n0=3，N=12+3=15，例如 (1,−1,0) 是一运行。",
    "formula": "N=2k(k-1)+n_0\\quad(k\\ge3,\\ \\text{classic pairwise construction})",
    "meaning": "每次两个因子在±1，其余为0，并加入中心。",
    "sources": [
     {
      "section": "5.3.3.6.2 Three-factor geometry; higher-dimensional pair construction is local",
      "title": "NIST/SEMATECH · 5.3.3.6.2 Three-factor geometry; higher-dimensional pair construction is local",
      "url": "https://www.itl.nist.gov/div898/handbook/pri/section3/pri3362.htm"
     }
    ],
    "steps": "枚举因子对 → 四种±组合 → 其余置0 → 加中心 → 随机化。",
    "symbols": "$k$ 为因子数，$n_0$ 为中心运行数。",
    "variant": "经典三水平 Box-Behnken 无轴点；非 classic 半径模式是项目扩展。",
    "version": 1
   },
   "missing": [],
   "more": [
    "design.rsm"
   ],
   "needs": "statsmodels",
   "note": "三水平不包含角点的设计。",
   "outputs": [
    "试验方案表"
   ],
   "scenarios": [
    "实验设计"
   ],
   "similar": [
    "design.ccd"
   ],
   "similar_why": {
    "design.ccd": "拟合二次响应面的两种设计：CCD 含轴点，Box–Behnken 避开全因素同时处于极端水平；试验数取决于因素数和中心点配置。"
   },
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "因素水平数不多，又不想做角点试验时。"
  },
  {
   "after": [],
   "before": [
    "prep.pca"
   ],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "客观赋权",
   "id": "eval.pca",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "指标赋权",
   "label": "主成分分析评价",
   "level": 8,
   "math": {
    "conditions": "成分符号任意，必须说明定向；这是评价扩展，不等于 prep.pca 的降维输出；解释方差不等于业务价值。",
    "example": "教学示例（非真实实验）：全部特征值3、1，保留两项权重0.75、0.25；某对象得分2、0，归一化前综合值1.5；仅保留第一项时当前权重仍0.75。",
    "formula": "Sv_j=\\lambda_jv_j,\\quad z_{ij}=x_{c,i}^\\top v_j,\\quad F_i=\\sum_{j=1}^k a_jz_{ij},\\quad a_j=\\frac{\\lambda_j}{\\sum_{l=1}^p\\lambda_l}",
    "meaning": "用保留成分得分的加权和构造综合评价。",
    "sources": [
     {
      "section": "PCA: centered data, singular values and explained variance",
      "title": "scikit-learn · PCA: centered data, singular values and explained variance",
      "url": "https://scikit-learn.org/stable/modules/decomposition.html#pca"
     }
    ],
    "steps": "统一指标方向与归一化 → 中心化/SVD → 选成分 → 算得分 → 加权并对最终综合值 minmax 到0–1。非 Pearson 分支对相关矩阵分解后以特征向量乘特征值平方根投影；rotate 改分数与权重；equal 为1/k。",
    "symbols": "$S=X_c^\\top X_c/(n-1)$；$p$ 为全部成分数，$k$ 为保留数；$a$ 为方差占比。",
    "variant": "评价用 PCA；默认 Pearson 分支对归一化后中心化数据做 SVD，方差权重使用对全部成分的方差占比。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "以方差贡献率加权综合。",
   "outputs": [
    "权重向量",
    "综合得分"
   ],
   "scenarios": [
    "指标赋权"
   ],
   "similar": [
    "eval.factor"
   ],
   "similar_why": {
    "eval.factor": "多指标综合评价的两种建模方式：PCA 分解总方差，因子分析建模共同协变及潜在结构。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "多指标评价，想让方差大的指标自动占更大权重时。"
  },
  {
   "after": [],
   "before": [
    "model.correlation"
   ],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "客观赋权",
   "id": "eval.factor",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "指标赋权",
   "label": "因子分析",
   "level": 8,
   "math": {
    "conditions": "正交旋转 Φ=I，斜交可相关；因子分数存在不确定性；principal 提取不应冒称 ML。",
    "example": "教学示例（非真实实验）：单因子载荷0.8、因子方差1、独特方差0.36，观测方差=0.64+0.36=1。",
    "formula": "x=\\Lambda f+\\epsilon,\\quad\\Sigma=\\Lambda\\Phi\\Lambda^\\top+\\Psi",
    "meaning": "用潜在公共因子解释观测变量间共变。",
    "sources": [
     {
      "section": "MINRES, ML, principal extraction and rotation",
      "title": "factor_analyzer · FactorAnalyzer",
      "url": "https://factor-analyzer.readthedocs.io/en/latest/factor_analyzer.html"
     }
    ],
    "steps": "相关/适配性检查 → 提取因子 → 旋转 → 按 regression/Bartlett 算因子分数 → 评价。",
    "symbols": "$\\Lambda$ 为载荷，$\\Phi$ 为因子协方差，$\\Psi$ 为独特方差（通常对角）。",
    "variant": "共同因子模型；principal、minres、ML 及 varimax/promax 并非同一估计。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "潜因子结构与因子得分。",
   "outputs": [
    "权重向量",
    "综合得分"
   ],
   "scenarios": [
    "指标赋权"
   ],
   "similar": [
    "eval.pca"
   ],
   "similar_why": {
    "eval.pca": "多指标综合评价的两种建模方式：PCA 分解总方差，因子分析建模共同协变及潜在结构。"
   },
   "suggests": [
    "prep.pca"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "指标背后存在潜在维度，想要因子得分和结构解释时。"
  },
  {
   "after": [],
   "before": [],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "客观赋权",
   "id": "eval.entropy",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "指标赋权",
   "label": "熵值法",
   "level": 12,
   "math": {
    "conditions": "要求 n>1；全常数/全零时需约定回退；权重来自数据变异，不代表业务重要性。",
    "example": "教学示例（非真实实验）：一列概率[0.5,0.5]，e=1，差异系数0；[1,0] 时e=0。",
    "formula": "p_{ij}=\\frac{z_{ij}}{\\sum_i z_{ij}},\\quad e_j=-\\frac1{\\log n}\\sum_i p_{ij}\\log p_{ij},\\quad w_j=\\frac{1-e_j}{\\sum_l(1-e_l)}",
    "meaning": "差异越大的指标通常获得越大熵权。",
    "sources": [
     {
      "section": "Chapter 2: entropy weights; Chapter 3: TOPSIS",
      "title": "Hwang & Yoon (1981) · Multiple Attribute Decision Making",
      "url": "https://doi.org/10.1007/978-3-642-48318-9"
     }
    ],
    "steps": "方向化/归一化 → 非负化与零列保护 → 算 p/e → 归一化信息差异 → 汇总。",
    "symbols": "$z_{ij}$ 为非负变换值，$n$ 为对象数；约定0log0=0。",
    "variant": "先统一方向和归一化；熵权与 equal/variance 为不同赋权方案。",
    "version": 1
   },
   "missing": [],
   "more": [
    "eval.topsis",
    "eval.vikor",
    "eval.rsr",
    "eval.dea",
    "eval.fuzzy"
   ],
   "needs": null,
   "note": "按信息量确定权重。",
   "outputs": [
    "权重向量"
   ],
   "scenarios": [
    "指标赋权"
   ],
   "similar": [
    "eval.critic"
   ],
   "similar_why": {
    "eval.critic": "赋权依据不同：熵值法看指标的信息量，CRITIC 看对比强度与指标间冲突性。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "不想靠专家打分，纯用数据离散程度定权重时。"
  },
  {
   "after": [],
   "before": [],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "客观赋权",
   "id": "eval.critic",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "指标赋权",
   "label": "CRITIC 权重法",
   "level": 12,
   "math": {
    "conditions": "常数列相关无定义需保护；高变异不等于高质量；CV 在均值近零时不稳。",
    "example": "教学示例（非真实实验）：两指标 s 分别1、2，彼此 r=0，C=1、2，权重1/3、2/3。",
    "formula": "C_j=s_j\\sum_l(1-r_{jl}),\\qquad w_j=\\frac{C_j}{\\sum_l C_l}",
    "meaning": "结合对比强度与指标间冲突赋权。",
    "sources": [
     {
      "section": "Contrast intensity and conflict",
      "title": "Diakoulaki et al. (1995) · CRITIC",
      "url": "https://doi.org/10.1016/0305-0548(94)00059-H"
     }
    ],
    "steps": "同向归一化 → 计算离散/相关 → 算冲突量 → 归一权重。",
    "symbols": "$s_j$ 为归一化列离散程度，$r_{jl}$ 为列间相关。",
    "variant": "标准差型 CRITIC 为下式；range/cv 与不同相关系数会改变权重。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "对比强度与冲突性赋权。",
   "outputs": [
    "权重向量"
   ],
   "scenarios": [
    "指标赋权"
   ],
   "similar": [
    "eval.entropy"
   ],
   "similar_why": {
    "eval.entropy": "赋权依据不同：熵值法看指标的信息量，CRITIC 看对比强度与指标间冲突性。"
   },
   "suggests": [],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "各指标对比强度差异大，或指标之间相关性强时。"
  },
  {
   "after": [],
   "before": [],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "排序决策",
   "id": "eval.topsis",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "决策排序",
   "label": "TOPSIS",
   "level": 12,
   "math": {
    "conditions": "正负距离都为0时当前返回0.5；样本增减可能改变排序；权重先乘后求平方与把权重直接乘平方不是同一口径。",
    "example": "教学示例（非真实实验）：两个已归一化对象 A=(1,1)、B=(0,0)，等权后为(0.5,0.5)、(0,0)，C_A=1、C_B=0。",
    "formula": "v_{ij}=w_jz_{ij},\\quad D_i^\\pm=\\sqrt{\\sum_j(v_{ij}-v_j^\\pm)^2},\\quad C_i=\\frac{D_i^-}{D_i^++D_i^-}",
    "meaning": "更接近正理想且远离负理想的对象得分更高。",
    "sources": [
     {
      "section": "Chapter 2: entropy weights; Chapter 3: TOPSIS",
      "title": "Hwang & Yoon (1981) · Multiple Attribute Decision Making",
      "url": "https://doi.org/10.1007/978-3-642-48318-9"
     }
    ],
    "steps": "统一效益/成本方向 → 按 normalize 变换 → 赋权 → 找理想解 → 算距离与贴近度。manhattan/chebyshev 改距离范数；理论边界模式另取约定边界。",
    "symbols": "$z$ 为方向化和选定归一化值；$w$ 和为1；默认 $v_j^+=\\max_i v_{ij},v_j^-=\\min_i v_{ij}$。",
    "variant": "当前默认 minmax + 熵权 + 样本理想解 + 欧氏距离；非一律向量归一化。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "与理想解的距离排序。",
   "outputs": [
    "综合得分",
    "排序结果"
   ],
   "scenarios": [
    "方案排序",
    "指标赋权"
   ],
   "similar": [
    "eval.vikor",
    "eval.rsr"
   ],
   "similar_why": {
    "eval.rsr": "排序思路不同：TOPSIS 算贴近度，RSR 用秩次换算出分档。",
    "eval.vikor": "都与理想解比较：TOPSIS 看整体距离，VIKOR 还会单独看最差的那项指标。"
   },
   "suggests": [
    "eval.entropy"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "已经有权重，想按与理想解的距离给方案排序时。"
  },
  {
   "after": [],
   "before": [],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "排序决策",
   "id": "eval.vikor",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "决策排序",
   "label": "VIKOR",
   "level": 12,
   "math": {
    "conditions": "常数指标与零范围需保护；不能仅凭最小 Q 就声称唯一稳健最优。",
    "example": "教学示例（非真实实验）：标准化 S 项0.2、R 项0.6、v=0.5，Q=0.4。",
    "formula": "S_i=\\sum_j w_j\\frac{f_j^*-f_{ij}}{f_j^*-f_j^-},\\quad R_i=\\max_j w_j\\frac{f_j^*-f_{ij}}{f_j^*-f_j^-},\\quad Q_i=v\\frac{S_i-S^*}{S^--S^*}+(1-v)\\frac{R_i-R^*}{R^--R^*}",
    "meaning": "同时考虑总遗憾和最差指标，Q 较小较好。",
    "sources": [
     {
      "section": "VIKOR compromise ranking and acceptance conditions",
      "title": "Opricovic & Tzeng (2004)",
      "url": "https://doi.org/10.1016/S0377-2217(03)00020-1"
     }
    ],
    "steps": "统一方向/赋权 → S,R → Q → 检查可接受优势与稳定性后给折中集。",
    "symbols": "$f^*,f^-$ 为已统一方向的最好/最差；$S^*,S^-$ 为最小/最大 S，R 同理；$v\\in[0,1]$。",
    "variant": "群体效用 S 与最大遗憾 R 的折中。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "折衷排序与群体效用。",
   "outputs": [
    "综合得分",
    "排序结果"
   ],
   "scenarios": [
    "方案排序",
    "指标赋权"
   ],
   "similar": [
    "eval.topsis",
    "eval.rsr"
   ],
   "similar_why": {
    "eval.rsr": "同一组方案可以两种方法各排一次，看结论是否一致。",
    "eval.topsis": "都与理想解比较：TOPSIS 看整体距离，VIKOR 还会单独看最差的那项指标。"
   },
   "suggests": [
    "eval.entropy"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "除了整体排序，还想避免某一项指标特别差的方案时。"
  },
  {
   "after": [],
   "before": [],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "排序决策",
   "id": "eval.rsr",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "决策排序",
   "label": "秩和比 RSR",
   "level": 12,
   "math": {
    "conditions": "采用项目归一秩加权规则，不冒称传统RSR；分档是样本内相对评价，全部同分时统一记中。",
    "example": "教学示例（非真实实验）：效益值10、20、30的秩为1、2、3，归一秩得分0、0.5、1；全部相等时都得0.5。",
    "formula": "RSR_i=\\sum_j w_j\\frac{r_{ij}-1}{\\max(n-1,1)}",
    "meaning": "各指标统一为效益方向，以升序平均秩缩放到0–1再加权，得分较大较好。",
    "sources": [
     {
      "section": "Ascending average ranks and tied observations; normalized-rank rule is local evaluate.rsr",
      "title": "SciPy · rankdata",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.rankdata.html"
     }
    ],
    "steps": "方向处理 → 逐列升序平均秩 → 归一化加权 → 得分降序排名 → 用得分升序经验概率计算probit。",
    "symbols": "$r_{ij}$ 为升序平均秩，同值同秩；$n$ 为对象数，单对象使用中性分0.5。",
    "variant": "当前采用项目归一秩加权实现；不同于常见 Σrank/(n·m) 传统 RSR。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "秩次综合评价与分档。",
   "outputs": [
    "排序结果",
    "综合得分"
   ],
   "scenarios": [
    "方案排序",
    "指标赋权"
   ],
   "similar": [
    "eval.topsis",
    "eval.vikor"
   ],
   "similar_why": {
    "eval.topsis": "排序思路不同：TOPSIS 算贴近度，RSR 用秩次换算出分档。",
    "eval.vikor": "同一组方案可以两种方法各排一次，看结论是否一致。"
   },
   "suggests": [
    "eval.entropy"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "指标多、量纲杂，想用秩次换算出分档结果时。"
  },
  {
   "after": [],
   "before": [],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "效率评价",
   "id": "eval.dea",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "效率评价",
   "label": "数据包络分析 DEA",
   "level": 12,
   "math": {
    "conditions": "需可比决策单元与足够样本；CRS/VRS 的规模报酬假设不同；效率为相对样本边界，不是绝对生产率。",
    "example": "教学示例（非真实实验）：两单元产出都1、投入分别2和1；CRS投入导向前者 θ=0.5。",
    "formula": "\\min_{\\theta,\\lambda}\\theta,\\quad X\\lambda\\le\\theta x_o,\\quad Y\\lambda\\ge y_o,\\quad\\lambda\\ge0",
    "meaning": "在不减少产出的条件下衡量投入可同比例压缩多少。",
    "sources": [
     {
      "section": "CCR efficiency linear program",
      "title": "Charnes, Cooper & Rhodes (1978)",
      "url": "https://doi.org/10.1016/0377-2217(78)90138-8"
     }
    ],
    "steps": "核对正投入产出 → 每单元解线性规划 → 看效率与松弛；输出导向最大化 φ、约束 Yλ≥φyo。",
    "symbols": "$o$ 为被评价单元；$X,Y$ 为投入/产出矩阵；$\\lambda$ 为参照组合权重。",
    "variant": "下式为投入导向 CCR/CRS 包络；VRS 增加 Σλ=1，产出导向目标不同。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "投入产出效率前沿。",
   "outputs": [
    "效率值"
   ],
   "scenarios": [
    "效率评价"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "eval.entropy"
   ],
   "tasks": [
    "regression"
   ],
   "when": "有多种投入和产出，想比较各决策单元的效率时。"
  },
  {
   "after": [],
   "before": [],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "排序决策",
   "id": "eval.fuzzy",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "决策排序",
   "label": "模糊综合评价",
   "level": 12,
   "math": {
    "conditions": "隶属度不是随机概率；maxmin 结果不必和为1；主观等级/边界需说明。",
    "example": "教学示例（非真实实验）：w=(0.4,0.6)、两指标好等级隶属度0.8、0.5，加权结果0.62，maxmin结果0.5。",
    "formula": "b_k=\\sum_j w_jr_{jk}\\quad\\text{(weighted)},\\qquad b_k=\\max_j\\min(w_j,r_{jk})\\quad\\text{(maxmin)}",
    "meaning": "把各指标对等级的隶属度合成评价向量。",
    "sources": [
     {
      "section": "Membership, max-min operations; weighted composition is the local evaluation variant",
      "title": "Zadeh (1965) · Fuzzy sets",
      "url": "https://doi.org/10.1016/S0019-9958(65)90241-X"
     }
    ],
    "steps": "设等级与隶属函数 → 统一方向 → 构 R → 按 operator 合成 → 需要时用等级分数解模糊。",
    "symbols": "$R=(r_{jk})$ 为隶属矩阵；$w$ 为权重；$b_k$ 为综合等级隶属度。",
    "variant": "隶属函数 triangle/trapezoid/gaussian；weighted/maxmin/average 运算不同。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "隶属度矩阵与合成算子。",
   "outputs": [
    "综合得分",
    "排序结果"
   ],
   "scenarios": [
    "方案排序",
    "指标赋权"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "eval.entropy"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "评价里带有「较好、一般」这类模糊说法时。"
  },
  {
   "after": [],
   "before": [],
   "category": "evaluate",
   "category_name": "综合评价与决策分析",
   "group": "排序决策",
   "id": "eval.grey",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "决策排序",
   "label": "灰色关联分析",
   "level": 12,
   "math": {
    "conditions": "参考与归一化影响排序；关联度非 Pearson 相关，也不表示因果；全差为0需保护。",
    "example": "教学示例（非真实实验）：Δmin=0、Δmax=2、ρ=0.5、某差=1，则关联系数=1/2。",
    "formula": "\\xi_{ij}=\\frac{\\Delta_{min}+\\rho\\Delta_{max}}{\\Delta_{ij}+\\rho\\Delta_{max}},\\quad\\Delta_{ij}=|z_{ij}-z_{0j}|,\\quad\\Gamma_i=\\sum_jw_j\\xi_{ij}",
    "meaning": "比较各对象与参考序列的逐指标接近程度。",
    "sources": [
     {
      "section": "Grey relational systems; coefficient conventions specified by local evaluate.grey",
      "title": "Deng · Grey systems",
      "url": "https://doi.org/10.1016/S0167-6911(82)80025-X"
     }
    ],
    "steps": "同向归一化 → 选参考 → 算差 → 关联系数 → 加权关联度。",
    "symbols": "$z_0$ 为参考，$\\rho$ 为分辨系数；最小/最大差在约定的全差矩阵取值。",
    "variant": "灰色关联系数；min_baseline=sample 或 zero 改最小差基准。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "参考序列的关联度排序。",
   "outputs": [
    "相关系数",
    "排序结果"
   ],
   "scenarios": [
    "方案排序",
    "指标赋权"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "样本量小、信息不完全，想用参考序列做关联排序时。"
  },
  {
   "after": [
    "domain.tfidf",
    "domain.sentiment",
    "domain.lda"
   ],
   "before": [
    "describe.frequency"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "文本分析",
   "id": "domain.wordfreq",
   "inputs": [
    "文本列"
   ],
   "kind": "文本分析",
   "label": "词频统计",
   "level": 13,
   "math": {
    "conditions": "分词策略决定计数含义；高频不一定重要；不能把词占比当受访者比例。",
    "example": "教学示例（非真实实验）：文档 'a a b' 与 'b c'，a频数2、总词5、占比0.4。",
    "formula": "tf(t)=\\sum_d\\operatorname{count}(t,d),\\quad share(t)=\\frac{tf(t)}{\\sum_u tf(u)}",
    "meaning": "统计词元出现次数，而非包含该词的文档数。",
    "sources": [
     {
      "section": "Text tokenization and bag of words",
      "title": "scikit-learn · Text tokenization and bag of words",
      "url": "https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction"
     }
    ],
    "steps": "选文本列 → 分词与过滤 → 计数 → 排序/展示 Top 词。",
    "symbols": "$t$ 为词元，$d$ 为文档；分母为全部计入词元总次数。",
    "variant": "分词/词元计数；中文切分、停用词、最短词长与 ngram 会改变词表。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "高频词与词云数据。",
   "outputs": [
    "汇总表"
   ],
   "scenarios": [
    "文本分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "想先看文本里哪些词出现得最多时。"
  },
  {
   "after": [],
   "before": [
    "domain.wordfreq"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "文本分析",
   "id": "domain.tfidf",
   "inputs": [
    "文本列"
   ],
   "kind": "文本分析",
   "label": "TF-IDF",
   "level": 13,
   "math": {
    "conditions": "这是平滑且有+1的口径；未平滑、二值化和次线性 TF 会改变结果。",
    "example": "教学示例（非真实实验）：N=3、df=1，idf=ln2+1≈1.6931；TF=2，归一前权重≈3.3863。",
    "formula": "idf(t)=\\log\\frac{1+N}{1+df(t)}+1,\\quad v_{dt}=tf(t,d)\\,idf(t)",
    "meaning": "降低到处都出现的词的相对权重。",
    "sources": [
     {
      "section": "TF-IDF exact smoothed formula",
      "title": "scikit-learn · TF-IDF exact smoothed formula",
      "url": "https://scikit-learn.org/stable/modules/feature_extraction.html#tfidf-term-weighting"
     }
    ],
    "steps": "分词 → 建训练词表 → 算 TF/IDF → 按 L1/L2/none 归一；测试只用训练词表和 IDF。",
    "symbols": "$N$ 为文档总数，$df(t)$ 为出现词 t 的文档数；$tf$ 为原计数或1+log计数。",
    "variant": "sklearn 平滑 IDF 默认口径，之后按 norm 归一化；sublinear_tf 可改 TF。",
    "version": 1
   },
   "missing": [],
   "more": [
    "domain.lda"
   ],
   "needs": null,
   "note": "词项权重与关键词抽取。",
   "outputs": [
    "汇总表"
   ],
   "scenarios": [
    "文本分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "想找出能区分文档的关键词，而不是通用高频词时。"
  },
  {
   "after": [],
   "before": [
    "domain.wordfreq"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "文本分析",
   "id": "domain.sentiment",
   "inputs": [
    "文本列"
   ],
   "kind": "文本分析",
   "label": "情感分析",
   "level": 13,
   "math": {
    "conditions": "不理解讽刺、领域语境与复杂否定；无命中返回0不证明语义中性。",
    "example": "教学示例（非真实实验）：正命中3、负命中1，s=0.5；无命中s=0。",
    "formula": "s=\\begin{cases}(n_+-n_-)/(n_++n_-),&n_++n_->0\\\\0,&\\text{otherwise}\\end{cases}",
    "meaning": "按正负词典命中比给出−1到1分数。",
    "sources": [
     {
      "section": "Lexicon based sentiment; exact normalized-hit rule belongs to local implementation",
      "title": "Liu (2012) · Sentiment Analysis",
      "url": "https://doi.org/10.2200/S00416ED1V01Y201204HLT016"
     }
    ],
    "steps": "匹配词典 → 可选否定窗处理 → 求分数 → 以正/负/零标记；代表词频另算。",
    "symbols": "$n_+,n_-$ 为当前计数规则下的正负命中；默认是词典词是否出现在文本中。",
    "variant": "当前词典命中法，非大模型情感理解；可选否定窗口翻转极性。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "词典法与监督分类。",
   "outputs": [
    "主题与情感",
    "汇总表"
   ],
   "scenarios": [
    "文本分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "想给评论、弹幕、访谈批量打正负面标签时。"
  },
  {
   "after": [],
   "before": [
    "domain.wordfreq"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "文本分析",
   "id": "domain.lda",
   "inputs": [
    "文本列"
   ],
   "kind": "文本分析",
   "label": "LDA 主题模型",
   "level": 13,
   "math": {
    "conditions": "输入为非负计数而非任意负值；主题可置换，主题名需人工解释；短文本可能不稳。",
    "example": "教学示例（非真实实验）：两主题比例(0.7,0.3)，某词在两主题概率0.2、0.1，则混合词概率0.17。",
    "formula": "\\theta_d\\sim Dir(\\alpha),\\quad z_{dn}\\sim Cat(\\theta_d),\\quad w_{dn}\\sim Cat(\\beta_{z_{dn}})",
    "meaning": "每篇文档混合多个主题，每主题给词分布。",
    "sources": [
     {
      "section": "Generative process and variational inference",
      "title": "Blei, Ng & Jordan (2003)",
      "url": "https://www.jmlr.org/papers/v3/blei03a.html"
     }
    ],
    "steps": "计数词袋 → 指定主题数/先验 → 变分拟合 → 看主题词与文档比例。",
    "symbols": "$\\theta_d$ 为文档主题比例，$z_{dn}$ 为词位置主题，$\\beta_k$ 为主题词概率。",
    "variant": "Latent Dirichlet Allocation 主题模型，不是线性判别分析；batch/online 为优化方式。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "主题分布与主题词。",
   "outputs": [
    "主题与情感",
    "评价指标"
   ],
   "scenarios": [
    "文本分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "domain.tfidf"
   ],
   "tasks": [
    "clustering"
   ],
   "when": "文档主题未知，想让模型自己归出主题时。"
  },
  {
   "after": [],
   "before": [],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "生存分析",
   "id": "domain.km",
   "inputs": [
    "生存时间与事件"
   ],
   "kind": "生存分析",
   "label": "Kaplan-Meier 生存曲线",
   "level": 13,
   "math": {
    "conditions": "独立/非信息性删失；竞争事件不能简单当删失后用1−KM当发生率。",
    "example": "教学示例（非真实实验）：初始5人首时点1事件，S=0.8；下一时点风险集4人1事件，S=0.8×0.75=0.6。",
    "formula": "\\hat S(t)=\\prod_{t_j\\le t}\\left(1-\\frac{d_j}{n_j}\\right)",
    "meaning": "按事件时点递乘条件存活概率。",
    "sources": [
     {
      "section": "Kaplan-Meier estimator and event_observed",
      "title": "lifelines · KaplanMeierFitter",
      "url": "https://lifelines.readthedocs.io/en/latest/fitters/univariate/KaplanMeierFitter.html"
     }
    ],
    "steps": "核对时间/事件码 → 排序 → 构风险集 → 递乘 → 区间/分组比较。",
    "symbols": "$d_j$ 为时点事件数，$n_j$ 为事件发生前风险集；删失减少后续风险集但不直接作为事件。",
    "variant": "Kaplan-Meier 右删失生存函数。",
    "version": 1
   },
   "missing": [],
   "more": [
    "domain.cox",
    "domain.competing"
   ],
   "needs": "lifelines",
   "note": "生存函数与中位生存期。",
   "outputs": [
    "生存曲线",
    "估计量与显著性"
   ],
   "scenarios": [
    "生存分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "classification"
   ],
   "when": "有随访时间和是否发生事件，想先画生存曲线时。"
  },
  {
   "after": [
    "domain.nomogram"
   ],
   "before": [
    "describe.stats"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "生存分析",
   "id": "domain.cox",
   "inputs": [
    "生存时间与事件",
    "特征矩阵"
   ],
   "kind": "生存分析",
   "label": "Cox 比例风险回归",
   "level": 13,
   "math": {
    "conditions": "风险比不是发生概率比；删失机制和比例风险假设重要；并列事件需 Efron/Breslow 等修正。",
    "example": "教学示例（非真实实验）：β=ln2 时一个单位协变量增加对应风险倍增2，不能说生存概率减半。",
    "formula": "h(t\\mid x)=h_0(t)e^{x^\\top\\beta},\\quad L(\\beta)=\\prod_{i:\\delta_i=1}\\frac{e^{x_i^\\top\\beta}}{\\sum_{j\\in R(t_i)}e^{x_j^\\top\\beta}}",
    "meaning": "风险比由协变量决定，基线风险不指定形状；右式为无并列事件的部分似然。",
    "sources": [
     {
      "section": "Cox proportional hazards model",
      "title": "lifelines · Cox regression",
      "url": "https://lifelines.readthedocs.io/en/latest/Survival%20Regression.html"
     }
    ],
    "steps": "时间/事件整理 → 部分似然拟合 → 比例风险诊断 → 风险比/生存预测。",
    "symbols": "$h_0$ 为基线风险，$\\delta_i$ 为事件指示，$R(t_i)$ 为风险集；$e^{\\beta_j}$ 为风险比。",
    "variant": "比例风险模型，ties/惩罚与基线估计口径以实现为准。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "lifelines",
   "note": "风险比与协变量影响。",
   "outputs": [
    "风险比",
    "估计量与显著性"
   ],
   "scenarios": [
    "生存分析"
   ],
   "similar": [
    "domain.weibull"
   ],
   "similar_why": {
    "domain.weibull": "生存模型两条路：Cox 半参数不指定分布，Weibull 假定分布形状后可外推。"
   },
   "suggests": [
    "domain.km"
   ],
   "tasks": [
    "classification"
   ],
   "when": "想看多个因素对生存风险的影响，要解释风险比时。"
  },
  {
   "after": [],
   "before": [
    "domain.cox"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "生存分析",
   "id": "domain.nomogram",
   "inputs": [
    "生存时间与事件",
    "特征矩阵"
   ],
   "kind": "生存分析",
   "label": "列线图",
   "level": 13,
   "math": {
    "conditions": "积分依赖本次特征范围，不能当作外部校准；风险与生存率使用同一预测时点，风险比不等于发生概率。",
    "example": "教学示例（非真实实验）：β=−1、列范围0到2、单项最高100分时，x=0得100分，x=2得0分，保留保护方向。",
    "formula": "P_i=c\\sum_j\\beta_j(x_{ij}-a_j),\\quad c=\\frac{P_{max}}{\\max_j\\{|\\beta_j|(x_{j,max}-x_{j,min})\\}}",
    "meaning": "正系数以最小值为零分，负系数以最大值为零分；总分与Cox线性预测同向。",
    "sources": [
     {
      "section": "Cox linear predictor and survival probability; affine point scaling is local domain.nomogram",
      "title": "lifelines · Cox regression",
      "url": "https://lifelines.readthedocs.io/en/latest/Survival%20Regression.html"
     }
    ],
    "steps": "拟合Cox → 按带符号的效应与列范围统一缩放 → 汇总积分 → 输出指定时点风险和生存率。",
    "symbols": "$a_j$ 为该列最低风险端点；$P_{max}$ 是影响范围最大单项的最高分，总分可更高；时点风险为$1-\\hat S(t\\mid x)$。",
    "variant": "将Cox线性预测统一缩放为同向积分；各列按本次样本范围制分，不是另一个预测模型。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "lifelines",
   "note": "个体风险评分与预测。",
   "outputs": [
    "风险比",
    "排序结果"
   ],
   "scenarios": [
    "生存分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "想把 Cox 模型做成一张能手工打分的预测图时。"
  },
  {
   "after": [],
   "before": [
    "describe.stats"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "生存分析",
   "id": "domain.competing",
   "inputs": [
    "生存时间与事件"
   ],
   "kind": "生存分析",
   "label": "竞争风险模型",
   "level": 13,
   "math": {
    "conditions": "不能对其他事件删失后用1−KM代替 CIF；独立删失与并列时点处理需核对。",
    "example": "教学示例（非真实实验）：初始10人同一时点1目标事件、2竞争事件，目标 CIF 增量为1×1/10=0.1。",
    "formula": "\\hat F_k(t)=\\sum_{t_j\\le t}\\hat S(t_j^-)\\frac{d_{jk}}{n_j}",
    "meaning": "目标事件的累积发生率同时考虑所有竞争事件对存活风险集的消耗。",
    "sources": [
     {
      "section": "Competing risk cumulative incidence",
      "title": "lifelines · AalenJohansenFitter",
      "url": "https://lifelines.readthedocs.io/en/latest/fitters/univariate/AalenJohansenFitter.html"
     }
    ],
    "steps": "统一事件码0删失/其余类别 → 估总事件生存 → 按事件类型累加 → 绘制 CIF。",
    "symbols": "$d_{jk}$ 为时点 j 的类型 k 事件数；$\\hat S(t_j^-)$ 为任一事件发生前存活率。",
    "variant": "Aalen-Johansen 累积发生函数；非 Fine-Gray 回归。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "lifelines",
   "note": "多种终点的累积发生函数。",
   "outputs": [
    "生存曲线"
   ],
   "scenarios": [
    "生存分析"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "domain.km"
   ],
   "tasks": [
    "classification"
   ],
   "when": "终点事件不止一种，比如死于该病与死于其他病时。"
  },
  {
   "after": [],
   "before": [],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "问卷与市场",
   "id": "domain.reliability",
   "inputs": [
    "问卷量表"
   ],
   "kind": "问卷分析",
   "label": "信度效度分析",
   "level": 13,
   "math": {
    "conditions": "α 高不证明单维性或效度；重复题可抬高 α；总分方差0时无定义。",
    "example": "教学示例（非真实实验）：k=3、题方差和3、总分方差6，α=3/2×(1−1/2)=0.75。",
    "formula": "\\alpha=\\frac{k}{k-1}\\left(1-\\frac{\\sum_js_j^2}{s_{total}^2}\\right)",
    "meaning": "比较各题方差和与总分方差，衡量题项一致程度。",
    "sources": [
     {
      "section": "Coefficient alpha and internal structure",
      "title": "Cronbach (1951)",
      "url": "https://doi.org/10.1007/BF02310555"
     }
    ],
    "steps": "检查反向题/缺失 → 算总分方差 → α → 删题诊断及效度另评。",
    "symbols": "$k>1$ 为题数，$s_j^2$ 为题方差，$s_{total}^2$ 为总分方差；使用同样样本/分母。",
    "variant": "Cronbach α 描述内部一致性；效度/KMO/Bartlett 是不同诊断。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "Cronbach α、KMO 与 Bartlett。",
   "outputs": [
    "信效度指标"
   ],
   "scenarios": [
    "问卷分析",
    "市场调研"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "classification",
    "regression"
   ],
   "when": "有问卷量表，想先确认信度和效度时。"
  },
  {
   "after": [],
   "before": [],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "问卷与市场",
   "id": "domain.nps",
   "inputs": [
    "连续目标"
   ],
   "kind": "问卷分析",
   "label": "NPS 净推荐值",
   "level": 13,
   "math": {
    "conditions": "不是平均评分；自定义阈值时应说明已偏离标准；非随机问卷不能直接推广全体客户。",
    "example": "教学示例（非真实实验）：10人中推荐6、贬损2、中立2，NPS=40。",
    "formula": "NPS=100\\left(\\frac{n_{prom}}n-\\frac{n_{det}}n\\right)",
    "meaning": "推荐者百分比减贬损者百分比，范围−100到100。",
    "sources": [
     {
      "section": "Promoters, passives and detractors; score definition",
      "title": "Bain · Net Promoter System",
      "url": "https://www.netpromotersystem.com/about/measuring-your-net-promoter-score/"
     }
    ],
    "steps": "核对量表/阈值 → 有效样本分类 → 百分点差 → 报告样本数和不确定性。",
    "symbols": "$n$ 为有效回答总数，含中立者；$n_{prom},n_{det}$ 为两组人数。",
    "variant": "标准0–10量表：9–10推荐者、0–6贬损者、7–8中立者。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "推荐者减贬损者占比。",
   "outputs": [
    "汇总表",
    "评价指标"
   ],
   "scenarios": [
    "问卷分析",
    "市场调研"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.frequency"
   ],
   "tasks": [
    "regression",
    "classification"
   ],
   "when": "只有一道「0 到 10 分推荐意愿」的题时。"
  },
  {
   "after": [],
   "before": [
    "describe.frequency"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "问卷与市场",
   "id": "domain.kano",
   "inputs": [
    "问卷量表"
   ],
   "kind": "问卷分析",
   "label": "Kano 模型",
   "level": 13,
   "math": {
    "conditions": "不能把阈值近似分类宣称严格原版 Kano；反向/可疑回答和分母排除规则需说明。",
    "example": "教学示例（非真实实验）：A=2、O=3、M=1、I=4，CS+=0.5、CS−=−0.4。",
    "formula": "CS_+=\\frac{A+O}{A+O+M+I},\\quad CS_-=-\\frac{O+M}{A+O+M+I}",
    "meaning": "对分类后的魅力/期望/必备/无差异需求计算满意/不满意系数。",
    "sources": [
     {
      "section": "Customer satisfaction coefficient, pp. 6-7; cites Berger et al.",
      "title": "Sauerwein et al. (1996) · Kano model",
      "url": "https://faculty.kfupm.edu.sa/CEM/bushait/CEM_515-082/kano/kano-model2.pdf"
     }
    ],
    "steps": "成对问项 → 按当前阈值规则分类 → 计算两类系数 → 看类别分布。",
    "symbols": "$A,O,M,I$ 为各类计数；当前 better_index 另为平均(具备分−不具备分)/(量表级数−1)。",
    "variant": "当前用量表阈值分类，非完整原版问答评价表；区分 better_index 与 cs_better/cs_worse。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "需求属性分类。",
   "outputs": [
    "汇总表",
    "排序结果"
   ],
   "scenarios": [
    "问卷分析",
    "市场调研"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "classification"
   ],
   "when": "想区分「必须有」「越多越好」「可有可无」的需求时。"
  },
  {
   "after": [],
   "before": [],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "问卷与市场",
   "id": "domain.maxdiff",
   "inputs": [
    "多指标矩阵"
   ],
   "kind": "问卷分析",
   "label": "MaxDiff 评分推导（非选择模型）",
   "level": 13,
   "math": {
    "conditions": "并列极值、展示次数不等影响计数；份额非经估计的市场选择概率；完整 MaxDiff 需设计与选择模型。",
    "example": "教学示例（非真实实验）：n=10、B=6、W=2，净分0.4；只统计 best_only 则为0.6。",
    "formula": "s_j=\\frac{B_j-W_j}{n},\\quad share_j=\\frac{e^{s_j/T}}{\\sum_le^{s_l/T}}",
    "meaning": "净选择频次衡量相对偏好，softmax 仅为当前展示转换。",
    "sources": [
     {
      "section": "Best-worst count versus model based analysis",
      "title": "Louviere, Flynn & Marley (2015) · Best-Worst Scaling",
      "url": "https://doi.org/10.1017/CBO9781107337855"
     }
    ],
    "steps": "逐行选极值 → 按 score_kind 求净/单侧得分 → 可选0–100缩放 → softmax 或非负归一份额。",
    "symbols": "$B,W$ 为被选最好/最差次数，$n$ 为受访者数，$T>0$ 为温度。",
    "variant": "当前从评分矩阵的每行最大/最小选项计数；不是基于完整 best-worst 设计的条件 logit。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "偏好份额估计。",
   "outputs": [
    "偏好效用",
    "排序结果"
   ],
   "scenarios": [
    "问卷分析",
    "市场调研"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "classification"
   ],
   "when": "选项多、被访者习惯全打高分，需要强制取舍时。"
  },
  {
   "after": [],
   "before": [],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "问卷与市场",
   "id": "domain.conjoint",
   "inputs": [
    "因子列",
    "目标列"
   ],
   "kind": "问卷分析",
   "label": "联合分析",
   "level": 13,
   "math": {
    "conditions": "评分与选择数据不能混用似然；softmax 份额是附加假设，不是自动获得真实市场份额；缺少基准编码会共线。",
    "example": "教学示例（非真实实验）：截距2、某属性效用1.5，其他编码0时该 profile 预测评分3.5。",
    "formula": "y_i=\\beta_0+\\sum_j\\beta_jx_{ij}+\\epsilon_i",
    "meaning": "用属性/水平编码解释 profile 评分，系数作为部分效用。",
    "sources": [
     {
      "section": "OLS objective for local ratings-based conjoint",
      "title": "scikit-learn · OLS objective for local ratings-based conjoint",
      "url": "https://scikit-learn.org/stable/modules/linear_model.html#ordinary-least-squares"
     }
    ],
    "steps": "确定 profile 与评分 → 编码 → OLS → 可选效用缩放 → 计算相对重要性/展示份额。",
    "symbols": "$x_{ij}$ 为选定属性编码，$y_i$ 为 profile 评分；编码基准影响系数。",
    "variant": "当前评分型 OLS 联合分析；非选择型混合 logit。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "属性效用与重要性。",
   "outputs": [
    "偏好效用",
    "估计量与显著性"
   ],
   "scenarios": [
    "问卷分析",
    "市场调研"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "regression"
   ],
   "when": "产品由多个属性组合而成，想知道各属性的效用时。"
  },
  {
   "after": [],
   "before": [],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "问卷与市场",
   "id": "domain.psm",
   "inputs": [
    "连续目标"
   ],
   "kind": "问卷分析",
   "label": "价格分位数与需求代理（非四问 PSM）",
   "level": 13,
   "math": {
    "conditions": "仅有一列不能估计原版四条便宜/贵/太便宜/太贵曲线；声明接受不等于真实购买；不要混淆因果 PSM。",
    "example": "教学示例（非真实实验）：价格回答 [10,20,30]，p=20 时 D=2/3、R≈13.33。",
    "formula": "\\hat D(p)=\\frac1n\\sum_i\\mathbf1(v_i\\ge p),\\quad R(p)=p\\hat D(p)",
    "meaning": "用声明价格超过 p 的比例近似可接受比例，收入代理为价格乘比例。",
    "sources": [
     {
      "section": "Empirical distribution and survival function; local price_sensitivity uses inclusive >= tail and grid revenue proxy",
      "title": "SciPy · ecdf",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ecdf.html"
     }
    ],
    "steps": "筛有效/按参数缩尾 → 求分位数 → 价格网格上算 D → midpoint 或 revenue 选价。",
    "symbols": "$v_i$ 为有效价格回答；$p$ 为网格价格。",
    "variant": "当前单列可接受价格的分位数/需求代理；不是四问 Van Westendorp 完整曲线交点法。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "价格接受区间与最优点。",
   "outputs": [
    "排序结果"
   ],
   "scenarios": [
    "问卷分析",
    "市场调研"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "classification"
   ],
   "when": "想知道价格定在哪一段用户还愿意接受时。"
  },
  {
   "after": [
    "domain.capability"
   ],
   "before": [
    "describe.stats"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "质量控制",
   "id": "domain.control",
   "inputs": [
    "连续目标",
    "时间列"
   ],
   "kind": "过程控制",
   "label": "控制图（X-bar/R、CUSUM、EWMA）",
   "level": 13,
   "math": {
    "conditions": "控制限不是规格限；估计基准、子组大小与自相关影响误报；EWMA 稳态限与初期时变限不同。",
    "example": "教学示例（非真实实验）：z0=10、λ=0.2、新观测12，z1=10.4；不能把12直接当EWMA点。",
    "formula": "z_t=\\lambda x_t+(1-\\lambda)z_{t-1},\\quad UCL_t=\\mu_0+L\\sigma\\sqrt{\\frac{\\lambda}{2-\\lambda}}",
    "meaning": "平滑累计小漂移；LCL 用同一偏移减去均值。",
    "sources": [
     {
      "section": "6.3.2.4 EWMA statistic and asymptotic control limits",
      "title": "NIST/SEMATECH · 6.3.2.4 EWMA statistic and asymptotic control limits",
      "url": "https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm"
     }
    ],
    "steps": "稳定基准估计 → 按图类型计算。Xbar/R 用子组均值和极差及 A2/D3/D4 常数；CUSUM 递推正负累计偏差，越 h 报警。",
    "symbols": "$\\lambda\\in(0,1]$ 为平滑系数，$\\mu_0,\\sigma$ 为受控基准，$L$ 为控制限宽。",
    "variant": "Xbar/R、CUSUM、EWMA；下式为当前 EWMA 的稳态控制限，非初期时变限。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "过程受控判定与告警点。",
   "outputs": [
    "控制限",
    "汇总表"
   ],
   "scenarios": [
    "质量控制"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "生产过程有连续监测数据，要判断过程是否受控时。"
  },
  {
   "after": [],
   "before": [
    "domain.control"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "质量控制",
   "id": "domain.capability",
   "inputs": [
    "连续目标"
   ],
   "kind": "过程控制",
   "label": "过程能力分析",
   "level": 13,
   "math": {
    "conditions": "非稳定过程或强非正态下常规解释不可靠；总体/组内 σ 分别对应不同能力口径；控制限不替代规格。",
    "example": "教学示例（非真实实验）：LSL=0、USL=12、μ=7、σ=2，Cp=1，Cpk=min(5/6,7/6)=0.8333。",
    "formula": "C_p=\\frac{USL-LSL}{6\\sigma},\\quad C_{pk}=\\min\\left(\\frac{USL-\\mu}{3\\sigma},\\frac{\\mu-LSL}{3\\sigma}\\right)",
    "meaning": "Cp 看潜在容差，Cpk 同时考虑偏心。",
    "sources": [
     {
      "section": "6.1.6 Cp and Cpk definitions",
      "title": "NIST/SEMATECH · 6.1.6 Cp and Cpk definitions",
      "url": "https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm"
     }
    ],
    "steps": "确认过程稳定 → 确认规格 → 核对分布/变换 → 估 σ → Cp/Cpk及缺陷率。",
    "symbols": "$USL,LSL$ 为规格上/下限，$\\mu,\\sigma$ 为过程均值和相应标准差估计。",
    "variant": "Cp/Cpk 为规格与短期过程离散比较；变换后必须同口径变换规格。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "Cp、Cpk、Pp、Ppk。",
   "outputs": [
    "过程能力指数"
   ],
   "scenarios": [
    "质量控制"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [],
   "tasks": [
    "regression"
   ],
   "when": "过程稳定之后，想知道它能不能满足规格要求时。"
  },
  {
   "after": [],
   "before": [],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "质量控制",
   "id": "domain.weibull",
   "inputs": [
    "生存时间与事件"
   ],
   "kind": "过程控制",
   "label": "Weibull 可靠性分析",
   "level": 13,
   "math": {
    "conditions": "β<1/=/ >1 风险递减/常数/递增；shape/scale 与其他库命名需对齐；不能对未支持的删失默认当失效。",
    "example": "教学示例（非真实实验）：β=2、η=10，t=10 时 S=e^(−1)≈0.3679。",
    "formula": "S(t)=e^{-(t/\\eta)^\\beta},\\quad h(t)=\\frac\\beta\\eta(t/\\eta)^{\\beta-1},\\quad t\\ge0",
    "meaning": "用形状控制风险随时间升降，用尺度设寿命量级。",
    "sources": [
     {
      "section": "Notes: statistic and null distribution",
      "title": "SciPy · weibull_min",
      "url": "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.weibull_min.html"
     }
    ],
    "steps": "核对正寿命与删失支持 → MLE/秩回归 → 诊断 → 可靠度/分位寿命。",
    "symbols": "$\\beta>0$ 为形状，$\\eta>0$ 为尺度；$S(\\eta)=e^{-1}$。",
    "variant": "两参数 Weibull；当前 MLE 或秩回归，非所有删失/三参数模型。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": null,
   "note": "形状与尺度参数、可靠度曲线。",
   "outputs": [
    "可靠度曲线",
    "估计量与显著性"
   ],
   "scenarios": [
    "质量控制"
   ],
   "similar": [
    "domain.cox"
   ],
   "similar_why": {
    "domain.cox": "生存模型两条路：Cox 半参数不指定分布，Weibull 假定分布形状后可外推。"
   },
   "suggests": [
    "describe.stats"
   ],
   "tasks": [
    "regression"
   ],
   "when": "关心失效时间的分布和可靠度曲线时。"
  },
  {
   "after": [],
   "before": [
    "describe.stats"
   ],
   "category": "domain",
   "category_name": "特定行业与场景分析",
   "group": "Meta 分析",
   "id": "domain.meta",
   "inputs": [
    "效应量列"
   ],
   "kind": "Meta 分析",
   "label": "Meta 分析",
   "level": 13,
   "math": {
    "conditions": "只在可比较效应尺度汇总；相关研究、发表偏倚和少研究数量影响推断；OR 通常在对数尺度合并再指数还原。",
    "example": "教学示例（非真实实验）：两研究效应1、3、方差均1，固定效应合并2，SE=1/√2≈0.7071。",
    "formula": "\\hat\\mu=\\frac{\\sum_iw_i\\hat\\theta_i}{\\sum_iw_i},\\quad w_i=\\frac1{v_i+\\tau^2},\\quad SE(\\hat\\mu)=\\sqrt{\\frac1{\\sum_iw_i}}",
    "meaning": "按研究估计精度汇总效应；随机效应另计研究间异质性。",
    "sources": [
     {
      "section": "Fixed and random effects meta-analysis",
      "title": "statsmodels · Fixed and random effects meta-analysis",
      "url": "https://www.statsmodels.org/stable/generated/statsmodels.stats.meta_analysis.combine_effects.html"
     }
    ],
    "steps": "统一效应尺度 → 核对输入是方差/SE → 估 τ² → 加权合并 → 异质性/敏感性。",
    "symbols": "$v_i$ 为研究内方差（输入 SE 时需平方）；$\\tau^2$ 为研究间方差，固定效应取0。",
    "variant": "逆方差固定/随机效应；τ² 可用 DL、REML、Paule-Mandel。",
    "version": 1
   },
   "missing": [],
   "more": [],
   "needs": "statsmodels",
   "note": "二分类/连续效应量与异质性。",
   "outputs": [
    "效应量与异质性",
    "估计量与显著性"
   ],
   "scenarios": [
    "证据汇总"
   ],
   "similar": [],
   "similar_why": {},
   "suggests": [
    "model.linear"
   ],
   "tasks": [
    "regression"
   ],
   "when": "同一个问题已有多篇研究，想把效应量合并时。"
  }
 ],
 "counts": {
  "alternative": 23,
  "categories": 9,
  "groups": 31,
  "levels": 13,
  "methods": 116,
  "prerequisite": 78,
  "suggest": 56
 },
 "edges": {
  "alternative": [
   {
    "from": "model.logistic",
    "to": "model.probit",
    "why": "同为二元响应回归，分别使用 Logit 与 Probit 链接；需结合模型假设和验证表现选择。"
   },
   {
    "from": "model.logistic",
    "to": "ml.lda_qda",
    "why": "同一分类任务可比较两者；判别分析对类内分布与协方差有假设，不能在任意数据上直接互换。"
   },
   {
    "from": "eval.pca",
    "to": "eval.factor",
    "why": "多指标综合评价的两种建模方式：PCA 分解总方差，因子分析建模共同协变及潜在结构。"
   },
   {
    "from": "test.chi2",
    "to": "test.fisher",
    "why": "在同一 2×2 计数表上可检验独立性：卡方使用渐近近似，稀疏或小样本可考虑 Fisher 精确检验。"
   },
   {
    "from": "test.anova",
    "to": "test.friedman",
    "why": "仅在重复测量或配组设计下比较：重复测量 ANOVA 与 Friedman 的假设及检验目标不同，独立组 ANOVA 不可直接换成 Friedman。"
   },
   {
    "from": "model.ridge",
    "to": "model.lasso",
    "why": "都在线性回归上加正则：岭回归保留全部变量只压小系数，Lasso 会把系数压到 0 做特征选择。"
   },
   {
    "from": "series.gm11",
    "to": "series.arima",
    "why": "都要拟合趋势做外推：ARIMA 要求序列平稳或差分平稳、样本量足够，灰色预测适合小样本、近似指数增长的数据。"
   },
   {
    "from": "ml.random_forest",
    "to": "ml.xgboost",
    "why": "同一个预测任务选一个强模型：随机森林走 Bagging，XGBoost 走 Boosting。"
   },
   {
    "from": "ml.random_forest",
    "to": "ml.lightgbm",
    "why": "同一预测任务可比较袋装树与梯度提升树，结合数据规模、资源限制及验证表现选择。"
   },
   {
    "from": "ml.xgboost",
    "to": "ml.lightgbm",
    "why": "同为梯度提升的工程实现；速度和精度取决于数据、参数及训练条件，没有固定的优劣保证。"
   },
   {
    "from": "ml.gbdt",
    "to": "ml.adaboost",
    "why": "两种提升思路：GBDT 拟合负梯度，AdaBoost 提高错分样本权重。"
   },
   {
    "from": "ml.kmeans",
    "to": "ml.hierarchical",
    "why": "都可做距离分群：K-Means 先给定 k，层次聚类可以结合树状图选择切分层级。"
   },
   {
    "from": "ml.dbscan",
    "to": "ml.hierarchical",
    "why": "都靠距离结构分群，样本有噪声点时 DBSCAN 更合适。"
   },
   {
    "from": "prep.pca",
    "to": "prep.tsne",
    "why": "用于低维可视化时可比较两者：PCA 保留总体方差，t-SNE 侧重局部邻域；后者不能作为一般下游建模的等价替换。"
   },
   {
    "from": "test.ttest",
    "to": "test.mannwhitney",
    "why": "两组独立样本可比较：T 检验针对均值，方差不齐可用 Welch；Mann–Whitney 针对分布差异，额外条件下才可解释位置差异。"
   },
   {
    "from": "test.ttest",
    "to": "test.wilcoxon",
    "why": "配对比较可选择配对 T 或 Wilcoxon 符号秩检验；后者检验差值分布是否关于零对称，不能只因偏态就直接替换。"
   },
   {
    "from": "test.anova",
    "to": "test.kruskal",
    "why": "仅限多个独立组的比较：ANOVA 针对均值，Kruskal–Wallis 使用秩；将后者解释为位置差异需结合分布形状，不能直接替换重复测量 ANOVA。"
   },
   {
    "from": "eval.topsis",
    "to": "eval.vikor",
    "why": "都与理想解比较：TOPSIS 看整体距离，VIKOR 还会单独看最差的那项指标。"
   },
   {
    "from": "eval.topsis",
    "to": "eval.rsr",
    "why": "排序思路不同：TOPSIS 算贴近度，RSR 用秩次换算出分档。"
   },
   {
    "from": "eval.vikor",
    "to": "eval.rsr",
    "why": "同一组方案可以两种方法各排一次，看结论是否一致。"
   },
   {
    "from": "eval.entropy",
    "to": "eval.critic",
    "why": "赋权依据不同：熵值法看指标的信息量，CRITIC 看对比强度与指标间冲突性。"
   },
   {
    "from": "design.ccd",
    "to": "design.boxbehnken",
    "why": "拟合二次响应面的两种设计：CCD 含轴点，Box–Behnken 避开全因素同时处于极端水平；试验数取决于因素数和中心点配置。"
   },
   {
    "from": "domain.cox",
    "to": "domain.weibull",
    "why": "生存模型两条路：Cox 半参数不指定分布，Weibull 假定分布形状后可外推。"
   }
  ],
  "prerequisite": [
   {
    "from": "model.correlation",
    "to": "prep.pca",
    "why": "PCA 从协方差或相关结构提取主要变化方向，先理解变量间共同变化。"
   },
   {
    "from": "test.ttest",
    "to": "describe.power",
    "why": "先学「T 检验（单样本/独立/配对）」，才谈得上「检验功效与样本量」。"
   },
   {
    "from": "test.anova",
    "to": "describe.power",
    "why": "先学「方差分析（单因素 / 协方差）」，才谈得上「检验功效与样本量」。"
   },
   {
    "from": "describe.stats",
    "to": "test.ttest",
    "why": "t 统计量就是均值差除以标准误，先懂这两个量才看得懂输出。"
   },
   {
    "from": "describe.stats",
    "to": "test.anova",
    "why": "先学「描述性统计」，才谈得上「方差分析（单因素 / 协方差）」。"
   },
   {
    "from": "test.ttest",
    "to": "test.anova",
    "why": "先学「T 检验（单样本/独立/配对）」，才谈得上「方差分析（单因素 / 协方差）」。"
   },
   {
    "from": "describe.stats",
    "to": "test.wilcoxon",
    "why": "先学「描述性统计」，才谈得上「Wilcoxon 符号秩检验」。"
   },
   {
    "from": "describe.stats",
    "to": "test.mannwhitney",
    "why": "先学「描述性统计」，才谈得上「Mann-Whitney U 检验」。"
   },
   {
    "from": "describe.stats",
    "to": "test.kruskal",
    "why": "先学「描述性统计」，才谈得上「Kruskal-Wallis H 检验」。"
   },
   {
    "from": "describe.stats",
    "to": "test.friedman",
    "why": "先学「描述性统计」，才谈得上「Friedman 检验」。"
   },
   {
    "from": "describe.crosstab",
    "to": "test.cochran",
    "why": "先学「列联表」，才谈得上「Cochran's Q 检验」。"
   },
   {
    "from": "describe.crosstab",
    "to": "test.chi2",
    "why": "卡方检验的输入就是列联表，先会读交叉频数与百分比。"
   },
   {
    "from": "describe.frequency",
    "to": "test.gof",
    "why": "拟合优度比较的是观测频数与理论频数。"
   },
   {
    "from": "describe.crosstab",
    "to": "test.fisher",
    "why": "精确检验算的还是 2×2 列联表的概率。"
   },
   {
    "from": "describe.stats",
    "to": "model.correlation",
    "why": "先理解均值、变异和分布，才能解释相关系数及异常值对相关性的影响。"
   },
   {
    "from": "model.correlation",
    "to": "model.canonical",
    "why": "先学「相关分析」，才谈得上「典型相关分析」。"
   },
   {
    "from": "model.correlation",
    "to": "model.vif",
    "why": "先学「相关分析」，才谈得上「VIF 共线性诊断」。"
   },
   {
    "from": "model.correlation",
    "to": "model.linear",
    "why": "回归系数与相关系数同源，先看相关再谈影响大小。"
   },
   {
    "from": "model.linear",
    "to": "model.ridge",
    "why": "岭回归只是在线性回归的损失上加了一项 L2 惩罚。"
   },
   {
    "from": "model.linear",
    "to": "model.lasso",
    "why": "先学「线性回归」，才谈得上「Lasso 回归」。"
   },
   {
    "from": "model.ridge",
    "to": "model.elasticnet",
    "why": "弹性网是岭回归与 Lasso 的凸组合，两项都要先看懂。"
   },
   {
    "from": "model.lasso",
    "to": "model.elasticnet",
    "why": "先学「Lasso 回归」，才谈得上「ElasticNet」。"
   },
   {
    "from": "model.linear",
    "to": "model.logistic",
    "why": "Logistic 就是把线性预测值压进 0–1 的链接函数。"
   },
   {
    "from": "model.linear",
    "to": "model.probit",
    "why": "先学「线性回归」，才谈得上「Probit 回归」。"
   },
   {
    "from": "model.linear",
    "to": "model.robust",
    "why": "先学「线性回归」，才谈得上「稳健性检验」。"
   },
   {
    "from": "model.linear",
    "to": "model.mediation",
    "why": "先学「线性回归」，才谈得上「中介效应」。"
   },
   {
    "from": "model.linear",
    "to": "model.moderation",
    "why": "先学「线性回归」，才谈得上「调节效应」。"
   },
   {
    "from": "model.mediation",
    "to": "model.chained",
    "why": "先学「中介效应」，才谈得上「链式中介」。"
   },
   {
    "from": "model.linear",
    "to": "model.gamma",
    "why": "先学「线性回归」，才谈得上「Gamma 回归」。"
   },
   {
    "from": "model.linear",
    "to": "model.poisson",
    "why": "先学「线性回归」，才谈得上「泊松回归」。"
   },
   {
    "from": "model.linear",
    "to": "model.gee",
    "why": "先学「线性回归」，才谈得上「GEE 广义估计方程」。"
   },
   {
    "from": "model.logistic",
    "to": "model.glmm",
    "why": "先学「Logistic 回归（二分类/多分类）」，才谈得上「GLMM 广义线性混合模型」。"
   },
   {
    "from": "model.linear",
    "to": "model.mixed",
    "why": "先学「线性回归」，才谈得上「混合效应模型」。"
   },
   {
    "from": "ml.kmeans",
    "to": "ml.fcm",
    "why": "模糊 C 均值把 K-Means 的硬归属换成了隶属度。"
   },
   {
    "from": "ml.trees",
    "to": "ml.random_forest",
    "why": "随机森林是很多棵决策树的 Bagging 集成，先懂单棵树怎么分裂。"
   },
   {
    "from": "ml.trees",
    "to": "ml.xgboost",
    "why": "先学「CART 决策树（基尼 / 熵）」，才谈得上「XGBoost」。"
   },
   {
    "from": "ml.trees",
    "to": "ml.lightgbm",
    "why": "先学「CART 决策树（基尼 / 熵）」，才谈得上「LightGBM」。"
   },
   {
    "from": "ml.trees",
    "to": "ml.adaboost",
    "why": "先学「CART 决策树（基尼 / 熵）」，才谈得上「AdaBoost」。"
   },
   {
    "from": "ml.trees",
    "to": "ml.gbdt",
    "why": "梯度提升里每棵新树拟合的是上一轮的负梯度。"
   },
   {
    "from": "model.correlation",
    "to": "ml.lda_qda",
    "why": "判别分析比较类均值与协方差结构，先理解变量间相关及类内变异。"
   },
   {
    "from": "series.adf",
    "to": "series.arima",
    "why": "单位根检验辅助选择差分候选阶数；还需结合序列图形、模型诊断和验证，不能由一次检验唯一决定。"
   },
   {
    "from": "series.arima",
    "to": "series.sarima",
    "why": "季节性 ARIMA 在 ARIMA 上多加了一层季节项。"
   },
   {
    "from": "describe.stats",
    "to": "series.garch",
    "why": "先学「描述性统计」，才谈得上「GARCH 波动率」。"
   },
   {
    "from": "series.adf",
    "to": "series.var",
    "why": "先学「单位根检验 ADF」，才谈得上「VAR 向量自回归」。"
   },
   {
    "from": "series.adf",
    "to": "series.coint",
    "why": "协整检验建立在同阶单整之上，先做单位根检验。"
   },
   {
    "from": "series.adf",
    "to": "series.granger",
    "why": "先学「单位根检验 ADF」，才谈得上「格兰杰因果检验」。"
   },
   {
    "from": "describe.stats",
    "to": "series.moran",
    "why": "Moran's I 使用围绕均值的偏差及方差刻画空间关联。"
   },
   {
    "from": "series.moran",
    "to": "series.spatial",
    "why": "Moran's I 辅助诊断空间关联；空间权重由邻接或距离等规则设定，是否采用空间回归还需模型诊断。"
   },
   {
    "from": "model.linear",
    "to": "series.panel",
    "why": "先学「线性回归」，才谈得上「面板数据模型」。"
   },
   {
    "from": "model.linear",
    "to": "series.threshold",
    "why": "先学「线性回归」，才谈得上「门槛回归」。"
   },
   {
    "from": "model.linear",
    "to": "series.tobit",
    "why": "先学「线性回归」，才谈得上「Tobit 回归」。"
   },
   {
    "from": "model.linear",
    "to": "series.quantile",
    "why": "先学「线性回归」，才谈得上「分位数回归」。"
   },
   {
    "from": "model.linear",
    "to": "causal.did",
    "why": "先学「线性回归」，才谈得上「双重差分 DID」。"
   },
   {
    "from": "model.logistic",
    "to": "causal.psm",
    "why": "先学「Logistic 回归（二分类/多分类）」，才谈得上「倾向得分匹配 PSM」。"
   },
   {
    "from": "causal.psm",
    "to": "causal.psmdid",
    "why": "PSM-DID 先用 PSM 匹配样本，再在匹配样本上做 DID。"
   },
   {
    "from": "causal.did",
    "to": "causal.psmdid",
    "why": "先学「双重差分 DID」，才谈得上「PSM-DID」。"
   },
   {
    "from": "model.linear",
    "to": "causal.rd",
    "why": "先学「线性回归」，才谈得上「断点回归 RD」。"
   },
   {
    "from": "model.probit",
    "to": "causal.heckman",
    "why": "先学「Probit 回归」，才谈得上「Heckman 两步法」。"
   },
   {
    "from": "causal.did",
    "to": "causal.placebo",
    "why": "先学「双重差分 DID」，才谈得上「安慰剂检验」。"
   },
   {
    "from": "test.anova",
    "to": "design.factorial",
    "why": "先学「方差分析（单因素 / 协方差）」，才谈得上「全因子设计」。"
   },
   {
    "from": "design.factorial",
    "to": "design.orthogonal",
    "why": "先学「全因子设计」，才谈得上「正交设计」。"
   },
   {
    "from": "design.factorial",
    "to": "design.uniform",
    "why": "先学「全因子设计」，才谈得上「均匀设计」。"
   },
   {
    "from": "design.factorial",
    "to": "design.rsm",
    "why": "先学「全因子设计」，才谈得上「响应面分析 RSM」。"
   },
   {
    "from": "design.factorial",
    "to": "design.ccd",
    "why": "中心复合设计是全因子设计加上星点与中心点。"
   },
   {
    "from": "design.factorial",
    "to": "design.boxbehnken",
    "why": "先学「全因子设计」，才谈得上「Box-Behnken 设计」。"
   },
   {
    "from": "prep.pca",
    "to": "eval.pca",
    "why": "主成分分析评价直接把 PCA 的方差贡献率当成权重。"
   },
   {
    "from": "model.correlation",
    "to": "eval.factor",
    "why": "因子分析建模共同协变和潜在结构，不是先运行 PCA 评价再加一层；先理解相关矩阵。"
   },
   {
    "from": "describe.frequency",
    "to": "domain.wordfreq",
    "why": "先学「频数分析」，才谈得上「词频统计」。"
   },
   {
    "from": "domain.wordfreq",
    "to": "domain.tfidf",
    "why": "先学「词频统计」，才谈得上「TF-IDF」。"
   },
   {
    "from": "domain.wordfreq",
    "to": "domain.sentiment",
    "why": "先学「词频统计」，才谈得上「情感分析」。"
   },
   {
    "from": "domain.wordfreq",
    "to": "domain.lda",
    "why": "本项目 LDA 主题模型使用词频矩阵；先理解文档中的计数表示，不要求先使用 TF-IDF。"
   },
   {
    "from": "describe.stats",
    "to": "domain.cox",
    "why": "先学「描述性统计」，才谈得上「Cox 比例风险回归」。"
   },
   {
    "from": "domain.cox",
    "to": "domain.nomogram",
    "why": "列线图把 Cox 的回归系数换算成个体得分。"
   },
   {
    "from": "describe.stats",
    "to": "domain.competing",
    "why": "先学「描述性统计」，才谈得上「竞争风险模型」。"
   },
   {
    "from": "describe.frequency",
    "to": "domain.kano",
    "why": "先学「频数分析」，才谈得上「Kano 模型」。"
   },
   {
    "from": "describe.stats",
    "to": "domain.control",
    "why": "先学「描述性统计」，才谈得上「控制图（X-bar/R、CUSUM、EWMA）」。"
   },
   {
    "from": "domain.control",
    "to": "domain.capability",
    "why": "先用控制图确认过程稳定，过程能力指数才有意义。"
   },
   {
    "from": "describe.stats",
    "to": "domain.meta",
    "why": "常规 Meta 分析合并效应量和方差，需理解估计与不确定性，不以线性回归为运行前提。"
   }
  ],
  "suggest": [
   {
    "from": "prep.duplicates",
    "to": "prep.missing",
    "why": "先看「重复值处理」，再学「缺失值处理」会顺一些。"
   },
   {
    "from": "prep.missing",
    "to": "prep.encoding",
    "why": "缺失值没处理完，编码出来的类别会有空洞。"
   },
   {
    "from": "prep.missing",
    "to": "prep.derive",
    "why": "先看「缺失值处理」，再学「生成变量」会顺一些。"
   },
   {
    "from": "prep.outliers",
    "to": "prep.winsorize",
    "why": "先看「异常值处理」，再学「缩尾处理 Winsorize」会顺一些。"
   },
   {
    "from": "prep.outliers",
    "to": "prep.transform",
    "why": "先看「异常值处理」，再学「数据变换 Box-Cox / Yeo-Johnson」会顺一些。"
   },
   {
    "from": "prep.missing",
    "to": "prep.balance",
    "why": "先补齐再重采样，否则少数类的合成样本会失真。"
   },
   {
    "from": "prep.missing",
    "to": "prep.scale",
    "why": "先看「缺失值处理」，再学「标准化与归一化」会顺一些。"
   },
   {
    "from": "prep.scale",
    "to": "prep.tsne",
    "why": "t-SNE 按距离算相似度，量纲不统一会直接扭曲邻域结构。"
   },
   {
    "from": "prep.scale",
    "to": "prep.pca",
    "why": "不同量纲可能让大方差变量主导 PCA；是否标准化需结合变量单位和分析目的，并非固定必做步骤。"
   },
   {
    "from": "describe.frequency",
    "to": "describe.crosstab",
    "why": "先看「频数分析」，再学「列联表」会顺一些。"
   },
   {
    "from": "describe.stats",
    "to": "describe.aggregate",
    "why": "先看「描述性统计」，再学「分类汇总」会顺一些。"
   },
   {
    "from": "describe.stats",
    "to": "describe.explore",
    "why": "先看「描述性统计」，再学「数据探索」会顺一些。"
   },
   {
    "from": "test.friedman",
    "to": "test.cochran",
    "why": "先看「Friedman 检验」，再学「Cochran's Q 检验」会顺一些。"
   },
   {
    "from": "prep.scale",
    "to": "model.ridge",
    "why": "先看「标准化与归一化」，再学「岭回归」会顺一些。"
   },
   {
    "from": "model.vif",
    "to": "model.ridge",
    "why": "VIF 可辅助识别共线性，但岭回归可以直接拟合，不要求先计算 VIF。"
   },
   {
    "from": "prep.scale",
    "to": "model.lasso",
    "why": "先看「标准化与归一化」，再学「Lasso 回归」会顺一些。"
   },
   {
    "from": "model.vif",
    "to": "model.lasso",
    "why": "VIF 可辅助理解共线性与变量选择，但 Lasso 不要求先运行共线性诊断。"
   },
   {
    "from": "prep.scale",
    "to": "model.elasticnet",
    "why": "先看「标准化与归一化」，再学「ElasticNet」会顺一些。"
   },
   {
    "from": "prep.scale",
    "to": "ml.kmeans",
    "why": "先看「标准化与归一化」，再学「K-Means 聚类」会顺一些。"
   },
   {
    "from": "prep.scale",
    "to": "ml.hierarchical",
    "why": "先看「标准化与归一化」，再学「分层聚类」会顺一些。"
   },
   {
    "from": "prep.scale",
    "to": "ml.dbscan",
    "why": "先看「标准化与归一化」，再学「DBSCAN 聚类」会顺一些。"
   },
   {
    "from": "ml.kmeans",
    "to": "ml.dbscan",
    "why": "先掌握一种划分式聚类，再理解基于密度的思路。"
   },
   {
    "from": "prep.scale",
    "to": "ml.svm",
    "why": "先看「标准化与归一化」，再学「支持向量机 SVM」会顺一些。"
   },
   {
    "from": "prep.scale",
    "to": "ml.knn",
    "why": "先看「标准化与归一化」，再学「K 近邻 KNN」会顺一些。"
   },
   {
    "from": "describe.stats",
    "to": "ml.nb",
    "why": "先看「描述性统计」，再学「朴素贝叶斯」会顺一些。"
   },
   {
    "from": "prep.scale",
    "to": "ml.mlp",
    "why": "先看「标准化与归一化」，再学「神经网络 MLP」会顺一些。"
   },
   {
    "from": "prep.scale",
    "to": "ml.rbf",
    "why": "先看「标准化与归一化」，再学「RBF 径向基网络」会顺一些。"
   },
   {
    "from": "describe.stats",
    "to": "ml.trees",
    "why": "先看「描述性统计」，再学「CART 决策树（基尼 / 熵）」会顺一些。"
   },
   {
    "from": "prep.scale",
    "to": "ml.lda_qda",
    "why": "先看「标准化与归一化」，再学「判别分析 LDA / QDA」会顺一些。"
   },
   {
    "from": "prep.spectral",
    "to": "series.sarima",
    "why": "先看「时序谱特征」，再学「季节性 ARIMA」会顺一些。"
   },
   {
    "from": "series.arima",
    "to": "series.garch",
    "why": "先看「ARIMA」，再学「GARCH 波动率」会顺一些。"
   },
   {
    "from": "describe.stats",
    "to": "series.adf",
    "why": "先看「描述性统计」，再学「单位根检验 ADF」会顺一些。"
   },
   {
    "from": "model.correlation",
    "to": "series.moran",
    "why": "先比较普通相关与空间自相关；单变量 Moran's I 不要求先对变量进行标准化。"
   },
   {
    "from": "series.arima",
    "to": "series.panel",
    "why": "先看「ARIMA」，再学「面板数据模型」会顺一些。"
   },
   {
    "from": "describe.crosstab",
    "to": "causal.did",
    "why": "先看「列联表」，再学「双重差分 DID」会顺一些。"
   },
   {
    "from": "design.orthogonal",
    "to": "design.uniform",
    "why": "先看「正交设计」，再学「均匀设计」会顺一些。"
   },
   {
    "from": "design.ccd",
    "to": "design.rsm",
    "why": "CCD 是响应面常见布点方案之一，也可选择 Box–Behnken 等设计。"
   },
   {
    "from": "design.boxbehnken",
    "to": "design.rsm",
    "why": "Box–Behnken 是响应面布点的可选方案，需结合因素数和可行试验区域选择。"
   },
   {
    "from": "prep.pca",
    "to": "eval.factor",
    "why": "对照 PCA 的方差分解与因子分析的共同协变模型，帮助理解两种提取思路。"
   },
   {
    "from": "eval.entropy",
    "to": "eval.topsis",
    "why": "TOPSIS 可用等权、熵权、CRITIC 或自定义权重；熵值法是可选赋权来源。"
   },
   {
    "from": "eval.entropy",
    "to": "eval.vikor",
    "why": "VIKOR 需要选定权重，熵值法只是本项目支持的赋权选项之一。"
   },
   {
    "from": "eval.entropy",
    "to": "eval.rsr",
    "why": "加权 RSR 可采用熵权，也可以使用等权或其他权重，不要求先做熵值法。"
   },
   {
    "from": "eval.entropy",
    "to": "eval.dea",
    "why": "先看「熵值法」，再学「数据包络分析 DEA」会顺一些。"
   },
   {
    "from": "eval.entropy",
    "to": "eval.fuzzy",
    "why": "模糊综合评价可使用不同来源的权重，熵值法是可选准备知识。"
   },
   {
    "from": "describe.stats",
    "to": "eval.grey",
    "why": "先看「描述性统计」，再学「灰色关联分析」会顺一些。"
   },
   {
    "from": "domain.tfidf",
    "to": "domain.lda",
    "why": "比较计数与 TF-IDF 的表示差异有助理解主题模型输入；通常应给 LDA 词频计数。"
   },
   {
    "from": "describe.stats",
    "to": "domain.km",
    "why": "先看「描述性统计」，再学「Kaplan-Meier 生存曲线」会顺一些。"
   },
   {
    "from": "domain.km",
    "to": "domain.cox",
    "why": "先读生存曲线有助理解时间与删失；Cox 可直接拟合，不要求先运行 Kaplan–Meier。"
   },
   {
    "from": "domain.km",
    "to": "domain.competing",
    "why": "先理解删失与生存曲线；竞争事件应使用对应的累计发生函数，不能直接用一减 KM 代替。"
   },
   {
    "from": "describe.stats",
    "to": "domain.reliability",
    "why": "先看「描述性统计」，再学「信度效度分析」会顺一些。"
   },
   {
    "from": "describe.frequency",
    "to": "domain.nps",
    "why": "先看「频数分析」，再学「NPS 净推荐值」会顺一些。"
   },
   {
    "from": "describe.stats",
    "to": "domain.maxdiff",
    "why": "先看「描述性统计」，再学「MaxDiff 评分推导（非选择模型）」会顺一些。"
   },
   {
    "from": "describe.stats",
    "to": "domain.conjoint",
    "why": "先看「描述性统计」，再学「联合分析」会顺一些。"
   },
   {
    "from": "describe.stats",
    "to": "domain.psm",
    "why": "先看「描述性统计」，再学「价格分位数与需求代理（非四问 PSM）」会顺一些。"
   },
   {
    "from": "describe.stats",
    "to": "domain.weibull",
    "why": "先看「描述性统计」，再学「Weibull 可靠性分析」会顺一些。"
   },
   {
    "from": "model.linear",
    "to": "domain.meta",
    "why": "回归知识有助理解扩展的元回归，但本次常规效应量合并不要求先做线性回归。"
   }
  ]
 },
 "layers": [
  {
   "count": 5,
   "groups": [
    "描述统计"
   ],
   "hint": "先看清数据长什么样：统计量、频数、交叉表与分组汇总。",
   "level": 1,
   "methods": [
    "describe.frequency",
    "describe.stats",
    "describe.crosstab",
    "describe.aggregate",
    "describe.explore"
   ],
   "name": "数据认知与描述统计"
  },
  {
   "count": 5,
   "groups": [
    "数据清洗",
    "特征工程"
   ],
   "hint": "把脏数据收拾干净：重复值、缺失值、异常值与变换。",
   "level": 2,
   "methods": [
    "prep.outliers",
    "prep.missing",
    "prep.duplicates",
    "prep.winsorize",
    "prep.transform"
   ],
   "name": "数据清洗"
  },
  {
   "count": 5,
   "groups": [
    "特征工程",
    "相关分析"
   ],
   "hint": "把变量整理成模型能用的形状，并看清它们之间的关系。",
   "level": 3,
   "methods": [
    "prep.encoding",
    "prep.derive",
    "prep.balance",
    "prep.scale",
    "model.correlation"
   ],
   "name": "探索分析"
  },
  {
   "count": 10,
   "groups": [
    "非参数检验",
    "离散数据检验",
    "参数检验"
   ],
   "hint": "从样本推到总体：参数检验与非参数检验。",
   "level": 4,
   "methods": [
    "test.ttest",
    "test.anova",
    "test.wilcoxon",
    "test.mannwhitney",
    "test.kruskal",
    "test.friedman",
    "test.cochran",
    "test.chi2",
    "test.gof",
    "test.fisher"
   ],
   "name": "基础统计推断"
  },
  {
   "count": 7,
   "groups": [
    "聚类分析",
    "经典算法",
    "树模型"
   ],
   "hint": "第一个预测模型与最基础的聚类：树、近邻、K-Means、DBSCAN 与模糊聚类。",
   "level": 5,
   "methods": [
    "ml.kmeans",
    "ml.hierarchical",
    "ml.dbscan",
    "ml.fcm",
    "ml.knn",
    "ml.nb",
    "ml.trees"
   ],
   "name": "基础机器学习"
  },
  {
   "count": 8,
   "groups": [
    "集成学习",
    "神经网络",
    "经典算法"
   ],
   "hint": "把模型合起来或换成更强的拟合器：袋装、提升、支持向量机与神经网络。",
   "level": 6,
   "methods": [
    "ml.random_forest",
    "ml.xgboost",
    "ml.lightgbm",
    "ml.adaboost",
    "ml.gbdt",
    "ml.svm",
    "ml.mlp",
    "ml.rbf"
   ],
   "name": "集成与神经网络"
  },
  {
   "count": 16,
   "groups": [
    "回归分析",
    "广义模型",
    "机制分析",
    "相关分析"
   ],
   "hint": "回归家族与机制模型：正则、广义线性、多层模型与中介调节。",
   "level": 7,
   "methods": [
    "model.vif",
    "model.linear",
    "model.ridge",
    "model.lasso",
    "model.elasticnet",
    "model.logistic",
    "model.probit",
    "model.robust",
    "model.mediation",
    "model.moderation",
    "model.chained",
    "model.gamma",
    "model.poisson",
    "model.gee",
    "model.glmm",
    "model.mixed"
   ],
   "name": "回归与机制模型"
  },
  {
   "count": 6,
   "groups": [
    "客观赋权",
    "降维",
    "相关分析",
    "经典算法"
   ],
   "hint": "多个变量一起看：主成分、t-SNE、因子、判别与典型相关。",
   "level": 8,
   "methods": [
    "prep.tsne",
    "prep.pca",
    "model.canonical",
    "ml.lda_qda",
    "eval.pca",
    "eval.factor"
   ],
   "name": "降维与多变量"
  },
  {
   "count": 15,
   "groups": [
    "时间序列",
    "面板数据",
    "空间计量",
    "时序特征"
   ],
   "hint": "带时间与空间结构的数据：序列、波动、面板、空间与谱特征。",
   "level": 9,
   "methods": [
    "prep.spectral",
    "series.arima",
    "series.sarima",
    "series.garch",
    "series.var",
    "series.adf",
    "series.coint",
    "series.granger",
    "series.gm11",
    "series.moran",
    "series.spatial",
    "series.panel",
    "series.threshold",
    "series.tobit",
    "series.quantile"
   ],
   "name": "时间与面板数据"
  },
  {
   "count": 6,
   "groups": [
    "因果推断"
   ],
   "hint": "从观察数据里识别因果：双重差分、断点、倾向得分与 Heckman。",
   "level": 10,
   "methods": [
    "causal.did",
    "causal.psm",
    "causal.psmdid",
    "causal.rd",
    "causal.heckman",
    "causal.placebo"
   ],
   "name": "因果推断"
  },
  {
   "count": 7,
   "groups": [
    "实验设计",
    "功效分析"
   ],
   "hint": "先算清需要多少样本，再主动做实验并按响应面寻优。",
   "level": 11,
   "methods": [
    "describe.power",
    "design.factorial",
    "design.orthogonal",
    "design.uniform",
    "design.rsm",
    "design.ccd",
    "design.boxbehnken"
   ],
   "name": "实验设计与优化"
  },
  {
   "count": 8,
   "groups": [
    "排序决策",
    "客观赋权",
    "效率评价"
   ],
   "hint": "把多指标合成一个评价值：客观赋权与决策排序。",
   "level": 12,
   "methods": [
    "eval.entropy",
    "eval.critic",
    "eval.topsis",
    "eval.vikor",
    "eval.rsr",
    "eval.dea",
    "eval.fuzzy",
    "eval.grey"
   ],
   "name": "综合评价与决策"
  },
  {
   "count": 18,
   "groups": [
    "问卷与市场",
    "文本分析",
    "生存分析",
    "质量控制",
    "Meta 分析"
   ],
   "hint": "面向具体数据类型与业务场景：生存、文本、问卷、质量控制与 Meta。",
   "level": 13,
   "methods": [
    "domain.wordfreq",
    "domain.tfidf",
    "domain.sentiment",
    "domain.lda",
    "domain.km",
    "domain.cox",
    "domain.nomogram",
    "domain.competing",
    "domain.reliability",
    "domain.nps",
    "domain.kano",
    "domain.maxdiff",
    "domain.conjoint",
    "domain.psm",
    "domain.control",
    "domain.capability",
    "domain.weibull",
    "domain.meta"
   ],
   "name": "行业与专题方法"
  }
 ],
 "problems": [],
 "scenarios": [
  {
   "methods": [
    "prep.outliers",
    "prep.missing",
    "prep.duplicates"
   ],
   "name": "数据清洗"
  },
  {
   "methods": [
    "prep.encoding",
    "prep.derive",
    "prep.winsorize",
    "prep.transform",
    "prep.balance",
    "prep.scale",
    "prep.spectral"
   ],
   "name": "特征构造"
  },
  {
   "methods": [
    "prep.tsne",
    "prep.pca"
   ],
   "name": "降维与可视化"
  },
  {
   "methods": [
    "describe.frequency",
    "describe.stats",
    "describe.crosstab",
    "describe.aggregate",
    "describe.explore"
   ],
   "name": "分布探索"
  },
  {
   "methods": [
    "test.ttest",
    "test.anova",
    "test.wilcoxon",
    "test.mannwhitney",
    "test.kruskal",
    "test.friedman",
    "test.cochran",
    "test.chi2",
    "test.gof",
    "test.fisher"
   ],
   "name": "组间差异比较"
  },
  {
   "methods": [
    "model.correlation",
    "model.canonical",
    "model.vif"
   ],
   "name": "关联探索"
  },
  {
   "methods": [
    "model.correlation",
    "model.canonical",
    "model.vif",
    "model.linear",
    "model.ridge",
    "model.lasso",
    "model.elasticnet",
    "model.logistic",
    "model.probit",
    "model.robust",
    "model.gamma",
    "model.poisson",
    "model.gee",
    "model.glmm",
    "model.mixed"
   ],
   "name": "影响因素分析"
  },
  {
   "methods": [
    "model.mediation",
    "model.moderation",
    "model.chained"
   ],
   "name": "影响机制"
  },
  {
   "methods": [
    "model.linear",
    "model.ridge",
    "model.lasso",
    "model.elasticnet",
    "model.logistic",
    "model.probit",
    "model.robust",
    "model.gamma",
    "model.poisson",
    "model.gee",
    "model.glmm",
    "model.mixed",
    "ml.random_forest",
    "ml.xgboost",
    "ml.lightgbm",
    "ml.adaboost",
    "ml.gbdt",
    "ml.svm",
    "ml.knn",
    "ml.nb",
    "ml.mlp",
    "ml.rbf",
    "ml.trees",
    "ml.lda_qda"
   ],
   "name": "预测建模"
  },
  {
   "methods": [
    "test.chi2",
    "test.gof",
    "test.fisher"
   ],
   "name": "分类预测"
  },
  {
   "methods": [
    "ml.random_forest",
    "ml.xgboost",
    "ml.lightgbm",
    "ml.adaboost",
    "ml.gbdt"
   ],
   "name": "特征重要性"
  },
  {
   "methods": [
    "ml.trees"
   ],
   "name": "规则提取"
  },
  {
   "methods": [
    "ml.kmeans",
    "ml.hierarchical",
    "ml.dbscan",
    "ml.fcm"
   ],
   "name": "客户分群"
  },
  {
   "methods": [
    "ml.kmeans",
    "ml.hierarchical",
    "ml.dbscan",
    "ml.fcm"
   ],
   "name": "结构发现"
  },
  {
   "methods": [
    "prep.spectral",
    "series.arima",
    "series.sarima",
    "series.garch",
    "series.var",
    "series.adf",
    "series.coint",
    "series.granger",
    "series.gm11"
   ],
   "name": "时序预测"
  },
  {
   "methods": [
    "series.arima",
    "series.sarima",
    "series.garch",
    "series.var",
    "series.adf",
    "series.coint",
    "series.granger",
    "series.gm11"
   ],
   "name": "平稳性诊断"
  },
  {
   "methods": [
    "series.moran",
    "series.spatial"
   ],
   "name": "空间分析"
  },
  {
   "methods": [
    "series.panel",
    "series.threshold",
    "series.tobit",
    "series.quantile"
   ],
   "name": "面板分析"
  },
  {
   "methods": [
    "causal.did",
    "causal.psm",
    "causal.psmdid",
    "causal.rd",
    "causal.heckman",
    "causal.placebo"
   ],
   "name": "因果效应评估"
  },
  {
   "methods": [
    "causal.did",
    "causal.psm",
    "causal.psmdid",
    "causal.rd",
    "causal.heckman",
    "causal.placebo"
   ],
   "name": "政策评估"
  },
  {
   "methods": [
    "describe.power",
    "design.factorial",
    "design.orthogonal",
    "design.uniform",
    "design.rsm",
    "design.ccd",
    "design.boxbehnken"
   ],
   "name": "实验设计"
  },
  {
   "methods": [
    "eval.pca",
    "eval.factor",
    "eval.entropy",
    "eval.critic",
    "eval.topsis",
    "eval.vikor",
    "eval.rsr",
    "eval.fuzzy",
    "eval.grey"
   ],
   "name": "指标赋权"
  },
  {
   "methods": [
    "eval.topsis",
    "eval.vikor",
    "eval.rsr",
    "eval.fuzzy",
    "eval.grey"
   ],
   "name": "方案排序"
  },
  {
   "methods": [
    "eval.dea"
   ],
   "name": "效率评价"
  },
  {
   "methods": [
    "domain.wordfreq",
    "domain.tfidf",
    "domain.sentiment",
    "domain.lda"
   ],
   "name": "文本分析"
  },
  {
   "methods": [
    "domain.km",
    "domain.cox",
    "domain.nomogram",
    "domain.competing"
   ],
   "name": "生存分析"
  },
  {
   "methods": [
    "domain.reliability",
    "domain.nps",
    "domain.kano",
    "domain.maxdiff",
    "domain.conjoint",
    "domain.psm"
   ],
   "name": "问卷分析"
  },
  {
   "methods": [
    "domain.reliability",
    "domain.nps",
    "domain.kano",
    "domain.maxdiff",
    "domain.conjoint",
    "domain.psm"
   ],
   "name": "市场调研"
  },
  {
   "methods": [
    "domain.control",
    "domain.capability",
    "domain.weibull"
   ],
   "name": "质量控制"
  },
  {
   "methods": [
    "domain.meta"
   ],
   "name": "证据汇总"
  }
 ],
 "tree": [
  {
   "count": 12,
   "groups": [
    {
     "count": 3,
     "kind": "数据清洗",
     "methods": [
      "prep.outliers",
      "prep.missing",
      "prep.duplicates"
     ],
     "name": "数据清洗"
    },
    {
     "count": 6,
     "kind": "特征构造",
     "methods": [
      "prep.encoding",
      "prep.derive",
      "prep.winsorize",
      "prep.transform",
      "prep.balance",
      "prep.scale"
     ],
     "name": "特征工程"
    },
    {
     "count": 2,
     "kind": "降维",
     "methods": [
      "prep.tsne",
      "prep.pca"
     ],
     "name": "降维"
    },
    {
     "count": 1,
     "kind": "特征构造",
     "methods": [
      "prep.spectral"
     ],
     "name": "时序特征"
    }
   ],
   "hint": "解决数据能不能用、好不好用的问题。",
   "key": "prep",
   "name": "数据准备与特征工程",
   "scenarios": [
    "数据清洗",
    "时序预测",
    "特征构造",
    "降维与可视化"
   ]
  },
  {
   "count": 6,
   "groups": [
    {
     "count": 5,
     "kind": "描述统计",
     "methods": [
      "describe.frequency",
      "describe.stats",
      "describe.crosstab",
      "describe.aggregate",
      "describe.explore"
     ],
     "name": "描述统计"
    },
    {
     "count": 1,
     "kind": "统计检验",
     "methods": [
      "describe.power"
     ],
     "name": "功效分析"
    }
   ],
   "hint": "了解数据的基本分布与整体情况。",
   "key": "describe",
   "name": "基础统计与描述性分析",
   "scenarios": [
    "分布探索",
    "实验设计"
   ]
  },
  {
   "count": 10,
   "groups": [
    {
     "count": 2,
     "kind": "统计检验",
     "methods": [
      "test.ttest",
      "test.anova"
     ],
     "name": "参数检验"
    },
    {
     "count": 5,
     "kind": "统计检验",
     "methods": [
      "test.wilcoxon",
      "test.mannwhitney",
      "test.kruskal",
      "test.friedman",
      "test.cochran"
     ],
     "name": "非参数检验"
    },
    {
     "count": 3,
     "kind": "统计检验",
     "methods": [
      "test.chi2",
      "test.gof",
      "test.fisher"
     ],
     "name": "离散数据检验"
    }
   ],
   "hint": "判断组间差异是否具有统计显著性。",
   "key": "test",
   "name": "差异性检验与假设检验",
   "scenarios": [
    "分类预测",
    "组间差异比较"
   ]
  },
  {
   "count": 18,
   "groups": [
    {
     "count": 3,
     "kind": "相关分析",
     "methods": [
      "model.correlation",
      "model.canonical",
      "model.vif"
     ],
     "name": "相关分析"
    },
    {
     "count": 7,
     "kind": "预测模型",
     "methods": [
      "model.linear",
      "model.ridge",
      "model.lasso",
      "model.elasticnet",
      "model.logistic",
      "model.probit",
      "model.robust"
     ],
     "name": "回归分析"
    },
    {
     "count": 3,
     "kind": "影响机制",
     "methods": [
      "model.mediation",
      "model.moderation",
      "model.chained"
     ],
     "name": "机制分析"
    },
    {
     "count": 5,
     "kind": "预测模型",
     "methods": [
      "model.gamma",
      "model.poisson",
      "model.gee",
      "model.glmm",
      "model.mixed"
     ],
     "name": "广义模型"
    }
   ],
   "hint": "探究关联、因果与预测关系。",
   "key": "model",
   "name": "关系与影响建模",
   "scenarios": [
    "关联探索",
    "影响因素分析",
    "影响机制",
    "预测建模"
   ]
  },
  {
   "count": 16,
   "groups": [
    {
     "count": 4,
     "kind": "聚类",
     "methods": [
      "ml.kmeans",
      "ml.hierarchical",
      "ml.dbscan",
      "ml.fcm"
     ],
     "name": "聚类分析"
    },
    {
     "count": 5,
     "kind": "预测模型",
     "methods": [
      "ml.random_forest",
      "ml.xgboost",
      "ml.lightgbm",
      "ml.adaboost",
      "ml.gbdt"
     ],
     "name": "集成学习"
    },
    {
     "count": 4,
     "kind": "预测模型",
     "methods": [
      "ml.svm",
      "ml.knn",
      "ml.nb",
      "ml.lda_qda"
     ],
     "name": "经典算法"
    },
    {
     "count": 2,
     "kind": "预测模型",
     "methods": [
      "ml.mlp",
      "ml.rbf"
     ],
     "name": "神经网络"
    },
    {
     "count": 1,
     "kind": "预测模型",
     "methods": [
      "ml.trees"
     ],
     "name": "树模型"
    }
   ],
   "hint": "无监督发现结构与有监督预测。",
   "key": "ml",
   "name": "分类、聚类与机器学习",
   "scenarios": [
    "客户分群",
    "特征重要性",
    "结构发现",
    "规则提取",
    "预测建模"
   ]
  },
  {
   "count": 14,
   "groups": [
    {
     "count": 8,
     "kind": "时序建模",
     "methods": [
      "series.arima",
      "series.sarima",
      "series.garch",
      "series.var",
      "series.adf",
      "series.coint",
      "series.granger",
      "series.gm11"
     ],
     "name": "时间序列"
    },
    {
     "count": 2,
     "kind": "空间建模",
     "methods": [
      "series.moran",
      "series.spatial"
     ],
     "name": "空间计量"
    },
    {
     "count": 4,
     "kind": "面板建模",
     "methods": [
      "series.panel",
      "series.threshold",
      "series.tobit",
      "series.quantile"
     ],
     "name": "面板数据"
    }
   ],
   "hint": "处理时间先后或空间位置特征的数据。",
   "key": "series",
   "name": "时间序列与空间计量",
   "scenarios": [
    "平稳性诊断",
    "时序预测",
    "空间分析",
    "面板分析"
   ]
  },
  {
   "count": 12,
   "groups": [
    {
     "count": 6,
     "kind": "因果推断",
     "methods": [
      "causal.did",
      "causal.psm",
      "causal.psmdid",
      "causal.rd",
      "causal.heckman",
      "causal.placebo"
     ],
     "name": "因果推断"
    },
    {
     "count": 6,
     "kind": "实验设计",
     "methods": [
      "design.factorial",
      "design.orthogonal",
      "design.uniform",
      "design.rsm",
      "design.ccd",
      "design.boxbehnken"
     ],
     "name": "实验设计"
    }
   ],
   "hint": "观察数据下的因果识别与主动实验设计。",
   "key": "causal",
   "name": "因果推断与实验设计",
   "scenarios": [
    "因果效应评估",
    "实验设计",
    "政策评估"
   ]
  },
  {
   "count": 10,
   "groups": [
    {
     "count": 4,
     "kind": "指标赋权",
     "methods": [
      "eval.pca",
      "eval.factor",
      "eval.entropy",
      "eval.critic"
     ],
     "name": "客观赋权"
    },
    {
     "count": 5,
     "kind": "决策排序",
     "methods": [
      "eval.topsis",
      "eval.vikor",
      "eval.rsr",
      "eval.fuzzy",
      "eval.grey"
     ],
     "name": "排序决策"
    },
    {
     "count": 1,
     "kind": "效率评价",
     "methods": [
      "eval.dea"
     ],
     "name": "效率评价"
    }
   ],
   "hint": "多指标融合成评价值用于排序决策。",
   "key": "evaluate",
   "name": "综合评价与决策分析",
   "scenarios": [
    "指标赋权",
    "效率评价",
    "方案排序"
   ]
  },
  {
   "count": 18,
   "groups": [
    {
     "count": 4,
     "kind": "文本分析",
     "methods": [
      "domain.wordfreq",
      "domain.tfidf",
      "domain.sentiment",
      "domain.lda"
     ],
     "name": "文本分析"
    },
    {
     "count": 4,
     "kind": "生存分析",
     "methods": [
      "domain.km",
      "domain.cox",
      "domain.nomogram",
      "domain.competing"
     ],
     "name": "生存分析"
    },
    {
     "count": 6,
     "kind": "问卷分析",
     "methods": [
      "domain.reliability",
      "domain.nps",
      "domain.kano",
      "domain.maxdiff",
      "domain.conjoint",
      "domain.psm"
     ],
     "name": "问卷与市场"
    },
    {
     "count": 3,
     "kind": "过程控制",
     "methods": [
      "domain.control",
      "domain.capability",
      "domain.weibull"
     ],
     "name": "质量控制"
    },
    {
     "count": 1,
     "kind": "Meta 分析",
     "methods": [
      "domain.meta"
     ],
     "name": "Meta 分析"
    }
   ],
   "hint": "面向特定数据类型或业务场景的方法。",
   "key": "domain",
   "name": "特定行业与场景分析",
   "scenarios": [
    "市场调研",
    "文本分析",
    "生存分析",
    "证据汇总",
    "质量控制",
    "问卷分析"
   ]
  }
 ]
} as MethodGraph


export const METHOD_GRAPH_UPDATED = {"methods": 116, "groups": 31, "categories": 9, "prerequisite": 78, "suggest": 56, "alternative": 23, "levels": 13}
