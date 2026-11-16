"""Conflict boundaries shared by card summaries and route workers."""

import json


def active_route(db, card_ids=None):
    """Return a live route job touching these cards; unknown legacy scopes conflict."""
    from agent.study_tools import live

    selected = set(card_ids) if card_ids is not None else None
    for identifier, raw in db.execute("SELECT job_id,payload FROM jobs WHERE status='running'"):
        data = json.loads(raw)
        if data.get("strategy") == "session_v1" or not live(identifier, data):
            continue
        scope = data.get("card_ids")
        if selected is None or not scope or selected.intersection(scope):
            return identifier
    return None


def route_fingerprint(graph, card_ids):
    """Include route evidence, protected borders and every layout obstacle.

    A summary of an unselected card changes neither this route's evidence nor
    its geometry, so it must not invalidate a model step or its latest audit.
    """
    from agent.study_store import fingerprint

    selected = set(card_ids)
    edges = {
        key: row for key, row in graph["edges"].items() if {row["from_id"], row["to_id"]} & selected
    }
    groups = {node.get("group_id") for key, node in graph["nodes"].items() if key in selected}
    return fingerprint(
        {
            "cards": {key: row for key, row in graph["cards"].items() if key in selected},
            "nodes": graph["nodes"],
            "groups": {key: row for key, row in graph["groups"].items() if key in groups},
            "edges": edges,
            "edge_routes": {key: row for key, row in graph["edge_routes"].items() if key in edges},
            "sources": {
                key: row for key, row in graph["sources"].items() if row["card_id"] in selected
            },
            "exclusions": {
                key: row
                for key, row in graph["exclusions"].items()
                if selected.intersection(row["card_ids"])
            },
        }
    )
