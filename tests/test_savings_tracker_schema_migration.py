import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cutctx.proxy.savings_tracker import SCHEMA_VERSION, SavingsTracker


def test_savings_tracker_schema_migration():
    with tempfile.TemporaryDirectory() as tempdir:
        db_path = Path(tempdir) / "test_savings.json"

        # Create a v3 state manually
        v3_state = {
            "schema_version": 3,
            "lifetime": {
                "requests": 10,
                "tokens_saved": 1000,
                "compression_savings_usd": 0.05,
                "cache_savings_usd": 0.02,
                "total_input_tokens": 5000,
                "total_input_cost_usd": 0.1,
            },
            "display_session": {
                "requests": 10,
                "tokens_saved": 1000,
                "compression_savings_usd": 0.05,
                "total_input_tokens": 5000,
                "total_input_cost_usd": 0.1,
                "savings_percent": 20.0,
                "started_at": "2026-07-01T12:00:00Z",
                "last_activity_at": "2026-07-01T12:05:00Z",
            },
            "history": [
                {
                    "timestamp": "2026-07-01T12:01:00Z",
                    "provider": "anthropic",
                    "model": "claude-3-5-sonnet",
                    "total_tokens_saved": 500,
                    "compression_savings_usd": 0.025,
                    "cache_savings_usd": 0.01,
                    "total_input_tokens": 2500,
                    "total_input_cost_usd": 0.05,
                    "delta_tokens_saved": 500,
                    "delta_savings_usd": 0.025,
                },
                {
                    "timestamp": "2026-07-01T12:05:00Z",
                    "provider": "anthropic",
                    "model": "claude-3-5-sonnet",
                    "total_tokens_saved": 1000,
                    "compression_savings_usd": 0.05,
                    "cache_savings_usd": 0.02,
                    "total_input_tokens": 5000,
                    "total_input_cost_usd": 0.1,
                    "delta_tokens_saved": 500,
                    "delta_savings_usd": 0.025,
                },
            ],
            "projects": {},
            "models": {},
            "clients": {},
        }

        with open(db_path, "w") as f:
            json.dump(v3_state, f)

        storage = SavingsTracker(db_path)
        snapshot = storage.snapshot()

        # Check migration note
        assert snapshot["schema_version"] == 6
        assert "attribution_note" in snapshot
        assert (
            "explicit created/observed token attribution introduced in schema v6"
            in snapshot["attribution_note"]
        )
        assert snapshot["lifetime"]["attribution_coverage"]["complete"] is False

        # Check that created/observed USD tracks were backfilled gracefully.
        assert snapshot["lifetime"]["compression_savings_usd"] == 0.05
        assert snapshot["lifetime"]["cache_savings_usd"] == 0.02
        assert snapshot["lifetime"]["created_savings_usd"] == 0.05
        assert snapshot["lifetime"]["observed_provider_savings_usd"] == 0.02
        assert snapshot["lifetime"]["compression_savings_observed_usd"] == 0.0


def test_savings_tracker_observed_usd_split():
    with tempfile.TemporaryDirectory() as tempdir:
        db_path = Path(tempdir) / "test_savings.json"
        storage = SavingsTracker(db_path)

        # We record a request that simulates both list price savings and observed discounts
        # Let's say model list price is $3.00 per 1M input tokens. So 1M tokens = $3
        # If we save 100k tokens via cache read, the list price value (created) is $0.30
        # If the provider discount is 50%, actual cash saved (observed) is $0.15

        # Litellm doesn't have custom caching pricing natively, so cache_savings_usd_delta is passed in
        storage.record_request(
            model="gpt-4o",  # cost per 1M tokens is $2.50 -> 1000 tokens = $0.0025
            input_tokens=2000,
            tokens_saved=1000,  # 1000 cache read + 0 cutctx
            cache_read_tokens=1000,
            cache_savings_usd_delta=0.00125,  # Observed discount (50% off)
        )

        snapshot = storage.snapshot()
        lifetime = snapshot["lifetime"]

        # Cache savings
        assert "cache_savings_usd" in lifetime
        assert "cache_savings_observed_usd" in lifetime
        assert lifetime["created_savings_usd"] == 0.0
        assert lifetime["observed_provider_savings_usd"] == 0.00125

        # 1000 tokens of gpt-4o input @ $2.50/1M = $0.0025 list price
        assert lifetime["cache_savings_usd"] == 0.0025
        assert lifetime["cache_savings_observed_usd"] == 0.00125

        history_row = snapshot["history"][-1]
        assert history_row["created_savings_usd"] == 0.0
        assert history_row["observed_provider_savings_usd"] == 0.00125
        assert history_row["cache_savings_usd"] == 0.0025
        assert history_row["cache_savings_observed_usd"] == 0.00125
