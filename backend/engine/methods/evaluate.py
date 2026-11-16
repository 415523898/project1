import math

import numpy as np
import pandas as pd

from engine import registry
from engine.registry import MethodError, numbers, register, table_of

EPS = 1e-12

DIRECTIONS = ("benefit", "cost", "mixed")
NORMALIZATIONS = ("minmax", "zscore", "vector", "ratio")
WEIGHTINGS = ("equal", "entropy", "critic", "custom")
REFERENCES = ("best", "worst")
MISSING_POLICIES = ("drop", "mean")
CONFLICTS = ("std", "range", "cv")
DISTRIBUTIONS = ("normal", "none")
EXTRACTIONS = ("principal", "minres", "ml")
ROTATIONS = ("varimax", "promax", "none")
OPERATORS = ("weighted", "maxmin", "average")
DISTANCES = ("euclidean", "manhattan", "chebyshev")
CORRELATIONS = ("pearson", "spearman", "kendall")
SHAPES = ("triangle", "trapezoid", "gaussian")
SELECTIONS = ("fixed", "eigenvalue", "cumulative")
BASELINES = ("sample", "zero")
STAGES = ("none", "tobit")
SCORE_METHODS = ("regression", "bartlett")


def _digits(context, default=4):
    return context.whole("digits", default, 0, 8)


def _frame(names, matrix, prefix, digits):
    values = np.round(np.asarray(matrix, dtype=float), digits)
    return pd.DataFrame(values, columns=[f"{prefix}{name}" for name in names])


def _distance(left, right, metric):
    delta = np.abs(np.asarray(left, dtype=float) - np.asarray(right, dtype=float))
    if metric == "manhattan":
        return delta.sum(axis=1)
    if metric == "chebyshev":
        return delta.max(axis=1)
    return np.sqrt((delta**2).sum(axis=1))


def _pairwise(matrix, method):
    values = np.asarray(matrix, dtype=float)
    if method == "pearson":
        return np.nan_to_num(np.atleast_2d(np.corrcoef(values, rowvar=False)), nan=0.0)
    frame = pd.DataFrame(values)
    return np.nan_to_num(frame.corr(method=method).to_numpy(dtype=float), nan=0.0)


def _kmo_statistics(matrix):
    values = np.asarray(matrix, dtype=float)
    width = values.shape[1]
    if width < 2:
        return None, [None] * width
    correlation = _pairwise(values, "pearson")
    inverse = np.linalg.pinv(correlation)
    diagonal = np.diag(inverse)
    scale = np.sqrt(np.abs(np.outer(diagonal, diagonal)))
    scale = np.where(scale <= EPS, 1.0, scale)
    partial = -inverse / scale
    np.fill_diagonal(partial, 0.0)
    plain = correlation.copy()
    np.fill_diagonal(plain, 0.0)
    plain_square = float((plain**2).sum())
    partial_square = float((partial**2).sum())
    if plain_square + partial_square <= EPS:
        return None, [None] * width
    statistic = plain_square / (plain_square + partial_square)
    per_indicator = []
    for index in range(width):
        row_plain = float((plain[index] ** 2).sum())
        row_partial = float((partial[index] ** 2).sum())
        total = row_plain + row_partial
        per_indicator.append(None if total <= EPS else row_plain / total)
    return statistic, per_indicator


def _bartlett_test(matrix):
    from scipy import stats as sps

    values = np.asarray(matrix, dtype=float)
    rows, width = values.shape
    dof = int(width * (width - 1) / 2)
    if width < 2 or rows <= width:
        return None, dof, None
    sign, logdet = np.linalg.slogdet(_pairwise(values, "pearson"))
    if sign <= 0:
        return None, dof, None
    statistic = max(-((rows - 1) - (2 * width + 5) / 6.0) * float(logdet), 0.0)
    return statistic, dof, float(sps.chi2.sf(statistic, dof))


def _bartlett_scores(data, loadings, uniqueness):
    specific = np.asarray(uniqueness, dtype=float)
    specific = np.where(specific <= EPS, EPS, specific)
    precision = np.diag(1.0 / specific)
    loadings = np.asarray(loadings, dtype=float)
    weight = precision @ loadings
    gram = loadings.T @ precision @ loadings
    return np.asarray(data, dtype=float) @ (weight @ np.linalg.pinv(gram))


def _grade_thresholds(context):
    raw = context.text("grade_thresholds", "20,40,60,80")
    parts = _as_list(raw)
    if len(parts) != 4:
        raise MethodError("grade_thresholds 需要 4 个百分位数字，例如 20,40,60,80。")
    try:
        values = [float(part) for part in parts]
    except ValueError:
        raise MethodError("grade_thresholds 需要用逗号分隔的数字，例如 20,40,60,80。") from None
    if any(value <= 0.0 or value >= 100.0 for value in values):
        raise MethodError("grade_thresholds 的每个百分位需要落在 0 与 100 之间。")
    if any(values[index] >= values[index + 1] for index in range(3)):
        raise MethodError("grade_thresholds 需要从小到大排列，例如 20,40,60,80。")
    return values


def _tobit_censored(response, design, lower, upper):
    from scipy import stats as sps
    from scipy.optimize import minimize

    y = np.asarray(response, dtype=float)
    x = np.column_stack([np.ones(y.size), np.asarray(design, dtype=float)])

    def objective(parameters):
        beta = parameters[:-1]
        sigma = math.exp(parameters[-1])
        mean = x @ beta
        z = (y - mean) / sigma
        likelihood = np.zeros_like(y)
        observed = np.ones_like(y, dtype=bool)
        if lower is not None:
            observed &= y > lower
        if upper is not None:
            observed &= y < upper
        likelihood[observed] = sps.norm.logpdf(z[observed]) - math.log(sigma)
        if upper is not None:
            at_upper = y >= upper
            likelihood[at_upper] = sps.norm.logsf((upper - mean[at_upper]) / sigma)
        if lower is not None:
            at_lower = y <= lower
            likelihood[at_lower] = sps.norm.logcdf((lower - mean[at_lower]) / sigma)
        return -float(likelihood.sum())

    start = np.concatenate([np.zeros(x.shape[1]), [math.log(max(float(np.std(y)), 1e-6))]])
    return minimize(objective, start, method="L-BFGS-B")


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _share(values):
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return values
    total = float(values.sum())
    if not math.isfinite(total) or total <= EPS:
        return np.full(values.size, 1.0 / values.size)
    return values / total


def _benefit_direction(context, matrix):
    direction = context.text("direction", "benefit", DIRECTIONS)
    signs = np.ones(matrix.shape[1])
    if direction == "benefit":
        return signs
    if direction == "cost":
        return -signs
    cost = _as_list(context.want("cost_columns"))
    if not cost:
        raise MethodError("direction=mixed 时必须用 cost_columns 指定成本型指标。")
    names = context.table.feature_names
    unknown = [name for name in cost if name not in names]
    if unknown:
        context.warn(f"成本型指标 {'、'.join(unknown)} 不在当前指标列中，已忽略。")
    for index, name in enumerate(names):
        if name in cost:
            signs[index] = -1.0
    return signs


def _normalization(context):
    return context.text("normalize", "minmax", NORMALIZATIONS)


def _normalized(context, matrix):
    matrix = np.asarray(matrix, dtype=float)
    signs = _benefit_direction(context, matrix)
    method = _normalization(context)
    cost = signs < 0
    if method == "minmax":
        low = matrix.min(axis=0)
        high = matrix.max(axis=0)
        span = np.where(high - low <= EPS, 1.0, high - low)
        scaled = (matrix - low) / span
        scaled[:, cost] = 1.0 - scaled[:, cost]
        return scaled, signs
    if method == "zscore":
        centre = matrix.mean(axis=0)
        spread = matrix.std(axis=0, ddof=0)
        spread = np.where(spread <= EPS, 1.0, spread)
        scaled = (matrix - centre) / spread
        scaled[:, cost] = -scaled[:, cost]
        return scaled, signs
    if method == "vector":
        norm = np.sqrt((matrix**2).sum(axis=0))
        norm = np.where(norm <= EPS, 1.0, norm)
        scaled = matrix / norm
        scaled[:, cost] = -scaled[:, cost]
        return scaled, signs
    non_negative = np.clip(matrix, 0.0, None)
    total = non_negative.sum(axis=0)
    total = np.where(total <= EPS, 1.0, total)
    scaled = non_negative / total
    if cost.any():
        if (matrix[:, cost] <= 0).any():
            raise MethodError("ratio 归一化下成本型指标必须全为正数。")
        inverse = 1.0 / matrix[:, cost]
        scaled[:, cost] = inverse / inverse.sum(axis=0, keepdims=True)
    return scaled, signs


def _shifted_positive(matrix, shift, shift_value=0.0001):
    values = np.asarray(matrix, dtype=float)
    if shift:
        offset = np.maximum(0.0, -values.min(axis=0))
        return values + offset + shift_value
    if (values < 0).any():
        raise MethodError("指标存在负值，无法直接取对数，请开启 shift 平移。")
    return values


def _entropy_statistics(matrix, shift, normalized=True, shift_value=0.0001):
    values = _shifted_positive(matrix, shift, shift_value)
    total = values.sum(axis=0, keepdims=True)
    total = np.where(np.abs(total) <= EPS, 1.0, total)
    proportion = values / total
    with np.errstate(divide="ignore", invalid="ignore"):
        logs = np.where(proportion > 0, np.log(np.where(proportion > 0, proportion, 1.0)), 0.0)
    constant = math.log(max(values.shape[0], 2)) if normalized else 1.0
    entropy_values = -np.sum(proportion * logs, axis=0) / constant
    return entropy_values, 1.0 - entropy_values


def _critic_statistics(matrix, mode, correlation="pearson"):
    matrix = np.asarray(matrix, dtype=float)
    if mode == "range":
        spread = matrix.max(axis=0) - matrix.min(axis=0)
    elif mode == "cv":
        mean = matrix.mean(axis=0)
        spread = matrix.std(axis=0, ddof=1)
        spread = np.abs(np.divide(spread, np.where(np.abs(mean) <= EPS, 1.0, mean)))
    else:
        spread = matrix.std(axis=0, ddof=1)
    correlation_matrix = _pairwise(matrix, correlation)
    conflict = np.sum(1.0 - correlation_matrix, axis=0)
    information = spread * conflict
    return spread, conflict, information, _share(information)


def _custom_weights(context, names):
    given = context.want("weights")
    if given is None:
        raise MethodError("weighting=custom 时必须通过 weights 给出权重。")
    if isinstance(given, dict):
        raw = np.array([float(given.get(name, 1.0)) for name in names], dtype=float)
    else:
        parts = _as_list(given)
        if not parts:
            raise MethodError("weighting=custom 时必须通过 weights 给出权重。")
        try:
            raw = np.array([float(part) for part in parts], dtype=float)
        except ValueError:
            raise MethodError("weights 需要用逗号分隔的数字，例如 0.2,0.3,0.5。") from None
    if raw.size != len(names):
        raise MethodError(
            f"weights 需要 {len(names)} 个数值，与指标数一致，当前给了 {raw.size} 个。"
        )
    if not np.isfinite(raw).all():
        raise MethodError("weights 必须是有限数字。")
    if (raw < 0).any():
        raise MethodError("weights 不能为负数。")
    return _share(raw)


def _weights(context, matrix):
    names = context.table.feature_names
    weighting = context.text("weighting", "entropy", WEIGHTINGS + ("variance",))
    if weighting == "custom":
        return _custom_weights(context, names)
    given = context.want("weights")
    if given is not None and _as_list(given):
        return _custom_weights(context, names)
    if weighting == "equal":
        return np.full(len(names), 1.0 / len(names))
    if weighting == "critic":
        return _critic_statistics(matrix, "std")[3]
    if weighting == "variance":
        return _share(np.asarray(matrix, dtype=float).var(axis=0, ddof=1))
    return _share(_entropy_statistics(matrix, True)[1])


def _missing_matrix(context, matrix):
    policy = context.text("missing", "drop", MISSING_POLICIES)
    values = np.asarray(matrix, dtype=float)
    mask = np.isnan(values)
    if np.isinf(values).any():
        raise MethodError("评价指标包含无穷值，无法计算有效权重或排名。")
    if not mask.any():
        return values, 0
    if policy == "mean":
        fill = np.nanmean(values, axis=0)
        if not np.isfinite(fill).all():
            raise MethodError("存在全空指标列，无法估计均值；请明确删除该指标或提供有效数据。")
        context.warn(f"按本方法 missing=mean 设置，填补 {int(mask.sum())} 个缺失单元格。")
        return np.where(mask, fill, values), int(mask.sum())
    keep = ~mask.any(axis=1)
    if not keep.any():
        raise MethodError("样本缺失处理为 drop 后没有可用样本。")
    count = int((~keep).sum())
    context.table.raw = context.table.raw.loc[keep].reset_index(drop=True)
    context.table.frame = context.table.frame.loc[keep].reset_index(drop=True)
    context.table.rows_dropped += count
    context.warn(f"按本方法 missing=drop 设置，排除含缺失的 {count} 个评价对象。")
    return values[keep], int(mask.sum())


def _ranking(names, scores, descending=True):
    order = np.argsort(
        -np.asarray(scores, dtype=float) if descending else np.asarray(scores, dtype=float),
        kind="stable",
    )
    ranks = np.empty(len(scores), dtype=int)
    ranks[order] = np.arange(1, len(scores) + 1)
    return ranks


def _figure(context, name, draw, message):
    if not context.flag("plot", True):
        return None
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn(message)
        return None
    fig = draw(plt)
    saved = context.save(fig, name)
    if saved is None:
        context.warn(message)
    return saved


def _object_labels(table, size):
    if size > 40:
        return None
    labels = table.labels()
    if labels is None:
        return None
    return [str(value) for value in np.asarray(labels).ravel()[:size]]


def _correlation_matrix(context, matrix):
    method = context.text("correlation", "pearson", CORRELATIONS)
    return _pairwise(matrix, method), method


def _varimax(loadings, iterations=200, tol=1e-9):
    matrix = np.asarray(loadings, dtype=float)
    rows, columns = matrix.shape
    rotation = np.eye(columns)
    if columns < 2:
        return matrix.copy(), rotation
    previous = 0.0
    for _ in range(iterations):
        basis = matrix @ rotation
        target = matrix.T @ (basis**3 - basis @ np.diag((basis**2).sum(axis=0)) / rows)
        left, singular, right = np.linalg.svd(target)
        rotation = left @ right
        value = float(singular.sum())
        if previous and value <= previous * (1.0 + tol):
            break
        previous = value
    return matrix @ rotation, rotation


def _rotate_loadings(loadings, method, power=4.0):
    matrix = np.asarray(loadings, dtype=float)
    if method == "none":
        return matrix, np.eye(matrix.shape[1])
    rotated, rotation = _varimax(matrix)
    if method == "promax":
        target = np.sign(rotated) * np.abs(rotated) ** power
        left, _, right = np.linalg.svd(rotated.T @ target)
        procrustes = left @ right
        return rotated @ procrustes, rotation @ procrustes
    return rotated, rotation


def _eigen_basis(matrix):
    values, vectors = np.linalg.eigh(np.asarray(matrix, dtype=float))
    order = np.argsort(values)[::-1]
    return np.clip(values[order], 0.0, None), vectors[:, order]


def _regression_scores(data, covariance, loadings):
    inverse = np.linalg.pinv(np.asarray(covariance, dtype=float))
    weights = inverse @ np.asarray(loadings, dtype=float)
    return np.asarray(data, dtype=float) @ weights


def _principal_loadings(covariance, data, factors):
    values, vectors = _eigen_basis(covariance)
    loadings = vectors[:, :factors] * np.sqrt(values[:factors])
    return loadings, values, _regression_scores(data, covariance, loadings)


def _principal_axis_loadings(covariance, data, factors, iterations=300, tol=1e-9):
    matrix = np.asarray(covariance, dtype=float)
    inverse = np.linalg.pinv(matrix)
    diagonal = np.diag(inverse)
    smc = 1.0 - 1.0 / np.where(np.abs(diagonal) <= EPS, 1.0, diagonal)
    communality = np.clip(smc, 0.0, 1.0)
    reduced = matrix.copy()
    loadings = np.zeros((matrix.shape[0], factors))
    for _ in range(iterations):
        np.fill_diagonal(reduced, communality)
        values, vectors = _eigen_basis(reduced)
        loadings = vectors[:, :factors] * np.sqrt(values[:factors])
        updated = (loadings**2).sum(axis=1)
        settled = float(np.max(np.abs(updated - communality))) <= tol
        communality = updated
        if settled:
            break
    values, _ = _eigen_basis(matrix)
    return loadings, values, _regression_scores(data, matrix, loadings)


@register("eval.entropy")
def entropy(context):
    matrix = context.table.matrix()
    names = context.table.feature_names
    if matrix.shape[1] < 2:
        raise MethodError("熵值法至少需要两个指标。")
    aggregate = context.text("aggregate", "entropy", ("entropy", "equal", "variance"))
    shift = context.flag("shift", True)
    shift_value = context.number("shift_value", 0.0001, 0.0, 1.0)
    normalized = context.flag("normalize_entropy", True)
    emit_scores = context.flag("emit_scores", False)
    digits = _digits(context)
    scaled, _ = _normalized(context, matrix)
    entropy_values, divergence = _entropy_statistics(scaled, shift, normalized, shift_value)
    if aggregate == "equal":
        weights = np.full(len(names), 1.0 / len(names))
    elif aggregate == "variance":
        weights = _share(np.asarray(scaled, dtype=float).var(axis=0, ddof=1))
    else:
        weights = _share(divergence)
    composite = scaled @ weights
    ranks = _ranking(names, composite)
    summary = pd.DataFrame(
        {
            "indicator": names,
            "entropy": numbers(entropy_values, digits),
            "divergence": numbers(divergence, digits),
            "weight": numbers(weights, digits),
        }
    )
    scores = pd.DataFrame({"rank": ranks, "score": numbers(composite, digits)})
    tables = {"weights": table_of(summary, limit=60), "scores": table_of(scores, limit=200)}
    if context.flag("emit_matrix", False):
        tables["standardized"] = table_of(_frame(names, scaled, "标准化_", digits), limit=200)
        tables["weighted"] = table_of(_frame(names, scaled * weights, "加权_", digits), limit=200)
    if emit_scores:
        labels = _object_labels(context.table, len(composite))
        score_frame = pd.DataFrame(
            {
                "object": np.arange(1, len(composite) + 1),
                "rank": ranks,
                "score": numbers(composite, digits),
            }
        )
        if labels is not None:
            score_frame.insert(0, "label", labels)
        tables["composite_scores"] = table_of(score_frame, limit=200)

    def draw(plt):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        order = np.argsort(weights)
        axes[0].barh([names[index] for index in order], weights[order], color="#4f7cff")
        axes[0].set_title("指标权重")
        axes[0].set_xlabel("权重")
        axes[0].grid(alpha=0.3, axis="x")
        rank_order = np.argsort(-composite)[:15]
        axes[1].bar(
            [str(index + 1) for index in rank_order], composite[rank_order], color="#f59e0b"
        )
        axes[1].set_title("综合得分前 15 位对象")
        axes[1].set_xlabel("对象")
        axes[1].set_ylabel("得分")
        axes[1].grid(alpha=0.3, axis="y")
        return fig

    _figure(context, "eval_entropy_weights_scores", draw, "未安装 matplotlib，跳过熵值法图。")
    notes = [
        "熵值法按指标的信息量赋权：离散程度越大权重越高。",
        "direction=mixed 时用 cost_columns 指定成本型指标，内部会取反向使其越大越好。",
        "shift 会把非正数平移为正数再取对数，shift_value 是平移后叠加的极小量，shift=False 时该值不参与计算。",
        "normalize_entropy=True 把信息熵除以 ln(样本数) 归一化到 0–1，False 输出原始熵值。",
        "emit_matrix=True 额外输出标准化矩阵与加权矩阵。",
    ]
    if aggregate != "entropy":
        notes.insert(1, "aggregate=equal 时各指标等权，variance 时用标准化后各指标的方差作权重。")
    if emit_scores:
        notes.append("emit_scores=True 额外输出各对象的综合得分表。")
    return registry.result(
        "eval.entropy",
        context.table,
        metrics={
            "indicators": len(names),
            "objects": context.table.n_rows,
            "normalize": _normalization(context),
            "shift": shift,
            "shift_value": round(shift_value, 6),
            "normalize_entropy": normalized,
            "digits": digits,
            "top_weight": names[int(np.argmax(weights))],
            "top_weight_value": round(float(weights.max()), digits),
            "best_object_rank1_score": round(float(composite.max()), digits),
        },
        tables=tables,
        notes=notes,
    )


@register("eval.critic")
def critic(context):
    matrix = context.table.matrix()
    names = context.table.feature_names
    if matrix.shape[1] < 2:
        raise MethodError("CRITIC 至少需要两个指标。")
    conflict = context.text("conflict", "std", CONFLICTS)
    correlation = context.text("correlation", "pearson", CORRELATIONS)
    digits = _digits(context)
    scaled, _ = _normalized(context, matrix)
    spread, conflict_term, information, weights = _critic_statistics(scaled, conflict, correlation)
    composite = scaled @ weights
    ranks = _ranking(names, composite)
    summary = pd.DataFrame(
        {
            "indicator": names,
            "std": numbers(spread, digits),
            "conflict": numbers(conflict_term, digits),
            "information": numbers(information, digits),
            "weight": numbers(weights, digits),
        }
    )
    tables = {
        "weights": table_of(summary, limit=60),
        "scores": table_of(
            pd.DataFrame({"rank": ranks, "score": numbers(composite, digits)}), limit=200
        ),
    }
    correlation_matrix = _pairwise(scaled, correlation)
    off_diagonal = correlation_matrix[~np.eye(len(names), dtype=bool)]
    if context.flag("emit_correlation", False):
        frame = pd.DataFrame(np.round(correlation_matrix, digits), columns=names)
        frame.insert(0, "indicator", names)
        tables["correlation"] = table_of(frame, limit=60)
    if context.flag("emit_matrix", False):
        tables["standardized"] = table_of(_frame(names, scaled, "标准化_", digits), limit=200)
        tables["weighted"] = table_of(_frame(names, scaled * weights, "加权_", digits), limit=200)

    def draw(plt):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        order = np.argsort(weights)
        axes[0].barh([names[index] for index in order], weights[order], color="#4f7cff")
        axes[0].set_title("CRITIC 指标权重")
        axes[0].set_xlabel("权重")
        axes[0].grid(alpha=0.3, axis="x")
        info_order = np.argsort(information)
        axes[1].barh(
            [names[index] for index in info_order], information[info_order], color="#f59e0b"
        )
        axes[1].set_title("信息量（对比强度 × 冲突性）")
        axes[1].set_xlabel("信息量")
        axes[1].grid(alpha=0.3, axis="x")
        return fig

    _figure(context, "eval_critic_weights_information", draw, "未安装 matplotlib，跳过 CRITIC 图。")
    return registry.result(
        "eval.critic",
        context.table,
        metrics={
            "indicators": len(names),
            "objects": context.table.n_rows,
            "normalize": _normalization(context),
            "conflict": conflict,
            "correlation": correlation,
            "digits": digits,
            "mean_correlation": round(float(off_diagonal.mean()), digits)
            if off_diagonal.size
            else None,
            "top_weight": names[int(np.argmax(weights))],
            "top_weight_value": round(float(weights.max()), digits),
        },
        tables=tables,
        notes=[
            "CRITIC 同时考虑指标的对比强度与冲突性（1 − 相关系数）。",
            "conflict=std 用标准差，range 用极差，cv 用变异系数衡量对比强度。",
            "correlation 决定冲突性所用的相关系数口径，支持 pearson、spearman 与 kendall。",
            "与熵值法的区别：CRITIC 会惩罚高度相关的指标，避免重复计权。",
            "emit_correlation 输出相关系数矩阵，emit_matrix 输出标准化与加权矩阵。",
        ],
    )


@register("eval.topsis")
def topsis(context):
    matrix = context.table.matrix()
    names = context.table.feature_names
    if matrix.shape[1] < 1:
        raise MethodError("TOPSIS 至少需要一个指标。")
    matrix, missing_cells = _missing_matrix(context, matrix)
    if matrix.shape[0] < 1:
        raise MethodError("TOPSIS 没有可用样本。")
    scaled, _ = _normalized(context, matrix)
    weights = _weights(context, scaled)
    weighted = scaled * weights
    metric = context.text("distance", "euclidean", DISTANCES)
    ideal_from = context.flag("ideal_from", True)
    if ideal_from:
        ideal = weighted.max(axis=0)
        anti = weighted.min(axis=0)
    else:
        ideal = weights.copy()
        anti = np.zeros(len(names))
        context.warn("理想解取自理论边界 1 与 0，建议配合 minmax 归一化使用。")
    to_ideal = _distance(weighted, ideal, metric)
    to_anti = _distance(weighted, anti, metric)
    denominator = to_ideal + to_anti
    closeness = np.where(
        denominator <= EPS, 0.5, to_anti / np.where(denominator <= EPS, 1.0, denominator)
    )
    ranks = _ranking(names, closeness)
    frames = pd.DataFrame(
        {
            "rank": ranks,
            "closeness": numbers(closeness, 6),
            "distance_to_ideal": numbers(to_ideal, 6),
            "distance_to_anti": numbers(to_anti, 6),
        }
    )
    tables = {"scores": table_of(frames, limit=200)}
    if context.flag("emit_matrix", False):
        tables["weighted"] = table_of(_frame(names, weighted, "加权_", 6), limit=200)

    def draw(plt):
        fig, axis = plt.subplots(figsize=(6.4, 4.8))
        scatter = axis.scatter(to_ideal, to_anti, c=closeness, cmap="viridis", s=32)
        axis.set_xlabel("与正理想解的距离")
        axis.set_ylabel("与负理想解的距离")
        axis.set_title("TOPSIS 理想解距离分布")
        axis.grid(alpha=0.3)
        fig.colorbar(scatter, ax=axis, label="贴近度")
        return fig

    _figure(context, "eval_topsis_ideal_distances", draw, "未安装 matplotlib，跳过 TOPSIS 图。")
    return registry.result(
        "eval.topsis",
        context.table,
        metrics={
            "indicators": len(names),
            "objects": int(matrix.shape[0]),
            "normalize": _normalization(context),
            "weighting": context.text("weighting", "entropy", WEIGHTINGS),
            "distance": metric,
            "ideal_from": ideal_from,
            "missing_cells": missing_cells,
            "missing": context.text("missing", "drop", MISSING_POLICIES),
            "best_closeness": round(float(closeness.max()), 6),
            "worst_closeness": round(float(closeness.min()), 6),
            "weights": numbers(weights, 6),
        },
        tables=tables,
        notes=[
            "贴近度越接近 1 表示越靠近正理想解。",
            "weighting 支持 equal、entropy、critic 与 custom；给出 weights 时优先使用自定义权重。",
            "distance 决定与理想解的距离口径：euclidean 欧氏、manhattan 曼哈顿、chebyshev 切比雪夫。",
            "missing=drop 丢弃含缺失的样本，mean 用列均值填补。",
            "emit_matrix=True 额外输出加权决策矩阵。",
        ],
    )


@register("eval.vikor")
def vikor(context):
    matrix = context.table.matrix()
    names = context.table.feature_names
    if matrix.shape[1] < 1:
        raise MethodError("VIKOR 至少需要一个指标。")
    matrix, missing_cells = _missing_matrix(context, matrix)
    if matrix.shape[0] < 1:
        raise MethodError("VIKOR 没有可用样本。")
    v = context.number("v", 0.5, 0.0, 1.0)
    check = context.flag("compromise_check", False)
    scaled, _ = _normalized(context, matrix)
    weights = _weights(context, scaled)
    best = scaled.max(axis=0)
    worst = scaled.min(axis=0)
    span = np.where(best - worst <= EPS, 1.0, best - worst)
    ratio = (best - scaled) / span
    utility = ratio @ weights
    regret = np.max(ratio * weights, axis=1)
    utility_low, utility_high = utility.min(), utility.max()
    regret_low, regret_high = regret.min(), regret.max()
    s_term = (
        (utility - utility_low) / (utility_high - utility_low)
        if utility_high - utility_low > EPS
        else np.zeros_like(utility)
    )
    r_term = (
        (regret - regret_low) / (regret_high - regret_low)
        if regret_high - regret_low > EPS
        else np.zeros_like(regret)
    )
    compromise = v * s_term + (1 - v) * r_term
    ranks = _ranking(names, compromise, descending=False)
    frames = pd.DataFrame(
        {
            "rank": ranks,
            "compromise": numbers(compromise, 6),
            "group_utility": numbers(utility, 6),
            "individual_regret": numbers(regret, 6),
        }
    )
    tables = {"scores": table_of(frames, limit=200)}
    if context.flag("emit_matrix", False):
        tables["weighted"] = table_of(_frame(names, ratio * weights, "加权_", 6), limit=200)
    metrics = {
        "indicators": len(names),
        "objects": int(matrix.shape[0]),
        "v": v,
        "normalize": _normalization(context),
        "weighting": context.text("weighting", "entropy", WEIGHTINGS),
        "missing_cells": missing_cells,
        "missing": context.text("missing", "drop", MISSING_POLICIES),
        "best_compromise": round(float(compromise.min()), 6),
        "weights": numbers(weights, 6),
    }
    notes = [
        "Q 值越小越好；v 越大越偏向群体效用，越小越偏向个别遗憾。",
        "v=0.5 是常见的折衷设置；weighting 支持 equal、entropy、critic 与 custom。",
        "给出 weights 时优先使用自定义权重；missing=drop 丢弃含缺失的样本，mean 用列均值填补。",
    ]
    if check:
        order = np.argsort(compromise, kind="stable")
        best_index = int(order[0])
        gap = float(compromise[order[1]] - compromise[best_index]) if compromise.size > 1 else 0.0
        bound = 1.0 / max(compromise.size - 1, 1)
        advantage = bool(compromise.size > 1 and gap >= bound)
        stability = bool(best_index in (int(np.argmin(utility)), int(np.argmin(regret))))
        acceptable = bool(advantage and stability)
        metrics["compromise_gap"] = round(gap, 6)
        metrics["advantage_bound"] = round(bound, 6)
        metrics["acceptable_advantage"] = advantage
        metrics["acceptable_stability"] = stability
        metrics["compromise_acceptable"] = acceptable
        metrics["best_object"] = best_index + 1
        notes.append("compromise_check=True 时按可接受优势与可接受稳定性两条准则检验最优折衷解。")
        if not acceptable:
            context.warn("最优折衷解未通过 VIKOR 可接受性检验，建议结合群体效用与个别遗憾列判断。")
    if context.flag("emit_matrix", False):
        notes.append("emit_matrix=True 额外输出加权归一化矩阵。")

    def draw(plt):
        fig, axis = plt.subplots(figsize=(6.4, 4.8))
        scatter = axis.scatter(utility, regret, c=compromise, cmap="plasma", s=32)
        axis.set_xlabel("群体效用 S")
        axis.set_ylabel("个别遗憾 R")
        axis.set_title("VIKOR 群体效用与个别遗憾")
        axis.grid(alpha=0.3)
        fig.colorbar(scatter, ax=axis, label="折衷值 Q")
        return fig

    _figure(context, "eval_vikor_utility_regret", draw, "未安装 matplotlib，跳过 VIKOR 图。")
    return registry.result(
        "eval.vikor",
        context.table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


@register("eval.rsr")
def rsr(context):
    matrix = context.table.matrix()
    names = context.table.feature_names
    if matrix.shape[1] < 1:
        raise MethodError("秩和比至少需要一个指标。")
    distribution = context.text("distribution", "normal", DISTRIBUTIONS)
    bins = context.whole("probit_bins", 7, 3, 15)
    scaled, _ = _normalized(context, matrix)
    weights = _weights(context, scaled)
    n_objects = matrix.shape[0]
    n_indicators = matrix.shape[1]
    from scipy.stats import norm, rankdata

    # Direction has already been unified: better observations must have higher
    # ascending ranks. Equal observations share their average rank.
    ranks = np.column_stack(
        [rankdata(scaled[:, index], method="average") for index in range(n_indicators)]
    )
    base = (ranks - 1.0) / (n_objects - 1) if n_objects > 1 else np.full_like(ranks, 0.5)
    rsr = base @ weights
    order = rankdata(-rsr, method="min").astype(int)
    probability = np.clip((rankdata(rsr, method="average") - 0.5) / n_objects, EPS, 1.0 - EPS)
    if distribution == "normal":
        probit = norm.ppf(probability)
    else:
        probit = probability * 100.0
    level = np.clip(((1.0 - probability) * bins).astype(int) + 1, 1, bins).astype(int)
    thresholds = _grade_thresholds(context)
    cuts = [np.percentile(rsr, value) for value in thresholds]
    grade = np.where(
        rsr >= cuts[3],
        "优",
        np.where(
            rsr >= cuts[2],
            "良",
            np.where(rsr >= cuts[1], "中", np.where(rsr >= cuts[0], "差", "很差")),
        ),
    )
    if np.ptp(rsr) <= EPS:
        grade[:] = "中"
    frames = pd.DataFrame(
        {
            "rank": order,
            "rsr": numbers(rsr, 6),
            "probit": numbers(probit, 6),
            "probit_level": level,
            "grade": grade,
        }
    )
    tables = {"scores": table_of(frames, limit=200)}
    if context.flag("emit_ranks", False):
        rank_frame = pd.DataFrame(
            np.column_stack([ranks.astype(float), rsr]),
            columns=[f"{name}_秩" for name in names] + ["rsr"],
        )
        rank_frame.insert(0, "对象", np.arange(1, n_objects + 1))
        tables["ranks"] = table_of(rank_frame, limit=200)

    def draw(plt):
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
        top = np.argsort(-rsr)[:15]
        axes[0].barh([str(index + 1) for index in top][::-1], rsr[top][::-1], color="#4f7cff")
        axes[0].set_title("RSR 得分前 15 位对象")
        axes[0].set_xlabel("加权 RSR")
        axes[0].grid(alpha=0.3, axis="x")
        grades = ["优", "良", "中", "差", "很差"]
        counts = [int((grade == name).sum()) for name in grades]
        axes[1].bar(grades, counts, color="#f59e0b")
        axes[1].set_title("分档结果分布")
        axes[1].set_ylabel("对象数")
        axes[1].grid(alpha=0.3, axis="y")
        return fig

    _figure(context, "eval_rsr_scores_grades", draw, "未安装 matplotlib，跳过 RSR 图。")
    return registry.result(
        "eval.rsr",
        context.table,
        metrics={
            "indicators": n_indicators,
            "objects": n_objects,
            "normalize": _normalization(context),
            "weighting": context.text("weighting", "entropy", WEIGHTINGS),
            "distribution": distribution,
            "probit_bins": bins,
            "grade_thresholds": thresholds,
            "best_rsr": round(float(rsr.max()), 6),
            "worst_rsr": round(float(rsr.min()), 6),
            "grades": {
                name: int((grade == name).sum()) for name in ("优", "良", "中", "差", "很差")
            },
        },
        tables=tables,
        notes=[
            "加权 RSR 把统一效益方向后的升序平均秩归一化，再按权重平均成 0–1 综合值；较大较好，相同观测同分同名次。",
            "weighting 支持 equal、entropy、critic 与 custom；给出 weights 时优先使用自定义权重。",
            "distribution=normal 用正态概率单位，none 用经验百分位；probit_level=1 为最高档。",
            "grade_thresholds 决定优/良/中/差/很差五档的百分位切点，默认 20/40/60/80。",
            "分档为当前样本内的相对评价；全部同分时统一记中，单个对象记中性分0.5。",
            "emit_ranks=True 额外输出各指标的秩次矩阵。",
        ],
    )


@register("eval.dea")
def dea(context):
    matrix = context.table.matrix()
    names = context.table.feature_names
    inputs = _as_list(context.want("input_columns"))
    outputs = _as_list(context.want("output_columns"))
    returns = context.text("returns", "crs", ("crs", "vrs"))
    orientation = context.text("orientation", "input", ("input", "output"))
    tol = context.number("tol", 1e-6, 1e-12, 0.01)
    stage = context.text("stage_two", "none", STAGES)
    digits = _digits(context, 6)
    if not inputs or not outputs:
        half = max(len(names) // 2, 1)
        inputs = inputs or names[:half]
        outputs = outputs or names[half:]
    if not inputs or not outputs:
        raise MethodError("DEA 需要至少一个投入指标和一个产出指标。")
    for name in inputs + outputs:
        if name not in names:
            raise MethodError(f"指标 {name} 不在特征中。可选：{'、'.join(names[:10])}")

    input_index = [names.index(name) for name in inputs]
    output_index = [names.index(name) for name in outputs]
    x = np.abs(matrix[:, input_index])
    y = np.abs(matrix[:, output_index])
    n = x.shape[0]
    if (x.sum(axis=1) <= EPS).any():
        raise MethodError("有对象的投入全为 0，无法计算效率。")

    from scipy.optimize import linprog

    def solve_frontier(input_matrix, output_matrix, kind, orientation_kind):
        rows = input_matrix.shape[0]
        width_in = input_matrix.shape[1]
        width_out = output_matrix.shape[1]
        variable = kind == "vrs"
        variables = width_in + width_out + (1 if variable else 0)
        constraints = np.vstack(
            [
                np.concatenate(
                    [-input_matrix[index], output_matrix[index], ([-1.0] if variable else [])]
                )
                for index in range(rows)
            ]
        )
        bounds = (
            [(0.0, None)] * width_in
            + [(0.0, None)] * width_out
            + ([(None, None)] if variable else [])
        )
        options = {
            "primal_feasibility_tolerance": max(tol, 1e-12),
            "dual_feasibility_tolerance": max(tol, 1e-12),
        }
        values = np.zeros(rows)
        vectors = [None] * rows
        count = 0
        for index in range(rows):
            if orientation_kind == "input":
                objective = np.concatenate(
                    [np.zeros(width_in), -output_matrix[index], ([1.0] if variable else [])]
                )
                equality = np.concatenate(
                    [input_matrix[index], np.zeros(width_out), ([0.0] if variable else [])]
                ).reshape(1, variables)
            else:
                objective = np.concatenate(
                    [input_matrix[index], np.zeros(width_out), ([1.0] if variable else [])]
                )
                equality = np.concatenate(
                    [np.zeros(width_in), output_matrix[index], ([0.0] if variable else [])]
                ).reshape(1, variables)
            found = linprog(
                objective,
                A_ub=constraints,
                b_ub=np.zeros(rows),
                A_eq=equality,
                b_eq=np.array([1.0]),
                bounds=bounds,
                method="highs",
                options=options,
            )
            if not found.success:
                found = linprog(
                    objective,
                    A_ub=constraints,
                    b_ub=np.zeros(rows),
                    A_eq=equality,
                    b_eq=np.array([1.0]),
                    bounds=bounds,
                    method="highs",
                )
            if found.success:
                if orientation_kind == "input":
                    values[index] = -found.fun
                else:
                    values[index] = 1.0 / found.fun if found.fun > EPS else 0.0
                vectors[index] = np.asarray(found.x[:width_in], dtype=float)
            else:
                count += 1
                values[index] = float("nan")
        return values, vectors, count

    efficiency, intensity, failures = solve_frontier(x, y, returns, orientation)
    if failures:
        context.warn(f"有 {failures} 个决策单元的线性规划未求得可行解，效率记 0。")

    efficiency = np.nan_to_num(efficiency, nan=0.0)
    threshold = 1.0 - max(tol, EPS)
    efficient = efficiency >= threshold
    ranks = _ranking(names, efficiency)
    frames = pd.DataFrame(
        {
            "rank": ranks,
            "efficiency": numbers(efficiency, digits),
            "efficient": efficient,
        }
    )
    tables = {"scores": table_of(frames, limit=200)}
    if context.flag("peers", False):
        rows = []
        for index in range(n):
            vector = intensity[index]
            peers = (
                []
                if vector is None
                else [entity for entity, value in enumerate(vector) if value > max(tol, 1e-8)]
            )
            rows.append(
                {
                    "object": index + 1,
                    "efficiency": round(float(efficiency[index]), digits),
                    "peer_count": len(peers),
                    "peers": "、".join(str(entity + 1) for entity in peers[:12]),
                }
            )
        tables["peers"] = table_of(pd.DataFrame(rows), limit=200)
    metrics = {
        "inputs": inputs,
        "outputs": outputs,
        "objects": n,
        "returns": returns,
        "orientation": orientation,
        "tol": tol,
        "stage_two": stage,
        "digits": digits,
        "solver_failures": failures,
        "efficient_units": int(efficient.sum()),
        "mean_efficiency": round(float(efficiency.mean()), digits),
        "min_efficiency": round(float(efficiency.min()), digits),
        "max_efficiency": round(float(efficiency.max()), digits),
    }
    notes = [
        "效率值为 1 表示该对象位于生产前沿面上。",
        "returns=crs 为规模报酬不变，vrs 为规模报酬可变；orientation 决定投入导向或产出导向。",
        "CRS 下两种导向互为倒数关系，折算到同一口径后数值一致；VRS 下两者不同。",
        "tol 同时作为线性规划的可行性容差与效率为 1 的判定容差。",
        "peers=True 时输出每个决策单元前沿面上的参考对象及其强度。",
        "stage_two=tobit 时用未参与效率计算的其余指标作为环境变量，对效率值做双侧截断回归。",
    ]
    if context.flag("scale_efficiency", False):
        crs_values, _, _ = solve_frontier(x, y, "crs", "input")
        vrs_values, _, _ = solve_frontier(x, y, "vrs", "input")
        crs_values = np.nan_to_num(crs_values, nan=0.0)
        vrs_values = np.nan_to_num(vrs_values, nan=0.0)
        scale = np.clip(
            np.divide(crs_values, np.where(vrs_values <= EPS, 1.0, vrs_values)), 0.0, 1.0
        )
        scale_frame = pd.DataFrame(
            {
                "object": np.arange(1, n + 1),
                "crs": numbers(crs_values, digits),
                "vrs": numbers(vrs_values, digits),
                "scale_efficiency": numbers(scale, digits),
                "scale_status": np.where(
                    scale >= threshold,
                    "规模有效",
                    np.where(crs_values < vrs_values, "规模报酬递增", "规模报酬递减"),
                ),
            }
        )
        tables["scale_efficiency"] = table_of(scale_frame, limit=200)
        metrics["mean_scale_efficiency"] = round(float(scale.mean()), digits)
        metrics["scale_efficient_units"] = int((scale >= threshold).sum())
        notes.append(
            "scale_efficiency=True 时同时求解 CRS 与 VRS 前沿，规模效率为两者之比，"
            "取 1 表示规模有效；该表里的 crs 与 vrs 两列固定按投入导向给出。"
        )
    if context.flag("sensitivity", False):
        specifications = []
        for position in range(x.shape[1]):
            keep_in = [item for item in range(x.shape[1]) if item != position]
            if keep_in:
                specifications.append((keep_in, list(range(y.shape[1]))))
        for position in range(y.shape[1]):
            keep_out = [item for item in range(y.shape[1]) if item != position]
            if keep_out:
                specifications.append((list(range(x.shape[1])), keep_out))
        rows = []
        for index in range(n):
            hits = []
            for keep_in, keep_out in specifications:
                local, _, _ = solve_frontier(x[:, keep_in], y[:, keep_out], returns, orientation)
                hits.append(float(np.nan_to_num(local, nan=0.0)[index]) >= threshold)
            rate = float(np.mean(hits)) if hits else 0.0
            rows.append(
                {
                    "object": index + 1,
                    "efficiency": round(float(efficiency[index]), digits),
                    "efficient_specifications": int(sum(hits)),
                    "specifications": len(hits),
                    "robust_rate": round(rate, digits),
                    "robust": bool(hits) and all(hits),
                }
            )
        tables["sensitivity"] = table_of(pd.DataFrame(rows), limit=200)
        metrics["sensitivity_specifications"] = len(specifications)
        metrics["mean_robust_rate"] = round(
            float(np.mean([row["robust_rate"] for row in rows])), digits
        )
        metrics["robust_units"] = int(sum(1 for row in rows if row["robust"]))
        notes.append(
            "sensitivity=True 时逐个剔除一项投入或产出重解前沿，"
            "稳健率高的对象其效率结论不依赖单一指标。"
        )

    def draw(plt):
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
        order = np.argsort(-efficiency)
        shown = order[:20]
        axes[0].bar([str(index + 1) for index in shown], efficiency[shown], color="#4f7cff")
        axes[0].tick_params(axis="x", labelrotation=90, labelsize=7)
        axes[0].axhline(1.0, color="#ef4444", linestyle="--", linewidth=1)
        axes[0].set_title("效率值前 20 位决策单元")
        axes[0].set_xlabel("决策单元")
        axes[0].set_ylabel("效率")
        axes[0].set_ylim(0.0, max(1.05, float(efficiency.max()) * 1.05))
        axes[0].grid(alpha=0.3, axis="y")
        axes[1].scatter(x.sum(axis=1), y.sum(axis=1), c=efficiency, cmap="viridis", s=30)
        axes[1].scatter(
            x[efficient].sum(axis=1),
            y[efficient].sum(axis=1),
            marker="o",
            s=70,
            facecolors="none",
            edgecolors="#ef4444",
            label="前沿面决策单元",
        )
        axes[1].set_xlabel("投入合计")
        axes[1].set_ylabel("产出合计")
        axes[1].set_title("投入产出与效率前沿")
        axes[1].legend(fontsize=8)
        axes[1].grid(alpha=0.3)
        return fig

    if stage == "tobit":
        environment = [name for name in names if name not in set(inputs) | set(outputs)]
        if not environment:
            context.warn("没有可用于二阶段回归的环境变量，已跳过 Tobit 回归。")
        else:
            environment_index = [names.index(name) for name in environment]
            outcome = _tobit_censored(efficiency, matrix[:, environment_index], 0.0, 1.0)
            beta = np.asarray(outcome.x[:-1], dtype=float)
            errors = None
            if hasattr(outcome, "hess_inv") and hasattr(outcome.hess_inv, "todense"):
                errors = np.sqrt(np.abs(np.diag(outcome.hess_inv.todense())))
            rows = []
            for position, term in enumerate(["常数项"] + environment):
                error = None if errors is None else float(errors[position])
                rows.append(
                    {
                        "term": term,
                        "coefficient": round(float(beta[position]), 6),
                        "std_error": None if error is None else round(error, 6),
                        "significant": None
                        if error is None
                        else bool(abs(beta[position] / max(error, EPS)) > 1.96),
                    }
                )
            tables["stage_two"] = table_of(pd.DataFrame(rows), limit=60)
            metrics["stage_two_censored"] = int(
                (efficiency <= 0.0).sum() + (efficiency >= 1.0).sum()
            )
            metrics["stage_two_log_likelihood"] = round(-float(outcome.fun), 6)
            metrics["stage_two_converged"] = bool(outcome.success)
            if not outcome.success:
                context.warn("二阶段 Tobit 回归未完全收敛，系数仅供参考。")
    _figure(context, "eval_dea_efficiency_frontier", draw, "未安装 matplotlib，跳过 DEA 图。")
    return registry.result(
        "eval.dea",
        context.table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


@register("eval.fuzzy")
def fuzzy(context):
    table = context.table
    matrix = table.matrix()
    names = table.feature_names
    levels = context.whole("levels", 5, 3, 9)
    operator = context.text("operator", "weighted", OPERATORS)
    shape = context.text("membership_shape", "triangle", SHAPES)
    normalize_rows = context.flag("normalize_membership", True)
    threshold = context.number("max_membership_warn", 0.5, 0.0, 1.0)
    lower = context.number("membership_lower", 0.0, 0.0, 1.0)
    upper = context.number("membership_upper", 1.0, 0.0, 1.0)
    if upper - lower < EPS:
        raise MethodError("隶属函数上界必须大于下界。")
    scaled, _ = _normalized(context, matrix)
    weights = _weights(context, scaled)

    edges = np.linspace(lower, upper, levels + 1)
    membership = np.zeros((matrix.shape[0], levels))
    for index in range(levels):
        low, high = edges[index], edges[index + 1]
        centre = (low + high) / 2
        width = max((high - low) / 2, EPS)
        offset = np.abs(scaled - centre)
        if shape == "trapezoid":
            block = np.clip(1.0 - np.maximum(offset - width * 0.4, 0.0) / width, 0.0, 1.0)
        elif shape == "gaussian":
            block = np.exp(-0.5 * (offset / width) ** 2)
        else:
            block = np.clip(1.0 - offset / width, 0.0, 1.0)
        membership[:, index] = (block * weights).sum(axis=1)
    if normalize_rows:
        row_sum = membership.sum(axis=1, keepdims=True)
        membership = np.divide(membership, np.where(row_sum <= EPS, 1.0, row_sum))

    graded = np.array([(edges[index] + edges[index + 1]) / 2 for index in range(levels)])
    if operator == "maxmin":
        score = membership.min(axis=1)
    elif operator == "average":
        score = membership.mean(axis=1)
    else:
        score = membership @ graded
    peak = membership.max(axis=1)
    weak = int((peak < threshold).sum())
    if weak:
        context.warn(f"有 {weak} 个样本的最大隶属度低于 {threshold}，评价结论偏模糊。")
    best_level = np.argmax(membership, axis=1)
    ranks = _ranking(names, score)
    frames = pd.DataFrame(
        {
            "rank": ranks,
            "score": numbers(score, 6),
            "peak_level": best_level + 1,
            "peak_membership": numbers(peak, 4),
            "membership": [numbers(row, 4) for row in membership],
        }
    )
    tables = {"scores": table_of(frames, limit=120)}
    if context.flag("emit_membership", False):
        level_frame = pd.DataFrame(
            np.round(membership, 4), columns=[f"等级{index + 1}" for index in range(levels)]
        )
        level_frame.insert(0, "对象", np.arange(1, matrix.shape[0] + 1))
        tables["membership"] = table_of(level_frame, limit=200)

    def draw(plt):
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
        shade = axes[0].imshow(
            membership,
            aspect="auto",
            cmap="YlGnBu",
            vmin=0.0,
            vmax=max(float(membership.max()), EPS),
        )
        axes[0].set_xticks(range(levels))
        axes[0].set_xticklabels([f"等级{index + 1}" for index in range(levels)])
        axes[0].set_xlabel("评语等级")
        axes[0].set_ylabel("对象")
        axes[0].set_title("等级隶属度热力图")
        fig.colorbar(shade, ax=axes[0])
        top = np.argsort(-score)[:15]
        axes[1].barh([str(index + 1) for index in top][::-1], score[top][::-1], color="#4f7cff")
        axes[1].set_title("综合得分前 15 位对象")
        axes[1].set_xlabel("综合得分")
        axes[1].grid(alpha=0.3, axis="x")
        return fig

    _figure(context, "eval_fuzzy_membership_scores", draw, "未安装 matplotlib，跳过模糊评价图。")
    notes = [
        "隶属度按等宽隶属函数构造，再按权重合成。",
        "weighted 用等级中心值加权，maxmin 取最保守的隶属度，average 取平均。",
        "membership_shape 支持 triangle 三角、trapezoid 梯形与 gaussian 高斯隶属函数。",
        "normalize_membership=True 时把每个样本的各等级隶属度归一化到和为 1。",
        "weighting 支持 equal、entropy、critic 与 custom；给出 weights 时优先使用自定义权重。",
        "最大隶属度低于 max_membership_warn 的样本会记入警告。",
        "emit_membership=True 额外输出各对象的等级隶属度表。",
    ]
    if lower != 0.0 or upper != 1.0:
        notes.insert(3, f"隶属函数区间取 [{lower}, {upper}]，等级按该区间等宽划分。")
    return registry.result(
        "eval.fuzzy",
        table,
        metrics={
            "indicators": len(names),
            "levels": levels,
            "operator": operator,
            "membership_shape": shape,
            "normalize_membership": normalize_rows,
            "objects": matrix.shape[0],
            "weighting": context.text("weighting", "entropy", WEIGHTINGS),
            "max_membership_warn": threshold,
            "low_membership": weak,
            "best_score": round(float(score.max()), 6),
            "mean_peak_membership": round(float(peak.mean()), 4),
            "weights": numbers(weights, 6),
        },
        tables=tables,
        notes=notes,
    )


@register("eval.grey")
def grey(context):
    table = context.table
    matrix = table.matrix()
    names = table.feature_names
    rho = context.number("rho", 0.5, 0.0, 1.0)
    reference = context.text("reference", "best")
    if reference not in REFERENCES:
        raise MethodError("reference 只能是 best 或 worst。")
    scaled, _ = _normalized(context, matrix)
    if reference == "worst":
        scaled = 1.0 - scaled
    reference_row = scaled.max(axis=0)
    difference = np.abs(scaled - reference_row)
    baseline = context.text("min_baseline", "sample", BASELINES)
    smallest = float(difference.min()) if baseline == "sample" else 0.0
    largest = float(difference.max())
    denominator = difference + rho * largest
    coefficient = np.divide(
        smallest + rho * largest, np.where(denominator <= EPS, 1.0, denominator)
    )
    weights = _weights(context, scaled)
    grade = coefficient @ weights
    ranks = _ranking(names, grade)
    frames = pd.DataFrame(
        {
            "rank": ranks,
            "grey_grade": numbers(grade, 6),
            "min_coefficient": numbers(coefficient.min(axis=1), 6),
            "max_coefficient": numbers(coefficient.max(axis=1), 6),
        }
    )
    tables = {"scores": table_of(frames, limit=200)}
    if context.flag("emit_coefficient", False):
        coefficient_frame = pd.DataFrame(np.round(coefficient, 6), columns=names)
        coefficient_frame.insert(0, "对象", np.arange(1, matrix.shape[0] + 1))
        tables["coefficient"] = table_of(coefficient_frame, limit=200)

    def draw(plt):
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
        top = np.argsort(-grade)[:15]
        axes[0].barh([str(index + 1) for index in top][::-1], grade[top][::-1], color="#4f7cff")
        axes[0].set_title("灰色关联度前 15 位对象")
        axes[0].set_xlabel("加权关联度")
        axes[0].grid(alpha=0.3, axis="x")
        positions = np.arange(len(names))
        means = coefficient.mean(axis=0)
        spread = coefficient.max(axis=0) - coefficient.min(axis=0)
        axes[1].bar(
            positions,
            means,
            yerr=spread / 2.0,
            color="#f59e0b",
            error_kw={"ecolor": "#94a3b8", "elinewidth": 1, "capsize": 2},
        )
        axes[1].set_xticks(positions)
        axes[1].set_xticklabels(names, rotation=45, ha="right", fontsize=7)
        axes[1].set_title("各指标关联系数均值与极差")
        axes[1].set_ylabel("关联系数")
        axes[1].grid(alpha=0.3, axis="y")
        return fig

    _figure(context, "eval_grey_grades_coefficients", draw, "未安装 matplotlib，跳过灰色关联图。")
    return registry.result(
        "eval.grey",
        table,
        metrics={
            "indicators": len(names),
            "objects": matrix.shape[0],
            "rho": rho,
            "reference": reference,
            "normalize": _normalization(context),
            "min_baseline": baseline,
            "weighting": context.text("weighting", "entropy", WEIGHTINGS),
            "best_grade": round(float(grade.max()), 6),
            "min_difference": round(float(smallest), 6),
            "max_difference": round(float(largest), 6),
            "weights": numbers(weights, 6),
        },
        tables=tables,
        notes=[
            "灰色关联度越接近 1 表示与参考序列越相似。",
            "分辨系数 rho 一般取 0.5，越小则差异越被放大。",
            "reference=best 以各指标最优值为参考序列，worst 以最差值为参考序列。",
            "min_baseline=sample 用实际最小差，zero 把两级最小差固定为 0。",
            "weighting 支持 equal、entropy、critic 与 custom；给出 weights 时优先使用自定义权重。",
            "emit_coefficient=True 额外输出关联系数矩阵。",
        ],
    )


@register("eval.pca")
def pca_evaluation(context):
    table = context.table
    matrix = table.matrix()
    names = table.feature_names
    if len(names) < 2:
        raise MethodError("主成分评价至少需要两个指标。")
    scaled, _ = _normalized(context, matrix)
    selection = context.text("select", "fixed", SELECTIONS)
    threshold = context.number("cumulative_threshold", 0.85, 0.5, 1.0)
    eigenvalue_threshold = context.number("eigenvalue_threshold", 1.0, 0.5, 3.0)
    loading_threshold = context.number("loading_threshold", 0.0, 0.0, 1.0)
    correlation, correlation_name = _correlation_matrix(context, scaled)
    if selection == "eigenvalue" and (
        _normalization(context) != "zscore" or correlation_name != "pearson"
    ):
        context.warn(
            "select=eigenvalue 的特征值大于 1 准则通常配合 normalize=zscore 与"
            " correlation=pearson 使用。"
        )
    top = min(context.whole("components", len(names), 1, len(names)), matrix.shape[0])
    weighting = context.text("weighting", "variance", ("variance", "equal"))
    rotate = context.flag("rotate", False)
    limit = int(min(len(names), matrix.shape[0]))
    centred = np.asarray(scaled, dtype=float) - np.asarray(scaled, dtype=float).mean(axis=0)
    left, singular, right = np.linalg.svd(centred, full_matrices=False)
    signs = np.sign(left[np.argmax(np.abs(left), axis=0), np.arange(left.shape[1])])
    signs = np.where(signs == 0.0, 1.0, signs)
    left = left * signs
    right = right * signs[:, None]
    reference_values = (singular**2) / max(centred.shape[0] - 1, 1)
    if correlation_name == "pearson":
        eigenvalues = reference_values
        eigenvectors = right.T
        ratios = eigenvalues / max(float(eigenvalues.sum()), EPS)
        scores = left * singular
        loadings = eigenvectors
    else:
        eigenvalues, eigenvectors = _eigen_basis(correlation)
        eigenvectors = np.asarray(eigenvectors, dtype=float)
        ratios = eigenvalues / max(float(eigenvalues.sum()), EPS)
        proper = eigenvectors * np.sqrt(eigenvalues)
        scores = centred @ proper
        loadings = eigenvectors
    for_cumulative = int(np.searchsorted(np.cumsum(ratios), threshold - 1e-12) + 1)
    if selection == "eigenvalue":
        top = int(max(1, int((eigenvalues >= eigenvalue_threshold).sum())))
    elif selection == "cumulative":
        top = int(max(1, for_cumulative))
    top = int(min(max(top, 1), limit))
    scores = scores[:, :top]
    weights = ratios[:top]
    loadings = eigenvectors[:, :top]
    used = scores
    if rotate:
        proper = loadings * np.sqrt(eigenvalues[:top])
        rotated, rotation = _varimax(proper)
        loadings = rotated
        used = scores @ rotation
        weights = (
            _share((rotated**2).sum(axis=0)) if weighting == "variance" else np.full(top, 1.0 / top)
        )
    elif weighting == "equal":
        weights = np.full(top, 1.0 / top)
    composite = used @ weights
    composite = composite - composite.min()
    if composite.max() > EPS:
        composite = composite / composite.max()
    ranks = _ranking(names, composite)
    loadings_frame = pd.DataFrame(loadings, columns=[f"PC{i + 1}" for i in range(top)], index=names)
    if loading_threshold > 0:
        loadings_frame = loadings_frame.mask(loadings_frame.abs() < loading_threshold)
    loadings_frame = loadings_frame.reset_index().rename(columns={"index": "indicator"})
    variance = pd.DataFrame(
        {
            "component": [f"PC{i + 1}" for i in range(top)],
            "explained": numbers(weights, 6),
            "cumulative": numbers(np.cumsum(weights), 6),
        }
    )
    tables = {
        "scores": table_of(
            pd.DataFrame({"rank": ranks, "score": numbers(composite, 6)}), limit=200
        ),
        "loadings": table_of(loadings_frame, limit=60),
        "variance": table_of(variance, limit=30),
    }
    if context.flag("emit_scores", False):
        if rotate:
            score_frame = pd.DataFrame(
                np.round(used, 6), columns=[f"PC{i + 1}" for i in range(top)]
            )
        else:
            score_frame = pd.DataFrame(
                np.round(scores, 6), columns=[f"PC{i + 1}" for i in range(top)]
            )
            score_frame["score"] = numbers(composite, 6)
        score_frame.insert(0, "对象", np.arange(1, used.shape[0] + 1))
        tables["component_scores"] = table_of(score_frame, limit=200)

    def draw(plt):
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
        shade = axes[0].imshow(
            loadings,
            aspect="auto",
            cmap="RdBu_r",
            vmin=-max(float(np.abs(loadings).max()), EPS),
            vmax=max(float(np.abs(loadings).max()), EPS),
        )
        axes[0].set_xticks(range(top))
        axes[0].set_xticklabels([f"PC{index + 1}" for index in range(top)])
        axes[0].set_yticks(range(len(names)))
        axes[0].set_yticklabels(names, fontsize=8)
        axes[0].set_title("主成分载荷热力图")
        fig.colorbar(shade, ax=axes[0], label="载荷")
        positions = np.arange(1, top + 1)
        axes[1].bar(positions, ratios[:top] * 100.0, color="#4f7cff")
        axes[1].plot(positions, np.cumsum(ratios[:top]) * 100.0, color="#f59e0b", marker="o")
        axes[1].set_xticks(positions)
        axes[1].set_xlabel("主成分")
        axes[1].set_ylabel("方差解释率 (%)")
        axes[1].set_title("主成分方差解释率与累计")
        axes[1].grid(alpha=0.3)
        return fig

    _figure(context, "eval_pca_loadings_variance", draw, "未安装 matplotlib，跳过主成分图。")
    notes = [
        "weighting=variance 用各主成分的方差贡献率作权重，equal 用等权。",
        "rotate=True 对载荷做方差极大旋转，避免主观赋权以外的结构解释困难。",
        "select=fixed 用 components 指定个数，eigenvalue 保留特征值大于 1 的成分，"
        "cumulative 保留累计方差达到 cumulative_threshold 的成分。",
        "loading_threshold 大于 0 时，载荷表中绝对值小于该阈值的载荷显示为空。",
        "emit_scores=True 额外输出主成分得分矩阵。",
        "主成分是原始指标的线性组合，综合评价结论的可解释性弱于熵值法。",
    ]
    if eigenvalue_threshold != 1.0:
        notes[2] = (
            "select=fixed 用 components 指定个数，eigenvalue 保留特征值大于 "
            f"{eigenvalue_threshold} 的成分，cumulative 保留累计方差达到 "
            "cumulative_threshold 的成分。"
        )
    if correlation_name != "pearson":
        notes.insert(3, f"相关阵口径为 {correlation_name}，主成分载荷与得分据此计算。")
    return registry.result(
        "eval.pca",
        table,
        metrics={
            "indicators": len(names),
            "components": top,
            "select": selection,
            "cumulative_threshold": threshold,
            "components_for_cumulative": for_cumulative,
            "loading_threshold": loading_threshold,
            "normalize": _normalization(context),
            "weighting": weighting,
            "rotate": rotate,
            "explained_total": round(float(np.cumsum(weights)[-1]), 6),
            "first_component_share": round(float(weights[0]), 6),
        },
        tables=tables,
        notes=notes,
    )


@register("eval.factor")
def factor_evaluation(context):
    from statsmodels.multivariate.factor import Factor

    table = context.table
    chosen = context.want("columns")
    names, matrix = registry.subset(table, chosen)
    if len(names) < 3:
        raise MethodError("因子分析至少需要三个指标。")
    standardize = context.flag("standardize", True)
    extract = context.text("extract", "principal", EXTRACTIONS)
    rotate = context.text("rotate", "varimax", ROTATIONS)
    scores_method = context.text("scores_method", "regression", SCORE_METHODS)
    promax_power = context.number("promax_power", 4.0, 2.0, 8.0)
    factors = context.whole("factors", max(1, len(names) // 3), 1, max(len(names) - 1, 1))
    adjustment = _benefit_direction(context, matrix)
    matrix = np.asarray(matrix, dtype=float) * adjustment
    if standardize:
        data, _, _ = registry.standardize(matrix)
        covariance = _pairwise(data, context.text("correlation", "pearson", CORRELATIONS))
        matrix_kind = "相关系数矩阵"
    else:
        data = np.asarray(matrix, dtype=float)
        covariance = np.cov(data, rowvar=False)
        matrix_kind = "协方差矩阵"
    covariance = np.nan_to_num(np.atleast_2d(covariance), nan=0.0)
    if extract == "ml":
        try:
            model = Factor(np.asarray(data, dtype=float), n_factor=factors, method="ml")
            fitted = model.fit()
            raw_loadings = np.asarray(fitted.loadings, dtype=float)
            uniqueness = np.clip(np.asarray(fitted.uniqueness, dtype=float), 0.0, None)
            raw_scores = np.asarray(fitted.factor_scoring(method="regression"), dtype=float)
            eigenvalues, _ = _eigen_basis(covariance)
        except Exception:
            context.warn("极大似然提取未收敛，已改用主轴因子法（minres）。")
            raw_loadings, eigenvalues, raw_scores = _principal_axis_loadings(
                covariance, data, factors
            )
            uniqueness = np.clip(np.diag(covariance) - (raw_loadings**2).sum(axis=1), 0.0, None)
    elif extract == "minres":
        raw_loadings, eigenvalues, raw_scores = _principal_axis_loadings(covariance, data, factors)
        uniqueness = np.clip(np.diag(covariance) - (raw_loadings**2).sum(axis=1), 0.0, None)
    else:
        raw_loadings, eigenvalues, raw_scores = _principal_loadings(covariance, data, factors)
        uniqueness = np.clip(np.diag(covariance) - (raw_loadings**2).sum(axis=1), 0.0, None)

    if scores_method == "bartlett":
        raw_scores = _bartlett_scores(data, raw_loadings, uniqueness)
    rotated, rotation = _rotate_loadings(raw_loadings, rotate, promax_power)
    scores = np.asarray(raw_scores, dtype=float) @ rotation
    communality = (rotated**2).sum(axis=1)
    explained = (rotated**2).sum(axis=0)
    weights = _share(explained)
    total_variance = float(np.asarray(eigenvalues, dtype=float).sum())
    composite = scores @ weights
    composite = composite - composite.min()
    if composite.max() > EPS:
        composite = composite / composite.max()
    ranks = _ranking(names, composite)

    loading_frame = pd.DataFrame(
        rotated, index=names, columns=[f"因子{i + 1}" for i in range(factors)]
    )
    variance_frame = pd.DataFrame(
        {
            "factor": [f"因子{i + 1}" for i in range(factors)],
            "variance": numbers(explained, 6),
            "proportion": numbers(weights, 6),
            "cumulative": numbers(np.cumsum(weights), 6),
        }
    )
    detail = pd.DataFrame(
        {
            "indicator": names,
            "communality": numbers(communality, 6),
            "specific_variance": numbers(uniqueness, 6),
        }
    )
    metrics = {
        "indicators": len(names),
        "factors": factors,
        "extract": extract,
        "rotate": rotate,
        "standardize": standardize,
        "scores_method": scores_method,
        "matrix": matrix_kind,
        "explained_total": round(float(weights.sum()), 6),
        "mean_communality": round(float(communality.mean()), 6),
        "matrix_total_variance": round(total_variance, 6),
        "components_for_1_eigenvalue": int((np.asarray(eigenvalues) >= 1.0).sum()),
    }
    tables = {
        "loadings": table_of(
            loading_frame.reset_index().rename(columns={"index": "indicator"}), limit=60
        ),
        "variance": table_of(variance_frame, limit=20),
        "communality": table_of(detail, limit=60),
        "scores": table_of(
            pd.DataFrame({"rank": ranks, "score": numbers(composite, 6)}), limit=200
        ),
    }
    notes = [
        "公因子方差（communality）表示该指标被公共因子解释的比例。",
        "extract=principal 用主成分解，minres 用主轴迭代，ml 用极大似然。",
        "standardize=True 在相关系数矩阵上做分析，False 在协方差矩阵上做分析。",
        "rotate 支持 varimax、promax 与 none，旋转会同时作用在载荷与因子得分上。",
        "scores_method 支持 regression 回归法与 bartlett 加权最小二乘法。",
    ]
    if context.text("correlation", "pearson", CORRELATIONS) != "pearson":
        notes.insert(
            3,
            "相关阵口径为 "
            f"{context.text('correlation', 'pearson', CORRELATIONS)}，"
            "参与分析的指标按该相关系数口径标准化。",
        )
    if context.flag("kmo", False):
        statistic, per_indicator = _kmo_statistics(data)
        known = [value for value in per_indicator if value is not None]
        metrics["kmo"] = None if statistic is None else round(float(statistic), 6)
        metrics["kmo_min_msa"] = None if not known else round(float(min(known)), 6)
        msa_frame = pd.DataFrame(
            {
                "indicator": names,
                "msa": [
                    None if value is None else round(float(value), 6) for value in per_indicator
                ],
            }
        )
        tables["kmo"] = table_of(msa_frame, limit=60)
        notes.append("KMO 越接近 1 越适合做因子分析，低于 0.6 时结构可能不稳定。")
    if context.flag("bartlett", False):
        statistic, dof, pvalue = _bartlett_test(data)
        metrics["bartlett_chi2"] = None if statistic is None else round(float(statistic), 6)
        metrics["bartlett_df"] = dof
        metrics["bartlett_p"] = None if pvalue is None else round(float(pvalue), 6)
        bartlett_frame = pd.DataFrame(
            [{"chi2": metrics["bartlett_chi2"], "df": dof, "p": metrics["bartlett_p"]}]
        )
        tables["bartlett"] = table_of(bartlett_frame, limit=5)
        if pvalue is not None and pvalue >= 0.05:
            context.warn(f"Bartlett 球形检验 p={pvalue:.4f}，指标间相关不足，因子结构可能不成立。")
        notes.append("Bartlett 球形检验的 p 值小于 0.05 时说明指标间存在可利用的共同变异。")
    if context.flag("emit_scores", False):
        score_frame = pd.DataFrame(
            np.round(scores, 6), columns=[f"因子{i + 1}" for i in range(factors)]
        )
        score_frame.insert(0, "对象", np.arange(1, scores.shape[0] + 1))
        score_frame["score"] = numbers(composite, 6)
        tables["factor_scores"] = table_of(score_frame, limit=200)
        notes.append("emit_scores=True 额外输出各对象的因子得分矩阵。")

    def draw(plt):
        fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
        limit = max(float(np.abs(rotated).max()), EPS)
        shade = axes[0].imshow(rotated, aspect="auto", cmap="RdBu_r", vmin=-limit, vmax=limit)
        axes[0].set_xticks(range(factors))
        axes[0].set_xticklabels([f"因子{index + 1}" for index in range(factors)])
        axes[0].set_yticks(range(len(names)))
        axes[0].set_yticklabels(names, fontsize=8)
        axes[0].set_title("旋转后因子载荷热力图")
        fig.colorbar(shade, ax=axes[0], label="载荷")
        positions = np.arange(1, factors + 1)
        axes[1].bar(positions, explained, color="#4f7cff")
        axes[1].plot(positions, np.cumsum(explained), color="#f59e0b", marker="o")
        axes[1].set_xticks(positions)
        axes[1].set_xlabel("因子")
        axes[1].set_ylabel("方差贡献")
        axes[1].set_title("因子方差贡献与累计")
        axes[1].grid(alpha=0.3)
        return fig

    _figure(context, "eval_factor_loadings_variance", draw, "未安装 matplotlib，跳过因子分析图。")
    return registry.result(
        "eval.factor",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )
