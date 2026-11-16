import json
import math
import re
import threading
from pathlib import Path

from agent import corpus, eventlog
from config import (
    LEARNING_BLOCK_GAP_X as BLOCK_GAP_X,
)
from config import (
    LEARNING_BLOCK_GAP_Y as BLOCK_GAP_Y,
)
from config import (
    LEARNING_BLOCK_ROWS as BLOCK_ROWS,
)
from config import (
    LEARNING_NODE_GAP as NODE_GAP,
)
from config import (
    LEARNING_NODE_HEIGHT as NODE_HEIGHT,
)
from config import (
    LEARNING_NODE_WIDTH as NODE_WIDTH,
)
from config import (
    LEARNING_ROW_GAP as ROW_GAP,
)
from engine import catalog, registry

_METHODS_LOADED = False

LOAD_ERRORS = []


def load_methods():
    global _METHODS_LOADED
    if _METHODS_LOADED and registry.REGISTRY:
        return
    del LOAD_ERRORS[:]
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
        except Exception as error:
            LOAD_ERRORS.append(f"{layer}: {type(error).__name__}: {error}")
    _METHODS_LOADED = True


LAYOUT_FILE = "learning-layout.json"

MARKS_FILE = "learning-marks.json"

STUDYING_FILE = "learning-studying.json"

SAFE_KEY = re.compile(r"^[A-Za-z0-9_.-]{1,64}\Z")

_locks = {}

_guard = threading.Lock()


def _lock(path):
    with _guard:
        return _locks.setdefault(str(path), threading.Lock())


def auto_layout(nodes, target_aspect=1.45):
    if not nodes:
        return []
    order = []
    blocks = {}
    for index, node in enumerate(nodes):
        stage = node.get("stage") or "未分类"
        if stage not in blocks:
            blocks[stage] = []
            order.append(stage)
        blocks[stage].append(index)

    order.sort(key=lambda stage: -len(blocks[stage]))
    columns = {stage: max(1, int(math.ceil(len(blocks[stage]) / BLOCK_ROWS))) for stage in order}
    block_height = BLOCK_ROWS * ROW_GAP

    def layout(side):
        rows = [order[at : at + side] for at in range(0, len(order), side)]
        widest = 0
        for row in rows:
            used = sum(columns[stage] for stage in row)
            widest = max(widest, used * NODE_GAP + (len(row) - 1) * BLOCK_GAP_X)
        height = 30 + len(rows) * (block_height + BLOCK_GAP_Y)
        return 40 + widest + NODE_WIDTH + 40, height

    best_side = 1
    best_error = None
    for candidate in range(1, len(order) + 1):
        width, height = layout(candidate)
        error = abs(math.log((width / height) / target_aspect))
        if best_error is None or error < best_error:
            best_error = error
            best_side = candidate
    side = best_side

    spots = {}
    rows = [order[at : at + side] for at in range(0, len(order), side)]
    for row_index, row in enumerate(rows):
        cursor = 40
        for stage in row:
            for offset, index in enumerate(blocks[stage]):
                spots[index] = (
                    cursor + (offset // BLOCK_ROWS) * NODE_GAP,
                    30 + row_index * (block_height + BLOCK_GAP_Y) + (offset % BLOCK_ROWS) * ROW_GAP,
                )
            cursor += columns[stage] * NODE_GAP + BLOCK_GAP_X
    return [spots.get(index, (40 + index * NODE_GAP, 30)) for index in range(len(nodes))]


def method_title(method):
    for entry in corpus.CORPUS:
        if corpus.run_method(entry["id"]) == method:
            return entry.get("title") or method
    return method


def _slug(entry_id):
    return entry_id.replace(".", "-")


def curriculum_route():
    load_methods()
    entries = []
    for row in catalog.overview():
        previous_group = []
        for group in row["groups"]:
            current_group = []
            for method in group["methods"]:
                node = {
                    "id": method["id"],
                    "key": _slug(method["id"]),
                    "title": method["label"],
                    "capability": method["category"],
                    "tasks": method["tasks"],
                    "run_method": method["id"] if registry.implemented(method["id"]) else None,
                    "level": len(entries),
                    "stage": row["name"],
                    "group": group["name"],
                    "requires": list(previous_group),
                    "why": method["note"],
                    "runnable": method["runnable"],
                    "missing": method["missing"],
                    "trackable": _trackable(method["id"]),
                }
                entries.append(node)
                current_group.append(node["id"])
            previous_group = current_group
    return entries


def _layout_path(root, owner):
    return Path(root) / owner / LAYOUT_FILE


def _marks_path(root, owner):
    return Path(root) / owner / MARKS_FILE


def _studying_path(root, owner):
    return Path(root) / owner / STUDYING_FILE


def _read(path, default):
    if not path.is_file():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return value if isinstance(value, type(default)) else default


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(path)


def _trackable(method_id):
    category = catalog.category_of(method_id)
    return category in ("ml", "model", "series", "causal", "domain", "evaluate")


def route_stages(nodes):
    stages = []
    seen = set()
    for node in nodes:
        name = node.get("stage")
        if name and name not in seen:
            seen.add(name)
            stages.append(name)
    if not stages:
        return [{"name": row["name"], "hint": row["hint"]} for row in catalog.overview()]
    hints = {row["name"]: row["hint"] for row in catalog.overview()}
    return [{"name": name, "hint": hints.get(name, "")} for name in stages]


def _project_nodes(root, owner, stored_nodes):
    nodes = [dict(node) for node in stored_nodes]
    layout = _read(_layout_path(root, owner), {})
    marks = _read(_marks_path(root, owner), {})
    finished, attempted = progress(root, owner)
    spots = auto_layout(nodes)
    studying_keys = set(studying(root, owner)) | bound_methods(root, owner)
    for index, node in enumerate(nodes):
        method = node.get("run_method")
        if "id" not in node:
            node["id"] = node["key"]
        node["studying"] = bool(node.get("key") in studying_keys or node.get("id") in studying_keys)
        if node["key"] in marks or node["id"] in marks:
            node["status"] = "done"
            node["manual"] = True
        elif method and method in finished:
            node["status"] = "done"
        elif method and method in attempted:
            node["status"] = "tried"
        elif not _unlocked(nodes, node, finished, marks):
            node["status"] = "locked"
        else:
            node["status"] = "todo"
        placed = layout.get(node["key"]) or layout.get(node["id"])
        if isinstance(placed, dict) and "x" in placed and "y" in placed:
            node["x"], node["y"] = placed["x"], placed["y"]
        else:
            node["x"], node["y"] = spots[index]
        node["stage"] = node.get("stage") or "课程表路线"
    edges = []
    for node in nodes:
        for need in node.get("requires") or []:
            edges.append({"from": _slug(need), "to": node["key"]})
    counts = {"done": 0, "todo": 0, "locked": 0, "tried": 0}
    for node in nodes:
        counts[node["status"]] = counts.get(node["status"], 0) + 1
    ordered = sorted(nodes, key=lambda item: (item.get("level", 0), item.get("key", "")))
    return {
        "mode": "curriculum",
        "nodes": nodes,
        "edges": edges,
        "card": {"width": NODE_WIDTH, "height": NODE_HEIGHT},
        "stages": route_stages(nodes),
        "progress": counts,
        "total": len(nodes),
        "conversations": 0,
        "next": next(
            (node["key"] for node in ordered if node["status"] in ("todo", "tried")), None
        ),
    }


def clear_progress(root, owner):
    for path in (_marks_path(root, owner), _studying_path(root, owner)):
        with _lock(path):
            if path.is_file():
                path.unlink()
    return True


def studying(root, owner):
    rows = _read(_studying_path(root, owner), {})
    return (
        {str(key): True for key, value in rows.items() if value} if isinstance(rows, dict) else {}
    )


def bound_methods(root, owner):
    """A confirmed binding means the method is being studied now.

    The state is derived from the live binding instead of being copied into the
    marks file, so deleting the card, the session or the binding restores the
    unlearned/still-studying state without a second write to keep in sync.
    """
    from agent import study_binding, study_store

    bindings = study_binding.all_bindings(root, owner)
    if not bindings:
        return set()
    with study_store.connection(root, owner) as db:
        cards = {row[0] for row in db.execute("SELECT card_id FROM cards")}
    return {
        value["method_id"]
        for value in bindings.values()
        if value.get("method_id")
        and value.get("card_id") in cards
        and eventlog.SessionLog(root, owner, value["session_id"]).exists()
    }


def mark_studying(root, owner, key, active):
    if not isinstance(key, str) or not SAFE_KEY.match(key):
        raise ValueError("节点标识无效。")
    path = _studying_path(root, owner)
    with _lock(path):
        rows = _read(path, {})
        rows = dict(rows) if isinstance(rows, dict) else {}
        if active:
            rows[key] = True
        else:
            rows.pop(key, None)
        _write(path, rows)
    return rows


def mark(root, owner, key, done):
    if not isinstance(key, str) or not SAFE_KEY.match(key):
        raise ValueError("节点标识无效。")
    path = _marks_path(root, owner)
    with _lock(path):
        marks = _read(path, {})
        if done:
            marks[key] = True
        else:
            marks.pop(key, None)
        _write(path, marks)
    if done:
        mark_studying(root, owner, key, False)
    return marks


def progress(root, owner):
    finished = set()
    attempted = {}
    for path in eventlog.log_paths(root, owner):
        log = eventlog.SessionLog(root, owner, path.stem, path)
        try:
            events = log.events()
        except eventlog.LogError:
            continue
        for event in events:
            if event.get("kind") != "tool/result":
                continue
            result = event.get("result")
            if not isinstance(result, dict):
                continue
            methods = result.get("methods")
            if not isinstance(methods, dict):
                continue
            for method, payload in methods.items():
                if not isinstance(payload, dict):
                    continue
                failed = bool(payload.get("error")) or payload.get("status") == "error"
                if failed:
                    attempted.setdefault(method, True)
                else:
                    finished.add(method)
                    attempted.pop(method, None)
    return finished, attempted


def project_curriculum(root, owner):
    return _project_nodes(root, owner, curriculum_route())


def _unlocked(nodes, node, finished, marks=None):
    marks = marks or {}
    requires = [need for need in (node.get("requires") or []) if need]
    if not requires:
        return True
    index = {}
    for item in nodes:
        index[item.get("id")] = item
        index[item.get("key")] = item
    for need in requires:
        if need in marks:
            continue
        target = index.get(need)
        if target is None:
            continue
        if target.get("key") in marks or target.get("id") in marks:
            continue
        if not target.get("trackable", True):
            continue
        method = target.get("run_method")
        if method and method not in finished:
            return False
    return True
