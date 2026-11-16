"""Server-owned formula lesson for the confirmed method of a conversation."""

from agent import eventlog, study_binding
from engine import catalog, method_math


def current(log):
    if not isinstance(log, eventlog.SessionLog):
        return None
    binding = study_binding.public(log.root, log.owner, log.session_id)
    if not binding or binding["card_missing"] or binding["session_missing"]:
        return None
    return binding["method_id"]


def context(log):
    method_id = current(log)
    if not method_id:
        return None
    lesson = method_math.lesson(method_id)
    if not lesson:
        return None
    return {
        "method_id": method_id,
        "label": catalog.label_of(method_id),
        "lesson": lesson,
    }
