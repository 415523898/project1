"""Compatibility HTTP adapter; non-HTTP workflows use agent.session_access."""

from agent import session_access
from agent.api.auth_api import current
from config import USER_ROOT


def check_session(session_id, allow_new=False):
    return session_access.check_session(USER_ROOT, current(), session_id, allow_new)
