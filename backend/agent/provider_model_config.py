"""Declarative per-model overrides: no expression evaluation or arbitrary request keys."""

import copy
import json
import re

LEVEL = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
FIELDS = {"max_output_tokens", "input_types", "efforts", "effort_mapping"}
INPUT_TYPES = {"text", "image", "audio", "document", "video"}
PATCH_FIELDS = {
    "chat": {"thinking", "reasoning_effort", "enable_thinking", "reasoning_split"},
    "responses": {"reasoning"},
    "anthropic": {"thinking", "output_config"},
    "gemini": {"generationConfig"},
}


def _object(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError("推理参数映射包含不支持的字段。")


def _level(value):
    return isinstance(value, str) and bool(LEVEL.fullmatch(value))


def patch(value, protocol):
    _object(value, PATCH_FIELDS[protocol])
    for key, item in value.items():
        if key in ("enable_thinking", "reasoning_split"):
            if type(item) is not bool:
                raise ValueError("思考开关必须为布尔值。")
        elif key == "reasoning_effort":
            if not _level(item):
                raise ValueError("推理参数取值无效。")
        elif key in ("reasoning", "output_config"):
            _object(item, {"effort"})
            if not _level(item.get("effort")):
                raise ValueError("推理强度参数无效。")
        elif key == "thinking":
            _object(item, {"type", "budget_tokens"})
            if item.get("type") not in ("enabled", "disabled", "adaptive"):
                raise ValueError("思考模式无效。")
            if "budget_tokens" in item and (
                type(item["budget_tokens"]) is not int or not 1 <= item["budget_tokens"] <= 1048576
            ):
                raise ValueError("思考预算无效。")
        else:
            _object(item, {"thinkingConfig"})
            config = item.get("thinkingConfig")
            _object(config, {"thinkingLevel", "thinkingBudget"})
            if "thinkingLevel" in config and not _level(config["thinkingLevel"]):
                raise ValueError("Gemini 思考等级无效。")
            if "thinkingBudget" in config and (
                type(config["thinkingBudget"]) is not int
                or not -1 <= config["thinkingBudget"] <= 1048576
            ):
                raise ValueError("Gemini 思考预算无效。")
            if "thinkingLevel" in config and "thinkingBudget" in config:
                raise ValueError("Gemini 不能同时配置思考等级和预算。")
    return copy.deepcopy(value)


def validate(value, protocol):
    if value is None:
        return None
    _object(value, FIELDS)
    limit = value.get("max_output_tokens")
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 1048576):
        raise ValueError("最大输出 Token 需为 1–1048576 的整数。")
    modalities = value.get("input_types", ["text", "image"])
    if (
        not isinstance(modalities, list)
        or not 1 <= len(modalities) <= len(INPUT_TYPES)
        or "text" not in modalities
        or any(not isinstance(item, str) or item not in INPUT_TYPES for item in modalities)
        or len(set(modalities)) != len(modalities)
    ):
        raise ValueError("模型输入类型无效。")
    levels = value.get("efforts", [])
    if (
        not isinstance(levels, list)
        or len(levels) > 12
        or any(not _level(item) or item == "auto" for item in levels)
        or len(set(levels)) != len(levels)
    ):
        raise ValueError("模型推理等级无效。")
    mapping = value.get("effort_mapping", {})
    if (
        not isinstance(mapping, dict)
        or len(json.dumps(mapping)) > 12000
        or set(mapping) - set(levels)
    ):
        raise ValueError("推理参数映射只能使用已声明的等级。")
    return {
        "input_types": list(modalities),
        "efforts": levels,
        "effort_mapping": {level: patch(raw, protocol) for level, raw in mapping.items()},
        **({"max_output_tokens": limit} if limit is not None else {}),
    }


def finalize(target, payload):
    options = getattr(target, "options", {})
    model = options.get("model_options") or {}
    result = copy.deepcopy(payload)
    for key, value in options.get("manual_mapping", {}).items():
        result[key] = {**result.get(key, {}), **value} if isinstance(value, dict) else value
    limit = model.get("max_output_tokens")
    if limit:
        protocol = options.get("protocol", "chat")
        if protocol == "gemini":
            result.setdefault("generationConfig", {})["maxOutputTokens"] = limit
        else:
            field = {"responses": "max_output_tokens", "anthropic": "max_tokens"}.get(
                protocol,
                "max_completion_tokens" if "max_completion_tokens" in result else "max_tokens",
            )
            result[field] = limit
    return result
