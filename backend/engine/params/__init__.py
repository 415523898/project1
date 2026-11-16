import math

from engine import splits
from engine.params import (
    causal,
    domain,
    evaluate,
    machine,
    modeling,
    prepare,
    series,
    stats,
)

TYPES = ("boolean", "integer", "number", "enum", "text", "columns")

LAYERS = (prepare, stats, evaluate, modeling, machine, domain, series, causal)

SPECS = {}
for _layer in LAYERS:
    for _method_id, _items in _layer.PARAMETERS.items():
        if _method_id in SPECS:
            raise ValueError(f"参数表重复登记：{_method_id}")
        SPECS[_method_id] = [dict(item) for item in _items]

FIGURES = {"key": "figures", "label": "输出图形", "type": "boolean", "default": True}
COLUMNS = {"key": "columns", "label": "参与建模的列", "type": "columns", "default": None}
SEED = {
    "key": "seed",
    "label": "随机种子",
    "type": "integer",
    "default": 42,
    "min": 0,
    "max": 1000000,
    "step": 1,
}


def _place(items, spec):
    position = spec.get("position")
    spec = {key: value for key, value in spec.items() if key != "position"}
    if position is None:
        items.append(spec)
        return
    items.insert(max(0, min(position, len(items))), spec)


def _with_common(method_id, items):
    merged = [dict(item) for item in items]
    seen = {item["key"] for item in merged}
    if splits.needs_split(method_id):
        head = [
            dict(spec)
            for spec in splits.specs_for(method_id, with_seed="seed" not in seen)
            if spec["key"] not in seen
        ]
        merged[0:0] = head
        seen.update(spec["key"] for spec in head)
    if "figures" not in seen:
        merged.append(dict(FIGURES))
    return merged


def specs(method_id):
    items = SPECS.get(str(method_id))
    if items is None:
        return []
    return _with_common(str(method_id), items)


def keys(method_id):
    return [item["key"] for item in specs(method_id)]


def for_method(method_id, values):
    if not isinstance(values, dict):
        raise ValueError("params 必须是 JSON 对象。")
    scoped = values.get(method_id, {})
    if not isinstance(scoped, dict):
        raise ValueError(f"params.{method_id} 必须是参数对象。")
    allowed = set(keys(method_id))
    unknown = set(scoped) - allowed
    if unknown:
        raise ValueError(f"{method_id} 不支持参数：{'、'.join(sorted(unknown))}。")
    shared = {key: value for key, value in values.items() if key in allowed}
    return {**shared, **scoped}


def defaults(method_id):
    values = {}
    for item in specs(method_id):
        values[item["key"]] = item.get("default")
    return values


def groups(method_id):
    order = []
    buckets = {}
    for item in specs(method_id):
        name = item.get("group") or "参数"
        if name not in buckets:
            buckets[name] = []
            order.append(name)
        buckets[name].append({key: value for key, value in item.items() if key != "group"})
    return [{"name": name, "params": buckets[name]} for name in order]


def table():
    return {method_id: specs(method_id) for method_id in specs_all()}


def specs_all():
    return sorted(SPECS)


def _boolean(spec, value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "yes", "on", "是"):
            return True
        if text in ("0", "false", "no", "off", "否"):
            return False
    raise ValueError(f"{spec['label']}需要是布尔值。")


def _number(spec, value):
    if isinstance(value, bool):
        raise ValueError(f"{spec['label']}需要是数字。")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{spec['label']}需要是数字。") from None
    if not math.isfinite(number):
        raise ValueError(f"{spec['label']}不是有限数字。")
    if "min" in spec and number < spec["min"] - 1e-12:
        raise ValueError(f"{spec['label']}不能小于 {spec['min']}。")
    if "max" in spec and number > spec["max"] + 1e-12:
        raise ValueError(f"{spec['label']}不能大于 {spec['max']}。")
    return number


def _integer(spec, value):
    number = _number(spec, value)
    if abs(number - round(number)) > 1e-9:
        raise ValueError(f"{spec['label']}需要是整数。")
    return int(round(number))


def _enum(spec, value):
    options = spec.get("options") or []
    for option in options:
        if value == option:
            return option
        if isinstance(option, str) and isinstance(value, str) and option == value.strip():
            return option
    rendered = "、".join(str(option) for option in options)
    raise ValueError(f"{spec['label']}只能是：{rendered}。")


def _text(spec, value):
    return str(value).strip()


def _columns(spec, value):
    if value is None:
        return None
    if isinstance(value, str):
        items = [part.strip() for part in value.replace("，", ",").split(",")]
        return [part for part in items if part]
    if isinstance(value, (list, tuple)):
        return [str(part).strip() for part in value if str(part).strip()]
    raise ValueError(f"{spec['label']}需要是列名列表。")


CONVERT = {
    "boolean": _boolean,
    "integer": _integer,
    "number": _number,
    "enum": _enum,
    "text": _text,
    "columns": _columns,
}


def clean(method_id, params=None):
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("参数格式无效。")
    items = specs(method_id)
    if not items:
        return dict(params)
    known = {}
    for item in items:
        known[item["key"]] = item
    unknown = [key for key in params if key not in known]
    if unknown:
        raise ValueError(f"{method_id} 不支持参数：{'、'.join(sorted(unknown))}。")
    values = {}
    for item in items:
        key = item["key"]
        if key in params and params[key] is not None:
            value = params[key]
        else:
            value = item.get("default")
        if value is None:
            values[key] = None
            continue
        try:
            values[key] = CONVERT[item["type"]](item, value)
        except KeyError:
            raise ValueError(f"参数 {key} 的类型 {item.get('type')} 不受支持。") from None
    if values.get("split_mode") == "stratified" and "shuffle" in values:
        values["shuffle"] = True
    return values


def hidden_by(item, values):
    need = item.get("hidden_when")
    if not isinstance(need, dict):
        return False
    for key, expected in need.items():
        options = expected if isinstance(expected, (list, tuple, set)) else (expected,)
        if values.get(key) in options:
            return True
    return False


def active(method_id, values):
    items = specs(method_id)
    result = dict(values or {})
    for item in items:
        if hidden_by(item, result):
            result.pop(item["key"], None)
    return result


def validate_table():
    problems = []
    for method_id in specs_all():
        if method_id not in _CATALOG_IDS():
            problems.append(f"参数表登记了方法库以外的方法：{method_id}")
        seen = set()
        for item in specs(method_id):
            key = item.get("key")
            if not key:
                problems.append(f"{method_id} 有参数缺少 key")
                continue
            if key in seen:
                problems.append(f"{method_id} 的参数 {key} 重复")
            seen.add(key)
            kind = item.get("type")
            if kind not in TYPES:
                problems.append(f"{method_id}.{key} 的类型 {kind} 不在 {TYPES}")
                continue
            if not item.get("label"):
                problems.append(f"{method_id}.{key} 缺少显示名")
            if "default" not in item:
                problems.append(f"{method_id}.{key} 缺少默认值")
            if kind == "enum":
                options = item.get("options") or []
                if not options:
                    problems.append(f"{method_id}.{key} 是枚举但没有候选项")
                elif item.get("default") is not None and item["default"] not in options:
                    problems.append(f"{method_id}.{key} 的默认值不在候选项里")
            if kind in ("number", "integer"):
                low, high = item.get("min"), item.get("max")
                if low is not None and high is not None and low > high:
                    problems.append(f"{method_id}.{key} 的上下界颠倒")
                value = item.get("default")
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if low is not None and value < low - 1e-12:
                        problems.append(f"{method_id}.{key} 的默认值小于下界")
                    if high is not None and value > high + 1e-12:
                        problems.append(f"{method_id}.{key} 的默认值大于上界")
            hidden = item.get("hidden_when")
            if hidden is not None and not isinstance(hidden, dict):
                problems.append(f"{method_id}.{key} 的 hidden_when 需要是字典")
            depends = item.get("depends_on")
            if depends is not None and depends not in seen:
                problems.append(f"{method_id}.{key} 依赖的 {depends} 不在它前面")
    missing = [item["id"] for item in _CATALOG_ITEMS() if not specs(item["id"])]
    if missing:
        problems.append(f"没有参数表的方法：{'、'.join(missing)}")
    return problems


def _CATALOG_ITEMS():
    from engine import catalog

    return catalog.CATALOG


def _CATALOG_IDS():
    return {item["id"] for item in _CATALOG_ITEMS()}
