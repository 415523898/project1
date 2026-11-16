"""Reviewed modeling teaching declarations; examples are invented, never results."""

from engine.math_sources import scipy, sklearn, sm


def populate(add):
    add(
        "model.correlation",
        "Pearson 线性相关；Spearman 对秩算 Pearson，Kendall 用一致/不一致对。",
        r"r=\frac{\sum_i(x_i-\bar x)(y_i-\bar y)}{\sqrt{\sum_i(x_i-\bar x)^2\sum_i(y_i-\bar y)^2}}",
        "衡量线性共变方向与强度。",
        r"$x_i,y_i$ 为成对观测；$r\in[-1,1]$。",
        "选相关类型 → 成对有效值 → 计算系数/检验 → 必要时多重校正。",
        "常数列分母为零；显著相关不证明因果；不同缺失样本集的相关不可直接比较。",
        "x=[1,2,3]、y=[2,4,6]，r=1。",
        scipy("pearsonr"),
        scipy("spearmanr"),
        scipy("kendalltau"),
    )

    add(
        "model.canonical",
        "典型相关 CCA：两组变量的线性组合。",
        r"\max_{a,b}\ \operatorname{corr}(Xa,Yb),\quad a^\top S_{XX}a=b^\top S_{YY}b=1",
        "寻找两组特征最相关的方向。",
        r"$X,Y$ 为两组中心化数据，$a,b$ 为权重；$S$ 为样本协方差块。",
        "划分两组 → 中心化/缩放 → 解第一对方向 → 在约束下求后续正交方向。",
        "样本量需支持协方差估计；共线和高维会使训练典型相关虚高，应做验证。",
        "X 只有 x、Y 只有 2x 且 x 非常数时，第一典型相关为1。",
        sklearn("cross_decomposition#canonical-correlation-analysis", "CCA"),
    )

    add(
        "model.vif",
        "每个解释变量对其余解释变量回归的共线诊断。",
        r"VIF_j=\frac1{1-R_j^2}",
        "度量该变量系数方差因共线性而膨胀的倍数。",
        r"$R_j^2$ 是用其他解释变量预测第 j 列的决定系数。",
        "逐列辅助回归 → 取 R² → 计算 VIF → 结合业务检查冗余。",
        "不用于证明因果或预测质量；完全共线趋于无穷；阈值不是普适定理。",
        "Rj²=0.8，VIF=5。",
        sm(
            "generated/statsmodels.stats.outliers_influence.variance_inflation_factor",
            "Variance inflation factor",
        ),
    )

    add(
        "model.linear",
        "OLS；截距由参数决定，HC0/HC1/HC3 改标准误口径，不改 OLS 目标。",
        r"\hat\beta=\arg\min_\beta\|y-X\beta\|_2^2,\qquad\hat\beta=(X^\top X)^{-1}X^\top y",
        "寻找平方残差总和最小的线性预测。",
        r"$X$ 为设计矩阵（可含截距列），$y$ 为目标，$\beta$ 为系数。右式要求满列秩。",
        "建矩阵 → 用数值分解拟合（非显式求逆） → 看残差、系数与区间 → 按划分评价。",
        "线性条件均值与外生性；同方差用于常规标准误；秩亏时需广义逆；拟合相关不自动是因果。",
        "点 (0,1)、(1,3)、(2,5)，含截距 OLS 得 β0=1、β1=2，残差均为0。",
        sklearn("linear_model#ordinary-least-squares", "OLS"),
    )

    add(
        "model.ridge",
        "sklearn Ridge：残差和 + αL2；通常不惩罚截距。",
        r"\min_\beta\ \|y-X\beta\|_2^2+\alpha\|\beta\|_2^2",
        "收缩系数减轻方差和共线不稳定。",
        r"$\alpha\ge0$ 为惩罚强度，$\beta$ 为受惩罚系数。",
        "训练集缩放 → 按参数/交叉验证选 α → 拟合 → 留出集验证。",
        "此处未除 n，与 Lasso 的 α 尺度不同；缩放影响惩罚；通常不会产生严格零系数。",
        "无截距，X=[1]、y=[2]、α=1，β=2/(1+1)=1。",
        sklearn("linear_model#ridge-regression-and-classification", "Ridge objective"),
    )

    add(
        "model.lasso",
        "sklearn Lasso：平方误差除以 2n；截距通常不惩罚。",
        r"\min_\beta\ \frac1{2n}\|y-X\beta\|_2^2+\alpha\|\beta\|_1",
        "L1 惩罚可把部分系数压到零。",
        r"$n$ 为训练行数；$\alpha$ 为惩罚强度；$\|\beta\|_1$ 为绝对值和。",
        "缩放 → 选 α → 坐标下降等优化 → 核查收敛与样本外误差。",
        "强相关变量可能被不稳定选择；非零不意味着因果；α 不能直接套用 Ridge 口径。",
        "n=1、X=[1]、y=[2]、无截距、α=0.5，软阈值解 β=1.5。",
        sklearn("linear_model#lasso", "Lasso objective"),
    )

    add(
        "model.elasticnet",
        "sklearn ElasticNet 的 l1_ratio 混合惩罚。",
        r"\min_\beta\ \frac1{2n}\|y-X\beta\|^2+\alpha r\|\beta\|_1+\frac{\alpha(1-r)}2\|\beta\|_2^2",
        "结合稀疏选择与稳定收缩。",
        r"$r\in[0,1]$ 为 l1_ratio，$\alpha$ 为总强度。",
        "缩放 → 联合选 α、r → 优化并看收敛 → 验证。",
        "r=1 为 Lasso；r=0 是此归一化下的 L2，α 数值不直接等于 Ridge 的 α。",
        "β=2、α=1、r=0.5 时，L1 项为1、L2 项为1，总惩罚2。",
        sklearn("linear_model#elastic-net", "Elastic-Net objective"),
    )

    add(
        "model.logistic",
        "二分类 logit；multinomial 用 softmax，需指定基准类/可识别参数化。",
        r"p_i=\frac1{1+e^{-x_i^\top\beta}},\quad\ell=\sum_i[y_i\log p_i+(1-y_i)\log(1-p_i)]",
        "通过最大似然估计类别概率；不是最小二乘拟合类别编号。",
        r"$y_i\in\{0,1\}$，$p_i=P(y_i=1\mid x_i)$；$e^{\beta_j}$ 为条件优势比。",
        "确认类别编码 → 最大化似然 → 阈值分类/概率评价；多类 P(k|x)=exp(ηk)/Σexp(ηl)。",
        "独立观测与 logit 线性；完全分离时估计可能不存在；优势比不是风险比。",
        "η=ln3，二分类 p=3/4；三类 η 全为0，softmax 各1/3。",
        sm("generated/statsmodels.discrete.discrete_model.Logit", "Logit"),
        sm("generated/statsmodels.discrete.discrete_model.MNLogit", "Multinomial logit"),
    )

    add(
        "model.probit",
        "二分类标准正态链接；系数指数不是 logit 的优势比。",
        r"P(y_i=1\mid x_i)=\Phi(x_i^\top\beta),\qquad\frac{\partial p_i}{\partial x_{ij}}=\phi(x_i^\top\beta)\beta_j",
        "用正态累积分布把线性预测映为概率。",
        r"$\Phi,\phi$ 为标准正态 CDF、密度；$\beta_j$ 为潜在尺度系数。",
        "二元编码 → 最大似然 → 计算个体或平均边际效应。",
        "边际效应依赖 x；离散变量宜比较预测概率差；不能把 exp(β)解释成优势比。",
        "η=0 时 p=0.5；βj=1 时局部边际效应 φ(0)≈0.399。",
        sm("generated/statsmodels.discrete.discrete_model.Probit", "Probit"),
    )

    add(
        "model.robust",
        "RLM；默认 bisquare，huber/hampel/andrew 是不同损失。",
        r"\min_\beta\sum_i\rho\!\left(\frac{y_i-x_i^\top\beta}{s}\right)",
        "降低大残差对拟合的影响。",
        r"$s$ 为稳健尺度，$\rho$ 为选定稳健损失。",
        "初始化 → 估计尺度 → 按 ψ(u)/u 更新权重 → 加权拟合直到收敛。",
        "稳健回归不等于 OLS 的稳健标准误；对高杠杆点未必稳健；不同损失不可混称 Huber。",
        "Huber 阈值1时残差3的损失为 1×3−1/2=2.5；平方损失为4.5（此示例仅 Huber）。",
        sm("rlm", "Robust linear models and norms"),
    )

    add(
        "model.mediation",
        "线性单中介乘积法；区间可用 percentile/normal/BCa bootstrap。",
        r"M=aX+u,\qquad Y=c'X+bM+v,\qquad IE=ab",
        "把通过中介 M 的路径系数乘积作为间接效应。",
        r"$a,b$ 为两条路径；$c'$ 为直接效应；截距/控制变量在式中省略。",
        "拟合两条回归 → 算 ab → 对完整观测单位重采样估计区间。",
        "因果解释需要时间顺序与无未控制混杂等额外假设；非线性模型不能直接套 c=c'+ab。",
        "a=0.5、b=2，间接效应=1。",
        sm(
            "generated/statsmodels.stats.mediation.Mediation",
            "Mediation; references and assumptions",
        ),
    )

    add(
        "model.moderation",
        "线性交互项调节效应，中心化改变主效应解释。",
        r"E[Y\mid X,Z]=\beta_0+\beta_1X+\beta_2Z+\beta_3XZ,\quad\frac{\partial E[Y]}{\partial X}=\beta_1+\beta_3Z",
        "X 的效应随 Z 改变。",
        r"$Z$ 为调节变量；$\beta_3$ 为交互系数。",
        "编码/中心化 → 构造乘积 → 拟合 → 在有意义 Z 值报告简单斜率。",
        "主效应是另一变量为零时的条件效应；避免超出观测范围推断。",
        "β1=1、β3=0.5，Z=2 时 X 的斜率为2。",
        sm("example_formulas", "Interactions using formulas"),
    )

    add(
        "model.chained",
        "线性串联双中介，区分各间接路径。",
        r"M_1=a_1X+u_1,\quad M_2=a_2X+dM_1+u_2,\quad Y=c'X+b_1M_1+b_2M_2+v",
        "串联间接效应 a1·d·b2，不包括两条单中介路径。",
        r"$a_1,d,b_2$ 为串联路径系数；另两条间接效应为 $a_1b_1,a_2b_2$。",
        "分别拟合三条回归 → 算三条间接路径 → 对同一行联合 bootstrap。",
        "路径排序是理论假设，回归拟合本身不能证明；因果解释仍需无混杂。",
        "a1=0.5、d=0.4、b2=2，串联效应=0.4。",
        sm(
            "generated/statsmodels.stats.mediation.Mediation",
            "Product of coefficients and resampling; local extension to two mediators",
        ),
    )

    add(
        "model.gamma",
        "Gamma GLM；默认 log，identity/inverse 改链接。",
        r"g(\mu_i)=x_i^\top\beta,\qquad\operatorname{Var}(Y_i\mid x_i)=\phi\mu_i^2",
        "对正连续且方差随均值平方变化的数据建模。",
        r"$\mu_i=E[Y_i|x_i]$，$\phi$ 为离散参数；默认 $g(\mu)=\log\mu$。",
        "检查严格正目标 → 指定链接 → 似然/IRLS 拟合 → 看残差与预测。",
        "零值不符合普通 Gamma；identity/inverse 需保证预测均值为正。",
        "log 链接 η=ln2，则预测均值2；φ=0.5 时条件方差2。",
        sm("generated/statsmodels.genmod.families.family.Gamma", "Gamma variance and links"),
    )

    add(
        "model.poisson",
        "Poisson、quasipoisson、NB 不同方差口径；下式为基础 Poisson log 链接。",
        r"\mu_i=e^{x_i^\top\beta},\quad P(Y_i=y)=\frac{e^{-\mu_i}\mu_i^y}{y!},\quad\operatorname{Var}(Y_i|x_i)=\mu_i",
        "对非负计数建模。",
        r"$y=0,1,\ldots$；$\mu_i$ 为条件期望。",
        "确认计数与暴露量 → 拟合 → 查过度离散；quasi 改为 φμ，NB2 改为 μ+αμ²。",
        "非整数连续数据不宜按计数解释；quasi 不具有相同完整似然，AIC 不能照搬。",
        "μ=2，P(Y=0)=e^(−2)≈0.1353；NB2 α=0.5 时方差4。",
        sm("generated/statsmodels.genmod.families.family.Poisson", "Poisson family"),
        sm("generated/statsmodels.genmod.families.family.NegativeBinomial", "NB2 variance"),
    )

    add(
        "model.gee",
        "边际 GEE，family 与工作相关可配置；稳健协方差不等同工作相关正确。",
        r"\sum_g D_g^\top V_g^{-1}(y_g-\mu_g)=0",
        "用群组内工作相关处理相关观测，估计总体平均效应。",
        r"$D_g=\partial\mu_g/\partial\beta^\top$；$V_g$ 为工作协方差；$g$ 为独立群组。",
        "指定群组/链接/工作相关 → 迭代解估计方程 → 选 robust/naive 协方差。",
        "群组之间独立；稳健推断通常需足够群组；不是随机效应个体条件模型。",
        "工作独立且同方差、仅截距时，方程化为 Σ(y−μ)=0，μ 为样本均值。",
        sm("gee", "Generalized estimating equations"),
    )

    add(
        "model.glmm",
        "实际使用变分贝叶斯拟合 Poisson/log 或 Binomial/logit 分组随机截距；区间为后验可信区间，不是频率学派置信区间。",
        r"g(\mu_{ij})=x_{ij}^\top\beta+b_j,\quad b_j\sim N(0,\sigma_b^2)",
        "在固定效应之外估计个体/群组随机截距。",
        r"$g$ 为 log 或 logit；$b_j$ 是组随机截距；$\sigma_b$ 是组间标准差。",
        "指定目标与组 → 建立固定/随机效应设计矩阵 → 变分贝叶斯拟合 → 报告后验与收敛状态。",
        "当前仅支持 Poisson 与 Binomial 随机截距；后验可信区间不能解释成频率学派显著性检验。",
        "log 链接固定部分 ln3、组截距 ln2 时，该组条件均值为6。",
        sm("mixed_glm", "Generalized linear mixed models"),
    )

    add(
        "model.mixed",
        "线性混合模型，随机截距/斜率；ML 与 REML 的方差估计不同。",
        r"y_g=X_g\beta+Z_gb_g+\epsilon_g,\quad b_g\sim N(0,G),\quad\epsilon_g\sim N(0,\sigma^2I)",
        "把总体固定效应与组特异偏差分开。",
        r"$X,Z$ 为固定/随机设计矩阵；$G$ 为随机效应协方差。",
        "指定组与随机结构 → ML/REML 拟合 → 检查收敛/方差边界 → 解读固定和随机效应。",
        "组间独立，指定协方差合理；随机效应正态是假设；比较不同固定效应模型时不直接比 REML 似然。",
        "固定截距2，组随机截距0.5，则该组条件截距2.5。",
        sm("mixed_linear", "Linear mixed effects models"),
    )
