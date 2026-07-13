from __future__ import annotations

import json

from click.testing import CliRunner

from cutctx.cli.main import main


def _write_request_history(tmp_path, rows) -> str:
    path = tmp_path / "request_history.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return str(path)


def _sample_request_history_rows() -> list[dict[str, object]]:
    return [
        {
            "request_id": "trace-1",
            "timestamp": "2026-07-09T12:00:00Z",
            "provider": "openai",
            "decline_reason": "bypass_header",
            "total_latency_ms": 120.5,
            "optimization_latency_ms": 18.2,
            "request_cost_usd": 0.21,
            "routing_metadata": {
                "requested_model": "gpt-5.4",
                "actual_model": "gpt-5.4-mini",
                "routed": True,
            },
            "fallback": {
                "provider": "openai",
                "reason": "connect_error",
            },
        },
        {
            "request_id": "trace-2",
            "timestamp": "2026-07-09T12:05:00Z",
            "provider": "anthropic",
            "decline_reason": "compression_disabled",
            "total_latency_ms": 240.0,
            "optimization_latency_ms": 30.0,
            "request_cost_usd": 0.33,
            "routing_metadata": {
                "requested_model": "claude-3.5",
                "actual_model": "claude-3.5",
                "routed": False,
            },
            "fallback": {
                "provider": "anthropic",
                "reason": "rate_limited",
            },
        },
    ]


def test_agent_context_report_markdown_no_data(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("cutctx.cli.report._collect_savings_history", lambda days: [])
    monkeypatch.setattr(
        "cutctx.cli.report._assurance_section",
        lambda: {"status": "no_data", "note": "No local evidence ledger found."},
    )
    monkeypatch.setattr("cutctx.paths.request_history_path", lambda: tmp_path / "missing.jsonl")
    runner = CliRunner()

    result = runner.invoke(main, ["report", "agent-context"])

    assert result.exit_code == 0, result.output
    assert "# Agent Context Report" in result.output
    assert "No savings-source rows found" in result.output
    assert "## Telemetry Snapshot" in result.output
    assert "- Telemetry status: no_data" in result.output
    assert "No request history found" in result.output
    assert "Context Assurance: no_data" in result.output
    assert "No local evidence ledger found" in result.output


def test_agent_context_report_json_aggregates_sources(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setattr(
        "cutctx.cli.report._assurance_section",
        lambda: {"status": "no_data", "note": "No local evidence ledger found."},
    )
    monkeypatch.setattr(
        "cutctx.paths.request_history_path",
        lambda: tmp_path / "request_history.jsonl",
    )
    _write_request_history(tmp_path, _sample_request_history_rows())
    runner = CliRunner()

    result = runner.invoke(
        main,
        ["report", "agent-context", "--days", "0", "--format", "json"],
    )

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
    telemetry = payload["telemetry"]
    assert telemetry["status"] == "observed"
    assert telemetry["requests_observed"] == 2
    assert telemetry["providers"] == {"anthropic": 1, "openai": 1}
    assert telemetry["fallback"] == {
        "count": 2,
        "providers": {"anthropic": 1, "openai": 1},
        "reasons": {"connect_error": 1, "rate_limited": 1},
    }
    assert telemetry["decline_reasons"] == {
        "bypass_header": 1,
        "compression_disabled": 1,
    }
    assert telemetry["latency_ms"] == {"avg": 180.25, "p50": 120.5, "p95": 240.0}
    assert telemetry["optimization_latency_ms"] == {
        "avg": 24.1,
        "p50": 18.2,
        "p95": 30.0,
    }


def test_agent_context_report_markdown_includes_telemetry_snapshot(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setattr(
        "cutctx.cli.report._assurance_section",
        lambda: {"status": "no_data", "note": "No local evidence ledger found."},
    )
    monkeypatch.setattr(
        "cutctx.paths.request_history_path",
        lambda: tmp_path / "request_history.jsonl",
    )
    _write_request_history(tmp_path, _sample_request_history_rows())
    runner = CliRunner()

    result = runner.invoke(main, ["report", "agent-context", "--days", "0"])

    assert result.exit_code == 0, result.output
    assert "## Telemetry Snapshot" in result.output
    assert "- Telemetry status: observed" in result.output
    assert "- Request log rows observed: 2" in result.output
    assert "- Fallback events: 2" in result.output
    assert "- Providers: anthropic=1, openai=1" in result.output
    assert "- Fallback providers: anthropic=1, openai=1" in result.output
    assert "- Decline reasons: bypass_header=1, compression_disabled=1" in result.output
    assert "- Latency p50/p95: 120.50 ms / 240.00 ms" in result.output
    assert "- Optimization latency p50/p95: 18.20 ms / 30.00 ms" in result.output
    assert (
        "- Telemetry note: Telemetry snapshot derived from durable request history."
        in result.output
    )
