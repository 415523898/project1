"""Reviewed prepare teaching declarations; examples are invented, never results."""

from engine.math_sources import PANDAS, PCA, PREPROCESS, scipy, sklearn, source


def populate(add):
    add(
        "prep.outliers",
        "默认 IQR 检测；另有 z-score 与 MAD，默认 report 不删除样本。",
        r"IQR=Q_3-Q_1,\quad [L,U]=[Q_1-kIQR,Q_3+kIQR]",
        "把落在四分位区间扩展边界之外的观测标为异常候选。",
        r"$Q_1,Q_3$ 为四分位数；$k$ 为倍数（通常 1.5）；$L,U$ 为下上界。",
        "先选列并估计边界，再标记；report、clip、winsorize、drop 分别报告、截断、缩尾或删行。z-score 比较标准分数，MAD 比较中位数绝对偏差，不能共用 IQR 阈值。",
        "极端值可能是真实信号；不同分位数插值约定会改变边界。预测任务只从训练集估计阈值。",
        "Q1=2、Q3=6、k=1.5，IQR=4，边界为 [-4,12]；13 被标记。",
        scipy("iqr"),
    )

    add(
        "prep.missing",
        "默认中位数填补；均值、众数、插值、前向填充、KNN、迭代和删除为不同规则。",
        r"\tilde x_i=\begin{cases}x_i,&x_i\text{ observed}\\m,&x_i\text{ missing}\end{cases}",
        "这是中位数填补的分段规则，不是所有缺失处理的统一公式。",
        r"$x_i$ 为原观测；$m$ 为拟合样本的非缺失中位数；$\tilde x_i$ 为填补后数值。",
        "先报告缺失比例与机制，再选策略。KNN 从邻居估计，迭代填补逐列建模；时序插值与前向填充依赖排序。",
        "填补不能消除非随机缺失偏差；训练/测试隔离，目标标签不随意填补；整列缺失没有可估计的中位数。",
        "[1,缺失,5] 的非缺失中位数为 3，得到 [1,3,5]。",
        PANDAS,
        sklearn("impute", "Univariate versus multivariate imputation"),
    )

    add(
        "prep.duplicates",
        "按选定键、文本归一化和 keep 规则查重；默认 report。没有统一数学目标函数。",
        "",
        "重复指选定键相等，不等于所有业务含义相同。",
        "键是参与比较的列；keep 决定标记口径；normalize 决定是否去空格、统一大小写。",
        "选择键 → 文本归一化 → 将缺失值按查重规则比较 → 标记重复组 → 报告/删行/增添标记。drop时keep=first/last保留首/末条，keep=none对应pandas keep=False，删除重复组全部成员。",
        "先核对业务主键与重复测量；默认特征键未必包含目标、分组和时间列。",
        "键为城市，trim_lower 后 ' A ' 与 'a' 属于同组；keep=first 将后者标记为重复。",
        source(
            "pandas · duplicated",
            "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.duplicated.html",
            "subset and keep; compare local drop behavior",
        ),
    )

    add(
        "prep.encoding",
        "onehot / ordinal / target；target 可取组内均值或中位数。",
        r"z_{ic}=\mathbf1(x_i=c),\qquad e(c)=\frac{1}{n_c}\sum_{i:x_i=c}y_i",
        "左式把类别展开成指示列；右式是均值目标编码，两者不可混同。",
        r"$c$ 为类别；$n_c$ 为该类别拟合样本数；$y_i$ 为目标；$z_{ic}$ 为 0/1 指示值。",
        "先确定类别字典与未知类别策略；ordinal 按指定顺序映射整数；target 仅在训练数据上估计。",
        "无序类别的整数编码不代表距离；目标编码若用测试标签或训练样本自身目标会泄漏，需要折外估计等保护。",
        "A 的两个训练目标为 2、4，均值编码为 3；onehot 的 A 行则为 [1,0]（另一个类别为 B）。",
        PREPROCESS,
    )

    add(
        "prep.derive",
        "interaction、ratio、polynomial、bin 各自构造不同特征。",
        r"z=x_1x_2,\quad r=\frac{x_1}{x_2},\quad p=x^d",
        "交互刻画乘积关系，比例刻画相对量，多项式允许弯曲关系；分箱按边界离散化。",
        r"$x_1,x_2$ 为原特征；$d$ 为次数；$z,r,p$ 为派生特征。",
        "选列与规则 → 检查零分母及单位 → 构造特征；分箱可用等宽、分位数或 KMeans 边界。",
        "避免未来信息、目标泄漏和不合理量纲；高次多项式会放大极值。",
        "x1=2、x2=4，交互=8、比例=0.5；x1 的平方=4。",
        PREPROCESS,
    )

    add(
        "prep.winsorize",
        "默认分位数缩尾；支持 IQR、zscore、MAD 边界和单侧处理。",
        r"x_i'=\min(U,\max(L,x_i))",
        "把边界外数值替换为边界，保留行数。",
        r"$L,U$ 为当前策略估计的下上界；$x_i'$ 为截断后的观测。",
        "选列 → 从拟合样本估计边界 → 按 side 只处理下侧、上侧或双侧 → 对比受影响记录。",
        "分位数缩尾会改变尾部分布；不等同删掉离群样本。",
        "边界 [2,8]，原值 [1,5,10] 变为 [2,5,8]。",
        scipy("mstats.winsorize"),
    )

    add(
        "prep.transform",
        "Yeo-Johnson 默认；下式展示 Box-Cox 正数分支，Yeo-Johnson 另含负数分支。",
        r"T_\lambda(x)=\begin{cases}(x^\lambda-1)/\lambda,&\lambda\ne0\\\log x,&\lambda=0\end{cases}",
        "幂变换缓解偏态；不是保证正态的定理。",
        r"$x>0$ 为 Box-Cox 输入；$\lambda$ 为幂参数，通常用似然估计。",
        "检查定义域 → 估计 λ → 变换。Yeo-Johnson 对 x≥0 用 Box-Cox(x+1)，对 x<0 用负的 Box-Cox(1−x,2−λ)；log 与 sqrt 有各自定义域。",
        "不能把 Box-Cox 套在零或负数；比较结果时注明后续是否标准化。",
        "Box-Cox 的 λ=0、x=e 时输出 1；Yeo-Johnson 的 λ=1 时是恒等变换。",
        PREPROCESS,
        scipy("boxcox"),
        scipy("yeojohnson"),
    )

    add(
        "prep.balance",
        "默认报告；weights、随机过/欠采样、SMOTE 为不同策略。",
        r"w_c=\frac{n}{K n_c},\qquad x_{new}=x_i+u(x_{nn}-x_i),\quad u\in[0,1]",
        "左式为平衡类权重；右式仅是 SMOTE 的线性插值。",
        r"$n$ 为训练记录数，$K$ 为类别数，$n_c$ 为类别频数；$x_{nn}$ 为同类近邻。",
        "先划分数据 → 统计训练类别 → 按策略重采样或计算权重 → 在原始分布测试集评价。",
        "不要重采样测试集；SMOTE 需要足够同类近邻，不能直接把类别整数当连续坐标。",
        "80/20 的二分类，权重为 100/(2×80)=0.625 与 2.5；SMOTE 在 2 和 4 之间 u=0.5 生成 3。",
        source(
            "imbalanced-learn · Over-sampling",
            "https://imbalanced-learn.org/stable/over_sampling.html",
            "SMOTE: sample generation",
        ),
        source(
            "scikit-learn · compute_class_weight",
            "https://scikit-learn.org/stable/modules/generated/sklearn.utils.class_weight.compute_class_weight.html",
            "balanced heuristic",
        ),
    )

    add(
        "prep.scale",
        "默认 zscore（StandardScaler，总体式方差 ddof=0）；另有 minmax、robust、maxabs。",
        r"z_i=\frac{x_i-\mu}{\sigma},\quad\sigma^2=\frac1n\sum_i(x_i-\mu)^2;\qquad u_i=\frac{x_i-x_{min}}{x_{max}-x_{min}}",
        "统一尺度；右式为映射到 [0,1] 的 minmax。",
        r"$\mu,\sigma$ 为拟合样本均值与标准差；$n$ 为拟合样本数；$x_{min},x_{max}$ 为边界。",
        "只从训练集估计变换量 → 对验证/测试应用同一规则。robust 用中位数与 IQR，maxabs 除以最大绝对值；常数列需保护零分母。",
        "zscore 不等于样本标准差 ddof=1；尺度敏感模型受影响，树模型通常无需标准化。",
        "[2,4] 的 μ=3、σ=1，zscore 为 [-1,1]；minmax 为 [0,1]。",
        PREPROCESS,
    )

    add(
        "prep.pca",
        "先按 scale 参数变换；随后 PCA 中心化。主成分符号可整体翻转。",
        r"S=\frac{X_c^\top X_c}{n-1},\quad Sv_j=\lambda_jv_j,\quad Z=X_cV_k",
        "找到保留最大方差的正交投影，不使用目标标签。",
        r"$X_c$ 为 n×p 中心化矩阵；$v_j$ 为单位特征向量；$\lambda_j$ 为方差；$V_k$ 为前 k 列向量。",
        "拟合缩放 → 中心化 → SVD/特征分解 → 按解释方差选 k → 投影；白化还会再缩放得分。",
        "协方差分母是 n−1；scale=none 不做标准化但仍中心化；主成分大方差不保证预测价值。",
        r"中心化矩阵 $X_c=\begin{bmatrix}-1&-1\\1&1\end{bmatrix}$，$S=\begin{bmatrix}2&2\\2&2\end{bmatrix}$；第一轴 $(1,1)/\sqrt2$，方差 4、得分 $\pm\sqrt2$。",
        PCA,
    )

    add(
        "prep.tsne",
        "二维/低维可视化；Barnes-Hut 与 exact 是近似和精确优化路线。",
        r"KL(P\Vert Q)=\sum_{i\ne j}p_{ij}\log\frac{p_{ij}}{q_{ij}},\qquad q_{ij}\propto(1+\|z_i-z_j\|^2)^{-1}",
        "让低维邻居概率接近高维邻居概率，主要保留局部邻域。",
        r"$p_{ij}$ 为对称化高维相似概率，$q_{ij}$ 为低维概率，$z_i$ 为嵌入坐标。",
        "缩放 → 用困惑度确定邻域带宽 → 构造 P → 初始化 → 迭代降低 KL。",
        "坐标轴和全局簇间距离通常无解释；随机种子和困惑度会改变图，不是聚类显著性证据。",
        "某对点 p=0.2、q=0.1，则该项为 0.2 ln 2≈0.1386；总 KL 还需对全部有序点对求和。",
        sklearn("manifold#t-sne", "t-SNE objective and perplexity"),
    )

    add(
        "prep.spectral",
        "FFT 频谱；窗、去趋势、采样间隔及是否功率谱决定数值尺度。",
        r"X_k=\sum_{t=0}^{n-1}x_t e^{-2\pi\mathrm{i}kt/n},\quad f_k=\frac{k}{n\Delta t}",
        "把等间隔序列分解为不同频率的复数振幅。",
        r"$n$ 为长度，$\Delta t$ 为采样间隔，$k$ 为频率索引，$\mathrm{i}^2=-1$。",
        "按时间排序 → 去趋势/加窗 → FFT → 取正频率 → 根据幅度或功率约定找峰值。",
        "需要近似等间隔采样；功率、幅度、单边加倍与归一化不同，不能直接比较不同口径。",
        "[1,−1,1,−1]，Δt=1；k=2 的 FFT 值为 4，频率 0.5，表示每 2 个采样重复。",
        source(
            "SciPy · Fourier transforms",
            "https://docs.scipy.org/doc/scipy/tutorial/fft.html",
            "Discrete Fourier transforms; normalization",
        ),
    )
