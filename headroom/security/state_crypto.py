"""State encryption and integrity protection for Headroom local files.

Provides machine-derived symmetric encryption (Fernet) for sensitive local state
(trial, seat) and HMAC-SHA256 integrity signing for license cache files.

Design:
    * Encryption key is derived deterministically from machine-specific identifiers
      (hostname + username + MAC address) so state files are bound to the machine
      and cannot be trivially copied/tampered across hosts.
    * HMAC key comes from ``HEADROOM_LICENSE_HMAC_SECRET`` env var. When unset,
      signing is skipped (development/backward-compat mode).
    * All functions are pure and accept explicit keys/paths — no hidden global state.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import platform
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("headroom.security.state_crypto")

# ---------------------------------------------------------------------------
# Machine-derived encryption key (Fernet)
# ---------------------------------------------------------------------------

_FERNET_KEY_ENV = "HEADROOM_STATE_ENCRYPTION_KEY"
_HMAC_SECRET_ENV = "HEADROOM_LICENSE_HMAC_SECRET"


def _machine_fingerprint() -> bytes:
    """Build a machine-specific fingerprint for key derivation.

    Combines hostname, username, and MAC address into a single byte string.
    This is deterministic per-machine but not portable — intentional: we want
    state files to be bound to the machine.
    """
    parts = [
        platform.node().encode(),
        os.environ.get("USER", os.environ.get("USERNAME", "")).encode(),
        str(uuid.getnode()).encode(),  # MAC address as integer
    ]
    return b"|".join(parts)


def derive_fernet_key() -> bytes:
    """Derive a Fernet-compatible 32-byte key from the machine fingerprint.

    Returns a URL-safe base64-encoded 32-byte key suitable for
    ``cryptography.fernet.Fernet(key)``.
    """
    env_key = os.environ.get(_FERNET_KEY_ENV, "").strip()
    if env_key:
        return env_key.encode()

    raw = hashlib.sha256(_machine_fingerprint()).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_json(data: dict[str, Any], key: bytes | None = None) -> str:
    """Encrypt a JSON-serializable dict to a Fernet token string."""
    from cryptography.fernet import Fernet

    if key is None:
        key = derive_fernet_key()
    f = Fernet(key)
    plaintext = json.dumps(data, separators=(",", ":")).encode()
    return f.encrypt(plaintext).decode()


def decrypt_json(token: str, key: bytes | None = None) -> dict[str, Any]:
    """Decrypt a Fernet token string back to a JSON dict.

    Raises ``cryptography.fernet.InvalidToken`` on tampered/corrupt data.
    """
    from cryptography.fernet import Fernet

    if key is None:
        key = derive_fernet_key()
    f = Fernet(key)
    plaintext = f.decrypt(token)
    return json.loads(plaintext)


# ---------------------------------------------------------------------------
# HMAC-SHA256 signing for license cache
# ---------------------------------------------------------------------------


def _get_hmac_secret() -> str | None:
    """Return the HMAC signing secret from env, or None if unset."""
    return os.environ.get(_HMAC_SECRET_ENV, "").strip() or None


def sign_payload(data: dict[str, Any], secret: str | None = None) -> str:
    """Compute HMAC-SHA256 signature of a JSON payload.

    The payload is canonicalized to compact JSON (sorted keys, no whitespace)
    before signing so signatures are deterministic.
    """
    if secret is None:
        secret = _get_hmac_secret()
    if not secret:
        return ""

    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()


def verify_payload(data: dict[str, Any], signature: str, secret: str | None = None) -> bool:
    """Verify HMAC-SHA256 signature of a JSON payload.

    Returns True if the signature is valid. Returns True (skip) if no secret
    is configured (development/backward-compat mode).
    """
    if secret is None:
        secret = _get_hmac_secret()
    if not secret:
        # No secret configured — skip verification (dev mode)
        return True
    expected = sign_payload(data, secret)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Encrypted file I/O helpers
# ---------------------------------------------------------------------------

_ENCRYPTED_MARKER = "HEADROOM_ENCRYPTED_V1"


def write_encrypted_json(path: Path, data: dict[str, Any]) -> None:
    """Encrypt and write a JSON dict to a file.

    File format:
        Line 1: marker string ("HEADROOM_ENCRYPTED_V1")
        Line 2: Fernet token (base64)
    """
    token = encrypt_json(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{_ENCRYPTED_MARKER}\n{token}\n")


_STRICT_STATE_ENV = "HEADROOM_STRICT_STATE"


def read_encrypted_json(path: Path) -> dict[str, Any] | None:
    """Read and decrypt a JSON dict from a file.

    Falls back to reading as plain JSON only if ``HEADROOM_STRICT_STATE`` is
    not set — this preserves backward-compat for users upgrading from older
    versions that stored plain JSON. In strict mode (production deployments),
    plain JSON files are rejected to prevent tampered-file substitution attacks.

    Returns None if the file doesn't exist or is corrupt.
    """
    if not path.exists():
        return None

    strict = os.environ.get(_STRICT_STATE_ENV, "").strip().lower() in ("1", "true", "yes")

    try:
        content = path.read_text()
        lines = content.strip().split("\n", 1)
        if len(lines) == 2 and lines[0] == _ENCRYPTED_MARKER:
            return decrypt_json(lines[1])
    except Exception:
        logger.warning("Failed to decrypt %s, trying plain JSON fallback", path)

    if strict:
        logger.error(
            "State file at %s is not encrypted and HEADROOM_STRICT_STATE=1 is set. "
            "Refusing to load plain JSON to prevent tampered-file substitution. "
            "Delete the file and restart to create a fresh encrypted state.",
            path,
        )
        return None

    # Fallback: plain JSON (migration path — disabled in strict mode)
    logger.warning(
        "State file at %s is not encrypted (plain JSON). Loading for migration. "
        "Set HEADROOM_STRICT_STATE=1 to reject unencrypted files in production.",
        path,
    )
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Corrupt state file at %s", path)
        return None


def write_hmac_json(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON dict with an HMAC signature for integrity.

    File format:
        {
            "payload": { ... original data ... },
            "signature": "hex-hmac-sha256"
        }
    """
    signature = sign_payload(data)
    envelope: dict[str, Any] = {"payload": data}
    if signature:
        envelope["signature"] = signature
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2))


def read_hmac_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON dict and verify its HMAC signature.

    Returns the payload dict if the signature is valid (or no secret is
    configured). Returns None if the signature is invalid or the file is
    corrupt.
    """
    if not path.exists():
        return None

    try:
        envelope = json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError):
        logger.warning("Corrupt HMAC file at %s", path)
        return None

    if "payload" not in envelope:
        # Legacy plain JSON — return as-is for migration
        logger.info("Legacy plain JSON at %s, treating as unsigned", path)
        return envelope

    payload = envelope["payload"]
    signature = envelope.get("signature", "")

    if not verify_payload(payload, signature):
        logger.warning(
            "HMAC signature mismatch at %s — file may have been tampered with", path
        )
        return None

    return payload
