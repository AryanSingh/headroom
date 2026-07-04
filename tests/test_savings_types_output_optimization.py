# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""TDD tests for the WS10 OUTPUT_OPTIMIZATION source registration.

Per artifacts/savings-moat-expansion-specs.md WS10 step 5:
"Attribution: measured savings = (predicted baseline output tokens
from quantile model) − actual; recorded as `output_optimization` source.
Label as estimated in the report (WS2), since baseline is
counterfactual."

Additive contract (same as WS16 and WS11): the savings source model
grows from 8 to 9.
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


def test_output_optimization_source_exists() -> None:
    assert hasattr(SavingsSource, "OUTPUT_OPTIMIZATION")
    assert SavingsSource.OUTPUT_OPTIMIZATION.value == "output_optimization"


def test_output_optimization_source_label_and_description() -> None:
    assert SavingsSource.OUTPUT_OPTIMIZATION in _LABELS
    assert SavingsSource.OUTPUT_OPTIMIZATION in _DESCRIPTIONS
    assert "output" in _LABELS[SavingsSource.OUTPUT_OPTIMIZATION].lower()


# ---------------------------------------------------------------------------
# Additive contract
# ---------------------------------------------------------------------------


def test_existing_source_values_unchanged() -> None:
    """Additive: the 8 baseline + WS10 OUTPUT_OPTIMIZATION + WS11 MEMOIZATION
    must all be present. The 7 original source values must not change."""
    expected = {
        "provider_prompt_cache",
        "cutctx_compression",
        "tool_schema_compaction",
        "api_surface_slimming",
        "semantic_cache",
        "prefix_cache_self_hosted",
        "model_routing",
        "output_optimization",  # WS10
        "memoization",  # WS11
    }
    actual = {member.value for member in SavingsSource}
    assert expected.issubset(actual)  # additive: other branches may add more sources


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_savings_by_source_accepts_output_optimization() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.OUTPUT_OPTIMIZATION, tokens=300, usd=0.15)
    assert sbs.get_tokens(SavingsSource.OUTPUT_OPTIMIZATION) == 300
    assert sbs.get_usd(SavingsSource.OUTPUT_OPTIMIZATION) == pytest.approx(0.15)


def test_savings_by_source_output_optimization_in_total() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.OUTPUT_OPTIMIZATION, tokens=300, usd=0.15)
    sbs.add(SavingsSource.CUTCTX_COMPRESSION, tokens=200, usd=0.10)
    assert sbs.total_tokens == 500
    assert sbs.total_usd == pytest.approx(0.25)


def test_savings_by_source_zero_output_optimization_evicts() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.OUTPUT_OPTIMIZATION, tokens=5)
    assert "output_optimization" in sbs.tokens
    sbs.add(SavingsSource.OUTPUT_OPTIMIZATION, tokens=-5)
    assert "output_optimization" not in sbs.tokens


def test_savings_by_source_to_dict_includes_output_optimization() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.OUTPUT_OPTIMIZATION, tokens=42, usd=0.01)
    d = sbs.to_dict()
    assert "output_optimization" in d["tokens"]
    assert "output_optimization" in d["usd"]


# ---------------------------------------------------------------------------
# Dashboard tolerance
# ---------------------------------------------------------------------------


def test_dashboard_tolerates_unknown_source() -> None:
    sbs = SavingsBySource()
    sbs.add(SavingsSource.OUTPUT_OPTIMIZATION, tokens=42)
    sbs.add("some_future_source_we_dont_know_about", tokens=10)
    assert sbs.total_tokens == 52


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_from_str_accepts_output_optimization() -> None:
    assert SavingsSource.from_str("output_optimization") == SavingsSource.OUTPUT_OPTIMIZATION
