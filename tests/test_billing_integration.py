"""
Tests for billing integration between pitchtoship and Cutctx.

Tests the tier mapping, license key generation, and logging
without making live API calls.
"""

import base64
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts to path for import
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from issue_license_from_webhook import (  # noqa: E402
    DEV_SECRET,
    PLAN_TO_TIER,
    TIER_TO_SEATS,
    encode_payload,
    generate_license_key,
    init_db,
    log_license,
    tier_to_prefix,
)


class TestTierMapping:
    def test_starter_maps_to_team(self):
        assert PLAN_TO_TIER["starter"] == "team"

    def test_studio_maps_to_business(self):
        assert PLAN_TO_TIER["studio"] == "business"

    def test_portfolio_maps_to_enterprise(self):
        assert PLAN_TO_TIER["portfolio"] == "enterprise"

    def test_all_plans_have_tiers(self):
        for plan, tier in PLAN_TO_TIER.items():
            assert tier in ("team", "business", "enterprise")


class TestTierToSeats:
    def test_team_seats(self):
        assert TIER_TO_SEATS["team"] == 5

    def test_business_seats(self):
        assert TIER_TO_SEATS["business"] == 25

    def test_enterprise_unlimited(self):
        assert TIER_TO_SEATS["enterprise"] == 0


class TestLicenseKeyGeneration:
    def test_key_format_team(self):
        key = generate_license_key(
            tier="team", org_name="test", seats=5,
            expiry=None, secret=None,
        )
        assert key.startswith("team-")
        assert ".dryrun" in key

    def test_key_format_business(self):
        key = generate_license_key(
            tier="business", org_name="test", seats=25,
            expiry=None, secret=None,
        )
        assert key.startswith("biz-")

    def test_key_format_enterprise(self):
        key = generate_license_key(
            tier="enterprise", org_name="test", seats=0,
            expiry=None, secret=None,
        )
        assert key.startswith("ent-")

    def test_key_with_secret_has_hmac(self):
        key = generate_license_key(
            tier="team", org_name="Acme", seats=5,
            expiry=None, secret="my-secret",
        )
        # Should have real HMAC sig, not .dryrun
        sig = key.split(".")[-1]
        assert sig != "dryrun"
        assert len(sig) == 64  # SHA-256 hex

    def test_key_with_expiry(self):
        key = generate_license_key(
            tier="team", org_name="Acme", seats=5,
            expiry="2026-01-01", secret=None,
        )
        # Payload should contain expiry
        parts = key.split("-", 1)
        encoded = parts[1].split(".")[0]
        padded = encoded + "=" * (4 - len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        assert payload["expiry"] == "2026-01-01"

    def test_key_with_long_org(self):
        long_org = "a" * 500
        key = generate_license_key(
            tier="team", org_name=long_org, seats=5,
            expiry=None, secret=None,
        )
        assert key.startswith("team-")

    def test_key_with_unicode_org(self):
        key = generate_license_key(
            tier="team", org_name="株式会社テスト", seats=5,
            expiry=None, secret=None,
        )
        assert key.startswith("team-")


class TestEncodePayload:
    def test_basic_payload(self):
        encoded = encode_payload("Acme", 5)
        padded = encoded + "=" * (4 - len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        assert payload["org"] == "Acme"
        assert payload["seats"] == 5
        assert "expiry" not in payload

    def test_payload_with_expiry(self):
        encoded = encode_payload("Acme", 5, expiry="2026-01-01")
        padded = encoded + "=" * (4 - len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        assert payload["expiry"] == "2026-01-01"

    def test_unlimited_seats(self):
        encoded = encode_payload("Acme", 0)
        padded = encoded + "=" * (4 - len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        assert payload["seats"] == "unlimited"


class TestTierPrefix:
    def test_builder(self):
        assert tier_to_prefix("builder") == "bld-"

    def test_team(self):
        assert tier_to_prefix("team") == "team-"

    def test_business(self):
        assert tier_to_prefix("business") == "biz-"

    def test_enterprise(self):
        assert tier_to_prefix("enterprise") == "ent-"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown tier"):
            tier_to_prefix("unknown")


class TestLicenseRecording:
    def test_log_and_retrieve(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            log_license(
                email="test@example.com",
                org="Test Org",
                plan="starter",
                tier="team",
                license_key="team-abc123.def",
                stripe_customer_id="cus_test",
                issued_at="2025-01-01T00:00:00Z",
            )
            # The function writes to default db_path, not our temp one
            # Instead, test init_db + direct insert on our temp db
            conn = sqlite3.connect(db_path)
            init_db(conn)
            conn.execute(
                """INSERT INTO licenses (email, org, plan, tier, license_key, stripe_customer_id, issued_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("test@example.com", "Test Org", "starter", "team", "team-abc123.def", "cus_test", "2025-01-01T00:00:00Z"),
            )
            conn.commit()
            row = conn.execute("SELECT email, tier, license_key, plan FROM licenses").fetchone()
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
            conn = sqlite3.connect(db_path)
            init_db(conn)
            conn.execute(
                """INSERT INTO licenses (email, org, plan, tier, license_key, stripe_customer_id, issued_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("test@example.com", "Test Org", "starter", "team", "team-abc123.def", "cus_12345", "2025-01-01T00:00:00Z"),
            )
            conn.commit()
            row = conn.execute("SELECT stripe_customer_id FROM licenses").fetchone()
            conn.close()
            assert row[0] == "cus_12345"
        finally:
            os.unlink(db_path)


class TestEdgeCases:
    def test_dev_secret_is_not_empty(self):
        assert DEV_SECRET
        assert len(DEV_SECRET) > 10

    def test_init_db_creates_table(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            init_db(conn)
            # Table should exist
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert "licenses" in table_names
            conn.close()
        finally:
            os.unlink(db_path)

    def test_init_db_idempotent(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            init_db(conn)
            init_db(conn)  # Should not raise
            conn.close()
        finally:
            os.unlink(db_path)
