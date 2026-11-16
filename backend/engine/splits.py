import hashlib

import numpy as np

GROUP = "数据划分"
MODES = ("stratified", "random", "time", "page", "none")
MODE_LABELS = {
    "stratified": "分层随机划分",
    "random": "随机划分",
    "time": "按时间顺序划分",
    "page": "沿用数据入口的划分",
    "none": "不划分，全量拟合",
}


class SplitError(ValueError):
    pass


class Outcome:
    def __init__(self, train, test, validation, kind, mode):
        self.train = np.asarray(train, dtype=int)
        self.test = None if test is None else np.asarray(test, dtype=int)
        self.validation = None if validation is None else np.asarray(validation, dtype=int)
        self.kind = kind
        self.mode = mode

    @property
    def has_test(self):
        return self.test is not None and self.test.size > 0

    def fingerprint(self):
        parts = [self.mode, ",".join(str(int(item)) for item in self.train), "|"]
        parts.append("" if self.test is None else ",".join(str(int(item)) for item in self.test))
        parts.append("|")
        parts.append(
            "" if self.validation is None else ",".join(str(int(item)) for item in self.validation)
        )
        return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()[:10]

    def summary(self):
        return {
            "kind": self.kind,
            "mode": self.mode,
            "fingerprint": self.fingerprint(),
            "train": int(self.train.size),
            "test": None if self.test is None else int(self.test.size),
            "validation": None if self.validation is None else int(self.validation.size),
        }


def default_mode(task):
    if task == "classification":
        return "stratified"
    if task == "regression":
        return "random"
    return "none"


def default_mode_for(method_id, task=None):
    from engine import catalog

    if task is None:
        item = catalog.BY_ID.get(str(method_id)) or {}
        task = (item.get("tasks") or [None])[0]
    if str(method_id).startswith("model."):
        return "none"
    return default_mode(task)


def options_for(task):
    if task == "classification":
        return ["stratified", "random", "time", "page", "none"]
    if task == "regression":
        return ["random", "time", "page", "none"]
    return ["none", "page", "random"]


DIAGNOSTIC = ("model.correlation", "model.canonical", "model.vif")


def needs_split(method_id, task=None):
    from engine import catalog

    method_id = str(method_id)
    if method_id in DIAGNOSTIC:
        return False
    if task is None:
        item = catalog.BY_ID.get(method_id) or {}
        task = (item.get("tasks") or [None])[0]
    if task == "clustering":
        return False
    return method_id.startswith(("ml.", "model."))


def specs_for(method_id, task=None, with_seed=True):
    from engine import catalog

    item = catalog.BY_ID.get(str(method_id)) or {}
    if task is None:
        task = (item.get("tasks") or [None])[0]
    mode = default_mode_for(method_id, task)
    options = options_for(task)
    if mode not in options:
        options = [mode] + options
    entries = [
        {
            "key": "split_mode",
            "label": "划分方式",
            "type": "enum",
            "default": mode,
            "options": options,
            "group": GROUP,
        },
        {
            "key": "test_size",
            "label": "测试集比例",
            "type": "number",
            "default": 0.3,
            "min": 0.05,
            "max": 0.6,
            "step": 0.05,
            "group": GROUP,
            "hidden_when": {"split_mode": ["page", "none"]},
        },
        {
            "key": "validation_size",
            "label": "验证集比例",
            "type": "number",
            "default": 0.0,
            "min": 0.0,
            "max": 0.3,
            "step": 0.05,
            "group": GROUP,
            "hidden_when": {"split_mode": ["page", "none"]},
        },
        {
            "key": "shuffle",
            "label": "打乱顺序",
            "type": "boolean",
            "default": True,
            "group": GROUP,
            "hidden_when": {"split_mode": ["stratified", "time", "page", "none"]},
        },
    ]
    if with_seed:
        entries.append(
            {
                "key": "seed",
                "label": "随机种子",
                "type": "integer",
                "default": 42,
                "min": 0,
                "max": 1000000,
                "step": 1,
                "group": GROUP,
                "hidden_when": {"split_mode": ["page", "none"]},
            }
        )
    return entries


def _fraction(value, fallback, label, low, high):
    if value is None:
        value = fallback
    if isinstance(value, bool):
        raise SplitError(f"{label}需要是数字。")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SplitError(f"{label}需要是数字。") from None
    if not np.isfinite(number):
        raise SplitError(f"{label}不是有限数字。")
    if number < low - 1e-12 or number > high + 1e-12:
        raise SplitError(f"{label}需要在 {low}–{high} 之间。")
    return number


def _seed(value):
    if value is None:
        return 42
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise SplitError("随机种子需要是整数。") from None
    return int(value)


def _page(page_split, n_rows):
    if not isinstance(page_split, dict):
        raise SplitError("没有有效的数据入口划分，请重新确认划分或显式选择其他划分方式。")
    train = page_split.get("train")
    test = page_split.get("test")
    if (
        not isinstance(train, (list, tuple))
        or not isinstance(test, (list, tuple))
        or not train
        or not test
    ):
        raise SplitError("数据入口的训练集和测试集不能为空。")
    validation = page_split.get("validation") or []
    supplied = list(train) + list(validation) + list(test)
    if any(isinstance(item, bool) or not isinstance(item, (int, np.integer)) for item in supplied):
        raise SplitError("数据入口划分索引必须是整数。")
    if len(supplied) != n_rows or len(set(supplied)) != len(supplied):
        raise SplitError("数据入口划分必须完整覆盖样本，且训练、验证和测试索引不得重复或重叠。")
    try:
        train_index = np.asarray([int(item) for item in train], dtype=int)
        test_index = np.asarray([int(item) for item in test], dtype=int)
    except (TypeError, ValueError):
        raise SplitError("数据入口划分索引无效。") from None
    if train_index.size == 0 or test_index.size == 0:
        raise SplitError("数据入口划分不能为空。")
    if train_index.min() < 0 or test_index.min() < 0:
        raise SplitError("数据入口划分索引越界。")
    if train_index.max() >= n_rows or test_index.max() >= n_rows:
        raise SplitError("数据入口划分索引越界。")
    if any(item < 0 or item >= n_rows for item in validation):
        raise SplitError("数据入口验证集索引越界。")
    return Outcome(
        train_index,
        test_index,
        validation or None,
        f"沿用数据入口划分：训练 {train_index.size} / 测试 {test_index.size}",
        "page",
    )


def _by_time(n_rows, test_size, validation_size):
    if n_rows < 12:
        raise SplitError("样本少于 12 条，无法划分训练集与测试集。")
    cut = int(round(n_rows * (1.0 - test_size)))
    cut = min(max(cut, 1), n_rows - 1)
    train = np.arange(cut)
    test = np.arange(cut, n_rows)
    validation = None
    kind = f"按时间顺序划分：训练前 {cut} 条 / 测试后 {n_rows - cut} 条"
    if validation_size > 0:
        share = validation_size / max(1.0 - test_size, 1e-9)
        inner = int(round(cut * (1.0 - share)))
        inner = min(max(inner, 1), cut - 1) if cut > 1 else cut
        train = np.arange(inner)
        validation = np.arange(inner, cut)
        kind = (
            f"按时间顺序划分：训练前 {inner} 条 / 验证 {cut - inner} 条 / 测试后 {n_rows - cut} 条"
        )
    return Outcome(train, test, validation, kind, "time")


def _by_random(n_rows, task, target, test_size, validation_size, seed, shuffle, mode):
    from sklearn.model_selection import train_test_split

    if n_rows < 12:
        raise SplitError("样本少于 12 条，无法划分训练集与测试集。")
    index = np.arange(n_rows)
    stratify = None
    note = ""
    if mode == "stratified" and target is not None:
        labels = np.asarray(target)
        if labels.size == n_rows:
            unique, counts = np.unique(labels, return_counts=True)
            if unique.size < 2:
                note = "目标只有一个取值，已按随机划分处理"
            elif counts.min() < 2:
                note = f"最小类别只有 {int(counts.min())} 个样本，已按随机划分处理"
            else:
                stratify = labels
    if stratify is None and mode == "stratified" and task == "classification" and target is None:
        note = "缺少目标列，已按随机划分处理"
    train, test = train_test_split(
        index, test_size=test_size, random_state=seed, shuffle=shuffle, stratify=stratify
    )
    label = "分层" if stratify is not None else "随机"
    validation = None
    kind = f"{label}划分：训练 {train.size} / 测试 {test.size}"
    if validation_size > 0:
        share = validation_size / max(1.0 - test_size, 1e-9)
        if share >= 0.9:
            raise SplitError("验证集比例相对测试集过大，请调小 validation_size。")
        inner = None
        if stratify is not None:
            block = np.asarray(target)[train]
            unique, counts = np.unique(block, return_counts=True)
            if counts.min() >= 2:
                inner = block
        train, validation = train_test_split(
            train, test_size=share, random_state=seed, shuffle=shuffle, stratify=inner
        )
        kind = f"{label}划分：训练 {train.size} / 验证 {validation.size} / 测试 {test.size}"
    if note:
        kind = f"{kind}（{note}）"
    return Outcome(train, test, validation, kind, mode)


def resolve(values, n_rows, task, target=None, time=None, page_split=None):
    values = dict(values or {})
    mode = values.get("split_mode") or default_mode(task)
    if mode not in MODES:
        raise SplitError(f"划分方式只能是：{'、'.join(MODES)}。")
    if mode == "none":
        return Outcome(np.arange(n_rows), None, None, "不划分：全部样本参与拟合", "none")
    if mode == "page":
        return _page(page_split, n_rows)
    test_size = _fraction(values.get("test_size"), 0.3, "测试集比例", 0.05, 0.6)
    validation_size = _fraction(values.get("validation_size"), 0.0, "验证集比例", 0.0, 0.3)
    if test_size + validation_size > 0.95:
        raise SplitError("测试集与验证集比例之和不能超过 0.95。")
    if mode == "time":
        return _by_time(n_rows, test_size, validation_size)
    seed = _seed(values.get("seed"))
    shuffle = values.get("shuffle")
    shuffle = True if shuffle is None else bool(shuffle)
    # Stratification requires shuffled sampling. A stale panel or API client
    # may still send false, so enforce the invariant at the shared entry point.
    if mode == "stratified":
        shuffle = True
    return _by_random(n_rows, task, target, test_size, validation_size, seed, shuffle, mode)
