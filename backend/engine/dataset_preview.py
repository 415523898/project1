"""Read-only, bounded pages of the complete accessible source table."""

from functools import lru_cache
from pathlib import Path

import pandas as pd

from engine import account_datasets, datasets


@lru_cache(maxsize=48)
def _row_count(path, stamp, size):
    # A CSV record may contain embedded newlines; count parsed records, not lines.
    return sum(
        len(chunk)
        for chunk in pd.read_csv(
            path, usecols=[0], dtype=str, keep_default_na=False, chunksize=20000
        )
    )


def page(root, owner, project, source, offset=0, limit=50):
    if not isinstance(source, str):
        raise ValueError("请选择数据集。")
    if offset < 0 or not 1 <= limit <= 200:
        raise ValueError("页码无效；每次可读取 1–200 行。")
    iris = False
    if source.startswith("file:"):
        record = account_datasets.summary(root, owner, source[5:])
        path = account_datasets._asset(root, owner, source[5:]) / "table.csv"
        total = record["rows"]
        label, kind = record["name"], "upload"
        # Browsing is available before analysis-role configuration is confirmed.
        columns = record["column_names"]
    else:
        spec = datasets.DATASETS.get(source)
        if spec is None:
            raise ValueError("数据集不存在。")
        path = Path(project) / "data" / spec["file"]
        if not path.is_file():
            raise ValueError("这份内置数据尚未安装。")
        label, kind = spec["label"], "builtin"
        iris = spec["kind"] == "iris_metadata"
        if iris:
            total = int(pd.read_csv(path, header=None, nrows=1).iloc[0, 0])
            columns = [*spec["features"], "species"]
        else:
            stat = path.stat()
            total = _row_count(str(path), stat.st_mtime_ns, stat.st_size)
            columns = [str(column) for column in pd.read_csv(path, nrows=0).columns]
    values = []
    if offset < total:
        options = dict(dtype=str, keep_default_na=False, nrows=limit, skiprows=range(1, offset + 1))
        if iris:
            options.update(header=None, skiprows=offset + 1, usecols=range(len(columns)))
        frame = pd.read_csv(path, **options)
        values = frame.fillna("").values.tolist()
    return {
        "dataset": source,
        "label": label,
        "kind": kind,
        "column_names": columns,
        "total_rows": int(total),
        "offset": offset,
        "limit": limit,
        "rows": values,
    }
