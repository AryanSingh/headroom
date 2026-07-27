"""Buyer report must separate eligible vs all-traffic rates honestly."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

from cutctx.cli.report import _collect_savings_history, build_buyer_report_payload
from cutctx.proxy.savings_tracker import SCHEMA_VERSION


def test_buyer_report_separates_eligible_and_all_traffic_rates() -> None:
    rows = [
        {
            "savings_by_source_tokens": {"cutctx_compression": 100},
            "compressed": True,
            "bypassed_small": False,
        },
        {
            "savings_by_source_tokens": {},
            "compressed": False,
            "bypassed_small": True,
        },
        {
            "savings_by_source_tokens": {"provider_prompt_cache": 50},
            "compressed": False,
            "bypassed_small": False,
        },
    ]
    payload = build_buyer_report_payload(rows)
    assert payload["requests_total"] == 3
    assert payload["requests_bypassed_small"] == 1
    assert payload["requests_compressed"] == 1
    assert payload["created_savings_tokens"] == 100
    assert payload["observed_provider_cache_tokens"] == 50
    assert payload["eligible_compression_rate"] == 0.5  # 1 compressed / 2 eligible
    assert abs(payload["all_traffic_compression_rate"] - (1 / 3)) < 1e-9
    assert "eligible" in payload["caveat"].lower()


def test_buyer_report_caveat_mentions_all_traffic_label() -> None:
    payload = build_buyer_report_payload([])
    assert "all-traffic" in payload["caveat"].lower() or "all traffic" in payload["caveat"].lower()


def test_collect_savings_history_wires_buyer_honesty_fields(tmp_path) -> None:
    """Integration: durable tracker rows must carry compressed/bypassed_small."""
    now = datetime.now(timezone.utc).isoformat()
    savings_path = tmp_path / "proxy_savings.json"
    savings_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "history": [
                    {
                        "timestamp": now,
                        "provider": "openai",
                        "model": "gpt-4o",
                        "delta_tokens_saved": 400,
                        "savings_by_source_tokens": {"cutctx_compression": 400},
                        "opportunity_funnel": {
                            "eligible_input_tokens": 1000,
                            "cache_protected_tokens": 0,
                            "compressed_tokens": 400,
                            "declined_tokens": 0,
                        },
                    },
                    {
                        "timestamp": now,
                        "provider": "openai",
                        "model": "gpt-4o",
                        "delta_tokens_saved": 0,
                        "decline_reason": "too_small",
                        "opportunity_funnel": {
                            "eligible_input_tokens": 120,
                            "cache_protected_tokens": 0,
                            "compressed_tokens": 0,
                            "declined_tokens": 120,
                        },
                    },
                    {
                        "timestamp": now,
                        "provider": "anthropic",
                        "model": "claude-3-5-sonnet-20241022",
                        "delta_tokens_saved": 0,
                        "savings_by_source_tokens": {"provider_prompt_cache": 200},
                        "opportunity_funnel": {
                            "eligible_input_tokens": 800,
                            "cache_protected_tokens": 200,
                            "compressed_tokens": 0,
                            "declined_tokens": 0,
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with patch(
        "cutctx.proxy.savings_tracker.get_default_savings_storage_path",
        return_value=str(savings_path),
    ):
        rows = _collect_savings_history(days=30)

    assert len(rows) == 3
    assert rows[0]["compressed"] is True
    assert rows[0]["bypassed_small"] is False
    assert rows[1]["compressed"] is False
    assert rows[1]["bypassed_small"] is True
    assert rows[2]["compressed"] is False
    assert rows[2]["bypassed_small"] is False

    payload = build_buyer_report_payload(rows)
    assert payload["requests_total"] == 3
    assert payload["requests_bypassed_small"] == 1
    assert payload["requests_compressed"] == 1
    assert payload["eligible_compression_rate"] == 0.5
