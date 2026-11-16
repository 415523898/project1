"""Password hashes and revocable hashed sessions shared across workers."""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHash, VerificationError

from agent.private_files import private_dir, write_json
from config import (
    AUTH_DATABASE_TIMEOUT_SECONDS,
    AUTH_HASH_MEMORY_KIB,
    AUTH_HASH_PARALLELISM,
    AUTH_HASH_TIME_COST,
)
from config import (
    AUTH_IDLE_SECONDS as IDLE_SECONDS,
)
from config import (
    AUTH_MAX_PASSWORD as MAX_PASSWORD,
)
from config import (
    AUTH_MAX_USERS as MAX_USERS,
)
from config import (
    AUTH_MIN_PASSWORD as MIN_PASSWORD,
)
from config import (
    AUTH_TOKEN_TTL_SECONDS as TOKEN_TTL_SECONDS,
)

USERNAME = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff-]{2,24}\Z")
ACCOUNT = "account.json"
HASHER = PasswordHasher(
    time_cost=AUTH_HASH_TIME_COST,
    memory_cost=AUTH_HASH_MEMORY_KIB,
    parallelism=AUTH_HASH_PARALLELISM,
    type=Type.ID,
)
DUMMY = HASHER.hash("nonexistent-account-timing-placeholder")


class AuthError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def hash_password(password, **_legacy):
    return {"algorithm": "argon2id", "encoded": HASHER.hash(password)}


def verify_password(password, record):
    if (
        not isinstance(password, str)
        or not 1 <= len(password) <= 200
        or not isinstance(record, dict)
    ):
        return False
    try:
        if record.get("algorithm") == "argon2id":
            return HASHER.verify(record["encoded"], password)
        if record.get("algorithm") == "pbkdf2_sha256":
            iterations = int(record["iterations"])
            if not 10000 <= iterations <= 2000000:
                return False
            salt = base64.b64decode(record["salt"], validate=True)
            expected = base64.b64decode(record["hash"], validate=True)
            if not 8 <= len(salt) <= 64 or len(expected) != 32:
                return False
            return hmac.compare_digest(
                hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations), expected
            )
    except (KeyError, ValueError, TypeError, VerificationError, InvalidHash):
        return False
    return False


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class UserStore:
    def __init__(self, root):
        self.root = private_dir(root)
        self.lock = threading.RLock()
        self.database = self.root / ".auth.sqlite3"
        legacy = self.root.parent / "auth.sqlite3"
        if self.root.name == "users" and legacy.is_file() and not self.database.exists():
            source = sqlite3.connect(legacy.as_uri() + "?mode=ro", uri=True)
            destination = sqlite3.connect(self.database)
            try:
                source.backup(destination)
            finally:
                source.close()
                destination.close()
        with self.db() as db:
            db.executescript("""CREATE TABLE IF NOT EXISTS sessions (
              token TEXT PRIMARY KEY, username TEXT NOT NULL, issued REAL NOT NULL,
              touched REAL NOT NULL, verified REAL NOT NULL);
              CREATE INDEX IF NOT EXISTS session_owner ON sessions(username);
              CREATE TABLE IF NOT EXISTS attempts (scope TEXT PRIMARY KEY, started REAL, failures INTEGER);""")
            if "credential_hash" not in {
                row[1] for row in db.execute("PRAGMA table_info(sessions)")
            }:
                db.execute(
                    "ALTER TABLE sessions ADD COLUMN credential_hash TEXT NOT NULL DEFAULT ''"
                )
        if os.name != "nt":
            self.database.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=AUTH_DATABASE_TIMEOUT_SECONDS)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _path(self, username):
        return self.root / username / ACCOUNT

    def _read(self, username):
        if not isinstance(username, str) or not USERNAME.fullmatch(username):
            return None
        try:
            record = json.loads(self._path(username).read_text(encoding="utf-8"))
            return record if isinstance(record, dict) else None
        except (OSError, ValueError):
            return None

    @staticmethod
    def _check_credentials(username, password):
        if not isinstance(username, str) or not USERNAME.fullmatch(username):
            raise AuthError("用户名需为 2–24 位字母、数字、下划线、连字符或中文。")
        if not isinstance(password, str) or not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
            raise AuthError(
                f"新密码长度需为 {MIN_PASSWORD}–{MAX_PASSWORD} 位，支持空格和密码短语。"
            )
        if (
            password.lower() in {"123456789012", "password1234", "1234567890123456", "qwerty123456"}
            or len(set(password)) < 4
        ):
            raise AuthError("该密码过于常见，请使用更长的独立密码或密码短语。")

    def register(self, username, password):
        self._check_credentials(username, password)
        with self.lock, self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if self._read(username) is not None:
                raise AuthError("这个用户名已经被注册。", 409)
            if sum(path.is_dir() for path in self.root.iterdir()) >= MAX_USERS:
                raise AuthError("用户数量已达上限。", 429)
            private_dir(self.root / username)
            from agent import study_store

            study_store.initialize_account(self.root, username)
            write_json(
                self._path(username),
                {
                    "format": "forest-user-v2",
                    "username": username,
                    "password": hash_password(password),
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
            # Attempts made before this account existed do not apply to its new credentials.
            db.execute("DELETE FROM attempts WHERE scope=?", ("account:" + digest(username),))
        return {"username": username}

    def _throttle(self, username, address):
        now = time.time()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM attempts WHERE started < ?", (now - 900,))
            for scope, limit in [
                ("account:" + digest(str(username)), 5),
                ("address:" + digest(str(address)), 30),
            ]:
                row = db.execute("SELECT failures FROM attempts WHERE scope=?", (scope,)).fetchone()
                if row and row["failures"] >= limit:
                    raise AuthError("登录尝试过多，请在 15 分钟后重试。", 429)
                db.execute(
                    "INSERT INTO attempts VALUES (?,?,1) ON CONFLICT(scope) DO UPDATE SET failures=failures+1",
                    (scope, now),
                )

    def _verify(self, username, password, address=""):
        record = self._read(username)
        # Filesystems may resolve an alias spelling (notably Windows). The
        # persisted identity owns data, credentials and account throttles.
        username = record.get("username", username) if record else username
        self._throttle(username, address)
        stored = (
            record.get("password", {}) if record else {"algorithm": "argon2id", "encoded": DUMMY}
        )
        if not verify_password(password, stored) or not record:
            raise AuthError("用户名或密码不正确。", 401)
        with self.lock, self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            latest = self._read(username)
            if not latest or latest.get("password") != record.get("password"):
                raise AuthError("密码已变更，请重新登录。", 401)
            if stored.get("algorithm") != "argon2id" or HASHER.check_needs_rehash(
                stored["encoded"]
            ):
                latest["password"] = hash_password(password)
                write_json(self._path(username), latest)
                # A hash upgrade is not a password change. Keep valid device
                # sessions bound to the upgraded hash for this same account.
                db.execute(
                    "UPDATE sessions SET credential_hash=? WHERE username=? AND credential_hash=?",
                    (
                        self._fingerprint(latest),
                        username,
                        digest(json.dumps(stored, sort_keys=True)),
                    ),
                )
            db.execute("DELETE FROM attempts WHERE scope=?", ("account:" + digest(username),))
        return latest

    def login(self, username, password, address=""):
        if (
            not isinstance(username, str)
            or not isinstance(password, str)
            or len(username) > 100
            or len(password) > 200
        ):
            raise AuthError("请填写有效的用户名和密码。")
        record = self._verify(username, password, address)
        return self.issue(record.get("username", username), self._fingerprint(record))

    @staticmethod
    def _fingerprint(record):
        return digest(json.dumps(record["password"], sort_keys=True))

    def issue(self, username, fingerprint=None):
        with self.lock, self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            record = self._read(username)
            if not record or (fingerprint is not None and fingerprint != self._fingerprint(record)):
                raise AuthError("密码已变更，请重新登录。", 401)
            return self._issue(db, record.get("username", username), self._fingerprint(record))

    def _issue(self, db, username, fingerprint):
        token, now = secrets.token_urlsafe(32), time.time()
        db.execute(
            "DELETE FROM sessions WHERE issued < ? OR touched < ?",
            (now - TOKEN_TTL_SECONDS, now - IDLE_SECONDS),
        )
        db.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?)",
            (digest(token), username, now, now, now, fingerprint),
        )
        db.execute(
            "DELETE FROM sessions WHERE username=? AND token NOT IN (SELECT token FROM sessions WHERE username=? ORDER BY issued DESC LIMIT 10)",
            (username, username),
        )
        return {"username": username, "token": token, "expires_in": TOKEN_TTL_SECONDS}

    def logout(self, token):
        with self.db() as db:
            return bool(
                db.execute("DELETE FROM sessions WHERE token=?", (digest(str(token)),)).rowcount
            )

    def logout_all(self, username):
        with self.db() as db:
            db.execute("DELETE FROM sessions WHERE username=?", (username,))

    def _active_session(self, db, token):
        if not isinstance(token, str) or not 20 <= len(token) <= 200:
            return None, None
        now = time.time()
        row = db.execute("SELECT * FROM sessions WHERE token=?", (digest(token),)).fetchone()
        account = self._read(row["username"]) if row else None
        if (
            not row
            or not account
            or self._fingerprint(account) != row["credential_hash"]
            or now - row["issued"] > TOKEN_TTL_SECONDS
            or now - row["touched"] > IDLE_SECONDS
        ):
            db.execute("DELETE FROM sessions WHERE token=?", (digest(token),))
            return None, None
        return row, account

    def resolve(self, token):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row, account = self._active_session(db, token)
            if not row:
                return None
            db.execute("UPDATE sessions SET touched=? WHERE token=?", (time.time(), digest(token)))
        return account.get("username", row["username"])

    def require_recent(self, token):
        with self.db() as db:
            row, _ = self._active_session(db, token)
        if not row or time.time() - row["verified"] > 900:
            raise AuthError("请在“账号安全”中验证当前密码后再修改密钥。", 403)

    def reauthenticate(self, token, password, address=""):
        username = self.resolve(token)
        if not username:
            raise AuthError("登录已失效。", 401)
        verified = self._verify(username, password, address)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row, account = self._active_session(db, token)
            if not row or self._fingerprint(account) != self._fingerprint(verified):
                raise AuthError("登录已失效，请重新登录。", 401)
            db.execute("UPDATE sessions SET verified=? WHERE token=?", (time.time(), digest(token)))
        return username

    def change_password(self, token, password, new_password, address=""):
        username = self.reauthenticate(token, password, address)
        self._check_credentials(username, new_password)
        with self.lock, self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row, record = self._active_session(db, token)
            if not row or not verify_password(password, record["password"]):
                raise AuthError("登录或密码已变更，请重新登录。", 401)
            record["password"] = hash_password(new_password)
            write_json(self._path(username), record)
            db.execute("DELETE FROM sessions WHERE username=?", (username,))
            return self._issue(db, username, self._fingerprint(record))


STORE = None


def store(root):
    global STORE
    if STORE is None or STORE.root != Path(root):
        STORE = UserStore(root)
    return STORE
