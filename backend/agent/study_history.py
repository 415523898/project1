"""Persistent command history. Restore patches against the current graph, never a whole snapshot."""

import copy
import json
import time

from agent import study_graph as rules
from agent.study_graph import fail


def state(db, metadata):
    saved = copy.deepcopy(metadata.get("command_history", {"undo": [], "redo": []}))
    cutoff = time.time() - metadata["history_retention_days"] * 86400
    valid = {
        row[0]
        for row in db.execute("SELECT revision_id FROM revisions WHERE created_at>=?", (cutoff,))
    }
    return {
        direction: [entry for entry in saved.get(direction, []) if entry["revision_id"] in valid][
            -100:
        ]
        for direction in ("undo", "redo")
    }


def public(history):
    return {
        **{
            direction: history[direction][-1] if history[direction] else None
            for direction in ("undo", "redo")
        },
        "undo_count": len(history["undo"]),
        "redo_count": len(history["redo"]),
    }


def label(operations):
    names = {
        "create_card": "添加卡片",
        "update_card": "编辑卡片",
        "delete_card": "删除卡片",
        "move_nodes": "移动卡片",
        "create_edge": "添加连线",
        "update_edge": "修改连线",
        "delete_edge": "删除连线",
        "remove_node": "移出路线",
        "add_node": "加入路线",
        "retire_session_card": "合并重复卡片",
        "move_session_nodes": "整理卡片位置",
        "set_node_lock": "固定位置",
        "set_level_pin": "修改编号",
        "set_edge_route": "修改连接点",
    }
    return names.get(operations[0].get("op"), "修改学习路线") if operations else "AI 整理关系"


def comparable(row, table):
    if row is None:
        return None
    return {
        key: value
        for key, value in row.items()
        if key != "revision" and not (table == "sources" and key == "availability")
    }


def prepare(db, metadata, before, operation, root, owner):
    rules.whitelist(operation, {"op", "revision_id"}, {"op", "revision_id"})
    direction = rules.choice(operation["op"], {"undo", "redo"}, "未知撤回操作。")
    history = state(db, metadata)
    stack = history[direction]
    if not stack:
        fail(
            "当前没有可向后撤回的动作。" if direction == "undo" else "当前没有可向前撤回的动作。",
            "history_empty",
            409,
        )
    entry = stack[-1]
    if operation["revision_id"] != entry["revision_id"]:
        fail("历史已变化，请刷新后重新选择要撤回的动作。", "history_conflict", 409)
    row = db.execute(
        "SELECT patch FROM revisions WHERE revision_id=?", (entry["revision_id"],)
    ).fetchone()
    if row is None:
        fail("这个动作已超出可撤回的保留窗口。", "history_expired", 409)
    after = copy.deepcopy(before)
    for change in json.loads(row[0]):
        table, key = change["table"], change["id"]
        expected = change["after" if direction == "undo" else "before"]
        desired = change["before" if direction == "undo" else "after"]
        current = before[table].get(key)
        if comparable(current, table) != comparable(expected, table):
            fail("相关对象已变化，不能覆盖后来的修改。", "history_conflict", 409, object_id=key)
        if desired is None:
            after[table].pop(key, None)
        else:
            restored = copy.deepcopy(desired)
            if current is None:
                restored["revision"] = max(
                    restored.get("revision", 0) + 1,
                    metadata["graph_revision"] + metadata["layout_revision"] + 1,
                )
            if table == "sources":
                from agent import eventlog

                session = restored.get("session_id")
                restored["availability"] = (
                    "available"
                    if session and eventlog.SessionLog(root, owner, session).exists()
                    else "missing"
                    if session
                    else "unknown"
                )
            after[table][key] = restored
    rules.validate_graph(after)
    history[direction].pop()
    history["redo" if direction == "undo" else "undo"].append(entry)
    return after, history, entry
