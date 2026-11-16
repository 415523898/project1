"""Reviewed machine teaching declarations; examples are invented, never results."""

from engine.math_sources import ENSEMBLE, sklearn, source


def populate(add):
    add(
        "ml.kmeans",
        "欧氏 KMeans，Lloyd/Elkan 求解相同平方距离目标。",
        r"\min_{C,\mu}\sum_{k=1}^K\sum_{i\in C_k}\|x_i-\mu_k\|_2^2",
        "让每簇围绕自己的均值尽量紧凑。",
        r"$C_k$ 为簇，$\mu_k$ 为中心，$K$ 为簇数。",
        "初始化中心 → 分配最近中心 → 更新均值 → 多次初始化择优。",
        "尺度敏感；局部最优；偏好近球形簇，编号无大小意义。",
        "点 [0,2,8,10] 分两簇中心1、9，总平方距离4。",
        sklearn("clustering#k-means", "K-means inertia"),
    )

    add(
        "ml.hierarchical",
        "凝聚层次聚类；Ward 为默认且需欧氏距离。",
        r"\Delta(A,B)=\frac{n_An_B}{n_A+n_B}\|\mu_A-\mu_B\|^2",
        "上式是 Ward 合并造成的簇内平方和增量，非所有 linkage 的距离定义。",
        r"$n_A,n_B$ 为簇大小，$\mu_A,\mu_B$ 为簇均值。",
        "各点为一簇 → 按 linkage 合并 → 切树。single/complete/average 用最小/最大/平均成对距离；SciPy Ward 输出距离还可能使用平方根缩放。",
        "Ward 不可任意搭配非欧氏距离；树状顺序不是时间或因果关系。",
        "两个单点0、2，Ward 平方和增量=2；并非直接把它当所有库的树高。",
        source(
            "SciPy · linkage",
            "https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html",
            "Ward, single, complete, average linkage definitions",
        ),
    )

    add(
        "ml.dbscan",
        "密度连通聚类，含核心点、边界点与噪声。",
        r"N_\varepsilon(x)=\{y:d(x,y)\le\varepsilon\},\quad |N_\varepsilon(x)|\ge m",
        "邻域足够密的点为核心点，核心点连通扩展成簇。",
        r"$\varepsilon$ 为 eps，$m$ 为 min_samples；sklearn 邻域计数包含自身。",
        "按 metric 算邻域 → 标核心 → 扩展密度可达点 → 其余标噪声。",
        "对尺度和 eps 敏感；不同密度簇难用一组阈值；噪声标签 −1 不代表必定错误数据。",
        "一维0、0.1、5，eps=0.2、m=2，前两点成簇，5为噪声。",
        sklearn("clustering#dbscan", "DBSCAN core samples"),
    )

    add(
        "ml.fcm",
        "模糊 C 均值，m>1；每点隶属度和为1。",
        r"J_m=\sum_i\sum_k u_{ik}^m\|x_i-c_k\|^2,\quad c_k=\frac{\sum_i u_{ik}^m x_i}{\sum_i u_{ik}^m}",
        "允许一个样本部分属于多个簇。",
        r"$u_{ik}\ge0,\sum_k u_{ik}=1$；$m$ 为模糊指数；$c_k$ 为中心。",
        "初始化隶属度/中心 → 按距离更新 u → 按加权均值更新中心 → 迭代。",
        "需处理零距离与零权重；隶属度不是经过概率校准的类别概率。",
        "点0、2对某簇的 u 都为0.5、m=2，中心为1。",
        source(
            "Bezdek et al. (1984) · FCM",
            "https://doi.org/10.1016/0098-3004(84)90020-7",
            "Fuzzy c-means objective and updates",
        ),
    )

    add(
        "ml.random_forest",
        "sklearn 分类平均叶概率后取 argmax；回归平均树预测。",
        r"\hat p_k(x)=\frac1B\sum_{b=1}^B p_{bk}(x),\quad\hat y_{clf}=\arg\max_k\hat p_k(x),\quad\hat y_{reg}=\frac1B\sum_b T_b(x)",
        "用重采样与随机特征减少树之间的相关性，再汇总预测。",
        r"$B$ 为树数，$p_{bk}$ 为第 b 树对类 k 的叶概率，$T_b$ 为回归预测。",
        "从训练集 bootstrap → 每节点随机选特征并按 criterion 分裂 → 汇总概率/预测 → 同一测试集评价。",
        "不同任务的 criterion 不通用；特征重要性有偏，不能作因果解释；sklearn 不是简单多数硬投票。",
        "两棵树对正类概率0.9、0.2，平均0.55，二分类预测正类；回归预测2、4则均值3。",
        ENSEMBLE,
    )

    add(
        "ml.xgboost",
        "加法树及二阶目标近似；具体分类/回归损失由任务决定。",
        r"\mathcal L^{(t)}\approx\sum_i[g_if_t(x_i)+\tfrac12h_if_t(x_i)^2]+\gamma T+\tfrac\lambda2\sum_jw_j^2",
        "用损失一二阶导数选择新树并惩罚复杂度。",
        r"$g_i,h_i$ 为当前损失导数，$T$ 为叶数，$w_j$ 为叶权，$\gamma,\lambda$ 为惩罚。",
        "初始化 → 计算梯度/Hessian → 建树 → 以 learning_rate 加入预测 → 验证。",
        "是单轮近似目标；不能把分类梯度当平方误差残差；gain 不代表因果效应。",
        "某叶 G=−4、H=3、λ=1，未乘学习率的最佳叶权 −G/(H+λ)=1。",
        source(
            "XGBoost · Model",
            "https://xgboost.readthedocs.io/en/stable/tutorials/model.html",
            "Regularized objective; Taylor expansion; leaf weights",
        ),
    )

    add(
        "ml.lightgbm",
        "梯度提升树，直方图与叶优先生长；GOSS/EFB 是可选优化而非每次必启用。",
        r"F_t(x)=F_{t-1}(x)+\eta f_t(x)",
        "逐轮拟合改善当前损失的树，用叶数等参数控制复杂度。",
        r"$F_t$ 为累计预测分数，$f_t$ 为新树，$\eta$ 为学习率。",
        "按任务选损失 → 量化直方图 → 选增益最大叶分裂 → 加入新树 → 验证。",
        "叶优先可能过拟合小数据；二分类累计分数需经 sigmoid 才是概率。",
        "旧分数1、新树输出0.5、η=0.1，新分数1.05。",
        source(
            "LightGBM · Features",
            "https://lightgbm.readthedocs.io/en/stable/Features.html",
            "Histogram based algorithms; leaf-wise growth",
        ),
    )

    add(
        "ml.adaboost",
        "分类与回归 AdaBoost 不同；下式仅解释经典二分类 AdaBoost，回归分支为 AdaBoost.R2。",
        r"\alpha_t=\tfrac12\log\frac{1-e_t}{e_t},\quad w_i'\propto w_i\exp[-\alpha_ty_ih_t(x_i)]",
        "增加难分样本权重，再加权组合弱学习器。",
        r"$y_i,h_t\in\{-1,1\}$，$e_t$ 为加权错误率；多类 SAMME 的系数改为 log((1−e)/e)+log(K−1)。",
        "初始化等权 → 拟合弱树 → 估计错误 → 更新样本权重 → 集成。回归按所选 linear/square/exponential 相对误差更新，预测为加权中位数。",
        "二分类式不能直接套到多类或回归；噪声点可能被反复放大；实际系数与 learning_rate/版本实现有关。",
        "经典二分类 et=0.25，α=0.5ln3≈0.5493，误分点相对正确点权重倍率3。",
        ENSEMBLE,
    )

    add(
        "ml.gbdt",
        "梯度提升；默认具体损失取决于分类/回归。",
        r"r_{it}=-\left.\frac{\partial\ell(y_i,F)}{\partial F}\right|_{F=F_{t-1}(x_i)},\quad F_t=F_{t-1}+\eta f_t",
        "新树逼近当前损失的负梯度。",
        r"$\ell$ 为损失，$r_{it}$ 为伪残差，$\eta$ 为学习率。",
        "初始化 → 计算负梯度 → 拟合树并更新叶值 → 缩步相加。",
        "只有平方误差下负梯度与普通残差成比例；分类输出分数要转换为概率。",
        "平方误差 ℓ=(y−F)²/2，y=3、F=1，负梯度2。",
        ENSEMBLE,
    )

    add(
        "ml.svm",
        "分类软间隔式；回归使用 ε 不敏感 SVR。",
        r"\min_{w,b,\xi}\tfrac12\|w\|^2+C\sum_i\xi_i,\quad y_i(w^\top\phi(x_i)+b)\ge1-\xi_i,\quad\xi_i\ge0",
        "在大间隔与误分类惩罚之间折中。",
        r"$C$ 为惩罚，$\phi$ 为核特征映射，$y_i=\pm1$；SVR 损失为 $\max(0,|y-f|-\varepsilon)$。",
        "缩放 → 选 kernel/C/gamma → 优化支持向量 → 分类或回归。",
        "核参数与尺度耦合；决策分数不是概率；分类式不描述 SVR 的 ε 管道。",
        "某分类样本间隔0.7，则所需松弛至少0.3；SVR 误差0.2、ε=0.1时损失0.1。",
        sklearn("svm", "SVC and SVR mathematical formulation"),
    )

    add(
        "ml.knn",
        "分类加权投票、回归加权均值；uniform/distance 两种权重。",
        r"\hat y_{reg}=\frac{\sum_{i\in N_k(x)}w_iy_i}{\sum_{i\in N_k(x)}w_i},\quad\hat y_{clf}=\arg\max_c\sum_{i\in N_k(x)}w_i\mathbf1(y_i=c)",
        "从局部相似观测推断目标。",
        r"$N_k$ 为最近 k 个训练点，uniform 时 $w_i=1$；distance 按距离倒数并保护零距离。",
        "训练集缩放 → 选度量 → 找近邻 → 按任务汇总。",
        "高维距离会退化；类别编号不能用回归均值冒充分类投票。",
        "三近邻回归目标2、4、6等权均值4；分类 A,A,B 投 A。",
        sklearn("neighbors", "Nearest neighbors classification and regression"),
    )

    add(
        "ml.nb",
        "Gaussian/Multinomial/Bernoulli 使用不同类条件分布。",
        r"P(c\mid x)\propto P(c)\prod_jP(x_j\mid c)",
        "在给定类别条件独立假设下组合特征证据。",
        r"$c$ 为类别，$P(c)$ 为先验；Gaussian 连续正态，Multinomial 计数，Bernoulli 二元。",
        "估计类先验与分布参数 → 用对数相加避免下溢 → 比较后验得分。",
        "条件独立通常近似；Multinomial 要求非负；平滑约定影响零频数。",
        "两类先验均0.5，某二元特征出现概率0.8、0.2，则见该特征后正类后验0.8。",
        sklearn("naive_bayes", "Naive Bayes variants"),
    )

    add(
        "ml.mlp",
        "多层前馈网络；分类输出概率，回归通常线性输出。",
        r"h^{(l)}=\sigma(W^{(l)}h^{(l-1)}+b^{(l)}),\qquad\min_\theta\frac1n\sum_i\ell(y_i,f_\theta(x_i))+\lambda R(\theta)",
        "通过多层非线性映射学习预测关系。",
        r"$h^{(0)}=x$，$W,b$ 为权重偏置，$\sigma$ 为 relu/tanh/logistic。",
        "训练集缩放 → 前向计算 → 反向求梯度 → 用 adam/sgd/lbfgs 优化 → 验证收敛。",
        "损失与输出取决于任务；正则系数的样本归一化以具体库为准；随机初始化影响解。",
        "单神经元 ReLU，w=2、b=−1、x=1，输出 max(0,1)=1。",
        sklearn("neural_networks_supervised", "Multilayer perceptron and regularization"),
    )

    add(
        "ml.rbf",
        "RBF 特征 + 输出层；中心可用 KMeans 或随机初始化。",
        r"\phi_j(x)=\exp(-\gamma\|x-c_j\|^2),\quad f(x)=b+\sum_jw_j\phi_j(x)",
        "用离中心的距离构造局部响应再拟合输出。",
        r"$c_j$ 为中心，$\gamma>0$ 为宽度倒数尺度，$w_j,b$ 为输出参数。",
        "缩放 → 选中心 → 算 RBF 矩阵 → 拟合输出层 → 按任务预测。",
        "gamma 与尺度相关；分类输出层与回归不同，RBF 响应本身不是概率。",
        "x=1、中心0、γ=1时响应 e^(−1)≈0.3679。",
        sklearn("metrics#radial-basis-function-rbf-kernel", "RBF kernel"),
    )

    add(
        "ml.trees",
        "实际实现 sklearn CART 二叉树，支持基尼或熵不纯度；不以 CART 冒充 C4.5、CHAID 或 QUEST。",
        r"\Delta I=I(P)-\frac{n_L}{n_P}I(L)-\frac{n_R}{n_P}I(R),\quad H=-\sum_kp_k\log p_k,\quad G=1-\sum_kp_k^2",
        "选择带来最大不纯度下降的切分。",
        r"$P,L,R$ 为父/左右子节点，$p_k$ 为节点类别比例；$I$ 可为熵或 Gini。",
        "枚举候选切分 → 算不纯度下降 → 按深度/叶样本限制递归 → 剪枝。",
        "原 C4.5 的增益率、CHAID 的卡方合并、QUEST 的选择机制并未由当前实现完整提供；不能把标签当算法保证。",
        "父节点各半两类，Gini=0.5；切成两个纯叶时下降0.5。",
        sklearn("tree", "Decision tree criteria and mathematical formulation"),
    )

    add(
        "ml.lda_qda",
        "LDA 共享协方差，QDA 每类协方差；此处 LDA 是判别分析，不是主题模型。",
        r"\delta_k^{LDA}=x^\top\Sigma^{-1}\mu_k-\tfrac12\mu_k^\top\Sigma^{-1}\mu_k+\log\pi_k",
        "用高斯类条件模型推导判别函数。",
        r"$\mu_k,\pi_k$ 为类均值/先验；LDA 共用 $\Sigma$；QDA 用 $\Sigma_k$。",
        "估计类均值/协方差 → 算判别分数 → 最大者分类。QDA 分数=−log|Σk|/2−(x−μk)ᵀΣk⁻¹(x−μk)/2+logπk。",
        "协方差须可估且稳定；LDA 边界线性、QDA 二次；小样本 QDA 易病态。",
        "等先验、一维共同方差1、类均值0和2，LDA 边界为1。",
        sklearn("lda_qda", "LDA and QDA mathematical formulation"),
    )
