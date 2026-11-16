"""Bounded recovery and credential-free diagnostics for provider requests."""

import contextlib
import contextvars
import json
import logging
import math
import re
import socket
import ssl
import threading
import time
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from logging.handlers import RotatingFileHandler
from urllib.error import URLError
from urllib.parse import urlsplit

from config import LOCAL_LOG_DIRECTORY
from config import (
    PROVIDER_TRANSPORT_MAX_ATTEMPTS as MAX_ATTEMPTS,
)
from config import (
    PROVIDER_TRANSPORT_MAX_RETRY_DELAY as MAX_RETRY_DELAY,
)
from config import (
    PROVIDER_TRANSPORT_RETRY_WINDOW as RETRY_WINDOW,
)

_scope = contextvars.ContextVar("provider_request_scope", default={})
LOGGER = logging.getLogger("forest.provider")
_log_lock = threading.Lock()


class ProviderError(Exception):
    def __init__(
        self,
        message,
        status=502,
        *,
        code="provider_error",
        retryable=False,
        retry_after=None,
        request_id=None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after
        self.request_id = request_id
        self.attempts = 1


@contextlib.contextmanager
def request_scope(
    *,
    cancelled=None,
    check_cancelled=None,
    on_retry=None,
    on_activity=None,
    on_message=None,
    on_tool_text_recovered=None,
    tool_argument_limit=4096,
    **trace,
):
    token = _scope.set(
        {
            "cancelled": cancelled,
            "check_cancelled": check_cancelled,
            "on_retry": on_retry,
            "on_activity": on_activity,
            "on_message": on_message,
            "on_tool_text_recovered": on_tool_text_recovered,
            "tool_argument_limit": tool_argument_limit,
            "trace": trace,
        }
    )
    try:
        yield
    finally:
        _scope.reset(token)


def activity(phase):
    """Expose activity labels only, never the model's private reasoning text."""
    scope = _scope.get()
    check = scope.get("check_cancelled")
    if check:
        check()
    callback = scope.get("on_activity")
    if callback:
        callback(phase)


def tool_argument_limit():
    return min(100000, max(4096, _scope.get().get("tool_argument_limit", 4096)))


def captures_message():
    return _scope.get().get("on_message") is not None


def tool_text_recovered():
    callback = _scope.get().get("on_tool_text_recovered")
    if callback:
        callback()


def completed_message(answer, calls, reasoning, native=None, reasoning_details=None):
    """Ephemeral protocol continuation; never log or emit private reasoning as UI text."""
    callback = _scope.get().get("on_message")
    if callback:
        message = {"role": "assistant", "content": answer or None}
        if calls:
            message["tool_calls"] = calls
        if reasoning:
            message["reasoning_content"] = reasoning
        if reasoning_details:
            message["reasoning_details"] = reasoning_details
        if native:
            message["_native"] = native
        callback(message)


def safe_text(value, key="", limit=600):
    text = str(value or "")
    if key:
        text = text.replace(key, "[已隐藏]")
    text = re.sub(r"(?i)Bearer\s+[^\s\"'<>]+", "Bearer [已隐藏]", text)
    return " ".join(text.split())[:limit]


def retry_after(value):
    if not value:
        return None
    try:
        delay = float(value)
    except (ValueError, TypeError):
        try:
            delay = parsedate_to_datetime(value).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0, delay) if math.isfinite(delay) else None


def http_failure(status, body, headers=None, key=""):
    info = body.get("error", body) if isinstance(body, dict) else body
    if isinstance(info, dict):
        detail = safe_text(info.get("message") or info.get("detail"), key)
        code = safe_text(info.get("code") or info.get("type") or f"http_{status}", key, 100)
    else:
        detail, code = safe_text(info, key), f"http_{status}"
    explicit_quota = any(
        word in (code + " " + detail).lower()
        for word in (
            "insufficient_quota",
            "quota_exhausted",
            "insufficient_balance",
            "balance_not_enough",
            "余额不足",
            "额度已用尽",
            "额度不足",
            "not enough balance",
            "exhausted your quota",
        )
    )
    messages = {
        400: "服务商拒绝了请求格式。",
        401: "API Key 无效或已过期。",
        402: "服务商报告余额或额度不足。",
        403: "接口拒绝访问，请检查权限。",
        404: "接口路径或模型不存在。",
        408: "服务商处理请求超时。",
        429: "服务商暂时限制了请求频率或并发，请稍后重试。",
    }
    message = (
        "服务商明确报告余额或额度不足。"
        if explicit_quota
        else messages.get(status, f"服务商返回 HTTP {status}。")
    )
    message += f"（HTTP {status} · {code}）"
    if detail:
        message += " " + detail
    if status == 400 and "tool_choice" in detail.lower():
        message += "（请确认模型支持工具调用，且模型名与接口匹配。）"
    headers = headers or {}
    request_id = (
        safe_text(
            headers.get("x-request-id") or headers.get("X-Request-Id") or headers.get("request-id"),
            key,
            100,
        )
        or None
    )
    delay = retry_after(headers.get("Retry-After") or headers.get("retry-after"))
    if delay is not None and delay > MAX_RETRY_DELAY:
        message += f" 服务商要求至少等待 {math.ceil(delay)} 秒。"
    if request_id:
        message += f" 请求编号：{request_id}。"
    return ProviderError(
        message,
        status if 400 <= status <= 599 else 502,
        code=code,
        retryable=not explicit_quota and (status in (408, 429) or 500 <= status <= 599),
        retry_after=delay,
        request_id=request_id,
    )


def connection_failure(error, key=""):
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, PermissionError) or getattr(reason, "winerror", None) == 10013:
        code, retryable = "network_permission", False
        message = "系统拒绝后端进程访问网络。请从正常终端重新启动后端；若仍失败，检查该 Python 进程的网络访问限制。"
        if getattr(reason, "winerror", None) == 10013:
            message += "（WinError 10013）"
    elif isinstance(reason, ssl.SSLCertVerificationError):
        code, message, retryable = "tls_certificate", "接口 TLS 证书验证失败。", False
    elif isinstance(reason, (TimeoutError, socket.timeout)):
        code, message, retryable = "timeout", "模型接口连接或读取超时。", True
    elif isinstance(reason, socket.gaierror):
        code, message, retryable = (
            "dns_error",
            "模型接口域名解析失败。",
            reason.errno == socket.EAI_AGAIN,
        )
    elif isinstance(reason, (ConnectionResetError, ConnectionAbortedError)):
        code, message, retryable = "connection_reset", "与模型接口的连接被中断。", True
    elif isinstance(reason, ConnectionRefusedError):
        code, message, retryable = "connection_refused", "模型接口连接被拒绝。", True
    elif isinstance(reason, ssl.SSLError):
        code, message, retryable = (
            "tls_connection",
            "模型接口 TLS 连接中断。",
            isinstance(reason, ssl.SSLEOFError) or "EOF" in str(reason).upper(),
        )
        if isinstance(error, URLError):
            message = "建立模型接口的 TLS 连接失败，尚未校验 API Key。请检查后端网络或代理链路。"
    elif isinstance(reason, HTTPException):
        code, message, retryable = "stream_disconnected", "模型接口响应流中断。", True
    else:
        code, message, retryable = "connection_error", "模型接口连接失败。", True
    detail = safe_text(f"{type(reason).__name__}: {reason}", key, 250)
    return ProviderError(
        f"{message}（{code}）{detail}",
        504 if code == "timeout" else 502,
        code=code,
        retryable=retryable,
    )


def _initialize_logger():
    with _log_lock:
        if LOGGER.handlers:
            return True
        try:
            directory = LOCAL_LOG_DIRECTORY
            directory.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                directory / "provider-requests.log",
                maxBytes=2_000_000,
                backupCount=2,
                encoding="utf-8",
                delay=True,
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            LOGGER.addHandler(handler)
            LOGGER.setLevel(logging.INFO)
            LOGGER.propagate = False
        except OSError:
            return False
    return True


def diagnostic(event, target, payload, key="", **fields):
    # Never record Authorization, API keys, prompts, dataset values or response bodies.
    if not _initialize_logger():
        return
    record = {
        "event": event,
        "host": urlsplit(target).hostname,
        "model": safe_text(payload.get("model"), key, 200),
        "message_count": len(payload.get("messages") or []),
        "request_bytes": len(json.dumps(payload, ensure_ascii=False).encode()),
        **_scope.get().get("trace", {}),
        **fields,
    }
    LOGGER.info(json.dumps(record, ensure_ascii=False, default=str))


def recover(operation, target, payload, key, progress=None):
    started = time.monotonic()
    scope = _scope.get()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        check = scope.get("check_cancelled")
        if check:
            check()
        try:
            value = operation()
            diagnostic(
                "success",
                target,
                payload,
                key,
                attempt=attempt,
                elapsed_ms=round((time.monotonic() - started) * 1000),
            )
            return value
        except ProviderError as error:
            if check:
                check()
            error.attempts = attempt
            delay = (
                error.retry_after
                if error.retry_after is not None
                else (2 if error.status == 429 else 1) * 2 ** (attempt - 1)
            )
            retry = (
                error.retryable
                and attempt < MAX_ATTEMPTS
                and not (progress and progress())
                and delay <= MAX_RETRY_DELAY
                and time.monotonic() - started + delay < RETRY_WINDOW
            )
            diagnostic(
                "retry" if retry else "failure",
                target,
                payload,
                key,
                attempt=attempt,
                status=error.status,
                code=error.code,
                request_id=error.request_id,
                detail=safe_text(error, key),
                elapsed_ms=round((time.monotonic() - started) * 1000),
                retry_delay_ms=round(delay * 1000) if retry else None,
                output_started=bool(progress and progress()),
            )
            if not retry:
                raise
            callback = scope.get("on_retry")
            if callback:
                callback(
                    {
                        "attempt": attempt + 1,
                        "delay_ms": round(delay * 1000),
                        "code": error.code,
                        "message": "模型请求暂时失败，正在自动重试…",
                    }
                )
            cancelled = scope.get("cancelled")
            if cancelled is not None:
                if cancelled.wait(delay) and check:
                    check()
            else:
                time.sleep(delay)
