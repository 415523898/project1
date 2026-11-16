"""Message revisions and branches retain original evidence and account ownership."""

import copy
import re
import shutil
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit

import config
from agent import eventlog
from engine import account_datasets, chat_attachments


def revision(log, value):
    if not isinstance(value, dict) or value.get("action") not in {"edit", "regenerate"}:
        raise ValueError("消息操作无效。")
    blocks = eventlog.turn_blocks(eventlog.active_events(log.events()))
    if not blocks or eventlog.turn_id(blocks[-1]["user"]) != value.get("event_id"):
        raise ValueError("这条消息已不是最新内容，请重新打开会话后操作。")
    target = blocks[-1]
    if value["action"] == "regenerate":
        end = next((e for e in reversed(target["events"]) if e["kind"] == "turn/end"), {})
        if (
            not end
            or end.get("interrupted")
            or not any(
                e["kind"] == "assistant/message" and e.get("text", "").strip()
                for e in target["events"]
            )
        ):
            raise ValueError("只能重新生成最新一轮已完成的回复。")
    return target


def fork(root, owner, session, event_id):
    source = eventlog.Store(root, owner).log(session)
    with source.lock:
        if not source.exists():
            raise eventlog.LogError("找不到这个对话记录。")
        events = eventlog.active_events(source.events())
        block = next(
            (b for b in eventlog.turn_blocks(events) if eventlog.turn_id(b["user"]) == event_id),
            None,
        )
        if block is None:
            raise ValueError("找不到这条回复，请重新打开会话后操作。")
        end = next((e for e in reversed(block["events"]) if e["kind"] == "turn/end"), {})
        if (
            not end
            or end.get("interrupted")
            or not any(
                e["kind"] == "assistant/message" and e.get("text", "").strip()
                for e in block["events"]
            )
        ):
            raise ValueError("请在回复完成后分支到新聊天。")
        cutoff = events.index(end) + 1
        prefix = copy.deepcopy(events[:cutoff])
        title = source.summary()["title"]
    identifier = uuid.uuid4().hex[:12]
    target = eventlog.Store(root, owner).log(identifier)
    copied = {}
    figure_base = Path(config.FIGURE_ROOT).resolve()

    def clone(value):
        if isinstance(value, dict):
            return {key: clone(item) for key, item in value.items()}
        if isinstance(value, list):
            return [clone(item) for item in value]
        if not isinstance(value, str):
            return value
        if "figures/" not in value:
            return value
        try:
            parsed = urlsplit(value)
        except ValueError:
            return value
        relative = unquote(parsed.path).lstrip("/")
        for route in ("api/figures/", "figures/"):
            if not relative.startswith(route + session + "/"):
                continue
            name = relative[len(route) :]
            original = (figure_base / name).resolve()
            scope = (figure_base / session).resolve()
            if not original.is_relative_to(scope) or not original.is_file():
                raise ValueError("分支引用的图表文件不可读取，请保留原会话后重试。")
            destination = figure_base / identifier / original.relative_to(scope)
            if name not in copied:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, destination)
                data = original.with_name(original.name + ".data.json")
                if data.is_file():
                    if data.is_symlink() or not data.resolve().is_relative_to(scope):
                        raise ValueError("分支引用的图形数据路径无效。")
                    shutil.copy2(data, destination.with_name(destination.name + ".data.json"))
                copied[name] = destination
            return "/" + route + destination.relative_to(figure_base).as_posix()
        pattern = (
            r"(?<=\()(?:https?://[^/\s)]+)?/?(?:api/)?figures/"
            + re.escape(session)
            + r'/[^\s)"<>]+'
        )
        return re.sub(pattern, lambda match: clone(match.group()), value)

    try:
        for event in prefix:
            payload = {
                key: value
                for key, value in event.items()
                if key not in {"v", "id", "seq", "kind", "supersedes", "revision_action"}
            }
            payload["origin_event_id"] = eventlog.turn_id(event)
            if event["kind"] == "user/message" and payload.get("attachments"):
                payload["attachments"] = chat_attachments.clone(
                    root, owner, session, identifier, payload["attachments"]
                )
            if event["kind"] == "tool/result" and isinstance(payload.get("result"), dict):
                result = payload["result"]
                payload["origin_experiment"] = {
                    key: result.pop(key)
                    for key in ("experiment_id", "experiment_version", "experiment_number")
                    if key in result
                }
            target.append(event["kind"], clone(payload))
        target.append(
            "session/title",
            {
                "text": ("分支 · " + title)[:60],
                "source": "branch",
                "branch_from": {"session": session, "event_id": event_id},
            },
        )
        # Dataset configuration is account-owned; no method/card binding is cloned.
        selected = (
            block["user"].get("context", {}).get("selected_dataset")
            if isinstance(block["user"].get("context"), dict)
            else None
        )
        if isinstance(selected, dict):
            account_datasets.restore_selection(root, owner, identifier, selected)
        for event in reversed(prefix):
            result = event.get("result")
            if (
                event["kind"] == "tool/result"
                and isinstance(result, dict)
                and result.get("methods")
                and result.get("dataset")
            ):
                account_datasets.remember_automatic(root, owner, identifier, result)
                break
        return eventlog.Store(root, owner).get(identifier)
    except Exception:
        target.path.unlink(missing_ok=True)
        folder = (figure_base / identifier).resolve()
        if folder.is_relative_to(figure_base) and folder.is_dir():
            shutil.rmtree(folder)
        account_datasets.forget_selection(root, owner, identifier)
        chat_attachments.drop_session(root, owner, identifier)
        raise
