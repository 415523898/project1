"""Keep observations, analysis matrices and fitted preprocessing distinct."""

import copy

import numpy as np
import pandas as pd

from engine import splits, tabular

CLUSTERS = {"ml.kmeans", "ml.hierarchical", "ml.dbscan", "ml.fcm"}
DIAGNOSTICS = {"model.correlation", "model.canonical", "model.vif"}
MISSING_AWARE = {
    "prep.missing",
    "prep.duplicates",
    "model.correlation",
    "eval.topsis",
    "eval.vikor",
}


def snapshot(table):
    return {
        "rows": len(table.raw),
        "columns": len(table.raw.columns),
        "missing_cells": int(table.raw.isna().sum().sum()),
        "duplicate_rows": int(table.raw.duplicated().sum()),
    }


def method_table(source, method):
    table = copy.deepcopy(source)
    table.source_summary = snapshot(source)
    table.observed_view = False
    table.allow_missing = method in MISSING_AWARE
    # Raw descriptive methods already select their own columns. Numeric
    # analysis must not inherit imputation/encoding from a model preview.
    if (
        not method.startswith(("ml.", "causal."))
        and not (method.startswith("model.") and method not in DIAGNOSTICS)
        and method != "prep.encoding"
    ):
        candidates = getattr(table, "input_features", table.feature_names)
        names = [
            name
            for name in candidates
            if name in table.raw and pd.api.types.is_numeric_dtype(table.raw[name])
        ]
        table.frame = table.raw[names].astype(float).copy()
        table.feature_names = names
        table.imputed, table.encoded = [], []
        table.observed_view = True
    return table


def fit_model_view(context, train):
    if getattr(context, "_model_prepared", False):
        return
    table = context.table
    method = getattr(context, "method_id", "")
    if method and not (
        method.startswith("ml.") or method.startswith("model.") and method not in DIAGNOSTICS
    ):
        return
    names = getattr(table, "input_features", table.feature_names)
    matrix, features, imputed, encoded = tabular._prepare_features(table.raw, names, fit_rows=train)
    selected = context.want("columns")
    if selected:
        selected = (
            [value.strip() for value in selected.split(",")]
            if isinstance(selected, str)
            else list(selected)
        )
        absent = [name for name in selected if name not in features]
        if absent:
            from engine.registry import MethodError

            raise MethodError(
                f"训练样本中无法构造所选特征 {'、'.join(absent)}，可能为常量或仅在测试集出现。"
            )
        matrix, features = matrix[selected], selected
    table.frame, table.feature_names = matrix, features
    table.imputed, table.encoded = imputed, encoded
    context._model_prepared = True
    table.preprocessing_scope = "train_only"
    if imputed:
        context.warn(
            "模型矩阵的缺失填充值仅由训练样本估计；原始数据保留缺失，处理记录见 data.imputed。"
        )
    if encoded:
        context.warn("模型矩阵的类别映射及常量列选择仅由训练样本确定，处理记录见 data.encoded。")


def prepare(context, method):
    context.method_id = method
    table = context.table
    numeric_response = method in {
        "test.ttest",
        "test.anova",
        "test.wilcoxon",
        "test.mannwhitney",
        "test.kruskal",
        "test.friedman",
        "test.cochran",
        "model.correlation",
        "domain.control",
        "domain.capability",
        "domain.weibull",
        "domain.psm",
    } or method.startswith("series.")
    if (
        numeric_response
        and table.target_name
        and not pd.api.types.is_numeric_dtype(table.raw[table.target_name])
    ):
        from engine.registry import MethodError

        raise MethodError("该分析需要真实数值响应，文本类别不能自动编码后当作连续测量或时间序列。")
    if splits.needs_split(method, table.task):
        target = table.target()
        if target is None:
            from engine.registry import MethodError

            raise MethodError("该建模方法需要明确的目标列。")
        missing = pd.isna(target)
        if missing.any():
            from engine.registry import MethodError

            if getattr(table, "page_split", None):
                raise MethodError("目标缺失行与已有划分不兼容，请重新确认有效目标及划分。")
            count = int(missing.sum())
            table.raw = table.raw.loc[~missing].reset_index(drop=True)
            table.frame = table.frame.loc[~missing].reset_index(drop=True)
            table.rows_dropped += count
            context.warn(f"本次监督建模排除目标缺失的 {count} 行；原始输入未改写。")
        context.split_indices()
    elif method.startswith(("ml.", "causal.")) or method == "prep.encoding":
        # Non-predictive encoding is an explicit, reported analysis transform.
        if table.imputed:
            context.warn(
                "本方法使用的数值矩阵包含自动填补；原始观测不变，具体列及数量见 data.imputed。"
            )
        if table.encoded and method != "prep.encoding":
            context.warn("本方法的数值矩阵包含类别编码或常量列排除，具体转换见 data.encoded。")


def require_finite(matrix):
    if not np.isfinite(np.asarray(matrix, dtype=float)).all():
        from engine.registry import MethodError

        raise MethodError(
            "选中的观测含缺失或非有限值；本方法不会提前自动填补。请明确处理缺失后再运行。"
        )


def require_regular_time(table):
    if not table.time_name:
        return  # Explicitly supplied sample order has no physical time claim.
    from engine.registry import MethodError

    times = table.raw[table.time_name]
    if times.isna().any() or times.duplicated().any():
        raise MethodError("时间列缺失或重复，不能当作等间隔单一序列。")
    if len(times) < 3:
        return
    if pd.api.types.is_numeric_dtype(times):
        gaps = np.diff(times.to_numpy(dtype=float))
        regular = np.isfinite(gaps).all() and (gaps > 0).all() and np.allclose(gaps, gaps[0])
    else:
        try:
            regular = pd.infer_freq(pd.DatetimeIndex(times)) is not None
        except (ValueError, TypeError):
            regular = False
    if not regular:
        raise MethodError(
            "时间观测不等间隔或存在缺期，请先明确重采样/补期策略；不能按连续行号推断原时间。"
        )
