"""Buyer report must separate eligible vs all-traffic rates honestly."""

from __future__ import annotations

from cutctx.cli.report import build_buyer_report_payload


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
