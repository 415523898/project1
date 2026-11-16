from flask import Blueprint, jsonify, request

from agent import credential_vault
from agent.api.auth_api import current, require, token_of

providers_api = Blueprint("providers_api", __name__)


@providers_api.before_request
def guard():
    denied = require()
    if denied is not None:
        return denied
    if request.method not in ("GET", "OPTIONS"):
        from agent.api.auth_api import AUTH

        AUTH.require_recent(token_of())


@providers_api.get("")
def listing():
    return jsonify(
        {
            "providers": credential_vault.for_app().list(current()),
        }
    )


@providers_api.post("/<identifier>")
def save(identifier):
    try:
        return jsonify(
            credential_vault.for_app().save(current(), identifier, request.get_json(silent=True))
        )
    except credential_vault.VaultError:
        raise
    except (ValueError, TypeError, AttributeError):
        return jsonify({"error": "提供商配置无效，请检查 API 地址、模型和参数。"}), 400


@providers_api.post("/<identifier>/delete")
def delete(identifier):
    credential_vault.for_app().delete(current(), identifier)
    return jsonify({"deleted": True})
