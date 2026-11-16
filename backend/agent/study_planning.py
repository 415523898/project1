"""Evidence candidates and fixed phase boundaries; never writes or chooses edges."""

import hashlib
import json

from agent import study_binding, study_reference
from agent import study_graph as rules


def workflow(data, selected):
    selected = set(selected)
    if not selected <= set(data.get("read_cards", [])):
        stage, tools = "read", ["read_route"]
    elif not data.get("reference_read"):
        stage, tools = "reference", ["read_route", "lookup_reference"]
    elif not selected <= set(data.get("matches", {})):
        stage, tools = "identify", ["read_route", "lookup_reference", "match_cards"]
    elif data.get("audit", {}).get("ok"):
        stage, tools = "complete", ["read_route", "finish_route"]
    else:
        stage = "repair" if data.get("audit") else "plan"
        tools = [
            "read_route",
            "lookup_reference",
            "match_cards",
            "edit_connections",
            "arrange_cards",
            "audit_route",
        ]
        if stage == "repair":
            tools.append("report_route_blocked")
    return {
        "stage": stage,
        "allowed_tools": tools,
        "remaining_card_ids": sorted(selected - set(data.get("matches", {}))),
        "stalled_reviews": data.get("stalled_reviews", 0),
    }


def relation_candidates(graph, identified, reference, bindings):
    """Offer reference paths, explicit stages and quoted relation sections separately."""
    if not identified:
        return []
    ids = sorted(identified)
    plan = study_reference.build(graph, ids, identified, reference)
    edges = {rules.connection_identity(edge): dict(edge) for edge in plan["edges"]}
    present_pairs = {(edge["from_id"], edge["to_id"]) for edge in edges.values()}
    hints = {key: study_reference.content_hints(graph["cards"][key]) for key in ids}
    # Only the existing explicit-section validator can add a text-based order.
    # An incidental model name, a similar title or a desire for connectivity cannot.
    for a in ids:
        for b in ids:
            if a == b or study_binding.independent_same_method(bindings, a, b):
                continue
            edge = {"from_id": a, "to_id": b, "type": "suggested_next", "evidence_refs": []}
            if (a, b) in present_pairs:
                continue
            if not hints[a]["successors"] and not hints[b]["prerequisites"]:
                continue
            # Workflow stages are already in the plan. For additional pairs,
            # require an actual relation section rather than an inferred transit.
            basis = study_reference.content_order_evidence(graph, identified, edge, reference)
            if not basis:
                continue
            edge["why"] = "卡片正文明确列出前置或后续方法，按原文方向连接。"
            edge["basis_quotes"] = basis
            edges[rules.connection_identity(edge)] = edge
    if len(edges) > 500:
        rules.fail("可核验候选关系超过500条，请缩小本次整理范围。", "scope_too_large")
    candidates = []
    for edge in edges.values():
        a, b = edge["from_id"], edge["to_id"]
        if edge["type"] in rules.ORDERED and study_binding.independent_same_method(bindings, a, b):
            continue
        refs = edge.get("evidence_refs", [])
        basis = (
            "reference" if refs else "card_text" if edge.get("basis_quotes") else "experiment_steps"
        )
        detail = edge.get("basis_quotes") or (
            [
                {
                    "from_step": identified[a]["step"],
                    "to_step": identified[b]["step"],
                    "flow_id": identified[a]["flow_id"],
                }
            ]
            if basis == "experiment_steps"
            else [{"reference": ref} for ref in refs]
        )
        identity = json.dumps([a, b, edge["type"], detail], ensure_ascii=False, sort_keys=True)
        candidates.append(
            {
                **{key: edge[key] for key in ("from_id", "to_id", "type", "why", "evidence_refs")},
                "candidate_id": "candidate-"
                + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24],
                "basis_kind": basis,
                "basis": detail,
                "already_present": any(
                    rules.edge_identity(e) == rules.edge_identity(edge)
                    for e in graph["edges"].values()
                ),
            }
        )
    return sorted(candidates, key=lambda item: (item["from_id"], item["to_id"], item["type"]))


def record_review(data, audit):
    if audit["ok"]:
        data.pop("review_signature", None)
        data["stalled_reviews"] = 0
        return
    signature = json.dumps(
        [
            audit["graph_revision"],
            audit["layout_revision"],
            audit["issues"],
            data.get("matches", {}),
        ],
        sort_keys=True,
        ensure_ascii=False,
    )
    data["stalled_reviews"] = (
        data.get("stalled_reviews", 0) + 1 if data.get("review_signature") == signature else 1
    )
    data["review_signature"] = signature
    if data["stalled_reviews"] >= 3:
        rules.fail(
            "连续审查未取得进展，请补充具体依据或缩小整理范围；已保存步骤可整次撤回。",
            "route_no_progress",
            409,
        )
