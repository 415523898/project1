from flask import Blueprint, jsonify, request

from agent import conversations, eventlog, provider, titles
from agent.api.auth_api import current, require
from agent.api.session_access import check_session
from config import PROJECT_ROOT, USER_ROOT

conversations_api = Blueprint("conversations_api", __name__)


def store():
    owner = current()
    return eventlog.Store(USER_ROOT, owner)


@conversations_api.before_request
def guard():
    return require()


@conversations_api.after_request
def private(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


@conversations_api.get("")
def list_sessions():
    try:
        return jsonify(conversations.listing(USER_ROOT, current()))
    except eventlog.LogError as error:
        return jsonify({"error": str(error)}), 400


@conversations_api.get("/workspaces")
def list_workspaces():
    return jsonify({"workspaces": store().workspaces()})


@conversations_api.get("/get")
def get_session():
    session_id = request.args.get("id", "")
    try:
        return jsonify(conversations.get(USER_ROOT, current(), session_id))
    except (eventlog.LogError, ValueError) as error:
        return jsonify({"error": str(error)}), 404


@conversations_api.post("/save")
def save_session():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "对话内容无效。"}), 400
    session_id = payload.get("id")
    if session_id is not None and not isinstance(session_id, str):
        return jsonify({"error": "对话编号无效。"}), 400
    if session_id:
        try:
            check_session(session_id, allow_new=True)
        except ValueError as error:
            return jsonify({"error": str(error)}), 404
    try:
        return jsonify(store().save(session_id, payload))
    except eventlog.LogError as error:
        return jsonify({"error": str(error)}), 400


@conversations_api.post("/title")
def generate_title():
    payload = request.get_json(silent=True)
    try:
        target, key, model = titles.settings(payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    try:
        return jsonify(titles.name_once(store(), payload.get("id"), (target, key, model)))
    except eventlog.LogError as error:
        return jsonify({"error": str(error)}), 404
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except provider.ProviderError as error:
        return jsonify({"error": str(error)[:600].replace(key, "[已隐藏]")}), error.status


@conversations_api.post("/delete")
def delete_session():
    payload = request.get_json(silent=True) or {}
    try:
        from agent import study_binding

        store().get(payload.get("id"))
        binding = study_binding.public(USER_ROOT, current(), payload.get("id"))
        if (
            binding
            and not binding["card_missing"]
            and payload.get("delete_choice") not in {"only", "both"}
        ):
            return jsonify(
                {"error": "是否同步删除对应的卡片？", "code": "delete_choice_required"}
            ), 409
        outcome = study_binding.delete_session(
            USER_ROOT,
            current(),
            PROJECT_ROOT,
            payload.get("id"),
            payload.get("delete_choice") == "both",
        )
    except eventlog.LogError as error:
        return jsonify({"error": str(error)}), 400
    except ValueError as error:
        return jsonify(
            error.public() if hasattr(error, "public") else {"error": str(error)}
        ), getattr(error, "status", 400)
    return jsonify(outcome)


@conversations_api.post("/fork")
def fork_session():
    from agent import conversation_actions

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求必须为 JSON 对象。"}), 400
    try:
        return jsonify(
            conversation_actions.fork(
                USER_ROOT, current(), payload.get("id"), payload.get("event_id")
            )
        )
    except eventlog.LogError as error:
        return jsonify({"error": str(error)}), 404
    except (ValueError, OSError) as error:
        return jsonify({"error": str(error)}), 400
