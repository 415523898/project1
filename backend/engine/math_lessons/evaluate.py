"""Reviewed evaluate teaching declarations; examples are invented, never results."""

from engine.math_sources import PCA, TOPSIS, source


def populate(add):
    add(
        "eval.pca",
        "评价用 PCA；默认 Pearson 分支对归一化后中心化数据做 SVD，方差权重使用对全部成分的方差占比。",
        r"Sv_j=\lambda_jv_j,\quad z_{ij}=x_{c,i}^\top v_j,\quad F_i=\sum_{j=1}^k a_jz_{ij},\quad a_j=\frac{\lambda_j}{\sum_{l=1}^p\lambda_l}",
        "用保留成分得分的加权和构造综合评价。",
        r"$S=X_c^\top X_c/(n-1)$；$p$ 为全部成分数，$k$ 为保留数；$a$ 为方差占比。",
        "统一指标方向与归一化 → 中心化/SVD → 选成分 → 算得分 → 加权并对最终综合值 minmax 到0–1。非 Pearson 分支对相关矩阵分解后以特征向量乘特征值平方根投影；rotate 改分数与权重；equal 为1/k。",
        "成分符号任意，必须说明定向；这是评价扩展，不等于 prep.pca 的降维输出；解释方差不等于业务价值。",
        "全部特征值3、1，保留两项权重0.75、0.25；某对象得分2、0，归一化前综合值1.5；仅保留第一项时当前权重仍0.75。",
        PCA,
    )

    add(
        "eval.factor",
        "共同因子模型；principal、minres、ML 及 varimax/promax 并非同一估计。",
        r"x=\Lambda f+\epsilon,\quad\Sigma=\Lambda\Phi\Lambda^\top+\Psi",
        "用潜在公共因子解释观测变量间共变。",
        r"$\Lambda$ 为载荷，$\Phi$ 为因子协方差，$\Psi$ 为独特方差（通常对角）。",
        "相关/适配性检查 → 提取因子 → 旋转 → 按 regression/Bartlett 算因子分数 → 评价。",
        "正交旋转 Φ=I，斜交可相关；因子分数存在不确定性；principal 提取不应冒称 ML。",
        "单因子载荷0.8、因子方差1、独特方差0.36，观测方差=0.64+0.36=1。",
        source(
            "factor_analyzer · FactorAnalyzer",
            "https://factor-analyzer.readthedocs.io/en/latest/factor_analyzer.html",
            "MINRES, ML, principal extraction and rotation",
        ),
    )

    add(
        "eval.entropy",
        "先统一方向和归一化；熵权与 equal/variance 为不同赋权方案。",
        r"p_{ij}=\frac{z_{ij}}{\sum_i z_{ij}},\quad e_j=-\frac1{\log n}\sum_i p_{ij}\log p_{ij},\quad w_j=\frac{1-e_j}{\sum_l(1-e_l)}",
        "差异越大的指标通常获得越大熵权。",
        r"$z_{ij}$ 为非负变换值，$n$ 为对象数；约定0log0=0。",
        "方向化/归一化 → 非负化与零列保护 → 算 p/e → 归一化信息差异 → 汇总。",
        "要求 n>1；全常数/全零时需约定回退；权重来自数据变异，不代表业务重要性。",
        "一列概率[0.5,0.5]，e=1，差异系数0；[1,0] 时e=0。",
        TOPSIS,
    )

    add(
        "eval.critic",
        "标准差型 CRITIC 为下式；range/cv 与不同相关系数会改变权重。",
        r"C_j=s_j\sum_l(1-r_{jl}),\qquad w_j=\frac{C_j}{\sum_l C_l}",
        "结合对比强度与指标间冲突赋权。",
        r"$s_j$ 为归一化列离散程度，$r_{jl}$ 为列间相关。",
        "同向归一化 → 计算离散/相关 → 算冲突量 → 归一权重。",
        "常数列相关无定义需保护；高变异不等于高质量；CV 在均值近零时不稳。",
        "两指标 s 分别1、2，彼此 r=0，C=1、2，权重1/3、2/3。",
        source(
            "Diakoulaki et al. (1995) · CRITIC",
            "https://doi.org/10.1016/0305-0548(94)00059-H",
            "Contrast intensity and conflict",
        ),
    )

    add(
        "eval.topsis",
        "当前默认 minmax + 熵权 + 样本理想解 + 欧氏距离；非一律向量归一化。",
        r"v_{ij}=w_jz_{ij},\quad D_i^\pm=\sqrt{\sum_j(v_{ij}-v_j^\pm)^2},\quad C_i=\frac{D_i^-}{D_i^++D_i^-}",
        "更接近正理想且远离负理想的对象得分更高。",
        r"$z$ 为方向化和选定归一化值；$w$ 和为1；默认 $v_j^+=\max_i v_{ij},v_j^-=\min_i v_{ij}$。",
        "统一效益/成本方向 → 按 normalize 变换 → 赋权 → 找理想解 → 算距离与贴近度。manhattan/chebyshev 改距离范数；理论边界模式另取约定边界。",
        "正负距离都为0时当前返回0.5；样本增减可能改变排序；权重先乘后求平方与把权重直接乘平方不是同一口径。",
        "两个已归一化对象 A=(1,1)、B=(0,0)，等权后为(0.5,0.5)、(0,0)，C_A=1、C_B=0。",
        TOPSIS,
    )

    add(
        "eval.vikor",
        "群体效用 S 与最大遗憾 R 的折中。",
        r"S_i=\sum_j w_j\frac{f_j^*-f_{ij}}{f_j^*-f_j^-},\quad R_i=\max_j w_j\frac{f_j^*-f_{ij}}{f_j^*-f_j^-},\quad Q_i=v\frac{S_i-S^*}{S^--S^*}+(1-v)\frac{R_i-R^*}{R^--R^*}",
        "同时考虑总遗憾和最差指标，Q 较小较好。",
        r"$f^*,f^-$ 为已统一方向的最好/最差；$S^*,S^-$ 为最小/最大 S，R 同理；$v\in[0,1]$。",
        "统一方向/赋权 → S,R → Q → 检查可接受优势与稳定性后给折中集。",
        "常数指标与零范围需保护；不能仅凭最小 Q 就声称唯一稳健最优。",
        "标准化 S 项0.2、R 项0.6、v=0.5，Q=0.4。",
        source(
            "Opricovic & Tzeng (2004)",
            "https://doi.org/10.1016/S0377-2217(03)00020-1",
            "VIKOR compromise ranking and acceptance conditions",
        ),
    )

    add(
        "eval.rsr",
        "当前采用项目归一秩加权实现；不同于常见 Σrank/(n·m) 传统 RSR。",
        r"RSR_i=\sum_j w_j\frac{r_{ij}-1}{\max(n-1,1)}",
        "各指标统一为效益方向，以升序平均秩缩放到0–1再加权，得分较大较好。",
        r"$r_{ij}$ 为升序平均秩，同值同秩；$n$ 为对象数，单对象使用中性分0.5。",
        "方向处理 → 逐列升序平均秩 → 归一化加权 → 得分降序排名 → 用得分升序经验概率计算probit。",
        "采用项目归一秩加权规则，不冒称传统RSR；分档是样本内相对评价，全部同分时统一记中。",
        "效益值10、20、30的秩为1、2、3，归一秩得分0、0.5、1；全部相等时都得0.5。",
        source(
            "SciPy · rankdata",
            "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.rankdata.html",
            "Ascending average ranks and tied observations; normalized-rank rule is local evaluate.rsr",
        ),
    )

    add(
        "eval.dea",
        "下式为投入导向 CCR/CRS 包络；VRS 增加 Σλ=1，产出导向目标不同。",
        r"\min_{\theta,\lambda}\theta,\quad X\lambda\le\theta x_o,\quad Y\lambda\ge y_o,\quad\lambda\ge0",
        "在不减少产出的条件下衡量投入可同比例压缩多少。",
        r"$o$ 为被评价单元；$X,Y$ 为投入/产出矩阵；$\lambda$ 为参照组合权重。",
        "核对正投入产出 → 每单元解线性规划 → 看效率与松弛；输出导向最大化 φ、约束 Yλ≥φyo。",
        "需可比决策单元与足够样本；CRS/VRS 的规模报酬假设不同；效率为相对样本边界，不是绝对生产率。",
        "两单元产出都1、投入分别2和1；CRS投入导向前者 θ=0.5。",
        source(
            "Charnes, Cooper & Rhodes (1978)",
            "https://doi.org/10.1016/0377-2217(78)90138-8",
            "CCR efficiency linear program",
        ),
    )

    add(
        "eval.fuzzy",
        "隶属函数 triangle/trapezoid/gaussian；weighted/maxmin/average 运算不同。",
        r"b_k=\sum_j w_jr_{jk}\quad\text{(weighted)},\qquad b_k=\max_j\min(w_j,r_{jk})\quad\text{(maxmin)}",
        "把各指标对等级的隶属度合成评价向量。",
        r"$R=(r_{jk})$ 为隶属矩阵；$w$ 为权重；$b_k$ 为综合等级隶属度。",
        "设等级与隶属函数 → 统一方向 → 构 R → 按 operator 合成 → 需要时用等级分数解模糊。",
        "隶属度不是随机概率；maxmin 结果不必和为1；主观等级/边界需说明。",
        "w=(0.4,0.6)、两指标好等级隶属度0.8、0.5，加权结果0.62，maxmin结果0.5。",
        source(
            "Zadeh (1965) · Fuzzy sets",
            "https://doi.org/10.1016/S0019-9958(65)90241-X",
            "Membership, max-min operations; weighted composition is the local evaluation variant",
        ),
    )

    add(
        "eval.grey",
        "灰色关联系数；min_baseline=sample 或 zero 改最小差基准。",
        r"\xi_{ij}=\frac{\Delta_{min}+\rho\Delta_{max}}{\Delta_{ij}+\rho\Delta_{max}},\quad\Delta_{ij}=|z_{ij}-z_{0j}|,\quad\Gamma_i=\sum_jw_j\xi_{ij}",
        "比较各对象与参考序列的逐指标接近程度。",
        r"$z_0$ 为参考，$\rho$ 为分辨系数；最小/最大差在约定的全差矩阵取值。",
        "同向归一化 → 选参考 → 算差 → 关联系数 → 加权关联度。",
        "参考与归一化影响排序；关联度非 Pearson 相关，也不表示因果；全差为0需保护。",
        "Δmin=0、Δmax=2、ρ=0.5、某差=1，则关联系数=1/2。",
        source(
            "Deng · Grey systems",
            "https://doi.org/10.1016/S0167-6911(82)80025-X",
            "Grey relational systems; coefficient conventions specified by local evaluate.grey",
        ),
    )
