import math

import numpy as np
import pandas as pd

from engine import registry
from engine.registry import MethodError, numbers, register, table_of

EPS = 1e-12


def _binary_values(context, name):
    series = context.table.raw[name]
    if series.isna().any() or series.nunique() != 2:
        raise MethodError(f"列 {name} 必须包含两个非缺失水平，无法推断缺失的处理/时期/选择状态。")
    if pd.api.types.is_numeric_dtype(series) and set(series.unique()) == {0, 1}:
        return series.to_numpy(dtype=float)
    levels = sorted(series.unique(), key=lambda value: str(value))
    note = f"二值列 {name} 的固定映射：{levels[0]}→0，{levels[1]}→1；请核对处理组和处理后时期含义。"
    if note not in context.warnings:
        context.warn(note)
    return series.map({levels[0]: 0.0, levels[1]: 1.0}).to_numpy(dtype=float)


def _binary_column(context, wanted, auto=True):
    table = context.table
    name = context.text(wanted)
    if name:
        if name not in table.raw.columns:
            raise MethodError(
                f"列 {name} 不在数据中。可用列："
                f"{'、'.join(str(item) for item in table.raw.columns[:12])}"
            )
        return name
    if not auto:
        raise MethodError(f"请用 {wanted} 指定要用的列。")
    for candidate in table.raw.columns:
        if table.raw[candidate].nunique(dropna=False) == 2:
            return candidate
    raise MethodError(f"需要一个二值列作为{wanted}，可用 {wanted}=列名 指定。")


def _outcome(context):
    table = context.table
    if table.target_name and not pd.api.types.is_numeric_dtype(table.raw[table.target_name]):
        raise MethodError("因果效应需要真实数值结果，不能将文本标签编码后当作连续响应。")
    target = table.numeric_target()
    if target is None:
        raise MethodError("需要一个数值结果列。")
    return np.asarray(target, dtype=float)


def _series_values(table, name):
    if name not in table.raw.columns:
        raise MethodError(
            f"列 {name} 不在数据中。可用列："
            f"{'、'.join(str(item) for item in table.raw.columns[:12])}"
        )
    values = table.raw[name]
    if pd.api.types.is_numeric_dtype(values):
        array = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    else:
        raise MethodError(f"列 {name} 需要真实数值，不能把文本类别编码成连续变量。")
    if not np.all(np.isfinite(array)):
        raise MethodError(f"列 {name} 含缺失或非有限值，请先明确处理策略。")
    return array


def _cluster_codes(table, column):
    if column not in table.raw.columns:
        raise MethodError(
            f"聚类变量 {column} 不在数据中。可用列："
            f"{'、'.join(str(item) for item in table.raw.columns[:12])}"
        )
    return pd.factorize(table.raw[column], sort=True)[0]


def _prepare_axes():
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    return plt


def _did_subgroup_effects(context, table, outcome, treated, period, groups, column):
    import statsmodels.formula.api as smf

    codes = _binary_values(context, treated)
    times = _binary_values(context, period)
    labels = table.raw[column].astype("string").to_numpy()
    frame = pd.DataFrame({"y": outcome, "treat": codes, "post": times})
    frame["did"] = frame["treat"] * frame["post"]
    frame["subgroup"] = labels
    rows = []
    for level in pd.unique(labels):
        block = frame[frame["subgroup"] == level]
        if block.shape[0] < 6 or block["treat"].nunique() < 2 or block["post"].nunique() < 2:
            continue
        try:
            fitted = smf.ols("y ~ treat + post + did", block).fit()
        except Exception:
            continue
        rows.append(
            {
                "subgroup": str(level),
                "observations": int(block.shape[0]),
                "did_effect": round(float(fitted.params["did"]), 6),
                "std_error": round(float(fitted.bse["did"]), 6),
                "p_value": round(float(fitted.pvalues["did"]), 8),
            }
        )
    if not rows:
        context.warn(f"分组 {column} 的每个水平样本都太少，已跳过分组异质性估计。")
        return None, None
    frame_out = pd.DataFrame(rows)
    spread = float(frame_out["did_effect"].max() - frame_out["did_effect"].min())
    return frame_out, round(spread, 6)


def _did_pretrend_figure(context, cell_means, trend_frame, trend_column, alpha, periods=None):
    plt = _prepare_axes()
    if plt is None:
        context.warn("未安装 matplotlib，跳过平行趋势图。")
        return None
    fig, axis = plt.subplots(figsize=(6.6, 4.6))
    drawn = False
    if trend_frame is not None:
        block = trend_frame
        levels = np.sort(pd.unique(block["trend"]))
        if periods is not None and levels.size > periods:
            levels = levels[-periods:]
            block = block[block["trend"].isin(levels)]
        part = block[block["post"] == 0.0]
        axis.plot(
            part["trend"],
            part["y"],
            linestyle="none",
            marker="o",
            markersize=4,
            color="#8fa8d8",
            alpha=0.7,
            label="政策前观测",
        )
        for group, color, marker in (("对照组", "#4f7cff", "o"), ("处理组", "#e08a3c", "s")):
            series = block[block["treat"] == (0.0 if group == "对照组" else 1.0)]
            means = series.groupby("trend")["y"].mean()
            axis.plot(
                means.index.to_numpy(dtype=float),
                means.to_numpy(dtype=float),
                marker=marker,
                color=color,
                linewidth=1.6,
                label=group,
            )
        axis.set_xlabel(trend_column if trend_column else "时间/政策前后")
        after = np.sort(block.loc[block["post"] > 0.0, "trend"].unique())
        if after.size:
            axis.axvline(
                float(after.min()), color="#d64545", linestyle="--", linewidth=1.2, label="政策时点"
            )
        drawn = True
    if not drawn:
        order = ["政策前", "政策后"]
        for group, color, marker in (("对照组", "#4f7cff", "o"), ("处理组", "#e08a3c", "s")):
            part = (
                cell_means[cell_means["group"] == group]
                .set_index("period")
                .reindex(order)["mean"]
                .to_numpy(dtype=float)
            )
            axis.plot(
                np.arange(len(order)), part, marker=marker, color=color, linewidth=1.6, label=group
            )
        axis.set_xticks(np.arange(len(order)))
        axis.set_xticklabels(order)
        axis.set_xlabel("政策前后")
    axis.set_ylabel("结果均值")
    axis.set_title(f"平行趋势与政策前后均值（显著性水平 {alpha:g}）")
    axis.legend(fontsize=8)
    axis.grid(alpha=0.3)
    suffix = f"_{trend_column}" if trend_column else ""
    return context.save(fig, f"causal_did_pretrend{suffix}")


@register("causal.did")
def did(context):
    import statsmodels.formula.api as smf

    table = context.table
    outcome = _outcome(context)
    treated = _binary_column(context, "treatment_column")
    period = _binary_column(context, "period_column")
    if treated == period:
        raise MethodError("处理组列与时间列不能是同一列。")
    std_error = context.text("std_error", "nonrobust", ("nonrobust", "heteroskedastic", "cluster"))
    cluster_column = context.text("cluster_column")
    trend_column = context.text("trend_column")
    het_column = context.text("heterogeneous_column")
    pretrend = context.flag("pretrend_test", False)
    pretrend_plot = context.flag("pretrend_plot", True)
    pretrend_alpha = (
        context.number("pretrend_alpha", 0.05, 0.001, 0.2) if (pretrend or pretrend_plot) else 0.05
    )

    codes = _binary_values(context, treated)
    times = _binary_values(context, period)
    interaction = codes * times
    frame = pd.DataFrame(
        {
            "y": outcome,
            "treat": codes.astype(float),
            "post": times.astype(float),
            "did": interaction.astype(float),
        }
    )
    control = context.want("columns")
    extra = []
    if control:
        if isinstance(control, str):
            control = [item.strip() for item in control.split(",") if item.strip()]
        matrix = table.matrix()
        for name in control:
            if name not in table.feature_names:
                raise MethodError(f"控制变量 {name} 不在特征中。")
            frame[f"c_{name}"] = matrix[:, table.feature_names.index(name)]
            extra.append(f"c_{name}")

    formula = "y ~ treat + post + did" + ("".join(f" + {name}" for name in extra))
    if trend_column:
        frame["trend"] = _series_values(table, trend_column)
        formula = formula + " + trend + treat:trend"
    cluster_count = None
    groups = None
    if std_error == "cluster":
        if cluster_column:
            groups = _cluster_codes(table, cluster_column)
        else:
            groups = codes * 2 + times
        cluster_count = int(np.unique(groups).size)
        if cluster_count < 10:
            context.warn(f"聚类变量只有 {cluster_count} 个取值，聚类稳健标准误在簇数很少时不可靠。")
    try:
        model = smf.ols(formula, frame)
        if std_error == "cluster":
            fitted = model.fit(cov_type="cluster", cov_kwds={"groups": groups})
        elif std_error == "heteroskedastic":
            fitted = model.fit(cov_type="HC1")
        else:
            fitted = model.fit()
    except Exception as error:
        raise MethodError(f"DID 回归失败：{error}")
    if "did" not in fitted.params.index:
        raise MethodError("模型中缺少交互项，请检查处理组与时间列是否为二值。")

    rows = pd.DataFrame(
        {
            "term": [str(name) for name in fitted.params.index],
            "coefficient": numbers(fitted.params.to_numpy(), 6),
            "std_error": numbers(fitted.bse.to_numpy(), 6),
            "t_value": numbers(fitted.tvalues.to_numpy(), 6),
            "p_value": numbers(fitted.pvalues.to_numpy(), 8),
        }
    )
    cells = frame.groupby(["treat", "post"])["y"].agg(["count", "mean"]).reset_index()
    cells["group"] = cells["treat"].map({0.0: "对照组", 1.0: "处理组"})
    cells["period"] = cells["post"].map({0.0: "政策前", 1.0: "政策后"})
    tables = {
        "coefficients": table_of(rows, limit=40),
        "cell_means": table_of(cells[["group", "period", "count", "mean"]], limit=10),
    }
    pretrend_p = None
    if pretrend:
        if not trend_column:
            context.warn("平行趋势检验需要 trend_column 指定数值型时间或趋势列，已跳过。")
        else:
            before = frame[frame["post"] == 0.0]
            if before.shape[0] < 10:
                context.warn("政策前样本不足 10 条，已跳过平行趋势检验。")
            else:
                try:
                    check = smf.ols("y ~ treat + trend + treat:trend", before).fit()
                except Exception as error:
                    raise MethodError(f"平行趋势检验失败：{error}")
                pretrend_p = float(check.pvalues["treat:trend"])
                tables["pretrend"] = table_of(
                    pd.DataFrame(
                        {
                            "term": ["treat:trend"],
                            "coefficient": numbers([check.params["treat:trend"]], 6),
                            "std_error": numbers([check.bse["treat:trend"]], 6),
                            "p_value": numbers([check.pvalues["treat:trend"]], 8),
                        }
                    )
                )
    spread = None
    if het_column:
        if het_column not in table.raw.columns:
            raise MethodError(
                f"分组异质性列 {het_column} 不在数据中。可用列："
                f"{'、'.join(str(item) for item in table.raw.columns[:12])}"
            )
        subgroup_frame, spread = _did_subgroup_effects(
            context, table, outcome, treated, period, codes * 2 + times, het_column
        )
        if subgroup_frame is not None:
            tables["subgroup_effects"] = table_of(subgroup_frame, limit=30)
    figures = []
    if pretrend_plot:
        trend_frame = pd.DataFrame(
            {
                "treat": frame["treat"],
                "post": frame["post"],
                "trend": frame["trend"] if trend_column else frame["post"],
                "y": frame["y"],
            }
        )
        figure = _did_pretrend_figure(context, cells, trend_frame, trend_column, pretrend_alpha)
        if figure:
            figures.append(figure)
    notes = [
        "DID 的核心假设是平行趋势：若没有政策，两组的差异变化应当一致。",
        "交互项系数就是政策效应；它显著说明处理组在政策后的变化明显不同。",
    ]
    if trend_column:
        notes.append(
            f"已按 {trend_column} 加入组别特定线性趋势 trend 与 treat:trend，"
            "用来吸收两组不同的时间趋势。"
        )
    if std_error == "heteroskedastic":
        notes.append("标准误为异方差稳健（HC1），系数不变但显著性判断更保守。")
    elif std_error == "cluster":
        notes.append(
            f"标准误按 {cluster_column or '处理组×时间单元格'} 聚类，共 {cluster_count} 个簇。"
        )
    if spread is not None:
        notes.append(f"分组 {het_column} 内分别重估 DID，各水平效应极差为 {spread:.6f}。")
    return registry.result(
        "causal.did",
        table,
        metrics={
            "treatment_column": treated,
            "period_column": period,
            "observations": int(fitted.nobs),
            "did_effect": round(float(fitted.params["did"]), 6),
            "did_p_value": round(float(fitted.pvalues["did"]), 8),
            "significant": bool(fitted.pvalues["did"] < 0.05),
            "r_squared": round(float(fitted.rsquared), 6),
            "controls": extra,
            "std_error": std_error,
            "cluster_column": cluster_column,
            "cluster_count": cluster_count,
            "trend_column": trend_column,
            "pretrend_test": bool(pretrend),
            "pretrend_p_value": None if pretrend_p is None else round(pretrend_p, 8),
            "pretrend_significant": None if pretrend_p is None else bool(pretrend_p < 0.05),
            "heterogeneous_column": het_column,
            "subgroup_effect_spread": spread,
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _match_rows(method, treated_p, control_p, ratio, caliper, replace):
    from sklearn.neighbors import NearestNeighbors

    count = treated_p.size
    pool = min(ratio, max(control_p.size, 1))
    if method == "nearest" and replace:
        neighbours = NearestNeighbors(n_neighbors=pool).fit(control_p.reshape(-1, 1))
        distance, position = neighbours.kneighbors(treated_p.reshape(-1, 1))
        positions = np.zeros((count, pool), dtype=int)
        weights = np.zeros((count, pool))
        kept = np.where(distance[:, 0] <= caliper)[0]
        if kept.size:
            positions[kept] = position[kept]
            raw = 1.0 / np.clip(distance[kept], 1e-9, None)
            weights[kept] = raw / raw.sum(axis=1, keepdims=True)
        return positions, weights
    if method == "nearest":
        positions = np.zeros((count, pool), dtype=int)
        weights = np.zeros((count, pool))
        taken = np.zeros(control_p.size, dtype=bool)
        for row in np.argsort(-treated_p):
            available = np.where(~taken)[0]
            if available.size == 0:
                break
            gap = np.abs(control_p[available] - treated_p[row])
            chosen = available[np.argsort(gap)[:pool]]
            if np.abs(control_p[chosen[0]] - treated_p[row]) > caliper:
                continue
            positions[row, : chosen.size] = chosen
            weights[row, : chosen.size] = 1.0 / chosen.size
            taken[chosen] = True
        return positions, weights
    rows = []
    if method == "stratify":
        edges = np.unique(np.quantile(np.concatenate([treated_p, control_p]), [0.2, 0.4, 0.6, 0.8]))
        treated_code = np.digitize(treated_p, edges)
        control_code = np.digitize(control_p, edges)
        for row in range(count):
            members = np.where(control_code == treated_code[row])[0]
            rows.append((members, np.ones(members.size)))
    else:
        neighbours = NearestNeighbors(radius=caliper).fit(control_p.reshape(-1, 1))
        distance, position = neighbours.radius_neighbors(
            treated_p.reshape(-1, 1), sort_results=True
        )
        for row in range(count):
            gap = np.asarray(distance[row], dtype=float)
            members = np.asarray(position[row], dtype=int)
            if method == "kernel" and members.size:
                kernel = (1.0 - np.clip(gap / caliper, 0.0, 1.0) ** 3) ** 3
                keep = kernel > 0.0
                members = members[keep]
                kernel = kernel[keep]
                rows.append((members, kernel))
            else:
                rows.append((members, np.ones(members.size)))
    width = max([members.size for members, _ in rows] + [1])
    positions = np.zeros((count, width), dtype=int)
    weights = np.zeros((count, width))
    for row, (members, kernel) in enumerate(rows):
        if members.size == 0 or kernel.sum() <= 0.0:
            continue
        positions[row, : members.size] = members
        weights[row, : members.size] = kernel / kernel.sum()
    return positions, weights


def _weighted_balance(matrix, treated_ids, control_flat, weight_flat, variance_ratio=False):
    rows = []
    control_matrix = matrix[control_flat] if control_flat.size else np.zeros((0, matrix.shape[1]))
    total_weight = float(weight_flat.sum()) if control_flat.size else 0.0
    for index in range(matrix.shape[1]):
        treated = matrix[treated_ids, index]
        control = control_matrix[:, index] if control_matrix.size else np.zeros(0)
        mean = (
            float(np.sum(control * weight_flat) / max(total_weight, EPS))
            if control.size
            else float("nan")
        )
        pooled = (
            math.sqrt((treated.var(ddof=1) + control.var(ddof=1)) / 2)
            if treated.size > 1 and control.size > 1
            else 0.0
        )
        smd = (treated.mean() - mean) / pooled if pooled > EPS else 0.0
        row = {
            "feature": f"V{index + 1}",
            "treated_mean": round(float(treated.mean()), 6),
            "control_mean": round(float(mean), 6),
            "smd": round(float(smd), 6),
        }
        if variance_ratio:
            share = (weight_flat / max(float(weight_flat.sum()), EPS)) if control.size else None
            control_var = (
                float(np.sum(control**2 * share)) - mean**2 if control.size else float("nan")
            )
            treated_var = float(treated.var(ddof=1)) if treated.size > 1 else float("nan")
            row["variance_ratio"] = (
                None
                if not np.isfinite(control_var) or control_var <= EPS
                else round(treated_var / control_var, 6)
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _matching_matrix(context, exclude=()):
    blocked = {str(name) for name in exclude if name}
    chosen = context.want("columns")
    if chosen:
        names, matrix = registry.subset(context.table, chosen)
        leaked = [name for name in names if name in blocked]
        if leaked:
            keep = [index for index, name in enumerate(names) if name not in blocked]
            if not keep:
                raise MethodError("匹配使用的协变量不能只包含处理组或时间列，请改选别的列。")
            context.warn(
                f"匹配协变量里已剔除 {'、'.join(leaked)}，"
                "否则倾向得分模型会把处理状态或政策时点本身当成特征。"
            )
            return [names[index] for index in keep], matrix[:, keep]
        return names, matrix
    names = [name for name in context.table.feature_names if name not in blocked]
    if not names:
        raise MethodError("匹配使用的协变量为空。")
    return names, context.table.frame[names].to_numpy(dtype=float)


def _balance(matrix, treatment):
    rows = []
    for index in range(matrix.shape[1]):
        treated = matrix[treatment == 1, index]
        control = matrix[treatment == 0, index]
        pooled = (
            math.sqrt((treated.var(ddof=1) + control.var(ddof=1)) / 2)
            if treated.size > 1 and control.size > 1
            else 0.0
        )
        smd = (treated.mean() - control.mean()) / pooled if pooled > EPS else 0.0
        rows.append(
            {
                "feature": f"V{index + 1}",
                "treated_mean": round(float(treated.mean()), 6),
                "control_mean": round(float(control.mean()), 6),
                "smd": round(float(smd), 6),
            }
        )
    return pd.DataFrame(rows)


def _smd_plot(context, before, after):
    plt = _prepare_axes()
    if plt is None:
        context.warn("未安装 matplotlib，跳过 SMD 平衡对比图。")
        return None
    count = min(len(before), len(after))
    if count == 0:
        return None
    index = np.arange(count)
    width = 0.4
    fig, axis = plt.subplots(figsize=(6.6, 4.6))
    axis.barh(
        index - width / 2,
        before["smd"].abs().to_numpy(dtype=float)[:count],
        height=width,
        color="#e08a3c",
        label="匹配前",
    )
    axis.barh(
        index + width / 2,
        after["smd"].abs().to_numpy(dtype=float)[:count],
        height=width,
        color="#4f7cff",
        label="匹配后",
    )
    axis.axvline(0.1, color="#d64545", linestyle="--", linewidth=1.2, label="0.1 参考线")
    axis.set_yticks(index)
    axis.set_yticklabels([str(name) for name in before["feature"].to_numpy()[:count]], fontsize=8)
    axis.invert_yaxis()
    axis.set_xlabel("标准化均值差 |SMD|")
    axis.set_title("匹配前后协变量平衡")
    axis.legend(fontsize=8)
    axis.grid(alpha=0.3, axis="x")
    return context.save(fig, "causal_psm_smd")


def _overlap_plot(context, treated_p, control_p):
    plt = _prepare_axes()
    if plt is None:
        context.warn("未安装 matplotlib，跳过倾向得分重叠图。")
        return None
    fig, axis = plt.subplots(figsize=(6.6, 4.4))
    bins = np.linspace(0.0, 1.0, 21)
    axis.hist(control_p, bins=bins, alpha=0.6, color="#4f7cff", label="对照组")
    axis.hist(treated_p, bins=bins, alpha=0.6, color="#e08a3c", label="处理组")
    axis.set_xlabel("倾向得分")
    axis.set_ylabel("频数")
    axis.set_title("倾向得分重叠与共同支撑域")
    axis.legend(fontsize=8)
    axis.grid(alpha=0.3, axis="y")
    return context.save(fig, "causal_psm_overlap")


def _variance_plot(context, matrix, treated_index, control_flat, weight_flat):
    plt = _prepare_axes()
    if plt is None:
        context.warn("未安装 matplotlib，跳过方差比诊断图。")
        return None
    treated = matrix[treated_index]
    if control_flat.size == 0:
        return None
    weight = weight_flat / max(float(weight_flat.sum()), EPS)
    control = matrix[control_flat]
    treated_var = treated.var(axis=0, ddof=1)
    control_var = (control**2).T @ weight - ((control.T @ weight) ** 2)
    ratio = treated_var / np.where(control_var <= EPS, 1.0, control_var)
    index = np.arange(ratio.size)
    fig, axis = plt.subplots(figsize=(6.6, 4.4))
    axis.scatter(index, ratio, s=42, color="#4f7cff")
    axis.axhline(1.0, color="#2f9e6b", linewidth=1.2, label="方差比 = 1")
    axis.axhline(2.0, color="#d64545", linestyle="--", linewidth=1.1, label="2 倍参考线")
    axis.axhline(0.5, color="#d64545", linestyle="--", linewidth=1.1)
    axis.set_xticks(index)
    axis.set_xticklabels([f"V{item + 1}" for item in index], fontsize=8)
    axis.set_xlabel("协变量")
    axis.set_ylabel("处理组/对照组方差比")
    axis.set_title("匹配后方差比诊断")
    axis.legend(fontsize=8)
    axis.grid(alpha=0.3)
    return context.save(fig, "causal_psm_variance_ratio")


@register("causal.psm")
def psm(context):
    from scipy import stats as sps
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import NearestNeighbors

    table = context.table
    treatment_column = _binary_column(context, "treatment_column")
    treatment = _binary_values(context, treatment_column)
    names, matrix = _matching_matrix(context, (treatment_column,))
    if len(set(treatment)) != 2:
        raise MethodError("处理组列必须是二值。")
    if min(np.bincount(treatment.astype(int))) < 3:
        raise MethodError("两组都需要至少 3 个样本。")
    ratio = context.whole("neighbours", 1, 1, 10)
    smd_threshold = context.number("smd_threshold", 0.1, 0.01, 1.0)
    method = context.text("match_method", "nearest", ("nearest", "radius", "kernel", "stratify"))
    replace = context.flag("replace", True)
    trim = context.number("trim", 0.0, 0.0, 0.4)
    want_ratio = context.flag("variance_ratio", False)
    want_smd_plot = context.flag("balance_plot", True)
    want_overlap = context.flag("overlap_plot", True)
    want_variance_plot = context.flag("variance_plot", False)

    scaled, _, _ = registry.standardize(matrix)
    model = LogisticRegression(max_iter=2000)
    model.fit(scaled, treatment)
    propensity = model.predict_proba(scaled)[:, 1]

    treated_index = np.where(treatment == 1)[0]
    control_index = np.where(treatment == 0)[0]
    if treated_index.size == 0 or control_index.size == 0:
        raise MethodError("处理组或对照组为空。")
    if trim > 0:
        support = (propensity >= trim) & (propensity <= 1.0 - trim)
        removed = int(support.size - support.sum())
        treated_index = treated_index[support[treated_index]]
        control_index = control_index[support[control_index]]
        if treated_index.size < 3 or control_index.size < 3:
            raise MethodError(
                f"trim={trim} 修剪后处理组 {treated_index.size} 个、"
                f"对照组 {control_index.size} 个，样本不足，请减小 trim。"
            )
        context.warn(f"共同支撑域修剪 trim={trim} 去掉了 {removed} 个倾向得分落在两端的样本。")

    treated_p = propensity[treated_index]
    control_p = propensity[control_index]
    pool = min(ratio, control_index.size)
    caliper = context.number("caliper")
    nearest = NearestNeighbors(n_neighbors=1).fit(control_p.reshape(-1, 1))
    gap_all = nearest.kneighbors(treated_p.reshape(-1, 1))[0].ravel()
    if method == "stratify":
        caliper = None
    elif caliper is None:
        caliper = max(float(np.percentile(gap_all, 90)), 1e-4)
        context.warn(f"未指定 caliper，已按最近邻距离的 90 百分位取 {caliper:.4f}。")
    elif caliper <= 0:
        raise MethodError("caliper 必须为正数。")

    positions, weights = _match_rows(
        method, treated_p, control_p, ratio, caliper if caliper else 1.0, replace
    )
    widths = (weights > 0).sum(axis=1)
    matched = np.where(widths > 0)[0]
    shown = "未使用（分层匹配）" if caliper is None else f"{caliper:.4f}"
    if matched.size < 3:
        raise MethodError(
            f"{method} 匹配（caliper={shown}）下只匹配到 {matched.size} 对，"
            f"最近邻距离中位数约 {np.median(gap_all):.4f}，请放宽 caliper 或减少匹配特征。"
        )
    matched_treated = treated_index[matched]
    matched_positions = positions[matched]
    matched_weights = weights[matched]
    row_widths = widths[matched]
    used = matched_weights > 0
    control_flat = control_index[matched_positions[used]]
    weight_flat = matched_weights[used]
    rows_index = np.repeat(np.arange(matched.size), row_widths)
    gap_flat = np.abs(propensity[control_flat] - np.repeat(treated_p[matched], row_widths))
    minimum = np.full(matched.size, np.inf)
    np.minimum.at(minimum, rows_index, gap_flat)

    outcome = _outcome(context)
    if method == "nearest" and replace and pool == 1:
        effect = float(outcome[matched_treated].mean() - outcome[control_flat].mean())
        statistic, pvalue = sps.ttest_ind(
            outcome[matched_treated], outcome[control_flat], equal_var=False
        )
        counterfactual = outcome[control_flat]
    else:
        counterfactual = np.bincount(
            rows_index, weights=outcome[control_flat] * weight_flat, minlength=matched.size
        )
        effect = float((outcome[matched_treated] - counterfactual).mean())
        statistic, pvalue = sps.ttest_1samp(outcome[matched_treated] - counterfactual, 0.0)

    before = _balance(matrix, treatment)
    after = (
        _weighted_balance(matrix, matched_treated, control_flat, weight_flat, want_ratio)
        if matched_treated.size
        else pd.DataFrame(columns=["feature", "smd"])
    )
    frame_after = pd.DataFrame(after)
    imbalanced = int((frame_after["smd"].abs() > smd_threshold).sum()) if len(frame_after) else 0
    ratio_after = None
    if want_ratio and len(frame_after) and "variance_ratio" in frame_after.columns:
        ratio_after = numbers(frame_after["variance_ratio"].to_numpy(dtype=float), 6)
    if method == "nearest":
        method_note = f"用最近的 {pool} 个对照作为反事实"
    elif method == "radius":
        method_note = f"用卡钳 {caliper:.4f} 半径内的全部对照加权作为反事实"
    elif method == "kernel":
        method_note = f"用三次核在带宽 {caliper:.4f} 内对全部对照加权作为反事实"
    else:
        method_note = "按倾向得分五分位分层，用同层对照的均值作为反事实"
    notes = [
        f"ATT 是处理组的平均处理效应，{method_note}"
        + ("（按倾向得分距离加权）。" if pool > 1 and method == "nearest" else "。"),
        f"标准化均值差 SMD 的绝对值小于 {smd_threshold} 认为匹配后已平衡；"
        f"当前有 {imbalanced} 个协变量仍超过该阈值。",
    ]
    if want_ratio:
        notes.append(
            "方差比是处理组与对照组协变量方差之比，理想值接近 1，"
            "偏离 2 或 0.5 说明匹配后两组离散程度仍不同。"
        )
    if not replace and method == "nearest":
        notes.append("已禁用有放回匹配，每个对照最多被一个处理个体使用。")
    if trim > 0:
        notes.append(f"匹配前按 trim={trim} 修剪了共同支撑域，倾向得分两端的样本不参与匹配。")
    figures = []
    if want_smd_plot and len(frame_after):
        figure = _smd_plot(context, pd.DataFrame(before), frame_after)
        if figure:
            figures.append(figure)
    if want_overlap:
        figure = _overlap_plot(context, treated_p, control_p)
        if figure:
            figures.append(figure)
    if want_variance_plot:
        figure = _variance_plot(context, matrix, matched_treated, control_flat, weight_flat)
        if figure:
            figures.append(figure)
    return registry.result(
        "causal.psm",
        table,
        metrics={
            "treatment_column": treatment_column,
            "neighbours": pool,
            "matched_features": len(names),
            "treated": int((treatment == 1).sum()),
            "control": int((treatment == 0).sum()),
            "matched_pairs": int(matched_treated.size),
            "caliper": caliper,
            "att_effect": round(effect, 6),
            "t_statistic": round(float(statistic), 6),
            "p_value": round(float(pvalue), 8),
            "significant": bool(pvalue < 0.05),
            "smd_threshold": smd_threshold,
            "imbalanced_after": imbalanced,
            "variance_ratio": bool(want_ratio),
            "variance_ratio_after": ratio_after,
            "match_method": method,
            "replace": bool(replace),
            "trim": trim,
            "matched_controls": int(control_flat.size),
            "mean_propensity_gap": round(float(minimum.mean()), 6) if minimum.size else None,
        },
        tables={
            "balance_before": table_of(before, limit=40),
            "balance_after": table_of(after, limit=40),
        },
        figures=figures,
        notes=notes,
    )


def _kernel_weights(centred, bandwidth, kernel):
    scaled = np.clip(np.abs(centred) / max(bandwidth, EPS), 0.0, 1.0)
    if kernel == "triangular":
        return 1.0 - scaled
    if kernel == "epanechnikov":
        return 0.75 * (1.0 - scaled**2)
    return np.ones(centred.size)


def _local_formula(degree):
    if degree == "quadratic":
        return "y ~ x + x2 + above + interaction + interaction2"
    return "y ~ x + above + interaction"


def _cv_bandwidth(score, outcome, cutoff, degree, grid=19, minimum=10):
    import statsmodels.formula.api as smf

    spread = float(score.max() - score.min())
    if spread <= EPS:
        raise MethodError("驱动变量没有变化，无法用交叉验证选择带宽。")
    formula = _local_formula(degree)
    best = None
    best_error = None
    for candidate in np.linspace(0.05, 0.95, int(grid)) * spread:
        mask = np.abs(score - cutoff) <= candidate
        if mask.sum() < minimum:
            continue
        centred = score[mask] - cutoff
        above = (centred >= 0).astype(float)
        frame = pd.DataFrame(
            {
                "y": outcome[mask],
                "x": centred,
                "above": above,
                "interaction": centred * above,
                "x2": centred**2,
                "interaction2": (centred**2) * above,
            }
        )
        try:
            fitted = smf.ols(formula, frame).fit()
            hat = fitted.get_influence().hat_matrix_diag
            error = float(np.mean((fitted.resid / np.clip(1.0 - hat, 1e-6, None)) ** 2))
        except Exception:
            continue
        if best_error is None or error < best_error:
            best_error = error
            best = float(candidate)
    if best is None:
        raise MethodError("交叉验证没有找到可用带宽，请手动指定 bandwidth。")
    return best


def _cutoff_figure(context, centred, values, cutoff, bandwidth, fitted, weights):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过断点图。")
        return None
    fig, axis = plt.subplots(figsize=(6.5, 4.5))
    axis.scatter(centred + cutoff, values, s=14, color="#aab8d0", alpha=0.75)
    params = fitted.params
    grid = np.linspace(-bandwidth, bandwidth, 80)

    def predict(point, side):
        total = float(params["Intercept"]) + float(params["x"]) * point
        if "x2" in params.index:
            total += float(params["x2"]) * point**2
        if side:
            total += float(params["above"]) + float(params["interaction"]) * point
            if "interaction2" in params.index:
                total += float(params["interaction2"]) * point**2
        return total

    left = grid[grid < 0.0]
    right = grid[grid >= 0.0]
    axis.plot(
        left + cutoff, [predict(point, False) for point in left], color="#4f7cff", linewidth=1.8
    )
    axis.plot(
        right + cutoff, [predict(point, True) for point in right], color="#e08a3c", linewidth=1.8
    )
    axis.axvline(cutoff, color="#d64545", linestyle="--", linewidth=1.2)
    axis.set_xlabel("驱动变量")
    axis.set_ylabel("结果")
    axis.set_title("断点两侧的局部拟合")
    axis.grid(alpha=0.3)
    return context.save(fig, "causal_rd_cutoff")


@register("causal.rd")
def regression_discontinuity(context):
    import statsmodels.formula.api as smf

    table = context.table
    running = context.text("running_column")
    if not running or running not in table.feature_names:
        running = table.feature_names[0]
    cutoff = context.number("cutoff")
    outcome = _outcome(context)
    if running not in table.feature_names:
        raise MethodError(f"驱动变量 {running} 不在特征中。")
    score = table.matrix()[:, table.feature_names.index(running)]
    if cutoff is None:
        cutoff = float(np.median(score))
        context.warn(f"未指定 cutoff，已取驱动变量的中位数 {cutoff:.4f}。")
    bandwidth = context.number("bandwidth")
    if bandwidth is None:
        bandwidth = float((score.max() - score.min()) * 0.5)
        context.warn(f"未指定 bandwidth，已取全距的一半 {bandwidth:.4f}。")

    method = context.text("bandwidth_method", "fixed", ("fixed", "cv"))
    kernel = context.text("kernel", "uniform", ("uniform", "triangular", "epanechnikov"))
    degree = context.text("polynomial", "linear", ("linear", "quadratic"))
    compare = context.flag("compare_orders", False)
    plot = context.flag("cutoff_plot", False)
    grid = context.whole("bandwidth_grid", 19, 5, 60)
    minimum = context.whole("min_bandwidth_n", 10, 5, 200)
    simulations = context.whole("simulations", 0, 0, 2000)
    simulation_seed = 42
    if method == "cv":
        bandwidth = _cv_bandwidth(score, outcome, cutoff, degree, grid, minimum)
        context.warn(f"已按留一交叉验证选择带宽 {bandwidth:.4f}。")

    inside = np.abs(score - cutoff) <= bandwidth
    if inside.sum() < minimum:
        raise MethodError(
            f"带宽 {bandwidth:.4f} 内只有 {inside.sum()} 个样本，"
            f"少于要求的 {minimum} 个，请放宽带宽或降低 min_bandwidth_n。"
        )
    centred = score[inside] - cutoff
    above = (centred >= 0).astype(float)
    frame = pd.DataFrame(
        {
            "y": outcome[inside],
            "x": centred,
            "above": above,
            "interaction": centred * above,
            "x2": centred**2,
            "interaction2": (centred**2) * above,
        }
    )
    weights = _kernel_weights(centred, bandwidth, kernel)
    labels = {"linear": "局部线性（含斜率变化）", "quadratic": "局部二次（含曲率与斜率变化）"}
    try:
        if kernel == "uniform":
            fitted = smf.ols(_local_formula(degree), frame).fit()
            local = smf.ols("y ~ above", frame).fit()
        else:
            fitted = smf.wls(_local_formula(degree), frame, weights=weights).fit()
            local = smf.wls("y ~ above", frame, weights=weights).fit()
    except Exception as error:
        raise MethodError(f"断点回归拟合失败：{error}")

    entries = [
        {
            "model": labels[degree],
            "effect": round(float(fitted.params["above"]), 6),
            "std_error": round(float(fitted.bse["above"]), 6),
            "p_value": round(float(fitted.pvalues["above"]), 8),
        }
    ]
    if compare:
        other = "quadratic" if degree == "linear" else "linear"
        try:
            alternative = (
                smf.ols(_local_formula(other), frame).fit()
                if kernel == "uniform"
                else smf.wls(_local_formula(other), frame, weights=weights).fit()
            )
        except Exception as error:
            raise MethodError(f"另一种阶数的断点回归拟合失败：{error}")
        entries.append(
            {
                "model": labels[other],
                "effect": round(float(alternative.params["above"]), 6),
                "std_error": round(float(alternative.bse["above"]), 6),
                "p_value": round(float(alternative.pvalues["above"]), 8),
            }
        )
    entries.append(
        {
            "model": "局部均值差",
            "effect": round(float(local.params["above"]), 6),
            "std_error": round(float(local.bse["above"]), 6),
            "p_value": round(float(local.pvalues["above"]), 8),
        }
    )
    rows = pd.DataFrame(entries)
    interval = None
    if simulations > 0:
        rng = np.random.default_rng(simulation_seed)
        base = frame["y"].to_numpy(dtype=float)
        residual = np.asarray(fitted.resid, dtype=float)
        centre = float(base.mean())
        draws = np.zeros(simulations)
        valid = 0
        for index in range(simulations):
            frame["y"] = centre + rng.permutation(residual)
            try:
                if kernel == "uniform":
                    draw = smf.ols(_local_formula(degree), frame).fit()
                else:
                    draw = smf.wls(_local_formula(degree), frame, weights=weights).fit()
                draws[valid] = float(draw.params["above"])
                valid += 1
            except Exception:
                continue
        if valid >= 10:
            draws = draws[:valid]
            interval = {
                "lower": round(float(np.percentile(draws, 2.5)), 6),
                "upper": round(float(np.percentile(draws, 97.5)), 6),
                "mean": round(float(draws.mean()), 6),
                "std": round(float(draws.std(ddof=1)), 6),
                "rounds": int(valid),
            }
        else:
            context.warn("断点效应模拟的有效轮次不足，已跳过区间估计。")
    figures = []
    if plot:
        figure = _cutoff_figure(
            context, centred, outcome[inside], cutoff, bandwidth, fitted, weights
        )
        if figure:
            figures.append(figure)
    notes = [
        "断点回归假定个体无法精确操纵驱动变量，阈值附近近似随机。",
        "带宽越小越接近局部随机，但样本量也随之减少。",
    ]
    if kernel != "uniform":
        notes.append(f"核函数为 {kernel}，带宽内样本按到断点的距离加权。")
    if method == "cv":
        notes.append("带宽由留一交叉验证在观测范围内选出，兼顾偏差与方差。")
    if interval is not None:
        notes.append(
            f"断点效应区间由 {interval['rounds']} 轮残差重排模拟得到"
            f"（95% 区间 {interval['lower']}~{interval['upper']}），"
            "只反映带宽内样本的抽样波动。"
        )
    return registry.result(
        "causal.rd",
        table,
        metrics={
            "running_column": running,
            "cutoff": round(cutoff, 6),
            "bandwidth": round(bandwidth, 6),
            "polynomial": degree,
            "observations": int(inside.sum()),
            "above_cutoff": int(above.sum()),
            "below_cutoff": int((1 - above).sum()),
            "local_linear_effect": round(float(fitted.params["above"]), 6),
            "local_linear_p": round(float(fitted.pvalues["above"]), 8),
            "mean_difference_effect": round(float(local.params["above"]), 6),
            "mean_difference_p": round(float(local.pvalues["above"]), 8),
            "significant": bool(fitted.pvalues["above"] < 0.05),
            "kernel": kernel,
            "bandwidth_method": method,
            "bandwidth_grid": grid,
            "min_bandwidth_n": minimum,
            "simulations": int(simulations),
            "simulated_interval": interval,
            "compare_orders": bool(compare),
        },
        tables={"effects": table_of(rows)},
        figures=figures,
        notes=notes,
    )


def _numeric_hessian(function, point, step=1e-4):
    size = point.size
    hessian = np.zeros((size, size))
    for left in range(size):
        for right in range(left, size):
            first = np.zeros(size)
            second = np.zeros(size)
            first[left] = step
            second[right] = step
            value = (
                function(point + first + second)
                - function(point + first - second)
                - function(point - first + second)
                + function(point - first - second)
            )
            hessian[left, right] = hessian[right, left] = value / (4.0 * step * step)
    return hessian


def _selection_figure(context, index, inverse_mills, observed):
    plt = _prepare_axes()
    if plt is None:
        context.warn("未安装 matplotlib，跳过选择方程图。")
        return None
    from scipy import stats as sps

    probability = np.clip(sps.norm.cdf(index), 1e-6, 1.0)
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.2))
    axes[0].hist(probability[observed], bins=18, alpha=0.65, color="#e08a3c", label="被选中")
    axes[0].hist(probability[~observed], bins=18, alpha=0.65, color="#4f7cff", label="未被选中")
    axes[0].set_xlabel("选择方程预测概率")
    axes[0].set_ylabel("频数")
    axes[0].set_title("选择方程拟合概率分布")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3, axis="y")
    order = np.argsort(index)
    axes[1].plot(index[order], inverse_mills[order], color="#4f7cff", linewidth=1.6)
    axes[1].scatter(index, inverse_mills, s=14, color="#e08a3c", alpha=0.7)
    axes[1].set_xlabel("选择方程线性指数")
    axes[1].set_ylabel("逆米尔斯比 λ")
    axes[1].set_title("逆米尔斯比与选择指数")
    axes[1].grid(alpha=0.3)
    return context.save(fig, "causal_heckman_selection")


@register("causal.heckman")
def heckman(context):
    import statsmodels.api as sm
    from scipy import stats as sps

    table = context.table
    selection_column = _binary_column(context, "selection_column")
    selected = _binary_values(context, selection_column)
    outcome = _outcome(context)
    names, raw = registry.subset(table, context.want("columns"))
    keep_features = [
        index
        for index, name in enumerate(names)
        if name != selection_column and not name.startswith(selection_column + "=")
    ]
    names = [names[index] for index in keep_features]
    raw = raw[:, keep_features]
    if not names:
        raise MethodError("选择标志不能同时作为其自身方程的预测变量，请指定有效协变量。")
    if not np.isfinite(outcome[selected == 1]).all():
        raise MethodError("被选中样本的结果缺失；Heckman 只允许未选中样本缺失结果。")
    matrix, _, _ = registry.standardize(raw)
    exclusive = context.want("exclusive_columns")
    if isinstance(exclusive, str):
        exclusive = [item.strip() for item in exclusive.split(",") if item.strip()]
    exclusive_names = []
    if exclusive:
        exclusive_names, exclusive_raw = registry.subset(table, exclusive)
        remaining = [index for index, name in enumerate(names) if name not in set(exclusive_names)]
        if not remaining:
            raise MethodError("结果方程至少需要一个协变量，排他性约束变量不能把结果方程清空。")
        matrix = matrix[:, remaining]
        names = [names[index] for index in remaining]
        exclusive_matrix, _, _ = registry.standardize(exclusive_raw)
        design = sm.add_constant(np.column_stack([matrix, exclusive_matrix]), has_constant="add")
    else:
        design = sm.add_constant(matrix, has_constant="add")
    link = context.text("selection_link", "probit", ("probit", "logit"))
    estimator = context.text("estimator", "two_step", ("two_step", "mle"))
    std_error = context.text("std_error", "nonrobust", ("nonrobust", "heteroskedastic"))
    want_selection = context.flag("selection_table", False)
    selection_plot = context.flag("selection_plot", True)

    if link == "logit":
        model = sm.Logit(selected, design)
    else:
        model = sm.Probit(selected, design)
    try:
        selection_fit = model.fit(disp=False, maxiter=200)
    except Exception as error:
        raise MethodError(f"选择方程拟合失败：{error}")
    if not selection_fit.mle_retvals.get("converged", True):
        context.warn("选择方程未完全收敛，逆米尔斯比可能不稳定。")
    index = np.clip(design @ selection_fit.params, -6.0, 6.0)
    density = sps.norm.pdf(index)
    cdf = np.clip(sps.norm.cdf(index), 0.01, 1.0)
    inverse_mills = density / cdf

    observed = selected == 1
    if observed.sum() < 10:
        raise MethodError("被选中的样本太少，无法估计结果方程。")
    selection_rows = pd.DataFrame(
        {
            "term": ["常数项"] + list(names) + list(exclusive_names),
            "coefficient": numbers(selection_fit.params, 6),
            "std_error": numbers(selection_fit.bse, 6),
            "t_value": numbers(selection_fit.tvalues, 6),
            "p_value": numbers(selection_fit.pvalues, 8),
        }
    )

    design_plain = sm.add_constant(matrix[observed], has_constant="add")
    plain = sm.OLS(outcome[observed], design_plain).fit()
    covariates = len(names)
    selection_covariates = len(names) + len(exclusive_names)
    if estimator == "mle":
        if link != "probit":
            raise MethodError(
                "极大似然估计目前只支持 probit 选择方程，请把 selection_link 设为 probit。"
            )
        from scipy.optimize import minimize

        full_design = sm.add_constant(matrix, has_constant="add")
        width = full_design.shape[1]
        depth = design.shape[1]
        start = np.concatenate(
            [
                np.asarray(plain.params, dtype=float),
                np.asarray(selection_fit.params, dtype=float),
                [0.0, math.atanh(0.2)],
            ]
        )

        def negative(theta):
            beta = theta[:width]
            gamma = theta[width : width + depth]
            sigma = math.exp(float(np.clip(theta[width + depth], -8.0, 8.0)))
            rho = math.tanh(float(theta[width + depth + 1]))
            latent = design @ gamma
            total = float(np.sum(np.log(np.clip(sps.norm.cdf(-latent[~observed]), 1e-300, None))))
            residual = (outcome[observed] - full_design[observed] @ beta) / sigma
            shifted = (latent[observed] + rho * residual) / math.sqrt(1.0 - rho**2)
            total += float(np.sum(np.log(np.clip(sps.norm.cdf(shifted), 1e-300, None))))
            total += float(np.sum(sps.norm.logpdf(residual))) - observed.sum() * math.log(sigma)
            return -total

        best = minimize(negative, start, method="L-BFGS-B", options={"maxiter": 1000})
        if not best.success and not np.isfinite(best.fun):
            raise MethodError(f"极大似然估计未收敛：{best.message}")
        beta = best.x[:width]
        gamma = best.x[width : width + depth]
        sigma = math.exp(float(np.clip(best.x[width + depth], -8.0, 8.0)))
        rho = math.tanh(float(best.x[width + depth + 1]))
        errors = np.full(best.x.size, np.nan)
        try:
            covariance = np.linalg.pinv(_numeric_hessian(negative, best.x))
            errors = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
        except Exception:
            context.warn("极大似然估计的数值海森矩阵不可用，标准误留空。")
        coefficients = np.concatenate([beta, [rho * sigma]])
        standard = np.concatenate([errors[:width], [errors[width + depth]]])
        with np.errstate(divide="ignore", invalid="ignore"):
            statistics = coefficients / standard
        rows = pd.DataFrame(
            {
                "term": ["常数项"] + list(names) + ["逆米尔斯比 λ"],
                "coefficient": numbers(coefficients, 6),
                "std_error": numbers(standard, 6),
                "t_value": numbers(statistics, 6),
                "p_value": numbers(2.0 * sps.norm.sf(np.abs(statistics)), 8),
            }
        )
        selection_rows = pd.DataFrame(
            {
                "term": ["常数项"] + list(names) + list(exclusive_names),
                "coefficient": numbers(gamma, 6),
                "std_error": numbers(errors[width : width + depth], 6),
                "t_value": numbers(
                    np.divide(
                        gamma,
                        errors[width : width + depth],
                        out=np.full(depth, np.nan),
                        where=errors[width : width + depth] > 0.0,
                    ),
                    6,
                ),
                "p_value": numbers(
                    2.0
                    * sps.norm.sf(
                        np.abs(
                            np.divide(
                                gamma,
                                errors[width : width + depth],
                                out=np.full(depth, np.nan),
                                where=errors[width : width + depth] > 0.0,
                            )
                        )
                    ),
                    8,
                ),
            }
        )
        prediction = full_design[observed] @ beta
        residual = outcome[observed] - prediction
        total = outcome[observed] - outcome[observed].mean()
        r_squared = float(1.0 - np.sum(residual**2) / max(float(np.sum(total**2)), EPS))
        lambda_value = float(rho * sigma)
        lambda_p = float(
            2.0 * sps.norm.sf(abs(lambda_value / max(float(errors[width + depth]), EPS)))
        )
        tables = {"outcome_equation": table_of(rows, limit=40)}
        if want_selection:
            tables["selection_equation"] = table_of(selection_rows, limit=40)
        figures = []
        if selection_plot:
            figure = _selection_figure(context, index, inverse_mills, observed)
            if figure:
                figures.append(figure)
        notes = [
            "逆米尔斯比 λ 显著说明存在样本选择偏误，普通回归会有偏。",
            "选择方程需要至少一个只影响“是否被选中”的变量，否则识别依赖函数形式。",
            f"结果由极大似然联合估计得到：σ={sigma:.4f}、ρ={rho:.4f}、λ=ρσ={lambda_value:.4f}。",
        ]
        if exclusive_names:
            notes.append(
                f"排他性约束变量 {', '.join(exclusive_names)} 只进入选择方程，"
                "为识别提供了额外的外生变动。"
            )
        return registry.result(
            "causal.heckman",
            table,
            metrics={
                "selection_column": selection_column,
                "selected": int(observed.sum()),
                "total": int(selected.size),
                "covariates": covariates,
                "selection_covariates": selection_covariates,
                "lambda": round(lambda_value, 6),
                "lambda_p_value": round(lambda_p, 8),
                "selection_bias": bool(lambda_p < 0.05),
                "r_squared_with_lambda": round(r_squared, 6),
                "r_squared_without_lambda": round(float(plain.rsquared), 6),
                "estimator": "mle",
                "selection_link": link,
                "std_error": std_error,
                "exclusive_columns": exclusive_names,
                "sigma": round(sigma, 6),
                "rho": round(rho, 6),
                "log_likelihood": round(float(-best.fun), 6),
            },
            tables=tables,
            notes=notes,
        )

    design2 = sm.add_constant(
        np.column_stack([matrix[observed], inverse_mills[observed]]), has_constant="add"
    )
    try:
        if std_error == "heteroskedastic":
            fitted = sm.OLS(outcome[observed], design2).fit(cov_type="HC1")
        else:
            fitted = sm.OLS(outcome[observed], design2).fit()
    except Exception as error:
        raise MethodError(f"结果方程拟合失败：{error}")
    rows = pd.DataFrame(
        {
            "term": ["常数项"] + list(names) + ["逆米尔斯比 λ"],
            "coefficient": numbers(fitted.params, 6),
            "std_error": numbers(fitted.bse, 6),
            "t_value": numbers(fitted.tvalues, 6),
            "p_value": numbers(fitted.pvalues, 8),
        }
    )
    lambda_value = float(fitted.params[-1])
    lambda_p = float(fitted.pvalues[-1])
    tables = {"outcome_equation": table_of(rows, limit=40)}
    if want_selection:
        tables["selection_equation"] = table_of(selection_rows, limit=40)
    figures = []
    if selection_plot:
        figure = _selection_figure(context, index, inverse_mills, observed)
        if figure:
            figures.append(figure)
    notes = [
        "逆米尔斯比 λ 显著说明存在样本选择偏误，普通回归会有偏。",
        "选择方程需要至少一个只影响“是否被选中”的变量，否则识别依赖函数形式。",
    ]
    if exclusive_names:
        notes.append(
            f"排他性约束变量 {', '.join(exclusive_names)} 只进入选择方程，"
            "为识别提供了额外的外生变动。"
        )
    if std_error == "heteroskedastic":
        notes.append("结果方程标准误为异方差稳健（HC1）。")
    if link == "logit":
        notes.append("选择方程使用 logit 连接函数，逆米尔斯比按正态密度与累积分布之比近似。")
    return registry.result(
        "causal.heckman",
        table,
        metrics={
            "selection_column": selection_column,
            "selected": int(observed.sum()),
            "total": int(selected.size),
            "covariates": covariates,
            "selection_covariates": selection_covariates,
            "lambda": round(lambda_value, 6),
            "lambda_p_value": round(lambda_p, 8),
            "selection_bias": bool(lambda_p < 0.05),
            "r_squared_with_lambda": round(float(fitted.rsquared), 6),
            "r_squared_without_lambda": round(float(plain.rsquared), 6),
            "estimator": "two_step",
            "selection_link": link,
            "std_error": std_error,
            "exclusive_columns": exclusive_names,
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("causal.psmdid")
def psm_did(context):
    import statsmodels.formula.api as smf
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import NearestNeighbors

    table = context.table
    treatment_column = _binary_column(context, "treatment_column")
    period_column = _binary_column(context, "period_column")
    if treatment_column == period_column:
        raise MethodError("处理组列与时间列不能是同一列。")
    treatment = _binary_values(context, treatment_column)
    period = _binary_values(context, period_column)
    trend_column = context.text("trend_column")
    pretrend_plot = context.flag("pretrend_plot", True)
    outcome = _outcome(context)
    names, matrix = _matching_matrix(context, (treatment_column, period_column))
    smd_threshold = context.number("smd_threshold", 0.1, 0.01, 1.0)
    ratio = context.whole("neighbours", 1, 1, 10)
    std_error = context.text("std_error", "nonrobust", ("nonrobust", "heteroskedastic", "cluster"))
    trim = context.number("trim", 0.0, 0.0, 0.4)

    baseline = period == 0
    if baseline.sum() < 10:
        raise MethodError("政策前的样本太少，无法估计倾向得分。")
    scaled, _, _ = registry.standardize(matrix[baseline])
    model = LogisticRegression(max_iter=2000)
    model.fit(scaled, treatment[baseline])
    propensity = model.predict_proba(scaled)[:, 1]

    base_index = np.where(baseline)[0]
    base_treated = np.where(treatment[base_index] == 1)[0]
    base_control = np.where(treatment[base_index] == 0)[0]
    if base_treated.size < 3 or base_control.size < 3:
        raise MethodError("政策前的处理组或对照组样本不足。")
    if trim > 0:
        support = (propensity >= trim) & (propensity <= 1.0 - trim)
        removed = int(support.size - support.sum())
        base_treated = base_treated[support[base_treated]]
        base_control = base_control[support[base_control]]
        if base_treated.size < 3 or base_control.size < 3:
            raise MethodError(
                f"trim={trim} 修剪后政策前处理组 {base_treated.size} 个、"
                f"对照组 {base_control.size} 个，样本不足，请减小 trim。"
            )
        context.warn(f"共同支撑域修剪 trim={trim} 去掉了 {removed} 个倾向得分落在两端的样本。")

    treated_p = propensity[base_treated]
    control_p = propensity[base_control]
    pool = min(ratio, base_control.size)
    local = NearestNeighbors(n_neighbors=1).fit(control_p.reshape(-1, 1))
    nearest = local.kneighbors(treated_p.reshape(-1, 1))[0].ravel()
    caliper = context.number("caliper")
    if caliper is None:
        caliper = max(float(np.percentile(nearest, 90)), 1e-4)
        context.warn(f"未指定 caliper，已按最近邻距离的 90 百分位取 {caliper:.4f}。")
    if caliper <= 0:
        raise MethodError("caliper 必须为正数。")

    positions, weights = _match_rows("nearest", treated_p, control_p, ratio, caliper, True)
    widths = (weights > 0).sum(axis=1)
    matched = np.where(widths > 0)[0]
    if matched.size < 3:
        raise MethodError(f"caliper={caliper} 下只匹配到 {matched.size} 对，请放宽 caliper。")
    row_widths = widths[matched]
    used = weights[matched] > 0
    weight_flat = weights[matched][used]
    treated_units = base_index[base_treated[matched]]
    control_units = base_index[base_control[positions[matched][used]]]
    pair_index = np.repeat(np.arange(matched.size), row_widths)

    kept_units = np.concatenate([treated_units, control_units])
    kept_weights = np.concatenate([np.ones(treated_units.size), weight_flat])
    kept_pairs = np.concatenate([pair_index, pair_index])
    frame = pd.DataFrame(
        {
            "y": outcome[kept_units],
            "treat": treatment[kept_units],
            "post": period[kept_units],
            "weight": kept_weights,
        }
    )
    frame["did"] = frame["treat"] * frame["post"]
    try:
        if std_error == "cluster":
            fitted = smf.wls("y ~ treat + post + did", frame, weights=frame["weight"]).fit(
                cov_type="cluster", cov_kwds={"groups": kept_pairs}
            )
        elif std_error == "heteroskedastic":
            fitted = smf.wls("y ~ treat + post + did", frame, weights=frame["weight"]).fit(
                cov_type="HC1"
            )
        else:
            fitted = smf.wls("y ~ treat + post + did", frame, weights=frame["weight"]).fit()
    except Exception as error:
        raise MethodError(f"PSM-DID 回归失败：{error}")

    smd_frame = pd.DataFrame(
        {
            "feature": [f"V{index + 1}" for index in range(len(names))],
            "treated_mean": numbers(matrix[treated_units].mean(axis=0), 6),
            "control_mean": numbers(
                (matrix[control_units] * weight_flat[:, None]).sum(axis=0)
                / max(treated_units.size, 1),
                6,
            ),
        }
    )
    pooled = np.sqrt(
        (matrix[treated_units].var(axis=0, ddof=1) + matrix[control_units].var(axis=0, ddof=1)) / 2
    )
    pooled = np.where(pooled <= EPS, 1.0, pooled)
    smd_frame["smd"] = numbers(
        (
            matrix[treated_units].mean(axis=0)
            - (matrix[control_units] * weight_flat[:, None]).sum(axis=0)
            / max(treated_units.size, 1)
        )
        / pooled,
        6,
    )
    imbalanced = int((smd_frame["smd"].abs() > smd_threshold).sum())
    notes = [
        "先用政策前的特征做匹配，再在匹配样本上做双重差分。",
        "匹配只在政策前进行，避免用政策后的信息选择样本。",
        f"匹配后处理组与对照组在这 {len(names)} 个协变量上有 {imbalanced} 个的 SMD 超过 {smd_threshold}。",
    ]
    if pool > 1:
        notes.append(f"每个处理个体使用 {pool} 个近邻对照，并按倾向得分距离倒数加权。")
    if trim > 0:
        notes.append(f"匹配前按 trim={trim} 修剪了共同支撑域。")
    if std_error == "cluster":
        notes.append(f"标准误按匹配对聚类，共 {matched.size} 个簇。")
    elif std_error == "heteroskedastic":
        notes.append("标准误为异方差稳健（HC1）。")
    figures = []
    if pretrend_plot:
        kept_frame = pd.DataFrame(
            {"treat": treatment[kept_units], "post": period[kept_units], "y": outcome[kept_units]}
        )
        trend_frame = None
        if trend_column:
            if trend_column not in table.raw.columns:
                raise MethodError(
                    f"时间趋势列 {trend_column} 不在数据中。"
                    f"可用列：{'、'.join(str(item) for item in table.raw.columns[:12])}"
                )
            trend_frame = pd.DataFrame(
                {
                    "treat": treatment[kept_units],
                    "post": period[kept_units],
                    "trend": _series_values(table, trend_column)[kept_units],
                    "y": outcome[kept_units],
                }
            )
        cells = kept_frame.groupby(["treat", "post"])["y"].agg(["count", "mean"]).reset_index()
        cells["group"] = cells["treat"].map({0.0: "对照组", 1.0: "处理组"})
        cells["period"] = cells["post"].map({0.0: "政策前", 1.0: "政策后"})
        figure = _did_pretrend_figure(context, cells, trend_frame, trend_column, 0.05, 10)
        if figure:
            figures.append(figure)
    return registry.result(
        "causal.psmdid",
        table,
        metrics={
            "treatment_column": treatment_column,
            "period_column": period_column,
            "matched_features": len(names),
            "matched_pairs": int(matched.size),
            "caliper": caliper,
            "observations": int(fitted.nobs),
            "smd_threshold": smd_threshold,
            "imbalanced_after": imbalanced,
            "neighbours": pool,
            "trim": trim,
            "std_error": std_error,
            "trend_column": trend_column,
            "matched_controls": int(control_units.size),
            "did_effect": round(float(fitted.params["did"]), 6),
            "did_p_value": round(float(fitted.pvalues["did"]), 8),
            "significant": bool(fitted.pvalues["did"] < 0.05),
        },
        tables={
            "coefficients": table_of(
                pd.DataFrame(
                    {
                        "term": [str(name) for name in fitted.params.index],
                        "coefficient": numbers(fitted.params.to_numpy(), 6),
                        "p_value": numbers(fitted.pvalues.to_numpy(), 8),
                    }
                ),
                limit=20,
            ),
            "balance_after": table_of(smd_frame, limit=40),
        },
        figures=figures,
        notes=notes,
    )


def _placebo_figure(context, draws, actual):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过安慰剂分布图。")
        return None
    fig, axis = plt.subplots(figsize=(6.5, 4.5))
    axis.hist(draws, bins=30, color="#8fb2ff", edgecolor="white")
    axis.axvline(actual, color="#d64545", linewidth=1.6)
    axis.set_xlabel("安慰剂效应")
    axis.set_ylabel("频数")
    axis.set_title("安慰剂分布与真实效应")
    axis.grid(alpha=0.3, axis="y")
    return context.save(fig, "causal_placebo_distribution")


@register("causal.placebo")
def placebo(context):
    import statsmodels.formula.api as smf

    table = context.table
    outcome = _outcome(context)
    treated = _binary_column(context, "treatment_column")
    period = _binary_column(context, "period_column")
    codes = _binary_values(context, treated)
    times = _binary_values(context, period)
    rounds = context.whole("rounds", 200, 20, 5000)
    seed = context.whole("seed", 42, 0, 10**6)
    kind = context.text("placebo_type", "shuffle_treatment", ("shuffle_treatment", "shift_period"))
    time_column = context.text("time_column")
    want_tail = context.flag("tail_summary", False)
    want_plot = context.flag("placebo_plot", False)

    frame = pd.DataFrame({"y": outcome, "treat": codes, "post": times})
    frame["did"] = frame["treat"] * frame["post"]
    actual = float(smf.ols("y ~ treat + post + did", frame).fit().params["did"])

    rng = np.random.default_rng(seed)
    draws = np.zeros(rounds)
    if kind == "shift_period":
        if not time_column:
            raise MethodError("安慰剂类型为随机政策时点时，请用 time_column 指定时间列。")
        values = _series_values(table, time_column)
        low, high = np.percentile(values, [20.0, 80.0])
        if high - low <= EPS:
            raise MethodError(f"时间列 {time_column} 的变化太小，无法随机提前政策时点。")
        for index in range(rounds):
            fake = (values >= rng.uniform(low, high)).astype(float)
            if fake.min() == fake.max():
                draws[index] = np.nan
                continue
            frame["post"] = fake
            frame["did"] = codes * fake
            try:
                draws[index] = float(smf.ols("y ~ treat + post + did", frame).fit().params["did"])
            except Exception:
                draws[index] = np.nan
    else:
        for index in range(rounds):
            shuffled = rng.permutation(codes)
            frame["treat"] = shuffled
            frame["did"] = shuffled * times
            try:
                draws[index] = float(smf.ols("y ~ treat + post + did", frame).fit().params["did"])
            except Exception:
                draws[index] = np.nan
    draws = draws[np.isfinite(draws)]
    if draws.size < 10:
        raise MethodError("安慰剂检验有效轮次不足，请增加 rounds。")
    pvalue = float((np.abs(draws) >= abs(actual)).mean())
    rows = pd.DataFrame(
        {
            "quantity": [
                "真实 DID 效应",
                "安慰剂均值",
                "安慰剂标准差",
                "安慰剂 2.5% 分位",
                "安慰剂 97.5% 分位",
                "双侧 p 值",
            ],
            "value": [
                round(actual, 6),
                round(float(draws.mean()), 6),
                round(float(draws.std(ddof=1)), 6),
                round(float(np.percentile(draws, 2.5)), 6),
                round(float(np.percentile(draws, 97.5)), 6),
                round(pvalue, 8),
            ],
        }
    )
    figures = []
    if want_plot:
        figure = _placebo_figure(context, draws, actual)
        if figure:
            figures.append(figure)
    tables_out = {"summary": table_of(rows)}
    if want_tail:
        levels = [1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0, 97.5, 99.0]
        tables_out["percentiles"] = table_of(
            pd.DataFrame(
                {
                    "percentile": [f"{level:g}%" for level in levels],
                    "placebo_effect": [
                        round(float(np.percentile(draws, level)), 6) for level in levels
                    ],
                    "two_sided_p": [
                        round(float((np.abs(draws) >= abs(np.percentile(draws, level))).mean()), 8)
                        for level in levels
                    ],
                }
            )
        )
    kind_note = (
        "随机打乱处理组标签后重估 DID"
        if kind == "shuffle_treatment"
        else f"在 {time_column} 的中间区间内随机提前政策时点后重估 DID"
    )
    notes = [
        f"{kind_note}，若真实效应落在安慰剂分布之外，说明结果不太可能是偶然。",
        "p 值由安慰剂分布中绝对值不小于真实效应的比例得到。",
    ]
    if kind == "shift_period":
        notes.append("提前政策时点的安慰剂检验只保留处理组划分不变、政策时点随机变动的变异。")
    if want_tail:
        notes.append(
            "分位数表给出安慰剂分布在常用分位上的效应值，"
            "真实效应落在 2.5%~97.5% 之外时可在 5% 水平上拒绝原假设。"
        )
    return registry.result(
        "causal.placebo",
        context.table,
        metrics={
            "treatment_column": treated,
            "period_column": period,
            "rounds": int(draws.size),
            "actual_effect": round(actual, 6),
            "placebo_mean": round(float(draws.mean()), 6),
            "placebo_std": round(float(draws.std(ddof=1)), 6),
            "p_value": round(pvalue, 8),
            "significant": bool(pvalue < 0.05),
            "percentile_of_actual": round(float((draws < actual).mean()), 6),
            "placebo_type": kind,
            "time_column": time_column,
            "tail_summary": bool(want_tail),
            "placebo_plot": bool(want_plot),
        },
        tables=tables_out,
        figures=figures,
        notes=notes,
    )


def _interaction_figure(context, frame, factors, combinations):
    try:
        import matplotlib.pyplot as plt

        if len(factors) == 2:
            fig, axis = plt.subplots(figsize=(6.5, 4.5))
            for level in pd.unique(frame[factors[1]]):
                block = combinations[combinations[factors[1]] == level]
                axis.plot(
                    block[factors[0]].astype(str), block["mean"], marker="o", label=str(level)
                )
            axis.set_xlabel(factors[0])
            axis.set_ylabel("均值")
            axis.set_title("交互作用图")
            axis.legend(title=factors[1], fontsize=8)
            axis.grid(alpha=0.3)
            return context.save(fig, "design_factorial_interaction")
        fig, axes = plt.subplots(1, len(factors), figsize=(4.5 * len(factors), 4))
        for position, name in enumerate(factors):
            block = frame.groupby(name)["y"].mean()
            axes[position].bar(block.index.astype(str), block.to_numpy(), color="#4f7cff")
            axes[position].set_title(f"{name} 的主效应")
            axes[position].grid(alpha=0.3, axis="y")
        return context.save(fig, "design_factorial_effects")
    except ImportError:
        context.warn("未安装 matplotlib，跳过交互作用图。")
        return None


def _residual_figure(context, fitted):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过残差诊断图。")
        return None
    predicted = np.asarray(fitted.fittedvalues, dtype=float)
    residual = np.asarray(fitted.resid, dtype=float)
    fig, axis = plt.subplots(figsize=(6.2, 4.5))
    axis.scatter(predicted, residual, s=18, color="#4f7cff", alpha=0.8)
    axis.axhline(0.0, color="#d64545", linewidth=1.1)
    axis.set_xlabel("拟合值")
    axis.set_ylabel("残差")
    axis.set_title("残差诊断")
    axis.grid(alpha=0.3)
    return context.save(fig, "design_factorial_residuals")


@register("design.factorial")
def factorial(context):
    import statsmodels.formula.api as smf

    table = context.table
    outcome = _outcome(context)
    chosen = context.want("factors")
    if isinstance(chosen, str):
        chosen = [item.strip() for item in chosen.split(",") if item.strip()]
    max_levels = context.whole("max_levels", 5, 2, 20)
    min_cell = context.whole("min_cell", 1, 1, 100)
    block_column = context.text("block_column")
    order_column = context.text("order_column")
    randomize = context.flag("randomize", False)
    order_seed = context.whole("order_seed", 42, 0, 10**6)
    want_effect = context.flag("effect_size", False)
    want_residual = context.flag("residual_plot", False)
    factors = []
    if chosen:
        for name in chosen:
            if name not in table.raw.columns:
                raise MethodError(
                    f"因子 {name} 不在数据中。可用列："
                    f"{'、'.join(str(item) for item in table.raw.columns[:12])}"
                )
            levels = int(table.raw[name].nunique(dropna=False))
            if levels < 2:
                raise MethodError(f"因子 {name} 只有 1 个水平，无法做因子分析。")
            if levels > max_levels:
                raise MethodError(
                    f"因子 {name} 有 {levels} 个水平，超过上限 {max_levels}；"
                    "请提高 max_levels 或改选低基数因子。"
                )
            factors.append(name)
    else:
        for name in table.raw.columns:
            if name == table.target_name:
                continue
            if table.raw[name].nunique(dropna=False) <= max_levels:
                factors.append(name)
    if len(factors) < 2:
        raise MethodError("全因子设计至少需要两个低基数因子列。")
    if len(factors) > 4:
        factors = factors[:4]
        context.warn("因子超过 4 个，只使用前 4 个以避免组合爆炸。")

    frame = pd.DataFrame({"y": outcome})
    for name in factors:
        frame[name] = table.raw[name].astype("string").to_numpy()
    block_levels = 0
    if block_column:
        if block_column not in table.raw.columns:
            raise MethodError(
                f"区组列 {block_column} 不在数据中。可用列："
                f"{'、'.join(str(item) for item in table.raw.columns[:12])}"
            )
        if block_column in factors:
            raise MethodError(f"区组列 {block_column} 不能同时作为因子，请改选别的列。")
        frame["block"] = table.raw[block_column].astype("string").to_numpy()
        block_levels = int(frame["block"].nunique())
    incomplete = frame[factors].isna().any(axis=1)
    dropped = int(incomplete.sum())
    if dropped:
        frame = frame[~incomplete].reset_index(drop=True)
        context.warn(f"因子列有缺失的 {dropped} 行已从因子分析中剔除。")
    if frame.shape[0] < 4:
        raise MethodError("剔除因子缺失的行之后样本太少，无法做因子分析。")
        if block_levels < 2:
            raise MethodError(f"区组列 {block_column} 只有 1 个水平，无法估计区组效应。")
    if randomize or order_column:
        frame = _shuffle_frame(context, frame, "random", order_seed, order_column)
    terms = " * ".join(f"C(Q('{name}'))" for name in factors)
    if block_column:
        formula = "y ~ C(Q('block')) + " + terms
    else:
        formula = "y ~ " + terms
    try:
        fitted = smf.ols(formula, frame).fit()
    except Exception as error:
        raise MethodError(f"全因子模型拟合失败：{error}")

    anova = None
    try:
        from statsmodels.stats.anova import anova_lm

        anova = anova_lm(fitted, typ=2)
        anova = anova.reset_index().rename(columns={"index": "term"})
    except Exception as error:
        context.warn(f"方差分析表生成失败：{error}")

    combinations = frame.groupby(factors)["y"].agg(["count", "mean", "std"]).reset_index()
    sparse = combinations[combinations["count"] < min_cell]
    if len(sparse):
        context.warn(f"有 {len(sparse)} 个水平组合的观测数少于 {min_cell}，交互效应估计会不稳定。")
    if block_column:
        block_counts = frame.groupby("block")["y"].size()
        if int(block_counts.min()) < 2:
            context.warn(f"区组 {block_column} 有水平只包含 1 条观测，区组效应估计会不稳定。")
    tables = {"cell_means": table_of(combinations, limit=60)}
    if anova is not None:
        tables["anova"] = table_of(anova, limit=40)
    max_eta = None
    if want_effect and anova is not None:
        residual = anova[anova["term"].astype(str) == "Residual"]
        if len(residual):
            error_ss = float(residual["sum_sq"].iloc[0])
            error_df = float(residual["df"].iloc[0])
            error_ms = error_ss / max(error_df, 1.0)
            size = float(len(frame))
            rows = []
            for _, item in anova.iterrows():
                if str(item["term"]) == "Residual":
                    continue
                ss = float(item["sum_sq"])
                df = float(item["df"])
                eta = ss / (ss + error_ss) if ss + error_ss > EPS else 0.0
                omega = (
                    (ss - df * error_ms) / (ss + (size - df) * error_ms) if error_ms > EPS else 0.0
                )
                rows.append(
                    {
                        "term": str(item["term"]),
                        "eta_squared": round(eta, 6),
                        "omega_squared": round(max(omega, 0.0), 6),
                    }
                )
            effect_frame = pd.DataFrame(rows)
            tables["effect_size"] = table_of(effect_frame, limit=40)
            if len(effect_frame):
                max_eta = round(float(effect_frame["eta_squared"].max()), 6)
        else:
            context.warn("方差分析表没有残差项，无法计算效应量。")
    figures = []
    if context.flag("interaction_plot", True) and 2 <= len(factors) <= 3:
        figure = _interaction_figure(context, frame, factors, combinations)
        if figure:
            figures.append(figure)
    if want_residual:
        figure = _residual_figure(context, fitted)
        if figure:
            figures.append(figure)
    notes = [
        "全因子设计包含所有主效应与交互效应，能识别因子之间的相互影响。",
        "因子数与水平数增加会让组合数快速增长，需要保证每个组合都有重复观测。",
    ]
    if block_column:
        notes.append(
            f"模型已把 {block_column}（{block_levels} 个水平）作为区组主效应，"
            "可以吸收区组造成的系统差异。"
        )
    if randomize or order_column:
        if order_column:
            notes.append(
                f"试验顺序已按 {order_column} 排序，顺序记在 run_order 列，拟合样本顺序随之改变。"
            )
        else:
            notes.append(f"试验顺序已按随机种子 {order_seed} 随机化，避免试验先后与因子效应混淆。")
    if want_effect:
        notes.append("η² 是效应平方和占总平方和的比例，ω² 进一步校正了自由度带来的高估。")
    return registry.result(
        "design.factorial",
        table,
        metrics={
            "factors": factors,
            "levels": [int(frame[name].nunique()) for name in factors],
            "cells": int(combinations.shape[0]),
            "observations": int(fitted.nobs),
            "max_levels": max_levels,
            "min_cell": min_cell,
            "sparse_cells": int(len(sparse)),
            "r_squared": round(float(fitted.rsquared), 6),
            "terms": int(len(fitted.params)),
            "aic": round(float(fitted.aic), 6),
            "block_column": block_column,
            "block_levels": block_levels,
            "randomize": bool(randomize),
            "order_column": order_column,
            "order_seed": order_seed,
            "effect_size": bool(want_effect),
            "max_eta_squared": max_eta,
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _design_matrix(context, kind):
    factors = context.want("factors")
    if isinstance(factors, str):
        factors = [item.strip() for item in factors.split(",") if item.strip()]
    if not factors:
        raise MethodError("请用 factors 指定因子名列表。")
    levels = context.want("levels") or [3] * len(factors)
    if isinstance(levels, int):
        levels = [levels] * len(factors)
    levels = [int(value) for value in levels]
    if len(levels) != len(factors):
        raise MethodError("levels 的个数必须与 factors 一致。")
    runs = context.whole("runs", max(levels) ** 2, len(factors), 200)
    return factors, levels, runs


def _shuffle_frame(context, frame, order, seed, column):
    if order != "random" or frame.shape[0] < 2:
        return frame
    records = None
    if column:
        if column not in context.table.raw.columns:
            raise MethodError(
                f"试验顺序列 {column} 不在数据中。可用列："
                f"{'、'.join(str(item) for item in context.table.raw.columns[:12])}"
            )
        keys = context.table.raw[column]
        if pd.api.types.is_numeric_dtype(keys):
            keys = pd.to_numeric(keys, errors="coerce").to_numpy(dtype=float)
        else:
            keys = keys.astype("string").factorize()[0].astype(float)
        if keys.size == frame.shape[0] and np.unique(keys).size == keys.size:
            records = frame.iloc[np.argsort(keys, kind="mergesort")].reset_index(drop=True)
        else:
            context.warn(
                f"顺序列 {column} 有 {keys.size} 个取值，与当前 {frame.shape[0]} 次试验"
                "无法一一对应，已改用随机种子排顺序。"
            )
    if records is None:
        records = _shuffle_runs(frame, order, seed)
    records.insert(0, "run_order", np.arange(1, records.shape[0] + 1))
    return records


def _coded_point(row, levels):
    parts = []
    for value, size in zip(row, levels):
        span = max(int(size) - 1, 1)
        parts.append(round(-1.0 + 2.0 * (float(value) - 1.0) / span, 6))
    return tuple(parts)


def _mixed_level_design(factors, levels, runs):
    clipped = [max(int(size), 2) for size in levels]
    combos = [()]
    for size in clipped:
        combos = [item + (step,) for item in combos for step in range(1, size + 1)]
    if not combos:
        raise MethodError("因子水平数无法生成组合。")
    if len(combos) <= runs:
        return pd.DataFrame(combos, columns=factors)
    unique = list(dict.fromkeys(_coded_point(item, clipped) for item in combos))
    if len(unique) < runs:
        raise MethodError(
            f"各因子水平组合的编码点数只有 {len(unique)} 个，"
            f"少于试验次数 {runs}，请减少 runs 或调整 levels。"
        )
    picked = []
    seen = set()
    step = 2
    while len(picked) < runs and len(seen) < len(unique):
        for item in range(0, len(unique), step):
            if len(picked) >= runs:
                break
            if item not in seen:
                seen.add(item)
                picked.append(item)
        step += 1
    if len(picked) < runs:
        raise MethodError(
            f"无法在 {len(unique)} 个编码点中选出 {runs} 个互不重复的试验点，"
            "请减少 runs 或增加 levels。"
        )
    coded = pd.DataFrame([unique[index] for index in picked], columns=factors)
    design = coded.copy()
    for position, name in enumerate(factors):
        size = clipped[position]
        design[name] = [
            min(max(int(round((float(value) + 1.0) / 2.0 * (size - 1))) + 1, 1), size)
            for value in coded[name].to_numpy(dtype=float)
        ]
        design[name] = design[name].astype(int)
    return design


def _repeat_runs(frame, replicates):
    if replicates <= 1:
        return frame
    return pd.concat([frame] * replicates, ignore_index=True)


def _shuffle_runs(frame, order, seed):
    if order != "random" or frame.shape[0] < 2:
        return frame
    rng = np.random.default_rng(seed)
    return frame.iloc[rng.permutation(frame.shape[0])].reset_index(drop=True)


def _coding_table(factors, levels):
    rows = []
    for position, name in enumerate(factors):
        size = levels[position]
        for step in range(size):
            code = f"水平{step + 1}" if size == 2 else step
            rows.append(
                {
                    "factor": name,
                    "level_code": step + 1,
                    "design_value": code,
                    "coded_value": round(-1.0 + 2.0 * step / max(size - 1, 1), 4),
                }
            )
    return pd.DataFrame(rows)


@register("design.orthogonal")
def orthogonal(context):
    factors, levels, runs = _design_matrix(context, "orthogonal")
    uniform = len(set(levels)) == 1
    mixed = context.flag("mixed_levels", True)
    if not uniform and not mixed:
        raise MethodError("正交表默认要求各因子水平数相同；各因子水平数不同时请打开 mixed_levels。")
    for name, count in zip(factors, levels):
        if count < 2:
            raise MethodError(f"因子 {name} 的水平数至少为 2。")
    replicates = context.whole("replicates", 1, 1, 10)
    order = context.text("order", "ordered", ("ordered", "random"))
    order_seed = context.whole("order_seed", 42, 0, 10**6)
    order_column = context.text("order_column")
    coding = context.flag("coding_table", True)
    check = context.flag("balance_check", True)
    plot = context.flag("design_plot", True)
    if not uniform:
        expected = 1
        for count in levels:
            expected *= count
        if expected > 200:
            raise MethodError(
                f"各因子水平数的组合共有 {expected} 个，超过上限 200，请减少因子或水平数。"
            )
        table_frame = _mixed_level_design(factors, levels, runs)
        runs = int(table_frame.shape[0])
    elif mixed:
        table_frame = _mixed_level_design(factors, levels, runs)
    elif levels[0] == 2:
        count = max(4, 2 ** int(math.ceil(math.log2(max(len(factors) + 1, 2)))))
        base = np.array([[0]])
        while base.shape[0] < count:
            base = np.vstack([np.hstack([base, base]), np.hstack([base, 1 - base])])
        table_frame = pd.DataFrame(base[:, : len(factors)], columns=factors) + 1
    else:
        size = levels[0]
        count = max(size * size, runs)
        rows = []
        for index in range(count):
            row = []
            for position, factor in enumerate(factors):
                step = (index + position * size) % size
                row.append(step + 1)
            rows.append(row)
        table_frame = pd.DataFrame(rows, columns=factors)
    table_frame = table_frame.head(runs)
    table_frame.columns = factors
    table_frame = _repeat_runs(table_frame, replicates)
    table_frame = _shuffle_frame(context, table_frame, order, order_seed, order_column)

    pairs = []
    for left in range(len(factors)):
        for right in range(left + 1, len(factors)):
            counts = pd.crosstab(table_frame[factors[left]], table_frame[factors[right]]).to_numpy()
            balance = float(counts.std() / max(counts.mean(), EPS)) if counts.size else None
            pairs.append(
                {
                    "pair": f"{factors[left]} × {factors[right]}",
                    "min_count": int(counts.min()),
                    "max_count": int(counts.max()),
                    "imbalance": None if balance is None else round(balance, 6),
                }
            )
    tables = {"design": table_of(table_frame, limit=60)}
    if coding:
        tables["coding"] = table_of(_coding_table(factors, levels), limit=40)
    if check:
        tables["balance"] = table_of(pd.DataFrame(pairs), limit=20)
    worst = max((item["imbalance"] or 0.0) for item in pairs) if pairs else None
    if check and worst is not None and worst > 0.01:
        context.warn(
            f"最大不均衡度 {worst:.4f} 超过 0.01，当前表在 {runs} 次试验下不是完全正交表。"
        )
    figures = []
    if plot and len(factors) >= 2:
        figure = _design_scatter_figure(
            context, table_frame, factors, "design_orthogonal_points", levels
        )
        if figure:
            figures.append(figure)
    notes = [
        "正交设计要求任意两个因子的各水平组合出现次数相同，从而主效应互不混杂。",
        "这里生成的是均衡表，实际试验时把水平编号替换成真实的因子取值。",
    ]
    if not uniform:
        notes.append(
            "已允许各因子水平数不同，混合水平表按编码点均匀选取，"
            "任意两个因子的组合出现次数未必完全相同，均衡性请参考检查表。"
        )
    if replicates > 1:
        notes.append(f"每个试验点重复 {replicates} 次，用来估计纯误差并提高检验功效。")
    if order == "random":
        if order_column:
            notes.append(f"试验顺序已按 {order_column} 排序，并把顺序写进 run_order 列。")
        else:
            notes.append(f"试验顺序已按随机种子 {order_seed} 打乱，避免顺序带来的系统误差。")
    return registry.result(
        "design.orthogonal",
        context.table,
        metrics={
            "factors": factors,
            "levels": levels if not uniform else levels[0],
            "mixed_levels": bool(mixed),
            "runs": int(table_frame.shape[0]),
            "balance_check": bool(check),
            "pairs_checked": len(pairs),
            "max_imbalance": worst,
            "replicates": replicates,
            "order": order,
            "order_seed": order_seed,
            "order_column": order_column,
            "coding_table": bool(coding),
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _primes(count):
    values = []
    candidate = 2
    while len(values) < count:
        if all(candidate % item for item in values):
            values.append(candidate)
        candidate += 1
    return values


def _van_der_corput(index, base):
    value = 0.0
    factor = 1.0 / base
    while index > 0:
        value += factor * (index % base)
        index //= base
        factor /= base
    return value


def _halton_design(factors, levels, count, seed, scramble):
    rng = np.random.default_rng(seed)
    bases = _primes(len(factors))
    shifts = rng.random(len(factors)) if scramble else np.zeros(len(factors))
    rows = []
    for index in range(1, count + 1):
        row = []
        for position, base in enumerate(bases):
            value = (_van_der_corput(index, base) + shifts[position]) % 1.0
            size = levels[position]
            row.append(int(min(value * size, size - 1)) + 1)
        rows.append(row)
    return pd.DataFrame(rows, columns=factors)


def _normalised_points(design, factors, levels):
    columns = []
    for position, name in enumerate(factors):
        size = max(int(levels[position]), 2)
        columns.append((design[name].to_numpy(dtype=float) - 0.5) / size)
    return np.column_stack(columns)


def _discrepancy(points, kind):
    count, dimension = points.shape
    half = np.abs(points - 0.5)
    if kind == "wrap_l2":
        gap = np.abs(points[:, None, :] - points[None, :, :])
        total = float(np.prod(1.5 - gap * (1.0 - gap), axis=2).sum())
        return float(np.sqrt(max(total / count**2 - (4.0 / 3.0) ** dimension, 0.0)))
    single = float(np.prod(1.0 + 0.5 * half - 0.5 * half**2, axis=1).sum())
    left = half[:, None, :]
    right = half[None, :, :]
    gap = np.abs(points[:, None, :] - points[None, :, :])
    pair = float(np.prod(1.0 + 0.5 * left + 0.5 * right - 0.5 * gap, axis=2).sum())
    value = (13.0 / 12.0) ** dimension - 2.0 / count * single + pair / count**2
    return float(np.sqrt(max(value, 0.0)))


@register("design.uniform")
def uniform_design(context):
    factors, levels, runs = _design_matrix(context, "uniform")
    seed = context.whole("seed", 42, 0, 10**6)
    construction = context.text("construction", "lattice", ("lattice", "halton"))
    replicates = context.whole("replicates", 1, 1, 10)
    mixed = context.flag("mixed_levels", True)
    scramble = context.flag("scramble", False)
    lattice_shift = context.flag("lattice_shift", False)
    metric = context.text("discrepancy", "centred_l2", ("centred_l2", "wrap_l2"))
    compare = context.flag("discrepancy_compare", False)
    order = context.text("order", "ordered", ("ordered", "random"))
    order_seed = context.whole("order_seed", 42, 0, 10**6)
    order_column = context.text("order_column")
    plot = context.flag("design_plot", True)
    count = max(runs, len(factors) + 1)
    if len(set(levels)) != 1 and not mixed:
        raise MethodError(
            "均匀设计默认要求各因子水平数相同；各因子水平数不同时请打开 mixed_levels。"
        )
    if mixed and len(set(levels)) == 1:
        count = max(count, len(factors) + 2)
    shifts = []
    if construction == "halton":
        table_frame = _halton_design(factors, levels, count, seed, scramble)
        multipliers = []
    else:
        size = count + 1
        multipliers = [candidate for candidate in range(2, size) if math.gcd(candidate, size) == 1]
        if not multipliers:
            raise MethodError(f"试验次数 {count} 下找不到与 {size} 互质的乘子，请换一个 runs。")
        rng = np.random.default_rng(seed)
        pool = list(multipliers)
        while len(pool) < len(factors):
            pool.extend(multipliers)
        order_index = rng.permutation(len(pool))
        chosen = [pool[index] for index in order_index[: len(factors)]]
        if lattice_shift:
            shifts = [int(value) for value in rng.integers(0, size, len(factors))]
        else:
            shifts = [0] * len(factors)
        rows = []
        for index in range(1, count + 1):
            row = []
            for position, factor in enumerate(factors):
                level = levels[position]
                value = (index * chosen[position] - 1 + shifts[position]) % size
                row.append(int(value * level / size) + 1)
            rows.append(row)
        multipliers = chosen
        table_frame = pd.DataFrame(rows, columns=factors)
    table_frame = _repeat_runs(table_frame, replicates)
    table_frame = _shuffle_frame(context, table_frame, order, order_seed, order_column)

    spread = []
    for name in factors:
        counts = table_frame[name].value_counts()
        spread.append(
            {
                "factor": name,
                "levels_used": int(counts.size),
                "min_count": int(counts.min()),
                "max_count": int(counts.max()),
            }
        )
    points = _normalised_points(table_frame, factors, levels)
    value = _discrepancy(points, metric)
    other = "wrap_l2" if metric == "centred_l2" else "centred_l2"
    if value > 0.1:
        context.warn(f"{metric} 偏差为 {value:.4f}，试验点分布偏聚集，建议增加 runs 或换随机种子。")
    tables = {
        "design": table_of(table_frame, limit=60),
        "spread": table_of(pd.DataFrame(spread), limit=20),
    }
    if compare:
        comparison = _discrepancy(points, other)
        tables["discrepancy"] = table_of(
            pd.DataFrame(
                {"metric": [metric, other], "value": [round(value, 6), round(comparison, 6)]}
            )
        )
    figures = []
    if plot and len(factors) >= 2:
        figure = _design_scatter_figure(
            context, table_frame, factors, "design_uniform_points", levels
        )
        if figure:
            figures.append(figure)
    notes = [
        "均匀设计让试验点在因子空间中尽量均匀散布，适合因子水平多而试验次数少的场景。",
        f"乘子按随机种子 {seed} 从互质候选里抽取，换种子会得到不同的均匀设计表。",
        "均匀设计牺牲正交性换取更少的试验次数，分析时需用回归建模。",
    ]
    if construction == "halton":
        notes[1] = f"当前用 Halton 低差异序列布点（前 {len(factors)} 个质数为基底），" + (
            "并对每个维度做了随机平移。" if scramble else "未做随机平移。"
        )
    elif lattice_shift:
        notes.append(
            f"格子点已按随机种子 {seed} 做了平移（偏移 {shifts}），"
            "同一组乘子下会得到不同的均匀设计表。"
        )
    if compare:
        notes.append(
            f"两种偏差口径同时给出：{metric} 与 {other}，数值越小说明试验点在因子空间中越均匀。"
        )
    if replicates > 1:
        notes.append(f"每个试验点重复 {replicates} 次，共 {table_frame.shape[0]} 次试验。")
    notes.append(f"均匀性用 {metric} 偏差衡量，当前设计偏差为 {value:.6f}，越小越均匀。")
    if order == "random":
        if order_column:
            notes.append(f"试验顺序已按 {order_column} 排序，并把顺序写进 run_order 列。")
        else:
            notes.append(f"试验顺序已按随机种子 {order_seed} 打乱，避免试验先后带来的系统误差。")
    return registry.result(
        "design.uniform",
        context.table,
        metrics={
            "factors": factors,
            "runs": int(table_frame.shape[0]),
            "seed": seed,
            "levels": levels if mixed else levels[0],
            "mixed_levels": bool(mixed),
            "multipliers": multipliers,
            "construction": construction,
            "replicates": replicates,
            "scramble": bool(scramble),
            "lattice_shift": bool(lattice_shift and construction == "lattice"),
            "discrepancy_metric": metric,
            "discrepancy_compare": bool(compare),
            "discrepancy": round(value, 6),
            "order": order,
            "order_seed": order_seed,
            "order_column": order_column,
            "mean_level_reuse": round(
                float(np.mean([item["max_count"] for item in spread[: len(factors)]])), 4
            ),
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


@register("design.rsm")
def response_surface(context):
    import statsmodels.formula.api as smf

    table = context.table
    outcome = _outcome(context)
    factors = context.want("factors")
    if isinstance(factors, str):
        factors = [item.strip() for item in factors.split(",") if item.strip()]
    if not factors:
        factors = list(table.feature_names[:2])
    if len(factors) < 2:
        raise MethodError(
            f"响应面分析至少需要两个因子；当前可用特征：{'、'.join(table.feature_names[:8])}"
        )
    if len(factors) > 4:
        raise MethodError("响应面分析最多支持四个因子。")
    for name in factors:
        if name not in table.feature_names:
            raise MethodError(
                f"因子 {name} 不在特征中（常量列会被自动移除）。"
                f"可选：{'、'.join(table.feature_names[:10])}"
            )

    matrix = table.matrix()
    order = context.text("model", "quadratic", ("linear", "quadratic"))
    grid_points = context.whole("grid_points", 30, 10, 100)
    step_size = context.number("step_size", 0.01, 1e-6, 1.0)
    optimiser = context.text("optimiser", "l-bfgs-b", ("l-bfgs-b", "nelder-mead"))
    contour_levels = context.whole("contour_levels", 12, 4, 40)
    want_cv = context.flag("cross_validation", False)
    want_plot = context.flag("response_plot", True)
    frame = pd.DataFrame({"y": outcome})
    for name in factors:
        values = matrix[:, table.feature_names.index(name)]
        frame[f"x_{name}"] = values
        frame[f"s_{name}"] = values**2
    terms = [f"x_{name}" for name in factors]
    if order == "quadratic":
        terms += [f"s_{name}" for name in factors]
        terms += [
            f"x_{factors[i]} : x_{factors[j]}"
            for i in range(len(factors))
            for j in range(i + 1, len(factors))
        ]
    formula = "y ~ " + " + ".join(terms)
    try:
        fitted = smf.ols(formula, frame).fit()
    except Exception as error:
        raise MethodError(f"响应面模型拟合失败：{error}")

    from scipy.optimize import minimize

    centre = np.array([frame[f"x_{name}"].mean() for name in factors])
    scale = np.array([frame[f"x_{name}"].std(ddof=0) or 1.0 for name in factors])
    lower_bounds = frame[[f"x_{name}" for name in factors]].min().to_numpy(dtype=float)
    upper_bounds = frame[[f"x_{name}" for name in factors]].max().to_numpy(dtype=float)

    def predict(point):
        row = {"Intercept": 1.0}
        for index, name in enumerate(factors):
            row[f"x_{name}"] = point[index]
            row[f"s_{name}"] = point[index] ** 2
        for i in range(len(factors)):
            for j in range(i + 1, len(factors)):
                row[f"x_{factors[i]} : x_{factors[j]}"] = point[i] * point[j]
        total = 0.0
        for term, coefficient in fitted.params.items():
            total += float(coefficient) * row.get(term, 0.0)
        return total

    bounds = list(zip(lower_bounds, upper_bounds))
    if optimiser == "nelder-mead":
        best = minimize(
            lambda point: -predict(point),
            centre,
            method="Nelder-Mead",
            bounds=bounds,
            options={"xatol": step_size, "fatol": 1e-9, "maxiter": 4000},
        )
    else:
        best = minimize(
            lambda point: -predict(point),
            centre,
            method="L-BFGS-B",
            bounds=bounds,
            options={"eps": step_size},
        )
    optimum = np.clip(best.x, lower_bounds, upper_bounds)
    rows = pd.DataFrame(
        {
            "term": [str(name) for name in fitted.params.index],
            "coefficient": numbers(fitted.params.to_numpy(), 6),
            "p_value": numbers(fitted.pvalues.to_numpy(), 8),
        }
    )
    stationary = pd.DataFrame(
        {
            "factor": factors,
            "optimum": numbers(optimum, 6),
            "centre": numbers(centre, 6),
            "std": numbers(scale, 6),
        }
    )
    curve = None
    if len(factors) == 2:
        axis = np.linspace(lower_bounds[0], upper_bounds[0], grid_points)
        second = np.linspace(lower_bounds[1], upper_bounds[1], grid_points)
        grid = []
        for value in axis:
            for other in second:
                grid.append(
                    {
                        "x1": round(float(value), 6),
                        "x2": round(float(other), 6),
                        "predicted": round(float(predict(np.array([value, other]))), 6),
                    }
                )
        curve = pd.DataFrame(grid)
    tables = {"coefficients": table_of(rows, limit=40), "optimum": table_of(stationary)}
    if curve is not None:
        tables["surface"] = table_of(curve, limit=grid_points * 3)
    diagnostics = {"press": None, "loo_r_squared": None}
    if want_cv:
        influence = fitted.get_influence()
        leverage = np.clip(influence.hat_matrix_diag, 0.0, 1.0 - 1e-9)
        residual = np.asarray(fitted.resid, dtype=float)
        press = float(np.sum((residual / (1.0 - leverage)) ** 2))
        total = float(np.sum((outcome - outcome.mean()) ** 2))
        diagnostics["press"] = round(press, 6)
        diagnostics["loo_r_squared"] = round(1.0 - press / max(total, EPS), 6)
        tables["diagnostics"] = table_of(
            pd.DataFrame(
                {
                    "quantity": [
                        "留一预测误差平方和 PRESS",
                        "留一交叉验证 R²",
                        "模型 R²",
                        "调整 R²",
                    ],
                    "value": [
                        diagnostics["press"],
                        diagnostics["loo_r_squared"],
                        round(float(fitted.rsquared), 6),
                        round(float(fitted.rsquared_adj), 6),
                    ],
                }
            )
        )
    figures = []
    if curve is not None and context.flag("figures", True) and want_plot:
        figure = _surface_figure(context, curve, grid_points, factors, contour_levels)
        if figure:
            figures.append(figure)
    name = {"l-bfgs-b": "L-BFGS-B", "nelder-mead": "Nelder-Mead"}[optimiser]
    notes = [
        (
            "二阶响应面用平方项描述曲率、交叉项描述因子间的交互。"
            if order == "quadratic"
            else "一阶响应面只含线性项，用于筛选显著因子。"
        ),
        "最优点在观测范围内才可靠；若落在边界，说明极值可能在试验区域外。",
        f"最优化由 {name} 完成，步长参数按该算法解释为差分步长。",
    ]
    if want_cv:
        notes.append("留一交叉验证 R² 明显低于模型 R² 时，说明响应面存在过拟合。")
    return registry.result(
        "design.rsm",
        table,
        metrics={
            "factors": factors,
            "observations": int(fitted.nobs),
            "model": order,
            "grid_points": grid_points,
            "step_size": step_size,
            "contour_levels": contour_levels,
            "terms": int(len(fitted.params)),
            "r_squared": round(float(fitted.rsquared), 6),
            "adjusted_r_squared": round(float(fitted.rsquared_adj), 6),
            "predicted_optimum": round(float(predict(optimum)), 6),
            "optimiser_success": bool(best.success),
            "optimiser": optimiser,
            "cross_validation": bool(want_cv),
            "press": diagnostics["press"],
            "loo_r_squared": diagnostics["loo_r_squared"],
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _surface_figure(context, curve, grid_points, factors, contour_levels=12):
    plt = _prepare_axes()
    if plt is None:
        context.warn("未安装 matplotlib，跳过响应面图。")
        return None
    try:
        pivot = curve.pivot(index="x2", columns="x1", values="predicted")
        fig, axis = plt.subplots(figsize=(6.5, 5))
        mesh = axis.contourf(
            pivot.columns.to_numpy(dtype=float),
            pivot.index.to_numpy(dtype=float),
            pivot.to_numpy(dtype=float),
            levels=int(contour_levels),
            cmap="viridis",
        )
        axis.set_xlabel(factors[0])
        axis.set_ylabel(factors[1])
        axis.set_title("响应面等高线")
        fig.colorbar(mesh, ax=axis, label="预测值")
        return context.save(fig, "design_rsm_surface")
    except Exception as error:
        context.warn(f"响应面图绘制失败：{error}")
        return None


def _central_design(context, kind):
    table = context.table
    factors = context.want("factors")
    if isinstance(factors, str):
        factors = [item.strip() for item in factors.split(",") if item.strip()]
    if not factors:
        factors = list(table.feature_names[:3])
    if len(factors) < 2:
        raise MethodError("需要至少两个因子。")
    if len(factors) > 6:
        raise MethodError("最多支持六个因子。")
    centre_runs = context.whole("centre_runs", 4, 1, 20)
    replicates = context.whole("replicates", 1, 1, 10)
    low, high = -1.0, 1.0
    rows = []
    if kind == "ccd":
        alpha = context.number("alpha")
        method = context.text("alpha_method", "rotatable", ("rotatable", "orthogonal", "face"))
        if alpha is None:
            if method == "orthogonal":
                alpha = float(math.sqrt(len(factors)))
            elif method == "face":
                alpha = 1.0
            else:
                alpha = 2.0 ** (len(factors) / 4)
        alpha = min(max(float(alpha), 1.0), 3.0)
        for index in range(len(factors)):
            for sign in (1, -1):
                row = [0.0] * len(factors)
                row[index] = sign * alpha
                rows.append(row)
        for _ in range(replicates):
            for mask in range(2 ** len(factors)):
                rows.append(
                    [high if (mask >> position) & 1 else low for position in range(len(factors))]
                )
    else:
        alpha = None
        method = None
        for _ in range(replicates):
            for left in range(len(factors)):
                for right in range(left + 1, len(factors)):
                    for first in (-1, 1):
                        for second in (-1, 1):
                            row = [0.0] * len(factors)
                            row[left] = first
                            row[right] = second
                            rows.append(row)
    for _ in range(centre_runs):
        rows.append([0.0] * len(factors))
    design = pd.DataFrame(rows, columns=factors)
    return design, factors, alpha, method


def _attach_blocks(design, factors, blocks, kind):
    if blocks <= 1:
        return design
    axis = design[factors].abs()
    largest = axis.max(axis=1).to_numpy(dtype=float)
    centre = largest <= 1e-9
    labels = np.ones(design.shape[0], dtype=int)
    if kind == "ccd":
        axial = largest > 1.0 + 1e-9
        edge = (~centre) & (~axial)
        order = np.where(edge)[0]
        if order.size:
            for position, chunk in enumerate(np.array_split(order, blocks - 1)):
                labels[chunk] = position + 1
        labels[axial] = blocks
    else:
        groups = {}
        for row in range(design.shape[0]):
            if centre[row]:
                continue
            values = design.iloc[row][factors].to_numpy(dtype=float)
            key = tuple(int(item) for item in np.where(np.abs(values) > 1e-9)[0])
            groups.setdefault(key, []).append(row)
        for position, key in enumerate(sorted(groups)):
            for row in groups[key]:
                labels[row] = (position % blocks) + 1
    if centre.any():
        index = np.where(centre)[0]
        labels[index] = (np.arange(index.size) % blocks) + 1
    design = design.copy()
    design["block"] = labels
    return design


def _design_scatter_figure(context, design, factors, name, levels=None, show_levels=True):
    plt = _prepare_axes()
    if plt is None:
        context.warn("未安装 matplotlib，跳过试验点分布图。")
        return None
    annotation = None
    if levels and show_levels:
        annotation = "水平数：" + "、".join(
            f"{factor}={levels[index]}" for index, factor in enumerate(factors)
        )
    if len(factors) >= 3:
        fig = plt.figure(figsize=(6.5, 5.5))
        axis = fig.add_subplot(111, projection="3d")
        axis.scatter(
            design[factors[0]], design[factors[1]], design[factors[2]], s=28, color="#4f7cff"
        )
        axis.set_xlabel(factors[0])
        axis.set_ylabel(factors[1])
        axis.set_zlabel(factors[2])
        axis.set_title("试验点分布" + (f"（{annotation}）" if annotation else ""))
        return context.save(fig, name)
    fig, axis = plt.subplots(figsize=(5.6, 5))
    axis.scatter(design[factors[0]], design[factors[1]], s=46, color="#4f7cff")
    if levels and len(levels) >= 2:
        for value in range(1, int(levels[0]) + 1):
            axis.axvline(value, color="#c9d2e3", linewidth=0.7)
        for value in range(1, int(levels[1]) + 1):
            axis.axhline(value, color="#c9d2e3", linewidth=0.7)
    else:
        axis.axhline(0.0, color="#c9d2e3", linewidth=0.9)
        axis.axvline(0.0, color="#c9d2e3", linewidth=0.9)
    axis.set_xlabel(factors[0])
    axis.set_ylabel(factors[1])
    axis.set_title("试验点分布" + (f"（{annotation}）" if annotation else ""))
    axis.grid(alpha=0.3)
    return context.save(fig, name)


@register("design.ccd")
def ccd(context):
    blocks = context.whole("blocks", 1, 1, 5)
    design, factors, alpha, method = _central_design(context, "ccd")
    design = _attach_blocks(design, factors, blocks, "ccd")
    axis = design[factors].abs().max(axis=1)
    radius = float(np.sqrt((design[factors] ** 2).sum(axis=1)).max())
    block_sizes = None
    if "block" in design.columns:
        counts = design["block"].value_counts().sort_index()
        block_sizes = {int(index): int(value) for index, value in counts.items()}
    figures = []
    if context.flag("design_plot", False) and len(factors) >= 2:
        levels = [int((design[name].abs().max() > 1.0) and 3 or 2) for name in factors]
        figure = _design_scatter_figure(context, design, factors, "design_ccd_points", levels)
        if figure:
            figures.append(figure)
    name = {"rotatable": "可旋转（2^(k/4)）", "orthogonal": "正交（√k）", "face": "面心（1.0）"}[
        method
    ]
    notes = [
        "中心复合设计由因子点、轴点与中心点组成，可以拟合含平方项的二次模型。",
        "轴点距离取 2^(k/4) 时设计具有可旋转性，预测方差只与到中心的距离有关。",
        f"当前星点距离为 {alpha:.4f}，取值方式为{name}。",
    ]
    if blocks > 1:
        notes.append(f"试验被拆成 {blocks} 个区组，析因点、轴点与中心点分散在不同区组里。")
    return registry.result(
        "design.ccd",
        context.table,
        metrics={
            "factors": factors,
            "runs": int(design.shape[0]),
            "factorial_points": int((axis == 1.0).sum()),
            "axial_points": int((axis > 1.0).sum()),
            "centre_points": int((axis == 0.0).sum()),
            "max_radius": round(radius, 6),
            "alpha": round(alpha, 6),
            "alpha_method": method,
            "blocks": blocks,
            "block_sizes": block_sizes,
        },
        tables={"design": table_of(design, limit=60)},
        figures=figures,
        notes=notes,
    )


@register("design.boxbehnken")
def box_behnken(context):
    blocks = context.whole("blocks", 1, 1, 5)
    order = context.text("order", "ordered", ("ordered", "random"))
    order_seed = context.whole("order_seed", 42, 0, 10**6)
    radius_mode = context.text(
        "radius_mode", "classic", ("classic", "spherical_factor", "spherical_edge")
    )
    design, factors, _, _ = _central_design(context, "boxbehnken")
    points = design[factors].to_numpy(dtype=float)
    if radius_mode == "spherical_factor":
        design[factors] = np.round(points / math.sqrt(len(factors)), 6)
    elif radius_mode == "spherical_edge":
        design[factors] = np.round(points / math.sqrt(2.0), 6)
    design = _attach_blocks(design, factors, blocks, "boxbehnken")
    design = _shuffle_runs(design, order, order_seed)
    radius = float(np.sqrt((design[factors] ** 2).sum(axis=1)).max())
    centre_points = int((design[factors].abs().max(axis=1) == 0.0).sum())
    block_sizes = None
    if "block" in design.columns:
        counts = design["block"].value_counts().sort_index()
        block_sizes = {int(index): int(value) for index, value in counts.items()}
    figures = []
    if context.flag("response_plot", True) and len(factors) >= 2:
        figure = _design_scatter_figure(context, design, factors, "design_boxbehnken_points")
        if figure:
            figures.append(figure)
    notes = [
        "Box-Behnken 设计不使用立方体的角点，所有试验点都在棱的中点上。",
        "因子数相同时它比 CCD 更省试验次数，但不能外推到极端组合。",
    ]
    if radius_mode == "spherical_factor":
        notes.append(
            f"棱中点已缩放到半径 {radius:.4f} 的球面上（系数 1/√k），"
            "各试验点到中心等距、因子编码为 ±1/√k。"
        )
    elif radius_mode == "spherical_edge":
        notes.append(
            f"棱中点已缩放到中心在面上的球面（系数 1/√2，半径 {radius:.4f}），"
            "非中心点到中心的距离一致。"
        )
    if blocks > 1:
        notes.append(f"试验被拆成 {blocks} 个区组，每对因子的边中点与中心点分散到不同区组。")
    if order == "random":
        notes.append(f"试验顺序已按随机种子 {order_seed} 打乱。")
    return registry.result(
        "design.boxbehnken",
        context.table,
        metrics={
            "factors": factors,
            "runs": int(design.shape[0]),
            "corner_points": 0,
            "centre_points": centre_points,
            "max_radius": round(radius, 6),
            "radius_mode": radius_mode,
            "points_radius": round(radius, 6),
            "blocks": blocks,
            "block_sizes": block_sizes,
            "order": order,
            "order_seed": order_seed,
        },
        tables={"design": table_of(design, limit=60)},
        figures=figures,
        notes=notes,
    )
