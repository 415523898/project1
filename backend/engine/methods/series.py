import math

import numpy as np
import pandas as pd

from engine import registry
from engine.registry import MethodError, numbers, register, table_of

EPS = 1e-12


def _series(context):
    table = context.table
    from engine.integrity import require_regular_time

    require_regular_time(table)
    values = table.numeric_target()
    if values is None:
        raise MethodError("时间序列方法需要一个数值列。")
    values = np.asarray(values, dtype=float)
    keep = np.isfinite(values)
    if not keep.all():
        raise MethodError(
            "时间序列含缺失或非有限观测；直接删除会压缩时间间隔，请先明确插补或缺失处理策略。"
        )
    if values.size < 8:
        raise MethodError("时间序列至少需要 8 个有效观测。")
    return values


def _multi_series(context):
    table = context.table
    from engine.integrity import require_regular_time

    require_regular_time(table)
    matrix = table.matrix()
    if matrix.shape[1] < 2:
        raise MethodError("多变量时间序列至少需要两列。")
    if matrix.shape[0] < 12:
        raise MethodError("多变量时间序列至少需要 12 个观测。")
    return matrix, table.feature_names


def _acf(values, nlags):
    from statsmodels.tsa.stattools import acf

    series = np.asarray(values, dtype=float)
    limit = max(int(series.size // 2) - 1, 1)
    return np.asarray(acf(series, nlags=max(min(int(nlags), limit), 1), fft=False), dtype=float)


def _pacf(values, nlags):
    from statsmodels.tsa.stattools import pacf

    series = np.asarray(values, dtype=float)
    limit = max(int(series.size // 2) - 1, 1)
    return np.asarray(pacf(series, nlags=max(min(int(nlags), limit), 1), method="ywm"), dtype=float)


def _pick_matrix_var(context, names, role):
    picked = context.text("cause", "first", ("first", "second"))
    if picked == "second" and len(names) < 2:
        raise MethodError(f"{role}需要至少两个变量，当前只有 {len(names)} 个。")
    return 0 if picked == "first" else 1


def _trend_for_arima(context, differences=0):
    trend = context.text("trend", "c", ("n", "c", "t", "ct"))
    if differences > 0 and trend == "c":
        return "t"
    return trend


def _adf_figure(context, values, labels, rolling_window, acf_lags):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过平稳性诊断图。")
        return []
    figure = plt.figure(figsize=(11, 7))
    grid = figure.add_gridspec(2, 2)
    top = figure.add_subplot(grid[0, :])
    bottom_left = figure.add_subplot(grid[1, 0])
    bottom_right = figure.add_subplot(grid[1, 1])
    window = max(2, min(int(rolling_window), max(values.size // 2, 2)))
    rolling_mean = pd.Series(values).rolling(window).mean().to_numpy()
    rolling_std = pd.Series(values).rolling(window).std().to_numpy()
    top.plot(range(1, values.size + 1), values, color="#374151", label="原始序列")
    top.plot(range(1, values.size + 1), rolling_mean, color="#4f7cff", label=f"{window} 点滚动均值")
    top.plot(
        range(1, values.size + 1), rolling_std, color="#ef4444", label=f"{window} 点滚动标准差"
    )
    top.set_title("序列与滚动统计量")
    top.legend(fontsize=8)
    top.grid(alpha=0.3)
    if labels:
        top.set_xlabel(labels[0])
    for axis, kind, series in (
        (bottom_left, "ACF", _acf(values, acf_lags)),
        (bottom_right, "PACF", _pacf(values, acf_lags)),
    ):
        lags = np.arange(series.size)
        axis.axhline(0, color="#6b7280", linewidth=0.8)
        axis.vlines(lags, 0, series, color="#4f7cff")
        limit = 1.959964 / math.sqrt(max(values.size, 1))
        axis.axhline(limit, color="#ef4444", linestyle="--", linewidth=0.8)
        axis.axhline(-limit, color="#ef4444", linestyle="--", linewidth=0.8)
        axis.set_title(f"{kind}（{series.size - 1} 阶）")
        axis.grid(alpha=0.3)
    figure.tight_layout()
    return _saved(context, figure, "series_adf_stationarity")


def _saved(context, figure, name):
    saved = context.save(figure, name)
    return [saved] if saved else []


@register("series.adf")
def adf(context):
    from statsmodels.tsa.stattools import adfuller, kpss

    values = _series(context)
    regression = context.text("regression", "c", ("c", "ct", "n"))
    selection = context.text("autolag", "AIC", ("AIC", "BIC", "t-stat", "none"))
    max_lag = context.whole("max_lag", None, 1, 50)
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    rolling_window = context.whole("rolling_window", 12, 2, 100)
    acf_lags = context.whole("acf_lags", None, 1, 100)
    trend_terms = {"n": 0, "c": 1, "ct": 2}[regression]
    feasible = int(values.size // 2) - 2 - trend_terms
    if max_lag is not None and feasible >= 1:
        max_lag = min(max_lag, feasible)
    outcome = adfuller(
        values,
        maxlag=max_lag,
        regression=regression,
        autolag=None if selection == "none" else selection,
    )
    statistic, pvalue, used = float(outcome[0]), float(outcome[1]), int(outcome[2])
    critical = outcome[4] if len(outcome) > 4 and isinstance(outcome[4], dict) else {}

    kpss_test = context.flag("kpss_test", True)
    kpss_regression = context.text("kpss_regression", "c", ("c", "ct"))
    kpss_setting = context.text("kpss_lags", "auto", ("auto", "legacy", "custom"))
    kpss_custom = context.whole("kpss_truncation", 12, 1, 200)
    kpss_alpha = context.number("kpss_alpha", 0.05, 1e-6, 0.5)
    if kpss_setting == "custom" and kpss_custom is None and kpss_test:
        raise MethodError("kpss_lags 设为 custom 时必须给出正的滞后截断阶数。")
    kpss_lags = {"auto": "auto", "legacy": "legacy"}.get(kpss_setting, kpss_custom)
    kpss_stat, kpss_p, kpss_critical, kpss_used = None, None, {}, None
    if kpss_test:
        try:
            outcome_kpss = kpss(values, regression=kpss_regression, nlags=kpss_lags)
            kpss_stat, kpss_p = float(outcome_kpss[0]), float(outcome_kpss[1])
            kpss_used = int(outcome_kpss[2])
            kpss_critical = outcome_kpss[3] if isinstance(outcome_kpss[3], dict) else {}
        except Exception as error:
            context.warn(f"KPSS 检验未完成：{error}")

    rows = pd.DataFrame(
        {
            "test": ["ADF", "KPSS"],
            "statistic": [
                round(float(statistic), 6),
                None if kpss_stat is None else round(kpss_stat, 6),
            ],
            "p_value": [round(float(pvalue), 8), None if kpss_p is None else round(kpss_p, 8)],
            "null_hypothesis": ["存在单位根（非平稳）", "序列平稳"],
        }
    )
    notes = [
        f"ADF 的原假设是“存在单位根”，p 小于 {alpha:g} 才拒绝，认为平稳。",
        f"ADF 的滞后阶数按 {selection} 准则挑选，none 表示完全采用你填写的最大滞后阶数。",
    ]
    if kpss_test:
        notes.append(
            f"KPSS 的原假设相反，p 大于 {alpha:g} 才认为平稳；"
            f"确定性项用 {kpss_regression}，滞后截断用 {kpss_setting}。"
        )
    else:
        notes.append("已关闭 KPSS 交叉验证，只有 ADF 一个结论。")
    stationarity_plot = context.flag("stationarity_plot", True)
    if stationarity_plot:
        plot_lags = acf_lags if acf_lags is not None else min(40, max(10, values.size // 2))
        _adf_figure(context, values, [str(values.size) + " 个观测"], rolling_window, plot_lags)
    return registry.result(
        "series.adf",
        context.table,
        metrics={
            "observations": int(values.size),
            "regression": regression,
            "autolag": selection,
            "max_lag": max_lag,
            "alpha": alpha,
            "kpss_alpha": kpss_alpha,
            "rolling_window": int(rolling_window),
            "stationarity_plot": bool(stationarity_plot),
            "acf_plot_lags": int(
                acf_lags if acf_lags is not None else min(40, max(10, values.size // 2))
            ),
            "adf_lags_used": int(used),
            "adf_statistic": round(float(statistic), 6),
            "adf_p_value": round(float(pvalue), 8),
            "lags_used": int(used),
            "stationary_by_adf": bool(pvalue < alpha),
            "critical_values": {key: round(float(value), 6) for key, value in critical.items()},
            "kpss_test": bool(kpss_test),
            "kpss_regression": kpss_regression,
            "kpss_lags": kpss_setting,
            "kpss_lags_used": kpss_used,
            "kpss_statistic": None if kpss_stat is None else round(kpss_stat, 6),
            "kpss_p_value": None if kpss_p is None else round(kpss_p, 8),
            "kpss_critical_values": {
                key: round(float(value), 6) for key, value in kpss_critical.items()
            },
            "stationary_by_kpss": None if kpss_p is None else bool(kpss_p > alpha),
        },
        tables={"tests": table_of(rows)},
        notes=notes,
    )


def _ljung_box_p(residuals, lags):
    from statsmodels.stats.diagnostic import acorr_ljungbox

    try:
        frame = acorr_ljungbox(residuals, lags=[int(lags)], return_df=True)
        return float(frame["lb_pvalue"].iloc[0])
    except Exception:
        return None


def _arima_order(context):
    order = _order(context)
    max_p = context.whole("max_p", 5, 0, 12)
    max_q = context.whole("max_q", 5, 0, 12)
    if order[0] > max_p:
        raise MethodError(f"自回归阶数 p={order[0]} 超过 max_p={max_p}，请调大 max_p 或调小 p。")
    if order[2] > max_q:
        raise MethodError(f"移动平均阶数 q={order[2]} 超过 max_q={max_q}，请调大 max_q 或调小 q。")
    return order


@register("series.arima")
def arima(context):
    from statsmodels.tsa.arima.model import ARIMA

    values = _series(context)
    order = _arima_order(context)
    horizon = context.whole("horizon", 10, 1, 200)
    trend = _trend_for_arima(context, order[1])
    stationarity = context.flag("enforce_stationarity", True)
    invertibility = context.flag("enforce_invertibility", True)
    confidence = context.number("conf_level", 0.95, 0.5, 0.999)
    residual_test = context.flag("residual_test", True)
    residual_lags = context.whole("residual_lags", None, 1, 50)
    model = ARIMA(
        values,
        order=order,
        trend=trend,
        enforce_stationarity=stationarity,
        enforce_invertibility=invertibility,
    )
    try:
        fitted = model.fit()
    except Exception as error:
        raise MethodError(f"ARIMA({order[0]},{order[1]},{order[2]}) 拟合失败：{error}")
    if not fitted.mle_retvals.get("converged", True):
        context.warn("ARIMA 未收敛，结果仅供参考，可尝试简化阶数。")

    forecast = fitted.get_forecast(steps=horizon)
    mean = np.asarray(forecast.predicted_mean, dtype=float)
    interval = np.asarray(forecast.conf_int(alpha=1 - confidence))
    rows = pd.DataFrame(
        {
            "step": range(1, horizon + 1),
            "forecast": numbers(mean, 6),
            "lower": numbers(interval[:, 0], 6),
            "upper": numbers(interval[:, 1], 6),
        }
    )
    residuals = np.asarray(fitted.resid, dtype=float)
    lags = residual_lags if residual_lags is not None else min(10, max(len(residuals) // 5, 1))
    ljung_p = _ljung_box_p(residuals, lags) if residual_test else None

    figures = []
    order_plot = context.flag("order_plot", True)
    if order_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(9, 4))
            axis.plot(range(len(values)), values, label="历史", color="#374151")
            axis.plot(
                range(len(values), len(values) + horizon), mean, label="预测", color="#4f7cff"
            )
            axis.fill_between(
                range(len(values), len(values) + horizon),
                interval[:, 0],
                interval[:, 1],
                color="#4f7cff",
                alpha=0.2,
                label=f"{confidence * 100:g}% 区间",
            )
            axis.set_title(f"ARIMA{order} 预测")
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3)
            name = context.save(fig, "series_arima")
            if name:
                figures.append(name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过预测图。")

    notes = [
        "ARIMA(p,d,q)：p 自回归阶数，d 差分次数，q 移动平均阶数。",
        f"趋势项 trend={trend}，n 无常数，c 常数，t 线性趋势，ct 两者都有"
        + (
            "；d 大于 0 时低于差分阶数的趋势项会被差分消掉，已自动提升到线性趋势。"
            if order[1] > 0 and context.text("trend", "c", ("n", "c", "t", "ct")) == "c"
            else "。"
        ),
        f"预测区间按 {confidence * 100:g}% 置信水平计算。",
    ]
    if residual_test:
        notes.append(f"Ljung-Box 检验用 {lags} 阶滞后，p 值大于 0.05 说明残差已经没有明显自相关。")
    else:
        notes.append("已关闭残差诊断，未计算 Ljung-Box 统计量。")
    return registry.result(
        "series.arima",
        context.table,
        metrics={
            "order": list(order),
            "observations": int(values.size),
            "horizon": horizon,
            "order_plot": bool(order_plot),
            "trend": trend,
            "max_p": context.whole("max_p", 5, 0, 12),
            "max_q": context.whole("max_q", 5, 0, 12),
            "enforce_stationarity": bool(stationarity),
            "enforce_invertibility": bool(invertibility),
            "conf_level": confidence,
            "residual_test": bool(residual_test),
            "residual_lags": int(lags) if residual_test else None,
            "aic": round(float(fitted.aic), 6),
            "bic": round(float(fitted.bic), 6),
            "log_likelihood": round(float(fitted.llf), 6),
            "residual_std": round(float(np.nanstd(residuals)), 6),
            "converged": bool(fitted.mle_retvals.get("converged", True)),
            "ljung_box_p": None if ljung_p is None else round(ljung_p, 8),
            "next_forecast": round(float(mean[0]), 6),
        },
        tables={"forecast": table_of(rows, limit=horizon)},
        figures=figures,
        notes=notes,
    )


def _order(context):
    p = context.whole("p", 1, 0, 10)
    d = context.whole("d", 1, 0, 3)
    q = context.whole("q", 1, 0, 10)
    return (p, d, q)


def _seasonal_order(context, season):
    return (
        context.whole("seasonal_p", 1, 0, 3),
        context.whole("seasonal_d", 0, 0, 2),
        context.whole("seasonal_q", 1, 0, 3),
        season,
    )


def _sarima_order(context, values, seasonal, trend, stationarity, invertibility):
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    order = _order(context)
    choice = context.text("order_selection", "fixed", ("fixed", "aic", "bic", "hqic"))
    max_p = context.whole("max_p", 5, 0, 12)
    max_q = context.whole("max_q", 5, 0, 12)
    if choice == "fixed":
        if order[0] > max_p:
            raise MethodError(
                f"自回归阶数 p={order[0]} 超过 max_p={max_p}，请调大 max_p 或调小 p。"
            )
        if order[2] > max_q:
            raise MethodError(
                f"移动平均阶数 q={order[2]} 超过 max_q={max_q}，请调大 max_q 或调小 q。"
            )
        return order, [], 0
    candidates = [(p, order[1], q) for p in range(max_p + 1) for q in range(max_q + 1)]
    fitted = []
    for candidate in candidates:
        try:
            result = SARIMAX(
                values,
                order=candidate,
                seasonal_order=seasonal,
                trend=trend,
                enforce_stationarity=stationarity,
                enforce_invertibility=invertibility,
            ).fit(disp=False)
        except Exception:
            continue
        fitted.append(
            {
                "order": candidate,
                "aic": round(float(result.aic), 6),
                "bic": round(float(result.bic), 6),
                "hqic": round(float(result.hqic), 6),
            }
        )
    usable = [item for item in fitted if item.get(choice) is not None]
    if not usable:
        context.warn(f"按 {choice} 自动定阶全部失败，改用固定阶数 p={order[0]}、q={order[2]}。")
        return order, fitted, 0
    best = min(usable, key=lambda item: item[choice])
    if best["order"] != order:
        context.warn(f"按 {choice} 把阶数从 {order} 调整为 {best['order']}。")
    return best["order"], fitted, len(usable)


def _sarima_forecast_figure(
    context, values, fitted, mean, interval, confidence, horizon, order, seasonal
):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过预测图。")
        return []
    history = np.asarray(fitted.fittedvalues, dtype=float)
    figure, axis = plt.subplots(figsize=(9.5, 4.2))
    axis.plot(range(1, values.size + 1), values, color="#374151", label="历史")
    axis.plot(range(1, values.size + 1), history, color="#10b981", linewidth=1.0, label="拟合")
    steps = range(values.size + 1, values.size + horizon + 1)
    axis.plot(steps, mean, color="#4f7cff", label="预测")
    axis.fill_between(
        list(steps),
        interval[:, 0],
        interval[:, 1],
        color="#4f7cff",
        alpha=0.2,
        label=f"{confidence * 100:g}% 区间",
    )
    axis.set_title(f"SARIMA{order}×{seasonal} 拟合与预测")
    axis.legend(fontsize=8)
    axis.grid(alpha=0.3)
    return _saved(context, figure, "series_sarima")


def _sarima_residual_figure(context, residuals, lags):
    try:
        import matplotlib.pyplot as plt
        from scipy import stats as sps
    except ImportError:
        context.warn("未安装 matplotlib，跳过残差诊断图。")
        return []
    figure, axes = plt.subplots(2, 2, figsize=(10.5, 6))
    axes[0][0].plot(range(1, residuals.size + 1), residuals, color="#374151")
    axes[0][0].axhline(0, color="#ef4444", linewidth=0.8)
    axes[0][0].set_title("残差序列")
    axes[0][0].grid(alpha=0.3)
    axes[0][1].hist(
        residuals, bins=min(20, max(5, residuals.size // 5)), color="#4f7cff", alpha=0.75
    )
    axes[0][1].set_title("残差分布")
    axes[0][1].grid(alpha=0.3)
    series = _acf(residuals, lags)
    axes[1][0].axhline(0, color="#6b7280", linewidth=0.8)
    axes[1][0].vlines(np.arange(series.size), 0, series, color="#4f7cff")
    limit = 1.959964 / math.sqrt(max(residuals.size, 1))
    axes[1][0].axhline(limit, color="#ef4444", linestyle="--", linewidth=0.8)
    axes[1][0].axhline(-limit, color="#ef4444", linestyle="--", linewidth=0.8)
    axes[1][0].set_title(f"残差 ACF（{series.size - 1} 阶）")
    axes[1][0].grid(alpha=0.3)
    spread = float(np.nanstd(residuals))
    if spread > EPS:
        sps.probplot(residuals / spread, dist="norm", plot=axes[1][1])
        axes[1][1].set_title("残差正态 Q-Q 图")
    axes[1][1].grid(alpha=0.3)
    figure.tight_layout()
    return _saved(context, figure, "series_sarima_residuals")


@register("series.sarima")
def sarima(context):
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    values = _series(context)
    season = context.whole("seasonal_period", 12, 2, 365)
    seasonal = _seasonal_order(context, season)
    sd = seasonal[1]
    horizon = context.whole("horizon", season, 1, 400)
    requested_trend = context.text("trend", "c", ("n", "c", "t", "ct"))
    stationarity = context.flag("enforce_stationarity", False)
    invertibility = context.flag("enforce_invertibility", False)
    confidence = context.number("conf_level", 0.95, 0.5, 0.999)
    residual_test = context.flag("residual_test", True)
    residual_lags = context.whole("residual_lags", None, 1, 100)
    selection_trend = (
        "t"
        if (context.whole("d", 1, 0, 3) + sd) > 0 and requested_trend == "c"
        else requested_trend
    )
    order, compared, compared_count = _sarima_order(
        context, values, seasonal, selection_trend, stationarity, invertibility
    )
    trend = "t" if (order[1] + sd) > 0 and requested_trend == "c" else requested_trend
    model = SARIMAX(
        values,
        order=order,
        seasonal_order=seasonal,
        trend=trend,
        enforce_stationarity=stationarity,
        enforce_invertibility=invertibility,
    )
    try:
        fitted = model.fit(disp=False)
    except Exception as error:
        raise MethodError(f"SARIMA 拟合失败：{error}")
    if not fitted.mle_retvals.get("converged", True):
        context.warn("SARIMA 未收敛，结果仅供参考，可尝试简化阶数。")

    forecast = fitted.get_forecast(steps=horizon)
    mean = np.asarray(forecast.predicted_mean, dtype=float)
    interval = np.asarray(forecast.conf_int(alpha=1 - confidence))
    rows = pd.DataFrame(
        {
            "step": range(1, horizon + 1),
            "forecast": numbers(mean, 6),
            "lower": numbers(interval[:, 0], 6),
            "upper": numbers(interval[:, 1], 6),
        }
    )
    residuals = np.asarray(fitted.resid, dtype=float)
    lags = residual_lags if residual_lags is not None else min(12, max(season, 1))
    ljung_p = _ljung_box_p(residuals, lags) if residual_test else None
    seasonal_lags = context.whole("seasonal_lags", 0, 0, 200)
    figures = []
    forecast_plot = context.flag("forecast_plot", True)
    if forecast_plot:
        figures.extend(
            _sarima_forecast_figure(
                context, values, fitted, mean, interval, confidence, horizon, order, seasonal
            )
        )
    residual_plot = context.flag("residual_plot", True)
    if residual_plot:
        figures.extend(
            _sarima_residual_figure(context, residuals, seasonal_lags if seasonal_lags else lags)
        )
    notes = [
        "季节项 (P,D,Q,s) 描述每隔 s 期重复的模式，例如月度数据的 s=12。",
        "季节阶数越多参数越多，样本少时容易不收敛。",
        f"趋势项 trend={trend}；是否强制平稳为 {stationarity}，是否强制可逆为 {invertibility}。",
    ]
    if residual_test:
        notes.append(f"Ljung-Box 残差检验用 {lags} 阶滞后，p 值大于 0.05 说明残差基本是白噪声。")
    else:
        notes.append("已关闭残差诊断，未计算 Ljung-Box 统计量。")
    return registry.result(
        "series.sarima",
        context.table,
        metrics={
            "order": list(order),
            "seasonal_order": list(seasonal),
            "observations": int(values.size),
            "horizon": horizon,
            "trend": trend,
            "order_selection": context.text(
                "order_selection", "fixed", ("fixed", "aic", "bic", "hqic")
            ),
            "models_compared": int(compared_count),
            "enforce_stationarity": bool(stationarity),
            "enforce_invertibility": bool(invertibility),
            "conf_level": confidence,
            "residual_test": bool(residual_test),
            "residual_lags": int(lags) if residual_test else None,
            "residual_plot": bool(residual_plot),
            "seasonal_lags": int(seasonal_lags if seasonal_lags else lags),
            "forecast_plot": bool(forecast_plot),
            "aic": round(float(fitted.aic), 6),
            "bic": round(float(fitted.bic), 6),
            "hqic": round(float(fitted.hqic), 6),
            "converged": bool(fitted.mle_retvals.get("converged", True)),
            "residual_std": round(float(np.nanstd(residuals)), 6),
            "ljung_box_p": None if ljung_p is None else round(ljung_p, 8),
            "next_forecast": round(float(mean[0]), 6),
        },
        tables={"forecast": table_of(rows, limit=horizon)},
        figures=figures,
        notes=notes,
    )


def _garch_figure(context, returns, conditional, residuals, name, panels):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过波动率图。")
        return []
    figure, axes = plt.subplots(len(panels), 1, figsize=(9.5, 2.8 * len(panels)), squeeze=False)
    for row, panel in enumerate(panels):
        axis = axes[row][0]
        if panel == "returns":
            axis.plot(range(1, returns.size + 1), returns, color="#374151")
            axis.set_title("收益率")
        elif panel == "volatility":
            axis.plot(range(1, conditional.size + 1), conditional, color="#ef4444")
            axis.set_title("条件波动率")
        elif panel == "overlay":
            axis.plot(
                range(1, returns.size + 1), returns, color="#9ca3af", linewidth=0.9, label="收益率"
            )
            axis.plot(
                range(1, conditional.size + 1), conditional, color="#ef4444", label="条件波动率"
            )
            axis.plot(range(1, conditional.size + 1), -conditional, color="#ef4444", linewidth=0.9)
            axis.set_title("收益率与正负条件波动率")
            axis.legend(fontsize=8)
        elif panel == "squared":
            axis.plot(range(1, returns.size + 1), returns**2, color="#4f7cff", linewidth=0.9)
            axis.set_title("收益率平方（波动聚集）")
        else:
            axis.plot(range(1, residuals.size + 1), residuals, color="#374151", linewidth=0.9)
            axis.axhline(0, color="#ef4444", linewidth=0.8)
            axis.set_title("标准化残差")
        axis.grid(alpha=0.3)
    figure.tight_layout()
    return _saved(context, figure, name)


@register("series.garch")
def garch(context):
    from arch import arch_model

    values = _series(context)
    if values.size < 20:
        raise MethodError("GARCH 至少需要 20 个观测。")
    p = context.whole("p", 1, 1, 3)
    q = context.whole("q", 1, 1, 3)
    horizon = context.whole("horizon", 5, 1, 60)
    distribution = context.text("dist", "normal", ("normal", "t", "skewt"))
    mean_kind = context.text("mean", "constant", ("constant", "zero", "AR"))
    mean_order = context.whole("mean_order", 1, 1, 3)
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    conditional_volatility = context.flag("conditional_volatility", True)
    standardized_residual = context.flag("standardized_residual", False)
    residual_plot = context.flag("residual_plot", True)
    residual_lags = context.whole("residual_lags", 10, 1, 60)
    returns = (
        np.diff(np.log(np.clip(values, EPS, None))) * 100 if (values > 0).all() else np.diff(values)
    )
    mean_setting = mean_kind
    options = {"vol": "GARCH", "p": p, "q": q, "dist": distribution, "mean": mean_setting}
    if mean_kind == "AR":
        options["lags"] = mean_order
    model = arch_model(returns, **options)
    try:
        fitted = model.fit(disp="off")
    except Exception as error:
        raise MethodError(f"GARCH 拟合失败：{error}")

    forecast = fitted.forecast(horizon=horizon, reindex=False)
    variance = np.asarray(forecast.variance)[0]
    rows = pd.DataFrame(
        {
            "step": range(1, horizon + 1),
            "variance": numbers(variance, 6),
            "volatility": numbers(np.sqrt(variance), 6),
        }
    )

    conditional = np.asarray(fitted.conditional_volatility, dtype=float)
    residuals = np.asarray(fitted.resid, dtype=float)
    volatility_frame = pd.DataFrame(
        {
            "index": range(1, conditional.size + 1),
            "return": numbers(returns, 6),
            "volatility": numbers(conditional, 6),
            "standardized_residual": numbers(residuals, 6),
        }
    )

    parameters = fitted.params
    pvalues = None if fitted.pvalues is None else np.asarray(fitted.pvalues, dtype=float)
    rows_params = pd.DataFrame(
        {
            "parameter": [str(name) for name in parameters.index],
            "value": numbers(parameters.to_numpy(), 6),
            "p_value": numbers(pvalues, 8) if pvalues is not None else [None] * len(parameters),
        }
    )
    if pvalues is not None:
        rows_params["significant"] = [bool(value < alpha) for value in pvalues]

    figures = []
    volatility_plot = context.flag("volatility_plot", True)
    if volatility_plot:
        figures.extend(
            _garch_figure(
                context, returns, conditional, residuals, "series_garch", ["returns", "volatility"]
            )
        )
    if residual_plot:
        figures.extend(
            _garch_figure(
                context,
                returns,
                conditional,
                residuals,
                "series_garch_residuals",
                ["squared", "standardized"],
            )
        )

    labels = {"alpha[1]": "alpha", "beta[1]": "beta", "nu": "nu", "lambda": "skew"}
    values_map = {}
    for source, target in labels.items():
        values_map[target] = float(parameters[source]) if source in parameters.index else None
    persistence = None
    if values_map["alpha"] is not None and values_map["beta"] is not None:
        persistence = values_map["alpha"] + values_map["beta"]
    standardized = residuals / np.where(conditional <= EPS, EPS, conditional)
    ljung_p = _ljung_box_p(standardized, residual_lags) if residual_plot else None
    metrics = {
        "p": p,
        "q": q,
        "observations": int(returns.size),
        "horizon": horizon,
        "dist": distribution,
        "mean": mean_kind,
        "alpha_level": alpha,
        "mean_order": int(mean_order),
        "volatility_plot": bool(volatility_plot),
        "residual_plot": bool(residual_plot),
        "residual_lags": int(residual_lags),
        "standardized_residual": bool(standardized_residual),
        "conditional_volatility": bool(conditional_volatility),
        "aic": round(float(fitted.aic), 6),
        "bic": round(float(fitted.bic), 6),
        "log_likelihood": round(float(fitted.loglikelihood), 6),
        "alpha": None if values_map["alpha"] is None else round(values_map["alpha"], 6),
        "beta": None if values_map["beta"] is None else round(values_map["beta"], 6),
        "nu": None if values_map["nu"] is None else round(values_map["nu"], 6),
        "skew": None if values_map["skew"] is None else round(values_map["skew"], 6),
        "persistence": None if persistence is None else round(persistence, 6),
        "standardized_residual_std": round(float(np.nanstd(standardized)), 6),
        "residual_ljung_box_p": None if ljung_p is None else round(ljung_p, 8),
        "next_volatility": round(float(math.sqrt(variance[0])), 6),
    }
    tables = {
        "forecast": table_of(rows, limit=horizon),
        "parameters": table_of(rows_params, limit=20),
    }
    if conditional_volatility:
        tables["conditional_volatility"] = table_of(volatility_frame, limit=200)
    if standardized_residual:
        tables["standardized_residual"] = table_of(
            pd.DataFrame(
                {
                    "index": range(1, standardized.size + 1),
                    "residual": numbers(residuals, 6),
                    "conditional_volatility": numbers(conditional, 6),
                    "standardized": numbers(standardized, 6),
                }
            ),
            limit=200,
        )
    notes = [
        "GARCH 建模的是波动率的聚集性：大波动后面往往还是大波动。",
        "alpha+beta 越接近 1，波动冲击衰减越慢。",
        f"分布假设为 {distribution}，均值方程设定为 {mean_kind}。",
    ]
    if mean_kind == "AR":
        notes.append(f"均值方程含 {mean_order} 阶自回归项，用于吸收收益率里的自相关。")
    if conditional_volatility:
        notes.append("已输出每个历史时点由模型推出的条件波动率序列。")
    else:
        notes.append("已关闭条件波动率序列输出。")
    if standardized_residual:
        notes.append("标准化残差等于残差除以条件波动率，理论上应接近同方差白噪声。")
    if residual_plot:
        notes.append(
            f"标准化残差的 Ljung-Box 检验用 {residual_lags} 阶滞后，"
            "p 值大于 0.05 说明 GARCH 已吸收掉主要波动结构。"
        )
    return registry.result(
        "series.garch",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _var_irf_figure(context, fitted, names, periods, irf_alpha):
    try:
        import matplotlib.pyplot as plt

        response = fitted.irf(periods=periods)
        responses = np.asarray(response.irfs, dtype=float)
        band = np.asarray(response.errband_mc(signif=irf_alpha), dtype=float)
        fig, axes = plt.subplots(1, len(names), figsize=(3.2 * len(names), 3), squeeze=False)
        for index, name in enumerate(names):
            axis = axes[0][index]
            steps = range(responses.shape[0])
            axis.plot(steps, responses[:, index, 0], color="#4f7cff")
            axis.fill_between(
                steps, band[0, :, index, 0], band[1, :, index, 0], color="#4f7cff", alpha=0.2
            )
            axis.set_title(f"{names[0]} → {name}", fontsize=9)
            axis.grid(alpha=0.3)
        return _saved(context, fig, "series_var_irf")
    except ImportError:
        context.warn("未安装 matplotlib，跳过脉冲响应图。")
        return []
    except Exception as error:
        context.warn(f"脉冲响应计算未完成：{error}")
        return []


def _var_forecast_figure(context, frame, names, projection, horizon):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过预测图。")
        return []
    history = frame.to_numpy(dtype=float)
    shown = min(history.shape[0], 40)
    fig, axes = plt.subplots(len(names), 1, figsize=(9.5, 2.6 * len(names)), squeeze=False)
    for index, name in enumerate(names):
        axis = axes[index][0]
        axis.plot(range(1, shown + 1), history[-shown:, index], color="#374151", label="历史")
        steps = range(shown + 1, shown + horizon + 1)
        axis.plot(steps, projection[:, index], color="#4f7cff", label="预测")
        axis.set_title(str(name), fontsize=9)
        axis.legend(fontsize=7)
        axis.grid(alpha=0.3)
    fig.suptitle("VAR 预测", fontsize=11)
    fig.tight_layout()
    return _saved(context, fig, "series_var_forecast")


def _lag_rule(context):
    rules = {"aic": "aic", "bic": "bic", "hqic": "hqic", "fpe": "fpe"}
    choice = context.text("selection", "fixed", ("fixed", "aic", "bic", "hqic", "fpe"))
    if choice == "fixed":
        return "fixed", None
    return choice, rules[choice]


@register("series.var")
def var_model(context):
    from statsmodels.tsa.api import VAR

    matrix, names = _multi_series(context)
    lags = context.whole("lags", 1, 1, 12)
    horizon = context.whole("horizon", 10, 1, 60)
    trend = context.text("trend", "c", ("c", "ct", "n"))
    selection, criterion = _lag_rule(context)
    frame = pd.DataFrame(matrix, columns=names)
    model = VAR(frame)
    chosen = lags
    if criterion is not None:
        try:
            order = model.select_order(maxlags=lags)
            chosen = max(int(getattr(order, criterion)), 1)
        except Exception as error:
            context.warn(f"按 {selection} 准则自动定阶失败（{error}），改用 lags={lags}。")
            chosen = lags
        if chosen != lags:
            context.warn(f"按 {selection} 准则把最大滞后阶数从 {lags} 调整为 {chosen}。")
    fitted = None
    last = None
    used_trend = trend
    candidates = [trend] + [item for item in ("c", "n") if item != trend]
    for candidate in candidates:
        try:
            fitted = model.fit(maxlags=chosen, ic=None, trend=candidate)
            used_trend = candidate
            if candidate != trend:
                context.warn(f"VAR 在 trend={trend} 下拟合失败，已改用 trend={candidate}。")
            break
        except Exception as error:
            last = error
    if fitted is None:
        variances = matrix.var(axis=0)
        order = np.argsort(-variances)
        for size in range(min(len(names), 6), 1, -1):
            picked = sorted(order[:size])
            subset = matrix[:, picked]
            try:
                fitted = VAR(pd.DataFrame(subset, columns=[names[i] for i in picked])).fit(
                    maxlags=chosen, ic=None, trend="n"
                )
                context.warn(
                    f"VAR 原始变量接近共线，已只保留方差最大的 {size} 个变量："
                    + "、".join(names[i] for i in picked)
                )
                matrix = subset
                names = [names[i] for i in picked]
                frame = pd.DataFrame(matrix, columns=names)
                used_trend = "n"
                break
            except Exception as error:
                last = error
    if fitted is None:
        context.warn(
            f"statsmodels VAR 拟合失败（{type(last).__name__}: {last}），已改用逐方程最小二乘估计。"
        )
        return _var_by_ols(context, matrix, names, lags, horizon, trend, selection)

    forecast = fitted.forecast(frame.to_numpy()[-fitted.k_ar :], steps=horizon)
    rows = []
    for step in range(horizon):
        for index, name in enumerate(names):
            rows.append(
                {
                    "step": step + 1,
                    "variable": name,
                    "forecast": round(float(forecast[step, index]), 6),
                }
            )

    tables = {"forecast": table_of(pd.DataFrame(rows), limit=80)}
    granger_test = context.flag("granger_test", True)
    causality_p = None
    if granger_test:
        position = _pick_matrix_var(context, names, "格兰杰因果检验的因变量")
        if len(names) < 2:
            context.warn("只有一个变量，无法做格兰杰因果检验。")
        else:
            try:
                causality = fitted.test_causality(
                    names[position], names[:position] + names[position + 1 :], kind="f"
                )
                causality_p = float(causality.pvalue)
                tables["granger"] = table_of(
                    pd.DataFrame(
                        {
                            "effect": [names[position]],
                            "causes": ["、".join(names[:position] + names[position + 1 :])],
                            "f_statistic": [round(float(causality.test_statistic), 6)],
                            "p_value": [round(causality_p, 8)],
                            "significant": [bool(causality_p < 0.05)],
                        }
                    ),
                    limit=20,
                )
            except Exception as error:
                context.warn(f"格兰杰因果检验未完成：{error}")
    try:
        aic = round(float(fitted.aic), 6)
        bic = round(float(fitted.bic), 6)
    except Exception:
        aic, bic = None, None
        context.warn("残差协方差矩阵接近奇异，无法计算 AIC/BIC；变量之间可能高度相关。")

    irf_plot = context.flag("irf_plot", True)
    irf_alpha = context.number("irf_alpha", 0.05, 0.001, 0.5)
    irf_periods = context.whole("irf_periods", None, 1, 120)
    periods = irf_periods if irf_periods is not None else horizon
    if irf_plot and periods != horizon:
        context.warn(f"脉冲响应图的期数单独设为 {periods} 期，预测表仍是 {horizon} 期。")
    figures = []
    if irf_plot:
        figures.extend(_var_irf_figure(context, fitted, names, periods, irf_alpha))
    forecast_plot = context.flag("forecast_plot", True)
    if forecast_plot:
        figures.extend(
            _var_forecast_figure(context, frame, names, np.asarray(forecast, dtype=float), horizon)
        )

    notes = [
        "VAR 把每个变量表示成所有变量滞后项的线性函数。",
        "滞后阶数过多会迅速消耗自由度，可用 AIC/BIC 选择。",
        f"确定性项设定 trend={used_trend}；脉冲响应的置信水平按 {irf_alpha:g} 计算。",
    ]
    if selection != "fixed":
        notes.append(f"已按 {selection} 准则在 1 到 {lags} 阶之间自动定阶。")
    return registry.result(
        "series.var",
        context.table,
        metrics={
            "variables": names,
            "lags": int(fitted.k_ar),
            "observations": int(fitted.nobs),
            "horizon": horizon,
            "irf_plot": bool(irf_plot),
            "aic": aic,
            "bic": bic,
            "forecast_plot": bool(forecast_plot),
            "trend": used_trend,
            "selection": selection,
            "selection_limit": lags,
            "granger_test": bool(granger_test),
            "irf_alpha": irf_alpha,
            "irf_periods": int(periods),
            "granger_p_for_first_variable": None if causality_p is None else round(causality_p, 8),
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _var_by_ols(context, matrix, names, lags, horizon, trend, selection):
    count, variables = matrix.shape
    usable = count - lags
    constant = trend in ("c", "ct")
    slope = 1 if trend == "ct" else 0
    if usable < variables * lags + 2:
        raise MethodError(
            f"样本不足以估计 {lags} 阶 VAR（需要多于 {variables * lags + 2} 个观测）。"
        )
    design = [np.ones(usable)] if constant else []
    if slope:
        design.append(np.arange(usable, dtype=float))
    for lag in range(1, lags + 1):
        design.append(matrix[lags - lag : count - lag])
    design = np.column_stack(design)
    coefficients = []
    for index in range(variables):
        response = matrix[lags:, index]
        beta, *_ = np.linalg.lstsq(design, response, rcond=None)
        coefficients.append(beta)
    coefficients = np.asarray(coefficients)

    history = matrix[-lags:].copy()
    predictions = []
    for step in range(horizon):
        row = [1.0] if constant else []
        if slope:
            row.append(float(usable + step))
        for lag in range(1, lags + 1):
            row.extend(history[-lag])
        row = np.asarray(row, dtype=float)
        step_value = coefficients @ row
        predictions.append(step_value)
        history = np.vstack([history, step_value])
    predictions = np.asarray(predictions)

    rows = []
    for step in range(horizon):
        for index, name in enumerate(names):
            rows.append(
                {
                    "step": step + 1,
                    "variable": name,
                    "forecast": round(float(predictions[step, index]), 6),
                }
            )
    coefficient_rows = []
    labels = []
    if constant:
        labels.append("常数项")
    if slope:
        labels.append("时间趋势")
    for lag in range(1, lags + 1):
        labels.extend(f"L{lag}.{name}" for name in names)
    for index, name in enumerate(names):
        for position, label in enumerate(labels):
            coefficient_rows.append(
                {
                    "equation": name,
                    "term": label,
                    "coefficient": round(float(coefficients[index][position]), 6),
                }
            )
    return registry.result(
        "series.var",
        context.table,
        metrics={
            "variables": names,
            "lags": lags,
            "observations": int(usable),
            "horizon": horizon,
            "trend": trend,
            "selection": selection,
            "selection_limit": lags,
            "granger_test": False,
            "estimator": "逐方程最小二乘（回退）",
        },
        tables={
            "forecast": table_of(pd.DataFrame(rows), limit=80),
            "coefficients": table_of(pd.DataFrame(coefficient_rows), limit=80),
        },
        notes=[
            "statsmodels 的 VAR 在数据接近奇异时无法求逆，这里改用逐方程普通最小二乘。",
            "逐方程最小二乘与 VAR 的系数估计等价，但未提供脉冲响应与协方差矩阵。",
        ],
    )


def _coint_figure(context, matrix, names, pairs):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过协整关系图。")
        return []
    from statsmodels.tsa.stattools import coint  # noqa: F401

    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))
    standardized = (matrix - matrix.mean(axis=0)) / np.where(
        matrix.std(axis=0) <= EPS, 1.0, matrix.std(axis=0)
    )
    for index, name in enumerate(names):
        axes[0].plot(
            range(1, matrix.shape[0] + 1), standardized[:, index], linewidth=1.0, label=str(name)
        )
    axes[0].set_title("标准化后的序列（重合程度反映共同趋势）")
    axes[0].legend(fontsize=7)
    axes[0].grid(alpha=0.3)
    selected = pairs[0] if pairs else None
    left = names.index(selected["left"]) if selected else 0
    right = names.index(selected["right"]) if selected else 1
    if selected is not None:
        covariance = np.cov(matrix[:, left], matrix[:, right])
        beta = covariance[0, 1] / max(covariance[1, 1], EPS)
        spread = matrix[:, left] - beta * matrix[:, right]
        axes[1].plot(
            range(1, spread.size + 1), spread, color="#4f7cff", linewidth=1.0, label="长期均衡残差"
        )
        axes[1].axhline(
            float(spread.mean()), color="#10b981", linestyle="--", linewidth=1, label="均值"
        )
        axes[1].set_title(
            f"{selected['left']} 与 {selected['right']} 的协整残差（p={selected['p_value']:g}）"
        )
        axes[1].legend(fontsize=7)
        axes[1].grid(alpha=0.3)
    else:
        axes[1].plot(
            range(1, matrix.shape[0] + 1),
            matrix[:, 1] - matrix[:, 0],
            color="#4f7cff",
            linewidth=1.0,
        )
        axes[1].set_title("两两差值走势")
        axes[1].grid(alpha=0.3)
    figure.tight_layout()
    return _saved(context, figure, "series_coint_equilibrium")


@register("series.coint")
def coint(context):
    from statsmodels.tsa.stattools import coint
    from statsmodels.tsa.vector_ar.vecm import coint_johansen

    matrix, names = _multi_series(context)
    lags = context.whole("lags", 1, 1, 12)
    trend = context.text("trend", "c", ("c", "ct", "n"))
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    johansen_test = context.flag("johansen_test", True)
    trace_statistic = context.flag("johansen_trace", True)
    eigenvalue_statistic = context.flag("johansen_max_eigen", False)
    pair_test = context.flag("pair_test", True)
    det_order = {"c": 0, "ct": 1, "n": -1}[trend]
    level = _critical_level(alpha)
    pair_threshold = _pair_critical(alpha)
    pairs = []
    if pair_test:
        for left in range(matrix.shape[1]):
            for right in range(left + 1, matrix.shape[1]):
                statistic, pvalue, critical = coint(
                    matrix[:, left], matrix[:, right], trend=trend, maxlag=lags
                )
                pairs.append(
                    {
                        "left": names[left],
                        "right": names[right],
                        "statistic": round(float(statistic), 6),
                        "p_value": round(float(pvalue), 8),
                        "critical_5pct": round(float(critical[1]), 6),
                        "critical_value": round(float(critical[pair_threshold[0]]), 6),
                        "critical_level": pair_threshold[1],
                        "cointegrated": bool(pvalue < alpha),
                    }
                )
        pairs.sort(key=lambda item: item["p_value"])

    johansen = None
    if johansen_test:
        try:
            result = coint_johansen(matrix, det_order=det_order, k_ar_diff=lags)
            column = _johansen_column(alpha)
            content = {
                "hypothesis": [f"至多 {index} 个协整关系" for index in range(len(names))],
                "critical_5pct": numbers(result.cvt[:, 1], 6),
                "critical_value": numbers(result.cvt[:, column], 6),
                "critical_level": [level] * len(names),
            }
            if trace_statistic:
                content["trace_statistic"] = numbers(result.lr1, 6)
                content["reject_5pct"] = [
                    bool(result.lr1[index] > result.cvt[index, 1]) for index in range(len(names))
                ]
                content["reject"] = [
                    bool(result.lr1[index] > result.cvt[index, column])
                    for index in range(len(names))
                ]
            if eigenvalue_statistic:
                content["max_eigen_statistic"] = numbers(result.lr2, 6)
                content["max_eigen_reject"] = [
                    bool(result.lr2[index] > result.cvm[index, column])
                    for index in range(len(names))
                ]
            johansen = pd.DataFrame(content)
        except Exception as error:
            context.warn(f"Johansen 协整检验未完成：{error}")

    tables = {}
    if pair_test:
        tables["pairs"] = table_of(pd.DataFrame(pairs), limit=40)
    if johansen is not None:
        tables["johansen"] = table_of(johansen, limit=20)
    notes = [
        "协整表示非平稳变量之间存在长期均衡关系，短线偏离会被拉回。",
        "Johansen 检验可以一次判断多个变量之间存在几个协整关系。",
        f"显著性水平 {alpha:g} 对应 {level} 临界值；Pair 检验与 Johansen 检验共用 trend={trend}、lags={lags}。",
    ]
    if not pair_test:
        notes.append("已关闭两两协整（Engle-Granger）检验，只保留 Johansen 检验。")
    if not johansen_test:
        notes.append("已关闭 Johansen 检验，只输出两两协整结果。")
    figures = []
    integration_plot = context.flag("integration_plot", True)
    if integration_plot:
        figures.extend(_coint_figure(context, matrix, names, pairs))
    return registry.result(
        "series.coint",
        context.table,
        metrics={
            "variables": names,
            "observations": int(matrix.shape[0]),
            "lags": lags,
            "trend": trend,
            "alpha": alpha,
            "critical_level": level,
            "johansen_test": bool(johansen_test),
            "johansen_trace": bool(trace_statistic),
            "johansen_max_eigen": bool(eigenvalue_statistic),
            "pair_test": bool(pair_test),
            "integration_plot": bool(integration_plot),
            "cointegrated_pairs": sum(1 for item in pairs if item["cointegrated"]),
            "total_pairs": len(pairs),
            "smallest_p": pairs[0]["p_value"] if pairs else None,
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _critical_level(alpha):
    if alpha <= 0.01:
        return "99%"
    if alpha <= 0.05:
        return "95%"
    return "90%"


def _pair_critical(alpha):
    if alpha <= 0.01:
        return 0, "99%"
    if alpha <= 0.05:
        return 1, "95%"
    return 2, "90%"


def _johansen_column(alpha):
    if alpha <= 0.01:
        return 2
    if alpha <= 0.05:
        return 1
    return 0


GRANGER_CRITERIA = {"aic": "aic", "bic": "bic", "fpe": "fpe", "hqic": "hqic"}


def _granger_heatmap(context, pvalues, names, alpha):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过因果检验 p 值热力图。")
        return []
    figure, axis = plt.subplots(figsize=(1.1 * len(names) + 3, 1.0 * len(names) + 2.4))
    shown = np.where(np.isnan(pvalues), 1.0, pvalues)
    image = axis.imshow(shown, cmap="RdYlGn_r", vmin=0.0, vmax=1.0)
    axis.set_xticks(range(len(names)))
    axis.set_yticks(range(len(names)))
    axis.set_xticklabels([str(name) for name in names], rotation=45, ha="right", fontsize=8)
    axis.set_yticklabels([str(name) for name in names], fontsize=8)
    axis.set_xlabel("被预测变量")
    axis.set_ylabel("原因变量")
    for row in range(len(names)):
        for column in range(len(names)):
            value = pvalues[row, column]
            if np.isnan(value):
                axis.text(column, row, "—", ha="center", va="center", fontsize=8)
            else:
                axis.text(column, row, f"{value:.3f}", ha="center", va="center", fontsize=7)
    axis.set_title(f"格兰杰因果检验 p 值热力图（绿为 p<{alpha:g}）")
    figure.colorbar(image, ax=axis, shrink=0.8)
    figure.tight_layout()
    return _saved(context, figure, "series_granger_heatmap")


@register("series.granger")
def granger(context):
    from statsmodels.tsa.stattools import grangercausalitytests

    matrix, names = _multi_series(context)
    default_lag = min(6, max(1, matrix.shape[0] // 10))
    max_lag = context.whole("max_lag", default_lag, 1, 20)
    if max_lag > default_lag and matrix.shape[0] <= 2 * max_lag + 4:
        context.warn(f"最大滞后阶数 {max_lag} 相对样本量偏大，估计结果可能不稳定。")
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    seed = context.whole("granger_seed", 20240517, 0, 2**31 - 1)
    np.random.seed(seed % (2**32))
    detail = context.flag("detail", False)
    chi_square = context.flag("chi_square", False)
    selection = context.text("lag_selection", "fixed", ("fixed", "aic", "bic", "fpe", "hqic"))
    requested = context.want("columns")
    if requested:
        chosen = registry.subset(context.table, requested)[0]
        unknown = [name for name in chosen if name not in names]
        if unknown:
            raise MethodError(
                f"columns 里的列不在数据中：{'、'.join(str(item) for item in unknown)}。"
            )
        cause_names = chosen
    else:
        cause_names = list(names)
    cause_index = [names.index(name) for name in cause_names]
    effect_name = context.text("effect")
    if effect_name:
        if effect_name not in names:
            raise MethodError(
                f"effect 列 {effect_name} 不在数据中。可用列："
                f"{'、'.join(str(name) for name in names)}。"
            )
        effect_index = [names.index(effect_name)]
    else:
        effect_index = list(range(matrix.shape[1]))
    rows = []
    for effect in effect_index:
        for cause in cause_index:
            if cause == effect:
                continue
            data = np.column_stack([matrix[:, effect], matrix[:, cause]])
            try:
                outcome = grangercausalitytests(data, maxlag=max_lag)
                best = min((lag, float(outcome[lag][0]["ssr_ftest"][1])) for lag in outcome)
                entry = {
                    "cause": names[cause],
                    "effect": names[effect],
                    "best_lag": int(best[0]),
                    "p_value": round(best[1], 8),
                    "significant": bool(best[1] < alpha),
                }
                if chi_square:
                    chi = outcome[best[0]][0]["ssr_chi2test"]
                    entry["chi2_statistic"] = round(float(chi[0]), 6)
                    entry["chi2_p_value"] = round(float(chi[1]), 8)
                    entry["chi2_significant"] = bool(float(chi[1]) < alpha)
                if detail:
                    for lag in sorted(outcome):
                        statistic, pvalue, degrees, _ = outcome[lag][0]["ssr_ftest"]
                        rows.append(
                            {
                                "cause": names[cause],
                                "effect": names[effect],
                                "lag": int(lag),
                                "best_lag": int(best[0]),
                                "p_value": round(best[1], 8),
                                "f_statistic": round(float(statistic), 6),
                                "lag_p_value": round(float(pvalue), 8),
                                "degrees": int(degrees),
                                "significant": bool(best[1] < alpha),
                            }
                        )
                else:
                    rows.append(entry)
            except Exception as error:
                context.warn(f"{names[cause]} → {names[effect]} 检验跳过：{error}")
    rows.sort(key=lambda item: (item["best_lag"], item["p_value"]))
    paired = {}
    for item in rows:
        key = (item["cause"], item["effect"])
        if key not in paired or (item["p_value"], item["best_lag"]) < (
            paired[key]["p_value"],
            paired[key]["best_lag"],
        ):
            paired[key] = item
    best_rows = sorted(paired.values(), key=lambda item: item["p_value"])
    significant = [item for item in best_rows if item["significant"]]
    if detail:
        frame = pd.DataFrame(rows)
    else:
        columns = ["cause", "effect", "best_lag", "p_value", "significant"]
        if chi_square and rows:
            columns.extend(["chi2_statistic", "chi2_p_value", "chi2_significant"])
        frame = pd.DataFrame(rows) if not rows else pd.DataFrame(rows)[columns]
    if frame.empty:
        frame = pd.DataFrame(columns=["cause", "effect", "best_lag", "p_value", "significant"])
    tables = {"pairs": table_of(frame, limit=200 if detail else 60)}
    if detail:
        tables["best"] = table_of(
            pd.DataFrame(
                [
                    {
                        key: item[key]
                        for key in ("cause", "effect", "best_lag", "p_value", "significant")
                    }
                    for item in best_rows
                ]
            ),
            limit=60,
        )
    suggestion = None
    if selection != "fixed":
        from statsmodels.tsa.api import VAR

        chosen_lag = None
        try:
            var_frame = pd.DataFrame(matrix, columns=names)
            order = VAR(var_frame).select_order(maxlags=min(max_lag, max(1, matrix.shape[0] // 4)))
            chosen_lag = getattr(order, GRANGER_CRITERIA[selection])
            chosen_lag = None if chosen_lag is None else max(int(chosen_lag), 1)
        except Exception as error:
            context.warn(f"按 {selection} 准则自动定阶失败（{error}），沿用 max_lag={max_lag}。")
        suggestion = max_lag if chosen_lag is None else chosen_lag
        tables["lag_selection"] = table_of(
            pd.DataFrame(
                {
                    "criterion": [selection.upper()],
                    "max_lag": [int(max_lag)],
                    "suggested_lag": [int(suggestion)],
                }
            ),
            limit=5,
        )
    effect_label = str(effect_name) if effect_name else "全部变量"
    notes = [
        "格兰杰因果只说明“领先有助于预测”，不等于真实因果机制。",
        "结果对滞后阶数敏感，这里报告每个方向上 p 值最小的滞后阶。",
        f"检验的原因变量为 {'、'.join(str(name) for name in cause_names)}，"
        f"被预测变量为 {effect_label}。",
    ]
    if selection != "fixed":
        notes.append(
            f"已按 {selection.upper()} 准则在 1 到 {max_lag} 阶之间给出建议滞后阶数，"
            "p 值仍取各方向的最优滞后。"
        )
    if suggestion is not None:
        tables["lag_selection"] = table_of(
            pd.DataFrame(
                {
                    "criterion": [selection.upper()],
                    "max_lag": [int(max_lag)],
                    "suggested_lag": [int(suggestion)],
                }
            ),
            limit=5,
        )
    pvalue_matrix = np.full((matrix.shape[1], matrix.shape[1]), np.nan)
    for index, name in enumerate(names):
        pvalue_matrix[index, index] = np.nan
    for item in paired.values():
        pvalue_matrix[names.index(str(item["cause"])), names.index(str(item["effect"]))] = float(
            item["p_value"]
        )
    figures = []
    heatmap_plot = context.flag("heatmap_plot", True)
    if heatmap_plot:
        figures.extend(_granger_heatmap(context, pvalue_matrix, names, alpha))
    if detail:
        notes.append("已输出每个滞后阶单独的 F 统计量与 p 值表。")
    if chi_square:
        notes.append("已同时输出卡方检验（ssr_chi2test）的结果用于对照。")
    return registry.result(
        "series.granger",
        context.table,
        metrics={
            "variables": names,
            "pairs": len(paired),
            "max_lag": max_lag,
            "alpha": alpha,
            "detail": bool(detail),
            "chi_square": bool(chi_square),
            "lag_selection": selection,
            "heatmap_plot": bool(heatmap_plot),
            "suggested_lag": suggestion,
            "granger_seed": int(seed),
            "cause_columns": [str(name) for name in cause_names],
            "effect_column": effect_name,
            "significant_pairs": len(significant),
            "strongest_pair": (
                f"{best_rows[0]['cause']} → {best_rows[0]['effect']}" if best_rows else None
            ),
            "smallest_p": best_rows[0]["p_value"] if best_rows else None,
        },
        tables=tables,
        figures=figures,
        notes=notes,
    )


GM_TYPES = ("gm11", "dgm11", "verhulst")


def _gm11_core(values, kind, background, smooth, horizon, optimize=False):
    sample = values
    if smooth:
        sample = np.empty_like(values)
        sample[0] = values[0]
        sample[1:] = smooth * values[1:] + (1 - smooth) * values[:-1]
    if kind == "verhulst" and not (sample > 0).all():
        raise MethodError("Verhulst 模型要求序列全为正数。")

    accumulated = np.cumsum(sample)
    z = 0.5 * (accumulated[1:] + accumulated[:-1]) if background == "mean" else accumulated[:-1]
    b = sample[1:]
    weight = 0.5
    if optimize and kind == "gm11" and background == "mean":
        candidates = [0.5, 0.4, 0.6, 0.45, 0.55, 0.35, 0.65, 0.3, 0.7]
        best = None
        for candidate in candidates:
            design = np.column_stack(
                [
                    -(candidate * accumulated[1:] + (1 - candidate) * accumulated[:-1]),
                    np.ones_like(z),
                ]
            )
            coefficients, *_ = np.linalg.lstsq(design, b, rcond=None)
            local_a = float(coefficients[0])
            if abs(local_a) < EPS:
                continue
            local_fitted = (sample[0] - float(coefficients[1]) / local_a) * np.exp(
                -local_a * np.arange(sample.size)
            ) + float(coefficients[1]) / local_a
            local_restored = np.diff(np.concatenate([[0.0], local_fitted]))
            error = float(
                np.mean(
                    np.abs(sample - local_restored)
                    / np.where(np.abs(sample) <= EPS, 1.0, np.abs(sample))
                )
            )
            if best is None or error < best[0] - 1e-12:
                best = (error, candidate)
        if best is not None:
            weight = best[1]
            background = "mean" if weight == 0.5 else "optimized"
            z = weight * accumulated[1:] + (1 - weight) * accumulated[:-1]
    try:
        if kind == "gm11":
            design = np.column_stack([-z, np.ones_like(z)])
            coefficients, *_ = np.linalg.lstsq(design, b, rcond=None)
            a, u = float(coefficients[0]), float(coefficients[1])
            if abs(a) < EPS:
                raise MethodError("发展系数接近 0，GM(1,1) 不适用。")
            steps = np.arange(0, sample.size + horizon)
            fitted = (sample[0] - u / a) * np.exp(-a * steps) + u / a
            restored = np.diff(np.concatenate([[0.0], fitted]))
            parameters = {"a": a, "u": u}
        elif kind == "dgm11":
            design = np.column_stack([accumulated[:-1], np.ones_like(z)])
            coefficients, *_ = np.linalg.lstsq(design, accumulated[1:], rcond=None)
            beta1, beta2 = float(coefficients[0]), float(coefficients[1])
            if abs(1 - beta1) < EPS:
                raise MethodError("发展系数接近 1，DGM(1,1) 不适用。")
            steps = np.arange(0, sample.size + horizon)
            fitted = beta1**steps * sample[0] + beta2 * (1 - beta1**steps) / (1 - beta1)
            restored = fitted.copy()
            restored[1:] = fitted[1:] - fitted[:-1]
            parameters = {
                "beta1": beta1,
                "beta2": beta2,
                "a": math.log(beta1) if beta1 > 0 else float("nan"),
                "u": beta2 / (1 - beta1),
            }
        else:
            design = np.column_stack([-z, np.ones_like(z)])
            coefficients, *_ = np.linalg.lstsq(design, -np.log(b), rcond=None)
            a, u = float(coefficients[0]), float(coefficients[1])
            base = math.exp(-u)
            if abs(base - 1) < EPS:
                raise MethodError("特征根接近 1，Verhulst 模型不适用。")
            steps = np.arange(0, sample.size + horizon)
            denominator = base + (a * sample[0] / (base - 1)) * base**-steps
            fitted = 1.0 / denominator
            restored = fitted.copy()
            parameters = {
                "a": a,
                "u": u,
                "saturation": round(float(1.0 / denominator[-1]), 6)
                if denominator[-1] != 0
                else None,
            }
    except MethodError:
        raise
    except Exception as error:
        raise MethodError(f"{kind} 参数估计失败：{error}")
    historical = restored[: sample.size]
    future = restored[sample.size :]
    return {
        "sample": sample,
        "background": background,
        "historical": historical,
        "future": future,
        "parameters": parameters,
        "weight": weight,
    }


def _gm11_figure(context, record, horizon, confidence_rows):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过灰色预测图。")
        return []
    sample = record["sample"]
    historical = record["historical"]
    future = record["future"]
    figure, axes = plt.subplots(2, 1, figsize=(9.5, 6), gridspec_kw={"height_ratios": [2, 1]})
    actual_steps = range(1, sample.size + 1)
    axes[0].plot(actual_steps, sample, marker="o", markersize=3, color="#374151", label="原始值")
    axes[0].plot(actual_steps, historical, color="#10b981", label="拟合值")
    future_steps = range(sample.size + 1, sample.size + horizon + 1)
    axes[0].plot(future_steps, future, marker="s", markersize=3, color="#4f7cff", label="预测值")
    if confidence_rows:
        axes[0].fill_between(
            list(future_steps),
            confidence_rows[0],
            confidence_rows[1],
            color="#4f7cff",
            alpha=0.2,
            label="预测区间",
        )
    axes[0].set_title("GM 系列模型：原始、拟合与预测")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)
    residual = sample - historical
    axes[1].bar(list(actual_steps), residual, color="#ef4444", alpha=0.75)
    axes[1].axhline(0, color="#374151", linewidth=0.8)
    axes[1].set_title("拟合残差")
    axes[1].grid(alpha=0.3)
    figure.tight_layout()
    return _saved(context, figure, "series_gm11_fit")


@register("series.gm11")
def gm11(context):
    values = _series(context)
    if values.size < 4:
        raise MethodError("GM(1,1) 至少需要 4 个观测。")
    horizon = context.whole("horizon", 5, 1, 50)
    kind = context.text("model", "gm11", GM_TYPES)
    background = context.text("background", "mean", ("mean", "raw"))
    residual_test = context.flag("residual_test", True)
    smooth = context.number(
        "smooth",
        None,
        0.0,
        1.0,
    )
    optimize_background = context.flag("optimize_background", True)
    applicability = context.flag("applicability", True)
    record = _gm11_core(values, kind, background, smooth, horizon, optimize_background)
    sample = record["sample"]
    used_background = record["background"]
    parameters = record["parameters"]
    historical = record["historical"]
    future = record["future"]
    residual = sample - historical
    relative = np.abs(residual) / np.where(np.abs(sample) <= EPS, 1.0, np.abs(sample))
    rows = pd.DataFrame({"step": range(1, horizon + 1), "forecast": numbers(future, 6)})
    forecast_ci = context.flag("forecast_ci", False)
    ci_band = None
    if forecast_ci:
        spread = float(np.std(residual))
        rows["ci_low"] = numbers(future - 1.959964 * spread, 6)
        rows["ci_high"] = numbers(future + 1.959964 * spread, 6)
        ci_band = (future - 1.959964 * spread, future + 1.959964 * spread)
    history = pd.DataFrame(
        {
            "index": range(1, sample.size + 1),
            "actual": numbers(sample, 6),
            "fitted": numbers(historical, 6),
            "residual": numbers(residual, 6),
            "relative_error": numbers(relative, 6),
        }
    )
    accuracy = (
        "一级（优）"
        if relative.mean() < 0.01
        else "二级（良）"
        if relative.mean() < 0.05
        else "三级（合格）"
        if relative.mean() < 0.10
        else "四级（不合格）"
    )
    metrics = {
        "model": kind,
        "background": background,
        "used_background": used_background,
        "observations": int(sample.size),
        "horizon": horizon,
        "smooth": smooth,
        "residual_test": bool(residual_test),
        "optimize_background": bool(optimize_background),
        "background_weight": record["weight"],
        "applicability": bool(applicability),
        "development_coefficient_a": (
            None if not np.isfinite(float(parameters["a"])) else round(float(parameters["a"]), 6)
        ),
        "grey_input_u": round(float(parameters["u"]), 6),
        "mean_relative_error": round(float(relative.mean()), 6),
        "accuracy_grade": accuracy,
        "forecast_ci": bool(forecast_ci),
        "next_forecast": round(float(future[0]), 6),
    }
    if kind == "dgm11":
        metrics["beta1"] = round(float(parameters["beta1"]), 6)
        metrics["beta2"] = round(float(parameters["beta2"]), 6)
    if kind == "verhulst":
        metrics["saturation"] = parameters["saturation"]
    tables = {"forecast": table_of(rows, limit=horizon), "history": table_of(history, limit=60)}
    notes = [
        "GM(1,1) 适合小样本、近似指数增长的数据，先用累加生成再还原。",
        "平均相对误差小于 1% 为一级精度，小于 5% 为二级。",
        f"背景值按{('紧邻均值' if background == 'mean' else '原始累加序列')}构造，"
        f"模型类型为 {kind}。",
    ]
    if smooth:
        notes.append(f"已先对原始序列做平滑系数 {smooth:g} 的一阶平滑再建模。")
    if optimize_background:
        notes.append(
            "optimize_background=True 时在背景值权重 0.3~1.0 之间搜索使平均相对误差"
            f"最小的方案，本次采用权重 {record['weight']:g}（{used_background}）。"
        )
    else:
        notes.append("已关闭背景值权重优化，直接按设定方式构造背景值。")
    if applicability:
        coefficient = abs(float(parameters["a"]))
        if not np.isfinite(coefficient):
            outlook = "发展系数无效，无法判断适用性"
        elif coefficient <= 0.3:
            outlook = "可用于中长期预测"
        elif coefficient <= 0.5:
            outlook = "适合短期预测，中长期慎用"
        elif coefficient <= 1.0:
            outlook = "只能用残差修正模型，不宜直接外推"
        else:
            outlook = "模型不适用，建议改用其他方法"
        metrics["applicability_range"] = outlook
        tables["applicability"] = table_of(
            pd.DataFrame(
                {
                    "indicator": ["发展系数 a", "|a| 所处区间", "适用性判断"],
                    "value": [round(float(parameters["a"]), 6), round(coefficient, 6), outlook],
                }
            ),
            limit=5,
        )
        notes.append(
            "灰色预测按发展系数 |a| 判断可用范围：不超过 0.3 适合中长期，"
            "0.3~0.5 适合短期，更大时不宜直接外推。"
        )
    if residual_test:
        actual_spread = float(np.std(sample))
        residual_spread = float(np.std(residual))
        ratio = residual_spread / max(actual_spread, EPS)
        small_error = float(np.mean(np.abs(residual - residual.mean()) < 0.6745 * actual_spread))
        grade = (
            "一级（优）"
            if ratio < 0.35 and small_error > 0.95
            else "二级（良）"
            if ratio < 0.50 and small_error > 0.80
            else "三级（合格）"
            if ratio < 0.65 and small_error > 0.70
            else "四级（不合格）"
        )
        autocorrelation = 0.0
        if residual.size > 1:
            left = residual[:-1] - residual[:-1].mean()
            right = residual[1:] - residual[1:].mean()
            denominator = math.sqrt(float((left**2).sum()) * float((right**2).sum()))
            autocorrelation = float((left * right).sum()) / max(denominator, EPS)
        statistic = 0.0
        for lag in range(1, min(5, residual.size - 1) + 1):
            left = residual[:-lag] - residual[:-lag].mean()
            right = residual[lag:] - residual[lag:].mean()
            denominator = math.sqrt(float((left**2).sum()) * float((right**2).sum()))
            rho = float((left * right).sum()) / max(denominator, EPS)
            statistic += rho * rho / max(residual.size - lag, 1)
        statistic *= residual.size * (residual.size + 2)
        from scipy import stats as sps

        pvalue = float(1 - sps.chi2.cdf(statistic, min(5, max(residual.size - 1, 1))))
        metrics["posterior_ratio_c"] = round(ratio, 6)
        metrics["small_error_probability"] = round(small_error, 6)
        metrics["residual_grade"] = grade
        metrics["residual_autocorrelation"] = round(autocorrelation, 6)
        metrics["residual_ljung_box_p"] = round(pvalue, 8)
        tables["residual_test"] = table_of(
            pd.DataFrame(
                {
                    "indicator": [
                        "后验差比值 C",
                        "小误差概率 P",
                        "残差一阶自相关",
                        "残差 Ljung-Box p",
                    ],
                    "value": [
                        round(ratio, 6),
                        round(small_error, 6),
                        round(autocorrelation, 6),
                        round(pvalue, 8),
                    ],
                    "benchmark": [
                        "C < 0.35 为一级",
                        "P > 0.95 为一级",
                        "越接近 0 越好",
                        "p > 0.05 才像白噪声",
                    ],
                    "grade": [grade, grade, grade, grade],
                }
            ),
            limit=20,
        )
        notes.append("后验差比值 C 越小、小误差概率 P 越大，说明残差越接近白噪声。")
    figures = []
    forecast_plot = context.flag("forecast_plot", True)
    if forecast_plot:
        figures.extend(_gm11_figure(context, record, horizon, ci_band))
    return registry.result(
        "series.gm11",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


LONGITUDE_NAMES = ("longitude", "long", "lon", "lng", "经度", "横坐标", "x")
LATITUDE_NAMES = ("latitude", "lat", "纬度", "纵坐标", "y")


def _coordinates(context, matrix):
    table = context.table
    names = [str(name) for name in table.raw.columns]
    lowered = [name.strip().lower() for name in names]

    def find(candidates):
        for candidate in candidates:
            for index, name in enumerate(lowered):
                if name == candidate:
                    return names[index]
        return None

    first = find(LONGITUDE_NAMES)
    other = find(LATITUDE_NAMES)
    if not first or not other or first == other:
        return None
    try:
        x = pd.to_numeric(table.raw[first], errors="coerce").to_numpy(dtype=float)
        y = pd.to_numeric(table.raw[other], errors="coerce").to_numpy(dtype=float)
    except (TypeError, ValueError):
        return None
    if x.size != y.size:
        return None
    return np.column_stack([x, y])


def _moran_figure(context, values, spatial_lag, moran_i, pvalue, coordinates):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过 Moran 散点图。")
        return []
    centre = float(values.mean())
    deviation = values - centre
    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    slope, intercept = np.polyfit(deviation, spatial_lag, 1)
    axes[0].axhline(0, color="#9ca3af", linewidth=0.8)
    axes[0].axvline(0, color="#9ca3af", linewidth=0.8)
    axes[0].scatter(deviation, spatial_lag, s=22, c="#4f7cff", alpha=0.8)
    grid = np.linspace(float(deviation.min()), float(deviation.max()), 50)
    axes[0].plot(
        grid, slope * grid + intercept, color="#ef4444", linewidth=1.2, label=f"斜率 {slope:.3f}"
    )
    axes[0].set_xlabel("变量偏离均值的量")
    axes[0].set_ylabel("空间滞后（邻居加权平均）")
    axes[0].set_title(f"Moran 散点图：I={moran_i:.4f}，p={pvalue:.4f}")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)
    quadrants = np.where(
        (deviation > 0) & (spatial_lag > 0),
        "高-高",
        np.where(
            (deviation < 0) & (spatial_lag < 0), "低-低", np.where(deviation > 0, "高-低", "低-高")
        ),
    )
    colours = {"高-高": "#ef4444", "低-低": "#3b82f6", "高-低": "#f59e0b", "低-高": "#10b981"}
    for name, colour in colours.items():
        picked = quadrants == name
        if picked.any():
            axes[1].scatter(
                coordinates[picked, 0],
                coordinates[picked, 1],
                s=26,
                c=colour,
                label=f"{name}（{int(picked.sum())}）",
            )
    axes[1].set_xlabel("坐标 1")
    axes[1].set_ylabel("坐标 2")
    axes[1].set_title("局部聚集类型分布")
    axes[1].legend(fontsize=7)
    axes[1].grid(alpha=0.3)
    figure.tight_layout()
    return _saved(context, figure, "series_moran_scatter")


@register("series.moran")
def moran(context):
    table = context.table
    matrix = table.matrix()
    coordinates = _coordinates(context, matrix)
    if coordinates is None:
        raise MethodError(
            "Moran's I 需要空间坐标；请提供 longitude/latitude/x/y 两列，"
            "或在空间中用 features 作为坐标。"
        )
    values = table.numeric_target()
    if values is None:
        raise MethodError("Moran's I 需要数值目标列。")
    keep = np.isfinite(values)
    values = np.asarray(values, dtype=float)[keep]
    coordinates = np.asarray(coordinates, dtype=float)[keep]
    if values.size < 8:
        raise MethodError("Moran's I 至少需要 8 个有效观测。")

    n = values.size
    weights_kind = context.text("weights", "distance", ("knn", "queen", "distance", "delaunay"))
    neighbours = context.whole("neighbours", 4, 1, max(1, n - 1))
    auto_threshold = _percentile_threshold(coordinates, 50) if weights_kind == "distance" else None
    threshold = context.number("threshold", auto_threshold, 1e-9, 1e9)
    permutation_count = context.whole("permutations", 999, 99, 9999)
    seed = context.whole("moran_seed", 20240517, 0, 2**31 - 1)
    alternative = context.text("alternative", "two-sided", ("two-sided", "greater", "less"))
    lisa = context.flag("lisa", True)
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    spatial = _spatial_weight_object(weights_kind, coordinates, neighbours, threshold)
    if len(spatial.islands):
        context.warn(
            f"空间权重里有 {len(spatial.islands)} 个孤立点，这些点没有邻居，"
            "可用 neighbours 或 threshold 调整。"
        )
    weights = _dense_standardised(spatial)
    total = float(weights.sum())
    if total <= EPS:
        raise MethodError("空间权重矩阵全为 0，请增大 threshold 或 neighbours。")

    mean = float(values.mean())
    deviation = values - mean
    denominator = float((deviation**2).sum())
    numerator = float((weights * np.outer(deviation, deviation)).sum())
    moran_i = n / total * numerator / max(denominator, EPS)
    expected = -1.0 / (n - 1)
    s0 = total
    s1 = 0.5 * float(((weights + weights.T) ** 2).sum())
    s2 = float((weights.sum(axis=1) + weights.sum(axis=0)) ** 2 @ np.ones(n))
    variance = (n * n * s1 - n * s2 + 3 * s0 * s0) / max(
        (n - 1) * (n + 1) * s0 * s0, EPS
    ) - expected**2
    variance = max(variance, EPS)
    z_score = (moran_i - expected) / math.sqrt(variance)
    from scipy import stats as sps

    if alternative == "greater":
        pvalue = float(1 - sps.norm.cdf(z_score))
    elif alternative == "less":
        pvalue = float(sps.norm.cdf(z_score))
    else:
        pvalue = float(2 * (1 - sps.norm.cdf(abs(z_score))))

    rng = np.random.default_rng(seed)
    exceed = 0
    observed = abs(float(moran_i) - expected)
    for _ in range(permutation_count):
        shuffled = rng.permutation(values)
        shifted = shuffled - shuffled.mean()
        statistic = (
            n
            / total
            * float((weights * np.outer(shifted, shifted)).sum())
            / max(float((shifted**2).sum()), EPS)
        )
        if alternative == "two-sided":
            hit = abs(statistic - expected) >= observed
        elif alternative == "greater":
            hit = (statistic - expected) >= (moran_i - expected)
        else:
            hit = (expected - statistic) >= (expected - moran_i)
        if hit:
            exceed += 1
    permutation_p = (exceed + 1) / (permutation_count + 1)

    degrees = [len(ring) for ring in spatial.neighbors.values()]
    metrics = {
        "observations": n,
        "weights": weights_kind,
        "neighbours": neighbours,
        "permutations": permutation_count,
        "moran_seed": int(seed),
        "alternative": alternative,
        "alpha": alpha,
        "lisa": bool(lisa),
        "average_neighbours": round(float(np.mean(degrees)), 4),
        "threshold": None if threshold is None else round(threshold, 6),
        "moran_i": round(float(moran_i), 6),
        "expected_i": round(float(expected), 6),
        "z_score": round(float(z_score), 6),
        "p_value": round(pvalue, 8),
        "permutation_p_value": round(float(permutation_p), 8),
        "spatial_autocorrelation": (
            "正相关（聚集）"
            if moran_i > expected and pvalue < alpha
            else "负相关（分散）"
            if moran_i < expected and pvalue < alpha
            else "不显著"
        ),
    }
    tables = {}
    notes = [
        "Moran's I 大于期望值表示相似值在空间上聚集，小于期望值表示高低相间。",
        f"备择假设为 {alternative}，显著性水平 {alpha:g}；置换检验用 {permutation_count} 次重排。",
        "置换检验不依赖正态假设，把观测值随机重排后统计超过实际值的比例得到 p 值。",
    ]
    if lisa:
        local = n * deviation * (weights @ deviation) / max(denominator, EPS)
        rows = pd.DataFrame(
            {
                "index": range(1, n + 1),
                "value": numbers(values, 6),
                "deviation": numbers(deviation, 6),
                "local_moran": numbers(local, 6),
                "cluster": [
                    "高-高"
                    if local[index] > 0 and deviation[index] > 0
                    else "低-低"
                    if local[index] > 0
                    else "高-低"
                    if deviation[index] > 0
                    else "低-高"
                    for index in range(n)
                ],
            }
        )
        clustering = rows["cluster"].value_counts()
        metrics["local_clusters"] = {str(key): int(value) for key, value in clustering.items()}
        tables["local_moran"] = table_of(rows, limit=80)
        notes.append("局部 Moran 指数用于定位高-高与低-低聚集区。")
    else:
        notes.append("已关闭局部 Moran 指数（LISA）输出。")
    spatial_lag = weights @ deviation
    metrics["spatial_lag_correlation"] = round(float(np.corrcoef(deviation, spatial_lag)[0, 1]), 6)
    metrics["spatial_lag_std"] = round(float(np.std(spatial_lag)), 6)
    figures = []
    scatter_plot = context.flag("scatter_plot", True)
    if scatter_plot:
        figures.extend(_moran_figure(context, values, spatial_lag, moran_i, pvalue, coordinates))
    return registry.result(
        "series.moran",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _spatial_figure(context, values, coordinates, fitted, rows, kind, names):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过空间回归图。")
        return []
    predicted = getattr(fitted, "predy", None)
    if predicted is None:
        return []
    predicted = np.asarray(predicted, dtype=float).ravel()
    if predicted.size != values.size:
        return []
    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    axes[0].scatter(values, predicted, s=22, c="#4f7cff", alpha=0.8)
    span = [float(min(values.min(), predicted.min())), float(max(values.max(), predicted.max()))]
    axes[0].plot(span, span, color="#ef4444", linestyle="--", linewidth=1)
    residual = values - predicted
    axes[0].set_xlabel("观测值")
    axes[0].set_ylabel("拟合值")
    axes[0].set_title(
        f"{_spatial_label(kind)}：观测与拟合（残差标准差 {float(np.std(residual)):.4g}）"
    )
    axes[0].grid(alpha=0.3)
    terms = [str(item) for item in rows["term"]]
    coefficients = np.asarray(rows["coefficient"], dtype=float)
    colours = ["#ef4444" if value < 0 else "#4f7cff" for value in coefficients]
    axes[1].barh(range(len(terms)), coefficients, color=colours)
    axes[1].set_yticks(range(len(terms)))
    axes[1].set_yticklabels(terms, fontsize=7)
    axes[1].axvline(0, color="#374151", linewidth=0.8)
    axes[1].set_title("系数估计")
    axes[1].grid(alpha=0.3, axis="x")
    figure.tight_layout()
    return _saved(context, figure, "series_spatial_fit")


@register("series.spatial")
def spatial_model(context):
    from spreg import OLS, GM_Combo, GM_Error, ML_Error, ML_Lag  # noqa: F401

    table = context.table
    matrix = table.matrix()
    coordinates = _coordinates(context, matrix)
    if coordinates is None:
        raise MethodError("空间回归需要坐标列（longitude/latitude 或 x/y）。")
    target = table.numeric_target()
    if target is None:
        raise MethodError("空间回归需要一个数值结果列。")

    values = np.asarray(target, dtype=float)
    keep = np.isfinite(values) & np.isfinite(coordinates).all(axis=1)
    values = values[keep]
    coordinates = np.asarray(coordinates, dtype=float)[keep]
    if values.size < 12:
        raise MethodError("空间回归至少需要 12 个有效观测。")

    kind = context.text("kind", "lag", ("lag", "error", "durbin", "ols"))
    weights_kind = context.text("weights", "knn", ("knn", "queen", "distance", "delaunay"))
    default_k = max(2, min(6, int(round(np.sqrt(values.size)))))
    neighbours = context.whole("neighbours", default_k, 1, values.size - 1)
    auto_threshold = _percentile_threshold(coordinates, 25) if weights_kind == "distance" else None
    threshold = context.number("threshold", auto_threshold, 1e-9, 1e9)
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    slx_lags = context.whole("slx_lags", 1, 1, 3)
    effects = context.want("effects") or []
    if isinstance(effects, str):
        effects = [effects]
    effects = [str(item) for item in effects]
    allowed_effects = ("direct", "indirect", "total")
    invalid_effects = [item for item in effects if item not in allowed_effects]
    if invalid_effects:
        raise MethodError(f"effects 只能是：{'、'.join(allowed_effects)}。")
    weights_summary = context.flag("weights_summary", False)
    if weights_kind == "queen":
        context.warn(
            "Queen 邻接由坐标推导，边界情形可能产生孤立点；点数据通常更适用 weights=delaunay。"
        )
    if weights_kind == "knn":
        context.warn(
            f"knn 权重使用 {neighbours} 个最近邻居（自动取值，可用 neighbours 调整）。"
            "点坐标数据建议改用 weights=delaunay，它是按几何三角剖分确定的，"
            "不必人为选 k。"
        )
    weights = _spatial_weight_object(weights_kind, coordinates, neighbours, threshold)
    if len(weights.islands):
        raise MethodError(f"空间权重里有 {len(weights.islands)} 个孤立点，请增大邻居数或距离阈值。")
    weights.transform = "r"

    requested = context.want("columns")
    selected_names, selected = registry.subset(table, requested)
    if context.flag("keep_coordinates"):
        regressors = selected[keep]
        regressor_names = list(selected_names)
    else:
        kept = [index for index, name in enumerate(selected_names) if not _is_coordinate_name(name)]
        regressors = selected[keep][:, kept] if kept else selected[keep][:, :0]
        regressor_names = [selected_names[index] for index in kept]
        dropped = [name for name in selected_names if _is_coordinate_name(name)]
        if dropped:
            context.warn(
                f"已把坐标列 {'、'.join(str(name) for name in dropped)} "
                "从解释变量里排除（坐标只用于构造空间权重）；"
                "需要保留时传 keep_coordinates=true。"
            )
    if not regressor_names:
        raise MethodError("排除坐标列后没有可用的解释变量，请补充特征或传 keep_coordinates=true。")

    design = np.column_stack([np.ones(values.size), regressors])
    try:
        if kind == "ols":
            fitted = OLS(values, design, w=weights, spat_diag=True, moran=True)
        elif kind == "error":
            fitted = ML_Error(values, design, w=weights)
        elif kind == "durbin":
            fitted = GM_Combo(values, design, w=weights, w_lags=slx_lags, lag_q=True)
        else:
            fitted = ML_Lag(values, design, w=weights)
    except Exception as error:
        raise MethodError(f"空间模型拟合失败：{error}")

    beta_names = _spatial_names(regressor_names, kind, fitted, slx_lags)
    betas = np.asarray(fitted.betas).ravel()
    rows = pd.DataFrame({"term": beta_names[: betas.size], "coefficient": numbers(betas, 6)})
    statistics = getattr(fitted, "z_stat", None)
    if statistics is not None:
        block = np.asarray(statistics)
        if block.ndim == 2 and block.shape[1] >= 2 and block.shape[0] == betas.size:
            rows["z_value"] = numbers(block[:, 0], 6)
            rows["p_value"] = numbers(block[:, 1], 8)
            rows["significant"] = [bool(value < alpha) for value in block[:, 1]]

    metrics = {
        "model": kind,
        "weights": weights_kind,
        "threshold": None if threshold is None else round(threshold, 6),
        "observations": int(values.size),
        "features": len(regressor_names),
        "feature_names": list(regressor_names),
        "alpha": alpha,
        "slx_lags": slx_lags,
        "weights_summary": bool(weights_summary),
        "effects": effects,
    }
    for label, value in (
        ("pseudo_r_squared", getattr(fitted, "pr2", None)),
        ("r_squared", getattr(fitted, "r2", None)),
    ):
        if value is not None and np.isfinite(float(value)):
            metrics[label] = round(float(value), 6)
    if getattr(fitted, "logll", None) is not None:
        metrics["log_likelihood"] = round(float(fitted.logll), 6)
    if getattr(fitted, "aic", None) is not None:
        metrics["aic"] = round(float(fitted.aic), 6)

    for key, position in (("spatial_lag_rho", betas.size - 1),):
        if kind in ("lag", "durbin") and position >= 0:
            metrics[key] = round(float(betas[position]), 6)
            metrics["spatial_dependence"] = abs(float(betas[position])) > 0.05
    if kind == "error":
        metrics["spatial_error_lambda"] = round(float(betas[-1]), 6)
        metrics["spatial_dependence"] = abs(float(betas[-1])) > 0.05
    if kind == "durbin":
        endogenous = len(beta_names) - betas.size
        if endogenous > 0 and "W×" in " ".join(beta_names):
            metrics["spatial_lag_of_features"] = "已包含"

    degrees = []
    try:
        degrees = [len(ring) for ring in weights.neighbors.values()]
        metrics["avg_neighbours"] = round(float(np.mean(degrees)), 4)
        metrics["isolated_points"] = int(len(weights.islands))
    except Exception:
        pass

    if kind == "ols":
        diagnostics = np.asarray(getattr(fitted, "moran_res", []) or [], dtype=float).ravel()
        if diagnostics.size >= 3:
            metrics["moran_residual_i"] = round(float(diagnostics[0]), 6)
            metrics["moran_residual_z"] = round(float(diagnostics[1]), 6)
            metrics["moran_residual_p"] = round(float(diagnostics[2]), 8)
            metrics["residual_spatial_autocorrelation"] = bool(diagnostics[2] < alpha)
        elif diagnostics.size >= 2:
            metrics["moran_residual_i"] = round(float(diagnostics[0]), 6)
            metrics["moran_residual_p"] = round(float(diagnostics[1]), 8)
            metrics["residual_spatial_autocorrelation"] = bool(diagnostics[1] < alpha)
        for label, attribute in (
            ("lm_lag", "lm_lag"),
            ("lm_error", "lm_error"),
            ("rlm_lag", "rlm_lag"),
            ("rlm_error", "rlm_error"),
        ):
            block = getattr(fitted, attribute, None)
            if block is None:
                continue
            block = np.asarray(block).ravel()
            if block.size >= 2:
                metrics[f"{label}_statistic"] = round(float(block[0]), 6)
                metrics[f"{label}_p"] = round(float(block[1]), 8)
                if label == "lm_lag":
                    metrics["lm_lag_p"] = round(float(block[1]), 8)

    tables = {"coefficients": table_of(rows, limit=60)}
    notes = [
        f"采用的模型：{_spatial_label(kind)}；权重由坐标构造（{weights_kind}）并做行标准化。",
        "空间滞后模型的 rho 显著说明邻居的取值会影响本地取值；"
        "空间误差模型的 lambda 显著说明存在未观测到的空间相关因素。",
        "先用 kind=ols 看残差的 Moran's I：不显著才说明普通回归够用。",
        f"显著性判断按 alpha={alpha:g}。",
    ]
    if effects:
        table = _spatial_effect_rows(kind, betas, weights, regressor_names, values.size)
        if table is None:
            context.warn(f"模型 {kind} 没有可分解的空间效应，已忽略 effects 设定。")
        else:
            content = table[table["effect"].isin(effects)]
            tables["effects"] = table_of(content, limit=60)
            notes.append(
                "直接效应是本地区变量的影响，间接效应是邻居变量的溢出影响，总效应是两者之和。"
            )
    else:
        notes.append("未做效应分解；需要时把 effects 设为 direct、indirect 或 total。")
    if weights_summary:
        dense = _dense_standardised(weights)
        links = int(np.count_nonzero(np.asarray(weights.sparse.todense())))
        tables["weights_summary"] = table_of(
            pd.DataFrame(
                {
                    "indicator": [
                        "观测数",
                        "非零连接数",
                        "平均邻居数",
                        "最大邻居数",
                        "最小邻居数",
                        "行标准化后行和均值",
                        "孤立点数",
                    ],
                    "value": [
                        int(values.size),
                        links,
                        round(float(np.mean(degrees)), 4) if degrees else None,
                        int(np.max(degrees)) if degrees else None,
                        int(np.min(degrees)) if degrees else None,
                        round(float(dense.sum(axis=1).mean()), 6),
                        int(len(weights.islands)),
                    ],
                }
            ),
            limit=20,
        )
        notes.append("空间权重矩阵摘要列出了连接数与邻居数分布，便于核对权重构造是否合理。")
    figures = []
    forecast_plot = context.flag("forecast_plot", True)
    if forecast_plot:
        figures.extend(
            _spatial_figure(context, values, coordinates, fitted, rows, kind, regressor_names)
        )
    return registry.result(
        "series.spatial",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


COORDINATE_NAMES = (
    "longitude",
    "long",
    "lon",
    "lng",
    "x",
    "经度",
    "横坐标",
    "latitude",
    "lat",
    "y",
    "纬度",
    "纵坐标",
    "coord",
    "geometry",
)


def _is_coordinate_name(name):
    return str(name).strip().lower() in COORDINATE_NAMES


def _spatial_label(kind):
    return {
        "lag": "空间滞后模型（ML）",
        "error": "空间误差模型（ML）",
        "durbin": "空间杜宾模型（GM）",
        "ols": "普通最小二乘 + 空间诊断",
    }[kind]


def _spatial_names(regressor_names, kind, fitted, slx_lags=1):
    base = ["常数项"] + list(regressor_names)
    size = np.asarray(fitted.betas).ravel().size
    names = list(base)
    if kind == "lag":
        names.append("rho（空间滞后）")
    elif kind == "error":
        names.append("lambda（空间误差）")
    elif kind == "durbin":
        extra = size - len(base)
        if extra >= 1:
            names.append("rho（空间滞后）")
        for lag in range(1, slx_lags + 1):
            label = "W×" if lag == 1 else f"W{lag}×"
            names.extend(f"{label}{name}" for name in base)
    while len(names) < size:
        names.append(f"参数{len(names)}")
    return names[:size]


def _spatial_effect_rows(kind, betas, weights, regressor_names, size):
    if kind == "lag":
        rho = float(betas[-1])
        dense = _dense_standardised(weights)
        leak = np.linalg.inv(np.eye(size) - rho * dense)
        coefficients = np.asarray(betas, dtype=float)[1 : 1 + len(regressor_names)]
        rows = []
        for name, coefficient in zip(regressor_names, coefficients):
            direct = float(coefficient * np.trace(leak) / size)
            total = float(coefficient * leak.sum() / size)
            rows.append({"effect": "direct", "term": str(name), "value": round(direct, 6)})
            rows.append(
                {"effect": "indirect", "term": str(name), "value": round(total - direct, 6)}
            )
            rows.append({"effect": "total", "term": str(name), "value": round(total, 6)})
        return pd.DataFrame(rows)
    if kind in ("ols", "error"):
        rows = []
        for position, name in enumerate(regressor_names, start=1):
            coefficient = round(float(betas[position]), 6)
            if kind == "ols":
                rows.append({"effect": "direct", "term": str(name), "value": coefficient})
                rows.append({"effect": "total", "term": str(name), "value": coefficient})
            else:
                rows.append({"effect": "direct", "term": str(name), "value": coefficient})
        return pd.DataFrame(rows)
    return None


def weights_build_delaunay(coordinates):
    from libpysal.weights import Voronoi

    voronoi = Voronoi(np.asarray(coordinates, dtype=float))
    ring = voronoi.neighbors
    if isinstance(ring, dict):
        return {int(key): [int(value) for value in values] for key, values in ring.items()}
    return {index: [int(value) for value in values] for index, values in enumerate(ring)}


def _geo_points(coordinates):
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import Point

    frame = pd.DataFrame(np.asarray(coordinates, dtype=float), columns=["x", "y"])
    return gpd.GeoDataFrame(
        frame, geometry=[Point(float(x), float(y)) for x, y in np.asarray(coordinates, dtype=float)]
    )


def _distance_weights(coordinates, threshold):
    from scipy.spatial.distance import cdist

    distances = cdist(coordinates, coordinates)
    adjacent = (distances <= threshold) & (distances > 0)
    size = coordinates.shape[0]
    return {index: list(np.where(adjacent[index])[0]) for index in range(size)}


def _percentile_threshold(coordinates, percentile):
    from scipy.spatial.distance import cdist

    distances = cdist(np.asarray(coordinates, dtype=float), np.asarray(coordinates, dtype=float))
    positive = distances[distances > 0]
    if positive.size == 0:
        return 1.0
    return float(np.percentile(positive, percentile))


def _spatial_weight_object(kind, coordinates, neighbours, threshold):
    from libpysal.weights import KNN, Queen, W

    points = np.asarray(coordinates, dtype=float)
    if kind == "queen":
        base = Queen.from_dataframe(_geo_points(points))
    elif kind == "delaunay":
        base = W(weights_build_delaunay(points), silence_warnings=True)
    elif kind == "distance":
        return W(_distance_weights(points, threshold), silence_warnings=True)
    else:
        base = KNN.from_array(points, k=int(neighbours))
    if threshold is None:
        return base
    from scipy.spatial.distance import cdist

    distances = cdist(points, points)
    capped = {
        int(node): [int(other) for other in ring if distances[node, other] <= threshold]
        for node, ring in base.neighbors.items()
    }
    return W(capped, silence_warnings=True)


def _dense_standardised(weights):
    matrix = weights.sparse
    dense = np.asarray(matrix.toarray() if hasattr(matrix, "toarray") else matrix, dtype=float)
    row_sum = dense.sum(axis=1, keepdims=True)
    return np.divide(dense, np.where(row_sum <= EPS, 1.0, row_sum))


def _panel_effects_figure(context, fitted, frame, target_column, kind, entity_count):
    try:
        import matplotlib.pyplot as plt
        from scipy import stats as sps  # noqa: F401
    except ImportError:
        context.warn("未安装 matplotlib，跳过个体效应图。")
        return []
    effects = getattr(fitted, "estimated_effects", None)
    if effects is None or effects.empty:
        context.warn("当前面板设定没有可用的个体效应序列，跳过个体效应图。")
        return []
    column = str(effects.columns[0])
    merged = effects.join(frame[[target_column]], how="inner")
    grouped = merged.groupby(level=0).mean()
    if grouped.empty:
        return []
    values_all = grouped[column].to_numpy()
    order = np.argsort(-values_all)
    shown = order[: min(len(order), 30)]
    labels = [str(grouped.index[index]) for index in shown]
    values = values_all[shown]
    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))
    colours = ["#ef4444" if value < 0 else "#4f7cff" for value in values]
    axes[0].barh(range(len(shown)), values, color=colours)
    axes[0].set_yticks(range(len(shown)))
    axes[0].set_yticklabels(labels, fontsize=6)
    axes[0].axvline(0, color="#374151", linewidth=0.8)
    axes[0].set_title(f"个体效应（前 {len(shown)} 个，共 {entity_count} 个个体）")
    axes[0].grid(alpha=0.3, axis="x")
    axes[1].hist(values_all, bins=min(20, max(5, values_all.size // 2)), color="#4f7cff", alpha=0.8)
    axes[1].axvline(
        float(values_all.mean()),
        color="#ef4444",
        linestyle="--",
        linewidth=1,
        label=f"均值 {float(values_all.mean()):.4g}",
    )
    axes[1].set_title("个体效应分布")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    figure.suptitle(f"{kind} 面板模型的个体异质性", fontsize=11)
    figure.tight_layout()
    return _saved(context, figure, "series_panel_effects")


def _panel_forecast_figure(context, frame, target_column, horizon, confidence):
    try:
        import matplotlib.pyplot as plt
        from scipy import stats as sps
    except ImportError:
        context.warn("未安装 matplotlib，跳过面板预测图。")
        return []
    series = frame[[target_column]].groupby(level=1).mean().sort_index()
    values = series[target_column].to_numpy(dtype=float)
    if values.size < 4:
        context.warn("时间点太少，跳过面板预测图。")
        return []
    steps = np.arange(values.size, dtype=float)
    slope, intercept = np.polyfit(steps, values, 1)
    residual = values - (slope * steps + intercept)
    spread = float(np.std(residual))
    future = np.arange(values.size, values.size + horizon, dtype=float)
    projection = slope * future + intercept
    quantile = float(sps.norm.ppf(1 - (1 - confidence) / 2))
    figure, axis = plt.subplots(figsize=(9.5, 4.2))
    axis.plot(steps + 1, values, marker="o", markersize=3, color="#374151", label="个体均值")
    axis.plot(future + 1, projection, color="#4f7cff", label="趋势外推")
    axis.fill_between(
        future + 1,
        projection - quantile * spread,
        projection + quantile * spread,
        color="#4f7cff",
        alpha=0.2,
        label=f"{confidence * 100:g}% 区间",
    )
    axis.set_title(f"面板个体均值的 {horizon} 期外推")
    axis.legend(fontsize=8)
    axis.grid(alpha=0.3)
    figure.tight_layout()
    return _saved(context, figure, "series_panel_forecast")


@register("series.panel")
def panel(context):
    from linearmodels.panel import PanelOLS, RandomEffects

    table = context.table
    group_column = context.text("group_column")
    time_column = context.text("time_column")
    if group_column:
        if group_column not in table.raw.columns:
            raise MethodError(
                f"个体列 {group_column} 不在数据中。可用列："
                f"{'、'.join(str(name) for name in table.raw.columns[:20])}。"
            )
        entity = table.raw[group_column].to_numpy()
    else:
        entity = table.group()
        group_column = table.group_name
    if time_column:
        if time_column not in table.raw.columns:
            raise MethodError(
                f"时间列 {time_column} 不在数据中。可用列："
                f"{'、'.join(str(name) for name in table.raw.columns[:20])}。"
            )
        time = table.raw[time_column].to_numpy()
    else:
        time = table.time()
        time_column = table.time_name
    if entity is None:
        raise MethodError("面板模型需要个体列（group）；可用 group_column 指定。")
    if time is None:
        raise MethodError("面板模型需要时间列（time）；可用 time_column 指定。")
    target = table.numeric_target()
    if target is None:
        raise MethodError("面板模型需要数值目标列。")
    kind = context.text("kind", "fixed", ("fixed", "random", "between"))
    hausman = context.flag("hausman", True)
    standard_errors = context.text(
        "std_errors", "unadjusted", ("unadjusted", "robust", "clustered")
    )
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    entity_effects = context.flag("entity_effects", True)
    time_effects = context.flag("time_effects", False)
    effects_plot = context.flag("effects_plot", True)
    forecast_plot = context.flag("forecast_plot", True)
    horizon = context.whole("horizon", 6, 1, 60)
    confidence = context.number("conf_level", 0.95, 0.5, 0.999)

    selected_names, selected = registry.subset(table, context.want("columns"))
    frame = pd.DataFrame(selected, columns=selected_names)
    frame["__target__"] = target
    index = pd.MultiIndex.from_arrays(
        [pd.factorize(entity)[0], pd.factorize(time)[0]], names=["entity", "time"]
    )
    frame.index = index
    if frame.index.duplicated().any():
        raise MethodError("存在重复的个体-时间组合，请先聚合到唯一的面板结构。")

    def covariance(cov_type):
        options = {"cov_type": cov_type}
        if cov_type == "clustered":
            options["clusters"] = pd.DataFrame(
                {"cluster": frame.index.get_level_values(0)}, index=frame.index
            )
        return options

    def fit_effects(cov_type=standard_errors):
        return PanelOLS(
            frame["__target__"],
            frame[selected_names],
            entity_effects=entity_effects,
            time_effects=time_effects,
        ).fit(**covariance(cov_type))

    def fit_random(cov_type=standard_errors):
        options = dict(covariance(cov_type))
        options.pop("clusters", None)
        return RandomEffects(frame["__target__"], frame[selected_names]).fit(**options)

    try:
        if kind == "random":
            fitted = fit_random()
        elif kind == "fixed":
            fitted = fit_effects()
        else:
            fitted = PanelOLS(
                frame["__target__"],
                frame[selected_names],
                entity_effects=entity_effects,
                time_effects=time_effects,
            ).fit(**covariance("unadjusted" if standard_errors == "clustered" else standard_errors))
    except Exception as error:
        raise MethodError(f"面板模型拟合失败：{error}")

    rows = pd.DataFrame(
        {
            "term": [str(name) for name in fitted.params.index],
            "coefficient": numbers(fitted.params.to_numpy(), 6),
            "std_error": numbers(fitted.std_errors.to_numpy(), 6),
            "t_value": numbers(fitted.tstats.to_numpy(), 6),
            "p_value": numbers(fitted.pvalues.to_numpy(), 8),
        }
    )
    rows["significant"] = [bool(value < alpha) for value in fitted.pvalues]
    metrics = {
        "kind": kind,
        "group_column": group_column,
        "time_column": time_column,
        "features": list(selected_names),
        "hausman": bool(hausman),
        "std_errors": standard_errors,
        "alpha": alpha,
        "entity_effects": bool(entity_effects),
        "time_effects": bool(time_effects),
        "effects_plot": bool(effects_plot),
        "forecast_plot": bool(forecast_plot),
        "horizon": int(horizon),
        "conf_level": confidence,
        "entities": int(pd.Series(entity).nunique()),
        "periods": int(pd.Series(time).nunique()),
        "observations": int(fitted.nobs),
        "r_squared_within": round(float(getattr(fitted, "rsquared_within", float("nan"))), 6)
        if np.isfinite(getattr(fitted, "rsquared_within", float("nan")))
        else None,
        "r_squared_between": round(float(getattr(fitted, "rsquared_between", float("nan"))), 6)
        if np.isfinite(getattr(fitted, "rsquared_between", float("nan")))
        else None,
        "r_squared_overall": round(float(getattr(fitted, "rsquared_overall", float("nan"))), 6)
        if np.isfinite(getattr(fitted, "rsquared_overall", float("nan")))
        else None,
    }
    notes = [
        "固定效应消除不随时间变化的个体差异；随机效应假设个体效应与解释变量不相关。",
        "面板数据必须先有稳定的个体与时间标识，且每个个体-时间只出现一次。",
        f"标准误类型为 {standard_errors}；clustered 表示按个体聚类的稳健标准误。",
    ]
    f_test = context.flag("f_test", False)
    if f_test:
        statistic = getattr(fitted, "f_statistic", None)
        if statistic is not None and np.isfinite(float(statistic.stat)):
            metrics["f_statistic"] = round(float(statistic.stat), 6)
            metrics["f_p_value"] = round(float(statistic.pval), 8)
            metrics["f_distribution"] = str(getattr(statistic, "dist_name", "") or "F")
            notes.append("F 检验的原假设是所有解释变量系数同时为零。")
        else:
            context.warn("当前面板模型没有可用的 F 统计量。")
    bp_test = context.flag("bp_test", False)
    if bp_test:
        pooled = PanelOLS(
            frame["__target__"], frame[selected_names], entity_effects=False, time_effects=False
        ).fit()
        residual = np.asarray(pooled.resids, dtype=float)
        left = frame.index.get_level_values(0).to_numpy()
        lengths = pd.Series(residual).groupby(left).size().to_numpy()
        sums = pd.Series(residual).groupby(left).sum().to_numpy()
        total = float(residual @ residual)
        entity_count = int(len(lengths))
        statistic = entity_count * entity_count / (2 * (total / max(int(frame.shape[0]), 1)))
        statistic *= float((sums**2 / np.maximum(lengths, 1)).sum() / entity_count**2)
        statistic = max(float(statistic), 0.0)
        from scipy import stats as sps

        pvalue = float(1 - sps.chi2.cdf(statistic, 1))
        metrics["bp_statistic"] = round(statistic, 6)
        metrics["bp_p_value"] = round(pvalue, 8)
        metrics["bp_recommendation"] = "存在个体随机效应" if pvalue < alpha else "个体效应不显著"
        notes.append("Breusch-Pagan LM 检验的原假设是个体效应方差为零，即普通混合回归就够用。")
    if hausman:
        try:
            fixed = fitted if kind == "fixed" else fit_effects("unadjusted")
            random_effects = fitted if kind == "random" else fit_random("unadjusted")
            common = [
                name
                for name in fixed.params.index
                if name in random_effects.params.index
                and str(name).strip().lower() not in ("const", "intercept", "常数项")
            ]
            if not common:
                raise ValueError("没有共同的可比系数")
            difference = (fixed.params[common] - random_effects.params[common]).to_numpy(
                dtype=float
            )
            covariance_block = (
                fixed.cov.loc[common, common] - random_effects.cov.loc[common, common]
            ).to_numpy(dtype=float)
            statistic = float(difference @ np.linalg.pinv(covariance_block) @ difference)
            if statistic < 0:
                context.warn("Hausman 统计量为负，说明协方差差矩阵非正定，结论仅供参考。")
                statistic = 0.0
            from scipy import stats as sps

            pvalue = float(1 - sps.chi2.cdf(statistic, len(common)))
            metrics["hausman_statistic"] = round(statistic, 6)
            metrics["hausman_dof"] = len(common)
            metrics["hausman_p_value"] = round(pvalue, 8)
            metrics["hausman_recommendation"] = "固定效应" if pvalue < alpha else "随机效应"
            notes.append(f"Hausman 检验 p 值小于 {alpha:g} 时拒绝随机效应，应改用固定效应。")
        except Exception as error:
            context.warn(f"Hausman 检验未完成：{error}")
    figures = []
    if effects_plot:
        figures.extend(
            _panel_effects_figure(
                context, fitted, frame, "__target__", kind, int(pd.Series(entity).nunique())
            )
        )
    if forecast_plot:
        figures.extend(_panel_forecast_figure(context, frame, "__target__", horizon, confidence))
    return registry.result(
        "series.panel",
        context.table,
        metrics=metrics,
        tables={"coefficients": table_of(rows, limit=60)},
        figures=figures,
        notes=notes,
    )


@register("series.threshold")
def threshold(context):
    import statsmodels.api as sm

    table = context.table
    matrix = table.matrix()
    target = table.numeric_target()
    if target is None or matrix.shape[1] < 2:
        raise MethodError("门槛回归需要目标列和至少两个特征（门槛变量 + 解释变量）。")
    names = table.feature_names
    gate_name = context.text("threshold_column") or names[0]
    if gate_name not in names:
        raise MethodError(f"门槛变量 {gate_name} 不在特征中。")
    lags = context.whole("lags", 1, 1, 12)
    bootstrap = context.whole("bootstrap", 300, 50, 5000)
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    trim = context.number("trim", 0.2, 0.05, 0.45)
    regime_count = context.whole("thresholds", 1, 1, 2)
    lr_plot = context.flag("lr_plot", False)
    gate = np.asarray(matrix[:, names.index(gate_name)], dtype=float)
    others = [index for index, name in enumerate(names) if name != gate_name]
    if not others:
        raise MethodError("除了门槛变量之外还需要至少一个解释变量。")
    response = np.asarray(target, dtype=float)
    size = response.size
    if size <= lags + 12:
        raise MethodError(f"样本不足以估计 {lags} 阶门槛模型，请减少 lags 或补充数据。")

    sample_gate = gate[lags:]
    sample_response = response[lags:]
    sample_regressors = matrix[lags:, others]
    lagged = np.column_stack([response[lags - lag : size - lag] for lag in range(1, lags + 1)])

    grid = np.linspace(trim * 100, (1 - trim) * 100, 25)
    candidates = [float(cut) for cut in np.percentile(sample_gate, grid)]
    minimal = max(5, int(round(trim * sample_gate.size)))
    usable = [
        cut
        for cut in candidates
        if minimal <= int((sample_gate <= cut).sum()) <= sample_gate.size - minimal
    ]
    if not usable:
        raise MethodError("没有找到可行的门槛分割点，样本可能太少或 trim 太大。")

    thresholds = [usable[0]]
    low = sample_gate <= usable[0]
    fitted = None
    ssr = None
    if regime_count == 1:
        best = None
        for cut in usable:
            low = sample_gate <= cut
            design = _threshold_design(sample_gate, lagged, sample_regressors, cut)
            try:
                fit = sm.OLS(sample_response, design).fit()
            except Exception:
                continue
            if best is None or fit.ssr < best[1]:
                best = (cut, float(fit.ssr), fit, low)
        if best is None:
            raise MethodError("没有找到可行的门槛分割点，样本可能太少。")
        thresholds, ssr, fitted, low = [best[0]], best[1], best[2], best[3]
    else:
        best = None
        for first in usable:
            for second in usable:
                if second <= first:
                    continue
                segment = int(((sample_gate > first) & (sample_gate <= second)).sum())
                if segment < minimal:
                    continue
                design = _threshold_design(sample_gate, lagged, sample_regressors, first, second)
                try:
                    fit = sm.OLS(sample_response, design).fit()
                except Exception:
                    continue
                if best is None or fit.ssr < best[1]:
                    best = (first, second, float(fit.ssr), fit)
        if best is None:
            raise MethodError("没有找到可行的双门槛组合，请放宽 trim 或减少解释变量。")
        thresholds, ssr, fitted = [best[0], best[1]], best[2], best[3]
        low = sample_gate <= thresholds[0]
        middle = (sample_gate > thresholds[0]) & (sample_gate <= thresholds[1])

    float(np.median(sample_gate))
    terms = ["常数项"]
    terms.extend(f"被解释变量滞后{lag}期" for lag in range(1, lags + 1))
    terms.extend(names[index] for index in others)
    terms.append("低区制指示")
    terms.append(f"低区制×{names[others[0]]}")
    if regime_count == 2:
        terms.append("中区制指示")
        terms.append(f"中区制×{names[others[0]]}")
    rows = []
    for position, term in enumerate(terms):
        if position >= len(fitted.params):
            break
        rows.append(
            {
                "term": term,
                "coefficient": round(float(fitted.params[position]), 6),
                "p_value": round(float(fitted.pvalues[position]), 8),
            }
        )

    if regime_count == 1:
        designs = [_threshold_design(sample_gate, lagged, sample_regressors, cut) for cut in usable]
    else:
        designs = []
        for cut in usable:
            try:
                designs.append(_threshold_design(sample_gate, lagged, sample_regressors, cut, cut))
            except Exception:
                continue
    linear_design = np.column_stack([np.ones(sample_response.size), lagged, sample_regressors])
    null_coefficients, *_ = np.linalg.lstsq(linear_design, sample_response, rcond=None)
    null_fitted = linear_design @ null_coefficients
    null_residual = sample_response - null_fitted
    parameters = designs[0].shape[1] if designs else len(terms)

    def supremum_f(sample):
        reference = _residual_sum_of_squares(linear_design, sample)
        best_ssr = min(_residual_sum_of_squares(design, sample) for design in designs)
        denominator = max(best_ssr / max(sample.size - parameters, 1), EPS)
        return max((reference - best_ssr) / denominator, 0.0)

    observed = supremum_f(sample_response)
    rng = np.random.default_rng(20240517)
    exceed = 0
    for _ in range(bootstrap):
        draw = null_fitted + rng.permutation(null_residual)
        if supremum_f(draw) >= observed:
            exceed += 1
    bootstrap_p = (exceed + 1) / (bootstrap + 1)

    figures = []
    if lr_plot:
        try:
            import matplotlib.pyplot as plt

            profile = []
            for cut in usable:
                design = _threshold_design(sample_gate, lagged, sample_regressors, cut)
                reference = _residual_sum_of_squares(linear_design, sample_response)
                candidate_ssr = _residual_sum_of_squares(design, sample_response)
                denominator = max(
                    candidate_ssr / max(sample_response.size - design.shape[1], 1), EPS
                )
                profile.append(max((reference - candidate_ssr) / denominator, 0.0))
            fig, axis = plt.subplots(figsize=(8, 4))
            axis.plot(usable, profile, color="#4f7cff")
            for value in thresholds:
                axis.axvline(value, color="#ef4444", linestyle="--")
            axis.set_xlabel("门槛候选值")
            axis.set_ylabel("似然比统计量")
            axis.set_title("门槛搜索的似然比序列")
            axis.grid(alpha=0.3)
            saved = context.save(fig, "series_threshold_lr")
            if saved:
                figures.append(saved)
        except ImportError:
            context.warn("未安装 matplotlib，跳过似然比序列图。")

    low_count = int(low.sum())
    high_count = int((~low).sum())
    metrics = {
        "threshold_column": gate_name,
        "threshold": round(thresholds[0], 6),
        "lags": lags,
        "thresholds": regime_count,
        "trim": trim,
        "alpha": alpha,
        "lr_plot": bool(lr_plot),
        "low_regime": low_count,
        "high_regime": high_count,
        "threshold_candidates": len(usable),
        "residual_sum_of_squares": round(float(ssr), 6),
        "r_squared": round(float(fitted.rsquared), 6),
        "observations": int(sample_response.size),
        "bootstrap": bootstrap,
        "bootstrap_p_value": round(float(bootstrap_p), 8),
        "threshold_effect_significant": bool(bootstrap_p < alpha),
    }
    tables = {"coefficients": table_of(pd.DataFrame(rows), limit=40)}
    notes = [
        "在门槛变量取值跨越门槛后，解释变量对被解释变量的影响会改变。",
        "模型按 lags 加入被解释变量的滞后项，用网格搜索最小化残差平方和确定门槛。",
        f"门槛效应用 Bootstrap 自抽样检验：p 值小于 {alpha:g} 才说明分段确实比线性模型更好。",
        f"搜索区间按两侧各修剪 {trim * 100:g}% 的样本，共 {len(usable)} 个候选门槛。",
    ]
    if regime_count == 2:
        second = round(float(thresholds[1]), 6)
        middle_count = int(middle.sum())
        metrics["second_threshold"] = second
        metrics["middle_regime"] = middle_count
        tables["regimes"] = table_of(
            pd.DataFrame(
                {
                    "regime": ["低区制", "中区制", "高区制"],
                    "rule": [
                        f"{gate_name} <= {thresholds[0]:.6g}",
                        f"{thresholds[0]:.6g} < {gate_name} <= {thresholds[1]:.6g}",
                        f"{gate_name} > {thresholds[1]:.6g}",
                    ],
                    "observations": [
                        low_count,
                        middle_count,
                        int(sample_response.size - low_count - middle_count),
                    ],
                }
            ),
            limit=10,
        )
        notes.append("双门槛模型在低、中、高三个区制上分别估计斜率。")
    return registry.result(
        "series.threshold",
        table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


def _threshold_design(gate, lagged, regressors, first, second=None):
    low = (np.asarray(gate, dtype=float) <= first).astype(float)
    regressors = np.asarray(regressors, dtype=float)
    columns = [np.ones(low.size), lagged, regressors, low, low * regressors[:, 0]]
    if second is not None and second > first:
        middle = (
            (np.asarray(gate, dtype=float) > first) & (np.asarray(gate, dtype=float) <= second)
        ).astype(float)
        columns.extend([middle, middle * regressors[:, 0]])
    return np.column_stack(columns)


def _residual_sum_of_squares(design, response):
    coefficients, *_ = np.linalg.lstsq(design, response, rcond=None)
    residual = response - design @ coefficients
    return float(residual @ residual)


def _tobit_figure(context, y, mean, lower, upper, direction):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        context.warn("未安装 matplotlib，跳过 Tobit 图。")
        return []
    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    axes[0].scatter(mean, y, s=20, c="#4f7cff", alpha=0.75, label="观测值")
    span = [float(min(mean.min(), y.min())), float(max(mean.max(), y.max()))]
    axes[0].plot(span, span, color="#ef4444", linestyle="--", linewidth=1, label="完全拟合线")
    if lower is not None:
        axes[0].axhline(
            lower, color="#f59e0b", linestyle=":", linewidth=1, label=f"左截断点 {lower:.4g}"
        )
        axes[0].scatter(
            mean[y <= lower],
            y[y <= lower],
            s=26,
            facecolors="none",
            edgecolors="#f59e0b",
            label="左截断观测",
        )
    if upper is not None:
        axes[0].axhline(
            upper, color="#10b981", linestyle=":", linewidth=1, label=f"右截断点 {upper:.4g}"
        )
        axes[0].scatter(
            mean[y >= upper],
            y[y >= upper],
            s=26,
            facecolors="none",
            edgecolors="#10b981",
            label="右截断观测",
        )
    axes[0].set_xlabel("潜在变量拟合值")
    axes[0].set_ylabel("观测值")
    axes[0].set_title(f"潜在变量与观测值对比（{direction} 截断）")
    axes[0].legend(fontsize=7)
    axes[0].grid(alpha=0.3)
    axes[1].hist(
        mean, bins=min(20, max(5, mean.size // 5)), color="#4f7cff", alpha=0.65, label="潜在变量"
    )
    axes[1].hist(y, bins=min(20, max(5, y.size // 5)), color="#ef4444", alpha=0.5, label="观测值")
    if lower is not None:
        axes[1].axvline(lower, color="#f59e0b", linestyle=":", linewidth=1)
    if upper is not None:
        axes[1].axvline(upper, color="#10b981", linestyle=":", linewidth=1)
    axes[1].set_title("潜在变量与观测值的分布")
    axes[1].legend(fontsize=8)
    axes[1].grid(alpha=0.3)
    figure.tight_layout()
    return _saved(context, figure, "series_tobit_latent")


@register("series.tobit")
def tobit(context):
    from scipy import stats as sps
    from scipy.optimize import minimize

    table = context.table
    target = table.numeric_target()
    if target is None:
        raise MethodError("Tobit 回归需要数值目标列。")
    y = np.asarray(target, dtype=float)
    direction = context.text("direction", "left", ("left", "right", "both"))
    lower = context.number("lower")
    upper = context.number("upper")
    alpha = context.number("alpha", 0.05, 1e-6, 0.5)
    marginal_effects = context.flag("marginal_effects", False)
    marginal_kind = context.text("marginal_effect_kind", "observed", ("observed", "latent"))
    latent = context.flag("latent", False)
    latent_plot = context.flag("latent_plot", True)
    if direction == "left":
        upper = None if lower is not None and upper is None else upper
    elif direction == "right":
        lower = None if upper is not None and lower is None else lower
    if lower is None and upper is None:
        if direction == "right":
            upper = float(np.max(y))
            context.warn(f"未指定截断点，已按观测最大值 {upper:.4f} 作为右截断点。")
        else:
            lower = float(np.min(y))
            context.warn(f"未指定截断点，已按观测最小值 {lower:.4f} 作为左截断点。")
    if direction == "left" and upper is not None and lower is not None:
        context.warn("direction=left 只处理左截断，已忽略上限。")
        upper = None
    if direction == "right" and lower is not None and upper is not None:
        context.warn("direction=right 只处理右截断，已忽略下限。")
        lower = None
    if direction == "both" and lower is None:
        lower = float(np.min(y))
        context.warn(f"双侧截断缺少下限，已按观测最小值 {lower:.4f} 作为左截断点。")
    if direction == "both" and upper is None:
        upper = float(np.max(y))
        context.warn(f"双侧截断缺少上限，已按观测最大值 {upper:.4f} 作为右截断点。")

    selected_names, selected = registry.subset(table, context.want("columns"))
    design = np.column_stack([np.ones(selected.shape[0]), selected])

    def negative_log_likelihood(parameters):
        beta = parameters[:-1]
        sigma = math.exp(parameters[-1])
        mean = design @ beta
        z = (y - mean) / sigma
        likelihood = np.zeros_like(y)
        uncensored = np.ones_like(y, dtype=bool)
        if upper is not None:
            uncensored &= y < upper
        if lower is not None:
            uncensored &= y > lower
        likelihood[uncensored] = sps.norm.logpdf(z[uncensored]) - math.log(sigma)
        if upper is not None:
            at_upper = y >= upper
            if at_upper.any():
                likelihood[at_upper] = sps.norm.logsf((upper - mean[at_upper]) / sigma)
        if lower is not None:
            at_lower = y <= lower
            if at_lower.any():
                likelihood[at_lower] = sps.norm.logcdf((lower - mean[at_lower]) / sigma)
        return -float(likelihood.sum())

    start = np.concatenate([np.zeros(design.shape[1]), [math.log(max(np.std(y), EPS))]])
    result = minimize(negative_log_likelihood, start, method="L-BFGS-B")
    if not result.success:
        context.warn(f"Tobit 优化未完全收敛：{result.message}")
    beta = result.x[:-1]
    sigma = math.exp(result.x[-1])
    errors = (
        np.sqrt(np.diag(result.hess_inv.todense())) if hasattr(result.hess_inv, "todense") else None
    )
    rows = []
    terms = ["常数项"] + list(selected_names)
    for position, term in enumerate(terms):
        error = None if errors is None else float(errors[position])
        rows.append(
            {
                "term": term,
                "coefficient": round(float(beta[position]), 6),
                "std_error": None if error is None else round(error, 6),
                "significant": None
                if error is None
                else bool(abs(beta[position] / max(error, EPS)) > sps.norm.ppf(1 - alpha / 2)),
            }
        )
    frame = pd.DataFrame(rows)
    mean = design @ beta
    censored = int(
        ((y <= lower).sum() if lower is not None else 0)
        + ((y >= upper).sum() if upper is not None else 0)
    )
    metrics = {
        "observations": int(y.size),
        "censored": censored,
        "features": list(selected_names),
        "direction": direction,
        "lower": None if lower is None else round(lower, 6),
        "upper": None if upper is None else round(upper, 6),
        "alpha": alpha,
        "marginal_effects": bool(marginal_effects),
        "marginal_effect_kind": marginal_kind,
        "latent": bool(latent),
        "latent_plot": bool(latent_plot),
        "sigma": round(sigma, 6),
        "log_likelihood": round(-float(result.fun), 6),
        "converged": bool(result.success),
    }
    tables = {"coefficients": table_of(frame, limit=40)}
    notes = [
        "Tobit 处理被截断或因变量只在某个范围内被观测到的情形。",
        "系数是潜在变量的影响；直接对观测值做普通回归会低估斜率。",
        f"截断方向为 {direction}，显著性按 alpha={alpha:g} 判断。",
    ]
    if marginal_effects:
        latent_scale = np.ones_like(y)
        if upper is not None:
            latent_scale = latent_scale * np.asarray(
                sps.norm.cdf((upper - mean) / sigma), dtype=float
            )
        if lower is not None:
            latent_scale = latent_scale * np.asarray(
                sps.norm.cdf((mean - lower) / sigma), dtype=float
            )
        if marginal_kind == "latent":
            factor = 1.0
        else:
            factor = float(np.mean(latent_scale))
        effect_rows = []
        for position, term in enumerate(terms):
            effect = float(beta[position]) * factor
            error = None if errors is None else float(errors[position]) * factor
            effect_rows.append(
                {
                    "term": term,
                    "coefficient": round(float(beta[position]), 6),
                    "marginal_effect": round(effect, 6),
                    "std_error": None if error is None else round(error, 6),
                }
            )
        tables["marginal_effects"] = table_of(pd.DataFrame(effect_rows), limit=40)
        metrics["marginal_effect_factor"] = round(factor, 6)
        if marginal_kind == "latent":
            notes.append(
                "未截断潜在变量上的边际效应就等于系数本身；"
                "换成 observed 可看解释变量对实际观测值的影响。"
            )
        else:
            notes.append(
                "观测值边际效应等于系数乘上平均非截断概率，衡量解释变量对实际观测值的影响。"
            )
    if latent:
        latent_rows = pd.DataFrame(
            {
                "index": range(1, y.size + 1),
                "observed": numbers(y, 6),
                "latent": numbers(mean, 6),
                "residual": numbers(y - mean, 6),
            }
        )
        tables["latent"] = table_of(latent_rows, limit=200)
        notes.append("潜在变量估计是模型给出的未受截断影响的期望值，可与观测值对照。")
    figures = []
    if latent_plot:
        figures.extend(_tobit_figure(context, y, mean, lower, upper, direction))
    return registry.result(
        "series.tobit",
        context.table,
        metrics=metrics,
        tables=tables,
        figures=figures,
        notes=notes,
    )


KERNELS = ("gaussian", "epanechnikov", "uniform", "triangle", "biweight")
STATSMODELS_KERNELS = {
    "gaussian": "gau",
    "epanechnikov": "epa",
    "uniform": "uni",
    "triangle": "tri",
    "biweight": "biw",
}


def _bandwidth_errors(target, design, coefficients, level, bandwidth, kernel):
    from scipy import stats as sps

    response = np.asarray(target, dtype=float)
    design = np.asarray(design, dtype=float)
    residual = response - design @ np.asarray(coefficients, dtype=float)
    standardized = residual / bandwidth
    if kernel == "gaussian":
        density = float(np.mean(sps.norm.pdf(standardized))) / bandwidth
    elif kernel == "epanechnikov":
        density = float(np.mean(0.75 * np.clip(1 - standardized**2, 0, None))) / bandwidth
    elif kernel == "uniform":
        density = float(np.mean(0.5 * (np.abs(standardized) <= 1))) / bandwidth
    elif kernel == "triangle":
        density = float(np.mean(np.clip(1 - np.abs(standardized), 0, None))) / bandwidth
    else:
        density = float(np.mean((15 / 16) * np.clip(1 - standardized**2, 0, None) ** 2)) / bandwidth
    density = max(density, EPS)
    weights = np.where(residual > 0, (level / density) ** 2, ((1 - level) / density) ** 2)
    inverse = np.linalg.pinv(design.T @ design)
    covariance = inverse @ (design.T * weights[np.newaxis, :]) @ design @ inverse
    errors = np.sqrt(np.abs(np.diag(covariance)))
    degrees = max(response.size - int(np.linalg.matrix_rank(design)), 1)
    ratios = np.abs(np.asarray(coefficients, dtype=float)) / np.where(errors <= EPS, EPS, errors)
    pvalues = 2 * (1 - sps.t.cdf(ratios, degrees))
    return errors, pvalues


@register("series.quantile")
def quantile(context):
    import statsmodels.api as sm

    table = context.table
    target = table.numeric_target()
    if target is None:
        raise MethodError("分位数回归需要数值目标列。")
    levels = context.want("quantiles") or [0.1, 0.25, 0.5, 0.75, 0.9]
    if isinstance(levels, str):
        levels = [float(item) for item in levels.split(",") if item.strip()]
    levels = [float(value) for value in levels if 0 < float(value) < 1]
    if not levels:
        raise MethodError("quantiles 必须是 0 到 1 之间的数值列表。")
    levels = sorted(set(levels))
    bandwidth = context.number("bandwidth", None, 1e-6, 1e6)
    kernel = context.text("kernel", "gaussian", KERNELS)
    max_iter = context.whole("max_iter", 1000, 10, 20000)
    tolerance = context.number("p_tol", 1e-6, 1e-12, 1e-2)
    coefficient_plot = context.flag("coefficient_plot", True)
    names, matrix = registry.subset(table, context.want("columns"))

    design = sm.add_constant(matrix, has_constant="add")
    rows = []
    for level in levels:
        try:
            fitted = sm.QuantReg(target, design).fit(
                q=level, kernel=STATSMODELS_KERNELS[kernel], max_iter=max_iter, p_tol=tolerance
            )
        except Exception as error:
            context.warn(f"分位点 {level} 拟合失败：{error}")
            continue
        coefficients = np.asarray(fitted.params, dtype=float)
        if bandwidth is None:
            errors = np.asarray(fitted.bse, dtype=float)
            pvalues = np.asarray(fitted.pvalues, dtype=float)
        else:
            errors, pvalues = _bandwidth_errors(
                target, design, coefficients, level, bandwidth, kernel
            )
        for position, name in enumerate(["常数项"] + list(names)):
            rows.append(
                {
                    "quantile": level,
                    "term": name,
                    "coefficient": round(float(coefficients[position]), 6),
                    "std_error": round(float(errors[position]), 6),
                    "p_value": round(float(pvalues[position]), 8),
                }
            )
    if not rows:
        raise MethodError("所有分位点都拟合失败。")
    frame = pd.DataFrame(rows)
    slopes = frame[frame["term"] != "常数项"]
    spread = slopes.groupby("term")["coefficient"].agg(["min", "max"])
    spread["range"] = spread["max"] - spread["min"]
    widest = spread["range"].idxmax()

    figures = []
    if coefficient_plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(8, 4.5))
            for name in ["常数项"] + list(names):
                track = frame[frame["term"] == name].sort_values("quantile")
                axis.plot(track["quantile"], track["coefficient"], marker="o", label=str(name))
            axis.set_xlabel("分位数")
            axis.set_ylabel("系数")
            axis.set_title("系数随分位数的变化")
            axis.legend(fontsize=7)
            axis.grid(alpha=0.3)
            saved = context.save(fig, "series_quantile_coefficients")
            if saved:
                figures.append(saved)
        except ImportError:
            context.warn("未安装 matplotlib，跳过系数变化图。")

    notes = [
        "分位数回归描述解释变量对因变量不同位置的影响，不假设同方差。",
        "如果同一变量在不同分位点的系数差异很大，说明影响不是常数。",
        f"最大迭代 {max_iter} 次、收敛容差 {tolerance:g}；核函数为 {kernel}。",
    ]
    if bandwidth is None:
        notes.append(
            "核带宽留空表示用 statsmodels 默认的 Hall-Sheather 带宽，"
            "核函数只在显式给出带宽时才参与标准误计算。"
        )
    else:
        notes.append("核带宽控制估计稀疏函数时的核密度平滑程度，只影响标准误与显著性，不改变系数。")
    return registry.result(
        "series.quantile",
        context.table,
        metrics={
            "observations": int(len(target)),
            "quantiles": levels,
            "features": list(names),
            "bandwidth": bandwidth,
            "kernel": kernel,
            "max_iter": max_iter,
            "p_tol": tolerance,
            "coefficient_plot": bool(coefficient_plot),
            "widest_effect_change": str(widest),
            "widest_range": round(float(spread.loc[widest, "range"]), 6),
        },
        tables={"coefficients": table_of(frame, limit=80)},
        figures=figures,
        notes=notes,
    )
