import json
import queue
import threading

from flask import Blueprint, Response, jsonify, request, stream_with_context

from agent import data_store, eventlog, learning, provider, retriever, runtime
from agent.api.auth_api import current
from agent.api.session_access import check_session
from config import (
    AGENT_API_MAX_UPLOAD_LENGTH as MAX_UPLOAD_LENGTH,
)
from config import AGENT_STREAM_HEARTBEAT_SECONDS, PROJECT_ROOT, USER_ROOT
from engine import account_datasets, catalog


def _session_log(session_id):
    if not isinstance(session_id, str) or not eventlog.SESSION_ID.match(session_id):
        raise ValueError("对话编号无效。")
    username = current()
    if not username:
        raise ValueError("请先登录。")
    check_session(session_id, allow_new=True)
    return eventlog.SessionLog(USER_ROOT, username, session_id)


agent_api = Blueprint("agent_api", __name__)


@agent_api.before_request
def _guard():
    from agent.api.auth_api import require

    denied = require()
    if denied is not None or request.method != "POST":
        return denied
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "请求必须为 JSON 对象。"}), 400


def _public_tools():
    tools = []
    for tool in runtime.ALL_TOOLS:
        function = tool["function"]
        tools.append(
            {
                "name": function["name"],
                "description": function["description"],
                "parameters": function["parameters"],
            }
        )
    return tools


@agent_api.get("/tools")
def tools():
    return jsonify(
        {
            "tools": _public_tools(),
            "limits": {
                "max_steps": runtime.MAX_STEPS,
                "max_methods_per_run": runtime.ml_tools.MAX_METHODS,
            },
            "execution": "server",
            "rag": retriever.RETRIEVER.status(),
        }
    )


@agent_api.post("/cancel")
def cancel():
    payload = request.get_json(silent=True) or {}
    token = payload.get("session")
    if not isinstance(token, str) or not token:
        return jsonify({"error": "会话编号无效。"}), 400
    return jsonify({"cancelled": runtime.RUNTIME.cancel(token)})


def _learning_root():
    owner = current()
    if not owner:
        raise ValueError("请先登录。")
    return USER_ROOT, owner


@agent_api.get("/learning/graph")
def learning_graph():
    try:
        _learning_root()
        return jsonify(catalog.graph())
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@agent_api.get("/learning")
def learning_map():
    try:
        root, owner = _learning_root()
        return jsonify(learning.project_curriculum(root, owner))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except eventlog.LogError as error:
        return jsonify({"error": str(error)}), 400


@agent_api.post("/learning/studying")
def learning_studying():
    payload = request.get_json(silent=True) or {}
    try:
        root, owner = _learning_root()
        key = payload.get("key")
        if isinstance(key, str) and key:
            learning.mark_studying(root, owner, key, payload.get("active") is True)
        return jsonify(learning.project_curriculum(root, owner))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@agent_api.post("/learning/progress")
def learning_progress():
    payload = request.get_json(silent=True) or {}
    try:
        root, owner = _learning_root()
        if payload.get("reset") is True:
            learning.clear_progress(root, owner)
        elif "key" in payload:
            learning.mark(root, owner, payload.get("key"), payload.get("done") is True)
        return jsonify(learning.project_curriculum(root, owner))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


def _mask_event(event, key):
    if not key:
        return event
    masked = dict(event)
    for field in ("text", "message", "model", "name"):
        if isinstance(masked.get(field), str):
            masked[field] = masked[field].replace(key, "[已隐藏]")
    return masked


def _sse(event):
    return "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"


def _chat_failure(error, key):
    message = str(error)
    if key:
        message = message.replace(key, "[已隐藏]")
    return message[:900]


def _error_event(error, key):
    event = {"type": "error", "message": _chat_failure(error, key)}
    if isinstance(error, provider.ProviderError):
        event.update(
            {
                "code": error.code,
                "status": error.status,
                "request_id": error.request_id,
                "attempts": error.attempts,
            }
        )
    return event


def _run_blocking(token, model_request):
    events = []

    def emit(event):
        events.append(_mask_event(event, model_request.key))

    try:
        runtime.RUNTIME.run(token, emit)
    except runtime.Cancelled:
        events.append({"type": "error", "message": "本轮已取消，未完成的工具没有执行结果。"})
    except Exception as error:
        events.append(_error_event(error, model_request.key))
    finally:
        runtime.RUNTIME.drop(token)
    return jsonify({"events": events})


def _run_streaming(token, model_request):
    messages = queue.Queue()
    key = model_request.key

    def emit(event):
        messages.put(("event", _mask_event(event, key)))

    def worker():
        try:
            runtime.RUNTIME.run(token, emit)
        except runtime.Cancelled:
            messages.put(
                ("event", {"type": "error", "message": "本轮已取消，未完成的工具没有执行结果。"})
            )
        except Exception as error:
            messages.put(("event", _error_event(error, key)))
        finally:
            runtime.RUNTIME.drop(token)
            messages.put(("close", None))

    thread = threading.Thread(target=worker, name="dsh-agent", daemon=True)
    thread.start()
    yield _sse(
        {
            "type": "start",
            "session": token,
            "model": model_request.model,
            "tools": model_request.allow_tools,
            "execution": "server",
        }
    )
    while True:
        try:
            kind, payload = messages.get(timeout=AGENT_STREAM_HEARTBEAT_SECONDS)
        except queue.Empty:
            yield ": keep-alive\n\n"
            continue
        if kind == "close":
            break
        yield _sse(payload)


@agent_api.post("/chat")
def chat():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    payload = dict(payload)
    try:
        payload["log"] = _session_log(payload.get("session"))
        if isinstance(payload.get("context"), dict):
            payload["context"] = account_datasets.context(
                USER_ROOT, current(), PROJECT_ROOT, payload["session"], payload["context"]
            )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    try:
        from agent import experiment_store

        log = payload["log"]
        if not isinstance(payload.get("context"), dict):
            raise ValueError("缺少实验快照。")
        view = payload["context"].pop("sidebar_view", None)
        payload["sidebar"] = experiment_store.evidence(
            log.root, log.owner, payload["session"], view
        )
        model_request = runtime.Request(payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    try:
        token, _ = runtime.RUNTIME.create(model_request)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if request.headers.get("X-DSH-Blocking") == "1":
        return _run_blocking(token, model_request)
    return Response(
        stream_with_context(_run_streaming(token, model_request)),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@agent_api.post("/data/prepare")
def data_prepare():
    payload = request.get_json(silent=True) or {}
    version = payload.get("version")
    shape = payload.get("shape")
    if not isinstance(version, str) or not version:
        return jsonify({"error": "数据版本号无效。"}), 400
    if data_store.STORE.has(version):
        stored = data_store.STORE.get(version)
        return jsonify(
            {"version": version, "stored": True, "shape": data_store.STORE.shape(stored)}
        )
    if not isinstance(shape, dict):
        return jsonify({"error": "缺少数据规模信息。"}), 400
    return jsonify(
        {
            "version": version,
            "stored": False,
            "expected_shape": shape,
            "upload": "/api/agent/data",
            "max_length": MAX_UPLOAD_LENGTH,
        }
    )


@agent_api.post("/data")
def data_upload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "数据格式无效。"}), 400
    try:
        shape = data_store.STORE.put(payload.get("version"), payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"stored": True, "version": payload.get("version"), "shape": shape})
