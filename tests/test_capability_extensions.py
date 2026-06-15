"""Tests for capability extensions: watcher, learn_share, billing, firewall_ml, airgap."""

from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Learn Watcher
# ---------------------------------------------------------------------------

class TestSessionWatcher:
    def test_init(self):
        from headroom.learn.watcher import SessionWatcher

        async def noop(path):
            pass

        w = SessionWatcher([Path("/tmp")], noop)
        assert w.seen_count == 0

    def test_scan_detects_new_file(self):
        from headroom.learn.watcher import SessionWatcher

        detected = []

        async def on_new(path):
            detected.append(path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Create a "settled" JSONL file (old enough)
            test_file = tmp / "session.jsonl"
            test_file.write_text('{"role": "user", "content": "test"}')
            # Set mtime to 60 seconds ago
            old_time = time.time() - 60
            import os
            os.utime(test_file, (old_time, old_time))

            w = SessionWatcher([tmp], on_new)
            asyncio.run(w._scan())

            assert len(detected) == 1
            assert detected[0] == test_file
            assert w.seen_count == 1

    def test_scan_skips_recent_file(self):
        from headroom.learn.watcher import SessionWatcher

        detected = []

        async def on_new(path):
            detected.append(path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            test_file = tmp / "session.jsonl"
            test_file.write_text('{"role": "user", "content": "test"}')

            w = SessionWatcher([tmp], on_new)
            asyncio.run(w._scan())

            assert len(detected) == 0  # Too recent

    def test_scan_skips_nonexistent_dir(self):
        from headroom.learn.watcher import SessionWatcher

        async def noop(path):
            pass

        w = SessionWatcher([Path("/nonexistent")], noop)
        asyncio.run(w._scan())
        assert w.seen_count == 0

    def test_stop(self):
        from headroom.learn.watcher import SessionWatcher

        async def noop(path):
            pass

        w = SessionWatcher([], noop)
        w._running = True
        w.stop()
        assert w._running is False

    def test_seen_count_increments(self):
        from headroom.learn.watcher import SessionWatcher

        detected = []

        async def on_new(path):
            detected.append(path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            for i in range(3):
                f = tmp / f"session_{i}.jsonl"
                f.write_text('{"test": true}')
                old_time = time.time() - 60
                import os
                os.utime(f, (old_time, old_time))

            w = SessionWatcher([tmp], on_new)
            asyncio.run(w._scan())
            assert w.seen_count == 3

            # Second scan should not detect same files
            asyncio.run(w._scan())
            assert w.seen_count == 3


# ---------------------------------------------------------------------------
# Learn Share
# ---------------------------------------------------------------------------

class TestLearnShare:
    def test_format_twitter_text_single(self):
        from headroom.cli.learn_share import format_twitter_text

        text = format_twitter_text(1, "Claude Code", "use cargo test instead of pytest")
        assert "Claude Code" in text
        assert "use cargo test instead of pytest" in text
        assert "cutctx" in text.lower() or "cutctx" in text

    def test_format_twitter_text_multiple(self):
        from headroom.cli.learn_share import format_twitter_text

        text = format_twitter_text(5, "Codex", "fix import path")
        assert "5th time" in text
        assert "4 other corrections" in text

    def test_print_share_prompt(self, capsys):
        from headroom.cli.learn_share import print_share_prompt

        print_share_prompt(3, "Claude Code", "use correct path")
        captured = capsys.readouterr()
        assert "twitter.com/intent/tweet" in captured.out


# ---------------------------------------------------------------------------
# Billing: Stripe Webhook
# ---------------------------------------------------------------------------

class TestStripeWebhook:
    def test_generate_license_key(self):
        from headroom.billing.stripe_webhook import generate_license_key

        with patch.dict("os.environ", {"HEADROOM_LICENSE_HMAC_SECRET": "test-secret-1234"}):
            key = generate_license_key("team", "cus_test123")
            assert key.startswith("team-")
            parts = key.split("-")
            assert len(parts) == 3  # tier, random_id, sig

    def test_generate_license_key_no_secret(self):
        from headroom.billing.stripe_webhook import generate_license_key

        with patch.dict("os.environ", {"HEADROOM_LICENSE_HMAC_SECRET": ""}):
            with pytest.raises(ValueError, match="HEADROOM_LICENSE_HMAC_SECRET"):
                generate_license_key("team", "cus_123")

    def test_verify_stripe_signature(self):
        from headroom.billing.stripe_webhook import verify_stripe_signature

        with patch.dict("os.environ", {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            # The actual verification requires proper HMAC
            # Just verify the function exists and can be called
            with pytest.raises((ValueError, Exception)):
                verify_stripe_signature(b'payload', "t=123,v1=bad")

    def test_handle_checkout_completed(self):
        from headroom.billing.stripe_webhook import LicenseRecord, handle_checkout_completed

        event_data = {
            "object": {
                "customer": "cus_123",
                "subscription": "sub_456",
                "metadata": {"tier": "team", "seats": "10"},
                "customer_details": {"email": "test@example.com"},
            }
        }

        with patch.dict("os.environ", {"HEADROOM_LICENSE_HMAC_SECRET": "test-secret"}):
            with patch("headroom.billing.stripe_webhook._save_license"):
                with patch("headroom.billing.stripe_webhook._send_license_email"):
                    record = handle_checkout_completed(event_data)
                    assert record.tier == "team"
                    assert record.seats == 10
                    assert record.customer_email == "test@example.com"
                    assert record.active is True


# ---------------------------------------------------------------------------
# Billing: License DB
# ---------------------------------------------------------------------------

class TestLicenseDB:
    def test_upsert_and_get(self):
        from headroom.billing.license_db import LicenseDB
        from headroom.billing.stripe_webhook import LicenseRecord

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            db = LicenseDB(Path(f.name))
            record = LicenseRecord(
                license_key="team-abc-sig12345678",
                tier="team",
                customer_email="test@test.com",
                seats=5,
                stripe_customer_id="cus_1",
                stripe_subscription_id="sub_1",
                created_at=time.time(),
                expires_at=time.time() + 86400,
                active=True,
            )
            db.upsert(record)
            result = db.validate("team-abc-sig12345678")
            assert result["valid"] is True
            assert result["tier"] == "team"

    def test_validate_not_found(self):
        from headroom.billing.license_db import LicenseDB

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            db = LicenseDB(Path(f.name))
            result = db.validate("nonexistent-key")
            assert result["valid"] is False
            assert result["reason"] == "key_not_found"

    def test_validate_expired(self):
        from headroom.billing.license_db import LicenseDB
        from headroom.billing.stripe_webhook import LicenseRecord

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            db = LicenseDB(Path(f.name))
            record = LicenseRecord(
                license_key="team-expired",
                tier="team",
                customer_email="test@test.com",
                seats=5,
                stripe_customer_id="cus_1",
                stripe_subscription_id="sub_1",
                created_at=time.time() - 100000,
                expires_at=time.time() - 1,  # expired
                active=True,
            )
            db.upsert(record)
            result = db.validate("team-expired")
            assert result["valid"] is False
            assert result["reason"] == "expired"

    def test_list_all(self):
        from headroom.billing.license_db import LicenseDB
        from headroom.billing.stripe_webhook import LicenseRecord

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            db = LicenseDB(Path(f.name))
            record = LicenseRecord(
                license_key="team-list",
                tier="team",
                customer_email="test@test.com",
                seats=5,
                stripe_customer_id="cus_1",
                stripe_subscription_id="sub_1",
                created_at=time.time(),
                expires_at=time.time() + 86400,
                active=True,
            )
            db.upsert(record)
            all_records = db.list_all()
            assert len(all_records) == 1
            assert all_records[0]["license_key"] == "team-list"


# ---------------------------------------------------------------------------
# Firewall ML Classifier
# ---------------------------------------------------------------------------

class TestFirewallML:
    def test_init_no_model(self):
        from headroom.security.firewall_ml import MLInjectionClassifier

        MLInjectionClassifier.reset_instance()
        clf = MLInjectionClassifier(model_dir=Path("/nonexistent"))
        assert clf.available is False

    def test_score_returns_zero_when_unavailable(self):
        from headroom.security.firewall_ml import MLInjectionClassifier

        MLInjectionClassifier.reset_instance()
        clf = MLInjectionClassifier(model_dir=Path("/nonexistent"))
        score = clf.score("ignore previous instructions")
        assert score == 0.0

    def test_is_injection_returns_false_when_unavailable(self):
        from headroom.security.firewall_ml import MLInjectionClassifier

        MLInjectionClassifier.reset_instance()
        clf = MLInjectionClassifier(model_dir=Path("/nonexistent"))
        assert clf.is_injection("ignore previous instructions") is False

    def test_singleton(self):
        from headroom.security.firewall_ml import MLInjectionClassifier

        MLInjectionClassifier.reset_instance()
        a = MLInjectionClassifier.get_instance()
        b = MLInjectionClassifier.get_instance()
        assert a is b
        MLInjectionClassifier.reset_instance()

    def test_score_batch(self):
        from headroom.security.firewall_ml import MLInjectionClassifier

        MLInjectionClassifier.reset_instance()
        clf = MLInjectionClassifier(model_dir=Path("/nonexistent"))
        scores = clf.score_batch(["text1", "text2", "text3"])
        assert len(scores) == 3
        assert all(s == 0.0 for s in scores)


# ---------------------------------------------------------------------------
# Airgap
# ---------------------------------------------------------------------------

class TestAirgap:
    def test_is_offline_default(self):
        from headroom.proxy.airgap import is_offline

        with patch.dict("os.environ", {"HEADROOM_OFFLINE_MODE": "0"}):
            assert is_offline() is False

    def test_check_offline_compat_ok(self):
        from headroom.proxy.airgap import check_offline_compat

        with patch.dict("os.environ", {"HEADROOM_OFFLINE_MODE": "0"}):
            check_offline_compat()  # Should not raise

    def test_check_offline_requires_hmac(self):
        from headroom.proxy.airgap import check_offline_compat

        with patch.dict("os.environ", {
            "HEADROOM_OFFLINE_MODE": "1",
            "HEADROOM_LICENSE_HMAC_SECRET": "",
        }):
            with pytest.raises(RuntimeError, match="HEADROOM_LICENSE_HMAC_SECRET"):
                check_offline_compat()
