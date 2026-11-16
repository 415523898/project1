import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

from config import (
    EVENTLOG_MAX_EVENT_BYTES as MAX_EVENT_BYTES,
)

LOG_SUFFIX = ".jsonl"
SESSION_DIR = "sessions"
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}\Z")

KINDS = (
    "turn/start",
    "user/message",
    "step/start",
    "assistant/message",
    "tool/call",
    "tool/result",
    "learning/direction",
    "learning/formula",
    "step/end",
    "turn/end",
    "session/title",
)


class LogError(Exception):
    pass


_locks = {}
_position = {}
_locks_guard = threading.Lock()


def lock_for(path):
    key = str(path)
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock()), _position.setdefault(key, [None])


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"


def _month():
    return time.strftime("%Y-%m")


def sessions_root(root, owner):
    return Path(root) / owner / SESSION_DIR


def log_paths(root, owner):
    directory = sessions_root(root, owner)
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.rglob("*" + LOG_SUFFIX) if path.is_file())


def _digest(tools):
    items = []
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        result = tool.get("result")
        if not isinstance(result, dict):
            continue
        entry = {"name": tool.get("name") or "tool"}
        if tool.get("reason"):
            entry["reason"] = tool["reason"]
        for key in ("error", "data", "split", "methods", "results"):
            if result.get(key) is not None:
                entry[key] = result[key]
        if tool.get("name") == "inspect_datasets" and result.get("dataset"):
            entry["dataset_profile"] = {
                key: result.get(key)
                for key in (
                    "id",
                    "label",
                    "rows",
                    "columns",
                    "task",
                    "target",
                    "time",
                    "group",
                    "fields",
                    "capabilities",
                )
            }
        figures = [
            figure.get("name")
            for figure in (result.get("figures") or [])
            if isinstance(figure, dict) and figure.get("url")
        ]
        if figures:
            entry["figures"] = figures
        if len(entry) > 1:
            items.append(entry)
    return items


def _turn_message(turn):
    payload = {"text": str(turn.get("question") or ""), "context": turn.get("context")}
    images = [
        item
        for item in (turn.get("images") or [])
        if isinstance(item, dict) and isinstance(item.get("data_url"), str)
    ]
    if (
        not images
        and isinstance(turn.get("image"), dict)
        and isinstance(turn["image"].get("data_url"), str)
    ):
        images = [turn["image"]]
    if images:
        payload["images"] = images
    if turn.get("attachments"):
        payload["attachments"] = turn["attachments"]
    return payload


def _event_images(event):
    images = event.get("images")
    if isinstance(images, list):
        return [item for item in images if isinstance(item, dict)]
    single = event.get("image")
    return [single] if isinstance(single, dict) else []


def turn_id(event):
    return str(event.get("id") or "seq:" + str(event.get("seq", "")))


def turn_blocks(events):
    """Physical spans remain immutable; replacement messages name the original user event."""
    blocks, current, start = [], None, None
    for index, event in enumerate(events):
        if event.get("kind") == "turn/start":
            if current is not None:
                current["end"] = index
                blocks.append(current)
                current = None
            start = index
        elif event.get("kind") == "user/message":
            if current is not None:
                current["end"] = index
                blocks.append(current)
            current = {"start": start if start is not None else index, "user": event}
            start = None
    if current is not None:
        current["end"] = len(events)
        blocks.append(current)
    for block in blocks:
        block["events"] = events[block["start"] : block["end"]]
    return blocks


def active_events(events):
    superseded = {
        event.get("supersedes")
        for event in events
        if event.get("kind") == "user/message" and event.get("supersedes")
    }
    hidden = set()
    for block in turn_blocks(events):
        if turn_id(block["user"]) in superseded:
            hidden.update(range(block["start"], block["end"]))
    return [
        event
        for index, event in enumerate(events)
        if index not in hidden or event.get("kind") == "session/title"
    ]


def _pairs(events):
    turns = []
    current = None
    for event in active_events(events):
        kind = event.get("kind")
        if kind == "user/message":
            text = event.get("text")
            if isinstance(text, str) and text.strip():
                current = {
                    "question": text,
                    "answer": "",
                    "context": event.get("context"),
                    "tool_result": [],
                    "images": _event_images(event),
                    "attachments": event.get("attachments", []),
                    "event_id": turn_id(event),
                }
                turns.append(current)
        elif kind == "assistant/message" and current is not None:
            text = event.get("text")
            if isinstance(text, str):
                current["answer"] += text
        elif kind == "tool/result" and current is not None:
            result = event.get("result")
            if isinstance(result, dict):
                current["tool_result"].append(
                    {"name": event.get("name") or "tool", "dispatch": result}
                )
    return turns


def derive(events, limit=6):
    turns = []
    for turn in _pairs(events):
        tools = []
        for item in turn["tool_result"]:
            tools.extend(_digest([{"name": item["name"], "result": item["dispatch"]}]))
        turns.append(
            {
                "question": turn["question"],
                "answer": turn["answer"],
                "context": turn["context"],
                "tool_result": tools or None,
                "images": turn["images"],
                "attachments": turn["attachments"],
                "event_id": turn["event_id"],
            }
        )
    return turns[-limit:] if limit else turns


class SessionLog:
    def __init__(self, root, owner, session_id, path=None):
        self.root = Path(root)
        self.owner = owner
        self.session_id = session_id
        self.directory = sessions_root(root, owner)
        self.path = Path(path) if path is not None else self._locate()
        self.lock, self._seq = lock_for(self.path)

    def _locate(self):
        for path in log_paths(self.root, self.owner):
            if path.stem == self.session_id:
                return path
        return self.directory / _month() / (self.session_id + LOG_SUFFIX)

    def exists(self):
        return self.path.is_file()

    def events(self):
        if not self.path.is_file():
            return []
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError as error:
            raise LogError(f"会话日志不可读：{error.strerror or error}") from error
        items = []
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("kind") in KINDS:
                items.append(item)
        return items

    def append(self, kind, payload=None, *, condition=None):
        if kind not in KINDS:
            raise LogError("未知的事件类型。")
        with self.lock:
            if condition is not None and not condition(self.events()):
                return None
            paid = self._seq[0]
            if paid is None:
                events = self.events()
                paid = (events[-1].get("seq") or 0) + 1 if events else 0
            event = {
                "v": 1,
                "seq": paid,
                "id": uuid.uuid4().hex[:12],
                "kind": kind,
                "at": _now(),
            }
            if payload:
                event.update(payload)
            line = json.dumps(event, ensure_ascii=False, allow_nan=False)
            if len(line.encode("utf-8")) > MAX_EVENT_BYTES:
                raise LogError("单条会话事件过大。")
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._write(line + "\n")
            except LogError:
                self._seq[0] = paid
                raise
            self._seq[0] = paid + 1
            # The log is authoritative evidence. Context compaction must never
            # replace its original tool results with irreversible head/tail text.
            return event

    def _write(self, text):
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        handle = None
        try:
            handle = os.open(self.path, flags, 0o600)
            os.write(handle, text.encode("utf-8"))
        except OSError as error:
            raise LogError(f"会话日志写入失败：{error.strerror or error}") from error
        finally:
            if handle is not None:
                os.close(handle)

    def summary(self):
        events = self.events()
        turns = [event for event in active_events(events) if event.get("kind") == "user/message"]
        named = [event for event in events if event.get("kind") == "session/title"]
        created = events[0].get("at") if events else _now()
        updated = events[-1].get("at") if events else created
        title = named[-1].get("text") if named else ""
        title_source = named[-1].get("source") if named else "fallback"
        if title_source not in {"manual", "ai", "fallback", "branch"}:
            first = next(
                (" ".join(str(event.get("text") or "").split())[:60] for event in turns), ""
            )
            if named and named[-1].get("branch_from"):
                title_source = "branch"
            elif not title or title == "新的对话" or title.rstrip("…") == first:
                title_source = "fallback"
            elif (
                title.startswith(("分支 · ", "分支·"))
                and any(event.get("branch_from") for event in named)
                and all(
                    event.get("text") == title
                    for event in named
                    if not event.get("origin_event_id")
                )
            ):
                title_source = "branch"
            else:
                title_source = "manual"
        if not title:
            for event in turns:
                text = event.get("text")
                if isinstance(text, str) and text.strip():
                    title = " ".join(text.split())[:60]
                    break
        return {
            "id": self.session_id,
            "title": title or "新的对话",
            "title_source": title_source,
            "created_at": created,
            "updated_at": updated,
            "turns": len(turns),
            "tools": sum(1 for event in events if event.get("kind") == "tool/result"),
        }

    def delete(self):
        with self.lock:
            return self._delete_locked()

    def _delete_locked(self):
        if not self.path.is_file():
            raise LogError("找不到这个对话记录。")
        try:
            self.path.unlink()
        except OSError as error:
            raise LogError(f"会话日志删除失败：{error.strerror or error}") from error
        try:
            self.path.parent.rmdir()
        except OSError:
            pass
        return {"deleted": self.session_id}


def list_logs(root, owner):
    items = []
    for path in log_paths(root, owner):
        log = SessionLog(root, owner, path.stem, path)
        try:
            items.append(log.summary())
        except LogError:
            continue
    items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return items


class Store:
    def __init__(self, root, owner):
        self.root = Path(root)
        self.owner = owner
        self.directory = self.root / owner
        self.directory.mkdir(parents=True, exist_ok=True)

    def log(self, session_id):
        if not isinstance(session_id, str) or not SESSION_ID.match(session_id):
            raise LogError("对话编号无效。")
        return SessionLog(self.root, self.owner, session_id)

    def list(self):
        return list_logs(self.root, self.owner)

    def get(self, session_id):
        log = self.log(session_id)
        if not log.exists():
            raise LogError("找不到这个对话记录。")
        events = log.events()
        if not events:
            raise LogError("找不到这个对话记录。")
        return {"id": session_id, **log.summary(), "events": active_events(events)}

    def save(self, session_id, payload):
        if not isinstance(payload, dict):
            raise LogError("对话内容无效。")
        session_id = session_id or uuid.uuid4().hex[:12]
        log = self.log(session_id)
        if log.exists():
            title = payload.get("title")
            if isinstance(title, str) and title.strip():
                source = payload.get("title_source", "manual")
                text = title.strip()[:60]

                # Autosaving a temporary title must not overwrite an AI/manual name.
                def writable(events):
                    named = [event for event in events if event["kind"] == "session/title"]
                    if not named:
                        return True
                    last = named[-1]
                    if source == "fallback":
                        return False
                    return last.get("text") != text or last.get("source") != source

                log.append("session/title", {"text": text, "source": source}, condition=writable)
            return {"id": session_id, **log.summary()}
        turns = payload.get("turns") or []
        # Imported metadata cannot introduce arbitrary paths, text or another session's refs.
        from engine import chat_attachments

        for turn in turns:
            if isinstance(turn, dict) and turn.get("attachments"):
                try:
                    turn["attachments"] = chat_attachments.resolve(log, turn["attachments"])
                except ValueError as error:
                    raise LogError(str(error)) from error
        if not turns:
            return self._touch(log, payload.get("title"), payload.get("title_source", "manual"))
        for index, turn in enumerate(turns):
            if not isinstance(turn, dict):
                continue
            log.append("turn/start", {"imported": True})
            log.append("user/message", _turn_message(turn))
            for tool in turn.get("tools") or []:
                if not isinstance(tool, dict):
                    continue
                name = tool.get("name") or "tool"
                log.append(
                    "tool/call",
                    {
                        "name": name,
                        "arguments": tool.get("arguments"),
                        "reason": tool.get("reason"),
                    },
                )
                if isinstance(tool.get("result"), dict):
                    log.append("tool/result", {"name": name, "result": tool["result"]})
            if turn.get("result") is not None:
                log.append("tool/result", {"name": "experiment", "result": turn["result"]})
            answer = turn.get("answer")
            if isinstance(answer, str) and answer:
                log.append("assistant/message", {"text": answer})
            log.append("turn/end", {"imported": True, "index": index})
        return {"id": session_id, **log.summary()}

    def _touch(self, log, title=None, title_source="manual"):
        log.append("turn/start", {"empty": True})
        log.append("turn/end", {"empty": True})
        if isinstance(title, str) and title.strip():
            log.append("session/title", {"text": title.strip()[:60], "source": title_source})
        return {"id": log.session_id, **log.summary()}

    def delete(self, session_id):
        log = self.log(session_id)
        if not log.exists():
            raise LogError("找不到这个对话记录。")
        return log.delete()

    def workspaces(self):
        return [
            {
                "id": self.owner,
                "label": self.owner,
                "root": str(self.root.parents[1]),
                "sessions": len(self.list()),
            }
        ]
