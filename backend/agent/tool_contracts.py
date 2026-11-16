import copy
import json
import re

from engine import catalog, params


class InvalidArguments(ValueError):
    pass


def _field(spec):
    kind = spec["type"]
    schema = {"description": spec["label"], "default": spec.get("default")}
    if kind == "enum":
        schema["enum"] = list(spec["options"])
        if spec.get("default") is None and None not in schema["enum"]:
            schema["enum"].append(None)
    elif kind == "columns":
        schema.update(type=["array", "null"], items={"type": "string"})
    else:
        mapped = "string" if kind == "text" else kind
        schema["type"] = [mapped, "null"] if spec.get("default") is None else mapped
    for source, target in (("min", "minimum"), ("max", "maximum")):
        if source in spec:
            schema[target] = spec[source]
    return schema


def parameter_schema(methods):
    properties = {}
    owners = {}
    for method in methods:
        for spec in params.specs(method):
            if spec["key"] == "figures":
                continue
            value = _field(spec)
            key = spec["key"]
            owners.setdefault(key, []).append(method)
            if key not in properties:
                properties[key] = value
            elif properties[key] != value:
                variants = properties[key].get("anyOf", [properties[key]])
                if value not in variants:
                    properties[key] = {"anyOf": [*variants, value]}
    for key, value in properties.items():
        value["description"] = (
            value.get("description", "") + "；仅适用于：" + "、".join(owners[key])
        )
    for method in methods:
        properties[method] = {
            "type": "object",
            "properties": {
                spec["key"]: _field(spec)
                for spec in params.specs(method)
                if spec["key"] != "figures"
            },
            "additionalProperties": False,
            "description": (
                "仅用于 "
                + method
                + " 的独立参数；同名字段覆盖共享参数，未填字段沿用共享值或默认值。"
            ),
        }
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": not bool(methods),
        "description": (
            "逐项填写用户指定的设置；未指定项才用默认值，接受全部默认也显式传 {}。"
            "本步字段来自当前候选方法的服务端参数表；换方法先检索。"
            '共享设置直接写字段；独立设置按方法ID分组，例如 {"test_size":0.3,"ml.knn":{"neighbours":5}}。'
            "figures/seed 等同名顶层设置不能与 params 冲突。"
        ),
    }


def _candidates(session):
    explicit = [
        method
        for method in re.findall(
            r"(?<![A-Za-z0-9_.])[a-z_]+\.[a-z_0-9]+(?![A-Za-z0-9_.])", session.request.question
        )
        if method in catalog.BY_ID
    ]
    if explicit:
        return list(dict.fromkeys(explicit))[:6]
    collected = []
    for call in reversed(session.calls):
        result = call.get("result") or {}
        if (
            not collected
            and call["name"] == "run_ml_suite"
            and isinstance(result, dict)
            and result.get("code") == "invalid_tool_arguments"
        ):
            arguments = call.get("arguments") or {}
            selected = arguments.get("methods", []) if isinstance(arguments, dict) else []
            selected = [item.get("method") if isinstance(item, dict) else item for item in selected]
            known = [
                method for method in selected if isinstance(method, str) and method in catalog.BY_ID
            ]
            if known:
                return list(dict.fromkeys(known))[:6]
        if not isinstance(result, dict) or result.get("error"):
            continue
        methods = []
        if call["name"] == "search_ml_methods":
            methods = [item.get("run_method") for item in result.get("results", [])]
            methods += [item.get("id") for item in result.get("library_matches", [])]
        elif call["name"] == "run_ml_suite":
            methods = list((result.get("methods") or {}).keys())
        known = [method for method in methods if method in catalog.BY_ID]
        collected.extend(known)
    return list(dict.fromkeys(collected))[:20]


def tools(session):
    from agent import ml_tools

    available = copy.deepcopy(ml_tools.TOOLS)
    tool = next(
        item["function"] for item in available if item["function"]["name"] == "run_ml_suite"
    )
    schema = tool["parameters"]
    schema["required"] = [*schema["required"], "params", "figures"]
    candidates = _candidates(session)
    schema["properties"]["params"] = parameter_schema(candidates)
    items = schema["properties"]["methods"]["items"]
    items["anyOf"] = items.pop("oneOf")
    if candidates:
        items["anyOf"][0]["enum"] = candidates
        items["anyOf"][1]["properties"]["method"]["enum"] = candidates
    for key in ("target", "group", "time"):
        schema["properties"][key]["description"] = (
            schema["properties"][key].get("description", "真实列名。")
            + "不需要该角色就省略，不要填写占位文字。"
        )
    return available


def _declared_fields(values, properties, excluded=()):
    for key, value in values.items():
        if key in excluded or key not in properties:
            continue
        spec = properties[key]
        kind = spec.get("type")
        valid = {
            "string": isinstance(value, str),
            "integer": type(value) is int,
            "boolean": type(value) is bool,
        }.get(kind, True)
        if not valid:
            raise ValueError(key + " 必须符合类型 " + str(kind))
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(key + " 的可用值为 " + json.dumps(spec["enum"], ensure_ascii=False))
        if kind == "integer" and not spec.get("minimum", value) <= value <= spec.get(
            "maximum", value
        ):
            raise ValueError(key + " 超出工具接口范围。")


def validate_run(arguments):
    from agent import ml_tools

    if not isinstance(arguments, dict):
        raise ValueError("工具参数必须是 JSON 对象。")
    methods = arguments.get("methods")
    if not isinstance(methods, list) or not 1 <= len(methods) <= ml_tools.MAX_METHODS:
        raise ValueError("methods 必须是包含 1–6 个方法的数组。")
    selected = []
    method_shape = ml_tools.RUN_TOOL["function"]["parameters"]["properties"]["methods"]["items"][
        "oneOf"
    ][1]
    for value in methods:
        if isinstance(value, str):
            selected.append(value)
        elif isinstance(value, dict) and isinstance(value.get("method"), str):
            unknown = set(value) - method_shape["properties"].keys()
            if unknown:
                raise ValueError("methods 对象不支持字段：" + "、".join(sorted(unknown)))
            _declared_fields(value, method_shape["properties"], excluded=("method",))
            selected.append(value["method"])
        else:
            raise ValueError("methods 中只能放真实方法标识或包含 method 的对象。")
    unknown_methods = [method for method in selected if method not in catalog.BY_ID]
    if unknown_methods:
        raise ml_tools.UnknownMethods(unknown_methods)
    schema = ml_tools.RUN_TOOL["function"]["parameters"]
    missing = [key for key in ("reason", "params", "figures") if key not in arguments]
    if missing:
        raise ValueError("请显式填写 " + "、".join(missing) + "；使用默认参数也需 params={}。")
    unknown = set(arguments) - schema["properties"].keys()
    if unknown:
        raise ValueError(
            "顶层不支持字段：" + "、".join(sorted(unknown)) + "；方法参数请放入 params。"
        )
    _declared_fields(arguments, schema["properties"], excluded=("methods", "params"))
    reason = arguments["reason"]
    if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 400:
        raise ValueError("reason 需为 10–400 字，说明本次实际要验证的问题。")
    values = arguments["params"]
    if not isinstance(values, dict):
        raise ValueError("params 必须是 JSON 对象，使用默认参数时传 {}。")
    allowed = {key for method in selected for key in params.keys(method)} | set(selected)
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(
            "所选方法不支持 params 字段：" + "、".join(sorted(unknown)) + "；请按检索参数表纠正。"
        )
    for method in selected:
        params.clean(method, params.for_method(method, values))
    for key in ("figures", "standardize", "pca", "use_page_split", "parallel_coordinates"):
        if key in arguments and type(arguments[key]) is not bool:
            raise ValueError(key + " 必须是 JSON 布尔值。")
    for scope, settings in [("params", values)] + [
        ("params." + method, values[method]) for method in selected if method in values
    ]:
        for key in (
            "figures",
            "seed",
            "standardize",
            "pca",
            "pca_components",
            "parallel_coordinates",
        ):
            if (
                key in arguments
                and key in settings
                and settings[key] is not None
                and arguments[key] != settings[key]
            ):
                raise ValueError(
                    "顶层 " + key + " 与 " + scope + "." + key + " 冲突，请只保留一个明确值。"
                )
    if "seed" in arguments and (
        type(arguments["seed"]) is not int or not 0 <= arguments["seed"] <= 1000000
    ):
        raise ValueError("顶层 seed 必须是 0–1000000 的整数。")


def invalid(error, arguments=None):
    result = {
        "error": "调用参数无效，尚未执行实验：" + str(error),
        "code": "invalid_tool_arguments",
        "retryable": True,
    }
    if isinstance(arguments, dict) and isinstance(arguments.get("methods"), list):
        methods = [
            item.get("method") if isinstance(item, dict) else item for item in arguments["methods"]
        ]
        result["accepted_params_by_method"] = {
            method: sorted(params.keys(method))
            for method in methods
            if isinstance(method, str) and method in catalog.BY_ID
        }
        result["recovery"] = (
            "尚未执行。下一次调用的 Schema 已按这些方法收敛；逐项核对合法参数名，"
            "共享参数直接写字段，独立参数写入 params.<方法ID> 对象；"
            "不要猜图形/输出开关。无法满足的输出要求应说明，不要声称已经完成。"
        )
    return result


def fingerprint(name, arguments):
    value = (
        {key: item for key, item in arguments.items() if key != "reason"}
        if isinstance(arguments, dict)
        else arguments
    )
    return name + ":" + json.dumps(value, ensure_ascii=False, sort_keys=True)


def model_result(name, result):
    if name == "search_ml_methods" and isinstance(result.get("context"), str):
        return {
            **result,
            "context": re.sub(r"(?m)^参数（当前完整规范）：.*(?:\n|$)", "", result["context"]),
            "parameter_source": "当前 run_ml_suite.params Schema 与 library_matches 参数简表；参数的完整权威来源为服务端 engine.params。",
        }
    if name == "run_ml_suite":
        return {key: value for key, value in result.items() if key != "methods_available"}
    return result
