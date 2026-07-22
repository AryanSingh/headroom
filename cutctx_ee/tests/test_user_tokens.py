from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from cutctx_ee.user_tokens import UserTokenError, verify_user_token


def _token(payload: dict, secret: str = "secret") -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    signed = f"ctu1.{encoded}"
    return f"{signed}.{hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()}"


def test_user_token_requires_valid_signature_license_and_expiry() -> None:
    token = _token({"sub": "user-1", "license_key": "license-1", "exp": time.time() + 60})
    assert verify_user_token(token, "secret", "license-1") == "user-1"
    with pytest.raises(UserTokenError):
        verify_user_token(token, "secret", "license-2")


def test_user_token_rejects_invalid_signature() -> None:
    token = _token({"sub": "user-1", "license_key": "license-1", "exp": time.time() + 60})
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")

    with pytest.raises(UserTokenError, match="invalid token signature"):
        verify_user_token(tampered, "secret", "license-1")


@pytest.mark.parametrize(
    "payload",
    [
        {"license_key": "license-1", "exp": time.time() + 60},
        {"sub": "user-1", "license_key": "license-1", "exp": time.time() - 1},
    ],
)
def test_user_token_rejects_missing_subject_or_expired_payload(payload: dict) -> None:
    with pytest.raises(UserTokenError):
        verify_user_token(_token(payload), "secret", "license-1")


def test_user_token_rejects_malformed_input() -> None:
    with pytest.raises(UserTokenError, match="malformed token"):
        verify_user_token("not-a-token", "secret", "license-1")
# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.
