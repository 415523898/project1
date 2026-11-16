import io
import json
import re
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from engine import harmonize, tabular

SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}\Z")
SUFFIXES = (".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls")
MAX_ROWS = None
MAX_COLUMNS = None
HEAD_ROWS = 5
TARGET_NAMES = (
    "target",
    "label",
    "class",
    "y",
    "outcome",
    "标签",
    "目标",
    "目标列",
    "类别",
    "结果",
)


class UploadError(ValueError):
    pass


def directory(root, session_id):
    if not isinstance(session_id, str) or not SAFE.match(session_id):
        raise UploadError("对话编号无效。")
    return Path(root) / "data" / "uploads" / session_id


def _text(blob):
    for encoding in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            return blob.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UploadError("文件编码无法识别，请另存为 UTF-8 或 GBK。")


def _frame(name, blob):
    suffix = Path(name).suffix.lower()
    if suffix not in SUFFIXES:
        raise UploadError("只支持 csv、tsv、txt、xlsx、xls 表格文件。")
    try:
        if suffix in (".xlsx", ".xlsm", ".xls"):
            frame = pd.read_excel(io.BytesIO(blob), sheet_name=0)
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                raise UploadError("表格是空的。")
        else:
            result = harmonize.harmonize(
                blob, name=Path(name).name, dedupe=False, drop_empty_columns=False
            )
            frame = result.frame
    except harmonize.HarmonizeInputError as error:
        raise UploadError(str(error)) from error
    except tabular.InputError as error:
        raise UploadError(str(error)) from error
    except (ValueError, OSError, ImportError, UnicodeError) as error:
        raise UploadError(f"表格读取失败：{error}") from error
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise UploadError("表格是空的。")
    frame.columns = [
        str(name).strip() or f"列{index + 1}" for index, name in enumerate(frame.columns)
    ]
    frame.columns = harmonize.clean_column_names(list(frame.columns))[0]
    if frame.empty:
        raise UploadError("表格至少需要一行数据和一列内容。")
    if MAX_COLUMNS is not None and frame.shape[1] > MAX_COLUMNS:
        raise UploadError(f"列数超过上限 {MAX_COLUMNS}。")
    if MAX_ROWS is not None and frame.shape[0] > MAX_ROWS:
        raise UploadError(f"行数超过上限 {MAX_ROWS}。")
    return frame.reset_index(drop=True)


def _numeric(series):
    try:
        pd.to_numeric(series, errors="raise")
    except (ValueError, TypeError):
        return False
    return True


def guess_target(frame):
    columns = [name for name in frame.columns if not str(name).endswith(harmonize.RAW_SUFFIX)]
    if not columns:
        columns = list(frame.columns)
    lowered = {str(name).strip().lower(): name for name in columns}
    for candidate in TARGET_NAMES:
        if candidate in lowered:
            return lowered[candidate]
    return columns[-1]


def _dtype(series):
    if _numeric(series):
        return "number"
    return "text"


def _json_safe(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return round(float(value), 6)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _head(frame):
    rows = []
    for _, row in frame.head(HEAD_ROWS).iterrows():
        rows.append(
            [
                _json_safe(value) if not isinstance(value, float) or np.isfinite(value) else None
                for value in row.tolist()
            ]
        )
    return rows


def _summary(file_id, name, frame, target, saved_at):
    return {
        "id": file_id,
        "name": name,
        "dataset": f"file:{file_id}",
        "rows": int(frame.shape[0]),
        "columns": int(frame.shape[1]),
        "column_names": [str(value) for value in frame.columns],
        "dtypes": {str(value): _dtype(frame[value]) for value in frame.columns},
        "target": target,
        "task": tabular.infer_task(frame[target]) if target else "clustering",
        "head": _head(frame),
        "saved_at": saved_at,
    }


def save(root, session_id, name, blob):
    if not isinstance(blob, (bytes, bytearray)) or not blob:
        raise UploadError("没有收到文件。")
    clean = Path(str(name or "table.csv")).name
    if not clean:
        clean = "table.csv"
    frame = _frame(clean, bytes(blob))
    target = guess_target(frame)
    file_id = uuid.uuid4().hex[:12]
    folder = directory(root, session_id)
    folder.mkdir(parents=True, exist_ok=True)
    saved_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    frame.to_csv(folder / f"{file_id}.csv", index=False, encoding="utf-8")
    summary = _summary(file_id, clean, frame, target, saved_at)
    (folder / f"{file_id}.json").write_text(
        json.dumps(summary, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def listing(root, session_id):
    folder = directory(root, session_id)
    if not folder.is_dir():
        return []
    items = []
    for path in sorted(folder.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and record.get("id"):
            items.append(record)
    items.sort(key=lambda item: item.get("saved_at") or "")
    return items


def summary_of(root, session_id, file_id):
    if not isinstance(file_id, str) or not SAFE.match(file_id):
        raise UploadError("文件编号无效。")
    path = directory(root, session_id) / f"{file_id}.json"
    if not path.is_file():
        raise UploadError("这个对话里没有这个文件。")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise UploadError("文件记录不可读。") from error
    if not isinstance(record, dict):
        raise UploadError("文件记录不可读。")
    return record


def drop(root, session_id, file_id):
    record = summary_of(root, session_id, file_id)
    folder = directory(root, session_id)
    for suffix in (".json", ".csv"):
        path = folder / f"{file_id}{suffix}"
        if path.is_file():
            path.unlink()
    return {"deleted": record.get("id"), "name": record.get("name")}


def frame_of(root, session_id, file_id):
    summary_of(root, session_id, file_id)
    path = directory(root, session_id) / f"{file_id}.csv"
    if not path.is_file():
        raise UploadError("文件内容已不存在。")
    try:
        return pd.read_csv(path)
    except (ValueError, OSError) as error:
        raise UploadError(f"文件内容读取失败：{error}") from error


def bundle(root, session_id, file_id, target=None, task=None):
    record = summary_of(root, session_id, file_id)
    frame = frame_of(root, session_id, file_id)
    chosen = target if isinstance(target, str) and target in frame.columns else record.get("target")
    if chosen not in frame.columns:
        chosen = None
    try:
        table = tabular.build(frame, target=chosen, task=task)
    except tabular.InputError as error:
        raise UploadError(str(error)) from error
    matrix = table.matrix()
    values = table.numeric_target()
    classes = []
    if table.task == "classification":
        labels = table.labels()
        if labels is not None:
            classes = sorted({str(value) for value in labels})
    return {
        "X": matrix,
        "y": values,
        "feature_names": list(table.feature_names),
        "target_name": table.target_name or "target",
        "task": table.task or "clustering",
        "class_names": classes,
        "excluded_columns": [],
        "dataset": f"file:{file_id}",
        "label": f"会话文件 {record.get('name')}",
        "notes": list(table.notes),
    }
