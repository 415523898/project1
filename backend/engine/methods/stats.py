import math

import numpy as np
import pandas as pd

from engine import registry
from engine.registry import MethodError, register, table_of

EPS = 1e-12

STAT_KEYS = ("mean", "median", "sum", "std", "var", "sem", "min", "max", "range", "count")
ALTERNATIVES = ("two-sided", "greater", "less")
CORRECTION_LABELS = {"none": "不校正", "bonferroni": "Bonferroni", "sidak": "Šidák", "holm": "Holm"}
CI_LABELS = {"wilson": "Wilson", "wald": "Wald 正态近似", "exact": "Clopper-Pearson 精确"}
DIVERGENCE = {
    "pearson": 1.0,
    "cressie_read": 2.0 / 3.0,
    "g_test": 0.0,
    "neyman": -0.5,
    "freeman_tukey": -1.0,
}
DIVERGENCE_LABELS = {
    "pearson": "Pearson 卡方",
    "cressie_read": "Cressie-Read（λ=2/3）",
    "g_test": "似然比 G 检验（λ=0）",
    "neyman": "Neyman 修正（λ=-1/2）",
    "freeman_tukey": "Freeman-Tukey（λ=-1）",
}
POWER_ALTERNATIVES = {"two-sided": "two-sided", "greater": "larger", "less": "smaller"}
PAIR_LIMIT = 4000


def _pick_columns(table, chosen):
    if not chosen:
        return [str(name) for name in table.raw.columns]
    names = [str(name).strip() for name in chosen if str(name).strip()]
    if not names:
        raise MethodError("至少需要选择一列。")
    absent = [name for name in names if name not in table.raw.columns]
    if absent:
        raise MethodError(
            f"列 {'、'.join(absent)} 不在数据里。可用列："
            f"{'、'.join(str(name) for name in table.raw.columns[:20])}。"
        )
    return names


def _group_name(table, column=None):
    name = column or table.group_name
    if name:
        if name not in table.raw.columns:
            raise MethodError(f"分组列 {name} 不在数据里。")
        return name
    for candidate in table.raw.columns:
        if candidate == table.target_name:
            continue
        if table.raw[candidate].nunique(dropna=True) <= 12:
            return candidate
    raise MethodError("需要一个分组列（或二值目标列）。")


def _bucketize(keys, values):
    buckets = {}
    for key, value in zip(keys, values):
        if value is None or not np.isfinite(float(value)):
            continue
        buckets.setdefault(str(key), []).append(float(value))
    return {key: np.array(items, dtype=float) for key, items in buckets.items()}


def _category_labels(series):
    labels = series.astype("string")
    if not labels.isna().any():
        return labels
    # A display label must not merge actual categories with missing observations.
    existing = set(labels.dropna())
    missing = "（空值）"
    number = 2
    while missing in existing:
        missing = f"（空值{number}）"
        number += 1
    return labels.fillna(missing)


def _labeled_table(frame, limit=50):
    occupied = {str(name) for name in frame.columns}
    name = str(frame.index.name or "行类别")
    while name in occupied:
        name += "（行类别）"
    return table_of(frame.rename_axis(name).reset_index(), limit=limit)


def _groups(context, column=None, target=None):
    table = context.table
    if table.target_name is None:
        raise MethodError("该方法需要目标列。")
    response = table.numeric_target()
    name = _group_name(table, column)
    valid = table.raw[name].notna().to_numpy() & np.isfinite(response)
    if not valid.all():
        context.warn(
            f"分组检验排除分组或响应缺失的 {int((~valid).sum())} 行；未将缺失标志作为真实处理组。"
        )
    keys = table.raw.loc[valid, name].astype("string").to_numpy()
    buckets = _bucketize(keys, response[valid])
    if len(buckets) < 1:
        raise MethodError("分组后没有可用样本。")
    return name, buckets


def _paired_groups(context, column=None):
    table = context.table
    name = _group_name(table, column)
    subject = context.text("subject") or table.group_name
    if not subject or subject == name or subject not in table.raw:
        raise MethodError(
            "配对/重复测量检验需要 subject 指定受试者或区组编号，不能按组内行序拼接。"
        )
    if not table.target_name:
        raise MethodError("配对检验需要数值目标列。")
    source = table.raw[[subject, name, table.target_name]].copy()
    source[table.target_name] = pd.to_numeric(source[table.target_name], errors="coerce")
    if source[[subject, name]].isna().any().any():
        raise MethodError("受试者编号或处理组有缺失，无法确认配对关系。")
    if source.duplicated([subject, name]).any():
        raise MethodError("同一受试者在同一处理下有多条记录，请先明确重复测量的汇总规则。")
    wide = source.pivot(index=subject, columns=name, values=table.target_name)
    valid = np.isfinite(wide.to_numpy(dtype=float)).all(axis=1)
    omitted = int((~valid).sum())
    if omitted:
        context.warn(f"配对按 {subject} 对齐，排除缺少部分处理或结果的 {omitted} 个受试者。")
    wide = wide.loc[valid]
    if wide.empty:
        raise MethodError("没有覆盖全部处理的完整配对受试者。")
    return name, {str(key): wide[key].to_numpy(dtype=float) for key in wide.columns}


def _round(value, digits):
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, int(digits))


def _aggregate(values, stat, digits=6):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if stat == "count":
        return int(values.size)
    if values.size == 0:
        return None
    if stat == "mean":
        return round(float(values.mean()), int(digits))
    if stat == "median":
        return round(float(np.median(values)), int(digits))
    if stat == "sum":
        return round(float(values.sum()), int(digits))
    if stat == "std":
        return round(float(values.std(ddof=1)), int(digits)) if values.size > 1 else None
    if stat == "var":
        return round(float(values.var(ddof=1)), int(digits)) if values.size > 1 else None
    if stat == "sem":
        return (
            round(float(values.std(ddof=1)) / math.sqrt(values.size), int(digits))
            if values.size > 1
            else None
        )
    if stat == "min":
        return round(float(values.min()), int(digits))
    if stat == "max":
        return round(float(values.max()), int(digits))
    if stat == "range":
        return round(float(values.max() - values.min()), int(digits))
    return int(values.size)


def _quantile(values, point, digits=6):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return None
    return round(float(np.quantile(values, point)), int(digits))


def _trimmed(values, trim):
    values = np.sort(np.asarray(values, dtype=float))
    cut = int(math.floor(values.size * trim))
    if values.size - 2 * cut < 1:
        return None
    core = values[cut : values.size - cut] if cut else values
    return float(core.mean())


def _parse_quantiles(raw):
    if not raw:
        return []
    items = []
    for part in str(raw).replace("，", ",").split(","):
        text = part.strip()
        if not text:
            continue
        try:
            value = float(text)
        except ValueError:
            raise MethodError(
                f"附加分位点 {text} 不是数字，请用逗号分隔 0 到 1 之间的数。"
            ) from None
        if not 0.0 < value < 1.0:
            raise MethodError(f"附加分位点 {text} 必须在 0 与 1 之间（不含端点）。")
        if any(abs(value - other) < 1e-9 for _, other in items):
            continue
        scaled = value * 100.0
        if abs(scaled - round(scaled)) < 1e-9:
            tag = f"{int(round(scaled)):02d}"
        else:
            tag = f"{scaled:g}".replace(".", "")
        items.append((tag, value))
    if not items:
        raise MethodError("附加分位点没有解析出有效数值。")
    if len(items) > 6:
        raise MethodError("附加分位点最多 6 个。")
    return items


def _cohens_d(first, second):
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    if first.size < 2 or second.size < 2:
        return None
    pooled = (first.size - 1) * first.var(ddof=1) + (second.size - 1) * second.var(ddof=1)
    pooled = pooled / (first.size + second.size - 2)
    if pooled <= EPS:
        return None
    return float((first.mean() - second.mean()) / math.sqrt(pooled))


def _adjust(raw, correction):
    values = np.asarray(raw, dtype=float)
    count = values.size
    if count == 0 or correction in (None, "none"):
        return values
    if correction == "bonferroni":
        return np.minimum(values * count, 1.0)
    if correction == "sidak":
        return np.minimum(1.0 - np.power(1.0 - values, count), 1.0)
    order = np.argsort(values, kind="stable")
    adjusted = np.empty(count)
    running = 0.0
    for position, index in enumerate(order):
        running = max(running, (count - position) * values[index])
        adjusted[index] = min(running, 1.0)
    return adjusted


def _percent_frame(counts, mode, digits=3):
    total = float(counts.to_numpy().sum())
    if mode == "row":
        base = counts.sum(axis=1).astype(float).replace(0.0, np.nan)
        share = counts.div(base, axis=0).fillna(0.0)
    elif mode == "column":
        base = counts.sum(axis=0).astype(float).replace(0.0, np.nan)
        share = counts.div(base, axis=1).fillna(0.0)
    elif total > 0:
        share = counts.astype(float) / total
    else:
        share = counts.astype(float) * 0.0
    return pd.DataFrame(
        np.round(share.to_numpy(dtype=float) * 100.0, int(digits)),
        index=counts.index,
        columns=counts.columns,
    )


def _binned(series, bins):
    if pd.api.types.is_numeric_dtype(series) and series.nunique(dropna=True) > bins:
        cut = pd.cut(pd.to_numeric(series, errors="coerce"), bins=bins, duplicates="drop")
        return _category_labels(cut)
    return _category_labels(series)


def _median_ci(values, level):
    from scipy import stats as sps

    values = np.sort(np.asarray(values, dtype=float))
    values = values[np.isfinite(values)]
    size = values.size
    if size < 3:
        return None, None
    best = None
    for rank in range((size - 1) // 2):
        cover = float(sps.binom.cdf(size - rank, size, 0.5) - sps.binom.cdf(rank, size, 0.5))
        if cover >= level:
            best = rank
        else:
            break
    if best is None:
        return None, None
    return float(values[best]), float(values[size - 1 - best])


def _walsh_bounds(values, level):
    from scipy import stats as sps

    values = np.sort(np.asarray(values, dtype=float))
    values = values[np.isfinite(values)]
    size = values.size
    total = size * (size + 1) // 2
    averages = ((values[:, None] + values[None, :]) / 2.0)[np.triu_indices(size)]
    averages.sort()
    spread = math.sqrt(size * (size + 1) * (2 * size + 1) / 24.0)
    critical = int(
        math.floor(
            size * (size + 1) / 4.0 - float(sps.norm.ppf((1.0 + level) / 2.0)) * spread - 0.5
        )
    )
    critical = max(min(critical, total // 2 - 1), 0)
    return (
        float(averages[critical]),
        float(averages[total - 1 - critical]),
        float(np.median(averages)),
    )


def _shift_bounds(first, second, level):
    from scipy import stats as sps

    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    differences = np.sort((first[:, None] - second[None, :]).ravel())
    total = differences.size
    spread = math.sqrt(first.size * second.size * (first.size + second.size + 1) / 12.0)
    critical = int(
        math.floor(total / 2.0 - float(sps.norm.ppf((1.0 + level) / 2.0)) * spread - 0.5)
    )
    critical = max(min(critical, total // 2 - 1), 0)
    return (
        float(differences[critical]),
        float(differences[total - 1 - critical]),
        float(np.median(differences)),
    )


def _effect_bounds(statistic, dfree, level, standardizer):
    from scipy import stats as sps
    from scipy.optimize import brentq

    alpha = 1.0 - level

    def bound(target):
        def function(point):
            return float(sps.nct.cdf(statistic, dfree, point)) - target

        low, high = statistic - 1.0, statistic + 1.0
        step = 1.0
        while function(low) < 0.0:
            low -= step
            step *= 2.0
        step = 1.0
        while function(high) > 0.0:
            high += step
            step *= 2.0
        return float(brentq(function, low, high))

    return (bound(1.0 - alpha / 2.0) * standardizer, bound(alpha / 2.0) * standardizer)


def _wilson(successes, total, level):
    from scipy import stats as sps

    if total <= 0:
        return None, None
    critical = float(sps.norm.ppf((1.0 + level) / 2.0))
    share = successes / float(total)
    denominator = 1.0 + critical * critical / total
    center = (share + critical * critical / (2.0 * total)) / denominator
    spread = (
        critical
        * math.sqrt(share * (1.0 - share) / total + critical * critical / (4.0 * total * total))
        / denominator
    )
    return max(center - spread, 0.0), min(center + spread, 1.0)


def _proportion_ci(successes, total, level, method):
    from scipy import stats as sps

    if total <= 0:
        return None, None
    if method == "wald":
        critical = float(sps.norm.ppf((1.0 + level) / 2.0))
        share = successes / float(total)
        spread = critical * math.sqrt(share * (1.0 - share) / total)
        return max(share - spread, 0.0), min(share + spread, 1.0)
    if method == "exact":
        alpha = 1.0 - level
        low = (
            0.0
            if successes <= 0
            else float(sps.beta.ppf(alpha / 2.0, successes, total - successes + 1))
        )
        high = (
            1.0
            if successes >= total
            else float(sps.beta.ppf(1.0 - alpha / 2.0, successes + 1, total - successes))
        )
        return low, high
    return _wilson(successes, total, level)


def _welch_anova(groups):
    from scipy import stats as sps

    sizes = np.array([group.size for group in groups], dtype=float)
    means = np.array([float(group.mean()) for group in groups], dtype=float)
    variances = np.array([float(group.var(ddof=1)) for group in groups], dtype=float)
    if (sizes < 2).any() or (variances <= EPS).any():
        return None
    weights = sizes / variances
    total_weight = float(weights.sum())
    grand = float((weights * means).sum() / total_weight)
    count = len(groups)
    between = float((weights * (means - grand) ** 2).sum()) / (count - 1)
    terms = float((((1.0 - weights / total_weight) ** 2) / (sizes - 1.0)).sum())
    if terms <= EPS:
        return None
    statistic = between / (1.0 + 2.0 * (count - 2) / (count * count - 1) * terms)
    dfree = (count * count - 1) / (3.0 * terms)
    return (
        float(statistic),
        int(count - 1),
        float(dfree),
        float(sps.f.sf(statistic, count - 1, dfree)),
    )


def _dunn_posthoc(groups, keys, correction, alpha):
    from scipy import stats as sps

    pooled = np.concatenate(groups)
    ranks = sps.rankdata(pooled)
    total = pooled.size
    sizes = np.array([group.size for group in groups], dtype=float)
    rank_sums = []
    offset = 0
    for group in groups:
        rank_sums.append(float(ranks[offset : offset + group.size].sum()))
        offset += group.size
    rank_sums = np.array(rank_sums)
    ties = pd.Series(pooled).value_counts().to_numpy(dtype=float)
    tie_term = float(np.sum(ties**3 - ties)) / (12.0 * max(total - 1, 1))
    spread = total * (total + 1) / 12.0 - tie_term
    if spread <= EPS:
        raise MethodError("秩的离散度为零，无法做事后两两比较。")
    rows = []
    for left in range(len(keys)):
        for right in range(left + 1, len(keys)):
            z = (rank_sums[left] / sizes[left] - rank_sums[right] / sizes[right]) / math.sqrt(
                spread * (1.0 / sizes[left] + 1.0 / sizes[right])
            )
            raw = float(2 * sps.norm.sf(abs(z)))
            rows.append(
                {
                    "pair": f"{keys[left]} vs {keys[right]}",
                    "z_statistic": round(float(z), 6),
                    "p_raw": round(raw, 8),
                }
            )
    adjusted = _adjust([row["p_raw"] for row in rows], correction)
    for row, value in zip(rows, adjusted):
        row["p_value"] = round(float(value), 8)
        row["significant"] = bool(value < alpha)
    return rows


def _nemenyi_posthoc(matrix, keys, correction, alpha):
    from scipy import stats as sps

    treatments = matrix.shape[1]
    blocks = matrix.shape[0]
    if blocks < 1:
        raise MethodError("没有可用于事后比较的区组。")
    mean_ranks = sps.rankdata(matrix, axis=1).mean(axis=0)
    spread = math.sqrt(treatments * (treatments + 1) / (6.0 * blocks))
    if spread <= EPS:
        raise MethodError("平均秩没有离散度，无法做事后两两比较。")
    rows = []
    for left in range(treatments):
        for right in range(left + 1, treatments):
            difference = float(mean_ranks[left] - mean_ranks[right])
            z = difference / spread
            raw = float(2 * sps.norm.sf(abs(z)))
            rows.append(
                {
                    "pair": f"{keys[left]} vs {keys[right]}",
                    "rank_difference": round(difference, 6),
                    "z_statistic": round(float(z), 6),
                    "p_raw": round(raw, 8),
                }
            )
    adjusted = _adjust([row["p_raw"] for row in rows], correction)
    for row, value in zip(rows, adjusted):
        row["p_value"] = round(float(value), 8)
        row["significant"] = bool(value < alpha)
    return rows


def _mcnemar_posthoc(matrix, keys, correction, alpha):
    from scipy import stats as sps

    rows = []
    for left in range(matrix.shape[1]):
        for right in range(left + 1, matrix.shape[1]):
            first = matrix[:, left]
            second = matrix[:, right]
            first_only = int(((first == 1) & (second == 0)).sum())
            second_only = int(((first == 0) & (second == 1)).sum())
            discordant = first_only + second_only
            if discordant == 0:
                raw = 1.0
            else:
                raw = float(
                    sps.binomtest(
                        min(first_only, second_only), discordant, 0.5, alternative="two-sided"
                    ).pvalue
                )
            rows.append(
                {
                    "pair": f"{keys[left]} vs {keys[right]}",
                    "first_only": first_only,
                    "second_only": second_only,
                    "discordant": discordant,
                    "p_raw": round(raw, 8),
                }
            )
    adjusted = _adjust([row["p_raw"] for row in rows], correction)
    for row, value in zip(rows, adjusted):
        row["p_value"] = round(float(value), 8)
        row["significant"] = bool(value < alpha)
    return rows


@register("describe.frequency")
def frequency(context):
    table = context.table
    chosen = _pick_columns(table, context.want("columns"))
    order = context.text("sort", "count", ("count", "name", "count_asc"))
    floor = context.number("top_ratio", 0.0, 0.0, 1.0)
    max_levels = context.whole("max_levels", 0, 0, 200)
    cumulative = context.flag("cumulative", False)
    include_missing = context.flag("dropna", False)
    digits = context.whole("decimals", 6, 0, 8)
    want_chart = context.flag("chart", True)
    rows = []
    skipped = []
    sample_notes = []
    for name in chosen:
        series = table.raw[name]
        if pd.api.types.is_numeric_dtype(series) and series.nunique() > 12:
            skipped.append(name)
            continue
        observed = series if include_missing else series.dropna()
        counts = _category_labels(observed).value_counts()
        if order == "name":
            counts = counts.sort_index()
        elif order == "count_asc":
            counts = counts.sort_values(ascending=True)
        total = len(observed)
        sample_notes.append(
            f"{name}：输入 {len(series)} 条，有效观测 {int(series.notna().sum())} 条，"
            f"缺失 {int(series.isna().sum())} 条；占比分母为 {total}。"
        )
        running = 0.0
        shown = 0
        for level, count in counts.items():
            ratio = float(count) / total
            if ratio + 1e-12 < floor:
                continue
            if max_levels and shown >= max_levels:
                break
            shown += 1
            running += ratio
            row = {
                "column": name,
                "level": level,
                "count": int(count),
                "ratio": round(ratio, digits),
            }
            if cumulative:
                row["cumulative_ratio"] = round(running, digits)
            rows.append(row)
    if skipped:
        context.warn(f"列 {'、'.join(skipped)} 的取值超过 12 个，已跳过频数统计。")
    if not rows:
        if floor > 0.0:
            raise MethodError(f"按占比不低于 {floor:g} 过滤后没有剩余水平，请降低该阈值。")
        raise MethodError("所选列没有可统计的类别；高基数数值列请先分箱，空值可按需计入。")
    frame = pd.DataFrame(rows)
    order_labels = {"count": "按频数降序", "name": "按名称升序", "count_asc": "按频数升序"}
    notes = [
        "分类列可直接统计；取值超过 12 个的数值列自动跳过，连续变量请先分箱。",
        "空值作为独立类别计入分母。"
        if include_missing
        else "空值不计入类别及比例分母，原始文本类别照常保留。",
        "Top 或占比筛选后保持原分母，不对展示的类别重新归一化。",
        f"排序方式：{order_labels[order]}；只保留占比不低于 {floor:g} 的水平。",
        f"占比保留 {digits} 位小数；"
        + (
            "已按当前排序输出累计占比列（只累计展示出来的水平）。"
            if cumulative
            else "未输出累计占比列。"
        ),
    ]
    notes.extend(sample_notes)
    if max_levels:
        notes.append(f"每列最多显示 {max_levels} 个水平（按当前排序取前 {max_levels} 个）。")
    metrics = {
        "columns": int(frame["column"].nunique()),
        "levels": len(rows),
        "rows": table.n_rows,
        "selected_columns": len(chosen),
        "sort": order,
        "top_ratio": floor,
        "cumulative": cumulative,
        "decimals": digits,
    }
    if max_levels:
        metrics["max_levels"] = max_levels
    figures = []
    if want_chart:
        name = _frequency_figure(context, frame, cumulative)
        if name:
            figures.append(name)
    return registry.result(
        "describe.frequency",
        table,
        metrics=metrics,
        tables={"frequency": table_of(frame, limit=80)},
        figures=figures,
        notes=notes,
    )


@register("describe.stats")
def stats(context):
    from scipy import stats as sps

    table = context.table
    chosen = _pick_columns(table, context.want("columns"))
    mode = context.text("mode", "sample", ("sample", "population"))
    trim = context.number("trim", 0.0, 0.0, 0.45)
    group_by = context.text("group_by")
    quantiles = _parse_quantiles(context.text("quantiles"))
    normality = context.flag("normality", False)
    level = context.number("ci", 0.95, 0.5, 0.999)
    want_skew = context.flag("skew_kurtosis", True)
    want_cv = context.flag("cv", True)
    want_box = context.flag("boxplot", True)
    ddof = 1 if mode == "sample" else 0
    frame = table.raw[chosen].select_dtypes(include=[np.number])
    dropped = [name for name in chosen if name not in frame.columns]
    if dropped:
        context.warn(f"列 {'、'.join(dropped)} 不是数值列，已跳过描述性统计。")
    if frame.empty:
        raise MethodError("没有数值列可以做描述性统计。")
    rows = []
    non_normal = []
    for name in frame.columns:
        series = pd.to_numeric(frame[name], errors="coerce").dropna()
        if series.empty:
            continue
        values = series.to_numpy(dtype=float)
        spread = float(series.std(ddof=ddof)) if series.size > ddof else None
        center = float(series.mean())
        trimmed = _trimmed(values, trim)
        row = {
            "column": name,
            "count": int(series.size),
            "missing": int(frame[name].isna().sum()),
            "mean": round(center, 6),
            "trimmed_mean": None if trimmed is None else round(trimmed, 6),
            "std": None if spread is None else round(spread, 6),
            "min": round(float(series.min()), 6),
            "q25": round(float(series.quantile(0.25)), 6),
            "median": round(float(series.median()), 6),
            "q75": round(float(series.quantile(0.75)), 6),
            "max": round(float(series.max()), 6),
        }
        if want_skew:
            row["skew"] = round(float(series.skew()), 6) if series.size > 2 else None
            row["kurtosis"] = round(float(series.kurtosis()), 6) if series.size > 3 else None
        if want_cv:
            row["cv"] = None if spread is None or abs(center) <= EPS else round(spread / center, 6)
        for tag, point in quantiles:
            row[f"p{tag}"] = round(float(series.quantile(point)), 6)
        if level:
            if spread is not None and series.size > 1:
                error = float(series.std(ddof=1)) / math.sqrt(series.size)
                critical = float(sps.t.ppf(1.0 - (1.0 - level) / 2.0, series.size - 1))
                row["ci_low"] = round(center - critical * error, 6)
                row["ci_high"] = round(center + critical * error, 6)
            else:
                row["ci_low"] = None
                row["ci_high"] = None
        if normality:
            if series.size <= 2:
                row["normality_test"] = None
                row["normality_p"] = None
            elif series.size <= 5000:
                outcome = sps.shapiro(values)
                row["normality_test"] = "Shapiro-Wilk"
                row["normality_p"] = round(float(outcome.pvalue), 8)
            else:
                outcome = sps.normaltest(values)
                row["normality_test"] = "D'Agostino-Pearson"
                row["normality_p"] = round(float(outcome.pvalue), 8)
            if row["normality_p"] is not None and row["normality_p"] < 0.05:
                non_normal.append(name)
        rows.append(row)
    summary = pd.DataFrame(rows)
    metrics = {
        "columns": len(rows),
        "rows": table.n_rows,
        "numeric_columns": int(frame.shape[1]),
        "std_mode": mode,
        "trim": trim,
        "group_by": group_by,
        "normality": normality,
        "ci_level": level,
        "quantiles": [point for _, point in quantiles],
    }
    tables = {"describe": table_of(summary, limit=60)}
    if group_by:
        name = _group_name(table, group_by)
        keys = _category_labels(table.raw[name]).to_numpy()
        grouped = []
        for column in frame.columns:
            numeric = pd.to_numeric(table.raw[column], errors="coerce").to_numpy(dtype=float)
            buckets = _bucketize(keys, numeric)
            for key in sorted(buckets):
                group_values = buckets[key]
                spread = (
                    float(np.std(group_values, ddof=ddof)) if group_values.size > ddof else None
                )
                grouped.append(
                    {
                        "group": key,
                        "column": column,
                        "count": int(group_values.size),
                        "mean": round(float(group_values.mean()), 6),
                        "std": None if spread is None else round(spread, 6),
                        "median": round(float(np.median(group_values)), 6),
                        "min": round(float(group_values.min()), 6),
                        "max": round(float(group_values.max()), 6),
                    }
                )
        tables["by_group"] = table_of(pd.DataFrame(grouped), limit=80)
        metrics["group_column"] = name
        metrics["groups"] = len({row["group"] for row in grouped})
    metrics["non_normal_columns"] = len(non_normal)
    notes = []
    if want_skew:
        notes.append("偏度绝对值大于 1 提示分布明显右偏或左偏；峰度大于 0 表示比正态更尖。")
    if want_cv:
        notes.append("变异系数 CV 只在均值远离 0 时有意义。")
    notes.append(
        f"标准差口径：{'样本（n−1）' if mode == 'sample' else '总体（n）'}；截尾均值比例 {trim:g}。"
    )
    notes.append(
        f"均值置信区间按 {level:.1%} 的 t 区间计算，使用样本标准误，"
        "不随标准差展示口径改变；输出 ci_low 与 ci_high 两列。"
    )
    if quantiles:
        notes.append(
            "附加分位点：" + "、".join(f"{point:g}(列 p{tag})" for tag, point in quantiles) + "。"
        )
    if normality:
        if non_normal:
            notes.append("在 5% 水平下拒绝正态性的列：" + "、".join(non_normal[:8]) + "。")
            context.warn(f"有 {len(non_normal)} 列在 5% 水平下不服从正态分布。")
        else:
            notes.append("所有纳分析的数值列在 5% 水平下都没有拒绝正态性。")
    if group_by:
        notes.append(f"额外按 {group_by} 分组输出每组各列的统计量。")
    figures = []
    if want_box:
        name = _stats_boxplot(context, frame, level, metrics.get("group_column"))
        if name:
            figures.append(name)
    return registry.result(
        "describe.stats",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("describe.crosstab")
def crosstab(context):
    from scipy import stats as sps

    table = context.table
    percent = context.text("percent", "row", ("row", "column", "total", "none"))
    floor = context.number("min_count", 5.0, 0.0, 100.0)
    margins = context.flag("margins", True)
    with_test = context.flag("chi_square", False)
    digits = context.whole("decimals", 3, 0, 6)
    want_expected = context.flag("expected", False)
    want_heatmap = context.flag("heatmap", True)
    candidates = [name for name in table.raw.columns if table.raw[name].nunique(dropna=False) <= 20]
    if len(candidates) < 2:
        raise MethodError("列联表需要两个低基数列。")
    first = context.text("row")
    second = context.text("column")
    if first and first not in table.raw.columns:
        raise MethodError(f"行变量 {first} 不在数据里。")
    if second and second not in table.raw.columns:
        raise MethodError(f"列变量 {second} 不在数据里。")
    if not first or first not in candidates:
        first = candidates[0]
    if not second or second not in candidates or second == first:
        second = next(name for name in candidates if name != first)

    frame = pd.crosstab(table.raw[first], table.raw[second], margins=margins, margins_name="合计")
    counts = pd.crosstab(table.raw[first], table.raw[second])
    total = float(counts.to_numpy().sum())
    expected = np.outer(counts.sum(axis=1), counts.sum(axis=0)) / max(total, 1.0)
    below = int((expected < floor).sum())
    if below:
        context.warn(f"有 {below} 个格子的期望频数低于 {floor:g}，卡方近似可能不可靠。")
    tables = {"crosstab": _labeled_table(frame, limit=40)}
    if percent != "none":
        tables["percent"] = _labeled_table(_percent_frame(counts, percent, digits), limit=40)
    if want_expected:
        expected_frame = pd.DataFrame(
            np.round(expected, 3), index=counts.index, columns=counts.columns
        )
        tables["expected"] = _labeled_table(expected_frame, limit=40)
    percent_labels = {
        "row": "行百分比",
        "column": "列百分比",
        "total": "总计百分比",
        "none": "不输出百分比",
    }
    metrics = {
        "row_variable": first,
        "column_variable": second,
        "cells": int(expected.shape[0] * expected.shape[1]),
        "rows": table.n_rows,
        "percent": percent,
        "min_count": floor,
        "cells_below_min_count": below,
        "margins": margins,
        "percent_decimals": digits,
    }
    notes = [
        "“合计”行列是边际频数。",
        "要判断两个变量是否独立，请运行卡方检验。",
        f"百分比口径：{percent_labels[percent]}。",
        f"百分比保留 {digits} 位小数；"
        + ("已输出合计行列。" if margins else "已按设置去掉合计行列。"),
        f"输入 {table.n_rows} 条，列联表有效记录 {int(total)} 条；"
        f"排除变量缺失的 {table.n_rows - int(total)} 条。",
    ]
    if not margins:
        notes[0] = "已按设置去掉“合计”行列，只看单元格频数。"
    if with_test:
        statistic, pvalue, dfree, _ = sps.chi2_contingency(
            counts.to_numpy(), correction=bool(counts.shape == (2, 2))
        )
        cramers = (
            math.sqrt(float(statistic) / (total * (min(counts.shape) - 1)))
            if total and min(counts.shape) > 1
            else None
        )
        metrics["chi_square"] = round(float(statistic), 6)
        metrics["p_value"] = round(float(pvalue), 8)
        metrics["df"] = int(dfree)
        metrics["significant"] = bool(pvalue < 0.05)
        if cramers is not None:
            metrics["cramers_v"] = round(float(cramers), 6)
            metrics["effect_size_note"] = "小" if cramers < 0.1 else "中" if cramers < 0.3 else "大"
        notes.append(
            f"已附带卡方独立性检验：χ²={float(statistic):.4g}，p="
            f"{float(pvalue):.4g}，自由度 {int(dfree)}"
            + (f"，Cramér's V={float(cramers):.4g}。" if cramers is not None else "。")
        )
    if want_expected:
        notes.append("已输出每个格子的期望频数表（按行、列边际独立时的理论频数）。")
    figures = []
    if want_heatmap:
        name = _crosstab_heatmap(context, counts, first, second)
        if name:
            figures.append(name)
    return registry.result(
        "describe.crosstab",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("describe.aggregate")
def aggregate(context):
    table = context.table
    chosen = context.want("columns")
    stat = context.text("stat", "mean", STAT_KEYS)
    order = context.text("sort", "value", ("value", "value_asc", "group", "none"))
    with_count = context.flag("with_count", True)
    share = context.flag("share", False)
    quantiles = _parse_quantiles(context.text("quantiles"))
    digits = context.whole("decimals", 6, 0, 8)
    want_bar = context.flag("bar_chart", True)
    name = _group_name(table, context.text("by"))
    if chosen:
        fields = _pick_columns(table, chosen)
    elif table.target_name:
        fields = [table.target_name]
    else:
        raise MethodError("分类汇总需要目标列，或先选择被汇总的列。")
    for field in fields:
        if not pd.api.types.is_numeric_dtype(table.raw[field]) and stat != "count":
            raise MethodError(f"列 {field} 不是数值列，无法计算 {stat}；可改用 count。")
    keys = _category_labels(table.raw[name]).to_numpy()
    buckets = {}
    counts = {}
    for field in fields:
        numeric = pd.to_numeric(table.raw[field], errors="coerce").to_numpy(dtype=float)
        buckets[field] = _bucketize(keys, numeric)
        if stat == "count":
            counts[field] = table.raw[field].groupby(keys, sort=False).count()
    sizes = {}
    for key in keys:
        sizes[str(key)] = sizes.get(str(key), 0) + 1
    total_rows = max(len(keys), 1)
    rows = []
    for key in sizes:
        row = {"group": key}
        if share:
            row["share"] = round(sizes[key] / total_rows, digits)
        for field in fields:
            values = buckets[field].get(key, np.array([], dtype=float))
            count = int(counts[field].get(key, 0)) if stat == "count" else int(values.size)
            summary_value = count if stat == "count" else _aggregate(values, stat, digits)
            if len(fields) == 1:
                if with_count:
                    row["count"] = count
                row[stat] = summary_value
                for tag, point in quantiles:
                    row[f"p{tag}"] = _quantile(values, point, digits)
            else:
                if with_count:
                    row[f"{field}_count"] = count
                row[f"{field}_{stat}"] = summary_value
                for tag, point in quantiles:
                    row[f"{field}_p{tag}"] = _quantile(values, point, digits)
        rows.append(row)
    frame = pd.DataFrame(rows)
    value_column = stat if len(fields) == 1 else f"{fields[0]}_{stat}"
    if order == "group":
        frame = frame.sort_values("group", kind="stable").reset_index(drop=True)
    elif order == "value":
        frame = frame.sort_values(
            value_column, ascending=False, na_position="last", kind="stable"
        ).reset_index(drop=True)
    elif order == "value_asc":
        frame = frame.sort_values(
            value_column, ascending=True, na_position="last", kind="stable"
        ).reset_index(drop=True)
    overall = (
        np.concatenate([buckets[fields[0]][key] for key in buckets[fields[0]]])
        if buckets[fields[0]]
        else np.array([], dtype=float)
    )
    ranked = sorted(sizes.items(), key=lambda item: -item[1])
    metrics = {
        "group_column": name,
        "groups": len(rows),
        "overall_mean": round(float(overall.mean()), 6) if overall.size else None,
        "largest_group": str(ranked[0][0]),
        "largest_count": int(ranked[0][1]),
        "smallest_group": str(ranked[-1][0]),
        "smallest_count": int(ranked[-1][1]),
        "stat": stat,
        "sort": order,
        "aggregated_columns": fields,
        "with_count": with_count,
        "share": share,
        "decimals": digits,
        "quantiles": [point for _, point in quantiles],
    }
    notes = [
        f"按 {name} 分组汇总 {'、'.join(fields)} 的 {stat}。",
        "组间均值只能描述差异，是否显著需要做检验。",
        f"结果保留 {digits} 位小数；"
        + ("已输出每组样本数。" if with_count else "已按设置去掉每组样本数。"),
    ]
    if share:
        notes.append("share 列是各组行数占全部行数的比例（分母包含响应缺失的行）。")
    if quantiles:
        notes.append("附加分位点：" + "、".join(f"{point:g}" for _, point in quantiles) + "。")
    figures = []
    if want_bar:
        count_column = "count" if len(fields) == 1 else f"{fields[0]}_count"
        name = _aggregate_bar(context, frame, value_column, count_column, stat)
        if name:
            figures.append(name)
    return registry.result(
        "describe.aggregate",
        table,
        metrics=metrics,
        tables={"groups": table_of(frame, limit=40)},
        figures=figures,
        notes=notes,
    )


@register("describe.explore")
def explore(context):
    table = context.table
    chosen = _pick_columns(table, context.want("columns"))
    warn_ratio = context.number("missing_warn", 0.5, 0.0, 1.0)
    unique_limit = context.whole("unique_limit", 20, 2, 200)
    sample_rows = context.whole("sample_rows", 5, 1, 50)
    want_corr = context.flag("correlation", False)
    want_outliers = context.flag("outliers", False)
    corr_method = context.text("correlation_method", "pearson", ("pearson", "spearman", "kendall"))
    outlier_factor = context.number("outlier_iqr", 1.5, 0.5, 5.0)
    want_missing_chart = context.flag("missing_chart", True)
    frame = table.raw[chosen]
    rows = []
    for name in chosen:
        series = frame[name]
        numeric = pd.api.types.is_numeric_dtype(series)
        unique = int(series.nunique(dropna=True))
        examples = [str(item) for item in series.dropna().unique()[:sample_rows]]
        rows.append(
            {
                "column": name,
                "dtype": str(series.dtype),
                "role": (
                    "目标"
                    if name == table.target_name
                    else "时间"
                    if name == table.time_name
                    else "分组"
                    if name == table.group_name
                    else "特征"
                ),
                "missing": int(series.isna().sum()),
                "missing_ratio": round(float(series.isna().mean()), 6),
                "unique": unique,
                "high_cardinality": bool(unique > unique_limit),
                "is_numeric": bool(numeric),
                "sample": str(series.dropna().iloc[0])[:40] if series.notna().any() else "",
                "examples": "、".join(examples)[:200],
            }
        )
    overview = pd.DataFrame(rows)
    constant = [row["column"] for row in rows if row["unique"] <= 1]
    high_missing = [row["column"] for row in rows if row["missing_ratio"] > warn_ratio]
    high_unique = [row["column"] for row in rows if row["high_cardinality"]]
    if high_missing:
        context.warn(f"缺失占比超过 {warn_ratio:g} 的列：" + "、".join(high_missing))
    numeric_frame = frame.select_dtypes(include=[np.number])
    metrics = {
        "columns": int(frame.shape[1]),
        "rows": int(frame.shape[0]),
        "numeric_columns": int(numeric_frame.shape[1]),
        "constant_columns": len(constant),
        "high_missing_columns": len(high_missing),
        "high_cardinality_columns": len(high_unique),
        "missing_warn": warn_ratio,
        "unique_limit": unique_limit,
        "sample_rows": sample_rows,
        "correlation": want_corr,
        "outliers": want_outliers,
        "inferred_task": table.task,
    }
    tables = {"columns": table_of(overview, limit=80)}
    notes = (
        (["常量列（只有 1 个取值）：" + "、".join(constant[:8])] if constant else [])
        + (
            ["缺失超过 " + f"{warn_ratio:.0%}" + " 的列：" + "、".join(high_missing[:8])]
            if high_missing
            else []
        )
        + (
            ["唯一值超过 " + str(unique_limit) + " 的高基数列：" + "、".join(high_unique[:8])]
            if high_unique
            else []
        )
    )
    if want_corr:
        if numeric_frame.shape[1] >= 2:
            matrix = numeric_frame.corr(method=corr_method).round(3)
            matrix.index.name = "column"
            tables["correlation"] = table_of(matrix.reset_index(), limit=40)
            values = np.array(matrix.to_numpy(dtype=float), copy=True)
            np.fill_diagonal(values, np.nan)
            if np.isfinite(values).any():
                position = int(np.nanargmax(np.abs(values)))
                row_index, column_index = np.unravel_index(position, values.shape)
                metrics["max_abs_correlation"] = round(
                    float(abs(values[row_index, column_index])), 6
                )
                notes.append(
                    f"相关最强的数值列组合：{matrix.index[row_index]} 与 "
                    f"{matrix.columns[column_index]}（r="
                    f"{values[row_index, column_index]:.3f}）。"
                )
            if corr_method != "pearson":
                corr_labels = {"spearman": "Spearman 秩相关", "kendall": "Kendall τ 相关"}
                metrics["correlation_method"] = corr_method
                notes.append(f"相关矩阵按{corr_labels[corr_method]}计算。")
        else:
            context.warn("数值列少于 2 个，无法输出相关矩阵。")
            notes.append("数值列少于 2 个，无法输出相关矩阵。")
    if want_outliers:
        outlier_rows = []
        for name in numeric_frame.columns:
            values = pd.to_numeric(frame[name], errors="coerce").dropna().to_numpy(dtype=float)
            if values.size < 4:
                continue
            low, high = np.quantile(values, [0.25, 0.75])
            span = float(high - low)
            lower = float(low - outlier_factor * span)
            upper = float(high + outlier_factor * span)
            count = int(((values < lower) | (values > upper)).sum())
            outlier_rows.append(
                {
                    "column": name,
                    "q1": round(float(low), 6),
                    "q3": round(float(high), 6),
                    "lower_bound": round(lower, 6),
                    "upper_bound": round(upper, 6),
                    "outliers": count,
                    "outlier_ratio": round(count / values.size, 6),
                }
            )
        outlier_frame = pd.DataFrame(outlier_rows)
        tables["outliers"] = table_of(outlier_frame, limit=40)
        flagged = [row["column"] for row in outlier_rows if row["outliers"]]
        metrics["outlier_columns"] = len(flagged)
        metrics["outlier_total"] = int(sum(row["outliers"] for row in outlier_rows))
        metrics["outlier_iqr"] = outlier_factor
        notes.append(
            f"按 {outlier_factor:g}×IQR 规则判定疑似异常值"
            + ("，命中列：" + "、".join(flagged[:8]) + "。" if flagged else "，没有列命中。")
        )
    notes.append(f"每列最多列出 {sample_rows} 个唯一值示例（examples 列）。")
    notes.append(f"推断的任务类型：{table.task}。")
    figures = []
    if want_missing_chart:
        name = _explore_missing_chart(context, overview)
        if name:
            figures.append(name)
    return registry.result(
        "describe.explore",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("describe.power")
def power(context):
    from statsmodels.stats.power import NormalIndPower, TTestIndPower
    from statsmodels.stats.proportion import proportion_effectsize

    table = context.table
    kind = context.text("kind", "t", ("t", "proportion", "anova"))
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    power_target = context.number("power", 0.8, 0.01, 0.999)
    effect = context.number("effect", 0.5, 1e-6, 20.0)
    ratio = context.number("ratio", 1.0, 0.05, 20.0)
    alternative = context.text("alternative", "two-sided", ALTERNATIVES)
    dropout = context.number("dropout", 0.0, 0.0, 0.9)
    curve_max = context.whole("curve_max", 500, 100, 5000)
    curve_min = context.whole("curve_min", 10, 2, 5000)
    want_curve = context.flag("power_curve", True)
    groups = context.whole("groups", 2, 2, 10)
    power_alternative = POWER_ALTERNATIVES[alternative]

    if kind == "proportion":
        baseline = context.number("baseline", 0.2, 1e-6, 1 - 1e-6)
        target = context.number("target", min(baseline + 0.1, 0.999), 1e-6, 1 - 1e-6)
        effect = float(proportion_effectsize(target, baseline))
        if (effect > 0 and alternative == "less") or (effect < 0 and alternative == "greater"):
            context.warn("目标比例与基线比例的大小关系与所选单侧方向相反，已按效应量绝对值计算。")
        analysis = NormalIndPower()
    else:
        analysis = TTestIndPower()
        if kind == "anova" and groups > 2:
            effect = effect / math.sqrt(groups)
    effect = -abs(effect) if alternative == "less" else abs(effect)

    needed = analysis.solve_power(
        effect_size=effect,
        alpha=alpha,
        power=power_target,
        ratio=ratio,
        alternative=power_alternative,
    )
    clamped = False
    if not math.isfinite(float(needed)):
        context.warn("按给定效应量与目标功效，所需样本量低于求解器下限，已按每组 2 例报告。")
        needed = 2.0
        clamped = True
    per_group = int(math.ceil(needed))
    achieved = analysis.solve_power(
        effect_size=effect,
        alpha=alpha,
        nobs1=max(per_group, 2),
        ratio=ratio,
        alternative=power_alternative,
    )
    second_group = int(math.ceil(per_group * ratio))
    total = per_group + second_group
    if dropout > 0:
        adjusted_total = int(math.ceil(total / (1.0 - dropout)))
        adjusted_per_group = int(math.ceil(per_group / (1.0 - dropout)))
    else:
        adjusted_total = total
        adjusted_per_group = per_group

    curve_low = min(curve_min, curve_max)
    sizes = [size for size in (10, 20, 30, 50, 100, 200, 500) if curve_low <= size <= curve_max]
    if not sizes:
        sizes.append(curve_low)
    if curve_max not in sizes:
        sizes.append(curve_max)
    rows = []
    for size in sizes:
        value = analysis.solve_power(
            effect_size=effect, alpha=alpha, nobs1=size, ratio=ratio, alternative=power_alternative
        )
        rows.append(
            {
                "per_group": size,
                "total": size + int(math.ceil(size * ratio)),
                "power": round(float(value), 6),
            }
        )
    curve = pd.DataFrame(rows)
    alternative_labels = {"two-sided": "双侧", "greater": "单侧（大于）", "less": "单侧（小于）"}
    notes = [
        "效应量越小、要求的功效越高，需要的样本量越大。",
        f"两组样本量配比（第二组/第一组）为 {ratio:g}，"
        f"备择假设为{alternative_labels[alternative]}。",
        f"已按脱落率 {dropout:.0%} 折算所需总样本量 {adjusted_total}。",
    ]
    if kind == "anova":
        notes.append(f"方差分析按 {groups} 组把预期效应量换算成 Cohen's f 后再求样本量。")
    if kind == "proportion":
        notes.append("比例检验的效应量按 Cohen's h 计算，基线比例与目标比例共同决定 h。")
    if curve_min > 10:
        notes.append(f"功效曲线从每组 {curve_low} 个样本起算。")
    if clamped:
        notes.append("所需每组样本量低于 2 例时按每组 2 例报告。")
    figures = []
    if want_curve:
        name = _power_curve(context, curve, per_group, power_target)
        if name:
            figures.append(name)
    return registry.result(
        "describe.power",
        table,
        metrics={
            "kind": kind,
            "alpha": alpha,
            "target_power": power_target,
            "effect_size": round(float(effect), 6),
            "required_per_group": per_group,
            "required_second_group": second_group,
            "required_total": total,
            "required_per_group_with_dropout": adjusted_per_group,
            "required_total_with_dropout": adjusted_total,
            "achieved_power": round(float(achieved), 6),
            "ratio": ratio,
            "alternative": alternative,
            "dropout": dropout,
            "curve_max": curve_max,
        },
        tables={"power_by_sample": table_of(curve)},
        figures=figures,
        notes=notes,
    )


@register("test.ttest")
def ttest(context):
    from scipy import stats as sps

    table = context.table
    kind = context.text("kind", "independent", ("one_sample", "independent", "paired"))
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    popmean = context.number("popmean", 0.0)
    alternative = context.text("alternative", "two-sided", ALTERNATIVES)
    variance = context.text("variance", "auto", ("auto", "equal", "unequal"))
    trim = context.number("trim", 0.0, 0.0, 0.45)
    level = context.number("ci", 0.95, 0.5, 0.999)
    want_effect_ci = context.flag("effect_ci", False)
    effect_kind = context.text("effect_size", "cohen", ("cohen", "hedges"))
    want_normality = context.flag("normality_check", False)
    want_box = context.flag("boxplot", True)
    if trim > 0 and kind != "independent":
        raise MethodError("截尾比例只在独立样本 T 检验（Yuen 检验）中生效。")

    equal_var = None
    variance_p = None
    difference = None
    error = None
    trimmed = False
    first = None
    second = None
    keys = []
    if kind == "one_sample":
        values = table.numeric_target()
        if values is None:
            raise MethodError("单样本 T 检验需要数值目标列。")
        values = values[np.isfinite(values)]
        if values.size < 2:
            raise MethodError("单样本 T 检验至少需要 2 个有效样本。")
        first = values
        int(values.size)
        statistic, pvalue = sps.ttest_1samp(values, popmean, alternative=alternative)
        detail = {
            "group": "样本",
            "n": int(values.size),
            "mean": round(float(values.mean()), 6),
            "std": round(float(values.std(ddof=1)), 6),
            "reference": popmean,
        }
        dfree = values.size - 1
        rows = pd.DataFrame([detail])
        difference = float(values.mean()) - popmean
        error = float(values.std(ddof=1)) / math.sqrt(values.size) if values.size > 1 else None
    else:
        grouping = _paired_groups if kind == "paired" else _groups
        name, buckets = grouping(context, context.text("by"))
        keys = sorted(buckets)
        if kind == "paired":
            if len(keys) != 2:
                raise MethodError("配对 T 检验需要恰好两组。")
            first, second = buckets[keys[0]], buckets[keys[1]]
            size = first.size
            if size < 3:
                raise MethodError("配对样本太少。")
            int(size)
            statistic, pvalue = sps.ttest_rel(first[:size], second[:size], alternative=alternative)
            difference_values = first[:size] - second[:size]
            dfree = size - 1
            detail = {
                "group": f"{keys[0]} − {keys[1]}",
                "n": int(size),
                "mean": round(float(difference_values.mean()), 6),
                "std": round(float(difference_values.std(ddof=1)), 6),
            }
            rows = pd.DataFrame([detail])
            difference = float(difference_values.mean())
            error = float(difference_values.std(ddof=1)) / math.sqrt(size)
        else:
            if len(keys) != 2:
                raise MethodError(
                    f"独立样本 T 检验需要两组，当前有 {len(keys)} 组：{'、'.join(keys)}"
                )
            first, second = buckets[keys[0]], buckets[keys[1]]
            if first.size < 2 or second.size < 2:
                raise MethodError("每组至少需要 2 个样本。")
            int(first.size + second.size)
            if variance == "equal":
                equal_var = True
            elif variance == "unequal":
                equal_var = False
            else:
                variance_p = float(sps.levene(first, second, center="mean").pvalue)
                if not math.isfinite(variance_p):
                    variance_p = None
                    context.warn("Levene 方差检验无法计算，改用 Welch 校正；请检查各组变异。")
                equal_var = bool(variance_p is not None and variance_p >= alpha)
            if equal_var:
                pooled = (
                    (first.size - 1) * first.var(ddof=1) + (second.size - 1) * second.var(ddof=1)
                ) / max(first.size + second.size - 2, 1)
                error = math.sqrt(pooled * (1.0 / first.size + 1.0 / second.size))
            else:
                error = math.sqrt(first.var(ddof=1) / first.size + second.var(ddof=1) / second.size)
            if trim > 0:
                outcome = sps.ttest_ind(
                    first, second, trim=trim, equal_var=equal_var, alternative=alternative
                )
                statistic = float(outcome.statistic)
                pvalue = float(outcome.pvalue)
                dfree = float(outcome.df)
                first_center = _trimmed(first, trim)
                second_center = _trimmed(second, trim)
                if first_center is None or second_center is None:
                    raise MethodError("截尾比例过大，截尾后没有剩余样本。")
                difference = float(first_center - second_center)
                trimmed = True
            else:
                outcome = sps.ttest_ind(first, second, equal_var=equal_var, alternative=alternative)
                statistic, pvalue = outcome.statistic, outcome.pvalue
                dfree = float(outcome.df)
                difference = float(first.mean() - second.mean())
            rows = pd.DataFrame(
                [
                    {
                        "group": keys[0],
                        "n": int(first.size),
                        "mean": round(float(first.mean()), 6),
                        "std": round(float(first.std(ddof=1)), 6),
                    },
                    {
                        "group": keys[1],
                        "n": int(second.size),
                        "mean": round(float(second.mean()), 6),
                        "std": round(float(second.std(ddof=1)), 6),
                    },
                ]
            )

    statistic = float(statistic)
    pvalue = float(pvalue)
    dfree = float(dfree)
    if not all(math.isfinite(value) for value in (statistic, pvalue, dfree)) or dfree <= 0:
        raise MethodError("样本不足或有效方差为 0，无法计算有限的 T 检验结果，请检查数据与分组。")
    if error is not None and error > 0 and abs(statistic) > EPS:
        error = abs(float(difference) / statistic)
    if difference is not None and error is not None and error > 0:
        critical = float(sps.t.ppf(1.0 - (1.0 - level) / 2.0, dfree))
        ci_low = float(difference) - critical * error
        ci_high = float(difference) + critical * error
    else:
        ci_low = None
        ci_high = None
    if kind == "independent":
        effect_df = first.size + second.size - 2
        effect_sd = math.sqrt(
            ((first.size - 1) * first.var(ddof=1) + (second.size - 1) * second.var(ddof=1))
            / effect_df
        )
        effect_delta = float(first.mean() - second.mean())
    else:
        effect_values = first if kind == "one_sample" else difference_values
        effect_df = effect_values.size - 1
        effect_sd = float(effect_values.std(ddof=1))
        effect_delta = float(difference)
    effect = effect_delta / effect_sd if effect_sd > 0 else None
    effect_standardizer = error / effect_sd if error is not None and effect_sd > 0 else None
    effect_scale = 1.0
    effect_name = "cohens_d"
    effect_labels = {"cohens_d": "Cohen's d", "hedges_g": "Hedges' g"}
    if effect_kind == "hedges":
        effect_name = "hedges_g"
        if effect_df > 1:
            effect_scale = 1.0 - 3.0 / (4.0 * effect_df - 1.0)
        else:
            effect = None
            context.warn("有效自由度不足，无法估计 Hedges' g。")
        if effect is not None:
            effect = effect * effect_scale
    metrics = {
        "kind": kind,
        "statistic": round(statistic, 6),
        "p_value": round(pvalue, 8),
        "degrees_of_freedom": round(dfree, 6),
        "alpha": alpha,
        "alternative": alternative,
        "significant": bool(pvalue < alpha),
        "ci_level": level,
        "mean_difference": _round(difference, 6),
        "ci_low": _round(ci_low, 6),
        "ci_high": _round(ci_high, 6),
    }
    if trimmed:
        metrics["trim"] = trim
        metrics["degrees_of_freedom_exact"] = round(dfree, 6)
    if equal_var is not None:
        metrics["variance"] = variance
        metrics["equal_var"] = bool(equal_var)
        if variance_p is not None:
            metrics["variance_test_p"] = round(variance_p, 8)
    if effect is not None and math.isfinite(effect):
        metrics[effect_name] = round(float(effect), 6)
        metrics["effect_size_note"] = (
            "小"
            if abs(effect) < 0.2
            else "中"
            if abs(effect) < 0.5
            else "大"
            if abs(effect) < 0.8
            else "很大"
        )
    if want_effect_ci:
        if (
            not trimmed
            and effect is not None
            and math.isfinite(effect)
            and effect_standardizer is not None
        ):
            low, high = _effect_bounds(statistic, dfree, level, effect_standardizer)
            metrics[f"{effect_name}_ci_low"] = round(float(low) * effect_scale, 6)
            metrics[f"{effect_name}_ci_high"] = round(float(high) * effect_scale, 6)
        else:
            metrics[f"{effect_name}_ci_low"] = None
            metrics[f"{effect_name}_ci_high"] = None
    notes = []
    if kind == "independent":
        if trimmed:
            notes.append(
                f"按截尾比例 {trim:g} 做 Yuen 截尾检验，"
                "使用截尾均值与 Winsorized 方差，自由度是校正后的值。"
            )
            notes.append(
                "Cohen's d / Hedges' g 另按原始样本均值差与合并标准差计算，"
                "不是截尾均值的标准化效应量；不把截尾统计量套入原始效应量置信区间。"
            )
        elif variance == "equal":
            notes.append("按参数要求假设两组方差相等，使用合并方差 t 检验。")
        elif variance == "unequal":
            notes.append("按参数要求使用 Welch 校正（不假设方差相等）。")
        else:
            notes.append(
                f"自动判定方差：Levene 检验 p="
                f"{'—' if variance_p is None else format(variance_p, '.4g')}，"
                f"采用{'等方差' if equal_var else 'Welch 校正'}。"
            )
    notes.append(f"备择假设为 {alternative}。")
    if ci_low is None:
        notes.append(f"均值差的 {level:.1%} 置信区间无法计算（有效样本不足）。")
    else:
        notes.append(f"均值差的 {level:.1%} 置信区间：[{ci_low:.6g}, {ci_high:.6g}]。")
    if want_effect_ci and f"{effect_name}_ci_low" in metrics:
        if trimmed:
            notes.append("截尾检验未提供原始样本效应量的非中心 t 置信区间。")
        elif metrics[f"{effect_name}_ci_low"] is None:
            notes.append(
                f"{effect_labels[effect_name]} 无法计算（有效样本量或方差不足），"
                "因此它的置信区间不可用。"
            )
        else:
            notes.append(
                f"{effect_labels[effect_name]} 的 {level:.1%} 置信区间"
                "按非中心 t 分布计算；Welch 分支的标准化换算是近似区间。"
            )
    if effect_kind == "hedges":
        notes.append(f"Hedges' g 由 Cohen's d 乘小样本校正因子 {effect_scale:.6g} 得到。")
    notes.append("p 值小于显著性水平只能说明差异难以用随机波动解释，不代表效应很大。")
    if want_normality:
        samples = (
            [("样本", first)] if kind == "one_sample" else [(keys[0], first), (keys[1], second)]
        )
        items = []
        for label, block in samples:
            values = np.asarray(block, dtype=float)
            values = values[np.isfinite(values)]
            if values.size <= 2:
                items.append({"group": label, "n": int(values.size), "test": None, "p_value": None})
            elif values.size <= 5000:
                items.append(
                    {
                        "group": label,
                        "n": int(values.size),
                        "test": "Shapiro-Wilk",
                        "p_value": round(float(sps.shapiro(values).pvalue), 8),
                    }
                )
            else:
                items.append(
                    {
                        "group": label,
                        "n": int(values.size),
                        "test": "D'Agostino-Pearson",
                        "p_value": round(float(sps.normaltest(values).pvalue), 8),
                    }
                )
        tables = {
            "groups": table_of(rows, limit=30),
            "normality": table_of(pd.DataFrame(items), limit=20),
        }
        notes.append("已输出各组正态性检验；p 小于 0.05 提示该组分布偏离正态。")
    else:
        tables = {"groups": table_of(rows, limit=30)}
    figures = []
    if want_box:
        name = _ttest_figure(
            context, kind, first, second, keys, level, popmean, difference, ci_low, ci_high
        )
        if name:
            figures.append(name)
    return registry.result(
        "test.ttest",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("test.anova")
def anova(context):
    from scipy import stats as sps

    table = context.table
    name, buckets = _groups(context, context.text("by"))
    keys = sorted(buckets)
    if len(keys) < 2:
        raise MethodError("方差分析至少需要两组。")
    small = [key for key in keys if buckets[key].size < 3]
    if small:
        raise MethodError(f"以下组样本不足 3 个：{'、'.join(small)}")
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    covariate = context.text("covariate")
    correction = context.text("correction", "bonferroni", ("none", "bonferroni", "sidak", "holm"))
    threshold = context.number("effect_size", 0.0, 0.0, 1.0)
    welch = context.flag("welch", False)
    variance_test = context.flag("variance_test", False)
    level = context.number("ci", 0.95, 0.5, 0.999)
    posthoc_test = context.text("posthoc_test", "mannwhitney", ("mannwhitney", "tukey"))
    effect_kind = context.text("effect_kind", "eta_squared", ("eta_squared", "omega_squared"))
    want_box = context.flag("boxplot", True)
    if welch and covariate:
        raise MethodError("Welch 方差分析不支持协变量，请改用普通方差分析或去掉协变量。")

    slope = None
    slope_p = None
    welch_df = None
    if covariate:
        if covariate not in table.raw.columns:
            raise MethodError(f"协变量 {covariate} 不在数据里。")
        if not pd.api.types.is_numeric_dtype(table.raw[covariate]):
            raise MethodError(f"协变量 {covariate} 不是数值列。")
        response = table.numeric_target()
        extra = pd.to_numeric(table.raw[covariate], errors="coerce").to_numpy(dtype=float)
        labels = _category_labels(table.raw[name]).to_numpy()
        aligned = {key: ([], []) for key in keys}
        for key, value, cov in zip(labels, response, extra):
            label = str(key)
            if label not in aligned or not np.isfinite(float(value)) or not np.isfinite(cov):
                continue
            aligned[label][0].append(float(value))
            aligned[label][1].append(float(cov))
        aligned = {
            key: (np.array(pair[0], dtype=float), np.array(pair[1], dtype=float))
            for key, pair in aligned.items()
            if len(pair[0]) >= 3
        }
        if len(aligned) < 2:
            raise MethodError("协方差分析至少需要两组、每组 3 个以上完整样本。")
        keys = sorted(aligned)
        groups = [aligned[key][0] for key in keys]
        y = np.concatenate(groups)
        x = np.concatenate([aligned[key][1] for key in keys])
        group_labels = np.concatenate(
            [np.full(aligned[key][0].size, key, dtype=object) for key in keys]
        )
        dummies = pd.get_dummies(pd.Series(group_labels), drop_first=True).to_numpy(dtype=float)
        design = np.column_stack([dummies, x, np.ones(y.size)])
        reduced = np.column_stack([x, np.ones(y.size)])
        beta = np.linalg.lstsq(design, y, rcond=None)[0]
        residual = y - design @ beta
        rss_full = float(residual @ residual)
        beta_reduced = np.linalg.lstsq(reduced, y, rcond=None)[0]
        residual_reduced = y - reduced @ beta_reduced
        rss_reduced = float(residual_reduced @ residual_reduced)
        dfree_between = int(dummies.shape[1])
        dfree_within = int(y.size - design.shape[1])
        if dfree_within <= 0:
            raise MethodError("协方差分析的样本量不足以估计组间效应。")
        between = max(rss_reduced - rss_full, 0.0)
        within = rss_full
        if rss_full <= EPS:
            statistic, pvalue = 0.0, 1.0
        else:
            statistic = float(max(between / dfree_between / (rss_full / dfree_within), 0.0))
            pvalue = float(sps.f.sf(statistic, dfree_between, dfree_within))
        slope = float(beta[dfree_between])
        covariance = np.linalg.pinv(design.T @ design)
        standard_error = math.sqrt(
            max(float(rss_full / dfree_within * covariance[dfree_between, dfree_between]), 0.0)
        )
        if standard_error > EPS:
            slope_p = float(2 * sps.t.sf(abs(slope / standard_error), dfree_within))
        adjusted = y - slope * (x - float(x.mean()))
        rows = []
        for key in keys:
            values = aligned[key][0]
            mask = group_labels == key
            rows.append(
                {
                    "group": key,
                    "n": int(values.size),
                    "mean": round(float(values.mean()), 6),
                    "adjusted_mean": round(float(adjusted[mask].mean()), 6),
                    "std": round(float(values.std(ddof=1)), 6) if values.size > 1 else None,
                    "min": round(float(values.min()), 6),
                    "max": round(float(values.max()), 6),
                }
            )
    else:
        groups = [buckets[key] for key in keys]
        statistic, pvalue = sps.f_oneway(*groups)
        grand = np.concatenate(groups)
        between = sum(group.size * (group.mean() - grand.mean()) ** 2 for group in groups)
        within = sum(((group - group.mean()) ** 2).sum() for group in groups)
        dfree_between = len(groups) - 1
        dfree_within = grand.size - len(groups)
        rows = []
        for key in keys:
            values = buckets[key]
            rows.append(
                {
                    "group": key,
                    "n": int(values.size),
                    "mean": round(float(values.mean()), 6),
                    "std": round(float(values.std(ddof=1)), 6) if values.size > 1 else None,
                    "min": round(float(values.min()), 6),
                    "max": round(float(values.max()), 6),
                }
            )
        if welch:
            outcome = _welch_anova(groups)
            if outcome is None:
                raise MethodError("Welch 方差分析需要每组至少 2 个样本，且组内方差大于 0。")
            statistic = outcome[0]
            pvalue = outcome[3]
            dfree_between = outcome[1]
            dfree_within = outcome[2]
            welch_df = outcome[2]

    for row, values in zip(rows, groups):
        values = np.asarray(values, dtype=float)
        if values.size > 1:
            error = float(values.std(ddof=1)) / math.sqrt(values.size)
            critical = float(sps.t.ppf(1.0 - (1.0 - level) / 2.0, values.size - 1))
            row["ci_low"] = round(float(values.mean()) - critical * error, 6)
            row["ci_high"] = round(float(values.mean()) + critical * error, 6)
        else:
            row["ci_low"] = None
            row["ci_high"] = None

    if variance_test:
        outcome = sps.levene(*groups, center="mean")
        levene_p = float(outcome.pvalue)
        if levene_p < alpha:
            context.warn(
                f"Levene 检验 p={levene_p:.4g} 小于 {alpha:g}，"
                "各组方差不齐，建议改用 Welch 方差分析。"
            )

    eta = between / (between + within) if (between + within) > EPS else None
    omega = None
    if (between + within) > EPS and dfree_within > 0:
        ms_within = within / dfree_within
        omega = (between - dfree_between * ms_within) / (between + within + ms_within)
    frames = pd.DataFrame(rows)

    metrics = {
        "group_column": name,
        "groups": len(groups),
        "f_statistic": round(float(statistic), 6),
        "p_value": round(float(pvalue), 8),
        "df_between": int(dfree_between),
        "df_within": int(round(dfree_within)),
        "alpha": alpha,
        "significant": bool(pvalue < alpha),
        "sum_squares_between": round(float(between), 6),
        "sum_squares_within": round(float(within), 6),
        "correction": correction,
        "effect_size_threshold": threshold,
        "welch": welch,
        "variance_test": variance_test,
        "ci_level": level,
    }
    if welch_df is not None:
        metrics["welch_df_within"] = round(float(welch_df), 6)
    if variance_test:
        metrics["levene_statistic"] = round(float(outcome.statistic), 6)
        metrics["levene_p_value"] = round(levene_p, 8)
    if covariate:
        metrics["covariate"] = covariate
        metrics["covariate_slope"] = round(slope, 6)
        if slope_p is not None:
            metrics["covariate_p_value"] = round(slope_p, 8)
    if effect_kind == "omega_squared" and omega is not None:
        metrics["omega_squared"] = round(float(omega), 6)
        metrics["effect_size_note"] = "小" if omega < 0.06 else "中" if omega < 0.14 else "大"
    elif eta is not None:
        metrics["eta_squared"] = round(float(eta), 6)
        metrics["effect_size_note"] = "小" if eta < 0.06 else "中" if eta < 0.14 else "大"

    posthoc_rows = []
    total_pairs = len(groups) * (len(groups) - 1) // 2
    if len(groups) > 2 and pvalue < alpha:
        pairs = []
        if posthoc_test == "tukey":
            from statsmodels.stats.multicomp import pairwise_tukeyhsd

            flat_labels = np.concatenate(
                [np.full(group.size, str(key), dtype=object) for group, key in zip(groups, keys)]
            )
            flat_values = np.concatenate(groups)
            outcome_tukey = pairwise_tukeyhsd(flat_values, flat_labels)
            summary = outcome_tukey.summary()
            headings = [str(item) for item in summary.data[0]]
            position_pair = headings.index("group1")
            position_other = headings.index("group2")
            position_adjusted = headings.index("p-adj")
            for record in summary.data[1:]:
                pairs.append(
                    {
                        "pair": f"{record[position_pair]} vs {record[position_other]}",
                        "p_raw": float(record[position_adjusted]),
                        "p_value": float(record[position_adjusted]),
                        "cohens_d": _cohens_d(
                            groups[keys.index(str(record[position_pair]))],
                            groups[keys.index(str(record[position_other]))],
                        ),
                    }
                )
            for pair in pairs:
                effect = pair["cohens_d"]
                if effect is not None and abs(effect) < threshold - 1e-12:
                    continue
                posthoc_rows.append(
                    {
                        "pair": pair["pair"],
                        "p_value": round(float(pair["p_value"]), 8),
                        "p_raw": round(float(pair["p_raw"]), 8),
                        "cohens_d": None if effect is None else round(float(effect), 6),
                        "significant": bool(pair["p_value"] < alpha),
                        "significant_bonferroni": bool(pair["p_value"] < alpha),
                    }
                )
        else:
            for left in range(len(groups)):
                for right in range(left + 1, len(groups)):
                    raw = float(
                        sps.mannwhitneyu(
                            groups[left], groups[right], alternative="two-sided"
                        ).pvalue
                    )
                    pairs.append(
                        {
                            "pair": f"{keys[left]} vs {keys[right]}",
                            "p_raw": raw,
                            "cohens_d": _cohens_d(groups[left], groups[right]),
                        }
                    )
            adjusted = _adjust([pair["p_raw"] for pair in pairs], correction)
            for pair, value in zip(pairs, adjusted):
                effect = pair["cohens_d"]
                if effect is not None and abs(effect) < threshold - 1e-12:
                    continue
                posthoc_rows.append(
                    {
                        "pair": pair["pair"],
                        "p_value": round(float(value), 8),
                        "p_raw": round(pair["p_raw"], 8),
                        "cohens_d": None if effect is None else round(float(effect), 6),
                        "significant": bool(value < alpha),
                        "significant_bonferroni": bool(pair["p_raw"] < alpha / max(total_pairs, 1)),
                    }
                )
    metrics["posthoc_total_pairs"] = total_pairs
    metrics["posthoc_reported_pairs"] = len(posthoc_rows)

    tables = {"groups": table_of(frames, limit=40)}
    if posthoc_rows:
        tables["posthoc"] = table_of(pd.DataFrame(posthoc_rows), limit=40)

    notes = ["F 检验比较的是组间方差与组内方差之比。"]
    if welch:
        notes.append("已改用 Welch 方差分析：不假设方差齐性，分母自由度按各组样本量与方差校正。")
        notes.append(
            "平方和仍是经典分解（组间/组内），仅用于描述，"
            "Welch 的 F 与校正自由度才是这里的检验结论。"
        )
    if variance_test:
        notes.append(
            f"Levene 方差齐性检验（中心为均值）："
            f"统计量 {float(outcome.statistic):.4g}，p={levene_p:.4g}。"
        )
    if covariate:
        notes.append(f"已把 {covariate} 作为协变量做协方差分析，组间效应是扣除协变量后的结果。")
    if total_pairs:
        if posthoc_test == "tukey":
            notes.append(
                f"事后两两比较使用 Tukey HSD（假设各组方差齐性）；只报告效应量绝对值"
                f"不低于 {threshold:g} 的两两比较。"
            )
        else:
            notes.append(
                f"多重比较使用 Mann-Whitney 检验并做 "
                f"{CORRECTION_LABELS.get(correction, correction)} 校正；只报告效应量绝对值"
                f"不低于 {threshold:g} 的两两比较。"
            )
    if effect_kind == "omega_squared":
        notes.append("效应量按 ω² 报告，它比 η² 更少高估总体效应。")
    notes.append(f"组均值置信区间按 {level:.1%} 的 t 区间计算，输出 ci_low 与 ci_high 两列。")
    figures = []
    if want_box:
        figure_name = _boxplot_with_interval(
            context,
            groups,
            keys,
            [row.get("mean") for row in rows],
            [row.get("ci_low") for row in rows],
            [row.get("ci_high") for row in rows],
            f"均值与 {level:.0%} 置信区间",
            f"各组分布（F={float(statistic):.4g}，p={float(pvalue):.4g}）",
            "test.anova_boxplot",
        )
        if figure_name:
            figures.append(figure_name)
    return registry.result(
        "test.anova",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("test.wilcoxon")
def wilcoxon(context):
    from scipy import stats as sps

    table = context.table
    name, buckets = _paired_groups(context, context.text("by"))
    keys = sorted(buckets)
    if len(keys) != 2:
        raise MethodError(f"Wilcoxon 符号秩检验需要两组，当前 {len(keys)} 组。")
    size = buckets[keys[0]].size
    if size < 5:
        raise MethodError("配对样本至少需要 5 对。")
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    alternative = context.text("alternative", "two-sided", ALTERNATIVES)
    zero_method = context.text("zero_method", "wilcox", ("wilcox", "pratt", "zsplit"))
    want_hl = context.flag("hl", False)
    level = context.number("ci", 0.95, 0.5, 0.999)
    want_rank_biserial = context.flag("rank_biserial", False)
    want_rank_table = context.flag("rank_table", False)
    want_histogram = context.flag("histogram", True)
    first = buckets[keys[0]][:size]
    second = buckets[keys[1]][:size]
    statistic, pvalue = sps.wilcoxon(
        first, second, alternative=alternative, zero_method=zero_method
    )
    difference = first - second
    nonzero = int(np.count_nonzero(difference))
    rows = pd.DataFrame(
        [
            {
                "pair": f"{keys[0]} − {keys[1]}",
                "n": int(size),
                "nonzero_differences": nonzero,
                "median_difference": round(float(np.median(difference)), 6),
                "positive_ranks": int((difference > 0).sum()),
                "negative_ranks": int((difference < 0).sum()),
            }
        ]
    )
    metrics = {
        "group_column": name,
        "statistic": round(float(statistic), 6),
        "p_value": round(float(pvalue), 8),
        "pairs": int(size),
        "nonzero_pairs": nonzero,
        "alpha": alpha,
        "alternative": alternative,
        "zero_method": zero_method,
        "significant": bool(pvalue < alpha),
    }
    notes = [
        "符号秩检验不要求正态分布，但对差值的对称性有要求。",
        "差值为 0 的配对会被剔除，有效样本量可能小于配对数。",
        f"零差异处理方式为 {zero_method}，备择假设为 {alternative}。",
    ]
    effective = difference[difference != 0] if zero_method == "wilcox" else difference
    if effective.size < 2:
        notes.append("有效差值少于 2 个，无法估计中位数差的置信区间。")
    elif effective.size > PAIR_LIMIT:
        context.warn(
            f"有效差值 {effective.size} 超过 {PAIR_LIMIT}，"
            "已跳过 Hodges-Lehmann 估计与中位数差置信区间。"
        )
        notes.append(f"有效差值超过 {PAIR_LIMIT}，为控制内存未计算 Walsh 平均数。")
    else:
        low, high, estimate = _walsh_bounds(effective, level)
        metrics["ci_level"] = level
        metrics["ci_low"] = round(float(low), 6)
        metrics["ci_high"] = round(float(high), 6)
        if want_hl:
            metrics["hodges_lehmann"] = round(float(estimate), 6)
        notes.append(
            f"中位数差的 {level:.1%} 置信区间由 Walsh 平均数的次序统计量得到："
            f"[{low:.6g}, {high:.6g}]。"
        )
        if want_hl:
            notes.append(f"Hodges-Lehmann 估计（Walsh 平均数中位数）为 {estimate:.6g}。")
    tables = {"pairs": table_of(rows)}
    if want_rank_biserial:
        ranks = sps.rankdata(np.abs(effective))
        positive = float(ranks[effective > 0].sum())
        negative = float(ranks[effective < 0].sum())
        total_rank = positive + negative
        if total_rank > EPS:
            metrics["rank_biserial"] = round((positive - negative) / total_rank, 6)
            notes.append("秩二列相关 r = (正秩和 − 负秩和) / 总秩和，范围 −1 到 1。")
        else:
            metrics["rank_biserial"] = None
            notes.append("有效差值全为 0，秩二列相关无法计算。")
    if want_rank_table:
        rank_rows = []
        for index in range(difference.size):
            rank_rows.append(
                {
                    "index": int(index + 1),
                    "difference": round(float(difference[index]), 6),
                    "absolute": round(float(abs(difference[index])), 6),
                    "sign": (
                        "正" if difference[index] > 0 else "负" if difference[index] < 0 else "零"
                    ),
                }
            )
        tables["ranks"] = table_of(pd.DataFrame(rank_rows), limit=60)
        notes.append("已输出每对差值的明细表（含符号），零差异按所选方式处理。")
    figures = []
    if want_histogram:
        estimate_value = metrics.get("hodges_lehmann")
        name = _wilcoxon_hist(context, difference, estimate_value)
        if name:
            figures.append(name)
    return registry.result(
        "test.wilcoxon",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("test.mannwhitney")
def mannwhitney(context):
    from scipy import stats as sps

    table = context.table
    name, buckets = _groups(context, context.text("by"))
    keys = sorted(buckets)
    if len(keys) != 2:
        raise MethodError(f"Mann-Whitney U 检验需要两组，当前 {len(keys)} 组。")
    first, second = buckets[keys[0]], buckets[keys[1]]
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    alternative = context.text("alternative", "two-sided", ALTERNATIVES)
    method = context.text("method", "auto", ("auto", "asymptotic", "exact"))
    ranks = context.flag("ranks", True)
    level = context.number("ci", 0.95, 0.5, 0.999)
    want_auc = context.flag("auc", False)
    want_rank_table = context.flag("rank_table", False)
    want_box = context.flag("boxplot", True)
    statistic, pvalue = sps.mannwhitneyu(first, second, alternative=alternative, method=method)
    rank_biserial = 1 - (2 * float(statistic)) / (first.size * second.size)
    pooled = sps.rankdata(np.concatenate([first, second]))
    first_row = {
        "group": keys[0],
        "n": int(first.size),
        "median": round(float(np.median(first)), 6),
    }
    second_row = {
        "group": keys[1],
        "n": int(second.size),
        "median": round(float(np.median(second)), 6),
    }
    metrics = {
        "group_column": name,
        "u_statistic": round(float(statistic), 6),
        "p_value": round(float(pvalue), 8),
        "alpha": alpha,
        "alternative": alternative,
        "method": method,
        "significant": bool(pvalue < alpha),
        "rank_biserial": round(float(rank_biserial), 6),
        "effect_size_note": (
            "小"
            if abs(rank_biserial) < 0.1
            else "中"
            if abs(rank_biserial) < 0.3
            else "大"
            if abs(rank_biserial) < 0.5
            else "很大"
        ),
        "ranks": ranks,
    }
    notes = [
        "秩和检验比较的是分布位置，对异常值不敏感。",
        "秩二列相关 r 在 -1 到 1 之间，绝对值越大差异越明显。",
        f"备择假设为 {alternative}，p 值算法为 {method}。",
    ]
    if ranks:
        first_row["rank_sum"] = round(float(pooled[: first.size].sum()), 6)
        second_row["rank_sum"] = round(float(pooled[first.size :].sum()), 6)
        metrics["median_difference"] = round(float(np.median(first) - np.median(second)), 6)
        notes.append("分组表里给出了秩和，median_difference 是两组中位数之差。")
    rows = pd.DataFrame([first_row, second_row])
    product = first.size * second.size
    if product > 4000000:
        context.warn(f"两组样本量乘积 {product} 过大，已跳过位移量的置信区间。")
        notes.append("两组样本量乘积过大，为控制内存未计算成对差值。")
    else:
        low, high, estimate = _shift_bounds(first, second, level)
        metrics["ci_level"] = level
        metrics["ci_low"] = round(float(low), 6)
        metrics["ci_high"] = round(float(high), 6)
        metrics["hodges_lehmann"] = round(float(estimate), 6)
        notes.append(
            f"位移量（Hodges-Lehmann）估计为 {estimate:.6g}，"
            f"{level:.1%} 置信区间 [{low:.6g}, {high:.6g}]。"
        )
    if want_auc:
        total_pairs = float(first.size) * float(second.size)
        if total_pairs > 4000000:
            context.warn("两组样本量乘积过大，已跳过优势概率计算。")
            metrics["auc"] = None
        else:
            wins = float((first[:, None] > second[None, :]).sum())
            ties = float((first[:, None] == second[None, :]).sum())
            metrics["auc"] = round((wins + 0.5 * ties) / total_pairs, 6) if total_pairs else None
            notes.append("优势概率 AUC 是第一组取值大于第二组取值的概率（并列各计一半）。")
    tables = {"groups": table_of(rows)}
    if want_rank_table:
        items = [
            {
                "group": keys[0],
                "value": round(float(first[index]), 6),
                "rank": round(float(pooled[index]), 6),
            }
            for index in range(first.size)
        ]
        items += [
            {
                "group": keys[1],
                "value": round(float(second[index]), 6),
                "rank": round(float(pooled[first.size + index]), 6),
            }
            for index in range(second.size)
        ]
        tables["ranks"] = table_of(pd.DataFrame(items), limit=60)
        notes.append("已输出每条观测在合并样本中的秩明细表。")
    figures = []
    if want_box:
        name = _boxplot_with_interval(
            context,
            [first, second],
            [keys[0], keys[1]],
            [float(np.median(first)), float(np.median(second))],
            [None, None],
            [None, None],
            "中位数",
            f"两组分布（U={float(statistic):.4g}，p={float(pvalue):.4g}）",
            "test.mannwhitney_boxplot",
        )
        if name:
            figures.append(name)
    return registry.result(
        "test.mannwhitney",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("test.kruskal")
def kruskal(context):
    from scipy import stats as sps

    table = context.table
    name, buckets = _groups(context, context.text("by"))
    keys = sorted(buckets)
    if len(keys) < 3:
        raise MethodError("Kruskal-Wallis 检验用于三组及以上；两组请用 Mann-Whitney U 检验。")
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    posthoc = context.text("posthoc", "none", ("none", "dunn"))
    correction = context.text("correction", "holm", ("holm", "bonferroni", "sidak", "none"))
    tie_correction = context.flag("tie_correction", True)
    group_table = context.flag("group_table", True)
    level = context.number("ci", 0.95, 0.5, 0.999)
    want_box = context.flag("boxplot", True)
    groups = [buckets[key] for key in keys]
    pooled = np.concatenate(groups)
    size = pooled.size
    ranks = sps.rankdata(pooled)
    rank_sums = []
    offset = 0
    for group in groups:
        rank_sums.append(float(ranks[offset : offset + group.size].sum()))
        offset += group.size
    rank_sums = np.array(rank_sums)
    sizes = np.array([group.size for group in groups], dtype=float)
    statistic = 12.0 / (size * (size + 1)) * float(np.sum(rank_sums**2 / sizes)) - 3.0 * (size + 1)
    tie_factor = 1.0
    if tie_correction and size > 1:
        counts = pd.Series(pooled).value_counts().to_numpy(dtype=float)
        ties = float(np.sum(counts**3 - counts))
        tie_factor = 1.0 - ties / (size**3 - size)
        if tie_factor > EPS:
            statistic = statistic / tie_factor
    pvalue = float(sps.chi2.sf(float(statistic), len(groups) - 1))
    total = sum(group.size for group in groups)
    epsilon = (
        ((float(statistic) - len(groups) + 1) / (total - len(groups)))
        if total > len(groups)
        else None
    )

    rows = []
    offset = 0
    for key in keys:
        values = buckets[key]
        block = ranks[offset : offset + values.size]
        offset += values.size
        low, high = _median_ci(values, level)
        rows.append(
            {
                "group": key,
                "n": int(values.size),
                "median": round(float(np.median(values)), 6),
                "mean_rank": round(float(block.mean()), 6),
                "ci_low": _round(low, 6),
                "ci_high": _round(high, 6),
            }
        )
    metrics = {
        "group_column": name,
        "groups": len(groups),
        "h_statistic": round(float(statistic), 6),
        "p_value": round(pvalue, 8),
        "df": len(groups) - 1,
        "alpha": alpha,
        "significant": bool(pvalue < alpha),
        "tie_correction": tie_correction,
        "tie_factor": round(float(tie_factor), 6),
        "group_table": group_table,
        "ci_level": level,
    }
    if epsilon is not None:
        metrics["epsilon_squared"] = round(float(epsilon), 6)
    tables = {}
    if group_table:
        tables["groups"] = table_of(pd.DataFrame(rows), limit=40)
    notes = [
        "Kruskal-Wallis 是单因素方差分析的非参数替代。",
        "结果显著只说明至少有一组与其它组不同，具体哪几组需要事后两两比较。",
        f"秩相同分校正{'已启用' if tie_correction else '已关闭'}；"
        f"各组中位数按 {level:.1%} 的次序统计量区间给出。",
    ]
    if not group_table:
        notes.append("已按设置不输出分组统计表。")
    if posthoc != "none":
        posthoc_rows = _dunn_posthoc(groups, keys, correction, alpha)
        tables["posthoc"] = table_of(pd.DataFrame(posthoc_rows), limit=40)
        metrics["posthoc"] = posthoc
        metrics["posthoc_pairs"] = len(posthoc_rows)
        notes.append(
            f"事后比较使用 Dunn 检验，校正方式：{CORRECTION_LABELS.get(correction, correction)}。"
        )
    figures = []
    if want_box:
        name = _boxplot_with_interval(
            context,
            groups,
            keys,
            [row.get("median") for row in rows],
            [row.get("ci_low") for row in rows],
            [row.get("ci_high") for row in rows],
            f"中位数与 {level:.0%} 区间",
            f"各组分布（H={float(statistic):.4g}，p={float(pvalue):.4g}）",
            "test.kruskal_boxplot",
        )
        if name:
            figures.append(name)
    return registry.result(
        "test.kruskal",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("test.friedman")
def friedman(context):
    from scipy import stats as sps

    table = context.table
    name, buckets = _paired_groups(context, context.text("by"))
    keys = sorted(buckets)
    if len(keys) < 3:
        raise MethodError("Friedman 检验至少需要三个处理组。")
    size = buckets[keys[0]].size
    if size < 3:
        raise MethodError("每个处理至少需要 3 次重复。")
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    posthoc = context.text("posthoc", "none", ("none", "nemenyi"))
    correction = context.text("correction", "holm", ("holm", "bonferroni", "sidak", "none"))
    p_method = context.text("p_method", "chi2", ("chi2", "iman_davenport"))
    treatment_table = context.flag("treatment_table", True)
    with_kendall = context.flag("kendall", True)
    want_ranks_table = context.flag("ranks_table", False)
    want_rank_chart = context.flag("rank_chart", True)
    matrix = np.column_stack([buckets[key][:size] for key in keys])
    treatments = matrix.shape[1]
    blocks = matrix.shape[0]
    ranks = sps.rankdata(matrix, axis=1)
    statistic = float(
        sps.friedmanchisquare(*[matrix[:, index] for index in range(treatments)]).statistic
    )
    f_statistic = None
    df_first = None
    df_second = None
    if p_method == "iman_davenport":
        denominator = blocks * (treatments - 1) - statistic
        if denominator <= EPS:
            raise MethodError("Iman-Davenport 校正的分母不为正，无法计算 F 统计量。")
        df_first = treatments - 1
        df_second = (treatments - 1) * (blocks - 1)
        f_statistic = (blocks - 1) * statistic / denominator
        pvalue = float(sps.f.sf(f_statistic, df_first, df_second))
    else:
        pvalue = float(sps.chi2.sf(statistic, treatments - 1))
    kendall = statistic / (size * (treatments - 1)) if size and treatments > 1 else None
    rows = pd.DataFrame(
        [
            {
                "treatment": key,
                "n": int(size),
                "mean_rank": round(float(ranks.mean(axis=0)[index]), 6),
                "mean": round(float(matrix[:, index].mean()), 6),
            }
            for index, key in enumerate(keys)
        ]
    )
    metrics = {
        "group_column": name,
        "treatments": treatments,
        "blocks": int(size),
        "chi_square": round(float(statistic), 6),
        "p_value": round(pvalue, 8),
        "alpha": alpha,
        "significant": bool(pvalue < alpha),
        "p_method": p_method,
        "treatment_table": treatment_table,
        "kendall": with_kendall,
    }
    if f_statistic is not None:
        metrics["iman_davenport_f"] = round(float(f_statistic), 6)
        metrics["df1"] = int(df_first)
        metrics["df2"] = int(df_second)
    tables = {}
    if treatment_table:
        tables["treatments"] = table_of(rows, limit=40)
    notes = [
        "Friedman 检验用于随机区组设计，每个区组内比较多个处理。",
        "卡方统计量已按秩相同分做修正（与 Friedman 原始定义一致）。",
    ]
    if not treatment_table:
        notes.append("已按设置不输出各处理统计表。")
    if p_method == "iman_davenport":
        notes.append(
            f"p 值改用 Iman-Davenport F 校正：F={f_statistic:.4g}，"
            f"自由度 ({df_first}, {df_second})，小样本下比卡方近似更保守。"
        )
    if kendall is not None and with_kendall:
        metrics["kendall_w"] = round(float(kendall), 6)
        metrics["agreement_note"] = "弱" if kendall < 0.3 else "中" if kendall < 0.6 else "强"
        notes.append("Kendall's W 表示评价者/区组之间的一致性程度。")
    if posthoc != "none":
        posthoc_rows = _nemenyi_posthoc(matrix, keys, correction, alpha)
        tables["posthoc"] = table_of(pd.DataFrame(posthoc_rows), limit=40)
        metrics["posthoc"] = posthoc
        metrics["posthoc_pairs"] = len(posthoc_rows)
        notes.append(
            f"事后比较使用 Nemenyi 检验，校正方式："
            f"{CORRECTION_LABELS.get(correction, correction)}。"
        )
    if want_ranks_table:
        rank_frame = pd.DataFrame(np.round(ranks, 6), columns=[str(key) for key in keys])
        rank_frame.insert(0, "block", np.arange(1, blocks + 1))
        tables["ranks"] = table_of(rank_frame, limit=60)
        notes.append("已输出各区组内各处理的秩明细（每行一个区组，1 表示该区组内最小）。")
    figures = []
    if want_rank_chart:
        name = _friedman_rank_chart(context, rows, metrics.get("kendall_w"), statistic, pvalue)
        if name:
            figures.append(name)
    return registry.result(
        "test.friedman",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("test.cochran")
def cochran(context):
    from statsmodels.stats.contingency_tables import cochrans_q

    table = context.table
    name, buckets = _paired_groups(context, context.text("by"))
    keys = sorted(buckets)
    if len(keys) < 3:
        raise MethodError("Cochran's Q 检验至少需要三个处理。")
    size = buckets[keys[0]].size
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    posthoc = context.text("posthoc", "none", ("none", "mcnemar"))
    correction = context.text("correction", "holm", ("holm", "bonferroni", "sidak", "none"))
    threshold = context.number("threshold", 0.0, -1e9, 1e9)
    rate_table = context.flag("rate_table", True)
    level = context.number("ci", 0.95, 0.5, 0.999)
    ci_method = context.text("ci_method", "wilson", ("wilson", "wald", "exact"))
    want_rate_chart = context.flag("rate_chart", True)
    matrix = np.column_stack([(buckets[key][:size] > threshold).astype(int) for key in keys])
    outcome = cochrans_q(matrix)
    statistic = float(outcome.statistic if hasattr(outcome, "statistic") else outcome[0])
    pvalue = float(outcome.pvalue if hasattr(outcome, "pvalue") else outcome[1])
    if not math.isfinite(statistic) or not math.isfinite(pvalue):
        raise MethodError("所有处理的结果都相同（区组内没有差异），Cochran's Q 无法计算。")
    rows = []
    for index, key in enumerate(keys):
        successes = int(matrix[:, index].sum())
        low, high = _proportion_ci(successes, int(size), level, ci_method)
        rows.append(
            {
                "treatment": key,
                "n": int(size),
                "successes": successes,
                "rate": round(float(matrix[:, index].mean()), 6),
                "ci_low": _round(low, 6),
                "ci_high": _round(high, 6),
            }
        )
    metrics = {
        "group_column": name,
        "treatments": len(keys),
        "blocks": int(size),
        "q_statistic": round(statistic, 6),
        "p_value": round(pvalue, 8),
        "df": len(keys) - 1,
        "alpha": alpha,
        "significant": bool(pvalue < alpha),
        "threshold": threshold,
        "rate_table": rate_table,
        "ci_level": level,
    }
    tables = {}
    if rate_table:
        tables["treatments"] = table_of(pd.DataFrame(rows), limit=30)
    notes = [
        "Cochran's Q 是二分响应的重复测量检验，相当于二分版本的 Friedman。",
        f"这里把目标列中严格大于 {threshold:g} 的取值视为“成功”。",
        f"各处理成功率的置信区间是 {level:.1%} 的 {CI_LABELS[ci_method]} 区间。",
    ]
    if not rate_table:
        notes.append("已按设置不输出各处理成功率表。")
    if posthoc != "none":
        posthoc_rows = _mcnemar_posthoc(matrix, keys, correction, alpha)
        tables["posthoc"] = table_of(pd.DataFrame(posthoc_rows), limit=30)
        metrics["posthoc"] = posthoc
        metrics["posthoc_pairs"] = len(posthoc_rows)
        notes.append(
            f"事后比较使用 McNemar 检验，校正方式："
            f"{CORRECTION_LABELS.get(correction, correction)}。"
        )
    figures = []
    if want_rate_chart:
        name = _cochran_rate_chart(context, pd.DataFrame(rows), level, CI_LABELS[ci_method])
        if name:
            figures.append(name)
    return registry.result(
        "test.cochran",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("test.chi2")
def chi2(context):
    from scipy import stats as sps

    table = context.table
    bins = context.whole("bins", 4, 2, 20)
    correction = context.text("correction", "auto", ("auto", "yes", "no"))
    statistic_kind = context.text("statistic", "pearson", tuple(DIVERGENCE))
    effect_size = context.text("effect_size", "cramers_v", ("cramers_v", "phi", "contingency"))
    p_method = context.text("p_method", "chi2", ("chi2", "monte_carlo"))
    reps = context.whole("mc_reps", 2000, 100, 20000)
    seed = context.whole("mc_seed", 42, 0, 1000000)
    want_residuals = context.flag("residuals", False)
    want_heatmap = context.flag("heatmap", True)
    candidates = [name for name in table.raw.columns if table.raw[name].nunique(dropna=False) <= 20]
    if len(candidates) < 2:
        raise MethodError("卡方检验需要两个低基数列。")
    first = context.text("row")
    second = context.text("column")
    if first and first not in table.raw.columns:
        raise MethodError(f"行变量 {first} 不在数据里。")
    if second and second not in table.raw.columns:
        raise MethodError(f"列变量 {second} 不在数据里。")
    if not first:
        first = candidates[0]
    if not second or second == first:
        second = next(name for name in candidates if name != first)
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)

    observed = pd.crosstab(_binned(table.raw[first], bins), _binned(table.raw[second], bins))
    if observed.shape[0] < 2 or observed.shape[1] < 2:
        raise MethodError("列联表至少需要 2×2。")
    if correction == "yes":
        use_correction = True
    elif correction == "no":
        use_correction = False
    else:
        use_correction = observed.shape == (2, 2)
    lambda_ = DIVERGENCE[statistic_kind]
    statistic, pvalue, dfree, expected = sps.chi2_contingency(
        observed.to_numpy(), correction=use_correction, lambda_=lambda_
    )
    total = observed.to_numpy().sum()
    cramers = math.sqrt(float(statistic) / (total * (min(observed.shape) - 1))) if total else None
    effect_labels = {"cramers_v": "Cramér's V", "phi": "φ 系数", "contingency": "列联系数 C"}
    effect_value = None
    effect_key = None
    if total:
        if effect_size == "phi":
            effect_key = "phi_coefficient"
            effect_value = math.sqrt(float(statistic) / float(total))
        elif effect_size == "contingency":
            effect_key = "contingency_coefficient"
            denominator = float(statistic) + float(total)
            effect_value = math.sqrt(float(statistic) / denominator) if denominator > EPS else None
        else:
            effect_key = "cramers_v"
            effect_value = cramers
    small = int((expected < 5).sum())
    expected_frame = pd.DataFrame(
        np.round(expected, 3), index=observed.index, columns=observed.columns
    )

    metrics = {
        "row_variable": first,
        "column_variable": second,
        "chi_square": round(float(statistic), 6),
        "p_value": round(float(pvalue), 8),
        "df": int(dfree),
        "alpha": alpha,
        "significant": bool(pvalue < alpha),
        "cells_with_expected_below_5": small,
        "correction": bool(use_correction),
        "bins": bins,
        "statistic": statistic_kind,
        "lambda": lambda_,
        "residuals": want_residuals,
    }
    if effect_value is not None:
        metrics[effect_key] = round(float(effect_value), 6)
        metrics["effect_size_note"] = (
            "小" if effect_value < 0.1 else "中" if effect_value < 0.3 else "大"
        )
    tables = {"observed": _labeled_table(observed), "expected": _labeled_table(expected_frame)}
    if want_residuals:
        items = []
        for row_index, row_label in enumerate(observed.index):
            for column_index, column_label in enumerate(observed.columns):
                count = int(observed.iloc[row_index, column_index])
                expect = float(expected[row_index, column_index])
                items.append(
                    {
                        "row": str(row_label),
                        "column": str(column_label),
                        "observed": count,
                        "expected": round(expect, 3),
                        "residual": round(count - expect, 3),
                        "std_residual": (
                            None if expect <= 0 else round((count - expect) / math.sqrt(expect), 6)
                        ),
                    }
                )
        tables["residuals"] = table_of(pd.DataFrame(items), limit=60)
    notes = [
        "卡方检验要求期望频数大多大于 5；小于 5 的格子较多时应改用 Fisher 精确检验。",
        f"{effect_labels[effect_size]} 用于衡量关联强度，0 表示独立。",
        f"连续性校正：{'启用' if use_correction else '关闭'}；数值列按 {bins} 个等宽区间分箱。",
        f"统计量类型：{DIVERGENCE_LABELS[statistic_kind]}，Cressie-Read 幂参数 λ={lambda_:g}。",
    ]
    if want_residuals:
        notes.append("已输出标准化残差表：(观测−期望)/√期望，绝对值大于 2 的格子值得关注。")
    if p_method == "monte_carlo":
        probabilities = expected / max(float(expected.sum()), EPS)
        generator = np.random.default_rng(seed)
        simulated_statistic = np.empty(int(reps))
        flat = probabilities.ravel()
        for index in range(int(reps)):
            draw = generator.multinomial(int(total), flat).reshape(expected.shape)
            simulated_statistic[index] = sps.chi2_contingency(
                draw, correction=False, lambda_=lambda_
            )[0]
        monte = float(
            (1 + int((simulated_statistic >= float(statistic) - 1e-12).sum())) / (int(reps) + 1)
        )
        metrics["monte_carlo_p_value"] = round(monte, 8)
        metrics["monte_carlo_reps"] = int(reps)
        metrics["monte_carlo_seed"] = int(seed)
        notes.append(
            f"Monte Carlo p 值由 {int(reps)} 次按期望比例的多项式重抽样得到"
            f"（种子 {int(seed)}）：p={monte:.6g}；卡方近似的 p 值为 "
            f"{float(pvalue):.6g}。"
        )
    figures = []
    if want_heatmap:
        name = _chi2_heatmap(context, observed, expected)
        if name:
            figures.append(name)
    return registry.result(
        "test.chi2",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("test.gof")
def gof(context):
    from scipy import stats as sps

    table = context.table
    column = context.text("column") or table.target_name
    if not column:
        raise MethodError("拟合优度检验需要目标列，或先指定检验的列。")
    if column not in table.raw.columns:
        raise MethodError(f"列 {column} 不在数据里。")
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    expected_kind = context.want("expected")
    if expected_kind not in ("uniform", "normal"):
        expected_kind = "uniform"
    bins = context.whole("bins", 5, 2, 50)
    sigma = context.number("sigma", 1.0, 1e-6, 1e6)
    p_method = context.text("p_method", "chi2", ("chi2", "monte_carlo"))
    reps = context.whole("mc_reps", 2000, 100, 20000)
    seed = context.whole("gof_seed", 42, 0, 1000000)
    ddof = context.whole("ddof", 0, 0, 5)
    compare_table = context.flag("compare_table", True)
    want_histogram = context.flag("histogram", True)
    series = table.raw[column]

    mean_estimate = None
    edges = None
    if expected_kind == "normal":
        if not pd.api.types.is_numeric_dtype(series):
            raise MethodError("正态期望分布需要数值列。")
        values = pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype=float)
        if values.size < bins:
            raise MethodError(f"有效样本 {values.size} 少于分箱数 {bins}。")
        edges = np.linspace(float(values.min()), float(values.max()), bins + 1)
        counts, _ = np.histogram(values, bins=edges)
        mean_estimate = float(values.mean())
        probabilities = np.diff(sps.norm.cdf((edges - mean_estimate) / sigma))
        if (probabilities <= 0).any():
            raise MethodError("正态期望频数出现非正值，请调整 sigma 或分箱数。")
        observed_counts = counts.astype(float)
        expected_values = probabilities / probabilities.sum() * observed_counts.sum()
        labels = [f"[{edges[index]:.4g}, {edges[index + 1]:.4g})" for index in range(bins)]
    else:
        counts = _binned(series, bins).value_counts().sort_index()
        if counts.size < 2:
            raise MethodError("至少需要两个类别。")
        observed_counts = counts.to_numpy(dtype=float)
        expected_values = np.full(counts.size, observed_counts.sum() / counts.size, dtype=float)
        labels = [str(item) for item in counts.index]

    categories = int(observed_counts.size)
    degrees = categories - 1 - ddof
    if degrees < 1:
        raise MethodError(f"自由度调整 {ddof} 过大：{categories} 个类别至少要保留 1 个自由度。")
    statistic = float(sps.chisquare(observed_counts, f_exp=expected_values).statistic)
    pvalue = float(sps.chi2.sf(statistic, degrees))
    rows = pd.DataFrame(
        {
            "category": labels,
            "observed": observed_counts.astype(int),
            "expected": np.round(expected_values, 3),
            "difference": np.round(observed_counts - expected_values, 3),
        }
    )
    metrics = {
        "categories": categories,
        "chi_square": round(statistic, 6),
        "p_value": round(pvalue, 8),
        "df": degrees,
        "uniform_null": expected_kind == "uniform",
        "column": column,
        "alpha": alpha,
        "expected": expected_kind,
        "bins": bins,
        "significant": bool(pvalue < alpha),
        "ddof": ddof,
        "p_method": p_method,
        "compare_table": compare_table,
    }
    if mean_estimate is not None:
        metrics["mean_estimate"] = round(mean_estimate, 6)
        metrics["sigma"] = sigma
    notes = [
        "默认检验“各类别均匀分布”；选择正态期望时按样本均值与给定标准差计算区间概率。",
        f"检验列：{column}；数值列按 {bins} 个等宽区间分箱。",
        f"显著性水平：{alpha:g}；自由度已扣除 {ddof} 个估计参数。",
    ]
    tables = {"categories": table_of(rows, limit=40)} if compare_table else {}
    if not compare_table:
        notes.append("已按设置不输出观测与期望的对比表。")
    if p_method == "monte_carlo":
        total = int(observed_counts.sum())
        probabilities = expected_values / expected_values.sum()
        generator = np.random.default_rng(seed)
        if expected_kind == "normal":
            draws = generator.normal(mean_estimate, sigma, size=(reps, total))
            position = np.clip(np.searchsorted(edges, draws, side="right") - 1, 0, categories - 1)
            simulated = np.zeros((reps, categories))
            for index in range(categories):
                simulated[:, index] = (position == index).sum(axis=1)
        else:
            simulated = generator.multinomial(total, probabilities, size=reps).astype(float)
        expected_row = probabilities * total
        spread = np.where(expected_row > 0, expected_row, 1.0)
        simulated_statistic = (((simulated - expected_row) ** 2) / spread).sum(axis=1)
        monte = float((1 + int((simulated_statistic >= statistic - 1e-12).sum())) / (reps + 1))
        metrics["monte_carlo_p_value"] = round(monte, 8)
        metrics["monte_carlo_reps"] = reps
        metrics["monte_carlo_seed"] = seed
        notes.append(
            f"Monte Carlo p 值由 {reps} 次重抽样得到（种子 {seed}）："
            f"p={monte:.6g}；卡方近似的 p 值为 {pvalue:.6g}。"
        )
    figures = []
    if want_histogram:
        name = _gof_compare_chart(context, rows, statistic, pvalue)
        if name:
            figures.append(name)
    return registry.result(
        "test.gof",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("test.fisher")
def fisher(context):
    from scipy import stats as sps
    from scipy.stats.contingency import odds_ratio

    table = context.table
    candidates = [name for name in table.raw.columns if table.raw[name].nunique(dropna=False) == 2]
    if len(candidates) < 2:
        raise MethodError("Fisher 精确检验需要两个二值列。")
    first = context.text("row")
    second = context.text("column")
    if first and first not in table.raw.columns:
        raise MethodError(f"行变量 {first} 不在数据里。")
    if second and second not in table.raw.columns:
        raise MethodError(f"列变量 {second} 不在数据里。")
    if not first or first not in candidates:
        first = candidates[0]
    if not second or second not in candidates or second == first:
        second = next(name for name in candidates if name != first)
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    alternative = context.text("alternative", "two-sided", ALTERNATIVES)
    estimate = context.text("estimate", "sample", ("sample", "conditional"))
    level = context.number("ci", 0.95, 0.5, 0.999)
    want_mid_p = context.flag("mid_p", False)
    want_relative_risk = context.flag("relative_risk", False)
    want_residuals = context.flag("residuals", False)
    want_forest = context.flag("forest_plot", True)

    observed = pd.crosstab(table.raw[first], table.raw[second])
    if observed.shape != (2, 2):
        raise MethodError(
            f"Fisher 精确检验需要 2×2 表，当前 {observed.shape[0]}×{observed.shape[1]}。"
        )
    table2 = observed.to_numpy()
    odds, pvalue = sps.fisher_exact(table2, alternative=alternative)
    if estimate == "conditional":
        odds = float(odds_ratio(table2, kind="conditional").statistic)
    else:
        odds = float(odds)
    rows = int(table2[0].sum())
    columns = int(table2[:, 0].sum())
    total = int(table2.sum())
    if rows and columns and total:
        a = table2[0, 0]
        b = table2[0, 1]
        c = table2[1, 0]
        d = table2[1, 1]
        phi = (a * d - b * c) / math.sqrt(
            max(rows * columns * (total - rows) * (total - columns), EPS)
        )
    else:
        phi = None
    metrics = {
        "row_variable": first,
        "column_variable": second,
        "odds_ratio": round(float(odds), 6),
        "p_value": round(float(pvalue), 8),
        "alpha": alpha,
        "alternative": alternative,
        "significant": bool(pvalue < alpha),
        "estimate": estimate,
        "ci_level": level,
        "residuals": want_residuals,
    }
    if phi is not None:
        metrics["phi_coefficient"] = round(float(phi), 6)
    notes = [
        "Fisher 精确检验基于超几何分布，适合小样本或期望频数偏低的 2×2 表。",
        "优势比 OR 大于 1 表示第一行与第一列的关联为正。",
        f"备择假设为 {alternative}；优势比按"
        f"{'条件极大似然' if estimate == 'conditional' else '样本比值'}估计。",
    ]
    try:
        outcome = odds_ratio(table2, kind=estimate)
        interval = outcome.confidence_interval(confidence_level=level)
        low, high = float(interval.low), float(interval.high)
    except (ValueError, ZeroDivisionError, FloatingPointError) as error:
        low, high = None, None
        context.warn(f"优势比的置信区间无法计算：{error}")
    metrics["odds_ratio_ci_low"] = _round(low, 6)
    metrics["odds_ratio_ci_high"] = _round(high, 6)
    if low is None:
        notes.append(f"优势比的 {level:.1%} 置信区间无法计算（存在零格子）。")
    else:
        notes.append(
            f"优势比的 {level:.1%} 置信区间："
            f"[{low:.6g}, {high:.6g}]（{'条件极大似然' if estimate == 'conditional' else 'Woolf 对数正态近似'}）。"
        )
    tables = {"observed": _labeled_table(observed)}
    expected = np.outer(table2.sum(axis=1), table2.sum(axis=0)) / max(total, 1)
    if want_residuals:
        items = []
        for row_index, row_label in enumerate(observed.index):
            for column_index, column_label in enumerate(observed.columns):
                count = int(table2[row_index, column_index])
                expect = float(expected[row_index, column_index])
                items.append(
                    {
                        "row": str(row_label),
                        "column": str(column_label),
                        "observed": count,
                        "expected": round(expect, 3),
                        "residual": round(count - expect, 3),
                        "std_residual": (
                            None if expect <= 0 else round((count - expect) / math.sqrt(expect), 6)
                        ),
                    }
                )
        tables["residuals"] = table_of(pd.DataFrame(items), limit=20)
        notes.append("已输出观测与期望的对比表，标准化残差为 (观测−期望)/√期望。")
    mid_value = None
    if want_mid_p:
        from scipy.stats import hypergeom

        probability_observed = float(hypergeom.pmf(int(table2[0, 0]), total, columns, rows))
        mid_value = max(float(pvalue) - 0.5 * probability_observed, 0.0)
        metrics["mid_p_value"] = round(float(mid_value), 8)
        metrics["observed_table_probability"] = round(probability_observed, 8)
        notes.append(
            f"mid-p 值 = 精确 p 值 − 0.5×观测表概率 = {float(mid_value):.6g}"
            f"（观测表概率 {probability_observed:.6g}）。"
        )
    risk_first = None
    risk_second = None
    if want_relative_risk:
        first_total = int(table2[0].sum())
        second_total = int(table2[1].sum())
        if first_total and second_total:
            risk_first = float(table2[0, 0]) / float(first_total)
            risk_second = float(table2[1, 0]) / float(second_total)
    if risk_first is not None and risk_second is not None:
        metrics["risk_first"] = round(float(risk_first), 6)
        metrics["risk_second"] = round(float(risk_second), 6)
        metrics["risk_difference"] = round(float(risk_first - risk_second), 6)
        if risk_second > EPS:
            metrics["risk_ratio"] = round(float(risk_first / risk_second), 6)
        notes.append(
            f"第一行风险 {float(risk_first):.4g}、第二行风险 {float(risk_second):.4g}，"
            "风险差为两者之差；风险比为两者之比（第二行风险为 0 时不报告）。"
        )
    elif want_relative_risk:
        notes.append("有一行的合计为 0，无法计算相对风险。")
    figures = []
    if want_forest:
        name = _fisher_forest(context, odds, low, high, level, pvalue)
        if name:
            figures.append(name)
    return registry.result(
        "test.fisher",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _frequency_figure(context, frame, cumulative):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过频数条形图。")
        return None
    columns = list(dict.fromkeys(str(item) for item in frame["column"]))[:4]
    if not columns:
        return None
    ncols = min(2, len(columns))
    nrows = (len(columns) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.2 * ncols, 4.8 * nrows), squeeze=False)
    for position, name in enumerate(columns):
        axis = axes.flat[position]
        block = frame[frame["column"] == name]
        labels = [str(item) for item in block["level"]]
        counts = block["count"].to_numpy(dtype=float)
        axis.bar(labels, counts, color="#4f7cff")
        axis.set_title(str(name), fontsize=10)
        axis.set_ylabel("频数")
        axis.grid(alpha=0.3, axis="y")
        if cumulative and "cumulative_ratio" in block.columns:
            twin = axis.twinx()
            twin.plot(
                labels,
                block["cumulative_ratio"].to_numpy(dtype=float) * 100.0,
                color="#d64545",
                marker="o",
                markersize=3,
                linewidth=1.0,
            )
            twin.set_ylabel("累计占比（%）", fontsize=8)
            twin.set_ylim(0.0, 105.0)
        plt.setp(axis.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    for axis in list(axes.flat)[len(columns) :]:
        axis.set_visible(False)
    fig.suptitle("各列频数分布", fontsize=11)
    return context.save(fig, "describe.frequency_bar")


def _boxplot_with_interval(
    context, arrays, labels, centers, lows, highs, series_label, title, name
):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过箱线图。")
        return None
    if not arrays:
        return None
    fig, axis = plt.subplots(figsize=(max(5.4, 0.8 * len(arrays) + 2.2), 4.4))
    axis.boxplot(
        arrays,
        tick_labels=[str(item) for item in labels],
        patch_artist=True,
        boxprops={"facecolor": "#cfe0ff", "edgecolor": "#3a5fa8"},
        medianprops={"color": "#3a5fa8"},
    )
    positions = []
    values = []
    errors = []
    for index, center in enumerate(centers):
        if center is None:
            continue
        positions.append(index + 1)
        values.append(float(center))
        if lows[index] is not None and highs[index] is not None:
            errors.append(max((float(highs[index]) - float(lows[index])) / 2.0, 0.0))
        else:
            errors.append(0.0)
    if positions:
        axis.errorbar(
            positions,
            values,
            yerr=errors,
            fmt="D",
            color="#d64545",
            markersize=4,
            capsize=3,
            linewidth=1.0,
            label=series_label,
        )
        axis.legend(fontsize=8)
    axis.set_title(title, fontsize=10)
    axis.set_ylabel("取值")
    axis.grid(alpha=0.3, axis="y")
    return context.save(fig, name)


def _interval_from_block(block, level, centers, lows, highs):
    from scipy import stats as sps

    if block.size > 1:
        error = float(block.std(ddof=1)) / math.sqrt(block.size)
        critical = float(sps.t.ppf(1.0 - (1.0 - level) / 2.0, block.size - 1))
        centers.append(float(block.mean()))
        lows.append(float(block.mean()) - critical * error)
        highs.append(float(block.mean()) + critical * error)
    else:
        centers.append(float(block.mean()))
        lows.append(None)
        highs.append(None)


def _stats_boxplot(context, frame, level, group_column=None):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过分布箱线图。")
        return None

    columns = [name for name in frame.columns][:16]
    if not columns:
        return None
    count = len(columns)
    ncols = min(4, count)
    nrows = int(math.ceil(count / float(ncols)))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.9 * ncols, 3.3 * nrows), squeeze=False)
    for position, name in enumerate(columns):
        axis = axes[position // ncols][position % ncols]
        arrays = []
        labels = []
        centers = []
        lows = []
        highs = []
        if group_column:
            keys = _category_labels(context.table.raw[group_column]).to_numpy()
            numeric = pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=float)
            buckets = _bucketize(keys, numeric)
            for key in sorted(buckets):
                block = buckets[key]
                if block.size == 0:
                    continue
                arrays.append(block)
                labels.append(str(key))
                _interval_from_block(block, level, centers, lows, highs)
        else:
            values = pd.to_numeric(frame[name], errors="coerce").dropna().to_numpy(dtype=float)
            if values.size == 0:
                continue
            arrays.append(values)
            labels.append("全部")
            _interval_from_block(values, level, centers, lows, highs)
        if not arrays:
            continue
        axis.boxplot(
            arrays,
            tick_labels=labels,
            patch_artist=True,
            boxprops={"facecolor": "#cfe0ff", "edgecolor": "#3a5fa8"},
            medianprops={"color": "#3a5fa8"},
        )
        positions = []
        center_values = []
        errors = []
        for index, center in enumerate(centers):
            if center is None:
                continue
            positions.append(index + 1)
            center_values.append(float(center))
            errors.append(
                0.0
                if lows[index] is None or highs[index] is None
                else max((float(highs[index]) - float(lows[index])) / 2.0, 0.0)
            )
        if positions:
            axis.errorbar(
                positions,
                center_values,
                yerr=errors,
                fmt="D",
                color="#d64545",
                markersize=4,
                capsize=3,
                linewidth=1.0,
            )
        axis.set_title(str(name), fontsize=9)
        axis.grid(alpha=0.3, axis="y")
        plt.setp(axis.get_xticklabels(), rotation=30, ha="right", fontsize=7)
    for index in range(count, nrows * ncols):
        axes[index // ncols][index % ncols].set_visible(False)
    fig.suptitle(f"各列分布与均值 {level:.0%} 置信区间", fontsize=11)
    fig.tight_layout()
    return context.save(fig, "describe.stats_boxplot")


def _crosstab_heatmap(context, counts, first, second):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过列联表热力图。")
        return None
    values = counts.to_numpy(dtype=float)
    if values.size == 0:
        return None
    fig, axis = plt.subplots(
        figsize=(max(4.6, 0.85 * values.shape[1] + 2.2), max(3.6, 0.6 * values.shape[0] + 1.8))
    )
    image = axis.imshow(values, cmap="Blues", aspect="auto")
    axis.set_xticks(np.arange(values.shape[1]), labels=[str(item) for item in counts.columns])
    axis.set_yticks(np.arange(values.shape[0]), labels=[str(item) for item in counts.index])
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            shade = "#ffffff" if values[row, column] > 0.6 * float(values.max()) else "#1b2a41"
            axis.text(
                column,
                row,
                f"{int(values[row, column])}",
                ha="center",
                va="center",
                fontsize=8,
                color=shade,
            )
    fig.colorbar(image, ax=axis, shrink=0.85)
    axis.set_xlabel(str(second))
    axis.set_ylabel(str(first))
    axis.set_title(f"{first} × {second} 列联表热力图", fontsize=10)
    plt.setp(axis.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    return context.save(fig, "describe.crosstab_heatmap")


def _aggregate_bar(context, frame, value_column, count_column, stat):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过分组汇总条形图。")
        return None
    if frame.empty or value_column not in frame.columns:
        return None
    labels = [str(item) for item in frame["group"]]
    values = pd.to_numeric(frame[value_column], errors="coerce").to_numpy(dtype=float)
    fig, axis = plt.subplots(figsize=(max(5.4, 0.6 * len(labels) + 2.4), 4.4))
    bars = axis.bar(labels, values, color="#4f7cff")
    for position, bar in enumerate(bars):
        if not math.isfinite(float(values[position])):
            continue
        axis.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height(),
            f"{values[position]:.4g}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
        if count_column and count_column in frame.columns:
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                0.0,
                f"n={int(frame[count_column].iloc[position])}",
                ha="center",
                va="bottom",
                fontsize=7,
                color="#4a5568",
            )
    axis.set_xlabel("分组")
    axis.set_ylabel(str(stat))
    axis.set_title(f"各组 {stat} 对比", fontsize=10)
    axis.grid(alpha=0.3, axis="y")
    plt.setp(axis.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    return context.save(fig, "describe.aggregate_bar")


def _explore_missing_chart(context, overview):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过缺失比例条形图。")
        return None
    if overview.empty:
        return None
    labels = [str(item) for item in overview["column"]]
    ratios = overview["missing_ratio"].to_numpy(dtype=float) * 100.0
    unique = overview["unique"].to_numpy(dtype=float)
    fig, axis = plt.subplots(figsize=(max(6.0, 0.5 * len(labels) + 2.4), 4.4))
    bars = axis.bar(labels, ratios, color="#f0a35e")
    for position, bar in enumerate(bars):
        axis.text(
            bar.get_x() + bar.get_width() / 2.0,
            0.0,
            f"{int(unique[position])}",
            ha="center",
            va="bottom",
            fontsize=7,
            color="#4a5568",
        )
        if ratios[position] > 0:
            axis.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height(),
                f"{ratios[position]:.2f}%",
                ha="center",
                va="bottom",
                fontsize=7,
            )
    axis.set_ylabel("缺失比例（%）")
    axis.set_xlabel("列（柱内数字为唯一值个数）")
    axis.set_title("各列缺失比例", fontsize=10)
    axis.grid(alpha=0.3, axis="y")
    plt.setp(axis.get_xticklabels(), rotation=60, ha="right", fontsize=8)
    return context.save(fig, "describe.explore_missing")


def _power_curve(context, curve, per_group, power_target):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过功效曲线图。")
        return None
    if curve.empty:
        return None
    sizes = curve["per_group"].to_numpy(dtype=float)
    power = curve["power"].to_numpy(dtype=float)
    fig, axis = plt.subplots(figsize=(6.4, 4.4))
    axis.plot(sizes, power, marker="o", color="#4f7cff", label="功效")
    axis.axhline(
        power_target,
        color="#d64545",
        linestyle="--",
        linewidth=1.1,
        label=f"目标功效 {power_target:g}",
    )
    axis.axvline(
        per_group,
        color="#41a36d",
        linestyle=":",
        linewidth=1.2,
        label=f"所需每组样本量 {per_group}",
    )
    axis.set_xlabel("每组样本量")
    axis.set_ylabel("功效")
    axis.set_title("功效曲线", fontsize=10)
    axis.set_ylim(0.0, 1.05)
    axis.grid(alpha=0.3)
    axis.legend(fontsize=8)
    return context.save(fig, "describe.power_curve")


def _ttest_figure(
    context, kind, first, second, keys, level, popmean, mean_difference, ci_low, ci_high
):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过分布箱线图。")
        return None
    from scipy import stats as sps

    if kind == "one_sample":
        if first is None or np.asarray(first).size == 0:
            return None
        arrays = [np.asarray(first, dtype=float)]
        labels = ["样本"]
    else:
        if first is None or second is None:
            return None
        if np.asarray(first).size == 0 or np.asarray(second).size == 0:
            return None
        arrays = [np.asarray(first, dtype=float), np.asarray(second, dtype=float)]
        labels = [str(keys[0]), str(keys[1])]
    fig, axis = plt.subplots(figsize=(6.2, 4.4))
    axis.boxplot(
        arrays,
        tick_labels=labels,
        patch_artist=True,
        boxprops={"facecolor": "#cfe0ff", "edgecolor": "#3a5fa8"},
        medianprops={"color": "#3a5fa8"},
    )
    for position, block in enumerate(arrays, start=1):
        block = block[np.isfinite(block)]
        if block.size > 1:
            error = float(block.std(ddof=1)) / math.sqrt(block.size)
            critical = float(sps.t.ppf(1.0 - (1.0 - level) / 2.0, block.size - 1))
            axis.errorbar(
                [position],
                [float(block.mean())],
                yerr=[critical * error],
                fmt="D",
                color="#d64545",
                markersize=4,
                capsize=3,
                linewidth=1.0,
            )
    if kind == "one_sample":
        axis.axhline(
            popmean, color="#41a36d", linestyle="--", linewidth=1.2, label=f"参照均值 {popmean:g}"
        )
        if ci_low is not None and ci_high is not None:
            axis.axhline(float(ci_low) + popmean, color="#8a63d2", linestyle=":", linewidth=1.0)
            axis.axhline(float(ci_high) + popmean, color="#8a63d2", linestyle=":", linewidth=1.0)
        axis.legend(fontsize=8)
    title = "样本分布与均值置信区间" if kind == "one_sample" else "两组分布与均值置信区间"
    if mean_difference is not None and ci_low is not None:
        title += (
            f"（均值差 {float(mean_difference):.4g}，{level:.0%} 区间 "
            f"[{float(ci_low):.4g}, {float(ci_high):.4g}]）"
        )
    axis.set_title(title, fontsize=10)
    axis.set_ylabel("取值")
    axis.grid(alpha=0.3, axis="y")
    return context.save(fig, "test.ttest_boxplot")


def _wilcoxon_hist(context, difference, estimate):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过差值分布直方图。")
        return None
    values = np.asarray(difference, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return None
    bins = min(20, max(5, int(math.sqrt(values.size)) + 1))
    fig, axis = plt.subplots(figsize=(6.2, 4.2))
    axis.hist(values, bins=bins, color="#4f7cff", edgecolor="white")
    axis.axvline(0.0, color="#8a63d2", linestyle="--", linewidth=1.1, label="零差异")
    axis.axvline(
        float(np.median(values)),
        color="#41a36d",
        linestyle="-",
        linewidth=1.1,
        label=f"差值中位数 {float(np.median(values)):.4g}",
    )
    if estimate is not None:
        axis.axvline(
            float(estimate),
            color="#d64545",
            linestyle="-",
            linewidth=1.1,
            label=f"Hodges-Lehmann {float(estimate):.4g}",
        )
    axis.set_xlabel("配对差值")
    axis.set_ylabel("频数")
    axis.set_title("配对差值分布", fontsize=10)
    axis.grid(alpha=0.3, axis="y")
    axis.legend(fontsize=8)
    return context.save(fig, "test.wilcoxon_histogram")


def _friedman_rank_chart(context, rows, kendall, statistic, pvalue):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过平均秩条形图。")
        return None
    if rows.empty:
        return None
    labels = [str(item) for item in rows["treatment"]]
    ranks = rows["mean_rank"].to_numpy(dtype=float)
    fig, axis = plt.subplots(figsize=(max(5.4, 0.7 * len(labels) + 2.4), 4.2))
    bars = axis.bar(labels, ranks, color="#8a63d2")
    for position, bar in enumerate(bars):
        axis.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height(),
            f"{ranks[position]:.2f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    axis.set_ylabel("平均秩（越小越好）")
    axis.set_xlabel("处理")
    title = f"各处理平均秩（χ²={float(statistic):.4g}，p={float(pvalue):.4g}）"
    if kendall is not None:
        title = (
            f"各处理平均秩（χ²={float(statistic):.4g}，p={float(pvalue):.4g}，"
            f"Kendall's W={float(kendall):.3f}）"
        )
    axis.set_title(title, fontsize=10)
    axis.grid(alpha=0.3, axis="y")
    plt.setp(axis.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    return context.save(fig, "test.friedman_ranks")


def _cochran_rate_chart(context, rows, level, ci_label):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过成功率图。")
        return None
    if rows.empty:
        return None
    labels = [str(item) for item in rows["treatment"]]
    rates = rows["rate"].to_numpy(dtype=float) * 100.0
    low = rows["ci_low"].to_numpy(dtype=float)
    high = rows["ci_high"].to_numpy(dtype=float)
    lower = np.where(np.isfinite(low), rates - low * 100.0, 0.0)
    upper = np.where(np.isfinite(high), high * 100.0 - rates, 0.0)
    fig, axis = plt.subplots(figsize=(max(5.4, 0.7 * len(labels) + 2.4), 4.2))
    bars = axis.bar(labels, rates, color="#41a36d")
    axis.errorbar(
        np.arange(len(labels)),
        rates,
        yerr=[lower, upper],
        fmt="none",
        ecolor="#1b2a41",
        capsize=4,
        linewidth=1.0,
    )
    for position, bar in enumerate(bars):
        axis.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height(),
            f"{rates[position]:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    axis.set_ylabel("成功率（%）")
    axis.set_xlabel("处理")
    axis.set_title(f"各处理成功率与 {level:.0%} {ci_label}区间", fontsize=10)
    axis.grid(alpha=0.3, axis="y")
    plt.setp(axis.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    return context.save(fig, "test.cochran_rates")


def _chi2_heatmap(context, observed, expected):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过标准化残差热力图。")
        return None
    expected = np.asarray(expected, dtype=float)
    total = float(observed.to_numpy(dtype=float).sum())
    if total <= 0 or expected.size == 0:
        return None
    residual = (observed.to_numpy(dtype=float) - expected) / np.sqrt(
        np.where(expected > 0, expected, 1.0)
    )
    limit = float(np.nanmax(np.abs(residual))) if residual.size else 1.0
    limit = max(limit, 1e-9)
    fig, axis = plt.subplots(
        figsize=(max(4.6, 0.85 * residual.shape[1] + 2.2), max(3.6, 0.6 * residual.shape[0] + 1.8))
    )
    image = axis.imshow(residual, cmap="RdBu_r", aspect="auto", vmin=-limit, vmax=limit)
    axis.set_xticks(np.arange(residual.shape[1]), labels=[str(item) for item in observed.columns])
    axis.set_yticks(np.arange(residual.shape[0]), labels=[str(item) for item in observed.index])
    for row in range(residual.shape[0]):
        for column in range(residual.shape[1]):
            shade = "#ffffff" if abs(residual[row, column]) > 0.6 * limit else "#1b2a41"
            axis.text(
                column,
                row,
                f"{residual[row, column]:.1f}",
                ha="center",
                va="center",
                fontsize=8,
                color=shade,
            )
    fig.colorbar(image, ax=axis, shrink=0.85)
    axis.set_title("标准化残差（观测−期望）/√期望", fontsize=10)
    plt.setp(axis.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    return context.save(fig, "test.chi2_heatmap")


def _gof_compare_chart(context, rows, statistic, pvalue):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过观测与期望对比图。")
        return None
    if rows.empty:
        return None
    labels = [str(item) for item in rows["category"]]
    observed = rows["observed"].to_numpy(dtype=float)
    expected = rows["expected"].to_numpy(dtype=float)
    positions = np.arange(len(labels), dtype=float)
    width = 0.38
    fig, axis = plt.subplots(figsize=(max(6.0, 0.7 * len(labels) + 2.4), 4.4))
    axis.bar(positions - width / 2.0, observed, width, label="观测频数", color="#4f7cff")
    axis.bar(positions + width / 2.0, expected, width, label="期望频数", color="#f0a35e")
    axis.set_xticks(positions, labels=labels)
    axis.set_ylabel("频数")
    axis.set_title(
        f"观测与期望频数对比（χ²={float(statistic):.4g}，p={float(pvalue):.4g}）", fontsize=10
    )
    axis.grid(alpha=0.3, axis="y")
    axis.legend(fontsize=8)
    plt.setp(axis.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    return context.save(fig, "test.gof_compare")


def _fisher_forest(context, odds, low, high, level, pvalue):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过优势比森林图。")
        return None
    if odds is None or low is None or high is None:
        return None
    if not all(math.isfinite(float(item)) for item in (odds, low, high)):
        return None
    if float(low) <= 0.0 or float(high) <= 0.0 or float(odds) <= 0.0:
        return None
    fig, axis = plt.subplots(figsize=(6.4, 3.0))
    axis.errorbar(
        [float(odds)],
        [1.0],
        xerr=[[float(odds) - float(low)], [float(high) - float(odds)]],
        fmt="o",
        color="#4f7cff",
        capsize=5,
        markersize=7,
    )
    axis.axvline(1.0, color="#d64545", linestyle="--", linewidth=1.1)
    axis.set_xscale("log")
    axis.set_yticks([])
    axis.set_xlabel("优势比（对数刻度）")
    axis.set_title(
        f"优势比 {float(odds):.4g}，{level:.0%} 置信区间 "
        f"[{float(low):.4g}, {float(high):.4g}]，p={float(pvalue):.4g}",
        fontsize=10,
    )
    axis.grid(alpha=0.3, axis="x")
    return context.save(fig, "test.fisher_forest")
