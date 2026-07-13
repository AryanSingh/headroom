from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from cutctx.cli.main import main
from cutctx.proxy.savings_tracker import SavingsTracker


def _seed_savings_history() -> None:
    tracker = SavingsTracker()
    tracker.record_request(
        model="gpt-4o",
        provider="openai",
        project="headroom-smoke",
        client="codex",
        input_tokens=3600,
        tokens_saved=2000,
        cache_read_tokens=1200,
        savings_by_source_tokens={
            "provider_prompt_cache": 1200,
            "cutctx_compression": 800,
        },
        savings_by_source_usd={
            "provider_prompt_cache": 0.09,
            "cutctx_compression": 0.14,
        },
    )
    tracker.record_request(
        model="claude-3-5-sonnet-20241022",
        provider="anthropic",
        project="headroom-smoke",
        client="codex",
        input_tokens=1400,
        tokens_saved=600,
        savings_by_source_tokens={
            "semantic_cache": 600,
        },
        savings_by_source_usd={
            "semantic_cache": 0.05,
        },
        compression_savings_usd_delta=0.0,
    )
    tracker.record_request(
        model="gpt-5.4",
        provider="openai",
        project="headroom-smoke",
        client="codex",
        input_tokens=2200,
        tokens_saved=1550,
        savings_by_source_tokens={
            "model_routing": 900,
            "tool_schema_compaction": 300,
            "api_surface_slimming": 150,
            "cutctx_compression": 200,
        },
        savings_by_source_usd={
            "model_routing": 0.11,
            "tool_schema_compaction": 0.03,
            "api_surface_slimming": 0.02,
            "cutctx_compression": 0.04,
        },
        compression_savings_usd_delta=0.04,
        model_routing_usd_delta=0.11,
        tool_schema_compaction_usd_delta=0.03,
        api_surface_slimming_usd_delta=0.02,
    )


def _validate_report(payload: dict[str, Any]) -> dict[str, Any]:
    token_sum = int(sum(int(value) for value in payload["savings_by_source"].values()))
    usd_sum = round(sum(float(value) for value in payload["savings_by_source_usd"].values()), 6)
    total_tokens = int(payload["total_tokens_saved"])
    total_usd = round(float(payload["total_usd_saved"]), 6)
    return {
        "tokens_match": total_tokens == token_sum,
        "usd_match": abs(total_usd - usd_sum) < 1e-6,
        "token_total": total_tokens,
        "token_sum": token_sum,
        "usd_total": total_usd,
        "usd_sum": usd_sum,
    }


def generate_buyer_report_smoke(
    *,
    workspace_dir: Path,
    markdown_output: Path,
    json_output: Path,
) -> dict[str, Any]:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    savings_path = workspace_dir / "proxy_savings.json"

    previous_savings_path = os.environ.get("CUTCTX_SAVINGS_PATH")
    os.environ["CUTCTX_SAVINGS_PATH"] = str(savings_path)

    try:
        if savings_path.exists():
            savings_path.unlink()
        _seed_savings_history()

        runner = CliRunner()
        json_result = runner.invoke(main, ["report", "buyer", "--days", "3650", "--format", "json"])
        if json_result.exit_code != 0:
            raise RuntimeError(json_result.output or "buyer report JSON generation failed")
        payload = json.loads(json_result.output)
        payload["validation"] = _validate_report(payload)

        markdown_result = runner.invoke(
            main,
            ["report", "buyer", "--days", "3650", "--format", "markdown"],
        )
        if markdown_result.exit_code != 0:
            raise RuntimeError(markdown_result.output or "buyer report markdown generation failed")

        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(markdown_result.output, encoding="utf-8")

        return payload
    finally:
        if previous_savings_path is None:
            os.environ.pop("CUTCTX_SAVINGS_PATH", None)
        else:
            os.environ["CUTCTX_SAVINGS_PATH"] = previous_savings_path


def main_entry() -> None:
    payload = generate_buyer_report_smoke(
        workspace_dir=Path("artifacts/buyer-report-smoke-workspace"),
        markdown_output=Path("artifacts/buyer-report-smoke.md"),
        json_output=Path("artifacts/buyer-report-smoke.json"),
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main_entry()
