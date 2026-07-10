"""Tests benchmark CLI and runner."""

from __future__ import annotations

import json


class TestBenchmarkRunner:
    """Verify BenchmarkRunner adapter registry and execution."""

    def test_benchmark_runner_registers_all_compressors(self) -> None:
        """All expected adapters should be present."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        adapters = runner.list_compressors()
        names = {adapter.name for adapter in adapters}

        expected = {
            "raw_passthrough",
            "smart_crusher",
            "log",
            "search",
            "diff",
            "code",
            "kompress",
            "llmlingua",
            "drain3",
            "html",
            "verbatim_compactor",
            "content_router",
        }

        assert expected <= names
        assert "content_router" in names
        assert any(adapter.name == "content_router" and adapter.available for adapter in adapters)

    def test_raw_passthrough_adapter_is_an_exact_zero_savings_baseline(self) -> None:
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.core import EvalCase

        runner = BenchmarkRunner()
        adapter = next(adapter for adapter in runner.list_compressors() if adapter.name == "raw_passthrough")
        result = adapter.compress_fn("retain this context exactly")

        assert result.compressed == "retain this context exactly"
        assert result.tokens_saved == 0

    def test_content_router_benchmark_adapter_is_deterministic(self, monkeypatch) -> None:
        """CI router benchmark should not invoke heavyweight ML fallback by default."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.transforms import content_router as router_mod

        captured_configs = []
        original_init = router_mod.ContentRouter.__init__

        def spy_init(self, config=None, observer=None):  # type: ignore[no-untyped-def]
            captured_configs.append(config)
            original_init(self, config=config, observer=observer)

        monkeypatch.setattr(router_mod.ContentRouter, "__init__", spy_init)

        BenchmarkRunner()

        router_config = next(
            config
            for config in captured_configs
            if isinstance(config, router_mod.ContentRouterConfig)
        )
        assert router_config.enable_kompress is False
        assert router_config.fallback_strategy is router_mod.CompressionStrategy.PASSTHROUGH

    def test_content_router_benchmark_adapter_uses_case_query_as_context(self, monkeypatch) -> None:
        """Benchmark adapter should pass EvalCase.query into the router."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.transforms import content_router as router_mod

        captured_contexts: list[str] = []
        original_compress = router_mod.ContentRouter.compress

        def spy_compress(self, content, context="", **kwargs):  # type: ignore[no-untyped-def]
            captured_contexts.append(context)
            return original_compress(self, content, context=context, **kwargs)

        monkeypatch.setattr(router_mod.ContentRouter, "compress", spy_compress)

        runner = BenchmarkRunner()
        adapter = next(a for a in runner.list_compressors() if a.name == "content_router")

        from cutctx.evals.core import EvalCase

        case = EvalCase(id="code-1", context="function demo() {}", query="Which function matters?")
        assert adapter.compress_case_fn is not None
        adapter.compress_case_fn(case)

        assert captured_contexts[-1] == "Which function matters?"

    def test_code_benchmark_adapter_preserves_query_named_symbol(self) -> None:
        """Case-aware code compression should protect symbols named in the query."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.core import EvalCase

        runner = BenchmarkRunner()
        adapter = next(a for a in runner.list_compressors() if a.name == "code")

        case = EvalCase(
            id="code-query-1",
            context="""
async def fetch_with_retry(client, url, retries=3):
    try:
        return await client.get(url)
    except httpx.HTTPError as exc:
        raise RuntimeError(str(exc))
""",
            query="Which exception type is retried in fetch_with_retry?",
            ground_truth="httpx.HTTPError",
        )

        assert adapter.compress_case_fn is not None
        result = adapter.compress_case_fn(case)
        assert "fetch_with_retry" in result.compressed
        assert "httpx.HTTPError" in result.compressed

    def test_benchmark_runner_runs_tool_outputs(self) -> None:
        """Running the tool_outputs dataset should produce result rows."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.datasets import load_tool_output_samples

        dataset = load_tool_output_samples()
        runner = BenchmarkRunner()
        result = runner.run(
            dataset=dataset,
            compressors=["content_router", "smart_crusher", "log", "search"],
            n=1,
            parallel=1,
            seed=42,
        )

        assert result.seed == 42
        assert len(result.compressors) == 4
        assert result.datasets
        assert len(result.results) == 4
        assert {row.compressor for row in result.results} == {
            "content_router",
            "smart_crusher",
            "log",
            "search",
        }

        content_router_row = next(
            row for row in result.results if row.compressor == "content_router"
        )
        assert content_router_row.avg_ms >= 0
        assert content_router_row.tokens_saved >= 0

    def test_verbatim_compactor_adapter_preserves_exact_critical_lines(self) -> None:
        """Dedicated compaction mode should preserve exact path/error strings."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.core import EvalCase

        runner = BenchmarkRunner()
        adapter = next(a for a in runner.list_compressors() if a.name == "verbatim_compactor")

        case = EvalCase(
            id="verbatim-1",
            context="""INFO start\nDEBUG cache hit\nDEBUG cache hit\nTraceback (most recent call last):\n  File \"services/payments/vault.py\", line 77, in issue_token\n    raise PermissionDeniedError(\"vault token expired\")\nPermissionDeniedError: vault token expired\nINFO rollback finished\n""",
            query="Which file raised `PermissionDeniedError`?",
            metadata={
                "critical_items": [
                    "services/payments/vault.py",
                    "line 77",
                    "PermissionDeniedError: vault token expired",
                ]
            },
        )

        assert adapter.compress_case_fn is not None
        result = adapter.compress_case_fn(case)
        assert "services/payments/vault.py" in result.compressed
        assert "PermissionDeniedError: vault token expired" in result.compressed
        assert result.tokens_saved > 0

    def test_builtin_benchmark_breadth_datasets_are_available_locally(
        self,
        monkeypatch,
    ) -> None:
        """Local breadth datasets should register and load by name."""
        from cutctx.evals import datasets as dataset_mod
        from cutctx.evals.core import EvalCase, EvalSuite

        expected = ["code_samples", "rag_samples", "mixed_agent_traces", "verbatim_compaction"]

        flattened = {
            dataset_name
            for category_names in dataset_mod.list_available_datasets().values()
            for dataset_name in category_names
        }
        assert set(expected) <= flattened

        for name in expected:
            monkeypatch.setitem(
                dataset_mod.DATASET_REGISTRY[name],
                "loader",
                lambda *, _name=name, **kwargs: EvalSuite(
                    name=_name,
                    cases=[
                        EvalCase(
                            id=f"{_name}-1",
                            context=f"{_name} context",
                            query="Summarize the payload.",
                        )
                    ],
                ),
            )

        for name in expected:
            suite = dataset_mod.load_dataset_by_name(name)
            assert suite.name == name
            assert len(suite.cases) == 1
            assert suite.cases[0].id == f"{name}-1"

    def test_benchmark_runner_runs_builtin_breadth_datasets(self) -> None:
        """Benchmark runner should preserve dataset names for new local breadth sets."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.datasets import (
            load_code_samples,
            load_mixed_agent_traces,
            load_rag_samples,
        )

        runner = BenchmarkRunner()
        suites = [load_code_samples(), load_rag_samples(), load_mixed_agent_traces()]

        results = [
            runner.run(
                dataset=suite,
                compressors=["content_router"],
                n=1,
                parallel=1,
                seed=42,
            )
            for suite in suites
        ]

        assert [result.datasets for result in results] == [
            ["CodeSamples"],
            ["RAGSamples"],
            ["MixedAgentTraces"],
        ]
        assert all(len(result.results) == 1 for result in results)

    def test_verbatim_compaction_dataset_has_fixed_fixtures(self) -> None:
        """Dedicated verbatim suite should ship local fixed fixtures with exact critical strings."""
        from cutctx.evals.datasets import load_verbatim_compaction_samples

        suite = load_verbatim_compaction_samples()

        assert suite.name == "VerbatimCompactionSamples"
        assert len(suite.cases) >= 3
        assert all(case.metadata.get("critical_items") for case in suite.cases)
        assert any("line 77" in case.metadata["critical_items"] for case in suite.cases)

    def test_code_samples_content_router_recovers_nonzero_savings(self) -> None:
        """Built-in code fixtures should exercise real code compression, not passthrough."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.datasets import load_code_samples

        runner = BenchmarkRunner()
        suite = load_code_samples()

        result = runner.run(
            dataset=suite,
            compressors=["content_router"],
            metrics=["tokens_saved", "critical_item_recall", "verbatim_fidelity"],
            n=len(suite.cases),
            parallel=1,
            seed=42,
        )

        row = result.results[0]
        assert row.tokens_saved > 0
        assert row.critical_item_recall == 1.0
        assert row.verbatim_fidelity == 1.0

    def test_benchmark_runner_computes_critical_item_recall_from_case_metadata(self) -> None:
        """Critical items declared by fixtures should become a first-class metric."""
        from cutctx.evals.benchmark_runner import (
            BenchmarkRunner,
            CompressorAdapter,
            CompressorResult,
        )
        from cutctx.evals.core import EvalCase, EvalSuite

        runner = BenchmarkRunner()
        runner._adapters["critical_probe"] = CompressorAdapter(
            name="critical_probe",
            available=True,
            display_name="CriticalProbe",
            compress_fn=lambda text: CompressorResult(
                compressed="owner=payments-platform request=build_441",
                tokens_saved=10,
                duration_ms=1.0,
            ),
        )

        suite = EvalSuite(
            name="CriticalItems",
            cases=[
                EvalCase(
                    id="critical-1",
                    context="FeatureFlagMismatchError owner=payments-platform request=build_441",
                    query="Who owns the broken build?",
                    ground_truth="payments-platform",
                    metadata={
                        "critical_items": [
                            "FeatureFlagMismatchError",
                            "payments-platform",
                            "build_441",
                        ]
                    },
                )
            ],
        )

        result = runner.run(
            dataset=suite,
            compressors=["critical_probe"],
            metrics=["ratio", "critical_item_recall"],
            n=1,
            parallel=1,
            seed=42,
        )

        row = result.results[0]
        assert row.critical_item_recall == 2 / 3

    def test_benchmark_runner_prefers_declared_critical_items_over_ground_truth(self) -> None:
        """Explicit critical fixture strings should be authoritative for fidelity checks."""
        from cutctx.evals.benchmark_runner import (
            BenchmarkRunner,
            CompressorAdapter,
            CompressorResult,
        )
        from cutctx.evals.core import EvalCase, EvalSuite

        runner = BenchmarkRunner()
        runner._adapters["declared_critical_probe"] = CompressorAdapter(
            name="declared_critical_probe",
            available=True,
            display_name="DeclaredCriticalProbe",
            compress_fn=lambda text: CompressorResult(
                compressed='File "services/payments/vault.py", line 77, in issue_token',
                tokens_saved=10,
                duration_ms=1.0,
            ),
        )

        suite = EvalSuite(
            name="DeclaredCriticalItems",
            cases=[
                EvalCase(
                    id="declared-critical-1",
                    context='File "services/payments/vault.py", line 77, in issue_token',
                    query="Which file and line raised the error?",
                    ground_truth="services/payments/vault.py:77",
                    metadata={
                        "critical_items": [
                            "services/payments/vault.py",
                            "line 77",
                        ]
                    },
                )
            ],
        )

        result = runner.run(
            dataset=suite,
            compressors=["declared_critical_probe"],
            metrics=["critical_item_recall", "verbatim_fidelity"],
            n=1,
            parallel=1,
            seed=42,
        )

        row = result.results[0]
        assert row.critical_item_recall == 1.0
        assert row.verbatim_fidelity == 1.0

    def test_benchmark_runner_computes_throughput_and_verbatim_fidelity(self) -> None:
        """Benchmark rows should expose throughput and verbatim preservation metrics."""
        from cutctx.evals.benchmark_runner import (
            BenchmarkRunner,
            CompressorAdapter,
            CompressorResult,
        )
        from cutctx.evals.core import EvalCase, EvalSuite

        runner = BenchmarkRunner()
        runner._adapters["verbatim_probe"] = CompressorAdapter(
            name="verbatim_probe",
            available=True,
            display_name="VerbatimProbe",
            compress_fn=lambda text: CompressorResult(
                compressed="keep request=build_441 but omit the error type",
                tokens_saved=10,
                duration_ms=50.0,
            ),
        )

        suite = EvalSuite(
            name="VerbatimSuite",
            cases=[
                EvalCase(
                    id="verbatim-1",
                    context="FeatureFlagMismatchError request=build_441 owner=payments-platform",
                    query="Who owns the broken build?",
                    metadata={"critical_items": ["FeatureFlagMismatchError", "build_441"]},
                )
            ],
        )

        result = runner.run(
            dataset=suite,
            compressors=["verbatim_probe"],
            metrics=["tokens_per_second", "verbatim_fidelity"],
            n=1,
            parallel=1,
            seed=42,
        )

        row = result.results[0]
        assert row.tokens_per_second is not None
        assert row.tokens_per_second > 0
        assert row.verbatim_fidelity == 0.5

    def test_llmlingua_benchmark_adapter_runs_one_case(self, monkeypatch) -> None:
        """LLMLingua adapter should remain runnable on the benchmark EvalCase surface."""
        from types import SimpleNamespace

        import cutctx.transforms.llmlingua_compressor as llm_mod
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.core import EvalCase, EvalSuite

        class FakeLLMLinguaCompressor:
            def compress(self, text: str) -> SimpleNamespace:
                return SimpleNamespace(compressed=f"compressed::{text}")

        monkeypatch.setattr(llm_mod, "LLMLinguaCompressor", FakeLLMLinguaCompressor)

        runner = BenchmarkRunner()
        suite = EvalSuite(
            name="LLMLinguaAdapterSuite",
            cases=[
                EvalCase(
                    id="llm-1",
                    context="Traceback in payments service line 77",
                    query="Where did the failure happen?",
                    metadata={"critical_items": ["payments", "line 77"]},
                )
            ],
        )

        result = runner.run(
            dataset=suite,
            compressors=["llmlingua"],
            metrics=["ratio", "critical_item_recall"],
            n=1,
            parallel=1,
            seed=42,
        )

        assert len(result.results) == 1
        row = result.results[0]
        assert row.compressor == "llmlingua"
        assert row.errors == 0
        assert row.critical_item_recall == 1.0

    def test_llmlingua_benchmark_adapter_accepts_explicit_model(self, monkeypatch) -> None:
        """Research runs can select a smaller official checkpoint explicitly."""
        import cutctx.transforms.llmlingua_compressor as llm_mod
        from cutctx.evals.benchmark_runner import BenchmarkRunner

        observed: dict[str, object] = {}

        class FakeLLMLinguaCompressor:
            def __init__(self, config) -> None:  # noqa: ANN001
                observed["model_name"] = config.model_name

            def compress(self, text: str):  # noqa: ANN201
                return type(
                    "Result",
                    (),
                    {"compressed": text, "used_fallback": False},
                )()

        monkeypatch.setattr(llm_mod, "LLMLinguaCompressor", FakeLLMLinguaCompressor)

        BenchmarkRunner(
            llmlingua_model="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
        )

        assert observed["model_name"] == (
            "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
        )

    def test_llmlingua_benchmark_adapter_marks_runtime_fallback_as_error(
        self, monkeypatch
    ) -> None:
        """LLMLingua runtime fallback should not look like a valid benchmark result."""
        from types import SimpleNamespace

        import cutctx.transforms.llmlingua_compressor as llm_mod
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.core import EvalCase, EvalSuite

        class FakeLLMLinguaCompressor:
            def compress(self, text: str) -> SimpleNamespace:
                return SimpleNamespace(
                    compressed=text,
                    used_fallback=True,
                    fallback_reason="runtime_error",
                )

        monkeypatch.setattr(llm_mod, "LLMLinguaCompressor", FakeLLMLinguaCompressor)

        runner = BenchmarkRunner()
        suite = EvalSuite(
            name="LLMLinguaFallbackSuite",
            cases=[
                EvalCase(
                    id="llm-fallback-1",
                    context="Traceback in payments service line 77",
                    query="Where did the failure happen?",
                )
            ],
        )

        result = runner.run(
            dataset=suite,
            compressors=["llmlingua"],
            metrics=["ratio"],
            n=1,
            parallel=1,
            seed=42,
        )

        assert len(result.results) == 1
        row = result.results[0]
        assert row.compressor == "llmlingua"
        assert row.errors == 1

    def test_benchmark_runner_supports_untimed_warmup_cases(self) -> None:
        """Warmup cases should execute before timed verification runs."""
        from cutctx.evals.benchmark_runner import (
            BenchmarkRunner,
            CompressorAdapter,
            CompressorResult,
        )
        from cutctx.evals.core import EvalCase, EvalSuite

        runner = BenchmarkRunner()
        call_count = 0

        def compress_fn(text: str) -> CompressorResult:
            nonlocal call_count
            call_count += 1
            return CompressorResult(compressed=text, tokens_saved=0, duration_ms=1.0)

        runner._adapters["warmup_probe"] = CompressorAdapter(
            name="warmup_probe",
            available=True,
            display_name="WarmupProbe",
            compress_fn=compress_fn,
        )

        suite = EvalSuite(
            name="WarmupSuite",
            cases=[
                EvalCase(id="warmup-1", context="alpha", query="q1"),
                EvalCase(id="warmup-2", context="beta", query="q2"),
            ],
        )

        result = runner.run(
            dataset=suite,
            compressors=["warmup_probe"],
            metrics=["ratio"],
            n=2,
            parallel=1,
            seed=42,
            warmup_cases=1,
        )

        assert result.results[0].n == 2
        assert call_count == 3

    def test_benchmark_runner_prefers_case_aware_adapter_path(self) -> None:
        """Case-aware adapters should receive the full EvalCase, not only raw text."""
        from cutctx.evals.benchmark_runner import (
            BenchmarkRunner,
            CompressorAdapter,
            CompressorResult,
        )
        from cutctx.evals.core import EvalCase, EvalSuite

        runner = BenchmarkRunner()
        seen_queries: list[str] = []

        runner._adapters["case_probe"] = CompressorAdapter(
            name="case_probe",
            available=True,
            display_name="CaseProbe",
            compress_fn=lambda text: CompressorResult(compressed=text, tokens_saved=0, duration_ms=1.0),
            compress_case_fn=lambda case: (
                seen_queries.append(case.query)
                or CompressorResult(compressed=case.context, tokens_saved=0, duration_ms=1.0)
            ),
        )

        suite = EvalSuite(
            name="CaseAwareSuite",
            cases=[EvalCase(id="case-1", context="alpha", query="preserve alpha")],
        )

        runner.run(
            dataset=suite,
            compressors=["case_probe"],
            metrics=["ratio"],
            n=1,
            parallel=1,
            seed=42,
        )

        assert seen_queries == ["preserve alpha"]


class TestBenchmarkReport:
    """Verify report dataclasses stay JSON-serializable and readable."""

    def test_benchmark_report_to_dict(self) -> None:
        """Suite and result dicts should serialize to JSON."""
        from cutctx.evals.benchmark_report import (
            BenchmarkSuiteResult,
            CompressorBenchmarkResult,
        )

        single = CompressorBenchmarkResult(
            dataset="ToolOutputSamples",
            compressor="content_router",
            n=5,
            ratio=0.35,
            tokens_saved=1200,
            tokens_per_second=640.0,
            avg_ms=12.34,
            p50_ms=10.5,
            f1=0.78,
            rouge_l=0.82,
            information_recall=0.90,
            critical_item_recall=1.0,
            verbatim_fidelity=1.0,
            exact_match=0.0,
            errors=0,
            skipped=False,
        )

        row_dict = single.to_dict()
        assert row_dict["dataset"] == "ToolOutputSamples"
        assert row_dict["compressor"] == "content_router"
        assert row_dict["ratio"] == 0.35
        assert row_dict["tokens_saved"] == 1200
        assert row_dict["tokens_per_second"] == 640.0
        assert row_dict["critical_item_recall"] == 1.0
        assert row_dict["verbatim_fidelity"] == 1.0
        assert row_dict["skipped"] is False
        json.dumps(row_dict)

        suite = BenchmarkSuiteResult(
            seed=42,
            compressors=["content_router"],
            datasets=["ToolOutputSamples"],
            results=[single],
            metadata={"llmlingua_model": "example/checkpoint"},
        )

        suite_dict = suite.to_dict()
        assert suite_dict["seed"] == 42
        assert len(suite_dict["results"]) == 1
        assert suite_dict["totals"]["datasets"] == 1
        assert suite_dict["totals"]["compressors"] == 1
        assert suite_dict["totals"]["cells"] == 1
        assert suite_dict["metadata"]["llmlingua_model"] == "example/checkpoint"
        json.dumps(suite_dict)

    def test_markdown_output(self) -> None:
        """Markdown output should contain the expected headers and values."""
        from cutctx.evals.benchmark_report import (
            BenchmarkSuiteResult,
            CompressorBenchmarkResult,
        )

        r1 = CompressorBenchmarkResult(
            dataset="ToolOutputSamples",
            compressor="content_router",
            n=5,
            ratio=0.35,
            tokens_saved=1200,
            avg_ms=10.0,
            p50_ms=8.0,
            f1=0.78,
            errors=0,
        )
        r2 = CompressorBenchmarkResult(
            dataset="ToolOutputSamples",
            compressor="smart_crusher",
            n=5,
            ratio=0.42,
            tokens_saved=1000,
            avg_ms=5.0,
            p50_ms=4.0,
            f1=0.85,
            errors=0,
        )

        suite = BenchmarkSuiteResult(
            seed=42,
            compressors=["content_router", "smart_crusher"],
            datasets=["ToolOutputSamples"],
            results=[r1, r2],
        )

        markdown = suite.to_markdown("ratio")
        assert "Compression Ratio" in markdown
        assert "Dataset" in markdown
        assert "ContentRouter" in markdown
        assert "SmartCrusher" in markdown
        assert "ToolOutputSamples" in markdown
        assert "35.0%" in markdown
        assert "42.0%" in markdown

        throughput_markdown = suite.to_markdown("tokens_per_second")
        assert "Tokens / Second" in throughput_markdown

        relative_markdown = suite.to_relative_markdown("tokens_saved")
        assert "Relative Delta vs ContentRouter for Tokens Saved" in relative_markdown
        assert "0.0%" in relative_markdown
        assert "-16.7%" in relative_markdown

        fidelity_suite = BenchmarkSuiteResult(
            seed=42,
            compressors=["content_router"],
            datasets=["ToolOutputSamples"],
            results=[
                CompressorBenchmarkResult(
                    dataset="ToolOutputSamples",
                    compressor="content_router",
                    n=5,
                    ratio=0.35,
                    tokens_saved=1200,
                    tokens_per_second=800.0,
                    avg_ms=10.0,
                    p50_ms=8.0,
                    verbatim_fidelity=1.0,
                    errors=0,
                )
            ],
        )
        fidelity_markdown = fidelity_suite.to_markdown("verbatim_fidelity")
        assert "Verbatim Fidelity" in fidelity_markdown
        assert "1.000" in fidelity_markdown

        fidelity_html = fidelity_suite.to_html("verbatim_fidelity")
        assert "<table>" in fidelity_html
        assert "Verbatim Fidelity" in fidelity_html

    def test_benchmark_report_can_emit_relative_delta_sections(self) -> None:
        from cutctx.cli.evals import _build_html_report, _build_markdown_report
        from cutctx.evals.benchmark_report import BenchmarkSuiteResult, CompressorBenchmarkResult

        suite = BenchmarkSuiteResult(
            seed=9,
            compressors=["content_router", "llmlingua"],
            datasets=["CodeSamples"],
            results=[
                CompressorBenchmarkResult(
                    dataset="CodeSamples",
                    compressor="content_router",
                    n=2,
                    ratio=0.80,
                    tokens_saved=20,
                    avg_ms=10.0,
                    p50_ms=10.0,
                    errors=0,
                ),
                CompressorBenchmarkResult(
                    dataset="CodeSamples",
                    compressor="llmlingua",
                    n=2,
                    ratio=1.0,
                    tokens_saved=0,
                    avg_ms=8.0,
                    p50_ms=8.0,
                    errors=0,
                ),
            ],
        )

        markdown = _build_markdown_report(suite, ["ratio", "tokens_saved"])
        assert "## Compression Ratio by Dataset" in markdown
        assert "## Relative Delta vs ContentRouter for Compression Ratio" in markdown
        assert "## Relative Delta vs ContentRouter for Tokens Saved" in markdown

        html = _build_html_report(suite, ["ratio", "tokens_saved"])
        assert "Relative Delta vs ContentRouter for Compression Ratio" in html
        assert "Relative Delta vs ContentRouter for Tokens Saved" in html

    def test_benchmark_report_preserves_dataset_names_across_outputs(self, tmp_path) -> None:
        """Dataset names should survive JSON and markdown reporting unchanged."""
        from cutctx.cli.evals import _build_markdown_report
        from cutctx.evals.benchmark_report import (
            BenchmarkSuiteResult,
            CompressorBenchmarkResult,
        )

        suite = BenchmarkSuiteResult(
            seed=7,
            compressors=["content_router"],
            datasets=["code_samples", "rag_samples", "mixed_agent_traces"],
            results=[
                CompressorBenchmarkResult(
                    dataset="code_samples",
                    compressor="content_router",
                    n=1,
                    ratio=0.52,
                    tokens_saved=11,
                    avg_ms=1.0,
                    p50_ms=1.0,
                    errors=0,
                ),
                CompressorBenchmarkResult(
                    dataset="rag_samples",
                    compressor="content_router",
                    n=1,
                    ratio=0.61,
                    tokens_saved=9,
                    avg_ms=1.1,
                    p50_ms=1.1,
                    errors=0,
                ),
                CompressorBenchmarkResult(
                    dataset="mixed_agent_traces",
                    compressor="content_router",
                    n=1,
                    ratio=0.73,
                    tokens_saved=7,
                    avg_ms=1.2,
                    p50_ms=1.2,
                    errors=0,
                ),
            ],
        )

        json_path = tmp_path / "benchmark.json"
        suite.save(json_path)
        saved = json.loads(json_path.read_text(encoding="utf-8"))

        assert saved["datasets"] == ["code_samples", "rag_samples", "mixed_agent_traces"]
        assert [row["dataset"] for row in saved["results"]] == [
            "code_samples",
            "rag_samples",
            "mixed_agent_traces",
        ]

        markdown = _build_markdown_report(suite, ["ratio"])
        assert "Datasets: code_samples, rag_samples, mixed_agent_traces" in markdown
        assert "| code_samples |" in markdown
        assert "| rag_samples |" in markdown
        assert "| mixed_agent_traces |" in markdown


class TestBenchmarkCLI:
    """Verify benchmark CLI command wiring."""

    def test_benchmark_cli_help(self) -> None:
        """Running ``cutctx evals benchmark --help`` must exit 0."""
        from click.testing import CliRunner

        from cutctx.cli.evals import evals

        runner = CliRunner()
        result = runner.invoke(evals, ["benchmark", "--help"])
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
        assert "benchmark" in result.output.lower()

    def test_benchmark_cli_can_configure_hf_transport_for_live_baselines(self, monkeypatch) -> None:
        """The explicit transport controls must be set before benchmark execution."""
        from click.testing import CliRunner

        import cutctx.cli.evals as cli_evals

        captured: dict[str, str | None] = {}

        def fake_run_benchmark(**_kwargs):  # noqa: ANN003
            captured["llmlingua_model"] = _kwargs.get("llmlingua_model")
            captured["hf_hub_disable_xet"] = cli_evals.os.environ.get(
                "HF_HUB_DISABLE_XET"
            )
            captured["hf_hub_download_timeout"] = cli_evals.os.environ.get(
                "HF_HUB_DOWNLOAD_TIMEOUT"
            )

        monkeypatch.delenv("HF_HUB_DISABLE_XET", raising=False)
        monkeypatch.delenv("HF_HUB_DOWNLOAD_TIMEOUT", raising=False)
        monkeypatch.setattr(cli_evals, "_run_benchmark", fake_run_benchmark)

        result = CliRunner().invoke(
            cli_evals.evals,
            [
                "benchmark",
                "--disable-hf-xet",
                "--hf-download-timeout",
                "600",
                "--llmlingua-model",
                "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
            ],
        )

        assert result.exit_code == 0, result.output
        assert captured["hf_hub_disable_xet"] == "1"
        assert captured["hf_hub_download_timeout"] == "600"
        assert captured["llmlingua_model"] == (
            "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank"
        )

    def test_benchmark_cli_llmlingua_preset_expands_expected_surface(self, monkeypatch) -> None:
        """Named LLMLingua preset should keep datasets, compressors, and metrics stable."""
        from click.testing import CliRunner

        import cutctx.cli.evals as cli_evals
        from cutctx.evals import datasets as dataset_mod
        from cutctx.evals.benchmark_report import (
            BenchmarkSuiteResult,
            CompressorBenchmarkResult,
        )
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.core import EvalCase, EvalSuite

        expected_datasets = [
            "code_samples",
            "rag_samples",
            "mixed_agent_traces",
            "verbatim_compaction",
        ]
        expected_metrics = [
            "ratio",
            "tokens_saved",
            "tokens_per_second",
            "f1",
            "information_recall",
            "critical_item_recall",
            "verbatim_fidelity",
        ]
        load_calls: list[tuple[str, dict[str, object]]] = []
        run_calls: list[dict[str, object]] = []

        for name in expected_datasets:
            monkeypatch.setitem(
                dataset_mod.DATASET_REGISTRY[name],
                "loader",
                lambda *, _name=name, **kwargs: EvalSuite(
                    name=_name,
                    cases=[
                        EvalCase(
                            id=f"{_name}-1",
                            context=f"{_name} context",
                            query="What should be preserved?",
                        )
                    ],
                ),
            )

        original_load_dataset_by_name = dataset_mod.load_dataset_by_name

        def spy_load_dataset_by_name(name: str, n: int | None = None, **kwargs):
            load_calls.append((name, {"n": n, **kwargs}))
            return original_load_dataset_by_name(name, n=n, **kwargs)

        monkeypatch.setattr(dataset_mod, "load_dataset_by_name", spy_load_dataset_by_name)

        def fake_run(
            self,  # noqa: ANN001
            dataset,
            compressors=None,
            metrics=None,
            n: int = 50,
            parallel: int = 4,
            seed: int = 42,
        ) -> BenchmarkSuiteResult:
            selected_compressors = list(compressors or [])
            selected_metrics = list(metrics or [])
            run_calls.append(
                {
                    "dataset": dataset.name,
                    "compressors": selected_compressors,
                    "metrics": selected_metrics,
                    "n": n,
                }
            )
            return BenchmarkSuiteResult(
                seed=seed,
                compressors=selected_compressors,
                datasets=[dataset.name],
                results=[
                    CompressorBenchmarkResult(
                        dataset=dataset.name,
                        compressor=compressor,
                        n=len(dataset.cases),
                        ratio=0.5,
                        tokens_saved=10,
                        tokens_per_second=1000.0,
                        avg_ms=1.0,
                        p50_ms=1.0,
                        f1=1.0,
                        information_recall=1.0,
                        critical_item_recall=1.0,
                        verbatim_fidelity=1.0,
                        errors=0,
                    )
                    for compressor in selected_compressors
                ],
            )

        monkeypatch.setattr(BenchmarkRunner, "run", fake_run)
        runner = CliRunner()

        result = runner.invoke(
            cli_evals.evals,
            ["benchmark", "--preset", "llmlingua_research", "--parallel", "1"],
        )

        assert result.exit_code == 0, result.output
        assert "Preset:           llmlingua_research" in result.output
        assert [name for name, _ in load_calls] == expected_datasets
        assert len(run_calls) == 4
        for call in run_calls:
            assert call["compressors"] == ["content_router", "llmlingua"]
            assert call["metrics"] == expected_metrics

    def test_verify_cli_help(self) -> None:
        """Running ``cutctx verify --help`` must exit 0."""
        from click.testing import CliRunner

        from cutctx.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["verify", "--help"])
        assert result.exit_code == 0, f"Exit {result.exit_code}: {result.output}"
        assert "verify" in result.output.lower()

    def test_benchmark_cli_accepts_builtin_breadth_datasets(
        self,
        monkeypatch,
    ) -> None:
        """CLI should target the new local breadth datasets without downloads."""
        from click.testing import CliRunner

        from cutctx.cli.evals import evals
        from cutctx.evals import datasets as dataset_mod
        from cutctx.evals.benchmark_report import (
            BenchmarkSuiteResult,
            CompressorBenchmarkResult,
        )
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.core import EvalCase, EvalSuite

        expected = ["code_samples", "rag_samples", "mixed_agent_traces"]
        load_calls: list[tuple[str, dict[str, object]]] = []
        run_calls: list[str] = []

        for name in expected:
            monkeypatch.setitem(
                dataset_mod.DATASET_REGISTRY[name],
                "loader",
                lambda *, _name=name, **kwargs: EvalSuite(
                    name=_name,
                    cases=[
                        EvalCase(
                            id=f"{_name}-1",
                            context=f"{_name} context",
                            query="What should be preserved?",
                        )
                    ],
                ),
            )

        original_load_dataset_by_name = dataset_mod.load_dataset_by_name

        def spy_load_dataset_by_name(name: str, n: int | None = None, **kwargs):
            load_calls.append((name, {"n": n, **kwargs}))
            return original_load_dataset_by_name(name, n=n, **kwargs)

        monkeypatch.setattr(dataset_mod, "load_dataset_by_name", spy_load_dataset_by_name)

        def fake_run(
            self,  # noqa: ANN001
            dataset,
            compressors=None,
            metrics=None,
            n: int = 50,
            parallel: int = 4,
            seed: int = 42,
        ) -> BenchmarkSuiteResult:
            run_calls.append(dataset.name)
            compressor_names = list(compressors or ["content_router"])
            return BenchmarkSuiteResult(
                seed=seed,
                compressors=compressor_names,
                datasets=[dataset.name],
                results=[
                    CompressorBenchmarkResult(
                        dataset=dataset.name,
                        compressor=compressor_names[0],
                        n=len(dataset.cases),
                        ratio=0.5,
                        tokens_saved=10,
                        avg_ms=1.0,
                        p50_ms=1.0,
                        f1=1.0,
                        information_recall=1.0,
                        errors=0,
                    )
                ],
            )

        monkeypatch.setattr(BenchmarkRunner, "run", fake_run)
        runner = CliRunner()

        result = runner.invoke(
            evals,
            [
                "benchmark",
                "-d",
                "code_samples",
                "-d",
                "rag_samples",
                "-d",
                "mixed_agent_traces",
                "-c",
                "content_router",
                "--metrics",
                "tokens_per_second",
                "--metrics",
                "verbatim_fidelity",
                "--parallel",
                "1",
            ],
        )

        assert result.exit_code == 0, result.output
        assert [name for name, _ in load_calls] == expected
        assert run_calls == expected
        for name in expected:
            assert f"Loading dataset: {name}" in result.output

    def test_benchmark_cli_can_emit_html_report(self, tmp_path, monkeypatch) -> None:
        """Benchmark CLI should support HTML report output for benchmark artifacts."""
        from click.testing import CliRunner

        from cutctx.cli.evals import evals
        from cutctx.evals.benchmark_report import BenchmarkSuiteResult, CompressorBenchmarkResult
        from cutctx.evals.benchmark_runner import BenchmarkRunner

        def fake_run(self, dataset, compressors=None, metrics=None, n=50, parallel=4, seed=42):  # noqa: ANN001
            compressor_names = list(compressors or ["verbatim_compactor"])
            return BenchmarkSuiteResult(
                seed=seed,
                compressors=compressor_names,
                datasets=[dataset.name],
                results=[
                    CompressorBenchmarkResult(
                        dataset=dataset.name,
                        compressor=compressor_names[0],
                        n=1,
                        ratio=0.5,
                        tokens_saved=10,
                        tokens_per_second=1234.0,
                        avg_ms=1.0,
                        p50_ms=1.0,
                        f1=1.0,
                        information_recall=1.0,
                        critical_item_recall=1.0,
                        verbatim_fidelity=1.0,
                        errors=0,
                    )
                ],
            )

        monkeypatch.setattr(BenchmarkRunner, "run", fake_run)
        output = tmp_path / "benchmark.json"

        runner = CliRunner()
        result = runner.invoke(
            evals,
            [
                "benchmark",
                "-d",
                "verbatim_compaction",
                "-c",
                "verbatim_compactor",
                "--output",
                str(output),
                "--html",
            ],
        )

        assert result.exit_code == 0, result.output
        html_path = output.with_suffix(".html")
        assert html_path.exists()
        html = html_path.read_text(encoding="utf-8")
        assert "Cutctx Compressor Benchmark Report" in html
        assert "VerbatimCompactor" in html


class TestVerifyReport:
    """Verify CI report helpers keep the requested shape."""

    def test_verify_report_builder_and_markdown(self) -> None:
        """The verify report should include SHA, metrics, and pass/fail rows."""
        from cutctx.cli import evals as cli_evals
        from cutctx.evals.benchmark_report import (
            BenchmarkSuiteResult,
            CompressorBenchmarkResult,
        )

        row = CompressorBenchmarkResult(
            dataset="ToolOutputSamples",
            compressor="content_router",
            n=8,
            ratio=0.7912,
            tokens_saved=335,
            avg_ms=24.47,
            p50_ms=18.12,
            f1=1.0,
            information_recall=1.0,
            critical_item_recall=1.0,
            errors=0,
            skipped=False,
        )
        suite = BenchmarkSuiteResult(
            seed=42,
            compressors=["content_router"],
            datasets=["ToolOutputSamples"],
            results=[row],
        )

        report = cli_evals._build_verify_report(
            suite,
            git_sha="abc123",
            selected_datasets=["tool_outputs"],
            selected_compressors=["content_router"],
            thresholds={
                "min_f1": 0.9,
                "min_information_recall": 0.9,
                "max_compression_ratio": 0.95,
                "max_latency_ms": 250.0,
                "min_critical_item_recall": 0.9,
                "min_verbatim_fidelity": 0.9,
                "min_tokens_per_second": 0.0,
            },
            skipped_compressors=[],
        )

        assert report["git_sha"] == "abc123"
        assert report["pass"] is True
        assert report["results"][0]["critical_item_recall"] == 1.0
        assert report["results"][0]["critical_item_recall_source"] == "benchmark_metric"
        assert report["results"][0]["status"] == "PASS"

        markdown = cli_evals._render_verify_report(report, fmt="markdown")
        assert "# Cutctx Verify Report" in markdown
        assert "Git SHA: `abc123`" in markdown
        assert "ToolOutputSamples" in markdown
        assert "content_router" in markdown

    def test_verify_report_fails_on_verbatim_fidelity_or_throughput_regression(self) -> None:
        """Verify report should surface dedicated fidelity and throughput regressions."""
        from cutctx.cli import evals as cli_evals
        from cutctx.evals.benchmark_report import BenchmarkSuiteResult, CompressorBenchmarkResult

        row = CompressorBenchmarkResult(
            dataset="VerbatimCompactionSamples",
            compressor="verbatim_compactor",
            n=3,
            ratio=0.62,
            tokens_saved=120,
            tokens_per_second=80.0,
            avg_ms=40.0,
            p50_ms=35.0,
            f1=0.99,
            information_recall=1.0,
            critical_item_recall=1.0,
            verbatim_fidelity=0.5,
            errors=0,
            skipped=False,
        )
        suite = BenchmarkSuiteResult(
            seed=42,
            compressors=["verbatim_compactor"],
            datasets=["VerbatimCompactionSamples"],
            results=[row],
        )

        report = cli_evals._build_verify_report(
            suite,
            git_sha="abc123",
            selected_datasets=["verbatim_compaction"],
            selected_compressors=["verbatim_compactor"],
            thresholds={
                "min_f1": 0.9,
                "min_information_recall": 0.9,
                "max_compression_ratio": 0.95,
                "max_latency_ms": 250.0,
                "min_critical_item_recall": 0.9,
                "min_verbatim_fidelity": 0.9,
                "min_tokens_per_second": 500.0,
            },
            skipped_compressors=[],
        )

        assert report["pass"] is False
        assert any("verbatim_fidelity" in reason for reason in report["results"][0]["reasons"])
        assert any("tokens_per_second" in reason for reason in report["results"][0]["reasons"])

    def test_verify_cli_json_and_ci_exit(self, monkeypatch) -> None:
        """The CLI should emit JSON and fail CI when the report fails."""
        import json as json_module

        from click.testing import CliRunner

        import cutctx.cli.evals as cli_evals
        from cutctx.cli.main import main

        failing_report = {
            "git_sha": "abc123",
            "generated_at": "2026-07-08T00:00:00+00:00",
            "dataset": "tool_outputs",
            "datasets": ["tool_outputs"],
            "compressors": ["content_router"],
            "thresholds": {
                "min_f1": 0.9,
                "min_information_recall": 0.9,
                "max_compression_ratio": 0.95,
                "max_latency_ms": 250.0,
            },
            "summary": {
                "datasets": 1,
                "compressors": 1,
                "rows": 1,
                "passed": 0,
                "failed": 1,
                "skipped": 0,
                "duration_ms": 12.5,
                "tokens_saved": 0,
            },
            "results": [
                {
                    "dataset": "ToolOutputSamples",
                    "compressor": "content_router",
                    "tokens_saved": 0,
                    "compression_ratio": 1.0,
                    "f1": 0.5,
                    "information_recall": 0.4,
                    "critical_item_recall": 0.4,
                    "critical_item_recall_source": "information_recall_proxy",
                    "latency_ms": 300.0,
                    "p50_latency_ms": 300.0,
                    "status": "FAIL",
                    "pass": False,
                    "reasons": ["tokens_saved <= 0"],
                    "skipped": False,
                }
            ],
            "skipped_compressors": [],
            "pass": False,
        }

        monkeypatch.setattr(cli_evals, "_run_verify", lambda **kwargs: failing_report)

        runner = CliRunner()
        result = runner.invoke(main, ["verify", "--format", "json"])
        assert result.exit_code == 0, result.output
        data = json_module.loads(result.output)
        assert data["git_sha"] == "abc123"
        assert data["summary"]["tokens_saved"] == 0

        ci_result = runner.invoke(main, ["verify", "--ci"])
        assert ci_result.exit_code == 1, ci_result.output


class TestBenchmarkEdgeCases:
    """Edge case handling."""

    def test_unknown_compressor_skipped(self) -> None:
        """Unknown compressors are skipped instead of crashing the run."""
        from cutctx.evals.benchmark_runner import BenchmarkRunner
        from cutctx.evals.datasets import load_tool_output_samples

        dataset = load_tool_output_samples()
        runner = BenchmarkRunner()
        result = runner.run(
            dataset=dataset,
            compressors=["nonexistent_compressor"],
            n=1,
            parallel=1,
            seed=42,
        )

        assert len(result.results) == 0
