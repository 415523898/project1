"""Dataset evidence and method prerequisites; the LLM makes the final choice."""

import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import pandas as pd

from engine import catalog, datasets, uploads

TEXT_METHODS = {"domain.wordfreq", "domain.tfidf", "domain.sentiment", "domain.lda"}
SERIES_METHODS = {
    "series.adf",
    "series.arima",
    "series.sarima",
    "series.garch",
    "series.gm11",
    "series.var",
    "series.coint",
    "series.granger",
    "prep.lag",
}
SURVIVAL_METHODS = {
    "domain.km",
    "domain.cox",
    "domain.nomogram",
    "domain.competing",
    "domain.weibull",
}
ALIASES = {
    "effect_column": ("effect", "effect_size", "estimate", "yi", "log_or", "log_rr", "效应量"),
    "variance_column": (
        "variance",
        "var",
        "vi",
        "se",
        "stderr",
        "standard_error",
        "方差",
        "标准误",
    ),
    "duration_column": (
        "duration",
        "survival_time",
        "followup_time",
        "follow_up",
        "生存时间",
        "随访时间",
    ),
    "event_column": ("event", "event_status", "status", "death", "事件", "死亡"),
    "functional_item": ("functional", "functional_item", "功能具备"),
    "dysfunctional_item": ("dysfunctional", "dysfunctional_item", "功能不具备"),
}


class SelectionError(ValueError):
    def __init__(self, message, code="dataset_required"):
        super().__init__(message)
        self.code = code


def semantic_column(names, key, explicit=None):
    if explicit:
        if explicit not in names:
            raise SelectionError(
                f"指定列 {explicit} 不存在，请先 inspect_datasets 查看真实字段。", "invalid_column"
            )
        return explicit
    lowered = {str(name).strip().lower(): name for name in names}
    return next((lowered[name] for name in ALIASES.get(key, ()) if name in lowered), None)


def _traits(record):
    names = record.get("column_names") or []
    types = record.get("dtypes") or {}
    text = record.get("text_column")
    traits = []
    if text or any(
        value == "text"
        and any(
            word in str(name).lower()
            for word in ("text", "review", "comment", "document", "评论", "文本")
        )
        for name, value in types.items()
    ):
        traits.append("text")
    if record.get("time"):
        traits.append("time")
    if record.get("time") and record.get("group"):
        traits.append("panel")
    if any(
        "nps" in str(name).lower() or "recommend" in str(name).lower() or "推荐" in str(name)
        for name in names
    ):
        traits.append("nps")
    if all(semantic_column(names, key) for key in ("effect_column", "variance_column")):
        traits.append("meta")
    if all(semantic_column(names, key) for key in ("duration_column", "event_column")):
        traits.append("survival")
    if all(semantic_column(names, key) for key in ("functional_item", "dysfunctional_item")):
        traits.append("kano")
    if (
        record.get("dataset") == "consumer_survey"
        or sum(bool(re.match(r"^(q\d+|item[_\d]|题项)", str(name), re.I)) for name in names) >= 2
    ):
        traits.append("survey")
    lowered = {str(name).lower() for name in names}
    if lowered & {"longitude", "lon", "lng", "经度"} and lowered & {"latitude", "lat", "纬度"}:
        traits.append("spatial")
    return traits


def _record(frame, record, details=False):
    result = {
        key: record.get(key)
        for key in (
            "id",
            "dataset",
            "kind",
            "label",
            "task",
            "target",
            "time",
            "group",
            "text_column",
            "configured",
            "suggested_target",
        )
    }
    result["id"] = record["dataset"]
    result["rows"], result["columns"] = frame.shape
    result["column_names"] = [str(name) for name in frame.columns]
    result["dtypes"] = {
        str(name): "number" if pd.api.types.is_numeric_dtype(frame[name]) else "text"
        for name in frame.columns
    }
    result["capabilities"] = _traits(result)
    result["missing_cells"] = int(frame.isna().sum().sum())
    if details:
        result["head"] = uploads._head(frame)
        result["fields"] = []
        for name in frame.columns:
            series = frame[name]
            field = {
                "name": str(name),
                "type": result["dtypes"][str(name)],
                "missing": int(series.isna().sum()),
                "unique": int(series.nunique()),
            }
            if pd.api.types.is_numeric_dtype(series) and series.notna().any():
                field.update(
                    min=uploads._json_safe(series.min()), max=uploads._json_safe(series.max())
                )
            result["fields"].append(field)
    return result


@lru_cache(maxsize=48)
def _builtin(project, identifier, stamp, size, details):
    spec = datasets.DATASETS[identifier]
    path = Path(project) / "data" / spec["file"]
    if spec["kind"] == "iris_metadata":
        frame = pd.read_csv(path, header=None).iloc[1:, : len(spec["features"]) + 1].copy()
        frame.columns = [*spec["features"], "species"]
        frame = frame.apply(pd.to_numeric)
    else:
        frame = pd.read_csv(path, nrows=spec.get("limit"))
    record = {
        "dataset": identifier,
        "id": identifier,
        "kind": "builtin",
        "label": spec["label"],
        "task": spec["task"],
        "target": spec.get("target", "species" if identifier == "iris" else None),
        "time": spec.get("time_column"),
        "group": spec.get("group_column"),
        "text_column": spec.get("text_column"),
    }
    value = _record(frame, record, details)
    value["column_metadata"] = datasets.column_metadata(identifier, value["column_names"])
    value["notes"] = ["目录展示原始表概况；实际实验返回清洗后的行列数。"]
    return value


def inspect(project, identifier, data_access=None):
    if identifier in datasets.DATASETS:
        path = Path(project) / "data" / datasets.DATASETS[identifier]["file"]
        stat = path.stat()
        return deepcopy(_builtin(str(project), identifier, stat.st_mtime_ns, stat.st_size, True))
    if isinstance(identifier, str) and identifier.startswith("file:") and data_access:
        from engine import account_datasets

        users, owner = data_access
        record = account_datasets.summary(users, owner, identifier[5:])
        return _record(account_datasets.frame(users, owner, identifier[5:]), record, True)
    raise SelectionError("这份数据不在当前可访问的数据目录中。", "dataset_unavailable")


def inventory(project, data_access=None):
    result = []
    for identifier, spec in datasets.DATASETS.items():
        path = Path(project) / "data" / spec["file"]
        if not path.is_file():
            continue
        stat = path.stat()
        result.append(
            deepcopy(_builtin(str(project), identifier, stat.st_mtime_ns, stat.st_size, False))
        )
    if data_access:
        from engine import account_datasets

        for record in account_datasets.listing(*data_access):
            item = {
                key: record.get(key)
                for key in (
                    "dataset",
                    "label",
                    "task",
                    "target",
                    "time",
                    "group",
                    "rows",
                    "columns",
                    "column_names",
                    "dtypes",
                    "configured",
                    "suggested_target",
                )
            }
            item.update(id=record["dataset"], kind="upload", capabilities=_traits(record))
            result.append(item)
    return result


def requirements(method):
    if method in TEXT_METHODS:
        return ["有实际文本内容的文本列"]
    if method in SERIES_METHODS:
        return ["有真实顺序的时间列", "数值序列/目标列"]
    if method == "series.panel":
        return ["个体列", "时间列", "数值目标列"]
    if method in ("series.moran", "series.spatial"):
        return ["真实空间坐标列"]
    if method == "domain.meta":
        return ["真实研究效应量列", "方差或标准误列；不可拿普通测量列代替"]
    if method in SURVIVAL_METHODS:
        return ["生存/随访时长列", "事件/删失列"]
    if method == "domain.kano":
        return ["同一需求的功能具备/不具备成对题项"]
    if method == "domain.nps":
        return ["推荐意愿评分列（通常 0–10），可用 score_column 指定"]
    if method == "domain.reliability":
        return ["同一量表的多个题项"]
    return list(catalog.BY_ID.get(method, {}).get("inputs") or [])


def with_roles(profile, roles):
    result = {**profile, **{key: roles.get(key) for key in ("target", "task", "time", "group")}}
    result["capabilities"] = _traits(result)
    return result


def suitable(method, record):
    """Conservative candidate hints, not a probability or a final model decision."""
    capabilities = record.get("capabilities") or _traits(record)
    specific = (
        "text"
        if method in TEXT_METHODS
        else "time"
        if method in SERIES_METHODS
        else "survival"
        if method in SURVIVAL_METHODS
        else {
            "series.panel": "panel",
            "series.moran": "spatial",
            "series.spatial": "spatial",
            "domain.meta": "meta",
            "domain.kano": "kano",
            "domain.nps": "nps",
            "domain.reliability": "survey",
        }.get(method)
    )
    if specific:
        return specific in capabilities
    item = catalog.BY_ID.get(method, {})
    if item.get("kind") in ("预测模型", "影响机制"):
        return record.get("task") in item.get("tasks", ()) and bool(record.get("target"))
    if method == "prep.balance":
        return record.get("task") == "classification"
    return True


def prepare(method, table, values):
    """Validate real roles before execution. Never substitute arbitrary numeric columns."""
    values = dict(values)
    names = list(table.raw.columns)
    if method == "domain.meta" or method in SURVIVAL_METHODS or method == "domain.kano":
        keys = (
            ("effect_column", "variance_column")
            if method == "domain.meta"
            else ("duration_column", "event_column")
            if method in SURVIVAL_METHODS
            else ("functional_item", "dysfunctional_item")
        )
        for key in keys:
            name = semantic_column(names, key, values.get(key))
            if not name:
                raise SelectionError(
                    f"{catalog.BY_ID[method]['label']}缺少明确的 {key}。需要{'、'.join(requirements(method))}，请查看字段后指定；没有合适数据时请说明限制或请求上传。",
                    "dataset_incompatible",
                )
            values[key] = name
        if values[keys[0]] == values[keys[1]]:
            raise SelectionError("两个分析角色不能使用同一列。", "dataset_incompatible")
    if method in TEXT_METHODS:
        column = values.get("text_column")
        if column and column not in names:
            raise SelectionError("指定的文本列不存在。", "invalid_column")
        if column and (
            pd.api.types.is_numeric_dtype(table.raw[column]) or column == table.time_name
        ):
            raise SelectionError(
                "文本分析需要文本内容，不能将数值或时间列当作文本。", "dataset_incompatible"
            )
        if not column and not any(
            not pd.api.types.is_numeric_dtype(table.raw[name])
            for name in names
            if name != table.time_name
        ):
            raise SelectionError(
                "该数据没有文本列，请选择评论/文本数据，或上传合适的数据。", "dataset_incompatible"
            )
    if method in SERIES_METHODS and not table.time_name:
        raise SelectionError(
            "该方法需要真实时间列，不能把普通横截面数据的行号当作时间。", "dataset_incompatible"
        )
    if method == "series.panel" and (not table.time_name or not table.group_name):
        raise SelectionError(
            "面板方法需要时间列与个体列，请选择面板数据或明确指定字段。", "dataset_incompatible"
        )
    if method == "domain.nps":
        target = values.get("score_column") or table.target_name
        if values.get("score_column") and target not in names:
            raise SelectionError("指定的推荐评分列不存在。", "invalid_column")
        if not target or (
            not values.get("score_column")
            and not any(part in target.lower() for part in ("nps", "recommend", "推荐"))
        ):
            raise SelectionError(
                "NPS 需要明确的推荐意愿评分目标列，请优先选择 nps_survey；不能用一般类别标签代替。",
                "dataset_incompatible",
            )
        scores = pd.to_numeric(table.raw[target], errors="coerce").dropna()
        if scores.empty or not scores.between(0, values.get("scale_max", 10)).all():
            raise SelectionError("推荐评分超出指定量表范围。", "dataset_incompatible")
    if method == "domain.reliability" and not values.get("columns"):
        items = [name for name in names if re.match(r"^(q\d+|item[_\d]|题项)", str(name), re.I)]
        if {"d", "x1", "x2", "x3", "x4", "x5", "x6"} <= set(names):
            items = [f"x{index}" for index in range(1, 7)]
        if len(items) < 2:
            raise SelectionError(
                "信度分析需要同一量表的多个题项，请显式指定 columns；不能把一般测量特征当成问卷。",
                "dataset_incompatible",
            )
        values["columns"] = items
    item = catalog.BY_ID.get(method, {})
    if item.get("kind") == "预测模型" and table.task not in item.get("tasks", ()):
        raise SelectionError(
            f"当前目标任务 {table.task} 与 {item['label']} 不匹配，请选择适合的数据或方法。",
            "dataset_incompatible",
        )
    return values


TOOL = {
    "type": "function",
    "function": {
        "name": "inspect_datasets",
        "description": "浏览当前账号可访问的内置/上传数据目录，或查看某份数据的真实字段、类型、缺失、取值范围及前5行。不运行实验，也不修改用户的手动指定。选择数据或字段前可先查看；目录可分页。",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "dataset": {
                    "type": "string",
                    "description": "指定时查看该数据详情，省略时列目录；使用目录中的真实ID。",
                },
                "method": {
                    "type": "string",
                    "enum": sorted(catalog.BY_ID),
                    "description": "可选，返回此方法的数据要求和候选提示。",
                },
                "offset": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30},
            },
        },
    },
}


def inspect_tool(arguments, project, data_access=None):
    if not isinstance(arguments, dict):
        raise SelectionError("数据查看参数格式无效。")
    method = arguments.get("method")
    if method and method not in catalog.BY_ID:
        raise SelectionError("请使用方法库中的真实方法ID。")
    if arguments.get("dataset"):
        result = inspect(project, arguments["dataset"], data_access)
        if method:
            result.update(requirements=requirements(method), suggested=suitable(method, result))
        return result
    offset, limit = arguments.get("offset", 0), arguments.get("limit", 30)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 30:
        raise SelectionError("目录分页参数无效。")
    records = inventory(project, data_access)
    if method:
        records.sort(key=lambda item: not suitable(method, item))
        records = [{**item, "suggested": suitable(method, item)} for item in records]
    end = offset + limit
    return {
        "datasets": records[offset:end],
        "total": len(records),
        "next_offset": end if end < len(records) else None,
        "requirements": requirements(method) if method else [],
        "note": "候选提示只依据可见字段；最终要核对业务含义。未配置上传数据可由模型在运行时显式指定 target/task/time/group，无需用户先手动选择。",
    }
