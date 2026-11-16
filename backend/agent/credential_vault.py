"""Account-scoped encrypted provider profiles. No API returns plaintext credentials."""

import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from agent import provider_catalog, provider_options, provider_profiles
from agent.private_files import private_dir
from agent.provider_profiles import model_options as model_options
from config import VAULT_DATABASE_TIMEOUT_SECONDS, environment, vault_key_path

IDENTIFIER = re.compile(r"^[a-z][a-z0-9-]{0,79}$")


class VaultError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def keyring(root, production=False):
    configured = environment("FOREST_VAULT_KEYS").strip()
    if production and not configured and not environment("FOREST_VAULT_KEY_FILE"):
        raise VaultError("生产环境必须显式指定 FOREST_VAULT_KEY_FILE 或 FOREST_VAULT_KEYS。", 503)
    path = vault_key_path(root)
    if configured:
        raw = configured
    else:
        if not path.exists():
            if production:
                raise VaultError("生产环境必须配置独立的密钥文件或 FOREST_VAULT_KEYS。", 503)
            private_dir(path.parent)
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(Fernet.generate_key() + b"\n")
        if production and os.name != "nt" and path.stat().st_mode & 0o077:
            raise VaultError("服务器主密钥文件权限须为 600。", 503)
        raw = path.read_text(encoding="ascii").strip()
    try:
        return MultiFernet(
            [Fernet(value.strip().encode()) for value in raw.split(",") if value.strip()]
        )
    except (ValueError, TypeError):
        raise VaultError("服务器加密主密钥格式无效。", 503)


class Vault:
    def __init__(self, root, cipher=None, production=False):
        self.root = private_dir(root)
        self.cipher = cipher or keyring(root, production)
        self.path = self.root / "credentials.sqlite3"
        with self.db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS credentials(owner TEXT, id TEXT, ciphertext BLOB NOT NULL, PRIMARY KEY(owner,id))"
            )
        if os.name != "nt":
            self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=VAULT_DATABASE_TIMEOUT_SECONDS)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _read(self, owner, identifier):
        with self.db() as db:
            row = db.execute(
                "SELECT ciphertext FROM credentials WHERE owner=? AND id=?", (owner, identifier)
            ).fetchone()
        if not row:
            return None
        try:
            value = json.loads(self.cipher.decrypt(row[0]))
            if value["owner"] != owner or value["id"] != identifier:
                raise ValueError()
            return value
        except (InvalidToken, ValueError, KeyError):
            raise VaultError("服务器无法解密该配置，请检查主密钥及备份。", 503)

    def _public(self, value):
        return {
            "id": value["id"],
            "settings": provider_catalog.metadata(value["id"], value["settings"]),
            "has_key": bool(value["api_key"]),
        }

    def list(self, owner):
        with self.db() as db:
            ids = [
                row[0]
                for row in db.execute(
                    "SELECT id FROM credentials WHERE owner=? ORDER BY id", (owner,)
                )
            ]
        return [
            self._public(value) for identifier in ids if (value := self._read(owner, identifier))
        ]

    def save(self, owner, identifier, payload):
        if not IDENTIFIER.fullmatch(identifier) or not isinstance(payload, dict):
            raise VaultError("提供商配置无效。")
        try:
            settings, protocol, base = provider_profiles.normalize(
                identifier, payload.get("settings")
            )
        except provider_profiles.InvalidProfile as error:
            raise VaultError(str(error)) from error
        previous = self._read(owner, identifier)
        key = (
            payload.get("api_key")
            if "api_key" in payload
            else previous["api_key"]
            if previous
            else ""
        )
        try:
            key = provider_options.api_key(key, allow_empty=True)
        except ValueError as error:
            raise VaultError(str(error)) from None
        # Reusing a key at a changed destination requires explicitly re-entering it.
        if (
            previous
            and "api_key" not in payload
            and (
                base.strip().rstrip("/") != previous["settings"]["base_url"].rstrip("/")
                or protocol != previous["settings"]["protocol"]
            )
        ):
            raise VaultError("更换上游地址或协议时，请重新填写 API Key。")
        settings["base_url"] = base.strip().rstrip("/")
        settings["enabled"] = settings.get("enabled") is True and bool(key)
        value = {"owner": owner, "id": identifier, "settings": settings, "api_key": key}
        encrypted = self.cipher.encrypt(json.dumps(value, ensure_ascii=False).encode())
        with self.db() as db:
            db.execute(
                "INSERT INTO credentials VALUES (?,?,?) ON CONFLICT(owner,id) DO UPDATE SET ciphertext=excluded.ciphertext",
                (owner, identifier, encrypted),
            )
        return self._public(value)

    def delete(self, owner, identifier):
        with self.db() as db:
            db.execute("DELETE FROM credentials WHERE owner=? AND id=?", (owner, identifier))

    def resolve(self, owner, payload, catalog=False):
        identifier = payload.get("credential_id")
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
            raise VaultError("凭据引用无效。")
        value = self._read(owner, identifier)
        if not value or not value["api_key"] or not value["settings"]["enabled"]:
            raise VaultError("提供商未配置密钥或已停用。", 403)
        saved = value["settings"]
        for field in ("base_url", "protocol"):
            requested = payload.get(field, saved[field])
            if not isinstance(requested, str) or requested.rstrip("/") != saved[field].rstrip("/"):
                raise VaultError("已保存密钥只能用于绑定的上游地址与协议。", 403)
        models = {m["id"]: m for m in saved["models"] if m.get("enabled") is not False}
        model_id = payload.get("model", saved.get("model"))
        if not catalog and model_id not in models:
            raise VaultError("此提供商未启用该模型。", 403)
        model = models.get(model_id, {})
        payload.update(
            base_url=saved["base_url"],
            protocol=saved["protocol"],
            model=model_id,
            provider_family=saved.get("provider_family", "custom"),
            api_key=value["api_key"],
        )
        payload["model_options"] = model_options(model)
        payload.pop("credential_id", None)

    def rotate(self):
        """MultiFernet's first key encrypts; retain old keys until this completes."""
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            for owner, identifier, encrypted in db.execute(
                "SELECT owner,id,ciphertext FROM credentials"
            ).fetchall():
                rotated = self.cipher.rotate(encrypted)
                db.execute(
                    "UPDATE credentials SET ciphertext=? WHERE owner=? AND id=?",
                    (rotated, owner, identifier),
                )


_cache, _lock = {}, threading.Lock()


def for_root(auth_root, production=False):
    """Open/cache the vault for an explicit account root, retaining legacy backup behavior."""
    key = (str(Path(auth_root)), bool(production))
    with _lock:
        if key not in _cache:
            root = Path(auth_root) / ".vault"
            legacy = Path(auth_root).parent
            if (
                Path(auth_root).name == "users"
                and (legacy / "credentials.sqlite3").is_file()
                and not (root / "credentials.sqlite3").exists()
            ):
                private_dir(root)
                source = sqlite3.connect(
                    (legacy / "credentials.sqlite3").as_uri() + "?mode=ro", uri=True
                )
                destination = sqlite3.connect(root / "credentials.sqlite3")
                try:
                    source.backup(destination)
                finally:
                    source.close()
                    destination.close()
                old_key = legacy / "secrets/vault.key"
                new_key = root / "secrets/vault.key"
                if (
                    not environment("FOREST_VAULT_KEYS")
                    and not environment("FOREST_VAULT_KEY_FILE")
                    and old_key.is_file()
                    and not new_key.exists()
                ):
                    private_dir(new_key.parent)
                    fd = os.open(new_key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    with os.fdopen(fd, "wb") as file:
                        file.write(old_key.read_bytes())
            _cache[key] = Vault(root, production=key[1])
        return _cache[key]


def for_app():
    """Compatibility adapter for request handlers and existing Flask test fixtures."""
    from flask import current_app

    from agent.api.auth_api import AUTH

    return for_root(AUTH.root, bool(current_app.config.get("PRODUCTION")))
