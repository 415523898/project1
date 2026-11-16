def boolean(key, label, default, group=None, depends_on=None, hidden_when=None):
    item = {"key": key, "label": label, "type": "boolean", "default": default}
    if group:
        item["group"] = group
    if depends_on:
        item["depends_on"] = depends_on
    if hidden_when:
        item["hidden_when"] = hidden_when
    return item


def integer(
    key, label, default, low=None, high=None, step=1, group=None, depends_on=None, hidden_when=None
):
    item = {"key": key, "label": label, "type": "integer", "default": default, "step": step}
    if low is not None:
        item["min"] = low
    if high is not None:
        item["max"] = high
    if group:
        item["group"] = group
    if depends_on:
        item["depends_on"] = depends_on
    if hidden_when:
        item["hidden_when"] = hidden_when
    return item


def number(
    key,
    label,
    default,
    low=None,
    high=None,
    step=None,
    group=None,
    depends_on=None,
    hidden_when=None,
):
    item = {"key": key, "label": label, "type": "number", "default": default}
    if low is not None:
        item["min"] = low
    if high is not None:
        item["max"] = high
    if step is not None:
        item["step"] = step
    if group:
        item["group"] = group
    if depends_on:
        item["depends_on"] = depends_on
    if hidden_when:
        item["hidden_when"] = hidden_when
    return item


def enum(key, label, default, options, group=None, depends_on=None, hidden_when=None):
    item = {
        "key": key,
        "label": label,
        "type": "enum",
        "default": default,
        "options": list(options),
    }
    if group:
        item["group"] = group
    if depends_on:
        item["depends_on"] = depends_on
    if hidden_when:
        item["hidden_when"] = hidden_when
    return item


def text(key, label, default=None, group=None, depends_on=None, hidden_when=None):
    item = {"key": key, "label": label, "type": "text", "default": default}
    if group:
        item["group"] = group
    if depends_on:
        item["depends_on"] = depends_on
    if hidden_when:
        item["hidden_when"] = hidden_when
    return item


def columns(key, label, group=None, depends_on=None):
    item = {"key": key, "label": label, "type": "columns", "default": None}
    if group:
        item["group"] = group
    if depends_on:
        item["depends_on"] = depends_on
    return item
