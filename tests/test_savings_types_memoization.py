# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""TDD tests for the WS11 MEMOIZATION source registration in savings types.

Per artifacts/savings-moat-expansion-specs.md WS11 step 5:
"Attribution: avoided request's estimated input tokens recorded as
`memoization` source."

Additive contract (same as WS16): the savings source model grows
from 7 to 8. Older consumers that key off the canonical string
values are unaffected. Consumers that aggregate unknown sources
must tolerate them.
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


def test_memoization_source_exists() -> None:
    assert hasattr(SavingsSource, "MEMOIZATION")
    assert SavingsSource.MEMOIZATION.value == "memoization"


def test_memoization_source_label_and_description() -> None:
    assert SavingsSource.MEMOIZATION in _LABELS
    assert SavingsSource.MEMOIZATION in _DESCRIPTIONS
    assert "memoization" in _LABELS[SavingsSource.MEMOIZATION].lower()
    assert "ws11" in _DESCRIPTIONS[SavingsSource.MEMOIZATION].lower() or (
        "memoiz" in _DESCRIPTIONS[SavingsSource.MEMOIZATION].lower()
    )


# ---------------------------------------------------------------------------
# Additive contract — no existing source names changed
# ---------------------------------------------------------------------------


def test_existing_source_values_unchanged() -> None:
    """The 7 baseline source values must not change."""
    expected = {
        "provider_prompt_cache",
        "cutctx_compression",
        "tool_schema_compaction",
        "api_surface_slimming",
        "semantic_cache",
        "prefix_cache_self_hosted",
        "model_routing",
        "memoization",  # new
    }
    actual = {member.value for member in SavingsSource}
    assert actual == expected


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_savings_by_source_accepts_memoization() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.MEMOIZATION, tokens=100, usd=0.05)
    assert sbs.get_tokens(SavingsSource.MEMOIZATION) == 100
    assert sbs.get_usd(SavingsSource.MEMOIZATION) == pytest.approx(0.05)


def test_savings_by_source_memoization_in_total() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.MEMOIZATION, tokens=200, usd=0.10)
    sbs.add(SavingsSource.CUTCTX_COMPRESSION, tokens=100, usd=0.05)
    assert sbs.total_tokens == 300
    assert sbs.total_usd == pytest.approx(0.15)


def test_savings_by_source_zero_memoization_evicts() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.MEMOIZATION, tokens=10)
    assert "memoization" in sbs.tokens
    sbs.add(SavingsSource.MEMOIZATION, tokens=-10)
    assert "memoization" not in sbs.tokens


def test_savings_by_source_to_dict_includes_memoization() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.MEMOIZATION, tokens=42, usd=0.01)
    d = sbs.to_dict()
    assert "memoization" in d["tokens"]
    assert "memoization" in d["usd"]


# ---------------------------------------------------------------------------
# Dashboard tolerance (same as WS16)
# ---------------------------------------------------------------------------


def test_dashboard_tolerates_unknown_source() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.MEMOIZATION, tokens=42)
    sbs.add("some_future_source_we_dont_know_about", tokens=10)
    assert sbs.total_tokens == 52
    assert "some_future_source_we_dont_know_about" in sbs.tokens


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_from_str_accepts_memoization() -> None:
    assert SavingsSource.from_str("memoization") == SavingsSource.MEMOIZATION
