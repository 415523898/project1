"""Hold malformed tool markup before it reaches the visible token stream.

Executable tools are never recovered from text. MiMo's metadata-only direction
format can be normalized against the declared schema; code examples stay text.
"""

import json
import re
import secrets

OPENERS = tuple(
    "<" + name + boundary
    for name in ("tool_call", "tool_calls", "function_call", "function_calls", "tool_use")
    for boundary in (">", " ", "\n", "\r", "\t")
) + ("<function=", "[tool_calls]", "[tool_call]")
MAX_OPENER_LENGTH = max(map(len, OPENERS))

FORMAT_CORRECTION = (
    "上一请求把工具调用写成了正文，程序没有执行这些文本。"
    "需要工具时必须通过接口 tools 返回真实 tool_calls，严格使用本次声明的工具名称和参数；"
    "不要输出 <tool_call>、<function=...>、<tool_use> 或 [TOOL_CALLS] 等协议文本。"
    "无需工具时直接完整回答用户，已有实验与已保存步骤不要重复执行。解释代码语法时放在 Markdown 代码块中。"
)


class ToolMarkupFilter:
    def __init__(self):
        self.pending = ""
        self.code = None
        self.found = False

    def feed(self, text, final=False):
        if self.found:
            return ""
        self.pending += text
        output, index = [], 0
        while index < len(self.pending):
            char = self.pending[index]
            if char in ("`", "~"):
                end = index + 1
                while end < len(self.pending) and self.pending[end] == char:
                    end += 1
                if end == len(self.pending) and not final:
                    break
                count = end - index
                if self.code:
                    mark, width = self.code
                    if char == mark and (count == width or width >= 3 and count >= width):
                        self.code = None
                elif char == "`" or count >= 3:
                    self.code = (char, count)
                output.append(self.pending[index:end])
                index = end
                continue
            if char in ("<", "[") and not self.code:
                candidate = self.pending[index : index + MAX_OPENER_LENGTH].lower()
                if any(candidate.startswith(opener) for opener in OPENERS):
                    self.found = True
                    break
                if any(opener.startswith(candidate) for opener in OPENERS):
                    if not final:
                        break
                    if len(candidate) >= 6:
                        self.found = True
                        break
            output.append(char)
            index += 1
        self.pending = "" if self.found else self.pending[index:]
        return "".join(output)

    def finish(self):
        return self.feed("", final=True)


def reject_tool_markup(text):
    """Apply the same text/protocol boundary to non-streaming consumers."""
    guard = ToolMarkupFilter()
    guard.feed(text or "", final=True)
    if guard.found:
        from agent.provider_transport import ProviderError

        raise ProviderError(
            "模型将工具调用写成了正文，未执行该文本；本步需要返回真实工具调用。", code="tool_format"
        )


def native_calls_match(calls, payload):
    """Only structured calls to tools declared on this request can justify hiding a duplicate body."""
    names = {item.get("function", {}).get("name") for item in payload.get("tools", [])}
    if not isinstance(calls, list) or not calls or not names:
        return False
    for call in calls:
        if (
            not isinstance(call, dict)
            or call.get("type") != "function"
            or not isinstance(call.get("id"), str)
            or not call["id"]
        ):
            return False
        function = call.get("function")
        if (
            not isinstance(function, dict)
            or function.get("name") not in names
            or not isinstance(function.get("arguments"), str)
        ):
            return False
        try:
            if not isinstance(json.loads(function["arguments"]), dict):
                return False
        except (ValueError, TypeError):
            return False
    return True


def normalize_tool_reply(text, calls, payload):
    """Discard duplicate protocol prose, never turn prose into executable calls.

    Some responses contain BOTH native calls and their XML-like representation.
    The original guard rejected the native calls too. Executors still validate
    each native call's schema, permissions and side effects after this boundary.
    """
    remaining, visible = text or "", []
    while remaining:
        guard = ToolMarkupFilter()
        head = guard.feed(remaining, final=True)
        visible.append(head)
        if not guard.found:
            break
        if not native_calls_match(calls, payload):
            reject_tool_markup(remaining)
        names = {call["function"]["name"] for call in calls}
        block = re.match(
            r"<tool_call>\s*<function=([\w.-]+)>(.*?)</function>\s*</tool_call>",
            remaining[len(head) :],
            re.S,
        )
        # Only a complete duplicate has a safe boundary for resuming public text.
        if not block or block[1] not in names or re.search(r"<(?:tool_call|function=)", block[2]):
            break
        remaining = remaining[len(head) + block.end() :]
    return "".join(visible)


def recover_direction(text, payload):
    """Compatibility for one non-mutating, explicitly declared metadata tool."""
    if not payload.get("model", "").lower().split("/")[-1].startswith("mimo-"):
        return None
    spec = next(
        (
            item.get("function")
            for item in payload.get("tools", [])
            if item.get("function", {}).get("name") == "report_learning_direction"
        ),
        None,
    )
    if not spec:
        return None
    guard = ToolMarkupFilter()
    head = guard.feed(text, final=True)
    if not guard.found:
        return None
    block = re.match(
        r"<tool_call>\s*<function=report_learning_direction>\s*(.*?)\s*</function>\s*</tool_call>",
        text[len(head) :],
        re.S,
    )
    if not block:
        return None
    tail = text[len(head) + block.end() :]
    tail_guard = ToolMarkupFilter()
    tail_guard.feed(tail, final=True)
    if tail_guard.found:
        return None
    parameters = block[1]
    values = {}
    position = 0
    for match in re.finditer(r"\s*<parameter=(\w+)>(.*?)</parameter>", parameters, re.S):
        if match.start() != position or match[1] in values:
            return None
        raw = match[2].strip()
        try:
            value = json.loads(raw) if raw.startswith('"') or raw == "null" else raw
        except ValueError:
            return None
        values[match[1]] = value
        position = match.end()
    if parameters[position:].strip() or set(values) != {"intent", "method_id", "evidence"}:
        return None
    properties = spec.get("parameters", {}).get("properties", {})
    if values["intent"] not in properties.get("intent", {}).get("enum", []):
        return None
    if values["method_id"] not in properties.get("method_id", {}).get("enum", []):
        return None
    if not isinstance(values["evidence"], str) or len(values["evidence"]) > 4000:
        return None
    return head + tail, [
        {
            "id": "compat_direction_" + secrets.token_hex(8),
            "type": "function",
            "function": {
                "name": "report_learning_direction",
                "arguments": json.dumps(values, ensure_ascii=False),
            },
        }
    ]


def reconcile_direction_calls(text, calls, payload):
    """Repair only MiMo's declared, non-executable direction metadata.

    A response can contain a partial native direction call, the complete strict
    metadata wrapper, and other intact native tools. Keep their IDs and boundaries;
    never recover executable tools or their arguments from the body.
    """
    recovery = recover_direction(text, payload)
    if not recovery:
        return text, calls
    visible, recovered = recovery
    direction = "report_learning_direction"
    existing = [call for call in calls or [] if call.get("function", {}).get("name") == direction]
    if len(existing) > 1:
        return text, calls
    result = list(calls or [])
    if not existing:
        result.insert(0, recovered[0])
    else:
        current = existing[0]
        try:
            valid_json = isinstance(json.loads(current["function"]["arguments"]), dict)
        except (ValueError, TypeError, KeyError):
            valid_json = False
        if not valid_json:
            replacement = {**recovered[0], "id": current.get("id") or recovered[0]["id"]}
            result[result.index(current)] = replacement
    from agent.provider_transport import tool_text_recovered

    tool_text_recovered()
    return visible, result
