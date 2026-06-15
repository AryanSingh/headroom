"""
Tests for billing integration between pitchtoship and CutCtx.

Tests the tier mapping, license key generation, and webhook handling
without making live API calls.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts to path for import
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from issue_license_from_webhook import (
    PLAN_TO_TIER,
    generate_license_key,
    handle_webhook_payload,
    record_license,
)


class TestTierMapping:
    def test_starter_maps_to_team(self):
        assert PLAN_TO_TIER["starter"] == "team"

    def test_studio_maps_to_business(self):
        assert PLAN_TO_TIER["studio"] == "business"

    def test_portfolio_maps_to_enterprise(self):
        assert PLAN_TO_TIER["portfolio"] == "enterprise"


class TestLicenseKeyGeneration:
    def test_key_format_team(self):
        key = generate_license_key("team", "test@example.com")
        assert key.startswith("team-")
        assert "." in key
        parts = key.split(".", 1)
        assert len(parts) == 2

    def test_key_format_business(self):
        key = generate_license_key("business", "test@example.com")
        assert key.startswith("business-")

    def test_key_format_enterprise(self):
        key = generate_license_key("enterprise", "test@example.com")
        assert key.startswith("enterprise-")

    def test_key_contains_email_in_payload(self):
        key = generate_license_key("team", "alice@corp.com")
        # Payload is base64url-encoded JSON
        import base64

        encoded_payload = key.split("-")[1].split(".")[0]
        # Add padding
        padded = encoded_payload + "=" * (4 - len(encoded_payload) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(payload_bytes)
        assert payload["email"] == "alice@corp.com"
        assert payload["tier"] == "team"

    def test_key_expiry_is_one_year(self):
        from datetime import datetime, timedelta, timezone

        key = generate_license_key("team", "test@example.com", expiry_days=365)
        import base64

        encoded_payload = key.split("-")[1].split(".")[0]
        padded = encoded_payload + "=" * (4 - len(encoded_payload) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded)
        payload = json.loads(payload_bytes)

        expires = datetime.fromisoformat(payload["expires"])
        issued = datetime.fromisoformat(payload["issued"])
        delta = expires - issued
        assert delta.days >= 364  # Allow for rounding at boundary

    def test_key_with_hmac_secret(self):
        with patch.dict(os.environ, {"HEADROOM_LICENSE_HMAC_SECRET": "test-secret"}):
            key = generate_license_key("team", "test@example.com")
            # Should have real HMAC, not .dev
            assert not key.endswith(".dev")
            sig = key.split(".")[-1]
            assert len(sig) == 16  # Truncated HMAC


class TestWebhookHandling:
    def test_valid_starter_plan(self):
        payload = {
            "email": "user@example.com",
            "plan": "starter",
            "stripe_customer_id": "cus_123",
        }
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            result = handle_webhook_payload(payload, db_path=db_path)
            assert result["success"] is True
            assert result["license_key"].startswith("team-")
        finally:
            os.unlink(db_path)

    def test_valid_studio_plan(self):
        payload = {"email": "user@example.com", "plan": "studio"}
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            result = handle_webhook_payload(payload, db_path=db_path)
            assert result["success"] is True
            assert result["license_key"].startswith("business-")
        finally:
            os.unlink(db_path)

    def test_missing_email_returns_error(self):
        result = handle_webhook_payload({"plan": "starter"})
        assert result["success"] is False
        assert "Missing email" in result["error"]

    def test_missing_plan_returns_error(self):
        result = handle_webhook_payload({"email": "test@example.com"})
        assert result["success"] is False
        assert "Missing email or plan" in result["error"]

    def test_unknown_plan_returns_error(self):
        result = handle_webhook_payload({"email": "test@example.com", "plan": "unknown"})
        assert result["success"] is False
        assert "Unknown plan" in result["error"]

    def test_dry_run_does_not_write_db(self):
        payload = {"email": "test@example.com", "plan": "starter"}
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            result = handle_webhook_payload(payload, dry_run=True, db_path=db_path)
            assert result["success"] is True
            # DB table not created in dry-run mode (expected)
            assert not os.path.exists(db_path) or os.path.getsize(db_path) == 0
        finally:
            os.unlink(db_path)


class TestLicenseRecording:
    def test_record_and_retrieve(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            record_license(
                "test@example.com", "team", "team-abc123.def", "starter",
                stripe_customer_id="cus_test", db_path=db_path,
            )
            import sqlite3

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT email, tier, license_key, plan FROM licenses_issued"
            ).fetchone()
            conn.close()
            assert row[0] == "test@example.com"
            assert row[1] == "team"
            assert row[2] == "team-abc123.def"
            assert row[3] == "starter"
        finally:
            os.unlink(db_path)

    def test_record_with_stripe_customer_id(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            record_license(
                "test@example.com", "team", "team-abc123.def", "starter",
                stripe_customer_id="cus_12345", db_path=db_path,
            )
            import sqlite3

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT stripe_customer_id FROM licenses_issued"
            ).fetchone()
            conn.close()
            assert row[0] == "cus_12345"
        finally:
            os.unlink(db_path)


class TestEdgeCases:
    def test_get_checkout_url_returns_fallback_on_timeout(self):
        """When pitchtoship is unreachable, should return a fallback URL."""
        # This tests the resilience pattern, not the actual HTTP call
        with patch("httpx.get", side_effect=Exception("Connection timeout")):
            # The actual function doesn't exist yet, but the pattern should work
            pass  # Placeholder for when billing.py has get_checkout_url()

    def test_key_with_long_email(self):
        long_email = "a" * 200 + "@example.com"
        key = generate_license_key("team", long_email)
        assert key.startswith("team-")

    def test_key_with_unicode_email(self):
        key = generate_license_key("team", "用户@example.com")
        assert key.startswith("team-")
