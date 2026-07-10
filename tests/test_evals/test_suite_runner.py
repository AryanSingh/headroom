from __future__ import annotations

from types import SimpleNamespace


def test_compression_only_runner_loads_verbatim_fixture_cases() -> None:
    from cutctx.evals.runners.compression_only import CompressionOnlyRunner

    runner = CompressionOnlyRunner()
    cases = runner.generate_verbatim_compaction_cases()

    assert len(cases) >= 3
    assert all(case["critical_items"] for case in cases)
    assert any("line 77" in case["critical_items"] for case in cases)


def test_compression_only_runner_evaluates_verbatim_fidelity() -> None:
    from cutctx.evals.runners.compression_only import CompressionOnlyRunner

    runner = CompressionOnlyRunner()
    result = runner.evaluate_verbatim_compaction(
        cases=[
            {
                "id": "verbatim-1",
                "content": """INFO start\nDEBUG cache warmup bucket=artifacts count=14\nDEBUG cache warmup bucket=config count=9\nDEBUG cache warmup bucket=templates count=22\nDEBUG retrying vault lookup attempt=1\nDEBUG retrying vault lookup attempt=2\nTraceback (most recent call last):\n  File \"services/payments/vault.py\", line 77, in issue_token\n    raise PermissionDeniedError(\"vault token expired\")\nPermissionDeniedError: vault token expired\nINFO done\n""",
                "query": "Which file raised `PermissionDeniedError`?",
                "critical_items": [
                    "services/payments/vault.py",
                    "line 77",
                    "PermissionDeniedError: vault token expired",
                ],
            }
        ],
        fidelity_threshold=0.9,
    )

    assert result.benchmark == "verbatim_compaction"
    assert result.accuracy_rate == 1.0
    assert result.critical_item_recall == 1.0
    assert result.verbatim_fidelity == 1.0
    assert result.tokens_per_second is not None
    assert result.passed_cases == 1
    assert result.total_tokens_saved > 0


def test_suite_runner_registers_verbatim_compaction_spec() -> None:
    from cutctx.evals.suite_runner import BENCHMARK_SUITE

    spec = next(spec for spec in BENCHMARK_SUITE if spec.name == "Verbatim Compaction")

    assert spec.runner_type == "compression_only"
    assert spec.primary_metric == "verbatim_fidelity"
    assert spec.pass_threshold == 0.90
    assert spec.sample_size == 3


def test_suite_runner_registers_tool_schema_compaction_spec() -> None:
    from cutctx.evals.suite_runner import BENCHMARK_SUITE

    spec = next(spec for spec in BENCHMARK_SUITE if spec.name == "Tool Schema Compaction")

    assert spec.runner_type == "compression_only"
    assert spec.primary_metric == "tool_schema_integrity"
    assert spec.pass_threshold == 1.0
    assert spec.sample_size == 4


def test_suite_runner_filters_specs_by_runner_type_and_name() -> None:
    from cutctx.evals.suite_runner import SuiteRunner

    runner = SuiteRunner(
        tiers=[1, 2],
        auto_start_proxy=False,
        runner_types=["compression_only"],
        benchmark_names=["CCR Round-trip", "Tool Schema Compaction"],
    )

    specs = runner._get_specs()

    assert [spec.name for spec in specs] == ["CCR Round-trip", "Tool Schema Compaction"]
    assert all(spec.runner_type == "compression_only" for spec in specs)


def test_suite_runner_compression_only_uses_spec_threshold(monkeypatch) -> None:
    from cutctx.evals.runners.compression_only import CompressionOnlyResult, CompressionOnlyRunner
    from cutctx.evals.suite_runner import BenchmarkSpec, SuiteRunner

    def fake_evaluate(self, fidelity_threshold: float = 0.9):  # noqa: ANN001
        assert fidelity_threshold == 0.95
        return CompressionOnlyResult(
            benchmark="verbatim_compaction",
            total_cases=3,
            passed_cases=2,
            failed_cases=1,
            accuracy_rate=0.94,
            avg_compression_ratio=0.4,
            total_original_tokens=100,
            total_compressed_tokens=60,
            total_tokens_saved=40,
            tokens_per_second=1234.5,
            critical_item_recall=0.94,
            verbatim_fidelity=0.94,
        )

    monkeypatch.setattr(CompressionOnlyRunner, "evaluate_verbatim_compaction", fake_evaluate)

    runner = SuiteRunner(tiers=[2], auto_start_proxy=False)
    spec = BenchmarkSpec(
        name="Verbatim Compaction",
        category="compression",
        tier=2,
        runner_type="compression_only",
        sample_size=3,
        primary_metric="verbatim_fidelity",
        pass_threshold=0.95,
    )

    raw = runner._run_compression_only_benchmark(spec)

    assert raw["accuracy_rate"] == 0.94
    assert raw["tokens_per_second"] == 1234.5
    assert raw["critical_item_recall"] == 0.94
    assert raw["verbatim_fidelity"] == 0.94
    assert raw["passed"] is False


def test_suite_runner_before_after_uses_spec_threshold(monkeypatch) -> None:
    from cutctx.evals import datasets as dataset_mod
    from cutctx.evals.runners import before_after as before_after_mod
    from cutctx.evals.suite_runner import BenchmarkSpec, SuiteRunner
    import cutctx.evals.suite_runner as suite_runner_mod

    monkeypatch.setattr(
        dataset_mod,
        "load_dataset_by_name",
        lambda *args, **kwargs: SimpleNamespace(name="fake", cases=[1, 2]),
    )
    monkeypatch.setattr(suite_runner_mod, "_check_proxy", lambda port: False)

    class FakeBeforeAfterRunner:
        def __init__(self, llm_config, use_semantic_similarity=False):  # noqa: ANN001
            self.llm_config = llm_config

        def run(self, suite, progress_callback=None, mode=None):  # noqa: ANN001
            return SimpleNamespace(
                accuracy_preservation_rate=0.92,
                avg_compression_ratio=0.31,
                total_tokens_saved=12,
                total_cases=2,
                duration_seconds=0.05,
            )

    monkeypatch.setattr(before_after_mod, "BeforeAfterRunner", FakeBeforeAfterRunner)

    runner = SuiteRunner(tiers=[2], auto_start_proxy=False)
    spec = BenchmarkSpec(
        name="Synthetic BeforeAfter",
        category="qa",
        tier=2,
        runner_type="before_after",
        sample_size=2,
        dataset_name="rag_samples",
        primary_metric="accuracy_preservation_rate",
        pass_threshold=0.95,
    )

    raw = runner._run_before_after_benchmark(spec, tracker=None)

    assert raw["accuracy_rate"] == 0.92
    assert raw["passed"] is False


def test_suite_runner_tool_schema_compaction_uses_registered_runner(monkeypatch) -> None:
    from cutctx.evals.runners.compression_only import CompressionOnlyResult, CompressionOnlyRunner
    from cutctx.evals.suite_runner import BenchmarkSpec, SuiteRunner

    def fake_evaluate(self):  # noqa: ANN001
        return CompressionOnlyResult(
            benchmark="tool_schema_compaction",
            total_cases=4,
            passed_cases=4,
            failed_cases=0,
            accuracy_rate=1.0,
            avg_compression_ratio=0.18,
            total_original_tokens=80,
            total_compressed_tokens=65,
            total_tokens_saved=15,
            tokens_per_second=987.6,
        )

    monkeypatch.setattr(CompressionOnlyRunner, "evaluate_tool_schema_compaction", fake_evaluate)

    runner = SuiteRunner(tiers=[2], auto_start_proxy=False)
    spec = BenchmarkSpec(
        name="Tool Schema Compaction",
        category="compression",
        tier=2,
        runner_type="compression_only",
        sample_size=4,
        primary_metric="tool_schema_integrity",
        pass_threshold=1.0,
    )

    raw = runner._run_compression_only_benchmark(spec)

    assert raw["accuracy_rate"] == 1.0
    assert raw["tokens_per_second"] == 987.6
    assert raw["passed"] is True
