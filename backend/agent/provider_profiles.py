"""Provider profile normalization independent of HTTP, encryption and persistence."""

import json

from agent import provider_catalog, provider_model_config, provider_options


class InvalidProfile(ValueError):
    """Profile errors retaining the vault's existing public validation messages."""


def model_options(model):
    """Return only explicitly filled overrides. Legacy smart:true stays automatic."""
    if model.get("smart") is True:
        return None
    options = {
        key: model[key]
        for key in provider_model_config.FIELDS
        if key in model and model[key] is not None
    }
    return {key: value for key, value in options.items() if value not in (None, [], {})} or None


def normalize(identifier, settings):
    allowed = {
        "base_url",
        "model",
        "allow_tools",
        "detail",
        "provider_id",
        "provider_family",
        "protocol",
        "reasoning_effort",
        "enabled",
        "models",
        "preset_id",
        "profile_name",
    }
    if (
        not isinstance(settings, dict)
        or set(settings) - allowed
        or settings.get("provider_id") != identifier
    ):
        raise InvalidProfile("提供商配置字段无效。")
    if len(json.dumps(settings)) > 256000:
        raise InvalidProfile("提供商配置过大。")
    settings = json.loads(json.dumps(settings))
    if "preset_id" in settings and (
        not isinstance(settings["preset_id"], str)
        or settings["preset_id"] not in {*provider_catalog.PRESETS, "custom"}
    ):
        raise InvalidProfile("供应商预设无效。")
    if "profile_name" in settings and (
        not isinstance(settings["profile_name"], str)
        or len(settings["profile_name"]) > 80
        or any(ord(c) < 32 for c in settings["profile_name"])
    ):
        raise InvalidProfile("配置名称需为 80 字符以内的单行文本。")
    settings = provider_catalog.metadata(identifier, settings)
    protocol = settings.get("protocol", "chat")
    base = settings.get("base_url")
    if not isinstance(base, str):
        raise InvalidProfile("API 地址无效。")
    provider_options.endpoint(base.strip(), {"protocol": protocol})
    if not isinstance(settings.get("models"), list) or len(settings["models"]) > 100:
        raise InvalidProfile("模型列表无效。")
    for model in settings["models"]:
        if (
            not isinstance(model, dict)
            or not isinstance(model.get("id"), str)
            or not 1 <= len(model["id"]) <= 200
        ):
            raise InvalidProfile("模型 ID 无效。")
        if model.get("smart") is True:
            continue
        options = model_options(model)
        if options:
            provider_model_config.validate(options, protocol)
    return settings, protocol, base
