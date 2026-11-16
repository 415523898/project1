from flask import Blueprint, jsonify, send_file

from agent.api.auth_api import require
from agent.api.session_access import check_session
from config import FIGURE_ROOT, IMAGE_TYPES

figures_api = Blueprint("figures_api", __name__)


def serve_figure(name):
    denied = require()
    if denied is not None:
        return denied
    target = (FIGURE_ROOT / name).resolve()
    try:
        relative = target.relative_to(FIGURE_ROOT.resolve())
    except ValueError:
        return jsonify({"error": "路径无效。"}), 403
    try:
        check_session(relative.parts[0] if len(relative.parts) > 1 else None)
    except ValueError:
        return jsonify({"error": "图不存在或不属于当前账号。"}), 404
    if not target.is_file() or target.suffix.lower() not in IMAGE_TYPES:
        return jsonify({"error": "图不存在。"}), 404
    response = send_file(target, mimetype=IMAGE_TYPES[target.suffix.lower()], max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    return response


figures_root = Blueprint("figures_root", __name__)


@figures_root.get("/<path:name>")
def figure_file(name):
    return serve_figure(name)


@figures_api.get("/<path:name>")
def figure(name):
    return serve_figure(name)
