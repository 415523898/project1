"""Conversation read projections assembled from the existing scoped stores."""

from agent import eventlog, experiment_store, runtime, study_store
from engine import account_datasets


def listing(root, owner):
    from agent import study_binding

    sessions = eventlog.Store(root, owner).list()
    bindings = study_binding.all_bindings(root, owner)
    with_cards = study_store.workspace(root, owner).get("cards", []) if bindings else []
    ids = {card["card_id"] for card in with_cards}
    for session in sessions:
        if session["id"] in bindings:
            session["binding"] = {
                **bindings[session["id"]],
                "card_missing": bindings[session["id"]]["card_id"] not in ids,
            }
    return {"sessions": sessions}


def get(root, owner, session_id):
    record = eventlog.Store(root, owner).get(session_id)
    record["message_actions"] = {"revision": True, "fork": True}
    record["experiment_sidebar"] = experiment_store.public(
        experiment_store.load(root, owner, session_id, record["events"])
    )
    record["selected_dataset"] = account_datasets.selection(root, owner, session_id)
    record["run"] = runtime.RUNTIME.conversation_status(root, owner, session_id)
    return record
