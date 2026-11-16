"""Account-scoped study workspace HTTP API."""

from urllib.parse import unquote

from flask import Blueprint, jsonify, request

from agent import self_check, study_session, study_sources, study_store
from agent.api.auth_api import current, require
from agent.study_graph import StudyError
from config import PROJECT_ROOT, USER_ROOT

study_api = Blueprint("study_api", __name__)


@study_api.before_request
def guard():
    denied = require()
    if denied is not None or request.method == "OPTIONS":
        return denied
    expected_owner = request.headers.get("X-Study-Owner")
    if expected_owner is not None and unquote(expected_owner) != current():
        return jsonify({"error": "登录账号已变化，请重新登录。", "code": "account_changed"}), 409


@study_api.after_request
def private(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


@study_api.errorhandler(StudyError)
def invalid_change(error):
    return jsonify(error.public()), error.status


@study_api.get("/workspace")
def workspace():
    return jsonify(study_store.workspace(USER_ROOT, current()))


@study_api.get("/revision")
def revision():
    return jsonify(study_store.revision_stamp(USER_ROOT, current()))


@study_api.get("/cards/<card_id>")
def card(card_id):
    return jsonify(study_store.get_card(USER_ROOT, current(), card_id))


@study_api.post("/changes")
def changes():
    if request.content_length is not None and request.content_length > 2 * 1024 * 1024:
        return jsonify({"error": "变更超过 2 MiB，请拆分。", "code": "payload_too_large"}), 413
    payload = request.get_json(silent=True)
    operations = payload.get("operations", []) if isinstance(payload, dict) else []
    from agent import eventlog, study_binding

    deleted = (
        {
            op.get("card_id")
            for op in operations
            if isinstance(op, dict) and op.get("op") == "delete_card"
        }
        if isinstance(operations, list)
        else set()
    )
    sessions = [
        sid
        for sid, b in study_binding.all_bindings(USER_ROOT, current()).items()
        if b["card_id"] in deleted
    ]
    choice = payload.get("delete_choice") if isinstance(payload, dict) else None
    if sessions and choice not in {"only", "both"}:
        return jsonify({"error": "是否同步删除对应的会话？", "code": "delete_choice_required"}), 409
    if isinstance(payload, dict) and "delete_choice" in payload:
        if choice not in {"only", "both"}:
            raise StudyError("删除选项无效。")
    ai_request = isinstance(operations, list) and any(
        isinstance(op, dict) and op.get("op") == "ai_relations" for op in operations
    )
    if ai_request:
        raise StudyError("AI 整理卡片功能已移除。", "feature_removed", 410)
    result = study_store.apply_changes(USER_ROOT, current(), payload)
    if choice == "both":
        for sid in sessions:
            if eventlog.SessionLog(USER_ROOT, current(), sid).exists():
                study_binding.delete_session(USER_ROOT, current(), PROJECT_ROOT, sid)
    return jsonify(result), 202 if result["status"] == "running" else 200


@study_api.get("/operations/<operation_id>")
def operation(operation_id):
    return jsonify(study_store.operation_result(USER_ROOT, current(), operation_id))


@study_api.get("/revisions")
def revisions():
    return jsonify(study_store.revisions(USER_ROOT, current()))


@study_api.post("/organize/session")
def organize_session():
    from agent.api.auth_api import AUTH, token_of

    token, owner = token_of(), current()
    try:
        if request.content_length and request.content_length > 64000:
            raise StudyError("整理请求过大。", "payload_too_large", 413)
        result = study_session.start(
            USER_ROOT,
            owner,
            request.get_json(silent=True),
            authorized=lambda: AUTH.resolve(token) == owner,
        )
        return jsonify(result), 202 if result["status"] == "running" else 200
    except ValueError as error:
        if isinstance(error, StudyError):
            raise
        return jsonify({"error": str(error), "code": "invalid_settings"}), 400


@study_api.get("/organize/session/<operation_id>")
def session_operation(operation_id):
    return jsonify(study_session.public(USER_ROOT, current(), operation_id))


@study_api.post("/organize/session/<operation_id>/cancel")
def cancel_session_operation(operation_id):
    return jsonify(study_session.cancel(USER_ROOT, current(), operation_id))


@study_api.get("/sessions/<session_id>/cards")
def cards_for_session(session_id):
    return jsonify(
        study_session.session_cards(USER_ROOT, current(), session_id, request.args.get("since"))
    )


@study_api.get("/sources/<source_id>/locate")
def locate_source(source_id):
    return jsonify(
        study_sources.locate(USER_ROOT, current(), source_id, request.args.get("event_ref"))
    )


@study_api.get("/sessions/<session_id>/self-check")
def self_check_state(session_id):
    return jsonify(self_check.state(USER_ROOT, current(), session_id))


@study_api.get("/self-check/attempts/<attempt_id>")
def self_check_attempt(attempt_id):
    return jsonify(self_check.attempt(USER_ROOT, current(), attempt_id))


def self_check_request(action, *args):
    from agent.api.auth_api import AUTH, token_of

    if request.content_length and request.content_length > 32000:
        raise StudyError("自测请求过大。", "payload_too_large", 413)
    token, owner = token_of(), current()
    try:
        result = action(
            USER_ROOT,
            owner,
            *args,
            request.get_json(silent=True),
            authorized=lambda: AUTH.resolve(token) == owner,
        )
        return jsonify(result), 202 if result.get("status") == "running" else 200
    except ValueError as error:
        if isinstance(error, StudyError):
            raise
        return jsonify({"error": str(error), "code": "invalid_settings"}), 400


@study_api.post("/self-check/start")
def start_self_check():
    return self_check_request(self_check.start)


@study_api.post("/self-check/attempts/<attempt_id>/submit")
def submit_self_check(attempt_id):
    return self_check_request(self_check.submit, attempt_id)


@study_api.post("/self-check/attempts/<attempt_id>/retry")
def retry_self_check(attempt_id):
    return self_check_request(self_check.retry, attempt_id)


@study_api.post("/self-check/attempts/<attempt_id>/draft")
def self_check_draft(attempt_id):
    if request.content_length and request.content_length > 16000:
        raise StudyError("作答草稿过大。", "payload_too_large", 413)
    return jsonify(
        self_check.save_draft(USER_ROOT, current(), attempt_id, request.get_json(silent=True))
    )


@study_api.get("/self-check/operations/<operation_id>")
def read_self_check_operation(operation_id):
    return jsonify(self_check.operation(USER_ROOT, current(), operation_id))


@study_api.post("/self-check/operations/<operation_id>/cancel")
def stop_self_check_operation(operation_id):
    return jsonify(self_check.cancel(USER_ROOT, current(), operation_id))
