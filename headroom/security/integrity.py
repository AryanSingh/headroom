"""EE binary integrity verification for Cutctx.

Verifies that all compiled headroom_ee extension modules (.so/.pyd) match the
SHA-256 hashes recorded in the signed integrity manifest
(``headroom_ee/MANIFEST.sha256.json``).

Called once at EE import time (``headroom_ee.__init__``) before any proprietary
code is executed. If a module hash mismatches or the manifest signature is
invalid, EE loading is aborted.

Design:
    * The manifest is HMAC-SHA256 signed with ``HEADROOM_LICENSE_HMAC_SECRET``.
    * If the secret is not set, signature verification is skipped and only
      hash integrity is checked (development / air-gap installs without the
      secret).
    * If ``HEADROOM_SKIP_INTEGRITY_CHECK=1`` the entire check is bypassed
      (emergency escape hatch for debugging — never set in production).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("headroom.security.integrity")

_HMAC_SECRET_ENV = "HEADROOM_LICENSE_HMAC_SECRET"
_SKIP_CHECK_ENV = "HEADROOM_SKIP_INTEGRITY_CHECK"
_MANIFEST_FILENAME = "MANIFEST.sha256.json"


def _ee_dir() -> Path:
    """Return the path to the installed headroom_ee package directory."""
    try:
        import headroom_ee  # type: ignore[import]
        return Path(headroom_ee.__file__).parent
    except ImportError:
        # headroom_ee not installed — nothing to check
        return Path("/nonexistent")


def _load_manifest(ee_dir: Path) -> dict[str, Any] | None:
    """Load and parse the manifest file. Returns None if missing."""
    manifest_path = ee_dir / _MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read EE manifest at %s: %s", manifest_path, exc)
        return None


def _verify_manifest_signature(manifest: dict[str, Any], secret: str) -> bool:
    """Return True if the manifest HMAC signature is valid."""
    provided_sig = manifest.get("signature", "")
    if not provided_sig:
        return False  # signature field is required when a secret is set

    # Reconstruct the payload that was signed (everything except 'signature')
    payload = {k: v for k, v in manifest.items() if k != "signature"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    expected_sig = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()

    # Constant-time comparison
    diff = 0
    for a, b in zip(expected_sig.encode(), provided_sig.encode()):
        diff |= a ^ b
    return diff == 0 and len(expected_sig) == len(provided_sig)


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class IntegrityError(RuntimeError):
    """Raised when EE module integrity check fails."""


def verify_ee_manifest(strict: bool = True) -> None:
    """Verify all headroom_ee .so files against the signed integrity manifest.

    Args:
        strict: If True (default), raise ``IntegrityError`` on any failure.
            If False, log a warning instead (use only in dev environments).

    Raises:
        IntegrityError: Hash mismatch, missing files, or invalid manifest
            signature (when ``HEADROOM_LICENSE_HMAC_SECRET`` is set and
            ``strict=True``).
    """
    if os.environ.get(_SKIP_CHECK_ENV, "").strip() in ("1", "true", "yes"):
        logger.warning(
            "EE integrity check SKIPPED (%s=1). "
            "Never set this in production.",
            _SKIP_CHECK_ENV,
        )
        return

    ee_dir = _ee_dir()
    if not ee_dir.exists():
        # headroom_ee not installed — nothing to verify
        return

    manifest = _load_manifest(ee_dir)
    if manifest is None:
        msg = (
            f"headroom_ee integrity manifest not found at "
            f"{ee_dir / _MANIFEST_FILENAME}. "
            "Run `python scripts/build_ee_manifest.py` to regenerate."
        )
        if strict:
            raise IntegrityError(msg)
        logger.warning(msg)
        return

    # --- Signature verification ---
    secret = os.environ.get(_HMAC_SECRET_ENV, "").strip() or None
    if secret:
        if not _verify_manifest_signature(manifest, secret):
            msg = (
                "headroom_ee manifest signature INVALID — the manifest may "
                "have been tampered with. Refusing to load EE modules."
            )
            if strict:
                raise IntegrityError(msg)
            logger.error(msg)
            return
        logger.debug("EE manifest signature OK")
    else:
        logger.debug(
            "EE manifest signature not verified (%s not set) — "
            "hash-only integrity check active.",
            _HMAC_SECRET_ENV,
        )

    # --- File hash verification ---
    files: dict[str, str] = manifest.get("files", {})
    if not files:
        logger.warning("EE integrity manifest has no file entries — skipping hash check.")
        return

    failures: list[str] = []
    for rel_path, expected_hash in files.items():
        abs_path = ee_dir / rel_path
        if not abs_path.exists():
            failures.append(f"MISSING: {rel_path}")
            continue
        actual_hash = _sha256_file(abs_path)
        if not hmac.compare_digest(actual_hash, expected_hash):
            failures.append(
                f"MISMATCH: {rel_path} "
                f"(expected {expected_hash[:16]}…, got {actual_hash[:16]}…)"
            )

    if failures:
        detail = "\n  ".join(failures)
        msg = (
            f"headroom_ee integrity check failed — "
            f"{len(failures)} file(s) tampered or missing:\n  {detail}\n"
            "Refusing to load EE modules."
        )
        if strict:
            raise IntegrityError(msg)
        logger.error(msg)
        return

    logger.debug("EE integrity check passed (%d file(s) verified).", len(files))
