"""Stable columns for peers and continuous rows for linear learning paths."""

from collections import defaultdict
from statistics import median

from agent.study_graph import ORDERED, coordinate, fail, resolve_levels
from config import (
    STUDY_LAYOUT_CLEARANCE as CLEARANCE,
)
from config import (
    STUDY_LAYOUT_COLUMN as COLUMN,
)
from config import (
    STUDY_LAYOUT_GROUP_GAP as GROUP_GAP,
)
from config import (
    STUDY_LAYOUT_HEIGHT as HEIGHT,
)
from config import (
    STUDY_LAYOUT_ROW as ROW,
)
from config import (
    STUDY_LAYOUT_WIDTH as WIDTH,
)


def automatic_routes(graph, card_ids):
    """Face automatic AI links toward the new columns; preserve user choices."""
    selected, routes = set(card_ids), {}
    for key, edge in graph["edges"].items():
        if (
            not {edge["from_id"], edge["to_id"]} <= selected
            or edge.get("created_by") != "ai"
            or edge.get("manual_fields")
            or edge.get("semantic_locked")
        ):
            continue
        route = graph["edge_routes"][key]
        if route.get("route_locked") or route.get("mode") == "guided":
            continue
        source, target = graph["nodes"][edge["from_id"]], graph["nodes"][edge["to_id"]]
        dx, dy = target["x"] - source["x"], target["y"] - source["y"]
        if abs(dx) >= WIDTH:
            sides = ("right", "left") if dx > 0 else ("left", "right")
        elif abs(dy) >= HEIGHT:
            sides = ("bottom", "top") if dy > 0 else ("top", "bottom")
        else:
            continue
        values = dict(zip(("source_side", "target_side"), sides))
        if any(route.get(field) != value for field, value in values.items()):
            routes[key] = values
    return routes


def components(graph, card_ids, ordered_only=False):
    """Stable weak components, optionally restricted to relations expressing a sequence."""
    remaining, neighbors, groups = set(card_ids), defaultdict(set), []
    for edge in graph["edges"].values():
        a, b = edge["from_id"], edge["to_id"]
        if a in remaining and b in remaining and (not ordered_only or edge["type"] in ORDERED):
            neighbors[a].add(b)
            neighbors[b].add(a)
    while remaining:
        todo, group = [min(remaining)], set()
        while todo:
            key = todo.pop()
            if key not in group:
                group.add(key)
                todo.extend(neighbors[key] - group)
        remaining -= group
        groups.append(sorted(group))
    return sorted(groups, key=lambda group: (-len(group), group))


def _intersects(a, b):
    return (
        a["x"] < b["x"] + WIDTH + CLEARANCE
        and a["x"] + WIDTH + CLEARANCE > b["x"]
        and a["y"] < b["y"] + HEIGHT + CLEARANCE
        and a["y"] + HEIGHT + CLEARANCE > b["y"]
    )


def _rows(keys, columns, parents, children, cards, locked=()):
    """Center branches while treating every uninterrupted linear chain as one row."""
    by_column, offsets = defaultdict(list), {}
    for key in keys:
        by_column[columns[key]].append(key)
    for values in by_column.values():
        values.sort(key=lambda key: (cards[key]["title"], key))
        offsets.update({key: i - (len(values) - 1) / 2 for i, key in enumerate(values)})
    for forward in (True, False, True):
        neighbors = parents if forward else children
        for column in sorted(by_column, reverse=not forward):
            values = by_column[column]

            def order(key):
                adjacent = [offsets[n] for n in neighbors[key] if n in offsets]
                return (median(adjacent) if adjacent else offsets[key], cards[key]["title"], key)

            values.sort(key=order)
            offsets.update({key: i - (len(values) - 1) / 2 for i, key in enumerate(values)})
    roots = dict(zip(keys, keys))

    def find(key):
        while roots[key] != key:
            roots[key] = roots[roots[key]]
            key = roots[key]
        return key

    for key in keys:
        if len(children[key]) == 1 and key not in locked:
            child = next(iter(children[key]))
            if child in roots and child not in locked and len(parents[child]) == 1:
                roots[find(child)] = find(key)
    blocks = defaultdict(list)
    for key in keys:
        blocks[find(key)].append(key)
    preferred = {block: median(offsets[key] for key in values) for block, values in blocks.items()}
    ordered = sorted(
        blocks,
        key=lambda block: (
            preferred[block],
            min(cards[key]["title"] for key in blocks[block]),
            block,
        ),
    )
    order = {block: i for i, block in enumerate(ordered)}
    above = defaultdict(set)
    for values in by_column.values():
        column_blocks = sorted({find(key) for key in values}, key=order.get)
        for a, b in zip(column_blocks, column_blocks[1:]):
            above[b].add(a)
    y = {}
    for block in ordered:
        y[block] = max([preferred[block]] + [y[a] + 1 for a in above[block]])
    top = min(y.values())
    preferred = {key: y[find(key)] - top for key in keys}
    return _center_rows(keys, columns, parents, children, preferred, locked)


def _center_rows(keys, columns, parents, children, preferred, locked):
    """Solve row alignment, branch medians and spacing as one constraint system.

    The barycentric ordering above is deterministic, but spacing a crowded column
    can move a branch without moving its parent. Reapplying the heuristic cannot
    fix that. A small linear program projects it onto the actual audit constraints.
    """
    keys = sorted(keys)
    locked = set(locked)
    linear = [
        (a, b)
        for a in keys
        for b in children[a]
        if len(children[a]) == len(parents[b]) == 1 and not {a, b} & locked
    ]
    centers = []
    for key in keys:
        for adjacent, reverse in ((parents[key], children), (children[key], parents)):
            if (
                len(adjacent) > 1
                and all(len(reverse[n]) == 1 for n in adjacent)
                and len({columns[n] for n in adjacent}) == 1
                and not ({key} | adjacent) & locked
            ):
                ordered = sorted(adjacent, key=lambda n: (preferred[n], n))
                centers.append((key, ordered[(len(ordered) - 1) // 2], ordered[len(ordered) // 2]))
    if all(abs(preferred[key] - (preferred[a] + preferred[b]) / 2) < 1e-8 for key, a, b in centers):
        return preferred

    # scipy is a core runtime dependency; import only for graphs needing projection.
    from scipy.optimize import linprog

    size, index = len(keys), {key: i for i, key in enumerate(keys)}
    dimensions = size * 2 + 1
    equalities, equal_values, inequalities, upper_values = [], [], [], []

    def equation(values):
        row = [0.0] * dimensions
        for key, value in values:
            row[index[key]] += value
        equalities.append(row)
        equal_values.append(0.0)

    for a, b in linear:
        equation([(a, 1), (b, -1)])
    for key, a, b in centers:
        equation([(key, 1), (a, -0.5), (b, -0.5)])
    by_column = defaultdict(list)
    for key in keys:
        if key not in locked:
            by_column[columns[key]].append(key)
    for values in by_column.values():
        values.sort(key=lambda key: (preferred[key], key))
        for a, b in zip(values, values[1:]):
            row = [0.0] * dimensions
            row[index[a]], row[index[b]] = 1, -1
            inequalities.append(row)
            upper_values.append(-1)
    for key, i in index.items():
        for sign in (1, -1):
            row = [0.0] * dimensions
            row[i], row[size + i] = sign, -1
            inequalities.append(row)
            upper_values.append(sign * preferred[key])
        row = [0.0] * dimensions
        row[i], row[-1] = 1, -1
        inequalities.append(row)
        upper_values.append(0)
    solution = linprog(
        [0.0] * size + [1.0] * size + [0.05],
        A_ub=inequalities,
        b_ub=upper_values,
        A_eq=equalities or None,
        b_eq=equal_values or None,
        bounds=[(preferred[key], preferred[key]) if key in locked else (0, None) for key in keys]
        + [(0, None)] * (size + 1),
        method="highs",
    )
    if not solution.success:
        fail(
            "当前关系无法同时满足同行、分支居中与卡片间距，请检查冲突关系或固定位置。",
            "layout_blocked",
            409,
        )
    rows = {key: round(float(solution.x[i]), 6) for key, i in index.items()}
    top = min(rows.values())
    return {key: value - top for key, value in rows.items()}


def ranks(graph, card_ids):
    """Use exactly the same numbers as cards, including pins and cyclic routes."""
    levels = resolve_levels(graph)
    return {key: levels[key] for key in card_ids}


def forward_edges(graph, card_ids):
    """Only increasing numbers constrain geometry; every other link is still rendered."""
    levels = ranks(graph, card_ids)
    return [
        edge
        for edge in graph["edges"].values()
        if edge["type"] in ORDERED
        and edge["from_id"] in levels
        and edge["to_id"] in levels
        and levels[edge["from_id"]] < levels[edge["to_id"]]
    ]


def arrange(graph, card_ids, plan=None):
    selected = set(card_ids)
    nodes = {key: graph["nodes"][key] for key in sorted(selected)}
    if not any(not node["position_locked"] for node in nodes.values()):
        return {}
    # Numbers determine columns. Reverse, peer and cyclic links cannot contradict rows.
    ranks_ = ranks(graph, selected)
    parents, children = defaultdict(set), defaultdict(set)
    edges = forward_edges(graph, selected)
    for edge in edges:
        if edge["type"] in ORDERED and {edge["from_id"], edge["to_id"]} <= selected:
            parents[edge["to_id"]].add(edge["from_id"])
            children[edge["from_id"]].add(edge["to_id"])
    levels = sorted(set(ranks_.values()))
    columns = {key: levels.index(ranks_[key]) for key in nodes}
    width = (len(levels) - 1) * COLUMN
    if width > 40000:
        fail("学习链过长，当前画布范围无法容纳。", "layout_blocked", 409)
    anchors = [
        node["x"] - columns[key] * COLUMN for key, node in nodes.items() if node["position_locked"]
    ]
    base_x = (
        median(anchors)
        if anchors
        else (plan or {}).get("base_x", min(node["x"] for node in nodes.values()))
    )
    base_x = max(-20000, min(base_x, 20000 - width))
    positions, occupied = (
        {},
        [
            {"x": node["x"], "y": node["y"]}
            for key, node in graph["nodes"].items()
            if key not in selected or node["position_locked"]
        ],
    )
    cursor = max(-20000, min(node["y"] for node in nodes.values()))
    groups = components(graph, selected)
    isolated_ids = {group[0] for group in groups if len(group) == 1}
    # Repeated whole-method cards remain parallel in one column even in the pending area.
    cohorts = defaultdict(list)
    for key in sorted(isolated_ids):
        methods = tuple(sorted(graph["cards"][key].get("method_ids", [])))
        cohorts[methods or (key,)].append(key)
    groups = [group for group in groups if len(group) > 1] + list(cohorts.values())
    groups.sort(
        key=lambda values: (
            set(values) <= isolated_ids,
            min(columns[key] for key in values),
            min(graph["cards"][key]["title"] for key in values),
            values,
        )
    )
    locked = {key for key, node in nodes.items() if node["position_locked"]}
    shelf_x, shelf_bottom = base_x, cursor
    isolated_columns = None
    shelf_width = max(
        COLUMN * 3 + WIDTH,
        max(
            (max(columns[k] for k in group) - min(columns[k] for k in group)) * COLUMN + WIDTH
            for group in groups
        ),
    )
    for keys in groups:
        rows = _rows(keys, columns, parents, children, graph["cards"], locked)
        first_column = min(columns[key] for key in keys)
        group_width = (max(columns[key] for key in keys) - first_column) * COLUMN + WIDTH
        anchored = bool(set(keys) & locked)
        isolated = set(keys) <= isolated_ids
        isolated_column = None
        if isolated and not anchored:
            if isolated_columns is None:
                top = (
                    shelf_bottom + GROUP_GAP
                    if any(key not in isolated_ids for key in selected)
                    else cursor
                )
                isolated_columns = [top] * 3
            isolated_column = min(range(3), key=lambda index: (isolated_columns[index], index))
            shelf_x = min(base_x, 20000 - 2 * COLUMN) + isolated_column * COLUMN
        elif not anchored:
            # Connected groups use shelves; isolated method cohorts use the grid below.
            if shelf_x > base_x and shelf_x - base_x + group_width > shelf_width:
                cursor, shelf_x = shelf_bottom + GROUP_GAP, base_x
        group_x = (
            base_x
            if anchored
            else min(
                shelf_x - first_column * COLUMN, 20000 - max(columns[key] for key in keys) * COLUMN
            )
        )
        anchors_y = [
            nodes[key]["y"] - rows[key] * ROW for key in keys if nodes[key]["position_locked"]
        ]
        base_y = cursor
        if anchors_y:
            base_y = median(anchors_y)
        elif isolated_column is not None:
            base_y = isolated_columns[isolated_column]
        max_row = max(rows.values())
        base_y = max(-20000, min(base_y, 20000 - max_row * ROW))
        while True:
            candidates = {
                key: {"x": group_x + columns[key] * COLUMN, "y": base_y + rows[key] * ROW}
                for key in keys
                if not nodes[key]["position_locked"]
            }
            if not any(
                _intersects(point, obstacle)
                for point in candidates.values()
                for obstacle in occupied
            ):
                break
            base_y += ROW
            if base_y + max_row * ROW > 20000:
                fail("固定卡片阻挡布局，当前范围无法容纳完整流程。", "layout_blocked", 409)
        for key, point in candidates.items():
            point = {axis: coordinate(value) for axis, value in point.items()}
            occupied.append(point)
            if any(point[axis] != nodes[key][axis] for axis in ("x", "y")):
                positions[key] = point
        shelf_bottom = max(
            [shelf_bottom, base_y + max_row * ROW + HEIGHT]
            + [nodes[key]["y"] + HEIGHT for key in keys if nodes[key]["position_locked"]]
        )
        shelf_x = group_x + (first_column * COLUMN) + group_width + GROUP_GAP
        if isolated_column is not None:
            isolated_columns[isolated_column] = base_y + max_row * ROW + ROW
        if anchored:
            cursor, shelf_x = shelf_bottom + GROUP_GAP, base_x
    candidate = {
        **graph,
        "nodes": {key: {**node, **positions.get(key, {})} for key, node in graph["nodes"].items()},
    }
    issues, _ = audit_geometry(candidate, selected)
    if issues:
        fail(
            "当前布局约束存在冲突，未保存坐标，请检查固定位置或冲突关系。",
            "layout_blocked",
            409,
            issues=issues,
        )
    return positions


def audit_geometry(graph, card_ids):
    """The geometry contract shared with the tool audit and layout regression tests."""
    selected, nodes = set(card_ids), graph["nodes"]
    issues, warnings, overlaps = [], [], []
    for a in sorted(selected):
        for b in sorted(nodes):
            if b == a or b in selected and b < a:
                continue
            if (
                abs(nodes[a]["x"] - nodes[b]["x"]) < WIDTH
                and abs(nodes[a]["y"] - nodes[b]["y"]) < HEIGHT
            ):
                (
                    warnings
                    if nodes[a]["position_locked"] and nodes[b]["position_locked"]
                    else overlaps
                ).append({"code": "overlap", "card_ids": [a, b]})
    if overlaps:
        issues.append({"code": "overlap", "pairs": overlaps[:50]})
    by_level, levels = defaultdict(list), ranks(graph, selected)
    for index, group in enumerate(components(graph, selected)):
        for key in group:
            if not nodes[key]["position_locked"]:
                by_level[(index, levels[key])].append(key)
    misplaced = [keys for keys in by_level.values() if len({nodes[key]["x"] for key in keys}) > 1]
    if misplaced:
        issues.append({"code": "peer_columns", "groups": misplaced})
    parents, children = defaultdict(set), defaultdict(set)
    ordered = forward_edges(graph, selected)
    for edge in ordered:
        parents[edge["to_id"]].add(edge["from_id"])
        children[edge["from_id"]].add(edge["to_id"])
    rows, backwards = [], []
    for edge in ordered:
        a, b = edge["from_id"], edge["to_id"]
        if nodes[a]["position_locked"] or nodes[b]["position_locked"]:
            continue
        if nodes[b]["x"] < nodes[a]["x"] + WIDTH:
            backwards.append([a, b])
        if len(children[a]) == len(parents[b]) == 1 and abs(nodes[a]["y"] - nodes[b]["y"]) > 0.01:
            rows.append([a, b])
    if backwards:
        issues.append({"code": "backwards_columns", "pairs": backwards})
    if rows:
        issues.append({"code": "linear_rows", "pairs": rows})
    off_center = []
    for key in sorted(selected):
        for adjacent, reverse in ((parents[key], children), (children[key], parents)):
            if (
                len(adjacent) > 1
                and all(len(reverse[n]) == 1 for n in adjacent)
                and len({nodes[n]["x"] for n in adjacent}) == 1
                and not any(nodes[n]["position_locked"] for n in {key} | adjacent)
            ):
                middle = median(nodes[n]["y"] for n in adjacent)
                if abs(nodes[key]["y"] - middle) > 0.01:
                    off_center.append({"card_id": key, "expected_y": middle})
    if off_center:
        issues.append({"code": "branch_centering", "cards": off_center})
    return issues, warnings
