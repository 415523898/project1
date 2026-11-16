from flask import Blueprint, current_app, g, jsonify, request

from agent import auth, session_cookie
from config import USER_ROOT

AUTH = auth.store(USER_ROOT)

auth_api = Blueprint("auth_api", __name__)


def token_of():
    cookie = session_cookie.read()
    if cookie:
        return cookie
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return request.headers.get("X-Auth-Token", "").strip()


def current():
    return getattr(g, "username", None)


def require():
    if request.method == "OPTIONS":
        return None
    username = AUTH.resolve(token_of())
    if username is None:
        return jsonify({"error": "请先登录。"}), 401
    g.username = username
    return None


@auth_api.post("/register")
def register():
    if not current_app.config.get("REGISTRATION_ENABLED", True):
        return jsonify({"error": "服务器已关闭公开注册。"}), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    try:
        AUTH._throttle("registration:" + str(request.remote_addr), request.remote_addr)
        created = AUTH.register(payload.get("username"), payload.get("password"))
    except auth.AuthError as error:
        return jsonify({"error": str(error)}), error.status
    # Registration already validated and stored these credentials. Issuing its
    # session must not consume a second login slot after account creation.
    session = AUTH.issue(created["username"])
    return session_cookie.attach(
        jsonify({**created, "username": session["username"]}), session["token"]
    )


@auth_api.post("/login")
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    try:
        session = AUTH.login(payload.get("username"), payload.get("password"), request.remote_addr)
    except auth.AuthError as error:
        return jsonify({"error": str(error)}), error.status
    return session_cookie.attach(jsonify({"username": session["username"]}), session["token"])


@auth_api.post("/logout")
def logout():
    response = jsonify({"logged_out": AUTH.logout(token_of())})
    return session_cookie.clear(response)


@auth_api.get("/me")
def me():
    username = AUTH.resolve(token_of())
    if username is None:
        return jsonify({"error": "未登录。"}), 401
    return jsonify({"username": username})


@auth_api.post("/reauthenticate")
def reauthenticate():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    username = AUTH.reauthenticate(token_of(), payload.get("password"), request.remote_addr)
    return jsonify({"username": username, "verified": True})


@auth_api.post("/password")
def password():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    session = AUTH.change_password(
        token_of(), payload.get("password"), payload.get("new_password"), request.remote_addr
    )
    return session_cookie.attach(
        jsonify({"username": session["username"], "changed": True}), session["token"]
    )


@auth_api.post("/logout-all")
def logout_all():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    username = AUTH.reauthenticate(token_of(), payload.get("password"), request.remote_addr)
    AUTH.logout_all(username)
    return session_cookie.clear(jsonify({"logged_out": True}))
