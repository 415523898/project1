from engine import catalog

ENTRY_LISTS = ("figures", "notes", "warnings")
ENTRY_KEYS = (
    "method",
    "metrics",
    "tables",
    "data",
    "figures",
    "notes",
    "warnings",
    "params",
    "parameters",
    "elapsed_ms",
)


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            return str(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def method_entry(name, entry):
    if not isinstance(entry, dict):
        raise ValueError(f"方法 {name} 的结果不是对象。")

    metrics = {}
    nested = entry.get("metrics")
    if isinstance(nested, dict):
        for key, value in nested.items():
            if key in ENTRY_LISTS or key in ENTRY_KEYS:
                continue
            metrics[key] = value

    tables = {}
    for key, value in (entry.get("tables") or {}).items():
        tables[key] = value
    for key, value in entry.items():
        if key in ENTRY_KEYS:
            continue
        if isinstance(value, dict):
            tables.setdefault(key, value)
            continue
        metrics[key] = value

    item = catalog.BY_ID.get(name, {})
    payload = {"method": name}
    payload["label"] = entry.get("label") or item.get("label") or name
    category = entry.get("category") or (catalog.category_of(name) if item else None)
    if category:
        payload["category"] = category
    group = entry.get("group") or item.get("group")
    if group:
        payload["group"] = group
    task = entry.get("task") or (item.get("tasks") or [None])[0]
    if task:
        payload["task"] = task
    payload["metrics"] = metrics
    payload["tables"] = tables
    for key in ENTRY_LISTS:
        value = entry.get(key)
        payload[key] = list(value) if isinstance(value, list) else []
    if isinstance(entry.get("data"), dict):
        payload["data"] = entry["data"]
    if isinstance(entry.get("split"), dict):
        payload["split"] = entry["split"]
    if isinstance(entry.get("params"), dict):
        payload["params"] = entry["params"]
    if isinstance(entry.get("parameters"), list):
        payload["parameters"] = entry["parameters"]
    if entry.get("elapsed_ms") is not None:
        payload["elapsed_ms"] = entry["elapsed_ms"]
    return payload


def methods(entries):
    if entries is None:
        return {}
    if isinstance(entries, dict):
        items = list(entries.items())
    elif isinstance(entries, list):
        items = [(entry.get("method"), entry) for entry in entries if isinstance(entry, dict)]
    else:
        raise ValueError("方法结果既不是对象也不是列表。")
    payload = {}
    for index, (name, entry) in enumerate(items):
        if not isinstance(name, str) or not name:
            raise ValueError(f"第 {index + 1} 条方法结果缺少方法标识。")
        payload[name] = clean(method_entry(name, entry))
    return payload


def figures_of(entries):
    collected = []
    for entry in methods(entries).values():
        collected.extend(entry["figures"])
    return collected
