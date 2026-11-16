import json
import socket
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from agent import provider_native, provider_options
from agent.provider_transport import (
    ProviderError,
    activity,
    captures_message,
    completed_message,
    connection_failure,
    diagnostic,
    http_failure,
    recover,
    tool_argument_limit,
)
from agent.provider_transport import (
    request_scope as request_scope,  # Public request-local transport context.
)
from config import (
    PROVIDER_MAX_REPLY_CHARS as MAX_REPLY_CHARS,
)
from config import (
    PROVIDER_MAX_STREAM_LINE as MAX_STREAM_LINE,
)
from config import PROVIDER_REQUEST_TIMEOUT_SECONDS, environment


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def endpoint(base_url, settings=None):
    return provider_options.endpoint(base_url, settings)


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    return ""


def merge_tool_chunks(chunks, fragment, routing=None):
    """Separate calls by ID, including providers that restart wire indices.

    routing belongs to one response. Index-only continuations follow the most
    recent ID associated with that wire index; standard interleaved indices work
    unchanged. Nothing in this assembler repairs or executes argument text.
    """
    if not isinstance(fragment, dict):
        raise ValueError("模型工具分片无效。")
    wire_index = fragment.get("index")
    if wire_index is not None and (type(wire_index) is not int or not 0 <= wire_index < 4):
        raise ValueError("模型工具调用数量无效。")
    routing = routing if routing is not None else {}
    aliases = routing.setdefault("indices", {})
    identifier = fragment.get("id")
    if identifier is not None and (not isinstance(identifier, str) or len(identifier) > 200):
        raise ValueError("模型工具调用ID无效。")
    index = (
        aliases.get(wire_index, wire_index) if wire_index is not None else routing.get("active", 0)
    )
    if identifier:
        known = next((key for key, call in chunks.items() if call["id"] == identifier), None)
        if known is not None:
            index = known
        elif index in chunks and chunks[index]["id"] not in ("", identifier):
            index = next((key for key in range(4) if key not in chunks), None)
            routing["reassigned"] = routing.get("reassigned", 0) + 1
    if index is None or not 0 <= index < 4:
        raise ValueError("模型工具调用数量无效。")
    if wire_index is not None:
        aliases[wire_index] = index
    routing["active"] = index
    call = chunks.setdefault(
        index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
    )
    if identifier:
        call["id"] = identifier
    function = fragment.get("function") or {}
    if not isinstance(function, dict):
        raise ValueError("模型工具分片函数无效。")
    for field in ("name", "arguments"):
        piece = function.get(field) or ""
        if not isinstance(piece, str):
            raise ValueError("模型工具分片字段无效。")
        call["function"][field] += piece
        if len(call["function"][field]) > (tool_argument_limit() if field == "arguments" else 4096):
            raise ValueError("工具参数过大。")


def read_payload(upstream):
    raw = upstream.read(2000001)
    if len(raw) > 2000000:
        raise ValueError("模型回复过大。")
    return json.loads(raw)


def merge_reasoning_details(blocks, fragments):
    if not isinstance(fragments, list):
        raise ProviderError("模型推理上下文格式无效，未执行本步工具。", code="reasoning_format")
    for position, fragment in enumerate(fragments):
        if not isinstance(fragment, dict):
            raise ProviderError("模型推理上下文格式无效，未执行本步工具。", code="reasoning_format")
        # Type distinguishes text from signed blocks that share the same wire index.
        identity = (fragment.get("type"), fragment.get("index", position))
        block = blocks.setdefault(identity, {})
        for key, value in fragment.items():
            if key in ("text", "summary", "data") and isinstance(value, str):
                block[key] = block.get(key, "") + value
            elif key not in block or block[key] == value:
                block[key] = value
            else:
                raise ProviderError(
                    "模型推理上下文标识冲突，未执行本步工具。", code="reasoning_format"
                )
    if (
        sum(len(json.dumps(block, ensure_ascii=False)) for block in blocks.values())
        > MAX_REPLY_CHARS
    ):
        raise ProviderError("模型本步推理上下文过长，未执行本步工具。", code="reasoning_limit")


def open_stream(request):

    for name in ("Authorization", "X-api-key", "X-goog-api-key"):
        value = request.get_header(name)
        if value is not None:
            raw_key = value.removeprefix("Bearer ") if name == "Authorization" else value
            try:
                provider_options.api_key(raw_key)
            except ValueError as error:
                raise ProviderError(str(error), status=400, code="invalid_api_key") from None
    if environment("FOREST_ENV") == "production":
        from agent.security import public_endpoint

        public_endpoint(request.full_url)
    return build_opener(*_handlers(request.full_url)).open(
        request, timeout=PROVIDER_REQUEST_TIMEOUT_SECONDS
    )


def _handlers(target):
    handlers = [NoRedirect()]
    if urlsplit(target).hostname in ("127.0.0.1", "localhost", "::1"):
        handlers.append(ProxyHandler({}))
    return handlers


def call(target, key, payload):
    def once():
        result = _call_once(target, key, payload)
        parsed = parse_message(result)
        from agent.tool_markup import reconcile_direction_calls

        parsed["answer"], parsed["calls"] = reconcile_direction_calls(
            parsed["answer"], parsed["calls"], payload
        )
        answer = normalize_answer(parsed["answer"], parsed["calls"], payload, target, key)
        if result.get("choices") and isinstance(result["choices"][0].get("message"), dict):
            result["choices"][0]["message"].update(content=answer, tool_calls=parsed["calls"])
        return result

    return recover(once, target, payload, key)


def _call_once(target, key, payload):
    if getattr(target, "options", {}).get("protocol", "chat") != "chat":
        return provider_native.send(target, key, payload)
    payload = provider_options.prepare_chat(target, payload)
    request = Request(
        target,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    upstream = None
    try:
        upstream = open_stream(request)
        result = read_payload(upstream)
        if isinstance(result, dict) and result.get("error"):
            raise _response_error(result, upstream.headers, key)
        return result
    except HTTPError as error:
        raise _http_error(error, key) from error
    except (URLError, TimeoutError, socket.timeout, OSError, HTTPException) as error:
        raise connection_failure(error, key) from error
    finally:
        if upstream is not None:
            upstream.close()


def _http_error(error, key=""):
    body = ""
    try:
        raw = error.read(64000).decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except ValueError:
            body = raw
    except (OSError, HTTPException):
        pass
    finally:
        error.close()
    return http_failure(error.code, body, error.headers, key)


def parse_message(result):
    choices = result.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    answer = text_content(message.get("content")) or text_content(message.get("refusal"))
    calls = message.get("tool_calls")
    return {
        "answer": answer,
        "reasoning_only": not answer
        and bool(
            message.get("reasoning_content")
            or choices
            and choices[0].get("finish_reason") == "length"
        ),
        "calls": calls if isinstance(calls, list) and calls else None,
        "usage": result.get("usage"),
        "model": result.get("model"),
    }


def _response_error(body, headers, key):
    info = body.get("error")
    info = info if isinstance(info, dict) else {}
    status = info.get("status") or info.get("status_code")
    code = str(info.get("code") or info.get("type") or "")
    if status is None:
        status = {
            "invalid_api_key": 401,
            "authentication_failed": 401,
            "invalid_request_error": 400,
            "rate_limit_exceeded": 429,
            "too_many_requests": 429,
            "insufficient_quota": 429,
        }.get(code, code if code.isdigit() else 502)
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = 502
    return http_failure(status, body, headers, key)


def stream(target, key, payload, on_token):
    emitted = False
    from agent.tool_markup import ToolMarkupFilter

    def once():
        nonlocal emitted
        markup = ToolMarkupFilter()
        visible_parts = []

        def token(text):
            nonlocal emitted
            visible = markup.feed(text) if markup else text
            if visible:
                emitted = True
                visible_parts.append(visible)
                on_token(visible)

        result = _stream_once(target, key, payload, token)
        if markup:
            tail = markup.finish()
            if tail:
                emitted = True
                visible_parts.append(tail)
                on_token(tail)
            from agent.tool_markup import native_calls_match

            if markup.found and not native_calls_match(result[1], payload):
                raise ProviderError(
                    "模型把工具调用写成了正文标签，未执行该调用；请重试本轮。", code="tool_format"
                )
        visible = "".join(visible_parts)
        accepted = result[0] or ""
        if accepted.startswith(visible) and accepted[len(visible) :]:
            emitted = True
            on_token(accepted[len(visible) :])
        return result

    return recover(once, target, payload, key, progress=lambda: emitted)


def normalize_answer(answer, calls, payload, target, key):
    from agent.tool_markup import normalize_tool_reply

    visible = normalize_tool_reply(answer, calls, payload)
    if visible != answer:
        diagnostic(
            "duplicate_tool_body_discarded",
            target,
            payload,
            key,
            tool_count=len(calls or []),
            discarded_chars=len(answer) - len(visible),
        )
    return visible


def validate_completion(finish_reason, answer, calls, has_tools=False):
    if finish_reason == "length" and (has_tools or not answer):
        raise ProviderError("模型输出达到本步上限，思考或工具参数未完成。", code="output_limit")
    if finish_reason in {"insufficient_system_resource", "aborted"}:
        raise ProviderError(
            "服务商中断了本步生成，正在尝试恢复。", code="generation_aborted", retryable=True
        )
    if finish_reason == "content_filter":
        raise ProviderError("服务商未提供本步结果（content_filter）。", code="content_filter")
    if not answer and not calls:
        raise ProviderError(
            "模型本步返回空内容且没有工具调用。", code="empty_response", retryable=True
        )


def _stream_once(target, key, payload, on_token):
    if getattr(target, "options", {}).get("protocol", "chat") != "chat":
        return provider_native.send(target, key, payload, on_token)
    payload = provider_options.prepare_chat(target, payload)
    request = Request(
        target,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    answer, reasoning, tool_chunks, usage, actual_model = "", "", {}, None, payload["model"]
    tool_routing, reasoning_details = {}, {}
    event_lines, finished, reply_length = [], False, 0
    summary = {
        "events": 0,
        "reasoning_chars": 0,
        "message_frames": 0,
        "tool_fragments": 0,
        "finish_reason": None,
        "stream": False,
        "tool_count": 0,
    }
    upstream = None
    try:
        upstream = open_stream(request)
        content_type = upstream.headers.get("Content-Type", "")
        summary["stream"] = "text/event-stream" in content_type
        activity("connected")
        if "text/event-stream" not in content_type:
            result = read_payload(upstream)
            if isinstance(result, dict) and result.get("error"):
                raise _response_error(result, upstream.headers, key)
            parsed = parse_message(result)
            from agent.tool_markup import reconcile_direction_calls

            parsed["answer"], parsed["calls"] = reconcile_direction_calls(
                parsed["answer"], parsed["calls"], payload
            )
            message = (result.get("choices") or [{}])[0].get("message") or {}
            if captures_message() and message.get("reasoning_details"):
                merge_reasoning_details(reasoning_details, message["reasoning_details"])
            finish_reason = (result.get("choices") or [{}])[0].get("finish_reason")
            usage, reply_length, finished = parsed["usage"], len(parsed["answer"]), True
            summary.update(
                finish_reason=finish_reason,
                tool_count=len(parsed["calls"] or []),
                message_frames=1,
                reasoning_chars=len(
                    text_content(message.get("reasoning_content"))
                    or text_content(message.get("reasoning"))
                ),
            )
            validate_completion(
                finish_reason, parsed["answer"], parsed["calls"], bool(payload.get("tools"))
            )
            parsed["answer"] = normalize_answer(
                parsed["answer"], parsed["calls"], payload, target, key
            )
            completed_message(
                parsed["answer"],
                parsed["calls"],
                message.get("reasoning_content") or message.get("reasoning"),
                reasoning_details=list(reasoning_details.values()),
            )
            if parsed["answer"]:
                activity("generating")
                on_token(parsed["answer"])
            return (
                parsed["answer"],
                parsed["calls"],
                parsed["usage"],
                parsed["model"] or payload["model"],
                True,
            )
        while True:
            line = upstream.readline(MAX_STREAM_LINE + 1)
            if len(line) > MAX_STREAM_LINE:
                raise ValueError("模型事件过大。")
            if not line:
                if not event_lines:
                    break
                line = b"\n"
            clean = line.decode("utf-8").rstrip("\r\n")
            if clean.startswith("data:"):
                event_lines.append(clean[5:].lstrip())
            if clean or not event_lines:
                if not line:
                    break
                continue
            event = "\n".join(event_lines)
            event_lines = []
            if event == "[DONE]":
                finished = True
                break
            chunk = json.loads(event)
            summary["events"] += 1
            if chunk.get("error"):
                raise _response_error(chunk, upstream.headers, key)
            actual_model = chunk.get("model", actual_model)
            usage = chunk.get("usage") or usage
            choices = chunk.get("choices", [])
            if not choices:
                continue
            choice = choices[0]
            if choice.get("message"):
                summary["message_frames"] += 1
            delta = choice.get("delta") or choice.get("message") or {}
            fragment_reasoning = text_content(delta.get("reasoning_content")) or text_content(
                delta.get("reasoning")
            )
            summary["reasoning_chars"] += len(fragment_reasoning)
            if captures_message():
                reasoning += fragment_reasoning
                if delta.get("reasoning_details"):
                    merge_reasoning_details(reasoning_details, delta["reasoning_details"])
                if len(reasoning) > MAX_REPLY_CHARS:
                    raise ProviderError(
                        "模型本步思考上下文过长，未执行本步工具。", code="reasoning_limit"
                    )
            summary["tool_fragments"] += len(delta.get("tool_calls") or [])
            summary["finish_reason"] = choice.get("finish_reason") or summary["finish_reason"]
            if (
                delta.get("reasoning_content")
                or delta.get("reasoning")
                or delta.get("reasoning_details")
            ):
                activity("thinking")
            for fragment in delta.get("tool_calls") or []:
                activity("tool_call")
                merge_tool_chunks(tool_chunks, fragment, tool_routing)
                summary["tool_count"] = len(tool_chunks)
            text = text_content(delta.get("content")) or text_content(delta.get("refusal"))
            if text:
                activity("generating")
                reply_length += len(text)
                if reply_length > MAX_REPLY_CHARS:
                    raise ValueError("模型回复过长，已停止。")
                answer += text
                on_token(text)
            if choice.get("finish_reason"):
                finished = True
                # A terminal model event completes the answer. Optional usage or
                # transport EOF must not keep a completed chat busy for minutes.
                break
        if not finished:
            raise ProviderError("模型回答流提前中断。", code="stream_disconnected", retryable=True)
        calls = [tool_chunks[index] for index in sorted(tool_chunks)] or None
        from agent.tool_markup import reconcile_direction_calls

        answer, calls = reconcile_direction_calls(answer, calls, payload)
        validate_completion(summary["finish_reason"], answer, calls, bool(payload.get("tools")))
        answer = normalize_answer(answer, calls, payload, target, key)
        completed_message(
            answer, calls, reasoning, reasoning_details=list(reasoning_details.values())
        )
        return answer, calls, usage, actual_model, True
    except HTTPError as error:
        raise _http_error(error, key) from error
    except (URLError, TimeoutError, socket.timeout, OSError, HTTPException) as error:
        raise connection_failure(error, key) from error
    finally:
        if upstream is not None:
            upstream.close()
            # Structure and numeric counters only: never persist content, arguments,
            # private reasoning, Authorization or provider credentials.
            diagnostic(
                "stream_summary",
                target,
                payload,
                key,
                **summary,
                text_chars=reply_length,
                tool_index_reassignments=tool_routing.get("reassigned", 0),
                finished=finished,
                max_tokens=payload.get("max_tokens", payload.get("max_completion_tokens")),
                completion_tokens=usage.get("completion_tokens")
                if isinstance(usage, dict)
                else None,
            )
