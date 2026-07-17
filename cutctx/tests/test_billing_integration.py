"""Integration tests for billing → license flow."""

from __future__ import annotations

import os
import sys
import pytest

# Ensure test HMAC secret is set before any module imports it
os.environ.setdefault("CUTCTX_LICENSE_HMAC_SECRET", "test-secret-for-tests")

# Make scripts/ importable
_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_SCRIPTS_DIR))

from generate_license import generate_license_key, tier_to_prefix  # noqa: E402

from cutctx import billing  # noqa: E402
from cutctx.billing import (  # noqa: E402
    PITCHTOSHIP_BASE_URL,
    get_checkout_url,
    get_portal_url,
    map_tier_to_plan,
)

# ---------------------------------------------------------------------------
# TestTierMapping
# ---------------------------------------------------------------------------


class TestTierMapping:
    @pytest.mark.parametrize(
        "tier, expected_plan",
        [
            ("team", "starter"),
            ("business", "studio"),
            ("enterprise", "portfolio"),
        ],
    )
    def test_tier_mapping(self, tier: str, expected_plan: str):
        """map_tier_to_plan(tier) returns the correct pitchtoship plan key."""
        assert map_tier_to_plan(tier) == expected_plan

    def test_tier_mapping_unknown_defaults_to_starter(self):
        """Unknown tier falls back to 'starter'."""
        assert map_tier_to_plan("unknown-tier") == "starter"


# ---------------------------------------------------------------------------
# TestCheckoutURL
# ---------------------------------------------------------------------------


class TestCheckoutURL:
    def test_get_checkout_url_is_a_pitchtoship_billing_deep_link(self, monkeypatch):
        """Checkout always opens the hosted PitchToShip Razorpay billing flow."""
        monkeypatch.setattr(billing, "PITCHTOSHIP_BASE_URL", "https://billing.example")

        assert get_checkout_url("starter", "buyer@example.com", "monthly") == (
            "https://billing.example/billing?product=cutctx&plan=starter"
            "&billing=monthly&email=buyer%40example.com"
        )

    def test_get_checkout_url_normalizes_unknown_values(self, monkeypatch):
        monkeypatch.setattr(billing, "PITCHTOSHIP_BASE_URL", "https://billing.example")

        assert get_checkout_url("unknown", billing="weekly") == (
            "https://billing.example/billing?product=cutctx&plan=starter&billing=annual"
        )


# ---------------------------------------------------------------------------
# TestPortalURL
# ---------------------------------------------------------------------------


class TestPortalURL:
    def test_get_portal_url_is_the_pitchtoship_account_portal(self, monkeypatch):
        monkeypatch.setattr(billing, "PITCHTOSHIP_BASE_URL", "https://billing.example")

        assert get_portal_url("buyer@example.com") == (
            "https://billing.example/account?email=buyer%40example.com"
        )


# ---------------------------------------------------------------------------
# TestLicenseKeyFormat  (uses generate_license.py)
# ---------------------------------------------------------------------------


class TestLicenseKeyFormat:
    SECRET = "test-secret-for-tests"

    @pytest.mark.parametrize(
        "tier, expected_prefix",
        [
            ("team", "team-"),
            ("business", "biz-"),
            ("enterprise", "ent-"),
            ("builder", "bld-"),
        ],
    )
    def test_license_key_prefix(self, tier: str, expected_prefix: str):
        """Generated license key starts with the correct tier prefix."""
        _, signed_key = generate_license_key(
            tier=tier,
            org_name="TestOrg",
            seats=5,
            secret=self.SECRET,
        )
        assert signed_key is not None
        assert signed_key.startswith(expected_prefix), (
            f"Expected key to start with '{expected_prefix}', got: {signed_key!r}"
        )

    def test_license_key_contains_hmac_separator(self):
        """License key contains '.' separating the base64 payload from the HMAC hex."""
        _, signed_key = generate_license_key(
            tier="team",
            org_name="SepTestOrg",
            seats=3,
            secret=self.SECRET,
        )
        assert signed_key is not None
        parts = signed_key.split(".")
        assert len(parts) == 2, f"Expected exactly one '.' separator, got: {signed_key!r}"

    def test_license_key_hmac_part_is_valid_hex(self):
        """The part after '.' is valid hexadecimal (HMAC-SHA256 digest)."""
        _, signed_key = generate_license_key(
            tier="business",
            org_name="HexOrg",
            seats=1,
            secret=self.SECRET,
        )
        assert signed_key is not None
        _, hmac_part = signed_key.split(".", 1)
        # Should be decodeable as hex
        try:
            bytes.fromhex(hmac_part)
        except ValueError:
            pytest.fail(f"HMAC part is not valid hex: {hmac_part!r}")

    def test_license_key_unsigned_has_no_hmac(self):
        """Dry-run (no secret) returns None for the signed key."""
        unsigned_key, signed_key = generate_license_key(
            tier="team",
            org_name="DryRunOrg",
            seats=2,
            secret=None,
        )
        assert signed_key is None
        assert unsigned_key.startswith("team-")

    def test_tier_to_prefix_raises_on_unknown_tier(self):
        """tier_to_prefix raises ValueError for unknown tier strings."""
        with pytest.raises(ValueError, match="Unknown tier"):
            tier_to_prefix("gold")
