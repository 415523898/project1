from flask import Blueprint, jsonify, request

from agent import eventlog, learning_exploration, titles
from agent.api.auth_api import current, require
from agent.api.session_access import check_session
from config import USER_ROOT

learning_exploration_api = Blueprint("learning_exploration_api", __name__)


@learning_exploration_api.before_request
def guard():
    return require()


@learning_exploration_api.after_request
def private(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def payload_session():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("请求格式无效。")
    check_session(payload.get("session"))
    return payload, payload["session"]


@learning_exploration_api.get("/state")
def get_state():
    try:
        session = check_session(request.args.get("session"))
        return jsonify(learning_exploration.load(USER_ROOT, current(), session))
    except (ValueError, eventlog.LogError) as error:
        return jsonify({"error": str(error)}), 404


@learning_exploration_api.post("/state")
def save_state():
    try:
        payload, session = payload_session()
        settings = (
            titles.settings(payload["provider"])
            if payload.get("confirm") and payload.get("provider")
            else None
        )
        result = learning_exploration.update(USER_ROOT, current(), session, payload)
        if settings:
            # Binding is already durable; maintenance runs independently of the browser.
            log = eventlog.Store(USER_ROOT, current()).log(session)
            learning_exploration.after_turn(log, settings)
        return jsonify(result)
    except eventlog.LogError as error:
        return jsonify({"error": str(error)}), 404
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@learning_exploration_api.post("/session-card")
def session_card():
    from agent import provider, study_topic

    try:
        payload, session = payload_session()
        settings = titles.settings(payload.get("provider"))
        return jsonify(study_topic.generate(USER_ROOT, current(), session, settings))
    except provider.ProviderError as error:
        return jsonify({"error": str(error)[:600], "code": error.code}), 502
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@learning_exploration_api.post("/match-card")
def match_card():
    from agent import provider, runtime, session_match

    try:
        payload, session = payload_session()
        if runtime.RUNTIME.conversation_status(USER_ROOT, current(), session)["running"]:
            return jsonify({"error": "请等当前回复完成后，再匹配并生成学习卡片。"}), 409
        settings = titles.settings(payload.get("provider"))
        result = session_match.match(USER_ROOT, current(), session, settings)
        if result.get("matched") and not result.get("existing"):
            learning_exploration.after_turn(
                eventlog.Store(USER_ROOT, current()).log(session), settings
            )
        return jsonify(result)
    except eventlog.LogError as error:
        return jsonify({"error": str(error)}), 404
    except provider.ProviderError as error:
        return jsonify({"error": str(error), "code": error.code}), 502
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
