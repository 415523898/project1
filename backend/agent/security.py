"""HTTP guards and saved-credential resolution before API handlers consume JSON."""

import ipaddress
import re
import socket
from urllib.parse import urlsplit

from flask import g, jsonify, request

from agent import auth, credential_vault
from config import MAX_HTTP_REQUEST_BYTES, environment


def public_endpoint(url):
    """Defense in depth: cloud deployments must also block private egress at the network."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("生产环境上游必须使用 HTTPS。")
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("生产环境禁止访问内网或保留地址。")


def install(app):
    production = environment("FOREST_ENV") == "production"
    app.config.update(
        PRODUCTION=production,
        AUTH_COOKIE_SECURE=production,
        AUTH_COOKIE=environment("FOREST_AUTH_COOKIE"),
        REGISTRATION_ENABLED=environment("FOREST_REGISTRATION") == "1",
        MAX_CONTENT_LENGTH=MAX_HTTP_REQUEST_BYTES,
    )
    if production:
        from agent.api.auth_api import AUTH

        credential_vault.keyring(
            AUTH.root / ".vault", True
        )  # Fail closed before accepting traffic.
    hops = int(environment("FOREST_PROXY_HOPS"))
    if hops:
        if hops != 1:
            raise ValueError("当前仅支持一个可信反向代理；FOREST_PROXY_HOPS 应为 0 或 1。")
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0, x_prefix=0)

    @app.errorhandler(auth.AuthError)
    @app.errorhandler(credential_vault.VaultError)
    def safe_error(error):
        response = jsonify({"error": str(error)})
        if error.status == 429:
            response.headers["Retry-After"] = "900"
        return response, error.status

    @app.before_request
    def protect():
        if not request.path.startswith("/api/") or request.method == "OPTIONS":
            return None
        if production and not request.is_secure:
            return jsonify({"error": "生产环境仅接受 HTTPS。"}), 400
        if request.method not in ("GET", "HEAD"):
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                return jsonify({"error": "拒绝跨站写入。"}), 403
            if (production or request.headers.get("Origin")) and request.headers.get(
                "X-Forest-Request"
            ) != "1":
                return jsonify({"error": "缺少请求校验头，请从当前前端重试。"}), 403
        payload = request.get_json(silent=True) if request.is_json else None
        if not isinstance(payload, dict) or request.path.startswith("/api/providers"):
            return None
        consumers = {
            "/api/ai/test",
            "/api/ai/models",
            "/api/agent/chat",
            "/api/agent/learning/conversations/arrange",
            "/api/agent/learning/route",
            "/api/conversations/title",
            "/api/files/suggest",
            "/api/experiments/explain",
            "/api/study/organize/session",
            "/api/learning-exploration/state",
            "/api/learning-exploration/match-card",
            "/api/learning-exploration/session-card",
        }
        quiz_model = request.path == "/api/study/self-check/start" or bool(
            re.fullmatch(r"/api/study/self-check/attempts/[^/]+/(submit|retry)", request.path)
        )
        if request.path not in consumers and not quiz_model:
            return None
        candidates = [payload]
        if isinstance(payload.get("provider"), dict):
            candidates.append(payload["provider"])
        from agent.api.auth_api import AUTH, token_of

        for config in candidates:
            if "credential_id" in config:
                owner = AUTH.resolve(token_of())
                if not owner:
                    raise auth.AuthError("请先登录。", 401)
                g.username = owner
                credential_vault.for_app().resolve(
                    owner, config, catalog=request.path == "/api/ai/models"
                )

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "private, no-store"
        return response
