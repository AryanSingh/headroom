from __future__ import annotations

import json

import pytest

from benchmarks import run_comparison
from benchmarks.llmlingua_compressor import _chunks


class _Compressor:
    name = "fixture"

    def compress(self, text: str) -> tuple[str, float]:
        return text[: max(1, len(text) // 2)], 1.5


def test_direct_comparison_records_tokenizer_quality_and_repetitions(tmp_path) -> None:
    rows = run_comparison.run_benchmark(
        _Compressor(),
        [("fixture.txt", "alpha beta gamma delta")],
        "unit",
        runs=2,
        warmup_runs=1,
        encoding_name="cl100k_base",
    )

    assert len(rows) == 1
    assert rows[0].runs == 2
    assert rows[0].f1_score is not None
    assert rows[0].rouge_l_score is not None
    assert rows[0].quality_score is not None


def test_bootstrap_intervals_and_paired_deltas_are_deterministic() -> None:
    first = run_comparison.bootstrap_interval([0.1, 0.2, 0.3])
    second = run_comparison.bootstrap_interval([0.1, 0.2, 0.3])

    assert first == second
    assert first is not None
    assert first["samples"] == 3
    assert first["lower_95"] <= first["estimate"] <= first["upper_95"]

    rows = [
        run_comparison.BenchmarkResult("cutctx", "unit", "a", 10, 5, 0.5, 2, 0.8),
        run_comparison.BenchmarkResult("llmlingua-2", "unit", "a", 10, 4, 0.4, 3, 0.7),
    ]
    deltas = run_comparison.paired_comparator_deltas(rows)

    assert deltas["candidate_minus_baseline_reduction"]["estimate"] == pytest.approx(-0.1)
    assert deltas["candidate_minus_baseline_latency_ms"]["estimate"] == -1


def test_main_writes_versioned_evidence_schema(tmp_path, monkeypatch) -> None:
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "sample.txt").write_text("alpha beta gamma delta", encoding="utf-8")
    output = tmp_path / "result.json"
    monkeypatch.setattr(run_comparison, "CutctxCompressor", _Compressor)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_comparison.py",
            "--fixtures-dir",
            str(fixtures),
            "--output",
            str(output),
            "--runs",
            "2",
        ],
    )

    run_comparison.main()

    evidence = json.loads(output.read_text(encoding="utf-8"))
    assert evidence["schema_version"] == 4
    assert evidence["tokenizer"] == "cl100k_base"
    assert evidence["runs"] == 2
    assert evidence["fixture_sha256"]
    assert evidence["quality_metric"].endswith("not downstream task quality")
    assert isinstance(evidence["git_worktree_dirty"], bool)
    assert evidence["results"][0]["quality_score"] is not None
    assert evidence["uncertainty"]["by_method"]["fixture"]["reduction"]["samples"] == 1


def test_llmlingua_chunks_long_fixtures_below_model_window() -> None:
    chunks = _chunks("word " * 800)

    assert len(chunks) == 5
    assert all(len(chunk.split()) <= 160 for chunk in chunks)
