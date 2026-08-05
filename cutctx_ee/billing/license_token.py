# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Minting **and verification** of Cutctx licence artefacts.

Two signed formats exist and both are verified here:

``hrk1.{kid}.{payload_b64url}.{sig_b64url}``
    Ed25519 entitlement token. Minted by :func:`sign_license`, verified by
    :func:`verify_license_token` against a pinned public-key trust store.

``{prefix}{payload_b64url}.{hmac_hex}``
    HMAC-SHA256 licence key minted by ``cutctx license generate``
    (``bld-``/``team-``/``biz-``/``ent-``), verified by
    :func:`verify_hmac_license_key` with ``CUTCTX_LICENSE_HMAC_SECRET``.

Audit-2026-08-03 C3.1: neither format had a verifier, so the only input to
the entitlement decision was an HTTP body from whatever host
``CUTCTX_LICENSE_API_URL`` happened to point at. :func:`verified_tier` is the
local, offline oracle that decision now has to consult.
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ed25519

#: Env var holding extra Ed25519 trust anchors: ``kid=hexpubkey[,kid=hex…]``.
#: Lets a self-hosted / air-gapped deployment issue its own signed licences
#: without weakening the default (see :func:`load_trust_store`).
_TRUST_STORE_ENV = "CUTCTX_LICENSE_PUBLIC_KEYS"
_HMAC_SECRET_ENV = "CUTCTX_LICENSE_HMAC_SECRET"

#: Built-in Ed25519 trust anchors shipped with the release (kid -> pubkey hex).
#: Populated at packaging time by the release signing job.
BUILTIN_PUBLIC_KEYS: dict[str, str] = {}

#: Origins the vendor actually operates. A validation response from one of
#: these over HTTPS is authoritative even without a per-response signature;
#: a response from anywhere else is not (C3.1 — the env override stays usable
#: but only signed answers from it count).
PINNED_LICENSE_ORIGINS: frozenset[str] = frozenset(
    {
        "udeekuvifncmqvoywhlg.supabase.co",
        "pitchtoship.com",
        "www.pitchtoship.com",
    }
)

_TIER_RANK: dict[str, int] = {
    "builder": 0,
    "oss": 0,
    "free": 0,
    "team": 1,
    "business": 2,
    "enterprise": 3,
    "enterprise_plus": 3,
}

_PREFIX_TIERS: dict[str, str] = {
    "bld-": "builder",
    "team-": "team",
    "biz-": "business",
    "ent-": "enterprise",
}

#: Tolerated clock skew (seconds) when checking ``nbf``/``exp``.
_CLOCK_SKEW = 300


class LicenseSignatureError(ValueError):
    """Raised when a licence artefact carries no verifiable signature."""


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(text + padding)
    except (binascii.Error, ValueError) as exc:
        raise LicenseSignatureError(f"malformed base64url segment: {exc}") from exc


def sign_license(
    tier: str,
    kid: str,
    private_key_hex: str,
    extra_payload: dict[str, Any] | None = None,
    duration_days: int = 365,
) -> str:
    """
    Generate an hrk1 signed token using Ed25519.
    Format: hrk1.{kid}.{payload_b64url}.{sig_b64url}
    """
    import time

    try:
        priv_bytes = bytes.fromhex(private_key_hex)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(priv_bytes)
    except Exception as e:
        raise ValueError(f"Invalid private key hex: {e}") from e

    payload = {
        "tier": tier,
        "nbf": int(time.time()) - 300,  # 5 min clock skew
        "exp": int(time.time()) + (duration_days * 86400),
    }
    if extra_payload:
        payload.update(extra_payload)

    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = b64url_encode(payload_json.encode("utf-8"))

    signed_message = f"hrk1.{kid}.{payload_b64}".encode()
    signature = private_key.sign(signed_message)
    sig_b64 = b64url_encode(signature)

    return f"{signed_message.decode('ascii')}.{sig_b64}"


def get_default_issuer_config():
    """Retrieve the configured Ed25519 Key ID and Private Key (hex) from env."""
    kid = os.environ.get("CUTCTX_LICENSE_KID")
    priv_hex = os.environ.get("CUTCTX_LICENSE_PRIVATE_KEY")
    return kid, priv_hex


# ---------------------------------------------------------------------------
# Verification (C3.1)
# ---------------------------------------------------------------------------


def load_trust_store() -> dict[str, str]:
    """Return the Ed25519 trust anchors: ``kid`` -> public key hex.

    Built-in release anchors, plus any supplied via ``CUTCTX_LICENSE_PUBLIC_KEYS``
    as ``kid=hexpubkey`` pairs. Operator-supplied anchors are how an air-gapped
    or self-hosted deployment issues its own licences — adding a *public* key is
    a deliberate act by the machine owner, unlike redirecting an HTTP URL.
    """
    store = dict(BUILTIN_PUBLIC_KEYS)
    raw = os.environ.get(_TRUST_STORE_ENV, "").strip()
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        kid, _, pub_hex = entry.partition("=")
        kid, pub_hex = kid.strip(), pub_hex.strip()
        if kid and pub_hex:
            store[kid] = pub_hex
    return store


def verify_license_token(token: str, now: float | None = None) -> dict[str, Any]:
    """Verify an ``hrk1`` Ed25519 token and return its claims.

    Raises :class:`LicenseSignatureError` if the format, key id, signature, or
    validity window is not acceptable. Never returns unverified claims.
    """
    parts = token.split(".")
    if len(parts) != 4 or parts[0] != "hrk1":
        raise LicenseSignatureError("not an hrk1 token")
    _, kid, payload_b64, sig_b64 = parts

    trust_store = load_trust_store()
    pub_hex = trust_store.get(kid)
    if not pub_hex:
        raise LicenseSignatureError(f"unknown key id {kid!r} — not in the trust store")
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
    except (ValueError, TypeError) as exc:
        raise LicenseSignatureError(f"trust store entry for {kid!r} is not a valid key") from exc

    signed_message = f"hrk1.{kid}.{payload_b64}".encode()
    try:
        public_key.verify(b64url_decode(sig_b64), signed_message)
    except LicenseSignatureError:
        raise
    except Exception as exc:  # cryptography raises InvalidSignature
        raise LicenseSignatureError("signature does not verify") from exc

    try:
        claims = json.loads(b64url_decode(payload_b64))
    except (json.JSONDecodeError, ValueError) as exc:
        raise LicenseSignatureError("payload is not JSON") from exc
    if not isinstance(claims, dict):
        raise LicenseSignatureError("payload is not a JSON object")

    _check_validity_window(claims, now)
    return claims


def verify_hmac_license_key(license_key: str, secret: str | None = None) -> dict[str, Any]:
    """Verify a ``cutctx license generate`` HMAC key and return its claims.

    Format: ``{prefix}{payload_b64url}.{hmac_sha256_hex}``. The returned dict
    carries the decoded payload plus a ``tier`` derived from the prefix.
    """
    if secret is None:
        secret = os.environ.get(_HMAC_SECRET_ENV, "").strip() or None
    if not secret:
        raise LicenseSignatureError(f"{_HMAC_SECRET_ENV} is not set — cannot verify HMAC keys")

    prefix = next((p for p in _PREFIX_TIERS if license_key.startswith(p)), None)
    if prefix is None:
        raise LicenseSignatureError("not a cutctx-minted HMAC licence key")
    unsigned_key, sep, provided_sig = license_key.rpartition(".")
    if not sep or not provided_sig:
        raise LicenseSignatureError("licence key carries no signature")

    expected = hmac.new(secret.encode("utf-8"), unsigned_key.encode("utf-8"), hashlib.sha256)
    if not hmac.compare_digest(expected.hexdigest(), provided_sig):
        raise LicenseSignatureError("licence key signature does not verify")

    try:
        claims = json.loads(b64url_decode(unsigned_key[len(prefix) :]))
    except (json.JSONDecodeError, ValueError) as exc:
        raise LicenseSignatureError("licence key payload is not JSON") from exc
    if not isinstance(claims, dict):
        raise LicenseSignatureError("licence key payload is not a JSON object")

    claims.setdefault("tier", _PREFIX_TIERS[prefix])
    _check_validity_window(claims, None)
    return claims


def _check_validity_window(claims: Mapping[str, Any], now: float | None) -> None:
    """Reject claims outside their ``nbf``/``exp``/``expiry`` window."""
    current = time.time() if now is None else now
    nbf = claims.get("nbf")
    if isinstance(nbf, int | float) and current + _CLOCK_SKEW < nbf:
        raise LicenseSignatureError("licence is not valid yet")
    exp = claims.get("exp")
    if isinstance(exp, int | float) and current - _CLOCK_SKEW > exp:
        raise LicenseSignatureError("licence has expired")
    expiry = claims.get("expiry")
    if isinstance(expiry, str) and expiry:
        from datetime import datetime, timezone

        try:
            parsed = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        except ValueError as exc:
            raise LicenseSignatureError(f"malformed expiry {expiry!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed.timestamp() + _CLOCK_SKEW < current:
            raise LicenseSignatureError("licence has expired")


def tier_rank(tier: str | None) -> int:
    """Return the numeric rank of a tier string (unknown -> builder)."""
    return _TIER_RANK.get((tier or "").lower().strip(), 0)


def is_pinned_license_origin(api_url: str | None) -> bool:
    """Return True when ``api_url`` is a vendor-operated HTTPS origin.

    ``CUTCTX_LICENSE_API_URL`` is deliberately still honoured — self-hosted and
    air-gapped deployments need it — but redirecting it no longer *grants*
    anything on its own: an off-pin origin has to prove the entitlement with a
    signature (see :func:`authoritative_tier`).
    """
    if not api_url:
        return False
    parts = urlsplit(api_url)
    return parts.scheme == "https" and parts.hostname in PINNED_LICENSE_ORIGINS


def verified_tier(
    license_key: str | None,
    response: Mapping[str, Any] | None = None,
) -> str | None:
    """Return the tier a locally verifiable signature proves, else ``None``.

    Checked in order:

    1. A signed ``hrk1`` entitlement token carried in the validation response
       (``license_token`` / ``entitlement_token`` / ``signed_tier``).
    2. The licence key itself, when it is an ``hrk1`` token or a
       ``cutctx license generate`` HMAC key.

    ``None`` means "nothing here is signed" — the caller must not grant a paid
    tier on that basis alone.
    """
    if response:
        for field in ("license_token", "entitlement_token", "signed_tier"):
            token = response.get(field)
            if not isinstance(token, str) or not token.startswith("hrk1."):
                continue
            try:
                claims = verify_license_token(token)
            except LicenseSignatureError:
                continue
            if not _key_binding_ok(claims, license_key):
                continue
            tier = claims.get("tier")
            if isinstance(tier, str) and tier:
                return tier

    if isinstance(license_key, str) and license_key:
        try:
            if license_key.startswith("hrk1."):
                claims = verify_license_token(license_key)
            else:
                claims = verify_hmac_license_key(license_key)
        except LicenseSignatureError:
            return None
        tier = claims.get("tier")
        if isinstance(tier, str) and tier:
            return tier
    return None


def _key_binding_ok(claims: Mapping[str, Any], license_key: str | None) -> bool:
    """A token that names a licence key must be presented with that key."""
    bound = claims.get("key_sha256")
    if not isinstance(bound, str) or not bound:
        return True
    if not license_key:
        return False
    return hmac.compare_digest(hashlib.sha256(license_key.encode()).hexdigest(), bound)


def authoritative_tier(
    claimed_tier: str | None,
    license_key: str | None,
    api_url: str | None,
    response: Mapping[str, Any] | None = None,
) -> str | None:
    """Clamp a licence-API tier claim to what is actually provable.

    Returns the tier that may be applied, or ``None`` for "no paid entitlement".

    * A signature (response token or signed key) is authoritative, and the
      response may still *downgrade* below it — never above it.
    * With no signature, the claim counts only when it came from a pinned
      vendor HTTPS origin. That is what stops
      ``CUTCTX_LICENSE_API_URL=http://attacker/`` returning
      ``{"valid": true, "tier": "enterprise"}`` from granting anything.
    """
    if not claimed_tier or tier_rank(claimed_tier) == 0:
        return None

    proven = verified_tier(license_key, response)
    if proven is not None:
        return claimed_tier if tier_rank(claimed_tier) <= tier_rank(proven) else proven
    if is_pinned_license_origin(api_url):
        return claimed_tier
    return None
