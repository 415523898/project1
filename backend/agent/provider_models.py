"""Fetch model IDs on an explicit user action; credentials stay in headers."""

import socket
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request

from agent import provider, provider_catalog


def list_models(settings):
    key = provider.provider_options.request_key(settings.get("api_key"))
    target = provider.endpoint(settings.get("base_url", "").strip(), settings)
    protocol = target.options.get("protocol", "chat")
    base = str(target)
    suffix = {"chat": "/chat/completions", "responses": "/responses", "anthropic": "/messages"}.get(
        protocol
    )
    if suffix:
        base = base.removesuffix(suffix)
    headers = {"Accept": "application/json"}
    if protocol == "gemini":
        headers["x-goog-api-key"] = key
    elif protocol == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        headers["Authorization"] = "Bearer " + key
    upstream = None
    try:
        url = (
            provider_catalog.models_url(settings.get("base_url", "").strip(), protocol)
            or base.rstrip("/") + "/models"
        )
        upstream = provider.open_stream(Request(url, headers=headers))
        result = provider.read_payload(upstream)
        if result.get("error"):
            raise provider._response_error(result, upstream.headers, key)
        rows = result.get("models" if protocol == "gemini" else "data", [])
        if not isinstance(rows, list):
            raise ValueError("上游未返回有效的模型目录，请手动添加模型。")
        ids = []
        for row in rows[:500]:
            if not isinstance(row, dict):
                continue
            if (
                protocol == "gemini"
                and row.get("supportedGenerationMethods")
                and "generateContent" not in row["supportedGenerationMethods"]
            ):
                continue
            value = row.get("name" if protocol == "gemini" else "id")
            if isinstance(value, str):
                value = value.removeprefix("models/").strip()
                if 0 < len(value) <= 200 and value not in ids:
                    ids.append(value)
        return {
            "models": [{"id": value} for value in ids[:100]],
            "truncated": len(ids) > 100
            or bool(result.get("nextPageToken") or result.get("has_more")),
        }
    except HTTPError as error:
        raise provider._http_error(error, key) from error
    except (URLError, TimeoutError, socket.timeout, OSError, HTTPException) as error:
        raise provider.connection_failure(error, key) from error
    finally:
        if upstream is not None:
            upstream.close()
