"""Existing domain quality algorithms; registered by engine.methods.domain."""

import math

import numpy as np
import pandas as pd

from engine import registry
from engine.registry import MethodError, numbers, table_of

EPS = 1e-12


def _rule_signals(centred, spread):
    signals = []
    values = np.asarray(centred, dtype=float)
    size = values.size
    if spread is None or spread <= EPS or size == 0:
        return signals
    z = values / float(spread)
    for index in np.nonzero(np.abs(z) > 3.0)[0]:
        signals.append((int(index), "准则1：超出 3σ 控制限"))
    for index in range(size):
        if index >= 8:
            window = z[index - 8 : index + 1]
            if np.all(window > 0) or np.all(window < 0):
                signals.append((int(index), "准则2：连续 9 点位于中心线同侧"))
    for index in range(size):
        if index >= 5:
            steps = np.diff(z[index - 5 : index + 1])
            if np.all(steps > 0) or np.all(steps < 0):
                signals.append((int(index), "准则3：连续 6 点单调上升或下降"))
    for index in range(size):
        if index >= 13:
            steps = np.diff(z[index - 13 : index + 1])
            if np.all(steps[:-1] * steps[1:] < 0):
                signals.append((int(index), "准则4：连续 14 点上下交替"))
    for index in range(size):
        if index >= 2:
            window = z[index - 2 : index + 1]
            if int((window > 2.0).sum()) >= 2 or int((window < -2.0).sum()) >= 2:
                signals.append((int(index), "准则5：3 点中 2 点超出 2σ 同侧"))
    for index in range(size):
        if index >= 4:
            window = z[index - 4 : index + 1]
            if int((window > 1.0).sum()) >= 4 or int((window < -1.0).sum()) >= 4:
                signals.append((int(index), "准则6：5 点中 4 点超出 1σ 同侧"))
    for index in range(size):
        if index >= 14 and np.all(np.abs(z[index - 14 : index + 1]) < 1.0):
            signals.append((int(index), "准则7：连续 15 点落在 1σ 以内"))
    for index in range(size):
        if index >= 7 and np.all(np.abs(z[index - 7 : index + 1]) > 1.0):
            signals.append((int(index), "准则8：连续 8 点都在 1σ 以外"))
    return signals


def control_chart(context):
    table = context.table
    target = table.numeric_target()
    if target is None:
        raise MethodError("控制图需要数值列。")
    chart = context.text("chart", "xbar_r", ("xbar_r", "cusum", "ewma"))
    rules = context.text("rules", "none", ("none", "western_electric"))
    sigma_estimate = context.text("sigma_estimate", "range", ("range", "std"))
    violation_table = context.flag("violation_table", True)
    control_plot = context.flag("control_plot", True)
    values = target[np.isfinite(target)]
    subgroup = context.whole("subgroup", 5, 2, 50)
    if values.size < subgroup * 2:
        raise MethodError(f"{chart} 至少需要 {subgroup * 2} 个观测。")

    if chart == "xbar_r":
        usable = values[: (values.size // subgroup) * subgroup].reshape(-1, subgroup)
        means = usable.mean(axis=1)
        ranges = usable.max(axis=1) - usable.min(axis=1)
        mean_of_means = float(means.mean())
        mean_range = float(ranges.mean())
        constants = {
            2: (1.880, 0.000, 2.660),
            3: (1.023, 0.000, 1.954),
            4: (0.729, 0.000, 1.628),
            5: (0.577, 0.000, 1.427),
            6: (0.483, 0.000, 1.287),
            7: (0.419, 0.076, 1.182),
            8: (0.373, 0.136, 1.099),
            9: (0.337, 0.184, 1.032),
            10: (0.308, 0.223, 0.975),
        }
        spread_constants = {
            2: 1.128,
            3: 1.693,
            4: 2.059,
            5: 2.326,
            6: 2.534,
            7: 2.704,
            8: 2.847,
            9: 2.970,
            10: 3.078,
        }
        a2, d3, d4 = constants.get(subgroup, (0.577, 0.000, 1.427))
        if sigma_estimate == "std":
            sigma_of_means = float(np.sqrt((usable.std(axis=1, ddof=1) ** 2).mean() / subgroup))
            upper = mean_of_means + 3.0 * sigma_of_means
            lower = mean_of_means - 3.0 * sigma_of_means
        else:
            sigma_of_means = mean_range / spread_constants.get(subgroup, 2.326)
            upper = mean_of_means + a2 * mean_range
            lower = mean_of_means - a2 * mean_range
        r_upper = d4 * mean_range
        r_lower = max(d3 * mean_range, 0.0)
        violations = [index for index, value in enumerate(means) if value > upper or value < lower]
        signals = (
            _rule_signals(means - mean_of_means, sigma_of_means)
            if rules == "western_electric"
            else []
        )
        reasons = {}
        for index in violations:
            reasons.setdefault(int(index), []).append("超出 3σ 控制限")
        for index, reason in signals:
            reasons.setdefault(int(index), []).append(reason)
        flagged = sorted(reasons)
        violation_rows = [
            {
                "index": index + 1,
                "value": round(float(means[index]), 6),
                "reason": "；".join(reasons[index]),
            }
            for index in flagged
        ]
        series = pd.DataFrame(
            {
                "subgroup": range(1, len(means) + 1),
                "mean": numbers(means, 6),
                "range": numbers(ranges, 6),
            }
        )
        metrics = {
            "chart": chart,
            "subgroups": int(len(means)),
            "subgroup_size": subgroup,
            "center_line": round(mean_of_means, 6),
            "upper_control": round(upper, 6),
            "lower_control": round(lower, 6),
            "range_center": round(mean_range, 6),
            "range_upper": round(r_upper, 6),
            "sigma_of_means": round(sigma_of_means, 6),
            "rules": rules,
            "out_of_control": len(flagged),
        }
    elif chart == "cusum":
        centre = float(values.mean())
        spread = float(values.std(ddof=1)) if values.size > 1 else 1.0
        spread = max(spread, EPS)
        slack = context.number("slack", 0.5, 0.05, 2.0)
        allowed = slack * spread
        positive = np.zeros(values.size)
        negative = np.zeros(values.size)
        for index in range(1, values.size):
            positive[index] = max(0.0, positive[index - 1] + values[index] - centre - allowed)
            negative[index] = min(0.0, negative[index - 1] + values[index] - centre + allowed)
        threshold = context.number("threshold", 5.0, 1.0, 20.0) * spread
        violations = [
            index
            for index in range(values.size)
            if positive[index] > threshold or negative[index] < -threshold
        ]
        violation_rows = [
            {
                "index": index + 1,
                "value": round(float(values[index]), 6),
                "reason": "累积和超出判定界限",
            }
            for index in violations
        ]
        series = pd.DataFrame(
            {
                "index": range(1, values.size + 1),
                "value": numbers(values, 6),
                "cusum_high": numbers(positive, 6),
                "cusum_low": numbers(negative, 6),
            }
        )
        metrics = {
            "chart": chart,
            "observations": int(values.size),
            "center_line": round(centre, 6),
            "slack": slack,
            "threshold": round(threshold, 6),
            "rules": rules,
            "out_of_control": len(violations),
        }
    else:
        centre = float(values.mean())
        spread = float(values.std(ddof=1)) if values.size > 1 else 1.0
        spread = max(spread, EPS)
        smoothing = context.number("lambda", 0.2, 0.01, 1.0)
        width = context.number("width", 3.0, 1.0, 6.0)
        statistic = np.zeros(values.size)
        statistic[0] = centre
        for index in range(1, values.size):
            statistic[index] = smoothing * values[index] + (1 - smoothing) * statistic[index - 1]
        limit = width * spread * math.sqrt(smoothing / (2 - smoothing))
        violations = [
            index for index in range(values.size) if abs(statistic[index] - centre) > limit
        ]
        violation_rows = [
            {
                "index": index + 1,
                "value": round(float(statistic[index]), 6),
                "reason": "指数加权值超出控制限",
            }
            for index in violations
        ]
        series = pd.DataFrame(
            {
                "index": range(1, values.size + 1),
                "value": numbers(values, 6),
                "ewma": numbers(statistic, 6),
            }
        )
        metrics = {
            "chart": chart,
            "observations": int(values.size),
            "center_line": round(centre, 6),
            "lambda": smoothing,
            "control_limit": round(limit, 6),
            "rules": rules,
            "out_of_control": len(violations),
        }

    tables = {"series": table_of(series, limit=80)}
    if violation_table:
        tables["violations"] = table_of(
            pd.DataFrame(violation_rows, columns=["index", "value", "reason"]), limit=60
        )
    metrics["violation_table"] = bool(violation_table)
    metrics["violation_points"] = int(len(violation_rows))
    notes = [
        "落在控制限之外的点提示存在特殊原因变异，需要调查。",
        "控制限由过程自身波动计算，不是规格限。",
    ]
    if chart == "xbar_r" and rules == "western_electric":
        notes.append("已启用 Western Electric 八条准则，失控点明细给出每条点命中的判定准则。")
    if violation_table:
        notes.append("失控点明细列出被判定为异常的观测序号、取值与原因。")
    if chart == "xbar_r" and sigma_estimate == "std":
        notes.append("组内标准差改用各子组样本标准差的合并估计，控制限随之变化。")
    if control_plot:
        try:
            import matplotlib.pyplot as plt

            if chart == "xbar_r":
                positions = np.arange(1, len(means) + 1)
                fig, axes = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True)
                axes[0].plot(positions, means, marker="o", markersize=3, color="#4f7cff")
                axes[0].axhline(mean_of_means, color="#4a5568", linewidth=1.0)
                axes[0].axhline(upper, linestyle="--", color="#e24a4a", linewidth=1.2)
                axes[0].axhline(lower, linestyle="--", color="#e24a4a", linewidth=1.2)
                for position in flagged:
                    axes[0].plot(
                        positions[position], means[position], "o", color="#e24a4a", markersize=6
                    )
                axes[0].set_ylabel("子组均值")
                axes[0].set_title(f"X-bar 控制图（子组大小 {subgroup}）")
                axes[0].grid(alpha=0.3)
                axes[1].plot(positions, ranges, marker="o", markersize=3, color="#4f7cff")
                axes[1].axhline(mean_range, color="#4a5568", linewidth=1.0)
                axes[1].axhline(r_upper, linestyle="--", color="#e24a4a", linewidth=1.2)
                axes[1].axhline(r_lower, linestyle="--", color="#e24a4a", linewidth=1.2)
                axes[1].set_ylabel("子组极差")
                axes[1].set_xlabel("子组序号")
                axes[1].set_title("R 控制图")
                axes[1].grid(alpha=0.3)
                context.save(fig, "domain_control_xbar_r")
            elif chart == "cusum":
                positions = np.arange(1, values.size + 1)
                fig, axis = plt.subplots(figsize=(8, 4.5))
                axis.plot(positions, positive, color="#4f7cff", label="上侧累积和")
                axis.plot(positions, negative, color="#f0803c", label="下侧累积和")
                axis.axhline(
                    threshold,
                    linestyle="--",
                    color="#e24a4a",
                    linewidth=1.2,
                    label=f"判定界限 {threshold:.4g}",
                )
                axis.axhline(-threshold, linestyle="--", color="#e24a4a", linewidth=1.2)
                axis.set_xlabel("观测序号")
                axis.set_ylabel("累积和")
                axis.set_title(f"CUSUM 控制图（松弛量 {slack:g}σ）")
                axis.legend(fontsize=8)
                axis.grid(alpha=0.3)
                context.save(fig, "domain_control_cusum")
            else:
                positions = np.arange(1, values.size + 1)
                fig, axis = plt.subplots(figsize=(8, 4.5))
                axis.plot(positions, values, color="#9aa7bd", linewidth=1.0, label="原始观测")
                axis.plot(positions, statistic, color="#4f7cff", label=f"EWMA（λ={smoothing:g}）")
                axis.axhline(centre, color="#4a5568", linewidth=1.0)
                axis.axhline(centre + limit, linestyle="--", color="#e24a4a", linewidth=1.2)
                axis.axhline(centre - limit, linestyle="--", color="#e24a4a", linewidth=1.2)
                axis.set_xlabel("观测序号")
                axis.set_ylabel("指数加权值")
                axis.set_title("EWMA 控制图")
                axis.legend(fontsize=8)
                axis.grid(alpha=0.3)
                context.save(fig, "domain_control_ewma")
        except ImportError:
            context.warn("未安装 matplotlib，跳过控制图。")
    return registry.result(
        "domain.control",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


def capability(context):
    table = context.table
    target = table.numeric_target()
    if target is None:
        raise MethodError("过程能力分析需要数值列。")
    values = target[np.isfinite(target)]
    if values.size < 5:
        raise MethodError("过程能力分析至少需要 5 个观测。")
    lower = context.number("lower_spec")
    upper = context.number("upper_spec")
    goal = context.number("target")
    level = context.number("alpha", 0.95, 0.5, 0.999)
    subgroup = context.whole("subgroup", 1, 1, 20)
    transform = context.text("transform", "none", ("none", "yeo-johnson"))
    normality = context.flag("normality", True)
    histogram = context.flag("histogram", True)
    transform_lambda = None
    if transform == "yeo-johnson":
        from sklearn.preprocessing import PowerTransformer

        power = PowerTransformer(method="yeo-johnson", standardize=False)
        values = power.fit_transform(values.reshape(-1, 1)).ravel()
        lower = None if lower is None else float(power.transform([[lower]])[0, 0])
        upper = None if upper is None else float(power.transform([[upper]])[0, 0])
        goal = None if goal is None else float(power.transform([[goal]])[0, 0])
        transform_lambda = round(float(np.asarray(power.lambdas_).ravel()[0]), 6)
    if lower is None and upper is None:
        centre = float(values.mean())
        spread = float(values.std(ddof=1)) if values.size > 1 else 1.0
        lower, upper = centre - 3 * spread, centre + 3 * spread
        context.warn(f"未提供规格限，已按均值 ±3σ 生成：{lower:.4f} / {upper:.4f}。")
    if lower is not None and upper is not None and lower >= upper:
        raise MethodError("下规格限必须小于上规格限。")

    mean = float(values.mean())
    spread = float(values.std(ddof=1)) if values.size > 1 else 0.0
    if spread <= EPS:
        raise MethodError("标准差为 0，无法计算过程能力。")
    from scipy import stats as sps

    within = float(np.median(np.abs(np.diff(values))) / 0.6745) if values.size > 2 else spread
    if subgroup >= 2:
        if values.size < subgroup * 2:
            raise MethodError(f"子组大小 {subgroup} 需要至少 {subgroup * 2} 个观测。")
        usable = values[: (values.size // subgroup) * subgroup].reshape(-1, subgroup)
        moving = np.abs(np.diff(usable.mean(axis=1)))
        spread_constants = {
            2: 1.128,
            3: 1.693,
            4: 2.059,
            5: 2.326,
            6: 2.534,
            7: 2.704,
            8: 2.847,
            9: 2.970,
            10: 3.078,
            11: 3.173,
            12: 3.258,
            13: 3.336,
            14: 3.407,
            15: 3.472,
            16: 3.532,
            17: 3.588,
            18: 3.640,
            19: 3.689,
            20: 3.735,
        }
        within = float(moving.mean() / spread_constants.get(subgroup, 1.128)) * math.sqrt(subgroup)
    within = max(within, EPS)

    def indices(sigma):
        cp = (upper - lower) / (6 * sigma) if lower is not None and upper is not None else None
        cpu = (upper - mean) / (3 * sigma) if upper is not None else None
        cpl = (mean - lower) / (3 * sigma) if lower is not None else None
        cpk = min(value for value in (cpu, cpl) if value is not None) if (cpu or cpl) else None
        return cp, cpk, cpu, cpl

    cp, cpk, cpu, cpl = indices(spread)
    pp, ppk, _, _ = indices(within)
    bias = None if goal is None else mean - goal
    cpm = None
    if goal is not None and lower is not None and upper is not None:
        deviation = math.sqrt(spread**2 + bias**2)
        cpm = (upper - lower) / (6 * deviation) if deviation > EPS else None
    defects = 0.0
    if upper is not None:
        defects += float(1 - sps.norm.cdf((upper - mean) / spread))
    if lower is not None:
        defects += float(sps.norm.cdf((lower - mean) / spread))
    rows = pd.DataFrame(
        [
            {"index": "Cp", "value": None if cp is None else round(cp, 6), "basis": "整体标准差"},
            {
                "index": "Cpk",
                "value": None if cpk is None else round(cpk, 6),
                "basis": "整体标准差",
            },
            {
                "index": "CPU",
                "value": None if cpu is None else round(cpu, 6),
                "basis": "整体标准差",
            },
            {
                "index": "CPL",
                "value": None if cpl is None else round(cpl, 6),
                "basis": "整体标准差",
            },
            {"index": "Pp", "value": None if pp is None else round(pp, 6), "basis": "组内标准差"},
            {
                "index": "Ppk",
                "value": None if ppk is None else round(ppk, 6),
                "basis": "组内标准差",
            },
        ]
    )
    degrees = int(values.size - 1)
    lower_chi = float(sps.chi2.ppf((1 - level) / 2, degrees)) if degrees > 0 else None
    upper_chi = float(sps.chi2.ppf(1 - (1 - level) / 2, degrees)) if degrees > 0 else None
    interval_rows = []
    if cp is not None and lower_chi and upper_chi:
        interval_rows.append(
            {
                "index": "Cp",
                "lower": round(cp * math.sqrt(lower_chi / degrees), 6),
                "upper": round(cp * math.sqrt(upper_chi / degrees), 6),
            }
        )
    if cpk is not None and lower_chi and upper_chi:
        interval_rows.append(
            {
                "index": "Cpk",
                "lower": round(cpk * math.sqrt(lower_chi / degrees), 6),
                "upper": round(cpk * math.sqrt(upper_chi / degrees), 6),
            }
        )
    tables = {
        "indices": table_of(rows),
        "confidence_intervals": table_of(
            pd.DataFrame(interval_rows, columns=["index", "lower", "upper"])
        ),
    }
    normality_p = None
    normality_statistic = None
    if normality:
        if values.size < 8:
            context.warn("观测少于 8 个，跳过正态性检验。")
        else:
            normality_statistic, normality_p = sps.shapiro(values[:5000])
            normality_statistic = round(float(normality_statistic), 6)
            normality_p = round(float(normality_p), 8)
            tables["normality"] = table_of(
                pd.DataFrame(
                    [
                        {
                            "test": "Shapiro-Wilk",
                            "statistic": normality_statistic,
                            "p_value": normality_p,
                        }
                    ]
                )
            )
    if histogram:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.hist(
                values, bins="auto", density=True, color="#4f7cff", alpha=0.65, edgecolor="white"
            )
            low_edge = float(values.min()) if lower is None else min(float(values.min()), lower)
            high_edge = float(values.max()) if upper is None else max(float(values.max()), upper)
            line = np.linspace(low_edge, high_edge, 200)
            axis.plot(line, sps.norm.pdf(line, mean, spread), color="#f0803c", linewidth=1.4)
            if lower is not None:
                axis.axvline(
                    lower, color="#e24a4a", linestyle="--", linewidth=1.2, label="下规格限"
                )
            if upper is not None:
                axis.axvline(
                    upper, color="#e24a4a", linestyle="--", linewidth=1.2, label="上规格限"
                )
            if goal is not None:
                axis.axvline(goal, color="#38a169", linestyle=":", linewidth=1.2, label="目标值")
            axis.axvline(mean, color="#4a5568", linewidth=1.0, label="过程均值")
            axis.set_xlabel("观测值")
            axis.set_ylabel("密度")
            axis.set_title("过程分布与规格限")
            axis.legend(fontsize=7)
            axis.grid(alpha=0.3)
            context.save(fig, "domain_capability")
        except ImportError:
            context.warn("未安装 matplotlib，跳过能力直方图。")
    notes = [
        "Cp 只看规格宽度与过程波动的比值，Cpk 还考虑均值偏移。",
        "Cpk 大于 1.33 通常认为过程能力充足；小于 1 表示能力不足。",
        f"指数置信区间按 {level * 100:g}% 水平用卡方分布计算。",
        "给出目标值时会同时报告 Cpm，它把偏离目标的损失计入能力。",
    ]
    if subgroup >= 2:
        notes.append(f"组内标准差按子组大小 {subgroup} 的移动极差估计，用于 Pp/Ppk。")
    if normality:
        notes.append("正态性检验用于判断 Cp/Cpk 的分布假设是否成立，p 值偏小说明偏离正态。")
    if transform != "none":
        notes.append(
            f"已按 {transform} 变换后再计算能力指数，规格限同步变换到同一尺度"
            f"（λ={transform_lambda:g}）。"
        )
    metrics = {
        "observations": int(values.size),
        "mean": round(mean, 6),
        "std": round(spread, 6),
        "within_std": round(within, 6),
        "lower_spec": None if lower is None else round(lower, 6),
        "upper_spec": None if upper is None else round(upper, 6),
        "target": None if goal is None else round(goal, 6),
        "target_bias": None if bias is None else round(bias, 6),
        "confidence_level": round(float(level), 6),
        "subgroup": int(subgroup),
        "normality": bool(normality),
        "normality_statistic": normality_statistic,
        "normality_p": normality_p,
        "histogram": bool(histogram),
        "cp": None if cp is None else round(cp, 6),
        "cpk": None if cpk is None else round(cpk, 6),
        "pp": None if pp is None else round(pp, 6),
        "ppk": None if ppk is None else round(ppk, 6),
        "cpm": None if cpm is None else round(cpm, 6),
        "expected_defect_rate": round(defects, 8),
    }
    if transform != "none":
        metrics["transform"] = transform
        metrics["transform_lambda"] = transform_lambda
    return registry.result(
        "domain.capability",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


def _weibull_loglikelihood(values, shape, scale):
    shape = max(float(shape), EPS)
    scale = max(float(scale), EPS)
    return (
        values.size * math.log(shape)
        - values.size * shape * math.log(scale)
        + (shape - 1.0) * float(np.log(values).sum())
        - float(((values / scale) ** shape).sum())
    )


def _weibull_covariance(values, shape, scale):
    step_shape = max(abs(float(shape)) * 1e-4, 1e-6)
    step_scale = max(abs(float(scale)) * 1e-4, 1e-6)
    centre = _weibull_loglikelihood(values, shape, scale)
    second_shape = (
        _weibull_loglikelihood(values, shape + step_shape, scale)
        - 2.0 * centre
        + _weibull_loglikelihood(values, shape - step_shape, scale)
    ) / step_shape**2
    second_scale = (
        _weibull_loglikelihood(values, shape, scale + step_scale)
        - 2.0 * centre
        + _weibull_loglikelihood(values, shape, scale - step_scale)
    ) / step_scale**2
    cross = (
        _weibull_loglikelihood(values, shape + step_shape, scale + step_scale)
        - _weibull_loglikelihood(values, shape + step_shape, scale - step_scale)
        - _weibull_loglikelihood(values, shape - step_shape, scale + step_scale)
        + _weibull_loglikelihood(values, shape - step_shape, scale - step_scale)
    ) / (4.0 * step_shape * step_scale)
    information = -np.asarray([[second_shape, cross], [cross, second_scale]], dtype=float)
    eigenvalues, vectors = np.linalg.eigh(information)
    eigenvalues = np.where(eigenvalues <= 1e-12, 1e-12, eigenvalues)
    information = vectors @ np.diag(eigenvalues) @ vectors.T
    return np.linalg.inv(information)


def weibull(context):
    from scipy import stats as sps

    table = context.table
    curve_points = context.whole("curve_points", 60, 10, 500)
    b_life = context.number("b_life", 10.0, 1.0, 50.0)
    method = context.text("method", "mle", ("mle", "rank"))
    level = context.number("ci", 0.95, 0.5, 0.999)
    probability_plot = context.flag("probability_plot", True)
    curve_plot = context.flag("curve_plot", True)
    hazard_plot = context.flag("hazard_plot", False)
    chosen = context.want("columns")
    if chosen:
        names = [str(name).strip() for name in chosen if str(name).strip()]
        if len(names) != 1:
            raise MethodError("Weibull 分析一次只能指定一个寿命列。")
        name = names[0]
        if name in table.raw.columns:
            values = pd.to_numeric(table.raw[name], errors="coerce").to_numpy(dtype=float)
        elif name in table.feature_names:
            values = table.frame[name].to_numpy(dtype=float)
        else:
            raise MethodError(
                f"列 {name} 不在数据中。"
                f"可选：{'、'.join(str(item) for item in table.raw.columns[:12])}"
            )
    else:
        target = table.numeric_target()
        if target is None:
            raise MethodError("Weibull 分析需要寿命或失效时间列。")
        values = np.asarray(target, dtype=float)
    values = values[np.isfinite(values)]
    values = values[values > 0]
    if values.size < 5:
        raise MethodError("Weibull 分析至少需要 5 个正的失效时间。")
    if method == "rank":
        order = np.sort(values)
        count = order.size
        median_rank = (np.arange(1, count + 1) - 0.3) / (count + 0.4)
        slope, intercept = np.polyfit(np.log(order), np.log(-np.log(1.0 - median_rank)), 1)
        if not np.isfinite(slope) or float(slope) <= EPS:
            raise MethodError("秩回归得到的形状参数非正，请改用 method=mle。")
        shape = float(slope)
        scale = float(math.exp(-float(intercept) / float(slope)))
        location = 0.0
    else:
        shape, location, scale = sps.weibull_min.fit(values, floc=0)
    mean_life = float(sps.weibull_min.mean(shape, loc=0, scale=scale))
    median_life = float(sps.weibull_min.median(shape, loc=0, scale=scale))
    fraction = min(max(float(b_life) / 100.0, 1e-6), 0.999999)
    b_value = float(sps.weibull_min.ppf(fraction, shape, loc=0, scale=scale))
    at_mean = float(sps.weibull_min.sf(mean_life, shape, loc=0, scale=scale))
    z_critical = float(sps.norm.ppf(0.5 + level / 2.0))
    covariance = _weibull_covariance(values, shape, scale)
    shape_error = math.sqrt(max(float(covariance[0, 0]), 0.0))
    scale_error = math.sqrt(max(float(covariance[1, 1]), 0.0))
    factor = math.log(-math.log(1.0 - fraction))
    gradient_shape = b_value * (-factor) / max(float(shape) ** 2, EPS)
    gradient_scale = b_value / max(float(scale), EPS)
    b_variance = (
        gradient_shape**2 * float(covariance[0, 0])
        + gradient_scale**2 * float(covariance[1, 1])
        + 2.0 * gradient_shape * gradient_scale * float(covariance[0, 1])
    )
    b_error = math.sqrt(max(b_variance, 0.0))

    grid = np.linspace(max(values.min() * 0.5, 1e-9), values.max() * 1.5, curve_points)
    rows = pd.DataFrame(
        {
            "time": numbers(grid, 4),
            "reliability": numbers(sps.weibull_min.sf(grid, shape, loc=0, scale=scale), 6),
            "hazard": numbers(
                sps.weibull_min.pdf(grid, shape, loc=0, scale=scale)
                / np.clip(sps.weibull_min.sf(grid, shape, loc=0, scale=scale), 1e-12, None),
                6,
            ),
        }
    )
    if curve_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.plot(grid, sps.weibull_min.sf(grid, shape, loc=0, scale=scale), color="#4f7cff")
            axis.set_xlabel("时间")
            axis.set_ylabel("可靠度 R(t)")
            axis.set_title(f"Weibull 可靠度曲线（形状 k={shape:.3f}）")
            axis.grid(alpha=0.3)
            context.save(fig, "domain_weibull")
        except ImportError:
            context.warn("未安装 matplotlib，跳过可靠度曲线。")

    if hazard_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.plot(grid, np.asarray(rows["hazard"], dtype=float), color="#f0803c")
            axis.set_xlabel("时间")
            axis.set_ylabel("失效率 h(t)")
            axis.set_title(f"Weibull 失效率曲线（形状 k={shape:.3f}）")
            axis.grid(alpha=0.3)
            context.save(fig, "domain_weibull_hazard")
        except ImportError:
            context.warn("未安装 matplotlib，跳过失效率曲线。")

    if probability_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7, 4.5))
            order = np.sort(values)
            ranks = (np.arange(1, order.size + 1) - 0.3) / (order.size + 0.4)
            axis.plot(
                np.log(order),
                np.log(-np.log(1.0 - ranks)),
                "o",
                markersize=3,
                color="#4f7cff",
                label="经验分位",
            )
            line = np.linspace(float(order.min()), float(order.max()), 100)
            axis.plot(
                np.log(line),
                np.log(-np.log(1.0 - sps.weibull_min.cdf(line, shape, loc=0, scale=scale))),
                color="#f0803c",
                label=f"拟合曲线 k={shape:.3f}",
            )
            axis.set_xlabel("ln(时间)")
            axis.set_ylabel("ln(−ln(1−F))")
            axis.set_title("Weibull 概率图")
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3)
            context.save(fig, "domain_weibull_probability")
        except ImportError:
            context.warn("未安装 matplotlib，跳过概率图。")

    if shape < 1:
        behaviour = "早期失效型（失效率递减）"
    elif shape < 1.3:
        behaviour = "随机失效型（失效率近似恒定）"
    else:
        behaviour = "耗损型（失效率递增）"
    notes = [
        "形状参数 k<1 表示早期失效，k≈1 表示随机失效，k>1 表示耗损失效。",
        f"B{b_life:g} 寿命是累积失效达到 {b_life:g}%（可靠度降到 {100 - b_life:g}%）的时间，"
        f"是可靠性设计常用指标。",
        f"可靠度曲线按 {curve_points} 个时间点等距输出。",
        f"形状、尺度与 B{b_life:g} 寿命的 {level * 100:g}% 置信区间由观测信息矩阵近似得到。",
    ]
    if method == "rank":
        notes.append("参数估计用中位秩回归（概率图最小二乘），对极端值更稳健但不是最大似然。")
    if probability_plot:
        notes.append("概率图上点越接近直线，说明 Weibull 分布拟合越好。")
    if hazard_plot:
        notes.append("失效率曲线直接展示 h(t) 随时间的走向，便于判断失效阶段。")
    return registry.result(
        "domain.weibull",
        table,
        metrics={
            "observations": int(values.size),
            "shape": round(float(shape), 6),
            "scale": round(float(scale), 6),
            "location": round(float(location), 6),
            "method": method,
            "confidence_level": round(float(level), 6),
            "z_critical": round(z_critical, 6),
            "shape_se": round(shape_error, 6),
            "scale_se": round(scale_error, 6),
            "shape_ci_low": round(max(float(shape) - z_critical * shape_error, EPS), 6),
            "shape_ci_high": round(float(shape) + z_critical * shape_error, 6),
            "scale_ci_low": round(max(float(scale) - z_critical * scale_error, EPS), 6),
            "scale_ci_high": round(float(scale) + z_critical * scale_error, 6),
            "curve_points": int(curve_points),
            "probability_plot": bool(probability_plot),
            "b_life_percent": round(float(b_life), 6),
            "mean_life": round(mean_life, 6),
            "median_life": round(median_life, 6),
            "b10_life": round(b_value, 6),
            "b_life_ci_low": round(max(b_value - z_critical * b_error, 0.0), 6),
            "b_life_ci_high": round(b_value + z_critical * b_error, 6),
            "reliability_at_mean": round(at_mean, 6),
            "failure_behaviour": behaviour,
        },
        tables={"reliability_curve": table_of(rows, limit=curve_points)},
        notes=notes,
    )
