"""Request-local provider settings. Targets remain strings for existing job APIs."""

import copy
from urllib.parse import urlsplit

from agent import provider_model_config
from agent.provider_catalog import FAMILIES
from config import MODEL_CHAT_OUTPUT_TOKENS, MODEL_REASONING_MIN_OUTPUT_TOKENS

PROTOCOLS = {"chat", "responses", "anthropic", "gemini"}


def api_key(value, *, allow_empty=False):
    """Credentials are opaque printable ASCII header values, never prose."""
    if (
        not isinstance(value, str)
        or len(value) > 5000
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("请填写有效的 API Key。")
    value = value.strip(" ")
    if not value and allow_empty:
        return value
    if not value or any(not 33 <= ord(character) <= 126 for character in value):
        raise ValueError(
            "API Key 格式无效：请粘贴服务商提供的密钥，不要填写中文、空格或不可见字符。"
        )
    return value


def request_key(value, *, allow_empty=False):
    """请求携带的密钥；不再从环境变量读取，必须由用户在接口设置中提供。"""
    text = value if isinstance(value, str) else ""
    if not text.strip():
        if allow_empty:
            return ""
        raise ValueError("请先在「接口设置」中填写 API Key。")
    return api_key(text, allow_empty=allow_empty)


class Target(str):
    def __new__(cls, value, options=None):
        result = super().__new__(cls, value)
        result.options = dict(options or {})
        return result


def endpoint(base, settings=None):
    parsed = urlsplit(base or "")
    if (
        parsed.scheme not in ("https", "http")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Base URL 需为 http(s) 接口地址，不含账号、查询参数或片段。")
    options = {}
    if settings and any(
        k in settings for k in ("protocol", "provider_family", "reasoning_effort", "model_options")
    ):
        protocol = settings.get("protocol", "chat")
        family = settings.get("provider_family", "custom")
        effort = settings.get("reasoning_effort", "auto")
        if protocol not in PROTOCOLS or family not in {*FAMILIES, "custom"}:
            raise ValueError("模型服务商或请求协议无效。")
        manual = provider_model_config.validate(settings.get("model_options"), protocol)
        requested_effort = effort
        mapping = {}
        if manual and effort != "auto":
            if effort not in manual["efforts"]:
                raise ValueError("此模型未启用该推理等级。")
            mapping = manual["effort_mapping"].get(effort, {})
            if mapping:
                effort = "auto"
        if effort not in (
            "auto",
            "off",
            "enabled",
            "none",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
        ):
            raise ValueError("思考强度无效。")
        model = settings.get("model", "")
        capability = next(
            (m for m in FAMILIES.get(family, {}).get("models", []) if m["id"] == model), None
        )
        if (
            effort != "auto"
            and family != "custom"
            and (not capability or effort not in capability["efforts"])
        ):
            raise ValueError("该模型未确认支持此思考档位，请选择“服务商默认”。")
        expected = FAMILIES.get(family, {}).get("protocol")
        if (
            family != "custom"
            and effort != "auto"
            and protocol != expected
            and not (family == "mimo" and protocol == "anthropic")
            and not (family in ("openai", "grok", "muse") and protocol == "chat")
        ):
            raise ValueError("该协议暂沿用服务商默认思考配置。")
        if protocol == "chat" and family == "openai" and model.startswith("gpt-6"):
            raise ValueError("GPT-6 的工具调用需要 Responses 协议。")
        options = {
            "protocol": protocol,
            "family": family,
            "effort": effort,
            "capability": capability or {},
            "requested_effort": requested_effort,
            "model_options": manual,
            "manual_mapping": mapping,
        }
    protocol = options.get("protocol", "chat")
    value = base.rstrip("/")
    expected = {
        "chat": "/chat/completions",
        "responses": "/responses",
        "anthropic": "/messages",
        "gemini": "",
    }[protocol]
    if expected and value.endswith(expected):
        return Target(value, options)
    for old in ("/chat/completions", "/responses", "/messages"):
        if value.endswith(old):
            value = value[: -len(old)]
            break
    suffix = "/v1/messages" if protocol == "anthropic" and not value.endswith("/v1") else expected
    value += suffix
    return Target(value, options)


def prepare_chat(target, payload):
    result = copy.deepcopy(payload)
    options = getattr(target, "options", {})
    # Native continuation lives only in memory, never on a Chat Completions wire.
    for message in result.get("messages", []):
        message.pop("_native", None)
    if not options:
        return result
    family, effort = options["family"], options["effort"]
    if "max_tokens" not in result and "max_completion_tokens" not in result:
        result["max_tokens"] = MODEL_CHAT_OUTPUT_TOKENS
    if effort != "off" and options.get("capability", {}).get("efforts"):
        for limit in ("max_tokens", "max_completion_tokens"):
            if limit in result:
                result[limit] = max(result[limit], MODEL_REASONING_MIN_OUTPUT_TOKENS)
    for key in ("reasoning_effort", "thinking", "enable_thinking", "temperature", "top_p"):
        result.pop(key, None)
    if family in ("openai", "mimo", "minimax") and "max_tokens" in result:
        result["max_completion_tokens"] = result.pop("max_tokens")
    if family == "minimax":
        result["reasoning_split"] = True
    if effort == "auto":
        return provider_model_config.finalize(target, result)
    if family in ("deepseek", "glm", "mimo", "kimi"):
        result["thinking"] = {"type": "disabled" if effort == "off" else "enabled"}
        if effort not in ("off", "enabled"):
            result["reasoning_effort"] = effort
    elif family == "qwen":
        result["enable_thinking"] = effort != "off"
    elif family == "minimax":
        if effort in ("off", "enabled"):
            result["thinking"] = {"type": "disabled" if effort == "off" else "adaptive"}
        else:
            result["reasoning_effort"] = effort
    elif family not in ("hunyuan", "gemini", "claude"):
        result["reasoning_effort"] = "none" if effort == "off" else effort
    return provider_model_config.finalize(target, result)
