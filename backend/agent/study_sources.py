"""Stable, complete-prefix session evidence for learning cards; never a six-turn chat view."""

import copy
import hashlib
import json
from itertools import groupby

from agent import eventlog, experiment_store
from agent import study_store as store
from agent.study_graph import fail
from config import (
    STUDY_SOURCES_CHUNK_CHARS as CHUNK_CHARS,
)
from config import (
    STUDY_SOURCES_FRAGMENT_CHARS as FRAGMENT_CHARS,
)
from config import (
    STUDY_SOURCES_MAX_CHUNK_CHARS as MAX_CHUNK_CHARS,
)
from config import (
    STUDY_SOURCES_MAX_CHUNK_UNITS as MAX_CHUNK_UNITS,
)
from config import (
    STUDY_SOURCES_UNIT_CHARS as UNIT_CHARS,
)

SECRET_FIELDS = {
    "api_key",
    "authorization",
    "password",
    "access_token",
    "refresh_token",
    "cookie",
    "data_url",
}


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if k.lower() not in SECRET_FIELDS}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def event_ref(event, position):
    return (
        "event:" + str(event["id"]) if event.get("id") else "seq:" + str(event.get("seq", position))
    )


def pruned(value):
    return (
        isinstance(value, dict)
        and (bool(value.get("pruned")) or any(str(k).startswith("text_") for k in value))
        or "（中间内容已裁剪）" in str(value)
    )


def snapshot(root, owner, session_id, cutoff=None):
    log = eventlog.Store(root, owner).log(session_id)
    with log.lock:
        if not log.exists():
            fail("来源会话不存在或已删除。", "source_deleted", 404)
        try:
            lines = log.path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            fail("来源记录不可读取，未开始整理。", "source_unreadable")
        events, invalid = [], []
        for position, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, dict) or value.get("kind") not in eventlog.KINDS:
                    raise ValueError()
                events.append((position, value))
            except (ValueError, TypeError):
                invalid.append(position)
        complete = [
            i
            for i, (_, e) in enumerate(events)
            if e["kind"] == "turn/end" and not e.get("interrupted") and not e.get("empty")
        ]
        if cutoff is None:
            if not complete:
                fail("还没有完整的一轮会话；可在本轮结束后整理。", "no_complete_turn", 409)
            last = complete[-1]
        else:
            last = next(
                (i for i, (position, e) in enumerate(events) if event_ref(e, position) == cutoff),
                None,
            )
            if last is None:
                fail("来源截止事件已改变，请重新整理。", "source_changed", 409)
        prefix = events[: last + 1]
        end_line = prefix[-1][0]
        prefix_hash = hashlib.sha256("\n".join(lines[: end_line + 1]).encode("utf-8")).hexdigest()
    units, turn, turn_seq, losses = [], 0, None, []
    replacements = {
        e["supersedes"]: eventlog.turn_id(e)
        for _, e in prefix
        if e.get("kind") == "user/message" and e.get("supersedes")
    }
    turn_identity = None
    turn_states = {}
    current_turn = None
    for position, event in prefix:
        if event["kind"] == "user/message":
            current_turn = event.get("seq", position)
        if current_turn is not None and event["kind"] == "turn/end":
            turn_states[current_turn] = "interrupted" if event.get("interrupted") else "completed"
    # Read existing immutable versions only. Never migrate a pruned event into an
    # apparent authoritative version, and never substitute the active version.
    path = experiment_store._path(root, owner, session_id)
    try:
        experiments = experiment_store._load(path)
    except (OSError, ValueError):
        experiments = {"experiments": []}
    for position, event in prefix:
        kind = event["kind"]
        if kind == "user/message":
            turn += 1
            turn_seq = event.get("seq", position)
            turn_identity = eventlog.turn_id(event)
        if kind not in {"user/message", "assistant/message", "tool/call", "tool/result"}:
            continue
        result = event.get("result") if kind == "tool/result" else None
        experiment_id = result.get("experiment_id") if isinstance(result, dict) else None
        version = result.get("experiment_version") if isinstance(result, dict) else None
        if type(version) is not int:
            version = None
        restored = None
        if experiment_id and type(version) is int:
            for item in experiments.get("experiments", []):
                if item.get("id") == experiment_id:
                    restored = next(
                        (
                            v.get("result")
                            for v in item.get("versions", [])
                            if v.get("version") == version
                        ),
                        None,
                    )
        missing = pruned(event)
        if restored is not None and not pruned(restored):
            result = restored
            missing = False
        if missing:
            losses.append(event_ref(event, position))
        if kind in {"user/message", "assistant/message"}:
            text = event.get("text") or ""
            if event.get("images") or event.get("image"):
                text += "\n[本轮有图片；本次仅整理已保存的文字与实验事实，图片内容未读取。]"
                losses.append(event_ref(event, position))
        else:
            text = store.encode(
                clean(
                    {"name": event.get("name"), "arguments": event.get("arguments")}
                    if kind == "tool/call"
                    else {
                        "name": event.get("name"),
                        "result": result,
                        "interrupted": event.get("interrupted", False),
                    }
                )
            )
        if not isinstance(text, str):
            text = store.encode(clean(text))
        for part, start in enumerate(range(0, len(text), UNIT_CHARS)):
            identity = event_ref(event, position)
            key = "u_" + hashlib.sha256(f"{session_id}:{identity}:{part}".encode()).hexdigest()[:24]
            units.append(
                {
                    "unit_id": key,
                    "event_ref": identity,
                    "event_seq": event.get("seq", position),
                    "turn": turn,
                    "turn_start_seq": turn_seq,
                    "kind": kind,
                    "part": part + 1,
                    "text": text[start : start + UNIT_CHARS],
                    "turn_status": turn_states.get(turn_seq, "legacy"),
                    "superseded_by": replacements.get(turn_identity),
                    "revision_action": event.get("revision_action")
                    if kind == "user/message"
                    else None,
                    "experiment_id": experiment_id,
                    "version": version,
                    "evidence_quality": "partial" if missing else "snapshot",
                }
            )
    if not units:
        fail("这个会话没有可整理的有效内容。", "empty_source", 409)
    return {
        "session_id": session_id,
        "cutoff_ref": event_ref(prefix[-1][1], prefix[-1][0]),
        "cutoff_seq": prefix[-1][1].get("seq", prefix[-1][0]),
        "fingerprint": prefix_hash,
        "turns": turn,
        "units": units,
        "source_scan_complete": not any(p <= end_line for p in invalid),
        "invalid_records": sum(p <= end_line for p in invalid),
        "evidence_quality": "partial"
        if losses or any(p <= end_line for p in invalid)
        else "snapshot",
        "pruned_refs": sorted(set(losses)),
        "precision": "event" if all(e.get("id") is not None for _, e in prefix) else "legacy",
    }


def model_unit(unit):
    """The model selects a local anchor; the server alone copies original text."""
    fragments = []
    start = 0
    text = unit["text"]
    while start < len(text):
        end = min(start + FRAGMENT_CHARS, len(text))
        if end < len(text):
            boundary = max(
                text.rfind(mark, start + FRAGMENT_CHARS // 2, end)
                for mark in ["\n", "。", "；", ";"]
            )
            if boundary >= 0:
                end = boundary + 1
        fragments.append({"evidence_id": "p" + str(len(fragments) + 1), "text": text[start:end]})
        start = end
    return {
        k: unit[k]
        for k in [
            "unit_id",
            "turn",
            "kind",
            "turn_status",
            "experiment_id",
            "version",
            "evidence_quality",
            "superseded_by",
            "revision_action",
        ]
        if k in unit
    } | {"fragments": fragments}


def chunks(value):
    """Keep ordinary turns intact; split only tool-heavy turns, with bounded input."""
    result, batch, size = [], [], 0

    def flush():
        nonlocal batch, size
        if batch:
            result.append(batch)
        batch, size = [], 0

    for _, group in groupby(value["units"], key=lambda u: u["turn"]):
        group = list(group)
        counts = [len(store.encode(model_unit(u))) for u in group]
        total = sum(counts)
        if total <= MAX_CHUNK_CHARS and len(group) <= MAX_CHUNK_UNITS:
            if batch and (
                size + total > MAX_CHUNK_CHARS or len(batch) + len(group) > MAX_CHUNK_UNITS
            ):
                flush()
            batch.extend(group)
            size += total
            if size >= CHUNK_CHARS:
                flush()
        else:
            for unit, count in zip(group, counts):
                if batch and (size + count > CHUNK_CHARS or len(batch) >= MAX_CHUNK_UNITS):
                    flush()
                batch.append(unit)
                size += count
    if batch:
        result.append(batch)
    return result


def public_snapshot(value):
    return {k: copy.deepcopy(v) for k, v in value.items() if k != "units"} | {
        "unit_count": len(value["units"])
    }


def verify(root, owner, value):
    current = snapshot(root, owner, value["session_id"], value["cutoff_ref"])
    if current["fingerprint"] != value["fingerprint"]:
        fail("来源前缀已修改，已提取的内容不能直接保存，请重新整理。", "source_changed", 409)


def locate(root, owner, source_id, ref=None):
    with store.connection(root, owner) as db:
        row = db.execute("SELECT payload FROM sources WHERE source_id=?", (source_id,)).fetchone()
    if not row:
        fail("来源不存在。", "not_found", 404)
    source = json.loads(row[0])
    session = source.get("session_id")
    if not session:
        fail("这条来源没有关联会话。", "source_missing", 404)
    if ref is not None and ref not in source.get("event_refs", []):
        fail("来源事件不属于这张卡片。", "invalid_source")
    refs = {ref} if ref else set(source.get("event_refs", []))
    log = eventlog.Store(root, owner).log(session)
    if not log.exists():
        fail("原会话已删除；卡片采用的事实仍然保留。", "source_deleted", 404)
    events = log.events()
    visible = eventlog.active_events(events)
    identities = [eventlog.turn_id(e) for e in visible if e["kind"] == "user/message"]
    replacements = {
        e["supersedes"]: eventlog.turn_id(e)
        for e in events
        if e["kind"] == "user/message" and e.get("supersedes")
    }
    identity = None
    for position, event in enumerate(events):
        if event["kind"] == "user/message":
            identity = eventlog.turn_id(event)
        if event_ref(event, position) in refs:
            superseded = identity in replacements
            seen = set()
            while identity in replacements and identity not in seen:
                seen.add(identity)
                identity = replacements[identity]
            turn = identities.index(identity) if identity in identities else 0
            return {
                "session_id": session,
                "turn_index": turn,
                "event_ref": event_ref(event, position),
                "superseded": superseded,
                "experiment_id": source.get("experiment_id"),
                "version": source.get("version"),
                "precision": source.get("precision", "event"),
            }
    fail("来源事件已缺失；卡片采用的事实仍然保留。", "source_missing", 404)
