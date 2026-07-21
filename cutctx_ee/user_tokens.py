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
