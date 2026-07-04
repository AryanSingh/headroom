# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""TDD tests for the WS13 BATCH_ROUTING source registration.

Per artifacts/savings-moat-expansion-specs.md WS13:
"Attribution: price delta recorded as `batch_routing` source."

Additive contract: the savings source model grows from 7 to 8.
"""

from __future__ import annotations

import pytest

from cutctx.savings.types import (
    _DESCRIPTIONS,
    _LABELS,
    SavingsBySource,
    SavingsSource,
)

# ---------------------------------------------------------------------------
# Enum registration
# ---------------------------------------------------------------------------


def test_batch_routing_source_exists() -> None:
    assert hasattr(SavingsSource, "BATCH_ROUTING")
    assert SavingsSource.BATCH_ROUTING.value == "batch_routing"


def test_batch_routing_source_label_and_description() -> None:
    assert SavingsSource.BATCH_ROUTING in _LABELS
    assert SavingsSource.BATCH_ROUTING in _DESCRIPTIONS
    assert "batch" in _LABELS[SavingsSource.BATCH_ROUTING].lower()


# ---------------------------------------------------------------------------
# Additive contract
# ---------------------------------------------------------------------------


def test_existing_source_values_unchanged() -> None:
    """Additive: the 7 original source values must not change."""
    expected = {
        "provider_prompt_cache",
        "cutctx_compression",
        "tool_schema_compaction",
        "api_surface_slimming",
        "semantic_cache",
        "prefix_cache_self_hosted",
        "model_routing",
        "batch_routing",  # new
    }
    actual = {member.value for member in SavingsSource}
    assert expected.issubset(actual)  # additive: other branches may add more sources


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_savings_by_source_accepts_batch_routing() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.BATCH_ROUTING, tokens=0, usd=0.5)  # price delta, not tokens
    assert sbs.get_usd(SavingsSource.BATCH_ROUTING) == pytest.approx(0.5)


def test_savings_by_source_batch_routing_in_total() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.BATCH_ROUTING, usd=0.5)
    sbs.add(SavingsSource.CUTCTX_COMPRESSION, usd=0.1)
    assert sbs.total_usd == pytest.approx(0.6)


def test_savings_by_source_zero_batch_routing_evicts() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.BATCH_ROUTING, usd=0.1)
    assert "batch_routing" in sbs.usd
    sbs.add(SavingsSource.BATCH_ROUTING, usd=-0.1)
    assert "batch_routing" not in sbs.usd


def test_savings_by_source_to_dict_includes_batch_routing() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.BATCH_ROUTING, usd=0.1)
    d = sbs.to_dict()
    assert "batch_routing" in d["usd"]


# ---------------------------------------------------------------------------
# Dashboard tolerance
# ---------------------------------------------------------------------------


def test_dashboard_tolerates_unknown_source() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.BATCH_ROUTING, usd=0.1)
    sbs.add("some_future_source_we_dont_know_about", usd=0.05)
    assert sbs.total_usd == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_from_str_accepts_batch_routing() -> None:
    assert SavingsSource.from_str("batch_routing") == SavingsSource.BATCH_ROUTING
