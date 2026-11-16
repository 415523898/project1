"""Account-owned table assets and conversation source selections.

The authenticated owner and storage root are supplied by server code, never JSON.
"""

import hashlib
import json
import re
import shutil
import time
import uuid
from pathlib import Path

import pandas as pd

from agent.atomic_json import write_json as _write
from engine import datasets, tabular, uploads

ID = re.compile(r"^[a-f0-9]{12,32}\Z")
SESSION = re.compile(r"^[A-Za-z0-9_-]{6,64}\Z")
TASKS = {"classification", "regression", "clustering"}


def directory(root, owner):
    base = Path(root).resolve()
    if not isinstance(owner, str) or not owner or Path(owner).name != owner or owner in (".", ".."):
        raise ValueError("账号无效。")
    folder = (base / owner / "datasets").resolve()
    if not folder.is_relative_to(base):
        raise ValueError("账号目录无效。")
    return folder


def _asset(root, owner, file_id):
    if not isinstance(file_id, str) or not ID.fullmatch(file_id):
        raise ValueError("数据编号无效。")
    return directory(root, owner) / file_id


def summary(root, owner, file_id):
    path = _asset(root, owner, file_id) / "metadata.json"
    if not path.is_file():
        raise ValueError("当前账号中没有这份数据。")
    return json.loads(path.read_text(encoding="utf-8"))


def frame(root, owner, file_id):
    record = summary(root, owner, file_id)
    # Preserve identifiers such as 001 and original text, including the string NA.
    types = {key: "string" for key, value in record["dtypes"].items() if value == "text"}
    return pd.read_csv(
        _asset(root, owner, file_id) / "table.csv",
        dtype=types,
        keep_default_na=False,
        na_values=[""],
    )


def _auto_label(clean, table, existing):
    """Readable default name: file stem, else column names; keep labels unique."""
    stem = re.sub(r"[_\-.]+", " ", Path(clean).stem).strip()
    stem = re.sub(r"\s+", " ", stem)
    generic = {
        "data",
        "dataset",
        "datasets",
        "table",
        "sheet",
        "export",
        "upload",
        "file",
        "tmp",
        "temp",
        "book",
        "数据",
        "数据集",
        "表格",
        "工作簿",
    }
    if len(stem) < 2 or stem.casefold() in generic:
        columns = [str(name).strip() for name in table.columns[:3] if str(name).strip()]
        stem = ("、".join(columns) + " 数据") if columns else "上传数据"
    label = stem[:60]
    taken = {str(item.get("label") or "") for item in existing}
    base, index = label, 2
    while label in taken:
        label = f"{base} ({index})"
        index += 1
    return label


def save(root, owner, name, blob):
    if not blob:
        raise ValueError("请选择非空文件。")
    clean = str(name or "table.csv").replace("\\", "/").rsplit("/", 1)[-1][:180]
    table = uploads._frame(clean, blob)
    digest = hashlib.sha256(bytes(blob)).hexdigest()
    existing = listing(root, owner)
    for item in existing:
        # Re-uploading the same bytes must not create a duplicate dataset entry.
        if item.get("sha256") == digest and item.get("size") == len(blob):
            return item
    file_id = uuid.uuid4().hex
    record = uploads._summary(file_id, clean, table, None, time.strftime("%Y-%m-%dT%H:%M:%S"))
    record.update(
        kind="upload",
        label=_auto_label(clean, table, existing),
        source_name=clean,
        sha256=digest,
        size=len(blob),
        time=None,
        group=None,
        configured=False,
        suggested_target=uploads.guess_target(table) if len(table.columns) > 1 else None,
    )
    folder = _asset(root, owner, file_id)
    folder.mkdir(parents=True)
    try:
        (folder / ("original" + Path(clean).suffix.lower())).write_bytes(blob)
        table.to_csv(folder / "table.csv", index=False, encoding="utf-8")
        _write(folder / "metadata.json", record)
    except Exception:
        shutil.rmtree(folder)
        raise
    return record


def _forget_dataset(root, owner, dataset):
    base = directory(root, owner).parent
    for folder in ("dataset_selections", "automatic_datasets"):
        for path in (base / folder).glob("*.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(value, dict) and value.get("dataset") == dataset:
                path.unlink(missing_ok=True)


def delete(root, owner, file_id):
    record = summary(root, owner, file_id)
    folder = _asset(root, owner, file_id)
    shutil.rmtree(folder)
    _forget_dataset(root, owner, record["dataset"])
    return {"deleted": file_id, "label": record.get("label") or record.get("name") or file_id}


def configure(root, owner, file_id, values):
    record = summary(root, owner, file_id)
    columns = record["column_names"]
    fields = {key: values.get(key) or None for key in ("target", "time", "group")}
    for key, name in fields.items():
        if name is not None and (not isinstance(name, str) or name not in columns):
            raise ValueError(f"{key} 列不在这份数据中。")
    chosen = [value for value in fields.values() if value]
    if len(set(chosen)) != len(chosen):
        raise ValueError("目标、时间和分组需要选择不同的列。")
    task = values.get("task") or (
        "clustering"
        if not fields["target"]
        else tabular.infer_task(frame(root, owner, file_id)[fields["target"]])
    )
    if task not in TASKS:
        raise ValueError("请选择分类、回归或无目标分析。")
    if task != "clustering" and not fields["target"]:
        raise ValueError("分类和回归需要指定目标列；描述统计、文本或聚类可选择无目标分析。")
    if task == "clustering" and fields["target"]:
        raise ValueError("无目标分析无需目标列。")
    if task == "regression" and not pd.api.types.is_numeric_dtype(
        frame(root, owner, file_id)[fields["target"]]
    ):
        raise ValueError("回归的目标列需要是数值。")
    record.update(**fields, task=task, configured=True)
    _write(_asset(root, owner, file_id) / "metadata.json", record)
    return record


def listing(root, owner):
    folder = directory(root, owner)
    records = []
    for path in folder.glob("*/metadata.json"):
        try:
            records.append(summary(root, owner, path.parent.name))
        except (ValueError, OSError):
            continue
    return sorted(records, key=lambda item: item["saved_at"], reverse=True)


def import_legacy(root, owner, project):
    """Copy only uploads whose conversation log belongs to this account."""
    sessions = Path(root) / owner / "sessions"
    for log in sessions.glob("**/*.jsonl"):
        if not SESSION.fullmatch(log.stem):
            continue
        folder = Path(project) / "data" / "uploads" / log.stem
        for path in folder.glob("*.json"):
            if not ID.fullmatch(path.stem) or not path.with_suffix(".csv").is_file():
                continue
            destination = _asset(root, owner, path.stem)
            if (destination / "metadata.json").is_file():
                continue
            record = uploads.summary_of(project, log.stem, path.stem)
            record.update(
                kind="upload", label=record["name"], configured=True, time=None, group=None
            )
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path.with_suffix(".csv"), destination / "table.csv")
            _write(destination / "metadata.json", record)


def builtins(project):
    return [
        {
            "id": key,
            "dataset": key,
            "label": item["label"],
            "kind": "builtin",
            "task": item["task"],
            "target": item.get("target", "species" if key == "iris" else None),
            "time": item.get("time_column"),
            "group": item.get("group_column"),
        }
        for key, item in datasets.DATASETS.items()
        if (Path(project) / "data" / item["file"]).is_file()
    ]


def resolve(root, owner, project, source):
    if not isinstance(source, str):
        raise ValueError("请选择数据集。")
    if source.startswith("file:"):
        record = summary(root, owner, source[5:])
        if not record.get("configured"):
            raise ValueError("请先确认这份数据的任务与目标列。")
        return record
    for record in builtins(project):
        if record["dataset"] == source:
            return record
    raise ValueError("数据集不存在。")


def _selection_path(root, owner, session):
    if not isinstance(session, str) or not SESSION.fullmatch(session):
        raise ValueError("会话编号无效。")
    return directory(root, owner).parent / "dataset_selections" / (session + ".json")


def select(root, owner, project, session, source):
    path = _selection_path(root, owner, session)
    if source is None:
        _write(path, None)
        return None
    record = resolve(root, owner, project, source)
    # Snapshot the role configuration: editing a library item must not change old conversations.
    _write(path, record)
    return record


def selection(root, owner, session):
    path = _selection_path(root, owner, session)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def restore_selection(root, owner, session, snapshot):
    """Copy a historical role snapshot without resolving today's library settings."""
    _write(_selection_path(root, owner, session), snapshot)


def current_info(root, owner, project, session):
    """Show the real selected/last successfully used source; this never makes a selection."""
    from agent import eventlog
    from engine import dataset_selection

    selected = selection(root, owner, session)
    record = selected or automatic(root, owner, session)
    if not record:
        for event in reversed(eventlog.Store(root, owner).get(session)["events"]):
            result = event.get("result")
            if (
                event["kind"] == "tool/result"
                and isinstance(result, dict)
                and result.get("methods")
                and result.get("dataset")
            ):
                record = {
                    "dataset": result["dataset"],
                    **{
                        key: value
                        for key, value in (result.get("data") or {}).items()
                        if key in ("task", "target", "time", "group")
                    },
                }
                break
    if not record:
        return None
    profile = dataset_selection.inspect(project, record["dataset"], (root, owner))
    profile["task"] = record.get("task") or profile.get("task")
    for role in ("target", "time", "group"):
        profile[role] = record.get(role, profile.get(role))
    descriptions = {
        "iris": "记录鸢尾花的花萼、花瓣测量特征及类别标签，可用于分类、聚类和描述性分析。",
        "breast_cancer": "包含细胞核的测量特征与乳腺癌诊断标签，可用于二分类、模型比较与特征分析。",
        "wine": "包含葡萄酒的化学测量指标与类别标签，可用于分类、聚类和降维分析。",
    }
    profile["description"] = descriptions.get(
        record["dataset"],
        "这是当前账号上传的表格，可根据下方字段和任务配置选择分析方法。"
        if profile.get("kind") == "upload"
        else "这份内置数据可用于学习和复现实验，下方展示数据规模、任务、字段及样本。",
    )
    return {
        "selection_mode": "manual" if selected else "auto",
        "dataset": profile,
        "reason": record.get("reason", ""),
        "notes": profile.get(
            "notes", ["这里展示原始数据概况；实验使用的清洗后样本量以实验结果为准。"]
        ),
    }


def context(root, owner, project, session, snapshot):
    from engine import dataset_selection

    result = dict(snapshot) if isinstance(snapshot, dict) else {}
    result.pop("selected_dataset", None)
    result.pop("dataset_policy", None)
    result.pop("dataset_catalog", None)
    result.pop("automatic_dataset", None)
    remembered = automatic(root, owner, session)
    result["dataset_policy"] = {
        "mode": "auto",
        "note": "模型根据问题和方法选择合适数据；继续同一分析时优先沿用上次数据，不适合时说明换用原因。手动指定是可选覆盖。",
    }
    if remembered:
        result["automatic_dataset"] = remembered
    records = dataset_selection.inventory(project, (root, owner))
    compact = [
        {
            **{key: value for key, value in item.items() if key not in ("dtypes", "column_names")},
            "column_names": item.get("column_names", [])[:12],
            "columns_truncated": len(item.get("column_names", [])) > 12,
        }
        for item in records[:30]
    ]
    result["dataset_catalog"] = {
        "datasets": compact,
        "total": len(records),
        "next_offset": 30 if len(records) > 30 else None,
        "note": "字段不完整或需看样本时调用 inspect_datasets；可继续分页查看目录。",
    }
    record = selection(root, owner, session)
    if record:
        resolve(root, owner, project, record["dataset"])
        result.pop("data_version", None)
        result.update(
            selected_dataset=record,
            dataset=record["dataset"],
            task=record["task"],
            target=record.get("target"),
            time=record.get("time"),
            group=record.get("group"),
        )
        result["draft"] = {**result.get("draft", {}), "dataset": record["dataset"]}
        result["files"] = [record] if record["kind"] == "upload" else []
        result["dataset_policy"]["mode"] = "manual"
    else:
        result["files"] = []
        result["draft"] = {
            key: value for key, value in result.get("draft", {}).items() if key != "dataset"
        }
        for key in ("dataset", "task", "target", "time", "group"):
            result.pop(key, None)
    return result


def forget_selection(root, owner, session):
    _selection_path(root, owner, session).unlink(missing_ok=True)
    _automatic_path(root, owner, session).unlink(missing_ok=True)


def _automatic_path(root, owner, session):
    return (
        _selection_path(root, owner, session).parent.parent
        / "automatic_datasets"
        / (session + ".json")
    )


def automatic(root, owner, session):
    path = _automatic_path(root, owner, session)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def remember_automatic(root, owner, session, result):
    """Remember successful real runs only; never turn an AI choice into a manual lock."""
    if not session or not result.get("methods") or not result.get("dataset"):
        return
    data = result.get("data") or {}
    roles = {key: data.get(key) for key in ("target", "task", "time", "group")}
    _write(
        _automatic_path(root, owner, session),
        {
            "dataset": result["dataset"],
            "label": result.get("dataset_label"),
            **roles,
            "methods": list(result["methods"]),
            "reason": result.get("reason"),
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    )


def bundle(root, owner, file_id, roles=None, allow_unconfigured=False):
    record = summary(root, owner, file_id)
    if not record.get("configured") and not allow_unconfigured:
        raise ValueError("请先确认任务与目标列，或由模型查看字段后在实验调用中指定。")
    roles = record if roles is None else roles
    chosen = [roles.get(key) for key in ("target", "time", "group") if roles.get(key)]
    if len(chosen) != len(set(chosen)):
        raise ValueError("目标、时间和分组需要选择不同的列。")
    source = frame(root, owner, file_id)
    target = roles.get("target")
    if (
        target
        and target in source
        and roles.get("task") == "regression"
        and not pd.api.types.is_numeric_dtype(source[target])
    ):
        raise ValueError("回归目标列需要是数值，不能把文本标签编码后当作连续目标。")
    table = tabular.build(
        source,
        target=target,
        task=roles.get("task"),
        time=roles.get("time"),
        group=roles.get("group"),
    )
    return {
        "X": table.matrix(),
        "y": table.numeric_target(),
        "table": table,
        "feature_names": table.feature_names,
        "target_name": table.target_name,
        "task": table.task,
        "class_names": [],
        "dataset": record["dataset"],
        "label": record["name"],
        "notes": table.notes,
    }
