"""Account-owned sidebar experiments, immutable rerun versions and model evidence."""

import copy
import hashlib
import json
import os
import threading
from pathlib import Path

from agent import eventlog
from agent.atomic_json import write_json
from engine import catalog, datasets, report

_guard = threading.Lock()
_locks = {}


def _path(root, owner, session):
    if not isinstance(owner, str) or Path(owner).name != owner or owner in ("", ".", ".."):
        raise ValueError("账号无效。")
    if not isinstance(session, str) or not eventlog.SESSION_ID.fullmatch(session):
        raise ValueError("会话编号无效。")
    return Path(root) / owner / "experiments" / (session + ".json")


def _lock(path):
    with _guard:
        key = str(path.resolve())
        if os.name == "nt":
            # realpath can retain the extended prefix while an atomic replace
            # races with its existence check. Both spellings need one lock.
            if key[:8].upper() == "\\\\?\\UNC\\":
                key = "\\\\" + key[8:]
            else:
                key = key.removeprefix("\\\\?\\")
            key = os.path.normcase(key)
        return _locks.setdefault(key, threading.RLock())


def _load(path):
    if not path.is_file():
        return {"schema": 1, "revision": 0, "selected_id": None, "experiments": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("experiments"), list):
        raise ValueError("实验记录损坏，请保留文件并检查服务器日志。")
    return value


def _write(path, value):
    value["revision"] += 1
    write_json(path, value)


def _item(state, identifier):
    item = next(
        (
            item
            for item in state["experiments"]
            if item["id"] == identifier and not item.get("deleted")
        ),
        None,
    )
    if item is None:
        raise ValueError("实验不存在、已删除或不属于当前会话。")
    return item


def _version(item, number=None):
    number = item["active_version"] if number is None else number
    version = next((value for value in item["versions"] if value["version"] == number), None)
    if type(number) is not int or version is None:
        raise ValueError("实验版本不存在。")
    return version


def _title(result):
    names = [
        entry.get("label") or catalog.BY_ID.get(name, {}).get("label") or name
        for name, entry in (result.get("methods") or {}).items()
        if isinstance(entry, dict)
    ]
    names += [
        entry.get("label")
        or catalog.BY_ID.get(entry.get("method"), {}).get("label")
        or entry.get("method", "")
        for entry in result.get("failures") or []
        if isinstance(entry, dict)
    ]
    return "、".join(dict.fromkeys(filter(None, names))) or result.get("title") or "实验结果"


def _add(state, result, source_key, at=None):
    identifier = "exp_" + hashlib.sha256(source_key.encode("utf-8")).hexdigest()[:16]
    item = {
        "id": identifier,
        "number": len(state["experiments"]) + 1,
        "source_key": source_key,
        "title": _title(result),
        "active_version": 1,
        "deleted": False,
        "versions": [],
    }
    _append(item, result, at)
    state["experiments"].append(item)
    state["selected_id"] = identifier
    return item


def _append(item, result, at=None):
    number = len(item["versions"]) + 1
    data = {
        **report.clean(copy.deepcopy(result)),
        "experiment_id": item["id"],
        "experiment_number": item["number"],
        "experiment_version": number,
    }
    item["versions"].append(
        {"version": number, "created_at": at or eventlog._now(), "result": data, "explanations": {}}
    )
    item["active_version"] = number
    item["title"] = _title(data)
    return data


def _migrate(state, events):
    known = {item["source_key"] for item in state["experiments"]}
    changed = False
    for event in events:
        if event.get("kind") != "tool/result" or event.get("name") not in (
            "run_ml_suite",
            "experiment",
        ):
            continue
        result = event.get("result")
        if not isinstance(result, dict) or result.get("code") == "invalid_tool_arguments":
            continue
        source = (
            "tool:" + str(event["call"]) + ":" + str(event.get("id") or event.get("seq"))
            if event.get("call")
            else "legacy:" + str(event.get("id") or event.get("seq"))
        )
        if source in known:
            continue
        # Runtime persists the experiment before writing its tool/result event.
        if any(item["id"] == result.get("experiment_id") for item in state["experiments"]):
            continue
        item = _add(state, result, source, event.get("at"))
        item["aliases"] = ["tool:" + str(event["call"])] if event.get("call") else []
        known.add(source)
        changed = True
    return changed


def load(root, owner, session, events=None):
    path = _path(root, owner, session)
    with _lock(path):
        log = eventlog.SessionLog(root, owner, session)
        if not log.exists():
            raise ValueError("会话不存在或已删除。")
        state = _load(path)
        if _migrate(state, log.events() if events is None else events):
            _write(path, state)
        return copy.deepcopy(state)


def register(root, owner, session, result, source_key):
    path = _path(root, owner, session)
    with _lock(path):
        state = load(root, owner, session)
        item = next(
            (entry for entry in state["experiments"] if entry["source_key"] == source_key), None
        )
        if item is None:
            item = _add(state, result, source_key)
            _write(path, state)
        return copy.deepcopy(_version(item)["result"])


def merge(previous, next_result, replaced):
    previous, next_result = copy.deepcopy(previous), copy.deepcopy(next_result)
    replaced = (
        set(replaced)
        | set(next_result.get("methods") or {})
        | {item["method"] for item in next_result.get("failures") or []}
    )
    methods = {
        key: value for key, value in (previous.get("methods") or {}).items() if key not in replaced
    }
    # Pin source and split to retained methods before replacing the common metadata.
    for value in methods.values():
        if not isinstance(value, dict):
            continue
        for key in ("data", "split", "dataset", "dataset_label", "source"):
            if key not in value and key in previous:
                value[key] = previous[key]
    methods.update(next_result.get("methods") or {})
    removed = {
        figure.get("name")
        for key in replaced
        for figure in (previous.get("methods") or {}).get(key, {}).get("figures", [])
        if isinstance(figure, dict)
    }
    figures = (
        []
        if set(previous.get("methods") or {}).issubset(replaced)
        else [
            figure for figure in previous.get("figures") or [] if figure.get("name") not in removed
        ]
    )
    by_url = {
        figure.get("url") or figure.get("name"): figure
        for figure in [*figures, *(next_result.get("figures") or [])]
    }
    failures = [
        item for item in previous.get("failures") or [] if item.get("method") not in replaced
    ] + (next_result.get("failures") or [])
    result = {
        **previous,
        **next_result,
        "methods": methods,
        "figures": list(by_url.values()),
        "failures": failures,
        "notes": next_result.get("notes", []),
        "warnings": next_result.get("warnings", []),
    }
    for key in ("error", "failures_note"):
        if key not in next_result:
            result.pop(key, None)
    return result


def rerun(root, owner, session, identifier, base_version, result, methods):
    path = _path(root, owner, session)
    with _lock(path):
        state = load(root, owner, session)
        item = _item(state, identifier)
        previous = _version(item, base_version)["result"]
        merged = merge(previous, result, methods)
        saved = _append(item, merged)
        state["selected_id"] = identifier
        _write(path, state)
        return copy.deepcopy(saved)


def mutate(root, owner, session, action, identifier, version=None):
    path = _path(root, owner, session)
    with _lock(path):
        state = load(root, owner, session)
        item = _item(state, identifier)
        if action == "delete":
            item["deleted"] = True
            if state["selected_id"] == identifier:
                state["selected_id"] = next(
                    (
                        value["id"]
                        for value in reversed(state["experiments"])
                        if not value.get("deleted")
                    ),
                    None,
                )
        elif action in ("select", "version"):
            if action == "version":
                item["active_version"] = _version(item, version)["version"]
                item["title"] = _title(_version(item)["result"])
            state["selected_id"] = identifier
        else:
            raise ValueError("未知的实验操作。")
        _write(path, state)
        return copy.deepcopy(state)


def public(state):
    result = copy.deepcopy(state)
    for item in result["experiments"]:
        if item.get("deleted"):
            item["versions"] = []
        for version in item["versions"]:
            version["result"] = datasets.with_metadata(version["result"])
            version["result"]["result_explanations"] = version.get("explanations", {})
    return result


def evidence(root, owner, session, view=None):
    state = load(root, owner, session)
    # Explicit browser selection/deletions are small references; results stay server-owned.
    if isinstance(view, dict):
        hidden = view.get("hidden_source_keys")
        if isinstance(hidden, list):
            for item in state["experiments"]:
                if not item.get("deleted") and any(
                    key in hidden
                    for key in [
                        item["source_key"],
                        item["id"],
                        "experiment:" + item["id"],
                        *item.get("aliases", []),
                    ]
                ):
                    state = mutate(root, owner, session, "delete", item["id"])
        identifier = view.get("selected_id")
        versions = view.get("active_versions")
        if isinstance(versions, dict):
            for identity, version in versions.items():
                item = _item(state, identity)
                if item["active_version"] != version:
                    state = mutate(root, owner, session, "version", identity, version)
        if isinstance(identifier, str) and identifier != state["selected_id"]:
            state = mutate(root, owner, session, "select", identifier)
    items = []
    for item in state["experiments"]:
        if item.get("deleted"):
            continue
        version = _version(item)
        items.append(
            {
                "id": item["id"],
                "number": item["number"],
                "name": _title(version["result"]),
                "version": version["version"],
                "version_count": len(item["versions"]),
                "created_at": version["created_at"],
                "result": datasets.with_metadata(version["result"]),
                "explanations": version["explanations"],
            }
        )
    return {
        "selected_id": state["selected_id"],
        "experiments": items,
        "meaning": "右侧保留的全部实验；每个实验仅当前展示版本。ID稳定，编号指实验卡片而非卡片内的方法序号。",
    }


def get(root, owner, session, identifier, version=None):
    state = load(root, owner, session)
    item = _item(state, identifier)
    return copy.deepcopy(_version(item, version))


def explanation(root, owner, session, identifier, version, method, value):
    if not identifier:
        return
    path = _path(root, owner, session)
    with _lock(path):
        state = load(root, owner, session)
        item = _item(state, identifier)
        selected = _version(item, version)
        if method not in (selected["result"].get("methods") or {}) and method != "__result":
            raise ValueError("解读方法不属于该实验版本。")
        selected["explanations"][method] = {
            key: value[key] for key in ("text", "model", "usage", "fingerprint") if key in value
        }
        _write(path, state)


def purge(root, owner, session):
    path = _path(root, owner, session)
    with _lock(path):
        path.unlink(missing_ok=True)
