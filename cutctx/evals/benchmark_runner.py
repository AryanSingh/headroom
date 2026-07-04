"""Benchmark runner — runs compressors against standard datasets.

Each compressor is wrapped in a ``CompressorAdapter`` that normalises its
unique ``compress()`` / ``crush()`` / ``extract()`` signature into a unified
``(text: str) -> CompressorResult`` callable.  Adapters handle optional
dependencies gracefully (``available=False`` if the import fails).
"""

from __future__ import annotations

import logging
import random
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from cutctx.evals.benchmark_report import (
    BenchmarkSuiteResult,
    CompressorBenchmarkResult,
)
from cutctx.evals.core import EvalSuite
from cutctx.evals.metrics import (
    compute_exact_match,
    compute_f1,
    compute_rouge_l,
    compute_semantic_similarity,
)

logger = logging.getLogger(__name__)


# ── Unified result wrapper ─────────────────────────────────────────────


@dataclass
class CompressorResult:
    """Normalised result from any compressor adapter."""

    compressed: str
    tokens_saved: int = 0
    duration_ms: float = 0.0
    error: str | None = None


# ── Adapter type ───────────────────────────────────────────────────────


@dataclass
class CompressorAdapter:
    """Wraps a compressor into a unified callable interface.

    Attributes:
        name: Short identifier (e.g. ``"smart_crusher"``).
        available: Whether the underlying package can be imported.
        compress_fn: Callable that accepts raw text and returns
            a :class:`CompressorResult`.
        display_name: Human-readable label for tables.
    """

    name: str
    available: bool
    compress_fn: Callable[[str], CompressorResult]
    display_name: str = ""


# ── Runner ─────────────────────────────────────────────────────────────


class BenchmarkRunner:
    """Runs compressors against evaluation datasets and collects metrics.

    Usage::

        runner = BenchmarkRunner()
        result = runner.run(
            dataset=dataset,
            compressors=["smart_crusher", "log", "content_router"],
            metrics=["ratio", "f1"],
            n=50,
            parallel=4,
            seed=42,
        )
        print(result.to_markdown("ratio"))
    """

    def __init__(self) -> None:
        self._adapters: dict[str, CompressorAdapter] = {}
        self._register_adapters()

    # -- adapter registry -----------------------------------------------

    def _register_adapters(self) -> None:
        """Populate the adapter registry (called once at init)."""
        self._register_smart_crusher()
        self._register_log()
        self._register_search()
        self._register_diff()
        self._register_code()
        self._register_kompress()
        self._register_llmlingua()
        self._register_drain3()
        self._register_html()
        self._register_content_router()

    # Each registration method has a guarded import so the module stays
    # importable even when optional packages are missing.

    def _register_smart_crusher(self) -> None:
        try:
            from cutctx.transforms.smart_crusher import SmartCrusher

            crusher = SmartCrusher()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = crusher.crush(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["smart_crusher"] = CompressorAdapter(
                name="smart_crusher",
                available=True,
                compress_fn=_fn,
                display_name="SmartCrusher",
            )
        except ImportError:
            self._adapters["smart_crusher"] = CompressorAdapter(
                name="smart_crusher", available=False, compress_fn=_noop
            )

    def _register_log(self) -> None:
        try:
            from cutctx.transforms.log_compressor import LogCompressor

            comp = LogCompressor()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = comp.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["log"] = CompressorAdapter(
                name="log", available=True, compress_fn=_fn, display_name="Log"
            )
        except ImportError:
            self._adapters["log"] = CompressorAdapter(
                name="log", available=False, compress_fn=_noop
            )

    def _register_search(self) -> None:
        try:
            from cutctx.transforms.search_compressor import SearchCompressor

            comp = SearchCompressor()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = comp.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["search"] = CompressorAdapter(
                name="search", available=True, compress_fn=_fn, display_name="Search"
            )
        except ImportError:
            self._adapters["search"] = CompressorAdapter(
                name="search", available=False, compress_fn=_noop
            )

    def _register_diff(self) -> None:
        try:
            from cutctx.transforms.diff_compressor import DiffCompressor

            comp = DiffCompressor()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = comp.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["diff"] = CompressorAdapter(
                name="diff", available=True, compress_fn=_fn, display_name="Diff"
            )
        except ImportError:
            self._adapters["diff"] = CompressorAdapter(
                name="diff", available=False, compress_fn=_noop
            )

    def _register_code(self) -> None:
        try:
            from cutctx.transforms.code_compressor import CodeAwareCompressor

            comp = CodeAwareCompressor()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = comp.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["code"] = CompressorAdapter(
                name="code", available=True, compress_fn=_fn, display_name="Code"
            )
        except ImportError:
            self._adapters["code"] = CompressorAdapter(
                name="code", available=False, compress_fn=_noop
            )

    def _register_kompress(self) -> None:
        try:
            from cutctx.transforms.kompress_compressor import KompressCompressor

            comp = KompressCompressor()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = comp.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["kompress"] = CompressorAdapter(
                name="kompress", available=True, compress_fn=_fn, display_name="Kompress"
            )
        except ImportError:
            self._adapters["kompress"] = CompressorAdapter(
                name="kompress", available=False, compress_fn=_noop
            )

    def _register_llmlingua(self) -> None:
        try:
            from cutctx.transforms.llmlingua_compressor import LLMLinguaCompressor

            comp = LLMLinguaCompressor()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = comp.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["llmlingua"] = CompressorAdapter(
                name="llmlingua", available=True, compress_fn=_fn, display_name="LLMLingua"
            )
        except ImportError:
            self._adapters["llmlingua"] = CompressorAdapter(
                name="llmlingua", available=False, compress_fn=_noop
            )

    def _register_drain3(self) -> None:
        try:
            from cutctx.transforms.drain3_compressor import Drain3LogCompressor

            comp = Drain3LogCompressor()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = comp.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["drain3"] = CompressorAdapter(
                name="drain3", available=True, compress_fn=_fn, display_name="Drain3"
            )
        except ImportError:
            self._adapters["drain3"] = CompressorAdapter(
                name="drain3", available=False, compress_fn=_noop
            )

    def _register_html(self) -> None:
        try:
            from cutctx.transforms.html_extractor import HTMLExtractor

            extractor = HTMLExtractor()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = extractor.extract(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.extracted
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["html"] = CompressorAdapter(
                name="html", available=True, compress_fn=_fn, display_name="HTML"
            )
        except ImportError:
            self._adapters["html"] = CompressorAdapter(
                name="html", available=False, compress_fn=_noop
            )

    def _register_content_router(self) -> None:
        try:
            from cutctx.transforms.content_router import ContentRouter

            router = ContentRouter()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = router.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["content_router"] = CompressorAdapter(
                name="content_router",
                available=True,
                compress_fn=_fn,
                display_name="ContentRouter",
            )
        except ImportError:
            self._adapters["content_router"] = CompressorAdapter(
                name="content_router", available=False, compress_fn=_noop
            )

    # -- public API ------------------------------------------------------

    def list_compressors(self) -> list[CompressorAdapter]:
        """Return all registered adapters."""
        return list(self._adapters.values())

    def run(
        self,
        dataset: EvalSuite,
        compressors: list[str] | None = None,
        metrics: list[str] | None = None,
        n: int = 50,
        parallel: int = 4,
        seed: int = 42,
    ) -> BenchmarkSuiteResult:
        """Run compressors against *dataset* and return aggregated results.

        Parameters
        ----------
        dataset:
            Evaluation suite (list of ``EvalCase`` instances).
        compressors:
            Which compressor keys to test.  ``None`` means all registered.
        metrics:
            Which metrics to compute.  ``None`` means all available.
        n:
            Maximum number of cases to use from the dataset.
        parallel:
            Thread pool size for parallel compression.
        seed:
            Random seed for reproducible sampling.
        """
        random.seed(seed)

        if metrics is None:
            metrics = [
                "ratio",
                "tokens_saved",
                "f1",
                "rouge_l",
                "information_recall",
                "exact_match",
            ]
        if compressors is None:
            compressors = sorted(self._adapters.keys())

        cases = list(dataset.cases)
        if len(cases) > n:
            cases = random.sample(cases, n)

        dataset_name = dataset.name
        metric_set = set(metrics)
        results: list[CompressorBenchmarkResult] = []
        duration_seconds = 0.0

        start_total = time.perf_counter()

        for comp_key in compressors:
            adapter = self._adapters.get(comp_key)
            if adapter is None:
                logger.warning("Unknown compressor '%s' — skipping", comp_key)
                continue

            if not adapter.available:
                results.append(
                    CompressorBenchmarkResult(
                        dataset=dataset_name,
                        compressor=comp_key,
                        n=len(cases),
                        ratio=0.0,
                        tokens_saved=0,
                        avg_ms=0.0,
                        p50_ms=0.0,
                        skipped=True,
                    )
                )
                continue

            # Run compression in parallel
            per_case_results: list[dict[str, Any]] = []
            errors = 0

            with ThreadPoolExecutor(max_workers=parallel) as pool:
                future_map = {
                    pool.submit(self._compress_case, adapter, case.context): case for case in cases
                }
                for future in as_completed(future_map):
                    case = future_map[future]
                    try:
                        cr = future.result()
                        if cr.error:
                            errors += 1
                        per_case_results.append(
                            {
                                "id": case.id,
                                "original_len": len(case.context),
                                "original_tokens": len(case.context) // 4,
                                "compressed": cr.compressed,
                                "compressed_tokens": len(cr.compressed) // 4,
                                "duration_ms": cr.duration_ms,
                                "error": cr.error,
                                "ground_truth": case.ground_truth,
                            }
                        )
                    except Exception as exc:
                        errors += 1
                        per_case_results.append(
                            {
                                "id": case.id,
                                "original_len": len(case.context),
                                "original_tokens": len(case.context) // 4,
                                "compressed": case.context,
                                "compressed_tokens": len(case.context) // 4,
                                "duration_ms": 0.0,
                                "error": str(exc),
                                "ground_truth": case.ground_truth,
                            }
                        )

            # Aggregate metrics
            if not per_case_results:
                continue

            total_original_tokens = sum(r["original_tokens"] for r in per_case_results)
            total_compressed_tokens = sum(r["compressed_tokens"] for r in per_case_results)
            valid = [r for r in per_case_results if not r["error"]]
            ratios = [
                r["compressed_tokens"] / r["original_tokens"] if r["original_tokens"] > 0 else 1.0
                for r in valid
            ]
            durations = [r["duration_ms"] for r in valid]
            tokens_saved = total_original_tokens - total_compressed_tokens

            avg_ratio = statistics.mean(ratios) if ratios else 0.0
            avg_ms = statistics.mean(durations) if durations else 0.0
            p50_ms = statistics.median(durations) if durations else 0.0

            # F1 / ROUGE-L / exact_match between original and compressed
            f1_vals: list[float] = []
            rouge_vals: list[float] = []
            em_vals: list[bool] = []
            for r in valid:
                orig_text = next(c.context for c in cases if c.id == r["id"])
                comp_text = r["compressed"]
                try:
                    f1_vals.append(compute_f1(orig_text, comp_text))
                except Exception:
                    pass
                try:
                    rouge_vals.append(compute_rouge_l(orig_text, comp_text))
                except Exception:
                    pass
                try:
                    em_vals.append(compute_exact_match(orig_text, comp_text))
                except Exception:
                    pass

            # Information recall: generate probes and check preservation
            irecall_vals: list[float] = []
            if "information_recall" in metric_set:
                from cutctx.evals.datasets import generate_retrieval_probes

                for r in valid:
                    orig_text = next(c.context for c in cases if c.id == r["id"])
                    comp_text = r["compressed"]
                    probes = generate_retrieval_probes(orig_text, n_probes=5)
                    if probes:
                        preserved = sum(1 for p in probes if p.lower() in comp_text.lower())
                        irecall_vals.append(preserved / len(probes))

            result = CompressorBenchmarkResult(
                dataset=dataset_name,
                compressor=comp_key,
                n=len(cases),
                ratio=avg_ratio,
                tokens_saved=tokens_saved,
                avg_ms=avg_ms,
                p50_ms=p50_ms,
                f1=statistics.mean(f1_vals) if f1_vals else None,
                rouge_l=statistics.mean(rouge_vals) if rouge_vals else None,
                exact_match=sum(em_vals) / len(em_vals) if em_vals else None,
                information_recall=statistics.mean(irecall_vals) if irecall_vals else None,
                errors=errors,
                skipped=False,
            )

            # Semantic similarity (requires sentence-transformers)
            if "semantic_sim" in metric_set:
                sim_vals: list[float] = []
                for r in valid:
                    orig_text = next(c.context for c in cases if c.id == r["id"])
                    comp_text = r["compressed"]
                    try:
                        sim = compute_semantic_similarity(orig_text, comp_text)
                        sim_vals.append(sim)
                    except (ImportError, Exception):
                        pass
                if sim_vals:
                    result.semantic_sim = statistics.mean(sim_vals)

            results.append(result)

        duration_seconds = time.perf_counter() - start_total

        suite_result = BenchmarkSuiteResult(
            seed=seed,
            compressors=compressors,
            datasets=[dataset_name],
            results=results,
        )
        suite_result.totals["duration_seconds"] = duration_seconds
        suite_result._compute_totals()
        return suite_result

    # -- internal helpers ------------------------------------------------

    @staticmethod
    def _compress_case(adapter: CompressorAdapter, text: str) -> CompressorResult:
        """Run one adapter on one text string."""
        try:
            return adapter.compress_fn(text)
        except Exception as exc:
            return CompressorResult(
                compressed=text,
                tokens_saved=0,
                duration_ms=0.0,
                error=str(exc),
            )


def _noop(text: str) -> CompressorResult:
    """Fallback adapter for unavailable compressors."""
    return CompressorResult(compressed=text, tokens_saved=0, duration_ms=0.0)
