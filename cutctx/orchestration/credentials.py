"""Encrypted, multi-account credential storage."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class CredentialStoreError(RuntimeError):
    pass


class EncryptedCredentialStore:
    """Store credential payloads encrypted at rest with a separately held key.

    The master key can be injected through ``CUTCTX_ORCHESTRATION_MASTER_KEY``.
    Otherwise a mode-0600 local key is created lazily on the first write.  This
    keeps read-only proxy startup free of filesystem side effects.
    """

    def __init__(self, path: Path | str, key_path: Path | str | None = None) -> None:
        self.path = Path(path)
        self.key_path = Path(key_path) if key_path else self.path.with_suffix(".key")
        self._lock = threading.RLock()

    def put(self, reference: str, secret: dict[str, Any]) -> None:
        if not reference.strip():
            raise ValueError("Credential reference must not be empty")
        with self._lock:
            values = self._read_all()
            values[reference] = dict(secret)
            self._write_all(values)

    def get(self, reference: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._read_all().get(reference)
            return dict(value) if isinstance(value, dict) else None

    def delete(self, reference: str) -> bool:
        with self._lock:
            values = self._read_all()
            if reference not in values:
                return False
            del values[reference]
            self._write_all(values)
            return True

    def references(self) -> list[str]:
        with self._lock:
            return sorted(self._read_all())

    def _fernet(self, *, create: bool) -> Fernet | None:
        injected = os.environ.get("CUTCTX_ORCHESTRATION_MASTER_KEY", "").strip()
        if injected:
            key = injected.encode("ascii")
        elif self.key_path.exists():
            key = self.key_path.read_bytes().strip()
        elif create:
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            key = Fernet.generate_key()
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            descriptor = os.open(self.key_path, flags, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(key)
        else:
            return None
        try:
            return Fernet(key)
        except (TypeError, ValueError) as exc:
            raise CredentialStoreError("Invalid orchestration master key") from exc

    def _read_all(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        fernet = self._fernet(create=False)
        if fernet is None:
            raise CredentialStoreError("Credential data exists but its encryption key is missing")
        try:
            decrypted = fernet.decrypt(self.path.read_bytes())
            payload = json.loads(decrypted.decode("utf-8"))
        except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CredentialStoreError("Credential store cannot be decrypted") from exc
        if not isinstance(payload, dict):
            raise CredentialStoreError("Credential store has an invalid payload")
        return {str(key): dict(value) for key, value in payload.items() if isinstance(value, dict)}

    def _write_all(self, payload: dict[str, dict[str, Any]]) -> None:
        fernet = self._fernet(create=True)
        assert fernet is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = fernet.encrypt(json.dumps(payload, sort_keys=True).encode("utf-8"))
        descriptor, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
