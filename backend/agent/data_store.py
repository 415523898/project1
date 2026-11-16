import hashlib
import json
import math
import threading
import time

from config import (
    DATA_STORE_MAX_CLASSES as MAX_CLASSES,
)
from config import (
    DATA_STORE_MAX_FEATURES as MAX_FEATURES,
)
from config import (
    DATA_STORE_MAX_POINTS as MAX_POINTS,
)
from config import (
    DATA_STORE_MAX_TTL_SECONDS as MAX_TTL_SECONDS,
)
from config import DATA_STORE_MAX_VERSIONS as MAX_VERSIONS


class DataStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.items = {}

    @staticmethod
    def fingerprint(payload):
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

    def prune(self):
        now = time.monotonic()
        expired = [
            key for key, value in self.items.items() if now - value["stored_at"] > MAX_TTL_SECONDS
        ]
        for key in expired:
            self.items.pop(key, None)

    def put(self, version, payload):
        self.validate(version, payload)
        with self.lock:
            self.prune()
            if len(self.items) >= MAX_VERSIONS and version not in self.items:
                oldest = min(self.items, key=lambda key: self.items[key]["stored_at"])
                self.items.pop(oldest, None)
            self.items[version] = {
                "stored_at": time.monotonic(),
                "data": payload,
                "shape": self.shape(payload),
            }
            return self.items[version]["shape"]

    def get(self, version):
        with self.lock:
            self.prune()
            item = self.items.get(version)
            return item["data"] if item else None

    def require(self, version):
        data = self.get(version)
        if data is None:
            raise ValueError("本轮确认数据已不在服务端内存中，请重新确认数据后再试。")
        return data

    def has(self, version):
        return self.get(version) is not None

    @staticmethod
    def shape(payload):
        split = payload.get("split") or {}
        x = payload.get("X") or []
        return {
            "records": len(x),
            "features": len(x[0]) if x else 0,
            "classes": len(payload.get("class_names") or []),
            "task": payload.get("task"),
            "split": {name: len(split.get(name) or []) for name in ("train", "validation", "test")},
            "version": payload.get("version"),
        }

    @staticmethod
    def forest_view(payload):
        x = payload.get("X") or []
        if len(x) and len(x[0]) != 2:
            return None
        if len(payload.get("class_names") or []) not in (0, 2):
            return None
        forest = payload.get("forest")
        return forest if isinstance(forest, dict) else None

    @staticmethod
    def validate(version, payload):
        if not isinstance(version, str) or not 1 <= len(version) <= 200:
            raise ValueError("数据版本号无效。")
        if not isinstance(payload, dict):
            raise ValueError("数据格式无效。")
        if payload.get("version") != version:
            raise ValueError("数据版本号与内容不一致。")
        x, y, split = payload.get("X"), payload.get("y"), payload.get("split") or {}
        train, test = split.get("train") or [], split.get("test") or []
        if not isinstance(x, list) or not x:
            raise ValueError("数据矩阵无效。")
        if MAX_POINTS is not None and len(x) > MAX_POINTS:
            raise ValueError(f"数据矩阵无效或过大（最多 {MAX_POINTS} 行）。")
        width = len(x[0]) if isinstance(x[0], list) else 0
        if width < 1:
            raise ValueError("特征数量必须在 1 以上。")
        if MAX_FEATURES is not None and width > MAX_FEATURES:
            raise ValueError(f"特征数量必须在 1 到 {MAX_FEATURES} 之间。")
        for row in x:
            if not isinstance(row, list) or len(row) != width:
                raise ValueError("特征矩阵每行长度必须一致。")
            if any(
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                for value in row
            ):
                raise ValueError("特征矩阵只能包含有限数值。")
        if not isinstance(y, list) or len(y) != len(x):
            raise ValueError("目标列长度必须与特征矩阵一致。")
        values = [float(value) for value in y]
        if any(not math.isfinite(value) for value in values):
            raise ValueError("目标列只能包含有限数值。")
        class_names = payload.get("class_names") or []
        if class_names:
            if not isinstance(class_names, list) or len(class_names) > MAX_CLASSES:
                raise ValueError("类别名无效。")
            allowed = set(range(len(class_names)))
            if (
                any(not value.is_integer() for value in values)
                or {int(value) for value in values} - allowed
            ):
                raise ValueError("目标取值与类别名不匹配。")
        indices = list(train) + list(split.get("validation") or []) + list(test)
        if len(indices) != len(x) or len(set(indices)) != len(indices):
            raise ValueError("划分索引无效。")
        if any(
            not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(x)
            for index in indices
        ):
            raise ValueError("划分索引无效。")
        if not train or not test:
            raise ValueError("训练集与测试集不能为空。")
        return True


STORE = DataStore()
