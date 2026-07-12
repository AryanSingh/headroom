from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_orchestrator_reads_top_level_live_model_routing_savings() -> None:
    source = (ROOT / "dashboard/src/pages/Orchestrator.jsx").read_text()

    assert "stats?.savings_by_source?.usd?.model_routing" in source
    assert "stats?.savings_by_source?.tokens?.model_routing" in source


def test_capabilities_explains_zero_compression_when_cache_is_protected() -> None:
    source = (ROOT / "dashboard/src/pages/Capabilities.jsx").read_text()

    assert "cache_protected_tokens" in source
    assert "left unchanged intentionally" in source
