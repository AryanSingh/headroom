from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from cutctx_ee.billing import pitchtoship_client as client


def test_online_verification_caches_the_public_key_for_first_offline_use(monkeypatch):
    monkeypatch.setattr(
        client,
        "_post",
        lambda *_args, **_kwargs: {
            "valid": True,
            "tier": "builder",
            "features": ["core_compression"],
            "signed_token": "pts1.payload.signature",
        },
    )
    fetched = []
    monkeypatch.setattr(client, "_fetch_public_key", lambda: fetched.append(True) or "public-key")
    monkeypatch.setattr(client, "_cache_signed_token", lambda *_args: None)

    result = client.verify_license("PTS-TEST-CUTCTX", "machine-1")

    assert result and result["valid"] is True
    assert fetched == [True]


def test_verify_signed_token_accepts_a_signature_with_high_bit_der_integer():
    private_key = ec.generate_private_key(ec.SECP256R1())
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps({"tier": "builder"}).encode("utf-8"))
        .rstrip(b"=")
        .decode("ascii")
    )
    signed_data = f"pts1.{payload_b64}".encode("ascii")

    for _ in range(256):
        der_signature = private_key.sign(signed_data, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der_signature)
        raw_signature = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        if raw_signature[0] & 0x80 or raw_signature[32] & 0x80:
            break
    else:
        raise AssertionError("could not produce a high-bit ECDSA integer")

    signature_b64 = base64.urlsafe_b64encode(raw_signature).rstrip(b"=").decode("ascii")
    token = f"pts1.{payload_b64}.{signature_b64}"
    pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    assert client.verify_signed_token(token, pem) == {"tier": "builder"}
# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.
