"""One confirmed method/card per session. No implicit migration of historical cards."""

import copy
import uuid

from agent import eventlog
from agent import study_graph as rules
from agent import study_store as store
from engine import catalog

KEY = "session_bindings_v1"


def by_card(metadata):
    return {value["card_id"]: value for value in metadata.get(KEY, {}).values()}


def independent_same_method(bindings, a, b):
    left, right = bindings.get(a), bindings.get(b)
    return bool(
        left
        and right
        and left["session_id"] != right["session_id"]
        and left["method_id"] == right["method_id"]
    )


def all_bindings(root, owner):
    with store.connection(root, owner) as db:
        return store.meta(db).get(KEY, {})


def public(root, owner, session_id):
    value = all_bindings(root, owner).get(session_id)
    if not value:
        return None
    with store.connection(root, owner) as db:
        exists = bool(
            db.execute("SELECT 1 FROM cards WHERE card_id=?", (value["card_id"],)).fetchone()
        )
    return {
        **value,
        "card_missing": not exists,
        "session_missing": not eventlog.SessionLog(root, owner, session_id).exists(),
    }


def enrich(root, owner, graph, bindings):
    """Only explicit associations receive warnings; independent cards stay independent."""
    for session_id, value in bindings.items():
        card = graph["cards"].get(value["card_id"])
        if card:
            card["binding"] = {
                **value,
                "session_missing": not eventlog.SessionLog(root, owner, session_id).exists(),
            }


def confirm(root, owner, session_id, method_id, summary=None, expected_event_id=None):
    eventlog.Store(root, owner).get(session_id)
    if method_id not in catalog.BY_ID:
        rules.fail("找不到这个方法。")
    log = eventlog.Store(root, owner).log(session_id)
    with log.lock:
        if not log.exists():
            rules.fail("来源会话已删除。", "source_deleted", 409)
        # Recheck under the per-session lock: concurrent retries share one card.
        current = public(root, owner, session_id)
        if current:
            if current["method_id"] != method_id:
                rules.fail("本会话已绑定一个方法，请在新会话学习新方法。", "already_bound", 409)
            return current
        value = store.workspace(root, owner)
        operations = []
        # Binding replaces the automatic general card of this conversation instead
        # of leaving two cards for the same session.
        from agent import study_topic

        topic = study_topic.topic_card(root, owner, session_id)
        if topic:
            operations.append(
                {
                    "op": "delete_card",
                    "card_id": topic["card_id"],
                    "expected_revision": topic["revision"],
                }
            )
        operations += [
            {
                "op": "create_card",
                "client_ref": "bound_card",
                "values": {
                    "title": catalog.label_of(method_id),
                    "summary": summary or "已绑定会话，可在学习卡片面板手动让 AI 更新。",
                    "type": "conversation",
                    "method_ids": [method_id],
                },
            },
            {
                "op": "add_node",
                "card_id": "bound_card",
                "x": 40,
                "y": max((n["y"] for n in value["nodes"]), default=-192) + 288,
            },
        ]
        request = {
            "schema_version": 2,
            "operation_id": "bind_" + uuid.uuid4().hex,
            "base_graph_revision": value["graph_revision"],
            "base_layout_revision": value["layout_revision"],
            "operations": operations,
        }
        if expected_event_id is not None:
            events = log.events()
            if not events or events[-1].get("id") != expected_event_id:
                rules.fail("会话内容已更新，请基于最新回复重新匹配。", "source_changed", 409)
        store._apply_changes(
            root,
            owner,
            request,
            request["operation_id"],
            store.fingerprint(request),
            binding_create={
                "session_id": session_id,
                "method_id": method_id,
                "card_ref": "bound_card",
            },
        )
    return public(root, owner, session_id)


def validate_commit(db, before, after, actor, job=None, creation=None):
    """Inside the graph transaction: confirmation, uniqueness and deletion races."""
    bindings = copy.deepcopy(store.meta(db).get(KEY, {}))
    if creation:
        sid = creation["session_id"]
        if sid in bindings:
            rules.fail("本会话已有绑定，请刷新后查看。", "already_bound", 409)
        cid = creation["card_id"]
        bindings[sid] = {"session_id": sid, "method_id": creation["method_id"], "card_id": cid}
        # Confirmation is a human decision; the generated content remains auto-maintainable.
        after["cards"][cid].update(created_by="ai_session", manual_fields=[])
    if job and job.get("binding"):
        binding = job["binding"]
        if (
            bindings.get(binding["session_id"]) != binding
            or binding["card_id"] not in before["cards"]
        ):
            rules.fail("关联卡片已删除或绑定已变化，本次更新未应用。", "binding_changed", 409)
        changed_cards = {
            cid
            for cid in set(before["cards"]) | set(after["cards"])
            if before["cards"].get(cid) != after["cards"].get(cid)
        }
        if changed_cards - {binding["card_id"]}:
            rules.fail("一次会话只能更新已绑定的一张卡片。", "binding_scope", 409)
    for binding in bindings.values():
        card = after["cards"].get(binding["card_id"])
        if card and card["method_ids"] != [binding["method_id"]]:
            rules.fail("绑定方法不可自动切换，请另开会话。", "binding_method", 409)
    if creation:
        store.set_meta(db, {KEY: bindings})


def delete_session(root, owner, project_root, session_id, sync_card=False):
    """Keep a tombstone association when only one endpoint is removed."""
    from agent import experiment_store, learning_exploration, result_explanation, runtime
    from agent.figure_scope import drop_session_figures
    from engine import account_datasets, chat_attachments

    handle = eventlog.Store(root, owner)
    handle.get(session_id)
    binding = public(root, owner, session_id)
    runtime.RUNTIME.cancel_conversation(root, owner, session_id)
    if sync_card and binding and not binding["card_missing"]:
        value = store.workspace(root, owner)
        store.apply_changes(
            root,
            owner,
            {
                "schema_version": 2,
                "operation_id": "delete_bound_" + uuid.uuid4().hex,
                "base_graph_revision": value["graph_revision"],
                "base_layout_revision": value["layout_revision"],
                "operations": [
                    {
                        "op": "delete_card",
                        "card_id": binding["card_id"],
                        "expected_revision": next(
                            c["revision"]
                            for c in value["cards"]
                            if c["card_id"] == binding["card_id"]
                        ),
                    }
                ],
            },
        )
    outcome = handle.delete(session_id)
    store.invalidate_session(root, owner, session_id)
    learning_exploration.purge(root, owner, session_id)
    result_explanation.purge(owner, session_id, root)
    experiment_store.purge(root, owner, session_id)
    account_datasets.forget_selection(root, owner, session_id)
    chat_attachments.drop_session(root, owner, session_id)
    outcome["figures_removed"] = drop_session_figures(project_root, session_id)
    return outcome


def auto_update(root, owner, session_id, settings):
    """Write the conversation's general card once; method cards update only on request."""
    binding = public(root, owner, session_id)
    if binding:
        return None
    # Every conversation gets one method-less study card after its first completed
    # turn. Confirmed method cards are refreshed only when the user asks for it.
    from agent import study_topic

    try:
        return study_topic.generate(root, owner, session_id, settings, update_existing=False)
    except ValueError:
        return None
