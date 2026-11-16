from flask import Blueprint, jsonify, request

from agent import dataset_autofill, eventlog, provider, titles
from agent.api.auth_api import current, require
from agent.api.session_access import check_session
from config import PROJECT_ROOT, USER_ROOT
from engine import account_datasets as library
from engine import dataset_preview

files_api = Blueprint("files_api", __name__)


@files_api.before_request
def guard():
    return require()


@files_api.after_request
def private(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


@files_api.get("")
def listing():
    try:
        library.import_legacy(USER_ROOT, current(), PROJECT_ROOT)
        return jsonify(
            {
                "files": library.listing(USER_ROOT, current()),
                "builtins": library.builtins(PROJECT_ROOT),
            }
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@files_api.post("")
def upload():
    handle = request.files.get("file")
    if handle is not None:
        name = handle.filename
        blob = handle.read()
    else:
        name = request.args.get("name", "")
        blob = request.get_data(cache=False)
    try:
        return jsonify(library.save(USER_ROOT, current(), name, blob))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@files_api.get("/preview")
def preview():
    try:
        return jsonify(
            dataset_preview.page(
                USER_ROOT,
                current(),
                PROJECT_ROOT,
                request.args.get("dataset"),
                int(request.args.get("offset", 0)),
                int(request.args.get("limit", 50)),
            )
        )
    except (ValueError, TypeError, OSError) as error:
        return jsonify({"error": str(error)}), 400


@files_api.post("/configure")
def configure():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(library.configure(USER_ROOT, current(), payload.get("id"), payload))
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400


@files_api.post("/select")
def select():
    payload = request.get_json(silent=True) or {}
    try:
        session = check_session(payload.get("session"))
        return jsonify(
            {
                "selected_dataset": library.select(
                    USER_ROOT, current(), PROJECT_ROOT, session, payload.get("dataset")
                )
            }
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@files_api.get("/current")
def current_dataset():
    try:
        session = check_session(request.args.get("session"))
        return jsonify(
            {"current_dataset": library.current_info(USER_ROOT, current(), PROJECT_ROOT, session)}
        )
    except (ValueError, OSError, eventlog.LogError) as error:
        return jsonify({"error": str(error)}), 400


@files_api.post("/suggest")
def suggest():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    key = payload.get("api_key")
    try:
        settings = titles.settings(payload)
        result = dataset_autofill.suggest(
            USER_ROOT, current(), payload.get("id"), PROJECT_ROOT, settings
        )
        return jsonify(result)
    except provider.ProviderError as error:
        message = (
            str(error).replace(key, "[已隐藏]") if isinstance(key, str) and key else str(error)
        )
        return jsonify({"error": message[:600]}), error.status
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400


@files_api.post("/delete")
def delete():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(library.delete(USER_ROOT, current(), payload.get("id")))
    except (ValueError, OSError) as error:
        return jsonify({"error": str(error)}), 400
