import time

from flask import Blueprint, jsonify, request

from agent import provider, provider_models

ai_api = Blueprint("ai_api", __name__)


def upstream_failure(error, key=""):
    # Vendor authentication failures must not sign the user out of this application.
    auth_failure = error.status in (401, 403)
    message = str(error)[:600].replace(key, "[已隐藏]") if key else str(error)[:600]
    return jsonify(
        {"error": message, "code": "upstream_error" if auth_failure else error.code}
    ), 502 if auth_failure else error.status


@ai_api.before_request
def guard():
    from agent.api.auth_api import require

    return require()


@ai_api.post("/models")
def models():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    try:
        return jsonify(provider_models.list_models(payload))
    except provider.ProviderError as error:
        return upstream_failure(error)
    except (ValueError, AttributeError):
        return jsonify({"error": "模型目录请求无效，请核对上游地址、协议和密钥。"}), 400


@ai_api.post("/test")
def test_connection():
    started = time.perf_counter()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "请求格式无效。"}), 400
    raw_model = payload.get("model")
    model = raw_model.strip() if isinstance(raw_model, str) else ""
    if not model or len(model) > 200:
        return jsonify({"error": "请填写模型名。"}), 400
    try:
        key = provider.provider_options.request_key(payload.get("api_key"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    raw_base = payload.get("base_url")
    try:
        target = provider.endpoint(raw_base.strip() if isinstance(raw_base, str) else "", payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    request_payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请只回复：连接成功"}],
        "stream": False,
    }
    try:
        result = provider.call(target, key, request_payload)
    except provider.ProviderError as error:
        return upstream_failure(error, key)
    parsed = provider.parse_message(result)
    if not parsed["answer"]:
        return jsonify({"error": "接口未返回回答正文，请检查请求协议与模型名称。"}), 400
    return jsonify(
        {
            "answer": parsed["answer"].replace(key, "[已隐藏]"),
            "model": parsed["model"] or model,
            "usage": parsed["usage"],
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }
    )
