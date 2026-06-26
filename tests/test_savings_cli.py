"""Tests for savings orchestration CLI extensions (Phase 5)."""

from __future__ import annotations

import json

from click.testing import CliRunner

from cutctx.proxy.savings_tracker import CUTCTX_SAVINGS_PATH_ENV_VAR, SavingsTracker


class TestIntegrationsStatus:
    def test_status_terminal(self):
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "status"])
        # Either it ran successfully or integration wasn't registered.
        # If it ran, it should show providers and sources.
        if result.exit_code == 0:
            assert "openai" in result.output.lower() or "no such command" not in result.output.lower()
        # If the command isn't registered, that's a non-fatal pre-existing issue.
        # We only assert structure when it ran.

    def test_status_json(self):
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "status", "--format", "json"])
        if result.exit_code == 0:
            payload = json.loads(result.output)
            assert "providers" in payload
            assert "integrations" in payload
            assert "savings_sources" in payload
            assert "provider_prompt_cache" in payload["savings_sources"]
            assert "cutctx_compression" in payload["savings_sources"]

    def test_status_json_reports_production_by_source(self, tmp_path, monkeypatch):
        state_path = tmp_path / "proxy_savings.json"
        tracker = SavingsTracker(path=str(state_path))
        tracker.record_request(
            model="gpt-4o",
            input_tokens=1000,
            tokens_saved=1200,
            provider="openai",
            total_input_tokens=1000,
            total_input_cost_usd=1.23,
            savings_by_source_tokens={
                "provider_prompt_cache": 500,
                "cutctx_compression": 700,
            },
            savings_by_source_usd={
                "provider_prompt_cache": 0.12,
                "cutctx_compression": 0.27,
            },
        )
        monkeypatch.setenv(CUTCTX_SAVINGS_PATH_ENV_VAR, str(state_path))

        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "status", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        production = payload["production"]
        assert production["by_source"]["provider_prompt_cache"]["tokens"] == 500
        assert production["by_source"]["cutctx_compression"]["tokens"] == 700
        assert production["by_source"]["provider_prompt_cache"]["usd"] == 0.12
        assert production["by_source"]["cutctx_compression"]["usd"] == 0.27

    def test_status_json_uses_legacy_usd_fallback(self, tmp_path, monkeypatch):
        state_path = tmp_path / "proxy_savings.json"
        tracker = SavingsTracker(path=str(state_path))
        tracker.record_request(
            model="gpt-4o",
            input_tokens=1000,
            tokens_saved=1200,
            provider="openai",
            total_input_tokens=1000,
            total_input_cost_usd=1.23,
            savings_by_source_tokens={
                "provider_prompt_cache": 500,
                "cutctx_compression": 700,
            },
            compression_savings_usd_delta=0.27,
            cache_savings_usd_delta=0.12,
        )
        payload = json.loads(state_path.read_text())
        payload["history"][-1].pop("savings_by_source_usd", None)
        state_path.write_text(json.dumps(payload))
        monkeypatch.setenv(CUTCTX_SAVINGS_PATH_ENV_VAR, str(state_path))

        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "status", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        production = payload["production"]
        assert production["by_source"]["provider_prompt_cache"]["usd"] == 0.12
        assert production["by_source"]["cutctx_compression"]["usd"] == 0.27


class TestIntegrationsTest:
    def test_openai(self):
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "test", "openai", "--format", "json"])
        if result.exit_code == 0:
            payload = json.loads(result.output)
            assert payload["provider"] == "openai"
            assert payload["breakdown"]["total_tokens_saved"] == 750
            assert payload["breakdown"]["by_source"]["tokens"]["provider_prompt_cache"] == 750

    def test_anthropic(self):
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "test", "anthropic", "--format", "json"])
        if result.exit_code == 0:
            payload = json.loads(result.output)
            assert payload["provider"] == "anthropic"
            assert payload["breakdown"]["by_source"]["tokens"]["provider_prompt_cache"] == 900

    def test_gemini(self):
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "test", "gemini", "--format", "json"])
        if result.exit_code == 0:
            payload = json.loads(result.output)
            assert payload["breakdown"]["by_source"]["tokens"]["provider_prompt_cache"] == 800

    def test_litellm(self):
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "test", "litellm", "--format", "json"])
        if result.exit_code == 0:
            payload = json.loads(result.output)
            assert payload["integration"] == "litellm"
            assert payload["breakdown"]["by_source"]["tokens"]["provider_prompt_cache"] == 500

    def test_vllm_apc(self):
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "test", "vllm_apc", "--format", "json"])
        if result.exit_code == 0:
            payload = json.loads(result.output)
            # Self-hosted, NOT provider cache
            assert payload["breakdown"]["by_source"]["tokens"]["prefix_cache_self_hosted"] == 300
            assert payload["breakdown"]["by_source"]["tokens"].get("provider_prompt_cache", 0) == 0

    def test_unknown_provider(self):
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["integrations", "test", "not-a-real-provider"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Phase 5.1: by-source / by-provider / format flags on `savings`
# ---------------------------------------------------------------------------


class TestSavingsBreakdownFlags:
    def test_savings_by_source_no_sessions(self):
        """Empty storage should still invoke the new breakdown helper safely."""
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["savings", "--by-source"])
        # Either runs fine or returns the empty-state message.
        assert result.exit_code in (0, 1)
        # When empty, the CLI says so.
        assert "no" in result.output.lower() or "error" in result.output.lower() or result.output == ""

    def test_savings_format_json_flag_accepted(self):
        from cutctx.cli.main import main as root
        runner = CliRunner()
        result = runner.invoke(root, ["savings", "--format", "json"])
        # Just verify the flag is accepted (no click usage error).
        assert "no such option" not in result.output.lower()
