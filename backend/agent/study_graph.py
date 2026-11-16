"""Pure study command validation. No file, model, or session writes occur here."""

import copy
import hashlib
import json
import math
import re
import uuid
from collections import deque

from config import (
    STUDY_GRAPH_MAX_COORDINATE as MAX_COORDINATE,
)
from config import (
    STUDY_GRAPH_MAX_WAYPOINTS as MAX_WAYPOINTS,
)

SCHEMA_VERSION = 2
TABLES = ("cards", "sources", "nodes", "edges", "edge_routes", "groups", "exclusions")
ID_FIELDS = dict(
    zip(
        TABLES,
        ("card_id", "source_id", "card_id", "edge_id", "edge_id", "group_id", "exclusion_id"),
    )
)
ORDERED = {"prerequisite", "suggested_next"}
EDGE_TYPES = ORDERED | {"alternative", "related"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class StudyError(ValueError):
    def __init__(self, message, code="invalid_change", status=400, **details):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details

    def public(self):
        return {"error": str(self), "code": self.code, **self.details}


def fail(message, code="invalid_change", status=400, **details):
    raise StudyError(message, code, status, **details)


def identifier(value, field="id"):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        fail(f"{field} 无效。")
    return value


def whitelist(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        fail(
            "字段缺失或含有不允许写入的字段。",
            fields=sorted(set(value) - set(allowed)) if isinstance(value, dict) else [],
        )


def coordinate(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > MAX_COORDINATE:
        fail("坐标必须有限且位于 -20000 至 20000。")
    return round(value, 3)


def integer(value, low=1, high=1000000):
    if type(value) is not int or not low <= value <= high:
        fail("整数超出支持范围。")
    return value


def boolean(value):
    if type(value) is not bool:
        fail("锁定值必须为布尔值。")
    return value


def choice(value, allowed, message):
    if not isinstance(value, str) or value not in allowed:
        fail(message)
    return value


def string(value, limit, blank=True):
    if not isinstance(value, str) or len(value) > limit or (not blank and not value.strip()):
        fail("文字内容为空或超出长度限制。")
    return value


def string_list(value, limit=256):
    if not isinstance(value, list) or len(value) > limit:
        fail("列表无效或过长。")
    return [string(item, 1000, False) for item in value]


def empty_graph():
    return {table: {} for table in TABLES}


def pair_fingerprint(edge):
    return ":".join(sorted((edge["from_id"], edge["to_id"])))


def human_fields(card):
    """Manual edits that still carry a human decision.

    ``body`` is retired: the card detail no longer edits it and the session format always
    stores it empty, so an old ``body`` marker must not protect a duplicate card forever.
    """
    return sorted(field for field in (card.get("manual_fields") or []) if field != "body")


def edge_identity(edge):
    """Ordered links retain direction; peer links have a canonical identity."""
    start, end = edge["from_id"], edge["to_id"]
    if edge["type"] not in ORDERED:
        start, end = sorted((start, end))
    return start, end, edge["type"]


def connection_identity(edge):
    """Identity of an editable connection, independent of its precise relation type."""
    start, end, _ = edge_identity(edge)
    return edge["type"] in ORDERED, start, end


def ordered_components(graph):
    """Iterative Kosaraju traversal, including isolated nodes and self loops."""
    outgoing = {key: set() for key in graph["nodes"]}
    incoming = {key: set() for key in outgoing}
    for edge in graph["edges"].values():
        a, b = edge["from_id"], edge["to_id"]
        if edge["type"] in ORDERED and a in outgoing and b in outgoing:
            outgoing[a].add(b)
            incoming[b].add(a)
    seen, finished = set(), []
    for root in sorted(outgoing):
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(sorted(outgoing[root])))]
        while stack:
            key, children = stack[-1]
            child = next(children, None)
            if child is None:
                finished.append(key)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child, iter(sorted(outgoing[child]))))
    seen, groups = set(), []
    for root in reversed(finished):
        if root in seen:
            continue
        group, todo = [], [root]
        seen.add(root)
        while todo:
            key = todo.pop()
            group.append(key)
            for parent in sorted(incoming[key]):
                if parent not in seen:
                    seen.add(parent)
                    todo.append(parent)
        groups.append(sorted(group))
    return groups


def resolve_levels(graph):
    """Pins are user numbers, never constraints. Auto numbers follow the condensed DAG."""
    groups = ordered_components(graph)
    membership = {key: index for index, group in enumerate(groups) for key in group}
    outgoing = {index: [] for index in range(len(groups))}
    parents = {index: set() for index in outgoing}
    for edge in graph["edges"].values():
        if edge["type"] not in ORDERED:
            continue
        a, b = membership[edge["from_id"]], membership[edge["to_id"]]
        if a != b:
            outgoing[a].append((edge["from_id"], b))
            parents[b].add(a)
    indegree = {key: len(values) for key, values in parents.items()}
    queue = deque(sorted(key for key in indegree if not indegree[key]))
    minimum, levels = dict.fromkeys(indegree, 1), {}
    while queue:
        index = queue.popleft()
        for key in groups[index]:
            pin = graph["nodes"][key].get("level_pin")
            levels[key] = pin if pin is not None else min(999, minimum[index])
        for start, target in outgoing[index]:
            minimum[target] = max(minimum[target], levels[start] + 1)
        for target in sorted({target for _, target in outgoing[index]}):
            indegree[target] -= 1
            if not indegree[target]:
                queue.append(target)
    return levels


def graph_warnings(graph):
    """Advisories only: graph shape and numbering never prevent a connection."""
    levels = resolve_levels(graph)
    warnings = []
    for group in ordered_components(graph):
        selected = set(group)
        edges = [
            edge["edge_id"]
            for edge in graph["edges"].values()
            if edge["type"] in ORDERED and {edge["from_id"], edge["to_id"]} <= selected
        ]
        if len(group) > 1 or edges:
            warnings.append(
                {
                    "code": "cycle",
                    "card_ids": group,
                    "edge_ids": sorted(edges),
                    "message": "连线形成回路，已正常保留。",
                }
            )
    reversed_edges = [
        edge
        for edge in graph["edges"].values()
        if edge["type"] in ORDERED and levels[edge["from_id"]] > levels[edge["to_id"]]
    ]
    if reversed_edges:
        warnings.append(
            {
                "code": "number_reversed",
                "card_ids": sorted(
                    {key for edge in reversed_edges for key in (edge["from_id"], edge["to_id"])}
                ),
                "edge_ids": sorted(edge["edge_id"] for edge in reversed_edges),
                "message": "存在从较大编号指向较小编号的连线，已正常保留。",
            }
        )
    return warnings


def validate_graph(graph):
    nodes, edges = graph["nodes"], graph["edges"]
    for node in nodes.values():
        if node["card_id"] not in graph["cards"]:
            fail("节点对应的卡片不存在。")
        if node.get("group_id") is not None and node["group_id"] not in graph["groups"]:
            fail("分组不存在。")
    pairs = {}
    for edge in edges.values():
        start, end = edge["from_id"], edge["to_id"]
        if start not in nodes or end not in nodes:
            fail("关系端点必须存在于本账号路线内。", "invalid_endpoint", edge_id=edge["edge_id"])
        if edge["type"] not in EDGE_TYPES:
            fail("未知关系类型。")
        pair = edge_identity(edge)
        if pair in pairs:
            fail(
                "相同方向和类型的连线已存在。",
                "duplicate_edge",
                409,
                edge_ids=[pairs[pair], edge["edge_id"]],
            )
        pairs[pair] = edge["edge_id"]
        if edge["type"] not in ORDERED:
            edge["from_id"], edge["to_id"] = pair[:2]
        if (
            edge["type"] == "prerequisite"
            and edge["created_by"] != "user"
            and not edge["evidence_refs"]
        ):
            fail("AI 必要前置缺少明确依据。", "evidence_required")
    for key, level in resolve_levels(graph).items():
        nodes[key]["level"] = level


CARD_FIELDS = {"type", "title", "summary", "body", "method_ids", "evidence_status"}
EDGE_FIELDS = {"from_id", "to_id", "type", "why", "evidence_refs"}
SOURCE_FIELDS = {
    "session_id",
    "event_refs",
    "experiment_id",
    "version",
    "adopted_facts",
    "topic_key",
    "turn_start_seq",
    "turn_number",
    "event_turns",
    "snapshot_fingerprint",
    "cutoff_seq",
    "precision",
    "fact_fingerprints",
}


def card_changes(changes):
    whitelist(changes, CARD_FIELDS)
    result = dict(changes)
    for field, limit in (("title", 60), ("summary", 200), ("body", 100000)):
        if field in result:
            string(result[field], limit, field != "title")
    if "type" in result:
        choice(result["type"], {"manual", "conversation", "method"}, "未知卡片类型。")
    if "method_ids" in result:
        string_list(result["method_ids"])
    if "evidence_status" in result:
        choice(
            result["evidence_status"],
            {"none", "user_provided", "snapshot", "partial", "missing"},
            "未知证据状态。",
        )
    return result


def source_value(value, card_id):
    whitelist(value, SOURCE_FIELDS)
    result = {
        "source_id": "source_" + uuid.uuid4().hex,
        "card_id": card_id,
        "session_id": None,
        "event_refs": [],
        "experiment_id": None,
        "version": None,
        "adopted_facts": [],
        "availability": "unknown",
        "revision": 0,
        **copy.deepcopy(value),
    }
    if result["session_id"] is not None:
        from agent.eventlog import SESSION_ID

        if not isinstance(result["session_id"], str) or not SESSION_ID.fullmatch(
            result["session_id"]
        ):
            fail("来源会话编号无效。")
    string_list(result["event_refs"])
    string_list(result["adopted_facts"])
    if result["experiment_id"] is not None:
        identifier(result["experiment_id"], "experiment_id")
    if result["version"] is not None:
        integer(result["version"])
    for field in ("turn_start_seq", "cutoff_seq", "turn_number"):
        if result.get(field) is not None:
            integer(result[field], 0)
    for field in ("topic_key", "snapshot_fingerprint"):
        if field in result:
            string(result[field], 128, False)
    if "precision" in result:
        choice(result["precision"], {"event", "legacy"}, "来源定位精度无效。")
    if "fact_fingerprints" in result:
        string_list(result["fact_fingerprints"])
    if "event_turns" in result:
        turns = result["event_turns"]
        if not isinstance(turns, dict) or not set(turns) <= set(result["event_refs"]):
            fail("来源轮次索引无效。")
        for number in turns.values():
            integer(number, 0)
    return result


def apply_commands(before, payload, actor="user"):
    """Apply a batch to a copy and validate its final state, returning ID mappings."""
    if actor not in {"user", "ai", "ai_session"}:
        fail("未知修改来源。", "invalid_actor", 403)
    whitelist(
        payload,
        {
            "schema_version",
            "operation_id",
            "base_graph_revision",
            "base_layout_revision",
            "operations",
            "scope",
            "delete_choice",
        },
        {"schema_version", "operation_id", "base_graph_revision", "operations"},
    )
    if type(payload["schema_version"]) is not int or payload["schema_version"] != SCHEMA_VERSION:
        fail("协议版本不兼容。", "schema_version")
    identifier(payload["operation_id"], "operation_id")
    integer(payload["base_graph_revision"], 0)
    if "base_layout_revision" in payload:
        integer(payload["base_layout_revision"], 0)
    operations = payload["operations"]
    if "delete_choice" in payload:
        choice(payload["delete_choice"], {"only", "both"}, "删除选项无效。")
    if (
        not isinstance(operations, list)
        or not (0 if actor != "user" else 1) <= len(operations) <= 500
    ):
        fail("一次变更需包含 1–500 个操作。")
    scope = payload.get("scope", {"kind": "workspace"})
    whitelist(scope, {"kind", "card_ids"}, {"kind"})
    choice(scope["kind"], {"workspace", "selection"}, "未知作用域。")
    selection = None
    if scope["kind"] == "selection":
        if not isinstance(scope.get("card_ids"), list) or len(scope["card_ids"]) > 10000:
            fail("选区需要 card_ids。")
        selection = set(identifier(key, "card_id") for key in scope["card_ids"])
        if selection - set(before["cards"]):
            fail("选区包含未知卡片。", "invalid_scope")
    elif "card_ids" in scope:
        fail("workspace 作用域不接受 card_ids。")
    graph, refs = copy.deepcopy(before), {}

    def resolve(value):
        identifier(value)
        return refs.get(value, value)

    def in_scope(*keys):
        if selection is not None and any(key not in selection for key in keys):
            fail("操作超出固定选区。", "scope_conflict", 409, card_ids=list(keys))

    def existing(table, key, operation):
        key = resolve(key)
        row = graph[table].get(key)
        if row is None:
            fail("对象不存在或不属于当前账号。", "not_found", 404)
        old = before[table].get(key)
        if old is not None:
            if (
                type(operation.get("expected_revision")) is not int
                or operation["expected_revision"] != old["revision"]
            ):
                fail(
                    "对象修订已变化。",
                    "object_conflict",
                    409,
                    object_id=key,
                    revision=old["revision"],
                )
        elif "expected_revision" in operation:
            fail("新建对象不接受 expected_revision。")
        if table in {"cards", "nodes"}:
            in_scope(key)
        elif table in {"edges", "edge_routes"}:
            edge = graph["edges"][key]
            in_scope(edge["from_id"], edge["to_id"])
        return row

    def new_id(operation, prefix):
        ref = identifier(operation.get("client_ref"), "client_ref")
        if ref in refs or any(ref in before[table] for table in TABLES):
            fail("候选引用重复或与正式 ID 冲突。", "duplicate_ref")
        key = prefix + "_" + uuid.uuid4().hex
        refs[ref] = key
        return key

    def exclude(
        kind,
        fingerprint,
        card_ids,
        session_ids=(),
        topic_fingerprint=None,
        why="用户删除",
        edge=None,
    ):
        key = "exclude_" + uuid.uuid4().hex
        if edge is not None:
            session_ids = [
                source["session_id"]
                for source in graph["sources"].values()
                if source["card_id"] in card_ids and source.get("session_id")
            ]
        graph["exclusions"][key] = {
            "exclusion_id": key,
            "kind": kind,
            "fingerprint": fingerprint,
            "card_ids": list(card_ids),
            "session_ids": sorted(set(session_ids)),
            "scope": {"kind": "sources", "session_ids": sorted(set(session_ids))}
            if session_ids
            else {"kind": "workspace"},
            "topic_fingerprint": topic_fingerprint,
            "why": string(why, 4000),
            "relation": {field: edge[field] for field in ("from_id", "to_id", "type")}
            if edge
            else None,
            "revision": 0,
        }

    def remove_edges(card_id):
        for key, edge in list(graph["edges"].items()):
            if card_id in (edge["from_id"], edge["to_id"]):
                in_scope(edge["from_id"], edge["to_id"])
                exclude("edge", pair_fingerprint(edge), [edge["from_id"], edge["to_id"]], edge=edge)
                graph["edges"].pop(key)
                graph["edge_routes"].pop(key, None)

    for operation in operations:
        if not isinstance(operation, dict):
            fail("操作必须是对象。")
        op = operation.get("op")
        if not isinstance(op, str):
            fail("操作名必须为字符串。")
        if actor == "ai" and op not in {"create_edge", "update_edge", "delete_edge"}:
            fail("AI 整理仅能修改关系。", "invalid_ai_operation")
        if actor == "ai_session" and op not in {
            "create_card",
            "update_card",
            "add_source",
            "add_node",
            "create_group",
            "create_edge",
            "update_edge",
            "delete_edge",
            "retire_session_card",
            "move_session_nodes",
        }:
            fail("会话整理不能删除卡片或移动已有节点。", "invalid_ai_operation")
        common = {"op", "expected_revision"}
        if op == "create_card":
            whitelist(
                operation, {"op", "client_ref", "values", "sources"}, {"client_ref", "values"}
            )
            values = card_changes(operation["values"])
            if "title" not in values:
                fail("新卡片需要标题。")
            key = new_id(operation, "card")
            if selection is not None:
                selection.add(key)
            graph["cards"][key] = {
                "card_id": key,
                "type": "manual",
                "title": "",
                "summary": "",
                "body": "",
                "method_ids": [],
                "evidence_status": "none",
                "manual_fields": sorted(values) if actor == "user" else [],
                "created_by": actor,
                "revision": 0,
                **values,
            }
            sources = operation.get("sources", [])
            if not isinstance(sources, list) or len(sources) > 128:
                fail("来源列表无效。")
            for source in sources:
                row = source_value(source, key)
                graph["sources"][row["source_id"]] = row
        elif op == "update_card":
            whitelist(operation, common | {"card_id", "changes"}, {"card_id", "changes"})
            row = existing("cards", operation["card_id"], operation)
            changes = card_changes(operation["changes"])
            if actor == "ai_session" and (
                row.get("created_by") != "ai_session" or set(changes) & set(row["manual_fields"])
            ):
                fail("会话整理不能覆盖人工卡片或人工修改字段。", "manual_protected", 409)
            row.update(changes)
            if actor == "user":
                row["manual_fields"] = sorted(set(row["manual_fields"]) | set(changes))
        elif op == "add_source":
            whitelist(operation, common | {"card_id", "source"}, {"card_id", "source"})
            card = existing("cards", operation["card_id"], operation)
            row = source_value(operation["source"], card["card_id"])
            graph["sources"][row["source_id"]] = row
        elif op in {"delete_card", "remove_node", "retire_session_card"}:
            whitelist(operation, common | {"card_id"}, {"card_id"})
            if op == "retire_session_card":
                # Consolidating this session's own duplicates under one card is the only
                # path that may retire a card. Cards the user made, cards another flow
                # made, and any card with manual edits stay untouchable.
                row = existing("cards", operation["card_id"], operation)
                if row.get("created_by") != "ai_session" or human_fields(row):
                    fail(
                        "会话整理只能合并本会话生成且未被人工修改的卡片。", "manual_protected", 409
                    )
            else:
                row = existing(
                    "cards" if op == "delete_card" else "nodes", operation["card_id"], operation
                )
            key = row["card_id"]
            remove_edges(key)
            graph["nodes"].pop(key, None)
            sources = [value for value in graph["sources"].values() if value["card_id"] == key]
            card = graph["cards"][key]
            topic = {field: card[field] for field in ("title", "summary", "body", "method_ids")}
            topic_digest = hashlib.sha256(
                json.dumps(topic, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            retiring = op != "remove_node"
            exclude(
                "card" if retiring else "route",
                key,
                [key],
                [s["session_id"] for s in sources if s["session_id"]],
                topic_digest,
                why="同一方法的重复卡片已合并为一张" if op == "retire_session_card" else "用户删除",
            )
            if retiring:
                graph["cards"].pop(key)
                for source in sources:
                    graph["sources"].pop(source["source_id"])
        elif op == "add_node":
            whitelist(
                operation, common | {"card_id", "x", "y", "group_id", "level_pin"}, {"card_id"}
            )
            card = existing("cards", operation["card_id"], operation)
            key = card["card_id"]
            if key in graph["nodes"]:
                fail("卡片已在路线中。", "duplicate_node", 409)
            group_id = (
                resolve(operation["group_id"]) if operation.get("group_id") is not None else None
            )
            pin = (
                integer(operation["level_pin"], 1, 999)
                if operation.get("level_pin") is not None
                else None
            )
            graph["nodes"][key] = {
                "card_id": key,
                "node_id": key,
                "x": coordinate(operation.get("x", 40)),
                "y": coordinate(operation.get("y", 40)),
                "group_id": group_id,
                "position_locked": False,
                "level_pin": pin,
                "level": pin or 1,
                "revision": 0,
            }
            for eid, value in list(graph["exclusions"].items()):
                if value["kind"] == "route" and value["fingerprint"] == key:
                    graph["exclusions"].pop(eid)
        elif op in {"move_nodes", "move_session_nodes"}:
            whitelist(operation, {"op", "nodes"}, {"nodes"})
            if not isinstance(operation["nodes"], list) or not 1 <= len(operation["nodes"]) <= 500:
                fail("移动节点列表无效。")
            moved = set()
            for item in operation["nodes"]:
                whitelist(item, {"card_id", "x", "y", "expected_revision"}, {"card_id", "x", "y"})
                row = existing("nodes", item["card_id"], item)
                if row["card_id"] in moved:
                    fail("同次移动含有重复节点。")
                moved.add(row["card_id"])
                if (
                    op == "move_session_nodes"
                    and graph["cards"][row["card_id"]].get("created_by") != "ai_session"
                ):
                    fail("会话整理只能重排本会话生成的卡片。", "manual_protected", 409)
                if row["position_locked"]:
                    fail("节点位置已固定。", "position_locked", 409)
                row.update(x=coordinate(item["x"]), y=coordinate(item["y"]))
        elif op in {"set_node_lock", "set_level_pin", "set_node_group"}:
            field = {
                "set_node_lock": "position_locked",
                "set_level_pin": "level_pin",
                "set_node_group": "group_id",
            }[op]
            whitelist(operation, common | {"card_id", field}, {"card_id", field})
            row = existing("nodes", operation["card_id"], operation)
            value = operation[field]
            row[field] = (
                boolean(value)
                if field == "position_locked"
                else (
                    None
                    if value is None
                    else integer(value, 1, 999)
                    if field == "level_pin"
                    else resolve(value)
                )
            )
        elif op == "create_edge":
            whitelist(
                operation,
                {"op", "client_ref"} | EDGE_FIELDS,
                {"client_ref", "from_id", "to_id", "type"},
            )
            key = new_id(operation, "edge")
            start, end = resolve(operation["from_id"]), resolve(operation["to_id"])
            in_scope(start, end)
            row = {
                "edge_id": key,
                "from_id": start,
                "to_id": end,
                "type": choice(operation["type"], EDGE_TYPES, "未知关系类型。"),
                "why": string(operation.get("why", "用户设定"), 4000),
                "evidence_refs": string_list(operation.get("evidence_refs", [])),
                "created_by": actor,
                "origin": "user_defined" if actor == "user" else "ai_suggestion",
                "manual_fields": sorted(EDGE_FIELDS) if actor == "user" else [],
                "semantic_locked": False,
                "revision": 0,
            }
            graph["edges"][key] = row
            graph["edge_routes"][key] = {
                "edge_id": key,
                "mode": "auto",
                "source_side": "auto",
                "target_side": "auto",
                "waypoints": [],
                "route_locked": False,
                "revision": 0,
            }
            for eid, value in list(graph["exclusions"].items()):
                if value["kind"] == "edge" and value["fingerprint"] == pair_fingerprint(row):
                    graph["exclusions"].pop(eid)
        elif op in {"update_edge", "delete_edge", "set_edge_lock", "set_edge_route"}:
            fields = {
                "update_edge": {"changes"},
                "delete_edge": set(),
                "set_edge_lock": {"semantic_locked"},
                "set_edge_route": {"changes"},
            }[op]
            whitelist(
                operation,
                common | {"edge_id"} | fields | ({"why"} if op == "delete_edge" else set()),
                {"edge_id"} | fields,
            )
            row = existing(
                "edge_routes" if op == "set_edge_route" else "edges",
                operation["edge_id"],
                operation,
            )
            key = row["edge_id"]
            if actor == "ai_session" and (
                row.get("created_by") != "ai_session"
                or row.get("manual_fields")
                or row.get("semantic_locked")
                or graph["edge_routes"][key]["route_locked"]
            ):
                fail("会话整理不能改动人工或固定关系。", "manual_protected", 409)
            if op == "delete_edge":
                if actor == "user":
                    exclude(
                        "edge",
                        pair_fingerprint(row),
                        [row["from_id"], row["to_id"]],
                        why=operation.get("why", "用户删除关系"),
                        edge=row,
                    )
                graph["edges"].pop(key)
                graph["edge_routes"].pop(key, None)
            elif op == "set_edge_lock":
                row["semantic_locked"] = boolean(operation["semantic_locked"])
            elif op == "update_edge":
                changes = operation["changes"]
                whitelist(changes, EDGE_FIELDS)
                if row["semantic_locked"] and any(
                    changes.get(k, row[k]) != row[k] for k in changes
                ):
                    fail("关系已固定，先显式解除固定再编辑。", "semantic_locked", 409)
                for field, value in changes.items():
                    if field == "type":
                        choice(value, EDGE_TYPES, "未知关系类型。")
                    row[field] = (
                        resolve(value)
                        if field in {"from_id", "to_id"}
                        else string(value, 4000)
                        if field == "why"
                        else string_list(value)
                        if field == "evidence_refs"
                        else value
                    )
                in_scope(row["from_id"], row["to_id"])
                if actor == "user":
                    row["manual_fields"] = sorted(set(row["manual_fields"]) | set(changes))
            else:
                changes = operation["changes"]
                whitelist(
                    changes, {"mode", "source_side", "target_side", "waypoints", "route_locked"}
                )
                if row["route_locked"] and any(
                    changes.get(k, row[k]) != row[k] for k in changes if k != "route_locked"
                ):
                    fail("走线已固定，先显式解除固定再编辑。", "route_locked", 409)
                for field, value in changes.items():
                    if field == "mode":
                        choice(value, {"auto", "guided"}, "未知走线模式。")
                    if field in {"source_side", "target_side"}:
                        choice(value, {"auto", "left", "right", "top", "bottom"}, "未知端口。")
                    if field == "route_locked":
                        boolean(value)
                    if field == "waypoints":
                        if not isinstance(value, list) or len(value) > MAX_WAYPOINTS:
                            fail("走线最多允许 8 个引导点。")
                        value = [
                            dict(x=coordinate(point["x"]), y=coordinate(point["y"]))
                            for point in value
                            if _valid_point(point)
                        ]
                    row[field] = value
                if (
                    actor == "user"
                    and "mode" not in changes
                    and any(
                        field in changes for field in ("source_side", "target_side", "waypoints")
                    )
                ):
                    row["mode"] = "guided"
        elif op in {"create_group", "update_group", "delete_group"}:
            if selection is not None:
                fail("分组编辑需要工作区作用域。", "scope_conflict", 409)
            if op == "create_group":
                whitelist(operation, {"op", "client_ref", "values"}, {"client_ref", "values"})
                key = new_id(operation, "group")
                row = {
                    "group_id": key,
                    "title": "",
                    "description": "",
                    "sort_hint": 0,
                    "revision": 0,
                }
                graph["groups"][key] = row
                changes = operation["values"]
            else:
                whitelist(
                    operation,
                    common | {"group_id"} | ({"changes"} if op == "update_group" else set()),
                    {"group_id"} | ({"changes"} if op == "update_group" else set()),
                )
                row = existing("groups", operation["group_id"], operation)
                changes = operation.get("changes", {})
            if op == "delete_group":
                graph["groups"].pop(row["group_id"])
                for node in graph["nodes"].values():
                    if node["group_id"] == row["group_id"]:
                        node["group_id"] = None
            else:
                whitelist(changes, {"title", "description", "sort_hint"})
                if op == "create_group" and "title" not in changes:
                    fail("分组需要标题。")
                for field, value in changes.items():
                    row[field] = (
                        integer(value, -1000000, 1000000)
                        if field == "sort_hint"
                        else string(
                            value, 4000 if field == "description" else 100, field != "title"
                        )
                    )
        else:
            fail("未知操作。", operation=op if isinstance(op, str) else None)
    validate_graph(graph)
    return graph, refs


def _valid_point(value):
    whitelist(value, {"x", "y"}, {"x", "y"})
    return True


def changes_between(before, after):
    patch = []
    for table in TABLES:
        for key in sorted(set(before[table]) | set(after[table])):
            old, new = before[table].get(key), after[table].get(key)
            if old != new:
                patch.append({"table": table, "id": key, "before": old, "after": new})
    return patch


def revision_kinds(patch):
    semantic, layout = False, False
    for change in patch:
        table, old, new = change["table"], change["before"], change["after"]
        if table == "edge_routes":
            # A default route follows edge lifecycle; only explicit presentation
            # edits consume layout revisions or invalidate a layout preview.
            layout |= old is not None and new is not None
            if old is None and new is not None:
                layout |= (
                    new["mode"] != "auto"
                    or new["waypoints"] != []
                    or new["route_locked"]
                    or new["source_side"] != "auto"
                    or new["target_side"] != "auto"
                )
        elif table == "nodes" and old is not None and new is not None:
            semantic |= any(old.get(k) != new.get(k) for k in ("group_id", "level_pin", "level"))
            layout |= any(old.get(k) != new.get(k) for k in ("x", "y", "position_locked"))
        else:
            semantic = True
    return semantic, layout
