"""Main-Harness suggestions require confirmation; background work only maintains bound cards."""

import json
import os
import threading
import time
from pathlib import Path

from agent import eventlog, provider
from engine import catalog

_guard = threading.Lock()
_locks = {}
_maintenance = {}


def locks(path):
    with _guard:
        return _locks.setdefault(str(path), (threading.RLock(), threading.Lock()))


def state_path(root, owner, session):
    if not isinstance(session, str) or not eventlog.SESSION_ID.fullmatch(session):
        raise ValueError("对话编号无效。")
    return Path(root) / owner / "learning" / (session + ".json")


def fresh():
    return {
        "version": 2,
        "origin_id": None,
        "current_id": None,
        "enabled": True,
        "baseline": -1,
        "source_seq": -1,
        "seen_seq": -1,
        "revision": 0,
        "direction_id": None,
        "streak": 0,
        "matches": [],
        "last_error": "",
        "proposal_id": None,
        "dismissed_proposals": [],
        "drift_id": None,
        "dismissed_directions": [],
        "awaiting_goal": True,
        "maintenance_error": "",
        "excluded_turn_starts": [],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "calls": 0,
            "unknown_calls": 0,
        },
    }


def read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return {**fresh(), **value}
    except (OSError, ValueError):
        pass
    return fresh()


def chat_context(root, owner, session):
    """Read the saved card selection even when optional AI matching is disabled."""
    path = state_path(root, owner, session)
    with locks(path)[0]:
        state = read(path)

    def describe(identifier):
        item = catalog.BY_ID.get(identifier)
        if not item:
            return None
        return {
            key: item[key]
            for key in ("id", "label", "group", "kind", "tasks", "inputs", "outputs", "note")
            if key in item
        } | {
            "when": catalog.WHEN.get(identifier, ""),
            "category": catalog.CATEGORY_NAMES.get(catalog.category_of(identifier), ""),
        }

    from agent import study_binding

    binding = study_binding.public(root, owner, session)
    if binding:
        state.update(current_id=binding["method_id"], origin_id=binding["method_id"])
    current = describe(state.get("current_id")) or describe(state.get("origin_id"))
    if not current:
        return None
    return {
        "origin": describe(state.get("origin_id")),
        "current": current,
        "confirmed": bool(binding),
    }


def synchronize(root, owner, session, state):
    from agent import study_binding

    binding = study_binding.public(root, owner, session)
    state.update(
        current_id=binding["method_id"] if binding else None,
        origin_id=binding["method_id"] if binding else None,
        binding=binding,
    )
    return state


def write(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def completed_rounds(events):
    rounds = []
    current = None
    for event in eventlog.active_events(events):
        kind = event.get("kind")
        if kind == "turn/start":
            current = {"question": "", "answer": ""}
        elif kind == "user/message":
            current = {
                "question": str(event.get("text") or ""),
                "answer": "",
                "start_seq": event.get("seq", -1),
                "event_id": eventlog.turn_id(event),
            }
        elif kind == "assistant/message" and current:
            current["answer"] += str(event.get("text") or "")
        elif kind == "turn/end" and current:
            if (
                current["question"].strip()
                and current["answer"].strip()
                and not event.get("interrupted")
            ):
                rounds.append({**current, "seq": int(event.get("seq", -1))})
            current = None
    return rounds


def next_round(state, rounds):
    boundary = max(state["baseline"], state["seen_seq"])
    return next((turn for turn in rounds if turn["seq"] > boundary), None)


def public(state, rounds):
    return {
        key: state[key]
        for key in ("origin_id", "current_id", "enabled", "matches", "usage", "last_error")
    } | {
        "mode": "guided" if state["origin_id"] else "free",
        "ready": False,
        "direction_source": "main_harness",
        "last_error": "",
        **{
            k: state.get(k)
            for k in ("binding", "proposal_id", "drift_id", "awaiting_goal", "maintenance_error")
        },
    }


def load(root, owner, session):
    path = state_path(root, owner, session)
    with locks(path)[0]:
        rounds = completed_rounds(eventlog.Store(root, owner).get(session)["events"])
        state = synchronize(root, owner, session, read(path))
        return {**public(state, rounds), "pending": False}


def update(root, owner, session, payload):
    path = state_path(root, owner, session)
    with locks(path)[0]:
        rounds = completed_rounds(eventlog.Store(root, owner).get(session)["events"])
        state = synchronize(root, owner, session, read(path))
        if "source" in payload:
            source = payload["source"]
            if not isinstance(source, str) or source not in catalog.BY_ID:
                raise ValueError("找不到这个学习卡片。")
            if not state.get("binding"):
                state.update(proposal_id=source, awaiting_goal=False, matches=[])
                state["revision"] += 1
        if payload.get("confirm"):
            from agent import study_binding

            if payload["confirm"] != state.get("proposal_id") and payload["confirm"] != (
                state.get("binding") or {}
            ).get("method_id"):
                raise ValueError("绑定建议已变化，请重新确认。")
            study_binding.confirm(root, owner, session, payload["confirm"])
            state = synchronize(root, owner, session, state)
            state.update(proposal_id=None, matches=[], awaiting_goal=False)
            state["revision"] += 1
        if payload.get("dismiss_proposal"):
            proposal = state.get("proposal_id")
            if proposal and proposal not in state["dismissed_proposals"]:
                state["dismissed_proposals"].append(proposal)
            state.update(proposal_id=None, matches=[])
            state["revision"] += 1
        if payload.get("dismiss_drift"):
            direction = state.get("drift_id")
            if direction and direction not in state["dismissed_directions"]:
                state["dismissed_directions"].append(direction)
            state["drift_id"] = None
            state["revision"] += 1
        if "enabled" in payload:
            raise ValueError("独立 AI 探索已移除，学习方向由主对话 Harness 判断。")
        write(path, state)
        return public(state, rounds)


def apply_decision(state, decision):
    if not state.get("current_id"):
        direction = decision.get("direction_id") if decision.get("clear") else None
        state.update(
            matches=decision["matches"][:1] if direction else [],
            awaiting_goal=not bool(direction),
            proposal_id=direction if direction not in state["dismissed_proposals"] else None,
        )
        return
    direction = (
        decision.get("direction_id") if decision.get("clear") and decision.get("changed") else None
    )
    state.update(
        matches=[],
        proposal_id=None,
        awaiting_goal=False,
        drift_id=direction if direction not in state["dismissed_directions"] else None,
    )


def record_main_direction(log, user_event_id, value):
    """Publish only metadata belonging to the latest fully completed active reply."""
    from agent import learning_direction

    path = state_path(log.root, log.owner, log.session_id)
    with locks(path)[0]:
        rounds = completed_rounds(log.events())
        if not rounds or rounds[-1].get("event_id") != user_event_id:
            raise ValueError("学习方向所属回复尚未完成或已被替换。")
        turn = rounds[-1]
        value = learning_direction.validate(value, turn["question"])
        state = synchronize(log.root, log.owner, log.session_id, read(path))
        clear = value["intent"] == "learn"
        changed = bool(
            clear and state.get("current_id") and value["method_id"] != state["current_id"]
        )
        apply_decision(
            state,
            {"matches": [], "clear": clear, "changed": changed, "direction_id": value["method_id"]},
        )
        if changed and turn["start_seq"] not in state["excluded_turn_starts"]:
            state["excluded_turn_starts"].append(turn["start_seq"])
        state.update(seen_seq=turn["seq"], last_error="", direction_source="main_harness")
        state["revision"] += 1
        write(path, state)
        return public(state, rounds)


def purge(root, owner, session):
    path = state_path(root, owner, session)
    with locks(path)[0]:
        path.unlink(missing_ok=True)


def after_turn(log, settings):
    """Detached from the browser: completed background chats still get their card."""
    from agent import study_binding

    if not isinstance(log, eventlog.SessionLog):
        return
    identity = str(log.path)
    with _guard:
        if identity in _maintenance:
            _maintenance[identity]["settings"] = settings
            _maintenance[identity]["queued"] = True
            return
        pending = {"settings": settings, "queued": True}
        _maintenance[identity] = pending

    def work():
        try:
            while log.exists():
                with _guard:
                    if not pending["queued"]:
                        break
                    pending["queued"] = False
                    selected = pending["settings"]
                try:
                    deadline = time.monotonic() + 900
                    while log.exists():
                        try:
                            job = study_binding.auto_update(
                                log.root, log.owner, log.session_id, selected
                            )
                            break
                        except ValueError as error:
                            if (
                                getattr(error, "code", "") != "ai_busy"
                                or time.monotonic() > deadline
                            ):
                                raise
                            time.sleep(0.5)
                    else:
                        break
                    if job and job.get("status") == "running":
                        from agent import study_session

                        while job["status"] == "running" and log.exists():
                            time.sleep(0.5)
                            job = study_session.public(log.root, log.owner, job["operation_id"])
                    path = state_path(log.root, log.owner, log.session_id)
                    if log.exists():
                        with locks(path)[0]:
                            state = read(path)
                            state["maintenance_error"] = ""
                            write(path, state)
                except (ValueError, eventlog.LogError, provider.ProviderError) as problem:
                    if log.exists():
                        path = state_path(log.root, log.owner, log.session_id)
                        with locks(path)[0]:
                            state = read(path)
                            state["maintenance_error"] = str(problem).replace(
                                selected[1], "[已隐藏]"
                            )[:240]
                            write(path, state)
                with _guard:
                    if not pending["queued"]:
                        _maintenance.pop(identity, None)
                        return
        finally:
            with _guard:
                if _maintenance.get(identity) is pending:
                    _maintenance.pop(identity, None)

    threading.Thread(target=work, name="learning-intent-" + log.session_id, daemon=True).start()
