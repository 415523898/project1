"""Account-local immutable self-check attempts and cancellable, idempotent jobs."""

import copy
import json
import threading
import time
import uuid

from agent import eventlog, provider, study_binding, study_model, titles
from agent import self_check_contract as contract
from agent import self_check_summary as summary
from agent import self_check_workflow as workflow
from agent import study_store as store
from agent.provider_transport import safe_text
from agent.study_graph import fail, identifier, whitelist
from config import (
    SELF_CHECK_MAX_SECONDS as MAX_SECONDS,
)

BOOT = uuid.uuid4().hex
_guard = threading.Lock()
_workers = {}


def model_target(target, model):
    return study_model.structured_target(target, model)


def model_options(model, kind, repair):
    limit = (8192 if kind == "generate" else 4096) * (2 if repair else 1)
    return study_model.options(model, limit)


def recent_questions(db, value):
    rows = db.execute(
        "SELECT payload FROM self_check_attempts WHERE method_id=? AND id!=? AND status IN ('ready','grading','grade_failed','completed') ORDER BY created_at DESC LIMIT 8",
        (value["method_id"], value["id"]),
    ).fetchall()
    result = []
    for row in rows:
        old = json.loads(row[0])
        for q in old.get("paper", {}).get("questions", []):
            result.append(
                {
                    "id": old["id"] + ":" + q["id"],
                    "type": q["type"],
                    "prompt": q["prompt"],
                    "point_ids": q["point_ids"],
                }
            )
    return result


def chat_context(root, owner, sid):
    """Server-owned completed results only; current unanswered keys stay private."""
    if not eventlog.SessionLog(root, owner, sid).exists():
        return None
    binding = study_binding.public(root, owner, sid)
    if not binding:
        return None
    with store.connection(root, owner) as db:
        if not _exists(db):
            return None
        values = [
            json.loads(r[0])
            for r in db.execute(
                "SELECT payload FROM self_check_attempts WHERE session_id=? AND method_id=? AND card_id=? ORDER BY created_at DESC",
                (sid, binding["method_id"], binding["card_id"]),
            )
        ]
    completed = [v for v in values if v["status"] == "completed"]
    if not completed:
        return None
    value = completed[0]
    result = value["result"]
    questions = []
    for q in value["paper"]["questions"]:
        item = {
            "id": q["id"],
            "type": q["type"],
            "prompt": q["prompt"][:600],
            "student_answer": value["submitted"].get(q["id"], ""),
            "reference_explanation": q["explanation"][:500],
        }
        if q["type"] == "short":
            item.update(
                points=result["short_points"],
                maximum=40,
                criteria=[
                    {
                        "criterion": next(r["text"] for r in q["rubric"] if r["id"] == e["id"]),
                        "level": e["level"],
                        "points": e["points"],
                        "evidence": e["evidence"][:300],
                        "reason": e["reason"][:400],
                    }
                    for e in result["short"]["evaluations"]
                ],
            )
        else:
            objective = next(r for r in result["objective"] if r["id"] == q["id"])
            item.update(
                points=objective["points"],
                maximum=15,
                correct=objective["correct"],
                reference_answer=q["answer"],
            )
        questions.append(item)
    return {
        "source": "server_completed_self_check",
        "attempt_id": value["id"],
        "method_id": value["method_id"],
        "label": value["label"],
        "completed_at": value["updated_at"],
        "latest_attempt": {"id": values[0]["id"], "status": values[0]["status"]},
        "total": result["total"],
        "short_points": result["short_points"],
        "passed": result["passed"],
        "rules": value["rules"],
        "scope": result["scope"],
        "questions": questions,
        "feedback": result["short"]["feedback"][:600],
        "advice": [a[:300] for a in result["short"]["advice"][:5]],
        "previous_scores": [
            {
                "attempt_id": v["id"],
                "total": v["result"]["total"],
                "short_points": v["result"]["short_points"],
            }
            for v in completed[1:3]
        ],
        "note": "仅已完成试卷的反馈摘要，不含当前未作答试卷答案。",
    }


def active_count():
    with _guard:
        return len(_workers)


def _schema(db):
    store._require_enabled(db)
    db.execute(
        "CREATE TABLE IF NOT EXISTS self_check_attempts (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, method_id TEXT NOT NULL, card_id TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS self_check_session ON self_check_attempts(session_id,method_id,created_at DESC)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS self_check_operations (id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, kind TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    store.set_meta(db, {"self_check_schema_version": 1})


def _exists(db):
    return bool(
        db.execute("SELECT 1 FROM sqlite_master WHERE name='self_check_attempts'").fetchone()
    )


def _attempt(db, aid):
    row = (
        db.execute("SELECT payload FROM self_check_attempts WHERE id=?", (aid,)).fetchone()
        if _exists(db)
        else None
    )
    if not row:
        fail("自测试卷不存在或不属于当前账号。", "not_found", 404)
    return json.loads(row[0])


def _operation(db, oid):
    row = (
        db.execute("SELECT payload FROM self_check_operations WHERE id=?", (oid,)).fetchone()
        if _exists(db)
        else None
    )
    if not row:
        fail("自测任务不存在或不属于当前账号。", "not_found", 404)
    return json.loads(row[0])


def _save_attempt(db, value):
    value["updated_at"] = time.time()
    value["revision"] += 1
    db.execute(
        "UPDATE self_check_attempts SET status=?,revision=?,payload=?,updated_at=? WHERE id=?",
        (value["status"], value["revision"], store.encode(value), value["updated_at"], value["id"]),
    )


def _save_operation(db, value):
    value["updated_at"] = time.time()
    db.execute(
        "UPDATE self_check_operations SET status=?,payload=? WHERE id=?",
        (value["status"], store.encode(value), value["id"]),
    )


def _general(attempt):
    return not attempt.get("method_id") and not attempt.get("card_id")


def _binding_matches(db, attempt):
    if _general(attempt):
        return True
    current = store.meta(db).get(study_binding.KEY, {}).get(attempt["session_id"])
    return bool(
        current
        and current["method_id"] == attempt["method_id"]
        and current["card_id"] == attempt["card_id"]
        and db.execute("SELECT 1 FROM cards WHERE card_id=?", (attempt["card_id"],)).fetchone()
    )


def _validate_binding(db, attempt, root, owner):
    if _general(attempt):
        if not eventlog.SessionLog(root, owner, attempt["session_id"]).exists():
            fail("会话已删除；原自测记录保留。", "binding_changed", 409)
        return
    if (
        not _binding_matches(db, attempt)
        or not eventlog.SessionLog(root, owner, attempt["session_id"]).exists()
    ):
        fail("会话或方法绑定已变化；原自测记录保留，请在当前方法重新开始。", "binding_changed", 409)


def _public_attempt(db, value, root, owner):
    keys = [
        "id",
        "session_id",
        "method_id",
        "card_id",
        "label",
        "status",
        "revision",
        "created_at",
        "updated_at",
        "draft",
        "submitted",
        "rules",
        "operation_id",
        "failure",
    ]
    public = {key: copy.deepcopy(value[key]) for key in keys if key in value}
    frozen = value["frozen"]
    paper = value.get("paper")
    public.update(
        binding_valid=_binding_matches(db, value)
        and eventlog.SessionLog(root, owner, value["session_id"]).exists(),
        candidate_count=frozen["candidate_count"],
        valid_count=len(paper["valid_turns"]) if paper else None,
        summary=frozen.get("summary", ""),
        scope_note=frozen["scope_note"],
        selection_partial=frozen["selection_partial"],
        snapshot=frozen["snapshot"],
        blueprint_version=frozen["blueprint"]["version"],
    )
    if paper:
        public["reason"] = paper["reason"]
        public["missing_points"] = paper["missing_points"]
        public["advice"] = paper["advice"]
        public["questions"] = [
            {
                key: copy.deepcopy(q[key])
                for key in ("id", "type", "prompt", "point_ids", "options", "basis_kind")
            }
            for q in paper["questions"]
        ]
        covered = {pid for q in paper["questions"] for pid in q["point_ids"]}
        public["covered_points"] = [
            {"id": p["id"], "title": p["title"]}
            for p in frozen["blueprint"]["points"]
            if p["id"] in covered
        ]
        public["uncovered_points"] = [
            p["title"] for p in frozen["blueprint"]["points"] if p["id"] not in covered
        ]
    if value["status"] == "completed":
        public["result"] = copy.deepcopy(value["result"])
        public["review"] = [
            {
                key: copy.deepcopy(q[key])
                for key in ("id", "answer", "explanation", "rubric", "evidence", "lesson_quote")
            }
            for q in paper["questions"]
        ]
    from engine.learner_text import inaccessible_question, presentation

    if paper and any(inaccessible_question(q) for q in paper["questions"]):
        public["requires_refresh"] = True
        public["content_notice"] = (
            "这份历史试卷含依赖应用内部信息的题目，已停止展示题目与解析。原始作答和成绩保留，可重新出题。"
        )
        public["questions"] = []
        public["review"] = []
        if public.get("result"):
            public["result"]["objective"] = []
            public["result"]["short"].update(evaluations=[], feedback="原始成绩已保留。", advice=[])

    return presentation(public)


def _public_operation(op):
    return {
        key: copy.deepcopy(op[key])
        for key in (
            "id",
            "attempt_id",
            "kind",
            "status",
            "message",
            "calls",
            "used_tokens",
            "failure",
            "model",
            "created_at",
            "updated_at",
        )
        if key in op
    }


def _recover(root, owner):
    with store.connection(root, owner) as db:
        if not _exists(db):
            return
        rows = db.execute(
            "SELECT payload FROM self_check_operations WHERE status='running'"
        ).fetchall()
    stale = []
    for row in rows:
        op = json.loads(row[0])
        if op["boot"] != BOOT or time.time() - op["created_at"] > MAX_SECONDS + 30:
            stale.append(op["id"])
    if not stale:
        return
    with store.connection(root, owner, write=True) as db:
        for oid in stale:
            op = _operation(db, oid)
            if op["status"] != "running":
                continue
            attempt = _attempt(db, op["attempt_id"])
            op.update(
                status="interrupted",
                message="服务重启或执行超时，试卷和已提交答案保留。",
                failure={"code": "interrupted", "error": "可重新读取原任务，或主动恢复本阶段。"},
            )
            _save_operation(db, op)
            if attempt["operation_id"] == oid:
                attempt.update(status=op["kind"] + "_failed", failure=op["failure"])
                _save_attempt(db, attempt)


def state(root, owner, sid):
    if not isinstance(sid, str) or not eventlog.SESSION_ID.fullmatch(sid):
        fail("会话编号无效。")
    binding = study_binding.public(root, owner, sid)
    if not eventlog.SessionLog(root, owner, sid).exists():
        fail("会话不存在或不属于当前账号。", "not_found", 404)
    count = len(contract.eligible_blocks(root, owner, sid))
    general = binding is None
    valid = general or bool(
        binding and not binding["card_missing"] and not binding["session_missing"]
    )
    result = {
        "binding": binding,
        "candidate_count": count,
        "can_start": valid and count > 0,
        "rules": contract.RULES,
        "generation_version": contract.GENERATION_VERSION,
        "attempt": None,
        "history": [],
    }
    if not store.database_path(root, owner).is_file():
        return result
    _recover(root, owner)
    with store.connection(root, owner) as db:
        if not _exists(db):
            return result
        if valid:
            if general:
                row = db.execute(
                    "SELECT payload FROM self_check_attempts WHERE session_id=? AND method_id='' AND card_id='' ORDER BY created_at DESC LIMIT 1",
                    (sid,),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT payload FROM self_check_attempts WHERE session_id=? AND method_id=? AND card_id=? ORDER BY created_at DESC LIMIT 1",
                    (sid, binding["method_id"], binding["card_id"]),
                ).fetchone()
            if row:
                result["attempt"] = _public_attempt(db, json.loads(row[0]), root, owner)
        rows = db.execute(
            "SELECT payload FROM self_check_attempts WHERE session_id=? AND status IN ('ready','grading','grade_failed','completed') ORDER BY created_at DESC LIMIT 30",
            (sid,),
        ).fetchall()
        for row in rows:
            value = json.loads(row[0])
            public = _public_attempt(db, value, root, owner)
            if len(value.get("paper", {}).get("questions", [])) != 5:
                continue
            result["history"].append(
                {
                    key: public[key]
                    for key in (
                        "id",
                        "label",
                        "method_id",
                        "binding_valid",
                        "status",
                        "created_at",
                        "result",
                    )
                    if key in public
                }
            )
    return result


def attempt(root, owner, aid):
    identifier(aid, "attempt_id")
    _recover(root, owner)
    with store.connection(root, owner) as db:
        return _public_attempt(db, _attempt(db, aid), root, owner)


def operation(root, owner, oid):
    identifier(oid, "operation_id")
    _recover(root, owner)
    with store.connection(root, owner) as db:
        return _public_operation(_operation(db, oid))


def _existing(root, owner, oid, fingerprint):
    with store.connection(root, owner) as db:
        if not _exists(db):
            return None
        row = db.execute(
            "SELECT payload,fingerprint FROM self_check_operations WHERE id=?", (oid,)
        ).fetchone()
        if not row:
            return None
        if row[1] != fingerprint:
            fail("同一任务编号不能用于其他请求。", "idempotency_conflict", 409)
        return _public_operation(json.loads(row[0]))


def _new_job(db, value, oid, kind, fingerprint, model):
    running = db.execute(
        "SELECT 1 FROM self_check_operations o JOIN self_check_attempts a ON a.id=o.attempt_id "
        "WHERE o.status='running' AND a.session_id=? LIMIT 1",
        (value["session_id"],),
    ).fetchone()
    if running:
        fail("当前会话已有自测任务运行，请先完成或停止。", "self_check_busy", 409)
    op = {
        "id": oid,
        "attempt_id": value["id"],
        "kind": kind,
        "status": "running",
        "calls": 0,
        "used_tokens": 0,
        "model": model,
        "created_at": time.time(),
        "updated_at": time.time(),
        "boot": BOOT,
        "message": "正在检查已学内容并准备题目…"
        if kind == "generate"
        else "正在按固定要点评价简答…",
    }
    db.execute(
        "INSERT INTO self_check_operations VALUES(?,?,?,?,?,?)",
        (oid, value["id"], kind, fingerprint, "running", store.encode(op)),
    )
    value.update(
        status="generating" if kind == "generate" else "grading", operation_id=oid, failure=None
    )
    _save_attempt(db, value)
    return op


def _launch(root, owner, op, settings, authorized):
    flag = threading.Event()
    key = (str(root), owner, op["id"])
    with _guard:
        _workers[key] = flag
    threading.Thread(
        target=_run,
        args=(root, owner, op["id"], settings, authorized, flag),
        daemon=True,
        name="self-check-" + op["id"],
    ).start()
    return _public_operation(op)


def start(root, owner, payload, authorized=lambda: True):
    whitelist(
        payload,
        {"operation_id", "session_id", "new_attempt", "provider"},
        {"operation_id", "session_id", "provider"},
    )
    oid = identifier(payload["operation_id"], "operation_id")
    sid = payload["session_id"]
    if not isinstance(sid, str) or not eventlog.SESSION_ID.fullmatch(sid):
        fail("会话编号无效。")
    fresh = payload.get("new_attempt", False)
    if type(fresh) is not bool:
        fail("重新出题参数无效。")
    fingerprint = store.fingerprint({"kind": "generate", "session_id": sid, "new_attempt": fresh})
    old = _existing(root, owner, oid, fingerprint)
    if old:
        return old
    if not authorized():
        fail("登录已失效。", "auth_expired", 401)
    from agent.runtime import RUNTIME

    if RUNTIME.conversation_status(root, owner, sid)["running"]:
        fail("请等待当前聊天生成完成后再开始自测。", "chat_busy", 409)
    binding = study_binding.public(root, owner, sid)
    if binding and (binding["card_missing"] or binding["session_missing"]):
        fail("请先确认有效的方法绑定。", "binding_required", 409)
    if not binding and not contract.eligible_blocks(root, owner, sid):
        fail("尚无可核对的学习内容，请先完成一轮对话。", "insufficient_evidence", 409)
    method_id = binding["method_id"] if binding else ""
    card_id = binding["card_id"] if binding else ""
    current = state(root, owner, sid)
    if current["attempt"] and not fresh:
        return operation(root, owner, current["attempt"]["operation_id"])
    settings = titles.settings(payload["provider"])
    frozen = contract.freeze(
        root, owner, sid, summary.placeholder(method_id), secrets=(settings[1],)
    )
    value = {
        "id": "quiz-" + uuid.uuid4().hex,
        "session_id": sid,
        "method_id": method_id,
        "card_id": card_id,
        "label": frozen["blueprint"]["label"],
        "status": "generating",
        "revision": 0,
        "created_at": time.time(),
        "updated_at": time.time(),
        "frozen": frozen,
        "rules": copy.deepcopy(contract.RULES),
        "draft": {},
        "prompt_version": contract.VERSION,
    }
    with store.connection(root, owner, write=True) as db:
        _schema(db)
        old = db.execute(
            "SELECT fingerprint,payload FROM self_check_operations WHERE id=?", (oid,)
        ).fetchone()
        if old:
            if old[0] != fingerprint:
                fail("任务编号冲突。", "idempotency_conflict", 409)
            return _public_operation(json.loads(old[1]))
        _validate_binding(db, value, root, owner)
        if not fresh:
            previous = db.execute(
                "SELECT payload FROM self_check_attempts WHERE session_id=? AND method_id=? AND card_id=? ORDER BY created_at DESC LIMIT 1",
                (sid, value["method_id"], value["card_id"]),
            ).fetchone()
            if previous:
                return _public_operation(_operation(db, json.loads(previous[0])["operation_id"]))
        db.execute(
            "INSERT INTO self_check_attempts VALUES(?,?,?,?,?,?,?,?,?)",
            (
                value["id"],
                sid,
                value["method_id"],
                value["card_id"],
                value["status"],
                0,
                store.encode(value),
                value["created_at"],
                value["updated_at"],
            ),
        )
        op = _new_job(db, value, oid, "generate", fingerprint, settings[2])
    return _launch(root, owner, op, settings, authorized)


def save_draft(root, owner, aid, payload):
    whitelist(payload, {"revision", "answers"}, {"revision", "answers"})
    with store.connection(root, owner, write=True) as db:
        value = _attempt(db, aid)
        _validate_binding(db, value, root, owner)
        if value["status"] != "ready":
            fail("本卷已提交或尚未准备好，不能修改作答。", "answers_locked", 409)
        answers = payload["answers"]
        if not isinstance(answers, dict) or not set(answers) <= set(
            "q" + str(i) for i in range(1, 6)
        ):
            fail("作答草稿无效。", "invalid_answers")
        if type(payload["revision"]) is not int or payload["revision"] != value["revision"]:
            fail("服务器草稿已变化；本机填写保留，请读取后再确认。", "draft_conflict", 409)
        for qid, answer in answers.items():
            if not isinstance(answer, str) or len(answer) > (1500 if qid == "q5" else 5):
                fail("作答长度无效。", "invalid_answers")
            if qid != "q5" and answer not in ("", "true", "false", "A", "B", "C", "D"):
                fail("题目选项无效。", "invalid_answers")
        value["draft"] = copy.deepcopy(answers)
        _save_attempt(db, value)
        return _public_attempt(db, value, root, owner)


def submit(root, owner, aid, payload, authorized=lambda: True):
    whitelist(
        payload,
        {"operation_id", "revision", "answers", "provider"},
        {"operation_id", "revision", "answers", "provider"},
    )
    oid = identifier(payload["operation_id"], "operation_id")
    fingerprint = store.fingerprint(
        {"kind": "grade", "attempt_id": aid, "answers": payload["answers"]}
    )
    old = _existing(root, owner, oid, fingerprint)
    if old:
        return old
    if not authorized():
        fail("登录已失效。", "auth_expired", 401)
    settings = titles.settings(payload["provider"])
    if settings[1] and settings[1] in store.encode(payload["answers"]):
        fail("作答中含当前模型密钥，请移除密钥后再提交。", "credential_in_answer", 409)
    with store.connection(root, owner, write=True) as db:
        value = _attempt(db, aid)
        _validate_binding(db, value, root, owner)
        if value["status"] in ("grading", "grade_failed", "completed"):
            if payload["answers"] != value.get("submitted"):
                fail("已提交答案已冻结，不能替换。", "answers_locked", 409)
            return _public_operation(_operation(db, value["operation_id"]))
        if value["status"] != "ready":
            fail("试卷尚未准备好。", "not_ready", 409)
        if payload["revision"] != value["revision"]:
            fail("草稿版本已变化，请重新读取。", "draft_conflict", 409)
        value["submitted"] = contract.answers(payload["answers"], value["paper"]["questions"])
        value["draft"] = copy.deepcopy(value["submitted"])
        op = _new_job(db, value, oid, "grade", fingerprint, settings[2])
    return _launch(root, owner, op, settings, authorized)


def retry(root, owner, aid, payload, authorized=lambda: True):
    whitelist(payload, {"operation_id", "provider"}, {"operation_id", "provider"})
    oid = identifier(payload["operation_id"], "operation_id")
    fingerprint = store.fingerprint({"kind": "retry", "attempt_id": aid})
    old = _existing(root, owner, oid, fingerprint)
    if old:
        return old
    settings = titles.settings(payload["provider"])
    if not authorized():
        fail("登录已失效。", "auth_expired", 401)
    with store.connection(root, owner, write=True) as db:
        previous = (
            db.execute(
                "SELECT fingerprint,payload FROM self_check_operations WHERE id=?", (oid,)
            ).fetchone()
            if _exists(db)
            else None
        )
        if previous:
            if previous[0] != fingerprint:
                fail("任务编号冲突。", "idempotency_conflict", 409)
            return _public_operation(json.loads(previous[1]))
        value = _attempt(db, aid)
        _validate_binding(db, value, root, owner)
        if value["status"] not in ("generate_failed", "grade_failed"):
            fail("本阶段无需恢复，请读取已有结果。", "not_retryable", 409)
        kind = "grade" if value.get("submitted") else "generate"
        op = _new_job(db, value, oid, kind, fingerprint, settings[2])
    return _launch(root, owner, op, settings, authorized)


def cancel(root, owner, oid):
    with _guard:
        flag = _workers.get((str(root), owner, oid))
        if flag:
            flag.set()
    with store.connection(root, owner, write=True) as db:
        op = _operation(db, oid)
        if op["status"] == "running":
            value = _attempt(db, op["attempt_id"])
            op.update(
                status="cancelled",
                message="自测任务已停止，已保存内容保留。",
                failure={"code": "cancelled", "error": "已停止；可主动恢复本阶段。"},
            )
            _save_operation(db, op)
            value.update(status=op["kind"] + "_failed", failure=op["failure"])
            _save_attempt(db, value)
        return _public_operation(op)


def _prepare_summary(root, owner, oid, target, key, model, check):
    """Replace the method blueprint with a summary of this conversation's math."""
    with store.connection(root, owner) as db:
        op = _operation(db, oid)
        value = _attempt(db, op["attempt_id"])
        if value["frozen"].get("summary"):
            return
        label = value["frozen"]["blueprint"]["label"]
        material = summary.rounds(root, owner, value["session_id"])
    if not material:
        fail("尚无可总结的完整交流，请先围绕当前方法学习。", "insufficient_evidence", 409)
    check(True)
    result = summary.generate(target, key, model, label, material)
    check(True)
    blueprint = summary.blueprint(
        value["method_id"], label, result["summary"], result["points"]
    )
    frozen = contract.freeze(root, owner, value["session_id"], blueprint, secrets=(key,))
    frozen["summary"] = result["summary"]
    with store.connection(root, owner, write=True) as db:
        op = _operation(db, oid)
        value = _attempt(db, op["attempt_id"])
        if op["status"] != "running":
            fail("自测任务已停止。", "cancelled", 409)
        _validate_binding(db, value, root, owner)
        value["frozen"] = frozen
        value["label"] = blueprint["label"]
        op["calls"] += 1
        op["used_tokens"] += (result.get("usage") or {}).get("total_tokens", 0)
        op["message"] = "已总结本会话的数学内容，正在准备题目…"
        _save_attempt(db, value)
        _save_operation(db, op)


def _run(root, owner, oid, settings, authorized, flag):
    target, key, model = settings
    target = model_target(target, model)
    started = time.monotonic()
    last_check = 0

    def check(force=False):
        nonlocal last_check
        if flag.is_set():
            fail("自测已停止。", "cancelled", 409)
        if time.monotonic() - started > MAX_SECONDS:
            fail("本次自测请求超时，原卷保留。", "budget_limit", 409)
        if not force and time.monotonic() - last_check < 0.2:
            return
        if not authorized():
            fail("登录已失效，任务已停止。", "auth_expired", 401)
        with store.connection(root, owner) as db:
            op = _operation(db, oid)
            if op["status"] != "running":
                fail("自测任务已停止。", "cancelled", 409)
            _validate_binding(db, _attempt(db, op["attempt_id"]), root, owner)
        last_check = time.monotonic()

    try:
        check(True)
        with store.connection(root, owner) as db:
            op = _operation(db, oid)
            value = _attempt(db, op["attempt_id"])
            previous = recent_questions(db, value) if op["kind"] == "generate" else []
        kind = op["kind"]
        if kind == "generate":
            _prepare_summary(root, owner, oid, target, key, model, check)
            with store.connection(root, owner) as db:
                op = _operation(db, oid)
                value = _attempt(db, op["attempt_id"])
                previous = recent_questions(db, value)
        name = "prepare_self_check" if kind == "generate" else "grade_self_check"
        system = contract.PREPARE_SYSTEM if kind == "generate" else contract.GRADE_SYSTEM

        def call(sample, schema, repair, feedback):
            check(True)
            encoded = store.encode(sample)
            if len(encoded) > 100000:
                fail("学习材料超出本次输入预算。", "budget_limit", 409)
            if key and key in encoded:
                fail("作答中含当前模型密钥，请移除后再提交。", "credential_in_answer", 409)
            messages = [{"role": "system", "content": system}, {"role": "user", "content": encoded}]
            if feedback:
                messages.append(
                    {
                        "role": "user",
                        "content": feedback.replace(key, "[已隐藏]") if key else feedback,
                    }
                )
            with store.connection(root, owner, write=True) as db:
                item = _operation(db, oid)
                item["calls"] += 1
                if item["calls"] > 3:
                    fail("达到本阶段请求预算，已校验题目和作答保留。", "budget_limit", 409)
                item.update(
                    input_chars=len(encoded),
                    input_fingerprint=store.fingerprint(sample),
                    prompt_version=contract.VERSION,
                )
                if kind == "generate":
                    item.update(
                        evidence_sent=len(sample["evidence"]),
                        evidence_ids_sent=[e["id"] for e in sample["evidence"]],
                        comparison_questions=len(previous),
                        comparison_question_ids=[q["id"] for q in previous],
                    )
                _save_operation(db, item)

            def on_retry(_):
                check(True)
                with store.connection(root, owner, write=True) as db:
                    item = _operation(db, oid)
                    if item["calls"] >= 3:
                        fail("网络重试预算已用完，已保存内容保留。", "budget_limit", 409)
                    item["calls"] += 1
                    item["message"] = "连接暂时失败，正在恢复本次请求…"
                    _save_operation(db, item)

            with provider.request_scope(
                cancelled=flag,
                check_cancelled=check,
                on_retry=on_retry,
                tool_argument_limit=64000,
                operation_id=oid,
                phase="self_check",
                step=repair + 1,
            ):
                answer, calls, usage, _, _ = provider.stream(
                    target,
                    key,
                    {
                        "model": model,
                        "messages": messages,
                        "stream": study_model.streaming(model),
                        "tools": [
                            {
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "description": "只返回当前阶段需要的自测结构化内容",
                                    "parameters": schema,
                                },
                            }
                        ],
                        "tool_choice": {"type": "function", "function": {"name": name}},
                        **model_options(model, kind, repair),
                    },
                    lambda _: None,
                )
            check(True)
            with store.connection(root, owner, write=True) as db:
                item = _operation(db, oid)
                item["used_tokens"] += (usage or {}).get("total_tokens", 0)
                _save_operation(db, item)
            return workflow.decode(answer, calls, name)

        def save_checkpoint(checkpoint):
            check(True)
            with store.connection(root, owner, write=True) as db:
                item = _operation(db, oid)
                current = _attempt(db, item["attempt_id"])
                if item["status"] != "running" or current["operation_id"] != oid:
                    fail("任务已停止。", "cancelled", 409)
                current["generation_checkpoint"] = copy.deepcopy(checkpoint)
                _save_attempt(db, current)
                item["validation_issues"] = checkpoint["issues"]
                item["message"] = (
                    "正在补齐未完成题目…" if checkpoint["accepted"] else "正在核对题目依据…"
                )
                _save_operation(db, item)

        result = (
            workflow.generate(
                value["frozen"], previous, call, save_checkpoint, value.get("generation_checkpoint")
            )
            if kind == "generate"
            else workflow.grade(value, call)
        )
        check(True)
        with store.connection(root, owner, write=True) as db:
            op = _operation(db, oid)
            value = _attempt(db, op["attempt_id"])
            if op["status"] != "running" or flag.is_set():
                return
            _validate_binding(db, value, root, owner)
            if not authorized():
                fail("登录已失效，未提交结果。", "auth_expired", 401)
            if kind == "generate":
                value.update(
                    paper=result,
                    status="ready" if result["ready"] else "insufficient",
                    paper_prompt_version=contract.VERSION,
                )
            else:
                value.update(result=result, status="completed")
            value.pop("generation_checkpoint", None)
            value["failure"] = None
            _save_attempt(db, value)
            op.update(
                status="succeeded", message="试卷已保存。" if kind == "generate" else "评价已保存。"
            )
            _save_operation(db, op)
    except Exception as error:
        try:
            with store.connection(root, owner, write=True) as db:
                op = _operation(db, oid)
                if op["status"] == "running":
                    value = _attempt(db, op["attempt_id"])
                    failure = {
                        "code": getattr(error, "code", "self_check_failed"),
                        "error": safe_text(error, key, 500),
                    }
                    op.update(
                        status="failed", failure=failure, message="本阶段未完成，已保存内容保留。"
                    )
                    _save_operation(db, op)
                    value.update(status=op["kind"] + "_failed", failure=failure)
                    _save_attempt(db, value)
        except Exception:
            pass
    finally:
        with _guard:
            _workers.pop((str(root), owner, oid), None)
