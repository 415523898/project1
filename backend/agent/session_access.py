"""Conversation ownership checks with explicit storage and identity inputs."""

from agent import eventlog


def check_session(root, owner, session_id, allow_new=False):
    if not isinstance(session_id, str) or not eventlog.SESSION_ID.fullmatch(session_id):
        raise ValueError("对话编号无效。")
    if not owner:
        raise ValueError("请先登录。")
    # IDs also identify figure/upload directories, so another account cannot
    # claim an existing ID by creating a second conversation with that ID.
    if root.is_dir():
        for directory in root.iterdir():
            if directory.is_dir() and directory.name != owner:
                if eventlog.SessionLog(root, directory.name, session_id).exists():
                    raise ValueError("对话不存在或不属于当前账号。")
    if not allow_new and not eventlog.SessionLog(root, owner, session_id).exists():
        raise ValueError("对话不存在或不属于当前账号。")
    return session_id
