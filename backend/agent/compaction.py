import copy
import json
import os
import threading
from pathlib import Path

from config import (
    COMPACTION_HEAD_CHARS as HEAD_CHARS,
)
from config import (
    COMPACTION_TAIL_CHARS as TAIL_CHARS,
)
from config import (
    COMPACTION_THRESHOLD_CHARS as THRESHOLD_CHARS,
)

MARKER = "\n\n...（中间内容已裁剪）...\n\n"
PRUNED_KEY = "text"
SIZE_KEY = "chars"

_locks = {}
_guard = threading.Lock()


def needs_trim(text):
    return isinstance(text, str) and len(text) > THRESHOLD_CHARS


def trim(text):
    if not needs_trim(text):
        return text
    head = text[:HEAD_CHARS]
    tail = text[-TAIL_CHARS:]
    return head + MARKER + tail


def _prune_value(value):
    if not isinstance(value, dict):
        return value, 0
    saved = 0
    pruned = dict(value)
    for key in list(pruned):
        text = pruned[key]
        if needs_trim(text):
            pruned[key] = trim(text)
            pruned[PRUNED_KEY + "_" + key] = len(text)
            saved += len(text) - len(pruned[key])
    return pruned, saved


def context_view(events):
    """Derived model input only; source events and persisted logs stay intact."""
    result = copy.deepcopy(events)
    for event in result:
        if isinstance(event.get("result"), dict):
            event["result"], _ = _prune_value(event["result"])
        for key, value in list(event.items()):
            if key not in {"text", "result"} and needs_trim(value):
                event[key] = trim(value)
    return result


def compact(path):
    path = Path(path)
    if not path.is_file():
        return 0
    with _guard:
        lock = _locks.setdefault(str(path), threading.Lock())
    with lock:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            return 0
        lines = [line for line in raw.split("\n") if line.strip()]
        changed = False
        total_saved = 0
        rebuilt = []
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                rebuilt.append(line)
                continue
            if not isinstance(event, dict):
                rebuilt.append(line)
                continue
            saved = 0
            payload, trimmed = _prune_value(event.get("result"))
            if trimmed:
                event["result"] = payload
                event["pruned"] = event.get("pruned", 0) + trimmed
                saved += trimmed
                changed = True
            for key in list(event):
                if key == "result" or key in ("text", "pruned"):
                    continue
                text = event[key]
                if needs_trim(text):
                    event[key] = trim(text)
                    event["pruned"] = event.get("pruned", 0) + (len(text) - len(event[key]))
                    saved += len(text) - len(event[key])
                    changed = True
            total_saved += saved
            rebuilt.append(json.dumps(event, ensure_ascii=False, allow_nan=False))
        if not changed:
            return 0
        temporary = path.with_suffix(".compact")
        try:
            temporary.write_text("\n".join(rebuilt) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return 0
        return total_saved
