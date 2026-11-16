"""Reviewed stats teaching declarations; examples are invented, never results."""

from engine.math_sources import PANDAS, scipy, sm, source


def populate(add):
    add(
        "describe.frequency",
        "默认排除缺失并按有效观测计频率；包含缺失时按全部记录计频率。",
        r"p_c=\frac{n_c}{\sum_j n_j}",
        "统计每一类占当前缺失口径下有效分母的比例。",
        r"$n_c$ 为类别 c 次数，$p_c$ 为频率；分母在类别筛选前确定。",
        "先决定是否包含缺失 → 统计各类别 → 除以对应总数 → 排序与筛选；加权频数需要另行声明权重。",
        "隐藏缺失时分母为非缺失数，包含缺失时分母为全部记录数；Top 或占比筛选后不重新归一化，真实类别与缺失标记分开。",
        "A,A,空值：隐藏缺失时 A 频数2、频率1；包含缺失时 A 频率2/3、空值频率1/3。",
        source(
            "pandas · value_counts",
            "https://pandas.pydata.org/docs/reference/api/pandas.Series.value_counts.html",
            "normalize and dropna",
        ),
    )

    add(
        "describe.stats",
        "默认显示样本标准差；总体模式仅改变标准差展示口径，均值t区间独立使用样本标准误。",
        r"\bar x=\frac1n\sum_i x_i,\quad s^2=\frac{\sum_i(x_i-\bar x)^2}{n-1},\quad\sigma_N^2=\frac{\sum_i(x_i-\bar x)^2}{n}",
        "均值描述中心，方差描述平方离散程度。",
        r"$n$ 为非缺失数；$s^2$ 为样本方差；$\sigma_N^2$ 为总体式方差。",
        "逐列去除缺失 → 算中心、分位数与离散量 → 明确标准差样本/总体模式 → 用样本标准误计算均值t区间。",
        "样本方差和均值t区间要求 n>1；t区间还需核对独立性与分布条件；标准差是方差开平方，有原量纲。",
        "[1,2,3] 均值 2；样本方差 1，总体式方差 2/3。",
        scipy("describe"),
        scipy("sem"),
        scipy("ttest_1samp"),
    )

    add(
        "describe.crosstab",
        "列联计数及行/列/总百分比。",
        r"p_{j\mid i}=\frac{n_{ij}}{\sum_j n_{ij}}",
        "展示两个类别变量的联合分布；此式仅对应行百分比。",
        r"$n_{ij}$ 为第 i 行第 j 列频数；分母为第 i 行总数。",
        "保留行类别并交叉计数 → 依 percent 选择分母 → 比较分布；列百分比改除列和，总百分比改除有效成对记录总数。",
        "交叉表本身不是独立性检验；结构零、缺失类别和样本权重需要单独处理。",
        "某行 [2,3]，行百分比 [40%,60%]。",
        source(
            "pandas · crosstab",
            "https://pandas.pydata.org/docs/reference/api/pandas.crosstab.html",
            "normalize",
        ),
    )

    add(
        "describe.aggregate",
        "按类别分组后，选择均值、求和、中位数、标准差、范围或非缺失计数等统计量。",
        r"\bar x_g=\frac1{n_g}\sum_{i\in g}x_i",
        "按分组分别汇总，不改变组内观测的定义。",
        r"$g$ 为组，$n_g$ 为该组非缺失数。",
        "选分组键 → 选统计量 → 分组计算；计数直接统计原列非缺失值，文本列也适用，空组计数为0。",
        "组均值直接平均通常不等于全体均值，应按组样本数加权；std/var 核对 ddof。",
        "A 组 [2,4] 均值 3；B 组 [9] 均值 9；全体均值 5。",
        source(
            "pandas · GroupBy",
            "https://pandas.pydata.org/docs/user_guide/groupby.html",
            "Aggregation",
        ),
    )

    add(
        "describe.explore",
        "探索是多步骤诊断，没有单一公式；相关类型可选 Pearson/Spearman/Kendall。",
        "",
        "先了解结构、分布、缺失、离群与变量关系，再决定正式模型。",
        "记录数、列类型、缺失比例、分位数、相关系数分别反映不同性质。",
        "查表结构 → 统计缺失与唯一值 → 看分布与散点 → 检查相关；保留观察和假设的区分。",
        "探索结果不能自动当成事先指定的显著性结论；相关不等于因果。",
        "10 行中 2 行缺失，缺失率 20%；这不说明应自动删列。",
        PANDAS,
        scipy("pearsonr"),
    )

    add(
        "describe.power",
        "t、proportion、anova 使用不同备择分布；下式是功效定义而非通用样本量闭式解。",
        r"1-\beta=P_{H_1}(\text{reject }H_0)",
        "在指定真实效应下检出该效应的概率。",
        r"$\alpha$ 为一类错误率，$\beta$ 为二类错误率；效应量、样本量和单双侧决定功效。",
        "确定检验类型与效应量 → 指定 α、样本量/目标功效 → 用相应分布数值求解。",
        "Cohen d、比例差与 ANOVA f 不能互换；事后用观测效应计算的功效不替代区间估计。",
        "功效 0.8 表示在给定备择假设下重复 100 次约有 80 次拒绝 H0，不是 H1 为真的概率 80%。",
        sm("stats#power-and-sample-size-calculations", "Power and sample size"),
    )

    add(
        "test.ttest",
        "独立样本默认需核对 variance；此处先列 Welch，再给单样本/配对/等方差口径。",
        r"t=\frac{\bar x-\bar y}{\sqrt{s_x^2/n_x+s_y^2/n_y}},\quad\nu=\frac{(s_x^2/n_x+s_y^2/n_y)^2}{(s_x^2/n_x)^2/(n_x-1)+(s_y^2/n_y)^2/(n_y-1)}",
        "用均值差相对标准误判断证据，Welch 不要求两组方差相等。",
        r"$s_x^2,s_y^2$ 使用各自 n−1 分母；$\nu$ 为 Welch-Satterthwaite 自由度。",
        "单样本 t=(均值−μ0)/(s/√n)；配对先算每对差值再做单样本检验；等方差用合并方差 sp²=[(nx−1)sx²+(ny−1)sy²]/(nx+ny−2)，自由度 nx+ny−2。最后按备择方向计算 p。",
        "独立检验要求组间独立；配对检验要求差值近似正态或样本充分。auto 的方差分支依代码诊断，不能直接视为 Welch。",
        "两组均值 5、3，样本方差均为 4，各 n=8，Welch 标准误=1，t=2，自由度14。",
        scipy("ttest_ind"),
        scipy("ttest_1samp"),
        scipy("ttest_rel"),
    )

    add(
        "test.anova",
        "下式仅为单因素独立同方差 ANOVA；多因素/ANCOVA/重复测量使用不同设计与误差项。",
        r"F=\frac{SS_B/(k-1)}{SS_W/(n-k)},\quad SS_B=\sum_gn_g(\bar x_g-\bar x)^2,\quad SS_W=\sum_g\sum_i(x_{gi}-\bar x_g)^2",
        "比较组间均值变化与组内随机变化。",
        r"$k$ 为组数，$n$ 为总样本量；$SS_B,SS_W$ 为组间、组内平方和。",
        "明确设计 → 拟合相应线性模型 → 选正确平方和/误差项 → F 检验 → 必要时做经校正的事后比较。",
        "独立、残差近似正态、方差齐性；重复测量还需考虑被试相关与球形性；显著不说明所有组都不同。",
        "k=3、n=9、SSB=12、SSW=6，F=(12/2)/(6/6)=6。",
        scipy("f_oneway"),
        sm("anova", "ANOVA; repeated measures ANOVA"),
    )

    add(
        "test.wilcoxon",
        "配对差值的 Wilcoxon 符号秩；零差值与并列秩按 zero_method 处理。",
        r"W^+=\sum_{d_i>0}\operatorname{rank}(|d_i|),\quad W^-=\sum_{d_i<0}\operatorname{rank}(|d_i|)",
        "同时使用差值方向和绝对差值的秩；双侧统计量常取两者较小值。",
        r"$d_i$ 为成对差；秩按绝对差排序，并列取平均秩。",
        "算配对差 → 处理零 → 排绝对值秩 → 分别求正负秩和 → 按单双侧与精确/渐近分布求 p。",
        "配对间独立；位置解释需差值分布对称，不是任意分布下的中位数检验。",
        "差为 [1,−2,3]，秩 1,2,3，W+=4、W−=2，双侧统计量 2。",
        scipy("wilcoxon"),
    )

    add(
        "test.mannwhitney",
        "两独立样本秩和；精确与渐近、并列校正为不同 p 值口径。",
        r"U_x=R_x-\frac{n_x(n_x+1)}2,\qquad U_y=n_xn_y-U_x",
        "比较一组取值相对另一组的排序优势。",
        r"$R_x$ 为合并排序后 x 组秩和；$n_x,n_y$ 为两组大小。",
        "合并排名 → 求组秩和 → 算 U → 按备择方向和 method 求 p。",
        "观测独立；只有分布形状等条件成立时才可主要解释为位置差；不能无条件称为中位数检验。",
        "x=[1,2]、y=[3,4]，Rx=3，Ux=0，Uy=4。",
        scipy("mannwhitneyu"),
    )

    add(
        "test.kruskal",
        "独立多组的 Kruskal-Wallis；下式未做并列秩校正。",
        r"H=\frac{12}{n(n+1)}\sum_g\frac{R_g^2}{n_g}-3(n+1)",
        "比较多组的合并秩分布。",
        r"$R_g$ 为第 g 组秩和；$n_g$ 为组大小；$n=\sum_g n_g$。",
        "合并排名 → 计算 H → 有并列时除以校正因子 → 参考 χ²(k−1) 或更合适的小样本方法。",
        "组间独立；分布形状不一致时不单纯反映中位数；显著后需校正的两两比较。",
        "两组 [1,2]、[3,4] 的秩和为3、7，H=2.4。",
        scipy("kruskal"),
    )

    add(
        "test.friedman",
        "同一被试/区组多条件的秩检验；可选 Iman-Davenport F 近似。",
        r"Q=\frac{12}{nk(k+1)}\sum_j R_j^2-3n(k+1)",
        "先在每个区组内部排序，再比较各条件秩和。",
        r"$n$ 为区组数，$k$ 为条件数，$R_j$ 为条件 j 的区组内秩和。",
        "每行排名 → 汇总列秩和 → 并列校正 → 选 χ² 或 F 近似；F=(n−1)Q/[n(k−1)−Q]。",
        "区组间独立、区组内配对完整；小样本 χ² 近似可能不准。",
        "n=2、k=3，两行秩均 [1,2,3]，列秩和 [2,4,6]，Q=4。",
        scipy("friedmanchisquare"),
    )

    add(
        "test.cochran",
        "同一对象 k 个二元条件的 Cochran Q。",
        r"Q=(k-1)\frac{k\sum_j C_j^2-T^2}{kT-\sum_i R_i^2}",
        "检验相关二元条件的成功率是否相同。",
        r"$C_j$ 为列成功数，$R_i$ 为行成功数，$T$ 为总成功数，$k$ 为条件数。",
        "核对 0/1 与配对 → 算行列和 → Q → χ²(k−1) 近似 → 必要时校正 McNemar 事后比较。",
        "对象间独立；全为一致响应时分母可为零，不能报告常规 Q。",
        "两对象响应 [1,0,0] 和 [1,1,0]，C=[2,1,0]、R=[1,2]、T=3，Q=3。",
        sm("generated/statsmodels.stats.contingency_tables.cochrans_q", "Cochran Q"),
    )

    add(
        "test.chi2",
        "下式为 Pearson 独立性 χ²、无连续性校正；另有 G 检验/Cressie-Read 等。",
        r"E_{ij}=\frac{R_iC_j}{n},\quad\chi^2=\sum_{ij}\frac{(O_{ij}-E_{ij})^2}{E_{ij}}",
        "比较独立假设下的期望频数与观测频数。",
        r"$O,E$ 为观测和期望；$R,C$ 为边际频数；自由度 (r−1)(c−1)。",
        "建频数表 → 算期望 → 按 statistic/correction 选统计量 → 渐近或 Monte Carlo 求 p。",
        "计数、独立抽样；期望频数太低时优先精确/模拟方法；2×2 Yates 校正会改变统计量。",
        "O=[[8,2],[2,8]]，E 全为5，无校正 χ²=7.2。",
        scipy("chi2_contingency"),
    )

    add(
        "test.gof",
        "单变量类别频数拟合优度；uniform 和拟合 normal 的期望构造不同。",
        r"\chi^2=\sum_{j=1}^k\frac{(O_j-np_j)^2}{np_j}",
        "检验观测类别比例是否符合指定分布。",
        r"$p_j$ 为零假设概率，$n$ 为总数，$k$ 为类别数。",
        "给定分箱/类别 → 估计或指定期望概率 → 核对总和 → 统计量 → 明确自由度扣除了几个估计参数。",
        "期望频数不可过小；已估参数时 df 通常为 k−1−参数数，小样本/数据驱动分箱须谨慎。",
        "骰子两类简例 O=[8,12]、p=[0.5,0.5]，χ²=0.8。",
        scipy("chisquare"),
    )

    add(
        "test.fisher",
        "2×2 固定边际的精确检验；sample 与 conditional 比值比估计不同。",
        r"P(A=a)=\frac{\binom{a+b}{a}\binom{c+d}{c}}{\binom{n}{a+c}},\quad OR_{sample}=\frac{ad}{bc}",
        "在零假设与固定边际下枚举可行表，不依赖大样本 χ² 近似。",
        r"表为 $\begin{bmatrix}a&b\\c&d\end{bmatrix}$；$n=a+b+c+d$。",
        "计算观测表概率 → 按备择方向加总同样或更极端的表；双侧 p 不是简单把单侧翻倍。",
        "抽样设计应符合条件分析；零单元会使样本 OR 为零/无穷，不应随意加0.5冒充原结果。",
        "表全为1时样本 OR=1；该表概率为 4/6，双侧 p=1。",
        scipy("fisher_exact"),
    )
