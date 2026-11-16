"""Account-local study workspace transactions."""

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from agent import study_graph as graph_rules
from agent import study_history
from agent.study_graph import StudyError, fail
from config import STUDY_DATABASE_TIMEOUT_SECONDS
from config import (
    STUDY_STORE_HISTORY_RETENTION_DAYS as HISTORY_RETENTION_DAYS,
)

SCHEMA_VERSION = 2
EDGE_COLUMNS = """(edge_id TEXT PRIMARY KEY,
from_id TEXT NOT NULL REFERENCES nodes(card_id) ON DELETE CASCADE,
to_id TEXT NOT NULL REFERENCES nodes(card_id) ON DELETE CASCADE,
pair_key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL)"""

DDL = f"""
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cards (card_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (source_id TEXT PRIMARY KEY, card_id TEXT NOT NULL REFERENCES cards(card_id) ON DELETE CASCADE, session_id TEXT, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS sources_session ON sources(session_id);
CREATE TABLE IF NOT EXISTS groups (group_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS nodes (card_id TEXT PRIMARY KEY REFERENCES cards(card_id) ON DELETE CASCADE, group_id TEXT REFERENCES groups(group_id), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS edges {EDGE_COLUMNS};
CREATE TABLE IF NOT EXISTS edge_routes (edge_id TEXT PRIMARY KEY REFERENCES edges(edge_id) ON DELETE CASCADE, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exclusions (exclusion_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations (operation_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, status TEXT NOT NULL CHECK(status='succeeded'), result TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS operation_attempts (operation_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')), error TEXT, started_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS revisions (revision_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL UNIQUE REFERENCES operations(operation_id), graph_revision INTEGER NOT NULL, layout_revision INTEGER NOT NULL, patch TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proposals (proposal_id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL);
"""


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def fingerprint(value):
    try:
        return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()
    except (TypeError, ValueError, RecursionError):
        fail("变更必须是有限的 JSON 数据。")


def database_path(root, owner):
    from agent.auth import USERNAME

    if not isinstance(owner, str) or not USERNAME.fullmatch(owner):
        fail("账号无效。", "invalid_owner", 403)
    base = Path(root).resolve()
    path = (base / owner / "study" / "study.sqlite3").resolve()
    if not path.is_relative_to(base / owner):
        fail("账号存储位置无效。", "invalid_owner", 403)
    return path


@contextmanager
def connection(root, owner, write=False, initialize=False):
    path = database_path(root, owner)
    if initialize:
        path.parent.mkdir(parents=True, exist_ok=True)
    if not initialize and not path.is_file():
        fail("账号学习工作区尚未初始化。", "study_not_enabled", 409)
    uri = path.as_uri() + ("?mode=rwc" if initialize else "?mode=rw" if write else "?mode=ro")
    db = sqlite3.connect(
        uri, uri=True, timeout=STUDY_DATABASE_TIMEOUT_SECONDS, isolation_level=None
    )
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute(f"PRAGMA busy_timeout={int(STUDY_DATABASE_TIMEOUT_SECONDS * 1000)}")
        if initialize:
            db.executescript(DDL)
        if write:
            db.execute("BEGIN IMMEDIATE")
            db.execute("PRAGMA defer_foreign_keys=ON")
        else:
            db.execute("BEGIN")
        yield db
        db.commit()
    except sqlite3.OperationalError as error:
        db.rollback()
        if "locked" in str(error) or "busy" in str(error):
            fail("保存繁忙，请使用同一 operation_id 重试。", "store_busy", 503)
        raise
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def meta(db):
    return {key: json.loads(value) for key, value in db.execute("SELECT key,value FROM meta")}


def set_meta(db, values):
    db.executemany(
        "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        [(key, encode(value)) for key, value in values.items()],
    )


def initialize_account(root, owner):
    """Create an account workspace without overwriting an existing one."""
    if database_path(root, owner).exists():
        return  # Preserve any explicitly provisioned route without overwriting it.
    with connection(root, owner, write=True, initialize=True) as db:
        set_meta(
            db,
            {
                "schema_version": SCHEMA_VERSION,
                "mode": "study_v2",
                "graph_revision": 0,
                "layout_revision": 0,
                "history_retention_days": HISTORY_RETENTION_DAYS,
            },
        )


def _require_enabled(db):
    state = meta(db)
    if state.get("schema_version") != SCHEMA_VERSION:
        fail("学习路线数据库版本不兼容。", "schema_version", 409)
    if state.get("mode") != "study_v2":
        fail("新模式未启用。", "study_not_enabled", 409)
    return state


def load_graph(db):
    return {
        table: {
            row[graph_rules.ID_FIELDS[table]]: row
            for (payload,) in db.execute(f"SELECT payload FROM {table}")
            for row in [json.loads(payload)]
        }
        for table in graph_rules.TABLES
    }


def _upsert(db, table, row):
    key_field = graph_rules.ID_FIELDS[table]
    columns = [key_field]
    if table == "sources":
        columns += ["card_id", "session_id"]
    elif table == "nodes":
        columns += ["group_id"]
    elif table == "edges":
        columns += ["from_id", "to_id", "pair_key"]
    values = [
        encode(graph_rules.edge_identity(row)) if col == "pair_key" else row[col] for col in columns
    ] + [encode(row)]
    columns += ["payload"]
    update = ",".join(f"{col}=excluded.{col}" for col in columns[1:])
    db.execute(
        f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join('?' for _ in columns)}) ON CONFLICT({key_field}) DO UPDATE SET {update}",
        values,
    )


def save_patch(db, patch):
    # Remove changed edges before reinserting to allow a final-state endpoint swap.
    # All work stays inside the same transaction; routes are restored below.
    for change in patch:
        if change["table"] == "edges":
            db.execute("DELETE FROM edges WHERE edge_id=?", (change["id"],))
    for table in ("edge_routes", "edges", "sources", "nodes", "cards", "groups", "exclusions"):
        for change in patch:
            if change["table"] == table and change["after"] is None:
                db.execute(
                    f"DELETE FROM {table} WHERE {graph_rules.ID_FIELDS[table]}=?", (change["id"],)
                )
    for table in ("cards", "groups", "nodes", "sources", "edges", "edge_routes", "exclusions"):
        for change in patch:
            if change["table"] == table and change["after"] is not None:
                _upsert(db, table, change["after"])


def workspace(root, owner):
    with connection(root, owner) as db:
        state = _require_enabled(db)
        graph = load_graph(db)
        history = study_history.public(study_history.state(db, state))
        pending = db.execute(
            "SELECT job_id,payload FROM jobs WHERE status='running' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if pending and json.loads(pending[1]).get("strategy") == "session_v1":
            pending = next(
                (
                    (key, raw)
                    for key, raw in db.execute(
                        "SELECT job_id,payload FROM jobs WHERE status='running' ORDER BY rowid DESC"
                    )
                    if json.loads(raw).get("strategy") != "session_v1"
                ),
                None,
            )
        from agent.study_tools import live

        if (
            pending
            and not live(pending[0], json.loads(pending[1]))
            and json.loads(pending[1]).get("strategy") != "tools_v1"
        ):
            pending = None
        if pending:
            from agent.study_tools import public_progress

            pending_data = json.loads(pending[1])
            pending = {
                "operation_id": pending[0],
                "kind": "ai-relations",
                "instruction": pending_data.get("instruction", ""),
                **(
                    {"progress": public_progress(pending_data)}
                    if pending_data.get("strategy") == "tools_v1"
                    else {}
                ),
            }
    _resolve_availability(root, owner, graph)
    from agent import study_binding

    study_binding.enrich(root, owner, graph, state.get(study_binding.KEY, {}))
    for key, level in graph_rules.resolve_levels(graph).items():
        graph["nodes"][key]["level"] = level
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "study_v2",
        "enabled": True,
        "graph_revision": state["graph_revision"],
        "layout_revision": state["layout_revision"],
        "history_retention_days": state["history_retention_days"],
        "card_size": {"width": 240, "height": 128},
        "capabilities": {
            "manual": True,
            "canvas": True,
            "history": True,
            "ai_relations": False,
            "ai_session": True,
        },
        "history": history,
        "pending_operation": pending,
        "warnings": graph_rules.graph_warnings(graph),
        **{table: list(rows.values()) for table, rows in graph.items()},
    }


def _resolve_availability(root, owner, graph):
    from agent import eventlog

    available = {}
    for source in graph["sources"].values():
        session_id = source.get("session_id")
        if session_id:
            if session_id not in available:
                available[session_id] = eventlog.SessionLog(root, owner, session_id).exists()
            source["availability"] = "available" if available[session_id] else "missing"


def get_card(root, owner, card_id):
    graph_rules.identifier(card_id, "card_id")
    value = workspace(root, owner)
    card = next((row for row in value.get("cards", []) if row["card_id"] == card_id), None)
    if card is None:
        fail("找不到卡片。", "not_found", 404)
    return {
        "card": card,
        "sources": [s for s in value["sources"] if s["card_id"] == card_id],
        "node": next((n for n in value["nodes"] if n["card_id"] == card_id), None),
        "edges": [e for e in value["edges"] if card_id in (e["from_id"], e["to_id"])],
        "graph_revision": value["graph_revision"],
        "layout_revision": value["layout_revision"],
    }


def _complete_patch(before, after):
    for table in graph_rules.TABLES:
        for key, row in after[table].items():
            old = before[table].get(key)
            if row != old:
                row["revision"] = old["revision"] + 1 if old else max(1, row.get("revision", 0))
    patch = graph_rules.changes_between(before, after)
    # Deleting/replacing an edge cascades the old route in SQLite.
    changed_edges = {
        change["id"]
        for change in patch
        if change["table"] == "edges" and change["after"] is not None
    }
    patched_routes = {change["id"] for change in patch if change["table"] == "edge_routes"}
    for key in sorted(changed_edges - patched_routes):
        patch.append(
            {
                "table": "edge_routes",
                "id": key,
                "before": before["edge_routes"].get(key),
                "after": after["edge_routes"][key],
            }
        )
    return patch


def _claim_operation(root, owner, operation_id, digest):
    with connection(root, owner, write=True) as db:
        _require_enabled(db)
        previous = db.execute(
            "SELECT fingerprint,result FROM operations WHERE operation_id=?", (operation_id,)
        ).fetchone()
        job = db.execute(
            "SELECT status,payload FROM jobs WHERE job_id=?", (operation_id,)
        ).fetchone()
        data = json.loads(job[1]) if job else {}
        if data.get("strategy") == "session_v1":
            fail("会话整理编号不能用于手工变更。", "idempotency_conflict", 409)
        if data.get("strategy") == "tools_v1" and (
            job[0] == "running" or previous and job[0] != "succeeded"
        ):
            if previous and previous[0] != digest:
                fail("同一整理编号不能用于不同参数。", "idempotency_conflict", 409)
            from agent.study_tools import public_progress

            return {
                "operation_id": operation_id,
                "status": "running" if job[0] == "running" else "failed",
                "progress": public_progress(data),
                "failure": data.get("failure"),
                **({"partial_result": json.loads(previous[1])} if previous else {}),
            }
        if previous:
            if previous[0] != digest:
                fail("同一 operation_id 不能用于不同参数。", "idempotency_conflict", 409)
            return json.loads(previous[1])
        attempt = db.execute(
            "SELECT fingerprint,status,started_at FROM operation_attempts WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
        if attempt and attempt[1] == "running" and time.time() - attempt[2] < 300:
            if attempt[0] != digest:
                fail("该 operation_id 正在执行不同参数。", "idempotency_conflict", 409)
            return {"operation_id": operation_id, "status": "running", "retryable": True}
        # Failed or expired attempts can be retried, including corrected inputs.
        db.execute(
            "INSERT INTO operation_attempts VALUES(?,?,?,NULL,?) ON CONFLICT(operation_id) DO UPDATE SET fingerprint=excluded.fingerprint,status=excluded.status,error=NULL,started_at=excluded.started_at",
            (operation_id, digest, "running", time.time()),
        )
    return None


def apply_changes(root, owner, payload):
    if not isinstance(payload, dict):
        fail("请求必须是 JSON 对象。")
    operation_id = graph_rules.identifier(payload.get("operation_id"), "operation_id")
    digest = fingerprint(payload)
    claimed = _claim_operation(root, owner, operation_id, digest)
    if claimed is not None:
        return claimed
    try:
        return _apply_changes(root, owner, payload, operation_id, digest)
    except Exception as error:
        public = (
            error.public()
            if isinstance(error, StudyError)
            else {"error": "变更未提交，可重试。", "code": "commit_failed"}
        )
        with connection(root, owner, write=True) as db:
            db.execute(
                "UPDATE operation_attempts SET status='failed',error=? WHERE operation_id=? AND fingerprint=? AND status='running'",
                (encode(public), operation_id, digest),
            )
        raise


def _apply_changes(
    root,
    owner,
    payload,
    operation_id,
    digest,
    actor="user",
    ai_result=None,
    ai_job_token=None,
    ai_arrange_layout=False,
    ai_layout_plan=None,
    ai_ignored_exclusions=(),
    binding_create=None,
):
    with connection(root, owner, write=True) as db:
        state = _require_enabled(db)
        previous = db.execute(
            "SELECT fingerprint,result FROM operations WHERE operation_id=?", (operation_id,)
        ).fetchone()
        if previous:
            if previous[0] != digest:
                fail("同一 operation_id 不能用于不同参数。", "idempotency_conflict", 409)
            return json.loads(previous[1])
        before = load_graph(db)
        if actor == "user":
            from agent.study_tools import live

            if any(
                json.loads(raw).get("strategy") == "tools_v1" and live(job_id, json.loads(raw))
                for job_id, raw in db.execute(
                    "SELECT job_id,payload FROM jobs WHERE status='running'"
                )
            ):
                fail("AI 正在逐步整理这条路线，请停止或完成后再编辑。", "ai_busy", 409)
        if (
            actor == "ai"
            and ai_arrange_layout
            and payload.get("base_layout_revision") != state["layout_revision"]
        ):
            fail("整理期间卡片位置已变化，本次结果未应用，请重新整理。", "layout_conflict", 409)
        operations = payload.get("operations", [])
        if not isinstance(operations, list):
            fail("操作列表无效。")
        history = None
        history_entry = None
        if (
            len(operations) == 1
            and isinstance(operations[0], dict)
            and isinstance(operations[0].get("op"), str)
            and operations[0]["op"] in {"undo", "redo"}
        ):
            graph_rules.whitelist(
                payload,
                {
                    "schema_version",
                    "operation_id",
                    "base_graph_revision",
                    "base_layout_revision",
                    "operations",
                },
                {
                    "schema_version",
                    "operation_id",
                    "base_graph_revision",
                    "base_layout_revision",
                    "operations",
                },
            )
            if (
                type(payload["schema_version"]) is not int
                or payload["schema_version"] != SCHEMA_VERSION
            ):
                fail("协议版本不兼容。", "schema_version")
            graph_rules.integer(payload["base_graph_revision"], 0)
            graph_rules.integer(payload["base_layout_revision"], 0)
            after, history, history_entry = study_history.prepare(
                db, state, before, operations[0], root, owner
            )
            refs = {}
        else:
            if actor in {"ai", "ai_session"}:
                job = db.execute(
                    "SELECT status,payload FROM jobs WHERE job_id=?", (operation_id,)
                ).fetchone()
                if (
                    job is None
                    or job[0] != "running"
                    or json.loads(job[1]).get("run_id") != ai_job_token
                ):
                    fail("整理已停止，结果未应用。", "cancelled", 409)
                if actor == "ai_session":
                    from agent.study_jobs import active_route

                    binding = json.loads(job[1]).get("binding")
                    scope = [binding["card_id"]] if binding else None
                    if active_route(db, scope):
                        fail("该卡片正在整理路线，学习总结已完成，等待保存。", "scope_busy", 409)
            after, refs = graph_rules.apply_commands(before, payload, actor=actor)
            if actor in {"ai", "ai_session"}:
                for key in ai_ignored_exclusions:
                    after["exclusions"].pop(key, None)
            if actor == "ai" and ai_arrange_layout:
                from agent import study_layout

                card_ids = payload["scope"]["card_ids"]
                positions = study_layout.arrange(after, card_ids, ai_layout_plan)
                for card_id, position in positions.items():
                    after["nodes"][card_id].update(position)
                ai_result = {
                    **(ai_result or {}),
                    "moved": len(positions),
                    "fixed": sum(after["nodes"][key]["position_locked"] for key in card_ids),
                }
        from agent import study_binding

        creation = (
            {**binding_create, "card_id": refs[binding_create["card_ref"]]}
            if binding_create
            else None
        )
        study_binding.validate_commit(
            db,
            before,
            after,
            actor,
            json.loads(job[1]) if actor == "ai_session" else None,
            creation,
        )
        patch = _complete_patch(before, after)
        semantic, layout = graph_rules.revision_kinds(
            [p for p in patch if p["before"] != p["after"]]
        )
        if payload["base_graph_revision"] != state["graph_revision"]:
            fail(
                "路线已变化，本次结果未应用，请重新整理或重试操作。",
                "graph_conflict",
                409,
                graph_revision=state["graph_revision"],
                layout_revision=state["layout_revision"],
            )
        if layout and payload.get("base_layout_revision") != state["layout_revision"]:
            fail(
                "布局已变化，请刷新位置预览。",
                "layout_conflict",
                409,
                graph_revision=state["graph_revision"],
                layout_revision=state["layout_revision"],
            )
        base_graph_revision, base_layout_revision = (
            state["graph_revision"],
            state["layout_revision"],
        )
        state["graph_revision"] += int(semantic)
        state["layout_revision"] += int(layout)
        revision_id = "revision_" + uuid.uuid4().hex if patch else None
        result = {
            "operation_id": operation_id,
            "status": "succeeded",
            "changed": bool(patch),
            "graph_revision": state["graph_revision"],
            "layout_revision": state["layout_revision"],
            "revision_id": revision_id,
            "id_map": refs,
            "warnings": graph_rules.graph_warnings(after),
            "objects": [
                {
                    "table": p["table"],
                    "id": p["id"],
                    "revision": p["after"]["revision"] if p["after"] else None,
                }
                for p in patch
                if p["before"] != p["after"]
            ],
        }
        if ai_result is not None:
            result["ai_summary"] = ai_result
        if history_entry:
            result["history_action"] = {
                "direction": operations[0]["op"],
                "label": history_entry["label"],
            }
        save_patch(db, patch)
        set_meta(db, {key: state[key] for key in ("graph_revision", "layout_revision")})
        now = time.time()
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?,?)",
            (operation_id, digest, "succeeded", encode(result), now),
        )
        db.execute(
            "UPDATE operation_attempts SET status='succeeded',error=NULL WHERE operation_id=?",
            (operation_id,),
        )
        if revision_id:
            db.execute(
                "INSERT INTO revisions VALUES(?,?,?,?,?,?)",
                (
                    revision_id,
                    operation_id,
                    state["graph_revision"],
                    state["layout_revision"],
                    encode(patch),
                    now,
                ),
            )
            if history is None:
                history = study_history.state(db, state)
                ai_label = "AI 整理路线" if ai_arrange_layout else "AI 整理关系"
                history["undo"].append(
                    {
                        "revision_id": revision_id,
                        "label": "会话整理为学习卡片"
                        if actor == "ai_session"
                        else ai_label
                        if actor == "ai"
                        else study_history.label(operations),
                    }
                )
                history["undo"] = history["undo"][-100:]
                history["redo"] = []
        if history is not None:
            set_meta(db, {"command_history": history})
        # Return the exact committed rows. A browser can acknowledge a save
        # without depending on a second full-workspace HTTP request succeeding.
        result["projection"] = {
            "base_graph_revision": base_graph_revision,
            "base_layout_revision": base_layout_revision,
            "changes": [
                {"table": item["table"], "id": item["id"], "value": item["after"]}
                for item in patch
                if item["table"] != "exclusions"
            ],
            "levels": graph_rules.resolve_levels(after),
            "history": study_history.public(
                history if history is not None else study_history.state(db, state)
            ),
        }
        db.execute(
            "UPDATE operations SET result=? WHERE operation_id=?", (encode(result), operation_id)
        )
        if actor == "ai":
            db.execute(
                "UPDATE jobs SET status='succeeded',payload=? WHERE job_id=?",
                (encode({"summary": ai_result}), operation_id),
            )
        db.execute(
            "DELETE FROM revisions WHERE created_at<?",
            (now - state["history_retention_days"] * 86400,),
        )
        db.execute(
            "DELETE FROM operation_attempts WHERE status='failed' AND started_at<?",
            (now - state["history_retention_days"] * 86400,),
        )
        return result


def revision_stamp(root, owner):
    """Small background validation, without loading cards, sources or job payloads."""
    with connection(root, owner) as db:
        state = _require_enabled(db)
        return {key: state[key] for key in ("graph_revision", "layout_revision")}


def operation_result(root, owner, operation_id):
    graph_rules.identifier(operation_id, "operation_id")
    with connection(root, owner) as db:
        _require_enabled(db)
        row = db.execute(
            "SELECT result FROM operations WHERE operation_id=?", (operation_id,)
        ).fetchone()
        job = db.execute(
            "SELECT status,payload FROM jobs WHERE job_id=?", (operation_id,)
        ).fetchone()
        attempt = (
            db.execute(
                "SELECT status,error,started_at FROM operation_attempts WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if row is None
            else None
        )
    data = json.loads(job[1]) if job else {}
    if data.get("strategy") == "session_v1":
        from agent import study_session

        session_result = study_session.public(root, owner, operation_id)
        if session_result.get("result"):
            return session_result["result"]
        return {
            "operation_id": operation_id,
            "status": "running" if session_result["status"] == "running" else "failed",
            "progress": session_result.get("progress"),
            "failure": session_result.get("failure"),
        }
    if data.get("strategy") == "tools_v1":
        from agent import study_tools

        if job[0] == "running" and not study_tools.live(operation_id, data):
            study_tools.fail_job(
                root,
                owner,
                operation_id,
                StudyError("整理进程已中断，已保存步骤可整次撤回。", "interrupted"),
                run_id=data.get("run_id"),
            )
            return operation_result(root, owner, operation_id)
        progress = study_tools.public_progress(data)
        progress["elapsed_ms"] = round(
            (
                (time.time() if job[0] == "running" else data.get("updated_at", time.time()))
                - data["started_at"]
            )
            * 1000
        )
        if job[0] != "succeeded":
            return {
                "operation_id": operation_id,
                "status": "running" if job[0] == "running" else "failed",
                "progress": progress,
                "failure": data.get("failure"),
                **({"partial_result": json.loads(row[0])} if row else {}),
            }
        if row:
            return {**json.loads(row[0]), "progress": progress}
    if row is None:
        if attempt:
            status = (
                "failed"
                if attempt[0] == "running" and time.time() - attempt[2] >= 300
                else attempt[0]
            )
            return {
                "operation_id": operation_id,
                "status": status,
                "retryable": True,
                "failure": json.loads(attempt[1])
                if attempt[1]
                else {"code": "interrupted"}
                if status == "failed"
                else None,
            }
        fail(
            "未找到已提交结果；失败请求不会占用幂等键，可用原 ID 重试。", "operation_not_found", 404
        )
    return json.loads(row[0])


def revisions(root, owner):
    with connection(root, owner) as db:
        state = _require_enabled(db)
        cutoff = time.time() - state["history_retention_days"] * 86400
        rows = db.execute(
            "SELECT revision_id,operation_id,graph_revision,layout_revision,patch,created_at FROM revisions WHERE created_at>=? ORDER BY created_at DESC LIMIT 100",
            (cutoff,),
        ).fetchall()
    return {
        "history_retention_days": state["history_retention_days"],
        "revisions": [
            dict(
                zip(
                    (
                        "revision_id",
                        "operation_id",
                        "graph_revision",
                        "layout_revision",
                        "patch",
                        "created_at",
                    ),
                    (*row[:4], json.loads(row[4]), row[5]),
                )
            )
            for row in rows
        ],
    }


def invalidate_session(root, owner, session_id):
    """Only derived availability and pending material are affected; adopted cards survive."""
    with connection(root, owner, write=True) as db:
        _require_enabled(db)
        for (payload,) in db.execute(
            "SELECT payload FROM sources WHERE session_id=?", (session_id,)
        ).fetchall():
            row = json.loads(payload)
            row["availability"] = "missing"
            _upsert(db, "sources", row)
        for table, key_field in (("jobs", "job_id"), ("proposals", "proposal_id")):
            for key, status, payload in db.execute(
                f"SELECT {key_field},status,payload FROM {table}"
            ).fetchall():
                value = json.loads(payload)
                if value.get("strategy") == "session_v1" and session_id in value.get(
                    "session_ids", []
                ):
                    value.pop("chunks", None)
                    value.pop("compositions", None)
                    if status == "running":
                        value.update(
                            phase="cancelled",
                            message="来源会话已删除，任务已停止。",
                            failure={"code": "source_deleted", "error": "来源会话已删除。"},
                            updated_at=time.time(),
                        )
                        status = "cancelled"
                    db.execute(
                        f"UPDATE {table} SET status=?,payload=? WHERE {key_field}=?",
                        (status, encode(value), key),
                    )
                    continue
                pending = (
                    status
                    in {
                        "queued",
                        "reading",
                        "extracting",
                        "synthesizing",
                        "validating",
                        "interrupted",
                    }
                    if table == "jobs"
                    else status == "ready"
                )
                if session_id in value.get("session_ids", []) and pending:
                    next_status = "cancelled" if table == "jobs" else "invalidated"
                    value = {
                        "session_ids": value.get("session_ids", []),
                        "reason": "source_deleted",
                    }
                    db.execute(
                        f"UPDATE {table} SET status=?,payload=? WHERE {key_field}=?",
                        (next_status, encode(value), key),
                    )
