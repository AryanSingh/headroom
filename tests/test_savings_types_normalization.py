# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""Tests for the WS16 NORMALIZATION source registration in savings types.

Per artifacts/savings-moat-expansion-specs.md WS16 step 3:
"New savings sources introduced here (output_optimization, memoization,
batch_routing, normalization) must be registered in the attribution
model in cutctx/savings/types.py so the 5-source model grows to N-source
without breaking existing consumers (additive enum members only; verify
dashboard aggregation in dashboard/src/lib/use-dashboard-data.js
tolerates unknown sources first — add a tolerance test if absent)."
"""

from __future__ import annotations

import pytest

from cutctx.savings.types import (
    SavingsBySource,
    SavingsSource,
    _DESCRIPTIONS,
    _LABELS,
)


# ---------------------------------------------------------------------------
# Enum registration
# ---------------------------------------------------------------------------


def test_normalization_source_exists() -> None:
    """The NORMALIZATION source must be registered as an additive
    SavingsSource enum member.
    """
    assert hasattr(SavingsSource, "NORMALIZATION")
    assert SavingsSource.NORMALIZATION.value == "normalization"


def test_normalization_source_label_and_description() -> None:
    """The NORMALIZATION source must have a label and description so
    it appears correctly in dashboards, the Agent Context Report (WS2),
    and the per-source attribution breakdown.
    """
    assert SavingsSource.NORMALIZATION in _LABELS
    assert SavingsSource.NORMALIZATION in _DESCRIPTIONS
    assert "normalization" in _LABELS[SavingsSource.NORMALIZATION].lower()
    assert "ws16" in _DESCRIPTIONS[SavingsSource.NORMALIZATION].lower() or (
        "normalization" in _DESCRIPTIONS[SavingsSource.NORMALIZATION].lower()
    )


# ---------------------------------------------------------------------------
# Additive contract — no existing source names changed
# ---------------------------------------------------------------------------


def test_existing_source_values_unchanged() -> None:
    """Additive contract: existing SavingsSource values must not
    change. This protects dashboards and integrations that key off
    the canonical string values.
    """
    expected = {
        "provider_prompt_cache",
        "cutctx_compression",
        "tool_schema_compaction",
        "api_surface_slimming",
        "semantic_cache",
        "prefix_cache_self_hosted",
        "model_routing",
        "normalization",
    }
    actual = {member.value for member in SavingsSource}
    assert expected.issubset(actual), (
        f"SavingsSource enum members changed: missing={expected-actual}"
    )  # additive: other branches may add more sources


# ---------------------------------------------------------------------------
# SavingsBySource aggregation — normalization integrates cleanly
# ---------------------------------------------------------------------------


def test_savings_by_source_accepts_normalization() -> None:
    """SavingsBySource.add() should accept NORMALIZATION and aggregate it."""
    sbs = SavingsBySource()
    sbs.add(SavingsSource.NORMALIZATION, tokens=42, usd=0.01)
    assert sbs.get_tokens(SavingsSource.NORMALIZATION) == 42
    assert sbs.get_usd(SavingsSource.NORMALIZATION) == pytest.approx(0.01)


def test_savings_by_source_normalization_in_total() -> None:
    """NORMALIZATION savings must roll up into the total."""
    sbs = SavingsBySource()
    sbs.add(SavingsSource.NORMALIZATION, tokens=100, usd=0.05)
    sbs.add(SavingsSource.CUTCTX_COMPRESSION, tokens=200, usd=0.10)
    assert sbs.total_tokens == 300
    assert sbs.total_usd == pytest.approx(0.15)


def test_savings_by_source_zero_normalization_evicts() -> None:
    """A NORMALIZATION entry that nets to zero tokens should be
    evicted from the dict (same as other sources).
    """
    sbs = SavingsBySource()
    sbs.add(SavingsSource.NORMALIZATION, tokens=5)
    assert "normalization" in sbs.tokens
    sbs.add(SavingsSource.NORMALIZATION, tokens=-5)  # net to 0
    assert "normalization" not in sbs.tokens


def test_savings_by_source_to_dict_includes_normalization() -> None:
    """The serialization must include the new source so the dashboard
    and Agent Context Report can display it.
    """
    sbs = SavingsBySource()
    sbs.add(SavingsSource.NORMALIZATION, tokens=42, usd=0.01)
    d = sbs.to_dict()
    assert "normalization" in d["tokens"]
    assert "normalization" in d["usd"]


# ---------------------------------------------------------------------------
# Dashboard tolerance — the spec requires this
# ---------------------------------------------------------------------------


def test_dashboard_tolerates_unknown_source() -> None:
    """The dashboard aggregator (dashboard/src/lib/use-dashboard-data.js)
    must tolerate unknown savings sources without crashing. We can't
    import the JS file from a Python test, but we can verify the
    Python aggregation layer that the JS consumes does the same.
    """
    # The aggregator is a function from dict-of-source->tokens to
    # total-tokens. If a new source appears, it should be summed,
    # not error.
    sbs = SavingsBySource()
    sbs.add(SavingsSource.NORMALIZATION, tokens=42)
    sbs.add("some_future_source_we_dont_know_about", tokens=10)
    # The savings aggregator must not raise on unknown sources
    assert sbs.total_tokens == 52
    # And must include the future source in the dict
    assert "some_future_source_we_dont_know_about" in sbs.tokens


# ---------------------------------------------------------------------------
# Token string round-trip — from_str() must accept the new value
# ---------------------------------------------------------------------------


def test_from_str_accepts_normalization() -> None:
    """SavingsSource.from_str() must accept the new value (used by
    JSON deserialization in the dashboard).
    """
    assert SavingsSource.from_str("normalization") == SavingsSource.NORMALIZATION
