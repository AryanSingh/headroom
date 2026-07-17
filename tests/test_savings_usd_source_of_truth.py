"""Lifetime model-routing USD must carry the router's true price delta.

Guards the attribution divergence where ``lifetime.model_routing_savings_usd``
re-estimated routing savings at the routed-to model's flat input rate while
``lifetime["savings_by_source_usd.model_routing"]`` (and the headline
``created_savings_usd``) carried the router's true (source − target) price
delta — a 4.1x disagreement visible to any procurement reviewer.

Token-avoidance sources (provider cache, semantic cache, tool-surface) keep
their intentional two-column design: ``X_savings_usd`` is a list-price
valuation of the avoided tokens; ``X_savings_observed_usd`` is the actual
cash delta. Routing has no meaningful list-price column — its only honest
valuation is the delta — so its typed counter must follow the by-source
ledger, exactly like ``compression_savings_usd`` already does.
"""

from __future__ import annotations

import pytest

from cutctx.proxy.savings_tracker import SavingsTracker


def _record_routed_request(tracker: SavingsTracker, *, routing_usd: float | None) -> None:
    kwargs: dict = {}
    by_source_usd = {"cutctx_compression": 1.25}
    if routing_usd is not None:
        by_source_usd["model_routing"] = routing_usd
        kwargs["model_routing_usd_delta"] = routing_usd
    tracker.record_request(
        model="gpt-5.4-mini",
        input_tokens=10_000,
        tokens_saved=300,
        cache_read_tokens=12_000,
        savings_by_source_tokens={
            "cutctx_compression": 300,
            "provider_prompt_cache": 12_000,
            "model_routing": 200_000,
        },
        savings_by_source_usd=by_source_usd,
        compression_savings_usd_delta=1.25,
        **kwargs,
    )


def test_lifetime_routing_usd_uses_router_delta_not_flat_reestimate(tmp_path) -> None:
    tracker = SavingsTracker(path=str(tmp_path / "savings.json"))

    # The router's true delta for these 200k routed tokens. A flat
    # re-estimate at the routed-to model's input rate would produce a
    # different (and meaningless) number.
    _record_routed_request(tracker, routing_usd=0.75)

    lifetime = tracker.stats_preview()["lifetime"]
    assert lifetime["model_routing_savings_usd"] == pytest.approx(0.75)
    assert lifetime["savings_by_source_usd.model_routing"] == pytest.approx(0.75)
    assert lifetime["model_routing_savings_observed_usd"] == pytest.approx(0.75)


def test_lifetime_routing_usd_falls_back_to_estimate_without_by_source(tmp_path) -> None:
    tracker = SavingsTracker(path=str(tmp_path / "savings.json"))

    # Legacy caller shape: routed tokens known, no USD provided anywhere.
    _record_routed_request(tracker, routing_usd=None)

    lifetime = tracker.stats_preview()["lifetime"]
    # The flat estimate is a legacy fallback; it must still produce a
    # non-negative value and never crash.
    assert lifetime["model_routing_savings_usd"] >= 0.0


def test_token_avoidance_sources_keep_list_price_column(tmp_path) -> None:
    tracker = SavingsTracker(path=str(tmp_path / "savings.json"))

    # Explicit observed cash delta differs from list price; the typed
    # cache column must stay a list-price valuation (two-column design).
    tracker.record_request(
        model="gpt-4o",
        input_tokens=2_000,
        tokens_saved=1_000,
        cache_read_tokens=1_000,
        cache_savings_usd_delta=0.00125,
    )

    lifetime = tracker.stats_preview()["lifetime"]
    assert lifetime["cache_savings_usd"] == pytest.approx(0.0025)
    assert lifetime["cache_savings_observed_usd"] == pytest.approx(0.00125)


def test_v7_migration_reconciles_routing_usd_onto_by_source_ledger(tmp_path) -> None:
    import json

    path = tmp_path / "savings.json"
    v6_state = {
        "schema_version": 6,
        "lifetime": {
            "requests": 100,
            "tokens_saved": 1_000_000,
            "total_input_tokens": 5_000_000,
            "total_input_cost_usd": 50.0,
            "compression_savings_usd": 193.75,
            "cache_savings_usd": 8268.61,
            "model_routing_savings_usd": 273.45,
            "savings_by_source_usd.model_routing": 1122.32,
            "savings_by_source_usd.cutctx_compression": 142.03,
            "savings_by_source_usd.provider_prompt_cache": 8264.05,
        },
        "display_session": {
            "requests": 0,
            "tokens_saved": 0,
            "total_input_tokens": 0,
            "total_input_cost_usd": 0.0,
            "savings_percent": 0.0,
            "started_at": "2026-07-18T00:00:00Z",
            "last_activity_at": "2026-07-18T00:00:00Z",
        },
        "history": [],
        "projects": {},
        "models": {},
        "clients": {},
    }
    path.write_text(json.dumps(v6_state))

    tracker = SavingsTracker(path=str(path))
    snapshot = tracker.snapshot()

    assert snapshot["schema_version"] >= 7
    lifetime = snapshot["lifetime"]
    # Routing typed counter adopts the canonical by-source delta.
    assert lifetime["model_routing_savings_usd"] == pytest.approx(1122.32)
    # Two-column token-avoidance sources are untouched by the migration.
    assert lifetime["cache_savings_usd"] == pytest.approx(8268.61)
    assert lifetime["compression_savings_usd"] == pytest.approx(193.75)
    # The pre-reconciliation value stays auditable.
    reconciliation = snapshot["attribution_reconciliation"]
    fields = reconciliation["fields"]
    assert fields["model_routing_savings_usd"]["previous"] == pytest.approx(273.45)
    assert fields["model_routing_savings_usd"]["reconciled_to"] == pytest.approx(1122.32)


def test_v7_migration_is_idempotent_and_skips_consistent_files(tmp_path) -> None:
    import json

    path = tmp_path / "savings.json"
    v6_state = {
        "schema_version": 6,
        "lifetime": {
            "requests": 1,
            "tokens_saved": 10,
            "total_input_tokens": 100,
            "total_input_cost_usd": 1.0,
            "model_routing_savings_usd": 5.0,
            "savings_by_source_usd.model_routing": 5.0,
        },
        "display_session": {
            "requests": 0,
            "tokens_saved": 0,
            "total_input_tokens": 0,
            "total_input_cost_usd": 0.0,
            "savings_percent": 0.0,
            "started_at": "2026-07-18T00:00:00Z",
            "last_activity_at": "2026-07-18T00:00:00Z",
        },
        "history": [],
        "projects": {},
        "models": {},
        "clients": {},
    }
    path.write_text(json.dumps(v6_state))

    snapshot = SavingsTracker(path=str(path)).snapshot()
    assert snapshot["schema_version"] >= 7
    assert snapshot["lifetime"]["model_routing_savings_usd"] == pytest.approx(5.0)
    assert "attribution_reconciliation" not in snapshot


def test_history_response_carries_attribution_provenance(tmp_path) -> None:
    import json

    path = tmp_path / "savings.json"
    v6_state = {
        "schema_version": 6,
        "lifetime": {
            "requests": 100,
            "tokens_saved": 1_000_000,
            "total_input_tokens": 5_000_000,
            "total_input_cost_usd": 50.0,
            "model_routing_savings_usd": 273.45,
            "savings_by_source_usd.model_routing": 1122.32,
        },
        "display_session": {
            "requests": 0,
            "tokens_saved": 0,
            "total_input_tokens": 0,
            "total_input_cost_usd": 0.0,
            "savings_percent": 0.0,
            "started_at": "2026-07-18T00:00:00Z",
            "last_activity_at": "2026-07-18T00:00:00Z",
        },
        "history": [],
        "projects": {},
        "models": {},
        "clients": {},
    }
    path.write_text(json.dumps(v6_state))

    response = SavingsTracker(path=str(path)).history_response()
    assert "attribution_reconciliation" in response
    fields = response["attribution_reconciliation"]["fields"]
    assert "model_routing_savings_usd" in fields
