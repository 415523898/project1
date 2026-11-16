"""Reviewed series teaching declarations; examples are invented, never results."""

from engine.math_sources import sm, source


def populate(add):
    add(
        "series.arima",
        "statsmodels ARIMA 把趋势作为回归项、误差为 ARIMA；MA 项采用加号。",
        r"\phi(B)(1-B)^d(y_t-m_t)=\theta(B)\epsilon_t,\quad\phi(B)=1-\sum_{j=1}^p\phi_jB^j,\quad\theta(B)=1+\sum_{j=1}^q\theta_jB^j",
        "差分后用过去值与过去创新解释当前误差序列。",
        r"$By_t=y_{t-1}$，$d$ 为差分阶数；$m_t$ 为允许的确定性趋势；$\epsilon_t$ 为白噪声。",
        "按时间排序 → 选 p,d,q/趋势 → 似然估计 → 检查残差 → 预测并还原差分。",
        "差分后需平稳、MA 可逆；有积分时常数趋势受限制，不能把 ARIMA 的回归截距直接当 AR 方程常数。",
        "ARIMA(1,0,0)、均值 m=10、φ=0.5，当前12且未来创新均值0，下一步预测11。",
        sm(
            "generated/statsmodels.tsa.arima.model.ARIMA",
            "ARIMA model specification and trend restrictions",
        ),
    )

    add(
        "series.sarima",
        "乘法季节 ARIMA；季节参数 P,D,Q,s，实际趋势口径以 SARIMAX 实现为准。",
        r"\phi(B)\Phi(B^s)(1-B)^d(1-B^s)^Dy_t=c_t+\theta(B)\Theta(B^s)\epsilon_t",
        "同时建模短期依赖与季节重复。",
        r"$s$ 为季节长度，$\Phi,\Theta$ 为季节 AR/MA 多项式；$c_t$ 为允许趋势。",
        "确定采样周期 → 普通/季节差分 → 选阶 → 拟合诊断 → 按时间预测。",
        "趋势与 ARIMA 回归趋势参数化不同；至少需足够季节周期；季节差分不等于去除全部季节结构。",
        "s=12、D=1、其余零且无趋势时，月度季节随机游走下一年同月预测为今年同月值。",
        sm(
            "generated/statsmodels.tsa.statespace.sarimax.SARIMAX",
            "SARIMAX multiplicative seasonal model",
        ),
    )

    add(
        "series.garch",
        "GARCH(p,q)，此式展示对称 GARCH(1,1)；分布可为 normal/t/skewt。",
        r"\epsilon_t=\sigma_tz_t,\quad\sigma_t^2=\omega+\alpha\epsilon_{t-1}^2+\beta\sigma_{t-1}^2",
        "波动随上一期冲击和波动递推。",
        r"$z_t$ 标准化创新，$\omega>0$，$\alpha,\beta\ge0$；有限无条件方差通常需 α+β<1。",
        "拟合均值 → 对残差条件方差建模 → 选创新分布 → 检验标准化残差 → 预测波动。",
        "条件方差不是收益预测；重尾分布的参数与尺度需核对。",
        "ω=0.1、α=0.2、β=0.7，上一残差平方2、方差1，则新方差1.2。",
        source(
            "arch · Volatility modeling",
            "https://arch.readthedocs.io/en/latest/univariate/univariate_volatility_modeling.html",
            "GARCH variance equation",
        ),
    )

    add(
        "series.var",
        "多变量 VAR(p)，可选确定性趋势和滞后定阶。",
        r"y_t=c+A_1y_{t-1}+\cdots+A_py_{t-p}+u_t",
        "每个变量由所有变量的滞后共同预测。",
        r"$y_t$ 为向量，$A_j$ 为系数矩阵，$u_t$ 为向量创新。",
        "对齐时间 → 检查平稳/协整 → 定阶 → 拟合 → 稳定性、残差、脉冲响应诊断。",
        "VAR 稳定性要求特征根条件；脉冲响应识别取决于排序/结构假设，不能自动视为因果。",
        r"$A_1=\begin{bmatrix}0.5&0\\0.2&0.4\end{bmatrix}$，$y_t=(2,1)^\top$、c=0，下一步预测 $(1,0.8)^\top$。",
        sm("vector_ar", "Vector autoregressions"),
    )

    add(
        "series.adf",
        "ADF 可带常数/趋势；附带 KPSS 的零假设相反。",
        r"\Delta y_t=a+bt+\gamma y_{t-1}+\sum_{j=1}^p\delta_j\Delta y_{t-j}+u_t",
        "ADF 检验 H0:γ=0（单位根），不是普通 t 分布检验。",
        r"$\Delta y_t=y_t-y_{t-1}$；$p$ 为差分滞后数；a,b 按 regression 选择。",
        "选常数/趋势 → 选滞后 → 回归 → 用 Dickey-Fuller 专用分布/临界值判断。",
        "结构突变会影响结果；未拒绝不等于证明单位根；KPSS 的 H0 为平稳。",
        "若统计量−1而对应5%临界值−2.9，不能拒绝单位根（仅示例临界值，实际以工具结果为准）。",
        sm("generated/statsmodels.tsa.stattools.adfuller", "ADF"),
        sm("generated/statsmodels.tsa.stattools.kpss", "KPSS"),
    )

    add(
        "series.coint",
        "Engle-Granger 两步协整；不是所有多变量协整检验的公式。",
        r"y_t=a+\beta x_t+u_t,\qquad u_t\sim I(0)\text{ while }x_t,y_t\sim I(1)",
        "两个非平稳序列存在平稳线性组合。",
        r"$I(1)$ 为一阶单整，$I(0)$ 为平稳，$u_t$ 为长期关系残差。",
        "检验单整阶 → 估计长期回归 → 残差单位根检验，使用协整专用临界值。",
        "不能套普通残差 ADF 的 p 值当协整 p 值；协整不自动给因果方向。",
        "y=2x+平稳噪声且 x 为随机游走时，y−2x 平稳，可能协整。",
        sm("generated/statsmodels.tsa.stattools.coint", "Augmented Engle-Granger two-step test"),
    )

    add(
        "series.granger",
        "预测意义的 Granger，比较含/不含另一序列滞后的嵌套模型。",
        r"F=\frac{(RSS_R-RSS_U)/m}{RSS_U/(n-k_U)}",
        "检验加入 X 的 m 个滞后是否改善对 Y 的条件预测。",
        r"$R,U$ 为受限/非受限模型；$k_U$ 为非受限参数数；$n$ 为有效行数。",
        "对齐序列 → 选滞后 → 拟合两模型 → 联合检验 X 滞后系数全零。",
        "要求时间与滞后设定合理；遗漏变量会造成预测关系，不能等同干预因果。",
        "RSSR=120、RSSU=100、m=2、n−kU=20，F=2。",
        sm(
            "generated/statsmodels.tsa.stattools.grangercausalitytests",
            "Granger noncausality tests",
        ),
    )

    add(
        "series.gm11",
        "标准 GM(1,1)；DGM、Verhulst 及背景权重优化是不同变体。",
        r"x^{(1)}_k=\sum_{i=1}^k x^{(0)}_i,\quad x^{(0)}_k+a z^{(1)}_k=b,\quad z^{(1)}_k=\tfrac12(x^{(1)}_k+x^{(1)}_{k-1})",
        "累加降低波动，用一阶灰微分近似指数趋势再差分还原。",
        r"$x^{(0)}$ 为原序列，$x^{(1)}$ 为累加序列，$a,b$ 为待估参数。",
        "累加 → 构背景值 → 最小二乘估 a,b → 时间响应 → 差分还原；当前可优化背景权重，需读取 used_background。",
        "适合小样本近指数而非任意序列；a≈0 要单独处理；DGM 用离散递推，Verhulst 用饱和增长项。",
        "原值 [2,3,4] 累加为 [2,5,9]，标准均值背景为 [3.5,7]，用后两项建立两条方程。",
        source(
            "Deng (1982) · Grey systems",
            "https://doi.org/10.1016/S0167-6911(82)80025-X",
            "Grey differential models; local implementation specifies background variants",
        ),
    )

    add(
        "series.moran",
        "全局 Moran I；空间权重及行标准化会改变数值。",
        r"I=\frac{n}{S_0}\frac{\sum_{ij}w_{ij}(x_i-\bar x)(x_j-\bar x)}{\sum_i(x_i-\bar x)^2},\quad S_0=\sum_{ij}w_{ij}",
        "度量邻近位置取值的相似性。",
        r"$w_{ij}$ 为邻接/距离权重；$n$ 为位置数；随机置换下常见期望为 −1/(n−1)。",
        "选邻居定义 → 构 W → 中心化 → I → 解析/置换推断；局部 Moran 是另一个统计量。",
        "权重必须有业务依据；孤立点和不对称矩阵影响推断；I 不总被严格限制在 [−1,1]。",
        "两点互为唯一邻居，取值1、3，I=−1，显示高低相邻。",
        source(
            "PySAL · Moran",
            "https://pysal.org/esda/stable/generated/esda.Moran.html",
            "Moran I and spatial weights",
        ),
    )

    add(
        "series.spatial",
        "lag / error / durbin / ols 为不同模型。",
        r"y=\rho Wy+X\beta+\epsilon\quad(SAR),\qquad y=X\beta+u,\ u=\lambda Wu+\epsilon\quad(SEM)",
        "SAR 关联邻近结果，SEM 关联误差，Durbin 再引入 WX。",
        r"$W$ 为已知空间权重，$\rho,\lambda$ 为空间参数。",
        "构 W → 选模型 → 估计 → 诊断；Durbin 为 y=ρWy+Xβ+WXθ+ε，OLS 则不含空间项。",
        "SAR 中系数不直接等于总边际效应，需考虑 (I−ρW)⁻¹ 反馈；W 与外生性假设决定解释。",
        "两地互邻，ρ=0.2、基础预测均为1时，对称均衡预测为1/(1−0.2)=1.25。",
        source(
            "PySAL spreg · Spatial models",
            "https://pysal.org/spreg/api.html",
            "ML_Lag, ML_Error and slx_lags",
        ),
    )

    add(
        "series.panel",
        "固定效应、随机效应、between；下式是双向固定效应。",
        r"y_{it}=\alpha_i+\tau_t+x_{it}^\top\beta+u_{it}",
        "利用个体内时间变化，控制不随时间变的个体差异。",
        r"$i,t$ 为个体和时间；$\alpha_i,\tau_t$ 为个体与时间效应。",
        "确定面板索引 → 选效应 → within/相应估计 → 选聚类标准误；random 还要求个体效应与解释变量不相关，between 对个体均值回归。",
        "固定效应不能估计被吸收的时间不变量；聚类层级、样本选择与共同趋势影响推断。",
        "同一人 y 从3到5、x从1到2，去均值后固定截距消除，简单斜率为2。",
        source(
            "linearmodels · Panel models",
            "https://bashtage.github.io/linearmodels/panel/mathematical-formula.html",
            "Fixed effects, random effects, between estimators",
        ),
    )

    add(
        "series.threshold",
        "按门槛变量分段的回归；门槛搜索非普通固定分组检验。",
        r"y_i=x_i^\top\beta_1\mathbf1(q_i\le\gamma)+x_i^\top\beta_2\mathbf1(q_i>\gamma)+u_i",
        "允许回归关系在门槛两侧不同。",
        r"$q_i$ 为门槛变量，$\gamma$ 为门槛，$\beta_1,\beta_2$ 为分段系数。",
        "确定搜索区间及最小段样本 → 遍历门槛 → 最小化残差平方和 → 适当 bootstrap 不确定性。",
        "门槛由数据选出，不能把固定门槛常规 p 值直接当门槛存在性证据；不同于因果断点设计。",
        "q≤5 时 y=x，q>5 时 y=2x；x=3 的两段预测分别3、6。",
        source(
            "Hansen (2000) · Sample splitting and threshold estimation",
            "https://users.ssc.wisc.edu/~bhansen/papers/ecnmt_00.pdf",
            "Threshold regression and nonstandard inference",
        ),
    )

    add(
        "series.tobit",
        "受限因变量删失似然；不是截断抽样回归，left/right/both 口径不同。",
        r"y_i^*=x_i^\top\beta+\epsilon_i,\quad\epsilon_i\sim N(0,\sigma^2),\quad y_i=\max(L,y_i^*)\ \text{(left)}",
        "边界值记录仍在样本内，代表潜在值落在边界外。",
        r"$y^*$ 为潜在值，$L$ 为已知删失下限；右删失用 min(U,y*)，双侧用 clip。",
        "明确机制/真实边界 → 内部值用正态密度、下边界用 Φ((L−μ)/σ)、上边界用1−Φ((U−μ)/σ) → 最大似然。",
        "从观测最值猜边界不能证明删失；遗漏边界外对象的截断抽样需要不同归一化似然；潜在与观测边际效应不同。",
        "L=0、潜在值−2时观测为0；μ=0、σ=1时落在下界的概率0.5。",
        source(
            "Tobin (1958) · Limited dependent variables",
            "https://doi.org/10.2307/1907382",
            "Censored normal model",
        ),
    )

    add(
        "series.quantile",
        "条件分位数回归，kernel/bandwidth 用于标准误估计。",
        r"\min_\beta\sum_i\rho_\tau(y_i-x_i^\top\beta),\quad\rho_\tau(u)=u(\tau-\mathbf1(u<0))",
        "估计目标条件分位数而非条件均值。",
        r"$\tau\in(0,1)$ 为分位点，$u$ 为残差。",
        "选 τ → 优化非对称绝对损失 → 估计协方差 → 比较不同 τ 系数。",
        "独立/相关样本要选相应推断；多个分位数可能交叉；τ=0.5 是中位数回归。",
        "τ=0.8 时 u=2 损失1.6，u=−2损失0.4，更惩罚低估。",
        sm("generated/statsmodels.regression.quantile_regression.QuantReg", "Quantile regression"),
    )
