import math

import numpy as np
import pandas as pd

from engine import registry, tabular
from engine.methods.support import note_columns
from engine.registry import MethodError, numbers, register, subset, table_of

nan = math.nan


def _column_list(value):
    if value is None:
        return None
    if isinstance(value, str):
        items = [part.strip() for part in value.replace("，", ",").split(",")]
        return [part for part in items if part]
    return [str(part).strip() for part in value if str(part).strip()]


def _encoding_pool(table):
    """Text columns prep.encoding may work on, split into two groups.

    ``blocks`` are the columns the input layer already encoded into model
    features. ``reserved`` are the text columns it kept beside the numeric
    feature matrix (identifiers, survey categories, free text): they never
    enter a model on their own, but the user can still choose to encode them.
    """
    original = table.raw
    blocks = []
    named = set()
    for block in table.encoded:
        name = block.get("column")
        if name not in original.columns or str(name) in named:
            continue
        if block.get("method") not in ("onehot", "ordinal", "constant"):
            continue
        if pd.api.types.is_numeric_dtype(original[name]):
            continue
        item = dict(block)
        item["column"] = str(name)
        blocks.append(item)
        named.add(str(name))
    target = str(table.target_name or "")
    reserved = []
    for name in original.columns:
        if str(name) in named or str(name) == target:
            continue
        series = original[name]
        if pd.api.types.is_bool_dtype(series) or pd.api.types.is_numeric_dtype(series):
            continue
        reserved.append(str(name))
    return blocks, reserved


def _default_category(table, name, series, limit=200):
    """Default candidates skip timestamps, roles and near-unique ids/free text."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return False
    if str(name) in {str(table.time_name or ""), str(table.group_name or "")}:
        return False
    return int(series.nunique(dropna=True)) <= limit


def _encoded_values(working, name, method, text, levels):
    """How every original level shows up after encoding, for the mapping table."""
    if method == "onehot":
        return {
            level: (
                f"{name}={level}"[:60]
                if f"{name}={level}"[:60] in working.columns
                else "基准列（丢弃，全为 0）"
            )
            for level in levels
        }
    if method == "constant":
        return {level: "0（常量列）" for level in levels}
    found = {}
    if name in working.columns:
        values = working[name].to_numpy(dtype=float)
        for position, level in enumerate(text.to_numpy()):
            if level not in found:
                found[level] = round(float(values[position]), 6)
    return {level: found.get(level) for level in levels}


def _pick(context, available, default, role):
    chosen = _column_list(context.want("columns"))
    if not chosen:
        return list(default)
    absent = [name for name in chosen if name not in available]
    if absent:
        raise MethodError(
            f"{role} {', '.join(absent)} 不在数据列里："
            f"{', '.join(str(name) for name in available[:20])}。"
        )
    picked = [name for name in available if name in set(chosen)]
    if not picked:
        raise MethodError(f"{role}里没有可用的列。")
    return picked


def _empty(columns):
    return pd.DataFrame(columns=columns)


def _target_averages(values, codes, mask, stat, smoothing, prior):
    block = pd.DataFrame(
        {"code": np.asarray(codes)[mask], "value": np.asarray(values, dtype=float)[mask]}
    )
    grouped = block.groupby("code")["value"]
    averages = grouped.median() if stat == "median" else grouped.mean()
    if smoothing > 0.0:
        counts = grouped.count()
        averages = (averages * counts + smoothing * prior) / (counts + smoothing)
    return averages


@register("prep.outliers")
def outliers(context):
    table = context.table
    names, matrix = subset(table, context.want("columns"))
    method = context.text("method", "iqr", ("iqr", "zscore", "mad"))
    action = context.text("action", "report", ("report", "clip", "winsorize", "drop"))
    factor = context.number("factor", 3.0, 0.1, 20)
    replace = context.text("replace", "boundary", ("boundary", "median", "quantile"))
    replace_quantile = context.number("replace_quantile", 0.05, 0.0, 0.25)
    min_count = context.whole("min_count", 0, 0, 1000)
    mark = context.flag("mark", False)
    detail = context.flag("detail", True)
    plot = context.flag("plot", True)
    total = len(table.feature_names)
    note_columns(context, names, total)

    if method == "iqr":
        low = np.percentile(matrix, 25, axis=0)
        high = np.percentile(matrix, 75, axis=0)
        spread = high - low
        spread = np.where(spread <= 1e-12, 1.0, spread)
        lower = low - factor * spread
        upper = high + factor * spread
    elif method == "zscore":
        centre = matrix.mean(axis=0)
        spread = matrix.std(axis=0, ddof=0)
        spread = np.where(spread <= 1e-12, 1.0, spread)
        lower = centre - factor * spread
        upper = centre + factor * spread
    else:
        centre = np.median(matrix, axis=0)
        spread = np.median(np.abs(matrix - centre), axis=0) * 1.4826
        spread = np.where(spread <= 1e-12, 1.0, spread)
        lower = centre - factor * spread
        upper = centre + factor * spread

    below = matrix < lower
    above = matrix > upper
    flags = below | above
    counts = flags.sum(axis=0)
    gated = counts < min_count
    treated = flags & ~gated
    rows = pd.DataFrame(
        {
            "feature": names,
            "lower": numbers(lower),
            "upper": numbers(upper),
            "outliers": counts.astype(int),
            "treated": treated.sum(axis=0).astype(int),
            "gated": gated.astype(bool),
            "ratio": numbers(counts / max(table.n_rows, 1)),
        }
    )

    cleaned = matrix.copy()
    if mark:
        marked = table.frame.copy()
        for index, name in enumerate(names):
            marked[f"{name}_异常标记"] = treated[:, index].astype(float)
        table.frame = marked
        table.feature_names = [str(name) for name in marked.columns]
    mapped_matrix = matrix.copy()
    fill_low = np.zeros(matrix.shape[1], dtype=float)
    fill_high = np.zeros(matrix.shape[1], dtype=float)
    dropped = 0
    tables = {"per_feature": table_of(rows)}
    if action in ("report", "clip", "winsorize"):
        if replace == "median":
            fill_low = np.median(matrix, axis=0)
            fill_high = fill_low
        elif replace == "quantile":
            fill_low = np.percentile(matrix, replace_quantile * 100, axis=0)
            fill_high = np.percentile(matrix, (1.0 - replace_quantile) * 100, axis=0)
        else:
            fill_low = np.asarray(lower, dtype=float)
            fill_high = np.asarray(upper, dtype=float)
        for index in range(matrix.shape[1]):
            column = matrix[:, index]
            if action == "winsorize":
                order = np.argsort(column, kind="stable")
                ranks = np.empty_like(order)
                ranks[order] = np.arange(len(column))
                proportion = ranks / max(len(column) - 1, 1)
                mapped = np.percentile(column, proportion * 100)
                mapped = np.clip(mapped, lower[index], upper[index])
            elif replace == "median":
                mapped = np.where(below[:, index] | above[:, index], fill_low[index], column)
            elif replace == "quantile":
                mapped = np.where(
                    below[:, index],
                    fill_low[index],
                    np.where(above[:, index], fill_high[index], column),
                )
            else:
                mapped = np.clip(column, lower[index], upper[index])
            mapped_matrix[:, index] = mapped
            if action != "report":
                cleaned[:, index] = np.where(treated[:, index], mapped, column)
        if action != "report":
            registry.apply_matrix(table, names, cleaned)
    elif action == "drop":
        keep = ~treated.any(axis=1)
        dropped = int((~keep).sum())
        table.frame = table.frame.loc[keep].reset_index(drop=True)
        if len(table.raw) == len(keep):
            table.raw = table.raw.loc[keep].reset_index(drop=True)

    coverage = treated if action == "report" else cleaned != matrix
    if detail and action in ("report", "clip", "winsorize"):
        detail_rows = []
        for index, name in enumerate(names):
            for position in np.flatnonzero(coverage[:, index])[:200]:
                detail_rows.append(
                    {
                        "feature": name,
                        "row": int(position),
                        "before": round(float(matrix[position, index]), 6),
                        "replaced_with": round(float(mapped_matrix[position, index]), 6),
                        "side": "low" if below[position, index] else "high",
                    }
                )
        tables["outlier_detail"] = table_of(
            pd.DataFrame(detail_rows)
            if detail_rows
            else _empty(["feature", "row", "before", "replaced_with", "side"])
        )

    if action != "report":
        table.notes.append(f"已按 {method} 异常值判定执行 {action}，剩余 {table.n_rows} 行。")

    notes = [
        f"判定方式：{method}，阈值 {factor}。",
        f"只在 {len(names)}/{total} 个特征上判定，其余列不参与。",
        "report 只报告不改数据；clip/winsorize 压缩极端值；drop 删除含异常值的行。",
    ]
    if action in ("clip", "winsorize"):
        notes.append(f"压缩回填口径：{replace}。")
    if min_count > 0:
        notes.append(f"异常值少于 {min_count} 个的列不做处理，共 {int(gated.sum())} 列被跳过。")
    if mark:
        notes.append(f"已在数据中补出 {len(names)} 个 0/1 异常标记列。")
    metrics = {
        "rows": table.n_rows,
        "features": len(names),
        "features_total": total,
        "outlier_cells": int(flags.sum()),
        "treated_cells": int(treated.sum()),
        "gated_columns": int(gated.sum()),
        "rows_with_outlier": int(flags.any(axis=1).sum()),
        "rows_dropped": dropped,
        "method": method,
        "action": action,
    }
    if mark:
        metrics["marked_columns"] = len(names)

    figures = []
    if plot:
        try:
            import matplotlib.pyplot as plt

            shown = min(len(names), 12)
            fig, axis = plt.subplots(figsize=(max(6.2, 1.05 * shown + 2.4), 4.6))
            axis.boxplot(
                [matrix[:, index] for index in range(shown)],
                tick_labels=[str(name) for name in names[:shown]],
                patch_artist=True,
                boxprops={"facecolor": "#cfe0ff", "edgecolor": "#3a5fa8"},
                medianprops={"color": "#3a5fa8"},
            )
            labelled = False
            for index in range(shown):
                positions = np.flatnonzero(flags[:, index])
                if not positions.size:
                    continue
                offsets = ((np.arange(positions.size) % 5) - 2) * 0.06
                axis.scatter(
                    np.full(positions.size, index + 1) + offsets,
                    matrix[positions, index],
                    s=16,
                    color="#d64545",
                    label=None if labelled else "判定异常的点",
                    zorder=3,
                )
                labelled = True
            if labelled:
                axis.legend(fontsize=8)
            axis.set_title(f"异常值箱线图（{method} 判定，倍数 {factor}，动作 {action}）")
            axis.set_ylabel("取值")
            axis.grid(alpha=0.3, axis="y")
            figure_name = context.save(fig, "prep.outliers_异常值箱线")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过异常值箱线图。")
    return registry.result(
        "prep.outliers",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


@register("prep.missing")
def missing(context):
    table = context.table
    frame = table.raw.copy()
    original = frame.copy()
    missing_before = int(original.isna().sum().sum())
    strategy = context.text(
        "strategy",
        "median",
        ("median", "mean", "linear", "ffill", "mode", "zero", "knn", "iterative", "drop"),
    )
    neighbours = context.whole("neighbours", 5, 1, 50)
    fill_value = context.number("fill_value", 0.0, -1000000.0, 1000000.0)
    iterations = context.whole("iterations", 10, 1, 100)
    min_missing = context.whole("min_missing", 0, 0, 1000)
    drop_threshold = context.number("drop_threshold", 1.0, 0.0, 1.0)
    indicator = context.flag("indicator", False)
    plot = context.flag("plot", True)
    effective_neighbours = None
    available = [str(name) for name in frame.columns]
    picked = _pick(context, available, available, "列")

    before = frame.shape[0]
    roles = {name for name in (table.target_name, table.time_name, table.group_name) if name}
    dropped_columns = []
    if drop_threshold < 1.0:
        for name in frame.columns:
            if name in roles:
                continue
            if float(frame[name].isna().mean()) > drop_threshold:
                dropped_columns.append(str(name))
        if dropped_columns:
            frame = frame.drop(columns=dropped_columns)
            available = [str(name) for name in frame.columns]
            picked = [name for name in picked if name in set(available)]
            if not picked:
                raise MethodError(f"整列删除阈值 {drop_threshold} 把参与填充的列全部删掉了。")

    report = []
    for name in frame.columns:
        gap = int(frame[name].isna().sum())
        if gap:
            report.append(
                {"column": name, "missing": gap, "ratio": round(gap / max(len(frame), 1), 4)}
            )

    numeric = [
        name
        for name in frame.columns
        if name != table.target_name
        and name not in (table.time_name, table.group_name)
        and pd.api.types.is_numeric_dtype(frame[name])
    ]
    work = frame[numeric].astype(float)
    if not numeric:
        raise MethodError("没有可处理的数值列。")

    targets = [name for name in numeric if name in set(picked)]
    text_targets = [
        name
        for name in picked
        if name in frame.columns
        and name not in set(numeric)
        and name not in roles
        and frame[name].isna().any()
    ]
    if min_missing > 0:
        targets = [name for name in targets if int(work[name].isna().sum()) >= min_missing]
        text_targets = [
            name for name in text_targets if int(frame[name].isna().sum()) >= min_missing
        ]

    fill_map = {}
    text_fill = {}
    if strategy == "drop":
        selected = targets + text_targets
        keep = (
            frame[selected].isna().any(axis=1) if selected else pd.Series(False, index=work.index)
        )
        keep = ~keep
        filled = work[keep].reset_index(drop=True)
    elif strategy in ("mean", "median", "zero"):
        filled = work.copy()
        if targets:
            block = work[targets]
            if strategy == "mean":
                filled[targets] = block.fillna(block.mean())
            elif strategy == "median":
                filled[targets] = block.fillna(block.median())
            else:
                filled[targets] = block.fillna(fill_value)
    elif strategy == "mode":
        filled = work.copy()
        for name in targets:
            column = work[name]
            mode = column.mode()
            filled[name] = column.fillna(mode.iloc[0] if len(mode) else 0.0)
    elif strategy in ("linear", "ffill"):
        filled = work.copy()
        if targets:
            block = work[targets]
            if strategy == "linear":
                filled[targets] = block.interpolate(method="linear", limit_direction="both")
            else:
                filled[targets] = block.ffill().bfill()
    elif strategy == "knn":
        filled = work.copy()
        usable = [name for name in targets if work[name].notna().any()]
        if usable:
            from sklearn.impute import KNNImputer

            effective_neighbours = min(neighbours, max(work.shape[0] - 1, 1))
            filled[usable] = KNNImputer(n_neighbors=effective_neighbours).fit_transform(
                work[usable]
            )
    else:
        filled = work.copy()
        usable = [name for name in targets if work[name].notna().any()]
        if usable:
            from sklearn.experimental import enable_iterative_imputer  # noqa: F401
            from sklearn.impute import IterativeImputer

            filled[usable] = IterativeImputer(max_iter=iterations, random_state=0).fit_transform(
                work[usable]
            )

    if strategy != "drop":
        for name in targets:
            gap = work[name].isna()
            if bool(gap.any()):
                fill_map[name] = round(float(filled.loc[gap.to_numpy(), name].mean()), 6)

    if strategy != "drop":
        whole = frame.copy()
        whole[numeric] = filled.to_numpy()
        for name in text_targets:
            series = frame[name]
            mode = series.mode()
            choice = mode.iloc[0] if len(mode) else "缺失"
            text_fill[name] = choice
            whole[name] = series.fillna(choice)
    else:
        whole = frame.loc[keep].copy()

    indicator_columns = []
    if indicator and strategy != "drop":
        for name in list(targets) + list(text_targets):
            if name in whole.columns and bool(frame[name].isna().any()):
                label = f"{name}_缺失指示"
                whole[label] = frame[name].isna().astype(float).to_numpy()
                indicator_columns.append(label)

    common = [name for name in whole.columns if name in original.columns]
    changed = original.loc[whole.index, common].isna() & whole[common].notna()
    filled_cells = int(changed.sum().sum())
    filled_columns = int(changed.any().sum())
    rebuilt = tabular.build(
        whole,
        target=table.target_name,
        time=table.time_name,
        group=table.group_name,
        task=table.task,
    )
    table.frame = rebuilt.frame
    table.raw = rebuilt.raw
    table.feature_names = rebuilt.feature_names
    table.imputed = rebuilt.imputed
    table.encoded = rebuilt.encoded

    # A cleaning result reports the changed observations, not an additional
    # automatically imputed/encoded model preview of those observations.
    actual_names = [
        name
        for name in table.raw.columns
        if name not in roles and pd.api.types.is_numeric_dtype(table.raw[name])
    ]
    table.frame = table.raw[actual_names].astype(float).copy()
    table.feature_names = actual_names
    table.imputed = [
        {"column": name, "method": strategy, "count": int(changed[name].sum())}
        for name in changed
        if changed[name].any()
    ]
    table.encoded = []
    table.preprocessing_scope = "explicit_method"

    for item in report:
        item["fill"] = fill_map.get(item["column"], text_fill.get(item["column"]))
    participating = targets + text_targets
    skipped = [item["column"] for item in report if item["column"] not in set(participating)]
    remaining = int(table.raw.isna().sum().sum())
    rows = pd.DataFrame(report) if report else _empty(["column", "missing", "ratio", "fill"])
    notes = [
        f"填充方式：{strategy}。",
        f"参与填充的列共 {len(participating)} 个，其余列保持原样。",
        "均值/中位数/众数按列计算；KNN 与迭代法只用选中的列互相推断；drop 直接删除选中列含缺失的行。",
    ]
    if dropped_columns:
        notes.append(
            f"缺失比例高于 {drop_threshold} 的 {len(dropped_columns)} 列已整列删除："
            f"{'、'.join(dropped_columns[:10])}。"
        )
    if indicator_columns:
        notes.append(f"已补出 {len(indicator_columns)} 个缺失指示列。")
    if strategy == "zero":
        notes.append(f"零值策略的填充常数为 {fill_value}。")
    if strategy == "iterative":
        notes.append(f"迭代填充共跑 {iterations} 轮。")
    if strategy == "linear":
        notes.append("linear 策略按行顺序在相邻有效值之间线性插值。")
    if strategy == "ffill":
        notes.append("ffill 策略用上一个有效值向后填充，开头的缺失再用后一个有效值回填。")
    if min_missing > 0:
        notes.append(f"缺失数少于 {min_missing} 个的列本次不填充。")
    if skipped:
        notes.append(f"未参与填充的缺失列：{'、'.join(str(name) for name in skipped[:10])}。")
    metrics = {
        "strategy": strategy,
        "columns_with_missing": len(report),
        "imputed_columns": filled_columns,
        "participating_columns": len(participating),
        "filled_cells": filled_cells,
        "skipped_columns": len(skipped),
        "missing_cells_before": missing_before,
        "missing_cells_after": remaining,
        "rows_before": before,
        "rows_after": table.n_rows,
        "fill_value": fill_value,
        "iterations": iterations,
        "drop_threshold": drop_threshold,
        "dropped_columns": len(dropped_columns),
        "indicator": bool(indicator),
        "indicator_columns": len(indicator_columns),
    }
    if not missing_before:
        notes.append("原始输入没有缺失值，本次无需填充，实际填充 0 个单元格。")
    if min_missing > 0:
        metrics["min_missing"] = min_missing
    if effective_neighbours is not None:
        metrics["neighbours"] = effective_neighbours
        notes.append(f"KNN 使用 {effective_neighbours} 个最近邻居推断缺失值。")

    figures = []
    if plot:
        try:
            import matplotlib.pyplot as plt

            after = table.raw
            labels_before = [str(name) for name in frame.columns]
            before_ratio = [float(frame[name].isna().mean()) for name in frame.columns]
            after_ratio = [
                float(after[name].isna().mean()) if name in after.columns else 0.0
                for name in frame.columns
            ]
            fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.6))
            flags = frame.isna().to_numpy()
            shown = min(flags.shape[0], 400)
            axes[0].imshow(
                flags[:shown].T,
                aspect="auto",
                cmap="Greys",
                interpolation="nearest",
                vmin=0,
                vmax=1,
            )
            axes[0].set_yticks(range(len(labels_before)))
            axes[0].set_yticklabels(labels_before, fontsize=7)
            axes[0].set_xlabel("行号")
            scope = f"，图示前 {shown}/{len(frame)} 行" if shown < len(frame) else ""
            axes[0].set_title(f"缺失值矩阵（处理前，全表 {int(flags.sum())} 个缺失{scope}）")
            positions = np.arange(len(labels_before))
            axes[1].bar(positions - 0.2, before_ratio, width=0.4, color="#4f7cff", label="处理前")
            axes[1].bar(positions + 0.2, after_ratio, width=0.4, color="#f59e0b", label="处理后")
            axes[1].set_xticks(positions)
            axes[1].set_xticklabels(labels_before, rotation=45, ha="right", fontsize=7)
            axes[1].set_ylabel("缺失比例")
            axes[1].set_title(f"各列缺失比例对比（{strategy}）")
            axes[1].legend(fontsize=8)
            axes[1].grid(alpha=0.3, axis="y")
            figure_name = context.save(fig, "prep.missing_缺失矩阵")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过缺失值矩阵图。")
    return registry.result(
        "prep.missing",
        table,
        metrics=metrics,
        tables={"missing_by_column": table_of(rows)},
        notes=notes,
    )


@register("prep.duplicates")
def duplicates(context):
    table = context.table
    frame = table.raw
    action = context.text("action", "report", ("report", "drop", "mark"))
    keep = context.text("keep", "first", ("first", "last", "none"))
    normalize = context.text("normalize", "none", ("none", "trim", "lower", "trim_lower"))
    include_roles = context.flag("include_roles", False)
    detail = context.flag("detail", True)
    group_summary = context.flag("group_summary", False)
    plot = context.flag("plot", True)
    available = [str(name) for name in frame.columns]
    defaults = [
        name
        for name in frame.columns
        if name not in (table.target_name, table.time_name, table.group_name)
    ]
    if include_roles:
        defaults = [name for name in frame.columns]
    subset_names = _pick(context, available, defaults, "列")

    keys = frame
    if normalize != "none":
        keys = frame.copy()
        for name in subset_names:
            if pd.api.types.is_numeric_dtype(keys[name]):
                continue
            text = keys[name].astype("string")
            if normalize in ("trim", "trim_lower"):
                text = text.str.strip()
            if normalize in ("lower", "trim_lower"):
                text = text.str.lower()
            keys[name] = text

    mask = keys.duplicated(subset=subset_names, keep=False if keep == "none" else keep)
    count = int(mask.sum())
    grouped = pd.factorize(pd.MultiIndex.from_frame(keys[subset_names]), sort=False)[0]
    sizes = pd.Series(grouped).value_counts()
    groups = int((sizes > 1).sum())
    removable = count

    if action == "drop" and removable:
        keep_mask = ~mask
        kept_frame = frame[keep_mask.to_numpy()].reset_index(drop=True)
        if kept_frame.empty:
            table.raw = kept_frame
            table.frame = table.frame.iloc[:0].copy()
        else:
            rebuilt = tabular.build(
                kept_frame,
                target=table.target_name,
                time=table.time_name,
                group=table.group_name,
                task=table.task,
            )
            table.frame = rebuilt.frame
            table.raw = rebuilt.raw
            table.feature_names = rebuilt.feature_names
        table.notes.append(f"已删除 {removable} 行完全重复的特征组合。")

    sample = _empty(["重复组"] + [str(name) for name in subset_names])
    if detail and count:
        sample = frame[mask].copy()
        sample.insert(0, "重复组", grouped[mask.to_numpy()] + 1)
        sample = sample.head(20)
    if action == "mark":
        marked = table.frame.copy()
        marked["重复标记"] = mask.to_numpy().astype(float)
        table.frame = marked
        table.feature_names = [str(name) for name in marked.columns]
        table.notes.append(f"已在数据中把 {count} 行重复样本标记为 1。")
    tables = {}
    if detail:
        tables["duplicate_examples"] = table_of(sample)
    group_rows = [
        {"重复组": int(code) + 1, "行数": int(size)}
        for code, size in sizes.items()
        if int(size) > 1
    ]
    group_rows.sort(key=lambda item: item["行数"], reverse=True)
    if group_summary:
        tables["duplicate_groups"] = table_of(
            pd.DataFrame(group_rows) if group_rows else _empty(["重复组", "行数"])
        )

    notes = [
        f"按选中的 {len(subset_names)} 列判断重复，未选中的列不参与判断。",
        "默认使用全部原始特征列；目标列与时间/分组列只在被显式选中时才参与。",
    ]
    if keep != "first":
        notes.append(f"重复行的保留口径为 {keep}，标记口径随之改变。")
    if normalize != "none":
        notes.append(f"文本列先按 {normalize} 做归一化再比较。")
    if include_roles:
        notes.append("本次把目标列与时间/分组列也纳入了查重键。")
    if action == "mark":
        notes.append("mark 只增补一列 0/1 重复标记，不删除任何行。")
    if group_summary:
        notes.append(f"重复组汇总表按组内行数排序，共 {len(group_rows)} 组。")

    figures = []
    if plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7.6, 4.4))
            if group_rows:
                shown = group_rows[:12]
                axis.bar(
                    [f"组{item['重复组']}" for item in shown],
                    [item["行数"] for item in shown],
                    color="#4f7cff",
                )
                axis.set_ylabel("组内行数")
                axis.set_title(f"重复组规模（共 {groups} 组，涉及 {count} 行）")
            else:
                axis.bar(["未发现重复"], [0], color="#4f7cff")
                axis.set_title("未发现完全重复的行")
            axis.grid(alpha=0.3, axis="y")
            figure_name = context.save(fig, "prep.duplicates_重复组规模")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过重复组规模图。")
    return registry.result(
        "prep.duplicates",
        table,
        metrics={
            "rows_before": int(frame.shape[0]),
            "duplicate_rows": count,
            "unique_rows": int(frame.shape[0]) - removable,
            "action": action,
            "columns_used": len(subset_names),
            "rows_after": table.n_rows,
            "keep": keep,
            "normalize": normalize,
            "duplicate_groups": groups,
            "include_roles": bool(include_roles),
        },
        tables=tables,
        notes=notes,
    )


@register("prep.encoding")
def encoding(context):
    table = context.table
    method = context.text("method", "onehot", ("onehot", "ordinal", "target"))
    drop_first = context.flag("drop_first", True)
    max_levels = context.whole("max_levels", 50, 2, 200)
    rare_threshold = context.number("rare_threshold", 0.0, 0.0, 0.5)
    target_stat = context.text("target_stat", "mean", ("mean", "median"))
    smoothing = context.number("smoothing", 0.0, 0.0, 20.0)
    folds = context.whole("folds", 0, 0, 20)
    order_method = context.text(
        "ordinal_order", "appearance", ("appearance", "frequency", "alphabet")
    )
    plot = context.flag("plot", True)
    frame = table.frame
    original = table.raw
    available = [str(name) for name in original.columns]

    blocks, reserved = _encoding_pool(table)
    categorical = [block["column"] for block in blocks]
    encoded_names = set(categorical)
    selectable = [*categorical, *reserved]

    chosen = _column_list(context.want("columns"))
    if chosen:
        absent = [name for name in chosen if name not in available]
        if absent:
            raise MethodError(
                f"列 {', '.join(absent)} 不在数据列里："
                f"{', '.join(str(name) for name in available[:20])}。"
            )
        targets = [name for name in selectable if name in set(chosen)]
        if not targets:
            raise MethodError(
                "选中的列里没有可编码的类别列："
                f"{'、'.join(str(name) for name in chosen[:8])} 是数值或布尔列，不需要编码。"
                f"可编码的列：{'、'.join(str(name) for name in selectable[:12]) or '无'}"
            )
    else:
        targets = [
            *categorical,
            *[name for name in reserved if _default_category(table, name, original[name])],
        ]
    if not targets:
        if selectable:
            context.warn(
                "没有自动选中类别列："
                f"{'、'.join(str(name) for name in selectable[:8])} 的取值过多或属于时间、"
                "分组列，需要在「参与编码的列」里显式指定后才会编码。"
            )
        else:
            context.warn("这份数据里没有文本或类别列，所有列都是数值或布尔列，本步无需编码。")

    def levels_of(name):
        series = original[name].astype("string")
        if series.isna().any():
            mode = series.mode()
            series = series.fillna(mode.iloc[0] if len(mode) else "缺失")
        return series, [str(level) for level in pd.unique(series.dropna())]

    def owned(name, block_method):
        if block_method == "onehot":
            prefix = f"{name}="
            return [column for column in frame.columns if str(column).startswith(prefix)]
        return [name] if name in frame.columns else []

    target_values = None
    if method == "target":
        if not table.target_name:
            raise MethodError("目标编码需要目标列。")
        target_values = table.numeric_target()
        if target_values is None:
            raise MethodError("目标编码需要可用的目标列。")

    jobs = list(blocks)
    for name in targets:
        if str(name) not in encoded_names:
            jobs.append({"column": str(name), "method": "reserved", "levels": None})

    working = frame.copy()
    summary = []
    level_values = {}
    frequencies = 0
    for block in jobs:
        name = block["column"]
        reserved_block = block["method"] == "reserved"
        text, levels = levels_of(name)
        if rare_threshold > 0.0 and len(levels) > 1:
            share = text.value_counts(normalize=True)
            rare = [level for level in levels if float(share.get(level, 0.0)) < rare_threshold]
            if rare:
                text = text.where(~text.isin(rare), "其他")
                levels = [level for level in levels if level not in set(rare)] + ["其他"]
        level_values[name] = (text, levels)
        if name not in targets:
            if reserved_block:
                continue
            working = working.drop(columns=owned(name, block["method"]))
            counts = text.value_counts()
            working[name] = text.map(counts).astype(float).to_numpy()
            summary.append({"column": name, "levels": len(levels), "method": "frequency"})
            frequencies += 1
            continue
        if method == "onehot" and block["method"] == "onehot" and drop_first:
            summary.append({"column": name, "levels": len(levels), "method": "onehot"})
            continue
        working = working.drop(columns=owned(name, block["method"]))
        if method == "onehot":
            if len(levels) > max_levels:
                codes, _ = pd.factorize(text)
                working[name] = codes.astype(float)
                summary.append({"column": name, "levels": len(levels), "method": "ordinal"})
            elif len(levels) <= 1:
                working[name] = np.zeros(len(text))
                summary.append({"column": name, "levels": len(levels), "method": "constant"})
            else:
                start = 1 if drop_first else 0
                for level in levels[start:]:
                    label = f"{name}={level}"[:60]
                    working[label] = (text == level).astype(float).to_numpy()
                summary.append({"column": name, "levels": len(levels), "method": "onehot"})
        elif method == "ordinal":
            if order_method == "frequency":
                order = [str(level) for level in text.value_counts().index]
                codes = pd.Categorical(text, categories=order).codes
            elif order_method == "alphabet":
                codes = pd.Categorical(text, categories=sorted(levels)).codes
            else:
                codes, _ = pd.factorize(text)
            working[name] = np.asarray(codes, dtype=float)
            summary.append({"column": name, "levels": len(levels), "method": "ordinal"})
        else:
            codes = pd.Categorical(text, categories=levels).codes
            values = np.asarray(target_values, dtype=float)
            prior = float(np.nanmean(values))
            if folds and folds > 1:
                generator = np.random.default_rng(0)
                fold_ids = generator.permutation(len(values)) % int(folds)
                encoded = np.full(len(values), prior, dtype=float)
                for fold in range(int(folds)):
                    test = fold_ids == fold
                    if not bool(test.any()) or bool(test.all()):
                        continue
                    averages = _target_averages(values, codes, ~test, target_stat, smoothing, prior)
                    mapped = pd.Series(codes[test]).map(averages)
                    encoded[test] = mapped.fillna(prior).to_numpy(dtype=float)
                working[name] = encoded
            elif target_stat == "median":
                averages = _target_averages(
                    values, codes, np.ones(len(values), dtype=bool), "median", smoothing, prior
                )
                mapped = pd.Series(codes).map(averages)
                working[name] = mapped.fillna(prior).astype(float).to_numpy()
            elif smoothing > 0.0:
                grouped = pd.Series(values).groupby(codes).agg(["sum", "count"])
                averages = (grouped["sum"] + smoothing * prior) / (grouped["count"] + smoothing)
                working[name] = pd.Series(codes).map(averages).astype(float).to_numpy()
            else:
                averages = pd.Series(values).groupby(codes).mean()
                working[name] = pd.Series(codes).map(averages).astype(float).to_numpy()
            summary.append({"column": name, "levels": len(levels), "method": "target"})

    for row in summary:
        name = row["column"]
        if row["method"] == "onehot":
            columns = [column for column in working.columns if str(column).startswith(f"{name}=")]
        else:
            columns = [name] if name in working.columns else []
        if columns:
            row["encoded_mean"] = round(float(working[columns].to_numpy(dtype=float).mean()), 6)
        else:
            row["encoded_mean"] = None

    table.frame = working
    table.feature_names = [str(name) for name in working.columns]

    summary_frame = (
        pd.DataFrame(summary) if summary else _empty(["column", "levels", "method", "encoded_mean"])
    )
    mapping = []
    for row in summary:
        name = row["column"]
        text, levels = level_values.get(name, (None, []))
        if text is None:
            continue
        encoded = _encoded_values(working, name, row["method"], text, levels)
        for level in levels:
            mapping.append(
                {
                    "column": name,
                    "value": str(level),
                    "method": row["method"],
                    "encoded_as": encoded.get(level),
                }
            )
    mapping_frame = pd.DataFrame(mapping, columns=["column", "value", "method", "encoded_as"])
    notes = [
        "独热编码把 K 个水平展开为 K-1 个 0/1 列，避免完全共线。",
        "序号编码保留一列，适合有序类别。",
        "目标编码用类别均值替换，适合高基数类别但要防泄漏。",
    ]
    if mapping:
        notes.append(
            "原值到编码结果的对应关系见下表 encoding_map（基准列、序号、目标统计量或频数）。"
        )
    if method == "onehot" and not drop_first:
        notes.append("已保留全部哑变量，编码后的列之间会完全共线。")
    if rare_threshold > 0.0:
        notes.append(f"频数占比低于 {rare_threshold} 的类别已并入「其他」。")
    if method == "target" and smoothing > 0.0:
        notes.append(f"目标编码按平滑系数 {smoothing} 向全局均值收缩。")
    if method == "target" and target_stat == "median":
        notes.append("目标编码用类别中位数替换，比均值更抗离群值。")
    if method == "target" and folds and folds > 1:
        notes.append(f"目标编码按 {folds} 折交叉计算，每个样本只用其他折的类别统计量，降低泄漏。")
    if frequencies:
        notes.append(
            f"选中的 {len(targets)} 个类别列按 {method} 编码，"
            f"未选中的 {frequencies} 个原有类别列折叠为频数编码。"
        )
    extra_used = [name for name in targets if name not in encoded_names]
    if extra_used:
        notes.append(
            f"以下文本列原本不在数值特征里，本次按选择编码后加入特征："
            f"{'、'.join(str(name) for name in extra_used[:8])}。"
        )
        skipped = [name for name in reserved if name not in set(targets)]
        if skipped:
            notes.append(
                f"其余文本列 {'、'.join(str(name) for name in skipped[:8])} 没有被选中，"
                "仍不进入特征；需要时可在「参与编码的列」里显式选择。"
            )

    figures = []
    if plot and summary:
        try:
            import matplotlib.pyplot as plt

            shown = [row["column"] for row in summary if row["column"] in set(targets)][:2]
            if not shown:
                shown = [row["column"] for row in summary][:2]
            fig, axes = plt.subplots(len(shown), 2, figsize=(11.4, 3.5 * len(shown)), squeeze=False)
            for row_index, label in enumerate(shown):
                text, levels = levels_of(label)
                if rare_threshold > 0.0 and len(levels) > 1:
                    share = text.value_counts(normalize=True)
                    rare = [
                        level for level in levels if float(share.get(level, 0.0)) < rare_threshold
                    ]
                    if rare:
                        text = text.where(~text.isin(rare), "其他")
                counts = text.value_counts()
                axes[row_index, 0].bar(
                    [str(level) for level in counts.index],
                    counts.to_numpy(dtype=int),
                    color="#4f7cff",
                )
                axes[row_index, 0].set_title(f"{label} 编码前各类别样本数", fontsize=10)
                axes[row_index, 0].tick_params(axis="x", labelsize=8)
                columns = [
                    column for column in working.columns if str(column).startswith(f"{label}=")
                ]
                if not columns and label in working.columns:
                    columns = [label]
                if columns:
                    means = working[columns].groupby(text.to_numpy()).mean()
                    if len(columns) == 1:
                        axes[row_index, 1].bar(
                            [str(item) for item in means.index],
                            means.iloc[:, 0].to_numpy(dtype=float),
                            color="#f59e0b",
                        )
                        axes[row_index, 1].set_title(f"{label} 编码后取值（{method}）", fontsize=10)
                        axes[row_index, 1].tick_params(axis="x", labelsize=8)
                    else:
                        axes[row_index, 1].imshow(
                            means.to_numpy(dtype=float), aspect="auto", cmap="Blues"
                        )
                        axes[row_index, 1].set_yticks(range(means.shape[0]))
                        axes[row_index, 1].set_yticklabels(
                            [str(item) for item in means.index], fontsize=8
                        )
                        axes[row_index, 1].set_xticks(range(len(columns)))
                        axes[row_index, 1].set_xticklabels(
                            [str(column) for column in columns], rotation=45, ha="right", fontsize=7
                        )
                        axes[row_index, 1].set_title(
                            f"{label} 编码后哑变量均值（{method}）", fontsize=10
                        )
                else:
                    axes[row_index, 1].bar(["无编码列"], [0], color="#f59e0b")
                axes[row_index, 1].grid(alpha=0.3, axis="y")
            fig.tight_layout()
            figure_name = context.save(fig, "prep.encoding_编码前后对比")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过编码前后对比图。")
    return registry.result(
        "prep.encoding",
        table,
        metrics={
            "strategy": method,
            "categorical_columns": len(summary),
            "encoded_features": len(table.feature_names),
            "columns_used": len(targets),
            "frequency_columns": frequencies,
            "extra_text_columns": len(extra_used),
            "levels_encoded": len(mapping),
            "drop_first": bool(drop_first),
            "max_levels": max_levels,
            "rare_threshold": rare_threshold,
            "smoothing": smoothing,
            "ordinal_order": order_method,
        },
        tables={
            "encoded_columns": table_of(summary_frame),
            "encoding_map": table_of(mapping_frame, limit=200),
        },
        notes=notes,
    )


@register("prep.derive")
def derive(context):
    table = context.table
    kind = context.text("kind", "interaction", ("interaction", "ratio", "polynomial", "bin"))
    left = context.text("left")
    right = context.text("right")
    bins = context.whole("bins", 5, 2, 50)
    strategy = context.text("strategy", "width", ("width", "quantile", "kmeans"))
    denominator_shift = context.number("denominator_shift", 0.0, 0.0, 1000.0)
    standardize = context.flag("standardize", False)
    keep_source = context.flag("keep_source", True)
    plot = context.flag("plot", True)

    names = list(table.feature_names)
    chosen = _column_list(context.want("columns"))
    if chosen:
        absent = [name for name in chosen if name not in names]
        if absent:
            raise MethodError(f"列 {', '.join(absent)} 不在特征中。可选：{'、'.join(names[:10])}")
        pool = [name for name in names if name in set(chosen)]
    else:
        pool = list(names)
    if not pool:
        raise MethodError("至少需要选择一列参与构造。")

    def check(name, role):
        if name in pool:
            return
        if name in names:
            raise MethodError(f"{role} {name} 不在选中的列里：{'、'.join(pool[:10])}")
        raise MethodError(f"{role} {name} 不在特征中。可选：{'、'.join(names[:10])}")

    if left:
        check(left, "左列")
    if right:
        check(right, "右列")

    frame = table.frame.copy()
    created = []
    sources = []
    bin_rows = []
    if kind == "interaction":
        left = left or pool[0]
        right = right or (pool[1] if len(pool) > 1 else None)
        if not right:
            raise MethodError("生成交互项至少需要两个特征。")
        new = f"{left}*{right}"
        frame[new] = frame[left] * frame[right]
        created.append(new)
        sources = [left, right]
    elif kind == "ratio":
        left = left or pool[0]
        right = right or (pool[1] if len(pool) > 1 else None)
        if not right:
            raise MethodError("生成比值至少需要两个特征。")
        denominator = frame[right].replace(0, np.nan)
        if denominator_shift > 0.0:
            denominator = denominator + denominator_shift
        new = f"{left}/{right}"
        frame[new] = denominator.map(lambda value: value).rdiv(frame[left]).fillna(0.0)
        created.append(new)
        sources = [left, right]
    elif kind == "polynomial":
        from sklearn.preprocessing import PolynomialFeatures

        degree = context.whole("degree", 2, 2, 3)
        values = frame[pool].to_numpy(dtype=float)
        transformer = PolynomialFeatures(degree=degree, include_bias=False)
        expanded = transformer.fit_transform(values)
        labels = [str(label) for label in transformer.get_feature_names_out(pool)]
        if expanded.shape[1] > 120:
            raise MethodError(
                f"多项式展开后有 {expanded.shape[1]} 列，超过 120，请降低 degree 或减少列。"
            )
        kept = [name for name in names if name not in set(pool)]
        expanded_frame = pd.DataFrame(expanded, columns=labels, index=frame.index)
        frame = pd.concat([frame[kept], expanded_frame], axis=1) if kept else expanded_frame
        created = [label for label in labels if label not in names]
    else:
        if left or right:
            targets = [name for name in (left, right) if name]
        elif chosen:
            targets = list(pool)
        else:
            targets = [pool[0]]
        for name in targets:
            label = f"{name}_分箱"
            if strategy == "quantile":
                binned, edges = pd.qcut(
                    frame[name], q=bins, labels=False, duplicates="drop", retbins=True
                )
            elif strategy == "kmeans":
                values = np.asarray(frame[name], dtype=float)
                if not np.isfinite(values).all():
                    raise MethodError("聚类分箱要求列里没有缺失或无穷值。")
                from sklearn.cluster import KMeans

                distinct = np.unique(values)
                count = int(min(bins, distinct.size))
                if count < 2:
                    raise MethodError(f"列 {name} 的取值不足两种，无法聚类分箱。")
                model = KMeans(n_clusters=count, n_init=10, random_state=0).fit(
                    values.reshape(-1, 1)
                )
                centres = model.cluster_centers_.ravel()
                order = np.argsort(centres)
                mapping = {int(old): int(new) for new, old in enumerate(order)}
                ordered = centres[order]
                binned = pd.Series(
                    [mapping[int(code)] for code in model.labels_], index=frame.index
                )
                edges = np.concatenate(
                    (
                        [float(values.min())],
                        [
                            (ordered[position] + ordered[position + 1]) / 2.0
                            for position in range(len(ordered) - 1)
                        ],
                        [float(values.max())],
                    )
                )
            else:
                binned, edges = pd.cut(
                    frame[name], bins=bins, labels=False, duplicates="drop", retbins=True
                )
            codes = pd.Series(binned, index=frame.index).astype(float).fillna(-1.0)
            frame[label] = codes
            created.append(label)
            for rank in range(len(edges) - 1):
                bin_rows.append(
                    {
                        "feature": label,
                        "bin": rank + 1,
                        "lower": round(float(edges[rank]), 6),
                        "upper": round(float(edges[rank + 1]), 6),
                        "count": int((codes == rank).sum()),
                    }
                )
        sources = list(targets)

    if standardize and created:
        block = frame[created].to_numpy(dtype=float)
        centre = block.mean(axis=0)
        spread = block.std(axis=0, ddof=0)
        spread = np.where(spread <= 1e-12, 1.0, spread)
        frame[created] = (block - centre) / spread

    if not keep_source and sources:
        drop = [name for name in sources if name in frame.columns and name not in set(created)]
        if drop and len(frame.columns) - len(drop) >= 1:
            frame = frame.drop(columns=drop)

    table.frame = frame
    table.feature_names = [str(name) for name in frame.columns]
    stats = []
    for label in created:
        if label not in frame.columns:
            continue
        column = pd.Series(frame[label]).astype(float)
        stats.append(
            {
                "feature": label,
                "mean": round(float(column.mean()), 6),
                "std": round(float(column.std(ddof=0)), 6),
                "min": round(float(column.min()), 6),
                "max": round(float(column.max()), 6),
            }
        )
    notes = [
        f"生成方式：{kind}。",
        f"参与构造的列共 {len(pool)} 个，未选中的列不参与生成。",
        "比值列分母为 0 时按 0 处理，避免产生无穷值。",
    ]
    if standardize:
        notes.append("派生列已按 z 分数标准化。")
    if kind == "ratio" and denominator_shift > 0.0:
        notes.append(f"分母先整体平移 {denominator_shift} 再求比值，避免分母过小或为零。")
    if not keep_source and sources:
        notes.append("参与构造的原始列已从特征表里移除。")
    metrics = {
        "kind": kind,
        "created": len(created),
        "features_after": len(table.feature_names),
        "columns_used": len(pool),
        "standardized": bool(standardize),
    }
    tables = {
        "created_features": table_of(
            pd.DataFrame(stats) if stats else _empty(["feature", "mean", "std", "min", "max"])
        )
    }
    if kind == "bin":
        metrics["bins"] = bins
        metrics["strategy"] = strategy
        tables["bin_summary"] = table_of(
            pd.DataFrame(bin_rows)
            if bin_rows
            else _empty(["feature", "bin", "lower", "upper", "count"])
        )
        notes.append(f"{strategy} 分箱：每个选中列切成最多 {bins} 段，落在区间外的取值记为 -1。")
    elif kind == "polynomial":
        metrics["degree"] = degree

    figures = []
    if plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(8.4, 4.6))
            if kind == "bin" and bin_rows:
                labels_bin = [f"{row['feature']}#{row['bin']}" for row in bin_rows]
                axis.bar(labels_bin, [row["count"] for row in bin_rows], color="#4f7cff")
                axis.set_title(f"分箱样本分布（{strategy} 口径，每列最多 {bins} 段）")
                axis.set_ylabel("样本数")
                plt.setp(axis.get_xticklabels(), rotation=45, ha="right", fontsize=7)
            elif created:
                shown = [label for label in created if label in frame.columns][:8]
                axis.boxplot(
                    [pd.Series(frame[label]).astype(float).to_numpy() for label in shown],
                    tick_labels=[str(label) for label in shown],
                    patch_artist=True,
                    boxprops={"facecolor": "#cfe0ff", "edgecolor": "#3a5fa8"},
                    medianprops={"color": "#3a5fa8"},
                )
                axis.set_title(f"{kind} 派生列取值分布（共 {len(created)} 列）")
                plt.setp(axis.get_xticklabels(), rotation=30, ha="right", fontsize=8)
            else:
                axis.bar(["未生成派生列"], [0], color="#4f7cff")
                axis.set_title("本次没有生成派生列")
            axis.grid(alpha=0.3, axis="y")
            figure_name = context.save(fig, "prep.derive_派生分布")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过派生分布图。")
    return registry.result(
        "prep.derive",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


@register("prep.winsorize")
def winsorize(context):
    table = context.table
    method = context.text("method", "quantile", ("quantile", "iqr", "zscore", "mad"))
    factor = context.number("factor", 1.5, 0.1, 20.0)
    lower_pct = context.number("lower", 0.01, 0.0, 0.49)
    upper_pct = context.number("upper", 0.99, 0.51, 1.0)
    side = context.text("side", "both", ("both", "lower", "upper"))
    detail = context.flag("detail", True)
    plot = context.flag("plot", True)
    if method == "quantile" and lower_pct >= upper_pct:
        raise MethodError("下分位必须小于上分位。")
    names, matrix = subset(table, context.want("columns"))
    total = len(table.feature_names)
    note_columns(context, names, total)
    if method == "quantile":
        low = np.percentile(matrix, lower_pct * 100, axis=0)
        high = np.percentile(matrix, upper_pct * 100, axis=0)
    elif method == "iqr":
        first = np.percentile(matrix, 25, axis=0)
        third = np.percentile(matrix, 75, axis=0)
        spread = np.where(third - first <= 1e-12, 1.0, third - first)
        low = first - factor * spread
        high = third + factor * spread
    elif method == "zscore":
        centre = matrix.mean(axis=0)
        spread = matrix.std(axis=0, ddof=0)
        spread = np.where(np.abs(spread) <= 1e-12, 1.0, spread)
        low = centre - factor * spread
        high = centre + factor * spread
    else:
        centre = np.median(matrix, axis=0)
        spread = np.median(np.abs(matrix - centre), axis=0) * 1.4826
        spread = np.where(np.abs(spread) <= 1e-12, 1.0, spread)
        low = centre - factor * spread
        high = centre + factor * spread
    if side == "both":
        clipped = np.clip(matrix, low, high)
    elif side == "lower":
        clipped = np.maximum(matrix, low)
    else:
        clipped = np.minimum(matrix, high)
    changed = clipped != matrix
    counts = changed.sum(axis=0)

    registry.apply_matrix(table, names, clipped)
    rows = pd.DataFrame(
        {
            "feature": names,
            "lower": numbers(low),
            "upper": numbers(high),
            "clipped": counts.astype(int),
        }
    )
    tables = {"per_feature": table_of(rows)}
    if detail:
        detail_rows = []
        for index, name in enumerate(names):
            for position in np.flatnonzero(changed[:, index])[:200]:
                detail_rows.append(
                    {
                        "feature": name,
                        "row": int(position),
                        "before": round(float(matrix[position, index]), 6),
                        "after": round(float(clipped[position, index]), 6),
                        "side": "low" if matrix[position, index] < low[index] else "high",
                    }
                )
        tables["clipped_detail"] = table_of(
            pd.DataFrame(detail_rows)
            if detail_rows
            else _empty(["feature", "row", "before", "after", "side"])
        )
    notes = [
        f"按 {method} 口径缩尾，判定倍数 {factor}。",
        f"只在 {len(names)}/{total} 个特征上缩尾，其余列保持原样。",
        "缩尾保留样本但压缩极端值，比直接删除更稳健。",
    ]
    if method == "quantile":
        notes.append(f"分位口径：下分位 {lower_pct:.0%}、上分位 {upper_pct:.0%}。")
    if side == "lower":
        notes.append("只压缩低端极端值，高端取值保持原样。")
    elif side == "upper":
        notes.append("只压缩高端极端值，低端取值保持原样。")
    metrics = {
        "lower": lower_pct,
        "upper": upper_pct,
        "method": method,
        "factor": factor,
        "clipped_cells": int(changed.sum()),
        "clipped_rows": int(changed.any(axis=1).sum()),
        "features": len(names),
        "features_total": total,
    }
    if side != "both":
        metrics["side"] = side

    figures = []
    if plot:
        try:
            import matplotlib.pyplot as plt

            shown = min(len(names), 12)
            fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.6), sharey=True)
            for axis, block, title in (
                (axes[0], matrix, "缩尾前"),
                (axes[1], clipped, "缩尾后（红点为被压缩的取值）"),
            ):
                axis.boxplot(
                    [block[:, index] for index in range(shown)],
                    tick_labels=[str(name) for name in names[:shown]],
                    patch_artist=True,
                    boxprops={"facecolor": "#cfe0ff", "edgecolor": "#3a5fa8"},
                    medianprops={"color": "#3a5fa8"},
                )
                axis.set_title(title, fontsize=10)
                axis.grid(alpha=0.3, axis="y")
            axes[0].set_ylabel("取值")
            for index in range(shown):
                positions = np.flatnonzero(changed[:, index])
                if not positions.size:
                    continue
                offsets = ((np.arange(positions.size) % 5) - 2) * 0.06
                axes[1].scatter(
                    np.full(positions.size, index + 1) + offsets,
                    clipped[positions, index],
                    s=14,
                    color="#d64545",
                    zorder=3,
                )
            fig.suptitle(f"缩尾前后箱线图（{method} 口径，{side} 方向）", fontsize=11)
            figure_name = context.save(fig, "prep.winsorize_缩尾前后箱线")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过缩尾前后箱线图。")
    return registry.result(
        "prep.winsorize",
        table,
        metrics=metrics,
        tables=tables,
        notes=notes,
    )


@register("prep.transform")
def transform(context):
    table = context.table
    method = context.text("method", "yeojohnson", ("boxcox", "yeojohnson", "log", "sqrt"))
    auto = context.flag("auto", False)
    lmbda = context.number("lmbda", None, -5.0, 5.0)
    shift = context.number("shift", 0.0, 0.0, 100.0)
    standardize = context.flag("standardize", False)
    threshold = context.number("skew_threshold", 0.0, 0.0, 5.0)
    plot = context.flag("plot", True)
    names, matrix = subset(table, context.want("columns"))
    total = len(table.feature_names)
    skipped = 0
    if threshold > 0.0 and matrix.shape[1]:
        skews = np.abs(pd.DataFrame(matrix).skew().to_numpy(dtype=float))
        keep = skews > threshold
        skipped = int((~keep).sum())
        names = [name for name, flag in zip(names, keep) if flag]
        matrix = matrix[:, keep]
    note_columns(context, names, total)

    shifted = 0.0
    used_lambda = []
    chosen = []
    if auto:
        from scipy.stats import boxcox, yeojohnson

        out = np.zeros_like(matrix)
        for index in range(matrix.shape[1]):
            column = matrix[:, index]
            if float(np.ptp(column)) <= 1e-12:
                out[:, index] = column
                used_lambda.append(None)
                chosen.append("原值")
                continue
            candidates = [("yeojohnson",) + tuple(yeojohnson(column))]
            if bool((column >= 0).all()):
                candidates.append(("log", np.log1p(column), None))
                candidates.append(("sqrt", np.sqrt(column), None))
            if bool((column > 0).all()):
                candidates.append(("boxcox",) + tuple(boxcox(column)))
            pick = min(candidates, key=lambda item: abs(float(pd.Series(item[1]).skew())))
            out[:, index] = pick[1]
            used_lambda.append(None if pick[2] is None else float(pick[2]))
            chosen.append(pick[0])
    elif method == "boxcox":
        minimum = float(matrix.min()) if matrix.size else 0.0
        if minimum <= 0.0:
            shifted = float(-minimum + 1.0) + shift
            matrix = matrix + shifted
        from scipy.stats import boxcox

        out = np.zeros_like(matrix)
        for index in range(matrix.shape[1]):
            if lmbda is None:
                converted, best = boxcox(matrix[:, index])
                used_lambda.append(best)
            else:
                converted = boxcox(matrix[:, index], lmbda=lmbda)
                used_lambda.append(float(lmbda))
            out[:, index] = converted
    elif method == "yeojohnson":
        from scipy.stats import yeojohnson

        out = np.zeros_like(matrix)
        for index in range(matrix.shape[1]):
            if lmbda is None:
                converted, best = yeojohnson(matrix[:, index])
                used_lambda.append(best)
            else:
                converted = yeojohnson(matrix[:, index], lmbda=lmbda)
                used_lambda.append(float(lmbda))
            out[:, index] = converted
    elif method == "log":
        if (matrix < 0).any():
            raise MethodError("对数变换要求所有值非负。")
        out = np.log1p(matrix)
        used_lambda = [None] * matrix.shape[1]
    else:
        if (matrix < 0).any():
            raise MethodError("平方根变换要求所有值非负。")
        out = np.sqrt(matrix)
        used_lambda = [None] * matrix.shape[1]

    if standardize and matrix.shape[1]:
        centre = out.mean(axis=0)
        spread = out.std(axis=0, ddof=0)
        spread = np.where(np.abs(spread) <= 1e-12, 1.0, spread)
        out = (out - centre) / spread

    registry.apply_matrix(table, names, out)
    rows = []
    for position, name in enumerate(names):
        rows.append(
            {
                "feature": name,
                "lambda": used_lambda[position],
                "shift": round(shifted, 6),
                "skew_before": round(float(pd.Series(matrix[:, position]).skew()), 6)
                if matrix.shape[1]
                else 0.0,
                "skew_after": round(float(pd.Series(out[:, position]).skew()), 6)
                if out.shape[1]
                else 0.0,
                "std_after": round(float(out[:, position].std(ddof=0)), 6) if out.shape[1] else 0.0,
            }
        )
    notes = [
        f"变换方式：{'auto' if auto else method}。",
        f"只在 {len(names)}/{total} 个特征上变换，其余列保持原样。",
    ]
    if shifted:
        notes.append(f"Box-Cox 要求正值，已先整体平移 {round(shifted, 6)} 后再变换。")
    if lmbda is not None and not auto:
        notes.append(f"变换参数按手动指定的 {lmbda} 使用。")
    if auto:
        summary = "、".join(f"{name}→{kind}" for name, kind in list(zip(names, chosen))[:10])
        notes.append(f"按变换后偏度绝对值最小自动挑选：{summary}。")
    if standardize:
        notes.append("变换后已按 z 分数标准化。")
    if skipped:
        notes.append(f"偏度绝对值不超过 {threshold} 的 {skipped} 个列未做变换。")
    before = round(float(pd.DataFrame(matrix).skew().abs().mean()), 4) if matrix.shape[1] else 0.0
    after = round(float(pd.DataFrame(out).skew().abs().mean()), 4) if out.shape[1] else 0.0

    figures = []
    if plot and names and out.shape[1]:
        try:
            import matplotlib.pyplot as plt

            shown = min(len(names), 2)
            fig, axes = plt.subplots(shown, 2, figsize=(11.4, 3.5 * shown), squeeze=False)
            for row_index in range(shown):
                before_skew = float(pd.Series(matrix[:, row_index]).skew())
                after_skew = float(pd.Series(out[:, row_index]).skew())
                axes[row_index, 0].hist(matrix[:, row_index], bins=20, color="#4f7cff")
                axes[row_index, 0].set_title(
                    f"{names[row_index]} 变换前（偏度 {before_skew:.2f}）", fontsize=10
                )
                axes[row_index, 1].hist(out[:, row_index], bins=20, color="#f59e0b")
                axes[row_index, 1].set_title(
                    f"{names[row_index]} 变换后（偏度 {after_skew:.2f}）", fontsize=10
                )
                axes[row_index, 1].set_ylabel("样本数")
            fig.tight_layout()
            figure_name = context.save(fig, "prep.transform_变换前后分布")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过变换前后分布图。")
    return registry.result(
        "prep.transform",
        table,
        metrics={
            "method": "auto" if auto else method,
            "features": len(names),
            "features_total": total,
            "skipped_columns": skipped,
            "shifted": bool(shifted),
            "skew_threshold": threshold,
            "standardized": bool(standardize),
            "mean_skew_before": before,
            "mean_skew_after": after,
        },
        tables={
            "per_feature": table_of(
                pd.DataFrame(rows)
                if rows
                else _empty(
                    ["feature", "lambda", "shift", "skew_before", "skew_after", "std_after"]
                )
            )
        },
        notes=notes,
    )


@register("prep.balance")
def balance(context):
    table = context.table
    if not table.target_name or table.task != "classification":
        raise MethodError("样本均衡只适用于分类任务。")
    method = context.text(
        "method", "report", ("report", "weights", "oversample", "smote", "undersample")
    )
    ratio = context.number("ratio", 1.0, 0.1, 1.0)
    neighbours = context.whole("neighbours", 5, 1, 50)
    smote_kind = context.text("smote_kind", "smote", ("smote", "borderline", "adasyn"))
    seed = context.whole("balance_seed", 0, 0, 1000000)
    power = context.number("weight_power", 1.0, 0.1, 3.0)
    plot = context.flag("plot", True)
    names, matrix = subset(table, context.want("columns"))
    total = len(table.feature_names)
    note_columns(context, names, total)
    labels = table.labels()
    values, counts = np.unique(labels, return_counts=True)
    distribution = pd.DataFrame(
        {"class": values, "count": counts, "ratio": numbers(counts / counts.sum())}
    )

    metrics = {
        "method": method,
        "classes": len(values),
        "imbalance_ratio": round(float(counts.max() / max(counts.min(), 1)), 3),
        "rows": table.n_rows,
        "features_used": len(names),
        "features_total": total,
    }
    notes = [
        f"参与均衡的特征列共 {len(names)}/{total} 个。",
        "report 只统计分布；weights 建议样本权重；oversample/smote 生成少数类样本；undersample 削减多数类。",
    ]
    resampled = None
    resampled_target = None
    if method == "weights":
        weight = {
            label: (len(labels) / (len(values) * count)) ** power
            for label, count in zip(values, counts)
        }
        metrics["weight_of_minority"] = round(float(max(weight.values())), 4)
        metrics["weight_power"] = power
        if power != 1.0:
            notes.append(f"权重按 1/n 的 {power} 次幂设置，越大越偏向少数类。")
    elif method in ("oversample", "smote", "undersample") and len(values) > 1:
        target = labels
        try:
            if method == "oversample":
                from imblearn.over_sampling import RandomOverSampler

                sampler = RandomOverSampler(random_state=seed, sampling_strategy=ratio)
            elif method == "smote":
                from imblearn.over_sampling import SMOTE, BorderlineSMOTE

                smallest = int(counts.min())
                if smallest < 3:
                    raise MethodError("SMOTE 要求少数类至少 3 个样本。")
                effective = min(neighbours, smallest - 1)
                if smote_kind == "borderline":
                    sampler = BorderlineSMOTE(
                        random_state=seed, k_neighbors=effective, sampling_strategy=ratio
                    )
                else:
                    sampler = SMOTE(
                        random_state=seed, k_neighbors=effective, sampling_strategy=ratio
                    )
                metrics["neighbours"] = effective
                metrics["smote_kind"] = smote_kind
            else:
                from imblearn.under_sampling import RandomUnderSampler

                sampler = RandomUnderSampler(random_state=seed, sampling_strategy=ratio)
            resampled, resampled_target = sampler.fit_resample(matrix, target)
        except ImportError as error:
            raise MethodError(
                f"{method} 需要 imbalanced-learn（imblearn），当前环境未安装；"
                "report 与 weights 不需要它。"
            ) from error
        frame = pd.DataFrame(resampled, columns=names)
        table.frame = frame
        table.feature_names = list(names)
        table.raw = pd.DataFrame({table.target_name: resampled_target})
        table.notes.append(f"已执行 {method}，样本数 {table.n_rows} → {frame.shape[0]}。")
        metrics["rows_after"] = int(frame.shape[0])
        metrics["ratio"] = ratio
        metrics["balance_seed"] = seed
        notes.append(f"重采样口径：目标类间比例 {ratio}，随机种子 {seed}。")
        if method == "smote" and smote_kind != "smote":
            notes.append(f"SMOTE 采用 {smote_kind} 变体生成少数类样本。")
        if len(names) < total:
            notes.append("重采样只使用选中的特征列，未选中的特征不再保留。")

    profile = []
    profile_matrix = np.asarray(resampled, dtype=float) if resampled is not None else matrix
    profile_labels = np.asarray(resampled_target) if resampled is not None else labels
    for label in values:
        mask = profile_labels == label
        means = profile_matrix[mask].mean(axis=0) if mask.any() else np.full(len(names), nan)
        for position, name in enumerate(names):
            profile.append(
                {
                    "class": str(label),
                    "feature": name,
                    "mean": means[position],
                    "count": int(mask.sum()),
                }
            )
    profile_frame = (
        pd.DataFrame(profile) if profile else _empty(["class", "feature", "mean", "count"])
    )

    figures = []
    if plot:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(7.6, 4.4))
            positions = np.arange(len(values))
            axis.bar(positions - 0.2, counts, width=0.4, color="#4f7cff", label="处理前")
            if resampled is not None:
                after_values, after_counts = np.unique(
                    np.asarray(resampled_target), return_counts=True
                )
                lookup = {
                    str(label): int(count) for label, count in zip(after_values, after_counts)
                }
                axis.bar(
                    positions + 0.2,
                    [lookup.get(str(label), 0) for label in values],
                    width=0.4,
                    color="#f59e0b",
                    label="处理后",
                )
            axis.set_xticks(positions)
            axis.set_xticklabels([str(value) for value in values])
            axis.set_ylabel("样本数")
            axis.set_title(f"类别样本数对比（{method}）")
            axis.legend(fontsize=8)
            axis.grid(alpha=0.3, axis="y")
            figure_name = context.save(fig, "prep.balance_类别分布")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过类别分布对比图。")
    return registry.result(
        "prep.balance",
        table,
        metrics=metrics,
        tables={"distribution": table_of(distribution), "class_profile": table_of(profile_frame)},
        notes=notes,
    )


@register("prep.scale")
def scale(context):
    table = context.table
    method = context.text("method", "zscore", ("zscore", "minmax", "robust", "maxabs"))
    lower_bound = context.number("lower_bound", 0.0, -100.0, 100.0)
    upper_bound = context.number("upper_bound", 1.0, -100.0, 100.0)
    center = context.flag("center", True)
    resize = context.flag("scale", True)
    clamp = context.flag("clamp", False)
    plot = context.flag("plot", True)
    names, matrix = subset(table, context.want("columns"))
    total = len(table.feature_names)
    note_columns(context, names, total)

    if method == "zscore":
        centre = matrix.mean(axis=0)
        spread = matrix.std(axis=0, ddof=0)
    elif method == "minmax":
        centre = matrix.min(axis=0)
        spread = matrix.max(axis=0) - centre
    elif method == "robust":
        centre = np.median(matrix, axis=0)
        spread = np.percentile(matrix, 75, axis=0) - np.percentile(matrix, 25, axis=0)
    else:
        centre = np.zeros(matrix.shape[1], dtype=float)
        spread = np.abs(matrix).max(axis=0)
    spread = np.where(np.abs(spread) <= 1e-12, 1.0, spread)
    out = matrix.astype(float).copy()
    if method == "minmax":
        span = upper_bound - lower_bound
        if center:
            out = out - centre
        if resize:
            out = out / spread * span + lower_bound
    else:
        if center:
            out = out - centre
        if resize:
            out = out / spread
    if clamp and method == "minmax":
        raw = out.copy()
        out = np.clip(out, lower_bound, upper_bound)
        clamped = int(np.sum(out != raw))
    else:
        clamped = 0

    registry.apply_matrix(table, names, out)
    notes = [
        f"缩放方式：{method}。",
        f"只在 {len(names)}/{total} 个特征上缩放，其余列保持原样。",
        "标准化按列进行；在真实建模中应当只用训练集拟合参数，这里的展示用全量数据。",
    ]
    if method == "minmax":
        notes.append(f"Min-Max 目标区间为 [{lower_bound}, {upper_bound}]。")
    if not center:
        notes.append("已关闭中心化，输出保留原始水平。")
    if not resize:
        notes.append("已关闭缩放，输出只做平移。")
    if clamp and method == "minmax":
        notes.append(f"输出已截断到目标区间 [{lower_bound}, {upper_bound}]。")
    metrics = {
        "method": method,
        "features": len(names),
        "features_total": total,
        "center": bool(center),
        "scale": bool(resize),
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "max_abs_mean": round(float(np.abs(out.mean(axis=0)).max()), 6),
        "max_std": round(float(out.std(axis=0, ddof=0).max()), 6),
        "min_value": round(float(out.min()), 6),
        "max_value": round(float(out.max()), 6),
    }
    if clamp and method == "minmax":
        metrics["clamped_cells"] = clamped

    figures = []
    if plot:
        try:
            import matplotlib.pyplot as plt

            shown = min(len(names), 12)
            fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.6))
            for axis, block, title in (
                (axes[0], matrix, "缩放前（原始量纲）"),
                (axes[1], out, "缩放后"),
            ):
                axis.boxplot(
                    [block[:, index] for index in range(shown)],
                    tick_labels=[str(name) for name in names[:shown]],
                    patch_artist=True,
                    boxprops={"facecolor": "#cfe0ff", "edgecolor": "#3a5fa8"},
                    medianprops={"color": "#3a5fa8"},
                )
                axis.set_title(title, fontsize=10)
                axis.grid(alpha=0.3, axis="y")
            fig.suptitle(f"缩放前后分布对比（{method}）", fontsize=11)
            figure_name = context.save(fig, "prep.scale_缩放前后分布")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过缩放前后分布图。")
    return registry.result(
        "prep.scale",
        table,
        metrics=metrics,
        notes=notes,
    )


@register("prep.pca")
def pca(context):
    table = context.table
    components = context.whole("components", None, 1, 50)
    scale_method = context.text("scale", "zscore", ("zscore", "minmax", "robust", "none"))
    variance = context.number("variance", 0.0, 0.0, 0.995)
    whiten = context.flag("whiten", False)
    min_loading = context.number("min_loading", 0.0, 0.0, 1.0)
    loadings_top = context.whole("loadings_top", 50, 1, 1000)
    names, matrix = subset(table, context.want("columns"))
    total = len(table.feature_names)
    if len(names) < 2:
        raise MethodError("PCA 至少需要两个特征。")
    note_columns(context, names, total)
    standardized = registry.scaled(matrix, scale_method)

    from sklearn.decomposition import PCA

    limit = min(len(names), matrix.shape[0])
    probe = PCA(n_components=limit, random_state=0).fit(standardized)
    cumulative_all = np.cumsum(probe.explained_variance_ratio_)
    if variance > 0.0:
        top = int(np.searchsorted(cumulative_all, variance) + 1)
    else:
        top = min(components or len(names), len(names), matrix.shape[0])
    top = max(1, min(top, limit))
    model = PCA(n_components=top, whiten=whiten, random_state=0)
    scores = model.fit_transform(standardized)
    ratio = model.explained_variance_ratio_
    cumulative = np.cumsum(ratio)

    loadings = pd.DataFrame(
        model.components_.T, columns=[f"PC{i + 1}" for i in range(top)], index=names
    ).reset_index()
    loadings = loadings.rename(columns={"index": "feature"})
    variance_frame = pd.DataFrame(
        {
            "component": [f"PC{i + 1}" for i in range(top)],
            "explained": numbers(ratio, 6),
            "cumulative": numbers(cumulative, 6),
            "eigenvalue": numbers(model.explained_variance_, 6),
        }
    )
    loading_rows = []
    for index, name in enumerate(names):
        for position in range(top):
            weight = float(model.components_[index, position])
            if abs(weight) > min_loading:
                loading_rows.append(
                    {
                        "feature": name,
                        "component": f"PC{position + 1}",
                        "loading": round(weight, 6),
                        "abs_loading": round(abs(weight), 6),
                    }
                )
    loading_rows.sort(key=lambda row: row["abs_loading"], reverse=True)
    top_loadings = (
        pd.DataFrame(loading_rows)
        if loading_rows
        else _empty(["feature", "component", "loading", "abs_loading"])
    )

    figures = []
    try:
        import matplotlib.pyplot as plt

        fig, axis = plt.subplots(figsize=(7, 4))
        axis.bar(range(1, top + 1), ratio * 100, color="#4f7cff")
        axis.plot(range(1, top + 1), cumulative * 100, color="#f59e0b", marker="o")
        axis.set_xlabel("主成分")
        axis.set_ylabel("方差解释率 (%)")
        axis.set_title("碎石图与累计解释率")
        axis.grid(alpha=0.3)
        name = context.save(fig, "pca_scree")
        if name:
            figures.append(name)
    except ImportError:
        context.warn("未安装 matplotlib，跳过碎石图。")

    if top >= 2:
        try:
            import matplotlib.pyplot as plt

            fig, axis = plt.subplots(figsize=(6, 5))
            from engine.plot_layout import embedding_scatter

            embedding_scatter(axis, scores[:, 0], scores[:, 1], table)
            axis.set_xlabel(f"PC1 ({ratio[0]:.1%})")
            axis.set_ylabel(f"PC2 ({ratio[1]:.1%})")
            axis.set_title("主成分得分")
            axis.grid(alpha=0.3)
            name = context.save(fig, "prep_pca_scores")
            if name:
                figures.append(name)
        except ImportError:
            pass

    table.frame = pd.DataFrame(scores, columns=[f"PC{i + 1}" for i in range(top)])
    table.feature_names = [f"PC{i + 1}" for i in range(top)]
    notes = [
        f"参与降维的列共 {len(names)}/{total} 个：{'、'.join(str(name) for name in names[:10])}。",
        f"前置缩放方式：{scale_method}。",
        "主成分是原始特征的线性组合，可解释性弱于原始特征。",
        "载荷绝对值越大表示该特征对该主成分贡献越大。",
    ]
    if whiten:
        notes.append("已白化，各主成分得分方差被拉到同一尺度。")
    if variance > 0.0:
        notes.append(f"主成分个数按累计方差 {variance} 自动确定。")
    return registry.result(
        "prep.pca",
        table,
        metrics={
            "components": top,
            "features_in": len(names),
            "features_total": total,
            "scale": scale_method,
            "whiten": bool(whiten),
            "variance_threshold": variance,
            "min_loading": min_loading,
            "loading_rows": int(top_loadings.shape[0]),
            "score_std_first": round(float(scores[:, 0].std(ddof=1)), 6),
            "explained_first": round(float(ratio[0]), 4),
            "explained_total": round(float(cumulative[-1]), 4),
            "components_for_90pct": int(np.searchsorted(cumulative, 0.90) + 1),
        },
        tables={
            "variance": table_of(variance_frame),
            "loadings": table_of(loadings),
            "top_loadings": table_of(top_loadings, limit=loadings_top),
        },
        notes=notes,
    )


@register("prep.tsne")
def tsne(context):
    table = context.table
    perplexity = context.number("perplexity", 30.0, 2.0, 200.0)
    seed = context.whole("seed", 42, 0, 10**6)
    iterations = context.whole("iterations", 1000, 250, 5000)
    scale_method = context.text("scale", "zscore", ("zscore", "minmax", "robust", "none"))
    learning_rate = context.number("learning_rate", 0.0, 0.0, 1000.0)
    exaggeration = context.number("early_exaggeration", 12.0, 1.0, 50.0)
    init = context.text("init", "random", ("random", "pca"))
    metric = context.text("metric", "euclidean", ("euclidean", "manhattan", "cosine", "chebyshev"))
    neighbour_method = context.text("method", "barnes_hut", ("barnes_hut", "exact"))
    angle = context.number("angle", 0.5, 0.0, 1.0)
    names, matrix = subset(table, context.want("columns"))
    total = len(table.feature_names)
    if table.n_rows < 10:
        raise MethodError("t-SNE 至少需要 10 个样本。")
    if len(names) < 2:
        raise MethodError("t-SNE 至少需要两个特征。")
    note_columns(context, names, total)
    effective = min(perplexity, max((table.n_rows - 1) / 3.0, 2.0))
    standardized = registry.scaled(matrix, scale_method)

    from sklearn.manifold import TSNE

    settings = {
        "n_components": 2,
        "perplexity": effective,
        "init": init,
        "learning_rate": "auto" if learning_rate <= 0 else learning_rate,
        "early_exaggeration": exaggeration,
        "metric": metric,
        "random_state": seed,
        "max_iter": iterations,
        "method": neighbour_method,
    }
    if neighbour_method == "barnes_hut":
        settings["angle"] = angle
    embedding = TSNE(**settings).fit_transform(standardized)

    figures = []
    try:
        import matplotlib.pyplot as plt

        fig, axis = plt.subplots(figsize=(6.5, 5.5))
        from engine.plot_layout import embedding_scatter

        embedding_scatter(axis, embedding[:, 0], embedding[:, 1], table)
        axis.set_title(f"t-SNE 二维嵌入（perplexity={effective:.0f}，迭代 {iterations} 轮）")
        axis.grid(alpha=0.3)
        name = context.save(fig, "prep_tsne")
        if name:
            figures.append(name)
    except ImportError:
        context.warn("未安装 matplotlib，跳过 t-SNE 图。")

    frame = pd.DataFrame(embedding, columns=["tSNE1", "tSNE2"])
    table.frame = frame
    table.feature_names = ["tSNE1", "tSNE2"]
    notes = [
        f"参与降维的列共 {len(names)}/{total} 个：{'、'.join(str(name) for name in names[:10])}。",
        f"前置缩放方式：{scale_method}；随机种子 {seed}，迭代 {iterations} 轮。",
        "t-SNE 只保留局部邻域结构，簇间距离不代表真实相似度。",
        "perplexity 一般取 5–50，且要小于样本量的三分之一。",
    ]
    if init == "pca":
        notes.append("初始化改用主成分分析，嵌入更稳定。")
    if learning_rate > 0:
        notes.append(f"学习率按手动指定的 {learning_rate} 使用。")
    if neighbour_method == "exact":
        notes.append("近邻计算使用精确算法，不做 Barnes-Hut 近似，样本量大时明显更慢。")
    elif angle != 0.5:
        notes.append(f"Barnes-Hut 角度取 {angle}，越小越精确、越慢。")
    metrics = {
        "rows": table.n_rows,
        "perplexity": round(effective, 2),
        "seed": seed,
        "iterations": iterations,
        "scale": scale_method,
        "learning_rate": learning_rate,
        "early_exaggeration": exaggeration,
        "init": init,
        "metric": metric,
        "features_in": len(names),
        "features_total": total,
    }
    if neighbour_method != "barnes_hut" or angle != 0.5:
        metrics["method"] = neighbour_method
        metrics["angle"] = angle
    return registry.result(
        "prep.tsne",
        table,
        metrics=metrics,
        tables={"embedding": table_of(frame)},
        notes=notes,
    )


@register("prep.spectral")
def spectral(context):
    from engine.integrity import require_regular_time

    require_regular_time(context.table)
    table = context.table
    top = context.whole("top", 3, 1, 20)
    window = context.text("window", "none", ("none", "hann", "hamming", "blackman"))
    detrend = context.text("detrend", "mean", ("none", "mean", "linear"))
    rate = context.number("sampling_rate", 1.0, 0.0001, 1000000.0)
    pad = context.whole("pad", 0, 0, 4096)
    min_freq = context.number("min_freq", 0.0, 0.0, 1000000.0)
    max_freq = context.number("max_freq", 0.0, 0.0, 1000000.0)
    plot = context.flag("plot", True)
    names, matrix = subset(table, context.want("columns"))
    total = len(table.feature_names)
    note_columns(context, names, total)

    rows = []
    features = {}
    spectra = []
    for index, name in enumerate(names):
        series = np.asarray(matrix[:, index], dtype=float)
        if series.size < 8:
            raise MethodError("谱特征至少需要 8 个时间点。")
        if detrend == "mean":
            centred = series - series.mean()
        elif detrend == "linear":
            from scipy.signal import detrend as linear_detrend

            centred = linear_detrend(series, type="linear")
        else:
            centred = series
        if window != "none":
            from scipy.signal import get_window

            centred = centred * get_window(window, series.size)
        size = series.size if pad <= series.size else int(pad)
        spectrum = np.abs(np.fft.rfft(centred, n=size))
        power = spectrum**2
        total_power = power.sum()
        frequencies = np.fft.rfftfreq(size, d=1.0 / rate)
        candidate = np.arange(1, power.size)
        if min_freq > 0.0:
            candidate = candidate[frequencies[candidate] >= min_freq]
        if max_freq > 0.0:
            candidate = candidate[frequencies[candidate] <= max_freq]
        if candidate.size == 0:
            candidate = np.arange(1, power.size)
            if min_freq > 0.0 or max_freq > 0.0:
                context.warn(f"列 {name} 在设定的频率区间里没有频点，已回退到全频段挑主频。")
        if total_power <= 1e-12:
            for rank in range(1, top + 1):
                rows.append(
                    {
                        "feature": name,
                        "rank": rank,
                        "dominant_freq": 0.0,
                        "dominant_period": None,
                        "spectral_entropy": 0.0,
                        "energy_ratio": 0.0,
                        "centroid": 0.0,
                    }
                )
                features[f"{name}_主频{rank}"] = np.zeros(series.size)
            features[f"{name}_谱熵"] = np.zeros(series.size)
            features[f"{name}_主频能量占比"] = np.zeros(series.size)
            if len(spectra) < 3:
                spectra.append((name, frequencies, spectrum, []))
            continue
        share = power / total_power
        order = (
            candidate[np.argsort(power[candidate])[::-1]]
            if candidate.size
            else np.zeros(0, dtype=int)
        )
        picks = order[: min(top, order.size)]
        entropy = (
            float(-np.sum(share[share > 0] * np.log(share[share > 0])) / np.log(len(share)))
            if len(share) > 1
            else 0.0
        )
        centroid = float(np.sum(frequencies * share))
        for rank, position in enumerate(picks, start=1):
            frequency = float(frequencies[position])
            rows.append(
                {
                    "feature": name,
                    "rank": rank,
                    "dominant_freq": round(frequency, 6),
                    "dominant_period": round(1.0 / frequency, 4) if frequency > 0 else None,
                    "spectral_entropy": round(entropy, 6),
                    "energy_ratio": round(float(share[position]), 6),
                    "centroid": round(centroid, 6),
                }
            )
            features[f"{name}_主频{rank}"] = np.full(series.size, frequency)
        features[f"{name}_谱熵"] = np.full(series.size, entropy)
        features[f"{name}_主频能量占比"] = np.full(series.size, float(share[picks[0]]))
        if len(spectra) < 3:
            spectra.append((name, frequencies, spectrum, [int(item) for item in picks]))

    summary = (
        pd.DataFrame(rows)
        if rows
        else _empty(
            [
                "feature",
                "rank",
                "dominant_freq",
                "dominant_period",
                "spectral_entropy",
                "energy_ratio",
                "centroid",
            ]
        )
    )
    new = pd.DataFrame(features)
    kept = [name for name in table.feature_names if name not in set(names)]
    if kept:
        frame = pd.concat(
            [table.frame[kept].reset_index(drop=True), new.reset_index(drop=True)], axis=1
        )
    else:
        frame = new
    table.frame = frame
    table.feature_names = [str(name) for name in frame.columns]
    notes = [
        f"每个选中列保留能量最高的 {top} 个主频，再附上谱熵与主频能量占比。",
        f"参与取谱的列共 {len(names)}/{total} 个，未选中的列保持原样。",
        "谱特征把整段序列压缩成主频、谱熵与能量占比，适合把时序当作分类输入。",
        "主频越高表示短期波动越剧烈；谱熵越大表示能量越分散、越接近噪声。",
    ]
    if window != "none":
        notes.append(f"取谱前先加 {window} 窗，抑制截断引起的频谱泄漏。")
    if detrend != "mean":
        notes.append(f"去趋势方式为 {detrend}。")
    if rate != 1.0:
        notes.append(f"采样频率按 {rate} 换算，主频单位与采样频率一致。")
    if pad > 0:
        notes.append(f"频谱按 {max(pad, table.n_rows)} 点计算（补零提高频率分辨率）。")
    if min_freq > 0.0:
        notes.append(f"主频只在不低于 {min_freq} 的频率里挑选。")
    if max_freq > 0.0:
        notes.append(f"主频只在不高于 {max_freq} 的频率里挑选。")
    metrics = {
        "features_in": len(names),
        "features_total": total,
        "features_out": len(table.feature_names),
        "time_points": table.n_rows,
        "top": top,
        "window": window,
        "detrend": detrend,
        "sampling_rate": rate,
        "pad": pad,
    }
    if min_freq > 0.0:
        metrics["min_freq"] = min_freq
    if max_freq > 0.0:
        metrics["max_freq"] = max_freq

    figures = []
    if plot and spectra:
        try:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(
                len(spectra), 1, figsize=(8.8, 2.7 * len(spectra)), squeeze=False
            )
            for row_index, (label, freq_axis, amplitude, picks) in enumerate(spectra):
                axis = axes[row_index, 0]
                axis.plot(freq_axis, amplitude, color="#4f7cff", linewidth=1.0)
                for rank, position in enumerate(picks, start=1):
                    axis.scatter(
                        [freq_axis[position]],
                        [amplitude[position]],
                        s=26,
                        color="#d64545",
                        zorder=3,
                    )
                    axis.annotate(
                        f"主频{rank}",
                        (freq_axis[position], amplitude[position]),
                        textcoords="offset points",
                        xytext=(4, 4),
                        fontsize=7,
                    )
                axis.set_title(f"{label} 幅值谱（前 {len(picks)} 个主频已标出）", fontsize=9)
                axis.set_ylabel("幅值")
                axis.grid(alpha=0.3)
            axes[-1, 0].set_xlabel("频率")
            fig.tight_layout()
            figure_name = context.save(fig, "prep.spectral_频谱主频")
            if figure_name:
                figures.append(figure_name)
        except ImportError:
            context.warn("未安装 matplotlib，跳过频谱主频图。")
    return registry.result(
        "prep.spectral",
        table,
        metrics=metrics,
        tables={"spectrum": table_of(summary)},
        notes=notes,
    )
