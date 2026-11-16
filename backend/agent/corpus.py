import json

from engine import catalog, method_math, params


def _capability(item):
    if item["id"].startswith("prep."):
        return "preprocessing"
    if item["id"].startswith(("describe.", "test.", "eval.")):
        return "evaluation"
    if tuple(item["tasks"]) == ("classification",):
        return "classifier"
    if tuple(item["tasks"]) == ("regression",):
        return "regressor"
    return "analysis"


def _entry(item):
    method_id = item["id"]
    lesson = method_math.lesson(method_id) or {}
    return {
        "id": method_id,
        "title": item["label"],
        "capability": _capability(item),
        "tasks": list(item["tasks"]),
        "keywords": [method_id, item["label"], item["group"], *item["scenarios"]],
        "knowledge": "；".join(
            value for value in (item["note"], lesson.get("variant"), lesson.get("meaning")) if value
        ),
        "when": catalog.WHEN.get(method_id, ""),
        "inputs": list(item["inputs"]),
        "parameters": params.defaults(method_id),
        "parameter_specs": params.specs(method_id),
        "outputs": list(item["outputs"]),
        "limits": [lesson["conditions"]] if lesson.get("conditions") else [],
        "sources": lesson.get("sources", []),
    }


CORPUS = [_entry(item) for item in catalog.CATALOG]
BY_ID = {entry["id"]: entry for entry in CORPUS}
RUN_METHODS = {method_id: method_id for method_id in BY_ID}


def run_method(entry_id):
    return RUN_METHODS.get(entry_id)


def by_id(entry_id):
    return BY_ID.get(entry_id)


def methods_for_task(task):
    return [entry["id"] for entry in CORPUS if task in entry["tasks"]]


def entry_text(entry):
    return "\n".join(
        [
            entry["title"],
            "能力：" + entry["capability"],
            "任务：" + "、".join(entry["tasks"]),
            "关键词：" + "、".join(entry["keywords"]),
            "知识：" + entry["knowledge"],
            "适用：" + entry["when"],
            "输入：" + "、".join(entry["inputs"]),
            "参数（当前完整规范）："
            + json.dumps(entry["parameter_specs"], ensure_ascii=False, separators=(",", ":")),
            "输出：" + "；".join(entry["outputs"]),
            "限制：" + "；".join(entry["limits"]),
            "来源：" + json.dumps(entry["sources"], ensure_ascii=False, separators=(",", ":")),
            "可运行标识（run_ml_suite 的 methods）：" + entry["id"],
        ]
    )


def summary(entry):
    method = run_method(entry["id"])
    return {
        "id": entry["id"],
        "title": entry["title"],
        "capability": entry["capability"],
        "tasks": entry["tasks"],
        "when": entry["when"],
        "outputs": entry["outputs"],
        "limits": entry["limits"],
        "sources": entry["sources"],
        "run_method": method,
        "runnable": method is not None and not catalog.missing_for(catalog.BY_ID[method]),
    }
