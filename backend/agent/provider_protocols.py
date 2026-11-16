"""Translate the Harness conversation to native inference protocols, without UI text changes."""

import copy
import json
import uuid
from urllib.parse import quote

from agent.provider_model_config import finalize


def text(value):
    if isinstance(value, str):
        return value
    return "".join(
        p.get("text", "")
        for p in (value or [])
        if isinstance(p, dict) and isinstance(p.get("text"), str)
    )


def parts(content, protocol):
    if isinstance(content, str) or content is None:
        return (
            [{"type": "text", "text": content or ""}]
            if protocol == "anthropic"
            else [{"text": content or ""}]
        )
    result = []
    for part in content:
        if part.get("type") == "text":
            result.append(
                {"type": "text", "text": part["text"]}
                if protocol == "anthropic"
                else {"text": part["text"]}
            )
        elif part.get("type") == "image_url":
            url = part["image_url"]["url"]
            if url.startswith("data:"):
                mime, data = url[5:].split(";base64,", 1)
                result.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": data},
                    }
                    if protocol == "anthropic"
                    else {"inlineData": {"mimeType": mime, "data": data}}
                )
            elif protocol == "anthropic":
                result.append({"type": "image", "source": {"type": "url", "url": url}})
            else:
                result.append({"fileData": {"mimeType": "image/jpeg", "fileUri": url}})
    return result


def encode(target, payload, key, streaming):
    options = target.options
    protocol, family, effort = options["protocol"], options["family"], options["effort"]
    messages = payload.get("messages", [])
    limit = payload.get("max_completion_tokens", payload.get("max_tokens", 16384))
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if streaming else "application/json",
    }
    url = str(target)
    tools = [tool["function"] for tool in payload.get("tools", [])]
    if protocol == "responses":
        headers["Authorization"] = "Bearer " + key
        items = []
        for m in messages:
            if m.get("_native", {}).get("protocol") == protocol:
                items.extend(copy.deepcopy(m["_native"]["items"]))
                continue
            if m["role"] == "tool":
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": m["tool_call_id"],
                        "output": text(m.get("content")),
                    }
                )
                continue
            content = m.get("content")
            if content:
                if isinstance(content, list):
                    content = [
                        {"type": "input_image", "image_url": p["image_url"]["url"]}
                        if p["type"] == "image_url"
                        else {"type": "input_text", "text": p.get("text", "")}
                        for p in content
                    ]
                items.append({"role": m["role"], "content": content})
            for call in m.get("tool_calls", []):
                items.append({"type": "function_call", "call_id": call["id"], **call["function"]})
        body = {
            "model": payload["model"],
            "input": items,
            "stream": streaming,
            "store": False,
            "max_output_tokens": max(limit, 4096),
        }
        if family in ("openai", "grok", "muse"):
            body["include"] = ["reasoning.encrypted_content"]
        if effort != "auto":
            body["reasoning"] = {"effort": "none" if effort == "off" else effort}
        if tools:
            body["tools"] = [{"type": "function", **tool, "strict": False} for tool in tools]
            body["tool_choice"] = payload.get("tool_choice", "auto")
    elif protocol == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        body = {
            "model": payload["model"],
            "system": "\n".join(text(m.get("content")) for m in messages if m["role"] == "system"),
            "messages": [],
            "max_tokens": max(limit, 4096),
            "stream": streaming,
        }
        for m in messages:
            if m["role"] == "system":
                continue
            role = "assistant" if m["role"] == "assistant" else "user"
            if m.get("_native", {}).get("protocol") == protocol:
                blocks = copy.deepcopy(m["_native"]["items"])
            elif m["role"] == "tool":
                blocks = [
                    {
                        "type": "tool_result",
                        "tool_use_id": m["tool_call_id"],
                        "content": text(m.get("content")),
                    }
                ]
            else:
                blocks = parts(m.get("content"), protocol) if m.get("content") else []
                blocks += [
                    {
                        "type": "tool_use",
                        "id": c["id"],
                        "name": c["function"]["name"],
                        "input": json.loads(c["function"]["arguments"]),
                    }
                    for c in m.get("tool_calls", [])
                ]
            if not blocks:
                continue
            if body["messages"] and body["messages"][-1]["role"] == role:
                body["messages"][-1]["content"].extend(blocks)
            else:
                body["messages"].append({"role": role, "content": blocks})
        if effort != "auto":
            body["thinking"] = (
                {"type": "disabled" if effort == "off" else "adaptive"}
                if family in ("claude", "custom")
                else (
                    {"type": "disabled"}
                    if effort == "off"
                    else {"type": "enabled", "budget_tokens": 1024}
                )
            )
            if effort not in ("off", "enabled"):
                body["output_config"] = {"effort": effort}
        if tools:
            body["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t["parameters"],
                }
                for t in tools
            ]
            body["tool_choice"] = {
                "type": "none" if payload.get("tool_choice") == "none" else "auto"
            }
    elif protocol == "gemini":
        headers["x-goog-api-key"] = key
        model = quote(payload["model"].removeprefix("models/"), safe="-._")
        url = (
            url.rstrip("/")
            + "/models/"
            + model
            + (":streamGenerateContent?alt=sse" if streaming else ":generateContent")
        )
        body = {"contents": [], "generationConfig": {"maxOutputTokens": max(limit, 4096)}}
        system = "\n".join(text(m.get("content")) for m in messages if m["role"] == "system")
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        names = {c["id"]: c["function"]["name"] for m in messages for c in m.get("tool_calls", [])}
        native_ids = {
            p["functionCall"]["id"]
            for m in messages
            for p in m.get("_native", {}).get("items", [])
            if isinstance(p, dict) and p.get("functionCall", {}).get("id")
        }
        for m in messages:
            if m["role"] == "system":
                continue
            role = "model" if m["role"] == "assistant" else "user"
            if m.get("_native", {}).get("protocol") == protocol:
                blocks = copy.deepcopy(m["_native"]["items"])
            elif m["role"] == "tool":
                try:
                    result = json.loads(m.get("content", "{}"))
                except ValueError:
                    result = {"output": text(m.get("content"))}
                response = {
                    "name": names[m["tool_call_id"]],
                    "response": result if isinstance(result, dict) else {"output": result},
                }
                if m["tool_call_id"] in native_ids:
                    response["id"] = m["tool_call_id"]
                blocks = [{"functionResponse": response}]
            else:
                blocks = parts(m.get("content"), protocol) if m.get("content") else []
                blocks += [
                    {
                        "functionCall": {
                            "name": c["function"]["name"],
                            "args": json.loads(c["function"]["arguments"]),
                        }
                    }
                    for c in m.get("tool_calls", [])
                ]
            if body["contents"] and body["contents"][-1]["role"] == role:
                body["contents"][-1]["parts"].extend(blocks)
            else:
                body["contents"].append({"role": role, "parts": blocks})
        if effort != "auto":
            thinking = (
                {"thinkingBudget": 0 if effort == "off" else -1}
                if options["capability"].get("budget")
                else {"thinkingLevel": effort}
            )
            body["generationConfig"]["thinkingConfig"] = thinking
        if tools:
            # Gemini accepts JSON schema on parametersJsonSchema, including nullable unions.
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parametersJsonSchema": t["parameters"],
                        }
                        for t in tools
                    ]
                }
            ]
            body["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": "NONE" if payload.get("tool_choice") == "none" else "AUTO"
                }
            }
    else:
        raise ValueError("未支持的模型协议。")
    return url, headers, finalize(target, body)


def normalize(protocol, result, model):
    calls, answer, native, reason = [], "", [], None
    usage = result.get("usage") or {}
    if protocol == "responses":
        native = result.get("output", [])
        for item in native:
            if item.get("type") == "message":
                answer += "".join(
                    p.get("text", p.get("refusal", "")) for p in item.get("content", [])
                )
            elif item.get("type") == "function_call":
                calls.append(
                    {
                        "id": item["call_id"],
                        "type": "function",
                        "function": {"name": item["name"], "arguments": item["arguments"]},
                    }
                )
        reason = "length" if result.get("status") == "incomplete" else None
    elif protocol == "anthropic":
        native = result.get("content", [])
        for item in native:
            if item.get("type") == "text":
                answer += item["text"]
            elif item.get("type") == "tool_use":
                calls.append(
                    {
                        "id": item["id"],
                        "type": "function",
                        "function": {
                            "name": item["name"],
                            "arguments": json.dumps(item.get("input", {}), ensure_ascii=False),
                        },
                    }
                )
        reason = "length" if result.get("stop_reason") == "max_tokens" else None
    else:
        candidate = (result.get("candidates") or [{}])[0]
        native = candidate.get("content", {}).get("parts", [])
        usage = result.get("usageMetadata", {})
        for index, item in enumerate(native):
            if item.get("text") and not item.get("thought"):
                answer += item["text"]
            if item.get("functionCall"):
                call = item["functionCall"]
                calls.append(
                    {
                        "id": call.get("id") or "gemini_" + uuid.uuid4().hex,
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(call.get("args", {}), ensure_ascii=False),
                        },
                    }
                )
        reason = "length" if candidate.get("finishReason") == "MAX_TOKENS" else None
        if candidate.get("finishReason") in (
            "SAFETY",
            "RECITATION",
            "PROHIBITED_CONTENT",
        ) or result.get("promptFeedback", {}).get("blockReason"):
            reason = "content_filter"
    if "input_tokens" in usage:
        usage = {
            **usage,
            "prompt_tokens": usage["input_tokens"],
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage["input_tokens"] + usage.get("output_tokens", 0),
        }
    elif "promptTokenCount" in usage:
        usage = {
            "prompt_tokens": usage["promptTokenCount"],
            "completion_tokens": usage.get("candidatesTokenCount", 0)
            + usage.get("thoughtsTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        }
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": answer,
                    "tool_calls": calls or None,
                    "_native": {"protocol": protocol, "items": native},
                },
                "finish_reason": reason,
            }
        ],
        "usage": usage,
        "model": result.get("model", result.get("modelVersion", model)),
    }
