# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for residency proof signing/verification round-trip.

Audit-Deep-2026-06-21 Blocker 2: the in-process verify() method returned
False for a signature the prover itself just produced, because the signer
hashed the payload (SHA-256) but the verifier passed the payload raw.
This file pins the fix.
"""

from __future__ import annotations

import pytest

# Skip the entire module if cryptography is not installed in the venv
# (residency_proof uses Ed25519 from cryptography).
pytest.importorskip("cryptography")


def _make_test_keys(monkeypatch):
    """Set up an ephemeral Ed25519 keypair in env vars for the test."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    monkeypatch.setenv("CUTCTX_LICENSE_PRIVATE_KEY", priv_bytes.hex())
    monkeypatch.setenv("CUTCTX_LICENSE_PUBLIC_KEY", pub_bytes.hex())
    monkeypatch.setenv("CUTCTX_LICENSE_KID", "test-kid")
    return priv, pub_bytes


class TestResidencyVerify:
    """Pin the signer/verifier protocol to SHA-256(payload).digest()."""

    def test_sign_then_verify_round_trip(self, monkeypatch):
        """The prover's verify() must return True for a signature it just produced."""
        from cutctx.security.residency_proof import ResidencyProver

        _make_test_keys(monkeypatch)
        prover = ResidencyProver(tenant_id="tenant-test-1")
        attest = prover.generate(data_regions=["us-west-2"], sign=False)
        signed = prover._sign(attest)
        # Was False before the fix; must be True now.
        assert signed.signature_hex is not None
        assert prover.verify(signed) is True, (
            "In-process verify() returned False for a signature the prover "
            "itself just produced. This is the Blocker-2 bug."
        )

    def test_verify_rejects_tampered_signature(self, monkeypatch):
        """verify() must return False if the signature is tampered with."""
        from cutctx.security.residency_proof import ResidencyProver

        _make_test_keys(monkeypatch)
        prover = ResidencyProver(tenant_id="tenant-test-2")
        signed = prover._sign(prover.generate(data_regions=["us-east-1"], sign=False))
        # Flip a hex digit in the signature.
        sig = bytearray.fromhex(signed.signature_hex)
        sig[0] ^= 0x01
        signed.signature_hex = sig.hex()
        assert prover.verify(signed) is False

    def test_verify_rejects_tampered_payload(self, monkeypatch):
        """verify() must return False if the signed payload is altered."""
        from dataclasses import replace

        from cutctx.security.residency_proof import ResidencyProver

        _make_test_keys(monkeypatch)
        prover = ResidencyProver(tenant_id="tenant-test-3")
        signed = prover._sign(prover.generate(data_regions=["eu-west-1"], sign=False))
        # Change the data_regions field after signing.
        tampered = replace(signed, data_regions=["ap-southeast-1"])
        assert prover.verify(tampered) is False

    def test_verify_unsigned_attestation_returns_true(self, monkeypatch):
        """An attestation with no signature_hex is treated as unsigned, and verify()
        returns True (per docs: 'unsign mode is the default')."""
        from cutctx.security.residency_proof import ResidencyProver

        _make_test_keys(monkeypatch)
        prover = ResidencyProver(tenant_id="tenant-test-4")
        unsigned = prover.generate(data_regions=["us-west-2"], sign=False)
        assert unsigned.signature_hex is None
        assert prover.verify(unsigned) is True

    def test_verify_with_wrong_public_key(self, monkeypatch):
        """verify() must return False when the public key doesn't match the signer."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        from cutctx.security.residency_proof import ResidencyProver

        # Generate signer key
        priv_a = Ed25519PrivateKey.generate()
        priv_a_bytes = priv_a.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Generate a different public key for the verifier
        priv_b = Ed25519PrivateKey.generate()
        priv_b_bytes = priv_b.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_b_bytes = priv_b.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        # First sign with priv_a, then check verifier with priv_b's pub key
        # by manipulating the env temporarily.
        monkeypatch.setenv("CUTCTX_LICENSE_PRIVATE_KEY", priv_a_bytes.hex())
        monkeypatch.setenv(
            "CUTCTX_LICENSE_PUBLIC_KEY",
            priv_a.public_key()
            .public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            .hex(),
        )
        monkeypatch.setenv("CUTCTX_LICENSE_KID", "test-kid-a")
        prover_a = ResidencyProver(tenant_id="tenant-test-5")
        signed = prover_a._sign(prover_a.generate(data_regions=["us-west-2"], sign=False))

        # Now verify with a different public key
        monkeypatch.setenv("CUTCTX_LICENSE_PRIVATE_KEY", priv_b_bytes.hex())
        monkeypatch.setenv("CUTCTX_LICENSE_PUBLIC_KEY", pub_b_bytes.hex())
        monkeypatch.setenv("CUTCTX_LICENSE_KID", "test-kid-b")
        prover_b = ResidencyProver(tenant_id="tenant-test-5")
        assert prover_b.verify(signed) is False
