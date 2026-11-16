from flask import Blueprint, jsonify, request

from agent import eventlog, experiment_store, experiment_workflow, experiments, provider, titles
from agent.api.auth_api import current, require
from agent.api.session_access import check_session
from config import USER_ROOT

experiments_api = Blueprint("experiments_api", __name__)


@experiments_api.before_request
def guard():
    if request.endpoint in (
        "experiments_api.run",
        "experiments_api.explain",
        "experiments_api.saved_explanation",
        "experiments_api.sidebar",
    ):
        return require()


@experiments_api.after_request
def private_explanations(response):
    if request.endpoint in (
        "experiments_api.explain",
        "experiments_api.saved_explanation",
        "experiments_api.sidebar",
    ):
        response.headers["Cache-Control"] = "private, no-store"
    return response


@experiments_api.get("/catalog")
def catalog():
    return jsonify(experiments.catalog(str(experiments.PROJECT_ROOT)))


@experiments_api.post("/explain")
def explain():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    try:
        session = check_session(payload.get("session"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 404
    key = payload.get("api_key")
    try:
        settings = titles.settings(payload)
        return jsonify(
            experiment_workflow.explain(USER_ROOT, current(), session, settings, payload)
        )
    except provider.ProviderError as error:
        message = (
            str(error)[:600].replace(key, "[已隐藏]")
            if isinstance(key, str) and key
            else str(error)[:600]
        )
        return jsonify({"error": message}), error.status
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400


@experiments_api.post("/explain/saved")
def saved_explanation():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    try:
        session = check_session(payload.get("session"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 404
    try:
        return jsonify(
            experiment_workflow.saved_explanation(USER_ROOT, current(), session, payload)
        )
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400


@experiments_api.post("/run")
def run():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    context = payload.get("context")
    if context is not None and not isinstance(context, dict):
        return jsonify({"error": "实验上下文无效。"}), 400
    context = dict(context or {})
    # Manual reruns use the panel's explicit source. Never trust a client-supplied
    # conversation selection as authoritative role configuration.
    context.pop("selected_dataset", None)
    session_id = payload.get("session")
    if session_id is not None and not isinstance(session_id, str):
        return jsonify({"error": "会话编号无效。"}), 400
    if session_id:
        try:
            check_session(session_id)
        except ValueError as error:
            return jsonify({"error": str(error)}), 404
    session_id, context = experiment_workflow.prepare_run(USER_ROOT, current(), payload, context)
    try:
        result = experiment_workflow.run(
            USER_ROOT, current(), str(experiments.PROJECT_ROOT), payload, session_id, context
        )
    except experiments.Unavailable as error:
        return jsonify({"error": str(error)}), 400
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({**result, "session": session_id})


@experiments_api.route("/sidebar", methods=["GET", "POST"])
def sidebar():
    payload = (request.get_json(silent=True) or {}) if request.method == "POST" else request.args
    try:
        session = check_session(payload.get("session"))
        if request.method == "POST":
            state = experiment_store.mutate(
                USER_ROOT,
                current(),
                session,
                payload.get("action"),
                payload.get("experiment_id"),
                payload.get("version"),
            )
        else:
            state = experiment_store.load(USER_ROOT, current(), session)
        return jsonify(experiment_store.public(state))
    except (ValueError, eventlog.LogError) as error:
        return jsonify({"error": str(error)}), 400
