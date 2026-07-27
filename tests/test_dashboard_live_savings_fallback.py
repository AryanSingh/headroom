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
    """Each routing mode must describe what it does, not name a preset.

    Asserted against the behaviour rather than one exact sentence: the Auto
    copy was rewritten in cca958a6 and this test kept failing on the old
    literal even though the guarantee it exists to protect still held.
    """
    source = (ROOT / "dashboard/src/pages/Orchestrator.jsx").read_text()

    # Every selectable mode carries a behavioural description.
    for behaviour in (
        "every request uses the model you asked for",  # off
        "pick a fast, mid, or strong certified model from task complexity",  # auto
        "Choose the cheapest certified compatible model",  # aggressive
    ):
        assert behaviour in source, f"missing behavioural copy: {behaviour!r}"

    # Internal preset identifiers must not appear in the mode picker itself.
    # They are allowed further down, where the detail text names the preset
    # backing the active mode — that is reference information, not the label
    # an operator chooses from.
    picker_start = source.index("const ROUTING_MODES")
    picker = source[picker_start : source.index("];", picker_start)]
    for preset_id in (
        "codex-gpt54mini-high",
        "codex-opencode-slim",
        "oh-my-opencode-slim",
        "economy",
    ):
        assert preset_id not in picker, (
            f"internal preset name leaked into the mode picker: {preset_id!r}"
        )


def test_orchestrator_puts_operating_controls_before_advanced_studios() -> None:
    source = (ROOT / "dashboard/src/pages/Orchestrator.jsx").read_text()

    assert source.index("<h2>Routing mode control</h2>") < source.index("<RoutingStudio />")
    assert 'className="panel orchestrator-mode-panel"' in source
