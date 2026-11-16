"""Existing domain meta algorithms; registered by engine.methods.domain."""

import math

import numpy as np
import pandas as pd

from engine import registry
from engine.registry import MethodError, numbers, table_of

EPS = 1e-12


def _paule_mandel_tau(effects, variances, dfree):
    tau = 0.0
    for _ in range(200):
        weights = 1.0 / (variances + tau)
        mean = float((effects * weights).sum() / weights.sum())
        q_value = float((weights * (effects - mean) ** 2).sum())
        denominator = float(weights.sum() - (weights**2).sum() / weights.sum())
        if denominator <= EPS:
            return 0.0
        updated = max(0.0, (q_value - dfree) / denominator)
        if abs(updated - tau) < 1e-12:
            return updated
        tau = updated
    return tau


def _reml_tau(effects, variances):
    def objective(tau):
        weights = 1.0 / (variances + tau)
        mean = float((effects * weights).sum() / weights.sum())
        return 0.5 * (
            float(np.log(variances + tau).sum())
            + math.log(float(weights.sum()))
            + float((weights * (effects - mean) ** 2).sum())
        )

    spread = float(effects.std(ddof=1)) if effects.size > 1 else 1.0
    from scipy.optimize import minimize_scalar

    result = minimize_scalar(objective, bounds=(0.0, max(spread * 10.0, 1e-6)), method="bounded")
    return max(0.0, float(result.x))


def meta_analysis(context):
    import statsmodels.api as sm
    from scipy import stats as sps

    table = context.table
    effect = context.text("effect_column")
    variance = context.text("variance_column")
    spread_kind = context.text("spread_kind", "auto", ("auto", "variance", "se"))
    model_choice = context.text("model", "random", ("fixed", "random", "both"))
    tau_method = context.text("tau_method", "dl", ("dl", "reml", "pm"))
    level = context.number("alpha", 0.05, 1e-6, 0.5)
    egger = context.flag("egger", True)
    funnel_plot = context.flag("funnel_plot", True)
    forest_plot = context.flag("forest_plot", True)
    raw = table.raw
    from engine.dataset_selection import semantic_column

    effect = semantic_column(raw.columns, "effect_column", effect)
    variance = semantic_column(raw.columns, "variance_column", variance)
    if not effect or not variance:
        raise MethodError(
            "Meta 分析需要真实的效应量列与方差（或标准误）列，请明确指定，不能用普通测量列代替。"
        )
    if effect == variance:
        raise MethodError("效应量与方差/标准误必须是不同列。")
    if spread_kind == "auto":
        lowered = str(variance).strip().lower()
        if lowered in ("se", "stderr", "standard_error", "标准误"):
            spread_kind = "se"
        elif lowered in ("variance", "var", "vi", "方差"):
            spread_kind = "variance"
        else:
            raise MethodError(
                "请用 spread_kind 明确该列是 variance（方差）还是 se（标准误），不能根据数值大小猜测。"
            )

    values = pd.to_numeric(raw[effect], errors="coerce")
    spread = pd.to_numeric(raw[variance], errors="coerce")
    keep = values.notna() & spread.notna() & (spread > 0)
    if keep.sum() < 3:
        raise MethodError("Meta 分析至少需要 3 个有效研究。")
    effects = values[keep].to_numpy(dtype=float)
    variance_values = spread[keep].to_numpy(dtype=float)
    if spread_kind == "se":
        variance_values = variance_values**2

    fixed = 1.0 / variance_values
    fixed_mean = float((effects * fixed).sum() / fixed.sum())
    fixed_se = float(math.sqrt(1.0 / fixed.sum()))
    q = float((fixed * (effects - fixed_mean) ** 2).sum())
    dfree = len(effects) - 1
    q_p = float(1 - sps.chi2.cdf(q, dfree)) if dfree > 0 else None
    i_squared = max(0.0, (q - dfree) / q) * 100 if q > 0 else 0.0
    tau_squared = (
        max(0.0, (q - dfree) / (fixed.sum() - (fixed**2).sum() / fixed.sum()))
        if fixed.sum() > 0
        else 0.0
    )
    if tau_method == "pm":
        tau_squared = _paule_mandel_tau(effects, variance_values, dfree)
    elif tau_method == "reml":
        tau_squared = _reml_tau(effects, variance_values)

    random = 1.0 / (variance_values + tau_squared)
    random_mean = float((effects * random).sum() / random.sum())
    random_se = float(math.sqrt(1.0 / random.sum()))
    z_critical = float(sps.norm.ppf(1 - level / 2.0))
    fixed_low = fixed_mean - z_critical * fixed_se
    fixed_high = fixed_mean + z_critical * fixed_se
    random_low = random_mean - z_critical * random_se
    random_high = random_mean + z_critical * random_se
    if model_choice == "fixed":
        pooled_mean, pooled_se = fixed_mean, fixed_se
        ci_low, ci_high = fixed_low, fixed_high
    else:
        pooled_mean, pooled_se = random_mean, random_se
        ci_low, ci_high = random_low, random_high
    z_value = pooled_mean / pooled_se if pooled_se > 0 else 0.0
    p_value = float(2 * (1 - sps.norm.cdf(abs(z_value))))

    rows = pd.DataFrame(
        {
            "study": range(1, len(effects) + 1),
            "effect": numbers(effects, 6),
            "variance": numbers(variance_values, 6),
            "weight_fixed": numbers(fixed / fixed.sum(), 6),
            "weight_random": numbers(random / random.sum(), 6),
        }
    )
    if funnel_plot:
        try:
            import matplotlib.pyplot as plt

            errors = np.sqrt(variance_values)
            fig, axis = plt.subplots(figsize=(7, 4.5))
            axis.scatter(pooled_mean - effects, errors, color="#4f7cff")
            axis.axvline(0, color="#9aa7bd", linewidth=1.0)
            axis.axvline(ci_low - pooled_mean, linestyle="--", color="#f0803c", linewidth=1.0)
            axis.axvline(ci_high - pooled_mean, linestyle="--", color="#f0803c", linewidth=1.0)
            axis.set_xlabel("效应量 − 合并效应")
            axis.set_ylabel("标准误")
            axis.set_title(f"漏斗图（{model_choice}，{100 * (1 - level):g}% 区间）")
            axis.grid(alpha=0.3)
            context.save(fig, "domain_meta")
        except ImportError:
            context.warn("未安装 matplotlib，跳过漏斗图。")

    if forest_plot:
        try:
            import matplotlib.pyplot as plt

            errors = z_critical * np.sqrt(variance_values)
            positions = np.arange(1, effects.size + 1)
            fig, axis = plt.subplots(figsize=(7, min(max(4.5, 0.18 * effects.size + 2), 12.0)))
            axis.errorbar(
                effects,
                positions,
                xerr=errors,
                fmt="o",
                markersize=3,
                color="#4f7cff",
                ecolor="#9aa7bd",
                elinewidth=1.0,
            )
            axis.axvline(pooled_mean, color="#e24a4a", linewidth=1.2, label="合并效应")
            axis.axvline(ci_low, linestyle="--", color="#e24a4a", linewidth=1.0)
            axis.axvline(ci_high, linestyle="--", color="#e24a4a", linewidth=1.0)
            axis.axvline(0.0, color="#4a5568", linewidth=1.0)
            axis.set_xlabel("效应量")
            axis.set_ylabel("研究序号")
            axis.set_title(f"森林图（{model_choice} 模型，{100 * (1 - level):g}% 区间）")
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3)
            context.save(fig, "domain_meta_forest")
        except ImportError:
            context.warn("未安装 matplotlib，跳过森林图。")

    metrics = {
        "studies": int(len(effects)),
        "effect_column": effect,
        "variance_column": variance,
        "model": model_choice,
        "tau_method": tau_method,
        "funnel_plot": bool(funnel_plot),
        "egger": bool(egger),
        "alpha": round(float(level), 6),
        "z_critical": round(z_critical, 6),
        "pooled_effect": round(pooled_mean, 6),
        "pooled_se": round(pooled_se, 6),
        "fixed_effect": round(fixed_mean, 6),
        "fixed_se": round(fixed_se, 6),
        "fixed_ci_low": round(fixed_low, 6),
        "fixed_ci_high": round(fixed_high, 6),
        "random_effect": round(random_mean, 6),
        "random_se": round(random_se, 6),
        "random_ci_low": round(random_low, 6),
        "random_ci_high": round(random_high, 6),
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "z_value": round(z_value, 6),
        "p_value": round(p_value, 8),
        "q_statistic": round(q, 6),
        "q_p_value": None if q_p is None else round(q_p, 8),
        "i_squared": round(float(i_squared), 4),
        "tau_squared": round(float(tau_squared), 6),
        "heterogeneity": ("低" if i_squared < 25 else "中" if i_squared < 75 else "高"),
    }
    tables = {"studies": table_of(rows, limit=80)}
    if egger:
        precision = 1.0 / np.sqrt(variance_values)
        normalized = effects * precision
        egger_fit = sm.OLS(normalized, sm.add_constant(precision)).fit()
        intercept = float(egger_fit.params[0])
        intercept_error = float(egger_fit.bse[0])
        intercept_p = float(egger_fit.pvalues[0])
        metrics["egger_intercept"] = round(intercept, 6)
        metrics["egger_std_error"] = round(intercept_error, 6)
        metrics["egger_p_value"] = round(intercept_p, 8)
        tables["egger"] = table_of(
            pd.DataFrame(
                [
                    {
                        "test": "Egger 回归截距",
                        "intercept": round(intercept, 6),
                        "std_error": round(intercept_error, 6),
                        "p_value": round(intercept_p, 8),
                    }
                ]
            )
        )
    notes = [
        "固定效应用于研究间同质的情形；随机效应允许真实效应随研究变化。",
        f"当前合并模型为 {model_choice}，显著性水平 {level:g}（z={z_critical:.4f}）。",
        "I² 表示总变异中由异质性贡献的比例，超过 75% 说明异质性很大。",
        "漏斗图用效应量偏差对标准误作图，可以用来观察发表偏倚。",
    ]
    if tau_method == "reml":
        notes.append("异质性方差用限制最大似然（REML）估计，通常比 DerSimonian-Laird 更稳。")
    elif tau_method == "pm":
        notes.append("异质性方差用 Paule-Mandel 迭代估计，在少数研究时表现更好。")
    if egger:
        notes.append(
            "Egger 检验以效应量标准化的回归截距判断漏斗图是否对称，截距显著偏离 0 提示发表偏倚。"
        )
    if spread_kind == "variance":
        notes.append("方差列按方差直接解读，不做标准误平方转换。")
    elif spread_kind == "se":
        notes.append("方差列按标准误解读，已平方转换为方差。")
    return registry.result(
        "domain.meta",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )
