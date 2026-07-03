from __future__ import annotations

import json

from click.testing import CliRunner

from cutctx.cli.main import main


def test_agent_context_report_markdown_no_data(monkeypatch) -> None:
    monkeypatch.setattr("cutctx.cli.report._collect_savings_history", lambda days: [])
    runner = CliRunner()

    result = runner.invoke(main, ["report", "agent-context"])

    assert result.exit_code == 0, result.output
    assert "# Agent Context Report" in result.output
    assert "No savings-source rows found" in result.output
    assert "Context Assurance: no_data" in result.output
    assert "No local evidence ledger found" in result.output


def test_agent_context_report_json_aggregates_sources(monkeypatch) -> None:
    monkeypatch.setattr(
        "cutctx.cli.report._collect_savings_history",
        lambda days: [
            {
                "tokens_saved": 10,
                "cost_savings_usd": 0.5,
                "savings_by_source_tokens": {"cutctx_compression": 7},
            },
            {
                "tokens_saved": 20,
                "cost_savings_usd": 1.25,
                "savings_by_source_tokens": {
                    "cutctx_compression": 3,
                    "provider_prompt_cache": 20,
                },
            },
        ],
    )
    runner = CliRunner()

    result = runner.invoke(main, ["report", "agent-context", "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "agent_context_report_v1"
    assert payload["summary"]["requests"] == 2
    assert payload["summary"]["tokens_saved"] == 30
    assert payload["summary"]["usd_saved"] == 1.75
    assert payload["savings_by_source_tokens"] == {
        "cutctx_compression": 10,
        "provider_prompt_cache": 20,
    }
