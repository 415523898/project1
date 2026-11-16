"""Strict JSON replacement for dataset, attachment and experiment metadata.

Callers own path authorization, locks and revision changes. Account credentials
use private_files.write_json instead, which also enforces private modes/fsync.
"""

import json
import uuid
from pathlib import Path


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
