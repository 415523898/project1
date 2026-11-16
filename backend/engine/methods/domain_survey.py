"""Existing domain survey algorithms; registered by engine.methods.domain."""

import math

import numpy as np
import pandas as pd

from engine import registry
from engine.registry import MethodError, numbers, table_of

EPS = 1e-12


def reliability(context):
    table = context.table
    chosen = context.want("columns")
    names, matrix = registry.subset(table, chosen)
    minimum = context.whole("min_items", 2, 2, 50)
    threshold = context.number("alpha_threshold", 0.7, 0.3, 0.99)
    standardize = context.flag("standardize", False)
    split_half = context.flag("split_half", True)
    bartlett = context.flag("bartlett", True)
    omega = context.flag("omega", False)
    alpha_plot = context.flag("alpha_plot", True)
    scree_plot = context.flag("scree_plot", True)
    if matrix.shape[1] < 2:
        raise MethodError("信度分析至少需要两个题项。")
    if matrix.shape[1] < minimum:
        raise MethodError(f"信度分析至少需要 {minimum} 个题项，当前只选了 {matrix.shape[1]} 个。")

    def cronbach_alpha(block):
        items = block.shape[1]
        if items < 2:
            return None
        if standardize:
            centred = block - block.mean(axis=0, keepdims=True)
            spread = block.std(axis=0, ddof=1, keepdims=True)
            spread = np.where(spread <= EPS, 1.0, spread)
            values = centred / spread
            variance_items = values.var(axis=0, ddof=1).sum()
            variance_total = values.sum(axis=1).var(ddof=1)
        else:
            variance_items = block.var(axis=0, ddof=1).sum()
            variance_total = block.sum(axis=1).var(ddof=1)
        if variance_total <= EPS:
            return None
        return items / (items - 1) * (1 - variance_items / variance_total)

    alpha = cronbach_alpha(matrix)
    if alpha is None:
        raise MethodError("总方差为 0，无法计算信度。")
    item_rows = []
    for index, name in enumerate(names):
        rest = np.delete(matrix, index, axis=1)
        item_rows.append(
            {
                "item": name,
                "item_total_correlation": round(
                    float(np.corrcoef(matrix[:, index], matrix.sum(axis=1))[0, 1]), 6
                ),
                "alpha_if_deleted": round(float(cronbach_alpha(rest) or 0.0), 6),
            }
        )
    items = pd.DataFrame(item_rows)

    half = matrix.shape[1] // 2
    split = [cronbach_alpha(matrix[:, :half]), cronbach_alpha(matrix[:, half:])]
    spearman_brown = None
    if all(value is not None for value in split):
        correlation = float(
            np.corrcoef(matrix[:, :half].sum(axis=1), matrix[:, half:].sum(axis=1))[0, 1]
        )
        spearman_brown = 2 * correlation / (1 + correlation) if abs(1 + correlation) > EPS else None
    if not split_half:
        split = [None, None]
        spearman_brown = None

    from scipy.stats import chi2

    correlation_matrix = np.corrcoef(matrix, rowvar=False)
    correlation_matrix = np.nan_to_num(correlation_matrix, nan=0.0)
    np.fill_diagonal(correlation_matrix, 1.0)
    determinant = max(float(np.linalg.det(correlation_matrix)), EPS)
    statistic = -(matrix.shape[0] - 1 - (2 * matrix.shape[1] + 5) / 6) * math.log(determinant)
    dfree = matrix.shape[1] * (matrix.shape[1] - 1) / 2
    bartlett_p = float(1 - chi2.cdf(statistic, dfree)) if dfree > 0 else None
    if not bartlett:
        statistic = None
        bartlett_p = None

    metrics = {
        "items": int(matrix.shape[1]),
        "respondents": int(matrix.shape[0]),
        "min_items": int(minimum),
        "items_over_minimum": int(matrix.shape[1] - minimum),
        "alpha_threshold": round(float(threshold), 6),
        "standardize": bool(standardize),
        "split_half": bool(split_half),
        "bartlett": bool(bartlett),
        "cronbach_alpha": round(float(alpha), 6),
        "alpha_level": (
            "优秀"
            if alpha >= threshold + 0.2
            else "良好"
            if alpha >= threshold + 0.1
            else "可接受"
            if alpha >= threshold
            else "偏低"
        ),
        "split_half_alpha": numbers([value for value in split if value is not None], 6),
        "spearman_brown": None if spearman_brown is None else round(spearman_brown, 6),
        "bartlett_chi_square": None if statistic is None else round(statistic, 6),
        "bartlett_p": None if bartlett_p is None else round(bartlett_p, 8),
    }
    notes = [
        f"Cronbach α 大于 {threshold:g} 一般可接受，大于 {threshold + 0.2:g} 表示内部一致性很好。",
        f"少于 {minimum} 个题项时不做信度分析，避免结果不可靠。",
        "alpha_if_deleted 明显高于总 α 的题项应考虑删除。",
        "Bartlett 检验显著说明题项之间存在相关，适合做因子分析。",
    ]
    if standardize:
        notes.append("已先把各题项标准化再计算 α，等价于用相关矩阵计算，可消除量纲差异。")
    if omega:
        from sklearn.decomposition import FactorAnalysis

        factor = FactorAnalysis(n_components=1, random_state=0)
        factor.fit(registry.scaled(matrix, "zscore"))
        loadings = np.asarray(factor.components_[0], dtype=float)
        common = float((loadings**2).sum())
        unique = float(np.clip(factor.noise_variance_, 0.0, None).sum())
        metrics["mcdonald_omega"] = round(common / max(common + unique, EPS), 6)
        notes.append("McDonald's ω 由单因子模型的共同方差占总方差的比例得到，不要求题目等价。")
    if alpha_plot:
        try:
            import matplotlib.pyplot as plt

            values = items["alpha_if_deleted"].to_numpy()
            order = np.argsort(-values)[: min(20, values.size)]
            fig, axis = plt.subplots(figsize=(7, 5))
            axis.barh(
                [str(items["item"].to_numpy()[index]) for index in order][::-1],
                values[order][::-1],
                color="#4f7cff",
            )
            axis.axvline(
                float(alpha),
                color="#e24a4a",
                linestyle="--",
                linewidth=1.2,
                label=f"总 α={float(alpha):.3f}",
            )
            axis.set_xlabel("删除该题项后的 α")
            axis.set_title("题项删除后的 α 变化（前 20 项）")
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3, axis="x")
            context.save(fig, "domain_reliability_alpha")
        except ImportError:
            context.warn("未安装 matplotlib，跳过题项删除 α 图。")
    if scree_plot:
        try:
            import matplotlib.pyplot as plt

            eigenvalues = np.sort(np.linalg.eigvalsh(correlation_matrix))[::-1]
            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.plot(
                np.arange(1, eigenvalues.size + 1),
                eigenvalues,
                marker="o",
                markersize=4,
                color="#4f7cff",
            )
            axis.axhline(1.0, color="#e24a4a", linestyle="--", linewidth=1.2, label="特征值 1")
            axis.set_xlabel("因子序号")
            axis.set_ylabel("特征值")
            axis.set_title("相关矩阵碎石图")
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3)
            context.save(fig, "domain_reliability_scree")
        except ImportError:
            context.warn("未安装 matplotlib，跳过碎石图。")
    return registry.result(
        "domain.reliability",
        table,
        metrics=metrics,
        tables={"items": table_of(items, limit=60)},
        notes=notes,
    )


def nps(context):
    table = context.table
    score_column = context.text("score_column")
    if score_column and score_column not in table.raw.columns:
        raise MethodError("指定的推荐意愿评分列不存在。")
    target = (
        pd.to_numeric(table.raw[score_column], errors="coerce").to_numpy(dtype=float)
        if score_column in table.raw.columns
        else table.numeric_target()
    )
    if target is None:
        raise MethodError("NPS 需要数值评分列。")
    scale = context.number("scale_max", 10.0, 2.0, 100.0)
    promoter = context.number("promoter", 9.0, 0.0, scale)
    detractor = context.number("detractor", 7.0, 0.0, scale)
    level = context.number("ci", 0.95, 0.5, 0.999)
    group_column = context.text("group_column")
    zero_test = context.flag("zero_test", False)
    category_plot = context.flag("category_plot", True)
    distribution_plot = context.flag("distribution_plot", True)
    if detractor > promoter:
        raise MethodError("贬损阈值不应高于推荐阈值。")
    values = target[np.isfinite(target)]
    promoters = int((values >= promoter).sum())
    detractors = int((values <= detractor).sum())
    passives = int(values.size - promoters - detractors)
    score = (promoters - detractors) / max(values.size, 1) * 100
    from scipy import stats as sps

    ratio_promoter = promoters / max(values.size, 1)
    ratio_detractor = detractors / max(values.size, 1)
    variance = (
        (ratio_promoter + ratio_detractor - (ratio_promoter - ratio_detractor) ** 2)
        / max(values.size, 1)
        * 10000
    )
    z_critical = float(sps.norm.ppf(0.5 + level / 2.0))
    spread = z_critical * math.sqrt(max(variance, 0.0))
    interval_low = max(float(score) - spread, -100.0)
    interval_high = min(float(score) + spread, 100.0)
    rows = pd.DataFrame(
        {
            "category": ["推荐者", "被动者", "贬损者"],
            "count": [promoters, passives, detractors],
            "ratio": numbers(
                np.asarray([promoters, passives, detractors], dtype=float) / max(values.size, 1), 4
            ),
        }
    )
    tables = {"categories": table_of(rows)}
    group_note = None
    if group_column:
        if group_column not in table.raw.columns:
            raise MethodError(
                f"细分群体列 {group_column} 不在数据中。"
                f"可选：{'、'.join(str(name) for name in table.raw.columns[:12])}"
            )
        labels = table.raw[group_column].astype("string").fillna("缺失").to_numpy()
        if labels.size != target.size:
            raise MethodError(f"细分群体列 {group_column} 与评分列长度不一致。")
        labels = labels[np.isfinite(target)]
        group_rows = []
        for label in sorted(set(str(item) for item in labels)):
            block = values[labels == label]
            if block.size == 0:
                continue
            group_promoters = int((block >= promoter).sum())
            group_detractors = int((block <= detractor).sum())
            group_rows.append(
                {
                    "group": label,
                    "respondents": int(block.size),
                    "promoters": group_promoters,
                    "detractors": group_detractors,
                    "nps": round((group_promoters - group_detractors) / block.size * 100, 4),
                }
            )
        if not group_rows:
            raise MethodError(f"细分群体列 {group_column} 没有可用分组。")
        tables["group_nps"] = table_of(pd.DataFrame(group_rows), limit=50)
        group_note = f"已按 {group_column} 分组计算 NPS，共 {len(group_rows)} 个细分群体。"
    zero_stats = None
    if zero_test:
        error = math.sqrt(max(variance, 0.0))
        z_value = float(score / error) if error > EPS else 0.0
        p_value = float(2 * (1 - sps.norm.cdf(abs(z_value)))) if error > EPS else None
        zero_stats = (
            round(z_value, 6),
            None if p_value is None else round(p_value, 8),
            round(error, 4),
        )
        tables["zero_test"] = table_of(
            pd.DataFrame(
                [
                    {
                        "test": "NPS 与 0 的差异",
                        "nps": round(float(score), 4),
                        "std_error": round(error, 4),
                        "z_value": round(z_value, 6),
                        "p_value": None if p_value is None else round(p_value, 8),
                    }
                ]
            )
        )
    if category_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(6, 4))
            axis.bar(rows["category"], rows["count"], color=["#4f7cff", "#9aa7bd", "#f0803c"])
            axis.set_ylabel("人数")
            axis.set_title(f"NPS 分档（{promoter:g} 分及以上为推荐者）")
            axis.grid(alpha=0.3, axis="y")
            context.save(fig, "domain_nps")
        except ImportError:
            context.warn("未安装 matplotlib，跳过分档图。")
    notes = [
        "NPS = 推荐者占比 − 贬损者占比，范围 −100 到 +100。",
        f"当前量表满分 {scale:g}：{promoter:g} 分及以上为推荐者，{detractor:g} 分及以下为贬损者。",
        f"NPS 的 {level * 100:g}% 置信区间按推荐者与贬损者的多项分布方差近似计算。",
        "分档图展示三档人数分布。",
    ]
    if zero_stats is not None:
        notes.append(
            "NPS 与 0 的检验用推荐者与贬损者占比的方差近似，p 值偏小说明净推荐值显著不为 0。"
        )
    if group_note:
        notes.append(group_note)
    metrics = {
        "respondents": int(values.size),
        "nps": round(float(score), 4),
        "promoters": promoters,
        "passives": passives,
        "detractors": detractors,
        "mean_score": round(float(values.mean()), 6),
        "confidence_level": round(float(level), 6),
        "nps_ci_low": round(float(interval_low), 4),
        "nps_ci_high": round(float(interval_high), 4),
        "scale_max": scale,
        "category_plot": bool(category_plot),
    }
    if group_column:
        metrics["group_column"] = str(group_column)
        metrics["groups"] = int(tables["group_nps"]["total_rows"])
    if zero_stats is not None:
        metrics["zero_test_z"] = zero_stats[0]
        metrics["zero_test_p"] = zero_stats[1]
        metrics["nps_std_error"] = zero_stats[2]
    if distribution_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.hist(
                values, bins=max(5, min(20, values.size // 10)), color="#4f7cff", edgecolor="white"
            )
            axis.axvline(
                promoter,
                color="#38a169",
                linestyle="--",
                linewidth=1.2,
                label=f"推荐者阈值 {promoter:g}",
            )
            axis.axvline(
                detractor,
                color="#e24a4a",
                linestyle="--",
                linewidth=1.2,
                label=f"贬损者阈值 {detractor:g}",
            )
            axis.set_xlabel("评分")
            axis.set_ylabel("人数")
            axis.set_title("NPS 评分分布与分档阈值")
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3, axis="y")
            context.save(fig, "domain_nps_distribution")
        except ImportError:
            context.warn("未安装 matplotlib，跳过评分分布图。")
    return registry.result(
        "domain.nps",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


def _kano_scores(table, name, index, label):
    if name:
        if name not in table.raw.columns:
            raise MethodError(
                f"{label}列 {name} 不在数据中。"
                f"可选：{'、'.join(str(item) for item in table.raw.columns[:12])}"
            )
        values = pd.to_numeric(table.raw[name], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).any():
            raise MethodError(f"{label}列 {name} 不是数值评分列。")
        return np.where(np.isfinite(values), values, float(np.nanmedian(values)))
    if index >= table.n_features:
        raise MethodError(
            f"Kano 模型需要{label}列，请用 functional_item / dysfunctional_item 指定。"
        )
    return table.matrix()[:, index]


def kano(context):
    table = context.table
    functional_item = context.text("functional_item")
    dysfunctional_item = context.text("dysfunctional_item")
    from engine.dataset_selection import semantic_column

    functional_item = semantic_column(table.raw.columns, "functional_item", functional_item)
    dysfunctional_item = semantic_column(
        table.raw.columns, "dysfunctional_item", dysfunctional_item
    )
    if not functional_item or not dysfunctional_item or functional_item == dysfunctional_item:
        raise MethodError(
            "Kano 需要明确的功能具备/不具备成对题项，请指定 functional_item 和 dysfunctional_item。"
        )
    threshold = context.number("threshold", 4.0, 1.0, 5.0)
    scale = context.number("scale_max", 5.0, 2.0, 10.0)
    better_worse = context.flag("better_worse", True)
    plot = context.flag("plot", True)
    category_plot = context.flag("category_plot", True)
    if 2 * threshold < scale:
        raise MethodError(f"判定阈值不能小于量表满分的一半（{scale / 2:g}）。")
    functional = _kano_scores(table, functional_item, 0, "功能具备")
    dysfunctional = _kano_scores(table, dysfunctional_item, 1, "功能不具备")
    names = list(table.feature_names)
    functional_name = functional_item or (names[0] if names else "功能具备")
    dysfunctional_name = dysfunctional_item or (names[1] if len(names) > 1 else "功能不具备")
    high = threshold
    low = scale - threshold

    def classify(good, bad):
        if good >= high and bad <= low:
            return "魅力需求"
        if good >= high and bad >= high:
            return "期望需求"
        if good <= low and bad >= high:
            return "必备需求"
        if good <= low and bad <= low:
            return "无差异需求"
        return "反向需求"

    labels = [classify(float(left), float(right)) for left, right in zip(functional, dysfunctional)]
    counts = pd.Series(labels).value_counts()
    rows = pd.DataFrame(
        {
            "category": counts.index,
            "count": counts.to_numpy(),
            "ratio": numbers(counts.to_numpy() / max(len(labels), 1), 4),
        }
    )
    better = functional - dysfunctional
    cs = float(better.mean()) / max(scale - 1.0, EPS) if better.size else 0.0
    metrics = {
        "respondents": int(functional.size),
        "functional_column": functional_name,
        "dysfunctional_column": dysfunctional_name,
        "threshold": round(float(threshold), 6),
        "scale_max": round(float(scale), 6),
        "dominant": str(counts.index[0]) if len(counts) else None,
        "better_worse": bool(better_worse),
        "category_plot": bool(plot),
        "better_index": round(float(cs), 6),
    }
    tables = {"categories": table_of(rows)}
    notes = [
        f"按 {scale:g} 级量表分类：具备得分不低于 {high:g} 且不具备得分不高于 {low:g} 的是魅力需求。",
        "具备与不具备评分由 functional_item / dysfunctional_item 指定，或按明确的题项名称识别。",
        "better 指数越大表示该功能越能提升满意度。",
    ]
    if better_worse:
        total = sum(1 for label in labels if label != "反向需求")
        attractive = labels.count("魅力需求")
        expected = labels.count("期望需求")
        must = labels.count("必备需求")
        cs_better = (attractive + expected) / max(total, 1)
        cs_worse = -(expected + must) / max(total, 1)
        metrics["cs_better"] = round(float(cs_better), 6)
        metrics["cs_worse"] = round(float(cs_worse), 6)
        tables["coefficients"] = table_of(
            pd.DataFrame(
                [
                    {
                        "index": "better",
                        "value": round(float(cs_better), 6),
                        "meaning": "功能具备时的满意度提升潜力",
                    },
                    {
                        "index": "worse",
                        "value": round(float(cs_worse), 6),
                        "meaning": "功能不具备时的满意度下降风险",
                    },
                ]
            )
        )
        notes.append(
            f"标准 Kano 系数：better={cs_better:.4f}、worse={cs_worse:.4f}，"
            f"用魅力、期望、必备与无差异四类的频数计算。"
        )
    if plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(6.5, 5))
            axis.scatter(functional, dysfunctional, s=18, color="#4f7cff", alpha=0.6)
            axis.axvline(high, linestyle="--", color="#9aa7bd", linewidth=1.0)
            axis.axhline(high, linestyle="--", color="#9aa7bd", linewidth=1.0)
            axis.axvline(low, linestyle=":", color="#9aa7bd", linewidth=1.0)
            axis.axhline(low, linestyle=":", color="#9aa7bd", linewidth=1.0)
            axis.set_xlabel("功能具备得分")
            axis.set_ylabel("功能不具备得分")
            axis.set_title("Kano 属性分类矩阵")
            axis.grid(alpha=0.3)
            context.save(fig, "domain_kano")
        except ImportError:
            context.warn("未安装 matplotlib，跳过属性分类矩阵图。")
    if category_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(6.5, 4.5))
            axis.bar(
                [str(category) for category in rows["category"]], rows["count"], color="#4f7cff"
            )
            axis.set_ylabel("人数")
            axis.set_title("Kano 需求类别分布")
            axis.grid(alpha=0.3, axis="y")
            context.save(fig, "domain_kano_category")
        except ImportError:
            context.warn("未安装 matplotlib，跳过需求类别分布图。")
    return registry.result(
        "domain.kano",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


def maxdiff(context):
    table = context.table
    chosen = context.want("columns")
    names, matrix = registry.subset(table, chosen)
    temperature = context.number("temperature", 1.0, 0.1, 10.0)
    score_kind = context.text("score_kind", "diff", ("diff", "best_only", "worst_only"))
    share_kind = context.text("share_kind", "softmax", ("softmax", "normalized"))
    score_scale = context.text("score_scale", "raw", ("raw", "rescaled"))
    utility = context.flag("utility", False)
    top = context.whole("top", 20, 3, 60)
    utility_plot = context.flag("utility_plot", True)
    if matrix.shape[1] < 3:
        raise MethodError("MaxDiff 至少需要三个选项。")
    best = matrix.argmax(axis=1)
    worst = matrix.argmin(axis=1)
    valid_choices = ((matrix == matrix.max(axis=1, keepdims=True)).sum(axis=1) == 1) & (
        (matrix == matrix.min(axis=1, keepdims=True)).sum(axis=1) == 1
    )
    if not valid_choices.any():
        raise MethodError("所有评分行都有并列最佳或最差，不能据此推导唯一的 Best–Worst 选择。")
    if not valid_choices.all():
        context.warn(f"{int((~valid_choices).sum())} 行存在并列最佳或最差，不计入推导的选择次数。")
    counts = np.zeros(matrix.shape[1])
    for index in range(matrix.shape[0]):
        if not valid_choices[index]:
            continue
        if score_kind in ("diff", "best_only"):
            counts[best[index]] += 1
        if score_kind in ("diff", "worst_only"):
            counts[worst[index]] -= 1
    scores = counts / int(valid_choices.sum())
    order = np.argsort(-scores)
    reported = scores
    if score_scale == "rescaled":
        span = max(float(np.ptp(scores)), EPS)
        reported = (scores - scores.min()) / span * 100.0
    rows = pd.DataFrame(
        {
            "option": [names[index] for index in order],
            "net_score": numbers(reported[order], 6),
            "times_best": [int(((best == index) & valid_choices).sum()) for index in order],
            "times_worst": [int(((worst == index) & valid_choices).sum()) for index in order],
        }
    )
    if share_kind == "normalized":
        shifted = scores - scores.min()
        share = (
            shifted / shifted.sum()
            if shifted.sum() > EPS
            else np.full(len(scores), 1.0 / len(scores))
        )
    else:
        share = _softmax(scores, temperature)
    rows["share"] = numbers(share[order], 6)
    listed = int(min(top, matrix.shape[0]))
    choices = pd.DataFrame(
        {
            "choice_set": range(1, listed + 1),
            "best": [
                names[int(best[index])] if valid_choices[index] else "并列，未计入"
                for index in range(listed)
            ],
            "worst": [
                names[int(worst[index])] if valid_choices[index] else "并列，未计入"
                for index in range(listed)
            ],
        }
    )
    tables = {"options": table_of(rows, limit=top), "choices": table_of(choices, limit=top)}
    if utility:
        centered = matrix - matrix.mean(axis=1, keepdims=True)
        scaled = centered / max(float(temperature), EPS)
        scaled = scaled - scaled.max(axis=1, keepdims=True)
        exponent = np.exp(scaled)
        utilities = exponent / np.maximum(exponent.sum(axis=1, keepdims=True), EPS)
        utility_rows = pd.DataFrame(utilities, columns=[f"效用_{name}" for name in names])
        utility_rows.insert(0, "respondent", range(1, matrix.shape[0] + 1))
        tables["utilities"] = table_of(utility_rows, limit=50)
    notes = [
        "净得分 = 被选为最好的次数 − 被选为最差的次数，再除以受访者数。",
        "本实现从评分矩阵推导最佳/最差，未拟合真实 Best–Worst 选择实验的条件 logit；份额是分数变换，不是市场选择概率。",
        f"份额用温度为 {temperature:g} 的 softmax 把净得分换算成相对偏好比例。",
        f"选项排行榜与选择集明细各输出前 {top} 行。",
    ]
    if score_kind == "best_only":
        notes.append("净得分口径为仅统计被选为最好的次数，不考虑被选为最差。")
    elif score_kind == "worst_only":
        notes.append("净得分口径为仅统计被选为最差的次数（取负），不考虑被选为最好。")
    if share_kind == "normalized":
        notes.append("份额改为把非负的净得分归一化，温度参数此时不起作用。")
    if utility:
        notes.append(
            "个体效用按每行评分做中心化 softmax，行内和为 1，可比较同一受访者对各选项的偏好。"
        )
    if score_scale == "rescaled":
        notes.append("净得分已按选项间极差线性重标定到 0–100，便于报告相对效用。")
    if utility_plot:
        try:
            import matplotlib.pyplot as plt

            chart = rows.head(listed)
            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.barh(
                [str(option) for option in chart["option"]][::-1],
                chart["net_score"].to_numpy()[::-1],
                color="#4f7cff",
            )
            axis.axvline(0.0, color="#4a5568", linewidth=1.0)
            axis.set_xlabel("净得分")
            axis.set_title("MaxDiff 选项效用（净得分）")
            axis.grid(alpha=0.3, axis="x")
            context.save(fig, "domain_maxdiff_utility")
        except ImportError:
            context.warn("未安装 matplotlib，跳过效用条形图。")
    return registry.result(
        "domain.maxdiff",
        table,
        metrics={
            "options": int(matrix.shape[1]),
            "respondents": int(matrix.shape[0]),
            "effective_choice_rows": int(valid_choices.sum()),
            "input_kind": "ratings_proxy",
            "temperature": round(float(temperature), 6),
            "score_kind": score_kind,
            "share_kind": share_kind,
            "utility": bool(utility),
            "top": int(top),
            "top_option": names[int(order[0])],
            "top_share": round(float(share[int(order[0])]), 6),
        },
        tables=tables,
        notes=notes,
    )


def _softmax(values, temperature=1.0):
    shifted = np.asarray(values, dtype=float) / max(float(temperature), EPS)
    shifted = shifted - shifted.max()
    exponent = np.exp(shifted)
    return exponent / max(exponent.sum(), EPS)


def conjoint(context):
    import statsmodels.api as sm

    table = context.table
    chosen = context.want("columns")
    names, matrix = registry.subset(table, chosen)
    preference = context.text("preference_column")
    standardize = context.flag("standardize", False)
    interactions = context.flag("interactions", False)
    utility_scale = context.text("utility_scale", "raw", ("raw", "centered", "rescaled"))
    importance_ci = context.flag("importance_ci", False)
    profiles = context.whole("profiles", None, 2, 100000)
    utility_plot = context.flag("utility_plot", True)
    if matrix.shape[1] < 2:
        raise MethodError("联合分析至少需要两个属性列。")
    if standardize:
        matrix = registry.scaled(matrix, "zscore")
    if preference:
        if preference not in table.raw.columns:
            raise MethodError(f"偏好评分列 {preference} 不在数据中。")
        response = pd.to_numeric(table.raw[preference], errors="coerce").to_numpy(dtype=float)
    else:
        response = table.numeric_target()
        if response is None:
            raise MethodError("联合分析需要一个偏好/评分列。")
    keep = np.isfinite(response)
    if profiles is not None:
        limit = min(int(profiles), matrix.shape[0])
        selected = np.zeros(matrix.shape[0], dtype=bool)
        selected[:limit] = True
        keep = keep & selected
    if keep.sum() < 2:
        raise MethodError("联合分析至少需要两个有效 profile。")
    selected_matrix = matrix[keep]
    terms = [str(name) for name in names]
    if interactions:
        parts = [selected_matrix]
        for first in range(selected_matrix.shape[1]):
            for second in range(first + 1, selected_matrix.shape[1]):
                parts.append(
                    (selected_matrix[:, first] * selected_matrix[:, second]).reshape(-1, 1)
                )
                terms.append(f"{names[first]}×{names[second]}")
        selected_matrix = np.hstack(parts)
    if keep.sum() < selected_matrix.shape[1] + 1:
        raise MethodError(
            f"联合分析需要至少 {selected_matrix.shape[1] + 1} 个有效 profile 才能估计 "
            f"{selected_matrix.shape[1]} 个项，当前只有 {int(keep.sum())} 个。"
        )
    design = sm.add_constant(selected_matrix, has_constant="add")
    fitted = sm.OLS(response[keep], design).fit()
    utilities = np.asarray(fitted.params[1:], dtype=float)
    if utility_scale == "centered":
        utilities = utilities - utilities.mean()
    elif utility_scale == "rescaled":
        span = max(float(np.ptp(utilities)), EPS)
        utilities = (utilities - utilities.min()) / span * 100.0
    importance = np.abs(utilities)
    total = importance.sum()
    weights = importance / total if total > EPS else np.full(len(terms), 1.0 / len(terms))
    rows = pd.DataFrame(
        {
            "attribute": terms,
            "utility": numbers(utilities, 6),
            "importance": numbers(weights, 4),
            "p_value": numbers(fitted.pvalues[1:], 8),
        }
    )
    if importance_ci:
        from scipy import stats as sps

        covariance = np.asarray(fitted.cov_params(), dtype=float)[1:, 1:]
        gradient = np.zeros((utilities.size, utilities.size))
        for index in range(utilities.size):
            for other in range(utilities.size):
                term = -abs(utilities[index]) * np.sign(utilities[other]) / max(total**2, EPS)
                if index == other:
                    term += np.sign(utilities[index]) / max(total, EPS)
                gradient[index, other] = term
        variance = np.einsum("ij,jk,ik->i", gradient, covariance, gradient)
        z_value = float(sps.norm.ppf(0.975))
        error = np.sqrt(np.clip(variance, 0.0, None))
        rows["importance_low"] = numbers(weights - z_value * error, 4)
        rows["importance_high"] = numbers(weights + z_value * error, 4)
    rows = rows.sort_values("importance", ascending=False)
    notes = [
        "效用值来自线性回归系数，表示该属性水平的偏好贡献。",
        "重要性用效用绝对值归一化得到，反映该属性对偏好的相对影响。",
        "参与估计的 profile 数可按需限制，属性列可先做标准化。",
    ]
    if interactions:
        notes.append(f"已加入属性两两乘积项，参与估计的项共 {len(terms)} 个，用于检验属性交互。")
    else:
        notes.append("这里假设各属性效应可加、不存在交互。")
    if importance_ci:
        notes.append("重要性的置信区间用回归系数协方差矩阵做 delta 方法近似（95% 水平）。")
    if utility_scale == "centered":
        notes.append("效用值已减去均值（中心化），零点表示各属性的平均水平。")
    elif utility_scale == "rescaled":
        notes.append("效用值已线性重标定到 0–100，便于跨属性比较相对偏好强度。")
    if utility_plot:
        try:
            import matplotlib.pyplot as plt

            chart = rows.head(min(20, int(rows.shape[0])))
            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.barh(
                [str(attribute) for attribute in chart["attribute"]][::-1],
                chart["utility"].to_numpy()[::-1],
                color="#4f7cff",
            )
            axis.axvline(0.0, color="#4a5568", linewidth=1.0)
            axis.set_xlabel("效用值")
            axis.set_title("联合分析属性效用")
            axis.grid(alpha=0.3, axis="x")
            context.save(fig, "domain_conjoint_utility")
        except ImportError:
            context.warn("未安装 matplotlib，跳过属性效用条形图。")
    return registry.result(
        "domain.conjoint",
        table,
        metrics={
            "attributes": len(names),
            "terms": len(terms),
            "profiles": int(keep.sum()),
            "profiles_limit": None if profiles is None else int(profiles),
            "standardize": bool(standardize),
            "interactions": bool(interactions),
            "importance_ci": bool(importance_ci),
            "r_squared": round(float(fitted.rsquared), 6),
            "most_important": str(rows.iloc[0]["attribute"]),
            "most_important_weight": round(float(rows.iloc[0]["importance"]), 4),
        },
        tables={"utilities": table_of(rows, limit=40)},
        notes=notes,
    )


def _parse_quantiles(text):
    parts = [part.strip() for part in str(text).replace("，", ",").split(",") if part.strip()]
    if not parts:
        raise MethodError("分位点不能为空，请写成逗号分隔的百分数，例如 10,25,50,75,90。")
    values = []
    for part in parts:
        try:
            value = float(part)
        except (TypeError, ValueError):
            raise MethodError(
                f"分位点 {part} 不是数字，请写成逗号分隔的百分数，例如 10,25,50,75,90。"
            ) from None
        if not math.isfinite(value) or not 0 < value < 100:
            raise MethodError(f"分位点 {part} 必须落在 0 到 100 之间。")
        values.append(value)
    levels = sorted(set(values))
    if len(levels) < 3:
        raise MethodError("至少需要三个互不相同的分位点，例如 10,25,50,75,90。")
    return levels


def price_sensitivity(context):
    table = context.table
    column = context.text("price_column")
    if column:
        if column not in table.raw.columns:
            raise MethodError(
                f"价格列 {column} 不在数据中。"
                f"可选：{'、'.join(str(name) for name in table.raw.columns[:12])}"
            )
        prices = pd.to_numeric(table.raw[column], errors="coerce").to_numpy(dtype=float)
    else:
        target = table.numeric_target()
        if target is None:
            raise MethodError("PSM 需要一列价格评分或购买意愿。")
        column = table.target_name
        prices = np.asarray(target, dtype=float)
    levels = _parse_quantiles(context.text("quantiles", "10,25,50,75,90"))
    trim = context.number("trim", 0.0, 0.0, 0.4)
    curve_points = context.whole("curve_points", 40, 10, 200)
    optimal_rule = context.text("optimal_rule", "midpoint", ("midpoint", "revenue"))
    intersection_plot = context.flag("intersection_plot", True)
    distribution_plot = context.flag("distribution_plot", True)
    values = prices[np.isfinite(prices)]
    if values.size < 8:
        raise MethodError("PSM 需要至少 8 个有效价格观测。")
    if np.unique(values).size < 2:
        raise MethodError("价格只有一种取值，无法估计价格敏感度。")
    if trim > 0:
        low_bound = float(np.quantile(values, trim))
        high_bound = float(np.quantile(values, 1.0 - trim))
        trimmed = values[(values >= low_bound) & (values <= high_bound)]
        if trimmed.size >= 8:
            values = trimmed
        else:
            context.warn(f"按 {trim:g} 缩尾后只剩 {trimmed.size} 个观测，已忽略缩尾设置。")
    values = np.sort(values)
    points = np.percentile(values, levels)
    too_cheap = float(points[0])
    bargain = float(points[1])
    expensive = float(points[-2])
    too_expensive = float(points[-1])
    optimum = (bargain + expensive) / 2
    indifference = (too_cheap + too_expensive) / 2
    if len(levels) == 5:
        labels = ["太便宜", "便宜", "价格适中", "偏贵", "太贵"]
    else:
        labels = [f"P{level:g}" for level in levels]
    rows = pd.DataFrame(
        {
            "point": labels,
            "quantile": numbers(levels, 4),
            "price": numbers(points, 4),
        }
    )
    grid = np.linspace(float(values.min()), float(values.max()), curve_points)
    demand = np.asarray([float((values >= price).mean()) for price in grid])
    if optimal_rule == "revenue":
        optimum = float(grid[int(np.argmax(grid * demand))])
    curve = pd.DataFrame({"price": numbers(grid, 4), "accept_share": numbers(demand, 6)})
    if intersection_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.plot(grid, demand, color="#4f7cff")
            for value, label in zip(
                [too_cheap, bargain, expensive, too_expensive], ["太便宜", "便宜", "偏贵", "太贵"]
            ):
                share_at = float((values >= value).mean())
                axis.axvline(value, linestyle="--", linewidth=1.0, label=f"{label} {value:.4g}")
                axis.plot([value], [share_at], "o", color="#f0803c", markersize=4)
            axis.set_xlabel("价格")
            axis.set_ylabel("可接受比例")
            axis.set_title("价格接受曲线与四个关键价格点")
            axis.legend(fontsize=7)
            axis.grid(alpha=0.3)
            context.save(fig, "domain_psm_curve")
        except ImportError:
            context.warn("未安装 matplotlib，跳过价格曲线交点图。")
    if distribution_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.hist(
                values, bins=min(20, max(5, values.size // 5)), color="#4f7cff", edgecolor="white"
            )
            for value, label in zip(
                [too_cheap, bargain, expensive, too_expensive], ["太便宜", "便宜", "偏贵", "太贵"]
            ):
                axis.axvline(value, linestyle="--", linewidth=1.0, label=f"{label} {value:.4g}")
            axis.set_xlabel("价格")
            axis.set_ylabel("频数")
            axis.set_title("价格分布与关键分位点")
            axis.legend(fontsize=7)
            axis.grid(alpha=0.3)
            context.save(fig, "domain_psm")
        except ImportError:
            context.warn("未安装 matplotlib，跳过价格分布图。")
    notes = [
        "最优价格按价格与可接受比例的收益最大点选取，无差异价格取两端的中点。"
        if optimal_rule == "revenue"
        else "最优价格取“便宜”与“偏贵”分位数的中点，无差异价格取两端的中点。",
        f"分位点由 quantiles 指定（{', '.join(f'{level:g}' for level in levels)}）。",
        "这是对已有价格数据的分位数近似，不等价于完整的 PSM 问卷四问法。",
        f"价格接受曲线在 {curve_points} 个价格点上给出愿意接受该价格的样本比例。",
    ]
    if trim > 0:
        notes.append(f"分位点与曲线已先按 {trim * 100:g}% 两端缩尾，降低极端价格的干扰。")
    return registry.result(
        "domain.psm",
        table,
        metrics={
            "column": column,
            "respondents": int(values.size),
            "quantiles": numbers(levels, 4),
            "trim": round(float(trim), 6),
            "curve_points": int(curve_points),
            "too_cheap": round(too_cheap, 4),
            "bargain": round(bargain, 4),
            "expensive": round(expensive, 4),
            "too_expensive": round(too_expensive, 4),
            "optimal_price": round(optimum, 4),
            "indifference_price": round(indifference, 4),
            "intersection_plot": bool(intersection_plot),
            "distribution_plot": bool(distribution_plot),
        },
        tables={
            "price_points": table_of(rows),
            "accept_curve": table_of(curve, limit=curve_points),
        },
        notes=notes,
    )
