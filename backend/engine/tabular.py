try:
    import numpy as np
    import pandas as pd
except ImportError as error:
    raise ImportError("统一输入层需要 numpy 与 pandas。") from error


class InputError(ValueError):
    pass


class Table:
    def __init__(
        self,
        raw,
        features,
        feature_names,
        target_name=None,
        time_name=None,
        group_name=None,
        task=None,
        notes=None,
        imputed=None,
        encoded=None,
    ):
        self.raw = raw
        self.frame = features
        self.feature_names = list(feature_names)
        self.target_name = target_name
        self.time_name = time_name
        self.group_name = group_name
        self.task = task
        self.notes = list(notes or [])
        self.rows_dropped = 0
        self.imputed = list(imputed or [])
        self.encoded = list(encoded or [])
        self.input_features = list(features.columns)

    @property
    def n_rows(self):
        return int(self.frame.shape[0])

    @property
    def n_features(self):
        return len(self.feature_names)

    def matrix(self):
        if not self.feature_names:
            return np.zeros((self.n_rows, 0), dtype=float)
        values = self.frame[self.feature_names].to_numpy(dtype=float)
        if getattr(self, "observed_view", False) and not getattr(self, "allow_missing", False):
            from engine.integrity import require_finite

            require_finite(values)
        return values

    def target(self):
        if not self.target_name or self.target_name not in self.raw.columns:
            return None
        return self.raw[self.target_name].to_numpy()

    def numeric_target(self):
        values = self.target()
        if values is None:
            return None
        series = pd.Series(values)
        if pd.api.types.is_numeric_dtype(series):
            return series.to_numpy(dtype=float)
        codes, levels = pd.factorize(series, sort=True)
        self.target_encoding = {str(value): int(index) for index, value in enumerate(levels)}
        return codes.astype(float)

    def labels(self):
        values = self.target()
        if values is None:
            return None
        series = pd.Series(values)
        if pd.api.types.is_numeric_dtype(series):
            unique = sorted(pd.unique(series.dropna()))
            if len(unique) <= 20 and all(float(value).is_integer() for value in unique):
                return np.array([str(int(value)) for value in series], dtype=object)
        return np.array([str(value) for value in series], dtype=object)

    def column(self, name):
        if name not in self.raw.columns:
            raise InputError(f"列 {name} 不存在。")
        return self.raw[name].to_numpy()

    def time(self):
        return self.column(self.time_name) if self.time_name else None

    def group(self):
        return self.column(self.group_name) if self.group_name else None

    def is_classification(self):
        return self.task == "classification"

    def summary(self):
        return {
            "rows": self.n_rows,
            "columns": int(self.raw.shape[1]),
            "column_names": [str(name) for name in self.raw.columns],
            "features": self.feature_names,
            "target": self.target_name,
            "time": self.time_name,
            "group": self.group_name,
            "task": self.task,
            "rows_dropped": self.rows_dropped,
            "imputed": self.imputed,
            "encoded": self.encoded,
            "notes": self.notes,
            "source": getattr(self, "source_summary", None),
            "preprocessing_scope": getattr(self, "preprocessing_scope", None),
            "target_encoding": getattr(self, "target_encoding", None),
        }


def infer_task(target):
    if target is None:
        return "clustering"
    series = pd.Series(target)
    if pd.api.types.is_numeric_dtype(series):
        unique = pd.unique(series.dropna())
        if 2 <= len(unique) <= 10 and all(float(value).is_integer() for value in unique):
            return "classification"
        return "regression"
    return "classification"


def build(
    source,
    target=None,
    time=None,
    group=None,
    task=None,
    dropna=False,
    max_rows=None,
    max_columns=None,
    exclude=(),
):
    frame = _to_frame(source)
    if frame.empty:
        raise InputError("数据为空。")
    if max_rows is not None and frame.shape[0] > max_rows:
        raise InputError(f"行数超过上限 {max_rows}。")
    if max_columns is not None and frame.shape[1] > max_columns:
        raise InputError(f"列数超过上限 {max_columns}。")

    notes = []
    frame = frame.copy()
    frame.columns = [str(name).strip() for name in frame.columns]

    for role, name in (("目标", target), ("时间", time), ("分组", group)):
        if name and name not in frame.columns:
            raise InputError(f"{role}列 {name} 不在数据中。可用列：{', '.join(frame.columns[:12])}")

    time_name = time
    if not time_name:
        time_name = _guess_time(frame, exclude=(target, group))
    group_name = group

    if time_name and pd.api.types.is_numeric_dtype(frame[time_name]):
        notes.append(f"时间列 {time_name} 已按数值排序。")
    elif time_name:
        try:
            frame[time_name] = pd.to_datetime(frame[time_name])
            notes.append(f"时间列 {time_name} 已解析为时间。")
        except (ValueError, TypeError):
            notes.append(f"时间列 {time_name} 无法解析为时间，按原值处理。")
            time_name = None

    if time_name:
        frame = frame.sort_values(time_name, kind="stable").reset_index(drop=True)

    excluded = {name for name in (target, time_name, group_name, *exclude) if name}
    feature_columns = [name for name in frame.columns if name not in excluded]
    target_name = target if target and target in frame.columns else None
    if not feature_columns:
        if not target_name:
            raise InputError("没有可用特征，也没有指定目标列。")
        # A univariate table is valid for descriptive/series methods. An
        # artificial row-number predictor would change the experiment.
        feature_columns = []
    frame = frame.reset_index(drop=True)

    if dropna and target_name:
        before = frame.shape[0]
        frame = frame[frame[target_name].notna()].reset_index(drop=True)
        dropped = before - frame.shape[0]
        if frame.empty:
            raise InputError("目标列全部为空，没有可用样本。")
    else:
        dropped = 0

    features, names, imputed, encoded = _prepare_features(frame, feature_columns)
    if len(features) == 0:
        raise InputError("清洗后没有可用样本。")

    table = Table(
        frame, features, names, target_name, time_name, group_name, task, notes, imputed, encoded
    )
    table.rows_dropped += dropped
    table.input_features = list(feature_columns)
    if not table.task:
        table.task = task or infer_task(frame[target_name] if target_name else None)
    return table


def _to_frame(source):
    if isinstance(source, pd.DataFrame):
        return source
    if isinstance(source, dict):
        try:
            return pd.DataFrame(source)
        except ValueError as error:
            raise InputError(f"列长度不一致：{error}") from error
    if isinstance(source, (list, tuple)):
        if not source:
            raise InputError("数据为空。")
        if all(isinstance(row, dict) for row in source):
            return pd.DataFrame(list(source))
        try:
            return pd.DataFrame(list(source))
        except ValueError as error:
            raise InputError(f"行长度不一致：{error}") from error
    raise InputError("数据必须是 DataFrame、列字典或行列表。")


def _guess_time(frame, exclude=()):
    for name in frame.columns:
        if name in exclude:
            continue
        lowered = str(name).lower()
        if lowered in ("date", "time", "datetime", "timestamp", "日期", "时间"):
            return name
    return None


def _prepare_features(frame, columns, fit_rows=None):
    imputed = []
    encoded = []
    pieces = []
    names = []

    for name in columns:
        series = frame[name]
        reference = series if fit_rows is None else series.iloc[fit_rows]
        if pd.api.types.is_bool_dtype(series):
            pieces.append(series.astype(float).rename(name))
            names.append(name)
            continue
        if pd.api.types.is_numeric_dtype(series):
            cleaned = pd.to_numeric(series, errors="coerce")
            if cleaned.isna().any():
                observed = pd.to_numeric(reference, errors="coerce")
                fill = observed.median() if observed.notna().any() else 0.0
                imputed.append(
                    {
                        "column": name,
                        "method": "median"
                        if observed.notna().any()
                        else "zero_no_training_observations",
                        "count": int(cleaned.isna().sum()),
                        "fill_value": float(fill),
                    }
                )
                cleaned = cleaned.fillna(fill)
            if cleaned.isna().any():
                imputed.append(
                    {"column": name, "method": "zero", "count": int(cleaned.isna().sum())}
                )
                cleaned = cleaned.fillna(0.0)
            pieces.append(cleaned.astype(float).rename(name))
            names.append(name)
            continue

        text = series.astype("string")
        if text.isna().any():
            imputed.append({"column": name, "method": "mode", "count": int(text.isna().sum())})
            mode = reference.astype("string").mode()
            text = text.fillna(mode.iloc[0] if len(mode) else "缺失")
        categories = list(pd.unique(reference.astype("string").dropna()))
        if not categories:
            categories = ["缺失"]
        if len(categories) > 50:
            codes = {value: index for index, value in enumerate(categories)}
            pieces.append(text.map(codes).fillna(-1).astype(float).rename(name))
            names.append(name)
            encoded.append({"column": name, "method": "ordinal", "levels": len(categories)})
        elif len(categories) <= 1:
            pieces.append(pd.Series(np.zeros(len(text)), index=frame.index, name=name))
            names.append(name)
            encoded.append({"column": name, "method": "constant", "levels": len(categories)})
        else:
            for level in categories[1:]:
                label = f"{name}={level}"[:60]
                pieces.append(
                    pd.Series((text == level).astype(float), index=frame.index, name=label)
                )
                names.append(label)
            encoded.append({"column": name, "method": "onehot", "levels": len(categories)})

    if not pieces:
        return pd.DataFrame(index=frame.index), [], imputed, encoded

    matrix = pd.concat(pieces, axis=1)

    reference_matrix = matrix if fit_rows is None else matrix.iloc[fit_rows]
    constant = [
        name for name in matrix.columns if float(reference_matrix[name].std(ddof=0)) <= 1e-12
    ]
    if constant:
        matrix = matrix.drop(columns=constant)
        names = [name for name in names if name not in set(constant)]
        for name in constant:
            encoded.append({"column": str(name), "method": "dropped-constant", "levels": 1})

    return matrix, names, imputed, encoded


def numeric_frame(table, columns=None):
    names = list(columns or table.feature_names)
    return table.frame[names].astype(float)
