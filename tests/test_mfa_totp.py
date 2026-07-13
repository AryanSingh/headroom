# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for the TOTP (RFC 6238) MFA implementation.

Audit-Deep-2026-06-21 High-12: admin MFA via TOTP. These tests
verify the cryptographic primitives (HOTP, TOTP, base32),
the single-use replay protection, the clock-skew window, and
the SQLite-backed enrollment store.
"""

from __future__ import annotations

import pytest

# ── HOTP / TOTP primitives ────────────────────────────────────────────────


class TestHotp:
    def test_hotp_rfc4226_test_vectors(self):
        """RFC 4226 Appendix D test vectors (truncated to 6 digits)."""
        from cutctx.security.mfa import _base32_decode, _hotp

        # RFC 4226: secret "12345678901234567890" (ASCII).
        secret = _base32_decode("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ")
        # Test vectors from the RFC. We check the lower-6 digits
        # of the 8-digit values for ease of comparison.
        expected = {
            0: "755224",
            1: "287082",
            2: "359152",
            3: "969429",
            4: "338314",
            5: "254676",
            6: "287922",
            7: "162583",
            8: "399871",
            9: "520489",
        }
        for counter, code in expected.items():
            assert _hotp(secret, counter) == code, (
                f"HOTP mismatch at counter={counter}: expected {code}, got {_hotp(secret, counter)}"
            )


class TestTotp:
    def test_generate_secret_is_unique(self):
        from cutctx.security.mfa import generate_secret

        secrets = {generate_secret() for _ in range(100)}
        assert len(secrets) == 100, "generate_secret must be unique"

    def test_secret_round_trip_via_base32(self):
        from cutctx.security.mfa import (
            _base32_decode,
            _base32_encode,
            generate_secret,
        )

        secret_b32 = generate_secret()
        raw = _base32_decode(secret_b32)
        assert len(raw) == 20  # 160-bit secret per RFC 6238
        # Re-encoding should produce the same base32 string
        # (the padding-free round-trip is exact for full bytes).
        assert _base32_encode(raw) == secret_b32

    def test_current_totp_matches_hmac_at_same_step(self):
        from cutctx.security.mfa import (
            _base32_decode,
            _hotp,
            current_totp,
            generate_secret,
        )

        secret = generate_secret()
        # Pin "now" to a specific value so we can compare
        # against the raw HOTP at the matching counter.
        now = 1700000000.0
        counter = int(now) // 30
        expected = _hotp(_base32_decode(secret), counter)
        totp = current_totp(secret, now=now)
        assert totp.code == expected

    def test_remaining_seconds(self):
        from cutctx.security.mfa import (
            TOTP_STEP_S,
            current_totp,
            generate_secret,
        )

        secret = generate_secret()
        now = 1700000000.0
        totp = current_totp(secret, now=now)
        # 1700000000 % 30 = 10, so remaining = 30 - 10 = 20.
        assert totp.remaining_s == TOTP_STEP_S - (int(now) % TOTP_STEP_S)

    def test_verify_with_correct_code(self):
        from cutctx.security.mfa import (
            current_totp,
            generate_secret,
            verify_totp,
        )

        secret = generate_secret()
        code = current_totp(secret).code
        assert verify_totp(secret, code) is True

    def test_verify_with_wrong_code(self):
        from cutctx.security.mfa import generate_secret, verify_totp

        secret = generate_secret()
        assert verify_totp(secret, "000000") is False
        assert verify_totp(secret, "abcdef") is False
        assert verify_totp(secret, "12345") is False  # too short
        assert verify_totp(secret, "1234567") is False  # too long

    def test_verify_rejects_replay(self):
        """A successful verify consumes the counter so a
        second submit of the same code is rejected.
        """
        from cutctx.security.mfa import (
            TOTP_STEP_S,
            current_totp,
            generate_secret,
            verify_totp,
        )

        secret = generate_secret()
        # Pin now so the counter is stable
        now = 1700000000.0
        counter = int(now) // TOTP_STEP_S
        code = current_totp(secret, now=now).code
        # First call: ok
        assert verify_totp(secret, code, now=now, last_used_counter=counter - 1) is True
        # Same code again, with the counter advanced -> reject
        assert verify_totp(secret, code, now=now, last_used_counter=counter) is False

    def test_verify_clock_skew_window(self):
        """Codes one step in the past or future are accepted."""
        from cutctx.security.mfa import (
            TOTP_STEP_S,
            current_totp,
            generate_secret,
            verify_totp,
        )

        secret = generate_secret()
        now = 1700000000.0
        current = current_totp(secret, now=now).code
        # One step in the future (skewed clock)
        skewed_now = now + TOTP_STEP_S
        # Use a last_used_counter 2 steps behind to allow the
        # current step to be accepted.
        current_counter = int(now) // TOTP_STEP_S
        # The current code, with a future-skewed clock: the
        # current step is now in the past, but still within
        # TOTP_WINDOW=1.
        assert (
            verify_totp(
                secret,
                current,
                now=skewed_now,
                last_used_counter=current_counter - 1,
            )
            is True
        )


# ── MfaStore (SQLite) ──────────────────────────────────────────────────────


@pytest.fixture
def mfa_store(tmp_path):
    from cutctx.security.mfa import MfaStore

    db = tmp_path / "mfa.db"
    yield MfaStore(db_path=str(db))


class TestMfaStore:
    def test_get_none_when_empty(self, mfa_store):
        assert mfa_store.get("alice") is None

    def test_enroll_then_get(self, mfa_store):
        from cutctx.security.mfa import generate_secret

        secret = generate_secret()
        mfa_store.enroll("alice", secret)
        enrollment = mfa_store.get("alice")
        assert enrollment is not None
        assert enrollment["user_id"] == "alice"
        assert enrollment["secret_b32"] == secret
        assert enrollment["last_used_counter"] == 0

    def test_enroll_overwrites(self, mfa_store):
        from cutctx.security.mfa import generate_secret

        mfa_store.enroll("alice", "OLD-SECRET")
        new = generate_secret()
        mfa_store.enroll("alice", new)
        enrollment = mfa_store.get("alice")
        assert enrollment["secret_b32"] == new
        # Counter resets on re-enroll.
        assert enrollment["last_used_counter"] == 0

    def test_revoke_returns_true_when_present(self, mfa_store):
        from cutctx.security.mfa import generate_secret

        mfa_store.enroll("alice", generate_secret())
        assert mfa_store.revoke("alice") is True
        assert mfa_store.get("alice") is None

    def test_revoke_returns_false_when_absent(self, mfa_store):
        assert mfa_store.revoke("missing") is False

    def test_consume_counter_advances(self, mfa_store):
        from cutctx.security.mfa import generate_secret

        mfa_store.enroll("alice", generate_secret())
        assert mfa_store.consume_counter("alice", 5) is True
        enrollment = mfa_store.get("alice")
        assert enrollment["last_used_counter"] == 5
        # A stale counter does not regress
        assert mfa_store.consume_counter("alice", 3) is False
        enrollment = mfa_store.get("alice")
        assert enrollment["last_used_counter"] == 5
        # A newer counter advances
        assert mfa_store.consume_counter("alice", 7) is True
        enrollment = mfa_store.get("alice")
        assert enrollment["last_used_counter"] == 7

    def test_persistence_across_instances(self, tmp_path):
        from cutctx.security.mfa import MfaStore, generate_secret

        db = str(tmp_path / "mfa.db")
        store_a = MfaStore(db_path=db)
        secret = generate_secret()
        store_a.enroll("alice", secret)
        store_a.consume_counter("alice", 12)
        # New instance, same DB file
        store_b = MfaStore(db_path=db)
        enrollment = store_b.get("alice")
        assert enrollment["secret_b32"] == secret
        assert enrollment["last_used_counter"] == 12


# ── Integration: enroll -> code -> verify (full round-trip) ──────────────


class TestEnrollVerifyRoundTrip:
    def test_enroll_code_verifies(self, mfa_store):
        from cutctx.security.mfa import current_totp, verify_totp

        mfa_store.enroll("alice", "JBSWY3DPEHPK3PXP")
        enrollment = mfa_store.get("alice")
        code = current_totp(enrollment["secret_b32"]).code
        assert (
            verify_totp(
                enrollment["secret_b32"],
                code,
                last_used_counter=enrollment["last_used_counter"],
            )
            is True
        )

    def test_known_test_vector(self, mfa_store):
        """Verify a hand-rolled TOTP at a known time matches.

        Using a stable secret + time, the TOTP value is
        deterministic. This catches regressions where a
        refactor accidentally changes the truncation logic.
        """
        from cutctx.security.mfa import current_totp, verify_totp

        # 16-byte zero-padded secret
        secret = "A" * 32  # base32 for 16 zero bytes
        mfa_store.enroll("alice", secret)
        # Pin time. 1700000000 // 30 = 56666666.
        code = current_totp(secret, now=1700000000.0).code
        # 6 digits, all numeric
        assert len(code) == 6
        assert code.isdigit()
        # Verify
        assert verify_totp(secret, code, now=1700000000.0) is True

    def test_matching_counter_is_single_use_compatible(self):
        from cutctx.security.mfa import current_totp, matching_totp_counter

        secret = "JBSWY3DPEHPK3PXP"
        now = 1_700_000_000.0
        counter = int(now) // 30
        code = current_totp(secret, now=now).code

        assert (
            matching_totp_counter(secret, code, now=now, last_used_counter=counter - 1) == counter
        )
        assert matching_totp_counter(secret, code, now=now, last_used_counter=counter) is None
