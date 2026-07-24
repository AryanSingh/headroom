# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.

"""PitchToShip license validation client.

Optional integration — Cutctx works WITHOUT PitchToShip.
When PITCHTOSHIP_URL is set, license validation, trial, and seat
management are delegated to PitchToShip's centralized API.

Security model:
  1. Online:  PitchToShip verifies license in DB, returns ECDSA-signed token
  2. Offline: Cutctx verifies cached signed token using PitchToShip's public key
  3. Tamper:  Signature verification fails → fail closed (deny access)
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("cutctx.pitchtoship")

PITCHTOSHIP_URL = os.environ.get("PITCHTOSHIP_URL")  # e.g. http://localhost:3001
_HOSTED_LICENSE_URL = os.environ.get(
    "CUTCTX_LICENSE_SUPABASE_URL", "https://udeekuvifncmqvoywhlg.supabase.co"
).rstrip("/")
# Supabase anon keys identify the public project API and are intentionally safe
# to distribute with browser and runtime clients. This must never be replaced
# with a service-role key.
_HOSTED_LICENSE_ANON_KEY = os.environ.get(
    "CUTCTX_LICENSE_SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVkZWVrdXZpZm5jbXF2b3l3aGxnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ3OTQ3NjUsImV4cCI6MjEwMDM3MDc2NX0.Jhg4l0uf1ccwT-2Om3Ae3HOjy9SaCvX6EHnZ1FGhRGA",
)
_CACHE_DIR = Path.home() / ".cutctx" / "pts_cache"
_PUBLIC_KEY_CACHE = _CACHE_DIR / "pitchtoship_public.pem"
_SIGNED_TOKEN_CACHE = _CACHE_DIR / "signed_token_cache.json"
_PUBLIC_KEY_TTL = 86400  # Re-fetch public key every 24 hours

# --- Cache Encryption ---
_CACHE_SALT = b"cutctx-pitchtoship-cache-v1"


_MACHINE_ID_FILE = _CACHE_DIR / ".machine-id"


def _get_machine_id() -> str:
    """Get or generate a persistent machine identifier (high-entropy)."""
    if _MACHINE_ID_FILE.exists():
        try:
            return _MACHINE_ID_FILE.read_text().strip()
        except OSError:
            pass
    # Generate and persist a random UUID
    import uuid

    mid = str(uuid.uuid4())
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _MACHINE_ID_FILE.write_text(mid)
        _MACHINE_ID_FILE.chmod(0o600)
    except OSError:
        pass
    return mid


def _get_cache_key() -> bytes:
    """Generate a machine-specific encryption key for cache files."""
    import hashlib

    machine_id = _get_machine_id().encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", machine_id, _CACHE_SALT, 100000)


def _encrypt_cache(data: str) -> bytes:
    """Encrypt cache data with Fernet (AES-128-CBC + HMAC)."""
    try:
        from cryptography.fernet import Fernet

        key = base64.urlsafe_b64encode(_get_cache_key())
        return Fernet(key).encrypt(data.encode("utf-8"))
    except ImportError:
        # Fallback: write plaintext if cryptography not available
        return data.encode("utf-8")


def _decrypt_cache(data: bytes) -> str | None:
    """Decrypt cache data. Returns None on failure."""
    try:
        from cryptography.fernet import Fernet

        key = base64.urlsafe_b64encode(_get_cache_key())
        return Fernet(key).decrypt(data, ttl=_PUBLIC_KEY_TTL + 3600).decode("utf-8")
    except ImportError:
        return data.decode("utf-8")
    except Exception:
        return None


def _b64url_decode(data: str) -> bytes:
    """Decode base64url-encoded data."""
    # Add padding if needed
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def is_configured() -> bool:
    """Return True if PitchToShip integration is enabled."""
    return bool(PITCHTOSHIP_URL)


def _is_hosted_cutctx_key(license_key: str) -> bool:
    """Return whether a key was issued by the hosted CutCtx portal."""
    return license_key.startswith("cutctx_")


def _post_hosted_license(endpoint: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Call a public Supabase license Edge Function.

    A client-side (4xx) response is returned as a definitive response so the
    caller can deny access. A server error or network failure returns ``None``
    and therefore permits the existing offline validation fallback.
    """
    try:
        payload = json.dumps(data).encode("utf-8")
        req = Request(
            f"{_HOSTED_LICENSE_URL}/functions/v1/{endpoint}",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "apikey": _HOSTED_LICENSE_ANON_KEY,
            },
            method="POST",
        )
        with urlopen(req, timeout=5.0) as response:
            body = json.loads(response.read().decode("utf-8"))
            return body if isinstance(body, dict) else None
    except HTTPError as exc:
        if exc.code >= 500:
            logger.warning("Hosted license service returned HTTP %s", exc.code)
            return None
        try:
            body = json.loads(exc.read().decode("utf-8"))
            return body if isinstance(body, dict) else {"valid": False}
        except Exception:
            return {"valid": False}
    except (URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Hosted license service unavailable: %s", exc)
        return None


def _post(endpoint: str, data: dict[str, Any], timeout: float = 5.0) -> dict[str, Any] | None:
    """POST JSON to PitchToShip. Returns parsed response or None on failure."""
    if not is_configured():
        return None
    try:
        payload = json.dumps(data).encode("utf-8")
        url = f"{PITCHTOSHIP_URL}{endpoint}"
        req = Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        logger.warning("PitchToShip unreachable at %s%s: %s", PITCHTOSHIP_URL, endpoint, e.reason)
        return None
    except Exception as e:
        logger.warning("PitchToShip request failed: %s", e)
        return None


def _get(endpoint: str, timeout: float = 5.0) -> dict[str, Any] | None:
    """GET JSON from PitchToShip. Returns parsed response or None on failure."""
    if not is_configured():
        return None
    try:
        url = f"{PITCHTOSHIP_URL}{endpoint}"
        req = Request(url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        logger.warning("PitchToShip unreachable at %s%s: %s", PITCHTOSHIP_URL, endpoint, e.reason)
        return None
    except Exception as e:
        logger.warning("PitchToShip request failed: %s", e)
        return None


# --- ECDSA Public Key Management ---


def _fetch_public_key() -> str | None:
    """Fetch ECDSA P-256 public key from PitchToShip, with local cache."""
    # Check encrypted cache first
    if _PUBLIC_KEY_CACHE.exists():
        try:
            raw = _PUBLIC_KEY_CACHE.read_bytes()
            decrypted = _decrypt_cache(raw)
            if decrypted:
                cache_data = json.loads(decrypted)
                if time.time() - cache_data.get("fetched_at", 0) < _PUBLIC_KEY_TTL:
                    return cache_data["public_key"]
        except (json.JSONDecodeError, KeyError):
            pass

    # Fetch from server
    result = _get("/api/licenses/public-key")
    if result and result.get("public_key"):
        public_key = result["public_key"]
        # Cache to disk (encrypted)
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            plaintext = json.dumps(
                {
                    "public_key": public_key,
                    "fetched_at": time.time(),
                }
            )
            _PUBLIC_KEY_CACHE.write_bytes(_encrypt_cache(plaintext))
            logger.info("PitchToShip public key cached (encrypted) to %s", _PUBLIC_KEY_CACHE)
        except OSError as e:
            logger.warning("Failed to cache public key: %s", e)
        return public_key

    return None


def _get_cached_public_key() -> str | None:
    """Get public key — try cache first, then fetch."""
    key = _fetch_public_key()
    if key:
        return key

    # If fetch failed, try stale encrypted cache
    if _PUBLIC_KEY_CACHE.exists():
        try:
            raw = _PUBLIC_KEY_CACHE.read_bytes()
            decrypted = _decrypt_cache(raw)
            if decrypted:
                cache_data = json.loads(decrypted)
                logger.warning("Using stale PitchToShip public key cache")
                return cache_data.get("public_key")
        except (json.JSONDecodeError, KeyError):
            pass

    return None


# --- Signed Token Verification ---


def verify_signed_token(signed_token: str, public_key_pem: str) -> dict[str, Any] | None:
    """Verify an ECDSA P-256 signed token from PitchToShip.

    Token format: pts1.{payload_b64url}.{sig_b64url}
    Signature is over ASCII bytes of "pts1.{payload_b64url}".

    Returns the payload dict if valid, None if invalid.
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric.ec import ECDSA
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except ImportError:
        logger.error("cryptography library not available — cannot verify signed tokens")
        return None

    parts = signed_token.split(".")
    if len(parts) != 3 or parts[0] != "pts1":
        logger.warning("Invalid signed token format (expected pts1.{payload}.{sig})")
        return None

    header_b64, payload_b64, sig_b64 = parts
    signed_data = f"{header_b64}.{payload_b64}".encode("ascii")

    try:
        # Decode the raw (r||s) signature (64 bytes: 32 r + 32 s)
        sig_raw = _b64url_decode(sig_b64)
        if len(sig_raw) != 64:
            logger.warning("Invalid signature length: %d bytes (expected 64)", len(sig_raw))
            return None

        r = int.from_bytes(sig_raw[:32], "big")
        s = int.from_bytes(sig_raw[32:], "big")

        # Reconstruct DER-encoded signature for the cryptography library
        def _int_to_der_bytes(n: int) -> bytes:
            n_bytes = n.to_bytes(32, "big")
            # Strip leading zeros
            n_bytes = n_bytes.lstrip(b"\x00") or b"\x00"
            # ASN.1 INTEGER is signed. Prefix positive values whose high bit
            # is set so cryptography does not interpret them as negative.
            if n_bytes[0] & 0x80:
                n_bytes = b"\x00" + n_bytes
            return b"\x02" + bytes([len(n_bytes)]) + n_bytes

        r_der = _int_to_der_bytes(r)
        s_der = _int_to_der_bytes(s)
        der_sig = b"\x30" + bytes([len(r_der) + len(s_der)]) + r_der + s_der

        # Load public key and verify
        public_key = load_pem_public_key(public_key_pem.encode("ascii"))
        public_key.verify(der_sig, signed_data, ECDSA(hashes.SHA256()))

        # Signature valid — decode and return payload
        payload_bytes = _b64url_decode(payload_b64)
        return json.loads(payload_bytes.decode("utf-8"))

    except InvalidSignature:
        logger.warning("ECDSA signature verification failed — token may have been tampered with")
        return None
    except Exception as e:
        logger.warning("Signed token verification error: %s", e)
        return None


def _cache_signed_token(signed_token: str, license_key: str) -> None:
    """Cache a signed token for offline verification (encrypted on disk)."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache = {}
        if _SIGNED_TOKEN_CACHE.exists():
            try:
                raw = _SIGNED_TOKEN_CACHE.read_bytes()
                decrypted = _decrypt_cache(raw)
                if decrypted:
                    cache = json.loads(decrypted)
            except (json.JSONDecodeError, KeyError):
                cache = {}
        cache[license_key] = {
            "signed_token": signed_token,
            "cached_at": time.time(),
        }
        plaintext = json.dumps(cache)
        _SIGNED_TOKEN_CACHE.write_bytes(_encrypt_cache(plaintext))
    except OSError as e:
        logger.warning("Failed to cache signed token: %s", e)


def _get_cached_signed_token(license_key: str) -> str | None:
    """Retrieve a cached signed token for offline verification (encrypted on disk)."""
    if not _SIGNED_TOKEN_CACHE.exists():
        return None
    try:
        raw = _SIGNED_TOKEN_CACHE.read_bytes()
        decrypted = _decrypt_cache(raw)
        if not decrypted:
            return None
        cache = json.loads(decrypted)
        entry = cache.get(license_key)
        if entry and entry.get("signed_token"):
            return entry["signed_token"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None


# --- Public API ---


def verify_license(license_key: str, hwid: str) -> dict[str, Any] | None:
    """Verify license against PitchToShip.

    When online: calls PitchToShip API, caches the signed token for offline use.
    When offline: verifies the cached signed token using ECDSA public key.
    Returns None if verification fails (fail closed).
    """
    if _is_hosted_cutctx_key(license_key):
        hosted = _post_hosted_license("verify-license", {"key": license_key})
        if hosted is not None:
            if not hosted.get("valid"):
                return {"valid": False}
            return {
                "valid": True,
                "tier": hosted.get("tier"),
                "seats": hosted.get("seatsLimit"),
                "expires_at": hosted.get("expiresAt"),
            }

    # Legacy online verification remains for pre-hosted licenses.
    result = _post("/api/licenses/verify", {"license_key": license_key, "hwid": hwid})
    if result and result.get("valid"):
        # Cache the signed token for offline use
        signed_token = result.get("signed_token")
        if signed_token:
            _cache_signed_token(signed_token, license_key)
            # Prime the public-key cache while the service is reachable. Without
            # this, a first successful online activation cannot be verified when
            # the next validation happens offline.
            _fetch_public_key()
        return result

    # PitchToShip unreachable or returned invalid — try offline verification
    logger.info(
        "PitchToShip offline, attempting offline ECDSA verification for key=%s", license_key[:8]
    )
    signed_token = _get_cached_signed_token(license_key)
    if signed_token:
        public_key = _get_cached_public_key()
        if public_key:
            payload = verify_signed_token(signed_token, public_key)
            if payload:
                # Verify the token hasn't expired
                exp = payload.get("expires_at")
                if exp:
                    from datetime import datetime

                    if isinstance(exp, str):
                        exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                        if exp_dt.timestamp() < time.time():
                            logger.warning("Cached signed token expired")
                            return None
                logger.info(
                    "Offline ECDSA verification succeeded for key=%s, tier=%s",
                    license_key[:8],
                    payload.get("tier"),
                )
                return {
                    "valid": True,
                    "tier": payload.get("tier"),
                    "features": payload.get("features"),
                    "expires_at": payload.get("expires_at"),
                    "offline_verified": True,
                }
        else:
            logger.warning("No public key available for offline verification")

    return None


def issue_trial(hwid: str, product: str = "cutctx") -> dict[str, Any] | None:
    """Request trial token from PitchToShip."""
    return _post("/api/trials/issue", {"hwid": hwid, "product": product})


def verify_trial_token(token: str) -> dict[str, Any] | None:
    """Verify a trial token issued by PitchToShip."""
    result = _post("/api/trials/verify", {"token": token})
    if result and result.get("valid"):
        return result
    return None


def heartbeat_seat(license_key: str, hwid: str) -> dict[str, Any] | None:
    """Send seat heartbeat to PitchToShip."""
    if _is_hosted_cutctx_key(license_key):
        return _post_hosted_license("seat-heartbeat", {"key": license_key, "hwid": hwid})
    return _post("/api/seats/heartbeat", {"license_key": license_key, "hwid": hwid})
