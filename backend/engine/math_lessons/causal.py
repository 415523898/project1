"""Reviewed causal teaching declarations; examples are invented, never results."""

from engine.math_sources import DESIGN, DID, source


def populate(add):
    add(
        "causal.did",
        "经典两组两期 DID；协变量扩展不自动解决错位处理时点问题。",
        r"\tau=(\bar Y_{T,post}-\bar Y_{T,pre})-(\bar Y_{C,post}-\bar Y_{C,pre})",
        "用对照组变化扣除共同时间变化。",
        r"$T,C$ 为处理/对照，pre/post 为前/后；$\tau$ 为处理组平均处理效应的识别量。",
        "定义组与期 → 四均值或回归 Y=α+βT+γPost+τT·Post+Xδ+u → 合理聚类标准误。",
        "无提前反应、平行的未处理趋势、稳定组构成、无溢出；前趋势未显著不能证明平行；多期 TWFE 异质效应需专门方法。",
        "处理组10→15，对照组8→10，DID=(15−10)−(10−8)=3。",
        DID,
    )

    add(
        "causal.psm",
        "倾向得分匹配，nearest/radius/kernel/stratify 权重不同。",
        r"e(x)=P(D=1\mid X=x),\quad\widehat{ATT}=\frac1{n_T}\sum_{i:D_i=1}\left[Y_i-\sum_{j:D_j=0}w_{ij}Y_j\right]",
        "在观测协变量相近的对象间比较结果。",
        r"$D$ 为处理，$w_{ij}$ 是每个处理对象的对照权重，通常和为1。",
        "仅用处理前协变量估 e → 检查共同支持 → 匹配 → 平衡诊断 → 报告匹配样本与效应。",
        "需要无未测混杂、重叠与一致性；匹配无法修复未观测混杂；不能用处理后变量匹配。",
        "一个处理对象结果8，两个等权匹配对照为4、6，则该对象差为3。",
        source(
            "Rosenbaum & Rubin (1983)",
            "https://doi.org/10.1093/biomet/70.1.41",
            "Propensity score balancing and strong ignorability",
        ),
    )

    add(
        "causal.psmdid",
        "先匹配再比较前后变化，ATT 针对匹配后可比较人群。",
        r"\widehat\tau=\frac1{n_T}\sum_{i:D_i=1}\left[\Delta Y_i-\sum_{j:D_j=0}w_{ij}\Delta Y_j\right]",
        "把匹配权重用于 DID 的变化差。",
        r"$\Delta Y=Y_{post}-Y_{pre}$，$w_{ij}$ 为基于处理前协变量的匹配权重。",
        "估倾向得分 → 匹配和平衡 → 计算变化/加权 DID → 用合适标准误。",
        "仍需条件平行趋势、重叠、无提前反应；匹配不自动消除时间变化混杂。",
        "处理变化5，对照加权变化2，PSM-DID=3。",
        DID,
        source(
            "Heckman, Ichimura & Todd (1997)",
            "https://doi.org/10.2307/2171882",
            "Conditional difference in differences and matching",
        ),
    )

    add(
        "causal.rd",
        "当前为 sharp 局部多项式断点；不是 fuzzy RD 的比率估计。",
        r"\tau=\lim_{x\downarrow c}E[Y\mid X=x]-\lim_{x\uparrow c}E[Y\mid X=x]",
        "比较刚过阈值与刚低于阈值的局部结果差。",
        r"$X$ 为运行变量、$c$ 为断点；右极限减左极限。",
        "核对阈值处理规则 → 选带宽/核 → 两侧局部拟合 → 截距差 → 敏感性与操纵检查。",
        "阈值附近潜在结果连续、无精确操纵；效应仅局部；若处理概率非0→1跳变需 fuzzy RD 除以处理概率跳跃。",
        "阈值处右预测12、左预测10，sharp RD 效应2。",
        source(
            "Cunningham · Regression discontinuity",
            "https://mixtape.scunning.com/06-regression_discontinuity",
            "Sharp and fuzzy designs; continuity",
        ),
    )

    add(
        "causal.heckman",
        "下式为经典 probit 选择的两步法；logit 选择修正不是同一正态逆 Mills 比。",
        r"P(S=1\mid z)=\Phi(z^\top\gamma),\quad\lambda(z)=\frac{\phi(z^\top\gamma)}{\Phi(z^\top\gamma)},\quad E[Y\mid S=1,x,z]=x^\top\beta+\rho\sigma\lambda(z)",
        "对因选择而可见的结果样本加入选择修正项。",
        r"$S$ 为可观测指示；$z$ 为选择解释变量；$\rho$ 为两方程误差相关。",
        "全部样本估选择 → 计算选中者修正项 → 结果回归；MLE 则联合最大似然。当前选 logit 时按实现的替代修正规则解读。",
        "需排除限制等识别依据及误差分布假设；逆 Mills 比只对应正态 probit；结果不稳需报告。",
        "probit 指数0时 λ=φ(0)/Φ(0)≈0.7979；ρσ=2 时修正项≈1.5958。",
        source(
            "Heckman (1979) · Sample selection bias",
            "https://doi.org/10.2307/1912352",
            "Two-step normal selection correction",
        ),
    )

    add(
        "causal.placebo",
        "处理组置换或处理期移动的安慰剂；当前代码使用不加1的经验尾部比例。",
        r"\hat p=\frac1B\sum_{b=1}^B\mathbf1(|\hat\tau_b|\ge|\hat\tau_{obs}|)",
        "将真实统计量和伪处理下统计量比较，检查设计是否容易产生假信号。",
        r"$B$ 为重抽次数，$\hat\tau_b$ 为伪处理效应；当前实现可得0，不应把有限模拟的0解释为严格零概率；加1校正是另一个约定。",
        "保留合理交换结构 → 伪处理 → 重估同模型 → 对比效应分布；移动时点与随机置换不是同一零分布。",
        "需要适当交换性/随机化设计；一般观察数据的置换不能证明因果，安慰剂通过也不能证明识别假设。",
        "B=20 有2次至少一样极端，当前输出 p=2/20=0.1；若采用加1约定则为3/21。",
        source(
            "Phipson & Smyth (2010)",
            "https://doi.org/10.2202/1544-6115.1585",
            "Permutation p-values should never be zero",
        ),
    )

    add(
        "design.factorial",
        "全因子设计及其主效应/交互回归。",
        r"N=\prod_{j=1}^k L_j,\qquad y=\beta_0+\sum_j\beta_jx_j+\sum_{j<l}\beta_{jl}x_jx_l+\epsilon",
        "覆盖各因子所有水平组合，分离主效应和交互。",
        r"$L_j$ 为因子 j 的水平数；$N$ 为不含重复的运行数；编码 $x_j$ 与原单位不同。",
        "确定因子水平 → 生成笛卡尔积 → 随机化/重复 → 拟合主效应与交互。",
        "试验顺序和误差独立性重要；无重复的饱和模型没有纯误差自由度。",
        "3因子各2水平，组合数2³=8；每组合重复2次需16次。",
        DESIGN,
    )

    add(
        "design.orthogonal",
        "正交/混合水平设计；实际构造的平衡与正交性需检查，不是任意行数都存在标准正交表。",
        r"X^\top X\ \text{is diagonal (orthogonal coded columns)}",
        "编码列互不相关时，主效应估计可分开。",
        r"$X$ 为中心化/正交对比编码的设计矩阵；含截距时其余列和需为0。",
        "确定水平/运行数 → 选正交表或当前构造 → 检查列平衡与混杂 → 随机化。",
        "正交不是无交互；分数设计会混杂效应；混合水平不能一律用±1编码。",
        "两因子四运行 [−1,−1]、[−1,1]、[1,−1]、[1,1]，两列内积0。",
        DESIGN,
    )

    add(
        "design.uniform",
        "均匀设计 lattice 或 Halton，目标是覆盖空间，不保证正交。",
        r"u_{ij}=\varphi_{b_j}(i)\quad\text{(Halton)}",
        "用不同素数基的反根序列填充单位超立方体。",
        r"$b_j$ 为互异素数，$\varphi_b$ 把整数的 b 进制数字反向放到小数位。",
        "生成 lattice/Halton 点 → 映射因子水平 → 按 centered/wrap L2 discrepancy 评价 → 随机化/重复。",
        "不同构造不能套同一生成式；离散化可能重复点；空间均匀不等于统计独立或最优因果设计。",
        "二进制 1、10、11 的反根为0.5、0.25、0.75。",
        source(
            "SciPy · Halton",
            "https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Halton.html",
            "Van der Corput sequence in prime bases",
        ),
    )

    add(
        "design.rsm",
        "线性或二阶响应面，以下为二阶。",
        r"\hat y=\beta_0+\sum_j\beta_jx_j+\sum_j\beta_{jj}x_j^2+\sum_{j<l}\beta_{jl}x_jx_l",
        "用低阶多项式近似局部响应并在约束内优化。",
        r"$x_j$ 为编码因子；$\beta_{jj}$ 为曲率；$\beta_{jl}$ 为交互。",
        "设计实验 → 拟合 → 残差/失拟诊断 → 在范围内搜索最优 → 新实验确认。",
        "是局部近似；求出的极值可能在边界或为鞍点，不能外推全局最优。",
        "ŷ=5−(x−1)²，允许 x∈[0,2]，最优 x=1、ŷ=5。",
        DESIGN,
    )

    add(
        "design.ccd",
        "中心复合设计；rotatable/orthogonal/face 使用不同 α。",
        r"N=N_f+2k+n_0,\qquad\alpha=N_f^{1/4}\ \text{(rotatable full factorial core)}",
        "因子核心、轴点和中心点共同支持二阶模型。",
        r"$k$ 为因子数，$N_f$ 为因子核心运行数，$n_0$ 为中心次数；$\alpha$ 为轴点半径。",
        "生成因子核心 → 加每轴±α → 加中心/区组/重复 → 检查可行范围。",
        "可旋转 α 仅对应相应核心与假设；面心 α=1；不能把编码轴点当原单位。",
        "k=2、Nf=4、n0=1，N=9，可旋转 α=√2。",
        DESIGN,
    )

    add(
        "design.boxbehnken",
        "经典三水平 Box-Behnken 无轴点；非 classic 半径模式是项目扩展。",
        r"N=2k(k-1)+n_0\quad(k\ge3,\ \text{classic pairwise construction})",
        "每次两个因子在±1，其余为0，并加入中心。",
        r"$k$ 为因子数，$n_0$ 为中心运行数。",
        "枚举因子对 → 四种±组合 → 其余置0 → 加中心 → 随机化。",
        "式子对应当前成对构造，不概括所有高维压缩设计表；扩展半径会改变几何性质；不可宣称有 CCD 轴点。",
        "k=3、n0=3，N=12+3=15，例如 (1,−1,0) 是一运行。",
        DESIGN,
    )
