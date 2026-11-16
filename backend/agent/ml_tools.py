import json
import time
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from agent import algorithm_execution, retriever
from agent.capacity import experiment
from config import (
    ML_TOOLS_MAX_FEATURES as MAX_FEATURES,
)
from config import (
    ML_TOOLS_MAX_METHODS as MAX_METHODS,
)
from config import (
    ML_TOOLS_MAX_ROWS as MAX_ROWS,
)
from config import (
    ML_TOOLS_MAX_RUN_SECONDS as MAX_RUN_SECONDS,
)
from engine import catalog, dataset_selection, datasets, registry
from engine import report as engine_report

FIGURES_DIR = Path("figures")


class UnknownMethods(ValueError):
    def __init__(self, methods):
        self.methods = methods
        super().__init__(
            f"不支持的方法：{'、'.join(methods)}。请从 available_methods 选择真实标识后重新调用，不能自行命名。"
        )

    def result(self):
        return {
            "error": str(self),
            "invalid_methods": self.methods,
            "available_methods": [
                {"id": item["id"], "label": item["label"], "tasks": list(item["tasks"])}
                for item in catalog.CATALOG
            ],
        }


_registry_ready = False


def ensure_methods():
    global _registry_ready
    if _registry_ready:
        return
    for layer in (
        "prepare",
        "stats",
        "evaluate",
        "modeling",
        "machine",
        "domain",
        "series",
        "causal",
    ):
        try:
            registry.load_implementations(layer)
        except ImportError:
            continue
    _registry_ready = True


SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_ml_methods",
        "description": (
            "检索本机方法库，覆盖九大类共 116 个方法（数据准备与特征工程、基础统计与描述性分析、"
            "差异性检验与假设检验、关系与影响建模、分类聚类与机器学习、时间序列与空间计量、"
            "因果推断与实验设计、综合评价与决策分析、特定行业与场景分析）。"
            "返回方法标识、所属类别、适用任务、输出、可调参数与限制，并给出可直接运行的方法标识。"
            "需要先了解可用方法、确认方法标识、确认可调参数、或决定跑哪个方法时先调用它。"
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "minLength": 2, "maxLength": 400},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
            },
        },
    },
}

RUN_TOOL = {
    "type": "function",
    "function": {
        "name": "run_ml_suite",
        "description": (
            "在服务端真正运行方法并生成图。methods 里放方法库里的条目标识，"
            "先用 search_ml_methods 检索得到，例如 ml.random_forest、ml.xgboost、"
            "model.linear、test.anova、eval.topsis、series.arima。"
            "dataset 从每轮 dataset_catalog 或 inspect_datasets 返回的目录里挑：本地数据集 21 份"
            "（含 iris、wine、boston、auto_mpg、cps_wages、air_passengers 等，各自标了任务），"
            "或当前账号上传的表格（形如 file:ab12cd34ef56），或数据入口确认的数据。"
            "由你按方法要求与字段业务含义选择，写真实 id 而不是中文标签。"
            "首次显式填写 dataset；延续同一流程可沿用 automatic_dataset。auto_run 仅为建议；"
            "只想知道某个方法是什么请先调用 search_ml_methods。"
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["reason", "methods"],
            "properties": {
                "reason": {
                    "type": "string",
                    "minLength": 10,
                    "maxLength": 400,
                    "description": "本次要验证的问题，以及所选数据为什么适合该方法；换数据时说明原因。",
                },
                "dataset": {
                    "type": "string",
                    "description": "由模型按问题和字段选择的目录ID，或当前账号上传表格的 file:<id>；首次运行需显式指定。",
                },
                "methods": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_METHODS,
                    "items": {
                        "oneOf": [
                            {"type": "string", "enum": sorted(catalog.BY_ID)},
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "method": {"type": "string", "enum": sorted(catalog.BY_ID)},
                                    "dataset": {"type": "string"},
                                    "target": {"type": "string"},
                                    "group": {"type": "string"},
                                    "time": {"type": "string"},
                                    "task": {
                                        "type": "string",
                                        "enum": ["classification", "regression", "clustering"],
                                    },
                                },
                                "required": ["method"],
                            },
                        ]
                    },
                    "description": (
                        "方法标识，或带自己数据来源的对象 "
                        '{"method": "ml.random_forest", '
                        '"dataset": "wine"}。'
                        "不给 dataset 就用顶层 dataset。"
                    ),
                },
                "params": {
                    "type": "object",
                    "description": (
                        '共享参数直接写字段，例如 {"split_mode":"random","test_size":0.3}；'
                        '单方法独立参数按方法ID分组，例如 {"ml.knn":{"neighbours":5}}。'
                        "独立同名字段覆盖共享字段，合法字段与取值仍以该方法参数表为准。"
                    ),
                },
                "standardize": {"type": "boolean"},
                "pca": {"type": "boolean"},
                "pca_components": {"type": "integer", "minimum": 1, "maximum": 50},
                "seed": {"type": "integer", "minimum": 0, "maximum": 1000000},
                "use_page_split": {"type": "boolean"},
                "figures": {"type": "boolean"},
                "parallel_coordinates": {"type": "boolean"},
                "target": {"type": "string", "description": "方法库条目要用的结果列名。"},
                "task": {
                    "type": "string",
                    "enum": ["classification", "regression", "clustering"],
                    "description": "上传数据本次运行的目标任务；先看真实字段，预测需同时指定 target。不修改账号数据的保存配置。",
                },
                "group": {
                    "type": "string",
                    "description": "方法库条目要用的分组列名（面板/混合模型需要）。",
                },
                "time": {"type": "string", "description": "方法库条目要用的时间列名。"},
            },
        },
    },
}

TOOLS = [SEARCH_TOOL, RUN_TOOL, dataset_selection.TOOL]
TOOL_NAMES = tuple(tool["function"]["name"] for tool in TOOLS)

TOOL_PROMPT = """你可以调用方法检索、数据查看和实验运行工具。
search_ml_methods：在本机方法库里检索（方法名匹配 + BM25 + 可选向量召回 + 重排序），覆盖九大类 116 个方法，
  返回方法标识、所属类别、适用任务、输出与限制；library_matches 是方法库里的匹配条目。
  想解释概念、推荐方法、确认方法标识或不确定该跑什么时先调用它。
  runnable_methods 与 auto_run.runnable_methods 使用相同适配口径；auto_run 仅为建议，不代替数据选择。
inspect_datasets：省略 dataset 时浏览内置与当前账号上传数据目录，可分页；指定 dataset 时读取真实字段、类型、缺失、范围与前5行。
  默认你自己根据问题和方法选择数据，不能要求用户先手动指定；字段含义不清楚时先查看，不能把普通数值列冒充专业角色。
run_ml_suite：真正在服务端运行方法并生成图。必填 reason（说明本次要验证的问题）、methods、params 和顶层 figures 布尔值。
  数据集用 dataset 显式指定目录中的真实ID（含账号上传数据），不能默认用 iris。
  methods 里放方法库的条目标识，共 116 个（ml.xgboost、model.linear、test.ttest、eval.topsis、series.arima 等）；
  也可以写成 {"method": "ml.random_forest", "dataset": "wine"} 这样给单个方法单独指定数据，
  一次调用就能让不同方法跑在不同数据集上。
  先考虑 automatic_dataset 中上次成功使用的数据，适合当前流程时沿用；换数据需说明名称和原因。
  selected_dataset 是用户主动指定时的覆盖约束；不适用时说明原因，不得擅自换用其他数据。
  上传数据无需用户先配置：查看后用 target/task/time/group 指定本次角色，仅描述/文本/聚类无需目标列。
  你自己挑了数据时，必须在回答里说明用的是哪份数据、它大致是什么内容
  （标签、样本数、列数、目标列），不要只汇报指标。
  方法设置只放 params（例如 {"clusters": 3}、{"method": "spearman"}、{"standardize": true}）；接受全部默认值也显式传 {}。
  多方法共享设置可直接写字段；独立设置可按真实方法ID分组，如 {"test_size":0.3,"ml.knn":{"neighbours":5}}。
  分组参数仅传给对应方法，同名字段覆盖共享参数；不适用字段和与顶层设置冲突的值仍会拒绝。
  用户指定的设置必须逐项转成当前参数表的字段，不能遗漏后用默认值执行；参数含义有歧义时先核对，不能自行猜值。
  figures 控制本次是否允许出图，方法自己的绘图项仍在 params。两处同名值不得冲突。
  需要指定结果列、分组列或时间列时用 target / group / time；不需要就省略，不填占位文字。
  调用参数错误时按错误字段修正后再调用；相同错误不要重复提交。服务端会在执行前拒绝无效参数。
自动实验规则（对全部算法一视同仁，不是只有随机森林）：
  用户问的是真实表现、想比较方法或要图时，核对方法和数据要求后调用 run_ml_suite，用真实结果回答。
  auto_run 不强制首个方法，用户点名的方法优先；可用检索结果或 inspect_datasets 核对所需字段。
  方法库里 missing 非空的表示缺少依赖，要向用户说明缺什么，不要假装跑过。
  auto_run.available 为 false 时先查看目录/字段；无合适数据则说明缺少什么并建议上传，不要拼凑数据硬跑。
  不要重复劳动：历史里的工具记录已经写明做过哪些检索和实验。同一个数据集上已经跑过的方法不要重跑，
  方法库也不需要每轮重新检索；用户换了数据、方法、参数或明确要求重跑时需要新的一次调用。
  用户只是问概念、问原理、问如何选择时不要跑实验，直接用检索到的方法库内容回答。
只有拿到 run_ml_suite 的实际返回值后才能声称跑过实验；报告指标必须逐字引用返回值，不要自己编造或外推。
返回值里的 failures 列出没跑成功的方法，必须如实说明原因，不要用推测结果补上。
指标要同时说明训练与测试口径、划分方式与预处理（标准化/PCA）状态；只有一个参数变化时才能讨论该参数的影响。
讲一个方法的调参必须讲全：关键参数有哪些、各自的范围与默认值、调大调小分别会怎样改变结果、在这份数据上建议从哪个取值起步；
参数名、范围与默认值只能来自返回值里的 parameters（该方法的完整参数表）与 params（本次生效值），不要凭记忆编造。
一次实验最多 6 个方法；图会保存到服务端 figures 目录并在返回值里给出 URL，说明图名与它展示的内容即可。
想让用户看到图时，先用 params 把该方法参数表里的图形开关（*_plot、*chart*、*figure* 这类布尔项）打开再运行；
默认关着的图不会生成，回答里不要声称有图。返回值里 figures 为空就说明这次没出图，并说明怎么打开。
限制：聚类不需要标签，使用全部记录；PCA 之后不再绘制原始特征散点图与平行坐标图。"""


def _figure_root():
    """出图目录只认 utils.config.FIGURE_ROOT：预览进程改的就是它，调用方传进来的 root 只管数据。"""
    from config import FIGURE_ROOT

    return Path(FIGURE_ROOT)


def _tools_dir(session_id=None, run_id=None):
    from agent import figure_scope

    return figure_scope.scope_in(_figure_root(), session_id, run_id)


def _relative_dir(target):
    return Path(target).resolve().relative_to(_figure_root().resolve()).as_posix()


def _runnable(results):
    methods = []
    for item in results:
        method = item.get("run_method")
        if method and registry.known(method) and method not in methods:
            methods.append(method)
    return methods


def _method_task(method):
    return registry.method_task(method)


def _is_catalog(method):
    return method in catalog.BY_ID


def _compatible(method, task):
    if task in (None, ""):
        return True
    item = catalog.BY_ID.get(method, {})
    if task in (item.get("tasks") or ()):
        return True
    if task == "clustering" and item.get("kind") in ("描述统计", "文本分析"):
        return True
    method_task = _method_task(method)
    if method_task == task:
        return True
    return method_task == "clustering" and task == "classification"


def _for_task(methods, task):
    return [method for method in methods if _compatible(method, task)]


def _dataset_choices(context_snapshot):
    snapshot = context_snapshot if isinstance(context_snapshot, dict) else {}
    if isinstance(snapshot.get("dataset_catalog"), dict):
        choices = list(snapshot["dataset_catalog"].get("datasets") or [])
        selected = snapshot.get("selected_dataset")
        if selected and not any(item["id"] == selected["dataset"] for item in choices):
            choices.append({**selected, "id": selected["dataset"]})
        return choices
    choices = [
        {
            "id": key,
            "label": value["label"],
            "task": value["task"],
            "target": value.get("target"),
            "time": value.get("time_column"),
            "text_column": value.get("text_column"),
            "group": value.get("group_column"),
            "kind": "本地数据集",
        }
        for key, value in sorted(datasets.DATASETS.items())
    ]
    seen = set(datasets.DATASETS)
    for item in snapshot.get("files") or []:
        key = item.get("dataset") if isinstance(item, dict) else None
        if isinstance(key, str) and key and key not in seen:
            seen.add(key)
            choices.append(
                {
                    "id": key,
                    "label": item.get("label") or item.get("name") or "本对话上传的表格",
                    "task": item.get("task"),
                    "target": item.get("target"),
                    "time": item.get("time"),
                    "kind": "本对话上传",
                }
            )
    page = snapshot.get("dataset")
    if isinstance(page, str) and page and page not in seen:
        choices.append(
            {
                "id": page,
                "label": snapshot.get("label") or "数据入口确认的数据",
                "task": snapshot.get("task"),
                "target": snapshot.get("target"),
                "time": snapshot.get("time"),
                "kind": "数据入口确认",
            }
        )
    return choices


def _search_result(results, context_snapshot):
    found = _runnable(results)
    snapshot = context_snapshot if isinstance(context_snapshot, dict) else {}
    task = snapshot.get("task")
    choices = _dataset_choices(snapshot)
    if snapshot.get("dataset_policy"):
        selected = snapshot.get("selected_dataset")
        candidates = [item for item in choices if not selected or item["id"] == selected["dataset"]]
        runnable = [
            method
            for method in found
            if any(dataset_selection.suitable(method, item) for item in candidates)
        ]
        # A paginated catalogue may omit the right upload. Let the model inspect later pages.
        if snapshot.get("dataset_catalog", {}).get("next_offset") is not None and not selected:
            runnable = found
    else:
        runnable = _for_task(found, task)
    dropped = [method for method in found if method not in runnable]
    if not runnable:
        theirs = sorted({_method_task(method) for method in found})
        note = (
            "检索到的方法没有能在当前数据上运行的；"
            if found
            else "检索结果里没有可直接运行的方法；"
        )
        if theirs:
            note += "请核对所需字段与业务含义；可查看数据目录，确实无合适数据时说明限制或请求上传。"
        return {
            "available": False,
            "method": None,
            "task": None,
            "runnable_methods": [],
            "incompatible_methods": dropped,
            "note": note,
        }
    hit = runnable[0]
    required = _method_task(hit)
    dataset = (snapshot.get("selected_dataset") or {}).get("dataset") or snapshot.get("dataset")
    target = dataset if dataset in datasets.DATASETS else None
    call = f'run_ml_suite(methods=["{hit}"]' + (f', dataset="{target}"' if target else "") + ")"
    note = (
        f"检索到候选方法 {hit}。用户需要实验时，先根据方法要求选择最合适的数据，再调用 {call}。"
        "这是建议而非强制首选；以用户点名的方法和真实数据条件为准。"
    )
    if dropped:
        note += f"（{'、'.join(dropped)} 与当前数据任务不符，不要运行。）"
    return {
        "available": True,
        "method": hit,
        "task": required,
        "dataset": target,
        "params": _parameter_brief(hit),
        "runnable_methods": runnable,
        "incompatible_methods": dropped,
        "note": note,
    }


def search(arguments, retriever_instance=None, context_snapshot=None):
    if not isinstance(arguments, dict) or "query" not in arguments:
        raise ValueError("检索参数格式无效。")
    query = arguments["query"]
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 400:
        raise ValueError("检索关键词需为 2–400 字。")
    top_k = arguments.get("top_k", 4)
    if top_k is not None and (type(top_k) is not int or not 1 <= top_k <= 10):
        raise ValueError("top_k 需为 1–10 的整数。")
    instance = retriever_instance or retriever.RETRIEVER
    outcome, context = instance.context(query.strip(), top_k or 4)
    results = outcome["results"]
    library = _library_matches(query.strip(), top_k or 4)
    known = {item.get("run_method") for item in results}
    results_for_selection = [
        *results,
        *[
            {"run_method": item["id"]}
            for item in library
            if item["id"] not in known and item["runnable"]
        ],
    ]
    suggestion = _search_result(results_for_selection, context_snapshot)
    runnable = suggestion["runnable_methods"]
    choices = _dataset_choices(context_snapshot)
    notes = [
        "检索结果来自本机方法库，不是模型记忆。",
        "runnable_methods 就是 run_ml_suite 的 methods 参数可用的标识。",
        suggestion["note"],
        "datasets 是本次可运行的全部数据（本地数据集、本对话上传的表格、数据入口确认的数据）。"
        "数据由你根据问题、方法要求、真实字段和业务含义选择。先考虑沿用上轮合适数据，换数据时说明原因。"
        "同一比较必须保持数据和划分一致。不同数据的教学演示可在 methods 对象分别指定，但不能直接比较指标。"
        "dataset 参数写 datasets 里的 id（如 iris、wine_quality_red、file:ab12cd34ef56），"
        "不要写中文标签。",
    ]
    if library:
        notes.append(
            "方法库还有这些匹配条目，可用 run_ml_suite(methods=[...]) 直接运行："
            + "、".join(f"{item['id']}（{item['label']}）" for item in library[:4])
        )
    return {
        "query": outcome["query"],
        "channels": outcome["channels"],
        "results": results,
        "context": context,
        "runnable_methods": runnable,
        "datasets": choices,
        "dataset_requirements": {
            method: dataset_selection.requirements(method)
            for method in _runnable(results_for_selection)
        },
        "dataset_candidates": {
            method: [item["id"] for item in choices if dataset_selection.suitable(method, item)]
            for method in runnable
        },
        "datasets_next_offset": (context_snapshot or {})
        .get("dataset_catalog", {})
        .get("next_offset"),
        "auto_run": suggestion,
        "library_matches": library,
        "notes": notes,
    }


def _parameter_brief(method_id):
    from engine import params as method_params

    parts = []
    for spec in method_params.specs(method_id):
        if spec["key"] == "figures":
            continue
        kind = spec["type"]
        if kind == "enum":
            body = "/".join(
                "无" if option is None else str(option) for option in spec.get("options") or []
            )
        elif kind == "boolean":
            body = "是/否"
        elif kind == "columns":
            body = "列名列表"
        elif kind == "text":
            body = "文本"
        else:
            low, high = spec.get("min"), spec.get("max")
            body = f"{low}~{high}" if low is not None or high is not None else "数值"
        default = spec.get("default")
        parts.append(
            f"{spec['label']}({spec['key']}={default if default is not None else '空'}，{body})"
        )
    return "；".join(parts)


def _library_matches(query, top_k):
    scored = []
    needles = [part for part in query.lower().split() if part]
    for item in catalog.CATALOG:
        haystack = " ".join(
            [item["id"], item["label"], item.get("group") or "", item.get("note") or ""]
        ).lower()
        score = sum(1 for needle in needles if needle in haystack)
        if score == 0 and query.lower() in haystack:
            score = 1
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    picked = []
    for position, (_, item) in enumerate(scored[: max(top_k, 4)]):
        absent = catalog.missing_for(item)
        entry = {
            "id": item["id"],
            "label": item["label"],
            "category_label": catalog.CATEGORY_NAMES.get(catalog.category_of(item["id"]), ""),
            "group": item.get("group"),
            "tasks": list(item["tasks"]),
            "note": item.get("note") or "",
            "runnable": not absent,
            "missing": absent,
        }
        if position < 4:
            entry["params"] = _parameter_brief(item["id"])
        picked.append(entry)
    return picked


def _friendly(error, label):
    message = str(error)
    if "Singular" in message or "singular" in message:
        return (
            f"{label}求解时矩阵奇异：自变量之间高度相关，或量纲差异过大。"
            "先做标准化、去掉共线的自变量，再重试。"
        )
    if "overflow" in message or "divide by zero" in message:
        return f"{label}数值溢出：先做标准化或变换量纲，再重试。"
    return message


def _run_catalog(arguments, methods, bundle, source, root, session_id, data_store=None):
    figures = arguments.get("figures", True)
    figures_dir = _tools_dir(session_id) if figures else None
    version = arguments.get("data_version")
    table = registry.from_bundle(bundle, data_store, version)
    target = arguments.get("target")
    group = arguments.get("group")
    time_column = arguments.get("time")
    task = arguments.get("task") or table.task
    if task not in ("classification", "regression", "clustering"):
        raise dataset_selection.SelectionError(
            "任务应为 classification、regression 或 clustering。"
        )
    if (
        (target and target != table.target_name)
        or (group and group != table.group_name)
        or (time_column and time_column != table.time_name)
        or task != table.task
    ):
        from engine import tabular

        table = tabular.build(
            table.raw,
            target=target or table.target_name,
            group=group or table.group_name,
            time=time_column or table.time_name,
            task=task,
        )
    if (
        table.task == "regression"
        and table.target_name
        and not pd.api.types.is_numeric_dtype(table.raw[table.target_name])
    ):
        raise dataset_selection.SelectionError("回归目标列必须是数值。", "dataset_incompatible")
    params = arguments.get("params")
    if not isinstance(params, dict):
        params = {}
    params = dict(params)
    from engine import params as method_params

    allowed = set()
    for name in methods:
        allowed.update(method_params.keys(name))
    if arguments.get("standardize") is True and "standardize" in allowed:
        params.setdefault("standardize", True)
    if arguments.get("pca") is True and "pca" in allowed:
        params.setdefault("pca", True)
    if arguments.get("pca_components") and "pca_components" in allowed:
        params.setdefault("pca_components", arguments["pca_components"])
    if arguments.get("parallel_coordinates") and "parallel_coordinates" in allowed:
        params.setdefault("parallel_coordinates", True)
    seed = arguments.get("seed", 42)
    if type(seed) is not int or not 0 <= seed <= 1000000:
        raise ValueError("随机种子需为 0–1000000 的整数。")
    if "seed" in allowed:
        params.setdefault("seed", seed)
    if (
        arguments.get("use_page_split")
        and "split_mode" in allowed
        and getattr(table, "page_split", None)
    ):
        params.setdefault("split_mode", "page")

    started = time.perf_counter()
    results = []
    failures = []
    for name in methods:
        if not _is_catalog(name):
            failures.append(
                {
                    "method": name,
                    "error": "这个方法标识不在方法库里，请先调用 search_ml_methods 确认。",
                }
            )
            continue
        entry = catalog.BY_ID[name]
        absent = catalog.missing_for(entry)
        if absent:
            failures.append(
                {
                    "method": name,
                    "label": entry["label"],
                    "error": f"需要 {', '.join(absent)}，当前环境未安装。",
                }
            )
            continue
        try:
            algorithm_execution.check()
            subset = method_params.for_method(name, params)
            subset = dataset_selection.prepare(name, table, subset)
            outcome = algorithm_execution.run_method(
                name,
                table,
                subset,
                root=root,
                figures_dir=figures_dir,
                session_id=session_id,
                figures=bool(figures),
            )
        except algorithm_execution.AlgorithmTimeout as error:
            failures.extend(
                {"method": pending, "error": str(error), "code": error.code}
                for pending in methods[methods.index(name) :]
            )
            break
        except Exception as error:
            failures.append(
                {"method": name, "label": entry["label"], "error": _friendly(error, entry["label"])}
            )
            continue
        if figures_dir:
            try:
                folder = _relative_dir(figures_dir)
            except ValueError:
                folder = None
            if folder:
                for figure in outcome.get("figures") or []:
                    stem = figure.get("name")
                    if stem:
                        figure["url"] = "/api/figures/" + quote(f"{folder}/{stem}")
        results.append(outcome)
        try:
            import matplotlib.pyplot as plt

            plt.close("all")
        except Exception:
            pass

    report = {
        "reason": arguments.get("reason"),
        "source": source,
        "dataset": bundle.get("dataset"),
        "dataset_label": bundle.get("label"),
        "task": table.task,
        "data": table.summary(),
        "methods": engine_report.methods(results),
        "failures": failures,
        "failures_note": (
            "以下方法没有跑成功，请如实说明原因："
            + "；".join(
                f"{item.get('label') or item['method']}：{item['error']}" for item in failures
            )
        )
        if failures
        else None,
        "figures": engine_report.figures_of(results),
        "figures_dir": (_relative_dir(figures_dir) if figures_dir else None),
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "methods_available": sorted(catalog.BY_ID),
    }
    return datasets.with_metadata(report)


@experiment
def run(arguments, context, data_store, root, session_id=None, data_access=None):
    # A single budget covers all methods and dataset groups in this tool call.
    with algorithm_execution.execution_scope(seconds=MAX_RUN_SECONDS):
        return _run(arguments, context, data_store, root, session_id, data_access)


def _run(arguments, context, data_store, root, session_id=None, data_access=None):
    ensure_methods()
    if not isinstance(arguments, dict):
        raise ValueError("工具参数格式无效。")
    arguments = dict(arguments)
    selected = context.get("selected_dataset") if data_access else None
    if selected:
        requested = arguments.get("dataset")
        if requested and requested != selected["dataset"]:
            raise ValueError(
                f"当前会话已选择 {selected['dataset']}，请使用这份数据；换数据请点击选择数据集。"
            )
        for key in ("dataset", "target", "time", "group"):
            arguments[key] = selected.get(key)
    reason = arguments.get("reason")
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 400:
        raise ValueError("调用工具须说明具体不确定之处。")
    methods = arguments.get("methods")
    if not isinstance(methods, list) or not 1 <= len(methods) <= MAX_METHODS:
        raise ValueError(f"需要 1–{MAX_METHODS} 个方法。")
    resolved = []
    overrides = {}
    for item in methods:
        if isinstance(item, dict):
            name = str(item.get("method") or item.get("id") or "")
            if any(item.get(key) for key in ("dataset", "target", "group", "time", "task")):
                overrides[name] = {
                    key: item[key]
                    for key in ("dataset", "target", "group", "time", "task")
                    if item.get(key)
                }
                if selected and any(
                    value != selected.get(key) for key, value in overrides[name].items()
                ):
                    raise ValueError(
                        "当前会话已选择数据与字段角色，方法参数不能覆盖；请在右侧数据集恢复自动选择或修改指定。"
                    )
        else:
            name = str(item)
        if name not in resolved:
            resolved.append(name)
    unknown = [name for name in resolved if not isinstance(name, str) or not registry.known(name)]
    if unknown:
        raise UnknownMethods(unknown)
    every = overrides and all(name in overrides for name in resolved)
    if every and (
        arguments.get("dataset") or all(overrides[name].get("dataset") for name in resolved)
    ):
        return _run_mixed(
            arguments,
            resolved,
            overrides,
            None,
            None,
            root,
            session_id,
            data_store,
            context,
            data_access,
        )
    bundle, source = _resolve_data(arguments, context, data_store, root, session_id, data_access)
    task = bundle["task"]
    legacy = [name for name in resolved if not _is_catalog(name)]
    if (
        legacy
        and task == "classification"
        and all(_method_task(name) == "regression" for name in legacy)
    ):
        raise ValueError("这份数据是分类任务，请选择分类方法。")
    if (
        legacy
        and task == "regression"
        and all(_method_task(name) == "classification" for name in legacy)
    ):
        raise ValueError("这份数据是回归任务，请选择回归方法。")
    if overrides:
        return _run_mixed(
            arguments,
            resolved,
            overrides,
            bundle,
            source,
            root,
            session_id,
            data_store,
            context,
            data_access,
        )
    arguments = dict(arguments)
    arguments["methods"] = resolved
    previous = (context.get("automatic_dataset") or {}).get("dataset")
    result = _run_catalog(arguments, resolved, bundle, source, root, session_id, data_store)
    result["dataset_choice"] = {
        "mode": "manual" if selected else "automatic",
        "previous_dataset": previous,
        "changed": bool(previous and previous != result.get("dataset")),
        "reason": reason,
    }
    _remember(result, context, data_access, session_id)
    return result


def _remember(result, context, data_access, session_id):
    if not data_access or not session_id or context.get("selected_dataset"):
        return
    from engine import account_datasets

    account_datasets.remember_automatic(*data_access, session_id, result)
    if result.get("methods") and result.get("dataset"):
        context["automatic_dataset"] = account_datasets.automatic(*data_access, session_id)


def _run_mixed(
    arguments,
    resolved,
    overrides,
    bundle,
    source,
    root,
    session_id,
    data_store,
    context=None,
    data_access=None,
):
    groups = []
    for name in resolved:
        key = json.dumps(overrides.get(name, {}), sort_keys=True)
        for group in groups:
            if group["key"] == key:
                group["methods"].append(name)
                break
        else:
            groups.append({"key": key, "fields": overrides.get(name, {}), "methods": [name]})
    merged = None
    used = []
    for group in groups:
        fields = group["fields"]
        payload = dict(arguments)
        payload["methods"] = group["methods"]
        for key, value in fields.items():
            payload[key] = value
        if fields:
            selected = (context or {}).get("selected_dataset") if data_access else None
            if selected and fields.get("dataset", selected["dataset"]) != selected["dataset"]:
                raise ValueError("当前会话已选择数据集，不能在方法参数中切换到其他数据。")
            if not payload.get("dataset") and bundle:
                payload["dataset"] = bundle.get("dataset")
            group_bundle, group_source = _resolve_data(
                payload, context or {}, data_store, root, session_id, data_access
            )
        else:
            group_bundle, group_source = bundle, source
        report = _run_catalog(
            payload, group["methods"], group_bundle, group_source, root, session_id, data_store
        )
        _remember(report, context or {}, data_access, session_id)
        used.append(
            {
                "dataset": report.get("dataset"),
                "label": report.get("dataset_label"),
                "source": report.get("source"),
                "methods": group["methods"],
            }
        )
        for name, entry in (report.get("methods") or {}).items():
            entry["dataset"] = report.get("dataset")
            entry["dataset_label"] = report.get("dataset_label")
            entry["source"] = report.get("source")
        if merged is None:
            merged = report
        else:
            merged["methods"].update(report.get("methods") or {})
            merged["failures"].extend(report.get("failures") or [])
            merged["figures"].extend(report.get("figures") or [])
            merged["elapsed_ms"] = merged.get("elapsed_ms", 0) + report.get("elapsed_ms", 0)
            if report.get("failures_note"):
                merged["failures_note"] = (
                    (merged.get("failures_note") or "") + " " + report["failures_note"]
                ).strip()
    merged["datasets"] = used
    if len(used) > 1:
        merged["source"] = "、".join(item["source"] for item in used if item["source"])
        merged["dataset"] = None
    return merged


def _data_dir(root):
    return Path(root) / "data"


def _dataset_snapshot(arguments, context, data_store):
    selected = context.get("selected_dataset")
    if isinstance(selected, dict):
        return {**context, **selected}
    version = context.get("data_version")
    if version:
        stored = data_store.get(version)
        if stored is not None:
            return {
                **context,
                "data_version": version,
                "task": stored.get("task") or context.get("task"),
                "dataset": "page",
            }
    dataset_id = arguments.get("dataset")
    if dataset_id in datasets.DATASETS:
        return {**context, "dataset": dataset_id, "task": datasets.DATASETS[dataset_id]["task"]}
    return dict(context)


def _resolve_data(arguments, context, data_store, root, session_id=None, data_access=None):
    version = context.get("data_version")
    if version:
        stored = data_store.get(version)
        if stored is None:
            raise ValueError("本轮确认的数据不在服务端，请重新确认数据后再试。")
        bundle = dict(stored)
        bundle.setdefault("dataset", "page")
        bundle.setdefault("label", "数据入口确认的数据")
        _check_size(bundle)
        return bundle, "数据入口确认的数据"
    dataset_id = arguments.get("dataset")
    if not dataset_id and context.get("dataset_policy", {}).get("mode") == "auto":
        previous = context.get("automatic_dataset") or {}
        identifier = previous.get("dataset")
        if identifier:
            profile = dataset_selection.with_roles(
                dataset_selection.inspect(root, identifier, data_access), previous
            )
            names = [
                item.get("method") if isinstance(item, dict) else item
                for item in arguments.get("methods", [])
            ]
            if all(dataset_selection.suitable(name, profile) for name in names):
                dataset_id = identifier
        if not dataset_id:
            raise dataset_selection.SelectionError(
                "请根据方法要求从 dataset_catalog 选择合适数据，并显式填写 dataset；可用 inspect_datasets 查看字段。没有适合的数据时请说明原因，不要使用默认 iris。"
            )
    if not dataset_id:
        dataset_id = _attached_dataset(context)
    if not dataset_id:
        raise ValueError(
            "请指定本地数据集（iris、wine、boston）、本对话上传的文件，或先在数据页确认数据。"
        )
    if isinstance(dataset_id, str) and dataset_id.startswith("file:"):
        from engine import account_datasets, uploads

        try:
            if data_access:
                users, owner = data_access
                # Legacy imports are permitted only for a session owned by the authenticated account.
                from agent import eventlog

                if session_id and eventlog.SessionLog(users, owner, session_id).exists():
                    account_datasets.import_legacy(users, owner, root)
                roles = context.get("selected_dataset")
                if not roles:
                    record = account_datasets.summary(users, owner, dataset_id[5:])
                    previous = context.get("automatic_dataset") or {}
                    roles = {key: record.get(key) for key in ("target", "task", "time", "group")}
                    if not record.get("configured"):
                        roles = {"target": None, "task": None, "time": None, "group": None}
                    if previous.get("dataset") == dataset_id:
                        roles.update({key: previous.get(key) for key in roles})
                    roles.update({key: arguments[key] for key in roles if key in arguments})
                    if roles.get("task") not in (
                        None,
                        "classification",
                        "regression",
                        "clustering",
                    ):
                        raise dataset_selection.SelectionError(
                            "任务应为 classification、regression 或 clustering。"
                        )
                    if roles.get("task") in ("classification", "regression") and not roles.get(
                        "target"
                    ):
                        raise dataset_selection.SelectionError(
                            "预测任务需要显式指定真实 target 列，请先查看上传数据字段。"
                        )
                    if roles.get("task") == "clustering" and roles.get("target"):
                        raise dataset_selection.SelectionError("无目标分析不能同时指定 target。")
                bundle = account_datasets.bundle(
                    users, owner, dataset_id[5:], roles=roles, allow_unconfigured=True
                )
            else:
                bundle = uploads.bundle(
                    root, session_id, dataset_id[5:], target=arguments.get("target")
                )
        except uploads.UploadError as error:
            raise ValueError(str(error)) from error
        _check_size(bundle)
        return bundle, f"本对话上传的文件（{bundle.get('label')}）"
    bundle = datasets.load(dataset_id, _data_dir(root))
    bundle["label"] = datasets.DATASETS[dataset_id]["label"]
    _check_size(bundle)
    return bundle, f"本地数据集 {dataset_id}"


def _attached_dataset(context):
    if not isinstance(context, dict):
        return None
    if isinstance(context.get("selected_dataset"), dict):
        return context["selected_dataset"].get("dataset")
    files = context.get("files")
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict) and isinstance(item.get("dataset"), str):
                return item["dataset"]
    draft = context.get("draft")
    if isinstance(draft, dict) and isinstance(draft.get("dataset"), str):
        return draft["dataset"]
    return None


def _check_size(bundle):
    rows = len(bundle["X"])
    columns = len(bundle["X"][0]) if rows else 0
    if (MAX_ROWS is not None and rows > MAX_ROWS) or (
        MAX_FEATURES is not None and columns > MAX_FEATURES
    ):
        limits = []
        if MAX_ROWS is not None:
            limits.append(f"{MAX_ROWS} 行")
        if MAX_FEATURES is not None:
            limits.append(f"{MAX_FEATURES} 个特征")
        raise ValueError("数据规模超出限制：最多 " + "、".join(limits) + "。")
    if rows < 1:
        raise ValueError("没有可用记录。")


def execute(
    name,
    arguments,
    context,
    data_store,
    root,
    retriever_instance=None,
    session_id=None,
    data_access=None,
):
    if name == "inspect_datasets":
        try:
            return dataset_selection.inspect_tool(arguments, root, data_access)
        except (ValueError, TypeError, OSError) as error:
            return {"error": str(error)[:600]}
    if name == "search_ml_methods":
        try:
            snapshot = _dataset_snapshot(arguments, context, data_store)
        except (ValueError, TypeError, KeyError, AttributeError, IndexError):
            snapshot = {}
        return search(arguments, retriever_instance, snapshot)
    if name == "run_ml_suite":
        try:
            return run(arguments, context, data_store, root, session_id, data_access=data_access)
        except dataset_selection.SelectionError as error:
            return {
                "error": str(error),
                "code": error.code,
                "next_action": "查看 inspect_datasets 的真实字段，纠正数据和角色后重试；无合适数据则解释限制，不得捏造结果。",
            }
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            IndexError,
            ZeroDivisionError,
            OverflowError,
        ) as error:
            return {"error": str(error)[:600]}
    return {"error": f"不支持的工具 {name}。"}
