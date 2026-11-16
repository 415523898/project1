import math

import numpy as np
import pandas as pd

from engine import registry
from engine.numerics import probabilities
from engine.plot_diagnostics import confusion_figure
from engine.registry import MethodError, numbers, register, table_of

EPS = 1e-12


def _fit_rows(context):
    outcome = context.split_indices()
    if not outcome.has_test:
        return None
    rows = outcome.train
    if rows.size < 3:
        raise MethodError(f"划分后训练集只有 {rows.size} 条，样本太少无法拟合；请调小 test_size。")
    return rows


def _aligned(context, values):
    rows = _fit_rows(context)
    if values is None or rows is None:
        return values
    return np.asarray(values)[rows]


def _xy(context, columns=None, require_target=True):
    table = context.table
    rows = _fit_rows(context)
    matrix = table.matrix()
    target = table.numeric_target()
    if target is None and require_target:
        raise MethodError("该方法需要数值目标列。")
    if columns:
        if isinstance(columns, str):
            columns = [item.strip() for item in columns.split(",") if item.strip()]
        index = []
        for name in columns:
            if name not in table.feature_names:
                raise MethodError(
                    f"列 {name} 不在特征中。可选：{'、'.join(table.feature_names[:10])}"
                )
            index.append(table.feature_names.index(name))
        matrix = matrix[:, index]
        names = list(columns)
    else:
        names = list(table.feature_names)
    if not names:
        raise MethodError("没有可用特征。")
    if rows is not None:
        matrix = matrix[rows]
        if target is not None:
            target = np.asarray(target, dtype=float)[rows]
    return matrix, target, names


def _add_constant(matrix):
    return np.column_stack([np.ones(matrix.shape[0]), matrix])


def _durbin_watson(residuals):
    from statsmodels.stats.stattools import durbin_watson

    return durbin_watson(residuals)


def _labels(names, constant=True):
    return (["常数项"] if constant else []) + list(names)


def _design(matrix, constant=True):
    return _add_constant(matrix) if constant else np.asarray(matrix, dtype=float)


def _evaluation_data(context, names):
    rows = context.evaluation_indices()
    table = context.table
    columns = [table.feature_names.index(name) for name in names]
    matrix = table.matrix()[rows][:, columns]
    return matrix, np.asarray(table.labels())[rows]


def _finite_forest_rows(context, estimates, lows, highs):
    estimates, lows, highs = (
        np.asarray(values, dtype=float) for values in (estimates, lows, highs)
    )
    valid = (
        np.isfinite(estimates)
        & np.isfinite(lows)
        & np.isfinite(highs)
        & (lows <= estimates)
        & (estimates <= highs)
    )
    if not valid.all():
        context.warn(f"森林图略去 {int((~valid).sum())} 项不可用的估计或置信区间。")
    return np.flatnonzero(valid).tolist()


def _classification_diagnostic(context, name, actual, predicted, classes):
    if not context.figures_enabled:
        return None
    scope = "留出测试集" if context.split_used().has_test else "训练样本"
    context.warn("系数推断图不可用；改为真实评价样本的分类混淆矩阵，不含系数置信区间。")
    return confusion_figure(
        context,
        name,
        actual,
        predicted,
        f"分类诊断：{scope}（{len(actual)}条）\n混淆矩阵，不含系数置信区间",
        classes,
    )


def _coefficients(response, predictors):
    design = _add_constant(np.column_stack(predictors))
    return np.linalg.lstsq(design, np.asarray(response, dtype=float), rcond=None)[0]


def _confusion(predicted, actual):
    predicted = np.asarray(predicted, dtype=int)
    actual = np.asarray(actual, dtype=int)
    positive = int(((predicted == 1) & (actual == 1)).sum())
    negative = int(((predicted == 0) & (actual == 0)).sum())
    false_positive = int(((predicted == 1) & (actual == 0)).sum())
    false_negative = int(((predicted == 0) & (actual == 1)).sum())
    sensitivity = positive / (positive + false_negative) if positive + false_negative else None
    specificity = negative / (negative + false_positive) if negative + false_positive else None
    return {
        "true_positive": positive,
        "false_positive": false_positive,
        "true_negative": negative,
        "false_negative": false_negative,
        "sensitivity": None if sensitivity is None else round(sensitivity, 6),
        "specificity": None if specificity is None else round(specificity, 6),
    }


COLORS = ("#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2")


def _plotting():
    import matplotlib.pyplot as plt

    return plt


def _keep(figures, context, figure, name):
    saved = context.save(figure, name)
    if saved:
        figures.append(saved)
    return saved


def _z_value(confidence):
    from scipy import stats as sps

    return float(sps.norm.ppf(0.5 + float(confidence) / 2.0))


def _variable_summary(matrix):
    values = np.asarray(matrix, dtype=float)
    if values.ndim == 1:
        values = values.reshape(-1, 1)
    mean = values.mean(axis=0)
    spread = values.std(axis=0, ddof=0)
    return mean, np.where(spread <= EPS, 1.0, spread)


def _curve_points(values, count=25, low=0.05, high=0.95):
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return np.zeros(count)
    points = np.unique(np.percentile(values, np.linspace(low * 100.0, high * 100.0, count)))
    if points.size < 2:
        points = np.linspace(float(values.min()), float(values.max()) + 1.0, count)
    return points


def _design_grid(matrix, position, points, mean, spread):
    grid = np.tile(np.asarray(mean, dtype=float), (len(points), 1))
    if position is None:
        grid[:, 0] = points
    else:
        grid[:, position] = points
    return grid


def _chosen_column(names, asked):
    if not names:
        return None
    if asked and asked in names:
        return asked
    return names[0]


def _weights_for(context, rows):
    column = (context.text("weight_column") or "").strip()
    if not column or column in ("1", "等权", "equal"):
        values = np.ones(context.table.n_rows, dtype=float)
    else:
        if column not in context.table.frame.columns:
            raise MethodError(
                f"权重列 {column} 不在数据里："
                f"{'、'.join(str(name) for name in context.table.frame.columns[:12])}"
            )
        try:
            values = np.asarray(context.column(column), dtype=float)
        except (TypeError, ValueError):
            raise MethodError(f"权重列 {column} 必须是数值列。")
        if not np.all(np.isfinite(values)):
            raise MethodError(f"权重列 {column} 含缺失或非有限值。")
        if (values < 0).any():
            raise MethodError(f"权重列 {column} 存在负值，权重必须非负。")
        if values.sum() <= EPS:
            raise MethodError(f"权重列 {column} 全部为 0，无法拟合。")
    return _aligned(context, values)


def _jackknife_positions(size, cap=500):
    if size <= cap:
        return list(range(size))
    rng = np.random.default_rng(20240101)
    return sorted(int(value) for value in rng.choice(size, cap, replace=False))


def _bca_interval(draws, estimate, jackknife, confidence):
    from scipy import stats as sps

    values = np.asarray(draws, dtype=float)
    if values.size < 30:
        return None, None
    proportion = float(np.mean(values < estimate))
    proportion = min(max(proportion, 1.0 / values.size), 1.0 - 1.0 / values.size)
    bias = float(sps.norm.ppf(proportion))
    steps = np.asarray(jackknife, dtype=float)
    if steps.size < 2:
        return None, None
    centered = steps.mean() - steps
    denominator = 6.0 * float(np.sum(centered**2)) ** 1.5
    if denominator <= EPS:
        acceleration = 0.0
    else:
        acceleration = float(np.sum(centered**3)) / denominator
    alpha = 1.0 - float(confidence)
    bounds = []
    for tail in (alpha / 2.0, 1.0 - alpha / 2.0):
        adjusted = bias + (bias + float(sps.norm.ppf(tail))) / max(
            1.0 - acceleration * (bias + float(sps.norm.ppf(tail))), 1e-6
        )
        bounds.append(float(np.percentile(values, 100.0 * float(sps.norm.cdf(adjusted)))))
    return min(bounds), max(bounds)


def _bootstrap_draws(context, target, matrix, treatment, mediator, boot, seed):
    import statsmodels.api as sm

    y = np.asarray(target, dtype=float)
    x = np.asarray(matrix[:, treatment], dtype=float)
    m = np.asarray(matrix[:, mediator], dtype=float)

    def paths(x_values, m_values, y_values):
        a_value = float(sm.OLS(m_values, _add_constant(x_values.reshape(-1, 1))).fit().params[1])
        fit = sm.OLS(y_values, _add_constant(np.column_stack([x_values, m_values]))).fit()
        return a_value, float(fit.params[2])

    a, b = paths(x, m, y)
    observed = a * b
    rng = np.random.default_rng(seed)
    size = y.size
    draws = []
    for _ in range(boot):
        pick = rng.integers(0, size, size)
        try:
            a_star, b_star = paths(x[pick], m[pick], y[pick])
        except Exception:
            continue
        if np.isfinite(a_star) and np.isfinite(b_star):
            draws.append(a_star * b_star)
            continue
        draws.append(np.nan)
    steps = []
    for position in _jackknife_positions(size):
        keep = np.ones(size, dtype=bool)
        keep[position] = False
        try:
            a_star, b_star = paths(x[keep], m[keep], y[keep])
        except Exception:
            steps.append(observed)
            continue
        steps.append(a_star * b_star)
    return a, b, observed, np.asarray(draws, dtype=float), np.asarray(steps, dtype=float)


def _path_plot(
    context, figure_name, left_title, right_title, left_draw, right_draw, draws, low, high, indirect
):
    plt = _plotting()
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.3))
    axis = axes[0]
    left_draw(axis)
    axis.set_title(left_title)
    axis = axes[1]
    if right_draw is not None:
        right_draw(axis)
    axis.set_title(right_title)
    if draws is not None:
        finite = np.asarray(draws, dtype=float)
    else:
        finite = np.asarray([], dtype=float)
    finite = finite[np.isfinite(finite)]
    axis = axes[1]
    if finite.size:
        axis.hist(
            finite,
            bins=min(40, max(8, int(np.sqrt(finite.size)) + 4)),
            color="#93c5fd",
            edgecolor="#2563eb",
            alpha=0.85,
        )
    if indirect is not None:
        axis.axvline(indirect, color="#dc2626", linewidth=1.6, label=f"点估计 {indirect:.4g}")
    if low is not None and high is not None:
        axis.axvline(
            low,
            color="#111827",
            linewidth=1.1,
            linestyle="--",
            label=f"区间 [{low:.4g}, {high:.4g}]",
        )
        axis.axvline(high, color="#111827", linewidth=1.1, linestyle="--")
    if finite.size:
        axis.axvline(0.0, color="#6b7280", linewidth=1.0, linestyle=":")
    axis.set_xlabel("Bootstrap 间接效应")
    axis.set_ylabel("频数")
    axis.legend(fontsize=7)
    axis.grid(alpha=0.3)
    fig.tight_layout()
    return context.save(fig, figure_name)


def _mediation_panel(context, treatment, mediator, outcome, values):
    _plotting()

    def draw(axis):
        nodes = {"x": (0.08, 0.5), "m": (0.5, 0.78), "y": (0.92, 0.5)}
        labels = {"x": treatment, "m": mediator, "y": outcome}
        for key, (xpos, ypos) in nodes.items():
            axis.text(
                xpos,
                ypos,
                labels[key],
                ha="center",
                va="center",
                fontsize=9,
                bbox={"boxstyle": "round,pad=0.4", "facecolor": "#eff6ff", "edgecolor": "#2563eb"},
            )
        axis.annotate(
            "",
            xy=nodes["m"],
            xytext=nodes["x"],
            arrowprops={"arrowstyle": "->", "color": "#2563eb", "lw": 1.4},
        )
        axis.annotate(
            "",
            xy=nodes["y"],
            xytext=nodes["m"],
            arrowprops={"arrowstyle": "->", "color": "#2563eb", "lw": 1.4},
        )
        axis.annotate(
            "",
            xy=(0.92, 0.28),
            xytext=(0.08, 0.28),
            arrowprops={"arrowstyle": "->", "color": "#dc2626", "lw": 1.2, "linestyle": "dashed"},
        )
        axis.text(0.24, 0.58, f"a = {values['a']:.4g}", fontsize=8, color="#2563eb")
        axis.text(0.64, 0.64, f"b = {values['b']:.4g}", fontsize=8, color="#2563eb")
        axis.text(0.4, 0.2, f"c' = {values['direct']:.4g}", fontsize=8, color="#dc2626")
        axis.text(0.5, 0.04, f"间接效应 a×b = {values['indirect']:.4g}", fontsize=8, ha="center")
        axis.set_xlim(0, 1)
        axis.set_ylim(0, 1)
        axis.axis("off")

    return _path_plot(
        context,
        "model_mediation_path_and_bootstrap",
        "中介路径系数",
        "Bootstrap 间接效应分布",
        draw,
        None,
        values["draws"],
        values["low"],
        values["high"],
        values["indirect"],
    )


def _forest_plot(context, figure_name, terms, estimates, lows, highs, label, color="#2563eb"):
    if not context.figures_enabled:
        return None
    keep = _finite_forest_rows(context, estimates, lows, highs)
    if not keep:
        context.warn("没有可用的估计与置信区间，不生成空森林图。")
        return None
    plt = _plotting()
    order = keep[::-1]
    height = max(3.0, 0.34 * len(keep) + 1.2)
    fig, axis = plt.subplots(figsize=(7.2, height))
    positions = np.arange(len(keep))
    for row, position in zip(order, positions):
        axis.plot([lows[row], highs[row]], [position, position], color=color, linewidth=1.6)
        axis.plot([estimates[row]], [position], marker="o", color=color, markersize=5)
    axis.axvline(1.0 if label == "优势比" else 0.0, color="#dc2626", linewidth=1.1, linestyle="--")
    axis.set_yticks(positions)
    axis.set_yticklabels([terms[row] for row in order], fontsize=8)
    axis.set_xlabel(label)
    axis.set_title(f"{label}森林图（95% 置信区间）")
    axis.grid(alpha=0.3, axis="x")
    fig.tight_layout()
    return context.save(fig, figure_name)


def _group_effects_plot(
    context, figure_name, title, groups, values, fitted, limit=None, order="value"
):
    plt = _plotting()
    labels = [str(value) for value in groups]
    observed = (
        pd.Series(np.asarray(values, dtype=float)).groupby(np.asarray(labels), sort=False).mean()
    )
    predicted = (
        pd.Series(np.asarray(fitted, dtype=float)).groupby(np.asarray(labels), sort=False).mean()
    )
    frame = pd.DataFrame({"observed": observed, "fitted": predicted}).dropna()
    if order == "value":
        frame = (
            frame.assign(__key=frame["observed"] - frame["fitted"])
            .sort_values("__key", ascending=False)
            .drop(columns=["__key"])
        )
    else:
        frame = frame.sort_index()
    if limit is not None:
        frame = frame.head(int(limit))
    positions = np.arange(len(frame))
    width = 0.38
    fig, axis = plt.subplots(figsize=(max(6.0, 0.6 * len(frame) + 2.0), 4.2))
    axis.bar(
        positions - width / 2,
        frame["observed"].to_numpy(dtype=float),
        width,
        label="组均值（观测）",
        color="#93c5fd",
        edgecolor="#2563eb",
    )
    axis.bar(
        positions + width / 2,
        frame["fitted"].to_numpy(dtype=float),
        width,
        label="组均值（拟合）",
        color="#fca5a5",
        edgecolor="#dc2626",
    )
    axis.set_xticks(positions)
    axis.set_xticklabels([str(name) for name in frame.index], rotation=45, fontsize=7)
    axis.set_xlabel("分组")
    axis.set_ylabel("目标均值")
    axis.set_title(title)
    axis.legend(fontsize=8)
    axis.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    return context.save(fig, figure_name)


def _observed_correlation(first, second, method):
    from scipy import stats as sps

    first, second = np.asarray(first, dtype=float), np.asarray(second, dtype=float)
    keep = np.isfinite(first) & np.isfinite(second)
    first, second = first[keep], second[keep]
    size = int(keep.sum())
    if size < 3 or np.ptp(first) == 0 or np.ptp(second) == 0:
        return float("nan"), float("nan"), size
    function = {"pearson": sps.pearsonr, "spearman": sps.spearmanr, "kendall": sps.kendalltau}[
        method
    ]
    statistic, pvalue = function(first, second)
    return float(statistic), float(pvalue), size


@register("model.correlation")
def correlation(context):
    from scipy import stats as sps  # noqa: F401

    table = context.table
    method = context.text("method", "pearson", ("pearson", "spearman", "kendall"))
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    top_pairs = context.whole("top_pairs", 10, 1, 100)
    matrix_plot = context.flag("matrix_plot", True)
    names, matrix = registry.subset(table, context.want("columns"))
    target = table.numeric_target()

    frames = {}
    if np.isnan(matrix).any():
        context.warn(
            "相关分析按每对变量的共同有效观测计算，未自动填补；每对样本量见 observations。"
        )
    if target is not None:
        rows = []
        for index, name in enumerate(names):
            column = matrix[:, index]
            statistic, pvalue, pair_n = _observed_correlation(column, target, method)
            rows.append(
                {
                    "feature": name,
                    "observations": pair_n,
                    "r": round(float(statistic), 6),
                    "p_value": round(float(pvalue), 8),
                    "significant": bool(pvalue < alpha),
                }
            )
        frames["with_target"] = table_of(pd.DataFrame(rows), limit=60)

    full = []
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            statistic, pvalue, pair_n = _observed_correlation(
                matrix[:, left], matrix[:, right], method
            )
            if not np.isfinite(statistic) or not np.isfinite(pvalue):
                context.warn(
                    f"{names[left]} 与 {names[right]} 的有效配对不足或含常量，相关系数未定义，未纳入显著性计数。"
                )
                continue
            full.append(
                {
                    "left": names[left],
                    "right": names[right],
                    "observations": pair_n,
                    "r": round(float(statistic), 6),
                    "p_value": round(float(pvalue), 8),
                    "significant": bool(pvalue < alpha),
                }
            )
    full.sort(key=lambda item: -abs(item["r"]))
    shown = full[:top_pairs]
    adjust = context.text("p_adjust", "none", ("none", "bonferroni", "holm"))
    if adjust != "none" and full:
        order = np.argsort([item["p_value"] for item in full])
        count = len(full)
        adjusted = [None] * count
        if adjust == "bonferroni":
            for position in range(count):
                adjusted[position] = min(1.0, float(full[position]["p_value"]) * count)
        else:
            running = 0.0
            for rank, position in enumerate(order, start=1):
                value = float(full[position]["p_value"]) * (count - rank + 1)
                running = max(running, min(1.0, value))
                adjusted[position] = running
        for position, item in enumerate(full):
            item["p_adjusted"] = round(float(adjusted[position]), 8)
            item["still_significant"] = bool(adjusted[position] < alpha)
        metrics_adjusted = int(sum(1 for item in full if item["still_significant"]))
    else:
        metrics_adjusted = None
    shown = full[:top_pairs]
    if shown:
        frames["feature_pairs"] = table_of(pd.DataFrame(shown), limit=60)

    figures = []
    plot_top = context.whole("plot_top", None, 2, 50)
    drawn = names
    if plot_top is not None and len(names) > plot_top:
        strengths = [
            float(
                np.nanmax(np.abs(np.delete(np.corrcoef(matrix, rowvar=False)[position], position)))
            )
            if len(names) > 1
            else 0.0
            for position in range(len(names))
        ]
        order = np.argsort(strengths)[::-1][:plot_top]
        drawn = [names[position] for position in sorted(order)]
    if matrix_plot and len(drawn) >= 2:
        try:
            import matplotlib.pyplot as plt

            frame = pd.DataFrame(matrix, columns=names)[drawn]
            correlation = frame.corr(method=method).to_numpy(dtype=float)
            size = max(3.4, 1.0 + 0.5 * len(drawn))
            fig, axes = plt.subplots(figsize=(size, size * 0.9))
            image = axes.imshow(correlation, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
            axes.set_xticks(range(len(drawn)))
            axes.set_xticklabels(drawn, rotation=90, fontsize=7)
            axes.set_yticks(range(len(drawn)))
            axes.set_yticklabels(drawn, fontsize=7)
            for row in range(len(drawn)):
                for column in range(len(drawn)):
                    axes.text(
                        column,
                        row,
                        f"{correlation[row, column]:.2f}",
                        ha="center",
                        va="center",
                        fontsize=6,
                    )
            axes.set_title("相关矩阵热图")
            fig.colorbar(image, ax=axes, shrink=0.75)
            name = context.save(fig, "model_correlation_matrix")
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过相关矩阵图。")

    metrics = {
        "method": method,
        "features": len(names),
        "target_available": target is not None,
        "alpha": alpha,
        "top_pairs": top_pairs,
        "matrix_plot": matrix_plot,
        "p_adjust": adjust,
        "pairs_total": len(full),
        "pairs_reported": len(shown),
        "significant_pairs": int(sum(1 for item in full if item["p_value"] < alpha)),
        "significant_after_adjust": metrics_adjusted,
        "significant_with_target": int(
            sum(1 for item in frames.get("with_target", {}).get("rows", []) if item[-1])
        ),
    }
    if full:
        metrics["strongest_pair"] = f"{full[0]['left']} ~ {full[0]['right']}"
        metrics["strongest_r"] = full[0]["r"]
    if plot_top is not None:
        metrics["plot_features"] = len(drawn)
        metrics["plot_feature_names"] = list(drawn)
    return registry.result(
        "model.correlation",
        table,
        metrics=metrics,
        tables=frames,
        figures=figures,
        notes=[
            "Pearson 度量线性相关，Spearman 与 Kendall 基于秩，对异常值更稳健。",
            f"显著性按 alpha = {alpha:g} 判定。",
            "相关不等于因果；强相关也可能来自共同趋势或第三方变量。",
        ],
    )


@register("model.canonical")
def canonical(context):
    from sklearn.cross_decomposition import CCA

    table = context.table
    names, matrix = registry.subset(table, context.want("columns"))
    if len(names) < 4:
        raise MethodError("典型相关至少需要四个特征，才能分成两组。")
    scale = context.flag("standardize", True)
    default_half = len(names) // 2
    half = context.whole("split_at", default_half, 1, len(names) - 1)
    left_index = list(range(half))
    right_index = list(range(half, len(names)))
    left = matrix[:, left_index]
    right = matrix[:, right_index]

    components = min(left.shape[1], right.shape[1], context.whole("components", 2, 1, 5))
    model = CCA(n_components=components, scale=bool(scale))
    left_scores, right_scores = model.fit_transform(left, right)

    rows = []
    for index in range(components):
        correlation = float(np.corrcoef(left_scores[:, index], right_scores[:, index])[0, 1])
        rows.append(
            {
                "component": index + 1,
                "canonical_correlation": round(correlation, 6),
                "shared_variance": round(correlation**2, 6),
            }
        )
    summary = pd.DataFrame(rows)
    weights = summary["shared_variance"].to_numpy(dtype=float)
    if weights.sum() > EPS:
        weights = weights / weights.sum()
    composite = left_scores @ weights
    composite = composite - composite.min()
    if composite.max() > EPS:
        composite = composite / composite.max()

    metrics = {
        "left_group": [names[index] for index in left_index],
        "right_group": [names[index] for index in right_index],
        "components": components,
        "split_at": half,
        "standardize": bool(context.flag("standardize", True)),
        "first_correlation": round(float(summary.iloc[0]["canonical_correlation"]), 6),
        "mean_shared_variance": round(float(summary["shared_variance"].mean()), 6),
    }
    left_names = [names[index] for index in left_index]
    right_names = [names[index] for index in right_index]
    tables = {
        "components": table_of(summary),
        "left_loadings": _loadings(model.x_loadings_, left_names, context),
        "right_loadings": _loadings(model.y_loadings_, right_names, context),
    }
    notes = [
        "典型相关寻找两组变量的线性组合，使它们的相关最大。",
        "载荷表示每个变量对其典型变量的贡献方向与大小。",
    ]
    figures = []
    if bool(context.flag("loadings_plot", True)) and len(names) >= 4:
        try:
            plt = _plotting()
            left_loadings = np.atleast_2d(np.asarray(model.x_loadings_, dtype=float))[:, 0]
            right_loadings = np.atleast_2d(np.asarray(model.y_loadings_, dtype=float))[:, 0]
            left_rank = np.argsort(np.abs(left_loadings))[::-1][:8]
            right_rank = np.argsort(np.abs(right_loadings))[::-1][:8]
            first = float(summary.iloc[0]["canonical_correlation"])
            left_color = "#2563eb" if first >= 0 else "#dc2626"
            right_color = "#059669" if first >= 0 else "#d97706"
            fig, axes = plt.subplots(
                1, 3, figsize=(13.2, 4.4), gridspec_kw={"width_ratios": [1.0, 1.0, 1.1]}
            )
            axis = axes[0]
            axis.barh(np.arange(len(left_rank)), left_loadings[left_rank], color=left_color)
            axis.set_yticks(np.arange(len(left_rank)))
            axis.set_yticklabels([left_names[index] for index in left_rank], fontsize=7)
            axis.axvline(0, color="#111827", linewidth=0.8)
            axis.set_title("左组变量载荷（第一对）", fontsize=9)
            axis.grid(alpha=0.3, axis="x")
            axis = axes[1]
            axis.barh(np.arange(len(right_rank)), right_loadings[right_rank], color=right_color)
            axis.set_yticks(np.arange(len(right_rank)))
            axis.set_yticklabels([right_names[index] for index in right_rank], fontsize=7)
            axis.axvline(0, color="#111827", linewidth=0.8)
            axis.set_title("右组变量载荷（第一对）", fontsize=9)
            axis.grid(alpha=0.3, axis="x")
            axis = axes[2]
            positions = np.arange(1, components + 1)
            width = 0.38
            axis.bar(
                positions - width / 2,
                summary["canonical_correlation"].to_numpy(dtype=float),
                width,
                label="典型相关系数",
                color="#60a5fa",
            )
            axis.bar(
                positions + width / 2,
                summary["shared_variance"].to_numpy(dtype=float),
                width,
                label="共享方差 R²",
                color="#f59e0b",
            )
            for index in range(components):
                axis.text(
                    positions[index] - width / 2,
                    float(summary.iloc[index]["canonical_correlation"]),
                    f"{float(summary.iloc[index]['canonical_correlation']):.3f}",
                    ha="center",
                    va="bottom",
                    fontsize=7,
                )
                axis.text(
                    positions[index] + width / 2,
                    float(summary.iloc[index]["shared_variance"]),
                    f"{float(summary.iloc[index]['shared_variance']):.3f}",
                    ha="center",
                    va="bottom",
                    fontsize=7,
                )
            axis.set_xticks(positions)
            axis.set_xlabel("典型变量对")
            axis.set_ylim(0, 1.12)
            axis.set_title("典型相关与共享方差", fontsize=9)
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3, axis="y")
            fig.tight_layout()
            _keep(figures, context, fig, "model_canonical_loadings_and_correlations")
        except ImportError:
            context.warn("未安装 matplotlib，跳过典型相关图。")
    if context.flag("significance", False):
        test = _canonical_significance(
            summary["canonical_correlation"].to_numpy(dtype=float),
            left.shape[1],
            right.shape[1],
            matrix.shape[0],
        )
        metrics.update(
            {
                "wilks_lambda": test["wilks_lambda"],
                "chi_square": test["chi_square"],
                "df": test["df"],
                "p_value": test["p_value"],
                "significant": bool(test["p_value"] < 0.05),
            }
        )
        tables["significance"] = table_of(pd.DataFrame(test["rows"]))
        notes.append("Wilks' Lambda 的卡方近似用来判断这一对典型变量是否显著。")
    if context.flag("redundancy", False):
        left_spread = np.where(np.std(left, axis=0) <= EPS, 1.0, np.std(left, axis=0))
        right_spread = np.where(np.std(right, axis=0) <= EPS, 1.0, np.std(right, axis=0))
        left_scaled = (left - left.mean(axis=0)) / left_spread
        right_scaled = (right - right.mean(axis=0)) / right_spread
        left_variance = 0.0
        right_variance = 0.0
        for index in range(components):
            left_variance += float(
                np.mean(
                    np.corrcoef(
                        np.column_stack([left_scaled, right_scores[:, index]]), rowvar=False
                    )[: left.shape[1], left.shape[1]]
                    ** 2
                )
            )
            right_variance += float(
                np.mean(
                    np.corrcoef(
                        np.column_stack([right_scaled, left_scores[:, index]]), rowvar=False
                    )[: right.shape[1], right.shape[1]]
                    ** 2
                )
            )
        left_variance /= components
        right_variance /= components
        metrics.update(
            {
                "left_redundancy": round(left_variance, 6),
                "right_redundancy": round(right_variance, 6),
            }
        )
        tables["redundancy"] = table_of(
            pd.DataFrame(
                {
                    "quantity": ["左组被右组解释的方差比例", "右组被左组解释的方差比例"],
                    "value": numbers([left_variance, right_variance], 6),
                }
            )
        )
        notes.append(
            "冗余度衡量一组变量平均能被另一组的典型变量解释多少方差，"
            "比单个典型相关系数更能反映整体重叠程度。"
        )
    return registry.result(
        "model.canonical", table, metrics=metrics, tables=tables, figures=figures, notes=notes
    )


def _loadings(matrix, names, context):
    limit = context.whole("loadings_top", None, 1, 50)
    frame = pd.DataFrame(np.atleast_2d(matrix), index=names).reset_index()
    frame = frame.rename(columns={"index": "feature"})
    if limit is not None and not frame.empty:
        absolute = frame.drop(columns=["feature"]).abs().max(axis=1)
        frame = frame.assign(__order=absolute.to_numpy()).sort_values("__order", ascending=False)
        frame = frame.drop(columns=["__order"]).head(limit)
    return table_of(frame, limit=60)


def _canonical_significance(correlations, p, q, rows):
    from scipy import stats as sps

    items = []
    for index in range(len(correlations)):
        remaining = correlations[index:]
        wilks = float(np.prod(np.clip(1.0 - remaining**2, 1e-12, None)))
        dfree = int((p - index) * (q - index))
        statistic = float(-(rows - 1 - (p + q + 1) / 2.0) * math.log(wilks))
        pvalue = float(1 - sps.chi2.cdf(statistic, dfree)) if dfree > 0 else None
        items.append(
            {
                "component": index + 1,
                "wilks_lambda": round(wilks, 8),
                "chi_square": round(statistic, 6),
                "df": dfree,
                "p_value": None if pvalue is None else round(pvalue, 8),
            }
        )
    first = items[0]
    return {
        "wilks_lambda": first["wilks_lambda"],
        "chi_square": first["chi_square"],
        "df": first["df"],
        "p_value": first["p_value"],
        "rows": items,
    }


@register("model.vif")
def vif(context):
    from statsmodels.stats.outliers_influence import variance_inflation_factor
    from statsmodels.tools.tools import add_constant

    table = context.table
    names, matrix = registry.subset(table, context.want("columns"))
    threshold = context.number("threshold", 10.0, 1.0, 1000.0)
    if len(names) < 2:
        raise MethodError("共线性诊断至少需要两个特征。")

    def diagnose(block, block_names):
        design = add_constant(block, has_constant="add")
        values = []
        for position, name in enumerate(block_names):
            value = float(variance_inflation_factor(design, position + 1))
            values.append(
                {
                    "feature": name,
                    "vif": None if not np.isfinite(value) else round(value, 6),
                    "tolerance": None
                    if not np.isfinite(value) or value <= EPS
                    else round(1.0 / value, 6),
                }
            )
        return np.asarray(design, dtype=float), values

    design, rows = diagnose(matrix, names)
    frames = pd.DataFrame(rows)
    finite = [row["vif"] for row in rows if isinstance(row["vif"], float)]
    worst = max(rows, key=lambda row: row["vif"] if isinstance(row["vif"], float) else -1)
    over = [
        row["feature"] for row in rows if isinstance(row["vif"], float) and row["vif"] > threshold
    ]
    metrics = {
        "features": len(names),
        "max_vif": worst["vif"],
        "worst_feature": worst["feature"],
        "mean_vif": round(float(np.mean(finite)), 6) if finite else None,
        "threshold": threshold,
        "count_over_threshold": len(over),
        "over_threshold": over,
        "count_over_10": int(sum(1 for value in finite if value > 10)),
        "count_over_5": int(sum(1 for value in finite if value > 5)),
    }
    tables = {"vif": table_of(frames, limit=60)}
    notes = [
        "VIF 大于 10（或容忍度小于 0.1）通常认为存在严重共线性。",
        f"按当前阈值 {threshold:g}，有 {len(over)} 个特征超限。",
        "共线性不会让预测变差，但会让系数不稳定、难以解释单个变量的作用。",
    ]

    if context.flag("pair_table", False) and over:
        positions = [names.index(name) for name in over]
        block = pd.DataFrame(matrix[:, positions], columns=over)
        metrics["over_threshold_max_abs_r"] = round(
            float(block.corr().abs().where(~np.eye(len(over), dtype=bool)).max().max()), 6
        )
        tables["over_threshold_correlations"] = table_of(
            block.corr().reset_index().rename(columns={"index": "feature"}), limit=30
        )
        notes.append("超限变量之间的两两相关可以用来判断共线性来自哪几个变量抱团。")

    if context.flag("condition_number", False):
        metrics["condition_number"] = round(float(np.linalg.cond(design)), 6)
        notes.append(
            f"设计矩阵的条件数 {metrics['condition_number']:.4g}，"
            "超过 30 一般说明存在中等以上共线性。"
        )

    if context.flag("drop_above", False) and over:
        budget = context.whole("max_drops", 3, 1, 50)
        kept = list(names)
        index = list(range(len(names)))
        dropped = []
        current = matrix
        for _ in range(budget):
            _, current_rows = diagnose(current, kept)
            values = [
                (row["vif"] if isinstance(row["vif"], float) else -1.0, row["feature"])
                for row in current_rows
            ]
            worst_value, worst_name = max(values)
            if worst_value <= threshold:
                break
            position = kept.index(worst_name)
            kept = [name for name in kept if name != worst_name]
            index = [item for item in index if item != position]
            if len(kept) < 2:
                break
            current = matrix[:, index]
            dropped.append(
                {
                    "feature": worst_name,
                    "vif_before_drop": round(worst_value, 6),
                    "remaining": len(kept),
                }
            )
        if dropped:
            _, final_rows = diagnose(current, kept)
            metrics.update(
                {
                    "dropped_features": [item["feature"] for item in dropped],
                    "remaining_features": len(kept),
                    "max_vif_after_drop": max(
                        (row["vif"] if isinstance(row["vif"], float) else -1.0)
                        for row in final_rows
                    ),
                }
            )
            tables["dropped"] = table_of(pd.DataFrame(dropped))
            tables["vif_after_drop"] = table_of(pd.DataFrame(final_rows), limit=60)
            notes.append(
                f"已按阈值逐步剔除 {len(dropped)} 个变量，剔除后最大 VIF "
                f"{metrics['max_vif_after_drop']:.4g}。"
            )

    figures = []
    if bool(context.flag("vif_plot", True)) and frames.shape[0] >= 2:
        try:
            plt = _plotting()
            ordered = frames.assign(__value=frames["vif"].astype(float).fillna(0.0)).sort_values(
                "__value"
            )
            values = ordered["vif"].astype(float).fillna(0.0).to_numpy(dtype=float)
            colors = ["#dc2626" if value > threshold else "#93c5fd" for value in values]
            height = max(3.0, 0.3 * values.size + 1.3)
            fig, axis = plt.subplots(figsize=(6.8, height))
            axis.barh(np.arange(values.size), values, color=colors, edgecolor="#1e3a8a")
            axis.axvline(
                threshold,
                color="#dc2626",
                linewidth=1.2,
                linestyle="--",
                label=f"阈值 {threshold:g}",
            )
            axis.axvline(10.0, color="#6b7280", linewidth=0.9, linestyle=":")
            axis.set_yticks(np.arange(values.size))
            axis.set_yticklabels([str(name) for name in ordered["feature"]], fontsize=7)
            axis.set_xlabel("VIF")
            axis.set_title("方差膨胀因子")
            for position, value in enumerate(values):
                axis.text(value, position, f" {value:.1f}", va="center", fontsize=6)
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3, axis="x")
            fig.tight_layout()
            _keep(figures, context, fig, "model_vif_bar")
        except ImportError:
            context.warn("未安装 matplotlib，跳过 VIF 条形图。")

    return registry.result(
        "model.vif", table, metrics=metrics, tables=tables, figures=figures, notes=notes
    )


def _ols(context, add_constant=None, covariance=None, support_weights=False):
    import statsmodels.api as sm

    matrix, target, names = _xy(context, context.want("columns"))
    constant = context.flag("add_constant", True) if add_constant is None else bool(add_constant)
    kind = (
        context.text("covariance", "nonrobust", ("nonrobust", "HC0", "HC1", "HC3"))
        if covariance is None
        else covariance
    )
    design = _design(matrix, constant)
    fitted = sm.OLS(target, design).fit(cov_type=kind)
    if not (support_weights and context.flag("weighted", False)):
        return fitted, names, constant, None
    weights = _weights_for(context, _fit_rows(context))
    fitted = sm.WLS(target, design, weights=weights).fit(cov_type=kind)
    return fitted, names, constant, weights


@register("model.linear")
def linear(context):
    constant = context.flag("add_constant", True)
    covariance = context.text("covariance", "nonrobust", ("nonrobust", "HC0", "HC1", "HC3"))
    residual_plot = context.flag("residual_plot", True)
    fitted, names, _, weights = _ols(
        context, add_constant=constant, covariance=covariance, support_weights=True
    )
    labels = _labels(names, constant)
    rows = pd.DataFrame(
        {
            "term": labels,
            "coefficient": numbers(fitted.params, 6),
            "std_error": numbers(fitted.bse, 6),
            "t_value": numbers(fitted.tvalues, 6),
            "p_value": numbers(fitted.pvalues, 8),
        }
    )
    rows["ci_low"] = numbers(fitted.conf_int()[:, 0], 6)
    rows["ci_high"] = numbers(fitted.conf_int()[:, 1], 6)
    rows["significant"] = [bool(value < 0.05) for value in fitted.pvalues]

    predictions = np.asarray(fitted.fittedvalues, dtype=float)
    target = np.asarray(fitted.model.endog, dtype=float)
    residuals = target - predictions
    from scipy import stats as sps

    shapiro_p = None
    if 3 <= residuals.size <= 5000:
        shapiro_p = float(sps.shapiro(residuals).pvalue)

    figures = []
    if residual_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(11, 4))
            axes[0].scatter(predictions, residuals, s=14, alpha=0.7)
            axes[0].axhline(0, color="#ef4444", linewidth=1)
            axes[0].set_xlabel("拟合值")
            axes[0].set_ylabel("残差")
            axes[0].set_title("残差-拟合值")
            axes[0].grid(alpha=0.3)
            sps.probplot(residuals, dist="norm", plot=axes[1])
            axes[1].set_title("残差正态 Q-Q 图")
            axes[1].grid(alpha=0.3)
            name = context.save(fig, "model_linear_diagnostics")
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过诊断图。")

    if bool(context.flag("coefficient_plot", True)):
        try:
            intervals = np.asarray(fitted.conf_int(), dtype=float)
            coefficients = np.asarray(fitted.params, dtype=float)
            saved = _forest_plot(
                context,
                "model_linear_coefficients",
                _labels(names, constant),
                coefficients,
                intervals[:, 0],
                intervals[:, 1],
                "回归系数",
            )
            if saved:
                figures.append(saved)
        except ImportError:
            context.warn("未安装 matplotlib，跳过系数森林图。")

    tables = {"coefficients": table_of(rows, limit=60)}
    notes = [
        "系数表示该特征每增加一个单位、其它特征不变时目标的平均变化量。",
        f"标准误类型为 {covariance}；HC 系列为异方差稳健标准误。",
        "R² 高不代表因果；残差若不随拟合值随机分布，说明线性设定可能不成立。",
    ]
    extra_metrics = {}
    if weights is not None:
        weight_column = context.text("weight_column") or "1"
        weight_values = np.asarray(weights, dtype=float)
        extra_metrics.update(
            {
                "weighted": True,
                "weight_column": weight_column,
                "weight_min": round(float(weight_values.min()), 6),
                "weight_max": round(float(weight_values.max()), 6),
                "weight_mean": round(float(weight_values.mean()), 6),
            }
        )
        notes.append(
            f"已按列 {weight_column} 作为权重做加权最小二乘（WLS）；"
            "权重越大，该观测对系数的影响越强。"
        )
    if context.flag("vif", False) and len(names) >= 2:
        from statsmodels.stats.outliers_influence import variance_inflation_factor

        design = np.asarray(fitted.model.exog, dtype=float)
        offset = 1 if constant else 0
        values = [
            round(float(variance_inflation_factor(design, position + offset)), 6)
            for position in range(len(names))
        ]
        rows["vif"] = [None] + values if constant else values
        tables["coefficients"] = table_of(rows, limit=60)
        extra_metrics["max_vif"] = max(values)
        if max(values) > 10:
            notes.append(
                f"最大 VIF 为 {max(values):.4g}，存在较严重的共线性，单个系数的解释要谨慎。"
            )
    if context.flag("influence", False):
        influence = fitted.get_influence()
        cooks = np.asarray(influence.cooks_distance[0], dtype=float)
        leverage = np.asarray(influence.hat_matrix_diag, dtype=float)
        frame = pd.DataFrame(
            {
                "row": np.arange(1, cooks.size + 1),
                "cooks_distance": numbers(cooks, 6),
                "leverage": numbers(leverage, 6),
            }
        )
        frame = frame.sort_values("cooks_distance", ascending=False)
        threshold = float(4.0 / max(cooks.size, 1))
        tables["influence"] = table_of(frame, limit=30)
        extra_metrics.update(
            {
                "influential_points": int((cooks > threshold).sum()),
                "max_cooks_distance": round(float(cooks.max()), 6),
            }
        )
        notes.append(
            f"Cook 距离超过 4/n（{threshold:.4g}）的观测有 "
            f"{extra_metrics['influential_points']} 个，值得逐个检查。"
        )
    metrics = {
        "observations": int(fitted.nobs),
        "features": len(names),
        "add_constant": constant,
        "covariance": covariance,
        "residual_plot": residual_plot,
        "r_squared": round(float(fitted.rsquared), 6),
        "adjusted_r_squared": round(float(fitted.rsquared_adj), 6),
        "f_statistic": round(float(fitted.fvalue), 6),
        "f_p_value": round(float(fitted.f_pvalue), 8),
        "residual_std": round(float(np.sqrt(fitted.mse_resid)), 6),
        "durbin_watson": round(float(_durbin_watson(residuals)), 6),
        "shapiro_p": None if shapiro_p is None else round(shapiro_p, 8),
    }
    metrics.update(extra_metrics)
    return registry.result(
        "model.linear",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _regularized(context, alpha=None, l1_ratio=None, penalty="l2"):
    from sklearn.linear_model import ElasticNet, Lasso, Ridge
    from sklearn.metrics import r2_score
    from sklearn.model_selection import cross_val_score

    matrix, target, names = _xy(context, context.want("columns"))
    scaled, _, spread = registry.standardize(matrix)
    select_alpha = context.flag("select_alpha", False)
    chosen = context.number("alpha", None, 0.0, 10000.0) if alpha is None else alpha
    cv = context.whole("cv", 5, 2, 20)

    def make(value):
        if penalty == "l1":
            return Lasso(alpha=value, max_iter=20000)
        if penalty == "elastic":
            return ElasticNet(alpha=value, l1_ratio=l1_ratio or 0.5, max_iter=20000)
        return Ridge(alpha=value)

    selected_by_cv = bool(select_alpha or chosen is None)
    scoring = context.text("scoring", "r2", ("r2", "neg_mse"))
    score_name = "r2" if scoring == "r2" else "neg_mean_squared_error"
    folds = min(cv, max(len(target) // 5, 2))
    repeats = context.whole("cv_repeats", 1, 1, 20)
    curve = None
    if selected_by_cv or context.flag("cv_curve", False):
        from sklearn.model_selection import KFold

        grid = np.logspace(-4, 3, 30)
        records = []
        best, best_score = grid[0], -np.inf
        for value in grid:
            scores = []
            for repeat in range(repeats):
                splitter = (
                    folds
                    if repeats == 1
                    else KFold(n_splits=folds, shuffle=True, random_state=repeat + 11)
                )
                scores.append(
                    np.asarray(
                        cross_val_score(
                            make(value), scaled, target, cv=splitter, scoring=score_name
                        ),
                        dtype=float,
                    )
                )
            joined = np.concatenate(scores)
            mean = float(np.mean(joined))
            spread = float(np.std(joined, ddof=1)) if joined.size > 1 else 0.0
            records.append(
                {
                    "alpha": round(float(value), 8),
                    "mean_score": round(mean, 6),
                    "std_score": round(spread, 6),
                    "folds": int(folds * repeats),
                }
            )
            if mean > best_score:
                best, best_score = value, mean
        curve = pd.DataFrame(records)
        if selected_by_cv:
            chosen = float(best)

    model = make(chosen)
    model.fit(scaled, target)
    predictions = model.predict(scaled)
    coefficients = np.asarray(model.coef_, dtype=float).ravel()
    threshold = context.number("selection_threshold", 1e-8, 0.0, 1.0)
    selected = [names[index] for index in range(len(names)) if abs(coefficients[index]) > threshold]

    rows = pd.DataFrame(
        {
            "feature": names,
            "coefficient": numbers(coefficients / np.where(spread <= EPS, 1.0, spread), 6),
            "standardized": numbers(coefficients, 6),
            "nonzero": [bool(abs(value) > threshold) for value in coefficients],
        }
    )
    rows = rows.reindex(rows["standardized"].abs().sort_values(ascending=False).index)
    path = None
    if context.flag("path", False):
        records = []
        for value in np.logspace(-4, 2, 12):
            fitted = make(float(value)).fit(scaled, target)
            records.append(
                {
                    "alpha": round(float(value), 8),
                    "nonzero": int((np.abs(np.asarray(fitted.coef_)) > threshold).sum()),
                    "r_squared": round(float(r2_score(target, fitted.predict(scaled))), 6),
                }
            )
        path = pd.DataFrame(records)

    curves = None
    if context.flag("coefficient_plot", True):
        alphas = np.logspace(-4, 3, 40)
        curves = np.vstack(
            [
                np.asarray(make(float(value)).fit(scaled, target).coef_, dtype=float).ravel()
                for value in alphas
            ]
        )

    inference = None
    if context.flag("inference", False):
        design = np.column_stack([np.ones(len(target)), scaled])
        residual = np.asarray(target, dtype=float) - np.asarray(predictions, dtype=float)
        degrees = max(len(target) - design.shape[1], 1)
        variance = float(residual @ residual) / degrees
        try:
            covariance = variance * np.linalg.pinv(design.T @ design)
            errors = np.sqrt(np.clip(np.diag(covariance)[1:], 0.0, None))
        except np.linalg.LinAlgError:
            errors = np.full(len(names), np.nan)
        inference = pd.DataFrame(
            {
                "feature": names,
                "standardized": numbers(coefficients, 6),
                "std_error": numbers(errors, 6),
                "t_value": numbers(
                    np.divide(coefficients, np.where(errors <= EPS, np.nan, errors)), 6
                ),
                "significant": [
                    bool(abs(value) > 1.96)
                    for value in np.divide(coefficients, np.where(errors <= EPS, np.nan, errors))
                ],
            }
        )
    return {
        "model": model,
        "alpha": chosen,
        "names": names,
        "table": rows,
        "path": path,
        "curve": curve,
        "curves": curves,
        "inference": inference,
        "threshold": threshold,
        "metrics": {
            "alpha": round(float(chosen), 8),
            "select_alpha": selected_by_cv,
            "cv": cv,
            "cv_repeats": repeats,
            "scoring": scoring,
            "observations": int(len(target)),
            "features": len(names),
            "selected_features": len(selected),
            "r_squared": round(float(r2_score(target, predictions)), 6),
            "nonzero_coefficients": int((np.abs(coefficients) > threshold).sum()),
        },
        "selected": selected,
    }


def _with_path(outcome, tables):
    if outcome.get("path") is not None:
        tables["path"] = table_of(outcome["path"], limit=20)
    if outcome.get("curve") is not None:
        tables["cv_curve"] = table_of(outcome["curve"], limit=30)
    if outcome.get("inference") is not None:
        tables["inference"] = table_of(outcome["inference"], limit=60)
    return tables


def _regularized_result(context, method_id, outcome, notes):
    figures = []
    if bool(context.flag("coefficient_plot", True)) and outcome["curves"] is not None:
        try:
            plt = _plotting()
            alphas = np.logspace(-4, 3, outcome["curves"].shape[0])
            fig, axis = plt.subplots(figsize=(7.4, 4.4))
            for position, name in enumerate(outcome["names"]):
                axis.plot(
                    alphas,
                    outcome["curves"][:, position],
                    linewidth=1.1,
                    label=name if position < 12 else None,
                    color=COLORS[position % len(COLORS)],
                )
            axis.axvline(
                outcome["alpha"],
                color="#111827",
                linewidth=1.2,
                linestyle="--",
                label=f"alpha = {outcome['alpha']:.4g}",
            )
            axis.set_xscale("log")
            axis.set_xlabel("正则强度 alpha（对数刻度）")
            axis.set_ylabel("标准化系数")
            axis.set_title("正则化系数路径")
            if len(outcome["names"]) <= 12:
                axis.legend(fontsize=6, ncol=2)
            axis.grid(alpha=0.3)
            fig.tight_layout()
            name = context.save(fig, f"{method_id.replace('.', '_')}_coefficient_path")
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过系数路径图。")
    return registry.result(
        method_id,
        context.table,
        metrics=outcome["metrics"],
        tables=_with_path(outcome, {"coefficients": table_of(outcome["table"], limit=60)}),
        figures=figures,
        notes=notes,
    )


@register("model.ridge")
def ridge(context):
    outcome = _regularized(context, penalty="l2")
    return _regularized_result(
        context,
        "model.ridge",
        outcome,
        [
            f"岭回归使用 L2 惩罚，alpha = {outcome['alpha']:.6g}"
            f"（{'按交叉验证选取' if outcome['metrics']['select_alpha'] else '使用给定值'}）。",
            "岭回归把系数整体压缩但不置零，适合共线性强、特征都可能有用的场景。",
        ],
    )


@register("model.lasso")
def lasso(context):
    outcome = _regularized(context, penalty="l1")
    metrics = dict(outcome["metrics"])
    metrics["selected"] = outcome["selected"][:20]
    outcome["metrics"] = metrics
    return _regularized_result(
        context,
        "model.lasso",
        outcome,
        [
            f"Lasso 使用 L1 惩罚，alpha = {outcome['alpha']:.6g}"
            f"（{'按交叉验证选取' if outcome['metrics']['select_alpha'] else '使用给定值'}）。",
            "L1 会把部分系数压到 0，因此 Lasso 同时完成特征选择。",
        ],
    )


@register("model.elasticnet")
def elasticnet(context):
    ratio = context.number("l1_ratio", 0.5, 0.0, 1.0)
    outcome = _regularized(context, penalty="elastic", l1_ratio=ratio)
    metrics = dict(outcome["metrics"])
    metrics["l1_ratio"] = ratio
    outcome["metrics"] = metrics
    return _regularized_result(
        context,
        "model.elasticnet",
        outcome,
        [
            f"ElasticNet 混合 L1 与 L2，l1_ratio = {ratio}，alpha = {outcome['alpha']:.6g}"
            f"（{'按交叉验证选取' if outcome['metrics']['select_alpha'] else '使用给定值'}）。",
            "当特征高度相关时，弹性网比纯 Lasso 更稳定，会保留成组的相关特征。",
        ],
    )


def _classification_report(predicted, actual, names):
    predicted = np.asarray(predicted, dtype=int)
    actual = np.asarray(actual, dtype=int)
    rows = []
    for position, label in enumerate(names):
        target_hit = actual == position
        predicted_hit = predicted == position
        total = float(target_hit.sum())
        hit = float((target_hit & predicted_hit).sum())
        precision = hit / float(predicted_hit.sum()) if predicted_hit.sum() else None
        recall = hit / total if total else None
        if precision is None or recall is None or precision + recall <= EPS:
            f1 = None
        else:
            f1 = 2.0 * precision * recall / (precision + recall)
        rows.append(
            {
                "class": label,
                "precision": None if precision is None else round(precision, 6),
                "recall": None if recall is None else round(recall, 6),
                "f1": None if f1 is None else round(f1, 6),
                "support": int(total),
            }
        )
    accuracy = float((predicted == actual).mean()) if actual.size else None
    rows.append(
        {
            "class": "整体",
            "precision": None,
            "recall": None,
            "f1": None if accuracy is None else round(accuracy, 6),
            "support": int(actual.size),
        }
    )
    return pd.DataFrame(rows)


def _odds_plot(context, figure_name, frame, ratio=True):
    if not context.figures_enabled:
        return None
    columns = list(frame.columns)
    if ratio and "odds_ratio" in columns and "ci_low" in columns and "ci_high" in columns:
        estimates = np.asarray(frame["odds_ratio"], dtype=float)
        lows = np.asarray(frame["ci_low"], dtype=float)
        highs = np.asarray(frame["ci_high"], dtype=float)
        reference = 1.0
        label = "优势比"
    elif ratio and "coefficient" in columns and "std_error" in columns:
        coefficients = np.asarray(frame["coefficient"], dtype=float)
        error = np.asarray(frame["std_error"], dtype=float)
        with np.errstate(over="ignore", invalid="ignore"):
            estimates = np.exp(coefficients)
            lows = np.exp(coefficients - 1.96 * error)
            highs = np.exp(coefficients + 1.96 * error)
        reference = 1.0
        label = "优势比"
    else:
        estimates = np.asarray(frame["coefficient"], dtype=float)
        error = np.asarray(frame["std_error"], dtype=float)
        lows = estimates - 1.96 * error
        highs = estimates + 1.96 * error
        reference = 0.0
        label = "系数"
    term = "term" if "term" in columns else "class"
    terms = [str(value) for value in frame[term]]
    valid = _finite_forest_rows(context, estimates, lows, highs)
    keep = [index for index in valid if terms[index] != "常数项"]
    if not keep:
        keep = valid
    if not keep:
        context.warn("没有可用的估计与置信区间，不生成空森林图。")
        return None
    if "class" in columns:
        terms = [f"{label} · {name}" for label, name in zip(frame["class"], terms)]
    plt = _plotting()
    order = keep[::-1]
    positions = np.arange(len(keep))
    fig, axis = plt.subplots(figsize=(7.0, max(3.0, 0.34 * len(keep) + 1.3)))
    for position, row in zip(positions, order):
        color = "#059669" if (lows[row] > reference or highs[row] < reference) else "#6b7280"
        axis.plot([lows[row], highs[row]], [position, position], color=color, linewidth=1.6)
        axis.plot([estimates[row]], [position], marker="o", color=color, markersize=5)
    axis.axvline(reference, color="#dc2626", linewidth=1.1, linestyle="--")
    axis.set_yticks(positions)
    axis.set_yticklabels([terms[row] for row in order], fontsize=8)
    axis.set_xlabel(label)
    axis.set_title(f"{label}森林图（95% 置信区间）")
    axis.grid(alpha=0.3, axis="x")
    fig.tight_layout()
    return context.save(fig, figure_name)


@register("model.logistic")
def logistic(context):
    import statsmodels.api as sm

    from engine.methods.discrete_fit import StableMNLogit, fit_discrete, inference_arrays

    table = context.table
    kind = context.text("kind", "binary", ("binary", "multinomial"))
    constant = context.flag("add_constant", True)
    odds = context.flag("odds_ratio", True)
    cutoff = context.number("cutoff", 0.5, 0.01, 0.99)
    covariance = context.text("covariance", "nonrobust", ("nonrobust", "HC0", "HC1", "HC3"))
    matrix, target, names = _xy(context, context.want("columns"))
    labels = _aligned(context, table.labels())
    if labels is None:
        raise MethodError("逻辑回归需要目标列。")
    unique = list(pd.unique(labels))
    if len(unique) < 2:
        raise MethodError(f"逻辑回归至少需要 2 个类别，当前只有 {len(unique)} 个。")
    if len(unique) > 2:
        kind = "multinomial"
    effect_scale = context.text("effect_scale", "both", ("coef", "odds_ratio", "both"))
    fit_statistics = context.text("fit_statistics", "none", ("none", "lr", "lr_robust"))

    design = _design(matrix, constant)
    evaluation_matrix, evaluation_labels = _evaluation_data(context, names)
    evaluation_design = _design(evaluation_matrix, constant)
    if kind == "multinomial":
        categories = pd.Categorical(labels).categories
        codes = pd.Categorical(labels, categories=categories).codes
        classes = [str(value) for value in categories]
        actual = pd.Categorical(evaluation_labels, categories=categories).codes
        if (actual < 0).any():
            raise MethodError("评价集包含训练集未见的类别，请调整划分以保留各类别训练样本。")
        fitted, converged, inference = fit_discrete(
            context, StableMNLogit(codes, design), covariance
        )
        errors, statistics, pvalues = inference_arrays(fitted, inference)
        rows = []
        for index, label in enumerate(classes[1:]):
            for position, term in enumerate(_labels(names, constant)):
                rows.append(
                    {
                        "class": label,
                        "term": term,
                        "coefficient": round(float(fitted.params[position, index]), 6),
                        "std_error": round(float(errors[position, index]), 6),
                        "z_value": round(float(statistics[position, index]), 6),
                        "p_value": round(float(pvalues[position, index]), 8),
                    }
                )
        table_frame = pd.DataFrame(rows)
        probability = probabilities(fitted.predict(evaluation_design), len(actual), len(classes))
        predicted = probability.argmax(axis=1)
        accuracy = float((predicted == actual).mean()) if actual.size else None
        report_names = classes
        metrics = {
            "kind": kind,
            "classes": len(unique),
            "observations": int(fitted.nobs),
            "add_constant": constant,
            "cutoff": cutoff,
            "covariance": covariance,
            "pseudo_r_squared": round(float(fitted.prsquared), 6),
            "log_likelihood": round(float(fitted.llf), 6),
            "accuracy": None if accuracy is None else round(accuracy, 6),
            "class_names": classes,
            "reference_class": classes[0],
            "converged": converged,
            "inference_available": inference,
        }
    else:
        binary = (labels == unique[1]).astype(float) if len(unique) == 2 else target
        fitted, converged, inference = fit_discrete(context, sm.Logit(binary, design), covariance)
        errors, statistics, pvalues = inference_arrays(fitted, inference)
        rows = pd.DataFrame(
            {
                "term": _labels(names, constant),
                "coefficient": numbers(fitted.params, 6),
                "std_error": numbers(errors, 6),
                "z_value": numbers(statistics, 6),
                "p_value": numbers(pvalues, 8),
            }
        )
        if odds and inference:
            if effect_scale in ("odds_ratio", "both"):
                with np.errstate(over="ignore", invalid="ignore"):
                    rows["odds_ratio"] = numbers(np.exp(fitted.params), 6)
                    intervals = fitted.conf_int()
                    rows["ci_low"] = numbers(np.exp(intervals[:, 0]), 6)
                    rows["ci_high"] = numbers(np.exp(intervals[:, 1]), 6)
        rows["significant"] = [bool(value < 0.05) if inference else None for value in pvalues]
        table_frame = rows

        if not pd.Series(evaluation_labels).isin(unique).all():
            raise MethodError("评价集包含训练集未见的类别，请调整划分。")
        probability = probabilities(fitted.predict(evaluation_design), len(evaluation_labels))
        predicted = (probability >= cutoff).astype(int)
        actual = (evaluation_labels == unique[1]).astype(int)
        accuracy = float((predicted == actual).mean()) if actual.size else None
        metrics = {
            "kind": kind,
            "classes": len(unique),
            "observations": int(fitted.nobs),
            "add_constant": constant,
            "cutoff": cutoff,
            "covariance": covariance,
            "odds_ratio": odds,
            "pseudo_r_squared": round(float(fitted.prsquared), 6),
            "log_likelihood": round(float(fitted.llf), 6),
            "accuracy_at_threshold": None if accuracy is None else round(accuracy, 6),
            "reference_class": str(unique[0]),
            "positive_class": str(unique[-1]),
            "converged": converged,
            "inference_available": inference,
        }
        metrics.update(_confusion(predicted, actual))
        report_names = [str(unique[0]), str(unique[1])]
        if fit_statistics != "none":
            from scipy import stats as sps

            null = sm.Logit(binary, np.ones((binary.size, 1))).fit(disp=False)
            statistic = 2.0 * (float(fitted.llf) - float(null.llf))
            degrees = max(len(names) + (1 if constant else 0) - 1, 1)
            kind_fit = "似然比检验"
            if fit_statistics == "lr_robust":
                try:
                    from statsmodels.stats.diagnostic import compare_lr_test

                    test = compare_lr_test(fitted, null)
                    statistic = float(test[0])
                    kind_fit = "稳健似然比检验"
                except Exception:
                    pass
            metrics.update(
                {
                    "lr_statistic": round(statistic, 6),
                    "lr_df": int(degrees),
                    "lr_p_value": round(float(1 - sps.chi2.cdf(statistic, degrees)), 8),
                    "fit_statistics": fit_statistics,
                }
            )
            notes_fit = [
                f"{kind_fit}统计量 {statistic:.4g}（自由度 {degrees}），"
                "检验除截距外的系数是否全为 0。"
            ]
        else:
            notes_fit = []

    tables = {"coefficients": table_of(table_frame, limit=80)}
    if context.flag("classification_report", False):
        report = _classification_report(predicted, actual, report_names)
        tables["classification_report"] = table_of(report)
        metrics["classification_report"] = True
    figures = []
    if bool(context.flag("coefficient_plot", True)):
        metrics["coefficient_plot_status"] = (
            "not_generated" if inference else "unavailable_inference"
        )
        if not inference:
            figure = _classification_diagnostic(
                context, "model_logistic_classification", actual, predicted, report_names
            )
            if figure:
                metrics["diagnostic_plot"] = "confusion_matrix"
        elif effect_scale != "coef":
            figure = _odds_plot(context, "model_logistic_odds_ratio", table_frame)
        else:
            figure = _odds_plot(context, "model_logistic_coefficients", table_frame, ratio=False)
        if figure:
            figures.append(figure)
            if inference:
                metrics["coefficient_plot_status"] = "generated"
    notes = ["系数是 Logit 尺度上的变化；优势比 OR = exp(系数)，OR>1 表示该特征提高事件发生比。"]
    if kind == "binary":
        notes.append(f"分类阈值取 {cutoff:g}，预测概率达到该值才判为正类。")
        notes.extend(notes_fit)
    else:
        notes.append(
            f"多分类按最大概率判类，参照类是 {metrics['reference_class']}；"
            "cutoff 参数只在二分类生效。"
        )
        notes.append("多分类系数与指数效应都相对于参照类解释，不能当作二分类的无条件事件概率变化。")
    if not inference:
        notes.append("系数仅保留当前优化得到的数值解，不支持效应大小、显著性或优势比推断。")
    notes.append(
        "拟合统计与系数来自训练集；分类指标和分类报告来自 evaluation_scope 指定的评价样本。"
    )
    return registry.result(
        "model.logistic",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("model.probit")
def probit(context):
    import statsmodels.api as sm

    from engine.methods.discrete_fit import fit_discrete, inference_arrays

    table = context.table
    constant = context.flag("add_constant", True)
    cutoff = context.number("cutoff", 0.5, 0.01, 0.99)
    effect_scale = context.text("effect_scale", "coef", ("coef", "odds_ratio", "both"))
    covariance = context.text("covariance", "nonrobust", ("nonrobust", "HC0", "HC1", "HC3"))
    marginal_effects = context.text(
        "marginal_effects", "none", ("none", "average", "at_means", "both")
    )
    matrix, target, names = _xy(context, context.want("columns"))
    labels = _aligned(context, table.labels())
    if labels is None:
        raise MethodError("Probit 回归需要目标列。")
    unique = list(pd.unique(labels))
    if len(unique) != 2:
        raise MethodError(f"Probit 回归用于二分类，当前有 {len(unique)} 个类别。")
    binary = (labels == unique[1]).astype(float)
    design = _design(matrix, constant)
    fitted, converged, inference = fit_discrete(context, sm.Probit(binary, design), covariance)
    errors, statistics, pvalues = inference_arrays(fitted, inference)
    rows = pd.DataFrame(
        {
            "term": _labels(names, constant),
            "coefficient": numbers(fitted.params, 6),
            "std_error": numbers(errors, 6),
            "z_value": numbers(statistics, 6),
            "p_value": numbers(pvalues, 8),
        }
    )
    rows["significant"] = [bool(value < 0.05) if inference else None for value in pvalues]
    evaluation_matrix, evaluation_labels = _evaluation_data(context, names)
    if not pd.Series(evaluation_labels).isin(unique).all():
        raise MethodError("评价集包含训练集未见的类别，请调整划分。")
    probability = probabilities(
        fitted.predict(_design(evaluation_matrix, constant)), len(evaluation_labels)
    )
    predicted = (probability >= cutoff).astype(int)
    actual = (evaluation_labels == unique[1]).astype(int)
    accuracy = float((predicted == actual).mean())
    metrics = {
        "observations": int(fitted.nobs),
        "features": len(names),
        "add_constant": constant,
        "cutoff": cutoff,
        "pseudo_r_squared": round(float(fitted.prsquared), 6),
        "log_likelihood": round(float(fitted.llf), 6),
        "accuracy_at_threshold": round(accuracy, 6),
        "positive_class": str(unique[-1]),
        "converged": converged,
        "inference_available": inference,
    }
    metrics.update(_confusion(predicted, actual))
    if context.flag("odds_ratio", False) or effect_scale != "coef":
        context.warn(
            "Probit 系数的指数不是优势比；保留参数兼容，但只输出 Probit 系数与适用的边际效应。"
        )
        metrics["odds_ratio"] = False
        metrics["effect_scale"] = "coef"
    tables = {"coefficients": table_of(rows, limit=80)}
    if marginal_effects != "none":
        from scipy import stats as sps

        density = sps.norm.pdf(np.asarray(design @ fitted.params, dtype=float))
        if marginal_effects in ("average", "both"):
            effects = np.asarray(fitted.params, dtype=float) * float(density.mean())
            tables["marginal_effects"] = table_of(
                pd.DataFrame(
                    {
                        "term": _labels(names, constant),
                        "average_marginal_effect": numbers(effects, 6),
                    }
                ),
                limit=80,
            )
            metrics["max_abs_marginal_effect"] = round(float(np.abs(effects).max()), 6)
        if marginal_effects in ("at_means", "both"):
            means = np.asarray(design, dtype=float).mean(axis=0)
            at_means = np.asarray(fitted.params, dtype=float) * float(
                sps.norm.pdf(float(means @ np.asarray(fitted.params, dtype=float)))
            )
            tables["marginal_effects_at_means"] = table_of(
                pd.DataFrame(
                    {
                        "term": _labels(names, constant),
                        "marginal_effect_at_means": numbers(at_means, 6),
                    }
                ),
                limit=80,
            )
            metrics["max_abs_marginal_effect_at_means"] = round(float(np.abs(at_means).max()), 6)
    if context.flag("discrimination", False):
        from sklearn.metrics import roc_auc_score

        try:
            auc = float(roc_auc_score(actual, probability))
        except ValueError:
            auc = None
        metrics["auc"] = None if auc is None else round(auc, 6)
    if context.flag("classification_report", False):
        report = _classification_report(predicted, actual, [str(unique[0]), str(unique[1])])
        tables["classification_report"] = table_of(report)
        metrics["classification_report"] = True
    tables["coefficients"] = table_of(rows, limit=80)
    figures = []
    if bool(context.flag("coefficient_plot", True)) and len(rows) > 1:
        metrics["coefficient_plot_status"] = (
            "not_generated" if inference else "unavailable_inference"
        )
        if inference:
            figure = _odds_plot(context, "model_probit_coefficients", rows, ratio=False)
        else:
            figure = _classification_diagnostic(
                context,
                "model_probit_classification",
                actual,
                predicted,
                [str(value) for value in unique],
            )
            if figure:
                metrics["diagnostic_plot"] = "confusion_matrix"
        if figure:
            figures.append(figure)
            if inference:
                metrics["coefficient_plot_status"] = "generated"
    return registry.result(
        "model.probit",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=[
            "Probit 用标准正态分布的累积分布函数作为链接，系数解释为潜在变量的边际影响。",
            f"分类阈值取 {cutoff:g}，预测概率达到该值才判为正类。",
            "与 Logistic 回归相比，Probit 对尾部概率的假设更薄。",
        ],
    )


@register("model.robust")
def robust(context):
    import statsmodels.api as sm
    from statsmodels.robust import norms

    kind = context.text("kind", "bisquare", ("huber", "bisquare", "hampel", "andrew"))
    c = context.number("c", 1.345, 0.1, 20.0)
    constant = context.flag("add_constant", True)
    plain, names, _, _ = _ols(context, add_constant=constant, covariance="nonrobust")
    corrected, _, _, _ = _ols(context, add_constant=constant, covariance="HC3")
    estimator = {
        "huber": norms.HuberT(t=c),
        "bisquare": norms.TukeyBiweight(c=c),
        "hampel": norms.Hampel(a=c),
        "andrew": norms.AndrewWave(a=c),
    }[kind]
    design = np.asarray(plain.model.exog, dtype=float)
    target = np.asarray(plain.model.endog, dtype=float)
    max_iter = context.whole("max_iter", 50, 5, 1000)
    robust_fit = sm.RLM(target, design, M=estimator).fit(maxiter=max_iter)
    weights = np.asarray(robust_fit.weights, dtype=float)

    rows = pd.DataFrame(
        {
            "term": _labels(names, constant),
            "coefficient": numbers(plain.params, 6),
            "coefficient_robust": numbers(robust_fit.params, 6),
            "p_ols": numbers(plain.pvalues, 8),
            "std_error_ols": numbers(plain.bse, 6),
            "std_error_hc3": numbers(corrected.bse, 6),
            "p_hc3": numbers(corrected.pvalues, 8),
            "std_error_robust": numbers(robust_fit.bse, 6),
            "p_robust": numbers(robust_fit.pvalues, 8),
        }
    )
    changed_hc3 = []
    changed_robust = []
    for index, term in enumerate(_labels(names, constant)):
        if constant and index == 0:
            continue
        if bool(plain.pvalues[index] < 0.05) != bool(corrected.pvalues[index] < 0.05):
            changed_hc3.append(term)
        if bool(plain.pvalues[index] < 0.05) != bool(robust_fit.pvalues[index] < 0.05):
            changed_robust.append(term)
    plain_error = np.asarray(plain.bse, dtype=float)
    scale = np.where(plain_error <= EPS, 1.0, plain_error)
    residual = target - np.asarray(robust_fit.fittedvalues, dtype=float)
    influence = pd.DataFrame(
        {
            "observation": np.arange(1, target.size + 1),
            "observed": numbers(target, 6),
            "fitted": numbers(robust_fit.fittedvalues, 6),
            "residual": numbers(residual, 6),
            "weight": numbers(weights, 6),
        }
    ).nsmallest(min(15, target.size), "weight")
    tables = {
        "comparison": table_of(rows, limit=60),
        "downweighted_observations": table_of(influence, limit=20),
    }
    if context.flag("weight_table", False):
        distribution = pd.DataFrame(
            {
                "quantity": [
                    "权重均值",
                    "权重标准差",
                    "权重最小值",
                    "权重最大值",
                    "权重 < 0.5 的观测数",
                    "权重 < 0.9 的观测数",
                ],
                "value": numbers(
                    [
                        weights.mean(),
                        weights.std(ddof=1),
                        weights.min(),
                        weights.max(),
                        float((weights < 0.5).sum()),
                        float((weights < 0.9).sum()),
                    ],
                    6,
                ),
            }
        )
        tables["weight_summary"] = table_of(distribution)
    confidence = context.number("confidence", 0.95, 0.5, 0.999)
    interval_table = bool(context.flag("confidence_table", False))
    limit = _z_value(confidence)
    intervals = pd.DataFrame(
        {
            "term": _labels(names, constant),
            "coefficient": numbers(robust_fit.params, 6),
            "std_error": numbers(robust_fit.bse, 6),
            "ci_low": numbers(
                np.asarray(robust_fit.params, dtype=float)
                - limit * np.asarray(robust_fit.bse, dtype=float),
                6,
            ),
            "ci_high": numbers(
                np.asarray(robust_fit.params, dtype=float)
                + limit * np.asarray(robust_fit.bse, dtype=float),
                6,
            ),
        }
    )
    notes = [
        f"当前使用 {kind} 的 M 估计量（稳健常数 c = {c:g}），"
        "它通过给异常点降权来抵抗离群值对系数的影响。",
        "HC3 是异方差稳健标准误，不改变系数，只改变标准误与 p 值。",
        "相对普通最小二乘结论发生变化的项："
        + ("、".join(changed_robust) if changed_robust else "无"),
    ]
    if interval_table:
        tables["robust_intervals"] = table_of(intervals, limit=60)
        notes.append(
            f"稳健系数的 {confidence:.3g} 置信区间按正态分位点 "
            f"z = {limit:.4g} 计算（协方差为 nonrobust）。"
        )
    outlier_cutoff = None
    metrics = {}
    if context.flag("outlier_detection", False):
        outlier_cutoff = context.number("outlier_cutoff", 0.5, 0.0, 1.0)
        flagged = np.where(weights < outlier_cutoff)[0]
        metrics.update(
            {
                "outlier_cutoff": outlier_cutoff,
                "flagged_observations": int(flagged.size),
                "flagged_rows": [int(position) + 1 for position in flagged[:20]],
            }
        )
        if flagged.size:
            tables["flagged_observations"] = table_of(
                pd.DataFrame(
                    {
                        "observation": [int(position) + 1 for position in flagged],
                        "observed": numbers(target[flagged], 6),
                        "fitted": numbers(
                            np.asarray(robust_fit.fittedvalues, dtype=float)[flagged], 6
                        ),
                        "residual": numbers(residual[flagged], 6),
                        "weight": numbers(weights[flagged], 6),
                    }
                ),
                limit=40,
            )
        notes.append(
            f"权重低于 {outlier_cutoff:g} 的观测有 {flagged.size} 个，它们对稳健拟合几乎没有影响。"
        )
    if context.flag("influence_table", False):
        leverage_design = np.asarray(design, dtype=float)
        projection = (
            leverage_design
            @ np.linalg.pinv(leverage_design.T @ leverage_design)
            @ leverage_design.T
        )
        leverage = np.clip(np.asarray(projection, dtype=float).diagonal(), 0.0, 1.0 - 1e-9)
        cooks = (
            (weights**2 * residual**2 * leverage)
            / np.maximum((1.0 - leverage) ** 2, EPS)
            / max(float(robust_fit.scale) ** 2 * design.shape[1], EPS)
        )
        frame = pd.DataFrame(
            {
                "observation": np.arange(1, target.size + 1),
                "leverage": numbers(leverage, 6),
                "cooks_distance": numbers(cooks, 6),
                "weight": numbers(weights, 6),
            }
        ).sort_values("cooks_distance", ascending=False)
        tables["influence"] = table_of(frame, limit=30)
        metrics.update(
            {
                "max_leverage": round(float(np.max(leverage)), 6),
                "max_cooks_distance": round(float(np.max(cooks)), 6),
                "influential_points": int((cooks > 4.0 / max(target.size, 1)).sum()),
            }
        )
        notes.append("杠杆值与 Cook 距离用来定位既远离均值、又对系数影响大的观测。")
    figures_out = []
    if bool(context.flag("weight_plot", True)):
        try:
            plt = _plotting()
            positions = np.arange(len(intervals))
            labels_out = [str(value) for value in intervals["term"]]
            center = np.asarray(robust_fit.params, dtype=float)
            plain_center = np.asarray(plain.params, dtype=float)
            fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.4))
            axis = axes[0]
            axis.scatter(np.arange(target.size), weights, s=14, alpha=0.6, color="#2563eb")
            axis.axhline(1.0, color="#6b7280", linewidth=0.9, linestyle=":")
            if outlier_cutoff is not None:
                axis.axhline(
                    outlier_cutoff,
                    color="#dc2626",
                    linewidth=1.1,
                    linestyle="--",
                    label=f"低权重阈值 {outlier_cutoff:g}",
                )
                axis.legend(fontsize=8)
            axis.set_xlabel("观测序号")
            axis.set_ylabel("稳健权重")
            axis.set_title(f"{kind} 权重分布")
            axis.grid(alpha=0.3)
            axis = axes[1]
            width = 0.38
            axis.barh(positions - width / 2, center, width, label="稳健 M 估计", color="#059669")
            axis.barh(
                positions + width / 2, plain_center, width, label="普通最小二乘", color="#93c5fd"
            )
            axis.axvline(0.0, color="#111827", linewidth=0.9)
            axis.set_yticks(positions)
            axis.set_yticklabels(labels_out, fontsize=7)
            axis.set_title("系数对比")
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3, axis="x")
            fig.tight_layout()
            _keep(figures_out, context, fig, "model_robust_weights_and_coefficients")
        except ImportError:
            context.warn("未安装 matplotlib，跳过稳健权重图。")
    return registry.result(
        "model.robust",
        context.table,
        metrics={
            "observations": int(plain.nobs),
            "features": len(names),
            "r_squared": round(float(plain.rsquared), 6),
            "kind": kind,
            "c": c,
            "add_constant": constant,
            "max_iter": max_iter,
            "robust_scale": round(float(robust_fit.scale), 6),
            "downweighted": int((weights < 0.99).sum()),
            "min_weight": round(float(weights.min()), 6),
            "max_std_error_ratio": round(float(np.max(np.asarray(robust_fit.bse) / scale)), 6),
            "max_std_error_ratio_hc3": round(float(np.max(np.asarray(corrected.bse) / scale)), 6),
            "conclusion_changed": changed_robust,
            "conclusion_changed_hc3": changed_hc3,
        },
        tables=tables,
        figures=figures_out,
        notes=notes,
    )


def _mediation_notes(boot, seed, confidence, ci_method, draws, low, high):
    notes = [
        f"间接效应 a×b 由 {boot} 次 Bootstrap（种子 {seed}）重抽样，"
        f"给出 {confidence:.3g} 百分位置信区间，区间不包含 0 时认为中介效应成立。",
        "总效应 = 直接效应 + 间接效应；这里假设没有未观测的混淆变量。",
    ]
    if ci_method == "normal":
        notes[0] = (
            f"间接效应 a×b 由 {boot} 次 Bootstrap（种子 {seed}）重抽样，"
            f"给出 {confidence:.3g} 正态近似置信区间"
            "（Sobel 标准误），区间不包含 0 时认为中介效应成立。"
        )
    elif ci_method == "bca":
        notes[0] = (
            f"间接效应 a×b 由 {boot} 次 Bootstrap（种子 {seed}）重抽样，"
            f"给出 {confidence:.3g} 偏差校正加速（BCa）置信区间，"
            "区间不包含 0 时认为中介效应成立。"
        )
    return notes


@register("model.mediation")
def mediation(context):
    import statsmodels.api as sm

    table = context.table
    if table.numeric_target() is None:
        raise MethodError("中介效应需要数值目标列。")
    matrix, target, names = _xy(context, context.want("columns"))
    if len(names) < 2:
        raise MethodError("中介效应需要自变量与中介变量两个特征。")
    treatment = context.text("treatment") or names[0]
    mediator = context.text("mediator")
    if not mediator or mediator == treatment:
        mediator = next(name for name in names if name != treatment)
    for name in (treatment, mediator):
        if name not in names:
            raise MethodError(f"列 {name} 不在进入模型的特征中：{'、'.join(names[:10])}")
    boot = context.whole("bootstrap", 1000, 100, 10000)
    seed = context.whole("seed", 42, 0, 1000000)
    ci_method = context.text("ci_method", "percentile", ("percentile", "normal", "bca"))
    index = {name: names.index(name) for name in names}
    x = matrix[:, index[treatment]]
    m = matrix[:, index[mediator]]
    y = np.asarray(target, dtype=float)

    a, b, indirect, draws, steps = _bootstrap_draws(
        context, y, matrix, index[treatment], index[mediator], boot, seed
    )
    a_fit = sm.OLS(m, _add_constant(x.reshape(-1, 1))).fit()
    a = float(a_fit.params[1])
    both = _add_constant(np.column_stack([x, m]))
    direct_model = sm.OLS(y, both).fit()
    c_direct = float(direct_model.params[1])
    b = float(direct_model.params[2])
    total_model = sm.OLS(y, _add_constant(x.reshape(-1, 1))).fit()
    c_total = float(total_model.params[1])
    indirect = a * b
    interval_table = bool(context.flag("interval_table", False))
    confidence = context.number("confidence", 0.95, 0.5, 0.999)
    tail = (1.0 - confidence) / 2.0 * 100.0
    if draws.size >= 30:
        if ci_method == "normal":
            standard = math.sqrt(
                max(a**2 * float(direct_model.bse[2]) ** 2 + b**2 * float(a_fit.bse[1]) ** 2, 0.0)
            )
            limit = _z_value(confidence)
            low, high = indirect - limit * standard, indirect + limit * standard
        elif ci_method == "bca":
            low, high = _bca_interval(draws, indirect, steps, confidence)
        else:
            low, high = (float(value) for value in np.percentile(draws, [tail, 100.0 - tail]))
    else:
        low, high = None, None
    standard_error = float(np.nanstd(draws, ddof=1)) if draws.size > 1 else None
    total_error = float(total_model.bse[1]) if hasattr(total_model, "bse") else None
    total_ci = np.asarray(total_model.conf_int(), dtype=float)[1]
    direct_ci = np.asarray(direct_model.conf_int(), dtype=float)[1]

    rows = pd.DataFrame(
        [
            {"path": f"{treatment} → {mediator} (a)", "estimate": round(a, 6)},
            {"path": f"{mediator} → 目标 (b)", "estimate": round(b, 6)},
            {"path": f"{treatment} → 目标 总效应 (c)", "estimate": round(c_total, 6)},
            {"path": f"{treatment} → 目标 直接效应 (c')", "estimate": round(c_direct, 6)},
            {"path": "间接效应 a×b", "estimate": round(indirect, 6)},
        ]
    )
    if interval_table:
        rows["std_error"] = numbers(
            [
                float(a_fit.bse[1]),
                float(direct_model.bse[2]),
                total_error,
                float(direct_model.bse[1]),
                standard_error,
            ],
            6,
        )
        rows["ci_low"] = numbers(
            [
                float(a_fit.conf_int()[1][0]),
                float(direct_model.conf_int()[2][0]),
                float(total_ci[0]),
                float(direct_ci[0]),
                low,
            ],
            6,
        )
        rows["ci_high"] = numbers(
            [
                float(a_fit.conf_int()[1][1]),
                float(direct_model.conf_int()[2][1]),
                float(total_ci[1]),
                float(direct_ci[1]),
                high,
            ],
            6,
        )
    proportion = indirect / c_total if abs(c_total) > EPS else None
    tables = {"paths": table_of(rows)}
    if context.flag("decomposition_table", False):
        tables["effect_decomposition"] = table_of(
            pd.DataFrame(
                {
                    "quantity": [
                        "间接效应 a×b",
                        "直接效应 c'",
                        "总效应 c",
                        "中介占比（间接/总）",
                        "间接与直接之比",
                    ],
                    "value": numbers(
                        [
                            indirect,
                            c_direct,
                            c_total,
                            indirect / c_total if abs(c_total) > EPS else np.nan,
                            indirect / c_direct if abs(c_direct) > EPS else np.nan,
                        ],
                        6,
                    ),
                }
            )
        )
    if context.flag("bootstrap_table", False) and draws.size:
        tables["bootstrap_distribution"] = table_of(
            pd.DataFrame(
                {
                    "quantity": ["重抽样次数", "均值", "标准差", "最小值", "最大值"],
                    "value": numbers(
                        [draws.size, draws.mean(), draws.std(ddof=1), draws.min(), draws.max()], 6
                    ),
                }
            )
        )
    figures = []
    if bool(context.flag("effect_plot", True)):
        try:
            name = _mediation_panel(
                context,
                treatment,
                mediator,
                "目标",
                {
                    "a": a,
                    "b": b,
                    "direct": c_direct,
                    "indirect": indirect,
                    "draws": draws,
                    "low": low,
                    "high": high,
                },
            )
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过中介路径图。")
    metrics = {
        "treatment": treatment,
        "mediator": mediator,
        "a": round(a, 6),
        "b": round(b, 6),
        "total_effect": round(c_total, 6),
        "direct_effect": round(c_direct, 6),
        "indirect_effect": round(indirect, 6),
        "proportion_mediated": None if proportion is None else round(proportion, 6),
        "bootstrap": boot,
        "seed": seed,
        "confidence": confidence,
        "bootstrap_draws": int(draws.size),
        "ci_low": None if low is None else round(float(low), 6),
        "ci_high": None if high is None else round(float(high), 6),
        "significant_indirect": None if low is None else bool(low > 0 or high < 0),
    }
    if ci_method != "percentile":
        metrics["ci_method"] = ci_method
    return registry.result(
        "model.mediation",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=_mediation_notes(boot, seed, confidence, ci_method, draws, low, high),
    )


@register("model.moderation")
def moderation(context):
    import statsmodels.api as sm

    table = context.table
    if table.numeric_target() is None:
        raise MethodError("调节效应需要数值目标列。")
    matrix, target, names = _xy(context, context.want("columns"))
    if len(names) < 2:
        raise MethodError("调节效应需要自变量与调节变量两个特征。")
    focal = context.text("focal") or names[0]
    moderator = context.text("moderator")
    if not moderator or moderator == focal:
        moderator = next(name for name in names if name != focal)
    for name in (focal, moderator):
        if name not in names:
            raise MethodError(f"列 {name} 不在进入模型的特征中：{'、'.join(names[:10])}")
    centered = context.flag("center", True)
    show_slopes = context.flag("simple_slopes", True)
    slope_points = context.whole("slope_points", 3, 2, 7)
    probe_range = context.number("probe_range", 1.0, 0.5, 3.0)
    report_slope_ci = bool(context.flag("slope_intervals", False))
    confidence = context.number("confidence", 0.95, 0.5, 0.999)
    index = {name: names.index(name) for name in names}
    x = matrix[:, index[focal]]
    w = matrix[:, index[moderator]]
    y = np.asarray(target, dtype=float)

    if centered:
        xc = x - x.mean()
        wc = w - w.mean()
    else:
        xc = np.asarray(x, dtype=float).copy()
        wc = np.asarray(w, dtype=float).copy()
    interaction = xc * wc
    design = _add_constant(np.column_stack([xc, wc, interaction]))
    fitted = sm.OLS(y, design).fit()
    beta = float(fitted.params[3])
    pvalue = float(fitted.pvalues[3])

    spread = float(wc.std(ddof=1)) if wc.size > 1 else 0.0
    simple = []
    if show_slopes:
        from scipy import stats as sps

        centre = float(wc.mean())
        critical = float(sps.t.ppf(0.5 + confidence / 2.0, fitted.df_resid))
        for offset in np.linspace(-probe_range, probe_range, slope_points):
            probe = centre + float(offset) * spread
            label = (
                "均值"
                if abs(offset) < 1e-9
                else (
                    "高（+1 SD）"
                    if abs(offset - 1.0) < 1e-9
                    else ("低（-1 SD）" if abs(offset + 1.0) < 1e-9 else f"{offset:+.2f} SD")
                )
            )
            point = float(fitted.params[1] + beta * probe)
            variance = (
                fitted.cov_params()[1, 1]
                + 2 * probe * fitted.cov_params()[1, 3]
                + probe**2 * fitted.cov_params()[3, 3]
            )
            error = math.sqrt(max(float(variance), EPS))
            statistic = point / error
            record = {
                "moderator_level": label,
                "moderator_value": round(probe, 6),
                "slope": round(point, 6),
                "std_error": round(error, 6),
                "p_value": round(float(2 * (1 - sps.t.cdf(abs(statistic), fitted.df_resid))), 8),
            }
            if report_slope_ci:
                record["ci_low"] = round(point - critical * error, 6)
                record["ci_high"] = round(point + critical * error, 6)
            simple.append(record)
        slopes = pd.DataFrame(simple)
    else:
        slopes = None

    suffix = "（中心化）" if centered else ""
    rows = pd.DataFrame(
        {
            "term": _labels([f"{focal}{suffix}", f"{moderator}{suffix}", f"{focal}×{moderator}"]),
            "coefficient": numbers(fitted.params, 6),
            "std_error": numbers(fitted.bse, 6),
            "t_value": numbers(fitted.tvalues, 6),
            "p_value": numbers(fitted.pvalues, 8),
        }
    )
    tables = {"coefficients": table_of(rows)}
    if show_slopes:
        tables["simple_slopes"] = table_of(slopes)
    figures = []
    if bool(context.flag("interaction_plot", True)):
        try:
            plt = _plotting()
            points = _curve_points(xc, count=25)
            if slopes is not None:
                probes = [(row["moderator_level"], float(row["moderator_value"])) for row in simple]
            else:
                probes = [
                    ("低（-1 SD）", float(wc.mean()) - spread),
                    ("均值", float(wc.mean())),
                    ("高（+1 SD）", float(wc.mean()) + spread),
                ]
            fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.4))
            for position, (label, probe) in enumerate(probes):
                line = (
                    float(fitted.params[0])
                    + float(fitted.params[1]) * points
                    + float(fitted.params[2]) * probe
                    + beta * points * probe
                )
                axes[0].plot(
                    points,
                    line,
                    linewidth=1.6,
                    color=COLORS[position % len(COLORS)],
                    label=f"调节变量 {label}",
                )
            axes[0].scatter(xc, y, s=10, alpha=0.25, color="#6b7280")
            axes[0].set_xlabel(f"{focal}{suffix}")
            axes[0].set_ylabel("目标")
            axes[0].set_title("不同调节水平下的简单斜率")
            axes[0].legend(fontsize=7)
            axes[0].grid(alpha=0.3)
            tertiles = np.quantile(wc, [1.0 / 3.0, 2.0 / 3.0])
            bands = np.digitize(wc, tertiles)
            for position, name in enumerate(["低", "中", "高"]):
                pick = np.asarray(xc)[bands == position]
                if pick.size:
                    axes[1].hist(
                        pick,
                        bins=12,
                        alpha=0.5,
                        color=COLORS[position % len(COLORS)],
                        label=f"调节{name}",
                    )
            axes[1].set_xlabel(f"{focal}{suffix}")
            axes[1].set_ylabel("频数")
            axes[1].set_title("调节变量三分组的自变量分布")
            axes[1].legend(fontsize=7)
            axes[1].grid(alpha=0.3)
            fig.tight_layout()
            name = context.save(fig, "model_moderation_interaction")
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过调节效应图。")
    return registry.result(
        "model.moderation",
        context.table,
        metrics={
            "focal": focal,
            "moderator": moderator,
            "center": centered,
            "simple_slopes": show_slopes,
            "slope_points": slope_points,
            "interaction_beta": round(beta, 6),
            "interaction_p": round(pvalue, 8),
            "moderation_significant": bool(pvalue < 0.05),
            "r_squared": round(float(fitted.rsquared), 6),
        },
        tables=tables,
        figures=figures,
        notes=[
            "交互项显著说明自变量对目标的影响随调节变量取值而变化。",
            "变量已中心化，避免交互项与主效应产生非本质共线性。"
            if centered
            else "变量未中心化，主效应表示调节变量取 0 时的条件效应。",
            f"简单斜率在调节变量的 {slope_points} 个取值点上检验。"
            if not report_slope_ci
            else f"简单斜率在调节变量的 {slope_points} 个取值点上检验"
            f"（{confidence:.3g} 置信区间）。"
            if show_slopes
            else "未输出简单斜率检验。",
        ],
    )


@register("model.chained")
def chained(context):
    import statsmodels.api as sm

    table = context.table
    if table.numeric_target() is None:
        raise MethodError("链式中介需要数值目标列。")
    matrix, target, names = _xy(context, context.want("columns"))
    if len(names) < 3:
        raise MethodError("链式中介至少需要自变量和两个中介变量。")
    treatment = context.text("treatment") or names[0]
    chain = [name for name in names if name != treatment]
    if len(chain) < 2:
        raise MethodError("至少需要两个中介变量。")
    boot = context.whole("bootstrap", 1000, 100, 10000)
    seed = context.whole("seed", 42, 0, 1000000)
    ci_method = context.text("ci_method", "percentile", ("percentile", "normal", "bca"))
    first, second = chain[0], chain[1]
    index = {name: names.index(name) for name in names}
    x = matrix[:, index[treatment]]
    m1 = matrix[:, index[first]]
    m2 = matrix[:, index[second]]
    y = np.asarray(target, dtype=float)

    def fit(response, predictors):
        design = _add_constant(np.column_stack(predictors))
        return sm.OLS(response, design).fit()

    def effects(responses, treatment_values, first_values, second_values):
        a1_value = float(_coefficients(first_values, [treatment_values])[1])
        second_fit = _coefficients(second_values, [treatment_values, first_values])
        a2_value = float(second_fit[1])
        d21_value = float(second_fit[2])
        final_fit = _coefficients(responses, [treatment_values, first_values, second_values])
        b1_value = float(final_fit[2])
        b2_value = float(final_fit[3])
        direct_value = float(final_fit[1])
        first_part = a1_value * b1_value
        second_part = a2_value * b2_value
        chain_part = a1_value * d21_value * b2_value
        return {
            "a1": a1_value,
            "a2": a2_value,
            "d21": d21_value,
            "b1": b1_value,
            "b2": b2_value,
            "direct": direct_value,
            "first_indirect": first_part,
            "second_indirect": second_part,
            "chain_indirect": chain_part,
            "total_indirect": first_part + second_part + chain_part,
        }

    a1 = float(fit(m1, [x]).params[1])
    a2 = float(fit(m2, [x, m1]).params[1])
    d21 = float(fit(m2, [x, m1]).params[2])
    final = fit(y, [x, m1, m2])
    b1 = float(final.params[2])
    b2 = float(final.params[3])
    direct = float(final.params[1])
    first_indirect = a1 * b1
    second_indirect = a2 * b2
    chain_indirect = a1 * d21 * b2
    total_indirect = first_indirect + second_indirect + chain_indirect

    rng = np.random.default_rng(seed)
    draws = []
    steps = []
    size = y.size
    for _ in range(boot):
        pick = rng.integers(0, size, size)
        try:
            draws.append(effects(y[pick], x[pick], m1[pick], m2[pick])["total_indirect"])
        except Exception:
            continue
    draws = np.asarray(draws, dtype=float)
    for position in _jackknife_positions(size):
        keep = np.ones(size, dtype=bool)
        keep[position] = False
        try:
            steps.append(effects(y[keep], x[keep], m1[keep], m2[keep])["total_indirect"])
        except Exception:
            steps.append(total_indirect)
    steps = np.asarray(steps, dtype=float)
    confidence = context.number("confidence", 0.95, 0.5, 0.999)
    tail = (1.0 - confidence) / 2.0 * 100.0
    if draws.size >= 30:
        if ci_method == "normal":
            limit = _z_value(confidence)
            standard = float(np.nanstd(draws, ddof=1))
            low, high = total_indirect - limit * standard, total_indirect + limit * standard
        elif ci_method == "bca":
            low, high = _bca_interval(draws, total_indirect, steps, confidence)
        else:
            low, high = (float(value) for value in np.percentile(draws, [tail, 100.0 - tail]))
    else:
        low, high = None, None

    rows = pd.DataFrame(
        [
            {"path": f"{treatment} → {first} (a1)", "estimate": round(a1, 6)},
            {"path": f"{treatment} → {second} (a2)", "estimate": round(a2, 6)},
            {"path": f"{first} → {second} (d21)", "estimate": round(d21, 6)},
            {"path": f"{first} → 目标 (b1)", "estimate": round(b1, 6)},
            {"path": f"{second} → 目标 (b2)", "estimate": round(b2, 6)},
            {"path": f"{treatment} → 目标 直接效应", "estimate": round(direct, 6)},
            {"path": f"间接：{treatment}→{first}→目标", "estimate": round(first_indirect, 6)},
            {"path": f"间接：{treatment}→{second}→目标", "estimate": round(second_indirect, 6)},
            {
                "path": f"链式：{treatment}→{first}→{second}→目标",
                "estimate": round(chain_indirect, 6),
            },
            {"path": "间接效应合计", "estimate": round(total_indirect, 6)},
        ]
    )
    if context.flag("interval_table", False):
        rows["std_error"] = numbers(
            [
                float(fit(m1, [x]).bse[1]),
                float(fit(m2, [x, m1]).bse[1]),
                float(fit(m2, [x, m1]).bse[2]),
                float(final.bse[2]),
                float(final.bse[3]),
                float(final.bse[1]),
                None,
                None,
                None,
                None if draws.size < 2 else float(np.nanstd(draws, ddof=1)),
            ],
            6,
        )
    tables = {"paths": table_of(rows)}
    if context.flag("bootstrap_table", False):
        tables["effect_decomposition"] = table_of(
            pd.DataFrame(
                {
                    "quantity": [
                        "间接：经第一个中介",
                        "间接：经第二个中介",
                        "链式间接",
                        "间接效应合计",
                        "直接效应",
                        "间接与直接之比",
                    ],
                    "value": numbers(
                        [
                            first_indirect,
                            second_indirect,
                            chain_indirect,
                            total_indirect,
                            direct,
                            total_indirect / direct if abs(direct) > EPS else np.nan,
                        ],
                        6,
                    ),
                }
            )
        )
    if context.flag("distribution_table", False) and draws.size:
        tables["bootstrap_distribution"] = table_of(
            pd.DataFrame(
                {
                    "quantity": ["重抽样次数", "均值", "标准差", "最小值", "最大值"],
                    "value": numbers(
                        [draws.size, draws.mean(), draws.std(ddof=1), draws.min(), draws.max()], 6
                    ),
                }
            )
        )
    figures = []
    if bool(context.flag("chain_plot", True)):
        try:
            plt = _plotting()
            moves = [
                f"{treatment}→{first}",
                f"{treatment}→{second}",
                f"{first}→{second}",
                f"{first}→目标",
                f"{second}→目标",
            ]
            values_bars = [a1, a2, d21, b1, b2]
            fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.3))
            axis = axes[0]
            axis.barh(
                np.arange(len(moves)),
                values_bars,
                color=["#2563eb" if value >= 0 else "#dc2626" for value in values_bars],
            )
            axis.axvline(0.0, color="#111827", linewidth=0.9)
            axis.set_yticks(np.arange(len(moves)))
            axis.set_yticklabels(moves, fontsize=8)
            axis.set_xlabel("路径系数")
            axis.set_title("链式路径系数")
            axis.grid(alpha=0.3, axis="x")
            axis = axes[1]
            pieces = [first_indirect, second_indirect, chain_indirect, direct]
            names_pieces = [f"间接：经{first}", f"间接：经{second}", "链式间接", "直接效应"]
            axis.bar(
                np.arange(len(pieces)), pieces, color=["#2563eb", "#0891b2", "#7c3aed", "#dc2626"]
            )
            axis.axhline(0.0, color="#111827", linewidth=0.9)
            axis.set_xticks(np.arange(len(pieces)))
            axis.set_xticklabels(names_pieces, rotation=20, fontsize=8)
            axis.set_ylabel("效应大小")
            axis.set_title("效应分解")
            axis.grid(alpha=0.3, axis="y")
            fig.tight_layout()
            name = context.save(fig, "model_chained_paths_and_effects")
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过链式路径图。")
    labels = {"percentile": "百分位", "normal": "正态近似", "bca": "偏差校正加速（BCa）"}
    notes = [
        "链式间接效应等于 a1 × d21 × b2，表示依次经过两个中介的传导。",
        f"间接效应合计由 {boot} 次 Bootstrap（种子 {seed}）重抽样，"
        f"给出 {confidence:.3g} 百分位置信区间，区间不包含 0 时认为间接效应成立。",
    ]
    if ci_method != "percentile":
        notes[1] = (
            f"间接效应合计由 {boot} 次 Bootstrap（种子 {seed}）重抽样，"
            f"给出 {confidence:.3g} {labels[ci_method]}置信区间，"
            "区间不包含 0 时认为间接效应成立。"
        )
    return registry.result(
        "model.chained",
        context.table,
        metrics={
            "treatment": treatment,
            "mediators": [first, second],
            "bootstrap": boot,
            "seed": seed,
            "confidence": confidence,
            "ci_method": ci_method,
            "bootstrap_draws": int(draws.size),
            "ci_low": None if low is None else round(float(low), 6),
            "ci_high": None if high is None else round(float(high), 6),
            "significant_indirect": None if low is None else bool(low > 0 or high < 0),
            "first_indirect": round(first_indirect, 6),
            "second_indirect": round(second_indirect, 6),
            "chain_indirect": round(chain_indirect, 6),
            "total_indirect": round(total_indirect, 6),
            "direct_effect": round(direct, 6),
            "r_squared": round(float(final.rsquared), 6),
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _glm(context, family, label, max_iter=None):
    import statsmodels.api as sm

    matrix, target, names = _xy(context, context.want("columns"))
    constant = context.flag("add_constant", True)
    scale_check = context.flag("scale_check", True) if family == "gamma" else True
    if family in ("poisson", "quasipoisson", "gamma", "nb") and (target < 0).any():
        raise MethodError(f"{label}要求目标非负，当前存在负值。")
    if family == "gamma":
        zeros = int((target <= 0).sum())
        if zeros:
            raise MethodError(
                f"Gamma 回归要求响应严格为正，当前有 {zeros} 个观测小于等于 0"
                f"（最小值 {float(target.min()):.4g}）。"
                "若响应是计数，请改用泊松或负二项；若响应是分类取值，请改用 Logistic。"
            )
        distinct = int(np.unique(np.round(target, 10)).size)
        if distinct <= 5 and distinct < max(6, target.size * 0.05):
            raise MethodError(
                f"Gamma 回归要求连续的正响应，当前目标只有 {distinct} 个不同取值"
                "（看起来是分类或有序取值）。请改用 Logistic、有序回归或泊松。"
            )
    if family in ("poisson", "quasipoisson", "nb") and not np.allclose(target, np.round(target)):
        context.warn("泊松回归假定计数响应，目标列含非整数，请确认是否合适。")
    design = _design(matrix, constant)

    scale = 1.0
    response = target
    magnitude = float(np.mean(np.abs(target)))
    if family == "gamma" and scale_check and magnitude > 0 and not 0.1 <= magnitude <= 1000.0:
        scale = 1.0 / magnitude
        response = target * scale
        context.warn(
            f"目标均值约 {magnitude:.4g}，Gamma 回归在该尺度下无法收敛，"
            "已按比例缩放后拟合；下表系数已换算回原始尺度。"
        )

    dispersion = None
    covariance = context.text("covariance", "nonrobust", ("nonrobust", "HC0", "HC1", "HC3"))
    max_iter = context.whole("max_iter", 100, 10, 2000) if max_iter is None else int(max_iter)
    link_name = (
        context.text("link", "log", ("log", "identity", "inverse")) if family == "gamma" else "log"
    )
    links = {
        "log": sm.families.links.Log(),
        "identity": sm.families.links.Identity(),
        "inverse": sm.families.links.InversePower(),
    }
    chosen = {
        "poisson": sm.families.Poisson(),
        "nb": sm.families.Poisson(),
        "gamma": sm.families.Gamma(link=links[link_name]),
        "gaussian": sm.families.Gaussian(),
    }[family if family != "quasipoisson" else "poisson"]
    try:
        if family == "nb":
            seed_fit = sm.GLM(response, design, family=sm.families.Poisson()).fit()
            mean = np.asarray(seed_fit.fittedvalues, dtype=float)
            dispersion = max(
                (float(seed_fit.pearson_chi2) - float(seed_fit.df_resid))
                / max(float(np.sum(mean**2)), EPS),
                1e-8,
            )
            for _ in range(15):
                fitted = sm.GLM(
                    response, design, family=sm.families.NegativeBinomial(alpha=dispersion)
                ).fit()
                mean = np.asarray(fitted.fittedvalues, dtype=float)
                updated = max(
                    (float(fitted.pearson_chi2) - float(fitted.df_resid))
                    / max(float(np.sum(mean**2)), EPS),
                    1e-8,
                )
                settled = abs(updated - dispersion) <= 1e-9 * max(dispersion, 1e-8)
                dispersion = updated
                if settled:
                    break
            fitted = sm.GLM(
                response, design, family=sm.families.NegativeBinomial(alpha=dispersion)
            ).fit()
        elif family == "quasipoisson":
            fitted = sm.GLM(response, design, family=chosen).fit(scale="X2")
        else:
            fitted = sm.GLM(response, design, family=chosen).fit(
                maxiter=max_iter, cov_type=covariance
            )
    except Exception as error:
        raise MethodError(f"{label}拟合失败：{error}")

    coefficients = np.asarray(fitted.params, dtype=float).copy()
    errors = np.asarray(fitted.bse, dtype=float).copy()
    if scale != 1.0:
        coefficients[0] -= math.log(scale)
    history = getattr(fitted, "fit_history", None)
    iterations = None
    if isinstance(history, dict):
        record = history.get("iteration")
        iterations = (
            record if isinstance(record, int) else (None if record is None else len(record))
        )
    return {
        "family": family,
        "names": names,
        "constant": constant,
        "scale": scale,
        "scale_check": scale_check,
        "link": link_name,
        "covariance": covariance,
        "design": np.asarray(design, dtype=float),
        "iterations": iterations,
        "max_iter": max_iter,
        "converged": bool(getattr(fitted, "converged", True)),
        "coefficients": coefficients,
        "errors": errors,
        "nobs": int(fitted.nobs),
        "deviance": float(fitted.deviance),
        "pearson_chi2": float(fitted.pearson_chi2),
        "aic": float(fitted.aic),
        "dispersion": dispersion,
        "log_likelihood": float(fitted.llf),
        "pseudo_r_squared": float(1 - fitted.deviance / max(fitted.null_deviance, EPS)),
        "model_scale": float(fitted.scale),
        "model": fitted,
        "fitted_values": np.asarray(fitted.fittedvalues, dtype=float),
        "tvalues": np.asarray(fitted.tvalues, dtype=float),
        "pvalues": np.asarray(fitted.pvalues, dtype=float),
        "rate_ratio": family in ("poisson", "quasipoisson"),
    }


def _glm_table(outcome):
    rows = pd.DataFrame(
        {
            "term": _labels(outcome["names"], outcome["constant"]),
            "coefficient": numbers(outcome["coefficients"], 6),
            "std_error": numbers(outcome["errors"], 6),
            "z_value": numbers(outcome["tvalues"], 6),
            "p_value": numbers(outcome["pvalues"], 8),
        }
    )
    if outcome["rate_ratio"]:
        rows["rate_ratio"] = numbers(np.exp(np.clip(outcome["coefficients"], -500, 500)), 6)
    rows["significant"] = [bool(value < 0.05) for value in outcome["pvalues"]]
    return rows


def _blup_plot(context, figure_name, effects, groups, values, fitted_values, limit, order):
    plt = _plotting()
    labels = [str(key) for key in effects]
    magnitudes = [float(np.asarray(value, dtype=float).ravel()[0]) for value in effects.values()]
    frame = pd.DataFrame({"group": labels, "blup": magnitudes})
    if order == "value":
        frame = frame.reindex(frame["blup"].abs().sort_values(ascending=False).index)
    else:
        frame = frame.sort_values("group")
    frame = frame.head(int(limit)).iloc[::-1]
    plotted = [str(name) for name in frame["group"]]
    positions = np.arange(frame.shape[0])
    colors = ["#2563eb" if value >= 0 else "#dc2626" for value in frame["blup"]]
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.4))
    axes[0].barh(positions, frame["blup"].to_numpy(dtype=float), color=colors)
    axes[0].axvline(0.0, color="#111827", linewidth=0.9)
    axes[0].set_yticks(positions)
    axes[0].set_yticklabels([str(name) for name in frame["group"]], fontsize=7)
    axes[0].set_xlabel("随机效应（BLUP）")
    axes[0].set_title("各组的随机效应")
    axes[0].grid(alpha=0.3, axis="x")
    groups_array = np.asarray([str(value) for value in groups])
    observed = pd.Series(np.asarray(values, dtype=float)).groupby(groups_array, sort=False).mean()
    predicted = (
        pd.Series(np.asarray(fitted_values, dtype=float)).groupby(groups_array, sort=False).mean()
    )
    matched = pd.DataFrame({"observed": observed, "fitted": predicted}).dropna()
    axes[1].scatter(matched["observed"], matched["fitted"], s=24, color="#059669")
    if matched.shape[0] >= 2:
        span = [float(min(matched.min())), float(max(matched.max()))]
        axes[1].plot(
            span, span, color="#dc2626", linewidth=1.0, linestyle="--", label="观测 = 拟合"
        )
        axes[1].legend(fontsize=8)
    axes[1].set_xlabel("组均值（观测）")
    axes[1].set_ylabel("组均值（拟合）")
    axes[1].set_title("组均值拟合对比")
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    return context.save(fig, figure_name), plotted


def _glm_metrics(outcome):
    return {
        "observations": outcome["nobs"],
        "features": len(outcome["names"]),
        "family": outcome["family"],
        "add_constant": outcome["constant"],
        "deviance": None if outcome["deviance"] is None else round(float(outcome["deviance"]), 6),
        "pearson_chi2": round(float(outcome["pearson_chi2"]), 6),
        "aic": round(float(outcome["aic"]), 6),
        "pseudo_r_squared": round(float(outcome["pseudo_r_squared"]), 6),
    }


def _fit_diagnostics(outcome, default_iter):
    if outcome.get("max_iter") == default_iter:
        return {}
    result = {"converged": bool(outcome["converged"]), "max_iter": int(outcome["max_iter"])}
    if outcome.get("iterations") is not None:
        result["iterations"] = int(outcome["iterations"])
    return result


def _mean_curve(context, figure_name, label, outcome, confidence, asked=None):
    plt = _plotting()
    names = outcome["names"]
    matrix, target, _ = _xy(context, context.want("columns"))
    mean, spread = _variable_summary(matrix)
    position = None
    chosen = _chosen_column(names, asked)
    if chosen is not None:
        position = names.index(chosen)
    points = _curve_points(matrix[:, position] if position is not None else matrix[:, 0])
    grid = _design_grid(matrix, position, points, mean, spread)
    design = _design(grid, outcome["constant"])
    coefficients = np.asarray(outcome["coefficients"], dtype=float)
    linear = np.asarray(design @ coefficients, dtype=float)
    link = outcome["link"]
    if outcome["family"] == "gamma":
        if link == "identity":
            fitted = linear
            tangent = np.ones_like(linear)
        elif link == "inverse":
            fitted = 1.0 / np.clip(linear, EPS, None)
            tangent = -1.0 / np.clip(linear**2, EPS, None)
        else:
            fitted = np.exp(np.clip(linear, -50.0, 50.0))
            tangent = fitted
    else:
        fitted = np.exp(np.clip(linear, -50.0, 50.0))
        tangent = fitted
    variance = np.asarray(outcome["model"].cov_params(), dtype=float)
    linear_error = np.sqrt(np.clip(np.einsum("ij,jk,ik->i", design, variance, design), 0.0, None))
    interval = _z_value(confidence)
    lower = fitted - interval * np.abs(tangent) * linear_error
    upper = fitted + interval * np.abs(tangent) * linear_error
    observed = np.asarray(target, dtype=float)
    fig, axis = plt.subplots(figsize=(7.4, 4.4))
    axis.scatter(
        matrix[:, position] if position is not None else matrix[:, 0],
        observed,
        s=16,
        alpha=0.4,
        color="#6b7280",
        label="观测值",
    )
    axis.plot(points, fitted, color="#2563eb", linewidth=1.8, label="预测均值")
    axis.fill_between(
        points,
        np.clip(lower, 0.0, None),
        np.clip(upper, 0.0, None),
        color="#93c5fd",
        alpha=0.35,
        label=f"{confidence:.3g} 置信区间",
    )
    if outcome["rate_ratio"]:
        axis.set_yscale("log")
    axis.set_xlabel(f"{chosen}（其余变量取均值）")
    axis.set_ylabel("预测均值")
    axis.set_title(f"{label}回归预测均值曲线")
    axis.legend(fontsize=8)
    axis.grid(alpha=0.3)
    fig.tight_layout()
    return context.save(fig, figure_name)


@register("model.poisson")
def poisson(context):
    family = context.text("family", "poisson", ("poisson", "quasipoisson", "nb"))
    dispersion_check = context.flag("dispersion_check", True)
    label = {"poisson": "泊松回归", "quasipoisson": "准泊松回归", "nb": "负二项回归"}[family]
    outcome = _glm(context, family, label)
    width = len(outcome["names"]) + (1 if outcome["constant"] else 0)
    degrees = outcome["nobs"] - width
    ratio = None if degrees <= 0 else float(outcome["pearson_chi2"]) / degrees
    metrics = _glm_metrics(outcome)
    metrics["family"] = family
    metrics["dispersion_check"] = dispersion_check
    metrics["dispersion_ratio"] = None if ratio is None else round(ratio, 6)
    metrics["overdispersed"] = None if ratio is None else bool(ratio > 1.5)
    if family == "nb":
        metrics["dispersion"] = round(float(outcome["dispersion"]), 8)
    if family == "quasipoisson":
        metrics["dispersion"] = round(float(outcome["model_scale"]), 8)
    if dispersion_check and ratio is not None and ratio > 1.5:
        context.warn(
            f"Pearson 卡方与自由度之比为 {ratio:.3g}，明显大于 1，"
            "说明存在过度离散，建议改用准泊松或负二项模型。"
        )
    metrics.update(_fit_diagnostics(outcome, 100))
    tables = {"coefficients": table_of(_glm_table(outcome), limit=60)}
    confidence = context.number("confidence", 0.95, 0.5, 0.999)
    z = _z_value(confidence)
    if context.flag("rate_ci", False) and outcome["rate_ratio"]:
        errors = np.asarray(outcome["errors"], dtype=float)
        coefficients = np.asarray(outcome["coefficients"], dtype=float)
        tables["rate_ratio_ci"] = table_of(
            pd.DataFrame(
                {
                    "term": _labels(outcome["names"], outcome["constant"]),
                    "rate_ratio": numbers(np.exp(np.clip(coefficients, -500, 500)), 6),
                    "ci_low": numbers(np.exp(np.clip(coefficients - z * errors, -500, 500)), 6),
                    "ci_high": numbers(np.exp(np.clip(coefficients + z * errors, -500, 500)), 6),
                }
            ),
            limit=60,
        )
        metrics["rate_ci"] = True
    if context.flag("prediction_table", False):
        predicted = np.asarray(outcome["fitted_values"], dtype=float)
        frame = pd.DataFrame(
            {"row": np.arange(1, predicted.size + 1), "predicted": numbers(predicted, 6)}
        )
        tables["predictions"] = table_of(frame, limit=40)
        metrics["mean_predicted"] = round(float(predicted.mean()), 6)
    notes = {
        "poisson": [
            "泊松回归的系数取指数后是发生率比 IRR。",
            "若 Pearson 卡方与自由度之比远大于 1，说明存在过度离散，应考虑准泊松或负二项模型。",
        ],
        "quasipoisson": [
            "准泊松沿用泊松的均值结构，但用 Pearson 卡方估计离散度，"
            "据此放大标准误，系数不变而显著性更保守。",
            "报告的离散度大于 1 表示数据相对泊松模型过度离散。",
        ],
        "nb": [
            "负二项回归在泊松均值方差关系上增加离散参数，系数取指数后仍是发生率比。",
            "Pearson 卡方除以自由度接近 1 说明离散参数已吸收过度离散。",
        ],
    }[family]
    figures = []
    if bool(context.flag("mean_curve", True)):
        try:
            name = _mean_curve(
                context,
                "model_poisson_mean_curve",
                {"poisson": "泊松", "quasipoisson": "准泊松", "nb": "负二项"}[family],
                outcome,
                confidence,
            )
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过预测均值曲线。")
    return registry.result(
        "model.poisson",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("model.gamma")
def gamma(context):
    outcome = _glm(context, "gamma", "Gamma 回归")
    metrics = _glm_metrics(outcome)
    metrics["scale"] = round(float(outcome["scale"]), 8)
    metrics["scale_check"] = outcome["scale_check"]
    metrics["link"] = outcome["link"]
    metrics.update(_fit_diagnostics(outcome, 100))
    tables = {"coefficients": table_of(_glm_table(outcome), limit=60)}
    if context.flag("report_scale", False):
        tables["scale"] = table_of(
            pd.DataFrame(
                {
                    "quantity": ["离散度（scale）", "对数似然", "AIC", "偏差"],
                    "value": numbers(
                        [
                            outcome["model_scale"],
                            outcome["log_likelihood"],
                            outcome["aic"],
                            outcome["deviance"],
                        ],
                        6,
                    ),
                }
            )
        )
    if context.flag("prediction_table", False):
        predicted = np.asarray(outcome["fitted_values"], dtype=float)
        tables["predictions"] = table_of(
            pd.DataFrame(
                {"row": np.arange(1, predicted.size + 1), "predicted": numbers(predicted, 6)}
            ),
            limit=40,
        )
        metrics["mean_predicted"] = round(float(predicted.mean()), 6)
    confidence = context.number("confidence", 0.95, 0.5, 0.999)
    if context.flag("coefficient_table", False):
        limit = _z_value(confidence)
        coefficients = np.asarray(outcome["coefficients"], dtype=float)
        errors = np.asarray(outcome["errors"], dtype=float)
        tables["coefficient_intervals"] = table_of(
            pd.DataFrame(
                {
                    "term": _labels(outcome["names"], outcome["constant"]),
                    "coefficient": numbers(coefficients, 6),
                    "std_error": numbers(errors, 6),
                    "ci_low": numbers(coefficients - limit * errors, 6),
                    "ci_high": numbers(coefficients + limit * errors, 6),
                }
            ),
            limit=60,
        )
        metrics["confidence"] = confidence
    figures = []
    if bool(context.flag("mean_curve", True)):
        try:
            name = _mean_curve(context, "model_gamma_mean_curve", "Gamma", outcome, confidence)
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过预测均值曲线。")
    return registry.result(
        "model.gamma",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=[
            f"Gamma 回归适合取值为正、方差随均值增大的连续响应，当前链接函数为 {outcome['link']}。",
            "对数链接下系数表示对数均值的变化；恒等链接下系数就是均值的直接变化。",
        ],
    )


@register("model.gee")
def gee(context):
    import statsmodels.api as sm

    table = context.table
    matrix, target, names = _xy(context, context.want("columns"))
    groups = _aligned(context, table.group())
    if groups is None:
        raise MethodError("GEE 需要分组列来说明哪些观测属于同一个个体。")
    family = context.text("family", "gaussian", ("gaussian", "poisson", "binomial"))
    correlation = context.text(
        "correlation", "exchangeable", ("exchangeable", "independence", "ar1", "unstructured")
    )
    constant = context.flag("add_constant", True)
    max_iter = context.whole("max_iter", 100, 10, 2000)
    covariance = context.text("covariance", "robust", ("robust", "naive", "bias_reduced"))
    confidence = context.number("confidence", 0.95, 0.5, 0.999)
    chosen = {
        "gaussian": sm.families.Gaussian(),
        "poisson": sm.families.Poisson(),
        "binomial": sm.families.Binomial(),
    }[family]
    design = _design(matrix, constant)
    fitted = sm.GEE(
        target,
        design,
        groups=pd.factorize(groups)[0],
        family=chosen,
        cov_struct=sm.cov_struct.__dict__[
            {
                "exchangeable": "Exchangeable",
                "independence": "Independence",
                "ar1": "Autoregressive",
                "unstructured": "Unstructured",
            }[correlation]
        ](),
    ).fit(maxiter=max_iter, cov_type=covariance)
    rows = pd.DataFrame(
        {
            "term": _labels(names, constant),
            "coefficient": numbers(fitted.params, 6),
            "std_error": numbers(fitted.bse, 6),
            "z_value": numbers(fitted.tvalues, 6),
            "p_value": numbers(fitted.pvalues, 8),
        }
    )
    rows["significant"] = [bool(value < 0.05) for value in fitted.pvalues]
    ratio_family = family in ("poisson", "binomial")
    exponentiate = context.flag("exponentiate", False) and ratio_family
    critical = _z_value(confidence)
    if exponentiate:
        coefficients = np.asarray(fitted.params, dtype=float)
        errors = np.asarray(fitted.bse, dtype=float)
        rows["odds_ratio"] = numbers(np.exp(np.clip(coefficients, -500, 500)), 6)
        rows["ci_low"] = numbers(np.exp(np.clip(coefficients - critical * errors, -500, 500)), 6)
        rows["ci_high"] = numbers(np.exp(np.clip(coefficients + critical * errors, -500, 500)), 6)
    metrics = {
        "observations": int(fitted.nobs),
        "groups": int(pd.Series(groups).nunique()),
        "family": family,
        "correlation": correlation,
        "covariance": covariance,
        "exponentiate": bool(exponentiate),
        "add_constant": constant,
        "max_iter": max_iter,
        "features": len(names),
        "scale": round(float(fitted.scale), 6),
    }
    tables = {"coefficients": table_of(rows, limit=60)}
    summary = None
    try:
        summary = fitted.cov_struct.summary()
    except Exception:
        summary = None
    values = getattr(fitted.cov_struct, "dep_params", None)
    if context.flag("correlation_matrix", False):
        if values is not None:
            array = np.atleast_1d(np.asarray(values, dtype=float))
            tables["working_correlation"] = table_of(
                pd.DataFrame(
                    {
                        "parameter": [f"相关参数 {index + 1}" for index in range(array.size)],
                        "value": numbers(array, 6),
                    }
                ),
                limit=20,
            )
            metrics["working_correlation_max"] = round(float(np.max(np.abs(array))), 6)
        elif summary:
            tables["working_correlation"] = table_of(pd.DataFrame({"description": [str(summary)]}))
        else:
            context.warn("当前工作相关结构没有可导出的参数。")
    if context.flag("report_scale", False):
        metrics["model_scale"] = round(float(fitted.scale), 6)
    critical = _z_value(confidence)
    if context.flag("coefficient_table", False):
        tables["coefficient_intervals"] = table_of(
            pd.DataFrame(
                {
                    "term": _labels(names, constant),
                    "coefficient": numbers(fitted.params, 6),
                    "std_error": numbers(fitted.bse, 6),
                    "ci_low": numbers(
                        np.asarray(fitted.params, dtype=float)
                        - critical * np.asarray(fitted.bse, dtype=float),
                        6,
                    ),
                    "ci_high": numbers(
                        np.asarray(fitted.params, dtype=float)
                        + critical * np.asarray(fitted.bse, dtype=float),
                        6,
                    ),
                }
            ),
            limit=60,
        )
        metrics["confidence"] = confidence
    figures = []
    if bool(context.flag("effects_plot", True)):
        try:
            name = _group_effects_plot(
                context,
                "model_gee_group_fit",
                "GEE 分组拟合对比",
                groups,
                target,
                np.asarray(fitted.fittedvalues, dtype=float),
            )
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过分组拟合图。")
    notes = [
        "GEE 估计的是总体平均效应，对组内相关结构的假设不敏感。",
        "与混合模型不同，GEE 不给出个体随机效应。",
    ]
    if covariance != "robust":
        notes.append(
            f"标准误类型为 {covariance}；robust 为聚类稳健标准误，"
            "naive 忽略组内相关，bias_reduced 为偏差校正稳健标准误。"
        )
    if exponentiate:
        notes.append(
            f"系数已按指数尺度输出（{confidence:.3g} 置信区间），"
            "泊松族读作发生率比、二项族读作优势比。"
        )
    return registry.result(
        "model.gee",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("model.mixed")
def mixed(context):
    import statsmodels.api as sm  # noqa: F401
    import statsmodels.formula.api as smf

    table = context.table
    if table.numeric_target() is None:
        raise MethodError("混合效应模型需要数值目标列。")
    matrix, target, names = _xy(context, context.want("columns"))
    group_by = context.text("group_by", "group", ("group", "time"))
    if group_by == "time" and table.time() is None:
        raise MethodError("按时间分组需要时间列，当前数据没有可用的时间列。")
    groups = (
        _aligned(context, table.group()) if group_by == "group" else _aligned(context, table.time())
    )
    if groups is None:
        raise MethodError("混合效应模型需要分组列（个体标识）。")
    frame = pd.DataFrame(matrix, columns=names)
    frame["__target__"] = target
    frame["__group__"] = pd.factorize(groups)[0]

    formula = "__target__ ~ " + " + ".join(f"Q('{name}')" for name in names)
    random = context.text("random", "intercept", ("intercept", "slope"))
    max_iter = context.whole("max_iter", 200, 20, 5000)
    reml = context.text("reml", "default", ("default", "ml", "reml"))
    if random == "slope" and names:
        random_term = f"~ Q('{names[0]}')"
    else:
        random_term = "~ 1"
    degrees_of_freedom = context.text("degrees_of_freedom", "residual", ("residual", "normal"))
    model = smf.mixedlm(formula, frame, groups=frame["__group__"], re_formula=random_term)
    options = {"method": "lbfgs", "maxiter": max_iter, "use_t": degrees_of_freedom == "residual"}
    if reml != "default":
        options["reml"] = reml == "reml"
    try:
        fitted = model.fit(**options)
    except Exception as error:
        singular = "singular" in str(error).lower() or "LinAlgError" in type(error).__name__
        if singular:
            relaxed = dict(options)
            relaxed["method"] = "powell"
            try:
                fitted = model.fit(**relaxed)
                context.warn("随机效应方差位于边界，已改用无需梯度的 powell 优化器重新拟合。")
            except Exception:
                raise MethodError(
                    "混合效应模型在此数据上无法求解（随机效应协方差矩阵奇异）。"
                    "常见原因：分组内样本太少、组间差异接近零，或随机斜率没有足够变异。"
                    "可以改用随机截距（random=intercept）、减少固定效应，或换用 GEE。"
                ) from error
        else:
            raise MethodError(f"混合效应模型拟合失败：{error}") from error

    rows = []
    for term in fitted.params.index:
        rows.append(
            {
                "term": str(term),
                "coefficient": round(float(fitted.params[term]), 6),
                "std_error": round(float(fitted.bse[term]), 6),
                "z_value": round(float(fitted.tvalues[term]), 6),
                "p_value": round(float(fitted.pvalues[term]), 8),
            }
        )
    rows = pd.DataFrame(rows)
    rows["significant"] = [bool(value < 0.05) for value in rows["p_value"]]
    random_effect = next(
        (float(value) for value in fitted.cov_re.to_numpy().ravel() if np.isfinite(value)), None
    )
    tables = {"coefficients": table_of(rows, limit=60)}
    values = np.asarray(target, dtype=float)
    metrics = {
        "observations": int(fitted.nobs),
        "groups": int(frame["__group__"].nunique()),
        "features": len(names),
        "random": random,
        "max_iter": max_iter,
        "group_by": group_by,
        "reml": reml,
        "degrees_of_freedom": degrees_of_freedom,
        "converged": bool(fitted.converged),
        "group_variance": None if random_effect is None else round(random_effect, 6),
    }
    variance_components = getattr(fitted, "cov_re", None)
    if variance_components is not None:
        tables["random_effects"] = table_of(
            pd.DataFrame(
                np.asarray(variance_components, dtype=float),
                index=list(variance_components.index),
                columns=list(variance_components.columns),
            )
            .reset_index()
            .rename(columns={"index": "term"}),
            limit=20,
        )
    confidence = context.number("confidence", 0.95, 0.5, 0.999)
    critical = _z_value(confidence)
    if context.flag("coefficient_table", False):
        intervals = pd.DataFrame(
            {
                "term": [str(term) for term in fitted.params.index],
                "coefficient": numbers(fitted.params, 6),
                "std_error": numbers(fitted.bse, 6),
                "ci_low": numbers(
                    np.asarray(fitted.params, dtype=float)
                    - critical * np.asarray(fitted.bse, dtype=float),
                    6,
                ),
                "ci_high": numbers(
                    np.asarray(fitted.params, dtype=float)
                    + critical * np.asarray(fitted.bse, dtype=float),
                    6,
                ),
            }
        )
        tables["coefficient_intervals"] = table_of(intervals, limit=60)
        metrics["confidence"] = confidence
    if context.flag("icc", False):
        residual = float(getattr(fitted, "scale", 1.0))
        between = 0.0 if random_effect is None else float(random_effect)
        total = between + residual
        metrics["icc"] = None if total <= EPS else round(between / total, 6)
        metrics["residual_variance"] = round(residual, 6)
    if context.flag("blup", False):
        effects = np.asarray(
            fitted.random_effects
            and [
                float(np.asarray(value, dtype=float).ravel()[0])
                for value in fitted.random_effects.values()
            ]
            or [],
            dtype=float,
        )
        if effects.size:
            tables["group_effects"] = table_of(
                pd.DataFrame(
                    {
                        "group": [str(key) for key in fitted.random_effects],
                        "blup": numbers(effects, 6),
                    }
                ),
                limit=40,
            )
            metrics["blup_groups"] = int(effects.size)
    if context.flag("fit_statistics", False):
        metrics["log_likelihood"] = round(float(fitted.llf), 6)
        metrics["aic"] = round(float(fitted.aic), 6)
        metrics["bic"] = round(float(fitted.bic), 6)
    figures = []
    if bool(context.flag("effect_plot", True)):
        plot_groups = context.whole("plot_groups", 12, 2, 50)
        plot_order = context.text("plot_order", "value", ("value", "name"))
        try:
            name, plotted = _blup_plot(
                context,
                "model_mixed_random_effects_and_fit",
                fitted.random_effects,
                groups,
                values,
                fitted.fittedvalues,
                plot_groups,
                plot_order,
            )
            if name:
                figures.append(name)
            if plot_groups != 12 or plot_order != "value":
                metrics["plotted_groups"] = len(plotted)
                metrics["plot_group_labels"] = plotted
        except ImportError:
            context.warn("未安装 matplotlib，跳过随机效应图。")
    notes = [
        "混合模型把组间差异建模为随机效应，适合重复测量与分层数据。",
        "固定效应系数表示组内平均变化，不能直接与普通回归系数比较。",
    ]
    if random == "slope":
        notes.append(
            "随机斜率项同时包含随机截距；statsmodels 的 re_formula 默认带截距，无法只放斜率。"
        )
    return registry.result(
        "model.mixed",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("model.glmm")
def glmm(context):
    from scipy.sparse import csr_matrix
    from scipy.special import expit
    from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM, PoissonBayesMixedGLM

    table = context.table
    groups = _aligned(context, table.group())
    if groups is None or pd.isna(groups).any():
        raise MethodError("GLMM 需要完整的分组/个体标识列。")
    family = context.text("family", "poisson", ("poisson", "binomial", "gamma"))
    link = context.text("link", "default", ("default", "log", "identity", "logit"))
    if family == "gamma":
        raise MethodError(
            "当前 GLMM 后端仅支持 Poisson/log 与 Binomial/logit 随机截距；Gamma 不会退化为普通 GLM。"
        )
    wanted = "logit" if family == "binomial" else "log"
    if link not in ("default", wanted):
        raise MethodError(f"当前 {family} GLMM 只支持 {wanted} 链接。")
    if context.text("covariance", "nonrobust") != "nonrobust":
        raise MethodError("此 GLMM 使用变分贝叶斯后验标准差，不支持频率学派 HC 标准误。")
    matrix, target, names = _xy(context, context.want("columns"))
    if family == "binomial" and set(np.unique(target)) != {0.0, 1.0}:
        raise MethodError("二项 GLMM 需要真实的 0/1 目标。")
    if family == "poisson" and ((target < 0).any() or not np.equal(target, np.floor(target)).all()):
        raise MethodError("Poisson GLMM 需要非负整数计数目标。")
    codes, levels = pd.factorize(groups, sort=True)
    if len(levels) < 2:
        raise MethodError("随机截距至少需要两个组。")
    exog = np.column_stack([np.ones(len(target)), matrix])
    random_design = csr_matrix(
        (np.ones(len(codes)), (np.arange(len(codes)), codes)), shape=(len(codes), len(levels))
    )
    cls = BinomialBayesMixedGLM if family == "binomial" else PoissonBayesMixedGLM
    model = cls(
        target,
        exog,
        random_design,
        np.zeros(len(levels), dtype=int),
        vcp_p=0.5,
        fe_p=2.0,
        fep_names=["常数项"] + names,
    )
    limit = context.whole("max_iter", 200, 20, 5000)
    width = model.k_fep + model.k_vcp + model.k_vc
    fitted = model.fit_vb(
        mean=np.zeros(width), sd=np.full(width, 0.1), minim_opts={"maxiter": limit}, scale_fe=True
    )
    if not fitted.optim_retvals.get("success", False):
        context.warn("GLMM 变分优化未完全收敛，请核对后验及收敛状态后解释。")
    linear = exog @ fitted.fe_mean + random_design @ fitted.vc_mean
    predictions = expit(linear) if family == "binomial" else np.exp(np.clip(linear, -40, 40))
    confidence = context.number("confidence", 0.95, 0.5, 0.999)
    critical = _z_value(confidence)
    coefficients = pd.DataFrame(
        {
            "term": ["常数项"] + names,
            "posterior_mean": numbers(fitted.fe_mean, 6),
            "posterior_sd": numbers(fitted.fe_sd, 6),
        }
    )
    if context.flag("coefficient_table", False):
        coefficients["credible_low"] = numbers(fitted.fe_mean - critical * fitted.fe_sd, 6)
        coefficients["credible_high"] = numbers(fitted.fe_mean + critical * fitted.fe_sd, 6)
    tables = {
        "coefficients": table_of(coefficients, limit=60),
        "random_intercepts": table_of(
            pd.DataFrame(
                {
                    "group": [str(x) for x in levels],
                    "posterior_mean": numbers(fitted.vc_mean, 6),
                    "posterior_sd": numbers(fitted.vc_sd, 6),
                }
            ),
            limit=60,
        ),
    }
    metrics = {
        "observations": len(target),
        "groups": len(levels),
        "family": family,
        "link": wanted,
        "estimator": "variational_bayes_random_intercept",
        "random_intercept_sd": float(np.exp(fitted.vcp_mean[0])),
        "converged": bool(fitted.optim_retvals.get("success", False)),
        "max_iter": limit,
    }
    notes = [
        "实际拟合固定效应与分组随机截距；后验标准差及可信区间属于变分贝叶斯估计，不能当作频率学派 p 值。",
        "不使用普通 GLM 替代 GLMM；不输出未经边际似然计算的 AIC/BIC。",
    ]
    if context.flag("report_deviance", True):
        import statsmodels.api as sm

        distribution = sm.families.Binomial() if family == "binomial" else sm.families.Poisson()
        metrics["conditional_deviance"] = float(distribution.deviance(target, predictions))
    if context.flag("dispersion", False):
        variance = predictions * (1 - predictions) if family == "binomial" else predictions
        metrics["conditional_pearson_dispersion"] = float(
            np.sum((target - predictions) ** 2 / np.maximum(variance, EPS))
            / max(len(target) - exog.shape[1], 1)
        )
        notes.append("离散度以包含随机截距的条件拟合值计算，仅作诊断。")
    if context.flag("random_effect_note", False):
        tables["group_sizes"] = table_of(
            pd.DataFrame({"group": [str(x) for x in levels], "size": np.bincount(codes)}), limit=60
        )
    if context.flag("effects_plot", True):
        try:
            _group_effects_plot(
                context,
                "model_glmm_group_fit",
                "GLMM 随机截距条件拟合",
                groups,
                target,
                predictions,
            )
        except ImportError:
            context.warn("未安装 matplotlib，跳过分组拟合图。")
    return registry.result("model.glmm", table, metrics=metrics, tables=tables, notes=notes)
