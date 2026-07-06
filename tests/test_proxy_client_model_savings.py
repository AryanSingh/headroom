"""Tests for durable per-model and per-client savings attribution.

Companion to ``test_proxy_project_savings.py``: "Savings by model" and
"Savings by client" on the dashboard used to be built from a tiny
10-request recency window (model) or mislabeled per-project data
(client) because ``SavingsTracker`` never accumulated either durably.
These tests lock in the fix — a ``models``/``clients`` map that
persists and accumulates exactly like the existing ``projects`` map.
"""

from __future__ import annotations

import pytest

from cutctx.proxy.savings_tracker import SavingsTracker


def test_tracker_accumulates_per_model_and_persists(tmp_path):
    path = tmp_path / "savings.json"
    tracker = SavingsTracker(path=str(path))

    tracker.record_request(model="claude-sonnet-4-5", input_tokens=1000, tokens_saved=400)
    tracker.record_request(model="claude-sonnet-4-5", input_tokens=500, tokens_saved=100)
    tracker.record_request(model="deepseek-v4-flash", input_tokens=200, tokens_saved=50)

    models = tracker.stats_preview()["models"]
    assert list(models) == ["claude-sonnet-4-5", "deepseek-v4-flash"]  # sorted by tokens saved desc
    assert models["claude-sonnet-4-5"]["requests"] == 2
    assert models["claude-sonnet-4-5"]["tokens_saved"] == 500
    assert models["deepseek-v4-flash"]["requests"] == 1

    reloaded = SavingsTracker(path=str(path))
    assert reloaded.stats_preview()["models"]["claude-sonnet-4-5"]["tokens_saved"] == 500


def test_per_model_totals_are_not_a_recency_sample(tmp_path):
    """A burst of cheap-model traffic must not make the lifetime model
    breakdown look dominant next to a model that ran for far more
    requests earlier — that was the actual bug: the dashboard fell
    back to grouping only the last ~10 requests."""
    path = tmp_path / "savings.json"
    tracker = SavingsTracker(path=str(path))

    for _ in range(50):
        tracker.record_request(model="claude-sonnet-4-5", input_tokens=1000, tokens_saved=400)
    for _ in range(3):
        tracker.record_request(model="deepseek-v4-flash", input_tokens=100, tokens_saved=90)

    models = tracker.stats_preview()["models"]
    assert models["claude-sonnet-4-5"]["tokens_saved"] == 50 * 400
    assert models["deepseek-v4-flash"]["tokens_saved"] == 3 * 90
    # claude's lifetime share must still dominate despite deepseek being
    # the most *recent* traffic.
    assert models["claude-sonnet-4-5"]["tokens_saved"] > models["deepseek-v4-flash"]["tokens_saved"]


def test_tracker_accumulates_per_client_and_persists(tmp_path):
    path = tmp_path / "savings.json"
    tracker = SavingsTracker(path=str(path))

    tracker.record_request(model="gpt-4o", input_tokens=1000, tokens_saved=400, client="claude-code")
    tracker.record_request(model="gpt-4o", input_tokens=500, tokens_saved=100, client="claude-code")
    tracker.record_request(model="gpt-4o", input_tokens=200, tokens_saved=50, client="opencode")
    tracker.record_request(model="gpt-4o", input_tokens=99, tokens_saved=9)  # unidentified harness

    clients = tracker.stats_preview()["clients"]
    assert list(clients) == ["claude-code", "opencode"]
    assert clients["claude-code"]["requests"] == 2
    assert clients["claude-code"]["tokens_saved"] == 500
    assert clients["opencode"]["requests"] == 1

    # Unidentified-harness traffic still lands in the lifetime totals,
    # it just isn't attributed to any client bucket.
    assert tracker.stats_preview()["lifetime"]["requests"] == 4

    reloaded = SavingsTracker(path=str(path))
    assert reloaded.stats_preview()["clients"]["claude-code"]["tokens_saved"] == 500


def test_per_client_is_distinct_from_per_project(tmp_path):
    """The dashboard bug showed directory names ("headroom",
    "aryansingh") under "Savings by client" because client rows fell
    back to the per-project map. Client and project must be tracked
    (and remain retrievable) independently, even for the same request."""
    path = tmp_path / "savings.json"
    tracker = SavingsTracker(path=str(path))

    tracker.record_request(
        model="gpt-4o", input_tokens=1000, tokens_saved=400, project="headroom", client="opencode"
    )

    preview = tracker.stats_preview()
    assert list(preview["projects"]) == ["headroom"]
    assert list(preview["clients"]) == ["opencode"]
    assert preview["projects"] != preview["clients"]


def test_model_and_client_maps_cap_cardinality(tmp_path):
    from cutctx.proxy.savings_tracker import DEFAULT_MAX_CLIENTS, DEFAULT_MAX_MODELS

    path = tmp_path / "savings.json"
    tracker = SavingsTracker(path=str(path))

    for i in range(DEFAULT_MAX_MODELS + 5):
        tracker.record_request(
            model=f"model-{i}", input_tokens=10, tokens_saved=1, client=f"client-{i}"
        )

    preview = tracker.stats_preview()
    assert len(preview["models"]) <= DEFAULT_MAX_MODELS
    assert len(preview["clients"]) <= DEFAULT_MAX_CLIENTS


@pytest.mark.parametrize("bad_client", ["", "   ", None])
def test_unusable_client_names_are_skipped(tmp_path, bad_client):
    path = tmp_path / "savings.json"
    tracker = SavingsTracker(path=str(path))
    tracker.record_request(model="gpt-4o", input_tokens=10, tokens_saved=5, client=bad_client)
    assert tracker.stats_preview()["clients"] == {}


def test_compress_provider_calls_are_excluded_from_model_breakdown(tmp_path):
    """``/v1/compress`` never calls an upstream model — the ``model`` field
    on those requests is only a tokenizer hint a client-side plugin passes
    in (e.g. opencode's cutctx.ts plugin defaulted it to "claude-sonnet-4-5"
    regardless of the user's actual chat model, like MiMo v2.5). Bucketing
    those calls under "models" mislabeled real per-model inference savings
    on the dashboard, so provider="compress" must be excluded from that
    axis — project/client attribution is still meaningful and kept."""
    path = tmp_path / "savings.json"
    tracker = SavingsTracker(path=str(path))

    tracker.record_request(
        model="mimo-v2.5", input_tokens=1000, tokens_saved=400, client="opencode"
    )
    tracker.record_request(
        model="claude-sonnet-4-5",
        input_tokens=500,
        tokens_saved=100,
        client="opencode",
        provider="compress",
    )

    preview = tracker.stats_preview()
    assert list(preview["models"]) == ["mimo-v2.5"]
    # The compress-endpoint request still counts toward the client and
    # lifetime totals — just not toward the (misleading) model breakdown.
    assert preview["clients"]["opencode"]["requests"] == 2
    assert preview["lifetime"]["requests"] == 2
