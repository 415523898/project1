import importlib

CATEGORIES = [
    ("prep", "数据准备与特征工程", "解决数据能不能用、好不好用的问题。", ("prep",)),
    ("describe", "基础统计与描述性分析", "了解数据的基本分布与整体情况。", ("describe",)),
    ("test", "差异性检验与假设检验", "判断组间差异是否具有统计显著性。", ("test",)),
    ("model", "关系与影响建模", "探究关联、因果与预测关系。", ("model",)),
    ("ml", "分类、聚类与机器学习", "无监督发现结构与有监督预测。", ("ml",)),
    ("series", "时间序列与空间计量", "处理时间先后或空间位置特征的数据。", ("series",)),
    ("causal", "因果推断与实验设计", "观察数据下的因果识别与主动实验设计。", ("causal", "design")),
    ("evaluate", "综合评价与决策分析", "多指标融合成评价值用于排序决策。", ("eval",)),
    ("domain", "特定行业与场景分析", "面向特定数据类型或业务场景的方法。", ("domain",)),
]

PREFIX_CATEGORY = {prefix: key for key, _, _, prefixes in CATEGORIES for prefix in prefixes}
CATEGORY_NAMES = {key: name for key, name, _, _ in CATEGORIES}


KINDS = (
    "数据清洗",
    "特征构造",
    "降维",
    "描述统计",
    "统计检验",
    "相关分析",
    "预测模型",
    "影响机制",
    "聚类",
    "时序建模",
    "空间建模",
    "面板建模",
    "因果推断",
    "实验设计",
    "指标赋权",
    "决策排序",
    "效率评价",
    "文本分析",
    "生存分析",
    "问卷分析",
    "过程控制",
    "Meta 分析",
)

SCENARIOS = (
    "数据清洗",
    "特征构造",
    "降维与可视化",
    "分布探索",
    "组间差异比较",
    "关联探索",
    "影响因素分析",
    "影响机制",
    "预测建模",
    "分类预测",
    "特征重要性",
    "规则提取",
    "客户分群",
    "结构发现",
    "时序预测",
    "平稳性诊断",
    "空间分析",
    "面板分析",
    "因果效应评估",
    "政策评估",
    "实验设计",
    "指标赋权",
    "方案排序",
    "效率评价",
    "文本分析",
    "生存分析",
    "问卷分析",
    "市场调研",
    "质量控制",
    "证据汇总",
)

INPUTS = (
    "数据表",
    "特征矩阵",
    "目标列",
    "分类目标",
    "连续目标",
    "分组列",
    "两分组列",
    "时间序列",
    "时间列",
    "个体列",
    "空间坐标",
    "生存时间与事件",
    "文本列",
    "多指标矩阵",
    "分类变量",
    "问卷量表",
    "因子列",
    "效应量列",
)

OUTPUTS = (
    "清洗后数据",
    "新特征",
    "降维坐标",
    "汇总表",
    "分布指标",
    "检验统计量与 p 值",
    "相关系数",
    "回归系数",
    "优势比",
    "预测值",
    "预测概率",
    "分组标签",
    "簇中心",
    "特征重要性",
    "规则集",
    "时序预测值",
    "模型诊断量",
    "因果效应估计",
    "估计量与显著性",
    "权重向量",
    "综合得分",
    "排序结果",
    "效率值",
    "主题与情感",
    "生存曲线",
    "风险比",
    "信效度指标",
    "偏好效用",
    "控制限",
    "过程能力指数",
    "可靠度曲线",
    "效应量与异质性",
    "试验方案表",
    "评价指标",
)

GROUP_KIND = {
    "数据清洗": "数据清洗",
    "特征工程": "特征构造",
    "降维": "降维",
    "时序特征": "特征构造",
    "描述统计": "描述统计",
    "功效分析": "统计检验",
    "参数检验": "统计检验",
    "非参数检验": "统计检验",
    "离散数据检验": "统计检验",
    "相关分析": "相关分析",
    "回归分析": "预测模型",
    "机制分析": "影响机制",
    "广义模型": "预测模型",
    "聚类分析": "聚类",
    "集成学习": "预测模型",
    "经典算法": "预测模型",
    "神经网络": "预测模型",
    "树模型": "预测模型",
    "时间序列": "时序建模",
    "空间计量": "空间建模",
    "面板数据": "面板建模",
    "因果推断": "因果推断",
    "实验设计": "实验设计",
    "客观赋权": "指标赋权",
    "排序决策": "决策排序",
    "效率评价": "效率评价",
    "文本分析": "文本分析",
    "生存分析": "生存分析",
    "问卷与市场": "问卷分析",
    "质量控制": "过程控制",
    "Meta 分析": "Meta 分析",
}

GROUP_SCENARIOS = {
    "数据清洗": ("数据清洗",),
    "特征工程": ("特征构造",),
    "降维": ("降维与可视化",),
    "时序特征": ("特征构造", "时序预测"),
    "描述统计": ("分布探索",),
    "功效分析": ("实验设计",),
    "参数检验": ("组间差异比较",),
    "非参数检验": ("组间差异比较",),
    "离散数据检验": ("组间差异比较", "分类预测"),
    "相关分析": ("关联探索", "影响因素分析"),
    "回归分析": ("影响因素分析", "预测建模"),
    "机制分析": ("影响机制",),
    "广义模型": ("影响因素分析", "预测建模"),
    "聚类分析": ("客户分群", "结构发现"),
    "集成学习": ("预测建模", "特征重要性"),
    "经典算法": ("预测建模",),
    "神经网络": ("预测建模",),
    "树模型": ("预测建模", "规则提取"),
    "时间序列": ("时序预测", "平稳性诊断"),
    "空间计量": ("空间分析",),
    "面板数据": ("面板分析",),
    "因果推断": ("因果效应评估", "政策评估"),
    "实验设计": ("实验设计",),
    "客观赋权": ("指标赋权",),
    "排序决策": ("方案排序", "指标赋权"),
    "效率评价": ("效率评价",),
    "文本分析": ("文本分析",),
    "生存分析": ("生存分析",),
    "问卷与市场": ("问卷分析", "市场调研"),
    "质量控制": ("质量控制",),
    "Meta 分析": ("证据汇总",),
}

GROUP_INPUTS = {
    "数据清洗": ("数据表",),
    "特征工程": ("数据表", "特征矩阵"),
    "降维": ("特征矩阵",),
    "时序特征": ("时间序列",),
    "描述统计": ("数据表",),
    "功效分析": ("分组列",),
    "参数检验": ("分组列", "连续目标"),
    "非参数检验": ("分组列", "连续目标"),
    "离散数据检验": ("分类变量",),
    "相关分析": ("特征矩阵",),
    "回归分析": ("特征矩阵", "目标列"),
    "机制分析": ("特征矩阵", "目标列"),
    "广义模型": ("特征矩阵", "目标列"),
    "聚类分析": ("特征矩阵",),
    "集成学习": ("特征矩阵", "目标列"),
    "经典算法": ("特征矩阵", "目标列"),
    "神经网络": ("特征矩阵", "目标列"),
    "树模型": ("特征矩阵", "目标列"),
    "时间序列": ("时间序列",),
    "空间计量": ("空间坐标", "特征矩阵"),
    "面板数据": ("个体列", "时间列", "特征矩阵"),
    "因果推断": ("分组列", "目标列"),
    "实验设计": ("因子列",),
    "客观赋权": ("多指标矩阵",),
    "排序决策": ("多指标矩阵",),
    "效率评价": ("多指标矩阵",),
    "文本分析": ("文本列",),
    "生存分析": ("生存时间与事件", "特征矩阵"),
    "问卷与市场": ("问卷量表",),
    "质量控制": ("连续目标",),
    "Meta 分析": ("效应量列",),
}

METHOD_INPUTS = {
    "prep.balance": ("分类目标",),
    "prep.pca": ("特征矩阵",),
    "prep.tsne": ("特征矩阵",),
    "prep.spectral": ("时间序列",),
    "describe.crosstab": ("分类变量",),
    "describe.frequency": ("分类变量",),
    "describe.aggregate": ("分组列",),
    "test.ttest": ("两分组列", "连续目标"),
    "test.wilcoxon": ("两分组列", "连续目标"),
    "test.mannwhitney": ("两分组列", "连续目标"),
    "test.friedman": ("分组列",),
    "test.cochran": ("分组列",),
    "model.logistic": ("特征矩阵", "分类目标"),
    "model.probit": ("特征矩阵", "分类目标"),
    "model.poisson": ("特征矩阵", "目标列"),
    "model.gamma": ("特征矩阵", "目标列"),
    "model.gee": ("个体列", "特征矩阵", "目标列"),
    "model.glmm": ("个体列", "特征矩阵", "目标列"),
    "model.mixed": ("个体列", "时间列", "特征矩阵", "目标列"),
    "model.mediation": ("特征矩阵", "目标列"),
    "model.moderation": ("特征矩阵", "目标列"),
    "ml.lda_qda": ("特征矩阵", "分类目标"),
    "series.moran": ("空间坐标", "目标列"),
    "series.panel": ("个体列", "时间列", "特征矩阵", "目标列"),
    "series.threshold": ("特征矩阵", "目标列"),
    "series.tobit": ("特征矩阵", "目标列"),
    "series.quantile": ("特征矩阵", "目标列"),
    "causal.did": ("分组列", "两分组列", "目标列"),
    "causal.psm": ("特征矩阵", "两分组列", "目标列"),
    "causal.psmdid": ("特征矩阵", "两分组列", "目标列"),
    "causal.rd": ("特征矩阵", "目标列"),
    "causal.heckman": ("特征矩阵", "两分组列", "目标列"),
    "causal.placebo": ("两分组列", "目标列"),
    "design.factorial": ("因子列", "目标列"),
    "design.orthogonal": ("因子列",),
    "design.uniform": ("因子列",),
    "design.rsm": ("因子列", "目标列"),
    "design.ccd": ("因子列",),
    "design.boxbehnken": ("因子列",),
    "domain.km": ("生存时间与事件",),
    "domain.cox": ("生存时间与事件", "特征矩阵"),
    "domain.nomogram": ("生存时间与事件", "特征矩阵"),
    "domain.competing": ("生存时间与事件",),
    "domain.weibull": ("生存时间与事件",),
    "domain.reliability": ("问卷量表",),
    "domain.nps": ("连续目标",),
    "domain.kano": ("问卷量表",),
    "domain.maxdiff": ("多指标矩阵",),
    "domain.conjoint": ("因子列", "目标列"),
    "domain.psm": ("连续目标",),
    "domain.control": ("连续目标", "时间列"),
    "domain.capability": ("连续目标",),
    "domain.meta": ("效应量列",),
    "domain.wordfreq": ("文本列",),
    "domain.tfidf": ("文本列",),
    "domain.sentiment": ("文本列",),
    "domain.lda": ("文本列",),
    "eval.dea": ("多指标矩阵",),
    "eval.factor": ("多指标矩阵",),
}

METHOD_BEFORE = {
    "prep.pca": ("model.correlation",),
    "model.correlation": ("describe.stats",),
    "test.ttest": ("describe.stats",),
    "test.anova": ("describe.stats", "test.ttest"),
    "describe.power": ("test.ttest", "test.anova"),
    "test.chi2": ("describe.crosstab",),
    "test.fisher": ("describe.crosstab",),
    "test.gof": ("describe.frequency",),
    "test.wilcoxon": ("describe.stats",),
    "test.mannwhitney": ("describe.stats",),
    "test.kruskal": ("describe.stats",),
    "test.friedman": ("describe.stats",),
    "test.cochran": ("describe.crosstab",),
    "model.linear": ("model.correlation",),
    "model.logistic": ("model.linear",),
    "model.probit": ("model.linear",),
    "model.poisson": ("model.linear",),
    "model.gamma": ("model.linear",),
    "model.ridge": ("model.linear",),
    "model.lasso": ("model.linear",),
    "model.elasticnet": ("model.ridge", "model.lasso"),
    "model.robust": ("model.linear",),
    "model.vif": ("model.correlation",),
    "model.canonical": ("model.correlation",),
    "model.mediation": ("model.linear",),
    "model.moderation": ("model.linear",),
    "model.chained": ("model.mediation",),
    "model.gee": ("model.linear",),
    "model.glmm": ("model.logistic",),
    "model.mixed": ("model.linear",),
    "ml.fcm": ("ml.kmeans",),
    "ml.lda_qda": ("model.correlation",),
    "ml.random_forest": ("ml.trees",),
    "ml.adaboost": ("ml.trees",),
    "ml.gbdt": ("ml.trees",),
    "ml.xgboost": ("ml.trees",),
    "ml.lightgbm": ("ml.trees",),
    "series.arima": ("series.adf",),
    "series.sarima": ("series.arima",),
    "series.garch": ("describe.stats",),
    "series.var": ("series.adf",),
    "series.coint": ("series.adf",),
    "series.granger": ("series.adf",),
    "series.moran": ("describe.stats",),
    "series.spatial": ("series.moran",),
    "series.panel": ("model.linear",),
    "series.threshold": ("model.linear",),
    "series.tobit": ("model.linear",),
    "series.quantile": ("model.linear",),
    "causal.did": ("model.linear",),
    "causal.psm": ("model.logistic",),
    "causal.psmdid": ("causal.psm", "causal.did"),
    "causal.rd": ("model.linear",),
    "causal.heckman": ("model.probit",),
    "causal.placebo": ("causal.did",),
    "design.factorial": ("test.anova",),
    "design.orthogonal": ("design.factorial",),
    "design.uniform": ("design.factorial",),
    "design.ccd": ("design.factorial",),
    "design.boxbehnken": ("design.factorial",),
    "design.rsm": ("design.factorial",),
    "eval.pca": ("prep.pca",),
    "eval.factor": ("model.correlation",),
    "domain.cox": ("describe.stats",),
    "domain.nomogram": ("domain.cox",),
    "domain.competing": ("describe.stats",),
    "domain.wordfreq": ("describe.frequency",),
    "domain.tfidf": ("domain.wordfreq",),
    "domain.lda": ("domain.wordfreq",),
    "domain.sentiment": ("domain.wordfreq",),
    "domain.kano": ("describe.frequency",),
    "domain.control": ("describe.stats",),
    "domain.capability": ("domain.control",),
    "domain.meta": ("describe.stats",),
}

METHOD_SUGGESTS = {
    "prep.pca": ("prep.scale",),
    "prep.tsne": ("prep.scale",),
    "ml.kmeans": ("prep.scale",),
    "ml.hierarchical": ("prep.scale",),
    "ml.svm": ("prep.scale",),
    "ml.knn": ("prep.scale",),
    "ml.mlp": ("prep.scale",),
    "ml.rbf": ("prep.scale",),
    "ml.lda_qda": ("prep.scale",),
    "model.ridge": ("prep.scale", "model.vif"),
    "model.lasso": ("prep.scale", "model.vif"),
    "model.elasticnet": ("prep.scale",),
    "series.garch": ("series.arima",),
    "series.moran": ("model.correlation",),
    "design.uniform": ("design.orthogonal",),
    "design.rsm": ("design.ccd", "design.boxbehnken"),
    "eval.topsis": ("eval.entropy",),
    "eval.vikor": ("eval.entropy",),
    "eval.rsr": ("eval.entropy",),
    "eval.fuzzy": ("eval.entropy",),
    "eval.factor": ("prep.pca",),
    "domain.cox": ("domain.km",),
    "domain.competing": ("domain.km",),
    "domain.lda": ("domain.tfidf",),
    "domain.meta": ("model.linear",),
    "prep.encoding": ("prep.missing",),
    "prep.missing": ("prep.duplicates",),
    "series.sarima": ("prep.spectral",),
    "prep.derive": ("prep.missing",),
    "prep.winsorize": ("prep.outliers",),
    "prep.transform": ("prep.outliers",),
    "prep.balance": ("prep.missing",),
    "prep.scale": ("prep.missing",),
    "describe.explore": ("describe.stats",),
    "describe.aggregate": ("describe.stats",),
    "describe.crosstab": ("describe.frequency",),
    "test.cochran": ("test.friedman",),
    "ml.nb": ("describe.stats",),
    "ml.trees": ("describe.stats",),
    "ml.dbscan": ("prep.scale", "ml.kmeans"),
    "series.adf": ("describe.stats",),
    "series.panel": ("series.arima",),
    "causal.did": ("describe.crosstab",),
    "eval.dea": ("eval.entropy",),
    "eval.grey": ("describe.stats",),
    "domain.km": ("describe.stats",),
    "domain.weibull": ("describe.stats",),
    "domain.reliability": ("describe.stats",),
    "domain.conjoint": ("describe.stats",),
    "domain.maxdiff": ("describe.stats",),
    "domain.nps": ("describe.frequency",),
    "domain.psm": ("describe.stats",),
}

SIMILAR = (
    (
        "model.logistic",
        "model.probit",
        "同为二元响应回归，分别使用 Logit 与 Probit 链接；需结合模型假设和验证表现选择。",
    ),
    (
        "model.logistic",
        "ml.lda_qda",
        "同一分类任务可比较两者；判别分析对类内分布与协方差有假设，不能在任意数据上直接互换。",
    ),
    (
        "eval.pca",
        "eval.factor",
        "多指标综合评价的两种建模方式：PCA 分解总方差，因子分析建模共同协变及潜在结构。",
    ),
    (
        "test.chi2",
        "test.fisher",
        "在同一 2×2 计数表上可检验独立性：卡方使用渐近近似，稀疏或小样本可考虑 Fisher 精确检验。",
    ),
    (
        "test.anova",
        "test.friedman",
        "仅在重复测量或配组设计下比较：重复测量 ANOVA 与 Friedman 的假设及检验目标不同，独立组 ANOVA 不可直接换成 Friedman。",
    ),
    (
        "model.ridge",
        "model.lasso",
        "都在线性回归上加正则：岭回归保留全部变量只压小系数，Lasso 会把系数压到 0 做特征选择。",
    ),
    (
        "series.gm11",
        "series.arima",
        "都要拟合趋势做外推：ARIMA 要求序列平稳或差分平稳、样本量足够，"
        "灰色预测适合小样本、近似指数增长的数据。",
    ),
    (
        "ml.random_forest",
        "ml.xgboost",
        "同一个预测任务选一个强模型：随机森林走 Bagging，XGBoost 走 Boosting。",
    ),
    (
        "ml.random_forest",
        "ml.lightgbm",
        "同一预测任务可比较袋装树与梯度提升树，结合数据规模、资源限制及验证表现选择。",
    ),
    (
        "ml.xgboost",
        "ml.lightgbm",
        "同为梯度提升的工程实现；速度和精度取决于数据、参数及训练条件，没有固定的优劣保证。",
    ),
    ("ml.gbdt", "ml.adaboost", "两种提升思路：GBDT 拟合负梯度，AdaBoost 提高错分样本权重。"),
    (
        "ml.kmeans",
        "ml.hierarchical",
        "都可做距离分群：K-Means 先给定 k，层次聚类可以结合树状图选择切分层级。",
    ),
    ("ml.dbscan", "ml.hierarchical", "都靠距离结构分群，样本有噪声点时 DBSCAN 更合适。"),
    (
        "prep.pca",
        "prep.tsne",
        "用于低维可视化时可比较两者：PCA 保留总体方差，t-SNE 侧重局部邻域；后者不能作为一般下游建模的等价替换。",
    ),
    (
        "test.ttest",
        "test.mannwhitney",
        "两组独立样本可比较：T 检验针对均值，方差不齐可用 Welch；Mann–Whitney 针对分布差异，额外条件下才可解释位置差异。",
    ),
    (
        "test.ttest",
        "test.wilcoxon",
        "配对比较可选择配对 T 或 Wilcoxon 符号秩检验；后者检验差值分布是否关于零对称，不能只因偏态就直接替换。",
    ),
    (
        "test.anova",
        "test.kruskal",
        "仅限多个独立组的比较：ANOVA 针对均值，Kruskal–Wallis 使用秩；将后者解释为位置差异需结合分布形状，不能直接替换重复测量 ANOVA。",
    ),
    (
        "eval.topsis",
        "eval.vikor",
        "都与理想解比较：TOPSIS 看整体距离，VIKOR 还会单独看最差的那项指标。",
    ),
    ("eval.topsis", "eval.rsr", "排序思路不同：TOPSIS 算贴近度，RSR 用秩次换算出分档。"),
    ("eval.vikor", "eval.rsr", "同一组方案可以两种方法各排一次，看结论是否一致。"),
    (
        "eval.entropy",
        "eval.critic",
        "赋权依据不同：熵值法看指标的信息量，CRITIC 看对比强度与指标间冲突性。",
    ),
    (
        "design.ccd",
        "design.boxbehnken",
        "拟合二次响应面的两种设计：CCD 含轴点，Box–Behnken 避开全因素同时处于极端水平；试验数取决于因素数和中心点配置。",
    ),
    (
        "domain.cox",
        "domain.weibull",
        "生存模型两条路：Cox 半参数不指定分布，Weibull 假定分布形状后可外推。",
    ),
)

WHEN = {
    "prep.outliers": "个别点明显偏离其余样本、又确认不是录入错误时。",
    "prep.missing": "表格里有空缺，而且不能直接把整行丢掉时。",
    "prep.duplicates": "合并了多张表或采集存在重复提交，要先确认唯一性时。",
    "prep.encoding": "有分类变量要送进模型，而模型只吃数值时。",
    "prep.derive": "现成字段不够用，需要从原始列组合出更有解释力的变量时。",
    "prep.winsorize": "想保留极端值的存在、但不让它主导结果时。",
    "prep.transform": "变量明显右偏、方差随均值增大，想让分布接近正态时。",
    "prep.balance": "分类样本严重不平衡，模型只会预测多数类时。",
    "prep.scale": "变量量纲相差很大，而方法依赖距离或梯度时。",
    "prep.tsne": "只想看看高维数据能不能分成几团，不打算用降维结果建模时。",
    "prep.pca": "变量多且高度相关，想压成少数几个综合维度再往下做时。",
    "prep.spectral": "拿到的是长时间序列，想用频域特征描述它的周期结构时。",
    "describe.frequency": "想先知道每个分类变量有哪些取值、各占多少时。",
    "describe.stats": "拿到一份新数据，第一件事是看集中趋势、离散程度和分布形状时。",
    "describe.crosstab": "两个分类变量放在一起，想看清交叉分布时。",
    "describe.aggregate": "想按某个分组变量分组求均值、求和或计数时。",
    "describe.explore": "想一次扫完缺失、类型、唯一值和分布概览时。",
    "describe.power": "实验开始之前，想算清楚最少要收多少样本时。",
    "test.ttest": "比较两组均值有没有差异，且样本近似正态时。",
    "test.anova": "比较三组及以上均值，或要看因素之间的交互作用时。",
    "test.wilcoxon": "配对或重复测量数据，差值明显偏态时。",
    "test.mannwhitney": "两组独立样本，正态性或方差齐性不成立时。",
    "test.kruskal": "三组及以上独立样本，不满足方差分析前提时。",
    "test.friedman": "同一批对象在多个条件下重复测量，要做非参数比较时。",
    "test.cochran": "同一批对象的二值响应在三个以上时点重复测量时。",
    "test.chi2": "想知道两个分类变量是否相互独立时。",
    "test.gof": "想检验观测频数是否符合某个理论分布或比例时。",
    "test.fisher": "2×2 列联表里出现期望频数小于 5 的小样本时。",
    "model.correlation": "想先判断哪些连续变量之间存在线性关联时。",
    "model.canonical": "一组自变量与一组因变量之间整体上怎么相关时。",
    "model.vif": "回归之前想确认自变量之间有没有严重共线性时。",
    "model.linear": "因变量连续，想量化各自变量的影响方向与大小并做预测时。",
    "model.ridge": "自变量共线性强、样本数少于变量数，需要让系数稳定下来时。",
    "model.lasso": "变量很多，想让模型自动把没用的系数压到 0 时。",
    "model.elasticnet": "变量成组相关，Lasso 只留一个、岭回归一个都不删时。",
    "model.logistic": "因变量是二分类（或有序、多分类），要解释优势比时。",
    "model.probit": "二分类问题，但理论设定是正态潜变量时。",
    "model.robust": "数据有异方差或离群点，想确认结论没被个别点带偏时。",
    "model.mediation": "想说明「A 通过中间变量 M 影响 B」的作用路径时。",
    "model.moderation": "想说明「A 对 B 的影响在什么条件下更强或更弱」时。",
    "model.chained": "影响要经过两个以上中介环节串联传递时。",
    "model.gamma": "因变量是正的连续量（时长、金额），且方差随均值增大时。",
    "model.poisson": "因变量是计数（次数、件数、人数）时。",
    "model.gee": "数据按个体或班级聚类，只关心总体平均效应时。",
    "model.glmm": "聚类数据、因变量非正态，还想要随机效应时。",
    "model.mixed": "有嵌套或重复测量结构，需要随机截距、随机斜率时。",
    "ml.kmeans": "想按数值特征把样本分成 k 组，且各组大致呈球形时。",
    "ml.hierarchical": "事先不知道分几类，想用树状图看层次结构时。",
    "ml.dbscan": "分群形状不规则，而且希望把噪声点单独剔出来时。",
    "ml.fcm": "边界样本不该被硬性归到某一类，需要隶属度时。",
    "ml.random_forest": "表格数据要一个稳、少调参的强基线预测模型时。",
    "ml.xgboost": "追求预测精度，也愿意花时间调参时。",
    "ml.lightgbm": "样本量大、特征维度高，训练速度成为瓶颈时。",
    "ml.adaboost": "想用一批简单弱学习器逐步加权组合出一个强模型时。",
    "ml.gbdt": "想理解梯度提升到底在拟合什么时。",
    "ml.svm": "样本量中等、维度高，类别边界比较清晰时。",
    "ml.knn": "需要没有训练过程的直观基线，或做小规模分类回归时。",
    "ml.nb": "文本或高维稀疏特征的快速基线分类时。",
    "ml.mlp": "变量之间的关系明显非线性，且数据量足够时。",
    "ml.rbf": "需要局部响应的浅层网络，而训练样本不太多时。",
    "ml.trees": "想要可读的 if-then 规则和特征重要性时。",
    "ml.lda_qda": "分类任务，同时想得到判别边界和降维结果时。",
    "series.arima": "单变量序列（差分后）平稳，要做短期预测时。",
    "series.sarima": "序列有稳定的季节周期，比如月度、季度数据时。",
    "series.garch": "关心的不是水平而是波动率，比如金融收益率时。",
    "series.var": "多个时间序列相互影响，要看脉冲响应时。",
    "series.adf": "建模之前必须确认序列平稳，否则会做出伪回归时。",
    "series.coint": "多个非平稳序列之间存在长期均衡关系时。",
    "series.granger": "想判断一个序列是否有助于预测另一个序列时。",
    "series.gm11": "样本极少（四五个点以上）且近似指数增长时。",
    "series.moran": "想知道空间上是否聚集，近处是相似还是相反时。",
    "series.spatial": "空间自相关显著，回归必须带上空间权重时。",
    "series.panel": "同时有多个个体和多个时期的面板数据时。",
    "series.threshold": "影响关系可能在某个门槛值前后发生改变时。",
    "series.tobit": "因变量被截断或删失，比如低于检测限一律记为 0 时。",
    "series.quantile": "关心的不是平均水平，而是高分段、低分段各自的影响因素时。",
    "causal.did": "有处理组和对照组，而且都有政策前后的两期数据时。",
    "causal.psm": "处理组与对照组基线差异大，想先配对出可比样本时。",
    "causal.psmdid": "既想缓解选择偏误、又要做前后对比时。",
    "causal.rd": "处理只发生在某个阈值两侧，比如分数线、年龄线时。",
    "causal.heckman": "样本经过自选择，只观测到愿意参与的那部分人时。",
    "causal.placebo": "做完 DID 之后，想验证结论不是趋势巧合时。",
    "design.factorial": "想同时看多个因素的主效应和交互效应时。",
    "design.orthogonal": "因素多、全因子试验次数根本做不完时。",
    "design.uniform": "因素水平多、正交表不够用，只想让试验点均匀散布时。",
    "design.rsm": "想找因素的最优组合，而不只是判断谁显著时。",
    "design.ccd": "响应面试验需要一个能拟合二次曲面、还能外推的设计时。",
    "design.boxbehnken": "因素水平数不多，又不想做角点试验时。",
    "eval.pca": "多指标评价，想让方差大的指标自动占更大权重时。",
    "eval.factor": "指标背后存在潜在维度，想要因子得分和结构解释时。",
    "eval.entropy": "不想靠专家打分，纯用数据离散程度定权重时。",
    "eval.critic": "各指标对比强度差异大，或指标之间相关性强时。",
    "eval.topsis": "已经有权重，想按与理想解的距离给方案排序时。",
    "eval.vikor": "除了整体排序，还想避免某一项指标特别差的方案时。",
    "eval.rsr": "指标多、量纲杂，想用秩次换算出分档结果时。",
    "eval.dea": "有多种投入和产出，想比较各决策单元的效率时。",
    "eval.fuzzy": "评价里带有「较好、一般」这类模糊说法时。",
    "eval.grey": "样本量小、信息不完全，想用参考序列做关联排序时。",
    "domain.wordfreq": "想先看文本里哪些词出现得最多时。",
    "domain.tfidf": "想找出能区分文档的关键词，而不是通用高频词时。",
    "domain.sentiment": "想给评论、弹幕、访谈批量打正负面标签时。",
    "domain.lda": "文档主题未知，想让模型自己归出主题时。",
    "domain.km": "有随访时间和是否发生事件，想先画生存曲线时。",
    "domain.cox": "想看多个因素对生存风险的影响，要解释风险比时。",
    "domain.nomogram": "想把 Cox 模型做成一张能手工打分的预测图时。",
    "domain.competing": "终点事件不止一种，比如死于该病与死于其他病时。",
    "domain.reliability": "有问卷量表，想先确认信度和效度时。",
    "domain.nps": "只有一道「0 到 10 分推荐意愿」的题时。",
    "domain.kano": "想区分「必须有」「越多越好」「可有可无」的需求时。",
    "domain.maxdiff": "选项多、被访者习惯全打高分，需要强制取舍时。",
    "domain.conjoint": "产品由多个属性组合而成，想知道各属性的效用时。",
    "domain.psm": "想知道价格定在哪一段用户还愿意接受时。",
    "domain.control": "生产过程有连续监测数据，要判断过程是否受控时。",
    "domain.capability": "过程稳定之后，想知道它能不能满足规格要求时。",
    "domain.weibull": "关心失效时间的分布和可靠度曲线时。",
    "domain.meta": "同一个问题已有多篇研究，想把效应量合并时。",
}

EDGE_WHY = {
    (
        "describe.stats",
        "model.correlation",
    ): "先理解均值、变异和分布，才能解释相关系数及异常值对相关性的影响。",
    (
        "model.correlation",
        "prep.pca",
    ): "PCA 从协方差或相关结构提取主要变化方向，先理解变量间共同变化。",
    (
        "model.correlation",
        "eval.factor",
    ): "因子分析建模共同协变和潜在结构，不是先运行 PCA 评价再加一层；先理解相关矩阵。",
    (
        "model.correlation",
        "ml.lda_qda",
    ): "判别分析比较类均值与协方差结构，先理解变量间相关及类内变异。",
    (
        "domain.wordfreq",
        "domain.lda",
    ): "本项目 LDA 主题模型使用词频矩阵；先理解文档中的计数表示，不要求先使用 TF-IDF。",
    (
        "domain.tfidf",
        "domain.lda",
    ): "比较计数与 TF-IDF 的表示差异有助理解主题模型输入；通常应给 LDA 词频计数。",
    (
        "describe.stats",
        "domain.meta",
    ): "常规 Meta 分析合并效应量和方差，需理解估计与不确定性，不以线性回归为运行前提。",
    (
        "model.linear",
        "domain.meta",
    ): "回归知识有助理解扩展的元回归，但本次常规效应量合并不要求先做线性回归。",
    ("describe.stats", "series.moran"): "Moran's I 使用围绕均值的偏差及方差刻画空间关联。",
    (
        "model.correlation",
        "series.moran",
    ): "先比较普通相关与空间自相关；单变量 Moran's I 不要求先对变量进行标准化。",
    ("model.vif", "model.ridge"): "VIF 可辅助识别共线性，但岭回归可以直接拟合，不要求先计算 VIF。",
    (
        "model.vif",
        "model.lasso",
    ): "VIF 可辅助理解共线性与变量选择，但 Lasso 不要求先运行共线性诊断。",
    (
        "eval.entropy",
        "eval.topsis",
    ): "TOPSIS 可用等权、熵权、CRITIC 或自定义权重；熵值法是可选赋权来源。",
    ("eval.entropy", "eval.vikor"): "VIKOR 需要选定权重，熵值法只是本项目支持的赋权选项之一。",
    (
        "eval.entropy",
        "eval.rsr",
    ): "加权 RSR 可采用熵权，也可以使用等权或其他权重，不要求先做熵值法。",
    ("eval.entropy", "eval.fuzzy"): "模糊综合评价可使用不同来源的权重，熵值法是可选准备知识。",
    ("design.ccd", "design.rsm"): "CCD 是响应面常见布点方案之一，也可选择 Box–Behnken 等设计。",
    (
        "design.boxbehnken",
        "design.rsm",
    ): "Box–Behnken 是响应面布点的可选方案，需结合因素数和可行试验区域选择。",
    (
        "prep.pca",
        "eval.factor",
    ): "对照 PCA 的方差分解与因子分析的共同协变模型，帮助理解两种提取思路。",
    (
        "prep.scale",
        "prep.pca",
    ): "不同量纲可能让大方差变量主导 PCA；是否标准化需结合变量单位和分析目的，并非固定必做步骤。",
    ("prep.scale", "prep.tsne"): "t-SNE 按距离算相似度，量纲不统一会直接扭曲邻域结构。",
    ("describe.stats", "test.ttest"): "t 统计量就是均值差除以标准误，先懂这两个量才看得懂输出。",
    ("describe.crosstab", "test.chi2"): "卡方检验的输入就是列联表，先会读交叉频数与百分比。",
    ("describe.crosstab", "test.fisher"): "精确检验算的还是 2×2 列联表的概率。",
    ("describe.frequency", "test.gof"): "拟合优度比较的是观测频数与理论频数。",
    ("model.correlation", "model.linear"): "回归系数与相关系数同源，先看相关再谈影响大小。",
    ("model.linear", "model.logistic"): "Logistic 就是把线性预测值压进 0–1 的链接函数。",
    ("model.linear", "model.ridge"): "岭回归只是在线性回归的损失上加了一项 L2 惩罚。",
    ("model.ridge", "model.elasticnet"): "弹性网是岭回归与 Lasso 的凸组合，两项都要先看懂。",
    ("ml.trees", "ml.random_forest"): "随机森林是很多棵决策树的 Bagging 集成，先懂单棵树怎么分裂。",
    ("ml.trees", "ml.gbdt"): "梯度提升里每棵新树拟合的是上一轮的负梯度。",
    ("ml.kmeans", "ml.fcm"): "模糊 C 均值把 K-Means 的硬归属换成了隶属度。",
    (
        "series.adf",
        "series.arima",
    ): "单位根检验辅助选择差分候选阶数；还需结合序列图形、模型诊断和验证，不能由一次检验唯一决定。",
    ("series.adf", "series.coint"): "协整检验建立在同阶单整之上，先做单位根检验。",
    ("series.arima", "series.sarima"): "季节性 ARIMA 在 ARIMA 上多加了一层季节项。",
    (
        "series.moran",
        "series.spatial",
    ): "Moran's I 辅助诊断空间关联；空间权重由邻接或距离等规则设定，是否采用空间回归还需模型诊断。",
    (
        "domain.km",
        "domain.cox",
    ): "先读生存曲线有助理解时间与删失；Cox 可直接拟合，不要求先运行 Kaplan–Meier。",
    (
        "domain.km",
        "domain.competing",
    ): "先理解删失与生存曲线；竞争事件应使用对应的累计发生函数，不能直接用一减 KM 代替。",
    ("domain.cox", "domain.nomogram"): "列线图把 Cox 的回归系数换算成个体得分。",
    ("domain.control", "domain.capability"): "先用控制图确认过程稳定，过程能力指数才有意义。",
    ("design.factorial", "design.ccd"): "中心复合设计是全因子设计加上星点与中心点。",
    ("prep.pca", "eval.pca"): "主成分分析评价直接把 PCA 的方差贡献率当成权重。",
    ("causal.psm", "causal.psmdid"): "PSM-DID 先用 PSM 匹配样本，再在匹配样本上做 DID。",
    ("prep.missing", "prep.encoding"): "缺失值没处理完，编码出来的类别会有空洞。",
    ("prep.missing", "prep.balance"): "先补齐再重采样，否则少数类的合成样本会失真。",
    ("ml.kmeans", "ml.dbscan"): "先掌握一种划分式聚类，再理解基于密度的思路。",
}

GROUP_OUTPUTS = {
    "数据清洗": ("清洗后数据",),
    "特征工程": ("新特征",),
    "降维": ("降维坐标",),
    "时序特征": ("新特征",),
    "描述统计": ("汇总表", "分布指标"),
    "功效分析": ("评价指标",),
    "参数检验": ("检验统计量与 p 值",),
    "非参数检验": ("检验统计量与 p 值",),
    "离散数据检验": ("检验统计量与 p 值",),
    "相关分析": ("相关系数",),
    "回归分析": ("回归系数", "模型诊断量"),
    "机制分析": ("因果效应估计", "估计量与显著性"),
    "广义模型": ("回归系数", "模型诊断量"),
    "聚类分析": ("分组标签", "簇中心"),
    "集成学习": ("预测值", "特征重要性", "评价指标"),
    "经典算法": ("预测值", "评价指标"),
    "神经网络": ("预测值", "评价指标"),
    "树模型": ("规则集", "特征重要性"),
    "时间序列": ("时序预测值", "模型诊断量"),
    "空间计量": ("估计量与显著性",),
    "面板数据": ("估计量与显著性", "模型诊断量"),
    "因果推断": ("因果效应估计", "估计量与显著性"),
    "实验设计": ("试验方案表",),
    "客观赋权": ("权重向量",),
    "排序决策": ("综合得分", "排序结果"),
    "效率评价": ("效率值",),
    "文本分析": ("主题与情感",),
    "生存分析": ("生存曲线", "风险比"),
    "问卷与市场": ("偏好效用", "排序结果"),
    "质量控制": ("控制限", "过程能力指数"),
    "Meta 分析": ("效应量与异质性",),
}

METHOD_OUTPUTS = {
    "prep.balance": ("清洗后数据",),
    "prep.spectral": ("新特征",),
    "describe.frequency": ("汇总表",),
    "describe.stats": ("汇总表", "分布指标"),
    "describe.crosstab": ("汇总表",),
    "describe.aggregate": ("汇总表",),
    "describe.explore": ("汇总表", "分布指标"),
    "describe.power": ("评价指标",),
    "test.gof": ("检验统计量与 p 值",),
    "model.logistic": ("回归系数", "优势比", "预测概率"),
    "model.probit": ("回归系数", "预测概率"),
    "model.poisson": ("回归系数", "模型诊断量"),
    "model.gamma": ("回归系数", "模型诊断量"),
    "model.canonical": ("相关系数", "估计量与显著性"),
    "model.correlation": ("相关系数",),
    "model.vif": ("模型诊断量",),
    "ml.kmeans": ("分组标签", "簇中心", "评价指标"),
    "ml.hierarchical": ("分组标签",),
    "ml.dbscan": ("分组标签",),
    "ml.fcm": ("分组标签", "簇中心"),
    "ml.lda_qda": ("分组标签", "回归系数", "评价指标"),
    "series.adf": ("检验统计量与 p 值", "模型诊断量"),
    "series.arima": ("时序预测值", "模型诊断量"),
    "series.sarima": ("时序预测值", "模型诊断量"),
    "series.garch": ("时序预测值", "模型诊断量"),
    "series.var": ("时序预测值", "回归系数"),
    "series.gm11": ("时序预测值", "评价指标"),
    "series.coint": ("检验统计量与 p 值",),
    "series.granger": ("检验统计量与 p 值",),
    "series.moran": ("检验统计量与 p 值", "分组标签"),
    "series.panel": ("估计量与显著性", "模型诊断量"),
    "series.threshold": ("估计量与显著性",),
    "series.tobit": ("回归系数", "模型诊断量"),
    "series.quantile": ("回归系数", "估计量与显著性"),
    "causal.did": ("因果效应估计", "估计量与显著性"),
    "causal.psm": ("因果效应估计", "汇总表"),
    "causal.psmdid": ("因果效应估计", "估计量与显著性"),
    "causal.rd": ("因果效应估计", "估计量与显著性"),
    "causal.heckman": ("回归系数", "估计量与显著性"),
    "causal.placebo": ("因果效应估计", "检验统计量与 p 值"),
    "design.orthogonal": ("试验方案表",),
    "design.uniform": ("试验方案表",),
    "design.ccd": ("试验方案表",),
    "design.boxbehnken": ("试验方案表",),
    "design.factorial": ("估计量与显著性", "试验方案表"),
    "design.rsm": ("回归系数", "排序结果"),
    "eval.entropy": ("权重向量",),
    "eval.critic": ("权重向量",),
    "eval.topsis": ("综合得分", "排序结果"),
    "eval.vikor": ("综合得分", "排序结果"),
    "eval.rsr": ("排序结果", "综合得分"),
    "eval.dea": ("效率值",),
    "eval.fuzzy": ("综合得分", "排序结果"),
    "eval.grey": ("相关系数", "排序结果"),
    "eval.pca": ("权重向量", "综合得分"),
    "eval.factor": ("权重向量", "综合得分"),
    "domain.wordfreq": ("汇总表",),
    "domain.tfidf": ("汇总表",),
    "domain.sentiment": ("主题与情感", "汇总表"),
    "domain.lda": ("主题与情感", "评价指标"),
    "domain.km": ("生存曲线", "估计量与显著性"),
    "domain.cox": ("风险比", "估计量与显著性"),
    "domain.nomogram": ("风险比", "排序结果"),
    "domain.competing": ("生存曲线",),
    "domain.weibull": ("可靠度曲线", "估计量与显著性"),
    "domain.reliability": ("信效度指标",),
    "domain.nps": ("汇总表", "评价指标"),
    "domain.kano": ("汇总表", "排序结果"),
    "domain.maxdiff": ("偏好效用", "排序结果"),
    "domain.conjoint": ("偏好效用", "估计量与显著性"),
    "domain.psm": ("排序结果",),
    "domain.control": ("控制限", "汇总表"),
    "domain.capability": ("过程能力指数",),
    "domain.meta": ("效应量与异质性", "估计量与显著性"),
}


def category_of(method_id):
    return PREFIX_CATEGORY.get(str(method_id).split(".")[0])


CATALOG = [
    dict(
        id="prep.outliers",
        label="异常值处理",
        group="数据清洗",
        kind="数据清洗",
        needs=None,
        tasks=("classification", "regression", "clustering"),
        scenarios=("数据清洗",),
        inputs=("数据表",),
        outputs=("清洗后数据",),
        note="IQR / Z 分数识别并按截断或缩尾处理。",
    ),
    dict(
        id="prep.missing",
        label="缺失值处理",
        group="数据清洗",
        kind="数据清洗",
        needs=None,
        tasks=("classification", "regression", "clustering"),
        scenarios=("数据清洗",),
        inputs=("数据表",),
        outputs=("清洗后数据",),
        note="均值/中位数/众数填充、KNN 填充、迭代回归填充。",
    ),
    dict(
        id="prep.duplicates",
        label="重复值处理",
        group="数据清洗",
        kind="数据清洗",
        needs=None,
        tasks=("classification", "regression", "clustering"),
        scenarios=("数据清洗",),
        inputs=("数据表",),
        outputs=("清洗后数据",),
        note="识别并去重。",
    ),
    dict(
        id="prep.encoding",
        label="数据编码",
        group="特征工程",
        kind="特征构造",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("特征构造",),
        inputs=("数据表", "特征矩阵"),
        outputs=("新特征",),
        note="独热、序号、目标编码。",
    ),
    dict(
        id="prep.derive",
        label="生成变量",
        group="特征工程",
        kind="特征构造",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("特征构造",),
        inputs=("数据表", "特征矩阵"),
        outputs=("新特征",),
        note="比值、乘积、多项式、分箱离散化。",
    ),
    dict(
        id="prep.winsorize",
        label="缩尾处理 Winsorize",
        group="特征工程",
        kind="特征构造",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("特征构造",),
        inputs=("数据表", "特征矩阵"),
        outputs=("新特征",),
        note="按分位数压缩极端值。",
    ),
    dict(
        id="prep.transform",
        label="数据变换 Box-Cox / Yeo-Johnson",
        group="特征工程",
        kind="特征构造",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("特征构造",),
        inputs=("数据表", "特征矩阵"),
        outputs=("新特征",),
        note="稳定方差、接近正态。",
    ),
    dict(
        id="prep.balance",
        label="样本均衡",
        group="特征工程",
        kind="特征构造",
        needs=None,
        tasks=("classification",),
        scenarios=("特征构造",),
        inputs=("分类目标",),
        outputs=("清洗后数据",),
        note="类别权重、随机过采样、SMOTE、欠采样；重采样选项需要 imbalanced-learn，"
        "权重与分布报告不需要。",
    ),
    dict(
        id="prep.scale",
        label="标准化与归一化",
        group="特征工程",
        kind="特征构造",
        needs=None,
        tasks=("classification", "regression", "clustering"),
        scenarios=("特征构造",),
        inputs=("数据表", "特征矩阵"),
        outputs=("新特征",),
        note="Z 分数与 Min-Max。",
    ),
    dict(
        id="prep.tsne",
        label="t-SNE 降维可视化",
        group="降维",
        kind="降维",
        needs=None,
        tasks=("classification", "regression", "clustering"),
        scenarios=("降维与可视化",),
        inputs=("特征矩阵",),
        outputs=("降维坐标",),
        note="非线性降维散点。",
    ),
    dict(
        id="prep.pca",
        label="主成分分析 PCA",
        group="降维",
        kind="降维",
        needs=None,
        tasks=("classification", "regression", "clustering"),
        scenarios=("降维与可视化",),
        inputs=("特征矩阵",),
        outputs=("降维坐标",),
        note="碎石图与载荷图。",
    ),
    dict(
        id="prep.spectral",
        label="时序谱特征",
        group="时序特征",
        kind="特征构造",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("特征构造", "时序预测"),
        inputs=("时间序列",),
        outputs=("新特征",),
        note="FFT 主频、谱熵、能量占比。",
    ),
    dict(
        id="describe.frequency",
        label="频数分析",
        group="描述统计",
        kind="描述统计",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("分布探索",),
        inputs=("分类变量",),
        outputs=("汇总表",),
        note="分类变量频数与占比。",
    ),
    dict(
        id="describe.stats",
        label="描述性统计",
        group="描述统计",
        kind="描述统计",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("分布探索",),
        inputs=("数据表",),
        outputs=("汇总表", "分布指标"),
        note="均值、标准差、分位数、偏峰度。",
    ),
    dict(
        id="describe.crosstab",
        label="列联表",
        group="描述统计",
        kind="描述统计",
        needs=None,
        tasks=("classification",),
        scenarios=("分布探索",),
        inputs=("分类变量",),
        outputs=("汇总表",),
        note="交叉频数与行列表百分比。",
    ),
    dict(
        id="describe.aggregate",
        label="分类汇总",
        group="描述统计",
        kind="描述统计",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("分布探索",),
        inputs=("分组列",),
        outputs=("汇总表",),
        note="按分组变量聚合统计。",
    ),
    dict(
        id="describe.explore",
        label="数据探索",
        group="描述统计",
        kind="描述统计",
        needs=None,
        tasks=("classification", "regression", "clustering"),
        scenarios=("分布探索",),
        inputs=("数据表",),
        outputs=("汇总表", "分布指标"),
        note="缺失、唯一值、类型、分布摘要。",
    ),
    dict(
        id="describe.power",
        label="检验功效与样本量",
        group="功效分析",
        kind="统计检验",
        needs="statsmodels",
        tasks=("classification", "regression"),
        scenarios=("实验设计",),
        inputs=("分组列",),
        outputs=("评价指标",),
        note="功效分析、最小样本量计算。",
    ),
    dict(
        id="test.ttest",
        label="T 检验（单样本/独立/配对）",
        group="参数检验",
        kind="统计检验",
        needs="scipy",
        tasks=("classification", "regression"),
        scenarios=("组间差异比较",),
        inputs=("两分组列", "连续目标"),
        outputs=("检验统计量与 p 值",),
        note="三种 T 检验与效应量。",
    ),
    dict(
        id="test.anova",
        label="方差分析（单因素 / 协方差）",
        group="参数检验",
        kind="统计检验",
        needs="statsmodels",
        tasks=("classification", "regression"),
        scenarios=("组间差异比较",),
        inputs=("分组列", "连续目标"),
        outputs=("检验统计量与 p 值",),
        note="单因素独立组 ANOVA 与含一个协变量的 ANCOVA；不提供重复测量或多因素 ANOVA。",
    ),
    dict(
        id="test.wilcoxon",
        label="Wilcoxon 符号秩检验",
        group="非参数检验",
        kind="统计检验",
        needs="scipy",
        tasks=("classification", "regression"),
        scenarios=("组间差异比较",),
        inputs=("两分组列", "连续目标"),
        outputs=("检验统计量与 p 值",),
        note="配对样本的非参数替代。",
    ),
    dict(
        id="test.mannwhitney",
        label="Mann-Whitney U 检验",
        group="非参数检验",
        kind="统计检验",
        needs="scipy",
        tasks=("classification", "regression"),
        scenarios=("组间差异比较",),
        inputs=("两分组列", "连续目标"),
        outputs=("检验统计量与 p 值",),
        note="两独立样本的非参数替代。",
    ),
    dict(
        id="test.kruskal",
        label="Kruskal-Wallis H 检验",
        group="非参数检验",
        kind="统计检验",
        needs="scipy",
        tasks=("classification", "regression"),
        scenarios=("组间差异比较",),
        inputs=("分组列", "连续目标"),
        outputs=("检验统计量与 p 值",),
        note="多组非参数替代。",
    ),
    dict(
        id="test.friedman",
        label="Friedman 检验",
        group="非参数检验",
        kind="统计检验",
        needs="scipy",
        tasks=("classification", "regression"),
        scenarios=("组间差异比较",),
        inputs=("分组列",),
        outputs=("检验统计量与 p 值",),
        note="随机区组重复测量的非参数检验。",
    ),
    dict(
        id="test.cochran",
        label="Cochran's Q 检验",
        group="非参数检验",
        kind="统计检验",
        needs="statsmodels",
        tasks=("classification",),
        scenarios=("组间差异比较",),
        inputs=("分组列",),
        outputs=("检验统计量与 p 值",),
        note="二分响应重复测量。",
    ),
    dict(
        id="test.chi2",
        label="卡方检验",
        group="离散数据检验",
        kind="统计检验",
        needs="scipy",
        tasks=("classification",),
        scenarios=("组间差异比较", "分类预测"),
        inputs=("分类变量",),
        outputs=("检验统计量与 p 值",),
        note="列联表独立性检验。",
    ),
    dict(
        id="test.gof",
        label="卡方拟合优度检验",
        group="离散数据检验",
        kind="统计检验",
        needs="scipy",
        tasks=("classification",),
        scenarios=("组间差异比较", "分类预测"),
        inputs=("分类变量",),
        outputs=("检验统计量与 p 值",),
        note="观测分布与理论分布比较。",
    ),
    dict(
        id="test.fisher",
        label="Fisher 精确检验",
        group="离散数据检验",
        kind="统计检验",
        needs="scipy",
        tasks=("classification",),
        scenarios=("组间差异比较", "分类预测"),
        inputs=("分类变量",),
        outputs=("检验统计量与 p 值",),
        note="小样本 2×2 精确检验。",
    ),
    dict(
        id="model.correlation",
        label="相关分析",
        group="相关分析",
        kind="相关分析",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("关联探索", "影响因素分析"),
        inputs=("特征矩阵",),
        outputs=("相关系数",),
        note="Pearson、Spearman、Kendall、偏相关。",
    ),
    dict(
        id="model.canonical",
        label="典型相关分析",
        group="相关分析",
        kind="相关分析",
        needs="sklearn",
        tasks=("regression",),
        scenarios=("关联探索", "影响因素分析"),
        inputs=("特征矩阵",),
        outputs=("相关系数", "估计量与显著性"),
        note="两组变量之间的相关结构。",
    ),
    dict(
        id="model.vif",
        label="VIF 共线性诊断",
        group="相关分析",
        kind="相关分析",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("关联探索", "影响因素分析"),
        inputs=("特征矩阵",),
        outputs=("模型诊断量",),
        note="方差膨胀因子与容忍度。",
    ),
    dict(
        id="model.linear",
        label="线性回归",
        group="回归分析",
        kind="预测模型",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="系数、标准误、t 值、R²。",
    ),
    dict(
        id="model.ridge",
        label="岭回归",
        group="回归分析",
        kind="预测模型",
        needs=None,
        tasks=("regression",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="L2 正则与系数路径。",
    ),
    dict(
        id="model.lasso",
        label="Lasso 回归",
        group="回归分析",
        kind="预测模型",
        needs=None,
        tasks=("regression",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="L1 正则做特征选择。",
    ),
    dict(
        id="model.elasticnet",
        label="ElasticNet",
        group="回归分析",
        kind="预测模型",
        needs=None,
        tasks=("regression",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="L1+L2 混合正则。",
    ),
    dict(
        id="model.logistic",
        label="Logistic 回归（二分类/多分类）",
        group="回归分析",
        kind="预测模型",
        needs="statsmodels",
        tasks=("classification",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("特征矩阵", "分类目标"),
        outputs=("回归系数", "优势比", "预测概率"),
        note="三种响应类型与优势比。",
    ),
    dict(
        id="model.probit",
        label="Probit 回归",
        group="回归分析",
        kind="预测模型",
        needs="statsmodels",
        tasks=("classification",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("特征矩阵", "分类目标"),
        outputs=("回归系数", "预测概率"),
        note="正态链接函数的二分类模型。",
    ),
    dict(
        id="model.robust",
        label="稳健性检验",
        group="回归分析",
        kind="预测模型",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="稳健标准误与多种设定对比。",
    ),
    dict(
        id="model.mediation",
        label="中介效应",
        group="机制分析",
        kind="影响机制",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("影响机制",),
        inputs=("特征矩阵", "目标列"),
        outputs=("因果效应估计", "估计量与显著性"),
        note="Baron-Kenny 与 Bootstrap 间接效应。",
    ),
    dict(
        id="model.moderation",
        label="调节效应",
        group="机制分析",
        kind="影响机制",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("影响机制",),
        inputs=("特征矩阵", "目标列"),
        outputs=("因果效应估计", "估计量与显著性"),
        note="交互项与简单斜率。",
    ),
    dict(
        id="model.chained",
        label="链式中介",
        group="机制分析",
        kind="影响机制",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("影响机制",),
        inputs=("特征矩阵", "目标列"),
        outputs=("因果效应估计", "估计量与显著性"),
        note="多中介串联的间接效应分解。",
    ),
    dict(
        id="model.gamma",
        label="Gamma 回归",
        group="广义模型",
        kind="预测模型",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="正连续响应的广义线性模型。",
    ),
    dict(
        id="model.poisson",
        label="泊松回归",
        group="广义模型",
        kind="预测模型",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="计数响应与发生率比。",
    ),
    dict(
        id="model.gee",
        label="GEE 广义估计方程",
        group="广义模型",
        kind="预测模型",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("个体列", "特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="聚类相关数据的总体平均模型。",
    ),
    dict(
        id="model.glmm",
        label="GLMM 广义线性混合模型",
        group="广义模型",
        kind="预测模型",
        needs="statsmodels",
        tasks=("classification", "regression"),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("个体列", "特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="Poisson/log 或 Binomial/logit 随机截距；变分贝叶斯后验估计。",
    ),
    dict(
        id="model.mixed",
        label="混合效应模型",
        group="广义模型",
        kind="预测模型",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("影响因素分析", "预测建模"),
        inputs=("个体列", "时间列", "特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="随机截距与随机斜率。",
    ),
    dict(
        id="ml.kmeans",
        label="K-Means 聚类",
        group="聚类分析",
        kind="聚类",
        needs=None,
        tasks=("clustering",),
        scenarios=("客户分群", "结构发现"),
        inputs=("特征矩阵",),
        outputs=("分组标签", "簇中心", "评价指标"),
        note="肘部法与轮廓系数。",
    ),
    dict(
        id="ml.hierarchical",
        label="分层聚类",
        group="聚类分析",
        kind="聚类",
        needs="scipy",
        tasks=("clustering",),
        scenarios=("客户分群", "结构发现"),
        inputs=("特征矩阵",),
        outputs=("分组标签",),
        note="树状图与多种连接方式。",
    ),
    dict(
        id="ml.dbscan",
        label="DBSCAN 聚类",
        group="聚类分析",
        kind="聚类",
        needs=None,
        tasks=("clustering",),
        scenarios=("客户分群", "结构发现"),
        inputs=("特征矩阵",),
        outputs=("分组标签",),
        note="密度聚类与噪声点识别。",
    ),
    dict(
        id="ml.fcm",
        label="模糊 C 均值聚类",
        group="聚类分析",
        kind="聚类",
        needs=None,
        tasks=("clustering",),
        scenarios=("客户分群", "结构发现"),
        inputs=("特征矩阵",),
        outputs=("分组标签", "簇中心"),
        note="隶属度矩阵与模糊划分系数。",
    ),
    dict(
        id="ml.random_forest",
        label="随机森林",
        group="集成学习",
        kind="预测模型",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("预测建模", "特征重要性"),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "特征重要性", "评价指标"),
        note="特征重要性与袋外误差。",
    ),
    dict(
        id="ml.xgboost",
        label="XGBoost",
        group="集成学习",
        kind="预测模型",
        needs="xgboost",
        tasks=("classification", "regression"),
        scenarios=("预测建模", "特征重要性"),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "特征重要性", "评价指标"),
        note="梯度提升与早停。",
    ),
    dict(
        id="ml.lightgbm",
        label="LightGBM",
        group="集成学习",
        kind="预测模型",
        needs="lightgbm",
        tasks=("classification", "regression"),
        scenarios=("预测建模", "特征重要性"),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "特征重要性", "评价指标"),
        note="直方图梯度提升。",
    ),
    dict(
        id="ml.adaboost",
        label="AdaBoost",
        group="集成学习",
        kind="预测模型",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("预测建模", "特征重要性"),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "特征重要性", "评价指标"),
        note="自适应提升。",
    ),
    dict(
        id="ml.gbdt",
        label="GBDT 梯度提升树",
        group="集成学习",
        kind="预测模型",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("预测建模", "特征重要性"),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "特征重要性", "评价指标"),
        note="逐步拟合负梯度。",
    ),
    dict(
        id="ml.svm",
        label="支持向量机 SVM",
        group="经典算法",
        kind="预测模型",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("预测建模",),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "评价指标"),
        note="核函数与支持向量。",
    ),
    dict(
        id="ml.knn",
        label="K 近邻 KNN",
        group="经典算法",
        kind="预测模型",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("预测建模",),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "评价指标"),
        note="距离度量与 k 选择。",
    ),
    dict(
        id="ml.nb",
        label="朴素贝叶斯",
        group="经典算法",
        kind="预测模型",
        needs=None,
        tasks=("classification",),
        scenarios=("预测建模",),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "评价指标"),
        note="高斯与多项式朴素贝叶斯。",
    ),
    dict(
        id="ml.mlp",
        label="神经网络 MLP",
        group="神经网络",
        kind="预测模型",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("预测建模",),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "评价指标"),
        note="多层感知机与损失曲线。",
    ),
    dict(
        id="ml.rbf",
        label="RBF 径向基网络",
        group="神经网络",
        kind="预测模型",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("预测建模",),
        inputs=("特征矩阵", "目标列"),
        outputs=("预测值", "评价指标"),
        note="径向基核的浅层网络。",
    ),
    dict(
        id="ml.trees",
        label="CART 决策树（基尼 / 熵）",
        group="树模型",
        kind="预测模型",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("预测建模", "规则提取"),
        inputs=("特征矩阵", "目标列"),
        outputs=("规则集", "特征重要性"),
        note="实际使用 CART 二叉树，以基尼或熵下降分裂；不声称实现 C4.5/CHAID/QUEST。",
    ),
    dict(
        id="ml.lda_qda",
        label="判别分析 LDA / QDA",
        group="经典算法",
        kind="预测模型",
        needs=None,
        tasks=("classification",),
        scenarios=("预测建模",),
        inputs=("特征矩阵", "分类目标"),
        outputs=("分组标签", "回归系数", "评价指标"),
        note="线性与二次判别边界。",
    ),
    dict(
        id="series.arima",
        label="ARIMA",
        group="时间序列",
        kind="时序建模",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("时序预测", "平稳性诊断"),
        inputs=("时间序列",),
        outputs=("时序预测值", "模型诊断量"),
        note="自回归差分移动平均与预测。",
    ),
    dict(
        id="series.sarima",
        label="季节性 ARIMA",
        group="时间序列",
        kind="时序建模",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("时序预测", "平稳性诊断"),
        inputs=("时间序列",),
        outputs=("时序预测值", "模型诊断量"),
        note="含季节项的 ARIMA。",
    ),
    dict(
        id="series.garch",
        label="GARCH 波动率",
        group="时间序列",
        kind="时序建模",
        needs="arch",
        tasks=("regression",),
        scenarios=("时序预测", "平稳性诊断"),
        inputs=("时间序列",),
        outputs=("时序预测值", "模型诊断量"),
        note="条件异方差与波动率预测。",
    ),
    dict(
        id="series.var",
        label="VAR 向量自回归",
        group="时间序列",
        kind="时序建模",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("时序预测", "平稳性诊断"),
        inputs=("时间序列",),
        outputs=("时序预测值", "回归系数"),
        note="多变量相互动态与脉冲响应。",
    ),
    dict(
        id="series.adf",
        label="单位根检验 ADF",
        group="时间序列",
        kind="时序建模",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("时序预测", "平稳性诊断"),
        inputs=("时间序列",),
        outputs=("检验统计量与 p 值", "模型诊断量"),
        note="平稳性检验。",
    ),
    dict(
        id="series.coint",
        label="协整检验",
        group="时间序列",
        kind="时序建模",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("时序预测", "平稳性诊断"),
        inputs=("时间序列",),
        outputs=("检验统计量与 p 值",),
        note="长期均衡关系。",
    ),
    dict(
        id="series.granger",
        label="格兰杰因果检验",
        group="时间序列",
        kind="时序建模",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("时序预测", "平稳性诊断"),
        inputs=("时间序列",),
        outputs=("检验统计量与 p 值",),
        note="领先滞后预测关系。",
    ),
    dict(
        id="series.gm11",
        label="灰色预测 GM(1,1)",
        group="时间序列",
        kind="时序建模",
        needs=None,
        tasks=("regression",),
        scenarios=("时序预测", "平稳性诊断"),
        inputs=("时间序列",),
        outputs=("时序预测值", "评价指标"),
        note="小样本累加生成预测。",
    ),
    dict(
        id="series.moran",
        label="空间自相关 Moran's I",
        group="空间计量",
        kind="空间建模",
        needs=None,
        tasks=("regression",),
        scenarios=("空间分析",),
        inputs=("空间坐标", "目标列"),
        outputs=("检验统计量与 p 值", "分组标签"),
        note="空间聚集程度与局部指标。",
    ),
    dict(
        id="series.spatial",
        label="空间滞后/误差/杜宾模型",
        group="空间计量",
        kind="空间建模",
        needs="spreg",
        tasks=("regression",),
        scenarios=("空间分析",),
        inputs=("空间坐标", "特征矩阵"),
        outputs=("估计量与显著性",),
        note="含空间权重的回归模型。",
    ),
    dict(
        id="series.panel",
        label="面板数据模型",
        group="面板数据",
        kind="面板建模",
        needs="linearmodels",
        tasks=("regression",),
        scenarios=("面板分析",),
        inputs=("个体列", "时间列", "特征矩阵", "目标列"),
        outputs=("估计量与显著性", "模型诊断量"),
        note="固定效应、随机效应、系统 GMM。",
    ),
    dict(
        id="series.threshold",
        label="门槛回归",
        group="面板数据",
        kind="面板建模",
        needs=None,
        tasks=("regression",),
        scenarios=("面板分析",),
        inputs=("特征矩阵", "目标列"),
        outputs=("估计量与显著性",),
        note="按门槛变量分段估计。",
    ),
    dict(
        id="series.tobit",
        label="Tobit 回归",
        group="面板数据",
        kind="面板建模",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("面板分析",),
        inputs=("特征矩阵", "目标列"),
        outputs=("回归系数", "模型诊断量"),
        note="受限因变量（截断/删失）。",
    ),
    dict(
        id="series.quantile",
        label="分位数回归",
        group="面板数据",
        kind="面板建模",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("面板分析",),
        inputs=("特征矩阵", "目标列"),
        outputs=("回归系数", "估计量与显著性"),
        note="不同分位点上的条件影响。",
    ),
    dict(
        id="causal.did",
        label="双重差分 DID",
        group="因果推断",
        kind="因果推断",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("因果效应评估", "政策评估"),
        inputs=("分组列", "两分组列", "目标列"),
        outputs=("因果效应估计", "估计量与显著性"),
        note="处理组与对照组前后变化。",
    ),
    dict(
        id="causal.psm",
        label="倾向得分匹配 PSM",
        group="因果推断",
        kind="因果推断",
        needs=None,
        tasks=("classification",),
        scenarios=("因果效应评估", "政策评估"),
        inputs=("特征矩阵", "两分组列", "目标列"),
        outputs=("因果效应估计", "汇总表"),
        note="匹配后比较与平衡性检验。",
    ),
    dict(
        id="causal.psmdid",
        label="PSM-DID",
        group="因果推断",
        kind="因果推断",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("因果效应评估", "政策评估"),
        inputs=("特征矩阵", "两分组列", "目标列"),
        outputs=("因果效应估计", "估计量与显著性"),
        note="匹配后再做双重差分。",
    ),
    dict(
        id="causal.rd",
        label="断点回归 RD",
        group="因果推断",
        kind="因果推断",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("因果效应评估", "政策评估"),
        inputs=("特征矩阵", "目标列"),
        outputs=("因果效应估计", "估计量与显著性"),
        note="阈值附近的局部效应。",
    ),
    dict(
        id="causal.heckman",
        label="Heckman 两步法",
        group="因果推断",
        kind="因果推断",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("因果效应评估", "政策评估"),
        inputs=("特征矩阵", "两分组列", "目标列"),
        outputs=("回归系数", "估计量与显著性"),
        note="样本选择偏误修正。",
    ),
    dict(
        id="causal.placebo",
        label="安慰剂检验",
        group="因果推断",
        kind="因果推断",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("因果效应评估", "政策评估"),
        inputs=("两分组列", "目标列"),
        outputs=("因果效应估计", "检验统计量与 p 值"),
        note="随机化处理时点或组别的稳健性。",
    ),
    dict(
        id="design.factorial",
        label="全因子设计",
        group="实验设计",
        kind="实验设计",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("实验设计",),
        inputs=("因子列", "目标列"),
        outputs=("估计量与显著性", "试验方案表"),
        note="主效应与交互效应估计。",
    ),
    dict(
        id="design.orthogonal",
        label="正交设计",
        group="实验设计",
        kind="实验设计",
        needs=None,
        tasks=("regression",),
        scenarios=("实验设计",),
        inputs=("因子列",),
        outputs=("试验方案表",),
        note="正交表安排多因素试验。",
    ),
    dict(
        id="design.uniform",
        label="均匀设计",
        group="实验设计",
        kind="实验设计",
        needs=None,
        tasks=("regression",),
        scenarios=("实验设计",),
        inputs=("因子列",),
        outputs=("试验方案表",),
        note="均匀散布的试验点。",
    ),
    dict(
        id="design.rsm",
        label="响应面分析 RSM",
        group="实验设计",
        kind="实验设计",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("实验设计",),
        inputs=("因子列", "目标列"),
        outputs=("回归系数", "排序结果"),
        note="二阶模型与最优区域。",
    ),
    dict(
        id="design.ccd",
        label="中心复合设计 CCD",
        group="实验设计",
        kind="实验设计",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("实验设计",),
        inputs=("因子列",),
        outputs=("试验方案表",),
        note="可拟合二次曲面的经典设计。",
    ),
    dict(
        id="design.boxbehnken",
        label="Box-Behnken 设计",
        group="实验设计",
        kind="实验设计",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("实验设计",),
        inputs=("因子列",),
        outputs=("试验方案表",),
        note="三水平不包含角点的设计。",
    ),
    dict(
        id="eval.pca",
        label="主成分分析评价",
        group="客观赋权",
        kind="指标赋权",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("指标赋权",),
        inputs=("多指标矩阵",),
        outputs=("权重向量", "综合得分"),
        note="以方差贡献率加权综合。",
    ),
    dict(
        id="eval.factor",
        label="因子分析",
        group="客观赋权",
        kind="指标赋权",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("指标赋权",),
        inputs=("多指标矩阵",),
        outputs=("权重向量", "综合得分"),
        note="潜因子结构与因子得分。",
    ),
    dict(
        id="eval.entropy",
        label="熵值法",
        group="客观赋权",
        kind="指标赋权",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("指标赋权",),
        inputs=("多指标矩阵",),
        outputs=("权重向量",),
        note="按信息量确定权重。",
    ),
    dict(
        id="eval.critic",
        label="CRITIC 权重法",
        group="客观赋权",
        kind="指标赋权",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("指标赋权",),
        inputs=("多指标矩阵",),
        outputs=("权重向量",),
        note="对比强度与冲突性赋权。",
    ),
    dict(
        id="eval.topsis",
        label="TOPSIS",
        group="排序决策",
        kind="决策排序",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("方案排序", "指标赋权"),
        inputs=("多指标矩阵",),
        outputs=("综合得分", "排序结果"),
        note="与理想解的距离排序。",
    ),
    dict(
        id="eval.vikor",
        label="VIKOR",
        group="排序决策",
        kind="决策排序",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("方案排序", "指标赋权"),
        inputs=("多指标矩阵",),
        outputs=("综合得分", "排序结果"),
        note="折衷排序与群体效用。",
    ),
    dict(
        id="eval.rsr",
        label="秩和比 RSR",
        group="排序决策",
        kind="决策排序",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("方案排序", "指标赋权"),
        inputs=("多指标矩阵",),
        outputs=("排序结果", "综合得分"),
        note="秩次综合评价与分档。",
    ),
    dict(
        id="eval.dea",
        label="数据包络分析 DEA",
        group="效率评价",
        kind="效率评价",
        needs=None,
        tasks=("regression",),
        scenarios=("效率评价",),
        inputs=("多指标矩阵",),
        outputs=("效率值",),
        note="投入产出效率前沿。",
    ),
    dict(
        id="eval.fuzzy",
        label="模糊综合评价",
        group="排序决策",
        kind="决策排序",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("方案排序", "指标赋权"),
        inputs=("多指标矩阵",),
        outputs=("综合得分", "排序结果"),
        note="隶属度矩阵与合成算子。",
    ),
    dict(
        id="eval.grey",
        label="灰色关联分析",
        group="排序决策",
        kind="决策排序",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("方案排序", "指标赋权"),
        inputs=("多指标矩阵",),
        outputs=("相关系数", "排序结果"),
        note="参考序列的关联度排序。",
    ),
    dict(
        id="domain.wordfreq",
        label="词频统计",
        group="文本分析",
        kind="文本分析",
        needs=None,
        tasks=("classification",),
        scenarios=("文本分析",),
        inputs=("文本列",),
        outputs=("汇总表",),
        note="高频词与词云数据。",
    ),
    dict(
        id="domain.tfidf",
        label="TF-IDF",
        group="文本分析",
        kind="文本分析",
        needs=None,
        tasks=("classification",),
        scenarios=("文本分析",),
        inputs=("文本列",),
        outputs=("汇总表",),
        note="词项权重与关键词抽取。",
    ),
    dict(
        id="domain.sentiment",
        label="情感分析",
        group="文本分析",
        kind="文本分析",
        needs=None,
        tasks=("classification",),
        scenarios=("文本分析",),
        inputs=("文本列",),
        outputs=("主题与情感", "汇总表"),
        note="词典法与监督分类。",
    ),
    dict(
        id="domain.lda",
        label="LDA 主题模型",
        group="文本分析",
        kind="文本分析",
        needs=None,
        tasks=("clustering",),
        scenarios=("文本分析",),
        inputs=("文本列",),
        outputs=("主题与情感", "评价指标"),
        note="主题分布与主题词。",
    ),
    dict(
        id="domain.km",
        label="Kaplan-Meier 生存曲线",
        group="生存分析",
        kind="生存分析",
        needs="lifelines",
        tasks=("classification",),
        scenarios=("生存分析",),
        inputs=("生存时间与事件",),
        outputs=("生存曲线", "估计量与显著性"),
        note="生存函数与中位生存期。",
    ),
    dict(
        id="domain.cox",
        label="Cox 比例风险回归",
        group="生存分析",
        kind="生存分析",
        needs="lifelines",
        tasks=("classification",),
        scenarios=("生存分析",),
        inputs=("生存时间与事件", "特征矩阵"),
        outputs=("风险比", "估计量与显著性"),
        note="风险比与协变量影响。",
    ),
    dict(
        id="domain.nomogram",
        label="列线图",
        group="生存分析",
        kind="生存分析",
        needs="lifelines",
        tasks=("classification",),
        scenarios=("生存分析",),
        inputs=("生存时间与事件", "特征矩阵"),
        outputs=("风险比", "排序结果"),
        note="个体风险评分与预测。",
    ),
    dict(
        id="domain.competing",
        label="竞争风险模型",
        group="生存分析",
        kind="生存分析",
        needs="lifelines",
        tasks=("classification",),
        scenarios=("生存分析",),
        inputs=("生存时间与事件",),
        outputs=("生存曲线",),
        note="多种终点的累积发生函数。",
    ),
    dict(
        id="domain.reliability",
        label="信度效度分析",
        group="问卷与市场",
        kind="问卷分析",
        needs=None,
        tasks=("classification", "regression"),
        scenarios=("问卷分析", "市场调研"),
        inputs=("问卷量表",),
        outputs=("信效度指标",),
        note="Cronbach α、KMO 与 Bartlett。",
    ),
    dict(
        id="domain.nps",
        label="NPS 净推荐值",
        group="问卷与市场",
        kind="问卷分析",
        needs=None,
        tasks=("regression", "classification"),
        scenarios=("问卷分析", "市场调研"),
        inputs=("连续目标",),
        outputs=("汇总表", "评价指标"),
        note="推荐者减贬损者占比。",
    ),
    dict(
        id="domain.kano",
        label="Kano 模型",
        group="问卷与市场",
        kind="问卷分析",
        needs=None,
        tasks=("classification",),
        scenarios=("问卷分析", "市场调研"),
        inputs=("问卷量表",),
        outputs=("汇总表", "排序结果"),
        note="需求属性分类。",
    ),
    dict(
        id="domain.maxdiff",
        label="MaxDiff 评分推导（非选择模型）",
        group="问卷与市场",
        kind="问卷分析",
        needs=None,
        tasks=("classification",),
        scenarios=("问卷分析", "市场调研"),
        inputs=("多指标矩阵",),
        outputs=("偏好效用", "排序结果"),
        note="偏好份额估计。",
    ),
    dict(
        id="domain.conjoint",
        label="联合分析",
        group="问卷与市场",
        kind="问卷分析",
        needs=None,
        tasks=("regression",),
        scenarios=("问卷分析", "市场调研"),
        inputs=("因子列", "目标列"),
        outputs=("偏好效用", "估计量与显著性"),
        note="属性效用与重要性。",
    ),
    dict(
        id="domain.psm",
        label="价格分位数与需求代理（非四问 PSM）",
        group="问卷与市场",
        kind="问卷分析",
        needs=None,
        tasks=("classification",),
        scenarios=("问卷分析", "市场调研"),
        inputs=("连续目标",),
        outputs=("排序结果",),
        note="价格接受区间与最优点。",
    ),
    dict(
        id="domain.control",
        label="控制图（X-bar/R、CUSUM、EWMA）",
        group="质量控制",
        kind="过程控制",
        needs=None,
        tasks=("regression",),
        scenarios=("质量控制",),
        inputs=("连续目标", "时间列"),
        outputs=("控制限", "汇总表"),
        note="过程受控判定与告警点。",
    ),
    dict(
        id="domain.capability",
        label="过程能力分析",
        group="质量控制",
        kind="过程控制",
        needs=None,
        tasks=("regression",),
        scenarios=("质量控制",),
        inputs=("连续目标",),
        outputs=("过程能力指数",),
        note="Cp、Cpk、Pp、Ppk。",
    ),
    dict(
        id="domain.weibull",
        label="Weibull 可靠性分析",
        group="质量控制",
        kind="过程控制",
        needs=None,
        tasks=("regression",),
        scenarios=("质量控制",),
        inputs=("生存时间与事件",),
        outputs=("可靠度曲线", "估计量与显著性"),
        note="形状与尺度参数、可靠度曲线。",
    ),
    dict(
        id="domain.meta",
        label="Meta 分析",
        group="Meta 分析",
        kind="Meta 分析",
        needs="statsmodels",
        tasks=("regression",),
        scenarios=("证据汇总",),
        inputs=("效应量列",),
        outputs=("效应量与异质性", "估计量与显著性"),
        note="二分类/连续效应量与异质性。",
    ),
]

BY_ID = {item["id"]: item for item in CATALOG}

_runnable = {}


GROUP_OF = {item["id"]: item["group"] for item in CATALOG}
_CATEGORY_GROUPS = {}
for _item in CATALOG:
    _CATEGORY_GROUPS.setdefault(category_of(_item["id"]), [])
    if _item["group"] not in _CATEGORY_GROUPS[category_of(_item["id"])]:
        _CATEGORY_GROUPS[category_of(_item["id"])].append(_item["group"])


def prerequisite_ids(method_id):
    return [need for need in dict.fromkeys(METHOD_BEFORE.get(method_id, ())) if need != method_id]


def suggest_ids(method_id):
    hard = set(prerequisite_ids(method_id))
    return [
        need
        for need in dict.fromkeys(METHOD_SUGGESTS.get(method_id, ()))
        if need != method_id and need not in hard
    ]


def dependent_ids(method_id):
    return [item["id"] for item in CATALOG if method_id in prerequisite_ids(item["id"])]


def suggested_dependent_ids(method_id):
    return [item["id"] for item in CATALOG if method_id in suggest_ids(item["id"])]


def alternative_ids(method_id):
    found = []
    for left, right, _why in SIMILAR:
        if left == method_id:
            found.append(right)
        elif right == method_id:
            found.append(left)
    return found


def alternative_why(method_id, other_id):
    for left, right, why in SIMILAR:
        if {left, right} == {method_id, other_id}:
            return why
    return ""


def label_of(method_id):
    return BY_ID.get(method_id, {}).get("label") or method_id


def edge_why(source, target, kind="prerequisite"):
    known = EDGE_WHY.get((source, target))
    if known:
        return known
    if kind == "suggest":
        return f"先看「{label_of(source)}」，再学「{label_of(target)}」会顺一些。"
    return f"先学「{label_of(source)}」，才谈得上「{label_of(target)}」。"


_LEVELS = {}


def depths():
    needs = {item["id"]: prerequisite_ids(item["id"]) for item in CATALOG}
    found = {}

    def reach(method_id, seen):
        if method_id in found:
            return found[method_id]
        if method_id in seen:
            return 1
        seen.add(method_id)
        best = 1
        for need in needs.get(method_id, ()):
            if need in needs:
                best = max(best, reach(need, seen) + 1)
        found[method_id] = best
        return best

    for item in CATALOG:
        reach(item["id"], set())
    return found


LAYER_PLAN = (
    (
        "数据认知与描述统计",
        "先看清数据长什么样：统计量、频数、交叉表与分组汇总。",
        (
            "describe.stats",
            "describe.frequency",
            "describe.explore",
            "describe.aggregate",
            "describe.crosstab",
        ),
    ),
    (
        "数据清洗",
        "把脏数据收拾干净：重复值、缺失值、异常值与变换。",
        ("prep.duplicates", "prep.missing", "prep.outliers", "prep.winsorize", "prep.transform"),
    ),
    (
        "探索分析",
        "把变量整理成模型能用的形状，并看清它们之间的关系。",
        ("prep.encoding", "prep.derive", "prep.balance", "prep.scale", "model.correlation"),
    ),
    (
        "基础统计推断",
        "从样本推到总体：参数检验与非参数检验。",
        (
            "test.wilcoxon",
            "test.mannwhitney",
            "test.kruskal",
            "test.friedman",
            "test.cochran",
            "test.ttest",
            "test.chi2",
            "test.gof",
            "test.fisher",
            "test.anova",
        ),
    ),
    (
        "基础机器学习",
        "第一个预测模型与最基础的聚类：树、近邻、K-Means、DBSCAN 与模糊聚类。",
        ("ml.nb", "ml.trees", "ml.knn", "ml.kmeans", "ml.hierarchical", "ml.dbscan", "ml.fcm"),
    ),
    (
        "集成与神经网络",
        "把模型合起来或换成更强的拟合器：袋装、提升、支持向量机与神经网络。",
        (
            "ml.random_forest",
            "ml.xgboost",
            "ml.lightgbm",
            "ml.adaboost",
            "ml.gbdt",
            "ml.svm",
            "ml.mlp",
            "ml.rbf",
        ),
    ),
    (
        "回归与机制模型",
        "回归家族与机制模型：正则、广义线性、多层模型与中介调节。",
        (
            "model.vif",
            "model.linear",
            "model.ridge",
            "model.lasso",
            "model.elasticnet",
            "model.logistic",
            "model.probit",
            "model.robust",
            "model.poisson",
            "model.gamma",
            "model.glmm",
            "model.gee",
            "model.mixed",
            "model.mediation",
            "model.moderation",
            "model.chained",
        ),
    ),
    (
        "降维与多变量",
        "多个变量一起看：主成分、t-SNE、因子、判别与典型相关。",
        ("prep.pca", "prep.tsne", "eval.pca", "eval.factor", "model.canonical", "ml.lda_qda"),
    ),
    (
        "时间与面板数据",
        "带时间与空间结构的数据：序列、波动、面板、空间与谱特征。",
        (
            "series.adf",
            "series.gm11",
            "series.arima",
            "series.var",
            "series.coint",
            "series.granger",
            "series.moran",
            "series.sarima",
            "series.garch",
            "series.spatial",
            "series.panel",
            "series.threshold",
            "series.tobit",
            "series.quantile",
            "prep.spectral",
        ),
    ),
    (
        "因果推断",
        "从观察数据里识别因果：双重差分、断点、倾向得分与 Heckman。",
        (
            "causal.did",
            "causal.rd",
            "causal.psm",
            "causal.placebo",
            "causal.psmdid",
            "causal.heckman",
        ),
    ),
    (
        "实验设计与优化",
        "先算清需要多少样本，再主动做实验并按响应面寻优。",
        (
            "design.factorial",
            "design.orthogonal",
            "design.ccd",
            "design.boxbehnken",
            "design.uniform",
            "design.rsm",
            "describe.power",
        ),
    ),
    (
        "综合评价与决策",
        "把多指标合成一个评价值：客观赋权与决策排序。",
        (
            "eval.entropy",
            "eval.critic",
            "eval.dea",
            "eval.grey",
            "eval.topsis",
            "eval.vikor",
            "eval.rsr",
            "eval.fuzzy",
        ),
    ),
    (
        "行业与专题方法",
        "面向具体数据类型与业务场景：生存、文本、问卷、质量控制与 Meta。",
        (
            "domain.km",
            "domain.reliability",
            "domain.nps",
            "domain.maxdiff",
            "domain.conjoint",
            "domain.psm",
            "domain.weibull",
            "domain.wordfreq",
            "domain.cox",
            "domain.competing",
            "domain.kano",
            "domain.control",
            "domain.tfidf",
            "domain.sentiment",
            "domain.nomogram",
            "domain.capability",
            "domain.meta",
            "domain.lda",
        ),
    ),
)

LAYER_NAMES = {index: name for index, (name, _hint, _methods) in enumerate(LAYER_PLAN, 1)}
LAYER_HINTS = {index: hint for index, (_name, hint, _methods) in enumerate(LAYER_PLAN, 1)}


def planned():
    planned = {}
    for index, (_name, _hint, methods) in enumerate(LAYER_PLAN, 1):
        for method_id in methods:
            planned[method_id] = index
    return planned


def levels():
    if _LEVELS:
        return _LEVELS
    planned_levels = planned()
    fallback = depths()
    for item in CATALOG:
        _LEVELS[item["id"]] = planned_levels.get(item["id"], fallback[item["id"]])
    return _LEVELS


def layers(level_of=None):
    level_of = level_of or levels()
    buckets = {}
    for item in CATALOG:
        buckets.setdefault(level_of[item["id"]], []).append(item)
    rows = []
    for level in sorted(buckets):
        items = buckets[level]
        counts = {}
        for item in items:
            counts[item["group"]] = counts.get(item["group"], 0) + 1
        fallback = f"{max(counts, key=counts.get)} 等 {len(counts)} 个分组"
        rows.append(
            {
                "level": level,
                "name": LAYER_NAMES.get(level, fallback),
                "hint": LAYER_HINTS.get(level, ""),
                "count": len(items),
                "groups": sorted(counts, key=lambda name: (-counts[name], name)),
                "methods": [item["id"] for item in items],
            }
        )
    return rows


def method_card(method_id):
    from engine.method_math import public_lesson

    item = BY_ID.get(method_id)
    if item is None:
        return None
    return {
        "id": item["id"],
        "label": item["label"],
        "category": category_of(item["id"]),
        "category_name": CATEGORY_NAMES.get(category_of(item["id"])),
        "group": item["group"],
        "kind": item["kind"],
        "tasks": list(item["tasks"]),
        "scenarios": list(item["scenarios"]),
        "inputs": list(item["inputs"]),
        "outputs": list(item["outputs"]),
        "note": item["note"],
        "math": public_lesson(method_id),
        "when": WHEN.get(item["id"], ""),
        "level": levels().get(item["id"], 1),
        "needs": item["needs"],
        "missing": missing_for(item),
        "before": prerequisite_ids(item["id"]),
        "suggests": suggest_ids(item["id"]),
        "after": dependent_ids(item["id"]),
        "more": suggested_dependent_ids(item["id"]),
        "similar": alternative_ids(item["id"]),
        "similar_why": {
            other: alternative_why(item["id"], other) for other in alternative_ids(item["id"])
        },
    }


def graph():
    cards = [method_card(item["id"]) for item in CATALOG]

    tree = []
    for key, name, hint, _prefixes in CATEGORIES:
        groups = []
        for group_name in _CATEGORY_GROUPS.get(key, []):
            members = [
                item["id"]
                for item in CATALOG
                if item["group"] == group_name and category_of(item["id"]) == key
            ]
            if not members:
                continue
            groups.append(
                {
                    "name": group_name,
                    "kind": GROUP_KIND.get(group_name),
                    "count": len(members),
                    "methods": members,
                }
            )
        tree.append(
            {
                "key": key,
                "name": name,
                "hint": hint,
                "count": sum(group["count"] for group in groups),
                "scenarios": sorted(
                    {name for group in groups for name in GROUP_SCENARIOS.get(group["name"], ())}
                ),
                "groups": groups,
            }
        )

    prerequisites = [
        {"from": source, "to": target, "why": edge_why(source, target)}
        for source, target in relation_graph()
    ]
    suggests = [
        {"from": source, "to": target, "why": edge_why(source, target, "suggest")}
        for source, target in suggest_graph()
    ]
    alternatives = [{"from": left, "to": right, "why": why} for left, right, why in SIMILAR]

    scenarios = []
    for name in SCENARIOS:
        scenarios.append(
            {
                "name": name,
                "methods": [item["id"] for item in CATALOG if name in item["scenarios"]],
            }
        )

    rows = layers()
    return {
        "cards": cards,
        "tree": tree,
        "edges": {
            "prerequisite": prerequisites,
            "suggest": suggests,
            "alternative": alternatives,
        },
        "layers": rows,
        "scenarios": scenarios,
        "counts": {
            "methods": len(cards),
            "groups": len({item["group"] for item in CATALOG}),
            "categories": len(CATEGORIES),
            "prerequisite": len(prerequisites),
            "suggest": len(suggests),
            "alternative": len(alternatives),
            "levels": len(rows),
        },
        "problems": validate(),
    }


def relation_graph():
    edges = []
    for item in CATALOG:
        for need in prerequisite_ids(item["id"]):
            edges.append((need, item["id"]))
    return edges


def suggest_graph():
    edges = []
    for item in CATALOG:
        for need in suggest_ids(item["id"]):
            edges.append((need, item["id"]))
    return edges


def validate():
    problems = []
    known = set(BY_ID)
    for item in CATALOG:
        method_id = item["id"]
        for field in ("kind", "scenarios", "inputs", "outputs"):
            if not item.get(field):
                problems.append(f"{method_id} 缺少 {field}")
        if item["kind"] not in KINDS:
            problems.append(f"{method_id} 的 kind 不在词表内：{item['kind']}")
        for name in item["scenarios"]:
            if name not in SCENARIOS:
                problems.append(f"{method_id} 的 scenario 不在词表内：{name}")
        for name in item["inputs"]:
            if name not in INPUTS:
                problems.append(f"{method_id} 的 input 不在词表内：{name}")
        for name in item["outputs"]:
            if name not in OUTPUTS:
                problems.append(f"{method_id} 的 output 不在词表内：{name}")

    for method_id, needs in METHOD_BEFORE.items():
        if method_id not in known:
            problems.append(f"METHOD_BEFORE 里有未知方法：{method_id}")
        if len(needs) != len(set(needs)):
            problems.append(f"{method_id} 存在重复硬前置")
        for need in needs:
            if need not in known:
                problems.append(f"{method_id} 的前置 {need} 不存在")
            if need == method_id:
                problems.append(f"{method_id} 依赖了自己")
    for method_id, needs in METHOD_SUGGESTS.items():
        if method_id not in known:
            problems.append(f"METHOD_SUGGESTS 里有未知方法：{method_id}")
        if len(needs) != len(set(needs)):
            problems.append(f"{method_id} 存在重复软前置")
        for need in needs:
            if need not in known:
                problems.append(f"{method_id} 的软前置 {need} 不存在")
            if need == method_id:
                problems.append(f"{method_id} 软前置依赖了自己")
            if need in METHOD_BEFORE.get(method_id, ()):
                problems.append(f"{method_id} 的 {need} 同时是硬前置和软前置")

    for method_id in known:
        if not WHEN.get(method_id):
            problems.append(f"{method_id} 缺少 when 描述")

    for left, right, why in SIMILAR:
        if left not in known or right not in known:
            problems.append(f"SIMILAR 里有未知方法：{left} / {right}")
        if left == right:
            problems.append(f"SIMILAR 里有自我配对：{left}")
        if not why:
            problems.append(f"SIMILAR 里 {left} / {right} 缺少换用说明")
    pairs = [tuple(sorted((left, right))) for left, right, _why in SIMILAR]
    for pair in set(pairs):
        if pairs.count(pair) > 1:
            problems.append(f"SIMILAR 里有重复配对：{pair}")

    edges = {item["id"]: set(prerequisite_ids(item["id"])) for item in CATALOG}
    directed = {(need, method_id) for method_id in edges for need in edges[method_id]}
    directed |= {(need, item["id"]) for item in CATALOG for need in suggest_ids(item["id"])}
    for left, right, _why in SIMILAR:
        if (left, right) in directed or (right, left) in directed:
            problems.append(f"{left} 与 {right} 既是前置关系又是可替代，同一对方法只该有一种关系")
    for item in CATALOG:
        method_id = item["id"]
        for need in prerequisite_ids(method_id):
            if method_id in suggest_ids(need):
                problems.append(f"{need} 与 {method_id} 既是硬前置又是软前置")
    colour = {}

    def visit(node, trail):
        state = colour.get(node)
        if state == "done":
            return None
        if state == "open":
            return trail + [node]
        colour[node] = "open"
        for need in edges.get(node, ()):
            cycle = visit(need, trail + [node])
            if cycle:
                return cycle
        colour[node] = "done"
        return None

    for method_id in edges:
        cycle = visit(method_id, [])
        if cycle:
            problems.append("前置关系存在循环：" + " -> ".join(cycle))
            break

    level_of = levels()
    missing_names = sorted({level for level in set(level_of.values()) if level not in LAYER_NAMES})
    if missing_names:
        problems.append(f"LAYER_NAMES 缺少层级名称：{missing_names}")
    return problems


def missing_for(item):
    need = item.get("needs")
    if not need:
        return []
    if need not in _runnable:
        try:
            importlib.import_module(need)
            _runnable[need] = True
        except Exception:
            _runnable[need] = False
    return [] if _runnable[need] else [need]


def runnable(item):
    return not missing_for(item)


def refresh():
    _runnable.clear()
    _LEVELS.clear()


def by_category(category):
    return [item for item in CATALOG if category_of(item["id"]) == category]


def for_task(task):
    return [item for item in CATALOG if task in item["tasks"]]


def search(term):
    term = (term or "").strip().lower()
    if not term:
        return []
    found = []
    for item in CATALOG:
        haystack = " ".join(
            [item["id"], item["label"], item.get("note") or "", item.get("group") or ""]
        ).lower()
        if term in haystack:
            found.append(item)
    return found


def public(item):
    missing = missing_for(item)
    return {
        "id": item["id"],
        "label": item["label"],
        "group": item.get("group"),
        "category": category_of(item["id"]),
        "category_label": CATEGORY_NAMES.get(category_of(item["id"]), ""),
        "tasks": list(item["tasks"]),
        "note": item.get("note") or "",
        "runnable": not missing,
        "missing": missing,
    }


def overview():
    rows = []
    for key, name, hint, _prefixes in CATEGORIES:
        items = by_category(key)
        rows.append(
            {
                "key": key,
                "name": name,
                "hint": hint,
                "total": len(items),
                "runnable": sum(1 for item in items if runnable(item)),
                "groups": _groups(items),
            }
        )
    return rows


def _groups(items):
    order = []
    buckets = {}
    for item in items:
        name = item.get("group") or "其他"
        if name not in buckets:
            buckets[name] = []
            order.append(name)
        buckets[name].append(public(item))
    return [{"name": name, "methods": buckets[name]} for name in order]
