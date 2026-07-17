from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from cutctx.evals.offline_downstream import run_offline_downstream_evaluation
from cutctx.product_evidence import (
    aggregate_savings_receipt,
    build_product_evidence,
    render_product_evidence_markdown,
    select_downstream_task_report,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_savings_receipt_uses_first_request_and_additive_source_totals() -> None:
    rows = [
        {
            "timestamp": "2026-07-14T10:00:00+00:00",
            "tokens_saved": 100,
            "savings_by_source_tokens": {"cutctx_compression": 80, "model_routing": 20},
            "savings_by_source_usd": {"cutctx_compression": 0.08, "model_routing": 0.02},
        },
        {
            "timestamp": "2026-07-15T10:00:00+00:00",
            "tokens_saved": 50,
            "savings_by_source_tokens": {"provider_prompt_cache": 50},
            "savings_by_source_usd": {"provider_prompt_cache": 0.01},
        },
    ]

    receipt = aggregate_savings_receipt(rows)

    assert receipt["status"] == "available"
    assert receipt["requests"] == 2
    assert receipt["tokens_saved"] == 150
    assert receipt["usd_saved"] == 0.11
    assert receipt["savings_by_source_tokens"] == {
        "cutctx_compression": 80,
        "model_routing": 20,
        "provider_prompt_cache": 50,
    }


def test_savings_receipt_preserves_legacy_attribution_without_double_counting() -> None:
    receipt = aggregate_savings_receipt(
        [{"tokens_saved": 40, "compression_savings_usd": 0.03, "cache_savings_usd": 0.01}]
    )

    assert receipt["usd_saved"] == 0.04
    assert receipt["savings_by_source_usd"] == {
        "cutctx_compression": 0.03,
        "provider_prompt_cache": 0.01,
    }


def test_downstream_report_selection_rejects_compression_only_metrics(tmp_path: Path) -> None:
    compression_only = tmp_path / "artifacts" / "compression" / "results.json"
    downstream = tmp_path / "artifacts" / "downstream" / "results.json"
    _write_json(
        compression_only,
        {
            "timestamp": "2026-07-15T11:00:00+00:00",
            "benchmarks": [{"metric": "information_recall", "accuracy_rate": 1.0}],
        },
    )
    _write_json(
        downstream,
        {
            "timestamp": "2026-07-14T11:00:00+00:00",
            "summary": {"all_passed": True},
            "benchmarks": [
                {
                    "metric": "exact_match_flexible-extract",
                    "baseline_score": 0.8,
                    "cutctx_score": 0.79,
                }
            ],
        },
    )

    selected = select_downstream_task_report(tmp_path)

    assert selected is not None
    assert selected["path"] == "artifacts/downstream/results.json"
    assert selected["payload"]["summary"]["all_passed"] is True


def test_product_evidence_embeds_hashed_artifacts_and_activation_receipts(tmp_path: Path) -> None:
    routing_path = tmp_path / "artifacts" / "model-routing-quality.json"
    _write_json(
        routing_path,
        {"schema_version": 1, "cases": 59, "metrics": {"unsafe_downgrade_rate": 0.0}},
    )
    generated_at = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    rows = [
        {
            "timestamp": "2026-07-15T10:00:00+00:00",
            "tokens_saved": 25,
            "savings_by_source_tokens": {"cutctx_compression": 25},
            "savings_by_source_usd": {"cutctx_compression": 0.005},
        }
    ]

    payload = build_product_evidence(root=tmp_path, savings_rows=rows, days=7, now=generated_at)

    routing = payload["evidence"]["model_routing"]
    assert routing["status"] == "available"
    assert routing["sha256"] == hashlib.sha256(routing_path.read_bytes()).hexdigest()
    assert routing["payload"]["cases"] == 59
    assert payload["activation"]["first_request"]["tokens_saved"] == 25
    assert payload["activation"]["period"]["period_days"] == 7
    assert payload["limitations"]


def test_product_evidence_rejects_stale_release_posture(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "artifacts" / "release-evidence-status.json",
        {"schema_version": 1, "market_claim_eligible": True},
    )
    _write_json(
        tmp_path / "artifacts" / "benchmark-release-manifest.json",
        {
            "schema_version": 1,
            "git_sha": "abc",
            "python_version": "3.12",
            "platform": "test",
            "architecture": "test",
            "packages": {},
            "checkpoint_id": "model",
            "seed": 42,
            "fixture_hashes": {"missing-fixture": "stale"},
            "timestamp": "2026-07-15T00:00:00+00:00",
            "provider_arms": {"raw_passthrough": "available"},
        },
    )
    _write_json(
        tmp_path / "artifacts" / "benchmark-release-bundle.json",
        {
            "schema_version": 1,
            "reports": {
                "raw_passthrough": {"status": "available", "path": "missing", "sha256": "x"},
                "content_router": {"status": "available", "path": "missing", "sha256": "x"},
                "verbatim_compactor": {"status": "available", "path": "missing", "sha256": "x"},
                "canonical_llmlingua_xlmr_large": {
                    "status": "available",
                    "path": "missing",
                    "sha256": "x",
                },
                "provider_native_cache_or_compaction": {
                    "status": "unavailable",
                    "reason": "no signal",
                },
            },
        },
    )

    payload = build_product_evidence(root=tmp_path, savings_rows=[])

    release = payload["evidence"]["release_posture"]
    assert release["status"] == "unavailable"
    assert "integrity" in release["reason"]
    assert any("release evidence integrity" in item.lower() for item in payload["limitations"])


def test_product_evidence_zero_state_is_valid_and_markdown_is_buyer_readable(
    tmp_path: Path,
) -> None:
    payload = build_product_evidence(
        root=tmp_path,
        savings_rows=[],
        days=7,
        now=datetime(2026, 7, 15, tzinfo=timezone.utc),
    )

    assert payload["activation"]["first_request"]["status"] == "no_data"
    assert payload["activation"]["period"]["status"] == "no_data"
    markdown = render_product_evidence_markdown(payload)
    assert "# Cutctx Product Evidence Receipt" in markdown
    assert "No persisted request savings are available" in markdown
    assert "Downstream task quality" in markdown


def test_evidence_cli_writes_portable_json(tmp_path: Path) -> None:
    from unittest.mock import patch

    from cutctx.cli.main import main

    output = tmp_path / "receipt.json"
    runner = CliRunner()
    with (
        patch("cutctx.cli.evidence._collect_savings_history", return_value=[]),
        patch("cutctx.cli.evidence.Path.cwd", return_value=tmp_path),
    ):
        result = runner.invoke(main, ["evidence", "--format", "json", "--output", str(output)])

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["period_days"] == 7
    assert "Product evidence written" in result.output


def test_offline_downstream_evaluation_scores_executed_task_outcomes() -> None:
    payload = run_offline_downstream_evaluation()

    benchmark = payload["benchmarks"][0]
    assert benchmark["metric"] == "accuracy"
    assert benchmark["baseline_score"] == 1.0
    assert benchmark["cutctx_score"] == 1.0
    assert benchmark["passed"] is True
    assert benchmark["n_samples"] >= 4
    assert payload["task_outcomes"]
    assert all(row["baseline_correct"] for row in payload["task_outcomes"])


def test_offline_downstream_cli_writes_report_selected_by_evidence(tmp_path: Path) -> None:
    from cutctx.cli.main import main

    output = tmp_path / "artifacts" / "downstream-task-quality" / "results.json"
    result = CliRunner().invoke(main, ["evals", "downstream", "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert output.is_file()
    selected = select_downstream_task_report(tmp_path)
    assert selected is not None
    assert selected["path"] == "artifacts/downstream-task-quality/results.json"
