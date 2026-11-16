from pathlib import Path

from agent import ml_tools
from config import (
    EXPERIMENTS_MAX_TREES as MAX_TREES,
)
from engine import catalog as library_catalog
from engine import datasets
from engine import params as method_params

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_RUN_SECONDS = ml_tools.MAX_RUN_SECONDS


def catalog_items():
    return library_catalog.CATALOG


def method_parameters(method_id):
    items = method_params.specs(method_id)
    return [dict(item) for item in items] if items else []


def method_parameter_groups(method_id):
    return method_params.groups(method_id)


def check_method_params(methods, parameters):
    if parameters is None:
        return {}
    if not isinstance(parameters, dict):
        raise ValueError("参数格式无效。")
    unknown = [name for name in methods if name not in library_catalog.BY_ID]
    if unknown:
        raise ValueError(f"未知的方法标识：{'、'.join(sorted(unknown))}。")
    allowed = set()
    for name in methods:
        allowed.update(method_params.keys(name))
    extra = sorted(set(parameters) - allowed)
    if extra:
        detail = "；".join(
            f"{name} 支持：{'、'.join(method_params.keys(name)) or '无参数'}" for name in methods
        )
        raise ValueError(f"这些参数不被选中的方法支持：{'、'.join(extra)}。{detail}")
    values = {}
    for name in methods:
        specs = method_params.specs(name)
        if not specs:
            continue
        subset = {
            key: value
            for key, value in parameters.items()
            if key in {spec["key"] for spec in specs}
        }
        try:
            values.update(method_params.clean(name, subset))
        except ValueError as error:
            raise ValueError(f"{library_catalog.BY_ID[name]['label']}：{error}") from None
    return values


class Unavailable(Exception):
    pass


def _run_with_dependencies(callable_, *args, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except ImportError as error:
        raise Unavailable(str(error)) from error


SOURCE_SHAPES = {}


def source_shape(source_id):
    if source_id not in SOURCE_SHAPES:
        try:
            bundle = _run_with_dependencies(datasets.load, source_id, PROJECT_ROOT / "data")
            rows = len(bundle["X"])
            SOURCE_SHAPES[source_id] = (
                len(bundle["X"][0]) if rows else 0,
                len(bundle.get("class_names") or []),
                [str(name) for name in (bundle.get("feature_names") or [])],
            )
        except (ValueError, OSError):
            SOURCE_SHAPES[source_id] = (0, 0, [])
    return SOURCE_SHAPES[source_id]


def _shared_specs():
    return method_parameters("ml.random_forest")


def catalog(root):
    library = []
    for item in catalog_items():
        method_id = item["id"]
        task = (item.get("tasks") or [None])[0]
        category = library_catalog.category_of(method_id)
        library.append(
            {
                "id": method_id,
                "title": item["label"],
                "group": item.get("group"),
                "category": category,
                "category_name": library_catalog.CATEGORY_NAMES.get(category, ""),
                "kind": item.get("kind"),
                "task": task,
                "tasks": list(item.get("tasks") or []),
                "scenarios": list(item.get("scenarios") or []),
                "inputs": list(item.get("inputs") or []),
                "outputs": list(item.get("outputs") or []),
                "note": item.get("note") or "",
                "when": library_catalog.WHEN.get(method_id, ""),
                "level": library_catalog.levels().get(method_id),
                "engine": "library",
                "needs": item.get("needs"),
                "missing": library_catalog.missing_for(item),
                "runnable": library_catalog.runnable(item),
                "params": method_parameters(method_id),
                "groups": method_parameter_groups(method_id),
                "requires": {"source_tasks": ["clustering"] if task == "clustering" else [task]},
            }
        )
    sources = []
    for key, value in datasets.DATASETS.items():
        features, classes, columns = source_shape(key)
        sources.append(
            {
                "id": key,
                "label": value["label"],
                "task": value["task"],
                "features": features,
                "classes": classes,
                "columns": columns,
                "time": value.get("time_column"),
                "group": value.get("group_column"),
                "text": value.get("text_column"),
            }
        )
    return {
        "library": library,
        "shared": _shared_specs(),
        "sources": sources,
        "limits": {
            "max_trees": MAX_TREES,
            "max_run_seconds": MAX_RUN_SECONDS,
            "max_rows": ml_tools.MAX_ROWS,
            "max_methods": ml_tools.MAX_METHODS,
        },
        "figures_dir": str(ml_tools.FIGURES_DIR).replace("\\", "/"),
    }


def run(arguments, context, data_store, root, session_id=None, data_access=None):
    if not isinstance(arguments, dict):
        raise ValueError("请求格式无效。")
    method = arguments.get("method")
    if not isinstance(method, str) or not method:
        raise ValueError("需要指定一个方法。")
    method = str(method)
    if method not in library_catalog.BY_ID:
        raise ValueError(f"不支持的方法：{method}。")
    payload = dict(arguments)
    payload.pop("method", None)
    payload["methods"] = [method]
    if isinstance(payload.get("parameters"), dict):
        payload["params"] = payload.pop("parameters")
    return run_catalog(payload, context, data_store, root, session_id, data_access=data_access)


def run_catalog(arguments, context, data_store, root, session_id=None, data_access=None):
    if not isinstance(arguments, dict):
        raise ValueError("请求格式无效。")
    methods = arguments.get("methods") or (
        [arguments.get("method")] if arguments.get("method") else []
    )
    if not isinstance(methods, list) or not methods:
        raise ValueError("需要指定一个方法。")
    methods = [str(name) for name in methods]
    values = check_method_params(methods, arguments.get("params"))
    payload = {
        "reason": arguments.get("reason") or "从方法库面板运行一次实验。",
        "methods": methods,
        "params": values,
        "dataset": arguments.get("source") or "iris",
        "figures": arguments.get("figures", True),
    }
    for key in ("columns", "target", "group", "time"):
        if arguments.get(key):
            payload[key] = arguments[key]
    if context.get("data_version"):
        payload["data_version"] = context["data_version"]
    return ml_tools.run(
        payload, context, data_store, root, session_id=session_id, data_access=data_access
    )
