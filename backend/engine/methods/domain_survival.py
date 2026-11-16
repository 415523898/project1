"""Existing domain survival algorithms; registered by engine.methods.domain."""

import numpy as np
import pandas as pd

from engine import registry
from engine.registry import MethodError, numbers, table_of

EPS = 1e-12


def _survival_columns(context):
    table = context.table
    duration = context.text("duration_column")
    event = context.text("event_column")
    from engine.dataset_selection import semantic_column

    duration = semantic_column(table.raw.columns, "duration_column", duration)
    event = semantic_column(table.raw.columns, "event_column", event)
    if not duration or not event or duration == event:
        raise MethodError(
            "需要明确的生存/随访时长列与事件/删失列，请指定 duration_column 和 event_column，不能用普通特征代替。"
        )
    times = pd.to_numeric(table.raw[duration], errors="coerce")
    events = pd.to_numeric(table.raw[event], errors="coerce")
    if not times.notna().any():
        raise MethodError(f"时间列 {duration} 不是数值列。")
    if not events.notna().any():
        raise MethodError(f"事件指示列 {event} 不是数值列。")
    keep = times.notna() & events.notna() & (times >= 0)
    return duration, event, times[keep].to_numpy(dtype=float), events[keep].to_numpy(dtype=int)


def kaplan_meier(context):
    from lifelines import KaplanMeierFitter
    from lifelines.statistics import logrank_test

    duration, event, times, events = _survival_columns(context)
    logrank = context.flag("logrank", True)
    level = context.number("ci", 0.95, 0.5, 0.999)
    risk_points = context.whole("risk_points", 12, 3, 100)
    grid_mode = context.text("grid_mode", "even", ("even", "quantile"))
    horizon = context.number("horizon", None, 1e-6, 1e9)
    if times.size < 5:
        raise MethodError("生存分析至少需要 5 个有效观测。")
    group_name = context.text("group_column")
    if group_name and group_name not in context.table.raw.columns:
        context.warn(f"分组列 {group_name} 不在数据中，已改用自动识别的分组列。")
        group_name = None
    group_name = group_name or context.table.group_name
    groups = None
    if group_name and group_name in context.table.raw.columns:
        groups = context.table.raw[group_name].astype("string").fillna("缺失").to_numpy()
        groups = groups[
            (pd.to_numeric(context.table.raw[duration], errors="coerce").notna()).to_numpy()
            & (pd.to_numeric(context.table.raw[event], errors="coerce").notna()).to_numpy()
            & (pd.to_numeric(context.table.raw[duration], errors="coerce") >= 0).to_numpy()
        ]
        groups = groups[: times.size]

    fitter = KaplanMeierFitter(alpha=1.0 - level)
    fitter.fit(times, event_observed=events)
    median = fitter.median_survival_time_
    timeline = np.asarray(fitter.timeline, dtype=float)
    survival = np.asarray(fitter.survival_function_.iloc[:, 0], dtype=float)
    band = fitter.confidence_interval_
    band_low = np.asarray(band.iloc[:, 0], dtype=float)
    band_high = np.asarray(band.iloc[:, 1], dtype=float)
    rows = pd.DataFrame({"time": numbers(timeline, 4), "survival": numbers(survival, 6)})
    band_rows = pd.DataFrame(
        {
            "time": numbers(timeline, 4),
            "survival_low": numbers(band_low, 6),
            "survival_high": numbers(band_high, 6),
        }
    )
    if grid_mode == "quantile":
        grid = np.unique(np.quantile(timeline, np.linspace(0.0, 1.0, risk_points)))
    else:
        grid = np.linspace(0.0, float(timeline[-1]), risk_points)
    risk_rows = pd.DataFrame(
        {
            "time": numbers(grid, 4),
            "survival": numbers(np.interp(grid, timeline, survival), 6),
            "survival_low": numbers(np.interp(grid, timeline, band_low), 6),
            "survival_high": numbers(np.interp(grid, timeline, band_high), 6),
        }
    )

    def crossing(curve, goal=0.5):
        below = np.nonzero(np.asarray(curve, dtype=float) <= goal)[0]
        if below.size == 0:
            return None
        return round(float(timeline[int(below[0])]), 6)

    if np.isfinite(median):
        median_low = crossing(band_low)
        median_high = crossing(band_high)
    else:
        median_low = None
        median_high = None
    metrics = {
        "duration_column": duration,
        "event_column": event,
        "observations": int(times.size),
        "events": int(events.sum()),
        "censored": int((events == 0).sum()),
        "logrank": bool(logrank),
        "confidence_level": round(float(level), 6),
        "risk_points": int(risk_points),
        "median_survival": None if not np.isfinite(median) else round(float(median), 6),
        "median_survival_low": median_low,
        "median_survival_high": median_high,
        "survival_at_median_time": round(float(np.interp(median, timeline, survival)), 6)
        if np.isfinite(median)
        else None,
    }
    tables = {
        "survival_function": table_of(rows, limit=60),
        "survival_interval": table_of(band_rows, limit=60),
        "risk_table": table_of(risk_rows, limit=risk_points),
    }
    if horizon is not None:
        at_time = float(horizon)
        metrics["horizon"] = round(at_time, 6)
        metrics["survival_at_horizon"] = round(float(np.interp(at_time, timeline, survival)), 6)
        tables["prediction_at_horizon"] = table_of(
            pd.DataFrame(
                [
                    {
                        "time": round(at_time, 6),
                        "survival": round(float(np.interp(at_time, timeline, survival)), 6),
                        "survival_low": round(float(np.interp(at_time, timeline, band_low)), 6),
                        "survival_high": round(float(np.interp(at_time, timeline, band_high)), 6),
                    }
                ]
            )
        )

    try:
        import matplotlib.pyplot as plt

        fig, axis = plt.subplots(figsize=(7, 4.5))
        if groups is not None and len(set(groups)) >= 2:
            for group_level in sorted(set(groups)):
                block = groups == group_level
                KaplanMeierFitter().fit(
                    times[block], event_observed=events[block], label=str(group_level)
                ).plot_survival_function(ax=axis, ci_show=False)
        else:
            fitter.plot_survival_function(ax=axis, ci_show=True)
        axis.set_xlabel("时间")
        axis.set_ylabel("生存概率")
        axis.set_title("Kaplan-Meier 生存曲线")
        axis.grid(alpha=0.3)
        context.save(fig, "domain_km")
    except ImportError:
        context.warn("未安装 matplotlib，跳过生存曲线。")

    if groups is not None and len(set(groups)) >= 2:
        labels = sorted(set(groups))
        if logrank:
            first = groups == labels[0]
            second = groups == labels[1]
            test = logrank_test(
                times[first],
                times[second],
                event_observed_A=events[first],
                event_observed_B=events[second],
            )
            p_value = float(test.p_value)
            statistic = float(test.test_statistic)
            metrics["logrank_p"] = round(p_value, 8)
            metrics["logrank_statistic"] = round(statistic, 6)
            tables["logrank"] = table_of(
                pd.DataFrame(
                    [
                        {
                            "comparison": f"{labels[0]} vs {labels[1]}",
                            "groups": int(len(labels)),
                            "statistic": round(statistic, 6),
                            "p_value": round(p_value, 8),
                        }
                    ]
                )
            )
            context.warn(f"两组 log-rank 检验 p = {p_value:.4g}")
        elif len(labels) > 2:
            context.warn(f"共有 {len(labels)} 组，Log-rank 检验已关闭。")
    elif logrank:
        context.warn("未提供分组列，跳过 Log-rank 检验。")

    notes = [
        "删失观测在事件发生前退出，Kaplan-Meier 会在每个事件时点重算风险集。",
        "中位生存期为生存曲线降到 0.5 的时间；若曲线未降到 0.5 则无法估计。",
        "Log-rank 检验比较各组生存曲线，p 小于显著性水平说明组间差异显著。",
    ]
    if level != 0.95:
        notes.append(
            f"生存曲线置信带按 {level * 100:g}% 水平计算，中位生存期区间由置信带与 0.5 的交点给出。"
        )
    if grid_mode == "quantile":
        notes.append(f"生存率表在 {risk_points} 个分位时点上插值输出，事件密集的时间段点更密。")
    else:
        notes.append(f"生存率表在 {risk_points} 个等距时点上插值输出。")
    if horizon is not None:
        notes.append(f"预测时点 {float(horizon):g} 的生存率由生存曲线插值得到。")
    return registry.result(
        "domain.km",
        context.table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


def _feature_columns(context, matrix):
    chosen = context.want("columns")
    if not chosen:
        return matrix, list(context.table.feature_names)
    if isinstance(chosen, str):
        chosen = [item.strip() for item in chosen.split(",") if item.strip()]
    names = list(context.table.feature_names)
    index = []
    for name in chosen:
        if name not in names:
            raise MethodError(f"列 {name} 不在特征中。可选：{'、'.join(names[:10])}")
        index.append(names.index(name))
    return matrix[:, index], [names[position] for position in index]


def cox(context):
    from lifelines import CoxPHFitter
    from scipy import stats as sps

    duration, event, times, events = _survival_columns(context)
    penalizer = context.number("penalizer", 0.01, 0.0, 10.0)
    level = context.number("ci", 0.95, 0.5, 0.999)
    strata = context.text("strata")
    baseline = context.flag("baseline", True)
    cumulative_hazard = context.flag("cumulative_hazard", False)
    survival_plot = context.flag("survival_plot", True)
    table = context.table
    matrix, feature_names = _feature_columns(context, table.matrix())
    keep = (
        pd.to_numeric(table.raw[duration], errors="coerce").notna().to_numpy()
        & pd.to_numeric(table.raw[event], errors="coerce").notna().to_numpy()
        & (pd.to_numeric(table.raw[duration], errors="coerce") >= 0).to_numpy()
    )
    if matrix.shape[0] != times.size:
        matrix = matrix[keep]
    if matrix.shape[0] != times.size:
        raise MethodError("生存列与特征行数不一致，请检查缺失值。")
    if matrix.shape[1] > 20:
        raise MethodError("Cox 回归最多支持 20 个特征，请先用 columns 选择。")
    if times.size < 10:
        raise MethodError("Cox 回归至少需要 10 个有效观测。")

    frame = pd.DataFrame(matrix, columns=feature_names)
    frame["__duration__"] = times
    frame["__event__"] = events
    strata_levels = None
    if strata:
        if strata not in table.raw.columns:
            raise MethodError(
                f"分层变量 {strata} 不在数据中。"
                f"可选：{'、'.join(str(name) for name in table.raw.columns[:12])}"
            )
        if strata in feature_names:
            raise MethodError(f"分层变量 {strata} 不能同时作为协变量，请把它从 columns 中去掉。")
        values = table.raw[strata].astype("string").fillna("缺失").to_numpy()[keep]
        if np.unique(values).size < 2:
            raise MethodError(f"分层变量 {strata} 只有一个取值，无法分层。")
        frame["__strata__"] = values
        strata_levels = sorted(str(item) for item in np.unique(values))
    model = CoxPHFitter(penalizer=penalizer)
    try:
        model.fit(
            frame,
            duration_col="__duration__",
            event_col="__event__",
            strata=["__strata__"] if strata else None,
        )
    except Exception as error:
        raise MethodError(f"Cox 模型拟合失败：{error}")

    summary = model.summary
    rows = summary.reset_index().rename(columns={"index": "covariate", "covariate": "covariate"})
    rows.columns = [str(column) for column in rows.columns]
    coefficients = np.asarray(summary["coef"], dtype=float)
    errors = np.asarray(summary["se(coef)"], dtype=float)
    z_critical = float(sps.norm.ppf(0.5 + level / 2.0))
    low = coefficients - z_critical * errors
    high = coefficients + z_critical * errors
    interval = pd.DataFrame(
        {
            "covariate": [str(name) for name in summary.index],
            "coef": numbers(coefficients, 6),
            "std_error": numbers(errors, 6),
            "ci_low": numbers(low, 6),
            "ci_high": numbers(high, 6),
            "exp_ci_low": numbers(np.exp(low), 6),
            "exp_ci_high": numbers(np.exp(high), 6),
        }
    )
    metrics = {
        "duration_column": duration,
        "event_column": event,
        "observations": int(times.size),
        "events": int(events.sum()),
        "features": int(matrix.shape[1]),
        "penalizer": round(float(penalizer), 6),
        "confidence_level": round(float(level), 6),
        "z_critical": round(z_critical, 6),
        "strata": None if not strata else str(strata),
        "strata_levels": None if strata_levels is None else int(len(strata_levels)),
        "baseline_survival": bool(baseline),
        "concordance": round(float(model.concordance_index_), 6),
        "log_likelihood": round(float(model.log_likelihood_), 6),
        "aic": round(float(model.AIC_partial_), 6),
    }
    if "p" in summary.columns:
        strongest = summary["p"].idxmin()
        metrics["most_significant"] = str(strongest)
        metrics["smallest_p"] = round(float(summary["p"].min()), 8)
    tables = {
        "coefficients": table_of(rows, limit=40),
        "confidence_intervals": table_of(interval, limit=40),
    }
    if baseline:
        baseline_frame = model.baseline_survival_
        tables["baseline_survival"] = table_of(
            pd.DataFrame(
                {
                    "time": numbers(baseline_frame.index.to_numpy(), 4),
                    "baseline_survival": numbers(baseline_frame.iloc[:, 0].to_numpy(), 6),
                }
            ),
            limit=60,
        )
    if cumulative_hazard:
        hazard_frame = model.baseline_cumulative_hazard_
        tables["baseline_cumulative_hazard"] = table_of(
            pd.DataFrame(
                {
                    "time": numbers(hazard_frame.index.to_numpy(), 4),
                    "baseline_cumulative_hazard": numbers(hazard_frame.iloc[:, 0].to_numpy(), 6),
                }
            ),
            limit=60,
        )
        metrics["cumulative_hazard"] = True
    notes = [
        "风险比 exp(coef) 大于 1 表示该协变量提高事件发生的瞬时风险。",
        "一致性指数 concordance 越接近 1 表示排序预测越准；0.5 相当于随机。",
        f"这里使用 penalizer={penalizer:g} 的 L2 惩罚以保证数值稳定。",
        f"系数置信区间按 {level * 100:g}% 水平计算（z={z_critical:.4f}）。",
    ]
    if strata:
        notes.append(f"已按 {strata} 分层（共 {len(strata_levels)} 层），各层有各自的基线风险。")
    if not baseline:
        notes.append("已按设置跳过基线生存函数输出。")
    if cumulative_hazard:
        notes.append("基线累积风险是各时间点的累积风险量，与基线生存函数一一对应。")
    if survival_plot:
        try:
            import matplotlib.pyplot as plt

            curve = model.baseline_survival_
            fig, axis = plt.subplots(figsize=(7, 4.5))
            for column in curve.columns:
                axis.step(
                    np.asarray(curve.index, dtype=float),
                    np.asarray(curve[column], dtype=float),
                    where="post",
                    label=str(column) if strata else "基线生存函数",
                )
            axis.set_xlabel("时间")
            axis.set_ylabel("生存概率")
            axis.set_title("Cox 基线生存曲线")
            if strata:
                axis.legend(fontsize=8)
            axis.grid(alpha=0.3)
            context.save(fig, "domain_cox_survival")
        except ImportError:
            context.warn("未安装 matplotlib，跳过生存曲线图。")
    return registry.result(
        "domain.cox",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


def nomogram(context):
    from lifelines import CoxPHFitter

    duration, event, times, events = _survival_columns(context)
    points_max = context.whole("points_max", 100, 10, 1000)
    horizon = context.number("horizon", None, 1e-6, 1e9)
    score_bins = context.whole("score_bins", 10, 3, 50)
    bin_mode = context.text("bin_mode", "quantile", ("quantile", "equal"))
    plot = context.flag("plot", True)
    table = context.table
    matrix, feature_names = _feature_columns(context, table.matrix())
    mask = (
        pd.to_numeric(table.raw[duration], errors="coerce").notna().to_numpy()
        & pd.to_numeric(table.raw[event], errors="coerce").notna().to_numpy()
        & (pd.to_numeric(table.raw[duration], errors="coerce") >= 0).to_numpy()
    )
    matrix = matrix[mask]
    if matrix.shape[0] != times.size or times.size < 15:
        raise MethodError("列线图至少需要 15 个有效观测。")
    frame = pd.DataFrame(matrix, columns=feature_names)
    frame["__duration__"] = times
    frame["__event__"] = events
    model = CoxPHFitter(penalizer=0.01)
    try:
        model.fit(frame, duration_col="__duration__", event_col="__event__")
    except Exception as error:
        raise MethodError(f"Cox 模型拟合失败：{error}")

    coefficients = model.params_
    at_time = float(horizon) if horizon is not None else float(np.median(times))
    try:
        predicted = model.predict_survival_function(frame[feature_names], times=[at_time])
    except Exception as error:
        raise MethodError(f"预测时点 {at_time:g} 的生存概率计算失败：{error}")
    predicted_values = np.asarray(predicted.to_numpy(), dtype=float).ravel()
    if predicted_values.size != len(frame) or not np.isfinite(predicted_values).all():
        raise MethodError(f"预测时点 {at_time:g} 没有得到有效的生存概率。")
    risk = 1.0 - predicted_values
    prediction = pd.DataFrame(
        {
            "quantile": ["P10", "P25", "P50", "P75", "P90"],
            "survival": numbers(np.percentile(predicted_values, [10, 25, 50, 75, 90]), 6),
        }
    )
    score_values = np.asarray(frame[feature_names], dtype=float)
    span = np.ptp(score_values, axis=0)
    coefficient_values = np.asarray(coefficients, dtype=float)
    effect_ranges = np.abs(coefficient_values) * span
    points_scale = float(points_max) / max(float(effect_ranges.max()), EPS)
    # Subtract each covariate's lowest-risk contribution, retaining its sign.
    # Summed points are one affine transform of the Cox linear predictor.
    baseline = np.where(coefficient_values >= 0, score_values.min(axis=0), score_values.max(axis=0))
    contributions = (score_values - baseline) * coefficient_values * points_scale
    total_points = contributions.sum(axis=1)
    covariate_max = effect_ranges * points_scale
    rows = pd.DataFrame(
        {
            "covariate": [str(name) for name in coefficients.index],
            "coefficient": numbers(coefficient_values, 6),
            "points_at_max": numbers(covariate_max, 2),
            "value_at_zero_points": numbers(baseline, 6),
            "value_at_max_points": numbers(
                np.where(
                    coefficient_values >= 0, score_values.max(axis=0), score_values.min(axis=0)
                ),
                6,
            ),
        }
    )
    distribution = pd.DataFrame(
        {
            "quantile": ["P10", "P25", "P50", "P75", "P90"],
            "risk": numbers(np.percentile(risk, [10, 25, 50, 75, 90]), 6),
            "points": numbers(np.percentile(total_points, [10, 25, 50, 75, 90]), 2),
        }
    )
    if bin_mode == "equal":
        edges = np.unique(
            np.linspace(float(total_points.min()), float(total_points.max()), score_bins + 1)
        )
    else:
        edges = np.unique(np.quantile(total_points, np.linspace(0.0, 1.0, score_bins + 1)))
    if edges.size < 2:
        raise MethodError("总分取值过于集中，无法按 score_bins 分档，请减少分档数。")
    score_rows = []
    for position in range(edges.size - 1):
        low_edge = float(edges[position])
        high_edge = float(edges[position + 1])
        if position == edges.size - 2:
            selected = (total_points >= low_edge) & (total_points <= high_edge)
        else:
            selected = (total_points >= low_edge) & (total_points < high_edge)
        if not selected.any():
            continue
        score_rows.append(
            {
                "score_low": round(low_edge, 4),
                "score_high": round(high_edge, 4),
                "respondents": int(selected.sum()),
                "mean_risk": round(float(risk[selected].mean()), 6),
                "mean_survival": round(float(predicted_values[selected].mean()), 6),
            }
        )
    if plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.barh([str(name) for name in coefficients.index], covariate_max, color="#4f7cff")
            axis.set_xlabel("协变量最大得分")
            axis.set_title(f"列线图协变量得分（单项最高 {points_max:g}）")
            axis.grid(alpha=0.3, axis="x")
            context.save(fig, "domain_nomogram")
        except ImportError:
            context.warn("未安装 matplotlib，跳过列线图。")
    notes = [
        f"按本次协变量范围与带符号的Cox效应统一换算积分，影响范围最大的单项最高为{points_max}分；总分可超过该值。",
        "负系数对应较大取值、较低积分；总分与Cox线性预测值同向，分档风险取1减去指定时点的预测生存概率。",
        f"预测时点 {at_time:g} 的个体生存概率用 Cox 基线生存函数与个体风险评分推算。",
        "这里给出每个协变量的最大得分与风险的分布，可用于手工评分。",
        f"总分-风险对照表把个体总分按 {score_bins} 档"
        f"{'等宽' if bin_mode == 'equal' else '分位'}切分，给出每档的平均风险与生存率。",
    ]
    return registry.result(
        "domain.nomogram",
        table,
        metrics={
            "observations": int(times.size),
            "features": int(matrix.shape[1]),
            "points_max": int(points_max),
            "horizon": round(at_time, 6),
            "score_bins": int(score_bins),
            "nomogram_plot": bool(plot),
            "mean_total_points": round(float(total_points.mean()), 4),
            "concordance": round(float(model.concordance_index_), 6),
            "mean_risk": round(float(risk.mean()), 6),
            "survival_at_horizon": round(float(predicted_values.mean()), 6),
            "max_points_per_covariate": round(float(points_max), 2),
        },
        tables={
            "covariate_points": table_of(rows, limit=40),
            "risk_distribution": table_of(distribution),
            "prediction_at_horizon": table_of(prediction),
            "score_risk": table_of(pd.DataFrame(score_rows), limit=score_bins),
        },
        notes=notes,
    )


def competing_risk(context):
    from lifelines import AalenJohansenFitter

    duration, event, times, events = _survival_columns(context)
    curves_points = context.whole("curves_points", 40, 10, 200)
    target_event = context.whole("target_event", None, 1, 99)
    horizon = context.number("horizon", None, 1e-6, 1e9)
    grid_mode = context.text("grid_mode", "even", ("even", "quantile"))
    cif_table = context.flag("cif_table", True)
    ci_band = context.flag("ci_band", False)
    curve_plot = context.flag("curve_plot", True)
    if times.size < 10:
        raise MethodError("竞争风险模型至少需要 10 个有效观测。")
    event_values = sorted(set(int(value) for value in events))
    if len(event_values) < 2:
        raise MethodError("竞争风险需要至少两种事件类型（例如 1=目标事件，2=竞争事件）。")
    selected = [
        value for value in event_values[1:] if target_event is None or value == int(target_event)
    ]
    if not selected:
        raise MethodError(
            f"目标事件码 {target_event:g} 不在事件类型里，"
            f"可选：{'、'.join(str(value) for value in event_values)}。"
        )
    rows = []
    curves = []
    axis = None
    if curve_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
        except ImportError:
            axis = None
            context.warn("未安装 matplotlib，跳过累积发生曲线。")
    for value in selected:
        indicator = (events == value).astype(int)
        fitter = AalenJohansenFitter()
        try:
            fitter.fit(times, indicator, event_of_interest=1)
        except Exception as error:
            raise MethodError(f"竞争风险拟合失败（事件码 {value}）：{error}")
        timeline = np.asarray(fitter.timeline, dtype=float)
        cumulative = np.asarray(fitter.cumulative_density_.iloc[:, 0].to_numpy(), dtype=float)
        band_low = None
        band_high = None
        if ci_band:
            band = np.asarray(fitter.confidence_interval_.to_numpy(), dtype=float)
            band_low = band[:, 0]
            band_high = band[:, 1]
        curves.append((f"事件{value}", timeline, cumulative, band_low, band_high))
        rows.append(
            {
                "event": f"事件{value}",
                "count": int((events == value).sum()),
                "final_cif": round(float(cumulative[-1]), 6),
            }
        )
        if axis is not None:
            axis.step(timeline, cumulative, where="post", label=f"事件{value}")
    if axis is not None:
        axis.set_xlabel("时间")
        axis.set_ylabel("累积发生概率")
        axis.set_title("竞争风险累积发生函数")
        axis.legend(fontsize=8)
        axis.grid(alpha=0.3)
        context.save(fig, "domain_competing")
    if grid_mode == "quantile":
        pool = np.concatenate([curve[1] for curve in curves])
        grid = np.unique(np.quantile(pool, np.linspace(0.0, 1.0, curves_points)))
    else:
        grid = np.linspace(
            min(float(curve[1][0]) for curve in curves),
            max(float(curve[1][-1]) for curve in curves),
            curves_points,
        )
    detail = pd.DataFrame({"time": numbers(grid, 4)})
    for label, timeline, cumulative, band_low, band_high in curves:
        position = np.searchsorted(timeline, grid, side="right") - 1
        values = np.where(
            position < 0, 0.0, cumulative[np.clip(position, 0, max(cumulative.size - 1, 0))]
        )
        detail[label] = numbers(values, 6)
        if ci_band:
            detail[f"{label}_low"] = numbers(
                np.where(
                    position < 0, 0.0, band_low[np.clip(position, 0, max(band_low.size - 1, 0))]
                ),
                6,
            )
            detail[f"{label}_high"] = numbers(
                np.where(
                    position < 0, 0.0, band_high[np.clip(position, 0, max(band_high.size - 1, 0))]
                ),
                6,
            )
    at_time = float(horizon) if horizon is not None else float(np.max(times))
    at_rows = []
    for label, timeline, cumulative, band_low, band_high in curves:
        position = np.searchsorted(timeline, at_time, side="right") - 1
        value = 0.0 if position < 0 else float(cumulative[min(position, cumulative.size - 1)])
        at_rows.append({"event": label, "time": round(at_time, 6), "cif": round(value, 6)})
    metrics = {
        "duration_column": duration,
        "event_column": event,
        "observations": int(times.size),
        "curves_points": int(curves_points),
        "grid_mode": grid_mode,
        "horizon": round(at_time, 6),
        "cif_table": bool(cif_table),
        "event_codes": event_values,
        "censored": int((events == 0).sum()),
    }
    if target_event is not None:
        metrics["target_event"] = int(target_event)
    tables = {
        "events": table_of(pd.DataFrame(rows), limit=20),
        "cif_at_horizon": table_of(pd.DataFrame(at_rows), limit=20),
    }
    if cif_table:
        tables["cumulative_incidence"] = table_of(detail, limit=curves_points)
    notes = [
        "竞争风险用累积发生函数 CIF 而不是 1−KM，因为竞争事件会阻止目标事件发生。",
        "事件码 0 视为删失，其余码各作为一个事件类型。",
        f"累积发生曲线按 {curves_points} 个时间点"
        f"{'等距' if grid_mode == 'even' else '按分位数'}输出。",
        f"预测时点 {at_time:g} 的累积发生率见 cif_at_horizon 表。",
    ]
    if target_event is not None:
        notes.append(f"只对目标事件码 {int(target_event):g} 估计累积发生率，其余事件当作竞争事件。")
    if ci_band:
        notes.append("累积发生函数同时给出置信带上下限，用于判断估计的不确定性。")
    return registry.result(
        "domain.competing",
        context.table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )
