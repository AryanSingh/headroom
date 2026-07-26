# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
"""Verification for Cutctx user-scoped provider tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


class UserTokenError(ValueError):
    pass


#: Default lifetime. Long enough to cover a working session without
#: re-issuing mid-run, short enough that a leaked token expires on its own.
DEFAULT_TTL_SECONDS = 12 * 60 * 60


def issue_user_token(
    subject: str,
    secret: str,
    license_key: str,
    *,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
) -> str:
    """Mint a token that :func:`verify_user_token` will accept.

    The verifier shipped without a counterpart, so every paid deployment had
    a gate that no client could satisfy: nothing produced this header and
    ``cutctx wrap`` never sent one. This is that missing half.

    The payload binds three things the verifier re-checks: ``sub`` (the seat
    subject), ``license_key`` (so a token minted for one organization cannot
    consume another's seats), and ``exp``.

    Args:
        subject: Stable identity the seat is leased to. The proxy sends this
            to the seat service, so it should be per-user rather than
            per-process — otherwise one user burns a seat per session.
        secret: Shared HMAC secret; see
            :mod:`cutctx.auth.user_token_secret`.
        license_key: Licence the token is scoped to.
        ttl_seconds: Lifetime from now.

    Raises:
        UserTokenError: on empty subject, secret, or licence — all three are
            required for the token to verify, and failing here beats minting
            something that is rejected later for no obvious reason.
    """
    if not subject:
        raise UserTokenError("token subject is required")
    if not secret:
        raise UserTokenError("signing secret is required")
    if not license_key:
        raise UserTokenError("license key is required")

    payload = {
        "sub": subject,
        "license_key": license_key,
        "exp": int(time.time() + ttl_seconds),
    }
    # Separators keep the encoding compact and stable; the verifier only
    # parses JSON, so exact bytes do not matter beyond signing over them.
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    signed = f"ctu1.{payload_b64}".encode()
    signature = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"ctu1.{payload_b64}.{signature}"


def verify_user_token(token: str, secret: str, license_key: str) -> str:
    """Return the signed user subject or raise for malformed/expired tokens.

    Format: ``ctu1.<base64url-json>.<hmac-sha256-hex>``. The payload must
    bind the user to the configured license, preventing a token issued to one
    organization from consuming another organization's seats.
    """
    try:
        version, payload_b64, signature = token.split(".")
        if version != "ctu1":
            raise UserTokenError("unsupported token version")
        signed = f"{version}.{payload_b64}".encode()
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise UserTokenError("invalid token signature")
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise UserTokenError("token subject is missing")
        if payload.get("license_key") != license_key:
            raise UserTokenError("token is not issued for this license")
        if not isinstance(payload.get("exp"), int | float) or payload["exp"] <= time.time():
            raise UserTokenError("token is expired")
        return subject
    except UserTokenError:
        raise
    except Exception as exc:
        raise UserTokenError("malformed token") from exc
