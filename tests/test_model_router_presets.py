"""Tests for named model-routing presets.

Verifies that:
- Default config (no preset) routes identically to today's default.
- "economy" preset enables broader routing with more routes.
- "subrequest-haiku" preset routes internal requests to Haiku-class models.
"""

from __future__ import annotations

import pytest

from cutctx.proxy.model_router import ModelRouterConfig


class TestDefaultPreset:
    """Default (no preset) matches today's behavior."""

    def test_default_config_has_expected_routes(self) -> None:
        cfg = ModelRouterConfig()
        assert len(cfg.routes) == 4
        assert cfg.enabled is False
        assert cfg.downgrade_when == "low_cache_read"

    def test_default_config_not_enabled(self) -> None:
        cfg = ModelRouterConfig()
        assert cfg.enabled is False  # off by default


class TestEconomyPreset:
    """Economy preset enables aggressive downgrade."""

    def test_economy_has_more_routes(self) -> None:
        cfg = ModelRouterConfig.economy_preset()
        assert len(cfg.routes) > 4  # broader than the default 4

    def test_economy_is_enabled(self) -> None:
        cfg = ModelRouterConfig.economy_preset()
        assert cfg.enabled is True

    def test_economy_downgrade_when_is_always(self) -> None:
        cfg = ModelRouterConfig.economy_preset()
        assert cfg.downgrade_when == "always"

    def test_economy_has_sonnet_to_haiku_route(self) -> None:
        cfg = ModelRouterConfig.economy_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert ("claude-sonnet-4-5", "claude-haiku-4-5") in pairs

    def test_economy_has_opus_to_sonnet_route(self) -> None:
        cfg = ModelRouterConfig.economy_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert any(s.startswith("claude-opus") and t.startswith("claude-sonnet") for s, t in pairs)

    def test_economy_has_gemini_route(self) -> None:
        cfg = ModelRouterConfig.economy_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert ("gemini-2.5-pro", "gemini-2.5-flash") in pairs

    def test_economy_thresholds_are_looser(self) -> None:
        cfg = ModelRouterConfig.economy_preset()
        assert cfg.cache_read_threshold >= 0.8
        assert cfg.tool_complexity_threshold >= 5.0


class TestSubrequestHaikuPreset:
    """Subrequest-haiku preset routes internal calls to Haiku-class models."""

    def test_subrequest_haiku_exists(self) -> None:
        cfg = ModelRouterConfig.subrequest_haiku_preset()
        assert cfg is not None
        assert isinstance(cfg, ModelRouterConfig)

    def test_subrequest_haiku_is_enabled(self) -> None:
        cfg = ModelRouterConfig.subrequest_haiku_preset()
        assert cfg.enabled is True

    def test_subrequest_haiku_has_routes(self) -> None:
        cfg = ModelRouterConfig.subrequest_haiku_preset()
        assert len(cfg.routes) > 0

    def test_subrequest_haiku_routes_to_haiku_models(self) -> None:
        cfg = ModelRouterConfig.subrequest_haiku_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        # At least some routes should target Haiku-class models
        haiku_targets = {t for s, t in pairs if "haiku" in t.lower()}
        assert len(haiku_targets) > 0, "No routes to Haiku-class models found"

    def test_subrequest_haiku_routes_opus_to_haiku(self) -> None:
        cfg = ModelRouterConfig.subrequest_haiku_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        # Opus should route to Haiku (direct, not intermediate steps)
        assert any(s.startswith("claude-opus") and "haiku" in t.lower() for s, t in pairs)

    def test_subrequest_haiku_routes_sonnet_to_haiku(self) -> None:
        cfg = ModelRouterConfig.subrequest_haiku_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        # Sonnet should route to Haiku
        assert any("sonnet" in s.lower() and "haiku" in t.lower() for s, t in pairs)

    def test_subrequest_haiku_default_is_off(self) -> None:
        """Default ModelRouterConfig (when not using preset) is still off."""
        cfg = ModelRouterConfig()
        assert cfg.enabled is False
        assert len(cfg.routes) == 4

    def test_subrequest_haiku_downgrade_when(self) -> None:
        cfg = ModelRouterConfig.subrequest_haiku_preset()
        # Should have a defined downgrade_when strategy
        assert cfg.downgrade_when in ["low_cache_read", "always"]


class TestCodexGpt54MiniHighPreset:
    """Canonical preset keeps heavy models requested but routes
    low-complexity work to GPT-5.4 mini with high reasoning."""

    def test_codex_gpt54mini_high_exists(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        assert isinstance(cfg, ModelRouterConfig)

    def test_codex_gpt54mini_high_is_enabled(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        assert cfg.enabled is True

    def test_codex_gpt54mini_high_uses_low_complexity_gate(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        assert cfg.downgrade_when == "low_complexity"

    def test_codex_gpt54mini_high_routes_gpt55_to_gpt54_mini(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert ("gpt-5.5", "gpt-5.4-mini") in pairs

    def test_codex_gpt54mini_high_routes_terra_to_gpt54_mini(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert ("gpt-5.6-terra", "gpt-5.4-mini") in pairs

    def test_codex_gpt54mini_high_routes_claude_opus_to_sonnet(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert ("claude-opus-4-5", "claude-sonnet-4-5") in pairs

    def test_codex_gpt54mini_high_routes_claude_sonnet_to_haiku(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert ("claude-sonnet-4-5", "claude-haiku-4-5") in pairs

    def test_codex_gpt54mini_high_routes_gpt54_to_gpt54_mini(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert ("gpt-5.4", "gpt-5.4-mini") in pairs

    def test_codex_gpt54mini_high_routes_gpt5_to_gpt54_mini(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert ("gpt-5", "gpt-5.4-mini") in pairs

    def test_codex_gpt54mini_high_does_not_force_gpt54_mini_lower(self) -> None:
        cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        pairs = {(r.source, r.target) for r in cfg.routes}
        assert not any(source == "gpt-5.4-mini" for source, _ in pairs)

    def test_codex_gpt54mini_high_keeps_default_config_off(self) -> None:
        cfg = ModelRouterConfig()
        assert cfg.enabled is False

    def test_codex_opencode_slim_alias_still_works(self) -> None:
        cfg = ModelRouterConfig.codex_opencode_slim_preset()
        assert cfg.routes == ModelRouterConfig.codex_gpt54mini_high_preset().routes


class TestPresetSelection:
    """Tests that proxy config routing_preset field maps correctly."""

    def test_none_preset_returns_default(self) -> None:
        preset = None
        if preset == "economy":
            cfg = ModelRouterConfig.economy_preset()
        else:
            cfg = ModelRouterConfig()
        assert cfg.enabled is False
        assert len(cfg.routes) == 4

    def test_economy_preset_selection(self) -> None:
        preset = "economy"
        if preset == "economy":
            cfg = ModelRouterConfig.economy_preset()
        else:
            cfg = ModelRouterConfig()
        assert cfg.enabled is True
        assert len(cfg.routes) > 4

    def test_codex_gpt54mini_high_preset_selection(self) -> None:
        preset = "codex-gpt54mini-high"
        if preset == "codex-gpt54mini-high":
            cfg = ModelRouterConfig.codex_gpt54mini_high_preset()
        else:
            cfg = ModelRouterConfig()
        assert cfg.enabled is True
        assert cfg.downgrade_when == "low_complexity"

    def test_codex_opencode_slim_alias_selection(self) -> None:
        cfg = ModelRouterConfig.from_preset_name("codex-opencode-slim")
        assert cfg is not None
        assert cfg.routes == ModelRouterConfig.codex_gpt54mini_high_preset().routes

    def test_claude_three_tier_eval_is_explicit_and_evidence_gated(self) -> None:
        cfg = ModelRouterConfig.from_preset_name("claude-three-tier-eval")
        assert cfg is not None
        assert cfg.require_calibrated_scorer is True
        opus = next(route for route in cfg.routes if route.source == "claude-opus-4-5")
        assert opus.target == "claude-haiku-4-5"
        assert opus.medium_target == "claude-sonnet-4-5"
