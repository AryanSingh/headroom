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


def test_capabilities_state_claude_desktop_and_streaming_scope_truthfully() -> None:
    source = (ROOT / "dashboard/src/data/capabilities.js").read_text()

    assert "clients that can point their API base URL" in source
    assert "Claude Desktop hosted model requests are excluded" in source
    assert "Claude Desktop MCP" in source
    assert "compress, retrieve, and stats tools" in source
    assert "response stream passthrough" in source
    assert "in-flight compression and PII redaction" not in source


def test_orchestrator_modes_explain_behavior_before_internal_preset_names() -> None:
    source = (ROOT / "dashboard/src/pages/Orchestrator.jsx").read_text()

    assert "Route clear low-complexity work to a lower-cost compatible model" in source
    assert "Choose the cheapest certified compatible model" in source


def test_orchestrator_puts_operating_controls_before_advanced_studios() -> None:
    source = (ROOT / "dashboard/src/pages/Orchestrator.jsx").read_text()

    assert source.index("<h2>Routing mode control</h2>") < source.index("<RoutingStudio />")
    assert 'className="panel orchestrator-mode-panel"' in source
