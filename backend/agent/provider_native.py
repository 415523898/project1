"""Bounded JSON/SSE transport for Responses, Messages and GenerateContent."""

import copy
import json
import socket
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request

from agent import provider_protocols as protocols
from agent.provider_transport import ProviderError, activity, completed_message, connection_failure


def send(target, key, payload, on_token=None):
    from agent import provider

    protocol = target.options["protocol"]
    streaming = on_token is not None
    url, headers, body = protocols.encode(target, payload, key, streaming)
    upstream = None
    try:
        upstream = provider.open_stream(
            Request(
                url,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )
        )
        activity("connected")
        if "text/event-stream" in upstream.headers.get("Content-Type", ""):
            result, emitted = read_sse(upstream, protocol, on_token or (lambda _: None), key)
        else:
            result, emitted = provider.read_payload(upstream), ""
        if result.get("error"):
            raise provider._response_error(result, upstream.headers, key)
        normalized = protocols.normalize(protocol, result, payload["model"])
        message = normalized["choices"][0]["message"]
        answer, calls = message["content"], message["tool_calls"]
        raw_answer = answer
        if len(answer) > provider.MAX_REPLY_CHARS or len(calls or []) > 4:
            raise ValueError("模型回复或工具数量超过限制。")
        for call in calls or []:
            if len(call["function"]["arguments"]) > provider.tool_argument_limit():
                raise ValueError("工具参数过大。")
        provider.validate_completion(
            normalized["choices"][0]["finish_reason"], answer, calls, bool(payload.get("tools"))
        )
        answer = provider.normalize_answer(answer, calls, payload, target, key)
        if answer != raw_answer:
            message["content"] = answer
            message["_native"] = clean_native_text(message["_native"], answer)
        completed_message(answer, calls, None, native=message["_native"])
        if streaming:
            if not raw_answer.startswith(emitted):
                raise ProviderError("模型流与最终正文不一致，请重试。", code="invalid_stream")
            remainder = raw_answer[len(emitted) :]
            if remainder:
                activity("generating")
                on_token(remainder)
            return answer, calls, normalized["usage"], normalized["model"], True
        return normalized
    except HTTPError as error:
        raise provider._http_error(error, key) from error
    except (URLError, TimeoutError, socket.timeout, OSError, HTTPException) as error:
        raise connection_failure(error, key) from error
    finally:
        if upstream is not None:
            upstream.close()


def clean_native_text(native, answer):
    """Keep native tool/reasoning state while removing rejected text from continuation."""
    native = copy.deepcopy(native)
    replaced = False

    def clean(blocks, key, is_text):
        nonlocal replaced
        result = []
        for block in blocks:
            if is_text(block):
                if answer and not replaced:
                    block[key] = answer
                    result.append(block)
                    replaced = True
            else:
                result.append(block)
        return result

    if native["protocol"] == "responses":
        for item in native["items"]:
            if item.get("type") == "message":
                item["content"] = clean(
                    item.get("content", []), "text", lambda b: b.get("type") == "output_text"
                )
        native["items"] = [
            item for item in native["items"] if item.get("type") != "message" or item.get("content")
        ]
    elif native["protocol"] == "anthropic":
        native["items"] = clean(native["items"], "text", lambda b: b.get("type") == "text")
    else:
        native["items"] = clean(
            native["items"], "text", lambda b: "text" in b and not b.get("thought")
        )
    return native


def read_sse(upstream, protocol, on_token, key):
    from agent import provider

    emitted, lines, size = "", [], 0
    result, blocks, arguments = {}, {}, {}

    def token(fragment):
        nonlocal emitted
        if not fragment:
            return
        emitted += fragment
        if len(emitted) > provider.MAX_REPLY_CHARS:
            raise ValueError("模型回复过长，已停止。")
        activity("generating")
        on_token(fragment)

    while True:
        raw = upstream.readline(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("模型事件过大。")
        line = raw.decode("utf-8").rstrip("\r\n")
        if line.startswith("data:"):
            lines.append(line[5:].lstrip())
        if (line or not lines) and raw:
            continue
        if not lines:
            break
        data = "\n".join(lines)
        lines = []
        if data == "[DONE]":
            break
        size += len(data)
        if size > 8_000_000:
            raise ValueError("模型事件总量过大。")
        event = json.loads(data)
        kind = event.get("type", "")
        if kind == "error" or event.get("error"):
            raise provider._response_error(event, {}, key)
        if protocol == "responses":
            if kind == "response.output_text.delta" or kind == "response.refusal.delta":
                token(event.get("delta", ""))
            elif kind.startswith("response.reasoning"):
                activity("thinking")
            elif kind.startswith("response.function_call"):
                activity("tool_call")
            elif kind in ("response.completed", "response.incomplete"):
                return event["response"], emitted
            elif kind == "response.failed":
                raise provider._response_error(event.get("response", {}), {}, key)
        elif protocol == "anthropic":
            if kind == "message_start":
                result = event["message"]
            elif kind == "content_block_start":
                blocks[event["index"]] = event["content_block"]
                if event["content_block"]["type"] in ("thinking", "redacted_thinking"):
                    activity("thinking")
                if event["content_block"]["type"] == "text":
                    token(event["content_block"].get("text", ""))
            elif kind == "content_block_delta":
                index, delta = event["index"], event["delta"]
                block = blocks[index]
                if delta["type"] == "text_delta":
                    block["text"] = block.get("text", "") + delta["text"]
                    token(delta["text"])
                elif delta["type"] == "input_json_delta":
                    arguments[index] = arguments.get(index, "") + delta["partial_json"]
                    activity("tool_call")
                elif delta["type"] == "thinking_delta":
                    block["thinking"] = block.get("thinking", "") + delta["thinking"]
                    activity("thinking")
                elif delta["type"] == "signature_delta":
                    block["signature"] = block.get("signature", "") + delta["signature"]
            elif kind == "message_delta":
                result.update(event.get("delta", {}))
                result["usage"] = {**result.get("usage", {}), **event.get("usage", {})}
            elif kind == "message_stop":
                for index, value in arguments.items():
                    blocks[index]["input"] = json.loads(value)
                result["content"] = [blocks[i] for i in sorted(blocks)]
                return result, emitted
        else:
            candidate = (event.get("candidates") or [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            blocks.setdefault(0, []).extend(parts)
            for part in parts:
                if part.get("thought"):
                    activity("thinking")
                elif part.get("text"):
                    token(part["text"])
                elif part.get("functionCall"):
                    activity("tool_call")
            result.update(event)
            if candidate.get("finishReason"):
                candidate["content"] = {"parts": blocks[0]}
                result["candidates"] = [candidate]
                return result, emitted
        if not raw:
            break
    raise ProviderError("模型回答流提前中断。", code="stream_disconnected", retryable=True)
