"""Reviewed domain teaching declarations; examples are invented, never results."""

from engine.math_sources import QUALITY, scipy, sklearn, sm, source


def populate(add):
    add(
        "domain.wordfreq",
        "分词/词元计数；中文切分、停用词、最短词长与 ngram 会改变词表。",
        r"tf(t)=\sum_d\operatorname{count}(t,d),\quad share(t)=\frac{tf(t)}{\sum_u tf(u)}",
        "统计词元出现次数，而非包含该词的文档数。",
        r"$t$ 为词元，$d$ 为文档；分母为全部计入词元总次数。",
        "选文本列 → 分词与过滤 → 计数 → 排序/展示 Top 词。",
        "分词策略决定计数含义；高频不一定重要；不能把词占比当受访者比例。",
        "文档 'a a b' 与 'b c'，a频数2、总词5、占比0.4。",
        sklearn("feature_extraction#text-feature-extraction", "Text tokenization and bag of words"),
    )

    add(
        "domain.tfidf",
        "sklearn 平滑 IDF 默认口径，之后按 norm 归一化；sublinear_tf 可改 TF。",
        r"idf(t)=\log\frac{1+N}{1+df(t)}+1,\quad v_{dt}=tf(t,d)\,idf(t)",
        "降低到处都出现的词的相对权重。",
        r"$N$ 为文档总数，$df(t)$ 为出现词 t 的文档数；$tf$ 为原计数或1+log计数。",
        "分词 → 建训练词表 → 算 TF/IDF → 按 L1/L2/none 归一；测试只用训练词表和 IDF。",
        "这是平滑且有+1的口径；未平滑、二值化和次线性 TF 会改变结果。",
        "N=3、df=1，idf=ln2+1≈1.6931；TF=2，归一前权重≈3.3863。",
        sklearn("feature_extraction#tfidf-term-weighting", "TF-IDF exact smoothed formula"),
    )

    add(
        "domain.sentiment",
        "当前词典命中法，非大模型情感理解；可选否定窗口翻转极性。",
        r"s=\begin{cases}(n_+-n_-)/(n_++n_-),&n_++n_->0\\0,&\text{otherwise}\end{cases}",
        "按正负词典命中比给出−1到1分数。",
        r"$n_+,n_-$ 为当前计数规则下的正负命中；默认是词典词是否出现在文本中。",
        "匹配词典 → 可选否定窗处理 → 求分数 → 以正/负/零标记；代表词频另算。",
        "不理解讽刺、领域语境与复杂否定；无命中返回0不证明语义中性。",
        "正命中3、负命中1，s=0.5；无命中s=0。",
        source(
            "Liu (2012) · Sentiment Analysis",
            "https://doi.org/10.2200/S00416ED1V01Y201204HLT016",
            "Lexicon based sentiment; exact normalized-hit rule belongs to local implementation",
        ),
    )

    add(
        "domain.lda",
        "Latent Dirichlet Allocation 主题模型，不是线性判别分析；batch/online 为优化方式。",
        r"\theta_d\sim Dir(\alpha),\quad z_{dn}\sim Cat(\theta_d),\quad w_{dn}\sim Cat(\beta_{z_{dn}})",
        "每篇文档混合多个主题，每主题给词分布。",
        r"$\theta_d$ 为文档主题比例，$z_{dn}$ 为词位置主题，$\beta_k$ 为主题词概率。",
        "计数词袋 → 指定主题数/先验 → 变分拟合 → 看主题词与文档比例。",
        "输入为非负计数而非任意负值；主题可置换，主题名需人工解释；短文本可能不稳。",
        "两主题比例(0.7,0.3)，某词在两主题概率0.2、0.1，则混合词概率0.17。",
        source(
            "Blei, Ng & Jordan (2003)",
            "https://www.jmlr.org/papers/v3/blei03a.html",
            "Generative process and variational inference",
        ),
    )

    add(
        "domain.km",
        "Kaplan-Meier 右删失生存函数。",
        r"\hat S(t)=\prod_{t_j\le t}\left(1-\frac{d_j}{n_j}\right)",
        "按事件时点递乘条件存活概率。",
        r"$d_j$ 为时点事件数，$n_j$ 为事件发生前风险集；删失减少后续风险集但不直接作为事件。",
        "核对时间/事件码 → 排序 → 构风险集 → 递乘 → 区间/分组比较。",
        "独立/非信息性删失；竞争事件不能简单当删失后用1−KM当发生率。",
        "初始5人首时点1事件，S=0.8；下一时点风险集4人1事件，S=0.8×0.75=0.6。",
        source(
            "lifelines · KaplanMeierFitter",
            "https://lifelines.readthedocs.io/en/latest/fitters/univariate/KaplanMeierFitter.html",
            "Kaplan-Meier estimator and event_observed",
        ),
    )

    add(
        "domain.cox",
        "比例风险模型，ties/惩罚与基线估计口径以实现为准。",
        r"h(t\mid x)=h_0(t)e^{x^\top\beta},\quad L(\beta)=\prod_{i:\delta_i=1}\frac{e^{x_i^\top\beta}}{\sum_{j\in R(t_i)}e^{x_j^\top\beta}}",
        "风险比由协变量决定，基线风险不指定形状；右式为无并列事件的部分似然。",
        r"$h_0$ 为基线风险，$\delta_i$ 为事件指示，$R(t_i)$ 为风险集；$e^{\beta_j}$ 为风险比。",
        "时间/事件整理 → 部分似然拟合 → 比例风险诊断 → 风险比/生存预测。",
        "风险比不是发生概率比；删失机制和比例风险假设重要；并列事件需 Efron/Breslow 等修正。",
        "β=ln2 时一个单位协变量增加对应风险倍增2，不能说生存概率减半。",
        source(
            "lifelines · Cox regression",
            "https://lifelines.readthedocs.io/en/latest/Survival%20Regression.html",
            "Cox proportional hazards model",
        ),
    )

    add(
        "domain.nomogram",
        "将Cox线性预测统一缩放为同向积分；各列按本次样本范围制分，不是另一个预测模型。",
        r"P_i=c\sum_j\beta_j(x_{ij}-a_j),\quad c=\frac{P_{max}}{\max_j\{|\beta_j|(x_{j,max}-x_{j,min})\}}",
        "正系数以最小值为零分，负系数以最大值为零分；总分与Cox线性预测同向。",
        r"$a_j$ 为该列最低风险端点；$P_{max}$ 是影响范围最大单项的最高分，总分可更高；时点风险为$1-\hat S(t\mid x)$。",
        "拟合Cox → 按带符号的效应与列范围统一缩放 → 汇总积分 → 输出指定时点风险和生存率。",
        "积分依赖本次特征范围，不能当作外部校准；风险与生存率使用同一预测时点，风险比不等于发生概率。",
        "β=−1、列范围0到2、单项最高100分时，x=0得100分，x=2得0分，保留保护方向。",
        source(
            "lifelines · Cox regression",
            "https://lifelines.readthedocs.io/en/latest/Survival%20Regression.html",
            "Cox linear predictor and survival probability; affine point scaling is local domain.nomogram",
        ),
    )

    add(
        "domain.competing",
        "Aalen-Johansen 累积发生函数；非 Fine-Gray 回归。",
        r"\hat F_k(t)=\sum_{t_j\le t}\hat S(t_j^-)\frac{d_{jk}}{n_j}",
        "目标事件的累积发生率同时考虑所有竞争事件对存活风险集的消耗。",
        r"$d_{jk}$ 为时点 j 的类型 k 事件数；$\hat S(t_j^-)$ 为任一事件发生前存活率。",
        "统一事件码0删失/其余类别 → 估总事件生存 → 按事件类型累加 → 绘制 CIF。",
        "不能对其他事件删失后用1−KM代替 CIF；独立删失与并列时点处理需核对。",
        "初始10人同一时点1目标事件、2竞争事件，目标 CIF 增量为1×1/10=0.1。",
        source(
            "lifelines · AalenJohansenFitter",
            "https://lifelines.readthedocs.io/en/latest/fitters/univariate/AalenJohansenFitter.html",
            "Competing risk cumulative incidence",
        ),
    )

    add(
        "domain.reliability",
        "Cronbach α 描述内部一致性；效度/KMO/Bartlett 是不同诊断。",
        r"\alpha=\frac{k}{k-1}\left(1-\frac{\sum_js_j^2}{s_{total}^2}\right)",
        "比较各题方差和与总分方差，衡量题项一致程度。",
        r"$k>1$ 为题数，$s_j^2$ 为题方差，$s_{total}^2$ 为总分方差；使用同样样本/分母。",
        "检查反向题/缺失 → 算总分方差 → α → 删题诊断及效度另评。",
        "α 高不证明单维性或效度；重复题可抬高 α；总分方差0时无定义。",
        "k=3、题方差和3、总分方差6，α=3/2×(1−1/2)=0.75。",
        source(
            "Cronbach (1951)",
            "https://doi.org/10.1007/BF02310555",
            "Coefficient alpha and internal structure",
        ),
    )

    add(
        "domain.nps",
        "标准0–10量表：9–10推荐者、0–6贬损者、7–8中立者。",
        r"NPS=100\left(\frac{n_{prom}}n-\frac{n_{det}}n\right)",
        "推荐者百分比减贬损者百分比，范围−100到100。",
        r"$n$ 为有效回答总数，含中立者；$n_{prom},n_{det}$ 为两组人数。",
        "核对量表/阈值 → 有效样本分类 → 百分点差 → 报告样本数和不确定性。",
        "不是平均评分；自定义阈值时应说明已偏离标准；非随机问卷不能直接推广全体客户。",
        "10人中推荐6、贬损2、中立2，NPS=40。",
        source(
            "Bain · Net Promoter System",
            "https://www.netpromotersystem.com/about/measuring-your-net-promoter-score/",
            "Promoters, passives and detractors; score definition",
        ),
    )

    add(
        "domain.kano",
        "当前用量表阈值分类，非完整原版问答评价表；区分 better_index 与 cs_better/cs_worse。",
        r"CS_+=\frac{A+O}{A+O+M+I},\quad CS_-=-\frac{O+M}{A+O+M+I}",
        "对分类后的魅力/期望/必备/无差异需求计算满意/不满意系数。",
        r"$A,O,M,I$ 为各类计数；当前 better_index 另为平均(具备分−不具备分)/(量表级数−1)。",
        "成对问项 → 按当前阈值规则分类 → 计算两类系数 → 看类别分布。",
        "不能把阈值近似分类宣称严格原版 Kano；反向/可疑回答和分母排除规则需说明。",
        "A=2、O=3、M=1、I=4，CS+=0.5、CS−=−0.4。",
        source(
            "Sauerwein et al. (1996) · Kano model",
            "https://faculty.kfupm.edu.sa/CEM/bushait/CEM_515-082/kano/kano-model2.pdf",
            "Customer satisfaction coefficient, pp. 6-7; cites Berger et al.",
        ),
    )

    add(
        "domain.maxdiff",
        "当前从评分矩阵的每行最大/最小选项计数；不是基于完整 best-worst 设计的条件 logit。",
        r"s_j=\frac{B_j-W_j}{n},\quad share_j=\frac{e^{s_j/T}}{\sum_le^{s_l/T}}",
        "净选择频次衡量相对偏好，softmax 仅为当前展示转换。",
        r"$B,W$ 为被选最好/最差次数，$n$ 为受访者数，$T>0$ 为温度。",
        "逐行选极值 → 按 score_kind 求净/单侧得分 → 可选0–100缩放 → softmax 或非负归一份额。",
        "并列极值、展示次数不等影响计数；份额非经估计的市场选择概率；完整 MaxDiff 需设计与选择模型。",
        "n=10、B=6、W=2，净分0.4；只统计 best_only 则为0.6。",
        source(
            "Louviere, Flynn & Marley (2015) · Best-Worst Scaling",
            "https://doi.org/10.1017/CBO9781107337855",
            "Best-worst count versus model based analysis",
        ),
    )

    add(
        "domain.conjoint",
        "当前评分型 OLS 联合分析；非选择型混合 logit。",
        r"y_i=\beta_0+\sum_j\beta_jx_{ij}+\epsilon_i",
        "用属性/水平编码解释 profile 评分，系数作为部分效用。",
        r"$x_{ij}$ 为选定属性编码，$y_i$ 为 profile 评分；编码基准影响系数。",
        "确定 profile 与评分 → 编码 → OLS → 可选效用缩放 → 计算相对重要性/展示份额。",
        "评分与选择数据不能混用似然；softmax 份额是附加假设，不是自动获得真实市场份额；缺少基准编码会共线。",
        "截距2、某属性效用1.5，其他编码0时该 profile 预测评分3.5。",
        sklearn(
            "linear_model#ordinary-least-squares", "OLS objective for local ratings-based conjoint"
        ),
    )

    add(
        "domain.psm",
        "当前单列可接受价格的分位数/需求代理；不是四问 Van Westendorp 完整曲线交点法。",
        r"\hat D(p)=\frac1n\sum_i\mathbf1(v_i\ge p),\quad R(p)=p\hat D(p)",
        "用声明价格超过 p 的比例近似可接受比例，收入代理为价格乘比例。",
        r"$v_i$ 为有效价格回答；$p$ 为网格价格。",
        "筛有效/按参数缩尾 → 求分位数 → 价格网格上算 D → midpoint 或 revenue 选价。",
        "仅有一列不能估计原版四条便宜/贵/太便宜/太贵曲线；声明接受不等于真实购买；不要混淆因果 PSM。",
        "价格回答 [10,20,30]，p=20 时 D=2/3、R≈13.33。",
        scipy(
            "ecdf",
            "Empirical distribution and survival function; local price_sensitivity uses inclusive >= tail and grid revenue proxy",
        ),
    )

    add(
        "domain.control",
        "Xbar/R、CUSUM、EWMA；下式为当前 EWMA 的稳态控制限，非初期时变限。",
        r"z_t=\lambda x_t+(1-\lambda)z_{t-1},\quad UCL_t=\mu_0+L\sigma\sqrt{\frac{\lambda}{2-\lambda}}",
        "平滑累计小漂移；LCL 用同一偏移减去均值。",
        r"$\lambda\in(0,1]$ 为平滑系数，$\mu_0,\sigma$ 为受控基准，$L$ 为控制限宽。",
        "稳定基准估计 → 按图类型计算。Xbar/R 用子组均值和极差及 A2/D3/D4 常数；CUSUM 递推正负累计偏差，越 h 报警。",
        "控制限不是规格限；估计基准、子组大小与自相关影响误报；EWMA 稳态限与初期时变限不同。",
        "z0=10、λ=0.2、新观测12，z1=10.4；不能把12直接当EWMA点。",
        QUALITY,
    )

    add(
        "domain.capability",
        "Cp/Cpk 为规格与短期过程离散比较；变换后必须同口径变换规格。",
        r"C_p=\frac{USL-LSL}{6\sigma},\quad C_{pk}=\min\left(\frac{USL-\mu}{3\sigma},\frac{\mu-LSL}{3\sigma}\right)",
        "Cp 看潜在容差，Cpk 同时考虑偏心。",
        r"$USL,LSL$ 为规格上/下限，$\mu,\sigma$ 为过程均值和相应标准差估计。",
        "确认过程稳定 → 确认规格 → 核对分布/变换 → 估 σ → Cp/Cpk及缺陷率。",
        "非稳定过程或强非正态下常规解释不可靠；总体/组内 σ 分别对应不同能力口径；控制限不替代规格。",
        "LSL=0、USL=12、μ=7、σ=2，Cp=1，Cpk=min(5/6,7/6)=0.8333。",
        QUALITY,
    )

    add(
        "domain.weibull",
        "两参数 Weibull；当前 MLE 或秩回归，非所有删失/三参数模型。",
        r"S(t)=e^{-(t/\eta)^\beta},\quad h(t)=\frac\beta\eta(t/\eta)^{\beta-1},\quad t\ge0",
        "用形状控制风险随时间升降，用尺度设寿命量级。",
        r"$\beta>0$ 为形状，$\eta>0$ 为尺度；$S(\eta)=e^{-1}$。",
        "核对正寿命与删失支持 → MLE/秩回归 → 诊断 → 可靠度/分位寿命。",
        "β<1/=/ >1 风险递减/常数/递增；shape/scale 与其他库命名需对齐；不能对未支持的删失默认当失效。",
        "β=2、η=10，t=10 时 S=e^(−1)≈0.3679。",
        scipy("weibull_min"),
    )

    add(
        "domain.meta",
        "逆方差固定/随机效应；τ² 可用 DL、REML、Paule-Mandel。",
        r"\hat\mu=\frac{\sum_iw_i\hat\theta_i}{\sum_iw_i},\quad w_i=\frac1{v_i+\tau^2},\quad SE(\hat\mu)=\sqrt{\frac1{\sum_iw_i}}",
        "按研究估计精度汇总效应；随机效应另计研究间异质性。",
        r"$v_i$ 为研究内方差（输入 SE 时需平方）；$\tau^2$ 为研究间方差，固定效应取0。",
        "统一效应尺度 → 核对输入是方差/SE → 估 τ² → 加权合并 → 异质性/敏感性。",
        "只在可比较效应尺度汇总；相关研究、发表偏倚和少研究数量影响推断；OR 通常在对数尺度合并再指数还原。",
        "两研究效应1、3、方差均1，固定效应合并2，SE=1/√2≈0.7071。",
        sm(
            "generated/statsmodels.stats.meta_analysis.combine_effects",
            "Fixed and random effects meta-analysis",
        ),
    )
