import importlib
import math
import time
import traceback
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError as error:
    raise ImportError("方法仓库需要 numpy 与 pandas。") from error

from engine import catalog, params, tabular


class MethodError(ValueError):
    pass


class Context:
    def __init__(self, table, params, figures_dir=None, session_id=None, figures=True):
        self.table = table
        self.params = params or {}
        self.figures_dir = Path(figures_dir) if figures_dir else None
        self.session_id = session_id
        self.figures = []
        self.warnings = []
        self.figures_enabled = bool(figures)
        self._split = None
        self._split_error = None
        self._model_prepared = False
        self._evaluation = None

    def split_indices(self):
        if self._split is not None:
            return self._split
        from engine import splits

        target = None
        if self.table.task == "classification":
            target = self.table.numeric_target()
        try:
            self._split = splits.resolve(
                self.params,
                self.table.n_rows,
                self.table.task,
                target=target,
                time=self.table.time(),
                page_split=getattr(self.table, "page_split", None),
            )
        except splits.SplitError as error:
            raise MethodError(str(error)) from None
        self.table.notes.append(self._split.kind)
        from engine.integrity import fit_model_view

        fit_model_view(self, self._split.train)
        return self._split

    def split_used(self):
        return self._split

    def evaluation_indices(self):
        """Record the rows actually selected by a predictive evaluation path."""
        split = self.split_indices()
        rows = split.test if split.has_test else split.train
        self._evaluation = ("held_out_test" if split.has_test else "training_only", len(rows))
        return rows

    def want(self, name, default=None):
        value = self.params.get(name, default)
        if value is None:
            return default
        return value

    def number(self, name, default=None, low=None, high=None):
        value = self.params.get(name, default)
        if value is None:
            return default
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise MethodError(f"参数 {name} 需要是数字。")
        if not math.isfinite(number):
            raise MethodError(f"参数 {name} 不是有限数字。")
        if low is not None and number < low:
            raise MethodError(f"参数 {name} 不能小于 {low}。")
        if high is not None and number > high:
            raise MethodError(f"参数 {name} 不能大于 {high}。")
        return number

    def whole(self, name, default=None, low=None, high=None):
        value = self.number(name, default, low, high)
        return None if value is None else int(round(value))

    def text(self, name, default=None, allowed=None):
        value = self.params.get(name, default)
        if value is None:
            return default
        value = str(value).strip()
        if allowed and value not in allowed:
            raise MethodError(f"参数 {name} 只能是：{'、'.join(allowed)}。")
        return value

    def flag(self, name, default=False):
        value = self.params.get(name, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on", "是")
        return bool(value)

    def column(self, name):
        return self.table.column(name)

    def save(self, figure, name):
        if self.figures_dir is None or figure is None or not self.figures_enabled:
            if figure is not None:
                try:
                    import matplotlib.pyplot as plt

                    plt.close(figure)
                except Exception:
                    pass
            return None
        stem = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(name))[:80]
        scope = f"{self.session_id}-" if self.session_id else ""
        target = self.figures_dir / f"{scope}{stem}.png"
        try:
            self.figures_dir.mkdir(parents=True, exist_ok=True)
            from engine.plot_layout import prepare

            prepare(figure)
            figure.savefig(target, bbox_inches="tight", dpi=150)
            self.figures.append(target.name)
            try:
                from engine.figure_data import snapshot

                snapshot(figure, target)
            except (OSError, TypeError, ValueError) as error:
                self.warnings.append(f"图 {stem} 的结构化数据保存失败：{error}")
        except OSError as error:
            self.warnings.append(f"图 {stem} 保存失败：{error}")
            return None
        finally:
            try:
                import matplotlib.pyplot as plt

                plt.close(figure)
            except Exception:
                pass
        return target.name

    def warn(self, message):
        self.warnings.append(str(message))


def configure_fonts():
    from engine.plot_fonts import configure

    return configure()


def result(method_id, table=None, **fields):
    item = catalog.BY_ID.get(method_id, {})
    actual_task = (fields.get("metrics") or {}).get("task")
    task = actual_task if actual_task in item.get("tasks", []) else item.get("tasks", [None])[0]
    payload = {
        "method": method_id,
        "label": item.get("label") or method_id,
        "category": catalog.category_of(method_id),
        "group": item.get("group"),
        "task": task,
        "metrics": {},
        "tables": {},
        "figures": [],
        "notes": [],
        "warnings": [],
    }
    if table is not None:
        payload["data"] = table.summary()
    payload.update(fields)
    return payload


REGISTRY = {}


def known(method_id):
    return method_id in catalog.BY_ID


def method_task(method_id):
    item = catalog.BY_ID.get(method_id)
    return (item.get("tasks") or [None])[0] if item else None


def from_bundle(bundle, data_store=None, version=None):
    if not isinstance(bundle, dict):
        raise MethodError("数据格式无效。")
    if isinstance(bundle.get("table"), tabular.Table):
        return bundle["table"]
    matrix = bundle.get("X")
    if matrix is None:
        raise MethodError("数据缺少特征矩阵。")
    names = [str(name) for name in (bundle.get("feature_names") or [])]
    if not names:
        width = len(matrix[0]) if matrix else 0
        names = [f"x{index + 1}" for index in range(width)]
    target_name = str(bundle.get("target_name") or "target")
    frame = pd.DataFrame(np.asarray(matrix, dtype=float), columns=names)
    values = bundle.get("y")
    if values is not None and len(values) == len(frame):
        frame[target_name] = list(values)
        target = target_name
    else:
        target = None
    if data_store is not None and version:
        try:
            original = data_store.retrieve(version)
        except Exception:
            original = None
        if isinstance(original, pd.DataFrame) and len(original) == len(frame):
            for name in original.columns:
                if name not in frame.columns:
                    frame[name] = original[name].to_numpy()
    time_name = None
    group_name = None
    for name in frame.columns:
        lowered = str(name).lower()
        if time_name is None and lowered in (
            "date",
            "time",
            "datetime",
            "timestamp",
            "日期",
            "时间",
            "period",
        ):
            time_name = name
        if group_name is None and lowered in (
            "entity",
            "group",
            "id",
            "个体",
            "分组",
            "subject",
            "firm",
            "code",
        ):
            group_name = name
    task = bundle.get("task")
    if task not in ("classification", "regression", "clustering"):
        task = None
    table = tabular.build(frame, target=target, time=time_name, group=group_name, task=task)
    split = bundle.get("split")
    if isinstance(split, dict) and split.get("test"):
        table.notes.append(
            f"数据自带划分：训练 {len(split.get('train') or [])}、测试 {len(split['test'])}。"
        )
        table.page_split = split
    return table


def register(*method_ids):
    def wrap(function):
        for method_id in method_ids:
            REGISTRY[method_id] = function
        return function

    return wrap


def implemented(method_id):
    return method_id in REGISTRY


def missing(method_id):
    item = catalog.BY_ID.get(method_id)
    if item is None:
        return [f"未知方法 {method_id}"]
    return catalog.missing_for(item)


def run(method_id, table, values=None, figures_dir=None, session_id=None, figures=True):
    if method_id not in catalog.BY_ID:
        raise MethodError(f"未知方法：{method_id}。")
    absent = missing(method_id)
    if absent:
        item = catalog.BY_ID[method_id]
        raise MethodError(f"{item['label']}需要 {', '.join(absent)}，当前环境未安装。")
    function = REGISTRY.get(method_id)
    if function is None:
        item = catalog.BY_ID[method_id]
        raise MethodError(f"{item['label']}已登记但尚未实现。")
    try:
        cleaned = params.clean(method_id, values)
    except ValueError as error:
        raise MethodError(str(error)) from None
    if cleaned.get("figures") is not None:
        figures = bool(figures and cleaned["figures"])
    from engine import integrity

    table = integrity.method_table(table, method_id)
    context = Context(table, cleaned, figures_dir, session_id, figures)
    integrity.prepare(context, method_id)
    started = time.perf_counter()
    try:
        outcome = function(context)
    except MethodError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        ZeroDivisionError,
        ArithmeticError,
    ) as error:
        raise MethodError(f"{catalog.BY_ID[method_id]['label']}执行失败：{error}") from None
    except Exception as error:
        detail = traceback.format_exc(limit=3).strip().splitlines()[-1]
        raise MethodError(
            f"{catalog.BY_ID[method_id]['label']}执行出错：{error}｜{detail}"
        ) from None
    payload = outcome if isinstance(outcome, dict) else {}
    payload.setdefault("method", method_id)
    item = catalog.BY_ID[method_id]
    payload.setdefault("label", item["label"])
    payload.setdefault("category", catalog.category_of(method_id))
    payload.setdefault("group", item.get("group"))
    payload.setdefault("metrics", {})
    payload.setdefault("tables", {})
    payload.setdefault("notes", [])
    payload["figures"] = [{"name": name, "url": None} for name in context.figures]
    payload["warnings"] = list(context.warnings) + list(payload.get("warnings") or [])
    payload["data"] = table.summary()
    payload["method"] = method_id
    payload["params"] = {key: value for key, value in cleaned.items() if key != "figures"}
    payload["parameters"] = params.specs(method_id)
    used = context.split_used()
    if used is not None:
        payload["split"] = used.summary()
        evaluation = context._evaluation
        payload["metrics"]["evaluation_scope"] = evaluation[0] if evaluation else "training_only"
        if evaluation:
            payload["metrics"]["evaluation_rows"] = evaluation[1]
        payload["metrics"]["fit_scope"] = "training_only"
        if used.has_test and evaluation is None:
            payload["warnings"].append(
                "已保留测试集，但本方法只报告训练集拟合/推断统计，未在测试集上评价预测。"
            )
        elif not used.has_test:
            payload["warnings"].append(
                "未划分独立测试集；本次拟合指标来自训练数据，不能作为泛化效果。"
            )
        payload.setdefault("metrics", {})["split_mode"] = used.mode
        payload["metrics"]["split_fingerprint"] = used.fingerprint()
        payload["metrics"]["split_train"] = int(used.train.size)
        if used.test is not None:
            payload["metrics"]["split_test"] = int(used.test.size)
        if used.validation is not None:
            payload["metrics"]["split_validation"] = int(used.validation.size)
    payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
    return payload


def load_implementations(layer):
    configure_fonts()
    name = f"engine.methods.{layer}"
    try:
        importlib.import_module(name)
    except ImportError as error:
        raise ImportError(f"无法加载实现层 {layer}：{error}") from error


def numbers(values, digits=4):
    if values is None:
        return []
    return [
        None if value is None or not np.isfinite(float(value)) else round(float(value), digits)
        for value in np.asarray(values, dtype=float).ravel()
    ]


def table_of(frame, limit=50):
    if not isinstance(frame, pd.DataFrame):
        return {}
    head = frame.head(limit)
    return {
        "columns": [str(name) for name in head.columns],
        "rows": [[_cell(value) for value in row] for row in head.itertuples(index=False)],
        "total_rows": int(frame.shape[0]),
        "truncated": bool(frame.shape[0] > limit),
    }


def _cell(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if not math.isfinite(number) else round(number, 6)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, int):
        return value
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    return str(value)[:200]


def standardize(matrix):
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2:
        raise MethodError("需要二维特征矩阵。")
    mean = matrix.mean(axis=0)
    spread = matrix.std(axis=0, ddof=0)
    spread = np.where(spread <= 1e-12, 1.0, spread)
    return (matrix - mean) / spread, mean, spread


def subset(table, columns):
    if not columns:
        return list(table.feature_names), table.matrix()
    names = [str(name).strip() for name in columns if str(name).strip()]
    absent = [name for name in names if name not in table.feature_names]
    if absent:
        raise MethodError(
            f"列 {', '.join(absent)} 不在可用特征里："
            f"{', '.join(str(name) for name in table.feature_names[:20])}。"
        )
    if not names:
        raise MethodError("至少需要选择一列。")
    frame = table.frame[names]
    values = frame.to_numpy(dtype=float)
    if getattr(table, "observed_view", False) and not getattr(table, "allow_missing", False):
        from engine.integrity import require_finite

        require_finite(values)
    return names, values


def apply_matrix(table, names, matrix):
    frame = table.frame.copy()
    for position, name in enumerate(names):
        frame[name] = np.asarray(matrix, dtype=float)[:, position]
    table.frame = frame
    return table


def scaled(matrix, method):
    matrix = np.asarray(matrix, dtype=float)
    if method in (None, "none"):
        return matrix
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
        raise MethodError(f"不支持的缩放方式 {method}。")
    spread = np.where(np.abs(spread) <= 1e-12, 1.0, spread)
    return (matrix - centre) / spread
