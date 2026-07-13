"""Benchmark runner — runs compressors against standard datasets.

Each compressor is wrapped in a ``CompressorAdapter`` that normalises its
unique ``compress()`` / ``crush()`` / ``extract()`` signature into a unified
``(text: str) -> CompressorResult`` callable.  Adapters handle optional
dependencies gracefully (``available=False`` if the import fails).
"""

from __future__ import annotations

import logging
import random
import re
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
from cutctx.evals.core import EvalCase, EvalSuite
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
    compress_case_fn: Callable[[EvalCase], CompressorResult] | None = None
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

    def __init__(self, *, llmlingua_model: str | None = None) -> None:
        self._adapters: dict[str, CompressorAdapter] = {}
        self._llmlingua_model = llmlingua_model
        self._register_adapters()

    # -- adapter registry -----------------------------------------------

    def _register_adapters(self) -> None:
        """Populate the adapter registry (called once at init)."""
        self._register_raw_passthrough()
        self._register_smart_crusher()
        self._register_log()
        self._register_search()
        self._register_diff()
        self._register_code()
        self._register_kompress()
        self._register_llmlingua()
        self._register_drain3()
        self._register_html()
        self._register_verbatim_compactor()
        self._register_content_router()

    # Each registration method has a guarded import so the module stays
    # importable even when optional packages are missing.

    def _register_raw_passthrough(self) -> None:
        """Register the explicit uncompressed denominator for release reports."""
        self._adapters["raw_passthrough"] = CompressorAdapter(
            name="raw_passthrough",
            available=True,
            compress_fn=_noop,
            display_name="RawPassthrough",
        )

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
                error = None
                if getattr(result, "used_fallback", False):
                    reason = getattr(result, "fallback_reason", None) or "unknown"
                    error = f"llmlingua_fallback:{reason}"
                return CompressorResult(
                    compressed=compressed,
                    tokens_saved=saved,
                    duration_ms=dt,
                    error=error,
                )

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
                error = None
                if getattr(result, "used_fallback", False):
                    reason = getattr(result, "fallback_reason", None) or "unknown"
                    error = f"llmlingua_fallback:{reason}"
                return CompressorResult(
                    compressed=compressed,
                    tokens_saved=saved,
                    duration_ms=dt,
                    error=error,
                )

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

            def _case_fn(case: EvalCase) -> CompressorResult:
                t0 = time.perf_counter()
                result = comp.compress(case.context, context=case.query)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(case.context) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["code"] = CompressorAdapter(
                name="code",
                available=True,
                compress_fn=_fn,
                compress_case_fn=_case_fn,
                display_name="Code",
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

            config = None
            if self._llmlingua_model:
                from cutctx.transforms.llmlingua_compressor import LLMLinguaConfig

                config = LLMLinguaConfig(model_name=self._llmlingua_model)
            comp = LLMLinguaCompressor(config) if config is not None else LLMLinguaCompressor()

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = comp.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                error = None
                if getattr(result, "used_fallback", False):
                    reason = getattr(result, "fallback_reason", None) or "unknown"
                    error = f"llmlingua_fallback:{reason}"
                return CompressorResult(
                    compressed=compressed,
                    tokens_saved=saved,
                    duration_ms=dt,
                    error=error,
                )

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

    def _register_verbatim_compactor(self) -> None:
        from cutctx.transforms.verbatim_compactor import VerbatimCompactor

        compactor = VerbatimCompactor()

        def _fn(text: str) -> CompressorResult:
            t0 = time.perf_counter()
            result = compactor.compress(text)
            dt = (time.perf_counter() - t0) * 1000
            compressed = result.compressed
            saved = (len(text) // 4) - (len(compressed) // 4)
            return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

        def _case_fn(case: EvalCase) -> CompressorResult:
            t0 = time.perf_counter()
            result = compactor.compress(
                case.context,
                context=case.query,
                critical_items=_get_critical_items(case),
            )
            dt = (time.perf_counter() - t0) * 1000
            compressed = result.compressed
            saved = (len(case.context) // 4) - (len(compressed) // 4)
            return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

        self._adapters["verbatim_compactor"] = CompressorAdapter(
            name="verbatim_compactor",
            available=True,
            compress_fn=_fn,
            compress_case_fn=_case_fn,
            display_name="VerbatimCompactor",
        )

    def _register_content_router(self) -> None:
        try:
            from cutctx.transforms.content_router import (
                CompressionStrategy,
                ContentRouter,
                ContentRouterConfig,
            )

            # Keep the default CI router benchmark deterministic and fast.
            # The heavyweight ML fallback has its own explicit `kompress`
            # adapter; ContentRouter here verifies routing plus structured
            # compressors without downloading/running model weights.
            router = ContentRouter(
                ContentRouterConfig(
                    enable_kompress=False,
                    fallback_strategy=CompressionStrategy.PASSTHROUGH,
                )
            )

            def _fn(text: str) -> CompressorResult:
                t0 = time.perf_counter()
                result = router.compress(text)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(text) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            def _case_fn(case: EvalCase) -> CompressorResult:
                t0 = time.perf_counter()
                result = router.compress(case.context, context=case.query)
                dt = (time.perf_counter() - t0) * 1000
                compressed = result.compressed
                saved = (len(case.context) // 4) - (len(compressed) // 4)
                return CompressorResult(compressed=compressed, tokens_saved=saved, duration_ms=dt)

            self._adapters["content_router"] = CompressorAdapter(
                name="content_router",
                available=True,
                compress_fn=_fn,
                compress_case_fn=_case_fn,
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
        warmup_cases: int = 0,
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
        warmup_cases:
            Number of initial cases to run as untimed warmup per compressor.
        """
        random.seed(seed)

        if metrics is None:
            metrics = [
                "ratio",
                "tokens_saved",
                "tokens_per_second",
                "f1",
                "rouge_l",
                "information_recall",
                "critical_item_recall",
                "verbatim_fidelity",
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

            if warmup_cases > 0:
                for case in cases[:warmup_cases]:
                    try:
                        self._compress_case(adapter, case)
                    except Exception:
                        logger.debug(
                            "Warmup failed for compressor '%s' on case '%s'", comp_key, case.id
                        )

            # Run compression in parallel
            per_case_results: list[dict[str, Any]] = []
            errors = 0

            with ThreadPoolExecutor(max_workers=parallel) as pool:
                future_map = {
                    pool.submit(self._compress_case, adapter, case): case for case in cases
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
            errors = sum(1 for r in per_case_results if r["error"])
            valid = [r for r in per_case_results if not r["error"]]
            if not valid:
                results.append(
                    CompressorBenchmarkResult(
                        dataset=dataset_name,
                        compressor=comp_key,
                        n=len(cases),
                        ratio=1.0,
                        tokens_saved=0,
                        avg_ms=0.0,
                        p50_ms=0.0,
                        errors=errors,
                        skipped=True,
                    )
                )
                continue
            cases_by_id = {case.id: case for case in cases}
            ratios = [
                r["compressed_tokens"] / r["original_tokens"] if r["original_tokens"] > 0 else 1.0
                for r in valid
            ]
            durations = [r["duration_ms"] for r in valid]
            tokens_saved = total_original_tokens - total_compressed_tokens

            avg_ratio = statistics.mean(ratios) if ratios else 0.0
            avg_ms = statistics.mean(durations) if durations else 0.0
            p50_ms = statistics.median(durations) if durations else 0.0
            total_duration_seconds = sum(durations) / 1000 if durations else 0.0
            tokens_per_second = (
                total_original_tokens / total_duration_seconds
                if total_duration_seconds > 0
                else None
            )

            # F1 / ROUGE-L / exact_match between original and compressed
            f1_vals: list[float] = []
            rouge_vals: list[float] = []
            em_vals: list[bool] = []
            for r in valid:
                orig_text = cases_by_id[r["id"]].context
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
                    orig_text = cases_by_id[r["id"]].context
                    comp_text = r["compressed"]
                    probes = generate_retrieval_probes(orig_text, n_probes=5)
                    if probes:
                        preserved = sum(1 for p in probes if p.lower() in comp_text.lower())
                        irecall_vals.append(preserved / len(probes))

            critical_item_recall = None
            critical_item_hits = 0
            critical_item_total = 0
            for r in valid:
                case = cases_by_id[r["id"]]
                critical_items = _get_critical_items(case)
                if not critical_items:
                    continue

                comp_text = r["compressed"].lower()
                critical_item_total += len(critical_items)
                critical_item_hits += sum(1 for item in critical_items if item.lower() in comp_text)

            if critical_item_total:
                critical_item_recall = critical_item_hits / critical_item_total

            verbatim_fidelity = None
            if critical_item_total:
                verbatim_fidelity = critical_item_hits / critical_item_total

            result = CompressorBenchmarkResult(
                dataset=dataset_name,
                compressor=comp_key,
                n=len(cases),
                ratio=avg_ratio,
                tokens_saved=tokens_saved,
                tokens_per_second=tokens_per_second,
                avg_ms=avg_ms,
                p50_ms=p50_ms,
                f1=statistics.mean(f1_vals) if f1_vals else None,
                rouge_l=statistics.mean(rouge_vals) if rouge_vals else None,
                exact_match=sum(em_vals) / len(em_vals) if em_vals else None,
                information_recall=statistics.mean(irecall_vals) if irecall_vals else None,
                critical_item_recall=critical_item_recall,
                verbatim_fidelity=verbatim_fidelity,
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
    def _compress_case(adapter: CompressorAdapter, case: EvalCase) -> CompressorResult:
        """Run one adapter on one text string."""
        try:
            if adapter.compress_case_fn is not None:
                return adapter.compress_case_fn(case)
            return adapter.compress_fn(case.context)
        except Exception as exc:
            return CompressorResult(
                compressed=case.context,
                tokens_saved=0,
                duration_ms=0.0,
                error=str(exc),
            )


def _noop(text: str) -> CompressorResult:
    """Fallback adapter for unavailable compressors."""
    return CompressorResult(compressed=text, tokens_saved=0, duration_ms=0.0)


def _get_critical_items(case: EvalCase) -> list[str]:
    """Return benchmark-critical strings that should survive compression."""
    metadata = getattr(case, "metadata", {}) or {}
    declared = metadata.get("critical_items")
    if isinstance(declared, list):
        items = [str(item).strip() for item in declared if str(item).strip()]
        if items:
            return _dedupe_preserving_order(items)

    ground_truth = getattr(case, "ground_truth", None)
    if isinstance(ground_truth, str) and ground_truth.strip():
        return [ground_truth.strip()]

    return _heuristic_critical_items(getattr(case, "context", ""))


def _heuristic_critical_items(text: str) -> list[str]:
    """Extract a small set of likely critical strings when fixtures do not declare them."""
    patterns = (
        r"[A-Za-z0-9_/.-]+\.py:\d+",
        r"\b[A-Z][A-Za-z]+Error\b",
        r"\b(?:req|build|INC)-?[A-Za-z0-9_-]{4,}\b",
        r"\b[A-Z]{2,}(?:_[A-Z0-9]+)+\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
    )
    items: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, text):
            value = match.strip()
            if value:
                items.append(value)
            if len(items) >= 5:
                return _dedupe_preserving_order(items)
    return _dedupe_preserving_order(items)


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
