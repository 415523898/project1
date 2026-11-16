import re
import uuid
from pathlib import Path

SAFE_SCOPE = re.compile(r"^[A-Za-z0-9_-]{1,64}\Z")


def scope_in(base, session_id=None, run_id=None):
    base = Path(base)
    scope = session_id if isinstance(session_id, str) and SAFE_SCOPE.match(session_id) else None
    if scope is None:
        name = "run-" + (run_id or uuid.uuid4().hex[:12])
        target = base / "unassigned" / name
    else:
        name = run_id or uuid.uuid4().hex[:12]
        if not SAFE_SCOPE.match(name):
            name = uuid.uuid4().hex[:12]
        target = base / scope / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def scope_dir(root, session_id=None, run_id=None):
    return scope_in(Path(root) / "figures", session_id, run_id)


def session_dir(root, session_id):
    if not isinstance(session_id, str) or not SAFE_SCOPE.match(session_id):
        return None
    return Path(root) / "figures" / session_id


def migrate_legacy(root, sessions_dir):
    import json
    import shutil

    base = Path(root) / "figures"
    if not base.is_dir():
        return 0
    owners = {}
    sessions_path = Path(sessions_dir)
    if sessions_path.is_dir():
        for record_path in sessions_path.glob("*.json"):
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            text = json.dumps(record, ensure_ascii=False)
            for name in set(re.findall(r"[A-Za-z0-9_.-]+\.png", text)):
                owners.setdefault(name, record_path.stem)
    moved = 0
    for path in list(base.glob("*.png")):
        owner = owners.get(path.name)
        target_dir = base / owner if owner else base / "unassigned" / "legacy"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / path.name
        if target.exists():
            target = target_dir / f"{path.stem}-{uuid.uuid4().hex[:6]}{path.suffix}"
        try:
            shutil.move(str(path), str(target))
            moved += 1
        except OSError:
            continue
    return moved


def drop_session_figures(root, session_id):
    target = session_dir(root, session_id)
    if target is None or not target.is_dir():
        return 0
    removed = sum(1 for path in target.rglob("*") if path.is_file())
    import shutil

    shutil.rmtree(target, ignore_errors=True)
    return removed
